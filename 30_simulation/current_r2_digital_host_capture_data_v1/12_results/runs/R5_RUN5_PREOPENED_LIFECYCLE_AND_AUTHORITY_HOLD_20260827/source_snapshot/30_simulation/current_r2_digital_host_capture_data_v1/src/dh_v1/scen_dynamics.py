"""S02 (free-floating conservation, no control) and S03 (no-contact joint
motion candidate diagnostic). No gravity, no contact, rigid bodies only.

Preregistered S02 acceptance thresholds (R4 after Run3 archive; see
11_verification/_archive_run2/ for the v1 run and PROTOCOL_REVISIONS.md):
  REL_H_DRIFT_MAX   = 1e-9   relative momentum drift at dt=1e-3 over 5 s
  REL_E_DRIFT_MAX   = 1e-9   relative kinetic-energy drift (zero torque)
  ROUNDOFF_FLOOR    = 1e-12  relative; order fitting applies only to adjacent
                             pairs whose endpoints are both at or above the floor
  CONV_ORDER_RANGE  = [3.0, 5.5]  applies ONLY to those informative pairs
  XCHECK_MAX        = 1e-8   |v_base integrated - v_base from momentum projection|
S03 has NO pass gate: it is a diagnostic and must not be cited as control PASS.
"""
from __future__ import annotations

import numpy as np

from .frames import quat_to_R
from .integrators import pack_state, rk4_run, unpack_state
from .plant import FloatingPlant

S02_THRESHOLDS = {
    "rel_h_drift_max": 1.0e-9,
    "rel_e_drift_max": 1.0e-9,
    "roundoff_floor_rel": 1.0e-12,
    "conv_order_range": [3.0, 5.5],
    "xcheck_max": 1.0e-8,
}


def evaluate_s02_convergence(rel_drifts, convergence_dts, thresholds=None) -> dict:
    """Evaluate the R4 pairwise convergence protocol without running a plant.

    Inputs are consumed in their supplied order.  The protocol requires a
    strict coarse-to-fine successive-halving sequence; this function never
    sorts them.
    Values below the declared floor are treated as roundoff dominated, but the
    floor cannot excuse a non-monotone approach from the measurable region.
    """
    th = S02_THRESHOLDS if thresholds is None else thresholds
    rel = np.asarray(rel_drifts, dtype=float)
    dts = np.asarray(convergence_dts, dtype=float)
    floor = float(th["roundoff_floor_rel"])
    order_lo, order_hi = map(float, th["conv_order_range"])

    if rel.ndim != 1 or dts.ndim != 1 or len(rel) == 0 or len(rel) != len(dts):
        return {
            "passed": False,
            "mode": "FAIL_INVALID_CONVERGENCE_INPUT",
            "dt_order_valid": False,
            "dt_ratio_valid": False,
            "observed_orders": [],
            "informative_orders": [],
            "informative_pair_indices": [],
        }
    finite_nonnegative = bool(np.all(np.isfinite(rel)) and np.all(rel >= 0.0))
    finite_positive_dts = bool(np.all(np.isfinite(dts)) and np.all(dts > 0.0))
    dt_order_valid = bool(finite_positive_dts and (len(dts) == 1 or np.all(dts[:-1] > dts[1:])))
    dt_ratio_valid = bool(dt_order_valid and (len(dts) == 1 or np.allclose(dts[:-1] / dts[1:], 2.0, rtol=1.0e-12, atol=0.0)))
    if not finite_nonnegative or not dt_order_valid or not dt_ratio_valid:
        if not finite_nonnegative:
            invalid_mode = "FAIL_NONFINITE_OR_NEGATIVE_DRIFT"
        elif not dt_order_valid:
            invalid_mode = "FAIL_INVALID_DT_ORDER"
        else:
            invalid_mode = "FAIL_INVALID_DT_RATIO"
        return {
            "passed": False,
            "mode": invalid_mode,
            "dt_order_valid": dt_order_valid,
            "dt_ratio_valid": dt_ratio_valid,
            "observed_orders": [],
            "informative_orders": [],
            "informative_pair_indices": [],
        }
    if len(rel) < 3:
        return {
            "passed": False,
            "mode": "FAIL_INSUFFICIENT_REFINEMENT_POINTS",
            "dt_order_valid": dt_order_valid,
            "dt_ratio_valid": dt_ratio_valid,
            "observed_orders": [],
            "informative_orders": [],
            "informative_pair_indices": [],
        }

    observed_orders = []
    informative_orders = []
    informative_pair_indices = []
    for idx, (ra, rb, da, db) in enumerate(zip(rel[:-1], rel[1:], dts[:-1], dts[1:])):
        if ra > 0.0 and rb > 0.0:
            order = float(np.log(ra / rb) / np.log(da / db))
        elif ra == 0.0 and rb == 0.0:
            order = float("nan")
        elif rb == 0.0:
            order = float("inf")
        else:
            order = float("-inf")
        observed_orders.append(order)
        if ra >= floor and rb >= floor:
            informative_orders.append(order)
            informative_pair_indices.append(idx)

    effective = np.maximum(rel, floor)
    monotone_to_floor = bool(np.all(effective[:-1] >= effective[1:]))
    if bool(np.all(rel < floor)):
        passed, mode = True, "PASS_AT_ROUNDOFF_FLOOR"
    elif informative_orders:
        order_pass = bool(all(np.isfinite(o) and order_lo <= o <= order_hi for o in informative_orders))
        passed = order_pass and monotone_to_floor
        mode = "ORDER_FIT" if passed else ("FAIL_NONMONOTONE_REFINEMENT" if not monotone_to_floor else "FAIL_ORDER_OUT_OF_RANGE")
    else:
        # Compare after clipping sub-floor noise to the floor.  This demands a
        # consistent coarse->fine decrease in the measurable region while not
        # pretending that ordering within roundoff noise is meaningful.
        entered_floor = bool(np.any(rel[:-1] >= floor) and rel[-1] < floor)
        passed = entered_floor and monotone_to_floor
        mode = "PASS_ENTERED_ROUNDOFF_FLOOR" if passed else "FAIL_NO_ORDER_EVIDENCE_ABOVE_FLOOR"

    return {
        "passed": passed,
        "mode": mode,
        "dt_order_valid": dt_order_valid,
        "dt_ratio_valid": dt_ratio_valid,
        "observed_orders": observed_orders,
        "informative_orders": informative_orders,
        "informative_pair_indices": informative_pair_indices,
    }


