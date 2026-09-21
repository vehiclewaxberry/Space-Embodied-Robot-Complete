from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

import time_varying_torque_plant as plant


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PACKAGE_ROOT / "results"
EVIDENCE_PATH = RESULTS / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_EVIDENCE_V1.json"
GATE_PATH = RESULTS / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_GATE_V1.json"
MANIFEST_PATH = RESULTS / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_MANIFEST_V1.json"
INDEPENDENT_RECEIPT_PATH = RESULTS / "R2_TIME_VARYING_TORQUE_PLANT_INDEPENDENT_VALIDATION_V1.json"


def load_evaluator():
    path = PACKAGE_ROOT / "evaluate_time_varying_torque_plant.py"
    spec = importlib.util.spec_from_file_location("_candidate_evaluator_for_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def contract():
    return plant.load_contract()


@pytest.fixture(scope="session")
def evidence():
    return plant.load_json_strict(EVIDENCE_PATH)


@pytest.fixture(scope="session")
def gate():
    return plant.load_json_strict(GATE_PATH)


@pytest.fixture(scope="session")
def manifest():
    return plant.load_json_strict(MANIFEST_PATH)


@pytest.fixture(scope="session")
def independent_receipt():
    return plant.load_json_strict(INDEPENDENT_RECEIPT_PATH)


@pytest.mark.parametrize("gate_id", plant.GATE_IDS)
def test_each_of_24_gate_rows_passes(gate, gate_id):
    rows = {row["id"]: row for row in gate["checks"]}
    assert tuple(row["id"] for row in gate["checks"]) == plant.GATE_IDS
    assert rows[gate_id]["pass"] is True


NEGATIVE_IDS = tuple(f"NC{index:02d}_" for index in range(1, 21))


@pytest.mark.parametrize("prefix", NEGATIVE_IDS)
def test_each_negative_control_passes(evidence, prefix):
    records = evidence["negative_controls"]["records"]
    matches = [record for record in records if record["id"].startswith(prefix)]
    assert len(matches) == 1
    assert matches[0]["pass"] is True


def test_gate_summary_is_exact_24_of_24(gate):
    assert gate["passed"] == 24
    assert gate["total"] == 24
    assert gate["all_checks_pass"] is True
    assert gate["verdict"] == gate["maximum_claim"]
    assert gate["review_status"] == "PENDING_OWNER_REVIEW"


def test_all_authority_boundaries_remain_false(gate, evidence):
    fields = (
        "flex_valid",
        "contact_valid",
        "target_attachment_valid",
        "hardware_valid",
        "control_valid",
        "parent_dynamics_engineering_complete",
        "sim13_non_abort_authorized",
        "next_stage_authorized",
        "release_credit",
    )
    assert all(gate[field] is False for field in fields)
    boundary = evidence["execution_boundaries"]
    assert boundary["candidate_only"] is True
    assert all(value is False for key, value in boundary.items() if key != "candidate_only")


def test_strict_json_rejects_duplicate_and_nonfinite_literals():
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY_REJECTED"):
        plant.loads_json_strict('{"x":1,"x":2}')
    with pytest.raises(ValueError, match="NONFINITE_JSON_CONSTANT_REJECTED"):
        plant.loads_json_strict('{"x":NaN}')
    with pytest.raises(ValueError, match="NONFINITE_JSON_CONSTANT_REJECTED"):
        plant.loads_json_strict('{"x":-Infinity}')


def test_source_pins_still_match(contract):
    audit = plant.validate_source_pins(contract)
    assert audit["all_match"] is True
    assert len(audit["records"]) == 19


def test_runtime_project_module_binding_is_exhaustive(contract, evidence):
    binding = contract["runtime_project_module_binding"]
    assert binding["direct_pinned_module_ids"] == [
        "parent_dynamics_source",
        "free_floating_tree",
        "unified_r2_backend",
    ]
    assert binding["transitive_pinned_module_ids"] == [
        "sim13_v2_package_init",
        "sim13_v2_authority_resolver",
        "sim13_v2_contracts_module",
        "sim13_v2_env_module",
        "sim13_v2_system_model",
        "sim13_v2_backends_package_init",
        "sim13_v2_backends_canonical",
    ]
    assert binding["expected_project_runtime_module_count_excluding_candidate"] == 10
    assert binding["runtime_transitive_module_count"] == 7
    assert binding["unpinned_project_runtime_modules_allowed"] is False
    inventory = evidence["runtime_project_module_inventory"]
    assert inventory["all_project_runtime_modules_pinned_exactly"] is True
    assert len(inventory["expected_module_source_paths"]) == 10
    assert inventory["actual_module_source_paths"] == inventory["expected_module_source_paths"]
    assert inventory["unpinned_project_runtime_modules"] == []
    assert inventory["pinned_but_not_imported_modules"] == []


def test_contract_hash_and_semantics_exact(contract):
    assert plant.canonical_sha256(contract) == plant.EXPECTED_CONTRACT_CANONICAL_SHA256
    semantic = plant.validate_contract_semantics(contract)
    assert semantic["semantic_contract_valid"] is True
    assert semantic["all_guards_false"] is True
    assert semantic["source_pin_count"] == 19
    assert contract["review_status"] == "PENDING_OWNER_REVIEW"


def test_state_history_dimensions_and_lane_lock(evidence):
    actuated = np.asarray(evidence["lanes"]["ACTUATED_8DOF"]["rk4_physical_state_history_23"])
    locked = np.asarray(evidence["lanes"]["LOCKED_2P_6R_PULSE"]["rk4_physical_state_history_23"])
    assert actuated.ndim == 2 and actuated.shape[1] == 23
    assert locked.ndim == 2 and locked.shape[1] == 23
    assert np.array_equal(locked[:, 13:15], np.full((len(locked), 2), 0.03575))
    assert np.array_equal(locked[:, 21:23], np.zeros((len(locked), 2)))


def test_derived_base_twist_is_six_dimensional(evidence):
    for lane in ("ACTUATED_8DOF", "LOCKED_2P_6R_PULSE"):
        twist = np.asarray(evidence["lanes"][lane]["rk4_audit"]["base_twist_body_history_mixed_m_s_rad_s"])
        assert twist.ndim == 2 and twist.shape[1] == 6


def test_backend_default_is_explicitly_rejected(evidence):
    audit = evidence["backend_default_state_audit"]
    assert audit["backend_default_accepted_for_execution"] is False
    assert audit["validation_rejected"] is True
    assert "gripper_joint2" in audit["violating_joints"]
    assert audit["required_invalid_value_exact"] is True


def test_manifest_is_deterministic_and_self_excluded(contract, manifest):
    evaluator = load_evaluator()
    checks = evaluator.check_manifest(manifest, contract)
    assert all(checks.values())
    paths = [entry["path"] for entry in manifest["package_entries"]]
    assert manifest["self_excluded_path"] not in paths
    assert paths == sorted(paths)
    assert len(paths) == 11
    assert paths == manifest["frozen_package_path_allowlist"]
    assert manifest["exclusions"] == [
        "results/R2_TIME_VARYING_TORQUE_PLANT_INDEPENDENT_VALIDATION_V1.json"
    ]
    assert manifest["cache_bytecode_or_unlisted_payload_allowed"] is False
    assert manifest["directory_payload_exact_at_generation"] is True
    assert manifest["external_source_pin_count"] == 19


def test_directory_payload_matches_frozen_allowlist_exactly(manifest):
    evaluator = load_evaluator()
    audit = evaluator.directory_payload_audit()
    assert audit["exact"] is True
    assert audit["missing_frozen_paths"] == []
    assert audit["unexpected_paths"] == []
    expected = set(manifest["frozen_package_path_allowlist"]) | {
        manifest["self_excluded_path"],
        manifest["exclusions"][0],
    }
    assert set(audit["actual_file_paths"]) == expected
    assert not [
        path
        for path in audit["actual_file_paths"]
        if "__pycache__" in path
        or ".pytest_cache" in path
        or path.endswith((".pyc", ".pyo"))
    ]


def test_manifest_and_artifacts_are_strict_json():
    for path in (EVIDENCE_PATH, GATE_PATH, MANIFEST_PATH):
        document = plant.load_json_strict(path)
        assert plant.canonical_sha256(document)


def test_no_hardware_uncertainty_is_invented(evidence):
    assert evidence["measurement_uncertainty_boundary"] == (
        "NO_HARDWARE_MEASUREMENTS_OR_UNCERTAINTY_MODEL_USED__DESIGN_NUMBERS_ONLY"
    )
    assert evidence["execution_boundaries"]["hardware_actuator_model_used"] is False


def test_standalone_validator_has_no_shared_implementation_imports():
    import ast

    path = PACKAGE_ROOT / "independent_validate_time_varying_torque_plant.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden = (
        "time_varying_torque_plant",
        "evaluate_time_varying_torque_plant",
        "src.time_varying_torque_plant",
    )
    assert not [name for name in imports if any(token in name for token in forbidden)]


