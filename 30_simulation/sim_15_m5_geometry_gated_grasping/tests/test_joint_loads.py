from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from conftest import public_mapping


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def _matvec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> tuple[float, ...]:
    return tuple(
        math.fsum(float(coefficient) * float(component) for coefficient, component in zip(row, vector, strict=True))
        for row in matrix
    )


def _reconstruct(
    coordinates_yz_m: Sequence[Sequence[float]],
    fastener_forces_N: Sequence[Sequence[float]],
) -> tuple[float, float, float, float, float, float]:
    axial = [float(force[0]) for force in fastener_forces_N]
    shear_y = [float(force[1]) for force in fastener_forces_N]
    shear_z = [float(force[2]) for force in fastener_forces_N]
    return (
        math.fsum(axial),
        math.fsum(shear_y),
        math.fsum(shear_z),
        math.fsum(
            float(coordinate[0]) * qz - float(coordinate[1]) * qy
            for coordinate, qy, qz in zip(
                coordinates_yz_m, shear_y, shear_z, strict=True
            )
        ),
        math.fsum(
            float(coordinate[1]) * normal
            for coordinate, normal in zip(coordinates_yz_m, axial, strict=True)
        ),
        -math.fsum(
            float(coordinate[0]) * normal
            for coordinate, normal in zip(coordinates_yz_m, axial, strict=True)
        ),
    )


def test_joint_model_declares_si_coordinates_and_six_dof_order(
    joint_model_document: dict[str, object],
) -> None:
    assert joint_model_document["schema"] == "M5_ANALYTIC_JOINT_LOAD_MODEL_V1"
    assert joint_model_document["units"] == {
        "force": "N",
        "moment": "N*m",
        "coordinate": "m",
        "influence_moment_terms": "1/m",
    }
    coordinate_contract = str(joint_model_document["coordinate_contract"])
    assert "x is interface normal" in coordinate_contract
    assert "wrench=[Fx,Fy,Fz,Mx,My,Mz]" in coordinate_contract
    assert joint_model_document["allowed_use"] == (
        "GEOMETRIC_WRENCH_DISTRIBUTION_SENSITIVITY_AND_SOFTWARE_VERIFICATION"
    )
    assert set(joint_model_document["prohibited_uses"]) == {
        "FASTENER_STRENGTH",
        "PRELOAD_MARGIN",
        "SLIP_OR_SEPARATION",
        "PLATE_STRESS",
        "FLIGHT_MOS",
    }


