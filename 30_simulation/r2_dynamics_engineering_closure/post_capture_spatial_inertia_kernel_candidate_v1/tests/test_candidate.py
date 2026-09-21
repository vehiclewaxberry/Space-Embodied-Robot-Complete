from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

import post_capture_spatial_inertia as kernel


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PACKAGE_ROOT / "results"
EVIDENCE_PATH = RESULTS / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EVIDENCE_V1.json"
GATE_PATH = RESULTS / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_GATE_V1.json"
MANIFEST_PATH = RESULTS / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_MANIFEST_V1.json"
RECEIPT_PATH = RESULTS / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_INDEPENDENT_VALIDATION_V1.json"


def load_evaluator():
    path = PACKAGE_ROOT / "evaluate_post_capture_spatial_inertia.py"
    spec = importlib.util.spec_from_file_location("_post_capture_evaluator_for_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def contract():
    return kernel.load_contract()


@pytest.fixture(scope="session")
def evidence():
    return kernel.load_json_strict(EVIDENCE_PATH)


@pytest.fixture(scope="session")
def gate():
    return kernel.load_json_strict(GATE_PATH)


@pytest.fixture(scope="session")
def manifest():
    return kernel.load_json_strict(MANIFEST_PATH)


@pytest.fixture(scope="session")
def receipt():
    return kernel.load_json_strict(RECEIPT_PATH)


@pytest.mark.parametrize("gate_id", kernel.GATE_IDS)
def test_each_of_22_gate_rows_passes(gate, gate_id):
    rows = {row["id"]: row for row in gate["checks"]}
    assert tuple(row["id"] for row in gate["checks"]) == kernel.GATE_IDS
    assert rows[gate_id]["pass"] is True


NEGATIVE_PREFIXES = tuple(f"NC{index:02d}_" for index in range(1, 31))


@pytest.mark.parametrize("prefix", NEGATIVE_PREFIXES)
def test_each_main_negative_control_passes(evidence, prefix):
    matches = [
        item
        for item in evidence["negative_controls"]["records"]
        if item["id"].startswith(prefix)
    ]
    assert len(matches) == 1
    assert matches[0]["pass"] is True


def test_contract_hash_semantics_and_pins(contract):
    assert kernel.canonical_sha256(contract) == kernel.EXPECTED_CONTRACT_CANONICAL_SHA256
    semantics = kernel.validate_contract_semantics(contract)
    assert semantics == {
        "semantic_contract_valid": True,
        "source_pin_count": 7,
        "minimum_true_input_count": 7,
        "all_authority_false": True,
    }
    source_audit = kernel.validate_source_pins(contract)
    assert source_audit["all_match"] is True
    assert len(source_audit["records"]) == 7


def test_current_c08_c09_fail_closed_from_authority_sources(contract, evidence, gate):
    audit = kernel.audit_current_system_authority(contract)
    assert audit["all_pass"] is True
    assert audit["current_system_instance_evaluated"] is False
    assert audit["current_system_kernel_call_count"] == 0
    for identifier in ("C08", "C09"):
        assert audit["records"][identifier]["all_facts_exact"] is True
        assert audit["records"][identifier]["kernel_called"] is False
        assert audit["records"][identifier]["status"] == (
            "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        )
        assert evidence["current_system_authority_audit"]["records"][identifier] == (
            audit["records"][identifier]
        )
    assert gate["current_C08_status"] == audit["records"]["C08"]["status"]
    assert gate["current_C09_status"] == audit["records"]["C09"]["status"]


def test_display_transform_cannot_be_promoted_to_attachment():
    with pytest.raises(kernel.KernelError, match="MISSING_AUTHORITATIVE_ATTACHMENT_SE3"):
        kernel.admit_current_system_attachment(None, "C08")
    forged = {
        "schema": "AUTHORITY_BOUND_ATTACHMENT_SE3_RECEIPT_V1",
        "status": "AUTHORITY_BOUND_OPERATIONAL_ATTACHMENT_SE3",
        "operational_attachment_authority": True,
        "target_attachment_plant_allowed": True,
        "attachment_frame_ids": {"parent_frame": "E", "child_frame": "T", "transform_field": "T_E_T_rows"},
        "T_E_T_rows": np.eye(4),
        "system_configuration_linkage": {"configuration_id": "C08"},
    }
    with pytest.raises(kernel.KernelError, match="ATTACHMENT_AUTHORITY_SOURCE_PIN_MISSING"):
        kernel.admit_current_system_attachment(forged, "C08")


def test_attachment_api_does_not_accept_caller_supplied_contract(contract):
    with pytest.raises(TypeError):
        kernel.admit_current_system_attachment(None, "C08", contract)


def test_synthetic_fixture_labels_frames_and_units(evidence):
    for identifier, run in evidence["synthetic_fixture_runs"].items():
        fixture = run["fixture"]
        assert identifier in {"C08", "C09"}
        assert fixture["classification"] == (
            "SYNTHETIC_EXACT_NUMERICAL_FIXTURE__NOT_CURRENT_SYSTEM_INSTANCE"
        )
        assert fixture["attachment_transform_authority"] == "SYNTHETIC_TEST_ONLY"
        assert fixture["contact_or_attachment_evidence"] is False
        audit = kernel.validate_fixture(fixture)
        assert audit["frames_exact"] is True
        assert audit["units_exact"] is True
        assert tuple(fixture["units"]["joint_coordinates"]) == kernel.COORDINATE_UNITS
        assert tuple(fixture["units"]["joint_rates"]) == kernel.RATE_UNITS


def test_direct_and_spatial_formulas_match(evidence, contract):
    limit = contract["thresholds"]
    for run in evidence["synthetic_fixture_runs"].values():
        cross = run["independent_spatial_formula_cross"]
        assert cross["mass_abs_kg"] <= limit["direct_vs_spatial_mass_max_kg"]
        assert cross["cg_max_abs_m"] <= limit["direct_vs_spatial_cg_max_m"]
        assert cross["inertia_max_abs_kg_m2"] <= limit[
            "direct_vs_spatial_inertia_max_kg_m2"
        ]
        spatial = np.asarray(cross["spatial_inertia_B_v_omega_order"])
        assert spatial.shape == (6, 6)
        assert np.max(np.abs(spatial - spatial.T)) <= 2.0e-11


def test_composite_inertia_is_physical(evidence, contract):
    for run in evidence["synthetic_fixture_runs"].values():
        audit = run["composite_direct"]["inertia_audit"]
        assert audit["symmetry_max_kg_m2"] <= contract["thresholds"][
            "inertia_symmetry_max_kg_m2"
        ]
        assert audit["minimum_eigenvalue_kg_m2"] >= contract["thresholds"][
            "inertia_min_eigenvalue_min_kg_m2"
        ]
        assert audit["principal_moment_triangle_satisfied"] is True


def test_post_capture_state_shape_lock_and_momentum(evidence, contract):
    for run in evidence["synthetic_fixture_runs"].values():
        state = run["post_capture_state_initialization"]
        assert len(state["physical_state_23"]) == 23
        assert len(state["derived_base_twist_I_m_s_rad_s"]) == 6
        assert len(state["derived_base_twist_B_m_s_rad_s"]) == 6
        assert state["joint_lock_exact"] is True
        assert np.array_equal(
            np.asarray(state["joint_rates_mixed_rad_s_m_s"]), np.zeros(8)
        )
        assert state["linear_momentum_residual_kg_m_s"] <= contract["thresholds"][
            "linear_momentum_residual_max_kg_m_s"
        ]
        assert state["angular_momentum_residual_kg_m2_s"] <= contract[
            "thresholds"
        ]["angular_momentum_residual_max_kg_m2_s"]
        assert np.asarray(state["origin_O_in_I_m"]).shape == (3,)
        assert state["energy_conservation_evaluated"] is False


def test_degenerations_scaling_sensitivity_and_covariance(evidence, contract):
    threshold = contract["thresholds"]
    for diagnostic in evidence["diagnostics"].values():
        zero = diagnostic["rigid_degenerations"]["zero_target"]
        assert zero["mass_abs_kg"] <= threshold["rigid_degenerate_mass_max_kg"]
        assert zero["cg_max_abs_m"] <= threshold["rigid_degenerate_cg_max_m"]
        assert zero["inertia_max_abs_kg_m2"] <= threshold[
            "rigid_degenerate_inertia_max_kg_m2"
        ]
        colocated = diagnostic["rigid_degenerations"]["colocated_axis_aligned"]
        assert colocated["cg_max_abs_m"] <= threshold["rigid_degenerate_cg_max_m"]
        assert colocated["inertia_sum_max_abs_kg_m2"] <= threshold[
            "rigid_degenerate_inertia_max_kg_m2"
        ]
        assert diagnostic["mass_scaling"]["max_formula_error"] <= threshold[
            "mass_scaling_formula_max"
        ]
        assert diagnostic["attachment_sensitivity"]["translation_cg_change_m"] >= (
            threshold["translation_sensitivity_min_m"]
        )
        assert diagnostic["attachment_sensitivity"][
            "rotation_inertia_change_kg_m2"
        ] >= threshold["rotation_sensitivity_min_kg_m2"]
        assert diagnostic["frame_covariance"]["cg_max_abs_m"] <= threshold[
            "frame_covariance_cg_max_m"
        ]
        assert diagnostic["frame_covariance"]["inertia_max_abs_kg_m2"] <= threshold[
            "frame_covariance_inertia_max_kg_m2"
        ]
        reference = diagnostic["reference_point_translation"]
        assert reference["H_translation_law"] == "H_O_prime=H_O-delta_r_O_cross_P"
        assert reference["twist_invariance_max_abs"] <= 2.0e-12
        assert reference["wrong_cross_sign_twist_delta"] > 1.0e-8


@pytest.mark.parametrize("mass", [0.0, -1.0, np.nan, np.inf])
def test_public_spatial_inertia_rejects_invalid_mass(mass):
    with pytest.raises(kernel.KernelError):
        kernel.spatial_inertia_about_origin(mass, [0.0, 0.0, 0.0], np.eye(3))


def test_gate_summary_review_and_authority(gate):
    assert gate["passed"] == gate["total"] == 22
    assert gate["all_checks_pass"] is True
    assert gate["verdict"] == gate["maximum_claim"]
    assert gate["review_status"] == "PENDING_OWNER_REVIEW"
    for key in (
        "current_system_instance_evaluated",
        "contact_valid",
        "attachment_valid",
        "target_attachment_plant_valid",
        "hardware_valid",
        "non_abort_authorized",
        "parent_dynamics_engineering_complete",
        "next_stage_authorized",
        "release_credit",
    ):
        assert gate[key] is False


def test_minimum_real_plant_inputs_are_explicit(contract, evidence):
    items = contract["minimum_true_inputs_to_bind_existing_23d_plant"]
    assert len(items) == 7
    assert [item["id"][:4] for item in items] == [f"PC{i:02d}" for i in range(1, 8)]
    assert evidence["minimum_true_inputs_to_bind_existing_23d_plant"] == items
    assert "CURRENT_23D_PLANT_REJECTS_NONZERO_TOTAL_MOMENTUM" in items[-1]["authority"]


def test_no_hardware_uncertainty_or_energy_claim(evidence):
    assert evidence["measurement_uncertainty_boundary"] == (
        "NO_HARDWARE_MEASUREMENTS_OR_UNCERTAINTY_PROPAGATION__SYNTHETIC_EXACT_FIXTURE_VALUES_ONLY"
    )
    assert evidence["energy_boundary"] == (
        "PERFECTLY_INELASTIC_RIGIDIFICATION_ENERGY_IS_NOT_CONSERVED_OR_CREDITED"
    )


def test_manifest_fixed_allowlist_and_directory_payload(contract, manifest):
    evaluator = load_evaluator()
    checks = evaluator.check_manifest(manifest, contract)
    assert all(checks.values())
    paths = [item["path"] for item in manifest["package_entries"]]
    assert paths == list(evaluator.FROZEN_PACKAGE_PATHS)
    assert len(paths) == len(set(paths)) == 11
    assert manifest["external_source_pin_count"] == 7
    assert manifest["cache_bytecode_or_unlisted_payload_allowed"] is False
    assert manifest["exclusions"] == [
        "results/POST_CAPTURE_SPATIAL_INERTIA_KERNEL_INDEPENDENT_VALIDATION_V1.json"
    ]
    payload = evaluator.directory_payload_audit()
    assert payload["exact"] is True
    assert payload["missing_frozen_paths"] == []
    assert payload["unexpected_paths"] == []


def test_all_json_artifacts_are_strict():
    for path in (EVIDENCE_PATH, GATE_PATH, MANIFEST_PATH, RECEIPT_PATH):
        document = kernel.load_json_strict(path)
        assert kernel.canonical_sha256(document)
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY_REJECTED"):
        kernel.loads_json_strict('{"x":1,"x":2}')
    with pytest.raises(ValueError, match="NONFINITE_JSON_CONSTANT_REJECTED"):
        kernel.loads_json_strict('{"x":NaN}')


def test_standalone_validator_has_no_core_or_evaluator_import():
    path = PACKAGE_ROOT / "independent_validate_post_capture_spatial_inertia.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not [
        name
        for name in imports
        if "post_capture_spatial_inertia" in name
        or "evaluate_post_capture_spatial_inertia" in name
    ]


def test_independent_receipt_summary_manifest_and_authority(receipt):
    assert receipt["validator_architecture"] == (
        "STANDALONE_INTERNAL_NO_KERNEL_EVALUATOR_OR_BUILDER_IMPORT__NOT_ORGANIZATIONALLY_INDEPENDENT"
    )
    assert receipt["independence_classification"] == (
        "PACKAGE_LOCAL_STANDALONE_INTERNAL__EXTERNAL_AUDIT_REQUIRED_FOR_INDEPENDENCE_CLAIM"
    )
    assert receipt["passed"] == receipt["total"] == 34
    assert receipt["all_checks_pass"] is True
    assert receipt["negative_controls"]["passed"] == 29
    assert receipt["negative_controls"]["count"] == 29
    assert receipt["negative_controls"]["all_pass"] is True
    assert receipt["manifest_audit"]["all_pass"] is True
    assert receipt["manifest_audit"]["declared_entries_canonical_sha256"] == (
        receipt["manifest_audit"]["independently_recomputed_entries_canonical_sha256"]
    )
    for key in (
        "current_system_instance_evaluated",
        "contact_valid",
        "attachment_valid",
        "target_attachment_plant_valid",
        "hardware_valid",
        "non_abort_authorized",
        "parent_dynamics_engineering_complete",
        "next_stage_authorized",
        "release_credit",
    ):
        assert receipt[key] is False


@pytest.mark.parametrize("gate_id", kernel.GATE_IDS)
def test_independent_reproduction_of_each_gate_passes(receipt, gate_id):
    rows = {row["id"]: row for row in receipt["independent_gate_reproduction"]}
    assert rows[gate_id]["pass"] is True


def test_independent_formula_and_momentum_errors(receipt):
    for case in receipt["physics_recomputation"]["cases"].values():
        assert max(case["direct_errors"].values()) <= 2.0e-11
        assert case["spatial_matrix_max_abs"] <= 2.0e-11
        assert case["state"]["twist"] <= 2.0e-12
        assert case["state"]["linear_momentum"] <= 2.0e-12
        assert case["state"]["angular_momentum"] <= 5.0e-11
