"""Fail-closed runtime safety decision core for SAFE-00.

`decide(request, evidence)` is deterministic for identical inputs and frozen
artifact semantics.  The I/O shell re-hashes every referenced artifact on every
call (canonical JSON for Gate evidence, raw bytes for the threshold registry);
`_decide_verified` is the pure decision kernel.
"""
from __future__ import annotations

import csv
import copy
import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml
from jsonschema import Draft202012Validator, FormatChecker


MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parents[1]
CONFIG = REPO / "20_engineering" / "config" / "safety_gate"
POLICY_PATH = CONFIG / "safety_policy_v1.yaml"
REQUEST_SCHEMA_PATH = CONFIG / "safety_request.schema.json"
EVIDENCE_SCHEMA_PATH = CONFIG / "evidence_bundle.schema.json"
RESPONSE_SCHEMA_PATH = CONFIG / "safety_response.schema.json"
KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")
MIN_HMAC_KEY_BYTES = 32


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _unique_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    document: Dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON object key: {key}")
        document[key] = value
    return document


def _reject_nonfinite(token: str) -> Any:
    raise ValueError(f"non-finite JSON number: {token}")


def load_strict_json(path: Path) -> Dict[str, Any]:
    """Load UTF-8 JSON while rejecting duplicate keys and NaN/Infinity."""
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_nonfinite,
    )
    if not isinstance(value, dict):
        raise ValueError("Gate JSON root must be an object")
    return value


def canonical_json_sha256_file(path: Path) -> str:
    """Hash JSON meaning, not checkout-specific whitespace or line endings."""
    return sha256_bytes(canonical_bytes(load_strict_json(path)))


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML mapping key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_strict_yaml(path: Path) -> Dict[str, Any]:
    value = yaml.load(
        path.read_text(encoding="utf-8"),
        Loader=_UniqueKeySafeLoader,
    )
    if not isinstance(value, dict):
        raise ValueError("YAML root must be a mapping")
    return value


def canonical_yaml_sha256_file(path: Path) -> str:
    return sha256_bytes(canonical_bytes(load_strict_yaml(path)))


def load_strict_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        if not fields or len(fields) != len(set(fields)):
            raise ValueError("CSV header is missing or contains duplicates")
        rows: List[Dict[str, str]] = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV row does not match its header")
            rows.append(dict(row))
    return rows


def canonical_csv_table_sha256(
    rows: List[Dict[str, str]],
    key_fields: Iterable[str],
) -> str:
    keys = tuple(key_fields)
    seen = set()
    for row in rows:
        key = tuple(row[field] for field in keys)
        if key in seen:
            raise ValueError(f"duplicate CSV row key: {key}")
        seen.add(key)
    ordered = sorted(rows, key=lambda row: tuple(row[field] for field in keys))
    return sha256_bytes(canonical_bytes(ordered))


def load_policy(path: Path = POLICY_PATH) -> Dict[str, Any]:
    return load_strict_yaml(path)


def load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validation_errors(document: Any, schema_path: Path) -> List[str]:
    validator = Draft202012Validator(load_schema(schema_path),
                                     format_checker=FormatChecker())
    return sorted(
        f"{'/'.join(str(x) for x in error.absolute_path) or '<root>'}: {error.message}"
        for error in validator.iter_errors(document)
    )


def validate_response(response: Dict[str, Any]) -> None:
    errors = _validation_errors(response, RESPONSE_SCHEMA_PATH)
    if errors:
        raise ValueError("invalid SafetyResponse: " + " | ".join(errors))


def _parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)