def evaluate_s02_gates(metrics: dict, xcheck: float, convergence: dict, thresholds=None) -> dict:
    """Apply hard S02 gates independently of the convergence label."""
    th = S02_THRESHOLDS if thresholds is None else thresholds
    gates = {
        "G_h_conservation": bool(np.isfinite(metrics["rel_h_drift_max"]) and metrics["rel_h_drift_max"] < th["rel_h_drift_max"]),
        "G_E_conservation": bool(np.isfinite(metrics["rel_E_drift_max"]) and metrics["rel_E_drift_max"] < th["rel_e_drift_max"]),
        "G_convergence_order": bool(convergence["passed"]),
        "G_momentum_projection_xcheck": bool(np.isfinite(xcheck) and xcheck < th["xcheck_max"]),
    }
    return {
        "gates": gates,
        "hard_gate_failures": [name for name, passed in gates.items() if name != "G_convergence_order" and not passed],
        "all_gates_pass": all(gates.values()),
    }


def assess_s03_refinement(run_summaries, momentum_abs_max=1.0e-9) -> dict:
    """Classify S03 time-step evidence while permanently withholding release.

    ``run_summaries`` must be ordered coarse->fine.  S03 remains diagnostic
    even when numerical refinement is supported; persistent effort saturation
    can therefore never turn into a complete scenario PASS.
    """
    runs = list(run_summaries)
    dts = [float(r["dt_s"]) for r in runs]
    order_valid = bool(len(runs) >= 2 and all(a > b for a, b in zip(dts[:-1], dts[1:])))
    if not order_valid:
        status = "R4_REPEAT_REQUIRED_INVALID_DT_ORDER"
    else:
        saturation = [bool(r["any_saturation"]) for r in runs]
        drift = [float(r["internal_torque_momentum_drift_abs"]) for r in runs]
        if saturation[-1] or all(saturation):
            status = "RUN4_PHYSICAL_OR_CONTROL_SATURATION_CONFIRMED"
        elif saturation[0] and not saturation[-1] and np.isfinite(drift[-1]) and drift[-1] < momentum_abs_max and drift[-1] < drift[0]:
            status = "RUN4_NUMERICAL_REFINEMENT_SUPPORTED"
        elif not np.all(np.isfinite(drift)) or drift[-1] >= momentum_abs_max or drift[-1] >= drift[0]:
            status = "RUN4_REPEAT_MOMENTUM_LEDGER_OR_MODEL_DEFECT"
        else:
            status = "R4_REPEAT_REQUIRED"
    return {
        "status": status,
        "dt_order_valid": order_valid,
        "complete_scenario_pass": False,
        "control_release": False,
        "claim": "DIAGNOSTIC_ONLY_NOT_CONTROL_PASS",
    }


