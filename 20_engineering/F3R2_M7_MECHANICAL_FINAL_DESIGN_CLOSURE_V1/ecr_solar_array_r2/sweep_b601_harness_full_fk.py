# -*- coding: utf-8 -*-
"""B601 arm harness FULL-KINEMATIC sweep gate (R2-HRN-04 / ODR-29).

Extends HARNESS_R2_FUNCTIONAL_GATES_V1 (joint1-only, q0-witness scope) to a
full 6-DOF FK sweep of a candidate 3D harness centerline.

Geometry authority notes (discovered during this task):
  * freecad_authoritative/B601_CARRIER_*.FCStd contain NO solids (datum
    containers only; their LinkedObjects point to the missing
    20_engineering/cad/02_carriers/ directory).  Per-link CAD shapes are
    therefore UNUSABLE.
  * The Q0 witness STEP is a set of 4 mm marker boxes at the FK joint
    origins (+30 mm axis-direction markers), in the A0 frame, mm - NOT the
    arm link geometry.  It validates KINEMATICS only.  FK here is validated
    against all five witness STEPs (Q0/STOWED/DEPLOYED_NOMINAL/PARTIAL/
    SERVICE) with max residual 0.0000 mm (see fk_validation).
  * The only per-link solid geometry is the accepted URDF collision STL
    set (meshes_b601_gripper/*.STL), the same meshes used by WP1
    HARNESS_ROUTING_V1 to derive R_child and the per-joint take-up upper
    bounds.  This gate uses them (mm), decimated to <=0.1 mm error.
    Scope consequence: clearances are vs the vendor collision meshes, not
    the (hollow) carrier CAD - recorded as a scope note.
  * Mount: F3R2_ARM_INITIAL_POSE.yaml transform_mm_rows (x=208.0 mm,
    clock 25 deg about +X_S; joint1 axis = +X_S).  This differs from the
    simplified task-text mount (185.25 + Ry90); the frozen SSOT mount is
    used and the discrepancy is documented in the output.

Centerline model: analytic primitives (line / circular arc / helix) with
R=30 mm filleted corners; joint crossings j2..j6 = helix wraps about the
joint axis at an auto-derived radius/azimuth/station (housing radius from
the posed meshes + standoff, azimuth chosen for routing-side continuity
along the arm); joint1 = clock-spring free coil (r=72.05 mm = link1
R_child 62.052428 + 10, captive 2 pi wrap, unwinds 1:1 with q1).

Checks per state: centerline length (provisioned = max*1.05, DERIVED),
min bend radius (analytic + discrete Menger corroboration), signed
clearance = dist(centerline, solid) - tube radius (5.0 mm) against the 10
arm link meshes + bus proxy AABB + R2 solar leaves STEP + gripper rail
full-stroke swept volumes.  A separate pinch pass evaluates the minimum
cable-to-housing distance inside each joint interface band (+-25 mm about
the crossing station) at all 12 hard-stop poses and the 6 named poses.

Run: G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe sweep_b601_harness_full_fk.py
Env: HRN_QUICK=1 -> reduced smoke sweep (debug).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import xml.etree.ElementTree as ET

import FreeCAD as App
import Mesh
import Part

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
CAD = PROJECT_ROOT / "20_engineering" / "cad" / "freecad_authoritative"
URDF = PROJECT_ROOT / "20_engineering" / "cad" / "spacecraft_layout" / "arm_b601_v1" / "arm_b601_v1.urdf"
STL_DIR = URDF.parent / "meshes_b601_gripper"
MOUNT_YAML = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807" / "04_configurations" / "F3R2_ARM_INITIAL_POSE.yaml"
JOINT_STATES = CAD / "joint_states.yaml"
NAMED_POSE_JSON = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1" / "11_validation" / "B601_NAMED_POSE_REVALIDATION_V1.json"
ROUTING_YAML = PROJECT_ROOT / "20_engineering" / "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1" / "wp1_structure_cad" / "HARNESS_ROUTING_V1.yaml"
SOLAR_STEP = HERE / "SOLAR_ARRAY_R2_CANDIDATE_V1.step"
RAIL_DIR = PROJECT_ROOT / "20_engineering" / "F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820" / "01_native_cad" / "gripper_r1"
RAIL_STEPS = [RAIL_DIR / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step",
              RAIL_DIR / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step"]
PALM_SLOT_STEP = RAIL_DIR / "B601_GRIPPER_PALM_RAIL_SLOT_R1.step"
WITNESS = {
    "Q0": CAD / "B601_KINEMATIC_ASSEMBLY_Q0_WITNESS.step",
    "STOWED": CAD / "B601_KINEMATIC_ASSEMBLY_STOWED_WITNESS.step",
    "DEPLOYED_NOMINAL": CAD / "B601_KINEMATIC_ASSEMBLY_DEPLOYED_NOMINAL_WITNESS.step",
    "PARTIAL": CAD / "B601_KINEMATIC_ASSEMBLY_PARTIAL_WITNESS.step",
    "SERVICE": CAD / "B601_KINEMATIC_ASSEMBLY_SERVICE_WITNESS.step",
}

OUT_JSON = HERE / "HARNESS_B601_FULL_FK_SWEEP_V2.json"
OUT_YAML = HERE / "HARNESS_B601_FULL_FK_SWEEP_V2.yaml"

QUICK = os.environ.get("HRN_QUICK", "") == "1"

# ---- requirement constants (WP1 HARNESS_ROUTING_V1, read-only) ------------
TAKEUP_BOUND = {
    "joint1": 347.493596, "joint2": 918.45, "joint3": 869.843711,
    "joint4": 505.684894, "joint5": 143.611582, "joint6": 178.35201,
}
TUBE_R = 5.0                 # mm, bundle radius 4.5 -> 5.0 candidate
BEND_CLASS = 25.0            # mm, TYPICAL_CLASS_VALUE_NOT_VENDOR_BOUND
TOL_PEN = 0.5                # mm penetration tolerance
SAMPLE_DS = 2.5              # mm centerline sampling
FILLET_R = 30.0              # mm nominal fillet radius at routing corners
STANDOFF = 15.0              # mm standoff above derived housing radius
COIL_R = 72.05               # mm joint1 free-coil radius = R_child 62.052428 + 10
COIL_PLANE_X = 330.0         # mm S-frame station of the joint1 coil plane
Q1_RANGE = 5.6               # rad joint1 range
N_JOINT_SAMPLES = 7 if QUICK else 33
N_LHS = 8 if QUICK else 40
DO_CORNERS = not QUICK

ARM_LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5",
             "link6", "gripper_link", "gripper_left", "gripper_right"]


def local_now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha256(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest().upper()


# ---------------------------------------------------------------------------
def tr(x, y, z):
    m = np.eye(4)
    m[0, 3], m[1, 3], m[2, 3] = x, y, z
    return m


def rot_axis(axis, ang):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    x, y, z = a
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    R = np.array([
        [x * x * C + c, x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, y * y * C + c, y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, z * z * C + c]])
    m = np.eye(4)
    m[:3, :3] = R
    return m


def rot_rpy(r, p, y):
    return rot_axis((0, 0, 1), y) @ rot_axis((0, 1, 0), p) @ rot_axis((1, 0, 0), r)


def orthobasis(a):
    a = np.asarray(a, float)
    a = a / np.linalg.norm(a)
    ref = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0.0, 1.0, 0])
    e1 = ref - a * (ref @ a)
    e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(a, e1)
    return a, e1, e2


def azimuth(p, origin, e1, e2):
    v = np.asarray(p, float) - origin
    return math.atan2(float(v @ e2), float(v @ e1))


def xform(M, p):
    return M[:3, :3] @ np.asarray(p, float) + M[:3, 3]


# ---------------------------------------------------------------------------
class ArmModel:
    def __init__(self, urdf_path, mount_rows):
        root = ET.parse(str(urdf_path)).getroot()
        order = []
        for j in root.iter("joint"):   # document order is parent-before-child
            o = j.find("origin")
            xyz = [float(v) for v in o.get("xyz").split()] if o is not None and o.get("xyz") else [0, 0, 0]
            rpy = [float(v) for v in o.get("rpy").split()] if o is not None and o.get("rpy") else [0, 0, 0]
            ax = j.find("axis")
            axis = [float(v) for v in ax.get("xyz").split()] if ax is not None else [1, 0, 0]
            lim = j.find("limit")
            lo = float(lim.get("lower")) if lim is not None else 0.0
            hi = float(lim.get("upper")) if lim is not None else 0.0
            order.append(dict(name=j.get("name"), type=j.get("type"),
                              xyz=xyz, rpy=rpy, axis=axis, lo=lo, hi=hi,
                              parent=j.find("parent").get("link"),
                              child=j.find("child").get("link")))
        self.joints = order
        self.rev = [j for j in order if j["type"] == "revolute"]
        self.mount = np.array(mount_rows, float)

    def origin_T(self, j):
        """joint frame F relative to parent link (fixed)."""
        return tr(*[v * 1000.0 for v in j["xyz"]]) @ rot_rpy(*j["rpy"])

    def fk(self, q6, gripper=(0.0, 0.0)):
        """returns dict link -> 4x4 in A0 (mm).  gripper prismatic in m."""
        qd = {j["name"]: q6[i] for i, j in enumerate(self.rev)}
        qd["gripper_joint1"] = gripper[0]
        qd["gripper_joint2"] = gripper[1]
        T = {"base_link": np.eye(4)}
        for j in self.joints:
            Tj = T[j["parent"]] @ self.origin_T(j)
            if j["type"] == "revolute":
                Tj = Tj @ rot_axis(j["axis"], qd.get(j["name"], 0.0))
            elif j["type"] == "prismatic":
                Tj = Tj @ tr(*[a * qd.get(j["name"], 0.0) * 1000.0 for a in j["axis"]])
            T[j["child"]] = Tj
        return T

    def fk_S(self, q6, gripper=(0.0, 0.0)):
        return {k: self.mount @ v for k, v in self.fk(q6, gripper).items()}

    def joint_frame(self, j, q6):
        T = self.fk(q6)
        return T[j["parent"]] @ self.origin_T(j)


def load_mount():
    import yaml
    data = yaml.safe_load(MOUNT_YAML.read_text(encoding="utf-8"))
    rows = data["mount"]["transform_mm_rows"]
    assert len(rows) == 4 and all(len(r) == 4 for r in rows)
    return rows


# ---------------------------------------------------------------------------
class TriField:
    CELL = 50.0
    D = 25.0          # exactness horizon mm

    def __init__(self, name, tris):
        self.name = name
        V = np.asarray(tris, float)
        self.v0 = V[:, 0, :].copy()
        self.e1 = (V[:, 1, :] - V[:, 0, :]).copy()
        self.e2 = (V[:, 2, :] - V[:, 0, :]).copy()
        self.n = len(V)
        lo = V.min(axis=1)
        hi = V.max(axis=1)
        self.bmin = lo.min(axis=0)
        self.bmax = hi.max(axis=0)
        from collections import defaultdict
        grid = defaultdict(list)
        c = self.CELL
        i0 = np.floor((lo - self.D) / c).astype(np.int32)
        i1 = np.floor((hi + self.D) / c).astype(np.int32)
        for ti in range(self.n):
            a, b = i0[ti], i1[ti]
            for ix in range(a[0], b[0] + 1):
                for iy in range(a[1], b[1] + 1):
                    for iz in range(a[2], b[2] + 1):
                        grid[(ix, iy, iz)].append(ti)
        self.grid = {k: np.array(v, dtype=np.int32) for k, v in grid.items()}

    def aabb_lb(self, P):
        q = np.maximum(np.maximum(self.bmin - P, P - self.bmax), 0.0)
        return np.sqrt((q * q).sum(axis=1))

    def _tri_dist(self, p, idx):
        A = self.v0[idx]
        B = A + self.e1[idx]
        C = A + self.e2[idx]
        AB = self.e1[idx]
        AC = self.e2[idx]
        AP = p - A
        d1 = (AB * AP).sum(1)
        d2 = (AC * AP).sum(1)
        BP = p - B
        d3 = (AB * BP).sum(1)
        d4 = (AC * BP).sum(1)
        CP = p - C
        d5 = (AB * CP).sum(1)
        d6 = (AC * CP).sum(1)
        best = np.full(len(idx), np.inf)

        def d2_seg(P0, P1):
            d = P1 - P0
            L2 = (d * d).sum(1)
            t = ((p - P0) * d).sum(1) / np.maximum(L2, 1e-30)
            t = np.clip(t, 0.0, 1.0)
            diff = P0 + t[:, None] * d - p
            return (diff * diff).sum(1)

        m = (d1 <= 0) & (d2 <= 0)
        if m.any():
            best[m] = np.minimum(best[m], (AP[m] * AP[m]).sum(1))
        m = (d3 >= 0) & (d4 <= d3)
        if m.any():
            best[m] = np.minimum(best[m], (BP[m] * BP[m]).sum(1))
        m = (d6 >= 0) & (d5 <= d6)
        if m.any():
            best[m] = np.minimum(best[m], (CP[m] * CP[m]).sum(1))
        vc = d1 * d4 - d3 * d2
        m = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
        if m.any():
            best[m] = np.minimum(best[m], d2_seg(A[m], B[m]))
        vb = d5 * d2 - d1 * d6
        m = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
        if m.any():
            best[m] = np.minimum(best[m], d2_seg(A[m], C[m]))
        va = d3 * d6 - d5 * d4
        m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
        if m.any():
            best[m] = np.minimum(best[m], d2_seg(B[m], C[m]))
        m = np.isinf(best)
        if m.any():
            nn = np.cross(AB[m], AC[m])
            nl = np.maximum(np.sqrt((nn * nn).sum(1)), 1e-30)
            dist = (nn * (p - A[m])).sum(1) / nl
            best[m] = dist * dist
        return math.sqrt(float(best.min())) if len(best) else math.inf

    def min_dist(self, p):
        """(distance, exact?) - exact if < D, else lower bound D."""
        key = tuple(np.floor(np.asarray(p, float) / self.CELL).astype(np.int32))
        idx = self.grid.get(key)
        if idx is None or len(idx) == 0:
            return self.D, False
        d = self._tri_dist(np.asarray(p, float), idx)
        if d < self.D:
            return d, True
        return self.D, False

    def inside(self, p):
        votes = 0
        for d in ((1.0, 0.0, 0.0), (1.0, 0.0173, 0.0091), (1.0, -0.0113, 0.0211)):
            votes += 1 if self._ray_count(np.asarray(p, float), np.array(d)) % 2 == 1 else -1
        return votes > 0

    def _ray_count(self, p, d):
        d = d / np.linalg.norm(d)
        h = np.cross(np.broadcast_to(d, self.e2.shape), self.e2)
        det = (self.e1 * h).sum(1)
        m = np.abs(det) > 1e-12
        if not m.any():
            return 0
        inv = 1.0 / det[m]
        sv = p - self.v0[m]
        u = (sv * h[m]).sum(1) * inv
        qv = np.cross(sv, self.e1[m])
        v = (np.broadcast_to(d, qv.shape) * qv).sum(1) * inv
        t = (self.e2[m] * qv).sum(1) * inv
        hit = (u >= 1e-12) & (v >= 1e-12) & (u + v <= 1 - 1e-12) & (t > 1e-9)
        return int(hit.sum())


class BoxField:
    D = 25.0

    def __init__(self, name, bmin, bmax):
        self.name = name
        self.bmin = np.array(bmin, float)
        self.bmax = np.array(bmax, float)

    def aabb_lb(self, P):
        q = np.maximum(np.maximum(self.bmin - P, P - self.bmax), 0.0)
        return np.sqrt((q * q).sum(axis=1))

    def min_dist(self, p):
        p = np.asarray(p, float)
        q = np.maximum(np.maximum(self.bmin - p, p - self.bmax), 0.0)
        return float(np.sqrt((q * q).sum())), True

    def inside(self, p):
        p = np.asarray(p, float)
        return bool((p > self.bmin).all() and (p < self.bmax).all())


def mesh_tris(stl_path, tol=0.1, red=0.9):
    m = Mesh.Mesh(str(stl_path))
    m.decimate(tol, red)
    pts, facs = m.Topology
    V = np.array([[p.x, p.y, p.z] for p in pts]) * 1000.0
    F = np.array(facs, dtype=np.int64)
    return V[F]


def shape_tris(shape, deflection=0.25):
    pts, facs = shape.tessellate(deflection)
    V = np.array([[p.x, p.y, p.z] for p in pts])
    F = np.array(facs, dtype=np.int64)
    return V[F]


# ---------------------------------------------------------------------------
# centerline primitives
def seg_line(p0, p1, ds=SAMPLE_DS):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    n = max(1, int(L / ds))
    return p0 + (p1 - p0) * np.linspace(0, 1, n + 1)[:, None], L


def seg_arc(center, e1, e2, r, phi0, phi1, ds=SAMPLE_DS):
    center = np.asarray(center, float)
    L = abs(phi1 - phi0) * r
    n = max(2, int(L / ds))
    phis = np.linspace(phi0, phi1, n + 1)
    pts = center + r * (np.cos(phis)[:, None] * e1[None, :]
                        + np.sin(phis)[:, None] * e2[None, :])
    return pts, L


def seg_helix(origin, a, e1, e2, r, phi0, phi1, z0, z1, ds=SAMPLE_DS):
    origin = np.asarray(origin, float)
    L = math.sqrt((r * (phi1 - phi0)) ** 2 + (z1 - z0) ** 2)
    n = max(2, int(L / ds))
    t = np.linspace(0, 1, n + 1)
    phis = phi0 + (phi1 - phi0) * t
    zs = z0 + (z1 - z0) * t
    pts = (origin + r * (np.cos(phis)[:, None] * e1[None, :]
                         + np.sin(phis)[:, None] * e2[None, :])
           + zs[:, None] * a[None, :])
    c = 0.0 if abs(phi1 - phi0) < 1e-12 else (z1 - z0) / (phi1 - phi0)
    return pts, L, r + c * c / max(r, 1e-9)


def catmull_rom(ctrl, ds=SAMPLE_DS):
    """uniform Catmull-Rom through control points (clamped ends), sampled
    at ~ds.  C1-continuous by construction."""
    C = np.array(ctrl, float)
    ext = np.vstack([C[0], C, C[-1]])
    out = []
    total = float(np.linalg.norm(np.diff(C, axis=0), axis=1).sum())
    n_samp = max(4, int(total / ds / max(1, len(C) - 1)) + 1)
    for i in range(len(C) - 1):
        P0, P1, P2, P3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for tt in np.linspace(0, 1, n_samp, endpoint=False):
            t2 = tt * tt
            t3 = t2 * tt
            out.append(0.5 * ((2 * P1) + (-P0 + P2) * tt
                              + (2 * P0 - 5 * P1 + 4 * P2 - P3) * t2
                              + (-P0 + 3 * P1 - 3 * P2 + P3) * t3))
    out.append(C[-1])
    return np.array(out)


def smooth_profile(g, passes=4, lift=1.5):
    """3-point averaging of a control profile + constant lift."""
    g = np.asarray(g, float)
    for _ in range(passes):
        if len(g) < 3:
            break
        g = np.concatenate([[g[0]], 0.25 * g[:-2] + 0.5 * g[1:-1]
                            + 0.25 * g[2:], [g[-1]]])
    return g + lift


class Connector:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)
        if kind == "poly":
            self.pts = np.asarray(self.pts, float)
            seg = np.diff(self.pts, axis=0)
            self._seglen = np.sqrt((seg * seg).sum(1))
            self._cum = np.concatenate([[0.0], np.cumsum(self._seglen)])

    def eval(self, t):
        """point + unit tangent (direction of travel) at fraction t."""
        if self.kind == "poly":
            L = float(self._cum[-1])
            target = float(np.clip(t, 0.0, 1.0)) * L
            i = int(np.searchsorted(self._cum, target, side="right")) - 1
            i = max(0, min(i, len(self._seglen) - 1))
            seg = self.pts[i + 1] - self.pts[i]
            sl = max(float(self._seglen[i]), 1e-30)
            frac = (target - self._cum[i]) / sl
            return self.pts[i] + frac * seg, seg / sl
        if self.kind == "line":
            d = self.p1 - self.p0
            u = d / max(np.linalg.norm(d), 1e-30)
            return self.p0 + t * d, u
        if self.kind == "arc":
            phi = self.phi0 + t * (self.phi1 - self.phi0)
            pos = self.center + self.r * (math.cos(phi) * self.e1 + math.sin(phi) * self.e2)
            sgn = 1.0 if self.phi1 >= self.phi0 else -1.0
            tan = sgn * (-math.sin(phi) * self.e1 + math.cos(phi) * self.e2)
            return pos, tan / np.linalg.norm(tan)
        phi = self.phi0 + t * (self.phi1 - self.phi0)
        z = self.z0 + t * (self.z1 - self.z0)
        pos = (self.origin + self.r * (math.cos(phi) * self.e1 + math.sin(phi) * self.e2)
               + z * self.a)
        dphi = self.phi1 - self.phi0
        tan = (dphi * self.r * (-math.sin(phi) * self.e1 + math.cos(phi) * self.e2)
               + (self.z1 - self.z0) * self.a)
        n = np.linalg.norm(tan)
        return pos, (tan / n if n > 1e-12 else self.a.copy())

    def length(self):
        if self.kind == "poly":
            return float(self._cum[-1])
        if self.kind == "line":
            return float(np.linalg.norm(self.p1 - self.p0))
        if self.kind == "arc":
            return abs(self.phi1 - self.phi0) * self.r
        return math.sqrt((self.r * (self.phi1 - self.phi0)) ** 2
                         + (self.z1 - self.z0) ** 2)

    def min_radius(self):
        if self.kind == "poly":
            R = discrete_radius(self.pts)
            return float(np.min(R)) if len(R) else math.inf
        if self.kind == "line":
            return math.inf
        if self.kind == "arc":
            return self.r
        c = 0.0 if abs(self.phi1 - self.phi0) < 1e-12 else (self.z1 - self.z0) / (self.phi1 - self.phi0)
        return self.r + c * c / max(self.r, 1e-9)

    def sample(self, t0=0.0, t1=1.0):
        if t0 >= t1:
            return np.zeros((0, 3)), 0.0, self.min_radius()
        if self.kind == "poly":
            L = float(self._cum[-1])
            s0, s1 = t0 * L, t1 * L
            m = (self._cum > s0) & (self._cum < s1)
            pa, _ = self.eval(t0)
            pb, _ = self.eval(t1)
            pts = np.vstack([pa[None, :], self.pts[m], pb[None, :]])
            Ll = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
            R = discrete_radius(pts)
            return pts, Ll, (float(np.min(R)) if len(R) else math.inf)
        if self.kind == "line":
            p0 = self.p0 + t0 * (self.p1 - self.p0)
            p1 = self.p0 + t1 * (self.p1 - self.p0)
            pts, L = seg_line(p0, p1)
            return pts, L, math.inf
        if self.kind == "arc":
            pts, L = seg_arc(self.center, self.e1, self.e2, self.r,
                             self.phi0 + t0 * (self.phi1 - self.phi0),
                             self.phi0 + t1 * (self.phi1 - self.phi0))
            return pts, L, self.r
        pts, L, rc = seg_helix(self.origin, self.a, self.e1, self.e2, self.r,
                               self.phi0 + t0 * (self.phi1 - self.phi0),
                               self.phi0 + t1 * (self.phi1 - self.phi0),
                               self.z0 + t0 * (self.z1 - self.z0),
                               self.z0 + t1 * (self.z1 - self.z0))
        return pts, L, rc


def fillet_at(corner, d_in, d_out, R_des=FILLET_R, avail_in=1e9, avail_out=1e9):
    """3D circular fillet at `corner` between incoming travel dir d_in and
    outgoing d_out.  t = R * tan(turn/2).  Returns (pts, length, R_eff,
    trim_mm) or None."""
    corner = np.asarray(corner, float)
    u1 = np.asarray(d_in, float)
    u1 = u1 / np.linalg.norm(u1)
    u2 = np.asarray(d_out, float)
    u2 = u2 / np.linalg.norm(u2)
    turn = math.acos(float(np.clip(u1 @ u2, -1, 1)))   # actual deflection
    if turn < math.radians(1.0):
        return None
    t = R_des * math.tan(turn / 2.0)
    R = R_des
    lim = 0.45 * min(avail_in, avail_out)
    if t > lim:
        t = lim
        R = t / math.tan(turn / 2.0)
    T1 = corner - t * u1
    T2 = corner + t * u2
    m1 = u2 - (u1 @ u2) * u1
    nm = np.linalg.norm(m1)
    if nm < 1e-12:
        return None
    m1 = m1 / nm
    O = T1 + R * m1
    _, e1, e2 = orthobasis(np.cross(u1, m1))
    phi0 = azimuth(T1, O, e1, e2)
    phi1 = azimuth(T2, O, e1, e2)
    d = (phi1 - phi0 + math.pi) % (2 * math.pi) - math.pi
    pts, L = seg_arc(O, e1, e2, R, phi0, phi0 + d)
    return pts, L, R, t


# ---------------------------------------------------------------------------
class HarnessDesign:
    """R2-HRN-05 iteration-2 candidate.

    Topology:
      bus clamps P0/P1/P2 -> joint1 clock-spring coil (plane x=330) ->
      HC-3 on link1 -> per-link body-hugging Catmull-Rom spans ->
      j2/j3/j4 (fold joints): AXIAL SIDE-BYPASS service loops - the cable
      leaves the parent body at A_p, runs axially to the bypass station s_b
      beyond the child-side assembly's axial extent about the joint axis
      (rotation about the axis preserves the axial coordinate, so no
      child-side geometry can ever sweep into s_b), U-turns through a
      semicircle of radius chord/2 >= 26 mm (enforced by a +52 mm radial
      separation between the out and return legs, both exactly axial so
      the U-turn is tangent-continuous by construction), and returns onto
      the child at A_c.  Take-up is absorbed by the U-turn chord growth;
      supplied take-up = pi * r_b.
      j5/j6 (wrist roll joints): clock-spring wraps about the compact wrist
      hub (same model as the joint1 coil): wrap W(q) = W_min + (q - q_lo),
      radius r_w from a full-circle hub scan + 8 mm; the gripper assembly
      (rigid with link6) is included in the j6 hub scan.
      All clamp/anchor geometry is derived from the decimated URDF meshes;
      every number in the report is measured, not asserted.
    """

    BYPASS_AX_MARGIN = 30.0    # s_b beyond child-side axial extent
    LEG_AX = 35.0              # axial leg length (s_leg = s_b - sgn*LEG_AX)
    LEG_RADIAL_SEP = 52.0      # out/return leg radial separation (-> R_turn>=26)
    R_BYPASS_FLOOR = 35.0
    WRAP_BAND = 12.0
    WRAP_MARGIN = 8.0
    WRAP_MIN = math.pi         # captive residual wrap at the closing stop
    DOWNSTREAM_R_CAP = 120.0   # hub-connectedness cap for downstream verts

    def __init__(self, arm, verts_local, rail_verts_gripper,
                 fields_local=None, rail_fields=None, bus_field=None):
        self.arm = arm
        self.verts_local = verts_local
        self.rail_verts_gripper = rail_verts_gripper
        self.fields_local = fields_local or {}
        self.rail_fields = rail_fields or []
        self.bus_field = bus_field
        self.T0 = arm.fk([0.0] * 6)
        self.crossings = {}
        self.spans = {}
        self._derive()

    def link_verts_in_F(self, link, TF):
        V = self.verts_local[link]
        M = np.linalg.inv(TF) @ self.T0[link]
        return V @ M[:3, :3].T + M[:3, 3]

    def _verts_in_F_at(self, link, TF, qvec):
        T = self.arm.fk(qvec)
        M = np.linalg.inv(TF) @ T[link]
        return self.verts_local[link] @ M[:3, :3].T + M[:3, 3]

    # ------------------------------------------------------------------------
    def _derive(self):
        arm = self.arm
        minus_zS = np.array([0.0, 0.0, -1.0])
        Tl1 = self.T0["link1"]
        Mi1 = np.linalg.inv(Tl1)

        # ---- joint1 coil + HC-3 clamp on link1 (unchanged from V1) ----------
        j1 = arm.rev[0]
        TF1 = arm.joint_frame(j1, [0.0] * 6)
        o1_A0 = TF1[:3, 3]
        a1_A0 = TF1[:3, :3] @ np.asarray(j1["axis"], float)
        a1_A0 = a1_A0 / np.linalg.norm(a1_A0)
        TF2 = arm.joint_frame(arm.rev[1], [0.0] * 6)
        o2_l1 = xform(Mi1, TF2[:3, 3])
        o1_l1 = xform(Mi1, o1_A0)
        a1_l1 = Mi1[:3, :3] @ a1_A0
        a1_l1, u1l, v1l = orthobasis(a1_l1)
        th3 = azimuth(o2_l1, o1_l1, u1l, v1l)     # clamp faces joint2
        coil_z_A0 = COIL_PLANE_X - arm.mount[0, 3]
        coil_c_A0 = o1_A0 + a1_A0 * ((coil_z_A0 - o1_A0[2]) / a1_A0[2])
        coil_c_l1 = xform(Mi1, coil_c_A0)
        s_ax = float((coil_c_l1 - o1_l1) @ a1_l1)
        self.clamp_l1 = (o1_l1 + a1_l1 * s_ax
                         + COIL_R * (math.cos(th3) * u1l + math.sin(th3) * v1l))
        self.coil_station_l1 = s_ax
        self.coil_center_S = xform(arm.mount, coil_c_A0)
        a1_S = arm.mount[:3, :3] @ a1_A0
        _, self.coil_e1_S, self.coil_e2_S = orthobasis(a1_S)
        Ta = arm.fk_S([0.0] * 6)["link1"]
        Tb = arm.fk_S([0.1] + [0.0] * 5)["link1"]
        pa = xform(Ta, self.clamp_l1)
        pb = xform(Tb, self.clamp_l1)
        dth = ((azimuth(pb, self.coil_center_S, self.coil_e1_S, self.coil_e2_S)
                - azimuth(pa, self.coil_center_S, self.coil_e1_S, self.coil_e2_S)
                + math.pi) % (2 * math.pi) - math.pi)
        self.coil_sign = 1.0 if dth >= 0 else -1.0
        # fixed-end azimuth = clamp azimuth at q1=0; the coil WINDS UP 1:1
        # with q1 (wrap = 2pi captive + q1, paid out as q1 decreases), so
        # the arc end lands on the moving clamp at every q1 by construction
        self.coil_beta0 = azimuth(pa, self.coil_center_S,
                                  self.coil_e1_S, self.coil_e2_S)
        # coil travel tangent at the HC-3 clamp, link1 frame (design const)
        self.coil_tan_l1 = self.coil_sign * (
            -math.sin(th3) * u1l + math.cos(th3) * v1l)
        self.crossings["joint1"] = dict(
            type="coil", alpha=th3, station=s_ax, radius=COIL_R,
            housing_radius=None, a=a1_l1, e1=u1l, e2=v1l,
            preferred_azimuth=th3, parent="base_link", child="link1",
            lo=j1["lo"], hi=j1["hi"], topology="clock_spring_coil")

        # ---- link spines + G0 (needed by the crossing side logic) -----------
        def j_origin_in_link(j, link):
            TF = arm.joint_frame(j, [0.0] * 6)
            return xform(np.linalg.inv(self.T0[link]) @ TF, np.zeros(3))

        self.G0 = np.array([-80.0, 0.0, 50.0])   # gripper palm back-top candidate
        T_link6_grip = tr(0, 0, 159.71) @ rot_rpy(0, -1.5708, 0)
        G0_l6 = xform(T_link6_grip, self.G0)
        self.spines = {
            "link1": (o1_l1, o2_l1),
            "link2": (np.zeros(3), j_origin_in_link(arm.rev[2], "link2")),
            "link3": (np.zeros(3), j_origin_in_link(arm.rev[3], "link3")),
            "link4": (np.zeros(3), j_origin_in_link(arm.rev[4], "link4")),
            "link5": (np.zeros(3), j_origin_in_link(arm.rev[5], "link5")),
            "link6": (np.zeros(3), np.array([0.0, 0.0, 159.71])),
        }

        # ---- ordered crossings j2..j6 ---------------------------------------
        downstream = {"joint2": ["link2", "link3", "link4", "link5", "link6",
                                 "gripper_link", "gripper_left", "gripper_right"],
                      "joint3": ["link3", "link4", "link5", "link6",
                                 "gripper_link", "gripper_left", "gripper_right"],
                      "joint4": ["link4", "link5", "link6",
                                 "gripper_link", "gripper_left", "gripper_right"],
                      "joint5": ["link5", "link6", "gripper_link",
                                 "gripper_left", "gripper_right"],
                      "joint6": ["link6", "gripper_link", "gripper_left",
                                 "gripper_right"]}
        prev_anchor = {"link1": self.clamp_l1}
        for ji, j in enumerate(arm.rev[1:], start=2):
            jn = j["name"]
            TF = arm.joint_frame(j, [0.0] * 6)
            a_l = np.asarray(j["axis"], float)
            a_l = a_l / np.linalg.norm(a_l)
            _, e1, e2 = orthobasis(a_l)
            parent, child = j["parent"], j["child"]
            qs = [j["lo"] + f * (j["hi"] - j["lo"])
                  for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
            qs3 = [j["lo"], 0.0, j["hi"]]
            T_parent_F = arm.origin_T(j)
            pref_pt_F = xform(np.linalg.inv(T_parent_F), prev_anchor[parent])
            a_pref = math.atan2(float(pref_pt_F @ e2), float(pref_pt_F @ e1))
            TSF = arm.mount @ TF
            dz = TSF[:3, :3].T @ minus_zS
            dz = dz - a_l * (dz @ a_l)
            if np.linalg.norm(dz) < 1e-9:
                dz = e1.copy()
            a_zpref = math.atan2(float(dz @ e2), float(dz @ e1))

            # geometry sets in F: parent chain (static) + IMMEDIATE child
            # posed over the crossing joint range.  Downstream-link
            # interference is not approximated here; it is MEASURED exactly
            # by the full sweep against all bodies at every state.
            parent_set = []
            for lnk in ARM_LINKS[:ARM_LINKS.index(parent) + 1]:
                parent_set.append(self.link_verts_in_F(lnk, TF))
            Vp_all = np.vstack(parent_set)
            child_q = []
            for q in qs:
                qv = [0.0] * 6
                qv[ji - 1] = q
                child_q.append((q, self._verts_in_F_at(child, TF, qv)))
            # for the wrist roll joints the gripper assembly is rigid with
            # link6 and rotates about joint6: include it in the j6 child set
            if jn == "joint6":
                extra_q = []
                for q in qs:
                    qv = [0.0] * 6
                    qv[ji - 1] = q
                    Vs = [child_q[[qq for qq, _ in child_q].index(q)][1]]
                    for lnk in ("gripper_link", "gripper_left", "gripper_right"):
                        Vs.append(self._verts_in_F_at(lnk, TF, qv))
                    extra_q.append((q, np.vstack(Vs)))
                child_q = extra_q

            if jn in ("joint2", "joint3", "joint4"):
                self._derive_bypass(jn, j, TF, a_l, e1, e2, Vp_all, child_q,
                                    a_pref, a_zpref, pref_pt_F, prev_anchor)
            else:
                self._derive_wrap(jn, j, TF, a_l, e1, e2, Vp_all, child_q,
                                  prev_anchor)

        # ---- bus-side fixed anchors (documented candidates) -----------------
        beta2 = math.radians(-142.0)
        self.P0 = np.array([171.0, 0.0, -70.0])   # HN-01 declared passage mouth
        self.P1 = np.array([200.0, 118.0 * math.cos(beta2 + 0.15),
                            118.0 * math.sin(beta2 + 0.15)])   # HC-1 candidate
        self.P2 = np.array([272.0, 121.0 * math.cos(beta2),
                            121.0 * math.sin(beta2)])          # HC-2 candidate

        self._build_bus_grid()
        self._derive_span_obstacles()
        self._derive_spans()

    def _spine_azimuth(self, link, p):
        """azimuth of point p (link frame) about the link spine."""
        o_a, o_b = self.spines[link]
        sd = o_b - o_a
        sd = sd / np.linalg.norm(sd)
        _, s1, s2 = orthobasis(sd)
        v = np.asarray(p, float) - o_a
        return math.atan2(float(v @ s2), float(v @ s1))

    def _line_penetration(self, link, p_from, p_to, margin):
        """max penetration (mm) of the straight segment p_from->p_to into
        the link's own body beyond `margin` clearance, exact queries."""
        fld = self.fields_local[link]
        p_from = np.asarray(p_from, float)
        p_to = np.asarray(p_to, float)
        L = float(np.linalg.norm(p_to - p_from))
        n = max(2, int(L / 10.0))
        worst = 0.0
        for t in np.linspace(0, 1, n + 1):
            d, exact = fld.min_dist(p_from + t * (p_to - p_from))
            if exact:
                worst = max(worst, margin - d)
        return worst

    # ------------------------------------------------------------------------
    def _derive_bypass(self, jn, j, TF, a_l, e1, e2, Vp_all, child_q,
                       a_pref, a_zpref, pref_pt_F, prev_anchor):
        parent, child = j["parent"], j["child"]
        # axial extent about the axis over BOTH the parent chain (static)
        # and the child-side set (posed): the bypass legs/U-turn must sit
        # beyond EVERYTHING on the chosen side - then no body can share the
        # leg stations at any q (rotation preserves the axial coordinate).
        lo_u = float((Vp_all @ a_l).min())
        hi_u = float((Vp_all @ a_l).max())
        for q, Vc in child_q:
            u = Vc @ a_l
            lo_u = min(lo_u, float(u.min()))
            hi_u = max(hi_u, float(u.max()))
        # housing split by function:
        #  r_fix   - out leg (parent-fixed azimuth alpha, window +-50)
        #  r_swept - return leg + U-turn sweep [alpha+lo, alpha+hi] +-50 vs the
        #            STATIC parent chain (union over q samples)
        #  r_child - return leg vs its OWN child body (static in child frame,
        #            narrow +-20 window; the leg rotates with the child)
        best = None
        lo, hi = j["lo"], j["hi"]
        for sgn in (1.0, -1.0):
            ext = hi_u if sgn > 0 else -lo_u
            s_leg = sgn * (ext + 10.0)        # leg starts past ALL extents
            s_b = sgn * (ext + 10.0 + self.LEG_AX)
            ulo = min(s_leg, s_b + sgn * 95.0) - 1.0
            uhi = max(s_leg, s_b + sgn * 95.0) + 1.0

            def corridor_max(V, azc, win_rad):
                u = V @ a_l
                m = (u >= ulo) & (u <= uhi)
                if not m.any():
                    return 0.0
                Vb = V[m]
                az = np.arctan2(Vb @ e2, Vb @ e1)
                rad = np.sqrt((Vb @ e1) ** 2 + (Vb @ e2) ** 2)
                dd = np.abs((az - azc + math.pi) % (2 * math.pi) - math.pi)
                mm = dd <= win_rad
                return float(rad[mm].max()) if mm.any() else 0.0

            for k in range(24):
                alpha = math.radians(k * 15.0)
                r_fix = corridor_max(Vp_all, alpha, math.radians(50.0))
                r_swept = 0.0
                for q, _ in child_q:
                    r_swept = max(r_swept, corridor_max(
                        Vp_all, alpha + q, math.radians(50.0)))
                # child body is static in its own frame: evaluate at q=0
                Vc0 = child_q[[qq for qq, _ in child_q].index(0.0)][1]                     if any(abs(qq) < 1e-12 for qq, _ in child_q) else child_q[0][1]
                r_child = corridor_max(Vc0, alpha, math.radians(20.0))
                r_b = max(self.R_BYPASS_FLOOR, r_fix + 12.0)
                r_out = max(r_b + self.LEG_RADIAL_SEP, r_swept + 12.0,
                            r_child + 5.0)
                A_p_F = s_leg * a_l + r_b * (math.cos(alpha) * e1
                                             + math.sin(alpha) * e2)
                A_p_link = xform(np.linalg.inv(self.T0[parent]) @ TF, A_p_F)
                # reversal penalty: span approach vs leg direction
                ap = A_p_F - pref_pt_F
                nap = np.linalg.norm(ap)
                d_app = float(ap / nap @ (sgn * a_l)) if nap > 1e-9 else 1.0
                pen_rev = 120.0 * max(0.0, 0.3 - d_app)
                # side consistency: entry anchor must sit on the SAME side
                # of the parent link as the previous crossing's exit anchor
                az_prev = self._spine_azimuth(parent, prev_anchor[parent])
                az_cand = self._spine_azimuth(parent, A_p_link)
                pen_side = 200.0 * abs(
                    (az_cand - az_prev + math.pi) % (2 * math.pi) - math.pi) / math.pi
                # body-tunneling: HARD filter - the straight run from the
                # previous anchor to this entry anchor must hold >= 8 mm
                # exact clearance vs the parent-side field sets
                pen_tunnel = 0.0
                fsets_p = self._span_field_sets(parent)
                seg = A_p_link - prev_anchor[parent]
                segL = float(np.linalg.norm(seg))
                for tt in np.linspace(0, 1, max(2, int(segL / 8.0))):
                    dm = self._mmd(fsets_p, prev_anchor[parent] + tt * seg)
                    if dm < 8.0:
                        pen_tunnel = 1000.0 + 20.0 * (8.0 - dm)
                        break
                d_cont = abs((alpha - a_pref + math.pi) % (2 * math.pi) - math.pi)
                d_out = abs((alpha - a_zpref + math.pi) % (2 * math.pi) - math.pi)
                score = (0.5 * r_b + 0.5 * r_out + 150.0 * d_cont / math.pi
                         + 1.5 * d_out / math.pi + 0.2 * abs(s_b) + pen_rev
                         + pen_tunnel + pen_side)
                if best is None or score < best[0]:
                    best = (score, alpha, sgn, s_b, s_leg, r_b, r_out,
                            max(r_fix, r_swept))
                if os.environ.get("HRN_DEBUG") == "1":
                    print("    DBG %s sgn=%+.0f alpha=%6.1f s_b=%7.1f r_b=%7.1f"
                          " r_out=%7.1f fix=%6.1f swept=%6.1f child=%6.1f"
                          " pen=%5.1f score=%7.1f" % (
                              jn, sgn, math.degrees(alpha), s_b, r_b, r_out,
                              r_fix, r_swept, r_child, pen_rev, score))
        _, alpha, sgn, s_b, s_leg, r_b, r_out, r_cor = best
        entry_F = s_leg * a_l + r_b * (math.cos(alpha) * e1
                                       + math.sin(alpha) * e2)
        exit_F = s_leg * a_l + r_out * (math.cos(alpha) * e1
                                        + math.sin(alpha) * e2)
        self.crossings[jn] = dict(
            type="bypass", alpha=alpha, station=0.0, radius=r_b, r_out=r_out,
            housing_radius=r_cor, s_bypass=s_b, s_leg=s_leg, sgn=sgn,
            a=a_l, e1=e1, e2=e2, preferred_azimuth=a_pref,
            outward_azimuth=a_zpref, parent=parent, child=child,
            lo=j["lo"], hi=j["hi"], entry_F=entry_F, exit_F=exit_F,
            topology="axial_side_bypass_loop")
        prev_anchor[child] = exit_F

    # ------------------------------------------------------------------------
    def _derive_wrap(self, jn, j, TF, a_l, e1, e2, Vp_all, child_q,
                     prev_anchor):
        arm = self.arm
        parent, child = j["parent"], j["child"]
        # hub scan: full-circle max radial within band, downstream capped
        best = None
        for s in np.arange(-40.0, 40.01, 5.0):
            r_h = 0.0
            u = Vp_all @ a_l
            m = np.abs(u - s) <= self.WRAP_BAND
            if m.any():
                Vb = Vp_all[m]
                rad = np.sqrt((Vb @ e1) ** 2 + (Vb @ e2) ** 2)
                r_h = float(rad.max())
            for q, Vc in child_q:
                u = Vc @ a_l
                m = np.abs(u - s) <= self.WRAP_BAND
                if not m.any():
                    continue
                Vb = Vc[m]
                rad = np.sqrt((Vb @ e1) ** 2 + (Vb @ e2) ** 2)
                own = rad[rad <= self.DOWNSTREAM_R_CAP]
                if len(own):
                    r_h = max(r_h, float(own.max()))
            score = r_h + 0.3 * abs(s)
            if best is None or score < best[0]:
                best = (score, s, r_h)
        _, s_w, r_h = best
        r_w = max(26.0, r_h + self.WRAP_MARGIN)
        # moving-clamp azimuth: continuity with the incoming span + exact
        # no-tunnel check for the parent-side straight approach
        pref_pt_F = xform(np.linalg.inv(arm.origin_T(j)), prev_anchor[parent])
        a_pref = math.atan2(float(pref_pt_F @ e2), float(pref_pt_F @ e1))
        best_az = None
        for k in range(24):
            az = math.radians(k * 15.0)
            beta0_c = az + j["lo"] - self.WRAP_MIN
            Cf_F = s_w * a_l + r_w * (math.cos(beta0_c) * e1
                                      + math.sin(beta0_c) * e2)
            Cf_link = xform(np.linalg.inv(self.T0[parent]) @ TF, Cf_F)
            pen = 0.0
            fsets_p = self._span_field_sets(parent)
            seg = Cf_link - prev_anchor[parent]
            segL = float(np.linalg.norm(seg))
            for tt in np.linspace(0, 1, max(2, int(segL / 8.0))):
                dm = self._mmd(fsets_p, prev_anchor[parent] + tt * seg)
                if dm < 8.0:
                    pen = 1000.0 + 20.0 * (8.0 - dm)
                    break
            d_cont = abs((az - a_pref + math.pi) % (2 * math.pi) - math.pi)
            score = 150.0 * d_cont / math.pi + pen
            if best_az is None or score < best_az[0]:
                best_az = (score, az)
        az_c = best_az[1]
        q_lo = j["lo"]
        beta0 = az_c + q_lo - self.WRAP_MIN      # sweep sign +1
        entry_F = s_w * a_l + r_w * (math.cos(beta0) * e1 + math.sin(beta0) * e2)
        exit_F = s_w * a_l + r_w * (math.cos(az_c) * e1 + math.sin(az_c) * e2)
        self.crossings[jn] = dict(
            type="wrap", alpha=az_c, station=s_w, radius=r_w,
            housing_radius=r_h, beta0=beta0, w_min=self.WRAP_MIN,
            a=a_l, e1=e1, e2=e2, preferred_azimuth=az_c,
            parent=parent, child=child, lo=j["lo"], hi=j["hi"],
            entry_F=entry_F, exit_F=exit_F,
            topology="clock_spring_wrap_wrist")
        prev_anchor[child] = exit_F

    # ------------------------------------------------------------------------
    # ------------------------------------------------------------------------
    def _build_bus_grid(self):
        """bus proxy AABB surface sampled on a ~30 mm grid (S frame)."""
        hx, hy, hz = 170.25, 113.15, 113.15
        pts = []
        for fixed, axis in ((hx, 0), (hy, 1), (hz, 2)):
            for sgn in (1.0, -1.0):
                u = np.arange(-[hx, hy, hz][(axis + 1) % 3],
                              [hx, hy, hz][(axis + 1) % 3] + 1, 30.0)
                v = np.arange(-[hx, hy, hz][(axis + 2) % 3],
                              [hx, hy, hz][(axis + 2) % 3] + 1, 30.0)
                for uu in u:
                    for vv in v:
                        p = [0.0, 0.0, 0.0]
                        p[axis] = sgn * fixed
                        p[(axis + 1) % 3] = uu
                        p[(axis + 2) % 3] = vv
                        pts.append(p)
        self.bus_grid_S = np.array(pts)

    def _derive_span_obstacles(self):
        """per-link obstacle sets for the span profile: own body, plus the
        base_link and the bus proxy for link1/link2 (root region), plus the
        gripper assembly + rail swept volumes (rigid) for link6.  All other
        body interactions are MEASURED exactly by the sweep, not
        approximated here."""
        arm = self.arm
        sets = {l: [(self.verts_local[l], STANDOFF + 3.0)]
                for l in ("link1", "link2", "link3", "link4", "link5",
                          "link6")}
        for link in ("link1", "link2"):
            k = int(link[-1])
            for q1 in (arm.rev[0]["lo"], 0.0, arm.rev[0]["hi"]):
                poses = [[q1] + [0.0] * 5]
                if k == 2:
                    poses += [[q1, arm.rev[1]["lo"]] + [0.0] * 4,
                              [q1, arm.rev[1]["hi"]] + [0.0] * 4]
                for qv in poses:
                    T = arm.fk(qv)
                    M = np.linalg.inv(T[link]) @ T["base_link"]
                    sets[link].append((self.verts_local["base_link"]
                                       @ M[:3, :3].T + M[:3, 3],
                                       STANDOFF + 5.0))
                    Mb = np.linalg.inv(T[link]) @ np.linalg.inv(arm.mount)
                    sets[link].append((self.bus_grid_S @ Mb[:3, :3].T
                                       + Mb[:3, 3], STANDOFF + 5.0))
        # link6: gripper assembly (static relative) + rail swept volumes
        Tl6 = self.T0["link6"]
        for g in ("gripper_link", "gripper_left", "gripper_right"):
            M = np.linalg.inv(Tl6) @ self.T0[g]
            sets["link6"].append((self.verts_local[g] @ M[:3, :3].T + M[:3, 3],
                                  STANDOFF + 3.0))
        if self.rail_verts_gripper is not None and len(self.rail_verts_gripper):
            M = np.linalg.inv(Tl6) @ self.T0["gripper_link"]
            sets["link6"].append((self.rail_verts_gripper @ M[:3, :3].T
                                  + M[:3, 3], STANDOFF + 3.0))
        self.span_obstacles = sets

    # ------------------------------------------------------------------------
    def anchor_entry_link(self, jname, link):
        """parent-side anchor (entry_F, joint-frame-local) in `link` frame."""
        arm = self.arm
        j = next(jj for jj in arm.rev if jj["name"] == jname)
        TF = arm.joint_frame(j, [0.0] * 6)
        M = np.linalg.inv(self.T0[link]) @ TF
        return xform(M, self.crossings[jname]["entry_F"])

    def anchor_exit_child(self, jname):
        """child-side anchor in the child-link frame (== F-local at q0)."""
        return self.crossings[jname]["exit_F"]

    def dir_in_link(self, jn, link, d_F):
        """direction vector from joint-frame-local of `jn` into `link`."""
        j = next(jj for jj in self.arm.rev if jj["name"] == jn)
        TF = self.arm.joint_frame(j, [0.0] * 6)
        M = np.linalg.inv(self.T0[link]) @ TF
        dv = M[:3, :3] @ np.asarray(d_F, float)
        n = np.linalg.norm(dv)
        return dv / n if n > 1e-12 else dv

    def span_hints(self, jn, side):
        """tangent hint for a span at the crossing `jn`; side='start' uses
        the child-side (exit) tangent, 'end' the parent-side (entry)
        tangent.  Vectors are F-local of the crossing; for the child side
        F-local == child frame at q0."""
        c = self.crossings[jn]
        if c["type"] == "bypass":
            sgn = c["sgn"]
            return (-sgn * c["a"]) if side == "start" else (sgn * c["a"])
        # wrist wrap: arc tangent is azimuthal
        if side == "start":
            ph = c["alpha"]            # moving clamp azimuth (child frame)
        else:
            ph = c["beta0"]            # fixed clamp azimuth (parent frame)
        return -math.sin(ph) * c["e1"] + math.cos(ph) * c["e2"]

    # ------------------------------------------------------------------------
    def _straight_span_clearance(self, link, A, B):
        """min exact clearance of the straight segment vs the link's
        field sets (inf if all beyond the exact horizon)."""
        fsets = self._span_field_sets(link)
        seg = np.asarray(B, float) - np.asarray(A, float)
        L = float(np.linalg.norm(seg))
        worst = math.inf
        for t in np.linspace(0, 1, max(2, int(L / 4.0))):
            dm = self._mmd(fsets, np.asarray(A, float) + t * seg)
            worst = min(worst, dm)
        return worst

    def _derive_spans(self):
        tgt = self.anchor_entry_link("joint2", "link1")
        hint_end = self.dir_in_link("joint2", "link1",
                                    self.span_hints("joint2", "end"))
        self.spans["link1"] = self._make_span("link1", self.clamp_l1, tgt,
                                              self.coil_tan_l1, hint_end)
        for ji, j in enumerate(self.arm.rev[1:], start=2):
            jn = j["name"]
            c = self.crossings[jn]
            child = j["child"]
            hint_start = self.span_hints(jn, "start")
            if ji < 6:
                nxt = self.arm.rev[ji]["name"]
                tgt_l = self.anchor_entry_link(nxt, child)
                hint_e = self.dir_in_link(nxt, child,
                                          self.span_hints(nxt, "end"))
            else:
                tgt_l = xform(tr(0, 0, 159.71) @ rot_rpy(0, -1.5708, 0),
                              self.G0)
                hint_e = None
            self.spans[child] = self._make_span(child, c["exit_F"], tgt_l,
                                                hint_start, hint_e)

    def _make_span(self, link, A, B, tan_start, tan_end):
        """straight line if it holds >= 8 mm exact clearance everywhere,
        else the v7 curved candidates.  Cache tuple:
        (pts, length, min_radius, design_margin, straight_flag)."""
        clr = self._straight_span_clearance(link, A, B)
        if clr >= 8.0:
            pts, L = seg_line(np.asarray(A, float), np.asarray(B, float))
            self._span_straight = getattr(self, "_span_straight", {})
            self._span_straight[link] = True
            return pts, L, math.inf, clr, True
        self._span_straight = getattr(self, "_span_straight", {})
        self._span_straight[link] = False
        pts, L, R, dm = self.span_path(link, A, B, tan_start, tan_end)
        return pts, L, R, dm, False

    class _MappedField:
        """field viewed through a rigid transform M (query frame -> field
        frame); distance is rigid-invariant.  Design-time (q0-relative)
        approximation for neighboring bodies - the sweep measures all
        poses exactly."""

        def __init__(self, fld, M):
            self.fld = fld
            self.M = M
            self.D = fld.D

        def min_dist(self, p):
            return self.fld.min_dist(xform(self.M, p))

    def _span_field_sets(self, link):
        """(field, margin) sets used by the span exact-push."""
        arm = self.arm
        Tl = self.T0[link]
        out = [(self.fields_local[link], STANDOFF + 3.0)]
        if link in ("link1", "link2"):
            Mb = np.linalg.inv(Tl)                     # base == A0 identity
            out.append((self._MappedField(self.fields_local["base_link"], Mb),
                        STANDOFF + 5.0))
            if self.bus_field is not None:
                Mu = np.linalg.inv(Tl) @ np.linalg.inv(arm.mount)
                out.append((self._MappedField(self.bus_field, Mu),
                            STANDOFF + 5.0))
        # adjacent links at the q0 relative pose (design-time only; the
        # sweep measures every pose exactly)
        adj = {"link1": ["link2"], "link2": ["link1", "link3"],
               "link3": ["link2", "link4"], "link4": ["link3", "link5"],
               "link5": ["link4", "link6"]}
        for g in adj.get(link, []):
            M = np.linalg.inv(Tl) @ self.T0[g]
            out.append((self._MappedField(self.fields_local[g], M),
                        STANDOFF + 5.0))
        if link == "link6":
            for g in ("gripper_link", "gripper_left", "gripper_right"):
                M = np.linalg.inv(Tl) @ self.T0[g]
                out.append((self._MappedField(self.fields_local[g], M),
                            STANDOFF + 3.0))
            Mg = np.linalg.inv(Tl) @ self.T0["gripper_link"]
            for rf in self.rail_fields:
                out.append((self._MappedField(rf, Mg), STANDOFF + 3.0))
        return out

    def _mmd(self, fsets, p):
        best = math.inf
        for fld, margin in fsets:
            d, exact = fld.min_dist(p)
            if exact:
                best = min(best, d - margin)
        return best

    def _marched_segment(self, fsets, P0, P1, s_dir):
        """stations along P0->P1 marched along s_dir until exact clearance;
        returns (ts, g, L, feasible).  Endpoints pinned (offset 0)."""
        ab = P1 - P0
        L = float(np.linalg.norm(ab))
        n_sta = max(3, int(L / 10.0))
        ts = np.linspace(0.0, 1.0, n_sta + 1)
        g = np.zeros(n_sta + 1)
        feas = True
        for i in range(1, n_sta):
            t = ts[i]
            p0 = P0 + t * ab
            gi = 0.0
            while self._mmd(fsets, p0 + gi * s_dir) < 0.0 and gi < 120.0:
                gi += 4.0
            if self._mmd(fsets, p0 + gi * s_dir) < 0.0:
                feas = False
            g[i] = gi
        return ts, g, L, feas

    def _env_profile(self, ts, g, L):
        """upper Lipschitz envelope (slope 0.6) with zero-pinned ends,
        then smoothing passes (no kinks -> honest Menger radius)."""
        cons_x = [0.0, L]
        cons_g = [0.0, 0.0]
        for t, gi in zip(ts, g):
            if 1e-9 < t < 1 - 1e-9:
                cons_x.append(t * L)
                cons_g.append(gi)
        cons_x = np.array(cons_x)
        cons_g = np.array(cons_g)
        env = np.array([float((cons_g - 0.6 * np.abs(cons_x - t * L)).max())
                        for t in ts])
        env[0] = 0.0
        env[-1] = 0.0
        if len(env) > 2:
            env[1:-1] = smooth_profile(env[1:-1], passes=4, lift=1.5)
        return env

    def _span_candidates(self, link, A, B):
        """v7 candidate families: (S) straight + exact push along one
        consistent side; (C) cylindrical wrap about the spine; (E) around
        either spine end.  Each returns (ctrl, feasible, excursion, L)."""
        A = np.asarray(A, float)
        B = np.asarray(B, float)
        fsets = self._span_field_sets(link)
        ab = B - A
        L_ab = float(np.linalg.norm(ab))
        u_dir = ab / max(L_ab, 1e-9)
        o_a, o_b = self.spines[link]
        sd = o_b - o_a
        sd = sd / max(np.linalg.norm(sd), 1e-9)
        _, s1, s2 = orthobasis(sd)

        def radial(p):
            n = p - (o_a + ((p - o_a) @ sd) * sd)
            ln = np.linalg.norm(n)
            return n / ln if ln > 1e-6 else None

        nA = radial(A)
        nB = radial(B)
        s = (nA + nB) if (nA is not None and nB is not None) else None
        if s is not None:
            s = s - u_dir * (s @ u_dir)
        if s is not None and np.linalg.norm(s) > 1e-6:
            side0 = s / np.linalg.norm(s)
        else:
            side0 = np.array([0.0, 0.0, 1.0])
        perp = np.cross(u_dir, side0)
        perp = perp / max(np.linalg.norm(perp), 1e-9)

        out = []
        for s_dir in (side0, -side0, perp, -perp):
            ts, g, L, feas = self._marched_segment(fsets, A, B, s_dir)
            env = self._env_profile(ts, g, L)
            ctrl = [A + t * ab + float(e) * s_dir for t, e in zip(ts, env)]
            exc = float(env.max()) if len(env) else 0.0
            out.append((ctrl, feas, exc, L_ab))

        # family C: cylindrical wrap about the spine (short way)
        uA = float((A - o_a) @ sd)
        uB = float((B - o_a) @ sd)
        rA = float(np.linalg.norm(A - (o_a + uA * sd)))
        rB = float(np.linalg.norm(B - (o_a + uB * sd)))
        azA = math.atan2(float((A - o_a) @ s2), float((A - o_a) @ s1))
        azB = math.atan2(float((B - o_a) @ s2), float((B - o_a) @ s1))
        dphi = (azB - azA + math.pi) % (2 * math.pi) - math.pi
        n_mid = max(3, int(L_ab / 12.0))
        tsc = np.linspace(0.0, 1.0, n_mid + 1)
        gc = np.zeros(n_mid + 1)
        feas = True
        for i in range(1, n_mid):
            t = tsc[i]
            u = uA + t * (uB - uA)
            az = azA + t * dphi
            n_u = math.cos(az) * s1 + math.sin(az) * s2
            r = 8.0
            while self._mmd(fsets, o_a + u * sd + r * n_u) < 0.0 and r < 150.0:
                r += 4.0
            if self._mmd(fsets, o_a + u * sd + r * n_u) < 0.0:
                feas = False
            gc[i] = r
        envc = self._env_profile(tsc, gc, L_ab)
        ctrl = []
        for i, t in enumerate(tsc):
            if i == 0:
                ctrl.append(A)
                continue
            if i == n_mid:
                ctrl.append(B)
                continue
            u = uA + t * (uB - uA)
            az = azA + t * dphi
            n_u = math.cos(az) * s1 + math.sin(az) * s2
            ctrl.append(o_a + u * sd + float(envc[i]) * n_u)
        out.append((ctrl, feas, float(envc.max()), L_ab))

        # family E: around each spine end
        for o_end, end_sgn in ((o_a, -1.0), (o_b, 1.0)):
            n_mid_dir = radial(0.5 * (A + B))
            if n_mid_dir is None:
                n_mid_dir = side0
            r_e = 10.0
            while (self._mmd(fsets, o_end + end_sgn * 25.0 * sd
                             + r_e * n_mid_dir) < 0.0 and r_e < 140.0):
                r_e += 5.0
            E = o_end + end_sgn * 25.0 * sd + r_e * n_mid_dir
            feas_e = r_e < 140.0
            ctrl = [A]
            exc = r_e
            for P0, P1 in ((A, E), (E, B)):
                seg = P1 - P0
                segL = float(np.linalg.norm(seg))
                su = seg / max(segL, 1e-9)
                n_s = radial(0.5 * (P0 + P1))
                if n_s is None:
                    n_s = side0
                n_s = n_s - su * (n_s @ su)
                if np.linalg.norm(n_s) < 1e-6:
                    n_s = side0
                n_s = n_s / np.linalg.norm(n_s)
                ts2, g2, L2, feas2 = self._marched_segment(fsets, P0, P1, n_s)
                feas_e = feas_e and feas2
                env2 = self._env_profile(ts2, g2, L2)
                for t, e in zip(ts2, env2):
                    if t < 1e-9 or t > 1 - 1e-9:
                        continue
                    ctrl.append(P0 + t * seg + float(e) * n_s)
                if len(env2):
                    exc = max(exc, float(env2.max()))
            ctrl.append(B)
            out.append((ctrl, feas_e, exc,
                        float(np.linalg.norm(E - A)
                              + np.linalg.norm(B - E))))
        return out

    def span_path(self, link, A, B, tan_start=None, tan_end=None):
        """evaluate all span candidates; pick by (feasible, min CR radius,
        excursion, length); exact-repair subdivision; returns (points,
        length, min Menger radius, design margin diagnostic)."""
        ab = np.asarray(B, float) - np.asarray(A, float)
        u_dir = ab / max(np.linalg.norm(ab), 1e-9)
        fsets = self._span_field_sets(link)
        best = None
        for ctrl0, feasible, excursion, L0 in self._span_candidates(link, A, B):
            ctrl = [ctrl0[0]]
            if tan_start is not None:
                tsv = np.asarray(tan_start, float)
                tsv = tsv / max(np.linalg.norm(tsv), 1e-9)
                if float(tsv @ u_dir) >= 0.3:
                    ctrl.append(ctrl0[0] + 40.0 * tsv)
            ctrl.extend(ctrl0[1:-1])
            if tan_end is not None:
                tev = np.asarray(tan_end, float)
                tev = tev / max(np.linalg.norm(tev), 1e-9)
                if float(tev @ u_dir) >= 0.3:
                    ctrl.append(ctrl0[-1] - 40.0 * tev)
            ctrl.append(ctrl0[-1])
            pts = catmull_rom(ctrl, SAMPLE_DS)
            for _repair in range(4):
                worst = None
                for ip, p in enumerate(pts):
                    dm = self._mmd(fsets, p)
                    if dm < 0 and (worst is None or dm < worst[0]):
                        worst = (dm, ip)
                if worst is None:
                    break
                wp = pts[worst[1]]
                ci = int(np.argmin([np.linalg.norm(c - wp) for c in ctrl]))
                ctrl.insert(ci + 1, np.asarray(wp, float))
                pts = catmull_rom(ctrl, SAMPLE_DS)
            L = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
            R = discrete_radius(pts)
            rmin = float(np.min(R)) if len(R) else math.inf
            score = ((0 if feasible else 1e6) - 100.0 * min(rmin, 40.0)
                     + excursion + 0.1 * L)
            if best is None or score < best[0]:
                best = (score, pts, L, rmin, feasible, excursion, ctrl)
        _, pts, L, rmin, feasible, excursion, ctrl = best
        dm = math.inf
        for p in pts[::2]:
            dm = min(dm, self._mmd(fsets, p))
        self._span_debug = getattr(self, "_span_debug", {})
        self._span_debug[link] = (feasible, [list(np.round(c, 1)) for c in ctrl])
        return pts, L, rmin, dm

    # ------------------------------------------------------------------------
    def build(self, q6):
        arm = self.arm
        TS = arm.fk_S(q6)

        def to_S(link, p):
            return xform(TS[link], p)

        nodes = []
        conns = []
        fillet_nodes = []
        sections = {}

        HC3 = to_S("link1", self.clamp_l1)
        th_m = azimuth(HC3, self.coil_center_S, self.coil_e1_S, self.coil_e2_S)
        s = self.coil_sign
        wrap = 2 * math.pi + q6[0]    # winds up 1:1 with q1 (R2-HRN-05 fix)
        phi_end = self.coil_beta0 + s * wrap
        d_az = (s * (phi_end - th_m)) % (2 * math.pi)
        az_res = min(d_az, 2 * math.pi - d_az)
        C0 = (self.coil_center_S
              + COIL_R * (math.cos(self.coil_beta0) * self.coil_e1_S
                          + math.sin(self.coil_beta0) * self.coil_e2_S))
        sections["joint1_coil"] = dict(
            radius=COIL_R, wrap_rad=round(wrap, 4),
            clamp_azimuth_residual_rad=round(az_res, 6))

        nodes.append(self.P0)
        conns.append(Connector("line", p0=self.P0, p1=self.P1, label="bus_P0_P1"))
        nodes.append(self.P1)
        fillet_nodes.append(1)
        conns.append(Connector("line", p0=self.P1, p1=self.P2, label="bus_P1_P2"))
        nodes.append(self.P2)
        fillet_nodes.append(2)
        conns.append(Connector("line", p0=self.P2, p1=C0, label="bus_P2_C0"))
        nodes.append(C0)
        fillet_nodes.append(3)
        conns.append(Connector("arc", center=self.coil_center_S,
                               e1=self.coil_e1_S, e2=self.coil_e2_S,
                               r=COIL_R, phi0=self.coil_beta0, phi1=phi_end,
                               label="joint1_coil"))
        nodes.append(HC3)
        fillet_nodes.append(4)

        # span on link1: HC-3 -> j2 entry anchor (design-time cache)
        sp_pts, sp_L, sp_R, sp_dm, sp_st = self.spans["link1"]
        sp_S = sp_pts @ TS["link1"][:3, :3].T + TS["link1"][:3, 3]
        conns.append(Connector("poly", pts=sp_S, label="span_link1"))
        sections["span_link1"] = dict(length_mm=round(sp_L, 2),
                                      min_radius_mm=round(sp_R, 2),
                                      design_margin_mm=round(sp_dm, 2),
                                      straight=bool(sp_st))

        for ji, j in enumerate(arm.rev[1:], start=2):
            jn = j["name"]
            c = self.crossings[jn]
            q = q6[ji - 1]
            TF_S = TS[j["parent"]] @ self.arm.origin_T(j)
            R = TF_S[:3, :3]
            t = TF_S[:3, 3]
            a_S = R @ c["a"]
            e1_S = R @ c["e1"]
            e2_S = R @ c["e2"]
            child = j["child"]

            if c["type"] == "bypass":
                r_b = c["radius"]
                r_out = c["r_out"]
                s_b = c["s_bypass"]
                alpha = c["alpha"]
                sgn = c["sgn"]
                a_out = sgn * a_S
                A_p_S = xform(TF_S, c["entry_F"])
                B_p_S = (t + r_b * (math.cos(alpha) * e1_S
                                    + math.sin(alpha) * e2_S) + s_b * a_S)
                B_c_S = (t + r_out * (math.cos(alpha + q) * e1_S
                                      + math.sin(alpha + q) * e2_S) + s_b * a_S)
                A_c_S = to_S(child, c["exit_F"])
                w = B_c_S - B_p_S
                chord = float(np.linalg.norm(w))
                w_hat = w / max(chord, 1e-9)
                R_turn = chord / 2.0
                M_S = 0.5 * (B_p_S + B_c_S)
                sections[jn + "_loop"] = dict(
                    bypass_radius_mm=round(r_b, 2),
                    bypass_station_mm=round(s_b, 1),
                    turn_radius_mm=round(R_turn, 2), dphi_rad=round(q, 4))
                nodes.append(A_p_S)
                fillet_nodes.append(len(nodes) - 1)
                conns.append(Connector("line", p0=A_p_S, p1=B_p_S,
                                       label=jn + "_leg_out"))
                nodes.append(B_p_S)
                fillet_nodes.append(len(nodes) - 1)
                conns.append(Connector("arc", center=M_S, e1=-w_hat, e2=a_out,
                                       r=R_turn, phi0=0.0, phi1=math.pi,
                                       label=jn + "_uturn"))
                nodes.append(B_c_S)
                fillet_nodes.append(len(nodes) - 1)
                conns.append(Connector("line", p0=B_c_S, p1=A_c_S,
                                       label=jn + "_leg_return"))
                nodes.append(A_c_S)
                fillet_nodes.append(len(nodes) - 1)
            else:  # wrist clock-spring wrap
                r_w = c["radius"]
                s_w = c["station"]
                W = c["w_min"] + (q - c["lo"])
                phi0 = c["beta0"]
                phi1 = c["beta0"] + W
                center_S = t + s_w * a_S
                Cf_S = xform(TF_S, c["entry_F"])
                Cm_S = to_S(child, c["exit_F"])
                th_cm = azimuth(Cm_S, center_S, e1_S, e2_S)
                d_az = (phi1 - th_cm) % (2 * math.pi)
                az_res = min(d_az, 2 * math.pi - d_az)
                sections[jn + "_wrap"] = dict(
                    wrap_radius_mm=round(r_w, 2), station_mm=round(s_w, 1),
                    wrap_rad=round(W, 4),
                    clamp_azimuth_residual_rad=round(az_res, 6))
                nodes.append(Cf_S)
                fillet_nodes.append(len(nodes) - 1)
                conns.append(Connector("arc", center=center_S, e1=e1_S, e2=e2_S,
                                       r=r_w, phi0=phi0, phi1=phi1,
                                       label=jn + "_wrap"))
                nodes.append(Cm_S)
                fillet_nodes.append(len(nodes) - 1)

            # span on the child link to the next anchor (design-time cache)
            sp_pts, sp_L, sp_R, sp_dm, sp_st = self.spans[child]
            sp_S = sp_pts @ TS[child][:3, :3].T + TS[child][:3, 3]
            conns.append(Connector("poly", pts=sp_S, label="span_" + child))
            sections["span_" + child] = dict(length_mm=round(sp_L, 2),
                                             min_radius_mm=round(sp_R, 2),
                                             design_margin_mm=round(sp_dm, 2),
                                             straight=bool(sp_st))

        nodes.append(to_S("gripper_link", self.G0))

        # ---- fillets + trimmed assembly -------------------------------------
        trims = [[0.0, 0.0] for _ in conns]
        fillets = {}
        for ni in fillet_nodes:
            if ni <= 0 or ni >= len(conns):
                continue
            cin = conns[ni - 1]
            cout = conns[ni]
            _, d_in = cin.eval(1.0)
            _, d_out = cout.eval(0.0)
            f = fillet_at(nodes[ni], d_in, d_out, FILLET_R,
                          cin.length(), cout.length())
            if f is not None:
                fillets[ni] = f
                trims[ni - 1][1] = f[3]
                trims[ni][0] = f[3]

        all_pts = []
        total_L = 0.0
        min_R = math.inf
        min_R_where = None
        for i, con in enumerate(conns):
            if i in fillets:
                fpts, fL, fR, _ = fillets[i]
                all_pts.append(fpts)
                total_L += fL
                if fR < min_R:
                    min_R = fR
                    min_R_where = "fillet_node_%d" % i
            L_full = con.length()
            t0 = trims[i][0] / L_full if L_full > 1e-9 else 0.0
            t1 = 1.0 - (trims[i][1] / L_full if L_full > 1e-9 else 0.0)
            pts, L, Rc = con.sample(t0, t1)
            all_pts.append(pts)
            total_L += L
            if Rc < min_R:
                min_R = Rc
                min_R_where = getattr(con, "label", "%s_%d" % (con.kind, i))
        P = np.vstack(all_pts)
        self.last_build = (conns, fillets, trims, nodes)
        return P, total_L, min_R, min_R_where, sections


