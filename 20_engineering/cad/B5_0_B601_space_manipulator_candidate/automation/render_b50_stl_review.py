"""Render an auditable review PNG from a STEP-derived B5.0 STL sidecar."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import vtk
from vtk.util.numpy_support import vtk_to_numpy


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]


def inside(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath(
            [str(path.resolve(strict=False)), str(root.resolve(strict=False))]
        ) == str(root.resolve(strict=False))
    except ValueError:
        return False


def candidate_path(path: Path, label: str) -> Path:
    resolved = path.resolve(strict=False)
    if not inside(resolved, CANDIDATE_ROOT):
        raise SystemExit(f"{label} escapes candidate root: {resolved}")
    return resolved


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def artifact(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise SystemExit(f"missing or empty artifact: {path}")
    return {
        "path": path.relative_to(CANDIDATE_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    args = parser.parse_args()

    stl = candidate_path(args.stl, "stl")
    output = candidate_path(args.output, "output")
    report_path = candidate_path(args.report, "report")
    if not stl.is_file():
        raise SystemExit(f"STL missing: {stl}")
    for path in (output, report_path):
        if path.exists():
            raise SystemExit(f"overwrite forbidden: {path}")
    if args.width < 640 or args.height < 480:
        raise SystemExit("review image dimensions are too small")

    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(stl))
    reader.Update()
    poly = reader.GetOutput()
    if poly is None or poly.GetNumberOfPoints() <= 0:
        raise SystemExit("VTK STL reader returned no geometry")
    bounds = [float(value) for value in poly.GetBounds()]
    center = (
        0.5 * (bounds[0] + bounds[1]),
        0.5 * (bounds[2] + bounds[3]),
        0.5 * (bounds[4] + bounds[5]),
    )
    extents = (
        bounds[1] - bounds[0],
        bounds[3] - bounds[2],
        bounds[5] - bounds[4],
    )
    diagonal = sum(value * value for value in extents) ** 0.5
    if diagonal <= 0.0:
        raise SystemExit("STL bounds are degenerate")

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.SplittingOff()
    normals.Update()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    mapper.ScalarVisibilityOff()
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(0.78, 0.83, 0.88)
    actor.GetProperty().SetAmbient(0.42)
    actor.GetProperty().SetDiffuse(0.66)
    actor.GetProperty().SetSpecular(0.18)
    actor.GetProperty().SetSpecularPower(24.0)
    actor.GetProperty().EdgeVisibilityOn()
    actor.GetProperty().SetEdgeColor(0.20, 0.27, 0.34)
    actor.GetProperty().SetLineWidth(0.35)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.055, 0.075, 0.105)
    renderer.SetBackground2(0.19, 0.24, 0.30)
    renderer.GradientBackgroundOn()
    renderer.AddActor(actor)
    camera = renderer.GetActiveCamera()
    camera.SetFocalPoint(*center)
    camera.SetPosition(
        center[0] + 1.55 * diagonal,
        center[1] - 1.80 * diagonal,
        center[2] + 1.15 * diagonal,
    )
    camera.SetViewUp(0.0, 0.0, 1.0)
    camera.ParallelProjectionOn()
    camera.SetParallelScale(0.62 * max(extents))
    renderer.ResetCameraClippingRange()

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(args.width, args.height)
    window.SetMultiSamples(0)
    window.AddRenderer(renderer)
    window.Render()

    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.SetScale(1)
    capture.SetInputBufferTypeToRGBA()
    capture.ReadFrontBufferOff()
    capture.Update()
    captured = capture.GetOutput()
    rgba = vtk_to_numpy(captured.GetPointData().GetScalars()).reshape(
        args.height, args.width, -1
    )
    rgb = rgba[:, :, :3].astype("int16")
    left = rgb[:, :8, :].mean(axis=1, keepdims=True)
    right = rgb[:, -8:, :].mean(axis=1, keepdims=True)
    background = 0.5 * (left + right)
    foreground_mask = abs(rgb - background).sum(axis=2) > 24.0
    foreground_pixels = int(foreground_mask.sum())
    foreground_ratio = foreground_pixels / float(args.width * args.height)
    if foreground_ratio < 0.002:
        raise SystemExit(
            "rendered image contains no reviewable foreground geometry: "
            f"foreground_ratio={foreground_ratio:.8f}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(output))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()
    if not output.is_file() or output.stat().st_size <= 0:
        raise SystemExit("VTK did not produce a review PNG")

    report = {
        "gate_id": "B5_0_VISUAL_REVIEW_RENDER",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_stl": artifact(stl),
        "source_geometry": {
            "points": int(poly.GetNumberOfPoints()),
            "polygons": int(poly.GetNumberOfPolys()),
            "bounds_mm": {
                "min": [bounds[0], bounds[2], bounds[4]],
                "max": [bounds[1], bounds[3], bounds[5]],
            },
        },
        "image": artifact(output),
        "image_validation": {
            "foreground_pixels": foreground_pixels,
            "foreground_ratio": foreground_ratio,
            "minimum_ratio": 0.002,
        },
        "renderer": {
            "engine": f"VTK {vtk.vtkVersion.GetVTKVersion()}",
            "offscreen": True,
            "width": args.width,
            "height": args.height,
            "projection": "parallel",
            "camera": "explicit_isometric_position_from_bounds",
        },
        "cad_snapshot_tool": {
            "attempts": 3,
            "result": "TOOL_DEVIATION_BROWSER_RESOURCE_FAILURE",
            "fallback": "VTK_OFFSCREEN_FROM_SAME_STEP_DERIVED_STL",
        },
        "claim_limit": (
            "visual review only; STL omits four null-triangulation faces and "
            "does not supersede the cold-verified STEP"
        ),
        "verdict": "B5_0_VISUAL_REVIEW_RENDER_PASS_WITH_TOOL_DEVIATION",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(report_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, report_path)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
