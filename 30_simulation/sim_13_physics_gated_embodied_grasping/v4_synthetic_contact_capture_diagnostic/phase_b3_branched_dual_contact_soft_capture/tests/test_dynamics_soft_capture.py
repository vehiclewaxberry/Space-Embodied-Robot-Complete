from __future__ import annotations

import numpy as np

from sim13_v4a.full_floating import quaternion_geodesic


REQUIRED_ORDER = (
    "PREGRASP_SEPARATED",
    "BILATERAL_APPROACH",
    "DUAL_CONTACT",
    "SOFT_CAPTURE_TRANSIENT_CANDIDATE",
    "BILATERAL_RELEASE",
)
ALLOWED_STATES = {
    *REQUIRED_ORDER,
    "LEFT_ONLY_CONTACT",
    "RIGHT_ONLY_CONTACT",
}


def _ordered_subsequence(sequence, required):
    cursor = 0
    for state in sequence:
        if cursor < len(required) and state == required[cursor]:
            cursor += 1
    return cursor == len(required)


def _terminal_difference(left, right):
    return {
        "service_base_position_m": float(np.linalg.norm(left.service_base_position_inertial_m[-1] - right.service_base_position_inertial_m[-1])),
        "service_base_quaternion_rad": quaternion_geodesic(left.service_base_quaternion_body_to_inertial_wxyz[-1], right.service_base_quaternion_body_to_inertial_wxyz[-1]),
        "service_q_R_rad": float(np.max(np.abs(left.service_joint_coordinates_mixed[-1, :6] - right.service_joint_coordinates_mixed[-1, :6]))),
        "service_q_P_m": float(np.max(np.abs(left.service_joint_coordinates_mixed[-1, 6:] - right.service_joint_coordinates_mixed[-1, 6:]))),
        "service_v_base_m_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, :3] - right.service_nu_s_mixed[-1, :3]))),
        "service_omega_base_rad_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, 3:6] - right.service_nu_s_mixed[-1, 3:6]))),
        "service_qdot_R_rad_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, 6:12] - right.service_nu_s_mixed[-1, 6:12]))),
        "service_qdot_P_m_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, 12:] - right.service_nu_s_mixed[-1, 12:]))),
        "target_position_m": float(np.linalg.norm(left.target_position_inertial_m[-1] - right.target_position_inertial_m[-1])),
        "target_quaternion_rad": quaternion_geodesic(left.target_quaternion_body_to_inertial_wxyz[-1], right.target_quaternion_body_to_inertial_wxyz[-1]),
        "target_velocity_m_s": float(np.max(np.abs(left.target_twist_inertial_mixed[-1, :3] - right.target_twist_inertial_mixed[-1, :3]))),
        "target_omega_rad_s": float(np.max(np.abs(left.target_twist_inertial_mixed[-1, 3:] - right.target_twist_inertial_mixed[-1, 3:]))),
    }


def test_nominal_state_machine_reaches_transient_candidate_and_bilateral_release(dual_bundle):
    history = dual_bundle[4]["rk4_reference"]
    sequence = [item["to"] for item in history.transition_log]
    assert _ordered_subsequence(sequence, REQUIRED_ORDER)
    assert set(sequence) <= ALLOWED_STATES
    assert not history.aborted_safe
    assert history.abort_reasons == ()


def test_every_qualifying_sample_satisfies_all_soft_capture_predicates(dual_bundle):
    _, _, _, config, histories, _ = dual_bundle
    history = histories["rk4_reference"]
    qualifying = [item for item in history.soft_capture_criteria_log if item["soft_capture_transient_qualifies"]]
    assert qualifying
    for item in qualifying:
        assert item["left_contact"] and item["right_contact"]
        assert item["dual_contact_dwell_s"] >= config.dual_contact_dwell_s
        assert item["normals_dot"] <= config.normals_opposition_max_dot
        assert item["target_inside_corridor"]
        assert item["target_relative_center_speed_m_s"] <= config.soft_capture_max_relative_center_speed_m_s
        assert item["target_relative_omega_rad_s"] <= config.soft_capture_max_relative_omega_rad_s
        assert abs(item["left_relative_normal_speed_m_s"]) <= config.soft_capture_max_abs_contact_normal_speed_m_s
        assert abs(item["right_relative_normal_speed_m_s"]) <= config.soft_capture_max_abs_contact_normal_speed_m_s
        assert item["left_relative_tangential_speed_m_s"] <= config.soft_capture_max_contact_tangential_speed_m_s
        assert item["right_relative_tangential_speed_m_s"] <= config.soft_capture_max_contact_tangential_speed_m_s
        assert item["left_finger_rate_m_s"] <= config.soft_capture_max_finger_opening_speed_m_s
        assert item["right_finger_rate_m_s"] <= config.soft_capture_max_finger_opening_speed_m_s
        assert item["left_normal_force_n"] >= config.soft_capture_min_normal_force_n
        assert item["right_normal_force_n"] >= config.soft_capture_min_normal_force_n
        assert item["all_ledgers_closed"] is True


