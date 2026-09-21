"""Acceptance tests for the frozen P0-C campaign artifacts."""
from __future__ import annotations

import ast
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Callable

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import numpy as np
import yaml

E16_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = E16_ROOT.parents[1]
SRC = E16_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sync_model import DOWNSTREAM_FIELDS, N_A, canonical_rows_digest  # noqa: E402
from run_campaign import render_figures  # noqa: E402


RESULTS_PATH = E16_ROOT / "results" / "sync_capture_216.json"
GATE_PATH = E16_ROOT / "results" / "gate_check.json"
MANIFEST_PATH = E16_ROOT / "results" / "run_manifest.json"
CONFIG_PATH = E16_ROOT / "20_engineering" / "config" / "experiment_v1.yaml"

with RESULTS_PATH.open(encoding="utf-8") as f:
    RESULTS = json.load(f)
with GATE_PATH.open(encoding="utf-8") as f:
    GATE = json.load(f)
with MANIFEST_PATH.open(encoding="utf-8") as f:
    MANIFEST = json.load(f)
with CONFIG_PATH.open(encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

ROWS = RESULTS["rows"]
DYNAMIC = [row for row in ROWS if row["dynamics_status"] == "EVALUATED"]
UPSTREAM = [row for row in ROWS if row["dynamics_status"] == "NOT_RUN_DUE_TO_UPSTREAM"]

TESTS: list[tuple[str, Callable[[], None]]] = []


def test(name: str):
    def register(func: Callable[[], None]) -> Callable[[], None]:
        TESTS.append((name, func))
        return func
    return register


@test("T01 exact 216-case Cartesian grid and unique identifiers")
def _grid() -> None:
    assert len(ROWS) == 216
    assert len({row["case_id"] for row in ROWS}) == 216
    assert len({row["scenario_hash"] for row in ROWS}) == 216
    grid = Counter((row["grasp_point_id"], float(row["capture_phase_s"]),
                    float(row["closure_speed_mps"]), row["task_mode"],
                    float(row["alpha"])) for row in ROWS)
    assert len(grid) == 216 and set(grid.values()) == {1}
    assert Counter(float(row["alpha"]) for row in ROWS) == Counter({0.0: 72, 0.8: 72, 1.0: 72})


@test("T02 terminal accounting is 216=18 dynamic+198 upstream")
def _accounting() -> None:
    assert len(DYNAMIC) == 18
    assert len(UPSTREAM) == 198
    assert all(str(row["case_terminal_status"]).startswith("COMPLETE") for row in ROWS)
    assert Counter(row["case_terminal_status"] for row in ROWS) == Counter({
        "COMPLETE_DYNAMIC_EVALUATED": 18,
        "COMPLETE_UPSTREAM_REJECTED": 198,
    })


@test("T03 upstream rejection uses explicit N/A for every downstream quantity")
def _na_policy() -> None:
    assert all(row["classification"] == "GEOMETRY_INVALID" for row in UPSTREAM)
    assert all(row["binding_constraint"] == "IK_FAIL" for row in UPSTREAM)
    for row in UPSTREAM:
        for field in DOWNSTREAM_FIELDS:
            assert field in row, (row["case_id"], field)
            assert row[field] == N_A, (row["case_id"], field, row[field])
        assert row["actuator_limit_status"] == "NOT_RUN_DUE_TO_UPSTREAM"


@test("T04 twist-frame/sign/unit contract is exactly satisfied")
def _twist_contract() -> None:
    assert CONFIG["twist_contract"]["expression_frame"] == "I"
    assert CONFIG["twist_contract"]["ordering"] == ["vx", "vy", "vz", "wx", "wy", "wz"]
    for row in DYNAMIC:
        xi_g = np.asarray(json.loads(row["xi_G_I_json"]), float)
        closure = np.asarray(json.loads(row["xi_closure_I_json"]), float)
        desired = np.asarray(json.loads(row["xi_EE_des_I_json"]), float)
        assert np.max(np.abs(desired - float(row["alpha"]) * xi_g - closure)) < 1.0e-12
        assert abs(np.linalg.norm(closure[:3]) - float(row["closure_speed_mps"])) < 1.0e-12
        assert np.max(np.abs(closure[3:])) == 0.0


@test("T05 all rigid dynamics invariants and contact closures pass")
def _invariants() -> None:
    fields = (
        "terminal_twist_residual_inf", "terminal_momentum_residual_inf",
        "base_momentum_residual_inf", "contact_twist_residual_inf",
        "contact_P_residual_inf", "contact_H_residual_inf",
        "two_stage_P_residual_inf", "two_stage_H_residual_inf",
        "wrench_closure_inf", "energy_closure_J",
    )
    maxima = {field: max(abs(float(row[field])) for row in DYNAMIC) for field in fields}
    assert all(value <= 1.0e-9 for value in maxima.values()), maxima
    assert max(float(row["contact_position_error_m"]) for row in DYNAMIC) <= 1.0e-6
    assert all(float(row["dT_contact_J"]) >= -1.0e-9 for row in DYNAMIC)
    assert all(float(row["dT_lock_J"]) >= -1.0e-9 for row in DYNAMIC)


@test("T06 IK/collision/conditioning/joint geometry flags and actuator evidence are explicit")
def _limits() -> None:
    assert all(all(bool(row[name]) for name in (
        "ik_feasible", "collision_feasible", "condition_feasible",
        "joint_limit_feasible", "terminal_tracking_feasible")) for row in DYNAMIC)
    assert all(float(row["collision_margin_m"]) >= 0.02 for row in DYNAMIC)
    assert all(float(row["condition_number"]) <= 10000.0 for row in DYNAMIC)
    assert all(float(row["joint_limit_margin_rad"]) >= 0.05 for row in DYNAMIC)
    assert all(row["joint_velocity_limit_status"] == "UNKNOWN_NO_FROZEN_LIMIT" for row in DYNAMIC)
    assert all(row["joint_torque_limit_status"] ==
               "UNKNOWN_NOT_MODELED_IN_TERMINAL_KINEMATICS" for row in DYNAMIC)
    assert all(row["actuator_limit_status"] in {
        "PARTIAL_PASS_WHEEL_THRUSTER_JOINT_LIMITS_UNKNOWN", "FAIL_WHEEL_OR_THRUSTER"
    } for row in DYNAMIC)


@test("T07 frozen thresholds match the inherited source without widening")
def _thresholds() -> None:
    with (REPO_ROOT / "20_engineering" / "config" / "grasp_evaluator" / "hard_constraints_v1.yaml").open(encoding="utf-8") as f:
        inherited = yaml.safe_load(f)["constraints"]
    frozen = CONFIG["hard_constraints_frozen"]
    for key in ("collision_margin_min_m", "condition_number_max",
                "post_capture_rate_max_dps", "wheel_momentum_max_Nms",
                "flexible_energy_max_J", "joint_limit_margin_min_rad"):
        assert float(frozen[key]) == float(inherited[key]), key
    assert GATE["threshold_policy"]["status"] == "FROZEN_NO_WIDENING"


@test("T08 every dynamic case has full classification and no SAFE claim")
def _classification() -> None:
    assert Counter(row["classification"] for row in DYNAMIC) == Counter({"CORE_UNSAFE": 18})
    assert Counter(row["binding_constraint"] for row in DYNAMIC) == Counter({
        "POST_CAPTURE_RATE_EXCEED": 18})
    assert all(float(row["post_capture_omega_dps"]) > 2.0 for row in DYNAMIC)
    assert all(row["flex_status"] == "UNKNOWN_NOT_RUN" for row in ROWS)
    assert all(row["flex_value"] == "UNKNOWN" for row in ROWS)
    assert not any(bool(row["safe_claim_permitted"]) for row in ROWS)


@test("T09 deterministic double-run digest is self-consistent")
def _determinism() -> None:
    digest = canonical_rows_digest(ROWS)
    assert GATE["determinism"] == {
        "status": "PASS", "rows_sha256": digest, "independent_runs": 2}
    assert RESULTS["rows_sha256"] == digest
    assert MANIFEST["rows_sha256"] == digest
    assert MANIFEST["deterministic_rerun"] is True


@test("T10 alpha statistics cover six complete paired blocks")
def _statistics() -> None:
    expected = {
        "alpha_median_summary.csv": 27,
        "alpha_omnibus_effects.csv": 9,
        "alpha_pairwise_effects.csv": 18,
    }
    for filename, n_rows in expected.items():
        with (E16_ROOT / "tables" / filename).open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == n_rows, (filename, len(rows))
        assert all(int(row["n_blocks"]) == 6 for row in rows)
    median_rows = []
    with (E16_ROOT / "tables" / "alpha_median_summary.csv").open(encoding="utf-8-sig", newline="") as f:
        median_rows = list(csv.DictReader(f))
    jlin = {float(row["alpha"]): float(row["median"]) for row in median_rows
            if row["metric"] == "capture_impulse_linear_norm_Ns"}
    jang = {float(row["alpha"]): float(row["median"]) for row in median_rows
            if row["metric"] == "capture_impulse_angular_norm_Nms"}
    assert jlin[1.0] < jlin[0.8] < jlin[0.0]
    assert jang[1.0] < jang[0.8] < jang[0.0]


@test("T11 Pareto/ranking tie rule makes G2-Sync a real synchronized low-impact candidate")
def _ranking() -> None:
    assert len(DYNAMIC) == 18
    assert sorted(int(row["overall_rank"]) for row in DYNAMIC) == list(range(1, 19))
    assert all(row["pareto_layer"] != N_A for row in DYNAMIC)
    assert all(float(row["normalized_initial_impulse_objective"]) > 0.0 for row in DYNAMIC)
    with (E16_ROOT / "tables" / "strategy_comparison.csv").open(encoding="utf-8-sig", newline="") as f:
        strategy = {row["strategy"]: row for row in csv.DictReader(f)}
    assert set(strategy) == {"G0", "G1", "G2", "G2-Sync"}
    assert float(strategy["G2-Sync"]["alpha"]) > 0.0
    assert (float(strategy["G2-Sync"]["normalized_initial_impulse_objective"])
            < float(strategy["G2"]["normalized_initial_impulse_objective"]))
    top = sorted(DYNAMIC, key=lambda row: int(row["overall_rank"]))[0]
    assert top["case_id"] == strategy["G2-Sync"]["case_id"]
    assert GATE["ranking_protocol"] == CONFIG["ranking_protocol"]


@test("T12 Top-20 underfill is honest and contains only 18 dynamic candidates")
def _top20() -> None:
    with (E16_ROOT / "tables" / "top20_rigid_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        top = list(csv.DictReader(f))
    assert len(top) == 18
    assert all(row["dynamics_status"] == "EVALUATED" for row in top)
    assert GATE["top20_requested"] == 20 and GATE["top20_delivered"] == 18
    assert GATE["top20_underfill_reason"] == "ONLY_18_LINE_A_GEOMETRY_VALID_DYNAMIC_CASES"


@test("T13 no ANCF/flexible solver is imported or executed")
def _no_ancf() -> None:
    imported: set[str] = set()
    for source in (SRC / "sync_model.py", SRC / "run_campaign.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.lower() for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.lower())
    assert not any(any(token in name for token in ("ancf", "sim_07", "flexible"))
                   for name in imported), imported
    assert CONFIG["flex_policy"]["run_ancf"] is False


@test("T14 primary-source literature record has adopted/not-adopted boundaries")
def _literature() -> None:
    text = (E16_ROOT / "docs" / "literature_assumptions.md").read_text(encoding="utf-8")
    for token in ("https://arxiv.org/abs/2512.09213",
                  "https://doi.org/10.3389/frobt.2019.00014",
                  "本项目采用", "本项目不采用", "UNKNOWN"):
        assert token in text


@test("T15 evidence artifacts exist and figure export is byte-deterministic")
def _artifacts() -> None:
    for rel in MANIFEST["artifacts"]:
        path = E16_ROOT / rel
        if rel in {"tests/test_report.md", "tests/test_results.json"}:
            continue
        assert path.is_file(), rel
        assert path.stat().st_size > 0, rel
    for rel in ("figures/alpha_effects.png", "figures/rigid_pareto.png",
                "figures/terminal_accounting.png"):
        assert (E16_ROOT / rel).stat().st_size > 10_000, rel
    figure_paths = [E16_ROOT / "figures" / f"{stem}.{suffix}"
                    for stem in ("alpha_effects", "rigid_pareto", "terminal_accounting")
                    for suffix in ("png", "pdf")]
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in figure_paths}
    ranked = sorted(DYNAMIC, key=lambda row: int(row["overall_rank"]))
    render_figures(ROWS, ranked)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in figure_paths}
    assert after == before, {name: (before[name], after[name])
                             for name in before if before[name] != after[name]}
    for path in (item for item in figure_paths if item.suffix == ".pdf"):
        content = path.read_bytes()
        assert b"/CreationDate" not in content, path.name
        assert b"/ModDate" not in content, path.name
    assert MANIFEST["figure_export"] == {
        "pdf_creator": "P0-C deterministic scientific renderer",
        "pdf_producer": "P0-C deterministic scientific renderer",
        "pdf_creation_date": "OMITTED_FOR_BYTE_DETERMINISM",
        "pdf_modification_date": "OMITTED_FOR_BYTE_DETERMINISM",
    }
    for rel, expected in MANIFEST["artifact_sha256"].items():
        actual = hashlib.sha256((E16_ROOT / rel).read_bytes()).hexdigest()
        assert actual == expected, rel
    figure_source = (SRC / "run_campaign.py").read_text(encoding="utf-8")
    assert "Post-capture rate change vs alpha=0 [pico-deg/s]" in figure_source
    assert 'ax.axhline(2.0' in figure_source


def main() -> None:
    outcomes: list[dict[str, str]] = []
    failures = 0
    for name, func in TESTS:
        try:
            func()
            outcomes.append({"test": name, "status": "PASS", "detail": ""})
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001 - test harness must capture evidence
            failures += 1
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            outcomes.append({"test": name, "status": "FAIL", "detail": detail})
            print(f"FAIL {name}: {detail}")

    invariant_fields = (
        "terminal_twist_residual_inf", "terminal_momentum_residual_inf",
        "contact_twist_residual_inf", "contact_P_residual_inf",
        "contact_H_residual_inf", "two_stage_P_residual_inf",
        "two_stage_H_residual_inf", "wrench_closure_inf", "energy_closure_J",
    )
    maxima = {field: max(abs(float(row[field])) for row in DYNAMIC)
              for field in invariant_fields}
    report_lines = [
        "# P0-C 验收测试报告", "", "日期：2026-07-14", "",
        f"结果：**{len(TESTS) - failures}/{len(TESTS)} PASS**", "",
        "| 测试 | 状态 | 详情 |", "| --- | --- | --- |",
    ]
    report_lines.extend(
        f"| {item['test']} | {item['status']} | {item['detail'] or '-'} |"
        for item in outcomes)
    report_lines.extend(["", "## 数值闭合最大残差", "",
                         "| 字段 | 最大绝对值 |", "| --- | ---: |"])
    report_lines.extend(f"| `{field}` | {value:.6e} |"
                        for field, value in maxima.items())
    report_lines.extend([
        "", "## 可重复性", "",
        f"- 独立运行次数：{GATE['determinism']['independent_runs']}",
        f"- 行摘要：`{GATE['determinism']['rows_sha256']}`",
        f"- 门禁：`{GATE['overall']}`", "",
    ])
    (E16_ROOT / "tests" / "test_report.md").write_text(
        "\n".join(report_lines), encoding="utf-8", newline="\n")
    with (E16_ROOT / "tests" / "test_results.json").open("w", encoding="utf-8", newline="\n") as f:
        json.dump({"passed": len(TESTS) - failures, "failed": failures,
                   "total": len(TESTS), "outcomes": outcomes,
                   "max_residuals": maxima}, f, ensure_ascii=False, indent=2,
                  allow_nan=False)
        f.write("\n")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
