"""Frictionless rigid-body impulse diagnostic for the additive DG4 candidate.

This module intentionally has no attachment or persistent-contact plant.  It computes
one mathematically bounded normal impulse and returns two separate post-impact bodies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


PRECONTACT = "PRECONTACT"
BOUNDED_CONTACT_DIAGNOSTIC = "BOUNDED_CONTACT_DIAGNOSTIC"
POST_IMPACT_DIAGNOSTIC = "POST_IMPACT_DIAGNOSTIC"
ABORT_ONLY = "ABORT_ONLY"


class FailClosedError(RuntimeError):
    """Raised whenever a request falls outside the bounded diagnostic contract."""


@dataclass(frozen=True)
class Body:
    mass_kg: float
    inertia_kg_m2: np.ndarray
    position_m: np.ndarray
    linear_velocity_m_s: np.ndarray
    angular_velocity_rad_s: np.ndarray
    contact_lever_m: np.ndarray


def _vec3(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise FailClosedError(f"DG4_INVALID_VECTOR:{name}")
    return array


def _mat3(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (3, 3) or not np.all(np.isfinite(array)):
        raise FailClosedError(f"DG4_INVALID_MATRIX:{name}")
    if not np.allclose(array, array.T, rtol=0.0, atol=1e-15):
        raise FailClosedError(f"DG4_NONSYMMETRIC_INERTIA:{name}")
    if float(np.min(np.linalg.eigvalsh(array))) <= 0.0:
        raise FailClosedError(f"DG4_NONPOSITIVE_INERTIA:{name}")
    return array


def inertia_from_components(components: Any) -> np.ndarray:
    """Build [Ixx,Iyy,Izz,Ixy,Ixz,Iyz] symmetric inertia matrix."""

    values = np.asarray(components, dtype=float)
    if values.shape != (6,) or not np.all(np.isfinite(values)):
        raise FailClosedError("DG4_INVALID_INERTIA_COMPONENTS")
    ixx, iyy, izz, ixy, ixz, iyz = values
    return _mat3(
        [[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]],
        "component_inertia",
    )


def diagonal_inertia(diagonal: Any) -> np.ndarray:
    values = np.asarray(diagonal, dtype=float)
    if values.shape != (3,) or not np.all(np.isfinite(values)):
        raise FailClosedError("DG4_INVALID_DIAGONAL_INERTIA")
    return _mat3(np.diag(values), "diagonal_inertia")


def normalized(vector: Any, name: str) -> np.ndarray:
    value = _vec3(vector, name)
    norm = float(np.linalg.norm(value))
    if not np.isfinite(norm) or norm <= 0.0:
        raise FailClosedError(f"DG4_ZERO_AXIS:{name}")
    return value / norm


def validate_request(
    *,
    scope: str,
    requested_speed_m_s: float,
    hard_upper_bound_m_s: float,
    unknown_disposition: str,
    source_bindings_valid: bool,
) -> str:
    """Return bounded diagnostic eligibility or raise a fail-closed error."""

    if not source_bindings_valid:
        raise FailClosedError("DG4_SOURCE_HASH_DRIFT_ABORT_ONLY")
    if unknown_disposition != ABORT_ONLY:
        raise FailClosedError("DG4_UNKNOWN_POLICY_NOT_ABORT_ONLY")
    if scope != "BOUNDED_DESIGN_DIAGNOSTIC_ONLY":
        raise FailClosedError("DG4_SCOPE_NOT_PERMITTED")
    if not np.isfinite(requested_speed_m_s) or requested_speed_m_s < 0.0:
        raise FailClosedError("DG4_INVALID_CLOSING_SPEED")
    if not np.isfinite(hard_upper_bound_m_s) or hard_upper_bound_m_s <= 0.0:
        raise FailClosedError("DG4_INVALID_SPEED_BOUND")
    if requested_speed_m_s > hard_upper_bound_m_s:
        raise FailClosedError("DG4_SPEED_BOUND_EXCEEDED_ABORT_ONLY")
    return "ELIGIBLE_BOUNDED_DESIGN_DIAGNOSTIC"


def transition(state: str, event: str, *, eligible: bool) -> str:
    if not eligible:
        return ABORT_ONLY
    table = {
        (PRECONTACT, "VALIDATED_BOUNDED_DIAGNOSTIC_ENTRY"): BOUNDED_CONTACT_DIAGNOSTIC,
        (
            BOUNDED_CONTACT_DIAGNOSTIC,
            "CONSERVATIVE_INTERNAL_IMPULSE_SOLVED",
        ): POST_IMPACT_DIAGNOSTIC,
    }
    output = table.get((state, event))
    if output is None:
        raise FailClosedError(f"DG4_PROHIBITED_TRANSITION:{state}:{event}")
    return output


def contact_velocity(body: Body) -> np.ndarray:
    return body.linear_velocity_m_s + np.cross(
        body.angular_velocity_rad_s, body.contact_lever_m
    )


def kinetic_energy_j(body: Body) -> float:
    translational = 0.5 * body.mass_kg * float(
        body.linear_velocity_m_s @ body.linear_velocity_m_s
    )
    rotational = 0.5 * float(
        body.angular_velocity_rad_s
        @ body.inertia_kg_m2
        @ body.angular_velocity_rad_s
    )
    return translational + rotational


def linear_momentum_ns(body: Body) -> np.ndarray:
    return body.mass_kg * body.linear_velocity_m_s


def angular_momentum_about_origin_nms(body: Body) -> np.ndarray:
    orbital = np.cross(body.position_m, linear_momentum_ns(body))
    spin = body.inertia_kg_m2 @ body.angular_velocity_rad_s
    return orbital + spin


def _rotational_effective_inverse_mass(
    inertia: np.ndarray, lever: np.ndarray, normal: np.ndarray
) -> float:
    angular_response = np.linalg.solve(inertia, np.cross(lever, normal))
    return float(normal @ np.cross(angular_response, lever))


def solve_case(
    *,
    case_id: str,
    target_id: str,
    service_mass_kg: float,
    service_inertia_kg_m2: Any,
    target_mass_kg: float,
    target_inertia_kg_m2: Any,
    service_contact_lever_m: Any,
    target_contact_lever_m: Any,
    contact_normal_axis: Any,
    closing_speed_m_s: float,
    hard_upper_bound_m_s: float,
    restitution: float,
    contact_window_s: float,
    target_tumble_rate_rad_s: float,
    target_tumble_axis: Any,
    request_scope: str = "BOUNDED_DESIGN_DIAGNOSTIC_ONLY",
    unknown_disposition: str = ABORT_ONLY,
    source_bindings_valid: bool = True,
) -> dict[str, Any]:
    """Solve one bounded impulse case and return deterministic raw diagnostics."""

    validate_request(
        scope=request_scope,
        requested_speed_m_s=float(closing_speed_m_s),
        hard_upper_bound_m_s=float(hard_upper_bound_m_s),
        unknown_disposition=unknown_disposition,
        source_bindings_valid=source_bindings_valid,
    )
    if not np.isfinite(service_mass_kg) or service_mass_kg <= 0.0:
        raise FailClosedError("DG4_INVALID_SERVICE_MASS")
    if not np.isfinite(target_mass_kg) or target_mass_kg <= 0.0:
        raise FailClosedError("DG4_INVALID_TARGET_MASS")
    if not np.isfinite(restitution) or not 0.0 <= restitution <= 1.0:
        raise FailClosedError("DG4_RESTITUTION_OUT_OF_MATHEMATICAL_RANGE")
    if not np.isfinite(contact_window_s) or contact_window_s <= 0.0:
        raise FailClosedError("DG4_INVALID_CONTACT_WINDOW")
    if not np.isfinite(target_tumble_rate_rad_s) or target_tumble_rate_rad_s < 0.0:
        raise FailClosedError("DG4_INVALID_TUMBLE_RATE")

    inertia_s = _mat3(service_inertia_kg_m2, "service_inertia")
    inertia_t = _mat3(target_inertia_kg_m2, "target_inertia")
    lever_s = _vec3(service_contact_lever_m, "service_contact_lever")
    lever_t = _vec3(target_contact_lever_m, "target_contact_lever")
    normal = normalized(contact_normal_axis, "diagnostic_contact_normal")
    tumble_axis = normalized(target_tumble_axis, "target_tumble_axis")

    # Both mathematical contact points coincide at the inertial origin.  This is a
    # conservation fixture only and does not instantiate a physical contact patch.
    position_s = -lever_s
    position_t = -lever_t
    omega_s = np.zeros(3, dtype=float)
    omega_t = tumble_axis * float(target_tumble_rate_rad_s)
    velocity_s = np.zeros(3, dtype=float)
    velocity_t = -float(closing_speed_m_s) * normal - np.cross(omega_t, lever_t)

    pre_s = Body(
        float(service_mass_kg),
        inertia_s,
        position_s,
        velocity_s,
        omega_s,
        lever_s,
    )
    pre_t = Body(
        float(target_mass_kg),
        inertia_t,
        position_t,
        velocity_t,
        omega_t,
        lever_t,
    )
    contact_coincidence_residual = float(
        np.linalg.norm(
            (pre_s.position_m + pre_s.contact_lever_m)
            - (pre_t.position_m + pre_t.contact_lever_m)
        )
    )
    relative_pre = contact_velocity(pre_t) - contact_velocity(pre_s)
    relative_normal_pre = float(normal @ relative_pre)
    if relative_normal_pre >= 0.0:
        raise FailClosedError("DG4_NOT_CLOSING")

    effective_inverse_mass = (
        1.0 / pre_s.mass_kg
        + 1.0 / pre_t.mass_kg
        + _rotational_effective_inverse_mass(inertia_s, lever_s, normal)
        + _rotational_effective_inverse_mass(inertia_t, lever_t, normal)
    )
    if not np.isfinite(effective_inverse_mass) or effective_inverse_mass <= 0.0:
        raise FailClosedError("DG4_NONPOSITIVE_EFFECTIVE_INVERSE_MASS")
    effective_mass = 1.0 / effective_inverse_mass
    impulse_magnitude = -(
        1.0 + float(restitution)
    ) * relative_normal_pre / effective_inverse_mass
    if not np.isfinite(impulse_magnitude) or impulse_magnitude <= 0.0:
        raise FailClosedError("DG4_NONPOSITIVE_IMPULSE")

    impulse_on_target = impulse_magnitude * normal
    impulse_on_service = -impulse_on_target
    post_velocity_s = pre_s.linear_velocity_m_s + impulse_on_service / pre_s.mass_kg
    post_velocity_t = pre_t.linear_velocity_m_s + impulse_on_target / pre_t.mass_kg
    post_omega_s = pre_s.angular_velocity_rad_s + np.linalg.solve(
        inertia_s, np.cross(lever_s, impulse_on_service)
    )
    post_omega_t = pre_t.angular_velocity_rad_s + np.linalg.solve(
        inertia_t, np.cross(lever_t, impulse_on_target)
    )

    post_s = Body(
        pre_s.mass_kg,
        inertia_s,
        position_s,
        post_velocity_s,
        post_omega_s,
        lever_s,
    )
    post_t = Body(
        pre_t.mass_kg,
        inertia_t,
        position_t,
        post_velocity_t,
        post_omega_t,
        lever_t,
    )

    relative_post = contact_velocity(post_t) - contact_velocity(post_s)
    relative_normal_post = float(normal @ relative_post)
    restitution_residual = abs(
        relative_normal_post + float(restitution) * relative_normal_pre
    )

    linear_pre = linear_momentum_ns(pre_s) + linear_momentum_ns(pre_t)
    linear_post = linear_momentum_ns(post_s) + linear_momentum_ns(post_t)
    angular_pre = angular_momentum_about_origin_nms(
        pre_s
    ) + angular_momentum_about_origin_nms(pre_t)
    angular_post = angular_momentum_about_origin_nms(
        post_s
    ) + angular_momentum_about_origin_nms(post_t)
    linear_residual = float(np.linalg.norm(linear_post - linear_pre))
    angular_residual = float(np.linalg.norm(angular_post - angular_pre))
    impulse_pair_residual = float(
        np.linalg.norm(impulse_on_service + impulse_on_target)
    )

    spin_delta_s = inertia_s @ (post_omega_s - omega_s)
    spin_delta_t = inertia_t @ (post_omega_t - omega_t)
    service_spin_impulse_residual = float(
        np.linalg.norm(spin_delta_s - np.cross(lever_s, impulse_on_service))
    )
    target_spin_impulse_residual = float(
        np.linalg.norm(spin_delta_t - np.cross(lever_t, impulse_on_target))
    )

    energy_pre = kinetic_energy_j(pre_s) + kinetic_energy_j(pre_t)
    energy_post = kinetic_energy_j(post_s) + kinetic_energy_j(post_t)
    energy_loss = energy_pre - energy_post
    analytic_energy_loss = 0.5 * effective_mass * (
        1.0 - float(restitution) ** 2
    ) * relative_normal_pre**2
    energy_identity_residual = abs(energy_loss - analytic_energy_loss)
    equivalent_half_sine_peak_force = (
        np.pi * impulse_magnitude / (2.0 * float(contact_window_s))
    )

    state = PRECONTACT
    state_sequence = [state]
    state = transition(
        state, "VALIDATED_BOUNDED_DIAGNOSTIC_ENTRY", eligible=True
    )
    state_sequence.append(state)
    state = transition(
        state, "CONSERVATIVE_INTERNAL_IMPULSE_SOLVED", eligible=True
    )
    state_sequence.append(state)

    return {
        "case_id": case_id,
        "target_id": target_id,
        "state_sequence": state_sequence,
        "terminal_state": state,
        "body_count_pre": 2,
        "body_count_post": 2,
        "attachment_created": False,
        "persistent_contact_created": False,
        "physical_contact_claimed": False,
        "contact_coincidence_residual_m": contact_coincidence_residual,
        "contact_normal_axis": normal.tolist(),
        "closing_speed_m_s": float(closing_speed_m_s),
        "hard_upper_bound_m_s": float(hard_upper_bound_m_s),
        "restitution": float(restitution),
        "contact_window_s": float(contact_window_s),
        "relative_normal_pre_m_s": relative_normal_pre,
        "relative_normal_post_m_s": relative_normal_post,
        "restitution_residual_m_s": restitution_residual,
        "effective_inverse_mass_per_kg": effective_inverse_mass,
        "effective_mass_kg": effective_mass,
        "impulse_magnitude_N_s": impulse_magnitude,
        "impulse_on_service_N_s": impulse_on_service.tolist(),
        "impulse_on_target_N_s": impulse_on_target.tolist(),
        "impulse_pair_residual_N_s": impulse_pair_residual,
        "equivalent_half_sine_peak_force_N": float(
            equivalent_half_sine_peak_force
        ),
        "linear_momentum_pre_N_s": linear_pre.tolist(),
        "linear_momentum_post_N_s": linear_post.tolist(),
        "linear_momentum_residual_N_s": linear_residual,
        "angular_momentum_pre_N_m_s": angular_pre.tolist(),
        "angular_momentum_post_N_m_s": angular_post.tolist(),
        "angular_momentum_residual_N_m_s": angular_residual,
        "service_spin_angular_impulse_residual_N_m_s": service_spin_impulse_residual,
        "target_spin_angular_impulse_residual_N_m_s": target_spin_impulse_residual,
        "kinetic_energy_pre_J": energy_pre,
        "kinetic_energy_post_J": energy_post,
        "kinetic_energy_loss_J": energy_loss,
        "analytic_energy_loss_J": analytic_energy_loss,
        "energy_identity_residual_J": energy_identity_residual,
        "service_post_linear_velocity_m_s": post_velocity_s.tolist(),
        "service_post_angular_velocity_rad_s": post_omega_s.tolist(),
        "target_post_linear_velocity_m_s": post_velocity_t.tolist(),
        "target_post_angular_velocity_rad_s": post_omega_t.tolist(),
    }

