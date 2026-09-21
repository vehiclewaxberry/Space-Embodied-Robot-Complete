#!/usr/bin/env python3
"""Independent link2 B12 validator. It deliberately imports no builder module."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape
from OCP.gp import gp_Trsf


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = next(candidate for candidate in (PACKAGE, *PACKAGE.parents) if (candidate / "PROJECT_MAP.md").is_file())
CONTRACT = PACKAGE / "00_contract/LINK2_B12_OPERATIONAL_COLLISION_CONTRACT_V1.json"
LOCK = PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"
LEDGER = PACKAGE / "00_contract/FRAME_UNIT_AND_UNCERTAINTY_LEDGER_V1.json"
REEXTRACTOR = PACKAGE / "04_validation/reextract_link2_b12_independent.py"
GEOMETRY_INDEX = PACKAGE / "05_results/LINK2_B12_GEOMETRY_INDEX_V1.json"
RUNTIME_RECEIPT = PACKAGE / "05_results/LINK2_B12_RUNTIME_SIDECAR_RECEIPT_V1.json"
POSE_RECEIPT = PACKAGE / "05_results/LINK2_B12_POSE_ADAPTER_SAMPLES_V1.json"
OUTPUT_GEOMETRY = PACKAGE / "05_results/INDEPENDENT_LINK2_B12_VALIDATION_V1.json"
OUTPUT_POSE = PACKAGE / "05_results/INDEPENDENT_POSE_ADAPTER_VALIDATION_V1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def stable(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def strict_json(path: Path) -> dict[str, Any]:
    def hook(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {key}: {path}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=hook)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def record(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def locate_freecad() -> Path:
    paths = []
    if os.environ.get("ROUTE_C_FREECAD_PYTHON"):
        paths.append(Path(os.environ["ROUTE_C_FREECAD_PYTHON"]))
    paths.extend([Path(r"G:\Windows_program_file\FreeCAD\bin\python.exe"), Path(r"C:\Program Files\FreeCAD 1.1\bin\python.exe")])
    return next(path.resolve() for path in paths if path.is_file())


def read_brep(path: Path):
    shape = TopoDS_Shape()
    require(BRepTools.Read_s(shape, str(path), BRep_Builder()), f"BREP read failed: {path}")
    return shape


def read_step(path: Path):
    reader = STEPControl_Reader()
    require(reader.ReadFile(str(path)) == IFSelect_RetDone, f"STEP read failed: {path}")
    roots = int(reader.TransferRoots())
    require(roots == 1, f"STEP root count is {roots}: {path}")
    shape = reader.OneShape()
    require(not shape.IsNull(), f"STEP null shape: {path}")
    return shape, roots


def volume(shape) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties, False, False, True)
    return float(properties.Mass())


def bbox(shape) -> np.ndarray:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    return np.asarray(box.Get(), dtype=np.float64).reshape(2, 3)


def solid_check(shape, context: str) -> dict[str, Any]:
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    require(count == 1, f"{context}: solid count {count}")
    shell = TopExp_Explorer(shape, TopAbs_SHELL)
    shell_count, closed = 0, True
    while shell.More():
        shell_count += 1
        closed &= bool(BRep_Tool.IsClosed_s(shell.Current()))
        shell.Next()
    value = volume(shape)
    require(BRepCheck_Analyzer(shape, True).IsValid() and shell_count > 0 and closed and math.isfinite(value) and value > 0, f"{context}: invalid/open/nonpositive")
    return {"solid_count": count, "shell_count": shell_count, "closed": closed, "volume_mm3": value, "bbox_mm": bbox(shape)}


def transform(shape, matrix: np.ndarray):
    trsf = gp_Trsf()
    trsf.SetValues(*(float(matrix[row, col]) for row in range(3) for col in range(4)))
    operation = BRepBuilderAPI_Transform(shape, trsf, True)
    operation.Build()
    require(operation.IsDone(), "independent BRep transform failed")
    return operation.Shape()


def cut_volume(left, right) -> float:
    operation = BRepAlgoAPI_Cut(left, right)
    operation.Build()
    require(operation.IsDone(), "independent BRep cut failed")
    return abs(volume(operation.Shape()))


def rpy(r: float, p: float, y: float) -> np.ndarray:
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.asarray([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr], [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]], dtype=np.float64)


def rodrigues(axis: np.ndarray, q: float) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    skew = np.asarray([[0, -z, y], [z, 0, -x], [-y, x, 0]], dtype=np.float64)
    return np.eye(3) * math.cos(q) + (1-math.cos(q))*np.outer(axis, axis) + math.sin(q)*skew


def independent_fk(urdf: Path) -> tuple[dict[str, Any], Any]:
    document = ET.parse(urdf).getroot()

    def parse(name: str, parent: str, child: str) -> tuple[dict[str, Any], Any]:
        matches = [item for item in document.findall("joint") if item.get("name") == name]
        require(len(matches) == 1, f"independent {name} count drift")
        item = matches[0]
        require(item.get("type") == "revolute" and item.find("parent").get("link") == parent and item.find("child").get("link") == child, f"independent {name} topology drift")
        xyz_raw = item.find("origin").get("xyz").split()
        rpy_raw = item.find("origin").get("rpy").split()
        axis_raw = item.find("axis").get("xyz").split()
        xyz = np.asarray([float(v) for v in xyz_raw], dtype=np.float64)
        angles = np.asarray([float(v) for v in rpy_raw], dtype=np.float64)
        axis = np.asarray([float(v) for v in axis_raw], dtype=np.float64)
        require(np.all(np.isfinite(xyz)) and np.all(np.isfinite(angles)) and np.all(np.isfinite(axis)) and np.linalg.norm(axis) > 0, f"independent {name} numeric drift")
        lower_raw, upper_raw = item.find("limit").get("lower"), item.find("limit").get("upper")
        lower, upper = float(lower_raw), float(upper_raw)
        require(math.isfinite(lower) and math.isfinite(upper) and lower < upper, f"independent {name} limits drift")
        origin = np.eye(4)
        origin[:3, :3] = rpy(*angles)
        origin[:3, 3] = xyz

        def one(q: float) -> np.ndarray:
            require(math.isfinite(q) and lower <= q <= upper, f"independent {name} limit rejection")
            motion = np.eye(4)
            motion[:3, :3] = rodrigues(axis, q)
            return origin @ motion

        raw = {"axis": axis_raw, "child": child, "limit_lower_rad": lower_raw, "limit_upper_rad": upper_raw, "origin_rpy_rad": rpy_raw, "origin_xyz_m": xyz_raw, "parent": parent}
        return raw, one

    raw1, fk1 = parse("joint1", "base_link", "link1")
    raw2, fk2 = parse("joint2", "link1", "link2")

    def fk(q1: float, q2: float) -> np.ndarray:
        return fk1(q1) @ fk2(q2)

    return {"joint1": raw1, "joint2": raw2}, fk


def manifold(faces: np.ndarray) -> dict[str, int | bool]:
    faces = np.asarray(faces, dtype=np.int64)
    directed = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    undirected = np.sort(directed, axis=1)
    _, inverse, counts = np.unique(undirected, axis=0, return_inverse=True, return_counts=True)
    boundary = int(np.count_nonzero(counts == 1)); nonmanifold = int(np.count_nonzero(counts > 2))
    forward = np.bincount(inverse, weights=(directed[:, 0] < directed[:, 1]).astype(np.int8), minlength=len(counts))
    mismatch = int(np.count_nonzero(forward != counts-forward))
    return {"boundary_edge_count": boundary, "nonmanifold_edge_count": nonmanifold, "orientation_mismatch_edge_count": mismatch, "closed_oriented_two_manifold": boundary == nonmanifold == mismatch == 0}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--write", action="store_true"); args = parser.parse_args()
    contract, lock, ledger = strict_json(CONTRACT), strict_json(LOCK), strict_json(LEDGER)
    require(len(contract["objects"]) == 12 and lock["source_pin_count"] == 10 and len(lock["source_pins"]) == 10, "contract/source count drift")
    paths = {}
    for pin in lock["source_pins"]:
        path = ROOT / pin["path"]
        require(path.is_file() and path.stat().st_size == pin["bytes"] and sha256(path) == pin["sha256"], f"independent source pin drift: {pin['id']}")
        paths[pin["id"]] = path
    registry = strict_json(paths["m01_registry"])
    all_link2 = {row["object_id"]: row for row in registry["objects"] if row["category"] == "R" and row["parent_frame"] == "link2"}
    selected = {row["object_id"] for row in contract["objects"]}
    excluded = set(contract["excluded_j3_carriage_objects"])
    require(len(all_link2) == 20 and len(selected) == 12 and len(excluded) == 8 and selected.isdisjoint(excluded) and selected | excluded == set(all_link2), "independent exact link2 selected/excluded partition drift")
    exact = {object_id: all_link2[object_id] for object_id in selected}
    raw_joints, fk = independent_fk(paths["accepted_urdf"])
    mount_document = strict_json(paths["execution_mount_12dp"])
    strings = mount_document["binding"]["canonical_matrix_decimal_strings"]
    require(mount_document["binding"]["canonical_decimal_places"] == 12 and all(len(v.rsplit('.',1)[-1]) == 12 for row in strings for v in row), "independent 12dp mount spelling drift")
    mount = np.asarray([[float(v) for v in row] for row in strings], dtype=np.float64)
    t0 = fk(0.0, 0.0); inv0 = np.linalg.inv(t0)
    inv0_mm = inv0.copy(); inv0_mm[:3, 3] *= 1000.0
    t0_mm = t0.copy(); t0_mm[:3, 3] *= 1000.0

    geometry_index = strict_json(GEOMETRY_INDEX); runtime_receipt = strict_json(RUNTIME_RECEIPT); pose_receipt = strict_json(POSE_RECEIPT)
    geometry_by_id = {row["object_id"]: row for row in geometry_index["objects"]}; runtime_by_id = {row["object_id"]: row for row in runtime_receipt["objects"]}
    freecad = locate_freecad()
    object_rows = []
    with tempfile.TemporaryDirectory(prefix="route_c_link2_b12_independent_") as directory_name:
        directory = Path(directory_name)
        completed = subprocess.run([str(freecad), str(REEXTRACTOR), "--output-dir", str(directory)], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="strict", check=False)
        require(completed.returncode == 0 and not completed.stderr.strip(), f"independent source re-extraction failed: {completed.stdout} {completed.stderr}")
        extraction = json.loads(completed.stdout)
        require(extraction["verdict"] == "INDEPENDENT_SOURCE_REEXTRACTION_12_OF_12_PASS" and extraction["object_placement_reapplied"] is False, "independent source extraction verdict drift")
        require(sum(not row["source_object_placement_is_identity"] for row in extraction["objects"]) == 7, "independent nonidentity placement count drift")
        source_by_id = {row["object_id"]: row for row in extraction["objects"]}
        for spec in contract["objects"]:
            object_id = spec["object_id"]
            source = read_brep(directory / source_by_id[object_id]["brep"]["filename"]); source_metric = solid_check(source, f"{object_id} source")
            step_path = PACKAGE / "01_cad" / spec["output"]
            step, roots = read_step(step_path); step_metric = solid_check(step, f"{object_id} STEP")
            expected = transform(source, inv0_mm); expected_metric = solid_check(expected, f"{object_id} expected link2")
            forward_difference = cut_volume(expected, step); reverse_difference = cut_volume(step, expected)
            recovered = transform(step, t0_mm); recovered_forward = cut_volume(source, recovered); recovered_reverse = cut_volume(recovered, source)
            difference_limit = contract["tolerances"]["brep_roundtrip_symmetric_difference_mm3"]
            require(max(forward_difference, reverse_difference, recovered_forward, recovered_reverse) <= difference_limit, f"bilateral BRep difference drift: {object_id}")
            require(abs(step_metric["volume_mm3"]-source_metric["volume_mm3"])/source_metric["volume_mm3"] <= contract["tolerances"]["step_reopen_volume_relative"], f"volume drift: {object_id}")
            runtime = runtime_by_id[object_id]; npz_record = runtime["artifacts"]["npz"]; npz_path = ROOT / npz_record["path"]
            require(record(npz_path) == npz_record, f"NPZ hash drift: {object_id}")
            with np.load(npz_path, allow_pickle=False) as archive:
                vertices = archive["vertices_m"]; faces = archive["faces"]
            topo = manifold(faces); require(topo["closed_oriented_two_manifold"], f"runtime nonmanifold: {object_id}")
            for kind in ("ply", "stl"):
                require(record(ROOT / runtime["artifacts"][kind]["path"]) == runtime["artifacts"][kind], f"runtime {kind} hash drift: {object_id}")
            mesh_volume = abs(float(np.einsum("ij,ij->i", vertices[faces][:,0], np.cross(vertices[faces][:,1], vertices[faces][:,2])).sum()/6.0))*1e9
            mesh_relative = abs(mesh_volume-step_metric["volume_mm3"])/step_metric["volume_mm3"]
            require(mesh_relative <= contract["tolerances"]["runtime_mesh_volume_relative"], f"runtime volume drift: {object_id}")
            object_rows.append({
                "object_id": object_id, "step": record(step_path), "step_transfer_root_count": roots,
                "source_valid_closed_positive_single_solid": True, "step_valid_closed_positive_single_solid": True,
                "source_volume_mm3": source_metric["volume_mm3"], "step_volume_mm3": step_metric["volume_mm3"],
                "expected_to_step_cut_mm3": forward_difference, "step_to_expected_cut_mm3": reverse_difference,
                "source_to_roundtrip_cut_mm3": recovered_forward, "roundtrip_to_source_cut_mm3": recovered_reverse,
                "expected_link2_bbox_mm": expected_metric["bbox_mm"].tolist(), "step_bbox_mm": step_metric["bbox_mm"].tolist(),
                "runtime_vertices": int(len(vertices)), "runtime_triangles": int(len(faces)), "runtime_manifold": topo,
                "runtime_mesh_volume_relative_error": mesh_relative,
            })
    geometry_document = {
        "schema": "ROUTE_C_LINK2_B12_INDEPENDENT_VALIDATION_V1", "generated_utc": "DETERMINISTIC_VALIDATION_NO_WALLCLOCK",
        "validator_imports_builder": False, "source_pin_count_verified": len(paths), "exact_registry_link2_object_count": len(exact),
        "excluded_J3_carriage_object_count": len(excluded), "nonidentity_source_object_placement_count": 7,
        "object_count": len(object_rows), "bilateral_brep_difference_pass_count": len(object_rows),
        "runtime_closed_oriented_two_manifold_pass_count": len(object_rows), "objects": object_rows,
        "system_registry_rows_modified": 0, "system_pair_query_credit": 0,
        "maximum_legal_claim": contract["maximum_legal_claim"],
        "verdict": "INDEPENDENT_LINK2_B12_STEP_BREP_RUNTIME_VALIDATION_PASS__LOCAL_CANDIDATE_ONLY",
    }
    pose_samples = []
    expected_pose_grid = [(q1, q2) for q1 in ("-2.8", "0", "2.8") for q2 in ("-3.14", "-1.57", "0")]
    require([(row["q1_rad"], row["q2_rad"]) for row in ledger["pose_samples"]] == expected_pose_grid, "independent nine-point q1/q2 Cartesian grid drift")
    sample_by_name = {row["sample"]: row for row in pose_receipt["samples"]}
    require(len(sample_by_name) == len(pose_receipt["samples"]) == 9, "independent pose sample count or uniqueness drift")
    ignored_q1_residuals = []
    sign_reversed_q1_residuals = []
    for sample in ledger["pose_samples"]:
        q1 = float(sample["q1_rad"])
        q2 = float(sample["q2_rad"])
        expected = mount @ fk(q1, q2)
        actual = np.asarray(sample_by_name[sample["sample"]]["T_S_link2_m"], dtype=np.float64)
        residual = float(np.max(np.abs(actual-expected))); require(residual <= contract["tolerances"]["fk_matrix_max_abs"], f"pose sample residual drift: {sample['sample']}")
        pose_samples.append({"sample": sample["sample"], "q1_rad": q1, "q2_rad": q2, "matrix_max_abs_residual": residual})
        ignored_q1_residuals.append(float(np.max(np.abs(expected - mount @ fk(0.0, q2)))))
        sign_reversed_q1_residuals.append(float(np.max(np.abs(expected - mount @ fk(-q1, q2)))))
    q0_closure = float(np.max(np.abs((mount @ fk(0.0, 0.0)) @ inv0 - mount)))
    require(q0_closure <= contract["tolerances"]["fk_matrix_max_abs"], "independent q0 S closure drift")
    require(raw_joints == pose_receipt["joint_chain_raw"], "builder/independent raw URDF numeric spelling mismatch")
    require(max(ignored_q1_residuals) > contract["tolerances"]["fk_matrix_max_abs"], "q1-ignored fault is not observable on pose grid")
    require(max(sign_reversed_q1_residuals) > contract["tolerances"]["fk_matrix_max_abs"], "q1-sign-reversed fault is not observable on pose grid")
    pose_document = {
        "schema": "ROUTE_C_LINK2_B12_INDEPENDENT_POSE_ADAPTER_VALIDATION_V1", "generated_utc": "DETERMINISTIC_VALIDATION_NO_WALLCLOCK",
        "validator_imports_builder": False, "accepted_urdf_raw_numeric_spelling": raw_joints,
        "execution_mount_12dp_strings_consumed_directly": strings, "execution_mount_reconstructed_from_25deg": False,
        "historical_D6_mount_used": False, "q0_source_A0_to_link2_to_S_closure_max_abs": q0_closure,
        "sample_count": len(pose_samples), "sample_grid": ledger["pose_sample_grid"], "samples": pose_samples,
        "q1_fault_sensitivity": {
            "ignored_q1_max_abs_residual": max(ignored_q1_residuals),
            "ignored_q1_rejected": True,
            "sign_reversed_q1_max_abs_residual": max(sign_reversed_q1_residuals),
            "sign_reversed_q1_rejected": True
        },
        "side_effect_free": True, "system_authority_changed": False,
        "verdict": "INDEPENDENT_ACCEPTED_URDF_JOINT1_JOINT2_FK_AND_12DP_MOUNT_POSE_ADAPTER_PASS",
    }
    if args.write:
        atomic_write(OUTPUT_GEOMETRY, stable(geometry_document)); atomic_write(OUTPUT_POSE, stable(pose_document))
    print(json.dumps({"geometry_objects": len(object_rows), "pose_samples": len(pose_samples), "geometry_verdict": geometry_document["verdict"], "pose_verdict": pose_document["verdict"], "mode": "write" if args.write else "check"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
