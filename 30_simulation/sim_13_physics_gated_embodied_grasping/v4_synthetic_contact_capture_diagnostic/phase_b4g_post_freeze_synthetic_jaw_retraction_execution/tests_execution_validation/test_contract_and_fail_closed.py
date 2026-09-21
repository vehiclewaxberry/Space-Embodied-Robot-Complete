from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from b4g_validation.core import (
    DuplicateKeyError,
    ValidationReport,
    canonical_bytes,
    canonical_sha256,
    read_json_strict,
)
from b4g_validation import validator


def test_contract_and_preregistration_preflight_is_clean() -> None:
    report = validator.validate_b4g(mode="contracts")
    assert report.passed, report.failures
    assert report.checks == 367
    assert report.observations["contract_and_preregistration"] == {
        "contract_files": 9,
        "bound_parent_files": 11,
        "registered_total_slots": 144,
        "lane_count": 6,
        "slots_per_lane": 24,
    }


def test_campaign_mode_fails_closed_when_campaign_tree_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(validator, "EVIDENCE_ROOT", tmp_path / "evidence")
    monkeypatch.setattr(validator, "RESULTS_ROOT", tmp_path / "results")
    report = validator.validate_b4g(mode="campaign")
    assert not report.passed
    codes = {item["code"] for item in report.failures}
    assert codes == {
        "CAMPAIGN_PRE_MISSING", "CAMPAIGN_SOURCE_MISSING",
        "CAMPAIGN_REFERENCE_MISSING", "CAMPAIGN_SCHEDULE_MISSING",
        "CAMPAIGN_A0_PARENT_MISSING",
        "CAMPAIGN_POST_MISSING", "CAMPAIGN_SUMMARY_MISSING",
    }


def test_strict_json_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_bytes(b'{"a":1,"a":2}\n')
    with pytest.raises(ValueError, match="JSON_STRICT_READ_FAILED"):
        read_json_strict(path)


def test_strict_json_rejects_overflow_to_infinity(tmp_path: Path) -> None:
    path = tmp_path / "overflow.json"
    path.write_bytes(b'{"value":1e999}\n')
    with pytest.raises(ValueError, match="JSON_STRICT_READ_FAILED"):
        read_json_strict(path)


def test_registered_slot_payload_hash_is_exact() -> None:
    schedule = read_json_strict(validator.CONTRACT_ROOT / "PHASE_B4G_REGISTERED_SCHEDULE_V1.json")
    assert schedule["slot_count"] == 144
    assert canonical_sha256(schedule["slots"]) == "21642ED06620E589ABB854CCFE936EC2C84D9571ACACA86F690ACC5DB2D78137"
    lane_counts = {lane: sum(slot["lane_id"] == lane for slot in schedule["slots"]) for lane in validator.LANES}
    assert lane_counts == {lane: 24 for lane in validator.LANES}


