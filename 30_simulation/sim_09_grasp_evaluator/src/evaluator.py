"""sim_09 -- evaluate(candidate, config) -> GraspEvaluationResult (Gate E0).

Pipeline: target propagation -> scene placement -> multi-start DLS IK
(-> INADMISSIBLE + IK_FAIL with a COMPLETE result structure if no solution)
-> collision margin along the approach trajectory -> free-floating base
reaction -> capture impulse (rigid_6dof / point_3dof) -> ANCF flexible energy
proxy -> actuator budget -> hard-constraint admissibility flags.

Hard-constraint thresholds live in 20_engineering/config/grasp_evaluator/hard_constraints_v1.yaml
(each threshold documents its source / placeholder status there).

Determinism: identical candidate -> bit-identical result (test t7). The only
non-deterministic outputs are the provenance wall_time_ms fields, excluded by
GraspEvaluationResult.canonical().

NO overall_score is computed (Gate E0 ruling: hard screening -> per-metric
values -> Pareto; see the comment slot in contract.GraspEvaluationResult).
"""
import _bootstrap  # noqa: F401
import copy
import os
import time

import numpy as np
import yaml

import adapters
import collision
import ik as ik_mod
import target_propagation
from contract import GraspEvaluationResult
from rigid_body import load_object

HARD_CONSTRAINTS_PATH = os.path.join(_bootstrap.CONFIG_DIR, "hard_constraints_v1.yaml")

# Evaluator defaults (scenario knobs; hard constraints stay in the yaml).
DEFAULT_CONFIG = {
    "scenario": {
        # GNC station-keeping assumption: the propagated grasp point is held at
        # this point of the servicer frame (see adapters.scene_placement).
        # [0.95, 0, -0.10] m: inside the B601 tool-along-+X workspace, away from
        # the on-axis wrist singularity (probed cond ~20-30 vs ~3e4 at z=0).
        "capture_point_S": [0.95, 0.0, -0.10],
        "chaser_mode": "b601",            # capture-scenario stack ("legacy_v0" = anchor)
        "propagation_mode": "const_omega",  # | "torque_free"
    },
    "approach": {"duration_s": 8.0, "n_out": 800},
    "collision": {"n_time_samples": 25},
    "flexible": {"enabled": True, "t_end_s": 15.0, "n_eval": 1500, "rtol": 1e-6,
                 "ei_case": "nominal"},
    "actuator": {"t_detumble_s": 900.0, "lever_m": 0.17, "isp_class": "cold_gas_60s"},
    # impact_severity_proxy = |J_t| + |L_grasp| / lever_ref  [N*s equivalent].
    # PROXY ONLY (no contact model): combines the transmitted impulse and the
    # grasp couple; NOT a peak contact force, NOT a grasp success probability.
    "severity": {"lever_ref_m": 1.0},
}

_HC_CACHE = {}


def load_hard_constraints(path=HARD_CONSTRAINTS_PATH):
    if path not in _HC_CACHE:
        with open(path, encoding="utf-8") as f:
            _HC_CACHE[path] = yaml.safe_load(f)["constraints"]
    return _HC_CACHE[path]


def make_config(overrides=None):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    for section, vals in (overrides or {}).items():
        cfg.setdefault(section, {}).update(vals)
    return cfg


def _empty_result(candidate, failure_codes, provenance, partial=None):
    """Complete result structure for an early-failed candidate."""
    hc = load_hard_constraints()
    flags = {name: False for name in hc}
    base = dict(
        ik_feasible=False, ik_solution_set=[], pose_residual=None,
        joint_limit_margin=None, task_jacobian_rank=None, task_nullity=None,
        manipulability=None, collision_margin=None, base_attitude_change=None,
        base_angular_velocity_metric=None, capture_impulse_6d=None,
        impulse_moment_at_grasp=None, post_capture_angular_velocity=None,
        wheel_momentum_required=None, thruster_impulse_required=None,
        propellant_required=None, flexible_energy_proxy=None,
        impact_severity_proxy=None, admissibility_flags=flags,
        failure_reason_codes=list(failure_codes), solver_provenance=provenance,
        scenario_hash=candidate.scenario_hash,
    )
    base.update(partial or {})
    return GraspEvaluationResult(**base)


