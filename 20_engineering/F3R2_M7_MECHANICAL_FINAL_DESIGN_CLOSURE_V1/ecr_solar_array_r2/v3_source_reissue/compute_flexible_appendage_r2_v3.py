# -*- coding: utf-8 -*-
"""FLEXIBLE_APPENDAGE_R2 - L1 engineering model + L2 reduced model (R2-WI-06).

L1: per-leaf sandwich EI estimate, hinge stiffness bands, latch compliance.
L2: 3-DOF-per-wing hinge-rotation reduced model linearised about the
    deployed flat configuration; eigenfrequencies computed numerically
    (pure python, no scipy) for nominal and band-corner stiffnesses.

Everything without a measurement source is PROVISIONAL_DERIVED with an
uncertainty interval (ODR-21).  The legacy flexible_appendage_v1.yaml is
NOT modified and NOT read as authority.

Outputs:
  FLEXIBLE_APPENDAGE_R2.yaml       - the parameter card
  FLEXIBLE_APPENDAGE_R2_MODES.json - numerical eigen evidence
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import solar_array_r2_kinematics_v3 as K
from source_execution_guard import require_execution_authority

HERE = Path(__file__).resolve().parent
OUT_YAML = HERE / "FLEXIBLE_APPENDAGE_R2_V3.yaml"
OUT_JSON = HERE / "FLEXIBLE_APPENDAGE_R2_MODES_V3.json"

# --- leaf candidate construction (ENGINEERING_CANDIDATE) -------------------
LEAF_M = 0.18            # kg (areal-density candidate 3.0 kg/m2)
LEAF_A = 0.300           # chord, m (along hinge axis X_S)
LEAF_L = 0.200           # span, m (cantilever direction)
LEAF_T = 0.0025          # total assembly thickness, m
E_FACES = 70.0e9         # Pa, quasi-isotropic CFRP faces candidate
T_FACE = 0.2e-3          # m per face (2 faces)
T_CORE = 2.1e-3          # m core
ZETA = 0.01              # modal damping, TBD_cite_literature (legacy conv.)

# sandwich bending stiffness per unit width ~ E * tf * (h)^2 / 2, h = core+tf
H = T_CORE + T_FACE
EI_PER_WIDTH = E_FACES * T_FACE * H * H / 2.0
EI_LEAF = EI_PER_WIDTH * LEAF_A
EI_BAND = (0.3 * EI_LEAF, 3.0 * EI_LEAF)   # PROVISIONAL_DERIVED band

MU = LEAF_M / LEAF_L
BETA1 = 1.87510407
F1_LEAF = (BETA1 ** 2 / (2.0 * math.pi * LEAF_L ** 2)) * math.sqrt(
    EI_LEAF / MU)
F1_LEAF_BAND = ((BETA1 ** 2 / (2.0 * math.pi * LEAF_L ** 2)) * math.sqrt(EI_BAND[0] / MU),
                (BETA1 ** 2 / (2.0 * math.pi * LEAF_L ** 2)) * math.sqrt(EI_BAND[1] / MU))

# hinge latched stiffness bands, N m / rad (PROVISIONAL_DERIVED)
K_ROOT = {"low": 50.0, "nominal": 200.0, "high": 800.0}
K_INTER = {"low": 20.0, "nominal": 100.0, "high": 400.0}

P0 = (K.LEAF1_MID_Y / 1000.0, K.HINGE_Z / 1000.0)  # derived from V3 root registration
I_LEAF_COM_X = LEAF_M / 12.0 * (LEAF_L ** 2 + LEAF_T ** 2)  # spin about chord


def kinetic_energy(dq, q=(0.0, 0.0, 0.0)):
    """T for the deployed (q=0) 3-leaf chain; angles relative hinge
    rotations q1,q2,q3; absolute leaf angles psi = 90 deg + cumulative q;
    2D kinematics in the (y,z) plane (rotations about X_S)."""
    psi = [math.pi / 2 + q[0],
           math.pi / 2 + q[0] + q[1],
           math.pi / 2 + q[0] + q[1] + q[2]]
    dpsi = [dq[0], dq[0] + dq[1], dq[0] + dq[1] + dq[2]]
    u = [(math.sin(p), math.cos(p)) for p in psi]
    up = [(math.cos(p), -math.sin(p)) for p in psi]  # du/dpsi

    T = 0.0
    P = P0
    vP = (0.0, 0.0)
    for i in range(3):
        vcom = (vP[0] + 0.5 * LEAF_L * dpsi[i] * up[i][0],
                vP[1] + 0.5 * LEAF_L * dpsi[i] * up[i][1])
        T += 0.5 * LEAF_M * (vcom[0] ** 2 + vcom[1] ** 2)
        T += 0.5 * I_LEAF_COM_X * dpsi[i] ** 2
        P = (P[0] + LEAF_L * u[i][0], P[1] + LEAF_L * u[i][1])
        vP = (vP[0] + LEAF_L * dpsi[i] * up[i][0],
              vP[1] + LEAF_L * dpsi[i] * up[i][1])
    return T


def mass_matrix():
    e = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    M = [[0.0] * 3 for _ in range(3)]
    Te = [kinetic_energy(v) for v in e]
    for i in range(3):
        M[i][i] = 2.0 * Te[i]
    for i in range(3):
        for j in range(i + 1, 3):
            s = tuple(a + b for a, b in zip(e[i], e[j]))
            M[i][j] = M[j][i] = kinetic_energy(s) - Te[i] - Te[j]
    return M


def solve3_gen_eig(M, K):
    """Eigenvalues of K q = w^2 M q via Jacobi on M^-1 K (3x3, symmetric)."""
    # Cholesky-free: form A = M^{-1} K by Gaussian elimination, then
    # use characteristic polynomial via Faddeev-LeVerrier.
    def matmul(A, B):
        return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)]
                for i in range(3)]

    def inv(A):
        n = 3
        aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)]
               for i, row in enumerate(A)]
        for col in range(n):
            piv = max(range(col, n), key=lambda r: abs(aug[r][col]))
            aug[col], aug[piv] = aug[piv], aug[col]
            d = aug[col][col]
            aug[col] = [v / d for v in aug[col]]
            for r in range(n):
                if r != col:
                    f = aug[r][col]
                    aug[r] = [a - f * b for a, b in zip(aug[r], aug[col])]
        return [row[n:] for row in aug]

    A = matmul(inv(M), K)
    # Faddeev-LeVerrier for char poly of 3x3
    A2 = matmul(A, A)
    A3 = matmul(A2, A)
    tr = lambda B: B[0][0] + B[1][1] + B[2][2]
    c1 = tr(A)
    c2 = 0.5 * (c1 * tr(A) - tr(A2))
    c3 = (tr(A) ** 3 - 3 * tr(A) * tr(A2) + 2 * tr(A3)) / 6.0
    # eigenvalues = roots of w^6 - c1 w^4 + c2 w^2 - c3 = 0 -> cubic in w^2
    # solve cubic x^3 - c1 x^2 + c2 x - c3 = 0 numerically (all roots > 0)
    roots = []
    xs = [1e-6]
    # bracket and bisect on a log grid
    import itertools  # noqa: F401
    grid = [10 ** (-2 + 0.02 * i) for i in range(500)]

    def f(x):
        return x ** 3 - c1 * x ** 2 + c2 * x - c3

    prev_x, prev_f = grid[0], f(grid[0])
    for x in grid[1:]:
        fx = f(x)
        if prev_f * fx < 0:
            lo, hi = prev_x, x
            for _ in range(200):
                mid = 0.5 * (lo + hi)
                if f(lo) * f(mid) <= 0:
                    hi = mid
                else:
                    lo = mid
            roots.append(0.5 * (lo + hi))
        prev_x, prev_f = x, fx
    return sorted(math.sqrt(r) for r in roots)  # rad/s


def wing_modes(k_root, k_inter):
    M = mass_matrix()
    K = [[k_root, 0.0, 0.0], [0.0, k_inter, 0.0], [0.0, 0.0, k_inter]]
    omegas = solve3_gen_eig(M, K)
    return [w / (2 * math.pi) for w in omegas]


def main():
    M = mass_matrix()
    cases = {
        "nominal": (K_ROOT["nominal"], K_INTER["nominal"]),
        "all_low": (K_ROOT["low"], K_INTER["low"]),
        "all_high": (K_ROOT["high"], K_INTER["high"]),
        "root_low_inter_high": (K_ROOT["low"], K_INTER["high"]),
        "root_high_inter_low": (K_ROOT["high"], K_INTER["low"]),
    }
    modes = {name: [round(f, 4) for f in wing_modes(kr, ki)]
             for name, (kr, ki) in cases.items()}

    evidence = {
        "schema": "FLEXIBLE_APPENDAGE_R2_MODES_V3",
        "generated_local": datetime.now(
            timezone(timedelta(hours=8))).isoformat(),
        "authority": "ODR-21 (R2-WI-06)",
        "model": "3-DOF-per-wing hinge-rotation chain, deployed flat config, "
                 "relative-angle springs, pure-python generalized eigen",
        "mass_matrix_kgm2": [[round(v, 9) for v in row] for row in M],
        "stiffness_bands_Nm_per_rad": {"root": K_ROOT, "inter": K_INTER},
        "modes_hz_per_case": modes,
        "leaf_standalone": {
            "EI_Nm2_nominal": round(EI_LEAF, 4),
            "EI_band_Nm2": [round(EI_BAND[0], 4), round(EI_BAND[1], 4)],
            "cantilever_f1_hz_nominal": round(F1_LEAF, 3),
            "cantilever_f1_hz_band": [round(F1_LEAF_BAND[0], 3),
                                      round(F1_LEAF_BAND[1], 3)],
            "note": "standalone leaf cantilever about its root edge; the "
                    "deployed WING modes are hinge-dominated and far lower",
        },
    }
    OUT_JSON.write_text(json.dumps(evidence, indent=1), encoding="utf-8")

    nom = modes["nominal"]
    lo = modes["all_low"]
    hi = modes["all_high"]
    OUT_YAML.write_text("""schema: FLEXIBLE_APPENDAGE_R2_V3
