"""Stage B transient stability under PROVISIONAL actuator dynamics (R5).

This layer EXECUTES the frozen L0 momentum plan of each stage-B row through a
deterministic fixed-grid actuator model:

- reaction wheels: per-axis momentum ramp toward the L0 wheel allocation,
  slew-limited by the PROVISIONAL wheel_max_torque_Nm; the per-axis
  +/-0.1 Nms box is never exceeded because the target is the already-clipped
  L0 allocation.
- thruster: whole pulses of the PROVISIONAL minimum pulse width along the
  fixed L0 external-removal direction; the angular impulse quantum is
  F * t_min * lever, and only complete pulses fire, so the executed removal is
  floor(|d_ext| / quantum) quanta and the terminal state differs from L0 by at
  most one quantum.

The rate map omega = I^-1 * H_body uses the combined inertia frozen at the
capture attitude (PROVISIONAL_L1_MOMENTUM_ACTUATOR); momentum bookkeeping is
exact.  Stability is judged only by the frozen time-window criterion; nothing
here supports a hardware-valid or closed-loop-control claim.
"""
from __future__ import annotations

import math

import numpy as np

from ledger import classify_attribution

TRANSIENT_STABILITY_STATUS = "EVALUATED_TIME_WINDOW_PROVISIONAL_ACTUATORS"
TRANSIENT_MODEL_FIDELITY = "PROVISIONAL_L1_MOMENTUM_ACTUATOR"


def _case_states(cfg: dict) -> dict:
    """Rebuild each case's capture state via the independent phase-B path."""
    from phase_b import _build_case, _load_cases

    cases = _load_cases(cfg)
    out = {}
    for case_id in cfg["stage_b"]["cases"]:
        capture = _build_case(cases[case_id])
        out[case_id] = {
            "H_init": np.asarray(capture["H_com"], dtype=float),
            "I_comb": np.asarray(capture["I_comb"], dtype=float),
        }
    return out


def _settle_time(ts: np.ndarray, rates: np.ndarray, thresh: float) -> float | None:
    """Start time of the trailing run with rate <= thresh; None if empty."""
    below = rates <= thresh
    if not below[-1]:
        return None
    idx = len(below) - 1
    while idx > 0 and below[idx - 1]:
        idx -= 1
    return float(ts[idx])


