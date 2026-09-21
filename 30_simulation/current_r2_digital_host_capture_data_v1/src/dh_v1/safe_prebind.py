"""Fail-closed prebind safety decision kernel (S07).

This is the PREBIND adapter of the SAFE philosophy for this increment only.
It does NOT replace safety_00_runtime_gate (SAFE-00) and carries no release
credit. Mapping contract (frozen for this increment):

    any REQUIRED item MISSING / UNKNOWN / MISMATCH        -> ABORT
    any REQUIRED item NOT_EVALUATED                       -> ABORT
    stale measurement within wait budget                  -> WAIT
    stale measurement beyond wait budget                  -> ABORT
    everything VERIFIED (or PROVISIONAL where allowed)    -> the scenario's
        requested action, capped at MODIFY when any PROVISIONAL is present.

EXECUTE can never be produced from UNKNOWN/NOT_EVALUATED/MISSING inputs, and
NOT_EVALUATED never converts into an ordinary negative label.
"""
from __future__ import annotations

from dataclasses import dataclass, field

VALID_STATUS = {"VERIFIED", "PROVISIONAL", "UNKNOWN", "NOT_EVALUATED", "MISSING", "MISMATCH", "STALE"}
DECISIONS = ("EXECUTE", "MODIFY", "ABORT", "WAIT")


class SafeContractViolation(RuntimeError):
    pass


@dataclass
class AuthorityItem:
    name: str
    status: str
    required: bool = True
    provisional_allowed: bool = False
    stale_age_s: float | None = None  # only meaningful with status == "STALE"

    def __post_init__(self):
        if self.status not in VALID_STATUS:
            raise SafeContractViolation(f"invalid status {self.status!r} for {self.name}")


@dataclass
class SafeDecision:
    decision: str
    reasons: list = field(default_factory=list)
    blocking_items: list = field(default_factory=list)
    requested_action: str = "EXECUTE"

    def as_dict(self) -> dict:
        return {
            "decision": self.decision,
            "requested_action": self.requested_action,
            "reasons": list(self.reasons),
            "blocking_items": list(self.blocking_items),
            "fail_closed": True,
        }


def decide(items: list[AuthorityItem], requested_action: str = "EXECUTE",
           stale_wait_budget_s: float = 2.0) -> SafeDecision:
    if requested_action not in ("EXECUTE", "MODIFY"):
        raise SafeContractViolation(f"requested_action must be EXECUTE or MODIFY, got {requested_action!r}")
    reasons: list[str] = []
    blocking: list[str] = []
    wait_needed = False
    provisional_present = False

    for it in items:
        if not it.required:
            continue
        if it.status in ("MISSING", "UNKNOWN", "MISMATCH", "NOT_EVALUATED"):
            blocking.append(it.name)
            reasons.append(f"{it.name}={it.status} -> fail-closed ABORT")
        elif it.status == "STALE":
            age = it.stale_age_s if it.stale_age_s is not None else float("inf")
            if age <= stale_wait_budget_s:
                wait_needed = True
                reasons.append(f"{it.name} stale {age:.3f}s <= budget {stale_wait_budget_s}s -> WAIT")
            else:
                blocking.append(it.name)
                reasons.append(f"{it.name} stale {age:.3f}s > budget {stale_wait_budget_s}s -> ABORT")
        elif it.status == "PROVISIONAL":
            if it.provisional_allowed:
                provisional_present = True
                reasons.append(f"{it.name}=PROVISIONAL accepted for this scenario, action capped at MODIFY")
            else:
                blocking.append(it.name)
                reasons.append(f"{it.name}=PROVISIONAL not admissible here -> ABORT")
        elif it.status == "VERIFIED":
            pass

    if blocking:
        return SafeDecision("ABORT", reasons, blocking, requested_action)
    if wait_needed:
        return SafeDecision("WAIT", reasons, [], requested_action)
    if provisional_present and requested_action == "EXECUTE":
        return SafeDecision("MODIFY", reasons, [], requested_action)
    return SafeDecision(requested_action, reasons, [], requested_action)


def label_from_decision(decision: str, evaluated: bool) -> str:
    """Dataset label taxonomy guard: NOT_EVALUATED is its own label and is
    never mapped onto the ordinary negative class."""
    if not evaluated:
        return "NOT_EVALUATED"
    if decision not in DECISIONS:
        raise SafeContractViolation(f"unknown decision {decision!r}")
    return decision