def _drift_metrics(samples: dict) -> dict:
    h0 = samples["h_O"][0]
    scale_h = max(float(np.linalg.norm(h0)), 1.0e-3)
    dh = np.linalg.norm(samples["h_O"] - h0, axis=1)
    E0 = float(samples["E"][0])
    dE = np.abs(samples["E"] - E0)
    # CoM must move linearly: fit and take residual
    t = samples["t"]
    res = []
    for k in range(3):
        c = np.polyfit(t, samples["p_com"][:, k], 1)
        res.append(float(np.max(np.abs(np.polyval(c, t) - samples["p_com"][:, k]))))
    return {
        "h0_world": h0.tolist(),
        "abs_h_drift_max": float(dh.max()),
        "rel_h_drift_max": float(dh.max() / scale_h),
        "E0_J": E0,
        "abs_E_drift_max": float(dE.max()),
        "rel_E_drift_max": float(dE.max() / max(abs(E0), 1.0e-9)),
        "com_linearity_residual_m": res,
        "quat_renorm_accumulated": float(samples["quat_renorm"][-1]),
    }


def _default_x0(plant: FloatingPlant, ic: str) -> np.ndarray:
    nj = plant.nj
    q = np.zeros(nj)
    # interior, non-singular arm posture (well inside B601 limits)
    q[1] = -1.0
    q[2] = -0.8
    q[3] = 0.3
    q[4] = 0.4
    qd = np.array([0.30, -0.20, 0.25, -0.15, 0.20, -0.10, 0.010, 0.010])[:nj]
    p = np.zeros(3)
    quat = np.array([1.0, 0.0, 0.0, 0.0])
    if ic == "base_at_rest_arm_moving":
        v6 = np.zeros(6)
    elif ic == "base_tumbling_arm_moving":
        v6 = np.array([0.02, -0.03, 0.05, 0.010, 0.0, -0.005])
    else:
        raise ValueError(f"unknown IC {ic!r}")
    return pack_state(p, quat, q, v6, qd)


def run_s02_case(plant: FloatingPlant, ic: str, t_end: float = 5.0, dt: float = 1.0e-3,
                 convergence_dts=(4.0e-3, 2.0e-3, 1.0e-3)) -> dict:
    x0 = _default_x0(plant, ic)
    runs = {}
    for d in convergence_dts:
        s = rk4_run(plant, x0, t_end, d, sample_every=max(1, int(round(0.05 / d))))
        runs[d] = s
    # convergence evidence between successive halvings on momentum drift.
    # At the roundoff floor, order fitting is ill-posed: floor itself passes.
    drifts = []
    scales = []
    for d in convergence_dts:
        h0 = runs[d]["h_O"][0]
        drifts.append(float(np.max(np.linalg.norm(runs[d]["h_O"] - h0, axis=1))))
        scales.append(max(float(np.linalg.norm(h0)), 1.0e-3))
    rel_drifts = [dr / sc for dr, sc in zip(drifts, scales)]
    main = runs[dt]
    metrics = _drift_metrics(main)

    # two-path cross-check: momentum projection of base velocity at final sample
    pT, quatT, qT, v6T, qdT = unpack_state(main["x"][-1], plant.nj)
    R_WB = quat_to_R(quatT)
    v6_proj = plant.base_velocity_from_momentum(R_WB, pT, qT, qdT, main["h_O"][0])
    xcheck = float(np.linalg.norm(v6T - v6_proj))

    th = S02_THRESHOLDS
    convergence = evaluate_s02_convergence(rel_drifts, convergence_dts, th)
    gate_eval = evaluate_s02_gates(metrics, xcheck, convergence, th)
    return {
        "ic": ic,
        "t_end_s": t_end,
        "dt_main_s": dt,
        "convergence_dts_s": list(convergence_dts),
        "drift_by_dt": dict(zip([str(d) for d in convergence_dts], drifts)),
        "rel_drift_by_dt": dict(zip([str(d) for d in convergence_dts], rel_drifts)),
        "observed_orders": convergence["observed_orders"],
        "informative_orders": convergence["informative_orders"],
        "informative_pair_indices": convergence["informative_pair_indices"],
        "dt_order_valid": convergence["dt_order_valid"],
        "dt_ratio_valid": convergence["dt_ratio_valid"],
        "convergence_mode": convergence["mode"],
        "metrics": metrics,
        "xcheck_base_velocity": xcheck,
        "thresholds": th,
        "gates": gate_eval["gates"],
        "hard_gate_failures": gate_eval["hard_gate_failures"],
        "all_gates_pass": gate_eval["all_gates_pass"],
        "samples": main,  # caller strips before JSON
    }


