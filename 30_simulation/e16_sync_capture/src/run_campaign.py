"""Run, analyse, and render the frozen P0-C 216-case campaign."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Iterable

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sync_model import (  # noqa: E402
    E16_ROOT,
    N_A,
    canonical_rows_digest,
    load_config,
    run_campaign,
)


RESULTS = E16_ROOT / "results"
TABLES = E16_ROOT / "tables"
FIGURES = E16_ROOT / "figures"
DOCS = E16_ROOT / "docs"

PARETO_METRICS = (
    "capture_impulse_linear_norm_Ns",
    "capture_impulse_angular_norm_Nms",
    "post_capture_omega_dps",
    "base_attitude_change_deg",
    "terminal_base_rate_dps",
    "wheel_momentum_required_Nms",
)

STAT_METRICS = {
    "capture_impulse_linear_norm_Ns": "Initial linear impulse [N s]",
    "capture_impulse_angular_norm_Nms": "Initial angular impulse [N m s]",
    "capture_impulse_6d_norm": "Initial 6D impulse norm [mixed units]",
    "relative_twist_pre_norm": "Pre-contact relative twist norm [mixed units]",
    "terminal_joint_speed_max_radps": "Terminal maximum joint speed [rad/s]",
    "terminal_base_rate_dps": "Terminal base rate [deg/s]",
    "post_capture_omega_dps": "Post-capture rigid rate [deg/s]",
    "wheel_momentum_required_Nms": "Wheel momentum demand [N m s]",
    "propellant_required_g": "Equivalent cold-gas propellant [g]",
}

ALPHA_ORDER = (0.0, 0.8, 1.0)
ALPHA_COLOURS = {0.0: "#0072B2", 0.8: "#E69F00", 1.0: "#009E73"}
PDF_METADATA = {
    "Creator": "P0-C deterministic scientific renderer",
    "Producer": "P0-C deterministic scientific renderer",
    "CreationDate": None,
    "ModDate": None,
}


def _mkdirs() -> None:
    for directory in (RESULTS, TABLES, FIGURES, DOCS):
        directory.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in row:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    names = _fieldnames(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=names, extrasaction="raise",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _save_figure(fig: plt.Figure, stem: str) -> None:
    """Export byte-stable PNG/PDF pairs without wall-clock PDF metadata."""
    fig.savefig(FIGURES / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.pdf", dpi=300, bbox_inches="tight",
                metadata=PDF_METADATA)


def _dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    av = np.asarray([float(a[name]) for name in PARETO_METRICS])
    bv = np.asarray([float(b[name]) for name in PARETO_METRICS])
    tol = 1.0e-12
    return bool(np.all(av <= bv + tol) and np.any(av < bv - tol))


def assign_pareto_and_rank(rows: list[dict[str, Any]],
                           cfg: dict[str, Any]) -> list[dict[str, Any]]:
    dynamic = [row for row in rows if row["dynamics_status"] == "EVALUATED"]
    remaining = sorted(dynamic, key=lambda row: row["case_id"])
    layer = 1
    while remaining:
        front = [candidate for candidate in remaining
                 if not any(_dominates(other, candidate)
                            for other in remaining if other is not candidate)]
        if not front:
            raise RuntimeError("Pareto decomposition stalled")
        for row in front:
            row["pareto_layer"] = layer
        front_ids = {id(row) for row in front}
        remaining = [row for row in remaining if id(row) not in front_ids]
        layer += 1

    g0_reference = [row for row in dynamic
                    if (row["grasp_point_id"] == "P1"
                        and float(row["capture_phase_s"]) == 0.0
                        and float(row["closure_speed_mps"]) == 0.01
                        and row["task_mode"] == "pose_6d"
                        and float(row["alpha"]) == 0.0)]
    if len(g0_reference) != 1:
        raise RuntimeError("frozen G0 normalization reference is not unique")
    j_linear_g0 = float(g0_reference[0]["capture_impulse_linear_norm_Ns"])
    j_angular_g0 = float(g0_reference[0]["capture_impulse_angular_norm_Nms"])
    if min(j_linear_g0, j_angular_g0) <= 0.0:
        raise RuntimeError("G0 impulse normalization scale must be positive")
    for row in dynamic:
        row["normalized_initial_impulse_objective"] = float(math.sqrt(0.5 * (
            (float(row["capture_impulse_linear_norm_Ns"]) / j_linear_g0) ** 2
            + (float(row["capture_impulse_angular_norm_Nms"]) / j_angular_g0) ** 2
        )))

    tolerance = float(cfg["ranking_protocol"]["core_margin_tie_tolerance"])
    for pareto_layer in sorted({int(row["pareto_layer"]) for row in dynamic}):
        layer_rows = [row for row in dynamic if int(row["pareto_layer"]) == pareto_layer]
        maximum_margin = max(float(row["core_margin"]) for row in layer_rows)
        for row in layer_rows:
            difference = maximum_margin - float(row["core_margin"])
            row["core_margin_tie_group"] = (
                0 if difference <= tolerance else int(math.ceil(difference / tolerance)))

    ranked = sorted(dynamic, key=lambda row: (
        int(row["pareto_layer"]),
        int(row["core_margin_tie_group"]),
        float(row["normalized_initial_impulse_objective"]),
        float(row["terminal_joint_speed_max_radps"]),
        float(row["terminal_base_rate_dps"]),
        row["case_id"],
    ))
    rank_by_case = {row["case_id"]: rank for rank, row in enumerate(ranked, 1)}
    top_ids = {row["case_id"] for row in ranked[:20]}
    for row in rows:
        if row["dynamics_status"] == "EVALUATED":
            row["overall_rank"] = rank_by_case[row["case_id"]]
            row["top20_included"] = row["case_id"] in top_ids
        else:
            row["pareto_layer"] = N_A
            row["core_margin_tie_group"] = N_A
            row["normalized_initial_impulse_objective"] = N_A
            row["overall_rank"] = N_A
            row["top20_included"] = False
    return ranked


def _paired_frame(dynamic: list[dict[str, Any]], metric: str) -> pd.DataFrame:
    frame = pd.DataFrame(dynamic)
    frame["block"] = (frame["grasp_point_id"].astype(str) + "|"
                      + frame["capture_phase_s"].astype(str) + "|"
                      + frame["closure_speed_mps"].astype(str) + "|"
                      + frame["task_mode"].astype(str))
    pivot = frame.pivot(index="block", columns="alpha", values=metric)
    return pivot.reindex(columns=list(ALPHA_ORDER)).dropna()


def _rank_biserial_improvement(reference: np.ndarray,
                                comparison: np.ndarray) -> float:
    improvement = np.asarray(reference, float) - np.asarray(comparison, float)
    nonzero = improvement[np.abs(improvement) > 1.0e-15]
    if len(nonzero) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(nonzero), method="average")
    r_plus = float(np.sum(ranks[nonzero > 0.0]))
    r_minus = float(np.sum(ranks[nonzero < 0.0]))
    return (r_plus - r_minus) / (r_plus + r_minus)


def _holm(p_values: Iterable[float]) -> list[float]:
    p = np.asarray(list(p_values), float)
    m = len(p)
    order = np.argsort(p)
    adjusted = np.empty(m, float)
    running = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (m - rank) * float(p[index]))
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted.tolist()


def statistics_tables(dynamic: list[dict[str, Any]]) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    omnibus: list[dict[str, Any]] = []
    pairwise: list[dict[str, Any]] = []
    complete_blocks: set[str] | None = None
    for metric, label in STAT_METRICS.items():
        pivot = _paired_frame(dynamic, metric)
        blocks = set(pivot.index.astype(str))
        complete_blocks = blocks if complete_blocks is None else complete_blocks & blocks
        arrays = [pivot[alpha].to_numpy(float) for alpha in ALPHA_ORDER]
        n = len(pivot)
        medians = [float(np.median(values)) for values in arrays]
        ref = medians[0]
        for alpha, median in zip(ALPHA_ORDER, medians):
            summaries.append({
                "metric": metric,
                "label": label,
                "alpha": alpha,
                "n_blocks": n,
                "median": median,
                "median_change_vs_alpha0_pct": (
                    100.0 * (median - ref) / abs(ref) if abs(ref) > 1.0e-15
                    else (0.0 if abs(median) <= 1.0e-15 else N_A)
                ),
            })
        with np.errstate(all="ignore"):
            try:
                friedman = stats.friedmanchisquare(*arrays)
                statistic = float(friedman.statistic)
                p_value = float(friedman.pvalue)
            except ValueError:
                statistic, p_value = 0.0, 1.0
        if not np.isfinite(statistic) or not np.isfinite(p_value):
            statistic, p_value = 0.0, 1.0
        kendall_w = statistic / (n * (len(ALPHA_ORDER) - 1)) if n else 0.0
        alpha1_difference = arrays[2] - arrays[0]
        denominator = np.maximum(np.abs(arrays[0]), 1.0e-15)
        max_abs_alpha1_change = float(np.max(np.abs(alpha1_difference)))
        max_relative_alpha1_change = float(np.max(np.abs(alpha1_difference) / denominator))
        shapiro_08 = stats.shapiro(arrays[1] - arrays[0]).pvalue if n >= 3 else float("nan")
        shapiro_10 = stats.shapiro(arrays[2] - arrays[0]).pvalue if n >= 3 else float("nan")
        omnibus.append({
            "metric": metric,
            "label": label,
            "n_blocks": n,
            "friedman_chi2": statistic,
            "friedman_p": p_value,
            "kendall_W": float(kendall_w),
            "max_abs_change_alpha1_minus_alpha0": max_abs_alpha1_change,
            "max_relative_change_alpha1_vs_alpha0": max_relative_alpha1_change,
            "practical_change_flag": ("NUMERICAL_ONLY_RELATIVE_LT_1E-9"
                                      if max_relative_alpha1_change < 1.0e-9 else
                                      "RESOLVED_CHANGE"),
            "shapiro_p_diff_alpha0p8_minus_0": (float(shapiro_08)
                                                  if np.isfinite(shapiro_08) else N_A),
            "shapiro_p_diff_alpha1_minus_0": (float(shapiro_10)
                                                if np.isfinite(shapiro_10) else N_A),
            "interpretation": "descriptive_for_deterministic_design_points",
        })

        metric_pairs: list[dict[str, Any]] = []
        for comparison, comp_values in ((0.8, arrays[1]), (1.0, arrays[2])):
            diff = comp_values - arrays[0]
            if np.all(np.abs(diff) <= 1.0e-15):
                wilcoxon_stat, raw_p = 0.0, 1.0
            else:
                test = stats.wilcoxon(comp_values, arrays[0], alternative="two-sided",
                                      zero_method="wilcox", method="auto")
                wilcoxon_stat, raw_p = float(test.statistic), float(test.pvalue)
            metric_pairs.append({
                "metric": metric,
                "label": label,
                "reference_alpha": 0.0,
                "comparison_alpha": comparison,
                "n_blocks": n,
                "wilcoxon_statistic": wilcoxon_stat,
                "wilcoxon_p_raw": raw_p,
                "rank_biserial_improvement_lower_is_better":
                    _rank_biserial_improvement(arrays[0], comp_values),
                "median_paired_difference_comparison_minus_reference":
                    float(np.median(diff)),
            })
        adjusted = _holm(item["wilcoxon_p_raw"] for item in metric_pairs)
        for item, corrected in zip(metric_pairs, adjusted):
            item["wilcoxon_p_holm_within_metric"] = corrected
            pairwise.append(item)

    _write_csv(TABLES / "alpha_median_summary.csv", summaries)
    _write_csv(TABLES / "alpha_omnibus_effects.csv", omnibus)
    _write_csv(TABLES / "alpha_pairwise_effects.csv", pairwise)
    return {
        "complete_paired_blocks": len(complete_blocks or set()),
        "summary_rows": summaries,
        "omnibus_rows": omnibus,
        "pairwise_rows": pairwise,
    }


def strategy_comparison(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def choose(candidates: list[dict[str, Any]], key) -> dict[str, Any]:
        if not candidates:
            raise RuntimeError("strategy has no eligible dynamic candidate")
        return sorted(candidates, key=key)[0]

    g0 = choose([row for row in ranked
                 if (row["grasp_point_id"] == "P1"
                     and float(row["capture_phase_s"]) == 0.0
                     and float(row["closure_speed_mps"]) == 0.01
                     and row["task_mode"] == "pose_6d"
                     and float(row["alpha"]) == 0.0)], lambda row: row["case_id"])
    alpha0 = [row for row in ranked if float(row["alpha"]) == 0.0]
    g1 = choose(alpha0, lambda row: (-float(row["manipulability"]), row["case_id"]))
    g2_pool = [row for row in alpha0 if int(row["pareto_layer"]) == 1]
    g2 = choose(g2_pool, lambda row: (int(row["core_margin_tie_group"]),
                                      float(row["normalized_initial_impulse_objective"]),
                                      float(row["terminal_joint_speed_max_radps"]),
                                      float(row["terminal_base_rate_dps"]),
                                      row["case_id"]))
    sync_pool = [row for row in ranked if int(row["pareto_layer"]) == 1]
    g2_sync = choose(sync_pool, lambda row: (int(row["core_margin_tie_group"]),
                                             float(row["normalized_initial_impulse_objective"]),
                                             float(row["terminal_joint_speed_max_radps"]),
                                             float(row["terminal_base_rate_dps"]),
                                             row["case_id"]))
    selected = {"G0": g0, "G1": g1, "G2": g2, "G2-Sync": g2_sync}
    output: list[dict[str, Any]] = []
    for strategy, row in selected.items():
        output.append({
            "strategy": strategy,
            "case_id": row["case_id"],
            "alpha": row["alpha"],
            "grasp_point_id": row["grasp_point_id"],
            "capture_phase_s": row["capture_phase_s"],
            "closure_speed_mps": row["closure_speed_mps"],
            "task_mode": row["task_mode"],
            "pareto_layer": row["pareto_layer"],
            "core_margin_tie_group": row["core_margin_tie_group"],
            "normalized_initial_impulse_objective": row["normalized_initial_impulse_objective"],
            "capture_impulse_linear_norm_Ns": row["capture_impulse_linear_norm_Ns"],
            "capture_impulse_angular_norm_Nms": row["capture_impulse_angular_norm_Nms"],
            "post_capture_omega_dps": row["post_capture_omega_dps"],
            "wheel_momentum_required_Nms": row["wheel_momentum_required_Nms"],
            "propellant_required_g": row["propellant_required_g"],
            "core_margin": row["core_margin"],
            "classification": row["classification"],
            "binding_constraint": row["binding_constraint"],
            "flex_status": row["flex_status"],
            "safe_claim_permitted": row["safe_claim_permitted"],
        })
    _write_csv(TABLES / "strategy_comparison.csv", output)
    return output


def render_figures(rows: list[dict[str, Any]], ranked: list[dict[str, Any]]) -> None:
    dynamic = [row for row in rows if row["dynamics_status"] == "EVALUATED"]
    panels = (
        ("capture_impulse_linear_norm_Ns", "Initial linear impulse [N s]"),
        ("capture_impulse_angular_norm_Nms", "Initial angular impulse [N m s]"),
        ("terminal_base_rate_dps", "Terminal base rate [deg/s]"),
        ("post_capture_omega_dps", "Post-capture rate [deg/s]"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), constrained_layout=True)
    for ax, (metric, ylabel) in zip(axes.ravel(), panels):
        pivot = _paired_frame(dynamic, metric)
        if metric == "post_capture_omega_dps":
            pivot = pivot.subtract(pivot[0.0], axis=0) * 1.0e12
            ylabel = "Post-capture rate change vs alpha=0 [pico-deg/s]"
        for _, values in pivot.iterrows():
            ax.plot(ALPHA_ORDER, values.to_numpy(float), color="#999999",
                    alpha=0.45, linewidth=0.9, zorder=1)
        medians = [float(np.median(pivot[alpha])) for alpha in ALPHA_ORDER]
        ax.plot(ALPHA_ORDER, medians, color="#000000", linewidth=1.8, zorder=2)
        for alpha, median in zip(ALPHA_ORDER, medians):
            ax.scatter([alpha], [median], s=55, color=ALPHA_COLOURS[alpha],
                       edgecolor="black", linewidth=0.5, zorder=3)
        ax.set_xticks(ALPHA_ORDER, ["0", "0.8", "1"])
        ax.set_xlabel(r"Synchronization gain $\alpha$")
        ax.set_ylabel(ylabel)
        if metric == "post_capture_omega_dps":
            ax.axhline(0.0, color="#555555", linewidth=0.8, linestyle="--")
            ax.text(0.02, 0.96,
                    "Pico-scale numerical change only; rigid rate remains ~3.05946 deg/s",
                    transform=ax.transAxes, va="top", fontsize=8.2,
                    bbox={"boxstyle": "round,pad=0.25", "facecolor": "white",
                          "edgecolor": "#AAAAAA", "alpha": 0.9})
        ax.grid(True, alpha=0.25)
    fig.suptitle("P0-C synchronized capture: six complete paired blocks")
    _save_figure(fig, "alpha_effects")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 5.8), constrained_layout=True)
    markers = {"pose_6d": "o", "approach_5d": "s"}
    for mode, marker in markers.items():
        for alpha in ALPHA_ORDER:
            subset = [row for row in dynamic
                      if row["task_mode"] == mode and float(row["alpha"]) == alpha]
            ax.scatter([float(row["capture_impulse_linear_norm_Ns"]) for row in subset],
                       [float(row["post_capture_omega_dps"]) for row in subset],
                       marker=marker, s=58, color=ALPHA_COLOURS[alpha],
                       edgecolor="black", linewidth=0.45,
                       label=f"{mode}, alpha={alpha:g}")
    for row in ranked[:3]:
        ax.annotate(str(row["overall_rank"]),
                    (float(row["capture_impulse_linear_norm_Ns"]),
                     float(row["post_capture_omega_dps"])),
                    xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set_xlabel("Initial linear impulse [N s]")
    post_values = [float(row["post_capture_omega_dps"]) for row in dynamic]
    ax.axhline(2.0, color="#D55E00", linewidth=1.5, linestyle="--",
               label="frozen limit = 2 deg/s")
    ax.set_ylim(1.8, 3.2)
    ax.text(0.98, 0.96,
            (f"All 18 cases: {min(post_values):.6f}-{max(post_values):.6f} deg/s\n"
             "Synchronization lowers initial impulse, not final rigid rate"),
            transform=ax.transAxes, ha="right", va="top", fontsize=8.2,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white",
                  "edgecolor": "#AAAAAA", "alpha": 0.9})
    ax.set_ylabel("Post-capture rigid rate [deg/s]")
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.6f"))
    ax.set_title("Rigid-capture trade space (18 dynamically evaluated cases)")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7.5, ncol=2)
    _save_figure(fig, "rigid_pareto")
    plt.close(fig)

    status = Counter(row["case_terminal_status"] for row in rows)
    fig, ax = plt.subplots(figsize=(7.5, 4.8), constrained_layout=True)
    labels = ["Dynamic evaluated", "Upstream rejected"]
    values = [status["COMPLETE_DYNAMIC_EVALUATED"],
              status["COMPLETE_UPSTREAM_REJECTED"]]
    bars = ax.bar(labels, values, color=["#009E73", "#D55E00"], width=0.58)
    ax.bar_label(bars, padding=3)
    ax.set_ylabel("Case count")
    ax.set_ylim(0, max(values) * 1.15)
    ax.set_title("All 216 cases have an explicit terminal status")
    ax.grid(axis="y", alpha=0.25)
    _save_figure(fig, "terminal_accounting")
    plt.close(fig)


def _markdown_table(headers: list[str], values: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |"
                 for row in values)
    return "\n".join(lines)


def build_report(summary: dict[str, Any], gate: dict[str, Any],
                 statistics: dict[str, Any], strategies: list[dict[str, Any]],
                 ranked: list[dict[str, Any]]) -> None:
    medians = statistics["summary_rows"]
    selected_metrics = (
        "capture_impulse_linear_norm_Ns",
        "capture_impulse_angular_norm_Nms",
        "terminal_base_rate_dps",
        "post_capture_omega_dps",
        "wheel_momentum_required_Nms",
    )
    median_rows: list[list[Any]] = []
    for metric in selected_metrics:
        by_alpha = {float(row["alpha"]): row for row in medians if row["metric"] == metric}
        label = STAT_METRICS[metric]
        median_rows.append([label] + [f"{float(by_alpha[a]['median']):.6g}" for a in ALPHA_ORDER])
    median_lookup = {(row["metric"], float(row["alpha"])): row
                     for row in statistics["summary_rows"]}
    omnibus_lookup = {row["metric"]: row for row in statistics["omnibus_rows"]}
    jlin_reduction = -float(median_lookup[("capture_impulse_linear_norm_Ns", 1.0)]
                             ["median_change_vs_alpha0_pct"])
    jang_reduction = -float(median_lookup[("capture_impulse_angular_norm_Nms", 1.0)]
                             ["median_change_vs_alpha0_pct"])
    terminal_rate_increase = float(median_lookup[("terminal_base_rate_dps", 1.0)]
                                   ["median_change_vs_alpha0_pct"])
    post_rate_max_change = float(omnibus_lookup["post_capture_omega_dps"]
                                 ["max_abs_change_alpha1_minus_alpha0"])

    strategy_rows = [[row["strategy"], row["case_id"], row["alpha"],
                      f"{float(row['normalized_initial_impulse_objective']):.6g}",
                      f"{float(row['capture_impulse_linear_norm_Ns']):.6g}",
                      f"{float(row['post_capture_omega_dps']):.6g}",
                      row["classification"], row["binding_constraint"]]
                     for row in strategies]
    top_rows = [[row["overall_rank"], row["case_id"], row["alpha"],
                 row["pareto_layer"],
                 f"{float(row['normalized_initial_impulse_objective']):.6g}",
                 f"{float(row['capture_impulse_linear_norm_Ns']):.6g}",
                 f"{float(row['capture_impulse_angular_norm_Nms']):.6g}",
                 f"{float(row['core_margin']):.6g}", row["classification"]]
                for row in ranked[:5]]
    report = f"""# P0-C 同步捕获 216 例刚体快算报告

