"""Regression tests for the ODR-60 top-level fail-closed aggregate."""
from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_builder():
    path = HERE / "build_odr60_collision_authority.py"
    spec = importlib.util.spec_from_file_location("odr60_collision_authority_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_checked_in_gate_and_manifest_are_deterministic_byte_identity() -> None:
    builder = load_builder()
    for name, expected in builder.output_map().items():
        assert (HERE / name).read_bytes() == expected


def test_top_level_gate_never_authorizes_full_collision_or_search() -> None:
    builder = load_builder()
    gate = json.loads((HERE / builder.GATE_NAME).read_text(encoding="utf-8"))
    assert gate["schema"] == "ODR60_OPTION_A_COLLISION_AUTHORITY_GATE_V1"
    assert gate["complete_hash_bound_acm"] is False
    assert gate["complete_system_collision_pass"] is False
    assert gate["pre_search_ready"] is False
    assert gate["path_search_executed"] is False
    assert gate["path_search_authorized"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False
    assert gate["system_registry"]["unassessed_fail_closed_pair_count"] == 11166
    assert "11166_NON_EXCEPTED_PAIRS_UNASSESSED" in gate["blockers"]


def test_proxy_pass_is_exactly_the_step_first_five_artifact_validation() -> None:
    builder = load_builder()
    gate = builder.build_gate()
    proxy = gate["base_link_proxy"]
    assert gate["proxy_pass"] is proxy["proxy_pass"]
    assert proxy["proxy_pass"] is all(proxy["checks"].values())
    if proxy["proxy_pass"]:
        assert proxy["status"] == "OPERATIONAL_PROXY_VERIFIED_PASS"
        assert all(proxy["present"].values())
    else:
        assert proxy["status"] != "OPERATIONAL_PROXY_VERIFIED_PASS"
        assert gate["complete_system_collision_pass"] is False


def test_missing_proxy_is_fail_closed_without_creating_test_artifacts() -> None:
    builder = load_builder()
    missing_dir = HERE / "__INTENTIONALLY_ABSENT_PROXY_TEST_DIRECTORY__"
    assert not missing_dir.exists()
    missing = builder.inspect_base_link_proxy(missing_dir)
    assert missing["proxy_pass"] is False
    assert missing["status"] == "MISSING_OPERATIONAL_PROXY"


def test_manifest_is_complete_sorted_hash_bound_and_excludes_itself() -> None:
    builder = load_builder()
    manifest_path = HERE / builder.MANIFEST_NAME
    rows = list(csv.DictReader(io.StringIO(manifest_path.read_text(encoding="utf-8"))))
    paths = [row["path"] for row in rows]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    assert builder.MANIFEST_NAME not in paths
    assert set(paths) == {
        path.relative_to(HERE).as_posix() for path in builder.collect_core_paths()
    }
    required_root = {
        builder.BUILDER_NAME,
        builder.GATE_NAME,
        builder.README_NAME,
        builder.TEST_NAME,
    }
    assert required_root.issubset(paths)
    assert any(path.startswith("base_link_proxy_v2/") for path in paths)
    assert any(path.startswith("system_registry/") for path in paths)
    for row in rows:
        path = HERE / row["path"]
        data = path.read_bytes()
        assert int(row["bytes"]) == len(data)
        assert row["sha256"] == builder.sha256_bytes(data)


def test_registry_structural_pass_does_not_become_collision_pass() -> None:
    builder = load_builder()
    registry = builder.inspect_system_registry()
    assert registry["structural_registry_pass"] is True
    assert registry["pair_count"] == 11175
    assert registry["excepted_pair_count"] == 9
    assert registry["unassessed_fail_closed_pair_count"] == 11166
    assert registry["complete_system_collision_pass"] is False
