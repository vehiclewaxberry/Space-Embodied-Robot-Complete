"""t3 -- b601 approach trajectory: total INERTIAL momentum along the whole
free-floating approach must stay below 1e-10 (reuses the sim_05 momentum_inertial
diagnostic, which is independent of the H-matrix assembly used to drive the base).

Trajectory: nominal candidate q0 -> q_c (IK solution of the approach_5d task),
joint-space min-jerk over 8 s, n_out = 800.
"""
import _helpers
import numpy as np

import adapters
import ik
import target_propagation
from evaluator import DEFAULT_CONFIG

MOM_TOL = 1e-10
CHECK_EVERY = 4          # momentum check at every 4th of the 800 output samples


def run():
    cand = _helpers.nominal_candidate(task_mode="approach_5d")
    prop = target_propagation.propagate(cand.target_state,
                                        cand.grasp_pose_target[:3, 3],
                                        cand.capture_time)
    placement = adapters.scene_placement(cand, prop,
                                         DEFAULT_CONFIG["scenario"]["capture_point_S"])
    task = ik.make_task("approach_5d", placement["p_des_S"], a_des=placement["a_des_S"])
    sols = ik.solve_ik(task, cand.initial_joint_configuration)
    assert sols, "IK failed for the nominal candidate"
    q_c = np.asarray(sols[0]["q"])

    br = adapters.base_reaction_adapter(cand.initial_joint_configuration, q_c,
                                        duration_s=8.0, n_out=800)
    traj, dyn = br["traj"], br["dyn"]
    q_fun, qd_fun = br["q_fun"], br["qd_fun"]
    worst = 0.0
    idx = range(0, len(traj["t"]), CHECK_EVERY)
    for i in idx:
        t = traj["t"][i]
        h = dyn.momentum_inertial(traj["r"][i], traj["Q"][i], q_fun(t),
                                  traj["Vb"][i], qd_fun(t))
        worst = max(worst, float(np.linalg.norm(h)))
    assert worst < MOM_TOL, f"inertial momentum norm {worst:.3e} >= {MOM_TOL}"
    return {"name": "t3_momentum", "passed": True, "worst_residual": worst,
            "peak_attitude_deg": br["peak_attitude_deg"],
            "peak_base_rate_dps": br["peak_base_rate_dps"],
            "n_checked": len(list(idx)),
            "note": f"|[P;L]|_inertial < {MOM_TOL} at {len(list(idx))} samples "
                    "(sim_05 momentum_inertial diagnostic)"}


if __name__ == "__main__":
    out = run()
    print(f"worst inertial momentum norm: {out['worst_residual']:.3e} "
          f"(tol {MOM_TOL}) over {out['n_checked']} samples")
    print(f"peak base attitude {out['peak_attitude_deg']:.4f} deg, "
          f"peak base rate {out['peak_base_rate_dps']:.4f} deg/s")
    print("PASS | worst", f"{out['worst_residual']:.3e}")
