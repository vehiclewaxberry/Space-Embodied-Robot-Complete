"""NC20 backend tests: schema, nominal, malformed, missing/stale anchors,
UNKNOWN/fail-closed, deterministic replay, read-only."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from sim13_v2_backends.feasibility_evaluator import (
    EXPECTED_ANCHOR_SHA256,
    ActionBoundFeasibilityEvaluator,
    AnchorSourceError,
    TargetRequest,
    debris_150kg_3dps_request,
    resign_receipt_for_negative_control,
)


ACTION = {"grasp_candidate_id": "GC", "capture_timing_id": "T", "strategy_id": "S1"}
CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "SIM13_V2_ACTION_BOUND_FEASIBILITY_RECEIPT_SCHEMA_V1.json"
)


def test_schema_contract_declares_anchor_binding():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "SIM13_V2_ACTION_BOUND_FEASIBILITY_RECEIPT_SCHEMA_V1"
    assert "requested_action_sha256" in contract["required_payload_fields"]
    assert "MISSION_VETO_INFEASIBLE_RATE" in contract["rejection_reasons"]
    assert len(contract["anchor_set"]["sim10"]) == 4
    assert len(contract["anchor_set"]["sim12"]) == 2
    assert contract["next_stage_authorized"] is False
    assert contract["release_credit"] is False


def test_nominal_anchor_evaluation_feasibility_fail(project_root):
    evaluator = ActionBoundFeasibilityEvaluator(project_root=project_root)
    target = debris_150kg_3dps_request()
    evaluation = evaluator.evaluate(target)
    assert evaluation["feasibility_verdict"] == "FEASIBILITY_FAIL"
    assert evaluation["post_grasp_verdict"] == "POST_GRASP_STABILITY_FAIL_WHEELS_ONLY"
    assert evaluation["reason_code"] == "MISSION_VETO_INFEASIBLE_RATE"
    assert evaluation["feasibility_pass"] is False
    assert evaluation["anchor_region"] == "INFEASIBLE_RATE"
    assert evaluation["anchor_w_plus_dps"] == pytest.approx(3.0633304945807067)
    assert evaluation["sim12_max_wheel_margin_Nms"] < 0.0


def test_unknown_target_masks_to_abort(project_root):
    evaluator = ActionBoundFeasibilityEvaluator(project_root=project_root)
    unknown = TargetRequest("other_target", 22.0, 0.5)
    evaluation = evaluator.evaluate(unknown)
    assert evaluation["feasibility_verdict"] == "UNKNOWN"
    assert evaluation["feasibility_pass"] is False


def test_action_bound_receipt_roundtrip_and_drift(project_root):
    evaluator = ActionBoundFeasibilityEvaluator(project_root=project_root)
    target = debris_150kg_3dps_request()
    receipt = evaluator.issue_receipt(action=ACTION, target=target)
    admission = evaluator.verify_receipt(
        receipt=receipt, action=ACTION, target=target
    )
    # the anchor verdict is FEASIBILITY_FAIL, so the verified receipt still
    # denies the non-ABORT request with the exact veto reason
    assert admission.allowed is False
    assert admission.receipt_verified is True
    assert admission.reason_code == "MISSION_VETO_INFEASIBLE_RATE"
    drifted = evaluator.verify_receipt(
        receipt=receipt, action={**ACTION, "strategy_id": "S3a"}, target=target
    )
    assert drifted.reason_code == "FEASIBILITY_RECEIPT_ACTION_MISMATCH"


def test_malformed_and_missing_receipt_rejected(project_root):
    evaluator = ActionBoundFeasibilityEvaluator(project_root=project_root)
    target = debris_150kg_3dps_request()
    missing = evaluator.verify_receipt(receipt=None, action=ACTION, target=target)
    assert missing.reason_code == "FEASIBILITY_RECEIPT_MISSING"
    malformed = evaluator.verify_receipt(
        receipt="not-a-receipt", action=ACTION, target=target  # type: ignore[arg-type]
    )
    assert malformed.reason_code == "FEASIBILITY_RECEIPT_MALFORMED"


def test_resigned_semantic_drift_rejected(project_root):
    evaluator = ActionBoundFeasibilityEvaluator(project_root=project_root)
    target = debris_150kg_3dps_request()
    receipt = evaluator.issue_receipt(action=ACTION, target=target)
    payload = dict(receipt.payload)
    payload["evaluation"] = {
        **dict(payload["evaluation"]),
        "feasibility_pass": True,
    }
    resigned = resign_receipt_for_negative_control(payload)
    admission = evaluator.verify_receipt(receipt=resigned, action=ACTION, target=target)
    assert admission.allowed is False
    assert admission.reason_code == "FEASIBILITY_RECEIPT_EVALUATION_DRIFT"


def test_missing_anchor_source_rejected(tmp_path):
    with pytest.raises(AnchorSourceError, match="ANCHOR_SOURCE_MISSING"):
        ActionBoundFeasibilityEvaluator(project_root=tmp_path)


def _stage_anchor_tree(project_root: Path, tmp_path: Path) -> Path:
    fake = tmp_path / "fake_root"
    for relative in EXPECTED_ANCHOR_SHA256:
        target = fake / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project_root / relative, target)
    return fake


def test_stale_anchor_hash_rejected(project_root, tmp_path):
    fake = _stage_anchor_tree(project_root, tmp_path)
    target = fake / "30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv"
    payload = bytearray(target.read_bytes())
    payload[-1] ^= 0x01
    target.write_bytes(bytes(payload))
    with pytest.raises(AnchorSourceError, match="ANCHOR_SOURCE_HASH_DRIFT"):
        ActionBoundFeasibilityEvaluator(project_root=fake)


def test_deterministic_replay_identical_evaluation(project_root):
    evaluator = ActionBoundFeasibilityEvaluator(project_root=project_root)
    target = debris_150kg_3dps_request()
    first = evaluator.issue_receipt(action=ACTION, target=target).as_dict()
    second = evaluator.issue_receipt(action=ACTION, target=target).as_dict()
    assert first == second


def test_evaluator_is_read_only(project_root):
    targets = [project_root / relative for relative in EXPECTED_ANCHOR_SHA256]
    before = {path: path.read_bytes() for path in targets}
    evaluator = ActionBoundFeasibilityEvaluator(project_root=project_root)
    target = debris_150kg_3dps_request()
    evaluator.evaluate(target)
    evaluator.issue_receipt(action=ACTION, target=target)
    after = {path: path.read_bytes() for path in targets}
    assert before == after
