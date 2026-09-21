# -*- coding: utf-8 -*-
"""FreeCADCmd: read the TRUE B-rep of named wing-root parts from a STEP.

Tessellation cannot answer "is this a cylinder of radius 4.000".  A 0.5 mm
deflection turns a small cylinder into an 8-sided prism, which is exactly the
trap this probe avoids: it reports the analytic surface types and radii that
OpenCascade holds, not a mesh's opinion of them.

env: F3R2_STEP  F3R2_OUT  F3R2_PARTS (comma-separated label prefixes)
"""
import json
import os

import FreeCAD
import Import
import Part

STEP = os.environ["F3R2_STEP"]
OUT = os.environ["F3R2_OUT"]
WANT = [s.strip() for s in os.environ["F3R2_PARTS"].split(",") if s.strip()]

doc = FreeCAD.newDocument("brep")
Import.insert(STEP, doc.Name)
objs = [o for o in doc.Objects
        if getattr(o, "Shape", None) is not None and o.Shape.Solids]


def correction(o):
    try:
        return o.getGlobalPlacement().multiply(o.Placement.inverse())
    except Exception:
        return FreeCAD.Placement()


rep = {"schema": "F3R2_BREP_PROBE_V1", "step": STEP, "parts": {}}
for o in objs:
    if not any(o.Label.startswith(w) for w in WANT):
        continue
    m = correction(o).toMatrix()
    faces = []
    for f in o.Shape.Faces:
        s = f.Surface
        kind = type(s).__name__
        d = {"kind": kind, "area_mm2": round(f.Area, 4)}
        if kind == "Cylinder":
            c = m.multiply(FreeCAD.Vector(s.Center.x, s.Center.y, s.Center.z))
            ax = m.submatrix(3).multiply(
                FreeCAD.Vector(s.Axis.x, s.Axis.y, s.Axis.z))
            d.update({"radius_mm": round(s.Radius, 6),
                      "axis_xyz": [round(ax.x, 6), round(ax.y, 6),
                                   round(ax.z, 6)],
                      "centre_mm": [round(c.x, 4), round(c.y, 4),
                                    round(c.z, 4)]})
        elif kind == "Plane":
            n = m.submatrix(3).multiply(
                FreeCAD.Vector(s.Axis.x, s.Axis.y, s.Axis.z))
            p = m.multiply(FreeCAD.Vector(s.Position.x, s.Position.y,
                                          s.Position.z))
            d.update({"normal": [round(n.x, 4), round(n.y, 4), round(n.z, 4)],
                      "point_mm": [round(p.x, 3), round(p.y, 3),
                                   round(p.z, 3)]})
        faces.append(d)
    bb = o.Shape.BoundBox
    xs, ys, zs = [], [], []
    for x in (bb.XMin, bb.XMax):
        for y in (bb.YMin, bb.YMax):
            for z in (bb.ZMin, bb.ZMax):
                v = m.multiply(FreeCAD.Vector(x, y, z))
                xs.append(v.x)
                ys.append(v.y)
                zs.append(v.z)
    rep["parts"][o.Label] = {
        "n_faces": len(o.Shape.Faces), "n_solids": len(o.Shape.Solids),
        "volume_mm3": round(o.Shape.Volume, 4),
        "box_mm": [round(min(xs), 4), round(min(ys), 4), round(min(zs), 4),
                   round(max(xs), 4), round(max(ys), 4), round(max(zs), 4)],
        "surface_kinds": sorted({f["kind"] for f in faces}),
        "n_cylindrical_faces": sum(1 for f in faces if f["kind"] == "Cylinder"),
        "cylinder_radii_mm": sorted({f["radius_mm"] for f in faces
                                     if f["kind"] == "Cylinder"}),
        # every cylinder is kept (fastener hole patterns live here); planes are
        # capped because a detailed link has thousands of tiny ones
        "cylinders": [f for f in faces if f["kind"] == "Cylinder"],
        "faces": ([f for f in faces if f["kind"] != "Cylinder"][:60])}
    print("%-30s faces=%-4d kinds=%-24s cyl_radii=%s"
          % (o.Label, len(o.Shape.Faces),
             ",".join(rep["parts"][o.Label]["surface_kinds"])[:24],
             rep["parts"][o.Label]["cylinder_radii_mm"]))

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(rep, fh, indent=1, ensure_ascii=False)
print("probed parts:", len(rep["parts"]))
