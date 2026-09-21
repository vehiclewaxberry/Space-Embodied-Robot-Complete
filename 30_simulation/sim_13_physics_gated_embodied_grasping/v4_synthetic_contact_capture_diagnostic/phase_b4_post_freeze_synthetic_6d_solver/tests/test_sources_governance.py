from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import b4_solver.constraint_solver as solver


def test_all_direct_and_transitive_sources_verify():
    verified = solver.verify_bound_sources()
    assert len(verified) == 11


@pytest.mark.parametrize("source_id", [
    "b4_contract_audited_gate", "b4_contract_terminal_manifest", "b4_model_contract",
    "b4_numerical_contract", "b4_source_contract", "b4_governance_contract",
    "b4_units_contract", "b3_reference_trace", "b3_branched_model",
    "b3_contact_kernel", "full_floating_model",
])
def test_each_direct_source_has_exact_bound_bytes_and_sha(source_id, phase_root):
    binding = json.loads((phase_root / "contracts" / "PHASE_B4E_SOURCE_BINDINGS_V1.json").read_text(encoding="utf-8"))
    item = next(value for value in binding["sources"] if value["id"] == source_id)
    path = solver._project_root() / item["path"]
    assert path.stat().st_size == item["bytes"]
    assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == item["sha256"]


def test_frozen_b4_contract_package_remains_contract_only(phase_root):
    gate = json.loads((phase_root.parent / "phase_b4_synthetic_6d_constraint_acquisition_release" / "results" / "SIM13_V4B4_CONTRACT_AUDITED_GATE_V1.json").read_text(encoding="utf-8"))
    assert gate["overall_status"].startswith("PASS_PHASE_B4_CONTRACT_FREEZE_ONLY")
    assert gate["authorizations"]["b4_dynamics_solver_implemented"] is False


def test_post_freeze_work_authority_is_not_owner_authority(phase_root):
    contract = json.loads((phase_root / "contracts" / "PHASE_B4E_POST_FREEZE_WORK_AUTHORIZATION_V1.json").read_text(encoding="utf-8"))
    assert contract["basis"]["post_freeze_plan_updated"] is True
    assert contract["authority_boundary"]["workflow_authorization_is_owner_mechanical_authorization"] is False
    assert not any(value for key, value in contract["authority_boundary"].items() if key != "workflow_authorization_is_owner_mechanical_authorization")


def test_run_horizon_is_bounded_and_not_physical(phase_root):
    spec = json.loads((phase_root / "contracts" / "PHASE_B4E_RUN_SPEC_V1.json").read_text(encoding="utf-8"))
    assert spec["active_propagation"]["end_time_s"] == 0.08
    assert "NOT_PHYSICAL" in spec["active_propagation"]["classification"]
    assert spec["horizon_exhaustion_semantics"]["equivalent_to_global_empty_eligibility_set"] is False
    transition = spec["synthetic_removal_transition"]
    assert transition["synthetic_fixture_pre_acquisition_P_coordinate_offset_m"] == -2.0e-5
    assert transition["synthetic_fixture_pre_acquisition_P_velocity_m_s"] == 2.0e-2
    assert transition["fixture_state_mutation_after_acquisition_forbidden"] is True
    assert transition["fixture_clearance_must_come_from_same_active_state_trajectory"] is True
    assert transition["fixture_removal_event_must_be_off_sample_grid"] is True
    assert transition["fixture_must_execute_propagate_active_finite_event_branch"] is True
    assert transition["fixture_values_are_hardware_specifications"] is False


@pytest.mark.parametrize("field", [
    "physical_6d_contact_closure", "physical_dual_contact_identified", "physical_friction_identified",
    "physical_actuator_timing_identified", "physical_retention_identified", "physical_lock_implemented",
    "physical_release_implemented", "physical_recontact_implemented", "held_capture_passed",
    "grasp_success_claimed", "target_attached_claimed", "released_attached_target_claimed",
    "current_system_bound", "formal_nc19_credit", "owner_authorized", "production_ready",
    "release_authorized", "next_stage_authorized", "physical_measurement_model_available",
    "gum_or_monte_carlo_uncertainty_authorized",
])
def test_every_forbidden_authority_is_false(field, phase_root):
    governance = json.loads((phase_root / "contracts" / "PHASE_B4E_GOVERNANCE_V1.json").read_text(encoding="utf-8"))
    assert governance["required_false"][field] is False


def test_formal_sim13_state_is_unchanged(phase_root):
    governance = json.loads((phase_root / "contracts" / "PHASE_B4E_GOVERNANCE_V1.json").read_text(encoding="utf-8"))
    assert governance["formal_sim13_v2_state_unchanged"] == {
        "passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]
    }


def test_no_forbidden_artifact_exists_in_post_freeze_tree(phase_root):
    names = {path.name for path in phase_root.rglob("*") if path.is_file()}
    forbidden = {"MECH_RL_SYSTEM_INTERFACE_V2.yaml", "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json", "execution.lock", "release.marker"}
    assert not names.intersection(forbidden)
    assert not any(path.suffix.lower() == ".urdf" for path in phase_root.rglob("*"))


def test_uncertainty_is_not_invented(phase_root):
    upstream = json.loads((phase_root.parent / "phase_b4_synthetic_6d_constraint_acquisition_release" / "contracts" / "PHASE_B4_UNCERTAINTY_AND_UNITS_LEDGER_V1.json").read_text(encoding="utf-8"))
    assert upstream["physical_measurement_model_available"] is False
    assert upstream["gum_or_monte_carlo_uncertainty_propagation_authorized"] is False