def test_independent_validation_receipt_passes(independent_receipt):
    assert independent_receipt["schema"] == "R2_TIME_VARYING_TORQUE_PLANT_INDEPENDENT_VALIDATION_V1"
    assert independent_receipt["validator_architecture"] == (
        "STANDALONE_NO_SHARED_BUILDER_EVALUATOR_SRC_IMPORTS"
    )
    assert independent_receipt["passed"] == 36
    assert independent_receipt["total"] == 36
    assert independent_receipt["all_checks_pass"] is True
    assert all(row["pass"] is True for row in independent_receipt["checks"])
    assert independent_receipt["manifest_audit"]["all_pass"] is True
    assert independent_receipt["gate_structure_audit"]["checks"]["review_status"] is True
    assert independent_receipt["contract_audit"]["checks"]["review_status"] is True
    assert (
        independent_receipt["manifest_audit"][
            "declared_entries_canonical_sha256"
        ]
        == independent_receipt["manifest_audit"][
            "independently_recomputed_entries_canonical_sha256"
        ]
    )


@pytest.mark.parametrize("gate_id", plant.GATE_IDS)
def test_independent_reproduction_of_each_gate_passes(independent_receipt, gate_id):
    rows = {row["id"]: row for row in independent_receipt["independent_gate_reproduction"]}
    assert rows[gate_id]["pass"] is True