def _time_text(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z")


def _min_time_text(values: Iterable[str]) -> str:
    return _time_text(min(_parse_time(value) for value in values))


def compute_scenario_hash(
    request: Dict[str, Any],
    evidence: Dict[str, Any],
) -> str:
    """Bind every decision input, including request/evidence time boundaries."""
    request_payload = copy.deepcopy(request)
    request_payload.pop("scenario_hash", None)
    request_payload.pop("request_id", None)
    evidence_payload = copy.deepcopy(evidence)
    evidence_payload.pop("scenario_hash", None)
    for record in evidence_payload.get("artifact_records", []):
        record.pop("scenario_hash", None)
    payload = {
        "request": request_payload,
        "evidence": evidence_payload,
    }
    return sha256_bytes(canonical_bytes(payload))


def _unique(items: Iterable[str]) -> List[str]:
    output: List[str] = []
    for item in items:
        if item not in output:
            output.append(item)
    return output


def _record_hash_values(record: Dict[str, Any]) -> Iterable[str]:
    yield record["gate_json_sha256"]
    yield record["registry_sha256"]
    yield record["scenario_hash"]
    row = record.get("row_binding")
    if row is not None:
        for field in (
            "source_sha256",
            "row_sha256",
            "case_config_sha256",
            "case_sha256",
            "mu_reference_sha256",
        ):
            yield row[field]


def _provenance_complete(records: List[Dict[str, Any]]) -> bool:
    required = (
        "artifact_id",
        "artifact_scope",
        "gate_json_path",
        "gate_json_hash_mode",
        "gate_json_sha256",
        "gate_verdict",
        "registry_sha256",
        "scenario_hash",
        "data_row_refs",
        "row_binding",
        "model_level",
        "certification",
        "provisional_flags",
        "flex_status",
    )
    if not records:
        return False
    for record in records:
        if any(field not in record for field in required):
            return False
        if not record["data_row_refs"]:
            return False
        if record["artifact_scope"] == "SCENARIO_ROW":
            if not isinstance(record["row_binding"], dict):
                return False
        elif record["artifact_scope"] == "GLOBAL_GATE_NON_SCENARIO":
            if record["row_binding"] is not None:
                return False
        else:
            return False
    return True


def _authorization_mac_payload(
    response: Dict[str, Any],
    authorization: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "response": {
            key: value for key, value in response.items()
            if key != "authorization"
        },
        "authorization_context": {
            key: value for key, value in authorization.items()
            if key != "mac_hex"
        },
    }


def authorization_mac_hex(
    response: Dict[str, Any],
    authorization: Dict[str, Any],
    authorization_key: bytes,
) -> str:
    return hmac.new(
        authorization_key,
        canonical_bytes(_authorization_mac_payload(response, authorization)),
        hashlib.sha256,
    ).hexdigest()


def _base_response(
    request: Dict[str, Any],
    evidence: Dict[str, Any],
    physical_state: str,
    decision: str,
    reasons: Iterable[str],
    valid_until: str,
    provenance_records: List[Dict[str, Any]] | None = None,
    fallback_trace: List[Dict[str, Any]] | None = None,
    modified_action: Dict[str, Any] | None = None,
    authorization_key: bytes | None = None,
    authorization_key_id: str | None = None,
    authorization_not_before: str | None = None,
) -> Dict[str, Any]:
    reason_codes = _unique(reasons)
    records = provenance_records or []
    evidence_hashes = sorted({
        value
        for record in records
        for value in _record_hash_values(record)
    })
    response = {
        "contract_version": "safety-gate-v1",
        "request_id": request.get("request_id", "INVALID_REQUEST"),
        "physical_state": physical_state,
        "decision": decision,
        "reason_code": reason_codes[0],
        "reason_codes": reason_codes,
        "modified_action": modified_action,
        "valid_until": valid_until,
        "evidence_hashes": evidence_hashes,
        "provenance": {
            "complete": _provenance_complete(records),
            "records": records,
        },
        "fallback_trace": fallback_trace or [],
        "authorization": None,
    }
    if decision in {"ALLOW", "MODIFY"}:
        if (not isinstance(authorization_key, bytes)
                or len(authorization_key) < MIN_HMAC_KEY_BYTES
                or not authorization_key_id or not authorization_not_before):
            raise ValueError("executable response requires an injected HMAC key")
        authorization = {
            "scheme": "HMAC-SHA256",
            "key_id": authorization_key_id,
            "not_before": authorization_not_before,
            "expires_at": valid_until,
            "enforcement_required": True,
        }
        authorization["mac_hex"] = authorization_mac_hex(
            response, authorization, authorization_key)
        response["authorization"] = authorization
    validate_response(response)
    return response


def _invalid_response(
    request: Any,
    evidence: Any,
    reason: str,
    decision: str = "ABORT",
) -> Dict[str, Any]:
    req = request if isinstance(request, dict) else {}
    ev = evidence if isinstance(evidence, dict) else {}
    when = ev.get("decision_time") or req.get("timestamp") or "1970-01-01T00:00:00Z"
    return _base_response(req, ev, "UNKNOWN", decision, [reason], when)


def verify_authorization(
    response: Dict[str, Any],
    at_time: str,
    authorization_key: bytes,
    expected_key_id: str,
) -> bool:
    try:
        validate_response(response)
        if (not isinstance(authorization_key, bytes)
                or len(authorization_key) < MIN_HMAC_KEY_BYTES):
            return False
        if response["decision"] not in {"ALLOW", "MODIFY"}:
            return False
        if response["physical_state"] != "SAFE":
            return False
        if (not response["provenance"]["complete"]
                or not response["provenance"]["records"]):
            return False
        if (not response["reason_codes"]
                or response["reason_code"] != response["reason_codes"][0]):
            return False
        if response["decision"] == "ALLOW":
            if (response["reason_code"] != "AUTHORIZED_SAFE"
                    or response["modified_action"] is not None):
                return False
        else:
            if (response["reason_code"] != "AUTHORIZED_WITH_MODIFICATION"
                    or response["modified_action"] is None):
                return False
        auth = response["authorization"]
        if (not auth or not auth["enforcement_required"]
                or auth["scheme"] != "HMAC-SHA256"
                or auth["key_id"] != expected_key_id):
            return False
        now = _parse_time(at_time)
        not_before = _parse_time(auth["not_before"])
        expires_at = _parse_time(auth["expires_at"])
        expected = authorization_mac_hex(response, auth, authorization_key)
        return (
            hmac.compare_digest(auth["mac_hex"], expected)
            and not_before <= now <= expires_at
            and auth["expires_at"] == response["valid_until"]
        )
    except (KeyError, TypeError, ValueError):
        return False


def _safe_repo_path(relative_path: str, repo_root: Path) -> Path:
    root = repo_root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("artifact path escapes repository") from exc
    return candidate


def _verdict(document: Dict[str, Any], dotted_key: str) -> Any:
    value: Any = document
    for key in dotted_key.split("."):
        value = value[key]
    return value


def _provenance_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "artifact_id": record["artifact_id"],
        "artifact_scope": record["artifact_scope"],
        "gate_json_path": record["gate_json_path"],
        "gate_json_hash_mode": record["gate_json_hash_mode"],
        "gate_json_sha256": record["gate_json_sha256"],
        "gate_verdict": record["gate_verdict"],
        "registry_sha256": record["registry_sha256"],
        "scenario_hash": record["scenario_hash"],
        "data_row_refs": list(record["data_row_refs"]),
        "row_binding": copy.deepcopy(record["row_binding"]),
        "model_level": record["model_level"],
        "certification": record["certification"],
        "provisional_flags": list(record["provisional_flags"]),
        "flex_status": record["flex_status"],
    }


