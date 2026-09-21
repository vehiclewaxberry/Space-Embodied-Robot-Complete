"""State-based observation builder for sim_13."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .action_mask import SafetyGateSnapshot
from .mechanical_asset_loader import MechanicalAssetBundle
from .physics_backend import BackendState


@dataclass(frozen=True)
class ObservationSchema:
    schema_version: str = "sim13-state-observation-v1"

    def build(
        self,
        state: BackendState,
        assets: MechanicalAssetBundle,
        gates: SafetyGateSnapshot,
    ) -> dict[str, Any]:
        joint_names = list(assets.urdf.joint_names)
        return {
            "schema_version": self.schema_version,
            "simulation_time_s": state.simulation_time_s,
            "target": {
                "kind": state.target_kind,
                "mass_kg": state.target_mass_kg,
                "relative_position_m": list(state.target_relative_position_m),
                "relative_quaternion_xyzw": list(state.target_relative_quaternion_xyzw),
                "relative_linear_velocity_mps": list(
                    state.target_relative_linear_velocity_mps),
                "angular_velocity_radps": list(state.target_angular_velocity_radps),
            },
            "service_spacecraft": {
                "base_quaternion_xyzw": list(state.base_quaternion_xyzw),
                "base_angular_velocity_radps": list(state.base_angular_velocity_radps),
            },
            "b601": {
                "joint_names": joint_names,
                "q": list(state.joint_position_rad_or_m),
                "dq": list(state.joint_velocity_radps_or_mps),
                "joint_limit_margin": {
                    "status": "UNKNOWN_NO_LIMIT_BINDING_IN_BOOTSTRAP",
                    "values": [None] * len(joint_names),
                },
                "end_effector": {
                    "position_m": list(state.end_effector_position_m),
                    "quaternion_xyzw": list(state.end_effector_quaternion_xyzw),
                    "linear_velocity_mps": list(state.end_effector_linear_velocity_mps),
                    "angular_velocity_radps": list(
                        state.end_effector_angular_velocity_radps),
                },
            },
            "flexible_modes": {
                "left_wing": {"status": "INTERFACE_ONLY_UNKNOWN", "q": [], "dq": []},
                "right_wing": {"status": "INTERFACE_ONLY_UNKNOWN", "q": [], "dq": []},
            },
            "grasp_candidates": [dict(item) for item in assets.grasp_candidates],
            "collision_flags": {
                "detected": state.collision_detected,
                "external_collision_clear": gates.external_collision_clear.value,
                "keep_out_clear": gates.keep_out_clear.value,
            },
            "physics_gates": {
                "sim_10": gates.sim10_gate.value,
                "safe_00": gates.safe00_state.value,
                "post_grasp_stability": gates.post_grasp_stability_gate.value,
            },
            "task_phase": state.task_phase,
        }


def validate_observation_finite(observation: Mapping[str, Any]) -> None:
    """Reject non-finite numeric values while allowing explicit ``None`` UNKNOWNs."""
    stack: list[Any] = [observation]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("observation contains a non-finite numeric value")


__all__ = ["ObservationSchema", "validate_observation_finite"]
