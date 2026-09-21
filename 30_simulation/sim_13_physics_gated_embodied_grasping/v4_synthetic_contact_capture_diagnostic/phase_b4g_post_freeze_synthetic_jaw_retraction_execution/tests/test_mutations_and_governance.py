from __future__ import annotations

import hashlib
import json

import pytest


PARENT_IDS = [f"B4FNC{i:02d}" for i in range(1, 23)]
COUNTS = [1, 2, 12, 2, 1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 2, 2, 2, 1, 10, 11, 6, 2]


def test_mutation_harness_registers_exactly_22_parents_and_65_subvariants(contracts):
    mutations = contracts["mutations"]
    assert mutations["scope"] == "REAL_RAW_ARTIFACT_OR_EXECUTED_PATH_MUTATIONS_ONLY"
    assert mutations["required_parent_ids"] == PARENT_IDS
    assert mutations["subvariant_counts_by_parent"] == COUNTS
    assert mutations["total_subvariants"] == sum(COUNTS) == 65
    assert len(mutations["variants"]) == 22
    assert [row["count"] for row in mutations["variants"]] == COUNTS
    for parent_id, row in zip(PARENT_IDS, mutations["variants"], strict=True):
        assert row["id"].startswith(parent_id + "_")
        assert row["count"] >= 1
        assert row["mutation"]
        assert row["expected_gate"].startswith("B4F-G")


def test_each_mutation_receipt_proves_real_unique_kill(contracts):
    mutations = contracts["mutations"]
    assert mutations["each_receipt_requires"] == [
        "nominal_input_sha256",
        "mutant_input_sha256",
        "real_path_hit",
        "expected_gate",
        "actual_failed_gate",
        "nominal_gate_sha256",
        "mutant_gate_sha256",
        "killed",
    ]
    assert mutations["dictionary_flag_only_mutation_forbidden"] is True
    assert mutations["all_65_subvariants_must_be_unique_hit_and_killed"] is True


def test_finite_event_mutation_fixture_cannot_gain_main_or_physical_credit(contracts):
    harness = contracts["mutations"]["finite_event_harness"]
    assert harness["id"] == "ALGORITHM_ONLY_FORCED_NONTRIGGER_MUTATION_HARNESS"
    assert harness["allowed_for"] == [
        "B4FNC07",
        "B4FNC08",
        "B4FNC11",
        "B4FNC12",
        "B4FNC13",
        "B4FNC14",
    ]
    assert harness["a1_or_b3_main_trigger_credit"] is False
    assert harness["physical_current_or_formal_credit"] is False


def test_finite_event_dependent_mutations_fail_closed_without_nonzero_work_event(contracts):
    harness = contracts["mutations"]["finite_event_harness"]
    assert harness["force_pulse"] == {
        "alpha_left": 0.5,
        "alpha_right": 0.5,
        "T_cmd_s": 0.0005,
        "start": "fixture acquisition",
        "profile": "same sin-squared command",
        "must_end_before_clearance_dwell": True,
    }
    precondition = harness["precondition"]
    assert "forced nontrigger path" in precondition
    assert "finite event" in precondition
    assert "abs(W_act_at_removal)>1e-12_J" in precondition
    assert "otherwise mutation audit fails closed" in precondition


def test_mutations_cover_schedule_domain_physics_hybrid_and_claim_boundaries(contracts):
    rows = {row["id"].split("_", 1)[0]: row for row in contracts["mutations"]["variants"]}
    assert rows["B4FNC03"]["count"] == 12
    assert "each Q index 0..11" in rows["B4FNC03"]["mutation"]
    assert rows["B4FNC16"]["count"] == 2
    assert "alpha=32" in rows["B4FNC16"]["mutation"]
    assert "T_cmd=0.04_s" in rows["B4FNC16"]["mutation"]
    assert rows["B4FNC19"]["count"] == 10
    assert rows["B4FNC20"]["count"] == 11
    assert rows["B4FNC21"]["count"] == 6
    assert "clipping and extrapolation" in rows["B4FNC21"]["mutation"]
    assert rows["B4FNC22"]["count"] == 2


def test_mutation_targets_and_amplitudes_are_deterministic_and_complete(contracts):
    targets = contracts["mutations"]["deterministic_targets_and_amplitudes"]
    assert targets["default_registered_forced_slot"] == (
        "RK4_REFERENCE__A1__ALPHA_2__TCMD_MS_10"
    )
    assert targets["a0_slot"] == "RK4_REFERENCE__A0__PRE"
    assert targets["force_injection_N"] == contracts["reference_force"][
        "individual_finger_reference_force_N"
    ]
    assert targets["opening_sign_mutants_left_right"] == [[-1, 1], [1, -1]]
    assert targets["work_multipliers"] == {"omitted": 0.0, "double_counted": 2.0}
    assert len(targets["P_domain_mutants"]) == 6
    assert targets["P_domain_mutants"][-2:] == [
        {"path": "CLIP_TO_UPPER_BOUND"},
        {"path": "EXTRAPOLATE_AFTER_UPPER_BOUND"},
    ]
    assert len(targets["reporting_mutants"]) == 2


