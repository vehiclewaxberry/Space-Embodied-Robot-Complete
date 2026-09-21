"""R5 unit-safe linear/angular momentum ledger.

Spatial algebra in the plant legitimately stores ``[H; P]``.  This module is
the reporting and Gate boundary: it splits angular momentum ``H`` [N*m*s]
from linear momentum ``P`` [kg*m/s] before any norm or normalization.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np

from .frames import make_T, quat_to_R
from .integrators import unpack_state
from .spatial import X_force


class LedgerContractError(RuntimeError):
    """Raised when a required external-action or event contract is absent."""


@dataclass(frozen=True)
class MomentumScales:
    P_den_kg_m_s: float
    H_den_N_m_s: float
    omega_den_rad_s: float
    v_den_m_s: float
    total_mass_kg: float
    L_ref_m: float
    T_ref_s: float
    source_terms: dict

    def as_dict(self) -> dict:
        return {
            "P_den_kg_m_s": self.P_den_kg_m_s,
            "H_den_N_m_s": self.H_den_N_m_s,
            "omega_den_rad_s": self.omega_den_rad_s,
            "v_den_m_s": self.v_den_m_s,
            "total_mass_kg": self.total_mass_kg,
            "L_ref_m": self.L_ref_m,
            "T_ref_s": self.T_ref_s,
            "computed_before_integration": True,
            "posterior_residual_used": False,
            "source_terms": self.source_terms,
        }


def split_spatial_momentum(h_spatial: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(H_O_I, P_I)`` without constructing a mixed-unit norm."""
    h = np.asarray(h_spatial, dtype=float)
    if h.shape[-1] != 6:
        raise LedgerContractError(f"spatial momentum last dimension must be 6, got {h.shape}")
    return h[..., :3].copy(), h[..., 3:].copy()


def _body_momentum_and_coms(plant, R_WB, p_WB, q, v_base, qd):
    velocities, kin = plant.body_velocities(q, v_base, qd)
    T_W = [make_T(R_WB, p_WB)]
    for i in range(1, len(plant.bodies)):
        T_W.append(T_W[plant.bodies[i].parent] @ kin[i - 1][0])

    H_parts, P_parts, masses, coms = [], [], [], []
    for i, body in enumerate(plant.bodies):
        h_world = X_force(T_W[i]) @ (body.I_sp @ velocities[i])
        H_parts.append(h_world[:3])
        P_parts.append(h_world[3:])
        mass = float(body.I_sp[5, 5])
        c_body = np.array(
            [body.I_sp[2, 4], body.I_sp[0, 5], body.I_sp[1, 3]], dtype=float
        ) / mass
        c_world = (T_W[i] @ np.concatenate([c_body, [1.0]]))[:3]
        masses.append(mass)
        coms.append(c_world)
    return np.asarray(H_parts), np.asarray(P_parts), np.asarray(masses), np.asarray(coms)


def body_momentum_contributions(plant, R_WB, p_WB, q, v_base, qd) -> dict:
    """Return deterministic per-dynamic-body P, spin-H and orbital-H terms."""
    H_O, P, masses, coms = _body_momentum_and_coms(
        plant, R_WB, p_WB, q, v_base, qd
    )
    H_orbital = np.cross(coms, P)
    H_spin = H_O - H_orbital
    return {
        "body_ids": [body.name for body in plant.bodies],
        "mass_kg": masses,
        "com_I_m": coms,
        "P_body_I_kg_m_s": P,
        "H_spin_body_I_N_m_s": H_spin,
        "H_orbital_body_O_I_N_m_s": H_orbital,
        "H_body_O_I_N_m_s": H_O,
    }


def compensated_component_sum(values: np.ndarray) -> np.ndarray:
    """Deterministically sum Nx3 same-unit vectors with ``math.fsum``."""
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or array.shape[1] != 3:
        raise LedgerContractError(f"expected Nx3 same-unit vectors, got {array.shape}")
    return np.asarray([math.fsum(array[:, axis].tolist()) for axis in range(3)])


