from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from conftest import public_mapping


def _field(value: Any, *names: str) -> Any:
    mapping = public_mapping(value)
    for name in names:
        if name in mapping:
            return mapping[name]
    raise AssertionError(f"none of the required result fields exist: {names!r}")


def _vector(value: Any, *names: str) -> tuple[float, float, float]:
    vector = tuple(float(component) for component in _field(value, *names))
    assert len(vector) == 3
    return vector  # type: ignore[return-value]


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(math.fsum(float(component) ** 2 for component in vector))


def _fixture_bodies(authority: Any, anchor_id: str) -> tuple[Any, Any]:
    from src.rigid_capture import body_from_mapping

    fixture = authority.diagnostic_fixture
    service_record = fixture["service_spacecraft_fixture"]
    anchor_record = fixture["anchors"][anchor_id]
    return body_from_mapping(service_record), body_from_mapping(anchor_record)


def _simple_body(
    *,
    mass_kg: float,
    position_m: Sequence[float] = (0.0, 0.0, 0.0),
    linear_velocity_mps: Sequence[float] = (0.0, 0.0, 0.0),
    angular_velocity_radps: Sequence[float] = (0.0, 0.0, 0.0),
) -> dict[str, object]:
    return {
        "mass_kg": mass_kg,
        "inertia_about_com_kg_m2": (
            (1.0, 0.0, 0.0),
            (0.0, 1.2, 0.0),
            (0.0, 0.0, 1.4),
        ),
        "initial_position_m": tuple(position_m),
        "initial_linear_velocity_mps": tuple(linear_velocity_mps),
        "initial_angular_velocity_radps": tuple(angular_velocity_radps),
    }


@pytest.mark.parametrize("anchor_id", ("ANCHOR_22KG_0P5DPS", "ANCHOR_150KG_3DPS"))
def test_hash_bound_rigid_capture_closes_linear_and_angular_momentum(
    interface_path: Path,
    anchor_id: str,
) -> None:
    from src.authority import load_authority
    from src.rigid_capture import RigidPlasticCaptureSolver

    authority = load_authority(interface_path)
    service, target = _fixture_bodies(authority, anchor_id)
    result = RigidPlasticCaptureSolver().capture(service, target)
    linear_residual = _vector(
        result,
        "linear_momentum_residual_kg_mps",
        "linear_residual_kg_mps",
    )
    angular_residual = _vector(
        result,
        "angular_momentum_residual_kg_m2ps",
        "angular_residual_kg_m2ps",
    )
    assert _norm(linear_residual) <= 1e-11
    assert _norm(angular_residual) <= 1e-11

    service_impulse = _vector(
        result,
        "service_com_linear_impulse_N_s",
        "service_com_impulse_Ns",
        "service_impulse_Ns",
    )
    target_impulse = _vector(
        result,
        "target_com_linear_impulse_N_s",
        "target_com_impulse_Ns",
        "target_impulse_Ns",
    )
    assert tuple(
        left + right for left, right in zip(service_impulse, target_impulse, strict=True)
    ) == pytest.approx((0.0, 0.0, 0.0), rel=0.0, abs=1e-11)


def test_capture_outputs_impulse_not_force_pressure_or_duration(
    interface_path: Path,
) -> None:
    from src.authority import load_authority
    from src.rigid_capture import RigidPlasticCaptureSolver

    authority = load_authority(interface_path)
    service, target = _fixture_bodies(authority, "ANCHOR_22KG_0P5DPS")
    result = RigidPlasticCaptureSolver().capture(service, target)
    mapping = public_mapping(result)
    assert mapping["contact_force_N"] is None
    assert mapping["contact_pressure_Pa"] is None
    assert mapping["contact_duration_s"] is None
    rendered = str(mapping).upper()
    assert "RIGID" in rendered and ("PLASTIC" in rendered or "DIAGNOSTIC" in rendered)
    assert "NOT" in rendered and "CONTACT_FORCE" in rendered


def test_internal_com_impulses_are_nonzero_for_relative_fixture_motion(
    interface_path: Path,
) -> None:
    from src.authority import load_authority
    from src.rigid_capture import RigidPlasticCaptureSolver

    authority = load_authority(interface_path)
    service, target = _fixture_bodies(authority, "ANCHOR_22KG_0P5DPS")
    result = RigidPlasticCaptureSolver().capture(service, target)
    service_impulse = _vector(
        result,
        "service_com_linear_impulse_N_s",
        "service_com_impulse_Ns",
        "service_impulse_Ns",
    )
    target_impulse = _vector(
        result,
        "target_com_linear_impulse_N_s",
        "target_com_impulse_Ns",
        "target_impulse_Ns",
    )
    assert _norm(service_impulse) > 0.0
    assert _norm(target_impulse) > 0.0


