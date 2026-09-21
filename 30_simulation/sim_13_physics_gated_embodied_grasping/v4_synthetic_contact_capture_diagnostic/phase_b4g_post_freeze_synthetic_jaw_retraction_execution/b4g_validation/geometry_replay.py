"""Independent, fail-closed geometry replay for the B4G evidence validator.

This module deliberately does not import the B3, B4E, or B4G solver/runtime
modules.  The small set of geometry equations needed by the evidence
validator is transcribed from five SHA-256-bound sources.  The public replay
functions accept only raw numerical records and reconstruct:

* the branched 6R fixed-palm / parallel-2P pad kinematics;
* the B4E snapshot-attached target pose and twist;
* the disabled-contact sphere gaps and normal gap rates; and
* the registered centred 2x2 P-to-gap Jacobian.

The active replay rebuilds the attached target after every P perturbation.
The post-release replay instead holds its independently propagated target
state fixed.  This distinction is part of the frozen B4G geometry semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


class GeometryReplayError(ValueError):
    """Fail-closed malformed-input, source-drift, or domain error."""


@dataclass(frozen=True)
class FrozenSourceBinding:
    source_id: str
    relative_path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class PalmKinematics:
    origin_inertial_m: np.ndarray
    rotation_body_to_inertial: np.ndarray
    translational_jacobian_mixed: np.ndarray
    angular_jacobian_mixed: np.ndarray


@dataclass(frozen=True)
class PadKinematics:
    side: str
    position_inertial_m: np.ndarray
    translational_jacobian_mixed: np.ndarray
    angular_jacobian_mixed: np.ndarray


@dataclass(frozen=True)
class GapRateReplay:
    gaps_m: np.ndarray
    gap_rates_m_s: np.ndarray


@dataclass(frozen=True)
class GapJacobianReplay:
    p_coordinates_m: np.ndarray
    centered_step_m: float
    raw_gap_jacobian_p: np.ndarray
    diagonal_derivatives: np.ndarray
    opening_signs: tuple[int, int]
    nominal_gaps_m: np.ndarray
    nominal_gap_rates_m_s: np.ndarray
    target_mode: str


@dataclass(frozen=True)
class MutationNoDomainGuardGeometryReplay:
    """Mutation-audit-only active geometry with the P-domain guard bypassed.

    This result can only diagnose that a clipping/extrapolation mutant reached
    the forbidden numerical branch.  It cannot make an out-of-domain state
    admissible and carries no campaign, selector, or physical credit.
    """

    p_coordinates_m: np.ndarray
    centered_step_m: float
    pad_positions_inertial_m: np.ndarray
    target_state_13: np.ndarray
    nominal_gaps_m: np.ndarray
    nominal_gap_rates_m_s: np.ndarray
    centered_minus_p_coordinates_m: np.ndarray
    centered_plus_p_coordinates_m: np.ndarray
    centered_minus_gaps_m: np.ndarray
    centered_plus_gaps_m: np.ndarray
    raw_gap_jacobian_p: np.ndarray


DIAGNOSTIC_RELATIVE_ROOT = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic"
)

FROZEN_SOURCE_BINDINGS: tuple[FrozenSourceBinding, ...] = (
    FrozenSourceBinding(
        "full_floating_geometry",
        f"{DIAGNOSTIC_RELATIVE_ROOT}/sim13_v4a/full_floating.py",
        40617,
        "3EC187C850F72EB1CAFF18713C71D6D0AC1773AF6C7AA8BFF4285FC26055C998",
    ),
    FrozenSourceBinding(
        "branched_gripper_geometry",
        (
            f"{DIAGNOSTIC_RELATIVE_ROOT}/"
            "phase_b3_branched_dual_contact_soft_capture/b3_contact/branched_model.py"
        ),
        14212,
        "21A3A5555215119684146FD2278181E70A0854ADF17A4A7B52E9DD3D954D5D96",
    ),
    FrozenSourceBinding(
        "dual_contact_gap_rate",
        (
            f"{DIAGNOSTIC_RELATIVE_ROOT}/"
            "phase_b3_branched_dual_contact_soft_capture/b3_contact/dual_contact_kernel.py"
        ),
        71290,
        "9D01439C8C658F95AB403C21752466D78018CC35701E7F4F54931B7228FF78B9",
    ),
    FrozenSourceBinding(
        "snapshot_attached_target",
        (
            f"{DIAGNOSTIC_RELATIVE_ROOT}/"
            "phase_b4_post_freeze_synthetic_6d_solver/b4_solver/constraint_solver.py"
        ),
        113625,
        "7AAF83E067019B3CA69FF78E61CADBC25BF9FAEC94699E7EA388859D8144295D",
    ),
    FrozenSourceBinding(
        "forced_retraction_geometry_semantics",
        (
            f"{DIAGNOSTIC_RELATIVE_ROOT}/"
            "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/"
            "b4g_solver/forced_retraction.py"
        ),
        53722,
        "E337E79F7F5D5095080ABDE93DF9982F80A0AD925E0F21FDA90D527AA075F239",
    ),
)

# Constants below are the geometry-only subset of the bound sources.
ARM_JOINT_AXES_PARENT: tuple[tuple[float, float, float], ...] = (
    (0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0),
    (0.0, 1.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (1.0, 0.0, 0.0),
)
ARM_JOINT_ORIGIN_OFFSETS_PARENT_M: tuple[tuple[float, float, float], ...] = (
    (0.19, 0.00, 0.11),
    (0.03, 0.01, 0.00),
    (0.02, -0.01, 0.01),
    (0.02, 0.00, 0.00),
    (0.01, 0.01, 0.00),
    (0.015, 0.00, 0.005),
)
ARM_LINK_TIP_OFFSETS_BODY_M: tuple[tuple[float, float, float], ...] = (
    (0.30, 0.00, 0.00),
    (0.27, 0.00, 0.00),
    (0.24, 0.00, 0.00),
    (0.20, 0.00, 0.00),
    (0.17, 0.00, 0.00),
    (0.14, 0.00, 0.00),
)
PALM_FIXED_ORIGIN_PARENT_M = (0.0, 0.0, 0.15971)
PALM_FIXED_ROTATION_AXIS = (0.0, 1.0, 0.0)
PALM_FIXED_ROTATION_ANGLE_RAD = -0.5 * math.pi
LEFT_P_AXIS_PALM = (0.0, -1.0, 0.0)
RIGHT_P_AXIS_PALM = (0.0, 1.0, 0.0)

SPHERE_RADIUS_M = 0.040
CLOSED_HALF_GAP_M = 0.010
PAD_X_PALM_M = -0.020
PAD_Z_PALM_M = 0.000
P_DOMAIN_M = ((0.0, 0.0715), (0.0, 0.0715))
REGISTERED_CENTERED_STEP_M = 1.0e-7
REGISTERED_OPENING_SIGNS = (1, 1)
UNIT_QUATERNION_TOLERANCE = 1.0e-9
ROTATION_MATRIX_TOLERANCE = 1.0e-12


def _default_project_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise GeometryReplayError("PROJECT_ROOT_NOT_FOUND")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def validate_frozen_source_bindings(
    project_root: Path | str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Verify exact path, byte count, and SHA-256 for all replay sources."""

    root = (
        _default_project_root()
        if project_root is None
        else Path(project_root).expanduser().resolve()
    )
    if not root.is_dir():
        raise GeometryReplayError("PROJECT_ROOT_NOT_DIRECTORY")
    resolved_root = root.resolve()
    records: list[dict[str, Any]] = []
    for binding in FROZEN_SOURCE_BINDINGS:
        path = (resolved_root / Path(binding.relative_path)).resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError as exc:
            raise GeometryReplayError(
                f"SOURCE_PATH_ESCAPES_PROJECT_ROOT:{binding.source_id}"
            ) from exc
        if not path.is_file():
            raise GeometryReplayError(f"SOURCE_MISSING:{binding.source_id}")
        actual_bytes = path.stat().st_size
        if actual_bytes != binding.bytes:
            raise GeometryReplayError(f"SOURCE_BYTE_DRIFT:{binding.source_id}")
        actual_sha256 = _sha256(path)
        if actual_sha256 != binding.sha256:
            raise GeometryReplayError(f"SOURCE_SHA256_DRIFT:{binding.source_id}")
        records.append(
            {
                "source_id": binding.source_id,
                "path": binding.relative_path,
                "bytes": actual_bytes,
                "sha256": actual_sha256,
            }
        )
    return tuple(records)


