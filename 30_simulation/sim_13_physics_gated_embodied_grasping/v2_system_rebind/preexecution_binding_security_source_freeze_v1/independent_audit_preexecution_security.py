#!/usr/bin/env python3
"""Independent stdlib-only audit of the pre-Gate evidence DAG."""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
FALSE_FIELDS = (
    "system_urdf_available", "current_system_bound", "interface_instantiated",
    "physical_contact_ready", "dynamics_backend_ready", "contact_execution_authorized",
    "grasp_training_authorized", "next_stage_authorized", "release",
)
PROHIBITED_EXTENSIONS = {
    ".urdf", ".xacro", ".sdf", ".step", ".stp", ".iges", ".igs", ".brep", ".fcstd",
    ".dwg", ".dxf", ".sat", ".x_t", ".x_b", ".stl", ".obj", ".dae", ".ply",
    ".gltf", ".glb", ".3mf", ".inp", ".odb", ".pyc", ".pyo",
}
CACHE_DIRECTORIES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis", ".tox", ".nox"}
MANIFEST_EXCLUDED_DIRECTORIES = {"evidence", "results", "manifest", "__pycache__", ".pytest_cache"}
FIXED_OUTPUT_FILES = {
    "evidence/PREEXECUTION_BINDING_SECURITY_INDEPENDENT_AUDIT_V1.json",
    "evidence/PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_VALIDATION_V1.json",
    "evidence/PREEXECUTION_SECURITY_NEGATIVE_CONTROLS_V1.json",
    "evidence/PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1.json",
    "manifest/PREEXECUTION_BINDING_SECURITY_SOURCE_SHA256_V1.json",
    "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1.json",
    "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_TERMINAL_V1.json",
}
EXPECTED_NC_REASONS = {
    "NC15": "REPLAY_NONCE",
    "NC16": "SHIELD_ATTESTATION_REQUIRED",
    "NC20": "MISSING_RECEIPT_KIND:FEASIBILITY_150KG_V2|MISSING_RECEIPT_KIND:POST_GRASP_V2",
}


def _walk_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite JSON")
    if isinstance(value, dict):
        for child in value.values():
            _walk_finite(child)
    elif isinstance(value, list):
        for child in value:
            _walk_finite(child)


