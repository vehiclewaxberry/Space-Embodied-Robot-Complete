from __future__ import annotations

import itertools

import numpy as np
import pytest

import sim13_v4.diagnostic_backend as backend_module
from sim13_v4.diagnostic_backend import (
    BACKEND_SCOPE,
    GENERALIZED_COORDINATE_UNITS,
    GENERALIZED_EFFORT_UNITS,
    GENERALIZED_RATE_UNITS,
    DiagnosticExecutionCoordinator,
    OpaqueInvocation,
    SyntheticCapabilityBackend,
    build_execution_context,
    effort_record,
    initial_diagnostic_state,
    nominal_generalized_effort,
    phase_only_negative_control,
    synthetic_non_debris_policy_fixture,
)
from sim13_v4.runtime_guard import (
    DiagnosticAction,
    DiagnosticClock,
    DiagnosticShield,
    synthetic_gate_snapshot,
)


_SEQUENCE = itertools.count()


def _execution_fixture():
    state = initial_diagnostic_state()
    effort = nominal_generalized_effort()
    policy = synthetic_non_debris_policy_fixture()
    action = DiagnosticAction("GC_SYNTHETIC", "T_SYNTHETIC", "S1")
    context = build_execution_context(
        run_id=f"SIM13-V4-NC18-{next(_SEQUENCE)}",
        state=state,
        generalized_effort=effort,
        step_s=0.001,
        steps=3,
        target_policy_fixture=policy,
    )
    snapshot = synthetic_gate_snapshot()
    shield = DiagnosticShield(clock=DiagnosticClock(2000.0))
    capability = shield.issue_capability(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        nonce=f"NC18-ONE-SHOT-{next(_SEQUENCE)}",
        validity_window_s=2.0,
    )
    coordinator = DiagnosticExecutionCoordinator()
    return coordinator, action, state, effort, policy, context, snapshot, shield, capability


def _executed_step():
    fixture = _execution_fixture()
    coordinator, action, state, effort, policy, context, snapshot, shield, capability = fixture
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
        mission_veto_receipt=None,
    )
    return (*fixture, result)


def test_backend_scope_is_synthetic_prebind_only() -> None:
    assert "SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY" in BACKEND_SCOPE
    assert "NOT_CURRENT_SYSTEM" in BACKEND_SCOPE
    assert "NOT_CONTACT" in BACKEND_SCOPE


def test_revolute_and_prismatic_units_are_not_collapsed() -> None:
    record = effort_record(nominal_generalized_effort())
    assert GENERALIZED_EFFORT_UNITS == ("N*m",) * 6 + ("N",) * 2
    assert GENERALIZED_COORDINATE_UNITS == ("rad",) * 6 + ("m",) * 2
    assert GENERALIZED_RATE_UNITS == ("rad/s",) * 6 + ("m/s",) * 2
    assert record["revolute"]["nonzero"] is True
    assert record["prismatic"]["nonzero"] is True
    assert record["heterogeneous_global_norm_used"] is False


def test_valid_capability_and_synthetic_policy_advance_real_state_through_coordinator() -> None:
    *_, result = _executed_step()
    evolution = result.state_evolution
    assert result.executed_action.is_abort is False
    assert result.capability_consumed is True
    assert result.backend_invocation_delta == 1
    assert result.production_credit is False
    assert evolution["accepted"] is True
    assert evolution["reason_code"] == "REAL_NUMERICAL_STATE_EVOLUTION_DETECTED"
    deltas = evolution["deltas"]
    assert deltas["revolute_qdot_max_abs_rad_s"] > 1.0e-6
    assert deltas["prismatic_qdot_max_abs_m_s"] > 1.0e-7
    assert deltas["base_twist_angular_norm_rad_s"] > 1.0e-7
    assert deltas["ee_centroid_position_norm_m"] > 1.0e-10
    assert evolution["base_linear_and_angular_twist_audited_separately"] is True
    assert evolution["heterogeneous_global_norm_used"] is False


def test_phase_only_fake_backend_is_detected() -> None:
    result = phase_only_negative_control(initial_diagnostic_state())
    assert result["physical_state_changed"] is False
    assert result["phase_changed"] is True
    assert result["accepted"] is False
    assert result["reason_code"] == "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY"


