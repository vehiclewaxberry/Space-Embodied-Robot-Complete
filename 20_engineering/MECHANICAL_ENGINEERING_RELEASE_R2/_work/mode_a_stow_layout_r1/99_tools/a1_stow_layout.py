"""A1 - Mode A interleaved stow layout, step 1.

Builds a single multi-body STEP containing:
  * the 10 B601 link convex hulls at the optimised stow pose q_stow
  * the 12U envelope drawn as 12 edge rails (so the arm stays visible)
in the project S frame (x in [-170.25,170.25], y,z in [-113.15,113.15]).

Also reports per-face protrusion and a slice-by-slice footprint map so the
bus can be laid out around the arm instead of the arm bolted onto the bus.

Reference geometry only. Writes nothing into project authority.
"""
import numpy as np, trimesh, os, json
from scipy.spatial import ConvexHull

from OCP.gp import gp_Pnt
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid)
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRep import BRep_Builder
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone

MESH = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper"
OUT = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_stow_layout_r1"
os.makedirs(OUT, exist_ok=True)

# 12U in project S frame (mm)
HX, HY, HZ = 170.25, 113.15, 113.15
RAIL = 6.0  # edge-rail cross-section for visibility

Q_STOW = np.radians([1.79, -0.54, -0.26, 89.45, -45.65, -1.08])

JOINTS = [
    ("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1)),
    ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1)),
    ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1)),
    ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1)),
    ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1)),
    ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1)),
]
FIXED = [("gripper_link", "link6", (0, 0, 0.15971), (0, -1.5708, 0)),
         ("gripper_left", "gripper_link", (-0.042091, 2.7531e-05, -1.3031e-05), (0, 0, -1.5708)),
         ("gripper_right", "gripper_link", (-0.042091, -2.7531e-05, 1.3031e-05), (0, 0, 1.5708))]


def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]])


def Tm(xyz, r):
    M = np.eye(4); M[:3, :3] = r; M[:3, 3] = xyz; return M


def arot(a, q):
    a = np.asarray(a, float); a = a/np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(q)*K + (1-np.cos(q))*K@K


# ---- FK, per-link hulls in mm ----
Tw = {"base_link": np.eye(4)}
for i, (c, p, xyz, rr, ax) in enumerate(JOINTS):
    Tw[c] = Tw[p] @ (Tm(xyz, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, Q_STOW[i])))
for c, p, xyz, rr in FIXED:
    Tw[c] = Tw[p] @ Tm(xyz, rpy(*rr))

links = {}
for f in sorted(os.listdir(MESH)):
    if not f.lower().endswith(".stl"):
        continue
    n = f[:-4]
    m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
    V = np.asarray(m.convex_hull.vertices, float)*1000.0
    links[n] = V @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0

ALL = np.vstack(list(links.values()))

# ---- align stow OBB to the S-frame axes, longest -> X ----
hull = trimesh.convex.convex_hull(trimesh.PointCloud(ALL))
Tobb, ext = trimesh.bounds.oriented_bounds(hull)      # Tobb maps world -> obb frame
R = Tobb[:3, :3]; t = Tobb[:3, 3]
order = np.argsort(ext)[::-1]                          # longest first
P = np.eye(3)[order]                                   # permutation, rows pick axes
def to_box(X):
    return (X @ R.T + t) @ P.T

links_b = {k: to_box(v) for k, v in links.items()}
allb = np.vstack(list(links_b.values()))
allb -= (allb.max(0) + allb.min(0)) / 2.0              # centre in the 12U
links_b = {k: v - (np.vstack(list(links_b.values())).max(0) +
                   np.vstack(list(links_b.values())).min(0))/2.0 for k, v in links_b.items()}

ext_s = np.sort(ext)[::-1]
box = np.array([2*HX, 2*HY, 2*HZ])
prot = (ext_s - box) / 2.0                             # protrusion per face, mm

# ---- slice footprint map along X ----
NS = 14
edges = np.linspace(-HX, HX, NS+1)
slices = []
for i in range(NS):
    m = (allb[:, 0] >= edges[i]) & (allb[:, 0] < edges[i+1])
    if m.sum() < 3:
        slices.append((edges[i], edges[i+1], 0.0, 0.0)); continue
    S = allb[m]
    slices.append((edges[i], edges[i+1], S[:, 1].max()-S[:, 1].min(),
                   S[:, 2].max()-S[:, 2].min()))

