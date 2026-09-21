"""Conservative bootstrap reward contract.

These terms only test environment wiring; they are not a trained-policy result
or a scientific claim about grasp optimality.
"""
from __future__ import annotations

from dataclasses import dataclass

from .safety_shield import ShieldResult


@dataclass(frozen=True)
class RewardBreakdown:
    total: float
    alive: float
    abort: float
    shield_intervention: float
    collision: float


class BootstrapReward:
    def evaluate(self, shield: ShieldResult, collision_detected: bool) -> RewardBreakdown:
        alive = 0.01
        abort = -1.0 if shield.executed_action.is_abort else 0.0
        intervention = -1.0 if shield.intervened else 0.0
        collision = -100.0 if collision_detected else 0.0
        return RewardBreakdown(
            total=alive + abort + intervention + collision,
            alive=alive,
            abort=abort,
            shield_intervention=intervention,
            collision=collision,
        )


__all__ = ["BootstrapReward", "RewardBreakdown"]
