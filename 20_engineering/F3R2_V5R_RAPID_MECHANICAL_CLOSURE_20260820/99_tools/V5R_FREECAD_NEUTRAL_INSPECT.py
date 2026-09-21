"""Read-only FreeCAD inspection for the V5R neutral fallback source."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App
import Part


def shape_facts(obj):
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        return None
    box = shape.BoundBox
    return {
        "label": obj.Label,
        "name": obj.Name,
        "shape_type": shape.ShapeType,
        "solids": len(shape.Solids),
        "shells": len(shape.Shells),
        "faces": len(shape.Faces),
        "volume_mm3": float(shape.Volume),
        "bounding_box_mm": [
            float(box.XMin), float(box.YMin), float(box.ZMin),
            float(box.XMax), float(box.YMax), float(box.ZMax),
        ],
    }


def inspect_fcstd(path: Path):
    doc = App.openDocument(str(path))
    try:
        rows = [row for obj in doc.Objects if (row := shape_facts(obj)) is not None]
        return {"kind": "FCStd", "objects": len(doc.Objects), "shape_objects": rows}
    finally:
        App.closeDocument(doc.Name)


def inspect_step(path: Path):
    doc = App.newDocument("V5R_STEP_READ_ONLY_INSPECT")
    try:
        Part.insert(str(path), doc.Name)
        doc.recompute()
        rows = [row for obj in doc.Objects if (row := shape_facts(obj)) is not None]
        return {"kind": "STEP", "objects": len(doc.Objects), "shape_objects": rows}
    finally:
        App.closeDocument(doc.Name)


def main():
    result = []
    for raw in sys.argv[1:]:
        path = Path(raw).resolve()
        item = {"path": path.as_posix(), "bytes": path.stat().st_size}
        item.update(inspect_fcstd(path) if path.suffix.lower() == ".fcstd" else inspect_step(path))
        result.append(item)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
