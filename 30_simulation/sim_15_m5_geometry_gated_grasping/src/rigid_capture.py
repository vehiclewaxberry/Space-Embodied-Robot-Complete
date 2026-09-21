"""Self-contained rigid, perfectly-plastic capture diagnostic.

The solver conserves system linear and angular momentum at an instantaneous
kinematic weld.  It deliberately produces impulses only.  No contact duration,
force, pressure, compliance, restitution, or flexible response is inferred.
All public inputs and outputs use SI units.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


Vector3 = tuple[float, float, float]
Matrix3 = tuple[Vector3, Vector3, Vector3]
QuaternionXYZW = tuple[float, float, float, float]

MODEL_SCOPE = (
    "IDEAL_INSTANTANEOUS_RIGID_PLASTIC_CAPTURE_DIAGNOSTIC_NOT_CONTACT_FORCE"
)


class CaptureInputError(ValueError):
    """Raised when a rigid-body state is malformed or nonphysical."""


class ProhibitedPhysicsOperation(RuntimeError):
    """Raised when code attempts to promote an impulse into contact physics."""


def _finite_scalar(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{label} must be a real SI value, not bool")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must be a real SI value") from exc
    if not math.isfinite(number):
        raise CaptureInputError(f"{label} must be finite")
    return number


def _vector3(value: Any, label: str) -> Vector3:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise TypeError(f"{label} must be a length-three SI sequence")
    if len(value) != 3:
        raise CaptureInputError(f"{label} must contain exactly three components")
    return (
        _finite_scalar(value[0], f"{label}[0]"),
        _finite_scalar(value[1], f"{label}[1]"),
        _finite_scalar(value[2], f"{label}[2]"),
    )


def _matrix3(value: Any, label: str) -> Matrix3:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise TypeError(f"{label} must be a 3x3 SI matrix")
    if len(value) != 3:
        raise CaptureInputError(f"{label} must have exactly three rows")
    matrix = tuple(_vector3(row, f"{label}[{index}]") for index, row in enumerate(value))
    result: Matrix3 = (matrix[0], matrix[1], matrix[2])
    scale = max(1.0, *(abs(component) for row in result for component in row))
    tolerance = 1.0e-12 * scale
    for row in range(3):
        for column in range(row + 1, 3):
            if abs(result[row][column] - result[column][row]) > tolerance:
                raise CaptureInputError(f"{label} must be symmetric")
    leading_1 = result[0][0]
    leading_2 = result[0][0] * result[1][1] - result[0][1] * result[1][0]
    determinant = _determinant(result)
    if leading_1 <= 0.0 or leading_2 <= 0.0 or determinant <= 0.0:
        raise CaptureInputError(f"{label} must be symmetric positive definite")
    return result


def _quaternion(value: Any, label: str) -> QuaternionXYZW:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise TypeError(f"{label} must be a length-four xyzw sequence")
    if len(value) != 4:
        raise CaptureInputError(f"{label} must contain exactly four components")
    quaternion = tuple(
        _finite_scalar(component, f"{label}[{index}]")
        for index, component in enumerate(value)
    )
    norm = math.sqrt(math.fsum(component * component for component in quaternion))
    if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1.0e-10):
        raise CaptureInputError(f"{label} must be unit length; no silent normalization")
    return (quaternion[0], quaternion[1], quaternion[2], quaternion[3])


def _determinant(matrix: Matrix3) -> float:
    return (
        matrix[0][0]
        * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def _add(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[0] + right[0],
        left[1] + right[1],
        left[2] + right[2],
    )


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[0] - right[0],
        left[1] - right[1],
        left[2] - right[2],
    )


def _scale(value: Vector3, coefficient: float) -> Vector3:
    return (
        coefficient * value[0],
        coefficient * value[1],
        coefficient * value[2],
    )


def _dot(left: Vector3, right: Vector3) -> float:
    return math.fsum(left[index] * right[index] for index in range(3))


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _matvec(matrix: Matrix3, vector: Vector3) -> Vector3:
    return (
        math.fsum(matrix[0][index] * vector[index] for index in range(3)),
        math.fsum(matrix[1][index] * vector[index] for index in range(3)),
        math.fsum(matrix[2][index] * vector[index] for index in range(3)),
    )


def _matmul(left: Matrix3, right: Matrix3) -> Matrix3:
    rows = tuple(
        tuple(
            math.fsum(left[row][axis] * right[axis][column] for axis in range(3))
            for column in range(3)
        )
        for row in range(3)
    )
    return (rows[0], rows[1], rows[2])  # type: ignore[return-value]


def _transpose(matrix: Matrix3) -> Matrix3:
    return (
        (matrix[0][0], matrix[1][0], matrix[2][0]),
        (matrix[0][1], matrix[1][1], matrix[2][1]),
        (matrix[0][2], matrix[1][2], matrix[2][2]),
    )


def _matrix_add(left: Matrix3, right: Matrix3) -> Matrix3:
    rows = tuple(
        tuple(left[row][column] + right[row][column] for column in range(3))
        for row in range(3)
    )
    return (rows[0], rows[1], rows[2])  # type: ignore[return-value]


def _rotation_from_quaternion(quaternion: QuaternionXYZW) -> Matrix3:
    x, y, z, w = quaternion
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return (
        (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)),
        (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)),
        (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)),
    )


def _world_inertia(body: "RigidBodyState") -> Matrix3:
    rotation = _rotation_from_quaternion(body.quaternion_xyzw)
    return _matmul(_matmul(rotation, body.inertia_about_com_kg_m2), _transpose(rotation))


def _parallel_axis(mass_kg: float, offset_m: Vector3) -> Matrix3:
    radius_squared = _dot(offset_m, offset_m)
    return (
        (
            mass_kg * (radius_squared - offset_m[0] * offset_m[0]),
            -mass_kg * offset_m[0] * offset_m[1],
            -mass_kg * offset_m[0] * offset_m[2],
        ),
        (
            -mass_kg * offset_m[1] * offset_m[0],
            mass_kg * (radius_squared - offset_m[1] * offset_m[1]),
            -mass_kg * offset_m[1] * offset_m[2],
        ),
        (
            -mass_kg * offset_m[2] * offset_m[0],
            -mass_kg * offset_m[2] * offset_m[1],
            mass_kg * (radius_squared - offset_m[2] * offset_m[2]),
        ),
    )


def _solve_3x3(matrix: Matrix3, right_hand_side: Vector3) -> Vector3:
    """Solve a nonsingular 3x3 system with deterministic partial pivoting."""

    augmented = [
        [matrix[row][0], matrix[row][1], matrix[row][2], right_hand_side[row]]
        for row in range(3)
    ]
    scale = max(abs(value) for row in matrix for value in row)
    if scale == 0.0:
        raise CaptureInputError("combined inertia is singular")
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= scale * 1.0e-15:
            raise CaptureInputError("combined inertia is singular or ill-conditioned")
        if pivot != column:
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        for item in range(column, 4):
            augmented[column][item] /= divisor
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            for item in range(column, 4):
                augmented[row][item] -= factor * augmented[column][item]
    return (augmented[0][3], augmented[1][3], augmented[2][3])


@dataclass(frozen=True)
class RigidBodyState:
    """One rigid-body COM state in a shared inertial frame (strict SI)."""

    mass_kg: float
    inertia_about_com_kg_m2: Matrix3
    position_m: Vector3
    linear_velocity_mps: Vector3
    angular_velocity_radps: Vector3
    quaternion_xyzw: QuaternionXYZW = (0.0, 0.0, 0.0, 1.0)

    def __post_init__(self) -> None:
        mass = _finite_scalar(self.mass_kg, "mass_kg")
        if mass <= 0.0:
            raise CaptureInputError("mass_kg must be strictly positive")
        object.__setattr__(self, "mass_kg", mass)
        object.__setattr__(
            self,
            "inertia_about_com_kg_m2",
            _matrix3(self.inertia_about_com_kg_m2, "inertia_about_com_kg_m2"),
        )
        object.__setattr__(self, "position_m", _vector3(self.position_m, "position_m"))
        object.__setattr__(
            self,
            "linear_velocity_mps",
            _vector3(self.linear_velocity_mps, "linear_velocity_mps"),
        )
        object.__setattr__(
            self,
            "angular_velocity_radps",
            _vector3(self.angular_velocity_radps, "angular_velocity_radps"),
        )
        object.__setattr__(
            self,
            "quaternion_xyzw",
            _quaternion(self.quaternion_xyzw, "quaternion_xyzw"),
        )


@dataclass(frozen=True)
class CaptureResult:
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
    service_com_linear_impulse_N_s: Vector3
    target_com_linear_impulse_N_s: Vector3
    service_com_angular_impulse_N_m_s: Vector3
    target_com_angular_impulse_N_m_s: Vector3
    kinetic_energy_before_J: float
    kinetic_energy_after_J: float
    plastic_energy_loss_J: float
    contact_force_N: None = None
    contact_pressure_Pa: None = None
    contact_duration_s: None = None
    physical_contact_computed: bool = False
    engineering_prediction: bool = False


def _required_alias(record: Mapping[str, Any], canonical: str, fixture_name: str) -> Any:
    present = [name for name in (canonical, fixture_name) if name in record]
    if not present:
        raise KeyError(f"missing required SI field: {fixture_name}")
    if len(present) == 2 and record[canonical] != record[fixture_name]:
        raise CaptureInputError(f"conflicting {canonical} and {fixture_name} values")
    return record[present[0]]


def body_from_mapping(record: Mapping[str, Any]) -> RigidBodyState:
    """Parse an explicit-SI fixture record into a validated rigid-body state."""

    if not isinstance(record, Mapping):
        raise TypeError("rigid-body record must be a mapping")
    if "mass_kg" not in record:
        raise KeyError("missing required SI field: mass_kg")
    if "inertia_about_com_kg_m2" not in record:
        raise KeyError("missing required SI field: inertia_about_com_kg_m2")
    quaternion = record.get(
        "quaternion_xyzw", record.get("initial_quaternion_xyzw", (0.0, 0.0, 0.0, 1.0))
    )
    return RigidBodyState(
        mass_kg=record["mass_kg"],
        inertia_about_com_kg_m2=record["inertia_about_com_kg_m2"],
        position_m=_required_alias(record, "position_m", "initial_position_m"),
        linear_velocity_mps=_required_alias(
            record, "linear_velocity_mps", "initial_linear_velocity_mps"
        ),
        angular_velocity_radps=_required_alias(
            record, "angular_velocity_radps", "initial_angular_velocity_radps"
        ),
        quaternion_xyzw=quaternion,
    )


class RigidPlasticCaptureSolver:
    """Instantaneous two-body rigid plastic-capture momentum diagnostic."""

    def capture(
        self,
        service: RigidBodyState | Mapping[str, Any],
        target: RigidBodyState | Mapping[str, Any],
    ) -> CaptureResult:
        service_body = (
            service if isinstance(service, RigidBodyState) else body_from_mapping(service)
        )
        target_body = (
            target if isinstance(target, RigidBodyState) else body_from_mapping(target)
        )
        bodies = (service_body, target_body)
        total_mass = math.fsum(body.mass_kg for body in bodies)
        center_of_mass = tuple(
            math.fsum(body.mass_kg * body.position_m[axis] for body in bodies)
            / total_mass
            for axis in range(3)
        )
        center_of_mass_m: Vector3 = (
            center_of_mass[0],
            center_of_mass[1],
            center_of_mass[2],
        )

        linear_momentum_before = tuple(
            math.fsum(
                body.mass_kg * body.linear_velocity_mps[axis] for body in bodies
            )
            for axis in range(3)
        )
        p_before: Vector3 = (
            linear_momentum_before[0],
            linear_momentum_before[1],
            linear_momentum_before[2],
        )
        combined_linear_velocity = _scale(p_before, 1.0 / total_mass)

        world_inertias = (_world_inertia(service_body), _world_inertia(target_body))
        offsets = (
            _subtract(service_body.position_m, center_of_mass_m),
            _subtract(target_body.position_m, center_of_mass_m),
        )
        combined_inertia = _matrix_add(
            _matrix_add(
                world_inertias[0], _parallel_axis(service_body.mass_kg, offsets[0])
            ),
            _matrix_add(
                world_inertias[1], _parallel_axis(target_body.mass_kg, offsets[1])
            ),
        )

        angular_terms = []
        for body, inertia, offset in zip(bodies, world_inertias, offsets, strict=True):
            spin = _matvec(inertia, body.angular_velocity_radps)
            orbital = _cross(offset, _scale(body.linear_velocity_mps, body.mass_kg))
            angular_terms.append(_add(spin, orbital))
        angular_momentum_before: Vector3 = tuple(
            math.fsum(term[axis] for term in angular_terms) for axis in range(3)
        )  # type: ignore[assignment]
        combined_angular_velocity = _solve_3x3(
            combined_inertia, angular_momentum_before
        )

        post_com_velocities = tuple(
            _add(combined_linear_velocity, _cross(combined_angular_velocity, offset))
            for offset in offsets
        )
        linear_impulses = tuple(
            _scale(
                _subtract(post_velocity, body.linear_velocity_mps), body.mass_kg
            )
            for body, post_velocity in zip(bodies, post_com_velocities, strict=True)
        )
        angular_impulses = tuple(
            _matvec(
                inertia,
                _subtract(combined_angular_velocity, body.angular_velocity_radps),
            )
            for body, inertia in zip(bodies, world_inertias, strict=True)
        )

        linear_momentum_after: Vector3 = tuple(
            math.fsum(
                body.mass_kg * post_velocity[axis]
                for body, post_velocity in zip(bodies, post_com_velocities, strict=True)
            )
            for axis in range(3)
        )  # type: ignore[assignment]
        angular_momentum_after = _matvec(
            combined_inertia, combined_angular_velocity
        )
        linear_residual = _subtract(linear_momentum_after, p_before)
        angular_residual = _subtract(
            angular_momentum_after, angular_momentum_before
        )

        kinetic_energy_before = math.fsum(
            0.5 * body.mass_kg * _dot(body.linear_velocity_mps, body.linear_velocity_mps)
            + 0.5
            * _dot(
                body.angular_velocity_radps,
                _matvec(inertia, body.angular_velocity_radps),
            )
            for body, inertia in zip(bodies, world_inertias, strict=True)
        )
        kinetic_energy_after = 0.5 * total_mass * _dot(
            combined_linear_velocity, combined_linear_velocity
        ) + 0.5 * _dot(
            combined_angular_velocity,
            _matvec(combined_inertia, combined_angular_velocity),
        )
        energy_loss = kinetic_energy_before - kinetic_energy_after
        tolerance = 1.0e-12 * max(1.0, kinetic_energy_before, kinetic_energy_after)
        if energy_loss < -tolerance:
            raise ArithmeticError("plastic capture unexpectedly created kinetic energy")
        if energy_loss < 0.0:
            energy_loss = 0.0

        return CaptureResult(
            model_scope=MODEL_SCOPE,
            total_mass_kg=total_mass,
            combined_center_of_mass_m=center_of_mass_m,
            combined_linear_velocity_mps=combined_linear_velocity,
            combined_angular_velocity_radps=combined_angular_velocity,
            combined_inertia_about_com_kg_m2=combined_inertia,
            linear_momentum_before_kg_mps=p_before,
            linear_momentum_after_kg_mps=linear_momentum_after,
            angular_momentum_before_kg_m2ps=angular_momentum_before,
            angular_momentum_after_kg_m2ps=angular_momentum_after,
            linear_momentum_residual_kg_mps=linear_residual,
            angular_momentum_residual_kg_m2ps=angular_residual,
            linear_residual_norm_kg_mps=math.sqrt(_dot(linear_residual, linear_residual)),
            angular_residual_norm_kg_m2ps=math.sqrt(
                _dot(angular_residual, angular_residual)
            ),
            service_com_linear_impulse_N_s=linear_impulses[0],
            target_com_linear_impulse_N_s=linear_impulses[1],
            service_com_angular_impulse_N_m_s=angular_impulses[0],
            target_com_angular_impulse_N_m_s=angular_impulses[1],
            kinetic_energy_before_J=kinetic_energy_before,
            kinetic_energy_after_J=kinetic_energy_after,
            plastic_energy_loss_J=energy_loss,
        )


def impulse_to_force(*_args: Any, **_kwargs: Any) -> None:
    """Always reject impulse-to-force conversion without a physical time history."""

    raise ProhibitedPhysicsOperation(
        "Impulse is N*s and cannot be divided by an invented duration to claim "
        "contact force; contact_force_N remains None until physical identification."
    )


def junction_couple_impulse_at_point(
    *,
    com_angular_impulse_N_m_s: Sequence[float],
    com_linear_impulse_N_s: Sequence[float],
    body_com_position_m: Sequence[float],
    junction_point_m: Sequence[float],
) -> Vector3:
    """Shift a body's COM angular impulse to an explicit junction point.

    ``L_at_p = dL_com - (p-r_com) x J``.  This does not create force or
    pressure; it only changes the reference point of the impulse wrench.
    """

    angular = _vector3(com_angular_impulse_N_m_s, "com_angular_impulse_N_m_s")
    linear = _vector3(com_linear_impulse_N_s, "com_linear_impulse_N_s")
    center = _vector3(body_com_position_m, "body_com_position_m")
    junction = _vector3(junction_point_m, "junction_point_m")
    lever = _subtract(junction, center)
    return _subtract(angular, _cross(lever, linear))


__all__ = [
    "CaptureInputError",
    "CaptureResult",
    "MODEL_SCOPE",
    "ProhibitedPhysicsOperation",
    "RigidBodyState",
    "RigidPlasticCaptureSolver",
    "body_from_mapping",
    "impulse_to_force",
    "junction_couple_impulse_at_point",
]
