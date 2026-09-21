"""VIZ-Gate 0 Stage 5 -- the four gate-status evidence figures.

40_evidence/artifacts/visualization/figures/
  fig_v07_gate_reason_breakdown.png       72-case waffle by SCIENTIFIC reason
  fig_v08_candidate_status_matrix.png     12x6 case matrix, four-class colors
  fig_v09_ancf_solver_attempt_timeline.png  15 fresh attempts + legacy forensics
  fig_v10_binding_constraint_map.png      3 physical-limit margins + reason mix

Semantic red line (display_semantics_v1.yaml iron rule 3): NO SAFE/UNSAFE
red-green binary.  Classes come from evidence_recount.recount() which re-derives
them row-by-row from binding_items; UNKNOWN != unsafe, missing evidence !=
physically unsafe, and VERIFIED_SAFE is an EMPTY set declared only in legends.

Every figure carries the lower-right provenance stamp (runtime git commit +
snapshot source files + scenario hashes where applicable).
"""
import _viz_bootstrap as vb  # noqa: F401  (env pins BEFORE numpy)
import csv
import json
import os

import numpy as np
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                    # noqa: E402
from matplotlib.patches import Rectangle, FancyArrowPatch  # noqa: E402
from matplotlib.lines import Line2D                # noqa: E402

import evidence_recount as er                      # noqa: E402

SNAP = vb.SNAPSHOT_DIR
FIG_DIR = vb.VIZ_FIGURES_DIR
COMMIT = vb.repo_commit_short()
DPI = 170

ATTEMPTS_CSV = os.path.join(
    SNAP, "results__sim_09_grasp_evaluator__e15_ancf_attempts.csv")
FORENSICS_CSV = os.path.join(
    SNAP, "results__sim_09_grasp_evaluator__e15_ancf_legacy_retry_forensics.csv")
GATE_JSON = os.path.join(
    SNAP, "results__sim_09_grasp_evaluator__e15_gate_check.json")

with open(os.path.join(vb.VIZ_CONFIG_DIR, "display_semantics_v1.yaml"),
          encoding="utf-8") as f:
    SEM = yaml.safe_load(f)
SC = {k: v["hex"] for k, v in SEM["semantic_colors"].items()}

CLS_COLOR = {
    "PHYSICAL_LIMIT_EXCEEDED": SC["physical_violation"],   # red
    "FLEX_SOLVER_UNKNOWN": SC["unknown"],                  # yellow
    "MISSING_FRESH_EVIDENCE": SC["evidence_missing"],      # grey-blue
    "VERIFIED_SAFE": SC["geometry_verified"],              # green (empty set)
}
CLS_ZH = {
    "PHYSICAL_LIMIT_EXCEEDED": "物理超限 PHYSICAL_LIMIT_EXCEEDED",
    "FLEX_SOLVER_UNKNOWN": "柔性求解不可判定 FLEX_SOLVER_UNKNOWN",
    "MISSING_FRESH_EVIDENCE": "证据缺失 MISSING_FRESH_EVIDENCE",
    "VERIFIED_SAFE": "已验证安全 VERIFIED_SAFE",
}

# CJK-capable font (Windows); keep unicode minus off for CJK fonts
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

REC = er.recount(write=False)
ROWS = REC["rows"]
TALLY = REC["tally"]
GATE = json.load(open(GATE_JSON, encoding="utf-8"))


def stamp(fig, sources, scenario_hashes=None):
    txt = f"git {COMMIT} | data: {', '.join(sources)}"
    if scenario_hashes:
        txt += f" | scenario_hash {', '.join(scenario_hashes)}"
    txt += f" | e15 source_commit {REC['provenance']['e15_source_commit'][:7]}"
    fig.text(0.988, 0.006, txt, ha="right", va="bottom", fontsize=5.5,
             color="#555555", family="monospace", wrap=True)


def save(fig, name):
    path = os.path.join(FIG_DIR, name)
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    assert os.path.getsize(path) > 20_000, f"{name} suspiciously small"
    print("saved", path, f"{os.path.getsize(path)/1024:.0f} KB")
    return path


