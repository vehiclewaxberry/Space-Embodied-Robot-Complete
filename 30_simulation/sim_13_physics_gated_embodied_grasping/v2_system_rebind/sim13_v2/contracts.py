"""Fail-closed Sim13 V2 runtime contracts.

The public environment surface never accepts gate values.  Gate snapshots can
only be minted by :mod:`authority_resolver` after verifying pinned repository
artifacts.  This module deliberately contains no convenience constructor for a
caller-provided PASS snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Iterator, Mapping


class GateState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


INHERITED_V1_GATES = (
    "ik_reachable",
    "external_collision_clear",
    "keep_out_clear",
    "sim10_gate",
    "safe00_state",
    "post_grasp_stability_gate",
    "gripper_configuration_accepted",
    "target_surface_normal_valid",
)
MECHANICAL_V2_GATES = (
    "mechanical_system_binding",
    "harness_rated_envelope",
    "contact_physics_ready",
    "route_c_scope_disposition",
)
REQUIRED_GATES = INHERITED_V1_GATES + MECHANICAL_V2_GATES


@dataclass(frozen=True)
class GateEvidence:
    state: GateState
    source_artifact: str | None
    source_field: str | None
    reason_code: str


_SNAPSHOT_FACTORY_TOKEN = object()


class GateSnapshot:
    """Immutable 12-gate snapshot produced only by the authority resolver."""

    __slots__ = ("_evidence",)

    def __init__(
        self,
        evidence: Mapping[str, GateEvidence],
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _SNAPSHOT_FACTORY_TOKEN:
            raise TypeError("GateSnapshot is authority-resolver constructed")
        if set(evidence) != set(REQUIRED_GATES):
            raise ValueError("authority snapshot must contain exactly the 12 required gates")
        ordered = {name: evidence[name] for name in REQUIRED_GATES}
        if any(not isinstance(item, GateEvidence) for item in ordered.values()):
            raise TypeError("every gate entry must be GateEvidence")
        self._evidence = MappingProxyType(ordered)

    def __iter__(self) -> Iterator[str]:
        return iter(REQUIRED_GATES)

    def __len__(self) -> int:
        return len(REQUIRED_GATES)

    def evidence(self, gate_name: str) -> GateEvidence:
        return self._evidence[gate_name]

    def state(self, gate_name: str) -> GateState:
        return self.evidence(gate_name).state

    @property
    def permits_non_abort(self) -> bool:
        return all(item.state is GateState.PASS for item in self._evidence.values())

    @property
    def blocking_reason_codes(self) -> tuple[str, ...]:
        return tuple(
            item.reason_code
            for item in self._evidence.values()
            if item.state is not GateState.PASS
        )

    def as_dict(self) -> dict[str, str]:
        return {name: self._evidence[name].state.value for name in REQUIRED_GATES}


def _authority_snapshot(evidence: Mapping[str, GateEvidence]) -> GateSnapshot:
    """Private minting hook used by the fixed-path authority resolver."""

    return GateSnapshot(evidence, _factory_token=_SNAPSHOT_FACTORY_TOKEN)


class StrategyId(str, Enum):
    S1 = "S1"
    S3A = "S3a"
    ABORT = "ABORT"


@dataclass(frozen=True)
class HighLevelAction:
    grasp_candidate_id: str
    capture_timing_id: str
    strategy_id: str

    def __post_init__(self) -> None:
        if self.strategy_id not in {item.value for item in StrategyId}:
            raise ValueError(f"unsupported strategy_id: {self.strategy_id}")
        if not self.grasp_candidate_id or not self.capture_timing_id:
            raise ValueError("candidate and timing identifiers must be non-empty")
        canonical_abort = (
            self.grasp_candidate_id == "__ABORT__"
            and self.capture_timing_id == "__ABORT__"
        )
        if (self.strategy_id == StrategyId.ABORT.value) != canonical_abort:
            raise ValueError("ABORT must use only the canonical ABORT identifiers")

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


_ACTION_FIELDS = frozenset(
    {"grasp_candidate_id", "capture_timing_id", "strategy_id"}
)
_LOW_LEVEL_ACTION_TOKENS = frozenset(
    {
        "torque",
        "torques",
        "tau",
        "joint_torque",
        "joint_torques",
        "position",
        "positions",
        "joint_position",
        "joint_positions",
        "velocity",
        "velocities",
        "joint_velocity",
        "joint_velocities",
        "trajectory",
        "joint_trajectory",
    }
)


def parse_action(value: HighLevelAction | Mapping[str, Any]) -> HighLevelAction:
    """Parse the exact high-level candidate/timing/strategy action contract."""

    if isinstance(value, HighLevelAction):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("action must be a HighLevelAction or mapping")
    keys = set(value)
    forbidden = sorted(keys & _LOW_LEVEL_ACTION_TOKENS)
    if forbidden:
        raise ValueError(f"low-level actuation fields are forbidden: {forbidden}")
    if keys != _ACTION_FIELDS:
        extras = sorted(keys - _ACTION_FIELDS)
        missing = sorted(_ACTION_FIELDS - keys)
        raise ValueError(
            f"action keys must be exactly {sorted(_ACTION_FIELDS)}; "
            f"extra={extras}, missing={missing}"
        )
    if any(not isinstance(value[name], str) for name in _ACTION_FIELDS):
        raise TypeError("all action identifiers must be strings")
    return HighLevelAction(
        grasp_candidate_id=value["grasp_candidate_id"],
        capture_timing_id=value["capture_timing_id"],
        strategy_id=value["strategy_id"],
    )


@dataclass(frozen=True)
class MaskDecision:
    allowed: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ShieldDecision:
    requested_action: HighLevelAction
    executed_action: HighLevelAction
    intervened: bool
    reason_codes: tuple[str, ...]


def decision_for(action: HighLevelAction, snapshot: GateSnapshot) -> MaskDecision:
    if action.is_abort:
        return MaskDecision(True, ("ABORT_ALWAYS_AVAILABLE",))
    if snapshot.permits_non_abort:
        return MaskDecision(True, ("TWELVE_HASH_BOUND_GATES_PASS",))
    return MaskDecision(False, snapshot.blocking_reason_codes)


def enforce_fail_closed(
    action: HighLevelAction,
    snapshot: GateSnapshot,
) -> ShieldDecision:
    decision = decision_for(action, snapshot)
    if decision.allowed:
        return ShieldDecision(action, action, False, decision.reason_codes)
    return ShieldDecision(
        action,
        HighLevelAction.abort(),
        True,
        ("SHIELD_EXECUTED_ABORT", *decision.reason_codes),
    )


def strategy_mask(snapshot: GateSnapshot) -> Mapping[str, MaskDecision]:
    """Return a compact policy mask; candidate/timing remain high-level fields."""

    blocked = snapshot.blocking_reason_codes
    return MappingProxyType(
        {
            StrategyId.S1.value: MaskDecision(not blocked, blocked or ("TWELVE_HASH_BOUND_GATES_PASS",)),
            StrategyId.S3A.value: MaskDecision(not blocked, blocked or ("TWELVE_HASH_BOUND_GATES_PASS",)),
            StrategyId.ABORT.value: MaskDecision(True, ("ABORT_ALWAYS_AVAILABLE",)),
        }
    )


def unknown_evidence(reason_code: str) -> Mapping[str, GateEvidence]:
    """Internal fail-closed evidence set for an unavailable authority config."""

    return MappingProxyType(
        {
            name: GateEvidence(GateState.UNKNOWN, None, None, reason_code)
            for name in REQUIRED_GATES
        }
    )


__all__ = [
    "GateEvidence",
    "GateSnapshot",
    "GateState",
    "HighLevelAction",
    "INHERITED_V1_GATES",
    "MECHANICAL_V2_GATES",
    "MaskDecision",
    "REQUIRED_GATES",
    "ShieldDecision",
    "StrategyId",
    "decision_for",
    "enforce_fail_closed",
    "parse_action",
    "strategy_mask",
]
