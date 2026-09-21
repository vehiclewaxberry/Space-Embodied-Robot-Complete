#!/usr/bin/env python3
"""Generate deterministic V4 synthetic runtime-guard diagnostic evidence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import csv
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sim13_v4.canonical import canonical_digest, file_record
from sim13_v4.diagnostic_backend import (
    BACKEND_ID,
    GENERALIZED_COORDINATE_UNITS,
    GENERALIZED_EFFORT_UNITS,
    GENERALIZED_RATE_UNITS,
    DiagnosticExecutionCoordinator,
    SyntheticCapabilityBackend,
    build_execution_context,
    debris_veto_policy_fixture,
    effort_record,
    initial_diagnostic_state,
    nominal_generalized_effort,
    phase_only_negative_control,
    synthetic_non_debris_policy_fixture,
)
from sim13_v4.mission_veto import (
    Sim10MissionVeto,
    TargetRequest,
    VetoReceipt,
    debris_150kg_3dps_request,
    diagnostic_resign_veto_payload,
    sim10_artifact_records,
)
from sim13_v4.runtime_guard import (
    DiagnosticAction,
    DiagnosticCapability,
    DiagnosticClock,
    DiagnosticShield,
    NONCE_PERSISTENCE_BOUNDARY,
    NonceLedger,
    synthetic_gate_snapshot,
)


EVIDENCE_DIR = HERE / "evidence"
RESULTS_DIR = HERE / "results"
SOURCE_MANIFEST_PATH = EVIDENCE_DIR / "SIM13_V4_SOURCE_MANIFEST_V1.csv"
LEDGER_PATH = EVIDENCE_DIR / "SIM13_V4_RUNTIME_GUARD_LEDGER_V1.json"
V2_GATE_PATH = (
    HERE.parent
    / "v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json"
)
V3_GATE_PATH = (
    HERE.parent
    / "v3_in_memory_dynamics_diagnostic/results/SIM13_V3_PHASE_A_DYNAMICS_GATE_V2.json"
)


SOURCE_PATHS: tuple[tuple[str, str], ...] = (
    ("README.md", "scope_and_reproduction_contract"),
    ("pytest.ini", "test_configuration_no_cache"),
    ("sim13_v4/__init__.py", "authority_boundary_constants"),
    ("sim13_v4/canonical.py", "canonical_digest_kernel"),
    ("sim13_v4/runtime_guard.py", "capability_and_replay_guard"),
    ("sim13_v4/diagnostic_backend.py", "v3_public_synthetic_dynamics_adapter"),
    ("sim13_v4/mission_veto.py", "sim10_read_only_veto_adapter"),
    ("tests/conftest.py", "test_path_bootstrap"),
    ("tests/test_runtime_capability.py", "nc15_capability_tests"),
    ("tests/test_backend_state_evolution.py", "nc16_nc18_backend_tests"),
    ("tests/test_sim10_veto.py", "nc20_veto_tests"),
    ("tests/test_authority_boundary.py", "scope_and_no_generator_tests"),
    ("generate_runtime_guard_evidence.py", "deterministic_evidence_builder"),
    ("independent_audit_runtime_guard.py", "independent_recomputation"),
    ("validate_runtime_guard_v4.py", "package_validator_and_gate_writer"),
)


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_bytes(payload.encode("utf-8"))


def build_source_manifest_bytes() -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=("path", "bytes", "sha256", "role"),
        lineterminator="\n",
    )
    writer.writeheader()
    for relative, role in SOURCE_PATHS:
        record = file_record(HERE / relative, PROJECT_ROOT)
        writer.writerow({**record, "role": role})
    return stream.getvalue().encode("utf-8")


def write_source_manifest() -> dict[str, object]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_MANIFEST_PATH.write_bytes(build_source_manifest_bytes())
    return file_record(SOURCE_MANIFEST_PATH, PROJECT_ROOT)


def _fixture(run_id: str, *, clock_s: float, nonce: str):
    action = DiagnosticAction("GC_SYNTHETIC", "T_SYNTHETIC", "S1")
    state = initial_diagnostic_state()
    effort = nominal_generalized_effort()
    policy = synthetic_non_debris_policy_fixture()
    context = build_execution_context(
        run_id=run_id,
        state=state,
        generalized_effort=effort,
        step_s=0.001,
        steps=3,
        target_policy_fixture=policy,
    )
    snapshot = synthetic_gate_snapshot()
    clock = DiagnosticClock(clock_s)
    shield = DiagnosticShield(clock=clock)
    capability = shield.issue_capability(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        nonce=nonce,
        validity_window_s=2.0,
    )
    return action, state, effort, policy, context, snapshot, clock, shield, capability


def _decision_record(decision: object, nonce: str) -> dict[str, object]:
    return {
        "allowed": bool(decision.allowed),
        "executed_action": decision.executed_action.as_dict(),
        "reason_code": decision.reason_code,
        "consumed_nonce_returned": decision.consumed_nonce,
        "canonical_module_nonce_consumed": NonceLedger().is_consumed(nonce),
    }


def _probe_nc15() -> dict[str, object]:
    cases: dict[str, dict[str, object]] = {}

    action, _, _, _, context, snapshot, clock, shield, capability = _fixture(
        "SIM13-V4-NC15-STALE", clock_s=1000.0, nonce="NC15-STALE"
    )
    clock.advance(2.000001)
    decision = shield.authorize_and_consume(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        capability=capability,
    )
    cases["stale"] = _decision_record(decision, "NC15-STALE")

    action, _, _, _, context, snapshot, _, shield, capability = _fixture(
        "SIM13-V4-NC15-REPLAY", clock_s=1010.0, nonce="NC15-REPLAY"
    )
    baseline = shield.authorize_and_consume(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        capability=capability,
    )
    second_shield = DiagnosticShield(clock=DiagnosticClock(1010.0))
    replay = shield.authorize_and_consume(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        capability=capability,
    )
    cases["replay"] = {
        "qualified_single_use_baseline": _decision_record(baseline, "NC15-REPLAY"),
        "same_shield_replay": _decision_record(replay, "NC15-REPLAY"),
    }
    cross_shield = second_shield.authorize_and_consume(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        capability=capability,
    )
    cases["cross_shield_new_ledger_replay"] = {
        "decision": _decision_record(cross_shield, "NC15-REPLAY"),
        "new_ledger_view_reports_consumed": NonceLedger().is_consumed("NC15-REPLAY"),
        "new_ledger_view_reconsume_allowed": NonceLedger().consume_once("NC15-REPLAY"),
        "isolated_ledger_injection_api_available": False,
    }

    action, _, _, _, context, snapshot, _, shield, capability = _fixture(
        "SIM13-V4-NC15-ACTION", clock_s=1020.0, nonce="NC15-ACTION"
    )
    changed_action = DiagnosticAction("GC_OTHER", "T_SYNTHETIC", "S1")
    decision = shield.authorize_and_consume(
        action=changed_action,
        context=context,
        gate_snapshot=snapshot,
        capability=capability,
    )
    cases["action_mismatch"] = _decision_record(decision, "NC15-ACTION")

    action, _, _, _, context, snapshot, _, shield, capability = _fixture(
        "SIM13-V4-NC15-CONTEXT", clock_s=1030.0, nonce="NC15-CONTEXT"
    )
    changed_context = dict(context)
    changed_context["run_id"] = "MISMATCHED-RUN"
    decision = shield.authorize_and_consume(
        action=action,
        context=changed_context,
        gate_snapshot=snapshot,
        capability=capability,
    )
    cases["context_mismatch"] = _decision_record(decision, "NC15-CONTEXT")

    action, _, _, _, context, snapshot, _, shield, capability = _fixture(
        "SIM13-V4-NC15-SNAPSHOT", clock_s=1040.0, nonce="NC15-SNAPSHOT"
    )
    changed_snapshot = synthetic_gate_snapshot(
        overrides={"contact_physics_ready": "UNKNOWN"}
    )
    decision = shield.authorize_and_consume(
        action=action,
        context=context,
        gate_snapshot=changed_snapshot,
        capability=capability,
    )
    cases["snapshot_mismatch"] = _decision_record(decision, "NC15-SNAPSHOT")

    action, _, _, _, context, snapshot, _, shield, capability = _fixture(
        "SIM13-V4-NC15-SIGNATURE", clock_s=1050.0, nonce="NC15-SIGNATURE"
    )
    tampered = DiagnosticCapability(capability.payload, "0" * 64)
    decision = shield.authorize_and_consume(
        action=action,
        context=context,
        gate_snapshot=snapshot,
        capability=tampered,
    )
    cases["signature_tamper"] = _decision_record(decision, "NC15-SIGNATURE")

    action, _, _, _, context, snapshot, _, issuer, capability = _fixture(
        "SIM13-V4-NC15-THREAD-RACE", clock_s=1060.0, nonce="NC15-THREAD-RACE"
    )
    shields = [issuer] + [DiagnosticShield(clock=DiagnosticClock(1060.0)) for _ in range(15)]
    with ThreadPoolExecutor(max_workers=16) as executor:
        race_decisions = list(
            executor.map(
                lambda item: item.authorize_and_consume(
                    action=action,
                    context=context,
                    gate_snapshot=snapshot,
                    capability=capability,
                ),
                shields,
            )
        )
    cases["thread_safe_cross_shield_race"] = {
        "attempts": len(race_decisions),
        "allowed": sum(int(item.allowed) for item in race_decisions),
        "replay_rejections": sum(
            item.reason_code == "CAPABILITY_NONCE_REPLAY" for item in race_decisions
        ),
        "canonical_module_nonce_consumed": NonceLedger().is_consumed(
            "NC15-THREAD-RACE"
        ),
    }

    expected = {
        "stale": "CAPABILITY_STALE",
        "action_mismatch": "CAPABILITY_ACTION_MISMATCH",
        "context_mismatch": "CAPABILITY_CONTEXT_MISMATCH",
        "snapshot_mismatch": "CAPABILITY_GATE_SNAPSHOT_MISMATCH",
        "signature_tamper": "CAPABILITY_SIGNATURE_INVALID",
    }
    passed = all(
        cases[name]["allowed"] is False
        and cases[name]["executed_action"]["strategy_id"] == "ABORT"
        and cases[name]["reason_code"] == reason
        and cases[name]["canonical_module_nonce_consumed"] is False
        for name, reason in expected.items()
    )
    passed = passed and (
        cases["replay"]["qualified_single_use_baseline"]["allowed"] is True
        and cases["replay"]["same_shield_replay"]["allowed"] is False
        and cases["replay"]["same_shield_replay"]["reason_code"]
        == "CAPABILITY_NONCE_REPLAY"
        and cases["replay"]["same_shield_replay"]["executed_action"]["strategy_id"]
        == "ABORT"
        and cases["cross_shield_new_ledger_replay"]["decision"]["reason_code"]
        == "CAPABILITY_NONCE_REPLAY"
        and cases["cross_shield_new_ledger_replay"]["new_ledger_view_reports_consumed"]
        is True
        and cases["cross_shield_new_ledger_replay"]["new_ledger_view_reconsume_allowed"]
        is False
        and cases["thread_safe_cross_shield_race"]["allowed"] == 1
        and cases["thread_safe_cross_shield_race"]["replay_rejections"] == 15
    )
    return {
        "control_id": "NC15",
        "scope": "SYNTHETIC_DIAGNOSTIC_EXECUTION_NOT_FORMAL_PRODUCTION_NC_CREDIT",
        "cases": cases,
        "persistence_boundary": NONCE_PERSISTENCE_BOUNDARY,
        "passed_diagnostic": passed,
        "formal_v2_status_changed": False,
    }


def _probe_nc18_and_nc16() -> tuple[dict[str, object], dict[str, object]]:
    (
        action, state, effort, policy, context, snapshot, _, shield, capability,
    ) = _fixture("SIM13-V4-NC18", clock_s=2000.0, nonce="NC18-ONE-SHOT")
    coordinator = DiagnosticExecutionCoordinator()
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
    try:
        SyntheticCapabilityBackend().execute(capability=capability)
    except PermissionError as exc:
        bypass_reason = str(exc)
    else:
        bypass_reason = "DIRECT_BYPASS_ESCAPED"
    nc16_pass = (
        bypass_reason == "BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR"
        and result.executed_action.is_abort is False
        and result.capability_consumed is True
        and result.backend_invocation_delta == 1
    )
    opaque_probe = coordinator.opaque_invocation_security_probe()
    nc16_pass = nc16_pass and opaque_probe["passed"] is True
    nc16 = {
        "control_id": "NC16",
        "scope": "SYNTHETIC_DIAGNOSTIC_EXECUTION_NOT_FORMAL_PRODUCTION_NC_CREDIT",
        "direct_bypass_reason": bypass_reason,
        "shielded_baseline_executed": result.executed_action.is_abort is False,
        "shielded_capability_consumed": result.capability_consumed,
        "coordinator_backend_invocation_delta": result.backend_invocation_delta,
        "opaque_invocation_negative_controls": opaque_probe,
        "capability_alone_is_backend_invocation": False,
        "security_boundary": "COOPERATIVE_PYTHON_API_DIAGNOSTIC_ONLY__MALICIOUS_MONKEYPATCH_OR_CLOSURE_INTROSPECTION_OUT_OF_SCOPE",
        "passed_diagnostic": nc16_pass,
        "formal_v2_status_changed": False,
    }
    phase_negative = phase_only_negative_control(state)
    phase_only_before = state.as_dict()
    phase_only_after = dict(phase_only_before)
    phase_only_after["phase"] = "FAKE_PHASE_ADVANCE_WITHOUT_PHYSICS"
    nc18_pass = (
        result.state_evolution["accepted"] is True
        and result.state_evolution["physical_state_changed"] is True
        and phase_negative["accepted"] is False
        and phase_negative["reason_code"]
        == "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY"
        and effort_record(effort)["revolute"]["nonzero"] is True
        and effort_record(effort)["prismatic"]["nonzero"] is True
    )
    nc18 = {
        "control_id": "NC18",
        "scope": "SYNTHETIC_V3_PUBLIC_6R2P_REDUCED_DYNAMICS_NOT_CURRENT_SYSTEM",
        "backend_id": BACKEND_ID,
        "action": action.as_dict(),
        "gate_snapshot": snapshot,
        "context": context,
        "target_policy_fixture": policy,
        "capability": capability.as_dict(),
        "input": {
            "initial_state": state.as_dict(),
            "generalized_effort": effort_record(effort),
            "step_s": 0.001,
            "steps": 3,
        },
        "output": {
            "executed_action": result.executed_action.as_dict(),
            "final_state": result.after.as_dict(),
            "coordinator_reason_code": result.coordinator_reason_code,
            "backend_reason_code": result.backend_reason_code,
            "state_evolution": dict(result.state_evolution),
            "capability_consumed": result.capability_consumed,
            "production_credit": result.production_credit,
            "backend_invocation_count_before": result.backend_invocation_count_before,
            "backend_invocation_count_after": result.backend_invocation_count_after,
            "backend_invocation_delta": result.backend_invocation_delta,
        },
        "phase_only_negative_control": {
            "before": phase_only_before,
            "after": phase_only_after,
            "assessment": phase_negative,
        },
        "unit_contract": {
            "coordinate_units": list(GENERALIZED_COORDINATE_UNITS),
            "rate_units": list(GENERALIZED_RATE_UNITS),
            "effort_units": list(GENERALIZED_EFFORT_UNITS),
            "heterogeneous_global_norm_used": False,
            "base_linear_and_angular_twist_audited_separately": True,
        },
        "passed_diagnostic": nc18_pass,
        "formal_v2_status_changed": False,
    }
    return nc16, nc18


def _veto_decision_record(decision: object) -> dict[str, object]:
    return {
        "allowed": decision.allowed,
        "executed_action": decision.executed_action.as_dict(),
        "reason_code": decision.reason_code,
        "receipt_verified": decision.receipt_verified,
        "historical_sim10_pass_inherited_to_current_system": (
            decision.historical_sim10_pass_inherited_to_current_system
        ),
    }


def _probe_nc20() -> dict[str, object]:
    action = DiagnosticAction("GC_DEBRIS", "T_CAPTURE", "S1")
    snapshot = synthetic_gate_snapshot()
    target = debris_150kg_3dps_request()
    evaluator = Sim10MissionVeto()
    receipt = evaluator.issue_veto_receipt(
        action=action, gate_snapshot=snapshot, target=target
    )
    valid = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=receipt,
    )
    other_action = DiagnosticAction("GC_OTHER", "T_CAPTURE", "S1")
    action_mismatch = evaluator.decide(
        action=other_action,
        gate_snapshot=snapshot,
        target=target,
        receipt=receipt,
    )
    changed_snapshot = synthetic_gate_snapshot(overrides={"sim10_gate": "UNKNOWN"})
    snapshot_mismatch = evaluator.decide(
        action=action,
        gate_snapshot=changed_snapshot,
        target=target,
        receipt=receipt,
    )
    target_mismatch = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=TargetRequest("target_debris_v0", 151.0, 3.0),
        receipt=receipt,
    )
    anchor_payload = deepcopy(dict(receipt.payload))
    anchor_payload["anchor_id"] = "unknown_anchor"
    anchor_mismatch = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=diagnostic_resign_veto_payload(anchor_payload),
    )
    hash_payload = deepcopy(dict(receipt.payload))
    hash_payload["sim10_gate_sha256"] = "0" * 64
    hash_mismatch = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=diagnostic_resign_veto_payload(hash_payload),
    )
    unknown = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=None,
    )
    malformed_payload = deepcopy(dict(receipt.payload))
    malformed_payload["anchor_w_plus_dps"] = "not-a-number"
    malformed = evaluator.decide(
        action=action,
        gate_snapshot=snapshot,
        target=target,
        receipt=diagnostic_resign_veto_payload(malformed_payload),
    )
    cases = {
        "valid_infeasible_rate_veto": _veto_decision_record(valid),
        "action_mismatch": _veto_decision_record(action_mismatch),
        "snapshot_mismatch": _veto_decision_record(snapshot_mismatch),
        "target_mismatch": _veto_decision_record(target_mismatch),
        "anchor_drift": _veto_decision_record(anchor_mismatch),
        "hash_drift": _veto_decision_record(hash_mismatch),
        "unknown_receipt": _veto_decision_record(unknown),
        "resigned_malformed_numeric": _veto_decision_record(malformed),
    }
    expected = {
        "valid_infeasible_rate_veto": "MISSION_VETO_INFEASIBLE_RATE",
        "action_mismatch": "SIM10_VETO_RECEIPT_ACTION_MISMATCH",
        "snapshot_mismatch": "SIM10_VETO_RECEIPT_SNAPSHOT_MISMATCH",
        "target_mismatch": "SIM10_VETO_RECEIPT_TARGET_MISMATCH",
        "anchor_drift": "SIM10_VETO_RECEIPT_ANCHOR_DRIFT",
        "hash_drift": "SIM10_VETO_RECEIPT_HASH_DRIFT",
        "unknown_receipt": "SIM10_VETO_RECEIPT_UNKNOWN",
        "resigned_malformed_numeric": "SIM10_VETO_RECEIPT_MALFORMED_TYPE",
    }
    passed = all(
        cases[name]["allowed"] is False
        and cases[name]["executed_action"]["strategy_id"] == "ABORT"
        and cases[name]["reason_code"] == reason
        and cases[name]["historical_sim10_pass_inherited_to_current_system"]
        is False
        for name, reason in expected.items()
    )
    passed = passed and cases["valid_infeasible_rate_veto"]["receipt_verified"] is True

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
    drift_specs = {
        "action_drift": (
            "action_sha256",
            "0" * 64,
            "SIM10_VETO_RECEIPT_ACTION_MISMATCH",
        ),
        "snapshot_drift": (
            "gate_snapshot_sha256",
            "0" * 64,
            "SIM10_VETO_RECEIPT_SNAPSHOT_MISMATCH",
        ),
        "target_drift": (
            "target_sha256",
            "0" * 64,
            "SIM10_VETO_RECEIPT_TARGET_MISMATCH",
        ),
        "anchor_drift": (
            "anchor_id",
            "unknown_anchor",
            "SIM10_VETO_RECEIPT_ANCHOR_DRIFT",
        ),
        "hash_drift": (
            "sim10_gate_sha256",
            "0" * 64,
            "SIM10_VETO_RECEIPT_HASH_DRIFT",
        ),
        "malformed_numeric": (
            "anchor_w_plus_dps",
            "not-a-number",
            "SIM10_VETO_RECEIPT_MALFORMED_TYPE",
        ),
    }
    drifted_inputs: list[tuple[str, VetoReceipt, str]] = []
    for name, (field, value, reason) in drift_specs.items():
        payload = deepcopy(dict(receipt.payload))
        payload[field] = value
        drifted_inputs.append(
            (name, diagnostic_resign_veto_payload(payload), reason)
        )
    coordinator_inputs = (
        ("missing_receipt", None, "SIM10_VETO_RECEIPT_UNKNOWN"),
        ("valid_infeasible_veto", receipt, "MISSION_VETO_INFEASIBLE_RATE"),
        *drifted_inputs,
    )
    coordinator = DiagnosticExecutionCoordinator()
    state_digest = canonical_digest(state.as_dict())
    coordinator_cases: dict[str, object] = {}
    for name, candidate_receipt, expected_reason in coordinator_inputs:
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
        coordinator_cases[name] = {
            "expected_reason": expected_reason,
            "observed_reason": result.coordinator_reason_code,
            "executed_action": result.executed_action.as_dict(),
            "capability_consumed": result.capability_consumed,
            "backend_invocation_count_before": result.backend_invocation_count_before,
            "backend_invocation_count_after": result.backend_invocation_count_after,
            "backend_invocation_delta": result.backend_invocation_delta,
            "before_state_sha256": canonical_digest(result.before.as_dict()),
            "after_state_sha256": canonical_digest(result.after.as_dict()),
            "state_byte_semantic_unchanged": (
                result.before.as_dict() == result.after.as_dict() == state.as_dict()
            ),
        }
    try:
        SyntheticCapabilityBackend().execute(capability=capability)
    except PermissionError as exc:
        direct_backend_reason = str(exc)
    else:
        direct_backend_reason = "DIRECT_CAPABILITY_BYPASS_ESCAPED"
    coordinator_pass = all(
        item["observed_reason"] == item["expected_reason"]
        and item["executed_action"]["strategy_id"] == "ABORT"
        and item["capability_consumed"] is False
        and item["backend_invocation_delta"] == 0
        and item["state_byte_semantic_unchanged"] is True
        and item["before_state_sha256"] == state_digest
        and item["after_state_sha256"] == state_digest
        for item in coordinator_cases.values()
    )
    coordinator_pass = (
        coordinator_pass
        and coordinator.backend_invocation_count == 0
        and NonceLedger().is_consumed(nonce) is False
        and direct_backend_reason
        == "BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR"
    )
    passed = passed and coordinator_pass
    return {
        "control_id": "NC20",
        "scope": "HISTORICAL_SIM10_HASH_BOUND_ACTION_VETO_DIAGNOSTIC_NOT_CURRENT_R2_PASS",
        "action": action.as_dict(),
        "gate_snapshot": snapshot,
        "target": target.as_dict(),
        "target_policy_fixture": policy,
        "coordinator_context": context,
        "coordinator_capability": capability.as_dict(),
        "receipt": receipt.as_dict(),
        "sim10_artifacts": sim10_artifact_records(),
        "cases": cases,
        "coordinator_prebackend_veto_cases": coordinator_cases,
        "coordinator_backend_invocation_count_final": coordinator.backend_invocation_count,
        "coordinator_capability_nonce_consumed": NonceLedger().is_consumed(nonce),
        "direct_capability_backend_bypass_reason": direct_backend_reason,
        "veto_precedes_capability_consumption_and_backend": coordinator_pass,
        "passed_diagnostic": passed,
        "formal_v2_status_changed": False,
    }


def build_ledger() -> dict[str, Any]:
    if not SOURCE_MANIFEST_PATH.is_file():
        raise FileNotFoundError("source manifest must be written before the ledger")
    v2_gate = json.loads(V2_GATE_PATH.read_text(encoding="utf-8"))
    if not (
        v2_gate.get("formal_negative_controls_passed") == 15
        and v2_gate.get("formal_negative_controls_declared") == 20
        and v2_gate.get("formal_negative_controls_hold_ids")
        == ["NC15", "NC16", "NC18", "NC19", "NC20"]
    ):
        raise RuntimeError("current V2 formal NC state has changed; fail closed")
    nc15 = _probe_nc15()
    nc16, nc18 = _probe_nc18_and_nc16()
    nc20 = _probe_nc20()
    controls = {item["control_id"]: item for item in (nc15, nc16, nc18, nc20)}
    passed = all(item["passed_diagnostic"] for item in controls.values())
    return {
        "schema": "SIM13_V4_RUNTIME_GUARD_DIAGNOSTIC_LEDGER_V1",
        "generated_date_local": "2026-08-24",
        "scope": "SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY",
        "technical_verdict": (
            "PASS_SYNTHETIC_RUNTIME_GUARD_LOGIC_DIAGNOSTIC_ONLY"
            if passed
            else "FAIL_SYNTHETIC_RUNTIME_GUARD_DIAGNOSTIC"
        ),
        "source_manifest": file_record(SOURCE_MANIFEST_PATH, PROJECT_ROOT),
        "read_only_provenance": {
            "v2_formal_gate": file_record(V2_GATE_PATH, PROJECT_ROOT),
            "v3_synthetic_dynamics_gate": file_record(V3_GATE_PATH, PROJECT_ROOT),
            "sim10": sim10_artifact_records(),
        },
        "formal_v2_negative_control_state": {
            "passed": v2_gate["formal_negative_controls_passed"],
            "declared": v2_gate["formal_negative_controls_declared"],
            "hold_ids": v2_gate["formal_negative_controls_hold_ids"],
            "unchanged_by_v4": True,
        },
        "diagnostic_controls": controls,
        "diagnostic_summary": {
            "declared": 4,
            "executed": 4,
            "passed": sum(
                int(item["passed_diagnostic"]) for item in controls.values()
            ),
            "failed": sum(
                int(not item["passed_diagnostic"]) for item in controls.values()
            ),
            "control_ids": ["NC15", "NC16", "NC18", "NC20"],
            "all_passed_diagnostic": passed,
            "formal_production_nc_credit": False,
        },
        "nc19": {
            "status": "HOLD_AUTHORITATIVE_NARROW_PHASE_CONTACT_AND_RELEASED_GEOMETRY_ABSENT",
            "executed": False,
            "passed": False,
        },
        "diagnostic_boundaries": {
            "nc15_nonce_persistence": (
                NONCE_PERSISTENCE_BOUNDARY
            ),
            "nc16_capability_security": (
                "COOPERATIVE_PYTHON_API_DIAGNOSTIC_ONLY__"
                "MALICIOUS_MONKEYPATCH_OR_CLOSURE_INTROSPECTION_OUT_OF_SCOPE"
            ),
            "nc18_dynamics": (
                "SYNTHETIC_V3_PUBLIC_6R2P_REDUCED_DYNAMICS_ONLY__"
                "NOT_CURRENT_SYSTEM_NOT_CONTACT"
            ),
            "nc20_veto": (
                "FOUR_SIM10_ARTIFACT_SHA_BINDINGS__GATE_SUMMARY_REGION_AND_"
                "W_PLUS__PARAMETER_CARD_CALIBRATION_MASS__ANCHOR_SOURCE_MASS_"
                "AND_TUMBLE__VETO_BEFORE_CAPABILITY_CONSUMPTION_AND_BACKEND"
            ),
        },
        "authority_flags": {
            "owner_accepted": False,
            "current_system_passed": False,
            "current_system_binding_passed": False,
            "system_binding_passed": False,
            "runtime_fail_closed_gate_passed": False,
            "runtime_production_gate_passed": False,
            "production_dynamics_gate_passed": False,
            "contact_grasp_gate_passed": False,
            "system_urdf_available": False,
            "system_interface_instantiated": False,
            "release_credit": False,
            "next_stage_authorized": False,
        },
        "truth_guard": (
            "V4 proves four guard capabilities on synthetic/read-only fixtures only; "
            "it does not convert current V2 formal 15/20 into 19/20 or any production PASS"
        ),
    }


def write_ledger() -> dict[str, Any]:
    document = build_ledger()
    _write_json(LEDGER_PATH, document)
    return document


def main() -> int:
    manifest = write_source_manifest()
    ledger = write_ledger()
    print(
        json.dumps(
            {
                "source_manifest_sha256": manifest["sha256"],
                "diagnostic_summary": ledger["diagnostic_summary"],
                "technical_verdict": ledger["technical_verdict"],
            },
            sort_keys=True,
        )
    )
    return 0 if ledger["diagnostic_summary"]["all_passed_diagnostic"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
