"""Regression and authority-boundary tests for the fixed-platform package."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
WORKSPACE = next(path for path in (PACKAGE, *PACKAGE.parents) if (path / "PROJECT_MAP.md").is_file())
VALIDATION = PACKAGE / "04_validation"
sys.path.insert(0, str(VALIDATION))

from fixed_platform_validation_lib import (  # noqa: E402
    CANDIDATES,
    EXPECTED_SYSTEM_INVARIANTS,
    T_S_M3R_LOCAL,
    verify_record,
)
from run_negative_controls import CONTROL_IDS  # noqa: E402


CONTRACT_PATH = PACKAGE / "00_contract" / "FIXED_PLATFORM_OPERATIONAL_COLLISION_CONTRACT_V1.json"
LOCK_PATH = PACKAGE / "00_contract" / "SOURCE_AUTHORITY_LOCK_V1.json"
LEDGER_PATH = PACKAGE / "00_contract" / "FRAME_AND_UNIT_LEDGER_V1.json"
RESULTS = PACKAGE / "05_results"
INDEPENDENT_PATH = RESULTS / "INDEPENDENT_STEP_REOPEN_VALIDATION_V1.json"
NEGATIVE_PATH = RESULTS / "NEGATIVE_CONTROLS_V1.json"
REPLAY_PATH = RESULTS / "FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def contract() -> dict[str, Any]:
    return load(CONTRACT_PATH)


@pytest.fixture(scope="session")
def lock() -> dict[str, Any]:
    return load(LOCK_PATH)


@pytest.fixture(scope="session")
def ledger() -> dict[str, Any]:
    return load(LEDGER_PATH)


@pytest.fixture(scope="session")
def independent() -> dict[str, Any]:
    return load(INDEPENDENT_PATH)


def test_contract_schema_and_scope(contract: dict[str, Any]) -> None:
    assert contract["schema"] == "ODR60_OPTION_A_FIXED_PLATFORM_OPERATIONAL_COLLISION_CONTRACT_V1"
    assert contract["authority_scope"] == "THREE_LOCAL_S_FRAME_STEP_FIRST_FIXED_PLATFORM_OPERATIONAL_COLLISION_CANDIDATES_ONLY"


def test_contract_has_three_distinct_candidates(contract: dict[str, Any]) -> None:
    rows = contract["candidate_set"]["authorized_candidates"]
    assert len(rows) == 3
    assert len({row["registry_object_id"] for row in rows}) == 3
    assert contract["candidate_set"]["aggregate_container_authorized"] is False


def test_contract_negative_control_order_is_exact(contract: dict[str, Any]) -> None:
    negative = contract["negative_control_contract"]
    assert negative["required_count"] == 24
    assert negative["ordering_is_frozen"] is True
    assert negative["required_ids_in_order"] == CONTROL_IDS


def test_source_lock_has_21_hash_pins(lock: dict[str, Any]) -> None:
    assert len(lock["source_pins"]) == 21
    assert len({row["id"] for row in lock["source_pins"]}) == 21


def test_every_source_pin_matches_current_bytes_and_hash(lock: dict[str, Any]) -> None:
    for row in lock["source_pins"]:
        verify_record(row)


def test_contract_control_files_are_hash_bound(contract: dict[str, Any]) -> None:
    controls = contract["contract_dependencies"]
    verify_record({**controls["source_authority_lock"], "path": str((PACKAGE / "00_contract" / controls["source_authority_lock"]["path"]).relative_to(WORKSPACE))})
    verify_record({**controls["frame_and_unit_ledger"], "path": str((PACKAGE / "00_contract" / controls["frame_and_unit_ledger"]["path"]).relative_to(WORKSPACE))})


def test_frame_matrix_matches_contract_and_ledger(contract: dict[str, Any], ledger: dict[str, Any]) -> None:
    expected = np.asarray(contract["frame_and_transform_contract"]["T_S_M3R_LOCAL_rows_mm"])
    assert np.array_equal(expected, T_S_M3R_LOCAL)
    assert np.array_equal(np.asarray(ledger["T_S_M3R_LOCAL_rows_mm"]), T_S_M3R_LOCAL)


def test_frame_rotation_is_proper_orthonormal() -> None:
    rotation = T_S_M3R_LOCAL[:3, :3]
    assert np.max(np.abs(rotation.T @ rotation - np.eye(3))) < 1e-12
    assert math.isclose(float(np.linalg.det(rotation)), 1.0, abs_tol=1e-12)


def test_load_bridge_identity_is_zero_transform(ledger: dict[str, Any]) -> None:
    row = next(row for row in ledger["objects"] if row["object_id"] == "F::LOAD_BRIDGE")
    assert row["source_frame"] == row["output_frame"] == "S"
    assert row["offline_transform"] == "IDENTITY"
    assert row["offline_transform_count_required"] == 0


@pytest.mark.parametrize("object_id", ["F::M3R_STAGE_A", "F::M3R_STAGE_B"])
def test_each_m3r_stage_has_exactly_one_transform(ledger: dict[str, Any], object_id: str) -> None:
    row = next(row for row in ledger["objects"] if row["object_id"] == object_id)
    assert row["source_frame"] == "M3R_LOCAL"
    assert row["output_frame"] == "S"
    assert row["offline_transform"] == "T_S_M3R_LOCAL"
    assert row["offline_transform_count_required"] == 1


def test_unit_chain_is_mm_to_m_once(ledger: dict[str, Any]) -> None:
    assert ledger["primary_step_length_unit"] == "mm"
    assert ledger["runtime_sidecar_length_unit"] == "m"
    assert ledger["step_to_runtime_scale"] == 0.001
    assert ledger["scale_application_count_required"] == 1


def test_as_built_uncertainty_is_explicitly_null(contract: dict[str, Any], lock: dict[str, Any], ledger: dict[str, Any]) -> None:
    assert ledger["as_built_uncertainty"] is None
    assert all(lock["as_built_uncertainty"][object_id] is None for object_id in CANDIDATES_BY_ID)
    assert lock["as_built_uncertainty"]["status"] == "MEASUREMENT_PENDING"
    assert lock["as_built_uncertainty"]["zero_fill_forbidden"] is True
    assert all(contract["as_built_and_uncertainty_contract"][object_id] is None for object_id in CANDIDATES_BY_ID)
    assert contract["as_built_and_uncertainty_contract"]["zero_fill_forbidden"] is True


CANDIDATES_BY_ID = {spec["object_id"]: name for name, spec in CANDIDATES.items()}


def test_system_authority_invariants_are_preserved(contract: dict[str, Any]) -> None:
    assert contract["current_system_authority_invariants"] == EXPECTED_SYSTEM_INVARIANTS


def test_primary_step_files_are_three_separate_files() -> None:
    paths = [PACKAGE / "01_cad" / spec["step"] for spec in CANDIDATES.values()]
    assert len(paths) == len({path.name for path in paths}) == 3
    assert all(path.is_file() and path.stat().st_size > 0 for path in paths)


def test_independent_validator_did_not_import_builder(independent: dict[str, Any]) -> None:
    proof = independent["validator_independence"]
    assert proof["candidate_builder_imported"] is False
    assert proof["candidate_geometry_module_imported"] is False
    assert proof["builder_executed"] is False
    assert proof["frozen_sources_reopened_directly_with_ocp"] is True


def test_independent_validation_summary_is_three_of_three(independent: dict[str, Any]) -> None:
    summary = independent["summary"]
    assert summary["objects_required"] == summary["objects_validated"] == 3
    assert summary["primary_step_single_solids_valid_closed_positive"] == 3
    assert summary["runtime_sidecar_sets_validated"] == 3
    assert summary["all_checks_pass"] is True


@pytest.mark.parametrize("name", sorted(CANDIDATES))
def test_each_candidate_is_one_valid_closed_positive_solid(independent: dict[str, Any], name: str) -> None:
    candidate = independent["objects"][name]["candidate"]
    assert candidate["solid_count"] == 1
    assert candidate["valid"] is True
    assert candidate["closed"] is True
    assert candidate["positive_volume"] is True
    assert candidate["volume_mm3"] > 0.0
    assert candidate["boundary_edge_count"] == candidate["nonmanifold_edge_count"] == 0


@pytest.mark.parametrize("name", sorted(CANDIDATES))
def test_each_candidate_matches_independent_source_transform(independent: dict[str, Any], name: str) -> None:
    comparison = independent["objects"][name]["comparison"]
    assert comparison["bbox_max_abs_error_mm"] <= 1e-6
    assert comparison["center_of_volume_max_abs_error_mm"] <= 1e-6
    assert comparison["volume_relative_error"] <= 1e-9
    assert comparison["surface_area_relative_error"] <= 1e-8
    assert comparison["face_count_equal"] is comparison["shell_count_equal"] is True


def test_load_bridge_output_is_identity_geometry(independent: dict[str, Any]) -> None:
    row = independent["objects"]["load_bridge"]
    assert row["placement_transform_application_count"] == 0
    assert row["transform_rule"] == "SOURCE_ALREADY_S__IDENTITY__NO_TRANSFORM"
    assert row["candidate"]["step"]["sha256"] == row["source"]["step"]["sha256"]


@pytest.mark.parametrize("name", ["m3r_stage_a", "m3r_stage_b"])
def test_m3r_candidate_is_transformed_once_not_relabelled(independent: dict[str, Any], name: str) -> None:
    row = independent["objects"][name]
    assert row["source_storage_frame"] == "M3R_LOCAL"
    assert row["owning_frame"] == "S"
    assert row["placement_transform_application_count"] == 1
    assert row["transform_rule"] == "M3R_LOCAL_TO_S_RIGID_TRANSFORM_APPLIED_EXACTLY_ONCE"
    assert row["candidate"]["step"]["sha256"] != row["source"]["step"]["sha256"]


@pytest.mark.parametrize("name", sorted(CANDIDATES))
def test_runtime_sidecars_are_metres_in_S_and_secondary(independent: dict[str, Any], name: str) -> None:
    runtime = independent["objects"][name]["runtime"]
    assert runtime["units"] == "m"
    assert runtime["frame"] == "S"
    assert runtime["object_id"] == CANDIDATES[name]["object_id"]
    assert runtime["mm_to_m_scale_application_count"] == 1
    assert runtime["mm_to_m_scale_factor"] == 0.001
    assert runtime["derived_from_primary_step"] is True
    assert runtime["primary_geometry_authority"] is False


@pytest.mark.parametrize("name", sorted(CANDIDATES))
def test_runtime_npz_has_safe_topology_and_metadata(name: str) -> None:
    path = PACKAGE / "02_runtime" / CANDIDATES[name]["npz"]
    with np.load(path, allow_pickle=False) as payload:
        assert set(payload.files) == {"faces", "metadata_json_utf8", "solid_ids", "vertices_m"}
        vertices = payload["vertices_m"]
        faces = payload["faces"]
        assert vertices.ndim == 2 and vertices.shape[1] == 3 and np.all(np.isfinite(vertices))
        assert faces.ndim == 2 and faces.shape[1] == 3
        assert int(faces.min()) >= 0 and int(faces.max()) < len(vertices)
        metadata = json.loads(bytes(payload["metadata_json_utf8"].tolist()).decode("utf-8"))
        assert metadata["units"] == "m" and metadata["frame"] == "S"
        assert metadata["object_id"] == CANDIDATES[name]["object_id"]
        assert metadata["step_to_runtime_scale_application_count"] == 1
        assert metadata["step_to_runtime_scale"] == 0.001
        assert metadata["as_built_derate_mm"] is None


def test_builder_receipts_all_checks_pass() -> None:
    for spec in CANDIDATES.values():
        receipt = load(RESULTS / spec["receipt"])
        assert receipt["checks"] and all(receipt["checks"].values())
        assert receipt["object_id"] == spec["object_id"]
        assert receipt["primary_step_geometry"]["brep_valid"] is True
        assert receipt["primary_step_geometry"]["all_shells_closed"] is True


def test_frame_and_unit_builder_audit_passes() -> None:
    audit = load(RESULTS / "FRAME_AND_UNIT_TRANSFORM_AUDIT_V1.json")
    assert audit["checks"] and all(audit["checks"].values())
    assert [row["transform_application_count"] for row in audit["rows"]] == [0, 1, 1]
    assert audit["unit_chain"] == {"primary_step": "mm", "runtime": "m", "scale": 0.001, "scale_application_count": 1}


def test_runtime_derivation_receipt_is_three_of_three() -> None:
    receipt = load(RESULTS / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json")
    assert len(receipt["rows"]) == 3 and all(row["pass"] for row in receipt["rows"])
    assert receipt["sidecar_is_primary_geometry_authority"] is False
    assert receipt["system_narrowphase_promoted"] is False
    assert receipt["as_built_derate_mm"] is None


def test_source_pin_recheck_passes_all_21() -> None:
    receipt = load(RESULTS / "SOURCE_PIN_RECHECK_V1.json")
    assert receipt["source_pin_count_verified"] == 21
    assert receipt["all_bytes_and_sha256_match"] is True
    assert receipt["system_authority_changed"] is False


def test_contractual_three_step_build_receipt_passes() -> None:
    receipt = load(RESULTS / "THREE_STEP_BUILD_RECEIPT_V1.json")
    assert receipt["object_count"] == 3
    assert receipt["valid_closed_positive_solid_count"] == 3
    assert receipt["checks"] and all(receipt["checks"].values())


def test_negative_controls_are_24_of_24() -> None:
    negative = load(NEGATIVE_PATH)
    summary = negative["summary"]
    assert summary["controls_required"] == summary["controls_executed"] == summary["controls_caught"] == 24
    assert summary["subcases_executed"] == summary["subcases_caught"] >= 24
    assert summary["all_controls_caught"] is True


def test_negative_control_ids_and_cases_are_exactly_caught() -> None:
    negative = load(NEGATIVE_PATH)
    assert [row["control_id"] for row in negative["controls"]] == CONTROL_IDS
    for control in negative["controls"]:
        assert control["status"] == "CAUGHT"
        assert control["case_count"] == control["caught_count"] == len(control["cases"])
        assert all(case["status"] == "CAUGHT" for case in control["cases"])


def test_negative_controls_are_isolated_and_system_unchanged() -> None:
    negative = load(NEGATIVE_PATH)
    isolation = negative["execution_isolation"]
    assert isolation["real_source_or_output_assets_modified"] is False
    assert isolation["cad_or_brep_execution_called"] is False
    assert isolation["pair_query_called"] is isolation["edge_evaluator_called"] is isolation["path_search_called"] is False
    assert negative["system_invariant_snapshot"]["unchanged"] is True
    assert negative["current_system_authority_invariants"] == EXPECTED_SYSTEM_INVARIANTS


def test_fresh_process_replay_passes_and_preserves_system_state() -> None:
    replay = load(REPLAY_PATH)
    assert replay["status"] == "PASS"
    assert replay["checks"] and all(replay["checks"].values())
    payload = replay["builder_payload"]
    assert payload["object_count"] == 3
    assert payload["system_operational_authority_rows"] == 1
    assert payload["system_pair_queries"] == 0
    assert payload["release_credit"] is False


def test_all_local_authority_documents_keep_forbidden_flags_false() -> None:
    documents = [
        load(INDEPENDENT_PATH),
        load(NEGATIVE_PATH),
        load(REPLAY_PATH),
        load(RESULTS / "BUILDER_EVIDENCE_V1.json"),
    ] + [load(RESULTS / spec["receipt"]) for spec in CANDIDATES.values()]
    forbidden = {"system_registry_reissued", "system_pair_evaluation_authorized", "pair_evaluation_authorized", "system_safe", "path_search_authorized", "parent_gate_credit", "next_stage_authorized", "release_credit"}
    for document in documents:
        for key, value in document.get("authority_flags", {}).items():
            if key in forbidden:
                assert value is False


def test_exact_m3r_output_x_spans() -> None:
    independent = load(INDEPENDENT_PATH)
    bbox_a = np.asarray(independent["objects"]["m3r_stage_a"]["candidate"]["bbox_mm"])
    bbox_b = np.asarray(independent["objects"]["m3r_stage_b"]["candidate"]["bbox_mm"])
    assert np.allclose(bbox_a[[0, 3]], [202.405, 210.405], atol=1e-6, rtol=0.0)
    assert np.allclose(bbox_b[[0, 3]], [196.0, 208.0], atol=1e-6, rtol=0.0)


def test_no_candidate_is_system_bound_or_pair_eligible(independent: dict[str, Any]) -> None:
    for row in independent["objects"].values():
        assert row["local_candidate_only"] is True
        assert row["system_registry_bound"] is False
        assert row["pair_eligible"] is False


def test_primary_step_hashes_are_distinct_except_identity_source_relationship() -> None:
    hashes = [hashlib.sha256((PACKAGE / "01_cad" / spec["step"]).read_bytes()).hexdigest().upper() for spec in CANDIDATES.values()]
    assert len(set(hashes)) == 3
