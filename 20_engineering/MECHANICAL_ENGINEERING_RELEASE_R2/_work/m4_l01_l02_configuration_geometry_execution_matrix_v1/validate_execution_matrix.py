"""Independent validator for the M4 L01/L02 geometry execution matrix pack.

This module never imports the builder or the guarded CAD generator.  It reads
the frozen third-party spec and validates emitted bytes, semantics, source
pins, AST import boundaries, negative controls, Gate, and manifest.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

from frozen_execution_spec_v1 import (
    COMPONENT_AUDIT,
    CONFIGURATIONS,
    CONFIG_IDS,
    D01_CONTRACT,
    FRAME_LEDGER,
    GATE_CRITERION_COUNT,
    LOCAL_MANIFEST_ROLES,
    NEGATIVE_CONTROL_COUNT,
    Q_HOME,
    Q_ZERO,
    SNAPSHOT_PLAN,
    SOURCE_PINS,
    STEP_FIRST_PLAN,
    T_S_B601_ARM_BASE_ROWS_MM,
)


PACKAGE = Path(__file__).resolve().parent
MANIFEST_NAME = "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_SHA256_V1.csv"
GATE_NAME = "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_GATE_V1.json"
NEGATIVE_NAME = "NEGATIVE_CONTROL_RESULTS_V1.json"
FORBIDDEN_TOP_LEVEL_CAD_MODULES = {"OCP", "build123d", "FreeCAD", "Part", "cadquery", "OCC"}


class ValidationError(RuntimeError):
    pass


def workspace_root(start: Path = PACKAGE) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise ValidationError("WORKSPACE_ROOT_NOT_FOUND")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _reject_constant(value: str):
    raise ValidationError(f"NONFINITE_JSON_CONSTANT:{value}")


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValidationError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def assert_finite(value: object, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationError(f"NONFINITE_VALUE:{path}")
    if isinstance(value, dict):
        for key, child in value.items():
            assert_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_finite(child, f"{path}[{index}]")


def strict_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValidationError(f"MISSING_FILE:{path.name}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except UnicodeDecodeError as exc:
        raise ValidationError(f"INVALID_UTF8:{path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"INVALID_JSON:{path.name}:{exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"TOP_LEVEL_OBJECT_REQUIRED:{path.name}")
    assert_finite(value)
    return value


def _check(rows: list[dict], check_id: str, condition: bool, detail: str = "") -> None:
    rows.append({"id": check_id, "pass": condition is True, "detail": detail})


def _load_core(package: Path) -> dict[str, dict]:
    mapping = {
        "source_lock": "SOURCE_AUTHORITY_LOCK_V1.json",
        "component": "COMPONENT_GEOMETRY_CAPABILITY_AUDIT_V1.yaml",
        "matrix": "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml",
        "frames": "FRAME_PLACEMENT_LEDGER_V1.yaml",
        "contract": "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml",
        "plan": "STEP_FIRST_BUILD_PLAN_V1.yaml",
        "preflight": "SOURCE_ONLY_PREFLIGHT_V1.json",
        "snapshots": "SNAPSHOT_TASK_PLAN_V1.json",
    }
    return {key: strict_json(package / name) for key, name in mapping.items()}


def _source_rows_exact(source_lock: dict) -> bool:
    rows = source_lock.get("sources")
    if not isinstance(rows, list) or len(rows) != len(SOURCE_PINS):
        return False
    for actual, expected in zip(rows, SOURCE_PINS, strict=True):
        for key in ("id", "path", "bytes", "sha256", "role"):
            if actual.get(key) != expected[key]:
                return False
        if actual.get("exists") is not True:
            return False
        if actual.get("actual_bytes") != expected["bytes"]:
            return False
        if actual.get("actual_sha256") != expected["sha256"]:
            return False
        if actual.get("match") is not True:
            return False
    return True


def _external_sources_match(source_lock: dict, root: Path) -> bool:
    for row in source_lock["sources"]:
        path = root / row["path"]
        if not path.is_file():
            return False
        if path.stat().st_size != row["bytes"]:
            return False
        if sha256(path) != row["sha256"]:
            return False
    return True


def _generator_ast_checks(path: Path) -> tuple[bool, bool, bool, bool]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    top_modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_modules.add(node.module.split(".")[0])
    no_top_cad = not (top_modules & FORBIDDEN_TOP_LEVEL_CAD_MODULES)

    gen = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "gen_step"), None)
    if gen is None:
        return no_top_cad, False, False, False
    delayed_modules: set[str] = set()
    authority_call_line = None
    first_cad_import_line = None
    for node in ast.walk(gen):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_execution_authority":
            authority_call_line = node.lineno if authority_call_line is None else min(authority_call_line, node.lineno)
        if isinstance(node, ast.Import):
            modules = {alias.name.split(".")[0] for alias in node.names}
            if modules & FORBIDDEN_TOP_LEVEL_CAD_MODULES:
                delayed_modules.update(modules)
                first_cad_import_line = node.lineno if first_cad_import_line is None else min(first_cad_import_line, node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.split(".")[0]
            if module in FORBIDDEN_TOP_LEVEL_CAD_MODULES:
                delayed_modules.add(module)
                first_cad_import_line = node.lineno if first_cad_import_line is None else min(first_cad_import_line, node.lineno)
    delayed_present = {"OCP", "build123d"}.issubset(delayed_modules)
    authority_before_import = bool(authority_call_line and first_cad_import_line and authority_call_line < first_cad_import_line)
    source_guards = all(
        token in source
        for token in (
            "GENERATION_NOT_AUTHORIZED_SOURCE_ONLY",
            "M4_GEOM_EXECUTION_AUTHORIZED",
            "MEMORY_GATE_GIB = 6.0",
            "EXPECTED_OUTPUT_SOLIDS = 403",
            "MASTER_INDICES = (1, 2, 3, 4, 5, 6, 27, 28, 41)",
            "SOLAR_INDICES = (7, 8, 9, 10, 11, 12)",
            "STATIC_CAD_Q0_CANNOT_STAND_IN_FOR_C01_QHOME",
        )
    )
    return no_top_cad, delayed_present, authority_before_import, source_guards


def evaluate_core(
    package: Path = PACKAGE,
    root: Path | None = None,
    verify_external_sources: bool = True,
) -> list[dict]:
    checks: list[dict] = []
    root = root or workspace_root(package)
    try:
        core = _load_core(package)
    except (ValidationError, OSError, SyntaxError) as exc:
        _check(checks, "V00_CORE_PARSE", False, str(exc))
        return checks

    lock = core["source_lock"]
    matrix = core["matrix"]
    contract = core["contract"]
    frames = core["frames"]
    plan = core["plan"]
    preflight = core["preflight"]
    snapshots = core["snapshots"]
    configurations = matrix.get("configurations", [])
    if not isinstance(configurations, list):
        configurations = []

    _check(checks, "V01_SOURCE_LOCK_SCHEMA", lock.get("schema") == "M4_L01_L02_GEOMETRY_SOURCE_AUTHORITY_LOCK_V1")
    _check(checks, "V02_SOURCE_COUNT_EXACT", lock.get("source_count") == 37 == len(SOURCE_PINS))
    ids = [row.get("id") for row in lock.get("sources", [])]
    paths = [row.get("path") for row in lock.get("sources", [])]
    _check(checks, "V03_SOURCE_IDS_UNIQUE", len(ids) == len(set(ids)) == 37 and lock.get("source_id_unique") is True)
    _check(checks, "V04_SOURCE_PATHS_UNIQUE", len(paths) == len(set(paths)) == 37 and lock.get("source_path_unique") is True)
    _check(checks, "V05_SOURCE_ROWS_EXACT", _source_rows_exact(lock))
    _check(checks, "V06_SOURCE_LOCK_ALL_MATCH_TRUE", lock.get("all_sources_match") is True)
    _check(checks, "V07_EXTERNAL_SOURCE_RECOMPUTE", (not verify_external_sources) or _external_sources_match(lock, root))

    _check(checks, "V08_COMPONENT_AUDIT_EXACT", core["component"] == COMPONENT_AUDIT)
    _check(checks, "V09_MATRIX_SCHEMA", matrix.get("schema") == "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1")
    _check(checks, "V10_NINE_CONFIGS", matrix.get("configuration_count") == 9 and len(configurations) == 9)
    _check(checks, "V11_CONFIG_IDS_EXACT", matrix.get("configuration_ids") == list(CONFIG_IDS) and [row.get("configuration_id") if isinstance(row, dict) else None for row in configurations] == list(CONFIG_IDS))
    _check(checks, "V12_CONFIG_ROWS_EXACT", configurations == CONFIGURATIONS)
    _check(checks, "V13_ZERO_CURRENT_STEP_BUILDABLE", matrix.get("configuration_current_step_buildable_count") == 0 and len(configurations) == 9 and all(isinstance(row, dict) and row.get("configuration_current_step_buildable_now") is False for row in configurations))
    _check(checks, "V14_ZERO_COMPLETE_GEOMETRY", matrix.get("current_complete_integrated_geometry_count") == 0 and len(configurations) == 9 and all(isinstance(row, dict) and row.get("current_complete_integrated_geometry") is False for row in configurations))
    _check(checks, "V15_ONE_DIAGNOSTIC_BRANCH", matrix.get("source_only_diagnostic_recipe_count") == 1 and len(matrix.get("non_configuration_current_diagnostic_branches", [])) == 1)
    branch = matrix["non_configuration_current_diagnostic_branches"][0]
    _check(checks, "V16_D01_NOT_C01_CURRENT", branch.get("branch_id") == D01_CONTRACT["branch_id"] and branch.get("configuration_current") is False and branch.get("maximum_claim") == "SOURCE_ONLY_FIXED_Q0_DIAGNOSTIC_RECIPE__NOT_C01_CURRENT")

    _check(checks, "V17_D01_CONTRACT_EXACT", contract == D01_CONTRACT)
    _check(checks, "V18_C01_QHOME_EXACT", len(configurations) >= 1 and isinstance(configurations[0], dict) and configurations[0].get("authoritative_q6_rad") == Q_HOME)
    _check(checks, "V19_D01_QZERO_EXACT", contract.get("q6_rad") == Q_ZERO and contract.get("reason_not_c01_current") == "STATIC_CAD_Q0_CANNOT_STAND_IN_FOR_C01_QHOME")
    _check(checks, "V20_C05_C09_AUTH_Q_NULL", len(configurations) == 9 and all(isinstance(row, dict) and row.get("authoritative_q6_rad") is None for row in configurations[4:]))
    _check(checks, "V21_TARGET_ATTACHMENTS_NULL", len(configurations) == 9 and all(isinstance(row, dict) and row.get("target_attachment_transform_S_rows") is None for row in configurations))
    _check(checks, "V22_C08_C09_TARGET_IDS_ONLY", len(configurations) == 9 and isinstance(configurations[7], dict) and isinstance(configurations[8], dict) and configurations[7].get("target_id") == "TARGET_SATELLITE_22KG" and configurations[8].get("target_id") == "TARGET_DEBRIS_150KG")
    _check(checks, "V23_SOLAR_FAILURE_TRANSFORMS_UNKNOWN", len(configurations) == 9 and all(isinstance(row, dict) and row.get("solar_transform_status") == "UNKNOWN_NO_CURRENT_INTEGRATED_GEOMETRY" for row in configurations[1:4]))

    _check(checks, "V24_FRAME_LEDGER_EXACT", frames == FRAME_LEDGER)
    _check(checks, "V25_UNITS_AND_ROOT_EXACT", contract.get("units") == "mm" and contract.get("root_frame") == "S" and frames["unit_policy"]["urdf_length"] == "m")
    _check(checks, "V26_B601_MATRIX_EXACT", contract["placements"]["B601_FIXED_Q0_LOCAL_TO_S_ROWS_MM"] == T_S_B601_ARM_BASE_ROWS_MM)
    _check(checks, "V27_NULL_PLACEMENTS_STRUCTURED", contract["placements"]["TARGET_22KG"] is None and contract["placements"]["TARGET_150KG"] is None and contract["placements"]["ARM_HDRM"] is None and contract["placements"]["SOLAR_HDRM_HARDWARE"] is None)
    _check(checks, "V28_SELECTIONS_EXACT", [row["index"] for row in contract["master_retained"]] == [1, 2, 3, 4, 5, 6, 27, 28, 41] and [row["index"] for row in contract["solar_selected"]] == [7, 8, 9, 10, 11, 12])
    _check(checks, "V29_NO_HDRM_KEEPOUT_PROMOTION", contract["solar_rejected_ranges"][-1] == {"indices": [19, 22], "reason": "HDRM_KEEPOUTS_ARE_NOT_HARDWARE_SOLIDS"})
    _check(checks, "V30_COUNTS_EXACT_403_3", contract["expected"]["leaf_solid_count"] == 403 and contract["expected"]["intermediate_group_count"] == 3 and sum(contract["expected"]["groups"].values()) == 403)
    _check(checks, "V31_BBOX_EXACT", contract["expected"]["bbox_S_mm"] == {"min": [-230.25, -715.4, -274.86072587989787], "max": [488.533214, 715.4, 285.63229786565915], "absolute_tolerance_mm": 0.1})
    _check(checks, "V32_DATUM_EXACT", contract["expected"]["m3r_arm_datum"] == {"installed_b601_min_x_mm": 210.405, "m3r_outer_face_x_mm": 210.405, "absolute_tolerance_mm": 0.01})

    _check(checks, "V33_STEP_PLAN_EXACT", plan == STEP_FIRST_PLAN)
    _check(checks, "V34_SNAPSHOT_PLAN_EXACT", snapshots == SNAPSHOT_PLAN)
    _check(checks, "V35_SNAPSHOTS_UNEXECUTED", all(task["executed"] is False and task["artifact"] is None for task in snapshots["tasks"]))
    _check(checks, "V36_PREFLIGHT_SOURCE_PASS", preflight.get("source_chain_pass") is True and preflight.get("source_count") == 37 and all(row.get("match") is True for row in preflight.get("source_matches", [])))
    _check(checks, "V37_NO_CAD_OR_STEP_EXECUTION", preflight.get("cad_kernel_import_attempted") is False and preflight.get("cad_kernel_loaded") is False and preflight.get("step_generation_attempted") is False and preflight.get("step_generation_executed") is False)
    _check(checks, "V38_NO_RUN_OR_MEMORY_AUTHORITY", preflight.get("fresh_run_authority_observed") is False and preflight.get("memory_measurement_attempted") is False and preflight.get("memory_gate_passed") is False and preflight.get("owner_override_observed") is False)
    _check(checks, "V39_NO_GEOMETRY_OUTPUTS", preflight.get("expected_output_exists") is False and preflight.get("forbidden_geometry_outputs_in_package") == [] and not any(path.suffix.lower() in {".step", ".stp", ".fcstd", ".glb"} for path in package.iterdir() if path.is_file()))

    boundary_fields = {
        "parent_gate_credit": matrix.get("parent_gate_credit"),
        "fresh_cad_run_authorized": matrix.get("fresh_cad_run_authorized"),
        "next_stage_authorized": matrix.get("next_stage_authorized"),
        "production_complete": matrix.get("production_complete"),
        "release_credit": matrix.get("release_credit"),
        "d01_configuration_credit": contract.get("configuration_credit"),
        "d01_collision_authority": contract.get("collision_authority"),
        "d01_contact_authority": contract.get("contact_authority"),
        "d01_mass_authority": contract.get("mass_authority"),
        "d01_production_authority": contract.get("production_authority"),
        "d01_release_credit": contract.get("release_credit"),
    }
    _check(checks, "V40_ALL_BOUNDARIES_FALSE", all(value is False for value in boundary_fields.values()), json.dumps(boundary_fields, sort_keys=True))

    generator = package / "source_only_step_generator_v1.py"
    try:
        no_top_cad, delayed_present, authority_before, source_guards = _generator_ast_checks(generator)
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        no_top_cad = delayed_present = authority_before = source_guards = False
        _check(checks, "V41_GENERATOR_AST_READ", False, str(exc))
    else:
        _check(checks, "V41_GENERATOR_AST_READ", True)
    _check(checks, "V42_GENERATOR_NO_TOP_LEVEL_CAD_IMPORT", no_top_cad)
    _check(checks, "V43_GENERATOR_DELAYED_CAD_IMPORT_PRESENT", delayed_present)
    _check(checks, "V44_AUTHORITY_BEFORE_CAD_IMPORT", authority_before)
    _check(checks, "V45_GENERATOR_GUARDS_FROZEN", source_guards)
    return checks


def evaluate_negative_receipt(package: Path = PACKAGE) -> list[dict]:
    checks: list[dict] = []
    try:
        value = strict_json(package / NEGATIVE_NAME)
    except ValidationError as exc:
        _check(checks, "N00_NEGATIVE_RECEIPT_PARSE", False, str(exc))
        return checks
    rows = value.get("results", [])
    ids = [row.get("id") for row in rows]
    _check(checks, "N01_NEGATIVE_SCHEMA", value.get("schema") == "M4_L01_L02_GEOMETRY_NEGATIVE_CONTROL_RESULTS_V1")
    _check(checks, "N02_NEGATIVE_COUNT", value.get("expected_count") == NEGATIVE_CONTROL_COUNT and value.get("executed_count") == NEGATIVE_CONTROL_COUNT and len(rows) == NEGATIVE_CONTROL_COUNT)
    _check(checks, "N03_NEGATIVE_IDS_UNIQUE", len(ids) == len(set(ids)) == NEGATIVE_CONTROL_COUNT)
    _check(checks, "N04_NEGATIVE_ALL_PASS", value.get("passed_count") == NEGATIVE_CONTROL_COUNT and value.get("all_passed") is True and all(row.get("passed") is True for row in rows))
    _check(checks, "N05_NEGATIVE_BOUNDARIES_FALSE", value.get("next_stage_authorized") is False and value.get("release_credit") is False)
    return checks


def evaluate_gate(package: Path = PACKAGE) -> list[dict]:
    checks: list[dict] = []
    try:
        gate = strict_json(package / GATE_NAME)
    except ValidationError as exc:
        _check(checks, "G00_GATE_PARSE", False, str(exc))
        return checks
    rows = gate.get("checks", [])
    ids = [row.get("id") for row in rows]
    _check(checks, "G01_GATE_SCHEMA", gate.get("schema") == "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_GATE_V1")
    _check(checks, "G02_GATE_COUNT", gate.get("expected_count") == GATE_CRITERION_COUNT and gate.get("passed_count") == GATE_CRITERION_COUNT and len(rows) == GATE_CRITERION_COUNT)
    _check(checks, "G03_GATE_IDS_UNIQUE", len(ids) == len(set(ids)) == GATE_CRITERION_COUNT and ids == [f"G{i:02d}_{suffix}" for i, suffix in enumerate([
        "SOURCE_COUNT_EXACT_37", "ALL_SOURCE_HASHES_MATCH", "SOURCE_IDS_UNIQUE", "SOURCE_PATHS_UNIQUE", "NINE_CONFIGURATIONS_EXACT", "CONFIGURATION_IDS_EXACT", "CONFIGURATION_CURRENT_STEP_COUNT_ZERO", "CURRENT_COMPLETE_GEOMETRY_COUNT_ZERO", "ONE_NON_CURRENT_DIAGNOSTIC_RECIPE", "D01_NOT_CONFIGURATION_CURRENT", "C01_QHOME_Q0_CONFLICT_EXACT", "D01_EXPECTED_403_SOLIDS", "D01_EXPECTED_3_GROUPS", "SELECTION_COUNTS_9_6_388", "D01_BBOX_FROZEN_MM", "UNIT_POLICY_MM", "B601_PLACEMENT_EXACT", "TARGET_ATTACHMENTS_REMAIN_NULL", "HDRM_HARDWARE_REMAINS_NULL", "C05_C09_Q_NOT_PROMOTED", "FAILURE_SOLAR_TRANSFORMS_NOT_INVENTED", "COLLISION_AUTHORITY_FALSE", "CONTACT_AUTHORITY_FALSE", "MASS_AUTHORITY_FALSE", "PRODUCTION_AND_RELEASE_FALSE", "FRESH_RUN_AUTHORITY_FALSE", "MEMORY_GATE_FALSE", "NO_CAD_KERNEL_OR_STEP_RUN", "SNAPSHOTS_UNEXECUTED", "NEGATIVE_CONTROLS_PASS"
    ], start=1)])
    _check(checks, "G04_GATE_ALL_PASS", gate.get("gate_passed") is True and all(row.get("pass") is True for row in rows))
    false_fields = [
        "parent_gate_credit", "configuration_credit", "fresh_cad_run_authorized",
        "memory_gate_passed", "owner_override_present", "cad_kernel_loaded",
        "step_generation_executed", "collision_authority", "contact_authority",
        "mass_authority", "next_stage_authorized", "operational_authorized",
        "production_complete", "release_credit",
    ]
    _check(checks, "G05_GATE_AUTHORITY_BOUNDARIES_FALSE", all(gate.get(key) is False for key in false_fields))
    _check(checks, "G06_GATE_COUNTS_ZERO_ONE", gate.get("configuration_current_step_buildable_count") == 0 and gate.get("source_only_diagnostic_recipe_count") == 1)
    expected_artifacts = {
        "SOURCE_AUTHORITY_LOCK_V1.json",
        "COMPONENT_GEOMETRY_CAPABILITY_AUDIT_V1.yaml",
        "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml",
        "FRAME_PLACEMENT_LEDGER_V1.yaml",
        "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml",
        "STEP_FIRST_BUILD_PLAN_V1.yaml",
        "SOURCE_ONLY_PREFLIGHT_V1.json",
        "SNAPSHOT_TASK_PLAN_V1.json",
        "NEGATIVE_CONTROL_RESULTS_V1.json",
    }
    hashes = gate.get("artifact_hashes", {})
    _check(checks, "G07_GATE_ARTIFACT_HASH_SET", set(hashes) == expected_artifacts)
    _check(checks, "G08_GATE_ARTIFACT_HASH_MATCH", all((package / name).is_file() and sha256(package / name) == digest for name, digest in hashes.items()))
    _check(checks, "G09_MANIFEST_SELF_EXCLUDED", gate.get("manifest") == {"path": MANIFEST_NAME, "self_excluded": True, "hash_embedded_here": False})
    return checks


def _actual_controlled_files(package: Path) -> set[str]:
    result = set()
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(package)
        if any(part in {"__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        result.add(relative.as_posix())
    return result


def evaluate_manifest(package: Path = PACKAGE) -> list[dict]:
    checks: list[dict] = []
    path = package / MANIFEST_NAME
    if not path.is_file():
        _check(checks, "M00_MANIFEST_PRESENT", False)
        return checks
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            header_ok = reader.fieldnames == ["path", "bytes", "sha256", "role", "exists"]
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        _check(checks, "M00_MANIFEST_PRESENT", False, str(exc))
        return checks
    _check(checks, "M00_MANIFEST_PRESENT", True)
    _check(checks, "M01_MANIFEST_HEADER_EXACT", header_ok)
    names = [row.get("path") for row in rows]
    _check(checks, "M02_MANIFEST_PATHS_UNIQUE", len(names) == len(set(names)))
    _check(checks, "M03_MANIFEST_EXACT_SET", set(names) == set(LOCAL_MANIFEST_ROLES))
    _check(checks, "M04_MANIFEST_ROLES_EXACT", all(row.get("role") == LOCAL_MANIFEST_ROLES.get(row.get("path")) for row in rows))
    row_matches = True
    for row in rows:
        local = package / row["path"]
        if not local.is_file() or row.get("exists") != "true":
            row_matches = False
            break
        if row.get("bytes") != str(local.stat().st_size) or row.get("sha256") != sha256(local):
            row_matches = False
            break
    _check(checks, "M05_MANIFEST_HASHES_MATCH", row_matches)
    actual = _actual_controlled_files(package)
    expected = set(LOCAL_MANIFEST_ROLES) | {MANIFEST_NAME}
    _check(checks, "M06_NO_EXTRA_OR_MISSING_CONTROLLED_FILES", actual == expected, f"extra={sorted(actual-expected)} missing={sorted(expected-actual)}")
    _check(checks, "M07_MANIFEST_SELF_EXCLUDED_ONLY", MANIFEST_NAME not in set(names) and len(rows) == len(LOCAL_MANIFEST_ROLES))
    return checks


def evaluate_all(
    package: Path = PACKAGE,
    root: Path | None = None,
    verify_external_sources: bool = True,
) -> list[dict]:
    return (
        evaluate_core(package, root, verify_external_sources)
        + evaluate_negative_receipt(package)
        + evaluate_gate(package)
        + evaluate_manifest(package)
    )


def main() -> int:
    checks = evaluate_all()
    failed = [row for row in checks if not row["pass"]]
    receipt = {
        "schema": "M4_L01_L02_GEOMETRY_EXECUTION_MATRIX_VALIDATION_STDOUT_V1",
        "passed_count": len(checks) - len(failed),
        "expected_count": len(checks),
        "all_passed": not failed,
        "failed": failed,
        "cad_kernel_loaded": any(module in sys.modules for module in FORBIDDEN_TOP_LEVEL_CAD_MODULES),
        "step_generation_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
