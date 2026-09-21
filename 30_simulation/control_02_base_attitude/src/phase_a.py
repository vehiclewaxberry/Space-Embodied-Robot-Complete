"""Stage A: bounded L0 momentum-level base-reaction suppression."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from config_loader import REPO
from ledger import classify_attribution


SIM05 = REPO / "30_simulation" / "sim_05_free_floating_arm"
COMMON = REPO / "30_simulation" / "common"
sys.path.insert(0, str(SIM05))
sys.path.insert(0, str(COMMON))

from dynamics import FreeFloatingB601, attitude_angle_deg, min_jerk  # noqa: E402
from rigid_body import q_to_R, qmult  # noqa: E402


E_WHEEL = np.vstack((np.zeros((3, 3)), np.eye(3)))


def _nominal_functions(
    q_start_rad: np.ndarray, q_end_rad: np.ndarray, t_maneuver: float
):
    q_start_rad = np.asarray(q_start_rad, dtype=float)
    q_end_rad = np.asarray(q_end_rad, dtype=float)
    delta = q_end_rad - q_start_rad

    def q_fun(t):
        return q_start_rad + np.array(
            [min_jerk(t, t_maneuver, a)[0] for a in delta]
        )

    def qd_fun(t):
        return np.array([min_jerk(t, t_maneuver, a)[1] for a in delta])

    return q_fun, qd_fun


def _quat_rhs(quat: np.ndarray, omega_body: np.ndarray) -> np.ndarray:
    qn = quat / np.linalg.norm(quat)
    return 0.5 * qmult(qn, np.array([0.0, *omega_body]))


def _midpoint_step(rhs, t: float, y: np.ndarray, dt: float) -> np.ndarray:
    """Deterministic two-evaluation fixed-grid step (bounded runtime)."""
    k1 = rhs(t, y)
    km = rhs(t + 0.5 * dt, y + 0.5 * dt * k1)
    out = y + dt * km
    out[3:7] /= np.linalg.norm(out[3:7])
    return out


def _reaction_projected_rate(
    dyn: FreeFloatingB601, q: np.ndarray, qd_des: np.ndarray, regularization: float
) -> tuple[np.ndarray, float]:
    """Closest bounded-rate command satisfying the corrected omega_b constraint."""
    hbb, hbm = dyn.momentum_matrices(q)
    reaction_map = np.linalg.solve(hbb, hbm)[3:, :]
    gram = reaction_map @ reaction_map.T
    correction = reaction_map.T @ np.linalg.solve(
        gram + (regularization**2) * np.eye(3), reaction_map @ qd_des
    )
    qd = qd_des - correction
    return qd, float(np.linalg.norm(reaction_map @ qd))


def _wheel_allocation(
    dyn: FreeFloatingB601,
    q: np.ndarray,
    qd: np.ndarray,
    capacity: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Ideal L0 wheel momentum allocation with a per-axis physical box."""
    hbb, hbm = dyn.momentum_matrices(q)
    arm_momentum = hbm @ qd
    omega_no_wheel = -np.linalg.solve(hbb, arm_momentum)[3:]
    wheel_to_omega = np.linalg.solve(hbb, E_WHEEL)[3:, :]
    h_unclipped = np.linalg.solve(wheel_to_omega, omega_no_wheel)
    return np.clip(h_unclipped, -capacity, capacity), h_unclipped


def _sample_ledger(dyn, q, qd, wheel_h):
    hbb, hbm = dyn.momentum_matrices(q)
    vb = -np.linalg.solve(hbb, hbm @ qd + E_WHEEL @ wheel_h)
    body = hbb @ vb + hbm @ qd
    total = body + E_WHEEL @ wheel_h
    return vb, body, total


def _closure_functions(q_s, qd_s, q_end, t_switch, t_maneuver):
    """Per-joint quintic on tau in [0,1] with matched start rate and exact end.

    Boundary conditions: p(0)=q_s, p'(0)=qd_s*duration, p''(0)=0,
    p(1)=q_end, p'(1)=0, p''(1)=0.  For t >= t_maneuver the command clamps to
    exactly the registered endpoint with zero rate, so the task endpoint is an
    identity by construction (R4 endpoint_policy=EXACT_REGISTERED_ENDPOINT).
    """
    duration = t_maneuver - t_switch
    a0 = np.asarray(q_s, dtype=float)
    a1 = np.asarray(qd_s, dtype=float) * duration
    system = np.array(
        [[1.0, 1.0, 1.0], [3.0, 4.0, 5.0], [6.0, 12.0, 20.0]]
    )
    rhs = np.vstack(
        (np.asarray(q_end, dtype=float) - a0 - a1, -a1, np.zeros(6))
    )
    a345 = np.linalg.solve(system, rhs)

    def q_fun(t):
        if t >= t_maneuver:
            return np.asarray(q_end, dtype=float).copy()
        tau = max((t - t_switch) / duration, 0.0)
        return (
            a0
            + a1 * tau
            + a345[0] * tau**3
            + a345[1] * tau**4
            + a345[2] * tau**5
        )

    def qd_fun(t):
        if t >= t_maneuver:
            return np.zeros(6)
        tau = max((t - t_switch) / duration, 0.0)
        return (
            a1
            + 3.0 * a345[0] * tau**2
            + 4.0 * a345[1] * tau**3
            + 5.0 * a345[2] * tau**4
        ) / duration

    return q_fun, qd_fun


