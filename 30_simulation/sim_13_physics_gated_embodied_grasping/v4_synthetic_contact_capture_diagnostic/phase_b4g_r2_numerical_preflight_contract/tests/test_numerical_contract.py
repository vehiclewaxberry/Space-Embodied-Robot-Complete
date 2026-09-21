from __future__ import annotations

import json
import math

from conftest import canonical_hash, has_null_leaf, load_contract
from validate_phase_b4g_r2_contract import evaluate_direct_order_triplet


def _numerical() -> dict:
    return load_contract("PHASE_B4G_R2_NUMERICAL_ACCEPTANCE_V1.json")


def test_g04_runner_validator_rule_is_one_exact_contract() -> None:
    g04 = _numerical()["g04_unified_work_rule"]
    assert g04["rule_id"] == g04["runner_rule_id_required"] == g04["validator_rule_id_required"]
    assert g04["W_act_initial_exact"] == 0.0
    assert g04["sample_power_absolute_tolerance_W"] == g04["stage_power_absolute_tolerance_W"] == 1e-14
    assert g04["sample_power_relative_tolerance"] == g04["stage_power_relative_tolerance"] == 0.0
    assert g04["cumulative_max_abs_error_limit_J"] == g04["terminal_native_abs_error_limit_J"] == 1e-7
    assert g04["refinement_slack_J"] == 1e-15
    assert g04["finite_removal_post_conditions"]["post_W_exactly_constant_and_equal_to_active_terminal"] is True
    assert g04["required_report_fields"] == g04["runner_required_report_fields"] == g04["validator_required_report_fields"]
    assert canonical_hash(g04["required_report_fields"]) == "D4A33853CCC0D45CE894B37F94F56CF6526F9B8D2E7BF59CCCE4FFDD8D076C0F"
    assert g04["pass_expression"] == g04["runner_pass_expression_required"] == g04["validator_pass_expression_required"]
    assert canonical_hash(g04["pass_expression"]) == "67547F8BF742182E9A8DB91C23BD654A52EA64FA3DCDA10712C8978ECC4B753C"
    assert g04["finite_removal_post_pass_expression"] in g04["pass_expression"]
    assert "for every saved post sample j and k=0..13" in g04["finite_removal_post_pass_expression"]
    assert g04["W_act_equal_to_delta_T_identity_forbidden"] is True


def test_g04_and_g06_use_direct_error_ratio_order() -> None:
    numerical = _numerical()
    order = numerical["g04_unified_work_rule"]["empirical_order"]
    assert order["p_CF"] == "log2(e_0.25ms/e_0.125ms)"
    assert order["p_FR"] == "log2(e_0.125ms/e_0.0625ms)"
    assert order["p_min"] == 1.8
    assert order["floor_resolution_scope"] == "FINE_AND_REFERENCE"
    g06 = numerical["g06_energy_minus_work_rule"]
    assert g06["empirical_order_formula"].startswith("use B4G_R2_TOTAL_DIRECT_ERROR_RATIO_ORDER_V1")
    assert g06["midpoint_p_min"] == 1.8
    assert g06["rk4_p_min"] == 3.0
    assert g06["active_max_abs_limit_J"] == 1e-7
    zero = evaluate_direct_order_triplet((0.0, 0.0, 0.0), floor_J=2e-12, p_min=1.8, floor_scope="FINE_AND_REFERENCE")
    exact_zero = evaluate_direct_order_triplet((4e-9, 1e-9, 0.0), floor_J=2e-12, p_min=1.8, floor_scope="FINE_AND_REFERENCE")
    floor_limit = evaluate_direct_order_triplet((1e-5, 5e-11, 0.0), floor_J=1e-10, p_min=3.0, floor_scope="ALL_THREE")
    regression = evaluate_direct_order_triplet((0.0, 1e-5, 1e-6), floor_J=1e-10, p_min=1.8, floor_scope="FINE_AND_REFERENCE")
    invalid_nonfinite = evaluate_direct_order_triplet((float("nan"), 1.0, 0.1), floor_J=1e-10, p_min=1.8, floor_scope="FINE_AND_REFERENCE")
    invalid_schema = evaluate_direct_order_triplet("bad", floor_J=1e-10, p_min=1.8, floor_scope="FINE_AND_REFERENCE")
    assert zero["passed"] is True and zero["category"] == "OVERALL_FLOOR_RESOLVED"
    assert exact_zero["passed"] is True and exact_zero["FR"]["order_status"] == "EXACT_ZERO_FINE_POSITIVE_ORDER_LIMIT"
    assert math.isclose(exact_zero["CF"]["order_value"], 2.0, rel_tol=0.0, abs_tol=1e-15)
    assert floor_limit["passed"] is True and floor_limit["CF"]["order_status"] == "FINE_FLOOR_RESOLVED_POSITIVE_ORDER_LIMIT"
    assert regression["passed"] is False and regression["CF"]["order_status"] == "NOT_EVALUATED_REGRESSION_FROM_FLOOR"
    assert invalid_nonfinite["category"] == invalid_schema["category"] == "INVALID_INPUT_NONFINITE_NEGATIVE_OR_SCHEMA"
    assert not has_null_leaf((zero, exact_zero, floor_limit, regression, invalid_nonfinite, invalid_schema))
    json.dumps((zero, exact_zero, floor_limit, regression, invalid_nonfinite, invalid_schema), allow_nan=False)


