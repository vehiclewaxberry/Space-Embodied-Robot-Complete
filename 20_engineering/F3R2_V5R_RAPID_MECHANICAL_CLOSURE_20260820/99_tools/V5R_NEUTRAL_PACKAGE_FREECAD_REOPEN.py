"""Independent read-only reopen check for the packaged V5R STEP and FCStd."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App
import Part


PROJECT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ROUND = PROJECT / r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
PACKAGE = ROUND / r"06_pack_and_go\V5R_NEUTRAL_OPERATIONAL_PACKAGE"
STEP = PACKAGE / r"cad\SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.step"
FCSTD = PACKAGE / r"cad\SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.FCStd"
SOURCE_STEP = ROUND / r"01_native_cad\SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.step"
SOURCE_FCSTD = ROUND / r"01_native_cad\SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.FCStd"
RECEIPT = ROUND / r"04_validation\V5R_NEUTRAL_PACKAGE_INDEPENDENT_REOPEN.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def shape_summary(shape) -> dict:
    box = shape.BoundBox
    return {
        "shape_type": shape.ShapeType,
        "solids": len(shape.Solids),
        "faces": len(shape.Faces),
        "volume_mm3": float(shape.Volume),
        "bounding_box_mm": [
            float(box.XMin), float(box.YMin), float(box.ZMin),
            float(box.XMax), float(box.YMax), float(box.ZMax),
        ],
    }


def select_deployed(objects):
    shaped = [obj for obj in objects if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0]
    if not shaped:
        raise RuntimeError("NO_SOLID_BEARING_OBJECT")
    return max(shaped, key=lambda obj: len(obj.Shape.Solids))


def reopen_fcstd(path: Path) -> dict:
    doc = App.openDocument(str(path))
    try:
        obj = select_deployed(doc.Objects)
        return {"object_count": len(doc.Objects), "selected_label": obj.Label, **shape_summary(obj.Shape)}
    finally:
        App.closeDocument(doc.Name)


def reopen_step(path: Path) -> dict:
    doc = App.newDocument("V5R_PACKAGE_STEP_REOPEN")
    try:
        Part.insert(str(path), doc.Name)
        doc.recompute()
        # STEP import intentionally flattens this export into 457 independent
        # solid objects.  Validate their aggregate, not a name-arbitrary member.
        shapes = [obj.Shape for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0]
        shape = Part.makeCompound(shapes)
        return {"object_count": len(doc.Objects), "selected_label": "AGGREGATE_OF_ALL_SOLID_OBJECTS", **shape_summary(shape)}
    finally:
        App.closeDocument(doc.Name)


def main() -> None:
    for path in (STEP, FCSTD, SOURCE_STEP, SOURCE_FCSTD):
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"REQUIRED_FILE_MISSING:{path}")
    if RECEIPT.exists():
        raise RuntimeError(f"WRITE_ONCE_RECEIPT_EXISTS:{RECEIPT}")
    hashes = {
        "packaged_step": sha256(STEP),
        "source_step": sha256(SOURCE_STEP),
        "packaged_fcstd": sha256(FCSTD),
        "source_fcstd": sha256(SOURCE_FCSTD),
    }
    if hashes["packaged_step"] != hashes["source_step"] or hashes["packaged_fcstd"] != hashes["source_fcstd"]:
        raise RuntimeError("PACKAGE_CAD_COPY_HASH_MISMATCH")
    step = reopen_step(STEP)
    fcstd = reopen_fcstd(FCSTD)
    if step["solids"] != 457 or fcstd["solids"] != 457:
        raise RuntimeError(f"SOLID_COUNT_DRIFT:step={step['solids']}:fcstd={fcstd['solids']}")
    if step["bounding_box_mm"] != fcstd["bounding_box_mm"]:
        delta = max(abs(a - b) for a, b in zip(step["bounding_box_mm"], fcstd["bounding_box_mm"]))
        if delta > 1e-6:
            raise RuntimeError(f"STEP_FCSTD_BOUNDING_BOX_DRIFT:{delta}")
    payload = {
        "schema": "V5R_NEUTRAL_PACKAGE_INDEPENDENT_REOPEN_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "memory_gate_passed": False,
        "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY",
        "owner_override_used": True,
        "mode": "FREECAD_READ_ONLY_NO_SAVE",
        "hashes": hashes,
        "step_reopen": step,
        "fcstd_reopen": fcstd,
        "missing_reference_semantics": "MONOLITHIC_STEP_AND_FCSTD_HAVE_NO_EXTERNAL_FILE_REFERENCES",
        "package_addenda_integration_status": "HOLD_NOT_MONOLITHICALLY_PLACED",
        "verdict": "NEUTRAL_PACKAGE_CAD_INDEPENDENT_REOPEN_PASS",
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with RECEIPT.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"verdict": payload["verdict"], "receipt": RECEIPT.as_posix()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