日期：2026-07-14
冻结基线：`6c15395f444f693adad6ff0dfc9a3cfc0b4cf310`
实验：`P0-C-216-rigid-sync-20260714`

## 结论先行

- 终态记账：**{summary['terminal_cases']}/{summary['expected_cases']}**，门禁通过。
- 实际完成刚体动力学：**{summary['dynamic_evaluated_cases']}** 例；沿用冻结 Line A 后有 **{summary['upstream_rejected_cases']}** 例在几何/IK 上游被拒绝，均记为 `N/A`，没有把未运行量伪装为 0。
- 刚体核心约束通过且柔性未知：**{gate['core_safe_rigid_flex_unknown_cases']}** 例；正式 `SAFE`：**0** 例。所有新 α 状态的柔性证据均为 `UNKNOWN`，所以 `safe_claim_permitted=false`。
- 可重复性：两次独立 216 例运行的规范化行摘要一致，SHA-256 为 `{gate['determinism']['rows_sha256']}`。
- α 的配对比较只覆盖 **{statistics['complete_paired_blocks']}** 个完整动态块；这是确定性设计点，不作为随机总体显著性推断。
- Top-20 请求只有 **{len(ranked[:20])}** 个动态有效候选可供排序，因此交付真实的 {len(ranked[:20])} 行，不以几何无效案例补足名额。

