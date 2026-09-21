from __future__ import annotations

import inspect
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from conftest import DIAGNOSTIC_ACKNOWLEDGEMENT, public_mapping


_MISSING = object()


def _ack_parameter() -> str:
    from src.env import Sim15DiagnosticEnv

    parameters = inspect.signature(Sim15DiagnosticEnv).parameters
    candidates = (
        "acknowledgement",
        "diagnostic_acknowledgement",
    )
    present = [name for name in candidates if name in parameters]
    assert len(present) == 1, (
        "Sim15 must expose one explicit acknowledgement parameter before any "
        "diagnostic mechanics can execute"
    )
    return present[0]


def _construct_env(authority: Any, acknowledgement: object = _MISSING, **kwargs: Any) -> Any:
    from src.env import Sim15DiagnosticEnv

    if acknowledgement is not _MISSING:
        kwargs[_ack_parameter()] = acknowledgement
    return Sim15DiagnosticEnv(authority, **kwargs)


def _diagnostic_env(interface_path: Path, **kwargs: Any) -> Any:
    from src.authority import load_authority

    return _construct_env(
        load_authority(interface_path),
        DIAGNOSTIC_ACKNOWLEDGEMENT,
        **kwargs,
    )


def _step(env: Any, action: Mapping[str, Any]) -> tuple[dict[str, Any], Any, bool, bool, dict[str, Any]]:
    output = env.step(action)
    assert isinstance(output, tuple) and len(output) == 5
    observation, reward, terminated, truncated, info = output
    assert isinstance(observation, dict)
    assert isinstance(terminated, bool) and isinstance(truncated, bool)
    assert isinstance(info, dict)
    return observation, reward, terminated, truncated, info


def test_diagnostic_environment_requires_exact_owner_acknowledgement(
    interface_path: Path,
) -> None:
    from src.authority import load_authority

    authority = load_authority(interface_path)
    _ack_parameter()
    with pytest.raises((PermissionError, RuntimeError, TypeError, ValueError)):
        _construct_env(authority)
    with pytest.raises((PermissionError, RuntimeError, ValueError)):
        _construct_env(authority, "I_ACCEPT_PLACEHOLDERS_AS_FLIGHT_AUTHORITY")
    env = _construct_env(authority, DIAGNOSTIC_ACKNOWLEDGEMENT)
    assert env is not None


def test_reset_discloses_scope_hash_and_all_closed_physical_channels(
    interface_path: Path,
) -> None:
    env = _diagnostic_env(interface_path)
    observation, info = env.reset()
    assert isinstance(observation, dict) and isinstance(info, dict)
    assert observation["interface_sha256"] == env.authority.interface_sha256
    assert observation["anchor_id"] == "ANCHOR_22KG_0P5DPS"
    assert observation["last_operation"] is None
    assert observation["capture_result"] is None
    assert observation["joint_load_result"] is None
    assert observation["physical_contact_authorized"] is False
    assert info["reason_code"] == "SIM15_DIAGNOSTIC_RESET"
    assert info["capture_result"] is None
    assert info["joint_load_result"] is None
    assert "DIAGNOSTIC" in str(info["scope"]).upper()
    assert "contact_gate" in info


def test_capture_action_returns_diagnostic_impulse_closure_without_rl_reward(
    interface_path: Path,
) -> None:
    env = _diagnostic_env(interface_path)
    env.reset()
    observation, reward, terminated, truncated, info = _step(
        env, {"operation": "capture"}
    )
    assert reward is None
    assert not terminated and not truncated
    assert observation["last_operation"] == "capture"
    assert observation["physical_contact_authorized"] is False
    assert observation["joint_load_result"] is None
    assert observation["capture_result"] is not None
    assert info["reason_code"] == "SIM15_RIGID_CAPTURE_DIAGNOSTIC_EXECUTED"
    assert info["joint_load_result"] is None
    result = public_mapping(info["capture_result"])
    assert result["linear_residual_norm_kg_mps"] <= 1e-11
    assert result["angular_residual_norm_kg_m2ps"] <= 1e-11
    assert result["contact_force_N"] is None
    assert result["contact_pressure_Pa"] is None
    assert result["contact_duration_s"] is None
    assert result["physical_contact_computed"] is False
    assert result["engineering_prediction"] is False


