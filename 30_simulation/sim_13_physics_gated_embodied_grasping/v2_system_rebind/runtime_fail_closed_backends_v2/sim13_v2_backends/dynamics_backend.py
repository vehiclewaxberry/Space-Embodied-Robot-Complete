"""Non-ABORT joint/base/end-effector state-evolution backend (WO-NC18).

This backend integrates the emitted Unified R2 system URDF (19 link / 18
joint / 8 movable DOF, hash-pinned) with the ``sim13_v2.free_floating_dynamics``
tree kernel and advances a free-floating state under generalized effort:

- joints: 6 revolute + 2 prismatic coordinates (rad, rad/s, N*m / m, m/s, N);
- base: inertial position, body-to-inertial quaternion, body twist, updated
  through the zero-momentum mechanical connection;
- end effector: centroid of ``gripper_link``/``gripper_left``/``gripper_right``
  origins, expressed inertially.

The reduced-dynamics integrator follows the established Schur-complement +
centered Richardson derivative + fixed-step RK4 pattern of the project V3
diagnostic, re-implemented here so the production-intent backend owns its
source.  A step that changes only the task phase without any physical state
update is rejected with ``DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY``.

Fail-closed loading: the emitted URDF and its execution receipt are opened
read-only and must match the pinned byte counts and SHA-256 digests exactly;
any absence, drift, or failed receipt check raises :class:`BackendSourceError`.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .canonical import canonical_digest, sha256_bytes


BACKEND_ID = "SIM13_V2_UNIFIED_R2_FREE_FLOATING_DYNAMICS_BACKEND_V1"
BACKEND_SCOPE = (
    "ZERO_MOMENTUM_FREE_FLOATING_STATE_EVOLUTION_NOT_CONTACT_NOT_PRODUCTION_AUTHORIZED"
)
URDF_RELATIVE_PATH = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "unified_r2_digital_prototype_prebind/generated_v2/"
    "unified_r2_c01_no_route_c_sim_candidate_v2.urdf"
)
URDF_RECEIPT_RELATIVE_PATH = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "unified_r2_digital_prototype_prebind/generated_v2/"
    "UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json"
)
EXPECTED_URDF_BYTES = 17191
EXPECTED_URDF_SHA256 = (
    "D84AA23CE98A2A9C697B1F32E433C01C3F0AE3BD0B5C56EF9A218DD88911CBDA"
)
EXPECTED_RECEIPT_BYTES = 2891
EXPECTED_RECEIPT_SHA256 = (
    "957CA67D7BCC2CB591DF2442F24532CA3DAE24F358FC69BF390AC1A20F6F021E"
)
EXPECTED_TOTAL_MASS_KG = 31.022864807342987
REVOLUTE_CHANNELS = tuple(range(6))
PRISMATIC_CHANNELS = (6, 7)
GENERALIZED_EFFORT_UNITS = ("N*m",) * 6 + ("N",) * 2
GENERALIZED_COORDINATE_UNITS = ("rad",) * 6 + ("m",) * 2
GENERALIZED_RATE_UNITS = ("rad/s",) * 6 + ("m/s",) * 2
REVOLUTE_DIFFERENCE_STEP_RAD = 2.0e-5
PRISMATIC_DIFFERENCE_STEP_M = 2.0e-6
STATE_CHANGE_EPSILON = 1.0e-12
MOMENTUM_RESIDUAL_LIMIT = 1.0e-9


class BackendSourceError(RuntimeError):
    """Raised when a pinned backend source is absent or hash-drifted."""


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


def _quat_product(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array(
        (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        )
    )


@dataclass(frozen=True)
class BackendState:
    """Complete non-ABORT state: joints, base, and end-effector."""

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

    def as_dict(self) -> dict[str, Any]:
        return {
            "q_mixed_rad_m": list(self.q_mixed_rad_m),
            "qdot_mixed_rad_s_m_s": list(self.qdot_mixed_rad_s_m_s),
            "base_position_inertial_m": list(self.base_position_inertial_m),
            "base_quaternion_body_to_inertial_wxyz": list(
                self.base_quaternion_body_to_inertial_wxyz
            ),
            "base_twist_body_mixed_m_s_rad_s": list(
                self.base_twist_body_mixed_m_s_rad_s
            ),
            "ee_centroid_inertial_m": list(self.ee_centroid_inertial_m),
            "phase": self.phase,
        }


def state_evolution_assessment(
    before: BackendState, after: BackendState
) -> dict[str, Any]:
    """Accept only a real physical state change; phase-only steps fail."""

    q_before, q_after = np.asarray(before.q_mixed_rad_m), np.asarray(after.q_mixed_rad_m)
    qdot_before = np.asarray(before.qdot_mixed_rad_s_m_s)
    qdot_after = np.asarray(after.qdot_mixed_rad_s_m_s)
    quat_before = np.asarray(before.base_quaternion_body_to_inertial_wxyz)
    quat_after = np.asarray(after.base_quaternion_body_to_inertial_wxyz)
    alignment = abs(float(quat_before @ quat_after))
    orientation_delta_rad = 2.0 * math.acos(min(1.0, max(-1.0, alignment)))
    deltas = {
        "revolute_q_max_abs_rad": float(np.max(np.abs(q_after[:6] - q_before[:6]))),
        "prismatic_q_max_abs_m": float(np.max(np.abs(q_after[6:] - q_before[6:]))),
        "revolute_qdot_max_abs_rad_s": float(
            np.max(np.abs(qdot_after[:6] - qdot_before[:6]))
        ),
        "prismatic_qdot_max_abs_m_s": float(
            np.max(np.abs(qdot_after[6:] - qdot_before[6:]))
        ),
        "base_position_norm_m": float(
            np.linalg.norm(
                np.asarray(after.base_position_inertial_m)
                - np.asarray(before.base_position_inertial_m)
            )
        ),
        "base_orientation_angle_rad": orientation_delta_rad,
        "base_twist_linear_norm_m_s": float(
            np.linalg.norm(
                np.asarray(after.base_twist_body_mixed_m_s_rad_s)[:3]
                - np.asarray(before.base_twist_body_mixed_m_s_rad_s)[:3]
            )
        ),
        "base_twist_angular_norm_rad_s": float(
            np.linalg.norm(
                np.asarray(after.base_twist_body_mixed_m_s_rad_s)[3:]
                - np.asarray(before.base_twist_body_mixed_m_s_rad_s)[3:]
            )
        ),
        "ee_centroid_position_norm_m": float(
            np.linalg.norm(
                np.asarray(after.ee_centroid_inertial_m)
                - np.asarray(before.ee_centroid_inertial_m)
            )
        ),
    }
    physical_changed = any(value > STATE_CHANGE_EPSILON for value in deltas.values())
    return {
        "physical_state_changed": physical_changed,
        "phase_changed": before.phase != after.phase,
        "accepted": physical_changed,
        "reason_code": (
            "REAL_NUMERICAL_STATE_EVOLUTION_DETECTED"
            if physical_changed
            else "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY"
        ),
        "deltas": deltas,
        "base_linear_and_angular_twist_audited_separately": True,
        "heterogeneous_global_norm_used": False,
    }


class UnifiedR2DynamicsBackend:
    """Hash-bound Unified R2 free-floating state-evolution backend."""

    def __init__(self, *, project_root: str | Path) -> None:
        root = Path(project_root).resolve()
        self.project_root = root
        self.urdf_path = (root / URDF_RELATIVE_PATH).resolve()
        self.urdf_receipt_path = (root / URDF_RECEIPT_RELATIVE_PATH).resolve()
        urdf_bytes, receipt_document = self._load_and_verify_sources()
        self.urdf_bytes = urdf_bytes
        self.urdf_sha256 = sha256_bytes(urdf_bytes)
        self.urdf_receipt = receipt_document
        # Deferred import: the backend module must import cleanly on hosts that
        # only inspect schemas, but construction always requires the kernel.
        from sim13_v2.free_floating_dynamics import URDFTreeDynamics
        from sim13_v2.system_model import SystemModel

        artifact_root = self.urdf_path.parent
        self.system_model = SystemModel.from_xml_bytes(
            urdf_bytes, artifact_root=artifact_root
        )
        self.tree = URDFTreeDynamics(urdf_bytes)
        if abs(self.tree.total_mass_kg - EXPECTED_TOTAL_MASS_KG) > 1.0e-12:
            raise BackendSourceError("UNIFIED_R2_TOTAL_MASS_DRIFT")
        self.dof = self.tree.movable_dof
        self.revolute_indices = tuple(
            index
            for index, joint in enumerate(self.tree.movable_joints)
            if joint.joint_type == "revolute"
        )
        self.prismatic_indices = tuple(
            index
            for index, joint in enumerate(self.tree.movable_joints)
            if joint.joint_type == "prismatic"
        )

    def _load_and_verify_sources(self) -> tuple[bytes, Mapping[str, Any]]:
        if not self.urdf_path.is_file():
            raise BackendSourceError("UNIFIED_R2_URDF_SOURCE_MISSING")
        urdf_bytes = self.urdf_path.read_bytes()
        if (
            len(urdf_bytes) != EXPECTED_URDF_BYTES
            or sha256_bytes(urdf_bytes) != EXPECTED_URDF_SHA256
        ):
            raise BackendSourceError("UNIFIED_R2_URDF_SOURCE_HASH_DRIFT")
        if not self.urdf_receipt_path.is_file():
            raise BackendSourceError("UNIFIED_R2_URDF_EXECUTION_RECEIPT_MISSING")
        receipt_bytes = self.urdf_receipt_path.read_bytes()
        if (
            len(receipt_bytes) != EXPECTED_RECEIPT_BYTES
            or sha256_bytes(receipt_bytes) != EXPECTED_RECEIPT_SHA256
        ):
            raise BackendSourceError("UNIFIED_R2_URDF_EXECUTION_RECEIPT_HASH_DRIFT")
        try:
            receipt = json.loads(receipt_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackendSourceError("UNIFIED_R2_URDF_EXECUTION_RECEIPT_MALFORMED") from exc
        output = receipt.get("outputs", {}).get("urdf", {}) if isinstance(receipt, Mapping) else {}
        if (
            receipt.get("schema") != "UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2"
            or receipt.get("all_checks_pass") is not True
            or output.get("sha256") != EXPECTED_URDF_SHA256
            or output.get("bytes") != EXPECTED_URDF_BYTES
        ):
            raise BackendSourceError("UNIFIED_R2_URDF_EXECUTION_RECEIPT_CONTENT_DRIFT")
        return urdf_bytes, receipt

    # ---- reduced zero-momentum dynamics (Schur complement + RK4) ----

    def _step_for_coordinate(self, index: int) -> float:
        if index in self.revolute_indices:
            return REVOLUTE_DIFFERENCE_STEP_RAD
        return PRISMATIC_DIFFERENCE_STEP_M

    def reduced_mass_matrix(self, q: Sequence[float]) -> np.ndarray:
        qv = _finite_vector(q, self.dof, "generalized_coordinates")
        blocks = self.tree.mass_matrix_blocks(qv)
        try:
            connection_term = blocks.Hmb @ np.linalg.solve(blocks.Hbb, blocks.Hbm)
        except np.linalg.LinAlgError as exc:
            raise ValueError("singular Hbb in reduced mass assembly") from exc
        reduced = blocks.Hmm - connection_term
        reduced = 0.5 * (reduced + reduced.T)
        if not np.all(np.isfinite(reduced)) or np.min(np.linalg.eigvalsh(reduced)) <= 0.0:
            raise ValueError("reduced mass matrix is not numerically positive definite")
        return reduced

    def mechanical_connection(self, q: Sequence[float]) -> np.ndarray:
        blocks = self.tree.mass_matrix_blocks(
            _finite_vector(q, self.dof, "generalized_coordinates")
        )
        try:
            return -np.linalg.solve(blocks.Hbb, blocks.Hbm)
        except np.linalg.LinAlgError as exc:
            raise ValueError("singular Hbb in mechanical connection") from exc

    def _centered_derivative(self, function, q: np.ndarray, index: int) -> np.ndarray:
        step = self._step_for_coordinate(index)
        plus = q.copy()
        minus = q.copy()
        plus[index] += step
        minus[index] -= step
        coarse = (function(plus) - function(minus)) / (2.0 * step)
        fine_step = 0.5 * step
        plus = q.copy()
        minus = q.copy()
        plus[index] += fine_step
        minus[index] -= fine_step
        fine = (function(plus) - function(minus)) / (2.0 * fine_step)
        return (4.0 * fine - coarse) / 3.0

    def _reduced_mass_derivatives(self, q: np.ndarray) -> np.ndarray:
        derivatives = np.empty((self.dof, self.dof, self.dof))
        for index in range(self.dof):
            derivatives[index] = self._centered_derivative(
                self.reduced_mass_matrix, q, index
            )
        return derivatives

    def _bias_effort(self, q: np.ndarray, rates: np.ndarray) -> np.ndarray:
        derivatives = self._reduced_mass_derivatives(q)
        mass_rate = np.tensordot(rates, derivatives, axes=(0, 0))
        energy_gradient = np.array(
            [rates @ derivatives[index] @ rates for index in range(self.dof)]
        )
        return mass_rate @ rates - 0.5 * energy_gradient

    def _solve_acceleration(
        self, q: np.ndarray, rates: np.ndarray, effort: np.ndarray
    ) -> np.ndarray:
        reduced = self.reduced_mass_matrix(q)
        bias = self._bias_effort(q, rates)
        try:
            return np.linalg.solve(reduced, effort - bias)
        except np.linalg.LinAlgError as exc:
            raise ValueError("singular reduced mass matrix") from exc

    def _state_derivative(self, state: np.ndarray, effort: np.ndarray) -> np.ndarray:
        n = self.dof
        q = state[:n]
        rates = state[n : 2 * n]
        acceleration = self._solve_acceleration(q, rates, effort)
        base_twist = self.mechanical_connection(q) @ rates
        quaternion = state[2 * n + 3 : 2 * n + 7]
        norm = float(np.linalg.norm(quaternion))
        if norm <= 0.0:
            raise ValueError("base quaternion norm must be nonzero")
        quaternion = quaternion / norm
        rotation = _quat_rotation_body_to_inertial(quaternion)
        position_rate = rotation @ base_twist[:3]
        quaternion_rate = 0.5 * _quat_product(
            quaternion, np.array((0.0, *base_twist[3:]))
        )
        return np.concatenate((rates, acceleration, position_rate, quaternion_rate))

    def ee_centroid_inertial(
        self,
        q: Sequence[float],
        base_position_inertial_m: Sequence[float],
        base_quaternion_body_to_inertial_wxyz: Sequence[float],
    ) -> np.ndarray:
        transforms, _ = self.tree.forward_kinematics(q)
        local = np.mean(
            np.stack(
                (
                    transforms["gripper_link"][:3, 3],
                    transforms["gripper_left"][:3, 3],
                    transforms["gripper_right"][:3, 3],
                )
            ),
            axis=0,
        )
        rotation = _quat_rotation_body_to_inertial(base_quaternion_body_to_inertial_wxyz)
        return _finite_vector(base_position_inertial_m, 3, "base_position") + rotation @ local

    def initial_state(self) -> BackendState:
        q = np.array((0.08, -0.04, 0.05, 0.02, -0.03, 0.06, 0.005, -0.004))
        qdot = np.zeros(self.dof)
        position = np.zeros(3)
        quaternion = np.array((1.0, 0.0, 0.0, 0.0))
        ee = self.ee_centroid_inertial(q, position, quaternion)
        return BackendState(
            tuple(q),
            tuple(qdot),
            tuple(position),
            tuple(quaternion),
            (0.0,) * 6,
            tuple(ee),
            "READY_NON_ABORT_STATE_EVOLUTION",
        )

    def nominal_generalized_effort(self) -> tuple[float, ...]:
        """Six revolute torques [N*m] then two prismatic forces [N]."""

        return (0.020, -0.015, 0.010, 0.008, -0.006, 0.005, 0.012, -0.009)

    def advance(
        self,
        state: BackendState,
        *,
        generalized_effort: Sequence[float],
        step_s: float,
        steps: int,
    ) -> tuple[BackendState, Mapping[str, Any], Mapping[str, Any]]:
        """Advance the free-floating state; return (after, assessment, audit)."""

        if not math.isfinite(step_s) or step_s <= 0.0:
            raise ValueError("step_s must be positive and finite")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise ValueError("steps must be a positive integer")
        effort = _finite_vector(generalized_effort, self.dof, "generalized_effort")
        n = self.dof
        q0 = _finite_vector(state.q_mixed_rad_m, n, "q")
        rates0 = _finite_vector(state.qdot_mixed_rad_s_m_s, n, "qdot")
        position0 = _finite_vector(state.base_position_inertial_m, 3, "base_position")
        quaternion0 = _finite_vector(
            state.base_quaternion_body_to_inertial_wxyz, 4, "base_quaternion"
        )
        norm = float(np.linalg.norm(quaternion0))
        if norm <= 0.0:
            raise ValueError("base quaternion norm must be nonzero")
        quaternion0 = quaternion0 / norm

        state_vector = np.concatenate((q0, rates0, position0, quaternion0))
        max_linear_residual = 0.0
        max_angular_residual = 0.0
        for _ in range(steps):
            k1 = self._state_derivative(state_vector, effort)
            k2 = self._state_derivative(state_vector + 0.5 * step_s * k1, effort)
            k3 = self._state_derivative(state_vector + 0.5 * step_s * k2, effort)
            k4 = self._state_derivative(state_vector + step_s * k3, effort)
            state_vector = state_vector + (step_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
            quat_slice = slice(2 * n + 3, 2 * n + 7)
            state_vector[quat_slice] /= np.linalg.norm(state_vector[quat_slice])

        q_final = state_vector[:n]
        rates_final = state_vector[n : 2 * n]
        position_final = state_vector[2 * n : 2 * n + 3]
        quaternion_final = state_vector[2 * n + 3 : 2 * n + 7]
        twist_final = self.mechanical_connection(q_final) @ rates_final
        momentum = self.tree.momentum(q_final, twist_final, rates_final)
        max_linear_residual = float(np.linalg.norm(momentum.linear_root_kg_m_s))
        max_angular_residual = float(
            np.linalg.norm(momentum.angular_about_root_kg_m2_s)
        )
        ee_final = self.ee_centroid_inertial(q_final, position_final, quaternion_final)
        after = BackendState(
            tuple(q_final),
            tuple(rates_final),
            tuple(position_final),
            tuple(quaternion_final),
            tuple(twist_final),
            tuple(ee_final),
            "DYNAMICS_ADVANCED_NON_ABORT",
        )
        assessment = state_evolution_assessment(state, after)
        audit = {
            "backend_id": BACKEND_ID,
            "backend_scope": BACKEND_SCOPE,
            "step_s": float(step_s),
            "steps": int(steps),
            "generalized_effort_units": list(GENERALIZED_EFFORT_UNITS),
            "generalized_coordinate_units": list(GENERALIZED_COORDINATE_UNITS),
            "generalized_rate_units": list(GENERALIZED_RATE_UNITS),
            "linear_momentum_residual_Ns": max_linear_residual,
            "angular_momentum_residual_Nms": max_angular_residual,
            "momentum_residual_limit": MOMENTUM_RESIDUAL_LIMIT,
            "momentum_conserved_within_limit": bool(
                max_linear_residual <= MOMENTUM_RESIDUAL_LIMIT
                and max_angular_residual <= MOMENTUM_RESIDUAL_LIMIT
            ),
        }
        return after, assessment, audit

    def source_manifest(self) -> dict[str, Any]:
        return {
            "backend_id": BACKEND_ID,
            "backend_scope": BACKEND_SCOPE,
            "urdf": {
                "path": URDF_RELATIVE_PATH,
                "bytes": EXPECTED_URDF_BYTES,
                "sha256": EXPECTED_URDF_SHA256,
            },
            "urdf_execution_receipt": {
                "path": URDF_RECEIPT_RELATIVE_PATH,
                "bytes": EXPECTED_RECEIPT_BYTES,
                "sha256": EXPECTED_RECEIPT_SHA256,
            },
            "model": {
                "links": self.tree.link_count,
                "joints": self.tree.joint_count,
                "physical_links": self.tree.physical_link_count,
                "frame_only_links": self.tree.frame_only_link_count,
                "movable_dof": self.dof,
                "total_mass_kg": self.tree.total_mass_kg,
            },
        }


class PhaseOnlyBackend:
    """Negative-control fixture: changes only the task phase, never physics."""

    def __init__(self, backend: UnifiedR2DynamicsBackend) -> None:
        self._backend = backend

    def advance(self, state: BackendState, **_: Any) -> BackendState:
        return BackendState(
            state.q_mixed_rad_m,
            state.qdot_mixed_rad_s_m_s,
            state.base_position_inertial_m,
            state.base_quaternion_body_to_inertial_wxyz,
            state.base_twist_body_mixed_m_s_rad_s,
            state.ee_centroid_inertial_m,
            "FAKE_PHASE_ADVANCE_WITHOUT_PHYSICS",
        )


def build_validation_receipt(backend: UnifiedR2DynamicsBackend) -> dict[str, Any]:
    """Nominal non-ABORT advance plus the phase-only failure check."""

    initial = backend.initial_state()
    after, assessment, audit = backend.advance(
        initial,
        generalized_effort=backend.nominal_generalized_effort(),
        step_s=1.0e-3,
        steps=10,
    )
    phase_only = PhaseOnlyBackend(backend).advance(initial)
    phase_assessment = state_evolution_assessment(initial, phase_only)
    checks = {
        "nominal_state_evolution_accepted": assessment["accepted"] is True,
        "momentum_conserved_within_limit": audit["momentum_conserved_within_limit"] is True,
        "phase_only_step_rejected": (
            phase_assessment["accepted"] is False
            and phase_assessment["reason_code"]
            == "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY"
        ),
    }
    return {
        "schema": "SIM13_V2_DYNAMICS_BACKEND_VALIDATION_RECEIPT_V1",
        "backend_id": BACKEND_ID,
        "backend_scope": BACKEND_SCOPE,
        "source_manifest": backend.source_manifest(),
        "initial_state_sha256": canonical_digest(initial.as_dict()),
        "advanced_state_sha256": canonical_digest(after.as_dict()),
        "state_evolution": dict(assessment),
        "integration_audit": dict(audit),
        "phase_only_negative_control": {
            "reason_code": phase_assessment["reason_code"],
            "accepted": phase_assessment["accepted"],
        },
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


__all__ = [
    "BACKEND_ID",
    "BACKEND_SCOPE",
    "BackendSourceError",
    "BackendState",
    "EXPECTED_RECEIPT_BYTES",
    "EXPECTED_RECEIPT_SHA256",
    "EXPECTED_TOTAL_MASS_KG",
    "EXPECTED_URDF_BYTES",
    "EXPECTED_URDF_SHA256",
    "GENERALIZED_EFFORT_UNITS",
    "MOMENTUM_RESIDUAL_LIMIT",
    "PhaseOnlyBackend",
    "STATE_CHANGE_EPSILON",
    "URDF_RECEIPT_RELATIVE_PATH",
    "URDF_RELATIVE_PATH",
    "UnifiedR2DynamicsBackend",
    "build_validation_receipt",
    "state_evolution_assessment",
]
