from __future__ import annotations

import math

import pytest


def test_reference_force_is_one_common_algorithm_only_per_finger_value(contracts):
    force = contracts["reference_force"]
    run_force = contracts["run_spec"]["force_reference"]
    assert force["classification"] == (
        "ALGORITHM_ONLY_DIMENSIONAL_REFERENCE_NOT_ACTUATOR_SPECIFICATION"
    )
    assert force["individual_finger_reference_force_N"] == pytest.approx(
        0.024542335689275555, rel=0.0, abs=1e-18
    )
    assert run_force["one_common_Q_ref_N_per_finger"] == (
        force["individual_finger_reference_force_N"]
    )
    assert force["per_lane_or_treatment_recomputation_forbidden"] is True
    assert force["physical_force_capacity_inferred"] is False


def test_reference_force_components_are_dimensionally_and_algebraically_coherent(contracts):
    force = contracts["reference_force"]
    expected_common = (
        force["symmetric_effective_mass_kg"]
        * force["reference_closing_speed_m_s"]
        / force["reference_braking_time_s"]
    )
    assert force["reference_common_force_N"] == pytest.approx(
        expected_common, rel=2e-15, abs=0.0
    )
    assert force["individual_finger_reference_force_N"] == pytest.approx(
        force["reference_common_force_N"] / math.sqrt(2.0), rel=2e-15, abs=0.0
    )


def test_reference_common_basis_is_unit_norm_and_p_only(contracts):
    basis = contracts["reference_force"]["common_basis_14"]
    assert len(basis) == 14
    assert basis[:12] == [0] * 12
    assert basis[12] == pytest.approx(1.0 / math.sqrt(2.0), abs=1e-16)
    assert basis[13] == pytest.approx(1.0 / math.sqrt(2.0), abs=1e-16)
    assert sum(component * component for component in basis) == pytest.approx(1.0, abs=3e-16)


def test_reference_opening_signs_are_positive_and_recomputed_from_raw_diagonal(contracts):
    force = contracts["reference_force"]
    assert force["centered_gap_derivative_step_m"] == 1e-7
    assert force["registered_and_recomputed_opening_sign_left_right"] == [1, 1]
    assert all(value > 0.0 for value in force["gap_derivative_diagonal_dimensionless_left_right"])
    assert all(0.0 <= q <= 0.0715 for q in force["source_P_coordinates_m_left_right"])
    requirement = force["implementation_requirement"]
    assert "linear solve" in requirement
    assert "never explicit matrix inverse" in requirement


def test_reference_recomputation_uses_native_quantity_tolerances(contracts):
    assert contracts["reference_force"]["recomputation_absolute_tolerances"] == {
        "P_coordinate_m": 1e-12,
        "eta_P_m_s": 1e-12,
        "gap_derivative_dimensionless": 1e-9,
        "effective_mass_kg": 1e-12,
        "reference_speed_m_s": 1e-12,
        "reference_force_N": 1e-12,
    }


def test_forced_active_state_is_30d_and_generalized_force_is_strictly_p_only(contracts):
    state = contracts["run_spec"]["active_state_and_stages"]
    assert state["augmented_state_shape"] == 30
    assert state["state_layout"] == "service_29_plus_signed_W_act_J"
    assert state["Q_shape"] == 14
    assert state["only_allowed_nonzero_Q_indices"] == [12, 13]
    assert "W_dot=Q_P_left*eta_P_left+Q_P_right*eta_P_right" in state["equation"]
    assert state["integrate_work_at_the_same_rk4_or_midpoint_stages"] is True
    assert "Q_base_and_R_exact_zero" in state["stage_audit"]


def test_command_profile_has_exact_zero_endpoints_and_closed_support(contracts):
    command = contracts["run_spec"]["command"]
    assert command["base_profile"] == (
        "Q_i=alpha_i*sigma_i*Q_ref*sin(pi*(t-start_i)/T_cmd)^2 "
        "on the closed support and exact 0.0 outside"
    )
    assert command["profile_endpoint_implementation"] == (
        "return exact 0.0 at and outside both endpoints; do not rely on floating sin(pi)"
    )
    assert command["command_during_full_clearance_dwell_and_removal"] == "exact_zero"
    assert command["a1_alpha_levels"] == [0.5, 1, 2, 4, 8, 16]
    assert command["a1_duration_s_levels"] == [0.005, 0.01, 0.02]


