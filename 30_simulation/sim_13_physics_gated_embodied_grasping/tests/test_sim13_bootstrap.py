from __future__ import annotations

import json
import math
from dataclasses import fields, replace
from pathlib import Path
from typing import Callable

import pytest

from src.action_mask import GateState, SafetyGateSnapshot
from src.action_space import HighLevelAction
from src.env import PhysicsGatedEmbodiedGraspingEnv
from src.mechanical_asset_loader import (
    AssetHashMismatch,
    B601_ACCEPTED_MASS_KG,
    load_mechanical_assets,
)
from src.physics_backend import ANCHOR_150KG, ANCHOR_22KG, SCENE_ANCHORS


def _first_non_abort(env: PhysicsGatedEmbodiedGraspingEnv) -> HighLevelAction:
    return next(action for action in env.action_space.actions if not action.is_abort)


def _assert_only_abort_allowed(
    env: PhysicsGatedEmbodiedGraspingEnv,
    gates: SafetyGateSnapshot,
) -> None:
    decisions = env.action_mask(gates)
    assert decisions[HighLevelAction.abort()].allowed is True
    assert all(
        not decision.allowed
        for action, decision in decisions.items()
        if not action.is_abort
    )


def test_env_reset_deterministic(mechanical_interface_path: Path) -> None:
    env = PhysicsGatedEmbodiedGraspingEnv(
        mechanical_interface_path,
        seed=13082026,
    )
    first_observation, first_info = env.reset()
    second_observation, second_info = env.reset()
    assert first_observation == second_observation
    assert first_info == second_info
    assert first_observation["task_phase"] == "RESET_READY"
    assert first_info["backend_scope"] == (
        "KINEMATIC_BOOTSTRAP_NOT_CONTACT_OR_TRAINING_PHYSICS"
    )


def test_same_seed_same_state(mechanical_interface_path: Path) -> None:
    left = PhysicsGatedEmbodiedGraspingEnv(mechanical_interface_path, seed=73)
    right = PhysicsGatedEmbodiedGraspingEnv(mechanical_interface_path, seed=73)
    left_observation, left_info = left.reset()
    right_observation, right_info = right.reset()
    assert left_observation == right_observation
    assert left_info == right_info
    gates = SafetyGateSnapshot.all_pass()
    action = _first_non_abort(left)
    assert action == _first_non_abort(right)
    assert left.step(action, gates=gates) == right.step(action, gates=gates)


def test_asset_hash_binding(
    mechanical_interface_path: Path,
    mechanical_interface_factory: Callable[..., Path],
) -> None:
    bundle = load_mechanical_assets(mechanical_interface_path)
    assert set(bundle.artifact_hashes) == {
        "accepted_urdf",
        "visual_mesh",
        "collision_mesh",
        "frame_tree",
    }
    bad_manifest = mechanical_interface_factory(
        artifact_hash_overrides={"collision_mesh": "0" * 64},
        directory_name="bad_hash_interface",
    )
    with pytest.raises(AssetHashMismatch, match="collision_mesh SHA-256 mismatch"):
        load_mechanical_assets(bad_manifest)


