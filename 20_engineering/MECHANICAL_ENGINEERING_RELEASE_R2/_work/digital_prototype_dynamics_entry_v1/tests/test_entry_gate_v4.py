from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
MODULE_PATH = PACKAGE / "aggregate_digital_prototype_dynamics_entry_v4.py"
SPEC = importlib.util.spec_from_file_location("aggregate_entry_v4", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def gate() -> dict:
    return MODULE.load_json(
        PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json"
    )


def sources() -> tuple[dict, dict, dict]:
    documents, binding = MODULE.load_sources()
    runtime = MODULE.observe_runtime(
        documents["cad_postgeneration_validator_preflight"]
    )
    return documents, binding, runtime


def test_all_seven_upstream_source_pins_are_exact() -> None:
    documents, binding, _ = sources()
    assert binding["all_match"] is True
    assert binding["matched"] == binding["total"] == 7
    assert set(documents) == set(MODULE.SOURCE_PINS)


def test_v4_gate_is_byte_reproducible_and_twenty_eight_of_twenty_eight() -> None:
    expected = MODULE.canonical_bytes(MODULE.build_gate())
    output = PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json"
    assert output.read_bytes() == expected
    assert gate()["summary"] == {"passed": 28, "total": 28, "failed": []}
    assert gate()["technical_verdict"] == (
        "PASS_ADDITIVE_CAD_EXECUTION_PREPARATION_M01_PREBIND_AND_CURRENT_STATE_REISSUE__"
        "CANDIDATE_STEP_M01_QUERY_NON_ABORT_PARENT_GATES_AND_RELEASE_HOLD"
    )


def test_source_pin_drift_fails_closed_without_partial_credit() -> None:
    original = deepcopy(MODULE.SOURCE_PINS)
    try:
        MODULE.SOURCE_PINS["entry_manifest_v3"]["bytes"] += 1
        drifted = MODULE.build_gate()
    finally:
        MODULE.SOURCE_PINS.clear()
        MODULE.SOURCE_PINS.update(original)
    assert drifted["technical_verdict"] == "SOURCE_HASH_DRIFT__FAIL_CLOSED"
    assert drifted["summary"] == {
        "passed": 0,
        "total": 1,
        "failed": ["V4-01_all_7_source_pins_exact"],
    }
    assert drifted["next_stage_authorized"] is False
    assert drifted["release_credit"] is False


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"state": false, "state": true}\n', encoding="utf-8")
    with pytest.raises(MODULE.AggregateError, match="DUPLICATE_JSON_KEY:state"):
        MODULE.load_json(path)


