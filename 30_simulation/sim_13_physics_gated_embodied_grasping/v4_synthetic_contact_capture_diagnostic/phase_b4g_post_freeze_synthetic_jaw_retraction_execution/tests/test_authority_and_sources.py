from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


@pytest.mark.parametrize(
    "field",
    [
        "create_separate_post_freeze_execution_sibling",
        "freeze_execution_disambiguation_spec_before_solver_run",
        "implement_and_test_synthetic_p_only_forced_active_solver",
        "execute_registered_a0_a1_and_conditional_a2_campaign",
        "execute_registered_negative_controls",
        "write_synthetic_diagnostic_evidence",
    ],
)
def test_post_freeze_workflow_actions_are_authorized(contracts, field):
    assert contracts["authorization"]["authorized"][field] is True


@pytest.mark.parametrize(
    "field",
    [
        "modify_b4_b4e_or_b4f",
        "modify_or_generate_urdf",
        "instantiate_current_system_interface",
        "introduce_physical_gripper_parameters",
        "invoke_private_builder_or_generator",
    ],
)
def test_parent_physical_and_current_system_actions_are_not_authorized(contracts, field):
    assert contracts["authorization"]["authorized"][field] is False


def test_workflow_authorization_never_becomes_owner_or_physical_authority(contracts):
    boundary = contracts["authorization"]["authority_boundary"]
    assert boundary == {
        "workflow_authorization_is_owner_mechanical_authorization": False,
        "physical_actuator_contact_lock_or_release_authorized": False,
        "current_system_binding_authorized": False,
        "formal_nc19_credit_authorized": False,
        "production_or_next_stage_authorized": False,
    }


def test_authorization_is_anchored_to_bound_b4f_gate(contracts):
    auth_sha = contracts["authorization"]["basis"]["parent_b4f_audited_gate_sha256"]
    bound = next(
        row for row in contracts["bindings"]["sources"] if row["id"] == "b4f_audited_gate"
    )
    assert auth_sha == bound["sha256"]


def test_bound_source_inventory_is_exact(contracts):
    assert [row["id"] for row in contracts["bindings"]["sources"]] == [
        "b4f_audited_gate",
        "b4f_terminal",
        "b4f_model_energy",
        "b4f_experiment",
        "b4f_numerical",
        "b4f_governance",
        "b4f_evidence_schema",
        "b4e_solver",
        "b4e_run_spec",
        "b4e_audited_gate",
        "b4e_terminal",
    ]


def test_all_bound_sources_exist_and_match_bytes_and_sha256(contracts, project_root):
    for row in contracts["bindings"]["sources"]:
        path = project_root / row["path"]
        assert path.is_file(), row["id"]
        assert path.stat().st_size == row["bytes"], row["id"]
        assert _sha256(path) == row["sha256"], row["id"]


def test_b4f_terminal_recursively_pins_every_record(contracts, project_root):
    row = next(x for x in contracts["bindings"]["sources"] if x["id"] == "b4f_terminal")
    terminal_path = project_root / row["path"]
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    assert terminal["self_excluded"] is True
    assert terminal["acyclic"] is True
    assert terminal_path.name not in {Path(item["path"]).name for item in terminal["records"]}
    for item in terminal["records"]:
        path = project_root / item["path"]
        assert path.is_file(), item["role"]
        assert path.stat().st_size == item["bytes"], item["role"]
        assert _sha256(path) == item["sha256"], item["role"]


def test_bound_b4f_gate_is_final_contract_audit_without_execution(contracts, project_root):
    row = next(x for x in contracts["bindings"]["sources"] if x["id"] == "b4f_audited_gate")
    gate = json.loads((project_root / row["path"]).read_text(encoding="utf-8"))
    assert gate["final"] is True
    assert gate["contract_capability_state"] == {
        "b4f_contract_frozen": True,
        "b4f_contract_audited": True,
        "parent_b4e_recursively_verified": True,
    }
    assert gate["implementation_and_campaign_state"]["b4f_solver_implemented"] is False
    assert gate["implementation_and_campaign_state"]["b4f_campaign_executed"] is False


def test_parent_packages_are_read_only_and_recursive_verification_is_required(contracts):
    bindings = contracts["bindings"]
    assert bindings["all_parent_packages_read_only"] is True
    assert bindings["recursive_b4f_to_b4e_to_b4_verification_required"] is True


def test_evidence_publication_is_atomic_self_excluding_and_audit_independent(contracts):
    schema = contracts["schema"]
    assert schema["atomic_json_required"] is True
    assert schema["atomic_npz_required"] is True
    assert schema["self_exclusion"] == {
        "source_manifest_self_excluded": True,
        "evidence_manifest_self_excluded": True,
        "terminal_manifest_self_excluded": True,
    }
    assert schema["independent_audit_imports_solver_validator_or_tests"] is False
    assert schema["stale_final_cleanup_on_any_failure_required"] is True
    assert schema["publication_order"][-1] == (
        "SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"
    )


def test_no_forbidden_local_artifact_has_been_created(contracts, phase_root):
    files = [path for path in phase_root.rglob("*") if path.is_file()]
    names = {path.name for path in files}
    forbidden = contracts["governance"]["forbidden_local_artifacts"]
    assert not any(path.suffix.lower() == ".urdf" for path in files)
    for literal in forbidden[1:]:
        assert literal not in names

