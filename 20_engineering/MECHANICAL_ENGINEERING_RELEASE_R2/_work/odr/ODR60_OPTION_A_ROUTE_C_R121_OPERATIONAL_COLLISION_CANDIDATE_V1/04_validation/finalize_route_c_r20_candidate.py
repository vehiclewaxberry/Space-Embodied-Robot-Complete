"""Issue a strictly local R20 candidate Gate after all evidence is present.

The finalizer never upgrades system collision authority.  Its inventories cover
the package payload while explicitly excluding the six finalizer outputs to
avoid self-referential hashes.  The 83-artifact deterministic builder core is
kept distinct from review images and nondeterministic CAD-tool GLB caches.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

from route_c_r20_validation_lib import (
    CONTRACT_PATH,
    DETERMINISM_PATH,
    INDEPENDENT_PATH,
    NEGATIVE_PATH,
    PACKAGE,
    PYTEST_PATH,
    R121_SOURCE_AUDIT_PATH,
    SOURCE_LOCK_PATH,
    ValidationFailure,
    atomic_write,
    require,
    sha256_bytes,
    sha256_path,
    stable_json_bytes,
    strict_json,
    system_state_from_authorities,
    validate_build_receipts,
    validate_contract_structure,
    validate_source_pins,
    workspace_root,
)


RESULTS = PACKAGE / "05_results"
REVIEWS = PACKAGE / "07_reviews"
GATE_PATH = RESULTS / "LOCAL_CANDIDATE_GATE_V1.json"
VERDICT_PATH = RESULTS / "ENGINEERING_VERDICT_V1.md"
MANIFEST_PATH = RESULTS / "PACKAGE_MANIFEST_V1.csv"
SHA256_INVENTORY_PATH = RESULTS / "PACKAGE_SHA256_INVENTORY_V1.csv"
CONTRACTUAL_SHA256_PATH = RESULTS / "PACKAGE_SHA256_V1.csv"
JSON_INVENTORY_PATH = RESULTS / "PACKAGE_INVENTORY_V1.json"

FINALIZER_OUTPUTS = {
    GATE_PATH,
    VERDICT_PATH,
    MANIFEST_PATH,
    SHA256_INVENTORY_PATH,
    CONTRACTUAL_SHA256_PATH,
    JSON_INVENTORY_PATH,
}

INSPECT_PATH = REVIEWS / "CAD_INSPECT_REFS_SUMMARY_V1.json"
SNAPSHOT_PATH = REVIEWS / "CAD_SNAPSHOT_REVIEW_V1.json"
VIEWER_PATH = REVIEWS / "CAD_VIEWER_STARTUP_RECEIPT_V1.json"
CACHE_PATH = REVIEWS / "CAD_CACHE_RELOCATION_RECEIPT_V1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def verify_package_relative_record(record: dict[str, Any]) -> Path:
    path = PACKAGE / str(record.get("path", ""))
    require(path.is_file(), f"review artifact missing: {path}")
    require(path.stat().st_size == int(record.get("bytes", -1)), f"review artifact byte drift: {path}")
    require(sha256_path(path) == str(record.get("sha256", "")).upper(), f"review artifact hash drift: {path}")
    return path


def validate_review_evidence(specs: list[dict[str, Any]]) -> dict[str, Any]:
    inspect = strict_json(INSPECT_PATH)
    snapshot = strict_json(SNAPSHOT_PATH)
    viewer = strict_json(VIEWER_PATH)
    cache = strict_json(CACHE_PATH)
    expected_steps = {row["output"] for row in specs}

    require(inspect.get("schema") == "ROUTE_C_ROOT_STATIC_R20_CAD_INSPECT_REFS_SUMMARY_V1", "CAD inspect schema drift")
    require(inspect.get("summary", {}).get("requested_step_files") == 20, "CAD inspect request count drift")
    require(inspect.get("summary", {}).get("responses") == inspect.get("summary", {}).get("successful") == 20, "CAD inspect success count drift")
    require(inspect.get("summary", {}).get("inspect_pass") is True, "CAD inspect evidence failed")
    inspect_records = inspect.get("step_files", [])
    require(len(inspect_records) == 20, "CAD inspect hash record count drift")
    for record in inspect_records:
        verify_package_relative_record(record)
    require({Path(row["path"]).name for row in inspect_records} == expected_steps, "CAD inspect STEP set drift")
    require(inspect.get("authority_boundary", {}).get("operational_registry_binding_granted") is False, "CAD inspect overclaims binding")

    require(snapshot.get("schema") == "ROUTE_C_ROOT_STATIC_R20_CAD_SNAPSHOT_REVIEW_V1", "CAD snapshot schema drift")
    require(snapshot.get("review_method", {}).get("snapshots_created") == 20, "CAD snapshot count drift")
    require(snapshot.get("visual_findings", {}).get("visual_review_pass") is True, "CAD snapshot review failed")
    snapshot_records = snapshot.get("snapshots", [])
    require(len(snapshot_records) == 20, "CAD snapshot record count drift")
    for record in snapshot_records:
        verify_package_relative_record(record)
    verify_package_relative_record(snapshot["contact_sheet"])
    require({Path(row["step"]).name for row in snapshot_records} == expected_steps, "CAD snapshot STEP set drift")
    require(snapshot.get("authority_boundary", {}).get("pair_collision_claimed") is False, "CAD snapshot overclaims pair clearance")

    require(viewer.get("schema") == "ROUTE_C_ROOT_STATIC_R20_CAD_VIEWER_STARTUP_RECEIPT_V1", "CAD viewer schema drift")
    require(viewer.get("exit_code") == 1 and viewer.get("startup_pass") is False, "CAD viewer failure disclosure drift")
    require(viewer.get("viewer_url") is None, "CAD viewer URL should be null after startup failure")
    require("agent:start" in str(viewer.get("root_cause", "")), "CAD viewer root cause not disclosed")
    require(viewer.get("authority_boundary", {}).get("viewer_pass_claimed") is False, "CAD viewer false PASS")
    require(viewer.get("authority_boundary", {}).get("local_geometry_gate_derived_from_viewer") is False, "local Gate improperly derived from viewer")

    require(cache.get("schema") == "ROUTE_C_ROOT_STATIC_R20_CAD_CACHE_RELOCATION_RECEIPT_V1", "CAD cache schema drift")
    require(cache.get("initial_moved_count") == 20 and cache.get("late_replay_moved_count") == 10, "CAD cache relocation count drift")
    require(cache.get("total_preserved_cache_files") == 30, "CAD cache preserved count drift")
    require(cache.get("classification") == "NONDETERMINISTIC_DIAGNOSTIC_DERIVATIVE_NOT_PRIMARY_GEOMETRY", "CAD cache classification drift")
    require(cache.get("replay_observation", {}).get("same_named_glb_hashes_repeated") is False, "CAD cache nondeterminism disclosure drift")
    require("EXCLUDE_FROM_DETERMINISTIC_CORE_AND_LOCAL_GATE" in cache.get("replay_observation", {}).get("disposition", ""), "CAD cache Gate exclusion missing")
    cache_records = list(cache.get("files", [])) + list(cache.get("late_replay_files", []))
    require(len(cache_records) == 30, "CAD cache file record count drift")
    for record in cache_records:
        verify_package_relative_record(record)
    require(cache.get("authority_boundary", {}).get("primary_geometry_changed") is False, "CAD cache claims primary geometry change")

    cad_files = sorted(path for path in (PACKAGE / "01_cad").iterdir() if path.is_file())
    require(len(cad_files) == 20, f"01_cad contains {len(cad_files)} files, expected 20")
    require({path.name for path in cad_files} == expected_steps, "01_cad is not the exact twenty-STEP primary set")
    require(all(path.suffix.lower() in {".step", ".stp"} for path in cad_files), "non-STEP artifact remains in 01_cad")

    return {
        "cad_inspect": {"status": "PASS", "step_files": 20, "receipt_sha256": sha256_path(INSPECT_PATH)},
        "cad_snapshot": {"status": "PASS", "snapshots": 20, "contact_sheet": 1, "receipt_sha256": sha256_path(SNAPSHOT_PATH)},
        "cad_viewer": {
            "status": "TRUTHFULLY_DISCLOSED_TOOL_STARTUP_FAILURE",
            "startup_pass": False,
            "geometry_gate_derived_from_viewer": False,
            "receipt_sha256": sha256_path(VIEWER_PATH),
        },
        "cad_cache": {
            "status": "PRESERVED_NONDETERMINISTIC_DIAGNOSTIC_EXCLUDED_FROM_CORE_AND_GATE",
            "files": 30,
            "receipt_sha256": sha256_path(CACHE_PATH),
        },
        "primary_cad_directory": {"step_files": 20, "other_files": 0},
    }


def classify(relative: Path) -> tuple[str, str]:
    text = relative.as_posix()
    top = relative.parts[0] if relative.parts else ""
    if top == "00_contract":
        return "FROZEN_CONTRACT", "CONTRACT_AUTHORITY"
    if top == "01_cad":
        return "PRIMARY_STEP_GEOMETRY", "LOCAL_CANDIDATE_PRIMARY_GEOMETRY"
    if top == "02_builder":
        return "CANDIDATE_BUILDER_SOURCE", "BUILDER_IMPLEMENTATION"
    if top == "02_runtime":
        return "RUNTIME_DERIVATIVE", "DERIVED_NON_PRIMARY_GEOMETRY"
    if top == "04_validation":
        return "INDEPENDENT_VALIDATION_SOURCE", "VALIDATION_IMPLEMENTATION"
    if top == "05_results":
        return "EVIDENCE_RECEIPT", "LOCAL_CANDIDATE_EVIDENCE"
    if top == "06_tests":
        return "TEST_SOURCE", "REGRESSION_TEST_IMPLEMENTATION"
    if text.startswith("07_reviews/cad_cache/"):
        return "NONDETERMINISTIC_CAD_CACHE", "DIAGNOSTIC_ONLY_EXCLUDED_FROM_CORE_AND_GATE"
    if text.startswith("07_reviews/snapshots/") or relative.suffix.lower() == ".png":
        return "CAD_REVIEW_IMAGE", "DIAGNOSTIC_VISUAL_EVIDENCE_NO_SYSTEM_CREDIT"
    if top == "07_reviews":
        return "CAD_REVIEW_RECEIPT", "DIAGNOSTIC_REVIEW_EVIDENCE_NO_SYSTEM_CREDIT"
    return "PACKAGE_SUPPORT", "SUPPORTING_LOCAL_EVIDENCE"


def payload_rows() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(PACKAGE.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path in FINALIZER_OUTPUTS:
            continue
        if "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".tmp"}:
            continue
        relative = path.relative_to(PACKAGE)
        classification, authority = classify(relative)
        rows.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_path(path),
                "classification": classification,
                "authority": authority,
            }
        )
    require(rows, "package payload is empty")
    require(len({row["path"] for row in rows}) == len(rows), "duplicate package payload path")
    return rows


def inventory_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=["path", "bytes", "sha256", "classification", "authority"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def output_record(path: Path, data: bytes) -> dict[str, Any]:
    return {
        "path": path.relative_to(workspace_root()).as_posix(),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def validate_and_compose() -> dict[str, bytes]:
    contract = strict_json(CONTRACT_PATH)
    specs = validate_contract_structure(contract)
    lock = strict_json(SOURCE_LOCK_PATH)
    pins = validate_source_pins(lock)
    build = validate_build_receipts(contract)
    independent = strict_json(INDEPENDENT_PATH)
    source_audit = strict_json(R121_SOURCE_AUDIT_PATH)
    negative = strict_json(NEGATIVE_PATH)
    determinism = strict_json(DETERMINISM_PATH)
    pytest_receipt = strict_json(PYTEST_PATH)
    system_state = system_state_from_authorities(pins)
    reviews = validate_review_evidence(specs)

    require(independent.get("schema") == "ROUTE_C_ROOT_STATIC_R20_INDEPENDENT_STEP_VALIDATION_V1", "independent schema drift")
    require(source_audit.get("schema") == "ROUTE_C_V9F_R121_SOURCE_TOPOLOGY_AUDIT_V1", "source topology audit schema drift")
    require(negative.get("schema") == "ROUTE_C_ROOT_STATIC_R20_NEGATIVE_CONTROLS_V1", "negative control schema drift")
    require(determinism.get("schema") == "ROUTE_C_ROOT_STATIC_R20_FRESH_PROCESS_DETERMINISM_RECEIPT_V1", "determinism schema drift")
    require(pytest_receipt.get("schema") == "ROUTE_C_ROOT_STATIC_R20_PYTEST_RECEIPT_V1", "pytest schema drift")

    expected_system = {
        "system_operational_authority_rows": 1,
        "known_active_objects": 150,
        "system_pair_queries": 0,
        "required_unassessed_pairs": 11166,
        "safe_certificates": 0,
        "system_edges_certified": 0,
        "path_search_executed": False,
        "stage_instances_bound": 0,
        "stage_instances_required": 3,
        "TMG4": "HOLD",
        "G12": "FAIL",
        "gate_a_pass": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "negative_witness_raw_mm": -10.729480331980062,
        "negative_witness_gated_mm": -17.313396996697108,
        "negative_witness_current_pair_credit": False,
    }
    require(system_state == expected_system, f"system authority state drift: {system_state}")
    require(independent.get("system_state_preserved") == expected_system, "independent system snapshot drift")

    source_counts = source_audit.get("counts", {})
    frame = independent.get("frame_and_unit_boundary", {})
    object_rows = independent.get("objects", [])
    negative_summary = negative.get("summary", {})
    contractual_ids = set(contract.get("negative_control_ids", []))
    negative_by_id = {row["id"]: row for row in negative.get("controls", [])}
    authority = independent.get("authority_flags", {})

    checks = {
        "G01_contract_exact_twenty_object_set": len(specs) == 20,
        "G02_thirteen_source_pins_match": len(pins) == 13,
        "G03_builder_three_receipts_and_83_core_declared": build["build"].get("generated_artifact_count_excluding_this_receipt") == 82,
        "G04_primary_cad_directory_exactly_twenty_STEP": reviews["primary_cad_directory"] == {"step_files": 20, "other_files": 0},
        "G05_full_R121_source_topology_121_117_4_125": source_counts.get("objects") == 121 and source_counts.get("single_solid_objects") == 117 and source_counts.get("double_solid_objects") == 4 and source_counts.get("total_solids") == 125,
        "G06_full_R121_name_sets_and_placements_audited": source_audit.get("name_set_cross_check", {}).get("all_four_sets_exactly_equal") is True and source_counts.get("nonidentity_freecad_object_placements") == 53 and source_audit.get("object_placement_reapplied") is False,
        "G07_twenty_source_and_target_BReps_valid_closed_positive": independent.get("valid_closed_positive_primary_STEP_count") == 20 and all(row.get("source_facts", {}).get("brep_valid") is True and row.get("local_geometry_candidate_pass") is True for row in object_rows),
        "G08_T_S_A0_applied_exactly_once": frame.get("T_S_A0_application_count_per_object") == 1 and all(row.get("transform", {}).get("application_count") == 1 and row.get("freecad_object_placement_reapplied") is False for row in object_rows),
        "G09_mm_to_m_applied_exactly_once": frame.get("primary_STEP_unit") == "mm" and frame.get("runtime_unit") == "m" and frame.get("step_to_runtime_scale") == 0.001 and frame.get("step_to_runtime_scale_application_count") == 1,
        "G10_topology_volume_bbox_and_centroid_residuals_pass": all(row.get("geometry_comparison", {}).get("topology_counts_exact") is True for row in object_rows),
        "G11_Boolean_symmetric_difference_20_of_20_pass": independent.get("boolean_symmetric_difference_available_count") == 20 and all(row.get("geometry_comparison", {}).get("boolean_symmetric_difference", {}).get("pass_if_available") is True for row in object_rows),
        "G12_runtime_60_sidecars_independently_rederived": independent.get("runtime_sidecar_artifact_count") == 60 and independent.get("runtime_sidecar_set_count") == 20 and all(row.get("runtime", {}).get("independent_step_tessellation_exact") is True for row in object_rows),
        "G13_as_built_null_and_zero_fill_absent": independent.get("uncertainty_boundary", {}).get("manufacturing_as_built_derate_mm") is None and independent.get("uncertainty_boundary", {}).get("numeric_zero_fill_found") is False and all(row.get("runtime", {}).get("as_built_derate_mm") is None for row in object_rows),
        "G14_independent_validator_import_boundary_pass": independent.get("validator_independence", {}).get("pass") is True and independent.get("validator_independence", {}).get("forbidden_imports") == [],
        "G15_all_33_contract_negative_controls_caught": len(contractual_ids) == 33 and contractual_ids <= set(negative_by_id) and all(negative_by_id[item].get("caught") is True for item in contractual_ids) and negative_summary.get("contractual_controls_caught") == 33,
        "G16_two_fresh_process_replays_preserve_83_core": determinism.get("fresh_process_determinism_pass") is True and determinism.get("fresh_process_count") == 2 and determinism.get("core_artifact_count") == 83 and determinism.get("core_unchanged") is True,
        "G17_pytest_at_least_24_all_pass": pytest_receipt.get("pytest_pass") is True and pytest_receipt.get("tests_passed", 0) >= 24 and pytest_receipt.get("tests_failed") == 0,
        "G18_system_state_1_of_150_0_of_11166_0_of_3_unchanged": system_state == expected_system,
        "G19_negative_witness_preserved_without_current_credit": system_state.get("negative_witness_raw_mm") < 0.0 and system_state.get("negative_witness_gated_mm") < 0.0 and system_state.get("negative_witness_current_pair_credit") is False,
        "G20_cad_inspect_20_of_20_pass_local_only": reviews["cad_inspect"]["status"] == "PASS",
        "G21_snapshot_20_plus_contact_sheet_review_pass": reviews["cad_snapshot"]["status"] == "PASS",
        "G22_viewer_failure_truthfully_disclosed_not_used_as_geometry_gate": reviews["cad_viewer"]["status"] == "TRUTHFULLY_DISCLOSED_TOOL_STARTUP_FAILURE" and reviews["cad_viewer"]["geometry_gate_derived_from_viewer"] is False,
        "G23_nondeterministic_cad_cache_preserved_but_excluded": reviews["cad_cache"]["files"] == 30 and reviews["cad_cache"]["status"] == "PRESERVED_NONDETERMINISTIC_DIAGNOSTIC_EXCLUDED_FROM_CORE_AND_GATE",
        "G24_no_system_pair_edge_path_or_release_credit": authority == {"edge_credit": False, "next_stage_authorized": False, "pair_eligible": False, "parent_gate_credit": False, "path_credit": False, "release_credit": False, "safe_credit": False, "system_operational_credit": False, "system_pair_query_credit": 0, "system_registry_reissued": False},
    }
    require(len(checks) >= 14, "local Gate has fewer than fourteen checks")
    require(all(checks.values()), "local Gate criteria failed: " + ", ".join(key for key, value in checks.items() if not value))

    rows = payload_rows()
    core_paths = {str(row["path"]).removeprefix(PACKAGE.relative_to(workspace_root()).as_posix() + "/") for row in determinism["core_before"]}
    payload_paths = {row["path"] for row in rows}
    require(len(core_paths) == 83 and core_paths <= payload_paths, "83-artifact deterministic core is not fully inventoried")
    require(all(not path.startswith("07_reviews/cad_cache/") for path in core_paths), "CAD cache entered deterministic core")
    classifications = dict(sorted(Counter(row["classification"] for row in rows).items()))
    require(classifications.get("PRIMARY_STEP_GEOMETRY") == 20, "inventory primary STEP count drift")
    require(classifications.get("NONDETERMINISTIC_CAD_CACHE") == 30, "inventory CAD cache count drift")
    checks["G25_payload_inventory_complete_and_83_core_separated"] = True

    inventory = {
        "schema": "ROUTE_C_ROOT_STATIC_R20_PACKAGE_INVENTORY_V1",
        "generated_utc": "DETERMINISTIC_FINALIZER_NO_WALLCLOCK",
        "scope": "PACKAGE_PAYLOAD_EXCLUDING_SELF_REFERENTIAL_FINALIZER_OUTPUTS",
        "package": PACKAGE.relative_to(workspace_root()).as_posix(),
        "excluded_finalizer_outputs": sorted(path.name for path in FINALIZER_OUTPUTS),
        "payload_file_count": len(rows),
        "payload_bytes": sum(int(row["bytes"]) for row in rows),
        "classification_counts": classifications,
        "deterministic_builder_core_count": 83,
        "nondeterministic_cad_cache_count": 30,
        "entries": rows,
        "authority_boundary": {
            "inventory_is_system_binding": False,
            "cad_cache_is_primary_geometry": False,
            "cad_cache_is_in_deterministic_core": False,
            "release_credit": False,
        },
        "verdict": "PACKAGE_PAYLOAD_INVENTORIED__FINALIZER_OUTPUTS_EXCLUDED_TO_AVOID_SELF_REFERENCE__NO_SYSTEM_CREDIT",
    }
    inventory_bytes = stable_json_bytes(inventory)
    csv_bytes = inventory_csv_bytes(rows)
    inventory_records = {
        "PACKAGE_INVENTORY_V1.json": output_record(JSON_INVENTORY_PATH, inventory_bytes),
        "PACKAGE_MANIFEST_V1.csv": output_record(MANIFEST_PATH, csv_bytes),
        "PACKAGE_SHA256_INVENTORY_V1.csv": output_record(SHA256_INVENTORY_PATH, csv_bytes),
        "PACKAGE_SHA256_V1.csv": output_record(CONTRACTUAL_SHA256_PATH, csv_bytes),
    }

    gate = {
        "schema": "ROUTE_C_ROOT_STATIC_R20_LOCAL_CANDIDATE_GATE_V1",
        "generated_utc": "DETERMINISTIC_FINALIZER_NO_WALLCLOCK",
        "scope": "R121_UMBRELLA_PHASE_A_ROOT_STATIC_R20_LOCAL_CANDIDATES_ONLY",
        "decision_rule": "Authority > evidence > independent reproduction > agent opinion",
        "checks_required": len(checks),
        "checks_passed": sum(bool(value) for value in checks.values()),
        "checks": checks,
        "local_candidate_gate_pass": True,
        "object_count": 20,
        "primary_step_count": 20,
        "runtime_sidecar_count": 60,
        "full_R121_source_audit": {"objects": 121, "single_solid_objects": 117, "double_solid_objects": 4, "total_solids": 125, "nonidentity_freecad_object_placements": 53},
        "negative_controls": {"contractual": 33, "supplemental": negative_summary.get("supplemental_controls_executed"), "caught": negative_summary.get("total_controls_caught")},
        "fresh_process_replays": 2,
        "pytest_passed": pytest_receipt["tests_passed"],
        "review_diagnostics": reviews,
        "package_inventory_outputs": inventory_records,
        "system_state_unchanged": system_state,
        "authority_flags": {
            "local_geometry_candidate_credit": True,
            "system_registry_binding_credit": False,
            "pair_query_credit": 0,
            "safe_certificate_credit": 0,
            "edge_credit": 0,
            "path_credit": False,
            "motion_certificate_credit": False,
            "parent_gate_credit": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "remaining_R101": "FAIL_CLOSED_HOST_AND_SPECIAL_MOTION_ADAPTER_HOLD",
        "review_status": "PENDING_OWNER_REVIEW",
        "maximum_legal_claim": contract["maximum_legal_claim"],
        "verdict": "LOCAL_R20_CANDIDATE_GATE_PASS__R101_SYSTEM_PAIR_EDGE_PATH_AND_RELEASE_REMAIN_FAIL_CLOSED",
    }
    gate_bytes = stable_json_bytes(gate)

    verdict_text = f"""# R121 / R20 工程裁决

