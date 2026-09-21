from __future__ import annotations

from copy import deepcopy

import pytest

from sim13_v4.mission_veto import (
    ANCHOR_REGION,
    ANCHOR_W_PLUS_DPS,
    EXPECTED_SIM10_ANCHOR_SOURCE_SHA256,
    EXPECTED_SIM10_GATE_SHA256,
    EXPECTED_SIM10_PARAMETER_CARD_SHA256,
    EXPECTED_SIM10_SUMMARY_SHA256,
    Sim10MissionVeto,
    TargetRequest,
    VetoReceipt,
    debris_150kg_3dps_request,
    diagnostic_resign_veto_payload,
    sim10_artifact_records,
)
from sim13_v4.diagnostic_backend import (
    DiagnosticExecutionCoordinator,
    SyntheticCapabilityBackend,
    build_execution_context,
    debris_veto_policy_fixture,
    initial_diagnostic_state,
    nominal_generalized_effort,
)
from sim13_v4.runtime_guard import (
    DiagnosticAction,
    DiagnosticClock,
    DiagnosticShield,
    NonceLedger,
    synthetic_gate_snapshot,
)


def _fixture():
    action = DiagnosticAction("GC_DEBRIS", "T_CAPTURE", "S1")
    snapshot = synthetic_gate_snapshot()
    target = debris_150kg_3dps_request()
    evaluator = Sim10MissionVeto()
    receipt = evaluator.issue_veto_receipt(
        action=action,
        gate_snapshot=snapshot,
        target=target,
    )
    return action, snapshot, target, evaluator, receipt


def test_sim10_gate_and_summary_are_read_only_hash_bound() -> None:
    records = sim10_artifact_records()
    assert records["gate"]["sha256"] == EXPECTED_SIM10_GATE_SHA256
    assert records["summary"]["sha256"] == EXPECTED_SIM10_SUMMARY_SHA256
    assert records["parameter_card"]["sha256"] == EXPECTED_SIM10_PARAMETER_CARD_SHA256
    assert records["anchor_source"]["sha256"] == EXPECTED_SIM10_ANCHOR_SOURCE_SHA256


def test_valid_150kg_3dps_receipt_vetoes_non_abort() -> None:
    action, snapshot, target, evaluator, receipt = _fixture()
    decision = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=receipt,
    )
    assert decision.allowed is False and decision.executed_action.is_abort
    assert decision.reason_code == "MISSION_VETO_INFEASIBLE_RATE"
    assert decision.receipt_verified is True
    assert decision.historical_sim10_pass_inherited_to_current_system is False
    assert receipt.payload["anchor_region"] == ANCHOR_REGION
    assert receipt.payload["anchor_w_plus_dps"] == ANCHOR_W_PLUS_DPS
    assert receipt.payload["current_r2_feasibility_passed"] is False
    assert receipt.payload["mass_speed_source_proof"] == {
        "parameter_card_calibration_mass_kg": 150.0,
        "anchor_source_target_mass_kg": 150.0,
        "anchor_source_tumble_rate_dps": 3.0,
    }


def test_missing_receipt_is_unknown_and_aborts() -> None:
    action, snapshot, target, evaluator, _ = _fixture()
    decision = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=None,
    )
    assert decision.executed_action.is_abort
    assert decision.reason_code == "SIM10_VETO_RECEIPT_UNKNOWN"


def test_receipt_action_mismatch_aborts() -> None:
    action, snapshot, target, evaluator, receipt = _fixture()
    other = DiagnosticAction("GC_OTHER", action.capture_timing_id, action.strategy_id)
    decision = evaluator.decide(
        action=other,
        gate_snapshot=snapshot,
        target=target,
        receipt=receipt,
    )
    assert decision.executed_action.is_abort
    assert decision.reason_code == "SIM10_VETO_RECEIPT_ACTION_MISMATCH"


def test_receipt_snapshot_mismatch_aborts() -> None:
    action, _, target, evaluator, receipt = _fixture()
    changed = synthetic_gate_snapshot(overrides={"sim10_gate": "UNKNOWN"})
    decision = evaluator.decide(
        action=action,
        gate_snapshot=changed,
        target=target,
        receipt=receipt,
    )
    assert decision.executed_action.is_abort
    assert decision.reason_code == "SIM10_VETO_RECEIPT_SNAPSHOT_MISMATCH"


def test_receipt_target_mismatch_aborts() -> None:
    action, snapshot, _, evaluator, receipt = _fixture()
    changed_target = TargetRequest("target_debris_v0", 151.0, 3.0)
    decision = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=changed_target,
        receipt=receipt,
    )
    assert decision.executed_action.is_abort
    assert decision.reason_code == "SIM10_VETO_RECEIPT_TARGET_MISMATCH"


def test_semantically_resigned_anchor_drift_still_aborts() -> None:
    action, snapshot, target, evaluator, receipt = _fixture()
    payload = deepcopy(dict(receipt.payload))
    payload["anchor_id"] = "unknown_anchor"
    drifted = diagnostic_resign_veto_payload(payload)
    decision = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=drifted,
    )
    assert decision.executed_action.is_abort
    assert decision.reason_code == "SIM10_VETO_RECEIPT_ANCHOR_DRIFT"


