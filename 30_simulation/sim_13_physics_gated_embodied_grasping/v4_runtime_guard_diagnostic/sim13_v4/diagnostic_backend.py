"""Unique coordinator for guarded V3 synthetic 6R+2P state evolution.

The public backend facade is intentionally locked. The real numerical backend
is local to :class:`DiagnosticExecutionCoordinator`; it accepts only an opaque
invocation registered in a closure-private, one-shot registry after mission
policy and shield checks have both completed.
"""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, replace
import hashlib
import math
from pathlib import Path
import sys
import threading
from typing import Mapping, Sequence

import numpy as np

from .canonical import canonical_digest
from .mission_veto import Sim10MissionVeto, TargetRequest, VetoReceipt
from .runtime_guard import DiagnosticAction, DiagnosticCapability, DiagnosticShield


V4_ROOT = Path(__file__).resolve().parents[1]
V3_ROOT = V4_ROOT.parent / "v3_in_memory_dynamics_diagnostic"
if str(V3_ROOT) not in sys.path:
    sys.path.insert(0, str(V3_ROOT))

from sim13_v3.reduced_dynamics import ZeroMomentumReducedDynamics
from sim13_v3.source_model import (
    FIXTURE_AUTHORITY_CLASS,
    FIXTURE_ID,
    build_synthetic_8dof_model,
)


BACKEND_ID = "SIM13_V4_V3_PUBLIC_SYNTHETIC_6R2P_BACKEND_V2"
BACKEND_SCOPE = "SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY_NOT_CURRENT_SYSTEM_NOT_CONTACT"
COORDINATOR_ID = "SIM13_V4_UNIQUE_DIAGNOSTIC_EXECUTION_COORDINATOR_V1"
REVOLUTE_CHANNELS = tuple(range(6))
PRISMATIC_CHANNELS = (6, 7)
GENERALIZED_EFFORT_UNITS = ("N*m",) * 6 + ("N",) * 2
GENERALIZED_COORDINATE_UNITS = ("rad",) * 6 + ("m",) * 2
GENERALIZED_RATE_UNITS = ("rad/s",) * 6 + ("m/s",) * 2


def _finite_vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{field} must contain {size} finite values")
    return result


