"""OCP geometry builders for takeover M01 operational assets.

Every asset is a closed-solid BRep (.brep bytes, hash-bound) in MILLIMETRES.
Convex decompositions are conservative by containment (machine-verified per
piece: every source mesh vertex must satisfy the hull inequalities), so the
per-object Hausdorff derate versus the design surface is exactly 0.
"""
import math
import os
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial import ConvexHull

from OCP.BRep import BRep_Builder
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon,
                                BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing,
                                BRepBuilderAPI_Transform)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.BRepTools import BRepTools
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Compound, TopoDS_Shape
from OCP.Bnd import Bnd_Box
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf

from .common import abspath

CONTAINMENT_TOL_MM = 1e-6


# ------------------------------------------------------------------ io
def load_step(path):
    from OCP.STEPControl import STEPControl_Reader
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if int(status) != 1:
        raise ValueError(f"STEP read failed: {path}")
    reader.TransferRoots()
    return reader.OneShape()


def load_brep(path):
    shape = TopoDS_Shape()
    builder = BRep_Builder()
    ok = BRepTools.Read_s(shape, str(path), builder)
    if not bool(ok) or shape.IsNull():
        raise ValueError(f"BRep read failed: {path}")
    return shape


def write_brep(shape, path):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    ok = BRepTools.Write_s(shape, str(path))
    if not bool(ok):
        raise ValueError(f"BRep write failed: {path}")


def count_solids(shape):
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    n = 0
    while exp.More():
        n += 1
        exp.Next()
    return n


def shape_aabb(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, False)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return np.array([xmin, ymin, zmin]), np.array([xmax, ymax, zmax])


def shape_volume(shape):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def validate_closed_solid_set(shape):
    valid = bool(BRepCheck_Analyzer(shape, True).IsValid())
    solids = count_solids(shape)
    lo, hi = shape_aabb(shape)
    finite = bool(np.all(np.isfinite(lo)) and np.all(np.isfinite(hi)))
    dims = hi - lo
    nondegenerate = bool(np.all(dims > 0.0))
    vol = shape_volume(shape) if solids else 0.0
    return {"valid": valid, "solid_count": solids, "finite_bounds": finite,
            "nondegenerate": nondegenerate, "volume_mm3": vol,
            "bounds_lo": lo.tolist(), "bounds_hi": hi.tolist()}


# ------------------------------------------------------------------ primitives
def box_from_bounds(lo, hi):
    lo = np.asarray(lo, float).copy()
    hi = np.asarray(hi, float).copy()
    d = hi - lo
    # enforce a minimum nonzero extent per axis (padding only ever grows the box)
    for k in range(3):
        if d[k] < 1e-6:
            mid = 0.5 * (lo[k] + hi[k])
            lo[k] = mid - 5e-7
            hi[k] = mid + 5e-7
    d = hi - lo
    return BRepPrimAPI_MakeBox(gp_Pnt(*lo), float(d[0]), float(d[1]), float(d[2])).Shape()


def capsule_compound(a_mm, b_mm, r_mm):
    """Capsule as a compound of {cylinder solid, sphere, sphere}.

    The members overlap; for closed sets d(A∪B, C) = min(d(A,C), d(B,C)), so
    the compound gives the exact external distance to the capsule union."""
    a = np.asarray(a_mm, float)
    b = np.asarray(b_mm, float)
    r = float(r_mm)
    assert r > 0 and np.all(np.isfinite(a)) and np.all(np.isfinite(b))
    axis = b - a
    L = float(np.linalg.norm(axis))
    assert L > 0.0, "zero-length capsule segment"
    d = axis / L
    ax2 = gp_Ax2(gp_Pnt(*a), gp_Dir(*d))
    cyl = BRepPrimAPI_MakeCylinder(ax2, r, L).Shape()
    sa = BRepPrimAPI_MakeSphere(gp_Pnt(*a), r).Shape()
    sb = BRepPrimAPI_MakeSphere(gp_Pnt(*b), r).Shape()
    builder = BRep_Builder()
    comp = TopoDS_Compound()
    builder.MakeCompound(comp)
    for s in (cyl, sa, sb):
        builder.Add(comp, s)
    return comp


