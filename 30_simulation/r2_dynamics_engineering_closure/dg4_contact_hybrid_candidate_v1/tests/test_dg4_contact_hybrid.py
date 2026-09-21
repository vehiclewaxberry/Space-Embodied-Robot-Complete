from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "DG4_CONTACT_HYBRID_CANDIDATE_CONTRACT_V1.yaml"
EVALUATOR_PATH = ROOT / "evaluate_dg4_candidate.py"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dg4_contact_hybrid import (  # noqa: E402
    ABORT_ONLY,
    FailClosedError,
    POST_IMPACT_DIAGNOSTIC,
    PRECONTACT,
    transition,
    validate_request,
)

SPEC = importlib.util.spec_from_file_location("dg4_evaluator", EVALUATOR_PATH)
EVALUATOR = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(EVALUATOR)


def load_contract():
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def evaluate_contract(contract_path: Path, output_root: Path):
    return EVALUATOR.evaluate(
        contract_path,
        output_root / "evidence.json",
        output_root / "gate.json",
    )


def evaluate_mutation(tmp_path: Path, mutation):
    data = copy.deepcopy(load_contract())
    mutation(data)
    contract = tmp_path / "mutated_contract.yaml"
    contract.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return evaluate_contract(contract, tmp_path)


def criterion(gate, criterion_id):
    return next(row for row in gate["criteria"] if row["id"] == criterion_id)


def estimate(case, quantity):
    return case["quantities"][quantity]["estimate"]


def test_nominal_candidate_passes_15_of_15_with_parent_hold(tmp_path):
    evidence, gate, passed = evaluate_contract(CONTRACT, tmp_path)
    assert passed is True
    assert gate["criteria_passed"] == 15
    assert gate["criteria_total"] == 15
    assert gate["gate"] == "PASS_CANDIDATE_WITH_PHYSICAL_HOLD"
    assert gate["parent_DG4_satisfied"] is False
    assert gate["physical_contact_ready"] is False
    assert gate["non_abort_grasp_ready"] is False
    assert gate["next_stage_authorized"] is False
    assert evidence["attachment_created"] is False


def test_exact_six_case_cross_product_and_two_targets(tmp_path):
    evidence, _, passed = evaluate_contract(CONTRACT, tmp_path)
    assert passed
    assert evidence["case_count"] == 6
    assert {case["target_id"] for case in evidence["cases"]} == {
        "TARGET_SATELLITE_22KG",
        "TARGET_DEBRIS_150KG",
    }
    assert {case["restitution_corner"] for case in evidence["cases"]} == {
        0.05,
        0.2,
        0.5,
    }


def test_every_case_uses_exact_three_state_sequence(tmp_path):
    evidence, _, passed = evaluate_contract(CONTRACT, tmp_path)
    assert passed
    for case in evidence["cases"]:
        assert case["state_sequence"] == [
            "PRECONTACT",
            "BOUNDED_CONTACT_DIAGNOSTIC",
            "POST_IMPACT_DIAGNOSTIC",
        ]
        assert case["terminal_state"] == "POST_IMPACT_DIAGNOSTIC"


def test_every_case_obeys_speed_and_restitution(tmp_path):
    evidence, _, passed = evaluate_contract(CONTRACT, tmp_path)
    assert passed
    for case in evidence["cases"]:
        assert estimate(case, "closing_speed") == 0.005
        assert case["audits"]["speed_bound_pass"] is True
        assert case["audits"]["precontact_is_closing"] is True
        assert case["audits"]["postimpact_is_separating"] is True
        assert case["audits"]["restitution_pass"] is True
        assert estimate(case, "relative_normal_post") == pytest.approx(
            -case["restitution_corner"] * estimate(case, "relative_normal_pre"),
            abs=1e-15,
        )


def test_linear_and_angular_momentum_audits_pass(tmp_path):
    evidence, _, passed = evaluate_contract(CONTRACT, tmp_path)
    assert passed
    for case in evidence["cases"]:
        assert case["audits"]["impulse_pair_pass"] is True
        assert case["audits"]["linear_momentum_pass"] is True
        assert case["audits"]["angular_momentum_pass"] is True
        assert case["audits"]["spin_angular_impulse_pass"] is True
        assert estimate(case, "linear_momentum_residual") <= 1e-12
        assert estimate(case, "angular_momentum_residual") <= 1e-12


def test_energy_nonincrease_and_independent_identity_pass(tmp_path):
    evidence, _, passed = evaluate_contract(CONTRACT, tmp_path)
    assert passed
    for case in evidence["cases"]:
        assert case["audits"]["energy_nonincrease_pass"] is True
        assert case["audits"]["energy_identity_pass"] is True
        assert estimate(case, "kinetic_energy_loss") >= 0.0
        assert estimate(case, "kinetic_energy_loss") == pytest.approx(
            estimate(case, "analytic_energy_loss"), abs=1e-12
        )


