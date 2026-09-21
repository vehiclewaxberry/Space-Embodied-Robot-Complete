"""Forced synthetic P-joint retraction on the hash-bound B4E active model.

The module adds a signed actuator-work state to the 29-state B4E attached
service model.  It is intentionally an algorithm-only diagnostic: the two
input channels are generalized forces, not a motor, transmission, latch, or
physical release model.

All geometry checks are fail-closed.  In particular, every accepted sample
and every RK4/midpoint stage must remain inside the inherited synthetic
P-stroke domain and must admit the registered centred gap derivative.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sys
from typing import Any, Callable, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
PHASE_ROOT = HERE.parent
DIAGNOSTIC_ROOT = PHASE_ROOT.parent
B4E_ROOT = DIAGNOSTIC_ROOT / "phase_b4_post_freeze_synthetic_6d_solver"
for candidate in (B4E_ROOT, DIAGNOSTIC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from b4_solver import constraint_solver as b4e  # noqa: E402


STATE_SIZE = 30
SERVICE_STATE_SIZE = 29
WORK_STATE_INDEX = 29
P_FORCE_INDICES = (12, 13)
P_COORDINATE_INDICES = (6, 7)
P_DOMAIN_M = ((0.0, 0.0715), (0.0, 0.0715))
CENTERED_SIGN_STEP_M = 1.0e-7
REGISTERED_OPENING_SIGNS = (1, 1)
REFERENCE_FORCE_N = 0.024542335689275555
ACTIVE_DURATION_S = 0.08
COMMAND_ZERO_TOLERANCE_N = 1.0e-12


class ForcedRetractionError(RuntimeError):
    """Fail-closed numerical or contract error in the B4G solver."""


class DomainExit(ForcedRetractionError):
    """A stage left the registered synthetic geometry domain.

    ``record`` is deliberately preserved so a caller can retain the first
    rejected raw stage without clipping or extrapolating it.
    """

    def __init__(self, reason: str, record: dict[str, Any]) -> None:
        super().__init__(reason)
        self.reason = str(reason)
        self.record = dict(record)


@dataclass(frozen=True)
class CommandArm:
    """One finger's dimensionless amplitude, delay, and command duration."""

    alpha: float
    delay_s: float
    duration_s: float

    def __post_init__(self) -> None:
        values = (float(self.alpha), float(self.delay_s), float(self.duration_s))
        if not all(math.isfinite(value) for value in values):
            raise ForcedRetractionError("NONFINITE_COMMAND_ARM")
        if self.alpha < 0.0 or self.delay_s < 0.0 or self.duration_s < 0.0:
            raise ForcedRetractionError("NEGATIVE_COMMAND_ARM_PARAMETER")


@dataclass(frozen=True)
class ForcedCommand:
    """Registered two-finger synthetic generalized-force command."""

    left: CommandArm
    right: CommandArm
    command_id: str = "UNSPECIFIED_SYNTHETIC_COMMAND"

    def end_time_s(self, acquisition_time_s: float) -> float:
        """Return the latest support end, including a deliberately-off arm."""

        acquisition = float(acquisition_time_s)
        return max(
            acquisition + self.left.delay_s + self.left.duration_s,
            acquisition + self.right.delay_s + self.right.duration_s,
        )

    @classmethod
    def zero(cls, command_id: str = "A0_ZERO_INPUT") -> "ForcedCommand":
        """Construct an exact-zero command with no support interval."""

        arm = CommandArm(0.0, 0.0, 0.0)
        return cls(arm, arm, command_id)


@dataclass(frozen=True)
class OpeningAudit:
    """Raw centred gap-Jacobian audit in native metres."""

    p_coordinates_m: np.ndarray
    raw_gap_jacobian: np.ndarray
    diagonal_derivatives: np.ndarray
    signs: tuple[int, int]
    nominal_gaps_m: np.ndarray
    nominal_gap_rates_m_s: np.ndarray
    contact_force_max_n: float
    contact_torque_max_n_m: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "P_coordinates_m_left_right": self.p_coordinates_m.tolist(),
            "raw_gap_jacobian_dimensionless": self.raw_gap_jacobian.tolist(),
            "diagonal_gap_derivatives_dimensionless": self.diagonal_derivatives.tolist(),
            "opening_sign_left_right": list(self.signs),
            "nominal_gap_m_left_right": self.nominal_gaps_m.tolist(),
            "nominal_gap_rate_m_s_left_right": self.nominal_gap_rates_m_s.tolist(),
            "contact_force_max_N": float(self.contact_force_max_n),
            "contact_torque_max_N_m": float(self.contact_torque_max_n_m),
        }


@dataclass(frozen=True)
class ForcedRunResult:
    """One fresh forced-active case with raw accepted arrays and metadata."""

    case_id: str
    method: str
    step_s: float
    event: Any
    acquisition: Any
    command: ForcedCommand
    time_s: np.ndarray
    state_30: np.ndarray
    applied_q_p_n: np.ndarray
    actuator_power_w: np.ndarray
    left_gap_m: np.ndarray
    right_gap_m: np.ndarray
    left_gap_rate_m_s: np.ndarray
    right_gap_rate_m_s: np.ndarray
    target_position_m: np.ndarray
    target_quaternion_wxyz: np.ndarray
    target_twist_mixed: np.ndarray
    total_linear_momentum_n_s: np.ndarray
    total_angular_momentum_n_m_s: np.ndarray
    total_kinetic_energy_j: np.ndarray
    sample_ledgers: dict[str, np.ndarray]
    stage_audits: tuple[dict[str, Any], ...]
    clearance: dict[str, Any]
    terminal_status: str
    geometry_domain_pass: bool
    synthetic_removal_executed: bool
    post_release: dict[str, Any] | None
    failure: dict[str, Any] | None
    search_endpoint: dict[str, Any] | None

    @property
    def signed_work_j(self) -> np.ndarray:
        """Return the accepted augmented signed-work history."""

        return self.state_30[:, WORK_STATE_INDEX]

    @property
    def command_q_14(self) -> np.ndarray:
        """Return the saved command in the frozen 14-channel layout."""

        command = np.zeros((len(self.applied_q_p_n), 14), dtype=float)
        command[:, 12:14] = self.applied_q_p_n
        return command


def _as_state_30(value: Sequence[float]) -> np.ndarray:
    state = np.asarray(value, dtype=float)
    if state.shape != (STATE_SIZE,) or not np.all(np.isfinite(state)):
        raise ForcedRetractionError("INVALID_FORCED_STATE_30")
    return state.copy()


def _service_with_coordinate(service: Any, coordinate_index: int, value_m: float) -> Any:
    coordinates = np.asarray(service.joint_coordinates_mixed, dtype=float).copy()
    coordinates[coordinate_index] = float(value_m)
    return b4e.ServiceState(
        np.asarray(service.base_position_inertial_m, dtype=float).copy(),
        np.asarray(service.base_quaternion_body_to_inertial_wxyz, dtype=float).copy(),
        coordinates,
        np.asarray(service.nu_s_mixed, dtype=float).copy(),
    )