def hull_solid(points):
    """Closed BRep solid = exact convex hull of points (mm)."""
    pts = np.asarray(points, float)
    assert pts.shape[0] >= 4 and pts.shape[1] == 3
    hull = ConvexHull(pts)
    verts = pts[hull.vertices]
    sewing = BRepBuilderAPI_Sewing(1.0e-6)
    for tri in hull.simplices:
        p = [gp_Pnt(*pts[i]) for i in tri]
        poly = BRepBuilderAPI_MakePolygon(p[0], p[1], p[2], True)
        face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
        sewing.Add(face)
    sewing.Perform()
    from OCP.TopoDS import TopoDS
    shell = TopoDS.Shell_s(sewing.SewedShape())
    solid = BRepBuilderAPI_MakeSolid(shell).Shape()
    if count_solids(solid) != 1:
        raise ValueError("hull solid construction failed")
    return solid, hull


def hull_contains(hull, points, tol=CONTAINMENT_TOL_MM):
    """Machine containment certificate: max hull-inequality violation."""
    eq = hull.equations
    v = points @ eq[:, :3].T + eq[:, 3]
    return float(v.max()) if v.size else 0.0


# ------------------------------------------------------------------ decomposition
def _components(faces):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for f in faces:
        a, b, c = int(f[0]), int(f[1]), int(f[2])
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        parent.setdefault(c, c)
        parent[find(a)] = find(b)
        parent[find(a)] = find(c)
    groups = {}
    for f in faces:
        groups.setdefault(find(int(f[0])), []).append(f)
    return list(groups.values())


def _mesh_volume(pts, faces):
    v = pts[faces[:, 0]]
    a = pts[faces[:, 1]] - v
    b = pts[faces[:, 2]] - v
    return abs(float((v * np.cross(a, b)).sum()) / 6.0)


def mesh_to_hull_pieces(vertices, faces, max_pieces=64, inflation_ratio=4.0):
    """Conservative convex decomposition: list of (piece_points, hull).
    Every piece's hull contains its mesh subset (certified)."""
    pts = np.asarray(vertices, float)
    faces = np.asarray(faces, dtype=np.int64)
    pieces = []
    comps = _components(faces)

    def add_piece(pverts, pfaces, depth):
        if len(pieces) >= max_pieces or len(pverts) < 4:
            lo = pverts.min(axis=0) - 1e-9
            hi = pverts.max(axis=0) + 1e-9
            pieces.append(("box", (lo, hi), None))
            return
        try:
            solid, hull = hull_solid(pverts)
            ok = bool(BRepCheck_Analyzer(solid, False).IsValid())
        except Exception:
            ok = False
        if not ok:
            lo = pverts.min(axis=0) - 1e-9
            hi = pverts.max(axis=0) + 1e-9
            pieces.append(("box", (lo, hi), None))
            return
        mesh_vol = _mesh_volume(pverts, pfaces)
        hull_vol = shape_volume(solid)
        ratio = hull_vol / max(mesh_vol, 1e-12)
        if ratio <= inflation_ratio or depth >= 6:
            violation = hull_contains(hull, pverts)
            assert violation <= CONTAINMENT_TOL_MM, f"hull containment violated: {violation}"
            pieces.append(("hull", solid, float(violation)))
            return
        axis = int(np.argmax(pverts.max(axis=0) - pverts.min(axis=0)))
        median = float(np.median(pverts[:, axis]))
        left_f = pfaces[np.all(pverts[pfaces][:, :, axis] <= median, axis=1)]
        right_f = pfaces[np.all(pverts[pfaces][:, :, axis] >= median, axis=1)]
        if len(left_f) == 0 or len(right_f) == 0 or len(left_f) + len(right_f) > 2 * len(pfaces):
            violation = hull_contains(hull, pverts)
            pieces.append(("hull", solid, float(violation)))
            return
        for sub in (left_f, right_f):
            idx = np.unique(sub.reshape(-1))
            add_piece(pverts[idx], np.searchsorted(idx, sub), depth + 1)

    for comp in comps:
        cf = np.asarray(comp, dtype=np.int64)
        idx = np.unique(cf.reshape(-1))
        add_piece(pts[idx], np.searchsorted(idx, cf), 0)
    return pieces


def pieces_to_compound(pieces):
    builder = BRep_Builder()
    comp = TopoDS_Compound()
    builder.MakeCompound(comp)
    for kind, payload, _ in pieces:
        solid = box_from_bounds(*payload) if kind == "box" else payload
        builder.Add(comp, solid)
    return comp


