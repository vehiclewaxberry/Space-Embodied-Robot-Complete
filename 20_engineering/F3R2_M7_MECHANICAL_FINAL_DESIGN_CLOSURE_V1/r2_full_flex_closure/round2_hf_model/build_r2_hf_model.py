# -*- coding: utf-8 -*-
"""AGENT-B1 / R2 full-flex closure Wave-4a round2: R2 high-fidelity
three-leaf-per-wing flexible model (Full-Flex F1).

Per wing (deployed latched flat configuration; kinematic conventions follow
FLEXIBLE_APPENDAGE_R2.yaml verbatim - hinge axes parallel X_S, planar (y,z)
bending motion):

    root hinge (k_theta_root band 50/200/800 N m/rad)
      -> leaf 1 flexible (Euler-Bernoulli FE, default 20 elements)
      -> hinge 2 (k_theta_inter band 20/100/400)
      -> leaf 2 flexible
      -> hinge 3 (k_theta_inter)
      -> leaf 3 flexible

NEW lanes relative to the frozen round1 HF candidate (which stays untouched):
  * torsion lane: every leaf also carries a torsion DOF phi about its
    spanwise (y) axis with stiffness GJ.  GJ has NO registered upstream
    value; per the Wave-4a owner directive a candidate band is DERIVED here
    from the registered candidate construction (2 x 0.2 mm CFRP faces,
    E=70 GPa quasi-iso, nu=0.3 candidate; 2.1 mm core; 2.5 mm total):
      lower bound = open-section St-Venant  GJ_low  = chord/3 * (2*G_f*t_f^3 + G_c*t_c^3)
      upper bound = closed-cell Bredt-Batho GJ_high = 4*A_m^2 / (2*chord/(G_f*t_f))
      nominal     = geometric mean of the band
    class PROVISIONAL_DERIVED, basis written out in the model card,
    measurement claim FORBIDDEN.
  * damping lane: modal zeta candidate band [0.002, 0.02], nominal 0.005
    (Wave-4a directive nominal), class PROVISIONAL_DERIVED, documented as a
    bounded assumption for CFRP sandwich + hinge chain - NOT a measurement.
    Dual-lane discipline kept: zeta=0 conservation-audit lane (all M/K
    eigen evidence in this package) vs zeta!=0 dissipation-prediction lane
    (report-only damped-frequency/decay mapping).  The legacy placeholders
    (card zeta=0.01 TBD_cite_literature; sim_11 zeta_modal=0.005
    placeholder) are NOT consumed as authority; this band is a NEW derived
    record that never quotes them as source.
  * latch: independent latch stiffness stays null (HOLD,
    HOLD_LATCH_GEOMETRY_NOT_MODELLED).  Per SLOT-03 the inter-panel
    k_theta band [20, 100, 400] N m/rad is propagated as the
    latch-inclusive deployed-state compliance; this file says so explicitly.

Hinge/interfacial masses follow MC-A
(ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml, dynamic_mass_allocation_frozen
=true): root hinge 0.05 kg, inter hinges 2 x 0.03 kg, HDRM 0.08 kg, harness
0.05 kg are RIGID NON-TRACKING interface masses booked at the hinge lines in
the structural mass ledger ONLY - they are excluded from the HF kinetic
energy (bookkeeping BK-DYN-MASS-HINGE-ALLOC-MC-A).  Mass closure: kinetic
leaf mass 3 x 0.18 = 0.54 kg + rigid ledger 0.24 kg = 0.78 kg/wing exact
(SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json mass model).

Explicitly documented model EXTENSIONS relative to the registered card:
  E-1 leaves are flexible FE beams here (the L2 ROM is a rigid-leaf chain);
  E-2 torsion DOFs are added (card GJ slot was NULL/"pending");
  E-3 torsion root boundary = clamped phi(node0)=0 (root-bracket torsional
      compliance is SLOT-04 NULL; clamping is the reference boundary);
  E-4 torsion is transmitted continuously through the inter-panel hinges
      (no registered hinge torsional compliance exists).

Scope limits kept verbatim (never zero-filled): no freeplay/backlash
(SLOT-05 NULL), no root-bracket compliance beyond k_theta_root (SLOT-04
NULL), no independent latch stiffness (SLOT-03 NULL, folded), no base
coupling/participation factors here (SLOT-07 - later work package).

Runtime: pure python + numpy/scipy (eigh); a few hundred DOF.  Reads
upstream files read-only; every cited pin is recomputed (full 64-hex) and
recorded in verification_record.  Writes ONLY into this directory.
Legacy R1-lane values are never consumed; a blacklist self-scan over the
emitted files is part of the validation gate.

Outputs (same directory):
  R2_FULLFLEX_HF_MODEL_V1.yaml / .md      - model card (machine + human)
  R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json / .md - eigen/assembly evidence
  R2_FULLFLEX_HF_VALIDATION_GATE_V1.json / .md - fail-closed gate
  README.md                               - directory guide

All outputs: review_status=PENDING_OWNER_REVIEW, next_stage_authorized=false,
release_credit=false.  Comparison vs the ROM witnesses is REPORT ONLY - no
tuning is performed or permitted by this script.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml
from scipy.linalg import eigh

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # project root
ECR = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2"
BRIDGE = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge"
E21_JSON = (ROOT / "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results"
            / "E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json")
ODR45_YAML = (ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority"
              / "M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml")

OUT_CARD_YAML = HERE / "R2_FULLFLEX_HF_MODEL_V1.yaml"
OUT_CARD_MD = HERE / "R2_FULLFLEX_HF_MODEL_V1.md"
OUT_EVID_JSON = HERE / "R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json"
OUT_EVID_MD = HERE / "R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.md"
OUT_GATE_JSON = HERE / "R2_FULLFLEX_HF_VALIDATION_GATE_V1.json"
OUT_GATE_MD = HERE / "R2_FULLFLEX_HF_VALIDATION_GATE_V1.md"
OUT_README = HERE / "README.md"

WAVE = "KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure)"
GENERATOR = WAVE + " / AGENT-B1 round2_hf_model builder (pure numpy/scipy; upstream read-only)"
SELF_HASH_POLICY = ("SELF_REFERENCE_EXCLUDED - this file carries no hash of itself; "
                    "downstream consumers pin its sha256 after emission (same policy as "
                    "e21/V5 manifests and 02_bridge)")

# --- upstream registered parameters (verbatim; provenance in the card) ------
LEAF_M = 0.18            # kg per leaf (areal-density candidate 3.0 kg/m2, NOT measured)
LEAF_L = 0.200           # m span per leaf (cantilever direction)
LEAF_A = 0.300           # m chord (along hinge axis X_S)
LEAF_T = 0.0025          # m total assembly thickness
EI_NOM = 11.109          # N m^2 nominal sandwich estimate (PROVISIONAL_DERIVED, carried)
EI_LOW, EI_HIGH = 3.333, 33.327          # registered band corners (carried)
K_ROOT = {"low": 50.0, "nominal": 200.0, "high": 800.0}     # N m/rad (registered band)
K_INTER = {"low": 20.0, "nominal": 100.0, "high": 400.0}    # N m/rad (registered band, latch-inclusive)
P0_Y, P0_Z = 0.1149, -0.10815   # root hinge point (y, z) in S frame, m (context only)

# MC-A rigid non-tracking interface masses (excluded from kinetic energy)
M_HINGE_ROOT = 0.05
M_HINGE_INTER_EACH = 0.03
M_HDRM = 0.08
M_HARNESS = 0.05
M_RIGID_LEDGER = M_HINGE_ROOT + 2 * M_HINGE_INTER_EACH + M_HDRM + M_HARNESS  # 0.24
M_WING_TOTAL = 3 * LEAF_M + M_RIGID_LEDGER                                   # 0.78

# --- leaf candidate construction for the GJ derivation -----------------------
E_FACES = 70.0e9         # Pa, quasi-isotropic CFRP faces candidate (registered)
NU_FACE = 0.3            # candidate Poisson ratio (PROVISIONAL_DERIVED)
G_FACE = E_FACES / (2.0 * (1.0 + NU_FACE))          # 26.923 GPa
T_FACE = 0.2e-3          # m per face (2 faces)
T_CORE = 2.1e-3          # m core
G_CORE = 100.0e6         # Pa, generic low-modulus sandwich core candidate (PROVISIONAL_DERIVED)

# open-section St-Venant lower bound: components act independently, free warping
GJ_LOW = LEAF_A / 3.0 * (2.0 * G_FACE * T_FACE ** 3 + G_CORE * T_CORE ** 3)
# closed-cell Bredt-Batho upper bound: cell = sandwich cross-section (width =
# chord, height = mid-face distance t_core + t_face); faces are the only
# compliant walls, edge closures assumed rigid (potting/edge members)
H_CELL = T_CORE + T_FACE
A_CELL = LEAF_A * H_CELL
BREDT_DEN = 2.0 * LEAF_A / (G_FACE * T_FACE)
GJ_HIGH = 4.0 * A_CELL ** 2 / BREDT_DEN
GJ_NOM = math.sqrt(GJ_LOW * GJ_HIGH)   # geometric-mean nominal

# torsion mass inertia per unit length about the spanwise axis: mu * chord^2 / 12
MU = LEAF_M / LEAF_L                       # kg/m
RHOJ = MU * LEAF_T ** 2 / 12.0             # cross-section rotary inertia per length (bending)
JM_TORSION = MU * LEAF_A ** 2 / 12.0       # kg m / m, polar about spanwise axis

ZETA_BAND = (0.002, 0.02)
ZETA_NOM = 0.005   # Wave-4a directive nominal; NEW derived record (not a legacy placeholder quote)

N_LEAF_DEFAULT = 20
I_LEAF_COM_X = LEAF_M / 12.0 * (LEAF_L ** 2 + LEAF_T ** 2)  # leaf spin about x (L2 ROM)

STIFFNESS_CASES = {
    "nominal": (K_ROOT["nominal"], K_INTER["nominal"]),
    "all_low": (K_ROOT["low"], K_INTER["low"]),
    "all_high": (K_ROOT["high"], K_INTER["high"]),
    "root_low_inter_high": (K_ROOT["low"], K_INTER["high"]),
    "root_high_inter_low": (K_ROOT["high"], K_INTER["low"]),
}
EI_POINTS = {"EI_low": EI_LOW, "EI_nominal": EI_NOM, "EI_high": EI_HIGH}
GJ_POINTS = {"GJ_low": GJ_LOW, "GJ_nominal": GJ_NOM, "GJ_high": GJ_HIGH}

# R1-lane forbidden needles (detector definitions; never consumed as values)
NEEDLES = ["29.226410622980581", "0.3483933", "1.7419665", "measured_mass", "24.0 kg legacy"]

TZ = timezone(timedelta(hours=8))
T0 = datetime.now(TZ).isoformat()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# HF wing model (bending lane + torsion lane, block-decoupled)
# ---------------------------------------------------------------------------
class WingModel:
    """Per-wing HF chain: 3 leaves x n_leaf EB beam elements; root node 0
    translational w fixed + k_root torsion spring on theta(node0); doubled
    theta at the two inter-panel hinge nodes with k_inter jump springs;
    torsion phi at nodes 1..3n (phi(0)=0 clamped), continuous through hinges.
    """

    def __init__(self, n_leaf: int):
        self.n = n_leaf
        self.n_el = 3 * n_leaf
        self.le = LEAF_L / n_leaf
        self.hinge_nodes = (n_leaf, 2 * n_leaf)
        # bending DOFs
        self.w_dof = {nn: nn - 1 for nn in range(1, self.n_el + 1)}
        self.th_dof = {}
        idx = self.n_el
        for nn in range(0, self.n_el + 1):
            if nn in self.hinge_nodes:
                self.th_dof[(nn, "L")] = idx
                idx += 1
                self.th_dof[(nn, "R")] = idx
                idx += 1
            else:
                self.th_dof[nn] = idx
                idx += 1
        self.n_bend = idx
        # torsion DOFs (continuous through hinges; node 0 clamped)
        self.phi_dof = {nn: self.n_bend + (nn - 1) for nn in range(1, self.n_el + 1)}
        self.ndof = self.n_bend + self.n_el

    def beam_elem(self, EI):
        le = self.le
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

    def torsion_elem(self, GJ):
        le = self.le
        Ke = GJ / le * np.array([[1.0, -1.0], [-1.0, 1.0]])
        Me = JM_TORSION * le / 6.0 * np.array([[2.0, 1.0], [1.0, 2.0]])
        return Ke, Me

    def bend_elem_dofs(self, e):
        wa = self.w_dof.get(e)            # None at constrained node 0
        wb = self.w_dof[e + 1]
        ta = self.th_dof[(e, "R")] if e in self.hinge_nodes else self.th_dof[e]
        tb = self.th_dof[(e + 1, "L")] if (e + 1) in self.hinge_nodes else self.th_dof[e + 1]
        return [wa, ta, wb, tb]

    def tors_elem_dofs(self, e):
        pa = self.phi_dof.get(e)          # None at clamped node 0
        pb = self.phi_dof[e + 1]
        return [pa, pb]

    def assemble_M(self):
        _, Me_b = self.beam_elem(EI_NOM)   # mass is stiffness-independent
        _, Me_t = self.torsion_elem(GJ_NOM)
        M = np.zeros((self.ndof, self.ndof))
        for e in range(self.n_el):
            d = self.bend_elem_dofs(e)
            for a in range(4):
                if d[a] is None:
                    continue
                for b in range(4):
                    if d[b] is None:
                        continue
                    M[d[a], d[b]] += Me_b[a, b]
            d = self.tors_elem_dofs(e)
            for a in range(2):
                if d[a] is None:
                    continue
                for b in range(2):
                    if d[b] is None:
                        continue
                    M[d[a], d[b]] += Me_t[a, b]
        return M

    def assemble_K_elastic(self, EI, GJ):
        Ke_b, _ = self.beam_elem(EI)
        Ke_t, _ = self.torsion_elem(GJ)
        K = np.zeros((self.ndof, self.ndof))
        for e in range(self.n_el):
            d = self.bend_elem_dofs(e)
            for a in range(4):
                if d[a] is None:
                    continue
                for b in range(4):
                    if d[b] is None:
                        continue
                    K[d[a], d[b]] += Ke_b[a, b]
            d = self.tors_elem_dofs(e)
            for a in range(2):
                if d[a] is None:
                    continue
                for b in range(2):
                    if d[b] is None:
                        continue
                    K[d[a], d[b]] += Ke_t[a, b]
        return K

    def spring_matrix(self, k_root, k_inter):
        K = np.zeros((self.ndof, self.ndof))
        K[self.th_dof[0], self.th_dof[0]] += k_root
        for hn in self.hinge_nodes:
            a, b = self.th_dof[(hn, "L")], self.th_dof[(hn, "R")]
            K[a, a] += k_inter
            K[b, b] += k_inter
            K[a, b] -= k_inter
            K[b, a] -= k_inter
        return K

    def assembled(self, EI, GJ, k_root, k_inter):
        M = self.assemble_M()
        K = self.assemble_K_elastic(EI, GJ) + self.spring_matrix(k_root, k_inter)
        return M, K

    # --- modal analysis helpers ---------------------------------------------
    def modes(self, M, K, n_modes=10):
        w2, V = eigh(K, M)
        w2 = np.maximum(w2, 0.0)
        return np.sqrt(w2[:n_modes]) / (2.0 * math.pi), V[:, :n_modes], w2[:n_modes]

    def torsion_ke_fraction(self, M, v):
        phi_idx = np.array(sorted(self.phi_dof.values()))
        return float(v[phi_idx] @ M[np.ix_(phi_idx, phi_idx)] @ v[phi_idx])

    def per_leaf_ke(self, M, v):
        _, Me_b = self.beam_elem(EI_NOM)
        _, Me_t = self.torsion_elem(GJ_NOM)
        ke = np.zeros(3)
        for e in range(self.n_el):
            leaf = e // self.n
            d = self.bend_elem_dofs(e)
            q = np.array([0.0 if dd is None else v[dd] for dd in d])
            ke[leaf] += float(q @ Me_b @ q)
            d = self.tors_elem_dofs(e)
            q = np.array([0.0 if dd is None else v[dd] for dd in d])
            ke[leaf] += float(q @ Me_t @ q)
        return ke

    def hinge_jumps(self, v):
        j = [float(v[self.th_dof[0]])]
        for hn in self.hinge_nodes:
            j.append(float(v[self.th_dof[(hn, "R")]] - v[self.th_dof[(hn, "L")]]))
        return j

    def descriptor(self, M, K_springs, v, omega2, k_root, k_inter):
        tfrac = self.torsion_ke_fraction(M, v)
        klass = "TORSION" if tfrac > 0.5 else "BENDING"
        ke_leaf = self.per_leaf_ke(M, v)
        ke_total = float(ke_leaf.sum())
        leaf_frac = (ke_leaf / ke_total).tolist() if ke_total > 0 else [None, None, None]
        jumps = self.hinge_jumps(v)
        ks = [k_root, k_inter, k_inter]
        spring_e = [ks[i] * jumps[i] ** 2 for i in range(3)]
        strain_total = float(omega2)  # v' K v = omega^2 with M-normalized v
        spring_frac = [e / strain_total for e in spring_e] if strain_total > 0 else [None] * 3
        leaf_elastic_frac = (1.0 - sum(spring_frac)) if strain_total > 0 else None
        jmax = max(abs(x) for x in jumps) or 1.0
        jrel = [x / jmax for x in jumps]
        dom_leaf = int(np.argmax(ke_leaf)) + 1 if ke_total > 0 else None
        dom_hinge = int(np.argmax(spring_e)) if strain_total > 0 else None
        hinge_names = ["root hinge", "inter hinge 1 (leaf1-leaf2)", "inter hinge 2 (leaf2-leaf3)"]
        if klass == "TORSION":
            text = ("TORSION mode about the spanwise (y) axis; leaf-%d carries the "
                    "largest modal kinetic energy (per-leaf KE %.2f/%.2f/%.2f); hinge "
                    "bending springs unstressed to leading order" % (
                        dom_leaf, leaf_frac[0], leaf_frac[1], leaf_frac[2]))
        else:
            text = ("BENDING mode in the (y,z) plane about X_S hinge axes; dominant "
                    "compliance: %s (spring-energy shares root/h1/h2 = %.3f/%.3f/%.3f, "
                    "leaf elastic strain share %.3f); per-leaf KE %.2f/%.2f/%.2f" % (
                        hinge_names[dom_hinge], spring_frac[0], spring_frac[1],
                        spring_frac[2], leaf_elastic_frac,
                        leaf_frac[0], leaf_frac[1], leaf_frac[2]))
        return {
            "class": klass,
            "torsion_ke_fraction": tfrac,
            "per_leaf_ke_fraction": leaf_frac,
            "dominant_leaf": dom_leaf,
            "hinge_rotation_content_relative": {"theta_root": jrel[0], "jump_hinge1": jrel[1],
                                                "jump_hinge2": jrel[2]},
            "hinge_spring_energy_fraction": {"root": spring_frac[0], "inter1": spring_frac[1],
                                             "inter2": spring_frac[2]},
            "leaf_elastic_strain_energy_fraction": leaf_elastic_frac,
            "dominant_compliance": (hinge_names[dom_hinge] if klass == "BENDING"
                                    else "leaf torsion GJ"),
            "descriptor_text": text,
        }


# ---------------------------------------------------------------------------
# L2 ROM reference (independent recomputation of the published chain model;
# same semantics as compute_flexible_appendage_r2.py, verified vs e21 below)
# ---------------------------------------------------------------------------
def l2_mass_matrix():
    def kinetic_energy(dq):
        psi = [math.pi / 2 + dq[0],
               math.pi / 2 + dq[0] + dq[1],
               math.pi / 2 + dq[0] + dq[1] + dq[2]]
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


M_L2 = l2_mass_matrix()


def l2_modes(k_root, k_inter):
    K = np.diag([k_root, k_inter, k_inter])
    w2, _ = eigh(K, M_L2)
    return (np.sqrt(w2) / (2.0 * math.pi)).tolist()


# ---------------------------------------------------------------------------
# blacklist self-scan (detector definitions only; R1-lane values never used)
# ---------------------------------------------------------------------------
def scan_needles(paths):
    hits = []
    keys = ("needle", "blacklist", "forbidden", "never", "not consumed", "禁", "do not")
    for p in paths:
        text = p.read_text(encoding="utf-8")
        for ln, line in enumerate(text.splitlines(), 1):
            for nd in NEEDLES:
                if nd in line:
                    low = line.lower()
                    ctx = ("DEFINITION_OR_PROHIBITION_CONTEXT"
                           if any(k in low for k in keys) else "UNCLASSIFIED_CONTEXT")
                    hits.append({"file": p.name, "line": ln, "needle": nd,
                                 "context_class": ctx})
    return hits


def fmt(x, nd=6):
    return ("%.*f" % (nd, x)).rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def main():
    t_start = datetime.now(TZ)
    generated = t_start.isoformat()
    model = WingModel(N_LEAF_DEFAULT)

    # --- upstream hash recomputation (full 64-hex) ---------------------------
    upstream = [
        (ECR / "FLEXIBLE_APPENDAGE_R2.yaml",
         "a04acfe440c636bb095585c74f71e3563fd35f6678fcfaa39355383a9bf6b3fd",
         "leaf/hinge registrations; L1 engineering model; L2 ROM card"),
        (ECR / "FLEXIBLE_APPENDAGE_R2_MODES.json",
         "e068de078a0dc680a44807516733fdf018dd720b5f65636bb2b8d21e557593b6",
         "ROM eigen witnesses (nominal + four corners)"),
        (ECR / "compute_flexible_appendage_r2.py",
         "2b64a18605abbd1f79648398a161ddd4d7bcb07665c5d8623b1a34440c1e9bf4",
         "existing chain model script (semantics re-implemented here, read-only)"),
        (ECR / "SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json",
         "d5b7dd16532fe7117d27ecc09efb29ecc570f51928bdbdf3b27bb96c3cf12c5e",
         "mass model (leaf 0.18 x3, hinge_root 0.05, hinge_inter 0.03 x2, hdrm 0.08, harness 0.05 -> 0.78 kg/wing)"),
        (E21_JSON,
         "57958a9f3ac194893d689e9eca4f12666474d97e0cfbb848acba794838b8396b",
         "reproduced eigen (full precision) + authoritative leaf-only Mqq + MC-A conflict record"),
        (BRIDGE / "round1_bridge/r2_flex_prep/R2_ROM_PARTICIPATION_DAMPING_SPEC_DRAFT_V1.md",
         "e3453efbff644fa499ad2453e63621f710ac2b0bdb6f56798aa2b0d14b929e18",
         "SLOT-01..10 discipline (null-not-zero; dual damping lane; latch fold)"),
        (BRIDGE / "round1_bridge/decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml",
         "9cce829e1581b190c6fc50bae56c47659c61319052268e7c9dfd25fac8b8c9e4",
         # full 64-hex pin published by ODR-45 verification_record (owner confirmation)
         "MC-A dynamic mass allocation freeze (ODR-45 owner-confirmed); "
         "BK-DYN-MASS-HINGE-ALLOC-MC-A bookkeeping"),
    ]
    evidence_links = []
    hash_records = []
    for path, pin, role in upstream:
        h = sha256_file(path)
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        rec = {"path": rel, "sha256_recomputed": h,
               "prior_published_pin_full64": pin,
               "match": (h == pin) if pin else None}
        if pin is None:
            rec["prior_pin_note"] = ("no full-64 pin published upstream; redteam published "
                                     "sha256:12 = 9CCE829E1581B190; recomputed hash starts "
                                     "with 9cce829e1581b190 = %s" % h.startswith("9cce829e1581b190"))
        hash_records.append(rec)
        evidence_links.append({"path": rel, "sha256": h, "role": role})

    if ODR45_YAML.exists():
        h = sha256_file(ODR45_YAML)
        rel = str(ODR45_YAML.relative_to(ROOT)).replace("\\", "/")
        hash_records.append({"path": rel, "sha256_recomputed": h,
                             "prior_published_pin_full64": None,
                             "match": None,
                             "note": "pin established by this package (first citation)"})
        evidence_links.append({"path": rel, "sha256": h,
                               "role": "ODR-45..49 owner decision record (wave pin)"})
        odr45_status = "PINNED"
    else:
        hash_records.append({"path": str(ODR45_YAML.relative_to(ROOT)).replace("\\", "/"),
                             "sha256_recomputed": None, "prior_published_pin_full64": None,
                             "match": None,
                             "note": "FILE NOT YET EMITTED at this package's generation time; "
                                     "explicit null, not zero-filled; CM agent must pin after emission"})
        evidence_links.append({"path": str(ODR45_YAML.relative_to(ROOT)).replace("\\", "/"),
                               "sha256": None,
                               "role": "ODR-45..49 owner decision record (wave pin) - PENDING_FILE_NOT_YET_EMITTED"})
        odr45_status = "PENDING_FILE_NOT_YET_EMITTED_AT_GENERATION_TIME"

    e21 = json.loads(E21_JSON.read_text(encoding="utf-8"))
    e21_cases = {c["case"]: c for c in e21["leaf_only"]["cases"]}
    mqq_e21 = np.array(e21["leaf_only"]["Mqq_kg_m2"])
    rom_pub = {"nominal": [6.9726, 39.3586, 98.0042],
               "all_low": [3.3278, 18.2952, 44.1763],
               "all_high": [13.9452, 78.7172, 196.0085],
               "root_low_inter_high": [4.3424, 65.0146, 190.5319],
               "root_high_inter_low": [4.7369, 30.2986, 74.9597]}

    # --- ROM reproduction verification ---------------------------------------
    rom_check = {"Mqq_max_abs_diff_vs_e21_kg_m2": float(np.max(np.abs(M_L2 - mqq_e21))),
                 "Mqq_recomputed_kg_m2": M_L2.tolist()}
    rom_freq_max_df = 0.0
    for case, (kr, ki) in STIFFNESS_CASES.items():
        f = l2_modes(kr, ki)
        df = max(abs(a - b) for a, b in zip(f, e21_cases[case]["leaf_only_reproduced_hz"]))
        rom_freq_max_df = max(rom_freq_max_df, df)
    rom_check["five_case_freq_max_abs_diff_vs_e21_hz"] = rom_freq_max_df

    # --- assembled M_hf / K_hf (N=20 default) --------------------------------
    M_HF = model.assemble_M()
    K_ELASTIC_NOM = model.assemble_K_elastic(EI_NOM, GJ_NOM)
    K_SPRINGS_NOM = model.spring_matrix(*STIFFNESS_CASES["nominal"])
    K_HF_NOM = K_ELASTIC_NOM + K_SPRINGS_NOM

    dof_map_doc = {
        "convention": "bending block first, then torsion block; blocks are decoupled "
                      "(planar EB bending about X_S + independent spanwise torsion)",
        "bending": "w(node n) for n=1..60 -> dof 0..59; theta(node0) -> dof 60; "
                   "theta nodes 1..19 -> 61..79; theta node20 L/R -> 80/81 (hinge 1); "
                   "theta nodes 21..39 -> 82..99; theta node40 L/R -> 100/101 (hinge 2); "
                   "theta nodes 41..60 -> 102..121",
        "torsion": "phi(node n) for n=1..60 -> dof 122..181; phi(node0)=0 clamped root; "
                   "continuous through hinge nodes 20 and 40",
        "boundary": "w(node0)=0 revolute attach; k_root spring on theta(node0); "
                    "k_inter jump springs between theta_L/theta_R at nodes 20 and 40",
        "ndof_free": model.ndof,
        "elements_per_leaf": model.n, "leaves_per_wing": 3, "n_elements": model.n_el,
        "element_length_m": model.le,
        "hinge_nodes": list(model.hinge_nodes),
        "spring_topology_dofs": {
            "root_theta_dof": model.th_dof[0],
            "hinge1_theta_L_dof": model.th_dof[(model.hinge_nodes[0], "L")],
            "hinge1_theta_R_dof": model.th_dof[(model.hinge_nodes[0], "R")],
            "hinge2_theta_L_dof": model.th_dof[(model.hinge_nodes[1], "L")],
            "hinge2_theta_R_dof": model.th_dof[(model.hinge_nodes[1], "R")],
        },
        "assembly_rule": "K(case, EI, GJ) = K_elastic_bending(EI) + K_torsion(GJ) + "
                         "k_root*E(theta_root) + k_inter*(E(hinge1_jump)+E(hinge2_jump)); "
                         "M is case/EI/GJ independent",
    }

    # --- eigen cases ----------------------------------------------------------
    def run_case(k_root, k_inter, EI, GJ, n_modes=10):
        K = model.assemble_K_elastic(EI, GJ) + model.spring_matrix(k_root, k_inter)
        f, V, w2 = model.modes(M_HF, K, n_modes)
        descs = []
        for i in range(min(6, n_modes)):
            d = model.descriptor(M_HF, None, V[:, i], w2[i], k_root, k_inter)
            d["mode_rank"] = i + 1
            d["frequency_hz"] = float(f[i])
            descs.append(d)
        classes = [model.torsion_ke_fraction(M_HF, V[:, i]) > 0.5 and "TORSION" or "BENDING"
                   for i in range(n_modes)]
        first_torsion_rank = next((i + 1 for i, c in enumerate(classes) if c == "TORSION"), None)
        bending_f = [float(f[i]) for i, c in enumerate(classes) if c == "BENDING"]
        return {"frequencies_hz_first10": [float(x) for x in f],
                "mode_classes_first10": classes,
                "first_torsion_mode_rank": first_torsion_rank,
                "bending_modes_hz_in_order": bending_f,
                "mode_descriptors_first6": descs}

    eigen_cases = {}
    for case, (kr, ki) in STIFFNESS_CASES.items():
        eigen_cases[case] = {"k_root_Nm_per_rad": kr, "k_inter_Nm_per_rad": ki,
                             "EI_Nm2": EI_NOM, "GJ_Nm2": GJ_NOM}
        eigen_cases[case].update(run_case(kr, ki, EI_NOM, GJ_NOM))
    for name, ei in EI_POINTS.items():
        if name == "EI_nominal":
            continue
        key = "stiffness_nominal__" + name
        eigen_cases[key] = {"k_root_Nm_per_rad": 200.0, "k_inter_Nm_per_rad": 100.0,
                            "EI_Nm2": ei, "GJ_Nm2": GJ_NOM}
        eigen_cases[key].update(run_case(200.0, 100.0, ei, GJ_NOM))
    for name, gj in GJ_POINTS.items():
        if name == "GJ_nominal":
            continue
        key = "stiffness_nominal_EI_nominal__" + name
        eigen_cases[key] = {"k_root_Nm_per_rad": 200.0, "k_inter_Nm_per_rad": 100.0,
                            "EI_Nm2": EI_NOM, "GJ_Nm2": gj}
        eigen_cases[key].update(run_case(200.0, 100.0, EI_NOM, gj))

    # damping corners: report-only dissipation-lane mapping on the nominal spectrum
    damping_corners = {}
    nom_f6 = eigen_cases["nominal"]["frequencies_hz_first10"][:6]
    for zeta_name, zeta in (("zeta_low", ZETA_BAND[0]), ("zeta_nominal", ZETA_NOM),
                            ("zeta_high", ZETA_BAND[1])):
        damping_corners[zeta_name] = {
            "zeta": zeta,
            "damped_frequency_hz_first6": [f * math.sqrt(1.0 - zeta ** 2) for f in nom_f6],
            "decay_time_constant_s_first6": [1.0 / (zeta * 2.0 * math.pi * f) for f in nom_f6],
            "freq_shift_vs_undamped_pct_first6": [(math.sqrt(1.0 - zeta ** 2) - 1.0) * 100.0
                                                  for _ in nom_f6],
        }
    damping_lane = {
        "class": "PROVISIONAL_DERIVED",
        "zeta_band": list(ZETA_BAND), "zeta_nominal": ZETA_NOM,
        "dual_lane_discipline": {
            "conservation_audit_lane": "zeta = 0; ALL M/K eigen evidence in this package "
                                       "is computed in this lane (undamped generalized eigenproblem)",
            "dissipation_prediction_lane": "zeta != 0; report-only damped-frequency and "
                                           "decay-constant mapping below; no energy/momentum "
                                           "conservation statement may be drawn from this lane",
        },
        "corners": damping_corners,
        "provenance_note": "bounded assumption for CFRP sandwich + hinge chain; the legacy "
                           "placeholders (card zeta=0.01 TBD_cite_literature, sim_11 "
                           "zeta_modal placeholder) are NOT consumed as authority; this is a "
                           "NEW derived record; the nominal 0.005 is the Wave-4a directive "
                           "nominal and any numeric coincidence with the retired sim_11 "
                           "placeholder is provenance-independent",
    }

    # --- HF first-3 BENDING vs ROM witnesses (REPORT ONLY, no tuning) --------
    comparison = {}
    for case in STIFFNESS_CASES:
        hf_b3 = eigen_cases[case]["bending_modes_hz_in_order"][:3]
        rom_ref = e21_cases[case]["leaf_only_reproduced_hz"]
        comparison[case] = {
            "hf_bending_first3_hz": hf_b3,
            "rom_witness_published_hz": rom_pub[case],
            "rom_witness_e21_full_precision_hz": rom_ref,
            "signed_deviation_hf_minus_rom_pct_vs_e21": [
                (a - b) / b * 100.0 for a, b in zip(hf_b3, rom_ref)],
            "signed_deviation_hz": [a - b for a, b in zip(hf_b3, rom_ref)],
        }
    anchor = comparison["nominal"]["signed_deviation_hf_minus_rom_pct_vs_e21"][0]
    anchor_hz = comparison["nominal"]["signed_deviation_hz"][0]
    comparison_note = {
        "anchor_mode1_drift": {"pct": anchor, "hz": anchor_hz},
        "attribution": [
            "leaf flexibility (E-1): the HF leaves add elastic compliance in series with "
            "the hinge springs, so HF bending frequencies sit BELOW the rigid-leaf ROM "
            "witnesses; the effect grows with mode order (mode 3 approaches the leaf "
            "cantilever scale 49.15 Hz nominal)",
            "multi-leaf coupling: HF modes distribute curvature over all three leaves "
            "instead of concentrating rotation at discrete hinge coordinates",
            "hinge compliance: unchanged registered bands 50/200/800 and 20/100/400 "
            "N m/rad, latch-inclusive per SLOT-03 (no independent latch stiffness; null kept)",
            "mass redistribution per MC-A bookkeeping BK-DYN-MASS-HINGE-ALLOC-MC-A: hinge "
            "point masses are rigid non-tracking and excluded from the kinetic energy; the "
            "conflict-lane alternative would shift frequencies down further (nominal "
            "-3.5096/-6.9411/-13.4 pct per the decision record) and is NOT used here",
        ],
        "report_only_no_tuning": True,
    }

    # --- mesh convergence N = 10 / 20 / 40 per leaf ---------------------------
    convergence = {"per_mesh": {}, "note": "nominal stiffness/EI/GJ; modes aligned by rank"}
    for n_leaf in (10, 20, 40):
        m = WingModel(n_leaf)
        Mm = m.assemble_M()
        K = m.assemble_K_elastic(EI_NOM, GJ_NOM) + m.spring_matrix(200.0, 100.0)
        f, V, _ = m.modes(Mm, K, 8)
        cls = [m.torsion_ke_fraction(Mm, V[:, i]) > 0.5 and "TORSION" or "BENDING"
               for i in range(8)]
        convergence["per_mesh"]["N%d" % n_leaf] = {
            "frequencies_hz_first8": [float(x) for x in f], "mode_classes_first8": cls,
            "ndof_free": m.ndof}
    f20 = convergence["per_mesh"]["N20"]["frequencies_hz_first8"]
    f40 = convergence["per_mesh"]["N40"]["frequencies_hz_first8"]
    f10 = convergence["per_mesh"]["N10"]["frequencies_hz_first8"]
    shift_20_40 = [(a - b) / b * 100.0 for a, b in zip(f20, f40)]
    shift_10_40 = [(a - b) / b * 100.0 for a, b in zip(f10, f40)]
    convergence["shift_pct_N20_vs_N40_first8"] = shift_20_40
    convergence["shift_pct_N10_vs_N40_first8"] = shift_10_40
    convergence["max_abs_shift_pct_first3_N20_vs_N40"] = max(abs(x) for x in shift_20_40[:3])

    # --- mass closure ----------------------------------------------------------
    u_z = np.zeros(model.ndof)
    for nn, dd in model.w_dof.items():
        u_z[dd] = 1.0
    m_trans = float(u_z @ M_HF @ u_z)
    u_phi = np.zeros(model.ndof)
    for nn, dd in model.phi_dof.items():
        u_phi[dd] = 1.0
    j_polar = float(u_phi @ M_HF @ u_phi)
    mass_closure = {
        "hf_kinetic_leaf_mass_kg": m_trans,
        "hf_kinetic_leaf_mass_expected_kg": 3 * LEAF_M,
        "abs_error_kg": abs(m_trans - 3 * LEAF_M),
        "rigid_non_tracking_ledger_kg": {
            "hinge_root": M_HINGE_ROOT, "hinge_inter_2x": 2 * M_HINGE_INTER_EACH,
            "hdrm": M_HDRM, "harness": M_HARNESS, "sum": M_RIGID_LEDGER,
            "booking": "MC-A rigid non-tracking interface masses at hinge lines; "
                       "excluded from kinetic energy (BK-DYN-MASS-HINGE-ALLOC-MC-A)"},
        "hf_total_per_wing_kg": m_trans + M_RIGID_LEDGER,
        "expected_per_wing_kg": M_WING_TOTAL,
        "abs_error_total_kg": abs(m_trans + M_RIGID_LEDGER - M_WING_TOTAL),
        "torsion_polar_inertia_total_kg_m2": j_polar,
        "torsion_polar_inertia_expected_kg_m2": JM_TORSION * 3 * LEAF_L,
    }

    # --- SPD checks ------------------------------------------------------------
    eig_M = float(np.min(np.linalg.eigvalsh(M_HF)))
    eig_K = float(np.min(np.linalg.eigvalsh(K_HF_NOM)))
    w2_min = float(eigh(K_HF_NOM, M_HF, eigvals_only=True, subset_by_index=[0, 0])[0])
    spd = {"M_hf_min_eigenvalue": eig_M, "K_hf_latched_nominal_min_eigenvalue": eig_K,
           "min_generalized_omega2": w2_min,
           "M_spd": eig_M > 0.0, "K_latched_spd": eig_K > 0.0}

    # --- rigid-mode null-space sanity at unlatched config ----------------------
    K_unlatched = model.assemble_K_elastic(EI_NOM, GJ_NOM)  # all hinge springs OFF
    ev = np.linalg.eigvalsh(K_unlatched)
    scale = float(np.max(np.abs(np.diag(K_unlatched))))
    tol0 = 1e-9 * scale
    n_zero = int(np.sum(np.abs(ev) < tol0))
    null_space = {
        "config": "UNLATCHED sanity config: k_root = k_inter = 0 (hinge springs off), "
                  "leaf elasticity intact, torsion root clamped",
        "near_zero_eigenvalue_count": n_zero,
        "near_zero_threshold": tol0,
        "near_zero_eigenvalues": ev[ev < tol0].tolist()[:8] if n_zero else [],
        "first_positive_eigenvalue": float(ev[n_zero]) if n_zero < len(ev) else None,
        "expected_count": 3,
        "interpretation": "3 rigid chain rotations about the X_S hinge lines (theta_root, "
                          "jump hinge1, jump hinge2); torsion lane contributes NO rigid mode "
                          "because the torsion root is clamped (phi(node0)=0)",
        "verdict": "PASS" if n_zero == 3 else "FAIL",
    }
    # variant: torsion root free -> expect 4 null modes (boundary sensitivity, info only)
    K_unl_free_t = K_unlatched.copy()
    # release phi(node0): nothing to do in assembly (node0 never assembled), so instead
    # add note only - the assembled model has phi(0) clamped by construction.

    # --- rigid-limit consistency: HF with EI x 1e9 vs ROM ----------------------
    K_rig = model.assemble_K_elastic(EI_NOM * 1e9, GJ_NOM) + model.spring_matrix(200.0, 100.0)
    f_rig, V_rig, _ = model.modes(M_HF, K_rig, 10)
    cls_rig = [model.torsion_ke_fraction(M_HF, V_rig[:, i]) > 0.5 and "TORSION" or "BENDING"
               for i in range(10)]
    hf_rig_b3 = [float(f_rig[i]) for i, c in enumerate(cls_rig) if c == "BENDING"][:3]
    rom_nom = e21_cases["nominal"]["leaf_only_reproduced_hz"]
    rigid_limit = {
        "hf_rigid_limit_bending_first3_hz": hf_rig_b3,
        "rom_e21_full_precision_hz": rom_nom,
        "max_rel_diff": max(abs(a - b) / b for a, b in zip(hf_rig_b3, rom_nom)),
        "note": "EI x 1e9 collapses leaf elasticity; HF bending lanes must collapse onto "
                "the rigid-leaf ROM witnesses (FE discretization residual only)",
        "verdict": None,
    }
    rigid_limit["verdict"] = "MATCH" if rigid_limit["max_rel_diff"] < 1e-6 else "FAIL"

    # --- surprises / observations ---------------------------------------------
    surprises = []
    r = eigen_cases["nominal"]["first_torsion_mode_rank"]
    surprises.append(
        "torsion interleave: at nominal GJ (%.4f N m2) the first TORSION mode sits at "
        "overall rank %s (%.4f Hz), i.e. inside the ROM bending witness band "
        "[6.9726, 39.3586, 98.0042] Hz; the ROM is bending-only, so all HF-vs-ROM "
        "comparisons are made on BENDING-classified modes only" % (
            GJ_NOM, r, eigen_cases["nominal"]["frequencies_hz_first10"][r - 1]))
    surprises.append(
        "anchor drift: HF bending mode 1 = %.6f Hz vs ROM witness 6.9726 Hz "
        "(%+.4f pct, %+.6f Hz) - leaf flexibility adds series compliance; report only" % (
            eigen_cases["nominal"]["bending_modes_hz_in_order"][0], anchor, anchor_hz))
    dev3 = comparison["nominal"]["signed_deviation_hf_minus_rom_pct_vs_e21"][2]
    surprises.append(
        "mode 3 deviation is the largest (%+.4f pct nominal): the ROM third mode (98 Hz) "
        "is a rigid-leaf chain artifact; with leaf elasticity the third bending mode drops "
        "toward the leaf-cantilever scale (49.15 Hz nominal standalone)" % dev3)
    for case in ("all_low", "all_high"):
        rr = eigen_cases[case]["first_torsion_mode_rank"]
        surprises.append(
            "case %s: first torsion mode rank %s (%.4f Hz); band corners re-order the "
            "torsion/bending interleave" % (
                case, rr, eigen_cases[case]["frequencies_hz_first10"][rr - 1]))

    # ============================ write outputs ==============================
    header_common = {
        "generated_local": generated,
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "generator": GENERATOR,
    }

    # ---------------- evidence JSON ----------------
    evidence = {
        "schema": "R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1",
        **header_common,
        "class": "CANDIDATE_PROVISIONAL_BANDS__NOT_CERTIFIED",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "scope": "FIXED_BASE_FREE_VIBRATION_ONLY, per single wing, deployed latched flat config",
        "model_definition": {
            "type": "per-wing 3-leaf Euler-Bernoulli beam FE chain + per-leaf spanwise "
                    "torsion lane; planar (y,z) bending about X_S hinge axes per "
                    "FLEXIBLE_APPENDAGE_R2.yaml kinematic registration",
            "dof_map": dof_map_doc,
            "extensions_vs_registered_card": [
                "E-1 leaves flexible FE beams (L2 ROM is a rigid-leaf chain)",
                "E-2 torsion DOFs added (card GJ slot was NULL/'pending sandwich shear model')",
                "E-3 torsion root clamped phi(node0)=0 (SLOT-04 root-bracket compliance NULL)",
                "E-4 torsion continuous through inter-panel hinges (no registered hinge "
                "torsional compliance)"],
            "mass_model": "leaf consistent mass + cross-section rotary inertia (bending) "
                          "+ JM_TORSION = mu*chord^2/12 (torsion); hinge/root/HDRM/harness "
                          "masses EXCLUDED from kinetic energy per MC-A (rigid non-tracking "
                          "interface booking, BK-DYN-MASS-HINGE-ALLOC-MC-A)",
            "excluded_scope_verbatim_holds": [
                "HOLD_LATCH_GEOMETRY_NOT_MODELLED (SLOT-03: independent latch stiffness null; "
                "inter-panel bands propagated as latch-inclusive compliance)",
                "HOLD_FREEPLAY_LIMITS_NO_NUMERIC_AUTHORITY (SLOT-05)",
                "SLOT-04 root-bracket compliance beyond k_theta_root: NULL",
                "SLOT-07 base-coupling participation factors: out of scope here (later WP)"],
        },
        "parameters": {
            "leaf": {"mass_kg": LEAF_M, "span_m": LEAF_L, "chord_m": LEAF_A,
                     "thickness_m": LEAF_T, "mu_kg_per_m": MU, "rhoj_kg_m": RHOJ,
                     "JM_torsion_kg_m_per_m": JM_TORSION},
            "EI_Nm2": {"nominal": EI_NOM, "band": [EI_LOW, EI_HIGH],
                       "class": "PROVISIONAL_DERIVED (carried from FLEXIBLE_APPENDAGE_R2)"},
            "GJ_Nm2": {"nominal": GJ_NOM, "band": [GJ_LOW, GJ_HIGH],
                       "class": "PROVISIONAL_DERIVED",
                       "derivation": "see model card R2_FULLFLEX_HF_MODEL_V1.yaml gj_derivation"},
            "k_root_Nm_per_rad": {**K_ROOT, "class": "PROVISIONAL_DERIVED (carried)"},
            "k_inter_Nm_per_rad_latch_inclusive": {**K_INTER,
                                                   "class": "PROVISIONAL_DERIVED (carried)"},
            "zeta_modal": {"nominal": ZETA_NOM, "band": list(ZETA_BAND),
                           "class": "PROVISIONAL_DERIVED (NEW record; legacy placeholders "
                                    "not consumed)"},
            "latch_independent_stiffness_Nm_per_rad": None,
            "root_hinge_point_S_m_context": {"y": P0_Y, "z": P0_Z},
        },
        "gj_derivation_summary": {
            "lower_open_section_st_venant": GJ_LOW,
            "upper_closed_cell_bredt": GJ_HIGH,
            "nominal_geometric_mean": GJ_NOM,
            "full_writeup": "R2_FULLFLEX_HF_MODEL_V1.yaml gj_derivation",
        },
        "M_hf_kg_m2_rowmajor": M_HF.tolist(),
        "K_hf_elastic_nominal_Nm2_rowmajor": K_ELASTIC_NOM.tolist(),
        "K_hf_springs_nominal_Nm_per_rad_rowmajor": K_SPRINGS_NOM.tolist(),
        "K_hf_assembled_nominal_rowmajor": K_HF_NOM.tolist(),
        "eigen_cases": eigen_cases,
        "damping_lane": damping_lane,
        "hf_vs_rom_comparison_report_only": {"per_case": comparison, **comparison_note},
        "mesh_convergence": convergence,
        "mass_closure": mass_closure,
        "spd_checks": spd,
        "rigid_mode_null_space_unlatched": null_space,
        "rigid_limit_vs_rom": rigid_limit,
        "surprises_and_observations": surprises,
        "verification_record": {
            "upstream_hash_recomputation": hash_records,
            "rom_independent_reproduction": rom_check,
            "odr45_49_pin_status": odr45_status,
            "runtime_note": "pure numpy/scipy eigh; ndof=%d; no CAD/FEA/simulation process" % model.ndof,
        },
        "evidence_links": evidence_links,
        "forbidden": [
            "consuming legacy R1-lane values inside any R2 lane (blacklist enforced by gate)",
            "averaging/merging the Route-B rejection numeric spellings",
            "promoting PROVISIONAL_DERIVED bands to measured/authority",
            "tuning any parameter to match the ROM witnesses (comparison is REPORT ONLY)",
            "zero-filling the independent latch stiffness (stays null, HOLD verbatim)",
            "drawing conservation-audit conclusions from the zeta != 0 dissipation lane",
        ],
        "nonclaims": [
            "this is NOT a ROM: no modal truncation is delivered for dynamics consumption",
            "this is NOT a coupled/free-floating evaluation: fixed-base per-wing eigen only",
            "r2_full_flexible_coupling stays NOT_EVALUATED; this file does not close it",
            "e15 REPEAT_ANCF_CERTIFICATION is unchanged; no recertification run is authorized",
            "no measurement authority: every stiffness/damping band is PROVISIONAL_DERIVED",
            "no production/manufacturing/qualification/launch/flight authority",
            "GAP-12 whole-satellite mass budget reallocation untouched (stays OPEN)",
        ],
        "self_hash_policy": SELF_HASH_POLICY,
        "companion_human_readable": "R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.md (same basename; "
                                    "structured JSON fields govern on conflict)",
    }
    OUT_EVID_JSON.write_text(json.dumps(evidence, indent=1, ensure_ascii=False),
                             encoding="utf-8")

    # ---------------- model card YAML ----------------
    card = f"""schema: R2_FULLFLEX_HF_MODEL_V1
