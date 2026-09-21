"""Bounded free-floating rigid-body diagnostic kernel.

This module closes total linear and angular momentum across one idealized,
instantaneous rigid-lock event. It does not calculate contact forces, impulse
history, compliance, friction or flexible response.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

from .interface_loader import DiagnosticAnchor, DiagnosticRigidBody


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
Matrix3 = tuple[Vector3, Vector3, Vector3]


def _vadd(left: Vector3, right: Vector3) -> Vector3:
    return tuple(left[i] + right[i] for i in range(3))  # type: ignore[return-value]


def _vsub(left: Vector3, right: Vector3) -> Vector3:
    return tuple(left[i] - right[i] for i in range(3))  # type: ignore[return-value]


def _vscale(value: Vector3, factor: float) -> Vector3:
    return tuple(item * factor for item in value)  # type: ignore[return-value]


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _norm(value: Vector3) -> float:
    return math.sqrt(math.fsum(item * item for item in value))


def _madd(*matrices: Matrix3) -> Matrix3:
    return tuple(
        tuple(math.fsum(matrix[i][j] for matrix in matrices) for j in range(3))
        for i in range(3)
    )  # type: ignore[return-value]


def _mvec(matrix: Matrix3, vector: Vector3) -> Vector3:
    return tuple(
        math.fsum(matrix[i][j] * vector[j] for j in range(3))
        for i in range(3)
    )  # type: ignore[return-value]


def _mmul(left: Matrix3, right: Matrix3) -> Matrix3:
    return tuple(
        tuple(
            math.fsum(left[i][k] * right[k][j] for k in range(3))
            for j in range(3)
        )
        for i in range(3)
    )  # type: ignore[return-value]


def _transpose(matrix: Matrix3) -> Matrix3:
    return tuple(
        tuple(matrix[j][i] for j in range(3))
        for i in range(3)
    )  # type: ignore[return-value]


def _quaternion_rotation_matrix(quaternion: Quaternion) -> Matrix3:
    x, y, z, w = quaternion
    return (
        (
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y - z * w),
            2.0 * (x * z + y * w),
        ),
        (
            2.0 * (x * y + z * w),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z - x * w),
        ),
        (
            2.0 * (x * z - y * w),
            2.0 * (y * z + x * w),
            1.0 - 2.0 * (x * x + y * y),
        ),
    )


def _parallel_axis(mass_kg: float, offset_m: Vector3) -> Matrix3:
    squared_radius = math.fsum(item * item for item in offset_m)
    return tuple(
        tuple(
            mass_kg
            * (
                (squared_radius if i == j else 0.0)
                - offset_m[i] * offset_m[j]
            )
            for j in range(3)
        )
        for i in range(3)
    )  # type: ignore[return-value]


def _solve3(matrix: Matrix3, rhs: Vector3) -> Vector3:
    augmented = [list(matrix[i]) + [rhs[i]] for i in range(3)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= 1e-15:
            raise ValueError("combined inertia tensor is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        augmented[column] = [item / pivot_value for item in augmented[column]]
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][index] - factor * augmented[column][index]
                for index in range(4)
            ]
    result = tuple(augmented[row][3] for row in range(3))
    if not all(math.isfinite(item) for item in result):
        raise ValueError("combined angular velocity is non-finite")
    return result  # type: ignore[return-value]


def _quaternion_multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    output = (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )
    magnitude = math.sqrt(math.fsum(item * item for item in output))
    return tuple(item / magnitude for item in output)  # type: ignore[return-value]


def _integrate_quaternion(
    quaternion: Quaternion,
    angular_velocity_radps: Vector3,
    timestep_s: float,
) -> Quaternion:
    speed = _norm(angular_velocity_radps)
    if speed == 0.0:
        return quaternion
    axis = _vscale(angular_velocity_radps, 1.0 / speed)
    half_angle = 0.5 * speed * timestep_s
    sine = math.sin(half_angle)
    delta = (
        axis[0] * sine,
        axis[1] * sine,
        axis[2] * sine,
        math.cos(half_angle),
    )
    return _quaternion_multiply(quaternion, delta)


@dataclass(frozen=True)
class RigidBodyState:
    mass_kg: float
    inertia_about_com_kg_m2: Matrix3
    position_m: Vector3
    quaternion_xyzw: Quaternion
    linear_velocity_mps: Vector3
    angular_velocity_radps: Vector3


def _world_inertia(body: RigidBodyState) -> Matrix3:
    rotation = _quaternion_rotation_matrix(body.quaternion_xyzw)
    return _mmul(
        _mmul(rotation, body.inertia_about_com_kg_m2),
        _transpose(rotation),
    )


@dataclass(frozen=True)
class CaptureClosureReport:
    model_scope: str
    total_mass_kg: float
    combined_center_of_mass_m: Vector3
    combined_linear_velocity_mps: Vector3
    combined_angular_velocity_radps: Vector3
    combined_inertia_about_com_kg_m2: Matrix3
    linear_momentum_before_kg_mps: Vector3
    linear_momentum_after_kg_mps: Vector3
    angular_momentum_before_kg_m2ps: Vector3
    angular_momentum_after_kg_m2ps: Vector3
    linear_momentum_residual_kg_mps: Vector3
    angular_momentum_residual_kg_m2ps: Vector3
    linear_residual_norm_kg_mps: float
    angular_residual_norm_kg_m2ps: float
    contact_force_computed: bool
    contact_impulse_history_computed: bool


def _body_from_fixture(body: DiagnosticRigidBody) -> RigidBodyState:
    return RigidBodyState(
        mass_kg=body.mass_kg,
        inertia_about_com_kg_m2=body.inertia_about_com_kg_m2,
        position_m=body.initial_position_m,
        quaternion_xyzw=(0.0, 0.0, 0.0, 1.0),
        linear_velocity_mps=body.initial_linear_velocity_mps,
        angular_velocity_radps=body.initial_angular_velocity_radps,
    )


class FreeFloatingMomentumBackend:
    """Two-body SI-unit diagnostic backend with an ideal rigid capture event."""

    model_scope = (
        "IDEAL_RIGID_LOCK_MOMENTUM_CLOSURE_NOT_CONTACT_FORCE_OR_FLEXIBLE_DYNAMICS"
    )

    def __init__(
        self,
        service_fixture: DiagnosticRigidBody,
        target_anchor: DiagnosticAnchor,
        *,
        timestep_s: float = 0.05,
    ) -> None:
        if not math.isfinite(timestep_s) or timestep_s <= 0.0:
            raise ValueError("timestep_s must be finite and positive")
        self.timestep_s = float(timestep_s)
        self.anchor_id = target_anchor.anchor_id
        self.target_kind = target_anchor.target_kind
        self.service = _body_from_fixture(service_fixture)
        self.target = _body_from_fixture(target_anchor.body)
        self.simulation_time_s = 0.0
        self.capture_report: CaptureClosureReport | None = None

    @property
    def captured(self) -> bool:
        return self.capture_report is not None

    def advance(self) -> None:
        dt = self.timestep_s
        self.service = replace(
            self.service,
            position_m=_vadd(
                self.service.position_m,
                _vscale(self.service.linear_velocity_mps, dt),
            ),
            quaternion_xyzw=_integrate_quaternion(
                self.service.quaternion_xyzw,
                self.service.angular_velocity_radps,
                dt,
            ),
        )
        self.target = replace(
            self.target,
            position_m=_vadd(
                self.target.position_m,
                _vscale(self.target.linear_velocity_mps, dt),
            ),
            quaternion_xyzw=_integrate_quaternion(
                self.target.quaternion_xyzw,
                self.target.angular_velocity_radps,
                dt,
            ),
        )
        self.simulation_time_s += dt

    def capture(self) -> CaptureClosureReport:
        if self.capture_report is not None:
            raise RuntimeError("capture may occur only once")
        service = self.service
        target = self.target
        total_mass = service.mass_kg + target.mass_kg
        center = _vscale(
            _vadd(
                _vscale(service.position_m, service.mass_kg),
                _vscale(target.position_m, target.mass_kg),
            ),
            1.0 / total_mass,
        )
        momentum_before = _vadd(
            _vscale(service.linear_velocity_mps, service.mass_kg),
            _vscale(target.linear_velocity_mps, target.mass_kg),
        )
        combined_velocity = _vscale(momentum_before, 1.0 / total_mass)
        service_offset = _vsub(service.position_m, center)
        target_offset = _vsub(target.position_m, center)
        service_inertia_world = _world_inertia(service)
        target_inertia_world = _world_inertia(target)
        service_orbital = _cross(
            service_offset,
            _vscale(
                _vsub(service.linear_velocity_mps, combined_velocity),
                service.mass_kg,
            ),
        )
        target_orbital = _cross(
            target_offset,
            _vscale(
                _vsub(target.linear_velocity_mps, combined_velocity),
                target.mass_kg,
            ),
        )
        angular_before = _vadd(
            _vadd(
                _mvec(
                    service_inertia_world,
                    service.angular_velocity_radps,
                ),
                service_orbital,
            ),
            _vadd(
                _mvec(
                    target_inertia_world,
                    target.angular_velocity_radps,
                ),
                target_orbital,
            ),
        )
        combined_inertia = _madd(
            service_inertia_world,
            _parallel_axis(service.mass_kg, service_offset),
            target_inertia_world,
            _parallel_axis(target.mass_kg, target_offset),
        )
        combined_omega = _solve3(combined_inertia, angular_before)
        service_velocity_after = _vadd(
            combined_velocity, _cross(combined_omega, service_offset)
        )
        target_velocity_after = _vadd(
            combined_velocity, _cross(combined_omega, target_offset)
        )
        self.service = replace(
            service,
            linear_velocity_mps=service_velocity_after,
            angular_velocity_radps=combined_omega,
        )
        self.target = replace(
            target,
            linear_velocity_mps=target_velocity_after,
            angular_velocity_radps=combined_omega,
        )
        momentum_after = _vadd(
            _vscale(service_velocity_after, service.mass_kg),
            _vscale(target_velocity_after, target.mass_kg),
        )
        angular_after = _mvec(combined_inertia, combined_omega)
        linear_residual = _vsub(momentum_after, momentum_before)
        angular_residual = _vsub(angular_after, angular_before)
        self.capture_report = CaptureClosureReport(
            model_scope=self.model_scope,
            total_mass_kg=total_mass,
            combined_center_of_mass_m=center,
            combined_linear_velocity_mps=combined_velocity,
            combined_angular_velocity_radps=combined_omega,
            combined_inertia_about_com_kg_m2=combined_inertia,
            linear_momentum_before_kg_mps=momentum_before,
            linear_momentum_after_kg_mps=momentum_after,
            angular_momentum_before_kg_m2ps=angular_before,
            angular_momentum_after_kg_m2ps=angular_after,
            linear_momentum_residual_kg_mps=linear_residual,
            angular_momentum_residual_kg_m2ps=angular_residual,
            linear_residual_norm_kg_mps=_norm(linear_residual),
            angular_residual_norm_kg_m2ps=_norm(angular_residual),
            contact_force_computed=False,
            contact_impulse_history_computed=False,
        )
        return self.capture_report


def vector_is_finite(values: Iterable[float]) -> bool:
    return all(math.isfinite(float(value)) for value in values)


__all__ = [
    "CaptureClosureReport",
    "FreeFloatingMomentumBackend",
    "Matrix3",
    "Quaternion",
    "RigidBodyState",
    "Vector3",
    "vector_is_finite",
]
