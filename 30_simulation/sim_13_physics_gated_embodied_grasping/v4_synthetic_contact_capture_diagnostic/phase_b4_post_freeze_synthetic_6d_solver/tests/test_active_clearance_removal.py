from __future__ import annotations

import numpy as np
import pytest

import b4_solver.constraint_solver as solver


@pytest.fixture(scope="module")
def hybrid_fixture(primary_run):
    return solver.execute_abstract_removal_fixture(primary_run)


@pytest.mark.parametrize("metric,tolerance", [
    ("linear_momentum_drift_N_s", 1.0e-9),
    ("angular_momentum_drift_N_m_s", 1.0e-9),
    ("energy_plus_dissipation_drift_J", 1.0e-7),
    ("pose_translation_residual_m", 1.0e-9),
    ("pose_rotation_residual_rad", 1.0e-9),
    ("relative_linear_twist_m_s", 1.0e-9),
    ("relative_angular_twist_rad_s", 1.0e-9),
    ("ideal_constraint_power_W", 1.0e-10),
    ("contact_force_while_active_N", 1.0e-12),
    ("contact_torque_while_active_N_m", 1.0e-12),
    ("mass_formula_fixed_child_inf", 1.0e-10),
    ("bias_formula_fixed_child_base_linear_N", 1.0e-9),
    ("bias_formula_fixed_child_base_angular_N_m", 1.0e-9),
    ("bias_formula_fixed_child_R_joint_N_m", 1.0e-9),
    ("bias_formula_fixed_child_P_joint_N", 1.0e-9),
    ("reduced_full_residual_power_W", 1.0e-10),
])
def test_active_metric_is_samplewise_below_native_tolerance(metric, tolerance, primary_run):
    assert primary_run.maxima[metric] <= tolerance
    assert np.all(np.abs(primary_run.sample_ledgers[metric]) <= tolerance)


def test_active_target_is_derived_not_independently_integrated(primary_run):
    assert primary_run.maxima["pose_translation_residual_m"] == 0.0
    assert primary_run.maxima["pose_rotation_residual_rad"] == 0.0
    assert primary_run.maxima["relative_linear_twist_m_s"] == 0.0
    assert primary_run.maxima["relative_angular_twist_rad_s"] == 0.0


def test_contact_kernel_is_exactly_disabled(primary_run):
    assert primary_run.maxima["contact_force_while_active_N"] == 0.0
    assert primary_run.maxima["contact_torque_while_active_N_m"] == 0.0


def test_primary_branch_has_no_finite_removal_in_bounded_horizon(primary_run):
    assert primary_run.clearance["finite_event"] is False
    assert primary_run.synthetic_removal_executed is False
    assert primary_run.terminal_status == "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED"
    assert primary_run.clearance["global_empty_eligibility_set_claimed"] is False
    assert primary_run.post_release is None


def test_bounded_horizon_ends_exactly_at_b3_boundary(primary_run):
    assert abs(primary_run.time_s[-1] - 0.08) <= 1.0e-14


def test_fingers_continue_deeper_into_negative_gap(primary_run):
    assert primary_run.left_gap_m[-1] < primary_run.left_gap_m[0] < 0.0
    assert primary_run.right_gap_m[-1] < primary_run.right_gap_m[0] < 0.0


def test_clearance_good_fixture_finds_earliest_event(primary_acquisition):
    ta = primary_acquisition.acquisition_time_s
    time = ta + np.arange(9) * 0.0005
    gap = np.full(9, 2.0e-6); rate = np.zeros(9)
    result = solver.certify_earliest_clearance(time, gap, gap, rate, rate, acquisition_time_s=ta)
    assert result["finite_event"] is True
    assert abs(result["tau_c_s"] - (ta + 0.001)) <= 1.0e-12
    assert abs(result["removal_time_s"] - (ta + 0.002)) <= 1.0e-12


def test_clearance_internal_negative_gap_trap_is_rejected(primary_acquisition):
    ta = primary_acquisition.acquisition_time_s
    time = np.array((ta + 0.001, ta + 0.002))
    gap = np.array((2.0e-6, 2.0e-6)); rate = np.array((-0.01, 0.01))
    result = solver.certify_earliest_clearance(time, gap, gap, rate, rate, acquisition_time_s=ta)
    assert result["finite_event"] is False