def _value_at_path(document: Dict[str, Any], dotted_path: str) -> Any:
    value: Any = document
    for key in dotted_path.split("."):
        value = value[key]
    return value


def candidate_row_claim(policy: Dict[str, Any]) -> Dict[str, Any]:
    binding = policy["candidate_binding"]
    row = binding["row_source"]
    case = binding["case_source"]
    mu = binding["mu_reference_source"]
    return {
        "source_path": row["path"],
        "source_hash_mode": row["hash_mode"],
        "source_sha256": row["canonical_table_sha256"],
        "key": copy.deepcopy(row["key"]),
        "row_hash_mode": row["row_hash_mode"],
        "row_sha256": row["canonical_row_sha256"],
        "case_config_path": case["path"],
        "case_config_hash_mode": case["hash_mode"],
        "case_config_sha256": case["canonical_document_sha256"],
        "case_key": case["key_path"],
        "case_sha256": case["canonical_case_sha256"],
        "mu_reference_path": mu["path"],
        "mu_reference_hash_mode": mu["hash_mode"],
        "mu_reference_sha256": mu["canonical_document_sha256"],
    }


def _same_number(left: Any, right: Any, tolerance: Any) -> bool:
    return abs(Decimal(str(left)) - Decimal(str(right))) <= Decimal(
        str(tolerance))


