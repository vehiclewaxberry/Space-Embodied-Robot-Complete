"""Diagnostic-only Sim15 environment facade.

This small facade intentionally is not an RL environment authority.  It offers
a Gymnasium-shaped reset/step API for deterministic software verification while
returning ``reward=None`` and refusing production or physical-contact actions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from enum import Enum
from typing import Any

from .authority import ACKNOWLEDGEMENT, AuthorityBundle
from .contact_gate import PhysicalContactGate
from .joint_loads import JointLoadDistributor
from .rigid_capture import RigidPlasticCaptureSolver, body_from_mapping


ENV_SCOPE = (
    "SIM15_HASH_BOUND_DIAGNOSTIC_SOFTWARE_VERIFICATION_NOT_PHYSICAL_CONTACT_OR_RL"
)


class ExecutionMode(str, Enum):
    DIAGNOSTIC_ONLY = "diagnostic_only"
    PRODUCTION = "production"


class DiagnosticAcknowledgementRequired(PermissionError):
    """Raised if diagnostic limitations were not explicitly acknowledged."""


class ProductionModeNotAuthorized(PermissionError):
    """Raised before any production-mode environment can be created."""


def _execution_mode(value: ExecutionMode | str) -> ExecutionMode:
    if isinstance(value, ExecutionMode):
        return value
    if not isinstance(value, str):
        raise TypeError("mode must be ExecutionMode or string")
    normalized = value.strip().casefold()
    if normalized in {"diagnostic", "diagnostic_only", "sim15_diagnostic"}:
        return ExecutionMode.DIAGNOSTIC_ONLY
    if normalized == "production":
        return ExecutionMode.PRODUCTION
    raise ValueError(f"unknown Sim15 execution mode: {value!r}")


class Sim15DiagnosticEnv:
    """Deterministic facade over bounded capture and joint-load diagnostics."""

    metadata = {
        "render_modes": (),
        "scope": ENV_SCOPE,
        "reward_authority": False,
        "physical_contact_authority": False,
    }

    def __init__(
        self,
        authority: AuthorityBundle,
        *,
        acknowledgement: str,
        mode: ExecutionMode | str = ExecutionMode.DIAGNOSTIC_ONLY,
        anchor_id: str = "ANCHOR_22KG_0P5DPS",
        joint_pattern_id: str = "B601_TO_STAGE_A_4XM4_64MM",
    ) -> None:
        selected_mode = _execution_mode(mode)
        if selected_mode is ExecutionMode.PRODUCTION:
            raise ProductionModeNotAuthorized(
                "Sim15 has no production authority; M5 authorizes diagnostic software only"
            )
        if acknowledgement != ACKNOWLEDGEMENT:
            raise DiagnosticAcknowledgementRequired(
                "exact M5 diagnostic acknowledgement is required before execution"
            )
        if not isinstance(authority, AuthorityBundle):
            raise TypeError("authority must be a verified AuthorityBundle")
        if authority.production_ready:
            raise ProductionModeNotAuthorized(
                "this diagnostic revision refuses an authority bundle marked production-ready"
            )
        anchors = authority.diagnostic_fixture.get("anchors")
        if not isinstance(anchors, Mapping) or anchor_id not in anchors:
            raise KeyError(f"unknown diagnostic fixture anchor: {anchor_id}")
        distributor = JointLoadDistributor(authority)
        if joint_pattern_id not in distributor.pattern_ids:
            raise KeyError(f"unknown frozen joint pattern: {joint_pattern_id}")

        self.authority = authority
        self.mode = selected_mode
        self.anchor_id = anchor_id
        self.joint_pattern_id = joint_pattern_id
        self._capture_solver = RigidPlasticCaptureSolver()
        self._joint_distributor = distributor
        self._last_operation: str | None = None
        self._capture_result: dict[str, Any] | None = None
        self._joint_load_result: dict[str, Any] | None = None

    def _contact_gate_mapping(self) -> dict[str, Any]:
        return asdict(PhysicalContactGate.evaluate(self.authority))

    def _observation(self) -> dict[str, Any]:
        contact_gate = self._contact_gate_mapping()
        return {
            "mode": self.mode.value,
            "interface_sha256": self.authority.interface_sha256,
            "anchor_id": self.anchor_id,
            "last_operation": self._last_operation,
            "capture_result": self._capture_result,
            "joint_load_result": self._joint_load_result,
            "physical_contact_authorized": bool(contact_gate["allowed"]),
        }

    def _info(
        self,
        *,
        reason_code: str,
        executed_action: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "scope": ENV_SCOPE,
            "reason_code": reason_code,
            "executed_action": None if executed_action is None else dict(executed_action),
            "capture_result": self._capture_result,
            "joint_load_result": self._joint_load_result,
            "contact_gate": self._contact_gate_mapping(),
        }

    def reset(
        self,
        *,
        seed: int | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            raise TypeError("seed must be an integer or None")
        if options is not None and not isinstance(options, Mapping):
            raise TypeError("options must be a mapping or None")
        if options and "anchor_id" in options:
            requested_anchor = options["anchor_id"]
            anchors = self.authority.diagnostic_fixture.get("anchors")
            if not isinstance(requested_anchor, str) or not isinstance(anchors, Mapping):
                raise TypeError("options.anchor_id must be a string")
            if requested_anchor not in anchors:
                raise KeyError(f"unknown diagnostic fixture anchor: {requested_anchor}")
            self.anchor_id = requested_anchor
        self._last_operation = None
        self._capture_result = None
        self._joint_load_result = None
        observation = self._observation()
        info = self._info(
            reason_code="SIM15_DIAGNOSTIC_RESET",
            executed_action=None,
        )
        info["seed"] = seed
        return observation, info

    def step(
        self, action: Mapping[str, Any]
    ) -> tuple[dict[str, Any], None, bool, bool, dict[str, Any]]:
        if not isinstance(action, Mapping):
            raise TypeError("Sim15 diagnostic action must be a mapping")
        operation = action.get("operation")
        if not isinstance(operation, str):
            raise TypeError("action.operation must be a string")
        operation = operation.strip().casefold()

        if operation == "physical_contact":
            unexpected = set(action) - {"operation"}
            if unexpected:
                raise ValueError(
                    f"physical_contact action contains prohibited fields: {sorted(unexpected)}"
                )
            PhysicalContactGate.require(self.authority)
            raise AssertionError("unreachable: current Sim15 contact gate must fail closed")

        if operation == "capture":
            unexpected = set(action) - {"operation", "anchor_id"}
            if unexpected:
                raise ValueError(
                    f"capture action contains prohibited fields: {sorted(unexpected)}"
                )
            requested_anchor = action.get("anchor_id", self.anchor_id)
            anchors = self.authority.diagnostic_fixture.get("anchors")
            if not isinstance(requested_anchor, str):
                raise TypeError("action.anchor_id must be a string")
            if not isinstance(anchors, Mapping) or requested_anchor not in anchors:
                raise KeyError(f"unknown diagnostic fixture anchor: {requested_anchor}")
            service_record = self.authority.diagnostic_fixture.get(
                "service_spacecraft_fixture"
            )
            if not isinstance(service_record, Mapping):
                raise ValueError("diagnostic service fixture is malformed")
            target_record = anchors[requested_anchor]
            if not isinstance(target_record, Mapping):
                raise ValueError("diagnostic target fixture is malformed")
            result = self._capture_solver.capture(
                body_from_mapping(service_record), body_from_mapping(target_record)
            )
            self.anchor_id = requested_anchor
            self._last_operation = "capture"
            self._capture_result = asdict(result)
            canonical_action = {"operation": "capture", "anchor_id": requested_anchor}
            reason_code = "SIM15_RIGID_CAPTURE_DIAGNOSTIC_EXECUTED"
        elif operation == "joint_load_distribution":
            unexpected = set(action) - {"operation", "pattern_id", "wrench_N_Nm"}
            if unexpected:
                raise ValueError(
                    "joint_load_distribution action contains prohibited fields: "
                    f"{sorted(unexpected)}"
                )
            if "wrench_N_Nm" not in action:
                raise KeyError("joint_load_distribution requires explicit wrench_N_Nm")
            pattern_id = action.get("pattern_id", self.joint_pattern_id)
            if not isinstance(pattern_id, str):
                raise TypeError("action.pattern_id must be a string")
            result = self._joint_distributor.distribute(
                pattern_id, action["wrench_N_Nm"]
            )
            self.joint_pattern_id = pattern_id
            self._last_operation = "joint_load_distribution"
            self._joint_load_result = asdict(result)
            canonical_action = {
                "operation": "joint_load_distribution",
                "pattern_id": pattern_id,
                "wrench_N_Nm": result.input_wrench_N_Nm,
            }
            reason_code = "SIM15_GEOMETRIC_JOINT_DISTRIBUTION_EXECUTED"
        else:
            raise ValueError(f"unsupported Sim15 diagnostic operation: {operation!r}")

        observation = self._observation()
        info = self._info(reason_code=reason_code, executed_action=canonical_action)
        return observation, None, False, False, info

    def close(self) -> None:
        """No resources are held; provided for API compatibility."""


__all__ = [
    "DiagnosticAcknowledgementRequired",
    "ENV_SCOPE",
    "ExecutionMode",
    "ProductionModeNotAuthorized",
    "Sim15DiagnosticEnv",
]
