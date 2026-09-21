from __future__ import annotations

import numpy as np

from b1_contact import ContactConfig, deterministic_contact_scenario, evaluate_contact
from sim13_v4a.full_floating import TargetState


def test_signed_gap_normal_and_common_point_follow_sphere_contract():
    model, service, target, config = deterministic_contact_scenario()
    observation = evaluate_contact(model, service, target, config)
    radial = observation.pad_point_inertial_m - target.position_inertial_m
    assert abs(observation.gap_m - (np.linalg.norm(radial) - config.sphere_radius_m)) < 1.0e-14
    assert np.linalg.norm(observation.normal_target_to_pad_inertial - radial / np.linalg.norm(radial)) < 1.0e-14
    assert np.linalg.norm(observation.common_contact_point_inertial_m - (target.position_inertial_m + config.sphere_radius_m * observation.normal_target_to_pad_inertial)) < 1.0e-14


def test_separated_contact_has_zero_force_and_no_tensile_term():
    model, service, target, config = deterministic_contact_scenario()
    observation = evaluate_contact(model, service, target, config)
    assert observation.gap_m > 0.0
    assert observation.penetration_m == 0.0
    assert observation.normal_force_magnitude_n == 0.0
    assert np.array_equal(observation.service_force_inertial_n, np.zeros(3))


def _penetrating_target(depth_m: float):
    model, service, target, config = deterministic_contact_scenario()
    pad, _, _ = model.point_position_and_jacobian(service, config.pad_link_index, config.pad_point_local_m)
    normal = np.array((0.91, -0.29, 0.29), dtype=float)
    normal /= np.linalg.norm(normal)
    position = pad - (config.sphere_radius_m - depth_m) * normal
    penetrating = TargetState(position, target.quaternion_body_to_inertial_wxyz, target.twist_inertial_mixed)
    return model, service, penetrating, config


def test_penetrating_force_law_has_elastic_and_closing_damping_only():
    model, service, target, config = _penetrating_target(2.0e-4)
    observation = evaluate_contact(model, service, target, config)
    expected = config.normal_stiffness_n_m * observation.penetration_m + config.normal_damping_n_s_m * max(-observation.relative_normal_speed_m_s, 0.0)
    assert abs(observation.normal_force_magnitude_n - expected) < 1.0e-12
    assert observation.normal_force_magnitude_n >= 0.0


def test_action_reaction_and_full_generalized_service_effort_are_exact():
    model, service, target, config = _penetrating_target(2.0e-4)
    observation = evaluate_contact(model, service, target, config)
    _, jacobian, _ = model.point_position_and_jacobian(service, config.pad_link_index, config.pad_point_local_m)
    assert np.linalg.norm(observation.service_force_inertial_n + observation.target_force_inertial_n) == 0.0
    assert np.linalg.norm(observation.service_generalized_contact_effort_mixed - jacobian.T @ observation.service_force_inertial_n) < 1.0e-14
    assert np.linalg.norm(observation.service_generalized_contact_effort_mixed[:6]) > 0.0
    assert np.linalg.norm(observation.service_generalized_contact_effort_mixed[6:]) > 0.0


def test_common_point_and_pad_offset_create_no_spurious_normal_moment():
    model, service, target, config = _penetrating_target(2.0e-4)
    observation = evaluate_contact(model, service, target, config)
    offset_moment = np.cross(observation.pad_point_inertial_m - observation.common_contact_point_inertial_m, observation.service_force_inertial_n)
    assert np.linalg.norm(offset_moment) < 1.0e-12
    assert np.linalg.norm(observation.target_torque_about_com_inertial_n_m) < 1.0e-12
