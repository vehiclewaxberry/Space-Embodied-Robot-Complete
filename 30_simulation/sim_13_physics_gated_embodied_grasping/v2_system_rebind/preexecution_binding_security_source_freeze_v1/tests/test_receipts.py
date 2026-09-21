from __future__ import annotations

import json
import inspect
import re

import pytest

from preexec_security.negative_controls import ACTION_ABORT, ACTION_S1, CONTEXT, NOW, SYNTHETIC_KEY
from preexec_security.receipts import (
    KINDS,
    ReceiptError,
    ReplayStore,
    SHIELD_CAPABILITY,
    admit_backend_request,
    evaluate_receipt_bound_join,
    issue_synthetic_receipt,
    verify_receipt,
)
from preexec_security.strict_json import (
    MAX_JSON_BYTES,
    MAX_JSON_NODES,
    MAX_JSON_STRING_CHARS,
    canonical_digest,
)


def _payload(kind: str) -> dict[str, object]:
    if kind == "SYSTEM_BINDING_V2":
        return {"status": "PASS", "system_urdf_sha256": "1" * 64}
    if kind == "RUNTIME_GATE_SNAPSHOT_V2":
        states = {
            name: "PASS"
            for name in (
                "ik_reachable", "external_collision_clear", "keep_out_clear", "sim10_gate",
                "safe00_state", "post_grasp_stability_gate", "gripper_configuration_accepted",
                "target_surface_normal_valid", "mechanical_system_binding",
                "harness_rated_envelope", "contact_physics_ready", "route_c_scope_disposition",
            )
        }
        return {"status": "PASS", "gate_count": 12, "gate_digest": canonical_digest(states), "gate_states": states}
    if kind == "DYNAMICS_GATE_V2":
        return {"status": "PASS", "backend_receipt_sha256": "2" * 64}
    if kind == "CONTACT_PREFLIGHT_V2":
        return {"status": "PASS", "contact_receipt_sha256": "3" * 64}
    if kind == "SHIELD_ATTESTATION_V2":
        return {"status": "PASS", "capability": SHIELD_CAPABILITY, "shielded": True}
    if kind == "FEASIBILITY_150KG_V2":
        return {
            "status": "FAIL", "target_mass_kg": 150.0, "target_rate_deg_s": 3.0,
            "post_capture_rate_deg_s": 3.0633, "verdict": "INFEASIBLE_RATE",
            "sim10_source_sha256": "4" * 64,
        }
    if kind == "POST_GRASP_V2":
        return {
            "status": "FAIL", "target_mass_kg": 150.0, "target_rate_deg_s": 3.0,
            "stability_receipt_sha256": "5" * 64,
        }
    raise AssertionError(kind)


def _receipt(kind: str, index: int, *, nonce: str | None = None) -> bytes:
    return issue_synthetic_receipt(
        kind=kind,
        action=ACTION_S1,
        context=CONTEXT,
        payload=_payload(kind),
        issued_at_unix_s=NOW - 1.0,
        expires_at_unix_s=NOW + 30.0,
        nonce=nonce or f"RECEIPT_{index:02d}_NONCE_0001",
        evidence_sha256=f"{index + 10:064X}",
        key=SYNTHETIC_KEY,
    )


def _bundle() -> dict[str, bytes]:
    return {kind: _receipt(kind, index) for index, kind in enumerate(KINDS)}