# ---- OCP solids ----
def hull_solid(pts):
    h = ConvexHull(pts)
    sew = BRepBuilderAPI_Sewing(1e-4)
    for s in h.simplices:
        poly = BRepBuilderAPI_MakePolygon()
        for idx in s:
            poly.Add(gp_Pnt(*pts[idx]))
        poly.Close()
        face = BRepBuilderAPI_MakeFace(poly.Wire())
        if face.IsDone():
            sew.Add(face.Face())
    sew.Perform()
    shell = TopoDS.Shell_s(sew.SewedShape())
    return BRepBuilderAPI_MakeSolid(shell).Solid()


def rail(p0, p1):
    d = np.array(p1) - np.array(p0)
    ax = int(np.argmax(np.abs(d)))
    dims = [RAIL, RAIL, RAIL]; dims[ax] = float(abs(d[ax]))
    org = [min(p0[i], p1[i]) - (0 if i == ax else RAIL/2) for i in range(3)]
    return BRepPrimAPI_MakeBox(gp_Pnt(*org), *dims).Shape()


comp = TopoDS_Compound(); bld = BRep_Builder(); bld.MakeCompound(comp)
for k, v in links_b.items():
    bld.Add(comp, hull_solid(v))
C = [(sx*HX, sy*HY, sz*HZ) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
for a in range(8):
    for b in range(a+1, 8):
        d = np.abs(np.array(C[a]) - np.array(C[b]))
        if (d > 1e-6).sum() == 1:
            bld.Add(comp, rail(C[a], C[b]))

w = STEPControl_Writer()
w.Transfer(comp, STEPControl_AsIs)
p = os.path.join(OUT, "A1_STOW_LAYOUT_R1.step")
assert w.Write(p) == IFSelect_RetDone
print("wrote", p, os.path.getsize(p), "bytes")

print("\n" + "="*74)
print("A1  STOWED ARM vs 12U ENVELOPE  (S frame, arm OBB axis-aligned & centred)")
print("="*74)
print(f"  stow OBB      = {ext_s[0]:.1f} x {ext_s[1]:.1f} x {ext_s[2]:.1f} mm")
print(f"  12U box       = {box[0]:.1f} x {box[1]:.1f} x {box[2]:.1f} mm")
print(f"  protrusion/face = X {prot[0]:+.1f}   Y {prot[1]:+.1f}   Z {prot[2]:+.1f} mm")
print(f"  CDS  allows +6.55/face -> X {'OK' if prot[0]<=6.55 else 'FAIL'}"
      f"  Y {'OK' if prot[1]<=6.55 else 'FAIL'}  Z {'OK' if prot[2]<=6.55 else 'FAIL'}")
print(f"  NanoRacks +9.50/face  -> X {'OK' if prot[0]<=9.5 else 'FAIL'}"
      f"  Y {'OK' if prot[1]<=9.5 else 'FAIL'}  Z {'OK' if prot[2]<=9.5 else 'FAIL'}")
print("\n  footprint per 24.3 mm slice along X  (Y x Z extent of the arm):")
print(f"  {'x_lo':>8s} {'x_hi':>8s} {'dY':>8s} {'dZ':>8s}   free area fraction of 226.3^2")
for a, b, dy, dz in slices:
    frac = 1.0 - (dy*dz)/(2*HY*2*HZ)
    bar = "#" * int(40*(dy*dz)/(2*HY*2*HZ))
    print(f"  {a:8.1f} {b:8.1f} {dy:8.1f} {dz:8.1f}   {frac*100:5.1f}%  {bar}")
print("="*74)
json.dump(dict(q_stow_deg=np.degrees(Q_STOW).tolist(), obb_mm=ext_s.tolist(),
               box_mm=box.tolist(), protrusion_per_face_mm=prot.tolist(),
               slices=[list(map(float, s)) for s in slices]),
          open(os.path.join(OUT, "A1_STOW_LAYOUT_R1.json"), "w"), indent=1)