# ==========================================================================
# fig_v07 -- waffle of the 72 cases by scientific reason class
# ==========================================================================
def fig_v07():
    order = ["PHYSICAL_LIMIT_EXCEEDED", "FLEX_SOLVER_UNKNOWN",
             "MISSING_FRESH_EVIDENCE"]
    seq = []
    for cls in order:
        seq += [cls] * TALLY[cls]
    assert len(seq) == 72

    fig = plt.figure(figsize=(11.5, 6.4))
    ax = fig.add_axes((0.04, 0.10, 0.44, 0.74))
    ncol, nrow = 12, 6
    for i, cls in enumerate(seq):
        r, c = divmod(i, ncol)
        ax.add_patch(Rectangle((c, nrow - 1 - r), 0.92, 0.92,
                               fc=CLS_COLOR[cls], ec="white", lw=1.2))
    ax.set_xlim(-0.2, ncol + 0.1)
    ax.set_ylim(-0.2, nrow + 0.1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("72 例按科学原因分类（1 格 = 1 例）", fontsize=11)

    # right side: legend + one-sentence meaning per class
    axr = fig.add_axes((0.50, 0.06, 0.49, 0.80))
    axr.axis("off")
    y = 0.96
    for cls in order + ["VERIFIED_SAFE"]:
        n = TALLY[cls]
        axr.add_patch(Rectangle((0.0, y - 0.045), 0.045, 0.062,
                                fc=CLS_COLOR[cls], ec="#444444", lw=0.5,
                                transform=axr.transAxes))
        head = f"{CLS_ZH[cls]}  —  {n}/72"
        if cls == "VERIFIED_SAFE":
            head += "（空集：仅在此图例声明，图中无绿格）"
        axr.text(0.07, y, head, fontsize=10, fontweight="bold",
                 va="top", transform=axr.transAxes)
        axr.text(0.07, y - 0.062, er.CLASSES[cls]["meaning_zh"],
                 fontsize=8.5, color="#333333", va="top", wrap=True,
                 transform=axr.transAxes)
        y -= 0.205
    axr.text(0.0, y + 0.02,
             "语义红线：本图不按 SAFE/UNSAFE 二分红绿；UNKNOWN ≠ 不安全，\n"
             "证据缺失 ≠ 物理不安全。分类按 binding_items 逐行重算（3/3/66/0，与\n"
             "bottleneck 表核对一致）。gate 判定 REPEAT_E1_5，admissible 0/72。",
             fontsize=8.5, color="#555555", va="top", transform=axr.transAxes)

    fig.suptitle("fig_v07 — Gate E1.5 科学原因分解（重算自 e15_bottleneck_summary.csv）",
                 fontsize=13, y=0.97)
    stamp(fig, ["e15_bottleneck_summary.csv (snapshot)",
                "evidence_recount.csv"])
    return save(fig, "fig_v07_gate_reason_breakdown.png")


# ==========================================================================
# fig_v08 -- 12x6 candidate status matrix
# ==========================================================================
def fig_v08():
    pids = ["P1", "P2", "P3"]
    tcs = [0, 30, 60, 90]
    vels = [5, 10, 20]           # mm/s
    modes = [("pose_6d", "6D"), ("approach_5d", "5D")]
    bycase = {r["case_id"]: r for r in ROWS}

    fig = plt.figure(figsize=(11.5, 8.6))
    ax = fig.add_axes((0.12, 0.15, 0.60, 0.72))
    nrow, ncol = len(pids) * len(tcs), len(vels) * len(modes)
    for ri, (pid, tc) in enumerate([(p, t) for p in pids for t in tcs]):
        for ci, (v, (mode, mlab)) in enumerate(
                [(v, m) for v in vels for m in modes]):
            cid = f"{pid}_tc{tc:02d}_v{v}mm_{mode}"
            row = bycase[cid]
            cls = row["recount_class"]
            yy = nrow - 1 - ri
            ax.add_patch(Rectangle((ci, yy), 0.94, 0.94,
                                   fc=CLS_COLOR[cls], ec="white", lw=1.0))
            ax.text(ci + 0.47, yy + 0.60, f"{pid}·t{tc:02d}", fontsize=5.4,
                    ha="center", va="center", color="white")
            ax.text(ci + 0.47, yy + 0.30, f"v{v}·{mlab}", fontsize=5.4,
                    ha="center", va="center", color="white")
    ax.set_xlim(-0.05, ncol)
    ax.set_ylim(-0.05, nrow)
    ax.set_aspect("equal")
    ax.set_xticks([c + 0.47 for c in range(ncol)])
    ax.set_xticklabels([f"{v} mm/s\n{mlab}" for v in vels
                        for _, mlab in modes], fontsize=7.5)
    ax.set_yticks([nrow - 1 - i + 0.47 for i in range(nrow)])
    ax.set_yticklabels([f"{p}  t_c={t} s" for p in pids for t in tcs],
                       fontsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)

    # sidebar note on the fresh-evidence row (P1, t_c = 0 -> top row)
    y_top = nrow - 0.53
    ax.annotate("P1 行注记：6 格获得新鲜评估\n（2 组 × 3 速度，t_c=0）\n"
                "其余 66 格 IK 不可达，仅几何筛除",
                xy=(ncol + 0.05, y_top), xytext=(ncol + 0.75, y_top - 1.4),
                fontsize=8.5, ha="left", va="center",
                arrowprops=dict(arrowstyle="-[, widthB=1.4, lengthB=0.5",
                                color="#444444", lw=1.1),
                annotation_clip=False)

    handles = [Line2D([0], [0], marker="s", ls="", ms=11,
                      mfc=CLS_COLOR[c], mec="#444444", label=CLS_ZH[c] +
                      ("（空集）" if c == "VERIFIED_SAFE" else f"（{TALLY[c]}）"))
               for c in ("PHYSICAL_LIMIT_EXCEEDED", "FLEX_SOLVER_UNKNOWN",
                         "MISSING_FRESH_EVIDENCE", "VERIFIED_SAFE")]
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.055), fontsize=8, ncol=2, frameon=False)

    fig.suptitle("fig_v08 — 72 例候选状态矩阵（行 = 抓取点 × 相位，列 = 速度 × 任务模式）\n"
                 "格色 = 科学原因四分类（非红绿安全二分）；gate REPEAT_E1_5，admissible 0/72",
                 fontsize=12, y=0.965)
    stamp(fig, ["e15_bottleneck_summary.csv (snapshot)",
                "e15_results_72cases.csv (snapshot)"])
    return save(fig, "fig_v08_candidate_status_matrix.png")


