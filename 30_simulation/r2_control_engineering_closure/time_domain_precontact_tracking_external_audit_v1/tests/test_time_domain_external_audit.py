from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_time_domain_external_audit_tests", ROOT / "audit_external.py")
assert spec is not None and spec.loader is not None
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


@pytest.fixture(scope="session")
def receipt():
    return audit.validate()


@pytest.mark.parametrize("check_id", [f"A{i:02d}" for i in range(1, 19)])
def test_each_external_check_passes(receipt, check_id):
    row = next(value for key, value in receipt["checks"].items() if key.startswith(check_id + "_"))
    assert row is True


def test_verdict_and_original_negative_gate_are_truthful(receipt):
    assert receipt["passed"] == receipt["total"] == 18
    assert receipt["technical_verdict"] == audit.PASS_VERDICT
    assert receipt["maximum_claim"] == audit.PASS_VERDICT
    assert receipt["original_candidate_gate"] == {
        "passed": 19,
        "total": 20,
        "gate_passed": False,
        "failed": [audit.EXPECTED_CANDIDATE_FAILURE],
        "reissued": False,
    }
    assert receipt["metric_parent_rebind"] == {
        "passed": 16,
        "total": 16,
        "gate_passed": True,
        "original_gate_reissued": False,
    }


def test_four_histories_not_conflated_with_three_labels(receipt):
    assert len(receipt["recomputed_scenarios"]) == 4
    assert {row["id"].split("_")[0] for row in receipt["recomputed_scenarios"]} == {"C0", "C1", "C2"}
    assert set(receipt["recomputed_comparisons"]) == {"PAIR_5D", "PAIR_6D"}


def test_units_memory_momentum_and_permissions_remain_bounded(receipt):
    assert receipt["execution_memory_admission"]["admission_samples_gib"] == [6.17, 6.26, 6.26]
    assert receipt["execution_memory_admission"]["scientific_or_release_authority"] is False
    assert receipt["momentum_reference"]["angular"] == "ABOUT_FIXED_INERTIAL_ORIGIN_O"
    assert receipt["momentum_reference"]["mixed_scalar_norm_credit"] is False
    for key in (
        "precontact_tracking_validated", "pose_or_attitude_tracking_validated",
        "control_valid", "hardware_valid", "collision_valid", "contact_valid",
        "flex_valid", "m01_path_bound", "safe_gate_credit", "sim13_credit",
        "non_abort_authorized", "next_stage_authorized", "release_credit",
    ):
        assert receipt[key] is False
    expected_authorities = {
        "parent_gate_reissued", "parent_gate_credit",
        "original_candidate_gate_reissued", "task_metric_parent_gate_reissued",
        "parent_dynamics_or_control_gate_credit", "precontact_tracking_validated",
        "pose_or_attitude_tracking_validated", "control_valid", "hardware_valid",
        "collision_valid", "contact_valid", "flex_valid", "target_attached",
        "m01_path_bound", "safe_gate_credit", "sim13_credit",
        "non_abort_authorized", "next_stage_authorized", "release_credit",
    }
    assert set(receipt["authority_boundaries"]) == expected_authorities
    assert all(value is False for value in receipt["authority_boundaries"].values())


def test_external_negative_controls_all_caught(receipt):
    assert receipt["negative_controls"]["passed"] == receipt["negative_controls"]["total"] == 12
    assert receipt["negative_controls"]["all_pass"] is True
    assert all(row["caught"] for row in receipt["negative_controls"]["records"])


def test_strict_inventory_rejects_missing_and_extra():
    exact = set(audit.AUDIT_ALLOWED_FILES)
    assert audit.inventory_exact(exact, audit.AUDIT_ALLOWED_FILES)
    assert not audit.inventory_exact(exact - {"README.md"}, audit.AUDIT_ALLOWED_FILES)
    assert not audit.inventory_exact(exact | {"rogue.txt"}, audit.AUDIT_ALLOWED_FILES)
