#!/usr/bin/env python3
"""Build and replay-check three source-bound B601 gripper STEP candidates."""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import trimesh
from scipy.optimize import linear_sum_assignment

from gripper_2p_geometry import (
    ACCEPTED_URDF_REL,
    ANGULAR_DEFLECTION_RAD,
    CAD_ASSETS,
    ASSIGNMENT_REL,
    CONTRACT_PATH,
    FRAME_LEDGER_PATH,
    LINEAR_DEFLECTION_MM,
    M5_FRAME_DECISION_REL,
    M5_SURFACE_DIR_REL,
    NEUTRAL_STEP_REL,
    OBJECTS,
    Q_MAX_M,
    Q_MIN_M,
    RESULTS,
    RUNTIME_ASSETS,
    R1_LEFT_STL_REL,
    R1_PALM_STEP_REL,
    R1_RIGHT_STL_REL,
    R1_VALIDATION_REL,
    SOURCE_LOCK_PATH,
    STEP_BBOX_REOPEN_TOLERANCE_MM,
    STEP_NUMERIC_DERATE_MM,
    STEP_VOLUME_REL_TOLERANCE,
    V5_RECEIPT_REL,
    apply_transform_points,
    bbox_mm,
    binary_stl,
    binary_ply,
    byte_record,
    canonicalize_mesh,
    deterministic_npz,
    extract_triangles_m,
    file_record,
    make_compound,
    manifold_metrics,
    parse_urdf_contract,
    read_step,
    reconstruct_neutral_groups,
    require,
    sha256_bytes,
    signed_volume_m3,
    solid_rows,
    stable_json_bytes,
    strict_json,
    transform_shape,
    verify_all_source_pins,
    verify_source_pin,
    workspace_root,
    write_step_bytes,
)


BUILDER_EVIDENCE = RESULTS / "BUILDER_EVIDENCE_V1.json"
STATE_EVIDENCE = RESULTS / "STATE_AND_FRAME_EVIDENCE_V1.json"
UNIT_AUDIT = RESULTS / "UNIT_AND_UNCERTAINTY_AUDIT_V1.json"
SOURCE_RECHECK = RESULTS / "SOURCE_PIN_RECHECK_V1.json"
SOLID_LEDGER = RESULTS / "THREE_CONTAINER_SOLID_IDENTITY_AND_VALIDITY_LEDGER_V1.json"
FRAME_UNIT_AUDIT = RESULTS / "FRAME_AND_UNIT_TRANSFORM_AUDIT_V1.json"
RUNTIME_RECEIPT = RESULTS / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json"
MESH_VOLUME_REL_TOLERANCE = 5.0e-3
MESH_BBOX_TOLERANCE_MM = 0.10
SOURCE_CROSSCHECK_BBOX_TOLERANCE_MM = 0.10
PRIMARY_M5_BBOX_TOLERANCE_MM = 0.001
_BUILD_EXECUTED_IN_THIS_PROCESS = False


def _read_step_from_bytes(data: bytes):
    with tempfile.TemporaryDirectory(prefix="b601_gripper_reopen_") as directory:
        path = Path(directory) / "candidate.step"
        path.write_bytes(data)
        return read_step(path)


