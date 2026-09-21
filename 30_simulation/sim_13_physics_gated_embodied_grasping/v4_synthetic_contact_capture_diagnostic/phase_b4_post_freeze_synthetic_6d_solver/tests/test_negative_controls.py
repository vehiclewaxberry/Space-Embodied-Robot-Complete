from __future__ import annotations

import pytest

import b4_solver.constraint_solver as solver


EXPECTED_IDS = [
    "B4NC01_SOURCE_BYTE_SHA_DRIFT", "B4NC02_TRIGGER_INDEX_CHERRY_PICK",
    "B4NC03_DUPLICATE_JC_ROW_RANK5_WITH_PINV_ATTEMPT", "B4NC04_L_COLUMN_RANK_LOSS",
    "B4NC05_ACQUISITION_PINV_OR_LSTSQ_CALL", "B4NC06_REMOVE_LENGTH_SCALING_D_EQUALS_I",
    "B4NC07_MIXED_UNIT_CONDITION_NUMBER_REPORTED", "B4NC08_AXIAL_MISSING_WRENCH_MISFORMULA",
    "B4NC09_CONTACT_AND_CONSTRAINT_SIMULTANEOUSLY_ACTIVE", "B4NC10_CONTACT_POTENTIAL_OMITTED",
    "B4NC11_CONTACT_POTENTIAL_DOUBLE_COUNTED", "B4NC12_PROJECTION_DISSIPATION_SIGN_FLIP",
    "B4NC13_TARGET_CHILD_MASS_OMITTED", "B4NC14_TARGET_CHILD_MASS_DOUBLE_COUNTED",
    "B4NC15_ACTIVE_INTERMEDIATE_LEDGER_MUTATION_WITH_GOOD_TERMINAL_LABEL",
    "B4NC16_REMOVAL_RESTORES_PRE_ACQUISITION_TWIST", "B4NC17_REMOVAL_ZEROES_TARGET_TWIST",
    "B4NC18_REMOVAL_RETURNS_DISSIPATED_ENERGY", "B4NC19_CLEARANCE_DWELL_NEGATIVE_GAP_INSERTION",
    "B4NC20_POST_REMOVAL_CONTACT_KERNEL_REACTIVATION", "B4NC21_PHYSICAL_OR_FORMAL_AUTHORITY_TRUE",
    "B4NC22_NULL_PHYSICAL_INPUT_ZERO_FILLED",
]


@pytest.fixture(scope="module")
def controls(primary_run):
    return solver.run_negative_controls(primary_run.acquisition, primary_run)


def test_negative_control_inventory_is_exact(controls):
    assert [item["id"] for item in controls] == EXPECTED_IDS


@pytest.mark.parametrize("control_id", EXPECTED_IDS)
def test_each_negative_control_is_killed_by_expected_gate(control_id, controls):
    item = next(value for value in controls if value["id"] == control_id)
    assert item["affected_path_hit"] is True
    assert item["killed"] is True
    assert item["expected_failed_check"] in item["actual_failed_checks"]
    assert item["nominal_sha256"] != item["mutant_sha256"]
    assert item["nominal_gate_output_sha256"] != item["mutant_gate_output_sha256"]
    assert item["mutation_level"] in ("REAL_RAW_ARTIFACT_OR_EXECUTED_PATH", "EVERY_INDIVIDUAL_RAW_GOVERNANCE_FIELD")


def test_nc21_mutates_all_required_false_fields(controls):
    item = next(value for value in controls if value["id"] == "B4NC21_PHYSICAL_OR_FORMAL_AUTHORITY_TRUE")
    assert item["actual_failed_checks"] == ["B4E-AUTHORITY"]
    assert item["subvariant_count"] == 8
    assert len({value["mutant_input_sha256"] for value in item["subvariants"]}) == 8
    assert all(value["killed"] for value in item["subvariants"])


def test_nc22_mutates_all_physical_null_fields(controls):
    item = next(value for value in controls if value["id"] == "B4NC22_NULL_PHYSICAL_INPUT_ZERO_FILLED")
    assert item["actual_failed_checks"] == ["B4E-NULL-ZEROFILL"]
    assert item["subvariant_count"] == 7
    assert len({value["mutant_input_sha256"] for value in item["subvariants"]}) == 7
    assert all(value["killed"] for value in item["subvariants"])


@pytest.mark.parametrize("control_id", [
    "B4NC03_DUPLICATE_JC_ROW_RANK5_WITH_PINV_ATTEMPT",
    "B4NC05_ACQUISITION_PINV_OR_LSTSQ_CALL",
    "B4NC09_CONTACT_AND_CONSTRAINT_SIMULTANEOUSLY_ACTIVE",
    "B4NC20_POST_REMOVAL_CONTACT_KERNEL_REACTIVATION",
])
def test_executed_path_mutants_are_not_gate_flag_mutations(control_id, controls):
    item = next(value for value in controls if value["id"] == control_id)
    assert item["mutation_level"] == "REAL_RAW_ARTIFACT_OR_EXECUTED_PATH"
    assert "actual" in item["mutated_path"] or "backend_calls" in item["mutated_path"]