def _verify_candidate_binding(
    request: Dict[str, Any],
    records: Dict[str, Dict[str, Any]],
    policy: Dict[str, Any],
    repo_root: Path,
) -> str | None:
    binding = policy["candidate_binding"]
    row_policy = binding["row_source"]
    case_policy = binding["case_source"]
    mu_policy = binding["mu_reference_source"]
    derived = binding["derived_request"]

    if request["candidate_id"] != binding["candidate_id"]:
        return "CANDIDATE_ID_MISMATCH"
    if request["proposed_action"]["task_action"] != binding["task_action"]:
        return "CANDIDATE_ACTION_MISMATCH"

    artifact_id = binding["source_artifact_id"]
    record = records.get(artifact_id)
    if record is None:
        return "CANDIDATE_ROW_BINDING_MISMATCH"
    if (record["artifact_scope"] != "SCENARIO_ROW"
            or record["data_row_refs"] != [binding["row_ref"]]
            or record["row_binding"] != candidate_row_claim(policy)):
        return "CANDIDATE_ROW_BINDING_MISMATCH"

    try:
        row_path = _safe_repo_path(row_policy["path"], repo_root)
        rows = load_strict_csv(row_path)
        table_hash = canonical_csv_table_sha256(
            rows, row_policy["key_fields"])
        if table_hash != row_policy["canonical_table_sha256"]:
            return "CANDIDATE_ROW_HASH_MISMATCH"
        selected = [
            row for row in rows
            if all(row[field] == str(value)
                   for field, value in row_policy["key"].items())
        ]
        if len(selected) != 1:
            return "CANDIDATE_ROW_BINDING_MISMATCH"
        row = selected[0]
        if sha256_bytes(canonical_bytes(row)) != row_policy[
                "canonical_row_sha256"]:
            return "CANDIDATE_ROW_HASH_MISMATCH"
        if any(row.get(field) != str(value)
               for field, value in row_policy["required_values"].items()):
            return "CANDIDATE_ROW_NOT_FEASIBLE"

        case_path = _safe_repo_path(case_policy["path"], repo_root)
        case_document = load_strict_yaml(case_path)
        if sha256_bytes(canonical_bytes(case_document)) != case_policy[
                "canonical_document_sha256"]:
            return "CANDIDATE_CASE_CONFIG_HASH_MISMATCH"
        case = _value_at_path(case_document, case_policy["key_path"])
        if (sha256_bytes(canonical_bytes(case))
                != case_policy["canonical_case_sha256"]):
            return "CANDIDATE_CASE_CONFIG_HASH_MISMATCH"

        mu_path = _safe_repo_path(mu_policy["path"], repo_root)
        mu_document = load_strict_yaml(mu_path)
        if sha256_bytes(canonical_bytes(mu_document)) != mu_policy[
                "canonical_document_sha256"]:
            return "CANDIDATE_MU_REFERENCE_HASH_MISMATCH"
        mu_reference = _value_at_path(
            mu_document, mu_policy["key_path"])
    except (
        OSError,
        UnicodeDecodeError,
        csv.Error,
        KeyError,
        TypeError,
        ValueError,
        yaml.YAMLError,
    ):
        return "CANDIDATE_SOURCE_INVALID"

    key = row_policy["key"]
    if (case_document.get("base_config") != mu_policy["path"]
            or key["case"] not in case_document["cases"]
            or key["strategy"] not in case_document["strategies"]
            or request["candidate_id"]
            != f"{key['case']}-{key['strategy']}"):
        return "CANDIDATE_ROW_BINDING_MISMATCH"
    if not _same_number(
            mu_reference, mu_policy["expected_kg"],
            derived["numeric_abs_tolerance"]):
        return "CANDIDATE_MU_REFERENCE_MISMATCH"

    state = request["state_estimate"]
    expected_mu = Decimal(str(case["m_t_kg"])) / Decimal(str(mu_reference))
    expected_alpha = derived["strategy_alpha"].get(key["strategy"])
    if expected_alpha is None:
        return "CANDIDATE_STRATEGY_UNBOUND"
    if state["geometry_class"] != case["cls"]:
        return "CANDIDATE_STATE_BINDING_MISMATCH"
    for actual, expected in (
        (state["omega_dps"], case["omega_dps"]),
        (state["mu"], expected_mu),
        (state["alpha"], expected_alpha),
        (state["lambda_actual"], derived["lambda_actual"]),
        (state["lambda_grid"], derived["lambda_grid"]),
    ):
        if not _same_number(
                actual, expected, derived["numeric_abs_tolerance"]):
            return "CANDIDATE_STATE_BINDING_MISMATCH"
    return None


