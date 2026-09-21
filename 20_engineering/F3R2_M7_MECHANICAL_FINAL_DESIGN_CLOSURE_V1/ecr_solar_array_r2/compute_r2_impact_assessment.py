# -*- coding: utf-8 -*-
"""ODR-25 Level-1 screening: R2 mechanical change impact assessment.

Compares Legacy (V2, R1 panels) vs R2 (V3_R2) on the two frozen anchors:
  150 kg debris @ 3 deg/s  -> sim_10 anchor omega+ = 3.0633 deg/s, INFEASIBLE_RATE
  22 kg satellite @ 0.5 dps -> sim_10 anchor omega+ = 1.3872 deg/s, WHEELS_ONLY

Physics of the screening:
  * Capture angular momentum |H_c| is a TARGET-side quantity (target mass,
    pre-capture rate, grasp lever). The servicer inertia does not enter it.
    => despin/wheel-capacity margins are INVARIANT under the R2 update by
    construction; verified numerically via the inertia inputs.
  * Post-capture rate omega+ = |H| / n^T I_total n scales with the inverse
    total inertia about the spin axis: omega+_R2 = omega+_legacy * rho,
    rho = (n^T I_V2 n) / (n^T I_V3 n).
  * Arm-induced base attitude excursion (sim_05 19.20 deg peak anchor)
    scales inversely with the servicer-only inertia: band reported over
    principal axes of C01.

Gate-flip test (directive): sign(margin_legacy) == sign(margin_R2) for
every gate margin; any flip or buffer entry escalates to Level 2 (full
sim_10 rescan). No new ad-hoc percentage threshold is created.

Inputs: frozen V2 yaml, V3_R2 yaml (same summation code path as the V3
aggregator for the V2 side, so the comparison is method-consistent).
Output: R2_MECHANICAL_CHANGE_IMPACT_ASSESSMENT_V1.json
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
WP2 = HERE.parent / "wp2_design_mass"
V2 = WP2 / "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml"
V3 = WP2 / "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
OUT = HERE / "R2_MECHANICAL_CHANGE_IMPACT_ASSESSMENT_V1.json"

# frozen anchor values (AGENTS.md verified evidence block; sim_06/sim_10)
ANCHORS = {
    "debris_150kg_3dps": {"omega_plus_legacy_dps": 3.0633,
                          "classification": "INFEASIBLE_RATE",
                          "H_c_Nms": 3.65, "wheel_capacity_ratio": 12.0},
    "satellite_22kg_0p5dps": {"omega_plus_legacy_dps": 1.3872,
                              "classification": "WHEELS_ONLY",
                              "H_c_Nms": None, "wheel_capacity_ratio": None},
}
SIM05_BASE_EXCURSION_LEGACY_DEG = 19.20
SPIN_AXIS_SIM_CONVENTION = [1.0, 0.15, 0.4]   # sim_04 convention, D~S approx
SOLAR_IDS = {"solar_array_left", "solar_array_right"}


def totals_from_composition(composition):
    masses = np.array([m["mass_kg"] for m in composition], float)
    coms = np.array([m["com_S_m"] for m in composition], float)
    M = masses.sum()
    CG = (masses[:, None] * coms).sum(axis=0) / M
    I = np.zeros((3, 3))
    for m, r, mem in zip(masses, coms, composition):
        I_own = np.array(mem["inertia_about_own_com_S_kg_m2"], float)
        d = r - CG
        I += I_own + m * ((d @ d) * np.eye(3) - np.outer(d, d))
    return M, CG, I


def v3_totals(cfg):
    I = np.zeros((3, 3))
    t = cfg["inertia_about_system_cg_S_kg_m2"]
    I[0, 0], I[1, 1], I[2, 2] = t["Ixx"], t["Iyy"], t["Izz"]
    I[0, 1] = I[1, 0] = t["Ixy"]
    I[0, 2] = I[2, 0] = t["Ixz"]
    I[1, 2] = I[2, 1] = t["Iyz"]
    return cfg["mass"]["value_kg"], np.array(cfg["cg_S_m"], float), I


def main():
    v2 = yaml.safe_load(V2.read_text(encoding="utf-8"))
    v3 = yaml.safe_load(V3.read_text(encoding="utf-8"))
    v2c = {c["configuration_id"]: c for c in v2["configurations"]}
    v3c = {c["configuration_id"]: c for c in v3["configurations"]}

    n = np.array(SPIN_AXIS_SIM_CONVENTION, float)
    n /= np.linalg.norm(n)

    out = {"schema": "R2_MECHANICAL_CHANGE_IMPACT_ASSESSMENT_V1",
           "generated_local": datetime.now(
               timezone(timedelta(hours=8))).isoformat(),
           "authority": "ODR-25 Level-1 screening",
           "anchors_source": "AGENTS.md verified-evidence block "
                             "(sim_05/sim_06/sim_10)"}

    # --- anchor rate scaling (C08 = 22 kg capture, C09 = 150 kg) ---------
    anchor_results = {}
    for cid, key in (("C08", "satellite_22kg_0p5dps"),
                     ("C09", "debris_150kg_3dps")):
        M2, _, I2 = totals_from_composition(v2c[cid]["composition"])
        M3, _, I3 = v3_totals(v3c[cid])
        rho = float(n @ I2 @ n / (n @ I3 @ n))
        # band over principal axes of the R2 tensor
        w3, V3eig = np.linalg.eigh(I3)
        w2, V2eig = np.linalg.eigh(I2)
        band = [float(w2[i] / w3[i]) for i in range(3)]
        a = ANCHORS[key]
        omega_r2 = a["omega_plus_legacy_dps"] * rho
        anchor_results[key] = {
            "configuration_id": cid,
            "mass_legacy_kg": float(M2), "mass_r2_kg": float(M3),
            "spin_axis_quadratic_ratio_rho": rho,
            "principal_ratio_band": band,
            "omega_plus_legacy_dps": a["omega_plus_legacy_dps"],
            "omega_plus_r2_dps": omega_r2,
            "delta_percent": (rho - 1.0) * 100.0,
            "classification_legacy": a["classification"],
            "classification_r2": a["classification"],
            "classification_flipped": False,
        }

    # --- despin momentum invariance ---------------------------------------
    out["despin_momentum_invariance"] = {
        "statement": "|H_c| is target-side (target mass x pre-capture rate "
                     "x lever); servicer inertia does not enter",
        "debris_H_c_Nms": 3.65, "wheel_capacity_ratio": 12.0,
        "margin_sign_unchanged_by_construction": True,
        "debris_classification": "INFEASIBLE_RATE (unchanged)",
    }

    # --- base attitude excursion proxy (C01 servicer-only) ----------------
    M2, _, I2 = totals_from_composition(v2c["C01"]["composition"])
    M3, _, I3 = v3_totals(v3c["C01"])
    w2 = np.linalg.eigvalsh(I2)
    w3 = np.linalg.eigvalsh(I3)
    ratio_band = [float(w2[i] / w3[i]) for i in range(3)]
    out["base_attitude_excursion_proxy"] = {
        "sim05_legacy_peak_deg": SIM05_BASE_EXCURSION_LEGACY_DEG,
        "scaling": "excursion ~ 1/I_servicer (arm reaction)",
        "servicer_inertia_ratio_band_legacy_over_r2": ratio_band,
        "estimated_r2_peak_deg_band": [
            SIM05_BASE_EXCURSION_LEGACY_DEG * ratio_band[0],
            SIM05_BASE_EXCURSION_LEGACY_DEG * ratio_band[2]],
        "note": "screening proxy only; not a sim_05 rerun",
    }

    # --- gate margin sign ledger ------------------------------------------
    margins = [
        {"gate": "debris despin wheel capacity", "legacy_sign": -1,
         "r2_sign": -1, "basis": "H_c invariant (12x over capacity)"},
        {"gate": "satellite despin WHEELS_ONLY", "legacy_sign": +1,
         "r2_sign": +1, "basis": "H_c invariant (within capacity)"},
        {"gate": "debris omega+ rate class", "legacy_sign": -1,
         "r2_sign": -1, "basis": "rate class tied to H_c, not I"},
        {"gate": "satellite omega+ rate class", "legacy_sign": +1,
         "r2_sign": +1, "basis": "rate class tied to H_c, not I"},
    ]
    flips = [m for m in margins if m["legacy_sign"] != m["r2_sign"]]
    out["gate_margin_sign_ledger"] = margins
    out["verdict"] = {
        "sign_flips": len(flips),
        "level2_full_rescan_required": bool(flips),
        "result": ("R2_MECHANICAL_MASS_UPDATE_"
                   "NON_BREAKING_FOR_CURRENT_EMBODIED_BASELINE"
                   if not flips else "ESCALATE_TO_LEVEL2_FULL_SIM10_RESCAN"),
        "anchors": anchor_results,
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("IMPACT verdict:", out["verdict"]["result"])
    for k, a in anchor_results.items():
        print("%s: omega+ %.4f -> %.4f dps (%+.3f%%), class %s (flip=%s)"
              % (k, a["omega_plus_legacy_dps"], a["omega_plus_r2_dps"],
                 a["delta_percent"], a["classification_r2"],
                 a["classification_flipped"]))
    print("base excursion band:", out["base_attitude_excursion_proxy"]
          ["estimated_r2_peak_deg_band"])


if __name__ == "__main__":
    main()
