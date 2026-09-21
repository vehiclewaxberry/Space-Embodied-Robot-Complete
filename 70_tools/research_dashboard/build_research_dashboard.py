"""Build the deterministic P0 research evidence layer from frozen local inputs.

The three component directories are read-only inputs. Every generated artifact is
written under ``70_tools/research_dashboard`` or to the one approved v1 HTML path.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "70_tools" / "research_dashboard"
RESULTS = HERE / "results"
TABLES = HERE / "tables"
DOCS = HERE / "docs"
TEMPLATE = HERE / "templates" / "dashboard_v1.html"
HTML_OUT = ROOT / "40_evidence" / "artifacts" / "visualization" / "project_visualization_v1_research.html"

VERDICT = "REPEAT_CORE"
SYNC_DIGEST = "bd972b6908a821f0c4ade06e80b1cb066cdc13f46e9b6c50c2f23a1504eac0f0"
PRE_REORG04_V0_SHA256 = "1F66454100AFB0A66E31E042C52C6B2A570801B72217F8709A2B50CA225B3166"
V0_SHA256 = "83C67E63A90E23172C085577E2FB5EF01B2E31D0E812C9729D0A4BA281DE57C7"
CANONICAL_TEXT_SUFFIXES = {".csv", ".html", ".json", ".md"}

SOURCE_SPECS = (
    ("core_gate", "30_simulation/e15_core_coverage/results/core_gate_check.json", "P0-A gate", "one gate record"),
    ("core_cases", "30_simulation/e15_core_coverage/results/core_evidence_72cases.csv", "P0-A coverage", "one row per 72-case core grid point"),
    ("core_manifest", "30_simulation/e15_core_coverage/results/core_run_manifest.json", "P0-A reproducibility", "one run manifest"),
    ("ancf_gate", "30_simulation/e15_ancf_certification/results/gate_summary.json", "P0-B gate", "one certification summary"),
    ("ancf_history", "30_simulation/e15_ancf_certification/results/historical_classification.csv", "P0-B history", "one row per 7 historical flexible case"),
    ("ancf_low_amplitude", "30_simulation/e15_ancf_certification/results/low_amplitude_runs.csv", "P0-B diagnostics", "one row per diagnostic solver run"),
    ("ancf_cross_solver", "30_simulation/e15_ancf_certification/tables/cross_solver_differences.csv", "P0-B cross-solver", "one row per paired diagnostic condition"),
    ("ancf_discretization", "30_simulation/e15_ancf_certification/tables/discretization_trends.csv", "P0-B discretization", "one adjacent refinement comparison"),
    ("ancf_newmark", "30_simulation/e15_ancf_certification/tables/newmark_timestep_trend.csv", "P0-B time step", "one Newmark time step"),
    ("ancf_manifest", "30_simulation/e15_ancf_certification/results/run_manifest.json", "P0-B reproducibility", "one run manifest"),
    ("sync_gate", "30_simulation/e16_sync_capture/results/gate_check.json", "P0-C gate", "one campaign gate record"),
    ("sync_cases", "30_simulation/e16_sync_capture/results/sync_capture_216.csv", "P0-C campaign", "one row per 216-case synchronized grid point"),
    ("sync_alpha", "30_simulation/e16_sync_capture/tables/alpha_median_summary.csv", "P0-C alpha effects", "one metric-alpha median"),
    ("sync_strategy", "30_simulation/e16_sync_capture/tables/strategy_comparison.csv", "P0-C strategy comparison", "one frozen strategy representative"),
    ("sync_manifest", "30_simulation/e16_sync_capture/results/run_manifest.json", "P0-C reproducibility", "one run manifest"),
    ("viz_v0", "40_evidence/artifacts/visualization/project_visualization_v0.html", "accepted VIZ-Gate 0 dashboard", "one immutable offline artifact"),
    ("viz_freeze", "40_evidence/artifacts/visualization/viz_gate0_freeze_manifest_20260714.csv", "VIZ-Gate 0 freeze", "one frozen artifact"),
    ("viz_snapshot", "40_evidence/artifacts/visualization/tables/gate_artifact_protection_manifest.csv", "E1.5 evidence snapshot", "one row per protected evidence artifact"),
    ("viz_assets", "40_evidence/artifacts/visualization/tables/asset_audit.csv", "VIZ input assets", "one row per audited local asset"),
    ("viz_portability", "40_evidence/artifacts/visualization/VIZ_GATE0_PORTABILITY_VERIFICATION_20260715.md", "VIZ-Gate 0 portability", "one verification report"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fingerprint(path: Path, source_id: str) -> tuple[bytes, str]:
    """Return checkout-stable evidence bytes and their declared hash mode.

    Windows may materialize tracked text with either CRLF or LF. Evidence
    fingerprints therefore canonicalize text newlines, except for the accepted
    v0 HTML whose frozen gate contract is explicitly a raw-byte SHA-256.
    """
    data = path.read_bytes()
    if source_id != "viz_v0" and path.suffix.lower() in CANONICAL_TEXT_SUFFIXES:
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n"), "CANONICAL_LF_TEXT_BYTES"
    return data, "RAW_FILE_BYTES"


def read_json(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def read_csv(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str | None) -> float | None:
    if value is None or value.strip() in {"", "UNKNOWN", "N/A"}:
        return None
    return float(value)


def as_int(value: str | None) -> int | None:
    number = as_float(value)
    return None if number is None else int(number)


def as_bool(value: str | None) -> bool | None:
    if value is None or value.strip() == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"unrecognized boolean: {value}")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_dashboard_html(path: Path, text: str) -> None:
    """Match the repository's Windows checkout convention for the external HTML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\r\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def csv_value(value: Any) -> Any:
    if value is None:
        return "N/A_NOT_APPLICABLE"
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fields})