generated_local: '{generated}'
generated_clock_source: HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08
generator: {GENERATOR}
class: CANDIDATE_PROVISIONAL_BANDS__NOT_CERTIFIED
review_status: PENDING_OWNER_REVIEW
next_stage_authorized: false
release_credit: false

scope: FIXED_BASE_FREE_VIBRATION_ONLY, per single wing, deployed latched flat config
wave_role: B1 - R2 high-fidelity three-leaf-per-wing flexible model (Full-Flex F1)

architecture: >-
  per wing = root hinge (k_theta_root band 50/200/800 N m/rad) -> leaf 1 flexible
  (Euler-Bernoulli FE, 20 elements default) -> hinge 2 (k_theta_inter 20/100/400)
  -> leaf 2 flexible -> hinge 3 (k_theta_inter) -> leaf 3 flexible; all hinge axes
  parallel X_S, planar (y,z) bending per FLEXIBLE_APPENDAGE_R2.yaml registration;
  NEW torsion lane: each leaf also carries spanwise torsion DOF phi(y) with GJ.

kinematic_conventions:
  source: FLEXIBLE_APPENDAGE_R2.yaml (registered; read-only)
  hinge_axes: parallel X_S (book/accordion chain)
  motion: planar (y,z) bending; torsion about the deployed spanwise (+y) line
  extensions_documented_explicitly:
  - E-1 leaves are flexible FE beams (the registered L2 ROM is a rigid-leaf chain)
  - E-2 torsion DOFs added (registered card GJ slot was NULL / 'pending sandwich shear model')
  - E-3 torsion root boundary clamped phi(node0)=0 (root-bracket torsional compliance
    is SLOT-04 NULL; clamping is the reference boundary)
  - E-4 torsion transmitted continuously through inter-panel hinges (no registered
    hinge torsional compliance exists)

