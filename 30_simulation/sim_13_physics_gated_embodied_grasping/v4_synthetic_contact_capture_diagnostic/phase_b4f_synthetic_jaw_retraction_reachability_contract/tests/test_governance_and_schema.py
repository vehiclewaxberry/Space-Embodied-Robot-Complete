from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "key",
    [
        "b4f_solver_implemented", "b4f_campaign_executed", "synthetic_reachability_passed",
        "minimum_required_synthetic_force_identified", "physical_actuator_force_identified",
        "physical_actuator_timing_identified", "physical_release_implemented",
        "physical_recontact_implemented", "held_capture_passed", "grasp_success_claimed",
        "current_system_bound", "formal_nc19_credit", "owner_authorized", "production_ready",
        "release_authorized", "next_stage_authorized", "hardware_specification_released",
        "physical_gripper_stroke_identified", "measurement_uncertainty_model_available",
    ],
)
def test_required_capability_remains_false(contracts, key):
    assert contracts["governance"]["required_false"][key] is False


@pytest.mark.parametrize(
    "key",
    [
        "physical_left_actuator_force_capacity_N", "physical_right_actuator_force_capacity_N",
        "physical_opening_time_s", "physical_braking_time_s", "physical_motor_current_A",
        "physical_transmission_efficiency", "physical_contact_frame_left",
        "physical_contact_frame_right", "physical_lock_transform", "physical_retention_capacity_N",
        "physical_release_energy_J",
    ],
)
def test_physical_input_is_required_null(contracts, key):
    assert key in contracts["governance"]["required_null_physical_inputs"]


def test_formal_sim13_state_is_unchanged(contracts):
    state = contracts["governance"]["formal_sim13_v2_state_unchanged"]
    assert state == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]}


def test_memory_is_diagnostic_only(contracts):
    memory = contracts["governance"]["memory_governance"]
    assert memory["unified_r2_or_v5_cad_memory_gate_applicable"] is False
    assert memory["memory_gate_credit_allowed"] is False
    assert memory["historical_owner_override_reuse_allowed"] is False
    assert memory["future_b4f_run_records_memory_as_diagnostic_only"] is True


def test_no_forbidden_artifact_exists(contracts, phase_root):
    names = {path.name for path in phase_root.rglob("*") if path.is_file()}
    forbidden = contracts["governance"]["forbidden_artifacts"]
    assert not any(name.endswith(".urdf") for name in names)
    for literal in forbidden[1:]:
        assert literal not in names


def test_contract_audit_allowed_true_is_exact(contracts):
    assert contracts["governance"]["allowed_true_after_contract_audit"] == [
        "b4f_contract_frozen", "b4f_contract_audited", "parent_b4e_recursively_verified"
    ]


def test_evidence_schema_is_self_excluding(contracts):
    schema = contracts["schema"]
    assert schema["self_exclusion"] == {
        "evidence_manifest_self_excluded": True,
        "terminal_manifest_self_excluded": True,
    }
    assert schema["publication_order"][-1] == "SIM13_V4B4F_CONTRACT_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"
    assert "implementation" in schema["claim_boundary"]


def test_result_rule_forbids_minimum_required_force(contracts):
    rule = contracts["governance"]["result_rule"]
    assert "lowest tested reachable level" in rule
    assert "never a minimum required force" in rule
    assert "physical actuator parameters" in rule