def test_independent_source_inventory_is_complete_and_prepruned(tmp_path: Path) -> None:
    project = tmp_path / "project"
    phase = project / "phase"
    (phase / "contracts").mkdir(parents=True)
    (phase / "b4g_validation").mkdir()
    (phase / "nested").mkdir()
    (phase / "evidence").mkdir()
    (phase / ".pytest_generated" / "arbitrarily" / "deep").mkdir(parents=True)
    (phase / ".smoke_probe").mkdir()
    (phase / "raw_cases").mkdir()
    (phase / "runner.py").write_text("RUNNER = True\n", encoding="utf-8")
    (phase / "nested" / "worker.py").write_text("WORKER = True\n", encoding="utf-8")
    (phase / "contracts" / "FROZEN.json").write_text("{}\n", encoding="utf-8")
    interchange_name = "PHASE_B4G_VALIDATOR_RAW_INTERFACE_V1.json"
    (phase / "b4g_validation" / interchange_name).write_text("{}\n", encoding="utf-8")
    (phase / "b4g_validation" / "derived.json").write_text("{}\n", encoding="utf-8")
    (phase / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (phase / "evidence" / "coordinated_omission.py").write_text("BAD = True\n", encoding="utf-8")
    (phase / ".pytest_generated" / "arbitrarily" / "deep" / "hidden.py").write_text("BAD = True\n", encoding="utf-8")
    (phase / ".smoke_probe" / "hidden.py").write_text("BAD = True\n", encoding="utf-8")
    (phase / "raw_cases" / "hidden.py").write_text("BAD = True\n", encoding="utf-8")

    inventory = validator._independent_local_source_inventory(project, phase)
    assert [row["id"] for row in inventory] == [
        f"local::b4g_validation/{interchange_name}",
        "local::contracts/FROZEN.json",
        "local::nested/worker.py",
        "local::pytest.ini",
        "local::runner.py",
    ]
    assert all(row["role"] == "B4G_FROZEN_CONTRACT_SOURCE_TEST_OR_WORKFLOW" for row in inventory)
    business_files = {
        path.relative_to(phase).as_posix()
        for path in validator._walk_phase_files_prepruned(
            phase, exclude_source_derived_trees=False,
        )
    }
    assert "evidence/coordinated_omission.py" in business_files
    assert not any(path.startswith(".pytest_generated/") for path in business_files)
    assert not any(path.startswith(".smoke_probe/") for path in business_files)


def test_coordinated_identity_and_freeze_omission_fails_independent_inventory(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    phase = project / "phase"
    phase.mkdir(parents=True)
    (phase / "first.py").write_text("FIRST = True\n", encoding="utf-8")
    (phase / "second.py").write_text("SECOND = True\n", encoding="utf-8")
    inventory = validator._independent_local_source_inventory(project, phase)
    coordinated_omission = inventory[:-1]
    omitted_freeze = {
        (row["path"], row["bytes"], row["sha256"])
        for row in coordinated_omission
    }
    report = ValidationReport(mode="campaign")
    validator._validate_independent_local_source_inventory(
        report,
        coordinated_omission,
        omitted_freeze,
        project_root=project,
        phase_root=phase,
    )
    assert not report.passed
    assert {failure["code"] for failure in report.failures} == {
        "CAMPAIGN_LOCAL_SOURCE_NOT_EXACT_INDEPENDENT_ALLOWLIST_INVENTORY",
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_NOT_EXACT_INDEPENDENT_ALLOWLIST_INVENTORY",
    }


@pytest.mark.parametrize("mode", ["contracts", "campaign", "full"])
def test_incomplete_mutation_marker_fails_every_semantic_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str,
) -> None:
    marker = (
        tmp_path / "b4g_mutation_execution"
        / "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
    )
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"not-even-json")
    monkeypatch.setattr(validator, "PHASE_ROOT", tmp_path)
    report = validator.validate_b4g(mode=mode)
    assert not report.passed
    assert "MUTATION_EXECUTION_INCOMPLETE_MARKER_PRESENT" in {
        failure["code"] for failure in report.failures
    }


