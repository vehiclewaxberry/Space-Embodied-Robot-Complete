"""S02 (free-floating conservation, no control) and S03 (no-contact joint
motion candidate diagnostic). No gravity, no contact, rigid bodies only.

Preregistered S02 acceptance thresholds (v2 after Run2 archive; see
11_verification/_archive_run2/ for the v1 run and PROTOCOL_REVISIONS.md):
  REL_H_DRIFT_MAX   = 1e-9   relative momentum drift at dt=1e-3 over 5 s
  REL_E_DRIFT_MAX   = 1e-9   relative kinetic-energy drift (zero torque)
  ROUNDOFF_FLOOR    = 1e-12  relative; drift below this at every scanned dt is
                             itself the strongest pass evidence — convergence-
                             order fitting is ill-posed at the floor (same
                             failure family as sim_11's ideal-impulse metric)
  CONV_ORDER_RANGE  = [3.0, 5.5]  applies ONLY when drift is above the floor
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
    orders = []
    for a, b in zip(drifts[:-1], drifts[1:]):
        if b > 0:
            orders.append(float(np.log2(a / b)))
    main = runs[dt]
    metrics = _drift_metrics(main)

    # two-path cross-check: momentum projection of base velocity at final sample
    pT, quatT, qT, v6T, qdT = unpack_state(main["x"][-1], plant.nj)
    R_WB = quat_to_R(quatT)
    v6_proj = plant.base_velocity_from_momentum(R_WB, pT, qT, qdT, main["h_O"][0])
    xcheck = float(np.linalg.norm(v6T - v6_proj))

    th = S02_THRESHOLDS
    floor = th["roundoff_floor_rel"]
    # Roache-style pair-wise semantics (protocol R4): order fitting is valid
    # only between two drifts BOTH above the roundoff floor; a drift below the
    # floor is roundoff-dominated and carries no order information.
    informative = [
        o for o, ra, rb in zip(orders, rel_drifts[:-1], rel_drifts[1:])
        if ra >= floor and rb >= floor
    ]
    if all(r < floor for r in rel_drifts):
        conv_pass, conv_mode = True, "PASS_AT_ROUNDOFF_FLOOR"
    elif informative:
        conv_pass = all(th["conv_order_range"][0] <= o <= th["conv_order_range"][1] for o in informative)
        conv_mode = "ORDER_FIT" if conv_pass else "FAIL_ORDER_OUT_OF_RANGE"
    elif rel_drifts[-1] < floor:
        conv_pass, conv_mode = True, "PASS_ENTERED_ROUNDOFF_FLOOR"
    else:
        conv_pass, conv_mode = False, "FAIL_NO_ORDER_EVIDENCE_ABOVE_FLOOR"
    gates = {
        "G_h_conservation": metrics["rel_h_drift_max"] < th["rel_h_drift_max"],
        "G_E_conservation": metrics["rel_E_drift_max"] < th["rel_e_drift_max"],
        "G_convergence_order": conv_pass,
        "G_momentum_projection_xcheck": xcheck < th["xcheck_max"],
    }
    return {
        "ic": ic,
        "t_end_s": t_end,
        "dt_main_s": dt,
        "convergence_dts_s": list(convergence_dts),
        "drift_by_dt": dict(zip([str(d) for d in convergence_dts], drifts)),
        "rel_drift_by_dt": dict(zip([str(d) for d in convergence_dts], rel_drifts)),
        "observed_orders": orders,
        "informative_orders": informative,
        "convergence_mode": conv_mode,
        "metrics": metrics,
        "xcheck_base_velocity": xcheck,
        "thresholds": th,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
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
