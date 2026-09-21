# -*- coding: utf-8 -*-
"""FreeCADCmd: export the gripper's INDIVIDUAL solids as meshes.

The main environment export groups solids by stripped label, so all 58
`B51_REF_gripper_detail_LINKLOCAL###` bodies collapse into one mesh -- which is
exactly how the record came to say "the CAD carries a SINGLE gripper solid".
This export keeps them apart so the two fingers can be moved independently and
tested against each other with real geometry rather than bounding boxes.

env: F3R2_STEP  F3R2_OUTDIR  F3R2_PREFIX  [F3R2_DEFLECTION]
"""
import json
import os

import FreeCAD
import Import
import MeshPart

STEP = os.environ["F3R2_STEP"]
OUTDIR = os.environ["F3R2_OUTDIR"]
PREFIX = os.environ["F3R2_PREFIX"]
LIN = float(os.environ.get("F3R2_DEFLECTION", "0.25"))
ANG = 0.25

os.makedirs(OUTDIR, exist_ok=True)
doc = FreeCAD.newDocument("grip")
Import.insert(STEP, doc.Name)


def correction(o):
    try:
        return o.getGlobalPlacement().multiply(o.Placement.inverse())
    except Exception:
        return FreeCAD.Placement()


rep = {"schema": "F3R2_GRIPPER_SOLID_MESH_V1", "step": STEP,
       "linear_deflection_mm": LIN, "angular_deflection_rad": ANG,
       "solids": {}}
n = 0
for o in doc.Objects:
    s = getattr(o, "Shape", None)
    if s is None or not s.Solids:
        continue
    if not o.Label.startswith(PREFIX):
        continue
    m = MeshPart.meshFromShape(Shape=s, LinearDeflection=LIN,
                               AngularDeflection=ANG, Relative=False)
    m.transform(correction(o).toMatrix())
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in o.Label)
    p = os.path.join(OUTDIR, "%s.stl" % safe)
    m.write(p)
    bb = m.BoundBox
    rep["solids"][o.Label] = {
        "path": p, "triangles": m.CountFacets, "points": m.CountPoints,
        "volume_mm3": round(s.Volume, 4), "n_faces": len(s.Faces),
        "box_mm": [round(bb.XMin, 4), round(bb.YMin, 4), round(bb.ZMin, 4),
                   round(bb.XMax, 4), round(bb.YMax, 4), round(bb.ZMax, 4)]}
    n += 1
    if n % 10 == 0:
        print("meshed", n)

with open(os.path.join(OUTDIR, "GRIPPER_SOLID_MESHES.json"), "w",
          encoding="utf-8") as fh:
    json.dump(rep, fh, indent=1, ensure_ascii=False)
print("gripper solids meshed:", n)
