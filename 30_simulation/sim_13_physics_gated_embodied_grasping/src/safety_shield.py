"""Last-line safety shield for high-level sim_13 actions."""
from __future__ import annotations

from dataclasses import dataclass

from .action_mask import ActionMasker, SafetyGateSnapshot
from .action_space import DiscreteActionSpace, HighLevelAction


@dataclass(frozen=True)
class ShieldResult:
    requested_action: HighLevelAction
    executed_action: HighLevelAction
    intervened: bool
    reason_codes: tuple[str, ...]


class SafetyShield:
    def __init__(self, masker: ActionMasker | None = None) -> None:
        self.masker = masker or ActionMasker()

    def enforce(
        self,
        requested_action: HighLevelAction,
        action_space: DiscreteActionSpace,
        gates: SafetyGateSnapshot,
    ) -> ShieldResult:
        decision = self.masker.decision_for(requested_action, action_space, gates)
        if decision.allowed:
            return ShieldResult(
                requested_action=requested_action,
                executed_action=requested_action,
                intervened=False,
                reason_codes=decision.reason_codes,
            )
        return ShieldResult(
            requested_action=requested_action,
            executed_action=HighLevelAction.abort(),
            intervened=True,
            reason_codes=("SHIELD_ABORT", *decision.reason_codes),
        )


__all__ = ["SafetyShield", "ShieldResult"]
