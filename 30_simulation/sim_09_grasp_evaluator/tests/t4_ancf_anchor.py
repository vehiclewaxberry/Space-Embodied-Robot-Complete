"""t4 -- ANCF flexible adapter anchor: for the sim_07a nominal 6DOF rigid-lock
case (legacy chaser, debris @3 deg/s, v_app=0.01) the adapter must reproduce

    tip peak = 3.674004 mm   +/- 1%
    U_max    = 2.3444e-5 J   +/- 1%

(source: 30_simulation/sim_07_ancf_flexible/results/task_response_summary.csv, row
6dof_rigid_lock/nominal). The excitation (dv, dw) is taken from the GENERAL
capture adapter in legacy_v0 mode -- i.e. the whole sim_09 chain reproduces the
validated sim_07a result, not just the beam integrator.
"""
import _helpers
import numpy as np

import adapters
import target_propagation
from evaluator import DEFAULT_CONFIG

ANCHOR_TIP_MM = 3.674004
ANCHOR_UMAX_J = 2.3444e-5
REL_TOL = 0.01


def run():
    cand = _helpers.nominal_candidate(capture_mode="rigid_6dof")
    prop = target_propagation.propagate(cand.target_state,
                                        cand.grasp_pose_target[:3, 3],
                                        cand.capture_time)
    placement = adapters.scene_placement(cand, prop,
                                         DEFAULT_CONFIG["scenario"]["capture_point_S"])
    cap = adapters.capture_adapter(cand, prop, placement, chaser_mode="legacy_v0")
    flx = adapters.flexible_adapter(cap["dv_chaser"], cap["dw_chaser"],
                                    placement["R_IS"], cap["meta"]["com_chaser_S"],
                                    t_end_s=15.0, n_eval=1500, rtol=1e-6,
                                    ei_case="nominal")
    rel_tip = abs(flx["tip_peak_mm"] - ANCHOR_TIP_MM) / ANCHOR_TIP_MM
    rel_u = abs(flx["U_max_J"] - ANCHOR_UMAX_J) / ANCHOR_UMAX_J
    worst = max(rel_tip, rel_u)
    assert rel_tip < REL_TOL, \
        f"tip peak {flx['tip_peak_mm']:.6f} mm vs anchor {ANCHOR_TIP_MM} ({rel_tip:.3%})"
    assert rel_u < REL_TOL, \
        f"U_max {flx['U_max_J']:.4e} J vs anchor {ANCHOR_UMAX_J} ({rel_u:.3%})"
    return {"name": "t4_ancf_anchor", "passed": True, "worst_residual": worst,
            "rows": [
                {"anchor": "tip_peak_mm", "expected": ANCHOR_TIP_MM,
                 "measured": flx["tip_peak_mm"], "residual_rel": rel_tip, "tol_rel": REL_TOL},
                {"anchor": "U_max_J", "expected": ANCHOR_UMAX_J,
                 "measured": flx["U_max_J"], "residual_rel": rel_u, "tol_rel": REL_TOL}],
            "E_flex_J": flx["E_flex_J"], "f1_hz": flx["f1_hz"],
            "note": "sim_07a 6dof_rigid_lock/nominal case via the sim_09 adapter chain"}


if __name__ == "__main__":
    out = run()
    for r in out["rows"]:
        print(f"{r['anchor']:12s} expected {r['expected']:.6g}  measured "
              f"{r['measured']:.6g}  rel residual {r['residual_rel']:.3e} (tol 1%)")
    print(f"E_flex = {out['E_flex_J']:.4e} J, f1 = {out['f1_hz']:.4f} Hz")
    print("PASS | worst rel", f"{out['worst_residual']:.3e}")
