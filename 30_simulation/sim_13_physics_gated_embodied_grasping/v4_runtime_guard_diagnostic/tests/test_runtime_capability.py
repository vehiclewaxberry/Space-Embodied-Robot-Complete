from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import itertools

import pytest

import sim13_v4.runtime_guard as guard_module
from sim13_v4.diagnostic_backend import (
    BACKEND_ID,
    build_execution_context,
    initial_diagnostic_state,
    nominal_generalized_effort,
    synthetic_non_debris_policy_fixture,
)
from sim13_v4.runtime_guard import (
    DIAGNOSTIC_CLOCK_CLASS,
    DIAGNOSTIC_KEY_CLASS,
    DiagnosticAction,
    DiagnosticCapability,
    DiagnosticClock,
    DiagnosticShield,
    MAX_VALIDITY_WINDOW_S,
    NONCE_PERSISTENCE_BOUNDARY,
    NonceLedger,
    synthetic_gate_snapshot,
)


_NONCE_SEQUENCE = itertools.count()


def _fixture(nonce: str | None = None):
    nonce = nonce or f"PYTEST-NC15-{next(_NONCE_SEQUENCE)}"
    action = DiagnosticAction("GC_SYNTHETIC", "T_SYNTHETIC", "S1")
    state = initial_diagnostic_state()
    effort = nominal_generalized_effort()
    policy = synthetic_non_debris_policy_fixture()
    context = build_execution_context(
        run_id=f"SIM13-V4-NC15-{next(_NONCE_SEQUENCE)}",
        state=state,
        generalized_effort=effort,
        step_s=0.001,
        steps=3,
        target_policy_fixture=policy,
    )
    snapshot = synthetic_gate_snapshot()
    clock = DiagnosticClock(1000.0)
    shield = DiagnosticShield(clock=clock)
    capability = shield.issue_capability(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        nonce=nonce,
        validity_window_s=2.0,
    )
    return action, context, snapshot, clock, shield, capability, nonce


def test_diagnostic_key_and_clock_are_explicitly_nonproduction() -> None:
    assert "NON_PRODUCTION" in DIAGNOSTIC_KEY_CLASS
    assert "NOT_TRUSTED_PRODUCTION" in DIAGNOSTIC_CLOCK_CLASS
    assert "SINGLE_CANONICAL_MODULE_INSTANCE_LIFETIME" in NONCE_PERSISTENCE_BOUNDARY
    assert "NO_IMPORTLIB_RELOAD_DUPLICATE_MODULE_INSTANCE" in NONCE_PERSISTENCE_BOUNDARY


def test_capability_is_bound_to_action_context_snapshot_backend_and_finite_window() -> None:
    action, context, snapshot, _, _, capability, _ = _fixture()
    payload = capability.payload
    assert payload["backend_id"] == BACKEND_ID == context["backend_id"]
    assert payload["validity_window_s"] == 2.0
    assert payload["expires_at_s"] - payload["not_before_s"] == 2.0
    assert payload["current_system_binding_passed"] is False
    assert payload["runtime_production_gate_passed"] is False
    assert action.is_abort is False
    assert snapshot["current_system_binding_passed"] is False


def test_valid_capability_is_consumed_exactly_once_and_replay_aborts() -> None:
    action, context, snapshot, _, shield, capability, nonce = _fixture()
    first = shield.authorize_and_consume(
        action=action, context=context, gate_snapshot=snapshot, capability=capability
    )
    second = shield.authorize_and_consume(
        action=action, context=context, gate_snapshot=snapshot, capability=capability
    )
    assert first.allowed is True and first.consumed_nonce == nonce
    assert first.reason_code == "CAPABILITY_ACCEPTED_ONCE"
    assert second.allowed is False and second.executed_action.is_abort
    assert second.reason_code == "CAPABILITY_NONCE_REPLAY"
    assert NonceLedger().is_consumed(nonce) is True


def test_replay_is_rejected_across_shield_instances_and_new_ledger_views() -> None:
    action, context, snapshot, _, first_shield, capability, nonce = _fixture(
        f"PYTEST-CROSS-SHIELD-{next(_NONCE_SEQUENCE)}"
    )
    accepted = first_shield.authorize_and_consume(
        action=action, context=context, gate_snapshot=snapshot, capability=capability
    )
    second_shield = DiagnosticShield(clock=DiagnosticClock(1000.0))
    replay = second_shield.authorize_and_consume(
        action=action, context=context, gate_snapshot=snapshot, capability=capability
    )
    fresh_view = NonceLedger()
    assert accepted.allowed is True
    assert replay.allowed is False and replay.reason_code == "CAPABILITY_NONCE_REPLAY"
    assert fresh_view.is_consumed(nonce) is True
    assert fresh_view.consume_once(nonce) is False


