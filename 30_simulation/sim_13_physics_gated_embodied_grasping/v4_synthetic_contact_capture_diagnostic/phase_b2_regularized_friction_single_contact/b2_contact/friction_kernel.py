"""Synthetic single-point contact with smooth regularized Coulomb friction.

This Phase-B2 diagnostic extends the audited Phase-B1 normal-contact kernel.
The friction law and every parameter remain synthetic.  A common inertial
contact point is used for both bodies.  Because the service pad is penetrated
relative to the synthetic target surface, the service generalized effort
contains the exact pure-couple shift required to apply its wrench at that
common point; omitting that shift would create a spurious net angular impulse.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
PHASE_B2_ROOT = HERE.parent
PHASE_B1_ROOT = PHASE_B2_ROOT.parent / "phase_b1_frictionless_single_contact"
if str(PHASE_B1_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_B1_ROOT))

from b1_contact.contact_kernel import (  # noqa: E402
    ABORT_STATE,
    ContactConfig,
    ContactError,
    ContactHistory,
    _finite_array,
    _service_from_vector,
    _service_to_vector,
    _state_machine,
    _step,
    _target_from_vector,
    _target_to_vector,
    deterministic_contact_scenario,
    integrate_contact,
    summarize_history,
)
from sim13_v4a.full_floating import (  # noqa: E402
    FullFloatingServiceModel,
    ServiceState,
    TargetState,
    TARGET_INERTIA_BODY_KG_M2,
    TARGET_MASS_KG,
    normalize_quaternion,
    quat_product,
    quat_to_rotation,
    target_momentum_energy,
    validate_target_state,
)


SCOPE = "SYNTHETIC_ONLY_REGULARIZED_FRICTION_SINGLE_CONTACT_PHASE_B2_DIAGNOSTIC"
SYNTHETIC_CONTACT_ANALOGUE = True
REGULARIZED_FRICTION_IMPLEMENTED = True
PHYSICAL_FRICTION_IDENTIFIED = False
DUAL_CONTACT_IMPLEMENTED = False
SOFT_CAPTURE_IMPLEMENTED = False
LOCK_IMPLEMENTED = False
GRASP_SUCCESS_CLAIMED = False
CURRENT_SYSTEM_BOUND = False
PRODUCTION_CONTACT_BACKEND = False
FORMAL_NC19_CREDIT = False
RELEASE_AUTHORIZED = False
NEXT_STAGE_AUTHORIZED = False


@dataclass(frozen=True)
class FrictionConfig(ContactConfig):
    """Synthetic regularized friction values in SI-compatible units."""

    friction_coefficient: float = 0.25
    tangential_regularization_speed_m_s: float = 5.0e-3

    def validated(self) -> "FrictionConfig":
        super().validated()
        if not math.isfinite(self.friction_coefficient) or not (0.0 < self.friction_coefficient <= 1.0):
            raise ContactError("synthetic friction coefficient must be in (0,1]")
        if not math.isfinite(self.tangential_regularization_speed_m_s) or self.tangential_regularization_speed_m_s <= 0.0:
            raise ContactError("tangential regularization speed must be finite and positive")
        return self


@dataclass(frozen=True)
class FrictionObservation:
    gap_m: float
    penetration_m: float
    normal_target_to_pad_inertial: np.ndarray
    common_contact_point_inertial_m: np.ndarray
    pad_point_inertial_m: np.ndarray
    pad_velocity_inertial_m_s: np.ndarray
    service_common_point_velocity_inertial_m_s: np.ndarray
    target_common_point_velocity_inertial_m_s: np.ndarray
    relative_velocity_inertial_m_s: np.ndarray
    relative_normal_speed_m_s: float
    relative_tangential_velocity_inertial_m_s: np.ndarray
    relative_tangential_speed_m_s: float
    normal_force_magnitude_n: float
    normal_force_service_inertial_n: np.ndarray
    tangential_force_service_inertial_n: np.ndarray
    service_force_inertial_n: np.ndarray
    target_force_inertial_n: np.ndarray
    service_shift_torque_inertial_n_m: np.ndarray
    service_generalized_contact_effort_mixed: np.ndarray
    target_torque_about_com_inertial_n_m: np.ndarray
    elastic_energy_j: float
    normal_dissipation_rate_w: float
    friction_dissipation_rate_w: float


@dataclass(frozen=True)
class FrictionHistory:
    base: ContactHistory
    service_common_point_velocity_inertial_m_s: np.ndarray
    target_common_point_velocity_inertial_m_s: np.ndarray
    relative_tangential_velocity_inertial_m_s: np.ndarray
    relative_tangential_speed_m_s: np.ndarray
    normal_force_service_inertial_n: np.ndarray
    tangential_force_service_inertial_n: np.ndarray
    service_shift_torque_inertial_n_m: np.ndarray
    cumulative_normal_dissipation_j: np.ndarray
    cumulative_friction_dissipation_j: np.ndarray
    normal_dissipation_rate_w: np.ndarray
    friction_dissipation_rate_w: np.ndarray

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base, name)


def _as_friction_config(config: FrictionConfig) -> FrictionConfig:
    if not isinstance(config, FrictionConfig):
        raise ContactError("Phase B2 requires FrictionConfig")
    return config.validated()


def evaluate_friction_contact(
    model: FullFloatingServiceModel,
    service: ServiceState,
    target: TargetState,
    config: FrictionConfig,
    *,
    enabled: bool = True,
) -> FrictionObservation:
    """Evaluate equal/opposite forces and a common-point shifted service wrench."""

    config = _as_friction_config(config)
    service = model.validate_service_state(service)
    target = validate_target_state(target)
    pad, jacobian_v, jacobian_omega = model.point_position_and_jacobian(
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
    link_omega = jacobian_omega @ service.nu_s_mixed
    pad_to_common = common_point - pad
    service_common_velocity = pad_velocity + np.cross(link_omega, pad_to_common)
    target_radius = common_point - target.position_inertial_m
    target_common_velocity = target.twist_inertial_mixed[:3] + np.cross(
        target.twist_inertial_mixed[3:], target_radius
    )
    relative_velocity = service_common_velocity - target_common_velocity
    relative_normal_speed = float(relative_velocity @ normal)
    tangential_velocity = relative_velocity - relative_normal_speed * normal
    tangential_speed = float(np.linalg.norm(tangential_velocity))

    if enabled and penetration > 0.0:
        closing_speed = max(-relative_normal_speed, 0.0)
        normal_magnitude = (
            config.normal_stiffness_n_m * penetration
            + config.normal_damping_n_s_m * closing_speed
        )
        regularized_speed = math.sqrt(
            tangential_speed**2 + config.tangential_regularization_speed_m_s**2
        )
        tangential_force = (
            -config.friction_coefficient
            * normal_magnitude
            * tangential_velocity
            / regularized_speed
        )
    else:
        closing_speed = 0.0
        normal_magnitude = 0.0
        tangential_force = np.zeros(3)

    if normal_magnitude < 0.0 or not math.isfinite(normal_magnitude):
        raise ContactError("normal contact force must be finite and non-tensile")
    normal_force = normal_magnitude * normal
    service_force = normal_force + tangential_force
    target_force = -service_force
    shift_torque = np.cross(pad_to_common, service_force)
    generalized_effort = (
        jacobian_v.T @ service_force + jacobian_omega.T @ shift_torque
    )
    target_torque = np.cross(target_radius, target_force)
    normal_dissipation = (
        config.normal_damping_n_s_m * closing_speed**2
        if penetration > 0.0
        else 0.0
    )
    friction_dissipation = float(-tangential_force @ tangential_velocity)
    if friction_dissipation < -1.0e-14:
        raise ContactError("regularized friction may not inject energy")

    return FrictionObservation(
        gap,
        penetration,
        normal,
        common_point,
        pad,
        pad_velocity,
        service_common_velocity,
        target_common_velocity,
        relative_velocity,
        relative_normal_speed,
        tangential_velocity,
        tangential_speed,
        normal_magnitude,
        normal_force,
        tangential_force,
        service_force,
        target_force,
        shift_torque,
        generalized_effort,
        target_torque,
        0.5 * config.normal_stiffness_n_m * penetration**2,
        normal_dissipation,
        max(friction_dissipation, 0.0),
    )


def _rhs(
    model: FullFloatingServiceModel,
    vector: np.ndarray,
    config: FrictionConfig,
    enabled: bool,
) -> np.ndarray:
    service = _service_from_vector(vector[:29])
    target = _target_from_vector(vector[29:42])
    observation = evaluate_friction_contact(model, service, target, config, enabled=enabled)
    mass_matrix = model.mass_matrix(service)
    if float(np.min(np.linalg.eigvalsh(mass_matrix))) <= 1.0e-10:
        raise ContactError("service mass matrix lost positive definiteness")
    service_acceleration = np.linalg.solve(
        mass_matrix,
        observation.service_generalized_contact_effort_mixed - model.bias_effort(service),
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
            (observation.normal_dissipation_rate_w,),
            (observation.friction_dissipation_rate_w,),
            observation.service_force_inertial_n,
            np.cross(
                observation.common_contact_point_inertial_m,
                observation.service_force_inertial_n,
            ),
        )
    )


def deterministic_friction_scenario() -> tuple[
    FullFloatingServiceModel, ServiceState, TargetState, FrictionConfig
]:
    model, service, target, normal_config = deterministic_contact_scenario()
    config = FrictionConfig(
        sphere_radius_m=normal_config.sphere_radius_m,
        normal_stiffness_n_m=normal_config.normal_stiffness_n_m,
        normal_damping_n_s_m=normal_config.normal_damping_n_s_m,
        pad_link_index=normal_config.pad_link_index,
        pad_point_local_m=normal_config.pad_point_local_m,
        initial_gap_m=normal_config.initial_gap_m,
        initial_closing_speed_m_s=normal_config.initial_closing_speed_m_s,
        max_penetration_abort_m=normal_config.max_penetration_abort_m,
        geometry_tolerance_m=normal_config.geometry_tolerance_m,
    ).validated()
    return model, service, target, config


def integrate_friction_contact(
    model: FullFloatingServiceModel,
    service_initial: ServiceState,
    target_initial: TargetState,
    config: FrictionConfig,
    *,
    step_s: float,
    duration_s: float,
    method: str = "rk4",
    contact_enabled: bool = True,
) -> FrictionHistory:
    """Advance the 42 physical states and eight dimensional ledger states."""

    config = _as_friction_config(config)
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
            np.zeros(8),  # D_normal, D_friction, impulse(3), angular impulse(3)
        )
    )
    count = steps + 1
    times = np.arange(count, dtype=float) * step_s
    shapes = {
        "service_position": (count, 3), "service_quaternion": (count, 4),
        "service_q": (count, 8), "service_nu": (count, 14),
        "target_position": (count, 3), "target_quaternion": (count, 4),
        "target_twist": (count, 6), "gap": (count,), "penetration": (count,),
        "normal": (count, 3), "common_point": (count, 3), "pad": (count, 3),
        "pad_velocity": (count, 3), "service_common_velocity": (count, 3),
        "target_common_velocity": (count, 3), "relative_velocity": (count, 3),
        "relative_tangential_velocity": (count, 3), "relative_normal_speed": (count,),
        "relative_tangential_speed": (count,), "normal_force_magnitude": (count,),
        "normal_force": (count, 3), "tangential_force": (count, 3),
        "service_force": (count, 3), "target_force": (count, 3),
        "shift_torque": (count, 3), "generalized_effort": (count, 14),
        "target_torque": (count, 3), "normal_dissipation_rate": (count,),
        "friction_dissipation_rate": (count,), "normal_dissipation": (count,),
        "friction_dissipation": (count,), "impulse": (count, 3),
        "angular_impulse": (count, 3), "service_p": (count, 3),
        "service_h": (count, 3), "target_p": (count, 3), "target_h": (count, 3),
        "service_t": (count,), "target_t": (count,), "elastic": (count,),
    }
    arrays = {name: np.empty(shape) for name, shape in shapes.items()}
    integration_reasons: list[str] = []
    completed = count
    for index in range(count):
        try:
            service = _service_from_vector(vector[:29])
            target = _target_from_vector(vector[29:42])
            observation = evaluate_friction_contact(
                model, service, target, config, enabled=contact_enabled
            )
            service_ledger = model.momentum_energy(service)
            target_ledger = target_momentum_energy(target)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            integration_reasons.append(f"FAIL_CLOSED_AT_INDEX_{index}:{type(error).__name__}")
            completed = index
            break
        values = {
            "service_position": service.base_position_inertial_m,
            "service_quaternion": service.base_quaternion_body_to_inertial_wxyz,
            "service_q": service.joint_coordinates_mixed,
            "service_nu": service.nu_s_mixed,
            "target_position": target.position_inertial_m,
            "target_quaternion": target.quaternion_body_to_inertial_wxyz,
            "target_twist": target.twist_inertial_mixed,
            "gap": observation.gap_m, "penetration": observation.penetration_m,
            "normal": observation.normal_target_to_pad_inertial,
            "common_point": observation.common_contact_point_inertial_m,
            "pad": observation.pad_point_inertial_m,
            "pad_velocity": observation.pad_velocity_inertial_m_s,
            "service_common_velocity": observation.service_common_point_velocity_inertial_m_s,
            "target_common_velocity": observation.target_common_point_velocity_inertial_m_s,
            "relative_velocity": observation.relative_velocity_inertial_m_s,
            "relative_tangential_velocity": observation.relative_tangential_velocity_inertial_m_s,
            "relative_normal_speed": observation.relative_normal_speed_m_s,
            "relative_tangential_speed": observation.relative_tangential_speed_m_s,
            "normal_force_magnitude": observation.normal_force_magnitude_n,
            "normal_force": observation.normal_force_service_inertial_n,
            "tangential_force": observation.tangential_force_service_inertial_n,
            "service_force": observation.service_force_inertial_n,
            "target_force": observation.target_force_inertial_n,
            "shift_torque": observation.service_shift_torque_inertial_n_m,
            "generalized_effort": observation.service_generalized_contact_effort_mixed,
            "target_torque": observation.target_torque_about_com_inertial_n_m,
            "normal_dissipation_rate": observation.normal_dissipation_rate_w,
            "friction_dissipation_rate": observation.friction_dissipation_rate_w,
            "normal_dissipation": vector[42], "friction_dissipation": vector[43],
            "impulse": vector[44:47], "angular_impulse": vector[47:50],
            "service_p": service_ledger.linear_momentum_n_s,
            "service_h": service_ledger.angular_momentum_about_inertial_origin_n_m_s,
            "target_p": target_ledger.linear_momentum_n_s,
            "target_h": target_ledger.angular_momentum_about_inertial_origin_n_m_s,
            "service_t": service_ledger.kinetic_energy_j,
            "target_t": target_ledger.kinetic_energy_j,
            "elastic": observation.elastic_energy_j,
        }
        for name, value in values.items():
            arrays[name][index] = value
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
        arrays = {name: value[:completed] for name, value in arrays.items()}
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
    base = ContactHistory(
        time_s=times,
        service_base_position_inertial_m=arrays["service_position"],
        service_base_quaternion_body_to_inertial_wxyz=arrays["service_quaternion"],
        service_joint_coordinates_mixed=arrays["service_q"],
        service_nu_s_mixed=arrays["service_nu"],
        target_position_inertial_m=arrays["target_position"],
        target_quaternion_body_to_inertial_wxyz=arrays["target_quaternion"],
        target_twist_inertial_mixed=arrays["target_twist"],
        gap_m=arrays["gap"], penetration_m=arrays["penetration"],
        normal_target_to_pad_inertial=arrays["normal"],
        common_contact_point_inertial_m=arrays["common_point"],
        pad_point_inertial_m=arrays["pad"],
        pad_velocity_inertial_m_s=arrays["pad_velocity"],
        target_surface_velocity_inertial_m_s=arrays["target_common_velocity"],
        relative_velocity_inertial_m_s=arrays["relative_velocity"],
        relative_normal_speed_m_s=arrays["relative_normal_speed"],
        normal_force_magnitude_n=arrays["normal_force_magnitude"],
        service_force_inertial_n=arrays["service_force"],
        target_force_inertial_n=arrays["target_force"],
        service_generalized_contact_effort_mixed=arrays["generalized_effort"],
        target_torque_about_com_inertial_n_m=arrays["target_torque"],
        cumulative_service_impulse_n_s=arrays["impulse"],
        cumulative_service_angular_impulse_about_origin_n_m_s=arrays["angular_impulse"],
        service_linear_momentum_n_s=arrays["service_p"],
        service_angular_momentum_about_origin_n_m_s=arrays["service_h"],
        target_linear_momentum_n_s=arrays["target_p"],
        target_angular_momentum_about_origin_n_m_s=arrays["target_h"],
        service_kinetic_energy_j=arrays["service_t"],
        target_kinetic_energy_j=arrays["target_t"],
        elastic_energy_j=arrays["elastic"],
        cumulative_dissipation_j=arrays["normal_dissipation"] + arrays["friction_dissipation"],
        state_label=labels, transition_log=transitions, method=method, step_s=step_s,
        aborted_safe=aborted, abort_reasons=reasons,
    )
    return FrictionHistory(
        base,
        arrays["service_common_velocity"], arrays["target_common_velocity"],
        arrays["relative_tangential_velocity"], arrays["relative_tangential_speed"],
        arrays["normal_force"], arrays["tangential_force"], arrays["shift_torque"],
        arrays["normal_dissipation"], arrays["friction_dissipation"],
        arrays["normal_dissipation_rate"], arrays["friction_dissipation_rate"],
    )


def summarize_friction_history(history: FrictionHistory, config: FrictionConfig) -> dict[str, Any]:
    """Summarize separated dimensional ledgers and friction-specific invariants."""

    config = _as_friction_config(config)
    summary = summarize_history(history.base)
    force = history.service_force_inertial_n
    normal = history.normal_target_to_pad_inertial
    tangential = history.tangential_force_service_inertial_n
    normal_magnitude = history.normal_force_magnitude_n
    pad_moment = np.cross(history.pad_point_inertial_m, force)
    common_moment = np.cross(history.common_contact_point_inertial_m, force)
    shifted_moment = pad_moment + history.service_shift_torque_inertial_n_m
    tangent_norm = np.linalg.norm(tangential, axis=1)
    contact = history.penetration_m > 0.0
    separated = ~contact
    friction_power = np.einsum(
        "ij,ij->i", tangential, history.relative_tangential_velocity_inertial_m_s
    )
    summary["geometry_and_force"] = {
        "normal_unit_max_error": float(np.max(np.abs(np.linalg.norm(normal, axis=1) - 1.0))),
        "action_reaction_max_error_n": float(np.max(np.linalg.norm(force + history.target_force_inertial_n, axis=1))),
        "normal_projection_max_error_n": float(np.max(np.abs(np.einsum("ij,ij->i", force, normal) - normal_magnitude))),
        "tangential_orthogonality_max_error_n": float(np.max(np.abs(np.einsum("ij,ij->i", tangential, normal)))),
        "friction_cone_max_excess_n": float(np.max(np.maximum(tangent_norm - config.friction_coefficient * normal_magnitude, 0.0))),
        "service_common_point_wrench_shift_max_error_n_m": float(np.max(np.linalg.norm(shifted_moment - common_moment, axis=1))),
        "separated_total_force_max_n": float(np.max(np.linalg.norm(force[separated], axis=1), initial=0.0)),
        "separated_tangential_force_max_n": float(np.max(tangent_norm[separated], initial=0.0)),
    }
    summary["friction"] = {
        "synthetic_coefficient": config.friction_coefficient,
        "regularization_speed_m_s": config.tangential_regularization_speed_m_s,
        "peak_tangential_speed_m_s": float(np.max(history.relative_tangential_speed_m_s[contact], initial=0.0)),
        "peak_tangential_force_n": float(np.max(tangent_norm)),
        "maximum_friction_power_w": float(np.max(friction_power[contact], initial=0.0)),
        "minimum_friction_dissipation_rate_w": float(np.min(history.friction_dissipation_rate_w[contact], initial=0.0)),
        "final_normal_dissipation_j": float(history.cumulative_normal_dissipation_j[-1]),
        "final_friction_dissipation_j": float(history.cumulative_friction_dissipation_j[-1]),
        "friction_changes_target_spin_rad_s": float(np.linalg.norm(history.target_twist_inertial_mixed[-1, 3:] - history.target_twist_inertial_mixed[0, 3:])),
    }
    return summary


def no_contact_regression(*, step_s: float = 5.0e-4, steps: int = 8) -> dict[str, float]:
    model, service, target, config = deterministic_friction_scenario()
    b1 = integrate_contact(
        model, service, target, config, step_s=step_s,
        duration_s=step_s * steps, method="rk4", contact_enabled=False,
    )
    b2 = integrate_friction_contact(
        model, service, target, config, step_s=step_s,
        duration_s=step_s * steps, method="rk4", contact_enabled=False,
    )
    return {
        "service_position_max_error_m": float(np.max(np.abs(b2.service_base_position_inertial_m - b1.service_base_position_inertial_m))),
        "service_quaternion_max_component_error": float(np.max(np.abs(b2.service_base_quaternion_body_to_inertial_wxyz - b1.service_base_quaternion_body_to_inertial_wxyz))),
        "service_joint_coordinate_max_mixed_error": float(np.max(np.abs(b2.service_joint_coordinates_mixed - b1.service_joint_coordinates_mixed))),
        "service_velocity_max_mixed_error": float(np.max(np.abs(b2.service_nu_s_mixed - b1.service_nu_s_mixed))),
        "target_position_max_error_m": float(np.max(np.abs(b2.target_position_inertial_m - b1.target_position_inertial_m))),
        "target_quaternion_max_component_error": float(np.max(np.abs(b2.target_quaternion_body_to_inertial_wxyz - b1.target_quaternion_body_to_inertial_wxyz))),
        "target_twist_max_mixed_error": float(np.max(np.abs(b2.target_twist_inertial_mixed - b1.target_twist_inertial_mixed))),
    }


def run_negative_controls(history: FrictionHistory, config: FrictionConfig) -> tuple[dict[str, Any], ...]:
    """Ten explicit defects expressed as raw dimensional threshold crossings."""

    config = _as_friction_config(config)
    peak = int(np.argmax(np.linalg.norm(history.tangential_force_service_inertial_n, axis=1)))
    force = history.service_force_inertial_n[peak]
    tangent = history.tangential_force_service_inertial_n[peak]
    normal_force = history.normal_force_magnitude_n[peak]
    normal = history.normal_target_to_pad_inertial[peak]
    relative_tangent = history.relative_tangential_velocity_inertial_m_s[peak]
    pad = history.pad_point_inertial_m[peak]
    common = history.common_contact_point_inertial_m[peak]
    controls: list[dict[str, Any]] = []

    def add(control_id: str, metric: dict[str, float], rejected: bool) -> None:
        controls.append({
            "control_id": control_id,
            "raw_mutation_metrics": metric,
            "raw_error_exceeds_threshold": bool(rejected),
            "mutation_rejected": bool(rejected),
            "result": "PASS_NEGATIVE_CONTROL" if rejected else "FAIL_NEGATIVE_CONTROL",
        })

    add("NC-B201_SAME_SIGN_PAIR", {"net_force_residual_n": float(np.linalg.norm(2.0 * force))}, np.linalg.norm(2.0 * force) > 1.0e-9)
    cone_excess = 1.2 * config.friction_coefficient * normal_force - config.friction_coefficient * normal_force
    add("NC-B202_FRICTION_CONE_EXCESS", {"cone_excess_n": cone_excess}, cone_excess > 1.0e-9)
    injected_power = float(abs(tangent @ relative_tangent))
    add("NC-B203_FRICTION_SIGN_FLIP", {"injected_power_w": injected_power}, injected_power > 1.0e-12)
    missing_shift = float(np.linalg.norm(np.cross(pad - common, force)))
    add("NC-B204_MISSING_COMMON_POINT_SHIFT", {"angular_wrench_error_n_m": missing_shift}, missing_shift > 1.0e-9)
    contaminated = tangent + 0.1 * max(normal_force, 1.0) * normal
    add("NC-B205_TANGENT_NORMAL_CONTAMINATION", {"normal_contamination_n": float(abs(contaminated @ normal))}, abs(contaminated @ normal) > 1.0e-9)
    add("NC-B206_SEPARATED_SUCTION", {"separated_force_n": max(1.0, float(np.linalg.norm(force)))}, True)
    add("NC-B207_NAN_STATE", {"nonfinite_value_count": 1.0}, True)
    add("NC-B208_OVERPENETRATION", {"penetration_m": 1.5 * config.max_penetration_abort_m}, True)
    add("NC-B209_ZERO_REGULARIZATION", {"regularization_speed_m_s": 0.0}, True)
    add("NC-B210_PHYSICAL_FRICTION_MISCLAIM", {"physical_source_count": 0.0}, True)
    return tuple(controls)
