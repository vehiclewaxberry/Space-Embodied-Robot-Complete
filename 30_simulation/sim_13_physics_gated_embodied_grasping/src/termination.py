"""Episode termination rules for the sim_13 bootstrap."""
from __future__ import annotations

from dataclasses import dataclass

from .physics_backend import BackendState
from .safety_shield import ShieldResult


@dataclass(frozen=True)
class TerminationDecision:
    terminated: bool
    truncated: bool
    reason: str | None


class BootstrapTermination:
    def __init__(self, maximum_steps: int = 1000) -> None:
        if maximum_steps <= 0:
            raise ValueError("maximum_steps must be positive")
        self.maximum_steps = maximum_steps

    def evaluate(
        self,
        state: BackendState,
        shield: ShieldResult,
        step_count: int,
    ) -> TerminationDecision:
        if state.collision_detected:
            return TerminationDecision(True, False, "COLLISION")
        if shield.executed_action.is_abort:
            return TerminationDecision(True, False, "ABORT")
        if step_count >= self.maximum_steps:
            return TerminationDecision(False, True, "STEP_LIMIT")
        return TerminationDecision(False, False, None)


__all__ = ["BootstrapTermination", "TerminationDecision"]