def _raw_contact_observations(
    model: Any,
    service: Any,
    snapshot: Any | None,
    *,
    independent_target: Any | None = None,
) -> tuple[Any, tuple[Any, Any]]:
    if (snapshot is None) == (independent_target is None):
        raise ForcedRetractionError("EXACTLY_ONE_GAP_TARGET_SOURCE_REQUIRED")
    if independent_target is None:
        target, _, _, _, _ = b4e.target_from_snapshot(model, service, snapshot)
    else:
        target = b4e.validate_target_state(independent_target)
    observations = b4e.evaluate_dual_contact(
        model, service, target, b4e.DualContactConfig(), enabled=False,
    )
    if len(observations) != 2:
        raise ForcedRetractionError("DUAL_CONTACT_OBSERVATION_COUNT_INVALID")
    return target, (observations[0], observations[1])


def opening_signs(
    model: Any,
    service: Any,
    snapshot: Any | None = None,
    *,
    independent_target: Any | None = None,
    step_m: float = CENTERED_SIGN_STEP_M,
    expected_signs: Sequence[int] = REGISTERED_OPENING_SIGNS,
    time_s: float | None = None,
    stage_label: str = "OPENING_SIGN_AUDIT",
) -> OpeningAudit:
    """Recompute the full raw 2x2 P-to-gap Jacobian by centred differences.

    A centred perturbation that would leave the inherited P domain is itself a
    fail-closed domain exit; no one-sided derivative or clipping is permitted.
    """

    service = model.validate_service_state(service)
    difference = float(step_m)
    if not math.isfinite(difference) or difference <= 0.0:
        raise ForcedRetractionError("INVALID_CENTERED_SIGN_STEP")
    expected = tuple(int(value) for value in expected_signs)
    if expected != REGISTERED_OPENING_SIGNS:
        raise ForcedRetractionError("UNREGISTERED_EXPECTED_OPENING_SIGNS")
    p_coordinates = np.asarray(service.joint_coordinates_mixed[6:8], dtype=float)
    base_record: dict[str, Any] = {
        "time_s": None if time_s is None else float(time_s),
        "stage_label": str(stage_label),
        "P_coordinates_m_left_right": p_coordinates.tolist(),
        "centered_step_m": difference,
    }
    for side, (coordinate, bounds) in enumerate(zip(p_coordinates, P_DOMAIN_M)):
        lower, upper = bounds
        if coordinate < lower or coordinate > upper:
            record = dict(base_record, failed_side=side, reason="P_COORDINATE_OUTSIDE_CLOSED_DOMAIN")
            raise DomainExit("P_COORDINATE_OUTSIDE_CLOSED_DOMAIN", record)
        if coordinate - difference < lower or coordinate + difference > upper:
            record = dict(base_record, failed_side=side, reason="CENTERED_GAP_DERIVATIVE_OUTSIDE_DOMAIN")
            raise DomainExit("CENTERED_GAP_DERIVATIVE_OUTSIDE_DOMAIN", record)

    if (snapshot is None) == (independent_target is None):
        raise ForcedRetractionError("EXACTLY_ONE_OPENING_TARGET_SOURCE_REQUIRED")
    _, nominal = _raw_contact_observations(
        model, service, snapshot, independent_target=independent_target,
    )
    nominal_gaps = np.array([float(item.gap_m) for item in nominal])
    nominal_rates = np.array([float(item.relative_normal_speed_m_s) for item in nominal])
    contact_force = max(float(np.linalg.norm(item.service_force_inertial_n)) for item in nominal)
    contact_torque = max(float(np.linalg.norm(item.service_shift_torque_inertial_n_m)) for item in nominal)
    jacobian = np.empty((2, 2), dtype=float)
    for p_column, coordinate_index in enumerate(P_COORDINATE_INDICES):
        coordinate = float(service.joint_coordinates_mixed[coordinate_index])
        minus = _service_with_coordinate(service, coordinate_index, coordinate - difference)
        plus = _service_with_coordinate(service, coordinate_index, coordinate + difference)
        _, observations_minus = _raw_contact_observations(
            model, minus, snapshot, independent_target=independent_target,
        )
        _, observations_plus = _raw_contact_observations(
            model, plus, snapshot, independent_target=independent_target,
        )
        jacobian[:, p_column] = (
            np.array([float(item.gap_m) for item in observations_plus])
            - np.array([float(item.gap_m) for item in observations_minus])
        ) / (2.0 * difference)

    diagonal = np.diag(jacobian).copy()
    signs = tuple(int(np.sign(value)) for value in diagonal)
    audit = OpeningAudit(
        p_coordinates.copy(), jacobian, diagonal, signs, nominal_gaps,
        nominal_rates, contact_force, contact_torque,
    )
    if not np.all(np.isfinite(jacobian)):
        raise ForcedRetractionError("NONFINITE_RAW_GAP_JACOBIAN")
    if any(value <= 0.0 for value in diagonal) or signs != expected:
        record = dict(base_record, reason="OPENING_SIGN_CHANGED_OR_NONPOSITIVE", **audit.as_dict())
        raise DomainExit("OPENING_SIGN_CHANGED_OR_NONPOSITIVE", record)
    if contact_force > 1.0e-12 or contact_torque > 1.0e-12:
        raise ForcedRetractionError("CONTACT_KERNEL_NOT_DISABLED_DURING_ACTIVE_STAGE")
    return audit


def sin2_profile_exact(time_from_start_s: float, duration_s: float) -> float:
    """Return the registered ``sin(pi*t/T)^2`` shape with exact-zero ends."""

    elapsed = float(time_from_start_s)
    duration = float(duration_s)
    if not math.isfinite(elapsed) or not math.isfinite(duration) or duration < 0.0:
        raise ForcedRetractionError("INVALID_COMMAND_PROFILE_TIME")
    if duration == 0.0 or elapsed <= 0.0 or elapsed >= duration:
        return 0.0
    value = math.sin(math.pi * elapsed / duration)
    return float(value * value)


def force_vector(
    command: ForcedCommand,
    time_s: float,
    acquisition_time_s: float,
    q_ref_n: float = REFERENCE_FORCE_N,
    opening_sign_vector: Sequence[int] = REGISTERED_OPENING_SIGNS,
) -> np.ndarray:
    """Return the 14D P-only generalized force at an absolute time."""

    reference = float(q_ref_n)
    if not math.isfinite(reference) or reference <= 0.0:
        raise ForcedRetractionError("INVALID_REFERENCE_FORCE")
    signs = tuple(int(value) for value in opening_sign_vector)
    if len(signs) != 2 or any(value not in (-1, 1) for value in signs):
        raise ForcedRetractionError("INVALID_CONSUMED_OPENING_SIGN_VECTOR")
    force = np.zeros(14, dtype=float)
    for output_index, arm, sign in zip(P_FORCE_INDICES, (command.left, command.right), signs):
        start = float(acquisition_time_s) + arm.delay_s
        profile = sin2_profile_exact(float(time_s) - start, arm.duration_s)
        if profile != 0.0 and arm.alpha != 0.0:
            force[output_index] = arm.alpha * sign * reference * profile
    # This exact comparison is intentional: no base/R effort is tolerated.
    if np.any(force[:12] != 0.0):
        raise ForcedRetractionError("FORCE_OUTSIDE_P_CHANNELS")
    return force