def _verify_artifacts(
    request: Dict[str, Any],
    evidence: Dict[str, Any],
    policy: Dict[str, Any],
    repo_root: Path,
) -> Tuple[str | None, List[Dict[str, Any]]]:
    expected_registry = policy["threshold_registry"]["sha256"]
    try:
        registry_path = _safe_repo_path(
            policy["threshold_registry"]["path"], repo_root)
        registry_actual = sha256_file(registry_path)
    except (OSError, ValueError):
        return "REGISTRY_HASH_MISMATCH", []
    if registry_actual != expected_registry:
        return "REGISTRY_HASH_MISMATCH", []
    if request["threshold_registry_hash"] != expected_registry:
        return "REGISTRY_HASH_MISMATCH", []

    records = {record["artifact_id"]: record for record in evidence["artifact_records"]}
    if len(records) != len(evidence["artifact_records"]):
        return "PROVENANCE_INCOMPLETE", []
    required = policy["required_artifacts_by_level"][request["model_level"]]
    if set(records) != set(required):
        return "PROVENANCE_INCOMPLETE", []

    verified: List[Dict[str, Any]] = []
    for artifact_id in required:
        record = records[artifact_id]
        frozen = policy["gate_artifacts"][artifact_id]
        if record["gate_json_path"] != frozen["path"]:
            return "PROVENANCE_INCOMPLETE", []
        if (record["model_level"] != request["model_level"]
                or record["certification"]
                != request["model_validity"]["certification"]):
            return "PROVENANCE_MODEL_CONTEXT_MISMATCH", []
        if record["artifact_scope"] != frozen["scenario_scope"]:
            return "PROVENANCE_SCOPE_MISMATCH", []
        if frozen["scenario_scope"] == "GLOBAL_GATE_NON_SCENARIO":
            if (record["row_binding"] is not None
                    or any(ref not in frozen["allowed_non_scenario_refs"]
                           for ref in record["data_row_refs"])):
                return "PROVENANCE_SCOPE_MISMATCH", []
        if (frozen["hash_mode"] != "CANONICAL_JSON_SHA256_V1"
                or record["gate_json_hash_mode"] != frozen["hash_mode"]):
            return "PROVENANCE_INCOMPLETE", []
        if record["registry_sha256"] != expected_registry:
            return "REGISTRY_HASH_MISMATCH", []
        if record["scenario_hash"] != request["scenario_hash"]:
            return "SCENARIO_HASH_MISMATCH", []
        try:
            path = _safe_repo_path(record["gate_json_path"], repo_root)
            document = load_strict_json(path)
            actual_hash = sha256_bytes(canonical_bytes(document))
            actual_verdict = _verdict(document, frozen["verdict_key"])
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            return "GATE_ARTIFACT_HASH_MISMATCH", []
        if (actual_hash != frozen["canonical_json_sha256"]
                or record["gate_json_sha256"] != actual_hash):
            return "GATE_ARTIFACT_HASH_MISMATCH", []
        if (actual_verdict != frozen["expected_verdict"]
                or record["gate_verdict"] != actual_verdict):
            return "GATE_VERDICT_MISMATCH", []
        if artifact_id == "sim11":
            actual_flags = set(document.get("provisional_fields", []))
            if not actual_flags.issubset(set(record["provisional_flags"])):
                return "PROVISIONAL_FLAGS_MISSING", []
            if not actual_flags.issubset(
                    set(request["model_validity"]["provisional_flags"])):
                return "PROVISIONAL_FLAGS_MISSING", []
        verified.append(_provenance_record(record))
    candidate_error = _verify_candidate_binding(
        request, records, policy, repo_root)
    if candidate_error:
        return candidate_error, []
    return None, verified


