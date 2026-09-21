from __future__ import annotations

from copy import deepcopy
import csv
from pathlib import Path
import sys

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_joint_system_gate import (  # noqa: E402
    AUDIT_PATH,
    CONTRACT_PATH,
    RESULTS,
    ROOT,
    bind_sources,
    build,
    load_json_strict,
    loads_json_strict,
    required_package_files,
    sha256_file,
    validate_red_team_audit_document,
)


@pytest.fixture(scope="session")
def gate() -> dict:
    return build()


def test_strict_json_rejects_duplicate_keys() -> None:
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY:a"):
        loads_json_strict('{"a": false, "a": true}')


def test_all_source_pins_are_exact(gate: dict) -> None:
    contract = load_json_strict(CONTRACT_PATH)
    binding, _ = bind_sources(contract)
    assert binding["summary"] == {"matched": 19, "total": 19}
    assert binding["all_match"] is True
    assert all(row["match"] is True for row in binding["pins"])
    duplicate = dict(contract)
    duplicate["source_pins"] = contract["source_pins"] + [contract["source_pins"][0]]
    with pytest.raises(ValueError, match="DUPLICATE_SOURCE_PIN_ID"):
        bind_sources(duplicate)


def test_owner_selection_is_recorded_but_never_bypasses_admission(gate: dict) -> None:
    assert gate["conditions"]["owner_option_a_selection_recorded"] is True
    assert gate["diagnostic_facts_no_credit"]["low_memory_override_authorized"] is False
    assert gate["conditions"]["mechanical_static_preflight_pass"] is False
    assert gate["conditions"]["runtime_memory_admission_pass"] is False
    assert gate["path_search_executed"] is False


def test_dynamics_and_control_red_team_holds_propagate(gate: dict) -> None:
    assert gate["diagnostic_facts_no_credit"][
        "dynamics_DG1_coordinate_metric_bound"
    ] is False
    assert gate["diagnostic_facts_no_credit"][
        "dynamics_DG2_independent_conservation"
    ] is False
    assert gate["diagnostic_facts_no_credit"][
        "control_task_space_metric_bound_native"
    ] is False
    assert gate["diagnostic_facts_no_credit"][
        "control_both_outer_task_guards_allow_native"
    ] is False
    assert gate["conditions"]["upstream_manifest_integrity_pass"] is True
    assert all(
        item["pass"] is True
        for item in gate["upstream_manifest_audit"]["components"].values()
    )
    assert gate["dynamics_engineering_pass"] is False
    assert gate["control_engineering_pass"] is False


def test_safe_and_sim13_do_not_upgrade_to_non_abort_authority(gate: dict) -> None:
    assert gate["diagnostic_facts_no_credit"]["safe_historical_gate_verdict"] == "PASS"
    assert gate["safe_independent_review_pass"] is False
    assert gate["diagnostic_facts_no_credit"]["sim13_negative_control_score"] == "20/20"
    assert "ABORT_ONLY" in gate["diagnostic_facts_no_credit"][
        "sim13_maximum_operational_state"
    ]
    assert gate["sim13_binding_pass"] is False


def test_joint_gate_is_native_fail_closed(gate: dict) -> None:
    expected_false = (
        "mechanical_handoff_pass",
        "dynamics_engineering_pass",
        "control_engineering_pass",
        "safe_independent_review_pass",
        "sim13_binding_pass",
        "joint_system_ready",
        "ready_for_physics_gated_embodied_intelligence",
        "path_search_executed",
        "next_stage_authorized",
        "release_credit",
    )
    for field in expected_false:
        assert type(gate[field]) is bool
        assert gate[field] is False
    assert gate["unknown_auto_allow_count"] == 0
    assert gate["artifact_package_complete"] is True
    assert gate["candidate_integration_contract_bound"] is True
    assert gate["conditions"]["independent_red_team_high_findings_zero"] is True
    assert gate["independent_review"]["evidence_valid"] is True
    assert gate["independent_review"]["receipt_path"] == AUDIT_PATH.relative_to(
        PACKAGE.parents[1]
    ).as_posix()
    assert gate["independent_review"]["receipt_bytes"] == AUDIT_PATH.stat().st_size
    assert gate["independent_review"]["receipt_sha256"] == sha256_file(AUDIT_PATH)
    contract = load_json_strict(CONTRACT_PATH)
    required = contract["required_ready_conditions"]
    assert gate["required_condition_evaluation"]["names"] == required
    assert gate["required_condition_evaluation"]["total"] == len(required)
    assert gate["required_condition_evaluation"]["all_pass"] is False

    valid_review = load_json_strict(AUDIT_PATH)
    invalid_reviews = []
    swapped = deepcopy(valid_review)
    swapped["reviewed_artifacts"][0]["path"], swapped["reviewed_artifacts"][1]["path"] = (
        swapped["reviewed_artifacts"][1]["path"],
        swapped["reviewed_artifacts"][0]["path"],
    )
    invalid_reviews.append(swapped)
    wrong = deepcopy(valid_review)
    wrong["reviewed_artifacts"][0]["path"] = "PROJECT_MAP.md"
    invalid_reviews.append(wrong)
    absolute = deepcopy(valid_review)
    absolute["reviewed_artifacts"][0]["path"] = str(
        (ROOT / valid_review["reviewed_artifacts"][0]["path"]).resolve()
    )
    invalid_reviews.append(absolute)
    traversal = deepcopy(valid_review)
    traversal["reviewed_artifacts"][0]["path"] = "../PROJECT_MAP.md"
    invalid_reviews.append(traversal)
    extra = deepcopy(valid_review)
    extra_row = deepcopy(extra["reviewed_artifacts"][0])
    extra_row["id"] = "extra_review_target"
    extra["reviewed_artifacts"].append(extra_row)
    invalid_reviews.append(extra)
    bool_count = deepcopy(valid_review)
    bool_count["open_high_findings_count"] = False
    invalid_reviews.append(bool_count)
    bool_bytes = deepcopy(valid_review)
    bool_bytes["reviewed_artifacts"][0]["bytes"] = False
    invalid_reviews.append(bool_bytes)
    lowercase_hash = deepcopy(valid_review)
    lowercase_hash["reviewed_artifacts"][0]["sha256"] = lowercase_hash[
        "reviewed_artifacts"
    ][0]["sha256"].lower()
    invalid_reviews.append(lowercase_hash)
    empty_reviewer = deepcopy(valid_review)
    empty_reviewer["reviewer"] = "  "
    invalid_reviews.append(empty_reviewer)
    for invalid in invalid_reviews:
        assert validate_red_team_audit_document(invalid)["evidence_valid"] is False


def test_required_package_manifest_is_exact(gate: dict) -> None:
    required = required_package_files()
    manifest = RESULTS / "R2_DYNAMICS_CONTROL_SHA256_V1.csv"
    with manifest.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["path"] for row in rows] == [
        path.relative_to(PACKAGE).as_posix() for path in required
    ]
    assert AUDIT_PATH.is_file()
    assert AUDIT_PATH.relative_to(PACKAGE).as_posix() in {
        row["path"] for row in rows
    }
    for row, path in zip(rows, required, strict=True):
        assert int(row["bytes"]) == path.stat().st_size
        assert row["sha256"] == sha256_file(path)
