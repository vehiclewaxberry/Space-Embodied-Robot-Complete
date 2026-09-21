"""Auditable synthetic 6R+2P full-floating no-contact dynamics.

This module is deliberately independent of every Unified-R2 builder and of the
Sim13 V2/V3 backends.  It supplies a hand-written synthetic analogue for an
algorithm-only Phase-A diagnostic.  It is not a production plant and it does
not implement contact.

The service generalized velocity is expressed in the inertial frame as

    nu_s = [v_base(3), omega_base(3), qdot_R(6), qdot_P(2)].

Revolute coordinates/rates/efforts use rad, rad/s and N*m.  Prismatic channels
use m, m/s and N.  A single unit must never be attached to the complete mixed
mass matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

import numpy as np


SCOPE = "SYNTHETIC_ONLY_FULL_FLOATING_NO_CONTACT_PHASE_A_DIAGNOSTIC"
CONTACT_IMPLEMENTED = False
CURRENT_SYSTEM_BOUND = False
PRODUCTION_BACKEND = False
FORMAL_NC19_CREDIT = False

JOINT_TYPES = ("R", "R", "R", "R", "R", "R", "P", "P")
JOINT_COORDINATE_UNITS = ("rad",) * 6 + ("m",) * 2
JOINT_RATE_UNITS = ("rad/s",) * 6 + ("m/s",) * 2
JOINT_EFFORT_UNITS = ("N*m",) * 6 + ("N",) * 2


class DynamicsError(ValueError):
    """Fail-closed input or numerical-contract error."""


def _array(values: Sequence[float], size: int, name: str) -> np.ndarray:
    value = np.asarray(values, dtype=float)
    if value.shape != (size,) or not np.all(np.isfinite(value)):
        raise DynamicsError(f"{name} must contain {size} finite values")
    return value.copy()


def skew(vector: Sequence[float]) -> np.ndarray:
    x, y, z = _array(vector, 3, "skew vector")
    return np.array(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def quat_product(left: Sequence[float], right: Sequence[float]) -> np.ndarray:
    lw, lx, ly, lz = _array(left, 4, "left quaternion")
    rw, rx, ry, rz = _array(right, 4, "right quaternion")
    return np.array(
        (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        )
    )


def normalize_quaternion(
    quaternion: Sequence[float], *, strict_unit: bool = False
) -> np.ndarray:
    result = _array(quaternion, 4, "quaternion")
    norm = float(np.linalg.norm(result))
    if not math.isfinite(norm) or norm < 1.0e-14:
        raise DynamicsError("quaternion norm must be finite and nonzero")
    if strict_unit and abs(norm - 1.0) > 1.0e-9:
        raise DynamicsError("public state quaternion must be unit normalized")
    return result / norm


def quat_from_rotvec(rotvec: Sequence[float]) -> np.ndarray:
    vector = _array(rotvec, 3, "rotation vector")
    angle = float(np.linalg.norm(vector))
    if angle < 1.0e-14:
        # The first-order term avoids a discontinuous direction at zero.
        return normalize_quaternion(np.array((1.0, *(0.5 * vector))))
    axis = vector / angle
    return np.array((math.cos(0.5 * angle), *(axis * math.sin(0.5 * angle))))


def quat_to_rotation(quaternion: Sequence[float]) -> np.ndarray:
    w, x, y, z = normalize_quaternion(quaternion)
    return np.array(
        (
            (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
            (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
            (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
        )
    )


def axis_rotation(axis: Sequence[float], angle_rad: float) -> np.ndarray:
    direction = _array(axis, 3, "rotation axis")
    norm = float(np.linalg.norm(direction))
    if norm < 1.0e-14 or not math.isfinite(angle_rad):
        raise DynamicsError("rotation axis and angle must be valid")
    direction /= norm
    cross = skew(direction)
    return (
        np.eye(3)
        + math.sin(angle_rad) * cross
        + (1.0 - math.cos(angle_rad)) * (cross @ cross)
    )


@dataclass(frozen=True)
class ServiceState:
    base_position_inertial_m: np.ndarray
    base_quaternion_body_to_inertial_wxyz: np.ndarray
    joint_coordinates_mixed: np.ndarray
    nu_s_mixed: np.ndarray


@dataclass(frozen=True)
class TargetState:
    position_inertial_m: np.ndarray
    quaternion_body_to_inertial_wxyz: np.ndarray
    twist_inertial_mixed: np.ndarray


@dataclass(frozen=True)
class StressPointCase:
    case_id: str
    link_index: int
    point_local_m: np.ndarray
    service_state: ServiceState


@dataclass(frozen=True)
class ELAuditStateCase:
    case_id: str
    service_state: ServiceState


@dataclass(frozen=True)
class BodyKinematics:
    name: str
    mass_kg: float
    inertia_inertial_kg_m2: np.ndarray
    position_inertial_m: np.ndarray
    rotation_body_to_inertial: np.ndarray
    translational_jacobian_mixed: np.ndarray
    angular_jacobian_mixed: np.ndarray


@dataclass(frozen=True)
class ChainKinematics:
    bodies: tuple[BodyKinematics, ...]
    joint_origins_inertial_m: tuple[np.ndarray, ...]
    joint_axes_inertial: tuple[np.ndarray, ...]
    link_origins_inertial_m: tuple[np.ndarray, ...]
    link_rotations_body_to_inertial: tuple[np.ndarray, ...]


@dataclass(frozen=True)
class MomentumLedger:
    linear_momentum_n_s: np.ndarray
    angular_momentum_about_inertial_origin_n_m_s: np.ndarray
    kinetic_energy_j: float


@dataclass(frozen=True)
class CombinedHistory:
    time_s: np.ndarray
    service_base_position_inertial_m: np.ndarray
    service_base_quaternion_body_to_inertial_wxyz: np.ndarray
    service_joint_coordinates_mixed: np.ndarray
    service_nu_s_mixed: np.ndarray
    target_position_inertial_m: np.ndarray
    target_quaternion_body_to_inertial_wxyz: np.ndarray
    target_twist_inertial_mixed: np.ndarray
    service_linear_momentum_n_s: np.ndarray
    service_angular_momentum_about_inertial_origin_n_m_s: np.ndarray
    service_kinetic_energy_j: np.ndarray
    target_linear_momentum_n_s: np.ndarray
    target_angular_momentum_about_inertial_origin_n_m_s: np.ndarray
    target_kinetic_energy_j: np.ndarray

    @property
    def total_linear_momentum_n_s(self) -> np.ndarray:
        return self.service_linear_momentum_n_s + self.target_linear_momentum_n_s

    @property
    def total_angular_momentum_about_inertial_origin_n_m_s(self) -> np.ndarray:
        return (
            self.service_angular_momentum_about_inertial_origin_n_m_s
            + self.target_angular_momentum_about_inertial_origin_n_m_s
        )

    @property
    def total_kinetic_energy_j(self) -> np.ndarray:
        return self.service_kinetic_energy_j + self.target_kinetic_energy_j


class FullFloatingServiceModel:
    """Synthetic serial 6R+2P tree with a free 6-DOF base."""

    def __init__(self) -> None:
        self.base_mass_kg = 19.4
        self.base_inertia_body_kg_m2 = np.diag((0.46, 0.52, 0.39))
        self.link_masses_kg = np.array((1.15, 0.94, 0.78, 0.62, 0.47, 0.36, 0.24, 0.19))
        self.link_inertias_body_kg_m2 = tuple(
            np.diag(diagonal)
            for diagonal in (
                (0.010, 0.019, 0.020),
                (0.008, 0.015, 0.016),
                (0.006, 0.012, 0.013),
                (0.0045, 0.0090, 0.0095),
                (0.0033, 0.0062, 0.0066),
                (0.0025, 0.0045, 0.0048),
                (0.0017, 0.0024, 0.0025),
                (0.0012, 0.0018, 0.0019),
            )
        )
        self.joint_types = JOINT_TYPES
        self.joint_axes_parent = tuple(
            np.array(axis, dtype=float)
            for axis in (
                (0.0, 0.0, 1.0),
                (0.0, 1.0, 0.0),
                (0.0, 1.0, 0.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (1.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
            )
        )
        self.joint_origin_offsets_parent_m = tuple(
            np.array(offset, dtype=float)
            for offset in (
                (0.19, 0.00, 0.11),
                (0.03, 0.01, 0.00),
                (0.02, -0.01, 0.01),
                (0.02, 0.00, 0.00),
                (0.01, 0.01, 0.00),
                (0.015, 0.00, 0.005),
                (0.010, 0.00, 0.000),
                (0.005, 0.00, 0.005),
            )
        )
        self.link_tip_offsets_body_m = tuple(
            np.array(offset, dtype=float)
            for offset in (
                (0.30, 0.00, 0.00),
                (0.27, 0.00, 0.00),
                (0.24, 0.00, 0.00),
                (0.20, 0.00, 0.00),
                (0.17, 0.00, 0.00),
                (0.14, 0.00, 0.00),
                (0.11, 0.00, 0.00),
                (0.09, 0.00, 0.00),
            )
        )
        self.link_com_offsets_body_m = tuple(
            0.48 * offset for offset in self.link_tip_offsets_body_m
        )
        self.dof = 8
        self.full_velocity_dof = 14

    @property
    def total_mass_kg(self) -> float:
        return float(self.base_mass_kg + np.sum(self.link_masses_kg))

    def validate_service_state(self, state: ServiceState) -> ServiceState:
        return ServiceState(
            _array(state.base_position_inertial_m, 3, "service base position"),
            normalize_quaternion(
                state.base_quaternion_body_to_inertial_wxyz, strict_unit=True
            ),
            _array(state.joint_coordinates_mixed, 8, "service joint coordinates"),
            _array(state.nu_s_mixed, 14, "service generalized velocity"),
        )

    def _chain_frames(self, state: ServiceState) -> tuple[
        list[np.ndarray], list[np.ndarray], list[np.ndarray], list[np.ndarray]
    ]:
        base_position = state.base_position_inertial_m
        parent_position = base_position
        parent_rotation = quat_to_rotation(
            state.base_quaternion_body_to_inertial_wxyz
        )
        joint_origins: list[np.ndarray] = []
        joint_axes: list[np.ndarray] = []
        link_origins: list[np.ndarray] = []
        link_rotations: list[np.ndarray] = []
        for index, joint_type in enumerate(self.joint_types):
            joint_origin = (
                parent_position
                + parent_rotation @ self.joint_origin_offsets_parent_m[index]
            )
            axis_world = parent_rotation @ self.joint_axes_parent[index]
            if joint_type == "R":
                child_rotation = parent_rotation @ axis_rotation(
                    self.joint_axes_parent[index],
                    float(state.joint_coordinates_mixed[index]),
                )
                child_origin = joint_origin
            else:
                child_rotation = parent_rotation
                child_origin = (
                    joint_origin
                    + axis_world * float(state.joint_coordinates_mixed[index])
                )
            joint_origins.append(joint_origin)
            joint_axes.append(axis_world)
            link_origins.append(child_origin)
            link_rotations.append(child_rotation)
            parent_position = (
                child_origin + child_rotation @ self.link_tip_offsets_body_m[index]
            )
            parent_rotation = child_rotation
        return joint_origins, joint_axes, link_origins, link_rotations

    def _point_jacobians_from_frames(
        self,
        state: ServiceState,
        link_index: int,
        point_inertial_m: np.ndarray,
        joint_origins: Sequence[np.ndarray],
        joint_axes: Sequence[np.ndarray],
    ) -> tuple[np.ndarray, np.ndarray]:
        if link_index < 0 or link_index >= self.dof:
            raise DynamicsError("link_index must be in [0, 7]")
        jv = np.zeros((3, self.full_velocity_dof))
        jw = np.zeros_like(jv)
        jv[:, :3] = np.eye(3)
        jv[:, 3:6] = -skew(point_inertial_m - state.base_position_inertial_m)
        jw[:, 3:6] = np.eye(3)
        for joint_index in range(link_index + 1):
            column = 6 + joint_index
            axis = joint_axes[joint_index]
            if self.joint_types[joint_index] == "R":
                jv[:, column] = np.cross(
                    axis, point_inertial_m - joint_origins[joint_index]
                )
                jw[:, column] = axis
            else:
                jv[:, column] = axis
        return jv, jw

    def kinematics(self, state: ServiceState) -> ChainKinematics:
        state = self.validate_service_state(state)
        base_rotation = quat_to_rotation(
            state.base_quaternion_body_to_inertial_wxyz
        )
        joint_origins, joint_axes, link_origins, link_rotations = self._chain_frames(
            state
        )
        base_jv = np.zeros((3, self.full_velocity_dof))
        base_jw = np.zeros_like(base_jv)
        base_jv[:, :3] = np.eye(3)
        base_jw[:, 3:6] = np.eye(3)
        bodies: list[BodyKinematics] = [
            BodyKinematics(
                "service_base",
                self.base_mass_kg,
                base_rotation @ self.base_inertia_body_kg_m2 @ base_rotation.T,
                state.base_position_inertial_m.copy(),
                base_rotation,
                base_jv,
                base_jw,
            )
        ]
        for link_index in range(self.dof):
            rotation = link_rotations[link_index]
            position = (
                link_origins[link_index]
                + rotation @ self.link_com_offsets_body_m[link_index]
            )
            jv, jw = self._point_jacobians_from_frames(
                state, link_index, position, joint_origins, joint_axes
            )
            bodies.append(
                BodyKinematics(
                    f"synthetic_link_{link_index + 1}",
                    float(self.link_masses_kg[link_index]),
                    rotation
                    @ self.link_inertias_body_kg_m2[link_index]
                    @ rotation.T,
                    position,
                    rotation,
                    jv,
                    jw,
                )
            )
        return ChainKinematics(
            tuple(bodies),
            tuple(joint_origins),
            tuple(joint_axes),
            tuple(link_origins),
            tuple(link_rotations),
        )

    def point_position_and_jacobian(
        self,
        state: ServiceState,
        link_index: int,
        point_local_m: Sequence[float],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        state = self.validate_service_state(state)
        local = _array(point_local_m, 3, "link-local point")
        frames = self.kinematics(state)
        position = (
            frames.link_origins_inertial_m[link_index]
            + frames.link_rotations_body_to_inertial[link_index] @ local
        )
        jv, jw = self._point_jacobians_from_frames(
            state,
            link_index,
            position,
            frames.joint_origins_inertial_m,
            frames.joint_axes_inertial,
        )
        return position, jv, jw

    def mass_matrix(self, state: ServiceState) -> np.ndarray:
        matrix = np.zeros((self.full_velocity_dof, self.full_velocity_dof))
        for body in self.kinematics(state).bodies:
            matrix += (
                body.mass_kg
                * body.translational_jacobian_mixed.T
                @ body.translational_jacobian_mixed
                + body.angular_jacobian_mixed.T
                @ body.inertia_inertial_kg_m2
                @ body.angular_jacobian_mixed
            )
        return 0.5 * (matrix + matrix.T)

    def _shift_state_along_velocity(
        self, state: ServiceState, velocity: np.ndarray, delta_s: float
    ) -> ServiceState:
        increment = quat_from_rotvec(delta_s * velocity[3:6])
        shifted_quaternion = normalize_quaternion(
            quat_product(
                increment, state.base_quaternion_body_to_inertial_wxyz
            )
        )
        return ServiceState(
            state.base_position_inertial_m + delta_s * velocity[:3],
            shifted_quaternion,
            state.joint_coordinates_mixed + delta_s * velocity[6:],
            velocity.copy(),
        )

    def bias_effort(self, state: ServiceState, *, difference_step_s: float = 2.0e-6) -> np.ndarray:
        state = self.validate_service_state(state)
        if not math.isfinite(difference_step_s) or difference_step_s <= 0.0:
            raise DynamicsError("difference_step_s must be positive and finite")
        velocity = state.nu_s_mixed
        present = self.kinematics(state)
        plus = self.kinematics(
            self._shift_state_along_velocity(state, velocity, difference_step_s)
        )
        minus = self.kinematics(
            self._shift_state_along_velocity(state, velocity, -difference_step_s)
        )
        bias = np.zeros(self.full_velocity_dof)
        for body, body_plus, body_minus in zip(
            present.bodies, plus.bodies, minus.bodies
        ):
            jv_dot = (
                body_plus.translational_jacobian_mixed
                - body_minus.translational_jacobian_mixed
            ) / (2.0 * difference_step_s)
            jw_dot = (
                body_plus.angular_jacobian_mixed
                - body_minus.angular_jacobian_mixed
            ) / (2.0 * difference_step_s)
            omega = body.angular_jacobian_mixed @ velocity
            translational_bias_acceleration = jv_dot @ velocity
            angular_bias_acceleration = jw_dot @ velocity
            inertial_torque = (
                body.inertia_inertial_kg_m2 @ angular_bias_acceleration
                + np.cross(
                    omega, body.inertia_inertial_kg_m2 @ omega
                )
            )
            bias += (
                body.translational_jacobian_mixed.T
                @ (body.mass_kg * translational_bias_acceleration)
                + body.angular_jacobian_mixed.T @ inertial_torque
            )
        return bias

    def acceleration_zero_external(self, state: ServiceState) -> np.ndarray:
        matrix = self.mass_matrix(state)
        minimum_eigenvalue = float(np.min(np.linalg.eigvalsh(matrix)))
        if minimum_eigenvalue <= 1.0e-10:
            raise DynamicsError("service mass matrix is not positive definite")
        return np.linalg.solve(matrix, -self.bias_effort(state))

    def momentum_energy(self, state: ServiceState) -> MomentumLedger:
        state = self.validate_service_state(state)
        linear = np.zeros(3)
        angular = np.zeros(3)
        energy = 0.0
        for body in self.kinematics(state).bodies:
            velocity = body.translational_jacobian_mixed @ state.nu_s_mixed
            omega = body.angular_jacobian_mixed @ state.nu_s_mixed
            body_linear = body.mass_kg * velocity
            body_spin = body.inertia_inertial_kg_m2 @ omega
            linear += body_linear
            angular += np.cross(body.position_inertial_m, body_linear) + body_spin
            energy += 0.5 * body.mass_kg * float(velocity @ velocity)
            energy += 0.5 * float(omega @ body_spin)
        return MomentumLedger(linear, angular, float(energy))

    def kinetic_energy_from_mass_matrix(self, state: ServiceState) -> float:
        state = self.validate_service_state(state)
        return float(0.5 * state.nu_s_mixed @ self.mass_matrix(state) @ state.nu_s_mixed)

    def finite_difference_point_jacobian(
        self,
        state: ServiceState,
        link_index: int,
        point_local_m: Sequence[float],
        *,
        translation_step_m: float = 2.0e-7,
        rotation_step_rad: float = 2.0e-7,
    ) -> np.ndarray:
        state = self.validate_service_state(state)
        result = np.zeros((3, self.full_velocity_dof))
        for column in range(self.full_velocity_dof):
            step = translation_step_m if column < 3 or column >= 12 else rotation_step_rad
            plus = self.perturb_configuration(state, column, step)
            minus = self.perturb_configuration(state, column, -step)
            plus_position = self.point_position_and_jacobian(
                plus, link_index, point_local_m
            )[0]
            minus_position = self.point_position_and_jacobian(
                minus, link_index, point_local_m
            )[0]
            result[:, column] = (plus_position - minus_position) / (2.0 * step)
        return result

    def perturb_configuration(
        self, state: ServiceState, column: int, increment: float
    ) -> ServiceState:
        state = self.validate_service_state(state)
        if column < 0 or column >= self.full_velocity_dof or not math.isfinite(increment):
            raise DynamicsError("configuration perturbation is invalid")
        position = state.base_position_inertial_m.copy()
        quaternion = state.base_quaternion_body_to_inertial_wxyz.copy()
        coordinates = state.joint_coordinates_mixed.copy()
        if column < 3:
            position[column] += increment
        elif column < 6:
            vector = np.zeros(3)
            vector[column - 3] = increment
            quaternion = normalize_quaternion(
                quat_product(quat_from_rotvec(vector), quaternion)
            )
        else:
            coordinates[column - 6] += increment
        return ServiceState(position, quaternion, coordinates, state.nu_s_mixed.copy())


TARGET_MASS_KG = 22.0
TARGET_INERTIA_BODY_KG_M2 = np.array(
    ((2.8, 0.08, -0.04), (0.08, 3.5, 0.06), (-0.04, 0.06, 4.1))
)


def validate_target_state(state: TargetState) -> TargetState:
    inertia_eigenvalues = np.linalg.eigvalsh(TARGET_INERTIA_BODY_KG_M2)
    if float(np.min(inertia_eigenvalues)) <= 0.0:
        raise DynamicsError("target inertia must be positive definite")
    return TargetState(
        _array(state.position_inertial_m, 3, "target position"),
        normalize_quaternion(
            state.quaternion_body_to_inertial_wxyz, strict_unit=True
        ),
        _array(state.twist_inertial_mixed, 6, "target twist"),
    )


def target_momentum_energy(state: TargetState) -> MomentumLedger:
    state = validate_target_state(state)
    rotation = quat_to_rotation(state.quaternion_body_to_inertial_wxyz)
    inertia_world = rotation @ TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    velocity = state.twist_inertial_mixed[:3]
    omega = state.twist_inertial_mixed[3:]
    linear = TARGET_MASS_KG * velocity
    spin = inertia_world @ omega
    angular = np.cross(state.position_inertial_m, linear) + spin
    energy = 0.5 * TARGET_MASS_KG * float(velocity @ velocity) + 0.5 * float(
        omega @ spin
    )
    return MomentumLedger(linear, angular, energy)


def _service_to_vector(state: ServiceState) -> np.ndarray:
    return np.concatenate(
        (
            state.base_position_inertial_m,
            state.base_quaternion_body_to_inertial_wxyz,
            state.joint_coordinates_mixed,
            state.nu_s_mixed,
        )
    )


def _service_from_vector(vector: Sequence[float], *, strict: bool = False) -> ServiceState:
    value = _array(vector, 29, "service integration state")
    quaternion = normalize_quaternion(value[3:7], strict_unit=strict)
    return ServiceState(value[:3], quaternion, value[7:15], value[15:29])


def _target_to_vector(state: TargetState) -> np.ndarray:
    return np.concatenate(
        (
            state.position_inertial_m,
            state.quaternion_body_to_inertial_wxyz,
            state.twist_inertial_mixed,
        )
    )


def _target_from_vector(vector: Sequence[float], *, strict: bool = False) -> TargetState:
    value = _array(vector, 13, "target integration state")
    quaternion = normalize_quaternion(value[3:7], strict_unit=strict)
    return TargetState(value[:3], quaternion, value[7:13])


def _service_rhs(model: FullFloatingServiceModel, vector: np.ndarray) -> np.ndarray:
    state = _service_from_vector(vector)
    acceleration = model.acceleration_zero_external(state)
    quaternion_rate = 0.5 * quat_product(
        np.array((0.0, *state.nu_s_mixed[3:6])),
        state.base_quaternion_body_to_inertial_wxyz,
    )
    return np.concatenate(
        (
            state.nu_s_mixed[:3],
            quaternion_rate,
            state.nu_s_mixed[6:],
            acceleration,
        )
    )


def _target_rhs(vector: np.ndarray) -> np.ndarray:
    state = _target_from_vector(vector)
    rotation = quat_to_rotation(state.quaternion_body_to_inertial_wxyz)
    inertia_world = rotation @ TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    velocity = state.twist_inertial_mixed[:3]
    omega = state.twist_inertial_mixed[3:]
    omega_dot = np.linalg.solve(inertia_world, -np.cross(omega, inertia_world @ omega))
    quaternion_rate = 0.5 * quat_product(
        np.array((0.0, *omega)), state.quaternion_body_to_inertial_wxyz
    )
    return np.concatenate((velocity, quaternion_rate, np.zeros(3), omega_dot))


def _step(function, state: np.ndarray, step_s: float, method: str) -> np.ndarray:
    if method == "rk4":
        k1 = function(state)
        k2 = function(state + 0.5 * step_s * k1)
        k3 = function(state + 0.5 * step_s * k2)
        k4 = function(state + step_s * k3)
        return state + (step_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    if method == "midpoint":
        k1 = function(state)
        k2 = function(state + 0.5 * step_s * k1)
        return state + step_s * k2
    raise DynamicsError("integration method must be 'rk4' or 'midpoint'")


def propagate_no_contact(
    model: FullFloatingServiceModel,
    service_initial: ServiceState,
    target_initial: TargetState,
    *,
    step_s: float,
    steps: int,
    method: str = "rk4",
) -> CombinedHistory:
    """Advance independent service and target plants on exactly one time grid."""

    if not math.isfinite(step_s) or step_s <= 0.0:
        raise DynamicsError("step_s must be positive and finite")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise DynamicsError("steps must be a positive integer")
    service_initial = model.validate_service_state(service_initial)
    target_initial = validate_target_state(target_initial)
    service_vector = _service_to_vector(service_initial)
    target_vector = _target_to_vector(target_initial)
    count = steps + 1
    times = np.arange(count, dtype=float) * step_s
    service_position = np.empty((count, 3))
    service_quaternion = np.empty((count, 4))
    service_coordinates = np.empty((count, 8))
    service_velocity = np.empty((count, 14))
    target_position = np.empty((count, 3))
    target_quaternion = np.empty((count, 4))
    target_velocity = np.empty((count, 6))
    service_linear = np.empty((count, 3))
    service_angular = np.empty((count, 3))
    service_energy = np.empty(count)
    target_linear = np.empty((count, 3))
    target_angular = np.empty((count, 3))
    target_energy = np.empty(count)
    for index in range(count):
        service = _service_from_vector(service_vector)
        target = _target_from_vector(target_vector)
        service_vector[3:7] = service.base_quaternion_body_to_inertial_wxyz
        target_vector[3:7] = target.quaternion_body_to_inertial_wxyz
        service_ledger = model.momentum_energy(service)
        target_ledger = target_momentum_energy(target)
        service_position[index] = service.base_position_inertial_m
        service_quaternion[index] = service.base_quaternion_body_to_inertial_wxyz
        service_coordinates[index] = service.joint_coordinates_mixed
        service_velocity[index] = service.nu_s_mixed
        target_position[index] = target.position_inertial_m
        target_quaternion[index] = target.quaternion_body_to_inertial_wxyz
        target_velocity[index] = target.twist_inertial_mixed
        service_linear[index] = service_ledger.linear_momentum_n_s
        service_angular[index] = service_ledger.angular_momentum_about_inertial_origin_n_m_s
        service_energy[index] = service_ledger.kinetic_energy_j
        target_linear[index] = target_ledger.linear_momentum_n_s
        target_angular[index] = target_ledger.angular_momentum_about_inertial_origin_n_m_s
        target_energy[index] = target_ledger.kinetic_energy_j
        if index == steps:
            break
        service_vector = _step(
            lambda value: _service_rhs(model, value), service_vector, step_s, method
        )
        target_vector = _step(_target_rhs, target_vector, step_s, method)
        service_vector[3:7] = normalize_quaternion(service_vector[3:7])
        target_vector[3:7] = normalize_quaternion(target_vector[3:7])
    return CombinedHistory(
        times,
        service_position,
        service_quaternion,
        service_coordinates,
        service_velocity,
        target_position,
        target_quaternion,
        target_velocity,
        service_linear,
        service_angular,
        service_energy,
        target_linear,
        target_angular,
        target_energy,
    )


def deterministic_scenario() -> tuple[
    FullFloatingServiceModel, ServiceState, TargetState
]:
    model = FullFloatingServiceModel()
    service = ServiceState(
        np.array((0.31, -0.22, 0.44)),
        quat_from_rotvec((0.17, -0.11, 0.21)),
        np.array((0.24, -0.31, 0.19, 0.27, -0.16, 0.12, 0.018, -0.009)),
        np.array(
            (
                0.032,
                -0.021,
                0.014,
                0.041,
                -0.033,
                0.027,
                0.115,
                -0.082,
                0.071,
                -0.054,
                0.046,
                -0.035,
                0.0075,
                -0.0058,
            )
        ),
    )
    target = TargetState(
        np.array((1.82, -0.46, 0.73)),
        quat_from_rotvec((-0.12, 0.18, 0.09)),
        np.array((-0.023, 0.017, -0.011, 0.083, -0.061, 0.047)),
    )
    return model, service, target


def deterministic_stress_points() -> tuple[StressPointCase, ...]:
    """Ten explicit, RNG-free kinematic stress cases covering every link."""

    # Each row is frozen as (id, link, base_position, base_rotvec, q[8], point).
    rows = (
        ("SP00_LINK0", 0, (0.10, -0.20, 0.30), (0.10, -0.05, 0.08), (0.10, -0.20, 0.15, -0.12, 0.08, -0.05, 0.010, -0.006), (0.083, -0.012, 0.021)),
        ("SP01_LINK1", 1, (-0.30, 0.15, 0.42), (-0.18, 0.09, 0.14), (-0.25, 0.31, -0.17, 0.22, -0.11, 0.07, -0.014, 0.009), (0.061, 0.018, -0.027)),
        ("SP02_LINK2", 2, (0.45, 0.08, -0.16), (0.21, 0.13, -0.19), (0.34, -0.28, 0.26, -0.18, 0.15, -0.09, 0.022, 0.004), (0.052, -0.024, 0.031)),
        ("SP03_LINK3", 3, (-0.12, -0.38, 0.27), (-0.11, -0.24, 0.16), (-0.37, 0.19, -0.29, 0.33, -0.14, 0.12, -0.008, -0.013), (0.047, 0.026, 0.019)),
        ("SP04_LINK4", 4, (0.24, 0.36, -0.22), (0.26, -0.17, -0.07), (0.18, 0.27, -0.35, -0.21, 0.24, -0.16, 0.016, 0.012), (0.039, -0.017, -0.029)),
        ("SP05_LINK5", 5, (-0.41, 0.12, 0.18), (-0.23, 0.20, 0.11), (-0.16, -0.32, 0.23, 0.29, -0.27, 0.18, -0.019, 0.007), (0.032, 0.021, -0.018)),
        ("SP06_LINK6", 6, (0.33, -0.29, -0.11), (0.15, 0.27, -0.22), (0.29, -0.14, -0.24, 0.17, 0.31, -0.20, 0.025, -0.015), (0.071, -0.023, 0.038)),
        ("SP07_LINK7", 7, (-0.19, 0.31, 0.39), (-0.28, -0.12, 0.25), (-0.31, 0.36, 0.12, -0.26, 0.19, 0.23, -0.011, 0.018), (0.064, 0.029, -0.034)),
        ("SP08_LINK0_EDGE", 0, (0.07, 0.44, -0.28), (0.31, -0.29, 0.18), (0.41, -0.39, 0.37, -0.34, 0.28, -0.25, 0.029, -0.021), (0.091, 0.027, -0.025)),
        ("SP09_LINK7_EDGE", 7, (-0.36, -0.17, 0.51), (-0.33, 0.24, -0.27), (-0.43, 0.38, -0.33, 0.30, -0.29, 0.27, -0.026, 0.023), (0.078, -0.031, 0.044)),
    )
    frozen_velocity = np.array(
        (0.021, -0.017, 0.013, 0.028, -0.022, 0.019, 0.07, -0.06, 0.05, -0.04, 0.03, -0.02, 0.004, -0.003)
    )
    return tuple(
        StressPointCase(
            case_id,
            link_index,
            np.asarray(point, dtype=float),
            ServiceState(
                np.asarray(position, dtype=float),
                quat_from_rotvec(rotvec),
                np.asarray(coordinates, dtype=float),
                frozen_velocity.copy(),
            ),
        )
        for case_id, link_index, position, rotvec, coordinates, point in rows
    )


def deterministic_el_audit_states() -> tuple[ELAuditStateCase, ...]:
    """Six explicit nonzero-velocity EL states; no RNG or inherited PASS."""

    _, nominal, _ = deterministic_scenario()
    rows = (
        (
            "EL00_NOMINAL",
            nominal.base_position_inertial_m,
            nominal.base_quaternion_body_to_inertial_wxyz,
            nominal.joint_coordinates_mixed,
            nominal.nu_s_mixed,
        ),
        (
            "EL01_CROSSED_RP",
            (-0.28, 0.17, 0.36),
            quat_from_rotvec((-0.16, 0.12, 0.19)),
            (-0.27, 0.33, -0.21, 0.24, -0.13, 0.09, -0.014, 0.011),
            (-0.026, 0.019, 0.012, -0.034, 0.029, -0.021, 0.092, -0.074, 0.063, -0.049, 0.038, -0.031, 0.0062, -0.0047),
        ),
        (
            "EL02_POSITIVE_EXTENSION",
            (0.42, 0.09, -0.18),
            quat_from_rotvec((0.22, 0.15, -0.17)),
            (0.36, -0.29, 0.25, -0.19, 0.17, -0.11, 0.024, 0.006),
            (0.024, -0.018, 0.016, 0.031, -0.027, 0.023, -0.086, 0.069, -0.058, 0.047, -0.036, 0.028, -0.0055, 0.0041),
        ),
        (
            "EL03_NEGATIVE_EXTENSION",
            (-0.15, -0.34, 0.25),
            quat_from_rotvec((-0.13, -0.23, 0.14)),
            (-0.39, 0.22, -0.31, 0.35, -0.18, 0.14, -0.021, -0.016),
            (0.018, 0.025, -0.014, -0.029, 0.024, 0.032, 0.081, -0.067, 0.055, -0.043, 0.034, -0.026, 0.0048, -0.0039),
        ),
        (
            "EL04_WRIST_FOLDED",
            (0.27, 0.32, -0.24),
            quat_from_rotvec((0.25, -0.18, -0.09)),
            (0.21, 0.30, -0.37, -0.23, 0.28, -0.20, 0.018, 0.014),
            (-0.021, -0.016, 0.019, 0.037, 0.022, -0.025, -0.097, 0.078, -0.064, 0.052, -0.041, 0.033, -0.0067, 0.0052),
        ),
        (
            "EL05_EDGE_MIXED",
            (-0.35, -0.16, 0.49),
            quat_from_rotvec((-0.31, 0.21, -0.25)),
            (-0.42, 0.37, -0.34, 0.31, -0.27, 0.26, -0.027, 0.022),
            (0.029, -0.023, 0.017, -0.038, -0.031, 0.026, 0.104, -0.083, 0.072, -0.057, 0.045, -0.036, 0.0071, -0.0054),
        ),
    )
    cases = []
    for case_id, position, quaternion, coordinates, velocity in rows:
        cases.append(
            ELAuditStateCase(
                case_id,
                ServiceState(
                    np.asarray(position, dtype=float),
                    normalize_quaternion(quaternion),
                    np.asarray(coordinates, dtype=float),
                    np.asarray(velocity, dtype=float),
                ),
            )
        )
    return tuple(cases)


def run_negative_controls(
    model: FullFloatingServiceModel, state: ServiceState
) -> dict[str, dict[str, object]]:
    """Inject registered defects and report independent rejection metrics."""

    state = model.validate_service_state(state)
    matrix = model.mass_matrix(state)
    shape_rates = np.array((0.13, -0.09, 0.08, -0.06, 0.05, -0.04, 0.009, -0.007))
    free_base_twist = -np.linalg.solve(matrix[:6, :6], matrix[:6, 6:] @ shape_rates)
    free_state = ServiceState(
        state.base_position_inertial_m,
        state.base_quaternion_body_to_inertial_wxyz,
        state.joint_coordinates_mixed,
        np.concatenate((free_base_twist, shape_rates)),
    )
    locked_state = ServiceState(
        state.base_position_inertial_m,
        state.base_quaternion_body_to_inertial_wxyz,
        state.joint_coordinates_mixed,
        np.concatenate((np.zeros(6), shape_rates)),
    )
    free_ledger = model.momentum_energy(free_state)
    locked_ledger = model.momentum_energy(locked_state)
    free_linear_defect_n_s = float(
        np.linalg.norm(free_ledger.linear_momentum_n_s)
    )
    free_angular_defect_n_m_s = float(
        np.linalg.norm(free_ledger.angular_momentum_about_inertial_origin_n_m_s)
    )
    locked_linear_defect_n_s = float(
        np.linalg.norm(locked_ledger.linear_momentum_n_s)
    )
    locked_angular_defect_n_m_s = float(
        np.linalg.norm(locked_ledger.angular_momentum_about_inertial_origin_n_m_s)
    )

    mutated_matrix = matrix.copy()
    mutated_matrix[:6, 6:] = 0.0
    mutated_matrix[6:, :6] = 0.0
    direct_energy = model.momentum_energy(state).kinetic_energy_j
    mutated_energy = float(0.5 * state.nu_s_mixed @ mutated_matrix @ state.nu_s_mixed)
    missing_coupling_error = abs(mutated_energy - direct_energy)

    point = np.array((0.071, -0.023, 0.038))
    _, analytic, _ = model.point_position_and_jacobian(state, 7, point)
    finite_difference = model.finite_difference_point_jacobian(state, 7, point)
    rp_mutation = analytic.copy()
    rp_mutation[:, 12:14] *= 1.0e-3
    rp_error = float(np.max(np.abs(rp_mutation - finite_difference)))
    sign_mutation = analytic.copy()
    sign_mutation[:, 8] *= -1.0
    sign_error = float(np.max(np.abs(sign_mutation - finite_difference)))
    _, offset_mutation, _ = model.point_position_and_jacobian(
        state, 7, (0.0, 0.0, 0.0)
    )
    offset_error = float(np.max(np.abs(offset_mutation - finite_difference)))

    nan_rejected = False
    invalid_norm_rejected = False
    try:
        model.validate_service_state(
            ServiceState(
                state.base_position_inertial_m,
                np.array((np.nan, 0.0, 0.0, 0.0)),
                state.joint_coordinates_mixed,
                state.nu_s_mixed,
            )
        )
    except DynamicsError:
        nan_rejected = True
    try:
        model.validate_service_state(
            ServiceState(
                state.base_position_inertial_m,
                np.array((2.0, 0.0, 0.0, 0.0)),
                state.joint_coordinates_mixed,
                state.nu_s_mixed,
            )
        )
    except DynamicsError:
        invalid_norm_rejected = True

    return {
        "NC-A01_BASE_LOCK": {
            "detected": free_linear_defect_n_s < 1.0e-12
            and free_angular_defect_n_m_s < 1.0e-12
            and locked_linear_defect_n_s > 1.0e-3
            and locked_angular_defect_n_m_s > 1.0e-3,
            "free_linear_momentum_defect_n_s": free_linear_defect_n_s,
            "free_angular_momentum_defect_n_m_s": free_angular_defect_n_m_s,
            "locked_linear_momentum_defect_n_s": locked_linear_defect_n_s,
            "locked_angular_momentum_defect_n_m_s": locked_angular_defect_n_m_s,
            "guard_thresholds": {
                "free_linear_max_n_s": 1.0e-12,
                "free_angular_max_n_m_s": 1.0e-12,
                "locked_linear_min_n_s": 1.0e-3,
                "locked_angular_min_n_m_s": 1.0e-3,
            },
            "linear_and_angular_momentum_combined": False,
        },
        "NC-A02_MISSING_COUPLING_BLOCK": {
            "detected": missing_coupling_error > 1.0e-5,
            "direct_vs_mutated_energy_error_j": missing_coupling_error,
            "guard_threshold_min_j": 1.0e-5,
        },
        "NC-A03_RP_UNIT_SCALE": {
            "detected": rp_error > 1.0e-2,
            "maximum_point_jacobian_error_mixed_units": rp_error,
            "guard_threshold_min_mixed_units": 1.0e-2,
        },
        "NC-A04_INVALID_QUATERNION": {
            "detected": nan_rejected and invalid_norm_rejected,
            "nan_rejected": nan_rejected,
            "nonunit_rejected": invalid_norm_rejected,
            "injected_nonunit_norm_error": 1.0,
            "guard_threshold_max_unit_norm_error": 1.0e-9,
        },
        "NC-A05_JACOBIAN_SIGN": {
            "detected": sign_error > 1.0e-2,
            "maximum_point_jacobian_error_mixed_units": sign_error,
            "guard_threshold_min_mixed_units": 1.0e-2,
        },
        "NC-A06_POINT_OFFSET": {
            "detected": offset_error > 1.0e-3,
            "maximum_point_jacobian_error_mixed_units": offset_error,
            "guard_threshold_min_mixed_units": 1.0e-3,
        },
    }


def relative_vector_drift(history: np.ndarray) -> float:
    values = np.asarray(history, dtype=float)
    denominator = max(float(np.linalg.norm(values[0])), 1.0e-12)
    return float(np.max(np.linalg.norm(values - values[0], axis=1)) / denominator)


def relative_scalar_drift(history: np.ndarray) -> float:
    values = np.asarray(history, dtype=float)
    denominator = max(abs(float(values[0])), 1.0e-12)
    return float(np.max(np.abs(values - values[0])) / denominator)


def quaternion_geodesic(left: Sequence[float], right: Sequence[float]) -> float:
    lq = normalize_quaternion(left)
    rq = normalize_quaternion(right)
    return float(2.0 * math.acos(min(1.0, abs(float(lq @ rq)))))