# ==========================================================================
# fig_v09 -- ANCF attempt timeline / swimlanes + legacy forensics flow
# ==========================================================================
def fig_v09():
    with open(ATTEMPTS_CSV, newline="", encoding="utf-8") as f:
        attempts = list(csv.DictReader(f))
    with open(FORENSICS_CSV, newline="", encoding="utf-8") as f:
        forensics = list(csv.DictReader(f))
    assert len(attempts) == 15, len(attempts)

    lanes = []
    for a in attempts:
        if a["case_id"] not in lanes:
            lanes.append(a["case_id"])
    fig = plt.figure(figsize=(11.5, 8.8))

    # ---- top panel: fresh E1.5 attempts, x = retry level ----
    ax = fig.add_axes((0.24, 0.55, 0.72, 0.35))
    c_ok, c_fail = SC["geometry_verified"], "#e07b28"
    for a in attempts:
        y = len(lanes) - 1 - lanes.index(a["case_id"])
        x = int(a["retry_level"])
        ok = a["classification"] == "COMPLETED"
        ax.scatter([x], [y], s=190, marker="s" if ok else "X",
                   c=c_ok if ok else c_fail, ec="#333333", lw=0.6, zorder=3)
        ax.annotate(f"{a['method']}\nrtol {a['rtol']}\n{float(a['integration_wall_s']):.0f} s",
                    (x, y), xytext=(0, -26), textcoords="offset points",
                    fontsize=5.6, ha="center", color="#555555")
    for y in range(len(lanes)):
        ax.axhline(y, color="#dddddd", lw=0.7, zorder=1)
    ax.set_yticks(range(len(lanes)))
    ax.set_yticklabels(list(reversed(lanes)), fontsize=8, family="monospace")
    ax.set_xticks(range(4))
    ax.set_xticklabels(["attempt L0\n(Radau 1e-6)", "L1\n(+max_step)",
                        "L2\n(Radau 1e-7)", "L3\n(BDF 1e-7)"], fontsize=7.5)
    ax.set_xlim(-0.5, 3.5)
    ax.set_ylim(-0.85, len(lanes) - 0.3)
    ax.set_title("E1.5 新鲜 ANCF 求解 attempt 泳道（15 次；6 个可达工况）",
                 fontsize=10.5)
    handles = [Line2D([0], [0], marker="s", ls="", ms=10, mfc=c_ok,
                      mec="#333333", label="COMPLETED（3 例，L0 即收敛）"),
               Line2D([0], [0], marker="X", ls="", ms=10, mfc=c_fail,
                      mec="#333333", label="SOLVER_NONCONVERGENCE（3 例 × L0–L3 全部失败）")]
    ax.legend(handles=handles, loc="upper right", fontsize=7.5, frameon=False)

    # ---- bottom panel: legacy RETRY_OK forensics flow ----
    axb = fig.add_axes((0.05, 0.055, 0.9, 0.40))
    axb.axis("off")
    retry_ok = [r for r in forensics
                if r["historical_flex_status"].startswith("RETRY_OK")]
    others = [r for r in forensics
              if not r["historical_flex_status"].startswith("RETRY_OK")]
    assert len(retry_ok) == 5, len(retry_ok)

    boxes_x = [0.06, 0.42, 0.78]
    heads = ["legacy 标记\nRETRY_OK_rtol1e-5", "E1.5 复核重跑\n4 attempts 全不收敛\n复核(crosscheck)记录 = 0",
             "降级\nUNKNOWN_INADMISSIBLE"]
    colors = ["#b9c6a0", c_fail, SC["unknown"]]
    for i, r in enumerate(retry_ok):
        y = 0.76 - i * 0.125
        for bx, col in zip(boxes_x, colors):
            axb.add_patch(Rectangle((bx, y - 0.045), 0.17, 0.09, fc=col,
                                    alpha=0.28, ec=col, lw=1.2,
                                    transform=axb.transAxes))
        axb.text(boxes_x[0] + 0.085, y, r["case_id"], fontsize=6.8,
                 ha="center", va="center", family="monospace",
                 transform=axb.transAxes)
        axb.text(boxes_x[1] + 0.085, y,
                 f"attempts={r['attempt_count']}  cross_validated={r['cross_validated']}",
                 fontsize=6.8, ha="center", va="center", family="monospace",
                 transform=axb.transAxes)
        axb.text(boxes_x[2] + 0.085, y, r["atomic_status"], fontsize=6.8,
                 ha="center", va="center", family="monospace",
                 transform=axb.transAxes)
        for x0, x1 in ((boxes_x[0] + 0.17, boxes_x[1]),
                       (boxes_x[1] + 0.17, boxes_x[2])):
            axb.add_patch(FancyArrowPatch((x0 + 0.004, y), (x1 - 0.004, y),
                                          arrowstyle="-|>", mutation_scale=13,
                                          color="#555555", lw=1.2,
                                          transform=axb.transAxes))
    for j, (bx, h) in enumerate(zip(boxes_x, heads)):
        axb.text(bx + 0.085, 1.00, h, fontsize=8.2, ha="center", va="top",
                 fontweight="bold", transform=axb.transAxes)
    axb.text(0.06, 0.13,
             "另有 2 例 legacy 即为 FLEX_SOLVER_FAIL（"
             + ", ".join(r["case_id"] for r in others) + "），复核后同为不收敛。",
             fontsize=7.8, color="#555555", transform=axb.transAxes)
    axb.text(0.06, 0.055,
             "关键结论：0/5 可复核 = 交叉比较从未发生（复核重跑不收敛，无可比对输出），\n"
             "而非“比较后发现不一致”。legacy RETRY_OK 数值从未获得独立复核记录。",
             fontsize=8.8, color="#8a5a00", fontweight="bold", va="top",
             transform=axb.transAxes)
    axb.set_title("legacy RETRY_OK → E1.5 复核 → 降级流向（5 条）", fontsize=10.5)

    fig.suptitle("fig_v09 — ANCF 求解 attempt 时间线与 legacy 复核取证",
                 fontsize=13, y=0.975)
    stamp(fig, ["e15_ancf_attempts.csv (snapshot)",
                "e15_ancf_legacy_retry_forensics.csv (snapshot)"])
    return save(fig, "fig_v09_ancf_solver_attempt_timeline.png")


