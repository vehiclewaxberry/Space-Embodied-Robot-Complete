# -*- coding: utf-8 -*-
"""FreeCADCmd: split a per-configuration STEP into ARM / ENVIRONMENT and write
per-part STL meshes in the assembly coordinate frame.

Why: SolidWorks on this machine dies (fatal low-memory dialog) or hangs during
whole-assembly interference detection, so the pose search cannot live there.
The STEP files exported and hash-bound during G2 carry the same geometry with
per-component labels, and FreeCAD tessellates them offline at controlled
deflection.  SolidWorks stays the authority for the FINAL native check; this is
the search instrument, and every mesh records the deflection it was built with
so no one mistakes a tessellation for the B-rep.

The arm is NOT meshed here -- its authoritative collision geometry is the
accepted URDF's own STL set, in link frames, which is what the pose search must
move.  Only the arm's as-built bounding box is recorded, as a registration
cross-check for the composed arm.

env:  F3R2_STEP  F3R2_OUTDIR  F3R2_TAG  [F3R2_DEFLECTION]
"""
import json
import os

import FreeCAD
import Import
import Mesh
import MeshPart

STEP = os.environ["F3R2_STEP"]
OUTDIR = os.environ["F3R2_OUTDIR"]
TAG = os.environ["F3R2_TAG"]
LIN = float(os.environ.get("F3R2_DEFLECTION", "0.4"))
ANG = 0.35

os.makedirs(OUTDIR, exist_ok=True)
rep = {"schema": "F3R2_ENV_MESH_V1", "step": STEP, "tag": TAG,
       "linear_deflection_mm": LIN, "angular_deflection_rad": ANG,
       "frame": "top-assembly frame of the F3R1/F3R2 baseline (mm)"}

doc = FreeCAD.newDocument("env")
Import.insert(STEP, doc.Name)
objs = [o for o in doc.Objects
        if getattr(o, "Shape", None) is not None and o.Shape.Solids]
rep["n_solid_objects"] = len(objs)
rep["placement_mode"] = ("parent-chain correction applied to each MESH "
                         "(shape copies exhaust memory on this machine)")


def parent_correction(o):
    """STEP import builds a container hierarchy: obj.Shape already carries the
    object's OWN placement but not its parents'.  A naive BoundBox therefore
    reports parent-local coordinates -- caught by an arm-registration
    cross-check that came out 480 mm off.  The missing factor is
    global * own^-1, applied to the tessellated mesh (cheap) rather than to the
    B-rep (which runs this machine out of memory)."""
    try:
        return o.getGlobalPlacement().multiply(o.Placement.inverse())
    except Exception:
        return FreeCAD.Placement()


def corrected_box(o):
    """AABB of the parent-corrected shape, from its 8 transformed corners."""
    bb = o.Shape.BoundBox
    m = parent_correction(o).toMatrix()
    xs, ys, zs = [], [], []
    for x in (bb.XMin, bb.XMax):
        for y in (bb.YMin, bb.YMax):
            for z in (bb.ZMin, bb.ZMax):
                v = m.multiply(FreeCAD.Vector(x, y, z))
                xs.append(v.x)
                ys.append(v.y)
                zs.append(v.z)
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def group_of(label):
    if label.startswith("B51_"):
        return "ARM"
    if label.startswith("WING_L"):
        return "WING_L"
    if label.startswith("WING_R"):
        return "WING_R"
    if ("Launch_Lock_Interface_Reference" in label
            or "Release_Clearance_Envelope" in label):
        return "REFERENCE_ONLY"
    return "BUS"


def base_label(label):
    return label.rstrip("0123456789") or label


groups, parts = {}, {}
for o in objs:
    g = group_of(o.Label)
    groups.setdefault(g, []).append(o)
    # The CAD arm is NOT the URDF mesh set: a link-by-link box comparison shows
    # the B51 CAD links carry detail the URDF STLs lack (link6 +46 mm) while the
    # URDF base_link keeps a vendor base plate the integration replaced.  For
    # MECHANICAL clearance the CAD is the truth, so arm links are exported per
    # link too, and posed later by the accepted URDF's kinematics.
    parts.setdefault(base_label(o.Label), []).append(o)

rep["group_counts"] = {k: len(v) for k, v in groups.items()}


def box_of(shapes):
    b = None
    for s in shapes:
        c = corrected_box(s)
        b = c if b is None else [min(b[i], c[i]) for i in range(3)] + \
            [max(b[i + 3], c[i + 3]) for i in range(3)]
    return [round(v, 4) for v in b]


def mesh_group(shapes, path):
    total = None
    for s in shapes:
        m = MeshPart.meshFromShape(Shape=s.Shape, LinearDeflection=LIN,
                                   AngularDeflection=ANG, Relative=False)
        m.transform(parent_correction(s).toMatrix())
        if total is None:
            total = m
        else:
            total.addMesh(m)
    if total is None:
        return None
    total.write(path)
    return {"path": path, "triangles": total.CountFacets,
            "points": total.CountPoints,
            "bytes": os.path.getsize(path)}


# ---- ARM: box only (URDF STLs are the authoritative arm collision geometry) --
if "ARM" in groups:
    rep["arm_as_built_box_mm"] = box_of(groups["ARM"])
    rep["arm_solid_objects"] = len(groups["ARM"])

# ---- environment groups + per-part meshes ----
rep["groups"] = {}
for g in ("BUS", "WING_L", "WING_R", "REFERENCE_ONLY"):
    if g not in groups:
        rep["groups"][g] = {"status": "ABSENT_IN_THIS_CONFIGURATION"}
        continue
    p = os.path.join(OUTDIR, "%s_%s.stl" % (TAG, g))
    info = mesh_group(groups[g], p)
    info["box_mm"] = box_of(groups[g])
    info["n_objects"] = len(groups[g])
    rep["groups"][g] = info
    print("group %-16s objects=%-4d tris=%-8s" % (g, len(groups[g]),
                                                  info["triangles"]))

rep["parts"] = {}
pdir = os.path.join(OUTDIR, "parts_%s" % TAG)
os.makedirs(pdir, exist_ok=True)
for name, shapes in sorted(parts.items()):
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    p = os.path.join(pdir, "%s.stl" % safe)
    info = mesh_group(shapes, p)
    info["box_mm"] = box_of(shapes)
    info["n_objects"] = len(shapes)
    info["group"] = group_of(shapes[0].Label)
    rep["parts"][name] = info

with open(os.path.join(OUTDIR, "ENV_MESH_%s.json" % TAG), "w",
          encoding="utf-8") as fh:
    json.dump(rep, fh, indent=1, ensure_ascii=False)
print("parts meshed:", len(rep["parts"]))
print("arm box:", rep.get("arm_as_built_box_mm"))
