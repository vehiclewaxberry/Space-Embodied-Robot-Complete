from __future__ import annotations

import copy

from validate_phase_b4_contract import evaluate_contract_payloads


def _evaluate(model, governance, units, numerical, sources, *, verify_files=False):
    return evaluate_contract_payloads(
        copy.deepcopy(model),
        copy.deepcopy(governance),
        copy.deepcopy(units),
        copy.deepcopy(numerical),
        copy.deepcopy(sources),
        verify_files=verify_files,
    )


def test_nc_source_sha_byte_drift_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    mutated = copy.deepcopy(source_bindings)
    mutated["sources"][0]["sha256"] = "0" * 64
    checks = evaluate_contract_payloads(model_contract, governance_contract, units_ledger, numerical_contract, mutated, verify_files=True)
    assert checks["B4C-03"]["pass"] is False

    swapped = copy.deepcopy(source_bindings)
    first = next(row for row in swapped["sources"] if row["id"] == "digital_prototype_frame_tree")
    second = next(row for row in swapped["sources"] if row["id"] == "accepted_arm_urdf_read_only")
    first["path"], second["path"] = second["path"], first["path"]
    first["bytes"], second["bytes"] = second["bytes"], first["bytes"]
    first["sha256"], second["sha256"] = second["sha256"], first["sha256"]
    checks = _evaluate(model_contract, governance_contract, units_ledger, numerical_contract, swapped)
    assert checks["B4C-02"]["pass"] is False


def test_nc_trigger_cherry_pick_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    model = copy.deepcopy(model_contract)
    model["trigger_contract"]["reference_record_index"] = 206
    checks = _evaluate(model, governance_contract, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-05"]["pass"] is False


def test_nc_b3_rank6_rewrite_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    model = copy.deepcopy(model_contract)
    model["upstream_ruling"]["b3_grasp_map_rank"] = 6
    model["upstream_ruling"]["full_6d_wrench_span"] = True
    checks = _evaluate(model, governance_contract, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-04"]["pass"] is False
    assert checks["B4C-16"]["pass"] is False


def test_nc_axial_missing_wrench_misformula_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    model = copy.deepcopy(model_contract)
    model["wrench_and_momentum_semantics"]["synthetic_missing_sixth_wrench_scalar"] = "chi_missing=a_chord dot ell"
    checks = _evaluate(model, governance_contract, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-16"]["pass"] is False


def test_nc_unscaled_mixed_condition_number_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    numerical = copy.deepcopy(numerical_contract)
    numerical["rank_and_linear_solve"]["condition_number_whitelist"] = ["M_minus_unscaled"]
    checks = _evaluate(model_contract, governance_contract, units_ledger, numerical, source_bindings)
    assert checks["B4C-15"]["pass"] is False

    relaxed = copy.deepcopy(numerical_contract)
    relaxed["active_trajectory_native_unit_tolerances"]["pose_translation_m"] = 1e6
    checks = _evaluate(model_contract, governance_contract, units_ledger, relaxed, source_bindings)
    assert checks["B4C-25"]["pass"] is False


def test_nc_contact_constraint_double_activity_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    model = copy.deepcopy(model_contract)
    model["contact_to_constraint_switch"]["b3_contact_force_after_acquisition"] = "active"
    model["contact_to_constraint_switch"]["double_counting_contact_and_constraint"] = "allowed"
    checks = _evaluate(model, governance_contract, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-18"]["pass"] is False


def test_nc_contact_potential_omission_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    model = copy.deepcopy(model_contract)
    model["contact_to_constraint_switch"]["reference_left_contact_potential_at_t_a_minus_j"] = 0.0
    model["contact_to_constraint_switch"]["contact_potential_sum"] = "omitted"
    checks = _evaluate(model, governance_contract, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-18"]["pass"] is False

    wrong_identity = copy.deepcopy(model_contract)
    wrong_identity["contact_to_constraint_switch"]["switch_dissipation"] = "D_switch=1+2"
    wrong_identity["contact_to_constraint_switch"]["full_event_energy_identity"] = "D_B3_minus is mentioned but the identity is false"
    checks = _evaluate(wrong_identity, governance_contract, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-18"]["pass"] is False


def test_nc_nonzero_removal_impulse_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    model = copy.deepcopy(model_contract)
    model["release_contract"]["release_impulse_linear_N_s"] = 1e-4
    checks = _evaluate(model, governance_contract, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-20"]["pass"] is False


def test_nc_post_removal_contact_reactivation_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    model = copy.deepcopy(model_contract)
    model["release_contract"]["contact_kernel_after_removal"] = "re-enabled"
    checks = _evaluate(model, governance_contract, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-21"]["pass"] is False


def test_nc_current_or_formal_authority_true_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    governance = copy.deepcopy(governance_contract)
    governance["required_false"]["current_system_bound"] = True
    checks = _evaluate(model_contract, governance, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-26"]["pass"] is False

    builder = copy.deepcopy(governance_contract)
    builder["authorized_scope"]["invoke_unified_private_builder_or_generator"] = True
    checks = _evaluate(model_contract, builder, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-26"]["pass"] is False


def test_nc_null_physical_input_zero_fill_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    units = copy.deepcopy(units_ledger)
    physical = next(row for row in units["quantities"] if row["id"] == "physical_lock_transform")
    physical["estimate"] = 0.0
    physical["source"] = "zero_fill"
    checks = _evaluate(model_contract, governance_contract, units, numerical_contract, source_bindings)
    assert checks["B4C-24"]["pass"] is False


def test_nc_success_terminal_alias_is_rejected(model_contract, governance_contract, units_ledger, numerical_contract, source_bindings) -> None:
    model = copy.deepcopy(model_contract)
    model["state_machine"]["success_label"] = "GRASP_SUCCESS"
    model["state_machine"]["forbidden_states"].remove("GRASP_SUCCESS")
    checks = _evaluate(model, governance_contract, units_ledger, numerical_contract, source_bindings)
    assert checks["B4C-22"]["pass"] is False