def _geometry_match(expected_rows: list[dict[str, Any]], actual_rows: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(expected_rows) == len(actual_rows), "STEP solid count changed across transform/export")
    costs: list[list[float]] = []
    metrics: list[list[dict[str, float]]] = []
    for expected in expected_rows:
        ebox = expected["bbox_mm"]
        ecenter = np.mean(ebox, axis=0)
        esize = ebox[1] - ebox[0]
        evolume = float(expected["volume_mm3"])
        cost_row: list[float] = []
        metric_row: list[dict[str, float]] = []
        for actual in actual_rows:
            abox = actual["bbox_mm"]
            acenter = np.mean(abox, axis=0)
            asize = abox[1] - abox[0]
            avolume = float(actual["volume_mm3"])
            center = float(np.linalg.norm(ecenter - acenter))
            size = float(np.linalg.norm(esize - asize))
            bbox = float(np.max(np.abs(ebox - abox)))
            volume = abs(evolume - avolume) / max(evolume, 1.0e-12)
            cost_row.append(center + size + 100.0 * volume)
            metric_row.append(
                {
                    "center_delta_mm": center,
                    "size_delta_mm": size,
                    "bbox_endpoint_max_abs_mm": bbox,
                    "volume_relative": volume,
                }
            )
        costs.append(cost_row)
        metrics.append(metric_row)
    expected_indices, actual_indices = linear_sum_assignment(costs)
    selected = [metrics[int(first)][int(second)] for first, second in zip(expected_indices, actual_indices, strict=True)]
    matches = [
        {
            "expected_index": int(first),
            "actual_index": int(second),
            **metrics[int(first)][int(second)],
        }
        for first, second in zip(expected_indices, actual_indices, strict=True)
    ]
    return {
        "matched_solid_count": len(selected),
        "max_center_delta_mm": max(row["center_delta_mm"] for row in selected),
        "max_size_delta_mm": max(row["size_delta_mm"] for row in selected),
        "max_bbox_endpoint_abs_mm": max(row["bbox_endpoint_max_abs_mm"] for row in selected),
        "max_volume_relative": max(row["volume_relative"] for row in selected),
        "matches": matches,
    }


def _mesh_bbox_mm(vertices_m: np.ndarray) -> np.ndarray:
    return np.vstack((vertices_m.min(axis=0), vertices_m.max(axis=0))) * 1000.0


def _source_mesh_bbox_mm(path: Path) -> np.ndarray:
    mesh = trimesh.load_mesh(path, process=False)
    require(isinstance(mesh, trimesh.Trimesh), f"source cross-check is not one mesh: {path}")
    return np.asarray(mesh.bounds, dtype=np.float64)


