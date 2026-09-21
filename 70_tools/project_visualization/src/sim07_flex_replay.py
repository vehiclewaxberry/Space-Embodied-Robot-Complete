"""VIZ-Gate 0 v05 -- read-only flexible-response evidence replay.

This renderer consumes only already-existing sim_07 summary/plot artifacts and
the frozen E1.5 failure records.  It does not execute any flexible-dynamics
model.  Because no nodal time history is archived, it deliberately renders a
diagnostic evidence reel rather than inventing a deformation animation.
"""
import _viz_bootstrap as vb  # noqa: F401  (environment pins before numpy)

import csv
import os

import numpy as np
from PIL import Image

import video_utils as vu


VIDEO = "anim_v05_flex_diagnostic"
OUT = os.path.join(vu.VIDEO_DIR, VIDEO + ".mp4")
FPS = 24
N_FRAMES = 28 * FPS

SIM07_RESULTS = os.path.join(
    vb.REPO_ROOT, "sim", "sim_07_ancf_flexible", "results")
SUMMARY_CSV = os.path.join(SIM07_RESULTS, "task_response_summary.csv")
TIP_PNG = os.path.join(SIM07_RESULTS, "tip_response_matrix.png")
ROOT_PNG = os.path.join(SIM07_RESULTS, "root_moment_and_energy.png")
FORENSICS_CSV = os.path.join(
    vb.SNAPSHOT_DIR,
    "results__sim_09_grasp_evaluator__e15_ancf_legacy_retry_forensics.csv")

FAIL_CASES = [
    "P3_tc30_v10mm_approach_5d",
    "P3_tc60_v5mm_approach_5d",
]


def _read_sources():
    with open(SUMMARY_CSV, encoding="utf-8", newline="") as f:
        summary = next(
            r for r in csv.DictReader(f)
            if r["capture_mode"] == "6dof_rigid_lock"
            and r["ei_case"] == "nominal")
    with open(FORENSICS_CSV, encoding="utf-8", newline="") as f:
        rows = {r["case_id"]: r for r in csv.DictReader(f)}
    failures = [rows[c] for c in FAIL_CASES]
    for r in failures:
        assert r["historical_flex_status"] == "FLEX_SOLVER_FAIL", r
        assert r["atomic_status"] == "UNKNOWN_INADMISSIBLE", r
    for p in (TIP_PNG, ROOT_PNG):
        if not os.path.isfile(p):
            raise FileNotFoundError(p)
    return summary, failures


def _metric_text(r):
    return (
        "EXISTING SUMMARY ROW\n"
        "6dof_rigid_lock / nominal\n\n"
        f"EI             {float(r['EI_Nm2']):.7g} N m2\n"
        f"f1             {float(r['f1_hz']):.5f} Hz\n"
        f"tip peak       {float(r['tip_peak_mm']):.6f} mm\n"
        f"root moment    {float(r['Mroot_peak_mNm']):.6f} mN m\n"
        f"U max          {float(r['U_max_J']):.5g} J\n"
        f"dominant f     {float(r['f_dom_hz']):.4f} Hz\n"
        f"t5%            {float(r['t5pct_s']):.2f} s\n"
        f"method         {r['t5_method']}\n\n"
        "READ-ONLY EXISTING DATA\n"
        "ANCF executions in this build: 0")


