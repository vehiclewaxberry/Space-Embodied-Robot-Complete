from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dg5_uncertainty import (  # noqa: E402
    audit_contract_boundary,
    audit_mass_uncertainty,
    audit_solar_rom,
    build_evidence,
    canonical_sha256,
    derived_metrics,
    file_sha256,
    load_contract,
    load_yaml,
    source_binding,
)


@pytest.fixture(scope="module")
def contract() -> dict:
    return load_contract()


@pytest.fixture(scope="module")
def evidence() -> dict:
    return build_evidence()


def test_all_16_external_source_pins_match(contract: dict) -> None:
    binding = source_binding(contract)
    assert binding["matched"] == binding["total"] == 16
    assert binding["all_match"] is True


def test_c01_design_inputs_are_exact_and_unit_separated(evidence: dict) -> None:
    mass = evidence["mass_uncertainty_audit"]
    assert mass["checks"]["all_10_estimates_u_units_distribution_dof_bound"] is True
    checks = mass["measurement_model"]["input_checks"]
    assert {checks[name]["unit_exact_for_named_measurand"] for name in checks} == {True}
    assert mass["measurement_model"]["reference_frame"] == "S"
    assert mass["measurement_model"]["inertia_reference_point"] == "system_center_of_mass"


def test_exhaustive_corner_audit_has_expected_falsifier(evidence: dict) -> None:
    audit = evidence["mass_uncertainty_audit"]["corner_audit"]
    assert audit["evaluated"] == 1024
    assert audit["basic_rigid_body_constraints_not_falsified"] == 880
    assert audit["quarantined"] == 144
    assert audit["mass_nonpositive"] == 0
    assert audit["inertia_non_spd"] == 0
    assert audit["triangle_inequality_invalid"] == 144


def test_no_probability_or_combined_uncertainty_is_invented(evidence: dict) -> None:
    model = evidence["mass_uncertainty_audit"]["measurement_model"]
    budget = evidence["mass_uncertainty_audit"]["oat_sensitivity_budget"]
    assert model["correlation_model"] is None
    assert model["combined_standard_uncertainty"] is None
    assert model["coverage_probability"] is None
    assert budget["combined_u"] is None


def test_solar_three_corner_replay(evidence: dict) -> None:
    solar = evidence["solar_r2_corner_audit"]
    assert solar["candidate_pass"] is True
    assert solar["corner_order"] == ["LOW", "NOMINAL", "HIGH"]
    assert max(row["frequency_replay_max_relative"] for row in solar["corner_results"].values()) <= 1e-10


def _solar_inputs(contract: dict) -> tuple[dict, dict, dict]:
    pins = contract["source_pins"]
    rom = json.loads((ROOT / pins["solar_r2_rom"]["path"]).read_text(encoding="utf-8"))
    envelope = json.loads((ROOT / pins["solar_r2_validity_envelope"]["path"]).read_text(encoding="utf-8"))
    rom_gate = json.loads((ROOT / pins["solar_r2_rom_gate"]["path"]).read_text(encoding="utf-8"))
    return rom, envelope, rom_gate


def test_current_dg1_dg2_bound_but_parent_dg5_held(evidence: dict) -> None:
    holds = evidence["authority_hold_audit"]
    assert holds["checks"]["current_DG1_DG2_candidate_gate_15_of_15_bound"] is True
    assert holds["parent_DG5_satisfied"] is False
    assert evidence["parent_DG5_satisfied"] is False


def test_as_built_contact_actuator_nulls_are_preserved(evidence: dict) -> None:
    holds = evidence["authority_hold_audit"]
    assert holds["contact_as_built_field_count"] == holds["contact_as_built_null_count"] == 22
    assert holds["actuator_joint_count"] == 8
    assert holds["actuator_required_fields_per_joint"] == 19
    assert holds["actuator_measurement_null_count"] == 152
    assert holds["as_built_mass_properties"] is None
    assert holds["contact_uncertainty"] is None
    assert holds["actuator_uncertainty"] is None


