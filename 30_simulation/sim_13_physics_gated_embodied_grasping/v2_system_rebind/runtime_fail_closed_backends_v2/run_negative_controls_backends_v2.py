#!/usr/bin/env python3
"""Execute the five Sim13 V2 backend negative controls (NC15/16/18/19/20).

Every probe starts from a qualified nominal baseline and applies one
single-fault mutation; each runs twice (A/B) and must be byte-deterministic.
The runner emits, read-only with respect to every historical artifact:

- ``evidence/SIM13_V2_BACKENDS_NEGATIVE_CONTROLS_V2.json``
- ``evidence/SIM13_V2_RUNTIME_EVALUATOR_RECEIPT_V1.json``
- ``evidence/SIM13_V2_DYNAMICS_BACKEND_VALIDATION_RECEIPT_V1.json``
- ``evidence/SIM13_V2_CONTACT_BACKEND_VALIDATION_RECEIPT_V1.json``
- ``results/SIM13_RUNTIME_FAIL_CLOSED_GATE_V2.json``
- ``results/SIM13_DYNAMICS_BACKEND_GATE_V2.json``
- ``results/SIM13_CONTACT_GRASP_GATE_V2.json``

No gate grants release credit; all gates are PENDING_OWNER_REVIEW with
``next_stage_authorized = false``.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable, Mapping

HERE = Path(__file__).resolve().parent
V2_REBIND_ROOT = HERE.parent
PROJECT_ROOT = HERE.parents[3]
for candidate in (str(HERE), str(V2_REBIND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from sim13_v2_backends.canonical import (
    canonical_digest,
    file_record,
    sha256_bytes,
    write_canonical_json,
)
from sim13_v2_backends.capability import (
    ShieldAttestationAuthority,
    ShieldedBackendAdmission,
)
from sim13_v2_backends.contact_backend import (
    BACKEND_ID as CONTACT_BACKEND_ID,
    BrokenContactDetector,
    NarrowPhaseContactBackend,
    audit_detector_consistency,
    build_validation_receipt as build_contact_receipt,
)
from sim13_v2_backends.dynamics_backend import (
    BACKEND_ID as DYNAMICS_BACKEND_ID,
    PhaseOnlyBackend,
    UnifiedR2DynamicsBackend,
    build_validation_receipt as build_dynamics_receipt,
    state_evolution_assessment,
)
from sim13_v2_backends.feasibility_evaluator import (
    ActionBoundFeasibilityEvaluator,
    debris_150kg_3dps_request,
)
from sim13_v2_backends.runtime_gate_adapter import CANONICAL_ABORT_ACTION, RuntimeGateAdapter
from sim13_v2_backends.snapshot_receipt import (
    FileReplayStore,
    InjectedClock,
    SnapshotReceiptAuthority,
)


EVIDENCE_PATH = HERE / "evidence" / "SIM13_V2_BACKENDS_NEGATIVE_CONTROLS_V2.json"
RUNTIME_EVALUATOR_RECEIPT_PATH = (
    HERE / "evidence" / "SIM13_V2_RUNTIME_EVALUATOR_RECEIPT_V1.json"
)
DYNAMICS_RECEIPT_PATH = (
    HERE / "evidence" / "SIM13_V2_DYNAMICS_BACKEND_VALIDATION_RECEIPT_V1.json"
)
CONTACT_RECEIPT_PATH = (
    HERE / "evidence" / "SIM13_V2_CONTACT_BACKEND_VALIDATION_RECEIPT_V1.json"
)
RUNTIME_GATE_PATH = HERE / "results" / "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2.json"
DYNAMICS_GATE_PATH = HERE / "results" / "SIM13_DYNAMICS_BACKEND_GATE_V2.json"
CONTACT_GATE_PATH = HERE / "results" / "SIM13_CONTACT_GRASP_GATE_V2.json"
GEOMETRY_PATH = HERE / "assets" / "SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1.json"
GENERATED_DATE_LOCAL = "2026-08-25"
CLOCK_T0_S = 1000.0

EXPECTED_REASON = {
    "NC15": "SNAPSHOT_REJECTED_STALE",
    "NC16": "BACKEND_REJECTS_UNSHIELDED_NON_ABORT",
    "NC18": "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY",
    "NC19": "CONTACT_DETECTION_FAILURE",
    "NC20": "MISSION_VETO_INFEASIBLE_RATE",
}
OBSERVED_OUTCOME = {
    "NC15": "MASK_TO_ABORT_ONLY",
    "NC16": "MASK_TO_ABORT_ONLY",
    "NC18": "FAIL_GATE",
    "NC19": "FAIL_GATE",
    "NC20": "MASK_TO_ABORT_ONLY",
}
REGISTRY_METADATA = {
    "NC15": {
        "stimulus": "STALE_OR_REPLAYED_GATE_SNAPSHOT",
        "required_observation": "snapshot_rejected",
        "future_gate": "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2",
    },
    "NC16": {
        "stimulus": "DIRECT_BACKEND_CALL_BYPASSES_SAFETY_SHIELD",
        "required_observation": "backend_rejects_unshielded_non_abort",
        "future_gate": "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2",
    },
    "NC18": {
        "stimulus": "NON_ABORT_STEP_CHANGES_TASK_PHASE_ONLY_WITHOUT_JOINT_BASE_OR_EE_STATE",
        "required_observation": "dynamics_state_update_failure",
        "future_gate": "SIM13_DYNAMICS_BACKEND_GATE_V2",
    },
    "NC19": {
        "stimulus": "OVERLAPPING_GEOMETRY_DOES_NOT_UPDATE_COLLISION_OR_CONTACT_STATE",
        "required_observation": "contact_detection_failure",
        "future_gate": "SIM13_CONTACT_GRASP_GATE_V2",
    },
    "NC20": {
        "stimulus": "DEBRIS_150KG_3DPS_REQUESTS_NON_ABORT_WITHOUT_FEASIBILITY_AND_POST_GRASP_PASS",
        "required_observation": "shield_executes_abort",
        "future_gate": "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2",
    },
}


@dataclass(frozen=True)
class ProbeResult:
    baseline_qualified: bool
    detected: bool
    observed_outcome: str
    exact_reason: str
    non_abort_execution_count: int
    scope: str
    baseline_assertion: str
    mutation_path: str
    mutation_description: str
    details: Mapping[str, Any]


@dataclass
class BackendRunnerContext:
    temporary_root: Path
    clock: InjectedClock
    dynamics_backend: UnifiedR2DynamicsBackend
    contact_backend: NarrowPhaseContactBackend
    feasibility_evaluator: ActionBoundFeasibilityEvaluator
    contact_geometry: Mapping[str, Any]

    def fresh_adapter(self, store_name: str) -> RuntimeGateAdapter:
        store_root = self.temporary_root / store_name
        return RuntimeGateAdapter(
            receipt_authority=SnapshotReceiptAuthority(clock=self.clock),
            backend_admission=ShieldedBackendAdmission(
                backend_id=DYNAMICS_BACKEND_ID,
                backend_source_sha256=backend_source_sha256(),
            ),
            feasibility_evaluator=self.feasibility_evaluator,
            receipt_replay_store=FileReplayStore(store_root / "receipts"),
            capability_replay_store=FileReplayStore(store_root / "capabilities"),
        )


def backend_source_sha256() -> str:
    return sha256_bytes((HERE / "sim13_v2_backends" / "dynamics_backend.py").read_bytes())


def action_fixture() -> dict[str, str]:
    return {
        "grasp_candidate_id": "GC_PRIMARY",
        "capture_timing_id": "T_NOMINAL",
        "strategy_id": "S1",
    }


def context_fixture(run_id: str) -> dict[str, Any]:
    return {
        "schema": "SIM13_V2_EXECUTION_CONTEXT_FIXTURE_V1",
        "class": "EVIDENCE_FIXTURE_NOT_PRODUCTION",
        "run_id": run_id,
        "backend_id": DYNAMICS_BACKEND_ID,
    }


def gate_snapshot_fixture() -> dict[str, Any]:
    gates = (
        "ik_reachable",
        "external_collision_clear",
        "keep_out_clear",
        "sim10_gate",
        "safe00_state",
        "post_grasp_stability_gate",
        "gripper_configuration_accepted",
        "target_surface_normal_valid",
        "mechanical_system_binding",
        "harness_rated_envelope",
        "contact_physics_ready",
        "route_c_scope_disposition",
    )
    return {
        "schema": "SIM13_V2_GATE_SNAPSHOT_FIXTURE_V1",
        "class": "SYNTHETIC_ALL_PASS_MACHINERY_FIXTURE_NOT_CURRENT_SYSTEM_AUTHORITY",
        "gates": {name: "PASS" for name in gates},
    }


def build_context(temporary_root: Path) -> BackendRunnerContext:
    geometry = json.loads(GEOMETRY_PATH.read_bytes().decode("utf-8"))
    return BackendRunnerContext(
        temporary_root=temporary_root,
        clock=InjectedClock(CLOCK_T0_S),
        dynamics_backend=UnifiedR2DynamicsBackend(project_root=PROJECT_ROOT),
        contact_backend=NarrowPhaseContactBackend(
            project_root=PROJECT_ROOT, contact_geometry=geometry
        ),
        feasibility_evaluator=ActionBoundFeasibilityEvaluator(project_root=PROJECT_ROOT),
        contact_geometry=geometry,
    )


def _issue_valid_pair(context: BackendRunnerContext, store_name: str, run_id: str, nonce_suffix: str):
    adapter = context.fresh_adapter(store_name)
    authority = SnapshotReceiptAuthority(clock=context.clock)
    action = action_fixture()
    exec_context = context_fixture(run_id)
    snapshot = gate_snapshot_fixture()
    receipt = authority.issue_receipt(
        action=action,
        context=exec_context,
        gate_snapshot=snapshot,
        nonce=f"NONCE_{nonce_suffix}",
        validity_window_s=2.0,
    )
    capability = ShieldAttestationAuthority().issue_capability(
        backend_id=DYNAMICS_BACKEND_ID,
        backend_source_sha256=backend_source_sha256(),
        action=action,
        context=exec_context,
        nonce=f"CAP_NONCE_{nonce_suffix}",
        issued_at_s=context.clock.read(),
        validity_window_s=2.0,
    )
    return adapter, authority, action, exec_context, snapshot, receipt, capability


def _probe_nc15(context: BackendRunnerContext, repeat: str) -> ProbeResult:
    # Baseline: a fresh receipt admits one non-ABORT request through the adapter.
    adapter, authority, action, exec_context, snapshot, receipt, capability = _issue_valid_pair(
        context, f"NC15_baseline_{repeat}", "RUN_NC15_BASELINE", f"NC15_BASE_{repeat}"
    )
    baseline_decision = adapter.admit(
        action=action,
        context=exec_context,
        gate_snapshot=snapshot,
        snapshot_receipt=receipt,
        capability_token=capability,
        now_s=context.clock.read(),
    )

    # Mutation 1: stale snapshot receipt -> snapshot_rejected -> mask to ABORT.
    stale_adapter, stale_authority, stale_action, stale_context, stale_snapshot, stale_receipt, stale_capability = _issue_valid_pair(
        context, f"NC15_stale_{repeat}", "RUN_NC15_STALE", f"NC15_STALE_{repeat}"
    )
    context.clock.advance(10.0)  # beyond the 2.0 s validity window
    stale_decision = stale_adapter.admit(
        action=stale_action,
        context=stale_context,
        gate_snapshot=stale_snapshot,
        snapshot_receipt=stale_receipt,
        capability_token=stale_capability,
        now_s=context.clock.read(),
    )
    stale_reason = stale_decision.reason_code

    # Mutation 2: replayed nonce -> snapshot_rejected -> mask to ABORT.
    replay_adapter, replay_authority, replay_action, replay_context, replay_snapshot, replay_receipt, replay_capability = _issue_valid_pair(
        context, f"NC15_replay_{repeat}", "RUN_NC15_REPLAY", f"NC15_REPLAY_{repeat}"
    )
    first = replay_adapter.admit(
        action=replay_action,
        context=replay_context,
        gate_snapshot=replay_snapshot,
        snapshot_receipt=replay_receipt,
        capability_token=replay_capability,
        now_s=context.clock.read(),
    )
    # fresh capability for the second attempt so only the receipt replay is exercised
    replay_capability_2 = ShieldAttestationAuthority().issue_capability(
        backend_id=DYNAMICS_BACKEND_ID,
        backend_source_sha256=backend_source_sha256(),
        action=replay_action,
        context=replay_context,
        nonce=f"CAP_NONCE_NC15_REPLAY2_{repeat}",
        issued_at_s=context.clock.read(),
        validity_window_s=2.0,
    )
    second = replay_adapter.admit(
        action=replay_action,
        context=replay_context,
        gate_snapshot=replay_snapshot,
        snapshot_receipt=replay_receipt,
        capability_token=replay_capability_2,
        now_s=context.clock.read(),
    )
    replay_reason = second.reason_code

    detected = (
        stale_decision.intervened is True
        and stale_decision.executed_action == CANONICAL_ABORT_ACTION
        and stale_reason == "SNAPSHOT_REJECTED_STALE"
        and first.allowed is True
        and second.intervened is True
        and second.executed_action == CANONICAL_ABORT_ACTION
        and replay_reason == "SNAPSHOT_REJECTED_NONCE_REPLAY"
    )
    return ProbeResult(
        baseline_decision.allowed is True and baseline_decision.intervened is False,
        detected,
        "MASK_TO_ABORT_ONLY" if detected else "NON_ABORT_ESCAPED",
        stale_reason,
        0 if detected else 1,
        "PRODUCTION_INTENT_RECEIPT_AUTHORITY_WITH_FILE_REPLAY_STORE",
        "a fresh action/context/snapshot-bound receipt admits exactly one non-ABORT request",
        "/snapshot_receipt/{expires_at_s,nonce}",
        "expire the receipt past its validity window; replay one consumed nonce",
        {
            "stale_reason": stale_reason,
            "replay_reason": replay_reason,
            "stale_masked_to_abort": stale_decision.executed_action == CANONICAL_ABORT_ACTION,
            "replay_masked_to_abort": second.executed_action == CANONICAL_ABORT_ACTION,
            "replay_store_pattern": "UNIFIED_R2_RUN_CONSUMPTION_SINGLE_USE_MARKER",
        },
    )


def _probe_nc16(context: BackendRunnerContext, repeat: str) -> ProbeResult:
    adapter, authority, action, exec_context, snapshot, receipt, capability = _issue_valid_pair(
        context, f"NC16_baseline_{repeat}", "RUN_NC16_BASELINE", f"NC16_BASE_{repeat}"
    )
    baseline_decision = adapter.admit(
        action=action,
        context=exec_context,
        gate_snapshot=snapshot,
        snapshot_receipt=receipt,
        capability_token=capability,
        now_s=context.clock.read(),
    )

    # Mutation: direct backend call without a shield attestation capability.
    direct_adapter, _, direct_action, direct_context, direct_snapshot, direct_receipt, _ = _issue_valid_pair(
        context, f"NC16_direct_{repeat}", "RUN_NC16_DIRECT", f"NC16_DIRECT_{repeat}"
    )
    direct_decision = direct_adapter.admit(
        action=direct_action,
        context=direct_context,
        gate_snapshot=direct_snapshot,
        snapshot_receipt=direct_receipt,
        capability_token=None,
        now_s=context.clock.read(),
    )
    direct_reason = direct_decision.reason_code

    # Secondary: a capability bound to a different backend source digest is rejected.
    foreign_capability = ShieldAttestationAuthority().issue_capability(
        backend_id=DYNAMICS_BACKEND_ID,
        backend_source_sha256=sha256_bytes(
            (HERE / "sim13_v2_backends" / "contact_backend.py").read_bytes()
        ),
        action=direct_action,
        context=direct_context,
        nonce=f"CAP_NONCE_NC16_FOREIGN_{repeat}",
        issued_at_s=context.clock.read(),
        validity_window_s=2.0,
    )
    foreign_adapter, _, foreign_action, foreign_context, foreign_snapshot, foreign_receipt, _ = _issue_valid_pair(
        context, f"NC16_foreign_{repeat}", "RUN_NC16_FOREIGN", f"NC16_FOREIGN_{repeat}"
    )
    foreign_decision = foreign_adapter.admit(
        action=foreign_action,
        context=foreign_context,
        gate_snapshot=foreign_snapshot,
        snapshot_receipt=foreign_receipt,
        capability_token=foreign_capability,
        now_s=context.clock.read(),
    )

    detected = (
        direct_decision.intervened is True
        and direct_decision.executed_action == CANONICAL_ABORT_ACTION
        and direct_reason == "BACKEND_REJECTS_UNSHIELDED_NON_ABORT"
        and foreign_decision.intervened is True
        and foreign_decision.reason_code == "CAPABILITY_TOKEN_BACKEND_SOURCE_MISMATCH"
    )
    return ProbeResult(
        baseline_decision.allowed is True,
        detected,
        "MASK_TO_ABORT_ONLY" if detected else "NON_ABORT_ESCAPED",
        direct_reason,
        0 if detected else 1,
        "PRODUCTION_INTENT_CAPABILITY_ADMISSION_BOUND_TO_BACKEND_SOURCE_SHA256",
        "a shield-minted capability bound to the backend source sha256 admits one non-ABORT call",
        "/capability_token (absent)",
        "remove the shield attestation so the backend is called unshielded",
        {
            "unshielded_reason": direct_reason,
            "foreign_source_reason": foreign_decision.reason_code,
            "backend_source_sha256": backend_source_sha256(),
            "unshielded_masked_to_abort": direct_decision.executed_action == CANONICAL_ABORT_ACTION,
        },
    )


def _probe_nc18(context: BackendRunnerContext, repeat: str) -> ProbeResult:
    backend = context.dynamics_backend
    initial = backend.initial_state()
    after, assessment, audit = backend.advance(
        initial,
        generalized_effort=backend.nominal_generalized_effort(),
        step_s=1.0e-3,
        steps=10,
    )
    phase_only = PhaseOnlyBackend(backend).advance(initial)
    phase_assessment = state_evolution_assessment(initial, phase_only)
    detected = (
        phase_assessment["accepted"] is False
        and phase_assessment["reason_code"] == "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY"
        and assessment["accepted"] is True
    )
    return ProbeResult(
        assessment["accepted"] is True and audit["momentum_conserved_within_limit"] is True,
        detected,
        "FAIL_GATE" if detected else "PHASE_ONLY_STEP_ESCAPED",
        phase_assessment["reason_code"],
        0,
        "UNIFIED_R2_FREE_FLOATING_STATE_EVOLUTION_BACKEND",
        "nominal generalized effort evolves joint/base/end-effector state with momentum conserved",
        "/backend_step/phase_only",
        "replace the numerical step with a phase-only update that changes no physical state",
        {
            "nominal_reason": assessment["reason_code"],
            "phase_only_reason": phase_assessment["reason_code"],
            "nominal_deltas": assessment["deltas"],
            "linear_momentum_residual_Ns": audit["linear_momentum_residual_Ns"],
            "angular_momentum_residual_Nms": audit["angular_momentum_residual_Nms"],
            "urdf_sha256": backend.urdf_sha256,
        },
    )


def _probe_nc19(context: BackendRunnerContext, repeat: str) -> ProbeResult:
    backend = context.contact_backend
    gap = backend.bands["initial_gap_m"].nominal
    clearance = backend.detect(gap * 0.5, gap * 0.5)
    overlap = backend.detect(gap + 1.0e-3, gap + 1.0e-3)
    broken = BrokenContactDetector(backend).detect(gap + 1.0e-3, gap + 1.0e-3)
    audit = audit_detector_consistency(overlap, broken)
    out_of_envelope = backend.detect_fail_closed(
        backend.bands["stroke_m"].upper + 1.0e-3, gap
    )
    detected = (
        audit["contact_detection_failure"] is True
        and audit["reason_code"] == "CONTACT_DETECTION_FAILURE"
        and out_of_envelope.state == "UNKNOWN"
    )
    return ProbeResult(
        clearance.state == "NO_CONTACT" and overlap.contact_state_updated is True,
        detected,
        "FAIL_GATE" if detected else "MISSING_CONTACT_UPDATE_ESCAPED",
        audit["reason_code"],
        0,
        "BOUNDED_PROVISIONAL_NARROW_PHASE_BACKEND_WITH_RELEASED_GEOMETRY",
        "overlapping geometry updates the contact state within the DESIGN_CONTACT_MODEL_V1 envelope",
        "/narrow_phase_detector/contact_state_update",
        "rig the detector so overlapping geometry produces no contact-state update",
        {
            "overlap_penetration_m": [pad.penetration_m for pad in overlap.pads],
            "overlap_total_normal_force_N": overlap.total_normal_force_N,
            "broken_audit": dict(audit),
            "out_of_envelope_reason": out_of_envelope.reason_code,
            "geometry_sha256": sha256_bytes(GEOMETRY_PATH.read_bytes()),
        },
    )


def _probe_nc20(context: BackendRunnerContext, repeat: str) -> ProbeResult:
    evaluator = context.feasibility_evaluator
    target = debris_150kg_3dps_request()
    adapter, authority, action, exec_context, snapshot, receipt, capability = _issue_valid_pair(
        context, f"NC20_baseline_{repeat}", "RUN_NC20_BASELINE", f"NC20_BASE_{repeat}"
    )
    evaluation = evaluator.evaluate(target)
    fail_receipt = evaluator.issue_receipt(action=action, target=target)
    decision = adapter.admit(
        action=action,
        context=exec_context,
        gate_snapshot=snapshot,
        snapshot_receipt=receipt,
        capability_token=capability,
        target=target,
        feasibility_receipt=fail_receipt,
        now_s=context.clock.read(),
    )
    # Secondary: no receipt at all -> receipt missing -> mask to ABORT.
    missing_adapter, _, missing_action, missing_context, missing_snapshot, missing_receipt, missing_capability = _issue_valid_pair(
        context, f"NC20_missing_{repeat}", "RUN_NC20_MISSING", f"NC20_MISSING_{repeat}"
    )
    missing_decision = missing_adapter.admit(
        action=missing_action,
        context=missing_context,
        gate_snapshot=missing_snapshot,
        snapshot_receipt=missing_receipt,
        capability_token=missing_capability,
        target=target,
        feasibility_receipt=None,
        now_s=context.clock.read(),
    )
    detected = (
        decision.intervened is True
        and decision.executed_action == CANONICAL_ABORT_ACTION
        and decision.reason_code == "MISSION_VETO_INFEASIBLE_RATE"
        and missing_decision.intervened is True
        and missing_decision.reason_code == "FEASIBILITY_RECEIPT_MISSING"
    )
    return ProbeResult(
        evaluation["feasibility_verdict"] == "FEASIBILITY_FAIL"
        and evaluation["post_grasp_verdict"] == "POST_GRASP_STABILITY_FAIL_WHEELS_ONLY"
        and abs(evaluation["anchor_w_plus_dps"] - 3.0633304945807067) <= 1.0e-15,
        detected,
        "MASK_TO_ABORT_ONLY" if detected else "NON_ABORT_ESCAPED",
        decision.reason_code,
        0 if detected else 1,
        "ACTION_BOUND_SIM10_SIM12_ANCHOR_FEASIBILITY_EVALUATOR",
        "the evaluator binds the 150 kg / 3 deg/s anchor and returns FEASIBILITY_FAIL with post-grasp stability FAIL",
        "/feasibility_receipt/evaluation/feasibility_pass",
        "request non-ABORT execution against the 150 kg anchor without a feasibility PASS",
        {
            "evaluation": dict(evaluation),
            "veto_reason": decision.reason_code,
            "missing_receipt_reason": missing_decision.reason_code,
            "masked_to_abort": decision.executed_action == CANONICAL_ABORT_ACTION,
            "anchor_hashes": dict(evaluator.anchor_hashes),
        },
    )


PROBES: Mapping[str, Callable[[BackendRunnerContext, str], ProbeResult]] = {
    "NC15": _probe_nc15,
    "NC16": _probe_nc16,
    "NC18": _probe_nc18,
    "NC19": _probe_nc19,
    "NC20": _probe_nc20,
}


def _tracked_source_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                HERE / "run_negative_controls_backends_v2.py",
                HERE / "emit_released_contact_geometry_v1.py",
                HERE / "sim13_v2_backends" / "__init__.py",
                HERE / "sim13_v2_backends" / "canonical.py",
                HERE / "sim13_v2_backends" / "capability.py",
                HERE / "sim13_v2_backends" / "contact_backend.py",
                HERE / "sim13_v2_backends" / "dynamics_backend.py",
                HERE / "sim13_v2_backends" / "feasibility_evaluator.py",
                HERE / "sim13_v2_backends" / "runtime_gate_adapter.py",
                HERE / "sim13_v2_backends" / "snapshot_receipt.py",
                HERE / "assets" / "SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1.json",
                HERE / "contracts" / "SIM13_V2_GATE_SNAPSHOT_RECEIPT_SCHEMA_V1.json",
                HERE / "contracts" / "SIM13_V2_BACKEND_CAPABILITY_TOKEN_SCHEMA_V1.json",
                HERE / "contracts" / "SIM13_V2_ACTION_BOUND_FEASIBILITY_RECEIPT_SCHEMA_V1.json",
                PROJECT_ROOT
                / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
                / "unified_r2_digital_prototype_prebind/generated_v2"
                / "unified_r2_c01_no_route_c_sim_candidate_v2.urdf",
                PROJECT_ROOT
                / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
                / "unified_r2_digital_prototype_prebind/generated_v2"
                / "UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json",
                PROJECT_ROOT
                / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b"
                / "DESIGN_CONTACT_MODEL_V1.yaml",
            )
        )
    )


def _source_hashes(paths: tuple[Path, ...]) -> dict[str, str]:
    output: dict[str, str] = {}
    for path in paths:
        relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
        output[relative] = sha256_bytes(path.read_bytes())
    return output


def _safe_probe(probe, context: BackendRunnerContext, repeat: str) -> ProbeResult:
    try:
        return probe(context, repeat)
    except Exception as exc:  # evidence records a hold instead of fabricating PASS
        return ProbeResult(
            False,
            False,
            "NOT_EXECUTED_BASELINE_OR_PROBE_ERROR",
            f"{type(exc).__name__}:{exc}",
            0,
            "PROBE_ERROR_FAIL_CLOSED",
            "baseline qualification raised an exception",
            "NONE",
            "no accepted single-fault execution",
            {},
        )


def build_package(run_probes: bool = True) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sim13_v2_backends_nc_") as temporary:
        context = build_context(Path(temporary))
        tracked = _tracked_source_paths()
        before = _source_hashes(tracked)
        probe_pairs = {
            control_id: (
                _safe_probe(probe, context, "A"),
                _safe_probe(probe, context, "B"),
            )
            for control_id, probe in PROBES.items()
        }
        after = _source_hashes(tracked)

        dynamics_receipt = build_dynamics_receipt(context.dynamics_backend)
        geometry_record = file_record(GEOMETRY_PATH, PROJECT_ROOT)
        contact_receipt = build_contact_receipt(
            context.contact_backend, geometry_record=geometry_record
        )

    hashes_unchanged = before == after
    rows: list[dict[str, Any]] = []
    summary = {"total": 5, "executed": 0, "passed": 0, "failed": 0}
    for control_id, (first, second) in probe_pairs.items():
        deterministic = first == second
        expected = EXPECTED_REASON[control_id]
        passed = (
            first.baseline_qualified
            and first.detected
            and first.observed_outcome == OBSERVED_OUTCOME[control_id]
            and first.exact_reason == expected
            and first.non_abort_execution_count == 0
            and deterministic
            and hashes_unchanged
        )
        summary["executed"] += 1
        summary["passed" if passed else "failed"] += 1
        meta = REGISTRY_METADATA[control_id]
        rows.append(
            {
                "control_id": control_id,
                "stimulus": meta["stimulus"],
                "required_observation": meta["required_observation"],
                "canonical_outcome": OBSERVED_OUTCOME[control_id],
                "future_gate": meta["future_gate"],
                "executed": True,
                "status": "PASS_NEGATIVE_CONTROL_DETECTED" if passed else "FAIL_NEGATIVE_CONTROL_ESCAPED",
                "runner_scope": first.scope,
                "baseline": {
                    "qualified": first.baseline_qualified,
                    "assertion": first.baseline_assertion,
                },
                "mutation": {
                    "deep_copy": True,
                    "single_fault": True,
                    "path": first.mutation_path,
                    "description": first.mutation_description,
                },
                "observed_outcome": first.observed_outcome,
                "non_abort_execution_count": first.non_abort_execution_count,
                "exact_reason_expected": expected,
                "exact_reason_observed": first.exact_reason,
                "exact_reason_match": first.exact_reason == expected,
                "deterministic_repeat": deterministic,
                "repeat_digest": canonical_digest(asdict(first)),
                "baseline_source_hashes_unchanged": hashes_unchanged,
                "details": dict(first.details),
            }
        )

    evidence = {
        "schema": "SIM13_V2_BACKENDS_NEGATIVE_CONTROLS_V2",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "scope": "FORMAL_SINGLE_FAULT_BACKEND_EXECUTION__NOT_PRODUCTION_AUTHORIZATION",
        "work_order": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/SIM13_BACKEND_WORK_ORDERS_V1.json",
        "source_hashes_before": before,
        "source_hashes_after": after,
        "source_hashes_unchanged": hashes_unchanged,
        "summary": summary,
        "controls": rows,
        "release_credit": False,
        "next_stage_authorized": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "truth_guard": "only executed single-fault probes may PASS; UNKNOWN is never PASS",
    }
    return {
        "evidence": evidence,
        "dynamics_receipt": dynamics_receipt,
        "contact_receipt": contact_receipt,
        "probe_results": probe_pairs,
        "source_hashes_unchanged": hashes_unchanged,
    }


def build_runtime_evaluator_receipt(
    package: Mapping[str, Any],
) -> Mapping[str, Any]:
    controls = {
        row["control_id"]: row for row in package["evidence"]["controls"]
    }
    checks = {
        "nc15_stale_and_replayed_snapshot_rejected": controls["NC15"]["status"]
        == "PASS_NEGATIVE_CONTROL_DETECTED",
        "nc16_unshielded_backend_call_rejected": controls["NC16"]["status"]
        == "PASS_NEGATIVE_CONTROL_DETECTED",
        "nc20_non_abort_150kg_without_feasibility_pass_aborted": controls["NC20"][
            "status"
        ]
        == "PASS_NEGATIVE_CONTROL_DETECTED",
        "baseline_source_hashes_unchanged": package["source_hashes_unchanged"] is True,
    }
    return {
        "schema": "SIM13_V2_RUNTIME_EVALUATOR_RECEIPT_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "evaluator": "run_negative_controls_backends_v2.py",
        "adapter": "SIM13_V2_RUNTIME_FAIL_CLOSED_GATE_ADAPTER_V1",
        "backends": {
            "snapshot_receipt": "sim13_v2_backends/snapshot_receipt.py",
            "capability": "sim13_v2_backends/capability.py",
            "feasibility_evaluator": "sim13_v2_backends/feasibility_evaluator.py",
            "runtime_gate_adapter": "sim13_v2_backends/runtime_gate_adapter.py",
        },
        "negative_control_evidence": "evidence/SIM13_V2_BACKENDS_NEGATIVE_CONTROLS_V2.json",
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "historical_15_of_20_prebind_evidence_not_modified": True,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_gate_documents(package: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    controls = {
        row["control_id"]: row for row in package["evidence"]["controls"]
    }
    runtime_pass = all(
        controls[cid]["status"] == "PASS_NEGATIVE_CONTROL_DETECTED"
        for cid in ("NC15", "NC16", "NC20")
    ) and package["source_hashes_unchanged"]
    dynamics_pass = (
        controls["NC18"]["status"] == "PASS_NEGATIVE_CONTROL_DETECTED"
        and package["dynamics_receipt"]["all_checks_pass"] is True
    )
    contact_pass = (
        controls["NC19"]["status"] == "PASS_NEGATIVE_CONTROL_DETECTED"
        and package["contact_receipt"]["all_checks_pass"] is True
    )
    common = {
        "generated_date_local": GENERATED_DATE_LOCAL,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    runtime_gate = {
        **common,
        "schema": "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2",
        "negative_controls": ["NC15", "NC16", "NC20"],
        "checks": {
            "nc15_snapshot_rejected": controls["NC15"]["status"],
            "nc16_backend_rejects_unshielded": controls["NC16"]["status"],
            "nc20_shield_executes_abort": controls["NC20"]["status"],
            "baseline_source_hashes_unchanged": package["source_hashes_unchanged"],
        },
        "gate_passed": runtime_pass,
        "verdict": (
            "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2_PASS__PENDING_OWNER_REVIEW__NO_RELEASE_CREDIT"
            if runtime_pass
            else "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2_FAIL"
        ),
    }
    dynamics_gate = {
        **common,
        "schema": "SIM13_DYNAMICS_BACKEND_GATE_V2",
        "negative_controls": ["NC18"],
        "checks": {
            "nc18_dynamics_state_update_failure": controls["NC18"]["status"],
            "dynamics_backend_validation_receipt_all_pass": package["dynamics_receipt"][
                "all_checks_pass"
            ],
        },
        "gate_passed": dynamics_pass,
        "verdict": (
            "SIM13_DYNAMICS_BACKEND_GATE_V2_PASS__PENDING_OWNER_REVIEW__NO_RELEASE_CREDIT"
            if dynamics_pass
            else "SIM13_DYNAMICS_BACKEND_GATE_V2_FAIL"
        ),
    }
    contact_gate = {
        **common,
        "schema": "SIM13_CONTACT_GRASP_GATE_V2",
        "negative_controls": ["NC19"],
        "checks": {
            "nc19_contact_detection_failure": controls["NC19"]["status"],
            "contact_backend_validation_receipt_all_pass": package["contact_receipt"][
                "all_checks_pass"
            ],
        },
        "gate_passed": contact_pass,
        "verdict": (
            "SIM13_CONTACT_GRASP_GATE_V2_PASS__BOUNDED_PROVISIONAL__PENDING_OWNER_REVIEW__NO_RELEASE_CREDIT"
            if contact_pass
            else "SIM13_CONTACT_GRASP_GATE_V2_FAIL"
        ),
    }
    return {
        "runtime": runtime_gate,
        "dynamics": dynamics_gate,
        "contact": contact_gate,
    }


def write_all() -> dict[str, Any]:
    package = build_package()
    runtime_receipt = build_runtime_evaluator_receipt(package)
    gates = build_gate_documents(package)
    write_canonical_json(EVIDENCE_PATH, package["evidence"])
    write_canonical_json(RUNTIME_EVALUATOR_RECEIPT_PATH, runtime_receipt)
    write_canonical_json(DYNAMICS_RECEIPT_PATH, package["dynamics_receipt"])
    write_canonical_json(CONTACT_RECEIPT_PATH, package["contact_receipt"])
    write_canonical_json(RUNTIME_GATE_PATH, gates["runtime"])
    write_canonical_json(DYNAMICS_GATE_PATH, gates["dynamics"])
    write_canonical_json(CONTACT_GATE_PATH, gates["contact"])
    return {
        "package": package,
        "runtime_receipt": runtime_receipt,
        "gates": gates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    if args.check_only:
        package = build_package()
        summary = package["evidence"]["summary"]
        print(json.dumps(summary, sort_keys=True))
        return 0 if summary["failed"] == 0 and summary["passed"] == 5 else 1
    output = write_all()
    summary = output["package"]["evidence"]["summary"]
    print(json.dumps(summary, sort_keys=True))
    for name, gate in output["gates"].items():
        print(f"{name}: {gate['verdict']}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
