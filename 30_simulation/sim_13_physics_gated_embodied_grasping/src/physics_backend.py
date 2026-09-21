"""Deterministic kinematic backend used to bootstrap sim_13.

This backend intentionally does not claim contact, flexible-body, or trained
policy fidelity.  It executes the two required scene anchors and advances the
target attitude exactly under a constant angular-rate kinematic model.  A later
physics adapter may replace it without changing the environment contract.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Mapping

from .action_space import HighLevelAction
from .domain_randomization import RandomizationSample


ANCHOR_22KG = "ANCHOR_22KG_0P5DPS"
ANCHOR_150KG = "ANCHOR_150KG_3DPS"


@dataclass(frozen=True)
class SceneAnchor:
    anchor_id: str
    target_kind: str
    target_mass_kg: float
    target_tumble_rate_dps: float
    accepted_configurations: tuple[str, str]


SCENE_ANCHORS: Mapping[str, SceneAnchor] = {
    ANCHOR_22KG: SceneAnchor(
        anchor_id=ANCHOR_22KG,
        target_kind="target_satellite",
        target_mass_kg=22.0,
        target_tumble_rate_dps=0.5,
        accepted_configurations=("DEPLOYED_NOMINAL", "ARM_TASK_READY"),
    ),
    ANCHOR_150KG: SceneAnchor(
        anchor_id=ANCHOR_150KG,
        target_kind="target_debris",
        target_mass_kg=150.0,
        target_tumble_rate_dps=3.0,
        accepted_configurations=("DEPLOYED_NOMINAL", "ARM_TASK_READY"),
    ),
}


@dataclass(frozen=True)
class BackendState:
    anchor_id: str
    simulation_time_s: float
    target_kind: str
    target_mass_kg: float
    target_relative_position_m: tuple[float, float, float]
    target_relative_quaternion_xyzw: tuple[float, float, float, float]
    target_relative_linear_velocity_mps: tuple[float, float, float]
    target_angular_velocity_radps: tuple[float, float, float]
    base_quaternion_xyzw: tuple[float, float, float, float]
    base_angular_velocity_radps: tuple[float, float, float]
    joint_position_rad_or_m: tuple[float, ...]
    joint_velocity_radps_or_mps: tuple[float, ...]
    end_effector_position_m: tuple[float, float, float]
    end_effector_quaternion_xyzw: tuple[float, float, float, float]
    end_effector_linear_velocity_mps: tuple[float, float, float]
    end_effector_angular_velocity_radps: tuple[float, float, float]
    collision_detected: bool
    task_phase: str
    last_strategy_id: str | None


def _quaternion_multiply(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    output = (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )
    norm = math.sqrt(math.fsum(value * value for value in output))
    return tuple(value / norm for value in output)  # type: ignore[return-value]


class DeterministicPhysicsBackend:
    """Small state machine with exact seed-independent anchor kinematics."""

    scope = "KINEMATIC_BOOTSTRAP_NOT_CONTACT_OR_TRAINING_PHYSICS"

    def __init__(self, timestep_s: float = 0.05) -> None:
        if not math.isfinite(timestep_s) or timestep_s <= 0.0:
            raise ValueError("timestep_s must be finite and positive")
        self.timestep_s = float(timestep_s)
        self._state: BackendState | None = None

    @property
    def state(self) -> BackendState:
        if self._state is None:
            raise RuntimeError("backend must be reset before state is read")
        return self._state

    def reset(
        self,
        anchor_id: str,
        randomization: RandomizationSample,
        joint_count: int,
    ) -> BackendState:
        try:
            anchor = SCENE_ANCHORS[anchor_id]
        except KeyError as exc:
            raise ValueError(f"unknown scene anchor: {anchor_id}") from exc
        if joint_count <= 0:
            raise ValueError("joint_count must be positive")
        dx, dy, dz = randomization.relative_position_delta_m
        target_mass = anchor.target_mass_kg * randomization.target_mass_scale
        tumble_dps = anchor.target_tumble_rate_dps + randomization.tumble_delta_dps
        self._state = BackendState(
            anchor_id=anchor.anchor_id,
            simulation_time_s=0.0,
            target_kind=anchor.target_kind,
            target_mass_kg=target_mass,
            target_relative_position_m=(1.0 + dx, dy, dz),
            target_relative_quaternion_xyzw=(0.0, 0.0, 0.0, 1.0),
            target_relative_linear_velocity_mps=(0.0, 0.0, 0.0),
            target_angular_velocity_radps=(0.0, 0.0, math.radians(tumble_dps)),
            base_quaternion_xyzw=(0.0, 0.0, 0.0, 1.0),
            base_angular_velocity_radps=(0.0, 0.0, 0.0),
            joint_position_rad_or_m=(0.0,) * joint_count,
            joint_velocity_radps_or_mps=(0.0,) * joint_count,
            end_effector_position_m=(0.0, 0.0, 0.0),
            end_effector_quaternion_xyzw=(0.0, 0.0, 0.0, 1.0),
            end_effector_linear_velocity_mps=(0.0, 0.0, 0.0),
            end_effector_angular_velocity_radps=(0.0, 0.0, 0.0),
            collision_detected=False,
            task_phase="RESET_READY",
            last_strategy_id=None,
        )
        return self._state

    def step(self, action: HighLevelAction) -> BackendState:
        state = self.state
        dt = self.timestep_s
        wz = state.target_angular_velocity_radps[2]
        half_angle = 0.5 * wz * dt
        delta = (0.0, 0.0, math.sin(half_angle), math.cos(half_angle))
        orientation = _quaternion_multiply(
            state.target_relative_quaternion_xyzw, delta)
        phase = "ABORTED_SAFE" if action.is_abort else "HIGH_LEVEL_ACTION_ACCEPTED"
        self._state = replace(
            state,
            simulation_time_s=state.simulation_time_s + dt,
            target_relative_quaternion_xyzw=orientation,
            task_phase=phase,
            last_strategy_id=action.strategy_id,
        )
        return self._state


__all__ = [
    "ANCHOR_22KG",
    "ANCHOR_150KG",
    "BackendState",
    "DeterministicPhysicsBackend",
    "SCENE_ANCHORS",
    "SceneAnchor",
]
