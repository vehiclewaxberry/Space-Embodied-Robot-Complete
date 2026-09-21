"""Deterministic, state-observation sim_13 environment bootstrap."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .action_mask import ActionMasker, MaskDecision, SafetyGateSnapshot
from .action_space import DiscreteActionSpace, HighLevelAction
from .domain_randomization import (
    DomainRandomizationConfig,
    DomainRandomizer,
    RandomizationSample,
)
from .mechanical_asset_loader import MechanicalAssetBundle, load_mechanical_assets
from .observation import ObservationSchema, validate_observation_finite
from .physics_backend import (
    ANCHOR_22KG,
    SCENE_ANCHORS,
    DeterministicPhysicsBackend,
)
from .reward import BootstrapReward
from .safety_shield import SafetyShield
from .termination import BootstrapTermination


class PhysicsGatedEmbodiedGraspingEnv:
    """Small Gym-like environment with no Gym dependency.

    ``reset`` returns ``(observation, info)`` and ``step`` returns
    ``(observation, reward, terminated, truncated, info)``.  The action surface
    is high-level and discrete; no direct torque field is accepted.
    """

    metadata = {
        "name": "sim_13_physics_gated_embodied_grasping",
        "contract_version": "sim13-env-bootstrap-v1",
        "render_modes": [],
    }

    def __init__(
        self,
        mechanical_interface_path: str | Path,
        *,
        seed: int = 0,
        anchor_id: str = ANCHOR_22KG,
        timestep_s: float = 0.05,
        maximum_steps: int = 1000,
        randomization_config: DomainRandomizationConfig | None = None,
    ) -> None:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("seed must be an integer")
        self.assets: MechanicalAssetBundle = load_mechanical_assets(
            mechanical_interface_path)
        self._validate_anchor(anchor_id)
        self.default_seed = seed
        self.anchor_id = anchor_id
        self.randomizer = DomainRandomizer(randomization_config)
        self.backend = DeterministicPhysicsBackend(timestep_s=timestep_s)
        self.action_space = DiscreteActionSpace(
            self.assets.grasp_candidate_ids,
            self.assets.capture_timing_ids,
        )
        self.masker = ActionMasker()
        self.shield = SafetyShield(self.masker)
        self.observation_schema = ObservationSchema()
        self.reward_model = BootstrapReward()
        self.termination_model = BootstrapTermination(maximum_steps)
        self._seed = seed
        self._sample: RandomizationSample | None = None
        self._gates = SafetyGateSnapshot()
        self._step_count = 0
        self._has_reset = False

    def _validate_anchor(self, anchor_id: str) -> None:
        try:
            anchor = SCENE_ANCHORS[anchor_id]
        except KeyError as exc:
            raise ValueError(f"unknown scene anchor: {anchor_id}") from exc
        missing = set(anchor.accepted_configurations) - set(
            self.assets.accepted_configurations)
        if missing:
            raise ValueError(
                f"mechanical interface does not accept anchor configurations: {sorted(missing)}"
            )

    def reset(
        self,
        *,
        seed: int | None = None,
        anchor_id: str | None = None,
        gates: SafetyGateSnapshot | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        selected_seed = self.default_seed if seed is None else seed
        if not isinstance(selected_seed, int) or isinstance(selected_seed, bool):
            raise ValueError("seed must be an integer")
        selected_anchor = self.anchor_id if anchor_id is None else anchor_id
        self._validate_anchor(selected_anchor)
        self._seed = selected_seed
        self.anchor_id = selected_anchor
        self._sample = self.randomizer.sample(selected_seed)
        self._gates = gates or SafetyGateSnapshot()
        self._step_count = 0
        self.backend.reset(
            selected_anchor,
            self._sample,
            joint_count=self.assets.urdf.joint_count,
        )
        self._has_reset = True
        observation = self._observation()
        return observation, self._info()

    def _observation(self) -> dict[str, Any]:
        observation = self.observation_schema.build(
            self.backend.state, self.assets, self._gates)
        validate_observation_finite(observation)
        return observation

    def _info(self) -> dict[str, Any]:
        if self._sample is None:
            raise RuntimeError("environment must be reset first")
        return {
            "seed": self._seed,
            "anchor_id": self.anchor_id,
            "step_count": self._step_count,
            "mechanical_interface_manifest_sha256": self.assets.manifest_sha256,
            "mechanical_artifact_hashes": dict(self.assets.artifact_hashes),
            "mass_authority": self.assets.mass_and_inertia["authority"],
            "backend_scope": self.backend.scope,
            "randomization": self._sample.as_dict(),
            "gate_snapshot": {
                key: value.value for key, value in asdict(self._gates).items()
            },
        }

    def action_mask(
        self,
        gates: SafetyGateSnapshot | None = None,
    ) -> Mapping[HighLevelAction, MaskDecision]:
        snapshot = self._gates if gates is None else gates
        return self.masker.evaluate(self.action_space, snapshot)

    def step(
        self,
        action: HighLevelAction | Mapping[str, Any],
        *,
        gates: SafetyGateSnapshot | None = None,
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if not self._has_reset:
            raise RuntimeError("reset must be called before step")
        requested = self.action_space.parse(action)
        if gates is not None:
            self._gates = gates
        shield_result = self.shield.enforce(
            requested, self.action_space, self._gates)
        state = self.backend.step(shield_result.executed_action)
        self._step_count += 1
        reward = self.reward_model.evaluate(
            shield_result, collision_detected=state.collision_detected)
        termination = self.termination_model.evaluate(
            state, shield_result, self._step_count)
        observation = self._observation()
        info = self._info()
        info.update({
            "requested_action": shield_result.requested_action.as_dict(),
            "executed_action": shield_result.executed_action.as_dict(),
            "shield_intervened": shield_result.intervened,
            "shield_reason_codes": list(shield_result.reason_codes),
            "reward_breakdown": asdict(reward),
            "termination_reason": termination.reason,
        })
        return (
            observation,
            reward.total,
            termination.terminated,
            termination.truncated,
            info,
        )


__all__ = ["PhysicsGatedEmbodiedGraspingEnv"]