def test_public_backend_direct_calls_are_always_precisely_rejected() -> None:
    backend = SyntheticCapabilityBackend()
    with pytest.raises(PermissionError) as caught:
        backend.execute(capability="EVEN_A_REAL_CAPABILITY_IS_NOT_AN_INVOCATION")
    assert str(caught.value) == "BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR"
    with pytest.raises(PermissionError) as caught:
        backend.execute_authorized_kernel(invocation=object.__new__(OpaqueInvocation))
    assert str(caught.value) == "BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR"


def test_opaque_invocation_construction_copy_identity_and_replay_guards() -> None:
    probe = DiagnosticExecutionCoordinator().opaque_invocation_security_probe()
    assert probe["passed"] is True
    assert probe["direct_construction_reason"] == "OPAQUE_INVOCATION_DIRECT_CONSTRUCTION_REJECTED"
    assert probe["object_new_accepted"] is False
    assert probe["object_new_reason"] == "OPAQUE_INVOCATION_UNREGISTERED"
    assert probe["copy_constructor_rejected"] is True
    assert probe["manual_clone_accepted"] is False
    assert probe["manual_clone_reason"] == "OPAQUE_INVOCATION_OBJECT_IDENTITY_MISMATCH"
    assert probe["registered_original_accepted_once"] is True
    assert probe["replay_accepted"] is False
    assert probe["replay_reason"] == "OPAQUE_INVOCATION_REPLAY_REJECTED"
    assert probe["module_private_forge_primitives"] == []
    assert "monkeypatch" in probe["cooperative_api_boundary"]


def test_importing_all_module_private_names_yields_no_factory_token_or_invocation_issuer() -> None:
    private_objects = {
        name: value for name, value in vars(backend_module).items() if name.startswith("_")
    }
    private_names = set(private_objects)
    assert "_ATTESTATION_FACTORY_TOKEN" not in private_names
    assert "_register_invocation" not in private_names
    assert "_issue_invocation" not in private_names
    facade = SyntheticCapabilityBackend()
    for name, value in private_objects.items():
        with pytest.raises(PermissionError) as caught:
            facade.execute_authorized_kernel(
                invocation=value,
                legacy_attestation={"imported_private_name": name},
            )
        assert str(caught.value) == "BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR"


def test_context_effort_drift_aborts_before_capability_consumption_or_backend() -> None:
    coordinator, action, state, effort, policy, context, snapshot, shield, capability = _execution_fixture()
    drifted_effort = list(effort)
    drifted_effort[0] += 0.001
    result = coordinator.execute(
        action=action,
        state=state,
        generalized_effort=drifted_effort,
        step_s=0.001,
        steps=3,
        context=context,
        gate_snapshot=snapshot,
        capability=capability,
        shield=shield,
        target_policy_fixture=policy,
        mission_veto_receipt=None,
    )
    assert result.executed_action.is_abort
    assert result.coordinator_reason_code == "COORDINATOR_CONTEXT_STATE_EFFORT_OR_POLICY_MISMATCH"
    assert result.capability_consumed is False
    assert result.backend_invocation_delta == 0
    assert result.after.as_dict() == state.as_dict()


def test_capability_replay_cannot_advance_backend_twice() -> None:
    coordinator, action, state, effort, policy, context, snapshot, shield, capability, first = _executed_step()
    second = coordinator.execute(
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
        mission_veto_receipt=None,
    )
    assert first.executed_action.is_abort is False
    assert second.executed_action.is_abort
    assert second.coordinator_reason_code == "CAPABILITY_NONCE_REPLAY"
    assert second.backend_invocation_delta == 0
    np.testing.assert_allclose(second.after.q_mixed_rad_m, state.q_mixed_rad_m)


def test_unknown_target_policy_aborts_before_capability_or_backend() -> None:
    coordinator, action, state, effort, policy, _, snapshot, shield, _ = _execution_fixture()
    unknown_policy = dict(policy)
    unknown_policy["policy_id"] = "FORGED_ALLOW"
    context = build_execution_context(
        run_id=f"SIM13-V4-UNKNOWN-POLICY-{next(_SEQUENCE)}",
        state=state,
        generalized_effort=effort,
        step_s=0.001,
        steps=3,
        target_policy_fixture=unknown_policy,
    )
    capability = shield.issue_capability(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        nonce=f"UNKNOWN-POLICY-{next(_SEQUENCE)}",
        validity_window_s=2.0,
    )
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
        target_policy_fixture=unknown_policy,
        mission_veto_receipt=None,
    )
    assert result.coordinator_reason_code == "TARGET_POLICY_UNKNOWN_FAIL_CLOSED"
    assert result.backend_invocation_delta == 0
    assert result.capability_consumed is False