def _stage_audit(
    model: Any,
    snapshot: Any,
    service: Any,
    generalized_force: np.ndarray,
    *,
    time_s: float,
    stage_label: str,
    consumed_opening_signs: Sequence[int] = REGISTERED_OPENING_SIGNS,
) -> tuple[OpeningAudit, dict[str, Any]]:
    audit = opening_signs(
        model, service, snapshot, time_s=time_s, stage_label=stage_label,
    )
    if generalized_force.shape != (14,) or not np.all(np.isfinite(generalized_force)):
        raise ForcedRetractionError("INVALID_GENERALIZED_FORCE")
    p_only = bool(np.all(generalized_force[:12] == 0.0))
    if not p_only:
        raise ForcedRetractionError("FORCE_OUTSIDE_P_CHANNELS")
    consumed = tuple(int(value) for value in consumed_opening_signs)
    record = {
        "time_s": float(time_s),
        "stage_label": str(stage_label),
        **audit.as_dict(),
        "generalized_force_14": generalized_force.tolist(),
        "consumed_opening_sign_left_right": list(consumed),
        "consumed_sigma_equals_raw_and_registered": bool(
            consumed == audit.signs == REGISTERED_OPENING_SIGNS
        ),
        "Q_base_and_R_exact_zero": p_only,
        "contact_kernel_enabled": False,
        "accepted": True,
    }
    if consumed != audit.signs or consumed != REGISTERED_OPENING_SIGNS:
        failed = dict(record, accepted=False, reason="CONSUMED_OPENING_SIGN_MISMATCH")
        raise DomainExit("CONSUMED_OPENING_SIGN_MISMATCH", failed)
    return audit, record


def _stage_code(label: str) -> int:
    """Map a readable stage label onto the frozen numeric evidence code."""

    if label.startswith("ACCEPTED_SAMPLE") or label == "EXACT_REMOVAL_EVENT":
        return 0
    if label.endswith("_MIDPOINT"):
        return 5
    for suffix, code in (("_K1", 1), ("_K2", 2), ("_K3", 3), ("_K4", 4)):
        if label.endswith(suffix):
            return code
    return 0


def forced_rhs(
    model: Any,
    snapshot: Any,
    command: ForcedCommand,
    acquisition_time_s: float,
    q_ref_n: float,
    time_s: float,
    state_30: Sequence[float],
    *,
    stage_label: str = "RHS",
    audit_sink: list[dict[str, Any]] | None = None,
    consumed_opening_signs: Sequence[int] = REGISTERED_OPENING_SIGNS,
) -> np.ndarray:
    """Evaluate the time-dependent 30D forced attached-state derivative."""

    state = _as_state_30(state_30)
    service = b4e._service_from_active_vector(state[:SERVICE_STATE_SIZE])
    generalized_force = force_vector(
        command, time_s, acquisition_time_s, q_ref_n, consumed_opening_signs,
    )
    try:
        _, record = _stage_audit(
            model, snapshot, service, generalized_force,
            time_s=float(time_s), stage_label=stage_label,
            consumed_opening_signs=consumed_opening_signs,
        )
    except DomainExit as error:
        failed = dict(error.record)
        failed.update({"accepted": False, "generalized_force_14": generalized_force.tolist()})
        if audit_sink is not None:
            audit_sink.append(failed)
        raise

    mass, bias, _, _, _, _ = b4e._active_formula_terms(model, service, snapshot)
    eigenvalues = np.linalg.eigvalsh(0.5 * (mass + mass.T))
    if not np.all(np.isfinite(eigenvalues)) or float(eigenvalues[0]) <= 0.0:
        raise ForcedRetractionError("FORCED_ACTIVE_MASS_NOT_SPD")
    acceleration = b4e._cholesky_solve(mass, generalized_force - bias)
    quaternion_rate = 0.5 * b4e.quat_product(
        np.array((0.0, *service.nu_s_mixed[3:6])),
        service.base_quaternion_body_to_inertial_wxyz,
    )
    power = float(generalized_force[12:14] @ service.nu_s_mixed[12:14])
    derivative = np.concatenate((
        service.nu_s_mixed[:3], quaternion_rate,
        service.nu_s_mixed[6:], acceleration, np.array((power,)),
    ))
    if derivative.shape != (STATE_SIZE,) or not np.all(np.isfinite(derivative)):
        raise ForcedRetractionError("NONFINITE_FORCED_RHS")
    cholesky = np.linalg.cholesky(0.5 * (mass + mass.T))
    record["service_state_29"] = state[:SERVICE_STATE_SIZE].tolist()
    record["stage_code"] = _stage_code(stage_label)
    record["mass_min_eigenvalue"] = float(eigenvalues[0])
    record["mass_cholesky_min_diagonal"] = float(np.min(np.diag(cholesky)))
    record["actuator_power_W"] = power
    if audit_sink is not None:
        audit_sink.append(record)
    return derivative


def _advance(
    method: str,
    rhs: Callable[[float, np.ndarray, str], np.ndarray],
    time_s: float,
    state: np.ndarray,
    step_s: float,
    *,
    label_prefix: str,
) -> np.ndarray:
    """Advance one time-dependent RK4 or explicit-midpoint step."""

    h = float(step_s)
    if not math.isfinite(h) or h <= 0.0:
        raise ForcedRetractionError("INVALID_FORCED_STEP")
    if method == "rk4":
        k1 = rhs(time_s, state, f"{label_prefix}_K1")
        k2 = rhs(time_s + 0.5 * h, state + 0.5 * h * k1, f"{label_prefix}_K2")
        k3 = rhs(time_s + 0.5 * h, state + 0.5 * h * k2, f"{label_prefix}_K3")
        k4 = rhs(time_s + h, state + h * k3, f"{label_prefix}_K4")
        result = state + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    elif method == "midpoint":
        k1 = rhs(time_s, state, f"{label_prefix}_K1")
        result = state + h * rhs(
            time_s + 0.5 * h, state + 0.5 * h * k1, f"{label_prefix}_MIDPOINT",
        )
    else:
        raise ForcedRetractionError(f"UNKNOWN_FORCED_INTEGRATOR:{method}")
    if result.shape != (STATE_SIZE,) or not np.all(np.isfinite(result)):
        raise ForcedRetractionError("NONFINITE_FORCED_STEP_RESULT")
    result = result.copy()
    result[3:7] = b4e._canonical_quaternion(result[3:7])
    return result


