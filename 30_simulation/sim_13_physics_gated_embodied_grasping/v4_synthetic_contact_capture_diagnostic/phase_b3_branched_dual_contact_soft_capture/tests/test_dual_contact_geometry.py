from __future__ import annotations

import numpy as np


def _skew(vector: np.ndarray) -> np.ndarray:
    x, y, z = vector
    return np.array(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def _reference(dual_bundle):
    return dual_bundle[4]["rk4_reference"], dual_bundle[5]["rk4_reference"]


def test_each_finger_gap_normal_and_common_point_follow_its_own_sphere_geometry(dual_bundle):
    _, _, _, config, _, _ = dual_bundle
    history, _ = _reference(dual_bundle)
    for data in (history.left, history.right):
        radial = data.pad_point_inertial_m - history.target_position_inertial_m
        distance = np.linalg.norm(radial, axis=1)
        expected_normal = radial / distance[:, None]
        expected_common = history.target_position_inertial_m + config.sphere_radius_m * expected_normal
        assert np.max(np.abs(data.gap_m - (distance - config.sphere_radius_m))) <= 2.0e-14
        assert np.max(np.abs(data.penetration_m - np.maximum(-data.gap_m, 0.0))) <= 2.0e-14
        assert np.max(np.linalg.norm(data.normal_target_to_pad_inertial - expected_normal, axis=1)) <= 2.0e-14
        assert np.max(np.linalg.norm(data.common_contact_point_inertial_m - expected_common, axis=1)) <= 2.0e-14


def test_action_reaction_is_exact_per_finger_and_total_target_force_is_a_sum(dual_bundle):
    history, _ = _reference(dual_bundle)
    for data in (history.left, history.right):
        assert np.max(np.linalg.norm(data.service_force_inertial_n + data.target_force_inertial_n, axis=1)) <= 1.0e-13
    service_sum = history.left.service_force_inertial_n + history.right.service_force_inertial_n
    target_sum = history.left.target_force_inertial_n + history.right.target_force_inertial_n
    assert np.max(np.linalg.norm(service_sum + target_sum, axis=1)) <= 1.0e-13
    assert np.max(np.linalg.norm(service_sum, axis=1)) > 0.0


def test_regularized_friction_is_tangent_bounded_and_never_injective(dual_bundle):
    _, _, _, config, _, _ = dual_bundle
    history, _ = _reference(dual_bundle)
    active_peak = 0.0
    for data in (history.left, history.right):
        tangent_norm = np.linalg.norm(data.tangential_force_service_inertial_n, axis=1)
        orthogonality = np.einsum(
            "ij,ij->i",
            data.tangential_force_service_inertial_n,
            data.normal_target_to_pad_inertial,
        )
        friction_power = np.einsum(
            "ij,ij->i",
            data.tangential_force_service_inertial_n,
            data.relative_tangential_velocity_inertial_m_s,
        )
        assert np.max(np.abs(orthogonality)) <= 1.0e-13
        assert np.max(tangent_norm - config.friction_coefficient * data.normal_force_magnitude_n) <= 1.0e-13
        assert np.max(friction_power) <= 1.0e-14
        assert np.min(data.friction_dissipation_rate_w) >= 0.0
        active_peak = max(active_peak, float(np.max(tangent_norm)))
    assert active_peak > 1.0e-3


def test_common_point_wrench_shift_and_target_torque_are_exact_for_each_side(dual_bundle):
    history, _ = _reference(dual_bundle)
    for data in (history.left, history.right):
        service_about_origin = (
            np.cross(data.pad_point_inertial_m, data.service_force_inertial_n)
            + data.service_shift_torque_inertial_n_m
        )
        service_common = np.cross(
            data.common_contact_point_inertial_m,
            data.service_force_inertial_n,
        )
        target_expected = np.cross(
            data.common_contact_point_inertial_m - history.target_position_inertial_m,
            data.target_force_inertial_n,
        )
        assert np.max(np.linalg.norm(service_about_origin - service_common, axis=1)) <= 1.0e-13
        assert np.max(np.linalg.norm(data.target_torque_about_com_inertial_n_m - target_expected, axis=1)) <= 1.0e-13


def test_separated_samples_have_zero_force_without_tension(dual_bundle):
    history, _ = _reference(dual_bundle)
    for data in (history.left, history.right):
        separated = data.penetration_m <= 0.0
        assert np.any(separated)
        assert np.max(data.normal_force_magnitude_n[separated]) == 0.0
        assert np.max(np.linalg.norm(data.service_force_inertial_n[separated], axis=1)) == 0.0
        assert np.max(np.linalg.norm(data.tangential_force_service_inertial_n[separated], axis=1)) == 0.0
        assert np.min(data.normal_force_magnitude_n) >= 0.0


def test_branches_remain_separate_and_two_point_grasp_map_has_rank_five(dual_bundle):
    history, summary = _reference(dual_bundle)
    assert np.max(np.abs(history.left.service_generalized_contact_effort_mixed[:, 13])) == 0.0
    assert np.max(np.abs(history.right.service_generalized_contact_effort_mixed[:, 12])) == 0.0
    qualifying = [
        int(item["index"])
        for item in history.soft_capture_criteria_log
        if item["soft_capture_transient_qualifies"]
    ]
    assert qualifying
    index = qualifying[0]
    left_point = history.left.common_contact_point_inertial_m[index]
    right_point = history.right.common_contact_point_inertial_m[index]
    target_origin = history.target_position_inertial_m[index]
    assert np.linalg.norm(left_point - right_point) > 2.0 * 0.9 * 0.040
    grasp_map = np.block(
        [
            [np.eye(3), np.eye(3)],
            [_skew(left_point - target_origin), _skew(right_point - target_origin)],
        ]
    )
    left_vectors, singular_values, _ = np.linalg.svd(grasp_map)
    tolerance = 1.0e-10 * max(float(singular_values[0]), 1.0)
    rank = int(np.count_nonzero(singular_values > tolerance))
    reciprocal = left_vectors[:, -1]
    contact_line = right_point - left_point
    contact_line /= np.linalg.norm(contact_line)
    angular = reciprocal[3:]
    alignment = abs(float(angular @ contact_line)) / np.linalg.norm(angular)
    assert rank == 5
    assert np.linalg.norm(grasp_map.T @ reciprocal) <= 1.0e-12
    assert alignment >= 1.0 - 1.0e-10
    assert summary["grasp_map"]["selected_sample"]["numerical_rank"] == rank
    assert summary["grasp_map"]["selected_sample"]["rank_deficiency"] == 1
    assert summary["grasp_map"]["all_evaluated_samples_rank_five"] is True
    assert summary["grasp_map"]["full_6d_wrench_span"] is False
    assert summary["grasp_map"]["full_6d_force_closure"] is False
    topology = history.topology_diagnostic
    assert topology == summary["topology"]
    assert topology["model_python_class"].endswith("BranchedGripperServiceModel")
    assert topology["left_own_P_jacobian_fd_max_error"] <= 2.0e-8
    assert topology["right_own_P_jacobian_fd_max_error"] <= 2.0e-8
    assert topology["left_cross_right_P_fd_norm"] <= 1.0e-12
    assert topology["right_cross_left_P_fd_norm"] <= 1.0e-12