def run_transient(cfg: dict, stage_b: list[dict]) -> tuple[list[dict], dict]:
    stage = cfg["stage_b"]
    act = stage["actuator_dynamics"]
    win = stage["stability_window"]
    force_N = float(stage["thruster_force_N"])
    lever_m = float(stage["lever_arm_m"])
    isp_s = float(stage["isp_s"])
    g0 = float(stage["g0_mps2"])
    box = np.asarray(stage["wheel_capacity_per_axis_Nms"], dtype=float)
    tau_max = float(act["wheel_max_torque_Nm"])
    t_pulse = float(act["thruster_min_pulse_s"])
    dt = float(win["time_step_s"])
    window_s = float(win["window_s"])
    hold_s = float(win["hold_min_s"])
    thresh_dps = float(win["rate_settle_dps"])
    tol = float(cfg["gates"]["attribution_abs"])
    quantum_Nms = force_N * t_pulse * lever_m

    if abs(dt - t_pulse) > 1e-15:
        raise RuntimeError(
            "stability_window.time_step_s must equal thruster_min_pulse_s "
            "so every pulse is grid-aligned"
        )

    states = _case_states(cfg)
    rows = []
    for l0 in stage_b:
        case_id = l0["case"]
        h_init = states[case_id]["H_init"]
        inertia = states[case_id]["I_comb"]
        inertia_inv = np.linalg.inv(inertia)

        wheel_target = np.asarray(l0["wheel_h_final_Nms"], dtype=float)
        d_ext = np.asarray(l0["external_angular_impulse_vector_Nms"], dtype=float)
        d_ext_norm = float(np.linalg.norm(d_ext))
        if d_ext_norm > tol:
            direction = d_ext / d_ext_norm
            n_pulses = int(math.floor(d_ext_norm / quantum_Nms + 1e-12))
        else:
            direction = np.zeros(3)
            n_pulses = 0
        executed_Nms = n_pulses * quantum_Nms
        remainder_Nms = d_ext_norm - executed_Nms

        wheel_slew_s = float(np.max(np.abs(wheel_target))) / tau_max if tau_max > 0 else 0.0
        completion_s = max(wheel_slew_s, n_pulses * dt)
        t_end = max(window_s, completion_s + dt)
        n_steps = int(round(t_end / dt))

        h_total = h_init.copy()
        h_wheel = np.zeros(3)
        fired = 0
        wheel_abs_peak = 0.0
        ts = np.zeros(n_steps + 1)
        rates = np.zeros(n_steps + 1)
        rates[0] = float(
            np.rad2deg(np.linalg.norm(inertia_inv @ (h_total - h_wheel)))
        )
        step_torque = tau_max * dt
        for k in range(n_steps):
            delta = np.clip(wheel_target - h_wheel, -step_torque, step_torque)
            h_wheel = h_wheel + delta
            if fired < n_pulses:
                h_total = h_total + direction * quantum_Nms
                fired += 1
            wheel_abs_peak = max(wheel_abs_peak, float(np.max(np.abs(h_wheel))))
            ts[k + 1] = (k + 1) * dt
            rates[k + 1] = float(
                np.rad2deg(np.linalg.norm(inertia_inv @ (h_total - h_wheel)))
            )

        in_window = ts <= window_s + 1e-12
        t_star = _settle_time(ts[in_window], rates[in_window], thresh_dps)
        stabilized = t_star is not None and (window_s - t_star) >= hold_s - 1e-9
        verdict = (
            "STABILIZED_WITHIN_WINDOW"
            if stabilized
            else "NOT_STABILIZED_WITHIN_WINDOW"
        )

        # Terminal consistency against the frozen L0 terminal state.
        h_body_end = h_total - h_wheel
        h_body_l0 = h_init + d_ext - wheel_target
        l0_diff_Nms = float(np.linalg.norm(h_body_end - h_body_l0))
        accumulation_err_Nms = abs(l0_diff_Nms - remainder_Nms)

        # Independent algebraic prediction (no time marching).
        pred_h_body = h_body_l0 - direction * remainder_Nms
        pred_rate_dps = float(
            np.rad2deg(np.linalg.norm(inertia_inv @ pred_h_body))
        )
        pred_stabilized = (
            pred_rate_dps <= thresh_dps and completion_s <= window_s - hold_s
        )
        prediction_matches = pred_stabilized == stabilized

        executed_vec = direction * (n_pulses * force_N * t_pulse * lever_m)
        thruster_impulse_Ns = n_pulses * force_N * t_pulse
        propellant_g = 1000.0 * thruster_impulse_Ns / (isp_s * g0)
        attribution = classify_attribution(
            executed_vec, h_wheel, internal_motion=False, tolerance=tol
        )

        rows.append(
            {
                "phase": "B_TRANSIENT",
                "case": case_id,
                "controller": l0["controller"],
                "evaluation_status": "EVALUATED",
                "analysis_scope": "TIME_WINDOW_TRANSIENT_STABILITY",
                "stability_status": TRANSIENT_STABILITY_STATUS,
                "model_fidelity": TRANSIENT_MODEL_FIDELITY,
                "hardware_valid": False,
                "domain_status": l0["domain_status"],
                "counterfactual_only": l0["counterfactual_only"],
                "flex_status": l0["flex_status"],
                "attribution": attribution,
                "stability_verdict": verdict,
                "stabilized_within_window": stabilized,
                "t_settle_s": t_star,
                "window_s": window_s,
                "hold_min_s": hold_s,
                "rate_settle_dps": thresh_dps,
                "rate_initial_dps": float(rates[0]),
                "rate_at_window_end_dps": float(rates[in_window][-1]),
                "rate_final_dps": float(rates[-1]),
                "n_pulses": n_pulses,
                "pulse_quantum_Nms": quantum_Nms,
                "unexecuted_remainder_Nms": remainder_Nms,
                "completion_time_s": completion_s,
                "wheel_slew_time_s": wheel_slew_s,
                "wheel_h_final_Nms": h_wheel.tolist(),
                "wheel_abs_peak_Nms": wheel_abs_peak,
                "external_angular_impulse_vector_Nms": executed_vec.tolist(),
                "external_angular_impulse_Nms": float(
                    np.linalg.norm(executed_vec)
                ),
                "thruster_total_impulse_Ns": thruster_impulse_Ns,
                "propellant_g": propellant_g,
                "H_body_final_Nms": float(np.linalg.norm(h_body_end)),
                "terminal_vs_L0_diff_Nms": l0_diff_Nms,
                "terminal_consistency_bound_Nms": quantum_Nms + 1e-9,
                "terminal_consistent_with_L0": l0_diff_Nms
                <= quantum_Nms + 1e-9,
                "accumulation_error_Nms": accumulation_err_Nms,
                "predicted_rate_dps": pred_rate_dps,
                "predicted_stabilized": pred_stabilized,
                "prediction_matches_simulation": prediction_matches,
                "timeseries_1hz": [
                    {
                        "t_s": float(ts[i]),
                        "rate_dps": float(rates[i]),
                    }
                    for i in range(0, len(ts), int(round(1.0 / dt)))
                ],
            }
        )

    criterion = {
        "status": "PROVISIONAL",
        "wheel_max_torque_Nm": tau_max,
        "thruster_min_pulse_s": t_pulse,
        "pulse_quantum_Nms": quantum_Nms,
        "window_s": window_s,
        "hold_min_s": hold_s,
        "rate_settle_dps": thresh_dps,
        "time_step_s": dt,
        "criterion_text": win["criterion"],
        "model_fidelity": TRANSIENT_MODEL_FIDELITY,
    }
    return rows, criterion