def source_inventory() -> list[dict[str, Any]]:
    inventory = []
    for source_id, relative, role, grain in SOURCE_SPECS:
        path = ROOT / relative
        fingerprint, fingerprint_mode = source_fingerprint(path, source_id)
        inventory.append(
            {
                "source_id": source_id,
                "path": relative.replace("\\", "/"),
                "role": role,
                "grain": grain,
                "sha256": hashlib.sha256(fingerprint).hexdigest(),
                "size_bytes": len(fingerprint),
                "fingerprint_mode": fingerprint_mode,
                "snapshot_date": "2026-07-15",
                "access": "read-only local evidence",
            }
        )
    return inventory


def core_unified_row(row: dict[str, str]) -> dict[str, Any]:
    applicable = as_bool(row["core_chain_applicable"]) is True
    return {
        "campaign_id": "P0-A-CORE-72",
        "campaign_discriminator": "CORE_COVERAGE",
        "campaign_grain": "3 points × 4 phases × 3 speeds × 2 task modes = 72",
        "case_id": row["case_id"],
        "grasp_point_id": row["grasp_point_id"],
        "capture_phase_s": as_float(row["t_c_s"]),
        "closure_speed_mps": as_float(row["v_app_mps"]),
        "task_mode": row["task_constraint_mode"],
        "alpha": None,
        "alpha_semantics": "N/A_NOT_IN_CORE_CAMPAIGN",
        "evaluation_path": "RIGID_CORE_NUMERIC" if applicable else "UPSTREAM_GEOMETRY_REJECTED",
        "dynamics_status": "EVALUATED" if applicable else "NOT_RUN_DUE_TO_UPSTREAM_IK",
        "rigid_classification": row["core_state"],
        "binding_constraint": row["primary_binding_cause"],
        "post_capture_rate_dps": as_float(row["post_capture_angular_velocity_dps"]),
        "post_capture_rate_limit_dps": as_float(row["post_capture_rate_max_dps"]),
        "initial_linear_impulse_Ns": as_float(row["capture_impulse_linear_norm_Ns"]),
        "initial_angular_impulse_Nms": as_float(row["capture_impulse_angular_norm_Nms"]),
        "flex_state": row["flex_status"] if applicable else "N/A_NOT_RUN_DUE_TO_UPSTREAM_IK",
        "flex_safety_eligible": as_bool(row["flex_safety_evaluation_eligible"]) if applicable else None,
        "evidence_semantics": row["evidence_status"],
        "safe_claim_permitted": False,
        "source_id": "core_cases",
    }