generated_local: '%s'
class: PROVISIONAL_DERIVED with uncertainty intervals (ODR-21)
authority: ODR-21 / R2-WI-06
supersedes: nothing - legacy flexible_appendage_v1.yaml stays untouched
  for historical sim_11 reproduction only

architecture: 3 flexible leaves per wing + root hinge compliance + 2
  inter-panel hinge compliances + latch stiffness (book/accordion chain,
  all hinge axes parallel X_S)

leaf_L1_engineering_model:
  construction_candidate: 2 x 0.2 mm CFRP faces (E = 70 GPa quasi-iso)
    over 2.1 mm core, total 2.5 mm; areal density candidate 3.0 kg/m2
  per_leaf:
    mass_kg: 0.18
    span_m: 0.200
    chord_m: 0.300
    thickness_m: 0.0025
    EI_Nm2: {nominal: %.3f, band: [%.3f, %.3f]}
    GJ_Nm2: {status: PROVISIONAL_DERIVED, note: torsion estimate pending
      sandwich shear model; band not yet assigned}
    cantilever_f1_hz: {nominal: %.2f, band: [%.2f, %.2f]}
      # standalone leaf about root edge; informational only
  root_hinge_ktheta_Nm_per_rad: {low: 50, nominal: 200, high: 800}
  inter_panel_ktheta_Nm_per_rad: {low: 20, nominal: 100, high: 400}
  latch_compliance: {status: PROVISIONAL_DERIVED, folded_into: inter-panel
    ktheta bands until latch hardware selected}
  ktheta_deployed_latched:
    note: ODR-32 explicit deployed-state rotational stiffness - the wing
      modal evidence below is computed AT the deployed latched state, so
      the root/inter ktheta bands ARE the deployed latch stiffness
      candidates
    root_Nm_per_rad: {low: 50, nominal: 200, high: 800}
    inter_panel_Nm_per_rad: {low: 20, nominal: 100, high: 400}
    drives: first wing mode (nominal 6.97 Hz, band 3.33-13.95 Hz) -
      capture-excitation and RL state models must use these bands
  damping: {type: modal, zeta: 0.01, status: TBD_cite_literature}

