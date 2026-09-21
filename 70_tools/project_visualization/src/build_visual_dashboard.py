"""VIZ-Gate 0 Stage 6 -- self-contained project dashboard + one-click rebuild.

Writes 40_evidence/artifacts/visualization/project_visualization_v0.html, a single
offline file with three modes:

  Geometry Mode  the complete interactive grasp explorer embedded as an inline
                 base64 payload and hydrated into an iframe at runtime, the
                 I/S/B/M/E/T/D/G1..G3 frame registry, 10 static
                 figures v01..v10 embedded as base64 thumbnails, and the full
                 45-row asset audit table.
  Dynamics Mode  6 replay-video cards embedded byte-for-byte as base64 MP4
                 data URIs, each carrying its keyframe-check badge, plus
                 the five audited headline numbers RE-READ from their source
                 CSVs at build time (sim_05 / sim_06 / sim_08).
  Evidence Mode  plotly donut of the four recount reason classes (data from
                 40_evidence/artifacts/visualization/tables/evidence_recount.csv), the interactive
                 72-cell case matrix (hover: case_id / scenario_hash /
                 reason), the t1..t11 functional-test table, Line A/B/C
                 verdict cards, the three-column claim ledger (declare /
                 qualify / forbid -- hardcoded but item-by-item verified
                 against 01_project/competition/00_repo_truth_audit_20260711.md
                 and the snapshot sim_09_gate_e15_report.md), and the 22-row
                 snapshot hash table.

Self-containment: plotly.js 6.3.0 is INLINED (plotly.offline.get_plotlyjs,
no CDN); figures and all six MP4 files are base64 data URIs.  The explorer is
an inline base64 runtime payload hydrated into a blank iframe (rather than a
multi-MB data URL, which Chromium rejects); it reuses the already-inlined
parent Plotly object instead of parsing a duplicate 4.7 MB bundle.  The
delivered dashboard has zero network or sidecar fetch targets and opens
directly from file://.  A strict fetch-target scan runs after writing.

Determinism: the generation timestamp shown on the page is the HEAD COMMIT
time from git (not wall clock), so rebuilding from the same commit and the
same inputs yields the same page.

Semantic red lines (inherited): UNKNOWN != unsafe; missing evidence !=
physically unsafe; no SAFE candidate / Top-3 claims; all flexible-dynamics
content carries the DIAGNOSTIC marker.

One-click rebuild:
  python 70_tools/project_visualization/src/build_visual_dashboard.py --dashboard-only
      rebuild ONLY the dashboard from artifacts already on disk (fast).
  python 70_tools/project_visualization/src/build_visual_dashboard.py --all [--dry-run]
      full chain: asset_audit + frame_registry -> make_figures -> evidence_recount +
      evidence_figures -> grasp_explorer_builder -> make_replay_videos ->
      dashboard -> 70_tools/project_visualization/tests/run_all.py.  --dry-run validates the
      chain (module files + expected outputs) and prints every step without
      executing the expensive stages.
"""
import _viz_bootstrap as vb  # noqa: F401  (env pins BEFORE numpy)
import argparse
import base64
import csv
import html as html_mod
import json
import os
import re
import subprocess
import sys

REPO = vb.REPO_ROOT
SNAP = vb.SNAPSHOT_DIR
OUT_HTML = os.path.join(REPO, "40_evidence", "artifacts", "visualization",
                        "project_visualization_v0.html")
GATE_JSON = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_gate_check.json")
E15_72_CSV = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_results_72cases.csv")
RECOUNT_CSV = os.path.join(vb.VIZ_TABLES_DIR, "evidence_recount.csv")
KEYFRAME_CSV = os.path.join(vb.VIZ_TABLES_DIR, "replay_keyframe_check.csv")
ASSET_CSV = os.path.join(vb.VIZ_TABLES_DIR, "asset_audit.csv")
FRAME_CSV = os.path.join(vb.VIZ_TABLES_DIR, "frame_registry_v1.csv")
PROTECT_CSV = os.path.join(vb.VIZ_TABLES_DIR, "gate_artifact_protection_manifest.csv")
SIM05_CSV = os.path.join(REPO, "30_simulation", "sim_05_free_floating_arm", "results",
                         "sim_05_base_attitude.csv")
SIM06_CSV = os.path.join(REPO, "30_simulation", "sim_06_capture_impulse", "results",
                         "capture_impulse_matrix_v0.csv")
SIM08_CSV = os.path.join(REPO, "30_simulation", "sim_08_detumble_actuator_budget",
                         "results", "actuator_budget_sweep.csv")
FIG_DIR = vb.VIZ_FIGURES_DIR
VIDEO_DIR = os.path.join(REPO, "40_evidence", "artifacts", "visualization", "videos")
EXPLORER_HTML = os.path.join(REPO, "40_evidence", "artifacts", "visualization",
                             "grasp_geometry_explorer_v0.html")

# semantic colors = display_semantics_v1 language (same as explorer/videos)
COLORS = {"PHYSICAL_LIMIT_EXCEEDED": "#c8443c", "FLEX_SOLVER_UNKNOWN": "#e0b400",
          "MISSING_FRESH_EVIDENCE": "#7d93b2", "VERIFIED_SAFE": "#4c9f70"}
CLS_ZH = {
    "PHYSICAL_LIMIT_EXCEEDED": "物理超限（已有数值证明真实超限，暂行阈值）",
    "FLEX_SOLVER_UNKNOWN": "柔性求解不可判定（ANCF 失败；不可判定 ≠ 不安全）",
    "MISSING_FRESH_EVIDENCE": "证据缺失（本轮未产生新鲜动态证据；≠ 物理不安全）",
    "VERIFIED_SAFE": "已验证安全（空集）",
}

