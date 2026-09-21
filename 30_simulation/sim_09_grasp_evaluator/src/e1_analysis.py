"""sim_09 Gate E1 -- analysis: tables + figures from e1_results_72cases.csv.

EVERYTHING here is derived from the results CSV (iron rule 5: rerunnable, no
hand-drawn / hard-coded numbers). Selection logic (iron rule 3):
hard-constraint screen -> per-metric values -> Pareto front. NO overall_score.

Groups
------
G0  baseline row: (P1, t_c=0, v_app=0.01, pose_6d) -- the E0 nominal scenario.
G1  geometric selection: in each (t_c x v_app x mode) bucket pick the grasp
    point by reachability (ik_feasible) + MAX manipulability (sqrt_det_JJT),
    ties broken lexicographically by grasp_point_id. Dynamics ignored.
G2  dynamics-aware selection: admissible rows only -> per-bucket Pareto layer 1
    on the six metrics [dtheta_base, |w+|, |J_t|, E_flex, H_RW, m_prop] (all
    minimized) -> representative = max deterministic M_PCS (tie lexicographic).

Outputs
-------
30_simulation/sim_09_grasp_evaluator/tables/g0_g1_g2_comparison.csv
30_simulation/sim_09_grasp_evaluator/tables/pareto_front.csv
30_simulation/sim_09_grasp_evaluator/tables/infeasible_cases.csv
30_simulation/sim_09_grasp_evaluator/figures/fig_e1_pareto.png
30_simulation/sim_09_grasp_evaluator/figures/fig_e1_g1_vs_g2.png
30_simulation/sim_09_grasp_evaluator/figures/fig_e1_phase_map.png
30_simulation/sim_09_grasp_evaluator/results/e1_gate_check.json   (pass-condition 3 verdict)

Run:  python e1_analysis.py
"""
import _bootstrap  # noqa: F401
import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

RESULTS_CSV = os.path.join(_bootstrap.RESULTS_DIR, "e1_results_72cases.csv")
TABLES_DIR = os.path.join(_bootstrap.REPO_ROOT, "tables", "sim_09_grasp_evaluator")
FIGURES_DIR = os.path.join(_bootstrap.REPO_ROOT, "figures", "sim_09_grasp_evaluator")
GATE_JSON = os.path.join(_bootstrap.RESULTS_DIR, "e1_gate_check.json")

BUCKET_KEYS = ["t_c_s", "v_app_mps", "task_constraint_mode"]
G0_CASE_ID = "P1_tc00_v10mm_pose_6d"

# six Pareto metrics, ALL minimized (order fixed by the E1 instruction)
PARETO_METRICS = ["base_attitude_change_deg", "post_capture_rate_dps",
                  "Jt_norm_Ns", "E_flex_J", "H_RW_Nms", "m_prop_g"]
METRIC_LABELS = {
    "base_attitude_change_deg": "dtheta_base [deg]",
    "post_capture_rate_dps": "|w+| [deg/s]",
    "Jt_norm_Ns": "|J_t| [N s]",
    "E_flex_J": "E_flex [J]",
    "H_RW_Nms": "H_RW [N m s]",
    "m_prop_g": "m_prop [g]",
}

