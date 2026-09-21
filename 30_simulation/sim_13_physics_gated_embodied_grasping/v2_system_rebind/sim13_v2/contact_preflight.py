"""Fail-closed contact preflight contracts for the Sim13 V2 rebind.

This module deliberately stops before contact dynamics.  It validates the
minimum evidence needed by a future contact adapter and provides an analytic
half-sine impulse fixture for regression tests.  It does not detect contact,
solve a contact manifold, estimate loads, or authorize a grasp.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable, Sequence


class ContactState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class CollisionState(str, Enum):
    UNKNOWN_NOT_EVALUATED = "UNKNOWN_NOT_EVALUATED"
    CLEAR_EVALUATED = "CLEAR_EVALUATED"
    COLLISION_DETECTED = "COLLISION_DETECTED"


@dataclass(frozen=True)
class ContactDecision:
    state: ContactState
    reason_codes: tuple[str, ...]
    scope: str = "CONTACT_PREFLIGHT_ONLY_NOT_CONTACT_DYNAMICS"

    @property
    def passed(self) -> bool:
        return self.state is ContactState.PASS


@dataclass(frozen=True)
class ContactAuthority:
    """Authority status for one contact datum.

    Only ``AUTHORITATIVE_RELEASED`` may support a local preflight PASS.  A
    local PASS remains one input to the 12-gate authority join and is never a
    system-level release by itself.
    """

    state: str
    source_sha256: str | None

    @property
    def released(self) -> bool:
        return self.state == "AUTHORITATIVE_RELEASED" and _is_sha256(
            self.source_sha256
        )


@dataclass(frozen=True)
class FingerContact:
    finger_id: str
    normal_force_N: float | None
    tangential_force_N: float | None
    pressure_Pa: float | None


@dataclass(frozen=True)
class LockReceipt:
    receipt_sha256: str | None
    age_s: float | None
    maximum_age_s: float | None
    lock_confirmed: bool | None


@dataclass(frozen=True)
class ContactReadinessInput:
    contacts: tuple[FingerContact, ...]
    friction_coefficient: float | None
    pressure_limit_Pa: float | None
    retention_force_required_N: float | None
    lock_receipt: LockReceipt | None
    geometry_authority: ContactAuthority
    material_authority: ContactAuthority
    collision_state: CollisionState = CollisionState.UNKNOWN_NOT_EVALUATED


@dataclass(frozen=True)
class HalfSineImpulseAudit:
    duration_s: float
    requested_impulse_Ns: float
    analytic_impulse_Ns: float
    peak_force_N: float
    normalization_error_Ns: float
    model_scope: str = (
        "ANALYTIC_HALF_SINE_EQUAL_IMPULSE_FIXTURE_NOT_CONTINUOUS_CONTACT_BACKEND"
    )


def _is_sha256(value: str | None) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdefABCDEF" for character in value)


def _finite(value: float | None) -> bool:
    return value is not None and math.isfinite(float(value))


def _as_vector3(values: Iterable[float]) -> tuple[float, float, float]:
    vector = tuple(float(value) for value in values)
    if len(vector) != 3:
        raise ValueError("contact normal must contain exactly three components")
    return vector  # type: ignore[return-value]


def validate_contact_normal(
    normal_xyz: Iterable[float],
    authority: ContactAuthority,
    *,
    unit_tolerance: float = 1.0e-9,
) -> ContactDecision:
    """Validate a released, finite unit contact normal without normalizing it.

    Silent normalization would hide a scale/unit defect, so a non-unit input is
    rejected rather than repaired.
    """

    try:
        normal = _as_vector3(normal_xyz)
    except (TypeError, ValueError, OverflowError):
        return ContactDecision(ContactState.FAIL, ("CONTACT_NORMAL_SHAPE_INVALID",))
    if not all(math.isfinite(value) for value in normal):
        return ContactDecision(ContactState.FAIL, ("CONTACT_NORMAL_NONFINITE",))
    norm = math.sqrt(math.fsum(value * value for value in normal))
    if norm <= 0.0:
        return ContactDecision(ContactState.FAIL, ("CONTACT_NORMAL_ZERO",))
    if abs(norm - 1.0) > unit_tolerance:
        return ContactDecision(ContactState.FAIL, ("CONTACT_NORMAL_NOT_UNIT",))
    if not authority.released:
        return ContactDecision(
            ContactState.UNKNOWN,
            (f"CONTACT_NORMAL_AUTHORITY_{authority.state}",),
        )
    return ContactDecision(ContactState.PASS, ("CONTACT_NORMAL_RELEASED_UNIT",))


def validate_contact_window(
    duration_s: float,
    authority: ContactAuthority,
) -> ContactDecision:
    if not math.isfinite(float(duration_s)) or float(duration_s) <= 0.0:
        return ContactDecision(ContactState.FAIL, ("CONTACT_WINDOW_DURATION_INVALID",))
    if not authority.released:
        return ContactDecision(
            ContactState.UNKNOWN,
            (f"CONTACT_WINDOW_AUTHORITY_{authority.state}",),
        )
    return ContactDecision(ContactState.PASS, ("CONTACT_WINDOW_RELEASED",))


def half_sine_equal_impulse_fixture(
    requested_impulse_Ns: float,
    duration_s: float,
) -> HalfSineImpulseAudit:
    """Return the exact audit for F(t)=F_peak sin(pi*t/Tc), 0<=t<=Tc."""

    impulse = float(requested_impulse_Ns)
    duration = float(duration_s)
    if not math.isfinite(impulse):
        raise ValueError("requested impulse must be finite")
    if not math.isfinite(duration) or duration <= 0.0:
        raise ValueError("contact-window duration must be finite and positive")
    peak_force = impulse * math.pi / (2.0 * duration)
    analytic_impulse = 2.0 * peak_force * duration / math.pi
    return HalfSineImpulseAudit(
        duration_s=duration,
        requested_impulse_Ns=impulse,
        analytic_impulse_Ns=analytic_impulse,
        peak_force_N=peak_force,
        normalization_error_Ns=analytic_impulse - impulse,
    )


def sampled_half_sine_impulse(
    requested_impulse_Ns: float,
    duration_s: float,
    *,
    intervals: int = 1000,
) -> float:
    """Numerically integrate the analytic fixture with the trapezoidal rule."""

    audit = half_sine_equal_impulse_fixture(requested_impulse_Ns, duration_s)
    if not isinstance(intervals, int) or intervals < 2:
        raise ValueError("intervals must be an integer >= 2")
    dt = audit.duration_s / intervals
    values = [
        audit.peak_force_N * math.sin(math.pi * index / intervals)
        for index in range(intervals + 1)
    ]
    return dt * (
        0.5 * values[0] + math.fsum(values[1:-1]) + 0.5 * values[-1]
    )


def _contact_reason_codes(data: ContactReadinessInput) -> list[str]:
    reasons: list[str] = []
    if data.collision_state is CollisionState.UNKNOWN_NOT_EVALUATED:
        reasons.append("COLLISION_UNKNOWN_NOT_EVALUATED")
    elif data.collision_state is CollisionState.COLLISION_DETECTED:
        reasons.append("COLLISION_DETECTED")

    if not data.geometry_authority.released:
        reasons.append(f"CONTACT_GEOMETRY_AUTHORITY_{data.geometry_authority.state}")
    if not data.material_authority.released:
        reasons.append(f"CONTACT_MATERIAL_AUTHORITY_{data.material_authority.state}")

    if len(data.contacts) != 2 or len({item.finger_id for item in data.contacts}) != 2:
        reasons.append("DUAL_FINGER_NAMED_MANIFOLD_ABSENT")
    for contact in data.contacts:
        prefix = contact.finger_id.upper() if contact.finger_id else "UNNAMED_FINGER"
        if not contact.finger_id:
            reasons.append("UNNAMED_FINGER_CONTACT")
        if not _finite(contact.normal_force_N):
            reasons.append(f"{prefix}_NORMAL_FORCE_UNKNOWN")
        elif float(contact.normal_force_N) < 0.0:
            reasons.append(f"{prefix}_NORMAL_FORCE_NEGATIVE")
        if not _finite(contact.tangential_force_N):
            reasons.append(f"{prefix}_TANGENTIAL_FORCE_UNKNOWN")
        if not _finite(contact.pressure_Pa):
            reasons.append(f"{prefix}_PRESSURE_UNKNOWN")

    if not _finite(data.friction_coefficient) or float(data.friction_coefficient) < 0.0:
        reasons.append("FRICTION_COEFFICIENT_UNKNOWN_OR_INVALID")
    if not _finite(data.pressure_limit_Pa) or float(data.pressure_limit_Pa) <= 0.0:
        reasons.append("PRESSURE_LIMIT_UNKNOWN_OR_INVALID")
    if not _finite(data.retention_force_required_N) or float(
        data.retention_force_required_N
    ) < 0.0:
        reasons.append("RETENTION_REQUIREMENT_UNKNOWN_OR_INVALID")

    if data.lock_receipt is None:
        reasons.append("LOCK_RECEIPT_ABSENT")
    else:
        receipt = data.lock_receipt
        if not _is_sha256(receipt.receipt_sha256):
            reasons.append("LOCK_RECEIPT_HASH_INVALID")
        if receipt.lock_confirmed is not True:
            reasons.append("LOCK_NOT_CONFIRMED")
        if (
            not _finite(receipt.age_s)
            or not _finite(receipt.maximum_age_s)
            or float(receipt.age_s) < 0.0
            or float(receipt.maximum_age_s) <= 0.0
            or float(receipt.age_s) > float(receipt.maximum_age_s)
        ):
            reasons.append("LOCK_RECEIPT_STALE_OR_TIME_INVALID")

    if reasons:
        return reasons

    mu = float(data.friction_coefficient)
    pressure_limit = float(data.pressure_limit_Pa)
    retention_required = float(data.retention_force_required_N)
    total_normal_force = 0.0
    for contact in data.contacts:
        normal = float(contact.normal_force_N)
        tangent = abs(float(contact.tangential_force_N))
        pressure = float(contact.pressure_Pa)
        total_normal_force += normal
        if tangent > mu * normal:
            reasons.append(f"{contact.finger_id.upper()}_FRICTION_CONE_VIOLATION")
        if pressure > pressure_limit:
            reasons.append(f"{contact.finger_id.upper()}_PRESSURE_LIMIT_EXCEEDED")
    if total_normal_force < retention_required:
        reasons.append("RETENTION_FORCE_MARGIN_NEGATIVE")
    return reasons


def evaluate_contact_readiness(data: ContactReadinessInput) -> ContactDecision:
    reasons = _contact_reason_codes(data)
    if not reasons:
        return ContactDecision(ContactState.PASS, ("CONTACT_PREFLIGHT_LOCAL_PASS",))
    unknown_tokens = (
        "UNKNOWN",
        "ABSENT",
        "AUTHORITY_",
        "NOT_EVALUATED",
        "NOT_CONFIRMED",
        "STALE",
        "INVALID",
    )
    state = (
        ContactState.UNKNOWN
        if any(any(token in reason for token in unknown_tokens) for reason in reasons)
        else ContactState.FAIL
    )
    return ContactDecision(state, tuple(dict.fromkeys(reasons)))


def contact_release_allowed(
    local_decision: ContactDecision,
    *,
    system_binding_passed: bool,
    runtime_gate_passed: bool,
    dynamics_gate_passed: bool,
) -> bool:
    """Exact-true ALL_OF join; local preflight alone can never release contact."""

    return all(
        value is True
        for value in (
            local_decision.passed,
            system_binding_passed,
            runtime_gate_passed,
            dynamics_gate_passed,
        )
    )


__all__ = [
    "CollisionState",
    "ContactAuthority",
    "ContactDecision",
    "ContactReadinessInput",
    "ContactState",
    "FingerContact",
    "HalfSineImpulseAudit",
    "LockReceipt",
    "contact_release_allowed",
    "evaluate_contact_readiness",
    "half_sine_equal_impulse_fixture",
    "sampled_half_sine_impulse",
    "validate_contact_normal",
    "validate_contact_window",
]