def test_kinematically_identical_colocated_bodies_need_no_impulse() -> None:
    from src.rigid_capture import RigidPlasticCaptureSolver, body_from_mapping

    state = {
        "position_m": (0.25, -0.5, 0.75),
        "linear_velocity_mps": (0.01, -0.02, 0.03),
        "angular_velocity_radps": (0.001, 0.002, -0.003),
    }
    left = body_from_mapping(
        _simple_body(
            mass_kg=2.0,
            position_m=state["position_m"],
            linear_velocity_mps=state["linear_velocity_mps"],
            angular_velocity_radps=state["angular_velocity_radps"],
        )
    )
    right = body_from_mapping(
        _simple_body(
            mass_kg=3.0,
            position_m=state["position_m"],
            linear_velocity_mps=state["linear_velocity_mps"],
            angular_velocity_radps=state["angular_velocity_radps"],
        )
    )
    result = RigidPlasticCaptureSolver().capture(left, right)
    assert _vector(
        result,
        "service_com_linear_impulse_N_s",
        "service_com_impulse_Ns",
        "service_impulse_Ns",
    ) == (
        pytest.approx(0.0, abs=1e-12),
        pytest.approx(0.0, abs=1e-12),
        pytest.approx(0.0, abs=1e-12),
    )
    assert _vector(
        result,
        "target_com_linear_impulse_N_s",
        "target_com_impulse_Ns",
        "target_impulse_Ns",
    ) == (
        pytest.approx(0.0, abs=1e-12),
        pytest.approx(0.0, abs=1e-12),
        pytest.approx(0.0, abs=1e-12),
    )


def test_capture_is_bitwise_deterministic_for_hash_bound_fixture(
    interface_path: Path,
) -> None:
    from src.authority import load_authority
    from src.rigid_capture import RigidPlasticCaptureSolver

    authority = load_authority(interface_path)
    left_bodies = _fixture_bodies(authority, "ANCHOR_150KG_3DPS")
    right_bodies = _fixture_bodies(authority, "ANCHOR_150KG_3DPS")
    left = public_mapping(RigidPlasticCaptureSolver().capture(*left_bodies))
    right = public_mapping(RigidPlasticCaptureSolver().capture(*right_bodies))
    assert left == right


def test_plastic_capture_dissipates_but_does_not_create_kinetic_energy(
    interface_path: Path,
) -> None:
    from src.authority import load_authority
    from src.rigid_capture import RigidPlasticCaptureSolver

    authority = load_authority(interface_path)
    service, target = _fixture_bodies(authority, "ANCHOR_150KG_3DPS")
    result = public_mapping(RigidPlasticCaptureSolver().capture(service, target))
    assert result["kinetic_energy_before_J"] >= result["kinetic_energy_after_J"]
    assert result["plastic_energy_loss_J"] >= 0.0
    assert result["plastic_energy_loss_J"] == pytest.approx(
        result["kinetic_energy_before_J"] - result["kinetic_energy_after_J"],
        rel=1e-12,
        abs=1e-12,
    )
    assert result["physical_contact_computed"] is False
    assert result["engineering_prediction"] is False


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("mass_kg", 0.0),
        ("mass_kg", -1.0),
        ("mass_kg", math.nan),
        ("mass_kg", math.inf),
        ("initial_position_m", (0.0, 0.0)),
        ("initial_linear_velocity_mps", (0.0, math.nan, 0.0)),
        ("initial_angular_velocity_radps", (0.0, 0.0, math.inf)),
        (
            "inertia_about_com_kg_m2",
            ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        ),
    ),
)
def test_body_loader_rejects_nonphysical_shape_or_nonfinite_values(
    field: str,
    invalid_value: object,
) -> None:
    from src.rigid_capture import body_from_mapping

    record = _simple_body(mass_kg=1.0)
    record[field] = invalid_value
    with pytest.raises((TypeError, ValueError)):
        body_from_mapping(record)


def test_body_loader_rejects_non_si_aliases_instead_of_silent_conversion() -> None:
    from src.rigid_capture import body_from_mapping

    record = _simple_body(mass_kg=1.0)
    record["mass_g"] = 1000.0
    del record["mass_kg"]
    with pytest.raises((KeyError, TypeError, ValueError)):
        body_from_mapping(record)


def test_impulse_to_force_conversion_is_explicitly_prohibited() -> None:
    from src.rigid_capture import ProhibitedPhysicsOperation, impulse_to_force

    with pytest.raises(ProhibitedPhysicsOperation):
        impulse_to_force((1.0, 0.0, 0.0), 0.01)