def test_explicit_wrench_action_returns_equilibrium_closed_diagnostic(
    interface_path: Path,
) -> None:
    env = _diagnostic_env(interface_path)
    env.reset()
    wrench = (125.0, -23.0, 47.0, 3.2, -4.1, 5.7)
    observation, reward, terminated, truncated, info = _step(
        env,
        {
            "operation": "joint_load_distribution",
            "pattern_id": "STAGE_A_TO_B_8XM5_R62P5MM",
            "wrench_N_Nm": wrench,
        },
    )
    assert reward is None
    assert not terminated and not truncated
    assert observation["last_operation"] == "joint_load_distribution"
    assert observation["capture_result"] is None
    assert observation["joint_load_result"] is not None
    assert info["reason_code"] == "SIM15_GEOMETRIC_JOINT_DISTRIBUTION_EXECUTED"
    result = public_mapping(info["joint_load_result"])
    assert tuple(result["reconstructed_wrench_N_Nm"]) == pytest.approx(
        wrench, rel=0.0, abs=1e-10
    )
    assert tuple(result["equilibrium_residual_N_Nm"]) == pytest.approx(
        (0.0,) * 6, rel=0.0, abs=1e-10
    )


def test_joint_action_requires_an_explicit_wrench_and_never_zero_fills(
    interface_path: Path,
) -> None:
    env = _diagnostic_env(interface_path)
    env.reset()
    with pytest.raises((KeyError, TypeError, ValueError)):
        env.step({"operation": "joint_load_distribution"})
    with pytest.raises((KeyError, TypeError, ValueError)):
        env.step(
            {
                "operation": "joint_load_distribution",
                "wrench_N_Nm": None,
            }
        )


@pytest.mark.parametrize(
    "action",
    (
        {"operation": "physical_contact"},
        {"operation": "contact_force"},
        {"operation": "run_fea"},
        {"operation": "rl_step"},
    ),
)
def test_unauthorized_physical_structural_or_rl_operations_fail_closed(
    interface_path: Path,
    action: dict[str, object],
) -> None:
    env = _diagnostic_env(interface_path)
    env.reset()
    with pytest.raises((PermissionError, RuntimeError, ValueError)):
        env.step(action)


def test_direct_joint_effort_alias_is_not_an_allowed_action(
    interface_path: Path,
) -> None:
    env = _diagnostic_env(interface_path)
    env.reset()
    with pytest.raises((KeyError, TypeError, ValueError)):
        env.step({"operation": "capture", "joint_torques_Nm": (0.0,) * 6})


def test_production_mode_is_not_constructible_from_diagnostic_authority(
    interface_path: Path,
) -> None:
    from src.authority import load_authority
    from src.env import ExecutionMode

    authority = load_authority(interface_path)
    production_member = next(
        member
        for member in ExecutionMode
        if "PRODUCTION" in str(member.value).upper()
    )
    with pytest.raises((PermissionError, RuntimeError, ValueError)):
        _construct_env(
            authority,
            DIAGNOSTIC_ACKNOWLEDGEMENT,
            mode=production_member,
        )


@pytest.mark.parametrize(
    "anchor_id",
    ("ANCHOR_22KG_0P5DPS", "ANCHOR_150KG_3DPS"),
)
def test_both_hash_bound_fixture_anchors_are_diagnostic_only(
    interface_path: Path,
    anchor_id: str,
) -> None:
    env = _diagnostic_env(interface_path, anchor_id=anchor_id)
    observation, _ = env.reset()
    assert observation["anchor_id"] == anchor_id
    observation, _, _, _, info = _step(env, {"operation": "capture"})
    result = public_mapping(info["capture_result"])
    assert result["engineering_prediction"] is False
    assert observation["physical_contact_authorized"] is False