def test_duplicate_csv_manifest_paths_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.csv"
    path.write_text(
        "path,bytes,sha256\n"
        + "a.json,1,"
        + "A" * 64
        + "\n"
        + "a.json,1,"
        + "A" * 64
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(MODULE.AggregateError, match="DUPLICATE_OR_EMPTY_CSV_PATH"):
        MODULE.load_csv_manifest(path)


def test_CAD_preparation_is_not_CAD_generation_or_geometry_credit() -> None:
    state = gate()["CAD_state"]
    assert state["expected_candidate_solids"] == 399
    assert state["expected_candidate_groups"] == 2
    assert state["candidate_step_present"] is False
    assert state["hidden_glb_present"] is False
    assert state["candidate_artifact_generated"] is False
    assert state["candidate_geometry_validated"] is False
    assert state["candidate_snapshot_executed"] is False
    assert state["candidate_snapshot_outputs_present"] == 0
    assert state["CAD_generation_authorized_by_V4"] is False


def test_M01_prebind_retains_zero_execution_state() -> None:
    state = gate()["M01_state"]
    assert state["prebind_checks"] == "18_OF_18"
    assert state["explicit_decision_keys"] == "30_OF_30"
    assert state["authoritative_values"] == "0_OF_30"
    assert state["legacy_required_values"] == "0_OF_9"
    assert state["stage_instances"] == "0_OF_3"
    assert state["asset_level_operational_authority"] == "1_OF_150"
    assert state["clearance_policy"] == "0_OF_11166"
    assert state["pair_oracle"] == "0_OF_11166"
    assert state["motion_certificates"] == "0_OF_150"
    assert state["continuous_edges_certified"] == 0
    assert state["pair_query_authorized"] is False
    assert state["path_search_authorized"] is False


def test_route_contact_nonabort_and_all_parent_release_states_are_HOLD() -> None:
    state = gate()["system_HOLD_state"]
    assert state["Route_C_formal_pass"] is False
    assert state["Route_C_raw_clearance_mm"] == -10.729480331980062
    assert state["Route_C_gated_clearance_mm"] == -17.313396996697108
    assert state["physical_contact_authority"] is False
    assert state["non_abort_authority"] is False
    assert state["Sim13_maximum_operational_state"] == "ABORT_ONLY"
    for name in (
        "parent_dynamics_complete",
        "parent_control_complete",
        "joint_system_ready",
        "terminal_mechanical_gate_a_pass",
        "mechanical_release_ready",
        "flight_release",
    ):
        assert state[name] is False


def test_every_execution_or_release_action_remains_false() -> None:
    document = gate()
    actions = document["bounded_actions_available"]
    for name in (
        "generate_integrated_candidate_CAD",
        "claim_candidate_geometry_validated",
        "claim_candidate_snapshot_complete",
        "execute_M01_pair_query",
        "execute_M01_path_search",
        "claim_Route_C_pass",
        "claim_physical_contact_or_non_abort",
        "execute_RL_or_VLA",
        "claim_parent_or_release_pass",
    ):
        assert actions[name] is False
    assert document["next_stage_authorized"] is False
    assert document["release_credit"] is False


def test_v4_manifest_is_self_excluded_and_all_entries_are_exact() -> None:
    path = PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V4.json"
    manifest = MODULE.load_json(path)
    assert manifest == MODULE.build_manifest()
    assert manifest["summary"] == {
        "local_count": 3,
        "external_pin_count": 7,
        "all_exist": True,
    }
    assert manifest["external_source_pins"] == MODULE.SOURCE_PINS
    assert manifest["self_reference_policy"].endswith("EXCLUDES_ITSELF")
    assert all(
        not record["path"].endswith(
            "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V4.json"
        )
        for record in manifest["local_artifacts"]
    )
    for record in manifest["local_artifacts"]:
        assert MODULE._record_matches(record, MODULE.ROOT)
    assert manifest["parent_gates_mutated"] is False
    assert manifest["next_stage_authorized"] is False
    assert manifest["release_credit"] is False


@pytest.mark.parametrize(
    ("case", "failed_check"),
    [
        ("v3_manifest_local_pin", "V4-04_V3_manifest_local_records_and_gate_pin_are_exact"),
        ("v3_physical_action", "V4-05_V3_denies_CAD_M01_physical_nonabort_and_release_authority"),
        ("cad_source_pin", "V4-07_all_9_CAD_preflight_source_pins_exact"),
        ("candidate_step_present", "V4-08_candidate_STEP_and_hidden_GLB_absent_and_geometry_unvalidated"),
        ("snapshot_present", "V4-09_candidate_snapshot_not_executed_and_four_outputs_absent"),
        ("memory_override", "V4-10_CAD_preflight_does_not_claim_memory_or_owner_override"),
        ("m01_check_count", "V4-11_M01_append_only_prebind_18_of_18"),
        ("m01_stage_instance", "V4-12_M01_has_30_explicit_keys_but_zero_values_and_zero_of_three_scenes"),
        ("m01_operational_count", "V4-14_M01_only_one_of_150_assets_has_asset_level_operational_authority"),
        ("m01_query_authority", "V4-15_M01_zero_of_11166_queries_zero_edges_and_search_false"),
        ("m01_manifest_pin", "V4-16_M01_six_row_manifest_is_self_excluded_and_exact"),
        ("current_manifest_self_policy", "V4-18_current_state_six_entry_package_manifest_self_excluded_and_exact"),
        ("route_c_pass", "V4-20_Route_C_negative_witness_and_formal_HOLD_preserved"),
        ("sim13_nonabort", "V4-21_Sim13_20_of_20_is_backend_negative_control_only_and_ABORT_ONLY"),
        ("parent_dynamics_pass", "V4-22_DG_candidates_do_not_promote_parent_dynamics"),
        ("physical_contact_authority", "V4-23_physical_contact_and_non_ABORT_authority_remain_false"),
        ("control_complete", "V4-24_parent_control_SAFE_RL_VLA_and_joint_system_remain_HOLD"),
        ("drawing_release", "V4-25_L06_eight_drawings_prohibited_and_6061_vs_7075_conflict_open"),
        ("mechanical_release", "V4-26_terminal_mechanical_and_release_Gates_remain_HOLD"),
        ("source_next_stage", "V4-27_all_source_authority_flags_fail_closed"),
        ("parent_mutation", "V4-28_no_parent_mutation_or_supersession_claim"),
    ],
)
def test_semantic_tampering_fails_closed(case: str, failed_check: str) -> None:
    loaded, binding, runtime = sources()
    documents = deepcopy(loaded)
    runtime = deepcopy(runtime)

    if case == "v3_manifest_local_pin":
        documents["entry_manifest_v3"]["local_artifacts"][0]["bytes"] += 1
    elif case == "v3_physical_action":
        documents["entry_gate_v3"]["bounded_research_actions_available"][
            "physical_contact_or_target_attachment"
        ] = True
    elif case == "cad_source_pin":
        documents["cad_postgeneration_validator_preflight"]["source_pins"][
            "generator"
        ]["bytes"] += 1
    elif case == "candidate_step_present":
        runtime["candidate_step"]["present"] = True
    elif case == "snapshot_present":
        runtime["candidate_snapshot_outputs"][0]["present"] = True
    elif case == "memory_override":
        documents["cad_postgeneration_validator_preflight"][
            "owner_override_used"
        ] = True
    elif case == "m01_check_count":
        documents["m01_prebind_gate"]["checks_passed"] = 17
    elif case == "m01_stage_instance":
        documents["m01_prebind_gate"]["scene_accounting"][
            "stage_instances_bound"
        ] = 1
    elif case == "m01_operational_count":
        documents["m01_prebind_gate"]["asset_accounting"][
            "operational_authority_rows"
        ] = 2
    elif case == "m01_query_authority":
        documents["m01_prebind_gate"]["system_execution_state"][
            "system_pair_evaluation_authorized"
        ] = True
    elif case == "m01_manifest_pin":
        documents["m01_prebind_manifest"]["rows"][0]["sha256"] = "0" * 64
    elif case == "current_manifest_self_policy":
        documents["current_state_package_manifest_v2"][
            "self_reference_policy"
        ] = "SELF_INCLUDED"
    elif case == "route_c_pass":
        documents["current_state_gate_v2"]["current_truth"][
            "mechanical_m01_route_c"
        ]["route_c_formal_pass"] = True
    elif case == "sim13_nonabort":
        documents["current_state_gate_v2"]["current_truth"]["sim13"][
            "maximum_operational_state"
        ] = "NON_ABORT"
    elif case == "parent_dynamics_pass":
        documents["current_state_gate_v2"]["current_truth"]["dynamics"][
            "parent_dynamics"
        ] = "6_OF_6_PASS"
    elif case == "physical_contact_authority":
        documents["current_state_gate_v2"]["current_truth"]["sim13"][
            "current_contact_grasp_authorized"
        ] = True
    elif case == "control_complete":
        documents["current_state_gate_v2"]["current_truth"][
            "control_and_joint"
        ]["control_engineering_complete"] = True
    elif case == "drawing_release":
        documents["current_state_gate_v2"]["current_truth"][
            "l06_drawing_bom_material_conflict"
        ]["manufacturing_or_procurement_release"] = True
    elif case == "mechanical_release":
        documents["current_state_gate_v2"]["mechanical_release_ready"] = True
    elif case == "source_next_stage":
        documents["m01_prebind_gate"]["next_stage_authorized"] = True
    elif case == "parent_mutation":
        documents["current_state_gate_v2"]["parent_artifacts_modified"] = True
    else:  # pragma: no cover - the parameter table is exhaustive
        raise AssertionError(case)

    result = MODULE.evaluate(documents, binding, runtime)
    assert result["checks"][failed_check] is False
    assert failed_check in result["summary"]["failed"]
    assert result["technical_verdict"] == (
        "ADDITIVE_PREPARATION_AND_REISSUE_HOLD__SEE_FAILED_CHECKS"
    )
    assert result["next_stage_authorized"] is False
    assert result["release_credit"] is False


def test_gate_and_manifest_json_are_finite() -> None:
    json.dumps(gate(), allow_nan=False)
    json.dumps(MODULE.build_manifest(), allow_nan=False)