def test_clearance_ledger_interval_failure_is_rejected(primary_acquisition):
    ta = primary_acquisition.acquisition_time_s
    time = ta + np.arange(9) * 0.0005
    gap = np.full(9, 2.0e-6); rate = np.zeros(9)
    certified = np.ones(8, dtype=bool); certified[3] = False
    result = solver.certify_earliest_clearance(time, gap, gap, rate, rate, acquisition_time_s=ta, ledger_interval_certified=certified)
    assert result["finite_event"] is True
    assert result["removal_time_s"] > ta + 0.002


def test_release_mapping_is_componentwise_and_zero_impulse(primary_run):
    index = 4
    service = solver.ServiceState(
        primary_run.service_position_m[index], primary_run.service_quaternion_wxyz[index],
        primary_run.service_joint_coordinates_mixed[index], primary_run.eta_mixed[index],
    )
    mapping = solver.release_mapping(primary_run.acquisition, service)
    np.testing.assert_array_equal(mapping["z_before"], mapping["z_after"])
    np.testing.assert_array_equal(mapping["linear_impulse_N_s"], np.zeros(3))
    np.testing.assert_array_equal(mapping["angular_impulse_N_m_s"], np.zeros(3))
    assert mapping["ideal_constraint_stored_energy_J"] == 0.0


def test_abstract_removal_fixture_does_not_promote_main_branch(primary_run, hybrid_fixture):
    assert primary_run.synthetic_removal_executed is False
    assert hybrid_fixture["fixture_pass_does_not_set_main_synthetic_removal_executed"] is True
    assert hybrid_fixture["fixture_inputs_are_hardware_specifications"] is False
    assert hybrid_fixture["fixture_satisfies_main_b3_soft_capture_trigger"] is False
    assert hybrid_fixture["fixture_receives_physical_or_main_trigger_credit"] is False
    assert hybrid_fixture["fixture_contact_points_and_potentials_recomputed_from_perturbed_state"] is True
    assert hybrid_fixture["fixture_event"]["state_label"] == "ALGORITHM_ONLY_NONTRIGGER_INITIAL_STATE_FIXTURE"
    assert hybrid_fixture["fixture_event"]["criteria"]["soft_capture_transient_qualifies"] is False


def test_hybrid_fixture_executes_complete_five_ms_post_release(hybrid_fixture):
    post = hybrid_fixture["post_release"]
    assert hybrid_fixture["clearance"]["finite_event"] is True
    assert hybrid_fixture["no_state_mutation_after_acquisition"] is True
    assert hybrid_fixture["clearance_derived_from_same_active_state_trajectory"] is True
    assert "COUNTERFACTUAL_ATTACHED_SEARCH_TRACE" in hybrid_fixture["active_trace_semantics"]
    assert hybrid_fixture["same_active_trajectory_required_interval_s"] == [
        hybrid_fixture["fixture_event"]["time_s"], hybrid_fixture["clearance"]["removal_time_s"]
    ]
    assert hybrid_fixture["propagate_active_finite_event_branch_executed"] is True
    assert hybrid_fixture["exact_active_state_reconstructed_at_offgrid_removal_time"] is True
    run = hybrid_fixture["active_run"]
    assert run["synthetic_removal_executed"] is True
    assert run["post_release"] == post
    ta = hybrid_fixture["fixture_event"]["time_s"]
    step = hybrid_fixture["fixture_event"]["step_s"]
    relative_index = (hybrid_fixture["clearance"]["removal_time_s"] - ta) / step
    assert abs(relative_index - round(relative_index)) > 1.0e-6
    assert post["post_release_passed"] is True
    assert post["terminal_status"] == "SYNTHETIC_CONSTRAINT_REMOVAL_AND_POST_RELEASE_OBSERVATION_COMPLETE"
    assert abs(post["observation_duration_s"] - 0.005) <= 1.0e-12
    assert post["clearance"]["full_interval_certified"] is True


@pytest.mark.parametrize("channel", [
    "service_base_linear_m_s", "service_base_angular_rad_s", "service_R_joint_rad_s",
    "service_P_joint_m_s", "target_linear_m_s", "target_angular_rad_s",
])
def test_hybrid_release_has_zero_native_channel_velocity_jump(channel, hybrid_fixture):
    mapping = hybrid_fixture["post_release"]["mapping"]
    assert mapping["native_velocity_jump_maxima"][channel] <= 1.0e-12
    np.testing.assert_array_equal(mapping["z_before"], mapping["z_after"])


