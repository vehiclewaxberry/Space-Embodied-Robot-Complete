"""Runtime fail-closed admission path for Sim13 V2 (NC15/NC16/NC20 join).

This adapter is the single high-level runtime path over the three
SIM13_RUNTIME_FAIL_CLOSED_GATE_V2 backends:

1. WO-NC15 -- every non-ABORT request must carry a fresh, single-use,
   action/context/snapshot-bound receipt; stale or replayed snapshots are
   rejected (``snapshot_rejected``) and the request is masked to ABORT.
2. WO-NC16 -- the dynamics backend may only be reached through a capability
   token minted by the shield and bound to the backend source SHA-256; a
   direct unshielded call is rejected
   (``backend_rejects_unshielded_non_abort``) and masked to ABORT.
3. WO-NC20 -- a non-ABORT request against the 150 kg / 3 deg/s debris anchor
   must carry a feasibility-PASS receipt from the action-bound evaluator;
   without one the shield executes the canonical ABORT
   (``shield_executes_abort`` / ``MISSION_VETO_INFEASIBLE_RATE``).

UNKNOWN is never PASS anywhere in this path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .capability import CapabilityToken, ShieldedBackendAdmission
from .feasibility_evaluator import (
    ActionBoundFeasibilityEvaluator,
    FeasibilityReceipt,
    TargetRequest,
    debris_150kg_3dps_request,
)
from .snapshot_receipt import (
    FileReplayStore,
    SnapshotReceipt,
    SnapshotReceiptAuthority,
)


ADAPTER_ID = "SIM13_V2_RUNTIME_FAIL_CLOSED_GATE_ADAPTER_V1"
CANONICAL_ABORT_ACTION = {
    "grasp_candidate_id": "__ABORT__",
    "capture_timing_id": "__ABORT__",
    "strategy_id": "ABORT",
}


@dataclass(frozen=True)
class AdapterDecision:
    allowed: bool
    requested_action: Mapping[str, Any]
    executed_action: Mapping[str, Any]
    intervened: bool
    reason_code: str
    receipt_nonce: str | None = None
    capability_nonce: str | None = None


def _abort(decision_action: Mapping[str, Any], reason: str) -> AdapterDecision:
    return AdapterDecision(
        False, decision_action, CANONICAL_ABORT_ACTION, True, reason
    )


class RuntimeGateAdapter:
    """Single admission path joining receipt, capability, and feasibility."""

    def __init__(
        self,
        *,
        receipt_authority: SnapshotReceiptAuthority,
        backend_admission: ShieldedBackendAdmission,
        feasibility_evaluator: ActionBoundFeasibilityEvaluator,
        receipt_replay_store: FileReplayStore,
        capability_replay_store: FileReplayStore,
    ) -> None:
        self.receipt_authority = receipt_authority
        self.backend_admission = backend_admission
        self.feasibility_evaluator = feasibility_evaluator
        self.receipt_replay_store = receipt_replay_store
        self.capability_replay_store = capability_replay_store

    def admit(
        self,
        *,
        action: Mapping[str, Any],
        context: Mapping[str, Any],
        gate_snapshot: Mapping[str, Any],
        snapshot_receipt: SnapshotReceipt | None,
        capability_token: CapabilityToken | None,
        target: TargetRequest | None = None,
        feasibility_receipt: FeasibilityReceipt | None = None,
        now_s: float,
    ) -> AdapterDecision:
        if action.get("strategy_id") == "ABORT":
            return AdapterDecision(
                True, action, action, False, "ABORT_ALWAYS_AVAILABLE"
            )

        receipt_admission = self.receipt_authority.verify_and_consume(
            receipt=snapshot_receipt,
            action=action,
            context=context,
            gate_snapshot=gate_snapshot,
            replay_store=self.receipt_replay_store,
        )
        if not receipt_admission.allowed:
            return _abort(action, receipt_admission.reason_code)

        capability_admission = self.backend_admission.admit(
            token=capability_token,
            action=action,
            context=context,
            now_s=now_s,
            replay_store=self.capability_replay_store,
        )
        if not capability_admission.allowed:
            return _abort(action, capability_admission.reason_code)

        if target is not None and target == debris_150kg_3dps_request():
            feasibility_admission = self.feasibility_evaluator.verify_receipt(
                receipt=feasibility_receipt,
                action=action,
                target=target,
            )
            if not feasibility_admission.allowed:
                return _abort(action, feasibility_admission.reason_code)

        return AdapterDecision(
            True,
            action,
            action,
            False,
            "RUNTIME_FAIL_CLOSED_ADMISSION_PASS",
            receipt_admission.consumed_nonce,
            capability_admission.consumed_nonce,
        )


__all__ = [
    "ADAPTER_ID",
    "AdapterDecision",
    "CANONICAL_ABORT_ACTION",
    "RuntimeGateAdapter",
]
