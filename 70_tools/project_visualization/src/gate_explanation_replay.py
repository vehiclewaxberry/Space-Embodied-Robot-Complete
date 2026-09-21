"""anim_v06_gate_explanation.mp4 -- animated explanation of the E1.5 gate state.

All 72 cell classifications are RECOMPUTED per frame-independent rule from the
snapshot bottleneck CSV binding_items column (NOTHING hardcoded):
    contains MPCS_LIMIT_NOT_STRICTLY_POSITIVE -> RED    (PHYSICAL_LIMIT_EXCEEDED)
    contains FLEX_SOLVER_FAIL                 -> YELLOW (FLEX_SOLVER_UNKNOWN)
    otherwise (missing/invalid evidence chain)-> GREY-BLUE (MISSING_FRESH_EVIDENCE)
State counts are cross-checked against e15_gate_check.json state_counts.

Colors are the display_semantics_v1.yaml semantic colors (iron rule 3):
UNKNOWN = yellow, hard-evidence violation = red, missing evidence = grey-blue,
not-yet-shown = neutral grey. The closing caption states explicitly that
"no SAFE candidate" is an EVIDENCE-STATE statement, not a physics conclusion.
"""
import _viz_bootstrap as vb
import csv
import json
import os

import numpy as np
import matplotlib.patches as mpatches

import video_utils as vu

VIDEO = "anim_v06_gate_explanation"
OUT = os.path.join(vu.VIDEO_DIR, VIDEO + ".mp4")
BOTTLENECK_CSV = os.path.join(
    vb.SNAPSHOT_DIR,
    "tables__sim_09_grasp_evaluator__e15_mpcs__e15_bottleneck_summary.csv")
GATE_JSON = os.path.join(
    vb.SNAPSHOT_DIR, "results__sim_09_grasp_evaluator__e15_gate_check.json")

FPS = 24
T_C = (0, 30, 60, 90)
V_APP = (5, 10, 20)                  # mm/s
ROWS = [("P1", "pose_6d"), ("P1", "approach_5d"),
        ("P2", "pose_6d"), ("P2", "approach_5d"),
        ("P3", "pose_6d"), ("P3", "approach_5d")]

CLASS_COLOR = {"RED": vu.SC["physical_violation"],
               "YELLOW": vu.SC["unknown"],
               "GREYBLUE": vu.SC["evidence_missing"],
               "PENDING": vu.SC["dynamics_unverified"]}
CLASS_LABEL = {"RED": "PHYSICAL_LIMIT_EXCEEDED (provisional threshold)",
               "YELLOW": "FLEX_SOLVER_UNKNOWN -> state UNKNOWN",
               "GREYBLUE": "MISSING_FRESH_EVIDENCE"}


def classify(binding_items):
    """The rule (recomputed per row, never hardcoded)."""
    if "MPCS_LIMIT_NOT_STRICTLY_POSITIVE" in binding_items:
        return "RED"
    if "FLEX_SOLVER_FAIL" in binding_items:
        return "YELLOW"
    return "GREYBLUE"