def test_receipt_rejects_duplicate_and_extra_fields_before_signature_use() -> None:
    receipt = _receipt("SYSTEM_BINDING_V2", 0)
    text = receipt.decode("utf-8").replace('{"body":', '{"body":{},"body":', 1)
    with pytest.raises(ReceiptError, match="DUPLICATE_KEY"):
        verify_receipt(text.encode(), expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    document = json.loads(receipt)
    document["body"]["caller_pass"] = True
    with pytest.raises(ReceiptError, match="KEY_SET_MISMATCH"):
        verify_receipt(json.dumps(document).encode(), expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    runtime_payload = _payload("RUNTIME_GATE_SNAPSHOT_V2")
    runtime_payload["gate_states"]["forged_gate"] = "PASS"
    with pytest.raises(ReceiptError, match="KEY_SET_MISMATCH"):
        issue_synthetic_receipt(kind="RUNTIME_GATE_SNAPSHOT_V2", action=ACTION_S1, context=CONTEXT, payload=runtime_payload, issued_at_unix_s=NOW - 1, expires_at_unix_s=NOW + 30, nonce="NESTED_EXTRA_NONCE_01", evidence_sha256="8" * 64, key=SYNTHETIC_KEY)


def test_receipt_is_action_context_time_and_replay_bound() -> None:
    receipt = _receipt("SYSTEM_BINDING_V2", 0)
    with pytest.raises(ReceiptError, match="ACTION_DIGEST_MISMATCH"):
        verify_receipt(receipt, expected_kind="SYSTEM_BINDING_V2", action=dict(ACTION_S1, strategy_id="S3a"), context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    with pytest.raises(ReceiptError, match="CONTEXT_DIGEST_MISMATCH"):
        verify_receipt(receipt, expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=dict(CONTEXT, authority_epoch=2), trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    with pytest.raises(ReceiptError, match="STALE_RECEIPT"):
        verify_receipt(receipt, expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW + 31.0, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    store = ReplayStore()
    verified = verify_receipt(receipt, expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY)
    assert store.seen_count == 0
    store.consume_many((verified.nonce,))
    with pytest.raises(ReceiptError, match="REPLAY_NONCE"):
        verify_receipt(receipt, expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY)


def test_public_verify_has_no_nonce_consumption_switch() -> None:
    assert "consume_nonce" not in inspect.signature(verify_receipt).parameters
    receipt = _receipt("SYSTEM_BINDING_V2", 0)
    store = ReplayStore()
    assert verify_receipt(receipt, expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY).status == "PASS"
    assert verify_receipt(receipt, expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY).status == "PASS"
    assert store.seen_count == 0


def test_exact_high_level_action_context_schema_is_enforced_at_every_entry() -> None:
    assert set(ACTION_S1) == {"grasp_candidate_id", "capture_timing_id", "strategy_id"}
    assert CONTEXT["target_class"] == "DEBRIS_150KG_3DPS"
    bad_action = dict(ACTION_S1, joint_torque_nm=[1.0] * 6)
    with pytest.raises(ReceiptError, match="KEY_SET_MISMATCH:/action"):
        issue_synthetic_receipt(kind="SYSTEM_BINDING_V2", action=bad_action, context=CONTEXT, payload=_payload("SYSTEM_BINDING_V2"), issued_at_unix_s=NOW - 1, expires_at_unix_s=NOW + 30, nonce="BAD_ACTION_ISSUE_NONCE", evidence_sha256="A" * 64, key=SYNTHETIC_KEY)
    receipt = _receipt("SYSTEM_BINDING_V2", 0)
    with pytest.raises(ReceiptError, match="KEY_SET_MISMATCH:/action"):
        verify_receipt(receipt, expected_kind="SYSTEM_BINDING_V2", action=bad_action, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    direct = admit_backend_request("S1", shield_receipt_bytes=None, action=bad_action, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert direct.executed_strategy == "ABORT" and direct.reason_codes[0].startswith("KEY_SET_MISMATCH:/action")
    joined = evaluate_receipt_bound_join("S1", receipt_bytes_by_kind={}, action=bad_action, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert joined.executed_strategy == "ABORT" and joined.reason_codes[0].startswith("KEY_SET_MISMATCH:/action")


def test_requested_strategy_and_abort_action_are_exact() -> None:
    mismatch = admit_backend_request("S3a", shield_receipt_bytes=None, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert mismatch.reason_codes == ("REQUESTED_STRATEGY_ACTION_MISMATCH",)
    joined = evaluate_receipt_bound_join("S3a", receipt_bytes_by_kind={}, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert joined.reason_codes == ("REQUESTED_STRATEGY_ACTION_MISMATCH",)
    canonical = admit_backend_request("ABORT", shield_receipt_bytes=None, action=ACTION_ABORT, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert canonical.allowed is True and canonical.executed_strategy == "ABORT"
    noncanonical = dict(ACTION_ABORT, grasp_candidate_id="GC_NOT_ABORT")
    denied = admit_backend_request("ABORT", shield_receipt_bytes=None, action=noncanonical, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert denied.allowed is False and denied.reason_codes == ("NONCANONICAL_ABORT_ACTION",)


def test_verified_receipt_payload_is_recursively_immutable() -> None:
    receipt = _receipt("RUNTIME_GATE_SNAPSHOT_V2", 1)
    verified = verify_receipt(receipt, expected_kind="RUNTIME_GATE_SNAPSHOT_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    with pytest.raises(TypeError):
        verified.payload["gate_states"]["mechanical_system_binding"] = "FAIL"


def test_bundle_validation_is_atomic_on_late_failure() -> None:
    bundle = _bundle()
    last = json.loads(bundle["POST_GRASP_V2"])
    last["signature_hmac_sha256"] = "0" * 64
    bundle["POST_GRASP_V2"] = json.dumps(last, separators=(",", ":")).encode()
    store = ReplayStore()
    decision = evaluate_receipt_bound_join("S1", receipt_bytes_by_kind=bundle, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY)
    assert decision.executed_strategy == "ABORT"
    assert decision.reason_codes == ("ATTESTATION_SIGNATURE_INVALID",)
    assert store.seen_count == 0
    verified = verify_receipt(bundle["SYSTEM_BINDING_V2"], expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY)
    assert verified.status == "PASS"


def test_nonce_is_globally_unique_across_receipt_kinds_and_bundle_commit_is_atomic() -> None:
    bundle = _bundle()
    shared = "GLOBAL_SHARED_NONCE_0001"
    bundle["SYSTEM_BINDING_V2"] = _receipt("SYSTEM_BINDING_V2", 0, nonce=shared)
    bundle["DYNAMICS_GATE_V2"] = _receipt("DYNAMICS_GATE_V2", 2, nonce=shared)
    store = ReplayStore()
    decision = evaluate_receipt_bound_join("S1", receipt_bytes_by_kind=bundle, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY)
    assert decision.reason_codes == ("DUPLICATE_NONCE_IN_BUNDLE",)
    assert store.seen_count == 0
    verify_receipt(bundle["SYSTEM_BINDING_V2"], expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY)


def test_direct_backend_guard_and_150kg_truth_are_fail_closed() -> None:
    direct = admit_backend_request("S1", shield_receipt_bytes=None, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert direct.executed_strategy == "ABORT"
    assert direct.reason_codes == ("SHIELD_ATTESTATION_REQUIRED",)
    shield = _receipt("SHIELD_ATTESTATION_V2", 4)
    attested = admit_backend_request("S1", shield_receipt_bytes=shield, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert attested.attestation_verified is True
    assert attested.allowed is False and attested.executed_strategy == "ABORT"
    assert attested.reason_codes == ("SOURCE_FREEZE_SCOPE_LOCK",)
    decision = evaluate_receipt_bound_join("S1", receipt_bytes_by_kind=_bundle(), action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert decision.executed_strategy == "ABORT"
    assert decision.reason_codes == ("FEASIBILITY_150KG_V2_FAIL",)
    forged = _payload("FEASIBILITY_150KG_V2")
    forged["status"] = "PASS"
    with pytest.raises(ReceiptError, match="150KG_3DPS_PASS_FORGERY"):
        issue_synthetic_receipt(kind="FEASIBILITY_150KG_V2", action=ACTION_S1, context=CONTEXT, payload=forged, issued_at_unix_s=NOW - 1, expires_at_unix_s=NOW + 30, nonce="FORGED_FEAS_NONCE_01", evidence_sha256="9" * 64, key=SYNTHETIC_KEY)


@pytest.mark.parametrize("status", ["FAIL", "HOLD", "UNKNOWN"])
def test_semantic_nonpass_and_source_scope_lock_do_not_consume_nonce(status: str) -> None:
    bundle = _bundle()
    bundle["SYSTEM_BINDING_V2"] = issue_synthetic_receipt(
        kind="SYSTEM_BINDING_V2", action=ACTION_S1, context=CONTEXT,
        payload={"status": status, "system_urdf_sha256": "1" * 64},
        issued_at_unix_s=NOW - 1, expires_at_unix_s=NOW + 30,
        nonce=f"SEMANTIC_{status}_NONCE_01", evidence_sha256="A" * 64, key=SYNTHETIC_KEY,
    )
    store = ReplayStore()
    first = evaluate_receipt_bound_join("S1", receipt_bytes_by_kind=bundle, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY)
    second = evaluate_receipt_bound_join("S1", receipt_bytes_by_kind=bundle, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=store, key=SYNTHETIC_KEY)
    assert first.reason_codes == second.reason_codes == (f"SYSTEM_BINDING_V2_{status}",)
    assert store.seen_count == 0
    shield = _receipt("SHIELD_ATTESTATION_V2", 4)
    locked = ReplayStore()
    assert admit_backend_request("S1", shield_receipt_bytes=shield, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=locked, key=SYNTHETIC_KEY).reason_codes == ("SOURCE_FREEZE_SCOPE_LOCK",)
    assert admit_backend_request("S1", shield_receipt_bytes=shield, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=locked, key=SYNTHETIC_KEY).reason_codes == ("SOURCE_FREEZE_SCOPE_LOCK",)
    assert locked.seen_count == 0


def test_invalid_provided_known_receipt_precedes_missing_kind() -> None:
    bundle = _bundle()
    bundle.pop("FEASIBILITY_150KG_V2")
    corrupted = json.loads(bundle["POST_GRASP_V2"])
    corrupted["signature_hmac_sha256"] = "0" * 64
    bundle["POST_GRASP_V2"] = json.dumps(corrupted, separators=(",", ":")).encode()
    decision = evaluate_receipt_bound_join("S1", receipt_bytes_by_kind=bundle, action=ACTION_S1, context=CONTEXT, trusted_now_unix_s=NOW, replay_store=ReplayStore(), key=SYNTHETIC_KEY)
    assert decision.reason_codes == ("ATTESTATION_SIGNATURE_INVALID",)


@pytest.mark.parametrize("bad_time", [float("nan"), float("inf"), float("-inf"), 10**399])
def test_issue_rejects_nonfinite_and_binary64_overflowing_times(bad_time) -> None:
    with pytest.raises(ReceiptError, match="INVALID_NUMBER:/body/issued_at_unix_s"):
        issue_synthetic_receipt(
            kind="SYSTEM_BINDING_V2",
            action=ACTION_S1,
            context=CONTEXT,
            payload=_payload("SYSTEM_BINDING_V2"),
            issued_at_unix_s=bad_time,
            expires_at_unix_s=NOW + 30.0,
            nonce="MALFORMED_TIME_NONCE_01",
            evidence_sha256="A" * 64,
            key=SYNTHETIC_KEY,
        )


def test_issue_rejects_non_object_payload_as_receipt_error() -> None:
    with pytest.raises(ReceiptError, match="PAYLOAD_NOT_OBJECT"):
        issue_synthetic_receipt(
            kind="SYSTEM_BINDING_V2",
            action=ACTION_S1,
            context=CONTEXT,
            payload=None,
            issued_at_unix_s=NOW - 1.0,
            expires_at_unix_s=NOW + 30.0,
            nonce="MALFORMED_PAYLOAD_NONCE_01",
            evidence_sha256="A" * 64,
            key=SYNTHETIC_KEY,
        )


@pytest.mark.parametrize("bad_receipt", [None, 7, {"body": {}}])
def test_public_verify_rejects_non_bytes_receipts_as_receipt_error(bad_receipt) -> None:
    with pytest.raises(ReceiptError, match="RECEIPT_BYTES_REQUIRED"):
        verify_receipt(
            bad_receipt,
            expected_kind="SYSTEM_BINDING_V2",
            action=ACTION_S1,
            context=CONTEXT,
            trusted_now_unix_s=NOW,
            replay_store=ReplayStore(),
            key=SYNTHETIC_KEY,
        )


@pytest.mark.parametrize("bad_receipt", [None, 7, {"body": {}}])
def test_admit_and_join_map_non_bytes_receipts_to_abort_without_nonce_use(bad_receipt) -> None:
    direct_store = ReplayStore()
    direct = admit_backend_request(
        "S1",
        shield_receipt_bytes=bad_receipt,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=direct_store,
        key=SYNTHETIC_KEY,
    )
    expected_direct = "SHIELD_ATTESTATION_REQUIRED" if bad_receipt is None else "RECEIPT_BYTES_REQUIRED"
    assert direct.allowed is False and direct.executed_strategy == "ABORT"
    assert direct.reason_codes == (expected_direct,)
    assert direct_store.seen_count == 0

    join_store = ReplayStore()
    joined = evaluate_receipt_bound_join(
        "S1",
        receipt_bytes_by_kind={"SHIELD_ATTESTATION_V2": bad_receipt},
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=join_store,
        key=SYNTHETIC_KEY,
    )
    assert joined.allowed is False and joined.executed_strategy == "ABORT"
    assert joined.reason_codes == ("RECEIPT_BYTES_REQUIRED",)
    assert join_store.seen_count == 0


@pytest.mark.parametrize(
    ("literal", "reason"),
    [
        ("NaN", "NON_FINITE_NUMBER"),
        ("Infinity", "NON_FINITE_NUMBER"),
        ("1e999", "NON_FINITE_NUMBER"),
        ("1" + "0" * 399, "INTEGER_DIGIT_LIMIT_EXCEEDED"),
    ],
)
def test_raw_receipt_malformed_numeric_literals_fail_closed(literal: str, reason: str) -> None:
    receipt = _receipt("SYSTEM_BINDING_V2", 0)
    forged = re.sub(
        rb'"issued_at_unix_s":[^,]+',
        b'"issued_at_unix_s":' + literal.encode("ascii"),
        receipt,
        count=1,
    )
    with pytest.raises(ReceiptError, match=re.escape(reason)):
        verify_receipt(
            forged,
            expected_kind="SYSTEM_BINDING_V2",
            action=ACTION_S1,
            context=CONTEXT,
            trusted_now_unix_s=NOW,
            replay_store=ReplayStore(),
            key=SYNTHETIC_KEY,
        )


@pytest.mark.parametrize("bad_now", [float("nan"), float("inf"), 10**399])
def test_admit_and_join_map_malformed_trusted_clock_to_abort_without_nonce_use(bad_now) -> None:
    shield = _receipt("SHIELD_ATTESTATION_V2", 4)
    direct_store = ReplayStore()
    direct = admit_backend_request(
        "S1",
        shield_receipt_bytes=shield,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=bad_now,
        replay_store=direct_store,
        key=SYNTHETIC_KEY,
    )
    assert direct.allowed is False and direct.executed_strategy == "ABORT"
    assert direct.reason_codes[0].startswith("INVALID_NUMBER:/trusted_now_unix_s")
    assert direct_store.seen_count == 0

    join_store = ReplayStore()
    joined = evaluate_receipt_bound_join(
        "S1",
        receipt_bytes_by_kind=_bundle(),
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=bad_now,
        replay_store=join_store,
        key=SYNTHETIC_KEY,
    )
    assert joined.allowed is False and joined.executed_strategy == "ABORT"
    assert joined.reason_codes[0].startswith("INVALID_NUMBER:/trusted_now_unix_s")
    assert join_store.seen_count == 0


def _malformed_receipt_boundaries() -> tuple[bytes, ...]:
    return (
        b"[" * 1200 + b"0" + b"]" * 1200,
        b'{"x":' * 1200 + b"0" + b"}" * 1200,
        b"9" * 5000,
        b" " * (MAX_JSON_BYTES + 1),
        b'"\xff"',
        b'"\\ud800"',
        ('"' + "x" * (MAX_JSON_STRING_CHARS + 1) + '"').encode("ascii"),
    )


@pytest.mark.parametrize(
    "bad_receipt",
    _malformed_receipt_boundaries(),
    ids=("deep-array", "deep-object", "long-int", "oversize-bytes", "invalid-utf8", "escaped-surrogate", "long-string"),
)
def test_public_verify_normalizes_bounded_parser_failures(bad_receipt: bytes) -> None:
    with pytest.raises(ReceiptError):
        verify_receipt(
            bad_receipt,
            expected_kind="SYSTEM_BINDING_V2",
            action=ACTION_S1,
            context=CONTEXT,
            trusted_now_unix_s=NOW,
            replay_store=ReplayStore(),
            key=SYNTHETIC_KEY,
        )


@pytest.mark.parametrize(
    "bad_receipt",
    _malformed_receipt_boundaries(),
    ids=("deep-array", "deep-object", "long-int", "oversize-bytes", "invalid-utf8", "escaped-surrogate", "long-string"),
)
def test_direct_and_join_bound_parser_failures_abort_without_nonce_use(bad_receipt: bytes) -> None:
    direct_store = ReplayStore()
    direct = admit_backend_request(
        "S1",
        shield_receipt_bytes=bad_receipt,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=direct_store,
        key=SYNTHETIC_KEY,
    )
    assert direct.allowed is False and direct.executed_strategy == "ABORT"
    assert direct_store.seen_count == 0

    join_store = ReplayStore()
    joined = evaluate_receipt_bound_join(
        "S1",
        receipt_bytes_by_kind={"SHIELD_ATTESTATION_V2": bad_receipt},
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=join_store,
        key=SYNTHETIC_KEY,
    )
    assert joined.allowed is False and joined.executed_strategy == "ABORT"
    assert join_store.seen_count == 0


def test_issue_bounds_in_memory_payload_depth_nodes_strings_and_integer_time() -> None:
    deep: object = 0
    for _ in range(1200):
        deep = [deep]
    malicious_payloads = (
        {"nested": deep},
        {"nodes": [0] * (MAX_JSON_NODES + 1)},
        {"text": "x" * (MAX_JSON_STRING_CHARS + 1)},
    )
    for index, payload in enumerate(malicious_payloads):
        with pytest.raises(ReceiptError):
            issue_synthetic_receipt(
                kind="SYSTEM_BINDING_V2",
                action=ACTION_S1,
                context=CONTEXT,
                payload=payload,
                issued_at_unix_s=NOW - 1.0,
                expires_at_unix_s=NOW + 30.0,
                nonce=f"BOUNDED_ISSUE_NONCE_{index:02d}",
                evidence_sha256="A" * 64,
                key=SYNTHETIC_KEY,
            )
    with pytest.raises(ReceiptError, match="INVALID_NUMBER:/body/issued_at_unix_s"):
        issue_synthetic_receipt(
            kind="SYSTEM_BINDING_V2",
            action=ACTION_S1,
            context=CONTEXT,
            payload=_payload("SYSTEM_BINDING_V2"),
            issued_at_unix_s=10**4999,
            expires_at_unix_s=NOW + 30.0,
            nonce="BOUNDED_ISSUE_TIME_NONCE",
            evidence_sha256="A" * 64,
            key=SYNTHETIC_KEY,
        )


def test_in_memory_action_context_limits_are_receipt_errors_or_abort_at_every_entry() -> None:
    deep: object = 0
    for _ in range(1200):
        deep = [deep]
    bad_action = dict(ACTION_S1, nested=deep)
    bad_context = dict(CONTEXT, authority_epoch=10**4999)
    with pytest.raises(ReceiptError, match="JSON_DEPTH_LIMIT_EXCEEDED"):
        issue_synthetic_receipt(
            kind="SYSTEM_BINDING_V2", action=bad_action, context=CONTEXT,
            payload=_payload("SYSTEM_BINDING_V2"), issued_at_unix_s=NOW - 1.0,
            expires_at_unix_s=NOW + 30.0, nonce="DEEP_ACTION_ISSUE_NONCE",
            evidence_sha256="A" * 64, key=SYNTHETIC_KEY,
        )
    receipt = _receipt("SYSTEM_BINDING_V2", 0)
    with pytest.raises(ReceiptError, match="INTEGER_DIGIT_LIMIT_EXCEEDED"):
        verify_receipt(
            receipt, expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1,
            context=bad_context, trusted_now_unix_s=NOW,
            replay_store=ReplayStore(), key=SYNTHETIC_KEY,
        )
    direct_store = ReplayStore()
    direct = admit_backend_request(
        "S1", shield_receipt_bytes=None, action=bad_action, context=CONTEXT,
        trusted_now_unix_s=NOW, replay_store=direct_store, key=SYNTHETIC_KEY,
    )
    join_store = ReplayStore()
    joined = evaluate_receipt_bound_join(
        "S1", receipt_bytes_by_kind={}, action=ACTION_S1, context=bad_context,
        trusted_now_unix_s=NOW, replay_store=join_store, key=SYNTHETIC_KEY,
    )
    assert direct.allowed is False and direct.executed_strategy == "ABORT"
    assert joined.allowed is False and joined.executed_strategy == "ABORT"
    assert direct_store.seen_count == join_store.seen_count == 0


def test_lone_surrogate_in_action_context_is_receipt_error_or_abort_without_nonce_use() -> None:
    bad_action = dict(ACTION_S1, grasp_candidate_id="\ud800")
    bad_context = dict(CONTEXT, target_class="\ud800")
    with pytest.raises(ReceiptError, match="INVALID_UTF8_STRING"):
        issue_synthetic_receipt(
            kind="SYSTEM_BINDING_V2", action=bad_action, context=CONTEXT,
            payload=_payload("SYSTEM_BINDING_V2"), issued_at_unix_s=NOW - 1.0,
            expires_at_unix_s=NOW + 30.0, nonce="SURROGATE_ISSUE_NONCE",
            evidence_sha256="A" * 64, key=SYNTHETIC_KEY,
        )
    receipt = _receipt("SYSTEM_BINDING_V2", 0)
    with pytest.raises(ReceiptError, match="INVALID_UTF8_STRING"):
        verify_receipt(
            receipt, expected_kind="SYSTEM_BINDING_V2", action=ACTION_S1,
            context=bad_context, trusted_now_unix_s=NOW,
            replay_store=ReplayStore(), key=SYNTHETIC_KEY,
        )
    direct_store = ReplayStore()
    direct = admit_backend_request(
        "S1", shield_receipt_bytes=None, action=bad_action, context=CONTEXT,
        trusted_now_unix_s=NOW, replay_store=direct_store, key=SYNTHETIC_KEY,
    )
    join_store = ReplayStore()
    joined = evaluate_receipt_bound_join(
        "S1", receipt_bytes_by_kind={}, action=ACTION_S1, context=bad_context,
        trusted_now_unix_s=NOW, replay_store=join_store, key=SYNTHETIC_KEY,
    )
    assert direct.allowed is False and direct.executed_strategy == "ABORT"
    assert joined.allowed is False and joined.executed_strategy == "ABORT"
    assert direct_store.seen_count == join_store.seen_count == 0
