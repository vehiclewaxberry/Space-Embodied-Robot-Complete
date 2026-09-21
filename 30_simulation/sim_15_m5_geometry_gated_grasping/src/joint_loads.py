"""Hash-bound six-DOF geometric fastener-group load distribution.

This module evaluates the frozen M5 influence matrices and independently
reconstructs the applied wrench.  It is not a fastener strength, preload,
slip, plate-stress, or flight margin model.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


Wrench6 = tuple[float, float, float, float, float, float]
Vector3 = tuple[float, float, float]
CoordinateYZ = tuple[float, float]
InfluenceMatrix3x6 = tuple[
    tuple[float, float, float, float, float, float],
    tuple[float, float, float, float, float, float],
    tuple[float, float, float, float, float, float],
]

MODEL_SCOPE = (
    "GEOMETRIC_DIAGNOSTIC_WRENCH_DISTRIBUTION_ONLY_NOT_STRENGTH_OR_FLIGHT_MOS"
)
EXPECTED_PROHIBITED_USES = (
    "FASTENER_STRENGTH",
    "PRELOAD_MARGIN",
    "SLIP_OR_SEPARATION",
    "PLATE_STRESS",
    "FLIGHT_MOS",
)


class JointLoadModelError(ValueError):
    """Raised for a malformed frozen model or invalid distribution input."""


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{label} must be a finite real SI value")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must be a finite real SI value") from exc
    if not math.isfinite(number):
        raise JointLoadModelError(f"{label} must be finite")
    return number


def _wrench6(value: Any) -> Wrench6:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise TypeError("wrench_N_Nm must be a six-component SI sequence")
    if len(value) != 6:
        raise JointLoadModelError("wrench_N_Nm must contain exactly six components")
    components = tuple(_finite(item, f"wrench_N_Nm[{index}]") for index, item in enumerate(value))
    return (
        components[0],
        components[1],
        components[2],
        components[3],
        components[4],
        components[5],
    )


def _coordinate(value: Any, label: str) -> CoordinateYZ:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise JointLoadModelError(f"{label} must be [y,z] in metres")
    if len(value) != 2:
        raise JointLoadModelError(f"{label} must contain exactly y and z")
    return (_finite(value[0], f"{label}[0]"), _finite(value[1], f"{label}[1]"))


def _influence_matrix(value: Any, label: str) -> InfluenceMatrix3x6:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise JointLoadModelError(f"{label} must be a 3x6 matrix")
    if len(value) != 3:
        raise JointLoadModelError(f"{label} must have exactly three rows")
    rows: list[tuple[float, float, float, float, float, float]] = []
    for row_index, raw_row in enumerate(value):
        if isinstance(raw_row, (str, bytes, bytearray, Mapping)) or not isinstance(
            raw_row, Sequence
        ):
            raise JointLoadModelError(f"{label}[{row_index}] must be a sequence")
        if len(raw_row) != 6:
            raise JointLoadModelError(f"{label}[{row_index}] must have six terms")
        terms = tuple(
            _finite(term, f"{label}[{row_index}][{column}]")
            for column, term in enumerate(raw_row)
        )
        rows.append((terms[0], terms[1], terms[2], terms[3], terms[4], terms[5]))
    return (rows[0], rows[1], rows[2])


def _matvec(matrix: InfluenceMatrix3x6, wrench: Wrench6) -> Vector3:
    return (
        math.fsum(matrix[0][axis] * wrench[axis] for axis in range(6)),
        math.fsum(matrix[1][axis] * wrench[axis] for axis in range(6)),
        math.fsum(matrix[2][axis] * wrench[axis] for axis in range(6)),
    )


@dataclass(frozen=True)
class FastenerLoad:
    fastener_index: int
    coordinate_yz_m: CoordinateYZ
    force_N: Vector3
    axial_force_N: float
    shear_y_N: float
    shear_z_N: float
    shear_resultant_N: float
    total_resultant_N: float


@dataclass(frozen=True)
class JointLoadResult:
    pattern_id: str
    model_scope: str
    input_wrench_N_Nm: Wrench6
    fasteners: tuple[FastenerLoad, ...]
    reconstructed_wrench_N_Nm: Wrench6
    equilibrium_residual_N_Nm: Wrench6
    equilibrium_residual_norm: float
    coordinate_standard_uncertainty_m: None
    uncertainty_distribution: None
    uncertainty_degrees_of_freedom: None
    uncertainty_status: str
    prohibited_uses: tuple[str, ...]
    fastener_strength_margin: None = None
    preload_margin: None = None
    slip_or_separation_margin: None = None
    plate_stress_Pa: None = None
    flight_mos: None = None
    engineering_prediction: bool = False


class JointLoadDistributor:
    """Evaluate and equilibrium-check the frozen M5 influence matrices."""

    def __init__(self, authority: Any) -> None:
        try:
            model = authority.joint_load_model
        except AttributeError as exc:
            raise TypeError("authority must expose joint_load_model") from exc
        if not isinstance(model, Mapping):
            raise TypeError("authority.joint_load_model must be a mapping")
        if model.get("schema") != "M5_ANALYTIC_JOINT_LOAD_MODEL_V1":
            raise JointLoadModelError("unexpected joint-load model schema")
        expected_units = {
            "force": "N",
            "moment": "N*m",
            "coordinate": "m",
            "influence_moment_terms": "1/m",
        }
        if model.get("units") != expected_units:
            raise JointLoadModelError("joint-load model is not the strict SI contract")
        if model.get("allowed_use") != (
            "GEOMETRIC_WRENCH_DISTRIBUTION_SENSITIVITY_AND_SOFTWARE_VERIFICATION"
        ):
            raise JointLoadModelError("joint-load model scope changed")
        if tuple(model.get("prohibited_uses", ())) != EXPECTED_PROHIBITED_USES:
            raise JointLoadModelError("joint-load prohibited-use contract changed")
        patterns = model.get("patterns")
        if not isinstance(patterns, Mapping) or not patterns:
            raise JointLoadModelError("joint-load model has no frozen patterns")
        uncertainty = model.get("uncertainty")
        if not isinstance(uncertainty, Mapping):
            raise JointLoadModelError("joint-load uncertainty contract is absent")
        if any(
            uncertainty.get(key) is not None
            for key in (
                "coordinate_standard_uncertainty_m",
                "distribution",
                "degrees_of_freedom",
            )
        ):
            raise JointLoadModelError("diagnostic software may not invent uncertainty")
        self._model = model

    @property
    def pattern_ids(self) -> tuple[str, ...]:
        patterns = self._model["patterns"]
        return tuple(str(pattern_id) for pattern_id in patterns)

    def distribute(self, pattern_id: str, wrench_N_Nm: Any) -> JointLoadResult:
        if not isinstance(pattern_id, str):
            raise TypeError("pattern_id must be a string")
        patterns = self._model["patterns"]
        if pattern_id not in patterns:
            raise KeyError(f"unknown frozen joint pattern: {pattern_id}")
        wrench = _wrench6(wrench_N_Nm)
        pattern = patterns[pattern_id]
        if not isinstance(pattern, Mapping):
            raise JointLoadModelError(f"pattern {pattern_id} must be a mapping")
        raw_coordinates = pattern.get("coordinates_yz_m")
        raw_matrices = pattern.get("influence_matrices")
        if not isinstance(raw_coordinates, Sequence) or isinstance(
            raw_coordinates, (str, bytes, bytearray)
        ):
            raise JointLoadModelError(f"{pattern_id}.coordinates_yz_m is malformed")
        if not isinstance(raw_matrices, Sequence) or isinstance(
            raw_matrices, (str, bytes, bytearray)
        ):
            raise JointLoadModelError(f"{pattern_id}.influence_matrices is malformed")
        count = pattern.get("fastener_count")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise JointLoadModelError(f"{pattern_id}.fastener_count is invalid")
        if len(raw_coordinates) != count or len(raw_matrices) != count:
            raise JointLoadModelError(f"{pattern_id} frozen dimensions are inconsistent")

        coordinates = tuple(
            _coordinate(value, f"{pattern_id}.coordinates_yz_m[{index}]")
            for index, value in enumerate(raw_coordinates)
        )
        matrices = tuple(
            _influence_matrix(value, f"{pattern_id}.influence_matrices[{index}]")
            for index, value in enumerate(raw_matrices)
        )
        forces = tuple(_matvec(matrix, wrench) for matrix in matrices)
        fasteners = tuple(
            FastenerLoad(
                fastener_index=index + 1,
                coordinate_yz_m=coordinate,
                force_N=force,
                axial_force_N=force[0],
                shear_y_N=force[1],
                shear_z_N=force[2],
                shear_resultant_N=math.hypot(force[1], force[2]),
                total_resultant_N=math.sqrt(math.fsum(component * component for component in force)),
            )
            for index, (coordinate, force) in enumerate(
                zip(coordinates, forces, strict=True)
            )
        )

        axial = tuple(force[0] for force in forces)
        shear_y = tuple(force[1] for force in forces)
        shear_z = tuple(force[2] for force in forces)
        reconstructed: Wrench6 = (
            math.fsum(axial),
            math.fsum(shear_y),
            math.fsum(shear_z),
            math.fsum(
                coordinate[0] * qz - coordinate[1] * qy
                for coordinate, qy, qz in zip(
                    coordinates, shear_y, shear_z, strict=True
                )
            ),
            math.fsum(
                coordinate[1] * normal
                for coordinate, normal in zip(coordinates, axial, strict=True)
            ),
            -math.fsum(
                coordinate[0] * normal
                for coordinate, normal in zip(coordinates, axial, strict=True)
            ),
        )
        residual: Wrench6 = tuple(
            reconstructed[index] - wrench[index] for index in range(6)
        )  # type: ignore[assignment]
        uncertainty = self._model["uncertainty"]
        return JointLoadResult(
            pattern_id=pattern_id,
            model_scope=MODEL_SCOPE,
            input_wrench_N_Nm=wrench,
            fasteners=fasteners,
            reconstructed_wrench_N_Nm=reconstructed,
            equilibrium_residual_N_Nm=residual,
            equilibrium_residual_norm=math.sqrt(
                math.fsum(component * component for component in residual)
            ),
            coordinate_standard_uncertainty_m=None,
            uncertainty_distribution=None,
            uncertainty_degrees_of_freedom=None,
            uncertainty_status=str(uncertainty.get("status")),
            prohibited_uses=EXPECTED_PROHIBITED_USES,
        )


__all__ = [
    "FastenerLoad",
    "JointLoadDistributor",
    "JointLoadModelError",
    "JointLoadResult",
    "MODEL_SCOPE",
]