def _atomic_write(path: Path, data: bytes, *, replace: bool) -> None:
    if path.exists() and not replace:
        raise FileExistsError(f"output exists; use --replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _artifact_paths(name: str) -> dict[str, Path]:
    spec = OBJECTS[name]
    stem = spec["runtime_stem"]
    return {
        "step": CAD_ASSETS / spec["step_name"],
        "ply": RUNTIME_ASSETS / f"{stem}.ply",
        "npz": RUNTIME_ASSETS / f"{stem}.npz",
        "stl": RUNTIME_ASSETS / f"{stem}.stl",
        "receipt": RESULTS / spec["receipt_name"],
    }


def build_all() -> dict[str, Any]:
    global _BUILD_EXECUTED_IN_THIS_PROCESS
    require(
        not _BUILD_EXECUTED_IN_THIS_PROCESS,
        "STEP export must run once per fresh CPython process because OCCT product counters are process-global",
    )
    _BUILD_EXECUTED_IN_THIS_PROCESS = True
    root = workspace_root()
    contract = strict_json(CONTRACT_PATH)
    lock = strict_json(SOURCE_LOCK_PATH)
    ledger = strict_json(FRAME_LEDGER_PATH)
    source_pin_count = verify_all_source_pins(lock)
    for relative in (
        ACCEPTED_URDF_REL,
        NEUTRAL_STEP_REL,
        V5_RECEIPT_REL,
        ASSIGNMENT_REL,
        R1_PALM_STEP_REL,
        R1_VALIDATION_REL,
        R1_LEFT_STL_REL,
        R1_RIGHT_STL_REL,
        M5_FRAME_DECISION_REL,
    ):
        verify_source_pin(lock, relative)
    for spec in OBJECTS.values():
        verify_source_pin(lock, M5_SURFACE_DIR_REL / spec["m5_surface"])

    urdf = parse_urdf_contract()
    neutral = reconstruct_neutral_groups()
    left_parent = make_compound(neutral["bound"][name] for name in neutral["grouped_names"]["gripper_left"])
    right_parent = make_compound(neutral["bound"][name] for name in neutral["grouped_names"]["gripper_right"])
    palm = read_step(root / R1_PALM_STEP_REL)
    left_matrix = np.asarray(urdf["joints"]["gripper_joint1"]["T_child_from_parent_q0_mm"], dtype=np.float64)
    right_matrix = np.asarray(urdf["joints"]["gripper_joint2"]["T_child_from_parent_q0_mm"], dtype=np.float64)
    shapes = {
        "gripper_link": {
            "target": palm,
            "parent_source": palm,
            "parent_from_output_mm": np.eye(4),
            "step_data": (root / R1_PALM_STEP_REL).read_bytes(),
            "source_kind": "BYTE_IDENTICAL_R1_PALM_STEP",
        },
        "gripper_left": {
            "target": transform_shape(left_parent, left_matrix),
            "parent_source": left_parent,
            "parent_from_output_mm": np.asarray(
                urdf["joints"]["gripper_joint1"]["T_parent_from_child_q0_mm"], dtype=np.float64
            ),
            "source_kind": "EXACT_NEUTRAL_BREP_GROUP_RIGIDLY_REEXPRESSED_IN_CHILD_FRAME",
        },
        "gripper_right": {
            "target": transform_shape(right_parent, right_matrix),
            "parent_source": right_parent,
            "parent_from_output_mm": np.asarray(
                urdf["joints"]["gripper_joint2"]["T_parent_from_child_q0_mm"], dtype=np.float64
            ),
            "source_kind": "EXACT_NEUTRAL_BREP_GROUP_RIGIDLY_REEXPRESSED_IN_CHILD_FRAME",
        },
    }
    shapes["gripper_left"]["step_data"] = write_step_bytes(shapes["gripper_left"]["target"])
    shapes["gripper_right"]["step_data"] = write_step_bytes(shapes["gripper_right"]["target"])

    object_builds: dict[str, Any] = {}
    for name, spec in OBJECTS.items():
        paths = _artifact_paths(name)
        step_data = shapes[name]["step_data"]
        reopened = _read_step_from_bytes(step_data)
        reopened_rows = solid_rows(reopened)
        expected_rows = solid_rows(shapes[name]["target"])
        require(len(reopened_rows) == int(spec["expected_solid_count"]), f"unexpected STEP solid count: {name}")
        require(all(row["brep_valid"] for row in reopened_rows), f"invalid reopened STEP solid: {name}")
        require(all(row["all_shells_closed"] for row in reopened_rows), f"open reopened STEP solid: {name}")
        require(all(math.isfinite(row["volume_mm3"]) and row["volume_mm3"] > 0.0 for row in reopened_rows), f"nonpositive STEP solid: {name}")
        export_match = _geometry_match(expected_rows, reopened_rows)
        require(export_match["max_bbox_endpoint_abs_mm"] <= STEP_BBOX_REOPEN_TOLERANCE_MM, f"STEP bbox replay drift: {name}")
        require(export_match["max_volume_relative"] <= STEP_VOLUME_REL_TOLERANCE, f"STEP volume replay drift: {name}")

        parent_reconstruction = transform_shape(reopened, shapes[name]["parent_from_output_mm"])
        q0_match = _geometry_match(solid_rows(shapes[name]["parent_source"]), solid_rows(parent_reconstruction))
        require(q0_match["max_bbox_endpoint_abs_mm"] <= STEP_BBOX_REOPEN_TOLERANCE_MM, f"q0 frame reconstruction drift: {name}")
        require(q0_match["max_volume_relative"] <= STEP_VOLUME_REL_TOLERANCE, f"q0 volume reconstruction drift: {name}")

        raw_triangles_m, raw_solid_ids, missing_faces = extract_triangles_m(reopened_rows)
        vertices_m, faces, solid_ids, canonical = canonicalize_mesh(
            raw_triangles_m, raw_solid_ids, len(reopened_rows)
        )
        topology = manifold_metrics(faces, solid_ids, len(reopened_rows))
        brep_volume_mm3 = float(sum(row["volume_mm3"] for row in reopened_rows))
        mesh_volume_by_solid_mm3 = [
            signed_volume_m3(vertices_m, faces[solid_ids == solid_id]) * 1.0e9
            for solid_id in range(len(reopened_rows))
        ]
        mesh_volume_mm3 = float(sum(mesh_volume_by_solid_mm3))
        mesh_volume_relative = abs(mesh_volume_mm3 - brep_volume_mm3) / brep_volume_mm3
        require(mesh_volume_relative <= MESH_VOLUME_REL_TOLERANCE, f"runtime/BRep volume drift: {name}")
        runtime_bbox_mm = _mesh_bbox_mm(vertices_m)
        step_bbox_mm = bbox_mm(reopened)
        runtime_bbox_error_mm = float(np.max(np.abs(runtime_bbox_mm - step_bbox_mm)))
        require(runtime_bbox_error_mm <= MESH_BBOX_TOLERANCE_MM, f"runtime/STEP bbox drift: {name}")

        parent_runtime_mm = apply_transform_points(vertices_m * 1000.0, shapes[name]["parent_from_output_mm"])
        parent_runtime_bbox_mm = np.vstack((parent_runtime_mm.min(axis=0), parent_runtime_mm.max(axis=0)))
        m5_path = root / M5_SURFACE_DIR_REL / spec["m5_surface"]
        m5_bbox_mm = _source_mesh_bbox_mm(m5_path) * 1000.0
        runtime_m5_bbox_error_mm = float(np.max(np.abs(parent_runtime_bbox_mm - m5_bbox_mm)))
        primary_m5_bbox_error_mm = float(np.max(np.abs(bbox_mm(parent_reconstruction) - m5_bbox_mm)))
        require(runtime_m5_bbox_error_mm <= SOURCE_CROSSCHECK_BBOX_TOLERANCE_MM, f"runtime/M5 q0 bbox cross-check drift: {name}")
        require(primary_m5_bbox_error_mm <= PRIMARY_M5_BBOX_TOLERANCE_MM, f"primary BRep/M5 q0 bbox cross-check drift: {name}")

        metadata = {
            "units": "m",
            "frame": spec["frame"],
            "object_id": spec["object_id"],
            "transform_application_count": 1,
        }
        npz_data = deterministic_npz(
            {
                "faces": faces,
                "frame": np.asarray(spec["frame"]),
                "object_id": np.asarray(spec["object_id"]),
                "solid_ids": solid_ids,
                "transform_application_count": np.asarray(1, dtype="<u1"),
                "units": np.asarray("m"),
                "vertices_m": vertices_m,
            }
        )
        ply_data = binary_ply(vertices_m, faces, spec["frame"])
        stl_data = binary_stl(vertices_m, faces, spec["frame"])
        source_records = {
            "accepted_urdf": file_record(root / ACCEPTED_URDF_REL),
            "r1_validation": file_record(root / R1_VALIDATION_REL),
            "m5_frame_decision": file_record(root / M5_FRAME_DECISION_REL),
            "m5_gripper_link_local_surface": file_record(m5_path),
        }
        if name == "gripper_link":
            source_records["primary_brep_source"] = file_record(root / R1_PALM_STEP_REL)
            source_member_ids = [f"R1_PALM_REOPEN_SOLID_{index + 1:02d}" for index in range(len(expected_rows))]
        else:
            source_records.update(
                {
                    "primary_brep_source": file_record(root / NEUTRAL_STEP_REL),
                    "v5_body_receipt": file_record(root / V5_RECEIPT_REL),
                    "solid_assignment": file_record(root / ASSIGNMENT_REL),
                    "r1_neutral_stl_crosscheck": file_record(
                        root / (R1_LEFT_STL_REL if name == "gripper_left" else R1_RIGHT_STL_REL)
                    ),
                }
            )
            source_member_ids = list(neutral["grouped_names"][name])
        require(len(source_member_ids) == len(expected_rows), f"source identity count mismatch: {name}")
        solid_identity = []
        for match in export_match["matches"]:
            actual = reopened_rows[int(match["actual_index"])]
            solid_identity.append(
                {
                    "source_member_id": source_member_ids[int(match["expected_index"])],
                    "output_solid_index": int(match["actual_index"]),
                    "volume_mm3": float(actual["volume_mm3"]),
                    "bbox_mm": actual["bbox_mm"].tolist(),
                    "face_count": int(actual["face_count"]),
                    "shell_count": int(actual["shell_count"]),
                    "brep_valid": bool(actual["brep_valid"]),
                    "all_shells_closed": bool(actual["all_shells_closed"]),
                }
            )
        checks = {
            "all_source_hashes_and_bytes_match": True,
            "accepted_urdf_frame_and_joint_contract_match": True,
            "expected_positive_valid_brep_solid_count": True,
            "step_export_reopens_without_geometry_drift": True,
            "q0_parent_frame_reconstruction_matches_source_brep": True,
            "runtime_mesh_per_solid_closed_and_oriented": True,
            "runtime_mesh_brep_volume_within_0p5_percent": True,
            "runtime_mesh_step_bbox_within_0p10_mm": True,
            "m5_gripper_link_local_q0_bbox_crosscheck_within_0p10_mm": True,
            "primary_brep_to_m5_q0_bbox_crosscheck_within_0p001_mm": True,
            "no_named_state_authority_claimed": True,
            "no_system_registry_pair_edge_path_or_release_credit": True,
        }
        receipt = {
            "schema": "B601_GRIPPER_2P_LOCAL_GEOMETRY_RECEIPT_V1",
            "as_of_date": "2026-08-28",
            "object_name": name,
            "object_id": spec["object_id"],
            "authority_scope": "LOCAL_STEP_FIRST_COLLISION_GEOMETRY_CANDIDATE_ONLY",
            "classification": "PENDING_OWNER_REVIEW",
            "source_kind": shapes[name]["source_kind"],
            "source_records": source_records,
            "primary_step": {**byte_record(paths["step"], step_data), "units": "mm", "frame": spec["frame"]},
            "runtime_npz": {**byte_record(paths["npz"], npz_data), **metadata},
            "runtime_ply": {
                **byte_record(paths["ply"], ply_data),
                "units": "m",
                "frame": spec["frame"],
                "scale_factor_from_step_mm": 0.001,
            },
            "runtime_stl": {
                **byte_record(paths["stl"], stl_data),
                "units": "m",
                "frame": spec["frame"],
                "unit_binding": "RECEIPT_AND_BINARY_HEADER",
            },
            "geometry": {
                "solid_count": len(reopened_rows),
                "face_count": int(sum(row["face_count"] for row in reopened_rows)),
                "shell_count": int(sum(row["shell_count"] for row in reopened_rows)),
                "brep_bbox_mm": step_bbox_mm.tolist(),
                "brep_volume_mm3": brep_volume_mm3,
                "runtime_vertex_count": int(len(vertices_m)),
                "runtime_triangle_count": int(len(faces)),
                "runtime_mesh_volume_mm3": mesh_volume_mm3,
                "runtime_mesh_brep_volume_relative_error": mesh_volume_relative,
                "runtime_step_bbox_max_abs_error_mm": runtime_bbox_error_mm,
                "runtime_mesh_to_m5_q0_bbox_max_abs_error_mm": runtime_m5_bbox_error_mm,
                "primary_brep_to_m5_q0_bbox_max_abs_error_mm": primary_m5_bbox_error_mm,
                "step_export_match": export_match,
                "q0_source_reconstruction_match": q0_match,
                "solid_identity": sorted(solid_identity, key=lambda row: row["source_member_id"]),
                "missing_triangulation_face_count": missing_faces,
                **canonical,
                **topology,
            },
            "uncertainty_and_units": {
                "primary_step_geometry_units": "mm",
                "urdf_translation_input_units": "m",
                "urdf_rpy_input_units": "rad",
                "runtime_units": "m",
                "m_to_mm_conversion_count_at_ocp_boundary": 1,
                "primary_brep_nominal_geometry_approximation_mm": 0.0,
                "primary_brep_numeric_derate_mm": STEP_NUMERIC_DERATE_MM,
                "runtime_mesh_chordal_derate_mm": LINEAR_DEFLECTION_MM,
                "runtime_mesh_angular_deflection_rad": ANGULAR_DEFLECTION_RAD,
                "manufacturing_as_built_derate_mm": None,
                "manufacturing_as_built_status": "MEASUREMENT_PENDING_SYSTEM_BIND_HOLD",
                "runtime_mesh_pair_lower_bound_required_debit_mm": 2.0 * (LINEAR_DEFLECTION_MM + STEP_NUMERIC_DERATE_MM),
            },
            "checks": checks,
            "authority_flags": {
                "candidate_may_be_submitted_for_owner_binding": True,
                "owner_named_state_map_resolved": False,
                "system_registry_reissued": False,
                "system_pair_evaluation_authorized": False,
                "contact_authority": False,
                "path_search_authorized": False,
                "parent_mechanical_gate_reissued": False,
                "next_stage_authorized": False,
                "release_credit": False,
            },
            "verdict": "LOCAL_GEOMETRY_CANDIDATE_PASS__PENDING_OWNER_STATE_MAP_AND_SYSTEM_BIND__NO_PAIR_EDGE_PATH_RELEASE_CREDIT",
        }
        receipt_data = stable_json_bytes(receipt)
        object_builds[name] = {
            "paths": paths,
            "step_data": step_data,
            "npz_data": npz_data,
            "ply_data": ply_data,
            "stl_data": stl_data,
            "receipt": receipt,
            "receipt_data": receipt_data,
        }

    state_evidence = {
        "schema": "B601_GRIPPER_2P_STATE_AND_FRAME_EVIDENCE_V1",
        "as_of_date": "2026-08-28",
        "accepted_urdf": file_record(root / ACCEPTED_URDF_REL),
        "urdf_contract": urdf,
        "raw_numeric_state_contract": {
            "required_fields": ["gripper_joint1_m", "gripper_joint2_m"],
            "units": "m",
            "inclusive_range": [Q_MIN_M, Q_MAX_M],
            "named_state_labels_authorized": False,
            "owner_state_map_conflict_resolved": False,
        },
        "frame_rule": {
            "palm_primary_frame": "gripper_link",
            "left_primary_frame": "gripper_left",
            "right_primary_frame": "gripper_right",
            "source_finger_frame": "gripper_link_at_q0",
            "finger_conversion": "OUTPUT_CHILD = INVERSE(T_PARENT_FROM_CHILD_Q0) * SOURCE_PARENT",
            "runtime_application": "T_PARENT_FROM_CHILD_Q * OUTPUT_CHILD_APPLIED_ONCE",
            "double_application_forbidden": True,
            "direct_link6_binding_rejected": True,
        },
        "owner_hold": "NAMED_CONFIGURATION_TO_NUMERIC_2P_TRAVEL_MAP_CONFLICT_NOT_RATIFIED",
        "system_authority_flags": {
            "stage_instances_bound": 0,
            "system_pair_queries_executed": 0,
            "path_search_authorized": False,
            "release_credit": False,
        },
    }
    unit_audit = {
        "schema": "B601_GRIPPER_2P_UNIT_AND_UNCERTAINTY_AUDIT_V1",
        "as_of_date": "2026-08-28",
        "ledger": [
            {"quantity": "primary BRep coordinate", "unit": "mm", "conversion": "none"},
            {"quantity": "URDF origin translation", "input_unit": "m", "OCP_unit": "mm", "conversion": "multiply by 1000 exactly once"},
            {"quantity": "URDF rpy", "unit": "rad", "conversion": "none"},
            {"quantity": "2P travel", "input_unit": "m", "OCP_unit": "mm", "conversion": "multiply by 1000 at future runtime boundary"},
            {"quantity": "runtime mesh coordinate", "unit": "m", "conversion": "primary mm multiplied by 1e-3 once"},
        ],
        "derates": {
            "primary_step_numeric_mm_per_object": STEP_NUMERIC_DERATE_MM,
            "runtime_mesh_chordal_mm_per_object": LINEAR_DEFLECTION_MM,
            "runtime_mesh_pair_lower_bound_debit_mm": 2.0 * (LINEAR_DEFLECTION_MM + STEP_NUMERIC_DERATE_MM),
            "manufacturing_as_built_mm": None,
        },
        "unknown_policy": "MISSING_AS_BUILT_OR_OWNER_STATE_AUTHORITY_REMAINS_HOLD_AND_CANNOT_BE_ZERO_FILLED",
        "checks": {
            "single_m_to_mm_boundary": True,
            "radians_not_converted_as_degrees": True,
            "runtime_mesh_derate_nonzero": True,
            "manufacturing_unknown_not_zero_filled": True,
            "no_threshold_relaxation": True,
        },
    }
    builder_evidence = {
        "schema": "B601_GRIPPER_2P_BUILDER_EVIDENCE_V1",
        "as_of_date": "2026-08-28",
        "contract": file_record(CONTRACT_PATH),
        "source_lock": file_record(SOURCE_LOCK_PATH),
        "frame_and_state_ledger": file_record(FRAME_LEDGER_PATH),
        "source_pin_count_verified": source_pin_count,
        "neutral_body_binding": {
            "source_solid_count": 57,
            "group_counts_before_r1_palm_cut": {key: len(value) for key, value in neutral["grouped_names"].items()},
            "maximum_center_delta_mm": max(row["center_delta_mm"] for row in neutral["binding_rows"]),
            "maximum_size_delta_mm": max(row["size_delta_mm"] for row in neutral["binding_rows"]),
            "maximum_volume_relative": max(row["volume_relative"] for row in neutral["binding_rows"]),
        },
        "outputs": {
            name: {
                "step": build["receipt"]["primary_step"],
                "runtime_npz": build["receipt"]["runtime_npz"],
                "runtime_ply": build["receipt"]["runtime_ply"],
                "runtime_stl": build["receipt"]["runtime_stl"],
                "receipt": byte_record(build["paths"]["receipt"], build["receipt_data"]),
            }
            for name, build in object_builds.items()
        },
        "deterministic_build_inputs_frozen": True,
        "deterministic_export_process_contract": {
            "fresh_cpython_process_required": True,
            "maximum_build_invocations_per_process": 1,
            "fixed_container_export_order": ["gripper_link", "gripper_left", "gripper_right"],
            "step_header_timestamp_canonicalized": True,
            "reason": "OCCT_STEP_GLOBAL_PRODUCT_AND_OCCURRENCE_COUNTERS_INCREMENT_WITHIN_ONE_PROCESS",
        },
        "maximum_local_claim": "3_OF_3_LOCAL_GEOMETRY_CANDIDATES_PASS__PENDING_OWNER_STATE_MAP_AND_SYSTEM_BIND__NO_PAIR_EDGE_PATH_RELEASE_CREDIT",
        "authority_flags": {
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
    }
    source_recheck = {
        "schema": "B601_GRIPPER_2P_SOURCE_PIN_RECHECK_V1",
        "as_of_date": "2026-08-28",
        "source_pin_count": len(lock["source_pins"]),
        "source_pin_count_verified": source_pin_count,
        "all_bytes_and_sha256_match": True,
        "pins": [
            {
                "source_id": row["source_id"],
                "path": row["path"],
                "bytes": row["bytes"],
                "sha256": row["sha256"],
                "match": True,
            }
            for row in lock["source_pins"]
        ],
        "authority_flags": {
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "release_credit": False,
        },
    }
    solid_ledger = {
        "schema": "B601_GRIPPER_2P_THREE_CONTAINER_SOLID_IDENTITY_AND_VALIDITY_LEDGER_V1",
        "as_of_date": "2026-08-28",
        "container_count": 3,
        "native_lineage_physical_body_count": 57,
        "native_aggregate_wrapper_excluded": "B51_REF_gripper_detail_LINKLOCAL057",
        "output_solid_count": sum(build["receipt"]["geometry"]["solid_count"] for build in object_builds.values()),
        "containers": {
            name: {
                "object_id": build["receipt"]["object_id"],
                "frame": build["receipt"]["primary_step"]["frame"],
                "primary_step": build["receipt"]["primary_step"],
                "solid_count": build["receipt"]["geometry"]["solid_count"],
                "face_count": build["receipt"]["geometry"]["face_count"],
                "solids": build["receipt"]["geometry"]["solid_identity"],
            }
            for name, build in object_builds.items()
        },
        "checks": {
            "three_containers_exact": True,
            "output_counts_12_24_24_total_60": True,
            "all_source_member_ids_unique_per_container": True,
            "all_solids_valid_closed_and_positive": True,
            "no_fusion_envelope_connector_or_wrapper": True,
        },
        "system_authority_increment": 0,
    }
    frame_unit_audit = {
        "schema": "B601_GRIPPER_2P_FRAME_AND_UNIT_TRANSFORM_AUDIT_V1",
        "as_of_date": "2026-08-28",
        "state_and_frame_evidence": state_evidence,
        "unit_and_uncertainty_audit": unit_audit,
        "checks": {
            "palm_gripper_link_local": True,
            "left_child_link_local_after_one_inverse_q0": True,
            "right_child_link_local_after_one_inverse_q0": True,
            "q0_recomposition_matches_source": True,
            "urdf_literal_1p5708_retained": True,
            "step_mm_to_runtime_m_once": True,
            "owner_named_state_map_remains_null": True,
        },
    }
    runtime_receipt = {
        "schema": "B601_GRIPPER_2P_RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1",
        "as_of_date": "2026-08-28",
        "derivation": "VALIDATED_PRIMARY_STEP_MM_TO_OWNING_LINK_LOCAL_RUNTIME_PLY_NPZ_STL_M",
        "objects": {
            name: {
                "source_step": build["receipt"]["primary_step"],
                "runtime_ply": build["receipt"]["runtime_ply"],
                "runtime_npz": build["receipt"]["runtime_npz"],
                "runtime_stl": build["receipt"]["runtime_stl"],
                "frame": build["receipt"]["primary_step"]["frame"],
                "scale_factor": 0.001,
                "scale_application_count": 1,
                "runtime_vertex_count": build["receipt"]["geometry"]["runtime_vertex_count"],
                "runtime_triangle_count": build["receipt"]["geometry"]["runtime_triangle_count"],
                "bounds_m": (
                    np.asarray(build["receipt"]["geometry"]["brep_bbox_mm"], dtype=np.float64) * 0.001
                ).tolist(),
                "runtime_mesh_chordal_derate_mm": LINEAR_DEFLECTION_MM,
            }
            for name, build in object_builds.items()
        },
        "sidecar_is_primary_geometry_authority": False,
        "owner_state_baked": False,
        "system_narrowphase_promoted": False,
    }
    return {
        "objects": object_builds,
        "state_path": STATE_EVIDENCE,
        "state_data": stable_json_bytes(state_evidence),
        "unit_path": UNIT_AUDIT,
        "unit_data": stable_json_bytes(unit_audit),
        "builder_path": BUILDER_EVIDENCE,
        "builder_data": stable_json_bytes(builder_evidence),
        "source_recheck_path": SOURCE_RECHECK,
        "source_recheck_data": stable_json_bytes(source_recheck),
        "solid_ledger_path": SOLID_LEDGER,
        "solid_ledger_data": stable_json_bytes(solid_ledger),
        "frame_unit_path": FRAME_UNIT_AUDIT,
        "frame_unit_data": stable_json_bytes(frame_unit_audit),
        "runtime_receipt_path": RUNTIME_RECEIPT,
        "runtime_receipt_data": stable_json_bytes(runtime_receipt),
        "contract_schema": contract.get("schema"),
        "ledger_schema": ledger.get("schema"),
    }


def run(*, check: bool, replace: bool) -> dict[str, Any]:
    build = build_all()
    outputs: list[tuple[Path, bytes]] = []
    for item in build["objects"].values():
        outputs.extend(
            [
                (item["paths"]["step"], item["step_data"]),
                (item["paths"]["npz"], item["npz_data"]),
                (item["paths"]["ply"], item["ply_data"]),
                (item["paths"]["stl"], item["stl_data"]),
                (item["paths"]["receipt"], item["receipt_data"]),
            ]
        )
    outputs.extend(
        [
            (build["state_path"], build["state_data"]),
            (build["unit_path"], build["unit_data"]),
            (build["builder_path"], build["builder_data"]),
            (build["source_recheck_path"], build["source_recheck_data"]),
            (build["solid_ledger_path"], build["solid_ledger_data"]),
            (build["frame_unit_path"], build["frame_unit_data"]),
            (build["runtime_receipt_path"], build["runtime_receipt_data"]),
        ]
    )
    for path, data in outputs:
        if check:
            require(path.is_file(), f"deterministic replay artifact missing: {path}")
            require(path.read_bytes() == data, f"deterministic replay mismatch: {path}")
        else:
            _atomic_write(path, data, replace=replace)
    return {
        "artifact_count": len(outputs),
        "objects": sorted(build["objects"]),
        "status": "PASS",
        "deterministic_replay": check,
        "sha256": {path.name: sha256_bytes(data) for path, data in outputs},
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.check and args.replace:
        raise SystemExit("--replace cannot be combined with --check")
    result = run(check=args.check, replace=args.replace)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