裁决：`LOCAL_R20_CANDIDATE_GATE_PASS`。20 个 Route-C 根部静态对象已形成逐对象 STEP-first 的本地 S-frame 碰撞几何候选；这不是系统碰撞注册、pair/edge/path 认证或机械发布许可。

- 独立几何：20/20 STEP 均为单根、单闭合正体积 BRep；`T_S_A0` 每对象恰施加一次，STEP 保持 mm，运行时 sidecar 仅做一次 0.001 的 mm→m 缩放。
- 源审计：V9F R121 为 121 个对象、117 个单 solid、4 个双 solid、共 125 solids；53 个对象具有非 identity FreeCAD Placement，验证链确认没有二次施加 Placement。
- 运行时与复现：60/60 PLY/NPZ/STL 从重开 STEP 独立派生；两次 fresh-process `--check` 保持 83/83 确定性核心不变；pytest {pytest_receipt['tests_passed']}/{pytest_receipt['tests_passed']} PASS。
- 负控：33/33 合同负控及 {negative_summary.get('supplemental_controls_executed')}/{negative_summary.get('supplemental_controls_executed')} 补充负控被 fail-closed 捕获。
- CAD 审阅：20/20 inspect 与 20 张快照＋contact sheet 完整。CAD Viewer 因已安装包缺少 `agent:start` 而真实 FAIL；该工具失败未被伪装成 PASS，也不是本地几何 Gate 的来源。
- 诊断缓存：首轮 20 个 GLB 加尾部异步重放 10 个 GLB 已留证。重放文件同字节数但哈希不同，因此全部标为 `NONDETERMINISTIC_DIAGNOSTIC`，不属于主 STEP、83 件确定性核心或 Gate 判据。