# dataviz reference palette (validated set; fixed categorical order)
C_BLUE, C_AQUA, C_ORANGE = "#2a78d6", "#1baf7a", "#eb6834"
C_GRAY, C_LIGHT = "#52514e", "#b5b4ad"
SEQ_CMAP = LinearSegmentedColormap.from_list(
    "seq_blue", ["#cde2fb", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"])


# --------------------------------------------------------------------------
# loading + selections
# --------------------------------------------------------------------------

def load(path=RESULTS_CSV):
    df = pd.read_csv(path)
    if len(df) != 72:
        raise SystemExit(f"expected 72 rows, found {len(df)} -- finish the sweep first")
    if df["scenario_hash"].nunique() != 72:
        raise SystemExit("scenario_hash values are not unique")
    return df.sort_values("grid_index").reset_index(drop=True)


def pareto_layer1(sub, metrics=PARETO_METRICS):
    """Boolean mask (index-aligned to `sub`) of non-dominated rows (minimize)."""
    X = sub[metrics].to_numpy(float)
    n = len(X)
    mask = np.ones(n, bool)
    for i in range(n):
        for j in range(n):
            if i != j and np.all(X[j] <= X[i]) and np.any(X[j] < X[i]):
                mask[i] = False
                break
    return pd.Series(mask, index=sub.index)


def g1_pick(bucket_df):
    """Reachability + max manipulability; ties (values equal within 1e-12,
    which happens by construction -- the E0 scene placement maps every grasp
    point to the same desired EE pose in S) -> lexicographic point id."""
    feas = bucket_df[bucket_df["ik_feasible"] == 1].copy()
    if feas.empty:
        return None
    feas["_manip_r"] = feas["manip_sqrt_det_JJT"].round(12)
    feas = feas.sort_values(["_manip_r", "grasp_point_id"],
                            ascending=[False, True], kind="mergesort")
    return feas.iloc[0]


def g2_pick(bucket_df):
    """Admissible -> in-bucket Pareto layer 1 -> max M_PCS (tie lexicographic)."""
    adm = bucket_df[bucket_df["admissible"] == 1]
    if adm.empty:
        return None
    front = adm[pareto_layer1(adm)]
    front = front.sort_values(["M_PCS", "grasp_point_id"],
                              ascending=[False, True], kind="mergesort")
    return front.iloc[0]


def all_picks(df):
    g1, g2 = {}, {}
    for key, sub in df.groupby(BUCKET_KEYS, sort=True):
        r1, r2 = g1_pick(sub), g2_pick(sub)
        if r1 is not None:
            g1[key] = r1
        if r2 is not None:
            g2[key] = r2
    return g1, g2


# --------------------------------------------------------------------------
# pass-condition 3 evaluation (per bucket, G2 vs G1)
# --------------------------------------------------------------------------

def rel_pct(new, old):
    if old == 0:
        return float("nan")
    return 100.0 * (new - old) / abs(old)


def gate3_evaluate(g1, g2):
    """For every bucket with both picks: criterion A = >=2 of the six metrics
    improved AND every other metric worsened by <= 5 %; criterion B =
    M_PCS improvement >= 20 % of |M_PCS(G1)|."""
    per_bucket = []
    for key in sorted(g2):
        if key not in g1:
            continue
        r1, r2 = g1[key], g2[key]
        deltas = {m: rel_pct(float(r2[m]), float(r1[m])) for m in PARETO_METRICS}
        improved = [m for m, d in deltas.items() if d < -1e-6]
        worsened = [d for m, d in deltas.items() if d > 1e-6]
        max_worse = max(worsened) if worsened else 0.0
        m1 = float(r1["M_PCS"]) if pd.notna(r1["M_PCS"]) else None
        m2 = float(r2["M_PCS"]) if pd.notna(r2["M_PCS"]) else None
        mpcs_gain_pct = (100.0 * (m2 - m1) / abs(m1)
                         if (m1 is not None and m2 is not None and m1 != 0) else None)
        pass_a = (len(improved) >= 2) and (max_worse <= 5.0)
        pass_b = (mpcs_gain_pct is not None) and (mpcs_gain_pct >= 20.0)
        per_bucket.append({
            "bucket": {"t_c_s": key[0], "v_app_mps": key[1], "mode": key[2]},
            "g1_case": r1["case_id"], "g2_case": r2["case_id"],
            "same_pick": bool(r1["case_id"] == r2["case_id"]),
            "metric_rel_pct_G2_vs_G1": {m: round(d, 3) for m, d in deltas.items()},
            "n_improved": len(improved), "improved": improved,
            "max_worsening_pct": round(max_worse, 3),
            "M_PCS_G1": m1, "M_PCS_G2": m2,
            "M_PCS_gain_pct": None if mpcs_gain_pct is None else round(mpcs_gain_pct, 2),
            "pass_A_2metrics_5pct": bool(pass_a and not (r1["case_id"] == r2["case_id"])),
            "pass_B_mpcs_20pct": bool(pass_b and not (r1["case_id"] == r2["case_id"])),
        })
    any_pass = any(b["pass_A_2metrics_5pct"] or b["pass_B_mpcs_20pct"]
                   for b in per_bucket)
    return per_bucket, any_pass


# --------------------------------------------------------------------------
# tables
# --------------------------------------------------------------------------

def write_comparison(df, g1, g2):
    """G0 / G1 / G2 representatives compared metric by metric. G1 and G2 are the
    picks of the G0 bucket (same t_c / v_app / mode -> like-for-like); if the G0
    bucket has no admissible G2 pick, fall back to the global max-M_PCS row."""
    g0 = df[df["case_id"] == G0_CASE_ID].iloc[0]
    key = (float(g0["t_c_s"]), float(g0["v_app_mps"]), g0["task_constraint_mode"])
    r1 = g1.get(key)
    r2 = g2.get(key)
    note2 = "G2 = in-bucket pick (same phase/speed/mode as G0)"
    if r2 is None:
        adm = df[df["admissible"] == 1]
        if adm.empty:
            raise SystemExit("no admissible rows -- no G2 representative")
        r2 = adm.sort_values(["M_PCS", "grasp_point_id"],
                             ascending=[False, True]).iloc[0]
        note2 = "G2 = GLOBAL max-M_PCS fallback (G0 bucket had no admissible row)"

    rows = [
        {"metric": "case_id", "unit": "-", "better": "-",
         "G0": g0["case_id"], "G1": r1["case_id"], "G2": r2["case_id"],
         "G2_vs_G1_rel_pct": "", "note": note2},
        {"metric": "grasp_point_id", "unit": "-", "better": "-",
         "G0": g0["grasp_point_id"], "G1": r1["grasp_point_id"],
         "G2": r2["grasp_point_id"], "G2_vs_G1_rel_pct": "", "note": ""},
        {"metric": "scenario_hash", "unit": "-", "better": "-",
         "G0": g0["scenario_hash"], "G1": r1["scenario_hash"],
         "G2": r2["scenario_hash"], "G2_vs_G1_rel_pct": "", "note": ""},
        {"metric": "admissible", "unit": "bool", "better": "-",
         "G0": int(g0["admissible"]), "G1": int(r1["admissible"]),
         "G2": int(r2["admissible"]), "G2_vs_G1_rel_pct": "",
         "note": "hard_constraints_v1.yaml screen"},
    ]
    numeric = ([(m, METRIC_LABELS[m].split("[")[1].rstrip("]"), "min")
                for m in PARETO_METRICS]
               + [("manip_sqrt_det_JJT", "-", "max"), ("manip_sigma_min", "-", "max"),
                  ("cond_number", "-", "min"), ("collision_margin_min_m", "m", "max"),
                  ("joint_limit_margin_rad", "rad", "max"),
                  ("severity_proxy", "N s eq (PROXY)", "min"),
                  ("mpcs_margin_H", "-", "max"), ("mpcs_margin_Jthr", "-", "max"),
                  ("mpcs_margin_Eflex", "-", "max"), ("mpcs_margin_omega", "-", "max"),
                  ("mpcs_margin_theta", "-", "max"), ("M_PCS", "-", "max")])
    for m, unit, better in numeric:
        v0, v1, v2 = float(g0[m]), float(r1[m]), float(r2[m])
        rows.append({"metric": m, "unit": unit, "better": better,
                     "G0": v0, "G1": v1, "G2": v2,
                     "G2_vs_G1_rel_pct": round(rel_pct(v2, v1), 3), "note": ""})
    out = os.path.join(TABLES_DIR, "g0_g1_g2_comparison.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    return out, g0, r1, r2


def write_pareto_front(df, g1):
    adm = df[df["admissible"] == 1]
    if adm.empty:
        front = adm.copy()
    else:
        front = adm[pareto_layer1(adm)].copy()
    g1_ids = {r["case_id"] for r in g1.values()}
    front["is_g1_pick"] = front["case_id"].isin(g1_ids).astype(int)
    cols = (["grid_index", "case_id", "grasp_point_id", "t_c_s", "v_app_mps",
             "task_constraint_mode", "scenario_hash"] + PARETO_METRICS
            + ["manip_sqrt_det_JJT", "M_PCS", "is_g1_pick"])
    out = os.path.join(TABLES_DIR, "pareto_front.csv")
    front.sort_values("grid_index")[cols].to_csv(out, index=False)
    return out, front


def write_infeasible(df):
    rows = []
    bad = df[df["admissible"] == 0]
    codes = {}
    for _, r in bad.iterrows():
        for c in str(r["failure_codes"]).split(";"):
            if c and c != "nan":
                codes.setdefault(c, []).append(r["case_id"])
    for c in sorted(codes):
        rows.append({"failure_code": c, "n_cases": len(codes[c]),
                     "case_ids": ";".join(sorted(codes[c]))})
    rows.append({"failure_code": "TOTAL_INADMISSIBLE", "n_cases": len(bad),
                 "case_ids": ""})
    rows.append({"failure_code": "TOTAL_ADMISSIBLE",
                 "n_cases": int((df["admissible"] == 1).sum()), "case_ids": ""})
    out = os.path.join(TABLES_DIR, "infeasible_cases.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    return out, codes


# --------------------------------------------------------------------------
# figures (matplotlib Agg; palette = validated dataviz reference instance)
# --------------------------------------------------------------------------

def _style(ax):
    ax.grid(True, color="#e4e3dd", linewidth=0.6, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(C_LIGHT)
    ax.tick_params(colors=C_GRAY, labelsize=8)


def fig_pareto(df, front, g1, g0_row):
    projections = [("post_capture_rate_dps", "Jt_norm_Ns"),
                   ("post_capture_rate_dps", "E_flex_J"),
                   ("H_RW_Nms", "base_attitude_change_deg")]
    g1_ids = {r["case_id"] for r in g1.values()}
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2))
    have = df[df["ik_feasible"] == 1]
    for ax, (mx, my) in zip(axes, projections):
        _style(ax)
        bad = have[have["admissible"] == 0]
        ok = have[(have["admissible"] == 1) & (~have["case_id"].isin(front["case_id"]))]
        ax.scatter(bad[mx], bad[my], s=22, marker="x", c=C_LIGHT, linewidths=1.2,
                   label="inadmissible", zorder=2)
        ax.scatter(ok[mx], ok[my], s=22, c=C_GRAY, alpha=0.55,
                   label="admissible", zorder=3)
        ax.scatter(front[mx], front[my], s=42, c=C_BLUE, label="Pareto layer 1",
                   zorder=4)
        g1_rows = have[have["case_id"].isin(g1_ids)]
        ax.scatter(g1_rows[mx], g1_rows[my], s=70, marker="X", facecolors="none",
                   edgecolors=C_ORANGE, linewidths=1.6, label="G1 picks", zorder=5)
        ax.scatter([g0_row[mx]], [g0_row[my]], s=120, marker="*", c="#0b0b0b",
                   label="G0 baseline", zorder=6)
        ax.set_xlabel(METRIC_LABELS[mx], fontsize=9, color="#0b0b0b")
        ax.set_ylabel(METRIC_LABELS[my], fontsize=9, color="#0b0b0b")
        ax.ticklabel_format(useOffset=False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=5, loc="upper center",
               bbox_to_anchor=(0.5, 0.92), fontsize=8, frameon=False)
    fig.suptitle("E1 thin slice (72 deterministic cases): Pareto front projections "
                 "-- G1 geometric picks vs dynamics-aware front", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    out = os.path.join(FIGURES_DIR, "fig_e1_pareto.png")
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return out


def fig_g1_vs_g2(r1, r2):
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4),
                                  gridspec_kw={"width_ratios": [3, 1]})
    _style(ax)
    _style(ax2)
    metrics = PARETO_METRICS + ["manip_sqrt_det_JJT"]
    labels = [METRIC_LABELS.get(m, "manipulability (max)") for m in metrics]
    v1 = np.array([float(r1[m]) for m in metrics])
    v2 = np.array([float(r2[m]) for m in metrics])
    norm2 = np.where(v1 != 0, v2 / v1, np.nan)
    x = np.arange(len(metrics))
    ax.bar(x - 0.19, np.ones_like(v1), width=0.36, color=C_BLUE, zorder=3,
           label=f"G1 {r1['case_id']}")
    ax.bar(x + 0.19, norm2, width=0.36, color=C_AQUA, zorder=3,
           label=f"G2 {r2['case_id']}")
    for i in range(len(metrics)):
        d = rel_pct(v2[i], v1[i])
        ax.annotate(f"{d:+.1f}%", (x[i] + 0.19, norm2[i]),
                    textcoords="offset points", xytext=(0, 4), ha="center",
                    fontsize=8, color="#0b0b0b")
        ax.annotate(f"{v1[i]:.3g}", (x[i] - 0.19, 0.02), rotation=90,
                    ha="center", va="bottom", fontsize=7, color="white")
        ax.annotate(f"{v2[i]:.3g}", (x[i] + 0.19, 0.02), rotation=90,
                    ha="center", va="bottom", fontsize=7, color="#0b0b0b")
    ax.axhline(1.0, color=C_LIGHT, linewidth=0.8, zorder=2)
    ax.set_xticks(x, [l.replace(" [", "\n[") for l in labels], fontsize=8)
    ax.set_ylabel("value / G1 value (G1 = 1.0)", fontsize=9)
    ax.set_ylim(0.0, max(1.0, float(np.nanmax(norm2))) * 1.45)
    ax.set_title("per-metric ratio (first six: lower is better; "
                 "manipulability: higher is better)", fontsize=9)
    ax.legend(fontsize=8, frameon=False, loc="upper left")

    m1 = float(r1["M_PCS"]); m2 = float(r2["M_PCS"])
    ax2.bar([0, 1], [m1, m2], width=0.55, color=[C_BLUE, C_AQUA], zorder=3)
    for xi, v in ((0, m1), (1, m2)):
        ax2.annotate(f"{v:+.3f}", (xi, v), textcoords="offset points",
                     xytext=(0, 5 if v >= 0 else -12), ha="center", fontsize=9)
    ax2.axhline(0.0, color=C_GRAY, linewidth=0.8)
    ax2.set_xticks([0, 1], ["G1", "G2"], fontsize=9)
    ax2.set_title("deterministic M_PCS\n(min of 5 margins; higher = more margin)",
                  fontsize=9)
    fig.suptitle("E1: geometric selection (G1) vs dynamics-aware selection (G2) "
                 f"-- bucket t_c={float(r1['t_c_s']):g} s, "
                 f"v_app={float(r1['v_app_mps']):g} m/s, "
                 f"{r1['task_constraint_mode']}", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = os.path.join(FIGURES_DIR, "fig_e1_g1_vs_g2.png")
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return out


def fig_phase_map(df, v_ref=0.01):
    points = ["P1", "P2", "P3"]
    tcs = sorted(df["t_c_s"].unique())
    panels = [("post_capture_rate_dps", "pose_6d"),
              ("post_capture_rate_dps", "approach_5d"),
              ("base_attitude_change_deg", "pose_6d"),
              ("base_attitude_change_deg", "approach_5d")]
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 6.8))
    for ax, (metric, mode) in zip(axes.ravel(), panels):
        sub = df[(df["v_app_mps"] == v_ref) & (df["task_constraint_mode"] == mode)]
        M = np.full((len(points), len(tcs)), np.nan)
        for i, p in enumerate(points):
            for j, tc in enumerate(tcs):
                row = sub[(sub["grasp_point_id"] == p) & (sub["t_c_s"] == tc)]
                if len(row) == 1 and pd.notna(row.iloc[0][metric]):
                    M[i, j] = float(row.iloc[0][metric])
        im = ax.imshow(M, cmap=SEQ_CMAP, aspect="auto")
        for i in range(len(points)):
            for j in range(len(tcs)):
                if np.isfinite(M[i, j]):
                    lum = (M[i, j] - np.nanmin(M)) / max(np.nanmax(M) - np.nanmin(M), 1e-30)
                    ax.text(j, i, f"{M[i, j]:.3f}", ha="center", va="center",
                            fontsize=8.5, color="white" if lum > 0.55 else "#0b0b0b")
        ax.set_xticks(range(len(tcs)), [f"{t:g}" for t in tcs], fontsize=8)
        ax.set_yticks(range(len(points)), points, fontsize=8)
        ax.set_xlabel("capture phase t_c [s]", fontsize=8, color=C_GRAY)
        ax.set_title(f"{METRIC_LABELS[metric]} -- {mode}", fontsize=9)
        cb = fig.colorbar(im, ax=ax, shrink=0.85,
                          format=matplotlib.ticker.ScalarFormatter(useOffset=False))
        cb.ax.tick_params(labelsize=7)
    fig.suptitle(f"E1 phase map @ v_app = {v_ref:g} m/s (rows: grasp point, "
                 "cols: capture phase)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = os.path.join(FIGURES_DIR, "fig_e1_phase_map.png")
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------

def main():
    os.makedirs(TABLES_DIR, exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)
    df = load()
    g1, g2 = all_picks(df)
    per_bucket, cond3_pass = gate3_evaluate(g1, g2)

    cmp_path, g0_row, r1, r2 = write_comparison(df, g1, g2)
    par_path, front = write_pareto_front(df, g1)
    inf_path, codes = write_infeasible(df)
    f1 = fig_pareto(df, front, g1, g0_row)
    f2 = fig_g1_vs_g2(r1, r2)
    f3 = fig_phase_map(df)

    gate = {
        "n_cases": int(len(df)),
        "n_ik_feasible": int((df["ik_feasible"] == 1).sum()),
        "n_admissible": int((df["admissible"] == 1).sum()),
        "failure_code_counts": {c: len(v) for c, v in sorted(codes.items())},
        "flex_status_counts": df["flex_status"].value_counts().to_dict(),
        "pareto_front_size": int(len(front)),
        "condition3_any_bucket_pass": bool(cond3_pass),
        "condition3_per_bucket": per_bucket,
        "g0_case": g0_row["case_id"], "g1_rep": r1["case_id"],
        "g2_rep": r2["case_id"],
        "outputs": [cmp_path, par_path, inf_path, f1, f2, f3],
    }
    with open(GATE_JSON, "w", encoding="utf-8") as f:
        json.dump(gate, f, indent=1, default=str)

    print(f"[e1_analysis] admissible {gate['n_admissible']}/72 | "
          f"pareto front {gate['pareto_front_size']} | "
          f"condition-3 pass: {cond3_pass}")
    for p in gate["outputs"] + [GATE_JSON]:
        print("  ->", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