@pytest.mark.parametrize(
    "fixture_key,expected_sha",
    [
        (
            "single_side_classifier_fixture",
            "CDE0554B08D4213E201526E740DC1EF75FBD9E26BEFEAEEF77CFDDB436E72902",
        ),
        (
            "endpoint_only_classifier_fixture",
            "21FDFEACE87FEE2945F44BEB46444F57276BDE178D174645BF3B76DC180C74EF",
        ),
    ],
)
def test_classifier_fixture_payload_hash_is_canonical_and_frozen(
    contracts, fixture_key, expected_sha
):
    fixture = contracts["mutations"]["deterministic_targets_and_amplitudes"][fixture_key]
    payload = json.dumps(
        fixture["canonical_payload"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    actual = hashlib.sha256(payload).hexdigest().upper()
    assert fixture["canonical_payload_sha256"] == actual == expected_sha


def test_nc09_single_side_fixture_separates_bilateral_from_mutant_logic(contracts):
    fixture = contracts["mutations"]["deterministic_targets_and_amplitudes"][
        "single_side_classifier_fixture"
    ]
    payload = fixture["canonical_payload"]
    assert payload["left_gap_m"] == [2e-6, 2e-6, 2e-6]
    assert payload["right_gap_m"] == [0.0, 0.0, 0.0]
    assert payload["left_gap_rate_m_s"] == payload["right_gap_rate_m_s"] == [0.0] * 3
    assert fixture["right_only_variant"] == "exact left-right swap"
    assert fixture["nominal_bilateral_result"] == "NO_FINITE_EVENT"
    assert fixture["mutant_single_side_result"] == "FINITE_EVENT"


def test_nc10_endpoint_only_fixture_contains_certified_interior_failure(contracts):
    fixture = contracts["mutations"]["deterministic_targets_and_amplitudes"][
        "endpoint_only_classifier_fixture"
    ]
    a, b, c, d = fixture["left_gap_Hermite_coefficients_m"]
    s = fixture["interior_minimum_at_normalized_s"]
    computed_minimum = ((a * s + b) * s + c) * s + d
    assert computed_minimum == pytest.approx(
        fixture["interior_minimum_gap_m"], rel=0.0, abs=1e-18
    )
    assert d == pytest.approx(2e-6, abs=1e-20)
    assert a + b + c + d == pytest.approx(2e-6, abs=1e-20)
    assert computed_minimum < 1e-6
    assert fixture["nominal_all_root_result"] == "NO_FINITE_EVENT"
    assert fixture["mutant_endpoint_only_result"] == "FINITE_EVENT"


def test_nc12_energy_return_uses_native_mass_metric_and_deterministic_root(contracts):
    rule = contracts["mutations"]["deterministic_targets_and_amplitudes"][
        "nc12_energy_injection_rule"
    ]
    assert "native 20D z" in rule
    assert "block-diagonal service-target mass M" in rule
    assert "unit service-left-P velocity basis e12" in rule
    assert "a=0.5*d^T*M*d" in rule
    assert "b=z^T*M*d" in rule
    assert "a*beta^2+b*beta-D_switch=0" in rule
    assert "real beta with smallest abs value, ties choose positive" in rule
    assert "record both roots and exact achieved kinetic increment" in rule


def test_consumed_sign_mutation_preserves_raw_sign_and_must_fail_g16(contracts):
    row = contracts["mutations"]["variants"][3]
    assert row["id"] == "B4FNC04_OPENING_SIGN_REVERSED"
    assert "sigma consumed by the actual command path" in row["mutation"]
    assert "preserving the raw positive derivative" in row["mutation"]
    assert "consumed, recomputed and registered signs" in row["mutation"]
    assert row["expected_gate"] == "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN"


def test_g12_mutation_replaces_provenance_and_not_only_numeric_time(contracts):
    row = contracts["mutations"]["variants"][14]
    assert row["id"] == "B4FNC15_SHARED_EVENT_TIME_FORCED"
    assert row["count"] == 2
    assert "time and provenance" in row["mutation"]
    assert "lane-specific earliest-event certificate" in row["mutation"]
    assert "even if numeric delta becomes zero" in row["mutation"]
    assert row["expected_gate"] == "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE"


def test_a2_mirror_mutations_have_frozen_noncredit_fallback_when_no_parent(contracts):
    targets = contracts["mutations"]["deterministic_targets_and_amplitudes"]
    fallback = targets["nc17_no_parent_harness"]
    assert fallback == {
        "id": "ALGORITHM_ONLY_A2_DETECTOR_HARNESS",
        "parent_alpha": 2.0,
        "parent_T_cmd_s": 0.01,
        "all_six_lanes_required": True,
        "used_only_if_no_reference_eligible_A1_parent": True,
        "a1_a2_or_physical_credit": False,
    }
    row = contracts["mutations"]["variants"][16]
    assert row["id"] == "B4FNC17_A2_LEFT_RIGHT_MIRROR_BROKEN"
    assert "if campaign A2 is not evaluated" in row["mutation"]
    assert "frozen non-credit A2 detector harness" in row["mutation"]


def test_governance_mutation_field_lists_match_governance_contract(contracts):
    targets = contracts["mutations"]["deterministic_targets_and_amplitudes"]
    required_false = contracts["governance"]["required_false"]
    required_null = contracts["governance"]["required_null_physical_inputs"]
    assert targets["nc19_required_false_fields"] == [
        "physical_actuator_force_identified",
        "physical_release_implemented",
        "held_capture_passed",
        "grasp_success_claimed",
        "current_system_bound",
        "formal_nc19_credit",
        "owner_authorized",
        "production_ready",
        "release_authorized",
        "next_stage_authorized",
    ]
    assert all(field in required_false for field in targets["nc19_required_false_fields"])
    assert targets["nc20_required_null_fields"] == required_null


def test_allowed_true_capabilities_are_exact_and_evidence_conditional(contracts):
    governance = contracts["governance"]
    assert governance["allowed_true_capabilities"] == [
        "b4g_workflow_authorized",
        "b4g_execution_spec_frozen",
        "b4g_solver_implemented",
        "b4g_campaign_executed",
        "parent_b4f_recursively_verified",
        "registered_domain_evaluated",
        "a0_replay_verified",
        "registered_negative_controls_executed",
        "b4g_execution_audited",
        "synthetic_reachability_observed",
        "lowest_tested_reachable_alpha_reported",
        "algorithm_only_case_removal_executed",
        "a2_stress_lane_evaluated",
    ]
    conditional = governance["conditionally_true_only_if_raw_evidence_supports"]
    assert conditional == [
        "synthetic_reachability_observed",
        "lowest_tested_reachable_alpha_reported",
        "algorithm_only_case_removal_executed",
        "a2_stress_lane_evaluated",
    ]
    assert set(conditional) <= set(governance["allowed_true_capabilities"])


def test_all_physical_current_formal_owner_and_claim_fields_are_required_false(contracts):
    required = contracts["governance"]["required_false"]
    assert set(required) == {
        "minimum_required_synthetic_force_identified",
        "physical_actuator_force_identified",
        "physical_actuator_timing_identified",
        "physical_release_implemented",
        "physical_recontact_implemented",
        "held_capture_passed",
        "grasp_success_claimed",
        "current_system_bound",
        "formal_nc19_credit",
        "owner_authorized",
        "production_ready",
        "release_authorized",
        "next_stage_authorized",
        "hardware_specification_released",
        "physical_gripper_stroke_identified",
        "measurement_uncertainty_model_available",
        "minimum_required_force_or_work_claimed",
        "continuous_threshold_or_interpolation_claimed",
        "global_unreachability_claimed",
        "statistical_population_inference_claimed",
    }
    assert all(value is False for value in required.values())


def test_all_physical_inputs_are_required_null(contracts):
    assert contracts["governance"]["required_null_physical_inputs"] == [
        "physical_left_actuator_force_capacity_N",
        "physical_right_actuator_force_capacity_N",
        "physical_opening_time_s",
        "physical_braking_time_s",
        "physical_motor_current_A",
        "physical_transmission_efficiency",
        "physical_contact_frame_left",
        "physical_contact_frame_right",
        "physical_lock_transform",
        "physical_retention_capacity_N",
        "physical_release_energy_J",
    ]


def test_formal_sim13_v2_hold_set_is_unchanged(contracts):
    assert contracts["governance"]["formal_sim13_v2_state_unchanged"] == {
        "passed": 15,
        "declared": 20,
        "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
    }


def test_memory_gate_is_not_applicable_and_no_override_is_used(contracts):
    expected = {
        "memory_gate_applicable": False,
        "memory_gate_passed": False,
        "owner_override_used": False,
        "classification": "DIAGNOSTIC_ONLY",
    }
    assert contracts["governance"]["memory_record_required"] == expected
    assert contracts["run_spec"]["memory"] == expected


def test_claim_rule_never_promotes_synthetic_result(contracts):
    rule = contracts["governance"]["claim_rule"]
    assert "observed registered discrete synthetic level" in rule
    for forbidden_claim in [
        "minimum force",
        "physical stroke",
        "actuator specification",
        "physical release",
        "current-system",
        "formal credit",
    ]:
        assert forbidden_claim in rule


def test_protected_asset_scope_is_exactly_bound_parents_and_local_forbidden_names(contracts):
    governance = contracts["governance"]
    assert governance["protected_asset_snapshot_scope"] == {
        "bound_parent_paths": "the exact 11 PHASE_B4G_SOURCE_BINDINGS_V1 sources",
        "local_forbidden_search_root": "this B4G package only",
        "unrelated_historical_repository_assets": (
            "diagnostic inventory only and not attributed to B4G"
        ),
    }
    policy = governance["forbidden_asset_policy"]
    assert "byte drift of any of the 11 bound parent assets" in policy
    assert "authorized B4G solver/tests/evidence/results creation is allowed" in policy
    assert "never delete or restore user assets" in policy