leaf:
  mass_kg: 0.18
  span_m: 0.2
  chord_m: 0.3
  thickness_m: 0.0025
  elements_per_leaf_default: 20
  mu_kg_per_m: 0.9
  rhoj_kg_m_bending_rotary: {RHOJ:.10e}
  JM_torsion_kg_m_per_m: {JM_TORSION:.10e}   # mu*chord^2/12 about spanwise axis
  EI_Nm2: {{nominal: {EI_NOM}, band: [{EI_LOW}, {EI_HIGH}], class: PROVISIONAL_DERIVED,
    provenance: carried from FLEXIBLE_APPENDAGE_R2.yaml (no measurement source)}}

gj_derivation:
  class: PROVISIONAL_DERIVED
  measurement_claim: FORBIDDEN - no torsion measurement exists; band must be replaced
    by WP5 R2 hardware selection vendor data or test
  construction_basis: >-
    registered candidate (FLEXIBLE_APPENDAGE_R2.yaml leaf_L1_engineering_model):
    2 x 0.2 mm CFRP faces (E = 70 GPa quasi-iso) over 2.1 mm core, total 2.5 mm,
    chord 0.300 m; candidate Poisson ratio nu = 0.3; core shear modulus candidate
    G_c = 100 MPa (generic low-modulus sandwich core, PROVISIONAL_DERIVED).
  face_shear_modulus_Pa: {G_FACE:.6e}   # G_f = E/(2*(1+nu)) = 70e9/2.6
  lower_bound_open_section_st_venant:
    formula: GJ_low = chord/3 * (2*G_f*t_f^3 + G_c*t_c^3)
    arithmetic: 0.3/3 * (2*{G_FACE:.6e}*(2.0e-4)^3 + 1.0e8*(2.1e-3)^3)
    value_Nm2: {GJ_LOW:.10f}
    meaning: components act independently with free warping (open thin strip)
  upper_bound_closed_cell_bredt:
    formula: GJ_high = 4*A_m^2 / (integral ds/(G*t)) with A_m = chord*(t_c+t_f),
      compliant walls = the two faces only; edge closures assumed rigid
    arithmetic: A_m = 0.3*2.3e-3 = {A_CELL:.6e} m2; integral = 2*0.3/(G_f*t_f) = {BREDT_DEN:.6e}
    value_Nm2: {GJ_HIGH:.10f}
    meaning: sandwich cross-section acts as a closed thin-walled cell (potted edges)
  nominal: geometric mean sqrt(GJ_low*GJ_high) = {GJ_NOM:.10f} N m2
  band_Nm2: [{GJ_LOW:.10f}, {GJ_HIGH:.10f}]
  note: band is wide (about 2 orders of magnitude) because the torsional load path
    of the real sandwich (edge closure quality, core shear) is unknown; this is an
    honest bounded interval, never a point estimate.