def test_single_side_contact_never_qualifies_as_soft_capture(dual_bundle):
    history = dual_bundle[4]["rk4_reference"]
    single_side = [
        item
        for item in history.soft_capture_criteria_log
        if bool(item["left_contact"]) ^ bool(item["right_contact"])
    ]
    assert single_side
    assert all(not item["soft_capture_transient_qualifies"] for item in single_side)
    single_side_indices = {int(item["index"]) for item in single_side}
    assert all(
        history.state_label[index] in {"LEFT_ONLY_CONTACT", "RIGHT_ONLY_CONTACT"}
        for index in single_side_indices
    )


def test_candidate_is_latched_until_partial_or_bilateral_release_without_lock_claim(dual_bundle):
    history = dual_bundle[4]["rk4_reference"]
    summary = dual_bundle[5]["rk4_reference"]
    transitions = [item["to"] for item in history.transition_log]
    candidate_index = transitions.index("SOFT_CAPTURE_TRANSIENT_CANDIDATE")
    release_index = transitions.index("BILATERAL_RELEASE")
    assert release_index > candidate_index
    assert "DUAL_CONTACT" not in transitions[candidate_index + 1 :]
    assert history.state_label[-1] == "BILATERAL_RELEASE"
    assert not ({"LOCKED", "GRASP_SUCCESS"} & set(history.state_label))
    assert summary["state_machine"]["locked_state_present"] is False
    assert summary["state_machine"]["grasp_success_state_present"] is False
    assert not any(summary["boundaries"].values())


def test_summed_per_contact_linear_and_angular_impulse_ledgers_close(dual_bundle):
    history = dual_bundle[4]["rk4_reference"]
    summary = dual_bundle[5]["rk4_reference"]
    left_impulse = history.left.cumulative_service_impulse_n_s
    right_impulse = history.right.cumulative_service_impulse_n_s
    left_angular = history.left.cumulative_service_angular_impulse_n_m_s
    right_angular = history.right.cumulative_service_angular_impulse_n_m_s
    assert np.linalg.norm(left_impulse[-1]) > 0.0
    assert np.linalg.norm(right_impulse[-1]) > 0.0
    assert np.linalg.norm(left_angular[-1]) > 0.0
    assert np.linalg.norm(right_angular[-1]) > 0.0
    delta_service_p = history.service_linear_momentum_n_s - history.service_linear_momentum_n_s[0]
    delta_target_p = history.target_linear_momentum_n_s - history.target_linear_momentum_n_s[0]
    delta_service_h = history.service_angular_momentum_about_origin_n_m_s - history.service_angular_momentum_about_origin_n_m_s[0]
    delta_target_h = history.target_angular_momentum_about_origin_n_m_s - history.target_angular_momentum_about_origin_n_m_s[0]
    assert np.max(np.linalg.norm(delta_service_p - left_impulse - right_impulse, axis=1)) <= 1.0e-10
    assert np.max(np.linalg.norm(delta_target_p + left_impulse + right_impulse, axis=1)) <= 1.0e-10
    assert np.max(np.linalg.norm(delta_service_h - left_angular - right_angular, axis=1)) <= 1.0e-10
    assert np.max(np.linalg.norm(delta_target_h + left_angular + right_angular, axis=1)) <= 1.0e-10
    assert summary["linear_momentum_n_s"]["total_max_drift_n_s"] <= 1.0e-10
    assert summary["angular_momentum_n_m_s"]["total_max_drift_n_m_s"] <= 1.0e-10