def test_fresh_alpha16_uses_full_legacy_gate_ids() -> None:
    rule = _numerical()["fresh_alpha16_propagation_rule"]
    assert len(rule["required_true_gate_ids"]) == 10
    assert all(gate.startswith("B4F-G") for gate in rule["required_true_gate_ids"])
    assert "B4F-G04-ACTUATOR-WORK-LEDGER" in rule["required_true_gate_ids"]
    assert "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN" in rule["required_true_gate_ids"]
    assert rule["G04_and_G06_each_case_limit_J"] == 1e-7


def test_common_propagation_has_method_specific_contraction_and_no_credit() -> None:
    rule = _numerical()["common_propagation_convergence_rule"]
    assert math.isclose(rule["midpoint_contraction_max"], 2.0 ** (-1.8), rel_tol=0.0, abs_tol=1e-16)
    assert rule["midpoint_contraction_formula"] == "2^(-1.8)"
    assert 0.295 <= 0.3 and 0.295 > rule["midpoint_contraction_max"]
    assert rule["rk4_contraction_max"] == 0.125
    assert rule["midpoint_p_min"] == 1.8
    assert rule["rk4_p_min"] == 3.0
    assert rule["shared_removal_time_comparison"] is False
    assert rule["G12_credit"] is False
    assert rule["selector_input"] is False
    assert "D_FR_midpoint/(2^1.8-1)" in rule["finest_cross_method_rule"]
    assert "D_FR_rk4/(2^3.0-1)" in rule["finest_cross_method_rule"]


def test_g12_aggregate_means_complete_evaluation_not_all_true() -> None:
    g12 = _numerical()["g12_reference_event_and_signed_work_preflight"]
    assert g12["level_count"] == 18
    assert g12["reference_lanes"] == ["RK4_H_MS_0P0625", "MIDPOINT_H_MS_0P0625"]
    assert g12["acquisition_event_time_difference_s_max"] == 0.00025
    assert g12["removal_event_time_difference_s_max"] == 0.00025
    assert g12["aggregate_requires_all_scientific_predicates_true"] is False
    assert g12["aggregate_rule_contract_frozen"] is True
    assert "NOT_APPLICABLE" in g12["neither_reference_finite_rule"]


def test_units_keep_energy_and_power_distinct() -> None:
    units = _numerical()["unit_contract"]
    assert units["energy_residual_margin_and_work"] == "J"
    assert "J/s" in units["power"] or "W" in units["power"]
    assert units["energy_gate_must_not_be_reported_as_power_margin"] is True
