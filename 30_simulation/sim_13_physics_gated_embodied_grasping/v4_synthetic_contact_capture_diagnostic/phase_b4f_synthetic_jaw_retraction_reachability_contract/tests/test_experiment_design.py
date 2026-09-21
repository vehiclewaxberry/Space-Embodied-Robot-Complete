from __future__ import annotations

import itertools

import pytest


def _arm(contracts, arm_id):
    return next(row for row in contracts["experiment"]["arms"] if row["id"] == arm_id)


def test_computer_experiment_not_hardware_replication(contracts):
    design = contracts["experiment"]
    assert design["scope"] == "PRE_REGISTERED_DETERMINISTIC_COMPUTER_EXPERIMENT"
    semantics = design["replication_semantics"]
    assert semantics["six_numerical_trajectories_are_hardware_replicates"] is False
    assert semantics["integrator_and_step_variants_are_verification_blocks"] is True
    assert semantics["statistical_population_inference_authorized"] is False
    assert semantics["pseudoreplication_forbidden"] is True


def test_a0_exact_zero_input_replay(contracts):
    arm = _arm(contracts, "A0_ZERO_INPUT_EXACT_REPLAY")
    assert arm["alpha_left"] == arm["alpha_right"] == 0.0
    assert arm["command_duration_s"] == 0.0
    assert "W_act=0" in arm["required_outcome"]
    assert "no finite main-branch removal" in arm["required_outcome"]


def test_a1_discrete_full_factorial_is_exact(contracts):
    arm = _arm(contracts, "A1_SYMMETRIC_BRAKE_OPEN")
    assert arm["alpha_levels_dimensionless"] == [0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
    assert arm["command_duration_levels_s"] == [0.005, 0.01, 0.02]
    assert len(list(itertools.product(arm["alpha_levels_dimensionless"], arm["command_duration_levels_s"]))) == 18
    assert arm["full_factorial_case_count_per_event_and_integrator"] == 18
    assert arm["center_or_unregistered_levels_forbidden"] is True


@pytest.mark.parametrize(
    "variant_id",
    ["RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR", "RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR"],
)
def test_a2_registered_variants(contracts, variant_id):
    arm = _arm(contracts, "A2_ASYMMETRIC_LAG_AND_ONE_SIDE_LOSS")
    assert variant_id in {row["id"] for row in arm["variants"]}
    assert arm["bilateral_clearance_gate_never_relaxed"] is True
    assert arm["success_or_failure_is_not_preregistered"] is True


def test_a2_is_conditional_on_a1_success(contracts):
    rule = _arm(contracts, "A2_ASYMMETRIC_LAG_AND_ONE_SIDE_LOSS")["parent_case_selection"]
    assert "if no A1 succeeds, A2 is NOT_EVALUATED" in rule


def test_registered_horizon_cannot_be_extended(contracts):
    horizon = contracts["experiment"]["registered_horizon"]
    assert horizon["active_duration_after_acquisition_s"] == 0.08
    assert horizon["extension_after_observing_results_forbidden"] is True
    assert horizon["global_unreachability_claim"] is False


def test_discrete_selector_only_reports_lowest_tested(contracts):
    selector = contracts["experiment"]["primary_case_selector"]
    assert selector["reported_label"] == "lowest_tested_reachable_alpha_in_registered_discrete_grid"
    assert selector["minimum_required_force_or_work_claim_authorized"] is False
    assert selector["between_level_interpolation_or_inverse_threshold_estimation_authorized"] is False
    assert selector["selected_case_is_a_synthetic_research_candidate_only"] is True


@pytest.mark.parametrize("side", ["left_P_coordinate_m_closed_interval", "right_P_coordinate_m_closed_interval"])
def test_geometry_domain_exact_closed_interval(contracts, side):
    domain = contracts["model"]["synthetic_geometry_validity_domain"]
    assert domain[side] == [0.0, 0.0715]
    assert domain["evaluation"] == "every accepted integrator stage, stored sample and exact event state"
    assert domain["exit_action"] == "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN"
    assert domain["extrapolation_or_clipping_forbidden"] is True


def test_geometry_failures_cannot_enter_selector(contracts):
    policy = contracts["experiment"]["geometry_domain_policy"]
    assert policy["any_stage_sample_or_event_outside_domain"] == "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN"
    assert policy["failed_domain_case_can_enter_primary_selector"] is False
    assert policy["clipping_or_extrapolation_forbidden"] is True


def test_blocking_and_seed_are_frozen(contracts):
    design = contracts["experiment"]
    assert [row["id"] for row in design["blocking"]["blocks"]] == ["RK4", "MIDPOINT"]
    assert design["blocking"]["each_treatment_uses_its_own_first_qualifying_B3_event"] is True
    assert design["blocking"]["forced_shared_event_time_forbidden"] is True
    assert design["blocking"]["fresh_initial_state_for_every_run"] is True
    assert design["run_order"]["seed"] == 20260824
    assert design["run_order"]["hidden_state_between_runs_forbidden"] is True