def frozen_constant_ledger() -> dict[str, Any]:
    """Return the immutable numerical constants consumed by this replay."""

    return {
        "arm_joint_axes_parent": [list(value) for value in ARM_JOINT_AXES_PARENT],
        "arm_joint_origin_offsets_parent_m": [
            list(value) for value in ARM_JOINT_ORIGIN_OFFSETS_PARENT_M
        ],
        "arm_link_tip_offsets_body_m": [
            list(value) for value in ARM_LINK_TIP_OFFSETS_BODY_M
        ],
        "palm_fixed_origin_parent_m": list(PALM_FIXED_ORIGIN_PARENT_M),
        "palm_fixed_rotation_axis": list(PALM_FIXED_ROTATION_AXIS),
        "palm_fixed_rotation_angle_rad": PALM_FIXED_ROTATION_ANGLE_RAD,
        "left_P_axis_palm": list(LEFT_P_AXIS_PALM),
        "right_P_axis_palm": list(RIGHT_P_AXIS_PALM),
        "sphere_radius_m": SPHERE_RADIUS_M,
        "closed_half_gap_m": CLOSED_HALF_GAP_M,
        "pad_x_palm_m": PAD_X_PALM_M,
        "pad_z_palm_m": PAD_Z_PALM_M,
        "P_domain_m": [list(value) for value in P_DOMAIN_M],
        "registered_centered_step_m": REGISTERED_CENTERED_STEP_M,
        "registered_opening_signs": list(REGISTERED_OPENING_SIGNS),
    }


