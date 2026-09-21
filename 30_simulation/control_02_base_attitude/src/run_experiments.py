"""Run the pre-registered CTRL-02 proof set and write deterministic artifacts."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config_loader import MODULE, load_config
from phase_a import run_phase_a
from phase_b import run_phase_b
from transient_b import run_transient


RESULTS = MODULE / "results"


def _write_json(path: Path, value) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def _write_stage_a_timeseries(rows: list[dict]) -> None:
    path = RESULTS / "stage_a_timeseries.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_control_results(stage_a: list[dict], stage_b: list[dict]) -> None:
    rows = []
    for row in stage_a:
        rows.append(
            {
                "phase": "A",
                "scenario": row["maneuver"],
                "controller": row["controller"],
                "evaluation_status": row["evaluation_status"],
                "analysis_scope": row.get("analysis_scope", ""),
                "stability_status": row.get("stability_status", ""),
                "method_result": row.get("method_result", ""),
                "domain_status": "",
                "attribution": row.get("attribution", ""),
                "peak_base_dev_angle_deg": row.get("peak_base_dev_angle_deg", ""),
                "body_rate_initial_dps": "",
                "body_rate_final_dps": "",
                "wheel_box_utilization_max": row.get("wheel_box_utilization_max", ""),
                "external_angular_impulse_Nms": row.get(
                    "external_angular_impulse_Nms", ""
                ),
                "propellant_g": "",
                "stage_a_generalized_momentum_residual": row.get(
                    "momentum_conservation_max_abs", ""
                ),
                "capture_eps_H_dimensionless": "",
                "capture_eps_P_dimensionless": "",
                "external_angular_ledger_closure_Nms": "",
                "flex_status": row["flex_status"],
            }
        )
    for row in stage_b:
        rows.append(
            {
                "phase": "B",
                "scenario": row["case"],
                "controller": row["controller"],
                "evaluation_status": row["evaluation_status"],
                "analysis_scope": row["analysis_scope"],
                "stability_status": row["stability_status"],
                "method_result": row["controller_outcome"],
                "domain_status": row["domain_status"],
                "attribution": row["attribution"],
                "peak_base_dev_angle_deg": "",
                "body_rate_initial_dps": row["post_capture_rate_initial_dps"],
                "body_rate_final_dps": row["body_rate_final_dps"],
                "wheel_box_utilization_max": row["wheel_box_utilization_max"],
                "external_angular_impulse_Nms": row[
                    "external_angular_impulse_Nms"
                ],
                "propellant_g": row["propellant_g"],
                "stage_a_generalized_momentum_residual": "",
                "capture_eps_H_dimensionless": row["capture_eps_H"],
                "capture_eps_P_dimensionless": row["capture_eps_P"],
                "external_angular_ledger_closure_Nms": row[
                    "external_ledger_closure_max_abs"
                ],
                "flex_status": row["flex_status"],
            }
        )
    path = RESULTS / "control_results.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_gc0_ledger(
    stage_a: list[dict], stage_b: list[dict], transient: list[dict]
) -> None:
    a_rows = [
        {
            "phase": "A",
            "scenario": r["maneuver"],
            "controller": r["controller"],
            "evaluation_status": r["evaluation_status"],
            "delta_H_external_Nms": r.get("external_angular_impulse_Nms"),
            "wheel_storage_peak_axis_Nms": r.get("wheel_peak_axis_Nms"),
            "H_total_residual_max_abs": r.get("momentum_conservation_max_abs"),
            "wheel_body_exchange_max_abs": r.get("wheel_body_exchange_max_abs"),
            "attribution": r.get("attribution"),
        }
        for r in stage_a
    ]
    b_rows = [
        {
            "phase": "B",
            "scenario": r["case"],
            "controller": r["controller"],
            "H_before_Nms": r["H_initial_Nms"],
            "H_after_total_Nms": r["H_total_final_Nms"],
            "H_after_body_Nms": r["H_body_final_Nms"],
            "wheel_storage_vector_Nms": r["wheel_h_final_Nms"],
            "delta_H_external_vector_Nms": r[
                "external_angular_impulse_vector_Nms"
            ],
            "capture_eps_H_dimensionless": r["capture_eps_H"],
            "capture_eps_P_dimensionless": r["capture_eps_P"],
            "external_closure_max_abs_Nms": r["external_ledger_closure_max_abs"],
            "propellant_g": r["propellant_g"],
            "attribution": r["attribution"],
            "domain_status": r["domain_status"],
            "physical_control_region": r["physical_control_region"],
            "frozen_legacy_region_crosscheck": r["frozen_legacy_region"],
            "analysis_scope": r["analysis_scope"],
            "stability_status": r["stability_status"],
        }
        for r in stage_b
    ]
    t_rows = [
        {
            "phase": "B_TRANSIENT",
            "scenario": r["case"],
            "controller": r["controller"],
            "stability_status": r["stability_status"],
            "model_fidelity": r["model_fidelity"],
            "wheel_storage_vector_Nms": r["wheel_h_final_Nms"],
            "delta_H_external_vector_Nms": r[
                "external_angular_impulse_vector_Nms"
            ],
            "H_after_body_Nms": r["H_body_final_Nms"],
            "terminal_vs_L0_diff_Nms": r["terminal_vs_L0_diff_Nms"],
            "propellant_g": r["propellant_g"],
            "attribution": r["attribution"],
            "stability_verdict": r["stability_verdict"],
        }
        for r in transient
    ]
    _write_json(
        RESULTS / "gc0_momentum_ledger.json",
        {
            "schema_version": "control02-gc0-ledger-v3",
            "residual_channels": {
                "capture_eps_H_and_eps_P": {
                    "unit": "1",
                    "description": "dimensionless rigidization conservation residuals",
                },
                "external_closure_max_abs_Nms": {
                    "unit": "N*m*s",
                    "description": "external angular-momentum ledger closure",
                },
            },
            "attribution_vocabulary": [
                "INTERNAL_REDISTRIBUTION",
                "MOMENTUM_STORAGE",
                "EXTERNAL_MOMENTUM_REMOVAL",
                "MIXED",
            ],
            "machine_classified": True,
            "rows": a_rows + b_rows + t_rows,
        },
    )


def _plot(stage_a: list[dict], stage_b: list[dict], transient: list[dict]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(19, 5))
    evaluated_a = [r for r in stage_a if r["evaluation_status"] == "EVALUATED"]
    labels_a = [f"{r['maneuver']}\n{r['controller'].split('_')[0]}" for r in evaluated_a]
    values_a = [r["peak_base_dev_angle_deg"] for r in evaluated_a]
    axes[0].bar(range(len(values_a)), values_a, color=["C0", "C1", "C2"] * 2)
    axes[0].set_xticks(range(len(values_a)), labels_a, rotation=20, ha="right")
    axes[0].set_ylabel("peak base dev_angle [deg]")
    axes[0].set_title("Stage A base-reaction comparison")
    axes[0].grid(axis="y", alpha=0.3)

    b2 = [r for r in stage_b if r["controller"] in ("B2_thruster_removal", "B3_wheel_thruster")]
    labels_b = [f"{r['case']}\n{r['controller'].split('_')[0]}" for r in b2]
    prop = [r["propellant_g"] for r in b2]
    colors = ["C3" if r["counterfactual_only"] else "C4" for r in b2]
    axes[1].bar(range(len(prop)), prop, color=colors)
    axes[1].set_xticks(range(len(prop)), labels_b, rotation=25, ha="right")
    axes[1].set_ylabel("propellant [g]")
    axes[1].set_title(
        "Stage B momentum-level terminal-feasibility cost\n"
        "(red = out-of-region counterfactual)"
    )
    axes[1].grid(axis="y", alpha=0.3)

    for r in transient:
        if r["controller"] == "B0_no_control":
            continue
        t = [s["t_s"] for s in r["timeseries_1hz"] if s["t_s"] <= r["window_s"]]
        v = [
            s["rate_dps"]
            for s in r["timeseries_1hz"]
            if s["t_s"] <= r["window_s"]
        ]
        style = "-" if r["stabilized_within_window"] else "--"
        axes[2].semilogy(t, [max(x, 1e-6) for x in v], style, linewidth=1.0,
                         label=f"{r['case']}/{r['controller'].split('_')[0]}")
    axes[2].axhline(
        transient[0]["rate_settle_dps"], color="k", linewidth=0.8, alpha=0.6
    )
    axes[2].set_xlabel("t [s]")
    axes[2].set_ylabel("body rate [deg/s]")
    axes[2].set_title(
        "Stage B transient (PROVISIONAL actuators)\n"
        "solid = stabilized within window, dashed = not"
    )
    axes[2].legend(fontsize=6, ncol=2)
    axes[2].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "control_02_overview.png", dpi=140)
    plt.close(fig)


def _write_transient_timeseries(rows: list[dict]) -> None:
    path = RESULTS / "stage_b_transient_timeseries.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["case", "controller", "t_s", "rate_dps"])
        for row in rows:
            for sample in row["timeseries_1hz"]:
                writer.writerow(
                    [row["case"], row["controller"], sample["t_s"], sample["rate_dps"]]
                )


def run_all(cfg: dict | None = None):
    cfg = load_config() if cfg is None else cfg
    RESULTS.mkdir(parents=True, exist_ok=True)
    stage_a, timeseries = run_phase_a(cfg)
    stage_b, crosschecks = run_phase_b(cfg)
    transient, transient_criterion = run_transient(cfg, stage_b)
    _write_json(RESULTS / "stage_a_summary.json", stage_a)
    _write_json(RESULTS / "stage_b_summary.json", stage_b)
    _write_json(
        RESULTS / "stage_b_transient.json",
        {"criterion": transient_criterion, "rows": transient},
    )
    _write_json(RESULTS / "sim12_independent_crosscheck.json", crosschecks)
    _write_stage_a_timeseries(timeseries)
    _write_transient_timeseries(transient)
    _write_control_results(stage_a, stage_b)
    _write_gc0_ledger(stage_a, stage_b, transient)
    _plot(stage_a, stage_b, transient)
    summary = {
        "schema_version": "control02-proof-set-v3",
        "n_stage_a_rows": len(stage_a),
        "n_stage_a_evaluated": sum(
            r["evaluation_status"] == "EVALUATED" for r in stage_a
        ),
        "n_stage_b_rows": len(stage_b),
        "n_stage_b_transient_rows": len(transient),
        "a3_evaluation_status": cfg["stage_a"]["A3"]["evaluation_status"],
        "flex_status": cfg["stage_b"]["flex_status"],
        "stage_b_analysis_scope": "MOMENTUM_LEVEL_TERMINAL_FEASIBILITY",
        "stage_b_l0_stability_status": "NOT_EVALUATED_NO_ACTUATOR_DYNAMICS",
        "stage_b_transient_stability_status": (
            "EVALUATED_TIME_WINDOW_PROVISIONAL_ACTUATORS"
        ),
        "n_stabilized_within_window": sum(
            r["stabilized_within_window"] for r in transient
        ),
    }
    _write_json(RESULTS / "experiment_summary.json", summary)
    return stage_a, timeseries, stage_b, crosschecks, transient, transient_criterion, summary


if __name__ == "__main__":
    print(json.dumps(run_all()[-1], indent=2, ensure_ascii=False))