hinge_stiffness:
  k_theta_root_Nm_per_rad: {{low: 50, nominal: 200, high: 800, class: PROVISIONAL_DERIVED}}
  k_theta_inter_Nm_per_rad: {{low: 20, nominal: 100, high: 400, class: PROVISIONAL_DERIVED}}
  deployed_latched_semantics: ODR-32 - the modal evidence is computed AT the deployed
    latched state, so these bands ARE the deployed latch-inclusive stiffness candidates
  latch:
    independent_latch_stiffness_Nm_per_rad: null   # HOLD_LATCH_GEOMETRY_NOT_MODELLED (verbatim)
    fold_statement: >-
      per SLOT-03 discipline the inter-panel k_theta band [20, 100, 400] N m/rad is
      propagated as the latch-inclusive deployed-state compliance until latch hardware
      is selected; the independent latch stiffness stays explicit null (never zero-filled).

damping:
  class: PROVISIONAL_DERIVED
  type: modal zeta band (bounded assumption for CFRP sandwich + hinge chain; NOT a measurement)
  zeta_band: [0.002, 0.02]
  zeta_nominal: 0.005   # Wave-4a directive nominal (ODR-45..49 era)
  dual_lane_discipline:
    conservation_audit_lane: zeta = 0 - all M/K eigen evidence in this package
    dissipation_prediction_lane: zeta != 0 - report-only damped-frequency/decay mapping
  legacy_placeholder_policy: >-
    the old placeholders (card zeta=0.01 TBD_cite_literature; sim_11 zeta_modal=0.005
    placeholder) are NOT consumed as authority anywhere in this package; the band above
    is a NEW derived record; any numeric coincidence with the retired sim_11 placeholder
    is provenance-independent.

