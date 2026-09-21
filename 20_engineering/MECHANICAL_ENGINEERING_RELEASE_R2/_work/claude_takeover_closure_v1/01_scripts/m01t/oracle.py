"""Pair-distance oracle ladder + scene runtime for the takeover M01 machinery.

Ladder per pair at a fixed configuration (all mm, S frame):
  1. AABB lower bound (conservative: posed-AABB separation <= true separation)
  2. OCP BRep compound distance (conservative: containment assets)
  3. exact design-surface distance (tri-tri exact for mesh-origin; tessellation
     at 0.01 mm with declared derate for STEP-origin; analytic capsules for C)
  4. certified contact witness (exact mesh intersection / capsule penetration)

Status: SAFE (certified lower margin > 0), UNSAFE (certified contact witness or
certified upper margin <= 0), UNKNOWN otherwise. UNKNOWN never becomes SAFE.
"""
import math

import numpy as np
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf
from OCP.Precision import Precision

from . import kinematics as K
from .assets import dist_shapes, shape_aabb
from .common import abspath, jload

BACKEND_DERATE_MM = float(Precision.Approximation_s())
TESS_DEFLECTION_MM = 0.01

ADJ_PAIRS = None  # set by scene load

_GRID_CACHE = {}


def _grid_cache_get(v, f, cell):
    return _GRID_CACHE.get((id(v), id(f), cell))


def _grid_cache_put(v, f, cell, grid):
    if len(_GRID_CACHE) > 512:
        _GRID_CACHE.clear()
    _GRID_CACHE[(id(v), id(f), cell)] = grid


# ================================================================ exact math
def clamp01(x):
    return min(1.0, max(0.0, x))


def point_triangle_distance(p, a, b, c):
    """Ericson 5.1.5. Returns (dist, closest_point)."""
    ab = b - a
    ac = c - a
    ap = p - a
    d1 = np.dot(ab, ap)
    d2 = np.dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return float(np.linalg.norm(ap)), a
    bp = p - b
    d3 = np.dot(ab, bp)
    d4 = np.dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return float(np.linalg.norm(bp)), b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        q = a + v * ab
        return float(np.linalg.norm(p - q)), q
    cp = p - c
    d5 = np.dot(ab, cp)
    d6 = np.dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return float(np.linalg.norm(cp)), c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        q = a + w * ac
        return float(np.linalg.norm(p - q)), q
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        q = b + w * (c - b)
        return float(np.linalg.norm(p - q)), q
    n = np.cross(ab, ac)
    nn = float(np.linalg.norm(n))
    if nn == 0.0:
        return float(min(np.linalg.norm(ap), np.linalg.norm(bp), np.linalg.norm(cp))), a
    dist = abs(np.dot(ap, n)) / nn
    return float(dist), p - (np.dot(ap, n) / (nn * nn)) * n


def segment_segment_distance(p1, q1, p2, q2):
    """Ericson 5.1.9. Returns (dist, c1, c2)."""
    d1 = q1 - p1
    d2 = q2 - p2
    r = p1 - p2
    a = float(d1 @ d1)
    e = float(d2 @ d2)
    f = float(d2 @ r)
    if a <= 1e-300 and e <= 1e-300:
        return float(np.linalg.norm(r)), p1, p2
    if a <= 1e-300:
        s = 0.0
        t = clamp01(f / e)
    else:
        c = float(d1 @ r)
        if e <= 1e-300:
            t = 0.0
            s = clamp01(-c / a)
        else:
            b = float(d1 @ d2)
            denom = a * e - b * b
            s = clamp01((b * f - c * e) / denom) if denom > 1e-300 else 0.0
            tnom = b * s + f
            if tnom < 0.0:
                t = 0.0
                s = clamp01(-c / a)
            elif tnom > e:
                t = 1.0
                s = clamp01((b - c) / a)
            else:
                t = tnom / e
    c1 = p1 + d1 * s
    c2 = p2 + d2 * t
    return float(np.linalg.norm(c1 - c2)), c1, c2


