"""High-level action, gate and capture-event contracts for Sim14."""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Mapping


class ExecutionMode(str, Enum):
    PRODUCTION_FAIL_CLOSED = "PRODUCTION_FAIL_CLOSED"
    BOUNDED_DIAGNOSTIC = "BOUNDED_DIAGNOSTIC"


class GateState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RuntimeGateSnapshot:
    ik_reachable: GateState = GateState.UNKNOWN
    external_collision_clear: GateState = GateState.UNKNOWN
    keep_out_clear: GateState = GateState.UNKNOWN
    joint_limits_satisfied: GateState = GateState.UNKNOWN
    relative_state_valid: GateState = GateState.UNKNOWN
    gripper_geometry_valid: GateState = GateState.UNKNOWN
    capture_window_valid: GateState = GateState.UNKNOWN
    post_capture_stability_valid: GateState = GateState.UNKNOWN

    @classmethod
    def all_pass(cls) -> "RuntimeGateSnapshot":
        return cls(**{item.name: GateState.PASS for item in fields(cls)})

    def reason_codes(self) -> tuple[str, ...]:
        output: list[str] = []
        for item in fields(self):
            state = getattr(self, item.name)
            if state is not GateState.PASS:
                output.append(f"{item.name.upper()}_{state.value}")
        return tuple(output)


class ActionCommand(str, Enum):
    ABORT = "ABORT"
    HOLD = "HOLD"
    MOVE_PREGRASP = "MOVE_PREGRASP"
    DECLARE_CONTACT_CANDIDATE = "DECLARE_CONTACT_CANDIDATE"
    CLOSE_GRIPPER = "CLOSE_GRIPPER"


@dataclass(frozen=True)
class HighLevelAction:
    command: ActionCommand

    @property
    def is_abort(self) -> bool:
        return self.command is ActionCommand.ABORT

    @classmethod
    def abort(cls) -> "HighLevelAction":
        return cls(ActionCommand.ABORT)

    @classmethod
    def parse(cls, value: "HighLevelAction | str | Mapping[str, Any]") -> "HighLevelAction":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(ActionCommand(value))
            except ValueError as exc:
                raise ValueError(f"unsupported high-level action: {value}") from exc
        forbidden = {
            key
            for key in value
            if "torque" in str(key).lower() or str(key).lower() in {"tau", "joint_effort"}
        }
        if forbidden:
            raise ValueError(
                f"direct joint torque/effort actions are forbidden: {sorted(forbidden)}"
            )
        if set(value) != {"command"}:
            raise ValueError("action mapping must contain exactly the command field")
        return cls.parse(str(value["command"]))

    def as_dict(self) -> dict[str, str]:
        return {"command": self.command.value}


class EventPhase(str, Enum):
    RESET_READY = "RESET_READY"
    PREGRASP = "PREGRASP"
    CONTACT_CANDIDATE = "CONTACT_CANDIDATE"
    CAPTURED = "CAPTURED"
    ABORTED_SAFE = "ABORTED_SAFE"


_LEGAL_COMMANDS = {
    EventPhase.RESET_READY: {ActionCommand.HOLD, ActionCommand.MOVE_PREGRASP},
    EventPhase.PREGRASP: {ActionCommand.HOLD, ActionCommand.DECLARE_CONTACT_CANDIDATE},
    EventPhase.CONTACT_CANDIDATE: {ActionCommand.HOLD, ActionCommand.CLOSE_GRIPPER},
    EventPhase.CAPTURED: {ActionCommand.HOLD},
    EventPhase.ABORTED_SAFE: set(),
}


@dataclass(frozen=True)
class MaskDecision:
    allowed: bool
    reason_codes: tuple[str, ...]


class ActionMasker:
    def evaluate(
        self,
        action: HighLevelAction,
        *,
        phase: EventPhase,
        gates: RuntimeGateSnapshot,
        mode: ExecutionMode,
        interface_production_ready: bool,
        diagnostic_acknowledged: bool,
    ) -> MaskDecision:
        if action.is_abort:
            return MaskDecision(True, ("ABORT_ALWAYS_AVAILABLE",))
        reasons = list(gates.reason_codes())
        if mode is ExecutionMode.PRODUCTION_FAIL_CLOSED:
            if not interface_production_ready:
                reasons.append("MECHANICAL_INTERFACE_NOT_PRODUCTION_READY")
        elif not diagnostic_acknowledged:
            reasons.append("DIAGNOSTIC_SCOPE_NOT_ACKNOWLEDGED")
        if action.command not in _LEGAL_COMMANDS[phase]:
            reasons.append(f"ILLEGAL_{phase.value}_TO_{action.command.value}")
        if reasons:
            return MaskDecision(False, tuple(reasons))
        scope = (
            "PRODUCTION_AUTHORITY_AND_RUNTIME_GATES_PASS"
            if mode is ExecutionMode.PRODUCTION_FAIL_CLOSED
            else "BOUNDED_DIAGNOSTIC_ONLY_RUNTIME_GATES_PASS"
        )
        return MaskDecision(True, (scope,))


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
        action: HighLevelAction,
        **context: Any,
    ) -> ShieldResult:
        decision = self.masker.evaluate(action, **context)
        if decision.allowed:
            return ShieldResult(action, action, False, decision.reason_codes)
        return ShieldResult(
            requested_action=action,
            executed_action=HighLevelAction.abort(),
            intervened=True,
            reason_codes=("SHIELD_ABORT", *decision.reason_codes),
        )


class CaptureEventStateMachine:
    def __init__(self) -> None:
        self.phase = EventPhase.RESET_READY

    def apply(self, action: HighLevelAction) -> EventPhase:
        if action.is_abort:
            self.phase = EventPhase.ABORTED_SAFE
        elif action.command is ActionCommand.HOLD:
            pass
        elif action.command is ActionCommand.MOVE_PREGRASP:
            self.phase = EventPhase.PREGRASP
        elif action.command is ActionCommand.DECLARE_CONTACT_CANDIDATE:
            self.phase = EventPhase.CONTACT_CANDIDATE
        elif action.command is ActionCommand.CLOSE_GRIPPER:
            self.phase = EventPhase.CAPTURED
        return self.phase


__all__ = [
    "ActionCommand",
    "ActionMasker",
    "CaptureEventStateMachine",
    "EventPhase",
    "ExecutionMode",
    "GateState",
    "HighLevelAction",
    "MaskDecision",
    "RuntimeGateSnapshot",
    "SafetyShield",
    "ShieldResult",
]
