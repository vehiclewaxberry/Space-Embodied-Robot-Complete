#!/usr/bin/env python3
"""Build 20 root-static Route-C STEP-first local collision candidates."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from route_c_root_static_geometry import (
    CAD_DIR,
    CONTRACT_PATH,
    FRAME_LEDGER_PATH,
    LINEAR_DEFLECTION_MM,
    PACKAGE,
    RESULTS_DIR,
    RUNTIME_DIR,
    SOURCE_LOCK_PATH,
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
    matrix_from_ledger,
    read_brep,
    read_step_bytes,
    require,
    sha256_path,
    stable_json_bytes,
    strict_json,
    transform_shape,
    validate_single_solid,
    verify_source_pins,
    volume_mm3,
    workspace_root,
    write_step_bytes,
)


GEOMETRY_INDEX = RESULTS_DIR / "ROOT_STATIC_R20_GEOMETRY_INDEX_V1.json"
RUNTIME_RECEIPT = RESULTS_DIR / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json"
BUILD_RECEIPT = RESULTS_DIR / "TWENTY_STEP_BUILD_RECEIPT_V1.json"
EXTRACTOR = PACKAGE / "02_builder/extract_v9f_root_static_r20_brep.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def locate_freecad_python() -> Path:
    override = os.environ.get("ROUTE_C_FREECAD_PYTHON")
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.extend(
        [
            Path(r"G:\Windows_program_file\FreeCAD\bin\python.exe"),
            Path(r"C:\Program Files\FreeCAD 1.1\bin\python.exe"),
            Path(r"C:\Program Files\FreeCAD 1.0\bin\python.exe"),
        ]
    )
    if os.name == "nt":
        try:
            import winreg

            roots = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hive, key_name in roots:
                try:
                    with winreg.OpenKey(hive, key_name) as key:
                        for index in range(winreg.QueryInfoKey(key)[0]):
                            sub_name = winreg.EnumKey(key, index)
                            with winreg.OpenKey(key, sub_name) as subkey:
                                try:
                                    display_name = str(winreg.QueryValueEx(subkey, "DisplayName")[0])
                                except OSError:
                                    continue
                                if "FreeCAD" not in display_name:
                                    continue
                                try:
                                    icon = str(winreg.QueryValueEx(subkey, "DisplayIcon")[0]).strip('"')
                                    candidates.append(Path(icon).parent / "python.exe")
                                except OSError:
                                    pass
                except OSError:
                    pass
        except ImportError:
            pass
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError("FreeCAD-bundled python.exe not found; set ROUTE_C_FREECAD_PYTHON")


def run_transient_extractor(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    freecad_python = locate_freecad_python()
    completed = subprocess.run(
        [str(freecad_python), str(EXTRACTOR), "--output-dir", str(directory)],
        cwd=str(workspace_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    require(completed.returncode == 0, f"FreeCAD extraction failed:\n{completed.stdout}\n{completed.stderr}")
    require(not completed.stderr.strip(), f"FreeCAD extraction wrote stderr: {completed.stderr}")
    extraction = json.loads(completed.stdout)
    require(extraction["verdict"] == "R20_TRANSIENT_BREP_EXTRACTION_PASS__SOURCE_OPENED_READ_ONLY", "extractor verdict HOLD")
    runtime = {
        "path": str(freecad_python),
        "bytes": freecad_python.stat().st_size,
        "sha256": sha256_path(freecad_python),
        "freecad_banner": subprocess.run(
            [str(freecad_python), "-c", "import FreeCAD; print(FreeCAD.Version())"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        ).stdout.strip(),
    }
    return extraction, runtime


def relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), 1.0e-300)


def build_artifacts() -> tuple[dict[Path, bytes], dict[str, Any]]:
    contract = strict_json(CONTRACT_PATH)
    source_lock = strict_json(SOURCE_LOCK_PATH)
    frame_ledger = strict_json(FRAME_LEDGER_PATH)
    source_pin_count = verify_source_pins(source_lock)
    require(source_pin_count == 13, "source pin count drift")
    specs = contract["objects"]
    require(len(specs) == 20, "contract must contain 20 objects")
    require(len({row["object_id"] for row in specs}) == 20, "object_id uniqueness drift")
    require(len({row["source_label"] for row in specs}) == 20, "source_label uniqueness drift")
    require(len({row["output"] for row in specs}) == 20, "output uniqueness drift")
    transform = matrix_from_ledger(frame_ledger)

    root = workspace_root()
    pins = {row["id"]: row for row in source_lock["source_pins"]}
    registry = strict_json(root / pins["m01_registry"]["path"])
    registry_rows = {row["object_id"]: row for row in registry["objects"] if row["category"] == "R"}
    receipt = strict_json(root / pins["v9f_build_receipt"]["path"])
    receipt_rows = {row["name"]: row for row in receipt["parts"] if row.get("geometry_role") == "PHYSICAL"}

    artifacts: dict[Path, bytes] = {}
    geometry_rows = []
    runtime_rows = []
    with tempfile.TemporaryDirectory(prefix="route_c_root_static_r20_brep_") as directory_name:
        directory = Path(directory_name)
        extraction, freecad_runtime = run_transient_extractor(directory)
        extracted = {row["object_id"]: row for row in extraction["objects"]}
        require(len(extracted) == 20, "transient extraction count drift")
        for spec in specs:
            object_id = spec["object_id"]
            source_label = spec["source_label"]
            source = extracted.get(object_id)
            require(source is not None and source["source_label"] == source_label, f"extraction mapping drift: {object_id}")
            registry_row = registry_rows.get(object_id)
            require(registry_row is not None, f"registry object missing: {object_id}")
            require(registry_row["parent_frame"] == spec["parent_frame"], f"parent frame drift: {object_id}")
            require(registry_row["motion_class"] == "HOST_FIXED_UNLESS_REGISTERED_OTHERWISE", f"motion class drift: {object_id}")
            require(registry_row["kind"] == spec["kind"], f"kind drift: {object_id}")
            triangle_pin = registry_row["geometry"]["narrowphase_candidate"]
            triangle_path = root / triangle_pin["path"]
            require(triangle_path.is_file(), f"triangle cross-check missing: {object_id}")
            require(triangle_path.stat().st_size == int(triangle_pin["bytes"]), f"triangle byte drift: {object_id}")
            require(sha256_path(triangle_path) == triangle_pin["sha256"], f"triangle hash drift: {object_id}")

            brep_path = directory / source["temporary_brep"]["filename"]
            require(brep_path.stat().st_size == source["temporary_brep"]["bytes"], f"transient BREP byte drift: {object_id}")
            require(sha256_path(brep_path) == source["temporary_brep"]["sha256"], f"transient BREP hash drift: {object_id}")
            source_shape = read_brep(brep_path)
            source_metric = validate_single_solid(source_shape, context=f"{object_id} source BREP")
            receipt_row = receipt_rows[source_label]
            receipt_volume_residual = relative_error(source_metric["volume_mm3"], float(receipt_row["volume_mm3"]))
            require(receipt_volume_residual <= float(contract["tolerances"]["source_receipt_volume_relative"]), f"source receipt volume drift: {object_id}")

            transformed = transform_shape(source_shape, transform)
            target_metric = validate_single_solid(transformed, context=f"{object_id} transformed BREP")
            rigid_volume_residual = relative_error(target_metric["volume_mm3"], source_metric["volume_mm3"])
            require(rigid_volume_residual <= 1.0e-12, f"rigid volume invariant drift: {object_id}")
            step_bytes = write_step_bytes(transformed)
            reopened = read_step_bytes(step_bytes)
            output_metric = validate_single_solid(reopened, context=f"{object_id} emitted STEP")
            step_volume_residual = relative_error(output_metric["volume_mm3"], target_metric["volume_mm3"])
            step_bbox_residual = float(np.max(np.abs(output_metric["bbox_mm"] - target_metric["bbox_mm"])))
            require(step_volume_residual <= float(contract["tolerances"]["step_reopen_volume_relative"]), f"STEP volume reopen drift: {object_id}")
            require(step_bbox_residual <= float(contract["tolerances"]["step_reopen_bbox_mm"]), f"STEP bbox reopen drift: {object_id}")

            step_path = CAD_DIR / spec["output"]
            artifacts[step_path] = step_bytes
            triangles_m, solid_ids = extract_triangles_m(reopened)
            vertices_m, faces, solid_ids, cleanup = canonicalize_mesh(triangles_m, solid_ids)
            manifold = manifold_metrics(faces)
            mesh_volume_m3 = abs(float(np.einsum(
                "ij,ij->i",
                vertices_m[faces][:, 0],
                np.cross(vertices_m[faces][:, 1], vertices_m[faces][:, 2]),
            ).sum() / 6.0))
            mesh_volume_relative_error = relative_error(mesh_volume_m3 * 1.0e9, output_metric["volume_mm3"])
            runtime_stem = Path(spec["output"]).stem.replace("_S_V1", "_S_M_V1")
            metadata = {
                "schema": "ROUTE_C_ROOT_STATIC_RUNTIME_MESH_V1",
                "object_id": object_id,
                "frame": "S",
                "length_unit": "m",
                "primary_step": step_path.relative_to(root).as_posix(),
                "primary_step_sha256": byte_record(step_path, step_bytes)["sha256"],
                "primary_step_is_geometry_authority": True,
                "runtime_is_geometry_authority": False,
                "linear_deflection_mm": LINEAR_DEFLECTION_MM,
                "as_built_derate_mm": None,
            }
            npz_path = RUNTIME_DIR / f"{runtime_stem}.npz"
            ply_path = RUNTIME_DIR / f"{runtime_stem}.ply"
            stl_path = RUNTIME_DIR / f"{runtime_stem}.stl"
            npz_bytes = deterministic_npz(
                {
                    "faces": faces,
                    "metadata_utf8": json_metadata_array(metadata),
                    "solid_ids": solid_ids,
                    "vertices_m": vertices_m,
                }
            )
            ply_bytes = binary_ply(vertices_m, faces, object_id)
            stl_bytes = binary_stl(vertices_m, faces, object_id)
            artifacts[npz_path] = npz_bytes
            artifacts[ply_path] = ply_bytes
            artifacts[stl_path] = stl_bytes
            runtime_artifacts = {
                "npz": byte_record(npz_path, npz_bytes),
                "ply": byte_record(ply_path, ply_bytes),
                "stl": byte_record(stl_path, stl_bytes),
            }
            step_record = byte_record(step_path, step_bytes)
            geometry_rows.append(
                {
                    "object_id": object_id,
                    "source_label": source_label,
                    "registry_parent_frame": registry_row["parent_frame"],
                    "registry_motion_class": registry_row["motion_class"],
                    "source_storage_frame": "A0_Q0_REFERENCE",
                    "output_frame": "S",
                    "length_unit": "mm",
                    "transform": "T_S_A0",
                    "transform_application_count": 1,
                    "source_shape_object_placement_consumed_separately": False,
                    "source_solid_count": 1,
                    "source_face_count": source_metric["face_count"],
                    "source_shell_count": source_metric["shell_count"],
                    "source_bbox_mm": source_metric["bbox_mm"].tolist(),
                    "source_volume_mm3": source_metric["volume_mm3"],
                    "source_receipt_volume_relative_residual": receipt_volume_residual,
                    "output_solid_count": 1,
                    "output_face_count": output_metric["face_count"],
                    "output_shell_count": output_metric["shell_count"],
                    "output_bbox_mm": output_metric["bbox_mm"].tolist(),
                    "output_volume_mm3": output_metric["volume_mm3"],
                    "rigid_volume_relative_residual": rigid_volume_residual,
                    "step_reopen_volume_relative_residual": step_volume_residual,
                    "step_reopen_bbox_max_abs_mm": step_bbox_residual,
                    "source_triangle_cross_check": {
                        "path": triangle_pin["path"],
                        "bytes": triangle_pin["bytes"],
                        "sha256": triangle_pin["sha256"],
                        "triangles": triangle_pin["triangles"],
                        "primary_geometry_authority": False,
                    },
                    "primary_step": step_record,
                    "runtime_sidecars": runtime_artifacts,
                }
            )
            runtime_rows.append(
                {
                    "object_id": object_id,
                    "frame": "S",
                    "unit": "m",
                    "vertices": int(len(vertices_m)),
                    "triangles": int(len(faces)),
                    "solid_ids": sorted({int(value) for value in solid_ids}),
                    "mesh_volume_relative_error": mesh_volume_relative_error,
                    "cleanup": cleanup,
                    "manifold": manifold,
                    "artifacts": runtime_artifacts,
                    "derived_from_primary_step_sha256": step_record["sha256"],
                }
            )

    geometry_index = {
        "schema": "ROUTE_C_ROOT_STATIC_R20_GEOMETRY_INDEX_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "scope": "R121_PHASE_A_ROOT_STATIC_R20",
        "source_pins_verified": source_pin_count,
        "object_count": len(geometry_rows),
        "source_valid_closed_single_positive_brep_count": len(geometry_rows),
        "output_valid_closed_single_positive_step_count": len(geometry_rows),
        "source_frame": "A0_Q0_REFERENCE",
        "output_frame": "S",
        "primary_step_unit": "mm",
        "transform_name": "T_S_A0",
        "transform_application_count_per_object": 1,
        "objects": geometry_rows,
        "system_registry_rows_modified": 0,
        "system_pair_query_credit": 0,
        "verdict": "R20_STEP_FIRST_GEOMETRY_BUILT__LOCAL_CANDIDATE_ONLY",
    }
    geometry_bytes = stable_json_bytes(geometry_index)
    artifacts[GEOMETRY_INDEX] = geometry_bytes
    runtime_receipt = {
        "schema": "ROUTE_C_ROOT_STATIC_R20_RUNTIME_SIDECAR_DERIVATION_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "object_count": len(runtime_rows),
        "sidecar_set_count": len(runtime_rows),
        "sidecar_artifact_count": 3 * len(runtime_rows),
        "source": "REOPENED_PRIMARY_STEP_ONLY",
        "frame": "S",
        "length_unit": "m",
        "step_to_runtime_scale": 0.001,
        "scale_application_count": 1,
        "linear_deflection_mm": LINEAR_DEFLECTION_MM,
        "runtime_is_primary_geometry_authority": False,
        "objects": runtime_rows,
        "verdict": "20_OF_20_RUNTIME_SIDECAR_SETS_DERIVED_FROM_REOPENED_PRIMARY_STEP_IN_S_METRES",
    }
    runtime_bytes = stable_json_bytes(runtime_receipt)
    artifacts[RUNTIME_RECEIPT] = runtime_bytes
    build_receipt = {
        "schema": "ROUTE_C_ROOT_STATIC_R20_TWENTY_STEP_BUILD_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "scope": "R121_UMBRELLA_PHASE_A_ROOT_STATIC_R20",
        "contract_files": {
            "root_static_r20_contract": byte_record(CONTRACT_PATH, CONTRACT_PATH.read_bytes()),
            "source_authority_lock": byte_record(SOURCE_LOCK_PATH, SOURCE_LOCK_PATH.read_bytes()),
            "frame_and_unit_ledger": byte_record(FRAME_LEDGER_PATH, FRAME_LEDGER_PATH.read_bytes()),
        },
        "freecad_runtime": freecad_runtime,
        "source_document": extraction["source"],
        "source_document_opened_read_only": True,
        "source_document_saved_or_recomputed": False,
        "source_pins_verified": source_pin_count,
        "objects_requested": 20,
        "objects_emitted": len(geometry_rows),
        "primary_step_files": len(geometry_rows),
        "runtime_sidecar_files": 3 * len(runtime_rows),
        "generated_artifact_count_excluding_this_receipt": len(artifacts),
        "geometry_index": byte_record(GEOMETRY_INDEX, geometry_bytes),
        "runtime_sidecar_receipt": byte_record(RUNTIME_RECEIPT, runtime_bytes),
        "transform": {
            "name": "T_S_A0",
            "source_frame": "A0_Q0_REFERENCE",
            "target_frame": "S",
            "source_unit": "mm",
            "target_step_unit": "mm",
            "application_count_per_object": 1,
            "canonical_matrix_decimal_strings_mm": frame_ledger["phase_A_root_static_R20"]["canonical_matrix_decimal_strings_mm"],
        },
        "remaining_R101": "FAIL_CLOSED_HOST_AND_SPECIAL_MOTION_ADAPTER_HOLD",
        "pair_eligible": False,
        "system_operational_credit": False,
        "system_pair_query_credit": 0,
        "safe_edge_path_credit": False,
        "release_credit": False,
        "maximum_legal_claim": "TWENTY_LOCAL_S_FRAME_STEP_FIRST_ROOT_STATIC_ROUTE_C_COLLISION_GEOMETRY_CANDIDATES_BUILT",
        "verdict": "R20_PRIMARY_STEP_AND_RUNTIME_BUILD_PASS__R101_AND_SYSTEM_BINDING_REMAIN_HELD",
    }
    build_bytes = stable_json_bytes(build_receipt)
    artifacts[BUILD_RECEIPT] = build_bytes
    summary = {
        "artifacts": len(artifacts),
        "objects": len(geometry_rows),
        "steps": len(geometry_rows),
        "runtime_sidecars": 3 * len(runtime_rows),
        "source_pins": source_pin_count,
        "verdict": build_receipt["verdict"],
    }
    return artifacts, summary


def main() -> None:
    args = parse_args()
    artifacts, summary = build_artifacts()
    if args.write:
        for path, data in sorted(artifacts.items(), key=lambda item: item[0].as_posix()):
            atomic_write(path, data, replace=args.replace)
        summary["mode"] = "write"
        summary["written"] = len(artifacts)
    else:
        failures = []
        for path, expected in sorted(artifacts.items(), key=lambda item: item[0].as_posix()):
            if not path.is_file():
                failures.append({"path": path.relative_to(workspace_root()).as_posix(), "reason": "missing"})
            elif path.read_bytes() != expected:
                failures.append({"path": path.relative_to(workspace_root()).as_posix(), "reason": "byte_mismatch"})
        require(not failures, f"deterministic artifact check failed: {failures}")
        summary["mode"] = "check"
        summary["verified"] = len(artifacts)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