def _strict(path: Path) -> Any:
    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise ValueError(f"duplicate key: {key}")
            output[key] = value
        return output
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=hook,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    _walk_finite(value)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(PROJECT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _recompute_nc_records(negative: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Derive every NC verdict from records; never trust the summary fields."""

    groups = negative.get("groups")
    if not isinstance(groups, list):
        return False, {"error": "groups_not_list"}
    derived_passed: list[str] = []
    group_details: dict[str, Any] = {}
    for control_id, expected_reason in EXPECTED_NC_REASONS.items():
        selected = [group for group in groups if group.get("control_id") == control_id]
        if len(selected) != 1:
            group_details[control_id] = {"valid": False, "reason": "group_cardinality"}
            continue
        group = selected[0]
        records = group.get("records")
        valid_records = isinstance(records, list) and len(records) == 2
        normalized: list[dict[str, Any]] = []
        repeat_ids: list[str] = []
        if valid_records:
            for record in records:
                valid_records = valid_records and isinstance(record, dict)
                if not isinstance(record, dict):
                    continue
                repeat_ids.append(record.get("repeat_id"))
                valid_records = valid_records and (
                    record.get("control_id") == control_id
                    and record.get("baseline_valid") is True
                    and record.get("expected_reason") == expected_reason
                    and record.get("observed_reason") == expected_reason
                    and record.get("observed_outcome") == "MASK_TO_ABORT_ONLY"
                    and record.get("non_abort_execution_count") == 0
                    and record.get("exact_reason_match") is True
                    and record.get("baseline_hash_unchanged") is True
                )
                normalized.append({key: value for key, value in record.items() if key != "repeat_id"})
        deterministic = bool(valid_records and repeat_ids == ["R1", "R2"] and normalized[0] == normalized[1])
        derived = bool(valid_records and deterministic)
        summary_consistent = (
            group.get("deterministic_repeat") is deterministic
            and group.get("status") == ("PASS_NEGATIVE_CONTROL_DETECTED" if derived else "FAIL_NEGATIVE_CONTROL_ESCAPED")
        )
        group_details[control_id] = {
            "records_valid": bool(valid_records),
            "deterministic_recomputed": deterministic,
            "summary_consistent": bool(summary_consistent),
        }
        if derived and summary_consistent:
            derived_passed.append(control_id)
    pins = negative.get("parent_baseline_hashes_before")
    after = negative.get("parent_baseline_hashes_after")
    pins_current = isinstance(pins, dict) and pins == after and all(
        (PROJECT / relative).is_file() and _sha(PROJECT / relative) == digest
        for relative, digest in pins.items()
    )
    summary_consistent = (
        len(groups) == len(EXPECTED_NC_REASONS)
        and negative.get("controls_requested") == list(EXPECTED_NC_REASONS)
        and negative.get("controls_passed") == derived_passed
        and negative.get("all_requested_controls_passed") is bool(derived_passed == list(EXPECTED_NC_REASONS))
        and negative.get("parent_baseline_hashes_unchanged") is bool(pins_current)
        and negative.get("parent_formal_nc_passed") == 15
        and negative.get("parent_formal_nc_total") == 20
        and negative.get("formal_nc_promotion") == 0
        and negative.get("additive_effective_source_only_frontier_passed") == (18 if len(derived_passed) == 3 and pins_current else 15)
        and negative.get("additive_effective_source_only_frontier_total") == 20
        and negative.get("remaining_dependency_holds") == ["NC18", "NC19"]
        and negative.get("contact_release_eligible") is False
        and negative.get("next_stage_authorized") is False
    )
    passed = derived_passed == list(EXPECTED_NC_REASONS) and pins_current and summary_consistent
    return passed, {
        "derived_controls_passed": derived_passed,
        "group_details": group_details,
        "parent_pins_current": bool(pins_current),
        "summary_consistent": bool(summary_consistent),
    }


def _asset_cache_findings() -> list[str]:
    findings: list[str] = []
    for path in HERE.rglob("*"):
        relative = path.relative_to(HERE).as_posix()
        if path.is_dir() and path.name.lower() in CACHE_DIRECTORIES:
            findings.append(f"CACHE_DIR:{relative}")
        elif path.is_file() and path.suffix.lower() in PROHIBITED_EXTENSIONS:
            findings.append(f"FORBIDDEN_FILE:{relative}")
    return sorted(findings)


def build_audit() -> dict[str, Any]:
    manifest_path = HERE / "manifest/PREEXECUTION_BINDING_SECURITY_SOURCE_SHA256_V1.json"
    validation_path = HERE / "evidence/PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_VALIDATION_V1.json"
    negative_path = HERE / "evidence/PREEXECUTION_SECURITY_NEGATIVE_CONTROLS_V1.json"
    pytest_path = HERE / "evidence/PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1.json"
    manifest = _strict(manifest_path)
    validation = _strict(validation_path)
    negative = _strict(negative_path)
    pytest_receipt = _strict(pytest_path)
    checks: dict[str, bool] = {}
    recorded_paths = {item["path"] for item in manifest["files"]}
    actual_paths = {
        path.relative_to(PROJECT).as_posix()
        for path in HERE.rglob("*")
        if path.is_file()
        and not any(part in MANIFEST_EXCLUDED_DIRECTORIES for part in path.relative_to(HERE).parts)
    }
    checks["manifest_all_files_current"] = recorded_paths == actual_paths and all(
        (PROJECT / item["path"]).is_file()
        and (PROJECT / item["path"]).stat().st_size == item["bytes"]
        and _sha(PROJECT / item["path"]) == item["sha256"]
        for item in manifest["files"]
    ) and manifest["file_count"] == len(manifest["files"])
    package_prefix = HERE.relative_to(PROJECT).as_posix() + "/"
    source_relative_paths = {
        path[len(package_prefix):]
        for path in recorded_paths
        if isinstance(path, str) and path.startswith(package_prefix)
    }
    allowed_package_files = source_relative_paths | FIXED_OUTPUT_FILES
    allowed_package_directories = {
        parent.as_posix()
        for relative in allowed_package_files
        for parent in PurePosixPath(relative).parents
        if parent.as_posix() != "."
    }
    actual_package_files = {
        path.relative_to(HERE).as_posix() for path in HERE.rglob("*") if path.is_file()
    }
    actual_package_directories = {
        path.relative_to(HERE).as_posix() for path in HERE.rglob("*") if path.is_dir()
    }
    checks["full_package_exact_allowlist"] = (
        len(source_relative_paths) == len(recorded_paths)
        and actual_package_files == allowed_package_files
        and actual_package_directories == allowed_package_directories
        and manifest.get("full_package_allowed_file_count") == len(allowed_package_files)
        and manifest.get("fixed_output_files") == sorted(FIXED_OUTPUT_FILES)
        and manifest.get("package_inventory_findings") == []
    )
    checks["manifest_source_static_pass"] = manifest["source_static_pass"] is True and manifest["source_static_findings"] == []
    checks["validation_complete"] = (
        validation["status"] == "PASS_SOURCE_FREEZE_ONLY"
        and validation["checks_passed"] == validation["checks_total"]
        and all(item.get("passed") is True for item in validation["checks"])
        and {item.get("id") for item in validation["checks"]}
        == {f"PSF-{index:02d}" for index in range(1, 18)}
        and validation.get("parent_formal_nc") == {"passed": 15, "total": 20, "promoted": 0}
        and validation.get("additive_effective_source_only_nc", {}).get("passed") == 18
        and validation.get("additive_effective_source_only_nc", {}).get("holds") == ["NC18", "NC19"]
    )
    expected_validation_inputs = {
        "source_manifest": _receipt(manifest_path),
        "negative_controls": _receipt(negative_path),
        "pytest": _receipt(pytest_path),
    }
    checks["validation_dag_inputs_exact"] = validation.get("dag_inputs") == expected_validation_inputs
    nc_passed, nc_recomputed = _recompute_nc_records(negative)
    checks["negative_control_records_recomputed"] = nc_passed
    checks["mandatory_false_exact"] = all(validation.get(field) is False for field in FALSE_FIELDS)
    checks["no_production_credit"] = validation["production_credit"] is False
    checks["replay_scope_nonproduction"] = validation.get("replay_store_scope") == "IN_PROCESS_SYNTHETIC_NONPERSISTENT__NO_PRODUCTION_CREDIT"
    interface_path = PROJECT / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
    urdf_path = PROJECT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf"
    checks["production_artifacts_absent"] = not interface_path.exists() and not urdf_path.exists()
    asset_findings = _asset_cache_findings()
    checks["no_generated_asset_or_cache"] = not asset_findings
    forbidden_ast: list[str] = []
    for path in HERE.rglob("*.py"):
        if any(part in CACHE_DIRECTORIES for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                text = ast.unparse(node)
                if "unified_r2_urdf_source_v2" in text:
                    forbidden_ast.append(path.name)
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if name in {"gen_urdf", "_build_robot"}:
                    forbidden_ast.append(path.name)
    checks["no_generator_import_or_call"] = forbidden_ast == []
    strict_json_path = HERE / "preexec_security/strict_json.py"
    strict_tree = ast.parse(strict_json_path.read_text(encoding="utf-8"))
    strict_constants: dict[str, Any] = {}
    loads_except_names: set[str] = set()
    for node in strict_tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.startswith("MAX_JSON_")
        ):
            try:
                strict_constants[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
        if isinstance(node, ast.FunctionDef) and node.name == "loads_strict":
            for child in ast.walk(node):
                if isinstance(child, ast.ExceptHandler):
                    if child.type is None:
                        loads_except_names.add("BARE_EXCEPT")
                    elif isinstance(child.type, ast.Name):
                        loads_except_names.add(child.type.id)
                    elif isinstance(child.type, ast.Attribute):
                        loads_except_names.add(ast.unparse(child.type))
                    elif isinstance(child.type, ast.Tuple):
                        loads_except_names.update(ast.unparse(item) for item in child.type.elts)
    checks["bounded_json_source_limits_frozen"] = strict_constants == {
        "MAX_JSON_BYTES": 262144,
        "MAX_JSON_DEPTH": 64,
        "MAX_JSON_COMPLEXITY_UNITS": 8192,
        "MAX_JSON_NODES": 8193,
        "MAX_JSON_STRING_CHARS": 16384,
        "MAX_JSON_TOTAL_STRING_CHARS": 131072,
        "MAX_JSON_NUMBER_CHARS": 256,
    }
    checks["bounded_json_narrow_exception_policy"] = (
        loads_except_names
        == {
            "UnicodeDecodeError",
            "UnicodeEncodeError",
            "StrictJSONError",
            "json.JSONDecodeError",
            "RecursionError",
            "ValueError",
        }
        and not any(
            isinstance(node, ast.ExceptHandler)
            and (
                node.type is None
                or (isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException", "MemoryError", "KeyboardInterrupt"})
            )
            for path in (strict_json_path, HERE / "preexec_security/receipts.py")
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    )
    boundary_checks = [item for item in validation.get("checks", []) if item.get("id") == "PSF-17"]
    expected_limit_record = {
        "bytes": 262144,
        "depth": 64,
        "complexity_units": 8192,
        "nodes": 8193,
        "string_chars": 16384,
        "total_string_chars": 131072,
        "number_chars": 256,
    }
    checks["bounded_json_totality_evidence_exact"] = (
        len(boundary_checks) == 1
        and boundary_checks[0].get("passed") is True
        and boundary_checks[0].get("observed", {}).get("limits") == expected_limit_record
        and boundary_checks[0].get("observed", {}).get("adjacent_limits_pass") is True
        and boundary_checks[0].get("observed", {}).get("denial_nonce_consumption") == 0
        and boundary_checks[0].get("observed", {}).get("parser_reasons")
        == {
            "deep_array_1200": "JSON_DEPTH_LIMIT_EXCEEDED",
            "deep_object_1200": "JSON_DEPTH_LIMIT_EXCEEDED",
            "escaped_lone_surrogate": "INVALID_UTF8_STRING:$",
            "integer_5000_digits": "INTEGER_DIGIT_LIMIT_EXCEEDED",
            "invalid_utf8": "INVALID_UTF8",
            "overlong_string": "JSON_STRING_CHARACTER_LIMIT_EXCEEDED",
            "oversize_bytes": "JSON_BYTE_LIMIT_EXCEEDED",
        }
        and boundary_checks[0].get("observed", {}).get("in_memory_surrogate_action_context_pass") is True
        and str(boundary_checks[0].get("observed", {}).get("in_memory_surrogate_verify_reason", "")).startswith("INVALID_UTF8_STRING")
    )
    checks["pytest_receipt_no_cache"] = (
        pytest_receipt.get("schema") == "PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1"
        and type(pytest_receipt.get("collected")) is int
        and pytest_receipt.get("collected") > 0
        and pytest_receipt.get("failed") == 0
        and pytest_receipt.get("passed") == pytest_receipt.get("collected")
        and pytest_receipt.get("collected") >= 97
        and isinstance(pytest_receipt.get("duration_seconds"), (int, float))
        and pytest_receipt.get("duration_seconds") > 0
        and pytest_receipt.get("cacheprovider_disabled") is True
        and pytest_receipt.get("bytecode_write_disabled") is True
    )
    passed = all(checks.values())
    return {
        "schema": "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_INDEPENDENT_AUDIT_V1",
        "status": "PASS_INDEPENDENT_SOURCE_FREEZE_AUDIT" if passed else "FAIL_INDEPENDENT_AUDIT",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "negative_control_recomputation": nc_recomputed,
        "asset_cache_findings": asset_findings,
        "dag_inputs": {
            "source_manifest": _receipt(manifest_path),
            "negative_controls": _receipt(negative_path),
            "pytest": _receipt(pytest_path),
            "validation": _receipt(validation_path),
        },
        "gate_ceiling": "PASS_SOURCE_FREEZE_ONLY",
        "formal_nc_promotion": 0,
        "production_credit": False,
        **{field: False for field in FALSE_FIELDS},
    }


def main() -> int:
    audit = build_audit()
    print(json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if audit["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