## 模型和边界

期望末端扭量在惯性系 `I` 中定义为：

`xi_EE_des_I = alpha * xi_G_I + xi_closure_I`

其中顺序为 `[vx, vy, vz, wx, wy, wz]`，线速度单位 m/s、角速度单位 rad/s；`xi_closure_I=[-v_close*n_out_I, 0]`，正的闭合速度沿目标外法向的反方向靠近表面。随后用 `diag(R_BI,R_BI)` 转入基座坐标系求解零总动量自由漂浮末端跟踪。

捕获仍采用冻结 E1.5 的两阶段刚体定义：先用 6-D Delassus 冲量闭合接触相对扭量，再把全部关节塑性锁定。表中的“初始捕获冲量”与“锁定冲量”分开，最终角速度和动量需求来自锁定后的组合刚体。

## α 中位数响应

{_markdown_table(['指标', 'α=0', 'α=0.8', 'α=1'], median_rows)}

`α=1` 相对 `α=0` 的中位线冲量下降 **{jlin_reduction:.2f}%**、中位角冲量下降 **{jang_reduction:.2f}%**，但终端基座角速度中位数上升 **{terminal_rate_increase:.2f}%**。同一配对块的最终刚体角速度最大变化仅 **{post_rate_max_change:.3e} deg/s**，统计表明确标为 `NUMERICAL_ONLY_RELATIVE_LT_1E-9`。

