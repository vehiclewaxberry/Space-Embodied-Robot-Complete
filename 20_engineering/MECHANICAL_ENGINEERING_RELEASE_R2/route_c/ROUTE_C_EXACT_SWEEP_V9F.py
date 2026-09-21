# ROUTE_C_EXACT_SWEEP_V9F.py
# Stage RC-4 V9F candidate verification (Route-C exact verification
# and digital-thread rebind).  Pure Python + numpy; no FreeCAD dependency at run
# time (the mesh pack is pre-built and hash-pinned by ROUTE_C_SWEEP_MESH_PREP_V9F.py).
#
# Run:  python ROUTE_C_EXACT_SWEEP_V9F.py           (from this directory)
# Replay: two runs are byte-identical (no wall clock, no RNG, fixed iteration
# order, repr() float serialization, LF line endings, sort_keys JSON).
#
# See ROUTE_C_EXACT_SWEEP_V9F.json "kinematic_attachment_model" and
# "tracking_tube_candidate" blocks for the declared model and tube parameters.
# Predicate set per ODR-54: clearance / bend / pinch / take-up(length) /
# axial extension / carrier travel / resistance torque / thermal-tolerance.

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

VARIANT = "V9F"
FAST_MODE = os.environ.get("RC_FAST", "0") == "1"
FAST_OUTPUT_TAG = os.environ.get("RC_FAST_OUTPUT_TAG", "")
INPUT_VARIANT = "V9F"

if FAST_OUTPUT_TAG and re.fullmatch(r"[A-Z0-9_]+", FAST_OUTPUT_TAG) is None:
    print("ABORT: RC_FAST_OUTPUT_TAG must match [A-Z0-9_]+", flush=True)
    raise SystemExit(2)
if FAST_OUTPUT_TAG and not FAST_MODE:
    print("ABORT: RC_FAST_OUTPUT_TAG is permitted only with RC_FAST=1", flush=True)
    raise SystemExit(2)

P_URDF = os.path.join(REPO, "cad", "spacecraft_layout", "arm_b601_v1", "arm_b601_v1.urdf")
P_MOUNT = os.path.join(REPO, "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807",
                       "04_configurations", "F3R2_ARM_INITIAL_POSE.yaml")
P_CENTER = os.path.join(HERE, "B601_ROUTE_C_HARNESS_CENTERLINE_%s.json" % INPUT_VARIANT)
P_CLAMPS = os.path.join(HERE, "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_%s.csv" % INPUT_VARIANT)
P_REG = os.path.join(HERE, "ROUTE_C_PHYSICAL_CAPABILITY_REGISTRY_V2.yaml")
P_CONTRACT = os.path.join(REPO, "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1",
                          "ecr_b601_harness_rated_envelope", "04_mission",
                          "B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml")
P_PACK = os.path.join(HERE, "ROUTE_C_SWEEP_MESH_PACK_%s" % INPUT_VARIANT)
P_MANIFEST = os.path.join(P_PACK, "MANIFEST.json")
P_BUILDER = os.path.join(HERE, "B601_ROUTE_C_BUILD_V9F.py")
P_RECEIPT = os.path.join(HERE, "B601_ROUTE_C_BUILD_RECEIPT_V9F.json")

URDF_SHA256_PIN = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"

_OUTPUT_TAG_SUFFIX = ("_" + FAST_OUTPUT_TAG) if FAST_OUTPUT_TAG else ""
OUT_SWEEP = os.path.join(
    HERE, "ROUTE_C_EXACT_SWEEP_%s%s.json" % (VARIANT, _OUTPUT_TAG_SUFFIX))
OUT_LEDGER = os.path.join(
    HERE, "ROUTE_C_ROBUST_MARGIN_LEDGER_%s%s.csv" % (VARIANT, _OUTPUT_TAG_SUFFIX))
OUT_GATE = os.path.join(
    HERE, "ROUTE_C_MISSION_COVERAGE_GATE_%s%s.json" % (VARIANT, _OUTPUT_TAG_SUFFIX))

# ------------------------------- constants ---------------------------------
BUNDLE_R = 4.5
BEND_LIMIT = 50.0
CARRIER_HALF = 55.0
J3_SADDLE_R = 63.0 if VARIANT == "V1" else 65.0
J4_SEGMENT_ID = "SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER"
J4_CARRIER_GAIN_MM_PER_RAD = 27.5
J4_Q_MID_RAD = -0.15
J4_CARRIER_X_MID_MM = -205.0
J4_CARRIER_X_Q0_MM = (J4_CARRIER_X_MID_MM
                        - J4_CARRIER_GAIN_MM_PER_RAD*(0.0-J4_Q_MID_RAD))
J4_STOP_MIN_MM, J4_STOP_MAX_MM = -255.0, -155.0
J4_Q_MIN_RAD, J4_Q_MAX_RAD = -1.87, 1.57
J4_TROMBONE_R_MM = math.sqrt(23.0**2 + 50.0**2)
J4_ANNULUS_R_MM = 55.0
J4_ANNULUS_FIXED_ANGLE_RAD = math.pi/2.0
J4_ANNULUS_GUIDE_COVERAGE_RAD = math.radians(185.0)
J4_ANNULUS_SEED_RAD = math.radians(20.0)
J4_TROMBONE_PHYSICAL_TRAVEL_MM = 100.0
J4_TELESCOPE_STAGE_LENGTH_MM = 57.0
J4_TELESCOPE_STAGE_COUNT = 4
J4_TELESCOPE_MIN_OVERLAP_MM = 25.0
J4_DYNAMIC_LENGTH_TOL_MM = 1.0e-6
J4_FOLLOWER_CLOSURE_TOL_MM = 1.0e-6
J4_INTERFACE_ARCLENGTH_WINDOW_MM = 65.0
V9_INPUT_MANIFEST = os.path.join(HERE, "ROUTE_C_V9_INPUT_MANIFEST.json")
V9_INPUT_MANIFEST_SHA256 = "24B9E2BFB21930E44945C0BA979351CFB9EB23358755D1018FCC4602CDED7E7C"
ALPHA_AL = 23.6e-6
DELTA_T_K = 100.0
MU_MAX = 0.20
EI_LOWER, EI_UPPER = 1.7e-4, 2.1e-2

EXPECTED_ARCHITECTURE = ("CHAINLESS_TELESCOPING_TROMBONE_CASSETTE__"
                         "R55_EXTERNAL_ANNULAR_FOLLOWER__LINK4_MOVING_TROLLEY")

DQ_TRACK = math.radians(0.20)
DQ_ENCCAL = math.radians(0.05)
DQ_TOTAL = DQ_TRACK + DQ_ENCCAL
D_INSTALL, D_GEOM, D_THERM, D_MESH = 0.5, 1.0, 1.0, 0.1
D_STATIC = D_INSTALL + D_GEOM + D_THERM + D_MESH

SAMPLE_DS = 1.5
MAX_DQ_STEP = math.radians(0.5 if FAST_MODE else 0.25)
EXACT_HORIZON = 30.0
RC_SAMPLE_ALLOW = 0.5

BUS_MIN = np.array([-170.25, -113.15, -113.15])
BUS_MAX = np.array([170.25, 113.15, 113.15])
CORRIDOR_MIN = np.array([64.0, -82.0, -30.0])
CORRIDOR_MAX = np.array([171.0, -58.0, 30.0])

