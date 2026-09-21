"""Computed, fail-closed physical-contact authorization gate for Sim15."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


GATE_SCOPE = "SIM15_PHYSICAL_CONTACT_FAIL_CLOSED_AUTHORIZATION_GATE"


class PhysicalContactNotAuthorized(RuntimeError):
    """Raised whenever a caller requests physical contact without full authority."""

    def __init__(self, decision: "ContactGateDecision") -> None:
        self.decision = decision
        reasons = ", ".join(decision.reason_codes) or "UNSPECIFIED_CONTACT_HOLD"
        super().__init__(f"physical contact is not authorized: {reasons}")


@dataclass(frozen=True)
class ContactGateDecision:
    gate_scope: str
    allowed: bool
    physical_contact_authorized: bool
    status: str
    reason_codes: tuple[str, ...]
    missing_parameter_paths: tuple[str, ...]
    incomplete_uncertainty_paths: tuple[str, ...]
    missing_contact_frame_paths: tuple[str, ...]
    missing_structural_path_fields: tuple[str, ...]
    force_output_permitted: bool
    pressure_output_permitted: bool


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _estimated_parameters(value: Any, path: tuple[str, ...] = ()) -> list[tuple[str, Mapping[str, Any]]]:
    found: list[tuple[str, Mapping[str, Any]]] = []
    if isinstance(value, Mapping):
        if "estimate" in value and "status" in value:
            found.append((".".join(path), value))
        for key, child in value.items():
            found.extend(_estimated_parameters(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_estimated_parameters(child, (*path, str(index))))
    return found


class PhysicalContactGate:
    """Derive contact authorization from every required upstream condition."""

    @staticmethod
    def evaluate(authority: Any) -> ContactGateDecision:
        contract = _mapping(getattr(authority, "contact_contract", None))
        document = _mapping(getattr(authority, "document", None))
        broadphase = _mapping(getattr(authority, "broadphase_audit", None))
        structural = _mapping(getattr(authority, "structural_gate", None))
        load_authority = _mapping(getattr(authority, "load_authority", None))
        geometry_capabilities = _mapping(document.get("geometry_capabilities"))
        load_capabilities = _mapping(document.get("loads_capabilities"))
        runtime_gates = _mapping(document.get("runtime_gates"))

        reasons: list[str] = []
        if contract.get("schema") != "M5_CONTACT_MODEL_PARAMETER_CONTRACT_V1":
            reasons.append("CONTACT_CONTRACT_SCHEMA_MISSING_OR_CHANGED")
        if contract.get("zero_fill_forbidden") is not True:
            reasons.append("ZERO_FILL_POLICY_NOT_ENFORCED")
        if contract.get("physical_contact_kernel_authorized") is not True:
            reasons.append("CONTACT_KERNEL_NOT_AUTHORIZED")

        parameters = _estimated_parameters(contract)
        missing_parameters = tuple(
            path for path, parameter in parameters if parameter.get("estimate") is None
        )
        if missing_parameters:
            reasons.append("PHYSICAL_CONTACT_PARAMETERS_INCOMPLETE")
        incomplete_uncertainty = tuple(
            path
            for path, parameter in parameters
            if any(
                parameter.get(key) is None
                for key in (
                    "standard_uncertainty",
                    "distribution",
                    "degrees_of_freedom",
                    "source",
                )
            )
        )
        if incomplete_uncertainty:
            reasons.append("CONTACT_PARAMETER_UNCERTAINTY_INCOMPLETE")

        contact_geometry = _mapping(contract.get("contact_geometry"))
        frame_fields = (
            "left_contact_frame_T_gripper_link",
            "right_contact_frame_T_gripper_link",
            "target_surface_normal",
        )
        missing_frames = tuple(
            f"contact_geometry.{field}"
            for field in frame_fields
            if contact_geometry.get(field) is None
        )
        if missing_frames:
            reasons.append("CONTACT_FRAMES_INCOMPLETE")

        structural_mapping = _mapping(contract.get("structural_mapping"))
        structural_fields = (
            "T_wrist_from_contact",
            "T_arm_base_from_wrist",
            "T_m3r_from_arm_base",
            "T_load_bridge_from_m3r",
        )
        missing_structural = tuple(
            f"structural_mapping.{field}"
            for field in structural_fields
            if structural_mapping.get(field) is None
        )
        if missing_structural:
            reasons.append("COMPLETE_6D_STRUCTURAL_LOAD_PATH_ABSENT")

        required_true_conditions = (
            (
                geometry_capabilities.get("narrow_phase_verified") is True,
                "NARROW_PHASE_NOT_VERIFIED",
            ),
            (
                geometry_capabilities.get("contact_geometry_authorized") is True,
                "CONTACT_GEOMETRY_NOT_AUTHORIZED",
            ),
            (
                broadphase.get("narrow_phase_available") is True,
                "NARROW_PHASE_UNAVAILABLE",
            ),
            (
                broadphase.get("system_collision_release") is True,
                "SYSTEM_COLLISION_NOT_RELEASED",
            ),
            (
                load_capabilities.get("physical_load_authority") is True,
                "PHYSICAL_LOAD_AUTHORITY_ABSENT",
            ),
            (
                load_authority.get("formal_loads_authorized") is True,
                "FORMAL_LOADS_NOT_AUTHORIZED",
            ),
            (
                structural.get("pass_token_issued") is True,
                "STRUCTURAL_PASS_TOKEN_NOT_ISSUED",
            ),
            (
                structural.get("formal_fea_authorized") is True,
                "FORMAL_FEA_NOT_AUTHORIZED",
            ),
        )
        for condition, reason in required_true_conditions:
            if not condition:
                reasons.append(reason)
        if runtime_gates.get("physical_contact") != "PASS":
            reasons.append("RUNTIME_PHYSICAL_CONTACT_GATE_HOLD")

        if contract.get("computed_contact_force_N") is not None:
            reasons.append("UNAUTHORIZED_PRECOMPUTED_CONTACT_FORCE_PRESENT")
        if contract.get("computed_contact_pressure_Pa") is not None:
            reasons.append("UNAUTHORIZED_PRECOMPUTED_CONTACT_PRESSURE_PRESENT")

        unique_reasons = tuple(dict.fromkeys(reasons))
        allowed = not unique_reasons
        return ContactGateDecision(
            gate_scope=GATE_SCOPE,
            allowed=allowed,
            physical_contact_authorized=allowed,
            status="PASS_PHYSICAL_CONTACT_AUTHORIZED" if allowed else "HOLD_PHYSICAL_CONTACT_NOT_AUTHORIZED",
            reason_codes=unique_reasons,
            missing_parameter_paths=missing_parameters,
            incomplete_uncertainty_paths=incomplete_uncertainty,
            missing_contact_frame_paths=missing_frames,
            missing_structural_path_fields=missing_structural,
            force_output_permitted=allowed,
            pressure_output_permitted=allowed,
        )

    @staticmethod
    def require(authority: Any) -> ContactGateDecision:
        decision = PhysicalContactGate.evaluate(authority)
        if not decision.allowed:
            raise PhysicalContactNotAuthorized(decision)
        return decision


__all__ = [
    "ContactGateDecision",
    "GATE_SCOPE",
    "PhysicalContactGate",
    "PhysicalContactNotAuthorized",
]