def test_urdf_joint_count(mechanical_interface_path: Path) -> None:
    urdf = load_mechanical_assets(mechanical_interface_path).urdf
    assert urdf.link_count == 10
    assert urdf.joint_count == 9
    assert dict(urdf.joint_type_counts) == {
        "fixed": 1,
        "prismatic": 2,
        "revolute": 6,
    }
    assert math.isclose(
        urdf.total_mass_kg,
        B601_ACCEPTED_MASS_KG,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_frame_tree(mechanical_interface_path: Path) -> None:
    tree = load_mechanical_assets(mechanical_interface_path).frame_tree
    assert tree.parent_by_frame[tree.root_frame] is None
    assert tree.frame_count >= 10
    for frame_id in tree.frame_ids:
        seen: set[str] = set()
        cursor: str | None = frame_id
        while cursor is not None:
            assert cursor not in seen
            seen.add(cursor)
            cursor = tree.parent_by_frame[cursor]
        assert tree.root_frame in seen


def test_collision_mesh_loading(mechanical_interface_path: Path) -> None:
    collision = load_mechanical_assets(mechanical_interface_path).artifacts[
        "collision_mesh"
    ]
    assert collision.path.is_file()
    assert collision.path.suffix.lower() == ".stl"
    assert collision.size_bytes > 0
    assert len(collision.sha256) == 64


def test_action_mask_unknown(mechanical_interface_path: Path) -> None:
    env = PhysicsGatedEmbodiedGraspingEnv(mechanical_interface_path)
    env.reset()
    gates = SafetyGateSnapshot()
    _assert_only_abort_allowed(env, gates)
    decision = env.action_mask(gates)[_first_non_abort(env)]
    assert len(decision.reason_codes) == len(fields(SafetyGateSnapshot))
    assert all(code.endswith("_UNKNOWN") for code in decision.reason_codes)


def test_abort_always_available(mechanical_interface_path: Path) -> None:
    env = PhysicsGatedEmbodiedGraspingEnv(mechanical_interface_path)
    env.reset()
    all_fail = SafetyGateSnapshot(
        **{item.name: GateState.FAIL for item in fields(SafetyGateSnapshot)}
    )
    for gates in (SafetyGateSnapshot(), all_fail, SafetyGateSnapshot.all_pass()):
        decision = env.action_mask(gates)[HighLevelAction.abort()]
        assert decision.allowed is True
        assert decision.reason_codes == ("ABORT_ALWAYS_AVAILABLE",)


def test_22kg_anchor(mechanical_interface_path: Path) -> None:
    env = PhysicsGatedEmbodiedGraspingEnv(
        mechanical_interface_path,
        anchor_id=ANCHOR_22KG,
    )
    observation, info = env.reset()
    anchor = SCENE_ANCHORS[ANCHOR_22KG]
    assert info["anchor_id"] == ANCHOR_22KG
    assert observation["target"]["kind"] == "target_satellite"
    assert observation["target"]["mass_kg"] == 22.0
    assert math.isclose(
        observation["target"]["angular_velocity_radps"][2],
        math.radians(0.5),
        rel_tol=0.0,
        abs_tol=1e-15,
    )
    assert set(anchor.accepted_configurations).issubset(
        env.assets.accepted_configurations
    )
    next_observation, _, terminated, truncated, step_info = env.step(
        HighLevelAction.abort()
    )
    assert terminated is True and truncated is False
    assert next_observation["task_phase"] == "ABORTED_SAFE"
    assert step_info["executed_action"] == HighLevelAction.abort().as_dict()


def test_150kg_anchor(mechanical_interface_path: Path) -> None:
    env = PhysicsGatedEmbodiedGraspingEnv(
        mechanical_interface_path,
        anchor_id=ANCHOR_150KG,
    )
    observation, info = env.reset()
    anchor = SCENE_ANCHORS[ANCHOR_150KG]
    assert info["anchor_id"] == ANCHOR_150KG
    assert observation["target"]["kind"] == "target_debris"
    assert observation["target"]["mass_kg"] == 150.0
    assert math.isclose(
        observation["target"]["angular_velocity_radps"][2],
        math.radians(3.0),
        rel_tol=0.0,
        abs_tol=1e-15,
    )
    assert set(anchor.accepted_configurations).issubset(
        env.assets.accepted_configurations
    )
    next_observation, _, terminated, truncated, step_info = env.step(
        HighLevelAction.abort()
    )
    assert terminated is True and truncated is False
    assert next_observation["task_phase"] == "ABORTED_SAFE"
    assert step_info["executed_action"] == HighLevelAction.abort().as_dict()


def test_no_false_allow(mechanical_interface_path: Path) -> None:
    env = PhysicsGatedEmbodiedGraspingEnv(mechanical_interface_path)
    action = _first_non_abort(env)
    for item in fields(SafetyGateSnapshot):
        for unsafe_state in (GateState.UNKNOWN, GateState.FAIL):
            gates = replace(
                SafetyGateSnapshot.all_pass(),
                **{item.name: unsafe_state},
            )
            env.reset(gates=gates)
            _assert_only_abort_allowed(env, gates)
            _, _, terminated, truncated, info = env.step(action)
            assert terminated is True
            assert truncated is False
            assert info["executed_action"] == HighLevelAction.abort().as_dict()
            assert info["shield_intervened"] is True
            expected_reason = f"{item.name.upper()}_{unsafe_state.value}"
            assert expected_reason in info["shield_reason_codes"]
