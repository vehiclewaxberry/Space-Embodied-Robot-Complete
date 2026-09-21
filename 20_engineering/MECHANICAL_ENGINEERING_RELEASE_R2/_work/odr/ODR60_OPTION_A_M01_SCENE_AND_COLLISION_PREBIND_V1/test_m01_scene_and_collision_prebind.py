from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import yaml


HERE = Path(__file__).resolve().parent
REPO = next(parent for parent in HERE.parents if (parent / "PROJECT_MAP.md").is_file())


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "m01_scene_collision_prebind_builder",
        HERE / "build_m01_scene_and_collision_prebind.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return load_builder()


@pytest.fixture(scope="module")
def scene():
    return yaml.safe_load((HERE / "M01_SCENE_DECISION_INTAKE_V1.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows():
    with (HERE / "M01_OPERATIONAL_ASSET_READINESS_V1.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def gate():
    return json.loads((HERE / "M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json").read_text(encoding="utf-8"))


def test_builder_reproduces_current_outputs(builder):
    builder.check_outputs(REPO)


def test_option_a_mount_and_frame_ledger_consumed(scene):
    truth = scene["consumed_current_truth"]
    assert truth["option_a_selected"] is True
    assert truth["mount_payload_sha256"] == "E20544EF880D1792EB3B616A4B74CBD635F130FC9AB5846C6A09E12EA6187B7D"
    assert truth["frame_relationships_bound"] == truth["frame_relationships_required"] == 10


def test_all_v2_stages_and_fields_are_explicit(scene):
    expected = {
        "PRE_RELEASE_CONSTANT_SCENE": [
            "gripper_joint1_m", "gripper_joint2_m", "solar_state", "solar_hdrm_state",
            "solar_latch_state", "arm_hdrm_state", "target_present", "target_attached",
            "active_object_universe_sha256", "active_pair_universe_sha256",
        ],
        "RELEASE_EVENT_SCENE": [
            "event_id", "event_time_or_ordering", "pre_scene_sha256", "post_scene_sha256",
            "arm_hdrm_state_t0_minus", "arm_hdrm_state_t0_plus", "release_outcome",
            "released_constraint_ids", "retained_constraint_ids", "failure_disposition",
        ],
        "POST_RELEASE_CONSTANT_SCENE": [
            "gripper_joint1_m", "gripper_joint2_m", "solar_state", "solar_hdrm_state",
            "solar_latch_state", "arm_hdrm_state", "target_present", "target_attached",
            "active_object_universe_sha256", "active_pair_universe_sha256",
        ],
    }
    assert scene["stage_order"] == list(expected)
    by_id = {stage["stage_id"]: stage for stage in scene["stages"]}
    assert set(by_id) == set(expected)
    for stage_id, fields in expected.items():
        assert list(by_id[stage_id]["values"]) == fields


def test_authoritative_stage_values_all_remain_null(scene):
    values = [value for stage in scene["stages"] for value in stage["values"].values()]
    assert len(values) == 30
    assert all(value is None for value in values)
    accounting = scene["authoritative_instance_accounting"]
    assert accounting["stage_instances_bound"] == 0
    assert accounting["stage_instances_required"] == 3
    assert accounting["legacy_required_values_bound"] == 0
    assert accounting["legacy_required_values_required"] == 9


def test_candidate_suggestions_are_quarantined(scene):
    candidate = scene["candidate_suggestions_not_authority"]
    assert candidate["authority"] == "NONE__ENGINEERING_HYPOTHESES_ONLY"
    assert candidate["may_fill_authoritative_stage_values"] is False
    assert "COPYING_THIS_BLOCK_INTO_STAGES_IS_FORBIDDEN" in candidate["promotion_rule"]
    assert all("candidate" not in stage for stage in scene["stages"])


def test_asset_columns_are_complete(rows, builder):
    assert rows
    assert list(rows[0]) == builder.ASSET_FIELDS
    assert all(set(row) == set(builder.ASSET_FIELDS) for row in rows)


def test_asset_row_and_category_counts(rows):
    assert len(rows) == 167
    expected = {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6, "K": 10, "MISSING": 7}
    actual = {key: sum(row["category"] == key for row in rows) for key in expected}
    assert actual == expected
    assert sum(row["row_class"] == "ACTIVE_OBJECT" for row in rows) == 150
    assert sum(row["row_class"] == "CONDITIONAL_VIRTUAL_KEEPOUT_CANDIDATE" for row in rows) == 10
    assert sum(row["row_class"] == "KNOWN_MISSING_OBJECT_OR_AUTHORITY_CATEGORY" for row in rows) == 7


def test_asset_ids_unique_and_current_activity_partition(rows):
    assert len({row["id"] for row in rows}) == 167
    assert sum(row["active_in_current_pair_universe"] == "true" for row in rows) == 150
    assert all(row["active_in_current_pair_universe"] == "false" for row in rows if row["category"] in {"K", "MISSING"})


def test_only_base_link_is_asset_level_operational(rows):
    operational = [row for row in rows if row["operational_authority"] == "true"]
    closed = [row for row in rows if row["closed"] == "true"]
    assert [row["id"] for row in operational] == ["A::base_link"]
    assert [row["id"] for row in closed] == ["A::base_link"]
    assert "SYSTEM_RUNTIME_POSE_AND_PAIR_HOLD" in operational[0]["readiness"]


def test_missing_categories_use_explicit_nulls(rows):
    missing = [row for row in rows if row["category"] == "MISSING"]
    for row in missing:
        for field in ("path", "hash", "bytes", "units", "frame", "state_selector"):
            assert row[field] == "null"
        assert row["hash_algorithm"] == "SHA256"
        assert row["closed"] == row["operational_authority"] == "false"


def test_units_are_never_silently_zero_filled(rows):
    assert all(row["units"] not in {"", "0", "0.0"} for row in rows)
    assert any(row["units"] == "null" for row in rows)
    assert all(
        "ASSET_UNITS" in row["representation_debit"]
        for row in rows
        if row["row_class"] == "ACTIVE_OBJECT" and row["units"] == "null"
    )


def test_non_null_asset_pins_match_files(rows):
    for row in rows:
        if row["path"] == "null":
            continue
        path = REPO / Path(row["path"])
        payload = path.read_bytes()
        assert len(payload) == int(row["bytes"])
        assert row["hash_algorithm"] == "SHA256"
        assert hashlib.sha256(payload).hexdigest().upper() == row["hash"]


def test_query_edge_and_search_stay_false(scene, gate):
    state = scene["fail_closed_execution_state"]
    assert state["collision_geometry_loaded"] is False
    assert state["pair_evaluation_authorized"] is False
    assert state["pair_queries_executed"] == 0
    assert state["edge_evaluation_authorized"] is False
    assert state["edges_certified"] == 0
    assert state["path_search_authorized"] is False
    assert state["path_search_executed"] is False
    assert gate["system_execution_state"]["system_pair_queries_executed"] == 0
    assert gate["next_stage_authorized"] is gate["release_credit"] is False


def test_gate_is_18_of_18_structural_pass_only(gate):
    assert gate["checks_passed"] == gate["checks_total"] == 18
    assert all(gate["checks"].values())
    assert gate["prebind_package_complete"] is True
    assert "ZERO_OF_THREE_STAGE_INSTANCES" in gate["verdict"]
    assert "11166_PAIR_QUERY_AND_PATH_SEARCH_HOLD" in gate["verdict"]
    assert gate["system_execution_state"]["complete_system_operational_collision_asset_set_bound"] is False


def test_local_artifact_pins_match(gate):
    for item in gate["local_artifact_pins"].values():
        path = HERE / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == item["sha256"]


def test_manifest_is_self_excluded_and_fresh():
    manifest_path = HERE / "M01_SCENE_AND_COLLISION_PREBIND_SHA256_V1.csv"
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        entries = list(csv.DictReader(handle))
    names = {row["path"] for row in entries}
    assert manifest_path.name not in names
    required = {
        "README.md",
        "build_m01_scene_and_collision_prebind.py",
        "test_m01_scene_and_collision_prebind.py",
        "M01_SCENE_DECISION_INTAKE_V1.yaml",
        "M01_OPERATIONAL_ASSET_READINESS_V1.csv",
        "M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json",
    }
    assert required <= names
    for row in entries:
        path = HERE / row["path"]
        payload = path.read_bytes()
        assert len(payload) == int(row["bytes"])
        assert hashlib.sha256(payload).hexdigest().upper() == row["sha256"]


def test_no_parent_file_is_in_package_manifest():
    with (HERE / "M01_SCENE_AND_COLLISION_PREBIND_SHA256_V1.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        names = {row["path"] for row in csv.DictReader(handle)}
    assert all(".." not in Path(name).parts for name in names)