def compute_preintegration_scales(plant, x0: np.ndarray, T_ref_s: float) -> MomentumScales:
    """Compute deterministic physical scales before a time integration.

    The fallback terms are plant/time scales, not arbitrary epsilons and not
    functions of the subsequently observed residuals.
    """
    if not np.isfinite(T_ref_s) or T_ref_s <= 0.0:
        raise LedgerContractError("T_ref_s must be finite and positive")
    p, quat, q, v_base, qd = unpack_state(np.asarray(x0, dtype=float), plant.nj)
    R_WB = quat_to_R(quat)
    H_parts, P_parts, masses, coms = _body_momentum_and_coms(
        plant, R_WB, p, q, v_base, qd
    )
    total_mass = float(masses.sum())
    p_com = np.average(coms, axis=0, weights=masses)
    L_ref = float(np.max(np.linalg.norm(coms - p_com, axis=1)))

    # Rigid-body angular response about the system CoM gives the assembled
    # system inertia tensor in the inertial frame without retyping inertias.
    I_G = np.zeros((3, 3))
    for axis in range(3):
        omega_I = np.zeros(3)
        omega_I[axis] = 1.0
        base_origin_velocity_I = np.cross(omega_I, p - p_com)
        v6 = np.concatenate([R_WB.T @ omega_I, R_WB.T @ base_origin_velocity_I])
        _, h_C, _, _, _ = plant.momentum_world(
            R_WB, p, q, v6, np.zeros(plant.nj)
        )
        I_G[:, axis] = h_C[:3]
    I_G = 0.5 * (I_G + I_G.T)
    I_G_spectral = float(np.linalg.norm(I_G, ord=2))

    sum_P_parts = float(np.sum(np.linalg.norm(P_parts, axis=1)))
    sum_H_parts = float(np.sum(np.linalg.norm(H_parts, axis=1)))
    P_plant_time = total_mass * L_ref / T_ref_s
    H_plant_time = I_G_spectral / T_ref_s
    P_den = max(sum_P_parts, P_plant_time)
    H_den = max(sum_H_parts, H_plant_time)
    omega_initial = float(np.linalg.norm(v_base[:3]))
    v_initial = float(np.linalg.norm(v_base[3:]))
    omega_den = max(omega_initial, 1.0 / T_ref_s)
    v_den = max(v_initial, L_ref / T_ref_s)
    values = (P_den, H_den, omega_den, v_den, total_mass, L_ref, I_G_spectral)
    if not all(np.isfinite(v) for v in values) or min(P_den, H_den, omega_den, v_den) <= 0.0:
        raise LedgerContractError("preintegration scale contract is non-finite or non-positive")
    return MomentumScales(
        P_den_kg_m_s=P_den,
        H_den_N_m_s=H_den,
        omega_den_rad_s=omega_den,
        v_den_m_s=v_den,
        total_mass_kg=total_mass,
        L_ref_m=L_ref,
        T_ref_s=float(T_ref_s),
        source_terms={
            "sum_body_initial_linear_momentum_norms_kg_m_s": sum_P_parts,
            "external_impulse_budget_kg_m_s": 0.0,
            "total_mass_times_L_ref_over_T_ref_kg_m_s": P_plant_time,
            "sum_body_initial_angular_momentum_about_O_norms_N_m_s": sum_H_parts,
            "external_angular_impulse_budget_N_m_s": 0.0,
            "system_com_inertia_spectral_norm_kg_m2": I_G_spectral,
            "system_com_inertia_over_T_ref_N_m_s": H_plant_time,
            "initial_base_angular_rate_norm_rad_s": omega_initial,
            "initial_base_linear_velocity_norm_m_s": v_initial,
        },
    )


def _cumulative_trapezoid(t: np.ndarray, values: np.ndarray) -> np.ndarray:
    out = np.zeros_like(values, dtype=float)
    if len(t) > 1:
        dt = np.diff(t)[:, None]
        out[1:] = np.cumsum(0.5 * (values[:-1] + values[1:]) * dt, axis=0)
    return out


def _event_cumulative(t: np.ndarray, events: Iterable[dict], key: str) -> np.ndarray:
    out = np.zeros((len(t), 3), dtype=float)
    for event in events:
        if "t_s" not in event or key not in event:
            raise LedgerContractError(f"event missing t_s or {key}")
        impulse = np.asarray(event[key], dtype=float)
        if impulse.shape != (3,) or not np.all(np.isfinite(impulse)):
            raise LedgerContractError(f"event {key} must be a finite 3-vector")
        out[t >= float(event["t_s"])] += impulse
    return out


