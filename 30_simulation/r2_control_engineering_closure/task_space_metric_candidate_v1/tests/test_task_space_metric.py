from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE.parents[2]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import task_space_metric as metric


def test_contract_and_source_pins_are_exact():
    contract = metric.load_contract()
    assert contract["claim_boundary"]["candidate_metric_bound"] is True
    assert contract["next_stage_authorized"] is False
    pins = metric.validate_source_pins(contract, PROJECT_ROOT)
    assert pins["all_match"]
    assert pins["matched"] == pins["total"] == 7


def test_chain_length_is_source_derived_and_configuration_independent():
    contract = metric.load_contract()
    audit = metric.derive_chain_length(contract, PROJECT_ROOT)
    assert audit["joint_count"] == 12
    assert audit["matches_declared"]
    assert audit["derivation_configuration_independent"]
    assert audit["conservative_triangle_bound"]
    assert audit["derived_characteristic_length_m"] == pytest.approx(1.170431204685893, abs=1e-15)


def test_metric_diagonal_nondimensionalizes_linear_rows():
    length = 1.170431204685893
    five = metric._metric_diagonal(length, 5)
    six = metric._metric_diagonal(length, 6)
    assert np.array_equal(five, np.array([1.0 / length] * 3 + [1.0, 1.0]))
    assert np.array_equal(six, np.array([1.0 / length] * 3 + [1.0, 1.0, 1.0]))


def test_candidate_all_seventeen_checks_pass_without_authority_escalation():
    evidence, gate = metric.evaluate_candidate(project_root=PROJECT_ROOT)
    assert gate["all_checks_pass"]
    assert gate["passed"] == gate["total"] == 17
    assert evidence["candidate_metric_bound"] is True
    assert evidence["precontact_tracking_validated"] is False
    assert gate["parent_control_gate_reissued"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False


def test_rank_nullity_and_unit_reparameterization():
    evidence, _ = metric.evaluate_candidate(project_root=PROJECT_ROOT)
    five, six = evidence["tasks"]
    assert five["guard"]["rank"] == 5
    assert five["nullspace"]["dimension"] == 1
    assert five["meter_millimeter_invariance"]["pass"]
    assert six["guard"]["rank"] == 6
    assert six["nullspace"]["dimension"] == 0
    assert six["meter_millimeter_invariance"]["pass"]
    assert all(row["free_floating_mass_weighted"]["kilogram_gram_reparameterization"]["pass"] for row in (five, six))
    assert all(row["free_floating_mass_weighted"]["kilogram_gram_reparameterization"]["normal_matrix_max_abs"] <= 1e-12 for row in (five, six))
    assert all(row["free_floating_mass_weighted"]["kilogram_gram_reparameterization"]["normalization_path"] == "COMMON_UNIT_SCALE_CANCELLED_BEFORE_INVERSION__SHARED_DIMENSIONLESS_M_BAR" for row in (five, six))
    assert all(row["free_floating_mass_weighted"]["dimensionless_dls_audit"]["normal_matrix_unit"] == "1" for row in (five, six))


def test_reference_mass_and_inertia_are_source_derived():
    contract = metric.load_contract()
    audit = metric.derive_reference_scales(contract, PROJECT_ROOT)
    assert audit["matches_declared"]
    assert audit["inertial_link_count"] == 16
    assert audit["derived_reference_mass_kg"] == pytest.approx(31.022864807342987, abs=1e-12)
    assert audit["derived_reference_inertia_kg_m2"] == pytest.approx(42.498508062024065, abs=1e-12)


def test_nonidentity_generalized_rate_scale_matches_manual_dimensionless_change_of_variables():
    jacobian = np.array([[1.0, 0.2, 0.0, 0.1, 0.0, 0.3], [0.0, 0.5, 0.4, 0.0, 0.2, 0.1]])
    desired = np.array([0.1, -0.2])
    physical_mass = np.diag([2.0, 3.0, 5.0, 7.0, 11.0, 13.0])
    scale = np.array([0.5, 2.0, 1.5, 3.0, 0.75, 4.0])
    reference_inertia = 17.0
    damping = 0.03
    result, audit = metric.dimensionless_mass_weighted_dls(
        jacobian, desired, physical_mass, scale, reference_inertia, damping
    )
    scale_inv = np.diag(1.0 / scale)
    mass_bar = scale_inv.T @ physical_mass @ scale_inv / reference_inertia
    jacobian_bar = jacobian @ scale_inv
    manual = scale_inv @ np.linalg.inv(mass_bar) @ jacobian_bar.T @ np.linalg.solve(
        jacobian_bar @ np.linalg.inv(mass_bar) @ jacobian_bar.T + damping**2 * np.eye(2), desired
    )
    assert np.allclose(result, manual, atol=1e-14, rtol=1e-14)
    assert np.allclose(audit["normalized_mass_matrix"], mass_bar, atol=1e-14, rtol=0.0)


def test_sensitivity_is_diagnostic_and_guards_remain_closed_form_valid():
    contract = metric.load_contract()
    evidence, _ = metric.evaluate_candidate(contract, PROJECT_ROOT)
    assert contract["sensitivity"]["robust_control_credit"] is False
    rows = [row for task in evidence["tasks"] for row in task["length_sensitivity_diagnostic"]]
    assert len(rows) == 6
    assert all(row["guard_allow"] for row in rows)


def test_negative_controls_all_caught():
    receipt = metric.run_negative_controls(metric.load_contract(), PROJECT_ROOT)
    assert receipt["all_pass"]
    assert receipt["passed"] == receipt["total"] == 29


def test_strict_json_rejects_duplicate_and_nonfinite():
    with pytest.raises(metric.MetricError, match="DUPLICATE_JSON_KEY"):
        metric.loads_json_strict('{"a":1,"a":2}')
    with pytest.raises(metric.MetricError, match="NONFINITE_JSON_CONSTANT"):
        metric.loads_json_strict('{"a":NaN}')


def test_built_gate_and_independent_receipt_if_present_are_fail_closed():
    gate_path = PACKAGE / "results" / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1.json"
    if not gate_path.exists():
        pytest.skip("builder not run yet")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate["artifact_package_complete"] is True
    assert gate["hardware_valid"] is False
    assert gate["safe_review_pass"] is False
    assert gate["next_stage_authorized"] is False
    receipt_path = PACKAGE / "results" / "CTRL_R2_TASK_SPACE_METRIC_STANDALONE_INTERNAL_VALIDATION_V1.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["all_pass"] is True
        assert receipt["next_stage_authorized"] is False
