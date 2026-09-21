from __future__ import annotations

import ast
import json
from pathlib import Path

import sim13_v4


V4_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = V4_ROOT.parents[2]


def test_all_authority_and_release_flags_remain_false() -> None:
    assert sim13_v4.CURRENT_SYSTEM_BINDING_PASSED is False
    assert sim13_v4.RUNTIME_PRODUCTION_GATE_PASSED is False
    assert sim13_v4.CONTACT_GRASP_GATE_PASSED is False
    assert sim13_v4.RELEASE_CREDIT is False
    assert sim13_v4.NEXT_STAGE_AUTHORIZED is False


def test_no_urdf_or_interface_or_authorization_file_is_created() -> None:
    assert list(V4_ROOT.rglob("*.urdf")) == []
    forbidden_names = {
        "MECH_RL_SYSTEM_INTERFACE_V2.yaml",
        "OWNER_AUTHORIZATION.json",
        "RUN_AUTHORIZATION.json",
        "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json",
    }
    assert not any(path.name in forbidden_names for path in V4_ROOT.rglob("*"))


def test_python_sources_do_not_call_private_unified_r2_generators() -> None:
    forbidden = {"_build_robot", "gen_urdf"}
    calls: list[str] = []
    for path in V4_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            if name in forbidden:
                calls.append(f"{path.name}:{name}")
    assert calls == []


def test_current_v2_formal_negative_control_state_is_not_rewritten() -> None:
    gate_path = (
        PROJECT_ROOT
        / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json"
    )
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate["formal_negative_controls_passed"] == 15
    assert gate["formal_negative_controls_declared"] == 20
    assert gate["formal_negative_controls_hold_ids"] == [
        "NC15",
        "NC16",
        "NC18",
        "NC19",
        "NC20",
    ]
    assert gate["runtime_fail_closed_gate_passed"] is False
    assert gate["production_dynamics_gate_passed"] is False
    assert gate["contact_grasp_gate_passed"] is False
    assert gate["next_stage_authorized"] is False