def _in_domain(request: Dict[str, Any], level: str,
               policy: Dict[str, Any]) -> bool:
    state = request["state_estimate"]
    domain = policy["domains"][level]
    if state["geometry_class"] not in domain["geometry_class"]:
        return False
    for field in ("mu", "omega_dps", "lambda_actual", "alpha"):
        lower, upper = domain[field]
        value = state[field]
        if value < lower or value > upper:
            return False
    for field in ("contact_T_c_ms", "panel_f1_hz"):
        if field in domain:
            value = state[field]
            if value is None:
                return False
            lower, upper = domain[field]
            if value < lower or value > upper:
                return False
    return True


def _fallback_trace(request: Dict[str, Any],
                    policy: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str | None]:
    trace: List[Dict[str, Any]] = []
    problem = None
    for fallback in request["model_validity"]["fallback_chain"]:
        target = fallback["target_level"]
        computed = _in_domain(request, target, policy) if fallback["domain_checked"] else None
        trace.append({
            "target_level": target,
            "domain_checked": fallback["domain_checked"],
            "computed_in_domain": computed,
            "accepted_for_finalization": False,
        })
        if not fallback["domain_checked"]:
            problem = problem or "FALLBACK_DOMAIN_UNCHECKED"
        elif not computed or fallback["reported_in_domain"] is not True:
            problem = problem or "FALLBACK_OUT_OF_DOMAIN"
    return trace, problem