def _finite_array(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise GeometryReplayError(f"{name}_NOT_NUMERICAL") from exc
    if array.shape != shape:
        raise GeometryReplayError(f"{name}_SHAPE")
    if not np.all(np.isfinite(array)):
        raise GeometryReplayError(f"{name}_NONFINITE")
    return array.copy()


def _strict_unit_quaternion(value: Any, name: str) -> np.ndarray:
    quaternion = _finite_array(value, (4,), name)
    norm = float(np.linalg.norm(quaternion))
    if not math.isfinite(norm) or norm < 1.0e-14:
        raise GeometryReplayError(f"{name}_ZERO_OR_NONFINITE_NORM")
    if abs(norm - 1.0) > UNIT_QUATERNION_TOLERANCE:
        raise GeometryReplayError(f"{name}_NOT_UNIT")
    return quaternion / norm


def _validate_service_state_29(
    value: Any, *, enforce_p_domain: bool,
) -> np.ndarray:
    state = _finite_array(value, (29,), "SERVICE_STATE_29")
    state[3:7] = _strict_unit_quaternion(state[3:7], "SERVICE_QUATERNION")
    if enforce_p_domain:
        for side, (coordinate, bounds) in enumerate(
            zip(state[13:15], P_DOMAIN_M)
        ):
            if coordinate < bounds[0] or coordinate > bounds[1]:
                raise GeometryReplayError(
                    f"P_COORDINATE_OUTSIDE_DOMAIN:{side}"
                )
    return state


def validate_service_state_29(value: Any) -> np.ndarray:
    return _validate_service_state_29(value, enforce_p_domain=True)


def validate_target_state_13(value: Any) -> np.ndarray:
    state = _finite_array(value, (13,), "TARGET_STATE_13")
    state[3:7] = _strict_unit_quaternion(state[3:7], "TARGET_QUATERNION")
    return state


def _skew(value: Any) -> np.ndarray:
    x, y, z = _finite_array(value, (3,), "SKEW_VECTOR")
    return np.array(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def _quaternion_to_rotation(value: Any) -> np.ndarray:
    w, x, y, z = _strict_unit_quaternion(value, "QUATERNION")
    return np.array(
        (
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
    )


def _axis_rotation(axis: Any, angle_rad: float) -> np.ndarray:
    direction = _finite_array(axis, (3,), "ROTATION_AXIS")
    angle = float(angle_rad)
    norm = float(np.linalg.norm(direction))
    if not math.isfinite(angle) or norm < 1.0e-14:
        raise GeometryReplayError("INVALID_AXIS_ROTATION")
    direction /= norm
    cross = _skew(direction)
    return (
        np.eye(3)
        + math.sin(angle) * cross
        + (1.0 - math.cos(angle)) * (cross @ cross)
    )


def _canonical_quaternion(value: Any, tolerance: float = 1.0e-15) -> np.ndarray:
    quaternion = _finite_array(value, (4,), "ROTATION_QUATERNION")
    norm = float(np.linalg.norm(quaternion))
    if not math.isfinite(norm) or norm < 1.0e-14:
        raise GeometryReplayError("ROTATION_QUATERNION_INVALID")
    quaternion /= norm
    if quaternion[0] < -tolerance:
        quaternion = -quaternion
    elif abs(quaternion[0]) <= tolerance:
        for component in quaternion[1:]:
            if abs(component) > tolerance:
                if component < 0.0:
                    quaternion = -quaternion
                break
    return quaternion


def _rotation_to_quaternion(value: Any) -> np.ndarray:
    rotation = _finite_array(value, (3, 3), "ROTATION_MATRIX")
    trace = float(np.trace(rotation))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        quaternion = np.array(
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
            scale = math.sqrt(
                max(
                    1.0
                    + rotation[0, 0]
                    - rotation[1, 1]
                    - rotation[2, 2],
                    0.0,
                )
            ) * 2.0
            quaternion = np.array(
                (
                    (rotation[2, 1] - rotation[1, 2]) / scale,
                    0.25 * scale,
                    (rotation[0, 1] + rotation[1, 0]) / scale,
                    (rotation[0, 2] + rotation[2, 0]) / scale,
                )
            )
        elif index == 1:
            scale = math.sqrt(
                max(
                    1.0
                    + rotation[1, 1]
                    - rotation[0, 0]
                    - rotation[2, 2],
                    0.0,
                )
            ) * 2.0
            quaternion = np.array(
                (
                    (rotation[0, 2] - rotation[2, 0]) / scale,
                    (rotation[0, 1] + rotation[1, 0]) / scale,
                    0.25 * scale,
                    (rotation[1, 2] + rotation[2, 1]) / scale,
                )
            )
        else:
            scale = math.sqrt(
                max(
                    1.0
                    + rotation[2, 2]
                    - rotation[0, 0]
                    - rotation[1, 1],
                    0.0,
                )
            ) * 2.0
            quaternion = np.array(
                (
                    (rotation[1, 0] - rotation[0, 1]) / scale,
                    (rotation[0, 2] + rotation[2, 0]) / scale,
                    (rotation[1, 2] + rotation[2, 1]) / scale,
                    0.25 * scale,
                )
            )
    return _canonical_quaternion(quaternion)


def _arm_and_palm_frames(
    service_state_29: Any,
    *,
    enforce_p_domain: bool = True,
) -> tuple[
    np.ndarray,
    np.ndarray,
    tuple[np.ndarray, ...],
    tuple[np.ndarray, ...],
]:
    state = _validate_service_state_29(
        service_state_29, enforce_p_domain=enforce_p_domain,
    )
    base_position = state[:3]
    parent_position = base_position.copy()
    parent_rotation = _quaternion_to_rotation(state[3:7])
    coordinates = state[7:15]
    joint_origins: list[np.ndarray] = []
    joint_axes: list[np.ndarray] = []
    for index in range(6):
        offset = np.asarray(ARM_JOINT_ORIGIN_OFFSETS_PARENT_M[index], dtype=float)
        axis_parent = np.asarray(ARM_JOINT_AXES_PARENT[index], dtype=float)
        joint_origin = parent_position + parent_rotation @ offset
        axis_inertial = parent_rotation @ axis_parent
        child_rotation = parent_rotation @ _axis_rotation(
            axis_parent, float(coordinates[index])
        )
        child_origin = joint_origin
        joint_origins.append(joint_origin)
        joint_axes.append(axis_inertial)
        parent_position = child_origin + child_rotation @ np.asarray(
            ARM_LINK_TIP_OFFSETS_BODY_M[index], dtype=float
        )
        parent_rotation = child_rotation
    palm_origin = parent_position + parent_rotation @ np.asarray(
        PALM_FIXED_ORIGIN_PARENT_M, dtype=float
    )
    palm_rotation = parent_rotation @ _axis_rotation(
        PALM_FIXED_ROTATION_AXIS, PALM_FIXED_ROTATION_ANGLE_RAD
    )
    return palm_origin, palm_rotation, tuple(joint_origins), tuple(joint_axes)


def _arm_point_jacobians(
    service_state_29: Any,
    point_inertial_m: Any,
    joint_origins: Sequence[np.ndarray],
    joint_axes: Sequence[np.ndarray],
    *,
    enforce_p_domain: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    state = _validate_service_state_29(
        service_state_29, enforce_p_domain=enforce_p_domain,
    )
    point = _finite_array(point_inertial_m, (3,), "POINT_INERTIAL_M")
    if len(joint_origins) != 6 or len(joint_axes) != 6:
        raise GeometryReplayError("ARM_FRAME_COUNT")
    jv = np.zeros((3, 14))
    jw = np.zeros((3, 14))
    jv[:, :3] = np.eye(3)
    jv[:, 3:6] = -_skew(point - state[:3])
    jw[:, 3:6] = np.eye(3)
    for index in range(6):
        axis = _finite_array(joint_axes[index], (3,), "JOINT_AXIS")
        origin = _finite_array(joint_origins[index], (3,), "JOINT_ORIGIN")
        jv[:, 6 + index] = np.cross(axis, point - origin)
        jw[:, 6 + index] = axis
    return jv, jw


def palm_kinematics(
    service_state_29: Any, *, _enforce_p_domain: bool = True,
) -> PalmKinematics:
    state = _validate_service_state_29(
        service_state_29, enforce_p_domain=_enforce_p_domain,
    )
    origin, rotation, joint_origins, joint_axes = _arm_and_palm_frames(
        state, enforce_p_domain=_enforce_p_domain,
    )
    jv, jw = _arm_point_jacobians(
        state, origin, joint_origins, joint_axes,
        enforce_p_domain=_enforce_p_domain,
    )
    return PalmKinematics(origin, rotation, jv, jw)


def pad_kinematics(
    service_state_29: Any, side: str, *, _enforce_p_domain: bool = True,
) -> PadKinematics:
    state = _validate_service_state_29(
        service_state_29, enforce_p_domain=_enforce_p_domain,
    )
    palm_origin, palm_rotation, joint_origins, joint_axes = _arm_and_palm_frames(
        state, enforce_p_domain=_enforce_p_domain,
    )
    if side == "left":
        coordinate = float(state[13])
        local = np.array(
            (PAD_X_PALM_M, -(CLOSED_HALF_GAP_M + coordinate), PAD_Z_PALM_M)
        )
        p_column = 12
        p_axis = palm_rotation @ np.asarray(LEFT_P_AXIS_PALM, dtype=float)
    elif side == "right":
        coordinate = float(state[14])
        local = np.array(
            (PAD_X_PALM_M, CLOSED_HALF_GAP_M + coordinate, PAD_Z_PALM_M)
        )
        p_column = 13
        p_axis = palm_rotation @ np.asarray(RIGHT_P_AXIS_PALM, dtype=float)
    else:
        raise GeometryReplayError("SIDE_MUST_BE_LEFT_OR_RIGHT")
    position = palm_origin + palm_rotation @ local
    jv, jw = _arm_point_jacobians(
        state, position, joint_origins, joint_axes,
        enforce_p_domain=_enforce_p_domain,
    )
    jv[:, p_column] = p_axis
    return PadKinematics(side, position, jv, jw)


def _snapshot_parts(snapshot: Any) -> tuple[np.ndarray, np.ndarray]:
    if isinstance(snapshot, Mapping):
        try:
            translation_value = snapshot["translation_palm_to_target_m"]
            rotation_value = snapshot["rotation_palm_to_target"]
        except KeyError as exc:
            raise GeometryReplayError("SNAPSHOT_FIELD_MISSING") from exc
    else:
        try:
            translation_value = snapshot.translation_palm_to_target_m
            rotation_value = snapshot.rotation_palm_to_target
        except AttributeError as exc:
            raise GeometryReplayError("SNAPSHOT_TYPE") from exc
    translation = _finite_array(
        translation_value, (3,), "SNAPSHOT_TRANSLATION_PALM_TO_TARGET_M"
    )
    rotation = _finite_array(
        rotation_value, (3, 3), "SNAPSHOT_ROTATION_PALM_TO_TARGET"
    )
    orthogonality = float(
        np.linalg.norm(rotation.T @ rotation - np.eye(3), ord=np.inf)
    )
    determinant = float(np.linalg.det(rotation))
    if (
        orthogonality > ROTATION_MATRIX_TOLERANCE
        or determinant <= 0.0
        or abs(determinant - 1.0) > ROTATION_MATRIX_TOLERANCE
    ):
        raise GeometryReplayError("SNAPSHOT_ROTATION_INVALID")
    return translation, rotation


def reconstruct_active_target_state_13(
    service_state_29: Any, snapshot: Any, *, _enforce_p_domain: bool = True,
) -> np.ndarray:
    """Rebuild the attached target from one service state and frozen snapshot."""

    state = _validate_service_state_29(
        service_state_29, enforce_p_domain=_enforce_p_domain,
    )
    translation, snapshot_rotation = _snapshot_parts(snapshot)
    palm = palm_kinematics(state, _enforce_p_domain=_enforce_p_domain)
    offset = palm.rotation_body_to_inertial @ translation
    target_position = palm.origin_inertial_m + offset
    target_rotation = palm.rotation_body_to_inertial @ snapshot_rotation
    target_jv = palm.translational_jacobian_mixed - _skew(
        offset
    ) @ palm.angular_jacobian_mixed
    attachment_map = np.vstack((target_jv, palm.angular_jacobian_mixed))
    target_twist = attachment_map @ state[15:29]
    return np.concatenate(
        (target_position, _rotation_to_quaternion(target_rotation), target_twist)
    )


def recompute_gap_rate(
    service_state_29: Any, target_state_13: Any, *,
    _enforce_p_domain: bool = True,
) -> GapRateReplay:
    """Recompute disabled-contact left/right sphere gaps and normal rates."""

    service = _validate_service_state_29(
        service_state_29, enforce_p_domain=_enforce_p_domain,
    )
    target = validate_target_state_13(target_state_13)
    gaps = np.empty(2)
    rates = np.empty(2)
    for index, side in enumerate(("left", "right")):
        pad = pad_kinematics(
            service, side, _enforce_p_domain=_enforce_p_domain,
        )
        radial = pad.position_inertial_m - target[:3]
        distance = float(np.linalg.norm(radial))
        if not math.isfinite(distance) or distance < 1.0e-12:
            raise GeometryReplayError("TARGET_CENTER_AND_PAD_COINCIDE")
        normal = radial / distance
        gap = distance - SPHERE_RADIUS_M
        common = target[:3] + SPHERE_RADIUS_M * normal
        pad_velocity = pad.translational_jacobian_mixed @ service[15:29]
        finger_omega = pad.angular_jacobian_mixed @ service[15:29]
        service_common_velocity = pad_velocity + np.cross(
            finger_omega, common - pad.position_inertial_m
        )
        target_common_velocity = target[7:10] + np.cross(
            target[10:13], common - target[:3]
        )
        relative_velocity = service_common_velocity - target_common_velocity
        gaps[index] = gap
        rates[index] = float(relative_velocity @ normal)
    if not np.all(np.isfinite(gaps)) or not np.all(np.isfinite(rates)):
        raise GeometryReplayError("NONFINITE_GAP_OR_RATE")
    return GapRateReplay(gaps, rates)


def recompute_active_gap_rate(
    service_state_29: Any, snapshot: Any, *, _enforce_p_domain: bool = True,
) -> GapRateReplay:
    target = reconstruct_active_target_state_13(
        service_state_29, snapshot, _enforce_p_domain=_enforce_p_domain,
    )
    return recompute_gap_rate(
        service_state_29, target, _enforce_p_domain=_enforce_p_domain,
    )


def recompute_mutation_only_no_domain_guard_active_geometry(
    service_state_29: Any,
    snapshot: Any,
    *,
    step_m: float = REGISTERED_CENTERED_STEP_M,
) -> MutationNoDomainGuardGeometryReplay:
    """Replay a forbidden clip/extrapolate branch without the P-domain guard.

    The bypass is intentionally confined to this mutation-audit helper.  Its
    output demonstrates that a mutant executed an inadmissible numerical path;
    it never changes the frozen G16 domain policy or makes the state eligible.
    """

    state = _validate_service_state_29(
        service_state_29, enforce_p_domain=False,
    )
    _snapshot_parts(snapshot)
    step = float(step_m)
    if not math.isfinite(step) or step <= 0.0:
        raise GeometryReplayError("INVALID_CENTERED_STEP")

    target = reconstruct_active_target_state_13(
        state, snapshot, _enforce_p_domain=False,
    )
    pads = np.vstack((
        pad_kinematics(
            state, "left", _enforce_p_domain=False,
        ).position_inertial_m,
        pad_kinematics(
            state, "right", _enforce_p_domain=False,
        ).position_inertial_m,
    ))
    nominal = recompute_gap_rate(
        state, target, _enforce_p_domain=False,
    )
    p_coordinates = state[13:15].copy()
    minus_p = np.tile(p_coordinates, (2, 1))
    plus_p = np.tile(p_coordinates, (2, 1))
    minus_gaps = np.empty((2, 2))
    plus_gaps = np.empty((2, 2))
    jacobian = np.empty((2, 2))
    for p_column in range(2):
        minus_state = state.copy()
        plus_state = state.copy()
        minus_state[13 + p_column] -= step
        plus_state[13 + p_column] += step
        minus_p[p_column] = minus_state[13:15]
        plus_p[p_column] = plus_state[13:15]
        # Active target reconstruction is repeated at each probe exactly as in
        # the frozen active-mode centred detector; only the domain guard is
        # bypassed for this negative-control evaluator.
        minus_gaps[p_column] = recompute_active_gap_rate(
            minus_state, snapshot, _enforce_p_domain=False,
        ).gaps_m
        plus_gaps[p_column] = recompute_active_gap_rate(
            plus_state, snapshot, _enforce_p_domain=False,
        ).gaps_m
        jacobian[:, p_column] = (
            plus_gaps[p_column] - minus_gaps[p_column]
        ) / (2.0 * step)
    arrays = (
        pads, target, nominal.gaps_m, nominal.gap_rates_m_s,
        minus_p, plus_p, minus_gaps, plus_gaps, jacobian,
    )
    if any(not np.all(np.isfinite(value)) for value in arrays):
        raise GeometryReplayError("NONFINITE_NO_DOMAIN_GUARD_GEOMETRY")
    return MutationNoDomainGuardGeometryReplay(
        p_coordinates_m=p_coordinates,
        centered_step_m=step,
        pad_positions_inertial_m=pads,
        target_state_13=target,
        nominal_gaps_m=nominal.gaps_m.copy(),
        nominal_gap_rates_m_s=nominal.gap_rates_m_s.copy(),
        centered_minus_p_coordinates_m=minus_p,
        centered_plus_p_coordinates_m=plus_p,
        centered_minus_gaps_m=minus_gaps,
        centered_plus_gaps_m=plus_gaps,
        raw_gap_jacobian_p=jacobian,
    )


def _with_p_coordinate(
    service_state_29: Any, p_column: int, coordinate_m: float
) -> np.ndarray:
    state = validate_service_state_29(service_state_29)
    if p_column not in (0, 1):
        raise GeometryReplayError("P_COLUMN_MUST_BE_ZERO_OR_ONE")
    coordinate = float(coordinate_m)
    if not math.isfinite(coordinate):
        raise GeometryReplayError("P_PERTURBATION_NONFINITE")
    state[13 + p_column] = coordinate
    return validate_service_state_29(state)


def centered_gap_jacobian(
    service_state_29: Any,
    *,
    snapshot: Any | None = None,
    independent_target_state_13: Any | None = None,
    step_m: float = REGISTERED_CENTERED_STEP_M,
) -> GapJacobianReplay:
    """Replay the full centred P-to-gap Jacobian with frozen target semantics.

    Exactly one target source is required.  ``snapshot`` selects active mode,
    where the target is reconstructed for the nominal and both perturbed
    states.  ``independent_target_state_13`` selects post-release mode, where
    the target remains fixed during the service P perturbations.
    """

    if (snapshot is None) == (independent_target_state_13 is None):
        raise GeometryReplayError("EXACTLY_ONE_TARGET_SOURCE_REQUIRED")
    state = validate_service_state_29(service_state_29)
    step = float(step_m)
    if not math.isfinite(step) or step <= 0.0:
        raise GeometryReplayError("INVALID_CENTERED_STEP")
    p_coordinates = state[13:15].copy()
    for side, (coordinate, bounds) in enumerate(zip(p_coordinates, P_DOMAIN_M)):
        if coordinate - step < bounds[0] or coordinate + step > bounds[1]:
            raise GeometryReplayError(
                f"CENTERED_PERTURBATION_OUTSIDE_DOMAIN:{side}"
            )

    if snapshot is not None:
        _snapshot_parts(snapshot)
        nominal = recompute_active_gap_rate(state, snapshot)
        target_mode = "ACTIVE_TARGET_REBUILT_FROM_SNAPSHOT"

        def evaluate(perturbed: np.ndarray) -> GapRateReplay:
            return recompute_active_gap_rate(perturbed, snapshot)

    else:
        fixed_target = validate_target_state_13(independent_target_state_13)
        nominal = recompute_gap_rate(state, fixed_target)
        target_mode = "POST_RELEASE_TARGET_FIXED_INDEPENDENTLY"

        def evaluate(perturbed: np.ndarray) -> GapRateReplay:
            return recompute_gap_rate(perturbed, fixed_target)

    jacobian = np.empty((2, 2))
    for p_column in range(2):
        coordinate = float(p_coordinates[p_column])
        minus = _with_p_coordinate(state, p_column, coordinate - step)
        plus = _with_p_coordinate(state, p_column, coordinate + step)
        minus_gaps = evaluate(minus).gaps_m
        plus_gaps = evaluate(plus).gaps_m
        jacobian[:, p_column] = (plus_gaps - minus_gaps) / (2.0 * step)
    if not np.all(np.isfinite(jacobian)):
        raise GeometryReplayError("NONFINITE_RAW_GAP_JACOBIAN")
    diagonal = np.diag(jacobian).copy()
    signs = tuple(int(np.sign(value)) for value in diagonal)
    return GapJacobianReplay(
        p_coordinates,
        step,
        jacobian,
        diagonal,
        signs,
        nominal.gaps_m.copy(),
        nominal.gap_rates_m_s.copy(),
        target_mode,
    )


def build_geometry_sign_fixture(
    service_state_29: Any,
    *,
    snapshot: Any | None = None,
    independent_target_state_13: Any | None = None,
    consumed_signs: Sequence[int] = REGISTERED_OPENING_SIGNS,
) -> dict[str, Any]:
    """Build a B4G/B4FNC04/B4FNC21-compatible raw geometry payload."""

    consumed = tuple(int(value) for value in consumed_signs)
    if len(consumed) != 2 or any(value not in (-1, 0, 1) for value in consumed):
        raise GeometryReplayError("INVALID_CONSUMED_OPENING_SIGNS")
    replay = centered_gap_jacobian(
        service_state_29,
        snapshot=snapshot,
        independent_target_state_13=independent_target_state_13,
        step_m=REGISTERED_CENTERED_STEP_M,
    )
    return {
        "P_coordinates_m": replay.p_coordinates_m.tolist(),
        "centered_step_m": replay.centered_step_m,
        "raw_gap_jacobian_P": replay.raw_gap_jacobian_p.tolist(),
        "registered_signs": list(REGISTERED_OPENING_SIGNS),
        "consumed_signs": list(consumed),
        "clipping_used": False,
        "extrapolation_used": False,
        "terminal_status": "INDEPENDENT_GEOMETRY_REPLAY_COMPLETE",
    }


__all__ = [
    "FROZEN_SOURCE_BINDINGS",
    "GapJacobianReplay",
    "GapRateReplay",
    "GeometryReplayError",
    "MutationNoDomainGuardGeometryReplay",
    "P_DOMAIN_M",
    "REGISTERED_CENTERED_STEP_M",
    "REGISTERED_OPENING_SIGNS",
    "build_geometry_sign_fixture",
    "centered_gap_jacobian",
    "frozen_constant_ledger",
    "pad_kinematics",
    "palm_kinematics",
    "recompute_active_gap_rate",
    "recompute_gap_rate",
    "recompute_mutation_only_no_domain_guard_active_geometry",
    "reconstruct_active_target_state_13",
    "validate_frozen_source_bindings",
    "validate_service_state_29",
    "validate_target_state_13",
]