def test_post_release_target_is_independently_integrated(hybrid_fixture):
    post = hybrid_fixture["post_release"]
    assert post["target_state_source_after_removal"] == "INDEPENDENT_13D_ZERO_EXTERNAL_FREE_FLIGHT"
    assert post["maxima"]["snapshot_translation_residual_m"] > 0.0
    assert post["maxima"]["snapshot_rotation_residual_rad"] > 0.0


def test_post_release_contact_kernel_remains_disabled(hybrid_fixture):
    trace = hybrid_fixture["post_release"]["trace"]
    assert all(call["phase"] == "POST_REMOVAL" and call["enabled_argument"] is False for call in trace["contact_calls"])
    assert max(trace["contact_force_N"]) == 0.0
    assert max(trace["contact_torque_N_m"]) == 0.0


def test_post_release_reentry_fails_closed(primary_run):
    model = solver.BranchedGripperServiceModel()
    service = solver._negative_control_release_service(primary_run)
    q = service.joint_coordinates_mixed.copy(); q[6:8] -= 0.000985
    velocity = service.nu_s_mixed.copy(); velocity[12:14] = -0.02
    near_reentry = solver.ServiceState(
        service.base_position_inertial_m, service.base_quaternion_body_to_inertial_wxyz,
        q, velocity,
    )
    result = solver.execute_post_release(
        model, primary_run.acquisition, near_reentry,
        release_time_s=primary_run.acquisition.acquisition_time_s + 0.002,
        method="rk4", step_s=0.00025,
    )
    assert result["post_release_passed"] is False
    assert result["clearance"]["full_interval_certified"] is False
    assert result["terminal_status"] == "DIAGNOSTIC_FAIL_CLOSED_POST_REMOVAL_CLEARANCE_REENTRY"


@pytest.mark.parametrize("scale", [1.0e-15, 1.0, 1.0e15])
def test_root_partition_is_invariant_to_coefficient_scale(scale):
    roots = solver._poly_real_roots(scale * np.array((1.0, -1.0, 0.1875)))
    np.testing.assert_allclose(roots, [0.25, 0.75], rtol=0.0, atol=1.0e-12)


def test_gap_threshold_is_fail_closed_in_metres(primary_acquisition):
    ta = primary_acquisition.acquisition_time_s
    time = ta + np.arange(9) * 0.0005
    rate = np.zeros(9)
    below = np.full(9, solver.GAP_CLEARANCE_M - 1.0e-15)
    exact = np.full(9, solver.GAP_CLEARANCE_M)
    assert solver.certify_earliest_clearance(time, below, below, rate, rate, acquisition_time_s=ta)["finite_event"] is False
    assert solver.certify_earliest_clearance(time, exact, exact, rate, rate, acquisition_time_s=ta)["finite_event"] is True


def test_gap_rate_threshold_is_fail_closed_in_metres_per_second(primary_acquisition):
    ta = primary_acquisition.acquisition_time_s
    time = ta + np.arange(9) * 0.0005
    elapsed = time - time[0]
    below_rate = -solver.GAP_RATE_REENTRY_TOL_M_S - 1.0e-12
    exact_rate = -solver.GAP_RATE_REENTRY_TOL_M_S
    gap_below = 1.0e-4 + below_rate * elapsed
    gap_exact = 1.0e-4 + exact_rate * elapsed
    assert solver.certify_earliest_clearance(time, gap_below, gap_below, np.full(9, below_rate), np.full(9, below_rate), acquisition_time_s=ta)["finite_event"] is False
    assert solver.certify_earliest_clearance(time, gap_exact, gap_exact, np.full(9, exact_rate), np.full(9, exact_rate), acquisition_time_s=ta)["finite_event"] is True


@pytest.mark.parametrize("bad_shape", [1, 3, 4])
def test_clearance_rejects_inconsistent_shapes(bad_shape, primary_acquisition):
    ta = primary_acquisition.acquisition_time_s
    time = np.linspace(ta, ta + 0.002, 5)
    good = np.full(5, 2.0e-6)
    with pytest.raises(solver.SolverError):
        solver.certify_earliest_clearance(time, good[:bad_shape], good, good, good, acquisition_time_s=ta)
