#!/usr/bin/env python3
"""Compose a compact temporary route-audit receipt from executed probes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
V5_RECEIPT = (
    ROOT
    / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
    / "13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def main() -> None:
    v1 = load(HERE / "TEMP_B601_GRIPPER_2P_BREP_EXTRACTION_ROUTE_AUDIT_V1.json")
    palm = load(HERE / "TEMP_B601_GRIPPER_R1_PALM_REGISTRATION_PROBE_V1.json")
    binding = load(HERE / "TEMP_B601_GRIPPER_B50_V5_BINDING_UNIQUENESS_PROBE_V1.json")
    ocp_probe = load(HERE / "TEMP_OCP_STEPCONTROL_DETERMINISM_PROBE_V1.json")
    v5 = load(V5_RECEIPT)
    native = v5["frame_contracts"]["GRIPPER"]["witness"]["target_part_cold_reopens"]

    fingers = {}
    for side, native_key in (("left", "LEFT_FINGER"), ("right", "RIGHT_FINGER")):
        file_name = f"B601_GRIPPER_{side.upper()}_FINGER_GRIPPER_LINK_LOCAL_R1_SOURCE.step"
        a = HERE / "fp_a" / file_name
        b = HERE / "fp_b" / file_name
        source = v1["fingers"][side]["source"]
        mesh = v1["fingers"][side]["mesh_registration"]
        native_volume = float(native[native_key]["cold_brep"]["volume_mm3"])
        b50_volume = float(source["volume_mm3"])
        fingers[side] = {
            "candidate": file_fact(a),
            "fresh_process_repeat": file_fact(b),
            "fresh_process_bitwise_repeatable": sha256(a) == sha256(b),
            "solid_count": source["solid_count"],
            "face_count_after_step_reopen": 771,
            "ocp_compound_valid": source["ocp_compound_valid"],
            "all_solids_ocp_valid": source["all_solids_ocp_valid"],
            "b50_brep_volume_mm3": b50_volume,
            "native_v5_cold_brep_volume_mm3": native_volume,
            "b50_minus_native_v5_volume_mm3": b50_volume - native_volume,
            "b50_minus_native_v5_relative": (b50_volume - native_volume) / native_volume,
            "r1_stl_volume_mm3": mesh["frozen_r1_stl_abs_volume_mm3"],
            "b50_minus_r1_stl_volume_mm3": b50_volume - float(mesh["frozen_r1_stl_abs_volume_mm3"]),
            "r1_stl_reexport_byte_identical": mesh["fresh_stl_byte_identical_to_frozen_r1"],
            "brep_to_r1_stl_bbox_endpoint_max_abs_mm": mesh["brep_to_frozen_r1_bbox_endpoint_max_abs_mm"],
            "brep_to_m5_ply_bbox_endpoint_max_abs_mm": mesh["brep_to_m5_bbox_endpoint_max_abs_mm"],
            "r1_to_m5_vertex_registration_max_mm": max(
                mesh["fresh_to_m5_vertex_registration"]["maximum_mm"],
                mesh["m5_to_fresh_vertex_registration"]["maximum_mm"],
            ),
            "canonical_geometry_sha256": source["canonical_geometry_sha256"],
            "same_process_build123d_bitwise_repeatable": v1["fingers"][side][
                "bitwise_repeatable_across_distinct_directories_and_seconds"
            ],
            "same_process_ocp_stepcontrol_bitwise_repeatable": ocp_probe[side]["bitwise_repeatable_same_process"],
        }

    snapshots = [file_fact(path) for path in sorted((HERE / "snapshots").glob("*.png"))]
    report = {
        "schema": "TEMP_B601_GRIPPER_3PIECE_STEP_FIRST_ROUTE_AUDIT_V2",
        "status": "ROUTE_PROTOTYPE_PASS_WITH_REQUIRED_FRESH_PROCESS_EXPORT_AND_AUTHORITY_HOLDS",
        "authority": "TEMPORARY_READ_ONLY_ROUTE_AUDIT_NO_PROJECT_GATE_OR_OPERATIONAL_CREDIT",
        "recommended_route": {
            "palm": "REUSE_HASH_BOUND_EXISTING_R1_PALM_STEP_WITHOUT_REEXPORT",
            "fingers": "IMPORT_HASH_BOUND_B50_STEP__REUSE_FROZEN_R1_HUNGARIAN_BINDING__SELECT_24_ASSIGNED_SOLIDS_PER_SIDE__EXPORT_UNMODIFIED_COMPOUND",
            "forbidden_geometry_operations": ["FUSE", "HEAL", "OFFSET", "SIMPLIFY", "STL_TO_BREP_RECONSTRUCTION"],
            "frame": "gripper_link",
            "brep_units": "mm",
            "m5_surface_units": "m",
            "m5_comparison_boundary": "EXPLICIT_MULTIPLY_BY_1000_TO_MM",
            "export_rule": "ONE_FRESH_CPYTHON_PROCESS_PER_COMPLETE_PACKAGE_BUILD__FIXED_TIMESTAMP__FIXED_PALM_LEFT_RIGHT_ORDER",
        },
        "binding_uniqueness": {
            "selected_count": binding["selected_count"],
            "all_selected_unique_row_minimum": binding["all_selected_unique_row_minimum"],
            "all_selected_unique_column_minimum": binding["all_selected_unique_column_minimum"],
            "minimum_row_runner_up_margin": binding["minimum_row_runner_up_margin"],
            "minimum_column_runner_up_margin": binding["minimum_column_runner_up_margin"],
        },
        "palm": {
            "source": v1["inputs"]["palm_r1_step"],
            "solid_count": palm["shape_facts"]["solid_count"],
            "ocp_compound_valid": palm["shape_facts"]["ocp_compound_valid"],
            "volume_mm3": palm["shape_facts"]["volume_mm3"],
            "brep_to_r1_stl_bbox_endpoint_max_abs_mm": palm["registration"][
                "brep_to_frozen_r1_bbox_endpoint_max_abs_mm"
            ],
            "brep_to_m5_ply_bbox_endpoint_max_abs_mm": palm["registration"][
                "brep_to_m5_bbox_endpoint_max_abs_mm"
            ],
            "r1_to_m5_vertex_registration_max_mm": max(
                palm["registration"]["fresh_to_m5_vertex_registration"]["maximum_mm"],
                palm["registration"]["m5_to_fresh_vertex_registration"]["maximum_mm"],
            ),
        },
        "fingers": fingers,
        "m5_surface_limit": {
            "all_three_m5_ply_watertight": False,
            "finger_ply_volume_is_authoritative": False,
            "legal_comparisons": ["BBOX", "VERTEX_REGISTRATION", "FRAME", "UNITS"],
        },
        "visual_review": {
            "reviewed": True,
            "finding": "EACH_FINGER_IS_A_24_SOLID_MULTIBODY_COMPOUND_WITH_DISCONNECTED_JAW_RAIL_FASTENER_COMPONENTS__NOT_A_MONOLITHIC_SOLID",
            "motion_ownership_risk": "OWNER_MUST_CONFIRM_ALL_24_ASSIGNED_SOLIDS_MOVE_WITH_THE_CORRESPONDING_PRISMATIC_OBJECT_BEFORE_OPERATIONAL_PROMOTION",
            "snapshots": snapshots,
        },
        "open_risks": [
            "B50_EXTRACTION_IS_NOT_NATIVE_V5_SLDPRT_TOPOLOGY_EQUIVALENCE__B50_REOPEN_HAS_771_FACES_PER_FINGER_VS_697_NATIVE_V5_COLD_RECEIPT",
            "SAME_PROCESS_XCAF_AND_STEPCONTROL_EXPORTS_ARE_NOT_BYTE_REPEATABLE_DUE_GLOBAL_OCCURRENCE_PRODUCT_COUNTERS",
            "M5_PLY_IS_NON_WATERTIGHT_SCREENING_SURFACE_AND_CANNOT_SUPPLY_VOLUME_OR_CONTACT_AUTHORITY",
            "LEGACY_LINK6_LOCAL_LABEL_CONFLICTS_WITH_NUMERIC_GRIPPER_LINK_BINDING__USE_NUMERIC_GRIPPER_LINK_AUTHORITY",
            "PRISMATIC_STATE_MAP_AND_24_SOLID_MOTION_OWNERSHIP_REMAIN_UNRATIFIED_FOR_M01",
        ],
        "maximum_observed_brep_to_m5_bbox_error_mm": max(
            palm["registration"]["brep_to_m5_bbox_endpoint_max_abs_mm"],
            *(finger["brep_to_m5_ply_bbox_endpoint_max_abs_mm"] for finger in fingers.values()),
        ),
        "maximum_observed_r1_to_m5_vertex_registration_error_mm": max(
            palm["registration"]["fresh_to_m5_vertex_registration"]["maximum_mm"],
            palm["registration"]["m5_to_fresh_vertex_registration"]["maximum_mm"],
            *(finger["r1_to_m5_vertex_registration_max_mm"] for finger in fingers.values()),
        ),
        "implementation_ready": True,
        "operational_promotion_authorized": False,
        "system_pair_query_executed": False,
        "project_files_modified": False,
    }
    output = HERE / "TEMP_B601_GRIPPER_3PIECE_STEP_FIRST_ROUTE_AUDIT_V2.json"
    if output.exists():
        raise RuntimeError(f"refusing overwrite: {output}")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "status": report["status"]}, indent=2))


if __name__ == "__main__":
    main()