def segment_triangle_distance(p0, p1, a, b, c):
    """Exact segment-triangle distance (0 if intersecting)."""
    if segment_triangle_intersect(p0, p1, a, b, c):
        return 0.0, p0, a
    cands = []
    d, q = point_triangle_distance(p0, a, b, c)
    cands.append((d, p0, q))
    d, q = point_triangle_distance(p1, a, b, c)
    cands.append((d, p1, q))
    for e0, e1 in ((a, b), (b, c), (c, a)):
        d, ca, cb = segment_segment_distance(p0, p1, e0, e1)
        cands.append((d, ca, cb))
    return min(cands, key=lambda x: x[0])


def segment_triangle_intersect(p0, p1, a, b, c):
    """Möller segment-triangle intersection."""
    n = np.cross(b - a, c - a)
    d0 = float(n @ (p0 - a))
    d1 = float(n @ (p1 - a))
    if d0 * d1 > 0.0 or (d0 == 0.0 and d1 == 0.0 and abs(n @ n) < 1e-300):
        return False
    nn = float(n @ n)
    if nn < 1e-300:
        return False
    t = d0 / (d0 - d1) if d0 != d1 else 0.0
    t = clamp01(t)
    p = p0 + t * (p1 - p0)
    # point-in-triangle via barycentric
    v0 = b - a
    v1 = c - a
    v2 = p - a
    d00 = v0 @ v0
    d01 = v0 @ v1
    d11 = v1 @ v1
    d20 = v2 @ v0
    d21 = v2 @ v1
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-300:
        return False
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    return (v >= -1e-12) and (w >= -1e-12) and (v + w <= 1.0 + 1e-12)


def tri_tri_distance(t1, t2):
    """Exact triangle-triangle distance (0 if intersecting) + witnesses."""
    if tri_tri_intersect(t1, t2):
        return 0.0, t1[0], t2[0]
    cands = []
    for i in range(3):
        d, q = point_triangle_distance(t1[i], t2[0], t2[1], t2[2])
        cands.append((d, t1[i], q))
        d, q = point_triangle_distance(t2[i], t1[0], t1[1], t1[2])
        cands.append((d, q, t2[i]))
    for i in range(3):
        e1 = (t1[i], t1[(i + 1) % 3])
        for j in range(3):
            e2 = (t2[j], t2[(j + 1) % 3])
            d, ca, cb = segment_segment_distance(e1[0], e1[1], e2[0], e2[1])
            cands.append((d, ca, cb))
    return min(cands, key=lambda x: x[0])


def tri_tri_intersect(t1, t2):
    """Möller tri-tri intersection (non-coplanar fast path + 2D fallback)."""
    n1 = np.cross(t1[1] - t1[0], t1[2] - t1[0])
    d2 = n1 @ (t2 - t1[0]).T if False else np.array([n1 @ (v - t1[0]) for v in t2])
    if np.all(d2 > 1e-14) or np.all(d2 < -1e-14):
        return False
    n2 = np.cross(t2[1] - t2[0], t2[2] - t2[0])
    d1 = np.array([n2 @ (v - t2[0]) for v in t1])
    if np.all(d1 > 1e-14) or np.all(d1 < -1e-14):
        return False
    if np.all(np.abs(d1) <= 1e-14) and np.all(np.abs(d2) <= 1e-14):
        return _coplanar_tri_tri(t1, t2)
    D = np.cross(n1, n2)
    if float(D @ D) < 1e-300:
        return _coplanar_tri_tri(t1, t2)

    def interval(tri, d, n_other_side):
        projs = D @ tri.T
        # find the vertex on the opposite side
        idx = None
        for i in range(3):
            if (d[i] > 1e-14) != n_other_side and abs(d[i]) > 1e-14:
                continue
        signs = np.sign(d)
        solo = None
        for i in range(3):
            j, k = (i + 1) % 3, (i + 2) % 3
            if signs[i] == 0 and signs[j] == 0 and signs[k] == 0:
                return None
            if signs[i] * signs[j] <= 0 and signs[i] * signs[k] <= 0 and \
               not (signs[i] == 0 and (signs[j] != 0 or signs[k] != 0) and False):
                if signs[i] != 0:
                    if signs[i] * signs[j] < 0 and signs[i] * signs[k] < 0:
                        solo = i
                        break
        if solo is None:
            solo = int(np.argmin(np.abs(d)))
        others = [i for i in range(3) if i != solo]
        ts = []
        for o in others:
            denom = d[solo] - d[o]
            if abs(denom) < 1e-300:
                ts.append(projs[solo])
            else:
                t = d[solo] / denom
                ts.append(projs[solo] + t * (projs[o] - projs[solo]))
        return min(ts), max(ts)

    i1 = interval(t1, d1, True)
    i2 = interval(t2, d2, True)
    if i1 is None or i2 is None:
        return _coplanar_tri_tri(t1, t2)
    return not (i1[1] < i2[0] - 1e-14 or i2[1] < i1[0] - 1e-14)