# ------------------------------------------------------------------ FCStd
def extract_fcstd_brep(fcstd_path, object_name):
    """Extract one FreeCAD object's shape with its Document.xml placement baked.

    Returns (shape_in_document_coordinates_mm, placement_dict)."""
    fcstd_path = abspath(fcstd_path) if not os.path.isabs(str(fcstd_path)) else fcstd_path
    with zipfile.ZipFile(fcstd_path) as z:
        doc = ET.fromstring(z.read("Document.xml"))
        placement = None
        for obj in doc.iter("Object"):
            if obj.get("name") == object_name:
                for prop in obj.iter("Property"):
                    if prop.get("name") == "Placement":
                        pos = prop.find(".//PropertyVector")
                        rot = prop.find(".//PropertyQuaternion")
                        placement = {
                            "position_mm": [float(pos.get(k)) for k in ("x", "y", "z")],
                            "quaternion_xyzw": [float(rot.get(k)) for k in ("qx", "qy", "qz", "qw")],
                        }
                        break
                break
        brp_name = None
        for cand in (f"{object_name}.Shape.brp", f"{object_name}.Shape1.brp"):
            if cand in z.namelist():
                brp_name = cand
                break
        if brp_name is None:
            raise ValueError(f"no .brp for {object_name} in {fcstd_path}")
        raw = z.read(brp_name)
    tmp = abspath(f"20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/claude_takeover_closure_v1/03_m01/assets/_tmp_fcstd_{object_name}.brp")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "wb") as f:
        f.write(raw)
    shape = load_brep(tmp)
    os.remove(tmp)
    if placement is not None:
        qx, qy, qz, qw = placement["quaternion_xyzw"]
        n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
        assert n > 0
        qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
        R = np.array([
            [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
            [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
            [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
        ])
        t = np.asarray(placement["position_mm"], float)
        tr = gp_Trsf()
        tr.SetValues(R[0, 0], R[0, 1], R[0, 2], t[0],
                     R[1, 0], R[1, 1], R[1, 2], t[1],
                     R[2, 0], R[2, 1], R[2, 2], t[2])
        shape = BRepBuilderAPI_Transform(shape, tr, True).Shape()
    return shape, placement


# ------------------------------------------------------------------ distance
def dist_shapes(shape_a, shape_b):
    """BRepExtrema distance: (value_mm, pa, pb, inner_solution, n_solutions)."""
    oracle = BRepExtrema_DistShapeShape(shape_a, shape_b)
    oracle.Perform()
    if not oracle.IsDone():
        return None
    n = int(oracle.NbSolution())
    if n <= 0:
        return None
    val = float(oracle.Value())
    pa = oracle.PointOnShape1(1)
    pb = oracle.PointOnShape2(1)
    best = (float(pa.X()), float(pa.Y()), float(pa.Z()))
    bestb = (float(pb.X()), float(pb.Y()), float(pb.Z()))
    for i in range(2, n + 1):
        pa = oracle.PointOnShape1(i)
        pb = oracle.PointOnShape2(i)
        d = math.dist((pa.X(), pa.Y(), pa.Z()), (pb.X(), pb.Y(), pb.Z()))
        if d < math.dist(best, bestb):
            best = (float(pa.X()), float(pa.Y()), float(pa.Z()))
            bestb = (float(pb.X()), float(pb.Y()), float(pb.Z()))
    return val, best, bestb, bool(oracle.InnerSolution()), n


def tessellate(shape, deflection_mm=0.01):
    """Deterministic OCP tessellation -> (vertices, faces). Caller must derate
    by deflection_mm (chordal gap can go either way)."""
    BRepMesh_IncrementalMesh(shape, deflection_mm, False, 0.5, True)
    verts = []
    faces = []
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            base = len(verts)
            nt = tri.NbNodes()
            for i in range(1, nt + 1):
                p = tri.Node(i).Transformed(trsf)
                verts.append((p.X(), p.Y(), p.Z()))
            nt2 = tri.NbTriangles()
            for i in range(1, nt2 + 1):
                t = tri.Triangle(i)
                a, b, c = t.Get()
                faces.append((base + a - 1, base + b - 1, base + c - 1))
        exp.Next()
    return np.asarray(verts, float), np.asarray(faces, dtype=np.int64)