def test_asymmetric_commands_preserve_registered_full_duration_and_mirrors(contracts):
    command = contracts["run_spec"]["command"]
    assert command["a2_right_half_delay"] == {
        "left_ratio": 1.0,
        "left_delay_s": 0.0,
        "right_ratio": 0.5,
        "right_delay_s": 0.005,
        "both_durations": "full parent T_cmd",
    }
    assert command["a2_left_half_delay_mirror"] == {
        "left_ratio": 0.5,
        "left_delay_s": 0.005,
        "right_ratio": 1.0,
        "right_delay_s": 0.0,
        "both_durations": "full parent T_cmd",
    }
    assert command["a2_right_command_off"]["right_ratio"] == 0.0
    assert command["a2_left_command_off_mirror"]["left_ratio"] == 0.0


def test_p_stroke_domain_is_closed_fail_closed_and_never_clipped(contracts):
    state = contracts["run_spec"]["active_state_and_stages"]
    assert state["P_coordinate_m_closed_interval_left_right"] == [
        [0, 0.0715],
        [0, 0.0715],
    ]
    assert state["centered_sign_step_m"] == 1e-7
    assert state["stage_domain_exit_action"] == (
        "terminate that case as DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN without "
        "clipping or extrapolation; preserve raw pre-failure stages; exclude case from selector"
    )
    assert state["a_domain_failed_case_invalidates_other_registered_cases"] is False
    assert "each raw diagonal gap derivative must be strictly positive" in state["sign_rule"]
    assert "sigma consumed by the actual command path must equal both recomputed sign" in state["sign_rule"]
    assert "registered sign +1 on each side" in state["sign_rule"]
    assert "consumed-sign mismatch" in state["sign_rule"]
    assert "out-of-domain fails closed" in state["sign_rule"]


def test_signed_actuator_work_and_energy_identity_are_not_redefined(contracts):
    ledger = contracts["run_spec"]["work_and_ledger_audit"]
    assert ledger["signed_work_never_replaced_by_absolute_work"] is True
    assert ledger["active_identity"] == (
        "T_service+T_target+D_B3+D_switch-W_act=initial_constant"
    )
    assert ledger["linear_and_angular_momentum_conserved_for_internal_joint_actuation"] is True
    assert ledger["forced_full_residual"] == "M_full*z_dot+h_full-[Q_a;zero_target]"
    assert ledger["reduced_residual"] == "L_transpose*forced_full_residual"
    assert ledger["work_at_removal_is_not_reset"] is True


def test_work_quadrature_requires_absolute_bound_not_only_relative_improvement(contracts):
    rule = contracts["run_spec"]["work_and_ledger_audit"]["quadrature_acceptance"]
    assert rule == (
        "fine absolute error versus augmented W must be <=1e-7_J AND either fine error "
        "<= coarse error+1e-15_J or coarse error <=1e-7_J"
    )
    assert "fine absolute error" in rule
    assert "<=1e-7_J AND" in rule


def test_event_mapping_is_exact_zero_jump_and_post_release_work_is_carried(contracts):
    hybrid = contracts["run_spec"]["event_and_hybrid"]
    assert hybrid["exact_event_reconstruction"] == (
        "reintegrate the forced 30D RHS from the accepted left bracket to t_removal; "
        "nearest-sample rounding forbidden"
    )
    assert hybrid["removal_mapping"] == (
        "z_before=L(q_r)eta_r; z_after componentwise copy; zero impulse; "
        "zero ideal constraint stored energy"
    )
    assert "carry W_act(t_removal) as a constant" in hybrid["post_release_work"]
    assert hybrid["gap_or_rate_reentry"] == "DIAGNOSTIC_FAIL_CLOSED"


def test_post_release_rechecks_domain_and_opening_sign_at_all_stages(contracts):
    hybrid = contracts["run_spec"]["event_and_hybrid"]
    assert "B4G-instrumented independent 29D service plus 13D target" in hybrid["post_release"]
    audit = hybrid["post_release_stage_audit"]
    assert "every RK4/midpoint RHS stage" in audit
    assert "stored sample and exact terminal state" in audit
    assert "both P coordinates in [0,0.0715]m" in audit
    assert "centered raw gap-Jacobian perturbations in-domain" in audit
    assert "both opening signs positive" in audit
    assert "no clipping or extrapolation" in audit


def test_a0_replay_acceptance_keeps_zero_force_work_and_native_channels(contracts):
    acceptance = contracts["run_spec"]["a0_acceptance"]
    assert acceptance["pre_and_post_sentinels_must_have_byte_identical_canonical_numeric_payloads_after_excluding_run_slot_identifiers"] is True
    assert acceptance["Q_and_W_exact_zero"] is True
    assert acceptance["compare_to_fresh_B4E_propagate_active_on_common_absolute_interval"] is True
    assert len(acceptance["comparison_channels"]) == 10
    tolerances = acceptance["native_absolute_tolerances"]
    assert list(tolerances) == acceptance["comparison_channels"]
    assert set(tolerances.values()) == {1e-12}
    assert acceptance["finite_main_removal_in_any_registered_a0_extension_action"] == (
        "FAIL_B4F_G02_A0_REQUIRED_OUTCOME"
    )
    assert acceptance[
        "no_main_removal_in_registered_zero_input_extension_is_not_global_unreachability"
    ] is True