def _coplanar_tri_tri(t1, t2):
    n = np.cross(t1[1] - t1[0], t1[2] - t1[0])
    nn = float(n @ n)
    if nn < 1e-300:
        return False
    n = n / math.sqrt(nn)
    ax = np.cross(n, np.array([1.0, 0, 0]))
    if float(ax @ ax) < 1e-12:
        ax = np.cross(n, np.array([0.0, 1.0, 0]))
    ax = ax / math.sqrt(float(ax @ ax))
    ay = np.cross(n, ax)
    p1 = np.stack([t1 @ ax, t1 @ ay], axis=1)
    p2 = np.stack([t2 @ ax, t2 @ ay], axis=1)

    def seg2d(a, b, c, d):
        d1 = np.cross(b - a, c - a)
        d2 = np.cross(b - a, d - a)
        d3 = np.cross(d - c, a - c)
        d4 = np.cross(d - c, b - c)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    for i in range(3):
        for j in range(3):
            if seg2d(p1[i], p1[(i + 1) % 3], p2[j], p2[(j + 1) % 3]):
                return True

    def in_tri(p, t):
        d = []
        for i in range(3):
            e = t[(i + 1) % 3] - t[i]
            d.append(np.cross(e, p - t[i]))
        return all(x >= -1e-14 for x in d) or all(x <= 1e-14 for x in d)

    return in_tri(p1[0], p2) or in_tri(p2[0], p1)


# ================================================================ mesh engine
def mesh_mesh_distance(v1, f1, v2, f2, tol_pause=0.0):
    """Exact mesh-mesh distance via grid-culled tri-tri evaluation.

    Returns (d_min, pa, pb, intersecting). Exact for the given meshes."""
    v1 = np.asarray(v1, float)
    v2 = np.asarray(v2, float)
    t1 = v1[f1]
    t2 = v2[f2]
    from scipy.spatial import cKDTree
    tree = cKDTree(v2)
    dvv, _ = tree.query(v1, k=1)
    tree1 = cKDTree(v1)
    dvv2, _ = tree1.query(v2, k=1)
    # any witnessed vertex-vertex distance is a valid upper bound; min is tightest
    ub = float(min(dvv.min() if len(dvv) else np.inf, dvv2.min() if len(dvv2) else np.inf))
    lo1 = t1.min(axis=1)
    hi1 = t1.max(axis=1)
    lo2 = t2.min(axis=1)
    hi2 = t2.max(axis=1)
    # uniform grid over mesh-2 triangle AABBs; cell = max tri extent of mesh 2
    ext2 = (hi2 - lo2).max(axis=1)
    cell = float(max(ext2.max(), 1e-6)) + 1e-9

    def cell_id(p):
        return tuple(np.floor(p / cell).astype(np.int64))

    grid = _grid_cache_get(v2, f2, cell)
    if grid is None:
        grid = {}
        for j in range(len(t2)):
            c0 = cell_id(lo2[j])
            c1 = cell_id(hi2[j])
            for ix in range(c0[0], c1[0] + 1):
                for iy in range(c0[1], c1[1] + 1):
                    for iz in range(c0[2], c1[2] + 1):
                        grid.setdefault((ix, iy, iz), []).append(j)
        _grid_cache_put(v2, f2, cell, grid)

    best = (ub, None, None)
    intersecting = False
    for i in range(len(t1)):
        # query window: tri AABB expanded by current best distance
        qlo = lo1[i] - best[0]
        qhi = hi1[i] + best[0]
        c0 = cell_id(qlo)
        c1 = cell_id(qhi)
        cand = set()
        for ix in range(c0[0], c1[0] + 1):
            for iy in range(c0[1], c1[1] + 1):
                for iz in range(c0[2], c1[2] + 1):
                    cand.update(grid.get((ix, iy, iz), ()))
        for j in cand:
            d, pa, pb = tri_tri_distance(t1[i], t2[j])
            if d < best[0]:
                best = (d, pa, pb)
            if d == 0.0:
                intersecting = True
    return best[0], best[1], best[2], intersecting