HOSTS = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]
VENDOR_LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5",
                "link6", "gripper_link", "gripper_left", "gripper_right"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


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
    R = np.array([[x * x * C + c, x * y * C - z * s, x * z * C + y * s],
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


def xform(M, p):
    return M[:3, :3] @ np.asarray(p, float) + M[:3, 3]


def xform_batch(M, P):
    return np.asarray(P, float) @ M[:3, :3].T + M[:3, 3]


def fr(x):
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return str(x)
    return x


def jdump(obj):
    return json.dumps(obj, indent=2, sort_keys=True, default=fr)


def _q_round12_key(q):
    """Canonical cache key; identical to the frozen evaluator's q rounding."""
    return tuple(round(float(x), 12) for x in q)


def _aabb_box_lower_bound(amin, amax, bmin, bmax):
    """Conservative Euclidean lower bound between two axis-aligned boxes."""
    gap = np.maximum(np.maximum(np.asarray(bmin)-np.asarray(amax),
                                np.asarray(amin)-np.asarray(bmax)), 0.0)
    return float(np.sqrt((gap*gap).sum()))


def _conservative_aabb_candidates(P, pmin, pmax, bmin, bmax, horizon):
    """Points that may be within *horizon* of a field's global AABB.

    A false entry proves that the point is farther than the exact-distance
    horizon from every triangle.  The group-box test is only an early return;
    the per-point bound remains the authority for candidate selection.
    """
    P = np.asarray(P, float)
    if len(P) == 0 or _aabb_box_lower_bound(pmin, pmax, bmin, bmax) > horizon:
        return np.zeros(len(P), dtype=bool)
    delta = np.maximum(np.maximum(np.asarray(bmin)-P,
                                  P-np.asarray(bmax)), 0.0)
    return np.sqrt((delta*delta).sum(axis=1)) <= horizon


def _exact_unique_rows_with_multiplicity(P):
    """First-occurrence, byte-exact row deduplication with integer weights.

    Used only for the RC cross-check's repeated triangle-v0 sample locations;
    multiplicity restores the frozen logical comparison-count semantics.
    """
    P = np.asarray(P, float)
    if P.ndim != 2 or P.shape[1] != 3 or not np.isfinite(P).all():
        raise ValueError("RC v0 samples must be a finite (N,3) array")
    first = {}
    unique_idx = []
    weights = []
    for i, row in enumerate(P):
        key = np.ascontiguousarray(row).tobytes()
        ui = first.get(key)
        if ui is None:
            first[key] = len(unique_idx)
            unique_idx.append(i)
            weights.append(1)
        else:
            weights[ui] += 1
    U = P[np.asarray(unique_idx, dtype=np.int64)]
    W = np.asarray(weights, dtype=np.int64)
    if int(W.sum()) != len(P):
        raise RuntimeError("RC v0 multiplicity conservation failure")
    return U, W


class ArmModel:
    def __init__(self, urdf_path, mount_rows):
        root = ET.parse(urdf_path).getroot()
        joints = []
        for j in root.iter("joint"):
            o = j.find("origin")
            xyz = [float(v) for v in o.get("xyz").split()] if o is not None and o.get("xyz") else [0, 0, 0]
            rpy = [float(v) for v in o.get("rpy").split()] if o is not None and o.get("rpy") else [0, 0, 0]
            ax = j.find("axis")
            axis = [float(v) for v in ax.get("xyz").split()] if ax is not None else [1, 0, 0]
            lim = j.find("limit")
            lo = float(lim.get("lower")) if lim is not None and lim.get("lower") is not None else 0.0
            hi = float(lim.get("upper")) if lim is not None and lim.get("upper") is not None else 0.0
            eff = float(lim.get("effort")) if lim is not None and lim.get("effort") is not None else None
            joints.append(dict(name=j.get("name"), type=j.get("type"), xyz=xyz, rpy=rpy,
                               axis=axis, lo=lo, hi=hi, effort=eff,
                               parent=j.find("parent").get("link"),
                               child=j.find("child").get("link")))
        self.joints = joints
        self.rev = [j for j in joints if j["type"] == "revolute"]
        self.mount = np.array(mount_rows, float)
        self.inv_mount = np.linalg.inv(self.mount)

    def origin_T(self, j):
        return tr(*[v * 1000.0 for v in j["xyz"]]) @ rot_rpy(*j["rpy"])

    def fk(self, q6, gripper=(0.0, 0.0)):
        qd = {j["name"]: q6[i] for i, j in enumerate(self.rev)}
        qd["gripper_joint1"], qd["gripper_joint2"] = gripper
        T = {"base_link": np.eye(4)}
        for j in self.joints:
            Tj = T[j["parent"]] @ self.origin_T(j)
            if j["type"] == "revolute":
                Tj = Tj @ rot_axis(j["axis"], qd.get(j["name"], 0.0))
            elif j["type"] == "prismatic":
                Tj = Tj @ tr(*[a * qd.get(j["name"], 0.0) * 1000.0 for a in j["axis"]])
            T[j["child"]] = Tj
        return T

    def joint_axis_world(self, j, T):
        TF = T[j["parent"]] @ self.origin_T(j)
        o = TF[:3, 3].copy()
        a = TF[:3, :3] @ np.asarray(j["axis"], float)
        return o, a / np.linalg.norm(a)


class TriField:
    CELL = 50.0

    def __init__(self, name, tris, horizon=EXACT_HORIZON):
        self.name = name
        V = np.asarray(tris, float)
        self.v0 = V[:, 0, :].copy()
        self.e1 = (V[:, 1, :] - V[:, 0, :]).copy()
        self.e2 = (V[:, 2, :] - V[:, 0, :]).copy()
        self.n = len(V)
        self.D = horizon
        lo = V.min(axis=1)
        hi = V.max(axis=1)
        self.bmin = lo.min(axis=0)
        self.bmax = hi.max(axis=0)
        self.aabb_corners = np.array(
            [[x, y, z]
             for x in (self.bmin[0], self.bmax[0])
             for y in (self.bmin[1], self.bmax[1])
             for z in (self.bmin[2], self.bmax[2])], dtype=float)
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
        # 2D-projection acceleration for inside tests on far (NaN) points:
        # precompute projected triangle coordinates on the plane normal to the
        # fixed ray direction and a 2D grid for candidate lookup.
        d_ray = np.array([1.0, 0.0173, 0.0091])
        self._ray_d = d_ray / np.linalg.norm(d_ray)
        ref = np.array([0.0, 0.0, 1.0]) if abs(self._ray_d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        e1r = np.cross(self._ray_d, ref)
        e1r = e1r / np.linalg.norm(e1r)
        e2r = np.cross(self._ray_d, e1r)
        self._ray_e1 = e1r
        self._ray_e2 = e2r
        v1 = self.v0 + self.e1
        v2 = self.v0 + self.e2
        self._t2d = np.stack([
            np.stack([self.v0 @ e1r, self.v0 @ e2r], axis=1),
            np.stack([v1 @ e1r, v1 @ e2r], axis=1),
            np.stack([v2 @ e1r, v2 @ e2r], axis=1)], axis=1)
        self._g2c = 10.0
        g2 = defaultdict(list)
        lo2 = self._t2d.reshape(-1, 2).min(axis=0)
        for ti in range(self.n):
            tlo = np.floor(self._t2d[ti].min(axis=0) / self._g2c).astype(np.int32) - 1
            thi = np.floor(self._t2d[ti].max(axis=0) / self._g2c).astype(np.int32) + 1
            for ix in range(tlo[0], thi[0] + 1):
                for iy in range(tlo[1], thi[1] + 1):
                    g2[(ix, iy)].append(ti)
        self._grid2d = {k: np.array(v, dtype=np.int32) for k, v in g2.items()}

    def aabb_lb(self, P):
        q = np.maximum(np.maximum(self.bmin - P, P - self.bmax), 0.0)
        return np.sqrt((q * q).sum(axis=1))

    def _tri_dist2_batch(self, P, idx):
        """(M points) x (K tris) -> (M,) min squared distance. Chunked over tris."""
        M = len(P)
        out = np.full(M, np.inf)
        A0 = self.v0[idx]
        E1 = self.e1[idx]
        E2 = self.e2[idx]
        for p_i in range(M):
            p = P[p_i]
            A = A0
            B = A0 + E1
            C = A0 + E2
            AP = p - A
            d1 = (E1 * AP).sum(1)
            d2 = (E2 * AP).sum(1)
            BP = p - B
            d3 = (E1 * BP).sum(1)
            d4 = (E2 * BP).sum(1)
            CP = p - C
            d5 = (E1 * CP).sum(1)
            d6 = (E2 * CP).sum(1)
            best = np.full(len(idx), np.inf)

            def d2_seg(P0, P1):
                d = P1 - P0
                L2 = np.maximum((d * d).sum(1), 1e-30)
                t = ((p - P0) * d).sum(1) / L2
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
                nn = np.cross(E1[m], E2[m])
                nl = np.maximum(np.sqrt((nn * nn).sum(1)), 1e-30)
                dist = (nn * (p - A[m])).sum(1) / nl
                best[m] = dist * dist
            out[p_i] = best.min() if len(best) else math.inf
        return out

    def min_dist_batch(self, P):
        """P: (M,3) in field frame -> (d(M,), exact(M,)) arrays."""
        P = np.asarray(P, float)
        d = np.full(len(P), self.D)
        exact = np.zeros(len(P), dtype=bool)
        if len(P) == 0:
            return d, exact
        keys = np.floor(P / self.CELL).astype(np.int32)
        # group point indices by cell key
        order = np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
        ks = keys[order]
        boundaries = np.flatnonzero(np.any(ks[1:] != ks[:-1], axis=1)) + 1
        groups = np.split(order, boundaries)
        kg = np.split(ks, boundaries)
        for idxs, karr in zip(groups, kg):
            key = tuple(karr[0])
            tris_idx = self.grid.get(key)
            if tris_idx is None or len(tris_idx) == 0:
                continue
            dd = np.sqrt(self._tri_dist2_batch(P[idxs], tris_idx))
            m = dd < self.D
            d[idxs[m]] = dd[m]
            exact[idxs[m]] = True
        return d, exact

    def inside_batch(self, P):
        P = np.asarray(P, float)
        votes = np.zeros(len(P), dtype=np.int32)
        for d0 in ((1.0, 0.0, 0.0), (1.0, 0.0173, 0.0091), (1.0, -0.0113, 0.0211)):
            d = np.asarray(d0, float)
            d = d / np.linalg.norm(d)
            h = np.cross(np.broadcast_to(d, self.e2.shape), self.e2)
            det = (self.e1 * h).sum(1)
            mt = np.abs(det) > 1e-12
            if not mt.any():
                continue
            E1 = self.e1[mt]
            E2 = self.e2[mt]
            H = h[mt]
            V0 = self.v0[mt]
            inv = 1.0 / det[mt]
            hits = np.zeros(len(P), dtype=np.int32)
            for p_i in range(len(P)):
                sv = P[p_i] - V0
                u = (sv * H).sum(1) * inv
                qv = np.cross(sv, E1)
                v = (d * qv).sum(1) * inv
                t = (E2 * qv).sum(1) * inv
                hit = (u >= 1e-12) & (v >= 1e-12) & (u + v <= 1 - 1e-12) & (t > 1e-9)
                hits[p_i] = int(hit.sum())
            votes += (hits % 2 == 1).astype(np.int32) * 2 - 1
        return votes > 0

    def inside_batch_fast(self, P):
        """inside test for far points via fixed-direction ray parity with 2D
        projection candidate prefilter. Single ray (deterministic); used only
        for points beyond the exactness horizon, where the result only flags
        deep penetration (reported as a lower-bound magnitude)."""
        P = np.asarray(P, float)
        out = np.zeros(len(P), dtype=bool)
        if len(P) == 0 or self.n == 0:
            return out
        d = self._ray_d
        keys = np.floor(np.stack([P @ self._ray_e1, P @ self._ray_e2], axis=1)
                        / self._g2c).astype(np.int32)
        order = np.lexsort((keys[:, 1], keys[:, 0]))
        ks = keys[order]
        boundaries = np.flatnonzero(np.any(ks[1:] != ks[:-1], axis=1)) + 1
        groups = np.split(order, boundaries)
        kg = np.split(ks, boundaries)
        for idxs, karr in zip(groups, kg):
            key = tuple(karr[0])
            cand = self._grid2d.get(key)
            if cand is None or len(cand) == 0:
                continue
            E1 = self.e1[cand]
            E2 = self.e2[cand]
            V0 = self.v0[cand]
            h = np.cross(np.broadcast_to(d, E2.shape), E2)
            det = (E1 * h).sum(1)
            mt = np.abs(det) > 1e-12
            if not mt.any():
                continue
            E1 = E1[mt]
            E2 = E2[mt]
            H = h[mt]
            V0 = V0[mt]
            inv = 1.0 / det[mt]
            for p_i in idxs:
                sv = P[p_i] - V0
                u = (sv * H).sum(1) * inv
                qv = np.cross(sv, E1)
                v = (d * qv).sum(1) * inv
                t = (E2 * qv).sum(1) * inv
                hit = (u >= 1e-12) & (v >= 1e-12) & (u + v <= 1 - 1e-12) & (t > 1e-9)
                out[p_i] = (int(hit.sum()) % 2) == 1
        return out

    def signed_clearance_batch(self, P, tube_r):
        """(M,) surface clearance: dist - tube_r, negative if inside.
        Points beyond the horizon get None (not evaluated), except deep
        penetrations which are flagged as -(D + tube_r) lower bound."""
        P = np.asarray(P, float)
        d, exact = self.min_dist_batch(P)
        out = np.full(len(P), np.nan)
        if exact.any():
            out[exact] = d[exact]
            cand = exact & (d < tube_r + 2.0)
            if cand.any():
                inside = self.inside_batch(P[cand])
                idxs = np.flatnonzero(cand)
                neg = idxs[inside]
                out[neg] = -out[neg]
            out[exact] -= tube_r
        nan_m = ~exact
        if nan_m.any():
            idxs = np.flatnonzero(nan_m)
            # only points inside the field's global AABB can be inside the mesh
            inside_aabb = ((P[idxs] >= self.bmin) & (P[idxs] <= self.bmax)).all(axis=1)
            if inside_aabb.any():
                sub = idxs[inside_aabb]
                # The fixed-ray parity test is only a prefilter.  Open/defective
                # tessellations can make a far point inside the global AABB look
                # enclosed under one ray, yielding the exact artificial lower
                # bound -(D+tube_r).  Confirm every fast positive with the
                # independent three-ray majority test before reporting a deep
                # penetration.  A rejected prefilter remains the already-proven
                # beyond-horizon case (distance >30 mm, larger than every folded
                # tube+tracking derate), represented as NaN for this local field.
                inside_fast = self.inside_batch_fast(P[sub])
                if inside_fast.any():
                    cand = sub[inside_fast]
                    inside_confirmed = self.inside_batch(P[cand])
                    if inside_confirmed.any():
                        out[cand[inside_confirmed]] = -(self.D + tube_r)
        return out


class BusField:
    """bus proxy = box minus declared feedthrough corridor (true S frame).

    Exact closed boundary mesh (box faces with the corridor opening on +x,
    corridor side walls x in [64, 170.25], corridor back wall at x=64), so
    distances near the corridor mouth are measured to the true solid, not to
    the voided face.  Corridor (true S, verified against P05 permuted station
    semantics): x in [64,171], y in [-82,-58], z in [-30,30]."""
    D = EXACT_HORIZON
    name = "BUS_PROXY_WITH_FEEDTHROUGH_CORRIDOR"

    def __init__(self):
        hx, hy, hz = 170.25, 113.15, 113.15
        x0, x1 = 64.0, 170.25          # corridor prism extent inside the box
        y0, y1 = -82.0, -58.0
        z0, z1 = -30.0, 30.0
        rects = []

        def rect(a, b, c, d):
            rects.append((np.array(a, float), np.array(b, float),
                          np.array(c, float), np.array(d, float)))

        # +x face (x=hx) with corridor hole: 4 bands
        rect((hx, -hy, -hz), (hx, y0, -hz), (hx, y0, hz), (hx, -hy, hz))
        rect((hx, y1, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, y1, hz))
        rect((hx, y0, -hz), (hx, y1, -hz), (hx, y1, z0), (hx, y0, z0))
        rect((hx, y0, z1), (hx, y1, z1), (hx, y1, hz), (hx, y0, hz))
        # -x face, +-y faces, +-z faces (full)
        rect((-hx, -hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (-hx, -hy, hz))
        rect((-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz))
        rect((-hx, hy, -hz), (hx, hy, -hz), (hx, hy, hz), (-hx, hy, hz))
        rect((-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz))
        rect((-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz))
        # corridor side walls (x in [x0, x1])
        rect((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))
        rect((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1))
        rect((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))
        rect((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))
        # corridor back wall at x0
        rect((x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1))
        tris = []
        for a, b, c, d in rects:
            tris.append([a, b, c])
            tris.append([a, c, d])
        self._field = TriField(self.name, np.array(tris, float))

    def aabb_lb(self, P):
        q = np.maximum(np.maximum(BUS_MIN - P, P - BUS_MAX), 0.0)
        return np.sqrt((q * q).sum(axis=1))

    def signed_clearance_batch(self, P, tube_r):
        return self._field.signed_clearance_batch(P, tube_r)


# ------------------------- centerline construction --------------------------
def seg_line_pts(p0, p1, ds=SAMPLE_DS):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    n = max(1, int(L / ds))
    return p0 + (p1 - p0) * np.linspace(0, 1, n + 1)[:, None], L


def seg_arc_pts(center, e1, e2, r, phi0, phi1, ds=SAMPLE_DS):
    center = np.asarray(center, float)
    L = abs(phi1 - phi0) * r
    n = max(2, int(L / ds))
    phis = np.linspace(phi0, phi1, n + 1)
    pts = center + r * (np.cos(phis)[:, None] * e1[None, :]
                        + np.sin(phis)[:, None] * e2[None, :])
    return pts, L


def seg_helix_pts(origin, a, e1, e2, r, phi0, phi1, z0, z1, ds=SAMPLE_DS):
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


def fillet_pts(corner, d_in, d_out, R_des, avail_in, avail_out, ds=SAMPLE_DS):
    corner = np.asarray(corner, float)
    u1 = np.asarray(d_in, float) / np.linalg.norm(d_in)
    u2 = np.asarray(d_out, float) / np.linalg.norm(d_out)
    turn = math.acos(float(np.clip(u1 @ u2, -1, 1)))
    if turn < math.radians(1.0):
        return None, 0.0, math.inf
    t = R_des * math.tan(turn / 2.0)
    R = R_des
    lim = 0.98 * min(avail_in, avail_out)   # same clamp as B601_ROUTE_C_BUILD_V1
    if t > lim:
        t = lim
        R = t / math.tan(turn / 2.0)
    T1 = corner - t * u1
    T2 = corner + t * u2
    m1 = u2 - (u1 @ u2) * u1
    nm = np.linalg.norm(m1)
    if nm < 1e-12:
        return None, 0.0, math.inf
    m1 = m1 / nm
    O = T1 + R * m1
    _, e1, e2 = orthobasis(np.cross(u1, m1))
    a1 = math.atan2(float((T1 - O) @ e2), float((T1 - O) @ e1))
    a2 = math.atan2(float((T2 - O) @ e2), float((T2 - O) @ e1))
    d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    pts, L = seg_arc_pts(O, e1, e2, R, a1, a1 + d, ds)
    return pts, L, R


def polyline_pts(points, corner_radii, ds=SAMPLE_DS):
    P = [np.asarray(p, float) for p in points]
    n = len(P)
    out = [P[0][None, :]]
    total = 0.0
    min_r = math.inf
    cursor = P[0]
    i = 1
    while i < n:
        if i < n - 1:
            R = corner_radii[i - 1] if i - 1 < len(corner_radii) else 50.0
            if R and R > 0:
                d_in = P[i] - cursor
                d_out = P[i + 1] - P[i]
                li = float(np.linalg.norm(d_in))
                lo = float(np.linalg.norm(d_out))
                fp, fl, fr_ = fillet_pts(P[i], d_in, d_out, R, li, lo, ds)
                if fp is not None:
                    sp, sl = seg_line_pts(cursor, fp[0], ds)
                    out.append(sp)
                    total += sl
                    out.append(fp[1:])
                    total += fl
                    min_r = min(min_r, fr_)
                    cursor = fp[-1]
                    i += 1
                    continue
        sp, sl = seg_line_pts(cursor, P[i], ds)
        out.append(sp[1:] if len(sp) > 1 else sp)
        total += sl
        cursor = P[i]
        i += 1
    return np.vstack(out), total, min_r


def build_section(sec, ds=SAMPLE_DS):
    kind = sec["type"]
    if kind == "polyline":
        return polyline_pts(sec["points"], sec.get("corner_fillet_radii_mm", []), ds)
    if kind == "arc":
        r = float(sec["radius_mm"])
        e1 = np.asarray(sec["basis_e1"], float)
        e2 = np.asarray(sec["basis_e2"], float)
        pts, L = seg_arc_pts(sec["center"], e1, e2, r,
                             math.radians(sec["start_angle_deg"]),
                             math.radians(sec["start_angle_deg"] + sec["sweep_deg"]), ds)
        return pts, L, r
    if kind == "helix":
        a = np.asarray(sec["axis"], float)
        e1 = np.asarray(sec["basis_e1"], float)
        e2 = np.asarray(sec["basis_e2"], float)
        r = float(sec["radius_mm"])
        phi0 = math.radians(sec["start_angle_deg"])
        sweep = math.radians(sec["sweep_deg"])
        z_adv = sec["pitch_mm_per_turn"] * sweep / (2 * math.pi)
        pts, L, rc = seg_helix_pts(sec["origin"], a, e1, e2, r, phi0, phi0 + sweep,
                                   0.0, z_adv, ds)
        return pts, L, rc
    raise ValueError("unknown section type %s" % kind)


def discrete_min_radius(pts):
    if len(pts) < 3:
        return math.inf
    A, B, C = pts[:-2], pts[1:-1], pts[2:]
    v1, v2 = B - A, C - B
    num = np.sqrt((np.cross(v1, v2) ** 2).sum(1))
    l1 = np.sqrt((v1 * v1).sum(1))
    l2 = np.sqrt((v2 * v2).sum(1))
    l3 = np.sqrt(((C - A) * (C - A)).sum(1))
    with np.errstate(divide="ignore", invalid="ignore"):
        R = np.where(num > 1e-12, l1 * l2 * l3 / (2 * num), np.inf)
    return float(np.min(R)) if len(R) else math.inf


# intended RC-part contact sets per segment (product-structure semantics:
# the guide/channel/clamp hardware serving a segment is DESIGNED to touch its
# cable; contact there is intended and excluded from the clearance predicate).
SEG_INTENDED_PARTS = {
    "SEG-00_BUS_FEEDTHROUGH_AND_RISER": {
        "RC-CHN-BUS-FT-BASE", "RC-CHN-BUS-FT-WALL-A", "RC-CHN-BUS-FT-WALL-B",
        "RC-CHN-BUS-FT-LINER", "RC-BRK-BUS-FLANGE", "RC-PLT-BUS-CONN",
        "RC-CLP-BUS-HN01", "RC-CLP-BUS-HN02", "RC-CLP-BUS-HN03",
        "RC-CLP-BUS-RISER", "RC-BRK-BASE-COLLAR", "RC-PLT-BASE-CONN",
        "RC-BRK-J1-RISER"},
    "SEG-01_J1_ANNULAR_SERVICE_LOOP": {
        "RC-GDE-J1-ANNULUS-LOW", "RC-GDE-J1-ANNULUS-UP", "RC-GDE-J1-ANNULUS-WALL",
        "RC-GDE-J1-LINER", "RC-CLP-J1-RELIEF-A1", "RC-CLP-J1-RELIEF-B1",
        "RC-CLP-J1-RELIEF-A2",
        "RC-CLP-J1-MOV", "RC-CLP-L1-01", "RC-BRK-L1-01"},
    "SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL": {
        "RC-GDE-J2-MANDREL", "RC-GDE-J2-MANDREL-LINER", "RC-CLP-J2-FIX",
        "RC-CLP-J2-MOV", "RC-CHN-L2-BASE", "RC-CHN-L2-WALL-A", "RC-CHN-L2-WALL-B",
        "RC-CHN-L2-LINER", "RC-CLP-L2-01", "RC-CLP-L2-02",
        "RC-CAR-J3-CARRIAGE", "RC-CLP-J3-MOV",
        "RC-CHN-E210-LINK-00", "RC-CHN-E210-LINK-01",
        "RC-CHN-E210-LINK-02", "RC-CHN-E210-LINK-03",
        "RC-CHN-E210-LINK-04", "RC-CHN-E210-LINK-05"},
    "SEG-03_J3_CARRIER_HYBRID_WRAP": {
        "RC-GDE-J3-SADDLE", "RC-GDE-J3-SADDLE-LINER", "RC-TRK-J3-RAIL",
        "RC-TRK-J3-STOP-A", "RC-TRK-J3-STOP-B", "RC-CAR-J3-CARRIAGE",
        "RC-CLP-J3-MOV", "RC-CHN-E210-LINK-00", "RC-CHN-E210-LINK-01",
        "RC-CHN-E210-LINK-02", "RC-CHN-E210-LINK-03", "RC-CHN-E210-LINK-04",
        "RC-CHN-E210-LINK-05", "RC-CHN-L3-BASE", "RC-CHN-L3-WALL-A",
        "RC-CHN-L3-WALL-B", "RC-CHN-L3-LINER",
        "RC-CLP-J3-HOST-BOUNDARY", "RC-CLP-L3-01", "RC-CLP-L3-02"},
    "SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER": {
        "RC-CLP-J4-FIX", "RC-GDE-J4-FIXED-APPROACH",
        "RC-GDE-J4-FIXED-APPROACH-LINER",
        "RC-TEL-J4-A-STAGE-1", "RC-TEL-J4-A-STAGE-2",
        "RC-TEL-J4-A-STAGE-3", "RC-TEL-J4-A-STAGE-4",
        "RC-TEL-J4-B-STAGE-1", "RC-TEL-J4-B-STAGE-2",
        "RC-TEL-J4-B-STAGE-3", "RC-TEL-J4-B-STAGE-4",
        "RC-TRK-J4-TROMBONE-RAIL", "RC-TRK-J4-STOP-NEG",
        "RC-TRK-J4-STOP-POS", "RC-CAR-J4-TROMBONE",
        "RC-GDE-J4-TROMBONE-U", "RC-GDE-J4-TROMBONE-U-LINER",
        "RC-GDE-J4-B-TO-ANNULUS", "RC-GDE-J4-B-TO-ANNULUS-LINER",
        "RC-CLP-J4-B", "RC-CLP-J4-ANN-ENTRY",
        "RC-GDE-J4-ANNULAR-FOLLOWER", "RC-GDE-J4-ANNULAR-FOLLOWER-LINER",
        "RC-CAR-J4-FOLLOWER-TROLLEY", "RC-CLP-J4-FOLLOWER",
        "RC-CLP-L4-01", "RC-GDE-J5-HIGH-BYPASS",
        "RC-GDE-J5-HIGH-BYPASS-LINER", "RC-GSP-L4-HIGH-E1",
        "RC-GSP-L4-HIGH-E2", "RC-CLP-J5-FIX"},
    "SEG-05_J5_WRIST_WRAP": {
        "RC-GDE-J5-WRAP", "RC-GDE-J5-WRAP-LINER", "RC-CLP-J5-FIX", "RC-CLP-J5-MOV",
        "RC-GDE-J5-HIGH-RETURN", "RC-GDE-J5-HIGH-RETURN-LINER",
        "RC-GSP-J5-HIGH-W2", "RC-GSP-J5-HIGH-W3", "RC-GSP-J5-HIGH-A6"},
    "SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN": {
        "RC-GDE-J6-RING-0", "RC-GDE-J6-RING-1", "RC-GDE-J6-RING-2",
        "RC-GDE-J6-RING-3", "RC-BRK-J6-GUIDE-A", "RC-BRK-J6-GUIDE-B",
        "RC-CLP-J6-FIX", "RC-CLP-J6-MOV",
        # wrist-run strain-relief station + connector split plate sit ON the
        # SEG-06 run (x 225..262, pre-plate): the run passes through the SR
        # clamp saddle bore and the boot bore zone and terminates at the
        # plate.  Serving-hardware registration (product-structure semantics),
        # same class as the clamp saddles above; was erroneously listed only
        # under SEG-07A/B.
        "RC-SR-WRIST", "RC-SR-WRIST-BOOT", "RC-PLT-WRIST-SPLIT"},
    "SEG-07A_WRIST_TAIL_DATA": {
        "RC-SR-WRIST", "RC-SR-WRIST-BOOT", "RC-PLT-WRIST-SPLIT",
        "RC-CONN-WR-D1", "RC-CONN-WR-P1"},
    "SEG-07B_WRIST_TAIL_POWER": {
        "RC-SR-WRIST", "RC-SR-WRIST-BOOT", "RC-PLT-WRIST-SPLIT",
        "RC-CONN-WR-D1", "RC-CONN-WR-P1"},
}


def main():
    log = []

    def note(msg):
        log.append(msg)
        print(msg, flush=True)

    # ---- input pinning -------------------------------------------------------
    pins = {}
    urdf_sha = sha256_file(P_URDF)
    pins["accepted_urdf"] = {"path": os.path.relpath(P_URDF, REPO).replace("\\", "/"),
                             "sha256": urdf_sha, "expected": URDF_SHA256_PIN,
                             "match": urdf_sha == URDF_SHA256_PIN}
    for tag, p in [("mount_pose_yaml", P_MOUNT), ("v9f_builder", P_BUILDER),
                    ("v9f_build_receipt", P_RECEIPT), ("centerline", P_CENTER),
                    ("clamp_register", P_CLAMPS), ("capability_registry", P_REG),
                    ("mission_contract", P_CONTRACT), ("mesh_pack_manifest", P_MANIFEST)]:
        pins[tag] = {"path": os.path.relpath(p, REPO).replace("\\", "/"),
                     "sha256": sha256_file(p)}
    pins["v9_input_manifest"] = {
        "path": os.path.relpath(V9_INPUT_MANIFEST, REPO).replace("\\", "/"),
        "sha256": sha256_file(V9_INPUT_MANIFEST),
        "expected": V9_INPUT_MANIFEST_SHA256,
        "match": sha256_file(V9_INPUT_MANIFEST) == V9_INPUT_MANIFEST_SHA256,
    }
    receipt = json.load(open(P_RECEIPT, encoding="utf-8"))
    expected_output_basenames = {
        "fcstd": "B601_ROUTE_C_GUIDED_DRESS_PACK_V9F.FCStd",
        "step": "B601_ROUTE_C_GUIDED_DRESS_PACK_V9F.step",
        "centerline_json": "B601_ROUTE_C_HARNESS_CENTERLINE_V9F.json",
        "clamp_register_csv": "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V9F.csv",
        "mass_delta_json": "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V9F.json",
    }
    receipt_checks = {
        "schema_v9f": receipt.get("schema") == "B601_ROUTE_C_BUILD_RECEIPT_V9F",
        "architecture_v9f": receipt.get("architecture") == EXPECTED_ARCHITECTURE,
        "input_manifest_match": bool(receipt.get("input_manifest", {}).get("match")),
        "input_manifest_sha_match": (
            receipt.get("input_manifest", {}).get("sha256", "").upper()
            == V9_INPUT_MANIFEST_SHA256),
        "output_names_match": all(
            os.path.basename(receipt.get("outputs", {}).get(k, "")) == v
            for k, v in expected_output_basenames.items()),
        "no_primary_carrier_parts": not any(
            ("PLANE-A-LINK" in p.get("name", "") or
             "PLANE-B-LINK" in p.get("name", "") or
             "CARRIER-SADDLE" in p.get("name", ""))
            for p in receipt.get("parts", [])),
        "motion_classes_bounded": all(
            p.get("motion_class") in (
                None, "FIXED_LINK3", "ONE_THIRD_TRAVEL",
                "TWO_THIRDS_TRAVEL", "FULL_TRAVEL", "FOLLOWER_LINK4",
                "FIXED_LINK4")
            for p in receipt.get("parts", [])),
    }
    pins["v9f_build_receipt_contract"] = {
        "checks": receipt_checks, "match": all(receipt_checks.values())}
    if (not pins["accepted_urdf"]["match"] or
            not pins["v9_input_manifest"]["match"] or
            not pins["v9f_build_receipt_contract"]["match"]):
        print("ABORT: V9F source/receipt authority binding mismatch", flush=True)
        raise SystemExit(3)

    manifest = json.load(open(P_MANIFEST, encoding="utf-8"))
    mi = manifest.get("inputs", {})
    manifest_contract_checks = {
        "variant_v9f": manifest.get("variant") == VARIANT,
        "schema_v9f": manifest.get("schema") == "ROUTE_C_SWEEP_MESH_PACK_V9F_MANIFEST",
        "receipt_hash_match": (
            mi.get("route_c_build_receipt", {}).get("sha256", "").upper()
            == pins["v9f_build_receipt"]["sha256"]),
        "urdf_hash_match": (
            mi.get("accepted_urdf", {}).get("sha256", "").upper()
            == URDF_SHA256_PIN),
        "input_manifest_hash_match": (
            mi.get("v9_input_manifest", {}).get("sha256", "").upper()
            == V9_INPUT_MANIFEST_SHA256 and
            bool(mi.get("v9_input_manifest", {}).get("match"))),
    }
    pins["v9f_mesh_manifest_contract"] = {
        "checks": manifest_contract_checks,
        "match": all(manifest_contract_checks.values()),
    }
    if not pins["v9f_mesh_manifest_contract"]["match"]:
        print("ABORT: V9F mesh manifest binding mismatch", flush=True)
        raise SystemExit(3)
    pack_files_ok = True
    pack_check = []
    for grp in manifest["files"]:
        for e in grp.get("entries", []):
            if "file" not in e:
                continue
            fp = os.path.join(P_PACK, e["file"])
            ok = os.path.exists(fp) and sha256_file(fp) == e["sha256"]
            pack_check.append({"file": e["file"], "match": ok})
            pack_files_ok = pack_files_ok and ok
        if grp["group"] == "gripper_rails":
            ps = grp.get("palm_slot")
            if ps:
                fp = os.path.join(P_PACK, ps["file"])
                ok = os.path.exists(fp) and sha256_file(fp) == ps["sha256"]
                pack_check.append({"file": ps["file"], "match": ok})
                pack_files_ok = pack_files_ok and ok
    pins["mesh_pack_files"] = {"checked": len(pack_check),
                               "mismatches": [c for c in pack_check if not c["match"]]}
    note("pack files verified: %d, mismatch: %d"
               % (len(pack_check), len(pins["mesh_pack_files"]["mismatches"])))
    if not pack_files_ok:
        print("ABORT: mesh pack hash mismatch", flush=True)
        raise SystemExit(3)

    # ---- mount + FK ----------------------------------------------------------
    mount_yaml = yaml.safe_load(open(P_MOUNT, encoding="utf-8"))
    arm = ArmModel(P_URDF, mount_yaml["mount"]["transform_mm_rows"])

    fk_val = []
    fk_ok = True
    for pose_name, q, row0 in [
            ("Q_DEPLOYED_HOME", [-1.570796, -2.094395, -1.047198, 0.0, -0.523599, 0.0],
             [0.499997, -0.866027, -6e-06, 91.616101]),
            ("Q_RELEASE_CLEAR", [-1.570796, -2.094395, -2.094395, -1.047198, -0.523599, 0.0],
             [0.500003, -0.866024, -6e-06, 91.618481]),
            ("Q_SERVICE_READY", [-1.570796, -1.047198, -2.094395, -0.523599, 0.0, 0.0],
             [4e-06, -1.0, -4e-06, -0.081635])]:
        T = arm.fk(q)["gripper_link"]
        res = float(np.max(np.abs(T[0, :] - np.array(row0))))
        fk_val.append({"pose": pose_name, "max_abs_residual_row0": res})
        fk_ok = fk_ok and res < 1e-3
    note("FK validation vs frozen witnesses: %s" % ("PASS" if fk_ok else "FAIL"))

    T0 = arm.fk([0.0] * 6)
    inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}

    # ---- centerline ----------------------------------------------------------
    center = json.load(open(P_CENTER, encoding="utf-8"))
    j4_source = next((s for s in center.get("segments", [])
                      if s.get("id") == J4_SEGMENT_ID), None)
    centerline_contract_checks = {
        "schema_v9f": center.get("schema") == "B601_ROUTE_C_HARNESS_CENTERLINE_V9F",
        "architecture_v9f": center.get("architecture") == EXPECTED_ARCHITECTURE,
        "j4_segment_present": j4_source is not None,
        "j4_exact_seven_sections": bool(
            j4_source and len(j4_source.get("sections", [])) == 7),
    }
    pins["v9f_centerline_contract"] = {
        "checks": centerline_contract_checks,
        "match": all(centerline_contract_checks.values()),
    }
    if not pins["v9f_centerline_contract"]["match"]:
        print("ABORT: V9F centerline schema/architecture mismatch", flush=True)
        raise SystemExit(3)

    # The exact J4 dynamic law is derived from the emitted V9F centerline, not
    # from rounded diagram coordinates.  Section topology is frozen as:
    # fixed approach / Plane-A leg / translating U / Plane-B leg /
    # fixed bridge / negative annular arc / link4-owned downstream route.
    j4_section_q0 = [build_section(s, ds=SAMPLE_DS)[0]
                     for s in j4_source["sections"]]
    J4_F_A = j4_section_q0[1][0].copy()
    J4_P_A_Q0 = j4_section_q0[1][-1].copy()
    J4_P_B_Q0 = j4_section_q0[3][0].copy()
    J4_F_B = j4_section_q0[3][-1].copy()
    J4_E_ANN = j4_section_q0[4][-1].copy()
    J4_DOWNSTREAM_Q0 = j4_section_q0[6].copy()
    j4_u_sec = j4_source["sections"][2]
    J4_U_CENTER_Q0 = np.asarray(j4_u_sec["center"], float)
    J4_U_E1 = np.asarray(j4_u_sec["basis_e1"], float)
    J4_U_E2 = np.asarray(j4_u_sec["basis_e2"], float)
    J4_U_RADIUS = float(j4_u_sec["radius_mm"])
    j4_ann_sec = j4_source["sections"][5]
    J4_ANN_CENTER = np.asarray(j4_ann_sec["center"], float)
    J4_ANN_AXIS = np.asarray(j4_ann_sec["normal"], float)
    J4_ANN_E1 = np.asarray(j4_ann_sec["basis_e1"], float)
    J4_ANN_E2 = np.asarray(j4_ann_sec["basis_e2"], float)
    J4_ANN_RADIUS = float(j4_ann_sec["radius_mm"])
    J4_ANN_ALPHA_FIXED = math.radians(float(j4_ann_sec["start_angle_deg"]))
    J4_ANN_BETA_Q0 = abs(math.radians(float(j4_ann_sec["sweep_deg"])))
    J4_X_FIXED = float(J4_F_A[0])
    J4_DYNAMIC_EXCHANGE_LENGTH_Q0 = (
        2.0*(J4_X_FIXED-float(J4_U_CENTER_Q0[0]))
        + math.pi*J4_U_RADIUS + J4_ANN_RADIUS*J4_ANN_BETA_Q0)
    source_geometry_checks = {
        "u_radius_match": abs(J4_U_RADIUS-J4_TROMBONE_R_MM) <= 1e-9,
        "annulus_radius_match": abs(J4_ANN_RADIUS-J4_ANNULUS_R_MM) <= 1e-9,
        "plane_a_continuity_mm": float(np.linalg.norm(J4_P_A_Q0-
            (J4_U_CENTER_Q0+J4_U_RADIUS*J4_U_E1))),
        "plane_b_continuity_mm": float(np.linalg.norm(J4_P_B_Q0-
            (J4_U_CENTER_Q0-J4_U_RADIUS*J4_U_E1))),
        "fixed_b_to_annulus_continuity_mm": float(np.linalg.norm(J4_E_ANN-
            (J4_ANN_CENTER+J4_ANN_RADIUS*J4_ANN_E2))),
        "downstream_start_to_annulus_q0_mm": float(np.linalg.norm(
            J4_DOWNSTREAM_Q0[0]-j4_section_q0[5][-1])),
    }
    source_geometry_pass = bool(
        source_geometry_checks["u_radius_match"] and
        source_geometry_checks["annulus_radius_match"] and
        max(source_geometry_checks[k] for k in (
            "plane_a_continuity_mm", "plane_b_continuity_mm",
            "fixed_b_to_annulus_continuity_mm",
            "downstream_start_to_annulus_q0_mm")) <= J4_FOLLOWER_CLOSURE_TOL_MM)
    pins["v9f_j4_source_geometry"] = {
        "checks": source_geometry_checks, "match": source_geometry_pass}
    if not source_geometry_pass:
        print("ABORT: V9F J4 centerline is not exact-continuous", flush=True)
        raise SystemExit(3)
    host_plan = {
        ("SEG-00_BUS_FEEDTHROUGH_AND_RISER", 0): ("base_link", None),
        ("SEG-01_J1_ANNULAR_SERVICE_LOOP", 0): ("base_link", None),
        ("SEG-01_J1_ANNULAR_SERVICE_LOOP", 1): ("link1", None),
        ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", 0): ("link1", "link2"),
        ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", 1): ("link2", "link1"),
        ("SEG-03_J3_CARRIER_HYBRID_WRAP", 0): ("link2", "link3"),
        ("SEG-03_J3_CARRIER_HYBRID_WRAP", 1): ("link2", "link3"),
        ("SEG-03_J3_CARRIER_HYBRID_WRAP", 2): ("link2", "link3"),
        ("SEG-03_J3_CARRIER_HYBRID_WRAP", 3): ("link3", None),
        (J4_SEGMENT_ID, 0): ("link3", None),
        (J4_SEGMENT_ID, 1): ("link3", None),
        (J4_SEGMENT_ID, 2): ("link3", None),
        (J4_SEGMENT_ID, 3): ("link3", None),
        (J4_SEGMENT_ID, 4): ("link3", None),
        (J4_SEGMENT_ID, 5): ("link3", None),
        (J4_SEGMENT_ID, 6): ("link4", None),
        ("SEG-05_J5_WRIST_WRAP", 0): ("link4", "link5"),
        ("SEG-05_J5_WRIST_WRAP", 1): ("link5", "link4"),
        ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", 0): ("link5", None),
        ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", 1): ("link6", None),
        ("SEG-07A_WRIST_TAIL_DATA", 0): ("link6", None),
        ("SEG-07B_WRIST_TAIL_POWER", 0): ("link6", None),
    }

    seg_records = []
    all_pts, all_host, all_alt, all_seg, all_sec, all_station = [], [], [], [], [], []
    min_routes = []
    menger_overall = math.inf
    bend_analytic_comparison_count = 0
    bend_menger_comparison_count = 0
    junction_checks = []
    section_station_ranges = {}
    for si, seg in enumerate(center["segments"]):
        sid = seg["id"]
        built_L = 0.0
        seg_min_r = math.inf
        prev_pts = None
        for ci, sec in enumerate(seg["sections"]):
            pts, L, rmin = build_section(sec)
            station_start = built_L
            if len(pts) > 1:
                local_station = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
                if local_station[-1] > 1e-12:
                    local_station *= L / local_station[-1]
            else:
                local_station = np.zeros(len(pts))
            host, alt = host_plan[(sid, ci)]
            hi = HOSTS.index(host)
            ai = HOSTS.index(alt) if alt else -1
            all_pts.append(pts)
            all_host += [hi] * len(pts)
            all_alt += [ai] * len(pts)
            all_seg += [si] * len(pts)
            all_sec += [ci] * len(pts)
            all_station.extend((station_start + local_station).tolist())
            section_station_ranges[(si, ci)] = (station_start, station_start + L)
            built_L += L
            seg_min_r = min(seg_min_r, rmin)
            if math.isfinite(rmin):
                bend_analytic_comparison_count += 1
            # per-section Menger (cross-section junctions are checked via the
            # tangent-continuity rule below, same as the A1 build-time check)
            sec_menger = discrete_min_radius(pts)
            menger_overall = min(menger_overall, sec_menger)
            if math.isfinite(sec_menger):
                bend_menger_comparison_count += 1
            if prev_pts is not None and len(prev_pts) >= 2 and len(pts) >= 2:
                t_end = prev_pts[-1] - prev_pts[-2]
                t_start = pts[1] - pts[0]
                n_end = np.linalg.norm(t_end)
                n_start = np.linalg.norm(t_start)
                if n_end > 1e-12 and n_start > 1e-12:
                    cos_a = float(np.clip(t_end @ t_start / (n_end * n_start), -1, 1))
                    ang = math.degrees(math.acos(cos_a))
                    junction_checks.append({"segment": sid, "junction": ci - 1,
                                            "tangent_mismatch_deg": ang,
                                            "pass_3deg_rule": bool(ang <= 3.0)})
            prev_pts = pts
        min_routes.append(seg_min_r)
        seg_records.append({
            "segment": sid,
            "declared_path_length_mm": seg["path_length_mm"],
            "rebuilt_path_length_mm": built_L,
            "length_residual_mm": built_L - seg["path_length_mm"],
            "min_radius_mm_analytic": seg_min_r,
            "take_up_required_mm": seg["take_up_required_mm"],
            "take_up_capacity_mm": seg["take_up_capacity_mm"],
        })
    P_A0 = np.vstack(all_pts)
    H_HOST = np.array(all_host, dtype=np.int32)
    H_ALT = np.array(all_alt, dtype=np.int32)
    H_SEG = np.array(all_seg, dtype=np.int32)
    H_SEC = np.array(all_sec, dtype=np.int32)
    H_STATION = np.array(all_station, dtype=float)
    note("centerline points: %d" % len(P_A0))

    bend_analytic = float(min(min_routes))
    junction_max_deg = max((jc["tangent_mismatch_deg"] for jc in junction_checks),
                           default=0.0)

    clamp_rows = []
    with open(P_CLAMPS, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            clamp_rows.append(row)
    clamp_axis_pts = []
    clamp_axis_tan = []
    for seg in center["segments"]:
        for sec in seg["sections"]:
            pts_f, _, _ = build_section(sec, ds=0.10)
            if len(pts_f) < 2:
                continue
            keep = np.r_[True, np.linalg.norm(np.diff(pts_f, axis=0), axis=1) > 1e-9]
            pts_f = pts_f[keep]
            if len(pts_f) < 2:
                continue
            tan_f = np.gradient(pts_f, axis=0)
            n_f = np.linalg.norm(tan_f, axis=1)
            tan_f = tan_f / np.maximum(n_f[:, None], 1e-12)
            clamp_axis_pts.append(pts_f)
            clamp_axis_tan.append(tan_f)
    P_CLAMP_AXIS = np.vstack(clamp_axis_pts)
    T_CLAMP_AXIS = np.vstack(clamp_axis_tan)
    CLAMP_AXIS_SAMPLE_ALLOW_MM = 0.051
    clamp_check = []
    for row in clamp_rows:
        host = row["host_link"]
        p_local = np.array([float(row["x_mm"]), float(row["y_mm"]), float(row["z_mm"])])
        p_A0 = p_local if row["frame"] == "S" else xform(T0[host], p_local)
        dist = np.sqrt(((P_CLAMP_AXIS - p_A0) ** 2).sum(1))
        k = int(np.argmin(dist))
        d = float(dist[k])
        applicable = bool(row.get("bore_radius_mm") and row.get("axis_dx"))
        rec = {"clamp_id": row["clamp_id"], "cad_part_name": row.get("cad_part_name"),
               "type": row["type"], "host": host,
               "min_dist_to_centerline_mm": d,
               "continuous_distance_upper_bound_mm": d + CLAMP_AXIS_SAMPLE_ALLOW_MM,
               "sampling_allowance_mm": CLAMP_AXIS_SAMPLE_ALLOW_MM,
               "applicable_to_bore_axis_gate": applicable}
        if applicable:
            axis_local = np.array([float(row["axis_dx"]), float(row["axis_dy"]),
                                   float(row["axis_dz"])])
            axis_A0 = axis_local if row["frame"] == "S" else T0[host][:3, :3] @ axis_local
            axis_A0 /= max(float(np.linalg.norm(axis_A0)), 1e-12)
            tangent = T_CLAMP_AXIS[k]
            angle = math.degrees(math.acos(max(-1.0, min(1.0,
                                                        abs(float(axis_A0 @ tangent))))))
            bore = float(row["bore_radius_mm"])
            retained = float(row["retained_radius_mm"])
            install = float(row["install_allowance_mm"])
            budget = bore - retained - install
            colocation_pass = d + CLAMP_AXIS_SAMPLE_ALLOW_MM <= budget + 1e-12
            tangent_pass = angle <= 3.0 + 1e-12
            rec.update({"bore_radius_mm": bore, "retained_radius_mm": retained,
                        "install_allowance_mm": install,
                        "colocation_budget_mm": budget,
                        "axis_to_centerline_tangent_angle_deg": angle,
                        "colocation_pass": bool(colocation_pass),
                        "tangent_pass": bool(tangent_pass),
                        "pass": bool(colocation_pass and tangent_pass)})
        else:
            rec.update({"pass": True, "disposition": "NOT_APPLICABLE_NON_BORE_INTERFACE"})
        clamp_check.append(rec)
    clamp_applicable = [c for c in clamp_check if c["applicable_to_bore_axis_gate"]]
    clamp_max_res = max(c["continuous_distance_upper_bound_mm"] for c in clamp_applicable)
    clamp_max_angle = max(c["axis_to_centerline_tangent_angle_deg"] for c in clamp_applicable)
    clamp_gate_pass = bool(clamp_applicable and all(c["pass"] for c in clamp_applicable))
    note("clamp/support bore-axis gate: %s; max distance upper %.3f mm; max tangent %.3f deg; "
         "bend analytic %.3f / menger %.3f"
         % ("PASS" if clamp_gate_pass else "FAIL", clamp_max_res, clamp_max_angle,
            bend_analytic, menger_overall))

    # ---- axisymmetry verification -------------------------------------------
    j1 = arm.rev[0]
    o1, a1 = arm.joint_axis_world(j1, T0)
    coil = center["segments"][1]["sections"][0]
    oc = np.array(coil["origin"], float)
    d_off1 = float(np.linalg.norm((oc - o1) - ((oc - o1) @ a1) * a1))
    j6 = arm.rev[5]
    o6, a6 = arm.joint_axis_world(j6, T0)
    hel = center["segments"][6]["sections"][0]
    oh = np.array(hel["origin"], float)
    ah = np.array(hel["axis"], float)
    d_par = float(np.linalg.norm(np.cross(ah / np.linalg.norm(ah), a6)))
    d_off6 = float(np.linalg.norm(np.cross((oh - o6), a6)))
    note("J1 coil axis offset %.5f mm; J6 helix parallel %.5f offset %.5f mm"
               % (d_off1, d_par, d_off6))

    # ---- obstacle fields ------------------------------------------------------
    def load_pack_tris(fname):
        return np.load(os.path.join(P_PACK, fname), allow_pickle=False)

    vendor_fields = {}
    solar_field = None
    for grp in manifest["files"]:
        if grp["group"] == "arm_vendor":
            for e in grp["entries"]:
                vendor_fields[e["link"]] = TriField(e["link"], load_pack_tris(e["file"]))
        if grp["group"] == "solar":
            solar_field = TriField("SOLAR_R2_DEPLOYED", load_pack_tris(grp["entries"][0]["file"]))
    rails = []
    palm = None
    for grp in manifest["files"]:
        if grp["group"] == "gripper_rails":
            for e in grp.get("entries", []):
                rails.append(TriField("RAIL_" + e["side"].upper(), load_pack_tris(e["file"])))
            palm = TriField("GRIPPER_PALM_SLOT", load_pack_tris(grp["palm_slot"]["file"]))
    bus_field = BusField()

    rc_parts = []   # (name, host, kind, motion_class, TriField)
    for grp in manifest["files"]:
        if grp["group"] == "route_c_parts":
            for e in grp["entries"]:
                if not e.get("valid") or e.get("kind") == "bundle_envelope":
                    continue
                fld = TriField(e["name"], load_pack_tris(e["file"]))
                rc_parts.append((e["name"], e["host_link"], e["kind"],
                                 e.get("motion_class"), fld))
    rc_v0_unique = {}
    for pname, _phost, _pkind, _motion_class, fld in rc_parts:
        if pname in rc_v0_unique:
            raise ValueError("duplicate Route-C part name in mesh pack: %s" % pname)
        rc_v0_unique[pname] = _exact_unique_rows_with_multiplicity(fld.v0)
    # J3 festoon carriage parts move along the link2 track with q3 (festoon
    # rule: carriage travel = R_saddle/2 * delta_q3 about the mid-range datum
    # q3_datum=-1.57; build position x=-140 mm in link2 frame).
    J3_CARRIAGE_PARTS = frozenset(
        ["RC-CAR-J3-CARRIAGE", "RC-CLP-J3-MOV"]
        + ["RC-CHN-E210-LINK-%02d" % i for i in range(6)])
    Q3_DATUM = -1.57
    CARRIAGE_X_BUILD = -140.0
    note("fields: vendor %d, rc parts %d, solar %d tris, rails %d"
               % (len(vendor_fields), len(rc_parts), solar_field.n, len(rails)))

    # ---- mission model --------------------------------------------------------
    contract = yaml.safe_load(open(P_CONTRACT, encoding="utf-8"))
    states = {k: v["q_rad"] for k, v in contract["states"].items()}
    segments = contract["segments"]

    def sample_segment(q_from, q_to, max_step):
        dq = [abs(b - a) for a, b in zip(q_from, q_to)]
        n = max(1, int(math.ceil(max(dq) / max_step)))
        ts = np.linspace(0.0, 1.0, n + 1)
        return (np.asarray(q_from, float)[None, :]
                + (np.asarray(q_to, float) - np.asarray(q_from, float))[None, :] * ts[:, None])

    reg = yaml.safe_load(open(P_REG, encoding="utf-8"))
    # take-up radii/capacities are read from the (variant) centerline JSON:
    # required_i = R_i * joint_range_i  =>  R_i = required_i / range_i;
    # capacity_i is the emitted design capacity for the segment.
    _seg_by_id = {s["id"]: s for s in center["segments"]}
    jrange = [j["hi"] - j["lo"] for j in arm.rev]
    def _loop_R(sid, jn):
        ji = [i for i, j in enumerate(arm.rev) if j["name"] == jn][0]
        return _seg_by_id[sid]["take_up_required_mm"] / jrange[ji]
    seg_takeup = [
        ("SEG-01_J1_ANNULAR_SERVICE_LOOP", "joint1", _loop_R("SEG-01_J1_ANNULAR_SERVICE_LOOP", "joint1"),
         _seg_by_id["SEG-01_J1_ANNULAR_SERVICE_LOOP"]["take_up_capacity_mm"]),
        ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", "joint2", _loop_R("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", "joint2"),
         _seg_by_id["SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL"]["take_up_capacity_mm"]),
        ("SEG-03_J3_CARRIER_HYBRID_WRAP", "joint3", _loop_R("SEG-03_J3_CARRIER_HYBRID_WRAP", "joint3"),
         _seg_by_id["SEG-03_J3_CARRIER_HYBRID_WRAP"]["take_up_capacity_mm"]),
        (J4_SEGMENT_ID, "joint4", _loop_R(J4_SEGMENT_ID, "joint4"),
         _seg_by_id[J4_SEGMENT_ID]["take_up_capacity_mm"]),
        ("SEG-05_J5_WRIST_WRAP", "joint5", _loop_R("SEG-05_J5_WRIST_WRAP", "joint5"),
         _seg_by_id["SEG-05_J5_WRIST_WRAP"]["take_up_capacity_mm"]),
        ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", "joint6", _loop_R("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", "joint6"),
         _seg_by_id["SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN"]["take_up_capacity_mm"]),
    ]
    jrange = [j["hi"] - j["lo"] for j in arm.rev]
    jeffort = [j["effort"] for j in arm.rev]
    seg_len = {r["segment"]: r["rebuilt_path_length_mm"] for r in seg_records}
    seg_id_list = [s["id"] for s in center["segments"]]
    seg_intended_idx = {
        si: (set() if sid == J4_SEGMENT_ID else SEG_INTENDED_PARTS.get(sid, set()))
        for si, sid in enumerate(seg_id_list)}
    # Adjacent-segment intended contact is fail-closed and fourfold bound:
    # exact segment + exact section + cumulative arclength interval + explicit
    # physical station/clamp whose bore-axis predicate has passed.  The V1/V8
    # Euclidean-65-mm shortcut is deliberately not inherited.
    clamp_gate_by_id = {c["clamp_id"]: c for c in clamp_check}

    def _make_interface_rule(rule_id, sid, ci, endpoint, station_id, clamp_id,
                             parts, full_section=False):
        si = seg_id_list.index(sid)
        s0, s1 = section_station_ranges[(si, ci)]
        if full_section:
            w0, w1 = s0, s1
        elif endpoint == "START":
            w0, w1 = s0, min(s1, s0+J4_INTERFACE_ARCLENGTH_WINDOW_MM)
        elif endpoint == "END":
            w0, w1 = max(s0, s1-J4_INTERFACE_ARCLENGTH_WINDOW_MM), s1
        else:
            raise ValueError("invalid interface endpoint %s" % endpoint)
        cc = clamp_gate_by_id.get(clamp_id)
        bore_ok = bool(cc and cc.get("applicable_to_bore_axis_gate") and cc.get("pass"))
        return {
            "rule_id": rule_id, "segment_id": sid, "segment_index": si,
            "section_index": ci,
            "cumulative_arclength_window_mm": [float(w0), float(w1)],
            "explicit_station_id": station_id, "clamp_id": clamp_id,
            "bore_axis_predicate": {
                "required": True, "evaluated": bool(cc), "pass": bore_ok,
                "axis_to_tangent_deg": (cc.get("axis_to_centerline_tangent_angle_deg")
                                          if cc else None),
                "colocation_upper_bound_mm": (cc.get("continuous_distance_upper_bound_mm")
                                                if cc else None),
            },
            "allowed_parts": sorted(parts),
            "valid_for_exclusion": bore_ok,
            "legacy_euclidean_window_used": False,
        }

    interface_rules = [
        _make_interface_rule(
            "IF-00-BUS-TO-J1", "SEG-00_BUS_FEEDTHROUGH_AND_RISER", 0, "END",
            "ST-BUS-RISER-END", "CF-BUS-03",
            {"RC-GDE-J1-ANNULUS-LOW", "RC-GDE-J1-ANNULUS-UP",
             "RC-GDE-J1-ANNULUS-WALL", "RC-GDE-J1-LINER"}),
        _make_interface_rule(
            "IF-01-J1-TO-J2", "SEG-01_J1_ANNULAR_SERVICE_LOOP", 1, "END",
            "ST-J2-FIX", "CF-J2-F",
            {"RC-GDE-J2-MANDREL", "RC-GDE-J2-MANDREL-LINER", "RC-CLP-J2-FIX"}),
        _make_interface_rule(
            "IF-02-J2-TO-J3", "SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", 1, "END",
            "ST-J3-CARRIAGE", "CM-J3-M",
            {"RC-GDE-J3-SADDLE", "RC-GDE-J3-SADDLE-LINER"}),
        _make_interface_rule(
            "IF-03-J3-TO-J4", "SEG-03_J3_CARRIER_HYBRID_WRAP", 3, "END",
            "ST-J4-TROMBONE-FIX", "CF-J4-F",
            {"RC-GDE-J4-FIXED-APPROACH",
             "RC-GDE-J4-FIXED-APPROACH-LINER"}),
        _make_interface_rule(
            "IF-04-J4-TO-J5", J4_SEGMENT_ID, 6, "END",
            "ST-J5-FIX", "CF-J5-F",
            {"RC-GDE-J5-WRAP", "RC-GDE-J5-WRAP-LINER", "RC-CLP-J5-MOV"}),
        _make_interface_rule(
            "IF-05-J5-CROSS-UPSTREAM", "SEG-05_J5_WRIST_WRAP", 0, "START",
            "ST-J5-FIX", "CF-J5-F",
            {"RC-GDE-J5-HIGH-BYPASS", "RC-GDE-J5-HIGH-BYPASS-LINER",
             "RC-CLP-J5-FIX", "RC-GSP-L4-HIGH-E2"}, full_section=True),
        _make_interface_rule(
            "IF-05-J5-TO-J6", "SEG-05_J5_WRIST_WRAP", 1, "END",
            "ST-J6-FIX", "CM-J6-F",
            {"RC-GDE-J6-RING-0", "RC-CLP-J6-FIX"}),
        _make_interface_rule(
            "IF-06-J6-FROM-J5", "SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", 0, "START",
            "ST-J6-FIX", "CM-J6-F",
            {"RC-GDE-J5-HIGH-RETURN", "RC-GDE-J5-HIGH-RETURN-LINER",
             "RC-GSP-J5-HIGH-A6"}),
    ]
    # J4 is not granted the legacy whole-segment own-hardware exemption.  Each
    # intended cable/guide contact is bounded to one explicit section and its
    # cumulative arclength, with a registered bore-axis clamp as the physical
    # station witness.  Other static segments retain their frozen semantics.
    interface_rules += [
        _make_interface_rule(
            "J4-LOCAL-00-FIXED-APPROACH", J4_SEGMENT_ID, 0, "END",
            "ST-J4-FIXED-APPROACH", "CF-J4-F",
            {"RC-CLP-J4-FIX", "RC-GDE-J4-FIXED-APPROACH",
             "RC-GDE-J4-FIXED-APPROACH-LINER"}, full_section=True),
        _make_interface_rule(
            "J4-LOCAL-01-PLANE-A-TELESCOPE", J4_SEGMENT_ID, 1, "START",
            "ST-J4-PLANE-A", "CF-J4-F",
            {"RC-TEL-J4-A-STAGE-1", "RC-TEL-J4-A-STAGE-2",
             "RC-TEL-J4-A-STAGE-3", "RC-TEL-J4-A-STAGE-4"},
            full_section=True),
        _make_interface_rule(
            "J4-LOCAL-02-U-SADDLE", J4_SEGMENT_ID, 2, "START",
            "ST-J4-U-SADDLE", "CF-J4-F",
            {"RC-CAR-J4-TROMBONE", "RC-GDE-J4-TROMBONE-U",
             "RC-GDE-J4-TROMBONE-U-LINER"}, full_section=True),
        _make_interface_rule(
            "J4-LOCAL-03-PLANE-B-TELESCOPE", J4_SEGMENT_ID, 3, "END",
            "ST-J4-PLANE-B", "CF-J4-B",
            {"RC-TEL-J4-B-STAGE-1", "RC-TEL-J4-B-STAGE-2",
             "RC-TEL-J4-B-STAGE-3", "RC-TEL-J4-B-STAGE-4",
             "RC-CLP-J4-B"}, full_section=True),
        _make_interface_rule(
            "J4-LOCAL-04-BRIDGE", J4_SEGMENT_ID, 4, "END",
            "ST-J4-ANNULAR-ENTRY", "CF-J4-ANN-E",
            {"RC-GDE-J4-B-TO-ANNULUS", "RC-GDE-J4-B-TO-ANNULUS-LINER",
             "RC-CLP-J4-B", "RC-CLP-J4-ANN-ENTRY"}, full_section=True),
        _make_interface_rule(
            "J4-LOCAL-05-ANNULAR-FOLLOWER", J4_SEGMENT_ID, 5, "START",
            "ST-J4-ANNULAR-ENTRY", "CF-J4-ANN-E",
            {"RC-GDE-J4-ANNULAR-FOLLOWER",
             "RC-GDE-J4-ANNULAR-FOLLOWER-LINER",
             "RC-CAR-J4-FOLLOWER-TROLLEY", "RC-CLP-J4-FOLLOWER",
             "RC-CLP-J4-ANN-ENTRY"}, full_section=True),
        _make_interface_rule(
            "J4-LOCAL-06-LINK4-DOWNSTREAM", J4_SEGMENT_ID, 6, "START",
            "ST-J4-LINK4-DOWNSTREAM", "CF-L4-01",
            {"RC-CAR-J4-FOLLOWER-TROLLEY", "RC-CLP-J4-FOLLOWER",
             "RC-CLP-L4-01", "RC-GDE-J5-HIGH-BYPASS",
             "RC-GDE-J5-HIGH-BYPASS-LINER", "RC-GSP-L4-HIGH-E1",
             "RC-GSP-L4-HIGH-E2", "RC-CLP-J5-FIX"}, full_section=True),
    ]
    interface_rules_by_seg = {}
    for rule in interface_rules:
        interface_rules_by_seg.setdefault(rule["segment_index"], []).append(rule)
    interface_exception_audit_pass = bool(
        interface_rules and all(r["valid_for_exclusion"] and
                                not r["legacy_euclidean_window_used"]
                                for r in interface_rules))

    # Frozen route-group order is the original HOSTS x attachment-alternate
    # loop order.  All q-invariant product-structure/interface exclusions are
    # compiled once, so excluded guide contact never enters a distance kernel.
    j4_si_route = seg_id_list.index(J4_SEGMENT_ID)
    route_groups = []
    for hi, h in enumerate(HOSTS):
        for altflag in (0, 1):
            idx = np.flatnonzero((H_HOST == hi) if altflag == 0 else (H_ALT == hi))
            if len(idx) == 0:
                continue
            seg_of_pts = H_SEG[idx]
            sec_of_pts = H_SEC[idx]
            station_of_pts = H_STATION[idx]
            j4_dynamic = ((seg_of_pts == j4_si_route)
                          & np.isin(sec_of_pts, [1, 2, 3, 5]))
            eligible_by_part = {}
            for pname, _phost, _pkind, _motion_class, _fld in rc_parts:
                intended = np.array(
                    [pname in seg_intended_idx[int(si)] for si in seg_of_pts],
                    dtype=bool)
                if not intended.all():
                    for si in set(int(x) for x in seg_of_pts):
                        for rule in interface_rules_by_seg.get(si, []):
                            if (pname not in rule["allowed_parts"] or
                                    not rule["valid_for_exclusion"]):
                                continue
                            w0, w1 = rule["cumulative_arclength_window_mm"]
                            intended |= ((seg_of_pts == si)
                                         & (sec_of_pts == rule["section_index"])
                                         & (station_of_pts >= w0-1e-12)
                                         & (station_of_pts <= w1+1e-12))
                eligible_by_part[pname] = ~intended
            if (set(eligible_by_part) != {p[0] for p in rc_parts} or
                    any(mask.dtype != np.bool_ or len(mask) != len(idx)
                        for mask in eligible_by_part.values())):
                raise RuntimeError("Route-C interface exclusion cache audit failure")
            route_groups.append({
                "host": h,
                "alternate": bool(altflag),
                "indices": idx,
                "P_A0": P_A0[idx],
                "segment": seg_of_pts,
                "section": sec_of_pts,
                "station": station_of_pts,
                "j4_dynamic": j4_dynamic,
                "rc_eligible": eligible_by_part,
            })

    upstream = {"base_link": [], "link1": [0], "link2": [0, 1], "link3": [0, 1, 2],
                "link4": [0, 1, 2, 3], "link5": [0, 1, 2, 3, 4],
                "link6": [0, 1, 2, 3, 4, 5]}

    def pose_points(P, host, T):
        Mh = T[host] @ inv_T0[host]
        return xform_batch(arm.mount @ Mh, P)

    def _unit(v):
        v = np.asarray(v, float)
        n = float(np.linalg.norm(v))
        if n <= 1e-12:
            raise ValueError("zero vector in V9F exact trombone/follower model")
        return v / n

    def j4_dynamic_state(q, T):
        """Exact V9F chainless trombone plus external annular follower.

        The two telescope legs change length symmetrically while the R55.036 U
        saddle translates rigidly.  The external R55 annular cable arc changes
        its occupied angle by the opposite length.  The moving endpoint is
        independently closed against the accepted-URDF link4 FK.  No Bezier,
        proportional solid scaling or distributed carrier deformation is used.
        """
        q4 = float(q[3])
        x_c = J4_CARRIER_X_MID_MM - J4_CARRIER_GAIN_MM_PER_RAD*(q4-J4_Q_MID_RAD)
        dx = x_c - J4_CARRIER_X_Q0_MM
        M3 = arm.mount @ T["link3"] @ inv_T0["link3"]
        M4 = arm.mount @ T["link4"] @ inv_T0["link4"]
        u_center = J4_U_CENTER_Q0 + np.array([dx, 0.0, 0.0])
        pa_a0 = u_center + J4_U_RADIUS*J4_U_E1
        pb_a0 = u_center - J4_U_RADIUS*J4_U_E1
        beta = J4_ANNULUS_SEED_RAD + (J4_Q_MAX_RAD-q4)
        alpha_m = J4_ANN_ALPHA_FIXED-beta
        ann_moving_a0 = (J4_ANN_CENTER + J4_ANN_RADIUS*(
            math.cos(alpha_m)*J4_ANN_E1 + math.sin(alpha_m)*J4_ANN_E2))
        ann_moving_s = xform(M3, ann_moving_a0)
        follower_fk_s = xform(M4, J4_DOWNSTREAM_Q0[0])
        follower_residual = float(np.linalg.norm(ann_moving_s-follower_fk_s))
        leg_length = J4_X_FIXED-x_c
        l_trombone = 2.0*leg_length + math.pi*J4_U_RADIUS
        l_annulus = J4_ANN_RADIUS*beta
        exchange_length = l_trombone+l_annulus
        exchange_residual = exchange_length-J4_DYNAMIC_EXCHANGE_LENGTH_Q0
        overlap = ((J4_TELESCOPE_STAGE_COUNT*J4_TELESCOPE_STAGE_LENGTH_MM-leg_length)
                   / (J4_TELESCOPE_STAGE_COUNT-1.0))
        stop_margin = min(x_c-J4_STOP_MIN_MM, J4_STOP_MAX_MM-x_c)
        guide_margin_rad = J4_ANNULUS_GUIDE_COVERAGE_RAD-beta
        return {
            "q4_rad": q4, "x_c_mm": x_c, "dx_mm": dx,
            "M3": M3, "M4": M4, "u_center_A0": u_center,
            "plane_a_tangent_A0": pa_a0, "plane_b_tangent_A0": pb_a0,
            "annulus_beta_rad": beta, "annulus_alpha_m_rad": alpha_m,
            "annulus_moving_A0": ann_moving_a0,
            "follower_endpoint_S": ann_moving_s,
            "link4_fk_endpoint_S": follower_fk_s,
            "follower_closure_residual_mm": follower_residual,
            "trombone_length_mm": l_trombone,
            "annulus_length_mm": l_annulus,
            "dynamic_exchange_length_mm": exchange_length,
            "dynamic_exchange_length_residual_mm": exchange_residual,
            "stage_overlap_mm": overlap,
            "hard_stop_margin_mm": stop_margin,
            "within_q4_hardware_limits": bool(
                J4_Q_MIN_RAD-1e-12 <= q4 <= J4_Q_MAX_RAD+1e-12),
            "annulus_guide_margin_rad": guide_margin_rad,
            "dynamic_min_bend_radius_mm": float(min(J4_U_RADIUS, J4_ANN_RADIUS)),
        }

    def pose_route_points(P0, host, T, q, seg_idx, sec_idx, j4s):
        """Pose route samples with the exact V9F J4 cable law."""
        out = pose_points(P0, host, T)
        j4_si = seg_id_list.index(J4_SEGMENT_ID)
        for ci in (1, 2, 3, 5):
            mm = (seg_idx == j4_si) & (sec_idx == ci)
            if not mm.any():
                continue
            if ci == 1:
                d0 = J4_P_A_Q0-J4_F_A
                u = ((P0[mm]-J4_F_A) @ d0) / max(float(d0@d0), 1e-12)
                p = J4_F_A + u[:, None]*(j4s["plane_a_tangent_A0"]-J4_F_A)
                out[mm] = xform_batch(j4s["M3"], p)
            elif ci == 2:
                p = P0[mm].copy()
                p[:, 0] += j4s["dx_mm"]
                out[mm] = xform_batch(j4s["M3"], p)
            elif ci == 3:
                d0 = J4_F_B-J4_P_B_Q0
                u = ((P0[mm]-J4_P_B_Q0) @ d0) / max(float(d0@d0), 1e-12)
                p = (j4s["plane_b_tangent_A0"]
                     + u[:, None]*(J4_F_B-j4s["plane_b_tangent_A0"]))
                out[mm] = xform_batch(j4s["M3"], p)
            else:  # exact negative annular arc, fixed entry to link4 follower
                rel = P0[mm]-J4_ANN_CENTER
                alpha0 = np.arctan2(rel @ J4_ANN_E2, rel @ J4_ANN_E1)
                u = np.clip((J4_ANN_ALPHA_FIXED-alpha0)/J4_ANN_BETA_Q0, 0.0, 1.0)
                alpha = J4_ANN_ALPHA_FIXED-j4s["annulus_beta_rad"]*u
                p = (J4_ANN_CENTER
                     + J4_ANN_RADIUS*(np.cos(alpha)[:, None]*J4_ANN_E1
                                      + np.sin(alpha)[:, None]*J4_ANN_E2))
                out[mm] = xform_batch(j4s["M3"], p)
        return out

    def rc_part_pose_S(pname, phost, motion_class, fld, T, q, dx_j3, j4s):
        """Return S<-A0 pose using rigid V9F hardware motions only."""
        if pname in J3_CARRIAGE_PARTS:
            return arm.mount @ T[phost] @ tr(dx_j3, 0.0, 0.0) @ inv_T0[phost]
        if motion_class == "FIXED_LINK3":
            return j4s["M3"]
        if motion_class in ("ONE_THIRD_TRAVEL", "TWO_THIRDS_TRAVEL",
                            "FULL_TRAVEL"):
            gain = {"ONE_THIRD_TRAVEL": 1.0/3.0,
                    "TWO_THIRDS_TRAVEL": 2.0/3.0,
                    "FULL_TRAVEL": 1.0}[motion_class]
            return j4s["M3"] @ tr(gain*j4s["dx_mm"], 0.0, 0.0)
        if motion_class == "FOLLOWER_LINK4":
            return j4s["M4"]
        return arm.mount @ T.get(phost, np.eye(4)) @ inv_T0.get(phost, np.eye(4))

    def axis_derate(P_S, host, joint_axes_S):
        if not upstream[host]:
            return np.zeros(len(P_S))
        out = np.zeros(len(P_S))
        for ji in upstream[host]:
            oS, aS = joint_axes_S[ji]
            v = P_S - oS
            d = np.sqrt(((v - np.outer(v @ aS, aS)) ** 2).sum(1))
            out += DQ_TOTAL * d
        return out

    # ---- clearance evaluation ----------------------------------------------------
    def _field_aabb_S(fld, Mpose):
        """broad-phase AABB of a field viewed in the S frame (frame-correct;
        axis-aligned bound of the pose-transformed local box; conservative)."""
        cs = xform_batch(Mpose, fld.aabb_corners)
        return cs.min(axis=0), cs.max(axis=0)

    SEG_BAND = {0: "SEG-01_J1_ANNULAR_SERVICE_LOOP",
                1: "SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL",
                2: "SEG-03_J3_CARRIER_HYBRID_WRAP",
                3: J4_SEGMENT_ID,
                4: "SEG-05_J5_WRIST_WRAP",
                5: "SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN"}
    pinch_evidence_template = {
        j["name"]: int(
            j["parent"] in vendor_fields and j["child"] in vendor_fields and
            (H_SEG == seg_id_list.index(SEG_BAND[ji])).any())
        for ji, j in enumerate(arm.rev)}

    # Small deterministic FIFO cache for base kinematics only.  The complete
    # clearance result cache below remains the authority for q-round12 reuse;
    # large per-part arrays are retained only for the current q.
    kinematic_cache = {}
    kinematic_cache_order = []
    KINEMATIC_CACHE_MAX = 256

    def _base_kinematics(q):
        q_arr = np.asarray(q, float)
        q_key = _q_round12_key(q_arr)
        cached = kinematic_cache.get(q_key)
        # Cross-check code uses six-decimal q samples.  Reuse a q-round12 entry
        # only when the actual binary q vector is also identical, preserving the
        # frozen calculation exactly if an unlikely rounding-key collision occurs.
        if (cached is not None and
                np.ascontiguousarray(cached["q"]).tobytes()
                == np.ascontiguousarray(q_arr).tobytes()):
            return cached
        T = arm.fk(list(q_arr))
        TS = {k: arm.mount @ v for k, v in T.items()}
        inv_TS = {k: np.linalg.inv(v) for k, v in TS.items()}
        joint_axes_S = []
        for j in arm.rev:
            o, a = arm.joint_axis_world(j, T)
            joint_axes_S.append((xform(arm.mount, o), arm.mount[:3, :3] @ a))
        j4s = j4_dynamic_state(q_arr, T)
        dx_car = 0.5 * J3_SADDLE_R * (float(q_arr[2]) - Q3_DATUM) - 0.0
        dx_car = max(-55.0, min(55.0, dx_car))
        state = {
            "q": q_arr.copy(), "T": T, "TS": TS, "inv_TS": inv_TS,
            "joint_axes_S": joint_axes_S, "j4": j4s, "dx_car": dx_car,
            "vendor_aabb_S": {
                lname: _field_aabb_S(fld, TS[lname])
                for lname, fld in vendor_fields.items()},
            "gripper_aabb_S": {
                id(fld): _field_aabb_S(fld, TS["gripper_link"])
                for fld in rails + [palm]},
        }
        if q_key not in kinematic_cache:
            kinematic_cache_order.append(q_key)
        kinematic_cache[q_key] = state
        while len(kinematic_cache_order) > KINEMATIC_CACHE_MAX:
            old = kinematic_cache_order.pop(0)
            kinematic_cache.pop(old, None)
        return state

    def _rc_pose_context(base, q, require_inverse=True, require_aabb=True):
        rc_pose = {}
        rc_inv = {}
        rc_aabb = {}
        for pname, phost, _pkind, motion_class, fld in rc_parts:
            Mpart = rc_part_pose_S(
                pname, phost, motion_class, fld, base["T"], q,
                base["dx_car"], base["j4"])
            rc_pose[pname] = Mpart
            if require_inverse:
                rc_inv[pname] = np.linalg.inv(Mpart)
            if require_aabb:
                rc_aabb[pname] = _field_aabb_S(fld, Mpart)
        return rc_pose, rc_inv, rc_aabb

    eval_cache = {}
    def eval_clearance(q, pinch_only=False):
        cache_key = (bool(pinch_only),) + _q_round12_key(q)
        if cache_key in eval_cache:
            return eval_cache[cache_key]
        base = _base_kinematics(q)
        T = base["T"]
        inv_TS = base["inv_TS"]
        j4s = base["j4"]
        aabb_S = base["vendor_aabb_S"]
        aabb_rail = base["gripper_aabb_S"]
        _rc_pose, rc_inv, aabb_rc = _rc_pose_context(base, q)
        best_gated = math.inf
        best_raw = math.inf
        best_detail = None
        pinch = {j["name"]: math.inf for j in arm.rev}
        comparison_counts = {"vendor": 0, "route_c_hardware": 0,
                             "solar": 0, "bus": 0, "gripper": 0}
        pinch_evidence_count = dict(pinch_evidence_template)

        for group in route_groups:
            h = group["host"]
            altflag = group["alternate"]
            P0_group = group["P_A0"]
            seg_of_pts = group["segment"]
            sec_of_pts = group["section"]
            j4_dynamic = group["j4_dynamic"]
            P = pose_route_points(P0_group, h, T, q, seg_of_pts, sec_of_pts, j4s)
            if len(P) == 0 or not np.isfinite(P).all():
                raise RuntimeError("non-finite or empty posed Route-C group")
            pmin, pmax = P.min(axis=0), P.max(axis=0)
            dr = axis_derate(P, h, base["joint_axes_S"]) + D_STATIC
            # Explicit q4 tracking tube for the non-rigid cable law.  The
            # link4-owned downstream run is already covered by axis_derate.
            dr = dr + j4_dynamic.astype(float)*J4_ANN_RADIUS*DQ_TOTAL

            # Rigid own-host pairs are precomputed once at q=0.  Only the J4
            # points whose shape changes in the host frame enter this kernel.
            for lname, fld in vendor_fields.items():
                eligible = j4_dynamic if lname == h else None
                if eligible is not None and not eligible.any():
                    continue
                bmn, bmx = aabb_S[lname]
                candidate = _conservative_aabb_candidates(
                    P, pmin, pmax, bmn, bmx, fld.D)
                if eligible is not None:
                    candidate &= eligible
                if not candidate.any():
                    continue
                candidate_idx = np.flatnonzero(candidate)
                Pl = xform_batch(inv_TS[lname], P[candidate_idx])
                c = fld.signed_clearance_batch(Pl, BUNDLE_R)
                ok = ~np.isnan(c)
                valid_idx = candidate_idx[ok]
                comparison_counts["vendor"] += int(ok.sum())
                if not ok.any():
                    continue
                gated = c[ok] - dr[valid_idx]
                k = int(np.argmin(gated))
                gv = float(gated[k])
                pi = int(valid_idx[k])
                if gv < best_gated:
                    best_gated = gv
                    best_raw = float(c[ok][k])
                    best_detail = {"host": h, "alternate": bool(altflag),
                                   "field": "vendor:" + lname,
                                   "point_A0_q0": [float(x) for x in P0_group[pi]],
                                   "derate_mm": float(dr[pi]),
                                   "segment": seg_id_list[int(seg_of_pts[pi])],
                                   "section_index": int(sec_of_pts[pi])}
                # pinch: points on the segment crossing joint ji vs its housings
                for ji, j in enumerate(arm.rev):
                    if lname not in (j["parent"], j["child"]):
                        continue
                    bseg = seg_id_list.index(SEG_BAND[ji])
                    mb = seg_of_pts[valid_idx] == bseg
                    if not mb.any():
                        continue
                    gb = gated[mb]
                    kb = int(np.argmin(gb))
                    if float(gb[kb]) < pinch[j["name"]]:
                        pinch[j["name"]] = float(gb[kb])

            # RC fields: q-invariant intended/interface masks are applied before
            # both the broad phase and the exact signed-distance kernel.
            for pname, _phost, _pkind, _motion_class, fld in rc_parts:
                eligible = group["rc_eligible"][pname]
                if not eligible.any():
                    continue
                bmn, bmx = aabb_rc[pname]
                candidate = _conservative_aabb_candidates(
                    P, pmin, pmax, bmn, bmx, fld.D)
                candidate &= eligible
                if not candidate.any():
                    continue
                candidate_idx = np.flatnonzero(candidate)
                Pl = xform_batch(rc_inv[pname], P[candidate_idx])
                c = fld.signed_clearance_batch(Pl, BUNDLE_R)
                ok = ~np.isnan(c)
                valid_idx = candidate_idx[ok]
                comparison_counts["route_c_hardware"] += int(ok.sum())
                if not ok.any():
                    continue
                gated = c[ok] - dr[valid_idx]
                k = int(np.argmin(gated))
                gv = float(gated[k])
                pi = int(valid_idx[k])
                if gv < best_gated:
                    best_gated = gv
                    best_raw = float(c[ok][k])
                    best_detail = {"host": h, "alternate": bool(altflag),
                                   "field": "rc:" + pname,
                                   "point_A0_q0": [float(x) for x in P0_group[pi]],
                                   "derate_mm": float(dr[pi]),
                                   "segment": seg_id_list[int(seg_of_pts[pi])],
                                   "section_index": int(sec_of_pts[pi])}

            # Solar field (fixed in S).
            candidate = _conservative_aabb_candidates(
                P, pmin, pmax, solar_field.bmin, solar_field.bmax, solar_field.D)
            if candidate.any():
                candidate_idx = np.flatnonzero(candidate)
                c = solar_field.signed_clearance_batch(P[candidate_idx], BUNDLE_R)
                ok = ~np.isnan(c)
                valid_idx = candidate_idx[ok]
                comparison_counts["solar"] += int(ok.sum())
                if ok.any():
                    gated = c[ok] - dr[valid_idx]
                    k = int(np.argmin(gated))
                    gv = float(gated[k])
                    pi = int(valid_idx[k])
                    if gv < best_gated:
                        best_gated = gv
                        best_raw = float(c[ok][k])
                        best_detail = {"host": h, "alternate": bool(altflag),
                                       "field": "solar",
                                       "point_A0_q0": [float(x) for x in P0_group[pi]],
                                       "derate_mm": float(dr[pi]),
                                       "segment": seg_id_list[int(seg_of_pts[pi])],
                                       "section_index": int(sec_of_pts[pi])}

            # Bus field (fixed in S).
            candidate = _conservative_aabb_candidates(
                P, pmin, pmax, BUS_MIN, BUS_MAX, bus_field.D)
            if candidate.any():
                candidate_idx = np.flatnonzero(candidate)
                c = bus_field.signed_clearance_batch(P[candidate_idx], BUNDLE_R)
                ok = ~np.isnan(c)
                valid_idx = candidate_idx[ok]
                comparison_counts["bus"] += int(ok.sum())
                if ok.any():
                    gated = c[ok] - dr[valid_idx]
                    k = int(np.argmin(gated))
                    gv = float(gated[k])
                    pi = int(valid_idx[k])
                    if gv < best_gated:
                        best_gated = gv
                        best_raw = float(c[ok][k])
                        best_detail = {"host": h, "alternate": bool(altflag),
                                       "field": "bus",
                                       "point_A0_q0": [float(x) for x in P0_group[pi]],
                                       "derate_mm": float(dr[pi]),
                                       "segment": seg_id_list[int(seg_of_pts[pi])],
                                       "section_index": int(sec_of_pts[pi])}

            # Rails + palm share one gripper-local transform per route group.
            P_gripper = None
            for fld in rails + [palm]:
                bmn, bmx = aabb_rail[id(fld)]
                candidate = _conservative_aabb_candidates(
                    P, pmin, pmax, bmn, bmx, fld.D)
                if not candidate.any():
                    continue
                if P_gripper is None:
                    P_gripper = xform_batch(inv_TS["gripper_link"], P)
                candidate_idx = np.flatnonzero(candidate)
                c = fld.signed_clearance_batch(P_gripper[candidate_idx], BUNDLE_R)
                ok = ~np.isnan(c)
                valid_idx = candidate_idx[ok]
                comparison_counts["gripper"] += int(ok.sum())
                if not ok.any():
                    continue
                gated = c[ok] - dr[valid_idx]
                k = int(np.argmin(gated))
                gv = float(gated[k])
                pi = int(valid_idx[k])
                if gv < best_gated:
                    best_gated = gv
                    best_raw = float(c[ok][k])
                    best_detail = {"host": h, "alternate": bool(altflag),
                                   "field": "gripper:" + fld.name,
                                   "point_A0_q0": [float(x) for x in P0_group[pi]],
                                   "derate_mm": float(dr[pi]),
                                   "segment": seg_id_list[int(seg_of_pts[pi])],
                                   "section_index": int(sec_of_pts[pi])}
        comparison_counts["total"] = int(sum(comparison_counts.values()))
        result = {"clearance": best_gated, "clearance_raw": best_raw,
                  "detail": best_detail, "pinch": pinch,
                  "comparison_counts": comparison_counts,
                  "pinch_evidence_count": pinch_evidence_count,
                  "j4_dynamic_min_bend_radius_mm": j4s["dynamic_min_bend_radius_mm"],
                  "j4_carriage_center_x_mm": j4s["x_c_mm"],
                  "j4_dynamic_exchange_length_residual_mm":
                      j4s["dynamic_exchange_length_residual_mm"],
                  "j4_follower_closure_residual_mm":
                      j4s["follower_closure_residual_mm"],
                  "j4_stage_overlap_mm": j4s["stage_overlap_mm"],
                  "j4_hard_stop_margin_mm": j4s["hard_stop_margin_mm"],
                  "j4_annulus_guide_margin_rad": j4s["annulus_guide_margin_rad"],
                  "j4_within_hardware_limits": j4s["within_q4_hardware_limits"]}
        eval_cache[cache_key] = result
        return result

    # ---- own-host-of-attachment clearances (pose-invariant rigid pairs) --------
    # For a cable point attached to host h, its clearance vs the vendor mesh of
    # h is constant (the pair is rigid): tracking-tube joint errors move them
    # together.  Computed once at q=0; derate = static allowance only (the
    # axis-tracking component does not apply to a rigid pair).
    inv_TS0 = {k: np.linalg.inv(arm.mount @ v) for k, v in T0.items()}
    own_best_seg = {}
    own_detail_seg = {}
    own_pinch = {j["name"]: math.inf for j in arm.rev}
    own_clearance_comparison_count = 0
    j4_si_constant = seg_id_list.index(J4_SEGMENT_ID)
    for hi, h in enumerate(HOSTS):
        if h not in vendor_fields:
            continue
        fld = vendor_fields[h]
        for altflag in (0, 1):
            m = (H_HOST == hi) if altflag == 0 else (H_ALT == hi)
            if not m.any():
                continue
            P = pose_points(P_A0[m], h, T0)
            Pl = xform_batch(inv_TS0[h], P)
            c = fld.signed_clearance_batch(Pl, BUNDLE_R)
            ok = ~np.isnan(c)
            seg_of_pts = H_SEG[m]
            sec_of_pts = H_SEC[m]
            q4_shape_changes = ((seg_of_pts == j4_si_constant)
                                & np.isin(sec_of_pts, [1, 2, 3, 5]))
            ok &= ~q4_shape_changes
            own_clearance_comparison_count += int(ok.sum())
            if not ok.any():
                continue
            gated = c[ok] - D_STATIC
            for si in set(int(s) for s in seg_of_pts):
                mb = seg_of_pts[ok] == si
                if not mb.any():
                    continue
                gb = gated[mb]
                kb = int(np.argmin(gb))
                gv = float(gb[kb])
                idxs = np.flatnonzero(ok)
                sub = idxs[mb]
                pi = int(sub[kb])
                if si not in own_best_seg or gv < own_best_seg[si]:
                    own_best_seg[si] = gv
                    own_detail_seg[si] = {"host": h, "alternate": bool(altflag),
                                          "field": "vendor:%s(own-host constant)" % h,
                                          "point_A0_q0": [float(x) for x in P_A0[m][pi]],
                                          "derate_mm": D_STATIC,
                                          "segment": seg_id_list[si]}
            for ji, j in enumerate(arm.rev):
                if h not in (j["parent"], j["child"]):
                    continue
                bseg = seg_id_list.index(SEG_BAND[ji])
                mb = seg_of_pts[ok] == bseg
                if not mb.any():
                    continue
                gb = gated[mb]
                kb = int(np.argmin(gb))
                own_pinch[j["name"]] = min(own_pinch[j["name"]], float(gb[kb]))

    def run_mission(max_step):
        seg_out = []
        worst_clear = math.inf
        worst_raw = math.inf
        worst_rec = None
        qmin = [math.inf] * 6
        qmax = [-math.inf] * 6
        pinch_worst = {j["name"]: math.inf for j in arm.rev}
        j4_length_residual_max = 0.0
        j4_follower_residual_max = 0.0
        j4_overlap_min = math.inf
        j4_stop_margin_min = math.inf
        j4_guide_margin_min = math.inf
        j4_limits_ok = True
        j4_dynamic_sample_count = 0
        clearance_comparison_count = 0
        pinch_evidence_count = {j["name"]: 0 for j in arm.rev}
        for seg in segments:
            qf = states[seg["from"]]
            qt = states[seg["to"]]
            qa = np.array([qf]) if seg["from"] == seg["to"] else sample_segment(qf, qt, max_step)
            seg_worst = math.inf
            seg_where = None
            for k in range(len(qa)):
                q = qa[k]
                for i in range(6):
                    qmin[i] = min(qmin[i], float(q[i]))
                    qmax[i] = max(qmax[i], float(q[i]))
                r = eval_clearance(q)
                clearance_comparison_count += int(r["comparison_counts"]["total"])
                for jn_, n_ in r["pinch_evidence_count"].items():
                    pinch_evidence_count[jn_] += int(n_)
                j4_dynamic_sample_count += 1
                j4_length_residual_max = max(
                    j4_length_residual_max,
                    abs(r["j4_dynamic_exchange_length_residual_mm"]))
                j4_follower_residual_max = max(
                    j4_follower_residual_max,
                    r["j4_follower_closure_residual_mm"])
                j4_overlap_min = min(j4_overlap_min, r["j4_stage_overlap_mm"])
                j4_stop_margin_min = min(j4_stop_margin_min, r["j4_hard_stop_margin_mm"])
                j4_guide_margin_min = min(j4_guide_margin_min,
                                          r["j4_annulus_guide_margin_rad"])
                j4_limits_ok = j4_limits_ok and r["j4_within_hardware_limits"]
                for jn_, v_ in r["pinch"].items():
                    pinch_worst[jn_] = min(pinch_worst[jn_], v_)
                if r["clearance"] < seg_worst:
                    seg_worst = r["clearance"]
                    seg_where = {"sample": int(k), "q": [float(x) for x in q],
                                 "detail": r["detail"], "raw": r["clearance_raw"]}
                if r["clearance"] < worst_clear:
                    worst_clear = r["clearance"]
                    worst_raw = r["clearance_raw"]
                    worst_rec = {"segment": seg["id"], **seg_where}
            seg_out.append({"segment": seg["id"], "from": seg["from"], "to": seg["to"],
                            "purpose": seg["purpose"], "samples": int(len(qa)),
                            "worst_clearance_mm": seg_worst, "worst_where": seg_where})
            note("mission progress: segment %s complete, poses %d, worst %.3f mm"
                 % (seg["id"], len(qa), seg_worst))
        return {"segments": seg_out, "worst_clearance_mm": worst_clear,
                "worst_raw_mm": worst_raw, "worst_record": worst_rec,
                "q_min": qmin, "q_max": qmax, "pinch": pinch_worst,
                "clearance_comparison_count": clearance_comparison_count,
                "pinch_evidence_count": pinch_evidence_count,
                "j4_exact": {
                    "comparison_count": j4_dynamic_sample_count,
                    "max_abs_dynamic_length_residual_mm": j4_length_residual_max,
                    "max_follower_closure_residual_mm": j4_follower_residual_max,
                    "min_stage_overlap_mm": j4_overlap_min,
                    "min_hard_stop_margin_mm": j4_stop_margin_min,
                    "min_annulus_guide_margin_rad": j4_guide_margin_min,
                    "all_samples_within_hardware_limits": bool(j4_limits_ok),
                }}

    note("running mission sweep (nominal step)...")
    # global pose-invariant own-host-of-attachment minimum (constant)
    own_best_global = math.inf
    own_detail_global = None
    for si, v in own_best_seg.items():
        if v < own_best_global:
            own_best_global = v
            own_detail_global = own_detail_seg[si]

    def fold_own_host(seg_worst, seg_where):
        if own_best_global < seg_worst:
            return own_best_global, {"detail": own_detail_global, "raw": None}
        return seg_worst, seg_where

    m_nom = run_mission(MAX_DQ_STEP)
    for s in m_nom["segments"]:
        s["worst_clearance_mm"], s["worst_where"] = fold_own_host(
            s["worst_clearance_mm"], s["worst_where"])
    if own_best_global < m_nom["worst_clearance_mm"]:
        m_nom["worst_clearance_mm"] = own_best_global
        m_nom["worst_record"] = {"segment": own_detail_global["segment"],
                                 "detail": own_detail_global, "raw": None}
    note("mission worst clearance (gated): %.3f mm" % m_nom["worst_clearance_mm"])
    if FAST_MODE:
        # Early-rejection mode evaluates the nominal step only.  It receives no
        # convergence or decision credit; earlier variants are not inherited as
        # V9F convergence evidence.
        m_ref = m_nom
        conv_mm = None
        refinement_factor = 1
        convergence_status = "NOT_EVALUATED_IN_EARLY_REJECTION_MODE"
        note("FAST_MODE: refinement NOT_EVALUATED; result is non-authoritative")
    else:
        note("running mission sweep (2x refinement)...")
        m_ref = run_mission(MAX_DQ_STEP / 2.0)
        for s in m_ref["segments"]:
            s["worst_clearance_mm"], s["worst_where"] = fold_own_host(
                s["worst_clearance_mm"], s["worst_where"])
        if own_best_global < m_ref["worst_clearance_mm"]:
            m_ref["worst_clearance_mm"] = own_best_global
            m_ref["worst_record"] = {"segment": own_detail_global["segment"],
                                     "detail": own_detail_global, "raw": None}
        conv_mm = abs(m_ref["worst_clearance_mm"] - m_nom["worst_clearance_mm"])
        refinement_factor = 2
        convergence_status = "EVALUATED"
        note("refined worst %.3f mm; |delta| %.4f mm"
                   % (m_ref["worst_clearance_mm"], conv_mm))

    key_state_map = [
        ("ARM_STOWED_ONORBIT_C05", "STOW"),
        ("ARM_RELEASE_CLEAR", "RELEASE_CLEAR"),
        ("Q_DEPLOYED_HOME", "HOME"),
        ("ARM_TASK_READY_C06", "TASK_READY"),
        ("PREGRASP", "PREGRASP"),
        ("CONTACT", "PREGRASP"),
        ("CAPTURE_22KG", "PREGRASP"),
        ("POST_CAPTURE_22KG", "PREGRASP"),
        ("PHYSICS_VETO_150KG", "PREGRASP"),
        ("SAFE_RECOVERY_TARGET", "HOME"),
    ]
    key_states_out = []
    for ks, cstate in key_state_map:
        r = eval_clearance(states[cstate])
        clr = r["clearance"]
        det = r["detail"]
        if own_best_global < clr:
            clr = own_best_global
            det = own_detail_global
        key_states_out.append({
            "state_id": ks, "contract_pose": cstate,
            "clearance_mm_gated": clr,
            "clearance_mm_raw": r["clearance_raw"],
            "detail": det,
            "pass": bool(clr >= 0.0),
        })
    n_key_unsafe = sum(1 for k in key_states_out if not k["pass"])
    note("key states: %d unsafe" % n_key_unsafe)

    pinch_out = []
    for ji, j in enumerate(arm.rev):
        v = min(m_nom["pinch"][j["name"]], m_ref["pinch"][j["name"]], own_pinch[j["name"]])
        if math.isinf(v):
            # no cable point of the band segment came within the exactness
            # horizon of the adjacent vendor housings at any mission sample:
            # the margin is bounded below by the horizon, the tube radius and
            # the worst band derate - reported as a lower bound, not Infinity.
            bseg_idx = seg_id_list.index(SEG_BAND[ji])
            pts_b = P_A0[H_SEG == bseg_idx]
            hosts_b = H_HOST[H_SEG == bseg_idx]
            band_derate = 0.0
            for hi_, h_ in enumerate(HOSTS):
                if not (hosts_b == hi_).any():
                    continue
                Pb = pts_b[hosts_b == hi_]
                for jup in upstream[h_]:
                    j2 = arm.rev[jup]
                    o2, a2 = arm.joint_axis_world(j2, T0)
                    vv = Pb - o2
                    dd = np.sqrt(((vv - np.outer(vv @ a2, a2)) ** 2).sum(1))
                    band_derate += DQ_TOTAL * float(dd.max())
            lb = EXACT_HORIZON - BUNDLE_R - (band_derate + D_STATIC)
            pinch_out.append({"joint": j["name"], "band_segment": SEG_BAND[ji],
                              "pinch_margin_mm_gated": lb,
                              "margin_is_horizon_lower_bound": True,
                              "note": "no band cable point within %.0f mm of %s/%s housings at any mission sample"
                                      % (EXACT_HORIZON, j["parent"], j["child"]),
                              "pass": bool(lb >= 0.0)})
        else:
            pinch_out.append({"joint": j["name"], "band_segment": SEG_BAND[ji],
                              "pinch_margin_mm_gated": v,
                              "margin_is_horizon_lower_bound": False,
                              "pass": bool(v >= 0.0)})
    pinch_worst = min(p["pinch_margin_mm_gated"] for p in pinch_out)
    note("pinch worst: %.3f mm" % pinch_worst)

    # ---- take-up / axial / travel / thermal / torque -----------------------------
    qmin, qmax = m_ref["q_min"], m_ref["q_max"]
    takeup_out = []
    for sid, jn, R_i, cap in seg_takeup:
        ji = [i for i, j in enumerate(arm.rev) if j["name"] == jn][0]
        rng_traj = qmax[ji] - qmin[ji]
        rng_tube = rng_traj + 2 * DQ_TOTAL
        demand = R_i * rng_tube
        dL_thermal = ALPHA_AL * DELTA_T_K * seg_len[sid]
        margin = cap - demand - dL_thermal
        demand_full = R_i * (jrange[ji] + 2 * DQ_TOTAL) + dL_thermal
        takeup_out.append({
            "segment": sid, "joint": jn, "loop_radius_mm": R_i, "capacity_mm": cap,
            "mission_joint_range_rad": rng_traj, "tube_range_rad": rng_tube,
            "take_up_demand_mm": demand, "thermal_length_derate_mm": dL_thermal,
            "margin_mm": margin,
            "margin_full_hardware_range_mm": cap - demand_full,
            "pass": bool(margin >= 0.0),
        })
    ext_total = sum(t["take_up_demand_mm"] for t in takeup_out)
    cap_total = sum(t["capacity_mm"] for t in takeup_out)

    q3_mid = 0.5 * (arm.rev[2]["lo"] + arm.rev[2]["hi"])
    travel_dem = 0.5 * J3_SADDLE_R * (max(abs(qmax[2] - q3_mid), abs(qmin[2] - q3_mid)) + DQ_TOTAL)
    travel_margin = CARRIER_HALF - travel_dem
    travel_dem_full = 0.5 * J3_SADDLE_R * (0.5 * jrange[2] + DQ_TOTAL)
    travel_margin_full = CARRIER_HALF - travel_dem_full

    # V9F J4 chainless trombone/follower screens.  The 185 deg guide is a
    # candidate physical coverage value, not a new Owner/TMG-2 acceptance rule.
    j4_mission_q_min = qmin[3]
    j4_mission_q_max = qmax[3]
    j4_mission_travel_demand = J4_CARRIER_GAIN_MM_PER_RAD * (
        (j4_mission_q_max-j4_mission_q_min) + 2.0*DQ_TOTAL)
    j4_full_travel_demand = J4_CARRIER_GAIN_MM_PER_RAD*(J4_Q_MAX_RAD-J4_Q_MIN_RAD)
    j4_mission_travel_margin = J4_TROMBONE_PHYSICAL_TRAVEL_MM-j4_mission_travel_demand
    j4_full_travel_margin = J4_TROMBONE_PHYSICAL_TRAVEL_MM-j4_full_travel_demand
    j4_beta_mission_nominal = J4_ANNULUS_SEED_RAD + (J4_Q_MAX_RAD-j4_mission_q_min)
    j4_beta_mission_tracking = j4_beta_mission_nominal + DQ_TOTAL
    j4_beta_full = J4_ANNULUS_SEED_RAD + (J4_Q_MAX_RAD-J4_Q_MIN_RAD)
    j4_guide_margin_nominal = J4_ANNULUS_GUIDE_COVERAGE_RAD-j4_beta_mission_nominal
    j4_guide_margin_tracking = J4_ANNULUS_GUIDE_COVERAGE_RAD-j4_beta_mission_tracking
    j4_guide_margin_full = J4_ANNULUS_GUIDE_COVERAGE_RAD-j4_beta_full
    j4_x_at_mission_high_tube = (J4_CARRIER_X_MID_MM-
        J4_CARRIER_GAIN_MM_PER_RAD*((j4_mission_q_max+DQ_TOTAL)-J4_Q_MID_RAD))
    j4_leg_max_mission_tube = J4_X_FIXED-j4_x_at_mission_high_tube
    j4_overlap_mission_tube = (
        (J4_TELESCOPE_STAGE_COUNT*J4_TELESCOPE_STAGE_LENGTH_MM-j4_leg_max_mission_tube)
        /(J4_TELESCOPE_STAGE_COUNT-1.0))
    j4_x_at_full_high = (J4_CARRIER_X_MID_MM-
        J4_CARRIER_GAIN_MM_PER_RAD*(J4_Q_MAX_RAD-J4_Q_MID_RAD))
    j4_overlap_full = (
        (J4_TELESCOPE_STAGE_COUNT*J4_TELESCOPE_STAGE_LENGTH_MM-
         (J4_X_FIXED-j4_x_at_full_high))/(J4_TELESCOPE_STAGE_COUNT-1.0))
    def _j4_x(q4_value):
        return (J4_CARRIER_X_MID_MM-
                J4_CARRIER_GAIN_MM_PER_RAD*(q4_value-J4_Q_MID_RAD))
    j4_x_mission_tube = [_j4_x(j4_mission_q_min-DQ_TOTAL),
                         _j4_x(j4_mission_q_max+DQ_TOTAL)]
    j4_x_full_limits = [_j4_x(J4_Q_MIN_RAD), _j4_x(J4_Q_MAX_RAD)]
    j4_mission_stop_margin = min(
        min(x-J4_STOP_MIN_MM, J4_STOP_MAX_MM-x) for x in j4_x_mission_tube)
    j4_full_stop_margin = min(
        min(x-J4_STOP_MIN_MM, J4_STOP_MAX_MM-x) for x in j4_x_full_limits)
    j4_exact = m_ref["j4_exact"]

    torque_out = []
    _R = {"V1": (0.060, 0.050, 0.063, 0.050, 0.050, 0.050),
          "V2": (0.060, 0.055, 0.065, 0.055, 0.055, 0.055),
          "V3": (0.060, 0.055, 0.065, 0.055, 0.055, 0.055),
          "V4": (0.060, 0.055, 0.065, 0.055, 0.055, 0.055),
          "V5": (0.060, 0.055, 0.065, 0.055, 0.055, 0.055),
          "V6": (0.060, 0.055, 0.065, 0.055, 0.055, 0.055),
          "V7": (0.060, 0.055, 0.065, 0.055, 0.055, 0.055),
          "V8": (0.066, 0.055, 0.065, 0.055, 0.055, 0.055),
          "V9": (0.066, 0.055, 0.065, 0.0550363516, 0.055, 0.055),
          "V9F": (0.066, 0.055, 0.065, 0.055, 0.055, 0.055),
          "VF": (0.060, 0.055, 0.065, 0.055, 0.055, 0.055)}[VARIANT]
    # V7 shortened the J1 annular coil to sweep -420 deg (SEG-01 corner fix);
    # the stored wrap angle feeds the capstan normal force in the torque model.
    _j1_wrap_deg = 420.0 if VARIANT in ("V7", "V8", "V9", "V9F", "VF") else 432.0
    _j4_wrap_deg = 185.0 if VARIANT == "V9F" else (180.0 if VARIANT == "V9" else 315.0)
    loop_meta = [("joint1", _R[0], math.radians(_j1_wrap_deg)),
                 ("joint2", _R[1], math.radians(250.0)),
                 ("joint3", _R[2], math.radians(200.0)),
                 ("joint4", _R[3], math.radians(_j4_wrap_deg)),
                 ("joint5", _R[4], math.radians(185.0)),
                 ("joint6", _R[5], math.radians(630.0))]
    for ji, (jn, R_i, Phi) in enumerate(loop_meta):
        taus = []
        for EI in (EI_LOWER, EI_UPPER):
            t_bend = EI / R_i
            N = EI / (R_i * R_i) * Phi
            taus.append(t_bend + MU_MAX * N * R_i)
        budget = jeffort[ji]
        torque_out.append({
            "joint": jn, "loop_radius_m": R_i, "stored_wrap_rad": Phi,
            "tau_min_Nm": taus[0], "tau_max_Nm": taus[1],
            "actuator_effort_budget_Nm": budget,
            "worst_fraction_of_budget": taus[1] / budget,
            "margin_Nm": budget - taus[1],
            "known_component_screen_pass": bool(taus[1] <= budget),
            "status": "KNOWN_COMPONENT_SCREEN_ONLY",
            "authority": "PROVISIONAL_DERIVED (EI bundle [1.7e-4, 2.1e-2] N m^2 candidate; "
                         "mu 0.20 P10 upper); installed-bundle torsion is excluded here and UNKNOWN",
        })

    # ---- full-range spot check ------------------------------------------------
    if FAST_MODE:
        # ODR-54: Gate A target is mission-rated coverage (E_MISSION subset of
        # E_ROUTE_C); full hardware range is NOT required.  The full-range spot
        # check is skipped in FAST_MODE and the V1 conclusion (full-range not
        # reachable, documented negative result) is carried as a reference.
        fr_worst = None
        fr_rec = {"scope": "SKIPPED_IN_FAST_MODE",
                  "basis": ("ODR-54 mission-rated target does not require full hardware "
                            "range; V1 full-range documented negative result and V3 "
                            "mission-envelope conclusion are carried as reference (V7 "
                            "harness geometry changes are confined to guide hardware, "
                            "which the full-range spot check does not re-scope)")}
        note("FAST_MODE: full-range spot check skipped (ODR-54 mission-rated target)")
    else:
        note("running full-range spot check...")
        fr_worst = math.inf
        fr_rec = None
        q_home = states["HOME"]
        for ji, j in enumerate(arm.rev):
            n = max(2, int(math.ceil((j["hi"] - j["lo"]) / math.radians(2.0))))
            for qv in np.linspace(j["lo"], j["hi"], n + 1):
                q = list(q_home)
                q[ji] = float(qv)
                r = eval_clearance(q)
                if r["clearance"] < fr_worst:
                    fr_worst = r["clearance"]
                    fr_rec = {"mode": "per_joint_sweep", "joint": j["name"],
                              "q": [float(x) for x in q], "detail": r["detail"]}
        import itertools
        for bits in itertools.product([0, 1], repeat=6):
            q = [arm.rev[i]["lo"] if bits[i] == 0 else arm.rev[i]["hi"] for i in range(6)]
            r = eval_clearance(q)
            if r["clearance"] < fr_worst:
                fr_worst = r["clearance"]
                fr_rec = {"mode": "limit_corner", "bits": list(bits),
                          "q": [float(x) for x in q], "detail": r["detail"]}
        note("full-range spot worst (gated): %.3f mm" % fr_worst)

    # ---- RC hardware cross-clearance -------------------------------------------
    # The key-state fast-check is an early-rejection instrument.  Running the
    # expensive all-hardware cross check after a key-state failure adds no design
    # decision value and formerly consumed tens of minutes per rejected seed.
    # It is therefore deliberately NOT_EVALUATED in FAST_MODE.  The authoritative
    # full mission run always executes this block before any release decision.
    rc_cross_evaluated = not FAST_MODE
    rc_worst = None
    rc_rec = None
    rc_evals = 0
    if FAST_MODE:
        rc_rec = {"scope": "NOT_EVALUATED_IN_KEY_STATE_FAST_CHECK",
                  "basis": "early-rejection filter; mandatory in full mission sweep"}
        note("FAST_MODE: RC hardware cross-clearance not evaluated (mandatory in full run)")
    else:
        note("running RC hardware cross-clearance...")
        rc_worst = math.inf
        mission_q_samples = []
        for seg in segments:
            qf, qt = states[seg["from"]], states[seg["to"]]
            qa = np.array([qf]) if seg["from"] == seg["to"] else sample_segment(
                qf, qt, math.radians(1.0))
            for q in qa:
                mission_q_samples.append(q)
        mission_q_samples = [np.array(q) for q in
                             np.unique(np.round(np.array(mission_q_samples), 6), axis=0)]
        for q in mission_q_samples:
            base = _base_kinematics(q)
            inv_TS = base["inv_TS"]
            aabb_S_x = base["vendor_aabb_S"]
            rc_pose_x, _rc_inv_unused, _rc_aabb_unused = _rc_pose_context(
                base, q, require_inverse=False, require_aabb=False)
            for pname, phost, pkind, motion_class, fld_part in rc_parts:
                unique_v0, multiplicity = rc_v0_unique[pname]
                P = xform_batch(rc_pose_x[pname], unique_v0)
                if len(P) == 0 or not np.isfinite(P).all():
                    raise RuntimeError("non-finite or empty RC cross-check sample group")
                pmin, pmax = P.min(axis=0), P.max(axis=0)
                relative_own_host_motion = (
                    pname in J3_CARRIAGE_PARTS or
                    motion_class in ("ONE_THIRD_TRAVEL", "TWO_THIRDS_TRAVEL",
                                     "FULL_TRAVEL"))
                for lname, fld in vendor_fields.items():
                    # Fixed brackets may retain their frozen own-host mounting
                    # exclusion.  Every part that moves relative to its host is
                    # checked against that host at every pose.
                    if lname == phost and not relative_own_host_motion:
                        continue
                    bmn, bmx = aabb_S_x[lname]
                    candidate = _conservative_aabb_candidates(
                        P, pmin, pmax, bmn, bmx, fld.D)
                    if not candidate.any():
                        continue
                    candidate_idx = np.flatnonzero(candidate)
                    Pl = xform_batch(inv_TS[lname], P[candidate_idx])
                    c = fld.signed_clearance_batch(Pl, RC_SAMPLE_ALLOW)
                    ok = ~np.isnan(c)
                    rc_evals += int(multiplicity[candidate_idx[ok]].sum())
                    if ok.any():
                        k = int(np.argmin(c[ok]))
                        if float(c[ok][k]) < rc_worst:
                            rc_worst = float(c[ok][k])
                            rc_rec = {"rc_part": pname, "rc_host": phost,
                                      "motion_class": motion_class,
                                      "field": "vendor:" + lname,
                                      "q": [float(x) for x in q]}
                candidate = _conservative_aabb_candidates(
                    P, pmin, pmax, solar_field.bmin, solar_field.bmax, solar_field.D)
                if candidate.any():
                    candidate_idx = np.flatnonzero(candidate)
                    c = solar_field.signed_clearance_batch(
                        P[candidate_idx], RC_SAMPLE_ALLOW)
                    ok = ~np.isnan(c)
                    rc_evals += int(multiplicity[candidate_idx[ok]].sum())
                    if ok.any():
                        k = int(np.argmin(c[ok]))
                        if float(c[ok][k]) < rc_worst:
                            rc_worst = float(c[ok][k])
                            rc_rec = {"rc_part": pname, "rc_host": phost,
                                      "motion_class": motion_class,
                                      "field": "solar", "q": [float(x) for x in q]}
                candidate = _conservative_aabb_candidates(
                    P, pmin, pmax, BUS_MIN, BUS_MAX, bus_field.D)
                if candidate.any():
                    candidate_idx = np.flatnonzero(candidate)
                    c = bus_field.signed_clearance_batch(
                        P[candidate_idx], RC_SAMPLE_ALLOW)
                    ok = ~np.isnan(c)
                    rc_evals += int(multiplicity[candidate_idx[ok]].sum())
                    if ok.any():
                        k = int(np.argmin(c[ok]))
                        if float(c[ok][k]) < rc_worst:
                            rc_worst = float(c[ok][k])
                            rc_rec = {"rc_part": pname, "rc_host": phost,
                                      "motion_class": motion_class,
                                      "field": "bus", "q": [float(x) for x in q]}
        note("RC cross-clearance worst %.3f mm over %d evals" % (rc_worst, rc_evals))

    # ---- D3 open-sector two-layer retention ------------------------------------
    d3_control = center.get("d3_open_sector_retention")
    clamp_by_id = {c["clamp_id"]: c for c in clamp_check}
    if d3_control:
        d3_ids = list(d3_control.get("required_retainer_ids", []))
        d3_retainer_checks = [clamp_by_id.get(cid) for cid in d3_ids]
        d3_retainers_present = all(c is not None for c in d3_retainer_checks)
        d3_retainers_pass = d3_retainers_present and all(c["pass"] for c in d3_retainer_checks)
        d3_max_span = max(float(x["free_span_mm"]) for x in d3_control["open_passages"])
        d3_limit = float(d3_control["p13_max_spacing_mm"])
        d3_span_pass = d3_max_span <= d3_limit + 1e-12
        d3_gate_pass = bool(d3_retainers_pass and d3_span_pass)
    else:
        d3_ids = []
        d3_retainer_checks = []
        d3_retainers_present = False
        d3_retainers_pass = False
        d3_max_span = None
        d3_limit = 150.0
        d3_span_pass = False
        d3_gate_pass = False

    # ---- margins, verdict ------------------------------------------------------
    clearance_mission = m_ref["worst_clearance_mm"]
    bend_margin = min(bend_analytic, menger_overall) - BEND_LIMIT
    takeup_worst = min(t["margin_mm"] for t in takeup_out)
    torque_worst_frac = max(t["worst_fraction_of_budget"] for t in torque_out)

    def _all_finite(values):
        return all(math.isfinite(float(v)) for v in values)

    clearance_comparison_count = (
        int(m_ref["clearance_comparison_count"])+own_clearance_comparison_count)
    pinch_comparison_by_joint = {
        j["name"]: int(m_ref["pinch_evidence_count"].get(j["name"], 0))
        for j in arm.rev}
    pinch_comparison_count = sum(pinch_comparison_by_joint.values())
    bend_comparison_count = (bend_analytic_comparison_count+
                             bend_menger_comparison_count)
    takeup_comparison_count = len(takeup_out)
    kinematic_integrity_comparison_count = (
        len(fk_val)+len(interface_rules)+len(junction_checks))
    kinematic_integrity_finite = _all_finite(
        [x["max_abs_residual_row0"] for x in fk_val]
        + [x["tangent_mismatch_deg"] for x in junction_checks])
    j4_exact_finite = _all_finite([
        j4_exact["max_abs_dynamic_length_residual_mm"],
        j4_exact["max_follower_closure_residual_mm"],
        j4_exact["min_stage_overlap_mm"],
        j4_exact["min_hard_stop_margin_mm"],
        j4_exact["min_annulus_guide_margin_rad"],
        j4_mission_travel_demand, j4_full_travel_demand,
        j4_overlap_mission_tube, j4_overlap_full,
        j4_mission_stop_margin, j4_full_stop_margin,
        j4_guide_margin_tracking, j4_guide_margin_full])

    predicates = {
        "kinematic_and_interface_integrity": {
            "comparison_count": kinematic_integrity_comparison_count,
            "fk_pass": fk_ok,
            "interface_exception_audit_pass": interface_exception_audit_pass,
            "junction_tangent_max_deg": junction_max_deg,
            "finite": kinematic_integrity_finite,
            "pass": bool(kinematic_integrity_comparison_count > 0 and fk_ok and
                         interface_exception_audit_pass and
                         junction_max_deg <= 3.0+1e-12 and
                         kinematic_integrity_finite),
        },
        "clearance": {"worst_mm_gated": clearance_mission,
                      "worst_mm_raw": m_ref["worst_raw_mm"],
                      "comparison_count": clearance_comparison_count,
                      "pass": bool(clearance_comparison_count > 0 and
                                   math.isfinite(clearance_mission) and
                                   clearance_mission >= 0.0)},
        "bend_radius": {"min_mm": min(bend_analytic, menger_overall),
                        "limit_mm": BEND_LIMIT, "margin_mm": bend_margin,
                        "comparison_count": bend_comparison_count,
                        "finite": bool(math.isfinite(min(bend_analytic, menger_overall))),
                        "pass": bool(bend_comparison_count > 0 and
                                     math.isfinite(bend_margin) and bend_margin >= 0.0),
                        "note": "finite analytic and sampled curvature evidence required"},
        "pinch": {"worst_mm_gated": pinch_worst,
                  "comparison_count": pinch_comparison_count,
                  "comparison_count_by_joint": pinch_comparison_by_joint,
                  "pass": bool(pinch_comparison_count > 0 and
                               all(n > 0 for n in pinch_comparison_by_joint.values()) and
                               math.isfinite(pinch_worst) and pinch_worst >= 0.0)},
        "take_up": {"worst_margin_mm": takeup_worst,
                    "comparison_count": takeup_comparison_count,
                    "pass": bool(takeup_comparison_count > 0 and
                                 math.isfinite(takeup_worst) and takeup_worst >= 0.0)},
        "axial_extension": {"total_demand_mm": ext_total, "total_capacity_mm": cap_total,
                             "margin_mm": cap_total - ext_total,
                             "comparison_count": takeup_comparison_count,
                             "pass": bool(takeup_comparison_count > 0 and
                                          _all_finite([ext_total, cap_total,
                                                       cap_total-ext_total]) and
                                          cap_total - ext_total >= 0.0)},
        "j3_carrier_travel": {"demand_mm": travel_dem, "hard_stop_half_stroke_mm": CARRIER_HALF,
                            "margin_mm": travel_margin,
                            "margin_full_range_mm": travel_margin_full,
                            "comparison_count": 1,
                            "pass": bool(_all_finite([travel_dem, travel_margin,
                                                      travel_margin_full]) and
                                         travel_margin >= 0.0)},
        "j4_exact_dynamic_closure": {
            "comparison_count": int(j4_exact["comparison_count"]),
            "max_abs_length_residual_mm": j4_exact["max_abs_dynamic_length_residual_mm"],
            "length_tolerance_mm": J4_DYNAMIC_LENGTH_TOL_MM,
            "max_follower_fk_residual_mm": j4_exact["max_follower_closure_residual_mm"],
            "follower_tolerance_mm": J4_FOLLOWER_CLOSURE_TOL_MM,
            "finite": j4_exact_finite,
            "pass": bool(j4_exact["comparison_count"] > 0 and j4_exact_finite and
                j4_exact["max_abs_dynamic_length_residual_mm"] <= J4_DYNAMIC_LENGTH_TOL_MM
                and j4_exact["max_follower_closure_residual_mm"] <= J4_FOLLOWER_CLOSURE_TOL_MM),
        },
        "j4_trombone_travel_and_overlap": {
            "comparison_count": int(j4_exact["comparison_count"]),
            "mission_tracking_tube_demand_mm": j4_mission_travel_demand,
            "physical_travel_mm": J4_TROMBONE_PHYSICAL_TRAVEL_MM,
            "mission_margin_mm": j4_mission_travel_margin,
            "full_hardware_demand_mm": j4_full_travel_demand,
            "full_hardware_margin_mm": j4_full_travel_margin,
            "mission_tracking_tube_overlap_mm": j4_overlap_mission_tube,
            "full_hardware_min_overlap_mm": j4_overlap_full,
            "source_min_overlap_rule_mm": J4_TELESCOPE_MIN_OVERLAP_MM,
            "mission_sample_min_hard_stop_margin_mm": j4_exact["min_hard_stop_margin_mm"],
            "mission_tracking_tube_hard_stop_margin_mm": j4_mission_stop_margin,
            "full_hardware_hard_stop_margin_mm": j4_full_stop_margin,
            "all_samples_within_q4_limits": j4_exact["all_samples_within_hardware_limits"],
            "finite": j4_exact_finite,
            "pass": bool(j4_exact["comparison_count"] > 0 and j4_exact_finite and
                         j4_mission_travel_margin >= 0.0 and
                         j4_full_travel_margin >= 0.0 and
                         j4_overlap_mission_tube >= J4_TELESCOPE_MIN_OVERLAP_MM and
                         j4_overlap_full >= J4_TELESCOPE_MIN_OVERLAP_MM and
                         j4_exact["min_hard_stop_margin_mm"] >= 0.0 and
                         j4_mission_stop_margin >= 0.0 and j4_full_stop_margin >= 0.0 and
                         j4_exact["all_samples_within_hardware_limits"]),
        },
        "j4_annular_follower_mission_coverage": {
            "comparison_count": int(j4_exact["comparison_count"]),
            "physical_candidate_coverage_deg": math.degrees(J4_ANNULUS_GUIDE_COVERAGE_RAD),
            "mission_nominal_required_deg": math.degrees(j4_beta_mission_nominal),
            "mission_nominal_margin_deg": math.degrees(j4_guide_margin_nominal),
            "mission_plus_tracking_required_deg": math.degrees(j4_beta_mission_tracking),
            "mission_plus_tracking_margin_deg": math.degrees(j4_guide_margin_tracking),
            "full_hardware_required_deg": math.degrees(j4_beta_full),
            "full_hardware_margin_deg": math.degrees(j4_guide_margin_full),
            "full_hardware_disposition": "DEFERRED_HOLD",
            "acceptance_authority": "CANDIDATE_GEOMETRY_SCREEN_ONLY__NO_ODR59_OWNER_RULE",
            "finite": j4_exact_finite,
            "pass": bool(j4_exact["comparison_count"] > 0 and j4_exact_finite and
                         j4_guide_margin_tracking >= 0.0),
        },
        "resistance_torque": {"worst_fraction_of_budget": torque_worst_frac,
                              "comparison_count": 0,
                              "known_component_comparison_count": len(torque_out),
                              "known_component_screen": "KNOWN_COMPONENT_SCREEN_ONLY",
                              "known_component_screen_pass": bool(torque_worst_frac <= 1.0),
                              "status": "HOLD_UNKNOWN_TORSION",
                              "pass": False,
                              "unknown_component": "installed-bundle torsion restoring moment (P08) UNKNOWN - fail-closed, not zero-filled"},
        "thermal_tolerance": {"delta_T_K": DELTA_T_K, "positional_derate_mm": D_THERM,
                              "length_derate_total_mm": sum(t["thermal_length_derate_mm"] for t in takeup_out),
                              "comparison_count": takeup_comparison_count,
                              "pass": bool(takeup_comparison_count > 0 and _all_finite(
                                  [t["thermal_length_derate_mm"] for t in takeup_out])),
                              "note": "thermal derates folded into clearance/take-up margins"},
        "clamp_and_guide_support_bore_axis": {
            "applicable_interfaces": len(clamp_applicable),
            "comparison_count": len(clamp_applicable),
            "max_continuous_distance_upper_bound_mm": clamp_max_res,
            "max_axis_tangent_angle_deg": clamp_max_angle,
            "pass": clamp_gate_pass,
            "note": "individual interface budgets and <=3 deg tangent rule; max-only INFO is forbidden",
        },
        "d3_open_sector_retention": {
            "control_present": bool(d3_control),
            "comparison_count": len(d3_retainer_checks),
            "required_retainer_ids": d3_ids,
            "retainers_present": d3_retainers_present,
            "retainers_pass_bore_axis_gate": d3_retainers_pass,
            "max_free_span_mm": d3_max_span,
            "p13_max_spacing_mm": d3_limit,
            "span_pass": d3_span_pass,
            "pass": d3_gate_pass,
            "note": "both physical helix passages through the 100..190 deg relief must be retained",
        },
        "rc_hardware_cross_clearance": {
            "evaluated": rc_cross_evaluated,
            "comparison_count": rc_evals,
            "worst_mm": rc_worst,
            "pass": bool(rc_cross_evaluated and rc_evals > 0 and
                         rc_worst is not None and math.isfinite(rc_worst) and
                         rc_worst >= 0.0),
            "note": ("mandatory RC parts vs vendor/solar/bus gate in full mission run; "
                     "NOT_EVALUATED is fail-closed and is permitted only in the non-authoritative "
                     "key-state early-rejection instrument"),
        },
    }

    empty_predicate_names = sorted(
        name for name, pred in predicates.items()
        if int(pred.get("comparison_count", 0)) <= 0)
    empty_comparison_set_count = len(empty_predicate_names)
    all_pred_pass = all(p["pass"] for p in predicates.values())
    geometry_predicate_names = [k for k in predicates if k != "resistance_torque"]
    mission_geometry_pass = ((not FAST_MODE) and
                             all(predicates[k]["pass"] for k in geometry_predicate_names)
                             and n_key_unsafe == 0)
    fr_spot_pass = ((fr_worst is not None) and math.isfinite(fr_worst)
                    and fr_worst >= 0.0)
    full_hw_pass = False  # V9F annular guide full-range coverage is an explicit HOLD.
    verdict = ("GEOMETRY_SIMULATION_READY_WITH_QUALIFICATION_HOLDS__OWNER_GATE_PENDING"
               if mission_geometry_pass
               else "BLOCKED_BY_GEOMETRY_OR_INTERFACE_PREDICATE")
    execution_mode = ("EARLY_REJECTION_ONLY" if FAST_MODE
                      else "FULL_CANDIDATE_EVALUATION")
    authoritative = not FAST_MODE

    sweep = {
        "schema": "ROUTE_C_EXACT_SWEEP_%s" % VARIANT,
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "stage": "RC-4_EXACT_FULL_TRAJECTORY_VERIFICATION",
        "execution_mode": execution_mode,
        "authoritative": authoritative,
        "authority_scope": ("NON_AUTHORITATIVE_EARLY_REJECTION"
                            if FAST_MODE else
                            "CANDIDATE_GEOMETRY_EVALUATOR_ONLY__NO_RELEASE_CREDIT"),
        "authority_rules": {"allowed": ["DESIGN_CANDIDATE", "PROVISIONAL_DERIVED",
                                        "BOUNDED_DATASHEET_RANGE"],
                            "forbidden": ["MEASURED", "AS_BUILT", "FLIGHT_QUALIFIED"]},
        "input_pins": pins,
        "fk_validation": {"checks": fk_val, "pass": fk_ok},
        "kinematic_attachment_model": {
            "rule": "P(q) = T_host(q) @ inv(T_host(0)) @ P(q=0) in A0; frozen mount to S",
            "j1_coil_axisymmetry_offset_mm": d_off1,
            "j6_helix_axisymmetry": {"parallelism": d_par, "axis_offset_mm": d_off6},
            "semi_captive_dual_attachment": "crossing sections evaluated under both parent and child attachment; minimum clearance reported",
            "own_segment_rc_contact": "intended contact with the guide/channel/clamp hardware serving a segment is excluded per SEG_INTENDED_PARTS (product-structure semantics); all other RC contact is gated",
            "adjacent_interface_contact": {
                "rule": "fourfold exact segment + section + cumulative arclength + explicit station/clamp/bore-axis predicate; legacy Euclidean-only exclusion forbidden",
                "maximum_arclength_window_mm": J4_INTERFACE_ARCLENGTH_WINDOW_MM,
                "rule_count": len(interface_rules),
                "qualification_scope": "clearance exclusion only; contact pressure, wear, fretting and cable escape remain declared qualification holds"
            },
            "j4_v9f_exact_law": {
                "topology": "four rigid nested telescope stages + rigid translating U + exact negative R55 annular cable arc + link4 FK follower/downstream",
                "solid_motion_classes": ["FIXED_LINK3", "ONE_THIRD_TRAVEL",
                                         "TWO_THIRDS_TRAVEL", "FULL_TRAVEL",
                                         "FOLLOWER_LINK4", "FIXED_LINK4"],
                "prohibited_models_removed": ["PROPORTIONAL_SOLID_SCALING",
                                               "BEZIER_RETURN_LEG",
                                               "DISTRIBUTED_CARRIER_DEFORMATION"],
            },
        },
        "tracking_tube_candidate": {
            "id": "MISSION_TRACKING_TUBE_CANDIDATE",
            "dq_tracking_rad": DQ_TRACK, "dq_encoder_calibration_rad": DQ_ENCCAL,
            "dq_total_rad_per_joint": DQ_TOTAL,
            "d_install_mm": D_INSTALL, "d_harness_geom_mm": D_GEOM,
            "d_thermal_mm": D_THERM, "d_mesh_mm": D_MESH,
            "d_static_total_mm": D_STATIC,
            "authority": "DESIGN_CANDIDATE - no B601 servo/encoder authority exists in the program; replacement by measured data is a registered downstream hold",
            "thermal_model": {"alpha_aluminum_per_K": ALPHA_AL, "delta_T_K": DELTA_T_K},
        },
        "centerline_verification": {
            "points": int(len(P_A0)), "sampling_ds_mm": SAMPLE_DS,
            "segments": seg_records,
            "bend_radius_analytic_mm": bend_analytic,
            "bend_radius_menger_mm": menger_overall,
            "junction_tangent_continuity": {
                "rule": "A1 build rule: tangent mismatch <= 3 deg at section junctions",
                "max_mismatch_deg": junction_max_deg,
                "checks": junction_checks,
            },
            "clamp_colocation_max_residual_mm": clamp_max_res,
            "clamp_axis_tangent_max_angle_deg": clamp_max_angle,
            "clamp_and_guide_support_gate_pass": clamp_gate_pass,
            "clamp_colocation_note": ("per-interface conservative continuous-distance upper "
                                      "bound plus retained-radius and installation allowance must "
                                      "fit the registered bore; CAD bore axis to centerline tangent "
                                      "must be <=3 deg; non-bore connector/saddle rows are N/A"),
            "clamp_checks": clamp_check,
        },
        "mission_sweep": {
            "sampling": {"max_joint_step_rad_nominal": MAX_DQ_STEP,
                         "refinement_factor": refinement_factor,
                         "convergence_status": convergence_status,
                         "convergence_abs_mm": conv_mm,
                         "total_samples_nominal": sum(s["samples"] for s in m_nom["segments"]),
                         "total_samples_refined": sum(s["samples"] for s in m_ref["segments"])},
            "per_segment_nominal": m_nom["segments"],
            "per_segment_refined": m_ref["segments"],
            "worst_clearance_mm_gated": clearance_mission,
            "worst_raw_mm": m_ref["worst_raw_mm"],
            "worst_record": m_ref["worst_record"],
            "q_min": qmin, "q_max": qmax,
        },
        "key_states": key_states_out,
        "pinch": pinch_out,
        "take_up": takeup_out,
        "axial_extension": {"total_demand_mm": ext_total, "total_capacity_mm": cap_total,
                            "margin_mm": cap_total - ext_total},
        "j3_carrier_travel": {"q3_mid_datum_rad": q3_mid, "demand_mm": travel_dem,
                              "margin_mm": travel_margin,
                              "margin_full_range_mm": travel_margin_full},
        "j4_trombone_annular_follower": {
            "mission_exact_metrics": j4_exact,
            "mission_tracking_tube_travel_demand_mm": j4_mission_travel_demand,
            "physical_travel_mm": J4_TROMBONE_PHYSICAL_TRAVEL_MM,
            "full_hardware_travel_demand_mm": j4_full_travel_demand,
            "mission_tracking_tube_min_overlap_mm": j4_overlap_mission_tube,
            "full_hardware_min_overlap_mm": j4_overlap_full,
            "annulus_guide_mission_nominal_margin_deg": math.degrees(j4_guide_margin_nominal),
            "annulus_guide_mission_tracking_margin_deg": math.degrees(j4_guide_margin_tracking),
            "annulus_guide_full_hardware_margin_deg": math.degrees(j4_guide_margin_full),
            "full_hardware_guide_disposition": "DEFERRED_HOLD",
        },
        "resistance_torque": torque_out,
        "rc_hardware_cross_clearance": {"evaluated": rc_cross_evaluated,
                                        "worst_mm": rc_worst, "evaluations": rc_evals,
                                        "record": rc_rec,
                                        "sampling_allowance_mm": RC_SAMPLE_ALLOW},
        "full_range_spot_check": {"worst_clearance_mm_gated": fr_worst, "record": fr_rec,
                                  "scope": "diagnostic per-joint sweeps + 64 limit corners; cannot clear the declared V9F full-range annular-guide HOLD"},
        "predicates": predicates,
        "verdict_inputs": {"all_predicates_pass_including_qualification_holds": all_pred_pass,
                            "mission_geometry_predicates_pass": mission_geometry_pass,
                            "empty_predicate_names": empty_predicate_names,
                            "empty_comparison_set_count": empty_comparison_set_count,
                            "overall_resistance_torque": "HOLD_UNKNOWN_TORSION",
                            "owner_numeric_acceptance_rule": "ABSENT_ODR59_PENDING",
                            "mandatory_key_states_unsafe": n_key_unsafe,
                           "full_range_spot_pass": fr_spot_pass},
        "verdict": verdict,
        "log": log,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    if FAST_OUTPUT_TAG:
        sweep["execution_metadata"] = {
            "fast_output_tag": FAST_OUTPUT_TAG,
            "scope": "OUTPUT_PATH_ISOLATION_ONLY__NOT_A_SCIENTIFIC_INPUT",
            "output_basenames": [os.path.basename(OUT_SWEEP),
                                 os.path.basename(OUT_LEDGER),
                                 os.path.basename(OUT_GATE)],
        }
    with open(OUT_SWEEP, "w", encoding="utf-8", newline="\n") as f:
        f.write(jdump(sweep))

    rows = []
    rows.append(["clearance_mission_worst_gated", "mm", clearance_mission, ">= 0",
                 "PASS" if clearance_mission >= 0 else "FAIL",
                 "cable tube surface vs gated obstacles after tracking-tube derate"])
    rows.append(["clearance_key_states_worst_gated", "mm",
                 min(k["clearance_mm_gated"] for k in key_states_out), ">= 0",
                 "PASS" if n_key_unsafe == 0 else "FAIL", "10 mandatory key states"])
    rows.append(["pinch_worst_gated", "mm", pinch_worst, ">= 0",
                 "PASS" if pinch_worst >= 0 else "FAIL",
                 "cable vs adjacent vendor housings in joint bands"])
    rows.append(["bend_radius_margin", "mm", bend_margin, ">= 0 (zero by design)",
                 "PASS" if bend_margin >= 0 else "FAIL", "guide-enforced radius vs P06=50.0"])
    for t in takeup_out:
        rows.append(["take_up_margin_%s" % t["joint"], "mm", t["margin_mm"], ">= 0",
                     "PASS" if t["pass"] else "FAIL",
                     "capacity - R*(mission range + 2*dq) - thermal"])
        rows.append(["take_up_margin_full_range_%s" % t["joint"], "mm",
                     t["margin_full_hardware_range_mm"], ">= 0",
                     "PASS" if t["margin_full_hardware_range_mm"] >= 0 else "FAIL",
                     "capacity - R*(URDF range + 2*dq) - thermal"])
    rows.append(["axial_extension_total_margin", "mm", cap_total - ext_total, ">= 0",
                 "PASS" if cap_total - ext_total >= 0 else "FAIL", "sum capacity - sum demand"])
    rows.append(["carrier_travel_margin", "mm", travel_margin, ">= 0",
                 "PASS" if travel_margin >= 0 else "FAIL",
                 "55 mm hard-stop half stroke - festoon demand"])
    rows.append(["carrier_travel_margin_full_range", "mm", travel_margin_full, ">= 0",
                 "PASS" if travel_margin_full >= 0 else "FAIL", "full J3 range"])
    rows.append(["j4_dynamic_length_residual_max", "mm",
                 j4_exact["max_abs_dynamic_length_residual_mm"],
                 "<= 1e-6", "PASS" if predicates["j4_exact_dynamic_closure"]["pass"] else "FAIL",
                 "L_trombone + L_annulus constant exchange"])
    rows.append(["j4_follower_fk_residual_max", "mm",
                 j4_exact["max_follower_closure_residual_mm"],
                 "<= 1e-6", "PASS" if predicates["j4_exact_dynamic_closure"]["pass"] else "FAIL",
                 "exact annular moving endpoint vs accepted-URDF link4 FK endpoint"])
    rows.append(["j4_full_hardware_min_stage_overlap", "mm", j4_overlap_full,
                 ">= 25", "PASS" if j4_overlap_full >= 25.0 else "FAIL",
                 "four independent rigid telescope stages; no solid scaling"])
    rows.append(["j4_annular_guide_mission_tracking_margin", "deg",
                 math.degrees(j4_guide_margin_tracking), ">= 0 candidate screen",
                 "PASS" if j4_guide_margin_tracking >= 0.0 else "FAIL",
                 "185 deg candidate guide minus mission plus tracking; not Owner acceptance"])
    rows.append(["j4_annular_guide_full_hardware_margin", "deg",
                 math.degrees(j4_guide_margin_full), "reported",
                 "DEFERRED_HOLD", "full q4 range requires more than 185 deg"])
    for t in torque_out:
        rows.append(["torque_margin_%s" % t["joint"], "N*m", t["margin_Nm"], ">= 0",
                     "KNOWN_COMPONENT_SCREEN_ONLY" if t["known_component_screen_pass"] else "FAIL",
                     "URDF effort %.1f - provisional bend/friction component only" % t["actuator_effort_budget_Nm"]])
    rows.append(["overall_resistance_torque_P08", "N*m", "UNKNOWN", "measured/qualified model required",
                 "HOLD_UNKNOWN_TORSION", "installed-bundle torsion is null/UNKNOWN and never zero-filled"])
    rows.append(["thermal_length_derate_total", "mm",
                 sum(t["thermal_length_derate_mm"] for t in takeup_out), "reported",
                 "INFO", "alpha_al*dT*path per segment summed"])
    rows.append(["clamp_support_bore_axis_gate", "count",
                 sum(1 for c in clamp_applicable if not c["pass"]), "= 0 failures",
                 "PASS" if clamp_gate_pass else "FAIL",
                 "per-interface bore containment and <=3 deg tangent alignment"])
    rows.append(["d3_open_sector_max_free_span", "mm",
                 d3_max_span if d3_max_span is not None else "UNKNOWN",
                 "<= %.3f" % d3_limit,
                 "PASS" if d3_gate_pass else "FAIL",
                 "two-layer helix crossing retention plus P13 spacing"])
    rows.append(["rc_hardware_cross_clearance_worst", "mm",
                 rc_worst if rc_cross_evaluated else "NOT_EVALUATED_IN_KEY_STATE_FAST_CHECK",
                 ">= 0 (mandatory in full mission sweep)",
                 ("PASS" if (rc_evals > 0 and rc_worst is not None and
                              math.isfinite(rc_worst) and rc_worst >= 0) else "FAIL")
                 if rc_cross_evaluated else "NOT_EVALUATED",
                 "RC parts vs vendor/solar/bus, other-host pairs"])
    rows.append(["full_range_spot_clearance_worst_gated", "mm",
                 fr_worst if fr_worst is not None else "SKIPPED_IN_FAST_MODE",
                 ">= 0 (not required by ODR-54 mission-rated target)",
                 "PASS" if fr_spot_pass else ("INFO" if fr_worst is None else "FAIL"),
                 "per-joint sweeps + 64 corners; skipped in FAST_MODE (V1/V3 reference)"])
    with open(OUT_LEDGER, "w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["margin_id", "unit", "value", "acceptance", "status", "basis"])
        for r in rows:
            w.writerow([r[0], r[1], repr(float(r[2])) if isinstance(r[2], float) else r[2],
                        r[3], r[4], r[5]])

    gate = {
        "schema": "ROUTE_C_MISSION_COVERAGE_GATE_%s" % VARIANT,
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "stage": "RC-4_MISSION_COVERAGE",
        "execution_mode": execution_mode,
        "authoritative": authoritative,
        "authority_scope": ("NON_AUTHORITATIVE_EARLY_REJECTION"
                            if FAST_MODE else
                            "CANDIDATE_GEOMETRY_EVALUATOR_ONLY__NO_RELEASE_CREDIT"),
        "odr_basis": ["ODR-42", "ODR-50", "ODR-52", "ODR-53", "ODR-54", "ODR-58"],
        "target": "E_MISSION_SUBSET_OF_E_ROUTE_C (mission-rated); full hardware range NOT required",
        "legal_outcomes": [
            "GEOMETRY_SIMULATION_READY_WITH_QUALIFICATION_HOLDS__OWNER_GATE_PENDING",
            "BLOCKED_BY_GEOMETRY_OR_INTERFACE_PREDICATE"],
        "verdict": verdict,
        "fail_closed_invariants": {
            "unknown_is_never_pass": True,
            "null_never_zero": True,
            "empty_comparison_set": empty_comparison_set_count,
            "empty_predicate_names": empty_predicate_names,
            "unexplained_penetration": 0,
            "mission_trajectory_unsafe_count": sum(1 for s in m_ref["segments"]
                                                   if s["worst_clearance_mm"] < 0.0),
            "unknown_auto_allow_count": 0,
            "hash_mismatch": len(pins["mesh_pack_files"]["mismatches"]),
        },
        "source_bindings": pins,
        "mandatory_key_states": {
            "total": len(key_states_out), "unsafe": n_key_unsafe,
            "checks": key_states_out,
            "state_mapping": "CONTACT/CAPTURE_22KG/POST_CAPTURE_22KG/PHYSICS_VETO_150KG arm-hold at PREGRASP q; SAFE_RECOVERY_TARGET at HOME q (V1 gate semantics)",
        },
        "trajectory_segments": {
            "required": len(segments),
            "evaluated_continuous": len(segments),
            "unsafe": sum(1 for s in m_ref["segments"] if s["worst_clearance_mm"] < 0.0),
            "trajectory_authority": "PROVISIONAL_MINIMUM_JERK_SEED_ONLY per contract; q-space path is the straight segment between contract states (quintic time law does not change the geometric path); time-parameter authority remains a registered hold and does not affect quasi-static harness predicates",
            "per_segment": m_ref["segments"],
        },
        "external_trajectory_gates": {
            "IK": "UNKNOWN_NOT_EVALUATED_FOR_COMPLETE_TRAJECTORY_SET",
            "COLLISION": "UNKNOWN_NOT_EVALUATED_FOR_COMPLETE_CURRENT_R2_TRAJECTORY_SET",
            "SOLAR_KEEP_OUT": "UNKNOWN_NOT_EVALUATED_FOR_COMPLETE_TRAJECTORY_SET",
            "SAFE_00": "UNKNOWN_22KG_ONLY_EXISTING_POLICY__150KG_NOT_REGISTERED",
            "scope": "carried verbatim from B601_HARNESS_MISSION_COVERAGE_GATE.json; arm-level mission gates are OUT OF SCOPE of this harness envelope verdict and remain registered UNKNOWN (fail-closed, not consumed here)",
        },
        "predicates": predicates,
        "overall_resistance_torque_status": "HOLD_UNKNOWN_TORSION",
        "owner_numeric_acceptance_rule": "ABSENT__ODR59_OR_EQUIVALENT_OWNER_RULING_PENDING",
        "tracking_tube": sweep["tracking_tube_candidate"],
        "convergence": {"refinement_factor": refinement_factor,
                        "status": convergence_status,
                        "worst_clearance_abs_change_mm": conv_mm},
        "full_range_spot_check": sweep["full_range_spot_check"],
        "declared_holds": [
            "MISSION_TRACKING_TUBE_CANDIDATE: control tracking and encoder/calibration error are DESIGN_CANDIDATE allocations pending B601 servo authority data",
            "torsion restoring moment of the installed bundle (P08) UNKNOWN - not zero-filled; registered C5 hold",
            "supplier dynamic flex life and space-environment applicability of igus/iglidur components - registered C6 holds",
            "V9F 185 deg annular follower is mission-bounded; full q4 hardware range coverage remains DEFERRED_HOLD",
            "ODR-59 or equivalent Owner numeric TMG-2 acceptance rule is absent; no release authorization may be inferred",
            "trajectory time-parameter authority (minimum-jerk seed) remains provisional per contract",
        ],
        "documented_failures": [],
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    if FAST_OUTPUT_TAG:
        gate["execution_metadata"] = sweep["execution_metadata"]
    if verdict == "BLOCKED_BY_GEOMETRY_OR_INTERFACE_PREDICATE":
        fails = []
        for name in geometry_predicate_names:
            p = predicates[name]
            if not p["pass"]:
                fails.append({"predicate": name, "detail": p})
        for k in key_states_out:
            if not k["pass"]:
                fails.append({"key_state": k["state_id"], "detail": k["detail"]})
        gate["documented_failures"] = fails
    with open(OUT_GATE, "w", encoding="utf-8", newline="\n") as f:
        f.write(jdump(gate))

    print("\n".join(log))
    print("VERDICT: %s" % verdict)


if __name__ == "__main__":
    main()
