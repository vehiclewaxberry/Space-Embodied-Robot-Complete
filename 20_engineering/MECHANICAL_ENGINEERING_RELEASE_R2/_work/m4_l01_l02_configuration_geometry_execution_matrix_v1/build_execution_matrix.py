"""Deterministically emit the append-only source-only geometry execution pack."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path

from frozen_execution_spec_v1 import (
    COMPONENT_AUDIT,
    CONFIGURATIONS,
    CONFIG_IDS,
    D01_CONTRACT,
    FRAME_LEDGER,
    GATE_CRITERION_COUNT,
    LOCAL_MANIFEST_ROLES,
    NEGATIVE_CONTROL_COUNT,
    PACKAGE_NAME,
    Q_HOME,
    Q_ZERO,
    SCHEMA_VERSION,
    SNAPSHOT_PLAN,
    SOURCE_PINS,
    STEP_FIRST_PLAN,
    T_S_B601_ARM_BASE_ROWS_MM,
)


PACKAGE = Path(__file__).resolve().parent
MANIFEST = PACKAGE / "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_SHA256_V1.csv"
GATE = PACKAGE / "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_GATE_V1.json"
NEGATIVE_RECEIPT = PACKAGE / "NEGATIVE_CONTROL_RESULTS_V1.json"


def workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("WORKSPACE_ROOT_NOT_FOUND")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def assert_finite(value: object, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"NONFINITE_VALUE:{path}")
    if isinstance(value, dict):
        for key, child in value.items():
            assert_finite(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_finite(child, f"{path}[{index}]")


def write_json(path: Path, value: object) -> None:
    assert_finite(value)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def verify_sources(root: Path) -> tuple[list[dict], bool]:
    rows: list[dict] = []
    for pin in SOURCE_PINS:
        path = root / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = sha256(path) if exists else None
        match = bool(
            exists
            and actual_bytes == pin["bytes"]
            and actual_sha == pin["sha256"]
        )
        row = deepcopy(pin)
        row.update(
            {
                "exists": exists,
                "actual_bytes": actual_bytes,
                "actual_sha256": actual_sha,
                "match": match,
            }
        )
        rows.append(row)
    return rows, all(row["match"] for row in rows)


def build_source_lock(source_rows: list[dict], all_match: bool) -> dict:
    return {
        "schema": "M4_L01_L02_GEOMETRY_SOURCE_AUTHORITY_LOCK_V1",
        "package": PACKAGE_NAME,
        "source_count": len(source_rows),
        "source_id_unique": len({row["id"] for row in source_rows}) == len(source_rows),
        "source_path_unique": len({row["path"] for row in source_rows}) == len(source_rows),
        "all_sources_match": all_match,
        "sources": source_rows,
        "claim_limit": "SOURCE_HASH_BINDING_ONLY__NO_CAD_RUN_OR_AUTHORITY_PROMOTION",
        "parent_gate_credit": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_matrix() -> dict:
    return {
        "schema": "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1",
        "source_spec": SCHEMA_VERSION,
        "scope": "C01_C09_CONFIGURATION_CURRENT_STEP_BUILDABILITY_AND_NON_CURRENT_DIAGNOSTIC_INCREMENT",
        "decision_rule": "AUTHORITY_GREATER_THAN_EVIDENCE_GREATER_THAN_INDEPENDENT_REPRODUCTION_GREATER_THAN_AGENT_OPINION",
        "unknown_policy": "UNKNOWN_REMAINS_NULL__ZERO_OR_IDENTITY_FILL_FORBIDDEN",
        "configuration_count": len(CONFIGURATIONS),
        "configuration_ids": list(CONFIG_IDS),
        "configuration_current_step_buildable_count": sum(
            bool(row["configuration_current_step_buildable_now"]) for row in CONFIGURATIONS
        ),
        "current_complete_integrated_geometry_count": sum(
            bool(row["current_complete_integrated_geometry"]) for row in CONFIGURATIONS
        ),
        "source_only_diagnostic_recipe_count": 1,
        "configurations": deepcopy(CONFIGURATIONS),
        "non_configuration_current_diagnostic_branches": [
            {
                "branch_id": D01_CONTRACT["branch_id"],
                "configuration_reference": D01_CONTRACT["configuration_reference"],
                "configuration_current": False,
                "source_only_contract_emittable": True,
                "cad_run_authorized": False,
                "step_generated": False,
                "expected_leaf_solid_count": D01_CONTRACT["expected"]["leaf_solid_count"],
                "expected_intermediate_group_count": D01_CONTRACT["expected"]["intermediate_group_count"],
                "expected_bbox_S_mm": D01_CONTRACT["expected"]["bbox_S_mm"],
                "maximum_claim": "SOURCE_ONLY_FIXED_Q0_DIAGNOSTIC_RECIPE__NOT_C01_CURRENT",
            }
        ],
        "parent_gate_credit": False,
        "fresh_cad_run_authorized": False,
        "next_stage_authorized": False,
        "production_complete": False,
        "release_credit": False,
    }


def build_preflight(source_rows: list[dict], all_match: bool) -> dict:
    output = PACKAGE / D01_CONTRACT["output"]["path"]
    forbidden_outputs = sorted(
        path.name
        for path in PACKAGE.iterdir()
        if path.is_file() and path.suffix.lower() in {".step", ".stp", ".fcstd", ".glb"}
    )
    return {
        "schema": "M4_L01_L02_SOURCE_ONLY_PREFLIGHT_V1",
        "source_count": len(source_rows),
        "source_chain_pass": all_match,
        "source_matches": [{"id": row["id"], "match": row["match"]} for row in source_rows],
        "cad_kernel_import_attempted": False,
        "cad_kernel_loaded": False,
        "step_generation_attempted": False,
        "step_generation_executed": False,
        "expected_output_exists": output.is_file(),
        "forbidden_geometry_outputs_in_package": forbidden_outputs,
        "memory_measurement_attempted": False,
        "memory_gate_gib": 6.0,
        "memory_gate_passed": False,
        "fresh_run_authority_observed": False,
        "owner_override_observed": False,
        "snapshot_execution_attempted": False,
        "snapshot_execution_status": "SKIPPED_NO_STEP_GENERATED_NO_FRESH_RUN_AUTHORITY",
        "verdict": "SOURCE_ONLY_CONTRACT_READY__CAD_RUN_NOT_AUTHORIZED",
        "next_action": "OBTAIN_FRESH_RUN_AUTHORITY_AND_MEMORY_ADMISSION_BEFORE_CALLING_GEN_STEP",
        "parent_gate_credit": False,
        "next_stage_authorized": False,
        "production_complete": False,
        "release_credit": False,
    }


def load_negative_status() -> tuple[bool, dict | None]:
    if not NEGATIVE_RECEIPT.is_file():
        return False, None
    try:
        value = json.loads(NEGATIVE_RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, None
    passed = bool(
        value.get("schema") == "M4_L01_L02_GEOMETRY_NEGATIVE_CONTROL_RESULTS_V1"
        and value.get("expected_count") == NEGATIVE_CONTROL_COUNT
        and value.get("executed_count") == NEGATIVE_CONTROL_COUNT
        and value.get("passed_count") == NEGATIVE_CONTROL_COUNT
        and value.get("all_passed") is True
    )
    return passed, value


def build_gate(source_lock: dict, matrix: dict, preflight: dict) -> dict:
    negative_ok, negative = load_negative_status()
    configs = matrix["configurations"]
    d01 = D01_CONTRACT
    criteria = [
        ("G01_SOURCE_COUNT_EXACT_37", source_lock["source_count"] == 37),
        ("G02_ALL_SOURCE_HASHES_MATCH", source_lock["all_sources_match"] is True),
        ("G03_SOURCE_IDS_UNIQUE", source_lock["source_id_unique"] is True),
        ("G04_SOURCE_PATHS_UNIQUE", source_lock["source_path_unique"] is True),
        ("G05_NINE_CONFIGURATIONS_EXACT", len(configs) == 9),
        ("G06_CONFIGURATION_IDS_EXACT", [row["configuration_id"] for row in configs] == list(CONFIG_IDS)),
        ("G07_CONFIGURATION_CURRENT_STEP_COUNT_ZERO", matrix["configuration_current_step_buildable_count"] == 0),
        ("G08_CURRENT_COMPLETE_GEOMETRY_COUNT_ZERO", matrix["current_complete_integrated_geometry_count"] == 0),
        ("G09_ONE_NON_CURRENT_DIAGNOSTIC_RECIPE", matrix["source_only_diagnostic_recipe_count"] == 1),
        ("G10_D01_NOT_CONFIGURATION_CURRENT", d01["configuration_current"] is False and d01["configuration_credit"] is False),
        ("G11_C01_QHOME_Q0_CONFLICT_EXACT", configs[0]["authoritative_q6_rad"] == Q_HOME and d01["q6_rad"] == Q_ZERO),
        ("G12_D01_EXPECTED_403_SOLIDS", d01["expected"]["leaf_solid_count"] == 403),
        ("G13_D01_EXPECTED_3_GROUPS", d01["expected"]["intermediate_group_count"] == 3),
        ("G14_SELECTION_COUNTS_9_6_388", len(d01["master_retained"]) == 9 and len(d01["solar_selected"]) == 6 and d01["b601_source_shape_count"] == 388),
        ("G15_D01_BBOX_FROZEN_MM", d01["expected"]["bbox_S_mm"]["min"] == [-230.25, -715.4, -274.86072587989787] and d01["expected"]["bbox_S_mm"]["max"] == [488.533214, 715.4, 285.63229786565915]),
        ("G16_UNIT_POLICY_MM", d01["units"] == "mm" and FRAME_LEDGER["unit_policy"]["step_length"] == "mm"),
        ("G17_B601_PLACEMENT_EXACT", d01["placements"]["B601_FIXED_Q0_LOCAL_TO_S_ROWS_MM"] == T_S_B601_ARM_BASE_ROWS_MM),
        ("G18_TARGET_ATTACHMENTS_REMAIN_NULL", all(row["target_attachment_transform_S_rows"] is None for row in configs)),
        ("G19_HDRM_HARDWARE_REMAINS_NULL", d01["placements"]["ARM_HDRM"] is None and d01["placements"]["SOLAR_HDRM_HARDWARE"] is None),
        ("G20_C05_C09_Q_NOT_PROMOTED", all(row["authoritative_q6_rad"] is None for row in configs[4:])),
        ("G21_FAILURE_SOLAR_TRANSFORMS_NOT_INVENTED", all(row["solar_transform_status"] == "UNKNOWN_NO_CURRENT_INTEGRATED_GEOMETRY" for row in configs[1:4])),
        ("G22_COLLISION_AUTHORITY_FALSE", d01["collision_authority"] is False),
        ("G23_CONTACT_AUTHORITY_FALSE", d01["contact_authority"] is False),
        ("G24_MASS_AUTHORITY_FALSE", d01["mass_authority"] is False),
        ("G25_PRODUCTION_AND_RELEASE_FALSE", d01["production_authority"] is False and d01["release_credit"] is False),
        ("G26_FRESH_RUN_AUTHORITY_FALSE", preflight["fresh_run_authority_observed"] is False),
        ("G27_MEMORY_GATE_FALSE", preflight["memory_gate_passed"] is False and preflight["owner_override_observed"] is False),
        ("G28_NO_CAD_KERNEL_OR_STEP_RUN", preflight["cad_kernel_loaded"] is False and preflight["step_generation_executed"] is False and not preflight["forbidden_geometry_outputs_in_package"]),
        ("G29_SNAPSHOTS_UNEXECUTED", all(task["executed"] is False and task["artifact"] is None for task in SNAPSHOT_PLAN["tasks"])),
        ("G30_NEGATIVE_CONTROLS_PASS", negative_ok),
    ]
    if len(criteria) != GATE_CRITERION_COUNT:
        raise AssertionError("GATE_CRITERION_COUNT_DRIFT")
    check_rows = [{"id": gate_id, "pass": result} for gate_id, result in criteria]
    all_passed = all(row["pass"] for row in check_rows)
    artifact_names = [
        "SOURCE_AUTHORITY_LOCK_V1.json",
        "COMPONENT_GEOMETRY_CAPABILITY_AUDIT_V1.yaml",
        "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml",
        "FRAME_PLACEMENT_LEDGER_V1.yaml",
        "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml",
        "STEP_FIRST_BUILD_PLAN_V1.yaml",
        "SOURCE_ONLY_PREFLIGHT_V1.json",
        "SNAPSHOT_TASK_PLAN_V1.json",
    ]
    if negative_ok:
        artifact_names.append("NEGATIVE_CONTROL_RESULTS_V1.json")
    return {
        "schema": "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_GATE_V1",
        "gate_scope": "APPEND_ONLY_SOURCE_ONLY_EXECUTION_CONTRACT_CORRECTNESS",
        "gate_passed": all_passed,
        "passed_count": sum(row["pass"] for row in check_rows),
        "expected_count": GATE_CRITERION_COUNT,
        "checks": check_rows,
        "verdict": (
            "PASS_SOURCE_ONLY_MATRIX__0_OF_9_CONFIGURATION_CURRENT_STEP_BUILDABLE__D01_Q0_DIAGNOSTIC_RECIPE_READY__NO_CAD_RUN_OR_RELEASE_CREDIT"
            if all_passed
            else "HOLD_SOURCE_ONLY_MATRIX_PENDING_NEGATIVE_CONTROL_RECEIPT"
        ),
        "configuration_current_step_buildable_count": 0,
        "source_only_diagnostic_recipe_count": 1,
        "negative_control_receipt": {
            "present": negative is not None,
            "expected_count": NEGATIVE_CONTROL_COUNT,
            "all_passed": negative_ok,
        },
        "artifact_hashes": {
            name: sha256(PACKAGE / name) for name in artifact_names
        },
        "manifest": {
            "path": MANIFEST.name,
            "self_excluded": True,
            "hash_embedded_here": False,
        },
        "parent_gate_credit": False,
        "configuration_credit": False,
        "fresh_cad_run_authorized": False,
        "memory_gate_passed": False,
        "owner_override_present": False,
        "cad_kernel_loaded": False,
        "step_generation_executed": False,
        "collision_authority": False,
        "contact_authority": False,
        "mass_authority": False,
        "next_stage_authorized": False,
        "operational_authorized": False,
        "production_complete": False,
        "release_credit": False,
    }


def write_manifest() -> None:
    rows = []
    for relative_path, role in sorted(LOCAL_MANIFEST_ROLES.items()):
        path = PACKAGE / relative_path
        rows.append(
            {
                "path": relative_path,
                "bytes": path.stat().st_size if path.is_file() else "",
                "sha256": sha256(path) if path.is_file() else "",
                "role": role,
                "exists": str(path.is_file()).lower(),
            }
        )
    with MANIFEST.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "bytes", "sha256", "role", "exists"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build() -> dict:
    root = workspace_root()
    source_rows, all_match = verify_sources(root)
    if not all_match:
        failed = [row["id"] for row in source_rows if not row["match"]]
        raise RuntimeError(f"SOURCE_PIN_MISMATCH:{failed}")

    source_lock = build_source_lock(source_rows, all_match)
    matrix = build_matrix()
    preflight = build_preflight(source_rows, all_match)
    write_json(PACKAGE / "SOURCE_AUTHORITY_LOCK_V1.json", source_lock)
    write_json(PACKAGE / "COMPONENT_GEOMETRY_CAPABILITY_AUDIT_V1.yaml", COMPONENT_AUDIT)
    write_json(PACKAGE / "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml", matrix)
    write_json(PACKAGE / "FRAME_PLACEMENT_LEDGER_V1.yaml", FRAME_LEDGER)
    write_json(PACKAGE / "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", D01_CONTRACT)
    write_json(PACKAGE / "STEP_FIRST_BUILD_PLAN_V1.yaml", STEP_FIRST_PLAN)
    write_json(PACKAGE / "SOURCE_ONLY_PREFLIGHT_V1.json", preflight)
    write_json(PACKAGE / "SNAPSHOT_TASK_PLAN_V1.json", SNAPSHOT_PLAN)
    gate = build_gate(source_lock, matrix, preflight)
    write_json(GATE, gate)
    write_manifest()
    return gate


if __name__ == "__main__":
    result = build()
    print(
        json.dumps(
            {
                "gate_passed": result["gate_passed"],
                "passed_count": result["passed_count"],
                "expected_count": result["expected_count"],
                "verdict": result["verdict"],
            },
            sort_keys=True,
        )
    )