# ================================================================ scene
class ObjRt:
    __slots__ = ("oid", "category", "storage_frame", "pose_law", "host",
                 "motion_class", "segment_id", "brep", "capsules", "mesh_v",
                 "mesh_f", "mesh_derate_mm", "aabb_lo", "aabb_hi", "asset_sha")


class Scene:
    """Loads the takeover M01-A manifest and rebuilds runtime state from
    hash-verified sources. Deterministic; no wallclock, no randomness."""

    def __init__(self):
        from .common import M01_OUT
        self.manifest = jload(f"{M01_OUT}/M01_OPERATIONAL_ASSET_MANIFEST_V1.json")
        self.receipt = jload(f"{M01_OUT}/M01_OPERATIONAL_ASSET_GENERATION_RECEIPT_V1.json")
        self.reg = jload("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
                         "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/"
                         "M01_SYSTEM_COLLISION_REGISTRY_V1.json")
        self.objects = {}
        regmap = {o["object_id"]: o for o in self.reg["objects"]}
        from .assets import load_brep, tessellate
        import numpy as _np
        for e in self.manifest["entries"]:
            oid = e["object_id"]
            rec = self.receipt["per_object"][oid]
            rt = ObjRt()
            rt.oid = oid
            rt.category = oid.split("::")[0]
            rt.storage_frame = e["storage_frame"]
            rt.pose_law = e["pose_law"]
            rt.host = rec.get("host_link")
            rt.motion_class = rec.get("motion_class")
            rt.segment_id = rec.get("segment_id")
            rt.asset_sha = e["asset_sha256"]
            rt.capsules = None
            rt.mesh_v = rt.mesh_f = None
            rt.mesh_derate_mm = 0.0
            if e["geometry_representation"] == "ANALYTIC_CAPSULE_CHAIN_PARAMETERS":
                caps = jload(rec["asset_path"])
                rt.capsules = caps
                a = _np.asarray(caps["a_A0_mm"])
                b = _np.asarray(caps["b_A0_mm"])
                r = _np.asarray(caps["effective_radius_mm"])
                lo = _np.minimum(a, b).min(axis=0) - r.max()
                hi = _np.maximum(a, b).max(axis=0) + r.max()
                rt.aabb_lo, rt.aabb_hi = lo, hi
                rt.brep = None
            elif e["geometry_representation"] == "DESIGN_SURFACE_TRIANGLE_MESH_NPZ":
                rt.brep = None
                z = _np.load(abspath(e["asset_path"]))
                rt.mesh_v = _np.asarray(z["vertices_mm"], float)
                rt.mesh_f = _np.asarray(z["faces"], dtype=_np.int64)
                rt.mesh_derate_mm = 0.0
                rt.aabb_lo = rt.mesh_v.min(axis=0)
                rt.aabb_hi = rt.mesh_v.max(axis=0)
            else:
                rt.brep = load_brep(abspath(e["asset_path"]))
                lo, hi = shape_aabb(rt.brep)
                rt.aabb_lo, rt.aabb_hi = _np.asarray(lo), _np.asarray(hi)
                rt.mesh_v, rt.mesh_f, rt.mesh_derate_mm = self._exact_mesh(oid, regmap[oid], rec, rt.brep)
            self.objects[oid] = rt
        self.exceptions = {tuple(sorted(x["canonical_pair"])) for x in self.reg["active_pair_exceptions"]}

    def _exact_mesh(self, oid, reg_obj, rec, brep):
        import numpy as _np
        if rec["geometry_representation"] == "DESIGN_SURFACE_TRIANGLE_MESH_NPZ":
            z = _np.load(abspath(rec["asset_path"]))
            return (_np.asarray(z["vertices_mm"], float),
                    _np.asarray(z["faces"], dtype=_np.int64), 0.0)
        # STEP-origin: tessellate (derate = deflection)
        from .assets import tessellate
        v, f = tessellate(brep, TESS_DEFLECTION_MM)
        return v, f, TESS_DEFLECTION_MM

    # ------------------------------------------------------------ posing
    def poses(self, q6, g1=0.0, g2=0.0):
        """Return {oid: 4x4 mm S transform} for rigid objects; C objects are
        posed per-capsule by posed_capsules()."""
        T = K.fk_mm(q6, g1, g2)
        M = {}
        for oid, rt in self.objects.items():
            law = rt.pose_law
            if law == "C_SECTION_POINT_LAWS":
                continue
            if law == "STATIC_S":
                M[oid] = np.eye(4)
            elif law == "MOUNT_STATIC":
                M[oid] = K.MOUNT_MM
            elif law in ("ARM_FK", "ARM_FK_2P"):
                M[oid] = K.MOUNT_MM @ T[rt.storage_frame]
            elif law == "ARM_FK_LINK1":
                M[oid] = K.MOUNT_MM @ T["link1"]
            elif law == "ARM_FK_LINK2":
                M[oid] = K.MOUNT_MM @ T["link2"]
            elif law == "HOST_FOLLOW_OR_REGISTERED_MOTION":
                M[oid] = K.pose_r_object_mm(rt.oid.split("::", 1)[1], rt.host,
                                            rt.motion_class, q6)
            else:
                raise ValueError(f"unknown pose law {law} for {oid}")
        return M

    def posed_capsules(self, oid, q6):
        """C object -> list of (a_S, b_S, r_eff) at q6 with annulus inflation."""
        rt = self.objects[oid]
        caps = rt.capsules
        seg = caps["segment_id"]
        a = np.asarray(caps["a_A0_mm"])
        b = np.asarray(caps["b_A0_mm"])
        r = np.asarray(caps["effective_radius_mm"])
        sec = np.asarray(caps["section_index"])
        out = []
        for si in sorted(set(sec.tolist())):
            m = sec == si
            pa = K.map_c_points_mm(seg, si, a[m], q6)
            pb = K.map_c_points_mm(seg, si, b[m], q6)
            rr = r[m].copy()
            if seg == K.J4_SEGMENT_ID and si == 5:
                for k, idx in enumerate(np.argwhere(m).reshape(-1)):
                    rr[k] += K.annulus_chord_inflation_mm(a[idx], b[idx], float(q6[3]))
            out.extend(zip(pa, pb, rr.tolist()))
        return out

    def posed_aabb(self, oid, M):
        rt = self.objects[oid]
        corners = np.array([[x, y, z] for x in (rt.aabb_lo[0], rt.aabb_hi[0])
                            for y in (rt.aabb_lo[1], rt.aabb_hi[1])
                            for z in (rt.aabb_lo[2], rt.aabb_hi[2])])
        p = corners @ M[:3, :3].T + M[:3, 3]
        return p.min(axis=0), p.max(axis=0)

    def posed_brep(self, oid, M):
        shape = self.objects[oid].brep
        tr = gp_Trsf()
        tr.SetValues(M[0, 0], M[0, 1], M[0, 2], M[0, 3],
                     M[1, 0], M[1, 1], M[1, 2], M[1, 3],
                     M[2, 0], M[2, 1], M[2, 2], M[2, 3])
        return BRepBuilderAPI_Transform(shape, tr, True).Shape()

    def posed_mesh(self, oid, M):
        rt = self.objects[oid]
        return rt.mesh_v @ M[:3, :3].T + M[:3, 3]