def test_energy_closes_with_four_separate_dissipation_channels(dual_bundle):
    history = dual_bundle[4]["rk4_reference"]
    summary = dual_bundle[5]["rk4_reference"]
    channels = (
        history.left.cumulative_normal_dissipation_j,
        history.left.cumulative_friction_dissipation_j,
        history.right.cumulative_normal_dissipation_j,
        history.right.cumulative_friction_dissipation_j,
    )
    assert all(channel[-1] > 0.0 for channel in channels)
    assert all(np.min(np.diff(channel)) >= -1.0e-15 for channel in channels)
    assert summary["energy_j"]["final_total_dissipation_j"] == sum(channel[-1] for channel in channels)
    assert summary["energy_j"]["total_mechanical_plus_dissipated_max_drift_j"] <= 1.0e-6


def test_rk4_step_halving_reduces_each_terminal_component_or_reaches_roundoff(dual_bundle):
    histories = dual_bundle[4]
    coarse = _terminal_difference(histories["rk4_coarse"], histories["rk4_fine"])
    fine = _terminal_difference(histories["rk4_fine"], histories["rk4_reference"])
    floors = {
        "service_base_position_m": 1.0e-12,
        "service_base_quaternion_rad": 5.0e-8,
        "service_q_R_rad": 1.0e-12,
        "service_q_P_m": 1.0e-12,
        "service_v_base_m_s": 1.0e-12,
        "service_omega_base_rad_s": 1.0e-14,
        "service_qdot_R_rad_s": 1.0e-12,
        "service_qdot_P_m_s": 1.0e-12,
        "target_position_m": 1.0e-12,
        "target_quaternion_rad": 5.0e-8,
        "target_velocity_m_s": 1.0e-12,
        "target_omega_rad_s": 1.0e-14,
    }
    assert all(
        fine[key] < coarse[key]
        or (fine[key] <= floors[key] and coarse[key] <= floors[key])
        for key in coarse
    )


def test_midpoint_refinement_is_bounded_across_nonsmooth_contact_events(dual_bundle):
    histories = dual_bundle[4]
    fine = _terminal_difference(histories["midpoint_fine"], histories["midpoint_reference"])
    envelopes = {
        "service_base_position_m": 5.0e-10,
        "service_base_quaternion_rad": 5.0e-8,
        "service_q_R_rad": 2.0e-6,
        "service_q_P_m": 2.0e-6,
        "service_v_base_m_s": 1.0e-7,
        "service_omega_base_rad_s": 4.0e-7,
        "service_qdot_R_rad_s": 5.0e-4,
        "service_qdot_P_m_s": 5.0e-4,
        "target_position_m": 1.0e-8,
        "target_quaternion_rad": 5.0e-8,
        "target_velocity_m_s": 1.0e-6,
        "target_omega_rad_s": 5.0e-9,
    }
    assert all(fine[key] <= envelopes[key] for key in fine)


def test_cross_integrator_contact_candidate_and_release_events_converge(dual_bundle):
    summaries = dual_bundle[5]
    rk = summaries["rk4_reference"]
    midpoint = summaries["midpoint_reference"]
    for side in ("left", "right"):
        assert abs(rk["per_contact"][side]["first_contact_time_s"] - midpoint["per_contact"][side]["first_contact_time_s"]) <= 5.0e-6
        assert abs(rk["per_contact"][side]["separation_after_contact_time_s"] - midpoint["per_contact"][side]["separation_after_contact_time_s"]) <= 1.0e-5
        assert abs(rk["per_contact"][side]["peak_normal_force_n"] - midpoint["per_contact"][side]["peak_normal_force_n"]) <= 1.0e-2
        assert abs(rk["per_contact"][side]["maximum_penetration_m"] - midpoint["per_contact"][side]["maximum_penetration_m"]) <= 2.0e-6
    assert abs(
        rk["state_machine"]["first_soft_capture_candidate_time_s"]
        - midpoint["state_machine"]["first_soft_capture_candidate_time_s"]
    ) <= 2.0e-4