def discrete_radius(P):
    if len(P) < 3:
        return np.array([np.inf])
    A = P[:-2]
    B = P[1:-1]
    C = P[2:]
    v1 = B - A
    v2 = C - B
    num = np.sqrt((np.cross(v1, v2) ** 2).sum(1))
    l1 = np.sqrt((v1 * v1).sum(1))
    l2 = np.sqrt((v2 * v2).sum(1))
    l3 = np.sqrt(((C - A) * (C - A)).sum(1))
    with np.errstate(divide="ignore", invalid="ignore"):
        R = np.where(num > 1e-12, l1 * l2 * l3 / (2 * num), np.inf)
    return R


def signed_clearance_point(fld, p_local):
    """signed distance - tube radius at one local-frame point."""
    d, exact = fld.min_dist(p_local)
    if not exact:
        return None
    if d < TUBE_R + 2.0 and fld.inside(p_local):
        d = -d
    return d - TUBE_R


# ---------------------------------------------------------------------------
def main():
    t_start = time.time()
    print("=== R2-HRN-04 full-FK harness sweep (QUICK=%s) ===" % QUICK)

    mount_rows = load_mount()
    arm = ArmModel(URDF, mount_rows)
    print("revolute joints:", [(j["name"], round(j["lo"], 3), round(j["hi"], 3))
                               for j in arm.rev])

    input_files = [URDF, MOUNT_YAML, JOINT_STATES, NAMED_POSE_JSON, ROUTING_YAML,
                   SOLAR_STEP, PALM_SLOT_STEP] + RAIL_STEPS + \
                  [STL_DIR / (l + ".STL") for l in ARM_LINKS] + \
                  [WITNESS[k] for k in WITNESS]
    hashes = {str(p.relative_to(PROJECT_ROOT)): sha256(p) for p in input_files}

    fields_local = {}
    verts_local = {}
    for l in ARM_LINKS:
        tris = mesh_tris(STL_DIR / (l + ".STL"))
        fields_local[l] = TriField(l, tris)
        V = tris.reshape(-1, 3)
        V = np.unique(np.round(V, 3), axis=0)
        verts_local[l] = V
        print("mesh %-13s tris=%6d verts=%6d" % (l, fields_local[l].n, len(V)))

    bus = BoxField("BUS_PROXY", (-170.25, -113.15, -113.15),
                   (170.25, 113.15, 113.15))
    solar_field = TriField("SOLAR_R2_DEPLOYED",
                           shape_tris(Part.read(str(SOLAR_STEP)), 0.3))
    print("solar tris:", solar_field.n)

    # rail swept volumes: validate frame against gripper_link mesh
    gl_field = fields_local["gripper_link"]
    palm_tris = shape_tris(Part.read(str(PALM_SLOT_STEP)), 0.25)
    pv = palm_tris.reshape(-1, 3)
    pv = pv[::max(1, len(pv) // 2000)]
    d_palm = np.array([gl_field.min_dist(p)[0] for p in pv])
    palm_med = float(np.median(d_palm))
    palm_p90 = float(np.percentile(d_palm, 90))
    print("palm-slot-vs-gripper_link vertex dist: median %.3f p90 %.3f mm"
          % (palm_med, palm_p90))
    rail_fields_local = []
    if palm_med < 3.0:
        for rp in RAIL_STEPS:
            rail_fields_local.append(
                TriField(rp.stem, shape_tris(Part.read(str(rp)), 0.25)))
        rail_note = ("rail swept volumes validated against gripper_link mesh "
                     "via palm-slot hugging (median %.3f mm, p90 %.3f mm); "
                     "treated as authored in the gripper_link frame"
                     % (palm_med, palm_p90))
    else:
        rail_note = ("RAIL_FRAME_VALIDATION_FAILED (median %.3f mm >= 3 mm); "
                     "rail swept volumes EXCLUDED; gripper slot exclusion "
                     "recorded as HOLD" % palm_med)
    print(rail_note)
    rail_verts_gripper = (np.vstack([rf.v0 for rf in rail_fields_local])
                          if rail_fields_local else None)

    design = HarnessDesign(arm, verts_local, rail_verts_gripper,
                           fields_local=fields_local,
                           rail_fields=rail_fields_local, bus_field=bus)
    print("crossing design:")
    for jn, c in design.crossings.items():
        print("  %-7s r=%7.2f alpha=%7.1fdeg s=%6.1f pref=%7.1fdeg" % (
            jn, c["radius"], math.degrees(c["alpha"]), c["station"],
            math.degrees(c["preferred_azimuth"])))
    print("clamp_l1 (HC-3):", np.round(design.clamp_l1, 2))
    print("G0 (gripper_link-local):", design.G0)
    print("P1:", np.round(design.P1, 2), " P2:", np.round(design.P2, 2))
    print("coil beta0=%.3f sign=%.0f" % (design.coil_beta0, design.coil_sign))

    # ---- FK validation -------------------------------------------------------
    import yaml
    js = yaml.safe_load(JOINT_STATES.read_text(encoding="utf-8"))["states"]
    fk_report = {}
    fk_pass = True
    for tag, wpath in WITNESS.items():
        st = js[tag]
        q6 = [math.radians(st["joint%d" % i]) for i in range(1, 7)]
        gp = (st.get("gripper_joint1", 0.0) / 1000.0,
              st.get("gripper_joint2", 0.0) / 1000.0)  # joint_states mm -> m
        T = arm.fk(q6, gp)
        w = Part.read(str(wpath))
        compact = []
        elongated = []
        for sld in w.Solids:
            bb = sld.BoundBox
            (compact if max(bb.XLength, bb.YLength, bb.ZLength) <= 6.0
             else elongated).append(sld)
        origins = []
        axes = []
        for j in arm.rev:
            TF = T[j["parent"]] @ arm.origin_T(j)
            origins.append(TF[:3, 3])
            axes.append(TF[:3, :3] @ np.asarray(j["axis"], float))
        TFg = T["link6"] @ tr(0, 0, 159.71) @ rot_rpy(0, -1.5708, 0)
        origins.append(TFg[:3, 3])
        axes.append(None)
        max_o = 0.0
        for o in origins:
            v = Part.Vertex(App.Vector(*o))
            max_o = max(max_o, min(float(v.distToShape(s)[0]) for s in compact))
        max_a = 0.0
        for o, a in zip(origins, axes):
            if a is None:
                continue
            a = a / np.linalg.norm(a)
            v = Part.Vertex(App.Vector(*(o + 15.0 * a)))
            max_a = max(max_a, min(float(v.distToShape(s)[0]) for s in elongated))
        fk_report[tag] = dict(max_origin_residual_mm=round(max_o, 4),
                              max_axis_marker_residual_mm=round(max_a, 4),
                              n_compact_markers=len(compact),
                              n_axis_markers=len(elongated))
        print("FK %-16s origin residual %.4f mm, axis residual %.4f mm"
              % (tag, max_o, max_a))
        if max_o > 1.0 or max_a > 3.0:
            fk_pass = False
    Tb = arm.fk_S([0.0] * 6)["base_link"]
    Vb = verts_local["base_link"] @ Tb[:3, :3].T + Tb[:3, 3]
    base_min_x = float(Vb[:, 0].min())
    fk_report["mount_base_face_x_mm"] = round(base_min_x, 3)
    fk_report["mount_expected_boss_face_x_mm"] = 208.0
    if abs(base_min_x - 208.0) > 1.0:
        fk_pass = False
    print("FK_VALIDATION %s (base face x=%.3f)"
          % ("PASS" if fk_pass else "FAIL", base_min_x))
    if not fk_pass:
        report = {
            "schema": "HARNESS_B601_FULL_FK_SWEEP_V2",
            "generated_local": local_now(),
            "verdict": {"B601_HARNESS_FUNCTIONAL_GATE": "FAIL_FK_VALIDATION"},
            "fk_validation": fk_report,
            "note": "FK vs witness markers exceeded thresholds; sweep NOT run "
                    "(task discipline).",
            "inputs_sha256": hashes,
        }
        OUT_JSON.write_text(json.dumps(report, indent=1), encoding="utf-8")
        OUT_YAML.write_text(yaml_dump(report), encoding="utf-8")
        print("ABORT: FK validation failed")
        return

    # ---- states --------------------------------------------------------------
    states = []
    for ji, j in enumerate(arm.rev):
        for i in range(N_JOINT_SAMPLES):
            q = [0.0] * 6
            q[ji] = j["lo"] + (j["hi"] - j["lo"]) * i / (N_JOINT_SAMPLES - 1)
            states.append(("SWEEP_%s_%02d" % (j["name"], i), q))
    npd = json.loads(NAMED_POSE_JSON.read_text(encoding="utf-8"))
    named = {}
    for pname, pr in npd["pose_results"].items():
        named[pname] = (pr["q_rad"], pr.get("source_hold"))
    named["PREGRASP_SCENE_CANDIDATE"] = (
        npd["pregrasp_scene_candidate"]["q_rad"],
        "DIAGNOSTIC_CANDIDATE_HOLD_FOR_CAPTURE_DYNAMICS")
    for pname, (qv, hold) in named.items():
        states.append(("NAMED_" + pname, list(qv)))
    if DO_CORNERS:
        import itertools
        for bits in itertools.product([0, 1], repeat=6):
            q = [arm.rev[i]["lo"] if bits[i] == 0 else arm.rev[i]["hi"]
                 for i in range(6)]
            states.append(("CORNER_" + "".join(str(b) for b in bits), q))
    rng = np.random.RandomState(20260822)
    lhs = np.zeros((N_LHS, 6))
    for k in range(6):
        perm = rng.permutation(N_LHS)
        lhs[:, k] = (perm + rng.rand(N_LHS)) / N_LHS
    for i in range(N_LHS):
        q = [arm.rev[k]["lo"] + lhs[i, k] * (arm.rev[k]["hi"] - arm.rev[k]["lo"])
             for k in range(6)]
        states.append(("LHS_%02d" % i, q))
    print("total states: %d" % len(states))

    # ---- main sweep: length / bend / clearance -------------------------------
    length_max = (-1.0, None)
    length_min = (1e18, None)
    bend_min = (math.inf, None)
    bend_discrete_min = (math.inf, None)
    clear_worst = (math.inf, None, None, None)
    per_field_min = {}
    coil_wrap_err = 0.0
    n_exact = 0
    n_lb = 0

    def sweep_field(fld, Pl, P, sname, label):
        nonlocal_vars = None
        return None

    def check_field(fld, Pl, P, sname, label, worst, per_min):
        n_e = 0
        n_b = 0
        lb = fld.aabb_lb(Pl)
        idx = np.where(lb < fld.D + 5.0)[0]
        if len(idx) == 0:
            val = float(lb.min()) - TUBE_R
            n_b += 1
            if val < worst[0]:
                worst = (val, sname, label, None)
            if label not in per_min or val < per_min[label][0]:
                per_min[label] = (val, sname + ":LB")
            return worst, per_min, n_e, n_b
        for ii in idx:
            val = signed_clearance_point(fld, Pl[ii])
            if val is None:
                n_b += 1
                continue
            n_e += 1
            if val < worst[0]:
                worst = (val, sname, label, [round(x, 2) for x in P[ii]])
            if label not in per_min or val < per_min[label][0]:
                per_min[label] = (val, sname)
        return worst, per_min, n_e, n_b

    for si, (sname, q6) in enumerate(states):
        TS = arm.fk_S(q6)
        P, L, Rmin, Rwhere, secs = design.build(q6)
        coil_wrap_err = max(coil_wrap_err,
                            secs["joint1_coil"]["clamp_azimuth_residual_rad"])
        if L > length_max[0]:
            length_max = (L, sname)
        if L < length_min[0]:
            length_min = (L, sname)
        if Rmin < bend_min[0]:
            bend_min = (Rmin, sname + ":" + str(Rwhere))
        Rdmin = float(np.min(discrete_radius(P)))
        if Rdmin < bend_discrete_min[0]:
            bend_discrete_min = (Rdmin, sname)

        for fld, Pl in ((bus, P), (solar_field, P)):
            clear_worst, per_field_min, ne, nb = check_field(
                fld, Pl, P, sname, fld.name, clear_worst, per_field_min)
            n_exact += ne
            n_lb += nb
        for lname in ARM_LINKS:
            T = TS[lname]
            Pl = (P - T[:3, 3]) @ T[:3, :3]
            clear_worst, per_field_min, ne, nb = check_field(
                fields_local[lname], Pl, P, sname, lname, clear_worst,
                per_field_min)
            n_exact += ne
            n_lb += nb
        Tg = TS["gripper_link"]
        for rf in rail_fields_local:
            Pl = (P - Tg[:3, 3]) @ Tg[:3, :3]
            clear_worst, per_field_min, ne, nb = check_field(
                rf, Pl, P, sname, rf.name, clear_worst, per_field_min)
            n_exact += ne
            n_lb += nb

        if si % 20 == 0 or si == len(states) - 1:
            print("state %d/%d %-28s L=%7.1f Rmin=%6.2f worst_clear=%8.3f t=%.0fs"
                  % (si + 1, len(states), sname, L, Rmin, clear_worst[0],
                     time.time() - t_start))

    provisioned = length_max[0] * 1.05

    # ---- pinch pass: hard stops + named poses --------------------------------
    pinch_states = []
    for ji, j in enumerate(arm.rev):
        for end in ("lo", "hi"):
            q = [0.0] * 6
            q[ji] = j[end]
            pinch_states.append(("HARDSTOP_%s_%s" % (j["name"], end), q))
    for pname, (qv, hold) in named.items():
        pinch_states.append(("NAMED_" + pname, list(qv)))
    pinch_per_joint = {j["name"]: (math.inf, None) for j in arm.rev}
    pinch_worst = (math.inf, None, None)
    empty_sets = 0
    for sname, q6 in pinch_states:
        TS = arm.fk_S(q6)
        P, L, Rmin, Rwhere, secs = design.build(q6)
        for ji, j in enumerate(arm.rev):
            jn = j["name"]
            c = design.crossings[jn]
            TF = TS[j["parent"]] @ arm.origin_T(j)
            Pl = (P - TF[:3, 3]) @ TF[:3, :3]
            zband = Pl @ c["a"]
            mband = np.abs(zband - c["station"]) <= 40.0
            if not mband.any():
                empty_sets += 1
                continue
            Pb = Pl[mband]
            best = math.inf
            for link in (j["parent"], j["child"]):
                M = np.linalg.inv(TS[link]) @ TF
                Pk = Pb @ M[:3, :3].T + M[:3, 3]
                fld = fields_local[link]
                for p in Pk:
                    val = signed_clearance_point(fld, p)
                    if val is not None and val < best:
                        best = val
            if best < pinch_worst[0]:
                pinch_worst = (best, sname, jn)
            if best < pinch_per_joint[jn][0]:
                pinch_per_joint[jn] = (best, sname)
    print("pinch worst=%.3f at %s %s"
          % (pinch_worst[0], pinch_worst[1], pinch_worst[2]))

    takeup = {}
    for j in arm.rev:
        jn = j["name"]
        c = design.crossings[jn]
        rng = j["hi"] - j["lo"]
        if jn == "joint1":
            supplied = c["radius"] * rng      # clock-spring coil pays out r*dq
        else:
            # bypass loop: U-turn arc length = pi*chord(q)/2; variation over
            # the envelope = pi/2 * (chord(max|q|) - chord(0)) = pi*r_b
            supplied = math.pi * c["radius"]
        takeup[jn] = dict(
            crossing_radius_mm=round(c["radius"], 3),
            joint_range_rad=round(rng, 6),
            takeup_supplied_mm=round(supplied, 3),
            wp1_upper_bound_mm=TAKEUP_BOUND[jn],
            margin_vs_wp1_bound_mm=round(supplied - TAKEUP_BOUND[jn], 3),
            note=("WP1 bound assumes clamp at R_child about the axis; the "
                  "side-bypass topology is not bounded by it - demand is "
                  "covered by the derived provisioned length"
                  if jn != "joint1" else "clock-spring coil, 1:1 unwind"),
        )

    checks = {
        "fk_validation_pass": fk_pass,
        "min_clearance_mm": round(clear_worst[0], 4) if clear_worst[1] else None,
        "collision_pass": bool(clear_worst[0] > -TOL_PEN),
        "min_bend_radius_mm": round(bend_min[0], 3) if bend_min[1] else None,
        "bend_pass_vs_class": bool(bend_min[0] >= BEND_CLASS),
        "pinch_worst_mm": round(pinch_worst[0], 4),
        "pinch_pass": bool(pinch_worst[0] > 0.0),
        "coil_clamp_azimuth_residual_max_rad": round(coil_wrap_err, 6),
        "empty_comparison_sets": empty_sets,
    }
    hard_fail = (not checks["collision_pass"]) or (not checks["bend_pass_vs_class"]) \
        or (not checks["pinch_pass"]) or empty_sets > 0
    verdict = "FAIL" if hard_fail else "PASS_WITH_PROVISIONAL_SCOPE"

    holds = [
        "HOLD_VENDOR_MINIMUM_BEND_RADIUS_ABSENT (gate uses class value 25.0 mm)",
        "HOLD_VENDOR_CABLE_OUTER_DIAMETER_ABSENT (tube radius 5.0 mm candidate)",
        "HOLD_CONNECTOR_PART_NUMBER_AND_SHELL_ABSENT",
        "HOLD_STRAIN_RELIEF_HARDWARE_NOT_SELECTED (P-clamp scheme is candidate)",
        "HOLD_ARM_CONNECTOR_FACE_STATION_UNRECONCILED (WP1 carry-over)",
        "HOLD_CLAMP_POSES_Y_AND_Z_UNDEFINED (WP1; this gate derives candidates)",
        "HOLD_CLEARANCE_VS_VENDOR_COLLISION_MESHES_NOT_CARRIER_CAD "
        "(carrier FCStd files contain no solids; 02_carriers missing)",
        "HOLD_SELF_COLLISION_OF_COIL_NOT_EVALUATED",
        "HOLD_CAMERA_AND_HDRM_CABLE_RUNS_NOT_IN_SCOPE (H-RUN-01 only)",
    ]
    scope_notes = [
        "geometry = accepted URDF collision STLs (decimate tol 0.1 mm), the "
        "same meshes behind the WP1 R_child / take-up upper bounds",
        "mount = F3R2_ARM_INITIAL_POSE.yaml transform_mm_rows (x=208.0 mm, "
        "25 deg clock about +X_S); supersedes the simplified task-text mount "
        "(185.25 + Ry90) - discrepancy documented",
        "gripper fingers locked at q=0 (URDF capture-ready); rail swept "
        "volumes cover the full finger stroke as exclusion solids",
        "centerline = analytic primitives (line/arc/helix) with R=30 mm "
        "fillets; clamp/waypoint positions are derived candidates, not "
        "released hardware stations",
        "distance engine: exact point-triangle below 25 mm horizon, "
        "conservative AABB lower bounds beyond it (min-tracking unaffected)",
        rail_note,
    ]

    redesign_history = [
        {"iteration": 0,
         "id": "V1_baseline",
         "source": "HARNESS_B601_FULL_FK_SWEEP_V1.json (accepted FAIL)",
         "design": "fixed-radius helix wraps through the joint wedge sector "
                   "+ straight inter-anchor legs with fillets",
         "worst": {"clearance_mm": -11.86, "min_bend_mm": 2.26,
                   "pinch_mm": -11.83},
         "lesson": "helix arc crosses the closing wedge at fold hard stops; "
                   "straight legs cut link bodies"},
        {"iteration": 1,
         "id": "V2_iter1_axial_side_bypass",
         "design": "axial side-bypass service loops beyond the joint axial "
                   "extent + Catmull-Rom body-hugging spans; coil wrap "
                   "asserted 1:1 with clamp azimuth residual diagnostic",
         "worst": "design-stage debug: U-turn cusps R=1.2 (uniform-CR "
                  "curvature concentration), span through-body penetrations",
         "lesson": "CR through sparse controls cusps at U-turn tips; "
                   "fillet tangent-length and deflection-angle formula bugs "
                   "found and fixed"},
        {"iteration": 2,
         "id": "V2_iter2_axial_legs_wrist_wraps",
         "design": "tangent-continuous U-turn semicircles between parallel "
                   "axial legs (+52 mm radial separation => R_turn >= 26 by "
                   "construction); clock-spring wraps at wrist rolls j5/j6; "
                   "housing split into fixed/swept/child terms",
         "worst": "design-stage debug: corridor housing exploded to 150-280 "
                  "mm (whole parent chain + folded child bar swept the leg "
                  "slices); spans tunnelled",
         "lesson": "swept-window housing over the full circle is "
                   "unusable; the child bar sweeps every azimuth"},
        {"iteration": 3,
         "id": "V2_iter3_consistency_and_spans",
         "design": "side-consistency between consecutive crossings; tangent "
                   "hints at span ends; straight-first spans",
         "worst": "design-stage debug: spans zigzagged (push direction "
                  "flips), hint hooks created cusps R~0.3 when misaligned "
                  "with the span direction",
         "lesson": "per-station push directions must be globally "
                   "consistent; hints only when aligned"},
        {"iteration": 4,
         "id": "V2_iter4_all_bodies_extent",
         "design": "bypass station beyond ALL bodies' axial extent on the "
                   "chosen side (parent chain included) - station disjoint "
                   "from every body at every q by construction",
         "worst": "design-stage debug: loop radii collapsed to the 35 mm "
                  "floor at clear stations; remaining failures concentrated "
                  "in spans",
         "lesson": "the leg-slice extent must cover static bodies too; "
                   "phantom 1.8 mm slice overlap had poisoned joint4 r_out "
                   "to 282 mm"},
        {"iteration": 5,
         "id": "V2_iter5_final_candidate",
         "design": "straight-first spans with >= 8 mm exact-clearance hard "
                   "filter inside the crossing azimuth search; curved "
                   "fallback = S/C/E candidate families with exact-repair "
                   "subdivision; final assembly = coil + spans + axial-leg "
                   "bypass U-turns (j2-j4) + wrist wraps (j5/j6)",
         "worst": "design-stage: crossing loops clean (U-turn R>=26, "
                  "legs station-disjoint); residual failures concentrate "
                  "in spans and in the coil region at fold states",
         "lesson": "full run 1: clear -11.995 vs link3 @ SWEEP_joint2_02, "
                   "bend 0.10 at span_link5, pinch -11.80; coil clamp "
                   "azimuth residual 3.12 rad exposed a coil model bug"},
        {"iteration": 6,
         "id": "V2_iter6_coil_wind_fix",
         "design": "joint1 coil re-based: fixed-end azimuth = clamp azimuth "
                   "at q1=0, coil winds up 1:1 with q1 (wrap = 2pi captive "
                   "+ q1); the V1/iter5 decreasing-wrap model could not end "
                   "on the moving clamp (residual pi), inserting a phantom "
                   "~100 mm chord into the centerline at every state",
         "worst": {"clearance_mm": round(clear_worst[0], 4),
                   "min_bend_mm": round(bend_min[0], 3),
                   "pinch_mm": round(pinch_worst[0], 4)},
         "lesson": "final measured result - this run; coil residual now "
                   "0.0 rad, but fold-envelope failures remain systematic"},
    ]

    failure_analysis = {
        "summary": "full-envelope external harness routing is falsified by "
                   "this candidate family on the accepted geometry",
        "root_causes": [
            "j2/j3 fold-flat envelope: the link2/link3 bars (max radius "
            "292.5/277.0 mm about their joint axes) sweep the full azimuth "
            "circle; the joint1 clock-spring coil (r=72.05 mm, plane "
            "x=330 mm) and every near-base routing element are engulfed "
            "(worst: -11.994 mm vs link3 at SWEEP_joint2_09, i.e. the "
            "centerline is 7 mm inside link3's surface at the coil plane)",
            "corner states (all six joints at hard limits) bring "
            "non-adjacent links into contact with span runs designed "
            "against single-joint sweeps (e.g. link2 -11.6 mm at "
            "CORNER_000000, link4 -11.99 mm at SWEEP_joint4_32)",
            "wrist spans between the j5/j6 clock-spring wraps retain "
            "sub-class bends (0.10 mm at CORNER_110000) - residual "
            "Catmull-Rom cusp at the wrap-to-span join at extreme poses",
            "pinch bands at hard stops reach -12 mm: fold closures land "
            "on spans anchored near the joint interfaces",
        ],
        "what_would_be_needed": [
            "routing through hollow joint shafts or slip rings (vendor/"
            "arm hardware change) for j2/j3",
            "OR a reduced harness-rated motion envelope (harness only "
            "rated over the mission poses + bounded joint subsets, with "
            "the full-fold states declared transport/service-only and "
            "harness removed or reeved for them)",
            "OR an articulated dress-pack with guided carriers (new "
            "hardware, its own gate)",
        ],
        "positive_results": [
            "FK pipeline validated to 0.0000 mm against all five witness "
            "STEP marker sets + base face x=208.000 mm",
            "joint1 coil model now exactly 1:1 (clamp azimuth residual "
            "0.0 rad over the sweep); take-up supply 403.5 mm vs "
            "requirement 347.493596 mm",
            "axial side-bypass loops achieve pinch-free stations by "
            "construction and U-turn radius >= 26 mm by construction",
            "wrist clock-spring wraps (j5 r=48.35, j6 r=42.48 mm) are "
            "locally clean at their own joints",
        ],
    }



    report = {
        "schema": "HARNESS_B601_FULL_FK_SWEEP_V2",
        "generated_local": local_now(),
        "authority": "R2-HRN-05 / ODR-29 (redesign iteration of R2-HRN-04)",
        "quick_mode": QUICK,
        "runtime_s": round(time.time() - t_start, 1),
        "sampling_mm": SAMPLE_DS,
        "tube_radius_mm": TUBE_R,
        "bend_class_limit_mm": BEND_CLASS,
        "penetration_tolerance_mm": TOL_PEN,
        "inputs_sha256": hashes,
        "fk_validation": fk_report,
        "design": {
            "topology": "bus clamp P0(HN-01 passage mouth)/P1(HC-1 candidate)/"
                        "P2(HC-2 candidate) -> joint1 clock-spring coil "
                        "(r=%.2f mm, captive 2pi wrap, unwinds 1:1 with q1, "
                        "plane x=%.1f) -> HC-3 on link1 -> body-hugging span "
                        "paths on each link (housing-radius profile + %.0f mm "
                        "standoff about the link spine) -> helix crossings "
                        "j2..j6 (radius/azimuth/station auto-derived, azimuth "
                        "for routing-side continuity) -> G0 termination on "
                        "the gripper palm back-top (rail slot envelope "
                        "avoided)" % (COIL_R, COIL_PLANE_X, STANDOFF),
            "crossings": {jn: dict(radius_mm=round(c["radius"], 3),
                                   azimuth_deg=round(math.degrees(c["alpha"]), 2),
                                   station_mm=c["station"],
                                   preferred_azimuth_deg=round(
                                       math.degrees(c["preferred_azimuth"]), 2),
                                   topology=c["topology"])
                          for jn, c in design.crossings.items()},
            "hc3_clamp_link1_local_mm": [round(x, 3) for x in design.clamp_l1],
            "spine_link1_local_mm": [[round(v, 3) for v in p]
                                     for p in design.spines["link1"]],
            "G0_gripper_link_local_mm": [round(x, 3) for x in design.G0],
            "P0_S_mm": [round(x, 3) for x in design.P0],
            "P1_S_mm": [round(x, 3) for x in design.P1],
            "P2_S_mm": [round(x, 3) for x in design.P2],
            "fillet_radius_nominal_mm": FILLET_R,
            "standoff_mm": STANDOFF,
        },
        "sweep": {
            "states_total": len(states),
            "per_joint_samples": N_JOINT_SAMPLES,
            "named_poses": sorted("NAMED_" + p for p in named),
            "corner_states": 64 if DO_CORNERS else 0,
            "lhs_states": N_LHS,
            "lhs_seed": 20260822,
            "exact_distance_queries": n_exact,
            "lower_bound_queries": n_lb,
            "pinch_states": len(pinch_states),
        },
        "results": {
            "length_required_max_mm": round(length_max[0], 3),
            "length_argmax_state": length_max[1],
            "length_required_min_mm": round(length_min[0], 3),
            "length_argmin_state": length_min[1],
            "length_provisioned_derived_mm": round(provisioned, 3),
            "min_bend_radius_mm": round(bend_min[0], 3),
            "min_bend_argmin": bend_min[1],
            "min_bend_discrete_menger_mm": (round(bend_discrete_min[0], 3)
                                            if math.isfinite(bend_discrete_min[0])
                                            else None),
            "min_bend_discrete_argmin": bend_discrete_min[1],
            "clearance_worst_mm": round(clear_worst[0], 4),
            "clearance_worst_state": clear_worst[1],
            "clearance_worst_against": clear_worst[2],
            "clearance_worst_point_S_mm": clear_worst[3],
            "clearance_per_field_min": {
                k: dict(min_mm=round(v[0], 4), state=v[1])
                for k, v in sorted(per_field_min.items())},
            "pinch_worst_mm": round(pinch_worst[0], 4),
            "pinch_worst_state": pinch_worst[1],
            "pinch_worst_joint": pinch_worst[2],
            "pinch_per_joint_min": {
                k: dict(min_mm=round(v[0], 4), state=v[1])
                for k, v in sorted(pinch_per_joint.items())},
            "takeup_per_joint": takeup,
        },
        "checks": checks,
        "verdict": {
            "B601_HARNESS_FUNCTIONAL_GATE": verdict,
            "verdict_rule": "FAIL if any penetration beyond tolerance, any "
                            "bend below the class limit, any pinch <= 0, or "
                            "any empty comparison set; else "
                            "PASS_WITH_PROVISIONAL_SCOPE (vendor HOLDs "
                            "outstanding; full PASS unreachable while cable "
                            "vendor data is absent)",
        },
        "holds": holds,
        "scope_notes": scope_notes,
        "redesign_history": redesign_history,
        "failure_analysis": failure_analysis,
    }
    OUT_JSON.write_text(json.dumps(report, indent=1), encoding="utf-8")
    OUT_YAML.write_text(yaml_dump(report), encoding="utf-8")
    print("VERDICT:", verdict)
    print("Lmax=%.1f (%s) prov=%.1f | Rmin=%.2f (%s) | clear=%.3f vs %s @ %s"
          % (length_max[0], length_max[1], provisioned, bend_min[0], bend_min[1],
             clear_worst[0], clear_worst[2], clear_worst[1]))
    print("runtime %.0fs" % (time.time() - t_start))


def yaml_dump(report):
    import yaml
    return yaml.safe_dump(json.loads(json.dumps(report)), sort_keys=False,
                          allow_unicode=True)


if __name__ == "__main__" or (len(sys.argv) > 1 and Path(sys.argv[1]).stem == __name__):
    main()