class PoseContext:
    """Per-configuration cache: poses, posed AABBs/BReps/capsules."""

    def __init__(self, scene, q6, g1=0.0, g2=0.0):
        self.scene = scene
        self.q6 = tuple(float(x) for x in q6)
        self.g1 = float(g1)
        self.g2 = float(g2)
        self.M = scene.poses(self.q6, g1, g2)
        self._aabb = {}
        self._brep = {}
        self._caps = {}
        self._mesh = {}

    def aabb(self, oid):
        if oid not in self._aabb:
            rt = self.scene.objects[oid]
            if rt.capsules is not None:
                caps = self.capsules(oid)
                pts = np.vstack([np.vstack([c[0], c[1]]) for c in caps])
                rr = max(c[2] for c in caps)
                self._aabb[oid] = (pts.min(axis=0) - rr, pts.max(axis=0) + rr)
            else:
                self._aabb[oid] = self.scene.posed_aabb(oid, self.M[oid])
        return self._aabb[oid]

    def brep(self, oid):
        if oid not in self._brep:
            rt = self.scene.objects[oid]
            if rt.capsules is not None:
                from .assets import capsule_compound
                from OCP.BRep import BRep_Builder
                from OCP.TopoDS import TopoDS_Compound
                b = BRep_Builder()
                comp = TopoDS_Compound()
                b.MakeCompound(comp)
                for ca, cb, rr in self.capsules(oid):
                    b.Add(comp, capsule_compound(ca, cb, rr))
                self._brep[oid] = comp
            else:
                self._brep[oid] = self.scene.posed_brep(oid, self.M[oid])
        return self._brep[oid]

    def capsules(self, oid):
        if oid not in self._caps:
            self._caps[oid] = self.scene.posed_capsules(oid, list(self.q6))
        return self._caps[oid]

    def mesh(self, oid):
        if oid not in self._mesh:
            self._mesh[oid] = self.scene.posed_mesh(oid, self.M[oid])
        return self._mesh[oid]