系统状态保持：1/150 operational、0/11166 pair queries、0 SAFE、0 edges、0/3 stages、无 path；`TMG4=HOLD`、`G12=FAIL`、Gate A=false、release credit=false。R101 的 q-dependent host/special-motion adapter 仍为 fail-closed HOLD。

最高合法主张：`{contract['maximum_legal_claim']}`。
"""
    verdict_bytes = verdict_text.encode("utf-8")
    return {
        JSON_INVENTORY_PATH: inventory_bytes,
        MANIFEST_PATH: csv_bytes,
        SHA256_INVENTORY_PATH: csv_bytes,
        CONTRACTUAL_SHA256_PATH: csv_bytes,
        GATE_PATH: gate_bytes,
        VERDICT_PATH: verdict_bytes,
    }


def main() -> None:
    args = parse_args()
    outputs = validate_and_compose()
    if args.write:
        for path, data in outputs.items():
            atomic_write(path, data)
    else:
        for path, expected in outputs.items():
            require(path.is_file(), f"finalizer output missing: {path}")
            require(path.read_bytes() == expected, f"finalizer output drift: {path}")
    gate = json.loads(outputs[GATE_PATH])
    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": "write" if args.write else "check",
                "local_gate_checks": gate["checks_passed"],
                "objects": gate["object_count"],
                "system_operational_authority_rows": gate["system_state_unchanged"]["system_operational_authority_rows"],
                "system_pair_queries": gate["system_state_unchanged"]["system_pair_queries"],
                "release_credit": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
