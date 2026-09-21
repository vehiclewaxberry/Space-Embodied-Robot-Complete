#!/usr/bin/env python3
"""Build the exact Route-C R101 link1 B6 as STEP-first host-local candidates."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from link1_pose_adapter import joint1_transform_A0_link1, load_adapter, pose_matrix_S_link1


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = next(candidate for candidate in (PACKAGE, *PACKAGE.parents) if (candidate / "PROJECT_MAP.md").is_file())
R20_UTIL_DIR = ROOT / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_R121_OPERATIONAL_COLLISION_CANDIDATE_V1/02_builder"
sys.path.insert(0, str(R20_UTIL_DIR))
from route_c_root_static_geometry import (  # noqa: E402
    atomic_write,
    bbox_mm,
    binary_ply,
    binary_stl,
    byte_record,
    canonicalize_mesh,
    deterministic_npz,
    extract_triangles_m,
    json_metadata_array,
    manifold_metrics,
    read_brep,
    read_step_bytes,
    require,
    sha256_path,
    stable_json_bytes,
    strict_json,
    transform_shape,
    validate_single_solid,
    write_step_bytes,
)


CONTRACT = PACKAGE / "00_contract/LINK1_B6_OPERATIONAL_COLLISION_CONTRACT_V1.json"
SOURCE_LOCK = PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"
LEDGER = PACKAGE / "00_contract/FRAME_UNIT_AND_UNCERTAINTY_LEDGER_V1.json"
EXTRACTOR = PACKAGE / "02_builder/extract_v9f_link1_b6_brep.py"
CAD_DIR = PACKAGE / "01_cad"
RUNTIME_DIR = PACKAGE / "02_runtime"
RESULTS_DIR = PACKAGE / "05_results"
GEOMETRY_INDEX = RESULTS_DIR / "LINK1_B6_GEOMETRY_INDEX_V1.json"
RUNTIME_RECEIPT = RESULTS_DIR / "LINK1_B6_RUNTIME_SIDECAR_RECEIPT_V1.json"
POSE_RECEIPT = RESULTS_DIR / "LINK1_B6_POSE_ADAPTER_SAMPLES_V1.json"
BUILD_RECEIPT = RESULTS_DIR / "SIX_STEP_BUILD_RECEIPT_V1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def locate_freecad_python() -> Path:
    candidates = []
    if os.environ.get("ROUTE_C_FREECAD_PYTHON"):
        candidates.append(Path(os.environ["ROUTE_C_FREECAD_PYTHON"]))
    candidates.extend([
        Path(r"G:\Windows_program_file\FreeCAD\bin\python.exe"),
        Path(r"C:\Program Files\FreeCAD 1.1\bin\python.exe"),
        Path(r"C:\Program Files\FreeCAD 1.0\bin\python.exe"),
    ])
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise RuntimeError("FreeCAD-bundled python.exe not found; set ROUTE_C_FREECAD_PYTHON")


def run_extractor(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = locate_freecad_python()
    completed = subprocess.run(
        [str(runtime), str(EXTRACTOR), "--output-dir", str(directory)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="strict", check=False,
    )
    require(completed.returncode == 0, f"FreeCAD extractor failed:\n{completed.stdout}\n{completed.stderr}")
    require(not completed.stderr.strip(), f"FreeCAD extractor wrote stderr: {completed.stderr}")
    document = json.loads(completed.stdout)
    require(document["verdict"] == "LINK1_B6_TRANSIENT_BREP_EXTRACTION_PASS__OBJECT_PLACEMENT_NOT_REAPPLIED", "extractor verdict drift")
    banner = subprocess.run(
        [str(runtime), "-c", "import FreeCAD; print(FreeCAD.Version())"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    ).stdout.strip()
    return document, {"path": str(runtime), "bytes": runtime.stat().st_size, "sha256": sha256_path(runtime), "freecad_banner": banner}


def verify_pins(lock: dict[str, Any]) -> dict[str, Path]:
    require(lock["source_pin_count"] == 10 and len(lock["source_pins"]) == 10, "source lock count drift")
    result = {}
    for row in lock["source_pins"]:
        require(row["id"] not in result, f"duplicate source pin: {row['id']}")
        path = ROOT / row["path"]
        require(path.is_file(), f"source pin missing: {row['id']}")
        require(path.stat().st_size == int(row["bytes"]), f"source bytes drift: {row['id']}")
        require(sha256_path(path) == row["sha256"], f"source hash drift: {row['id']}")
        result[row["id"]] = path
    return result


def matrix_m_to_mm(matrix: np.ndarray) -> np.ndarray:
    result = np.asarray(matrix, dtype=np.float64).copy()
    result[:3, 3] *= 1000.0
    return result


def relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), 1e-300)


def transform_points(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    homogeneous = np.column_stack([np.asarray(points, dtype=np.float64), np.ones(len(points))])
    return (matrix @ homogeneous.T).T[:, :3]


def bbox_corners(bounds: np.ndarray) -> np.ndarray:
    low, high = bounds
    return np.asarray([[x, y, z] for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])], dtype=np.float64)


def build_artifacts() -> tuple[dict[Path, bytes], dict[str, Any]]:
    contract = strict_json(CONTRACT)
    lock = strict_json(SOURCE_LOCK)
    ledger = strict_json(LEDGER)
    paths = verify_pins(lock)
    adapter = load_adapter()
    joint = adapter["joint"]
    mount = adapter["mount"]
    t_a0_l1_0_m = joint1_transform_A0_link1(0.0, joint)
    t_l1_a0_mm = matrix_m_to_mm(np.linalg.inv(t_a0_l1_0_m))
    t_a0_l1_0_mm = matrix_m_to_mm(t_a0_l1_0_m)
    specs = contract["objects"]
    require(len(specs) == 6, "contract must contain exactly six objects")
    require(len({row["object_id"] for row in specs}) == 6, "object id uniqueness drift")
    require(len({row["source_label"] for row in specs}) == 6, "source label uniqueness drift")
    require(len({row["output"] for row in specs}) == 6, "output uniqueness drift")

    registry = strict_json(paths["m01_registry"])
    registry_rows = {row["object_id"]: row for row in registry["objects"] if row["category"] == "R" and row["parent_frame"] == "link1"}
    require(set(registry_rows) == {row["object_id"] for row in specs}, "exact registry link1 selection drift")
    receipt = strict_json(paths["v9f_build_receipt"])
    receipt_rows = {row["name"]: row for row in receipt["parts"] if row.get("geometry_role") == "PHYSICAL"}
    mass_geometry = strict_json(paths["v9f_mass_geometry"])
    require(str(mass_geometry["frame"]).startswith("A0 = B601 base_link frame at q=0"), "mass geometry frame drift")
    require(mass_geometry["units"] == {"cg": "mm", "inertia_volume": "mm5", "volume": "mm3"}, "mass geometry unit drift")
    mass_rows = {row["name"]: row for row in mass_geometry["parts"] if row.get("geometry_role") == "PHYSICAL"}
    mesh_manifest = strict_json(paths["v9f_mesh_manifest"])
    require(mesh_manifest["schema"] == "ROUTE_C_SWEEP_MESH_PACK_V9F_MANIFEST" and mesh_manifest["variant"] == "V9F" and mesh_manifest["units"] == "mm", "mesh manifest drift")

    artifacts: dict[Path, bytes] = {}
    geometry_rows = []
    runtime_rows = []
    with tempfile.TemporaryDirectory(prefix="route_c_link1_b6_brep_") as directory_name:
        directory = Path(directory_name)
        extraction, freecad_runtime = run_extractor(directory)
        extracted = {row["object_id"]: row for row in extraction["objects"]}
        require(set(extracted) == set(registry_rows), "extracted object set drift")
        for spec in specs:
            object_id = spec["object_id"]
            source_row = extracted[object_id]
            registry_row = registry_rows[object_id]
            receipt_row = receipt_rows[spec["source_label"]]
            mass_row = mass_rows[spec["source_label"]]
            require(registry_row["motion_class"] == "HOST_FIXED_UNLESS_REGISTERED_OTHERWISE", f"motion class drift: {object_id}")
            require(registry_row["kind"] == spec["kind"], f"registry kind drift: {object_id}")
            require(receipt_row["host_link"] == "link1" and receipt_row["kind"] == spec["kind"], f"receipt mapping drift: {object_id}")
            require(mass_row["host_link"] == "link1" and mass_row["kind"] == spec["kind"], f"mass mapping drift: {object_id}")
            triangle_pin = registry_row["geometry"]["narrowphase_candidate"]
            triangle_path = ROOT / triangle_pin["path"]
            require(triangle_path.stat().st_size == int(triangle_pin["bytes"]) and sha256_path(triangle_path) == triangle_pin["sha256"], f"registry triangle pin drift: {object_id}")
            brep_path = directory / source_row["temporary_brep"]["filename"]
            require(brep_path.stat().st_size == int(source_row["temporary_brep"]["bytes"]) and sha256_path(brep_path) == source_row["temporary_brep"]["sha256"], f"transient BREP pin drift: {object_id}")
            source_shape = read_brep(brep_path)
            source_metric = validate_single_solid(source_shape, context=f"{object_id} A0 source")
            receipt_residual = relative_error(source_metric["volume_mm3"], float(receipt_row["volume_mm3"]))
            mass_residual = relative_error(source_metric["volume_mm3"], float(mass_row["volume_mm3"]))
            require(receipt_residual <= contract["tolerances"]["source_receipt_volume_relative"], f"receipt volume drift: {object_id}")
            require(mass_residual <= contract["tolerances"]["source_receipt_volume_relative"], f"mass volume drift: {object_id}")

            local_shape = transform_shape(source_shape, t_l1_a0_mm)
            local_metric = validate_single_solid(local_shape, context=f"{object_id} link1 local")
            recovered_shape = transform_shape(local_shape, t_a0_l1_0_mm)
            recovered_bbox_residual = float(np.max(np.abs(bbox_mm(recovered_shape) - source_metric["bbox_mm"])))
            require(recovered_bbox_residual <= contract["tolerances"]["q0_bbox_closure_mm"], f"A0 roundtrip bbox drift: {object_id}")
            step_bytes = write_step_bytes(local_shape)
            reopened = read_step_bytes(step_bytes)
            output_metric = validate_single_solid(reopened, context=f"{object_id} reopened STEP")
            step_volume_residual = relative_error(output_metric["volume_mm3"], source_metric["volume_mm3"])
            step_bbox_residual = float(np.max(np.abs(output_metric["bbox_mm"] - local_metric["bbox_mm"])))
            require(step_volume_residual <= contract["tolerances"]["step_reopen_volume_relative"], f"STEP volume drift: {object_id}")
            require(step_bbox_residual <= contract["tolerances"]["step_reopen_bbox_mm"], f"STEP bbox drift: {object_id}: {step_bbox_residual}")
            step_path = CAD_DIR / spec["output"]
            artifacts[step_path] = step_bytes
            step_record = byte_record(step_path, step_bytes)

            triangles_m, solid_ids = extract_triangles_m(reopened)
            vertices_m, faces, solid_ids, cleanup = canonicalize_mesh(triangles_m, solid_ids)
            manifold = manifold_metrics(faces)
            require(manifold["closed_oriented_two_manifold"], f"runtime mesh is not watertight: {object_id}")
            mesh_volume_m3 = abs(float(np.einsum("ij,ij->i", vertices_m[faces][:, 0], np.cross(vertices_m[faces][:, 1], vertices_m[faces][:, 2])).sum() / 6.0))
            mesh_volume_relative = relative_error(mesh_volume_m3 * 1e9, output_metric["volume_mm3"])
            require(mesh_volume_relative <= contract["tolerances"]["runtime_mesh_volume_relative"], f"runtime mesh volume drift: {object_id}")
            runtime_stem = Path(spec["output"]).stem + "_M"
            metadata = {
                "schema": "ROUTE_C_LINK1_LOCAL_RUNTIME_MESH_V1",
                "object_id": object_id,
                "frame": "link1",
                "joint_state": "q1=0",
                "length_unit": "m",
                "primary_step": step_record["path"],
                "primary_step_sha256": step_record["sha256"],
                "primary_step_is_geometry_authority": True,
                "runtime_is_geometry_authority": False,
                "step_to_runtime_scale": 0.001,
                "scale_application_count": 1,
                "linear_deflection_mm": 0.05,
                "as_built_derate_mm": None,
            }
            runtime_paths = {
                "npz": RUNTIME_DIR / f"{runtime_stem}.npz",
                "ply": RUNTIME_DIR / f"{runtime_stem}.ply",
                "stl": RUNTIME_DIR / f"{runtime_stem}.stl",
            }
            runtime_bytes = {
                "npz": deterministic_npz({"faces": faces, "metadata_utf8": json_metadata_array(metadata), "solid_ids": solid_ids, "vertices_m": vertices_m}),
                "ply": binary_ply(vertices_m, faces, object_id),
                "stl": binary_stl(vertices_m, faces, object_id),
            }
            runtime_records = {}
            for kind in ("npz", "ply", "stl"):
                artifacts[runtime_paths[kind]] = runtime_bytes[kind]
                runtime_records[kind] = byte_record(runtime_paths[kind], runtime_bytes[kind])

            local_cg_mm = transform_points(np.asarray([mass_row["cg_mm_A0"]]), t_l1_a0_mm)[0]
            geometry_rows.append({
                "object_id": object_id,
                "source_label": spec["source_label"],
                "source_internal_name": spec["source_internal_name"],
                "registry_parent_frame": "link1",
                "registry_motion_class": registry_row["motion_class"],
                "source_storage_frame": "A0_Q0_REFERENCE",
                "source_unit": "mm",
                "source_shape_object_placement_consumed_separately": False,
                "source_bbox_mm": source_metric["bbox_mm"].tolist(),
                "source_volume_mm3": source_metric["volume_mm3"],
                "source_receipt_volume_relative_residual": receipt_residual,
                "source_mass_geometry_volume_relative_residual": mass_residual,
                "source_cg_mm_A0": mass_row["cg_mm_A0"],
                "output_frame": "link1",
                "output_joint_state": "q1=0",
                "output_unit": "mm",
                "transform": "inv(T_A0_link1(0))_from_accepted_URDF_raw_numbers",
                "transform_application_count": 1,
                "output_solid_count": 1,
                "output_face_count": output_metric["face_count"],
                "output_bbox_mm": output_metric["bbox_mm"].tolist(),
                "output_volume_mm3": output_metric["volume_mm3"],
                "output_cg_mm_link1": local_cg_mm.tolist(),
                "a0_roundtrip_bbox_max_abs_mm": recovered_bbox_residual,
                "step_reopen_volume_relative_residual": step_volume_residual,
                "step_reopen_bbox_max_abs_mm": step_bbox_residual,
                "registry_triangle_cross_check": {**triangle_pin, "primary_geometry_authority": False},
                "primary_step": step_record,
                "runtime_sidecars": runtime_records,
            })
            runtime_rows.append({
                "object_id": object_id,
                "frame": "link1",
                "unit": "m",
                "vertices": int(len(vertices_m)),
                "triangles": int(len(faces)),
                "solid_ids": sorted({int(value) for value in solid_ids}),
                "mesh_volume_relative_error": mesh_volume_relative,
                "cleanup": cleanup,
                "manifold": manifold,
                "artifacts": runtime_records,
                "derived_from_primary_step_sha256": step_record["sha256"],
            })

    q0_matrix_closure = float(np.max(np.abs(pose_matrix_S_link1(0.0, joint, mount) @ np.linalg.inv(t_a0_l1_0_m) - mount)))
    require(q0_matrix_closure <= contract["tolerances"]["fk_matrix_max_abs"], "q0 pose/source matrix closure drift")
    sample_rows = []
    for sample in ledger["pose_samples"]:
        q = float(sample["q1_rad"])
        matrix = pose_matrix_S_link1(q, joint, mount)
        sample_rows.append({
            "sample": sample["sample"],
            "q1_rad_raw": sample["q1_rad"],
            "q2_to_q6_rad": [0, 0, 0, 0, 0],
            "T_S_link1_m": [[float(value) for value in row] for row in matrix],
            "rotation_orthonormal_max_abs": float(np.max(np.abs(matrix[:3, :3].T @ matrix[:3, :3] - np.eye(3)))),
            "rotation_determinant": float(np.linalg.det(matrix[:3, :3])),
        })
    pose_document = {
        "schema": "ROUTE_C_LINK1_B6_POSE_ADAPTER_SAMPLES_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "accepted_urdf": byte_record(paths["accepted_urdf"], paths["accepted_urdf"].read_bytes()),
        "execution_mount": byte_record(paths["execution_mount_12dp"], paths["execution_mount_12dp"].read_bytes()),
        "execution_mount_payload_sha256": adapter["mount_payload_sha256"],
        "execution_mount_decimal_strings_consumed_directly": adapter["mount_strings"],
        "joint1_raw": {
            "origin_xyz_m": joint["origin_xyz_raw"], "origin_rpy_rad": joint["origin_rpy_raw"], "axis": joint["axis_raw"],
            "limit_lower_rad": joint["limit_lower_raw"], "limit_upper_rad": joint["limit_upper_raw"],
        },
        "q0_source_to_link1_to_S_matrix_closure_max_abs": q0_matrix_closure,
        "samples": sample_rows,
        "side_effect_free": True,
        "system_authority_changed": False,
        "verdict": "JOINT1_ACCEPTED_URDF_RAW_FK_AND_12DP_EXECUTION_MOUNT_ADAPTER_SAMPLES_PASS",
    }
    pose_bytes = stable_json_bytes(pose_document)
    artifacts[POSE_RECEIPT] = pose_bytes
    geometry_document = {
        "schema": "ROUTE_C_LINK1_B6_GEOMETRY_INDEX_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "scope": "R101_FIRST_SAFE_BATCH_LINK1_B6",
        "source_pin_count_verified": len(paths),
        "object_count": len(geometry_rows),
        "source_valid_closed_single_positive_brep_count": len(geometry_rows),
        "output_valid_closed_single_positive_step_count": len(geometry_rows),
        "source_frame": "A0_Q0_REFERENCE",
        "output_frame": "link1",
        "output_joint_state": "q1=0",
        "primary_step_unit": "mm",
        "objects": geometry_rows,
        "system_registry_rows_modified": 0,
        "system_pair_query_credit": 0,
        "verdict": "LINK1_B6_STEP_FIRST_HOST_LOCAL_GEOMETRY_BUILT__LOCAL_CANDIDATE_ONLY",
    }
    geometry_bytes = stable_json_bytes(geometry_document)
    artifacts[GEOMETRY_INDEX] = geometry_bytes
    runtime_document = {
        "schema": "ROUTE_C_LINK1_B6_RUNTIME_SIDECAR_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "object_count": len(runtime_rows),
        "sidecar_set_count": len(runtime_rows),
        "sidecar_artifact_count": 3 * len(runtime_rows),
        "source": "COLD_REOPENED_PRIMARY_STEP_ONLY",
        "frame": "link1",
        "joint_state": "q1=0",
        "length_unit": "m",
        "step_to_runtime_scale": 0.001,
        "scale_application_count": 1,
        "runtime_is_primary_geometry_authority": False,
        "objects": runtime_rows,
        "verdict": "6_OF_6_RUNTIME_SIDECAR_SETS_DERIVED_FROM_REOPENED_LINK1_LOCAL_STEP_IN_METRES",
    }
    runtime_bytes = stable_json_bytes(runtime_document)
    artifacts[RUNTIME_RECEIPT] = runtime_bytes
    build_document = {
        "schema": "ROUTE_C_LINK1_B6_SIX_STEP_BUILD_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "scope": "R101_FIRST_SAFE_BATCH_LINK1_B6",
        "contract_files": {
            "source_authority_lock": byte_record(SOURCE_LOCK, SOURCE_LOCK.read_bytes()),
            "frame_unit_and_uncertainty_ledger": byte_record(LEDGER, LEDGER.read_bytes()),
            "link1_b6_contract": byte_record(CONTRACT, CONTRACT.read_bytes()),
        },
        "freecad_runtime": freecad_runtime,
        "source_document": extraction["source"],
        "source_document_opened_read_only": True,
        "source_document_saved_or_recomputed": False,
        "source_shape_object_placement_consumed_separately": False,
        "source_pins_verified": len(paths),
        "objects_requested": 6,
        "objects_emitted": len(geometry_rows),
        "primary_step_files": len(geometry_rows),
        "runtime_sidecar_files": 3 * len(runtime_rows),
        "generated_artifact_count_excluding_this_receipt": len(artifacts),
        "geometry_index": byte_record(GEOMETRY_INDEX, geometry_bytes),
        "runtime_sidecar_receipt": byte_record(RUNTIME_RECEIPT, runtime_bytes),
        "pose_adapter_receipt": byte_record(POSE_RECEIPT, pose_bytes),
        "remaining_R95": "FAIL_CLOSED_HOST_AND_SPECIAL_MOTION_ADAPTER_HOLD",
        "pair_eligible": False,
        "system_operational_credit": False,
        "system_pair_query_credit": 0,
        "safe_edge_path_credit": False,
        "release_credit": False,
        "maximum_legal_claim": contract["maximum_legal_claim"],
        "system_status_invariant": contract["system_status_invariant"],
        "verdict": "LINK1_B6_PRIMARY_STEP_RUNTIME_AND_POSE_ADAPTER_BUILD_PASS__SYSTEM_AUTHORITY_UNCHANGED",
    }
    build_bytes = stable_json_bytes(build_document)
    artifacts[BUILD_RECEIPT] = build_bytes
    return artifacts, {"objects": 6, "steps": 6, "runtime_sidecars": 18, "artifacts": len(artifacts), "verdict": build_document["verdict"]}


def main() -> None:
    args = parse_args()
    artifacts, summary = build_artifacts()
    if args.write:
        for path, data in sorted(artifacts.items(), key=lambda item: item[0].as_posix()):
            atomic_write(path, data, replace=args.replace)
        summary.update({"mode": "write", "written": len(artifacts)})
    else:
        failures = []
        for path, expected in sorted(artifacts.items(), key=lambda item: item[0].as_posix()):
            if not path.is_file():
                failures.append({"path": path.relative_to(ROOT).as_posix(), "reason": "missing"})
            elif path.read_bytes() != expected:
                failures.append({"path": path.relative_to(ROOT).as_posix(), "reason": "byte_mismatch"})
        require(not failures, f"deterministic artifact check failed: {failures}")
        summary.update({"mode": "check", "verified": len(artifacts)})
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
