# -*- coding: utf-8 -*-
"""R2-WI-07 thermo-mechanical clearance margin ledger (ODR-26 closure item).

CLEARANCE_MARGIN = nominal - manufacturing_stackup - thermal_drift
                   - hinge_position_error
Only MARGIN > 0 turns a nominal clearance into a functional PASS.

Evaluated quantities (directive 2026-08-22):
  Q1 leaf<->bus stowed standoff (nominal from kinematics module)
  Q2 leaf<->leaf stowed gap
  Q3 HDRM pin/sleeve alignment after thermal drift
  Q4 harness slack after thermal contraction

Thermal model (candidate band, PROVISIONAL_DERIVED):
  dT = +/-80 K LEO candidate; CTE Al bus 23e-6/K; CFRP leaf in-plane
  ~1e-6/K (near-zero, quasi-iso laminate candidate).
Manufacturing: worst-case (WC) and RSS both reported.
Hinge: M6 heritage tip sensitivity 0.2 mm/mrad; freeplay candidate
0.5 mrad at root (PROVISIONAL - no numeric authority yet, WP5 R2 item).

If Q1 fails WC, the directive-authorized fix is a standoff increase
(rebuild via kinematics STACK_STANDOFF); this script evaluates both the
as-found and the as-fixed value so the decision is numeric.

Outputs: CLEARANCE_MARGIN_LEDGER_R2_V1.json
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import solar_array_r2_kinematics as K

HERE = Path(__file__).resolve().parent
OUT = HERE / "CLEARANCE_MARGIN_LEDGER_R2_V1.json"

DT_HOT = 80.0
CTE_AL = 23.0e-6
CTE_CFRP = 1.0e-6

# candidates (PROVISIONAL_DERIVED unless noted)
MFG = {
    "cassette_position_mm": 0.10,
    "leaf_thickness_mm": 0.10,
    "hinge_line_position_mm": 0.10,
    "hdrm_station_position_mm": 0.15,
}
HINGE_TIP_SENSITIVITY_MM_PER_MRAD = 0.2   # M6 heritage (frozen evidence)
ROOT_FREEPLAY_MRAD = 0.5                  # PROVISIONAL candidate


def margin(nominal, terms):
    wc = nominal - sum(terms.values())
    rss = nominal - sum(v * v for v in terms.values()) ** 0.5
    return {"nominal_mm": round(nominal, 4),
            "terms_mm": {k: round(v, 4) for k, v in terms.items()},
            "margin_wc_mm": round(wc, 4),
            "margin_rss_mm": round(rss, 4),
            "functional_pass_wc": wc > 0.0}


def evaluate(standoff):
    q1 = margin(standoff, {
        "thermal_hot_bus_growth": CTE_AL * DT_HOT * K.BODY_CROSS_HALF,
        "mfg_cassette_position": MFG["cassette_position_mm"],
        "mfg_leaf_thickness": MFG["leaf_thickness_mm"],
        "mfg_hinge_line_position": MFG["hinge_line_position_mm"],
        "hinge_freeplay_at_root_region":
            HINGE_TIP_SENSITIVITY_MM_PER_MRAD * ROOT_FREEPLAY_MRAD * 0.15,
    })
    q2 = margin(K.LEAF_GAP, {
        "thermal_differential_leaf_leaf":
            abs(CTE_AL - CTE_CFRP) * 0.0,  # same material, same bath: ~0
        "mfg_two_leaf_thicknesses": 2 * MFG["leaf_thickness_mm"],
        "mfg_hinge_stack_position": MFG["hinge_line_position_mm"],
    })
    q3 = margin(0.50, {   # pin/sleeve diametral clearance candidate 0.5 mm
        "thermal_drift_al_vs_cfrp_over_120mm":
            abs(CTE_AL - CTE_CFRP) * DT_HOT * 120.0,
        "mfg_hdrm_station_position": MFG["hdrm_station_position_mm"],
    })
    q4 = margin(0.05 * 279.4, {  # solar root loop 5% provision margin
        "thermal_contraction_cable": 20.0e-6 * DT_HOT * 279.4,
        "routing_tolerance": 2.0,
    })
    return {"Q1_leaf_bus_standoff": q1, "Q2_leaf_leaf_gap": q2,
            "Q3_hdrm_pin_alignment": q3, "Q4_harness_slack": q4}


def main():
    as_found = evaluate(K.STACK_STANDOFF)          # 0.5 mm as built
    as_fixed = evaluate(1.0)                       # directive-authorized fix
    verdict = {
        "as_found_standoff_mm": K.STACK_STANDOFF,
        "as_found_Q1_pass_wc": as_found["Q1_leaf_bus_standoff"]["functional_pass_wc"],
        "action": ("none" if as_found["Q1_leaf_bus_standoff"]["functional_pass_wc"]
                   else "INCREASE_STANDOFF_TO_1.0_MM_AND_REBUILD"),
    }
    doc = {
        "schema": "CLEARANCE_MARGIN_LEDGER_R2_V1",
        "generated_local": datetime.now(
            timezone(timedelta(hours=8))).isoformat(),
        "authority": "ODR-26 / R2-WI-07",
        "class": "PROVISIONAL_DERIVED candidate budgets",
        "thermal_model": {"dT_K": DT_HOT, "cte_al": CTE_AL,
                          "cte_cfrp_inplane": CTE_CFRP},
        "as_found": as_found,
        "as_fixed_standoff_1p0": as_fixed,
        "verdict": verdict,
    }
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    for tag, res in (("AS_FOUND", as_found), ("AS_FIXED_1.0", as_fixed)):
        for q, r in res.items():
            print("%s %s: nominal=%.3f WC_margin=%+.4f pass=%s" % (
                tag, q, r["nominal_mm"], r["margin_wc_mm"],
                r["functional_pass_wc"]))


if __name__ == "__main__":
    main()