def _integrate_a1(dyn, q_start, q_end, qd_nom, stage):
    """Task-valid two-segment A1 (R4 redesign).

    Segment 1 [0, t_switch]: reaction-projected rate command (reduces base
    angular reaction).  Segment 2 [t_switch, t_maneuver]: analytic quintic
    closure with matched joint rates landing exactly on the registered joint
    endpoint; base pose keeps integrating under zero total momentum.
    """
    dt = float(stage["time_step_s"])
    t_end = float(stage["end_time_s"])
    t_maneuver = float(stage["maneuver_duration_s"])
    t_switch = float(stage["A1"]["t_switch_s"])
    regularization = float(stage["A1"]["projection_regularization"])
    n = int(round(t_end / dt)) + 1
    i_sw = int(round(t_switch / dt))
    ts = np.linspace(0.0, t_end, n)

    y = np.zeros(13)
    y[3] = 1.0
    y[7:13] = q_start

    def rhs13(t, state):
        quat = state[3:7] / np.linalg.norm(state[3:7])
        q = state[7:13]
        qd, _ = _reaction_projected_rate(dyn, q, qd_nom(t), regularization)
        vb = dyn.base_velocity_zero_momentum(q, qd)
        rdot = q_to_R(quat).as_matrix() @ vb[:3]
        return np.concatenate((rdot, _quat_rhs(quat, vb[3:]), qd))

    hist13 = np.zeros((i_sw + 1, 13))
    hist13[0] = y
    for i in range(i_sw):
        y = _midpoint_step(rhs13, ts[i], y, dt)
        hist13[i + 1] = y

    q_s = hist13[i_sw, 7:13].copy()
    qd_s, _ = _reaction_projected_rate(dyn, q_s, qd_nom(ts[i_sw]), regularization)
    q_c, qd_c = _closure_functions(q_s, qd_s, q_end, t_switch, t_maneuver)

    def rhs7(t, state):
        quat = state[3:7] / np.linalg.norm(state[3:7])
        vb = dyn.base_velocity_zero_momentum(q_c(t), qd_c(t))
        rdot = q_to_R(quat).as_matrix() @ vb[:3]
        return np.concatenate((rdot, _quat_rhs(quat, vb[3:])))

    pose = np.concatenate((hist13[i_sw, :3], hist13[i_sw, 3:7]))
    pose_hist = np.zeros((n, 7))
    pose_hist[: i_sw + 1] = hist13[:, :7]
    for i in range(i_sw, n - 1):
        pose = _midpoint_step(rhs7, ts[i], pose, dt)
        pose_hist[i + 1] = pose

    q_hist = np.zeros((n, 6))
    qd_hist = np.zeros((n, 6))
    q_hist[: i_sw + 1] = hist13[:, 7:13]
    for i in range(i_sw + 1):
        qd_hist[i], _ = _reaction_projected_rate(
            dyn, hist13[i, 7:13], qd_nom(ts[i]), regularization
        )
    for i in range(i_sw + 1, n):
        q_hist[i] = q_c(ts[i])
        qd_hist[i] = qd_c(ts[i])
    return ts, pose_hist, q_hist, qd_hist, i_sw


def _integrate_a2(dyn, q_nom, qd_nom, capacity, dt, t_end):
    n = int(round(t_end / dt)) + 1
    ts = np.linspace(0.0, t_end, n)
    y = np.zeros(7)
    y[3] = 1.0

    def rhs(t, state):
        quat = state[3:7] / np.linalg.norm(state[3:7])
        q, qd = q_nom(t), qd_nom(t)
        wheel_h, _ = _wheel_allocation(dyn, q, qd, capacity)
        vb, _, _ = _sample_ledger(dyn, q, qd, wheel_h)
        rdot = q_to_R(quat).as_matrix() @ vb[:3]
        return np.concatenate((rdot, _quat_rhs(quat, vb[3:])))

    hist = np.zeros((n, 7))
    hist[0] = y
    for i in range(n - 1):
        y = _midpoint_step(rhs, ts[i], y, dt)
        hist[i + 1] = y
    return ts, hist