def evaluate(candidate, config=None):
    cfg = config if config is not None else make_config()
    hc = load_hard_constraints()
    prov = {}
    failure = []

    # ---- 1. target propagation ------------------------------------------------
    t0 = time.time()
    try:
        r_g_T = candidate.grasp_pose_target[:3, 3]
        I_scaled = (np.asarray(candidate.target_inertia["I"], float)
                    * float(candidate.target_inertia.get("inertia_scale", 1.0)))
        prop = target_propagation.propagate(
            candidate.target_state, r_g_T, candidate.capture_time,
            mode=cfg["scenario"]["propagation_mode"], target_I=I_scaled)
    except Exception:
        prov["target_propagation"] = adapters.provenance(
            "30_simulation/sim_09_grasp_evaluator/src/target_propagation.py -> 30_simulation/common/rigid_body.py",
            {"r_g": "m", "v_g": "m/s", "omega": "rad/s"}, t0)
        return _empty_result(candidate, ["PROPAGATION_FAIL"], prov)
    prov["target_propagation"] = adapters.provenance(
        "30_simulation/sim_09_grasp_evaluator/src/target_propagation.py -> 30_simulation/common/rigid_body.py",
        {"r_g": "m", "v_g": "m/s", "omega": "rad/s"}, t0)

    placement = adapters.scene_placement(candidate, prop,
                                         cfg["scenario"]["capture_point_S"])

    # ---- 2. IK ------------------------------------------------------------------
    t0 = time.time()
    arm = ik_mod.get_arm()
    mode = candidate.task_constraint_mode
    if mode == "pose_6d":
        task = ik_mod.make_task(mode, placement["p_des_S"], R_des=placement["R_des_S"])
    elif mode == "approach_5d":
        task = ik_mod.make_task(mode, placement["p_des_S"], a_des=placement["a_des_S"])
    else:
        task = ik_mod.make_task(mode, placement["p_des_S"])
    sols = ik_mod.solve_ik(task, candidate.initial_joint_configuration, arm=arm)
    prov["ik"] = adapters.provenance(
        "30_simulation/sim_09_grasp_evaluator/src/ik.py -> 30_simulation/sim_05_free_floating_arm/b601_model.py",
        {"q": "rad", "residual_position": "m", "residual_orientation": "rad"}, t0)
    if not sols:
        return _empty_result(candidate, ["IK_FAIL"], prov)
    sel = sols[0]
    q_c = np.asarray(sel["q"], float)

    # manipulability at the selected solution (task Jacobian)
    _, J_task, _ = ik_mod.residual_and_jacobian(arm, q_c, task)
    sv = np.linalg.svd(J_task, compute_uv=False)
    manip = {"sqrt_det_JJT": float(np.prod(sv)), "sigma_min": float(sv[-1])}

    # ---- 3. collision along the approach trajectory ------------------------------
    t0 = time.time()
    q_fun, _ = adapters.approach_trajectory(candidate.initial_joint_configuration,
                                            q_c, cfg["approach"]["duration_s"])
    cg_T = load_object(candidate.target_id)["cg"]
    tprim = collision.target_primitive(candidate.target_id, placement["R_TS"],
                                       placement["r_T_S"], cg_T)
    t_grid = np.linspace(0.0, cfg["approach"]["duration_s"],
                         int(cfg["collision"]["n_time_samples"]))
    col = collision.trajectory_margin(arm, q_fun, t_grid, tprim,
                                      placement["p_des_S"])
    prov["collision"] = adapters.provenance(
        "30_simulation/sim_09_grasp_evaluator/src/collision.py (geometry: 20_engineering/config/grasp_evaluator/"
        "collision_geometry_v1.yaml)", {"margin": "m", "t": "s"}, t0)

    # ---- 4. free-floating base reaction -------------------------------------------
    br = adapters.base_reaction_adapter(candidate.initial_joint_configuration, q_c,
                                        cfg["approach"]["duration_s"],
                                        cfg["approach"]["n_out"])
    prov["base_reaction"] = br["provenance"]

    # ---- 5. capture impulse ---------------------------------------------------------
    cap = adapters.capture_adapter(candidate, prop, placement,
                                   cfg["scenario"]["chaser_mode"], q_c)
    prov["capture_impulse"] = cap["provenance"]

    # ---- 6. flexible energy proxy ------------------------------------------------------
    if cfg["flexible"]["enabled"]:
        flx = adapters.flexible_adapter(cap["dv_chaser"], cap["dw_chaser"],
                                        placement["R_IS"],
                                        cap["meta"]["com_chaser_S"],
                                        t_end_s=cfg["flexible"]["t_end_s"],
                                        n_eval=cfg["flexible"]["n_eval"],
                                        rtol=cfg["flexible"]["rtol"],
                                        ei_case=cfg["flexible"]["ei_case"])
        prov["flexible"] = flx["provenance"]
        e_flex = flx["E_flex_J"]
    else:
        flx, e_flex = None, None

    # ---- 7. actuator budget ---------------------------------------------------------------
    act = adapters.actuator_adapter(cap["H_c_norm_Nms"],
                                    cfg["actuator"]["t_detumble_s"],
                                    cfg["actuator"]["lever_m"],
                                    cfg["actuator"]["isp_class"])
    prov["actuator"] = act["provenance"]

    # ---- 8. severity proxy + admissibility -----------------------------------------------
    J_t = np.asarray(cap["J_t_Ns"], float)
    L_g = np.asarray(cap["L_grasp_Nms"], float)
    severity = float(np.linalg.norm(J_t)
                     + np.linalg.norm(L_g) / float(cfg["severity"]["lever_ref_m"]))

    flags = {
        "collision_margin_min_m": col["min_margin_m"] > float(hc["collision_margin_min_m"]),
        "condition_number_max": sel["condition_number"] < float(hc["condition_number_max"]),
        "post_capture_rate_max_dps": cap["post_rate_dps"] < float(hc["post_capture_rate_max_dps"]),
        "wheel_momentum_max_Nms": cap["H_c_norm_Nms"] < float(hc["wheel_momentum_max_Nms"]),
        "flexible_energy_max_J": (True if e_flex is None
                                  else e_flex < float(hc["flexible_energy_max_J"])),
        "joint_limit_margin_min_rad": sel["joint_limit_margin"] > float(hc["joint_limit_margin_min_rad"]),
    }
    if not flags["joint_limit_margin_min_rad"]:
        failure.append("LIMIT_VIOLATION")
    if not flags["collision_margin_min_m"]:
        failure.append("COLLISION")
    if not flags["condition_number_max"]:
        failure.append("SINGULAR")
    if not flags["post_capture_rate_max_dps"]:
        failure.append("IMPULSE_EXCEED")
    if not flags["wheel_momentum_max_Nms"]:
        failure.append("ACTUATOR_EXCEED")
    if not flags["flexible_energy_max_J"]:
        failure.append("FLEX_EXCEED")

    return GraspEvaluationResult(
        ik_feasible=True,
        ik_solution_set=sols,
        pose_residual={"position_m": sel["residual_position"],
                       "orientation_rad": sel["residual_orientation"]},
        joint_limit_margin=sel["joint_limit_margin"],
        task_jacobian_rank=sel["task_rank"],
        task_nullity=sel["task_nullity"],
        manipulability=manip,
        collision_margin={"min_margin_m": col["min_margin_m"],
                          "t_at_min_s": col["t_at_min_s"]},
        base_attitude_change=br["peak_attitude_deg"],
        base_angular_velocity_metric=br["peak_base_rate_dps"],
        capture_impulse_6d={"J_t_Ns": cap["J_t_Ns"], "L_grasp_Nms": cap["L_grasp_Nms"]},
        impulse_moment_at_grasp={"L_grasp_Nms": cap["L_grasp_Nms"],
                                 "norm_Nms": float(np.linalg.norm(L_g))},
        post_capture_angular_velocity=cap["post_rate_dps"],
        wheel_momentum_required=cap["H_c_norm_Nms"],
        thruster_impulse_required=act["total_impulse_Ns"],
        propellant_required=act["propellant_selected_g"],
        flexible_energy_proxy=e_flex,
        impact_severity_proxy=severity,
        admissibility_flags=flags,
        failure_reason_codes=failure,
        solver_provenance=prov,
        scenario_hash=candidate.scenario_hash,
    )