def test_deterministic_replay_exact() -> None:
    first = build_evidence()
    second = build_evidence()
    assert canonical_sha256(first) == canonical_sha256(second)
    assert first["mass_uncertainty_audit"]["corner_audit"]["corner_sequence_sha256"] == second["mass_uncertainty_audit"]["corner_audit"]["corner_sequence_sha256"]


def test_negative_control_mass_input_drift_fails(contract: dict) -> None:
    changed = deepcopy(contract)
    changed["measurement_model"]["inputs"]["mass"]["estimate"] += 0.001
    mass = load_yaml(ROOT / contract["source_pins"]["r2_design_mass_ledger"]["path"])
    bridge = load_yaml(ROOT / contract["source_pins"]["r2_bridged_mass_ledger"]["path"])
    audit = audit_mass_uncertainty(changed, mass, bridge)
    assert audit["checks"]["all_10_estimates_u_units_distribution_dof_bound"] is False
    assert audit["candidate_pass"] is False


def test_negative_control_nonphysical_inertia_is_detected(contract: dict) -> None:
    values = np.asarray([contract["measurement_model"]["inputs"][name]["estimate"] for name in contract["measurement_model"]["input_order"]], dtype=float)
    values[4] = -1.0
    metrics = derived_metrics(values)
    assert metrics["inertia_spd"] is False


@pytest.mark.parametrize(
    ("input_name", "bad_unit"),
    [
        ("mass", "m"),
        ("cg_x", "kg*m^2"),
        ("Ixx", "kg"),
    ],
)
def test_negative_control_named_input_unit_swap_fails(
    contract: dict, input_name: str, bad_unit: str
) -> None:
    changed = deepcopy(contract)
    changed["measurement_model"]["inputs"][input_name]["unit"] = bad_unit
    mass = load_yaml(ROOT / contract["source_pins"]["r2_design_mass_ledger"]["path"])
    bridge = load_yaml(ROOT / contract["source_pins"]["r2_bridged_mass_ledger"]["path"])
    audit = audit_mass_uncertainty(changed, mass, bridge)
    assert audit["checks"]["all_10_estimates_u_units_distribution_dof_bound"] is False
    assert audit["candidate_pass"] is False


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("coverage_factor", 2.0),
        ("interpretation", "95_PERCENT_COVERAGE"),
        ("u_scale", 2.0),
        ("corner_count", 2048),
        ("method", "MONTE_CARLO"),
    ],
)
def test_negative_control_propagation_semantics_tamper_fails(
    contract: dict, field: str, bad_value
) -> None:
    changed = deepcopy(contract)
    changed["measurement_model"]["propagation"][field] = bad_value
    mass = load_yaml(ROOT / contract["source_pins"]["r2_design_mass_ledger"]["path"])
    bridge = load_yaml(ROOT / contract["source_pins"]["r2_bridged_mass_ledger"]["path"])
    audit = audit_mass_uncertainty(changed, mass, bridge)
    assert audit["checks"]["deterministic_one_u_contract_exact"] is False
    assert audit["candidate_pass"] is False


@pytest.mark.parametrize(
    ("parameter_name", "bad_unit"),
    [("EI", "N*m"), ("zeta", "percent"), ("frequency", "rad/s")],
)
def test_negative_control_solar_named_unit_tamper_fails(
    contract: dict, parameter_name: str, bad_unit: str
) -> None:
    changed = deepcopy(contract)
    changed["solar_r2_corner_contract"]["parameter_units"][parameter_name] = bad_unit
    rom, envelope, rom_gate = _solar_inputs(contract)
    audit = audit_solar_rom(changed, rom, envelope, rom_gate)
    assert audit["checks"]["corner_order_parameter_units_interpretation_and_thresholds_exact"] is False
    assert audit["candidate_pass"] is False