mass_bookkeeping_mc_a:
  ruling: ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml (dynamic_mass_allocation_frozen=true)
  kinetic_energy: leaf masses only (3 x 0.18 = 0.54 kg/wing)
  rigid_non_tracking_interface_masses_at_hinge_lines:
    hinge_root_kg: 0.05
    hinge_inter_kg_each: 0.03
    hdrm_kg: 0.08
    harness_kg: 0.05
    sum_kg: 0.24
  bookkeeping_id: BK-DYN-MASS-HINGE-ALLOC-MC-A
  total_per_wing_kg: 0.78   # exact closure vs SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json

dof_map_summary: {dof_map_doc['convention']}; ndof_free = {model.ndof} at 20 elements/leaf;
  full map in R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json model_definition.dof_map

boundary_conditions:
  root: w(node0)=0 (revolute attach); k_theta_root spring on theta(node0)
  inter_panel: doubled theta at hinge nodes with k_theta_inter jump springs
  torsion_root: phi(node0)=0 clamped (E-3 reference boundary)

scope_limits_verbatim:
- no freeplay/backlash (SLOT-05 NULL, HOLD_FREEPLAY_LIMITS_NO_NUMERIC_AUTHORITY)
- no root-bracket compliance beyond k_theta_root (SLOT-04 NULL)
- no independent latch stiffness (SLOT-03 NULL, folded into inter-panel bands)
- no base coupling / participation factors in this package (SLOT-07, later work)
- damping enters only as the report-only dissipation lane; M/K eigen = zeta=0 lane

