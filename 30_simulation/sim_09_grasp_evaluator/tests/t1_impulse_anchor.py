"""t1 -- capture-impulse anchor (legacy_v0 chaser mode, nominal candidate).

Anchors (source: sim_06 results/capture_impulse_matrix_v0.csv row
target_debris_v0 @3 deg/s v_app=0.01, and sim_08 actuator_budget_sweep.csv):
    omega+    = 3.0633  +/- 0.001 deg/s
    |H_c|     = 3.6510  +/- 0.001 N*m*s
    |L_grasp| = 0.1217  +/- 0.001 N*m*s

Implementation check: general_capture_scenario(candidate_nominal, legacy_v0)
must reproduce the bodies of the existing build_capture_scenario FIELD BY FIELD
before rigidize is even run (bit-level scenario equivalence).
"""
import _helpers
import numpy as np

import adapters
import target_propagation
from capture_impulse import build_capture_scenario, rigidize, junction_couple
from evaluator import DEFAULT_CONFIG

ANCHORS = {"omega_plus_dps": (3.0633, 1e-3),
           "H_c_Nms": (3.6510, 1e-3),
           "L_grasp_Nms": (0.1217, 1e-3)}


def run():
    cand = _helpers.nominal_candidate()
    prop = target_propagation.propagate(cand.target_state,
                                        cand.grasp_pose_target[:3, 3],
                                        cand.capture_time)
    placement = adapters.scene_placement(cand, prop,
                                         DEFAULT_CONFIG["scenario"]["capture_point_S"])

    # --- scenario-level comparison vs the validated builder --------------------
    bodies_gen, meta = adapters.general_capture_scenario(cand, prop, placement,
                                                         chaser_mode="legacy_v0")
    bodies_ref, meta_ref = build_capture_scenario("target_debris_v0", 3.0, 0.01)
    worst_scene = 0.0
    for bg, br in zip(bodies_gen, bodies_ref):
        for k in ("m", "I", "r", "v", "w"):
            worst_scene = max(worst_scene, float(np.max(np.abs(
                np.asarray(bg[k], float) - np.asarray(br[k], float)))))
    assert worst_scene < 1e-14, f"scenario mismatch vs build_capture_scenario: {worst_scene:.3e}"

    # --- rigidize -> anchors ----------------------------------------------------
    res = rigidize(bodies_gen)
    J_t, L_g = junction_couple(res, bodies_gen, 1, meta["r_g_I"])
    got = {"omega_plus_dps": float(np.rad2deg(np.linalg.norm(res["w_plus"]))),
           "H_c_Nms": float(np.linalg.norm(res["I_comb"] @ res["w_plus"])),
           "L_grasp_Nms": float(np.linalg.norm(L_g))}

    # --- same numbers through the adapter API -----------------------------------
    cap = adapters.capture_adapter(cand, prop, placement, chaser_mode="legacy_v0")
    api = {"omega_plus_dps": cap["post_rate_dps"],
           "H_c_Nms": cap["H_c_norm_Nms"],
           "L_grasp_Nms": float(np.linalg.norm(cap["L_grasp_Nms"]))}

    rows, worst = [], 0.0
    for key, (exp, tol) in ANCHORS.items():
        res_direct = abs(got[key] - exp)
        res_api = abs(api[key] - exp)
        worst = max(worst, res_direct, res_api)
        assert res_direct < tol, f"{key}: got {got[key]:.6f}, expected {exp}+/-{tol}"
        assert res_api < tol, f"{key} (adapter API): got {api[key]:.6f}, expected {exp}+/-{tol}"
        rows.append({"anchor": key, "expected": exp, "measured": got[key],
                     "residual": res_direct, "tol": tol})
    return {"name": "t1_impulse_anchor", "passed": True, "worst_residual": worst,
            "rows": rows, "scene_field_mismatch": worst_scene,
            "note": "legacy_v0 scenario bit-matches build_capture_scenario; "
                    "anchors from sim_06/sim_08 CSVs"}


if __name__ == "__main__":
    out = run()
    for r in out["rows"]:
        print(f"{r['anchor']:16s} expected {r['expected']:.4f}  measured "
              f"{r['measured']:.6f}  residual {r['residual']:.2e} (tol {r['tol']})")
    print("scene mismatch:", f"{out['scene_field_mismatch']:.3e}")
    print("PASS" if out["passed"] else "FAIL", "| worst", f"{out['worst_residual']:.3e}")