def test_gate_status_and_outcome_semantics_distinguish_scientific_negative_results(contracts):
    semantics = contracts["run_spec"]["gate_semantics"]
    assert semantics["each_gate_record_fields"] == [
        "gate_id",
        "evaluation_status",
        "scientific_predicate",
        "applicability_reason",
        "detail",
    ]
    assert semantics["evaluation_status_values"] == ["PASS", "FAIL", "NOT_APPLICABLE"]
    assert semantics["outcome_gates"] == [
        "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE",
        "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE",
        "B4F-G13-A2-MIRROR-AND-BILATERAL-LOGIC",
    ]
    assert semantics["outcome_predicate_false_does_not_mean_validator_failure_if_evaluated_and_reported_without_credit"] is True
    assert semantics["no_event_makes_G10_G11_NOT_APPLICABLE_not_PASS"] is True
    assert semantics["unexpected_numerical_or_contract_failure_invalidates_campaign"] is True
    assert semantics["registered_case_geometry_domain_exit_is_a_valid_fail_closed_case_outcome"] is True


def test_gate_applicability_matrix_is_exact_for_all_g01_through_g17(contracts):
    matrix = contracts["run_spec"]["gate_semantics"]["per_gate_applicability"]
    assert list(matrix) == [
        "B4F-G01-SOURCE-AND-PARENT-RECURSIVE",
        "B4F-G02-A0-EXACT-REPLAY",
        "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE",
        "B4F-G04-ACTUATOR-WORK-LEDGER",
        "B4F-G05-P-H-CONSERVATION",
        "B4F-G06-ENERGY-MINUS-WORK-IDENTITY",
        "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION",
        "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL",
        "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE",
        "B4F-G10-EXACT-ZERO-JUMP-REMOVAL",
        "B4F-G11-INDEPENDENT-POST-RELEASE-5MS",
        "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE",
        "B4F-G13-A2-MIRROR-AND-BILATERAL-LOGIC",
        "B4F-G14-REGISTERED-DOMAIN-NO-POST-HOC-EXTENSION",
        "B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS",
        "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN",
        "B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY",
    ]
    for gate_id in ("B4F-G01-SOURCE-AND-PARENT-RECURSIVE", "B4F-G14-REGISTERED-DOMAIN-NO-POST-HOC-EXTENSION", "B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS", "B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY"):
        assert matrix[gate_id]["not_applicable_allowed"] is False
    assert matrix["B4F-G02-A0-EXACT-REPLAY"] == {
        "scope": "ALL_12_A0_PRE_POST_SLOTS_PLUS_GLOBAL_AGGREGATE",
        "not_applicable_allowed": False,
        "required_scientific_predicate": True,
    }
    a2_only_na = ["A2_NOT_EVALUATED_NO_A1_PARENT"]
    for gate_id in (
        "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE",
        "B4F-G04-ACTUATOR-WORK-LEDGER",
        "B4F-G05-P-H-CONSERVATION",
        "B4F-G06-ENERGY-MINUS-WORK-IDENTITY",
        "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION",
        "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL",
        "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN",
    ):
        assert matrix[gate_id]["allowed_not_applicable_reasons"] == a2_only_na
    event_na = [
        "NO_FINITE_REMOVAL_EVENT",
        "A2_NOT_EVALUATED_NO_A1_PARENT",
        "CASE_TERMINATED_GEOMETRY_BEFORE_EVENT",
    ]
    assert matrix["B4F-G10-EXACT-ZERO-JUMP-REMOVAL"]["allowed_not_applicable_reasons"] == event_na
    assert matrix["B4F-G11-INDEPENDENT-POST-RELEASE-5MS"]["allowed_not_applicable_reasons"] == event_na
    assert contracts["run_spec"]["gate_semantics"][
        "any_not_applicable_reason_outside_the_exact_matrix_is_validator_failure"
    ] is True