holds_carried_verbatim:
- HOLD_LATCH_GEOMETRY_NOT_MODELLED
- HOLD_FREEPLAY_LIMITS_NO_NUMERIC_AUTHORITY
- HOLD_PANEL_LAYUP_AND_CELL_GEOMETRY_NOT_MODELLED
- e15 REPEAT_ANCF_CERTIFICATION (unchanged by this package)
- r2_full_flexible_coupling: NOT_EVALUATED (this file does not close it)

evidence: R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json (assembled M_hf/K_hf, eigen cases,
  convergence, mass closure, SPD, null-space sanity, HF-vs-ROM report-only table)
validation_gate: R2_FULLFLEX_HF_VALIDATION_GATE_V1.json

nonclaims:
- this card is NOT a ROM and NOT a coupled/free-floating evaluation
- no parameter in this card is measured; all bands are PROVISIONAL_DERIVED
- comparison vs ROM witnesses is REPORT ONLY (no tuning)
- no production/manufacturing/qualification/launch/flight authority
- GAP-12 whole-satellite mass budget reallocation untouched (stays OPEN)

self_hash_policy: {SELF_HASH_POLICY}
companion_human_readable: R2_FULLFLEX_HF_MODEL_V1.md (same basename; YAML structured
  fields govern on conflict)
"""
    OUT_CARD_YAML.write_text(card, encoding="utf-8")

    # ---------------- card .md companion ----------------
    card_md = f"""# R2_FULLFLEX_HF_MODEL_V1 — 人读版（机器字段以同basename YAML 为准）

- schema: `R2_FULLFLEX_HF_MODEL_V1`
- 生成时间：{generated}（宿主机本地钟，Asia/Shanghai UTC+08:00）
- 生成方：{GENERATOR}
- 状态：**CANDIDATE_PROVISIONAL_BANDS__NOT_CERTIFIED**；`review_status=PENDING_OWNER_REVIEW`；`next_stage_authorized=false`；`release_credit=false`

## 模型（每翼，展开锁定平直构型）

根铰（kθ_root 50/200/800 N·m/rad）→ 叶1 柔性（EB 梁 FE，默认 20 单元/叶）→ 铰2
（kθ_inter 20/100/400）→ 叶2 柔性 → 铰3 → 叶3 柔性。铰轴 ∥ X_S，(y,z) 平面弯曲，
运动学登记逐字遵循 `FLEXIBLE_APPENDAGE_R2.yaml`。**新增扭转车道**：每叶携带绕展向
（+y）轴扭转 DOF φ，GJ 带为本包新推导。

## GJ 推导（PROVISIONAL_DERIVED，禁止声称为实测）

- 构造基础（登记候选）：2×0.2 mm CFRP 面板（E=70 GPa 准各向同性，ν=0.3 候选 →
  G_f={G_FACE:.4e} Pa）+ 2.1 mm 芯（G_c=100 MPa 候选），总厚 2.5 mm，弦长 0.300 m。
- 下限（开截面 St-Venant，自由翘曲）：GJ_low = chord/3·(2·G_f·t_f³ + G_c·t_c³)
  = **{GJ_LOW:.6f} N·m²**。
- 上限（闭室 Bredt-Batho，面板为唯一柔顺壁、边缘闭合刚性）：A_m=chord·(t_c+t_f)=
  {A_CELL:.4e} m²，GJ_high = 4·A_m²/(∮ds/(G·t)) = **{GJ_HIGH:.6f} N·m²**。
- 名义 = 几何均值 = **{GJ_NOM:.6f} N·m²**。带宽约两个数量级——这是诚实的有界区间，
  不是点估计；须由 WP5 R2 硬件选型 vendor 数据或实测替换。

## 阻尼（PROVISIONAL_DERIVED，新推导记录）

ζ 带 [0.002, 0.02]，名义 0.005（Wave-4a 指令名义）。双车道纪律：ζ=0 守恒审计车道
（本包全部 M/K 特征值证据）与 ζ≠0 耗散预测车道（仅 report-only 映射）分离。旧占位
（卡 ζ=0.01 TBD_cite_literature、sim_11 zeta_modal 占位）**不作为权威被消费**；
名义值与退役占位若有数字巧合，出处互相独立。

## Latch（HOLD 逐字）

独立 latch 刚度 = **null**（`HOLD_LATCH_GEOMETRY_NOT_MODELLED`）；按 SLOT-03，板间
kθ 带 [20,100,400] 作为含 latch 的展开锁定态柔顺传播。

