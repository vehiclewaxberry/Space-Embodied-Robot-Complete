from __future__ import annotations

import numpy as np
import pytest

from b3_contact import integrate_dual_contact, summarize_dual_contact_history
from b3_contact.branched_model import (
    CURRENT_SYSTEM_BOUND,
    PHYSICAL_CONTACT_FRAMES_BOUND,
    URDF_MODIFIED_OR_GENERATED,
)
from b3_contact.dual_contact_kernel import no_contact_regression
from sim13_v4a.full_floating import DynamicsError, ServiceState


def _with_q(state: ServiceState, q: np.ndarray) -> ServiceState:
    return ServiceState(
        state.base_position_inertial_m.copy(),
        state.base_quaternion_body_to_inertial_wxyz.copy(),
        np.asarray(q, dtype=float),
        state.nu_s_mixed.copy(),
    )


def _pad(model, state, config, side):
    return model.synthetic_pad_position_and_jacobian(
        state,
        side,
        closed_half_gap_m=config.closed_half_gap_m,
        pad_x_palm_m=config.pad_x_palm_m,
        pad_z_palm_m=config.pad_z_palm_m,
    )


def test_generalized_order_body_inventory_and_mass_are_branched(dual_scenario):
    model, service, _, _ = dual_scenario
    kinematics = model.kinematics(service)
    names = [body.name for body in kinematics.bodies]
    assert model.full_velocity_dof == 14
    assert service.joint_coordinates_mixed.shape == (8,)
    assert service.nu_s_mixed.shape == (14,)
    assert names == [
        "service_base",
        *[f"synthetic_arm_link_{index}" for index in range(1, 7)],
        "design_model_palm",
        "design_model_left_finger",
        "design_model_right_finger",
    ]
    assert abs(sum(body.mass_kg for body in kinematics.bodies) - model.total_mass_kg) <= 1.0e-12
    assert not CURRENT_SYSTEM_BOUND
    assert not PHYSICAL_CONTACT_FRAMES_BOUND
    assert not URDF_MODIFIED_OR_GENERATED


def test_mass_matrix_is_symmetric_positive_definite_at_two_states(dual_scenario):
    model, service, _, _ = dual_scenario
    q_perturbed = service.joint_coordinates_mixed + np.array(
        (0.08, -0.05, 0.04, -0.06, 0.03, -0.02, 0.004, -0.003)
    )
    for state in (service, _with_q(service, q_perturbed)):
        matrix = model.mass_matrix(state)
        assert matrix.shape == (14, 14)
        assert np.max(np.abs(matrix - matrix.T)) <= 1.0e-13
        assert float(np.min(np.linalg.eigvalsh(matrix))) > 1.0e-4


@pytest.mark.parametrize("side,own_column,cross_column", (("left", 12, 13), ("right", 13, 12)))
def test_pad_joint_jacobian_matches_finite_difference_and_has_no_cross_branch(
    dual_scenario, side, own_column, cross_column
):
    model, service, _, config = dual_scenario
    _, jacobian, angular_jacobian = _pad(model, service, config, side)
    finite_difference = np.empty((3, 8))
    for joint in range(8):
        epsilon = 1.0e-7
        q_plus = service.joint_coordinates_mixed.copy()
        q_minus = service.joint_coordinates_mixed.copy()
        q_plus[joint] += epsilon
        q_minus[joint] -= epsilon
        p_plus = _pad(model, _with_q(service, q_plus), config, side)[0]
        p_minus = _pad(model, _with_q(service, q_minus), config, side)[0]
        finite_difference[:, joint] = (p_plus - p_minus) / (2.0 * epsilon)
    assert np.max(np.abs(finite_difference - jacobian[:, 6:14])) <= 2.0e-8
    assert np.linalg.norm(jacobian[:, own_column]) >= 1.0 - 1.0e-12
    assert np.array_equal(jacobian[:, cross_column], np.zeros(3))
    assert np.array_equal(angular_jacobian[:, 12:14], np.zeros((3, 2)))


def test_palm_is_insensitive_to_both_prismatic_coordinates(dual_scenario):
    model, service, _, config = dual_scenario
    palm, rotation, jacobian, angular_jacobian = model.palm_frame_and_jacobians(service)
    q_changed = service.joint_coordinates_mixed.copy()
    q_changed[6:] += (0.006, -0.004)
    palm_changed, rotation_changed, _, _ = model.palm_frame_and_jacobians(
        _with_q(service, q_changed)
    )
    assert np.array_equal(palm_changed, palm)
    assert np.array_equal(rotation_changed, rotation)
    assert np.array_equal(jacobian[:, 12:14], np.zeros((3, 2)))
    assert np.array_equal(angular_jacobian[:, 12:14], np.zeros((3, 2)))
    with pytest.raises(DynamicsError):
        _pad(model, service, config, "center")


def test_no_contact_wrapper_regression_and_conservation(dual_scenario):
    assert max(no_contact_regression().values()) == 0.0
    model, service, target, config = dual_scenario
    history = integrate_dual_contact(
        model,
        service,
        target,
        config,
        step_s=5.0e-4,
        duration_s=4.0e-3,
        method="rk4",
        contact_enabled=False,
        require_soft_capture=False,
    )
    summary = summarize_dual_contact_history(history, config)
    assert not history.aborted_safe
    assert summary["linear_momentum_n_s"]["total_max_drift_n_s"] <= 1.0e-11
    assert summary["angular_momentum_n_m_s"]["total_max_drift_n_m_s"] <= 1.0e-11
    assert summary["energy_j"]["total_mechanical_plus_dissipated_max_drift_j"] <= 1.0e-10
