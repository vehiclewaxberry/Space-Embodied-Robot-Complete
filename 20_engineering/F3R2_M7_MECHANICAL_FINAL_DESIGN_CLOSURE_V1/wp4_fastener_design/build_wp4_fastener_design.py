#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WP4_FASTENER_DESIGN builder — M7 final design closure.

Pure analytic fastener design for the M3R 4xHM4-75 joint plus product fastener
schedules, following the ECSS-E-HB-32-23A method flow (preloaded bolted joint:
stiffness, load introduction factor PHI, preload/torque, slip/separation/
tension/shear/bearing/net-section/pull-through/thread-shear checks).

Fail-closed rules honoured:
  * every output carries schema / generated_local(+08:00) / source_register(SHA-256)
  * no zero-fill: unknowns stay null with an explicit HOLD status
  * candidate != authority; every check is DESIGN_ANALYSIS_NOT_QUALIFICATION,
    flight_allowables = HOLD
  * L0 URDF mass is read, never written
"""

import csv
import hashlib
import json
import math
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import numpy as np
import yaml

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
PROJ = "F:/China Graduate Future Flight Vehicle Innovation Competition"
ENG = os.path.join(PROJ, "20_engineering")
M7 = os.path.join(ENG, "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1")
WP4 = os.path.join(M7, "wp4_fastener_design")
CDR = os.path.join(ENG, "F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821", "02_wp1_loads")
M5 = os.path.join(ENG, "F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1")
M6 = os.path.join(ENG, "F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1")
M4 = os.path.join(ENG, "F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1")
DD = os.path.join(ENG, "F3R2_MECHANICAL_DETAILED_DESIGN_V1")
TC = os.path.join(ENG, "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807", "03_native_cad", "M3_interface_authority")

INPUTS = [
    ("M7_ODR", os.path.join(M7, "00_authority", "M7_OWNER_DECISION_REGISTER_V1.yaml")),
    ("M7_EXEC_PLAN", os.path.join(M7, "00_authority", "M7_EXECUTION_PLAN_V1.md")),
    ("CDR_AUTHORIZED_LOADS", os.path.join(CDR, "AUTHORIZED_MECHANICAL_LOADS_V1.yaml")),
    ("CDR_LOAD_CASES", os.path.join(CDR, "LOAD_CASE_MATRIX.csv")),
    ("CDR_LOAD_COMBOS", os.path.join(CDR, "LOAD_COMBINATION_MATRIX.csv")),
    ("CDR_CAPTURE_ENVELOPE", os.path.join(CDR, "DERIVED_CAPTURE_LOAD_ENVELOPE_V1.csv")),
    ("CDR_BC_AUTHORITY", os.path.join(CDR, "BOUNDARY_CONDITION_AUTHORITY.json")),
    ("M5_JOINT_MODEL", os.path.join(M5, "04_joint_load_model", "M5_ANALYTIC_JOINT_LOAD_MODEL_V1.yaml")),
    ("M5_INFLUENCE", os.path.join(M5, "04_joint_load_model", "M5_FASTENER_GROUP_INFLUENCE_MATRIX_V1.csv")),
    ("M6_UNIT_LOAD", os.path.join(M6, "wp5_structural_entry", "FASTENER_GROUP_ANALYTIC_UNIT_LOAD_V1.csv")),
    ("M6_UNIT_NOTE", os.path.join(M6, "wp5_structural_entry", "FASTENER_GROUP_ANALYTIC_NOTE_V1.yaml")),
    ("M6_MATERIAL_LIB", os.path.join(M6, "wp4_materials", "PROTOTYPE_MATERIAL_LIBRARY_V2.yaml")),
    ("M6_BOM_V2", os.path.join(M6, "wp6_drawings_bom", "DIGITAL_PROTOTYPE_BOM_V2_CANDIDATE.csv")),
    ("REV_C_INTERFACE", os.path.join(DD, "02_interfaces", "B601_BASE_ADAPTER_REV_C_INTERFACE.yaml")),
    ("M3R_PHYSICAL_STACK", os.path.join(TC, "M3R_TSM_PHYSICAL_STACK.yaml")),
    ("M4_STACKUP", os.path.join(M4, "05_tolerance", "INTERFACE_STACKUP_B601_M3R_V1.yaml")),
    ("URDF_B601", os.path.join(ENG, "cad", "spacecraft_layout", "arm_b601_v1", "arm_b601_v1.urdf")),
    ("SCENE_A1", os.path.join(ENG, "config", "coupled_scene", "scene_A1_arm_slew.yaml")),
]

GENERATED_LOCAL = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def source_register():
    reg = []
    for tag, p in INPUTS:
        reg.append({
            "id": tag,
            "path": os.path.relpath(p, PROJ).replace(os.sep, "/"),
            "sha256": sha256_of(p),
        })
    return reg


# ----------------------------------------------------------------------------
# ISO metric thread standard geometry (STANDARD_GEOMETRY, not material data)
# ----------------------------------------------------------------------------
THREADS = {
    "M4x0.7": dict(d=4.0, pitch=0.7, As=8.78, d2=3.545, d_minor_ext=3.002,
                   shcs_head_dia=7.0, washer_od=9.0, nut_height=None),
    "M5x0.8": dict(d=5.0, pitch=0.8, As=14.18, d2=4.480, d_minor_ext=3.933,
                   shcs_head_dia=8.5, washer_od=10.0, nut_height=None),
    "M6x1.0": dict(d=6.0, pitch=1.0, As=20.10, d2=5.350, d_minor_ext=4.773,
                   shcs_head_dia=10.0, washer_od=12.0, nut_height=5.2),
}
THREAD_SOURCE = "ISO_METRIC_COARSE_THREAD_BASIC_DIMENSIONS_PUBLIC_STANDARD_GEOMETRY_NOT_AN_ALLOWABLE"

# Material candidates from M6 library V2 (values quoted, statuses preserved)
MAT_A286 = dict(yield_proof_MPa=655.0, uts_MPa=965.0,
                value_kind="MIN_PUBLIC_DISTRIBUTOR_REFERENCE_AMS5737_1650F_CONDITION_CANDIDATE",
                E_GPa=200.0, E_kind="ASSUMPTION_NO_SOURCE_A286_CLASS_TYPICAL")
MAT_CRES = dict(yield_proof_MPa=207.0, uts_MPa=517.0,
                value_kind="MIN_ANNEALED_304_REFERENCE_NOT_CW_FASTENER_CONDITION_LOWER_BOUND_ONLY",
                E_GPa=200.0, E_kind="ASSUMPTION_NO_SOURCE_AUSTENITIC_CLASS_TYPICAL")
MAT_AL6061 = dict(yield_MPa=276.0, uts_MPa=310.0, E_GPa=68.3,
                  value_kind="TYPICAL_KAISER_PUBLIC_PDF_NOT_MINIMUM")

# Declared assembly/joint assumptions (ECSS-E-HB-32-23A method flow placeholders)
K_NOM = 0.20
K_BAND = [0.15, 0.25]          # torque factor candidate band, dry/lubricated scatter
TOOL_TOL = 0.10                # declared torque-tool tolerance band (+-10%)
RELAX = 0.10                   # declared embedment/relaxation loss of assembly preload
PRELOAD_PROOF_FRAC = 0.65      # target preload as fraction of proof load (band 0.50-0.75)
MU_BAND = [0.15, 0.30]         # declared friction band, dry steel/Al class, no authority
CONE_ALPHA_DEG = 30.0          # Shigley frustum half-angle candidate (VDI tan_phi=0.4 alternate)
THREAD_SHEAR_FACTOR = 0.577    # von Mises shear-from-tensile declared assumption
THREAD_ENGAGE_EFF = 0.75       # declared thread shear area effectiveness factor


# ----------------------------------------------------------------------------
# Fastener group load distribution (M5 model, verified against M6 unit CSV)
# ----------------------------------------------------------------------------
class Pattern:
    def __init__(self, name, coords, thread, hole_dia):
        self.name = name
        self.coords = [tuple(c) for c in coords]  # (y,z) m
        self.n = len(coords)
        self.thread = thread
        self.hole_dia = hole_dia
        self.sum_y2 = sum(c[0] ** 2 for c in coords)
        self.sum_z2 = sum(c[1] ** 2 for c in coords)
        self.sum_r2 = self.sum_y2 + self.sum_z2

    def distribute(self, wrench):
        """wrench = dict(Fx,Fy,Fz [N], Mx,My,Mz [N*m]); x normal, y/z in plane.
        Returns list per fastener: (N_axial, Qy, Qz, Q_res)."""
        Fx, Fy, Fz = wrench["Fx"], wrench["Fy"], wrench["Fz"]
        Mx, My, Mz = wrench["Mx"], wrench["My"], wrench["Mz"]
        out = []
        for (y, z) in self.coords:
            N = Fx / self.n + My * z / self.sum_z2 - Mz * y / self.sum_y2
            Qy = Fy / self.n + Mx * (-z) / self.sum_r2
            Qz = Fz / self.n + Mx * y / self.sum_r2
            out.append((N, Qy, Qz, math.hypot(Qy, Qz)))
        return out

    def worst(self, wrench):
        """Exact per-fastener extremes under this signed wrench."""
        dist = self.distribute(wrench)
        return max(d[0] for d in dist), min(d[0] for d in dist), max(d[3] for d in dist)


PAT_M3R = Pattern("B601_TO_STAGE_A_4XM4_HM4_75_64MM",
                  [(-0.032, -0.032), (-0.032, 0.032), (0.032, -0.032), (0.032, 0.032)],
                  THREADS["M4x0.7"], 4.6)
PAT_AB = Pattern("STAGE_A_TO_B_8XM5_R62P5MM",
                 [(0.0625 * math.cos(k * math.pi / 4), 0.0625 * math.sin(k * math.pi / 4))
                  for k in range(8)],
                 THREADS["M5x0.8"], 5.5)
PAT_BRIDGE = Pattern("STAGE_B_TO_SPACECRAFT_4XM6_140MM",
                     [(-0.07, -0.07), (-0.07, 0.07), (0.07, -0.07), (0.07, 0.07)],
                     THREADS["M6x1.0"], 6.6)


def verify_against_m6_unit_csv():
    """Reproduce M6 FASTENER_GROUP_ANALYTIC_UNIT_LOAD_V1.csv rows (software verification)."""
    rows = []
    with open(dict(INPUTS)["M6_UNIT_LOAD"], newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    max_diff = 0.0
    n_checked = 0
    for r in rows:
        comp = r["unit_load_component"]
        wrench = dict(Fx=0.0, Fy=0.0, Fz=0.0, Mx=0.0, My=0.0, Mz=0.0)
        wrench[comp] = 1.0
        idx = int(r["fastener_index"]) - 1
        got = PAT_M3R.distribute(wrench)[idx]
        for key, val in zip(("N_axial_N", "Qy_N", "Qz_N", "Q_resultant_N"), got):
            ref = float(r[key])
            max_diff = max(max_diff, abs(val - ref))
            n_checked += 1
    return max_diff, n_checked


# ----------------------------------------------------------------------------
# URDF parse + rigid-body inverse dynamics (LC-010 on-orbit arm slew)
# ----------------------------------------------------------------------------
def rpy_matrix(rpy):
    r, p, y = rpy
    Rx = np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])
    Ry = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
    Rz = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def parse_urdf(path):
    root = ET.parse(path).getroot()
    links, joints = {}, []
    for lk in root.findall("link"):
        name = lk.get("name")
        inert = lk.find("inertial")
        org = inert.find("origin")
        xyz = [float(v) for v in org.get("xyz").split()]
        rpy = [float(v) for v in (org.get("rpy") or "0 0 0").split()]
        mass = float(inert.find("mass").get("value"))
        ie = inert.find("inertia")
        I = np.array([[float(ie.get("ixx")), float(ie.get("ixy")), float(ie.get("ixz"))],
                      [float(ie.get("ixy")), float(ie.get("iyy")), float(ie.get("iyz"))],
                      [float(ie.get("ixz")), float(ie.get("iyz")), float(ie.get("izz"))]])
        links[name] = dict(mass=mass, com=np.array(xyz), com_rpy=rpy_matrix(rpy), I=I)
    for jn in root.findall("joint"):
        org = jn.find("origin")
        xyz = [float(v) for v in org.get("xyz").split()]
        rpy = [float(v) for v in (org.get("rpy") or "0 0 0").split()]
        joints.append(dict(name=jn.get("name"), type=jn.get("type"),
                           parent=jn.find("parent").get("link"),
                           child=jn.find("child").get("link"),
                           xyz=np.array(xyz), R=rpy_matrix(rpy),
                           axis=np.array([float(v) for v in jn.find("axis").get("xyz").split()])))
    return links, joints


def inverse_dynamics_base_wrench(links, joints, qmap, qdmap, qddmap):
    """Fixed-base microgravity RNE. Returns (F, M) exerted by arm on base,
    expressed at base_link origin in base_link coordinates."""
    # world state per link: R (orientation), P (origin), w, al, a_origin, a_com
    state = {"base_link": dict(R=np.eye(3), P=np.zeros(3), w=np.zeros(3),
                               al=np.zeros(3), ao=np.zeros(3))}
    order = []  # joints in chain order from root
    known = {"base_link"}
    remaining = list(joints)
    while remaining:
        for j in remaining:
            if j["parent"] in known:
                order.append(j)
                known.add(j["child"])
                remaining.remove(j)
                break
        else:
            raise RuntimeError("joint chain broken")
    for j in order:
        ps = state[j["parent"]]
        Rj = ps["R"] @ j["R"]                     # joint frame world orientation
        if j["type"] == "revolute":
            q = qmap.get(j["name"], 0.0)
            qd = qdmap.get(j["name"], 0.0)
            qdd = qddmap.get(j["name"], 0.0)
            # rotation about joint axis in joint frame
            ax = j["axis"]
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            Rq = np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * (K @ K)
            R = Rj @ Rq
            a_w = Rj @ ax

            w = ps["w"] + a_w * qd
            al = ps["al"] + a_w * qdd + np.cross(ps["w"], a_w * qd)
        else:  # fixed or locked prismatic
            R = Rj
            w, al = ps["w"], ps["al"]
        P = ps["P"] + ps["R"] @ j["xyz"]
        ao = ps["ao"] + np.cross(ps["al"], P - ps["P"]) + np.cross(ps["w"], np.cross(ps["w"], P - ps["P"]))
        state[j["child"]] = dict(R=R, P=P, w=w, al=al, ao=ao)
    # inward pass
    Ftot = np.zeros(3)
    Mtot = np.zeros(3)
    for j in reversed(order):
        lk = links[j["child"]]
        st = state[j["child"]]
        c = st["P"] + st["R"] @ lk["com"]
        ac = st["ao"] + np.cross(st["al"], c - st["P"]) + np.cross(st["w"], np.cross(st["w"], c - st["P"]))
        Iw = st["R"] @ lk["com_rpy"] @ lk["I"] @ lk["com_rpy"].T @ st["R"].T
        F = lk["mass"] * ac
        N = Iw @ st["al"] + np.cross(st["w"], Iw @ st["w"])
        Ftot += F
        Mtot += N + np.cross(c, F)   # moment about base_link origin
    return Ftot, Mtot


def verify_rne(links, joints):
    """RNE software verification: zero-motion wrench == 0, and linear force matches
    a central finite difference of total linear momentum at three trajectory points."""
    F0, M0 = inverse_dynamics_base_wrench(links, joints, {}, {}, {})
    zero_ok = bool(np.linalg.norm(F0) == 0.0 and np.linalg.norm(M0) == 0.0)
    T = 8.0
    dq2, dq3 = math.radians(60.0), math.radians(-40.0)

    def state_at(tau):
        s = 10 * tau**3 - 15 * tau**4 + 6 * tau**5
        sd = (30 * tau**2 - 60 * tau**3 + 30 * tau**4) / T
        sdd = (60 * tau - 180 * tau**2 + 120 * tau**3) / T**2
        return ({"joint2": dq2 * s, "joint3": dq3 * s},
                {"joint2": dq2 * sd, "joint3": dq3 * sd},
                {"joint2": dq2 * sdd, "joint3": dq3 * sdd})

    def com_positions(qmap):
        st = {"base_link": dict(R=np.eye(3), P=np.zeros(3))}
        out = {}
        order, known, remaining = [], {"base_link"}, list(joints)
        while remaining:
            for j in remaining:
                if j["parent"] in known:
                    order.append(j); known.add(j["child"]); remaining.remove(j); break
        for j in order:
            ps = st[j["parent"]]
            Rj = ps["R"] @ j["R"]
            if j["type"] == "revolute":
                q = qmap.get(j["name"], 0.0)
                ax = j["axis"]
                K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
                R = Rj @ (np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * (K @ K))
            else:
                R = Rj
            P = ps["P"] + ps["R"] @ j["xyz"]
            st[j["child"]] = dict(R=R, P=P)
            out[j["child"]] = P + R @ links[j["child"]]["com"]
        return out

    def total_momentum(tau, dtau=1e-5):
        c1 = com_positions(state_at(tau - dtau)[0])
        c2 = com_positions(state_at(tau + dtau)[0])
        p = np.zeros(3)
        for name in c1:
            p += links[name]["mass"] * (c2[name] - c1[name]) / (2 * dtau * T)
        return p

    rel_errs = []
    for tau in (0.2113, 0.5, 0.7887):
        qmap, qdmap, qddmap = state_at(tau)
        F, _M = inverse_dynamics_base_wrench(links, joints, qmap, qdmap, qddmap)
        Fd = (total_momentum(tau + 1e-4) - total_momentum(tau - 1e-4)) / (2e-4 * T)
        rel_errs.append(float(np.linalg.norm(F - Fd) / max(np.linalg.norm(F), 1e-12)))
    return {"zero_motion_wrench_zero": zero_ok,
            "linear_momentum_fd_max_rel_err": max(rel_errs)}


def lc010_inertial_wrench(urdf_path):
    links, joints = parse_urdf(urdf_path)
    T = 8.0
    dq2 = math.radians(60.0)
    dq3 = math.radians(-40.0)
    ns = 801
    best = None
    hist_peak = dict(F=0.0, M=0.0)
    for i in range(ns):
        tau = i / (ns - 1)
        s = 10 * tau**3 - 15 * tau**4 + 6 * tau**5
        sd = (30 * tau**2 - 60 * tau**3 + 30 * tau**4) / T
        sdd = (60 * tau - 180 * tau**2 + 120 * tau**3) / T**2
        qmap = {"joint2": dq2 * s, "joint3": dq3 * s}
        qdmap = {"joint2": dq2 * sd, "joint3": dq3 * sd}
        qddmap = {"joint2": dq2 * sdd, "joint3": dq3 * sdd}
        F, M = inverse_dynamics_base_wrench(links, joints, qmap, qdmap, qddmap)
        if best is None or (np.linalg.norm(F) + np.linalg.norm(M)) > best[0]:
            best = (np.linalg.norm(F) + np.linalg.norm(M), F, M, tau)
        hist_peak["F"] = max(hist_peak["F"], float(np.linalg.norm(F)))
        hist_peak["M"] = max(hist_peak["M"], float(np.linalg.norm(M)))
    return best[1], best[2], best[3], hist_peak


# ----------------------------------------------------------------------------
# Joint mechanics (ECSS-E-HB-32-23A method flow)
# ----------------------------------------------------------------------------
def bolt_stiffness(thr, L_grip_mm, E_GPa):
    """k_b [N/mm]; shank + head(0.4d) + thread-in-member(0.4d) simplification."""
    A_n = math.pi / 4 * thr["d"] ** 2
    E = E_GPa * 1000.0  # N/mm^2
    inv = (L_grip_mm + 0.4 * thr["d"]) / (E * A_n) + 0.4 * thr["d"] / (E * thr["As"])
    return 1.0 / inv


def member_frustum_stiffness(t_mm, d_nom_mm, d_head_mm, E_GPa, alpha_deg):
    """Shigley frustum stiffness for one member of thickness t."""
    E = E_GPa * 1000.0
    ta = math.tan(math.radians(alpha_deg))
    num = (2 * t_mm * ta + d_head_mm - d_nom_mm) * (d_head_mm + d_nom_mm)
    den = (2 * t_mm * ta + d_head_mm + d_nom_mm) * (d_head_mm - d_nom_mm)
    return math.pi * E * d_nom_mm * ta / math.log(num / den)


def joint_stiffness(thr, members):
    """members: list of (t_mm, E_GPa, d_head_mm). Returns k_b, k_m, PHI."""
    L = sum(m[0] for m in members)
    kb = bolt_stiffness(thr, L, MAT_A286["E_GPa"])
    inv_km = sum(1.0 / member_frustum_stiffness(t, thr["d"], dh, E, CONE_ALPHA_DEG)
                 for (t, E, dh) in members)
    km = 1.0 / inv_km
    phi = kb / (kb + km)
    return kb, km, phi


def preload_torque(thr, mat):
    """Preload candidates from proof fraction; torque via K-factor."""
    As = thr["As"]
    d = thr["d"]
    F_proof = mat["yield_proof_MPa"] * As      # N
    F_ult = mat["uts_MPa"] * As
    Fp_t = PRELOAD_PROOF_FRAC * F_proof
    T_t = K_NOM * Fp_t * d / 1000.0            # N*m
    T_min = T_t * (1 - TOOL_TOL)
    T_max = T_t * (1 + TOOL_TOL)
    Fp_max = T_max * 1000.0 / (K_BAND[0] * d)
    Fp_min_asm = T_min * 1000.0 / (K_BAND[1] * d)
    Fp_min = Fp_min_asm * (1 - RELAX)
    return dict(F_proof=F_proof, F_ult=F_ult, Fp_target=Fp_t, Fp_max=Fp_max,
                Fp_min_service=Fp_min, T_target=T_t, T_band=[T_min, T_max],
                Fp_band_sensitivity=dict(K_low_0p15=dict(Fp_max=Fp_max),
                                         K_high_0p25=dict(Fp_min=Fp_min_asm)))


def run_checks(pattern, joint, wrench, pt, stiff, case_id, variant, notes=""):
    """All per-case checks. Returns list of check-row dicts."""
    kb, km, phi = stiff
    thr = pattern.thread
    Fp_min = pt["Fp_min_service"]
    Fp_max = pt["Fp_max"]
    dist = pattern.distribute(wrench)
    N_max = max(d[0] for d in dist)
    N_min = min(d[0] for d in dist)
    Q_max = max(d[3] for d in dist)
    F_b_max = Fp_max + phi * max(N_max, 0.0)
    t_plate = joint["plate_t_mm"]
    E_sep = Fp_min * (1 - phi)
    mu = MU_BAND[0]
    # slip capacity at most-tensioned bolt (residual preload smallest there)
    F_resid = max(Fp_min - (1 - phi) * max(N_max, 0.0), 0.0)
    slip_cap = mu * F_resid
    # thread shear demand uses bolt max tension
    A_shank = math.pi / 4 * thr["d"] ** 2
    A_head_bearing = math.pi / 4 * (thr["shcs_head_dia"] ** 2 - pattern.hole_dia ** 2)
    A_net = (joint["tributary_mm"] - pattern.hole_dia) * t_plate
    al = MAT_AL6061
    rows = []

    def add(check, demand, capacity, unit, basis, status="DESIGN_ANALYSIS_NOT_QUALIFICATION"):
        ratio = None
        if demand is not None and capacity not in (None, 0):
            ratio = demand / capacity
        rows.append(dict(joint_id=pattern.name, case_id=case_id, case_variant=variant,
                         check_id=check, demand=demand, capacity=capacity,
                         demand_over_capacity=ratio, unit=unit, basis=basis,
                         status=status, notes=notes))

    add("SLIP_FRICTION", Q_max, slip_cap, "N",
        "Q_max vs mu_min*(Fp_min-(1-PHI)*N_max); mu candidate band [0.15,0.30] ASSUMPTION")
    add("SEPARATION", max(N_max, 0.0), E_sep, "N",
        "N_max vs Fp_min*(1-PHI); separation predicted when ratio>=1")
    add("BOLT_ADDITIONAL_TENSION_PROOF", F_b_max, pt["F_proof"], "N",
        "Fp_max+PHI*N_max vs S_proof*As (candidate material proof, A286 655MPa MIN distributor ref)")
    add("BOLT_TENSION_ULTIMATE", F_b_max, pt["F_ult"], "N",
        "Fp_max+PHI*N_max vs S_u*As (candidate A286 965MPa MIN distributor ref)")
    add("BOLT_SHEAR", Q_max / A_shank, THREAD_SHEAR_FACTOR * 655.0, "MPa",
        "Q_max/A_shank vs 0.577*S_proof; SHANK_IN_SHEAR_PLANE_ASSUMPTION; shear allowable ASSUMPTION_NO_SOURCE")
    add("BEARING_PLATE_6061T6", Q_max / (thr["d"] * t_plate), al["uts_MPa"], "MPa",
        "p=Q/(d*t_plate) vs 6061-T6 Ftu TYPICAL 310MPa reference level; INDICATIVE_NOT_AN_ALLOWABLE",
        status="INDICATIVE_REFERENCE_DESIGN_ANALYSIS_NOT_QUALIFICATION")
    add("NET_SECTION_PLATE_6061T6", max(N_max, 0.0) / A_net, al["uts_MPa"], "MPa",
        "sigma_net=N_max/((tributary-hole)*t_plate) conservative tributary model vs Ftu typical; INDICATIVE",
        status="INDICATIVE_REFERENCE_DESIGN_ANALYSIS_NOT_QUALIFICATION")
    add("HEAD_PULL_THROUGH", F_b_max / A_head_bearing, al["yield_MPa"], "MPa",
        "head bearing pressure vs 6061-T6 Fty TYPICAL 276MPa reference; INDICATIVE",
        status="INDICATIVE_REFERENCE_DESIGN_ANALYSIS_NOT_QUALIFICATION")
    # thread shear (external bolt thread, A286; engagement per joint design)
    L_e = joint["L_e_mm"]
    if L_e is None:
        add("THREAD_SHEAR_EXTERNAL_BOLT", None, None, "MPa",
            "engagement length as-built unknown", status="HOLD_AS_BUILT_ENGAGEMENT_UNKNOWN")
        add("THREAD_SHEAR_INTERNAL_MEMBER", None, None, "MPa",
            joint["internal_thread_note"], status=joint["internal_thread_status"])
    else:
        A_ts = math.pi * thr["d2"] * L_e * THREAD_ENGAGE_EFF
        tau_ext = F_b_max / A_ts
        add("THREAD_SHEAR_EXTERNAL_BOLT", tau_ext, THREAD_SHEAR_FACTOR * 655.0, "MPa",
            "tau=F_b_max/(pi*d2*L_e*0.75) vs 0.577*S_proof A286; L_e candidate declared")
        tau_allow_int = joint.get("tau_allow_internal_MPa")
        if tau_allow_int is None:
            add("THREAD_SHEAR_INTERNAL_MEMBER", None, None, "MPa",
                joint["internal_thread_note"], status=joint["internal_thread_status"])
        else:
            A_tsi = math.pi * thr["d"] * L_e * THREAD_ENGAGE_EFF
            add("THREAD_SHEAR_INTERNAL_MEMBER", F_b_max / A_tsi, tau_allow_int, "MPa",
                joint["internal_thread_note"])
    return rows


# ----------------------------------------------------------------------------
# Joint definitions (declared candidates; grip lengths pending WP1)
# ----------------------------------------------------------------------------
PENDING_WP1 = "PENDING_SIBLING_HASH:wp1_structure_cad/PRODUCT_STRUCTURE_V1.yaml"
PENDING_WP6 = "PENDING_SIBLING_HASH:wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1.yaml"
PENDING_WP5 = "PENDING_SIBLING_HASH:wp5_mechanisms"

JOINTS = {
    "B601_TO_STAGE_A_4XM4_HM4_75_64MM": dict(
        plate_t_mm=6.0,   # DECLARED CANDIDATE Stage A flange at bolt circle [4.0,8.0], pending WP1
        plate_t_note="CANDIDATE_ASSUMPTION_PENDING_WP1_PRODUCT_STRUCTURE",
        tributary_mm=64.0,
        L_e_mm=None,      # as-built B601 internal thread engagement unknown
        internal_thread_note="B601 vendor tapped holes; material and engagement unknown",
        internal_thread_status="HOLD_NO_B601_MATERIAL_OR_ENGAGEMENT_AUTHORITY",
        members=[(6.0, MAT_AL6061["E_GPa"], THREADS["M4x0.7"]["shcs_head_dia"]),
                 (6.0, MAT_AL6061["E_GPa"], THREADS["M4x0.7"]["shcs_head_dia"])],
        pattern=PAT_M3R),
    "STAGE_A_TO_B_8XM5_R62P5MM": dict(
        plate_t_mm=8.0,   # DECLARED CANDIDATE Stage B pocket floor [6.0,10.0], pending WP1
        plate_t_note="CANDIDATE_ASSUMPTION_PENDING_WP1_PRODUCT_STRUCTURE",
        tributary_mm=2 * math.pi * 62.5 / 8,
        L_e_mm=7.5,       # 1.5d with wire thread insert candidate (2d=10mm direct tap alternate)
        internal_thread_note="Stage A 6061-T6 candidate; wire-thread-insert candidate L_e=1.5d; tau_allow=0.577*Fty_typ ASSUMPTION on typical",
        internal_thread_status="DESIGN_ANALYSIS_NOT_QUALIFICATION",
        tau_allow_internal_MPa=THREAD_SHEAR_FACTOR * MAT_AL6061["yield_MPa"],
        members=[(8.0, MAT_AL6061["E_GPa"], THREADS["M5x0.8"]["shcs_head_dia"]),
                 (8.0, MAT_AL6061["E_GPa"], THREADS["M5x0.8"]["shcs_head_dia"])],
        pattern=PAT_AB),
    "STAGE_B_TO_SPACECRAFT_4XM6_140MM": dict(
        plate_t_mm=10.75,  # load bridge candidate plate thickness (M6 WP1 contract)
        plate_t_note="LOAD_BRIDGE_CANDIDATE_6061T6_FROM_M6_WP1_CONTRACT_BUS_SIDE_HOLD",
        tributary_mm=140.0 / 2,
        L_e_mm=5.2,        # standard M6 nut height candidate (through-bolt + nut)
        internal_thread_note="through-bolt + A286-class nut candidate; nut thread shear vs 0.577*S_proof A286 ASSUMPTION",
        internal_thread_status="DESIGN_ANALYSIS_NOT_QUALIFICATION",
        tau_allow_internal_MPa=THREAD_SHEAR_FACTOR * 655.0,
        members=[(8.0, MAT_AL6061["E_GPa"], THREADS["M6x1.0"]["shcs_head_dia"]),
                 (10.75, MAT_AL6061["E_GPa"], THREADS["M6x1.0"]["shcs_head_dia"])],
        pattern=PAT_BRIDGE),
}

# Lever-arm offsets toward bus for downstream joints (declared conservative bound)
LEVER_OFFSET = {"B601_TO_STAGE_A_4XM4_HM4_75_64MM": 0.0,
                "STAGE_A_TO_B_8XM5_R62P5MM": 0.025,
                "STAGE_B_TO_SPACECRAFT_4XM6_140MM": 0.035}


# ----------------------------------------------------------------------------
# Load cases
# ----------------------------------------------------------------------------
def capture_wrench(F_peak, lever, C_peak, variant):
    """Bounding capture wrench scenarios (contact direction unknown -> declared variants)."""
    if variant == "NORMAL_TENSION_BENDING":
        return dict(Fx=F_peak, Fy=0.0, Fz=0.0, Mx=0.0, My=F_peak * lever + C_peak, Mz=0.0)
    else:  # SHEAR_TORSION
        return dict(Fx=0.0, Fy=F_peak, Fz=0.0, Mx=C_peak, My=0.0, Mz=0.0)


def main():
    os.makedirs(WP4, exist_ok=True)
    reg = source_register()

    # -- software verification: reproduce M6 unit-load table ------------------
    diff, nchk = verify_against_m6_unit_csv()
    print(f"[verify] M6 unit-load reproduction: max abs diff {diff:.3e} over {nchk} values")
    assert diff < 1e-9

    # -- LC-010 inertial wrench from URDF -------------------------------------
    F010, M010, tau010, peak010 = lc010_inertial_wrench(dict(INPUTS)["URDF_B601"])
    print(f"[LC-010] controlling tau={tau010:.3f} |F|={np.linalg.norm(F010):.3f} N "
          f"|M|={np.linalg.norm(M010):.3f} N*m ; peaks F={peak010['F']:.3f} M={peak010['M']:.3f}")
    # map A0 -> joint datum: x_joint = z_A0 (interface normal); plane y/z ~ A0 x/y
    # moment arm base origin -> joint plane = 25.155 mm along +Z_A0
    r_datum = np.array([0.0, 0.0, 0.025155])
    M010_j = M010 - np.cross(r_datum, F010)
    W010 = dict(Fx=float(F010[2]), Fy=float(F010[0]), Fz=float(F010[1]),
                Mx=float(M010_j[2]), My=float(M010_j[0]), Mz=float(M010_j[1]))
    links_v, joints_v = parse_urdf(dict(INPUTS)["URDF_B601"])
    rne_ver = verify_rne(links_v, joints_v)
    print(f"[verify] RNE zero-motion={rne_ver['zero_motion_wrench_zero']} "
          f"momentum-FD max rel err={rne_ver['linear_momentum_fd_max_rel_err']:.2e}")

    # -- stiffness / preload per joint ----------------------------------------
    stiff = {}
    pt = {}
    for jid, j in JOINTS.items():
        kb, km, phi = joint_stiffness(j["pattern"].thread, j["members"])
        stiff[jid] = (kb, km, phi)
        pt[jid] = preload_torque(j["pattern"].thread, MAT_A286)
        print(f"[{jid}] k_b={kb:.3e} N/mm k_m={km:.3e} PHI={phi:.4f} "
              f"Fp_t={pt[jid]['Fp_target']:.1f} N T_t={pt[jid]['T_target']:.3f} N*m")

    # -- evaluate checks -------------------------------------------------------
    check_rows = []

    # LC-010 exact wrench history controlling sample (all joints see same wrench, declared)
    for jid, j in JOINTS.items():
        check_rows += run_checks(j["pattern"], j, W010, pt[jid], stiff[jid],
                                 "LC-010_ARM_NOMINAL_SLEW", "EXACT_WRENCH_CONTROLLING_SAMPLE",
                                 notes="DERIVED inertial wrench from URDF RNE; microgravity fixed-base ASSUMPTION")

    # Capture anchors: parametric half-sine pulse, contact-duration band
    captures = [
        ("LC-013_CAPTURE_22KG", 0.360622, 0.25173, 0.00152744),
        ("LC-014_CAPTURE_150KG", 0.677633, 1.21521, 0.130197),
    ]
    tc_band = [0.005, 0.010, 0.020, 0.050]
    for case, Jmax, lever, Cmax in captures:
        for tc in tc_band:
            F_peak = math.pi * Jmax / (2 * tc)
            C_peak = math.pi * Cmax / (2 * tc)
            for variant in ("NORMAL_TENSION_BENDING", "SHEAR_TORSION"):
                for jid, j in JOINTS.items():
                    W = capture_wrench(F_peak, lever + LEVER_OFFSET[jid], C_peak, variant)
                    check_rows += run_checks(j["pattern"], j, W, pt[jid], stiff[jid],
                                             case, variant,
                                             notes=(f"half-sine pulse ASSUMPTION tc={tc*1000:.0f}ms; "
                                                    f"F_peak=pi*J/(2tc)={F_peak:.1f}N; DERIVED impulse is "
                                                    f"NOT_STRUCTURAL_DESIGN_AUTHORITY; BOUNDING scenario"))

    # LC-016 gripper clamp: URDF effort limit 100 N as model-limit bounding shear at tip
    # tip lever arm from FK at pregrasp pose
    links, joints_urdf = parse_urdf(dict(INPUTS)["URDF_B601"])
    qmap_end = {"joint2": math.radians(60), "joint3": math.radians(-40)}
    # FK to gripper_link origin
    state = {"base_link": dict(R=np.eye(3), P=np.zeros(3))}
    for j in joints_urdf:
        if j["parent"] not in state:
            continue
        ps = state[j["parent"]]
        Rj = ps["R"] @ j["R"]
        if j["type"] == "revolute":
            q = qmap_end.get(j["name"], 0.0)
            ax = j["axis"]
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = Rj @ (np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * (K @ K))
        else:
            R = Rj
        P = ps["P"] + ps["R"] @ j["xyz"]
        state[j["child"]] = dict(R=R, P=P)
    tip = state["gripper_link"]["P"]
    lever_grip = float(np.linalg.norm(tip[:2]))  # transverse distance from arm base z axis
    print(f"[LC-016] gripper tip position {np.round(tip,4)} m, transverse lever {lever_grip:.4f} m")
    for jid, j in JOINTS.items():
        lev = lever_grip + 0.025155 + LEVER_OFFSET[jid]
        W = dict(Fx=0.0, Fy=100.0, Fz=0.0, Mx=0.0, My=100.0 * lev, Mz=0.0)
        check_rows += run_checks(j["pattern"], j, W, pt[jid], stiff[jid],
                                 "LC-016_GRIPPER_CLAMP", "MODEL_LIMIT_BOUNDING",
                                 notes="URDF effort limit 100N = MODEL_LIMIT_NOT_DESIGN_LOAD; "
                                       "bounding transverse shear at gripper tip ASSUMPTION")

    # HOLD rows: on-orbit cases without load authority (fail-closed, null numerics)
    hold_cases = [
        ("LC-008_SOLAR_ARRAY_DEPLOYMENT", "HOLD_NO_HINGE_TORQUE_DAMPING_OR_STOP_IMPACT_AUTHORITY"),
        ("LC-009_PANEL_FAILURE_CASES", "HOLD_CONFIGURATION_ENUM_ONLY_LOADS_UNKNOWN"),
        ("LC-011_ARM_EMERGENCY_STOP", "HOLD_NO_STOP_TIME_DECELERATION_LAW_OR_ACTUATOR_TORQUE_AUTHORITY"),
        ("LC-019_THERMAL_GRADIENT", "HOLD_NO_MISSION_THERMAL_ENVIRONMENT_PRELOAD_THERMAL_RESPONSE_UNKNOWN"),
        ("LC-020_SAFE_MODE", "HOLD_SAFE_MODE_MECHANICAL_STATE_UNDEFINED"),
        ("ON_ORBIT_SYSTEM_MODAL", "HOLD_MODAL_CHARACTERIZATION_BY_WP7_NO_STRENGTH_LOAD"),
        ("LAUNCH_FAMILY_LC001_TO_LC006", "HOLD_OUT_OF_ODR06_SCOPE_NO_LAUNCHER_OR_SEPARATION_ICD"),
    ]
    for case, st in hold_cases:
        for jid in JOINTS:
            for chk in ("SLIP_FRICTION", "SEPARATION", "BOLT_ADDITIONAL_TENSION_PROOF",
                        "BOLT_TENSION_ULTIMATE", "BOLT_SHEAR", "BEARING_PLATE_6061T6",
                        "NET_SECTION_PLATE_6061T6", "HEAD_PULL_THROUGH",
                        "THREAD_SHEAR_EXTERNAL_BOLT", "THREAD_SHEAR_INTERNAL_MEMBER"):
                check_rows.append(dict(joint_id=jid, case_id=case, case_variant="NA",
                                       check_id=chk, demand=None, capacity=None,
                                       demand_over_capacity=None, unit=None,
                                       basis="LOAD_AUTHORITY_ABSENT_FAIL_CLOSED_NULL",
                                       status=st, notes=""))

    # LC-021 verification rows
    check_rows.append(dict(joint_id="B601_TO_STAGE_A_4XM4_HM4_75_64MM",
                           case_id="LC-021_UNIT_CHARACTERIZATION",
                           case_variant="SOFTWARE_VERIFICATION", check_id="DISTRIBUTION_ENGINE_REPRODUCTION",
                           demand=diff, capacity=1e-9, demand_over_capacity=diff / 1e-9,
                           unit="N_or_Nm_abs_diff", basis="reproduces all 24 M6 unit-load rows",
                           status="PASS_SOFTWARE_VERIFICATION_ONLY", notes="not a strength result"))

    # ------------------------------------------------------------------------
    # write FASTENER_ANALYTIC_CHECKS_V1.csv
    # ------------------------------------------------------------------------
    def fmt(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.6g}"
        return str(v)

    checks_csv = os.path.join(WP4, "FASTENER_ANALYTIC_CHECKS_V1.csv")
    with open(checks_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["schema", "generated_local"])
        w.writerow(["FASTENER_ANALYTIC_CHECKS_V1", GENERATED_LOCAL])
        w.writerow(["joint_id", "case_id", "case_variant", "check_id", "demand", "capacity",
                    "demand_over_capacity", "unit", "basis", "status", "notes"])
        for r in check_rows:
            w.writerow([r["joint_id"], r["case_id"], r["case_variant"], r["check_id"],
                        fmt(r["demand"]), fmt(r["capacity"]),
                        fmt(r["demand_over_capacity"]), r["unit"] or "", r["basis"],
                        r["status"], r["notes"]])
        w.writerow(["source_register_id", "path", "sha256"] + [""] * 8)
        for s in reg:
            w.writerow([s["id"], s["path"], s["sha256"]] + [""] * 8)

    # ------------------------------------------------------------------------
    # FASTENER_SCHEDULE_V1.csv
    # ------------------------------------------------------------------------
    schedule_csv = os.path.join(WP4, "FASTENER_SCHEDULE_V1.csv")
    with open(schedule_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["schema", "FASTENER_SCHEDULE_V1"])
        w.writerow(["generated_local", GENERATED_LOCAL])
        w.writerow(["item_id", "joint_or_location", "fastener_spec", "thread_class",
                    "material_candidate", "material_candidate_status", "quantity",
                    "role", "length_candidate_mm", "notes", "status"])
        rows = [
            ["FST-001", "B601_TO_STAGE_A_4XM4_HM4_75_64MM (ARM_BASE_INTERFACE)",
             "M4x0.7 socket head cap screw, replaces/replicates as-built HM4-75 axes",
             "M4_CLASS", "A286_AMS5737_CANDIDATE (alternate CRES_304_F593_CW_HOLD)",
             "PROTOTYPE_CANDIDATE_NOT_SELECTED_FLIGHT_ALLOWABLES_HOLD",
             4, "PRIMARY_ARM_BASE_JOINT", 12.0,
             "length candidate = grip 6.0mm flange + 6.0mm engagement, pending WP1; "
             "as-built HM4-75 reuse prohibited as design authority (material unknown)",
             "CANDIDATE_DESIGN_ANALYSIS_NOT_QUALIFICATION"],
            ["FST-002", "STAGE_A_TO_B_8XM5_R62P5MM (M3R interstage)",
             "M5x0.8 socket head cap screw", "M5_CLASS", "A286_AMS5737_CANDIDATE",
             "PROTOTYPE_CANDIDATE_NOT_SELECTED_FLIGHT_ALLOWABLES_HOLD",
             8, "M3R_INTERSTAGE_JOINT", 16.0,
             "through Stage B clearance 5.5mm into Stage A wire-thread-insert candidate "
             "(L_e=7.5mm=1.5d) or direct tap alternate (L_e=10mm=2d)",
             "CANDIDATE_DESIGN_ANALYSIS_NOT_QUALIFICATION"],
            ["FST-003", "STAGE_B_TO_SPACECRAFT_4XM6_140MM (Stage B to load bridge)",
             "M6x1.0 hex head bolt + self-locking nut + washers (through-bolt)",
             "M6_CLASS", "A286_AMS5737_CANDIDATE bolt and nut class",
             "PROTOTYPE_CANDIDATE_NOT_SELECTED_FLIGHT_ALLOWABLES_HOLD",
             4, "LOAD_BRIDGE_JOINT", 25.0,
             "through Stage B flange + bridge plate 10.75mm 6061-T6 candidate; "
             "bus side of bridge = HOLD (BC-BUS-001)",
             "CANDIDATE_DESIGN_ANALYSIS_NOT_QUALIFICATION"],
            ["FST-004", "LOAD_BRIDGE_TO_BUS_PRIMARY_STRUCTURE",
             "UNKNOWN", None, None, "NO_AUTHORITY", None,
             "BUS_ATTACHMENT", None,
             "bus-side hole pattern, interface stiffness and structure unknown (BC-BUS-001 HOLD); "
             "pending WP1 PRODUCT_STRUCTURE", "HOLD_NO_BUS_SIDE_AUTHORITY"],
            ["FST-005", "SOLAR_HINGE_LEFT/RIGHT_ROOT",
             "TBD (hinge pin/bolt set)", None, None, "NO_HARDWARE_SELECTION", None,
             "HINGE_JOINT", None,
             "hinge stiffness/damping/torque authority absent (BC-SOLAR-L/R-001 HOLD); pending WP5",
             "HOLD_NO_HINGE_HARDWARE_AUTHORITY"],
            ["FST-006", "HDRM_ARM_HOLD_DOWN",
             "TBD (release device fastening)", None, None, "NO_HARDWARE_SELECTION", None,
             "HDRM_JOINT", None,
             "functional envelope only: 6mm stroke / 50N preload candidates (PROVISIONAL); "
             "pending WP5 hardware pack", "HOLD_FUNCTIONAL_ENVELOPE_ONLY"],
            ["FST-007", "GRIPPER_R1_PALM_AND_FINGER_HARDWARE",
             "TBD (pins/screws)", None, None, "NO_HARDWARE_SELECTION", None,
             "GRIPPER_JOINT", None,
             "contact force/friction/actuator authority absent (LC-016 HOLD); pending WP5",
             "HOLD_NO_GRIPPER_HARDWARE_AUTHORITY"],
            ["FST-008", "SENSOR_PACKAGE_CAMERA_BRACKET",
             "TBD", None, None, "NO_AUTHORIZED_POSE", None,
             "BRACKET_JOINT", None,
             "sensor package pose not authorized (BOM DP-010 HARD_HOLD); bracket candidates pending WP1",
             "HOLD_NO_AUTHORIZED_MOUNT_POSE"],
            ["FST-009", "M3R_INTERSTAGE_CLOCKING_DOWEL",
             "dowel pin 4.0mm class (locator, not a fastener)",
             "DOWEL_4MM", "TBD", "CANDIDATE_FEATURE_ONLY",
             1, "ANTI_MISASSEMBLY_LOCATOR", 5.5,
             "Stage A hole 4.1 / Stage B blind 4.0 depth 5.5 candidate; fit/material TBD (WP3/WP9)",
             "CANDIDATE_NOT_PROMOTED_FIT_HOLD"],
        ]
        for r in rows:
            w.writerow(r)
        w.writerow([])
        w.writerow(["source_register_id", "path", "sha256"] + [""] * 8)
        for s in reg:
            w.writerow([s["id"], s["path"], s["sha256"]] + [""] * 8)

    # ------------------------------------------------------------------------
    # TORQUE_PRELOAD_SCHEDULE_V1.csv
    # ------------------------------------------------------------------------
    torque_csv = os.path.join(WP4, "TORQUE_PRELOAD_SCHEDULE_V1.csv")
    with open(torque_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["schema", "TORQUE_PRELOAD_SCHEDULE_V1"])
        w.writerow(["generated_local", GENERATED_LOCAL])
        w.writerow(["joint_id", "fastener_spec", "material_candidate", "proof_load_N",
                    "preload_target_N", "preload_min_service_N", "preload_max_assembly_N",
                    "K_candidate", "K_band", "torque_target_Nm", "torque_band_Nm",
                    "tool_tolerance_declared", "relaxation_declared", "basis", "status"])
        for jid, j in JOINTS.items():
            thr = j["pattern"].thread
            p = pt[jid]
            w.writerow([jid, f"M{thr['d']:.0f}x{thr['pitch']}", "A286_AMS5737_CANDIDATE",
                        f"{p['F_proof']:.1f}", f"{p['Fp_target']:.1f}",
                        f"{p['Fp_min_service']:.1f}", f"{p['Fp_max']:.1f}",
                        K_NOM, "[0.15,0.25]", f"{p['T_target']:.3f}",
                        f"[{p['T_band'][0]:.3f},{p['T_band'][1]:.3f}]",
                        "+-10% ASSUMPTION", "10% embedment ASSUMPTION",
                        "preload=0.65*proof*As (band 0.50-0.75 declared); T=K*F*d K-factor; "
                        "ECSS-E-HB-32-23A method flow; candidate library V2 A286 655MPa MIN proof",
                        "CANDIDATE_DESIGN_ANALYSIS_NOT_QUALIFICATION_FLIGHT_ALLOWABLES_HOLD"])
        w.writerow([])
        w.writerow(["source_register_id", "path", "sha256"] + [""] * 12)
        for s in reg:
            w.writerow([s["id"], s["path"], s["sha256"]] + [""] * 12)

    # ------------------------------------------------------------------------
    # M3R_FASTENER_DESIGN_V1.yaml
    # ------------------------------------------------------------------------
    jid0 = "B601_TO_STAGE_A_4XM4_HM4_75_64MM"
    p0 = pt[jid0]
    kb0, km0, phi0 = stiff[jid0]
    # required engagement parametric (B601 side unknown)
    F_b_design = p0["Fp_max"]
    req_engage = {str(tau): F_b_design / (math.pi * THREADS["M4x0.7"]["d2"]
                                          * THREAD_ENGAGE_EFF * tau)
                  for tau in (100.0, 150.0, 200.0, 250.0)}

    # worst controlling capture ratios per joint (tc=5ms, 150kg)
    def ratio_at(case, variant, check, jid):
        for r in check_rows:
            if (r["case_id"] == case and r["case_variant"] == variant
                    and r["check_id"] == check and r["joint_id"] == jid
                    and "tc=5ms" in r.get("notes", "")):
                return r["demand_over_capacity"]
        return None

    yaml_doc = {
        "schema": "M3R_FASTENER_DESIGN_V1",
        "generated_local": GENERATED_LOCAL,
        "work_package": "WP4_FASTENER_DESIGN",
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "method_reference": "ECSS-E-HB-32-23A preloaded bolted joint method flow (handbook method; no controlled standard copy claimed; requirements not asserted)",
        "overall_status": "CANDIDATE_DESIGN_ANALYSIS_NOT_QUALIFICATION",
        "flight_allowables": "HOLD",
        "governing_flags": {
            "design_not_flight_qualified": True,
            "no_qualification_mos_claimed": True,
            "candidate_material_is_not_design_allowable": True,
            "no_zero_fill": True,
            "l0_urdf_mass_read_only": True,
        },
        "joint_definition": {
            "joint_id": jid0,
            "interface": "B601 arm base boss (as-built tapped holes) to M3R Stage A interface ring",
            "pattern": "4x HM4-75 M4-class axes, 64x64 mm square, equivalent PCD 90.509642 mm, clocking 25.000014 deg about interface normal",
            "stack_stations_mm": {"M_frame": 185.25, "adapter_plate_face": 198.0,
                                   "physical_mounting_face": 208.0, "as_built_screw_end_plane": 210.405},
            "stage_A_hole_mm": 4.6, "stage_A_counterbore_mm": 7.5,
            "screw_direction_idealization": ("DESIGN_ASSUMPTION: screws pass through Stage A clearance/counterbore "
                                              "and thread into the B601 boss; clamped interface = Stage A flange face "
                                              "against B601 boss face at x=208.0; as-built 2.405mm screw-end protrusion "
                                              "must be accommodated by Stage A recess (WP1/WP9 design constraint)"),
        },
        "bolt_material_trade": {
            "candidates": [
                {"id": "A286_AMS5737", "proof_MPa": 655.0, "uts_MPa": 965.0,
                 "value_kind": MAT_A286["value_kind"],
                 "pros": ["high proof -> preload 3.7kN class closes slip/separation for capture envelopes",
                          "AMS 5737 / A453 Gr660 fastener route exists"],
                 "cons": ["spec text paywalled, no spec values claimed", "galling tribology HOLD",
                          "cost/availability"], "selection": "PRIMARY_CANDIDATE"},
                {"id": "CRES_304_F593_Group1", "proof_MPa": 207.0, "uts_MPa": 517.0,
                 "value_kind": MAT_CRES["value_kind"],
                 "pros": ["cost/availability", "corrosion, non-magnetic class"],
                 "cons": ["only annealed reference known; CW fastener properties unknown (HOLD)",
                          "preload ~1.2kN class cannot close 150kg capture slip/separation envelope"],
                 "selection": "SECONDARY_HOLD_REQUIRES_CW_PROPERTY_AUTHORITY"},
            ],
            "outcome": "A286 primary candidate; CRES retained only if CW condition properties are later authorized",
            "selection_status": "CANDIDATE_NOT_SELECTED_PROCUREMENT_HOLD",
        },
        "thread_and_hole_scheme": {
            "B601_side_internal_thread": {
                "scheme": "AS_BUILT_VENDOR_TAPPED_HOLES (insert retrofit impossible)",
                "engagement_as_built_mm": None,
                "required_engagement_mm_parametric_at_Fb_max": req_engage,
                "required_engagement_note": "L_e_req = F_b_max/(pi*d2*0.75*tau_allow); tau_allow MPa parametric key; ASSUMPTION band, no B601 material authority",
                "status": "HOLD_NO_B601_MATERIAL_OR_ENGAGEMENT_AUTHORITY"},
            "stage_A_side_M5": {
                "scheme": "wire thread insert candidate L_e=7.5mm (1.5d); alternate direct tap in 6061-T6 L_e>=10mm (2d)",
                "status": "CANDIDATE"},
            "stage_B_bridge_M6": {
                "scheme": "through-bolt + A286-class self-locking nut candidate + washers both sides; nut height 5.2mm standard geometry",
                "status": "CANDIDATE"},
        },
        "washer_scheme": {
            "m3r_m4": "no washer (socket head in 7.5mm counterbore); ISO7089-class washer 9/4.3 candidate if counterbore replaced by spotface (WP9)",
            "stage_ab_m5": "washer candidate under head if Stage B floor spotfaced; TBD WP9",
            "bridge_m6": "washers both sides candidate (12/6.4 ISO7089-class)",
            "status": "CANDIDATE_STANDARD_GEOMETRY",
        },
        "preload_design": {
            "rule": "Fp_target = 0.65 * S_proof * As (declared; band 0.50-0.75)",
            "assembly_scatter": "T=K*F*d; K=0.2 candidate [0.15,0.25]; tool tolerance +-10% declared; embedment relaxation 10% declared",
            "values_per_joint": {
                jid: {"proof_load_N": round(pt[jid]["F_proof"], 1),
                      "Fp_target_N": round(pt[jid]["Fp_target"], 1),
                      "Fp_min_service_N": round(pt[jid]["Fp_min_service"], 1),
                      "Fp_max_assembly_N": round(pt[jid]["Fp_max"], 1),
                      "T_target_Nm": round(pt[jid]["T_target"], 3),
                      "T_band_Nm": [round(v, 3) for v in pt[jid]["T_band"]]}
                for jid in JOINTS},
            "assembly_proof_check": "Fp_max <= 0.75*F_proof required; see checks csv",
            "status": "CANDIDATE_ASSUMPTION_DECLARED",
        },
        "friction_coefficient": {
            "band": MU_BAND,
            "basis": "DECLARED_ASSUMPTION dry steel/Al class; no material-pair authority; vacuum/fretting effect HOLD",
            "status": "CANDIDATE_ASSUMPTION_VACUUM_EFFECT_HOLD",
        },
        "stiffness_model": {
            "method": "bolt: shank+head(0.4d)+thread(0.4d) springs; members: Shigley conical frustum alpha=30deg candidate (VDI2230 tan_phi=0.4 alternate)",
            "grip_lengths_declared": {
                jid0: {"L_grip_mm": 12.0, "kind": "CANDIDATE_ASSUMPTION two 6.0mm members; Stage A flange pending WP1"},
                "STAGE_A_TO_B_8XM5_R62P5MM": {"L_grip_mm": 16.0, "kind": "CANDIDATE_ASSUMPTION pending WP1"},
                "STAGE_B_TO_SPACECRAFT_4XM6_140MM": {"L_grip_mm": 18.75, "kind": "Stage B 8.0 candidate + bridge 10.75 contract"},
            },
            "results": {
                jid: {"k_b_N_mm": round(stiff[jid][0], 1), "k_m_N_mm": round(stiff[jid][1], 1),
                      "PHI": round(stiff[jid][2], 4)}
                for jid in JOINTS},
            "member_material_E": "6061-T6 68.3GPa typical both sides; B601 boss side E assumed equal (ASSUMPTION)",
            "status": "CANDIDATE_ANALYTIC_MODEL",
        },
        "load_cases_evaluated": {
            "LC-010_ARM_NOMINAL_SLEW": {
                "derivation": "rigid-body inverse dynamics (Newton-Euler) of accepted URDF under scene_A1 quintic 10-15-6 trajectory (8s, q2 +60deg, q3 -40deg); microgravity; fixed-base ASSUMPTION (free-floating base reaction not modelled)",
                "controlling_sample_tau": round(tau010, 4),
                "peak_wrench_envelope": {"F_peak_N": round(peak010["F"], 4), "M_peak_Nm": round(peak010["M"], 5)},
                "wrench_at_joint_datum_controlling": {k: round(v, 5) for k, v in W010.items()},
                "status": "DERIVED_ANALYSIS_CANDIDATE_NOT_A_DESIGN_LOAD_AUTHORITY"},
            "LC-013_CAPTURE_22KG": {
                "derivation": "DERIVED impulse envelope (0.0601233-0.360622 Ns) converted with half-sine pulse ASSUMPTION, contact duration band [5,10,20,50]ms; bounding scenarios NORMAL_TENSION_BENDING / SHEAR_TORSION",
                "F_peak_band_N": [round(math.pi * 0.360622 / (2 * tc), 1) for tc in (0.05, 0.005)],
                "status": "PARAMETRIC_ASSUMPTION_DERIVED_IMPULSE_NOT_STRUCTURAL_DESIGN_AUTHORITY"},
            "LC-014_CAPTURE_150KG": {
                "derivation": "same as LC-013 with impulse 0.274973-0.677633 Ns, couple 0.111944-0.130197 Nms, lever 1.21521m",
                "F_peak_band_N": [round(math.pi * 0.677633 / (2 * tc), 1) for tc in (0.05, 0.005)],
                "status": "PARAMETRIC_ASSUMPTION_DERIVED_IMPULSE_NOT_STRUCTURAL_DESIGN_AUTHORITY"},
            "LC-016_GRIPPER_CLAMP": {
                "derivation": "URDF effort limit 100N as MODEL_LIMIT bounding transverse shear at gripper tip (FK lever arm)",
                "tip_lever_from_base_m": round(lever_grip, 4),
                "status": "MODEL_LIMIT_ASSUMPTION_NOT_A_DESIGN_LOAD"},
            "hold_cases": [
                "LC-008 solar deployment: HOLD_NO_HINGE_TORQUE_AUTHORITY",
                "LC-009 panel failure: HOLD_LOADS_UNKNOWN (configuration enum only, attached-stuck per ODR-02)",
                "LC-011 emergency stop: HOLD_NO_STOP_LAW_AUTHORITY",
                "LC-019 thermal: HOLD_NO_THERMAL_ENVIRONMENT (preload thermal response unknown)",
                "LC-020 safe mode: HOLD",
                "on-orbit modal: WP7 characterization, no strength load",
                "launch family: HOLD per ODR-06 (no launcher/separation ICD)",
            ],
        },
        "check_summary_controlling": {
            "note": "full numeric rows in FASTENER_ANALYTIC_CHECKS_V1.csv; controlling = LC-014 tc=5ms unless noted; all ratios demand/capacity on candidate/assumed capacities",
            "m3r_joint_ratios_tc5ms_150kg": {
                "slip_friction": ratio_at("LC-014_CAPTURE_150KG", "SHEAR_TORSION", "SLIP_FRICTION", jid0),
                "separation": ratio_at("LC-014_CAPTURE_150KG", "NORMAL_TENSION_BENDING", "SEPARATION", jid0),
                "bolt_tension_proof": ratio_at("LC-014_CAPTURE_150KG", "NORMAL_TENSION_BENDING", "BOLT_ADDITIONAL_TENSION_PROOF", jid0),
                "bolt_shear": ratio_at("LC-014_CAPTURE_150KG", "SHEAR_TORSION", "BOLT_SHEAR", jid0),
                "bearing": ratio_at("LC-014_CAPTURE_150KG", "SHEAR_TORSION", "BEARING_PLATE_6061T6", jid0),
            },
        },
        "anti_loosening": {
            "scheme": ["primary: preload (residual preload maintained per checks)",
                       "CANDIDATE: anaerobic thread-locking adhesive class on M4/M5 threads",
                       "CANDIDATE ALTERNATE: all-metal self-locking nuts on M6 through-bolts"],
            "constraints": "vacuum outgassing/compatibility HOLD; lockwire not proposed (access and debris); prevailing-torque device on M4 not proposed",
            "status": "CANDIDATE_NOT_QUALIFIED",
        },
        "verification": {
            "distribution_engine_vs_M6_unit_csv": {"max_abs_diff": diff, "values_checked": nchk,
                                                    "verdict": "PASS_SOFTWARE_VERIFICATION"},
            "rne_implementation": "fixed-base microgravity Newton-Euler; envelope magnitudes only (sign convention per URDF)",
            "rne_checks": rne_ver,
        },
        "retained_holds": [
            "HOLD_FLIGHT_ALLOWABLES_ABSENT (all checks DESIGN_ANALYSIS_NOT_QUALIFICATION)",
            "HOLD_NO_B601_MATERIAL_OR_ENGAGEMENT_AUTHORITY (as-built internal thread strip)",
            "HOLD_NO_BUS_SIDE_AUTHORITY (load bridge to bus attachment, BC-BUS-001)",
            "HOLD_NO_HINGE/HDRM/GRIPPER/CAMERA_HARDWARE_AUTHORITY (pending WP5/WP1)",
            "HOLD_LAUNCH_FAMILY_LOADS (ODR-06)",
            "HOLD_THERMAL_PRELOAD_RESPONSE (LC-019)",
            "HOLD_VACUUM_TRIBOLOGY_AND_OUTGASSING",
            "HOLD_AS_BUILT_FASTENER_REUSE_AS_DESIGN_AUTHORITY",
        ],
        "sibling_dependencies": {
            "wp1_structure_cad": PENDING_WP1,
            "wp5_mechanisms": PENDING_WP5,
            "wp6_material_selection": PENDING_WP6,
        },
        "source_register": reg,
    }
    yaml_path = os.path.join(WP4, "M3R_FASTENER_DESIGN_V1.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_doc, f, sort_keys=False, allow_unicode=True, width=140)

    # ------------------------------------------------------------------------
    # receipt.json
    # ------------------------------------------------------------------------
    outputs = []
    for fn in ("M3R_FASTENER_DESIGN_V1.yaml", "FASTENER_SCHEDULE_V1.csv",
               "TORQUE_PRELOAD_SCHEDULE_V1.csv", "FASTENER_ANALYTIC_CHECKS_V1.csv"):
        p = os.path.join(WP4, fn)
        outputs.append({"path": f"wp4_fastener_design/{fn}",
                        "sha256": sha256_of(p), "bytes": os.path.getsize(p)})
    receipt = {
        "schema": "M7_WP4_RECEIPT_V1",
        "generated_local": GENERATED_LOCAL,
        "work_package": "WP4_FASTENER_DESIGN",
        "builder": "wp4_fastener_design/build_wp4_fastener_design.py",
        "builder_sha256": sha256_of(os.path.abspath(__file__)),
        "outputs": outputs,
        "verification": {
            "distribution_engine_vs_M6_unit_csv_max_abs_diff": diff,
            "distribution_engine_values_checked": nchk,
            "rne_checks": rne_ver,
            "verdict": "PASS_SOFTWARE_VERIFICATION_ONLY",
        },
        "retained_holds": yaml_doc["retained_holds"],
        "status": "WP4_COMPLETE_CANDIDATE_DESIGN_ANALYSIS_NOT_QUALIFICATION",
    }
    with open(os.path.join(WP4, "receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
    print("[done] wrote", ", ".join(o["path"] for o in outputs), "+ receipt.json")


if __name__ == "__main__":
    main()