def test_postimpact_keeps_two_separate_bodies(tmp_path):
    evidence, _, passed = evaluate_contract(CONTRACT, tmp_path)
    assert passed
    for case in evidence["cases"]:
        ledger = case["separate_body_ledger"]
        assert ledger == {
            "body_count_pre": 2,
            "body_count_post": 2,
            "attachment_created": False,
            "persistent_contact_created": False,
            "physical_contact_claimed": False,
        }


def test_original_0p05_runtime_request_aborts():
    with pytest.raises(FailClosedError, match="DG4_SPEED_BOUND_EXCEEDED_ABORT_ONLY"):
        validate_request(
            scope="BOUNDED_DESIGN_DIAGNOSTIC_ONLY",
            requested_speed_m_s=0.05,
            hard_upper_bound_m_s=0.005,
            unknown_disposition=ABORT_ONLY,
            source_bindings_valid=True,
        )


def test_unknown_allow_policy_aborts():
    with pytest.raises(FailClosedError, match="DG4_UNKNOWN_POLICY_NOT_ABORT_ONLY"):
        validate_request(
            scope="BOUNDED_DESIGN_DIAGNOSTIC_ONLY",
            requested_speed_m_s=0.005,
            hard_upper_bound_m_s=0.005,
            unknown_disposition="ALLOW",
            source_bindings_valid=True,
        )


def test_physical_or_production_scope_aborts():
    with pytest.raises(FailClosedError, match="DG4_SCOPE_NOT_PERMITTED"):
        validate_request(
            scope="PHYSICAL_CONTACT",
            requested_speed_m_s=0.005,
            hard_upper_bound_m_s=0.005,
            unknown_disposition=ABORT_ONLY,
            source_bindings_valid=True,
        )


def test_attachment_transition_is_absent_and_aborts():
    with pytest.raises(FailClosedError, match="DG4_PROHIBITED_TRANSITION"):
        transition(PRECONTACT, "ATTACH_TARGET", eligible=True)
    assert transition(PRECONTACT, "ATTACH_TARGET", eligible=False) == ABORT_ONLY
    assert POST_IMPACT_DIAGNOSTIC != "ATTACHED"


def test_source_hash_drift_fails_gate(tmp_path):
    def mutate(data):
        data["source_pins"]["target_models"]["sha256"] = "0" * 64

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C01")["state"] == "FAIL"
    assert gate["gate"] == "FAIL"


def test_hard_bound_drift_from_0p005_fails_gate(tmp_path):
    def mutate(data):
        data["quantities"]["first_contact_speed_hard_upper_bound"]["estimate"] = 0.006
        data["quantities"]["first_contact_speed_hard_upper_bound"]["upper_bound"] = 0.006

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C03")["state"] == "FAIL"


def test_original_0p05_consumer_promotion_fails_gate(tmp_path):
    def mutate(data):
        data["consumer_policy"]["original_0p05_disposition"] = "ALLOW"

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C03")["state"] == "FAIL"


def test_unknown_policy_allow_fails_gate(tmp_path):
    def mutate(data):
        data["consumer_policy"]["unknown_disposition"] = "ALLOW"

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C15")["state"] == "FAIL"
    assert gate["unknown_auto_allow_count"] == 1


def test_physical_as_built_zero_fill_fails_gate(tmp_path):
    def mutate(data):
        data["physical_as_built"]["first_contact_closing_speed_m_s"] = 0.0

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C15")["state"] == "FAIL"


def test_any_release_promotion_fails_gate(tmp_path):
    def mutate(data):
        data["release_boundary"]["non_abort_grasp_ready"] = True
        data["release_boundary"]["parent_DG4_satisfied"] = True

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C15")["state"] == "FAIL"
    assert gate["parent_DG4_satisfied"] is False


def test_target_mass_reinterpretation_fails_source_semantics(tmp_path):
    def mutate(data):
        data["quantities"]["target_satellite_mass"]["estimate"] = 23.0

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C05")["state"] == "FAIL"


@pytest.mark.parametrize(
    ("quantity_name", "bad_unit"),
    [
        ("target_satellite_mass", "m"),
        ("target_debris_inertia_diag", "kg"),
        ("target_satellite_contact_lever", "kg*m^2"),
        ("restitution_residual_limit", "m"),
        ("contact_origin_coincidence_residual_limit", "m/s"),
    ],
)
def test_exact_quantity_unit_mapping_is_fail_closed(
    tmp_path, quantity_name, bad_unit
):
    def mutate(data):
        data["quantities"][quantity_name]["si_unit"] = bad_unit

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C02")["state"] == "FAIL"


