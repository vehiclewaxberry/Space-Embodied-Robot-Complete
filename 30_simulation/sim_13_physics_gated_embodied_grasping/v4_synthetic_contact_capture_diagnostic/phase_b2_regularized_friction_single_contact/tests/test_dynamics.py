from __future__ import annotations

import numpy as np

from b1_contact import integrate_contact
from b2_contact import no_contact_regression, summarize_friction_history


def _terminal_vector(history):
    return np.concatenate((
        history.service_base_position_inertial_m[-1],
        history.service_joint_coordinates_mixed[-1],
        history.service_nu_s_mixed[-1],
        history.target_position_inertial_m[-1],
        history.target_twist_inertial_mixed[-1],
    ))


def test_state_machine_remains_single_contact_only(friction_bundle):
    history = friction_bundle[-1]["rk4_reference"]
    sequence = [item["to"] for item in history.transition_log]
    assert sequence == ["SEPARATED", "APPROACH", "SINGLE_CONTACT", "SEPARATING_AFTER_CONTACT"]
    assert not history.aborted_safe


def test_linear_angular_and_energy_ledgers_close(friction_bundle):
    config = friction_bundle[3]
    summary = summarize_friction_history(friction_bundle[-1]["rk4_reference"], config)
    assert summary["linear_momentum_n_s"]["total_max_drift_n_s"] <= 1.0e-10
    assert summary["angular_momentum_about_common_inertial_origin_n_m_s"]["total_max_drift_n_m_s"] <= 1.0e-10
    assert summary["energy_j"]["total_mechanical_plus_dissipated_max_drift_j"] <= 1.0e-6
    assert summary["friction"]["final_friction_dissipation_j"] > 0.0


def test_no_contact_limit_matches_phase_b1_componentwise():
    assert max(no_contact_regression().values()) <= 2.0e-14


def test_friction_changes_target_spin_relative_to_b1(friction_bundle):
    model, service, target, config, histories = friction_bundle
    b1 = integrate_contact(
        model, service, target, config,
        step_s=2.5e-4, duration_s=0.04, method="rk4",
    )
    b2 = histories["rk4_reference"]
    assert np.linalg.norm(b2.target_twist_inertial_mixed[-1, 3:] - b1.target_twist_inertial_mixed[-1, 3:]) > 1.0e-4


def test_rk4_step_halving_reduces_terminal_error(friction_bundle):
    h = friction_bundle[-1]
    coarse = np.max(np.abs(_terminal_vector(h["rk4_coarse"]) - _terminal_vector(h["rk4_fine"])))
    fine = np.max(np.abs(_terminal_vector(h["rk4_fine"]) - _terminal_vector(h["rk4_reference"])))
    assert fine < coarse
    assert fine <= 1.5e-4


def test_midpoint_step_halving_reduces_terminal_error(friction_bundle):
    h = friction_bundle[-1]
    coarse = np.max(np.abs(_terminal_vector(h["midpoint_coarse"]) - _terminal_vector(h["midpoint_fine"])))
    fine = np.max(np.abs(_terminal_vector(h["midpoint_fine"]) - _terminal_vector(h["midpoint_reference"])))
    assert fine < coarse
    assert fine <= 5.0e-6


def test_cross_integrator_contact_events_converge(friction_bundle):
    config = friction_bundle[3]
    h = friction_bundle[-1]
    rk = summarize_friction_history(h["rk4_reference"], config)["contact_event"]
    mp = summarize_friction_history(h["midpoint_reference"], config)["contact_event"]
    assert abs(rk["first_contact_time_s"] - mp["first_contact_time_s"]) <= 2.0e-6
    assert abs(rk["separation_after_contact_time_s"] - mp["separation_after_contact_time_s"]) <= 5.0e-6
    assert abs(rk["peak_normal_force_n"] - mp["peak_normal_force_n"]) <= 2.0e-2
    assert abs(rk["maximum_penetration_m"] - mp["maximum_penetration_m"]) <= 2.0e-6
