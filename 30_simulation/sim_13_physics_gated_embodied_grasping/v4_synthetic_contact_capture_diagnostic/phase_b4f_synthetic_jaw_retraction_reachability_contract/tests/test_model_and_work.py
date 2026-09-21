from __future__ import annotations

import pytest


def test_p_only_14d_effort_contract(contracts):
    equation = contracts["model"]["active_equation"]
    assert equation["Q_a_shape"] == 14
    assert equation["allowed_nonzero_indices_zero_based"] == [12, 13]
    assert equation["allowed_native_unit"] == "N"
    assert equation["all_base_and_R_joint_applied_efforts_exact_zero"] is True


def test_contact_constraint_mutual_exclusion(contracts):
    equation = contracts["model"]["active_equation"]
    assert equation["contact_kernel_enabled_while_synthetic_constraint_active"] is False
    assert equation["ideal_constraint_stored_energy_J"] == 0.0


@pytest.mark.parametrize("index,sign", [(0, 1), (1, 1)])
def test_opening_signs_are_registered_and_reverified(contracts, index, sign):
    sign_contract = contracts["model"]["sign_and_basis"]
    assert sign_contract["registered_opening_sign_vector_left_right"][index] == sign
    assert sign_contract["sign_must_be_reverified_from_raw_gap_jacobian_at_every_acquisition"] is True
    assert sign_contract["sign_must_remain_invariant_over_every_accepted_trajectory_sample"] is True


def test_force_reference_is_algorithm_only(contracts):
    force = contracts["model"]["reference_force_scaling"]
    assert force["classification"] == "ALGORITHM_ONLY_DIMENSIONAL_REFERENCE_NOT_ACTUATOR_SPECIFICATION"
    assert force["one_common_reference_force_for_all_integrators_blocks_and_treatments"] is True
    assert force["per_run_or_per_treatment_reference_force_recomputation_forbidden"] is True
    assert force["hardware_force_capacity_inferred"] is False


def test_command_profile_is_zero_during_removal_dwell(contracts):
    command = contracts["model"]["command_profile"]
    assert "sin(pi" in command["profile"]
    assert command["continuous_at_start_and_end"] is True
    assert command["command_must_be_exact_zero_through_clearance_dwell_and_at_removal"] is True
    assert command["post_release_applied_generalized_force"] == "exact_zero"


@pytest.mark.parametrize(
    "key,fragment",
    [
        ("instantaneous_power_W", "Q_P_left qdot_P_left"),
        ("signed_work_J", "integral"),
        ("primary_integration", "W_act_dot=P_act"),
        ("active_energy_identity", "-W_act"),
    ],
)
def test_signed_work_ledger_frozen(contracts, key, fragment):
    assert fragment in contracts["model"]["actuator_work_ledger"][key]


def test_work_is_not_reset_or_returned(contracts):
    ledger = contracts["model"]["actuator_work_ledger"]
    assert ledger["dissipated_energy_return_on_removal"] is False
    assert ledger["actuator_work_reset_on_removal"] is False


def test_zero_impulse_componentwise_removal(contracts):
    removal = contracts["model"]["removal_transition"]
    assert "componentwise copy" in removal["mapping"]
    assert removal["post_release_observation_s"] == 0.005
    assert removal["post_release_contact_kernel_enabled"] is False
    assert removal["post_release_actuator_generalized_force"] == "exact_zero"