def _failure(
    request: Dict[str, Any],
    evidence: Dict[str, Any],
    decision: str,
    reason: str,
    records: List[Dict[str, Any]],
    fallback_trace: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    return _base_response(
        request, evidence, "UNKNOWN", decision, [reason],
        evidence["decision_time"], records, fallback_trace)


def _verify_temporal_order(
    request: Dict[str, Any],
    evidence: Dict[str, Any],
    policy: Dict[str, Any],
) -> Tuple[str | None, str | None]:
    timing = policy["time_policy"]
    try:
        request_time = _parse_time(request["timestamp"])
        decision_time = _parse_time(evidence["decision_time"])
        state_captured = _parse_time(
            request["state_estimate"]["captured_at"])
        resource_captured = _parse_time(
            request["resource_state"]["captured_at"])
        deadline = _parse_time(request["decision_deadline"])
    except (KeyError, TypeError, ValueError):
        return "ABORT", "TEMPORAL_ORDER_INVALID"

    skew = timedelta(seconds=float(timing["max_clock_skew_s"]))
    if (state_captured > request_time + skew
            or resource_captured > request_time + skew
            or request_time > decision_time + skew):
        return "ABORT", "TEMPORAL_ORDER_INVALID"

    max_capture_age = timedelta(
        seconds=float(timing["max_capture_age_s"]))
    if (request_time - state_captured > max_capture_age + skew
            or request_time - resource_captured > max_capture_age + skew):
        return "WAIT", "CAPTURE_DATA_TOO_OLD"

    max_decision_age = timedelta(
        seconds=float(timing["max_request_to_decision_s"]))
    if decision_time - request_time > max_decision_age + skew:
        return "WAIT", "REQUEST_TO_DECISION_AGE_EXCEEDED"

    max_deadline = timedelta(
        seconds=float(timing["max_deadline_horizon_s"]))
    if deadline < request_time - skew:
        return "ABORT", "TEMPORAL_ORDER_INVALID"
    if deadline - request_time > max_deadline + skew:
        return "ABORT", "DEADLINE_HORIZON_INVALID"

    validity = [
        ("DECISION_DEADLINE_EXPIRED", request["decision_deadline"], False),
        ("STATE_STALE", request["state_estimate"]["valid_until"], True),
        ("MODEL_EVIDENCE_STALE", request["model_validity"]["valid_until"], True),
        ("RESOURCE_STATE_STALE", request["resource_state"]["valid_until"], True),
    ]
    validity.extend(
        ("EVIDENCE_STALE", record["valid_until"], True)
        for record in evidence["artifact_records"])
    max_validity = timedelta(
        seconds=float(timing["max_validity_horizon_s"]))
    try:
        for reason, valid_until_text, horizon_limited in validity:
            valid_until = _parse_time(valid_until_text)
            if (horizon_limited
                    and valid_until - request_time > max_validity + skew):
                return "ABORT", "VALIDITY_HORIZON_INVALID"
            if decision_time > valid_until + skew:
                return "WAIT", reason
    except (TypeError, ValueError):
        return "ABORT", "TEMPORAL_ORDER_INVALID"
    return None, None


def _decide_verified(
    request: Dict[str, Any],
    evidence: Dict[str, Any],
    policy: Dict[str, Any],
    records: List[Dict[str, Any]],
    authorization_key: bytes | None,
    authorization_key_id: str | None,
) -> Dict[str, Any]:
    if evidence["source_channel"] not in policy["trusted_state_channels"]:
        return _failure(request, evidence, "ABORT", "SOURCE_CHANNEL_UNTRUSTED", records)

    state = request["state_estimate"]
    validity = request["model_validity"]
    if (validity["selection_mode"] == "GRID_CELL"
            and Decimal(str(state["lambda_actual"]))
            != Decimal(str(state["lambda_grid"]))):
        return _failure(request, evidence, "BACKOFF",
                        "LAMBDA_GRID_SMUGGLING", records)

    level = request["model_level"]
    computed_domain = _in_domain(request, level, policy)
    if not computed_domain or validity["reported_in_domain"] is not True:
        return _failure(request, evidence, "BACKOFF", "OUT_OF_DOMAIN", records)

    if level == "L2":
        trace, fallback_problem = _fallback_trace(request, policy)
        if fallback_problem:
            return _failure(request, evidence, "BACKOFF", fallback_problem,
                            records, trace)
        return _failure(request, evidence, "WAIT",
                        "L2_FAILED_NO_OPTIMISTIC_FALLBACK", records, trace)

    expected_certification = policy["certification"][level]
    if validity["certification"] != expected_certification:
        return _failure(request, evidence, "WAIT",
                        "MODEL_CERTIFICATION_MISMATCH", records)
    if validity["reported_status"] != "PASS":
        return _failure(request, evidence, "WAIT",
                        "INDEPENDENT_EVIDENCE_UNKNOWN", records)
    if request["state_covariance"]["assessment"] != "PASS":
        return _failure(request, evidence, "BACKOFF",
                        "STATE_COVARIANCE_NOT_PASS", records)
    if request["resource_state"]["status"] == "UNKNOWN":
        return _failure(request, evidence, "WAIT",
                        "RESOURCE_STATE_UNKNOWN", records)
    if request["resource_state"]["status"] == "EXCEEDED":
        action = "BACKOFF" if request["resource_state"]["backoff_available"] else "ABORT"
        return _base_response(request, evidence, "UNSAFE", action,
                              ["RESOURCE_CONSTRAINT_UNSAFE"],
                              evidence["decision_time"], records)
    if evidence["physical_state"] == "UNKNOWN":
        return _failure(request, evidence, "WAIT",
                        "INDEPENDENT_EVIDENCE_UNKNOWN", records)
    if evidence["physical_state"] == "UNSAFE":
        action = "BACKOFF" if request["resource_state"]["backoff_available"] else "ABORT"
        return _base_response(request, evidence, "UNSAFE", action,
                              ["PHYSICAL_CONSTRAINT_UNSAFE"],
                              evidence["decision_time"], records)

    requested_mod = request["proposed_action"]["requested_modification"]
    required_mod = evidence["required_modification"]
    if requested_mod != required_mod:
        return _failure(request, evidence, "ABORT",
                        "MODIFICATION_BOUNDARY_UNVERIFIED", records)
    if (not isinstance(authorization_key, bytes)
            or len(authorization_key)
            < int(policy["authorization"]["minimum_key_bytes"])
            or not isinstance(authorization_key_id, str)
            or KEY_ID_PATTERN.fullmatch(authorization_key_id) is None):
        return _failure(request, evidence, "ABORT",
                        "AUTHORIZATION_KEY_UNAVAILABLE", records)

    valid_until = _min_time_text([
        request["decision_deadline"],
        request["state_estimate"]["valid_until"],
        request["model_validity"]["valid_until"],
        request["resource_state"]["valid_until"],
        *(record["valid_until"] for record in evidence["artifact_records"]),
    ])
    source_reasons = sorted(evidence["reason_codes"])
    if required_mod is not None:
        response = _base_response(
            request, evidence, "SAFE", "MODIFY",
            ["AUTHORIZED_WITH_MODIFICATION", *source_reasons],
            valid_until, records, modified_action=copy.deepcopy(required_mod),
            authorization_key=authorization_key,
            authorization_key_id=authorization_key_id,
            authorization_not_before=evidence["decision_time"])
    else:
        response = _base_response(
            request, evidence, "SAFE", "ALLOW",
            ["AUTHORIZED_SAFE", *source_reasons],
            valid_until, records,
            authorization_key=authorization_key,
            authorization_key_id=authorization_key_id,
            authorization_not_before=evidence["decision_time"])
    if not response["provenance"]["complete"]:
        return _failure(request, evidence, "ABORT",
                        "PROVENANCE_INCOMPLETE", records)
    return response


def decide(
    request: Dict[str, Any],
    evidence: Dict[str, Any],
    *,
    repo_root: Path = REPO,
    policy_path: Path = POLICY_PATH,
    authorization_key: bytes | None = None,
    authorization_key_id: str | None = None,
) -> Dict[str, Any]:
    """Validate, re-hash frozen evidence, then invoke the pure decision kernel."""
    request_errors = _validation_errors(request, REQUEST_SCHEMA_PATH)
    if request_errors:
        return _invalid_response(request, evidence, "REQUEST_SCHEMA_INVALID")
    evidence_errors = _validation_errors(evidence, EVIDENCE_SCHEMA_PATH)
    if evidence_errors:
        return _invalid_response(request, evidence, "EVIDENCE_SCHEMA_INVALID")
    policy = load_policy(policy_path)

    expected_scenario = compute_scenario_hash(request, evidence)
    if (request["scenario_hash"] != expected_scenario
            or evidence["scenario_hash"] != expected_scenario):
        return _invalid_response(request, evidence, "SCENARIO_HASH_MISMATCH")

    temporal_decision, temporal_reason = _verify_temporal_order(
        request, evidence, policy)
    if temporal_reason:
        return _invalid_response(
            request, evidence, temporal_reason, temporal_decision or "ABORT")

    artifact_error, records = _verify_artifacts(
        request, evidence, policy, repo_root)
    if artifact_error:
        return _invalid_response(request, evidence, artifact_error)
    return _decide_verified(
        request, evidence, policy, records,
        authorization_key, authorization_key_id)


def response_sha256(response: Dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(response))
