# -*- coding: utf-8 -*-
"""SOLAR_ARRAY_R2 mass properties package (R2-WI-05 stage 1).

Pure-python analytical computation from the R2 geometry candidate
(solar_array_r2_kinematics.py) and the ODR-19 candidate mass model
(build_solar_array_r2.py constants, duplicated here with provenance).

Per configuration C01..C09 (M4 configuration library semantics):
  leaf thin-plate own-COM inertia, rotated into S and shifted to the
  S origin; hinge point masses at chain hinge stations (root fixed,
  inter-panel hinges follow the chain); HDRM + harness fixed allowances.

Output: SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json
  - per-wing and both-wings mass / CG / inertia-about-S-origin per config
  - system mass delta vs LEGACY_R1 (budget reallocation decision stays OPEN)
  - consumed later by the WP2 V3 nine-config aggregation (integration step)

NOT used: any area-proportional rescale of 0.3483933 kg (forbidden by
ODR-18/ODR-19).  Legacy value appears only as a delta reference.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import solar_array_r2_kinematics as K

HERE = Path(__file__).resolve().parent
OUT = HERE / "SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json"

# --- candidate mass model (mirrors build_solar_array_r2.py, ODR-19) -------
LEAF_MASS = 0.18           # kg, areal-density candidate 3.0 kg/m2 x 0.06 m2
HINGE_ROOT = 0.05
HINGE_INTER = 0.03
HDRM = 0.08
HARNESS = 0.05
LEGACY_R1_PANEL = 0.3483933  # LEGACY_SIM11_PROVISIONAL, delta reference only
WHOLE_SAT_LEGACY = 24.000

# leaf local axes: e1 = chord (X_S), e2 = span, e3 = thickness
A, B, T = K.LEAF_CHORD / 1000.0, K.LEAF_SPAN / 1000.0, K.LEAF_T / 1000.0
I_LEAF_LOCAL = (
    LEAF_MASS / 12.0 * (B * B + T * T),   # about chord axis
    LEAF_MASS / 12.0 * (A * A + T * T),   # about span axis
    LEAF_MASS / 12.0 * (A * A + B * B),   # about normal
)

MM_TO_M = 1.0e-3

# solar state per configuration (M4 library semantics, ODR-02 attached-stuck;
# candidate convention: failed wing stuck at STOWED pose; partial-deploy
# stuck states are bounded between the stowed and deployed values)
CONFIG_SOLAR_STATE = {
    "C01": ("DEPLOYED_NOMINAL", ("D", "D")),
    "C02": ("LEFT_PANEL_FAIL", ("S", "D")),
    "C03": ("RIGHT_PANEL_FAIL", ("D", "S")),
    "C04": ("BOTH_PANEL_FAIL", ("S", "S")),
    "C05": ("ARM_STOWED_ONORBIT", ("S", "S")),
    "C06": ("ARM_TASK_READY", ("D", "D")),
    "C07": ("PREGRASP", ("D", "D")),
    "C08": ("TARGET_CAPTURE_22KG", ("D", "D")),
    "C09": ("TARGET_CAPTURE_150KG", ("D", "D")),
}


def mat_vec_det_ok(e2, e3):
    # right-handedness witness: e1 x e2 . e3 must be +1
    cx = -e2[2] * 0 + 0  # e1=(1,0,0): (e1 x e2) = (0, -e2[2], e2[1])
    return (0.0 * e3[0]) + (-e2[2]) * e3[1] + e2[1] * e3[2]


def rotate_diag_inertia(I_local, e2, e3):
    """R diag(I) R^T with R columns = [e1, e2, e3], e1 = (1,0,0)."""
    basis = [(1.0, 0.0, 0.0), e2, e3]
    I = [[0.0] * 3 for _ in range(3)]
    for col, Ival in enumerate(I_local):
        v = basis[col]
        for i in range(3):
            for j in range(3):
                I[i][j] += Ival * v[i] * v[j]
    return I


def steiner(I_com, m, r):
    x, y, z = r
    d2 = x * x + y * y + z * z
    return [[I_com[i][j] + m * (d2 * (1.0 if i == j else 0.0)
                                 - r[i] * r[j]) for j in range(3)]
            for i in range(3)]


def add_tensors(a, b):
    return [[a[i][j] + b[i][j] for j in range(3)] for i in range(3)]


def wing_mass_properties(side: int, state: str) -> dict:
    angles = K.DEPLOYED if state == "D" else K.STOWED
    segs = K.leaf_segments(side, *angles)

    total_m = 0.0
    cg = [0.0, 0.0, 0.0]
    I_origin = [[0.0] * 3 for _ in range(3)]

    def accumulate(m, r_m, I_com_S):
        nonlocal total_m, cg, I_origin
        total_m += m
        for i in range(3):
            cg[i] += m * r_m[i]
        I_origin = add_tensors(I_origin, steiner(I_com_S, m, r_m))

    hinge_points = []
    for leaf in segs:
        origin, e2, e3 = K.leaf_solid_frame(side, leaf)
        # COM at local (chord/2, span/2, T/2)
        com_mm = [origin[0] + 150.0 + 0.0 * e2[0],
                  origin[1] + 100.0 * e2[1] + (K.LEAF_T / 2.0) * e3[1],
                  origin[2] + 100.0 * e2[2] + (K.LEAF_T / 2.0) * e3[2]]
        com_m = [v * MM_TO_M for v in com_mm]
        I_S = rotate_diag_inertia(I_LEAF_LOCAL, e2, e3)
        accumulate(LEAF_MASS, com_m, I_S)
        hinge_points.append(leaf["start"])
    # root hinge at first chain point, inter hinges at leaf 1/2 tips
    p0 = hinge_points[0]
    tips = [leaf["tip"] for leaf in segs]
    stations = [(HINGE_ROOT, p0), (HINGE_INTER, tips[0]),
                (HINGE_INTER, tips[1])]
    for m, (yy, zz) in stations:
        accumulate(m, [0.0, yy * MM_TO_M, zz * MM_TO_M],
                   [[0.0] * 3 for _ in range(3)])
    # HDRM (bus-mounted, fixed) and harness root allowance (fixed)
    accumulate(HDRM, [0.0, side * 119.15 * MM_TO_M, 0.0],
               [[0.0] * 3 for _ in range(3)])
    accumulate(HARNESS, [0.0, side * K.LEAF1_MID_Y * MM_TO_M,
                         K.HINGE_Z * MM_TO_M], [[0.0] * 3 for _ in range(3)])

    cg = [v / total_m for v in cg]
    return {"mass_kg": round(total_m, 9),
            "cg_S_m": [round(v, 9) for v in cg],
            "inertia_about_S_origin_kgm2": [[round(v, 12) for v in row]
                                            for row in I_origin]}


def main() -> None:
    configs = {}
    for cid, (name, (ls, rs)) in CONFIG_SOLAR_STATE.items():
        left = wing_mass_properties(+1, ls)
        right = wing_mass_properties(-1, rs)
        both_I = add_tensors(
            left["inertia_about_S_origin_kgm2"],
            right["inertia_about_S_origin_kgm2"])
        mtot = left["mass_kg"] + right["mass_kg"]
        cg = [(left["cg_S_m"][i] * left["mass_kg"]
               + right["cg_S_m"][i] * right["mass_kg"]) / mtot
              for i in range(3)]
        configs[cid] = {
            "m4_name": name,
            "solar_states_left_right": [ls, rs],
            "left_wing": left,
            "right_wing": right,
            "both_wings": {
                "mass_kg": round(mtot, 9),
                "cg_S_m": [round(v, 9) for v in cg],
                "inertia_about_S_origin_kgm2": both_I,
            },
        }

    legacy_both = 2 * LEGACY_R1_PANEL
    r2_both = configs["C01"]["both_wings"]["mass_kg"]
    report = {
        "schema": "SOLAR_ARRAY_R2_MASS_PROPERTIES_V1",
        "generated_local": datetime.now(
            timezone(timedelta(hours=8))).isoformat(),
        "authority": "ODR-19 / R2-WI-05 stage 1 (solar subsystem package)",
        "class": "ENGINEERING_CANDIDATE",
        "mass_model": {
            "leaf_kg": LEAF_MASS, "hinge_root_kg": HINGE_ROOT,
            "hinge_inter_kg_each": HINGE_INTER, "hdrm_per_wing_kg": HDRM,
            "harness_per_wing_kg": HARNESS,
            "basis": "areal-density candidate 3.0 kg/m2; NOT measured; "
                     "no legacy rescale used",
        },
        "fail_state_convention": "ODR-02 attached-stuck; candidate models "
            "failed wing at STOWED pose (partial-deploy stuck states are "
            "bounded by stowed/deployed values)",
        "configurations": configs,
        "system_delta": {
            "legacy_r1_both_wings_kg": legacy_both,
            "r2_both_wings_kg": r2_both,
            "delta_kg": round(r2_both - legacy_both, 9),
            "whole_sat_legacy_kg": WHOLE_SAT_LEGACY,
            "whole_sat_with_r2_kg": round(
                WHOLE_SAT_LEGACY - legacy_both + r2_both, 9),
            "status": "OPEN - 24 kg budget reallocation decision required; "
                      "not closed by this package",
        },
        "next_integration": "WP2 V3 nine-config aggregation consumes this "
                            "package (replaces solar_array_left/right rows)",
    }
    OUT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("R2_MASS_OK wing_kg=%.6f both_kg=%.6f delta_kg=%+.6f whole=%.6f" % (
        configs["C01"]["left_wing"]["mass_kg"], r2_both,
        r2_both - legacy_both,
        WHOLE_SAT_LEGACY - legacy_both + r2_both))
    for cid in sorted(configs):
        b = configs[cid]["both_wings"]
        print("%s %-22s m=%.6f cg=[%.4f, %.4f, %.4f]" % (
            cid, configs[cid]["m4_name"], b["mass_kg"],
            b["cg_S_m"][0], b["cg_S_m"][1], b["cg_S_m"][2]))

if __name__ == "__main__":
    main()
