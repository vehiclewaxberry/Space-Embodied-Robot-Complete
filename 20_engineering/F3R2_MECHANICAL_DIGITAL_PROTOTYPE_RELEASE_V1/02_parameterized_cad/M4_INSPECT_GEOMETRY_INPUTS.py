"""Read-only FreeCAD geometry inventory for M4 source selection."""

import json
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
AUTH = ROOT / "20_engineering" / "cad" / "freecad_authoritative"


def metric(obj):
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull() or len(shape.Solids) == 0:
        return None
    box = shape.BoundBox
    return {
        "name": obj.Name,
        "label": obj.Label,
        "type_id": obj.TypeId,
        "shape_type": shape.ShapeType,
        "valid": shape.isValid(),
        "solids": len(shape.Solids),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "volume_mm3": shape.Volume,
        "bbox_mm": [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax],
    }


records = []
for path in sorted(AUTH.glob("B601_CARRIER_*.FCStd")):
    doc = App.openDocument(str(path))
    try:
        records.append({"path": path.name, "objects": [row for obj in doc.Objects if (row := metric(obj)) is not None]})
    finally:
        App.closeDocument(doc.Name)

step = AUTH / "B601_KINEMATIC_ASSEMBLY_Q0_WITNESS.step"
doc = App.newDocument("M4_Q0_INSPECT")
try:
    Part.insert(str(step), doc.Name)
    doc.recompute()
    records.append({"path": step.name, "objects": [row for obj in doc.Objects if (row := metric(obj)) is not None]})
finally:
    App.closeDocument(doc.Name)

print(json.dumps(records, indent=2))