def test_negative_control_solar_probability_interpretation_fails(contract: dict) -> None:
    changed = deepcopy(contract)
    changed["solar_r2_corner_contract"]["interpretation"] = "THREE_CORNERS_WITH_95_PERCENT_COVERAGE"
    rom, envelope, rom_gate = _solar_inputs(contract)
    audit = audit_solar_rom(changed, rom, envelope, rom_gate)
    assert audit["checks"]["corner_order_parameter_units_interpretation_and_thresholds_exact"] is False
    assert audit["checks"]["full_coupled_and_probability_credit_not_claimed"] is False
    assert audit["candidate_pass"] is False


@pytest.mark.parametrize(
    "mutation",
    ["authority", "allowed_claim", "forbidden_claim", "external_null", "execution_guard", "next_stage"],
)
def test_negative_control_contract_authority_boundary_tamper_fails(
    contract: dict, mutation: str
) -> None:
    changed = deepcopy(contract)
    if mutation == "authority":
        changed["authority_scope"] = "FULL_DG5_PHYSICAL_AUTHORITY"
    elif mutation == "allowed_claim":
        changed["claim_boundary"]["allowed"].append("hardware-valid uncertainty")
    elif mutation == "forbidden_claim":
        changed["claim_boundary"]["forbidden"].remove("full parent DG5 closure")
    elif mutation == "external_null":
        changed["external_authority_nulls"]["as_built_mass_kg"] = 31.0
    elif mutation == "execution_guard":
        changed["execution_guards"]["hardware_claimed"] = True
    elif mutation == "next_stage":
        changed["next_stage_authorized"] = True
    assert audit_contract_boundary(changed)["candidate_pass"] is False


@pytest.mark.parametrize(
    "mutation",
    ["measurand_promotion", "inertia_convention", "derived_mass_unit"],
)
def test_negative_control_measurement_model_identity_tamper_fails(
    contract: dict, mutation: str
) -> None:
    changed = deepcopy(contract)
    if mutation == "measurand_promotion":
        changed["measurement_model"]["measurand"] = "AS_BUILT_FLIGHT_QUALIFIED"
    elif mutation == "inertia_convention":
        changed["measurement_model"]["inertia_matrix_convention"] = "DIAGONAL_ONLY"
    elif mutation == "derived_mass_unit":
        changed["measurement_model"]["derived_measurands"]["mass"] = "m"
    audit = audit_contract_boundary(changed)
    assert audit["checks"]["entire_contract_canonical_sha256_exact"] is False
    assert audit["checks"]["measurement_model_identity_and_derived_units_exact"] is False
    assert audit["candidate_pass"] is False


def test_generated_gate_and_manifest_are_fail_closed(evidence: dict) -> None:
    gate = json.loads((PACKAGE / "results" / "R2_DG5_DESIGN_UNCERTAINTY_CANDIDATE_GATE_V1.json").read_text(encoding="utf-8"))
    manifest = json.loads((PACKAGE / "results" / "DG5_DESIGN_UNCERTAINTY_CANDIDATE_MANIFEST_V1.json").read_text(encoding="utf-8"))
    assert gate["summary"] == {"failed": [], "passed": 16, "total": 16}
    assert gate["design_uncertainty_candidate_satisfied"] is True
    assert gate["parent_DG5_satisfied"] is False
    assert gate["as_built_mass_properties"] is None
    assert gate["contact_uncertainty"] is None
    assert gate["actuator_uncertainty"] is None
    assert gate["hardware_valid"] is False
    assert gate["production_valid"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False
    assert manifest["summary"]["external_pin_count"] == 16


def test_manifest_local_hashes_are_current() -> None:
    manifest = json.loads((PACKAGE / "results" / "DG5_DESIGN_UNCERTAINTY_CANDIDATE_MANIFEST_V1.json").read_text(encoding="utf-8"))
    for record in manifest["local_artifacts"]:
        path = ROOT / record["path"]
        assert path.stat().st_size == record["bytes"]
        assert file_sha256(path) == record["sha256"]