@pytest.mark.parametrize(
    ("filename", "schema", "code"),
    [
        (
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json",
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1",
            "EXECUTION_INVALIDATED_MARKER_ACTIVE_NOT_FALSE",
        ),
        (
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json",
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1",
            "PRIOR_FINAL_CREDIT_SUPERSEDED_MARKER_ACTIVE_NOT_FALSE",
        ),
    ],
)
def test_active_attempt_marker_fails_closed(
    tmp_path: Path, filename: str, schema: str, code: str,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    (results / filename).write_bytes(
        canonical_bytes({"schema": schema, "active": True}) + b"\n"
    )
    report = ValidationReport(mode="campaign")
    validator._validate_attempt_state_markers(report, tmp_path)
    assert not report.passed
    assert code in {failure["code"] for failure in report.failures}


@pytest.mark.parametrize(
    ("filename", "code"),
    [
        (
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json",
            "EXECUTION_INVALIDATED_MARKER_INVALID_STRICT_JSON",
        ),
        (
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json",
            "PRIOR_FINAL_CREDIT_SUPERSEDED_MARKER_INVALID_STRICT_JSON",
        ),
    ],
)
def test_malformed_attempt_marker_fails_closed(
    tmp_path: Path, filename: str, code: str,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    (results / filename).write_bytes(b'{"schema":')
    report = ValidationReport(mode="campaign")
    validator._validate_attempt_state_markers(report, tmp_path)
    assert not report.passed
    assert code in {failure["code"] for failure in report.failures}


@pytest.mark.parametrize(
    ("filename", "schema", "code"),
    [
        (
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json",
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1",
            "EXECUTION_INVALIDATED_MARKER_NOT_CANONICAL_SORTED_COMPACT_LF",
        ),
        (
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json",
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1",
            "PRIOR_FINAL_CREDIT_SUPERSEDED_MARKER_NOT_CANONICAL_SORTED_COMPACT_LF",
        ),
    ],
)
def test_noncanonical_inactive_attempt_marker_fails_closed(
    tmp_path: Path, filename: str, schema: str, code: str,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    (results / filename).write_text(
        json.dumps({"schema": schema, "active": False}, indent=2) + "\n",
        encoding="utf-8",
    )
    report = ValidationReport(mode="campaign")
    validator._validate_attempt_state_markers(report, tmp_path)
    assert not report.passed
    assert code in {failure["code"] for failure in report.failures}


@pytest.mark.parametrize(
    ("filename", "code"),
    [
        (
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json",
            "EXECUTION_INVALIDATED_MARKER_SCHEMA_MISMATCH",
        ),
        (
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json",
            "PRIOR_FINAL_CREDIT_SUPERSEDED_MARKER_SCHEMA_MISMATCH",
        ),
    ],
)
def test_wrong_schema_inactive_attempt_marker_fails_closed(
    tmp_path: Path, filename: str, code: str,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    (results / filename).write_bytes(
        canonical_bytes({"schema": "WRONG_SCHEMA", "active": False}) + b"\n"
    )
    report = ValidationReport(mode="campaign")
    validator._validate_attempt_state_markers(report, tmp_path)
    assert not report.passed
    assert code in {failure["code"] for failure in report.failures}


def test_attempt_marker_directory_fails_before_json_read(tmp_path: Path) -> None:
    marker = tmp_path / "results" / "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json"
    marker.mkdir(parents=True)
    report = ValidationReport(mode="campaign")
    validator._validate_attempt_state_markers(report, tmp_path)
    assert "EXECUTION_INVALIDATED_MARKER_NOT_NON_SYMLINK_REGULAR_FILE" in {
        failure["code"] for failure in report.failures
    }


def test_valid_external_inactive_marker_symlink_fails_closed(tmp_path: Path) -> None:
    external = tmp_path.parent / f"{tmp_path.name}_external_inactive.json"
    external.write_bytes(
        canonical_bytes({
            "schema": "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1",
            "active": False,
        }) + b"\n"
    )
    marker = (
        tmp_path / "results"
        / "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json"
    )
    marker.parent.mkdir()
    try:
        marker.symlink_to(external)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlink unavailable in this environment: {error}")
    report = ValidationReport(mode="campaign")
    validator._validate_attempt_state_markers(report, tmp_path)
    assert "PRIOR_FINAL_CREDIT_SUPERSEDED_MARKER_NOT_NON_SYMLINK_REGULAR_FILE" in {
        failure["code"] for failure in report.failures
    }


def test_broken_attempt_marker_symlink_fails_closed(tmp_path: Path) -> None:
    marker = tmp_path / "results" / "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json"
    marker.parent.mkdir()
    missing_target = tmp_path.parent / f"{tmp_path.name}_does_not_exist.json"
    try:
        marker.symlink_to(missing_target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlink unavailable in this environment: {error}")
    assert os.path.lexists(marker)
    assert not marker.exists()
    report = ValidationReport(mode="campaign")
    validator._validate_attempt_state_markers(report, tmp_path)
    assert "EXECUTION_INVALIDATED_MARKER_NOT_NON_SYMLINK_REGULAR_FILE" in {
        failure["code"] for failure in report.failures
    }


def test_inactive_receipts_cannot_mask_incomplete_mutation_marker(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    for filename, schema in (
        (
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json",
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1",
        ),
        (
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json",
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1",
        ),
    ):
        (results / filename).write_bytes(
            canonical_bytes({"schema": schema, "active": False}) + b"\n"
        )
    incomplete = (
        tmp_path / "b4g_mutation_execution"
        / "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
    )
    incomplete.parent.mkdir()
    incomplete.write_bytes(b"{}\n")
    report = ValidationReport(mode="full")
    validator._validate_attempt_state_markers(report, tmp_path)
    assert {failure["code"] for failure in report.failures} == {
        "MUTATION_EXECUTION_INCOMPLETE_MARKER_PRESENT",
    }
