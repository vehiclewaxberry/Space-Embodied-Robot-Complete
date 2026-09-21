"""Zero-momentum reduced dynamics for a generic free-floating tree.

This module uses mixed generalized coordinates.  Revolute coordinates use
rad, rad/s and N*m; prismatic coordinates use m, m/s and N.  Consequently the
mass matrix has mixed block units and is never labelled with one global unit.
Centered two-step Richardson derivatives supply an independent numerical
Christoffel diagnostic.  Nothing here is a production or contact backend.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sys
from typing import Callable, Sequence

import numpy as np


V3_ROOT = Path(__file__).resolve().parents[1]
V2_ROOT = V3_ROOT.parent / "v2_system_rebind"
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from sim13_v2.free_floating_dynamics import (
    URDFDynamicsError,
    URDFTreeDynamics,
    quaternion_to_rotation_body_to_inertial,
)


BACKEND_SCOPE = "SYNTHETIC_ONLY_ZERO_MOMENTUM_REDUCED_RICHARDSON_DIAGNOSTIC"
CHRISTOFFEL_BACKEND = "TWO_STEP_CENTERED_RICHARDSON_PER_COORDINATE_DIAGNOSTIC_NOT_PRODUCTION"
PRODUCTION_DYNAMICS_GATE_PASSED = False
CURRENT_SYSTEM_BINDING_PASSED = False

REVOLUTE_DIFFERENCE_STEP_RAD = 2.0e-5
PRISMATIC_DIFFERENCE_STEP_M = 2.0e-6

MASS_MATRIX_BLOCK_UNIT_CONTRACT = {
    "BASE_LINEAR__BASE_LINEAR": "kg",
    "BASE_LINEAR__BASE_ANGULAR": "kg*m",
    "BASE_LINEAR__REVOLUTE": "kg*m",
    "BASE_LINEAR__PRISMATIC": "kg",
    "BASE_ANGULAR__BASE_ANGULAR": "kg*m^2",
    "BASE_ANGULAR__REVOLUTE": "kg*m^2",
    "BASE_ANGULAR__PRISMATIC": "kg*m",
    "REVOLUTE__REVOLUTE": "kg*m^2",
    "REVOLUTE__PRISMATIC": "kg*m",
    "PRISMATIC__PRISMATIC": "kg",
    "symmetry_rule": "M_ji has the same block unit as M_ij",
    "global_single_unit": None,
}


def _vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise URDFDynamicsError(f"{field} must contain {size} finite values")
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


def generalized_coordinate_contract(model: URDFTreeDynamics) -> list[dict[str, object]]:
    """Declare coordinate, rate, effort and conjugate-momentum units."""

    contract: list[dict[str, object]] = []
    for index, axis in enumerate(("x", "y", "z")):
        contract.append(
            {
                "index": index,
                "name": f"base_translation_{axis}",
                "coordinate_type": "BASE_LINEAR",
                "coordinate_unit": "m",
                "rate_unit": "m/s",
                "generalized_effort_unit": "N",
                "conjugate_momentum_unit": "N*s",
            }
        )
    for local_index, axis in enumerate(("x", "y", "z"), start=3):
        contract.append(
            {
                "index": local_index,
                "name": f"base_rotation_{axis}",
                "coordinate_type": "BASE_ANGULAR",
                "coordinate_unit": "rad",
                "rate_unit": "rad/s",
                "generalized_effort_unit": "N*m",
                "conjugate_momentum_unit": "N*m*s",
            }
        )
    for joint_index, joint in enumerate(model.movable_joints):
        revolute = joint.joint_type == "revolute"
        contract.append(
            {
                "index": 6 + joint_index,
                "joint_index": joint_index,
                "name": joint.name,
                "coordinate_type": "REVOLUTE" if revolute else "PRISMATIC",
                "coordinate_unit": "rad" if revolute else "m",
                "rate_unit": "rad/s" if revolute else "m/s",
                "acceleration_unit": "rad/s^2" if revolute else "m/s^2",
                "generalized_effort_unit": "N*m" if revolute else "N",
                "conjugate_momentum_unit": "N*m*s" if revolute else "N*s",
            }
        )
    return contract


@dataclass(frozen=True)
class DerivativeDiagnostic:
    derivatives_mixed_units: np.ndarray
    per_coordinate_coarse_step: np.ndarray
    per_coordinate_fine_step: np.ndarray
    per_coordinate_relative_consistency: np.ndarray
    per_coordinate_step_units: tuple[str, ...]


@dataclass(frozen=True)
class ForwardDynamicsState:
    reduced_mass_mixed_units: np.ndarray
    generalized_bias_effort_mixed_units: np.ndarray
    generalized_acceleration_mixed_units: np.ndarray
    base_twist_body: np.ndarray
    base_twist_component_derivative: np.ndarray
    full_velocity_mixed_units: np.ndarray
    full_acceleration_components_mixed_units: np.ndarray
    linear_momentum_residual_ns: float
    angular_momentum_about_root_residual_nms: float


@dataclass(frozen=True)
class ReducedDynamicsHistory:
    time_s: np.ndarray
    generalized_coordinates_mixed_units: np.ndarray
    generalized_rates_mixed_units: np.ndarray
    base_position_inertial_m: np.ndarray
    base_quaternion_body_to_inertial_wxyz: np.ndarray
    base_twist_body_mixed_units: np.ndarray
    kinetic_energy_j: np.ndarray
    generalized_work_j: np.ndarray
    linear_momentum_residual_ns: np.ndarray
    angular_momentum_about_root_residual_nms: np.ndarray

    @property
    def q(self) -> np.ndarray:
        return self.generalized_coordinates_mixed_units

    @property
    def qdot(self) -> np.ndarray:
        return self.generalized_rates_mixed_units


class ZeroMomentumReducedDynamics:
    """Diagnostic shape-space dynamics for an in-memory tree model."""

    def __init__(
        self,
        model: URDFTreeDynamics,
        *,
        revolute_difference_step_rad: float = REVOLUTE_DIFFERENCE_STEP_RAD,
        prismatic_difference_step_m: float = PRISMATIC_DIFFERENCE_STEP_M,
    ):
        if model.movable_dof < 1:
            raise URDFDynamicsError("at least one movable joint is required")
        for value, field in (
            (revolute_difference_step_rad, "revolute_difference_step_rad"),
            (prismatic_difference_step_m, "prismatic_difference_step_m"),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise URDFDynamicsError(f"{field} must be positive and finite")
        self.model = model
        self.dof = model.movable_dof
        self.revolute_difference_step_rad = float(revolute_difference_step_rad)
        self.prismatic_difference_step_m = float(prismatic_difference_step_m)
        self.revolute_indices = tuple(
            index
            for index, joint in enumerate(model.movable_joints)
            if joint.joint_type == "revolute"
        )
        self.prismatic_indices = tuple(
            index
            for index, joint in enumerate(model.movable_joints)
            if joint.joint_type == "prismatic"
        )
        self.coordinate_contract = generalized_coordinate_contract(model)

    def _q(self, values: Sequence[float]) -> np.ndarray:
        return _vector(values, self.dof, "generalized_coordinates")

    def _qdot(self, values: Sequence[float]) -> np.ndarray:
        return _vector(values, self.dof, "generalized_rates")

    def _step_for_coordinate(self, index: int) -> tuple[float, str]:
        if index in self.revolute_indices:
            return self.revolute_difference_step_rad, "rad"
        return self.prismatic_difference_step_m, "m"

    def reduced_mass_matrix(self, q: Sequence[float]) -> np.ndarray:
        """Return the Schur complement with mixed block units."""

        qv = self._q(q)
        blocks = self.model.mass_matrix_blocks(qv)
        try:
            connection_term = blocks.Hmb @ np.linalg.solve(blocks.Hbb, blocks.Hbm)
        except np.linalg.LinAlgError as exc:
            raise URDFDynamicsError("singular Hbb in reduced mass assembly") from exc
        reduced = blocks.Hmm - connection_term
        reduced = 0.5 * (reduced + reduced.T)
        if not np.all(np.isfinite(reduced)) or np.min(np.linalg.eigvalsh(reduced)) <= 0.0:
            raise URDFDynamicsError("reduced mass matrix is not numerically positive definite")
        return reduced

    def mechanical_connection(self, q: Sequence[float]) -> np.ndarray:
        blocks = self.model.mass_matrix_blocks(self._q(q))
        try:
            return -np.linalg.solve(blocks.Hbb, blocks.Hbm)
        except np.linalg.LinAlgError as exc:
            raise URDFDynamicsError("singular Hbb in mechanical connection") from exc

    def _richardson_derivative(
        self,
        function: Callable[[np.ndarray], np.ndarray],
        q: np.ndarray,
        index: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float, str]:
        coarse_step, unit = self._step_for_coordinate(index)
        fine_step = 0.5 * coarse_step

        def centered(step: float) -> np.ndarray:
            plus = q.copy()
            minus = q.copy()
            plus[index] += step
            minus[index] -= step
            return (function(plus) - function(minus)) / (2.0 * step)

        coarse = centered(coarse_step)
        fine = centered(fine_step)
        extrapolated = (4.0 * fine - coarse) / 3.0
        scale = max(float(np.linalg.norm(extrapolated)), np.finfo(float).tiny)
        consistency = float(np.linalg.norm(fine - coarse) / scale)
        return extrapolated, coarse, fine, consistency, coarse_step, unit

    def reduced_mass_derivative_diagnostic(self, q: Sequence[float]) -> DerivativeDiagnostic:
        qv = self._q(q)
        derivatives = np.empty((self.dof, self.dof, self.dof))
        coarse_steps = np.empty(self.dof)
        fine_steps = np.empty(self.dof)
        consistency = np.empty(self.dof)
        units: list[str] = []
        for index in range(self.dof):
            derivative, _, _, error, coarse_step, unit = self._richardson_derivative(
                self.reduced_mass_matrix, qv, index
            )
            derivatives[index] = derivative
            coarse_steps[index] = coarse_step
            fine_steps[index] = 0.5 * coarse_step
            consistency[index] = error
            units.append(unit)
        return DerivativeDiagnostic(
            derivatives,
            coarse_steps,
            fine_steps,
            consistency,
            tuple(units),
        )

    def reduced_mass_derivatives(self, q: Sequence[float]) -> np.ndarray:
        return self.reduced_mass_derivative_diagnostic(q).derivatives_mixed_units

    def generalized_bias_effort(
        self, q: Sequence[float], generalized_rates: Sequence[float]
    ) -> np.ndarray:
        qv = self._q(q)
        rates = self._qdot(generalized_rates)
        derivatives = self.reduced_mass_derivatives(qv)
        mass_rate = np.tensordot(rates, derivatives, axes=(0, 0))
        energy_gradient = np.array(
            [rates @ derivatives[index] @ rates for index in range(self.dof)]
        )
        return mass_rate @ rates - 0.5 * energy_gradient

    def inverse_dynamics(
        self,
        q: Sequence[float],
        generalized_rates: Sequence[float],
        generalized_accelerations: Sequence[float],
    ) -> np.ndarray:
        acceleration = _vector(
            generalized_accelerations, self.dof, "generalized_accelerations"
        )
        return self.reduced_mass_matrix(q) @ acceleration + self.generalized_bias_effort(
            q, generalized_rates
        )

    def _solve_generalized_acceleration(
        self,
        q: np.ndarray,
        rates: np.ndarray,
        effort: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        reduced = self.reduced_mass_matrix(q)
        bias = self.generalized_bias_effort(q, rates)
        try:
            acceleration = np.linalg.solve(reduced, effort - bias)
        except np.linalg.LinAlgError as exc:
            raise URDFDynamicsError("singular reduced mass matrix") from exc
        return reduced, bias, acceleration

    def base_twist_component_derivative(
        self,
        q: Sequence[float],
        generalized_rates: Sequence[float],
        generalized_accelerations: Sequence[float],
    ) -> np.ndarray:
        qv = self._q(q)
        rates = self._qdot(generalized_rates)
        accelerations = _vector(
            generalized_accelerations, self.dof, "generalized_accelerations"
        )
        connection = self.mechanical_connection(qv)
        connection_rate = np.zeros_like(connection)
        for index in range(self.dof):
            derivative, _, _, _, _, _ = self._richardson_derivative(
                self.mechanical_connection, qv, index
            )
            connection_rate += derivative * rates[index]
        return connection @ accelerations + connection_rate @ rates

    def forward_dynamics(
        self,
        q: Sequence[float],
        generalized_rates: Sequence[float],
        generalized_effort: Sequence[float],
    ) -> ForwardDynamicsState:
        qv = self._q(q)
        rates = self._qdot(generalized_rates)
        effort = _vector(generalized_effort, self.dof, "generalized_effort")
        reduced, bias, acceleration = self._solve_generalized_acceleration(
            qv, rates, effort
        )
        connection = self.mechanical_connection(qv)
        base_twist = connection @ rates
        base_derivative = self.base_twist_component_derivative(qv, rates, acceleration)
        momentum = self.model.momentum(qv, base_twist, rates)
        return ForwardDynamicsState(
            reduced_mass_mixed_units=reduced,
            generalized_bias_effort_mixed_units=bias,
            generalized_acceleration_mixed_units=acceleration,
            base_twist_body=base_twist,
            base_twist_component_derivative=base_derivative,
            full_velocity_mixed_units=np.concatenate((base_twist, rates)),
            full_acceleration_components_mixed_units=np.concatenate(
                (base_derivative, acceleration)
            ),
            linear_momentum_residual_ns=float(
                np.linalg.norm(momentum.linear_root_kg_m_s)
            ),
            angular_momentum_about_root_residual_nms=float(
                np.linalg.norm(momentum.angular_about_root_kg_m2_s)
            ),
        )

    def kinetic_energy_j(
        self, q: Sequence[float], generalized_rates: Sequence[float]
    ) -> float:
        qv = self._q(q)
        rates = self._qdot(generalized_rates)
        return float(0.5 * rates @ self.reduced_mass_matrix(qv) @ rates)

    def _state_derivative(
        self,
        time_s: float,
        state: np.ndarray,
        effort_function: Callable[[float, np.ndarray, np.ndarray], np.ndarray],
    ) -> np.ndarray:
        n = self.dof
        q = state[:n]
        rates = state[n : 2 * n]
        quaternion = state[2 * n + 3 : 2 * n + 7]
        norm = float(np.linalg.norm(quaternion))
        if norm <= 0.0:
            raise URDFDynamicsError("base quaternion norm must be nonzero")
        quaternion = quaternion / norm
        effort = _vector(
            effort_function(time_s, q.copy(), rates.copy()), n, "generalized_effort"
        )
        _, _, acceleration = self._solve_generalized_acceleration(q, rates, effort)
        base_twist = self.mechanical_connection(q) @ rates
        rotation = quaternion_to_rotation_body_to_inertial(quaternion)
        position_rate = rotation @ base_twist[:3]
        quaternion_rate = 0.5 * _quat_product(
            quaternion, np.array((0.0, *base_twist[3:]))
        )
        work_rate = float(effort @ rates)
        return np.concatenate(
            (
                rates,
                acceleration,
                position_rate,
                quaternion_rate,
                (work_rate,),
            )
        )

    def propagate(
        self,
        q_initial: Sequence[float],
        generalized_rates_initial: Sequence[float],
        *,
        step_s: float,
        steps: int,
        generalized_effort: Sequence[float]
        | Callable[[float, np.ndarray, np.ndarray], Sequence[float]]
        | None = None,
        base_position_inertial_initial_m: Sequence[float] = (0.0, 0.0, 0.0),
        base_quaternion_body_to_inertial_initial_wxyz: Sequence[float] = (
            1.0,
            0.0,
            0.0,
            0.0,
        ),
    ) -> ReducedDynamicsHistory:
        if not math.isfinite(step_s) or step_s <= 0.0:
            raise URDFDynamicsError("step_s must be positive and finite")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise URDFDynamicsError("steps must be a positive integer")
        q0 = self._q(q_initial)
        rates0 = self._qdot(generalized_rates_initial)
        position0 = _vector(base_position_inertial_initial_m, 3, "base_position")
        quaternion0 = _vector(
            base_quaternion_body_to_inertial_initial_wxyz, 4, "base_quaternion"
        )
        quaternion_norm = float(np.linalg.norm(quaternion0))
        if quaternion_norm <= 0.0:
            raise URDFDynamicsError("base quaternion norm must be nonzero")
        quaternion0 = quaternion0 / quaternion_norm
        if generalized_effort is None:
            constant_effort = np.zeros(self.dof)
            effort_function = lambda _t, _q, _v: constant_effort
        elif callable(generalized_effort):
            effort_function = lambda t, q, v: np.asarray(
                generalized_effort(t, q, v), dtype=float
            )
        else:
            constant_effort = _vector(
                generalized_effort, self.dof, "generalized_effort"
            )
            effort_function = lambda _t, _q, _v: constant_effort

        state = np.concatenate((q0, rates0, position0, quaternion0, (0.0,)))
        times = np.arange(steps + 1, dtype=float) * step_s
        q_history = np.empty((steps + 1, self.dof))
        rate_history = np.empty_like(q_history)
        position_history = np.empty((steps + 1, 3))
        quaternion_history = np.empty((steps + 1, 4))
        twist_history = np.empty((steps + 1, 6))
        energy_history = np.empty(steps + 1)
        work_history = np.empty(steps + 1)
        linear_momentum_history = np.empty(steps + 1)
        angular_momentum_history = np.empty(steps + 1)

        for index, time_s in enumerate(times):
            q = state[: self.dof]
            rates = state[self.dof : 2 * self.dof]
            quaternion = state[2 * self.dof + 3 : 2 * self.dof + 7]
            quaternion /= np.linalg.norm(quaternion)
            state[2 * self.dof + 3 : 2 * self.dof + 7] = quaternion
            base_twist = self.mechanical_connection(q) @ rates
            momentum = self.model.momentum(q, base_twist, rates)
            q_history[index] = q
            rate_history[index] = rates
            position_history[index] = state[2 * self.dof : 2 * self.dof + 3]
            quaternion_history[index] = quaternion
            twist_history[index] = base_twist
            energy_history[index] = self.kinetic_energy_j(q, rates)
            work_history[index] = state[-1]
            linear_momentum_history[index] = np.linalg.norm(
                momentum.linear_root_kg_m_s
            )
            angular_momentum_history[index] = np.linalg.norm(
                momentum.angular_about_root_kg_m2_s
            )
            if index == steps:
                break
            k1 = self._state_derivative(time_s, state, effort_function)
            k2 = self._state_derivative(
                time_s + 0.5 * step_s,
                state + 0.5 * step_s * k1,
                effort_function,
            )
            k3 = self._state_derivative(
                time_s + 0.5 * step_s,
                state + 0.5 * step_s * k2,
                effort_function,
            )
            k4 = self._state_derivative(
                time_s + step_s, state + step_s * k3, effort_function
            )
            state = state + (step_s / 6.0) * (
                k1 + 2.0 * k2 + 2.0 * k3 + k4
            )
            quaternion_slice = slice(2 * self.dof + 3, 2 * self.dof + 7)
            state[quaternion_slice] /= np.linalg.norm(state[quaternion_slice])

        return ReducedDynamicsHistory(
            time_s=times,
            generalized_coordinates_mixed_units=q_history,
            generalized_rates_mixed_units=rate_history,
            base_position_inertial_m=position_history,
            base_quaternion_body_to_inertial_wxyz=quaternion_history,
            base_twist_body_mixed_units=twist_history,
            kinetic_energy_j=energy_history,
            generalized_work_j=work_history,
            linear_momentum_residual_ns=linear_momentum_history,
            angular_momentum_about_root_residual_nms=angular_momentum_history,
        )