def test_independent_mutation_controls_pass(independent_receipt):
    controls = independent_receipt["negative_controls"]
    assert controls["passed"] == 28
    assert controls["count"] == 28
    assert controls["all_pass"] is True
    records = {record["id"]: record for record in controls["records"]}
    assert len(records) == 28
    for identifier in (
        "INC22_NONZERO_TOTAL_MOMENTUM_BEHAVIORAL_REJECTION",
        "INC25_GATE_REVIEW_STATUS_CONSISTENT_RESIGN",
        "INC26_FROZEN_ALLOWLIST_MUTATION",
        "INC27_TRANSITIVE_RUNTIME_PIN_MUTATION",
        "INC28_DOP853_ARCHIVE_FIELD_MUTATION",
    ):
        assert records[identifier]["pass"] is True
    assert records["INC22_NONZERO_TOTAL_MOMENTUM_BEHAVIORAL_REJECTION"]["observed"] == (
        "IndependentValidationError"
    )


def test_independent_dop853_reintegration_matches_each_archived_field(independent_receipt):
    limits = {
        "qR_rad": 1.0e-11,
        "qP_m": 1.0e-13,
        "dqR_rad_s": 1.0e-9,
        "dqP_m_s": 1.0e-11,
        "position_m": 1.0e-12,
        "attitude_rad": 1.0e-12,
        "work_J": 1.0e-12,
    }
    reproduction = independent_receipt["physics_recomputation"][
        "dop853_integration_reproduction"
    ]
    assert set(reproduction) == {"ACTUATED_8DOF", "LOCKED_2P_6R_PULSE"}
    for lane in reproduction.values():
        assert set(lane) == set(limits)
        assert all(lane[field] <= threshold for field, threshold in limits.items())


def test_independent_receipt_keeps_all_authority_false(independent_receipt):
    fields = (
        "flex_valid",
        "contact_valid",
        "target_attachment_valid",
        "hardware_valid",
        "control_valid",
        "parent_dynamics_engineering_complete",
        "sim13_non_abort_authorized",
        "next_stage_authorized",
        "release_credit",
    )
    assert all(independent_receipt[field] is False for field in fields)
