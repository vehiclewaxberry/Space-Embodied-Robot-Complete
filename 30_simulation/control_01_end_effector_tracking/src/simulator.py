"""Sampled-data closed-loop plant with a solver-grade energy ledger.

CTRL-01-R energy-audit remediation (repeat preregistration item 4):
the v0 loop already contained W_ctrl = int tau.theta_dot dt, but the ledger
was accumulated with a first-order rectangle rule over a first-order state
map, so the audit compared inconsistently discretized quantities and the
residual (7.9e-2) measured integrator defect, not physics. The fix keeps the
frozen 1e-9 threshold and makes the ledger self-consistent:

  * the commanded joint rate is applied as a first-order hold (velocity ramps
    linearly to the command over one 10 ms sample; theta_ddot is constant per
    interval) so the hybrid system is smooth in every interval and the
    continuous energy theorem d(T+U)/dt = tau.theta_dot - eta_dot^T D eta_dot
    holds exactly;
  * within each interval the state (r, quat, eta, eta_dot) AND the ledger
    integrals (W_joint, E_damp) are propagated together by adaptive DOP853
    at rtol 1e-11 / atol 1e-13 on the reduced zero-momentum manifold, the
    sim_11-proven audit pattern;
  * the plant evaluations use the machine-cross-checked FastPlant equal-output
    path (fail-closed against the frozen sim_11 SSOT).
"""
from __future__ import annotations

import math
import time

import numpy as np
from scipy.integrate import solve_ivp

from collision_evidence import (
    CollisionEvidenceUnavailable,
    evaluate_t3_collision,
)
from contracts import joint_limits
from controller import ResolvedRateController
from repo_imports import q_to_R, qmult


LEDGER_RTOL = 1e-11
LEDGER_ATOL = 1e-13
LEDGER_INTEGRATOR = "per_interval_DOP853_reduced_momentum_FOH"


def _dev_angle_deg(quat: np.ndarray) -> float:
    return math.degrees(2.0 * math.acos(float(np.clip(abs(quat[0]), 0.0, 1.0))))


def _ee_pose(plant, theta, r_I, quat):
    R_IB = q_to_R(quat).as_matrix()
    T_E_S = plant.arm.fk(theta)["T_E"]
    return (
        R_IB,
        r_I + R_IB @ T_E_S[:3, 3],
        R_IB @ T_E_S[:3, :3],
    )