def _initial_conditions(model: Any, event: Any, acquisition: Any) -> tuple[np.ndarray, dict[str, Any]]:
    service = b4e.ServiceState(
        event.service.base_position_inertial_m.copy(),
        event.service.base_quaternion_body_to_inertial_wxyz.copy(),
        event.service.joint_coordinates_mixed.copy(),
        acquisition.eta_plus.copy(),
    )
    service = model.validate_service_state(service)
    target, _, _, _, _ = b4e.target_from_snapshot(model, service, acquisition.snapshot)
    service_ledger = model.momentum_energy(service)
    target_ledger = b4e.target_momentum_energy(target)
    fixed_dissipation = float(event.b3_dissipation_j + acquisition.energy_audit["D_switch_J"])
    constants = {
        "linear_momentum": service_ledger.linear_momentum_n_s + target_ledger.linear_momentum_n_s,
        "angular_momentum": (
            service_ledger.angular_momentum_about_inertial_origin_n_m_s
            + target_ledger.angular_momentum_about_inertial_origin_n_m_s
        ),
        "energy_minus_work_J": (
            service_ledger.kinetic_energy_j + target_ledger.kinetic_energy_j + fixed_dissipation
        ),
        "fixed_dissipation_J": fixed_dissipation,
    }
    return np.concatenate((b4e._service_to_active_vector(service), np.zeros(1))), constants


def _sample(
    model: Any,
    acquisition: Any,
    command: ForcedCommand,
    q_ref_n: float,
    time_s: float,
    state: np.ndarray,
    constants: dict[str, Any],
    *,
    label: str,
    audit_sink: list[dict[str, Any]] | None = None,
    consumed_opening_signs: Sequence[int] = REGISTERED_OPENING_SIGNS,
) -> dict[str, Any]:
    service = b4e._service_from_active_vector(state[:SERVICE_STATE_SIZE])
    generalized_force = force_vector(
        command, time_s, acquisition.acquisition_time_s, q_ref_n,
        consumed_opening_signs,
    )
    try:
        opening, stage_record = _stage_audit(
            model, acquisition.snapshot, service, generalized_force,
            time_s=time_s, stage_label=label,
            consumed_opening_signs=consumed_opening_signs,
        )
    except DomainExit as error:
        if audit_sink is not None:
            audit_sink.append(dict(error.record))
        raise
    mass, bias, a, target, adot_eta, target_mass = b4e._active_formula_terms(
        model, service, acquisition.snapshot,
    )
    acceleration = b4e._cholesky_solve(mass, generalized_force - bias)
    target_acceleration = a @ acceleration + adot_eta
    service_mass = model.mass_matrix(service)
    full_mass = b4e._block_diagonal(service_mass, target_mass)
    full_bias = np.concatenate((model.bias_effort(service), b4e._target_bias(target)))
    full_acceleration = np.concatenate((acceleration, target_acceleration))
    full_applied = np.concatenate((generalized_force, np.zeros(6)))
    full_residual = full_mass @ full_acceleration + full_bias - full_applied
    embedding = np.vstack((np.eye(14), a))
    reduced_residual = embedding.T @ full_residual

    service_ledger = model.momentum_energy(service)
    target_ledger = b4e.target_momentum_energy(target)
    total_linear = service_ledger.linear_momentum_n_s + target_ledger.linear_momentum_n_s
    total_angular = (
        service_ledger.angular_momentum_about_inertial_origin_n_m_s
        + target_ledger.angular_momentum_about_inertial_origin_n_m_s
    )
    energy_minus_work = (
        service_ledger.kinetic_energy_j + target_ledger.kinetic_energy_j
        + constants["fixed_dissipation_J"] - float(state[WORK_STATE_INDEX])
    )
    combined_velocity = np.concatenate((service.nu_s_mixed, target.twist_inertial_mixed))
    actuator_power = float(generalized_force[12:14] @ service.nu_s_mixed[12:14])
    cholesky = np.linalg.cholesky(0.5 * (mass + mass.T))
    stage_record.update({
        "stage_code": 0,
        "service_state_29": state[:SERVICE_STATE_SIZE].tolist(),
        "mass_cholesky_min_diagonal": float(np.min(np.diag(cholesky))),
        "actuator_power_W": actuator_power,
    })
    if audit_sink is not None:
        audit_sink.append(stage_record)
    return {
        "target": target,
        "generalized_force": generalized_force,
        "actuator_power_W": actuator_power,
        "left_gap_m": float(opening.nominal_gaps_m[0]),
        "right_gap_m": float(opening.nominal_gaps_m[1]),
        "left_gap_rate_m_s": float(opening.nominal_gap_rates_m_s[0]),
        "right_gap_rate_m_s": float(opening.nominal_gap_rates_m_s[1]),
        "opening_audit": opening.as_dict(),
        "linear_momentum_drift_N_s": float(np.linalg.norm(total_linear - constants["linear_momentum"])),
        "angular_momentum_drift_N_m_s": float(np.linalg.norm(total_angular - constants["angular_momentum"])),
        "total_linear_momentum_N_s": total_linear,
        "total_angular_momentum_N_m_s": total_angular,
        "total_kinetic_energy_J": float(
            service_ledger.kinetic_energy_j + target_ledger.kinetic_energy_j
        ),
        "energy_minus_work_residual_J": abs(energy_minus_work - constants["energy_minus_work_J"]),
        "ideal_constraint_power_W": abs(float(combined_velocity @ full_residual)),
        "active_contact_force_N": float(opening.contact_force_max_n),
        "active_contact_torque_N_m": float(opening.contact_torque_max_n_m),
        "full_residual_20": full_residual,
        "reduced_residual_14": reduced_residual,
        "forced_full_residual_service_base_linear_N": float(np.max(np.abs(full_residual[0:3]))),
        "forced_full_residual_service_base_angular_N_m": float(np.max(np.abs(full_residual[3:6]))),
        "forced_full_residual_service_R_joint_N_m": float(np.max(np.abs(full_residual[6:12]))),
        "forced_full_residual_service_P_joint_N": float(np.max(np.abs(full_residual[12:14]))),
        "forced_full_residual_target_linear_N": float(np.max(np.abs(full_residual[14:17]))),
        "forced_full_residual_target_angular_N_m": float(np.max(np.abs(full_residual[17:20]))),
        "reduced_residual_base_linear_N": float(np.max(np.abs(reduced_residual[0:3]))),
        "reduced_residual_base_angular_N_m": float(np.max(np.abs(reduced_residual[3:6]))),
        "reduced_residual_R_joint_N_m": float(np.max(np.abs(reduced_residual[6:12]))),
        "reduced_residual_P_joint_N": float(np.max(np.abs(reduced_residual[12:14]))),
        "command_exact_zero": bool(np.all(generalized_force == 0.0)),
    }


_LEDGER_NAMES = (
    "linear_momentum_drift_N_s",
    "angular_momentum_drift_N_m_s",
    "energy_minus_work_residual_J",
    "ideal_constraint_power_W",
    "active_contact_force_N",
    "active_contact_torque_N_m",
    "forced_full_residual_service_base_linear_N",
    "forced_full_residual_service_base_angular_N_m",
    "forced_full_residual_service_R_joint_N_m",
    "forced_full_residual_service_P_joint_N",
    "forced_full_residual_target_linear_N",
    "forced_full_residual_target_angular_N_m",
    "reduced_residual_base_linear_N",
    "reduced_residual_base_angular_N_m",
    "reduced_residual_R_joint_N_m",
    "reduced_residual_P_joint_N",
)


