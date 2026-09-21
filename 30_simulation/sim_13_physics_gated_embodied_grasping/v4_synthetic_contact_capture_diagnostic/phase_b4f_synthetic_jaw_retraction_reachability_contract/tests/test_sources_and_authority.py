from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


@pytest.mark.parametrize(
    "key,expected",
    [
        ("freeze_contracts_and_test_contracts", True),
        ("bind_parent_sources_and_evidence", True),
        ("define_synthetic_generalized_force_profiles", True),
        ("define_algorithm_only_parameter_domain", True),
        ("implement_or_execute_b4f_solver", False),
        ("modify_b4_or_b4e", False),
        ("introduce_physical_gripper_parameters", False),
        ("modify_or_generate_urdf", False),
        ("bind_current_system_interface", False),
        ("invoke_private_builder_or_generator", False),
    ],
)
def test_authorized_scope_exact(contracts, key, expected):
    assert contracts["authorization"]["authorized"][key] is expected


@pytest.mark.parametrize(
    "key",
    [
        "workflow_authorization_is_owner_mechanical_authorization",
        "physical_actuator_or_release_authorized",
        "current_system_binding_authorized",
        "formal_nc19_credit_authorized",
        "production_or_next_stage_authorized",
    ],
)
def test_authority_boundary_false(contracts, key):
    assert contracts["authorization"]["authority_boundary"][key] is False


def test_bound_sources_exist_and_match_bytes(contracts, project_root):
    for row in contracts["bindings"]["sources"]:
        path = project_root / row["path"]
        assert path.is_file(), row["id"]
        assert path.stat().st_size == row["bytes"], row["id"]
        assert _sha(path) == row["sha256"], row["id"]


def test_parent_b4e_terminal_recursive_records(contracts, project_root):
    row = next(x for x in contracts["bindings"]["sources"] if x["id"] == "b4e_terminal_manifest")
    terminal_path = project_root / row["path"]
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    parent = terminal_path.parents[1]
    assert terminal["self_excluded"] is True
    for item in terminal["entries"]:
        path = parent / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert _sha(path) == item["sha256"]


def test_frozen_b4_terminal_and_gate_anchors(project_root):
    terminal = project_root / "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_synthetic_6d_constraint_acquisition_release/results/SIM13_V4B4_CONTRACT_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"
    gate = terminal.with_name("SIM13_V4B4_CONTRACT_AUDITED_GATE_V1.json")
    assert _sha(terminal) == "09D26114D50358FD488BF51912C68FDB3993AB0035201B22478D7CD9A9B7B76E"
    assert _sha(gate) == "55441DFF42C92235B14DF9C810B013ADC2E59D5607D7697A5D85795149431D92"


def test_parent_binding_policy_fail_closed(contracts):
    assert contracts["bindings"]["parent_source_mutation_authorized"] is False
    assert contracts["bindings"]["parent_b4e_recursive_manifest_verification_required"] is True
    assert contracts["bindings"]["frozen_b4_recursive_manifest_verification_required"] is True
    expected_paths = {
        "b4e_audited_gate": "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/results/SIM13_V4B4E_AUDITED_GATE_V1.json",
        "b4e_terminal_manifest": "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/results/SIM13_V4B4E_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json",
        "b4e_solver_source": "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/b4_solver/constraint_solver.py",
        "b4e_run_spec": "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/contracts/PHASE_B4E_RUN_SPEC_V1.json",
        "b4e_hybrid_fixture": "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/evidence/SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json",
        "b4_model_contract": "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_synthetic_6d_constraint_acquisition_release/contracts/PHASE_B4_MODEL_CONTRACT_V1.json",
        "b4_numerical_contract": "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_synthetic_6d_constraint_acquisition_release/contracts/PHASE_B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1.json",
    }
    assert {row["id"]: row["path"] for row in contracts["bindings"]["sources"]} == expected_paths