完整 Friedman、Kendall W、Shapiro-Wilk 和 Wilcoxon/Holm 结果见 `tables/alpha_*.csv`。若最终角速度/轮动量随 α 不变，并非同步无效：在零总动量机械臂假设下，α 主要改变首次接触相对速度与初始冲量，却不能消除目标原有的系统角动量；全锁定后的组合刚体状态仍受总角动量守恒控制。

## G0/G1/G2/G2-Sync

{_markdown_table(['策略', '案例', 'α', '归一化初始冲量', 'Jlin [N s]', 'ω+ [deg/s]', '分类', '约束'], strategy_rows)}

## 排名前五

{_markdown_table(['排名', '案例', 'α', 'Pareto层', '归一化初始冲量', 'Jlin [N s]', 'Jang [N m s]', '核心裕度', '分类'], top_rows)}

全部有效候选见 `tables/top20_rigid_candidates.csv`。排序规则在运行前冻结为：Pareto 层 → 核心裕度（差异不超过 `1e-9` 视为守恒数值并列）→ 相对 G0 的线/角初始冲量等权归一化范数 → 终端关节速度 → 终端基座角速度 → 仅最后使用案例编号。Pareto 层本身是对六个“越低越好”的刚体量进行非支配分层；没有修改任何冻结阈值。