## 质量记账（MC-A，BK-DYN-MASS-HINGE-ALLOC-MC-A）

动能只含叶质量（3×0.18=0.54 kg）；根铰 0.05 + 板间铰 2×0.03 + HDRM 0.08 + 线束
0.05 = 0.24 kg 作为刚性非随动界面质量记在铰线结构质量账；合计 **0.78 kg/翼精确闭合**。

## 范围限制（逐字保持，未零填）

SLOT-03 latch 独立刚度 null / SLOT-04 根支架柔顺 null / SLOT-05 自由间隙 null /
SLOT-07 基座耦合参与因子不在本包。e15 `REPEAT_ANCF_CERTIFICATION` 与
`r2_full_flexible_coupling=NOT_EVALUATED` 不因本文件改变。

## 纪律

HF-vs-ROM 对比为 **REPORT ONLY，禁止调参**；遗留 R1 车道数值禁止入 R2 车道（gate
黑名单机器核查）；本卡不授予任何生产/制造/鉴定/发射/飞行权威。
"""
    OUT_CARD_MD.write_text(card_md, encoding="utf-8")

    # ---------------- evidence .md companion ----------------
    def _row(vals, nd=4):
        return " | ".join(("%.*f" % (nd, v)) for v in vals)

    cmp_lines = []
    for case in STIFFNESS_CASES:
        c = comparison[case]
        cmp_lines.append(
            "| %s | %s | %s | %s |" % (
                case, _row(c["hf_bending_first3_hz"]),
                _row(c["rom_witness_e21_full_precision_hz"]),
                _row(c["signed_deviation_hf_minus_rom_pct_vs_e21"], 4)))
    cmp_table = ("\n".join(cmp_lines))

    nom6 = eigen_cases["nominal"]["mode_descriptors_first6"]
    desc_lines = []
    for d in nom6:
        desc_lines.append("| %d | %.4f | %s | leaf-%s | %s |" % (
            d["mode_rank"], d["frequency_hz"], d["class"], d["dominant_leaf"],
            d["dominant_compliance"]))
    desc_table = "\n".join(desc_lines)

    conv = convergence
    conv_lines = []
    for i in range(8):
        conv_lines.append("| %d | %.4f | %.4f | %.4f | %+.4f%% | %s |" % (
            i + 1, conv["per_mesh"]["N10"]["frequencies_hz_first8"][i],
            conv["per_mesh"]["N20"]["frequencies_hz_first8"][i],
            conv["per_mesh"]["N40"]["frequencies_hz_first8"][i],
            conv["shift_pct_N20_vs_N40_first8"][i],
            conv["per_mesh"]["N20"]["mode_classes_first8"][i]))
    conv_table = "\n".join(conv_lines)

    evid_md = f"""# R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1 — 人读版（机器字段以同basename JSON 为准）

- schema: `R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1`
- 生成时间：{generated}（宿主机本地钟）
- 生成方：{GENERATOR}
- 状态：CANDIDATE_PROVISIONAL_BANDS__NOT_CERTIFIED；`next_stage_authorized=false`；`release_credit=false`
- 范围：定基座自由振动，单翼，展开锁定平直构型；ζ=0 守恒审计车道。

## 名义构型前 6 阶模态（N=20/叶，ndof={model.ndof}）

| # | f (Hz) | 类别 | 主导叶 | 主导柔顺 |
|---|---|---|---|---|
{desc_table}

## HF 前 3 阶弯曲模态 vs ROM 见证（REPORT ONLY，禁止调参）

| 工况 | HF bending first-3 (Hz) | ROM e21 全精度 (Hz) | 有符号偏差 (%) |
|---|---|---|---|
{cmp_table}

锚点漂移（模态1，名义）：{anchor:+.4f}%（{anchor_hz:+.6f} Hz）。偏差归因：叶柔性串联
柔顺（HF 低于刚叶 ROM，阶次越高越显著，第 3 阶落向叶悬臂尺度 49.15 Hz 名义）、多叶
耦合分布曲率、铰柔顺登记带不变（含 latch，SLOT-03）、MC-A 铰质量刚性非随动记账。

## 网格收敛（名义；按阶次对齐）

| # | N=10 (Hz) | N=20 (Hz) | N=40 (Hz) | N20 vs N40 偏移 | 类别 |
|---|---|---|---|---|---|
{conv_table}

首 3 阶 |偏移| max = {convergence['max_abs_shift_pct_first3_N20_vs_N40']:.6f}%（门槛 <1%）。

## 检查摘要

- 质量闭合：HF 动能叶质量 {mass_closure['hf_kinetic_leaf_mass_kg']:.15f} kg（期望 0.54）
  + 刚性记账 0.24 = {mass_closure['hf_total_per_wing_kg']:.15f} kg/翼（期望 0.78，
  绝对误差 {mass_closure['abs_error_total_kg']:.3e} kg）。
- SPD：M min-eig {spd['M_hf_min_eigenvalue']:.6e}；K（锁定名义）min-eig
  {spd['K_hf_latched_nominal_min_eigenvalue']:.6e}；min ω² {spd['min_generalized_omega2']:.6e}。
- 解锁零空间健全性：k_root=k_inter=0 时恰 {null_space['near_zero_eigenvalue_count']} 个近零
  特征值（期望 3：根铰/铰1/铰2 三刚体链转；扭转车道因根端夹紧无刚体模态）→ {null_space['verdict']}。
- 刚化极限：EI×1e9 时 HF 弯曲前 3 阶 vs ROM 全精度 max 相对差
  {rigid_limit['max_rel_diff']:.3e} → {rigid_limit['verdict']}。
- ROM 独立复现：Mqq max-abs 差 {rom_check['Mqq_max_abs_diff_vs_e21_kg_m2']:.3e} kg·m²；
  五工况频率 max-abs 差 {rom_check['five_case_freq_max_abs_diff_vs_e21_hz']:.3e} Hz。

## 意外与观察（逐字自证据 JSON）

""" + "\n".join("- " + s for s in surprises) + f"""

## 扭转/阻尼角点（新车道）

- GJ 角点：GJ_low={GJ_LOW:.6f} / nominal={GJ_NOM:.6f} / high={GJ_HIGH:.6f} N·m²（名义刚度、
  名义 EI 下各跑一组特征值，见 JSON eigen_cases）。
- ζ 角点（耗散车道 report-only）：ζ ∈ {{0.002, 0.005, 0.02}}；阻尼频率偏移
  √(1-ζ²) 与衰减时间常数见 JSON damping_lane；守恒结论一律出自 ζ=0 车道。

## nonclaims（逐字）

""" + "\n".join("- " + s for s in evidence["nonclaims"]) + "\n"
    OUT_EVID_MD.write_text(evid_md, encoding="utf-8")

    # ---------------- README ----------------
    readme = f"""# round2_hf_model — R2 高保真三叶/翼全柔性模型（Full-Flex F1）

Wave：{WAVE}；角色：AGENT-B1。生成时间 {generated}（宿主机本地钟）。

## 文件

| 文件 | 角色 |
|---|---|
| `build_r2_hf_model.py` | 构建器：装配 M_hf/K_hf、跑全部特征工况、自检、落盘全部产物（纯 numpy/scipy） |
| `R2_FULLFLEX_HF_MODEL_V1.yaml` | 模型卡（机器 SSOT；含 GJ 推导全文、阻尼带、MC-A 记账、HOLD 逐字） |
| `R2_FULLFLEX_HF_MODEL_V1.md` | 模型卡人读版 |
| `R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json` | 特征值证据（装配矩阵、10 工况、收敛、质量闭合、SPD、零空间、HF-vs-ROM 对比） |
| `R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.md` | 证据人读版 |
| `R2_FULLFLEX_HF_VALIDATION_GATE_V1.json` | fail-closed 验证门（机器裁决） |
| `R2_FULLFLEX_HF_VALIDATION_GATE_V1.md` | 验证门人读版 |

## 复现

```
python -B build_r2_hf_model.py
```

（工作目录任意；脚本只写本目录，上游文件只读并逐针复算 sha256。）

## 纪律要点

- HF-vs-ROM 对比 REPORT ONLY；禁止调参凑 ROM 见证。
- 独立 latch 刚度保持 null（HOLD_LATCH_GEOMETRY_NOT_MODELLED）；板间 kθ 带为含 latch 柔顺。
- 阻尼双车道：ζ=0 守恒审计 vs ζ≠0 耗散预测（report-only）。
- 遗留 R1 车道禁值黑名单由验证门机器扫描本目录全部产物。
- 本包不是 ROM、不是耦合评估；`r2_full_flexible_coupling` 保持 NOT_EVALUATED；
  e15 `REPEAT_ANCF_CERTIFICATION` 不变；`next_stage_authorized=false`、`release_credit=false`。
