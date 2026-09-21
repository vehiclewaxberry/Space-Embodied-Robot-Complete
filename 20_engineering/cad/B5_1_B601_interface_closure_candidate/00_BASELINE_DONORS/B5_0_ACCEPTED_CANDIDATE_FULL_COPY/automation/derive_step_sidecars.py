"""Derive STL and GLB sidecars from a candidate STEP with explicit checks.

The bundled CAD CLI 0.3.9 currently returns exit 0 for direct imported STEP
targets while producing its hidden topology GLB but not the requested STL/native
GLB sidecars.  This candidate-local OCP fallback is therefore kept explicit and
records that tool deviation instead of silently treating the absent files as a
successful export.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import trimesh
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.StlAPI import StlAPI_Writer


CANDIDATE = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def inside(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath(
            [str(path.resolve(strict=False)), str(root.resolve(strict=False))]
        ) == str(root.resolve(strict=False))
    except ValueError:
        return False


def require_candidate(path: Path, label: str) -> Path:
    path = path.resolve(strict=False)
    if not inside(path, CANDIDATE):
        raise ValueError(f"{label} escapes candidate root: {path}")
    return path


def record(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"missing or empty artifact: {path}")
    return {
        "path": path.relative_to(CANDIDATE).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=Path, required=True)
    parser.add_argument("--stl", type=Path, required=True)
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expected-step-sha256")
    parser.add_argument("--linear-deflection-mm", type=float, default=0.05)
    parser.add_argument("--angular-deflection-rad", type=float, default=0.25)
    args = parser.parse_args()

    step = require_candidate(args.step, "step")
    stl = require_candidate(args.stl, "stl")
    glb = require_candidate(args.glb, "glb")
    report_path = require_candidate(args.report, "report")
    if not step.is_file():
        raise SystemExit(f"STEP missing: {step}")
    for output in (stl, glb, report_path):
        if output.exists():
            raise SystemExit(f"overwrite forbidden: {output}")
    if args.linear_deflection_mm <= 0 or args.angular_deflection_rad <= 0:
        raise SystemExit("mesh tolerances must be positive")

    step_hash = sha256(step)
    expected = (args.expected_step_sha256 or "").upper()
    if expected and step_hash != expected:
        raise SystemExit(f"STEP hash mismatch: {step_hash} != {expected}")

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(step))
    if status != IFSelect_RetDone:
        raise SystemExit(f"STEP read failed: {status!r}")
    roots = int(reader.TransferRoots())
    shape = reader.OneShape()
    if roots <= 0 or shape.IsNull():
        raise SystemExit("STEP transfer yielded no shape")

    mesh = BRepMesh_IncrementalMesh(
        shape,
        float(args.linear_deflection_mm),
        False,
        float(args.angular_deflection_rad),
        True,
    )
    mesh.Perform()
    if not mesh.IsDone():
        raise SystemExit("OpenCascade triangulation failed")

    stl.parent.mkdir(parents=True, exist_ok=True)
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    if not writer.Write(shape, str(stl)):
        raise SystemExit("OpenCascade STL write failed")

    tri = trimesh.load_mesh(stl, force="mesh", process=False)
    if tri.is_empty or len(tri.faces) <= 0:
        raise SystemExit("derived STL contains no triangles")
    glb.parent.mkdir(parents=True, exist_ok=True)
    tri.export(glb, file_type="glb")
    glb_check = trimesh.load(glb, force="scene", process=False)
    geometries = list(glb_check.geometry.values())
    if not geometries or sum(len(item.faces) for item in geometries) <= 0:
        raise SystemExit("derived GLB contains no triangles")

    bounds = tri.bounds.tolist()
    report = {
        "gate_id": "B5_0_STEP_SIDECAR_DERIVATION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_step": record(step),
        "source_step_hash_match": not expected or step_hash == expected,
        "cad_cli_0_3_9_direct_step_sidecar_attempt": {
            "exit_code": 0,
            "requested_outputs_produced": False,
            "hidden_topology_glb_produced": True,
            "classification": "TOOL_DEVIATION_RECORDED_FALLBACK_USED",
        },
        "fallback": {
            "engine": "OpenCascade StlAPI plus trimesh GLB export",
            "linear_deflection_mm": args.linear_deflection_mm,
            "angular_deflection_rad": args.angular_deflection_rad,
        },
        "stl": {
            **record(stl),
            "triangles": int(len(tri.faces)),
            "vertices": int(len(tri.vertices)),
            "bounds_mm": bounds,
        },
        "glb": {
            **record(glb),
            "geometry_count": len(geometries),
            "triangles": int(sum(len(item.faces) for item in geometries)),
        },
        "verdict": "B5_0_STEP_SIDECAR_DERIVATION_PASS_WITH_TOOL_DEVIATION",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(report_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, report_path)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