# ================================================================ pair query
def aabb_distance(lo1, hi1, lo2, hi2):
    d = np.maximum(np.maximum(lo1 - hi2, lo2 - hi1), 0.0)
    return float(np.sqrt((d ** 2).sum()))


def pair_query(scene, ctx, oid_a, oid_b, required_mm=0.0, rung_budget=3):
    """Full ladder at a fixed configuration. Returns a row dict."""
    ra, rb = scene.objects[oid_a], scene.objects[oid_b]
    derate_backend = BACKEND_DERATE_MM
    row = {"object_a": oid_a, "object_b": oid_b,
           "oracle_type": None, "exact_or_conservative": None,
           "result": "UNKNOWN", "minimum_distance_mm": None,
           "witness_a_S_mm": None, "witness_b_S_mm": None,
           "failure_reason": None, "rungs": []}

    # ---- rung 1: AABB broadphase
    lo_a, hi_a = ctx.aabb(oid_a)
    lo_b, hi_b = ctx.aabb(oid_b)
    lb = aabb_distance(lo_a, hi_a, lo_b, hi_b)
    row["rungs"].append({"rung": "AABB", "lower_bound_mm": lb})
    if lb - derate_backend - required_mm > 0.0:
        row.update(oracle_type="CONSERVATIVE_AABB_BROADPHASE",
                   exact_or_conservative="CONSERVATIVE_LOWER_BOUND",
                   result="SAFE", minimum_distance_mm=lb)
        return row
    if rung_budget < 2:
        row["failure_reason"] = "RUNG_BUDGET_EXHAUSTED_AFTER_AABB"
        return row

    # ---- rung 2: OCP exact BRep-BRep distance (only when both have BReps)
    if ra.brep is not None and rb.brep is not None:
        d_ocp = None
        try:
            res = dist_shapes(ctx.brep(oid_a), ctx.brep(oid_b))
            if res is not None:
                d_ocp = res[0]
        except Exception as exc:
            row["rungs"].append({"rung": "OCP_BREP", "error": type(exc).__name__})
            row["failure_reason"] = "ORACLE_EXCEPTION_RUNG2"
            return row
        if d_ocp is not None and math.isfinite(d_ocp):
            lower = ((d_ocp - 0.0) - 0.0) - derate_backend
            row["rungs"].append({"rung": "OCP_BREP_EXACT", "raw_mm": d_ocp, "lower_mm": lower})
            if lower - required_mm > 0.0:
                row.update(oracle_type="OCP_BREP_EXACT",
                           exact_or_conservative="EXACT_BREP",
                           result="SAFE", minimum_distance_mm=d_ocp)
                return row
    if rung_budget < 3:
        row["failure_reason"] = "RUNG_BUDGET_EXHAUSTED_AFTER_OCP"
        return row

    # ---- rung 3: exact design-surface distance + contact witness
    d_exact, wa, wb, contact = exact_design_distance(scene, ctx, oid_a, oid_b)
    if d_exact is None:
        row["failure_reason"] = "EXACT_RUNG_NOT_CONSTRUCTIBLE"
        return row
    tess = ra.mesh_derate_mm + rb.mesh_derate_mm
    lower = ((d_exact - tess) - 0.0) - derate_backend
    upper = d_exact + tess
    row["rungs"].append({"rung": "EXACT_DESIGN", "d_mm": d_exact,
                         "tess_derate_mm": tess, "lower_mm": lower, "upper_mm": upper})
    if contact:
        row.update(oracle_type="EXACT_DESIGN_SURFACE",
                   exact_or_conservative="EXACT_WITH_DECLARED_DERATE",
                   result="UNSAFE", minimum_distance_mm=0.0,
                   witness_a_S_mm=wa, witness_b_S_mm=wb)
        return row
    if lower - required_mm > 0.0:
        row.update(oracle_type="EXACT_DESIGN_SURFACE",
                   exact_or_conservative="EXACT_WITH_DECLARED_DERATE",
                   result="SAFE", minimum_distance_mm=d_exact)
        return row
    if upper - required_mm <= 0.0:
        row.update(oracle_type="EXACT_DESIGN_SURFACE",
                   exact_or_conservative="EXACT_WITH_DECLARED_DERATE",
                   result="UNSAFE", minimum_distance_mm=d_exact,
                   witness_a_S_mm=wa, witness_b_S_mm=wb)
        return row
    row.update(oracle_type="EXACT_DESIGN_SURFACE",
               exact_or_conservative="EXACT_WITH_DECLARED_DERATE",
               minimum_distance_mm=d_exact,
               failure_reason="THRESHOLD_INTERVAL_AMBIGUITY")
    return row


