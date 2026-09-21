import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
REPO = next(parent for parent in HERE.parents if (parent / "PROJECT_MAP.md").is_file())
SPEC = importlib.util.spec_from_file_location("odr60_execution_closure", HERE / "build_execution_closure.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


@pytest.fixture(scope="module")
def outputs():
    return MOD.build_outputs(REPO)


@pytest.fixture(scope="module")
def documents(outputs):
    return {name: json.loads(text, object_pairs_hook=MOD.strict_pairs) for name, text in outputs.items() if name.endswith(".json")}


def test_all_source_hashes_match():
    rows = MOD.verify_source_pins(REPO)
    assert len(rows) == len(MOD.SOURCE_PINS)
    assert all(row["match"] is True for row in rows)


def test_owner_selects_exactly_option_a(documents):
    record = documents["OWNER_SELECTION_RECORD_V1.json"]
    assert record["selection"]["option_a_selected"] is True
    assert record["selection"]["option_b_selected"] is False
    assert record["selection"]["hold_option_selected"] is False
    assert record["selection"]["exactly_one_branch_selected"] is True
    assert record["selection"]["machine_evidence"] == "EXPLICIT_EXECUTION_PROMPT_BLOCK_FIRST_LINE"
    assert record["machine_authority_evidence"]["authorized"] is True
    assert record["machine_authority_evidence"]["first_nonempty_line_raw"] == MOD.OPTION_A


@pytest.mark.parametrize(
    "text",
    [
        # A quoted token without the exact execution-prompt heading is not authority.
        f"> {MOD.OPTION_A}",
        # A recommendation is not authority.
        f"建议使用：{MOD.OPTION_A}",
        # The token must be the raw first non-empty line of the titled block.
        f"{MOD.EXECUTION_PROMPT_HEADING}\n\n```text\n# comment\n{MOD.OPTION_A}\n```",
        # Multiple branch tokens in the execution block are ambiguous and fail closed.
        f"{MOD.EXECUTION_PROMPT_HEADING}\n\n```text\n{MOD.OPTION_A}\n{MOD.OPTION_B}\n```",
    ],
)
def test_non_authoritative_token_placements_fail_closed(text):
    result = MOD.parse_execution_prompt_selection(text, [MOD.OPTION_A, MOD.OPTION_B, MOD.OPTION_HOLD])
    assert result["authorized"] is False
    assert result["selected_token"] is None


def test_low_memory_token_is_explicitly_not_authorized(documents):
    low = documents["OWNER_SELECTION_RECORD_V1.json"]["low_memory"]
    assert low["explicitly_not_authorized_now"] is True
    assert low["authorized_run_id"] is None
    assert low["memory_gate_passed"] is False
    assert low["runtime_memory_admission_pass"] is False


def test_mount_full_precision_spelling_is_bound(documents):
    mount = documents["EXECUTION_MOUNT_BINDING_V1.json"]
    matrix = mount["binding"]["canonical_matrix_decimal_strings"]
    assert mount["execution_mount_numeric_spelling_bound"] is True
    assert matrix[1][:2] == ["0.422618483193", "0.906307683772"]
    assert matrix[2][:2] == ["-0.906307683772", "0.422618483193"]
    assert matrix[0][3] == "0.208000000000"
    assert mount["system_mount_binding_sha256"] == mount["canonical_binding_payload_sha256"]
    assert len(mount["runtime_mount_numeric_spelling_policy_sha256"]) == 64


def test_mount_prohibits_d6_and_bridge_reapplication(documents):
    policy = documents["EXECUTION_MOUNT_BINDING_V1.json"]["spelling_policy"]
    assert policy["historical_D6_6dp_mount_forbidden"] is True
    assert policy["mixing_D6_and_full_precision_forbidden"] is True
    assert policy["mpi_physical_to_dynamics_bridge_reapplication_in_collision_scene_forbidden"] is True


def test_collision_frame_ledger_binds_ten_accepted_urdf_rows(documents):
    collision = documents["COLLISION_FRAME_REGISTRATION_V1.json"]
    assert collision["summary"]["accepted_urdf_link_count"] == 10
    assert collision["summary"]["registry_A_object_count"] == 10
    assert collision["summary"]["frame_relationships_bound"] == 10
    assert collision["summary"]["rows_with_all_verifiable_fields_crosschecked"] == 10
    assert len(collision["registrations"]) == 10
    assert collision["execution_mount_binding"]["spacecraft_mount_transform_baked_into_assets"] is False
    for row in collision["registrations"]:
        assert row["all_verifiable_fields_crosschecked"] is True
        assert row["frame_relationship_bound"] is True
        assert row["runtime_object_pose_bound"] is False
        assert row["T_registration_frame_asset_storage"] is not None
        assert row["evidence_cross_checks"]
        assert all(type(value) is bool and value is True for value in row["evidence_cross_checks"].values())


def test_collision_operational_promotion_remains_one_of_ten(documents):
    collision = documents["COLLISION_FRAME_REGISTRATION_V1.json"]
    promoted = [row for row in collision["registrations"] if row["operational_narrowphase_promoted"]]
    assert [row["object_id"] for row in promoted] == ["A::base_link"]
    assert collision["summary"]["complete_system_operational_collision_asset_set_bound"] is False


def test_gripper_states_are_not_guessed(documents):
    rows = documents["COLLISION_FRAME_REGISTRATION_V1.json"]["registrations"]
    fingers = [row for row in rows if row["object_id"] in {"A::gripper_left", "A::gripper_right"}]
    assert len(fingers) == 2
    assert all(row["motion_registration"]["state_value_m"] is None for row in fingers)
    assert all(row["motion_registration"]["runtime_state_bound"] is False for row in fingers)


def test_scene_schema_has_three_distinct_stages(documents):
    scene = documents["M01_THREE_STAGE_SCENE_SCHEMA_V2.json"]
    assert scene["schema_contract"]["stage_order"] == [
        "PRE_RELEASE_CONSTANT_SCENE",
        "RELEASE_EVENT_SCENE",
        "POST_RELEASE_CONSTANT_SCENE",
    ]
    assert scene["scene_schema_complete"] is True


def test_scene_instances_remain_zero_and_unknown(documents):
    scene = documents["M01_THREE_STAGE_SCENE_SCHEMA_V2.json"]
    assert scene["current_instances"]["stage_instances_bound"] == 0
    assert scene["current_instances"]["legacy_required_values_bound"] == 0
    assert scene["scene_binding_complete"] is False
    assert all(stage["instance"] is None for stage in scene["schema_contract"]["stages"])
    assert scene["fixed_structure_binding"]["complete_fixed_structure_binding"] is False
    assert scene["fixed_structure_binding"]["arm_execution_mount_document_sha256"] is not None


def test_fixed_endpoints_are_bound_but_candidate_path_is_not(documents):
    q = documents["M01_THREE_STAGE_SCENE_SCHEMA_V2.json"]["schema_contract"]["continuous_q_contract"]
    assert q["fixed_start_name"] == "STOW"
    assert q["fixed_goal_name"] == "RELEASE_CLEAR"
    assert q["candidate_path_sha256"] is None
    assert q["candidate_path_bound"] is False


def test_legacy_duplicate_is_detected_and_v2_is_strict(documents):
    old = REPO / MOD.SOURCE_PINS["legacy_preflight_gate"][0]
    assert MOD.duplicate_keys(old) == ["next_stage_authorized", "release_credit"]
    evidence = MOD.top_level_key_occurrence_evidence(old, ["next_stage_authorized", "release_credit"])
    assert evidence == {
        "next_stage_authorized": {
            "occurrence_count": 2,
            "native_values": [False, False],
            "all_values_are_native_boolean_false": True,
        },
        "release_credit": {
            "occurrence_count": 2,
            "native_values": [False, False],
            "all_values_are_native_boolean_false": True,
        },
    }
    v2 = documents["ODR60_OPTION_A_PREFLIGHT_GATE_V2.json"]
    assert v2["supersession"]["legacy_duplicate_key_evidence"] == evidence
    assert v2["supersession"]["duplicate_preserving_parser_check_pass"] is True
    assert v2["supersession"]["historical_file_modified"] is False
    assert v2["supersession"]["scientific_gate_upgrade_from_serialization_repair"] is False


def test_clearance_motion_and_oracle_counts_remain_zero(documents):
    ready = documents["ODR60_OPTION_A_PREFLIGHT_GATE_V2.json"]["static_closure"]
    assert (ready["clearance_policy_rows_bound"], ready["clearance_policy_rows_required"]) == (0, 11166)
    assert (ready["motion_certificates_bound"], ready["motion_certificates_required"]) == (0, 150)
    assert (ready["pair_oracle_rows_executed"], ready["pair_oracle_rows_required"]) == (0, 11166)


def test_all_execution_authorities_remain_false(documents):
    preflight = documents["ODR60_OPTION_A_PREFLIGHT_GATE_V2.json"]["execution_authority"]
    gate = documents["results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json"]
    assert all(
        preflight[key] is False
        for key in (
            "all_static_preconditions_pass", "runtime_memory_admission_pass",
            "geometry_load_or_query_authorized", "pair_evaluation_authorized",
            "edge_evaluation_authorized", "path_search_authorized", "path_search_executed",
            "next_stage_authorized", "release_credit",
        )
    )
    assert gate["execution_record"] == {
        "collision_geometry_loaded": False,
        "edges_certified": 0,
        "geometry_query_executed": False,
        "pair_queries_executed": 0,
        "path_search_executed": False,
        "path_search_process_started": False,
    }
    assert gate["owner_selection_recorded"] is True
    assert all(
        gate[key] is False
        for key in (
            "static_preflight_pass", "pair_evaluation_authorized",
            "edge_evaluation_authorized", "path_search_authorized",
            "path_search_executed", "next_stage_authorized", "release_credit",
        )
    )


def test_every_generated_json_has_unique_keys(outputs):
    for name, text in outputs.items():
        if name.endswith(".json"):
            json.loads(text, object_pairs_hook=MOD.strict_pairs)


def test_source_manifest_covers_exact_pins(outputs):
    rows = list(csv.DictReader(io.StringIO(outputs["ODR60_OPTION_A_SOURCE_HASH_MANIFEST_V1.csv"])))
    assert {row["source_id"] for row in rows} == set(MOD.SOURCE_PINS)
    assert all(row["match"] == "True" for row in rows)


def test_gate_local_artifact_pins_match_rendered_outputs(outputs, documents):
    pins = documents["results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json"]["local_artifact_pins"]
    assert set(pins) == set(outputs) - {"results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json"}
    for name, pin in pins.items():
        assert pin["path"] == name
        assert pin["sha256"] == MOD.sha256_bytes(outputs[name].encode("utf-8"))


def test_written_package_manifest_has_exact_local_coverage():
    manifest = HERE / "ODR60_OPTION_A_EXECUTION_CLOSURE_PACKAGE_SHA256_V1.csv"
    if not manifest.exists():
        pytest.skip("package manifest is emitted by the builder")
    rows = list(csv.DictReader(manifest.read_text(encoding="utf-8").splitlines()))
    actual = {
        path.relative_to(HERE).as_posix()
        for path in HERE.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != manifest.name
    }
    assert {row["path"] for row in rows} == actual
    for row in rows:
        path = HERE / row["path"]
        assert int(row["bytes"]) == path.stat().st_size
        assert row["sha256"] == MOD.sha256_file(path)
