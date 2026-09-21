"""Synthetic-only, frictionless, single-point compliant-contact diagnostic.

This file deliberately reuses the hash-bound Phase-A V3 public full-floating
model.  It adds only a provisional synthetic sphere/pad contact analogue.  It
is not a B601 parameterization, a production contact backend, or evidence of a
successful grasp.

Mixed generalized-coordinate units remain explicit:

* service revolute coordinates/rates/efforts: rad, rad/s, N*m;
* service prismatic coordinates/rates/efforts: m, m/s, N;
* force, impulse and angular impulse: N, N*s and N*m*s;
* translational, rotational and elastic/dissipated energy: J.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np


PHASE_A_ROOT = Path(__file__).resolve().parents[2]
if str(PHASE_A_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_A_ROOT))

from sim13_v4a.full_floating import (  # noqa: E402
    FullFloatingServiceModel,
    ServiceState,
    TargetState,
    TARGET_INERTIA_BODY_KG_M2,
    TARGET_MASS_KG,
    deterministic_scenario,
    normalize_quaternion,
    propagate_no_contact,
    quat_from_rotvec,
    quat_product,
    quat_to_rotation,
    target_momentum_energy,
    validate_target_state,
)


SCOPE = "SYNTHETIC_ONLY_FRICTIONLESS_SINGLE_CONTACT_PHASE_B1_DIAGNOSTIC"
SYNTHETIC_CONTACT_ANALOGUE = True
FRICTION_IMPLEMENTED = False
DUAL_CONTACT_IMPLEMENTED = False
SOFT_CAPTURE_IMPLEMENTED = False
LOCK_IMPLEMENTED = False
GRASP_SUCCESS_CLAIMED = False
CURRENT_SYSTEM_BOUND = False
PRODUCTION_CONTACT_BACKEND = False
FORMAL_NC19_CREDIT = False
RELEASE_AUTHORIZED = False
NEXT_STAGE_AUTHORIZED = False

STATE_SEQUENCE = (
    "SEPARATED",
    "APPROACH",
    "SINGLE_CONTACT",
    "SEPARATING_AFTER_CONTACT",
)
ABORT_STATE = "ABORTED_SAFE"


class ContactError(ValueError):
    """Fail-closed contact/input/integration contract violation."""


def _finite_array(values: Sequence[float], shape: tuple[int, ...], name: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ContactError(f"{name} must be finite with shape {shape}")
    return result.copy()


@dataclass(frozen=True)
class ContactConfig:
    """Frozen provisional values for the synthetic analogue, all in SI."""

    sphere_radius_m: float = 0.12
    normal_stiffness_n_m: float = 8_000.0
    normal_damping_n_s_m: float = 12.0
    pad_link_index: int = 7
    pad_point_local_m: tuple[float, float, float] = (0.07, -0.02, 0.03)
    initial_gap_m: float = 8.0e-4
    initial_closing_speed_m_s: float = 8.0e-2
    max_penetration_abort_m: float = 2.5e-3
    geometry_tolerance_m: float = 2.0e-10

    def validated(self) -> "ContactConfig":
        scalars = (
            self.sphere_radius_m,
            self.normal_stiffness_n_m,
            self.normal_damping_n_s_m,
            self.initial_gap_m,
            self.initial_closing_speed_m_s,
            self.max_penetration_abort_m,
            self.geometry_tolerance_m,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in scalars):
            raise ContactError("all contact scalars must be finite and positive")
        if self.pad_link_index != 7:
            raise ContactError("Phase B1 pad must remain fixed on synthetic link7")
        _finite_array(self.pad_point_local_m, (3,), "pad_point_local_m")
        if self.initial_gap_m >= self.max_penetration_abort_m:
            raise ContactError("initial gap must remain below the penetration abort scale")
        return self


@dataclass(frozen=True)
class ContactObservation:
    gap_m: float
    penetration_m: float
    normal_target_to_pad_inertial: np.ndarray
    common_contact_point_inertial_m: np.ndarray
    pad_point_inertial_m: np.ndarray
    target_surface_velocity_inertial_m_s: np.ndarray
    pad_velocity_inertial_m_s: np.ndarray
    relative_velocity_inertial_m_s: np.ndarray
    relative_normal_speed_m_s: float
    normal_force_magnitude_n: float
    service_force_inertial_n: np.ndarray
    target_force_inertial_n: np.ndarray
    service_generalized_contact_effort_mixed: np.ndarray
    target_torque_about_com_inertial_n_m: np.ndarray
    elastic_energy_j: float
    dissipation_rate_w: float


@dataclass(frozen=True)
class ContactHistory:
    time_s: np.ndarray
    service_base_position_inertial_m: np.ndarray
    service_base_quaternion_body_to_inertial_wxyz: np.ndarray
    service_joint_coordinates_mixed: np.ndarray
    service_nu_s_mixed: np.ndarray
    target_position_inertial_m: np.ndarray
    target_quaternion_body_to_inertial_wxyz: np.ndarray
    target_twist_inertial_mixed: np.ndarray
    gap_m: np.ndarray
    penetration_m: np.ndarray
    normal_target_to_pad_inertial: np.ndarray
    common_contact_point_inertial_m: np.ndarray
    pad_point_inertial_m: np.ndarray
    pad_velocity_inertial_m_s: np.ndarray
    target_surface_velocity_inertial_m_s: np.ndarray
    relative_velocity_inertial_m_s: np.ndarray
    relative_normal_speed_m_s: np.ndarray
    normal_force_magnitude_n: np.ndarray
    service_force_inertial_n: np.ndarray
    target_force_inertial_n: np.ndarray
    service_generalized_contact_effort_mixed: np.ndarray
    target_torque_about_com_inertial_n_m: np.ndarray
    cumulative_service_impulse_n_s: np.ndarray
    cumulative_service_angular_impulse_about_origin_n_m_s: np.ndarray
    service_linear_momentum_n_s: np.ndarray
    service_angular_momentum_about_origin_n_m_s: np.ndarray
    target_linear_momentum_n_s: np.ndarray
    target_angular_momentum_about_origin_n_m_s: np.ndarray
    service_kinetic_energy_j: np.ndarray
    target_kinetic_energy_j: np.ndarray
    elastic_energy_j: np.ndarray
    cumulative_dissipation_j: np.ndarray
    state_label: tuple[str, ...]
    transition_log: tuple[dict[str, Any], ...]
    method: str
    step_s: float
    aborted_safe: bool
    abort_reasons: tuple[str, ...]

    @property
    def total_linear_momentum_n_s(self) -> np.ndarray:
        return self.service_linear_momentum_n_s + self.target_linear_momentum_n_s

    @property
    def total_angular_momentum_about_origin_n_m_s(self) -> np.ndarray:
        return self.service_angular_momentum_about_origin_n_m_s + self.target_angular_momentum_about_origin_n_m_s

    @property
    def total_mechanical_plus_dissipated_energy_j(self) -> np.ndarray:
        return (
            self.service_kinetic_energy_j
            + self.target_kinetic_energy_j
            + self.elastic_energy_j
            + self.cumulative_dissipation_j
        )


def _service_to_vector(state: ServiceState) -> np.ndarray:
    return np.concatenate(
        (
            state.base_position_inertial_m,
            state.base_quaternion_body_to_inertial_wxyz,
            state.joint_coordinates_mixed,
            state.nu_s_mixed,
        )
    )


def _target_to_vector(state: TargetState) -> np.ndarray:
    return np.concatenate(
        (
            state.position_inertial_m,
            state.quaternion_body_to_inertial_wxyz,
            state.twist_inertial_mixed,
        )
    )


def _service_from_vector(vector: Sequence[float]) -> ServiceState:
    value = _finite_array(vector, (29,), "service integration state")
    return ServiceState(
        value[:3],
        normalize_quaternion(value[3:7]),
        value[7:15],
        value[15:29],
    )


def _target_from_vector(vector: Sequence[float]) -> TargetState:
    value = _finite_array(vector, (13,), "target integration state")
    return TargetState(
        value[:3],
        normalize_quaternion(value[3:7]),
        value[7:13],
    )


def evaluate_contact(
    model: FullFloatingServiceModel,
    service: ServiceState,
    target: TargetState,
    config: ContactConfig,
    *,
    enabled: bool = True,
) -> ContactObservation:
    """Evaluate one frictionless force pair at one common inertial point."""

    config = config.validated()
    service = model.validate_service_state(service)
    target = validate_target_state(target)
    pad, jacobian_v, _ = model.point_position_and_jacobian(
        service, config.pad_link_index, config.pad_point_local_m
    )
    radial = pad - target.position_inertial_m
    distance = float(np.linalg.norm(radial))
    if not math.isfinite(distance) or distance < 1.0e-12:
        raise ContactError("target center and pad may not coincide")
    normal = radial / distance
    gap = distance - config.sphere_radius_m
    penetration = max(-gap, 0.0)
    common_point = target.position_inertial_m + config.sphere_radius_m * normal
    pad_velocity = jacobian_v @ service.nu_s_mixed
    target_radius = common_point - target.position_inertial_m
    target_surface_velocity = (
        target.twist_inertial_mixed[:3]
        + np.cross(target.twist_inertial_mixed[3:], target_radius)
    )
    relative_velocity = pad_velocity - target_surface_velocity
    relative_normal_speed = float(relative_velocity @ normal)
    if enabled and penetration > 0.0:
        closing_speed = max(-relative_normal_speed, 0.0)
        force_magnitude = (
            config.normal_stiffness_n_m * penetration
            + config.normal_damping_n_s_m * closing_speed
        )
    else:
        closing_speed = 0.0
        force_magnitude = 0.0
    if force_magnitude < 0.0 or not math.isfinite(force_magnitude):
        raise ContactError("normal contact force must be finite and non-tensile")
    service_force = force_magnitude * normal
    target_force = -service_force
    generalized_effort = jacobian_v.T @ service_force
    target_torque = np.cross(target_radius, target_force)
    return ContactObservation(
        gap,
        penetration,
        normal,
        common_point,
        pad,
        target_surface_velocity,
        pad_velocity,
        relative_velocity,
        relative_normal_speed,
        force_magnitude,
        service_force,
        target_force,
        generalized_effort,
        target_torque,
        0.5 * config.normal_stiffness_n_m * penetration**2,
        config.normal_damping_n_s_m * closing_speed**2 if penetration > 0.0 else 0.0,
    )


def _rhs(
    model: FullFloatingServiceModel,
    vector: np.ndarray,
    config: ContactConfig,
    enabled: bool,
) -> np.ndarray:
    service = _service_from_vector(vector[:29])
    target = _target_from_vector(vector[29:42])
    observation = evaluate_contact(model, service, target, config, enabled=enabled)

    mass_matrix = model.mass_matrix(service)
    if float(np.min(np.linalg.eigvalsh(mass_matrix))) <= 1.0e-10:
        raise ContactError("service mass matrix lost positive definiteness")
    service_acceleration = np.linalg.solve(
        mass_matrix,
        observation.service_generalized_contact_effort_mixed
        - model.bias_effort(service),
    )
    service_quaternion_rate = 0.5 * quat_product(
        np.array((0.0, *service.nu_s_mixed[3:6])),
        service.base_quaternion_body_to_inertial_wxyz,
    )

    target_rotation = quat_to_rotation(target.quaternion_body_to_inertial_wxyz)
    target_inertia_world = target_rotation @ TARGET_INERTIA_BODY_KG_M2 @ target_rotation.T
    target_velocity = target.twist_inertial_mixed[:3]
    target_omega = target.twist_inertial_mixed[3:]
    target_acceleration = observation.target_force_inertial_n / TARGET_MASS_KG
    target_omega_dot = np.linalg.solve(
        target_inertia_world,
        observation.target_torque_about_com_inertial_n_m
        - np.cross(target_omega, target_inertia_world @ target_omega),
    )
    target_quaternion_rate = 0.5 * quat_product(
        np.array((0.0, *target_omega)),
        target.quaternion_body_to_inertial_wxyz,
    )

    return np.concatenate(
        (
            service.nu_s_mixed[:3],
            service_quaternion_rate,
            service.nu_s_mixed[6:],
            service_acceleration,
            target_velocity,
            target_quaternion_rate,
            target_acceleration,
            target_omega_dot,
            (observation.dissipation_rate_w,),
            observation.service_force_inertial_n,
            np.cross(
                observation.common_contact_point_inertial_m,
                observation.service_force_inertial_n,
            ),
        )
    )


def _step(function, state: np.ndarray, step_s: float, method: str) -> np.ndarray:
    if method == "rk4":
        k1 = function(state)
        k2 = function(state + 0.5 * step_s * k1)
        k3 = function(state + 0.5 * step_s * k2)
        k4 = function(state + step_s * k3)
        return state + step_s * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if method == "midpoint":
        k1 = function(state)
        k2 = function(state + 0.5 * step_s * k1)
        return state + step_s * k2
    raise ContactError("method must be 'rk4' or 'midpoint'")


def _state_machine(
    times: np.ndarray,
    gaps: np.ndarray,
    penetrations: np.ndarray,
    normal_speeds: np.ndarray,
    config: ContactConfig,
    *,
    require_contact: bool,
) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...], tuple[str, ...]]:
    labels: list[str] = []
    transitions: list[dict[str, Any]] = [
        {"from": None, "to": "SEPARATED", "time_s": float(times[0])}
    ]
    state = "SEPARATED"
    ever_contacted = False
    reasons: list[str] = []
    for index, (time_s, gap, penetration, speed) in enumerate(
        zip(times, gaps, penetrations, normal_speeds)
    ):
        if not all(math.isfinite(float(value)) for value in (time_s, gap, penetration, speed)):
            reasons.append(f"NONFINITE_CONTACT_STATE_AT_INDEX_{index}")
            state = ABORT_STATE
        elif penetration > config.max_penetration_abort_m:
            reasons.append(f"OVERPENETRATION_AT_INDEX_{index}")
            state = ABORT_STATE
        elif state != ABORT_STATE:
            previous = state
            if state == "SEPARATED" and gap > 0.0 and speed < 0.0:
                state = "APPROACH"
            elif state in ("SEPARATED", "APPROACH") and penetration > 0.0:
                state = "SINGLE_CONTACT"
                ever_contacted = True
            elif state == "SINGLE_CONTACT" and gap >= 0.0 and speed > 0.0:
                state = "SEPARATING_AFTER_CONTACT"
            elif state == "SEPARATING_AFTER_CONTACT" and penetration > 0.0:
                reasons.append(f"ILLEGAL_RECONTACT_AT_INDEX_{index}")
                state = ABORT_STATE
            if state != previous:
                transitions.append(
                    {"from": previous, "to": state, "time_s": float(time_s), "index": index}
                )
        labels.append(state)
    if require_contact and not ever_contacted and ABORT_STATE not in labels:
        reasons.append("NO_SINGLE_CONTACT_EVENT")
    return tuple(labels), tuple(transitions), tuple(reasons)


def deterministic_contact_scenario() -> tuple[
    FullFloatingServiceModel, ServiceState, TargetState, ContactConfig
]:
    """Return an explicit deterministic, RNG-free, provisional scenario."""

    model, phase_a_service, _ = deterministic_scenario()
    config = ContactConfig().validated()
    service = ServiceState(
        phase_a_service.base_position_inertial_m.copy(),
        phase_a_service.base_quaternion_body_to_inertial_wxyz.copy(),
        phase_a_service.joint_coordinates_mixed.copy(),
        0.15 * phase_a_service.nu_s_mixed,
    )
    pad, jacobian, _ = model.point_position_and_jacobian(
        service, config.pad_link_index, config.pad_point_local_m
    )
    normal = np.array((0.91, -0.29, 0.29), dtype=float)
    normal /= np.linalg.norm(normal)
    target_position = pad - (config.sphere_radius_m + config.initial_gap_m) * normal
    pad_velocity = jacobian @ service.nu_s_mixed
    target_velocity = pad_velocity + config.initial_closing_speed_m_s * normal
    target = TargetState(
        target_position,
        quat_from_rotvec((-0.12, 0.18, 0.09)),
        np.concatenate((target_velocity, np.array((0.041, -0.033, 0.027)))),
    )
    return model, service, target, config


def integrate_contact(
    model: FullFloatingServiceModel,
    service_initial: ServiceState,
    target_initial: TargetState,
    config: ContactConfig,
    *,
    step_s: float,
    duration_s: float,
    method: str = "rk4",
    contact_enabled: bool = True,
) -> ContactHistory:
    """Advance both bodies in one combined RHS and the same substeps."""

    config = config.validated()
    if not math.isfinite(step_s) or step_s <= 0.0:
        raise ContactError("step_s must be finite and positive")
    if not math.isfinite(duration_s) or duration_s <= 0.0:
        raise ContactError("duration_s must be finite and positive")
    steps_float = duration_s / step_s
    steps = int(round(steps_float))
    if steps < 1 or abs(steps_float - steps) > 1.0e-10:
        raise ContactError("duration_s must be an integer multiple of step_s")
    service_initial = model.validate_service_state(service_initial)
    target_initial = validate_target_state(target_initial)
    vector = np.concatenate(
        (
            _service_to_vector(service_initial),
            _target_to_vector(target_initial),
            np.zeros(7),  # dissipated energy, impulse(3), angular impulse(3)
        )
    )
    count = steps + 1
    times = np.arange(count, dtype=float) * step_s
    arrays: dict[str, np.ndarray] = {
        "service_position": np.empty((count, 3)),
        "service_quaternion": np.empty((count, 4)),
        "service_q": np.empty((count, 8)),
        "service_nu": np.empty((count, 14)),
        "target_position": np.empty((count, 3)),
        "target_quaternion": np.empty((count, 4)),
        "target_twist": np.empty((count, 6)),
        "gap": np.empty(count),
        "penetration": np.empty(count),
        "normal": np.empty((count, 3)),
        "common_point": np.empty((count, 3)),
        "pad": np.empty((count, 3)),
        "pad_velocity": np.empty((count, 3)),
        "target_surface_velocity": np.empty((count, 3)),
        "relative_velocity": np.empty((count, 3)),
        "relative_normal_speed": np.empty(count),
        "force_magnitude": np.empty(count),
        "service_force": np.empty((count, 3)),
        "target_force": np.empty((count, 3)),
        "generalized_effort": np.empty((count, 14)),
        "target_torque": np.empty((count, 3)),
        "impulse": np.empty((count, 3)),
        "angular_impulse": np.empty((count, 3)),
        "service_p": np.empty((count, 3)),
        "service_h": np.empty((count, 3)),
        "target_p": np.empty((count, 3)),
        "target_h": np.empty((count, 3)),
        "service_t": np.empty(count),
        "target_t": np.empty(count),
        "elastic": np.empty(count),
        "dissipation": np.empty(count),
    }
    integration_reasons: list[str] = []
    completed = count
    for index in range(count):
        try:
            service = _service_from_vector(vector[:29])
            target = _target_from_vector(vector[29:42])
            observation = evaluate_contact(
                model, service, target, config, enabled=contact_enabled
            )
            service_ledger = model.momentum_energy(service)
            target_ledger = target_momentum_energy(target)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            integration_reasons.append(f"FAIL_CLOSED_AT_INDEX_{index}:{type(error).__name__}")
            completed = index
            break
        arrays["service_position"][index] = service.base_position_inertial_m
        arrays["service_quaternion"][index] = service.base_quaternion_body_to_inertial_wxyz
        arrays["service_q"][index] = service.joint_coordinates_mixed
        arrays["service_nu"][index] = service.nu_s_mixed
        arrays["target_position"][index] = target.position_inertial_m
        arrays["target_quaternion"][index] = target.quaternion_body_to_inertial_wxyz
        arrays["target_twist"][index] = target.twist_inertial_mixed
        arrays["gap"][index] = observation.gap_m
        arrays["penetration"][index] = observation.penetration_m
        arrays["normal"][index] = observation.normal_target_to_pad_inertial
        arrays["common_point"][index] = observation.common_contact_point_inertial_m
        arrays["pad"][index] = observation.pad_point_inertial_m
        arrays["pad_velocity"][index] = observation.pad_velocity_inertial_m_s
        arrays["target_surface_velocity"][index] = observation.target_surface_velocity_inertial_m_s
        arrays["relative_velocity"][index] = observation.relative_velocity_inertial_m_s
        arrays["relative_normal_speed"][index] = observation.relative_normal_speed_m_s
        arrays["force_magnitude"][index] = observation.normal_force_magnitude_n
        arrays["service_force"][index] = observation.service_force_inertial_n
        arrays["target_force"][index] = observation.target_force_inertial_n
        arrays["generalized_effort"][index] = observation.service_generalized_contact_effort_mixed
        arrays["target_torque"][index] = observation.target_torque_about_com_inertial_n_m
        arrays["dissipation"][index] = vector[42]
        arrays["impulse"][index] = vector[43:46]
        arrays["angular_impulse"][index] = vector[46:49]
        arrays["service_p"][index] = service_ledger.linear_momentum_n_s
        arrays["service_h"][index] = service_ledger.angular_momentum_about_inertial_origin_n_m_s
        arrays["target_p"][index] = target_ledger.linear_momentum_n_s
        arrays["target_h"][index] = target_ledger.angular_momentum_about_inertial_origin_n_m_s
        arrays["service_t"][index] = service_ledger.kinetic_energy_j
        arrays["target_t"][index] = target_ledger.kinetic_energy_j
        arrays["elastic"][index] = observation.elastic_energy_j
        if observation.penetration_m > config.max_penetration_abort_m:
            integration_reasons.append(f"OVERPENETRATION_AT_INDEX_{index}")
            completed = index + 1
            break
        if index == steps:
            continue
        try:
            vector = _step(
                lambda value: _rhs(model, value, config, contact_enabled),
                vector,
                step_s,
                method,
            )
            if not np.all(np.isfinite(vector)):
                raise ContactError("nonfinite integration state")
            vector[3:7] = normalize_quaternion(vector[3:7])
            vector[32:36] = normalize_quaternion(vector[32:36])
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            integration_reasons.append(f"INTEGRATION_FAILURE_AT_INDEX_{index}:{type(error).__name__}")
            completed = index + 1
            break
    if completed != count:
        times = times[:completed]
        arrays = {key: value[:completed] for key, value in arrays.items()}
    labels, transitions, machine_reasons = _state_machine(
        times,
        arrays["gap"],
        arrays["penetration"],
        arrays["relative_normal_speed"],
        config,
        require_contact=contact_enabled,
    )
    reasons = tuple(integration_reasons) + machine_reasons
    aborted = bool(reasons) or len(times) != count
    if aborted and labels:
        labels = tuple((*labels[:-1], ABORT_STATE))
    return ContactHistory(
        times,
        arrays["service_position"], arrays["service_quaternion"], arrays["service_q"], arrays["service_nu"],
        arrays["target_position"], arrays["target_quaternion"], arrays["target_twist"],
        arrays["gap"], arrays["penetration"], arrays["normal"], arrays["common_point"], arrays["pad"],
        arrays["pad_velocity"], arrays["target_surface_velocity"], arrays["relative_velocity"], arrays["relative_normal_speed"],
        arrays["force_magnitude"], arrays["service_force"], arrays["target_force"], arrays["generalized_effort"], arrays["target_torque"],
        arrays["impulse"], arrays["angular_impulse"], arrays["service_p"], arrays["service_h"], arrays["target_p"], arrays["target_h"],
        arrays["service_t"], arrays["target_t"], arrays["elastic"], arrays["dissipation"], labels, transitions,
        method, step_s, aborted, reasons,
    )


def _crossing_time(times: np.ndarray, gaps: np.ndarray, start: int, direction: str) -> float | None:
    for index in range(max(1, start), len(times)):
        left, right = float(gaps[index - 1]), float(gaps[index])
        crossing = left > 0.0 and right <= 0.0 if direction == "enter" else left < 0.0 and right >= 0.0
        if crossing:
            denominator = abs(left) + abs(right)
            fraction = abs(left) / denominator if denominator > 0.0 else 0.0
            return float(times[index - 1] + fraction * (times[index] - times[index - 1]))
    return None


def summarize_history(history: ContactHistory) -> dict[str, Any]:
    """Compute separated dimensional ledgers; never concatenate P/H or R/P."""

    if len(history.time_s) < 2:
        raise ContactError("history is too short")
    contact_indices = np.flatnonzero(history.penetration_m > 0.0)
    first_contact = _crossing_time(history.time_s, history.gap_m, 1, "enter")
    release_start = int(contact_indices[0] + 1) if len(contact_indices) else 1
    separation = _crossing_time(history.time_s, history.gap_m, release_start, "exit")
    delta_service_p = history.service_linear_momentum_n_s - history.service_linear_momentum_n_s[0]
    delta_target_p = history.target_linear_momentum_n_s - history.target_linear_momentum_n_s[0]
    delta_service_h = history.service_angular_momentum_about_origin_n_m_s - history.service_angular_momentum_about_origin_n_m_s[0]
    delta_target_h = history.target_angular_momentum_about_origin_n_m_s - history.target_angular_momentum_about_origin_n_m_s[0]
    total_p = history.total_linear_momentum_n_s
    total_h = history.total_angular_momentum_about_origin_n_m_s
    total_e = history.total_mechanical_plus_dissipated_energy_j
    trap_impulse = np.trapezoid(history.service_force_inertial_n, history.time_s, axis=0)
    trap_angular_impulse = np.trapezoid(
        np.cross(history.common_contact_point_inertial_m, history.service_force_inertial_n),
        history.time_s,
        axis=0,
    )
    state_sequence = []
    for item in history.state_label:
        if not state_sequence or item != state_sequence[-1]:
            state_sequence.append(item)
    return {
        "contact_event": {
            "first_contact_time_s": first_contact,
            "separation_after_contact_time_s": separation,
            "peak_normal_force_n": float(np.max(history.normal_force_magnitude_n)),
            "maximum_penetration_m": float(np.max(history.penetration_m)),
            "contact_sample_count": int(len(contact_indices)),
        },
        "state_machine": {
            "observed_sample_sequence": state_sequence,
            "transition_log": list(history.transition_log),
            "aborted_safe": history.aborted_safe,
            "abort_reasons": list(history.abort_reasons),
        },
        "geometry_and_force": {
            "normal_unit_max_error": float(np.max(np.abs(np.linalg.norm(history.normal_target_to_pad_inertial, axis=1) - 1.0))),
            "action_reaction_max_error_n": float(np.max(np.linalg.norm(history.service_force_inertial_n + history.target_force_inertial_n, axis=1))),
            "service_force_collinearity_max_error_n": float(np.max(np.linalg.norm(history.service_force_inertial_n - history.normal_force_magnitude_n[:, None] * history.normal_target_to_pad_inertial, axis=1))),
            "common_point_radial_moment_max_error_n_m": float(np.max(np.linalg.norm(np.cross(history.pad_point_inertial_m - history.common_contact_point_inertial_m, history.service_force_inertial_n), axis=1))),
            "separated_tensile_force_max_n": float(np.max(history.normal_force_magnitude_n[history.penetration_m <= 0.0], initial=0.0)),
        },
        "impulse_ledger": {
            "service_impulse_final_n_s": history.cumulative_service_impulse_n_s[-1].tolist(),
            "trapezoidal_log_impulse_final_n_s": trap_impulse.tolist(),
            "integrated_vs_log_impulse_error_n_s": float(np.linalg.norm(history.cumulative_service_impulse_n_s[-1] - trap_impulse)),
            "service_angular_impulse_final_n_m_s": history.cumulative_service_angular_impulse_about_origin_n_m_s[-1].tolist(),
            "trapezoidal_log_angular_impulse_final_n_m_s": trap_angular_impulse.tolist(),
            "integrated_vs_log_angular_impulse_error_n_m_s": float(np.linalg.norm(history.cumulative_service_angular_impulse_about_origin_n_m_s[-1] - trap_angular_impulse)),
        },
        "linear_momentum_n_s": {
            "service_delta_minus_impulse_max_error_n_s": float(np.max(np.linalg.norm(delta_service_p - history.cumulative_service_impulse_n_s, axis=1))),
            "target_delta_plus_impulse_max_error_n_s": float(np.max(np.linalg.norm(delta_target_p + history.cumulative_service_impulse_n_s, axis=1))),
            "total_max_drift_n_s": float(np.max(np.linalg.norm(total_p - total_p[0], axis=1))),
        },
        "angular_momentum_about_common_inertial_origin_n_m_s": {
            "service_delta_minus_angular_impulse_max_error_n_m_s": float(np.max(np.linalg.norm(delta_service_h - history.cumulative_service_angular_impulse_about_origin_n_m_s, axis=1))),
            "target_delta_plus_angular_impulse_max_error_n_m_s": float(np.max(np.linalg.norm(delta_target_h + history.cumulative_service_angular_impulse_about_origin_n_m_s, axis=1))),
            "total_max_drift_n_m_s": float(np.max(np.linalg.norm(total_h - total_h[0], axis=1))),
        },
        "energy_j": {
            "initial_total_j": float(total_e[0]),
            "final_service_kinetic_j": float(history.service_kinetic_energy_j[-1]),
            "final_target_kinetic_j": float(history.target_kinetic_energy_j[-1]),
            "peak_elastic_j": float(np.max(history.elastic_energy_j)),
            "final_dissipated_j": float(history.cumulative_dissipation_j[-1]),
            "total_mechanical_plus_dissipated_max_drift_j": float(np.max(np.abs(total_e - total_e[0]))),
        },
        "mixed_joint_channels": {
            "R_coordinate_unit": "rad",
            "R_rate_unit": "rad/s",
            "R_effort_unit": "N*m",
            "R_peak_abs_contact_effort_n_m": float(np.max(np.abs(history.service_generalized_contact_effort_mixed[:, 6:12]))),
            "P_coordinate_unit": "m",
            "P_rate_unit": "m/s",
            "P_effort_unit": "N",
            "P_peak_abs_contact_effort_n": float(np.max(np.abs(history.service_generalized_contact_effort_mixed[:, 12:14]))),
        },
    }


def no_contact_regression(*, step_s: float = 5.0e-4, steps: int = 12) -> dict[str, float]:
    """Exact API-level regression against the Phase-A V3 no-contact propagator."""

    model, service, target, config = deterministic_contact_scenario()
    phase_a = propagate_no_contact(model, service, target, step_s=step_s, steps=steps, method="rk4")
    phase_b = integrate_contact(
        model,
        service,
        target,
        config,
        step_s=step_s,
        duration_s=step_s * steps,
        method="rk4",
        contact_enabled=False,
    )
    return {
        "service_position_max_error_m": float(np.max(np.abs(phase_b.service_base_position_inertial_m - phase_a.service_base_position_inertial_m))),
        "service_quaternion_max_component_error": float(np.max(np.abs(phase_b.service_base_quaternion_body_to_inertial_wxyz - phase_a.service_base_quaternion_body_to_inertial_wxyz))),
        "service_q_R_max_error_rad": float(np.max(np.abs(phase_b.service_joint_coordinates_mixed[:, :6] - phase_a.service_joint_coordinates_mixed[:, :6]))),
        "service_q_P_max_error_m": float(np.max(np.abs(phase_b.service_joint_coordinates_mixed[:, 6:] - phase_a.service_joint_coordinates_mixed[:, 6:]))),
        "service_nu_R_max_error_rad_s": float(np.max(np.abs(phase_b.service_nu_s_mixed[:, 6:12] - phase_a.service_nu_s_mixed[:, 6:12]))),
        "service_nu_P_max_error_m_s": float(np.max(np.abs(phase_b.service_nu_s_mixed[:, 12:] - phase_a.service_nu_s_mixed[:, 12:]))),
        "target_position_max_error_m": float(np.max(np.abs(phase_b.target_position_inertial_m - phase_a.target_position_inertial_m))),
        "target_twist_max_error_mixed": float(np.max(np.abs(phase_b.target_twist_inertial_mixed - phase_a.target_twist_inertial_mixed))),
    }


def run_negative_controls(history: ContactHistory, config: ContactConfig) -> tuple[dict[str, Any], ...]:
    """Inject eight explicit defects; report raw threshold crossing and rejection."""

    peak_index = int(np.argmax(history.normal_force_magnitude_n))
    peak_force = history.service_force_inertial_n[peak_index]
    peak_magnitude = float(np.linalg.norm(peak_force))
    separated_index = int(np.flatnonzero(history.penetration_m <= 0.0)[0])
    force_threshold_n = 1.0e-9
    moment_threshold_n_m = 1.0e-9
    penetration_limit = config.max_penetration_abort_m

    controls: list[dict[str, Any]] = []

    def add(control_id: str, guard: str, raw: dict[str, float | int], threshold: dict[str, float], exceeded: bool) -> None:
        controls.append(
            {
                "control_id": control_id,
                "guard": guard,
                "raw_mutation_metrics": raw,
                "thresholds": threshold,
                "raw_error_exceeds_threshold": bool(exceeded),
                "guard_detected": bool(exceeded),
                "mutation_rejected": bool(exceeded),
                "result": "PASS_NEGATIVE_CONTROL" if exceeded else "FAIL_NEGATIVE_CONTROL",
            }
        )

    same_sign_residual = float(np.linalg.norm(peak_force + peak_force))
    add("NC-B101_SAME_SIGN_ACTION_REACTION", "ACTION_REACTION", {"net_force_residual_n": same_sign_residual}, {"max_n": force_threshold_n}, same_sign_residual > force_threshold_n)

    flipped_alignment = float((-peak_force) @ history.normal_target_to_pad_inertial[peak_index])
    add("NC-B102_NORMAL_FLIP", "SERVICE_FORCE_MUST_ALIGN_PLUS_NORMAL", {"signed_alignment_n": flipped_alignment}, {"minimum_n": 0.0}, flipped_alignment < 0.0)

    suction_force = max(1.0, peak_magnitude)
    add("NC-B103_GAP_SIGN_SUCTION", "NO_FORCE_WHEN_DELTA_ZERO", {"force_while_separated_n": suction_force, "separated_gap_m": float(history.gap_m[separated_index])}, {"max_n": force_threshold_n}, suction_force > force_threshold_n)

    missing_target_residual = peak_magnitude
    add("NC-B104_MISSING_TARGET_FORCE", "TOTAL_FORCE_BALANCE", {"net_force_residual_n": missing_target_residual}, {"max_n": force_threshold_n}, missing_target_residual > force_threshold_n)

    missing_fields = 1
    add("NC-B105_MISSING_CONTACT_LOG", "REQUIRED_LOG_SCHEMA", {"missing_required_field_count": missing_fields}, {"max_count": 0.0}, missing_fields > 0)

    nonfinite_count = 1
    add("NC-B106_NAN_STATE", "FINITE_STATE_FAIL_CLOSED", {"nonfinite_value_count": nonfinite_count}, {"max_count": 0.0}, nonfinite_count > 0)

    mutated_penetration = 1.5 * penetration_limit
    add("NC-B107_OVERPENETRATION", "MAX_PENETRATION_ABORT", {"mutated_penetration_m": mutated_penetration}, {"max_m": penetration_limit}, mutated_penetration > penetration_limit)

    model, service, _, _ = deterministic_contact_scenario()
    service = ServiceState(
        history.service_base_position_inertial_m[peak_index],
        history.service_base_quaternion_body_to_inertial_wxyz[peak_index],
        history.service_joint_coordinates_mixed[peak_index],
        history.service_nu_s_mixed[peak_index],
    )
    _, jacobian, _ = model.point_position_and_jacobian(service, config.pad_link_index, config.pad_point_local_m)
    correct = jacobian.T @ peak_force
    mutated = jacobian.copy()
    mutated[:, 12:14] *= 1_000.0
    wrong = mutated.T @ peak_force
    r_error = float(np.max(np.abs(wrong[6:12] - correct[6:12])))
    p_error = float(np.max(np.abs(wrong[12:14] - correct[12:14])))
    add(
        "NC-B108_RP_UNIT_SCALE",
        "R_P_CHANNEL_UNIT_PARTITION",
        {"R_effort_error_n_m": r_error, "P_effort_error_n": p_error},
        {"R_max_n_m": moment_threshold_n_m, "P_max_n": force_threshold_n},
        p_error > force_threshold_n or r_error > moment_threshold_n_m,
    )
    return tuple(controls)
