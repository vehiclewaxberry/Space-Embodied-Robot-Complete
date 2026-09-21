#!/usr/bin/env python
"""Build the isolated Solar R2 per-wing HF model and five-mode ROM V2.

The package is component-level, deployed/latched, linear and fixed-base.  It
does not run the coupled e22 scenarios, does not alter any frozen upstream
asset, and never converts provisional parameters into measured authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml
from scipy.linalg import eigh

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ECR = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2"
E21_PATH = (ROOT / "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics"
            / "results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json")
OWNER_ATTACHMENT = Path(
    "C:/Users/stude/.codex/attachments/097124c4-bbc4-4459-85c4-748019414866/pasted-text.txt")
OWNER_ATTACHMENT_SHA = "67821E04869BE8202CF2473980B73AA4CE595B9689CC9D54F340820C0D38F773"

OUT_MODEL = HERE / "R2_HF_MODEL_V2.yaml"
OUT_EVID = HERE / "R2_HF_NUMERICAL_EVIDENCE_V2.json"
OUT_ROM = HERE / "R2_FIVE_MODE_ROM_V2.json"
OUT_ENV = HERE / "R2_FLEXIBILITY_VALIDITY_ENVELOPE_V2.json"
OUT_NPZ = HERE / "R2_HF_ROM_NUMERICAL_DATA_V2.npz"
OUT_GATE = HERE / "R2_FULL_FLEX_HF_ROM_GATE_V2.json"
OWNER_RECORD = HERE / "OWNER_AUTHORITY_TRANSCRIPTION_V1.yaml"
INDEPENDENT_SCRIPT = HERE / "tests/independent_recompute.py"
INDEPENDENT_REPORT = HERE / "tests/INDEPENDENT_RECOMPUTE_V2.json"

TZ = timezone(timedelta(hours=8))

# Geometry and mass.  Root y is deliberately the build/STEP/kinematic
# arithmetic result, not the stale 114.9-mm text registration.
ROOT_Y = 0.1154
ROOT_Z = -0.10815
LEAF_M = 0.18
LEAF_L = 0.200
LEAF_CHORD = 0.300
LEAF_T = 0.0025
MU = LEAF_M / LEAF_L
RHOJ_BEND = MU * LEAF_T ** 2 / 12.0
JM_TORSION = MU * (LEAF_CHORD ** 2 + LEAF_T ** 2) / 12.0
I_LEAF_COM_X = LEAF_M * (LEAF_L ** 2 + LEAF_T ** 2) / 12.0

RIGID_LEDGER = {
    "root_hinge": 0.05,
    "two_inter_panel_hinges": 0.06,
    "hdrm": 0.08,
    "harness": 0.05,
}

EI = {"low": 3.333, "nominal": 11.109, "high": 33.327}
K_ROOT = {"low": 50.0, "nominal": 200.0, "high": 800.0}
K_INTER = {"low": 20.0, "nominal": 100.0, "high": 400.0}
ZETA = {"low": 0.002, "nominal": 0.005, "high": 0.020}

# Quantitative small-angle domain for downstream response back-checks.  This is
# an engineering validity bound, not a material allowables or qualification
# claim.  At 0.05 rad, the chord-normal geometric error 1-cos(theta) is below
# 0.125 %, and the relative sin(theta) linearisation error is below 0.042 %.
LINEAR_ANGLE_LIMIT_RAD = 0.05
LINEAR_NODE_DEFLECTION_LIMIT_M = 3.0 * LEAF_L * LINEAR_ANGLE_LIMIT_RAD
LINEAR_GEOMETRY_ERROR_FRACTION = 1.0 - math.cos(LINEAR_ANGLE_LIMIT_RAD)

# Bounded torsion estimate for the registered candidate sandwich.  The bounds
# represent open-section/free-warping and closed-cell/edge-closed idealizations.
E_FACE = 70.0e9
NU_FACE = 0.3
G_FACE = E_FACE / (2.0 * (1.0 + NU_FACE))
T_FACE = 0.2e-3
T_CORE = 2.1e-3
G_CORE = 100.0e6
GJ_LOW = LEAF_CHORD / 3.0 * (2.0 * G_FACE * T_FACE ** 3 + G_CORE * T_CORE ** 3)
H_CELL = T_CORE + T_FACE
A_CELL = LEAF_CHORD * H_CELL
GJ_HIGH = 4.0 * A_CELL ** 2 / (2.0 * LEAF_CHORD / (G_FACE * T_FACE))
GJ = {"low": GJ_LOW, "nominal": math.sqrt(GJ_LOW * GJ_HIGH), "high": GJ_HIGH}

CORNERS = {
    "LOW": {"EI": EI["low"], "GJ": GJ["low"], "k_root": K_ROOT["low"],
            "k_inter": K_INTER["low"], "zeta": ZETA["low"]},
    "NOMINAL": {"EI": EI["nominal"], "GJ": GJ["nominal"],
                "k_root": K_ROOT["nominal"], "k_inter": K_INTER["nominal"],
                "zeta": ZETA["nominal"]},
    "HIGH": {"EI": EI["high"], "GJ": GJ["high"], "k_root": K_ROOT["high"],
             "k_inter": K_INTER["high"], "zeta": ZETA["high"]},
}

FIVE_L2_CASES = {
    "nominal": (200.0, 100.0),
    "all_low": (50.0, 20.0),
    "all_high": (800.0, 400.0),
    "root_low_inter_high": (50.0, 400.0),
    "root_high_inter_low": (800.0, 20.0),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def clean(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def dump_json(path: Path, obj) -> None:
    path.write_text(json.dumps(clean(obj), indent=2, ensure_ascii=False), encoding="utf-8")


def maxabs(a) -> float:
    return float(np.max(np.abs(np.asarray(a, dtype=float))))


class WingFE:
    """Three flexible leaves, three bending-compliance joints and torsion.

    Bending DOFs are global-z translations and local-span slopes.  Each
    inter-panel hinge duplicates the slope DOF while retaining continuous
    translation.  Torsion is a separate spanwise lane, continuous through the
    inter-panel hinges and clamped at the root reference.
    """

    def __init__(self, elements_per_leaf: int):
        self.n = int(elements_per_leaf)
        self.ne = 3 * self.n
        self.le = LEAF_L / self.n
        self.hinge_nodes = (self.n, 2 * self.n)
        idx = 0
        self.w = {}
        for node in range(self.ne + 1):
            self.w[node] = idx
            idx += 1
        self.th = {}
        for node in range(self.ne + 1):
            if node in self.hinge_nodes:
                self.th[(node, "L")] = idx
                idx += 1
                self.th[(node, "R")] = idx
                idx += 1
            else:
                self.th[node] = idx
                idx += 1
        self.phi = {}
        for node in range(self.ne + 1):
            self.phi[node] = idx
            idx += 1
        self.ndof_full = idx
        self.fixed_full = (self.w[0], self.phi[0])
        self.free_full = np.asarray([i for i in range(idx) if i not in self.fixed_full], int)
        self.full_to_reduced = {int(v): i for i, v in enumerate(self.free_full)}
        self.ndof = len(self.free_full)
        self.torsion_reduced = np.asarray(
            [self.full_to_reduced[self.phi[n]] for n in range(1, self.ne + 1)], int)
        self.coordinate_scale = np.asarray([
            LEAF_L if self._kind(int(fi)) == "w" else 1.0 for fi in self.free_full
        ])

    def _kind(self, full_index: int) -> str:
        if full_index in self.w.values():
            return "w"
        if full_index in self.phi.values():
            return "phi"
        return "theta"

    def _theta_left(self, node: int) -> int:
        return self.th[(node, "L")] if node in self.hinge_nodes else self.th[node]

    def _theta_right(self, node: int) -> int:
        return self.th[(node, "R")] if node in self.hinge_nodes else self.th[node]

    def bend_dofs(self, element: int) -> list[int]:
        return [self.w[element], self._theta_right(element),
                self.w[element + 1], self._theta_left(element + 1)]

    def torsion_dofs(self, element: int) -> list[int]:
        return [self.phi[element], self.phi[element + 1]]

    def bend_element(self, ei: float) -> tuple[np.ndarray, np.ndarray]:
        l = self.le
        K = ei / l ** 3 * np.asarray([
            [12, 6*l, -12, 6*l],
            [6*l, 4*l*l, -6*l, 2*l*l],
            [-12, -6*l, 12, -6*l],
            [6*l, 2*l*l, -6*l, 4*l*l]], float)
        Mt = MU * l / 420.0 * np.asarray([
            [156, 22*l, 54, -13*l],
            [22*l, 4*l*l, 13*l, -3*l*l],
            [54, 13*l, 156, -22*l],
            [-13*l, -3*l*l, -22*l, 4*l*l]], float)
        Mr = RHOJ_BEND / (30.0*l) * np.asarray([
            [36, 3*l, -36, 3*l],
            [3*l, 4*l*l, -3*l, -l*l],
            [-36, -3*l, 36, -3*l],
            [3*l, -l*l, -3*l, 4*l*l]], float)
        return K, Mt + Mr

    def torsion_element(self, gj: float) -> tuple[np.ndarray, np.ndarray]:
        l = self.le
        K = gj / l * np.asarray([[1, -1], [-1, 1]], float)
        M = JM_TORSION * l / 6.0 * np.asarray([[2, 1], [1, 2]], float)
        return K, M

    @staticmethod
    def _add(A: np.ndarray, dofs: list[int], Ae: np.ndarray) -> None:
        A[np.ix_(dofs, dofs)] += Ae

    def assemble_full(self, ei: float, gj: float, k_root: float,
                      k_inter: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        M = np.zeros((self.ndof_full, self.ndof_full))
        Kel = np.zeros_like(M)
        Kspr = np.zeros_like(M)
        Kb, Mb = self.bend_element(ei)
        Kt, Mt = self.torsion_element(gj)
        for e in range(self.ne):
            self._add(M, self.bend_dofs(e), Mb)
            self._add(Kel, self.bend_dofs(e), Kb)
            self._add(M, self.torsion_dofs(e), Mt)
            self._add(Kel, self.torsion_dofs(e), Kt)
        root = self.th[0]
        Kspr[root, root] += k_root
        for hn in self.hinge_nodes:
            a, b = self.th[(hn, "L")], self.th[(hn, "R")]
            Kspr[a, a] += k_inter
            Kspr[b, b] += k_inter
            Kspr[a, b] -= k_inter
            Kspr[b, a] -= k_inter
        return M, Kel, Kspr

    def reduced(self, A: np.ndarray) -> np.ndarray:
        return A[np.ix_(self.free_full, self.free_full)]

    def matrices(self, ei: float, gj: float, k_root: float,
                 k_inter: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        Mf, Kef, Ksf = self.assemble_full(ei, gj, k_root, k_inter)
        return Mf, self.reduced(Mf), self.reduced(Kef), self.reduced(Ksf)

    def rigid_translation_full(self) -> np.ndarray:
        u = np.zeros(self.ndof_full)
        for d in self.w.values():
            u[d] = 1.0
        return u

    def piecewise_rigid_Q(self) -> np.ndarray:
        Qf = np.zeros((self.ndof_full, 3))
        for node, d in self.w.items():
            s = node * self.le
            Qf[d, :] = [s, max(0.0, s-LEAF_L), max(0.0, s-2.0*LEAF_L)]
        slopes = (np.asarray([1.0, 0.0, 0.0]),
                  np.asarray([1.0, 1.0, 0.0]),
                  np.asarray([1.0, 1.0, 1.0]))
        for key, d in self.th.items():
            if isinstance(key, tuple):
                node, side = key
                if node == self.hinge_nodes[0]:
                    leaf = 0 if side == "L" else 1
                else:
                    leaf = 1 if side == "L" else 2
            else:
                node = key
                if node <= self.hinge_nodes[0]:
                    leaf = 0
                elif node <= self.hinge_nodes[1]:
                    leaf = 1
                else:
                    leaf = 2
            Qf[d, :] = slopes[leaf]
        return Qf[self.free_full, :]

    def dof_semantics(self) -> list[dict]:
        """Machine-readable meaning of every reduced HF coordinate."""
        semantic_by_full = {}
        for node, full in self.w.items():
            semantic_by_full[full] = {
                "kind": "TRANSVERSE_W", "node": node,
                "span_m": node * self.le, "side": None, "unit": "m"}
        for key, full in self.th.items():
            if isinstance(key, tuple):
                node, side = key
            else:
                node, side = key, "CONTINUOUS"
            semantic_by_full[full] = {
                "kind": "BENDING_SLOPE_THETA", "node": node,
                "span_m": node * self.le, "side": side, "unit": "rad"}
        for node, full in self.phi.items():
            semantic_by_full[full] = {
                "kind": "TORSION_PHI", "node": node,
                "span_m": node * self.le, "side": None, "unit": "rad"}
        return [
            {"reduced_index_0based": reduced, "full_index_0based": int(full),
             **semantic_by_full[int(full)]}
            for reduced, full in enumerate(self.free_full)
        ]

    def reconstruction_operators(self) -> dict[str, np.ndarray]:
        """Linear operators from reduced HF q to observable wing quantities.

        Fixed reference coordinates (root w and root torsion) are represented
        by all-zero rows, so downstream consumers never have to infer or
        silently reinsert constrained DOFs.
        """
        def row_for_full(full: int) -> np.ndarray:
            row = np.zeros(self.ndof)
            reduced = self.full_to_reduced.get(int(full))
            if reduced is not None:
                row[reduced] = 1.0
            return row

        w_nodes = np.vstack([row_for_full(self.w[n])
                             for n in range(self.ne + 1)])
        theta_items = sorted(
            self.th.items(),
            key=lambda kv: ((kv[0][0] if isinstance(kv[0], tuple) else kv[0]),
                            (kv[0][1] if isinstance(kv[0], tuple) else "CONTINUOUS")))
        theta_rows = np.vstack([row_for_full(full) for _, full in theta_items])
        torsion_nodes = np.vstack([row_for_full(self.phi[n])
                                   for n in range(self.ne + 1)])
        hinge_relative = np.vstack([
            row_for_full(self.th[0]),
            row_for_full(self.th[(self.hinge_nodes[0], "R")])
            - row_for_full(self.th[(self.hinge_nodes[0], "L")]),
            row_for_full(self.th[(self.hinge_nodes[1], "R")])
            - row_for_full(self.th[(self.hinge_nodes[1], "L")]),
        ])
        return {
            "w_nodes": w_nodes,
            "theta_dofs": theta_rows,
            "torsion_nodes": torsion_nodes,
            "hinge_relative": hinge_relative,
            "tip_w": w_nodes[-1:, :],
        }

    @staticmethod
    def hermite(x: float, l: float) -> tuple[np.ndarray, np.ndarray]:
        r = x/l
        N = np.asarray([1-3*r*r+2*r**3,
                        l*(r-2*r*r+r**3),
                        3*r*r-2*r**3,
                        l*(-r*r+r**3)])
        Nr = np.asarray([(-6*r+6*r*r)/l,
                         1-4*r+3*r*r,
                         (6*r-6*r*r)/l,
                         -2*r+3*r*r])
        return N, Nr

    def participation(self, wing_sign: int) -> tuple[np.ndarray, np.ndarray]:
        Bt = np.zeros((self.ndof_full, 3))
        Br = np.zeros((self.ndof_full, 3))
        gx, gw = np.polynomial.legendre.leggauss(5)
        for e in range(self.ne):
            bd = self.bend_dofs(e)
            td = self.torsion_dofs(e)
            for xi, wi in zip(gx, gw):
                x = 0.5*self.le*(1.0+xi)
                weight = 0.5*self.le*wi
                N, Nr = self.hermite(x, self.le)
                y_abs = wing_sign * (ROOT_Y + e*self.le + x)
                for a, d in enumerate(bd):
                    Bt[d, 2] += MU*N[a]*weight
                    Br[d, 0] += (MU*N[a]*y_abs +
                                 RHOJ_BEND*wing_sign*Nr[a])*weight
                Nt = np.asarray([1.0-x/self.le, x/self.le])
                for a, d in enumerate(td):
                    Br[d, 1] += wing_sign*JM_TORSION*Nt[a]*weight
        return Bt[self.free_full, :], Br[self.free_full, :]

    def mode_class(self, M: np.ndarray, v: np.ndarray) -> tuple[str, float]:
        idx = self.torsion_reduced
        fraction = float(v[idx] @ M[np.ix_(idx, idx)] @ v[idx])
        return ("TORSION" if fraction > 0.5 else "BENDING"), fraction

    def solve(self, corner: dict, count: int | None = None):
        _, M, Kel, Kspr = self.matrices(corner["EI"], corner["GJ"],
                                        corner["k_root"], corner["k_inter"])
        K = Kel + Kspr
        w2, V = eigh(K, M)
        w2 = np.maximum(w2, 0.0)
        if count is not None:
            w2, V = w2[:count], V[:, :count]
        f = np.sqrt(w2)/(2.0*math.pi)
        classes = [self.mode_class(M, V[:, i])[0] for i in range(V.shape[1])]
        fractions = [self.mode_class(M, V[:, i])[1] for i in range(V.shape[1])]
        return M, K, f, V, classes, fractions


def l2_Mqq_at_q_zero() -> np.ndarray:
    """Rigid-leaf kinetic Hessian at q=0; dq is velocity only."""
    M = np.zeros((3, 3))
    for leaf in range(3):
        Jv = np.zeros(3)
        Jw = np.zeros(3)
        for joint in range(leaf + 1):
            Jv[joint] = (leaf-joint+0.5)*LEAF_L
            Jw[joint] = 1.0
        M += LEAF_M*np.outer(Jv, Jv) + I_LEAF_COM_X*np.outer(Jw, Jw)
    return M


def lane_frequencies(f: np.ndarray, classes: list[str], nb=3, nt=2) -> dict:
    bend = [float(x) for x, c in zip(f, classes) if c == "BENDING"][:nb]
    tors = [float(x) for x, c in zip(f, classes) if c == "TORSION"][:nt]
    return {"bending_first3_hz": bend, "torsion_first2_hz": tors}


def make_crom(Mr: np.ndarray, Kr: np.ndarray, zeta: float) -> np.ndarray:
    lam, U = eigh(Kr, Mr)
    omega = np.sqrt(np.maximum(lam, 0.0))
    return Mr @ U @ np.diag(2.0*zeta*omega) @ U.T @ Mr


def coverage(M: np.ndarray, Phi: np.ndarray, B: np.ndarray) -> dict:
    Gamma = Phi.T @ B
    total = np.diag(B.T @ np.linalg.solve(M, B))
    retained = np.sum(Gamma*Gamma, axis=0)
    out = {}
    for i, name in enumerate(("x", "y", "z")):
        if abs(total[i]) < 1e-18:
            out[name] = {"full_effective_mass_or_inertia": 0.0,
                         "retained": 0.0, "coverage_fraction": None,
                         "null_disposition": "STRUCTURAL_ZERO_BY_MODEL_SYMMETRY"}
        else:
            out[name] = {"full_effective_mass_or_inertia": float(total[i]),
                         "retained": float(retained[i]),
                         "coverage_fraction": float(retained[i]/total[i])}
    return {"Gamma": Gamma, "coverage": out}


def parse_kinematic_arithmetic(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    def value(name):
        m = re.search(rf"^{name}\s*=\s*([0-9.]+)", text, re.MULTILINE)
        if not m:
            raise RuntimeError(f"constant {name} not found")
        return float(m.group(1))
    side, stand, thick = value("SIDE_FACE_Y"), value("STACK_STANDOFF"), value("LEAF_T")
    return {"SIDE_FACE_Y_mm": side, "STACK_STANDOFF_mm": stand,
            "LEAF_T_mm": thick,
            "arithmetic_y_abs_mm": side+stand+thick/2.0}


def main() -> None:
    generated = datetime.now(TZ).isoformat()
    model = WingFE(20)
    e21 = json.loads(E21_PATH.read_text(encoding="utf-8"))
    e21_cases = {c["case"]: c for c in e21["leaf_only"]["cases"]}
    Mqq_e21 = np.asarray(e21["leaf_only"]["Mqq_kg_m2"], float)

    upstream_paths = [
        OWNER_RECORD,
        ECR / "SOLAR_ARRAY_R2_CANDIDATE_V1.step",
        ECR / "SOLAR_ARRAY_R2_BUILD_REPORT_V2.json",
        ECR / "SOLAR_ARRAY_R2_BUILD_REPORT_V1.json",
        ECR / "solar_array_r2_kinematics.py",
        ECR / "FLEXIBLE_APPENDAGE_R2.yaml",
        ECR / "SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json",
        E21_PATH,
    ]
    upstream_hashes = {rel(p): sha256(p) for p in upstream_paths}
    owner_attachment_actual = sha256(OWNER_ATTACHMENT) if OWNER_ATTACHMENT.exists() else None

    # ODR-GPT-05 selects the CM-correct V2 report for current consumption.
    # V1 remains hash-recorded historical evidence only and is never consumed
    # as the current build-report authority.
    build_report_path = ECR / "SOLAR_ARRAY_R2_BUILD_REPORT_V2.json"
    historical_build_report_path = ECR / "SOLAR_ARRAY_R2_BUILD_REPORT_V1.json"
    build_report = json.loads(build_report_path.read_text(encoding="utf-8"))
    root_build_mm = float(build_report["parameters"]["root_hinge_line"]["y_abs_mm"])
    root_z_build_mm = float(build_report["parameters"]["root_hinge_line"]["z_mm"])
    root_arithmetic = parse_kinematic_arithmetic(ECR / "solar_array_r2_kinematics.py")
    geometry_authority = {
        "rule": "FROZEN_STEP_BUILD_KINEMATICS_ARITHMETIC__NO_AVERAGING",
        "root_hinge_S_m": {"y_abs": ROOT_Y, "z": ROOT_Z, "axis": "X_S"},
        "build_report_value_mm": {"y_abs": root_build_mm, "z": root_z_build_mm},
        "build_report_consumed": rel(build_report_path),
        "build_report_consumed_sha256": upstream_hashes[rel(build_report_path)],
        "historical_build_report_not_consumed": rel(historical_build_report_path),
        "historical_build_report_sha256": upstream_hashes[rel(historical_build_report_path)],
        "kinematics_arithmetic": root_arithmetic,
        "step_sha256": upstream_hashes[rel(ECR / "SOLAR_ARRAY_R2_CANDIDATE_V1.step")],
        "historical_conflict": {
            "id": "HIST-R2-ROOT-001",
            "stale_value_m": 0.1149,
            "locations": [
                rel(ECR / "SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V1.yaml"),
                rel(ECR / "compute_flexible_appendage_r2.py"),
                rel(ECR / "FLEXIBLE_APPENDAGE_R2.yaml"),
            ],
            "classification": "HISTORICAL_CONFIGURATION_REGISTRATION_DEFECT",
            "disposition": "REJECTED_HISTORICAL_CONFIG_DEFECT__NO_AVERAGING",
            "consumed_by_this_model": False,
        },
    }

    Mf, M, Kel_nom, Kspr_nom = model.matrices(**{
        "ei": CORNERS["NOMINAL"]["EI"], "gj": CORNERS["NOMINAL"]["GJ"],
        "k_root": CORNERS["NOMINAL"]["k_root"],
        "k_inter": CORNERS["NOMINAL"]["k_inter"]})
    K_nom = Kel_nom + Kspr_nom
    _, _, Kel_un, _ = model.matrices(EI["nominal"], GJ["nominal"], 0.0, 0.0)
    K_unlatched = Kel_un
    u_trans = model.rigid_translation_full()
    kinetic_mass = float(u_trans @ Mf @ u_trans)
    ledger_mass = sum(RIGID_LEDGER.values())
    mass_closure = {
        "method": "UNCONSTRAINED_FULL_ELEMENT_RIGID_TRANSLATION_FIELD",
        "hf_kinetic_leaf_mass_kg": kinetic_mass,
        "expected_leaf_mass_kg": 3.0*LEAF_M,
        "leaf_abs_error_kg": abs(kinetic_mass-3.0*LEAF_M),
        "rigid_nontracking_ledger_kg": RIGID_LEDGER,
        "rigid_ledger_sum_kg": ledger_mass,
        "total_per_wing_kg": kinetic_mass+ledger_mass,
        "expected_total_per_wing_kg": 0.78,
        "total_abs_error_kg": abs(kinetic_mass+ledger_mass-0.78),
        "prior_validator_defect": ("the all-ones field on the fixed-root constrained matrix is not an "
                                   "admissible rigid translation, so that validator produced a false "
                                   "mass difference (0.5343991071428571 kg); the unconstrained full-"
                                   "element rigid-body field recomputes 0.54 kg exactly"),
    }

    Mqq = l2_Mqq_at_q_zero()
    l2_check = {
        "reference_state": "q=[0,0,0] deployed-flat; dq symbols are velocities only",
        "Mqq_kg_m2": Mqq,
        "e21_Mqq_kg_m2": Mqq_e21,
        "Mqq_max_abs_diff_vs_e21_kg_m2": maxabs(Mqq-Mqq_e21),
        "prior_defect": "prior implementation inserted dq into psi and therefore used velocities as configuration angles",
        "five_cases": {},
    }
    max_df = 0.0
    for case, (kr, ki) in FIVE_L2_CASES.items():
        freq = np.sqrt(eigh(np.diag([kr, ki, ki]), Mqq,
                            eigvals_only=True))/(2.0*math.pi)
        ref_freq = np.asarray(e21_cases[case]["leaf_only_reproduced_hz"], float)
        df = maxabs(freq-ref_freq)
        max_df = max(max_df, df)
        l2_check["five_cases"][case] = {"recomputed_hz": freq,
                                         "e21_hz": ref_freq,
                                         "max_abs_diff_hz": df}
    l2_check["five_case_global_max_abs_diff_hz"] = max_df

    Q = model.piecewise_rigid_Q()
    projected_M = Q.T @ M @ Q
    rigid_projection = {
        "method": "PIECEWISE_RIGID_KINEMATIC_PROJECTION_Q",
        "artificial_stiffness_multiplier_used": False,
        "Q_shape": list(Q.shape),
        "QTMQ_kg_m2": projected_M,
        "max_abs_diff_QTMQ_vs_e21_kg_m2": maxabs(projected_M-Mqq_e21),
        "five_cases": {},
    }
    max_proj_k = 0.0
    max_proj_f = 0.0
    for case, (kr, ki) in FIVE_L2_CASES.items():
        _, _, Kel, Kspr = model.matrices(EI["nominal"], GJ["nominal"], kr, ki)
        Kp = Q.T @ (Kel+Kspr) @ Q
        Kref = np.diag([kr, ki, ki])
        fp = np.sqrt(eigh(Kp, projected_M, eigvals_only=True))/(2.0*math.pi)
        fr = np.asarray(e21_cases[case]["leaf_only_reproduced_hz"], float)
        dk, df = maxabs(Kp-Kref), maxabs(fp-fr)
        max_proj_k, max_proj_f = max(max_proj_k, dk), max(max_proj_f, df)
        rigid_projection["five_cases"][case] = {
            "QTKQ_Nm_per_rad": Kp, "target_K": Kref,
            "max_abs_K_diff": dk, "frequency_hz": fp,
            "max_abs_frequency_diff_vs_e21_hz": df}
    rigid_projection["global_max_abs_QTKQ_diff"] = max_proj_k
    rigid_projection["global_max_abs_frequency_diff_vs_e21_hz"] = max_proj_f

    S = model.coordinate_scale
    Ks = (S[:, None]*K_unlatched)*S[None, :]
    _, singular, vh = np.linalg.svd(Ks)
    sv_tol = float(np.max(singular)*1e-10)
    nullity = int(np.sum(singular < sv_tol))
    Qs = Q/S[:, None]
    Qorth, _ = np.linalg.qr(Qs)
    Nsvd = vh.T[:, -3:]
    principal = np.linalg.svd(Qorth.T @ Nsvd, compute_uv=False)
    mech_residuals = [float(np.linalg.norm(Ks@Qs[:, i]) /
                            (np.linalg.norm(Ks)*np.linalg.norm(Qs[:, i])))
                      for i in range(3)]
    nullspace = {
        "method": "DIMENSIONALLY_SCALED_SVD",
        "coordinate_scaling": "physical q = diag(scale) q_hat; w scale=0.2 m, theta/phi scale=1 rad",
        "singular_value_threshold": sv_tol,
        "near_zero_count": nullity,
        "expected_count": 3,
        "explicit_mechanism_vectors": [
            "root rotation: all three leaves move piecewise-rigidly",
            "inter-panel hinge 1 rotation: leaves 2 and 3 move piecewise-rigidly",
            "inter-panel hinge 2 rotation: leaf 3 moves piecewise-rigidly",
        ],
        "explicit_relative_residuals": mech_residuals,
        "principal_cosines_explicit_vs_svd": principal,
        "torsion_null_mode": "NONE; phi(root)=0 reference boundary",
    }

    min_M = float(np.min(np.linalg.eigvalsh(M)))
    min_K = float(np.min(np.linalg.eigvalsh(K_nom)))
    spd = {"M_min_eigenvalue": min_M, "K_nominal_min_eigenvalue": min_K,
           "M_spd": min_M > 0.0, "K_nominal_spd": min_K > 0.0}

    corner_results = {}
    corner_arrays = {}
    for name, corner in CORNERS.items():
        Mc, Kc, f, V, classes, tf = model.solve(corner)
        lane = lane_frequencies(f, classes)
        corner_results[name] = {
            "parameters": corner,
            "first12_hz": f[:12],
            "first12_classes": classes[:12],
            "first12_torsion_mass_fraction": tf[:12],
            **lane,
        }
        corner_arrays[name] = (Mc, Kc, f, V, classes)

    Mnom, _, fnom, Vnom, cnom = corner_arrays["NOMINAL"]
    bend_indices = [i for i, c in enumerate(cnom) if c == "BENDING"][:3]
    torsion_indices = [i for i, c in enumerate(cnom) if c == "TORSION"][:2]
    selection = bend_indices + torsion_indices
    labels = ["BENDING_1", "BENDING_2", "BENDING_3", "TORSION_1", "TORSION_2"]
    Phi = Vnom[:, selection]
    Mrom = Phi.T @ Mnom @ Phi
    dof_semantics = model.dof_semantics()
    reconstruction_hf = model.reconstruction_operators()
    reconstruction_rom = {name: op @ Phi
                          for name, op in reconstruction_hf.items()}
    linearity_contract = {
        "authority": "PROVISIONAL_DERIVED_SMALL_ANGLE_KINEMATIC_BOUND",
        "qualification_credit": False,
        "limits": {
            "max_abs_bending_slope_rad": LINEAR_ANGLE_LIMIT_RAD,
            "max_abs_hinge_relative_rotation_rad": LINEAR_ANGLE_LIMIT_RAD,
            "max_abs_torsion_angle_rad": LINEAR_ANGLE_LIMIT_RAD,
            "max_abs_transverse_node_displacement_m": LINEAR_NODE_DEFLECTION_LIMIT_M,
            "max_abs_tip_transverse_deflection_m": LINEAR_NODE_DEFLECTION_LIMIT_M,
        },
        "derivation": {
            "angle_rad": LINEAR_ANGLE_LIMIT_RAD,
            "one_minus_cos_angle": LINEAR_GEOMETRY_ERROR_FRACTION,
            "relative_sine_linearisation_error": (
                LINEAR_ANGLE_LIMIT_RAD - math.sin(LINEAR_ANGLE_LIMIT_RAD)
            ) / LINEAR_ANGLE_LIMIT_RAD,
            "deflection_limit_rule": "total deployed span (0.6 m) x angle limit",
        },
        "required_downstream_checks": [
            "max(abs(R_w_nodes @ eta)) <= max_abs_transverse_node_displacement_m",
            "max(abs(R_theta_dofs @ eta)) <= max_abs_bending_slope_rad",
            "max(abs(R_hinge_relative @ eta)) <= max_abs_hinge_relative_rotation_rad",
            "max(abs(R_torsion_nodes @ eta)) <= max_abs_torsion_angle_rad",
            "max(abs(R_tip_w @ eta)) <= max_abs_tip_transverse_deflection_m",
        ],
        "out_of_domain_policy": "FAIL_CLOSED__NO_LINEAR_ROM_EXTRAPOLATION",
        "replacement_trigger": "nonlinear HF correlation or as-built modal test supersedes this provisional bound",
    }

    Bt_L, Br_L = model.participation(+1)
    Bt_R, Br_R = model.participation(-1)
    part = {}
    gammas = {}
    for wing, Bt, Br in (("LEFT", Bt_L, Br_L), ("RIGHT", Bt_R, Br_R)):
        ct = coverage(Mnom, Phi, Bt)
        cr = coverage(Mnom, Phi, Br)
        part[wing] = {
            "B_t_shape": list(Bt.shape), "B_r_shape": list(Br.shape),
            "translation": ct["coverage"], "rotation": cr["coverage"],
            "active_coupling": ["bending-to-v_z", "bending-to-omega_x",
                                "torsion-to-omega_y"],
        }
        gammas[wing] = {"Gamma_t": ct["Gamma"], "Gamma_r": cr["Gamma"]}

    Kroms, Croms, rom_corner_freq = {}, {}, {}
    for name, (Mc, Kc, _, _, _) in corner_arrays.items():
        Kr = Phi.T @ Kc @ Phi
        Cr = make_crom(Mrom, Kr, CORNERS[name]["zeta"])
        Kroms[name], Croms[name] = Kr, Cr
        rom_corner_freq[name] = np.sqrt(eigh(Kr, Mrom, eigvals_only=True))/(2.0*math.pi)

    mesh = {}
    for n in (10, 20, 40):
        mm = WingFE(n)
        _, _, f, _, classes, _ = mm.solve(CORNERS["NOMINAL"])
        mesh[f"N{n}"] = lane_frequencies(f, classes)
    def rel_shift(a, b):
        return [abs(x-y)/y for x, y in zip(a, b)]
    mesh["N20_vs_N40_relative_shift"] = {
        "bending_first3": rel_shift(mesh["N20"]["bending_first3_hz"],
                                     mesh["N40"]["bending_first3_hz"]),
        "torsion_first2": rel_shift(mesh["N20"]["torsion_first2_hz"],
                                     mesh["N40"]["torsion_first2_hz"]),
    }
    mesh_max = max(mesh["N20_vs_N40_relative_shift"]["bending_first3"] +
                   mesh["N20_vs_N40_relative_shift"]["torsion_first2"])
    mesh["max_relative_shift_retained_lanes"] = mesh_max
    reconstruction_audit = {
        "reduced_dof_semantics_count": len(dof_semantics),
        "expected_reduced_dof_count": model.ndof,
        "operator_shapes_hf": {k: list(v.shape) for k, v in reconstruction_hf.items()},
        "operator_shapes_rom": {k: list(v.shape) for k, v in reconstruction_rom.items()},
        "root_w_row_max_abs": maxabs(reconstruction_hf["w_nodes"][0]),
        "root_torsion_row_max_abs": maxabs(reconstruction_hf["torsion_nodes"][0]),
        "tip_row_identity_residual": maxabs(
            reconstruction_hf["tip_w"] - reconstruction_hf["w_nodes"][-1:, :]),
        "modal_projection_max_abs_residual": max(
            maxabs(reconstruction_rom[k] - reconstruction_hf[k] @ Phi)
            for k in reconstruction_hf),
        "linearity_contract": linearity_contract,
    }

    model_card = {
        "schema": "R2_HF_MODEL_V2",
        "generated_local": generated,
        "authority": {
            "latest_owner_directives": [f"ODR-GPT-{i:02d}" for i in range(1, 7)],
            "transcription": rel(OWNER_RECORD),
            "source_attachment_sha256": OWNER_ATTACHMENT_SHA,
            "owner_accepted": False,
        },
        "class": "PROVISIONAL_DERIVED_BOUNDED_COMPONENT_MODEL",
        "configuration": "ONE_WING_DEPLOYED_FLAT_LATCHED_FIXED_BASE_LINEAR_SMALL_DEFLECTION",
        "geometry": geometry_authority,
        "architecture": {
            "wings": 2, "model_unit": "per wing", "leaves_per_wing": 3,
            "flexible_beam_elements_per_leaf": model.n,
            "bending_compliance_joints": ["root", "inter-panel-1", "inter-panel-2"],
            "torsion_lane": "independent spanwise Saint-Venant lane; continuous through inter-panel hinges",
            "root_boundaries": {"bending_translation_w": "fixed relative to base",
                                "root_bending_rotation": "k_theta_root spring",
                                "root_torsion_phi": "fixed reference"},
            "ndof_full": model.ndof_full, "ndof_after_reference_constraints": model.ndof,
            "reduced_dof_semantics_count": len(dof_semantics),
            "reconstruction_operator_names": list(reconstruction_rom),
        },
        "parameters": {
            "leaf_mass_kg": {"value": LEAF_M, "authority": "PROVISIONAL_DERIVED",
                             "basis": "3.0 kg/m2 candidate areal density x 0.06 m2"},
            "EI_Nm2": {"low": EI["low"], "nominal": EI["nominal"], "high": EI["high"],
                       "authority": "PROVISIONAL_DERIVED", "bounded_interval": True},
            "GJ_Nm2": {"low": GJ["low"], "nominal": GJ["nominal"], "high": GJ["high"],
                       "authority": "PROVISIONAL_DERIVED", "bounded_interval": True,
                       "derivation": "open-section/free-warping lower vs closed-cell edge-closed upper; geometric-mean nominal"},
            "k_theta_root_Nm_per_rad": {**K_ROOT, "authority": "PROVISIONAL_DERIVED",
                                        "bounded_interval": True},
            "k_theta_inter_latch_inclusive_Nm_per_rad": {**K_INTER,
                                                         "authority": "PROVISIONAL_DERIVED",
                                                         "bounded_interval": True,
                                                         "propagates_latch_inclusive_compliance": True},
            "independent_latch_stiffness_Nm_per_rad": {
                "value": None, "authority": "HOLD_HARDWARE_NOT_SELECTED",
                "zero_fill_forbidden": True,
                "disposition": "not independently claimed; latch-inclusive k_inter interval is propagated"},
            "modal_damping_ratio": {**ZETA, "authority": "PROVISIONAL_DERIVED",
                                    "bounded_interval": True,
                                    "conservation_lane": 0.0,
                                    "dissipation_lane": "LOW/NOMINAL/HIGH only"},
        },
        "mass_booking": {
            "kinetic_leaf_mass_per_wing_kg": 0.54,
            "rigid_nontracking_ledger_per_wing_kg": 0.24,
            "total_per_wing_kg": 0.78,
            "rule": "rigid ledger excluded from flexible kinetic energy and added once in structural mass accounting"},
        "uncertainty_method": {
            "type": "bounded deterministic corners; not a probabilistic standard uncertainty",
            "correlation_assumption": "LOW and HIGH are conservative all-parameter corners; no independence claim",
            "corners": CORNERS,
        },
        "quantitative_linearity_contract": linearity_contract,
        "scope_guards": {
            "r2_coupled_diagnostics": "NOT_EVALUATED",
            "e15_inheritance": "NOT_INHERITED",
            "measurement_claim": False,
            "flight_qualification": "HOLD",
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "upstream_hashes": upstream_hashes,
    }
    OUT_MODEL.write_text(yaml.safe_dump(clean(model_card), sort_keys=False,
                                        allow_unicode=True), encoding="utf-8")

    evidence = {
        "schema": "R2_HF_NUMERICAL_EVIDENCE_V2",
        "generated_local": generated,
        "class": "COMPONENT_HF_ROM_EVIDENCE_WITH_PROVISIONAL_PHYSICS",
        "geometry_authority": geometry_authority,
        "upstream_hashes": upstream_hashes,
        "owner_attachment_verification": {
            "expected_sha256": OWNER_ATTACHMENT_SHA,
            "recomputed_sha256": owner_attachment_actual,
            "match": owner_attachment_actual == OWNER_ATTACHMENT_SHA,
        },
        "model_dimensions": {"full": model.ndof_full, "reduced": model.ndof,
                             "elements_per_leaf": model.n, "leaves": 3},
        "mass_closure": mass_closure,
        "l2_reference": l2_check,
        "rigid_projection": rigid_projection,
        "nullspace": nullspace,
        "positive_definiteness": spd,
        "mesh_convergence": mesh,
        "dof_and_reconstruction_contract": reconstruction_audit,
        "parameter_corners": corner_results,
        "base_participation": part,
        "scope_guards": {
            "r2_coupled_diagnostics": "NOT_EVALUATED",
            "e15_inheritance": "NOT_INHERITED",
            "legacy_e15_gate_unchanged": True,
            "component_gate_is_not_coupled_gate": True,
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    dump_json(OUT_EVID, evidence)

    rom = {
        "schema": "R2_FIVE_MODE_ROM_V2",
        "generated_local": generated,
        "configuration": "per wing deployed-flat latched; nominal fixed basis",
        "selection_rule": "three lowest BENDING modes plus two lowest TORSION modes",
        "mode_labels": labels,
        "hf_mode_indices_1based": [i+1 for i in selection],
        "nominal_selected_frequencies_hz": [float(fnom[i]) for i in selection],
        "Phi_mass_normalized": Phi,
        "reduced_hf_dof_semantics": dof_semantics,
        "reconstruction_operators_rom": {
            "w_nodes": reconstruction_rom["w_nodes"],
            "theta_dofs": reconstruction_rom["theta_dofs"],
            "torsion_nodes": reconstruction_rom["torsion_nodes"],
            "hinge_relative": reconstruction_rom["hinge_relative"],
            "tip_w": reconstruction_rom["tip_w"],
            "coordinate_order": "rows follow the published reduced_hf_dof_semantics/node contracts; columns follow mode_labels",
        },
        "Mrom": Mrom,
        "Krom_by_corner": Kroms,
        "Crom_by_corner": Croms,
        "rom_eigenfrequencies_by_corner_hz": rom_corner_freq,
        "HF_base_participation_matrices": {
            "LEFT": {"B_t": Bt_L, "B_r": Br_L},
            "RIGHT": {"B_t": Bt_R, "B_r": Br_R},
        },
        "base_participation": {
            "LEFT": {**gammas["LEFT"], "effective_mass_and_inertia_coverage": part["LEFT"]},
            "RIGHT": {**gammas["RIGHT"], "effective_mass_and_inertia_coverage": part["RIGHT"]},
        },
        "reconstruction_contract": {
            "state": "q_flex ~= Phi * eta; qdot_flex ~= Phi * etadot",
            "equation": "Mrom*eta_ddot + Crom*eta_dot + Krom*eta = Phi^T*f_flex - Gamma_t*vbase_dot - Gamma_r*omega_base_dot",
            "force_projection": "f_rom = Phi^T f_hf",
            "base_coupling": "Gamma_t=Phi^T B_t; Gamma_r=Phi^T B_r",
            "units": {"bending_components_of_q": "m and rad",
                      "torsion_components_of_q": "rad", "eta": "mixed modal coordinate",
                      "Mrom": "mass-normalized identity", "Krom": "rad2/s2",
                      "Crom": "1/s"},
            "validity": "linear component reconstruction inside declared LOW/NOMINAL/HIGH envelope; no coupled-response claim",
        },
        "parameter_authority": "all EI/GJ/k_theta/zeta inputs PROVISIONAL_DERIVED bounded intervals",
        "independent_latch_stiffness": None,
        "latch_null_disposition": "latch-inclusive k_inter band propagated; no independent latch number invented",
        "quantitative_linearity_contract": linearity_contract,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    dump_json(OUT_ROM, rom)

    ranges = {}
    for i, label in enumerate(("BENDING_1", "BENDING_2", "BENDING_3")):
        vals = {c: corner_results[c]["bending_first3_hz"][i] for c in CORNERS}
        ranges[label] = {"by_corner_hz": vals, "min_hz": min(vals.values()),
                         "max_hz": max(vals.values())}
    for i, label in enumerate(("TORSION_1", "TORSION_2")):
        vals = {c: corner_results[c]["torsion_first2_hz"][i] for c in CORNERS}
        ranges[label] = {"by_corner_hz": vals, "min_hz": min(vals.values()),
                         "max_hz": max(vals.values())}
    envelope = {
        "schema": "R2_FLEXIBILITY_VALIDITY_ENVELOPE_V2",
        "generated_local": generated,
        "parameter_corners": CORNERS,
        "retained_mode_frequency_envelope": ranges,
        "geometry": {"root_y_abs_m": ROOT_Y, "root_z_m": ROOT_Z,
                     "leaves_per_wing": 3},
        "quantitative_linearity_contract": linearity_contract,
        "response_reconstruction": {
            "source": rel(OUT_ROM),
            "operators": list(reconstruction_rom),
            "out_of_domain_policy": "FAIL_CLOSED__NO_LINEAR_ROM_EXTRAPOLATION",
        },
        "valid_for": [
            "deployed-flat latched Solar R2 configuration",
            "small linear deformation around the deployed equilibrium within the quantitative_linearity_contract",
            "per-wing component HF/ROM use with explicit LEFT/RIGHT B matrices",
            "deterministic LOW/NOMINAL/HIGH bounded sensitivity studies",
        ],
        "invalid_or_not_evaluated_for": [
            "stowed, deployment transient, freeplay, backlash or contact",
            "independent latch hardware stiffness outside the folded k_inter interval",
            "nonlinear large-deflection response",
            "any response exceeding a quantitative_linearity_contract limit",
            "R2 coupled spacecraft-arm-target diagnostics",
            "e15 certification inheritance or flight qualification",
        ],
        "r2_coupled_diagnostics": "NOT_EVALUATED",
        "e15_inheritance": "NOT_INHERITED",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    dump_json(OUT_ENV, envelope)

    np.savez_compressed(
        OUT_NPZ,
        M_full=Mf, M=M, K_nominal=K_nom, K_unlatched=K_unlatched,
        coordinate_scale=S, Q_rigid=Q, Mqq_l2=Mqq,
        Phi_rom=Phi, Mrom=Mrom,
        Krom_LOW=Kroms["LOW"], Krom_NOMINAL=Kroms["NOMINAL"], Krom_HIGH=Kroms["HIGH"],
        Crom_LOW=Croms["LOW"], Crom_NOMINAL=Croms["NOMINAL"], Crom_HIGH=Croms["HIGH"],
        K_corner_LOW=corner_arrays["LOW"][1],
        K_corner_NOMINAL=corner_arrays["NOMINAL"][1],
        K_corner_HIGH=corner_arrays["HIGH"][1],
        Bt_L=Bt_L, Br_L=Br_L, Bt_R=Bt_R, Br_R=Br_R,
        Gamma_t_L=gammas["LEFT"]["Gamma_t"], Gamma_r_L=gammas["LEFT"]["Gamma_r"],
        Gamma_t_R=gammas["RIGHT"]["Gamma_t"], Gamma_r_R=gammas["RIGHT"]["Gamma_r"],
        R_w_nodes=reconstruction_rom["w_nodes"],
        R_theta_dofs=reconstruction_rom["theta_dofs"],
        R_torsion_nodes=reconstruction_rom["torsion_nodes"],
        R_hinge_relative=reconstruction_rom["hinge_relative"],
        R_tip_w=reconstruction_rom["tip_w"],
        linearity_limits=np.asarray([
            LINEAR_ANGLE_LIMIT_RAD,
            LINEAR_ANGLE_LIMIT_RAD,
            LINEAR_ANGLE_LIMIT_RAD,
            LINEAR_NODE_DEFLECTION_LIMIT_M,
            LINEAR_NODE_DEFLECTION_LIMIT_M,
        ]),
        rigid_translation_full=u_trans, free_full_indices=model.free_full,
    )

    proc = subprocess.run([sys.executable, str(INDEPENDENT_SCRIPT)], cwd=str(ROOT),
                          capture_output=True, text=True, check=False)
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr:
        print(proc.stderr.strip(), file=sys.stderr)
    independent = (json.loads(INDEPENDENT_REPORT.read_text(encoding="utf-8"))
                   if INDEPENDENT_REPORT.exists() else
                   {"verdict": "MISSING", "summary": {"passed": 0, "total": 0}})

    # Every FAIL/HOLD/null in the delivered evidence has an explicit disposition.
    dispositions = [
        {"id": "D01", "item": "historical root y=0.1149 m registrations",
         "state": "CLOSED_DEFECT", "disposition": geometry_authority["historical_conflict"]["disposition"]},
        {"id": "D02", "item": "independent latch stiffness", "state": "NULL_DECLARED",
         "disposition": "NO_ZERO_FILL; latch-inclusive k_inter LOW/NOMINAL/HIGH interval propagated"},
        {"id": "D03", "item": "EI/GJ/k_theta/zeta physical authority", "state": "HOLD_PROVISIONAL",
         "disposition": "bounded deterministic envelope; replacement triggered by hardware selection/test"},
        {"id": "D04", "item": "R2 coupled diagnostics", "state": "NOT_EVALUATED",
         "disposition": "outside this component Gate; cannot inherit component PASS"},
        {"id": "D05", "item": "e15 certification", "state": "NOT_INHERITED",
         "disposition": "legacy e15 result remains unchanged; new coupled model must rerun separately"},
        {"id": "D06", "item": "flight qualification/as-built correlation", "state": "HOLD",
         "disposition": "qualification layer; no measurement or flight claim"},
        {"id": "D07", "item": "structural-zero B/Gamma channels and coverage fractions",
         "state": "EXPECTED_NULL", "disposition": "explicit symmetry zeros, not missing calculations"},
        {"id": "D08", "item": "prior round constrained-field mass check", "state": "VALIDATOR_DEFECT",
         "disposition": ("not a physical missing-mass defect: fixed-root all-ones field was not an "
                         "admissible rigid translation; older round immutable; unconstrained full-"
                         "element rigid-body field independently recomputes 0.54 kg")},
        {"id": "D09", "item": "prior round L2 q/dq reference", "state": "REFERENCE_IMPLEMENTATION_DEFECT",
         "disposition": ("dq was inserted into configuration angles; isolated V2 evaluates q=0 and "
                         "uses dq only as velocity, then reproduces e21 Mqq and five cases")},
        {"id": "D10", "item": "downstream response reconstruction and linearity domain",
         "state": "CLOSED_BY_MACHINE_READABLE_CONTRACT",
         "disposition": ("183 reduced-DOF semantics plus node/slope/hinge/torsion/tip modal "
                         "operators and a provisional 0.05-rad small-angle domain are published; "
                         "out-of-domain response fails closed")},
    ]

    root_ok = (root_build_mm == 115.4 and root_z_build_mm == -108.15 and
               root_arithmetic["arithmetic_y_abs_mm"] == 115.4 and
               ROOT_Y == 0.1154 and ROOT_Z == -0.10815)
    param_ok = (all(x > 0 for x in EI.values()) and all(x > 0 for x in GJ.values()) and
                all(x > 0 for x in K_ROOT.values()) and all(x > 0 for x in K_INTER.values()) and
                all(x > 0 for x in ZETA.values()) and
                EI["low"] < EI["nominal"] < EI["high"] and
                GJ["low"] < GJ["nominal"] < GJ["high"])
    rom_ok = (len(selection) == 5 and len(bend_indices) == 3 and len(torsion_indices) == 2 and
              maxabs(Mrom-np.eye(5)) < 1e-10 and
              all(np.min(np.linalg.eigvalsh(x)) > 0 for x in Kroms.values()) and
              all(np.min(np.linalg.eigvalsh(x)) > 0 for x in Croms.values()))
    participation_ok = (maxabs(Bt_L-Bt_R) < 1e-14 and maxabs(Br_L+Br_R) < 1e-14 and
                        np.linalg.norm(Bt_L[:, 2]) > 0 and
                        np.linalg.norm(Br_L[:, 0]) > 0 and np.linalg.norm(Br_L[:, 1]) > 0)
    reconstruction_ok = (
        len(dof_semantics) == model.ndof
        and len({x["reduced_index_0based"] for x in dof_semantics}) == model.ndof
        and len({x["full_index_0based"] for x in dof_semantics}) == model.ndof
        and reconstruction_hf["w_nodes"].shape == (model.ne + 1, model.ndof)
        and reconstruction_hf["torsion_nodes"].shape == (model.ne + 1, model.ndof)
        and reconstruction_hf["hinge_relative"].shape == (3, model.ndof)
        and reconstruction_hf["tip_w"].shape == (1, model.ndof)
        and reconstruction_audit["root_w_row_max_abs"] == 0.0
        and reconstruction_audit["root_torsion_row_max_abs"] == 0.0
        and reconstruction_audit["tip_row_identity_residual"] == 0.0
        and reconstruction_audit["modal_projection_max_abs_residual"] == 0.0
        and LINEAR_ANGLE_LIMIT_RAD > 0.0
        and LINEAR_NODE_DEFLECTION_LIMIT_M > 0.0
        and LINEAR_GEOMETRY_ERROR_FRACTION < 0.0013)
    checks = [
        {"id": "G01", "name": "latest Owner directive source", "pass": owner_attachment_actual == OWNER_ATTACHMENT_SHA},
        {"id": "G02", "name": "root authority and historical conflict", "pass": root_ok},
        {"id": "G03", "name": "L2 q=0 Mqq and e21 five cases", "pass": l2_check["Mqq_max_abs_diff_vs_e21_kg_m2"] < 1e-12 and max_df < 1e-9},
        {"id": "G04", "name": "unconstrained mass closure 0.54+0.24=0.78", "pass": mass_closure["leaf_abs_error_kg"] < 1e-12 and mass_closure["total_abs_error_kg"] < 1e-12},
        {"id": "G05", "name": "M/K positive definite at nominal latched", "pass": spd["M_spd"] and spd["K_nominal_spd"]},
        {"id": "G06", "name": "scaled SVD and three explicit mechanisms", "pass": nullity == 3 and min(principal) > 1-1e-8 and max(mech_residuals) < 1e-11},
        {"id": "G07", "name": "piecewise-rigid Q projection", "pass": rigid_projection["max_abs_diff_QTMQ_vs_e21_kg_m2"] < 1e-12 and max_proj_k < 1e-7 and max_proj_f < 1e-8},
        {"id": "G08", "name": "three-leaf/three-joint/torsion architecture", "pass": model.n > 1 and len(model.hinge_nodes) == 2 and len(model.torsion_reduced) > 0},
        {"id": "G09", "name": "bounded provisional parameters and latch null propagation", "pass": param_ok},
        {"id": "G10", "name": "HF base participation B_t/B_r", "pass": participation_ok},
        {"id": "G11", "name": "five-mode mass-normalized ROM and bands", "pass": rom_ok},
        {"id": "G12", "name": "N20/N40 retained-lane mesh convergence", "pass": mesh_max < 5e-4},
        {"id": "G13", "name": "LOW/NOMINAL/HIGH validity envelope", "pass": set(corner_results) == {"LOW", "NOMINAL", "HIGH"} and len(ranges) == 5},
        {"id": "G14", "name": "independent recomputation", "pass": independent.get("verdict") == "PASS"},
        {"id": "G15", "name": "fail-closed scope", "pass": envelope["r2_coupled_diagnostics"] == "NOT_EVALUATED" and envelope["e15_inheritance"] == "NOT_INHERITED"},
        {"id": "G16", "name": "all evidence FAIL/HOLD/null disposed", "pass": len(dispositions) == 10 and all(d["disposition"] for d in dispositions)},
        {"id": "G17", "name": "DOF semantics, response reconstruction and quantitative linearity domain", "pass": reconstruction_ok},
    ]
    all_pass = all(c["pass"] for c in checks)
    evidence_files = [OUT_MODEL, OUT_EVID, OUT_ROM, OUT_ENV, OUT_NPZ,
                      OWNER_RECORD, INDEPENDENT_SCRIPT, INDEPENDENT_REPORT,
                      HERE / "tests/test_package.py", Path(__file__).resolve(),
                      HERE / "README.md"]
    gate = {
        "schema": "R2_FULL_FLEX_HF_ROM_GATE_V2",
        "generated_local": datetime.now(TZ).isoformat(),
        "technical_verdict": ("PASS_WITH_DECLARED_PROVISIONAL_PHYSICS"
                              if all_pass else "FAIL"),
        "scope": "R2 component HF plus per-wing five-mode ROM only",
        "criteria": checks,
        "summary": {"passed": sum(int(c["pass"]) for c in checks),
                    "total": len(checks)},
        "key_metrics": {
            "root_y_abs_m": ROOT_Y, "root_z_m": ROOT_Z,
            "leaf_mass_closure_kg": kinetic_mass,
            "wing_mass_with_rigid_ledger_kg": kinetic_mass+ledger_mass,
            "Mqq_max_abs_diff_vs_e21_kg_m2": l2_check["Mqq_max_abs_diff_vs_e21_kg_m2"],
            "five_case_max_abs_diff_vs_e21_hz": max_df,
            "QTMQ_max_abs_diff_vs_e21_kg_m2": rigid_projection["max_abs_diff_QTMQ_vs_e21_kg_m2"],
            "scaled_svd_nullity": nullity,
            "mesh_N20_N40_max_relative_shift": mesh_max,
            "rom_selected_frequencies_nominal_hz": [float(fnom[i]) for i in selection],
            "reduced_hf_dof_semantics_count": len(dof_semantics),
            "linearity_angle_limit_rad": LINEAR_ANGLE_LIMIT_RAD,
            "linearity_node_deflection_limit_m": LINEAR_NODE_DEFLECTION_LIMIT_M,
            "linearity_geometry_error_fraction": LINEAR_GEOMETRY_ERROR_FRACTION,
            "independent_recompute": independent.get("summary"),
        },
        "evidence_disposition_register": dispositions,
        "scope_guards": {
            "r2_coupled_diagnostics": "NOT_EVALUATED",
            "e15_inheritance": "NOT_INHERITED",
            "flight_qualification": "HOLD",
            "owner_accepted": False,
        },
        "evidence_hashes": {rel(p): sha256(p) for p in evidence_files},
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    dump_json(OUT_GATE, gate)
    print(f"R2 HF/ROM V2 {gate['technical_verdict']} "
          f"{gate['summary']['passed']}/{gate['summary']['total']}")
    print("nominal selected Hz:", [round(float(fnom[i]), 6) for i in selection])
    print("mass kg:", kinetic_mass, "+", ledger_mass, "=", kinetic_mass+ledger_mass)
    print("Gate SHA256:", sha256(OUT_GATE))
    if not all_pass:
        for c in checks:
            if not c["pass"]:
                print("FAILED", c["id"], c["name"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
