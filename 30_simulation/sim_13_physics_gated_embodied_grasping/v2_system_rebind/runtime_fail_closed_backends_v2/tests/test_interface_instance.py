"""MECH_RL_SYSTEM_INTERFACE_V2.yaml instance tests: schema, slots, pins."""

from __future__ import annotations

from pathlib import Path

import yaml

import emit_mech_rl_system_interface_v2 as emitter


SCHEMA_DEFINITION_RELATIVE = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    "/unified_r2_digital_prototype_prebind/sim13_versioned_rebind_boundary_v2"
    "/MECH_RL_SYSTEM_INTERFACE_V2_SCHEMA_DEFINITION.yaml"
)
INTERFACE_PATH = (
    Path(__file__).resolve().parents[2]
    / "interfaces"
    / "MECH_RL_SYSTEM_INTERFACE_V2.yaml"
)


def _definition(project_root: Path) -> dict:
    return yaml.safe_load(
        (project_root / SCHEMA_DEFINITION_RELATIVE).read_text(encoding="utf-8")
    )


def _instance() -> dict:
    return yaml.safe_load(INTERFACE_PATH.read_text(encoding="utf-8"))


def test_instance_matches_schema_definition_top_level(project_root):
    definition = _definition(project_root)
    instance = _instance()
    required = set(definition["required_top_level_fields"])
    assert required.issubset(set(instance))
    assert instance["schema"] == definition["field_schema"]["schema"]["exact_value"]
    assert (
        instance["configuration_id"]
        == definition["field_schema"]["configuration_id"]["exact_value"]
    )
    assert instance["selected_bus_mass_mode"] == "EXPLICIT_STRUCTURE_PLUS_RESIDUAL"


def test_core_artifacts_and_nine_gate_slots_present(project_root):
    definition = _definition(project_root)
    instance = _instance()
    artifacts = instance["artifacts"]
    for entry in definition["field_schema"]["artifacts"]["required_entries"]:
        assert entry in artifacts
        assert set(artifacts[entry]) == {"path", "bytes", "sha256"}
    gate_stages = artifacts["gate_stages"]
    expected = definition["field_schema"]["artifacts"]["gate_stage_required_entries"]
    assert set(gate_stages) == set(expected)
    slot_count = 0
    for stage, slots in expected.items():
        assert set(gate_stages[stage]) == set(slots)
        for slot in slots:
            record = gate_stages[stage][slot]
            assert set(record) == {"path", "bytes", "sha256"}
            assert len(record["sha256"]) == 64
            slot_count += 1
    assert slot_count == 9


def test_whole_system_and_b601_contracts_exact(project_root):
    definition = _definition(project_root)
    instance = _instance()
    for key, value in definition["field_schema"]["whole_system_contract"][
        "exact_fields"
    ].items():
        assert instance["whole_system_contract"][key] == value
    for key, value in definition["field_schema"]["accepted_b601_subtree"][
        "exact_fields"
    ].items():
        assert instance["accepted_b601_subtree"][key] == value


def test_authority_values_truthful_no_release_credit():
    instance = _instance()
    values = instance["authority"]["current_values"]
    assert values["owner_accepted"] is False
    assert values["route_c_exclusion_accepted_for_this_sim_candidate"] is False
    assert values["route_c_scope_disposition_pass"] is False
    assert values["sim13_system_binding_gate_passed"] is False
    assert values["consumer_load_all_of_passed"] is False
    assert values["contact_grasp_all_of_passed"] is False
    assert values["current_consumer_load_authorized"] is False
    assert values["current_contact_grasp_authorized"] is False
    assert values["runtime_fail_closed_gate_passed"] is True
    assert values["dynamics_backend_gate_passed"] is True
    assert values["contact_grasp_gate_passed"] is True
    assert instance["next_stage_authorized"] is False
    assert instance["release_credit"] is False
    assert instance["review_status"] == "PENDING_OWNER_REVIEW"


def test_emission_deterministic_and_live_artifact_pins():
    document = emitter.build_interface()
    payload = yaml.safe_dump(document, sort_keys=True, allow_unicode=True)
    assert INTERFACE_PATH.read_text(encoding="utf-8") == payload
    artifacts = document["artifacts"]
    for name, record in artifacts.items():
        if name == "gate_stages":
            continue
        live = emitter._record(record["path"])
        assert live == record
    for stage, slots in artifacts["gate_stages"].items():
        for slot, record in slots.items():
            live = emitter._record(record["path"])
            assert live == record