FIGURES = [
    ("fig_v01_system_assembly_isometric.png", "v01 系统装配 · 等轴测",
     "服务星 12U + B601@E1.5 构型 + 22 kg 合作目标（launch_adapter_ring 位于捕获点）"),
    ("fig_v02_system_assembly_top.png", "v02 系统装配 · 顶视", "同一装配场景顶视投影"),
    ("fig_v03_system_assembly_side.png", "v03 系统装配 · 侧视", "同一装配场景侧视投影"),
    ("fig_v04_mount_and_frames.png", "v04 安装接口与坐标系",
     "160×160 适配器 + 冻结 T_SM + S/M/E 坐标框架"),
    ("fig_v05_target_grasp_points.png", "v05 目标抓取点",
     "150 kg 碎片 P1/P2/P3 候选抓点（按 E1.5 证据态着色，无安全声明）"),
    ("fig_v06_workspace_keepout.png", "v06 工作空间与禁入区",
     "B601 可达包络 vs 目标禁入区"),
    ("fig_v07_gate_reason_breakdown.png", "v07 门禁原因四类分解",
     "72 工况按证据四类重算：3 / 3 / 66 / 0"),
    ("fig_v08_candidate_status_matrix.png", "v08 候选证据状态矩阵",
     "72 格证据状态（UNKNOWN ≠ 不安全）"),
    ("fig_v09_ancf_solver_attempt_timeline.png", "v09 ANCF 求解尝试时间线",
     "15 条逐次求解记录（Radau→BDF 链，失败不插值）"),
    ("fig_v10_binding_constraint_map.png", "v10 绑定约束图",
     "每工况绑定约束项分布（M_PCS 语义）"),
]

VIDEOS = [
    ("anim_v01_target_tumble.mp4", "v01 目标翻滚 + 捕获相位时间线",
     "150 kg 碎片力矩自由翻滚回放（DOP853）+ P1/P2/P3 抓点与 t_c 相位；翻滚轴为 E1 语境值"
     "（E1.5 快照未重申，画面内按证据缺失色声明）。", False),
    ("anim_v02_b601_approach.mp4", "v02 B601 接近 E1.5 选定构型",
     "8 s 最小加加速度接近 P1_tc00_v10mm_pose_6d 的快照选定 q_c——几何选定，"
     "动力学可采纳性未建立（REPEAT_E1_5）。", False),
    ("anim_v03_base_reaction.mp4", "v03 自由漂浮基座反作用（sim_05）",
     "纯 CSV 回放：臂机动 q2 0→+60° / q3 0→−40°，基座姿态偏差峰值 19.20°"
     "（q2 超 URDF 限位——动力学基准，非飞行轨迹，画面内声明）。", False),
    ("anim_v04_capture_impulse.mp4", "v04 捕获冲量（sim_06 名义格）",
     "接触冻结帧展示六维冲量数字；合体后仍以 ≈3.06 °/s 章动——捕获 ≠ 消旋。", False),
    ("anim_v05_flex_diagnostic.mp4", "v05 ANCF 柔性板捕获响应",
     "DIAGNOSTIC——非门禁验证。只读呈现既有汇总 CSV、聚合 PNG 与两例 "
     "FLEX_SOLVER_FAIL；仓库未保存可回放节点时序，构建中不求解、不插值、不伪造。", True),
    ("anim_v06_gate_explanation.mp4", "v06 E1.5 门禁裁决讲解",
     "72 格逐帧按 binding_items 规则重算并与 e15_gate_check.json 交叉核对："
     "0 SAFE / 3 UNKNOWN / 69 UNSAFE。", False),
]

# claim ledger -- hardcoded, item-by-item verified against
# 01_project/competition/00_repo_truth_audit_20260711.md ("审计") and the
# snapshot docs__90_competition__sim_09_gate_e15_report.md ("E1.5报告")
CLAIMS_OK = [
    ("sim_04 捕获走廊 1620 例全网格，SAFE 312/1620 = 19.3%，全部反作用感知", "审计 #1/#2"),
    ("3.0 °/s 碎片 @ v_app 0.01 m/s 捕获后合体 3.06 °/s（六维冲量解，25 项验证）",
     "capture_impulse_matrix_v0.csv；审计 #4"),
    ("消旋预算 |H_c| = 3.65 N·m·s ≈ 12× 三轮组容量（3×100 mN·m·s）；冷气工质 36.5 g"
     "（lever 0.17 m / Isp 60 s）", "actuator_budget_sweep.csv；审计 #6/#7/#8"),
    ("标量冲量公式系统性低估 −2.9% ~ −12.3%（全网格验证）", "审计 #5"),
    ("E1.5 证据线 A（真实几何+两阶段捕获）PASS：接触 twist 残差 1.4e-16、"
     "动量残差 1.0e-12、能量闭合 3.6e-15", "e15_gate_check.json line_A"),
    ("功能回归 t1–t11 全部通过；旧 E1 冻结证据 10/10 git blob 一致",
     "e15_gate_check.json functional_tests / legacy_e1_frozen"),
    ("72 工况证据状态计数 SAFE 0 / UNKNOWN 3 / UNSAFE 69（证据状态陈述，非物理结论）",
     "e15_gate_check.json state_counts"),
]
CLAIMS_QUALIFIED = [
    ("19.20° 基座姿态偏差峰值——B601 混合模型口径；q2=+60° 超 URDF 限位，"
     "是 sim_03 可比性动力学基准，非飞行轨迹", "审计 #9 + §4 约束注记"),
    ("刚性锁定激振比须写 ≈92× / 近两个数量级，不得写 100 倍", "审计 #12"),
    ("振铃衰减 37–75 s 为包络对数拟合外推值（超出 15 s 仿真窗），引用须注明外推", "审计 #13"),
    ("一切 ANCF / 柔性动力学内容仅限 DIAGNOSTIC 引用：Line B REPEAT，"
     "两例 FLEX_SOLVER_FAIL 不可判定", "E1.5报告 §3/§5"),
    ("全部安全阈值为 PROVISIONAL（暂行登记）；本轮 SAFE 定义 ≠ 普适航天安全标准",
     "E1.5报告 §6"),
    ("翻滚轴 [1, 0.15, 0.4]/|·| @ 3 °/s 为 E1 语境值，E1.5 快照未重申——"
     "引用时保留该声明", "anim_v01 画面声明"),
    ("装配图 v01–v04 的 22 kg 合作卫星与候选图 v05/v06 的 150 kg 碎片是两个"
     "展示场景（映射声明）：E1.5 的 72 工况全部针对碎片 P1/P2/P3", "asset_audit e15_results 行"),
]
CLAIMS_FORBIDDEN = [
    ("宣称存在 SAFE 候选或名义 Top-3（nominal_top3 = []，admissible 0/72）",
     "e15_gate_check.json"),
    ("把 UNKNOWN 或证据缺失表述为“不安全”（UNKNOWN ≠ 不安全；证据缺失 ≠ 物理不安全）",
     "语义红线 / display_semantics_v1"),
    ("把 REPEAT_E1_5 表述为 BLOCKED 或项目失败（它是“证据不足、重复 E1.5”的科学裁决）",
     "E1.5报告 §1"),
    ("使用“首次 ANCF / 在轨验证”等禁用语", "审计 §4 约束 11"),
    ("宣称柔性求解结果已通过门禁（Line B / C 均为 REPEAT）", "E1.5报告 §5"),
    ("宣称存在视觉/AprilTag 或 HIL 闭环（审计判定 MISSING）", "审计 §3"),
]


