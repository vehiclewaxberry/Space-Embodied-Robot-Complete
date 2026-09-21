from __future__ import annotations

import validate_phase_b4g_r1_contract as validator


def test_all_declared_upstream_sources_byte_match(bindings):
    result = validator.verify_bound_sources(bindings)
    assert result["pass"] is True
    assert len(result["records"]) == 9


def test_new_264_file_inventory_root_is_exact(bindings):
    result = validator.recompute_raw_inventory(bindings)
    assert result["pass"] is True
    assert (result["json_count"], result["npz_count"], result["file_count"]) == (144, 120, 264)
    assert result["canonical_sha256"] == "916F395EFEEEE3C234C7D3F361BFFB6134D060577A05ADEE0166F8F19CD43DD5"


def test_registered_schedule_and_conditional_a2_are_exact(raw_analysis):
    assert raw_analysis["schedule"]["slot_count"] == 144
    assert raw_analysis["schedule"]["slots_sha256"] == "21642ED06620E589ABB854CCFE936EC2C84D9571ACACA86F690ACC5DB2D78137"
    assert raw_analysis["raw_execution"]["status_counts"] == {
        "EXECUTED_FRESH_REGISTERED_SLOT": 120,
        "NOT_EVALUATED_NO_A1_SUCCESS": 24,
    }
    assert raw_analysis["raw_execution"]["a2_metadata_without_npz_count"] == 24


def test_only_slots_82_84_88_fail_g06(raw_analysis):
    assert raw_analysis["raw_execution"]["numeric_failed_slots"] == [82, 84, 88]
    assert raw_analysis["raw_execution"]["metadata_failure_pairs"] == [
        {"slot_index": 82, "gate_id": "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"},
        {"slot_index": 84, "gate_id": "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"},
        {"slot_index": 88, "gate_id": "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"},
    ]
    assert raw_analysis["raw_execution"]["failed_cases_max_stored_vs_T_minus_W_recompute_difference_J"] <= 1e-18
    assert raw_analysis["raw_execution"]["all_executed_max_stored_vs_T_minus_W_recompute_difference_J"] <= 2e-12


def test_midpoint_empirical_order_is_second_order(raw_analysis, closure_contract):
    expected = closure_contract["g06_failure_closure"]["midpoint_alpha16_empirical_orders"]
    assert abs(raw_analysis["g06"]["empirical_order_exact_min"] - expected["exact_min"]) <= 1e-12
    assert abs(raw_analysis["g06"]["empirical_order_exact_max"] - expected["exact_max"]) <= 1e-12
    assert expected["reported_two_decimal_range"] == [2.01, 2.08]


def test_g04_contract_divergence_is_preserved(raw_analysis, closure_contract):
    split = raw_analysis["g04_divergence"]
    assert split["run_spec_has_terminal_quadrature_acceptance"] is True
    assert split["run_spec_mentions_cumulative_work_error"] is False
    assert split["validator_requires_cumulative_work_error"] is True
    assert closure_contract["g04_runner_validator_divergence"]["silent_deletion_of_validator_check_authorized"] is False


def test_g12_has_no_eligible_parent(raw_analysis):
    g12 = raw_analysis["g12"]
    assert g12["paired_finite_count"] == 9
    assert g12["paired_scientific_predicate_false_count"] == 9
    assert g12["unpaired_count"] == 9
    assert g12["eligible_level_count"] == 0
    assert g12["selected_parent_level"] is None
    assert g12["removal_time_substantive_exceedance_count"] == 2
    assert g12["removal_time_binary_boundary_case_count"] == 1


def test_original_b4g_credit_remains_absent(raw_analysis):
    assert raw_analysis["original_credit"] == {
        "invalidation_active": True,
        "supersession_active": True,
        "replacement_campaign_summary": None,
        "formal_final_artifacts_absent_count": 9,
        "formal_final_artifacts_expected_absent_count": 9,
    }