def _quat_rotation_body_to_inertial(wxyz: Sequence[float]) -> np.ndarray:
    quaternion = _finite_vector(wxyz, 4, "base_quaternion")
    norm = float(np.linalg.norm(quaternion))
    if norm <= 0.0:
        raise ValueError("base quaternion norm must be positive")
    w, x, y, z = quaternion / norm
    return np.array(
        (
            (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
            (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
            (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
        )
    )


@dataclass(frozen=True)
class DiagnosticState:
    q_mixed_rad_m: tuple[float, ...]
    qdot_mixed_rad_s_m_s: tuple[float, ...]
    base_position_inertial_m: tuple[float, float, float]
    base_quaternion_body_to_inertial_wxyz: tuple[float, float, float, float]
    base_twist_body_mixed_m_s_rad_s: tuple[float, ...]
    ee_centroid_inertial_m: tuple[float, float, float]
    phase: str

    def __post_init__(self) -> None:
        _finite_vector(self.q_mixed_rad_m, 8, "q")
        _finite_vector(self.qdot_mixed_rad_s_m_s, 8, "qdot")
        _finite_vector(self.base_position_inertial_m, 3, "base_position")
        _finite_vector(self.base_quaternion_body_to_inertial_wxyz, 4, "base_quaternion")
        _finite_vector(self.base_twist_body_mixed_m_s_rad_s, 6, "base_twist")
        _finite_vector(self.ee_centroid_inertial_m, 3, "ee_centroid")

    def as_dict(self) -> dict[str, object]:
        return {
            "q_mixed_rad_m": list(self.q_mixed_rad_m),
            "qdot_mixed_rad_s_m_s": list(self.qdot_mixed_rad_s_m_s),
            "base_position_inertial_m": list(self.base_position_inertial_m),
            "base_quaternion_body_to_inertial_wxyz": list(self.base_quaternion_body_to_inertial_wxyz),
            "base_twist_body_mixed_m_s_rad_s": list(self.base_twist_body_mixed_m_s_rad_s),
            "ee_centroid_inertial_m": list(self.ee_centroid_inertial_m),
            "phase": self.phase,
        }


def _ee_centroid_inertial(
    model: object,
    q: Sequence[float],
    base_position_inertial_m: Sequence[float],
    base_quaternion_body_to_inertial_wxyz: Sequence[float],
) -> np.ndarray:
    transforms, _ = model.forward_kinematics(q)  # type: ignore[attr-defined]
    local = np.mean(
        np.stack(
            (
                transforms["synthetic_link_6"][:3, 3],
                transforms["synthetic_finger_1"][:3, 3],
                transforms["synthetic_finger_2"][:3, 3],
            )
        ),
        axis=0,
    )
    rotation = _quat_rotation_body_to_inertial(base_quaternion_body_to_inertial_wxyz)
    return _finite_vector(base_position_inertial_m, 3, "base_position") + rotation @ local


def initial_diagnostic_state() -> DiagnosticState:
    model = build_synthetic_8dof_model()
    q = np.array((0.08, -0.04, 0.05, 0.02, -0.03, 0.06, 0.005, -0.004))
    qdot = np.zeros(8)
    position = np.zeros(3)
    quaternion = np.array((1.0, 0.0, 0.0, 0.0))
    ee = _ee_centroid_inertial(model, q, position, quaternion)
    return DiagnosticState(
        tuple(q), tuple(qdot), tuple(position), tuple(quaternion), (0.0,) * 6,
        tuple(ee), "READY_SYNTHETIC_DIAGNOSTIC",
    )


def nominal_generalized_effort() -> tuple[float, ...]:
    """Six revolute torques [N*m], followed by two prismatic forces [N]."""

    return (0.020, -0.015, 0.010, 0.008, -0.006, 0.005, 0.012, -0.009)


def effort_record(effort: Sequence[float]) -> dict[str, object]:
    values = _finite_vector(effort, 8, "generalized_effort")
    return {
        "values_mixed": values.tolist(),
        "channel_units": list(GENERALIZED_EFFORT_UNITS),
        "revolute": {
            "indices": list(REVOLUTE_CHANNELS), "values_Nm": values[:6].tolist(),
            "nonzero": bool(np.any(values[:6] != 0.0)),
        },
        "prismatic": {
            "indices": list(PRISMATIC_CHANNELS), "values_N": values[6:].tolist(),
            "nonzero": bool(np.any(values[6:] != 0.0)),
        },
        "heterogeneous_global_norm_used": False,
    }


def synthetic_non_debris_policy_fixture() -> dict[str, object]:
    return {
        "schema": "SIM13_V4_SYNTHETIC_TARGET_POLICY_FIXTURE_V1",
        "policy_id": "ALLOW_SYNTHETIC_NON_DEBRIS_DYNAMICS_DIAGNOSTIC",
        "target": {
            "target_id": "synthetic_non_debris_fixture", "target_mass_kg": 1.0,
            "tumble_rate_dps": 0.0,
        },
        "mission_veto_required": False,
        "current_system_policy": False,
        "contact_policy": False,
        "production_credit": False,
    }


def debris_veto_policy_fixture(target: TargetRequest) -> dict[str, object]:
    return {
        "schema": "SIM13_V4_DEBRIS_VETO_POLICY_FIXTURE_V1",
        "policy_id": "REQUIRE_HASH_BOUND_SIM10_VETO_BEFORE_BACKEND",
        "target": target.as_dict(),
        "mission_veto_required": True,
        "current_system_policy": False,
        "contact_policy": False,
        "production_credit": False,
    }


def build_execution_context(
    *, run_id: str, state: DiagnosticState, generalized_effort: Sequence[float],
    step_s: float, steps: int, target_policy_fixture: Mapping[str, object],
) -> dict[str, object]:
    if not run_id:
        raise ValueError("run_id must be non-empty")
    if not math.isfinite(step_s) or step_s <= 0.0:
        raise ValueError("step_s must be positive and finite")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise ValueError("steps must be a positive integer")
    effort = effort_record(generalized_effort)
    return {
        "schema": "SIM13_V4_SYNTHETIC_EXECUTION_CONTEXT_V2",
        "scope": BACKEND_SCOPE,
        "coordinator_id": COORDINATOR_ID,
        "run_id": run_id,
        "backend_id": BACKEND_ID,
        "fixture_id": FIXTURE_ID,
        "fixture_authority_class": FIXTURE_AUTHORITY_CLASS,
        "initial_state_sha256": canonical_digest(state.as_dict()),
        "generalized_effort_sha256": canonical_digest(effort),
        "target_policy_sha256": canonical_digest(target_policy_fixture),
        "generalized_effort_units": list(GENERALIZED_EFFORT_UNITS),
        "generalized_coordinate_units": list(GENERALIZED_COORDINATE_UNITS),
        "generalized_rate_units": list(GENERALIZED_RATE_UNITS),
        "step_s": float(step_s),
        "steps": steps,
        "current_system_binding_passed": False,
        "runtime_production_gate_passed": False,
        "contact_grasp_gate_passed": False,
    }


def state_evolution_assessment(before: DiagnosticState, after: DiagnosticState) -> dict[str, object]:
    q_before, q_after = np.asarray(before.q_mixed_rad_m), np.asarray(after.q_mixed_rad_m)
    qdot_before = np.asarray(before.qdot_mixed_rad_s_m_s)
    qdot_after = np.asarray(after.qdot_mixed_rad_s_m_s)
    quaternion_before = np.asarray(before.base_quaternion_body_to_inertial_wxyz)
    quaternion_after = np.asarray(after.base_quaternion_body_to_inertial_wxyz)
    alignment = abs(float(quaternion_before @ quaternion_after))
    orientation_delta_rad = 2.0 * math.acos(min(1.0, max(-1.0, alignment)))
    deltas = {
        "revolute_q_max_abs_rad": float(np.max(np.abs(q_after[:6] - q_before[:6]))),
        "prismatic_q_max_abs_m": float(np.max(np.abs(q_after[6:] - q_before[6:]))),
        "revolute_qdot_max_abs_rad_s": float(np.max(np.abs(qdot_after[:6] - qdot_before[:6]))),
        "prismatic_qdot_max_abs_m_s": float(np.max(np.abs(qdot_after[6:] - qdot_before[6:]))),
        "base_position_norm_m": float(np.linalg.norm(np.asarray(after.base_position_inertial_m) - np.asarray(before.base_position_inertial_m))),
        "base_orientation_angle_rad": orientation_delta_rad,
        "base_twist_linear_norm_m_s": float(np.linalg.norm(np.asarray(after.base_twist_body_mixed_m_s_rad_s)[:3] - np.asarray(before.base_twist_body_mixed_m_s_rad_s)[:3])),
        "base_twist_angular_norm_rad_s": float(np.linalg.norm(np.asarray(after.base_twist_body_mixed_m_s_rad_s)[3:] - np.asarray(before.base_twist_body_mixed_m_s_rad_s)[3:])),
        "ee_centroid_position_norm_m": float(np.linalg.norm(np.asarray(after.ee_centroid_inertial_m) - np.asarray(before.ee_centroid_inertial_m))),
    }
    physical_changed = any(value > 1.0e-12 for value in deltas.values())
    return {
        "physical_state_changed": physical_changed,
        "phase_changed": before.phase != after.phase,
        "accepted": physical_changed,
        "reason_code": "REAL_NUMERICAL_STATE_EVOLUTION_DETECTED" if physical_changed else "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY",
        "deltas": deltas,
        "base_linear_and_angular_twist_audited_separately": True,
        "heterogeneous_global_norm_used": False,
    }


@dataclass(frozen=True)
class CoordinatorResult:
    executed_action: DiagnosticAction
    before: DiagnosticState
    after: DiagnosticState
    coordinator_reason_code: str
    backend_reason_code: str
    state_evolution: Mapping[str, object]
    capability_consumed: bool
    backend_invocation_count_before: int
    backend_invocation_count_after: int
    production_credit: bool = False

    @property
    def backend_invocation_delta(self) -> int:
        return self.backend_invocation_count_after - self.backend_invocation_count_before


class OpaqueInvocation:
    """Non-constructible marker; real objects are closure-registered."""

    __slots__ = ("_handle",)

    def __new__(cls, *args: object, **kwargs: object) -> "OpaqueInvocation":
        raise TypeError("OPAQUE_INVOCATION_DIRECT_CONSTRUCTION_REJECTED")


class SyntheticCapabilityBackend:
    """Locked facade proving that a capability alone cannot invoke dynamics."""

    __slots__ = ()

    def execute(self, *args: object, **kwargs: object) -> None:
        raise PermissionError("BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR")

    def execute_authorized_kernel(self, *args: object, **kwargs: object) -> None:
        raise PermissionError("BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR")


class DiagnosticExecutionCoordinator:
    """The sole high-level diagnostic execution surface."""

    __slots__ = ("_execute", "_security_probe", "_invocation_count")

    def __init__(self) -> None:
        registry_lock = threading.Lock()
        registry: dict[str, dict[str, object]] = {}
        sequence = 0
        backend_invocations = 0
        model = build_synthetic_8dof_model()
        solver = ZeroMomentumReducedDynamics(model)

        def register(bindings: Mapping[str, object]) -> OpaqueInvocation:
            nonlocal sequence
            with registry_lock:
                sequence += 1
                handle = hashlib.sha256(f"{sequence}:{canonical_digest(bindings)}".encode()).hexdigest().upper()
                invocation = object.__new__(OpaqueInvocation)
                object.__setattr__(invocation, "_handle", handle)
                registry[handle] = {"object": invocation, "bindings": dict(bindings), "state": "READY"}
                return invocation

        def redeem(invocation: object, bindings: Mapping[str, object]) -> tuple[bool, str]:
            if type(invocation) is not OpaqueInvocation:
                return False, "OPAQUE_INVOCATION_TYPE_REJECTED"
            handle = getattr(invocation, "_handle", None)
            if not isinstance(handle, str):
                return False, "OPAQUE_INVOCATION_UNREGISTERED"
            with registry_lock:
                record = registry.get(handle)
                if record is None:
                    return False, "OPAQUE_INVOCATION_UNREGISTERED"
                if record["object"] is not invocation:
                    return False, "OPAQUE_INVOCATION_OBJECT_IDENTITY_MISMATCH"
                if record["state"] != "READY":
                    return False, "OPAQUE_INVOCATION_REPLAY_REJECTED"
                if record["bindings"] != dict(bindings):
                    return False, "OPAQUE_INVOCATION_BINDING_MISMATCH"
                record["state"] = "CONSUMED"
                return True, "OPAQUE_INVOCATION_REDEEMED_ONCE"

        def invocation_count() -> int:
            with registry_lock:
                return backend_invocations

        class RegisteredSyntheticBackend:
            __slots__ = ()

            def advance(self, *, invocation: object, bindings: Mapping[str, object], state: DiagnosticState, generalized_effort: Sequence[float], step_s: float, steps: int) -> tuple[DiagnosticState, Mapping[str, object]]:
                nonlocal backend_invocations
                accepted, reason = redeem(invocation, bindings)
                if not accepted:
                    raise PermissionError(reason)
                with registry_lock:
                    backend_invocations += 1
                effort = _finite_vector(generalized_effort, 8, "generalized_effort")
                history = solver.propagate(
                    state.q_mixed_rad_m, state.qdot_mixed_rad_s_m_s,
                    step_s=step_s, steps=steps, generalized_effort=effort,
                    base_position_inertial_initial_m=state.base_position_inertial_m,
                    base_quaternion_body_to_inertial_initial_wxyz=state.base_quaternion_body_to_inertial_wxyz,
                )
                q_final, qdot_final = history.q[-1], history.qdot[-1]
                position_final = history.base_position_inertial_m[-1]
                quaternion_final = history.base_quaternion_body_to_inertial_wxyz[-1]
                twist_final = history.base_twist_body_mixed_units[-1]
                ee_final = _ee_centroid_inertial(model, q_final, position_final, quaternion_final)
                after = DiagnosticState(
                    tuple(q_final), tuple(qdot_final), tuple(position_final),
                    tuple(quaternion_final), tuple(twist_final), tuple(ee_final),
                    "DYNAMICS_ADVANCED_SYNTHETIC_DIAGNOSTIC",
                )
                assessment = state_evolution_assessment(state, after)
                if not assessment["accepted"]:
                    raise RuntimeError("DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY")
                return after, assessment

        backend = RegisteredSyntheticBackend()

        def abort_result(*, action: DiagnosticAction, state: DiagnosticState, reason: str, capability_consumed: bool, count_before: int) -> CoordinatorResult:
            return CoordinatorResult(
                DiagnosticAction.abort() if not action.is_abort else action,
                state, state, reason, "BACKEND_NOT_INVOKED",
                state_evolution_assessment(state, state), capability_consumed,
                count_before, invocation_count(),
            )

        def execute(*, action: DiagnosticAction, state: DiagnosticState, generalized_effort: Sequence[float], step_s: float, steps: int, context: Mapping[str, object], gate_snapshot: Mapping[str, object], capability: DiagnosticCapability | None, shield: DiagnosticShield, target_policy_fixture: Mapping[str, object], mission_veto_receipt: VetoReceipt | None) -> CoordinatorResult:
            count_before = invocation_count()
            try:
                expected_context = build_execution_context(
                    run_id=str(context.get("run_id", "")), state=state,
                    generalized_effort=generalized_effort, step_s=step_s, steps=steps,
                    target_policy_fixture=target_policy_fixture,
                )
            except (TypeError, ValueError, OverflowError):
                return abort_result(action=action, state=state, reason="COORDINATOR_CONTEXT_UNKNOWN_FAIL_CLOSED", capability_consumed=False, count_before=count_before)
            if dict(context) != expected_context:
                return abort_result(action=action, state=state, reason="COORDINATOR_CONTEXT_STATE_EFFORT_OR_POLICY_MISMATCH", capability_consumed=False, count_before=count_before)

            if dict(target_policy_fixture) == synthetic_non_debris_policy_fixture():
                if mission_veto_receipt is not None:
                    return abort_result(action=action, state=state, reason="SYNTHETIC_POLICY_UNEXPECTED_VETO_RECEIPT", capability_consumed=False, count_before=count_before)
            elif (
                target_policy_fixture.get("schema") == "SIM13_V4_DEBRIS_VETO_POLICY_FIXTURE_V1"
                and target_policy_fixture.get("policy_id") == "REQUIRE_HASH_BOUND_SIM10_VETO_BEFORE_BACKEND"
                and target_policy_fixture.get("mission_veto_required") is True
            ):
                try:
                    target_mapping = target_policy_fixture.get("target")
                    if not isinstance(target_mapping, Mapping):
                        raise ValueError("target mapping absent")
                    target = TargetRequest(
                        str(target_mapping.get("target_id", "")),
                        target_mapping.get("target_mass_kg"),  # type: ignore[arg-type]
                        target_mapping.get("tumble_rate_dps"),  # type: ignore[arg-type]
                    )
                    veto = Sim10MissionVeto().decide(
                        action=action, gate_snapshot=gate_snapshot,
                        target=target, receipt=mission_veto_receipt,
                    )
                except (TypeError, ValueError, OverflowError):
                    return abort_result(action=action, state=state, reason="MISSION_POLICY_OR_VETO_UNKNOWN_FAIL_CLOSED", capability_consumed=False, count_before=count_before)
                if not veto.allowed:
                    return abort_result(action=action, state=state, reason=veto.reason_code, capability_consumed=False, count_before=count_before)
                return abort_result(action=action, state=state, reason="DEBRIS_POLICY_UNEXPECTED_ALLOW_FAIL_CLOSED", capability_consumed=False, count_before=count_before)
            else:
                return abort_result(action=action, state=state, reason="TARGET_POLICY_UNKNOWN_FAIL_CLOSED", capability_consumed=False, count_before=count_before)

            admission = shield.authorize_and_consume(
                action=action, context=context, gate_snapshot=gate_snapshot,
                capability=capability,
            )
            if not admission.allowed or admission.consumed_nonce is None:
                return abort_result(action=action, state=state, reason=admission.reason_code, capability_consumed=False, count_before=count_before)
            bindings = {
                "coordinator_id": COORDINATOR_ID,
                "backend_id": BACKEND_ID,
                "action_sha256": canonical_digest(action.as_dict()),
                "context_sha256": canonical_digest(context),
                "gate_snapshot_sha256": canonical_digest(gate_snapshot),
                "target_policy_sha256": canonical_digest(target_policy_fixture),
                "capability_nonce": admission.consumed_nonce,
            }
            invocation = register(bindings)
            try:
                after, assessment = backend.advance(
                    invocation=invocation, bindings=bindings, state=state,
                    generalized_effort=generalized_effort, step_s=step_s, steps=steps,
                )
            except (PermissionError, RuntimeError, TypeError, ValueError) as exc:
                return abort_result(action=action, state=state, reason=f"COORDINATOR_BACKEND_FAIL_CLOSED:{type(exc).__name__}:{exc}", capability_consumed=True, count_before=count_before)
            return CoordinatorResult(
                action, state, after,
                "COORDINATOR_POLICY_SHIELD_AND_INVOCATION_ACCEPTED",
                "SYNTHETIC_V3_REDUCED_DYNAMICS_ADVANCED", assessment, True,
                count_before, invocation_count(),
            )

        def security_probe() -> dict[str, object]:
            bindings = {"probe": "OPAQUE_INVOCATION_SECURITY", "coordinator_id": COORDINATOR_ID}
            try:
                OpaqueInvocation()
            except TypeError as exc:
                direct_construct_reason = str(exc)
            else:
                direct_construct_reason = "DIRECT_CONSTRUCTION_ESCAPED"
            raw = object.__new__(OpaqueInvocation)
            raw_ok, raw_reason = redeem(raw, bindings)
            original = register(bindings)
            try:
                copied = copy(original)
            except TypeError:
                copy_constructor_rejected = True
            else:
                copy_constructor_rejected = False
                copied_ok, _ = redeem(copied, bindings)
                if copied_ok:
                    copy_constructor_rejected = False
            cloned = object.__new__(OpaqueInvocation)
            object.__setattr__(cloned, "_handle", getattr(original, "_handle"))
            clone_ok, clone_reason = redeem(cloned, bindings)
            original_ok, original_reason = redeem(original, bindings)
            replay_ok, replay_reason = redeem(original, bindings)
            private_globals = sorted(
                name for name in globals() if name.startswith("_")
                and any(token in name.lower() for token in ("factory_token", "register_invocation", "issue_invocation"))
            )
            passed = (
                direct_construct_reason == "OPAQUE_INVOCATION_DIRECT_CONSTRUCTION_REJECTED"
                and raw_ok is False and raw_reason == "OPAQUE_INVOCATION_UNREGISTERED"
                and copy_constructor_rejected is True
                and clone_ok is False and clone_reason == "OPAQUE_INVOCATION_OBJECT_IDENTITY_MISMATCH"
                and original_ok is True and original_reason == "OPAQUE_INVOCATION_REDEEMED_ONCE"
                and replay_ok is False and replay_reason == "OPAQUE_INVOCATION_REPLAY_REJECTED"
                and private_globals == []
            )
            return {
                "direct_construction_reason": direct_construct_reason,
                "object_new_accepted": raw_ok, "object_new_reason": raw_reason,
                "copy_constructor_rejected": copy_constructor_rejected,
                "manual_clone_accepted": clone_ok, "manual_clone_reason": clone_reason,
                "registered_original_accepted_once": original_ok,
                "registered_original_reason": original_reason,
                "replay_accepted": replay_ok, "replay_reason": replay_reason,
                "module_private_forge_primitives": private_globals,
                "cooperative_api_boundary": "Python in-process malicious monkeypatch/closure introspection is outside this diagnostic capability boundary",
                "passed": passed,
            }

        self._execute = execute
        self._security_probe = security_probe
        self._invocation_count = invocation_count

    def execute(self, **kwargs: object) -> CoordinatorResult:
        return self._execute(**kwargs)  # type: ignore[arg-type]

    def opaque_invocation_security_probe(self) -> dict[str, object]:
        return self._security_probe()

    @property
    def backend_invocation_count(self) -> int:
        return self._invocation_count()


def phase_only_negative_control(before: DiagnosticState) -> dict[str, object]:
    return state_evolution_assessment(before, replace(before, phase="FAKE_PHASE_ADVANCE_WITHOUT_PHYSICS"))


__all__ = (
    "BACKEND_ID", "BACKEND_SCOPE", "COORDINATOR_ID", "CoordinatorResult",
    "DiagnosticExecutionCoordinator", "DiagnosticState",
    "GENERALIZED_COORDINATE_UNITS", "GENERALIZED_EFFORT_UNITS",
    "GENERALIZED_RATE_UNITS", "OpaqueInvocation", "PRISMATIC_CHANNELS",
    "REVOLUTE_CHANNELS", "SyntheticCapabilityBackend", "build_execution_context",
    "debris_veto_policy_fixture", "effort_record", "initial_diagnostic_state",
    "nominal_generalized_effort", "phase_only_negative_control",
    "state_evolution_assessment", "synthetic_non_debris_policy_fixture",
)