def sync_unified_row(row: dict[str, str]) -> dict[str, Any]:
    evaluated = row["dynamics_status"] == "EVALUATED"
    return {
        "campaign_id": "P0-C-SYNC-216",
        "campaign_discriminator": "SYNCHRONIZED_CAPTURE",
        "campaign_grain": "3 points × 4 phases × 3 speeds × 2 task modes × 3 alpha = 216",
        "case_id": row["case_id"],
        "grasp_point_id": row["grasp_point_id"],
        "capture_phase_s": as_float(row["capture_phase_s"]),
        "closure_speed_mps": as_float(row["closure_speed_mps"]),
        "task_mode": row["task_mode"],
        "alpha": as_float(row["alpha"]),
        "alpha_semantics": "EVALUATED_GRID_DIMENSION",
        "evaluation_path": "SYNCHRONIZED_RIGID_DYNAMIC" if evaluated else "UPSTREAM_GEOMETRY_REJECTED",
        "dynamics_status": row["dynamics_status"],
        "rigid_classification": row["classification"],
        "binding_constraint": row["binding_constraint"],
        "post_capture_rate_dps": as_float(row["post_capture_omega_dps"]),
        "post_capture_rate_limit_dps": 2.0 if evaluated else None,
        "initial_linear_impulse_Ns": as_float(row["capture_impulse_linear_norm_Ns"]),
        "initial_angular_impulse_Nms": as_float(row["capture_impulse_angular_norm_Nms"]),
        "flex_state": row["flex_status"] if evaluated else "N/A_NOT_RUN_DUE_TO_UPSTREAM_IK",
        "flex_safety_eligible": False if evaluated else None,
        "evidence_semantics": row["evidence_status"],
        "safe_claim_permitted": as_bool(row["safe_claim_permitted"]) or False,
        "source_id": "sync_cases",
    }


def dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    lx, ly = left["initial_linear_impulse_Ns"], left["initial_angular_impulse_Nms"]
    rx, ry = right["initial_linear_impulse_Ns"], right["initial_angular_impulse_Nms"]
    return lx <= rx and ly <= ry and (lx < rx or ly < ry)


