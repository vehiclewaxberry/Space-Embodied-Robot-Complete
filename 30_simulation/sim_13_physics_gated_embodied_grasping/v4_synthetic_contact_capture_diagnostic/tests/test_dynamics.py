from __future__ import annotations

import numpy as np

from sim13_v4a.full_floating import (
    ServiceState,
    TargetState,
    deterministic_scenario,
    deterministic_el_audit_states,
    propagate_no_contact,
    quaternion_geodesic,
    relative_scalar_drift,
    relative_vector_drift,
)


def test_zero_velocity_zero_external_has_zero_acceleration() -> None:
    model, service, _ = deterministic_scenario()
    rest = ServiceState(
        service.base_position_inertial_m,
        service.base_quaternion_body_to_inertial_wxyz,
        service.joint_coordinates_mixed,
        np.zeros(14),
    )
    assert np.linalg.norm(model.acceleration_zero_external(rest)) < 1.0e-14


def test_service_free_motion_preserves_p_h_and_energy_separately() -> None:
    model, service, target = deterministic_scenario()
    history = propagate_no_contact(model, service, target, step_s=0.002, steps=40)
    assert relative_vector_drift(history.service_linear_momentum_n_s) < 2.0e-8
    assert relative_vector_drift(
        history.service_angular_momentum_about_inertial_origin_n_m_s
    ) < 2.0e-8
    assert relative_scalar_drift(history.service_kinetic_energy_j) < 2.0e-8


def test_target_full_6dof_preserves_p_h_and_energy_separately() -> None:
    model, service, target = deterministic_scenario()
    history = propagate_no_contact(model, service, target, step_s=0.002, steps=40)
    assert np.linalg.norm(history.target_position_inertial_m[-1] - history.target_position_inertial_m[0]) > 1.0e-3
    assert np.linalg.norm(history.target_twist_inertial_mixed[-1, 3:] - history.target_twist_inertial_mixed[0, 3:]) > 1.0e-5
    assert relative_vector_drift(history.target_linear_momentum_n_s) < 1.0e-13
    assert relative_vector_drift(
        history.target_angular_momentum_about_inertial_origin_n_m_s
    ) < 1.0e-11
    assert relative_scalar_drift(history.target_kinetic_energy_j) < 1.0e-12


def test_no_contact_decouples_plants_and_uses_one_time_axis() -> None:
    model, service, target = deterministic_scenario()
    baseline = propagate_no_contact(model, service, target, step_s=0.002, steps=20)
    changed_target = TargetState(
        target.position_inertial_m + np.array((0.4, -0.1, 0.2)),
        target.quaternion_body_to_inertial_wxyz,
        target.twist_inertial_mixed * np.array((1.2, 0.8, 1.1, 0.9, 1.1, 1.3)),
    )
    variant = propagate_no_contact(
        model, service, changed_target, step_s=0.002, steps=20
    )
    assert np.array_equal(baseline.time_s, variant.time_s)
    assert np.array_equal(
        baseline.service_joint_coordinates_mixed,
        variant.service_joint_coordinates_mixed,
    )
    assert np.array_equal(baseline.service_nu_s_mixed, variant.service_nu_s_mixed)
    assert relative_vector_drift(baseline.total_linear_momentum_n_s) < 2.0e-8
    assert relative_vector_drift(
        baseline.total_angular_momentum_about_inertial_origin_n_m_s
    ) < 2.0e-8
    assert relative_scalar_drift(baseline.total_kinetic_energy_j) < 2.0e-8


def test_rk4_step_halving_converges_componentwise() -> None:
    model, service, target = deterministic_scenario()
    coarse = propagate_no_contact(model, service, target, step_s=0.004, steps=20)
    fine = propagate_no_contact(model, service, target, step_s=0.002, steps=40)
    assert np.linalg.norm(
        coarse.service_base_position_inertial_m[-1]
        - fine.service_base_position_inertial_m[-1]
    ) < 2.0e-8
    assert quaternion_geodesic(
        coarse.service_base_quaternion_body_to_inertial_wxyz[-1],
        fine.service_base_quaternion_body_to_inertial_wxyz[-1],
    ) < 2.0e-7
    assert np.max(
        np.abs(
            coarse.service_joint_coordinates_mixed[-1]
            - fine.service_joint_coordinates_mixed[-1]
        )
    ) < 2.0e-7
    assert np.max(
        np.abs(coarse.service_nu_s_mixed[-1] - fine.service_nu_s_mixed[-1])
    ) < 2.0e-7
    assert np.linalg.norm(
        coarse.target_position_inertial_m[-1] - fine.target_position_inertial_m[-1]
    ) < 2.0e-12
    assert quaternion_geodesic(
        coarse.target_quaternion_body_to_inertial_wxyz[-1],
        fine.target_quaternion_body_to_inertial_wxyz[-1],
    ) < 2.0e-7


def test_el_audit_registry_has_six_explicit_diverse_nonzero_velocity_states() -> None:
    cases = deterministic_el_audit_states()
    assert len(cases) == 6
    assert cases[0].case_id == "EL00_NOMINAL"
    assert len({case.case_id for case in cases}) == 6
    coordinates = np.vstack(
        [case.service_state.joint_coordinates_mixed for case in cases]
    )
    assert np.ptp(coordinates[:, :6], axis=0).min() > 0.3
    assert np.ptp(coordinates[:, 6:], axis=0).min() > 0.03
    for case in cases:
        velocity = case.service_state.nu_s_mixed
        assert np.all(np.abs(velocity[:6]) > 0.0)
        assert np.all(np.abs(velocity[6:12]) > 0.0)
        assert np.all(np.abs(velocity[12:]) > 0.0)
        assert abs(np.linalg.norm(case.service_state.base_quaternion_body_to_inertial_wxyz) - 1.0) < 1.0e-12