def quintic(t, T):
    """Quintic 0->1 time law with zero boundary vel/acc; returns (s, sd, sdd)."""
    tau = np.clip(t / T, 0.0, 1.0)
    s = 10 * tau**3 - 15 * tau**4 + 6 * tau**5
    sd = (30 * tau**2 - 60 * tau**3 + 30 * tau**4) / T
    sdd = (60 * tau - 180 * tau**2 + 120 * tau**3) / T**2
    return s, sd, sdd


def run_s03(plant: FloatingPlant, t_end: float = 8.0, dt: float = 5.0e-4) -> dict:
    """PD joint tracking of a smooth quintic interior trajectory; free base.
    DIAGNOSTIC ONLY (control ladder C1 candidate) — never a control PASS.

    dt=5e-4 nominal: the fastest PD joint mode (low-inertia distal joints with
    the chosen Kd) exceeds the RK4 stability boundary at dt=1e-3, producing
    saturation chatter and O(0.1) momentum drift. That dt=1e-3 run is kept as a
    preregistered negative witness (see orchestrator), not silently discarded.
    """
    nj = plant.nj
    q_start = np.zeros(nj)
    q_start[1], q_start[2] = -1.2, -0.9
    q_goal = q_start.copy()
    q_goal[0] = 0.8
    q_goal[1] = -0.6
    q_goal[2] = -1.3
    q_goal[4] = 0.7
    q_goal[5] = 0.5
    T_traj = 6.0
    Kp = np.array([40.0, 60.0, 50.0, 15.0, 10.0, 8.0, 200.0, 200.0])[:nj]
    Kd = np.array([8.0, 12.0, 10.0, 2.0, 1.5, 1.2, 20.0, 20.0])[:nj]
    effort_caps = []
    for b in plant.bodies[1:]:
        effort_caps.append(b.limits.get("effort", np.inf) if b.limits else np.inf)
    effort_caps = np.asarray(effort_caps)

    log = {"tau": [], "e": [], "t": []}

    def tau_fn(t, q, qd, v_base):
        s, sd, _ = quintic(t, T_traj)
        q_ref = q_start + s * (q_goal - q_start)
        qd_ref = sd * (q_goal - q_start)
        e = q_ref - q
        tau = Kp * e + Kd * (qd_ref - qd)
        tau = np.clip(tau, -effort_caps, effort_caps)
        log["tau"].append(tau.copy())
        log["e"].append(e.copy())
        log["t"].append(t)
        return tau

    x0 = pack_state(np.zeros(3), np.array([1.0, 0, 0, 0]), q_start, np.zeros(6), np.zeros(nj))
    samples = rk4_run(plant, x0, t_end, dt, tau_fn=tau_fn, sample_every=max(1, int(round(0.05 / dt))))

    # settled tracking error (after trajectory end)
    tail = samples["t"] >= T_traj + 1.0
    qs = np.array([unpack_state(x, nj)[2] for x in samples["x"]])
    e_final = np.abs(qs[tail] - q_goal).max() if tail.any() else float("nan")
    tau_arr = np.asarray(log["tau"])
    quat_final = unpack_state(samples["x"][-1], nj)[1]
    ang = 2.0 * np.arccos(np.clip(abs(quat_final[0]), -1.0, 1.0))
    h0 = samples["h_O"][0]
    dh = float(np.max(np.linalg.norm(samples["h_O"] - h0, axis=1)))
    return {
        "scenario_id": "S03_NO_CONTACT_JOINT_MOTION_CANDIDATE",
        "claim": "DIAGNOSTIC_ONLY_NOT_CONTROL_PASS",
        "t_end_s": t_end,
        "dt_s": dt,
        "trajectory": {"type": "quintic", "T_s": T_traj, "q_start": q_start.tolist(), "q_goal": q_goal.tolist()},
        "tracking_error_settled_rad": float(e_final),
        "tau_abs_max_per_joint": np.abs(tau_arr).max(axis=0).tolist(),
        "effort_caps": effort_caps.tolist(),
        "any_saturation": bool(np.any(np.abs(tau_arr) >= effort_caps * 0.999)),
        "base_attitude_change_deg": float(np.degrees(ang)),
        "base_translation_m": float(np.linalg.norm(unpack_state(samples["x"][-1], nj)[0])),
        "internal_torque_momentum_drift_abs": dh,
        "samples": samples,
    }
