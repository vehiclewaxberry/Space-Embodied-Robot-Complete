"""Read-only FreeCAD/OCCT 7.8 per-face tessellation audit for B50.

Run this file with the explicitly located FreeCADCmd executable, not CPython.
It writes no CAD or mesh artifact and never modifies the source STEP.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import FreeCAD
import Part


SCRIPT_DIR = Path(__file__).resolve().parent
STEP_REL = Path(
    "20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/"
    "vendor_reference_linklocal/B50_REF_base_link_LINKLOCAL.step"
)
STEP_SHA256 = "A451B9150D00EC8E381AE69C0BB9D62B3A1FED1B1CD1AD373A719E28290F07C5"
LINEAR_DEFLECTION_MM = 0.05


def workspace_root() -> Path:
    for candidate in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root not found")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    step = workspace_root() / STEP_REL
    observed_hash = sha256(step)
    if observed_hash != STEP_SHA256:
        raise RuntimeError(f"STEP hash drift: {observed_hash}")
    shape = Part.read(str(step))
    if shape.isNull():
        raise RuntimeError("FreeCAD Part.read returned a null shape")

    missing = []
    triangle_count = 0
    face_count = 0
    positive_area_face_count = 0
    solid_rows = []
    for solid_index, solid in enumerate(shape.Solids):
        solid_triangles = 0
        solid_missing = 0
        for face_index, face in enumerate(solid.Faces):
            face_count += 1
            if face.Area > 0:
                positive_area_face_count += 1
            vertices, triangles = face.tessellate(LINEAR_DEFLECTION_MM)
            count = len(triangles)
            triangle_count += count
            solid_triangles += count
            if face.Area > 0 and count == 0:
                solid_missing += 1
                missing.append(
                    {
                        "solid_index": solid_index,
                        "face_index": face_index,
                        "area_mm2": float(face.Area),
                    }
                )
        solid_rows.append(
            {
                "solid_index": solid_index,
                "is_valid": bool(solid.isValid()),
                "is_closed": bool(solid.isClosed()),
                "faces": len(solid.Faces),
                "edges": len(solid.Edges),
                "volume_mm3": float(solid.Volume),
                "triangles": solid_triangles,
                "positive_area_faces_without_triangles": solid_missing,
            }
        )

    report = {
        "schema": "FREECAD78_B50_PER_FACE_TESSELLATION_AUDIT_V1",
        "source_step": {
            "path": STEP_REL.as_posix(),
            "sha256": observed_hash,
            "modified": False,
        },
        "runtime": {
            "freecad": FreeCAD.Version(),
            "occ": Part.OCC_VERSION,
        },
        "linear_deflection_mm": LINEAR_DEFLECTION_MM,
        "solid_count": len(shape.Solids),
        "face_count": face_count,
        "positive_area_face_count": positive_area_face_count,
        "triangle_count_sum_of_per_face_tessellations": triangle_count,
        "positive_area_faces_without_triangles": len(missing),
        "missing_faces": missing,
        "brep_valid_solid_count": sum(row["is_valid"] for row in solid_rows),
        "brep_closed_solid_count": sum(row["is_closed"] for row in solid_rows),
        "aggregate_per_solid_volume_mm3": sum(row["volume_mm3"] for row in solid_rows),
        "per_solid": solid_rows,
        "source_step_written": False,
        "pass": len(missing) == 0,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
