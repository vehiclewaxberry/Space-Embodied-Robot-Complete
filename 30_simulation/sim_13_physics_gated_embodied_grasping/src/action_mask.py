"""Fail-closed high-level action masking."""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Mapping

from .action_space import DiscreteActionSpace, HighLevelAction


class GateState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SafetyGateSnapshot:
    ik_reachable: GateState = GateState.UNKNOWN
    external_collision_clear: GateState = GateState.UNKNOWN
    keep_out_clear: GateState = GateState.UNKNOWN
    sim10_gate: GateState = GateState.UNKNOWN
    safe00_state: GateState = GateState.UNKNOWN
    post_grasp_stability_gate: GateState = GateState.UNKNOWN
    gripper_configuration_accepted: GateState = GateState.UNKNOWN
    target_surface_normal_valid: GateState = GateState.UNKNOWN

    @classmethod
    def all_pass(cls) -> "SafetyGateSnapshot":
        return cls(**{item.name: GateState.PASS for item in fields(cls)})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SafetyGateSnapshot":
        expected = {item.name for item in fields(cls)}
        if set(value) != expected:
            raise ValueError(f"gate snapshot keys must be exactly {sorted(expected)}")
        try:
            return cls(**{key: GateState(raw) for key, raw in value.items()})
        except ValueError as exc:
            raise ValueError("gate state must be PASS, FAIL or UNKNOWN") from exc

    def reason_codes(self) -> tuple[str, ...]:
        reasons: list[str] = []
        for item in fields(self):
            state = getattr(self, item.name)
            if state is GateState.FAIL:
                reasons.append(f"{item.name.upper()}_FAIL")
            elif state is GateState.UNKNOWN:
                reasons.append(f"{item.name.upper()}_UNKNOWN")
        return tuple(reasons)


@dataclass(frozen=True)
class MaskDecision:
    allowed: bool
    reason_codes: tuple[str, ...]


class ActionMasker:
    """Masks every non-ABORT action unless every required fact is PASS."""

    def evaluate(
        self,
        action_space: DiscreteActionSpace,
        gates: SafetyGateSnapshot,
    ) -> Mapping[HighLevelAction, MaskDecision]:
        reasons = gates.reason_codes()
        return {
            action: (
                MaskDecision(True, ("ABORT_ALWAYS_AVAILABLE",))
                if action.is_abort
                else MaskDecision(not reasons, ("ALL_REQUIRED_GATES_PASS",) if not reasons else reasons)
            )
            for action in action_space.actions
        }

    def decision_for(
        self,
        action: HighLevelAction,
        action_space: DiscreteActionSpace,
        gates: SafetyGateSnapshot,
    ) -> MaskDecision:
        if not action_space.contains(action):
            return MaskDecision(False, ("ACTION_OUTSIDE_DISCRETE_SPACE",))
        return self.evaluate(action_space, gates)[action]


__all__ = ["ActionMasker", "GateState", "MaskDecision", "SafetyGateSnapshot"]
