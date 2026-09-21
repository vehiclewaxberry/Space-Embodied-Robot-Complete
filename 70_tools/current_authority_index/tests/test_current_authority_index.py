from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOL_ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location("current_index", TOOL_ROOT / "build_current_authority_index.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_is_deterministic_and_non_destructive() -> None:
    first = MODULE.build(REPO_ROOT)
    out = REPO_ROOT / "01_project" / "current"
    first_hashes = {path.name: MODULE.sha(path) for path in out.iterdir() if path.is_file()}
    second = MODULE.build(REPO_ROOT)
    second_hashes = {path.name: MODULE.sha(path) for path in out.iterdir() if path.is_file()}
    assert first == second
    assert first_hashes == second_hashes
    assert first["delete_executed"] is False
    assert first["move_or_archive_executed"] is False
    assert first["eligible_delete_candidate_count"] == 0


def test_required_outputs_and_navigation_guards() -> None:
    out = REPO_ROOT / "01_project" / "current"
    required = {
        "README_CURRENT.md",
        "PROJECT_CURRENT_AUTHORITY_V1.yaml",
        "CURRENT_GATE_MATRIX_V1.csv",
        "ACTIVE_WORK_REGISTER_V1.csv",
        "HOLD_AND_NEGATIVE_RESULTS_V1.csv",
        "CURRENT_RELEASE_POINTERS_V1.yaml",
        "SUPERSEDED_ASSET_REGISTER_V1.csv",
        "RETIREMENT_CANDIDATES_V1.csv",
        "DELETE_CANDIDATES_V1.csv",
        "REFERENCE_GRAPH_V1.json",
    }
    assert required == {path.name for path in out.iterdir() if path.is_file()}
    readme = (out / "README_CURRENT.md").read_text(encoding="utf-8")
    assert "NAVIGATION_ONLY" in readme
    assert "本轮未删除" in readme
    assert "Option A 已由明确执行块首行记录" in readme
    assert "token 未记录" not in readme

    with (out / "DELETE_CANDIDATES_V1.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == []


def test_every_authority_source_exists_and_hashes() -> None:
    for _, rel, *_ in MODULE.SOURCES:
        path = REPO_ROOT / rel
        assert path.is_file()
        assert len(MODULE.sha(path)) == 64


def test_strict_json_duplicate_is_visible_not_hidden() -> None:
    out = REPO_ROOT / "01_project" / "current" / "CURRENT_GATE_MATRIX_V1.csv"
    with out.open(encoding="utf-8", newline="") as handle:
        rows = {row["id"]: row for row in csv.DictReader(handle)}
    assert rows["odr60_preflight"]["strict_json"] == "HOLD"
    assert "DUPLICATE_JSON_KEY" in rows["odr60_preflight"]["parse_error"]


def test_boolean_rendering_never_treats_string_false_as_true() -> None:
    assert MODULE.render_strict_bool(False) == ("false", "PASS")
    assert MODULE.render_strict_bool(True) == ("true", "PASS")
    rendered, status = MODULE.render_strict_bool("false")
    assert rendered == ""
    assert status == "HOLD_NON_BOOLEAN:str"


def test_reference_graph_never_authorizes_delete_or_release() -> None:
    graph = json.loads((REPO_ROOT / "01_project/current/REFERENCE_GRAPH_V1.json").read_text(encoding="utf-8"))
    assert graph["authority"] == "NONE"
    assert graph["delete_executed"] is False
    assert graph["move_or_archive_executed"] is False


def test_new_r2_closure_sources_are_strict_navigation_only() -> None:
    out = REPO_ROOT / "01_project" / "current"
    with (out / "CURRENT_GATE_MATRIX_V1.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = {row["id"]: row for row in csv.DictReader(handle)}
    expected = {
        "odr60_option_a_execution_closure",
        "r2_dynamics_engineering",
        "r2_8dof_constrained_dynamics",
        "r2_control_engineering",
        "r2_dynamics_control_system",
    }
    assert expected <= rows.keys()
    assert len(MODULE.SOURCES) == 41
    assert len(rows) == 30
    for source_id in expected:
        assert rows[source_id]["strict_json"] == "PASS"
        assert rows[source_id]["next_stage_authorized"] == "false"
        assert rows[source_id]["next_stage_type_check"] == "PASS"
        assert rows[source_id]["release_credit"] == "false"
        assert rows[source_id]["release_credit_type_check"] == "PASS"
    ids = [item[0] for item in MODULE.SOURCES]
    assert len(ids) == len(set(ids))

    pointers = (out / "CURRENT_RELEASE_POINTERS_V1.yaml").read_text(
        encoding="utf-8"
    )
    for key in (
        "mechanical_odr60_execution_closure",
        "dynamics_r2_engineering",
        "dynamics_r2_constrained",
        "control_r2_engineering",
        "system_r2_dynamics_control_closure",
    ):
        assert f"{key}:" in pointers