def run_closed_loop(plant, cfg: dict, method: str, task_mode: str, reference):
    """plant: FastPlant (cross-checked equal-output path of sim_11)."""
    dt = float(cfg["controller"]["sample_period_s"])
    controller = ResolvedRateController(plant, cfg, method, task_mode)
    t_grid = reference.t
    n = len(t_grid)
    m2 = 2 * plant.n_modes
    theta = reference.theta_initial.copy()
    theta_dot_achieved = (
        reference.theta_dot_initial.copy()
        if reference.theta_dot_initial is not None
        else np.zeros(6)
    )
    r_base = (
        reference.base_position_initial.copy()
        if reference.base_position_initial is not None
        else np.zeros(3)
    )
    quat = (
        reference.base_quaternion_initial.copy()
        if reference.base_quaternion_initial is not None
        else np.array([1.0, 0.0, 0.0, 0.0])
    )
    quat = quat / np.linalg.norm(quat)
    eta = (
        reference.eta_initial.copy()
        if reference.eta_initial is not None
        else np.zeros(m2)
    )
    eta_dot = (
        reference.eta_dot_initial.copy()
        if reference.eta_dot_initial is not None
        else np.zeros(m2)
    )
    lo, hi = joint_limits(plant.arm)

    theta_hist = np.zeros((n, 6))
    base_position_hist = np.zeros((n, 3))
    base_quaternion_hist = np.zeros((n, 4))
    theta_dot_hist = np.zeros((n, 6))
    theta_ddot_hist = np.zeros((n, 6))
    torque_hist = np.zeros((n, 6))
    pos_error = np.zeros(n)
    ori_error = np.zeros(n)
    sigma_min = np.zeros(n)
    condition = np.zeros(n)
    dev_angle = np.zeros(n)
    base_omega = np.zeros((n, 3))
    momentum_residual = np.zeros(n)
    energy = np.zeros(n)
    work = np.zeros(n)
    damping = np.zeros(n)
    tip = np.zeros((n, 2))
    modal_energy = np.zeros(n)
    nullity = np.zeros(n, dtype=int)
    null_active = np.zeros(n, dtype=bool)
    null_fade = np.zeros(n)
    null_leak = np.zeros(n)
    reaction_primary = np.zeros(n)
    reaction_command = np.zeros(n)
    feedforward_norm = np.zeros(n)
    step_wall = np.zeros(n)
    ledger_nfev = 0

    def base_velocity(geo, theta_dot_val, eta_dot_val):
        A = geo["A"]
        rate_m = np.concatenate([theta_dot_val, eta_dot_val])
        return -np.linalg.solve(A[:, :6], A[:, 6:] @ rate_m)

    freeze_time = reference.freeze_time_s
    snapshot = None
    work_running = 0.0
    damping_running = 0.0

    started = time.perf_counter()
    for k in range(n):
        step_started = time.perf_counter()
        # ---- node state records (velocity is the achieved, continuous one) ---
        geo = plant.geometry(theta, eta)
        Vb = base_velocity(geo, theta_dot_achieved, eta_dot)
        u = np.concatenate([Vb, theta_dot_achieved, eta_dot])
        h_I = plant.momentum_inertial(r_base, quat, theta, eta, u)
        energy[k] = plant.kinetic_energy(theta, eta, u) + plant.strain_energy(eta)
        work[k] = work_running
        damping[k] = damping_running
        theta_hist[k] = theta
        base_position_hist[k] = r_base
        base_quaternion_hist[k] = quat
        dev_angle[k] = _dev_angle_deg(quat)
        base_omega[k] = Vb[3:]
        momentum_residual[k] = float(np.max(np.abs(h_I)))
        modal_energy[k] = plant.strain_energy(eta)
        if plant.n_modes:
            tip[k, 0] = plant.panels[0].tip_deflection(eta[: plant.n_modes])
            tip[k, 1] = plant.panels[1].tip_deflection(eta[plant.n_modes:])
        if (
            freeze_time is not None
            and snapshot is None
            and np.isclose(t_grid[k], freeze_time, rtol=0.0, atol=1e-9)
        ):
            snapshot = {
                "t_abs_s": float(t_grid[k]),
                "theta": theta.copy(),
                "theta_dot": theta_dot_achieved.copy(),
                "base_position_I": r_base.copy(),
                "base_quaternion_BI": quat.copy(),
                "eta": eta.copy(),
                "eta_dot": eta_dot.copy(),
            }

        # ---- controller sample -----------------------------------------------
        R_IB, p_E_I, R_IE = _ee_pose(plant, theta, r_base, quat)
        output = controller.command(
            theta,
            eta,
            eta_dot,
            R_IB,
            p_E_I,
            R_IE,
            reference.sample(k),
        )
        theta_dot_cmd = output.theta_dot_command
        theta_ddot = (theta_dot_cmd - theta_dot_achieved) / dt
        pos_error[k] = output.position_error_m
        ori_error[k] = output.orientation_error_rad
        sigma_min[k] = output.task_sigma_min
        condition[k] = output.task_condition
        nullity[k] = output.task_nullity
        null_active[k] = output.nullspace_active
        null_fade[k] = output.nullspace_fade
        null_leak[k] = output.nullspace_leakage
        reaction_primary[k] = output.reaction_primary_norm
        reaction_command[k] = output.reaction_command_norm
        feedforward_norm[k] = output.feedforward_norm
        theta_dot_hist[k] = theta_dot_cmd
        theta_ddot_hist[k] = theta_ddot
        _, torque_start = plant.accelerations(theta, eta, u, theta_ddot, geo=geo)
        torque_hist[k] = torque_start

        if k == n - 1:
            step_wall[k] = time.perf_counter() - step_started
            break

        # ---- interval propagation with the ledger (FOH ramp) ------------------
        theta_node = theta.copy()
        theta_dot_node = theta_dot_achieved.copy()

        def rhs(t, y):
            th = theta_node + theta_dot_node * t + 0.5 * theta_ddot * t * t
            thd = theta_dot_node + theta_ddot * t
            quat_y = y[3:7]
            eta_y = y[7:7 + m2]
            etad_y = y[7 + m2:7 + 2 * m2]
            qn = quat_y / np.linalg.norm(quat_y)
            geo_y = plant.geometry(th, eta_y)
            Vb_y = base_velocity(geo_y, thd, etad_y)
            u_y = np.concatenate([Vb_y, thd, etad_y])
            udot_y, tau_y = plant.accelerations(
                th, eta_y, u_y, theta_ddot, geo=geo_y
            )
            Rb = q_to_R(qn).as_matrix()
            dy = np.empty_like(y)
            dy[0:3] = Rb @ Vb_y[:3]
            dy[3:7] = 0.5 * qmult(qn, np.array([0.0, *Vb_y[3:6]]))
            dy[7:7 + m2] = etad_y
            dy[7 + m2:7 + 2 * m2] = udot_y[plant.i_e]
            dy[7 + 2 * m2] = float(tau_y @ thd)
            dy[8 + 2 * m2] = (
                float(etad_y @ (plant.D_eta @ etad_y)) if m2 else 0.0
            )
            return dy

        y0 = np.concatenate(
            [r_base, quat, eta, eta_dot, [work_running, damping_running]]
        )
        sol = solve_ivp(
            rhs,
            (0.0, dt),
            y0,
            method="DOP853",
            rtol=LEDGER_RTOL,
            atol=LEDGER_ATOL,
        )
        assert sol.success, sol.message
        ledger_nfev += int(sol.nfev)
        y_end = sol.y[:, -1]
        r_base = y_end[0:3].copy()
        quat = y_end[3:7] / np.linalg.norm(y_end[3:7])
        eta = y_end[7:7 + m2].copy()
        eta_dot = y_end[7 + m2:7 + 2 * m2].copy()
        work_running = float(y_end[7 + 2 * m2])
        damping_running = float(y_end[8 + 2 * m2])
        theta = theta_node + theta_dot_node * dt + 0.5 * theta_ddot * dt * dt
        theta_dot_achieved = theta_dot_cmd.copy()
        step_wall[k] = time.perf_counter() - step_started

    runtime = time.perf_counter() - started
    audit = np.abs(work - (energy - energy[0]) - damping)
    energy_scale = max(
        float(np.max(np.abs(work))),
        float(np.max(np.abs(energy))),
        1e-15,
    )
    position_bound = (
        float(cfg["analytic_error_bounds"]["position_disturbance_bound_m_per_s"])
        / float(cfg["controller"]["position_gain_per_s"])
        + float(cfg["analytic_error_bounds"]["sampling_position_allowance_m"])
    )
    orientation_bound = (
        float(cfg["analytic_error_bounds"]["orientation_disturbance_bound_rad_per_s"])
        / float(cfg["controller"]["orientation_gain_per_s"])
        + float(cfg["analytic_error_bounds"]["sampling_orientation_allowance_rad"])
    )
    joint_margin = np.min(
        np.minimum(theta_hist - lo[None, :], hi[None, :] - theta_hist)
    )
    collision_result = None
    if reference.trajectory_id == "T3":
        try:
            collision_result = evaluate_t3_collision(
                plant,
                cfg,
                t_grid,
                theta_hist,
                base_position_hist,
                base_quaternion_hist,
                t_offset_s=float(reference.t_offset_s),
            )
        except CollisionEvidenceUnavailable as exc:
            collision_result = {
                "evaluation_status": "NOT_EVALUATED",
                "plan_contract_status": "FROZEN_INPUT_UNAVAILABLE",
                "static_evaluation_status": "NOT_EVALUATED",
                "target_evaluation_status": "NOT_EVALUATED",
                "combined_evaluation_status": "NOT_EVALUATED",
                "not_evaluated_reason": str(exc),
                "static_margin_min_m": None,
                "static_margin_t_at_min_s": None,
                "target_margin_min_m": None,
                "target_margin_t_at_min_s": None,
                "combined_margin_min_m": None,
                "combined_margin_t_at_min_s": None,
                "time_samples": int(n),
                "time_step_s": dt,
                "static_time_coverage": "NONE_FROZEN_INPUT_UNAVAILABLE",
                "target_time_coverage": "NONE_FROZEN_INPUT_UNAVAILABLE",
                "between_node_coverage": "NOT_GUARANTEED",
                "t_s": np.asarray(t_grid, dtype=float),
                "static_margin_m": None,
                "target_margin_m": None,
                "combined_margin_m": None,
            }
    collision_scalar = collision_result or {
        "evaluation_status": "NOT_APPLICABLE",
        "plan_contract_status": "NOT_APPLICABLE",
        "static_evaluation_status": "NOT_APPLICABLE",
        "target_evaluation_status": "NOT_APPLICABLE",
        "combined_evaluation_status": "NOT_APPLICABLE",
        "not_evaluated_reason": "",
        "static_margin_min_m": None,
        "static_margin_t_at_min_s": None,
        "target_margin_min_m": None,
        "target_margin_t_at_min_s": None,
        "combined_margin_min_m": None,
        "combined_margin_t_at_min_s": None,
        "time_samples": 0,
        "time_step_s": None,
        "static_time_coverage": "NOT_APPLICABLE",
        "target_time_coverage": "NOT_APPLICABLE",
        "between_node_coverage": "NOT_APPLICABLE",
    }
    summary = {
        "method": method,
        "task_mode": task_mode,
        "trajectory": reference.trajectory_id,
        "n_steps": int(n),
        "sample_period_s": dt,
        "position_error_rms_m": float(np.sqrt(np.mean(pos_error**2))),
        "position_error_p95_m": float(np.quantile(pos_error, 0.95)),
        "position_error_max_m": float(np.max(pos_error)),
        "orientation_error_rms_rad": float(np.sqrt(np.mean(ori_error**2))),
        "orientation_error_p95_rad": float(np.quantile(ori_error, 0.95)),
        "orientation_error_max_rad": float(np.max(ori_error)),
        "base_attitude_peak_deg": float(np.max(dev_angle)),
        "base_omega_integral_deg": float(
            np.degrees(np.sum(np.linalg.norm(base_omega, axis=1)) * dt)
        ),
        "joint_speed_max_radps": float(np.max(np.abs(theta_dot_hist))),
        "joint_acceleration_max_radps2": float(np.max(np.abs(theta_ddot_hist))),
        "joint_torque_max_Nm": float(np.max(np.abs(torque_hist))),
        "joint_limit_margin_min_rad": float(joint_margin),
        "task_sigma_min": float(np.min(sigma_min)),
        "task_condition_max": float(np.max(condition)),
        "momentum_max_abs": float(np.max(momentum_residual)),
        "energy_audit_relative": float(np.max(audit) / energy_scale),
        "energy_audit_abs_J": float(np.max(audit)),
        "energy_scale_J": float(energy_scale),
        "ledger_integrator": LEDGER_INTEGRATOR,
        "ledger_rtol": LEDGER_RTOL,
        "ledger_atol": LEDGER_ATOL,
        "ledger_nfev_total": int(ledger_nfev),
        "panel_tip_peak_mm": float(np.max(np.abs(tip)) * 1000.0),
        "panel_modal_energy_peak_J": float(np.max(modal_energy)),
        "panel_modal_energy_final_J": float(modal_energy[-1]),
        "panel_metrics_status": "PROVISIONAL",
        "mean_step_wall_ms": float(np.mean(step_wall) * 1000.0),
        "max_step_wall_ms": float(np.max(step_wall) * 1000.0),
        "runtime_s": float(runtime),
        "real_time_ratio": float(dt / max(np.mean(step_wall), 1e-15)),
        "analytic_position_bound_m": float(position_bound),
        "analytic_orientation_bound_rad": float(orientation_bound),
        "nullity_one_fraction": float(np.mean(nullity == 1)),
        "nullspace_active_fraction": float(np.mean(null_active)),
        "nullspace_fade_fraction": float(np.mean(null_fade < 1.0)),
        "nullspace_leakage_max": float(np.max(null_leak)),
        "reaction_primary_peak": float(np.max(reaction_primary)),
        "reaction_command_peak": float(np.max(reaction_command)),
        "reference_feedforward_peak": float(np.max(feedforward_norm)),
        "t3_collision_margin_min_m": collision_scalar[
            "combined_margin_min_m"
        ],
        "t3_collision_static_margin_min_m": collision_scalar[
            "static_margin_min_m"
        ],
        "t3_collision_static_t_at_min_s": collision_scalar[
            "static_margin_t_at_min_s"
        ],
        "t3_collision_target_margin_min_m": collision_scalar[
            "target_margin_min_m"
        ],
        "t3_collision_target_t_at_min_s": collision_scalar[
            "target_margin_t_at_min_s"
        ],
        "t3_collision_combined_margin_min_m": collision_scalar[
            "combined_margin_min_m"
        ],
        "t3_collision_combined_t_at_min_s": collision_scalar[
            "combined_margin_t_at_min_s"
        ],
        "t3_collision_evaluation_status": collision_scalar[
            "evaluation_status"
        ],
        "t3_collision_plan_contract_status": collision_scalar[
            "plan_contract_status"
        ],
        "t3_collision_static_evaluation_status": collision_scalar[
            "static_evaluation_status"
        ],
        "t3_collision_target_evaluation_status": collision_scalar[
            "target_evaluation_status"
        ],
        "t3_collision_combined_evaluation_status": collision_scalar[
            "combined_evaluation_status"
        ],
        "t3_collision_not_evaluated_reason": collision_scalar[
            "not_evaluated_reason"
        ],
        "t3_collision_time_samples": collision_scalar["time_samples"],
        "t3_collision_time_step_s": collision_scalar["time_step_s"],
        "t3_collision_static_time_coverage": collision_scalar[
            "static_time_coverage"
        ],
        "t3_collision_target_time_coverage": collision_scalar[
            "target_time_coverage"
        ],
        "t3_collision_between_node_coverage": collision_scalar[
            "between_node_coverage"
        ],
    }
    histories = {
        "t_s": t_grid,
        "theta_rad": theta_hist,
        "theta_dot_radps": theta_dot_hist,
        "position_error_m": pos_error,
        "orientation_error_rad": ori_error,
        "base_dev_angle_deg": dev_angle,
        "base_omega_radps": base_omega,
        "momentum_abs": momentum_residual,
        "panel_tip_m": tip,
        "panel_modal_energy_J": modal_energy,
        "task_sigma_min": sigma_min,
        "nullity": nullity,
        "nullspace_active": null_active.astype(int),
        "reaction_primary": reaction_primary,
        "reaction_command": reaction_command,
        "base_position_I_m": base_position_hist,
        "base_quaternion_BI": base_quaternion_hist,
        "energy_J": energy,
        "work_J": work,
        "damping_J": damping,
        "energy_audit_abs_J": audit,
        "collision": collision_result,
        "t2_freeze_snapshot": snapshot,
    }
    return summary, histories
