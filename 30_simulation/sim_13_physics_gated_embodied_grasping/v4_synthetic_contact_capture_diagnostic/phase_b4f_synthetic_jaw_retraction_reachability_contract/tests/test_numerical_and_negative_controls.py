from __future__ import annotations

import pytest


EXPECTED_NC = [
    "B4FNC01_PARENT_SOURCE_BYTE_DRIFT",
    "B4FNC02_A0_NONZERO_FORCE",
    "B4FNC03_FORCE_OUTSIDE_P_CHANNELS",
    "B4FNC04_OPENING_SIGN_REVERSED",
    "B4FNC05_ACTUATOR_WORK_OMITTED",
    "B4FNC06_ACTUATOR_WORK_DOUBLE_COUNTED",
    "B4FNC07_WORK_RESET_AT_REMOVAL",
    "B4FNC08_COMMAND_ACTIVE_DURING_CLEARANCE_DWELL",
    "B4FNC09_SINGLE_SIDE_CLEARANCE_ACCEPTED",
    "B4FNC10_ENDPOINT_ONLY_CLEARANCE",
    "B4FNC11_REMOVAL_RESTORES_PRE_ACQUISITION_TWIST",
    "B4FNC12_REMOVAL_RETURNS_DISSIPATED_ENERGY",
    "B4FNC13_POST_RELEASE_TARGET_STILL_SNAPSHOT_DERIVED",
    "B4FNC14_POST_RELEASE_CONTACT_REACTIVATED",
    "B4FNC15_SHARED_EVENT_TIME_FORCED",
    "B4FNC16_PARAMETER_DOMAIN_EXTENDED_AFTER_RESULTS",
    "B4FNC17_A2_LEFT_RIGHT_MIRROR_BROKEN",
    "B4FNC18_SYNTHETIC_FORCE_PROMOTED_TO_HARDWARE_SPEC",
    "B4FNC19_REQUIRED_FALSE_AUTHORITY_TRUE",
    "B4FNC20_NULL_PHYSICAL_INPUT_ZERO_FILLED",
    "B4FNC21_P_STROKE_DOMAIN_EXIT_OR_CLIPPING",
    "B4FNC22_LOWEST_TESTED_PROMOTED_TO_MINIMUM_REQUIRED_FORCE",
]


@pytest.mark.parametrize("negative_control_id", EXPECTED_NC)
def test_future_negative_control_is_preregistered(contracts, negative_control_id):
    numerical = contracts["numerical"]
    assert negative_control_id in numerical["required_negative_controls"]
    assert numerical["all_negative_controls_must_mutate_real_raw_artifacts_or_executed_paths"] is True
    assert numerical["dictionary_flag_only_mutation_forbidden"] is True


def test_future_negative_controls_are_not_claimed_executed(contracts):
    governance = contracts["governance"]
    assert governance["scope"] == "CONTRACT_FREEZE_ONLY_NO_SOLVER_EXECUTION"
    assert governance["required_false"]["b4f_solver_implemented"] is False
    assert governance["required_false"]["b4f_campaign_executed"] is False


def test_gate_ids_are_complete_and_unique(contracts):
    gates = contracts["numerical"]["gate_ids"]
    assert len(gates) == 17
    assert len(set(gates)) == 17
    assert gates[0] == "B4F-G01-SOURCE-AND-PARENT-RECURSIVE"
    assert gates[-1] == "B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY"


def test_native_velocity_jump_tolerances_are_componentwise(contracts):
    jump = contracts["numerical"]["native_tolerances"]["removal_native_velocity_jump"]
    assert set(jump) == {
        "service_base_linear_m_s", "service_base_angular_rad_s", "service_R_joint_rad_s",
        "service_P_joint_m_s", "target_linear_m_s", "target_angular_rad_s",
    }
    assert set(jump.values()) == {1e-12}


def test_terminal_outcomes_preserve_claim_boundary(contracts):
    outcomes = contracts["numerical"]["terminal_outcomes"]
    assert outcomes["success"] == "REACHABLE_IN_REGISTERED_SYNTHETIC_COMMAND_DOMAIN"
    assert outcomes["no_observed_success"] == "NOT_OBSERVED_IN_REGISTERED_SYNTHETIC_COMMAND_DOMAIN"
    assert outcomes["success_is_physical_release_capability"] is False
    assert outcomes["no_observed_success_is_global_unreachability"] is False