def candidate_rows(sync_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in sync_rows:
        if row["dynamics_status"] != "EVALUATED":
            continue
        candidates.append(
            {
                "case_id": row["case_id"],
                "grasp_point_id": row["grasp_point_id"],
                "capture_phase_s": as_float(row["capture_phase_s"]),
                "closure_speed_mps": as_float(row["closure_speed_mps"]),
                "task_mode": row["task_mode"],
                "alpha": as_float(row["alpha"]),
                "initial_linear_impulse_Ns": as_float(row["capture_impulse_linear_norm_Ns"]),
                "initial_angular_impulse_Nms": as_float(row["capture_impulse_angular_norm_Nms"]),
                "post_capture_rate_dps": as_float(row["post_capture_omega_dps"]),
                "post_capture_rate_limit_dps": 2.0,
                "wheel_momentum_required_Nms": as_float(row["wheel_momentum_required_Nms"]),
                "propellant_required_g": as_float(row["propellant_required_g"]),
                "terminal_joint_speed_max_radps": as_float(row["terminal_joint_speed_max_radps"]),
                "terminal_base_rate_dps": as_float(row["terminal_base_rate_dps"]),
                "core_margin": as_float(row["core_margin"]),
                "classification": row["classification"],
                "binding_constraint": row["binding_constraint"],
                "flex_state": row["flex_status"],
                "safe_claim_permitted": as_bool(row["safe_claim_permitted"]) or False,
                "campaign_pareto_layer": as_int(row["pareto_layer"]),
                "campaign_rank": as_int(row["overall_rank"]),
                "normalized_initial_impulse_objective": as_float(row["normalized_initial_impulse_objective"]),
                "strict_low_impulse_pareto": False,
                "source_id": "sync_cases",
            }
        )
    for candidate in candidates:
        candidate["strict_low_impulse_pareto"] = not any(
            dominates(other, candidate) for other in candidates if other is not candidate
        )
    return sorted(candidates, key=lambda row: (row["campaign_rank"], row["case_id"]))


def compact_solver_data(
    ancf_gate: dict[str, Any],
    history: list[dict[str, str]],
    cross_solver: list[dict[str, str]],
    discretization: list[dict[str, str]],
    newmark: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "overall": ancf_gate["overall"],
        "required_runs": ancf_gate["low_amplitude"]["required_runs"],
        "required_completed_runs": ancf_gate["low_amplitude"]["required_completed_runs"],
        "max_ancf_modal_trajectory_relative_difference": ancf_gate["low_amplitude"]["max_ancf_modal_trajectory_relative_difference"],
        "cross_solver_max_relative_difference": ancf_gate["cross_solver_diagnostic"]["max_relative_difference"],
        "cross_solver_gate_limit": 0.05,
        "final_candidate_available": ancf_gate["final_candidate_cross_solver"]["available"],
        "historical": [
            {
                "case_id": row["case_id"],
                "state": row["state"],
                "radau": row["radau_specific_classification"],
                "bdf": row["bdf_specific_classification"],
                "safety_eligible": as_bool(row["safety_evaluation_eligible"]),
            }
            for row in history
        ],
        "cross_solver": [
            {
                "label": (
                    f"n={row['n_elements']} jump"
                    if row["impulse_mode"] == "velocity_jump"
                    else f"{float(row['pulse_duration_s']) * 1000:g} ms pulse"
                ),
                "relative_difference": as_float(row["max_relative_difference"]),
                "strict_lt_5pct": as_bool(row["strict_lt_5pct"]),
            }
            for row in cross_solver
        ],
        "mesh": [
            {
                "label": f"{row['coarse']}→{row['fine']} elements",
                "relative_change": as_float(row["relative_change"]),
            }
            for row in discretization
            if row["study_axis"] == "mesh"
        ],
        "pulse": [
            {
                "label": f"{float(row['coarse']) * 1000:g} ms→jump",
                "relative_change": as_float(row["relative_change"]),
            }
            for row in discretization
            if row["study_axis"] == "impulse_duration_to_jump"
        ],
        "newmark": [
            {
                "label": f"Δt={float(row['time_step_s']) * 1000:g} ms",
                "trajectory_relative_difference": as_float(row["trajectory_relative_difference"]),
            }
            for row in newmark
        ],
    }


def build_summary(
    core_gate: dict[str, Any], ancf_gate: dict[str, Any], sync_gate: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    strict_front = [row for row in candidates if row["strict_low_impulse_pareto"]]
    selected = strict_front[0] if len(strict_front) == 1 else candidates[0]
    return {
        "schema_version": "research-integration-summary-v1",
        "generation_mode": "DETERMINISTIC_LOCAL_EVIDENCE_NO_RUNTIME_TIMESTAMP",
        "final_verdict": VERDICT,
        "final_verdict_basis": [
            "P0-A has zero rigid-core-safe candidates under frozen thresholds.",
            "P0-C reduces initial impact but all 18 dynamic cases remain rigid-core unsafe.",
            "P0-B has no candidate-level cross-solver flexible certificate and all seven historical cases remain UNKNOWN.",
        ],
        "decision_date": "2026-07-15",
        "viz_gate_0": {
            "accepted": True,
            "v0_sha256": V0_SHA256,
            "pre_reorg04_v0_sha256": PRE_REORG04_V0_SHA256,
            "refreeze_reason": "root_namespace_path_refreeze_reorg04",
            "snapshot_hashes": "22/22",
            "freeze_hashes": "29/29",
            "asset_paths": "45/45",
            "portability_status": "CURRENT_PASS",
            "superseded_note": "The early ANCF checkout-portability note is superseded by e765194, 86d50d1, and clean-checkout verification 1cc3c2f.",
        },
        "p0_a": {
            "gate": core_gate["gate"],
            "rows": core_gate["row_count"],
            "state_counts": core_gate["state_counts"],
            "evidence_missing": core_gate["evidence_missing_count"],
            "safe_candidates": core_gate["safe_candidate_count"],
            "scientific_verdict": core_gate["scientific_verdict"],
            "source_id": "core_gate",
        },
        "p0_b": {
            "overall": ancf_gate["overall"],
            "historical_total": ancf_gate["historical"]["total"],
            "historical_unknown": ancf_gate["historical"]["unknown"],
            "silent_zero": ancf_gate["historical"]["silent_zero"],
            "final_candidate_available": ancf_gate["final_candidate_cross_solver"]["available"],
            "source_id": "ancf_gate",
        },
        "p0_c": {
            "overall": sync_gate["overall"],
            "rows": sync_gate["case_accounting"]["terminal_cases"],
            "dynamic": sync_gate["case_accounting"]["dynamic_evaluated_cases"],
            "upstream_rejected": sync_gate["case_accounting"]["upstream_rejected_cases"],
            "formal_safe": sync_gate["formal_safe_cases"],
            "rows_sha256": sync_gate["determinism"]["rows_sha256"],
            "strict_low_impulse_front_size": len(strict_front),
            "selected_low_impulse_case": strict_front[0]["case_id"] if len(strict_front) == 1 else None,
            "selected_alpha": selected["alpha"],
            "selected_linear_impulse_Ns": selected["initial_linear_impulse_Ns"],
            "selected_angular_impulse_Nms": selected["initial_angular_impulse_Nms"],
            "selected_post_capture_rate_dps": selected["post_capture_rate_dps"],
            "post_capture_rate_limit_dps": selected["post_capture_rate_limit_dps"],
            "source_id": "sync_gate",
        },
        "case_models": {
            "case_r": "Rigid-body main line: 18 synchronized dynamic cases; all CORE_UNSAFE because post-capture rate exceeds 2 deg/s.",
            "case_f": "Flexible extension: candidate-level ANCF evidence remains UNKNOWN/unavailable and is excluded from ranking and safety claims.",
        },
        "evidence_semantics": {
            "N/A": "The downstream calculation was not applicable or not run because an upstream gate failed; it is never encoded as numeric zero.",
            "UNKNOWN": "The required evidence was attempted or scoped but not certified; UNKNOWN is not SAFE and is excluded from ranking/training.",
            "EVIDENCE_MISSING": "A required applicable evidence field is absent; P0-A count is zero but this does not imply physical safety.",
        },
        "next_gate": {
            "required_action": "Repeat the core campaign until at least one rigid candidate satisfies every frozen core threshold, then run candidate-level Radau/BDF flexible certification with <5% cross-solver difference.",
            "authorization": {"E2": False, "G3": False, "HIL": False},
        },
    }


def build_report(summary: dict[str, Any], selected: dict[str, Any], alpha: dict[str, float]) -> str:
    return f"""# P0 研究集成裁决（2026-07-15）

## 唯一裁决

`{summary['final_verdict']}`

P0-A、P0-B、P0-C 已完成机器证据交叉核对，但尚无可进入后续阶段的安全候选。E2、G3、HIL 均未获授权。

## 独立 campaign，不混池

- P0-A 核心覆盖：72 行，粒度为 3 抓取点 × 4 相位 × 3 速度 × 2 任务模式；66 行为 `GEOMETRY_INVALID`，6 行为 `CORE_UNSAFE`，`EVIDENCE_MISSING=0`，SAFE=0。
- P0-C 同步捕获：216 行，粒度在 P0-A 维度上额外加入 3 个 alpha；18 行完成刚体动力学，198 行上游几何拒绝，SAFE=0。两类 campaign 仅通过 discriminator 统一浏览，不合并为同一统计总体。

## 关键科学结论

- 严格以初始线冲量和角冲量作双目标 Pareto 时，唯一非支配点为 `{selected['case_id']}`（alpha={selected['alpha']:.1f}）：{selected['initial_linear_impulse_Ns']:.9f} N·s、{selected['initial_angular_impulse_Nms']:.9f} N·m·s。
- 相比 alpha=0，中位初始线冲量下降 {abs(alpha['linear']):.3f}%，角冲量下降 {abs(alpha['angular']):.3f}%；但捕获后刚体角速度仍为 {selected['post_capture_rate_dps']:.9f} deg/s，高于冻结门槛 2.0 deg/s。同步策略改善“初始冲量”，没有消除最终刚体角动量约束。
- Case R（刚体主线）18/18 均被 `POST_CAPTURE_RATE_EXCEED` 约束；Case F（柔性扩展）保持 `UNKNOWN_NOT_RUN`，不得填零、不得进入安全排序。
- P0-B 的低振幅锚点完成 6/6，ANCF-modal 最大轨迹差 0.008191%；然而 10 ms 脉冲的 Radau/BDF 诊断最大差为 5.637%，且 7 个历史候选全部 UNKNOWN，最终候选交叉求解器证据不可用。因此总判定保持 `REPEAT_ANCF_CERTIFICATION`。

## 下一门禁

先重复核心研究，得到至少一个满足所有冻结刚体阈值的候选；之后才可对该候选运行 Radau/BDF 柔性认证并要求最大差异 <5%。这不是 E2、G3 或 HIL 的启动许可。

## VIZ-Gate 0 状态

v0 已按 REORG04 新根路径完成路径重冻结，当前 SHA-256 为 `{V0_SHA256}`，迁移前 SHA-256 `{PRE_REORG04_V0_SHA256}` 保留在审计字段中。ANCF 报告中的早期 clean-checkout 可移植性注记已被提交 `e765194`、`86d50d1` 及清洁检出验证 `1cc3c2f` 覆盖；当前状态为 22/22 snapshot、29/29 freeze、45/45 assets。

## 语义合同

- `N/A`：上游门禁失败使下游不适用/未运行；不是数值 0。
- `UNKNOWN`：证据未认证；不等于 SAFE，且不得进入排序或训练。
- `EVIDENCE_MISSING`：适用证据缺失；本轮为 0，但不代表物理安全。
"""


def build() -> str:
    """Generate all integration outputs and return the dashboard SHA-256."""
    core_gate = read_json("30_simulation/e15_core_coverage/results/core_gate_check.json")
    ancf_gate = read_json("30_simulation/e15_ancf_certification/results/gate_summary.json")
    sync_gate = read_json("30_simulation/e16_sync_capture/results/gate_check.json")
    core_rows = read_csv("30_simulation/e15_core_coverage/results/core_evidence_72cases.csv")
    sync_rows = read_csv("30_simulation/e16_sync_capture/results/sync_capture_216.csv")
    history = read_csv("30_simulation/e15_ancf_certification/results/historical_classification.csv")
    cross_solver = read_csv("30_simulation/e15_ancf_certification/tables/cross_solver_differences.csv")
    discretization = read_csv("30_simulation/e15_ancf_certification/tables/discretization_trends.csv")
    newmark = read_csv("30_simulation/e15_ancf_certification/tables/newmark_timestep_trend.csv")
    alpha_rows = read_csv("30_simulation/e16_sync_capture/tables/alpha_median_summary.csv")
    strategies_raw = read_csv("30_simulation/e16_sync_capture/tables/strategy_comparison.csv")

    unified = [core_unified_row(row) for row in core_rows] + [sync_unified_row(row) for row in sync_rows]
    candidates = candidate_rows(sync_rows)
    selected = next(row for row in candidates if row["strict_low_impulse_pareto"])
    alpha_effect = {
        "linear": next(
            as_float(row["median_change_vs_alpha0_pct"])
            for row in alpha_rows
            if row["metric"] == "capture_impulse_linear_norm_Ns" and row["alpha"] == "1.0"
        ),
        "angular": next(
            as_float(row["median_change_vs_alpha0_pct"])
            for row in alpha_rows
            if row["metric"] == "capture_impulse_angular_norm_Nms" and row["alpha"] == "1.0"
        ),
    }
    solver = compact_solver_data(ancf_gate, history, cross_solver, discretization, newmark)
    summary = build_summary(core_gate, ancf_gate, sync_gate, candidates)
    sources = source_inventory()
    strategies = [
        {
            "strategy": row["strategy"],
            "case_id": row["case_id"],
            "alpha": as_float(row["alpha"]),
            "initial_linear_impulse_Ns": as_float(row["capture_impulse_linear_norm_Ns"]),
            "initial_angular_impulse_Nms": as_float(row["capture_impulse_angular_norm_Nms"]),
            "post_capture_rate_dps": as_float(row["post_capture_omega_dps"]),
            "classification": row["classification"],
            "flex_state": row["flex_status"],
            "safe_claim_permitted": as_bool(row["safe_claim_permitted"]) or False,
        }
        for row in strategies_raw
    ]

    unified_fields = list(unified[0].keys())
    pareto_fields = list(candidates[0].keys())
    write_csv(TABLES / "unified_campaign_map.csv", unified, unified_fields)
    write_csv(TABLES / "sync_low_impulse_pareto.csv", candidates, pareto_fields)
    solver_rows = []
    solver_sources = {
        "cross_solver": "ancf_cross_solver",
        "mesh": "ancf_discretization",
        "pulse": "ancf_discretization",
        "newmark": "ancf_newmark",
    }
    for family, value_key in (("cross_solver", "relative_difference"), ("mesh", "relative_change"), ("pulse", "relative_change"), ("newmark", "trajectory_relative_difference")):
        for row in solver[family]:
            solver_rows.append(
                {
                    "diagnostic_family": family,
                    "label": row["label"],
                    "relative_difference": row[value_key],
                    "gate_limit": 0.05 if family == "cross_solver" else None,
                    "source_id": solver_sources[family],
                }
            )
    write_csv(TABLES / "solver_diagnostics.csv", solver_rows, list(solver_rows[0].keys()))
    write_json(RESULTS / "input_source_inventory.json", {"schema_version": "research-source-inventory-v1", "sources": sources})
    write_json(RESULTS / "research_integration_summary.json", summary)
    write_text(DOCS / "RESEARCH_INTEGRATION_REPORT_ZH.md", build_report(summary, selected, alpha_effect))

    compact_rows = [
        {
            "campaign_id": row["campaign_id"],
            "case_id": row["case_id"],
            "point": row["grasp_point_id"],
            "phase_s": row["capture_phase_s"],
            "speed_mps": row["closure_speed_mps"],
            "task_mode": row["task_mode"],
            "alpha": row["alpha"],
            "dynamics_status": row["dynamics_status"],
            "classification": row["rigid_classification"],
            "binding": row["binding_constraint"],
            "rate_dps": row["post_capture_rate_dps"],
            "flex_state": row["flex_state"],
        }
        for row in unified
    ]
    dashboard_data = {
        "summary": summary,
        "campaign_rows": compact_rows,
        "candidates": candidates,
        "strategies": strategies,
        "alpha_effect": alpha_effect,
        "solver": solver,
        "sources": sources,
    }
    payload = json.dumps(dashboard_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__RESEARCH_DATA__", payload)
    write_dashboard_html(HTML_OUT, html)

    generated = (
        RESULTS / "input_source_inventory.json",
        RESULTS / "research_integration_summary.json",
        TABLES / "unified_campaign_map.csv",
        TABLES / "sync_low_impulse_pareto.csv",
        TABLES / "solver_diagnostics.csv",
        DOCS / "RESEARCH_INTEGRATION_REPORT_ZH.md",
        HTML_OUT,
    )
    manifest = {
        "schema_version": "research-integration-run-manifest-v1",
        "generation_mode": "DETERMINISTIC_LOCAL_EVIDENCE_NO_RUNTIME_TIMESTAMP",
        "verdict_source": "results/research_integration_summary.json",
        "source_inventory": "results/input_source_inventory.json",
        "artifacts": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in generated
        },
    }
    write_json(RESULTS / "run_manifest.json", manifest)
    return sha256(HTML_OUT)


if __name__ == "__main__":
    print(build())