def build():
    summary, failures = _read_sources()
    tip = np.asarray(Image.open(TIP_PNG).convert("RGB"))
    root = np.asarray(Image.open(ROOT_PNG).convert("RGB"))

    fig = vu.make_fig(facecolor="#f5f7fa")
    title = fig.text(0.025, 0.965, "v05 · Flexible-response evidence reel",
                     fontsize=17, fontweight="bold", va="top",
                     color="#172033", zorder=20)
    status = fig.text(
        0.025, 0.915,
        "READ-ONLY EXISTING ARTIFACTS · NO FLEXIBLE-DYNAMICS EXECUTION DURING BUILD",
        fontsize=9.2, fontweight="bold", color="#9b5a00", va="top",
        zorder=20)

    ax_img = fig.add_axes([0.025, 0.085, 0.695, 0.79], zorder=1)
    ax_img.set_axis_off()
    image = ax_img.imshow(tip)
    ax_info = fig.add_axes([0.745, 0.085, 0.23, 0.79], zorder=1)
    ax_info.set_facecolor("#172033")
    ax_info.set_xticks([])
    ax_info.set_yticks([])
    ax_info.text(0.06, 0.96, _metric_text(summary), transform=ax_info.transAxes,
                 va="top", ha="left", fontsize=8.1, linespacing=1.48,
                 family="monospace", color="white")

    ax_card = fig.add_axes([0.025, 0.085, 0.95, 0.79], zorder=10)
    ax_card.set_facecolor("#11151d")
    ax_card.set_xticks([])
    ax_card.set_yticks([])
    card_head = ax_card.text(0.5, 0.73, "", ha="center", va="center",
                             fontsize=23, fontweight="bold", color="#f2c14e",
                             transform=ax_card.transAxes)
    card_body = ax_card.text(0.5, 0.42, "", ha="center", va="center",
                             fontsize=11, linespacing=1.55, color="white",
                             family="monospace", transform=ax_card.transAxes)
    ax_card.set_visible(False)

    vu.add_watermark(fig, alpha=0.19, fontsize=29)
    vu.add_provenance(
        fig,
        ["task_response_summary.csv", "tip_response_matrix.png",
         "root_moment_and_energy.png", "e15_ancf_legacy_retry_forensics.csv"],
        extra="read-only evidence reel; no time-history reconstruction")

    progress = fig.add_axes([0.025, 0.045, 0.95, 0.008], zorder=30)
    progress.set_xlim(0, N_FRAMES - 1)
    progress.set_ylim(0, 1)
    progress.set_xticks([])
    progress.set_yticks([])
    progress.set_facecolor("#d9dee8")
    progress_bar = progress.barh([0.5], [0], height=1.0,
                                 color="#4c78a8", align="center")[0]

    def show_image(arr, heading):
        ax_card.set_visible(False)
        ax_img.set_visible(True)
        ax_info.set_visible(True)
        image.set_data(arr)
        title.set_text(heading)

    def show_card(heading, body, color="#f2c14e"):
        ax_img.set_visible(False)
        ax_info.set_visible(False)
        ax_card.set_visible(True)
        title.set_text("v05 · Flexible-response evidence boundary")
        card_head.set_text(heading)
        card_head.set_color(color)
        card_body.set_text(body)

    def draw(k):
        if k < 8 * FPS:
            show_image(tip, "v05 · Existing tip-response matrix (read-only)")
        elif k < 16 * FPS:
            show_image(root, "v05 · Existing root-moment and energy plot (read-only)")
        elif k < 21 * FPS:
            show_card(
                "NO_REPLAYABLE_TIME_HISTORY",
                "Only aggregate PNGs and the summary CSV are archived.\n"
                "No nodal/deformation time series is available for replay.\n\n"
                "No interpolation. No synthetic deformation. No hidden rerun.\n"
                "ANCF executions during this visualization build: 0\n\n"
                "Line B remains REPEAT · this reel is NOT gate validation.")
        else:
            idx = 0 if k < 24.5 * FPS else 1
            r = failures[idx]
            show_card(
                "FLEX_SOLVER_FAIL · UNKNOWN_INADMISSIBLE",
                f"case_id: {r['case_id']}\n"
                f"failure_classification: {r['failure_classification']}\n"
                f"attempt_count: {r['attempt_count']}\n"
                f"scenario_hash: {r['forensic_scenario_hash']}\n\n"
                "Failure evidence is preserved exactly.\n"
                "UNKNOWN is not recolored or narrated as physically unsafe.\n"
                "No failed interval is interpolated or animated.",
                color="#e0b400")
        progress_bar.set_width(k)

    vu.render_video(OUT, fig, N_FRAMES, draw, fps=FPS)

    f1 = float(summary["f1_hz"])
    tip_peak = float(summary["tip_peak_mm"])
    mroot = float(summary["Mroot_peak_mNm"])
    umax = float(summary["U_max_J"])
    fdom = float(summary["f_dom_hz"])
    t5 = float(summary["t5pct_s"])
    rows = [
        vu.kf_row(VIDEO, 0, 0.0, "f1 [Hz] (summary panel)", f1, f1,
                  "task_response_summary.csv"),
        vu.kf_row(VIDEO, 2 * FPS, 2.0, "tip peak [mm] (summary panel)",
                  tip_peak, tip_peak, "task_response_summary.csv"),
        vu.kf_row(VIDEO, 4 * FPS, 4.0, "root moment peak [mN m] (summary panel)",
                  mroot, mroot, "task_response_summary.csv"),
        vu.kf_row(VIDEO, 6 * FPS, 6.0, "U max [J] (summary panel)",
                  umax, umax, "task_response_summary.csv"),
        vu.kf_row(VIDEO, 8 * FPS, 8.0, "dominant f [Hz] (summary panel)",
                  fdom, fdom, "task_response_summary.csv"),
        vu.kf_row(VIDEO, 12 * FPS, 12.0, "t5% [s] (extrapolated panel)",
                  t5, t5, "task_response_summary.csv",
                  note="fit_extrapolated; beyond the 15 s run window"),
        vu.kf_row(VIDEO, 21 * FPS, 21.0, "failure case 1 (card)",
                  failures[0]["case_id"], FAIL_CASES[0],
                  "e15_ancf_legacy_retry_forensics.csv"),
        vu.kf_row(VIDEO, int(24.5 * FPS), 24.5, "failure case 2 (card)",
                  failures[1]["case_id"], FAIL_CASES[1],
                  "e15_ancf_legacy_retry_forensics.csv"),
    ]
    import matplotlib.pyplot as plt
    plt.close(fig)
    return {"video": VIDEO, "path": OUT, "n_frames": N_FRAMES, "fps": FPS,
            "kf_rows": rows, "read_only": True, "ancf_recomputed": False}


def main():
    out = build()
    n, bad = vu.update_keyframe_csv(VIDEO, out["kf_rows"])
    dur, mb, w, h = vu.video_info(out["path"])
    print(f"[{VIDEO}] {dur:.1f} s, {mb:.1f} MB, {w}x{h}, "
          f"keyframes {n} ({'ALL MATCH' if not bad else f'{len(bad)} MISMATCH'}), "
          "ANCF executions 0 (read-only existing artifacts)")
    for r in bad:
        print("  MISMATCH:", r)
    return out


if __name__ == "__main__":
    main()
