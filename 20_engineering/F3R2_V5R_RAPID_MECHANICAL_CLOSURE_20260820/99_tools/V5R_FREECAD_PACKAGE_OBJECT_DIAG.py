"""Print only the largest shape-bearing objects in packaged neutral CAD."""

from pathlib import Path
import json

import FreeCAD as App
import Part

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820\06_pack_and_go\V5R_NEUTRAL_OPERATIONAL_PACKAGE\cad")


def row(obj):
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        return None
    box = shape.BoundBox
    return {
        "name": obj.Name,
        "label": obj.Label,
        "type": shape.ShapeType,
        "solids": len(shape.Solids),
        "faces": len(shape.Faces),
        "volume": float(shape.Volume),
        "box": [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax],
    }


def summarize(doc):
    rows = [item for obj in doc.Objects if (item := row(obj)) is not None]
    rows.sort(key=lambda item: (item["solids"], item["faces"], item["volume"]), reverse=True)
    solid_shapes = [getattr(obj, "Shape") for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) > 0]
    compound = Part.makeCompound(solid_shapes)
    return {"objects": len(doc.Objects), "shape_objects": len(rows), "top": rows[:20], "aggregate_shape_count": len(solid_shapes), "aggregate_solids_with_duplicates": len(compound.Solids)}


fcstd = ROOT / "SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.FCStd"
step = ROOT / "SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.step"

doc = App.openDocument(str(fcstd))
try:
    fcstd_result = summarize(doc)
finally:
    App.closeDocument(doc.Name)

doc = App.newDocument("V5R_STEP_OBJECT_DIAG")
try:
    Part.insert(str(step), doc.Name)
    doc.recompute()
    step_result = summarize(doc)
finally:
    App.closeDocument(doc.Name)

print(json.dumps({"fcstd": fcstd_result, "step": step_result}, indent=2))
