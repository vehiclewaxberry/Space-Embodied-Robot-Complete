"""Form the write-once V5R neutral fallback from already verified F3R2 assets.

This script does not drive SolidWorks.  It copies the source STEP/FCStd/visual STL
without replacement and creates a coarse, conservative scene collision mesh from
the exact deployed compound in the FCStd document.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App
import MeshPart


PROJECT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ROUND = PROJECT / r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
SOURCE_ROOT = PROJECT / r"20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"

SOURCE_STEP = SOURCE_ROOT / r"03_native_cad\F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step"
SOURCE_FCSTD = SOURCE_ROOT / r"03_native_cad\F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.FCStd"
SOURCE_VISUAL = SOURCE_ROOT / r"05_clearance\mesh\parts_DEPLOYED\F3R1_V3_DEPLOYED_NOMINAL.stl"

OUTPUT_STEP = ROUND / r"01_native_cad\SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.step"
OUTPUT_FCSTD = ROUND / r"01_native_cad\SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.FCStd"
OUTPUT_VISUAL = ROUND / r"01_native_cad\SEI_MECH_B601_V5R_VISUAL_MESH.stl"
OUTPUT_COLLISION = ROUND / r"01_native_cad\SEI_MECH_B601_V5R_COLLISION_MESH.stl"
RECEIPT = ROUND / r"04_validation\V5R_FALLBACK_B_NEUTRAL_FORMATION_RECEIPT.json"

EXPECTED = {
    SOURCE_STEP: "A7549D0E913584FA4AF894A710F5CE9DF363722FD7F4F863B1C3B3FF2B4653C2",
    SOURCE_FCSTD: "7D423A2F19E34A04238AF82629875FDB320D841EE89F78051B454E737B9AF53A",
    SOURCE_VISUAL: "3147B19B669639EF3915CEB8B577BA0E331EA812FDDB508C3E76DF5C3A253208",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def fact(path: Path) -> dict:
    return {
        "path": path.resolve().as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def copy_once(source: Path, target: Path) -> None:
    if target.exists():
        raise RuntimeError(f"WRITE_ONCE_TARGET_EXISTS:{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as destination, source.open("rb") as origin:
        shutil.copyfileobj(origin, destination, 8 * 1024 * 1024)
    shutil.copystat(source, target)


def main() -> None:
    for path, expected in EXPECTED.items():
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"SOURCE_MISSING:{path}")
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"SOURCE_HASH_DRIFT:{path}:{actual}:{expected}")
    if RECEIPT.exists() or OUTPUT_COLLISION.exists():
        raise RuntimeError("WRITE_ONCE_RECEIPT_OR_COLLISION_EXISTS")

    copy_once(SOURCE_STEP, OUTPUT_STEP)
    copy_once(SOURCE_FCSTD, OUTPUT_FCSTD)
    copy_once(SOURCE_VISUAL, OUTPUT_VISUAL)

    doc = App.openDocument(str(OUTPUT_FCSTD))
    try:
        matches = doc.getObjectsByLabel("F3R1_V3_DEPLOYED_NOMINAL")
        matches = [obj for obj in matches if hasattr(obj, "Shape") and not obj.Shape.isNull()]
        if len(matches) != 1:
            raise RuntimeError(f"DEPLOYED_COMPOUND_CARDINALITY:{len(matches)}")
        obj = matches[0]
        shape = obj.Shape
        box = shape.BoundBox
        shape_summary = {
            "label": obj.Label,
            "shape_type": shape.ShapeType,
            "solid_count": len(shape.Solids),
            "face_count": len(shape.Faces),
            "volume_mm3": float(shape.Volume),
            "bounding_box_mm": [
                float(box.XMin), float(box.YMin), float(box.ZMin),
                float(box.XMax), float(box.YMax), float(box.ZMax),
            ],
        }
        if shape_summary["solid_count"] != 457:
            raise RuntimeError(f"DEPLOYED_SOLID_COUNT_DRIFT:{shape_summary['solid_count']}")
        mesh = MeshPart.meshFromShape(
            Shape=shape,
            LinearDeflection=4.0,
            AngularDeflection=0.5235987755982988,
            Relative=False,
        )
        if mesh.CountFacets <= 0:
            raise RuntimeError("COLLISION_MESH_EMPTY")
        mesh.write(str(OUTPUT_COLLISION))
        collision_summary = {
            "facet_count": int(mesh.CountFacets),
            "point_count": int(mesh.CountPoints),
            "linear_deflection_mm": 4.0,
            "angular_deflection_rad": 0.5235987755982988,
            "role": "CONSERVATIVE_SCENE_COLLISION_MESH",
            "limitation": "BROAD_PHASE_BOOTSTRAP; NARROW_PHASE/CONTACT FIDELITY HOLD",
        }
    finally:
        App.closeDocument(doc.Name)

    outputs = [OUTPUT_STEP, OUTPUT_FCSTD, OUTPUT_VISUAL, OUTPUT_COLLISION]
    for path in outputs:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"OUTPUT_MISSING_OR_EMPTY:{path}")
    if sha256(OUTPUT_STEP) != EXPECTED[SOURCE_STEP]:
        raise RuntimeError("STEP_COPY_HASH_MISMATCH")
    if sha256(OUTPUT_FCSTD) != EXPECTED[SOURCE_FCSTD]:
        raise RuntimeError("FCSTD_COPY_HASH_MISMATCH")
    if sha256(OUTPUT_VISUAL) != EXPECTED[SOURCE_VISUAL]:
        raise RuntimeError("VISUAL_COPY_HASH_MISMATCH")

    payload = {
        "schema": "V5R_FALLBACK_B_NEUTRAL_FORMATION_RECEIPT_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "owner_ruling": "AUTHORIZE_LOW_MEMORY_EXECUTION_WITH_BOUNDED_NATIVE_ATTEMPTS",
        "memory_gate_passed": False,
        "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY",
        "owner_override_used": True,
        "native_recovery_attempts_consumed": 2,
        "native_top_assembly_status": "HOLD",
        "neutral_operational_baseline_status": "PASS",
        "formation": "HASH_PINNED_BYTE_IDENTICAL_COPIES_PLUS_FREECAD_COARSE_TESSELLATION",
        "source_scope": "F3R2_DEPLOYED_OPERATIONAL_GEOMETRY; V5 ADDENDA ARE PACKAGE-BOUND SEPARATE ASSETS",
        "shape_summary": shape_summary,
        "collision_summary": collision_summary,
        "sources": [fact(path) for path in EXPECTED],
        "outputs": [fact(path) for path in outputs],
        "missing_asset_count": 0,
        "verdict": "V5R_NEUTRAL_OPERATIONAL_BASELINE_FORMED_WITH_NATIVE_TOP_HOLD",
        "non_claims": [
            "NOT A FRESH SOLIDWORKS EXPORT",
            "NATIVE TOP ASSEMBLY NOT PASSED",
            "GRIPPER R1 IS A SEPARATE PACKAGE ASSET UNTIL INTEGRATION AUTHORITY EXISTS",
            "FLIGHT/LAUNCH/FASTENER/HDRM QUALIFICATION NOT CLAIMED",
        ],
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with RECEIPT.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"verdict": payload["verdict"], "receipt": fact(RECEIPT)}, indent=2))


if __name__ == "__main__":
    main()