# ==========================================================================
# fig_v10 -- binding constraint map
# ==========================================================================
def fig_v10():
    phys = [r for r in ROWS if r["recount_class"] == "PHYSICAL_LIMIT_EXCEEDED"]
    unk = [r for r in ROWS if r["recount_class"] == "FLEX_SOLVER_UNKNOWN"]
    miss = [r for r in ROWS if r["recount_class"] == "MISSING_FRESH_EVIDENCE"]

    fig = plt.figure(figsize=(11.5, 8.2))

    # ---- top: the 3 physically-exceeded cases, rate vs provisional limit ----
    ax = fig.add_axes((0.30, 0.60, 0.62, 0.30))
    ylabels, rates, margins, hashes = [], [], [], []
    for r in phys:
        ylabels.append(r["case_id"])
        rates.append(float(r["post_capture_rate_dps"]))
        margins.append(float(r["margin__post_capture_rate_dps"]))
        hashes.append(r["scenario_hash"])
    limit = float(phys[0]["limit__post_capture_rate_dps"])
    yy = np.arange(len(phys))[::-1]
    ax.barh(yy, rates, height=0.55, color=CLS_COLOR["PHYSICAL_LIMIT_EXCEEDED"],
            ec="#333333", lw=0.6)
    ax.axvline(limit, color="#333333", ls="--", lw=1.4)
    ax.set_ylim(-0.95, len(phys) - 0.45)
    ax.text(limit + 0.05, -0.62,
            f"暂行限值 limit = {limit:.1f} deg/s (PROVISIONAL, UNVERIFIED)",
            fontsize=8, va="center")
    for y, rate, mg in zip(yy, rates, margins):
        ax.text(rate + 0.04, y, f"{rate:.3f} deg/s   margin = {mg:+.2f}",
                fontsize=8, va="center")
    ax.set_yticks(yy)
    ax.set_yticklabels(ylabels, fontsize=8.5, family="monospace")
    ax.set_xlim(0, 4.4)
    ax.set_xlabel("post_capture_rate_dps（捕获后残余角速率, deg/s）", fontsize=9)
    ax.set_title("3 例物理超限：实测 3.059 deg/s 对暂行限值 2.0（margin −0.53）",
                 fontsize=10.5)

    # ---- bottom: reason composition of the 3 UNKNOWN + 66 MISSING ----
    axb = fig.add_axes((0.30, 0.115, 0.62, 0.37))
    comp = []
    for cls, grp in (("FLEX_SOLVER_UNKNOWN", unk),
                     ("MISSING_FRESH_EVIDENCE", miss)):
        cnt = {}
        for r in grp:
            for t in er._tokens(r["binding_items"]):
                cnt[t] = cnt.get(t, 0) + 1
        for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
            comp.append((cls, k, v))
    yy = np.arange(len(comp))[::-1]
    for y, (cls, k, v) in zip(yy, comp):
        axb.barh(y, v, height=0.6, color=CLS_COLOR[cls], ec="#333333", lw=0.4)
        axb.text(v + 0.6, y, str(v), fontsize=7.5, va="center")
    axb.set_yticks(yy)
    axb.set_yticklabels([k for _, k, _ in comp], fontsize=7,
                        family="monospace")
    axb.set_xlim(0, 74)
    axb.set_xlabel("binding_items 原因码出现次数（3 例不可判定 + 66 例证据缺失）",
                   fontsize=9)
    axb.set_title("其余 69 例的原因构成：黄 = ANCF 失败不可判定；灰蓝 = IK 不可达"
                  "导致全链证据缺失", fontsize=10.5)
    handles = [Line2D([0], [0], marker="s", ls="", ms=9,
                      mfc=CLS_COLOR["FLEX_SOLVER_UNKNOWN"], mec="#333",
                      label="FLEX_SOLVER_UNKNOWN（3 例）"),
               Line2D([0], [0], marker="s", ls="", ms=9,
                      mfc=CLS_COLOR["MISSING_FRESH_EVIDENCE"], mec="#333",
                      label="MISSING_FRESH_EVIDENCE（66 例）")]
    axb.legend(handles=handles, loc="upper right", fontsize=7.5, frameon=False,
               bbox_to_anchor=(0.99, 0.90))

    # secondary-axis annotation: threshold registry status
    ax2 = ax.twinx()
    ax2.set_yticks([])
    ax2.set_ylabel("阈值登记册状态：PROVISIONAL\n（全部 limit 为暂行值，未经验证）",
                   fontsize=8.5, color="#8a5a00", rotation=270, labelpad=30)

    fig.suptitle("fig_v10 — 约束绑定图：谁在真正“卡门”\n"
                 "（物理超限仅 3 例有数值证明；证据缺失 ≠ 物理不安全）",
                 fontsize=12.5, y=0.985)
    stamp(fig, ["e15_bottleneck_summary.csv (snapshot)"],
          scenario_hashes=hashes)
    return save(fig, "fig_v10_binding_constraint_map.png")


if __name__ == "__main__":
    print("recount tally:", TALLY, "| matches_expected:",
          REC["matches_expected"])
    fig_v07()
    fig_v08()
    fig_v09()
    fig_v10()