def _ledger_closed(sample: dict[str, Any]) -> bool:
    return bool(
        sample["linear_momentum_drift_N_s"] <= 1.0e-9
        and sample["angular_momentum_drift_N_m_s"] <= 1.0e-9
        and sample["energy_minus_work_residual_J"] <= 1.0e-7
        and sample["ideal_constraint_power_W"] <= 1.0e-10
        and sample["active_contact_force_N"] <= 1.0e-12
        and sample["active_contact_torque_N_m"] <= 1.0e-12
    )


def _reconstruct_event_state(
    method: str,
    rhs: Callable[[float, np.ndarray, str], np.ndarray],
    left_time_s: float,
    left_state: np.ndarray,
    event_time_s: float,
) -> np.ndarray:
    remainder = float(event_time_s) - float(left_time_s)
    if remainder < -b4e.TIME_INTERVAL_MERGE_TOLERANCE_S:
        raise ForcedRetractionError("EVENT_BEFORE_RECONSTRUCTION_BRACKET")
    if abs(remainder) <= b4e.TIME_INTERVAL_MERGE_TOLERANCE_S:
        return left_state.copy()
    return _advance(
        method, rhs, float(left_time_s), left_state, remainder,
        label_prefix="EXACT_EVENT_RECONSTRUCTION",
    )


def _post_stage_audit(
    model: Any,
    time_s: float,
    state_42: Sequence[float],
    *,
    label: str,
    audit_sink: list[dict[str, Any]],
) -> tuple[Any, Any, OpeningAudit]:
    value = np.asarray(state_42, dtype=float)
    if value.shape != (42,) or not np.all(np.isfinite(value)):
        raise ForcedRetractionError("INVALID_POST_RELEASE_STATE_42")
    service = b4e._service_from_active_vector(value[:29])
    target = b4e._target_from_post_vector(value[29:42])
    try:
        opening = opening_signs(
            model, service, None, independent_target=target,
            time_s=float(time_s), stage_label=label,
        )
    except DomainExit as error:
        failed = dict(error.record)
        failed.update({
            "accepted": False,
            "stage_code": _stage_code(label),
            "service_state_29": value[:29].tolist(),
            "target_state_13": value[29:42].tolist(),
            "post_release": True,
        })
        audit_sink.append(failed)
        raise
    audit_sink.append({
        "time_s": float(time_s),
        "stage_label": label,
        "stage_code": _stage_code(label),
        "service_state_29": value[:29].tolist(),
        "target_state_13": value[29:42].tolist(),
        **opening.as_dict(),
        "consumed_opening_sign_left_right": list(REGISTERED_OPENING_SIGNS),
        "consumed_sigma_equals_raw_and_registered": opening.signs == REGISTERED_OPENING_SIGNS,
        "contact_kernel_enabled": False,
        "post_release_command_Q_14": [0.0] * 14,
        "accepted": True,
        "post_release": True,
    })
    return service, target, opening


def _advance_post_release(
    model: Any,
    method: str,
    time_s: float,
    state: np.ndarray,
    step_s: float,
    audit_sink: list[dict[str, Any]],
    *,
    label_prefix: str,
) -> np.ndarray:
    def rhs(stage_time: float, stage_state: np.ndarray, label: str) -> np.ndarray:
        _post_stage_audit(
            model, stage_time, stage_state, label=label, audit_sink=audit_sink,
        )
        return b4e._post_release_rhs(model, stage_state)

    h = float(step_s)
    if method == "rk4":
        k1 = rhs(time_s, state, f"{label_prefix}_K1")
        k2 = rhs(time_s + 0.5 * h, state + 0.5 * h * k1, f"{label_prefix}_K2")
        k3 = rhs(time_s + 0.5 * h, state + 0.5 * h * k2, f"{label_prefix}_K3")
        k4 = rhs(time_s + h, state + h * k3, f"{label_prefix}_K4")
        result = state + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    elif method == "midpoint":
        k1 = rhs(time_s, state, f"{label_prefix}_K1")
        midpoint = state + 0.5 * h * k1
        result = state + h * rhs(
            time_s + 0.5 * h, midpoint, f"{label_prefix}_MIDPOINT",
        )
    else:
        raise ForcedRetractionError(f"UNKNOWN_POST_RELEASE_INTEGRATOR:{method}")
    if not np.all(np.isfinite(result)):
        raise ForcedRetractionError("NONFINITE_POST_RELEASE_STEP_RESULT")
    result = result.copy()
    result[3:7] = b4e._canonical_quaternion(result[3:7])
    result[32:36] = b4e._canonical_quaternion(result[32:36])
    return result


