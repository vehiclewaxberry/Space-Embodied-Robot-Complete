"""High-level discrete action contract for sim_13.

No action in this module contains joint torques.  Joint-space execution remains
the responsibility of deterministic IK, velocity limiting and the safety shield.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class StrategyId(str, Enum):
    S1 = "S1"
    S3A = "S3a"
    ABORT = "ABORT"


@dataclass(frozen=True, order=True)
class HighLevelAction:
    grasp_candidate_id: str
    capture_timing_id: str
    strategy_id: str

    def __post_init__(self) -> None:
        if self.strategy_id not in {item.value for item in StrategyId}:
            raise ValueError(f"unsupported strategy_id: {self.strategy_id}")
        if not self.grasp_candidate_id or not self.capture_timing_id:
            raise ValueError("action identifiers must be non-empty")
        if self.strategy_id == StrategyId.ABORT.value and (
            self.grasp_candidate_id != "__ABORT__"
            or self.capture_timing_id != "__ABORT__"
        ):
            raise ValueError("ABORT must use the canonical ABORT identifiers")

    @property
    def is_abort(self) -> bool:
        return self.strategy_id == StrategyId.ABORT.value

    def as_dict(self) -> dict[str, str]:
        return {
            "grasp_candidate_id": self.grasp_candidate_id,
            "capture_timing_id": self.capture_timing_id,
            "strategy_id": self.strategy_id,
        }

    @classmethod
    def abort(cls) -> "HighLevelAction":
        return cls("__ABORT__", "__ABORT__", StrategyId.ABORT.value)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HighLevelAction":
        forbidden = {"joint_torque", "joint_torques", "tau", "torque"} & set(value)
        if forbidden:
            raise ValueError(f"direct joint torque actions are forbidden: {sorted(forbidden)}")
        required = {"grasp_candidate_id", "capture_timing_id", "strategy_id"}
        if set(value) != required:
            raise ValueError(f"action keys must be exactly {sorted(required)}")
        return cls(*(str(value[key]) for key in (
            "grasp_candidate_id", "capture_timing_id", "strategy_id"
        )))


def _unique_ids(values: Iterable[str], label: str) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label} values must be non-empty strings")
        if value == "__ABORT__":
            raise ValueError(f"{label} may not use the reserved __ABORT__ identifier")
        if value in result:
            raise ValueError(f"duplicate {label}: {value}")
        result.append(value)
    if not result:
        raise ValueError(f"{label} must not be empty")
    return tuple(result)


class DiscreteActionSpace:
    """Cartesian high-level action grid plus one canonical ABORT action."""

    def __init__(
        self,
        grasp_candidate_ids: Iterable[str],
        capture_timing_ids: Iterable[str],
    ) -> None:
        self.grasp_candidate_ids = _unique_ids(grasp_candidate_ids, "grasp_candidate_id")
        self.capture_timing_ids = _unique_ids(capture_timing_ids, "capture_timing_id")
        actions = [
            HighLevelAction(candidate, timing, strategy.value)
            for candidate in self.grasp_candidate_ids
            for timing in self.capture_timing_ids
            for strategy in (StrategyId.S1, StrategyId.S3A)
        ]
        actions.append(HighLevelAction.abort())
        self.actions = tuple(actions)
        self._action_set = frozenset(actions)

    def __len__(self) -> int:
        return len(self.actions)

    def contains(self, action: HighLevelAction) -> bool:
        return action in self._action_set

    def parse(self, value: HighLevelAction | Mapping[str, Any]) -> HighLevelAction:
        action = value if isinstance(value, HighLevelAction) else HighLevelAction.from_mapping(value)
        if action not in self._action_set:
            raise ValueError(f"action is outside this scene's discrete space: {action}")
        return action


__all__ = ["DiscreteActionSpace", "HighLevelAction", "StrategyId"]
