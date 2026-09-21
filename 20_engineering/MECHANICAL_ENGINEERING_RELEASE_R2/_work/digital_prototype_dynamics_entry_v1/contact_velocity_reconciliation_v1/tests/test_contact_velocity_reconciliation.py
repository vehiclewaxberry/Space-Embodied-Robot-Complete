from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "CONTACT_VELOCITY_RECONCILIATION_CANDIDATE_V1.yaml"
EVALUATOR = ROOT / "evaluate_contact_velocity_reconciliation.py"

SPEC = importlib.util.spec_from_file_location("contact_velocity_evaluator", EVALUATOR)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def load_contract():
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def evaluate_mutation(tmp_path: Path, mutation):
    data = copy.deepcopy(load_contract())
    mutation(data)
    path = tmp_path / "mutated_contract.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return MODULE.evaluate(path)


def criterion(gate, criterion_id):
    return next(item for item in gate["criteria"] if item["id"] == criterion_id)


def test_nominal_reconciliation_passes_with_physical_hold():
    gate, passed = MODULE.evaluate(CONTRACT)
    assert passed is True
    assert gate["criteria_passed"] == 9
    assert gate["criteria_total"] == 9
    assert gate["gate"] == "PASS_WITH_PHYSICAL_HOLD"
    assert gate["original_0p05_current_contact_consumer"] == "REJECT"
    assert gate["reduced_0p005_design_diagnostic_consumer"] == "ACCEPT_BOUNDED_DIAGNOSTIC_ONLY"
    assert gate["physical_contact_ready"] is False
    assert gate["production_dynamics_ready"] is False
    assert gate["non_abort_grasp_ready"] is False


def test_derived_ratio_and_excess_are_exact_semantic_diagnostics():
    gate, passed = MODULE.evaluate(CONTRACT)
    assert passed
    ratio = gate["derived_quantities"]["original_to_design_speed_ratio"]
    excess = gate["derived_quantities"]["original_nominal_excess_over_design_bound"]
    assert ratio["estimate"] == 10.0
    assert ratio["si_unit"] == "1"
    assert excess["estimate"] == 0.045000000000000005
    assert excess["si_unit"] == "m/s"
    assert ratio["standard_uncertainty"] is None
    assert excess["standard_uncertainty"] is None


def test_unreduced_0p05_consumer_is_rejected(tmp_path):
    def mutate(data):
        q = data["quantities"]["reduced_current_contact_consumer_candidate"]
        q["estimate"] = 0.05
        q["upper_bound"] = 0.05

    gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "CVR-G07")["state"] == "FAIL"
    assert gate["non_abort_grasp_ready"] is False


def test_any_candidate_upper_bound_above_0p005_is_rejected(tmp_path):
    def mutate(data):
        data["quantities"]["reduced_current_contact_consumer_candidate"]["upper_bound"] = 0.005000001

    gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "CVR-G07")["state"] == "FAIL"


def test_velocity_unit_mismatch_is_rejected(tmp_path):
    def mutate(data):
        data["quantities"]["reduced_current_contact_consumer_candidate"]["si_unit"] = "mm/s"

    gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "CVR-G07")["state"] == "FAIL"


def test_zero_filled_as_built_speed_is_rejected(tmp_path):
    def mutate(data):
        data["quantities"]["as_built_first_contact_closing_speed"]["estimate"] = 0.0
        data["quantities"]["as_built_first_contact_closing_speed"]["lower_bound"] = 0.0
        data["quantities"]["as_built_first_contact_closing_speed"]["upper_bound"] = 0.0

    gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "CVR-G08")["state"] == "FAIL"


def test_zero_filled_unknown_uncertainty_is_rejected(tmp_path):
    def mutate(data):
        data["quantities"]["as_built_first_contact_closing_speed"]["standard_uncertainty"] = 0.0

    gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "CVR-G08")["state"] == "FAIL"


def test_missing_quantity_metadata_is_rejected(tmp_path):
    def mutate(data):
        del data["quantities"]["original_provisional_contact_scenario_speed"]["degrees_of_freedom"]

    gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "CVR-G02")["state"] == "FAIL"


def test_source_hash_drift_is_rejected(tmp_path):
    def mutate(data):
        data["input_bindings"][2]["sha256"] = "0" * 64

    gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "CVR-G01")["state"] == "FAIL"


def test_attempted_physical_release_is_rejected(tmp_path):
    def mutate(data):
        data["consumer_bindings"]["current_contact_consumer"]["physical_contact_authorized"] = True
        data["ruling"]["next_stage_authorized"] = True

    gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "CVR-G09")["state"] == "FAIL"


def test_ruling_uses_quantity_references_not_duplicate_bare_values():
    ruling = load_contract()["ruling"]
    assert ruling["current_design_target_hard_upper_bound_quantity_ref"] == "current_design_target_hard_upper_bound"
    assert ruling["original_provisional_scenario_quantity_ref"] == "original_provisional_contact_scenario_speed"
    assert ruling["explicitly_reduced_design_diagnostic_quantity_ref"] == "reduced_current_contact_consumer_candidate"
    assert not any(key.endswith("_m_s") or key.endswith("_mps") for key in ruling)

