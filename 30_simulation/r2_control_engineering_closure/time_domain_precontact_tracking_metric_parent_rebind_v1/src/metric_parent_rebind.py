"""Append-only rebind of one drifted task-metric parent HOLD artifact.

The historical task-metric contract and all parent artifacts remain immutable.
Only an in-memory copy of that contract is changed, and only the declared
bytes/SHA256 of the already named precontact parent Gate are replaced with the
current directly pinned bytes.  The task-metric candidate is then recomputed.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = PACKAGE_ROOT / "contracts" / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_CONTRACT_V1.json"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "2B38EB1690FEF56F09719A404FDC008211ED1926682270B08194DDA5AA85D4D8"


class RebindError(RuntimeError):
    pass


def _reject_constant(token: str) -> None:
    raise ValueError(f"NONFINITE_JSON_CONSTANT_REJECTED:{token}")


def _unique_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY_REJECTED:{key}")
        result[key] = value
    return result


def loads_json_strict(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)


def load_json_strict(path: Path) -> Any:
    try:
        return loads_json_strict(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise RebindError(f"JSON_UTF8_REQUIRED:{path}") from exc


def _require(condition: bool, code: str) -> None:
    if not bool(condition):
        raise RebindError(code)


def to_builtin(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            return [to_builtin(item) for item in value.tolist()]
        if isinstance(value, np.generic):
            return to_builtin(value.item())
    except ImportError:
        pass
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RebindError("NONFINITE_OUTPUT_REJECTED")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"UNSUPPORTED_TYPE:{type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(to_builtin(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def file_record(path: Path, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(project_root.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest().upper(),
    }


def validate_contract(contract: Mapping[str, Any], *, check_canonical: bool = True) -> dict[str, Any]:
    _require(contract.get("schema") == "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_CONTRACT_V1", "CONTRACT_SCHEMA_MISMATCH")
    _require(contract.get("scope") == "APPEND_ONLY_SINGLE_TRANSITIVE_PARENT_HOLD_BYTE_REBIND_ONLY", "CONTRACT_SCOPE_MISMATCH")
    failure = contract.get("original_failure", {})
    _require(failure == {
        "candidate_gate_passed": False,
        "passed": 19,
        "total": 20,
        "failed_check": "G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT",
    }, "ORIGINAL_FAILURE_CONTRACT_MISMATCH")
    rebind = contract.get("single_rebind", {})
    _require(rebind.get("pin_id") == "precontact_tracking_parent_gate", "REBIND_PIN_ID_MISMATCH")
    _require(rebind.get("path") == "30_simulation/r2_control_engineering_closure/results/CTRL_R2_PRECONTACT_TRACKING_GATE_V1.json", "REBIND_PATH_MISMATCH")
    _require(rebind.get("declared_old_bytes") == 12960 and rebind.get("declared_old_sha256") == "0366500C2E639F1FBD673756E092DD0D90E5E68BADE57B6A1B81EFC5B6E8DBA0", "OLD_BINDING_MISMATCH")
    _require(rebind.get("current_bytes") == 12958 and rebind.get("current_sha256") == "79E53F74029598F166C2879E7E0B843B53AAFB1A47F41FDE785290BAA52D70A2", "CURRENT_BINDING_MISMATCH")
    _require(rebind.get("historical_file_mutation_allowed") is False, "HISTORICAL_MUTATION_ESCALATION")
    comparison = contract.get("recompute_comparison", {})
    _require(float(comparison.get("numeric_max_abs_tolerance", 0.0)) == 1e-15, "RECOMPUTE_TOLERANCE_MISMATCH")
    _require(comparison.get("non_numeric_and_structure_exact_required") is True, "RECOMPUTE_STRUCTURE_POLICY_MISMATCH")
    pins = contract.get("source_pins", [])
    _require(len(pins) == 12 and len({row.get("id") for row in pins}) == 12, "SOURCE_PIN_SET_MISMATCH")
    for pin in pins:
        _require(isinstance(pin.get("bytes"), int) and pin["bytes"] > 0, "SOURCE_PIN_BYTES_INVALID")
        sha = pin.get("sha256")
        _require(isinstance(sha, str) and len(sha) == 64 and sha == sha.upper(), "SOURCE_PIN_SHA_INVALID")
    _require(all(value is False for value in contract.get("authority_boundaries", {}).values()), "AUTHORITY_BOUNDARY_ESCALATED")
    _require(contract.get("review_status") == "PENDING_OWNER_REVIEW", "REVIEW_STATUS_MISMATCH")
    _require(contract.get("next_stage_authorized") is False and contract.get("release_credit") is False, "RELEASE_BOUNDARY_ESCALATED")
    if check_canonical and EXPECTED_CONTRACT_CANONICAL_SHA256 != "TO_BE_BOUND":
        _require(canonical_sha256(contract) == EXPECTED_CONTRACT_CANONICAL_SHA256, "CONTRACT_CANONICAL_SHA256_DRIFT")
    return {"valid": True, "source_pin_count": len(pins)}


def load_contract() -> dict[str, Any]:
    contract = load_json_strict(CONTRACT_PATH)
    validate_contract(contract)
    return contract


def _pin(contract: Mapping[str, Any], identifier: str, project_root: Path = PROJECT_ROOT) -> Path:
    rows = [row for row in contract["source_pins"] if row["id"] == identifier]
    _require(len(rows) == 1, f"SOURCE_PIN_NOT_UNIQUE:{identifier}")
    return (project_root / rows[0]["path"]).resolve()


def validate_source_pins(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    records = []
    for pin in contract["source_pins"]:
        path = (project_root / pin["path"]).resolve()
        _require(path.is_file(), f"SOURCE_PIN_MISSING:{pin['id']}")
        actual = file_record(path, project_root)
        match = actual["bytes"] == pin["bytes"] and actual["sha256"] == pin["sha256"]
        records.append({"id": pin["id"], **actual, "match": match})
        _require(match, f"SOURCE_PIN_DRIFT:{pin['id']}")
    return {"all_match": True, "matched": len(records), "total": len(records), "records": records}


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RebindError(f"MODULE_IMPORT_FAILED:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def audit_manifest_records(manifest: Mapping[str, Any], field: str, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    records = []
    for declared in manifest[field]:
        path = (project_root / declared["path"]).resolve()
        _require(path.is_file(), f"MANIFEST_FILE_MISSING:{declared['path']}")
        actual = file_record(path, project_root)
        match = actual["bytes"] == declared["bytes"] and actual["sha256"] == declared["sha256"]
        records.append({**actual, "match": match})
    return {"all_match": all(row["match"] for row in records), "matched": sum(row["match"] for row in records), "total": len(records), "records": records}


def original_metric_binding_audit(metric_contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    records = []
    for pin in metric_contract["source_pins"]:
        path = (project_root / pin["path"]).resolve()
        actual = file_record(path, project_root)
        match = actual["bytes"] == pin["bytes"] and actual["sha256"] == pin["sha256"]
        records.append({"id": pin["id"], "declared_bytes": pin["bytes"], "declared_sha256": pin["sha256"], "actual_bytes": actual["bytes"], "actual_sha256": actual["sha256"], "match": match})
    mismatches = [row for row in records if not row["match"]]
    exact_single = len(mismatches) == 1 and mismatches[0]["id"] == "precontact_tracking_parent_gate"
    return {"records": records, "mismatches": mismatches, "exact_single_parent_hold_mismatch": exact_single}


def parent_hold_semantics(parent_gate: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    required = contract["required_current_parent_hold_semantics"]
    checks = {
        "schema": parent_gate.get("schema") == required["schema"],
        "source_binding_pass": parent_gate.get("source_binding_pass") is required["source_binding_pass"],
        "candidate_packaging_pass": parent_gate.get("candidate_packaging_pass") is required["candidate_packaging_pass"],
        "time_domain_tracking_executed": parent_gate.get("first", {}).get("time_domain_tracking_executed") is required["time_domain_tracking_executed"],
        "precontact_tracking_validated": parent_gate.get("precontact_tracking_validated") is required["precontact_tracking_validated"],
        "next_stage_authorized": parent_gate.get("next_stage_authorized") is required["next_stage_authorized"],
        "release_credit": parent_gate.get("release_credit") is required["release_credit"],
        "verdict_hold": str(parent_gate.get("verdict", "")).startswith(required["verdict_prefix"]),
    }
    return {"checks": checks, "all_match": all(checks.values())}


def make_rebound_metric_contract(metric_contract: Mapping[str, Any], contract: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rebound = copy.deepcopy(dict(metric_contract))
    target = [row for row in rebound["source_pins"] if row["id"] == contract["single_rebind"]["pin_id"]]
    _require(len(target) == 1, "REBIND_TARGET_NOT_UNIQUE")
    before = copy.deepcopy(target[0])
    target[0]["bytes"] = contract["single_rebind"]["current_bytes"]
    target[0]["sha256"] = contract["single_rebind"]["current_sha256"]
    restored = copy.deepcopy(rebound)
    restored_target = next(row for row in restored["source_pins"] if row["id"] == contract["single_rebind"]["pin_id"])
    restored_target["bytes"] = before["bytes"]
    restored_target["sha256"] = before["sha256"]
    only_allowed = restored == metric_contract and target[0]["path"] == before["path"] and target[0]["id"] == before["id"]
    return rebound, {"only_bytes_and_sha_changed_for_named_pin": only_allowed, "before": before, "after": target[0]}


def compare_numeric_structure(left: Any, right: Any, path: str = "") -> dict[str, Any]:
    numeric_differences: list[dict[str, Any]] = []
    non_numeric_differences: list[dict[str, Any]] = []

    def walk(a: Any, b: Any, here: str) -> None:
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            if set(a.keys()) != set(b.keys()):
                non_numeric_differences.append({"path": here, "left_keys": sorted(a.keys()), "right_keys": sorted(b.keys())})
                return
            for key in sorted(a.keys()):
                walk(a[key], b[key], f"{here}/{key}")
            return
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                non_numeric_differences.append({"path": here, "left_length": len(a), "right_length": len(b)})
                return
            for index, (item_a, item_b) in enumerate(zip(a, b)):
                walk(item_a, item_b, f"{here}/{index}")
            return
        numeric_a = isinstance(a, (int, float)) and not isinstance(a, bool)
        numeric_b = isinstance(b, (int, float)) and not isinstance(b, bool)
        if numeric_a and numeric_b:
            difference = abs(float(a) - float(b))
            if difference != 0.0:
                numeric_differences.append({"path": here, "absolute_difference": difference, "left": a, "right": b})
            return
        if a != b:
            non_numeric_differences.append({"path": here, "left": a, "right": b})

    walk(left, right, path)
    return {
        "numeric_difference_count": len(numeric_differences),
        "numeric_max_abs": max((row["absolute_difference"] for row in numeric_differences), default=0.0),
        "numeric_differences": numeric_differences,
        "non_numeric_difference_count": len(non_numeric_differences),
        "non_numeric_differences": non_numeric_differences,
        "structure_and_non_numeric_exact": len(non_numeric_differences) == 0,
    }


def run_negative_controls(contract: Mapping[str, Any], metric_contract: Mapping[str, Any]) -> dict[str, Any]:
    records = []

    def expect(identifier: str, fn: Any, token: str) -> None:
        message = "NO_EXCEPTION"
        passed = False
        try:
            fn()
        except Exception as exc:
            message = str(exc)
            passed = token in message
        records.append({"id": identifier, "expected_token": token, "observed": message, "pass": passed})

    expect("NC01_DUPLICATE_JSON", lambda: loads_json_strict('{"x":1,"x":2}'), "DUPLICATE_JSON_KEY_REJECTED")
    expect("NC02_NONFINITE_JSON", lambda: loads_json_strict('{"x":NaN}'), "NONFINITE_JSON_CONSTANT_REJECTED")
    mutated = copy.deepcopy(contract); mutated["authority_boundaries"]["control_valid"] = True
    expect("NC03_AUTHORITY_ESCALATION", lambda: validate_contract(mutated, check_canonical=False), "AUTHORITY_BOUNDARY_ESCALATED")
    mutated = copy.deepcopy(contract); mutated["single_rebind"]["pin_id"] = "task_metric_gate"
    expect("NC04_WRONG_REBIND_ID", lambda: validate_contract(mutated, check_canonical=False), "REBIND_PIN_ID_MISMATCH")
    mutated = copy.deepcopy(contract); mutated["single_rebind"]["path"] = "wrong.json"
    expect("NC05_WRONG_REBIND_PATH", lambda: validate_contract(mutated, check_canonical=False), "REBIND_PATH_MISMATCH")
    mutated = copy.deepcopy(contract); mutated["source_pins"][0]["sha256"] = "0" * 64
    expect("NC06_SOURCE_DRIFT", lambda: validate_source_pins(mutated), "SOURCE_PIN_DRIFT")
    rebound, _ = make_rebound_metric_contract(metric_contract, contract)
    rebound["source_pins"][0]["sha256"] = "0" * 64
    expect("NC07_SECOND_METRIC_DRIFT", lambda: _require(original_metric_binding_audit(rebound)["exact_single_parent_hold_mismatch"], "MORE_THAN_SINGLE_METRIC_MISMATCH"), "MORE_THAN_SINGLE_METRIC_MISMATCH")
    mutated = copy.deepcopy(contract); mutated["original_failure"]["passed"] = 20
    expect("NC08_ORIGINAL_FAILURE_REWRITE", lambda: validate_contract(mutated, check_canonical=False), "ORIGINAL_FAILURE_CONTRACT_MISMATCH")
    mutated = copy.deepcopy(contract); mutated["single_rebind"]["historical_file_mutation_allowed"] = True
    expect("NC09_HISTORICAL_MUTATION", lambda: validate_contract(mutated, check_canonical=False), "HISTORICAL_MUTATION_ESCALATION")
    mutated = copy.deepcopy(contract); mutated["single_rebind"]["current_bytes"] = 12959
    expect("NC10_CURRENT_BINDING_MUTATION", lambda: validate_contract(mutated, check_canonical=False), "CURRENT_BINDING_MISMATCH")
    return {"records": records, "count": len(records), "passed": sum(row["pass"] for row in records), "all_pass": all(row["pass"] for row in records)}


def build_rebind(project_root: Path = PROJECT_ROOT) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = load_contract()
    direct = validate_source_pins(contract, project_root)
    task_manifest = load_json_strict(_pin(contract, "task_metric_manifest", project_root))
    time_manifest = load_json_strict(_pin(contract, "time_domain_manifest", project_root))
    task_local_manifest = audit_manifest_records(task_manifest, "local_records", project_root)
    task_parent_transitive = audit_manifest_records(task_manifest, "parent_transitive_source_pins", project_root)
    time_manifest_audit = audit_manifest_records(time_manifest, "inventory", project_root)
    metric_contract = load_json_strict(_pin(contract, "task_metric_contract", project_root))
    metric = _load_module("_td_metric_parent_rebind_source", _pin(contract, "task_metric_source", project_root))
    metric.validate_contract(metric_contract)
    original_binding = original_metric_binding_audit(metric_contract, project_root)
    parent_gate = load_json_strict(_pin(contract, "current_precontact_parent_gate", project_root))
    hold = parent_hold_semantics(parent_gate, contract)
    rebound_contract, mutation = make_rebound_metric_contract(metric_contract, contract)
    metric.validate_contract(rebound_contract)
    rebound_binding = metric.validate_source_pins(rebound_contract, project_root)
    rebound_evidence, rebound_gate = metric.evaluate_candidate(rebound_contract, project_root)
    archived_metric_evidence = load_json_strict(_pin(contract, "task_metric_evidence", project_root))
    archived_metric_gate = load_json_strict(_pin(contract, "task_metric_gate", project_root))
    time_gate = load_json_strict(_pin(contract, "time_domain_gate", project_root))
    time_evidence = load_json_strict(_pin(contract, "time_domain_evidence", project_root))
    time_negative = load_json_strict(_pin(contract, "time_domain_negative_controls", project_root))
    original_time_failure_exact = (
        time_gate.get("gate_passed") is False
        and time_gate.get("summary") == {"passed": 19, "total": 20, "failed": ["G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT"]}
        and sum(bool(value) for key, value in time_gate["checks"].items() if key != "G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT") == 19
    )
    task_recompute_comparison = compare_numeric_structure(rebound_evidence["tasks"], archived_metric_evidence["tasks"], "tasks")
    metric_numeric_equal = (
        task_recompute_comparison["structure_and_non_numeric_exact"]
        and task_recompute_comparison["numeric_max_abs"] <= float(contract["recompute_comparison"]["numeric_max_abs_tolerance"])
        and canonical_sha256(rebound_evidence["chain_derivation"]) == canonical_sha256(archived_metric_evidence["chain_derivation"])
        and canonical_sha256(rebound_evidence["reference_scale_derivation"]) == canonical_sha256(archived_metric_evidence["reference_scale_derivation"])
        and rebound_gate["checks"] == archived_metric_gate["checks"]
    )
    negative = run_negative_controls(contract, metric_contract)
    authority = copy.deepcopy(contract["authority_boundaries"])
    checks = {
        "R01_CONTRACT_AND_TWELVE_DIRECT_PINS_EXACT": validate_contract(contract)["valid"] and direct["matched"] == 12,
        "R02_TIME_DOMAIN_CANDIDATE_MANIFEST_CURRENT": time_manifest_audit["all_match"] and time_manifest_audit["total"] == 9,
        "R03_TASK_METRIC_LOCAL_MANIFEST_CURRENT": task_local_manifest["all_match"] and task_local_manifest["total"] == 9,
        "R04_TASK_METRIC_PARENT_TRANSITIVE_24_CURRENT": task_parent_transitive["all_match"] and task_parent_transitive["total"] == 24,
        "R05_ORIGINAL_METRIC_BINDING_HAS_EXACTLY_ONE_PARENT_HOLD_MISMATCH": original_binding["exact_single_parent_hold_mismatch"],
        "R06_CURRENT_PARENT_GATE_DIRECTLY_PINNED_AND_STILL_HOLD": hold["all_match"],
        "R07_IN_MEMORY_MUTATION_ONLY_BYTES_AND_SHA_OF_NAMED_PIN": mutation["only_bytes_and_sha_changed_for_named_pin"],
        "R08_REBOUND_METRIC_SOURCE_BINDING_SEVEN_OF_SEVEN": rebound_binding["all_match"] and rebound_binding["matched"] == 7,
        "R09_REBOUND_TASK_METRIC_RECOMPUTE_17_OF_17": rebound_gate["all_checks_pass"] and rebound_gate["passed"] == rebound_gate["total"] == 17,
        "R10_REBOUND_METRIC_NUMERICS_AND_CHECKS_EQUAL_ARCHIVED_CANDIDATE": metric_numeric_equal,
        "R11_ORIGINAL_TIME_DOMAIN_GATE_RETAINS_19_OF_20_SINGLE_G04_FAILURE": original_time_failure_exact,
        "R12_TIME_DOMAIN_FOUR_RUNS_AND_SCIENTIFIC_CHECKS_PRESERVED": len(time_evidence["scenarios"]) == 4 and all(value for key, value in time_gate["checks"].items() if key != "G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT"),
        "R13_TIME_DOMAIN_NEGATIVE_CONTROLS_TWENTY_OF_TWENTY": time_negative["all_pass"] and time_negative["passed"] == time_negative["count"] == 20,
        "R14_REBIND_NEGATIVE_CONTROLS_ALL_PASS": negative["all_pass"] and negative["passed"] == negative["count"] >= 10,
        "R15_ORIGINAL_FILES_NOT_REISSUED_OR_MUTATED": direct["all_match"],
        "R16_ALL_DOWNSTREAM_AUTHORITY_BOUNDARIES_FALSE": all(value is False for value in authority.values()),
    }
    passed = sum(bool(value) for value in checks.values())
    gate_passed = passed == len(checks)
    evidence = {
        "schema": "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_EVIDENCE_V1",
        "scope": contract["scope"],
        "direct_source_binding": direct,
        "task_metric_local_manifest_audit": task_local_manifest,
        "task_metric_parent_transitive_audit": task_parent_transitive,
        "time_domain_manifest_audit": time_manifest_audit,
        "original_metric_binding_audit": original_binding,
        "current_parent_hold_audit": hold,
        "in_memory_mutation_audit": mutation,
        "task_metric_recompute_comparison": task_recompute_comparison,
        "rebound_metric_source_binding": rebound_binding,
        "rebound_metric_gate": rebound_gate,
        "rebound_metric_evidence": rebound_evidence,
        "original_time_domain_gate_summary": time_gate["summary"],
        "time_domain_same_dimension_comparisons": time_evidence["same_dimension_comparisons"],
        "authority_boundaries": authority,
    }
    gate = {
        "schema": "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_GATE_V1",
        "technical_verdict": "TIME_DOMAIN_DIAGNOSTIC_TRANSITIVE_PARENT_HOLD_REBIND_PASS__ORIGINAL_19_OF_20_GATE_RETAINED__NO_CONTROL_RELEASE" if gate_passed else "TIME_DOMAIN_DIAGNOSTIC_TRANSITIVE_PARENT_HOLD_REBIND_REPEAT_REQUIRED__NO_CONTROL_RELEASE",
        "maximum_claim": "TIME_DOMAIN_DIAGNOSTIC_TRANSITIVE_PARENT_HOLD_REBIND_PASS" if gate_passed else "TRANSITIVE_PARENT_HOLD_REBIND_ATTEMPTED_REPEAT_REQUIRED",
        "checks": checks,
        "summary": {"passed": passed, "total": len(checks), "failed": [key for key, value in checks.items() if not value]},
        "gate_passed": gate_passed,
        "original_time_domain_gate_passed": False,
        "original_time_domain_gate_reissued": False,
        "authority_boundaries": authority,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    return to_builtin(evidence), to_builtin(gate), to_builtin(negative)
