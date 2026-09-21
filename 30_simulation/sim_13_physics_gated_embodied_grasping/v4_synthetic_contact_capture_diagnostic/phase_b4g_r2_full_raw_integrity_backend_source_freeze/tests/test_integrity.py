from __future__ import annotations

import sys

import numpy as np

from r2_full_integrity.fixture_factory import write_technical_fixture
from r2_full_integrity.integrity import (
    G03, G04, G05, G06, G07, G08, G09, G10, G11, G16,
    evaluate_full_raw_integrity,
)


def _evaluate(tmp_path, **kwargs):
    case, context = write_technical_fixture(tmp_path, **kwargs).load()
    return evaluate_full_raw_integrity(case, context)


def test_nominal_fixture_recomputes_every_gate_without_credit(tmp_path) -> None:
    result = _evaluate(tmp_path)
    assert result["full_gate_set_recomputed"] is True
    assert result["technical_fixture_full_raw_integrity_predicate_pass"] is True
    assert result["passed"] is False
    assert result["trajectory_count"] == 0
    assert set(result["gate_records"]) == {G03, G04, G05, G06, G07, G08, G09, G10, G11, G16}
    assert all(row["scientific_predicate"] is True for row in result["gate_records"].values())
    for field in (
        "r2_numerical_preflight_executed", "current_system_bound", "formal_nc19_credit",
        "scientific_credit", "owner_authorized", "production_credit",
        "release_authorized", "next_stage_authorized",
    ):
        assert result[field] is False
    assert not any(
        name.endswith("b4g_solver") or ".b4g_solver." in name
        or name.endswith("b4_solver") or ".b4_solver." in name
        or name.endswith("b3_contact") or ".b3_contact." in name
        for name in sys.modules
    )


def test_g03_kills_non_p_generalized_force(tmp_path) -> None:
    def mutate(arrays):
        arrays["command_Q_14"][1, 0] = 1.0e-9

    result = _evaluate(tmp_path, array_mutator=mutate)
    assert result["gate_records"][G03]["scientific_predicate"] is False


def test_g05_kills_native_linear_momentum_drift(tmp_path) -> None:
    def mutate(arrays):
        arrays["total_linear_momentum_N_s"][-1, 0] = 2.0e-9
        arrays["post_total_linear_momentum_N_s"][:] = arrays["total_linear_momentum_N_s"][-1]

    result = _evaluate(tmp_path, array_mutator=mutate)
    assert result["gate_records"][G05]["scientific_predicate"] is False


def test_g07_kills_contact_force_but_does_not_relabel_ideal_power(tmp_path) -> None:
    def mutate(arrays):
        arrays["contact_force_N"][1] = 2.0e-12

    result = _evaluate(tmp_path, array_mutator=mutate)
    assert result["gate_records"][G07]["scientific_predicate"] is False
    assert result["gate_records"][G07]["detail"]["ideal_constraint_power_is_shared_integrity_precondition"] is True


def test_shared_ideal_power_precondition_is_not_silently_folded_into_g07(tmp_path) -> None:
    def mutate(arrays):
        arrays["ideal_constraint_power_W"][1] = 2.0e-10

    result = _evaluate(tmp_path, array_mutator=mutate)
    assert result["gate_records"][G07]["scientific_predicate"] is True
    assert result["shared_integrity_preconditions"]["active_ideal_constraint_power_pass"] is False
    assert result["technical_fixture_full_raw_integrity_predicate_pass"] is False


def test_g08_kills_command_profile_drift(tmp_path) -> None:
    def mutate(arrays):
        arrays["command_Q_14"][2, 12] += 1.0e-9

    result = _evaluate(tmp_path, array_mutator=mutate)
    assert result["gate_records"][G08]["scientific_predicate"] is False


def test_g09_ignores_sidecar_as_oracle_and_kills_raw_clearance_break(tmp_path) -> None:
    def mutate(arrays):
        arrays["left_gap_m"][-2] = 0.0

    result = _evaluate(tmp_path, array_mutator=mutate)
    assert result["gate_records"][G09]["scientific_predicate"] is False
    assert result["gate_records"][G09]["detail"]["sidecar_outcome_used_as_oracle"] is False


def test_g10_kills_exact_state_mapping_jump_at_raw_event_index(tmp_path) -> None:
    def mutate(arrays):
        arrays["post_service_state_29"][0, 0] += 1.0e-9

    result = _evaluate(tmp_path, array_mutator=mutate)
    assert result["gate_records"][G10]["scientific_predicate"] is False


def test_g11_kills_compact_parent_terminal_mismatch(tmp_path) -> None:
    def mutate(parent):
        parent["terminal_service_state_29"][0] += 2.0e-12

    result = _evaluate(tmp_path, parent_mutator=mutate)
    assert result["gate_records"][G11]["scientific_predicate"] is False
    assert result["gate_records"][G11]["detail"]["parent_trace_crosscheck"]["parent_source_execution_credit"] is False


def test_g16_kills_stored_stage_jacobian_self_consistency_attack(tmp_path) -> None:
    def mutate(arrays):
        arrays["stage_gap_jacobian_P"][1, 0, 0] += 1.0e-6

    result = _evaluate(tmp_path, array_mutator=mutate)
    assert result["gate_records"][G16]["scientific_predicate"] is False


def test_g04_g06_are_raw_recomputed_not_upstream_boolean_inputs(tmp_path) -> None:
    result = _evaluate(tmp_path)
    assert result["gate_records"][G04]["detail"]["scientific_predicate"] is True
    assert result["gate_records"][G06]["detail"]["scientific_predicate"] is True
    assert "gate_predicates" not in result
    assert "selector_case_integrity_pass" not in result
