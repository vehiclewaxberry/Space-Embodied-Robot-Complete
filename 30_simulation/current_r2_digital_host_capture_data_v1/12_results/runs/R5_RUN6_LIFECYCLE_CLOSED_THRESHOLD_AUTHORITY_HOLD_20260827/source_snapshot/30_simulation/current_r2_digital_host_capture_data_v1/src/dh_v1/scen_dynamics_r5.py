"""R5 unit-safe S02/S03 dynamics and control diagnostics.

This module is intentionally additive: the immutable R4 source and evidence
remain untouched.  Scope is rigid, no gravity, no contact, no target body,
no reaction-wheel state and no thruster model.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .frames import quat_derivative, quat_normalize, quat_to_R
from .integrators import SolverNonConvergence, pack_state, unpack_state
from .momentum_ledger_r5 import (
    body_momentum_contributions,
    build_unit_safe_ledger,
    compute_preintegration_scales,
    evaluate_momentum_gate_r5,
    evaluate_three_point_convergence,
)


def quintic_reference(t: float, duration_s: float) -> tuple[float, float, float]:
    tau = np.clip(float(t) / float(duration_s), 0.0, 1.0)
    s = 10.0 * tau**3 - 15.0 * tau**4 + 6.0 * tau**5
    sd = (30.0 * tau**2 - 60.0 * tau**3 + 30.0 * tau**4) / duration_s
    sdd = (60.0 * tau - 180.0 * tau**2 + 120.0 * tau**3) / duration_s**2
    return float(s), float(sd), float(sdd)


@dataclass(frozen=True)
class PDControllerR5:
    q_start: np.ndarray
    q_goal: np.ndarray
    Kp: np.ndarray
    Kd: np.ndarray
    Ki: np.ndarray
    effort_caps: np.ndarray
    duration_s: float

    def evaluate(self, t: float, q: np.ndarray, qd: np.ndarray) -> dict:
        """Pure, side-effect-free controller evaluation."""
        s, sd, _ = quintic_reference(t, self.duration_s)
        q_ref = self.q_start + s * (self.q_goal - self.q_start)
        qd_ref = sd * (self.q_goal - self.q_start)
        e = q_ref - q
        de = qd_ref - qd
        effort_P = self.Kp * e
        effort_I = np.zeros_like(e)  # structural zero: PD has no integrator
        effort_D = self.Kd * de
        raw = effort_P + effort_I + effort_D
        limited = np.clip(raw, -self.effort_caps, self.effort_caps)
        at_limit = np.abs(raw) >= self.effort_caps
        clipped = np.abs(raw) > self.effort_caps
        return {
            "q_ref": q_ref,
            "qd_ref": qd_ref,
            "q_error": e,
            "qd_error": de,
            "effort_P": effort_P,
            "effort_I": effort_I,
            "effort_D": effort_D,
            "effort_raw": raw,
            "effort_limited": limited,
            "effort_cap": self.effort_caps,
            "effort_margin": self.effort_caps - np.abs(raw),
            "at_limit": at_limit,
            "was_clipped": clipped,
        }


def controller_from_config(plant, cfg: dict) -> PDControllerR5:
    arrays = {
        key: np.asarray(cfg[key], dtype=float)
        for key in ("Kp", "Kd", "Ki", "expected_effort_caps")
    }
    n = plant.nj
    if any(value.shape != (n,) for value in arrays.values()):
        raise ValueError("controller vectors must match the frozen plant joint count")
    actual_caps = np.asarray(
        [body.limits.get("effort", np.inf) if body.limits else np.inf for body in plant.bodies[1:]],
        dtype=float,
    )
    if not np.array_equal(actual_caps, arrays["expected_effort_caps"]):
        raise ValueError("accepted URDF effort caps do not match frozen controller contract")
    trajectory = cfg["trajectory"]
    q_start = np.asarray(trajectory["q_start"], dtype=float)
    q_goal = np.asarray(trajectory["q_goal"], dtype=float)
    if q_start.shape != (n,) or q_goal.shape != (n,):
        raise ValueError("trajectory endpoints must match the frozen plant joint count")
    return PDControllerR5(
        q_start=q_start,
        q_goal=q_goal,
        Kp=arrays["Kp"],
        Kd=arrays["Kd"],
        Ki=arrays["Ki"],
        effort_caps=actual_caps,
        duration_s=float(trajectory["duration_s"]),
    )


def zero_controller_evaluation(nj: int) -> dict:
    z = np.zeros(nj)
    b = np.zeros(nj, dtype=bool)
    return {
        "q_ref": z.copy(),
        "qd_ref": z.copy(),
        "q_error": z.copy(),
        "qd_error": z.copy(),
        "effort_P": z.copy(),
        "effort_I": z.copy(),
        "effort_D": z.copy(),
        "effort_raw": z.copy(),
        "effort_limited": z.copy(),
        "effort_cap": np.full(nj, np.inf),
        "effort_margin": np.full(nj, np.inf),
        "at_limit": b.copy(),
        "was_clipped": b.copy(),
    }


def _state_derivative(plant, x: np.ndarray, t: float, controller) -> tuple[np.ndarray, dict]:
    p, quat, q, v_base, qd = unpack_state(x, plant.nj)
    qn, _ = quat_normalize(quat)
    R_WB = quat_to_R(qn)
    control = controller.evaluate(t, q, qd) if controller is not None else zero_controller_evaluation(plant.nj)
    udot, _, _ = plant.forward_dynamics(q, v_base, qd, control["effort_limited"])
    derivative = np.concatenate(
        [R_WB @ v_base[3:], quat_derivative(qn, v_base[:3]), qd, udot]
    )
    return derivative, control


def rk4_step_r5(plant, x: np.ndarray, t: float, dt: float, controller=None):
    """Pure one-step map equivalent to the existing fixed-step RK4 scheme."""
    k1, c1 = _state_derivative(plant, x, t, controller)
    k2, c2 = _state_derivative(plant, x + 0.5 * dt * k1, t + 0.5 * dt, controller)
    k3, c3 = _state_derivative(plant, x + 0.5 * dt * k2, t + 0.5 * dt, controller)
    k4, c4 = _state_derivative(plant, x + dt * k3, t + dt, controller)
    x_next = np.asarray(x, dtype=float) + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    if not np.all(np.isfinite(x_next)):
        raise SolverNonConvergence(f"non-finite state at t={t + dt:.9f}s")
    qn, drift = quat_normalize(x_next[3:7])
    x_next[3:7] = qn
    if np.linalg.norm(x_next[7 + plant.nj : 10 + plant.nj]) > 1.0e3:
        raise SolverNonConvergence(f"base angular rate implausible at t={t + dt:.9f}s")
    return x_next, (c1, c2, c3, c4), float(drift)


def _empty_telemetry() -> dict:
    scalar = {"step_index": [], "t_s": [], "dt_s": []}
    vectors = {
        name: []
        for name in (
            "q",
            "qd",
            "q_ref",
            "qd_ref",
            "q_error",
            "qd_error",
            "effort_P",
            "effort_I",
            "effort_D",
            "effort_raw",
            "effort_limited",
            "effort_cap",
            "effort_margin",
            "at_limit",
            "was_clipped",
            "any_stage_clipped",
            "max_abs_stage_effort_raw",
        )
    }
    return {**scalar, **vectors}


def integrate_rk4_r5(
    plant,
    x0: np.ndarray,
    t_end_s: float,
    dt_s: float,
    *,
    controller=None,
    sample_period_target_s: float = 0.05,
    record_controller: bool = False,
) -> tuple[dict, dict]:
    n_steps_float = float(t_end_s) / float(dt_s)
    n_steps = int(round(n_steps_float))
    if not np.isclose(n_steps, n_steps_float, rtol=0.0, atol=1.0e-10):
        raise ValueError("t_end_s must be an integer multiple of dt_s")
    sample_every = max(1, int(round(sample_period_target_s / dt_s)))
    x = np.asarray(x0, dtype=float).copy()
    samples = {
        key: []
        for key in (
            "t",
            "x",
            "h_O",
            "h_C",
            "E",
            "p_com",
            "quat_renorm",
            "P_body_I_kg_m_s",
            "H_spin_body_I_N_m_s",
            "H_orbital_body_O_I_N_m_s",
            "H_body_O_I_N_m_s",
        )
    }
    samples["body_ids"] = [body.name for body in plant.bodies]
    telemetry = _empty_telemetry()
    renorm_acc = 0.0

    def record(t_now: float):
        p, quat, q, v_base, qd = unpack_state(x, plant.nj)
        R_WB = quat_to_R(quat)
        h_O, h_C, p_com, _, energy = plant.momentum_world(R_WB, p, q, v_base, qd)
        body = body_momentum_contributions(plant, R_WB, p, q, v_base, qd)
        samples["t"].append(t_now)
        samples["x"].append(x.copy())
        samples["h_O"].append(h_O)
        samples["h_C"].append(h_C)
        samples["E"].append(energy)
        samples["p_com"].append(p_com)
        samples["quat_renorm"].append(renorm_acc)
        for key in (
            "P_body_I_kg_m_s",
            "H_spin_body_I_N_m_s",
            "H_orbital_body_O_I_N_m_s",
            "H_body_O_I_N_m_s",
        ):
            samples[key].append(body[key])

    record(0.0)
    for step in range(n_steps):
        t = step * dt_s
        p, quat, q, v_base, qd = unpack_state(x, plant.nj)
        x_next, stages, drift = rk4_step_r5(plant, x, t, dt_s, controller)
        if record_controller:
            node = stages[0]
            stage_clipped = np.logical_or.reduce([s["was_clipped"] for s in stages])
            max_abs_stage = np.maximum.reduce([np.abs(s["effort_raw"]) for s in stages])
            telemetry["step_index"].append(step)
            telemetry["t_s"].append(t)
            telemetry["dt_s"].append(dt_s)
            telemetry["q"].append(q.copy())
            telemetry["qd"].append(qd.copy())
            for key in (
                "q_ref",
                "qd_ref",
                "q_error",
                "qd_error",
                "effort_P",
                "effort_I",
                "effort_D",
                "effort_raw",
                "effort_limited",
                "effort_cap",
                "effort_margin",
                "at_limit",
                "was_clipped",
            ):
                telemetry[key].append(node[key].copy())
            telemetry["any_stage_clipped"].append(stage_clipped)
            telemetry["max_abs_stage_effort_raw"].append(max_abs_stage)
        x = x_next
        renorm_acc += drift
        if (step + 1) % sample_every == 0 or step + 1 == n_steps:
            record((step + 1) * dt_s)

    for key in samples:
        if key != "body_ids":
            samples[key] = np.asarray(samples[key])
    samples["_solver_execution"] = {
        "integrator": "FIXED_STEP_CLASSICAL_RK4",
        "dt_s": float(dt_s),
        "t_end_s": float(t_end_s),
        "macro_step_count": n_steps,
        "sample_period_target_s": float(sample_period_target_s),
        "sample_every_macro_steps": sample_every,
        "regular_effective_sample_period_s": float(sample_every * dt_s),
        "final_state_forced_into_samples": bool(n_steps % sample_every != 0),
        "sample_count": len(samples["t"]),
        "quaternion_policy": "RENORMALIZE_AFTER_EACH_MACRO_STEP_WITH_NONIMPULSIVE_AUDIT",
        "adaptive_step": False,
        "arithmetic": "IEEE754_FLOAT64",
    }
    for key in telemetry:
        telemetry[key] = np.asarray(telemetry[key])
    return samples, telemetry


def default_s02_state(plant, initial_condition: str) -> np.ndarray:
    q = np.zeros(plant.nj)
    q[1], q[2], q[3], q[4] = -1.0, -0.8, 0.3, 0.4
    qd = np.array([0.30, -0.20, 0.25, -0.15, 0.20, -0.10, 0.010, 0.010])[: plant.nj]
    if initial_condition == "base_at_rest_arm_moving":
        v6 = np.zeros(6)
    elif initial_condition == "base_tumbling_arm_moving":
        v6 = np.array([0.02, -0.03, 0.05, 0.010, 0.0, -0.005])
    else:
        raise ValueError(f"unknown initial condition {initial_condition!r}")
    return pack_state(np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0]), q, v6, qd)


def _energy_metrics(samples: dict) -> dict:
    E0 = float(samples["E"][0])
    drift = np.abs(samples["E"] - E0)
    return {
        "E0_J": E0,
        "abs_E_drift_max_J": float(np.max(drift)),
        "rel_E_drift_max": float(np.max(drift) / max(abs(E0), 1.0e-9)),
    }


def run_s02_case_r5(plant, case: dict, scenario: dict, gates: dict) -> dict:
    dts = [float(v) for v in scenario["dt_grid_s"]]
    x0 = default_s02_state(plant, case["initial_condition"])
    scales = compute_preintegration_scales(plant, x0, float(scenario["t_end_s"]))
    runs = []
    for dt in dts:
        samples, _ = integrate_rk4_r5(
            plant,
            x0,
            float(scenario["t_end_s"]),
            dt,
            sample_period_target_s=float(scenario["sample_period_target_s"]),
        )
        ledger = build_unit_safe_ledger(
            samples,
            scales,
            np.asarray(scenario["external_force_I_N"], dtype=float),
            np.asarray(scenario["external_torque_about_O_I_Nm"], dtype=float),
            [],
            external_wrench_status=scenario["external_wrench_status"],
            event_monitor_status=scenario["event_monitor_status"],
        )
        pT, quatT, qT, v6T, qdT = unpack_state(samples["x"][-1], plant.nj)
        projected = plant.base_velocity_from_momentum(
            quat_to_R(quatT), pT, qT, qdT, samples["h_O"][0]
        )
        omega_abs = float(np.linalg.norm(v6T[:3] - projected[:3]))
        linear_abs = float(np.linalg.norm(v6T[3:] - projected[3:]))
        energy = _energy_metrics(samples)
        runs.append(
            {
                "dt_s": dt,
                "solver_execution": samples["_solver_execution"],
                "samples": samples,
                "ledger": ledger,
                "metrics": {
                    **ledger["metrics"],
                    **energy,
                    "omega_xcheck_abs_rad_s": omega_abs,
                    "linear_velocity_xcheck_abs_m_s": linear_abs,
                    "epsilon_omega_xcheck": omega_abs / scales.omega_den_rad_s,
                    "epsilon_linear_velocity_xcheck": linear_abs / scales.v_den_m_s,
                },
            }
        )

    P_values = [r["metrics"]["epsilon_P_max"] for r in runs]
    H_values = [r["metrics"]["epsilon_H_max"] for r in runs]
    mom = gates["momentum"]
    conv_P = evaluate_three_point_convergence(
        P_values, dts, float(mom["roundoff_floor_P"]), mom["convergence_order_range"]
    )
    conv_H = evaluate_three_point_convergence(
        H_values, dts, float(mom["roundoff_floor_H"]), mom["convergence_order_range"]
    )
    nominal_dt = float(scenario["nominal_dt_s"])
    nominal = next(r for r in runs if r["dt_s"] == nominal_dt)
    xcheck = gates["base_velocity_crosscheck"]
    momentum_ruling = evaluate_momentum_gate_r5(nominal["ledger"], mom)
    diagnostic_gate_map = {
        **momentum_ruling["numeric_diagnostic_gates"],
        "G_ENERGY_CONSERVATION": nominal["metrics"]["rel_E_drift_max"]
        < float(gates["energy"]["relative_drift_max"]),
        "G_P_THREE_POINT_CONVERGENCE": bool(conv_P["passed"]),
        "G_H_THREE_POINT_CONVERGENCE": bool(conv_H["passed"]),
        "G_BASE_ANGULAR_VELOCITY_XCHECK": nominal["metrics"]["epsilon_omega_xcheck"]
        < float(xcheck["epsilon_omega_max"]),
        "G_BASE_LINEAR_VELOCITY_XCHECK": nominal["metrics"]["epsilon_linear_velocity_xcheck"]
        < float(xcheck["epsilon_linear_velocity_max"]),
        "G_EXTERNAL_LEDGER_COMPLETE": all(r["ledger"]["contract"]["event_monitor_status"] == "VERIFIED" for r in runs),
        "G_NO_MIXED_DIMENSION_NORM": True,
    }
    threshold_authority_present = momentum_ruling["threshold_authority_gate"]
    formal_gate_map = {
        **diagnostic_gate_map,
        "G_RELATIVE_METRIC_THRESHOLD_AUTHORITY": threshold_authority_present,
    }
    return {
        "case": case,
        "initial_state": x0,
        "scales": scales.as_dict(),
        "runs": runs,
        "P_convergence": conv_P,
        "H_convergence": conv_H,
        "gates": formal_gate_map,
        "diagnostic_gates": diagnostic_gate_map,
        "numeric_diagnostic_all_pass": bool(all(diagnostic_gate_map.values())),
        "relative_metric_status": momentum_ruling["relative_metric_status"],
        "relative_metric_hard_gate": momentum_ruling["relative_metric_hard_gate"],
        "threshold_authority_status": momentum_ruling["threshold_authority_status"],
        "threshold_authority_verdict": momentum_ruling["formal_verdict"],
        "hard_gate_failures": [name for name, value in formal_gate_map.items() if not value],
        "all_gates_pass": bool(all(formal_gate_map.values())),
    }


def _longest_true_duration(mask: np.ndarray, dt: float) -> tuple[float, int]:
    best = current = 0
    transitions = 0
    previous = False
    for value in np.asarray(mask, dtype=bool):
        if value:
            current += 1
        else:
            current = 0
        best = max(best, current)
        if bool(value) != previous:
            transitions += 1
        previous = bool(value)
    return best * dt, transitions


def run_s03_dt_r5(plant, controller: PDControllerR5, scenario: dict, dt: float, gates: dict) -> dict:
    x0 = pack_state(
        np.zeros(3),
        np.array([1.0, 0.0, 0.0, 0.0]),
        controller.q_start,
        np.zeros(6),
        np.zeros(plant.nj),
    )
    scales = compute_preintegration_scales(plant, x0, float(scenario["t_end_s"]))
    samples, telemetry = integrate_rk4_r5(
        plant,
        x0,
        float(scenario["t_end_s"]),
        float(dt),
        controller=controller,
        sample_period_target_s=float(scenario["sample_period_target_s"]),
        record_controller=True,
    )
    ledger = build_unit_safe_ledger(
        samples,
        scales,
        np.asarray(scenario["external_force_I_N"], dtype=float),
        np.asarray(scenario["external_torque_about_O_I_Nm"], dtype=float),
        [],
        external_wrench_status=scenario["external_wrench_status"],
        event_monitor_status=scenario["event_monitor_status"],
    )
    q_samples = np.asarray([unpack_state(x, plant.nj)[2] for x in samples["x"]])
    tail = samples["t"] >= controller.duration_s + 1.0
    abs_error = np.abs(q_samples[tail] - controller.q_goal) if np.any(tail) else np.full((1, plant.nj), np.nan)
    rev = np.asarray([b.jtype == "revolute" for b in plant.bodies[1:]])
    pri = np.asarray([b.jtype == "prismatic" for b in plant.bodies[1:]])
    quat_final = unpack_state(samples["x"][-1], plant.nj)[1]
    attitude_change = 2.0 * np.arccos(np.clip(abs(quat_final[0]), -1.0, 1.0))
    node_clip = telemetry["was_clipped"]
    stage_clip = telemetry["any_stage_clipped"]
    joint_units = ["N*m" if flag else "N" for flag in rev]
    saturation = []
    for j in range(plant.nj):
        longest, transitions = _longest_true_duration(node_clip[:, j], float(dt))
        active = np.flatnonzero(node_clip[:, j])
        saturation.append(
            {
                "joint_index": j + 1,
                "joint_type": plant.bodies[j + 1].jtype,
                "effort_unit": joint_units[j],
                "accepted_node_saturation_duration_s": float(node_clip[:, j].sum() * dt),
                "accepted_node_saturation_fraction": float(node_clip[:, j].mean()),
                "any_stage_saturation_duration_upper_bound_s": float(stage_clip[:, j].sum() * dt),
                "any_stage_saturation_fraction_upper_bound": float(stage_clip[:, j].mean()),
                "first_accepted_node_saturation_time_s": None if len(active) == 0 else float(active[0] * dt),
                "longest_accepted_node_saturation_segment_s": float(longest),
                "accepted_node_saturation_transitions": int(transitions),
            }
        )
    effort_max = np.max(np.abs(telemetry["effort_limited"]), axis=0)
    physical_limit_violations = []
    for j, body in enumerate(plant.bodies[1:]):
        limits = body.limits or {}
        qj = telemetry["q"][:, j]
        below = bool("lower" in limits and np.any(qj < float(limits["lower"]) - 1.0e-12))
        above = bool("upper" in limits and np.any(qj > float(limits["upper"]) + 1.0e-12))
        physical_limit_violations.append(
            {"joint_index": j + 1, "below_lower": below, "above_upper": above}
        )
    metrics = {
        **ledger["metrics"],
        "tracking_error_revolute_max_rad": float(np.nanmax(abs_error[:, rev])),
        "tracking_error_prismatic_max_m": float(np.nanmax(abs_error[:, pri])),
        "generalized_effort_abs_max_per_joint": [
            {
                "joint_index": j + 1,
                "joint_type": plant.bodies[j + 1].jtype,
                "value": float(effort_max[j]),
                "unit": joint_units[j],
            }
            for j in range(plant.nj)
        ],
        "any_accepted_node_saturation": bool(np.any(node_clip)),
        "any_stage_saturation": bool(np.any(stage_clip)),
        "base_attitude_change_deg": float(np.degrees(attitude_change)),
        "base_translation_m": float(np.linalg.norm(unpack_state(samples["x"][-1], plant.nj)[0])),
        "physical_joint_limit_violations": physical_limit_violations,
        "controller_evaluation_contract": {
            "timeseries_basis": "K1_ACCEPTED_NODE",
            "all_four_stages_consumed_for_upper_bound": True,
            "I_term_status": "STRUCTURAL_ZERO_PD_NO_INTEGRATOR",
        },
        "saturation_by_joint": saturation,
    }
    return {
        "dt_s": float(dt),
        "solver_execution": samples["_solver_execution"],
        "initial_state": x0,
        "scales": scales.as_dict(),
        "samples": samples,
        "telemetry": telemetry,
        "ledger": ledger,
        "metrics": metrics,
        "claim": "DIAGNOSTIC_ONLY_NOT_CONTROL_PASS",
        "control_release": False,
    }


def _fd_jacobian(function, x0: np.ndarray, eps: float) -> np.ndarray:
    x0 = np.asarray(x0, dtype=float)
    f0 = np.asarray(function(x0), dtype=float)
    J = np.zeros((len(f0), len(x0)))
    for i in range(len(x0)):
        xp, xm = x0.copy(), x0.copy()
        xp[i] += eps
        xm[i] -= eps
        J[:, i] = (np.asarray(function(xp)) - np.asarray(function(xm))) / (2.0 * eps)
    return J


def _rk4_reduced_step(derivative, y: np.ndarray, dt: float) -> np.ndarray:
    k1 = derivative(y)
    k2 = derivative(y + 0.5 * dt * k1)
    k3 = derivative(y + 0.5 * dt * k2)
    k4 = derivative(y + dt * k3)
    return y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def stability_analysis_r5(plant, controller: PDControllerR5, scenario: dict) -> dict:
    """Analyze the terminal equilibrium without misclassifying neutral modes."""
    cfg = scenario["stability_linearization"]
    q_star = controller.q_goal.copy()
    H = plant.crba(q_star)
    H_BB, H_Bq = H[:6, :6], H[:6, 6:]
    H_qB, H_qq = H[6:, :6], H[6:, 6:]
    M_eff = H_qq - H_qB @ np.linalg.solve(H_BB, H_Bq)
    M_eff = 0.5 * (M_eff + M_eff.T)
    try:
        np.linalg.cholesky(M_eff)
        M_eff_positive_definite = True
    except np.linalg.LinAlgError:
        M_eff_positive_definite = False
    n = plant.nj
    A = np.block(
        [
            [np.zeros((n, n)), np.eye(n)],
            [-np.linalg.solve(M_eff, np.diag(controller.Kp)), -np.linalg.solve(M_eff, np.diag(controller.Kd))],
        ]
    )
    joint_is_rev = np.asarray([b.jtype == "revolute" for b in plant.bodies[1:]])
    q_scales = np.where(
        joint_is_rev,
        float(cfg["coordinate_scales"]["revolute_position_rad"]),
        float(cfg["coordinate_scales"]["prismatic_position_m"]),
    )
    qd_scales = np.where(
        joint_is_rev,
        float(cfg["coordinate_scales"]["revolute_rate_rad_s"]),
        float(cfg["coordinate_scales"]["prismatic_rate_m_s"]),
    )
    reduced_scales = np.concatenate([q_scales, qd_scales])
    S = np.diag(reduced_scales)
    A_scaled = np.linalg.solve(S, A @ S)

    def reduced_derivative_scaled(z):
        y = np.concatenate([q_star, np.zeros(n)]) + reduced_scales * np.asarray(z)
        q, qd = y[:n], y[n:]
        v_base = plant.base_velocity_from_momentum(
            np.eye(3), np.zeros(3), q, qd, np.zeros(6)
        )
        effort = controller.Kp * (q_star - q) - controller.Kd * qd
        udot, _, _ = plant.forward_dynamics(q, v_base, qd, effort)
        return np.concatenate([qd, udot[6:]]) / reduced_scales

    eps = float(cfg["finite_difference_scaled_epsilon"])
    A_fd = _fd_jacobian(reduced_derivative_scaled, np.zeros(2 * n), eps)
    continuous_eigs, eigvecs = np.linalg.eig(A_scaled)
    fast_index = int(np.argmin(continuous_eigs.real))
    fast_vec = eigvecs[:, fast_index]
    qd_participation = np.abs(fast_vec[n:])
    qd_participation /= max(float(np.max(qd_participation)), np.finfo(float).tiny)

    # Full velocity-state linearization is reported only to classify the six
    # free-floating neutral modes; its spectral radius is not a pass condition.
    full_scales = np.concatenate(
        [
            q_scales,
            np.full(3, float(cfg["coordinate_scales"]["angular_velocity_rad_s"])),
            np.full(3, float(cfg["coordinate_scales"]["linear_velocity_m_s"])),
            qd_scales,
        ]
    )

    def full_derivative_scaled(z):
        y = np.concatenate([q_star, np.zeros(6 + n)]) + full_scales * np.asarray(z)
        q, v_base, qd = y[:n], y[n : n + 6], y[n + 6 :]
        effort = controller.Kp * (q_star - q) - controller.Kd * qd
        udot, _, _ = plant.forward_dynamics(q, v_base, qd, effort)
        return np.concatenate([qd, udot]) / full_scales

    A_full = _fd_jacobian(full_derivative_scaled, np.zeros(n + 6 + n), eps)
    tol = float(cfg["eigenvalue_classification_tolerance"])
    per_dt = []
    for dt in [float(v) for v in scenario["dt_grid_s"]]:
        lam = continuous_eigs
        z = dt * lam
        amp = np.abs(1.0 + z + z**2 / 2.0 + z**3 / 6.0 + z**4 / 24.0)

        def actual_reduced_map(z0):
            y = np.concatenate([q_star, np.zeros(n)]) + reduced_scales * np.asarray(z0)
            q, qd = y[:n], y[n:]
            v_base = plant.base_velocity_from_momentum(
                np.eye(3), np.zeros(3), q, qd, np.zeros(6)
            )
            x = pack_state(
                np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0]), q, v_base, qd
            )
            x_next, _, _ = rk4_step_r5(plant, x, controller.duration_s + 1.0, dt, controller)
            _, _, q_next, _, qd_next = unpack_state(x_next, n)
            return (np.concatenate([q_next, qd_next]) - np.concatenate([q_star, np.zeros(n)])) / reduced_scales

        rho_samples = []
        actual_J = None
        for fd_eps in (0.5 * eps, eps, 2.0 * eps):
            actual_J = _fd_jacobian(actual_reduced_map, np.zeros(2 * n), fd_eps)
            rho_samples.append(float(np.max(np.abs(np.linalg.eigvals(actual_J)))))
        rho = rho_samples[1]
        rho_uncertainty = max(rho_samples) - min(rho_samples)

        I_full = np.eye(A_full.shape[0])
        A_dt = dt * A_full
        full_poly = I_full + A_dt + A_dt @ A_dt / 2.0 + A_dt @ A_dt @ A_dt / 6.0 + A_dt @ A_dt @ A_dt @ A_dt / 24.0
        mu_full = np.abs(np.linalg.eigvals(full_poly))
        classification_margin = 5.0 * rho_uncertainty + 1.0e-10
        if rho > 1.0 + classification_margin:
            reduced_class = "UNSTABLE"
        elif rho < 1.0 - classification_margin:
            reduced_class = "DECAY"
        else:
            reduced_class = "INCONCLUSIVE_ON_STABILITY_BOUNDARY"
        per_dt.append(
            {
                "dt_s": dt,
                "rk4_polynomial_max_amplification": float(np.max(amp)),
                "rk4_polynomial_unstable_modes": int(np.sum(amp > 1.0 + tol)),
                "actual_reduced_map_spectral_radius": rho,
                "actual_reduced_map_rho_fd_samples": rho_samples,
                "actual_reduced_map_rho_uncertainty_range": rho_uncertainty,
                "actual_reduced_map_classification": reduced_class,
                "full_velocity_state_rk4_polynomial_classification": {
                    "unstable": int(np.sum(mu_full > 1.0 + tol)),
                    "neutral": int(np.sum(np.abs(mu_full - 1.0) <= tol)),
                    "decay": int(np.sum(mu_full < 1.0 - tol)),
                    "spectral_radius": float(np.max(mu_full)),
                    "not_a_pass_condition": True,
                },
            }
        )

    continuous_stable = bool(np.max(continuous_eigs.real) < 0.0)
    mechanism_confirmed = bool(
        continuous_stable
        and per_dt[0]["actual_reduced_map_classification"] == "UNSTABLE"
        and all(item["actual_reduced_map_classification"] == "DECAY" for item in per_dt[1:])
        and per_dt[0]["rk4_polynomial_max_amplification"] > 1.0
        and all(item["rk4_polynomial_max_amplification"] < 1.0 for item in per_dt[1:])
    )
    if mechanism_confirmed:
        ruling = "RK4_TIME_DISCRETIZATION_MECHANISM_CONFIRMED"
    elif not continuous_stable:
        ruling = "CONTINUOUS_CONTROLLER_OR_PLANT_UNSTABLE"
    else:
        ruling = "MECHANISM_INCONCLUSIVE_NUMERICAL_BOUNDARY"
    return {
        "schema": "S03_LOCAL_STABILITY_ANALYSIS_R5_V1",
        "scope": "TERMINAL_EQUILIBRIUM_LOCAL_ANALYSIS_ONLY",
        "continuous_reduced_model": {
            "state": "8_joint_position_plus_8_joint_rate_zero_total_momentum_subspace",
            "M_eff_positive_definite": M_eff_positive_definite,
            "M_eff_test": "CHOLESKY_ON_DECLARED_UNIT_SCALED_GENERALIZED_COORDINATES",
            "M_eff_scalar_eigenvalues_omitted": "MIXED_6R_PLUS_2P_GENERALIZED_COORDINATES_HAVE_NO_SINGLE_SI_UNIT",
            "max_real_eigenvalue_per_s": float(np.max(continuous_eigs.real)),
            "min_real_eigenvalue_per_s": float(np.min(continuous_eigs.real)),
            "all_modes_strictly_stable": continuous_stable,
            "analytic_vs_scaled_fd_max_abs": float(np.max(np.abs(A_scaled - A_fd))),
            "analytic_vs_scaled_fd_relative_frobenius": float(
                np.linalg.norm(A_scaled - A_fd) / np.linalg.norm(A_scaled)
            ),
            "fastest_mode_joint_rate_participation_normalized": qd_participation.tolist(),
            "fastest_mode_dominant_joint_index": int(np.argmax(qd_participation) + 1),
        },
        "dt_analysis": per_dt,
        "ruling": ruling,
        "ruling_scope": "LOCAL_TERMINAL_EQUILIBRIUM_ZERO_TOTAL_MOMENTUM_INTERNAL_SUBSPACE_UNCONSTRAINED_6R_PLUS_2P_MATHEMATICAL_PLANT",
        "mechanism_confirmed": mechanism_confirmed,
        "full_velocity_state_polynomial_neutral_mode_policy": "CLASSIFY_NOT_REQUIRE_RHO_LT_ONE__NOT_ACTUAL_POSE_QUATERNION_MAP",
        "unit_scaling": {
            "reduced_state_scales": reduced_scales.tolist(),
            "full_state_scales": full_scales.tolist(),
            "finite_difference_scaled_epsilon": eps,
        },
        "physical_applicability_hold": {
            "active": True,
            "reason": "TWO_PRISMATIC_JOINTS_AT_LOWER_LIMIT_AND_UNCONSTRAINED_MATHEMATICAL_LINEARIZATION",
            "no_flight_control_release": True,
        },
        "claim": "LOCAL_MECHANISM_ONLY_NOT_GLOBAL_TRAJECTORY_STABILITY_OR_CONTROL_RELEASE",
    }