# ===================================================================== data
def esc(s):
    return html_mod.escape(str(s), quote=True)


def git_head_date():
    try:
        out = subprocess.run(["git", "show", "-s", "--format=%ci", "HEAD"],
                             cwd=REPO, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def load_gate():
    g = json.load(open(GATE_JSON, encoding="utf-8"))
    lines = {
        "A": "PASS" if g["line_A_geometry_capture"]["passed"] else "REPEAT",
        "B": "PASS" if g["line_B_ancf_reliability"]["passed"] else "REPEAT",
        "C": "PASS" if g["line_C_mpcs_pareto"]["passed"] else "REPEAT",
    }
    return {"gate": g["gate"], "state_counts": g["state_counts"],
            "tests": g["functional_tests"], "lines": lines,
            "legacy": g["legacy_e1_frozen"],
            "registry_status": g["line_C_mpcs_pareto"].get("registry_status", ""),
            "nominal_top3": g.get("nominal_top3", [])}


def count_admissible():
    with open(E15_72_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n_adm = sum(r["admissible"].strip().lower() == "true" for r in rows)
    return n_adm, len(rows)


def load_recount():
    with open(RECOUNT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    tally = {k: 0 for k in COLORS}
    for r in rows:
        tally[r["recount_class"]] = tally.get(r["recount_class"], 0) + 1
    return rows, tally


def load_keyframes():
    with open(KEYFRAME_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    per = {}
    for r in rows:
        v = r["video"]
        tot, ok = per.get(v, (0, 0))
        per[v] = (tot + 1, ok + (r["match"] == "True"))
    total = len(rows)
    matched = sum(r["match"] == "True" for r in rows)
    return per, total, matched


def load_assets():
    with open(ASSET_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_frames():
    with open(FRAME_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_snapshot_hashes():
    with open(PROTECT_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def key_numbers():
    """The five audited headline numbers, RE-READ from source CSVs."""
    with open(SIM05_CSV, newline="", encoding="utf-8") as f:
        dev_peak = max(float(r["base_dev_angle_deg"]) for r in csv.DictReader(f))
    post = None
    with open(SIM06_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["target"] == "target_debris_v0"
                    and float(r["tumble_dps"]) == 3.0
                    and float(r["v_app_mps"]) == 0.01):
                post = float(r["post_rate_full_dps"])
                break
    H = prop = None
    with open(SIM08_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["target"] == "target_debris_v0"
                    and float(r["tumble_dps"]) == 3.0
                    and float(r["lever_m"]) == 0.17
                    and r["isp_class"] == "cold_gas_60s"):
                H, prop = float(r["H_Nms"]), float(r["propellant_g"])
                break
    assert None not in (post, H, prop), "headline source rows not found"
    return [
        (f"{dev_peak:.2f}°", "基座姿态偏差峰值（须带臂模型口径限定）",
         "sim_05_base_attitude.csv"),
        (f"3.00 → {post:.2f} °/s", "捕获前后目标/合体角速度（捕获 ≠ 消旋）",
         "capture_impulse_matrix_v0.csv"),
        (f"|H_c| = {H:.2f} N·m·s", "3 °/s 碎片需消旋角动量",
         "actuator_budget_sweep.csv"),
        (f"{H / 0.3:.1f}×", "轮组容量比（3×100 mN·m·s 三轮组）",
         "actuator_budget_sweep.csv"),
        (f"{prop:.1f} g", "冷气工质（lever 0.17 m / Isp 60 s）",
         "actuator_budget_sweep.csv"),
    ]


# ===================================================================== html
def _fig_cards():
    cards = []
    for fname, title, note in FIGURES:
        p = os.path.join(FIG_DIR, fname)
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        cards.append(
            f'<figure class="figcard">'
            f'<img loading="lazy" src="data:image/png;base64,{b64}" '
            f'alt="{esc(title)}" onclick="lightbox(this)">'
            f'<figcaption><b>{esc(title)}</b><br>'
            f'<span class="mut">{esc(note)}</span></figcaption></figure>')
    return "\n".join(cards)


def _asset_table(rows):
    cols = ["asset_id", "asset_type", "path", "exists", "units", "frame",
            "mass", "confidence", "usable_for_render", "blocking_issue"]
    head = "".join(f"<th>{esc(c)}</th>" for c in cols)
    body = []
    for r in rows:
        tds = "".join(f"<td>{esc(r[c])}</td>" for c in cols)
        body.append(f"<tr>{tds}</tr>")
    return (f'<div class="scrollbox"><table class="data">'
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody>"
            f"</table></div>")


def _frame_table(rows):
    cols = ["frame_name", "parent_frame", "translation_m", "quaternion_wxyz",
            "source_file", "confidence", "context_note", "scenario_hash"]
    head = "".join(f"<th>{esc(c)}</th>" for c in cols)
    body = []
    for r in rows:
        tds = "".join(f'<td class="{("mono" if c in ("translation_m", "quaternion_wxyz", "scenario_hash") else "")}">{esc(r[c])}</td>'
                      for c in cols)
        body.append(f'<tr data-frame="{esc(r["frame_name"])}">{tds}</tr>')
    return (f'<div class="scrollbox framebox"><table class="data">'
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody>"
            f"</table></div>")


def _data_uri(path, mime):
    with open(path, "rb") as f:
        payload = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _explorer_embed():
    with open(EXPLORER_HTML, encoding="utf-8") as f:
        source = f.read()
    # The standalone explorer contains its own 4.7 MB Plotly bundle.  The
    # dashboard already has the identical bundle, so the iframe safely reuses
    # parent.Plotly; everything else remains byte-for-byte from the explorer.
    source, n = re.subn(
        r"<script>.*?</script>",
        "<script>window.Plotly = parent.Plotly;</script>", source,
        count=1, flags=re.S)
    if n != 1:
        raise RuntimeError("could not isolate explorer Plotly bundle")
    old_call = 'Plotly.react("plot",'
    new_call = 'Plotly.react(document.getElementById("plot"),'
    if source.count(old_call) != 1:
        raise RuntimeError("could not isolate explorer Plotly.react target")
    source = source.replace(old_call, new_call)
    payload = base64.b64encode(source.encode("utf-8")).decode("ascii")
    # Hydration also avoids Chromium's practical multi-MB iframe URL limit.
    return (
        '<iframe id="explorerFrame" data-file="grasp_geometry_explorer_v0.html" '
        'title="E1.5 抓取候选几何浏览器" allowfullscreen></iframe>'
        '<script id="explorerPayload" type="application/octet-stream">'
        f'{payload}</script>')


def _video_cards(per_video):
    cards = []
    for fname, title, desc, diag in VIDEOS:
        stem = fname[:-4]
        tot, ok = per_video.get(stem, (0, 0))
        src = _data_uri(os.path.join(VIDEO_DIR, fname), "video/mp4")
        badge = (f'<span class="kfbadge">keyframe {ok}/{tot} exact</span>'
                 if tot else '<span class="kfbadge warn">no keyframe rows</span>')
        diag_tag = ('<span class="diagtag">DIAGNOSTIC — NOT GATE VALIDATED'
                    "</span> " if diag else "")
        cards.append(
            f'<div class="vidcard">'
            f'<video controls preload="metadata" data-file="{esc(fname)}" '
            f'src="{src}"></video>'
            f'<div class="vmeta"><b>{esc(title)}</b> {badge}<br>'
            f'{diag_tag}<span class="mut">{esc(desc)}</span></div></div>')
    return "\n".join(cards)


def _num_cards(nums):
    out = []
    for val, label, src in nums:
        out.append(f'<div class="numcard"><div class="numval">{esc(val)}</div>'
                   f'<div class="numlabel">{esc(label)}</div>'
                   f'<div class="numsrc">源: {esc(src)}</div></div>')
    return "\n".join(out)


def _matrix(rows):
    """72-cell grid: rows = grasp point x task mode, cols = t_c x v_app."""
    tcs = sorted({int(float(r["t_c_s"])) for r in rows})
    vs = sorted({float(r["v_app_mps"]) for r in rows})
    gps = sorted({r["grasp_point_id"] for r in rows})
    modes = ["pose_6d", "approach_5d"]
    by_key = {(r["grasp_point_id"], r["task_constraint_mode"],
               int(float(r["t_c_s"])), float(r["v_app_mps"])): r for r in rows}
    head = "<tr><th></th>" + "".join(
        f"<th>t{tc}<br>v{int(v * 1000)}</th>" for tc in tcs for v in vs) + "</tr>"
    body = []
    for gp in gps:
        for mode in modes:
            cells = []
            for tc in tcs:
                for v in vs:
                    r = by_key[(gp, mode, tc, v)]
                    cls = r["recount_class"]
                    binding = r["binding_items"].replace("reason:", "")
                    binding = ";".join(binding.split(";")[:3])
                    tip = (f"{r['case_id']} | hash {r['scenario_hash']} | "
                           f"{cls}")
                    cells.append(
                        f'<td><div class="cell" style="background:'
                        f'{COLORS[cls]}" title="{esc(tip)}" '
                        f'data-case="{esc(r["case_id"])}" '
                        f'data-hash="{esc(r["scenario_hash"])}" '
                        f'data-cls="{esc(cls)}" '
                        f'data-bind="{esc(binding)}" '
                        f'onmouseover="cellinfo(this)"></div></td>')
            body.append(f'<tr><th class="rowh">{esc(gp)}<br>'
                        f'<span class="mut">{esc(mode)}</span></th>'
                        + "".join(cells) + "</tr>")
    legend = " &nbsp; ".join(
        f'<span class="chip" style="background:{COLORS[k]}"></span>'
        f"{k}: {CLS_ZH[k]}" for k in
        ("PHYSICAL_LIMIT_EXCEEDED", "FLEX_SOLVER_UNKNOWN",
         "MISSING_FRESH_EVIDENCE", "VERIFIED_SAFE"))
    return (f'<table class="matrix">{head}{"".join(body)}</table>'
            f'<div id="cellpanel" class="mut">悬停任一格查看 case_id / '
            f"scenario_hash / 原因类</div>"
            f'<div class="legend">{legend}</div>')


def _tests_table(tests):
    rows = []
    for t in tests["expected_tests"]:
        ok = t in tests["passed_tests"]
        cls = "pass" if ok else "fail"
        rows.append(f"<tr><td>{esc(t)}</td>"
                    f'<td class="{cls}">{"PASS" if ok else "FAIL"}</td></tr>')
    return ('<table class="data slim"><thead><tr><th>功能回归</th><th>结果</th>'
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>")


def _line_cards(gate):
    text = {
        "A": ("真实几何 + 两阶段捕获", "接触/动量/能量残差全部 ≤1e-12 量级，"
              "72 工况哈希绑定完整"),
        "B": ("ANCF 数值可靠性", "15 条逐次求解记录完整；历史 retry 复核与 "
              "Top-3 BDF 复核未通过 → 重复 E1.5"),
        "C": ("MPCS / Pareto 有效性", "确定性重算全部通过，但名义 Top-3 为空 "
              "且阈值登记 PROVISIONAL → 重复 E1.5"),
    }
    out = []
    for k in "ABC":
        v = gate["lines"][k]
        color = "#4c9f70" if v == "PASS" else "#e0b400"
        out.append(f'<div class="linecard"><div class="linehead">证据线 {k} '
                   f'<span class="linebadge" style="background:{color}">{v}'
                   f"</span></div><b>{esc(text[k][0])}</b>"
                   f'<div class="mut">{esc(text[k][1])}</div></div>')
    return "\n".join(out)


def _claims():
    def col(title, items, klass):
        lis = "".join(f"<li>{esc(t)} <span class='src'>[{esc(s)}]</span></li>"
                      for t, s in items)
        return (f'<div class="claimcol {klass}"><h4>{esc(title)}</h4>'
                f"<ul>{lis}</ul></div>")
    return (col("可直接声明", CLAIMS_OK, "ok")
            + col("须带限定声明", CLAIMS_QUALIFIED, "qual")
            + col("禁止声明", CLAIMS_FORBIDDEN, "forbid"))


def _hash_table(rows):
    body = []
    for r in rows:
        ok = (r["match_expected"] == "True" and r["snapshot_hash_match"] == "True")
        cls = "pass" if ok else "fail"
        body.append(f"<tr><td>{esc(r['source_rel_path'])}</td>"
                    f"<td class='mono'>{esc(r['expected_sha256'][:16])}…</td>"
                    f'<td class="{cls}">{"一致" if ok else "不一致"}</td></tr>')
    return ('<div class="scrollbox short"><table class="data slim"><thead>'
            "<tr><th>E1.5 冻结证据（22 条）</th><th>sha256</th><th>快照校验</th>"
            f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>")


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<link rel="icon" href="data:,">
<title>项目可视化仪表板 v0 — PROJECT_FROZEN_AT_REPEAT_E1_5</title>
<style>
 * { box-sizing:border-box; }
 body { margin:0; font-family:"Microsoft YaHei","Segoe UI",sans-serif;
        background:#f5f6f8; color:#222; }
 header { background:#243447; color:#fff; padding:12px 22px; }
 header h1 { margin:0; font-size:19px; font-weight:600; }
 .banner { display:inline-block; background:#7d93b2; color:#fff;
   border-radius:4px; padding:2px 10px; font-size:12.5px; margin-top:6px; }
 .meta { font-size:11.5px; color:#b8c4d4; margin-top:5px; line-height:1.6; }
 .shipnote { background:#37475d; color:#dce4ee; font-size:11.5px;
   border-radius:4px; padding:4px 10px; margin-top:6px; display:inline-block; }
 nav { background:#fff; border-bottom:1px solid #d8dde4; padding:0 22px;
   display:flex; gap:4px; }
 nav button { border:none; background:none; padding:11px 18px; font-size:14px;
   cursor:pointer; border-bottom:3px solid transparent; color:#555; }
 nav button.on { color:#243447; font-weight:600; border-bottom-color:#243447; }
 section { display:none; padding:16px 22px; }
 section.on { display:block; }
 h3 { color:#243447; font-size:15px; margin:18px 0 8px; }
 .mut { color:#777; font-size:12px; }
 .figgrid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
   gap:12px; }
 .figcard { margin:0; background:#fff; border:1px solid #d8dde4;
   border-radius:6px; padding:8px; }
 .figcard img { width:100%; cursor:zoom-in; border-radius:3px; }
 .figcard figcaption { font-size:12px; margin-top:5px; line-height:1.45; }
 #lb { display:none; position:fixed; inset:0; background:rgba(15,20,28,.88);
   z-index:50; cursor:zoom-out; align-items:center; justify-content:center; }
 #lb img { max-width:94vw; max-height:94vh; }
 .scrollbox { overflow:auto; max-height:430px; background:#fff;
   border:1px solid #d8dde4; border-radius:6px; }
 .scrollbox.short { max-height:300px; }
 .scrollbox.framebox { max-height:360px; }
 table.data { border-collapse:collapse; font-size:11.5px; width:100%; }
 table.data th { position:sticky; top:0; background:#243447; color:#fff;
   padding:5px 7px; text-align:left; font-weight:500; }
 table.data td { padding:4px 7px; border-bottom:1px solid #eef0f3;
   vertical-align:top; }
 table.data.slim { width:auto; min-width:340px; background:#fff;
   border:1px solid #d8dde4; border-radius:6px; }
 td.pass { color:#2c7a4b; font-weight:600; }
 td.fail { color:#c8443c; font-weight:600; }
 .mono { font-family:Consolas,monospace; font-size:10.5px; }
 .vidgrid { display:grid; grid-template-columns:repeat(auto-fill,minmax(390px,1fr));
   gap:14px; }
 .vidcard { background:#fff; border:1px solid #d8dde4; border-radius:6px;
   padding:9px; }
 .vidcard video { width:100%; background:#000; border-radius:3px; }
 #explorerFrame { display:block; width:100%; height:760px; border:1px solid #d8dde4;
   border-radius:6px; background:#fff; }
 .contractnote { background:#eaf4ee; border:1px solid #b7d6c1; color:#244d31;
   border-radius:4px; padding:7px 10px; font-size:12px; line-height:1.5; }
 .vmeta { font-size:12.5px; margin-top:6px; line-height:1.5; }
 .kfbadge { background:#2c7a4b; color:#fff; border-radius:3px; font-size:10.5px;
   padding:1px 7px; margin-left:6px; }
 .kfbadge.warn { background:#c8443c; }
 .diagtag { background:#e0b400; color:#3a3000; border-radius:3px;
   font-size:10.5px; padding:1px 7px; font-weight:700; }
 .numrow { display:flex; gap:12px; flex-wrap:wrap; }
 .numcard { background:#fff; border:1px solid #d8dde4; border-radius:6px;
   padding:12px 16px; min-width:190px; flex:1; }
 .numval { font-size:22px; font-weight:700; color:#243447; }
 .numlabel { font-size:12px; margin-top:3px; line-height:1.4; }
 .numsrc { font-size:10.5px; color:#8a94a3; margin-top:5px;
   font-family:Consolas,monospace; }
 .evgrid { display:flex; gap:16px; flex-wrap:wrap; align-items:flex-start; }
 #donut { width:430px; height:360px; background:#fff;
   border:1px solid #d8dde4; border-radius:6px; }
 table.matrix { border-collapse:separate; border-spacing:2px; background:#fff;
   border:1px solid #d8dde4; border-radius:6px; padding:8px; }
 table.matrix th { font-size:10px; color:#555; font-weight:500;
   padding:1px 2px; }
 table.matrix th.rowh { text-align:right; padding-right:6px; }
 .cell { width:26px; height:22px; border-radius:2px; cursor:crosshair; }
 #cellpanel { margin-top:6px; font-family:Consolas,monospace; font-size:11px;
   background:#fff; border:1px solid #d8dde4; border-radius:4px;
   padding:6px 9px; min-height:2.4em; max-width:720px; }
 .legend { font-size:11px; margin-top:6px; line-height:1.8; max-width:760px; }
 .chip { display:inline-block; width:10px; height:10px; border-radius:2px;
   margin-right:4px; vertical-align:-1px; }
 .linerow { display:flex; gap:12px; flex-wrap:wrap; }
 .linecard { background:#fff; border:1px solid #d8dde4; border-radius:6px;
   padding:10px 14px; flex:1; min-width:230px; font-size:12.5px; }
 .linehead { font-weight:700; color:#243447; margin-bottom:4px; }
 .linebadge { color:#fff; border-radius:3px; padding:1px 8px; font-size:11px;
   margin-left:6px; }
 .claimrow { display:flex; gap:12px; flex-wrap:wrap; align-items:stretch; }
 .claimcol { flex:1; min-width:280px; background:#fff; border-radius:6px;
   border:1px solid #d8dde4; border-top:4px solid #999; padding:8px 12px; }
 .claimcol.ok { border-top-color:#4c9f70; }
 .claimcol.qual { border-top-color:#e0b400; }
 .claimcol.forbid { border-top-color:#c8443c; }
 .claimcol h4 { margin:4px 0 6px; font-size:13.5px; color:#243447; }
 .claimcol ul { margin:0; padding-left:18px; font-size:12px; line-height:1.55; }
 .claimcol li { margin-bottom:7px; }
 .src { color:#8a94a3; font-size:10.5px; }
 footer { padding:14px 22px 26px; font-size:11.5px; color:#555;
   border-top:1px solid #d8dde4; background:#fff; line-height:1.7; }
</style>
<script>__PLOTLYJS__</script>
</head>
<body>
<header>
 <h1>中国研究生未来飞行器创新大赛 · 空间碎片捕获—稳定一体化 — 项目可视化仪表板 v0</h1>
 <div><span class="banner">__BANNER__</span></div>
 <div class="shipnote">真正单文件自包含：交互三维浏览器、10 张图、6 段 MP4 与 Plotly
  均已内嵌；可直接双击本 HTML，以 file:// 打开，无需本地服务器或旁车目录。</div>
 <div class="meta">源码/数据基线提交 <b>__COMMIT__</b> ｜ 生成时间戳 = HEAD 提交时间
  __COMMIT_DATE__（取自 git，确定性，非墙钟） ｜ E1.5 证据源提交 7de78a2 ｜
  语义红线：UNKNOWN ≠ 不安全 · 证据缺失 ≠ 物理不安全 · 无 SAFE 候选 / Top-3 声明 ·
  柔性内容一律 DIAGNOSTIC</div>
</header>
<nav>
 <button id="tab-geo" class="on" onclick="mode('geo')">Geometry Mode 几何</button>
 <button id="tab-dyn" onclick="mode('dyn')">Dynamics Mode 动力学</button>
 <button id="tab-evi" onclick="mode('evi')">Evidence Mode 证据</button>
</nav>

<section id="sec-geo" class="on">
 <h3>统一三维场景与候选联动（可旋转 / 缩放 / 筛选）</h3>
 <p class="contractnote">下方交互视图已嵌入本文件。P1/P2/P3 属于
  <b>target_debris_v0（D 系）</b>的 E1/E1.5 候选；22 kg 合作目标卫星使用自身
  CAD 抓点，二者不会混画。几何失败与动力学证据状态分两行显示。</p>
 __EXPLORER__
 <h3>坐标系登记（frame_registry_v1.csv，__N_FRAMES__ 行）</h3>
 <p class="mut">SSOT 命名：B = 自由漂浮母体基座；M = B601 安装面 / URDF 基准。
  静态表采用 t=0 参考；I→S 的动态姿态由 sim_05 回放提供。</p>
 __FRAME_TABLE__
 <h3>静态图 v01–v10（点击放大）</h3>
 <div class="figgrid">__FIGCARDS__</div>
 <h3>资产清单（asset_audit.csv，__N_ASSETS__ 行）</h3>
 __ASSET_TABLE__
</section>

<section id="sec-dyn">
 <h3>回放视频（6 段，关键帧数字全部与真值 CSV 核对：__KF_TOTAL__）</h3>
 <div class="vidgrid">__VIDCARDS__</div>
 <h3>关键数字（构建时从源 CSV 重读）</h3>
 <div class="numrow">__NUMCARDS__</div>
 <p class="mut">注：19.20° 为 B601 混合模型口径的动力学基准（q2 超 URDF 限位，非飞行轨迹）；
 所有阈值 PROVISIONAL。</p>
</section>

<section id="sec-evi">
 <h3>72 工况证据状态（四类原因重算，evidence_recount.csv）</h3>
 <div class="evgrid">
  <div id="donut"></div>
  <div>__MATRIX__</div>
 </div>
 <h3>功能回归 t1–t11 与证据线裁决</h3>
 <div class="evgrid">
  __TESTS_TABLE__
  <div class="linerow" style="flex:1; min-width:340px;">__LINECARDS__</div>
 </div>
 <h3>声明台账（逐条与 00_repo_truth_audit_20260711.md / sim_09_gate_e15_report.md 核对）</h3>
 <div class="claimrow">__CLAIMS__</div>
 <h3>E1.5 冻结证据快照哈希（22 条，Stage 0 校验）</h3>
 __HASHTABLE__
</section>

<div id="lb" onclick="this.style.display='none'"><img id="lbimg" alt=""></div>

<footer>
 <b>数据源清单：</b>__SOURCES__<br>
 <b>scenario_hash 说明：</b>每个工况的 scenario_hash 是 E1.5 运行器对完整场景参数
 （目标/抓点/捕获相位 t_c/接近速度/任务约束模式/末端 roll/惯量等）的确定性哈希，
 用于把每条证据行绑定到唯一场景；E1.5 的哈希包含 roll 参数化，同名 case 与 E1 哈希不同。<br>
 <b>源提交链：</b>7de78a2（E1.5 证据） → e89989b（E1 冻结基线） → 7371403（VIZ Stage 0 快照）
 → 9763a2d（VIZ Stage 1–2） → ae87f34（VIZ Stage 3–5） → 本页构建于 __COMMIT__。
</footer>

<script>
function mode(m){
  for (const k of ["geo","dyn","evi"]){
    document.getElementById("sec-"+k).classList.toggle("on", k===m);
    document.getElementById("tab-"+k).classList.toggle("on", k===m);
  }
}
function hydrateExplorer(){
  const frame = document.getElementById("explorerFrame");
  const payload = document.getElementById("explorerPayload").textContent.trim();
  const binary = atob(payload);
  const bytes = Uint8Array.from(binary, ch => ch.charCodeAt(0));
  const source = new TextDecoder("utf-8").decode(bytes);
  const doc = frame.contentWindow.document;
  doc.open();
  doc.write(source);
  doc.close();
}
function lightbox(img){
  document.getElementById("lbimg").src = img.src;
  document.getElementById("lb").style.display = "flex";
}
function cellinfo(el){
  document.getElementById("cellpanel").textContent =
    el.dataset.case + "  |  scenario_hash " + el.dataset.hash +
    "  |  " + el.dataset.cls + "  |  " + el.dataset.bind;
}
Plotly.newPlot("donut", [{
  type:"pie", hole:0.55, sort:false, direction:"clockwise",
  values:__DONUT_VALUES__, labels:__DONUT_LABELS__,
  marker:{colors:__DONUT_COLORS__},
  textinfo:"label+value", textposition:"outside",
  hovertemplate:"%{label}: %{value} 例<extra></extra>"
}], {
  title:{text:"证据状态四类分解（n=72）", font:{size:13}},
  margin:{t:44,l:18,r:18,b:14}, showlegend:false,
  annotations:[{text:"admissible __ADMISSIBLE__<br>gate __GATE__",
    showarrow:false, font:{size:12}}]
}, {displaylogo:false, staticPlot:false});
hydrateExplorer();
</script>
</body>
</html>
"""


def build_dashboard(verbose=True):
    from plotly.offline import get_plotlyjs

    gate = load_gate()
    n_adm, n_cases = count_admissible()
    rec_rows, tally = load_recount()
    per_video, kf_total, kf_matched = load_keyframes()
    assets = load_assets()
    frames = load_frames()
    hashes = load_snapshot_hashes()
    nums = key_numbers()
    commit = vb.repo_commit_short()

    tests = gate["tests"]
    n_t = len(tests["expected_tests"])
    n_tp = len([t for t in tests["expected_tests"]
                if t in tests["passed_tests"]])
    banner = (f"PROJECT_FROZEN_AT_{gate['gate']} | admissible {n_adm}/{n_cases}"
              f" | Line A {gate['lines']['A']} / B {gate['lines']['B']} / "
              f"C {gate['lines']['C']} | t1–t{n_t} "
              f"{'PASS' if n_tp == n_t else f'{n_tp}/{n_t}'}")

    order = ["PHYSICAL_LIMIT_EXCEEDED", "FLEX_SOLVER_UNKNOWN",
             "MISSING_FRESH_EVIDENCE", "VERIFIED_SAFE"]
    donut_labels = [f"{k}: {tally[k]}" for k in order]

    sources = esc("; ".join([
        "40_evidence/artifacts/visualization/tables/asset_audit.csv",
        "40_evidence/artifacts/visualization/tables/frame_registry_v1.csv",
        "40_evidence/artifacts/visualization/tables/evidence_recount.csv",
        "40_evidence/artifacts/visualization/tables/replay_keyframe_check.csv",
        "40_evidence/artifacts/visualization/tables/gate_artifact_protection_manifest.csv",
        "40_evidence/artifacts/visualization/e15_gate_evidence_snapshot_20260714/ (22 文件)",
        "30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv",
        "30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv",
        "30_simulation/sim_08_detumble_actuator_budget/results/actuator_budget_sweep.csv",
        "40_evidence/artifacts/visualization/figures/fig_v01..v10.png (base64 内嵌)",
        "40_evidence/artifacts/visualization/grasp_geometry_explorer_v0.html (交互载荷内嵌；复用父页内联 Plotly)",
        "40_evidence/artifacts/visualization/videos/anim_v01..v06.mp4 (base64 内嵌)",
        "01_project/competition/00_repo_truth_audit_20260711.md (声明台账依据)",
        "快照 sim_09_gate_e15_report.md (声明台账依据)",
    ]))

    page = (PAGE
            .replace("__PLOTLYJS__", get_plotlyjs())
            .replace("__BANNER__", esc(banner))
            .replace("__COMMIT_DATE__", esc(git_head_date()))
            .replace("__COMMIT__", esc(commit))
            .replace("__EXPLORER__", _explorer_embed())
            .replace("__N_FRAMES__", str(len(frames)))
            .replace("__FRAME_TABLE__", _frame_table(frames))
            .replace("__FIGCARDS__", _fig_cards())
            .replace("__N_ASSETS__", str(len(assets)))
            .replace("__ASSET_TABLE__", _asset_table(assets))
            .replace("__KF_TOTAL__", f"{kf_matched}/{kf_total} exact")
            .replace("__VIDCARDS__", _video_cards(per_video))
            .replace("__NUMCARDS__", _num_cards(nums))
            .replace("__MATRIX__", _matrix(rec_rows))
            .replace("__TESTS_TABLE__", _tests_table(tests))
            .replace("__LINECARDS__", _line_cards(gate))
            .replace("__CLAIMS__", _claims())
            .replace("__HASHTABLE__", _hash_table(hashes))
            .replace("__SOURCES__", sources)
            .replace("__DONUT_VALUES__", json.dumps([tally[k] for k in order]))
            .replace("__DONUT_LABELS__", json.dumps(donut_labels))
            .replace("__DONUT_COLORS__", json.dumps([COLORS[k] for k in order]))
            .replace("__ADMISSIBLE__", f"{n_adm}/{n_cases}")
            .replace("__GATE__", esc(gate["gate"])))

    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(page)
    size_mb = os.path.getsize(OUT_HTML) / 1e6

    # ---- strict single-file scan -----------------------------------------
    # Scripts must be INLINE.  Script bodies are stripped before scanning
    # markup because the inlined Plotly bundle contains harmless src/href
    # strings in JS literals.  Every actual markup fetch target must be a
    # data URI (or an in-document fragment); relative sidecars are forbidden.
    bad_targets = [m.group(0) for m in
                   re.finditer(r"<script\b[^>]*\bsrc\s*=", page)]
    markup = re.sub(r"<script\b[^>]*>.*?</script>", "<script></script>",
                    page, flags=re.S)
    targets = [m.group(1).strip() for m in re.finditer(
        r'(?:src|href)\s*=\s*["\']([^"\']*)["\']', markup)]
    bad_targets += [u[:160] for u in targets
                    if u and not (u.startswith("data:") or u.startswith("#"))]
    for pat in (r'@import\s+url\(\s*["\']?https?://',
                r'url\(\s*["\']?https?://'):
        bad_targets += [m.group(0) for m in re.finditer(pat, markup)]
    report = {"path": OUT_HTML, "size_mb": round(size_mb, 2),
              "external_refs": bad_targets,
              "self_contained": not bad_targets,
              "fetch_targets": len(targets),
              "figures_embedded": len(FIGURES),
              "videos_embedded": len(VIDEOS),
              "explorer_embedded": True,
              "explorer_embed_mode": "inline_runtime_payload_shared_plotly",
              "keyframe_badge": f"{kf_matched}/{kf_total}",
              "banner": banner}
    if verbose:
        print(f"dashboard written: {os.path.relpath(OUT_HTML, REPO)}")
        print(f"  size: {size_mb:.2f} MB | figures embedded: {len(FIGURES)} | "
              f"videos embedded: {len(VIDEOS)} | explorer embedded: yes")
        print(f"  banner: {banner}")
        print(f"  self-contained: {report['self_contained']} "
              f"(non-data fetch targets: {bad_targets or 'none'})")
    if bad_targets:
        raise SystemExit(f"self-containment scan FAILED: {bad_targets}")
    return report


# ============================================================== full chain
def _steps():
    """(name, expected outputs, thunk) for the --all chain."""
    def s1():
        import asset_audit
        asset_audit.main()
        import frame_registry
        frame_registry.main()

    def s2():
        import make_figures
        make_figures.main()

    def s3():
        import evidence_recount
        res = evidence_recount.recount(write=True)
        assert res["matches_expected"], res["tally"]
        import evidence_figures
        evidence_figures.fig_v07()
        evidence_figures.fig_v08()
        evidence_figures.fig_v09()
        evidence_figures.fig_v10()

    def s4():
        import grasp_explorer_builder
        rep = grasp_explorer_builder.build_html()
        assert rep["self_contained"], rep

    def s5():
        import make_replay_videos
        make_replay_videos.run()

    def s6():
        build_dashboard()

    def s7():
        rc = subprocess.call([sys.executable,
                              os.path.join(REPO, "70_tools", "project_visualization", "tests",
                                           "run_all.py")])
        if rc != 0:
            raise SystemExit(f"acceptance suite failed (exit {rc})")

    return [
        ("1. asset_audit + frame_registry (stage 1)", s1,
         ["40_evidence/artifacts/visualization/tables/asset_audit.csv",
          "40_evidence/artifacts/visualization/tables/frame_registry_v1.csv"]),
        ("2. make_figures         (stage 2, v01-v06)", s2,
         [f"40_evidence/artifacts/visualization/figures/fig_v0{i}_" for i in range(1, 7)]),
        ("3. evidence_recount + evidence_figures (stage 5, v07-v10)", s3,
         ["40_evidence/artifacts/visualization/tables/evidence_recount.csv",
          "40_evidence/artifacts/visualization/figures/fig_v07_", "40_evidence/artifacts/visualization/figures/fig_v08_",
          "40_evidence/artifacts/visualization/figures/fig_v09_", "40_evidence/artifacts/visualization/figures/fig_v10_"]),
        ("4. grasp_explorer_builder (stage 3)", s4,
         ["40_evidence/artifacts/visualization/grasp_geometry_explorer_v0.html"]),
        ("5. make_replay_videos   (stage 4, ~30 min render)", s5,
         [f"40_evidence/artifacts/visualization/videos/anim_v0{i}_" for i in range(1, 7)]
         + ["40_evidence/artifacts/visualization/tables/replay_keyframe_check.csv"]),
        ("6. build_dashboard      (stage 6, this module)", s6,
         ["40_evidence/artifacts/visualization/project_visualization_v0.html"]),
        ("7. acceptance tests     (70_tools/project_visualization/tests/run_all.py)", s7,
         ["70_tools/project_visualization/tests/viz_gate0_test_report.md"]),
    ]


def _output_exists(prefix):
    """True if the expected output (file or file-prefix) exists on disk."""
    p = os.path.join(REPO, prefix)
    if os.path.isfile(p):
        return True
    d, base = os.path.dirname(p), os.path.basename(p)
    if os.path.isdir(d):
        return any(fn.startswith(base) for fn in os.listdir(d))
    return False


def run_all(dry_run=False):
    steps = _steps()
    print(f"one-click rebuild chain ({'DRY-RUN' if dry_run else 'EXECUTE'}, "
          f"{len(steps)} steps):")
    ok = True
    for name, thunk, outputs in steps:
        if dry_run:
            missing = [o for o in outputs if not _output_exists(o)]
            state = "outputs present" if not missing else \
                f"MISSING: {missing}"
            print(f"  [dry] {name} -> {state}")
            ok = ok and not missing
        else:
            print(f"  [run] {name}")
            thunk()
    if dry_run:
        print(f"dry-run chain check: {'ALL OUTPUTS PRESENT' if ok else 'GAPS FOUND'}")
        return ok
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="VIZ-Gate 0 dashboard builder / one-click rebuild")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true",
                   help="full chain: audit->figures->recount->explorer->"
                        "videos->dashboard->tests")
    g.add_argument("--dashboard-only", action="store_true",
                   help="rebuild only the dashboard from artifacts on disk "
                        "(default)")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --all: print/validate the chain, execute nothing")
    args = ap.parse_args(argv)

    if args.all:
        return 0 if run_all(dry_run=args.dry_run) else 1
    build_dashboard()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