def test_each_frozen_influence_matrix_exactly_reconstructs_six_dof_wrench(
    joint_model_document: dict[str, object],
) -> None:
    patterns = joint_model_document["patterns"]
    assert isinstance(patterns, dict) and set(patterns) == {
        "B601_TO_STAGE_A_4XM4_64MM",
        "STAGE_A_TO_B_8XM5_R62P5MM",
        "STAGE_B_TO_SPACECRAFT_4XM6_140MM",
    }
    trial_wrenches = (
        (1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
        (125.0, -23.0, 47.0, 3.2, -4.1, 5.7),
    )
    for pattern_id, pattern in patterns.items():
        coordinates = pattern["coordinates_yz_m"]
        matrices = pattern["influence_matrices"]
        assert pattern["fastener_count"] == len(coordinates) == len(matrices)
        assert all(len(matrix) == 3 for matrix in matrices)
        assert all(len(row) == 6 for matrix in matrices for row in matrix)
        for wrench in trial_wrenches:
            forces = [_matvec(matrix, wrench) for matrix in matrices]
            reconstructed = _reconstruct(coordinates, forces)
            assert reconstructed == pytest.approx(wrench, rel=0.0, abs=1e-12), (
                pattern_id,
                wrench,
            )


def test_declared_geometric_sums_match_coordinates(
    joint_model_document: dict[str, object],
) -> None:
    patterns = joint_model_document["patterns"]
    assert isinstance(patterns, dict)
    for pattern_id, pattern in patterns.items():
        coordinates = pattern["coordinates_yz_m"]
        sum_y2 = math.fsum(float(y) ** 2 for y, _ in coordinates)
        sum_z2 = math.fsum(float(z) ** 2 for _, z in coordinates)
        sum_r2 = sum_y2 + sum_z2
        assert pattern["sum_y2_m2"] == pytest.approx(sum_y2, abs=1e-15)
        assert pattern["sum_z2_m2"] == pytest.approx(sum_z2, abs=1e-15)
        assert pattern["sum_r2_m2"] == pytest.approx(sum_r2, abs=1e-15)
        assert sum_y2 > 0.0 and sum_z2 > 0.0 and sum_r2 > 0.0, pattern_id


@pytest.mark.parametrize(
    "wrench_N_Nm",
    (
        (1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
        (125.0, -23.0, 47.0, 3.2, -4.1, 5.7),
    ),
)
def test_runtime_distributor_closes_force_and_moment_equilibrium(
    interface_path: Path,
    wrench_N_Nm: tuple[float, ...],
) -> None:
    from src.authority import load_authority
    from src.joint_loads import JointLoadDistributor

    authority = load_authority(interface_path)
    distributor = JointLoadDistributor(authority)
    for pattern_id in authority.joint_load_model["patterns"]:
        result = distributor.distribute(pattern_id, wrench_N_Nm)
        reconstructed = tuple(_field(result, "reconstructed_wrench_N_Nm"))
        residual = tuple(_field(result, "equilibrium_residual_N_Nm"))
        assert reconstructed == pytest.approx(wrench_N_Nm, rel=0.0, abs=1e-10)
        assert residual == pytest.approx((0.0,) * 6, rel=0.0, abs=1e-10)
        fasteners = _field(result, "fasteners")
        assert len(fasteners) == authority.joint_load_model["patterns"][pattern_id][
            "fastener_count"
        ]


def test_runtime_distributor_is_deterministic_and_diagnostic_scoped(
    interface_path: Path,
) -> None:
    from src.authority import load_authority
    from src.joint_loads import JointLoadDistributor

    authority = load_authority(interface_path)
    distributor = JointLoadDistributor(authority)
    args = ("B601_TO_STAGE_A_4XM4_64MM", (50.0, 2.0, -3.0, 1.0, 4.0, -5.0))
    left = public_mapping(distributor.distribute(*args))
    right = public_mapping(distributor.distribute(*args))
    assert left == right
    rendered = str(left).upper()
    assert "GEOMETRIC" in rendered or "DIAGNOSTIC" in rendered
    assert "FLIGHT_MOS" in rendered or "STRENGTH" in rendered


@pytest.mark.parametrize(
    ("pattern_id", "wrench"),
    (
        ("UNKNOWN_PATTERN", (0.0,) * 6),
        ("B601_TO_STAGE_A_4XM4_64MM", (0.0,) * 5),
        ("B601_TO_STAGE_A_4XM4_64MM", (0.0,) * 7),
        ("B601_TO_STAGE_A_4XM4_64MM", (0.0, 0.0, math.nan, 0.0, 0.0, 0.0)),
        ("B601_TO_STAGE_A_4XM4_64MM", (0.0, 0.0, math.inf, 0.0, 0.0, 0.0)),
        ("B601_TO_STAGE_A_4XM4_64MM", {"Fx_N": 1.0}),
    ),
)
def test_runtime_distributor_rejects_unknown_malformed_or_nonfinite_inputs(
    interface_path: Path,
    pattern_id: str,
    wrench: object,
) -> None:
    from src.authority import load_authority
    from src.joint_loads import JointLoadDistributor

    distributor = JointLoadDistributor(load_authority(interface_path))
    with pytest.raises((KeyError, TypeError, ValueError)):
        distributor.distribute(pattern_id, wrench)


def test_uncertainty_nulls_and_load_boundary_holds_are_not_zero_filled(
    m5_root: Path,
    joint_model_document: dict[str, object],
) -> None:
    uncertainty = joint_model_document["uncertainty"]
    assert {
        "estimate",
        "coordinate_standard_uncertainty_m",
        "distribution",
        "degrees_of_freedom",
        "source",
        "correlation_group",
        "status",
    }.issubset(uncertainty)
    assert uncertainty["estimate"] == "nominal pattern coordinates_yz_m above"
    assert uncertainty["source"] == "digital nominal geometry only"
    for unknown_field in (
        "coordinate_standard_uncertainty_m",
        "distribution",
        "degrees_of_freedom",
        "correlation_group",
    ):
        assert uncertainty[unknown_field] is None
    assert uncertainty["status"] == "HOLD_NO_METROLOGY_INPUT"
    import yaml

    migration_path = (
        m5_root / "03_load_authority" / "M5_LOAD_AUTHORITY_MIGRATION_V1.yaml"
    )
    migration = yaml.safe_load(migration_path.read_text(encoding="utf-8"))
    old = migration["old_boundary_ruling"]
    replacement = migration["replacement_boundary_contract"]
    invalid = migration["invalid_trajectory_ruling"]
    assert old["parent_frame"] == "M_FRAME"
    assert old["disposition"] == "REJECTED_FOR_PHYSICAL_LOAD_APPLICATION"
    assert replacement["T_M_DYNAMICS_FROM_SPACECRAFT_LOAD_BRIDGE_MATING_DATUM"] is None
    assert replacement["stiffness_6x6"] is None
    assert replacement["fastener_preload_N"] is None
    assert replacement["friction_coefficient"] is None
    assert replacement["formal_fea_use"] == "PROHIBITED"
    assert invalid["source_case"] == "LC-010"
    assert invalid["source_joint2_command_deg"] == 60.0
    assert invalid["accepted_joint2_limits_deg"] == [-179.908748, 0.0]
    assert invalid["disposition"] == "REJECTED_AS_LOAD_INPUT"
    assert migration["formal_loads_authorized"] is False
