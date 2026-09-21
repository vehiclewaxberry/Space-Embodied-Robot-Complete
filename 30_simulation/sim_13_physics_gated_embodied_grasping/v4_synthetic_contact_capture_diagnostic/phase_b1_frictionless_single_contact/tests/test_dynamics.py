from __future__ import annotations

import numpy as np

from b1_contact import no_contact_regression, summarize_history


def _final_component_errors(left, right):
    return {
        "base_position_m": float(np.linalg.norm(left.service_base_position_inertial_m[-1] - right.service_base_position_inertial_m[-1])),
        "q_R_rad": float(np.max(np.abs(left.service_joint_coordinates_mixed[-1, :6] - right.service_joint_coordinates_mixed[-1, :6]))),
        "q_P_m": float(np.max(np.abs(left.service_joint_coordinates_mixed[-1, 6:] - right.service_joint_coordinates_mixed[-1, 6:]))),
        "qdot_R_rad_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, 6:12] - right.service_nu_s_mixed[-1, 6:12]))),
        "qdot_P_m_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, 12:] - right.service_nu_s_mixed[-1, 12:]))),
        "target_position_m": float(np.linalg.norm(left.target_position_inertial_m[-1] - right.target_position_inertial_m[-1])),
        "target_velocity_m_s": float(np.max(np.abs(left.target_twist_inertial_mixed[-1, :3] - right.target_twist_inertial_mixed[-1, :3]))),
    }


def test_nominal_state_machine_has_only_single_contact_sequence(contact_bundle):
    history = contact_bundle[-1]["rk4_reference"]
    transitions = [item["to"] for item in history.transition_log]
    assert transitions == ["SEPARATED", "APPROACH", "SINGLE_CONTACT", "SEPARATING_AFTER_CONTACT"]
    assert not history.aborted_safe
    assert not ({"DUAL_CONTACT", "SOFT_CAPTURE", "LOCKED", "GRASP_SUCCESS"} & set(history.state_label))


def test_full_floating_contact_changes_base_revolute_and_prismatic_channels(contact_bundle):
    history = contact_bundle[-1]["rk4_reference"]
    delta = history.service_nu_s_mixed[-1] - history.service_nu_s_mixed[0]
    assert np.linalg.norm(delta[:6]) > 1.0e-8
    assert np.linalg.norm(delta[6:12]) > 1.0e-8
    assert np.linalg.norm(delta[12:14]) > 1.0e-8


def test_contact_force_common_point_and_ph_ledgers_close(contact_bundle):
    summary = summarize_history(contact_bundle[-1]["rk4_reference"])
    geometry = summary["geometry_and_force"]
    linear = summary["linear_momentum_n_s"]
    angular = summary["angular_momentum_about_common_inertial_origin_n_m_s"]
    assert geometry["action_reaction_max_error_n"] <= 1.0e-12
    assert geometry["common_point_radial_moment_max_error_n_m"] <= 1.0e-12
    assert linear["service_delta_minus_impulse_max_error_n_s"] <= 1.0e-10
    assert linear["target_delta_plus_impulse_max_error_n_s"] <= 1.0e-10
    assert linear["total_max_drift_n_s"] <= 1.0e-10
    assert angular["service_delta_minus_angular_impulse_max_error_n_m_s"] <= 1.0e-10
    assert angular["target_delta_plus_angular_impulse_max_error_n_m_s"] <= 1.0e-10
    assert angular["total_max_drift_n_m_s"] <= 1.0e-10


def test_kinetic_elastic_and_dissipation_energy_closes(contact_bundle):
    summary = summarize_history(contact_bundle[-1]["rk4_reference"])
    energy = summary["energy_j"]
    assert energy["peak_elastic_j"] > 0.0
    assert energy["final_dissipated_j"] > 0.0
    assert energy["total_mechanical_plus_dissipated_max_drift_j"] <= 1.0e-6


def test_no_contact_limit_regresses_phase_a_v3_componentwise():
    result = no_contact_regression(step_s=5.0e-4, steps=8)
    assert max(result.values()) <= 2.0e-14


def test_rk4_step_halving_reduces_every_frozen_component_error(contact_bundle):
    histories = contact_bundle[-1]
    coarse = _final_component_errors(histories["rk4_coarse"], histories["rk4_fine"])
    fine = _final_component_errors(histories["rk4_fine"], histories["rk4_reference"])
    assert all(fine[key] < coarse[key] for key in coarse)
    assert fine["q_R_rad"] < 6.0e-6
    assert fine["q_P_m"] < 5.0e-6
    assert fine["qdot_R_rad_s"] < 2.0e-4
    assert fine["qdot_P_m_s"] < 2.0e-4


def test_independent_midpoint_step_halving_and_event_times_converge(contact_bundle):
    histories = contact_bundle[-1]
    reference = histories["rk4_reference"]
    midpoint_coarse = histories["midpoint_coarse"]
    midpoint_fine = histories["midpoint_fine"]
    midpoint_reference = histories["midpoint_reference"]
    coarse_error = _final_component_errors(midpoint_coarse, midpoint_fine)
    fine_error = _final_component_errors(midpoint_fine, midpoint_reference)
    assert all(fine_error[key] < coarse_error[key] for key in coarse_error)
    reference_event = summarize_history(reference)["contact_event"]
    fine_event = summarize_history(midpoint_reference)["contact_event"]
    assert abs(fine_event["first_contact_time_s"] - reference_event["first_contact_time_s"]) < 2.0e-6
    assert abs(fine_event["separation_after_contact_time_s"] - reference_event["separation_after_contact_time_s"]) < 5.0e-6
    assert abs(fine_event["peak_normal_force_n"] - reference_event["peak_normal_force_n"]) < 2.0e-2
    assert abs(fine_event["maximum_penetration_m"] - reference_event["maximum_penetration_m"]) < 2.0e-6


def test_every_contact_log_uses_the_same_time_axis(contact_bundle):
    history = contact_bundle[-1]["rk4_reference"]
    count = len(history.time_s)
    logged = (
        history.gap_m,
        history.penetration_m,
        history.normal_target_to_pad_inertial,
        history.common_contact_point_inertial_m,
        history.relative_velocity_inertial_m_s,
        history.normal_force_magnitude_n,
        history.service_force_inertial_n,
        history.target_force_inertial_n,
        history.cumulative_service_impulse_n_s,
        history.cumulative_service_angular_impulse_about_origin_n_m_s,
    )
    assert all(len(item) == count for item in logged)
    assert np.allclose(np.diff(history.time_s), history.step_s)
