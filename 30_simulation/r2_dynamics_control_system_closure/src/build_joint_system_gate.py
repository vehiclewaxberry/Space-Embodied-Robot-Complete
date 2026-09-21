"""Build a fail-closed joint mechanical/dynamics/control system gate."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = PACKAGE / "contracts" / "R2_DYNAMICS_CONTROL_SYSTEM_CONTRACT_V1.json"
RESULTS = PACKAGE / "results"
AUDIT_PATH = RESULTS / "R2_DYNAMICS_CONTROL_INDEPENDENT_REVIEW_V1.json"
MECHANICAL_CLOSURE_PACKAGE = (
    ROOT
    / "20_engineering"
    / "MECHANICAL_ENGINEERING_RELEASE_R2"
    / "_work"
    / "odr"
    / "ODR60_OPTION_A_EXECUTION_CLOSURE_V1"
)
CONTROL_CLOSURE_PACKAGE = ROOT / "30_simulation" / "r2_control_engineering_closure"
EXPECTED_REVIEWED_ARTIFACTS = {
    "joint_contract": "30_simulation/r2_dynamics_control_system_closure/contracts/R2_DYNAMICS_CONTROL_SYSTEM_CONTRACT_V1.json",
    "joint_builder": "30_simulation/r2_dynamics_control_system_closure/src/build_joint_system_gate.py",
    "joint_tests": "30_simulation/r2_dynamics_control_system_closure/tests/test_joint_system_gate.py",
}


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def loads_json_strict(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_unique_pairs)


def load_json_strict(path: Path) -> Any:
    return loads_json_strict(path.read_text(encoding="utf-8"))


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.Node,
    deep: bool = False,
) -> dict:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"DUPLICATE_YAML_KEY:{key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_yaml_strict(path: Path) -> Any:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)


def load_csv_strict(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        if not fields:
            raise ValueError(f"CSV_HEADER_MISSING:{path.as_posix()}")
        if len(fields) != len(set(fields)):
            raise ValueError(f"DUPLICATE_CSV_HEADER:{path.as_posix()}")
        rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError(f"CSV_ROW_HAS_EXTRA_COLUMNS:{path.as_posix()}")
    return rows


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _resolve_path(raw_path: str, base: Path = ROOT) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else base / path


def bind_sources(contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = []
    documents: dict[str, Any] = {}
    seen_ids: set[str] = set()
    for pin in contract["source_pins"]:
        source_id = pin["id"]
        if source_id in seen_ids:
            raise ValueError(f"DUPLICATE_SOURCE_PIN_ID:{source_id}")
        seen_ids.add(source_id)
        path = ROOT / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_hash = sha256_file(path) if exists else None
        match = bool(
            exists
            and actual_bytes == pin["bytes"]
            and actual_hash == pin["sha256"]
        )
        rows.append(
            {
                "id": source_id,
                "path": pin["path"],
                "expected_bytes": pin["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": pin["sha256"],
                "actual_sha256": actual_hash,
                "match": match,
            }
        )
        if match:
            suffix = path.suffix.lower()
            if suffix in {".yaml", ".yml"}:
                documents[source_id] = load_yaml_strict(path)
            elif suffix == ".csv":
                documents[source_id] = load_csv_strict(path)
            else:
                documents[source_id] = load_json_strict(path)
    binding = {
        "schema": "R2_DYNAMICS_CONTROL_SOURCE_BINDING_V1",
        "pins": rows,
        "summary": {
            "matched": sum(row["match"] for row in rows),
            "total": len(rows),
        },
        "all_match": all(row["match"] for row in rows),
        "next_stage_authorized": False,
        "release_credit": False,
    }
    return binding, documents


def _validate_csv_hash_manifest(
    rows: list[dict[str, str]],
    *,
    base: Path,
    id_field: str | None = None,
    require_declared_match: bool = False,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_ids: set[str] = set()
    for row in rows:
        raw_path = row.get("path", "")
        duplicate_path = raw_path in seen_paths
        seen_paths.add(raw_path)
        duplicate_id = False
        if id_field is not None:
            raw_id = row.get(id_field, "")
            duplicate_id = raw_id in seen_ids
            seen_ids.add(raw_id)
        path = _resolve_path(raw_path, base)
        exists = bool(raw_path) and path.is_file()
        try:
            expected_bytes = int(row["bytes"])
        except (KeyError, TypeError, ValueError):
            expected_bytes = None
        expected_hash = row.get("sha256")
        actual_bytes = path.stat().st_size if exists else None
        actual_hash = sha256_file(path) if exists else None
        declared_match = row.get("match", "").lower() == "true"
        row_pass = bool(
            exists
            and not duplicate_path
            and not duplicate_id
            and expected_bytes == actual_bytes
            and expected_hash == actual_hash
            and (declared_match if require_declared_match else True)
        )
        checks.append(
            {
                "path": raw_path,
                "exists": exists,
                "bytes_match": expected_bytes == actual_bytes,
                "sha256_match": expected_hash == actual_hash,
                "duplicate_path": duplicate_path,
                "duplicate_id": duplicate_id,
                "declared_match_true": declared_match
                if require_declared_match
                else None,
                "pass": row_pass,
            }
        )
    return {
        "row_count": len(rows),
        "matched_count": sum(check["pass"] for check in checks),
        "pass": bool(rows) and all(check["pass"] for check in checks),
        "checks": checks,
    }


def _validate_source_binding(document: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    pins = document.get("pins", [])
    for pin in pins:
        source_id = pin.get("id", "")
        duplicate_id = source_id in seen_ids
        seen_ids.add(source_id)
        path = _resolve_path(pin.get("path", ""))
        exists = path.is_file()
        expected_bytes = pin.get("expected_bytes", pin.get("declared_bytes"))
        expected_hash = pin.get("expected_sha256", pin.get("declared_sha256"))
        actual_bytes = path.stat().st_size if exists else None
        actual_hash = sha256_file(path) if exists else None
        row_pass = bool(
            source_id
            and not duplicate_id
            and exists
            and pin.get("match") is True
            and pin.get("actual_bytes") == actual_bytes == expected_bytes
            and pin.get("actual_sha256") == actual_hash == expected_hash
        )
        checks.append(
            {
                "id": source_id,
                "path": pin.get("path"),
                "duplicate_id": duplicate_id,
                "pass": row_pass,
            }
        )
    if "all_match" in document:
        summary = document.get("summary", {})
        envelope_pass = bool(
            document.get("all_match") is True
            and summary.get("matched") == len(pins)
            and summary.get("total") == len(pins)
        )
    else:
        envelope_pass = bool(
            document.get("pass") is True
            and document.get("match_count") == len(pins)
            and document.get("pin_count") == len(pins)
            and document.get("mismatch_count") == 0
            and document.get("mismatches") == []
        )
    return {
        "row_count": len(pins),
        "matched_count": sum(check["pass"] for check in checks),
        "envelope_pass": envelope_pass,
        "pass": bool(pins) and envelope_pass and all(check["pass"] for check in checks),
        "checks": checks,
    }


def _validate_json_package_manifest(document: dict[str, Any]) -> dict[str, Any]:
    rows = document.get("artifacts", [])
    checks: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for row in rows:
        raw_path = row.get("path", "")
        duplicate_path = raw_path in seen_paths
        seen_paths.add(raw_path)
        path = _resolve_path(raw_path)
        exists = path.is_file()
        row_pass = bool(
            raw_path
            and not duplicate_path
            and exists
            and row.get("bytes") == path.stat().st_size
            and row.get("sha256") == sha256_file(path)
        )
        checks.append({"path": raw_path, "duplicate_path": duplicate_path, "pass": row_pass})
    envelope_pass = bool(
        document.get("summary", {}).get("count") == len(rows)
        and document.get("summary", {}).get("all_exist") is True
        and document.get("artifact_package_complete") is True
    )
    return {
        "row_count": len(rows),
        "matched_count": sum(check["pass"] for check in checks),
        "envelope_pass": envelope_pass,
        "pass": bool(rows) and envelope_pass and all(check["pass"] for check in checks),
        "checks": checks,
    }


def validate_upstream_manifests(docs: dict[str, Any]) -> dict[str, Any]:
    components = {
        "mechanical_closure_package_manifest": _validate_csv_hash_manifest(
            docs["odr60_execution_closure_package_manifest"],
            base=MECHANICAL_CLOSURE_PACKAGE,
        ),
        "mechanical_source_hash_manifest": _validate_csv_hash_manifest(
            docs["odr60_source_hash_manifest"],
            base=ROOT,
            id_field="source_id",
            require_declared_match=True,
        ),
        "dynamics_source_binding": _validate_source_binding(
            docs["r2_dynamics_source_binding"]
        ),
        "dynamics_package_manifest": _validate_json_package_manifest(
            docs["r2_dynamics_package_manifest"]
        ),
        "dynamics_sha256_manifest": _validate_csv_hash_manifest(
            docs["r2_dynamics_sha256_manifest"],
            base=ROOT,
        ),
        "control_source_binding": _validate_source_binding(
            docs["r2_control_source_binding"]
        ),
        "control_sha256_manifest": _validate_csv_hash_manifest(
            docs["r2_control_sha256_manifest"],
            base=CONTROL_CLOSURE_PACKAGE,
        ),
    }
    return {
        "components": {
            name: {
                "row_count": result["row_count"],
                "matched_count": result["matched_count"],
                "pass": result["pass"],
            }
            for name, result in components.items()
        },
        "pass": all(result["pass"] for result in components.values()),
    }


def validate_red_team_audit_document(document: dict[str, Any]) -> dict[str, Any]:
    rows = document.get("reviewed_artifacts", [])
    checks = []
    seen_ids: set[str] = set()
    rows_are_list = type(rows) is list
    for row in rows if rows_are_list else []:
        if type(row) is not dict:
            checks.append({"id": None, "pass": False})
            continue
        artifact_id_raw = row.get("id", "")
        artifact_id = artifact_id_raw if isinstance(artifact_id_raw, str) else ""
        duplicate_id = artifact_id in seen_ids
        seen_ids.add(artifact_id)
        raw_path = row.get("path", "")
        path_object = Path(raw_path) if isinstance(raw_path, str) else Path()
        expected_path = EXPECTED_REVIEWED_ARTIFACTS.get(artifact_id)
        canonical_relative_path = bool(
            isinstance(raw_path, str)
            and raw_path == expected_path
            and not path_object.is_absolute()
            and ".." not in path_object.parts
        )
        path = ROOT / raw_path if canonical_relative_path else ROOT
        inside_root = bool(
            canonical_relative_path
            and path.resolve().is_relative_to(ROOT.resolve())
        )
        exists = inside_root and path.is_file()
        declared_bytes = row.get("bytes")
        declared_hash = row.get("sha256")
        bytes_are_strict_int = type(declared_bytes) is int and declared_bytes >= 0
        hash_has_exact_format = bool(
            isinstance(declared_hash, str)
            and re.fullmatch(r"[0-9A-F]{64}", declared_hash)
        )
        row_pass = bool(
            artifact_id
            and not duplicate_id
            and canonical_relative_path
            and inside_root
            and exists
            and bytes_are_strict_int
            and hash_has_exact_format
            and declared_bytes == path.stat().st_size
            and declared_hash == sha256_file(path)
        )
        checks.append(
            {
                "id": artifact_id,
                "path": raw_path,
                "expected_path": expected_path,
                "duplicate_id": duplicate_id,
                "canonical_relative_path": canonical_relative_path,
                "inside_root": inside_root,
                "bytes_are_strict_int": bytes_are_strict_int,
                "sha256_has_exact_format": hash_has_exact_format,
                "pass": row_pass,
            }
        )
    open_high = document.get("open_high_findings_count")
    reviewer = document.get("reviewer")
    evidence_valid = bool(
        document.get("schema") == "R2_DYNAMICS_CONTROL_INDEPENDENT_REVIEW_V1"
        and document.get("review_status") == "INDEPENDENT_REVIEW_COMPLETE"
        and isinstance(reviewer, str)
        and bool(reviewer.strip())
        and type(open_high) is int
        and open_high >= 0
        and rows_are_list
        and seen_ids == set(EXPECTED_REVIEWED_ARTIFACTS)
        and len(rows) == len(EXPECTED_REVIEWED_ARTIFACTS)
        and all(check["pass"] for check in checks)
    )
    high_zero = bool(
        evidence_valid
        and type(open_high) is int
        and open_high == 0
        and document.get("independent_red_team_high_findings_zero") is True
    )
    return {
        "evidence_valid": evidence_valid,
        "high_findings_zero": high_zero,
        "reviewer": reviewer,
        "open_high_findings_count": open_high,
        "reviewed_artifact_count": len(rows) if rows_are_list else 0,
        "reason": None if evidence_valid else "INDEPENDENT_REVIEW_EVIDENCE_INVALID",
    }


def validate_red_team_audit() -> dict[str, Any]:
    if not AUDIT_PATH.is_file():
        return {
            "evidence_valid": False,
            "high_findings_zero": False,
            "reason": "INDEPENDENT_REVIEW_MISSING",
        }
    result = validate_red_team_audit_document(load_json_strict(AUDIT_PATH))
    result.update(
        {
            "receipt_path": AUDIT_PATH.relative_to(ROOT).as_posix(),
            "receipt_bytes": AUDIT_PATH.stat().st_size,
            "receipt_sha256": sha256_file(AUDIT_PATH),
        }
    )
    return result


def _run_specific_low_memory_override(selection: dict[str, Any]) -> bool:
    low_memory = selection["low_memory"]
    return bool(
        low_memory.get("explicitly_not_authorized_now") is False
        and isinstance(low_memory.get("authorized_run_id"), str)
        and bool(low_memory.get("authorized_run_id"))
        and isinstance(low_memory.get("authorization_window_start_utc"), str)
        and bool(low_memory.get("authorization_window_start_utc"))
        and isinstance(low_memory.get("authorization_window_end_utc"), str)
        and bool(low_memory.get("authorization_window_end_utc"))
        and low_memory.get("risk_override_reusable") is False
        and low_memory.get("runtime_memory_admission_pass") is True
    )


def build_gate(
    contract: dict[str, Any],
    binding: dict[str, Any],
    docs: dict[str, Any],
    independent_review: dict[str, Any],
    package_preflight_pass: bool,
) -> dict[str, Any]:
    if not binding["all_match"]:
        raise RuntimeError("JOINT_SOURCE_BINDING_FAIL_CLOSED")
    upstream_integrity = validate_upstream_manifests(docs)
    selection = docs["odr60_owner_selection"]
    mechanical = docs["odr60_execution_closure_gate"]
    handoff = docs["mechanical_handoff_gate"]
    dynamics = docs["r2_dynamics_gate"]
    constrained = docs["r2_constrained_dynamics_gate"]
    control = docs["r2_control_gate"]
    precontact = docs["r2_control_precontact_gate"]
    safe = docs["safe00_gate"]
    sim13 = docs["sim13_20_of_20_gate"]
    interface = docs["mech_rl_system_interface"]

    owner_option_a = bool(
        selection["selection"].get("option_a_selected") is True
        and selection["selection"].get("exactly_one_branch_selected") is True
        and selection["machine_authority_evidence"].get("authorized") is True
        and selection["machine_authority_evidence"].get("authority_evidence_class")
        == "EXPLICIT_EXECUTION_PROMPT_BLOCK_FIRST_LINE"
    )
    low_memory_override = _run_specific_low_memory_override(selection)
    low_memory = selection["low_memory"]
    runtime_memory_admission = bool(
        mechanical["authority"].get("runtime_memory_admission_pass") is True
        and low_memory.get("runtime_memory_admission_pass") is True
        and (low_memory.get("memory_gate_passed") is True or low_memory_override)
    )
    task_checks = precontact["first"]["checks"]
    task_metric_bound = task_checks.get("task_space_unit_metric_bound") is True
    both_guards_allow = bool(
        task_checks.get("both_local_task_guards_allow") is True
        and precontact["first"].get("tasks")
        and all(task["guard"].get("allow") is True for task in precontact["first"]["tasks"])
    )
    interface_values = interface["authority"]["current_values"]
    conditions = {
        "source_binding_pass": binding["all_match"],
        "upstream_manifest_integrity_pass": upstream_integrity["pass"],
        "owner_option_a_selection_recorded": owner_option_a,
        "mechanical_static_preflight_pass": mechanical.get("static_preflight_pass") is True,
        "mechanical_handoff_pass": handoff.get("verdict")
        == "MECHANICAL_TO_EMBODIED_HANDOFF_PASS"
        and handoff.get("next_stage_authorized") is True,
        "runtime_memory_admission_pass": runtime_memory_admission,
        "dynamics_engineering_pass": dynamics.get("dynamics_engineering_complete") is True
        and constrained.get("candidate_package_complete") is True,
        "control_engineering_pass": control.get("control_engineering_complete") is True
        and control.get("candidate_package_complete") is True,
        "control_task_space_metric_and_guards_pass": bool(task_metric_bound and both_guards_allow),
        "safe_independent_review_pass": safe.get("verdict") == "PASS"
        and safe.get("review_status") in {"APPROVED", "INDEPENDENT_REVIEW_PASS"}
        and safe.get("next_stage_authorized") is True,
        "sim13_system_binding_pass": interface_values.get(
            "sim13_system_binding_gate_passed"
        )
        is True,
        "sim13_non_abort_operation_authorized": bool(
            interface_values.get("current_consumer_load_authorized") is True
            and interface_values.get("current_contact_grasp_authorized") is True
            and "ABORT_ONLY" not in str(sim13.get("maximum_operational_state", ""))
            and sim13.get("next_stage_authorized") is True
        ),
        "independent_red_team_high_findings_zero": independent_review[
            "high_findings_zero"
        ],
    }
    required_names = contract["required_ready_conditions"]
    if len(required_names) != len(set(required_names)):
        raise ValueError("DUPLICATE_REQUIRED_READY_CONDITION")
    missing_conditions = [name for name in required_names if name not in conditions]
    if missing_conditions:
        raise KeyError("UNIMPLEMENTED_REQUIRED_READY_CONDITION:" + ",".join(missing_conditions))
    joint_ready = all(conditions[name] is True for name in required_names)
    if joint_ready:
        raise AssertionError("CURRENT_TREE_CANNOT_BE_JOINT_READY_WITH_DECLARED_HOLDS")
    return {
        "schema": "R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1",
        "technical_verdict": "R2_DYNAMICS_CONTROL_SYSTEM_HOLD__MECHANICAL_DYNAMICS_CONTROL_SAFE_SIM13_GATES_OPEN__NO_PATH_SEARCH__NO_RELEASE_CREDIT",
        "scope": "FAIL_CLOSED_SYSTEM_JOIN__NO_RUNTIME_EXECUTION",
        "package_manifest_coverage_policy": "ALL_REQUIRED_PACKAGE_ARTIFACTS_INCLUDING_INDEPENDENT_REVIEW_RECEIPT__MANIFEST_EXCLUDES_ONLY_ITSELF",
        "conditions": conditions,
        "required_condition_evaluation": {
            "names": required_names,
            "pass_count": sum(conditions[name] is True for name in required_names),
            "total": len(required_names),
            "all_pass": joint_ready,
        },
        "upstream_manifest_audit": upstream_integrity,
        "independent_review": independent_review,
        "diagnostic_facts_no_credit": {
            "owner_option_a_selected": owner_option_a,
            "low_memory_override_authorized": low_memory_override,
            "low_memory_authorized_run_id": low_memory.get("authorized_run_id"),
            "low_memory_authorization_window_start_utc": low_memory.get(
                "authorization_window_start_utc"
            ),
            "low_memory_authorization_window_end_utc": low_memory.get(
                "authorization_window_end_utc"
            ),
            "mechanical_static_frame_rows_bound": mechanical["actual_closures"][
                "accepted_urdf_subtree_collision_frame_rows"
            ],
            "mechanical_path_search_executed": mechanical["execution_record"][
                "path_search_executed"
            ],
            "dynamics_DG1_coordinate_metric_bound": constrained["checks"][
                "DG1_heterogeneous_coordinate_metric_bound"
            ],
            "dynamics_DG2_independent_conservation": constrained["checks"][
                "DG2_independent_full_state_momentum_conservation"
            ],
            "control_task_space_metric_bound_native": task_metric_bound,
            "control_both_outer_task_guards_allow_native": both_guards_allow,
            "safe_historical_gate_verdict": safe.get("verdict"),
            "sim13_negative_control_score": sim13.get("nc_score"),
            "sim13_maximum_operational_state": sim13.get("maximum_operational_state"),
        },
        "source_binding_pass": binding["all_match"],
        "artifact_package_complete": bool(package_preflight_pass),
        "candidate_integration_contract_bound": bool(
            binding["all_match"]
            and upstream_integrity["pass"]
            and owner_option_a
            and independent_review["evidence_valid"]
        ),
        "mechanical_handoff_pass": conditions["mechanical_handoff_pass"],
        "dynamics_engineering_pass": conditions["dynamics_engineering_pass"],
        "control_engineering_pass": conditions["control_engineering_pass"],
        "safe_independent_review_pass": conditions["safe_independent_review_pass"],
        "sim13_binding_pass": conditions["sim13_system_binding_pass"],
        "joint_system_ready": joint_ready,
        "ready_for_physics_gated_embodied_intelligence": False,
        "path_search_executed": mechanical["execution_record"]["path_search_executed"],
        "unknown_auto_allow_count": 0,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW__INDEPENDENT_TECHNICAL_REVIEW_COMPLETE",
    }


def required_package_files() -> list[Path]:
    required = [
        PACKAGE / "README.md",
        CONTRACT_PATH,
        PACKAGE / "src" / "build_joint_system_gate.py",
        PACKAGE / "tests" / "test_joint_system_gate.py",
        AUDIT_PATH,
        RESULTS / "R2_DYNAMICS_CONTROL_SOURCE_BINDING_V1.json",
        RESULTS / "R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json",
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "JOINT_REQUIRED_ARTIFACT_MISSING:"
            + ",".join(path.as_posix() for path in missing)
        )
    return required


def _static_required_files() -> list[Path]:
    required = [
        PACKAGE / "README.md",
        CONTRACT_PATH,
        PACKAGE / "src" / "build_joint_system_gate.py",
        PACKAGE / "tests" / "test_joint_system_gate.py",
        AUDIT_PATH,
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "JOINT_STATIC_ARTIFACT_MISSING:"
            + ",".join(path.as_posix() for path in missing)
        )
    return required


def _manifest_bytes(binding_bytes: bytes, gate_bytes: bytes) -> bytes:
    output_bytes = {
        RESULTS / "R2_DYNAMICS_CONTROL_SOURCE_BINDING_V1.json": binding_bytes,
        RESULTS / "R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json": gate_bytes,
    }
    ordered = [
        PACKAGE / "README.md",
        CONTRACT_PATH,
        PACKAGE / "src" / "build_joint_system_gate.py",
        PACKAGE / "tests" / "test_joint_system_gate.py",
        AUDIT_PATH,
        *output_bytes,
    ]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["path", "bytes", "sha256"])
    for path in ordered:
        data = output_bytes[path] if path in output_bytes else path.read_bytes()
        writer.writerow(
            [
                path.relative_to(PACKAGE).as_posix(),
                len(data),
                hashlib.sha256(data).hexdigest().upper(),
            ]
        )
    return stream.getvalue().encode("utf-8")


def _commit_outputs_gate_last(payloads: list[tuple[Path, bytes]]) -> None:
    staged: list[tuple[Path, Path, bytes]] = []
    try:
        for path, data in payloads:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.staged")
            temporary.write_bytes(data)
            if temporary.read_bytes() != data:
                raise OSError(f"STAGED_OUTPUT_BYTE_MISMATCH:{path.as_posix()}")
            staged.append((path, temporary, data))
        for path, temporary, _ in staged:
            temporary.replace(path)
    finally:
        for _, temporary, _ in staged:
            if temporary.exists():
                temporary.unlink()


def build() -> dict[str, Any]:
    static_files = _static_required_files()
    package_preflight_pass = bool(
        static_files
        and all(path.is_file() and path.stat().st_size > 0 for path in static_files)
    )
    contract = load_json_strict(CONTRACT_PATH)
    binding, documents = bind_sources(contract)
    independent_review = validate_red_team_audit()
    if not independent_review["evidence_valid"]:
        raise RuntimeError("JOINT_INDEPENDENT_REVIEW_EVIDENCE_FAIL_CLOSED")
    gate = build_gate(
        contract,
        binding,
        documents,
        independent_review,
        package_preflight_pass,
    )
    binding_bytes = _json_bytes(binding)
    gate_bytes = _json_bytes(gate)
    manifest_bytes = _manifest_bytes(binding_bytes, gate_bytes)
    _commit_outputs_gate_last(
        [
            (RESULTS / "R2_DYNAMICS_CONTROL_SOURCE_BINDING_V1.json", binding_bytes),
            (RESULTS / "R2_DYNAMICS_CONTROL_SHA256_V1.csv", manifest_bytes),
            (RESULTS / "R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json", gate_bytes),
        ]
    )
    required_package_files()
    manifest_audit = _validate_csv_hash_manifest(
        load_csv_strict(RESULTS / "R2_DYNAMICS_CONTROL_SHA256_V1.csv"),
        base=PACKAGE,
    )
    if not manifest_audit["pass"]:
        raise RuntimeError("JOINT_OUTPUT_MANIFEST_FAIL_CLOSED")
    return gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    gate = build()
    print(gate["technical_verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