def exact_design_distance(scene, ctx, oid_a, oid_b):
    """Exact distance between design surfaces at the posed configuration.
    Returns (d, witness_a, witness_b, contact_certified) or (None,...)."""
    ra, rb = scene.objects[oid_a], scene.objects[oid_b]

    def mesh_side(rt, oid):
        if rt.capsules is not None:
            return None
        return ctx.mesh(oid), rt.mesh_f

    def capsule_side(rt, oid):
        if rt.capsules is None:
            return None
        return ctx.capsules(oid)

    ca, cb = capsule_side(ra, oid_a), capsule_side(rb, oid_b)
    ma, mb = mesh_side(ra, oid_a), mesh_side(rb, oid_b)
    if ca is not None and cb is not None:
        return capsule_capsule_distance(ca, cb)
    if ca is not None and mb is not None:
        return capsule_mesh_distance(ca, mb[0], mb[1])
    if cb is not None and ma is not None:
        d, wa, wb, c = capsule_mesh_distance(cb, ma[0], ma[1])
        return d, wb, wa, c
    if ma is not None and mb is not None:
        return mesh_mesh_distance(ma[0], ma[1], mb[0], mb[1])
    return None, None, None, None


def capsule_capsule_distance(caps_a, caps_b):
    best = (math.inf, None, None)
    for a0, a1, ra in caps_a:
        for b0, b1, rb in caps_b:
            d, pa, pb = segment_segment_distance(np.asarray(a0), np.asarray(a1),
                                                 np.asarray(b0), np.asarray(b1))
            d_eff = d - ra - rb
            if d_eff < best[0]:
                best = (d_eff, pa, pb)
    if best[0] is math.inf:
        return None, None, None, None
    contact = best[0] <= 0.0
    return max(best[0], 0.0), best[1], best[2], contact


def capsule_mesh_distance(caps, v, f):
    tris = np.asarray(v)[f]
    best = (math.inf, None, None)
    contact = False
    for a0, a1, r in caps:
        a0 = np.asarray(a0)
        a1 = np.asarray(a1)
        # cull triangles by AABB vs capsule AABB
        lo = np.minimum(a0, a1) - r
        hi = np.maximum(a0, a1) + r
        tlo = tris.min(axis=1)
        thi = tris.max(axis=1)
        dlo = np.maximum(tlo - hi, 0.0)
        dhi = np.maximum(lo - thi, 0.0)
        dd = np.sqrt(((dlo + dhi) ** 2).sum(axis=1))
        cand = np.argwhere(dd <= max(best[0] + r, 0.0) + 1e-12).reshape(-1)
        for t in cand:
            dseg, pa, pb = segment_triangle_distance(a0, a1, tris[t][0], tris[t][1], tris[t][2])
            d_eff = dseg - r
            if d_eff < best[0]:
                best = (d_eff, pa, pb)
            if d_eff <= 0.0:
                contact = True
    if best[0] is math.inf:
        return None, None, None, None
    return max(best[0], 0.0), best[1], best[2], contact
