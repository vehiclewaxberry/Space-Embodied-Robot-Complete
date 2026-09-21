from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
MODULE_PATH = PACKAGE / "aggregate_digital_prototype_dynamics_entry_v3.py"
SPEC = importlib.util.spec_from_file_location("aggregate_entry_v3", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def gate() -> dict:
    return MODULE.load_json(
        PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3.json"
    )


def test_all_eleven_source_pins_are_exact() -> None:
    documents, binding = MODULE.load_sources()
    assert binding["all_match"] is True
    assert binding["matched"] == binding["total"] == 11
    assert set(documents) == set(MODULE.SOURCE_PINS)


def test_aggregate_is_reproducible_and_nineteen_of_nineteen() -> None:
    expected = MODULE.canonical_bytes(MODULE.build_gate())
    assert (
        PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3.json"
    ).read_bytes() == expected
    assert gate()["summary"] == {"passed": 19, "total": 19, "failed": []}


def test_source_pin_drift_fails_closed_without_partial_credit() -> None:
    original = deepcopy(MODULE.SOURCE_PINS)
    try:
        MODULE.SOURCE_PINS["dg5_candidate_gate"]["bytes"] += 1
        drifted = MODULE.build_gate()
    finally:
        MODULE.SOURCE_PINS.clear()
        MODULE.SOURCE_PINS.update(original)
    assert drifted["technical_verdict"] == "SOURCE_HASH_DRIFT__FAIL_CLOSED"
    assert drifted["summary"] == {
        "passed": 0,
        "total": 1,
        "failed": ["V3-01_all_11_source_pins_exact"],
    }
    assert drifted["next_stage_authorized"] is False
    assert drifted["release_credit"] is False


def test_all_five_dynamics_lanes_are_candidate_only() -> None:
    ledger = gate()["dynamics_candidate_ledger"]
    assert set(ledger) >= {"DG1", "DG2", "DG3", "DG4", "DG5"}
    assert ledger["DG3"]["parent_satisfied"] is False
    assert ledger["DG4"]["parent_satisfied"] is False
    assert ledger["DG5"]["parent_satisfied"] is False
    assert ledger["parent_dynamics_engineering_complete"] is False
    assert ledger["DG2"]["forbidden_inference"].startswith("NOT_TORQUE_DRIVEN")


def test_DG4_never_claims_attachment_or_physical_contact() -> None:
    dg4 = gate()["dynamics_candidate_ledger"]["DG4"]
    assert dg4["terminal_state"] == "POST_IMPACT_DIAGNOSTIC"
    assert dg4["real_attachment_ready"] is False
    assert dg4["physical_contact_ready"] is False


def test_DG5_880_count_is_not_named_physical_or_probabilistic() -> None:
    dg5 = gate()["dynamics_candidate_ledger"]["DG5"]
    assert dg5["corners_evaluated"] == 1024
    assert dg5["basic_rigid_body_constraints_not_falsified"] == 880
    assert dg5["quarantined_basic_constraint_failures"] == 144
    assert dg5["probability_or_as_built_credit"] is False


def test_option_A_and_mount_are_closed_but_M01_is_not() -> None:
    state = gate()["mechanical_and_M01_state"]
    assert state["owner_option_a_selected"] is True
    assert state["execution_mount_full_precision_bound"] is True
    assert state["accepted_urdf_subtree_frame_ledger"] == "10_OF_10"
    assert state["M01_required_scene_fields"] == "0_OF_9"
    assert state["M01_instantiated_stage_scenes"] == "0_OF_3"
    assert state["clearance_policy"] == "0_OF_11166"
    assert state["runtime_memory_admission_pass"] is False
    assert state["fresh_low_memory_owner_override_authorized"] is False


def test_supersession_is_field_limited() -> None:
    rows = gate()["supersession_ledger"]
    assert rows[0]["superseded_field_only"] == "OWNER_OPTION_SELECTION"
    assert rows[0]["broader_gate_inheritance"] is False
    assert rows[1]["M01_query_or_search_inheritance"] is False


def test_control_scope_is_predevelopment_only_and_joint_gate_is_four_of_thirteen() -> None:
    state = gate()["control_and_joint_state"]
    assert state["offline_control_predevelopment_candidate_packaging"] == "9_OF_9"
    assert state["offline_control_predevelopment_research_scope_available"] is True
    assert state["technical_predevelopment_complete"] is False
    assert state["control_engineering_complete"] is False
    assert state["safe_current_tree_review_pass"] is False
    assert state["RL_or_VLA_execution_authorized"] is False
    assert state["joint_gate"] == "4_OF_13"
    assert state["sim13_maximum_operational_state"] == "ABORT_ONLY"


def test_all_execution_and_release_authorities_are_false() -> None:
    document = gate()
    actions = document["bounded_research_actions_available"]
    assert actions["DG1_to_DG5_candidate_evidence_consumption"] is True
    assert actions["offline_control_contract_metric_and_negative_result_predevelopment"] is True
    for name in (
        "integrated_candidate_CAD_generation",
        "geometry_pair_or_edge_query",
        "M01_path_search",
        "physical_contact_or_target_attachment",
        "non_abort_grasp",
        "RL_or_VLA_execution",
        "hardware_or_flight_execution",
    ):
        assert actions[name] is False
    assert document["next_stage_authorized"] is False
    assert document["release_credit"] is False


def test_manifest_binds_current_local_artifacts_and_all_external_pins() -> None:
    manifest = MODULE.load_json(
        PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V3.json"
    )
    assert manifest["summary"] == {
        "local_count": 4,
        "external_pin_count": 11,
        "all_exist": True,
    }
    assert manifest["external_source_pins"] == MODULE.SOURCE_PINS
    for record in manifest["local_artifacts"]:
        path = MODULE.ROOT / record["path"]
        assert path.stat().st_size == record["bytes"]
        assert MODULE.sha256(path) == record["sha256"]
    assert manifest["parent_gates_mutated"] is False
    assert manifest["next_stage_authorized"] is False
    assert manifest["release_credit"] is False


def test_json_is_finite() -> None:
    json.dumps(gate(), allow_nan=False)
