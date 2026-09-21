from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RAW_BASE_SHA = "22641C079014FE968702393F61E7F7F1A8F80C6C1DF45A61E31545F6EAFF3B65"


def load_builder():
    path = HERE / "build_system_collision_registry.py"
    spec = importlib.util.spec_from_file_location("system_registry_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_outputs():
    registry = json.loads((HERE / "M01_SYSTEM_COLLISION_REGISTRY_V1.json").read_text(encoding="utf-8"))
    gate = json.loads((HERE / "M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json").read_text(encoding="utf-8"))
    pairs = list(csv.DictReader((HERE / "M01_PAIR_COVERAGE_V1.csv").open(encoding="utf-8", newline="")))
    return registry, gate, pairs


def test_deterministic_payloads_match_live_sources_and_outputs():
    builder = load_builder()
    repo = builder.find_repo()
    expected = builder.output_map(repo)
    for name, payload in expected.items():
        assert (HERE / name).read_bytes() == payload


def test_object_and_pair_universe_is_complete_and_unique():
    registry, gate, pairs = load_outputs()
    objects = registry["objects"]
    ids = [row["object_id"] for row in objects]
    assert len(ids) == len(set(ids)) == 150
    assert gate["object_counts"] == {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6}
    assert len(pairs) == 11175
    assert [int(row["pair_index"]) for row in pairs] == list(range(1, 11176))
    pair_keys = [tuple(sorted((row["object_a"], row["object_b"]))) for row in pairs]
    assert len(pair_keys) == len(set(pair_keys))


def test_only_nine_adjacent_pairs_are_excepted_and_everything_else_aborts_closed():
    registry, gate, pairs = load_outputs()
    excepted = [row for row in pairs if row["status"] == "EXCEPTED"]
    unassessed = [row for row in pairs if row["status"] == "UNASSESSED_FAIL_CLOSED"]
    expected = {
        tuple(rule["canonical_pair"])
        for rule in registry["active_pair_exceptions"]
    }
    actual = {
        tuple(sorted((row["object_a"], row["object_b"])))
        for row in excepted
    }
    assert len(expected) == len(actual) == len(excepted) == 9
    assert actual == expected
    assert len(unassessed) == 11166
    assert all(row["policy"] == "FORBID" for row in unassessed)
    assert gate["active_non_adjacent_pair_exceptions"] == 0
    assert registry["pair_policy"]["unknown"] == "ABORT"
    assert registry["pair_policy"]["wildcard_or_manual_exception"] == "FORBIDDEN"


def test_legacy_wide_exemptions_and_raw_base_mesh_are_not_consumed():
    registry, gate, _ = load_outputs()
    legacy = registry["legacy_behavior_rejected"]
    assert legacy["segment_wide_group_count"] == 8
    assert legacy["segment_part_membership_count"] == 91
    assert legacy["fixed_route_c_part_own_host_skip"]["disposition"].startswith("NOT_IMPORTED")
    object_text = json.dumps(registry["objects"], sort_keys=True)
    assert RAW_BASE_SHA not in object_text
    assert gate["raw_urdf_base_link_mesh_consumed_by_objects"] is False
    assert gate["fixed_own_host_object_skip_inherited"] is False


def test_no_authorization_or_search_claim_is_created():
    registry, gate, _ = load_outputs()
    assert registry["gate_semantics"]["structural_registry_complete"] is True
    assert registry["gate_semantics"]["complete_system_collision_pass"] is False
    assert registry["gate_semantics"]["path_search_legal"] is False
    assert gate["path_search_executed"] is False
    assert gate["pre_search_ready"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False