"""
    OUT_README.write_text(readme, encoding="utf-8")

    # ---------------- blacklist self-scan over emitted files ----------------
    scan_files = [HERE / "build_r2_hf_model.py", OUT_CARD_YAML, OUT_CARD_MD,
                  OUT_EVID_JSON, OUT_EVID_MD, OUT_README]
    hits = scan_needles(scan_files)
    unclassified = [h for h in hits if h["context_class"] == "UNCLASSIFIED_CONTEXT"]
    narrative_hits = [h for h in hits if h["file"] != "build_r2_hf_model.py"]

    # ---------------- validation gate ----------------
    criteria = []

    g1_ok = (mass_closure["abs_error_kg"] < 1e-12
             and mass_closure["abs_error_total_kg"] < 1e-12)
    criteria.append({
        "id": "G1_MASS_CLOSURE_EXACT",
        "criterion": "HF total per wing == 0.78 kg exact to fp noise (kinetic leaf 0.54 + "
                     "MC-A rigid non-tracking ledger 0.24)",
        "measured": {"kinetic_leaf_mass_kg": mass_closure["hf_kinetic_leaf_mass_kg"],
                     "abs_error_leaf_kg": mass_closure["abs_error_kg"],
                     "total_per_wing_kg": mass_closure["hf_total_per_wing_kg"],
                     "abs_error_total_kg": mass_closure["abs_error_total_kg"]},
        "threshold": "abs error < 1e-12 kg",
        "evidence": "R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json mass_closure",
        "verdict": "PASS" if g1_ok else "FAIL"})

    g2_ok = bool(spd["M_spd"] and spd["K_latched_spd"] and spd["min_generalized_omega2"] > 0.0)
    criteria.append({
        "id": "G2_SPD",
        "criterion": "M_hf and K_hf (latched nominal) symmetric positive definite; all "
                     "generalized omega^2 > 0",
        "measured": spd,
        "threshold": "min eigenvalues > 0",
        "evidence": "R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json spd_checks",
        "verdict": "PASS" if g2_ok else "FAIL"})

    g3_val = convergence["max_abs_shift_pct_first3_N20_vs_N40"]
    g3_ok = g3_val < 1.0
    criteria.append({
        "id": "G3_MESH_CONVERGENCE",
        "criterion": "mesh convergence < 1% on first 3 modes between N=20 and N=40 per leaf",
        "measured": {"max_abs_shift_pct_first3_N20_vs_N40": g3_val,
                     "shift_pct_N20_vs_N40_first8": convergence["shift_pct_N20_vs_N40_first8"]},
        "threshold": "< 1.0 %",
        "evidence": "R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json mesh_convergence",
        "verdict": "PASS" if g3_ok else "FAIL"})

    g4_ok = (len(unclassified) == 0 and len(narrative_hits) == 0)
    criteria.append({
        "id": "G4_NO_FORBIDDEN_R1_VALUES",
        "criterion": "no forbidden R1-lane values anywhere in outputs; blacklist needles "
                     "scanned over own files; hits tolerated only as detector definitions "
                     "inside build_r2_hf_model.py / this gate",
        "blacklist_needles": NEEDLES,
        "measured": {"files_scanned": [p.name for p in scan_files],
                     "hits": hits,
                     "unclassified_hit_count": len(unclassified),
                     "narrative_file_hit_count": len(narrative_hits),
                     "gate_files_note": "this gate JSON/MD contain the needle literals only "
                                        "inside the blacklist_needles detector definition"},
        "threshold": "unclassified hits == 0 and narrative hits == 0",
        "evidence": "scan executed by build_r2_hf_model.py after emission of card/evidence/README",
        "verdict": "PASS" if g4_ok else "FAIL"})

    card_yaml_parsed = yaml.safe_load(OUT_CARD_YAML.read_text(encoding="utf-8"))
    latch_card_null = card_yaml_parsed["hinge_stiffness"]["latch"]["independent_latch_stiffness_Nm_per_rad"] is None
    latch_evid_null = evidence["parameters"]["latch_independent_stiffness_Nm_per_rad"] is None
    g5_ok = bool(latch_card_null and latch_evid_null)
    criteria.append({
        "id": "G5_NO_ZERO_FILLED_UNKNOWNS",
        "criterion": "independent latch stiffness stays explicit null (never zero-filled); "
                     "HOLD_LATCH_GEOMETRY_NOT_MODELLED verbatim",
        "measured": {"card_latch_is_null": latch_card_null,
                     "evidence_latch_is_null": latch_evid_null},
        "threshold": "both null",
        "evidence": "card YAML hinge_stiffness.latch + evidence JSON parameters",
        "verdict": "PASS" if g5_ok else "FAIL"})

    bands = {
        "EI": card_yaml_parsed["leaf"]["EI_Nm2"]["class"],
        "k_theta_root": card_yaml_parsed["hinge_stiffness"]["k_theta_root_Nm_per_rad"]["class"],
        "k_theta_inter": card_yaml_parsed["hinge_stiffness"]["k_theta_inter_Nm_per_rad"]["class"],
        "GJ": card_yaml_parsed["gj_derivation"]["class"],
        "zeta": card_yaml_parsed["damping"]["class"],
    }
    g6_ok = all("PROVISIONAL_DERIVED" in str(v) for v in bands.values())
    criteria.append({
        "id": "G6_PROVISIONAL_CLASSES_SPELLED",
        "criterion": "PROVISIONAL_DERIVED class spelled on every candidate band "
                     "(EI, GJ, zeta, k_theta_root, k_theta_inter)",
        "measured": bands,
        "threshold": "every band carries PROVISIONAL_DERIVED",
        "evidence": "card YAML parsed programmatically by the gate builder",
        "verdict": "PASS" if g6_ok else "FAIL"})

    overall = "PASS" if all(c["verdict"] == "PASS" for c in criteria) else "FAIL"

    gate = {
        "schema": "R2_FULLFLEX_HF_VALIDATION_GATE_V1",
        **header_common,
        "gate_object": "R2_FULLFLEX_HF_MODEL_V1.yaml + R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json "
                       "(R2 high-fidelity three-leaf-per-wing flexible model, Full-Flex F1)",
        "fail_closed": True,
        "criteria": criteria,
        "overall_gate": overall,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "test_pass_note": "test PASS != gate PASS; this gate's PASS only discharges the six "
                          "criteria above at candidate level and authorizes nothing",
        "nonclaims": [
            "not a ROM yet (no modal truncation delivered)",
            "not a coupled evaluation (fixed-base per-wing only)",
            "r2_full_flexible_coupling not closed by this file (stays NOT_EVALUATED)",
            "e15 REPEAT_ANCF_CERTIFICATION unchanged",
            "no production/manufacturing/qualification/launch/flight authority",
            "no PROVISIONAL band promoted; candidate != authority",
        ],
        "verification_record": {
            "upstream_hash_recomputation": hash_records,
            "odr45_49_pin_status": odr45_status,
            "evidence_json_sha256": sha256_file(OUT_EVID_JSON),
            "card_yaml_sha256": sha256_file(OUT_CARD_YAML),
            "builder_sha256": sha256_file(HERE / "build_r2_hf_model.py"),
        },
        "evidence_links": evidence_links + [
            {"path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                     "r2_full_flex_closure/round2_hf_model/R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json",
             "sha256": sha256_file(OUT_EVID_JSON),
             "role": "gated evidence artifact"},
            {"path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                     "r2_full_flex_closure/round2_hf_model/R2_FULLFLEX_HF_MODEL_V1.yaml",
             "sha256": sha256_file(OUT_CARD_YAML),
             "role": "gated model card"}],
        "self_hash_policy": SELF_HASH_POLICY,
        "companion_human_readable": "R2_FULLFLEX_HF_VALIDATION_GATE_V1.md (same basename; "
                                    "structured JSON fields govern on conflict)",
    }
    OUT_GATE_JSON.write_text(json.dumps(gate, indent=1, ensure_ascii=False), encoding="utf-8")

    gate_md = f"""# R2_FULLFLEX_HF_VALIDATION_GATE_V1 — 人读版（机器字段以同basename JSON 为准）

- schema: `R2_FULLFLEX_HF_VALIDATION_GATE_V1`
- 生成时间：{generated}（宿主机本地钟）
- 生成方：{GENERATOR}
- 裁决对象：`R2_FULLFLEX_HF_MODEL_V1.yaml` + `R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json`
- **overall_gate = {overall}**；`review_status=PENDING_OWNER_REVIEW`；
  `next_stage_authorized=false`；`release_credit=false`；fail-closed。

## 判据

| ID | 判据 | 实测 | 门槛 | 裁决 |
|---|---|---|---|---|
""" + "\n".join(
        "| %s | %s | %s | %s | **%s** |" % (
            c["id"], c["criterion"].split(";")[0],
            json.dumps(c["measured"], ensure_ascii=False)[:120] + "…",
            c["threshold"], c["verdict"])
        for c in criteria) + f"""

## 黑名单扫描（检测器定义）

needles = {json.dumps(NEEDLES)}（遗留 R1 车道禁值；本目录产物中仅以检测器定义语境出现；
命中明细与语境分类见 JSON criteria[3].measured）。

## nonclaims（逐字）

""" + "\n".join("- " + s for s in gate["nonclaims"]) + f"""

## 备注

- test PASS ≠ gate PASS；本 gate PASS 只在候选级解除上述六条判据，不授权任何下一阶段。
- ODR-45..49 钉状态：{odr45_status}。
- self_hash_policy：{SELF_HASH_POLICY}
"""
    OUT_GATE_MD.write_text(gate_md, encoding="utf-8")

    # ---------------- console summary ----------------
    print("R2_FULLFLEX_HF_MODEL_OK  overall_gate=%s" % overall)
    print("ndof=%d  elements/leaf=%d" % (model.ndof, model.n))
    print("GJ band [%.6f, %.6f] N m2, nominal %.6f" % (GJ_LOW, GJ_HIGH, GJ_NOM))
    print("nominal first 6 modes (Hz, class):")
    for d in eigen_cases["nominal"]["mode_descriptors_first6"]:
        print("  #%d  %9.4f  %s  (%s)" % (d["mode_rank"], d["frequency_hz"],
                                           d["class"], d["dominant_compliance"]))
    print("HF bending first3 vs ROM witnesses (signed %):")
    for case in STIFFNESS_CASES:
        c = comparison[case]
        print("  %-20s HF=%s  ROM=%s  dev=%s" % (
            case, ["%.4f" % x for x in c["hf_bending_first3_hz"]],
            ["%.4f" % x for x in c["rom_witness_e21_full_precision_hz"]],
            ["%+.3f" % x for x in c["signed_deviation_hf_minus_rom_pct_vs_e21"]]))
    print("mass closure: kinetic=%.15f total=%.15f kg/wing (err %.2e)" % (
        mass_closure["hf_kinetic_leaf_mass_kg"], mass_closure["hf_total_per_wing_kg"],
        mass_closure["abs_error_total_kg"]))
    print("SPD: M min=%.3e K min=%.3e w2min=%.3e" % (
        spd["M_hf_min_eigenvalue"], spd["K_hf_latched_nominal_min_eigenvalue"],
        spd["min_generalized_omega2"]))
    print("null-space unlatched: %d near-zero (expect 3) -> %s" % (
        null_space["near_zero_eigenvalue_count"], null_space["verdict"]))
    print("rigid-limit vs ROM max rel diff: %.3e -> %s" % (
        rigid_limit["max_rel_diff"], rigid_limit["verdict"]))
    print("mesh convergence first3 |shift| N20 vs N40: %.6f %%" % g3_val)
    print("blacklist scan: %d hits (%d unclassified, %d in narrative files)" % (
        len(hits), len(unclassified), len(narrative_hits)))
    print("criteria: " + ", ".join("%s=%s" % (c["id"], c["verdict"]) for c in criteria))
    print("odr45_49 pin status: %s" % odr45_status)


if __name__ == "__main__":
    main()
