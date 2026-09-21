from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sim13_v3.reduced_dynamics import (
    CHRISTOFFEL_BACKEND,
    CURRENT_SYSTEM_BINDING_PASSED,
    MASS_MATRIX_BLOCK_UNIT_CONTRACT,
    PRODUCTION_DYNAMICS_GATE_PASSED,
    ZeroMomentumReducedDynamics,
    generalized_coordinate_contract,
)
from sim13_v3.source_model import (
    FIXTURE_AUTHORITY_CLASS,
    build_synthetic_8dof_model,
    synthetic_8dof_xml_bytes,
)


@pytest.fixture(scope="module")
def solver():
    return ZeroMomentumReducedDynamics(build_synthetic_8dof_model())


def _state():
    q = np.array((0.11, -0.16, 0.08, 0.13, -0.09, 0.06, 0.012, -0.009))
    qdot = np.array((0.055, -0.041, 0.032, 0.024, -0.019, 0.015, 0.004, -0.003))
    return q, qdot


def test_fixture_is_exactly_synthetic_8dof_and_never_written_as_urdf():
    model = build_synthetic_8dof_model()
    summary = model.model_summary()
    assert summary["links"] == 9
    assert summary["joints"] == 8
    assert summary["physical_links"] == 9
    assert summary["revolute_joints"] == 6
    assert summary["prismatic_joints"] == 2
    assert summary["movable_dof"] == 8
    assert FIXTURE_AUTHORITY_CLASS.startswith("SYNTHETIC_ONLY")
    assert b"SYNTHETIC_ONLY" in synthetic_8dof_xml_bytes()
    v3_root = Path(__file__).resolve().parents[1]
    assert list(v3_root.rglob("*.urdf")) == []


def test_scope_is_explicitly_nonproduction_and_fd_christoffel():
    assert "RICHARDSON" in CHRISTOFFEL_BACKEND
    assert PRODUCTION_DYNAMICS_GATE_PASSED is False
    assert CURRENT_SYSTEM_BINDING_PASSED is False


def test_mixed_generalized_coordinate_and_mass_block_unit_contract(solver):
    contract = generalized_coordinate_contract(solver.model)
    assert len(contract) == 14
    assert [item["generalized_effort_unit"] for item in contract[6:12]] == ["N*m"] * 6
    assert [item["generalized_effort_unit"] for item in contract[12:]] == ["N"] * 2
    assert [item["coordinate_type"] for item in contract[6:]] == ["REVOLUTE"] * 6 + ["PRISMATIC"] * 2
    assert MASS_MATRIX_BLOCK_UNIT_CONTRACT["REVOLUTE__REVOLUTE"] == "kg*m^2"
    assert MASS_MATRIX_BLOCK_UNIT_CONTRACT["REVOLUTE__PRISMATIC"] == "kg*m"
    assert MASS_MATRIX_BLOCK_UNIT_CONTRACT["PRISMATIC__PRISMATIC"] == "kg"
    assert MASS_MATRIX_BLOCK_UNIT_CONTRACT["global_single_unit"] is None


def test_full_14_by_14_mass_matrix_is_symmetric_positive_definite(solver):
    q, _ = _state()
    matrix = solver.model.mass_matrix(q)
    assert matrix.shape == (14, 14)
    np.testing.assert_allclose(matrix, matrix.T, atol=2.0e-12, rtol=0.0)
    assert np.min(np.linalg.eigvalsh(matrix)) > 1.0e-6
    reduced = solver.reduced_mass_matrix(q)
    assert reduced.shape == (8, 8)
    assert np.min(np.linalg.eigvalsh(reduced)) > 1.0e-7


def test_all_eight_generalized_coordinate_effort_channels_are_independent(solver):
    q, qdot = _state()
    baseline = solver.forward_dynamics(
        q, qdot, np.zeros(8)
    ).generalized_acceleration_mixed_units
    response = np.empty((8, 8))
    for index in range(8):
        effort = np.zeros(8)
        effort[index] = 0.2
        response[:, index] = (
            solver.forward_dynamics(
                q, qdot, effort
            ).generalized_acceleration_mixed_units
            - baseline
        )
    assert np.linalg.matrix_rank(response, tol=1.0e-10) == 8
    assert np.all(np.linalg.norm(response, axis=0) > 1.0e-7)


def test_forward_inverse_roundtrip(solver):
    q, qdot = _state()
    effort = np.linspace(-0.13, 0.17, 8)
    forward = solver.forward_dynamics(q, qdot, effort)
    reconstructed = solver.inverse_dynamics(
        q, qdot, forward.generalized_acceleration_mixed_units
    )
    np.testing.assert_allclose(reconstructed, effort, atol=2.0e-11, rtol=2.0e-11)


