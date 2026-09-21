# -*- coding: utf-8 -*-
"""AGENT-F1 / R2 full-flex closure Wave-3a round1: high-fidelity flexible wing model.

Builds the per-wing HF model: 3 flexible leaves (Euler-Bernoulli beam FE,
10 elements per leaf) + 2 inter-panel hinges (rotation-jump torsion springs)
+ root hinge spring to the fixed base (latched deployed state, ODR-32 bands).
Latch compliance stays folded into the inter-panel ktheta bands (upstream
card, HOLD_LATCH_GEOMETRY_NOT_MODELLED).  Hinge point masses (2 x 0.03 kg per
wing) are EXCLUDED from the kinetic energy per MC-A
(ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml, dynamic_mass_allocation_frozen
=true): they remain rigid, non-following interface masses in the structural
mass ledger only.  The same rigid-interface booking is applied to the root
hinge (0.05 kg), HDRM (0.08 kg) and harness (0.05 kg) masses; that extension
of MC-A is flagged explicitly in the YAML provenance file.

Scope limits (kept, not silently filled): no torsional DOFs (GJ band NULL,
SLOT-01), no freeplay/backlash (SLOT-05 NULL), no root-bracket compliance
beyond the root hinge spring (SLOT-04 NULL), no independent latch stiffness
(SLOT-03 NULL, folded).  Damping is NOT part of M/K; it enters the ROM stage
as a modal-zeta ASSUMPTION_BAND (literature-typical 0.001..0.02), never as a
point value.

Reads upstream files read-only (sha256 re-verified here).  Writes only into
this directory.  Pure numpy/scipy/hashlib/json.  No CAD/FEA/simulation
processes.  All outputs are CANDIDATE_PROVISIONAL_BANDS: release_credit=false,
next_stage_authorized=false.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.linalg import eigh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]  # project root
ECR = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2"
E21_JSON = (ROOT / "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results"
            / "E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json")

OUT_JSON = HERE / "SOLAR_R2_HF_FLEX_MODEL_V1.json"

# --- upstream parameters (verbatim values; provenance in the YAML file) ----
LEAF_M = 0.18            # kg per leaf (areal-density candidate 3.0 kg/m2, NOT measured)
LEAF_L = 0.200           # m span per leaf
LEAF_A = 0.300           # m chord (along hinge axis X_S)
LEAF_T = 0.0025          # m total thickness
EI_NOM = 11.109          # N m^2 nominal (sandwich estimate)
EI_LOW, EI_HIGH = 0.3 * EI_NOM, 3.0 * EI_NOM   # engineering band corners
K_ROOT = {"low": 50.0, "nominal": 200.0, "high": 800.0}      # N m/rad
K_INTER = {"low": 20.0, "nominal": 100.0, "high": 400.0}     # N m/rad
P0_Y, P0_Z = 0.1149, -0.10815   # root hinge point (y, z) in S frame, m
ZETA_BAND = (0.001, 0.02)       # ASSUMPTION_BAND (literature-typical modal damping)

MU = LEAF_M / LEAF_L                      # kg/m
RHOJ = MU * LEAF_T ** 2 / 12.0            # cross-section rotary inertia per length
I_LEAF_COM_X = LEAF_M / 12.0 * (LEAF_L ** 2 + LEAF_T ** 2)  # leaf spin about x (L2)

N_EL_LEAF = 10
N_EL = 3 * N_EL_LEAF                      # 30 elements, 31 nodes
LE = LEAF_L / N_EL_LEAF

HINGE_NODES = (N_EL_LEAF, 2 * N_EL_LEAF)  # nodes 10, 20 -> inter-panel hinges
CASES = {
    "nominal": (K_ROOT["nominal"], K_INTER["nominal"]),
    "all_low": (K_ROOT["low"], K_INTER["low"]),
    "all_high": (K_ROOT["high"], K_INTER["high"]),
    "root_low_inter_high": (K_ROOT["low"], K_INTER["high"]),
    "root_high_inter_low": (K_ROOT["high"], K_INTER["low"]),
}
EI_POINTS = {"EI_low": EI_LOW, "EI_nominal": EI_NOM, "EI_high": EI_HIGH}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --- DOF map -----------------------------------------------------------------
# Free DOFs: w at nodes 1..30 (root node 0 translationally fixed), theta at
# every node, doubled at the two hinge nodes (theta_L / theta_R).
def build_dof_map():
    w_dof = {n: n - 1 for n in range(1, N_EL + 1)}              # 0..29
    th_dof = {}
    idx = N_EL  # 30
    for n in range(0, N_EL + 1):
        if n in HINGE_NODES:
            th_dof[(n, "L")] = idx
            idx += 1
            th_dof[(n, "R")] = idx
            idx += 1
        else:
            th_dof[n] = idx
            idx += 1
    ndof = idx
    return w_dof, th_dof, ndof


W_DOF, TH_DOF, NDOF = build_dof_map()


def elem_dofs(e):
    """Global DOFs [w_a, th_a, w_b, th_b] of element e (nodes e, e+1)."""
    wa = W_DOF.get(e)        # None if constrained (node 0)
    wb = W_DOF[e + 1]
    if e in HINGE_NODES:
        ta = TH_DOF[(e, "R")]    # element outboard of hinge uses right rotation
    else:
        ta = TH_DOF[e]
    if (e + 1) in HINGE_NODES:
        tb = TH_DOF[(e + 1, "L")]
    else:
        tb = TH_DOF[e + 1]
    return [wa, ta, wb, tb]


def beam_matrices(EI):
    le = LE
    Ke = EI / le ** 3 * np.array([
        [12.0, 6 * le, -12.0, 6 * le],
        [6 * le, 4 * le ** 2, -6 * le, 2 * le ** 2],
        [-12.0, -6 * le, 12.0, -6 * le],
        [6 * le, 2 * le ** 2, -6 * le, 4 * le ** 2]])
    Me_t = MU * le / 420.0 * np.array([
        [156.0, 22 * le, 54.0, -13 * le],
        [22 * le, 4 * le ** 2, 13 * le, -3 * le ** 2],
        [54.0, 13 * le, 156.0, -22 * le],
        [-13 * le, -3 * le ** 2, -22 * le, 4 * le ** 2]])
    Me_r = RHOJ / (30.0 * le) * np.array([
        [36.0, 3 * le, -36.0, 3 * le],
        [3 * le, 4 * le ** 2, -3 * le, -le ** 2],
        [-36.0, -3 * le, 36.0, -3 * le],
        [3 * le, -le ** 2, -3 * le, 4 * le ** 2]])
    return Ke, Me_t + Me_r


def assemble_M():
    _, Me = beam_matrices(EI_NOM)  # mass is EI-independent
    M = np.zeros((NDOF, NDOF))
    for e in range(N_EL):
        d = elem_dofs(e)
        for a in range(4):
            if d[a] is None:
                continue
            for b in range(4):
                if d[b] is None:
                    continue
                M[d[a], d[b]] += Me[a, b]
    return M


def assemble_K_elastic(EI):
    Ke, _ = beam_matrices(EI)
    K = np.zeros((NDOF, NDOF))
    for e in range(N_EL):
        d = elem_dofs(e)
        for a in range(4):
            if d[a] is None:
                continue
            for b in range(4):
                if d[b] is None:
                    continue
                K[d[a], d[b]] += Ke[a, b]
    return K


def hinge_spring_matrix(k_root, k_inter):
    K = np.zeros((NDOF, NDOF))
    K[TH_DOF[0], TH_DOF[0]] += k_root
    for hn in HINGE_NODES:
        a, b = TH_DOF[(hn, "L")], TH_DOF[(hn, "R")]
        K[a, a] += k_inter
        K[b, b] += k_inter
        K[a, b] -= k_inter
        K[b, a] -= k_inter
    return K


def hf_modes(k_root, k_inter, EI, n_modes=10):
    K = assemble_K_elastic(EI) + hinge_spring_matrix(k_root, k_inter)
    w2, V = eigh(K, M_MAT)
    om = np.sqrt(np.maximum(w2, 0.0))
    return om[:n_modes] / (2.0 * math.pi), V[:, :n_modes]


def q_hinge_content(V):
    """L2-equivalent hinge coordinates of each HF mode:
    q = (theta_root, theta_jump_hinge1, theta_jump_hinge2)."""
    rows = np.array([
        V[TH_DOF[0], :],
        V[TH_DOF[(HINGE_NODES[0], "R")], :] - V[TH_DOF[(HINGE_NODES[0], "L")], :],
        V[TH_DOF[(HINGE_NODES[1], "R")], :] - V[TH_DOF[(HINGE_NODES[1], "L")], :],
    ])
    return rows  # 3 x n_modes


# --- L2 reference model (independent recomputation of the published chain) ---
def l2_mass_matrix():
    """Chain kinetic-energy mass matrix, numpy re-implementation of the
    published formulas (compute_flexible_appendage_r2.py semantics)."""

    def kinetic_energy(dq):
        # linearised about the DEPLOYED config q=0: leaf angles stay at pi/2,
        # dq is purely a rate vector (matches the published code semantics:
        # kinetic_energy(dq, q=(0,0,0))).
        psi = [math.pi / 2, math.pi / 2, math.pi / 2]
        dpsi = [dq[0], dq[0] + dq[1], dq[0] + dq[1] + dq[2]]
        up = [(math.cos(p), -math.sin(p)) for p in psi]
        T = 0.0
        vP = (0.0, 0.0)
        for i in range(3):
            vcom = (vP[0] + 0.5 * LEAF_L * dpsi[i] * up[i][0],
                    vP[1] + 0.5 * LEAF_L * dpsi[i] * up[i][1])
            T += 0.5 * LEAF_M * (vcom[0] ** 2 + vcom[1] ** 2)
            T += 0.5 * I_LEAF_COM_X * dpsi[i] ** 2
            vP = (vP[0] + LEAF_L * dpsi[i] * up[i][0],
                  vP[1] + LEAF_L * dpsi[i] * up[i][1])
        return T

    e = [np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])]
    M = np.zeros((3, 3))
    Te = [kinetic_energy(v) for v in e]
    for i in range(3):
        M[i, i] = 2.0 * Te[i]
        for j in range(i + 1, 3):
            M[i, j] = M[j, i] = kinetic_energy(e[i] + e[j]) - Te[i] - Te[j]
    return M


def l2_modes(k_root, k_inter):
    K = np.diag([k_root, k_inter, k_inter])
    w2, V = eigh(K, M_L2)
    return np.sqrt(w2) / (2.0 * math.pi), V


# --- L2-level participation factors (spec draft section 2) -------------------
def T_extended_l2(qd, vb, wb, wing):
    """Kinetic energy of the deployed (q=0) 3-leaf chain with base motion
    superposed: v_com -> v_com + v_b + w_b x r_com (S frame), leaf spin about
    x gets + w_b[0].  wing='L': chain along +y from P0; 'R': mirrored to -y."""
    sgn = 1.0 if wing == "L" else -1.0
    psi0 = sgn * math.pi / 2
    # linearised about the deployed config: leaf angles fixed at +/- pi/2,
    # qd is purely a rate vector (dpsi below), positions are the deployed ones
    psi = [psi0, psi0, psi0]
    dpsi = [qd[0], qd[0] + qd[1], qd[0] + qd[1] + qd[2]]
    # deployed direction u=(sin psi, cos psi) in (y,z)
    up = [(math.cos(p), -math.sin(p)) for p in psi]  # du/dpsi in (y,z)
    T = 0.0
    P = np.array([sgn * P0_Y, P0_Z])   # (y, z)
    vP = np.zeros(2)
    for i in range(3):
        vcom2 = vP + 0.5 * LEAF_L * dpsi[i] * np.array(up[i])
        P = P + LEAF_L * np.array([math.sin(psi[i]), math.cos(psi[i])])
        vP = vP + LEAF_L * dpsi[i] * np.array(up[i])
        # COM position of leaf i = outboard end minus half leaf vector
        r_com_y = P[0] - 0.5 * LEAF_L * math.sin(psi[i])
        r_com_z = P[1] - 0.5 * LEAF_L * math.cos(psi[i])
        r3 = np.array([0.0, r_com_y, r_com_z])
        v3 = np.array([0.0, vcom2[0], vcom2[1]]) + np.array(vb) + np.cross(np.array(wb), r3)
        T += 0.5 * LEAF_M * float(v3 @ v3)
        T += 0.5 * I_LEAF_COM_X * (dpsi[i] + wb[0]) ** 2
    return T


def cross_fd(func, n1, n2, h=1e-4):
    """Full second cross-derivative matrix d2 f / da db at a=b=0 by central
    differences (f is quadratic here, so the FD is exact to roundoff)."""
    B = np.zeros((n1, n2))
    for i in range(n1):
        for j in range(n2):
            def f2(a, b, i=i, j=j):
                qa = np.zeros(n1)
                qb = np.zeros(n2)
                qa[i] = a
                qb[j] = b
                return func(qa, qb)
            B[i, j] = (f2(h, h) - f2(h, -h) - f2(-h, h) + f2(-h, -h)) / (4.0 * h * h)
    return B


def l2_participation_numeric(wing):
    Bt = cross_fd(lambda qd, vb: T_extended_l2(qd, vb, (0.0, 0.0, 0.0), wing), 3, 3)
    Br = cross_fd(lambda qd, wb: T_extended_l2(qd, (0.0, 0.0, 0.0), wb, wing), 3, 3)
    return Bt, Br


def l2_participation_analytic(wing):
    """Chain-rule closed form.  1-based leaves i=1..3, hinge DOFs j=1..3.
    d v_com_i / d qd_j = L*(i-j+0.5) * up0  (j<=i, else 0), with
    up0 = (0,0,-1) for left wing and (0,0,+1) for the mirrored right wing.
    B_r[j, wx] += sum_i m (dv_i/dq_j) . (x_hat x r_i) + I_com * #(i>=j).
    x_hat x r = (0,-z,y); up0 has only a z component, so only y_i enters and
    z0 drops out at first order (verified numerically)."""
    sgn = 1.0 if wing == "L" else -1.0
    up0z = -1.0 if wing == "L" else 1.0
    Bt = np.zeros((3, 3))
    Br = np.zeros((3, 3))
    for j in range(1, 4):
        for i in range(j, 4):
            arm = LEAF_L * (i - j + 0.5)
            y_i = sgn * (P0_Y + (i - 0.5) * LEAF_L)
            Bt[j - 1, 2] += LEAF_M * arm * up0z
            Br[j - 1, 0] += LEAF_M * arm * up0z * y_i
        Br[j - 1, 0] += I_LEAF_COM_X * (4 - j)
    return Bt, Br


# --- HF-level participation factors ------------------------------------------
# 3-point Gauss quadrature on the element (exact for the integrands used).
_GX = [-math.sqrt(3.0 / 5.0), 0.0, math.sqrt(3.0 / 5.0)]
_GW = [5.0 / 9.0, 8.0 / 9.0, 5.0 / 9.0]


def hermite(s, le):
    xi = s / le
    N1 = 1 - 3 * xi ** 2 + 2 * xi ** 3
    N2 = le * (xi - 2 * xi ** 2 + xi ** 3)
    N3 = 3 * xi ** 2 - 2 * xi ** 3
    N4 = le * (-xi ** 2 + xi ** 3)
    return np.array([N1, N2, N3, N4])


def hermite_rot(s, le):
    xi = s / le
    return np.array([(-6 * xi + 6 * xi ** 2) / le,
                     1 - 4 * xi + 3 * xi ** 2,
                     (6 * xi - 6 * xi ** 2) / le,
                     -2 * xi + 3 * xi ** 2])  # dN/dy


def assemble_participation(wing):
    """B_t (NDOF x 3) and B_r (NDOF x 3) for the HF model.  By the planar
    kinematics only the v_z column of B_t and the w_x column of B_r are
    populated analytically; the other four columns are exactly zero and are
    verified numerically against the full 3D extended kinetic energy."""
    sgn = 1.0 if wing == "L" else -1.0
    Bt = np.zeros((NDOF, 3))
    Br = np.zeros((NDOF, 3))
    for e in range(N_EL):
        d = elem_dofs(e)
        b_vz = np.zeros(4)
        b_wx = np.zeros(4)
        for gx, gw in zip(_GX, _GW):
            s = 0.5 * LE * (1.0 + gx)
            wgt = 0.5 * LE * gw
            Nw = hermite(s, LE)
            Nr = hermite_rot(s, LE)
            y_abs = sgn * (P0_Y + (e * LE + s)) if wing == "L" else -(P0_Y + (e * LE + s))
            b_vz += MU * Nw * wgt
            b_wx += MU * Nw * y_abs * wgt + RHOJ * Nr * wgt
        for a in range(4):
            if d[a] is None:
                continue
            Bt[d[a], 2] += b_vz[a]
            Br[d[a], 0] += b_wx[a]
    return Bt, Br


def T_extended_hf(qd, vb, wb, wing):
    """Full 3D extended kinetic energy of the HF wing (numeric reference for
    the negative-control check of the analytic B matrices)."""
    sgn = 1.0 if wing == "L" else -1.0
    T = 0.0
    for e in range(N_EL):
        d = elem_dofs(e)
        qe = np.array([0.0 if dd is None else qd[dd] for dd in d])
        for gx, gw in zip(_GX, _GW):
            s = 0.5 * LE * (1.0 + gx)
            wgt = 0.5 * LE * gw
            Nw = hermite(s, LE)
            Nr = hermite_rot(s, LE)
            wd = float(Nw @ qe)
            thd = float(Nr @ qe)
            y_abs = sgn * (P0_Y + e * LE + s)
            r3 = np.array([0.0, y_abs, P0_Z])
            v3 = np.array([0.0, 0.0, wd]) + np.array(vb) + np.cross(np.array(wb), r3)
            T += wgt * 0.5 * MU * float(v3 @ v3)
            T += wgt * 0.5 * RHOJ * (thd + wb[0]) ** 2
    return T


def hf_participation_numeric(wing):
    Bt = cross_fd(lambda qd, vb: T_extended_hf(qd, vb, (0.0, 0.0, 0.0), wing), NDOF, 3)
    Br = cross_fd(lambda qd, wb: T_extended_hf(qd, (0.0, 0.0, 0.0), wb, wing), NDOF, 3)
    return Bt, Br


# --- verification helpers ------------------------------------------------------
def mac(a, b):
    a = np.asarray(a, float).ravel()
    b = np.asarray(b, float).ravel()
    return float((a @ b) ** 2 / ((a @ a) * (b @ b)))


M_MAT = assemble_M()
M_L2 = l2_mass_matrix()


def main():
    # V8 below temporarily rebuilds the module-level model at 20 el/leaf and
    # restores it afterwards; globals declared up front for the whole scope.
    global N_EL, LE, W_DOF, TH_DOF, NDOF, M_MAT, HINGE_NODES
    t0 = datetime.now(timezone(timedelta(hours=8))).isoformat()
    report = {"checks": {}, "errors": []}

    # --- V0: upstream hash re-verification (full 64-hex) ---------------------
    # Pins are loaded programmatically (never hand-transcribed): the 16-entry
    # full-hash addendum, plus the MC-A decision's evidence_links block for the
    # spec draft.  The MC-A decision itself carries no upstream pin (its policy
    # is SELF_REFERENCE_EXCLUDED); its computed hash is recorded, not checked.
    addendum = json.loads((ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
                           / "mpi_phys_dyn_bridge/round1_bridge/00_authority"
                           / "R2_FLEX_INPUT_INVENTORY_V1_FULLHASH_ADDENDUM_V1.json").read_text(encoding="utf-8"))
    used = {
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2_MODES.json",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/compute_flexible_appendage_r2.py",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_R2_MECHANISM_ANALYTICAL_LEDGER_V1.yaml",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V1.yaml",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V1.yaml",
        "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json",
    }
    hash_check = {}
    for ent in addendum["entries"]:
        if ent["path"] not in used:
            continue
        h = sha256_file(ROOT / ent["path"])
        ok = (h.lower() == ent["sha256"].lower())
        hash_check[ent["path"]] = {"sha256": h, "pin_source": "FULLHASH_ADDENDUM_V1", "match": ok}
        if not ok:
            report["errors"].append(f"HASH MISMATCH: {ent['path']}")
    # spec draft pin via MC-A evidence_links (regex on raw text, no YAML parser)
    mca_path = (ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
                / "mpi_phys_dyn_bridge/round1_bridge/decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml")
    mca_text = mca_path.read_text(encoding="utf-8")
    spec_rel = ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge"
                "/round1_bridge/r2_flex_prep/R2_ROM_PARTICIPATION_DAMPING_SPEC_DRAFT_V1.md")
    m = re.search(re.escape("path: " + spec_rel) + r"\s*\n\s*sha256:\s*([0-9A-Fa-f]{64})", mca_text)
    h = sha256_file(ROOT / spec_rel)
    ok = bool(m) and h.lower() == m.group(1).lower()
    hash_check[spec_rel] = {"sha256": h, "pin_source": "MC_A evidence_links", "match": ok}
    if not ok:
        report["errors"].append("HASH MISMATCH: spec draft (or pin not found in MC-A)")
    hash_check["decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml"] = {
        "sha256": sha256_file(mca_path),
        "pin_source": "NONE_UPSTREAM (SELF_REFERENCE_EXCLUDED policy); recorded only",
        "match": None}
    report["checks"]["V0_upstream_hash_reverification"] = hash_check

    e21 = json.loads(E21_JSON.read_text(encoding="utf-8"))

    # --- V1: L2 mass matrix vs e21 full-precision Mqq ------------------------
    mqq_e21 = np.array(e21["leaf_only"]["Mqq_kg_m2"])
    d_m = float(np.max(np.abs(M_L2 - mqq_e21)))
    report["checks"]["V1_L2_mass_matrix_recomputed"] = {
        "max_abs_diff_vs_e21_kg_m2": d_m,
        "e21_reproduction_bound_kg_m2": 4.999999997368221e-10,
        "Mqq_recomputed_kg_m2": M_L2.tolist(),
        "verdict": "MATCH" if d_m < 1e-12 else "FAIL",
    }

    # --- V2: L2 frequencies vs e21 full-precision reproduction ---------------
    five = {}
    max_df = 0.0
    for case, (kr, ki) in CASES.items():
        f, _ = l2_modes(kr, ki)
        ref = e21["leaf_only"]["cases"][[c["case"] for c in e21["leaf_only"]["cases"]].index(case)]
        ref_hz = ref["leaf_only_reproduced_hz"]
        df = [abs(a - b) for a, b in zip(f, ref_hz)]
        max_df = max(max_df, max(df))
        five[case] = {"l2_recomputed_hz": list(f), "e21_hz": ref_hz,
                      "max_abs_diff_hz": max(df)}
    report["checks"]["V2_L2_five_case_frequency_reproduction"] = {
        "per_case": five, "global_max_abs_diff_hz": max_df,
        "e21_G20_bound_hz": 4.840419126761475e-05,
        "verdict": "MATCH" if max_df < 1e-9 else "FAIL",
    }

    # --- V3: HF rigid limit vs L2 exact --------------------------------------
    # EI -> infinity recovers the rigid-leaf L2 chain.  A single extreme
    # multiplier is numerically meaningless (K/M contrast ~1e13 squares under
    # the eigh Cholesky reduction and crushes the small eigenvalues), so the
    # check is a multiplier sweep: the hinge-mode frequencies must approach
    # the L2 values monotonically at rate ~ 1/scale.
    rigid_trend = {}
    for scale in (1e2, 1e3, 1e4, 1e5):
        f_hf, _ = hf_modes(*CASES["nominal"], EI_NOM * scale, n_modes=3)
        f_l2, _ = l2_modes(*CASES["nominal"])
        rigid_trend[f"EI_x{scale:g}"] = {
            "hf_hz": list(f_hf),
            "rel_diff_vs_l2": [abs(a - b) / b for a, b in zip(f_hf, f_l2)],
        }
    rigid_cases = {}
    max_rel_cases = 0.0
    for case, (kr, ki) in CASES.items():
        f_hf, _ = hf_modes(kr, ki, EI_NOM * 1e4, n_modes=3)
        f_l2, _ = l2_modes(kr, ki)
        rel = [abs(a - b) / b for a, b in zip(f_hf, f_l2)]
        max_rel_cases = max(max_rel_cases, max(rel))
        rigid_cases[case] = {"hf_hz_at_EI_x1e4": list(f_hf), "l2_hz": list(f_l2),
                             "max_rel_diff": max(rel)}
    trend_best = max(rigid_trend[f"EI_x{1e5:g}"]["rel_diff_vs_l2"])
    report["checks"]["V3_rigid_limit_vs_L2"] = {
        "nominal_multiplier_trend": rigid_trend,
        "five_cases_at_EI_x1e4": rigid_cases,
        "five_cases_max_rel_diff_at_EI_x1e4": max_rel_cases,
        "note": ("residual scales ~ 1/scale (remaining beam compliance); "
                 "verified monotone approach to the published L2 values; "
                 "EI x 1e9 rejected as ill-conditioned (Cholesky contrast)"),
        "verdict": "MATCH" if (max_rel_cases < 1e-3 and trend_best < max_rel_cases) else "FAIL",
    }

    # --- V4: single-leaf cantilever vs analytic beta1 -------------------------
    # clamped leaf: rebuild a small standalone model (w=theta=0 at root)
    def cantilever_f1(EI, n_el=10):
        le = LEAF_L / n_el
        Ke, Me = beam_matrices(EI)
        ndof = 2 * (n_el + 1)
        K = np.zeros((ndof, ndof))
        M = np.zeros((ndof, ndof))
        # reuse generic element with le override: build directly
        Ke = EI / le ** 3 * np.array([
            [12.0, 6 * le, -12.0, 6 * le],
            [6 * le, 4 * le ** 2, -6 * le, 2 * le ** 2],
            [-12.0, -6 * le, 12.0, -6 * le],
            [6 * le, 2 * le ** 2, -6 * le, 4 * le ** 2]])
        Me = MU * le / 420.0 * np.array([
            [156.0, 22 * le, 54.0, -13 * le],
            [22 * le, 4 * le ** 2, 13 * le, -3 * le ** 2],
            [54.0, 13 * le, 156.0, -22 * le],
            [-13 * le, -3 * le ** 2, -22 * le, 4 * le ** 2]])
        Me_r = RHOJ / (30.0 * le) * np.array([
            [36.0, 3 * le, -36.0, 3 * le],
            [3 * le, 4 * le ** 2, -3 * le, -le ** 2],
            [-36.0, -3 * le, 36.0, -3 * le],
            [3 * le, -le ** 2, -3 * le, 4 * le ** 2]])
        Me = Me + Me_r
        for e in range(n_el):
            d = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
            for a in range(4):
                for b in range(4):
                    K[d[a], d[b]] += Ke[a, b]
                    M[d[a], d[b]] += Me[a, b]
        free = list(range(2, ndof))
        w2, _ = eigh(K[np.ix_(free, free)], M[np.ix_(free, free)])
        return math.sqrt(w2[0]) / (2 * math.pi)

    beta1 = 1.87510407
    f1_analytic = (beta1 ** 2 / (2.0 * math.pi * LEAF_L ** 2)) * math.sqrt(EI_NOM / MU)
    f1_fe = cantilever_f1(EI_NOM)
    report["checks"]["V4_leaf_cantilever_vs_analytic"] = {
        "fe_f1_hz": f1_fe, "analytic_f1_hz": f1_analytic,
        "rel_diff": abs(f1_fe - f1_analytic) / f1_analytic,
        "published_card_nominal_hz": 49.15,
        "verdict": "MATCH" if abs(f1_fe - f1_analytic) / f1_analytic < 1e-4 else "FAIL",
    }

    # --- V5: rigid-limit MAC between HF hinge content and L2 modes -----------
    f_r, V_r = hf_modes(*CASES["nominal"], EI_NOM * 1e4, n_modes=3)
    _, V_l2 = l2_modes(*CASES["nominal"])
    qh = q_hinge_content(V_r)  # 3 x 3
    mac_rigid = [[mac(qh[:, i], V_l2[:, j]) for j in range(3)] for i in range(3)]
    report["checks"]["V5_rigid_limit_MAC"] = {
        "mac_matrix_hf_vs_l2_at_EI_x1e4": mac_rigid,
        "min_diagonal": min(mac_rigid[i][i] for i in range(3)),
        "verdict": "MATCH" if min(mac_rigid[i][i] for i in range(3)) > 1.0 - 1e-6 else "FAIL",
    }

    # --- V6/V7: participation factors ----------------------------------------
    part = {}
    for wing in ("L", "R"):
        Bt_a, Br_a = l2_participation_analytic(wing)
        Bt_n, Br_n = l2_participation_numeric(wing)
        part[wing] = {
            "B_t_analytic": Bt_a.tolist(), "B_r_analytic": Br_a.tolist(),
            "B_t_max_abs_diff_analytic_vs_numeric": float(np.max(np.abs(Bt_a - Bt_n))),
            "B_r_max_abs_diff_analytic_vs_numeric": float(np.max(np.abs(Br_a - Br_n))),
            "B_t_zero_columns_max_abs": float(max(np.max(np.abs(Bt_n[:, 0])), np.max(np.abs(Bt_n[:, 1])))),
            "B_r_zero_columns_max_abs": float(max(np.max(np.abs(Br_n[:, 1])), np.max(np.abs(Br_n[:, 2])))),
        }
    # HF level: analytic assembly vs full-3D numeric FD
    Bt_hf, Br_hf = assemble_participation("L")
    Bt_hfn, Br_hfn = hf_participation_numeric("L")
    hf_check = {
        "B_t_max_abs_diff_analytic_vs_numeric": float(np.max(np.abs(Bt_hf - Bt_hfn))),
        "B_r_max_abs_diff_analytic_vs_numeric": float(np.max(np.abs(Br_hf - Br_hfn))),
        "B_t_numeric_zero_columns_max_abs": float(max(np.max(np.abs(Bt_hfn[:, 0])), np.max(np.abs(Bt_hfn[:, 1])))),
        "B_r_numeric_zero_columns_max_abs": float(max(np.max(np.abs(Br_hfn[:, 1])), np.max(np.abs(Br_hfn[:, 2])))),
    }
    # sum rules over the complete HF eigenbasis
    w2_all, V_all = eigh(assemble_K_elastic(EI_NOM) + hinge_spring_matrix(*CASES["nominal"]), M_MAT)
    gt = V_all.T @ Bt_hf[:, 2]
    gr = V_all.T @ Br_hf[:, 0]
    sum_t = float(gt @ gt)
    sum_r = float(gr @ gr)
    # reference: b^T M^-1 b
    ref_t = float(Bt_hf[:, 2] @ np.linalg.solve(M_MAT, Bt_hf[:, 2]))
    ref_r = float(Br_hf[:, 0] @ np.linalg.solve(M_MAT, Br_hf[:, 0]))
    # analytic references: total leaf mass; sum over leaves of integral mu*y^2 + rhoj
    mass_ref = 3 * LEAF_M
    iy_ref = 0.0
    for i in range(3):
        y_c = P0_Y + (i + 0.5) * LEAF_L
        iy_ref += LEAF_M * (y_c ** 2 + LEAF_L ** 2 / 12.0) + RHOJ * LEAF_L
    hf_check["sum_rule_translational_vz"] = {
        "sum_over_all_modes": sum_t, "bMinv_b": ref_t,
        "analytic_total_leaf_mass_kg": mass_ref,
        "rel_diff_vs_analytic": abs(sum_t - mass_ref) / mass_ref,
    }
    hf_check["sum_rule_rotational_wx"] = {
        "sum_over_all_modes": sum_r, "bMinv_b": ref_r,
        "analytic_leaf_inertia_about_x_at_S_kg_m2": iy_ref,
        "rel_diff_vs_analytic": abs(sum_r - iy_ref) / iy_ref,
    }
    part["hf_checks"] = hf_check
    report["checks"]["V6_V7_participation_factors"] = part

    # --- V8: discretization convergence 10 vs 20 elements per leaf -----------
    f10, _ = hf_modes(*CASES["nominal"], EI_NOM, n_modes=8)
    saved = (N_EL, LE, W_DOF, TH_DOF, NDOF, M_MAT)
    saved_hn = HINGE_NODES
    N_EL = 3 * 20
    LE = LEAF_L / 20
    HINGE_NODES = (20, 40)
    W_DOF, TH_DOF, NDOF = build_dof_map()
    M_MAT = assemble_M()
    f20, _ = hf_modes(*CASES["nominal"], EI_NOM, n_modes=8)
    rel8 = [abs(a - b) / b for a, b in zip(f10, f20)]
    report["checks"]["V8_mesh_convergence_10_vs_20_per_leaf_nominal"] = {
        "f_10_per_leaf_hz": list(f10), "f_20_per_leaf_hz": list(f20),
        "rel_diff_first8": rel8,
        "max_rel_diff_retained_first5": max(rel8[:5]),
        "note": "criterion applied to the 5 ROM-retained modes; higher modes shown for information",
        "verdict": "CONVERGED" if max(rel8[:5]) < 1e-4 else "REFINE",
    }
    N_EL, LE, W_DOF, TH_DOF, NDOF, M_MAT = saved
    HINGE_NODES = saved_hn

    # --- full sweep: 5 cases x 3 EI points ------------------------------------
    sweep = {}
    for case, (kr, ki) in CASES.items():
        sweep[case] = {"k_root_Nm_per_rad": kr, "k_inter_Nm_per_rad": ki, "per_ei": {}}
        for ei_name, ei_val in EI_POINTS.items():
            f, V = hf_modes(kr, ki, ei_val, n_modes=10)
            sweep[case]["per_ei"][ei_name] = {
                "EI_Nm2": ei_val,
                "frequencies_hz_first10": list(f),
                "eigenvectors_first8_mass_normalized": V[:, :8].tolist(),
                "hinge_content_first8": q_hinge_content(V[:, :8]).tolist(),
            }

    # store M and K_elastic blocks + nominal assembled K
    store = {
        "schema": "SOLAR_R2_HF_FLEX_MODEL_V1",
        "generated_local": t0,
        "generator": "AGENT-F1 R2 full-flex closure Wave-3a round1 (pure numpy/scipy; read-only upstream)",
        "class": "CANDIDATE_PROVISIONAL_BANDS__NOT_CERTIFIED",
        "release_credit": False,
        "next_stage_authorized": False,
        "model_definition": {
            "type": "per-wing Euler-Bernoulli beam FE chain, planar (y,z) bending about X_S",
            "elements_per_leaf": 10, "leaves_per_wing": 3, "n_elements": 30,
            "element_length_m": LE, "ndof_free": NDOF,
            "dof_order": "w nodes 1..30 -> dof 0..29; theta node0 -> 30; theta nodes1..9 -> 31..39; "
                          "theta node10 L/R -> 40/41; theta nodes11..19 -> 42..50; theta node20 L/R -> 51/52; "
                          "theta nodes21..30 -> 53..62",
            "root_boundary": "w(node0)=0 (revolute attach); k_root torsion spring on theta(node0) to ground",
            "hinge_model": "rotation jump at nodes 10 and 20, torsion spring k_inter between theta_L and theta_R",
            "mass_model": "leaf consistent mass + cross-section rotary inertia rhoj=mu*T^2/12; "
                          "hinge/root/HDRM/harness masses EXCLUDED from kinetic energy per MC-A "
                          "(rigid non-following interface booking in structural mass ledger)",
            "excluded_scope": ["torsion DOFs (GJ band NULL, SLOT-01)",
                               "freeplay/backlash (SLOT-05 NULL)",
                               "root-bracket compliance beyond k_root (SLOT-04 NULL)",
                               "independent latch stiffness (SLOT-03 NULL, folded into inter-panel bands)",
                               "damping matrix (injected at ROM stage as zeta ASSUMPTION_BAND)"],
        },
        "parameters": {
            "leaf_mass_kg": LEAF_M, "leaf_span_m": LEAF_L, "leaf_chord_m": LEAF_A,
            "leaf_thickness_m": LEAF_T, "mu_kg_per_m": MU, "rhoj_kg_m": RHOJ,
            "EI_Nm2": {"nominal": EI_NOM, "low": EI_LOW, "high": EI_HIGH},
            "k_root_Nm_per_rad": K_ROOT, "k_inter_Nm_per_rad": K_INTER,
            "root_hinge_point_S_m": {"y": P0_Y, "z": P0_Z},
        },
        "mass_matrix_kg_m2": M_MAT.tolist(),
        "K_elastic_per_ei_Nm2": {k: assemble_K_elastic(v).tolist() for k, v in EI_POINTS.items()},
        "hinge_spring_topology": {
            "root_theta_dof": TH_DOF[0],
            "hinge1_theta_L_dof": TH_DOF[(HINGE_NODES[0], "L")],
            "hinge1_theta_R_dof": TH_DOF[(HINGE_NODES[0], "R")],
            "hinge2_theta_L_dof": TH_DOF[(HINGE_NODES[1], "L")],
            "hinge2_theta_R_dof": TH_DOF[(HINGE_NODES[1], "R")],
            "assembly_rule": "K(case,EI) = K_elastic(EI) + k_root*E(root) + k_inter*(E(hinge1)+E(hinge2))",
        },
        "K_assembled_nominal": (assemble_K_elastic(EI_NOM) + hinge_spring_matrix(*CASES["nominal"])).tolist(),
        "participation_hf_left": {"B_t": assemble_participation("L")[0].tolist(),
                                  "B_r": assemble_participation("L")[1].tolist()},
        "participation_hf_right": {"B_t": assemble_participation("R")[0].tolist(),
                                   "B_r": assemble_participation("R")[1].tolist()},
        "participation_l2_per_spec_section2": {
            wing: {"B_t": l2_participation_analytic(wing)[0].tolist(),
                   "B_r": l2_participation_analytic(wing)[1].tolist()}
            for wing in ("L", "R")
        },
        "sweep_5_cases_x_3_ei": sweep,
        "l2_reference_per_case": {
            case: {"frequencies_hz": list(l2_modes(kr, ki)[0]),
                   "eigenvectors_mass_normalized": l2_modes(kr, ki)[1].tolist(),
                   "K_Nm_per_rad": [[kr, 0.0, 0.0], [0.0, ki, 0.0], [0.0, 0.0, ki]],
                   "Mqq_kg_m2": M_L2.tolist()}
            for case, (kr, ki) in CASES.items()
        },
        "verification": report["checks"],
        "errors": report["errors"],
    }
    OUT_JSON.write_text(json.dumps(store, indent=1), encoding="utf-8")
    print("HF_MODEL_OK")
    print(json.dumps({k: (v.get("verdict") if isinstance(v, dict) else None)
                      for k, v in report["checks"].items()}, indent=1))
    print("errors:", report["errors"])
    f_nom = sweep["nominal"]["per_ei"]["EI_nominal"]["frequencies_hz_first10"][:8]
    print("nominal first8 Hz:", [round(x, 4) for x in f_nom])


if __name__ == "__main__":
    main()
