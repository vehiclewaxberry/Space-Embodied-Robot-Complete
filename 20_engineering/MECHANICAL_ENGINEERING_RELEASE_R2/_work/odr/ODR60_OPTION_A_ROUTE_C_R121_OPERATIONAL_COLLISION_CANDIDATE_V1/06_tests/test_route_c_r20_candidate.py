"""Independent regression tests for the Route-C R121 umbrella / R20 batch."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
VALIDATION_DIR = PACKAGE / "04_validation"
sys.path.insert(0, str(VALIDATION_DIR))

from route_c_r20_validation_lib import (  # noqa: E402
    BUILD_RECEIPT_PATH,
    CAD_DIR,
    CONTRACT_PATH,
    DETERMINISM_PATH,
    GEOMETRY_INDEX_PATH,
    INDEPENDENT_PATH,
    NEGATIVE_PATH,
    R121_SOURCE_AUDIT_PATH,
    RUNTIME_DIR,
    RUNTIME_RECEIPT_PATH,
    SOURCE_LOCK_PATH,
    audit_independent_imports,
    read_step,
    sha256_path,
    shape_facts,
    strict_json,
    validate_build_receipts,
    validate_contract_structure,
    validate_source_pins,
    verify_record,
)


CONTRACT = strict_json(CONTRACT_PATH)
SPECS = validate_contract_structure(CONTRACT)
SPEC_BY_ID = {row["object_id"]: row for row in SPECS}
OBJECT_IDS = sorted(SPEC_BY_ID)
LOCK = strict_json(SOURCE_LOCK_PATH)
PIN_IDS = sorted(row["id"] for row in LOCK["source_pins"])
NEGATIVE = strict_json(NEGATIVE_PATH)
CONTRACTUAL_NEGATIVE_IDS = list(CONTRACT["negative_control_ids"])
SOURCE_AUDIT = strict_json(R121_SOURCE_AUDIT_PATH)
SOURCE_LABELS = sorted(row["source_label"] for row in SOURCE_AUDIT["objects"])
REVIEWS = PACKAGE / "07_reviews"


def relative_package_record(record: dict) -> Path:
    path = PACKAGE / record["path"]
    assert path.is_file()
    assert path.stat().st_size == record["bytes"]
    assert sha256_path(path) == record["sha256"]
    return path


def test_contract_and_source_lock_are_complete() -> None:
    assert len(SPECS) == 20
    assert len(PIN_IDS) == 13
    assert len(CONTRACTUAL_NEGATIVE_IDS) == 33
    assert CONTRACT["remaining_R101"]["status"] == "FAIL_CLOSED_HOLD"
    assert CONTRACT["system_registry_binding_authorized"] is False
    assert CONTRACT["path_search_authorized"] is False
    assert CONTRACT["release_credit"] is False


def test_all_thirteen_source_pins_match() -> None:
    assert set(validate_source_pins(LOCK)) == set(PIN_IDS)


def test_builder_receipts_remain_bounded() -> None:
    receipts = validate_build_receipts(CONTRACT)
    assert receipts["build"]["objects_emitted"] == 20
    assert receipts["build"]["system_operational_credit"] is False
    assert receipts["build"]["system_pair_query_credit"] == 0
    assert receipts["build"]["release_credit"] is False


@pytest.mark.parametrize("object_id", OBJECT_IDS)
def test_each_primary_step_is_one_valid_closed_positive_solid(object_id: str) -> None:
    path = CAD_DIR / SPEC_BY_ID[object_id]["output"]
    shape, roots = read_step(path)
    facts = shape_facts(shape, context=object_id)
    assert roots == {"roots_available": 1, "roots_transferred": 1}
    assert facts["solid_count"] == 1
    assert facts["brep_valid"] is True
    assert facts["all_shells_closed"] is True
    assert facts["volume_mm3"] > 0.0


@pytest.mark.parametrize("object_id", OBJECT_IDS)
def test_each_independent_object_row_has_local_credit_only(object_id: str) -> None:
    receipt = strict_json(INDEPENDENT_PATH)
    rows = {row["object_id"]: row for row in receipt["objects"]}
    row = rows[object_id]
    assert row["local_geometry_candidate_pass"] is True
    assert row["freecad_object_placement_reapplied"] is False
    assert row["transform"]["application_count"] == 1
    assert row["transform"]["source_and_target_step_unit"] == "mm"
    assert row["runtime"]["scale_application_count"] == 1
    assert row["runtime"]["step_to_runtime_scale"] == 0.001
    assert row["runtime"]["as_built_derate_mm"] is None
    assert row["pair_eligible"] is False
    assert row["system_registry_bound"] is False


@pytest.mark.parametrize("object_id", OBJECT_IDS)
def test_each_runtime_set_has_three_hash_pinned_derivatives(object_id: str) -> None:
    receipt = strict_json(INDEPENDENT_PATH)
    row = next(item for item in receipt["objects"] if item["object_id"] == object_id)
    assert set(row["runtime"]["artifacts"]) == {"npz", "ply", "stl"}
    for record in row["runtime"]["artifacts"].values():
        verify_record(record)
    assert row["runtime"]["independent_step_tessellation_exact"] is True
    assert row["runtime"]["ply_npz_exact"] is True
    assert row["runtime"]["manifold"]["closed_oriented_two_manifold"] is True


@pytest.mark.parametrize("control_id", CONTRACTUAL_NEGATIVE_IDS)
def test_each_contractual_negative_control_is_caught(control_id: str) -> None:
    rows = {row["id"]: row for row in NEGATIVE["controls"]}
    assert rows[control_id]["caught"] is True
    assert rows[control_id]["exception"] == "ValidationFailure"
    assert rows[control_id]["reason"]


@pytest.mark.parametrize("source_label", SOURCE_LABELS)
def test_each_r121_source_object_is_valid_closed_positive(source_label: str) -> None:
    rows = {row["source_label"]: row for row in SOURCE_AUDIT["objects"]}
    row = rows[source_label]
    assert row["valid"] is True
    assert row["closed"] is True
    assert row["positive_volume"] is True
    assert row["source_volume_mm3"] > 0.0
    assert row["source_solid_count"] in (1, 2)
    assert row["source_shape_object_placement_consumed_separately"] is False


def test_full_r121_topology_and_name_sets_are_exact() -> None:
    counts = SOURCE_AUDIT["counts"]
    assert counts["objects"] == 121
    assert counts["single_solid_objects"] == 117
    assert counts["double_solid_objects"] == 4
    assert counts["total_solids"] == 125
    assert counts["nonidentity_freecad_object_placements"] == 53
    assert SOURCE_AUDIT["name_set_cross_check"]["all_four_sets_exactly_equal"] is True
    assert SOURCE_AUDIT["object_placement_reapplied"] is False


def test_independent_receipt_has_twenty_derived_checks_and_no_overclaim() -> None:
    receipt = strict_json(INDEPENDENT_PATH)
    assert receipt["validation_pass"] is True
    assert receipt["checks_required"] == receipt["checks_passed"] == 20
    assert all(receipt["checks"].values())
    assert receipt["object_count"] == 20
    assert receipt["runtime_sidecar_artifact_count"] == 60
    assert receipt["boolean_symmetric_difference_available_count"] == 20
    assert receipt["system_state_preserved"]["system_operational_authority_rows"] == 1
    assert receipt["system_state_preserved"]["required_unassessed_pairs"] == 11166
    assert receipt["system_state_preserved"]["stage_instances_bound"] == 0
    assert receipt["system_state_preserved"]["stage_instances_required"] == 3
    assert receipt["system_state_preserved"]["TMG4"] == "HOLD"
    assert receipt["system_state_preserved"]["G12"] == "FAIL"
    assert receipt["next_stage_authorized"] is False
    assert receipt["release_credit"] is False


def test_independent_python_sources_do_not_import_candidate_core() -> None:
    paths = [
        PACKAGE / "04_validation/validate_route_c_r20_independent.py",
        PACKAGE / "04_validation/route_c_r20_validation_lib.py",
        PACKAGE / "04_validation/inspect_v9f_fcstd_source.py",
    ]
    result = audit_independent_imports(paths)
    assert result["pass"] is True
    assert result["forbidden_imports"] == []
    assert result["forbidden_modules_loaded"] == []


def test_fresh_process_receipt_covers_exact_builder_core() -> None:
    receipt = strict_json(DETERMINISM_PATH)
    assert receipt["fresh_process_determinism_pass"] is True
    assert receipt["fresh_process_count"] == 2
    assert receipt["core_artifact_count"] == 83
    assert receipt["core_before"] == receipt["core_after"]
    assert receipt["core_unchanged"] is True
    assert receipt["parsed_summaries_identical"] is True
    assert receipt["builder"]["imported_by_checker"] is False
    assert receipt["authority_boundary"]["cad_cache_in_core"] is False


def test_primary_cad_directory_contains_only_twenty_steps() -> None:
    files = sorted(path for path in CAD_DIR.iterdir() if path.is_file())
    assert len(files) == 20
    assert all(path.suffix.lower() in {".step", ".stp"} for path in files)
    assert {path.name for path in files} == {row["output"] for row in SPECS}


def test_cad_inspect_and_snapshot_evidence_is_hash_pinned() -> None:
    inspect = strict_json(REVIEWS / "CAD_INSPECT_REFS_SUMMARY_V1.json")
    snapshot = strict_json(REVIEWS / "CAD_SNAPSHOT_REVIEW_V1.json")
    assert inspect["summary"]["successful"] == 20
    assert inspect["summary"]["inspect_pass"] is True
    assert snapshot["review_method"]["snapshots_created"] == 20
    assert snapshot["visual_findings"]["visual_review_pass"] is True
    assert len(snapshot["snapshots"]) == 20
    for record in snapshot["snapshots"]:
        relative_package_record(record)
    relative_package_record(snapshot["contact_sheet"])


def test_viewer_failure_is_truthfully_disclosed_and_not_geometry_credit() -> None:
    receipt = strict_json(REVIEWS / "CAD_VIEWER_STARTUP_RECEIPT_V1.json")
    assert receipt["exit_code"] == 1
    assert receipt["startup_pass"] is False
    assert receipt["viewer_url"] is None
    assert "agent:start" in receipt["root_cause"]
    assert receipt["authority_boundary"]["viewer_pass_claimed"] is False
    assert receipt["authority_boundary"]["local_geometry_gate_derived_from_viewer"] is False


def test_cad_cache_is_relocated_and_diagnostic_only() -> None:
    receipt = strict_json(REVIEWS / "CAD_CACHE_RELOCATION_RECEIPT_V1.json")
    assert receipt["initial_moved_count"] == 20
    assert receipt["late_replay_moved_count"] == 10
    assert receipt["total_preserved_cache_files"] == 30
    assert receipt["source_directory_after_move"] == {"primary_step_count": 20, "hidden_step_glb_count": 0}
    assert receipt["classification"] == "NONDETERMINISTIC_DIAGNOSTIC_DERIVATIVE_NOT_PRIMARY_GEOMETRY"
    assert receipt["replay_observation"]["same_named_glb_hashes_repeated"] is False
    assert receipt["authority_boundary"]["primary_geometry_changed"] is False
    for record in receipt["files"] + receipt["late_replay_files"]:
        relative_package_record(record)


def test_all_frozen_receipt_files_exist() -> None:
    for path in (
        BUILD_RECEIPT_PATH,
        GEOMETRY_INDEX_PATH,
        RUNTIME_RECEIPT_PATH,
        INDEPENDENT_PATH,
        NEGATIVE_PATH,
        DETERMINISM_PATH,
        R121_SOURCE_AUDIT_PATH,
    ):
        assert path.is_file() and path.stat().st_size > 0