def test_semantically_resigned_hash_drift_still_aborts() -> None:
    action, snapshot, target, evaluator, receipt = _fixture()
    payload = deepcopy(dict(receipt.payload))
    payload["sim10_summary_sha256"] = "0" * 64
    drifted = diagnostic_resign_veto_payload(payload)
    decision = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=drifted,
    )
    assert decision.executed_action.is_abort
    assert decision.reason_code == "SIM10_VETO_RECEIPT_HASH_DRIFT"


def test_unsigned_receipt_tamper_aborts() -> None:
    action, snapshot, target, evaluator, receipt = _fixture()
    tampered = VetoReceipt(receipt.payload, "F" * 64)
    decision = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=tampered,
    )
    assert decision.executed_action.is_abort
    assert decision.reason_code == "SIM10_VETO_RECEIPT_SIGNATURE_INVALID"


def test_resigned_non_numeric_or_malformed_fields_abort_without_exception() -> None:
    action, snapshot, target, evaluator, receipt = _fixture()
    mutations = (
        ("anchor_w_plus_dps", "not-a-number"),
        ("anchor_w_plus_dps", [3.0633304945807067]),
        ("mass_speed_source_proof", "not-a-mapping"),
        (
            "mass_speed_source_proof",
            {
                "parameter_card_calibration_mass_kg": "150",
                "anchor_source_target_mass_kg": 150.0,
                "anchor_source_tumble_rate_dps": 3.0,
            },
        ),
    )
    for field, value in mutations:
        payload = deepcopy(dict(receipt.payload))
        payload[field] = value
        malformed = diagnostic_resign_veto_payload(payload)
        decision = evaluator.decide(
            action=action,
            gate_snapshot=snapshot,
            target=target,
            receipt=malformed,
        )
        assert decision.executed_action.is_abort
        assert decision.reason_code == "SIM10_VETO_RECEIPT_MALFORMED_TYPE"
    malformed_container = VetoReceipt(  # type: ignore[arg-type]
        ["not", "a", "mapping"], "0" * 64
    )
    decision = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=malformed_container,
    )
    assert decision.executed_action.is_abort
    assert decision.reason_code == "SIM10_VETO_RECEIPT_MALFORMED_TYPE"


def test_debris_veto_is_composed_before_capability_and_backend_for_all_fail_closed_cases() -> None:
    action, snapshot, target, evaluator, receipt = _fixture()
    state = initial_diagnostic_state()
    effort = nominal_generalized_effort()
    policy = debris_veto_policy_fixture(target)
    context = build_execution_context(
        run_id="SIM13-V4-NC20-COMPOSED",
        state=state,
        generalized_effort=effort,
        step_s=0.001,
        steps=3,
        target_policy_fixture=policy,
    )
    nonce = "NC20-COMPOSED-PREBACKEND"
    shield = DiagnosticShield(clock=DiagnosticClock(3000.0))
    capability = shield.issue_capability(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        nonce=nonce,
        validity_window_s=2.0,
    )
    receipt_mutations = {
        "action_drift": ("action_sha256", "0" * 64, "SIM10_VETO_RECEIPT_ACTION_MISMATCH"),
        "snapshot_drift": (
            "gate_snapshot_sha256",
            "0" * 64,
            "SIM10_VETO_RECEIPT_SNAPSHOT_MISMATCH",
        ),
        "target_drift": ("target_sha256", "0" * 64, "SIM10_VETO_RECEIPT_TARGET_MISMATCH"),
        "anchor_drift": ("anchor_id", "unknown_anchor", "SIM10_VETO_RECEIPT_ANCHOR_DRIFT"),
        "hash_drift": ("sim10_gate_sha256", "0" * 64, "SIM10_VETO_RECEIPT_HASH_DRIFT"),
        "malformed_numeric": (
            "anchor_w_plus_dps",
            "not-a-number",
            "SIM10_VETO_RECEIPT_MALFORMED_TYPE",
        ),
    }
    drifted_receipts = []
    for _, (field, value, reason) in receipt_mutations.items():
        drift_payload = deepcopy(dict(receipt.payload))
        drift_payload[field] = value
        drifted_receipts.append((diagnostic_resign_veto_payload(drift_payload), reason))
    cases = (
        (None, "SIM10_VETO_RECEIPT_UNKNOWN"),
        (receipt, "MISSION_VETO_INFEASIBLE_RATE"),
        *drifted_receipts,
    )
    coordinator = DiagnosticExecutionCoordinator()
    before_digest = state.as_dict()
    for candidate_receipt, expected_reason in cases:
        result = coordinator.execute(
            action=action,
            state=state,
            generalized_effort=effort,
            step_s=0.001,
            steps=3,
            context=context,
            gate_snapshot=snapshot,
            capability=capability,
            shield=shield,
            target_policy_fixture=policy,
            mission_veto_receipt=candidate_receipt,
        )
        assert result.executed_action.is_abort
        assert result.coordinator_reason_code == expected_reason
        assert result.backend_invocation_delta == 0
        assert result.capability_consumed is False
        assert result.before.as_dict() == before_digest
        assert result.after.as_dict() == before_digest
    assert coordinator.backend_invocation_count == 0
    assert NonceLedger().is_consumed(nonce) is False
    with pytest.raises(PermissionError) as caught:
        SyntheticCapabilityBackend().execute(capability=capability)
    assert str(caught.value) == "BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR"