def test_concurrent_cross_shield_consumption_admits_exactly_one() -> None:
    action, context, snapshot, _, issuer, capability, _ = _fixture(
        f"PYTEST-THREAD-RACE-{next(_NONCE_SEQUENCE)}"
    )
    shields = [issuer] + [
        DiagnosticShield(clock=DiagnosticClock(1000.0)) for _ in range(15)
    ]

    def attempt(shield: DiagnosticShield):
        return shield.authorize_and_consume(
            action=action,
            context=context,
            gate_snapshot=snapshot,
            capability=capability,
        )

    with ThreadPoolExecutor(max_workers=16) as executor:
        decisions = list(executor.map(attempt, shields))
    assert sum(int(item.allowed) for item in decisions) == 1
    assert sum(item.reason_code == "CAPABILITY_NONCE_REPLAY" for item in decisions) == 15


def test_external_isolated_ledger_injection_is_not_an_api() -> None:
    with pytest.raises(TypeError):
        DiagnosticShield(  # type: ignore[call-arg]
            clock=DiagnosticClock(1000.0), nonce_ledger=NonceLedger()
        )


def test_stale_capability_aborts_without_consuming_nonce() -> None:
    action, context, snapshot, clock, shield, capability, nonce = _fixture()
    clock.advance(2.000001)
    decision = shield.authorize_and_consume(
        action=action, context=context, gate_snapshot=snapshot, capability=capability
    )
    assert decision.executed_action.is_abort
    assert decision.reason_code == "CAPABILITY_STALE"
    assert NonceLedger().is_consumed(nonce) is False


def test_action_mismatch_aborts_without_consuming_nonce() -> None:
    action, context, snapshot, _, shield, capability, nonce = _fixture()
    changed = DiagnosticAction("GC_OTHER", action.capture_timing_id, action.strategy_id)
    decision = shield.authorize_and_consume(
        action=changed, context=context, gate_snapshot=snapshot, capability=capability
    )
    assert decision.reason_code == "CAPABILITY_ACTION_MISMATCH"
    assert decision.executed_action.is_abort
    assert NonceLedger().is_consumed(nonce) is False


def test_context_mismatch_aborts_without_consuming_nonce() -> None:
    action, context, snapshot, _, shield, capability, nonce = _fixture()
    changed = dict(context)
    changed["run_id"] = "SIM13-V4-STOLEN-CONTEXT"
    decision = shield.authorize_and_consume(
        action=action, context=changed, gate_snapshot=snapshot, capability=capability
    )
    assert decision.reason_code == "CAPABILITY_CONTEXT_MISMATCH"
    assert decision.executed_action.is_abort
    assert NonceLedger().is_consumed(nonce) is False


def test_gate_snapshot_mismatch_aborts_without_consuming_nonce() -> None:
    action, context, _, _, shield, capability, nonce = _fixture()
    changed = synthetic_gate_snapshot(overrides={"contact_physics_ready": "UNKNOWN"})
    decision = shield.authorize_and_consume(
        action=action, context=context, gate_snapshot=changed, capability=capability
    )
    assert decision.reason_code == "CAPABILITY_GATE_SNAPSHOT_MISMATCH"
    assert decision.executed_action.is_abort
    assert NonceLedger().is_consumed(nonce) is False


def test_signature_tamper_aborts() -> None:
    action, context, snapshot, _, shield, capability, nonce = _fixture()
    tampered = DiagnosticCapability(capability.payload, "0" * 64)
    decision = shield.authorize_and_consume(
        action=action, context=context, gate_snapshot=snapshot, capability=tampered
    )
    assert decision.reason_code == "CAPABILITY_SIGNATURE_INVALID"
    assert decision.executed_action.is_abort
    assert NonceLedger().is_consumed(nonce) is False


def test_missing_capability_aborts() -> None:
    action, context, snapshot, _, shield, _, _ = _fixture()
    decision = shield.authorize_and_consume(
        action=action, context=context, gate_snapshot=snapshot, capability=None
    )
    assert decision.reason_code == "CAPABILITY_MISSING"
    assert decision.executed_action.is_abort


def test_unbounded_or_nonpositive_validity_is_rejected_at_issue() -> None:
    action, context, snapshot, _, shield, _, _ = _fixture()
    for value in (0.0, -1.0, MAX_VALIDITY_WINDOW_S + 1.0):
        with pytest.raises(ValueError, match="validity window"):
            shield.issue_capability(
                action=action,
                context=context,
                gate_snapshot=snapshot,
                nonce=f"WINDOW-{value}-{next(_NONCE_SEQUENCE)}",
                validity_window_s=value,
            )


def test_unknown_gate_snapshot_cannot_mint_capability() -> None:
    action, context, _, _, shield, _, _ = _fixture()
    snapshot = synthetic_gate_snapshot(overrides={"harness_rated_envelope": "UNKNOWN"})
    with pytest.raises(ValueError, match="not admissible"):
        shield.issue_capability(
            action=action,
            context=context,
            gate_snapshot=snapshot,
            nonce=f"UNKNOWN-GATE-{next(_NONCE_SEQUENCE)}",
            validity_window_s=1.0,
        )


def test_importable_naked_attestation_factory_token_no_longer_exists() -> None:
    assert not hasattr(guard_module, "_ATTESTATION_FACTORY_TOKEN")
    assert not hasattr(guard_module, "ShieldAttestation")
