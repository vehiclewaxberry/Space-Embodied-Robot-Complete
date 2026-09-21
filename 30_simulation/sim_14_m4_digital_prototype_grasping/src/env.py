"""Fail-closed Sim14 environment with a bounded diagnostic execution mode."""
from __future__ import annotations

import math
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, Mapping

from .contracts import (
    ActionCommand,
    ActionMasker,
    CaptureEventStateMachine,
    EventPhase,
    ExecutionMode,
    HighLevelAction,
    MaskDecision,
    RuntimeGateSnapshot,
    SafetyShield,
)
from .dynamics import FreeFloatingMomentumBackend
from .interface_loader import (
    DiagnosticFixture,
    MechanicalInterfaceBundle,
    load_diagnostic_fixture,
    load_mechanical_interface,
    validate_diagnostic_fixture_against_m4,
)


ANCHOR_22KG = "ANCHOR_22KG_0P5DPS"
ANCHOR_150KG = "ANCHOR_150KG_3DPS"
KNOWN_ANCHORS = (ANCHOR_22KG, ANCHOR_150KG)


class M4DigitalPrototypeGraspingEnv:
    """Gym-like high-level environment without a Gym dependency.

    Production mode deliberately has no numerical backend in this revision: the
    M4 interface itself identifies incomplete system and target properties.
    Diagnostic mode requires the exact acknowledgement string before fixture
    values are loaded.
    """

    metadata = {
        "name": "sim_14_m4_digital_prototype_grasping",
        "contract_version": "sim14-m4-bridge-v1",
        "render_modes": [],
    }

    def __init__(
        self,
        mechanical_interface_path: str | Path,
        *,
        execution_mode: ExecutionMode | str = ExecutionMode.PRODUCTION_FAIL_CLOSED,
        diagnostic_fixture_path: str | Path | None = None,
        diagnostic_acknowledgement: str | None = None,
        anchor_id: str = ANCHOR_22KG,
        timestep_s: float = 0.05,
        maximum_steps: int = 1000,
    ) -> None:
        self.interface: MechanicalInterfaceBundle = load_mechanical_interface(
            mechanical_interface_path
        )
        try:
            self.mode = ExecutionMode(execution_mode)
        except ValueError as exc:
            raise ValueError(f"unsupported execution mode: {execution_mode}") from exc
        if anchor_id not in KNOWN_ANCHORS:
            raise ValueError(f"unknown anchor: {anchor_id}")
        if not isinstance(maximum_steps, int) or isinstance(maximum_steps, bool):
            raise ValueError("maximum_steps must be an integer")
        if maximum_steps <= 0:
            raise ValueError("maximum_steps must be positive")
        if not math.isfinite(timestep_s) or timestep_s <= 0.0:
            raise ValueError("timestep_s must be finite and positive")
        self.default_anchor_id = anchor_id
        self.timestep_s = float(timestep_s)
        self.maximum_steps = maximum_steps
        self.diagnostic_fixture: DiagnosticFixture | None = None
        if self.mode is ExecutionMode.BOUNDED_DIAGNOSTIC:
            if diagnostic_fixture_path is None:
                raise ValueError("bounded diagnostic mode requires a fixture path")
            self.diagnostic_fixture = load_diagnostic_fixture(
                diagnostic_fixture_path,
                acknowledgement=diagnostic_acknowledgement,
            )
            validate_diagnostic_fixture_against_m4(
                self.interface, self.diagnostic_fixture
            )
        self.masker = ActionMasker()
        self.shield = SafetyShield(self.masker)
        self.gates = RuntimeGateSnapshot()
        self.state_machine = CaptureEventStateMachine()
        self.backend: FreeFloatingMomentumBackend | None = None
        self.anchor_id = anchor_id
        self.step_count = 0
        self.has_reset = False
        self.termination_reason: str | None = None

    @property
    def diagnostic_acknowledged(self) -> bool:
        return self.diagnostic_fixture is not None

    @property
    def production_backend_bound(self) -> bool:
        # A future production backend must consume released configuration mass,
        # inertia, contact and collision authorities. None is bound in V1.
        return False

    @property
    def executable_authority_ready(self) -> bool:
        if self.mode is ExecutionMode.BOUNDED_DIAGNOSTIC:
            return self.diagnostic_acknowledged and self.backend is not None
        return self.interface.production_ready and self.production_backend_bound

    def reset(
        self,
        *,
        anchor_id: str | None = None,
        gates: RuntimeGateSnapshot | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        selected_anchor = self.default_anchor_id if anchor_id is None else anchor_id
        if selected_anchor not in KNOWN_ANCHORS:
            raise ValueError(f"unknown anchor: {selected_anchor}")
        self.anchor_id = selected_anchor
        self.gates = gates or RuntimeGateSnapshot()
        self.state_machine = CaptureEventStateMachine()
        self.step_count = 0
        self.termination_reason = None
        if self.diagnostic_fixture is not None:
            self.backend = FreeFloatingMomentumBackend(
                self.diagnostic_fixture.service_spacecraft,
                self.diagnostic_fixture.anchors[selected_anchor],
                timestep_s=self.timestep_s,
            )
        else:
            self.backend = None
        self.has_reset = True
        return self._observation(), self._info()

    def _mask_context(self) -> dict[str, Any]:
        return {
            "phase": self.state_machine.phase,
            "gates": self.gates,
            "mode": self.mode,
            "interface_production_ready": (
                self.interface.production_ready and self.production_backend_bound
            ),
            "diagnostic_acknowledged": self.diagnostic_acknowledged,
        }

    def action_mask(
        self,
        gates: RuntimeGateSnapshot | None = None,
    ) -> Mapping[HighLevelAction, MaskDecision]:
        if gates is not None:
            self.gates = gates
        context = self._mask_context()
        return {
            HighLevelAction(command): self.masker.evaluate(
                HighLevelAction(command), **context
            )
            for command in ActionCommand
        }

    def _observation(self) -> dict[str, Any]:
        backend = self.backend
        capture = backend.capture_report if backend is not None else None
        target_kind = backend.target_kind if backend is not None else None
        target_mass = backend.target.mass_kg if backend is not None else None
        observation: dict[str, Any] = {
            "schema_version": "SIM14_STATE_OBSERVATION_V1",
            "execution_mode": self.mode.value,
            "simulation_time_s": (
                backend.simulation_time_s if backend is not None else 0.0
            ),
            "task_phase": self.state_machine.phase.value,
            "mechanical_interface": {
                "sha256": self.interface.manifest_sha256,
                "production_ready": self.interface.production_ready,
                "production_backend_bound": self.production_backend_bound,
                "unresolved_required_artifacts": list(
                    self.interface.unresolved_required_artifacts
                ),
                "missing_authorities": list(
                    self.interface.computed_missing_authorities
                ),
            },
            "target": {
                "anchor_id": self.anchor_id,
                "kind": target_kind,
                "mass_kg": target_mass,
                "mass_authority": (
                    "DIAGNOSTIC_FIXTURE_NOT_ENGINEERING_AUTHORITY"
                    if backend is not None
                    else "UNKNOWN_PRODUCTION_AUTHORITY"
                ),
                "state": (
                    {
                        "position_m": list(backend.target.position_m),
                        "quaternion_xyzw": list(backend.target.quaternion_xyzw),
                        "linear_velocity_mps": list(
                            backend.target.linear_velocity_mps
                        ),
                        "angular_velocity_radps": list(
                            backend.target.angular_velocity_radps
                        ),
                    }
                    if backend is not None
                    else None
                ),
            },
            "service_spacecraft": (
                {
                    "mass_kg": backend.service.mass_kg,
                    "mass_authority": "DIAGNOSTIC_FIXTURE_NOT_ENGINEERING_AUTHORITY",
                    "position_m": list(backend.service.position_m),
                    "quaternion_xyzw": list(backend.service.quaternion_xyzw),
                    "linear_velocity_mps": list(
                        backend.service.linear_velocity_mps
                    ),
                    "angular_velocity_radps": list(
                        backend.service.angular_velocity_radps
                    ),
                }
                if backend is not None
                else {
                    "mass_kg": None,
                    "mass_authority": "UNKNOWN_PRODUCTION_AUTHORITY",
                }
            ),
            "capture_closure": asdict(capture) if capture is not None else None,
            "contact": {
                "force_N": None,
                "impulse_time_history_N_s": None,
                "pressure_Pa": None,
                "friction_coefficient": None,
                "status": "NOT_COMPUTED_NO_AUTHORIZED_CONTACT_MODEL",
            },
            "flexible_body": {
                "enabled": False,
                "modal_coordinates": None,
                "status": "NOT_COMPUTED_NO_AUTHORIZED_MODAL_MODEL",
            },
            "runtime_gates": {
                item.name: getattr(self.gates, item.name).value
                for item in fields(self.gates)
            },
        }
        self._validate_finite(observation)
        return observation

    @staticmethod
    def _validate_finite(value: Any) -> None:
        stack = [value]
        while stack:
            item = stack.pop()
            if isinstance(item, Mapping):
                stack.extend(item.values())
            elif isinstance(item, (list, tuple)):
                stack.extend(item)
            elif isinstance(item, float) and not math.isfinite(item):
                raise ValueError("observation contains a non-finite number")

    def _info(self) -> dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "step_count": self.step_count,
            "execution_mode": self.mode.value,
            "authorized_scope": (
                "BOUNDED_DIAGNOSTIC_SOFTWARE_MECHANICS_ONLY"
                if self.mode is ExecutionMode.BOUNDED_DIAGNOSTIC
                else "PRODUCTION_FAIL_CLOSED_NO_NUMERICAL_EXECUTION"
            ),
            "mechanical_interface_sha256": self.interface.manifest_sha256,
            "diagnostic_fixture_sha256": (
                self.diagnostic_fixture.sha256
                if self.diagnostic_fixture is not None
                else None
            ),
            "production_blockers": list(self.interface.blocker_codes),
            "termination_reason": self.termination_reason,
        }

    def step(
        self,
        action: HighLevelAction | str | Mapping[str, Any],
        *,
        gates: RuntimeGateSnapshot | None = None,
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if not self.has_reset:
            raise RuntimeError("reset must be called before step")
        if gates is not None:
            self.gates = gates
        requested = HighLevelAction.parse(action)
        shield = self.shield.enforce(requested, **self._mask_context())
        executed = shield.executed_action
        if executed.command is ActionCommand.CLOSE_GRIPPER:
            if self.backend is None:
                raise RuntimeError("safety defect: capture reached an unbound backend")
            self.backend.capture()
        elif not executed.is_abort:
            if self.backend is None:
                raise RuntimeError("safety defect: numerical action reached an unbound backend")
            self.backend.advance()
        phase = self.state_machine.apply(executed)
        self.step_count += 1
        terminated = phase is EventPhase.ABORTED_SAFE or phase is EventPhase.CAPTURED
        truncated = not terminated and self.step_count >= self.maximum_steps
        if phase is EventPhase.ABORTED_SAFE:
            self.termination_reason = "ABORT"
        elif phase is EventPhase.CAPTURED:
            self.termination_reason = "DIAGNOSTIC_CAPTURE_EVENT_COMPLETE"
        elif truncated:
            self.termination_reason = "STEP_LIMIT"
        reward = 1.0 if phase is EventPhase.CAPTURED else (-1.0 if terminated else 0.0)
        observation = self._observation()
        info = self._info()
        info.update(
            {
                "requested_action": requested.as_dict(),
                "executed_action": executed.as_dict(),
                "shield_intervened": shield.intervened,
                "shield_reason_codes": list(shield.reason_codes),
            }
        )
        return observation, reward, terminated, truncated, info


__all__ = [
    "ANCHOR_22KG",
    "ANCHOR_150KG",
    "KNOWN_ANCHORS",
    "M4DigitalPrototypeGraspingEnv",
]