def build_unit_safe_ledger(
    samples: dict,
    scales: MomentumScales,
    external_force_I_N: np.ndarray,
    external_torque_O_I_Nm: np.ndarray,
    events: Iterable[dict],
    *,
    external_wrench_status: str,
    event_monitor_status: str,
) -> dict:
    """Build separate P and H residual histories and dimensionless errors."""
    if external_wrench_status not in (
        "FROZEN_ZERO_BY_MODEL_SCOPE",
        "EXPLICIT_HISTORY_VERIFIED",
    ):
        raise LedgerContractError("external wrench must be explicit verified-zero or verified history")
    if event_monitor_status != "VERIFIED":
        raise LedgerContractError("empty events are admissible only with VERIFIED monitoring")
    t = np.asarray(samples["t"], dtype=float)
    H_plant, P_plant = split_spatial_momentum(np.asarray(samples["h_O"], dtype=float))
    if "P_body_I_kg_m_s" in samples and "H_body_O_I_N_m_s" in samples:
        P_body = np.asarray(samples["P_body_I_kg_m_s"], dtype=float)
        H_body = np.asarray(samples["H_body_O_I_N_m_s"], dtype=float)
        if P_body.ndim != 3 or H_body.shape != P_body.shape or P_body.shape[2] != 3:
            raise LedgerContractError("per-body momentum histories must both be time x body x 3")
        P = np.asarray([compensated_component_sum(row) for row in P_body])
        H = np.asarray([compensated_component_sum(row) for row in H_body])
        crosscheck_P = float(np.max(np.abs(P - P_plant)))
        crosscheck_H = float(np.max(np.abs(H - H_plant)))
    else:
        P, H = P_plant, H_plant
        P_body = H_body = None
        crosscheck_P = crosscheck_H = 0.0
    F = np.asarray(external_force_I_N, dtype=float)
    tau = np.asarray(external_torque_O_I_Nm, dtype=float)
    if F.shape == (3,):
        F = np.repeat(F[None, :], len(t), axis=0)
    if tau.shape == (3,):
        tau = np.repeat(tau[None, :], len(t), axis=0)
    if F.shape != (len(t), 3) or tau.shape != (len(t), 3):
        raise LedgerContractError("external force/torque histories must be 3-vectors or Nx3")
    if not np.all(np.isfinite(F)) or not np.all(np.isfinite(tau)):
        raise LedgerContractError("external force/torque histories must be finite")
    if external_wrench_status == "FROZEN_ZERO_BY_MODEL_SCOPE" and (
        np.any(F != 0.0) or np.any(tau != 0.0)
    ):
        raise LedgerContractError("frozen-zero external wrench status conflicts with nonzero history")

    events = list(events)
    J_ext = _cumulative_trapezoid(t, F)
    K_ext = _cumulative_trapezoid(t, tau)
    J_event = _event_cumulative(t, events, "linear_impulse_I_kg_m_s")
    K_event = _event_cumulative(t, events, "angular_impulse_O_I_N_m_s")
    R_P = P - P[0] - J_ext - J_event
    R_H = H - H[0] - K_ext - K_event
    norm_R_P = np.linalg.norm(R_P, axis=1)
    norm_R_H = np.linalg.norm(R_H, axis=1)
    epsilon_P = norm_R_P / scales.P_den_kg_m_s
    epsilon_H = norm_R_H / scales.H_den_N_m_s
    finite = bool(
        np.all(np.isfinite(R_P))
        and np.all(np.isfinite(R_H))
        and np.all(np.isfinite(epsilon_P))
        and np.all(np.isfinite(epsilon_H))
    )
    return {
        "t_s": t,
        "P_I_kg_m_s": P,
        "H_O_I_N_m_s": H,
        "external_J_I_kg_m_s": J_ext,
        "external_K_O_I_N_m_s": K_ext,
        "event_J_I_kg_m_s": J_event,
        "event_K_O_I_N_m_s": K_event,
        "R_P_I_kg_m_s": R_P,
        "R_H_O_I_N_m_s": R_H,
        "norm_R_P_kg_m_s": norm_R_P,
        "norm_R_H_N_m_s": norm_R_H,
        "epsilon_P": epsilon_P,
        "epsilon_H": epsilon_H,
        "metrics": {
            "epsilon_P_max": float(np.max(epsilon_P)),
            "epsilon_H_max": float(np.max(epsilon_H)),
            "norm_R_P_max_kg_m_s": float(np.max(norm_R_P)),
            "norm_R_H_max_N_m_s": float(np.max(norm_R_H)),
            "finite": finite,
            "per_body_sum_vs_plant_P_component_max_abs_kg_m_s": crosscheck_P,
            "per_body_sum_vs_plant_H_component_max_abs_N_m_s": crosscheck_H,
        },
        "contract": {
            "expressed_in": "I",
            "angular_momentum_about": "INERTIAL_ORIGIN_I",
            "origin_motion": "FIXED",
            "external_wrench_status": external_wrench_status,
            "event_monitor_status": event_monitor_status,
            "event_count": len(events),
            "velocity_discontinuity_count": 0,
            "configuration_projection": {
                "quaternion_renormalization": "RECORDED_NONIMPULSIVE",
                "velocity_reset": False,
            },
            "reaction_wheels": "NOT_IN_PLANT_NULL_NOT_ZERO_FILLED",
            "thrusters": "NOT_IN_PLANT_NULL_NOT_ZERO_FILLED",
            "target": "REGISTERED_NOT_SYSTEM_MEMBER",
            "no_mixed_dimension_norm": True,
            "same_unit_component_summation": "DETERMINISTIC_MATH_FSUM",
        },
        "body_ids": list(samples.get("body_ids", [])),
        "P_body_I_kg_m_s": P_body,
        "H_spin_body_I_N_m_s": samples.get("H_spin_body_I_N_m_s"),
        "H_orbital_body_O_I_N_m_s": samples.get("H_orbital_body_O_I_N_m_s"),
        "H_body_O_I_N_m_s": H_body,
    }


