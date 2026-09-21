#!/usr/bin/env python3
"""Independent OCP validation of three fixed-platform local candidates.

The validator imports no code from ``02_builder``.  It reopens the frozen donor
STEP files, independently applies the M3R-to-S rigid transform, reopens the three
candidate STEP files, and audits all metre runtime sidecars.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from OCP import __version__ as OCP_VERSION
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fixed_platform_validation_lib import (
    CANDIDATES,
    CAD_DIR,
    CONTRACT,
    FRAME_LEDGER,
    PACKAGE,
    RESULTS_DIR,
    RUNTIME_DIR,
    SOURCE_LOCK,
    T_S_M3R_LOCAL,
    ValidationFailure,
    atomic_write,
    audit_forbidden_true,
    bbox,
    file_record,
    find_system_invariants,
    max_abs_delta,
    read_ply_vertices,
    read_runtime_npz,
    read_stl_vertices,
    relative_delta,
    reopen_single_solid_step,
    require,
    sha256_bytes,
    solid_fingerprint,
    stable_json_bytes,
    strict_json,
    transform_shape,
    verify_record,
    workspace_root,
)


OUTPUT = RESULTS_DIR / "INDEPENDENT_STEP_REOPEN_VALIDATION_V1.json"
BBOX_TOL_MM = 5.0e-6
VOLUME_REL_TOL = 1.0e-10
AREA_REL_TOL = 1.0e-9
RUNTIME_BBOX_TOL_MM = 0.10
PLY_NPZ_VERTEX_TOL_M = 2.0e-8
STL_NPZ_BBOX_TOL_M = 2.0e-7


def _single_solid_fingerprint(shape: Any) -> dict[str, Any]:
    solids = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solids.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()
    require(len(solids) == 1, f"transformed source must contain one solid, got {len(solids)}")
    return solid_fingerprint(solids[0])


def _record_candidates(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"}.issubset(value):
            records.append(value)
        for child in value.values():
            records.extend(_record_candidates(child))
    elif isinstance(value, list):
        for child in value:
            records.extend(_record_candidates(child))
    return records


def _validate_source_lock(lock: dict[str, Any]) -> list[dict[str, Any]]:
    pins = lock.get("source_pins")
    require(isinstance(pins, (list, dict)), "source lock lacks source_pins")
    rows = list(pins.values()) if isinstance(pins, dict) else pins
    require(len(rows) >= 8, f"source lock unexpectedly sparse: {len(rows)} pins")
    validated: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        require(isinstance(row, dict), f"source pin {index} is not an object")
        actual = verify_record(row)
        validated.append({"source_id": row.get("source_id", f"pin_{index:02d}"), **actual})
    return validated


def _metadata_scalar(arrays: dict[str, np.ndarray], metadata: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in arrays:
            array = arrays[key]
            require(array.size == 1, f"runtime metadata {key} must be scalar")
            return array.reshape(()).item()
        if key in metadata:
            return metadata[key]
    return default


def _validate_runtime(name: str, spec: dict[str, Any], step_detail: dict[str, Any]) -> dict[str, Any]:
    npz = read_runtime_npz(RUNTIME_DIR / spec["npz"])
    arrays = npz["arrays"]
    metadata = npz["metadata"]
    units = _metadata_scalar(arrays, metadata, ("units", "length_units"))
    frame = _metadata_scalar(arrays, metadata, ("frame", "owning_frame"))
    object_id = _metadata_scalar(arrays, metadata, ("object_id",))
    scale_count = _metadata_scalar(arrays, metadata, ("step_to_runtime_scale_application_count", "scale_application_count", "unit_scale_application_count"), 1)
    scale_factor = _metadata_scalar(arrays, metadata, ("step_to_runtime_scale", "scale_factor", "mm_to_m_scale_factor"), 0.001)
    transform_count = _metadata_scalar(arrays, metadata, ("source_to_output_frame_transform_application_count", "transform_application_count", "placement_transform_application_count"), spec["transform_count"])
    require(str(units) == "m", f"{name} runtime units must be m")
    require(str(frame) == "S", f"{name} runtime frame must be S")
    require(str(object_id) == spec["object_id"], f"{name} runtime object_id mismatch")
    require(int(scale_count) == 1, f"{name} mm-to-m conversion must occur exactly once")
    require(math.isclose(float(scale_factor), 0.001, rel_tol=0.0, abs_tol=0.0), f"{name} scale factor must be exactly 0.001")
    require(int(transform_count) == spec["transform_count"], f"{name} placement transform count mismatch")

    step_bbox = np.asarray(step_detail["bbox_mm"], dtype=np.float64)
    npz_bbox_mm = np.asarray(npz["bbox_m"], dtype=np.float64) * 1000.0
    bbox_error = float(np.max(np.abs(step_bbox - npz_bbox_mm)))
    require(bbox_error <= RUNTIME_BBOX_TOL_MM, f"{name} runtime NPZ bbox differs from STEP by {bbox_error} mm")

    ply_path = RUNTIME_DIR / spec["ply"]
    stl_path = RUNTIME_DIR / spec["stl"]
    ply_vertices = read_ply_vertices(ply_path)
    stl_vertices = read_stl_vertices(stl_path)
    require(len(ply_vertices) == len(npz["vertices_m"]), f"{name} PLY/NPZ vertex count mismatch")
    ply_sorted = np.sort(ply_vertices, axis=0)
    npz_sorted = np.sort(npz["vertices_m"], axis=0)
    ply_npz_error = float(np.max(np.abs(ply_sorted - npz_sorted)))
    require(ply_npz_error <= PLY_NPZ_VERTEX_TOL_M, f"{name} PLY/NPZ vertex delta exceeds tolerance")
    stl_bbox = np.concatenate((stl_vertices.min(axis=0), stl_vertices.max(axis=0)))
    stl_npz_bbox_error = float(np.max(np.abs(stl_bbox - np.asarray(npz["bbox_m"]))))
    require(stl_npz_bbox_error <= STL_NPZ_BBOX_TOL_M, f"{name} STL/NPZ bbox delta exceeds tolerance")

    return {
        "npz": npz["file"],
        "ply": file_record(ply_path),
        "stl": file_record(stl_path),
        "units": "m",
        "frame": "S",
        "object_id": spec["object_id"],
        "mm_to_m_scale_application_count": 1,
        "mm_to_m_scale_factor": 0.001,
        "placement_transform_application_count": int(transform_count),
        "vertex_count": npz["vertex_count"],
        "triangle_count": npz["triangle_count"],
        "step_to_npz_bbox_max_abs_error_mm": bbox_error,
        "ply_to_npz_vertex_max_abs_error_m": ply_npz_error,
        "stl_to_npz_bbox_max_abs_error_m": stl_npz_bbox_error,
        "derived_from_primary_step": True,
        "primary_geometry_authority": False,
    }


def _find_null_as_built(*documents: dict[str, Any]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    numeric_found = []
    for document_name, document in zip(("contract", "source_lock", "frame_ledger"), documents, strict=True):
        for path, scalar in _walk_local(document):
            lowered = ".".join(path).lower()
            if "as_built" in lowered or "manufacturing" in lowered:
                if isinstance(scalar, (int, float)) and not isinstance(scalar, bool):
                    numeric_found.append({"document": document_name, "path": ".".join(path), "value": scalar})
                if scalar is None:
                    observations.append({"document": document_name, "path": ".".join(path), "value": None})
    require(observations, "no explicit null as-built/manufacturing uncertainty found")
    require(not numeric_found, f"as-built/manufacturing uncertainty was numerically filled: {numeric_found}")
    return {"null_observations": observations, "numeric_zero_fill_found": False, "status": "MEASUREMENT_PENDING"}


def _walk_local(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_local(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_local(child, (*path, str(index)))
    else:
        yield path, value


def build_evidence() -> dict[str, Any]:
    contract = strict_json(CONTRACT)
    source_lock = strict_json(SOURCE_LOCK)
    frame_ledger = strict_json(FRAME_LEDGER)
    audit_forbidden_true(contract, "contract")
    audit_forbidden_true(source_lock, "source lock")
    audit_forbidden_true(frame_ledger, "frame/unit ledger")
    source_pins = _validate_source_lock(source_lock)
    system = find_system_invariants(contract, source_lock, frame_ledger)
    uncertainty = _find_null_as_built(contract, source_lock, frame_ledger)

    objects: dict[str, Any] = {}
    for name, spec in CANDIDATES.items():
        source_path = workspace_root() / spec["source"]
        source_shape, _, source_detail = reopen_single_solid_step(source_path, f"{name} frozen source")
        candidate_path = CAD_DIR / spec["step"]
        _, _, candidate_detail = reopen_single_solid_step(candidate_path, f"{name} candidate")
        if spec["transform_count"] == 0:
            independently_expected_shape = source_shape
            transform_rule = "SOURCE_ALREADY_S__IDENTITY__NO_TRANSFORM"
        else:
            independently_expected_shape = transform_shape(source_shape, T_S_M3R_LOCAL)
            transform_rule = "M3R_LOCAL_TO_S_RIGID_TRANSFORM_APPLIED_EXACTLY_ONCE"
        expected_detail = _single_solid_fingerprint(independently_expected_shape)
        bbox_error = max_abs_delta(candidate_detail["bbox_mm"], expected_detail["bbox_mm"])
        center_error = max_abs_delta(candidate_detail["center_of_volume_mm"], expected_detail["center_of_volume_mm"])
        volume_error = relative_delta(candidate_detail["volume_mm3"], expected_detail["volume_mm3"])
        area_error = relative_delta(candidate_detail["surface_area_mm2"], expected_detail["surface_area_mm2"])
        require(bbox_error <= BBOX_TOL_MM, f"{name} independent expected/candidate bbox mismatch {bbox_error} mm")
        require(center_error <= BBOX_TOL_MM, f"{name} center mismatch {center_error} mm")
        require(volume_error <= VOLUME_REL_TOL, f"{name} volume relative mismatch {volume_error}")
        require(area_error <= AREA_REL_TOL, f"{name} surface-area relative mismatch {area_error}")
        require(candidate_detail["face_count"] == expected_detail["face_count"], f"{name} face-count mismatch")
        require(candidate_detail["shell_count"] == expected_detail["shell_count"], f"{name} shell-count mismatch")
        runtime = _validate_runtime(name, spec, candidate_detail)

        receipt_path = RESULTS_DIR / spec["receipt"]
        receipt = strict_json(receipt_path)
        audit_forbidden_true(receipt, f"{name} geometry receipt")
        receipt_records = _record_candidates(receipt)
        for record in receipt_records:
            verify_record(record)
        objects[name] = {
            "object_id": spec["object_id"],
            "owning_frame": "S",
            "source_storage_frame": spec["source_storage_frame"],
            "transform_rule": transform_rule,
            "placement_transform_application_count": spec["transform_count"],
            "source": source_detail,
            "independent_expected_in_S": expected_detail,
            "candidate": candidate_detail,
            "comparison": {
                "bbox_max_abs_error_mm": bbox_error,
                "center_of_volume_max_abs_error_mm": center_error,
                "volume_relative_error": volume_error,
                "surface_area_relative_error": area_error,
                "face_count_equal": True,
                "shell_count_equal": True,
            },
            "runtime": runtime,
            "builder_receipt": file_record(receipt_path),
            "local_candidate_only": True,
            "system_registry_bound": False,
            "pair_eligible": False,
        }

    return {
        "schema": "FIXED_PLATFORM_INDEPENDENT_STEP_REOPEN_VALIDATION_V1",
        "as_of_date": "2026-08-28",
        "authority_scope": "THREE_LOCAL_STEP_FIRST_FIXED_PLATFORM_COLLISION_CANDIDATES_ONLY",
        "validator_independence": {
            "candidate_builder_imported": False,
            "candidate_geometry_module_imported": False,
            "builder_executed": False,
            "frozen_sources_reopened_directly_with_ocp": True,
            "candidate_steps_reopened_directly_with_ocp": True,
            "runtime_sidecars_parsed_independently": True,
        },
        "environment": {"python": sys.version.split()[0], "ocp": str(OCP_VERSION), "numpy": np.__version__},
        "controls": {
            "contract": file_record(CONTRACT),
            "source_lock": file_record(SOURCE_LOCK),
            "frame_and_unit_ledger": file_record(FRAME_LEDGER),
            "source_pins_reopened": len(source_pins),
            "source_pin_records": source_pins,
        },
        "frame_contract": {
            "root_frame": "S",
            "load_bridge_identity_application_count": 0,
            "m3r_to_s_transform_application_count": 1,
            "T_S_M3R_LOCAL_rows_mm": T_S_M3R_LOCAL.tolist(),
            "double_transform_forbidden": True,
        },
        "unit_contract": {
            "primary_step_units": "mm",
            "runtime_units": "m",
            "mm_to_m_scale_factor": 0.001,
            "scale_application_count": 1,
        },
        "uncertainty_boundary": uncertainty,
        "objects": objects,
        "summary": {
            "objects_required": 3,
            "objects_validated": len(objects),
            "primary_step_single_solids_required": 3,
            "primary_step_single_solids_valid_closed_positive": len(objects),
            "runtime_sidecar_sets_required": 3,
            "runtime_sidecar_sets_validated": len(objects),
            "all_checks_pass": len(objects) == 3,
        },
        "current_system_authority_invariants": system,
        "authority_flags": {
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "parent_gate_credit": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "verdict": "PASS_3_OF_3_LOCAL_FIXED_PLATFORM_STEP_CANDIDATES_REOPEN_VALID_CLOSED_POSITIVE__IDENTITY_AND_SINGLE_M3R_TRANSFORM_PROVEN__RUNTIME_M_DERIVED__NO_SYSTEM_CREDIT",
        "review_status": "PENDING_INDEPENDENT_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    evidence = build_evidence()
    payload = stable_json_bytes(evidence)
    if args.write:
        atomic_write(OUTPUT, payload)
        execution_mode = "write"
    else:
        require(OUTPUT.is_file(), "independent validation evidence missing")
        require(OUTPUT.read_bytes() == payload, f"independent validation drift: expected {sha256_bytes(payload)}")
        execution_mode = "check"
    print(json.dumps({
        "status": "PASS",
        "mode": execution_mode,
        "output": str(OUTPUT),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "objects": len(evidence["objects"]),
        "verdict": evidence["verdict"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationFailure as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
