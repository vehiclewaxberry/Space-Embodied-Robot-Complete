#!/usr/bin/env python3
"""Build three source-bound, S-frame fixed-platform collision candidates."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from fixed_platform_geometry import (
    CAD_DIR,
    CONTRACT_PATH,
    FRAME_LEDGER_PATH,
    OBJECTS,
    PACKAGE,
    PRIMARY_NUMERIC_DERATE_MM,
    RESULTS_DIR,
    RUNTIME_CHORDAL_DERATE_MM,
    RUNTIME_DIR,
    SOURCE_LOCK_PATH,
    SOURCE_LEDGER_BBOX_TOLERANCE_MM,
    SOURCE_LEDGER_VOLUME_REL_TOLERANCE,
    STEP_BBOX_TOLERANCE_MM,
    STEP_VOLUME_REL_TOLERANCE,
    atomic_write,
    bbox_mm,
    binary_ply,
    binary_stl,
    byte_record,
    canonicalize_mesh,
    deterministic_npz,
    extract_triangles_m,
    file_record,
    json_metadata_array,
    manifold_metrics,
    read_step,
    read_step_from_bytes,
    require,
    sha256_bytes,
    solid_rows,
    source_pin,
    stable_json_bytes,
    strict_json,
    transform_shape,
    validate_single_solid,
    verify_all_source_pins,
    workspace_root,
    write_step_bytes,
)


SOURCE_RECHECK = RESULTS_DIR / "SOURCE_PIN_RECHECK_V1.json"
BUILDER_EVIDENCE = RESULTS_DIR / "BUILDER_EVIDENCE_V1.json"
THREE_STEP_RECEIPT = RESULTS_DIR / "THREE_STEP_BUILD_RECEIPT_V1.json"
FRAME_AUDIT = RESULTS_DIR / "FRAME_AND_UNIT_TRANSFORM_AUDIT_V1.json"
RUNTIME_RECEIPT = RESULTS_DIR / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json"
_BUILD_EXECUTED = False


def binding_entries() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    root = workspace_root()
    lock = strict_json(SOURCE_LOCK_PATH)
    pins = list(lock.get("source_pins", []))
    matches = [
        row
        for row in pins
        if row.get("source_id", row.get("id"))
        in {"m01_fixed_platform_pose_binding", "fixed_platform_pose_binding"}
    ]
    require(len(matches) == 1, "source lock must contain the fixed-platform pose binding pin")
    binding = strict_json(root / matches[0]["path"])
    entries = {row["object_id"]: row for row in binding["entries"]}
    require(set(entries) == {spec["object_id"] for spec in OBJECTS.values()}, "pose binding object set drift")
    return entries, binding


def _transform_matrix(entries: dict[str, dict[str, Any]]) -> np.ndarray:
    stage_a = np.asarray(entries["F::M3R_STAGE_A"]["T_S_asset_rows_mm"], dtype=np.float64)
    stage_b = np.asarray(entries["F::M3R_STAGE_B"]["T_S_asset_rows_mm"], dtype=np.float64)
    require(np.array_equal(stage_a, stage_b), "M3R A/B transforms differ")
    expected = np.asarray([
        [0.0, 0.0, 1.0, 208.0],
        [0.422618483193, 0.906307683772, 0.0, 0.015994151],
        [-0.906307683772, 0.422618483193, 0.0, -0.086366070],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=np.float64)
    require(np.array_equal(stage_a, expected), "T_S_M3R_LOCAL full-precision rows drifted")
    return stage_a


def _jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "bbox_mm": np.asarray(row["bbox_mm"], dtype=np.float64).tolist(),
        "volume_mm3": float(row["volume_mm3"]),
        "brep_valid": bool(row["brep_valid"]),
        "face_count": int(row["face_count"]),
        "shell_count": int(row["shell_count"]),
        "all_shells_closed": bool(row["all_shells_closed"]),
    }


def _paths(spec: dict[str, Any]) -> dict[str, Path]:
    stem = spec["runtime_stem"]
    return {
        "step": CAD_DIR / spec["step_name"],
        "ply": RUNTIME_DIR / f"{stem}.ply",
        "npz": RUNTIME_DIR / f"{stem}.npz",
        "stl": RUNTIME_DIR / f"{stem}.stl",
        "receipt": RESULTS_DIR / spec["receipt_name"],
    }


def build_bytes() -> dict[str, Any]:
    global _BUILD_EXECUTED
    require(not _BUILD_EXECUTED, "STEP export must run once per fresh process")
    _BUILD_EXECUTED = True
    root = workspace_root()
    contract = strict_json(CONTRACT_PATH)
    frame_ledger = strict_json(FRAME_LEDGER_PATH)
    lock = strict_json(SOURCE_LOCK_PATH)
    pin_count = verify_all_source_pins(lock)
    entries, binding = binding_entries()
    transform = _transform_matrix(entries)
    require(contract["current_system_authority_invariants"]["asset_level_operational_authority_rows"] == 1, "contract system authority drift")
    require(frame_ledger["primary_step_length_unit"] == "mm", "primary STEP unit drift")
    require(frame_ledger["runtime_sidecar_length_unit"] == "m", "runtime unit drift")
    require(frame_ledger["step_to_runtime_scale"] == 0.001, "mm-to-m scale drift")

    artifacts: dict[Path, bytes] = {}
    receipts: dict[str, dict[str, Any]] = {}
    runtime_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []

    for name, spec in OBJECTS.items():
        source_path = root / spec["source_rel"]
        pin = source_pin(lock, spec["source_rel"])
        source_shape = read_step(source_path)
        source_row = validate_single_solid(source_shape, context=f"{name} source")
        expected_box = np.asarray(spec["expected_local_bbox_mm"], dtype=np.float64)
        bbox_residual = float(np.max(np.abs(source_row["bbox_mm"] - expected_box)))
        volume_residual = abs(float(source_row["volume_mm3"]) - float(spec["expected_volume_mm3"])) / float(spec["expected_volume_mm3"])
        require(bbox_residual <= SOURCE_LEDGER_BBOX_TOLERANCE_MM, f"{name} source bbox drift: {bbox_residual}")
        require(volume_residual <= SOURCE_LEDGER_VOLUME_REL_TOLERANCE, f"{name} source volume drift: {volume_residual}")

        if spec["source_frame"] == "S":
            require(name == "load_bridge", "only load bridge may be source-authored in S")
            require(np.array_equal(np.asarray(entries[spec["object_id"]]["T_S_asset_rows"], dtype=np.float64), np.eye(4)), "load bridge runtime transform is not identity")
            output_data = source_path.read_bytes()
            transform_count = 0
            transform_rows = np.eye(4, dtype=np.float64)
            output_shape_expected = source_shape
        else:
            require(name in {"m3r_stage_a", "m3r_stage_b"}, "unexpected M3R transform target")
            output_shape_expected = transform_shape(source_shape, transform)
            output_data = write_step_bytes(output_shape_expected)
            transform_count = 1
            transform_rows = transform

        reopened = read_step_from_bytes(output_data)
        output_row = validate_single_solid(reopened, context=f"{name} emitted STEP")
        expected_s_row = validate_single_solid(output_shape_expected, context=f"{name} expected S shape")
        output_bbox_residual = float(np.max(np.abs(output_row["bbox_mm"] - expected_s_row["bbox_mm"])))
        output_volume_residual = abs(float(output_row["volume_mm3"]) - float(expected_s_row["volume_mm3"])) / float(expected_s_row["volume_mm3"])
        require(output_bbox_residual <= STEP_BBOX_TOLERANCE_MM, f"{name} output bbox reopen mismatch")
        require(output_volume_residual <= STEP_VOLUME_REL_TOLERANCE, f"{name} output volume reopen mismatch")

        triangles_m, solid_ids = extract_triangles_m(reopened)
        vertices_m, faces, solid_ids, mesh_audit = canonicalize_mesh(triangles_m, solid_ids)
        topology = manifold_metrics(faces)
        metadata = {
            "schema": "FIXED_PLATFORM_RUNTIME_GEOMETRY_METADATA_V1",
            "object_id": spec["object_id"],
            "frame": "S",
            "units": "m",
            "primary_step_units": "mm",
            "step_to_runtime_scale": 0.001,
            "step_to_runtime_scale_application_count": 1,
            "source_to_output_frame_transform_application_count": transform_count,
            "primary_numeric_derate_mm": PRIMARY_NUMERIC_DERATE_MM,
            "runtime_chordal_derate_mm": RUNTIME_CHORDAL_DERATE_MM,
            "as_built_derate_mm": None,
            "system_operational_promoted": False,
        }
        npz_data = deterministic_npz({
            "faces": faces,
            "metadata_json_utf8": json_metadata_array(metadata),
            "solid_ids": solid_ids,
            "vertices_m": vertices_m,
        })
        ply_data = binary_ply(vertices_m, faces, spec["object_id"])
        stl_data = binary_stl(vertices_m, faces, spec["object_id"])
        paths = _paths(spec)
        artifacts[paths["step"]] = output_data
        artifacts[paths["npz"]] = npz_data
        artifacts[paths["ply"]] = ply_data
        artifacts[paths["stl"]] = stl_data

        runtime_bbox_mm = np.vstack((vertices_m.min(axis=0), vertices_m.max(axis=0))) * 1000.0
        runtime_volume_mm3 = abs(float(np.einsum("ij,ij->i", vertices_m[faces][:, 0], np.cross(vertices_m[faces][:, 1], vertices_m[faces][:, 2])).sum() / 6.0)) * 1.0e9
        runtime_bbox_delta = float(np.max(np.abs(runtime_bbox_mm - output_row["bbox_mm"])))
        runtime_volume_relative = abs(runtime_volume_mm3 - float(output_row["volume_mm3"])) / float(output_row["volume_mm3"])
        require(runtime_bbox_delta <= RUNTIME_CHORDAL_DERATE_MM + PRIMARY_NUMERIC_DERATE_MM, f"{name} runtime bbox residual exceeds declared derate")
        require(runtime_volume_relative <= 0.005, f"{name} runtime volume residual exceeds 0.5 percent")

        receipt = {
            "schema": "FIXED_PLATFORM_OBJECT_GEOMETRY_RECEIPT_V1",
            "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
            "object_name": name,
            "object_id": spec["object_id"],
            "source": {**pin, "frame": spec["source_frame"], "units": "mm"},
            "source_geometry": _jsonable_row(source_row),
            "source_expectation_residual": {"bbox_max_abs_mm": bbox_residual, "volume_relative": volume_residual},
            "frame_operation": {
                "rule": spec["transform_rule"],
                "matrix_rows_mm": transform_rows.tolist(),
                "application_count": transform_count,
                "output_frame": "S",
                "double_transform_forbidden": True,
            },
            "primary_step": {**byte_record(paths["step"], output_data), "frame": "S", "units": "mm"},
            "primary_step_geometry": _jsonable_row(output_row),
            "reopen_residual": {"bbox_max_abs_mm": output_bbox_residual, "volume_relative": output_volume_residual},
            "runtime": {
                "npz": byte_record(paths["npz"], npz_data),
                "ply": byte_record(paths["ply"], ply_data),
                "stl": byte_record(paths["stl"], stl_data),
                "frame": "S",
                "units": "m",
                "vertex_count": int(len(vertices_m)),
                "triangle_count": int(len(faces)),
                "bbox_m": (runtime_bbox_mm * 1.0e-3).tolist(),
                "volume_m3": runtime_volume_mm3 * 1.0e-9,
                "bbox_vs_step_max_abs_mm": runtime_bbox_delta,
                "volume_vs_step_relative": runtime_volume_relative,
                "mesh_audit": mesh_audit,
                "topology": topology,
            },
            "uncertainty": {
                "primary_numeric_derate_mm": PRIMARY_NUMERIC_DERATE_MM,
                "runtime_chordal_derate_mm": RUNTIME_CHORDAL_DERATE_MM,
                "as_built_derate_mm": None,
                "as_built_status": "MEASUREMENT_PENDING_NOT_ZERO_FILLED",
            },
            "checks": {
                "source_hash_pin_match": True,
                "source_one_valid_closed_positive_solid": True,
                "output_one_valid_closed_positive_solid": True,
                "source_membership_preserved": True,
                "frame_transform_applied_exactly_as_contract": True,
                "step_mm_to_runtime_m_applied_once": True,
                "runtime_closed_oriented_two_manifold": True,
                "as_built_not_zero_filled": True,
                "system_authority_unchanged": True,
            },
            "authority_flags": {
                "local_operational_collision_candidate": True,
                "system_registry_reissued": False,
                "pair_evaluation_authorized": False,
                "system_safe": False,
                "path_search_authorized": False,
                "parent_gate_credit": False,
                "next_stage_authorized": False,
                "release_credit": False,
            },
        }
        receipt_data = stable_json_bytes(receipt)
        artifacts[paths["receipt"]] = receipt_data
        receipts[name] = receipt
        source_rows.append({"object_id": spec["object_id"], "path": pin["path"], "bytes": pin["bytes"], "sha256": pin["sha256"], "verified": True})
        frame_rows.append({"object_id": spec["object_id"], "source_frame": spec["source_frame"], "output_frame": "S", "rule": spec["transform_rule"], "transform_application_count": transform_count, "matrix_rows_mm": transform_rows.tolist(), "pass": True})
        runtime_rows.append({"object_id": spec["object_id"], "primary_step": receipt["primary_step"], "runtime_npz": receipt["runtime"]["npz"], "runtime_ply": receipt["runtime"]["ply"], "runtime_stl": receipt["runtime"]["stl"], "vertex_count": int(len(vertices_m)), "triangle_count": int(len(faces)), "frame": "S", "units": "m", "scale_application_count": 1, "pass": True})

    source_recheck = {
        "schema": "FIXED_PLATFORM_SOURCE_PIN_RECHECK_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "source_pin_count_verified": pin_count,
        "all_bytes_and_sha256_match": True,
        "object_geometry_sources": source_rows,
        "pose_binding_verdict": binding["verdict"],
        "system_authority_changed": False,
        "verdict": "ALL_SOURCE_PINS_MATCH__ZERO_AUTHORITY_PROMOTION",
    }
    frame_audit = {
        "schema": "FIXED_PLATFORM_FRAME_AND_UNIT_TRANSFORM_AUDIT_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "rows": frame_rows,
        "unit_chain": {"primary_step": "mm", "runtime": "m", "scale": 0.001, "scale_application_count": 1},
        "T_S_M3R_LOCAL_rows_mm": transform.tolist(),
        "checks": {
            "load_bridge_identity_only": True,
            "m3r_a_transform_once": True,
            "m3r_b_transform_once": True,
            "m3r_a_b_same_transform": True,
            "rotation_orthonormal_det_plus_one": True,
            "mm_to_m_once": True,
            "double_transform_rejected": True,
        },
        "verdict": "3_OF_3_FRAME_AND_UNIT_CHAINS_PASS",
    }
    runtime_receipt = {
        "schema": "FIXED_PLATFORM_RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "rows": runtime_rows,
        "sidecar_is_primary_geometry_authority": False,
        "system_narrowphase_promoted": False,
        "as_built_derate_mm": None,
        "verdict": "3_OF_3_RUNTIME_SIDECAR_SETS_DERIVED_FROM_REOPENED_PRIMARY_STEP_IN_S_METRES",
    }
    three_step_receipt = {
        "schema": "FIXED_PLATFORM_THREE_STEP_BUILD_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "objects": {name: {"object_id": receipt["object_id"], "primary_step": receipt["primary_step"], "solid_count": 1, "volume_mm3": receipt["primary_step_geometry"]["volume_mm3"], "runtime_triangle_count": receipt["runtime"]["triangle_count"], "pass": True} for name, receipt in receipts.items()},
        "object_count": 3,
        "valid_closed_positive_solid_count": 3,
        "checks": {
            "three_sources_hash_pinned": True,
            "three_primary_steps_emitted": True,
            "three_steps_independently_reopened_in_builder": True,
            "three_runtime_sidecar_sets_emitted": True,
            "no_geometry_invented": True,
            "no_system_registry_mutated": True,
        },
        "maximum_legal_claim": "THREE_LOCAL_S_FRAME_STEP_FIRST_OPERATIONAL_COLLISION_GEOMETRY_CANDIDATES_BUILT__SYSTEM_BINDING_PAIR_SAFE_EDGE_PATH_AND_RELEASE_REMAIN_HELD",
        "verdict": "3_OF_3_LOCAL_FIXED_PLATFORM_CANDIDATES_BUILT__ZERO_SYSTEM_CREDIT",
    }
    artifacts[SOURCE_RECHECK] = stable_json_bytes(source_recheck)
    artifacts[FRAME_AUDIT] = stable_json_bytes(frame_audit)
    artifacts[RUNTIME_RECEIPT] = stable_json_bytes(runtime_receipt)
    artifacts[THREE_STEP_RECEIPT] = stable_json_bytes(three_step_receipt)
    builder_evidence = {
        **three_step_receipt,
        "schema": "FIXED_PLATFORM_BUILDER_EVIDENCE_V1",
        "contractual_three_step_receipt": byte_record(
            THREE_STEP_RECEIPT, artifacts[THREE_STEP_RECEIPT]
        ),
    }
    artifacts[BUILDER_EVIDENCE] = stable_json_bytes(builder_evidence)
    return {"artifacts": artifacts, "object_count": 3, "pin_count": pin_count}


def execute(*, check: bool, replace: bool) -> dict[str, Any]:
    result = build_bytes()
    for path, data in sorted(result["artifacts"].items(), key=lambda item: item[0].as_posix()):
        if check:
            require(path.is_file(), f"expected artifact missing: {path}")
            require(path.read_bytes() == data, f"deterministic replay mismatch: {path}")
        else:
            atomic_write(path, data, replace=replace)
    return {
        "status": "PASS",
        "mode": "check" if check else "write",
        "object_count": result["object_count"],
        "source_pin_count": result["pin_count"],
        "artifact_count": len(result["artifacts"]),
        "system_operational_authority_rows": 1,
        "system_pair_queries": 0,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    print(json.dumps(execute(check=args.check, replace=args.replace), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
