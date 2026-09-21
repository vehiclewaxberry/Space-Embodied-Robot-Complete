#!/usr/bin/env python3
"""Cold-reopen neutral R1 exports and refresh the evidence diagram/manifest."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import trimesh
from build123d import import_step


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RAPID = ROOT / "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
TOOLS = RAPID / "99_tools"
MAIN_SCRIPT = TOOLS / "gripper_r1_build_and_validate.py"
VALIDATION = RAPID / "04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json"
REOPEN = RAPID / "04_validation/GRIPPER_R1_NEUTRAL_REOPEN_VALIDATION.json"
MANIFEST = RAPID / "07_evidence/GRIPPER_R1_OUTPUT_MANIFEST_SHA256.txt"
DIAGRAM = RAPID / "07_evidence/GRIPPER_R1_SWEEP_AND_INTERFERENCE_DIAGRAM.png"
CAD = RAPID / "01_native_cad/gripper_r1"


def load_main() -> Any:
    spec = importlib.util.spec_from_file_location("gripper_r1_build", MAIN_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load gripper R1 main script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stl_fact(path: Path) -> dict[str, Any]:
    mesh = trimesh.load_mesh(path, process=False)
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.to_geometry()
        mesh = trimesh.util.concatenate(tuple(mesh.values()))
    return {
        "path": str(path.resolve()).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": main.sha256(path),
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "volume_mm3": float(mesh.volume),
        "bounds_mm": mesh.bounds.tolist(),
    }


main = load_main()
data = json.loads(VALIDATION.read_text(encoding="utf-8"))
if REOPEN.exists():
    raise RuntimeError(f"write-once reopen receipt exists: {REOPEN}")

correlation = data["neutral_to_v5_fingerprint_correlation"]["rows"]
targets = set(data["correction"]["target_palm_bodies"])
target_boxes = {row["source_name"]: row["neutral_bbox_mm"] for row in correlation if row["source_name"] in targets}
main.make_diagram(
    target_boxes,
    data["correction"]["left_sweep_features"],
    data["correction"]["right_sweep_features"],
    float(data["metrics"]["removed_volume_mm3"]),
)

expected_volumes = {
    "B601_GRIPPER_PALM_RAIL_SLOT_R1.step": float(data["metrics"]["neutral_r1_palm_volume_mm3"]),
    "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step": None,
    "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step": None,
}
step_rows = {}
step_pass = True
for name, expected in expected_volumes.items():
    path = CAD / name
    shape = import_step(path)
    volume = float(shape.volume)
    delta = None if expected is None else abs(volume - expected)
    row = {
        **main.file_fact(path),
        "valid": bool(shape.is_valid),
        "solid_count": len(shape.solids()),
        "volume_mm3": volume,
        "expected_volume_mm3": expected,
        "volume_abs_delta_mm3": delta,
    }
    row["pass"] = row["valid"] and row["solid_count"] > 0 and (delta is None or delta <= 1.0e-5)
    step_pass = step_pass and row["pass"]
    step_rows[name] = row

stl_names = [
    "B601_GRIPPER_PALM_RAIL_SLOT_R1.stl",
    "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.stl",
    "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.stl",
    "B601_GRIPPER_LEFT_FINGER_NEUTRAL_SOURCE.stl",
    "B601_GRIPPER_RIGHT_FINGER_NEUTRAL_SOURCE.stl",
]
stl_rows = {name: stl_fact(CAD / name) for name in stl_names}
stl_pass = all(row["bytes"] > 0 and row["vertex_count"] > 0 and row["face_count"] > 0 for row in stl_rows.values())

receipt = {
    "schema": "F3R2_V5R_GRIPPER_R1_NEUTRAL_REOPEN_VALIDATION_V1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if step_pass and stl_pass else "HOLD",
    "scope": "NEUTRAL_STEP_AND_MESH_READABILITY_ONLY",
    "step_reopen": step_rows,
    "stl_reopen": stl_rows,
    "diagram": main.file_fact(DIAGRAM),
    "native_v5_reintegration": "HOLD_NOT_TESTED",
    "manufacturing_clearance": "PROVISIONAL_CLEARANCE_HOLD",
    "structural_strength": "HOLD",
}
REOPEN.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

stroke = data["continuous_stroke_acceptance"]
stroke["r1_four_pose_boolean_complete"] = bool(stroke["four_pose_boolean_complete"])
stroke["original_reference_boolean_complete"] = all(
    pose["left_original_target_palm_overlap_mm3"] is not None and pose["right_original_target_palm_overlap_mm3"] is not None
    for pose in stroke["poses"].values()
)
stroke["four_pose_boolean_complete_scope"] = "R1_CORRECTED_TARGET_PALM_BOOLEAN_ONLY"
data["post_export_reopen"] = receipt
data["outputs"][DIAGRAM.name] = main.file_fact(DIAGRAM)
data["outputs"][REOPEN.name] = main.file_fact(REOPEN)
VALIDATION.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

manifest_paths = []
for row in data["outputs"].values():
    path = Path(row["path"])
    if path.is_file() and path not in manifest_paths:
        manifest_paths.append(path)
for path in (REOPEN, VALIDATION):
    if path not in manifest_paths:
        manifest_paths.append(path)
MANIFEST.write_text(
    "\n".join(f"{main.sha256(path)}  {path.relative_to(RAPID).as_posix()}" for path in manifest_paths) + "\n",
    encoding="utf-8",
)

print(json.dumps({"status": receipt["status"], "step_reopen": step_rows, "diagram": receipt["diagram"]}, indent=2))
