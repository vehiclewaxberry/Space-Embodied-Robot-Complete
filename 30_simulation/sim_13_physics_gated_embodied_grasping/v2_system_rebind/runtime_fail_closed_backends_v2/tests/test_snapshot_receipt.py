"""NC15 backend tests: schema, nominal, malformed, stale, replay, fail-closed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sim13_v2_backends.snapshot_receipt import (
    FileReplayStore,
    InjectedClock,
    SnapshotReceiptAuthority,
    resign_receipt_for_negative_control,
)


ACTION = {"grasp_candidate_id": "GC", "capture_timing_id": "T", "strategy_id": "S1"}
CONTEXT = {"schema": "CTX", "run_id": "R1", "backend_id": "B1"}
SNAPSHOT = {"schema": "SNAP", "gates": {"g1": "PASS"}}
CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "SIM13_V2_GATE_SNAPSHOT_RECEIPT_SCHEMA_V1.json"
)


def _authority() -> tuple[SnapshotReceiptAuthority, InjectedClock]:
    clock = InjectedClock(100.0)
    return SnapshotReceiptAuthority(clock=clock), clock


def _issue(authority: SnapshotReceiptAuthority, nonce: str = "N1", window: float = 2.0):
    return authority.issue_receipt(
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        nonce=nonce,
        validity_window_s=window,
    )


def test_schema_contract_declares_required_fields():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "SIM13_V2_GATE_SNAPSHOT_RECEIPT_SCHEMA_V1"
    for field in (
        "action_sha256",
        "context_sha256",
        "gate_snapshot_sha256",
        "nonce",
        "issued_at_s",
        "expires_at_s",
    ):
        assert field in contract["required_payload_fields"]
    assert contract["next_stage_authorized"] is False
    assert contract["release_credit"] is False
    assert "SNAPSHOT_REJECTED_STALE" in contract["rejection_reasons"]
    assert "SNAPSHOT_REJECTED_NONCE_REPLAY" in contract["rejection_reasons"]


def test_nominal_fresh_receipt_admitted_once(tmp_path):
    authority, _ = _authority()
    store = FileReplayStore(tmp_path / "store")
    receipt = _issue(authority)
    decision = authority.verify_and_consume(
        receipt=receipt,
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        replay_store=store,
    )
    assert decision.allowed is True
    assert decision.reason_code == "SNAPSHOT_RECEIPT_ACCEPTED_ONCE"
    assert decision.consumed_nonce == "N1"


def test_malformed_receipt_rejected(tmp_path):
    authority, _ = _authority()
    store = FileReplayStore(tmp_path / "store")
    decision = authority.verify_and_consume(
        receipt="not-a-receipt",  # type: ignore[arg-type]
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        replay_store=store,
    )
    assert decision.allowed is False
    assert decision.reason_code == "SNAPSHOT_REJECTED_MALFORMED"
    missing = authority.verify_and_consume(
        receipt=None,
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        replay_store=store,
    )
    assert missing.reason_code == "SNAPSHOT_REJECTED_RECEIPT_MISSING"


def test_tampered_signature_rejected(tmp_path):
    authority, _ = _authority()
    store = FileReplayStore(tmp_path / "store")
    receipt = _issue(authority)
    payload = dict(receipt.payload)
    payload["nonce"] = "N1"  # same nonce but flip a binding field
    payload["action_sha256"] = "0" * 64
    tampered = type(receipt)(payload, receipt.signature_hmac_sha256)
    decision = authority.verify_and_consume(
        receipt=tampered,
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        replay_store=store,
    )
    assert decision.allowed is False
    assert decision.reason_code == "SNAPSHOT_REJECTED_SIGNATURE_INVALID"


def test_stale_receipt_rejected(tmp_path):
    authority, clock = _authority()
    store = FileReplayStore(tmp_path / "store")
    receipt = _issue(authority)
    clock.advance(10.0)
    decision = authority.verify_and_consume(
        receipt=receipt,
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        replay_store=store,
    )
    assert decision.allowed is False
    assert decision.reason_code == "SNAPSHOT_REJECTED_STALE"
    assert store.consumed_count == 0  # stale receipts never consume the nonce


def test_replayed_nonce_rejected_single_use(tmp_path):
    authority, _ = _authority()
    store = FileReplayStore(tmp_path / "store")
    receipt = _issue(authority)
    first = authority.verify_and_consume(
        receipt=receipt,
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        replay_store=store,
    )
    second = authority.verify_and_consume(
        receipt=receipt,
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        replay_store=store,
    )
    assert first.allowed is True
    assert second.allowed is False
    assert second.reason_code == "SNAPSHOT_REJECTED_NONCE_REPLAY"


def test_action_context_snapshot_drift_rejected(tmp_path):
    authority, _ = _authority()
    receipt = _issue(authority)
    for field, mutated in (
        ("action", {**ACTION, "strategy_id": "S3a"}),
        ("context", {**CONTEXT, "run_id": "R2"}),
        ("gate_snapshot", {"schema": "SNAP", "gates": {"g1": "UNKNOWN"}}),
    ):
        store = FileReplayStore(tmp_path / f"store_{field}")
        kwargs = dict(action=ACTION, context=CONTEXT, gate_snapshot=SNAPSHOT)
        kwargs[field] = mutated[field] if isinstance(mutated, dict) and field in mutated else mutated
        decision = authority.verify_and_consume(
            receipt=receipt,
            replay_store=store,
            **kwargs,
        )
        assert decision.allowed is False
        assert decision.reason_code.endswith("_MISMATCH")


def test_resigned_semantic_drift_still_rejected(tmp_path):
    authority, _ = _authority()
    store = FileReplayStore(tmp_path / "store")
    receipt = _issue(authority)
    payload = dict(receipt.payload)
    payload["validity_window_s"] = 100.0  # beyond the bounded maximum
    resigned = resign_receipt_for_negative_control(payload)
    decision = authority.verify_and_consume(
        receipt=resigned,
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        replay_store=store,
    )
    assert decision.allowed is False
    assert decision.reason_code == "SNAPSHOT_REJECTED_VALIDITY_WINDOW_INVALID"


def test_replay_store_writes_only_inside_store_root(tmp_path):
    authority, _ = _authority()
    outside = tmp_path / "outside"
    outside.mkdir()
    before = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    store = FileReplayStore(tmp_path / "store")
    receipt = _issue(authority)
    authority.verify_and_consume(
        receipt=receipt,
        action=ACTION,
        context=CONTEXT,
        gate_snapshot=SNAPSHOT,
        replay_store=store,
    )
    after = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    created = after - before
    assert created
    assert all(str(item).startswith("store") for item in created)
    assert not any(str(item).startswith("outside") for item in created)


def test_deterministic_replay_same_outcome(tmp_path):
    results = []
    for store_name in ("s1", "s2"):
        authority, _ = _authority()
        store = FileReplayStore(tmp_path / store_name)
        receipt = _issue(authority)
        decision = authority.verify_and_consume(
            receipt=receipt,
            action=ACTION,
            context=CONTEXT,
            gate_snapshot=SNAPSHOT,
            replay_store=store,
        )
        results.append((decision.allowed, decision.reason_code, receipt.as_dict()))
    assert results[0] == results[1]
