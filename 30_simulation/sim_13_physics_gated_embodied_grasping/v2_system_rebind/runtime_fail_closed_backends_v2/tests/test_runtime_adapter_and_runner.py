"""Runtime adapter join tests and NC-runner/evidence determinism tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import run_negative_controls_backends_v2 as runner
from sim13_v2_backends.canonical import canonical_digest
from sim13_v2_backends.capability import ShieldAttestationAuthority
from sim13_v2_backends.feasibility_evaluator import debris_150kg_3dps_request
from sim13_v2_backends.runtime_gate_adapter import CANONICAL_ABORT_ACTION
from sim13_v2_backends.snapshot_receipt import SnapshotReceiptAuthority


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def context(tmp_path):
    return runner.build_context(tmp_path)


def _admit_once(context, store_name, *, receipt=True, capability=True, feasibility="issue"):
    adapter, authority, action, exec_context, snapshot, snap_receipt, cap_token = (
        runner._issue_valid_pair(context, store_name, f"RUN_{store_name}", store_name)
    )
    target = debris_150kg_3dps_request()
    fee_receipt = None
    if feasibility == "issue":
        fee_receipt = context.feasibility_evaluator.issue_receipt(
            action=action, target=target
        )
    return adapter.admit(
        action=action,
        context=exec_context,
        gate_snapshot=snapshot,
        snapshot_receipt=snap_receipt if receipt else None,
        capability_token=cap_token if capability else None,
        target=target,
        feasibility_receipt=fee_receipt,
        now_s=context.clock.read(),
    )


def test_abort_action_always_available(context):
    adapter = context.fresh_adapter("abort_store")
    decision = adapter.admit(
        action=CANONICAL_ABORT_ACTION,
        context=runner.context_fixture("RUN_ABORT"),
        gate_snapshot=runner.gate_snapshot_fixture(),
        snapshot_receipt=None,
        capability_token=None,
        now_s=context.clock.read(),
    )
    assert decision.allowed is True
    assert decision.reason_code == "ABORT_ALWAYS_AVAILABLE"


def test_missing_receipt_masks_to_abort(context):
    decision = _admit_once(context, "missing_receipt", receipt=False)
    assert decision.intervened is True
    assert decision.executed_action == CANONICAL_ABORT_ACTION
    assert decision.reason_code == "SNAPSHOT_REJECTED_RECEIPT_MISSING"


def test_unshielded_call_masks_to_abort(context):
    decision = _admit_once(context, "unshielded", capability=False)
    assert decision.intervened is True
    assert decision.executed_action == CANONICAL_ABORT_ACTION
    assert decision.reason_code == "BACKEND_REJECTS_UNSHIELDED_NON_ABORT"


def test_150kg_non_abort_without_feasibility_pass_masks_to_abort(context):
    veto = _admit_once(context, "veto")
    assert veto.intervened is True
    assert veto.executed_action == CANONICAL_ABORT_ACTION
    assert veto.reason_code == "MISSION_VETO_INFEASIBLE_RATE"
    missing = _admit_once(context, "missing_fee", feasibility="none")
    assert missing.reason_code == "FEASIBILITY_RECEIPT_MISSING"
    assert missing.executed_action == CANONICAL_ABORT_ACTION


def test_runner_package_deterministic_replay(tmp_path):
    first = runner.build_package()["evidence"]
    second = runner.build_package()["evidence"]
    assert canonical_digest(first) == canonical_digest(second)
    assert first == second


def test_runner_summary_five_of_five():
    package = runner.build_package()
    summary = package["evidence"]["summary"]
    assert summary == {"total": 5, "executed": 5, "passed": 5, "failed": 0}
    assert package["dynamics_receipt"]["all_checks_pass"] is True
    assert package["contact_receipt"]["all_checks_pass"] is True
    gates = runner.build_gate_documents(package)
    assert gates["runtime"]["gate_passed"] is True
    assert gates["dynamics"]["gate_passed"] is True
    assert gates["contact"]["gate_passed"] is True
    for gate in gates.values():
        assert gate["review_status"] == "PENDING_OWNER_REVIEW"
        assert gate["next_stage_authorized"] is False
        assert gate["release_credit"] is False


def test_emitted_evidence_files_match_fresh_build():
    package = runner.build_package()
    on_disk = json.loads(
        (PACKAGE_ROOT / "evidence" / "SIM13_V2_BACKENDS_NEGATIVE_CONTROLS_V2.json")
        .read_bytes()
        .decode("utf-8")
    )
    assert on_disk == package["evidence"]
    for name in (
        "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2.json",
        "SIM13_DYNAMICS_BACKEND_GATE_V2.json",
        "SIM13_CONTACT_GRASP_GATE_V2.json",
    ):
        gate = json.loads(
            (PACKAGE_ROOT / "results" / name).read_bytes().decode("utf-8")
        )
        assert gate["gate_passed"] is True
        assert gate["next_stage_authorized"] is False
        assert gate["release_credit"] is False


def test_historical_prebind_evidence_not_modified(project_root):
    historical = (
        project_root
        / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
        / "evidence/SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1.json"
    )
    digest_before = historical.read_bytes()
    runner.build_package()
    assert historical.read_bytes() == digest_before
