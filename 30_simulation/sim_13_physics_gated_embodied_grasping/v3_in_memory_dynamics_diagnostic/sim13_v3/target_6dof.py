"""Complete translational plus non-principal rotational target diagnostic."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from sim13_v2.free_floating_dynamics import (
    URDFDynamicsError,
    quaternion_to_rotation_body_to_inertial,
)


TARGET_BACKEND_SCOPE = "FREE_TARGET_6DOF_RK4_DIAGNOSTIC_NOT_CONTACT_NOT_CAPTURE"
INERTIA_SYMMETRY_ABSOLUTE_TOLERANCE_KG_M2 = 1.0e-13


def _vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise URDFDynamicsError(f"{field} must contain {size} finite values")
    return result


def _inertia(values: Sequence[Sequence[float]]) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (3, 3) or not np.all(np.isfinite(result)):
        raise URDFDynamicsError("target inertia must be a finite 3x3 matrix")
    if not np.allclose(
        result,
        result.T,
        atol=INERTIA_SYMMETRY_ABSOLUTE_TOLERANCE_KG_M2,
        rtol=0.0,
    ):
        raise URDFDynamicsError(
            "target inertia asymmetry exceeds the fail-closed absolute tolerance"
        )
    result = 0.5 * (result + result.T)
    if np.min(np.linalg.eigvalsh(result)) <= 0.0:
        raise URDFDynamicsError("target inertia must be positive definite")
    return result


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
class Target6DOFHistory:
    time_s: np.ndarray
    position_inertial_m: np.ndarray
    velocity_inertial_m_s: np.ndarray
    omega_body_rad_s: np.ndarray
    quaternion_body_to_inertial_wxyz: np.ndarray
    linear_momentum_inertial_kg_m_s: np.ndarray
    spin_angular_momentum_about_com_inertial: np.ndarray
    total_angular_momentum_about_inertial_origin: np.ndarray
    kinetic_energy_j: np.ndarray

    @property
    def angular_momentum_unit(self) -> str:
        return "N*m*s"


def _derivative(
    state: np.ndarray,
    mass_kg: float,
    inertia_body: np.ndarray,
    force_inertial_n: np.ndarray,
    torque_body_nm: np.ndarray,
) -> np.ndarray:
    velocity = state[3:6]
    omega = state[6:9]
    quaternion = state[9:13]
    quaternion = quaternion / np.linalg.norm(quaternion)
    omega_dot = np.linalg.solve(
        inertia_body,
        torque_body_nm - np.cross(omega, inertia_body @ omega),
    )
    quaternion_dot = 0.5 * _quat_product(quaternion, np.array((0.0, *omega)))
    return np.concatenate(
        (velocity, force_inertial_n / mass_kg, omega_dot, quaternion_dot)
    )


def propagate_target_6dof(
    mass_kg: float,
    inertia_body_kg_m2: Sequence[Sequence[float]],
    position_inertial_initial_m: Sequence[float],
    velocity_inertial_initial_m_s: Sequence[float],
    omega_body_initial_rad_s: Sequence[float],
    *,
    step_s: float,
    steps: int,
    quaternion_body_to_inertial_initial_wxyz: Sequence[float] = (1.0, 0.0, 0.0, 0.0),
    force_inertial_n: Sequence[float] = (0.0, 0.0, 0.0),
    torque_body_nm: Sequence[float] = (0.0, 0.0, 0.0),
) -> Target6DOFHistory:
    """Advance a free target in translation and non-principal rotation."""

    if not math.isfinite(mass_kg) or mass_kg <= 0.0:
        raise URDFDynamicsError("target mass must be positive and finite")
    if not math.isfinite(step_s) or step_s <= 0.0:
        raise URDFDynamicsError("step_s must be positive and finite")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise URDFDynamicsError("steps must be a positive integer")
    inertia = _inertia(inertia_body_kg_m2)
    position = _vector(position_inertial_initial_m, 3, "position")
    velocity = _vector(velocity_inertial_initial_m_s, 3, "velocity")
    omega = _vector(omega_body_initial_rad_s, 3, "omega")
    quaternion = _vector(
        quaternion_body_to_inertial_initial_wxyz, 4, "quaternion"
    )
    norm = float(np.linalg.norm(quaternion))
    if norm <= 0.0:
        raise URDFDynamicsError("quaternion norm must be nonzero")
    quaternion = quaternion / norm
    force = _vector(force_inertial_n, 3, "force")
    torque = _vector(torque_body_nm, 3, "torque")
    state = np.concatenate((position, velocity, omega, quaternion))

    time = np.arange(steps + 1, dtype=float) * step_s
    positions = np.empty((steps + 1, 3))
    velocities = np.empty((steps + 1, 3))
    omegas = np.empty((steps + 1, 3))
    quaternions = np.empty((steps + 1, 4))
    linear_momentum = np.empty((steps + 1, 3))
    spin_angular_momentum = np.empty((steps + 1, 3))
    total_angular_momentum_about_origin = np.empty((steps + 1, 3))
    energy = np.empty(steps + 1)

    for index in range(steps + 1):
        state[9:13] /= np.linalg.norm(state[9:13])
        position, velocity, omega, quaternion = (
            state[:3], state[3:6], state[6:9], state[9:13]
        )
        rotation = quaternion_to_rotation_body_to_inertial(quaternion)
        positions[index] = position
        velocities[index] = velocity
        omegas[index] = omega
        quaternions[index] = quaternion
        linear_momentum[index] = mass_kg * velocity
        spin_angular_momentum[index] = rotation @ (inertia @ omega)
        total_angular_momentum_about_origin[index] = (
            np.cross(position, linear_momentum[index])
            + spin_angular_momentum[index]
        )
        energy[index] = 0.5 * mass_kg * (velocity @ velocity) + 0.5 * omega @ inertia @ omega
        if index == steps:
            break
        k1 = _derivative(state, mass_kg, inertia, force, torque)
        k2 = _derivative(state + 0.5 * step_s * k1, mass_kg, inertia, force, torque)
        k3 = _derivative(state + 0.5 * step_s * k2, mass_kg, inertia, force, torque)
        k4 = _derivative(state + step_s * k3, mass_kg, inertia, force, torque)
        state = state + (step_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        state[9:13] /= np.linalg.norm(state[9:13])

    return Target6DOFHistory(
        time,
        positions,
        velocities,
        omegas,
        quaternions,
        linear_momentum,
        spin_angular_momentum,
        total_angular_momentum_about_origin,
        energy,
    )
