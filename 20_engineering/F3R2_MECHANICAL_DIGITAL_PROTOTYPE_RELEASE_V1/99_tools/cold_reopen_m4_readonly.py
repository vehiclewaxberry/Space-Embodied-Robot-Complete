"""Read-only FreeCAD cold-reopen smoke check for the frozen M4 master."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App
import Part


M4_ROOT = Path(__file__).resolve().parents[1]
FCSTD = M4_ROOT / "02_parameterized_cad" / "SEI_DIGITAL_PROTOTYPE_V1.FCStd"
STEP = M4_ROOT / "02_parameterized_cad" / "SEI_DIGITAL_PROTOTYPE_V1.step"


master = App.openDocument(str(FCSTD))
try:
    links = [obj for obj in master.Objects if obj.TypeId == "App::Link"]
    sources = [
        obj
        for obj in master.Objects
        if obj.Name.startswith("SRC_")
        and hasattr(obj, "Shape")
        and not obj.Shape.isNull()
    ]
    fcstd_result = {
        "object_count": len(master.Objects),
        "app_part_count": sum(obj.TypeId == "App::Part" for obj in master.Objects),
        "app_link_count": len(links),
        "all_links_internal": all(
            obj.LinkedObject is not None and obj.LinkedObject.Document is master
            for obj in links
        ),
        "all_source_shapes_valid": all(obj.Shape.isValid() for obj in sources),
    }
finally:
    App.closeDocument(master.Name)

step_doc = App.newDocument("M4_ROOT_READONLY_STEP_REOPEN")
try:
    Part.insert(str(STEP), step_doc.Name)
    step_doc.recompute()
    shapes = [
        obj.Shape
        for obj in step_doc.Objects
        if hasattr(obj, "Shape") and not obj.Shape.isNull() and obj.Shape.Solids
    ]
    compound = Part.makeCompound(shapes)
    step_result = {
        "shape_object_count": len(shapes),
        "valid": compound.isValid(),
        "solid_count": len(compound.Solids),
    }
finally:
    App.closeDocument(step_doc.Name)

passed = (
    fcstd_result == {
        "object_count": 68,
        "app_part_count": 5,
        "app_link_count": 6,
        "all_links_internal": True,
        "all_source_shapes_valid": True,
    }
    and step_result == {
        "shape_object_count": 40,
        "valid": True,
        "solid_count": 40,
    }
)
message = "M4_ROOT_READONLY_COLD_REOPEN=" + json.dumps(
    {"passed": passed, "fcstd": fcstd_result, "step": step_result},
    sort_keys=True,
)
App.Console.PrintMessage(message + "\n")
sys.stdout.write(message + "\n")
sys.stdout.flush()
raise SystemExit(0 if passed else 2)
