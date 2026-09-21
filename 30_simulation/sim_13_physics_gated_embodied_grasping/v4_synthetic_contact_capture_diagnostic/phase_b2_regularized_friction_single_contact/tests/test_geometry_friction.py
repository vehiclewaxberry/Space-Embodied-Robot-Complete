from __future__ import annotations

import numpy as np

from b2_contact import evaluate_friction_contact
from sim13_v4a.full_floating import ServiceState, TargetState


def _state_at(history, index):
    return (
        ServiceState(
            history.service_base_position_inertial_m[index],
            history.service_base_quaternion_body_to_inertial_wxyz[index],
            history.service_joint_coordinates_mixed[index],
            history.service_nu_s_mixed[index],
        ),
        TargetState(
            history.target_position_inertial_m[index],
            history.target_quaternion_body_to_inertial_wxyz[index],
            history.target_twist_inertial_mixed[index],
        ),
    )


def test_action_reaction_and_tangent_orthogonality(friction_bundle):
    history = friction_bundle[-1]["rk4_reference"]
    assert np.max(np.linalg.norm(history.service_force_inertial_n + history.target_force_inertial_n, axis=1)) <= 1.0e-13
    dot = np.einsum("ij,ij->i", history.tangential_force_service_inertial_n, history.normal_target_to_pad_inertial)
    assert np.max(np.abs(dot)) <= 1.0e-13


def test_regularized_force_stays_inside_coulomb_bound(friction_bundle):
    config = friction_bundle[3]
    history = friction_bundle[-1]["rk4_reference"]
    tangent = np.linalg.norm(history.tangential_force_service_inertial_n, axis=1)
    assert np.max(tangent - config.friction_coefficient * history.normal_force_magnitude_n) <= 1.0e-13
    assert np.max(tangent) > 0.1


def test_friction_power_never_injects_energy(friction_bundle):
    history = friction_bundle[-1]["rk4_reference"]
    power = np.einsum("ij,ij->i", history.tangential_force_service_inertial_n, history.relative_tangential_velocity_inertial_m_s)
    assert np.max(power) <= 1.0e-14
    assert np.min(power) < -1.0e-4
    assert np.min(history.friction_dissipation_rate_w) >= 0.0


def test_common_point_wrench_shift_is_exact(friction_bundle):
    history = friction_bundle[-1]["rk4_reference"]
    left = np.cross(history.pad_point_inertial_m, history.service_force_inertial_n) + history.service_shift_torque_inertial_n_m
    right = np.cross(history.common_contact_point_inertial_m, history.service_force_inertial_n)
    assert np.max(np.linalg.norm(left - right, axis=1)) <= 1.0e-13
    assert np.max(np.linalg.norm(history.service_shift_torque_inertial_n_m, axis=1)) > 1.0e-7


def test_separated_state_has_no_normal_or_tangential_force(friction_bundle):
    history = friction_bundle[-1]["rk4_reference"]
    separated = history.penetration_m <= 0.0
    assert np.max(np.linalg.norm(history.service_force_inertial_n[separated], axis=1)) == 0.0
    assert np.max(np.linalg.norm(history.tangential_force_service_inertial_n[separated], axis=1)) == 0.0


def test_zero_relative_tangent_produces_zero_friction(friction_bundle):
    model, _, _, config, histories = friction_bundle
    history = histories["rk4_reference"]
    index = int(np.argmax(history.penetration_m))
    service, target = _state_at(history, index)
    first = evaluate_friction_contact(model, service, target, config)
    target_zero = TargetState(
        target.position_inertial_m,
        target.quaternion_body_to_inertial_wxyz,
        np.concatenate((first.service_common_point_velocity_inertial_m_s, np.zeros(3))),
    )
    second = evaluate_friction_contact(model, service, target_zero, config)
    assert second.relative_tangential_speed_m_s <= 1.0e-14
    assert np.linalg.norm(second.tangential_force_service_inertial_n) <= 1.0e-12
