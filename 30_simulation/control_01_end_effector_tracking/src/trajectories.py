"""Preregistered T1-T3 references with an explicit frame contract.

CTRL-01-R (repeat preregistration R-2): T3 no longer starts from
T2.q_initial_rad. Each method's T3 starts from that method's frozen T2 state
at t = 15 s (base position/attitude, joint angles and rates, modal state) and
the target continues the frozen sim09 const-omega 3 deg/s propagation, so the
T3-local time t maps to absolute target phase omega * (15 s + t).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np
from scipy.integrate import solve_ivp
from scipy.spatial.transform import Rotation

from repo_imports import q_to_R, qmult, quintic


@dataclass
class ReferenceTrajectory:
    trajectory_id: str
    t: np.ndarray
    position_I: np.ndarray
    rotation_IE: np.ndarray
    twist_I: np.ndarray
    theta_initial: np.ndarray
    theta_nominal: np.ndarray | None
    open_loop: dict
    theta_dot_initial: np.ndarray | None = None
    base_position_initial: np.ndarray | None = None
    base_quaternion_initial: np.ndarray | None = None
    eta_initial: np.ndarray | None = None
    eta_dot_initial: np.ndarray | None = None
    t_offset_s: float = 0.0
    freeze_time_s: float | None = None
    trigger: dict = field(default_factory=dict)

    def sample(self, index: int) -> dict:
        return {
            "position_I": self.position_I[index],
            "rotation_IE": self.rotation_IE[index],
            "twist_I": self.twist_I[index],
        }


def _pose_inertial(model, theta, r_base_I, quat_BI):
    R_IB = q_to_R(quat_BI).as_matrix()
    T_E_S = model.arm.fk(theta)["T_E"]
    return (
        np.asarray(r_base_I) + R_IB @ T_E_S[:3, 3],
        R_IB @ T_E_S[:3, :3],
    )


def _dev_angle_deg(quat: np.ndarray) -> float:
    return math.degrees(2.0 * math.acos(float(np.clip(abs(quat[0]), 0.0, 1.0))))


def _time_grid(total_s: float, dt: float) -> np.ndarray:
    steps = int(round(float(total_s) / float(dt)))
    if not np.isclose(steps * dt, total_s, atol=1e-12):
        raise ValueError("trajectory duration must be an integer number of steps")
    return np.arange(steps + 1, dtype=float) * float(dt)


def build_t1_reference(
    plant,
    cfg: dict,
    slow_model=None,
    rtol: float = 1e-11,
    atol: float = 1e-13,
) -> ReferenceTrajectory:
    """Compose A1 base motion and FK into an inertial reference path.

    CTRL-01-R: the open-loop A1 propagation now uses the same solver-grade
    integration as the closed-loop ledger (adaptive DOP853 on the reduced
    zero-momentum manifold) instead of the v0 first-order fixed-step map.
    The pure S-frame FK path is intentionally not returned as the J* reference.
    """
    dt = float(cfg["controller"]["sample_period_s"])
    tc = cfg["trajectories"]["T1"]
    t_grid = _time_grid(tc["duration_total_s"], dt)
    q0 = np.asarray(tc["q_start_rad"], dtype=float)
    q1 = np.deg2rad(np.asarray(tc["q_end_deg"], dtype=float))
    move_s = float(tc["duration_move_s"])
    n = len(t_grid)
    m2 = 2 * plant.n_modes

    def rhs(t, y):
        theta, theta_dot, theta_ddot = quintic(t, move_s, q0, q1)
        quat = y[3:7]
        eta = y[7:7 + m2]
        etad = y[7 + m2:7 + 2 * m2]
        qn = quat / np.linalg.norm(quat)
        geo = plant.geometry(theta, eta)
        A = geo["A"]
        rate_m = np.concatenate([theta_dot, etad])
        Vb = -np.linalg.solve(A[:, :6], A[:, 6:] @ rate_m)
        u = np.concatenate([Vb, theta_dot, etad])
        udot, _ = plant.accelerations(theta, eta, u, theta_ddot, geo=geo)
        Rb = q_to_R(qn).as_matrix()
        dy = np.empty_like(y)
        dy[0:3] = Rb @ Vb[:3]
        dy[3:7] = 0.5 * qmult(qn, np.array([0.0, *Vb[3:6]]))
        dy[7:7 + m2] = etad
        dy[7 + m2:7 + 2 * m2] = udot[plant.i_e]
        return dy

    y0 = np.concatenate([np.zeros(3), [1.0, 0.0, 0.0, 0.0], np.zeros(2 * m2)])
    sol = solve_ivp(
        rhs,
        (0.0, float(t_grid[-1])),
        y0,
        t_eval=t_grid,
        method="DOP853",
        rtol=rtol,
        atol=atol,
    )
    assert sol.success, sol.message

    position = np.zeros((n, 3))
    rotation = np.zeros((n, 3, 3))
    twist = np.zeros((n, 6))
    theta_hist = np.zeros((n, 6))
    dev = np.zeros(n)
    momentum_residual = np.zeros(n)
    momentum_model = slow_model if slow_model is not None else plant
    for k, t in enumerate(t_grid):
        theta, theta_dot, _ = quintic(t, move_s, q0, q1)
        theta_hist[k] = theta
        r = sol.y[0:3, k]
        quat = sol.y[3:7, k]
        quat = quat / np.linalg.norm(quat)
        eta = sol.y[7:7 + m2, k]
        etad = sol.y[7 + m2:7 + 2 * m2, k]
        R_IB = q_to_R(quat).as_matrix()
        T_E_S = plant.arm.fk(theta)["T_E"]
        position[k] = r + R_IB @ T_E_S[:3, 3]
        rotation[k] = R_IB @ T_E_S[:3, :3]
        A = plant.geometry(theta, eta)["A"]
        rate_m = np.concatenate([theta_dot, etad])
        Vb = -np.linalg.solve(A[:, :6], A[:, 6:] @ rate_m)
        Jstar = plant.generalized_jacobian(theta, eta)
        twist_S = Jstar @ rate_m
        twist[k, :3] = R_IB @ twist_S[:3]
        twist[k, 3:] = R_IB @ twist_S[3:]
        u = np.concatenate([Vb, theta_dot, etad])
        h_I = momentum_model.momentum_inertial(r, quat, theta, eta, u)
        momentum_residual[k] = float(np.max(np.abs(h_I)))
        dev[k] = _dev_angle_deg(quat)

    return ReferenceTrajectory(
        trajectory_id="T1",
        t=t_grid,
        position_I=position,
        rotation_IE=rotation,
        twist_I=twist,
        theta_initial=q0,
        theta_nominal=theta_hist,
        open_loop={
            "peak_base_attitude_deviation_deg": float(np.max(dev)),
            "momentum_max_abs": float(np.max(momentum_residual)),
            "integrator": "reduced_momentum_DOP853_adaptive",
            "rtol": rtol,
            "atol": atol,
            "sample_period_s": dt,
        },
    )


def build_t2_reference(model, cfg: dict) -> ReferenceTrajectory:
    dt = float(cfg["controller"]["sample_period_s"])
    tc = cfg["trajectories"]["T2"]
    t_grid = _time_grid(tc["duration_total_s"], dt)
    theta0 = np.asarray(tc["q_initial_rad"], dtype=float)
    p0, R0 = _pose_inertial(
        model, theta0, np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0])
    )
    expected_capture = np.asarray(tc["capture_point_S_m"], dtype=float)
    if np.linalg.norm(p0 - expected_capture) > 1e-6:
        raise ValueError("frozen T2 IK start no longer matches capture_point_S")
    axis = np.asarray(tc["target_tumble_axis_inertial"], dtype=float)
    axis /= np.linalg.norm(axis)
    omega = math.radians(float(tc["target_tumble_rate_before_capture_deg_per_s"]))
    position = np.repeat(p0[None, :], len(t_grid), axis=0)
    rotation = np.zeros((len(t_grid), 3, 3))
    twist = np.zeros((len(t_grid), 6))
    for k, t in enumerate(t_grid):
        rotation[k] = Rotation.from_rotvec(axis * omega * t).as_matrix() @ R0
        twist[k, 3:] = axis * omega
    trigger_time = float(
        cfg["trajectories"]["T3"]["trigger"]["time_s"]
    )
    return ReferenceTrajectory(
        trajectory_id="T2",
        t=t_grid,
        position_I=position,
        rotation_IE=rotation,
        twist_I=twist,
        theta_initial=theta0,
        theta_nominal=None,
        freeze_time_s=trigger_time,
        open_loop={
            "target_tumble_rate_before_capture_deg_per_s": float(
                tc["target_tumble_rate_before_capture_deg_per_s"]
            ),
            "stationkept_capture_point": bool(tc["stationkept_capture_point"]),
            "t3_trigger_freeze_time_s": trigger_time,
        },
    )


def build_t3_reference(model, cfg: dict, snapshot: dict) -> ReferenceTrajectory:
    """Emergency retreat from the method-specific frozen T2 t=15 s state.

    snapshot: dict with keys t_abs_s, theta, theta_dot, base_position_I,
    base_quaternion_BI, eta, eta_dot -- the full state frozen at the trigger.
    The retreat rule is the frozen v0 rule evaluated at the trigger pose:
    quintic 0.5 m along the negative current tool approach axis, orientation
    held at the trigger orientation.
    """
    dt = float(cfg["controller"]["sample_period_s"])
    tc = cfg["trajectories"]["T3"]
    trigger_cfg = tc["trigger"]
    expected_time = float(trigger_cfg["time_s"])
    if not np.isclose(float(snapshot["t_abs_s"]), expected_time, atol=1e-12):
        raise ValueError(
            "T3 snapshot time does not match the frozen trigger contract"
        )
    t_grid = _time_grid(tc["duration_total_s"], dt)
    theta0 = np.asarray(snapshot["theta"], dtype=float)
    r0 = np.asarray(snapshot["base_position_I"], dtype=float)
    quat0 = np.asarray(snapshot["base_quaternion_BI"], dtype=float)
    p0, R0 = _pose_inertial(model, theta0, r0, quat0)
    direction = -R0[:, 2]
    move_s = float(tc["duration_move_s"])
    distance = float(tc["retreat_distance_m"])
    position = np.zeros((len(t_grid), 3))
    rotation = np.repeat(R0[None, :, :], len(t_grid), axis=0)
    twist = np.zeros((len(t_grid), 6))
    for k, t in enumerate(t_grid):
        s, sd, _ = quintic(t, move_s, np.array([0.0]), np.array([distance]))
        position[k] = p0 + direction * float(s[0])
        twist[k, :3] = direction * float(sd[0])
    return ReferenceTrajectory(
        trajectory_id="T3",
        t=t_grid,
        position_I=position,
        rotation_IE=rotation,
        twist_I=twist,
        theta_initial=theta0,
        theta_nominal=None,
        theta_dot_initial=np.asarray(snapshot["theta_dot"], dtype=float),
        base_position_initial=r0,
        base_quaternion_initial=quat0,
        eta_initial=np.asarray(snapshot["eta"], dtype=float),
        eta_dot_initial=np.asarray(snapshot["eta_dot"], dtype=float),
        t_offset_s=expected_time,
        trigger={
            "source": str(trigger_cfg["source"]),
            "time_s": expected_time,
            "method_specific": bool(trigger_cfg["method_specific"]),
            "target_phase_continuation": bool(
                trigger_cfg["target_phase_continuation"]
            ),
            "retreat_start_position_I_m": p0.tolist(),
            "retreat_direction_I": direction.tolist(),
        },
        open_loop={
            "retreat_distance_m": distance,
            "move_duration_s": move_s,
            "trigger_time_s": expected_time,
        },
    )
