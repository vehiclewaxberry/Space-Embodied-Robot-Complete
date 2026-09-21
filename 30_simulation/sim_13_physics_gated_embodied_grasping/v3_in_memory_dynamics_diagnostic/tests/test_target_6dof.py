from __future__ import annotations

import numpy as np
import pytest

from sim13_v3.target_6dof import URDFDynamicsError, propagate_target_6dof


def _run(step_s: float, steps: int):
    return propagate_target_6dof(
        22.0,
        np.array(((2.1, 0.08, -0.03), (0.08, 3.2, 0.05), (-0.03, 0.05, 4.8))),
        (1.2, -0.4, 0.7),
        (0.06, -0.025, 0.018),
        (0.31, 0.47, -0.26),
        step_s=step_s,
        steps=steps,
        quaternion_body_to_inertial_initial_wxyz=(0.91, 0.12, -0.18, 0.34),
    )


def test_target_full_translation_nonprincipal_rotation_and_invariants():
    history = _run(0.001, 500)
    assert np.linalg.norm(history.position_inertial_m[-1] - history.position_inertial_m[0]) > 0.01
    assert np.linalg.norm(history.omega_body_rad_s[-1] - history.omega_body_rad_s[0]) > 1.0e-3
    linear_scale = np.linalg.norm(history.linear_momentum_inertial_kg_m_s[0])
    linear_drift = np.max(
        np.linalg.norm(
            history.linear_momentum_inertial_kg_m_s
            - history.linear_momentum_inertial_kg_m_s[0],
            axis=1,
        )
    ) / linear_scale
    spin_scale = np.linalg.norm(
        history.spin_angular_momentum_about_com_inertial[0]
    )
    spin_drift = np.max(
        np.linalg.norm(
            history.spin_angular_momentum_about_com_inertial
            - history.spin_angular_momentum_about_com_inertial[0],
            axis=1,
        )
    ) / spin_scale
    total_angular_scale = np.linalg.norm(
        history.total_angular_momentum_about_inertial_origin[0]
    )
    total_angular_drift = np.max(
        np.linalg.norm(
            history.total_angular_momentum_about_inertial_origin
            - history.total_angular_momentum_about_inertial_origin[0],
            axis=1,
        )
    ) / total_angular_scale
    energy_drift = np.max(
        np.abs(history.kinetic_energy_j - history.kinetic_energy_j[0])
    ) / history.kinetic_energy_j[0]
    assert linear_drift < 1.0e-14
    assert spin_drift < 2.0e-12
    assert total_angular_drift < 2.0e-12
    assert history.angular_momentum_unit == "N*m*s"
    assert energy_drift < 2.0e-13
    np.testing.assert_allclose(
        np.linalg.norm(history.quaternion_body_to_inertial_wxyz, axis=1),
        np.ones(history.time_s.size),
        atol=2.0e-14,
        rtol=0.0,
    )


def test_target_step_size_convergence():
    coarse = _run(0.002, 100)
    fine = _run(0.001, 200)
    position_error = np.linalg.norm(
        coarse.position_inertial_m[-1] - fine.position_inertial_m[-1]
    )
    omega_error = np.linalg.norm(coarse.omega_body_rad_s[-1] - fine.omega_body_rad_s[-1])
    velocity_error = np.linalg.norm(
        coarse.velocity_inertial_m_s[-1] - fine.velocity_inertial_m_s[-1]
    )
    quaternion_alignment = abs(
        float(
            coarse.quaternion_body_to_inertial_wxyz[-1]
            @ fine.quaternion_body_to_inertial_wxyz[-1]
        )
    )
    assert position_error < 1.0e-13
    assert velocity_error < 1.0e-13
    assert omega_error < 2.0e-13
    assert 1.0 - quaternion_alignment < 2.0e-14


def test_target_inertia_asymmetry_fails_closed():
    asymmetric = np.array(
        ((2.0, 2.0e-10, 0.0), (0.0, 3.0, 0.0), (0.0, 0.0, 4.0))
    )
    with pytest.raises(URDFDynamicsError, match="asymmetry exceeds"):
        propagate_target_6dof(
            22.0,
            asymmetric,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.1, 0.2, 0.3),
            step_s=0.001,
            steps=1,
        )