def _joint_margin(dyn, q_hist):
    margins = []
    for i, joint in enumerate(dyn.arm.joints):
        if joint["lower"] is not None:
            margins.append(q_hist[:, i] - float(joint["lower"]))
        if joint["upper"] is not None:
            margins.append(float(joint["upper"]) - q_hist[:, i])
    return float(np.min(np.vstack(margins)))


def evaluate_maneuver(cfg: dict, maneuver_id: str) -> tuple[list[dict], list[dict]]:
    stage = cfg["stage_a"]
    spec = stage["maneuvers"][maneuver_id]
    q_start = np.deg2rad(np.asarray(spec["q_start_deg"], dtype=float))
    q_end = np.deg2rad(np.asarray(spec["q_end_deg"], dtype=float))
    t_m = float(stage["maneuver_duration_s"])
    t_end = float(stage["end_time_s"])
    dt = float(stage["time_step_s"])
    q_nom, qd_nom = _nominal_functions(q_start, q_end, t_m)
    dyn = FreeFloatingB601()
    capacity = np.asarray(stage["A2"]["wheel_capacity_per_axis_Nms"], dtype=float)
    tol = float(cfg["gates"]["attribution_abs"])

    # A0 uses the frozen sim_05 integrator, so the headline anchor is an identity.
    n = int(round(t_end / dt)) + 1
    a0 = dyn.integrate_trajectory(q_nom, qd_nom, t_end, n_out=n)
    cases = {
        "A0_no_compensation": {
            "t": a0["t"],
            "r": a0["r"],
            "Q": a0["Q"],
            "q": np.array([q_nom(t) for t in a0["t"]]),
            "qd": np.array([qd_nom(t) for t in a0["t"]]),
        }
    }

    ts1, pose1, q1, qd1, i_switch = _integrate_a1(dyn, q_start, q_end, qd_nom, stage)
    cases["A1_reaction_trajectory"] = {
        "t": ts1,
        "r": pose1[:, :3],
        "Q": pose1[:, 3:7],
        "q": q1,
        "qd": qd1,
        "i_switch": i_switch,
    }

    ts2, h2 = _integrate_a2(dyn, q_nom, qd_nom, capacity, dt, t_end)
    cases["A2_arm_wheel_coordination"] = {
        "t": ts2,
        "r": h2[:, :3],
        "Q": h2[:, 3:7],
        "q": np.array([q_nom(t) for t in ts2]),
        "qd": np.array([qd_nom(t) for t in ts2]),
    }

    summaries, timeseries = [], []
    nominal_final = dyn.arm.fk(q_end)["T_E"][:3, 3]
    for controller, data in cases.items():
        wheel_hist, wheel_unclipped_hist = [], []
        vb_hist, total_hist, exchange_hist, reaction_hist = [], [], [], []
        for t, q, qd in zip(data["t"], data["q"], data["qd"]):
            if controller == "A2_arm_wheel_coordination":
                wheel_h, wheel_unclipped = _wheel_allocation(dyn, q, qd, capacity)
            else:
                wheel_h = np.zeros(3)
                wheel_unclipped = np.zeros(3)
            vb, body, total = _sample_ledger(dyn, q, qd, wheel_h)
            hbb, hbm = dyn.momentum_matrices(q)
            reaction_map = np.linalg.solve(hbb, hbm)[3:, :]
            wheel_hist.append(wheel_h)
            wheel_unclipped_hist.append(wheel_unclipped)
            vb_hist.append(vb)
            total_hist.append(total)
            exchange_hist.append(body[3:] + wheel_h)
            reaction_hist.append(reaction_map @ qd)
        wheel_hist = np.asarray(wheel_hist)
        wheel_unclipped_hist = np.asarray(wheel_unclipped_hist)
        vb_hist = np.asarray(vb_hist)
        total_hist = np.asarray(total_hist)
        exchange_hist = np.asarray(exchange_hist)
        reaction_hist = np.asarray(reaction_hist)
        dev = np.array([attitude_angle_deg(q) for q in data["Q"]])
        ee_final = dyn.arm.fk(data["q"][-1])["T_E"][:3, 3]
        internal_motion = bool(np.max(np.abs(data["qd"])) > tol)
        attribution = classify_attribution(
            np.zeros(3), wheel_hist[np.argmax(np.linalg.norm(wheel_hist, axis=1))],
            internal_motion, tol
        )
        max_axis = float(np.max(np.abs(wheel_hist)))
        unclipped_max_axis = float(np.max(np.abs(wheel_unclipped_hist)))
        summary = {
            "phase": "A",
            "maneuver": maneuver_id,
            "controller": controller,
            "evaluation_status": "EVALUATED",
            "control_action": "NONE" if controller.startswith("A0") else "ACTIVE",
            "attribution": attribution,
            "peak_base_dev_angle_deg": float(np.max(dev)),
            "final_base_dev_angle_deg": float(dev[-1]),
            "ee_endpoint_degradation_S_mm": float(np.linalg.norm(ee_final - nominal_final) * 1e3),
            "joint_endpoint_error_max_deg": float(
                np.max(np.abs(np.rad2deg(data["q"][-1] - q_end)))
            ),
            "joint_limit_margin_min_rad": _joint_margin(dyn, data["q"]),
            "wheel_peak_axis_Nms": max_axis,
            "wheel_unclipped_peak_axis_Nms": unclipped_max_axis,
            "wheel_box_utilization_max": max_axis / float(np.max(capacity)),
            "wheel_legacy_scalar_utilization": float(
                np.max(np.linalg.norm(wheel_hist, axis=1))
                / float(stage["A2"]["legacy_scalar_sum_Nms"])
            ),
            "wheel_saturated": bool(
                np.any(np.abs(wheel_unclipped_hist) >= capacity - 1e-12)
            ),
            "reaction_map_residual_max": float(
                np.max(np.linalg.norm(reaction_hist, axis=1))
            ),
            "momentum_conservation_max_abs": float(np.max(np.abs(total_hist))),
            "wheel_body_exchange_max_abs": float(np.max(np.abs(exchange_hist))),
            "external_angular_impulse_Nms": 0.0,
            "flex_status": "UNKNOWN_NOT_IN_CRITERIA",
            "model_fidelity": (
                stage["A2"]["fidelity_note"]
                if controller == "A2_arm_wheel_coordination"
                else "L0_MOMENTUM"
            ),
        }
        if controller == "A1_reaction_trajectory":
            i_switch = data["i_switch"]
            summary["a1_design"] = {
                "segments": 2,
                "t_switch_s": float(stage["A1"]["t_switch_s"]),
                "closure": stage["A1"]["closure"],
                "endpoint_policy": stage["A1"]["endpoint_policy"],
            }
            summary["reaction_projected_segment_residual_max"] = float(
                np.max(np.linalg.norm(reaction_hist[: i_switch + 1], axis=1))
            )
        task_complete = summary["joint_endpoint_error_max_deg"] <= 1e-6
        summary["task_endpoint_completed"] = task_complete
        summary["method_result"] = (
            "TASK_COMPLETED"
            if task_complete
            else "MACHINE_REJECTED_TASK_NOT_COMPLETED"
        )
        summaries.append(summary)
        for i, t in enumerate(data["t"]):
            timeseries.append(
                {
                    "phase": "A",
                    "maneuver": maneuver_id,
                    "controller": controller,
                    "t_s": float(t),
                    "base_dev_angle_deg": float(dev[i]),
                    "base_rate_norm_dps": float(
                        np.rad2deg(np.linalg.norm(vb_hist[i, 3:]))
                    ),
                    "wheel_h_x_Nms": float(wheel_hist[i, 0]),
                    "wheel_h_y_Nms": float(wheel_hist[i, 1]),
                    "wheel_h_z_Nms": float(wheel_hist[i, 2]),
                    "momentum_residual": float(np.max(np.abs(total_hist[i]))),
                }
            )

    summaries.append(
        {
            "phase": "A",
            "maneuver": maneuver_id,
            "controller": "A3_arm_wheel_thruster",
            "evaluation_status": stage["A3"]["evaluation_status"],
            "control_action": "NOT_EVALUATED",
            "attribution": None,
            "missing_frozen_inputs": stage["A3"]["missing_frozen_inputs"],
            "claim_forbidden": True,
            "flex_status": "UNKNOWN_NOT_IN_CRITERIA",
        }
    )
    return summaries, timeseries


def run_phase_a(cfg: dict) -> tuple[list[dict], list[dict]]:
    summaries, timeseries = [], []
    for maneuver_id in cfg["stage_a"]["maneuvers"]:
        s, t = evaluate_maneuver(cfg, maneuver_id)
        summaries.extend(s)
        timeseries.extend(t)
    return summaries, timeseries