## 门禁与限制

- 门禁总体：`{gate['overall']}`；216/216 终态完整、动力学或上游拒绝的去向完整、状态与约束原因完整、两次运行一致。
- 上游限制：冻结 Line A 的 24 个 `(抓取点, 相位, 模式)` 组中，仅 P1/0 s 的两个模式具有选定关节解，因此实际动态覆盖为 18，而非 216。
- 柔性限制：本工作未运行 ANCF，也未把旧候选柔性结果外推到新 α 状态；柔性保持 `UNKNOWN`。
- 统计限制：完整配对块只有 6 个；p 值只作确定性网格的描述辅助，效果量和逐案例响应优先。
- 控制限制：本文只评价终端扭量、刚体冲量与等效执行机构需求，不声称已经实现 MPC、真实轮控/推力器闭环、HIL 或 E2/G3。

## 证据索引

- `results/sync_capture_216.csv` / `.json`：216 例全量记录。
- `results/gate_check.json`：计数、状态、约束、阈值冻结和确定性检查。
- `results/run_manifest.json`：运行摘要和源文件哈希。
- `tables/strategy_comparison.csv`、`tables/top20_rigid_candidates.csv`：策略与候选排序。
- `tables/alpha_median_summary.csv`、`alpha_omnibus_effects.csv`、`alpha_pairwise_effects.csv`：α 统计。
- `figures/alpha_effects.*`、`rigid_pareto.*`、`terminal_accounting.*`：机器生成图。
- `docs/literature_assumptions.md`：在线核验的一手文献与采用/不采用边界。
- `tests/test_report.md`：验收测试记录。
"""
    (E16_ROOT / "README.md").write_text(report, encoding="utf-8", newline="\n")


def main() -> None:
    _mkdirs()
    cfg = load_config()
    print("STAGE 1/4 first 216-case run", flush=True)
    rows, summary = run_campaign(cfg)
    first_digest = canonical_rows_digest(rows)
    print(f"STAGE 1/4 complete {first_digest}", flush=True)
    print("STAGE 2/4 independent deterministic rerun", flush=True)
    repeat_rows, repeat_summary = run_campaign(cfg)
    repeat_digest = canonical_rows_digest(repeat_rows)
    print(f"STAGE 2/4 complete {repeat_digest}", flush=True)
    deterministic = (first_digest == repeat_digest and summary == repeat_summary)
    if not deterministic:
        raise RuntimeError("independent campaign rerun did not reproduce exactly")

    ranked = assign_pareto_and_rank(rows, cfg)
    ranked_repeat = assign_pareto_and_rank(repeat_rows, cfg)
    ranked_digest = canonical_rows_digest(rows)
    if ranked_digest != canonical_rows_digest(repeat_rows):
        raise RuntimeError("ranked campaign rerun did not reproduce exactly")
    print("STAGE 3/4 statistics, ranking, and gate", flush=True)
    dynamic = [row for row in rows if row["dynamics_status"] == "EVALUATED"]
    stat_output = statistics_tables(dynamic)
    strategies = strategy_comparison(ranked)
    top = ranked[:20]
    _write_csv(TABLES / "top20_rigid_candidates.csv", top)
    _write_csv(RESULTS / "sync_capture_216.csv", rows)

    terminal_counts = Counter(row["case_terminal_status"] for row in rows)
    dynamics_counts = Counter(row["dynamics_status"] for row in rows)
    class_counts = Counter(row["classification"] for row in rows)
    binding_counts = Counter(row["binding_constraint"] for row in rows)
    alpha_counts_all = Counter(str(row["alpha"]) for row in rows)
    alpha_counts_dynamic = Counter(str(row["alpha"]) for row in dynamic)
    downstream_na_ok = all(
        row["capture_impulse_linear_norm_Ns"] == N_A
        and row["post_capture_omega_dps"] == N_A
        and row["wheel_momentum_required_Nms"] == N_A
        for row in rows if row["dynamics_status"] == "NOT_RUN_DUE_TO_UPSTREAM"
    )
    every_status_and_reason = all(
        bool(row.get("case_terminal_status")) and bool(row.get("binding_constraint"))
        for row in rows
    )
    mandatory = {
        "terminal_216_of_216": summary["terminal_cases"] == 216,
        "dynamics_or_upstream_216_of_216": (
            summary["dynamic_evaluated_cases"] + summary["upstream_rejected_cases"] == 216),
        "invalid_downstream_explicit_NA": downstream_na_ok,
        "status_and_binding_reason_complete": every_status_and_reason,
        "deterministic_independent_rerun": deterministic,
        "alpha_grid_complete": alpha_counts_all == Counter({"0.0": 72, "0.8": 72, "1.0": 72}),
        "paired_alpha_statistics_available": stat_output["complete_paired_blocks"] == 6,
        "protected_source_hashes_match": all(item["matched"] for item in summary["source_hashes"]),
        "no_safe_claim_with_flex_unknown": not any(bool(row["safe_claim_permitted"])
                                                     for row in rows),
    }
    gate = {
        "schema_version": "e16_gate_v1",
        "campaign_id": cfg["campaign_id"],
        "overall": "PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS" if all(mandatory.values()) else "FAIL",
        "mandatory_checks": mandatory,
        "case_accounting": summary,
        "terminal_status_counts": dict(sorted(terminal_counts.items())),
        "dynamics_status_counts": dict(sorted(dynamics_counts.items())),
        "classification_counts": dict(sorted(class_counts.items())),
        "binding_constraint_counts": dict(sorted(binding_counts.items())),
        "alpha_counts_all": dict(sorted(alpha_counts_all.items())),
        "alpha_counts_dynamic": dict(sorted(alpha_counts_dynamic.items())),
        "core_safe_rigid_flex_unknown_cases": class_counts["CORE_SAFE_FLEX_UNKNOWN"],
        "formal_safe_cases": sum(bool(row["safe_claim_permitted"]) for row in rows),
        "top20_requested": 20,
        "top20_delivered": len(top),
        "top20_underfill_reason": (N_A if len(top) == 20 else
                                    "ONLY_18_LINE_A_GEOMETRY_VALID_DYNAMIC_CASES"),
        "determinism": {
            "status": "PASS" if deterministic else "FAIL",
            "rows_sha256": ranked_digest,
            "independent_runs": 2,
        },
        "threshold_policy": {
            "status": "FROZEN_NO_WIDENING",
            "values": cfg["hard_constraints_frozen"],
        },
        "ranking_protocol": cfg["ranking_protocol"],
        "flex_policy": cfg["flex_policy"],
        "statistics": {
            "complete_paired_blocks": stat_output["complete_paired_blocks"],
            "interpretation": cfg["statistics"]["interpretation_limit"],
        },
    }
    if gate["overall"] == "FAIL":
        raise RuntimeError(f"gate failed: {mandatory}")

    payload = {
        "schema_version": "e16_results_v1",
        "campaign_id": cfg["campaign_id"],
        "configuration": cfg,
        "summary": summary,
        "rows_sha256": ranked_digest,
        "rows": rows,
    }
    _write_json(RESULTS / "sync_capture_216.json", payload)
    _write_json(RESULTS / "gate_check.json", gate)
    manifest = {
        "campaign_id": cfg["campaign_id"],
        "command": "python 30_simulation/e16_sync_capture/src/run_campaign.py",
        "frozen_baseline_commit": cfg["frozen_baseline_commit"],
        "expected_cases": 216,
        "terminal_cases": summary["terminal_cases"],
        "dynamic_evaluated_cases": summary["dynamic_evaluated_cases"],
        "upstream_rejected_cases": summary["upstream_rejected_cases"],
        "rows_sha256": ranked_digest,
        "deterministic_rerun": deterministic,
        "figure_export": {
            "pdf_creator": PDF_METADATA["Creator"],
            "pdf_producer": PDF_METADATA["Producer"],
            "pdf_creation_date": "OMITTED_FOR_BYTE_DETERMINISM",
            "pdf_modification_date": "OMITTED_FOR_BYTE_DETERMINISM",
        },
        "source_hashes": summary["source_hashes"],
        "artifacts": [
            "results/sync_capture_216.csv", "results/sync_capture_216.json",
            "results/gate_check.json", "tables/top20_rigid_candidates.csv",
            "tables/strategy_comparison.csv", "tables/alpha_median_summary.csv",
            "tables/alpha_omnibus_effects.csv", "tables/alpha_pairwise_effects.csv",
            "figures/alpha_effects.png", "figures/alpha_effects.pdf",
            "figures/rigid_pareto.png", "figures/rigid_pareto.pdf",
            "figures/terminal_accounting.png", "figures/terminal_accounting.pdf",
            "README.md", "docs/literature_assumptions.md",
            "tests/test_report.md", "tests/test_results.json",
        ],
    }
    print("STAGE 4/4 figures and Chinese report", flush=True)
    render_figures(rows, ranked)
    build_report(summary, gate, stat_output, strategies, ranked)
    manifest["artifact_sha256"] = {
        rel: _sha256_file(E16_ROOT / rel)
        for rel in manifest["artifacts"]
        if not rel.startswith("tests/") and (E16_ROOT / rel).is_file()
    }
    _write_json(RESULTS / "run_manifest.json", manifest)
    print(json.dumps({
        "overall": gate["overall"],
        "terminal": summary["terminal_cases"],
        "dynamic": summary["dynamic_evaluated_cases"],
        "upstream": summary["upstream_rejected_cases"],
        "core_safe_flex_unknown": gate["core_safe_rigid_flex_unknown_cases"],
        "formal_safe": gate["formal_safe_cases"],
        "paired_blocks": stat_output["complete_paired_blocks"],
        "top_delivered": len(top),
        "rows_sha256": ranked_digest,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
