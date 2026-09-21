"""Independent frozen B4G forced-attached propagation replay.

This module deliberately does not import the production B4E/B4G solver, the
campaign runner, or the mutation executor.  It restates the frozen synthetic
6R+parallel-2P rigid-body model, attached-target reduction, time-dependent
P-only force law, and RK4/explicit-midpoint tableaux used by the NC08 evidence
path.  The independent validator can therefore distinguish a real numerical
propagation trace from an arbitrary, merely self-consistent collection of
states, work, and ledger arrays.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

import numpy as np
from scipy import linalg as scipy_linalg


class ForcedPropagationReplayError(ValueError):
    """Fail-closed input or numerical error in the independent replay."""


STATE_SIZE = 30
SERVICE_STATE_SIZE = 29
WORK_INDEX = 29
REFERENCE_DIFFERENCE_STEP_S = 2.0e-6

_BASE_MASS_KG = 19.4
_BASE_INERTIA_BODY_KG_M2 = np.diag((0.46, 0.52, 0.39))
_ARM_LINK_MASSES_KG = np.asarray((1.15, 0.94, 0.78, 0.62, 0.47, 0.36))
_ARM_LINK_INERTIAS_BODY_KG_M2 = tuple(
    np.diag(value)
    for value in (
        (0.010, 0.019, 0.020),
        (0.008, 0.015, 0.016),
        (0.006, 0.012, 0.013),
        (0.0045, 0.0090, 0.0095),
        (0.0033, 0.0062, 0.0066),
        (0.0025, 0.0045, 0.0048),
    )
)
_ARM_JOINT_AXES_PARENT = tuple(
    np.asarray(value, dtype=float)
    for value in (
        (0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
    )
)
_ARM_JOINT_ORIGINS_PARENT_M = tuple(
    np.asarray(value, dtype=float)
    for value in (
        (0.19, 0.00, 0.11),
        (0.03, 0.01, 0.00),
        (0.02, -0.01, 0.01),
        (0.02, 0.00, 0.00),
        (0.01, 0.01, 0.00),
        (0.015, 0.00, 0.005),
    )
)
_ARM_LINK_TIPS_BODY_M = tuple(
    np.asarray(value, dtype=float)
    for value in (
        (0.30, 0.00, 0.00),
        (0.27, 0.00, 0.00),
        (0.24, 0.00, 0.00),
        (0.20, 0.00, 0.00),
        (0.17, 0.00, 0.00),
        (0.14, 0.00, 0.00),
    )
)
_ARM_LINK_COM_BODY_M = tuple(0.48 * value for value in _ARM_LINK_TIPS_BODY_M)

_PALM_FIXED_ORIGIN_PARENT_M = np.asarray((0.0, 0.0, 0.15971))
_PALM_MASS_KG = 0.181800159145243
_PALM_COM_BODY_M = np.asarray(
    (-0.11400456131826, 7.30809328589541e-05, -8.098254686284e-08)
)
_PALM_INERTIA_BODY_KG_M2 = np.asarray(
    (
        (0.000232385828322385, -2.77584025941111e-07, -6.04874349510246e-10),
        (-2.77584025941111e-07, 5.85085867377427e-05, -1.15493362444215e-08),
        (-6.04874349510246e-10, -1.15493362444215e-08, 0.000205213535851537),
    )
)
_LEFT_JOINT_ORIGIN_PALM_M = np.asarray((-0.042091, 2.7531e-05, -1.3031e-05))
_RIGHT_JOINT_ORIGIN_PALM_M = np.asarray((-0.042091, -2.7531e-05, 1.3031e-05))
_LEFT_AXIS_PALM = np.asarray((0.0, -1.0, 0.0))
_RIGHT_AXIS_PALM = np.asarray((0.0, 1.0, 0.0))
_FINGER_MASSES_KG = (0.0423278952416158, 0.0423278949561274)
_FINGER_COM_BODY_M = (
    np.asarray((0.00937154605945142, -0.0183514409006279, -0.00213050813223617)),
    np.asarray((0.00937154599936671, 0.0183514410059713, 0.00213050822993754)),
)
_FINGER_INERTIAS_BODY_KG_M2 = (
    np.asarray(
        (
            (9.68819007445228e-06, -1.14547785891207e-06, 1.82410432419993e-08),
            (-1.14547785891207e-06, 9.7195653452821e-06, 1.20737618180169e-07),
            (1.82410432419993e-08, 1.20737618180169e-07, 1.13638462227589e-05),
        )
    ),
    np.asarray(
        (
            (9.68819002375832e-06, 1.14547786360874e-06, -1.82410118281856e-08),
            (1.14547786360874e-06, 9.7195652747221e-06, 1.20737613592695e-07),
            (-1.82410118281856e-08, 1.20737613592695e-07, 1.13638461944347e-05),
        )
    ),
)

_TARGET_MASS_KG = 22.0
_TARGET_INERTIA_BODY_KG_M2 = np.asarray(
    ((2.8, 0.08, -0.04), (0.08, 3.5, 0.06), (-0.04, 0.06, 4.1))
)

LEDGER_NAMES = (
    "linear_momentum_drift_N_s",
    "angular_momentum_drift_N_m_s",
    "energy_minus_work_residual_J",
    "ideal_constraint_power_W",
    "active_contact_force_N",
    "active_contact_torque_N_m",
    "forced_full_residual_service_base_linear_N",
    "forced_full_residual_service_base_angular_N_m",
    "forced_full_residual_service_R_joint_N_m",
    "forced_full_residual_service_P_joint_N",
    "forced_full_residual_target_linear_N",
    "forced_full_residual_target_angular_N_m",
    "reduced_residual_base_linear_N",
    "reduced_residual_base_angular_N_m",
    "reduced_residual_R_joint_N_m",
    "reduced_residual_P_joint_N",
)


@dataclass(frozen=True)
class _ServiceState:
    position_m: np.ndarray
    quaternion_wxyz: np.ndarray
    joints_mixed: np.ndarray
    velocity_mixed: np.ndarray


@dataclass(frozen=True)
class _Frames:
    joint_origins_m: tuple[np.ndarray, ...]
    joint_axes: tuple[np.ndarray, ...]
    link_origins_m: tuple[np.ndarray, ...]
    link_rotations: tuple[np.ndarray, ...]
    palm_origin_m: np.ndarray
    palm_rotation: np.ndarray
    left_joint_origin_m: np.ndarray
    right_joint_origin_m: np.ndarray
    left_axis: np.ndarray
    right_axis: np.ndarray
    left_link_origin_m: np.ndarray
    right_link_origin_m: np.ndarray
    left_link_rotation: np.ndarray
    right_link_rotation: np.ndarray


@dataclass(frozen=True)
class _Body:
    mass_kg: float
    inertia_inertial_kg_m2: np.ndarray
    position_m: np.ndarray
    jv: np.ndarray
    jw: np.ndarray


@dataclass(frozen=True)
class _TargetState:
    position_m: np.ndarray
    quaternion_wxyz: np.ndarray
    twist_mixed: np.ndarray


@dataclass(frozen=True)
class FrozenStageReplay:
    """One independently reconstructed accepted sample or RHS stage."""

    stage_label: str
    stage_code: int
    time_s: float
    state_30: np.ndarray
    derivative_30: np.ndarray | None
    generalized_force_14: np.ndarray
    actuator_power_W: float
    mass_cholesky_min_diagonal: float
    mass_min_eigenvalue: float | None


@dataclass(frozen=True)
class ForcedPropagationReplay:
    """Complete independent accepted-state, stage, and ledger reconstruction."""

    state_30: np.ndarray
    command_Q_14: np.ndarray
    actuator_power_W: np.ndarray
    target_state_13: np.ndarray
    total_linear_momentum_N_s: np.ndarray
    total_angular_momentum_N_m_s: np.ndarray
    total_kinetic_energy_J: np.ndarray
    sample_ledgers: Mapping[str, np.ndarray]
    stages: tuple[FrozenStageReplay, ...]


def _array(value: Any, shape: tuple[int, ...], code: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as error:
        raise ForcedPropagationReplayError(f"{code}_NOT_NUMERIC") from error
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ForcedPropagationReplayError(f"{code}_SHAPE_OR_NONFINITE")
    return result.copy()


def _number(value: Any, code: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise ForcedPropagationReplayError(f"{code}_NOT_FINITE_NUMBER")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ForcedPropagationReplayError(f"{code}_NOT_FINITE_NUMBER") from error
    if not math.isfinite(result):
        raise ForcedPropagationReplayError(f"{code}_NOT_FINITE_NUMBER")
    return result


def _skew(value: Any) -> np.ndarray:
    x, y, z = _array(value, (3,), "SKEW")
    return np.asarray(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def _quat_product(left: Any, right: Any) -> np.ndarray:
    lw, lx, ly, lz = _array(left, (4,), "QUAT_LEFT")
    rw, rx, ry, rz = _array(right, (4,), "QUAT_RIGHT")
    return np.asarray(
        (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        )
    )


def _normalize_quaternion(value: Any) -> np.ndarray:
    quaternion = _array(value, (4,), "QUATERNION")
    norm = float(np.linalg.norm(quaternion))
    if not math.isfinite(norm) or norm < 1.0e-14:
        raise ForcedPropagationReplayError("QUATERNION_NORM_INVALID")
    return quaternion / norm


def _canonical_quaternion(value: Any, tolerance: float = 1.0e-15) -> np.ndarray:
    quaternion = _normalize_quaternion(value)
    if quaternion[0] < -tolerance:
        quaternion = -quaternion
    elif abs(float(quaternion[0])) <= tolerance:
        for component in quaternion[1:]:
            if abs(float(component)) > tolerance:
                if component < 0.0:
                    quaternion = -quaternion
                break
    return quaternion


def _quat_from_rotvec(value: Any) -> np.ndarray:
    vector = _array(value, (3,), "ROTATION_VECTOR")
    angle = float(np.linalg.norm(vector))
    if angle < 1.0e-14:
        return _normalize_quaternion(np.asarray((1.0, *(0.5 * vector))))
    axis = vector / angle
    return np.asarray((math.cos(0.5 * angle), *(axis * math.sin(0.5 * angle))))


def _quat_to_rotation(value: Any) -> np.ndarray:
    w, x, y, z = _normalize_quaternion(value)
    return np.asarray(
        (
            (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
            (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
            (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
        )
    )


def _axis_rotation(axis: Any, angle_rad: float) -> np.ndarray:
    direction = _array(axis, (3,), "ROTATION_AXIS")
    norm = float(np.linalg.norm(direction))
    if norm < 1.0e-14 or not math.isfinite(float(angle_rad)):
        raise ForcedPropagationReplayError("ROTATION_AXIS_OR_ANGLE_INVALID")
    direction /= norm
    cross = _skew(direction)
    return np.eye(3) + math.sin(angle_rad) * cross + (1.0 - math.cos(angle_rad)) * (cross @ cross)


_PALM_FIXED_ROTATION = _axis_rotation((0.0, 1.0, 0.0), -0.5 * math.pi)
_LEFT_LINK_ROTATION_PALM = _axis_rotation((0.0, 0.0, 1.0), -0.5 * math.pi)
_RIGHT_LINK_ROTATION_PALM = _axis_rotation((0.0, 0.0, 1.0), 0.5 * math.pi)


def _rotation_to_quaternion(value: Any) -> np.ndarray:
    rotation = _array(value, (3, 3), "ROTATION_MATRIX")
    trace = float(np.trace(rotation))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        quaternion = np.asarray(
            (
                0.25 * scale,
                (rotation[2, 1] - rotation[1, 2]) / scale,
                (rotation[0, 2] - rotation[2, 0]) / scale,
                (rotation[1, 0] - rotation[0, 1]) / scale,
            )
        )
    else:
        index = int(np.argmax(np.diag(rotation)))
        if index == 0:
            scale = math.sqrt(max(1.0 + rotation[0, 0] - rotation[1, 1] - rotation[2, 2], 0.0)) * 2.0
            quaternion = np.asarray(
                (
                    (rotation[2, 1] - rotation[1, 2]) / scale,
                    0.25 * scale,
                    (rotation[0, 1] + rotation[1, 0]) / scale,
                    (rotation[0, 2] + rotation[2, 0]) / scale,
                )
            )
        elif index == 1:
            scale = math.sqrt(max(1.0 + rotation[1, 1] - rotation[0, 0] - rotation[2, 2], 0.0)) * 2.0
            quaternion = np.asarray(
                (
                    (rotation[0, 2] - rotation[2, 0]) / scale,
                    (rotation[0, 1] + rotation[1, 0]) / scale,
                    0.25 * scale,
                    (rotation[1, 2] + rotation[2, 1]) / scale,
                )
            )
        else:
            scale = math.sqrt(max(1.0 + rotation[2, 2] - rotation[0, 0] - rotation[1, 1], 0.0)) * 2.0
            quaternion = np.asarray(
                (
                    (rotation[1, 0] - rotation[0, 1]) / scale,
                    (rotation[0, 2] + rotation[2, 0]) / scale,
                    (rotation[1, 2] + rotation[2, 1]) / scale,
                    0.25 * scale,
                )
            )
    return _canonical_quaternion(quaternion)


def _service_from_vector(value: Any) -> _ServiceState:
    vector = _array(value, (SERVICE_STATE_SIZE,), "SERVICE_STATE")
    return _ServiceState(
        vector[:3], _normalize_quaternion(vector[3:7]),
        vector[7:15], vector[15:29],
    )


def _frames(service: _ServiceState) -> _Frames:
    parent_position = service.position_m
    parent_rotation = _quat_to_rotation(service.quaternion_wxyz)
    joint_origins: list[np.ndarray] = []
    joint_axes: list[np.ndarray] = []
    link_origins: list[np.ndarray] = []
    link_rotations: list[np.ndarray] = []
    for index in range(6):
        joint_origin = parent_position + parent_rotation @ _ARM_JOINT_ORIGINS_PARENT_M[index]
        axis = parent_rotation @ _ARM_JOINT_AXES_PARENT[index]
        child_rotation = parent_rotation @ _axis_rotation(
            _ARM_JOINT_AXES_PARENT[index], float(service.joints_mixed[index])
        )
        joint_origins.append(joint_origin)
        joint_axes.append(axis)
        link_origins.append(joint_origin)
        link_rotations.append(child_rotation)
        parent_position = joint_origin + child_rotation @ _ARM_LINK_TIPS_BODY_M[index]
        parent_rotation = child_rotation
    palm_origin = parent_position + parent_rotation @ _PALM_FIXED_ORIGIN_PARENT_M
    palm_rotation = parent_rotation @ _PALM_FIXED_ROTATION
    left_joint = palm_origin + palm_rotation @ _LEFT_JOINT_ORIGIN_PALM_M
    right_joint = palm_origin + palm_rotation @ _RIGHT_JOINT_ORIGIN_PALM_M
    left_axis = palm_rotation @ _LEFT_AXIS_PALM
    right_axis = palm_rotation @ _RIGHT_AXIS_PALM
    left_link = left_joint + left_axis * float(service.joints_mixed[6])
    right_link = right_joint + right_axis * float(service.joints_mixed[7])
    return _Frames(
        tuple(joint_origins), tuple(joint_axes), tuple(link_origins),
        tuple(link_rotations), palm_origin, palm_rotation,
        left_joint, right_joint, left_axis, right_axis, left_link, right_link,
        palm_rotation @ _LEFT_LINK_ROTATION_PALM,
        palm_rotation @ _RIGHT_LINK_ROTATION_PALM,
    )


def _arm_point_jacobians(
    service: _ServiceState, frames: _Frames, point_m: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    jv = np.zeros((3, 14))
    jw = np.zeros((3, 14))
    jv[:, :3] = np.eye(3)
    jv[:, 3:6] = -_skew(point_m - service.position_m)
    jw[:, 3:6] = np.eye(3)
    for index in range(6):
        axis = frames.joint_axes[index]
        jv[:, 6 + index] = np.cross(
            axis, point_m - frames.joint_origins_m[index]
        )
        jw[:, 6 + index] = axis
    return jv, jw


def _bodies(service: _ServiceState) -> tuple[_Body, ...]:
    frames = _frames(service)
    base_rotation = _quat_to_rotation(service.quaternion_wxyz)
    base_jv = np.zeros((3, 14))
    base_jw = np.zeros((3, 14))
    base_jv[:, :3] = np.eye(3)
    base_jw[:, 3:6] = np.eye(3)
    result: list[_Body] = [
        _Body(
            _BASE_MASS_KG,
            base_rotation @ _BASE_INERTIA_BODY_KG_M2 @ base_rotation.T,
            service.position_m.copy(), base_jv, base_jw,
        )
    ]
    for index in range(6):
        rotation = frames.link_rotations[index]
        position = frames.link_origins_m[index] + rotation @ _ARM_LINK_COM_BODY_M[index]
        jv = np.zeros((3, 14))
        jw = np.zeros((3, 14))
        jv[:, :3] = np.eye(3)
        jv[:, 3:6] = -_skew(position - service.position_m)
        jw[:, 3:6] = np.eye(3)
        for joint in range(index + 1):
            axis = frames.joint_axes[joint]
            jv[:, 6 + joint] = np.cross(
                axis, position - frames.joint_origins_m[joint]
            )
            jw[:, 6 + joint] = axis
        result.append(
            _Body(
                float(_ARM_LINK_MASSES_KG[index]),
                rotation @ _ARM_LINK_INERTIAS_BODY_KG_M2[index] @ rotation.T,
                position, jv, jw,
            )
        )
    palm_position = frames.palm_origin_m + frames.palm_rotation @ _PALM_COM_BODY_M
    palm_jv, palm_jw = _arm_point_jacobians(service, frames, palm_position)
    result.append(
        _Body(
            _PALM_MASS_KG,
            frames.palm_rotation @ _PALM_INERTIA_BODY_KG_M2 @ frames.palm_rotation.T,
            palm_position, palm_jv, palm_jw,
        )
    )
    finger_rows = (
        (
            frames.left_link_origin_m, frames.left_link_rotation,
            _FINGER_MASSES_KG[0], _FINGER_COM_BODY_M[0],
            _FINGER_INERTIAS_BODY_KG_M2[0], 12, frames.left_axis,
        ),
        (
            frames.right_link_origin_m, frames.right_link_rotation,
            _FINGER_MASSES_KG[1], _FINGER_COM_BODY_M[1],
            _FINGER_INERTIAS_BODY_KG_M2[1], 13, frames.right_axis,
        ),
    )
    for origin, rotation, mass, com, inertia, column, axis in finger_rows:
        position = origin + rotation @ com
        jv, jw = _arm_point_jacobians(service, frames, position)
        jv[:, column] = axis
        result.append(
            _Body(
                float(mass), rotation @ inertia @ rotation.T,
                position, jv, jw,
            )
        )
    return tuple(result)


def _mass_matrix(service: _ServiceState) -> np.ndarray:
    matrix = np.zeros((14, 14))
    for body in _bodies(service):
        matrix += (
            body.mass_kg * body.jv.T @ body.jv
            + body.jw.T @ body.inertia_inertial_kg_m2 @ body.jw
        )
    return 0.5 * (matrix + matrix.T)


def _shift_state(
    service: _ServiceState, velocity: np.ndarray, delta_s: float,
) -> _ServiceState:
    increment = _quat_from_rotvec(delta_s * velocity[3:6])
    return _ServiceState(
        service.position_m + delta_s * velocity[:3],
        _normalize_quaternion(_quat_product(increment, service.quaternion_wxyz)),
        service.joints_mixed + delta_s * velocity[6:],
        velocity.copy(),
    )


def _bias_effort(
    service: _ServiceState,
    difference_step_s: float = REFERENCE_DIFFERENCE_STEP_S,
) -> np.ndarray:
    velocity = service.velocity_mixed
    present = _bodies(service)
    plus = _bodies(_shift_state(service, velocity, difference_step_s))
    minus = _bodies(_shift_state(service, velocity, -difference_step_s))
    bias = np.zeros(14)
    for body, body_plus, body_minus in zip(present, plus, minus):
        jv_dot = (body_plus.jv - body_minus.jv) / (2.0 * difference_step_s)
        jw_dot = (body_plus.jw - body_minus.jw) / (2.0 * difference_step_s)
        omega = body.jw @ velocity
        translational_bias = jv_dot @ velocity
        angular_bias = jw_dot @ velocity
        torque = (
            body.inertia_inertial_kg_m2 @ angular_bias
            + np.cross(omega, body.inertia_inertial_kg_m2 @ omega)
        )
        bias += (
            body.jv.T @ (body.mass_kg * translational_bias)
            + body.jw.T @ torque
        )
    return bias


def _snapshot(snapshot: Any) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(snapshot, Mapping):
        raise ForcedPropagationReplayError("SNAPSHOT_NOT_OBJECT")
    translation = _array(
        snapshot.get("translation_palm_to_target_m"), (3,),
        "SNAPSHOT_TRANSLATION",
    )
    rotation = _array(
        snapshot.get("rotation_palm_to_target"), (3, 3),
        "SNAPSHOT_ROTATION",
    )
    return translation, rotation


def _target_from_snapshot(
    service: _ServiceState, snapshot: Any,
) -> tuple[_TargetState, np.ndarray]:
    translation, relative_rotation = _snapshot(snapshot)
    frames = _frames(service)
    palm_jv, palm_jw = _arm_point_jacobians(
        service, frames, frames.palm_origin_m,
    )
    offset = frames.palm_rotation @ translation
    position = frames.palm_origin_m + offset
    rotation = frames.palm_rotation @ relative_rotation
    a_v = palm_jv - _skew(offset) @ palm_jw
    a = np.vstack((a_v, palm_jw))
    target = _TargetState(
        position, _rotation_to_quaternion(rotation),
        a @ service.velocity_mixed,
    )
    return target, a


def _target_spatial_mass(target: _TargetState) -> np.ndarray:
    rotation = _quat_to_rotation(target.quaternion_wxyz)
    inertia = rotation @ _TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    matrix = np.zeros((6, 6))
    matrix[:3, :3] = _TARGET_MASS_KG * np.eye(3)
    matrix[3:, 3:] = inertia
    return matrix


def _target_bias(target: _TargetState) -> np.ndarray:
    mass = _target_spatial_mass(target)
    omega = target.twist_mixed[3:]
    return np.concatenate(
        (np.zeros(3), np.cross(omega, mass[3:, 3:] @ omega))
    )


def _active_formula_terms(
    service: _ServiceState, snapshot: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, _TargetState, np.ndarray, np.ndarray]:
    target, a = _target_from_snapshot(service, snapshot)
    plus = _shift_state(
        service, service.velocity_mixed, REFERENCE_DIFFERENCE_STEP_S,
    )
    minus = _shift_state(
        service, service.velocity_mixed, -REFERENCE_DIFFERENCE_STEP_S,
    )
    _, a_plus = _target_from_snapshot(plus, snapshot)
    _, a_minus = _target_from_snapshot(minus, snapshot)
    adot_eta = (
        (a_plus - a_minus) / (2.0 * REFERENCE_DIFFERENCE_STEP_S)
    ) @ service.velocity_mixed
    service_mass = _mass_matrix(service)
    service_bias = _bias_effort(service)
    target_mass = _target_spatial_mass(target)
    target_bias = _target_bias(target)
    attached_mass = service_mass + a.T @ target_mass @ a
    attached_bias = service_bias + a.T @ (
        target_bias + target_mass @ adot_eta
    )
    return attached_mass, attached_bias, a, target, adot_eta, target_mass


def _cholesky_solve(matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    try:
        factor = np.linalg.cholesky(0.5 * (matrix + matrix.T))
        first = scipy_linalg.solve_triangular(factor, rhs, lower=True)
        return scipy_linalg.solve_triangular(factor.T, first, lower=False)
    except (np.linalg.LinAlgError, ValueError) as error:
        raise ForcedPropagationReplayError("SPD_CHOLESKY_SOLVE_FAILED") from error


def _command_force(
    command: Mapping[str, Any], acquisition_time_s: float,
    time_s: float, q_ref_N: float, dwell_q_index: int,
    dwell_window_s: tuple[float, float],
) -> np.ndarray:
    force = np.zeros(14)
    for output_index, side in ((12, "left"), (13, "right")):
        arm = command.get(side)
        if not isinstance(arm, Mapping):
            raise ForcedPropagationReplayError(f"COMMAND_ARM_NOT_OBJECT:{side}")
        alpha = _number(arm.get("alpha"), f"COMMAND_ALPHA_{side}")
        delay = _number(arm.get("delay_s"), f"COMMAND_DELAY_{side}")
        duration = _number(arm.get("duration_s"), f"COMMAND_DURATION_{side}")
        if alpha < 0.0 or delay < 0.0 or duration < 0.0:
            raise ForcedPropagationReplayError(f"COMMAND_ARM_NEGATIVE:{side}")
        elapsed = float(time_s) - float(acquisition_time_s) - delay
        if duration != 0.0 and elapsed > 0.0 and elapsed < duration:
            profile = math.sin(math.pi * elapsed / duration)
            force[output_index] = alpha * q_ref_N * profile * profile
    if dwell_window_s[0] <= float(time_s) <= dwell_window_s[1]:
        force[dwell_q_index] += q_ref_N
    return force


def _rhs(
    state_30: np.ndarray, *, time_s: float, stage_label: str,
    command: Mapping[str, Any], acquisition_time_s: float, snapshot: Any,
    q_ref_N: float, dwell_q_index: int,
    dwell_window_s: tuple[float, float],
) -> FrozenStageReplay:
    raw_state = _array(state_30, (STATE_SIZE,), "RHS_STATE")
    service = _service_from_vector(raw_state[:SERVICE_STATE_SIZE])
    force = _command_force(
        command, acquisition_time_s, time_s, q_ref_N,
        dwell_q_index, dwell_window_s,
    )
    mass, bias, _, _, _, _ = _active_formula_terms(service, snapshot)
    symmetric = 0.5 * (mass + mass.T)
    eigenvalues = np.linalg.eigvalsh(symmetric)
    if not np.all(np.isfinite(eigenvalues)) or float(eigenvalues[0]) <= 0.0:
        raise ForcedPropagationReplayError("ATTACHED_MASS_NOT_SPD")
    acceleration = _cholesky_solve(mass, force - bias)
    quaternion_rate = 0.5 * _quat_product(
        np.asarray((0.0, *service.velocity_mixed[3:6])),
        service.quaternion_wxyz,
    )
    power = float(force[12:14] @ service.velocity_mixed[12:14])
    derivative = np.concatenate(
        (
            service.velocity_mixed[:3], quaternion_rate,
            service.velocity_mixed[6:], acceleration,
            np.asarray((power,)),
        )
    )
    if derivative.shape != (STATE_SIZE,) or not np.all(np.isfinite(derivative)):
        raise ForcedPropagationReplayError("RHS_NONFINITE")
    cholesky = np.linalg.cholesky(symmetric)
    stage_code = 5 if stage_label.endswith("_MIDPOINT") else int(stage_label[-1])
    return FrozenStageReplay(
        stage_label, stage_code, float(time_s), raw_state, derivative, force,
        power, float(np.min(np.diag(cholesky))), float(eigenvalues[0]),
    )


def _momentum_energy(
    service: _ServiceState,
) -> tuple[np.ndarray, np.ndarray, float]:
    linear = np.zeros(3)
    angular = np.zeros(3)
    energy = 0.0
    for body in _bodies(service):
        velocity = body.jv @ service.velocity_mixed
        omega = body.jw @ service.velocity_mixed
        body_linear = body.mass_kg * velocity
        spin = body.inertia_inertial_kg_m2 @ omega
        linear += body_linear
        angular += np.cross(body.position_m, body_linear) + spin
        energy += 0.5 * body.mass_kg * float(velocity @ velocity)
        energy += 0.5 * float(omega @ spin)
    return linear, angular, float(energy)


def _target_momentum_energy(
    target: _TargetState,
) -> tuple[np.ndarray, np.ndarray, float]:
    rotation = _quat_to_rotation(target.quaternion_wxyz)
    inertia = rotation @ _TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    velocity = target.twist_mixed[:3]
    omega = target.twist_mixed[3:]
    linear = _TARGET_MASS_KG * velocity
    spin = inertia @ omega
    angular = np.cross(target.position_m, linear) + spin
    energy = (
        0.5 * _TARGET_MASS_KG * float(velocity @ velocity)
        + 0.5 * float(omega @ spin)
    )
    return linear, angular, float(energy)


def _block_diagonal(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    result = np.zeros(
        (left.shape[0] + right.shape[0], left.shape[1] + right.shape[1])
    )
    result[: left.shape[0], : left.shape[1]] = left
    result[left.shape[0] :, left.shape[1] :] = right
    return result


def _sample(
    state_30: np.ndarray, *, time_s: float, label: str,
    command: Mapping[str, Any], acquisition_time_s: float, snapshot: Any,
    q_ref_N: float, dwell_q_index: int,
    dwell_window_s: tuple[float, float], constants: Mapping[str, Any],
) -> tuple[FrozenStageReplay, dict[str, Any]]:
    raw_state = _array(state_30, (STATE_SIZE,), "SAMPLE_STATE")
    service = _service_from_vector(raw_state[:SERVICE_STATE_SIZE])
    force = _command_force(
        command, acquisition_time_s, time_s, q_ref_N,
        dwell_q_index, dwell_window_s,
    )
    mass, bias, a, target, adot_eta, target_mass = _active_formula_terms(
        service, snapshot,
    )
    acceleration = _cholesky_solve(mass, force - bias)
    target_acceleration = a @ acceleration + adot_eta
    service_mass = _mass_matrix(service)
    full_mass = _block_diagonal(service_mass, target_mass)
    full_bias = np.concatenate((_bias_effort(service), _target_bias(target)))
    full_acceleration = np.concatenate((acceleration, target_acceleration))
    full_applied = np.concatenate((force, np.zeros(6)))
    full_residual = full_mass @ full_acceleration + full_bias - full_applied
    embedding = np.vstack((np.eye(14), a))
    reduced_residual = embedding.T @ full_residual

    service_linear, service_angular, service_energy = _momentum_energy(service)
    target_linear, target_angular, target_energy = _target_momentum_energy(target)
    total_linear = service_linear + target_linear
    total_angular = service_angular + target_angular
    total_energy = service_energy + target_energy
    fixed_dissipation = float(constants["fixed_dissipation_J"])
    energy_minus_work = total_energy + fixed_dissipation - float(raw_state[WORK_INDEX])
    combined_velocity = np.concatenate(
        (service.velocity_mixed, target.twist_mixed)
    )
    power = float(force[12:14] @ service.velocity_mixed[12:14])
    symmetric = 0.5 * (mass + mass.T)
    cholesky = np.linalg.cholesky(symmetric)
    stage = FrozenStageReplay(
        label, 0, float(time_s), raw_state, None, force, power,
        float(np.min(np.diag(cholesky))), None,
    )
    ledgers = {
        "linear_momentum_drift_N_s": float(
            np.linalg.norm(total_linear - constants["linear_momentum"])
        ),
        "angular_momentum_drift_N_m_s": float(
            np.linalg.norm(total_angular - constants["angular_momentum"])
        ),
        "energy_minus_work_residual_J": abs(
            energy_minus_work - float(constants["energy_minus_work_J"])
        ),
        "ideal_constraint_power_W": abs(float(combined_velocity @ full_residual)),
        "active_contact_force_N": 0.0,
        "active_contact_torque_N_m": 0.0,
        "forced_full_residual_service_base_linear_N": float(np.max(np.abs(full_residual[0:3]))),
        "forced_full_residual_service_base_angular_N_m": float(np.max(np.abs(full_residual[3:6]))),
        "forced_full_residual_service_R_joint_N_m": float(np.max(np.abs(full_residual[6:12]))),
        "forced_full_residual_service_P_joint_N": float(np.max(np.abs(full_residual[12:14]))),
        "forced_full_residual_target_linear_N": float(np.max(np.abs(full_residual[14:17]))),
        "forced_full_residual_target_angular_N_m": float(np.max(np.abs(full_residual[17:20]))),
        "reduced_residual_base_linear_N": float(np.max(np.abs(reduced_residual[0:3]))),
        "reduced_residual_base_angular_N_m": float(np.max(np.abs(reduced_residual[3:6]))),
        "reduced_residual_R_joint_N_m": float(np.max(np.abs(reduced_residual[6:12]))),
        "reduced_residual_P_joint_N": float(np.max(np.abs(reduced_residual[12:14]))),
    }
    return stage, {
        "target_state_13": np.concatenate(
            (target.position_m, target.quaternion_wxyz, target.twist_mixed)
        ),
        "total_linear_momentum_N_s": total_linear,
        "total_angular_momentum_N_m_s": total_angular,
        "total_kinetic_energy_J": total_energy,
        "generalized_force_14": force,
        "actuator_power_W": power,
        "ledgers": ledgers,
    }


def replay_forced_propagation(
    *,
    time_s: Sequence[float],
    initial_state_30: Sequence[float],
    method: str,
    step_s: float,
    event: Mapping[str, Any],
    acquisition: Mapping[str, Any],
    command: Mapping[str, Any],
    q_ref_N: float,
    dwell_q_index: int,
    dwell_window_s: tuple[float, float],
) -> ForcedPropagationReplay:
    """Replay the complete frozen NC08 propagation from fresh initial truth."""

    grid = np.asarray(time_s, dtype=float)
    if grid.ndim != 1 or len(grid) < 2 or not np.all(np.isfinite(grid)):
        raise ForcedPropagationReplayError("TIME_GRID_INVALID")
    step = _number(step_s, "STEP")
    if step <= 0.0 or not np.array_equal(
        grid, float(grid[0]) + np.arange(len(grid), dtype=float) * step
    ):
        raise ForcedPropagationReplayError("TIME_GRID_NOT_FROZEN")
    if method not in ("rk4", "midpoint"):
        raise ForcedPropagationReplayError("METHOD_NOT_FROZEN")
    if dwell_q_index not in (12, 13):
        raise ForcedPropagationReplayError("DWELL_Q_INDEX_INVALID")
    q_ref = _number(q_ref_N, "Q_REF")
    if q_ref <= 0.0:
        raise ForcedPropagationReplayError("Q_REF_NOT_POSITIVE")
    acquisition_time = _number(
        acquisition.get("acquisition_time_s"), "ACQUISITION_TIME",
    )
    if float(grid[0]) != acquisition_time or event.get("time_s") != acquisition_time:
        raise ForcedPropagationReplayError("EVENT_ACQUISITION_GRID_TIME_MISMATCH")
    snapshot = acquisition.get("snapshot")
    _snapshot(snapshot)
    energy_audit = acquisition.get("energy_audit")
    if not isinstance(energy_audit, Mapping):
        raise ForcedPropagationReplayError("ENERGY_AUDIT_NOT_OBJECT")
    fixed_dissipation = (
        _number(event.get("b3_dissipation_J"), "EVENT_B3_DISSIPATION")
        + _number(energy_audit.get("D_switch_J"), "D_SWITCH")
    )

    initial = _array(initial_state_30, (STATE_SIZE,), "INITIAL_STATE")
    initial_service = _service_from_vector(initial[:SERVICE_STATE_SIZE])
    initial_target, _ = _target_from_snapshot(initial_service, snapshot)
    service_linear, service_angular, service_energy = _momentum_energy(
        initial_service,
    )
    target_linear, target_angular, target_energy = _target_momentum_energy(
        initial_target,
    )
    constants = {
        "linear_momentum": service_linear + target_linear,
        "angular_momentum": service_angular + target_angular,
        "fixed_dissipation_J": fixed_dissipation,
        "energy_minus_work_J": (
            service_energy + target_energy + fixed_dissipation
        ),
    }

    states: list[np.ndarray] = [initial]
    stages: list[FrozenStageReplay] = []
    samples: list[dict[str, Any]] = []
    accepted, sample = _sample(
        initial, time_s=float(grid[0]), label="ACCEPTED_SAMPLE_0",
        command=command, acquisition_time_s=acquisition_time,
        snapshot=snapshot, q_ref_N=q_ref, dwell_q_index=dwell_q_index,
        dwell_window_s=dwell_window_s, constants=constants,
    )
    stages.append(accepted)
    samples.append(sample)

    for index in range(len(grid) - 1):
        left_time = float(grid[index])
        left = states[-1]
        if method == "rk4":
            stage1 = _rhs(
                left, time_s=left_time, stage_label=f"STEP_{index}_K1",
                command=command, acquisition_time_s=acquisition_time,
                snapshot=snapshot, q_ref_N=q_ref,
                dwell_q_index=dwell_q_index, dwell_window_s=dwell_window_s,
            )
            k1 = stage1.derivative_30
            assert k1 is not None
            stage2_state = left + 0.5 * step * k1
            stage2 = _rhs(
                stage2_state, time_s=left_time + 0.5 * step,
                stage_label=f"STEP_{index}_K2", command=command,
                acquisition_time_s=acquisition_time, snapshot=snapshot,
                q_ref_N=q_ref, dwell_q_index=dwell_q_index,
                dwell_window_s=dwell_window_s,
            )
            k2 = stage2.derivative_30
            assert k2 is not None
            stage3_state = left + 0.5 * step * k2
            stage3 = _rhs(
                stage3_state, time_s=left_time + 0.5 * step,
                stage_label=f"STEP_{index}_K3", command=command,
                acquisition_time_s=acquisition_time, snapshot=snapshot,
                q_ref_N=q_ref, dwell_q_index=dwell_q_index,
                dwell_window_s=dwell_window_s,
            )
            k3 = stage3.derivative_30
            assert k3 is not None
            stage4_state = left + step * k3
            stage4 = _rhs(
                stage4_state, time_s=left_time + step,
                stage_label=f"STEP_{index}_K4", command=command,
                acquisition_time_s=acquisition_time, snapshot=snapshot,
                q_ref_N=q_ref, dwell_q_index=dwell_q_index,
                dwell_window_s=dwell_window_s,
            )
            k4 = stage4.derivative_30
            assert k4 is not None
            next_state = left + (step / 6.0) * (
                k1 + 2.0 * k2 + 2.0 * k3 + k4
            )
            stages.extend((stage1, stage2, stage3, stage4))
        else:
            stage1 = _rhs(
                left, time_s=left_time, stage_label=f"STEP_{index}_K1",
                command=command, acquisition_time_s=acquisition_time,
                snapshot=snapshot, q_ref_N=q_ref,
                dwell_q_index=dwell_q_index, dwell_window_s=dwell_window_s,
            )
            k1 = stage1.derivative_30
            assert k1 is not None
            midpoint_state = left + 0.5 * step * k1
            midpoint = _rhs(
                midpoint_state, time_s=left_time + 0.5 * step,
                stage_label=f"STEP_{index}_MIDPOINT", command=command,
                acquisition_time_s=acquisition_time, snapshot=snapshot,
                q_ref_N=q_ref, dwell_q_index=dwell_q_index,
                dwell_window_s=dwell_window_s,
            )
            midpoint_derivative = midpoint.derivative_30
            assert midpoint_derivative is not None
            next_state = left + step * midpoint_derivative
            stages.extend((stage1, midpoint))
        next_state = next_state.copy()
        next_state[3:7] = _canonical_quaternion(next_state[3:7])
        if not np.all(np.isfinite(next_state)):
            raise ForcedPropagationReplayError("STEP_RESULT_NONFINITE")
        states.append(next_state)
        accepted, sample = _sample(
            next_state, time_s=float(grid[index + 1]),
            label=f"ACCEPTED_SAMPLE_{index + 1}", command=command,
            acquisition_time_s=acquisition_time, snapshot=snapshot,
            q_ref_N=q_ref, dwell_q_index=dwell_q_index,
            dwell_window_s=dwell_window_s, constants=constants,
        )
        stages.append(accepted)
        samples.append(sample)

    state_array = np.asarray(states, dtype=float)
    ledger_arrays = {
        name: np.asarray([sample["ledgers"][name] for sample in samples])
        for name in LEDGER_NAMES
    }
    return ForcedPropagationReplay(
        state_30=state_array,
        command_Q_14=np.asarray(
            [sample["generalized_force_14"] for sample in samples]
        ),
        actuator_power_W=np.asarray(
            [sample["actuator_power_W"] for sample in samples]
        ),
        target_state_13=np.asarray(
            [sample["target_state_13"] for sample in samples]
        ),
        total_linear_momentum_N_s=np.asarray(
            [sample["total_linear_momentum_N_s"] for sample in samples]
        ),
        total_angular_momentum_N_m_s=np.asarray(
            [sample["total_angular_momentum_N_m_s"] for sample in samples]
        ),
        total_kinetic_energy_J=np.asarray(
            [sample["total_kinetic_energy_J"] for sample in samples]
        ),
        sample_ledgers=ledger_arrays,
        stages=tuple(stages),
    )


__all__ = [
    "ForcedPropagationReplay", "ForcedPropagationReplayError",
    "FrozenStageReplay", "LEDGER_NAMES", "replay_forced_propagation",
]