def test_numerical_threshold_loosening_fails_gate(tmp_path):
    def mutate(data):
        record = data["quantities"]["contact_origin_coincidence_residual_limit"]
        record["estimate"] = 1.0e-6
        record["upper_bound"] = 1.0e-6

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C02")["state"] == "FAIL"


def test_contact_origin_and_restitution_residuals_have_distinct_units(tmp_path):
    evidence, _, passed = evaluate_contract(CONTRACT, tmp_path)
    assert passed is True
    for case in evidence["cases"]:
        restitution = case["quantities"]["restitution_residual"]
        coincidence = case["quantities"]["contact_origin_coincidence_residual"]
        assert restitution["si_unit"] == "m/s"
        assert coincidence["si_unit"] == "m"
        assert restitution["upper_bound"] == 1.0e-12
        assert coincidence["upper_bound"] == 1.0e-12


def test_mathematical_normal_cannot_be_promoted_to_physical_authority(tmp_path):
    def mutate(data):
        data["quantities"]["diagnostic_contact_normal_axis"]["status"] = "PHYSICAL_CONTACT_NORMAL_AUTHORITY"

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C15")["state"] == "FAIL"


def test_top_level_authority_scope_promotion_fails_gate(tmp_path):
    def mutate(data):
        data["authority_scope"] = "PHYSICAL_CONTACT_AND_ATTACHMENT_AUTHORITY"

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C02")["state"] == "FAIL"


def test_nonidentity_or_unbound_frame_fixture_fails_gate(tmp_path):
    def mutate(data):
        data["diagnostic_frame_fixture"]["R_I_from_D"][0][0] = 0.0

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C02")["state"] == "FAIL"


def test_debris_point_vector_cannot_be_promoted_to_ssot_lever(tmp_path):
    def mutate(data):
        record = data["quantities"]["target_debris_contact_lever"]
        record["status"] = "PHYSICAL_COM_TO_CONTACT_LEVER_AUTHORITY"
        record["authority"] = "TARGET_MODELS_V1"

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C05")["state"] == "FAIL"


@pytest.mark.parametrize(
    ("quantity_name", "field", "promoted_value", "expected_failed_criterion"),
    [
        ("target_satellite_contact_lever", "status", "PHYSICAL_PATCH", "DG4-C05"),
        ("restitution_nominal", "authority", "AS_BUILT_CONTACT_AUTHORITY", "DG4-C04"),
        ("diagnostic_contact_window", "status", "QUALIFIED_HARDWARE", "DG4-C04"),
    ],
)
def test_claim_sensitive_local_metadata_promotion_fails_gate(
    tmp_path, quantity_name, field, promoted_value, expected_failed_criterion
):
    def mutate(data):
        data["quantities"][quantity_name][field] = promoted_value

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C02")["state"] == "FAIL"
    assert criterion(gate, expected_failed_criterion)["state"] == "FAIL"
    assert criterion(gate, "DG4-C15")["state"] == "FAIL"


@pytest.mark.parametrize(
    "mutation_name",
    [
        "target_mass_authority",
        "target_tumble_value",
        "case_reference_mapping",
        "restitution_corner_mapping",
    ],
)
def test_any_frozen_contract_semantic_drift_fails_exact_contract_binding(
    tmp_path, mutation_name
):
    def mutate(data):
        if mutation_name == "target_mass_authority":
            data["quantities"]["target_satellite_mass"]["authority"] = (
                "AS_BUILT_FLIGHT_QUALIFIED"
            )
        elif mutation_name == "target_tumble_value":
            data["quantities"]["target_satellite_tumble_rate"]["estimate"] = 0.0
        elif mutation_name == "case_reference_mapping":
            data["cases"][0]["tumble_rate_quantity_ref"] = "target_debris_tumble_rate"
        elif mutation_name == "restitution_corner_mapping":
            data["restitution_corners"][0]["quantity_ref"] = "restitution_upper"

    _, gate, passed = evaluate_mutation(tmp_path, mutate)
    assert passed is False
    assert criterion(gate, "DG4-C02")["state"] == "FAIL"


def test_evaluator_outputs_are_byte_deterministic(tmp_path):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    out_a.mkdir()
    out_b.mkdir()
    _, gate_a, pass_a = evaluate_contract(CONTRACT, out_a)
    _, gate_b, pass_b = evaluate_contract(CONTRACT, out_b)
    assert pass_a and pass_b
    # Output paths differ by construction; normalize that non-physical field before the
    # semantic gate comparison, then compare physical evidence byte-for-byte.
    gate_a["evidence"]["path"] = "<REPLAY>"
    gate_b["evidence"]["path"] = "<REPLAY>"
    assert json.dumps(gate_a, sort_keys=True) == json.dumps(gate_b, sort_keys=True)
    assert (out_a / "evidence.json").read_bytes() == (out_b / "evidence.json").read_bytes()
