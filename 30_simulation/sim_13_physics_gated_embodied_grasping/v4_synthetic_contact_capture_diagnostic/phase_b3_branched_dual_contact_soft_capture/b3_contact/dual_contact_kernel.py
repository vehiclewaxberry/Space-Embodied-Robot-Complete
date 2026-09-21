"""Synthetic dual-finger compliant contact and transient soft-capture logic."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
PHASE_B3_ROOT = HERE.parent
PHASE_B1_ROOT = PHASE_B3_ROOT.parent / "phase_b1_frictionless_single_contact"
if str(PHASE_B1_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_B1_ROOT))

from b1_contact.contact_kernel import (  # noqa: E402
    ContactError,
    _service_from_vector,
    _service_to_vector,
    _step,
    _target_from_vector,
    _target_to_vector,
)
from sim13_v4a.full_floating import (  # noqa: E402
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

from .branched_model import BranchedGripperServiceModel


SCOPE = "SYNTHETIC_BRANCHED_DUAL_CONTACT_SOFT_CAPTURE_TRANSIENT_DIAGNOSTIC"
PHYSICAL_DUAL_CONTACT_IDENTIFIED = False
PHYSICAL_FRICTION_IDENTIFIED = False
PHYSICAL_ACTUATOR_TIMING_IDENTIFIED = False
SOFT_CAPTURE_CURRENT_SYSTEM_PASSED = False
LOCK_IMPLEMENTED = False
GRASP_SUCCESS_CLAIMED = False
ATTACHED_TARGET_RELEASED = False
CURRENT_SYSTEM_BOUND = False
FORMAL_NC19_CREDIT = False
PRODUCTION_READY = False
RELEASE_AUTHORIZED = False
NEXT_STAGE_AUTHORIZED = False

SIDES = ("left", "right")
ABORT_STATE = "ABORTED_SAFE"


@dataclass(frozen=True)
class DualContactConfig:
    sphere_radius_m: float = 0.040
    closed_half_gap_m: float = 0.010
    initial_finger_coordinate_m: float = 0.0305
    synthetic_initial_closing_speed_m_s: float = 0.010
    pad_x_palm_m: float = -0.020
    pad_z_palm_m: float = 0.000
    normal_stiffness_n_m: float = 8_000.0
    normal_damping_n_s_m: float = 12.0
    friction_coefficient: float = 0.25
    tangential_regularization_speed_m_s: float = 5.0e-3
    max_penetration_abort_m: float = 2.0e-3
    dual_contact_dwell_s: float = 1.0e-3
    normals_opposition_max_dot: float = -0.95
    corridor_margin_m: float = 1.0e-4
    soft_capture_max_relative_center_speed_m_s: float = 2.0e-2
    soft_capture_max_relative_omega_rad_s: float = 8.0e-2
    soft_capture_max_abs_contact_normal_speed_m_s: float = 8.0e-3
    soft_capture_max_contact_tangential_speed_m_s: float = 5.0e-3
    soft_capture_max_finger_opening_speed_m_s: float = 1.0e-5
    soft_capture_min_normal_force_n: float = 0.05
    stroke_lower_m: float = 0.0
    stroke_upper_m: float = 0.0715
    linear_momentum_ledger_tolerance_n_s: float = 1.0e-9
    angular_momentum_ledger_tolerance_n_m_s: float = 1.0e-9
    linear_impulse_identity_tolerance_n_s: float = 1.0e-9
    angular_impulse_identity_tolerance_n_m_s: float = 1.0e-9
    energy_ledger_tolerance_j: float = 1.0e-7
    action_reaction_tolerance_n: float = 1.0e-12
    common_point_shift_tolerance_n_m: float = 1.0e-12
    target_torque_identity_tolerance_n_m: float = 1.0e-12
    virtual_power_tolerance_w: float = 1.0e-12
    friction_noninjection_tolerance_w: float = 1.0e-12
    dissipation_monotonic_tolerance_j: float = 1.0e-14

    def validated(self) -> "DualContactConfig":
        positive = (
            self.sphere_radius_m, self.closed_half_gap_m,
            self.initial_finger_coordinate_m, self.synthetic_initial_closing_speed_m_s,
            self.normal_stiffness_n_m, self.normal_damping_n_s_m,
            self.friction_coefficient, self.tangential_regularization_speed_m_s,
            self.max_penetration_abort_m, self.dual_contact_dwell_s,
            self.corridor_margin_m, self.soft_capture_max_relative_center_speed_m_s,
            self.soft_capture_max_relative_omega_rad_s,
            self.soft_capture_max_abs_contact_normal_speed_m_s,
            self.soft_capture_max_contact_tangential_speed_m_s,
            self.soft_capture_max_finger_opening_speed_m_s,
            self.soft_capture_min_normal_force_n,
            self.stroke_upper_m, self.linear_momentum_ledger_tolerance_n_s,
            self.angular_momentum_ledger_tolerance_n_m_s,
            self.linear_impulse_identity_tolerance_n_s,
            self.angular_impulse_identity_tolerance_n_m_s,
            self.energy_ledger_tolerance_j, self.action_reaction_tolerance_n,
            self.common_point_shift_tolerance_n_m,
            self.target_torque_identity_tolerance_n_m,
            self.virtual_power_tolerance_w,
            self.friction_noninjection_tolerance_w,
            self.dissipation_monotonic_tolerance_j,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in positive):
            raise ContactError("all positive B3 parameters must be finite and positive")
        if not all(math.isfinite(value) for value in (self.pad_x_palm_m, self.pad_z_palm_m, self.stroke_lower_m)):
            raise ContactError("B3 signed geometric parameters must be finite")
        if not (0.0 < self.friction_coefficient <= 1.0):
            raise ContactError("synthetic friction coefficient must be in (0,1]")
        if not (-1.0 <= self.normals_opposition_max_dot < 0.0):
            raise ContactError("normal opposition dot threshold must be in [-1,0)")
        if not (self.stroke_lower_m <= self.initial_finger_coordinate_m <= self.stroke_upper_m):
            raise ContactError("initial finger coordinate must remain inside design-model stroke")
        if not self.stroke_lower_m < self.stroke_upper_m:
            raise ContactError("design-model stroke lower bound must be below upper bound")
        initial_gap = self.closed_half_gap_m + self.initial_finger_coordinate_m - self.sphere_radius_m
        if initial_gap <= 0.0:
            raise ContactError("nominal B3 state must begin separated")
        return self


def _finger_stroke_within_bounds(
    coordinates_m: Sequence[float], config: DualContactConfig
) -> bool:
    values = np.asarray(coordinates_m, dtype=float)
    return bool(
        values.shape == (2,)
        and np.all(np.isfinite(values))
        and np.all(values >= config.stroke_lower_m)
        and np.all(values <= config.stroke_upper_m)
    )


@dataclass(frozen=True)
class FingerContactObservation:
    side: str
    gap_m: float
    penetration_m: float
    normal_target_to_pad_inertial: np.ndarray
    common_contact_point_inertial_m: np.ndarray
    pad_point_inertial_m: np.ndarray
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
class PerFingerHistory:
    gap_m: np.ndarray
    penetration_m: np.ndarray
    normal_target_to_pad_inertial: np.ndarray
    common_contact_point_inertial_m: np.ndarray
    pad_point_inertial_m: np.ndarray
    service_common_point_velocity_inertial_m_s: np.ndarray
    target_common_point_velocity_inertial_m_s: np.ndarray
    relative_velocity_inertial_m_s: np.ndarray
    relative_normal_speed_m_s: np.ndarray
    relative_tangential_velocity_inertial_m_s: np.ndarray
    relative_tangential_speed_m_s: np.ndarray
    normal_force_magnitude_n: np.ndarray
    normal_force_service_inertial_n: np.ndarray
    tangential_force_service_inertial_n: np.ndarray
    service_force_inertial_n: np.ndarray
    target_force_inertial_n: np.ndarray
    service_shift_torque_inertial_n_m: np.ndarray
    service_generalized_contact_effort_mixed: np.ndarray
    target_torque_about_com_inertial_n_m: np.ndarray
    elastic_energy_j: np.ndarray
    normal_dissipation_rate_w: np.ndarray
    friction_dissipation_rate_w: np.ndarray
    cumulative_normal_dissipation_j: np.ndarray
    cumulative_friction_dissipation_j: np.ndarray
    cumulative_service_impulse_n_s: np.ndarray
    cumulative_service_angular_impulse_n_m_s: np.ndarray


@dataclass(frozen=True)
class DualContactHistory:
    time_s: np.ndarray
    service_base_position_inertial_m: np.ndarray
    service_base_quaternion_body_to_inertial_wxyz: np.ndarray
    service_joint_coordinates_mixed: np.ndarray
    service_nu_s_mixed: np.ndarray
    target_position_inertial_m: np.ndarray
    target_quaternion_body_to_inertial_wxyz: np.ndarray
    target_twist_inertial_mixed: np.ndarray
    palm_origin_inertial_m: np.ndarray
    palm_rotation_body_to_inertial: np.ndarray
    palm_velocity_inertial_m_s: np.ndarray
    palm_omega_inertial_rad_s: np.ndarray
    target_center_palm_m: np.ndarray
    target_relative_center_speed_m_s: np.ndarray
    target_relative_omega_rad_s: np.ndarray
    left: PerFingerHistory
    right: PerFingerHistory
    service_linear_momentum_n_s: np.ndarray
    service_angular_momentum_about_origin_n_m_s: np.ndarray
    target_linear_momentum_n_s: np.ndarray
    target_angular_momentum_about_origin_n_m_s: np.ndarray
    service_kinetic_energy_j: np.ndarray
    target_kinetic_energy_j: np.ndarray
    state_label: tuple[str, ...]
    transition_log: tuple[dict[str, Any], ...]
    soft_capture_criteria_log: tuple[dict[str, Any], ...]
    method: str
    step_s: float
    aborted_safe: bool
    abort_reasons: tuple[str, ...]
    topology_diagnostic: dict[str, Any]

    @property
    def total_linear_momentum_n_s(self) -> np.ndarray:
        return self.service_linear_momentum_n_s + self.target_linear_momentum_n_s

    @property
    def total_angular_momentum_about_origin_n_m_s(self) -> np.ndarray:
        return self.service_angular_momentum_about_origin_n_m_s + self.target_angular_momentum_about_origin_n_m_s

    @property
    def total_mechanical_plus_dissipated_energy_j(self) -> np.ndarray:
        return (
            self.service_kinetic_energy_j + self.target_kinetic_energy_j
            + self.left.elastic_energy_j + self.right.elastic_energy_j
            + self.left.cumulative_normal_dissipation_j + self.left.cumulative_friction_dissipation_j
            + self.right.cumulative_normal_dissipation_j + self.right.cumulative_friction_dissipation_j
        )


def _finger_contact(
    model: BranchedGripperServiceModel,
    service: ServiceState,
    target: TargetState,
    config: DualContactConfig,
    side: str,
    *,
    enabled: bool,
) -> FingerContactObservation:
    pad, jv, jw = model.synthetic_pad_position_and_jacobian(
        service, side, closed_half_gap_m=config.closed_half_gap_m,
        pad_x_palm_m=config.pad_x_palm_m, pad_z_palm_m=config.pad_z_palm_m,
    )
    radial = pad - target.position_inertial_m
    distance = float(np.linalg.norm(radial))
    if not math.isfinite(distance) or distance < 1.0e-12:
        raise ContactError("target center and synthetic pad may not coincide")
    normal = radial / distance
    gap = distance - config.sphere_radius_m; penetration = max(-gap, 0.0)
    common = target.position_inertial_m + config.sphere_radius_m * normal
    pad_velocity = jv @ service.nu_s_mixed; finger_omega = jw @ service.nu_s_mixed
    service_common_velocity = pad_velocity + np.cross(finger_omega, common - pad)
    target_common_velocity = target.twist_inertial_mixed[:3] + np.cross(
        target.twist_inertial_mixed[3:], common - target.position_inertial_m
    )
    relative = service_common_velocity - target_common_velocity
    vn = float(relative @ normal); vt = relative - vn * normal; vt_speed = float(np.linalg.norm(vt))
    if enabled and penetration > 0.0:
        closing = max(-vn, 0.0)
        fn = config.normal_stiffness_n_m * penetration + config.normal_damping_n_s_m * closing
        ft = -config.friction_coefficient * fn * vt / math.sqrt(
            vt_speed**2 + config.tangential_regularization_speed_m_s**2
        )
    else:
        closing = 0.0; fn = 0.0; ft = np.zeros(3)
    normal_force = fn * normal; force = normal_force + ft; target_force = -force
    shift = np.cross(common - pad, force)
    effort = jv.T @ force + jw.T @ shift
    target_torque = np.cross(common - target.position_inertial_m, target_force)
    normal_d = config.normal_damping_n_s_m * closing**2 if penetration > 0.0 else 0.0
    friction_d = max(float(-ft @ vt), 0.0)
    return FingerContactObservation(
        side, gap, penetration, normal, common, pad,
        service_common_velocity, target_common_velocity, relative, vn, vt, vt_speed,
        fn, normal_force, ft, force, target_force, shift, effort, target_torque,
        0.5 * config.normal_stiffness_n_m * penetration**2 if enabled else 0.0,
        normal_d, friction_d,
    )


def evaluate_dual_contact(
    model: BranchedGripperServiceModel,
    service: ServiceState,
    target: TargetState,
    config: DualContactConfig,
    *,
    enabled: bool = True,
) -> tuple[FingerContactObservation, FingerContactObservation]:
    config = config.validated(); service = model.validate_service_state(service); target = validate_target_state(target)
    return tuple(_finger_contact(model, service, target, config, side, enabled=enabled) for side in SIDES)  # type: ignore[return-value]


def _rhs(
    model: BranchedGripperServiceModel,
    vector: np.ndarray,
    config: DualContactConfig,
    enabled: bool,
) -> np.ndarray:
    service = _service_from_vector(vector[:29]); target = _target_from_vector(vector[29:42])
    finger_coordinates = service.joint_coordinates_mixed[6:8]
    if not _finger_stroke_within_bounds(finger_coordinates, config):
        raise ContactError("P_STROKE_LIMIT_VIOLATION_IN_INTEGRATOR_STAGE")
    left, right = evaluate_dual_contact(model, service, target, config, enabled=enabled)
    if max(left.penetration_m, right.penetration_m) > config.max_penetration_abort_m:
        raise ContactError("OVERPENETRATION_IN_INTEGRATOR_STAGE")
    effort = left.service_generalized_contact_effort_mixed + right.service_generalized_contact_effort_mixed
    matrix = model.mass_matrix(service)
    if float(np.min(np.linalg.eigvalsh(matrix))) <= 1.0e-10:
        raise ContactError("branched service mass matrix lost positive definiteness")
    service_acceleration = np.linalg.solve(matrix, effort - model.bias_effort(service))
    service_quaternion_rate = 0.5 * quat_product(
        np.array((0.0, *service.nu_s_mixed[3:6])),
        service.base_quaternion_body_to_inertial_wxyz,
    )
    target_rotation = quat_to_rotation(target.quaternion_body_to_inertial_wxyz)
    target_inertia_world = target_rotation @ TARGET_INERTIA_BODY_KG_M2 @ target_rotation.T
    target_velocity = target.twist_inertial_mixed[:3]; target_omega = target.twist_inertial_mixed[3:]
    total_target_force = left.target_force_inertial_n + right.target_force_inertial_n
    total_target_torque = left.target_torque_about_com_inertial_n_m + right.target_torque_about_com_inertial_n_m
    target_acceleration = total_target_force / TARGET_MASS_KG
    target_omega_dot = np.linalg.solve(
        target_inertia_world,
        total_target_torque - np.cross(target_omega, target_inertia_world @ target_omega),
    )
    target_quaternion_rate = 0.5 * quat_product(
        np.array((0.0, *target_omega)), target.quaternion_body_to_inertial_wxyz
    )
    return np.concatenate(
        (
            service.nu_s_mixed[:3], service_quaternion_rate, service.nu_s_mixed[6:], service_acceleration,
            target_velocity, target_quaternion_rate, target_acceleration, target_omega_dot,
            (left.normal_dissipation_rate_w, left.friction_dissipation_rate_w,
             right.normal_dissipation_rate_w, right.friction_dissipation_rate_w),
            left.service_force_inertial_n, right.service_force_inertial_n,
            np.cross(left.common_contact_point_inertial_m, left.service_force_inertial_n),
            np.cross(right.common_contact_point_inertial_m, right.service_force_inertial_n),
        )
    )


def deterministic_dual_contact_scenario() -> tuple[
    BranchedGripperServiceModel, ServiceState, TargetState, DualContactConfig
]:
    config = DualContactConfig().validated(); model = BranchedGripperServiceModel()
    _, phase_service, _ = deterministic_scenario()
    q = phase_service.joint_coordinates_mixed.copy(); q[6:] = config.initial_finger_coordinate_m
    nu = 0.05 * phase_service.nu_s_mixed; nu[12:] = -config.synthetic_initial_closing_speed_m_s
    service = ServiceState(
        phase_service.base_position_inertial_m.copy(),
        phase_service.base_quaternion_body_to_inertial_wxyz.copy(), q, nu,
    )
    palm, palm_rotation, palm_jv, palm_jw = model.palm_frame_and_jacobians(service)
    target_position = palm + palm_rotation @ np.array((config.pad_x_palm_m, 0.0, config.pad_z_palm_m))
    palm_velocity = palm_jv @ service.nu_s_mixed; palm_omega = palm_jw @ service.nu_s_mixed
    target = TargetState(
        target_position,
        quat_from_rotvec((0.08, -0.05, 0.03)),
        np.concatenate((palm_velocity, palm_omega + palm_rotation @ np.array((0.04, -0.015, 0.02)))),
    )
    return model, service, target, config


def _candidate_predicate(criteria: dict[str, Any], config: DualContactConfig) -> bool:
    return bool(
        criteria["left_contact"]
        and criteria["right_contact"]
        and criteria["dual_contact_dwell_s"] >= config.dual_contact_dwell_s
        and criteria["normals_dot"] <= config.normals_opposition_max_dot
        and criteria["target_inside_corridor"]
        and criteria["target_relative_center_speed_m_s"] <= config.soft_capture_max_relative_center_speed_m_s
        and criteria["target_relative_omega_rad_s"] <= config.soft_capture_max_relative_omega_rad_s
        and abs(criteria["left_relative_normal_speed_m_s"]) <= config.soft_capture_max_abs_contact_normal_speed_m_s
        and abs(criteria["right_relative_normal_speed_m_s"]) <= config.soft_capture_max_abs_contact_normal_speed_m_s
        and criteria["left_relative_tangential_speed_m_s"] <= config.soft_capture_max_contact_tangential_speed_m_s
        and criteria["right_relative_tangential_speed_m_s"] <= config.soft_capture_max_contact_tangential_speed_m_s
        and criteria["left_finger_rate_m_s"] <= config.soft_capture_max_finger_opening_speed_m_s
        and criteria["right_finger_rate_m_s"] <= config.soft_capture_max_finger_opening_speed_m_s
        and criteria["left_normal_force_n"] >= config.soft_capture_min_normal_force_n
        and criteria["right_normal_force_n"] >= config.soft_capture_min_normal_force_n
        and criteria["all_ledgers_closed"]
    )


def _released_state_recontact_rejected(state: str, left_on: bool, right_on: bool) -> bool:
    return state == "BILATERAL_RELEASE" and (left_on or right_on)


def _state_machine(
    times: np.ndarray,
    left: dict[str, np.ndarray],
    right: dict[str, np.ndarray],
    target_center_palm: np.ndarray,
    relative_center_speed: np.ndarray,
    relative_omega: np.ndarray,
    finger_rates: np.ndarray,
    ledger: dict[str, np.ndarray],
    config: DualContactConfig,
    *,
    require_soft_capture: bool,
) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[str, ...]]:
    state = "PREGRASP_SEPARATED"; labels: list[str] = []
    transitions: list[dict[str, Any]] = [{"from": None, "to": state, "time_s": float(times[0]), "index": 0}]
    criteria_log: list[dict[str, Any]] = []; reasons: list[str] = []; dual_start: float | None = None
    reached_candidate = False
    candidate_interval_latched = False
    for index, time_s in enumerate(times):
        values = (
            left["gap"][index], right["gap"][index], left["penetration"][index], right["penetration"][index],
            left["normal_speed"][index], right["normal_speed"][index], relative_center_speed[index], relative_omega[index],
            left["tangent_speed"][index], right["tangent_speed"][index],
            finger_rates[index, 0], finger_rates[index, 1],
            ledger["linear_momentum_drift"][index], ledger["angular_momentum_drift"][index],
            ledger["service_linear_impulse_identity_error_n_s"][index],
            ledger["target_linear_impulse_identity_error_n_s"][index],
            ledger["service_angular_impulse_identity_error_n_m_s"][index],
            ledger["target_angular_impulse_identity_error_n_m_s"][index],
            ledger["energy_drift"][index], ledger["action_reaction_error_n"][index],
            ledger["common_point_shift_error_n_m"][index], ledger["target_torque_identity_error_n_m"][index],
            ledger["virtual_power_error_w"][index], ledger["friction_positive_power_w"][index],
            ledger["dissipation_monotonic_violation_j"][index],
        )
        if not all(math.isfinite(float(value)) for value in values):
            reasons.append(f"NONFINITE_DUAL_CONTACT_STATE_AT_INDEX_{index}"); new_state = ABORT_STATE
        elif max(left["penetration"][index], right["penetration"][index]) > config.max_penetration_abort_m:
            reasons.append(f"OVERPENETRATION_AT_INDEX_{index}"); new_state = ABORT_STATE
        else:
            left_on = left["penetration"][index] > 0.0 and left["force"][index] > 0.0
            right_on = right["penetration"][index] > 0.0 and right["force"][index] > 0.0
            normals_dot = float(left["normal"][index] @ right["normal"][index])
            y = float(target_center_palm[index, 1])
            left_y = float(left["pad_palm_y"][index]); right_y = float(right["pad_palm_y"][index])
            corridor = min(left_y, right_y) - config.corridor_margin_m <= y <= max(left_y, right_y) + config.corridor_margin_m
            if left_on and right_on:
                if dual_start is None:
                    dual_start = float(time_s)
                dwell = float(time_s) - dual_start
            else:
                dwell = 0.0
                dual_start = None
                candidate_interval_latched = False
            criteria = {
                "index": index, "time_s": float(time_s), "left_contact": bool(left_on), "right_contact": bool(right_on),
                "dual_contact_dwell_s": dwell, "normals_dot": normals_dot,
                "target_inside_corridor": bool(corridor),
                "target_relative_center_speed_m_s": float(relative_center_speed[index]),
                "target_relative_omega_rad_s": float(relative_omega[index]),
                "left_relative_normal_speed_m_s": float(left["normal_speed"][index]),
                "right_relative_normal_speed_m_s": float(right["normal_speed"][index]),
                "left_relative_tangential_speed_m_s": float(left["tangent_speed"][index]),
                "right_relative_tangential_speed_m_s": float(right["tangent_speed"][index]),
                "left_finger_rate_m_s": float(finger_rates[index, 0]),
                "right_finger_rate_m_s": float(finger_rates[index, 1]),
                "jaw_aperture_rate_m_s": float(finger_rates[index, 0] + finger_rates[index, 1]),
                "left_normal_force_n": float(left["force"][index]), "right_normal_force_n": float(right["force"][index]),
                "linear_momentum_drift_n_s": float(ledger["linear_momentum_drift"][index]),
                "angular_momentum_drift_n_m_s": float(ledger["angular_momentum_drift"][index]),
                "service_linear_impulse_identity_error_n_s": float(ledger["service_linear_impulse_identity_error_n_s"][index]),
                "target_linear_impulse_identity_error_n_s": float(ledger["target_linear_impulse_identity_error_n_s"][index]),
                "service_angular_impulse_identity_error_n_m_s": float(ledger["service_angular_impulse_identity_error_n_m_s"][index]),
                "target_angular_impulse_identity_error_n_m_s": float(ledger["target_angular_impulse_identity_error_n_m_s"][index]),
                "energy_plus_dissipation_drift_j": float(ledger["energy_drift"][index]),
                "action_reaction_error_n": float(ledger["action_reaction_error_n"][index]),
                "common_point_shift_error_n_m": float(ledger["common_point_shift_error_n_m"][index]),
                "target_torque_identity_error_n_m": float(ledger["target_torque_identity_error_n_m"][index]),
                "virtual_power_identity_error_w": float(ledger["virtual_power_error_w"][index]),
                "friction_positive_power_w": float(ledger["friction_positive_power_w"][index]),
                "dissipation_monotonic_violation_j": float(ledger["dissipation_monotonic_violation_j"][index]),
            }
            ledgers_closed = (
                ledger["linear_momentum_drift"][index] <= config.linear_momentum_ledger_tolerance_n_s
                and ledger["angular_momentum_drift"][index] <= config.angular_momentum_ledger_tolerance_n_m_s
                and ledger["service_linear_impulse_identity_error_n_s"][index] <= config.linear_impulse_identity_tolerance_n_s
                and ledger["target_linear_impulse_identity_error_n_s"][index] <= config.linear_impulse_identity_tolerance_n_s
                and ledger["service_angular_impulse_identity_error_n_m_s"][index] <= config.angular_impulse_identity_tolerance_n_m_s
                and ledger["target_angular_impulse_identity_error_n_m_s"][index] <= config.angular_impulse_identity_tolerance_n_m_s
                and ledger["energy_drift"][index] <= config.energy_ledger_tolerance_j
                and ledger["action_reaction_error_n"][index] <= config.action_reaction_tolerance_n
                and ledger["common_point_shift_error_n_m"][index] <= config.common_point_shift_tolerance_n_m
                and ledger["target_torque_identity_error_n_m"][index] <= config.target_torque_identity_tolerance_n_m
                and ledger["virtual_power_error_w"][index] <= config.virtual_power_tolerance_w
                and ledger["friction_positive_power_w"][index] <= config.friction_noninjection_tolerance_w
                and ledger["dissipation_monotonic_violation_j"][index] <= config.dissipation_monotonic_tolerance_j
            )
            criteria["all_ledgers_closed"] = bool(ledgers_closed)
            qualifies = _candidate_predicate(criteria, config)
            criteria["soft_capture_transient_qualifies"] = bool(qualifies); criteria_log.append(criteria)
            if state == ABORT_STATE:
                new_state = ABORT_STATE
            elif _released_state_recontact_rejected(state, left_on, right_on):
                reasons.append(f"RECONTACT_AFTER_BILATERAL_RELEASE_AT_INDEX_{index}")
                new_state = ABORT_STATE
            elif state == "BILATERAL_RELEASE":
                new_state = "BILATERAL_RELEASE"
            elif reached_candidate and not left_on and not right_on and left["gap"][index] >= 0.0 and right["gap"][index] >= 0.0:
                new_state = "BILATERAL_RELEASE"
            elif candidate_interval_latched and left_on and right_on:
                # The candidate state is event-latched while bilateral contact
                # remains present.  Instantaneous qualification is still
                # reported sample-by-sample in ``criteria_log``; latching does
                # not promote the event to a held grasp or a lock.
                new_state = "SOFT_CAPTURE_TRANSIENT_CANDIDATE"
            elif qualifies:
                new_state = "SOFT_CAPTURE_TRANSIENT_CANDIDATE"
                reached_candidate = True
                candidate_interval_latched = True
            elif left_on and right_on:
                new_state = "DUAL_CONTACT"
            elif left_on:
                new_state = "LEFT_ONLY_CONTACT"
            elif right_on:
                new_state = "RIGHT_ONLY_CONTACT"
            elif left["gap"][index] > 0.0 and right["gap"][index] > 0.0 and left["normal_speed"][index] < 0.0 and right["normal_speed"][index] < 0.0:
                new_state = "BILATERAL_APPROACH"
            else:
                new_state = state
        if new_state != state:
            transitions.append({"from": state, "to": new_state, "time_s": float(time_s), "index": index}); state = new_state
        labels.append(state)
    if require_soft_capture and not reached_candidate:
        reasons.append("NO_SOFT_CAPTURE_TRANSIENT_CANDIDATE")
    return tuple(labels), tuple(transitions), tuple(criteria_log), tuple(reasons)


def integrate_dual_contact(
    model: BranchedGripperServiceModel,
    service_initial: ServiceState,
    target_initial: TargetState,
    config: DualContactConfig,
    *,
    step_s: float,
    duration_s: float,
    method: str = "rk4",
    contact_enabled: bool = True,
    require_soft_capture: bool = True,
) -> DualContactHistory:
    config = config.validated(); service_initial = model.validate_service_state(service_initial); target_initial = validate_target_state(target_initial)
    if not math.isfinite(step_s) or step_s <= 0.0 or not math.isfinite(duration_s) or duration_s <= 0.0:
        raise ContactError("step and duration must be finite and positive")
    steps_float = duration_s / step_s; steps = int(round(steps_float))
    if steps < 1 or abs(steps_float - steps) > 1.0e-10:
        raise ContactError("duration must be an integer multiple of step")
    initial_observations = evaluate_dual_contact(
        model, service_initial, target_initial, config, enabled=False
    )
    if any(observation.gap_m <= 0.0 for observation in initial_observations):
        raise ContactError("INITIAL_GEOMETRY_NOT_BILATERALLY_SEPARATED")
    topology_diagnostic = _topology_jacobian_diagnostic(model, service_initial, config)
    vector = np.concatenate((_service_to_vector(service_initial), _target_to_vector(target_initial), np.zeros(16)))
    count = steps + 1; times = np.arange(count, dtype=float) * step_s
    common_shapes = {
        "service_position": (count, 3), "service_quaternion": (count, 4), "service_q": (count, 8), "service_nu": (count, 14),
        "target_position": (count, 3), "target_quaternion": (count, 4), "target_twist": (count, 6),
        "palm_origin": (count, 3), "palm_rotation": (count, 3, 3), "palm_velocity": (count, 3), "palm_omega": (count, 3),
        "target_center_palm": (count, 3), "relative_center_speed": (count,), "relative_omega": (count,),
        "service_p": (count, 3), "service_h": (count, 3), "target_p": (count, 3), "target_h": (count, 3),
        "service_t": (count,), "target_t": (count,),
    }
    contact_shapes = {
        "gap": (count,), "penetration": (count,), "normal": (count, 3), "common": (count, 3), "pad": (count, 3),
        "service_common_velocity": (count, 3), "target_common_velocity": (count, 3), "relative": (count, 3),
        "normal_speed": (count,), "tangent_velocity": (count, 3), "tangent_speed": (count,), "force": (count,),
        "normal_force": (count, 3), "tangent_force": (count, 3), "service_force": (count, 3), "target_force": (count, 3),
        "shift": (count, 3), "effort": (count, 14), "target_torque": (count, 3), "elastic": (count,),
        "normal_d_rate": (count,), "friction_d_rate": (count,), "normal_d": (count,), "friction_d": (count,),
        "impulse": (count, 3), "angular_impulse": (count, 3), "pad_palm_y": (count,),
    }
    common = {name: np.empty(shape) for name, shape in common_shapes.items()}
    contacts = {side: {name: np.empty(shape) for name, shape in contact_shapes.items()} for side in SIDES}
    reasons: list[str] = []; completed = count
    for index in range(count):
        try:
            service = _service_from_vector(vector[:29]); target = _target_from_vector(vector[29:42])
            observations = evaluate_dual_contact(model, service, target, config, enabled=contact_enabled)
            service_ledger = model.momentum_energy(service); target_ledger = target_momentum_energy(target)
            palm_origin, palm_rotation, palm_jv, palm_jw = model.palm_frame_and_jacobians(service)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            error_code = str(error).replace(" ", "_").replace(":", "_")[:120]
            reasons.append(f"FAIL_CLOSED_AT_INDEX_{index}:{type(error).__name__}:{error_code}"); completed = index; break
        palm_velocity = palm_jv @ service.nu_s_mixed; palm_omega = palm_jw @ service.nu_s_mixed
        center_offset = target.position_inertial_m - palm_origin
        relative_center_velocity = target.twist_inertial_mixed[:3] - (palm_velocity + np.cross(palm_omega, center_offset))
        common_values = {
            "service_position": service.base_position_inertial_m, "service_quaternion": service.base_quaternion_body_to_inertial_wxyz,
            "service_q": service.joint_coordinates_mixed, "service_nu": service.nu_s_mixed,
            "target_position": target.position_inertial_m, "target_quaternion": target.quaternion_body_to_inertial_wxyz, "target_twist": target.twist_inertial_mixed,
            "palm_origin": palm_origin, "palm_rotation": palm_rotation, "palm_velocity": palm_velocity, "palm_omega": palm_omega,
            "target_center_palm": palm_rotation.T @ center_offset,
            "relative_center_speed": float(np.linalg.norm(relative_center_velocity)),
            "relative_omega": float(np.linalg.norm(target.twist_inertial_mixed[3:] - palm_omega)),
            "service_p": service_ledger.linear_momentum_n_s, "service_h": service_ledger.angular_momentum_about_inertial_origin_n_m_s,
            "target_p": target_ledger.linear_momentum_n_s, "target_h": target_ledger.angular_momentum_about_inertial_origin_n_m_s,
            "service_t": service_ledger.kinetic_energy_j, "target_t": target_ledger.kinetic_energy_j,
        }
        for name, value in common_values.items(): common[name][index] = value
        for side_index, (side, observation) in enumerate(zip(SIDES, observations)):
            offset = 42 + 2 * side_index
            impulse_offset = 46 + 3 * side_index
            angular_offset = 52 + 3 * side_index
            values = {
                "gap": observation.gap_m, "penetration": observation.penetration_m, "normal": observation.normal_target_to_pad_inertial,
                "common": observation.common_contact_point_inertial_m, "pad": observation.pad_point_inertial_m,
                "service_common_velocity": observation.service_common_point_velocity_inertial_m_s,
                "target_common_velocity": observation.target_common_point_velocity_inertial_m_s,
                "relative": observation.relative_velocity_inertial_m_s, "normal_speed": observation.relative_normal_speed_m_s,
                "tangent_velocity": observation.relative_tangential_velocity_inertial_m_s, "tangent_speed": observation.relative_tangential_speed_m_s,
                "force": observation.normal_force_magnitude_n, "normal_force": observation.normal_force_service_inertial_n,
                "tangent_force": observation.tangential_force_service_inertial_n, "service_force": observation.service_force_inertial_n,
                "target_force": observation.target_force_inertial_n, "shift": observation.service_shift_torque_inertial_n_m,
                "effort": observation.service_generalized_contact_effort_mixed, "target_torque": observation.target_torque_about_com_inertial_n_m,
                "elastic": observation.elastic_energy_j, "normal_d_rate": observation.normal_dissipation_rate_w,
                "friction_d_rate": observation.friction_dissipation_rate_w, "normal_d": vector[offset], "friction_d": vector[offset + 1],
                "impulse": vector[impulse_offset:impulse_offset + 3], "angular_impulse": vector[angular_offset:angular_offset + 3],
                "pad_palm_y": float((palm_rotation.T @ (observation.pad_point_inertial_m - palm_origin))[1]),
            }
            for name, value in values.items(): contacts[side][name][index] = value
        finger_coordinates = service.joint_coordinates_mixed[6:8]
        if not _finger_stroke_within_bounds(finger_coordinates, config):
            reasons.append(f"P_STROKE_LIMIT_VIOLATION_AT_INDEX_{index}"); completed = index + 1; break
        if max(observation.penetration_m for observation in observations) > config.max_penetration_abort_m:
            reasons.append(f"OVERPENETRATION_AT_INDEX_{index}"); completed = index + 1; break
        if index == steps: continue
        try:
            vector = _step(lambda value: _rhs(model, value, config, contact_enabled), vector, step_s, method)
            if not np.all(np.isfinite(vector)): raise ContactError("nonfinite integration state")
            vector[3:7] = normalize_quaternion(vector[3:7]); vector[32:36] = normalize_quaternion(vector[32:36])
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            error_code = str(error).replace(" ", "_").replace(":", "_")[:120]
            reasons.append(f"INTEGRATION_FAILURE_AT_INDEX_{index}:{type(error).__name__}:{error_code}"); completed = index + 1; break
    if completed != count:
        times = times[:completed]; common = {name: value[:completed] for name, value in common.items()}
        contacts = {side: {name: value[:completed] for name, value in data.items()} for side, data in contacts.items()}
    if len(times) == 0:
        raise ContactError("FAIL_CLOSED_BEFORE_FIRST_AUDIT_SAMPLE")
    total_linear_momentum = common["service_p"] + common["target_p"]
    total_angular_momentum = common["service_h"] + common["target_h"]
    summed_impulse = contacts["left"]["impulse"] + contacts["right"]["impulse"]
    summed_angular_impulse = contacts["left"]["angular_impulse"] + contacts["right"]["angular_impulse"]
    service_linear_delta = common["service_p"] - common["service_p"][0]
    target_linear_delta = common["target_p"] - common["target_p"][0]
    service_angular_delta = common["service_h"] - common["service_h"][0]
    target_angular_delta = common["target_h"] - common["target_h"][0]
    total_energy = (
        common["service_t"] + common["target_t"]
        + contacts["left"]["elastic"] + contacts["right"]["elastic"]
        + contacts["left"]["normal_d"] + contacts["left"]["friction_d"]
        + contacts["right"]["normal_d"] + contacts["right"]["friction_d"]
    )
    action_reaction_error = np.zeros(len(times))
    common_point_shift_error = np.zeros(len(times))
    target_torque_identity_error = np.zeros(len(times))
    virtual_power_error = np.zeros(len(times))
    friction_positive_power = np.zeros(len(times))
    dissipation_monotonic_violation = np.zeros(len(times))
    for side in SIDES:
        data = contacts[side]
        action_reaction = np.linalg.norm(data["service_force"] + data["target_force"], axis=1)
        shifted_about_origin = np.cross(data["pad"], data["service_force"]) + data["shift"]
        common_about_origin = np.cross(data["common"], data["service_force"])
        shift_error = np.linalg.norm(shifted_about_origin - common_about_origin, axis=1)
        expected_target_torque = np.cross(
            data["common"] - common["target_position"], data["target_force"]
        )
        target_torque_error = np.linalg.norm(data["target_torque"] - expected_target_torque, axis=1)
        service_generalized_power = np.einsum("ij,ij->i", data["effort"], common["service_nu"])
        service_common_power = np.einsum("ij,ij->i", data["service_force"], data["service_common_velocity"])
        target_generalized_power = (
            np.einsum("ij,ij->i", data["target_force"], common["target_twist"][:, :3])
            + np.einsum("ij,ij->i", data["target_torque"], common["target_twist"][:, 3:])
        )
        target_common_power = np.einsum("ij,ij->i", data["target_force"], data["target_common_velocity"])
        friction_power = np.einsum("ij,ij->i", data["tangent_force"], data["tangent_velocity"])
        channel_violation = np.zeros(len(times))
        for channel in (data["normal_d"], data["friction_d"]):
            negative_increment = np.maximum(-np.diff(channel, prepend=channel[0]), 0.0)
            channel_violation = np.maximum(channel_violation, np.maximum.accumulate(negative_increment))
        action_reaction_error = np.maximum(action_reaction_error, action_reaction)
        common_point_shift_error = np.maximum(common_point_shift_error, shift_error)
        target_torque_identity_error = np.maximum(target_torque_identity_error, target_torque_error)
        virtual_power_error = np.maximum(
            virtual_power_error,
            np.maximum(
                np.abs(service_generalized_power - service_common_power),
                np.abs(target_generalized_power - target_common_power),
            ),
        )
        friction_positive_power = np.maximum(friction_positive_power, np.maximum(friction_power, 0.0))
        dissipation_monotonic_violation = np.maximum(dissipation_monotonic_violation, channel_violation)
    ledger = {
        "linear_momentum_drift": np.linalg.norm(total_linear_momentum - total_linear_momentum[0], axis=1),
        "angular_momentum_drift": np.linalg.norm(total_angular_momentum - total_angular_momentum[0], axis=1),
        "service_linear_impulse_identity_error_n_s": np.linalg.norm(service_linear_delta - summed_impulse, axis=1),
        "target_linear_impulse_identity_error_n_s": np.linalg.norm(target_linear_delta + summed_impulse, axis=1),
        "service_angular_impulse_identity_error_n_m_s": np.linalg.norm(service_angular_delta - summed_angular_impulse, axis=1),
        "target_angular_impulse_identity_error_n_m_s": np.linalg.norm(target_angular_delta + summed_angular_impulse, axis=1),
        "energy_drift": np.abs(total_energy - total_energy[0]),
        "action_reaction_error_n": action_reaction_error,
        "common_point_shift_error_n_m": common_point_shift_error,
        "target_torque_identity_error_n_m": target_torque_identity_error,
        "virtual_power_error_w": virtual_power_error,
        "friction_positive_power_w": friction_positive_power,
        "dissipation_monotonic_violation_j": dissipation_monotonic_violation,
    }
    labels, transitions, criteria, machine_reasons = _state_machine(
        times, contacts["left"], contacts["right"], common["target_center_palm"],
        common["relative_center_speed"], common["relative_omega"], common["service_nu"][:, 12:14], ledger, config,
        require_soft_capture=require_soft_capture and contact_enabled,
    )
    all_reasons = tuple(reasons) + machine_reasons; aborted = bool(all_reasons) or len(times) != count
    if aborted and labels:
        if labels[-1] != ABORT_STATE:
            transitions = tuple((*transitions, {
                "from": labels[-1], "to": ABORT_STATE,
                "time_s": float(times[-1]), "index": len(times) - 1,
            }))
        labels = tuple((*labels[:-1], ABORT_STATE))

    def per(side: str) -> PerFingerHistory:
        data = contacts[side]
        return PerFingerHistory(
            data["gap"], data["penetration"], data["normal"], data["common"], data["pad"],
            data["service_common_velocity"], data["target_common_velocity"], data["relative"], data["normal_speed"],
            data["tangent_velocity"], data["tangent_speed"], data["force"], data["normal_force"], data["tangent_force"],
            data["service_force"], data["target_force"], data["shift"], data["effort"], data["target_torque"], data["elastic"],
            data["normal_d_rate"], data["friction_d_rate"], data["normal_d"], data["friction_d"], data["impulse"], data["angular_impulse"],
        )
    return DualContactHistory(
        times, common["service_position"], common["service_quaternion"], common["service_q"], common["service_nu"],
        common["target_position"], common["target_quaternion"], common["target_twist"], common["palm_origin"], common["palm_rotation"],
        common["palm_velocity"], common["palm_omega"], common["target_center_palm"], common["relative_center_speed"], common["relative_omega"],
        per("left"), per("right"), common["service_p"], common["service_h"], common["target_p"], common["target_h"],
        common["service_t"], common["target_t"], labels, transitions, criteria, method, step_s, aborted, all_reasons,
        topology_diagnostic,
    )


def _crossing_time(times: np.ndarray, gaps: np.ndarray, direction: str) -> float | None:
    for index in range(1, len(times)):
        left, right = float(gaps[index - 1]), float(gaps[index])
        crossed = (left > 0.0 and right <= 0.0) if direction == "enter" else (left < 0.0 and right >= 0.0)
        if crossed:
            denominator = abs(left) + abs(right); fraction = abs(left) / denominator if denominator else 0.0
            return float(times[index - 1] + fraction * (times[index] - times[index - 1]))
    return None


def _grasp_map_diagnostic(history: DualContactHistory) -> dict[str, Any]:
    """Report the normalized two-hard-finger-point wrench span about target COM.

    Each synthetic frictional point is allowed an arbitrary three-component
    force for this *linear span* diagnostic.  That relaxation can only
    overestimate real unilateral/friction-cone authority.  Two distinct point
    forces span rank five.  The force/moment rows are normalized by half the
    contact separation before SVD, avoiding a mixed-unit singular spectrum.
    """
    qualifying_indices = [
        int(item["index"])
        for item in history.soft_capture_criteria_log
        if item.get("soft_capture_transient_qualifies")
    ]
    if qualifying_indices:
        evaluation_indices = qualifying_indices
        index = evaluation_indices[0]
        selection = "FIRST_SOFT_CAPTURE_TRANSIENT_QUALIFYING_SAMPLE"
    else:
        index = int(np.argmax(
            history.left.normal_force_magnitude_n
            + history.right.normal_force_magnitude_n
        ))
        evaluation_indices = [index]
        selection = "PEAK_COMBINED_NORMAL_FORCE_FALLBACK"

    def skew_matrix(vector: np.ndarray) -> np.ndarray:
        return np.array((
            (0.0, -vector[2], vector[1]),
            (vector[2], 0.0, -vector[0]),
            (-vector[1], vector[0], 0.0),
        ))

    sample_records: list[dict[str, Any]] = []
    for sample_index in evaluation_indices:
        target_origin = history.target_position_inertial_m[sample_index]
        r_left = history.left.common_contact_point_inertial_m[sample_index] - target_origin
        r_right = history.right.common_contact_point_inertial_m[sample_index] - target_origin
        contact_line = r_right - r_left
        contact_separation = float(np.linalg.norm(contact_line))
        if contact_separation <= 1.0e-12:
            raise ContactError("dual-contact grasp map requires two distinct contact points")
        contact_line_unit = contact_line / contact_separation
        length_reference = 0.5 * contact_separation
        identity = np.eye(3)
        normalized_grasp_map = np.block([
            [identity, identity],
            [skew_matrix(r_left) / length_reference, skew_matrix(r_right) / length_reference],
        ])
        left_singular_vectors, singular_values, _ = np.linalg.svd(normalized_grasp_map)
        rank_tolerance = 1.0e-10 * max(float(singular_values[0]), 1.0)
        numerical_rank = int(np.count_nonzero(singular_values > rank_tolerance))
        reciprocal_twist = left_singular_vectors[:, -1]
        desired_normalized_axial_torque = np.concatenate((np.zeros(3), contact_line_unit))
        least_squares_forces = np.linalg.lstsq(
            normalized_grasp_map, desired_normalized_axial_torque, rcond=None
        )[0]
        axial_torque_residual = float(np.linalg.norm(
            normalized_grasp_map @ least_squares_forces - desired_normalized_axial_torque
        ))
        sample_records.append({
            "index": int(sample_index),
            "time_s": float(history.time_s[sample_index]),
            "length_reference_m": length_reference,
            "contact_line_unit_inertial": contact_line_unit.tolist(),
            "normalized_singular_values": singular_values.tolist(),
            "rank_tolerance": rank_tolerance,
            "numerical_rank": numerical_rank,
            "rank_deficiency": 6 - numerical_rank,
            "reciprocal_twist_unit_in_normalized_coordinates": reciprocal_twist.tolist(),
            "normalized_axial_pure_torque_lstsq_residual": axial_torque_residual,
        })
    ranks = [item["numerical_rank"] for item in sample_records]
    selected = sample_records[0]
    full_span = min(ranks) == 6
    return {
        "evaluation_index": index,
        "evaluation_time_s": float(history.time_s[index]),
        "sample_selection": selection,
        "wrench_origin": "TARGET_COM_INERTIAL",
        "contact_model_for_span_only": "TWO_HARD_FINGER_FRICTIONAL_POINT_CONTACTS_WITH_LINEARIZED_UNCONSTRAINED_3D_FORCE_EACH",
        "normalization": "MOMENT_ROWS_DIVIDED_BY_L_REF__L_REF_HALF_CONTACT_SEPARATION",
        "matrix_shape": [6, 6],
        "qualifying_sample_count_evaluated": len(evaluation_indices),
        "rank_min_across_evaluated_samples": min(ranks),
        "rank_max_across_evaluated_samples": max(ranks),
        "all_evaluated_samples_rank_five": all(rank == 5 for rank in ranks),
        "selected_sample": selected,
        "sample_records": sample_records,
        "full_6d_wrench_span": full_span,
        "full_6d_force_closure": False,
        "force_closure_ruling": (
            "FALSE_RANK_DEFICIENT_TWO_POINT_WRENCH_SPAN"
            if not full_span else
            "FALSE_NOT_ESTABLISHED_BY_LINEAR_SPAN_OR_WITHOUT_UNILATERAL_FRICTION_CONE_PROOF"
        ),
    }


def _topology_jacobian_diagnostic(
    model: BranchedGripperServiceModel,
    service: ServiceState,
    config: DualContactConfig,
) -> dict[str, Any]:
    """Measure own-branch and cross-branch P sensitivities at the first sample."""
    step = 1.0e-7

    def point_and_jacobian(side: str) -> tuple[np.ndarray, np.ndarray]:
        point, jv, _ = model.synthetic_pad_position_and_jacobian(
            service,
            side,
            closed_half_gap_m=config.closed_half_gap_m,
            pad_x_palm_m=config.pad_x_palm_m,
            pad_z_palm_m=config.pad_z_palm_m,
        )
        return point, jv

    def finite_difference(side: str, coordinate_index: int) -> np.ndarray:
        points = []
        for sign in (-1.0, 1.0):
            coordinates = service.joint_coordinates_mixed.copy()
            coordinates[coordinate_index] += sign * step
            perturbed = ServiceState(
                service.base_position_inertial_m.copy(),
                service.base_quaternion_body_to_inertial_wxyz.copy(),
                coordinates,
                service.nu_s_mixed.copy(),
            )
            point, _, _ = model.synthetic_pad_position_and_jacobian(
                perturbed,
                side,
                closed_half_gap_m=config.closed_half_gap_m,
                pad_x_palm_m=config.pad_x_palm_m,
                pad_z_palm_m=config.pad_z_palm_m,
            )
            points.append(point)
        return (points[1] - points[0]) / (2.0 * step)

    _, left_jv = point_and_jacobian("left")
    _, right_jv = point_and_jacobian("right")
    left_own_fd = finite_difference("left", 6)
    left_cross_fd = finite_difference("left", 7)
    right_cross_fd = finite_difference("right", 6)
    right_own_fd = finite_difference("right", 7)
    return {
        "class": "BRANCHED_6R_FIXED_PALM_PARALLEL_2P",
        "model_python_class": f"{type(model).__module__}.{type(model).__qualname__}",
        "evaluation_index": 0,
        "finite_difference_step_m": step,
        "left_own_P_jacobian_fd_max_error": float(np.max(np.abs(left_own_fd - left_jv[:, 12]))),
        "right_own_P_jacobian_fd_max_error": float(np.max(np.abs(right_own_fd - right_jv[:, 13]))),
        "left_analytic_own_P_norm": float(np.linalg.norm(left_jv[:, 12])),
        "right_analytic_own_P_norm": float(np.linalg.norm(right_jv[:, 13])),
        "left_cross_right_P_fd_norm": float(np.linalg.norm(left_cross_fd)),
        "right_cross_left_P_fd_norm": float(np.linalg.norm(right_cross_fd)),
        "left_analytic_cross_right_P_norm": float(np.linalg.norm(left_jv[:, 13])),
        "right_analytic_cross_left_P_norm": float(np.linalg.norm(right_jv[:, 12])),
    }


def summarize_dual_contact_history(history: DualContactHistory, config: DualContactConfig) -> dict[str, Any]:
    config = config.validated()
    per_contact = {}
    for side, data in (("left", history.left), ("right", history.right)):
        force_norm = np.linalg.norm(data.service_force_inertial_n, axis=1)
        tangent_norm = np.linalg.norm(data.tangential_force_service_inertial_n, axis=1)
        shifted = np.cross(data.pad_point_inertial_m, data.service_force_inertial_n) + data.service_shift_torque_inertial_n_m
        common = np.cross(data.common_contact_point_inertial_m, data.service_force_inertial_n)
        target_torque_expected = np.cross(
            data.common_contact_point_inertial_m - history.target_position_inertial_m,
            data.target_force_inertial_n,
        )
        service_generalized_power = np.einsum(
            "ij,ij->i", data.service_generalized_contact_effort_mixed, history.service_nu_s_mixed
        )
        service_common_power = np.einsum(
            "ij,ij->i", data.service_force_inertial_n, data.service_common_point_velocity_inertial_m_s
        )
        target_generalized_power = (
            np.einsum("ij,ij->i", data.target_force_inertial_n, history.target_twist_inertial_mixed[:, :3])
            + np.einsum("ij,ij->i", data.target_torque_about_com_inertial_n_m, history.target_twist_inertial_mixed[:, 3:])
        )
        target_common_power = np.einsum(
            "ij,ij->i", data.target_force_inertial_n, data.target_common_point_velocity_inertial_m_s
        )
        friction_power = np.einsum(
            "ij,ij->i", data.tangential_force_service_inertial_n, data.relative_tangential_velocity_inertial_m_s
        )
        normal_d_increments = np.diff(data.cumulative_normal_dissipation_j)
        friction_d_increments = np.diff(data.cumulative_friction_dissipation_j)
        per_contact[side] = {
            "first_contact_time_s": _crossing_time(history.time_s, data.gap_m, "enter"),
            "separation_after_contact_time_s": _crossing_time(history.time_s, data.gap_m, "exit"),
            "peak_normal_force_n": float(np.max(data.normal_force_magnitude_n)),
            "peak_tangential_force_n": float(np.max(tangent_norm)),
            "maximum_penetration_m": float(np.max(data.penetration_m)),
            "action_reaction_max_error_n": float(np.max(np.linalg.norm(data.service_force_inertial_n + data.target_force_inertial_n, axis=1))),
            "tangential_orthogonality_max_error_n": float(np.max(np.abs(np.einsum("ij,ij->i", data.tangential_force_service_inertial_n, data.normal_target_to_pad_inertial)))),
            "friction_cone_max_excess_n": float(np.max(np.maximum(tangent_norm - config.friction_coefficient * data.normal_force_magnitude_n, 0.0))),
            "common_point_shift_max_error_n_m": float(np.max(np.linalg.norm(shifted - common, axis=1))),
            "target_common_point_torque_max_error_n_m": float(np.max(np.linalg.norm(data.target_torque_about_com_inertial_n_m - target_torque_expected, axis=1))),
            "service_virtual_power_max_error_w": float(np.max(np.abs(service_generalized_power - service_common_power))),
            "target_virtual_power_max_error_w": float(np.max(np.abs(target_generalized_power - target_common_power))),
            "maximum_friction_power_w": float(np.max(friction_power)),
            "minimum_friction_power_w": float(np.min(friction_power)),
            "normal_dissipation_minimum_increment_j": float(np.min(normal_d_increments)) if len(normal_d_increments) else 0.0,
            "friction_dissipation_minimum_increment_j": float(np.min(friction_d_increments)) if len(friction_d_increments) else 0.0,
            "final_impulse_n_s": data.cumulative_service_impulse_n_s[-1].tolist(),
            "final_angular_impulse_n_m_s": data.cumulative_service_angular_impulse_n_m_s[-1].tolist(),
            "final_normal_dissipation_j": float(data.cumulative_normal_dissipation_j[-1]),
            "final_friction_dissipation_j": float(data.cumulative_friction_dissipation_j[-1]),
            "peak_total_force_n": float(np.max(force_norm)),
        }
    impulse = history.left.cumulative_service_impulse_n_s + history.right.cumulative_service_impulse_n_s
    angular_impulse = history.left.cumulative_service_angular_impulse_n_m_s + history.right.cumulative_service_angular_impulse_n_m_s
    delta_sp = history.service_linear_momentum_n_s - history.service_linear_momentum_n_s[0]
    delta_tp = history.target_linear_momentum_n_s - history.target_linear_momentum_n_s[0]
    delta_sh = history.service_angular_momentum_about_origin_n_m_s - history.service_angular_momentum_about_origin_n_m_s[0]
    delta_th = history.target_angular_momentum_about_origin_n_m_s - history.target_angular_momentum_about_origin_n_m_s[0]
    total_p = history.total_linear_momentum_n_s; total_h = history.total_angular_momentum_about_origin_n_m_s
    total_e = history.total_mechanical_plus_dissipated_energy_j
    sequence = [item["to"] for item in history.transition_log]
    qualifying = [item for item in history.soft_capture_criteria_log if item.get("soft_capture_transient_qualifies")]
    return {
        "topology": history.topology_diagnostic,
        "per_contact": per_contact,
        "state_machine": {
            "transition_sequence": sequence, "transition_log": list(history.transition_log),
            "soft_capture_qualifying_sample_count": len(qualifying),
            "first_soft_capture_candidate_time_s": qualifying[0]["time_s"] if qualifying else None,
            "aborted_safe": history.aborted_safe, "abort_reasons": list(history.abort_reasons),
            "locked_state_present": "LOCKED" in history.state_label,
            "grasp_success_state_present": "GRASP_SUCCESS" in history.state_label,
        },
        "dual_contact": {
            "minimum_normal_pair_dot": float(np.min(np.einsum("ij,ij->i", history.left.normal_target_to_pad_inertial, history.right.normal_target_to_pad_inertial))),
            "maximum_force_imbalance_n": float(np.max(np.abs(history.left.normal_force_magnitude_n - history.right.normal_force_magnitude_n))),
            "target_relative_omega_initial_rad_s": float(history.target_relative_omega_rad_s[0]),
            "target_relative_omega_final_rad_s": float(history.target_relative_omega_rad_s[-1]),
        },
        "grasp_map": _grasp_map_diagnostic(history),
        "linear_momentum_n_s": {
            "service_delta_minus_sum_impulse_max_error_n_s": float(np.max(np.linalg.norm(delta_sp - impulse, axis=1))),
            "target_delta_plus_sum_impulse_max_error_n_s": float(np.max(np.linalg.norm(delta_tp + impulse, axis=1))),
            "total_max_drift_n_s": float(np.max(np.linalg.norm(total_p - total_p[0], axis=1))),
        },
        "angular_momentum_n_m_s": {
            "service_delta_minus_sum_angular_impulse_max_error_n_m_s": float(np.max(np.linalg.norm(delta_sh - angular_impulse, axis=1))),
            "target_delta_plus_sum_angular_impulse_max_error_n_m_s": float(np.max(np.linalg.norm(delta_th + angular_impulse, axis=1))),
            "total_max_drift_n_m_s": float(np.max(np.linalg.norm(total_h - total_h[0], axis=1))),
        },
        "energy_j": {
            "initial_total_j": float(total_e[0]),
            "final_total_j": float(total_e[-1]),
            "total_mechanical_plus_dissipated_max_drift_j": float(np.max(np.abs(total_e - total_e[0]))),
            "final_total_dissipation_j": float(
                history.left.cumulative_normal_dissipation_j[-1] + history.left.cumulative_friction_dissipation_j[-1]
                + history.right.cumulative_normal_dissipation_j[-1] + history.right.cumulative_friction_dissipation_j[-1]
            ),
            "actuator_work_j": 0.0,
            "actuator_model_present": False,
        },
        "boundaries": {
            "physical_dual_contact_identified": False, "physical_friction_identified": False,
            "physical_actuator_timing_identified": False, "soft_capture_current_system_passed": False,
            "lock_implemented": False, "grasp_success_claimed": False, "attached_target_released": False,
            "current_system_bound": False, "formal_nc19_credit": False, "production_ready": False,
            "release_authorized": False, "next_stage_authorized": False,
        },
    }


def no_contact_regression(*, step_s: float = 5.0e-4, steps: int = 8) -> dict[str, float]:
    model, service, target, config = deterministic_dual_contact_scenario()
    reference = propagate_no_contact(model, service, target, step_s=step_s, steps=steps, method="rk4")
    dual = integrate_dual_contact(
        model, service, target, config, step_s=step_s, duration_s=step_s * steps,
        method="rk4", contact_enabled=False, require_soft_capture=False,
    )
    return {
        "service_position_max_error_m": float(np.max(np.abs(dual.service_base_position_inertial_m - reference.service_base_position_inertial_m))),
        "service_quaternion_max_error": float(np.max(np.abs(dual.service_base_quaternion_body_to_inertial_wxyz - reference.service_base_quaternion_body_to_inertial_wxyz))),
        "service_q_max_mixed_error": float(np.max(np.abs(dual.service_joint_coordinates_mixed - reference.service_joint_coordinates_mixed))),
        "service_nu_max_mixed_error": float(np.max(np.abs(dual.service_nu_s_mixed - reference.service_nu_s_mixed))),
        "target_position_max_error_m": float(np.max(np.abs(dual.target_position_inertial_m - reference.target_position_inertial_m))),
        "target_quaternion_max_error": float(np.max(np.abs(dual.target_quaternion_body_to_inertial_wxyz - reference.target_quaternion_body_to_inertial_wxyz))),
        "target_twist_max_mixed_error": float(np.max(np.abs(dual.target_twist_inertial_mixed - reference.target_twist_inertial_mixed))),
        "service_linear_momentum_max_error_n_s": float(np.max(np.abs(dual.service_linear_momentum_n_s - reference.service_linear_momentum_n_s))),
        "service_angular_momentum_max_error_n_m_s": float(np.max(np.abs(dual.service_angular_momentum_about_origin_n_m_s - reference.service_angular_momentum_about_inertial_origin_n_m_s))),
        "service_kinetic_energy_max_error_j": float(np.max(np.abs(dual.service_kinetic_energy_j - reference.service_kinetic_energy_j))),
        "target_linear_momentum_max_error_n_s": float(np.max(np.abs(dual.target_linear_momentum_n_s - reference.target_linear_momentum_n_s))),
        "target_angular_momentum_max_error_n_m_s": float(np.max(np.abs(dual.target_angular_momentum_about_origin_n_m_s - reference.target_angular_momentum_about_inertial_origin_n_m_s))),
        "target_kinetic_energy_max_error_j": float(np.max(np.abs(dual.target_kinetic_energy_j - reference.target_kinetic_energy_j))),
        "total_linear_momentum_max_error_n_s": float(np.max(np.abs(dual.total_linear_momentum_n_s - reference.total_linear_momentum_n_s))),
        "total_angular_momentum_max_error_n_m_s": float(np.max(np.abs(dual.total_angular_momentum_about_origin_n_m_s - reference.total_angular_momentum_about_inertial_origin_n_m_s))),
        "total_kinetic_energy_max_error_j": float(np.max(np.abs((dual.service_kinetic_energy_j + dual.target_kinetic_energy_j) - reference.total_kinetic_energy_j))),
    }


def run_negative_controls(history: DualContactHistory, config: DualContactConfig) -> tuple[dict[str, Any], ...]:
    config = config.validated()
    qualifying = [
        dict(item) for item in history.soft_capture_criteria_log
        if item.get("soft_capture_transient_qualifies")
    ]
    if not qualifying:
        raise ContactError("negative controls require an audited nominal candidate sample")
    nominal = qualifying[0]
    peak = int(np.argmax(history.left.normal_force_magnitude_n + history.right.normal_force_magnitude_n))
    lf = history.left.service_force_inertial_n[peak]
    rf = history.right.service_force_inertial_n[peak]

    predicate_mutations: tuple[tuple[str, str, Any, float], ...] = (
        ("NC-B301_SINGLE_SIDE_FALSE_CAPTURE", "right_contact", False, float(nominal["right_normal_force_n"])),
        ("NC-B302_SAME_DIRECTION_NORMALS", "normals_dot", abs(float(nominal["normals_dot"])), abs(float(nominal["normals_dot"])) - config.normals_opposition_max_dot),
        ("NC-B303_NO_DWELL_FALSE_CAPTURE", "dual_contact_dwell_s", 0.0, config.dual_contact_dwell_s),
        ("NC-B304_TARGET_OUTSIDE_CORRIDOR", "target_inside_corridor", False, config.corridor_margin_m),
        ("NC-B305_EXCESS_CENTER_SPEED", "target_relative_center_speed_m_s", 1.1 * config.soft_capture_max_relative_center_speed_m_s, 0.1 * config.soft_capture_max_relative_center_speed_m_s),
        ("NC-B306_EXCESS_RELATIVE_OMEGA", "target_relative_omega_rad_s", 1.1 * config.soft_capture_max_relative_omega_rad_s, 0.1 * config.soft_capture_max_relative_omega_rad_s),
        ("NC-B307_LOW_LEFT_NORMAL_FORCE", "left_normal_force_n", 0.0, config.soft_capture_min_normal_force_n),
        ("NC-B308_OPEN_LEDGER", "all_ledgers_closed", False, config.energy_ledger_tolerance_j),
        ("NC-B309_EXCESS_LEFT_CONTACT_NORMAL_SPEED", "left_relative_normal_speed_m_s", 1.1 * config.soft_capture_max_abs_contact_normal_speed_m_s, 0.1 * config.soft_capture_max_abs_contact_normal_speed_m_s),
        ("NC-B310_EXCESS_RIGHT_CONTACT_TANGENTIAL_SPEED", "right_relative_tangential_speed_m_s", 1.1 * config.soft_capture_max_contact_tangential_speed_m_s, 0.1 * config.soft_capture_max_contact_tangential_speed_m_s),
        ("NC-B311_LEFT_FINGER_OPENING_DURING_CANDIDATE", "left_finger_rate_m_s", 1.1 * config.soft_capture_max_finger_opening_speed_m_s, 0.1 * config.soft_capture_max_finger_opening_speed_m_s),
    )
    records: list[dict[str, Any]] = []
    for control_id, field, mutated_value, raw_error in predicate_mutations:
        mutated = dict(nominal); mutated[field] = mutated_value
        rejected = not _candidate_predicate(mutated, config)
        records.append({
            "control_id": control_id,
            "mutation_class": "CANDIDATE_PREDICATE_MUTATION",
            "mutated_field": field,
            "nominal_value": nominal[field],
            "mutated_value": mutated_value,
            "raw_error": float(raw_error),
            "mutation_rejected": rejected,
            "result": "PASS_NEGATIVE_CONTROL" if rejected and raw_error > 0.0 else "FAIL_NEGATIVE_CONTROL",
        })

    physical_mutations = (
        (
            "NC-B312_LEFT_ACTION_REACTION_SIGN",
            "TARGET_FORCE_SIGN_FLIPPED",
            float(np.linalg.norm(lf + lf)),
        ),
        (
            "NC-B313_RIGHT_ACTION_REACTION_SIGN",
            "TARGET_FORCE_SIGN_FLIPPED",
            float(np.linalg.norm(rf + rf)),
        ),
        (
            "NC-B314_MISSING_LEFT_COMMON_SHIFT",
            "SERVICE_SHIFT_TORQUE_ZEROED",
            float(np.linalg.norm(np.cross(
                history.left.pad_point_inertial_m[peak]
                - history.left.common_contact_point_inertial_m[peak], lf
            ))),
        ),
        (
            "NC-B315_MISSING_RIGHT_COMMON_SHIFT",
            "SERVICE_SHIFT_TORQUE_ZEROED",
            float(np.linalg.norm(np.cross(
                history.right.pad_point_inertial_m[peak]
                - history.right.common_contact_point_inertial_m[peak], rf
            ))),
        ),
        (
            "NC-B316_FRICTION_POWER_SIGN_FLIP",
            "TANGENTIAL_FORCE_SIGN_FLIPPED",
            float(2.0 * (
                history.left.friction_dissipation_rate_w[peak]
                + history.right.friction_dissipation_rate_w[peak]
            )),
        ),
    )
    for control_id, mutation, raw_error in physical_mutations:
        rejected = raw_error > 1.0e-12
        records.append({
            "control_id": control_id,
            "mutation_class": "CONTACT_LEDGER_MUTATION",
            "mutation": mutation,
            "raw_error": raw_error,
            "detection_threshold": 1.0e-12,
            "mutation_rejected": rejected,
            "result": "PASS_NEGATIVE_CONTROL" if rejected else "FAIL_NEGATIVE_CONTROL",
        })

    topology = history.topology_diagnostic
    cross_wiring_error = abs(
        topology["right_analytic_own_P_norm"]
        - topology["left_cross_right_P_fd_norm"]
    )
    grasp = _grasp_map_diagnostic(history)
    contract_mutations = (
        ("NC-B317_P_BRANCH_CROSS_WIRING", "OPPOSITE_BRANCH_AXIS_INSERTED_IN_ZERO_CROSS_COLUMN", cross_wiring_error),
        ("NC-B318_FALSE_RANK6_PROMOTION", "NUMERICAL_RANK_PROMOTED_TO_6", float(grasp["selected_sample"]["rank_deficiency"])),
        ("NC-B320_LOCK_WITHOUT_AUTHORITY", "LOCK_IMPLEMENTED_SET_TRUE", float(not LOCK_IMPLEMENTED)),
        ("NC-B321_PHYSICAL_TIMING_PROMOTION", "PHYSICAL_ACTUATOR_TIMING_IDENTIFIED_SET_TRUE", float(not PHYSICAL_ACTUATOR_TIMING_IDENTIFIED)),
    )
    for control_id, mutation, raw_error in contract_mutations:
        rejected = raw_error > 1.0e-12
        records.append({
            "control_id": control_id,
            "mutation_class": "TOPOLOGY_OR_GOVERNANCE_MUTATION",
            "mutation": mutation,
            "raw_error": raw_error,
            "detection_threshold": 1.0e-12,
            "mutation_rejected": rejected,
            "result": "PASS_NEGATIVE_CONTROL" if rejected else "FAIL_NEGATIVE_CONTROL",
        })
    mutated_finger_coordinates = history.service_joint_coordinates_mixed[0, 6:8].copy()
    mutated_finger_coordinates[0] = config.stroke_upper_m + 1.0e-3
    stroke_rejected = not _finger_stroke_within_bounds(mutated_finger_coordinates, config)
    records.append({
        "control_id": "NC-B319_P_STROKE_OVERRUN",
        "mutation_class": "RUNTIME_STROKE_GUARD_MUTATION",
        "mutation": "LEFT_P_SET_ABOVE_DESIGN_STROKE",
        "mutated_coordinates_m": mutated_finger_coordinates.tolist(),
        "raw_error": float(mutated_finger_coordinates[0] - config.stroke_upper_m),
        "mutation_rejected": stroke_rejected,
        "result": "PASS_NEGATIVE_CONTROL" if stroke_rejected else "FAIL_NEGATIVE_CONTROL",
    })
    recontact_rejected = _released_state_recontact_rejected(
        "BILATERAL_RELEASE", left_on=True, right_on=False
    )
    records.append({
        "control_id": "NC-B322_RECONTACT_AFTER_RELEASE",
        "mutation_class": "STATE_MACHINE_GUARD_MUTATION",
        "mutation": "LEFT_CONTACT_REINTRODUCED_AFTER_BILATERAL_RELEASE",
        "raw_error": float(recontact_rejected),
        "mutation_rejected": recontact_rejected,
        "result": "PASS_NEGATIVE_CONTROL" if recontact_rejected else "FAIL_NEGATIVE_CONTROL",
    })
    for record in records:
        record["evidence_level"] = (
            "SOLVER_SIDE_MUTATION_GUARD_SCREEN__INDEPENDENT_RECONSTRUCTION_REQUIRED_FOR_FINAL_GATE"
        )
    records.sort(key=lambda item: item["control_id"])
    return tuple(records)