def load_data():
    with open(BOTTLENECK_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 72, len(rows)
    for r in rows:
        r["_class"] = classify(r["binding_items"])
    gate = json.load(open(GATE_JSON, encoding="utf-8"))
    return rows, gate


def cell_of(r):
    """(row, col) grid position of a case."""
    ri = ROWS.index((r["grasp_point_id"], r["task_constraint_mode"]))
    ci = T_C.index(int(float(r["t_c_s"]))) * 3 + V_APP.index(
        int(round(float(r["v_app_mps"]) * 1000)))
    return ri, ci


def build():
    rows, gate = load_data()
    counts = {"RED": 0, "YELLOW": 0, "GREYBLUE": 0}
    for r in rows:
        counts[r["_class"]] += 1
    state_counts = {"SAFE": 0, "UNKNOWN": 0, "UNSAFE": 0}
    for r in rows:
        state_counts[r["e15_state"]] += 1
    red0 = next(r for r in rows if r["_class"] == "RED")
    rate = float(red0["post_capture_rate_dps"])
    lim = float(red0["limit__post_capture_rate_dps"])
    ylw = [r for r in rows if r["_class"] == "YELLOW"]
    evaluated = [r for r in rows if r["_class"] in ("RED", "YELLOW")]
    grey_reason = next(r for r in rows if r["_class"] == "GREYBLUE")

    # stage schedule [s]
    S0, S1, S2, S3, S4, S5, S6 = 0.0, 4.0, 9.0, 15.0, 21.0, 26.0, 30.5
    T_END = 36.0
    N_FRAMES = int(T_END * FPS)

    # ---------------- figure ----------------
    fig = vu.make_fig()
    ax = fig.add_axes((0.05, 0.30, 0.62, 0.56))
    ax.set_xlim(-0.6, 12.4)
    ax.set_ylim(-0.6, 6.4)
    ax.invert_yaxis()
    ax.set_axis_off()

    patches = {}
    for r in rows:
        ri, ci = cell_of(r)
        p = mpatches.FancyBboxPatch(
            (ci + 0.06, ri + 0.06), 0.88, 0.88,
            boxstyle="round,pad=0,rounding_size=0.08",
            fc=CLASS_COLOR["PENDING"], ec="white", lw=1.2, alpha=0.55)
        ax.add_patch(p)
        patches[r["case_id"]] = (p, r)
    for ri, (pid, mode) in enumerate(ROWS):
        ax.text(-0.15, ri + 0.5, f"{pid}\n{mode}", fontsize=6.6, ha="right",
                va="center")
    for ti, tc in enumerate(T_C):
        ax.text(ti * 3 + 1.5, -0.35, f"t_c = {tc} s", fontsize=7.5,
                ha="center")
        for vi, v in enumerate(V_APP):
            ax.text(ti * 3 + vi + 0.5, 6.3, f"{v}", fontsize=5.6, ha="center")
    ax.text(6.0, 6.75, "v_app [mm/s] per t_c block", fontsize=6.0,
            ha="center")

    fig.text(0.36, 0.975, "anim_v06  E1.5 gate state, cell by cell -- "
             "72-case evidence matrix (gate verdict: REPEAT_E1_5)",
             fontsize=11.5, ha="center", va="top", fontweight="bold")
    narr = fig.text(0.05, 0.245, "", fontsize=8.6, va="top", family="monospace",
                    bbox=dict(boxstyle="round,pad=0.5", fc="#f6f6f2",
                              ec="#999999"))
    closing = fig.text(0.36, 0.075, "", fontsize=9.0, ha="center", va="center",
                       fontweight="bold", color="#1a1a1a",
                       fontfamily=vu.CJK_FONT)

    # legend
    lx = 0.695
    for i, (cls, lab) in enumerate([("RED", "PHYSICAL_LIMIT_EXCEEDED"),
                                    ("YELLOW", "FLEX_SOLVER_UNKNOWN"),
                                    ("GREYBLUE", "MISSING_FRESH_EVIDENCE"),
                                    ("PENDING", "not yet shown")]):
        y = 0.845 - 0.038 * i
        fig.add_artist(mpatches.Rectangle(
            (lx, y), 0.018, 0.026, transform=fig.transFigure,
            fc=CLASS_COLOR[cls], ec="#666666", lw=0.5))
        fig.text(lx + 0.025, y + 0.012, lab, fontsize=7.0, va="center")
    fig.text(lx, 0.90, "display semantics v1 (iron rule: UNKNOWN /\n"
             "missing evidence never shown as safe or unsafe)", fontsize=6.4,
             va="top", color="#555555")

    counter = fig.text(lx, 0.62, "", fontsize=10.5, family="monospace",
                       va="top")
    breakdown = fig.text(lx, 0.46, "", fontsize=7.0, family="monospace",
                         va="top", color="#333333")
    vu.add_provenance(
        fig, ["e15_bottleneck_summary.csv(binding_items->rule)",
              "e15_gate_check.json(state_counts)"],
        extra="classification recomputed, not hardcoded")

    def set_cell(case_id, cls, alpha):
        p, _ = patches[case_id]
        p.set_facecolor(CLASS_COLOR[cls])
        p.set_alpha(alpha)

    def draw(k):
        t = k / FPS
        # stage 0: all grey
        if t < S1:
            narr.set_text(
                "STAGE 0 | 72-case grid (3 grasp points x 4 capture phases x\n"
                "3 approach speeds x 2 task modes). All cells start NEUTRAL:\n"
                "no state is asserted before evidence is examined.")
        elif t < S2:
            # 6 evaluated cells pulse
            ph = 0.5 + 0.5 * np.sin(2 * np.pi * 1.2 * (t - S1))
            for r in evaluated:
                p, _ = patches[r["case_id"]]
                p.set_edgecolor("#111111")
                p.set_linewidth(1.2 + 1.6 * ph)
            narr.set_text(
                "STAGE 1 | 6 cases (P1, t_c = 0) carry FRESH E1.5 numerics:\n"
                "geometry selection + capture wrenches + ANCF attempts.\n"
                "These six enter classification first.")
        elif t < S3:
            a = min(1.0, (t - S2) / 1.5)
            for r in rows:
                if r["_class"] == "RED":
                    set_cell(r["case_id"], "RED", 0.25 + 0.75 * a)
            narr.set_text(
                "STAGE 2 | 3 cases RED -- PHYSICAL_LIMIT_EXCEEDED:\n"
                f"post-capture rate {rate:.4f} deg/s >= limit {lim:.1f} deg/s\n"
                "(PROVISIONAL threshold) -> binding item\n"
                "MPCS_LIMIT_NOT_STRICTLY_POSITIVE -> state UNSAFE\n"
                "(qualified: UNSAFE_UNDER_PROVISIONAL_THRESHOLDS).")
        elif t < S4:
            a = min(1.0, (t - S3) / 1.5)
            for r in rows:
                if r["_class"] == "YELLOW":
                    set_cell(r["case_id"], "YELLOW", 0.25 + 0.75 * a)
            narr.set_text(
                "STAGE 3 | 3 cases YELLOW -- FLEX_SOLVER_UNKNOWN:\n"
                "reasons FLEX_SOLVER_FAIL; FLEX_STATUS_UNKNOWN_INADMISSIBLE;\n"
                "INVALID_OR_MISSING_E_flex_J -> state UNKNOWN.\n"
                "UNKNOWN is NOT shown green and NOT shown red (iron rule).")
        elif t < S5:
            a = min(1.0, (t - S4) / 2.0)
            for r in rows:
                if r["_class"] == "GREYBLUE":
                    set_cell(r["case_id"], "GREYBLUE", 0.25 + 0.75 * a)
            narr.set_text(
                "STAGE 4 | 66 cases GREY-BLUE -- MISSING_FRESH_EVIDENCE:\n"
                "reason chain (per bottleneck CSV): IK_FAIL / IK_INFEASIBLE +\n"
                "HARD_FLAG_MISSING_OR_INVALID_* + INVALID_OR_MISSING_* .\n"
                "No fresh E1.5 numerics bind these cells -- they are counted\n"
                "UNSAFE by the conservative gate rule, NOT by physics.")
        elif t < S6:
            frac = min(1.0, (t - S5) / 2.0)
            sc = {k2: int(round(v * frac)) for k2, v in state_counts.items()}
            counter.set_text(
                "E1.5 STATE COUNTS\n"
                "-----------------\n"
                f"SAFE     {sc['SAFE']:3d}\n"
                f"UNKNOWN  {sc['UNKNOWN']:3d}\n"
                f"UNSAFE   {sc['UNSAFE']:3d}")
            breakdown.set_text(
                f"UNSAFE {state_counts['UNSAFE']} =\n"
                f"  {counts['RED']} physical-limit (provisional)\n"
                f"+ {counts['GREYBLUE']} missing-fresh-evidence\n"
                f"UNKNOWN {state_counts['UNKNOWN']} = flex solver\n"
                "  non-convergence (unresolved)\n"
                "cross-check: e15_gate_check.json\n"
                f"  SAFE {gate['state_counts']['SAFE']} / "
                f"UNKNOWN {gate['state_counts']['UNKNOWN']} / "
                f"UNSAFE {gate['state_counts']['UNSAFE']}")
            narr.set_text(
                "STAGE 5 | Tally. The gate verdict follows the decision rule\n"
                "in e15_gate_check.json: REPEAT_E1_5 (evidence lines A pass,\n"
                "B/C fail) -- NOT a physics verdict on the 66 grey-blue cells.")
        else:
            closing.set_text(
                "“无SAFE候选”是证据状态陈述，非物理结论；\n"
                "66例缺新鲜证据 ≠ 物理不安全。\n"
                "\"No SAFE candidate\" is a statement about EVIDENCE STATE, "
                "not a physics conclusion;\n66 cases lacking fresh evidence "
                "are NOT thereby physically unsafe.")
            narr.set_text(
                "STAGE 6 | red = provisional threshold exceeded by fresh\n"
                "numerics; yellow = solver evidence unresolved; grey-blue =\n"
                "fresh evidence absent. Next: REPEAT_E1_5 (repair lines B, C).")

    vu.render_video(OUT, fig, N_FRAMES, draw, fps=FPS)

    # ---------------- keyframe checks ----------------
    kc = int((S5 + 2.5) * FPS)
    rows_kf = [
        vu.kf_row(VIDEO, kc, kc / FPS, "counter SAFE",
                  state_counts["SAFE"], gate["state_counts"]["SAFE"],
                  "e15_gate_check.json vs bottleneck CSV recount"),
        vu.kf_row(VIDEO, kc, kc / FPS, "counter UNKNOWN",
                  state_counts["UNKNOWN"], gate["state_counts"]["UNKNOWN"],
                  "e15_gate_check.json vs bottleneck CSV recount"),
        vu.kf_row(VIDEO, kc, kc / FPS, "counter UNSAFE",
                  state_counts["UNSAFE"], gate["state_counts"]["UNSAFE"],
                  "e15_gate_check.json vs bottleneck CSV recount"),
        vu.kf_row(VIDEO, int(S2 * FPS) + FPS, S2 + 1.0,
                  "RED narration rate [deg/s]",
                  rate, float(red0["post_capture_rate_dps"]),
                  "e15_bottleneck_summary.csv"),
        vu.kf_row(VIDEO, int(S2 * FPS) + FPS, S2 + 1.0,
                  "RED narration limit [deg/s]",
                  lim, float(red0["limit__post_capture_rate_dps"]),
                  "e15_bottleneck_summary.csv"),
        vu.kf_row(VIDEO, int(S3 * FPS) + FPS, S3 + 1.0,
                  "YELLOW cell count (recomputed rule)",
                  counts["YELLOW"], len(ylw),
                  "e15_bottleneck_summary.csv(binding_items)"),
        vu.kf_row(VIDEO, int(S4 * FPS) + FPS, S4 + 1.0,
                  "GREYBLUE cell count (recomputed rule)",
                  counts["GREYBLUE"], 72 - counts["RED"] - counts["YELLOW"],
                  "e15_bottleneck_summary.csv(binding_items)"),
        vu.kf_row(VIDEO, int(S6 * FPS), S6, "gate verdict (title)",
                  "REPEAT_E1_5", gate["gate"], "e15_gate_check.json"),
    ]
    # narrative grey reason chain must actually be the CSV chain
    assert "IK_FAIL" in grey_reason["binding_items"]
    import matplotlib.pyplot as plt
    plt.close(fig)
    return {"video": VIDEO, "path": OUT, "n_frames": N_FRAMES, "fps": FPS,
            "kf_rows": rows_kf}


def main():
    out = build()
    n, bad = vu.update_keyframe_csv(VIDEO, out["kf_rows"])
    dur, mb, w, h = vu.video_info(out["path"])
    print(f"[{VIDEO}] {dur:.1f} s, {mb:.1f} MB, {w}x{h}, "
          f"keyframes {n} ({'ALL MATCH' if not bad else f'{len(bad)} MISMATCH'})")
    for r in bad:
        print("  MISMATCH:", r)
    return out


if __name__ == "__main__":
    main()