def test_zero_state_zero_generalized_effort_zero_acceleration(solver):
    result = solver.forward_dynamics(np.zeros(8), np.zeros(8), np.zeros(8))
    np.testing.assert_allclose(
        result.generalized_acceleration_mixed_units,
        np.zeros(8),
        atol=1.0e-15,
        rtol=0.0,
    )
    np.testing.assert_allclose(result.base_twist_body, np.zeros(6), atol=1.0e-15, rtol=0.0)
    np.testing.assert_allclose(
        result.base_twist_component_derivative, np.zeros(6), atol=1.0e-15, rtol=0.0
    )


def test_single_generalized_effort_generates_base_reaction_and_separate_zero_momenta(solver):
    q = np.array((0.08, -0.04, 0.05, 0.02, -0.03, 0.06, 0.005, -0.004))
    effort = np.zeros(8)
    effort[2] = 0.25
    result = solver.forward_dynamics(q, np.zeros(8), effort)
    assert np.linalg.norm(result.base_twist_component_derivative) > 1.0e-5
    assert result.linear_momentum_residual_ns < 1.0e-14
    assert result.angular_momentum_about_root_residual_nms < 1.0e-14


def test_per_coordinate_two_step_richardson_derivatives_are_consistent(solver):
    q, _ = _state()
    diagnostic = solver.reduced_mass_derivative_diagnostic(q)
    np.testing.assert_allclose(
        diagnostic.per_coordinate_coarse_step[:6],
        np.full(6, 2.0e-5),
        atol=0.0,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        diagnostic.per_coordinate_coarse_step[6:],
        np.full(2, 2.0e-6),
        atol=0.0,
        rtol=0.0,
    )
    assert diagnostic.per_coordinate_step_units == ("rad",) * 6 + ("m",) * 2
    assert np.max(diagnostic.per_coordinate_relative_consistency) < 5.0e-7


def test_free_motion_conserves_reduced_energy_and_zero_momentum(solver):
    q, qdot = _state()
    history = solver.propagate(q, qdot, step_s=0.002, steps=25)
    energy_scale = history.kinetic_energy_j[0]
    relative_energy_drift = np.max(
        np.abs(history.kinetic_energy_j - energy_scale)
    ) / energy_scale
    assert relative_energy_drift < 2.0e-8
    assert np.max(history.linear_momentum_residual_ns) < 2.0e-13
    assert np.max(history.angular_momentum_about_root_residual_nms) < 2.0e-13
    np.testing.assert_allclose(
        np.linalg.norm(history.base_quaternion_body_to_inertial_wxyz, axis=1),
        np.ones(history.time_s.size),
        atol=2.0e-14,
        rtol=0.0,
    )


def test_powered_motion_closes_work_energy(solver):
    q, qdot = _state()
    effort = np.array((0.02, -0.015, 0.01, 0.008, -0.006, 0.005, 0.001, -0.0008))
    history = solver.propagate(
        q, qdot, step_s=0.001, steps=30, generalized_effort=effort
    )
    delta_energy = history.kinetic_energy_j - history.kinetic_energy_j[0]
    closure = delta_energy - history.generalized_work_j
    assert np.max(np.abs(closure)) < 2.0e-9


def test_robot_step_size_convergence(solver):
    q, qdot = _state()
    effort = np.array((0.01, -0.008, 0.006, 0.004, -0.003, 0.002, 0.0005, -0.0004))
    coarse = solver.propagate(
        q, qdot, step_s=0.002, steps=10, generalized_effort=effort
    )
    fine = solver.propagate(
        q, qdot, step_s=0.001, steps=20, generalized_effort=effort
    )
    assert np.max(np.abs(coarse.q[-1, :6] - fine.q[-1, :6])) < 2.0e-8
    assert np.max(np.abs(coarse.q[-1, 6:] - fine.q[-1, 6:])) < 2.0e-9
    assert np.max(np.abs(coarse.qdot[-1, :6] - fine.qdot[-1, :6])) < 2.0e-8
    assert np.max(np.abs(coarse.qdot[-1, 6:] - fine.qdot[-1, 6:])) < 2.0e-9
    assert np.linalg.norm(
        coarse.base_position_inertial_m[-1] - fine.base_position_inertial_m[-1]
    ) < 2.0e-9
    alignment = abs(
        float(
            coarse.base_quaternion_body_to_inertial_wxyz[-1]
            @ fine.base_quaternion_body_to_inertial_wxyz[-1]
        )
    )
    assert 2.0 * np.arccos(np.clip(alignment, -1.0, 1.0)) < 2.0e-8