def execute_instrumented_post_release(
    model: Any,
    acquisition: Any,
    service_at_release: Any,
    *,
    release_time_s: float,
    method: str,
    step_s: float,
    signed_work_j: float,
) -> dict[str, Any]:
    """Run and audit B4G's 42D post-release path, then cross-check B4E.

    Geometry and centred opening-sign checks are performed at every RHS stage
    and stored sample using the independent target state.  The hash-bound B4E
    primitive is executed separately as a terminal and mapping cross-check.
    """

    service_before = model.validate_service_state(service_at_release)
    target_before, a_release, _, _, _ = b4e.target_from_snapshot(
        model, service_before, acquisition.snapshot,
    )
    z_before = np.concatenate((service_before.nu_s_mixed, a_release @ service_before.nu_s_mixed))
    service_after = b4e.ServiceState(
        service_before.base_position_inertial_m.copy(),
        service_before.base_quaternion_body_to_inertial_wxyz.copy(),
        service_before.joint_coordinates_mixed.copy(),
        z_before[:14].copy(),
    )
    target_after = b4e.TargetState(
        target_before.position_inertial_m.copy(),
        target_before.quaternion_body_to_inertial_wxyz.copy(),
        z_before[14:20].copy(),
    )
    duration = float(b4e.POST_RELEASE_OBSERVATION_S)
    steps_float = duration / float(step_s)
    steps = int(round(steps_float))
    if steps < 1 or abs(steps_float - steps) > 1.0e-9:
        raise ForcedRetractionError("POST_RELEASE_OBSERVATION_NOT_INTEGER_MULTIPLE")
    state = np.concatenate((
        b4e._service_to_active_vector(service_after),
        b4e._target_to_post_vector(target_after),
    ))
    initial_service_ledger = model.momentum_energy(service_after)
    initial_target_ledger = b4e.target_momentum_energy(target_after)
    initial_linear = initial_service_ledger.linear_momentum_n_s + initial_target_ledger.linear_momentum_n_s
    initial_angular = (
        initial_service_ledger.angular_momentum_about_inertial_origin_n_m_s
        + initial_target_ledger.angular_momentum_about_inertial_origin_n_m_s
    )
    initial_energy = initial_service_ledger.kinetic_energy_j + initial_target_ledger.kinetic_energy_j

    times: list[float] = []
    states: list[np.ndarray] = []
    gaps: list[tuple[float, float]] = []
    rates: list[tuple[float, float]] = []
    total_linear: list[np.ndarray] = []
    total_angular: list[np.ndarray] = []
    total_energy: list[float] = []
    contact_force: list[float] = []
    contact_torque: list[float] = []
    stage_audits: list[dict[str, Any]] = []
    domain_failure: dict[str, Any] | None = None
    for index in range(steps + 1):
        time = float(release_time_s) + index * float(step_s)
        try:
            service, target, opening = _post_stage_audit(
                model, time, state, label=f"ACCEPTED_SAMPLE_{index}",
                audit_sink=stage_audits,
            )
        except DomainExit as error:
            domain_failure = dict(error.record, reason=error.reason)
            break
        service_ledger = model.momentum_energy(service)
        target_ledger = b4e.target_momentum_energy(target)
        times.append(time); states.append(state.copy())
        gaps.append((float(opening.nominal_gaps_m[0]), float(opening.nominal_gaps_m[1])))
        rates.append((float(opening.nominal_gap_rates_m_s[0]), float(opening.nominal_gap_rates_m_s[1])))
        total_linear.append(service_ledger.linear_momentum_n_s + target_ledger.linear_momentum_n_s)
        total_angular.append(
            service_ledger.angular_momentum_about_inertial_origin_n_m_s
            + target_ledger.angular_momentum_about_inertial_origin_n_m_s
        )
        total_energy.append(service_ledger.kinetic_energy_j + target_ledger.kinetic_energy_j)
        contact_force.append(float(opening.contact_force_max_n))
        contact_torque.append(float(opening.contact_torque_max_n_m))
        if index < steps:
            try:
                state = _advance_post_release(
                    model, method, time, state, float(step_s), stage_audits,
                    label_prefix=f"POST_STEP_{index}",
                )
            except DomainExit as error:
                domain_failure = dict(error.record, reason=error.reason)
                break

    parent = b4e.execute_post_release(
        model, acquisition, service_before,
        release_time_s=float(release_time_s), method=method, step_s=float(step_s),
    )
    if states:
        state_array = np.asarray(states)
        gap_array = np.asarray(gaps)
        rate_array = np.asarray(rates)
        linear_array = np.asarray(total_linear)
        angular_array = np.asarray(total_angular)
        energy_array = np.asarray(total_energy)
        clearance = b4e._continuous_clearance_coverage(
            np.asarray(times), gap_array[:, 0], gap_array[:, 1],
            rate_array[:, 0], rate_array[:, 1],
        ) if len(times) >= 2 else {"full_interval_certified": False}
        linear_drift = np.linalg.norm(linear_array - initial_linear, axis=1)
        angular_drift = np.linalg.norm(angular_array - initial_angular, axis=1)
        energy_drift = np.abs(energy_array - initial_energy)
    else:
        state_array = np.empty((0, 42)); gap_array = np.empty((0, 2)); rate_array = np.empty((0, 2))
        linear_array = np.empty((0, 3)); angular_array = np.empty((0, 3)); energy_array = np.empty(0)
        clearance = {"full_interval_certified": False}
        linear_drift = np.empty(0); angular_drift = np.empty(0); energy_drift = np.empty(0)

    parent_service = np.asarray(parent["trace"]["service_state_29"], dtype=float)
    parent_target = np.asarray(parent["trace"]["target_state_13"], dtype=float)
    complete = domain_failure is None and len(states) == steps + 1
    terminal_service_error = (
        float(np.max(np.abs(state_array[-1, :29] - parent_service[-1]))) if complete else math.inf
    )
    terminal_target_error = (
        float(np.max(np.abs(state_array[-1, 29:42] - parent_target[-1]))) if complete else math.inf
    )
    mapping_error = float(np.max(np.abs(z_before - np.asarray(parent["mapping"]["z_before"], dtype=float))))
    crosscheck_pass = bool(
        complete and mapping_error <= 1.0e-12
        and terminal_service_error <= 1.0e-12 and terminal_target_error <= 1.0e-12
    )
    ledger_pass = bool(
        complete and float(np.max(linear_drift)) <= 1.0e-9
        and float(np.max(angular_drift)) <= 1.0e-9
        and float(np.max(energy_drift)) <= 1.0e-7
    )
    contact_pass = bool(
        complete and max(contact_force, default=math.inf) <= 1.0e-12
        and max(contact_torque, default=math.inf) <= 1.0e-12
    )
    passed = bool(
        complete and crosscheck_pass and ledger_pass and contact_pass
        and clearance.get("full_interval_certified") is True
        and parent.get("post_release_passed") is True
    )
    if domain_failure is not None:
        terminal = "DIAGNOSTIC_FAIL_CLOSED_POST_RELEASE_GEOMETRY_DOMAIN"
    elif not crosscheck_pass:
        terminal = "DIAGNOSTIC_FAIL_CLOSED_POST_RELEASE_B4E_CROSSCHECK"
    elif not ledger_pass:
        terminal = "DIAGNOSTIC_FAIL_CLOSED_POST_RELEASE_LEDGER"
    elif not contact_pass:
        terminal = "DIAGNOSTIC_FAIL_CLOSED_POST_RELEASE_CONTACT_REACTIVATED"
    elif not clearance.get("full_interval_certified"):
        terminal = "DIAGNOSTIC_FAIL_CLOSED_POST_REMOVAL_CLEARANCE_REENTRY"
    elif not parent.get("post_release_passed"):
        terminal = str(parent.get("terminal_status"))
    else:
        terminal = "SYNTHETIC_CONSTRAINT_REMOVAL_AND_POST_RELEASE_OBSERVATION_COMPLETE"
    return {
        "release_time_s": float(release_time_s),
        "observation_duration_s": float(times[-1] - times[0]) if len(times) >= 2 else 0.0,
        "method": method,
        "step_s": float(step_s),
        "mapping": parent["mapping"],
        "instrumented_trace": {
            "time_s": times,
            "state_42": state_array.tolist(),
            "service_state_29": state_array[:, :29].tolist(),
            "target_state_13": state_array[:, 29:42].tolist(),
            "left_gap_m": gap_array[:, 0].tolist(),
            "right_gap_m": gap_array[:, 1].tolist(),
            "left_gap_rate_m_s": rate_array[:, 0].tolist(),
            "right_gap_rate_m_s": rate_array[:, 1].tolist(),
            "total_linear_momentum_N_s": linear_array.tolist(),
            "total_angular_momentum_N_m_s": angular_array.tolist(),
            "total_kinetic_energy_J": energy_array.tolist(),
            "contact_force_N": contact_force,
            "contact_torque_N_m": contact_torque,
            "stage_audits": stage_audits,
        },
        "maxima": {
            "linear_momentum_drift_N_s": float(np.max(linear_drift)) if len(linear_drift) else math.inf,
            "angular_momentum_drift_N_m_s": float(np.max(angular_drift)) if len(angular_drift) else math.inf,
            "energy_drift_J": float(np.max(energy_drift)) if len(energy_drift) else math.inf,
            "contact_force_N": max(contact_force, default=math.inf),
            "contact_torque_N_m": max(contact_torque, default=math.inf),
        },
        "clearance": clearance,
        "geometry_domain_pass": domain_failure is None,
        "domain_failure": domain_failure,
        "post_release_stage_audit_count": len(stage_audits),
        "parent_b4e_crosscheck": {
            "mapping_z_before_max_error": mapping_error,
            "terminal_service_state_max_error": terminal_service_error,
            "terminal_target_state_max_error": terminal_target_error,
            "parent_terminal_status": parent.get("terminal_status"),
            "parent_post_release_passed": parent.get("post_release_passed"),
            "passed": crosscheck_pass,
        },
        "signed_W_act_carried_constant_J": float(signed_work_j),
        "actuator_work_reset_on_removal": False,
        "post_release_generalized_force_14": [0.0] * 14,
        "post_release_passed": passed,
        "terminal_status": terminal,
        "physical_release_claimed": False,
    }