wing_L2_reduced_model:
  dof_per_wing: 3 (relative hinge rotations about deployed flat config)
  mass_matrix_kgm2: %s
  deployed_modes_hz:
    nominal: %s
    band_corners: {all_low: %s, all_high: %s}
  dominant_modes_for_sim: first 3 per wing (matches ODR-21 3-5 band)
  evidence: FLEXIBLE_APPENDAGE_R2_MODES.json

provenance:
  stiffness_damping_status: PROVISIONAL_DERIVED - no measurement source;
    all bands must be replaced by WP5 R2 hardware selection and/or test
  sim_usage: sim_11 legacy model must NOT quote this card; new R2-coupled
    runs must quote FLEXIBLE_APPENDAGE_R2 with its bands
""" % (evidence["generated_local"],
       EI_LEAF, EI_BAND[0], EI_BAND[1],
       F1_LEAF, F1_LEAF_BAND[0], F1_LEAF_BAND[1],
       evidence["mass_matrix_kgm2"], nom, lo, hi),
       encoding="utf-8")

    print("R2_FLEX_OK f_leaf1=%.2f Hz  wing nominal modes=%s Hz" % (
        F1_LEAF, nom))
    print("wing band corners low=%s high=%s" % (lo, hi))

if __name__ == "__main__":
    main()


