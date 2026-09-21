from __future__ import annotations

import numpy as np

from sim13_v4a.full_floating import (
    JOINT_COORDINATE_UNITS,
    JOINT_EFFORT_UNITS,
    JOINT_RATE_UNITS,
    ServiceState,
    deterministic_scenario,
    deterministic_stress_points,
    quat_from_rotvec,
    quat_product,
    quat_to_rotation,
)


def test_topology_and_mixed_unit_contract_are_explicit() -> None:
    model, service, _ = deterministic_scenario()
    assert model.joint_types == ("R", "R", "R", "R", "R", "R", "P", "P")
    assert JOINT_COORDINATE_UNITS == ("rad",) * 6 + ("m",) * 2
    assert JOINT_RATE_UNITS == ("rad/s",) * 6 + ("m/s",) * 2
    assert JOINT_EFFORT_UNITS == ("N*m",) * 6 + ("N",) * 2
    assert service.nu_s_mixed.shape == (14,)


def test_mass_matrix_is_spd_and_has_free_base_joint_coupling() -> None:
    model, service, _ = deterministic_scenario()
    matrix = model.mass_matrix(service)
    assert matrix.shape == (14, 14)
    assert np.max(np.abs(matrix - matrix.T)) < 1.0e-12
    assert np.min(np.linalg.eigvalsh(matrix)) > 1.0e-5
    assert np.linalg.norm(matrix[:6, 6:]) > 0.05


def test_mass_matrix_energy_matches_direct_body_sum() -> None:
    model, service, _ = deterministic_scenario()
    direct = model.momentum_energy(service).kinetic_energy_j
    quadratic = model.kinetic_energy_from_mass_matrix(service)
    assert abs(direct - quadratic) < 2.0e-14


def test_link_local_point_jacobian_matches_finite_difference() -> None:
    model, service, _ = deterministic_scenario()
    point = (0.071, -0.023, 0.038)
    _, analytic, _ = model.point_position_and_jacobian(service, 7, point)
    numerical = model.finite_difference_point_jacobian(service, 7, point)
    assert np.max(np.abs(analytic - numerical)) < 3.0e-8


def test_point_jacobian_is_covariant_under_global_rigid_transform() -> None:
    model, service, _ = deterministic_scenario()
    global_quaternion = quat_from_rotvec((0.23, -0.17, 0.11))
    global_rotation = quat_to_rotation(global_quaternion)
    translation = np.array((-0.7, 0.4, 0.2))
    transformed = ServiceState(
        translation + global_rotation @ service.base_position_inertial_m,
        quat_product(
            global_quaternion, service.base_quaternion_body_to_inertial_wxyz
        ),
        service.joint_coordinates_mixed.copy(),
        service.nu_s_mixed.copy(),
    )
    point = (0.053, 0.019, -0.027)
    position, jacobian, _ = model.point_position_and_jacobian(service, 6, point)
    transformed_position, transformed_jacobian, _ = model.point_position_and_jacobian(
        transformed, 6, point
    )
    velocity_transform = np.eye(14)
    velocity_transform[:3, :3] = global_rotation
    velocity_transform[3:6, 3:6] = global_rotation
    assert np.linalg.norm(transformed_position - (translation + global_rotation @ position)) < 1.0e-12
    assert np.max(
        np.abs(transformed_jacobian @ velocity_transform - global_rotation @ jacobian)
    ) < 2.0e-12


def test_fixed_multiconfiguration_registry_covers_all_links_and_point_jacobians() -> None:
    model, _, _ = deterministic_scenario()
    cases = deterministic_stress_points()
    assert len(cases) == 10
    assert {case.link_index for case in cases} == set(range(8))
    assert len({case.case_id for case in cases}) == len(cases)
    errors = []
    for case in cases:
        _, analytic, _ = model.point_position_and_jacobian(
            case.service_state, case.link_index, case.point_local_m
        )
        finite_difference = model.finite_difference_point_jacobian(
            case.service_state, case.link_index, case.point_local_m
        )
        errors.append(float(np.max(np.abs(analytic - finite_difference))))
    assert max(errors) < 3.0e-8