def propagate_forced_case(
    model: Any,
    event: Any,
    acquisition: Any,
    command: ForcedCommand,
    *,
    case_id: str,
    method: str,
    step_s: float,
    q_ref_n: float = REFERENCE_FORCE_N,
    end_time_s: float | None = None,
    active_duration_s: float = ACTIVE_DURATION_S,
    consumed_opening_signs: Sequence[int] = REGISTERED_OPENING_SIGNS,
) -> ForcedRunResult:
    """Propagate one forced case and stop at its first exact removal event.

    The clearance certificate is recomputed incrementally after the latest
    command end.  A right-bracket sample needed by the Hermite certificate is
    retained only in ``search_endpoint``; the accepted trajectory is truncated
    at the exactly reintegrated removal state.
    """

    if method not in ("rk4", "midpoint"):
        raise ForcedRetractionError(f"UNKNOWN_FORCED_INTEGRATOR:{method}")
    step = float(step_s)
    if not math.isfinite(step) or step <= 0.0:
        raise ForcedRetractionError("INVALID_FORCED_STEP")
    acquisition_time = float(event.time_s)
    if abs(float(acquisition.acquisition_time_s) - acquisition_time) > 1.0e-14:
        raise ForcedRetractionError("EVENT_ACQUISITION_TIME_MISMATCH")
    terminal_time = acquisition_time + float(active_duration_s) if end_time_s is None else float(end_time_s)
    if terminal_time <= acquisition_time:
        raise ForcedRetractionError("FORCED_HORIZON_NOT_POSITIVE")
    steps_float = (terminal_time - acquisition_time) / step
    steps = int(round(steps_float))
    if steps < 1 or abs(steps_float - steps) > 1.0e-9:
        raise ForcedRetractionError("FORCED_HORIZON_NOT_INTEGER_MULTIPLE")

    state, constants = _initial_conditions(model, event, acquisition)
    stage_audits: list[dict[str, Any]] = []
    rhs = lambda time, value, label: forced_rhs(
        model, acquisition.snapshot, command, acquisition_time, q_ref_n,
        time, value, stage_label=label, audit_sink=stage_audits,
        consumed_opening_signs=consumed_opening_signs,
    )
    times: list[float] = []
    states: list[np.ndarray] = []
    samples: list[dict[str, Any]] = []
    sample_closed: list[bool] = []
    failure: dict[str, Any] | None = None
    search_endpoint: dict[str, Any] | None = None
    clearance: dict[str, Any] = {
        "finite_event": False,
        "status": "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED",
        "global_empty_eligibility_set_claimed": False,
    }
    removal_executed = False
    post_release: dict[str, Any] | None = None
    geometry_pass = True
    command_end = command.end_time_s(acquisition_time)

    try:
        initial_sample = _sample(
            model, acquisition, command, q_ref_n, acquisition_time, state,
            constants, label="ACCEPTED_SAMPLE_0", audit_sink=stage_audits,
            consumed_opening_signs=consumed_opening_signs,
        )
    except DomainExit as error:
        failure = dict(error.record, reason=error.reason)
        return ForcedRunResult(
            case_id, method, step, event, acquisition, command,
            np.empty(0), np.empty((0, STATE_SIZE)), np.empty((0, 2)), np.empty(0),
            np.empty(0), np.empty(0), np.empty(0), np.empty(0),
            np.empty((0, 3)), np.empty((0, 4)), np.empty((0, 6)),
            np.empty((0, 3)), np.empty((0, 3)), np.empty(0),
            {name: np.empty(0) for name in _LEDGER_NAMES}, tuple(stage_audits),
            clearance, "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN", False, False,
            None, failure, None,
        )
    times.append(acquisition_time); states.append(state.copy()); samples.append(initial_sample)
    sample_closed.append(_ledger_closed(initial_sample))

    event_state: np.ndarray | None = None
    event_sample: dict[str, Any] | None = None
    for index in range(steps):
        left_time = times[-1]
        left_state = states[-1]
        try:
            next_state = _advance(
                method, rhs, left_time, left_state, step,
                label_prefix=f"STEP_{index}",
            )
            next_time = acquisition_time + (index + 1) * step
            next_sample = _sample(
                model, acquisition, command, q_ref_n, next_time, next_state,
                constants, label=f"ACCEPTED_SAMPLE_{index + 1}", audit_sink=stage_audits,
                consumed_opening_signs=consumed_opening_signs,
            )
        except DomainExit as error:
            geometry_pass = False
            failure = dict(error.record, reason=error.reason)
            break
        times.append(next_time); states.append(next_state.copy()); samples.append(next_sample)
        sample_closed.append(_ledger_closed(next_sample))

        if next_time + b4e.TIME_INTERVAL_MERGE_TOLERANCE_S < command_end + b4e.CLEARANCE_DWELL_S:
            continue
        interval_certified = np.asarray(sample_closed[:-1], dtype=bool) & np.asarray(sample_closed[1:], dtype=bool)
        command_zero_intervals = np.array(
            [
                times[item] >= command_end - b4e.TIME_INTERVAL_MERGE_TOLERANCE_S
                and samples[item]["command_exact_zero"]
                and samples[item + 1]["command_exact_zero"]
                for item in range(len(times) - 1)
            ],
            dtype=bool,
        )
        interval_certified &= command_zero_intervals
        # Passing command_end-1ms makes B4E's inherited minimum-active-dwell
        # eligibility begin at command_end while preserving its exact root logic.
        clearance_acquisition = max(acquisition_time, command_end - b4e.MINIMUM_ACTIVE_DWELL_S)
        clearance = b4e.certify_earliest_clearance(
            times,
            [sample["left_gap_m"] for sample in samples],
            [sample["right_gap_m"] for sample in samples],
            [sample["left_gap_rate_m_s"] for sample in samples],
            [sample["right_gap_rate_m_s"] for sample in samples],
            acquisition_time_s=clearance_acquisition,
            ledger_interval_certified=interval_certified,
        )
        clearance["command_end_time_s"] = command_end
        clearance["incremental_search"] = True
        if not clearance.get("finite_event"):
            continue

        removal_time = float(clearance["removal_time_s"])
        bracket_index = int(np.searchsorted(np.asarray(times), removal_time, side="right") - 1)
        bracket_index = max(0, min(bracket_index, len(times) - 1))
        if bracket_index == len(times) - 1 and abs(times[-1] - removal_time) > b4e.TIME_INTERVAL_MERGE_TOLERANCE_S:
            raise ForcedRetractionError("REMOVAL_EVENT_NOT_BRACKETED")
        if abs(times[bracket_index] - removal_time) <= b4e.TIME_INTERVAL_MERGE_TOLERANCE_S:
            event_state = states[bracket_index].copy()
            event_sample = samples[bracket_index]
            accepted_count = bracket_index + 1
        else:
            search_endpoint = {
                "time_s": float(times[bracket_index + 1]),
                "state_30": states[bracket_index + 1].tolist(),
                "classification": "COUNTERFACTUAL_ATTACHED_RIGHT_BRACKET_ONLY_NOT_ACCEPTED_AFTER_REMOVAL",
            }
            event_state = _reconstruct_event_state(
                method, rhs, times[bracket_index], states[bracket_index], removal_time,
            )
            event_sample = _sample(
                model, acquisition, command, q_ref_n, removal_time, event_state,
                constants, label="EXACT_REMOVAL_EVENT", audit_sink=stage_audits,
                consumed_opening_signs=consumed_opening_signs,
            )
            accepted_count = bracket_index + 1
            times = times[:accepted_count] + [removal_time]
            states = states[:accepted_count] + [event_state.copy()]
            samples = samples[:accepted_count] + [event_sample]
            sample_closed = sample_closed[:accepted_count] + [_ledger_closed(event_sample)]
        if not event_sample["command_exact_zero"]:
            raise ForcedRetractionError("COMMAND_NONZERO_AT_EXACT_REMOVAL")
        if not _ledger_closed(event_sample):
            raise ForcedRetractionError("ACTIVE_LEDGER_OPEN_AT_EXACT_REMOVAL")
        event_service = b4e._service_from_active_vector(event_state[:SERVICE_STATE_SIZE])
        # The B4G path instruments every independent 42D stage and then calls
        # the hash-bound B4E primitive as a mapping/terminal cross-check.
        post_release = execute_instrumented_post_release(
            model, acquisition, event_service,
            release_time_s=removal_time, method=method, step_s=step,
            signed_work_j=float(event_state[WORK_STATE_INDEX]),
        )
        removal_executed = bool(post_release.get("post_release_passed"))
        break

    if failure is not None:
        terminal_status = "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN"
    elif event_state is not None:
        terminal_status = str(post_release["terminal_status"]) if post_release is not None else "DIAGNOSTIC_FAIL_CLOSED_POST_RELEASE_MISSING"
    elif not all(sample_closed):
        terminal_status = "DIAGNOSTIC_FAIL_CLOSED_ACTIVE_LEDGER"
    else:
        terminal_status = "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED"

    time_array = np.asarray(times, dtype=float)
    state_array = np.asarray(states, dtype=float).reshape((-1, STATE_SIZE))
    q_p = np.asarray([sample["generalized_force"][12:14] for sample in samples], dtype=float).reshape((-1, 2))
    power = np.asarray([sample["actuator_power_W"] for sample in samples], dtype=float)
    ledgers = {
        name: np.asarray([float(sample[name]) for sample in samples], dtype=float)
        for name in _LEDGER_NAMES
    }
    targets = [sample["target"] for sample in samples]
    return ForcedRunResult(
        case_id, method, step, event, acquisition, command,
        time_array, state_array, q_p, power,
        np.asarray([sample["left_gap_m"] for sample in samples]),
        np.asarray([sample["right_gap_m"] for sample in samples]),
        np.asarray([sample["left_gap_rate_m_s"] for sample in samples]),
        np.asarray([sample["right_gap_rate_m_s"] for sample in samples]),
        np.asarray([target.position_inertial_m for target in targets]).reshape((-1, 3)),
        np.asarray([target.quaternion_body_to_inertial_wxyz for target in targets]).reshape((-1, 4)),
        np.asarray([target.twist_inertial_mixed for target in targets]).reshape((-1, 6)),
        np.asarray([sample["total_linear_momentum_N_s"] for sample in samples]).reshape((-1, 3)),
        np.asarray([sample["total_angular_momentum_N_m_s"] for sample in samples]).reshape((-1, 3)),
        np.asarray([sample["total_kinetic_energy_J"] for sample in samples]),
        ledgers, tuple(stage_audits), clearance, terminal_status, geometry_pass,
        removal_executed, post_release, failure, search_endpoint,
    )