def test_outcome_gate_matrix_preserves_negative_results_and_exact_na_counts(contracts):
    matrix = contracts["run_spec"]["gate_semantics"]["per_gate_applicability"]
    g09 = matrix["B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE"]
    assert g09["allowed_not_applicable_reasons"] == [
        "A2_NOT_EVALUATED_NO_A1_PARENT",
        "CASE_TERMINATED_GEOMETRY_BEFORE_OUTCOME",
    ]
    assert g09["scientific_predicate_false_allowed_without_execution_failure"] is True
    g12 = matrix["B4F-G12-CROSS-INTEGRATOR-CONVERGENCE"]
    assert g12["allowed_not_applicable_reasons"] == [
        "NO_PAIRED_FINITE_REFERENCE_EVENT",
        "REFERENCE_CASE_GEOMETRY_DOMAIN_EXIT",
    ]
    assert g12["scientific_predicate_false_allowed_without_execution_failure"] is True
    assert g12["both_acquisition_and_removal_time_differences_must_be_le_0p00025_s"] is True
    g13 = matrix["B4F-G13-A2-MIRROR-AND-BILATERAL-LOGIC"]
    assert g13["allowed_not_applicable_reasons"] == ["NO_REFERENCE_ELIGIBLE_A1_PARENT"]
    assert g13["no_parent_requires_exactly_24_slot_NA_records_plus_12_pair_NA_records_plus_one_global_NA"] is True
    assert g13["scientific_predicate_false_allowed_without_execution_failure"] is True


def test_selector_reports_only_a_registered_discrete_observation(contracts):
    selector = contracts["run_spec"]["selector"]
    assert selector["reported_label"] == (
        "lowest_tested_reachable_alpha_in_registered_discrete_grid"
    )
    assert selector["minimum_required_force_or_work_claim"] is False
    assert selector["interpolation_or_inverse_threshold_estimation"] is False
    assert selector["no_eligible_level_status"] == (
        "NOT_OBSERVED_IN_REGISTERED_SYNTHETIC_COMMAND_DOMAIN"
    )
    assert selector["no_eligible_level_is_global_unreachability"] is False


def test_reference_eligibility_requires_paired_reference_success(contracts):
    eligibility = contracts["run_spec"]["reference_eligibility"]
    assert eligibility["reference_lanes"] == ["RK4_REFERENCE", "MIDPOINT_REFERENCE"]
    assert eligibility["both_reference_cases_must_have_finite_bilateral_removal_and_post_release_pass"] is True
    assert eligibility["acquisition_event_time_difference_s_max"] == 0.00025
    assert eligibility["removal_event_time_difference_s_max"] == 0.00025
    provenance = eligibility["event_provenance_required"]
    assert "lane-specific fresh-event source record" in provenance
    assert "earliest-event certificate hash" in provenance
    assert "numeric agreement alone is insufficient" in provenance
    assert "forced/shared provenance fails G12" in provenance
    assert "not eligible" in eligibility["one_reference_success_only"]
    assert eligibility["neither_reference_success"] == (
        "level not eligible; G12 reason NO_PAIRED_FINITE_REFERENCE_EVENT"
    )
    assert "never hardware replicates" in eligibility["coarse_and_fine_lanes"]


def test_evidence_schema_preserves_native_arrays_units_and_event_provenance(contracts):
    schema = contracts["schema"]
    assert schema["canonical_json"] == {
        "encoding": "UTF-8",
        "key_order": "sorted",
        "separators": "comma_colon",
        "allow_nan": False,
        "line_ending": "LF",
        "terminal_newline": True,
    }
    assert schema["npz_policy"]["allow_pickle"] is False
    assert schema["npz_policy"]["object_or_string_arrays_forbidden"] is True
    active = schema["active_npz_arrays"]
    assert active["service_state_29"].startswith("float64[N,29]")
    assert active["target_state_13"].startswith("float64[N,13]")
    assert active["command_Q_14"].startswith("float64[N,14]")
    assert active["signed_W_act_J"] == "float64[N] J"
    assert active["stage_gap_jacobian_P"] == "float64[S,2,2] dimensionless"
    assert active["stage_domain_and_sign_pass"] == "bool[S]"
    post = schema["post_release_npz_arrays_if_event"]
    assert post["post_service_state_29"].startswith("float64[M,29]")
    assert post["post_target_state_13"].startswith("float64[M,13]")
    assert post["post_stage_gap_jacobian_P"] == "float64[U,2,2] dimensionless"
    assert post["post_stage_domain_and_sign_pass"] == "bool[U]"
    assert schema["event_provenance_required_fields"] == [
        "lane_id",
        "fresh_b3_reconstruction",
        "first_qualifying_event_index",
        "acquisition_time_s",
        "acquisition_certificate_sha256",
        "clearance_certificate_sha256",
        "removal_time_s",
    ]
