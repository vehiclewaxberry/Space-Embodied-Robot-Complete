# -*- coding: utf-8 -*-
"""FreeCADCmd probe: can a per-configuration STEP be split into ARM vs
ENVIRONMENT purely by the labels STEP carries?

If yes, the whole pose-search phase can run offline on meshes and SolidWorks is
needed only for the authoritative final checks -- which matters because this
machine's SolidWorks both dies (low memory) and hangs.

usage:  FreeCADCmd fc_probe_step.py <step_path> <out_json>
"""
import json
import os
import sys

import FreeCAD
import Part

step = os.environ.get("F3R2_STEP") or (sys.argv[1] if len(sys.argv) > 1 else "")
outj = os.environ.get("F3R2_OUT") or (sys.argv[2] if len(sys.argv) > 2 else "")
print("ARGV:", sys.argv)
print("STEP:", repr(step), "exists:", os.path.isfile(step) if step else None)
print("OUT :", repr(outj))

rep = {"step": step, "bytes": os.path.getsize(step)}
doc = FreeCAD.newDocument("probe")
# FreeCADCmd (console) has no ImportGui; Part.insert only handles BREP there.
# The console-safe STEP reader is the Import module.
import Import  # noqa: E402
Import.insert(step, doc.Name)
rep["reader"] = "Import.insert"
objs = [o for o in doc.Objects if getattr(o, "Shape", None) is not None]
rep["n_objects"] = len(objs)
def corrected_box(o):
    """Parent-chain correction: obj.Shape carries only its OWN placement."""
    bb = o.Shape.BoundBox
    try:
        m = o.getGlobalPlacement().multiply(o.Placement.inverse()).toMatrix()
    except Exception:
        return [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
    xs, ys, zs = [], [], []
    for x in (bb.XMin, bb.XMax):
        for y in (bb.YMin, bb.YMax):
            for z in (bb.ZMin, bb.ZMax):
                v = m.multiply(FreeCAD.Vector(x, y, z))
                xs.append(v.x)
                ys.append(v.y)
                zs.append(v.z)
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


rows = []
for o in objs:
    sh = o.Shape
    try:
        box = [round(v, 3) for v in corrected_box(o)]
    except Exception:
        box = None
    rows.append({"label": o.Label, "name": o.Name,
                 "n_solids": len(sh.Solids) if hasattr(sh, "Solids") else 0,
                 "n_faces": len(sh.Faces) if hasattr(sh, "Faces") else 0,
                 "volume_mm3": round(sh.Volume, 3) if hasattr(sh, "Volume") else None,
                 "box_mm": box})
rep["objects"] = rows
with open(outj, "w", encoding="utf-8") as fh:
    json.dump(rep, fh, indent=1, ensure_ascii=False)
print("objects:", len(objs))
for r in rows[:40]:
    print("  %-52s solids=%-4s vol=%s" % (r["label"][:52], r["n_solids"],
                                          r["volume_mm3"]))