def forced_run_to_raw(result: ForcedRunResult) -> dict[str, Any]:
    """Convert a result to an evidence-ready dictionary without hiding arrays."""

    return {
        "case_id": result.case_id,
        "method": result.method,
        "step_s": float(result.step_s),
        "event": b4e.event_to_json(result.event),
        "acquisition": b4e.acquisition_to_json(result.acquisition, include_matrices=False),
        "command": {
            "command_id": result.command.command_id,
            "left": {
                "alpha": result.command.left.alpha,
                "delay_s": result.command.left.delay_s,
                "duration_s": result.command.left.duration_s,
            },
            "right": {
                "alpha": result.command.right.alpha,
                "delay_s": result.command.right.delay_s,
                "duration_s": result.command.right.duration_s,
            },
        },
        "raw": {
            "time_s": result.time_s.tolist(),
            "state_30_service_29_plus_signed_W_act_J": result.state_30.tolist(),
            "applied_Q_P_left_right_N": result.applied_q_p_n.tolist(),
            "command_Q_14": result.command_q_14.tolist(),
            "actuator_power_W": result.actuator_power_w.tolist(),
            "left_gap_m": result.left_gap_m.tolist(),
            "right_gap_m": result.right_gap_m.tolist(),
            "left_gap_rate_m_s": result.left_gap_rate_m_s.tolist(),
            "right_gap_rate_m_s": result.right_gap_rate_m_s.tolist(),
            "target_position_m": result.target_position_m.tolist(),
            "target_quaternion_wxyz": result.target_quaternion_wxyz.tolist(),
            "target_twist_mixed": result.target_twist_mixed.tolist(),
            "total_linear_momentum_N_s": result.total_linear_momentum_n_s.tolist(),
            "total_angular_momentum_N_m_s": result.total_angular_momentum_n_m_s.tolist(),
            "total_kinetic_energy_J": result.total_kinetic_energy_j.tolist(),
            "sample_ledgers": {name: values.tolist() for name, values in result.sample_ledgers.items()},
            "stage_audits": list(result.stage_audits),
        },
        "clearance": result.clearance,
        "terminal_status": result.terminal_status,
        "geometry_domain_pass": result.geometry_domain_pass,
        "synthetic_removal_executed": result.synthetic_removal_executed,
        "post_release": result.post_release,
        "failure": result.failure,
        "search_endpoint": result.search_endpoint,
        "physical_release_claimed": False,
        "minimum_required_force_or_work_claimed": False,
    }