def evaluate_three_point_convergence(values, dts, floor: float, order_range) -> dict:
    """R4 pairwise/floor semantics, applied independently to P or H."""
    rel = np.asarray(values, dtype=float)
    dt = np.asarray(dts, dtype=float)
    lo, hi = map(float, order_range)
    valid_values = bool(rel.ndim == 1 and np.all(np.isfinite(rel)) and np.all(rel >= 0.0))
    valid_dt = bool(
        dt.ndim == 1
        and len(dt) == len(rel)
        and len(dt) >= 3
        and np.all(np.isfinite(dt))
        and np.all(dt > 0.0)
        and np.all(dt[:-1] > dt[1:])
    )
    ratio_valid = bool(valid_dt and np.allclose(dt[:-1] / dt[1:], 2.0, rtol=1.0e-12, atol=0.0))
    if not valid_values or not valid_dt or not ratio_valid:
        if not valid_values:
            mode = "FAIL_NONFINITE_OR_NEGATIVE_DRIFT"
        elif len(rel) < 3:
            mode = "FAIL_INSUFFICIENT_REFINEMENT_POINTS"
        elif not valid_dt:
            mode = "FAIL_INVALID_DT_ORDER"
        else:
            mode = "FAIL_INVALID_DT_RATIO"
        return {
            "passed": False,
            "mode": mode,
            "dt_order_valid": valid_dt,
            "dt_ratio_valid": ratio_valid,
            "observed_orders": [],
            "informative_orders": [],
            "informative_pair_indices": [],
        }

    observed, informative, indices = [], [], []
    for i, (a, b) in enumerate(zip(rel[:-1], rel[1:])):
        if a > 0.0 and b > 0.0:
            order = float(np.log(a / b) / np.log(dt[i] / dt[i + 1]))
        elif a == 0.0 and b == 0.0:
            order = float("nan")
        elif b == 0.0:
            order = float("inf")
        else:
            order = float("-inf")
        observed.append(order)
        if a >= floor and b >= floor:
            informative.append(order)
            indices.append(i)

    effective = np.maximum(rel, floor)
    monotone = bool(np.all(effective[:-1] >= effective[1:]))
    if bool(np.all(rel < floor)):
        passed, mode = True, "PASS_AT_ROUNDOFF_FLOOR"
    elif informative:
        order_ok = bool(all(np.isfinite(o) and lo <= o <= hi for o in informative))
        passed = monotone and order_ok
        mode = (
            "ORDER_FIT"
            if passed
            else "FAIL_NONMONOTONE_REFINEMENT"
            if not monotone
            else "FAIL_ORDER_OUT_OF_RANGE"
        )
    else:
        entered_floor = bool(np.any(rel[:-1] >= floor) and rel[-1] < floor)
        passed = monotone and entered_floor
        mode = "PASS_ENTERED_ROUNDOFF_FLOOR" if passed else "FAIL_NO_ORDER_EVIDENCE_ABOVE_FLOOR"
    return {
        "passed": passed,
        "mode": mode,
        "dt_order_valid": valid_dt,
        "dt_ratio_valid": ratio_valid,
        "observed_orders": observed,
        "informative_orders": informative,
        "informative_pair_indices": indices,
        "monotone_to_floor": monotone,
    }


def ledger_timeseries_columns(ledger: dict) -> dict:
    """Flatten the unit-safe ledger for a tabular time series."""
    cols = {"t_s": ledger["t_s"]}
    for key, labels in (
        ("P_I_kg_m_s", ("x", "y", "z")),
        ("H_O_I_N_m_s", ("x", "y", "z")),
        ("R_P_I_kg_m_s", ("x", "y", "z")),
        ("R_H_O_I_N_m_s", ("x", "y", "z")),
    ):
        for i, axis in enumerate(labels):
            cols[f"{key}_{axis}"] = ledger[key][:, i]
    for key in (
        "norm_R_P_kg_m_s",
        "norm_R_H_N_m_s",
        "epsilon_P",
        "epsilon_H",
    ):
        cols[key] = ledger[key]
    cols["P_I_norm_kg_m_s"] = np.linalg.norm(ledger["P_I_kg_m_s"], axis=1)
    cols["H_O_I_norm_N_m_s"] = np.linalg.norm(ledger["H_O_I_N_m_s"], axis=1)
    return cols
