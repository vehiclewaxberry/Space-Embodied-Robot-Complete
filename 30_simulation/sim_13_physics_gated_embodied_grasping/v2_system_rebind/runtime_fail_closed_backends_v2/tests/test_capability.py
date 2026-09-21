"""NC16 backend tests: schema, nominal, unshielded, source drift, replay."""

from __future__ import annotations

import json
from pathlib import Path

from sim13_v2_backends.capability import (
    ShieldAttestationAuthority,
    ShieldedBackendAdmission,
    resign_capability_for_negative_control,
    verify_capability,
)
from sim13_v2_backends.snapshot_receipt import FileReplayStore


BACKEND_ID = "SIM13_V2_UNIFIED_R2_FREE_FLOATING_DYNAMICS_BACKEND_V1"
BACKEND_SOURCE_SHA = "A" * 64
ACTION = {"grasp_candidate_id": "GC", "capture_timing_id": "T", "strategy_id": "S1"}
CONTEXT = {"schema": "CTX", "run_id": "R1", "backend_id": BACKEND_ID}
CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "SIM13_V2_BACKEND_CAPABILITY_TOKEN_SCHEMA_V1.json"
)


def _admission() -> ShieldedBackendAdmission:
    return ShieldedBackendAdmission(
        backend_id=BACKEND_ID, backend_source_sha256=BACKEND_SOURCE_SHA
    )


def _token(nonce: str = "C1", source_sha: str = BACKEND_SOURCE_SHA):
    return ShieldAttestationAuthority().issue_capability(
        backend_id=BACKEND_ID,
        backend_source_sha256=source_sha,
        action=ACTION,
        context=CONTEXT,
        nonce=nonce,
        issued_at_s=100.0,
        validity_window_s=2.0,
    )


def test_schema_contract_declares_source_binding():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "SIM13_V2_BACKEND_CAPABILITY_TOKEN_SCHEMA_V1"
    assert "backend_source_sha256" in contract["required_payload_fields"]
    assert "BACKEND_REJECTS_UNSHIELDED_NON_ABORT" in contract["rejection_reasons"]
    assert contract["next_stage_authorized"] is False
    assert contract["release_credit"] is False


def test_nominal_shielded_call_admitted_once(tmp_path):
    decision = _admission().admit(
        token=_token(),
        action=ACTION,
        context=CONTEXT,
        now_s=100.5,
        replay_store=FileReplayStore(tmp_path / "store"),
    )
    assert decision.allowed is True
    assert decision.reason_code == "CAPABILITY_TOKEN_ACCEPTED_ONCE"


def test_unshielded_call_rejected_exact_reason(tmp_path):
    decision = _admission().admit(
        token=None,
        action=ACTION,
        context=CONTEXT,
        now_s=100.5,
        replay_store=FileReplayStore(tmp_path / "store"),
    )
    assert decision.allowed is False
    assert decision.reason_code == "BACKEND_REJECTS_UNSHIELDED_NON_ABORT"


def test_malformed_token_rejected(tmp_path):
    decision = _admission().admit(
        token="not-a-token",  # type: ignore[arg-type]
        action=ACTION,
        context=CONTEXT,
        now_s=100.5,
        replay_store=FileReplayStore(tmp_path / "store"),
    )
    assert decision.allowed is False
    assert decision.reason_code == "CAPABILITY_TOKEN_MALFORMED"


def test_backend_source_drift_rejected(tmp_path):
    foreign = _token(source_sha="B" * 64)
    decision = _admission().admit(
        token=foreign,
        action=ACTION,
        context=CONTEXT,
        now_s=100.5,
        replay_store=FileReplayStore(tmp_path / "store"),
    )
    assert decision.allowed is False
    assert decision.reason_code == "CAPABILITY_TOKEN_BACKEND_SOURCE_MISMATCH"


def test_stale_and_replayed_token_rejected(tmp_path):
    token = _token()
    stale = _admission().admit(
        token=token,
        action=ACTION,
        context=CONTEXT,
        now_s=500.0,
        replay_store=FileReplayStore(tmp_path / "stale"),
    )
    assert stale.reason_code == "CAPABILITY_TOKEN_STALE"
    store = FileReplayStore(tmp_path / "replay")
    first = _admission().admit(
        token=token, action=ACTION, context=CONTEXT, now_s=100.5, replay_store=store
    )
    second = _admission().admit(
        token=token, action=ACTION, context=CONTEXT, now_s=100.6, replay_store=store
    )
    assert first.allowed is True
    assert second.allowed is False
    assert second.reason_code == "CAPABILITY_TOKEN_NONCE_REPLAY"


def test_action_context_drift_rejected(tmp_path):
    token = _token()
    decision = _admission().admit(
        token=token,
        action={**ACTION, "strategy_id": "S3a"},
        context=CONTEXT,
        now_s=100.5,
        replay_store=FileReplayStore(tmp_path / "a"),
    )
    assert decision.reason_code == "CAPABILITY_TOKEN_ACTION_MISMATCH"
    decision = _admission().admit(
        token=_token("C2"),
        action=ACTION,
        context={**CONTEXT, "run_id": "R2"},
        now_s=100.5,
        replay_store=FileReplayStore(tmp_path / "c"),
    )
    assert decision.reason_code == "CAPABILITY_TOKEN_CONTEXT_MISMATCH"


def test_resigned_window_escape_rejected(tmp_path):
    payload = dict(_token().payload)
    payload["validity_window_s"] = 999.0
    resigned = resign_capability_for_negative_control(payload)
    decision = _admission().admit(
        token=resigned,
        action=ACTION,
        context=CONTEXT,
        now_s=100.5,
        replay_store=FileReplayStore(tmp_path / "store"),
    )
    assert decision.allowed is False
    assert decision.reason_code == "CAPABILITY_TOKEN_VALIDITY_WINDOW_INVALID"


def test_deterministic_replay_same_outcome(tmp_path):
    results = []
    for store_name in ("s1", "s2"):
        decision = _admission().admit(
            token=_token(),
            action=ACTION,
            context=CONTEXT,
            now_s=100.5,
            replay_store=FileReplayStore(tmp_path / store_name),
        )
        results.append((decision.allowed, decision.reason_code))
    assert results[0] == results[1]
