"""Run the frozen CTRL-01-R matrix and write deterministic evidence artifacts.

Flow per method variant (repeat preregistration R-2/R-3):
  T1 (shared reference) -> T2 (30 s, full state frozen at t=15 s) ->
  T3 built from that variant's own frozen T2 t=15 s state with the target
  phase continuing the 3 deg/s const-omega propagation.
Variants: C0, C1, C2, C3 (main) + C1_MATCH5, C2_MATCH5 (matched 5D controls).
The fast plant is machine-cross-checked against the frozen sim_11 SSOT before
any scenario runs; a mismatch aborts the matrix (fail closed).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import platform
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from contracts import canonical_hash, load_config, load_matrix, raw_sha256
from fast_plant import FastPlant, cross_check_against_ssot
from repo_imports import (
    CONFIG_PATH,
    MATRIX_PATH,
    RESULTS_DIR,
    CoupledModel,
)
from simulator import LEDGER_ATOL, LEDGER_INTEGRATOR, LEDGER_RTOL, run_closed_loop
from trajectories import build_t1_reference, build_t2_reference, build_t3_reference


TRAJECTORIES = ("T1", "T2", "T3")


def _variants(matrix: dict):
    modes = matrix["main_matrix"]["task_mode"]
    variants = []
    for method in matrix["main_matrix"]["methods"]:
        variants.append(
            {
                "label": method,
                "method": method,
                "task_mode": modes[method],
                "role": "MAIN",
            }
        )
    for key, role in (
        ("supplemental_matched_task", "MATCHED_5D_CONTROL"),
        ("supplemental_matched_feedforward_task", "MATCHED_5D_FEEDFORWARD_CONTROL"),
    ):
        spec = matrix[key]
        variants.append(
            {
                "label": spec["label"],
                "method": spec["method"],
                "task_mode": spec["task_mode"],
                "role": role,
            }
        )
    return variants


def _matrix_rows(matrix: dict):
    rows = []
    for variant in _variants(matrix):
        for trajectory in TRAJECTORIES:
            rows.append(
                {
                    "scenario_id": f"{variant['label']}_{trajectory}",
                    "method": variant["method"],
                    "trajectory": trajectory,
                    "task_mode": variant["task_mode"],
                    "role": variant["role"],
                }
            )
    return rows


def _write_matrix(rows):
    path = RESULTS_DIR / "preregistered_matrix.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_summary(summaries):
    path = RESULTS_DIR / "control_01_summary.csv"
    fields = list(summaries[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries)
    return path


def _write_timeseries(all_histories):
    path = RESULTS_DIR / "control_01_timeseries.csv"
    fields = [
        "scenario_id",
        "t_s",
        "position_error_m",
        "orientation_error_rad",
        "base_dev_angle_deg",
        "base_omega_norm_radps",
        "momentum_abs",
        "panel_tip_abs_peak_m",
        "panel_modal_energy_J",
        "task_sigma_min",
        "nullity",
        "nullspace_active",
        "reaction_primary",
        "reaction_command",
        "energy_J",
        "work_J",
        "damping_J",
        "energy_audit_abs_J",
        "q1_rad",
        "q2_rad",
        "q3_rad",
        "q4_rad",
        "q5_rad",
        "q6_rad",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for scenario_id, hist in all_histories.items():
            stride = max(1, int(round(0.05 / np.median(np.diff(hist["t_s"])))))
            indices = list(range(0, len(hist["t_s"]), stride))
            if indices[-1] != len(hist["t_s"]) - 1:
                indices.append(len(hist["t_s"]) - 1)
            for k in indices:
                row = {
                    "scenario_id": scenario_id,
                    "t_s": float(hist["t_s"][k]),
                    "position_error_m": float(hist["position_error_m"][k]),
                    "orientation_error_rad": float(hist["orientation_error_rad"][k]),
                    "base_dev_angle_deg": float(hist["base_dev_angle_deg"][k]),
                    "base_omega_norm_radps": float(
                        np.linalg.norm(hist["base_omega_radps"][k])
                    ),
                    "momentum_abs": float(hist["momentum_abs"][k]),
                    "panel_tip_abs_peak_m": float(
                        np.max(np.abs(hist["panel_tip_m"][k]))
                    ),
                    "panel_modal_energy_J": float(
                        hist["panel_modal_energy_J"][k]
                    ),
                    "task_sigma_min": float(hist["task_sigma_min"][k]),
                    "nullity": int(hist["nullity"][k]),
                    "nullspace_active": int(hist["nullspace_active"][k]),
                    "reaction_primary": float(hist["reaction_primary"][k]),
                    "reaction_command": float(hist["reaction_command"][k]),
                    "energy_J": float(hist["energy_J"][k]),
                    "work_J": float(hist["work_J"][k]),
                    "damping_J": float(hist["damping_J"][k]),
                    "energy_audit_abs_J": float(hist["energy_audit_abs_J"][k]),
                }
                for j in range(6):
                    row[f"q{j + 1}_rad"] = float(hist["theta_rad"][k, j])
                writer.writerow(row)
    return path


def _write_collision_timeseries(all_histories):
    path = RESULTS_DIR / "control_01_collision_timeseries.csv"
    fields = [
        "scenario_id",
        "t_s",
        "evaluation_status",
        "plan_contract_status",
        "static_evaluation_status",
        "target_evaluation_status",
        "combined_evaluation_status",
        "static_margin_m",
        "target_margin_m",
        "combined_margin_m",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for scenario_id, history in all_histories.items():
            evidence = history.get("collision")
            if evidence is None:
                continue
            for index, t_s in enumerate(evidence["t_s"]):
                static = evidence["static_margin_m"]
                target = evidence["target_margin_m"]
                combined = evidence["combined_margin_m"]
                writer.writerow(
                    {
                        "scenario_id": scenario_id,
                        "t_s": float(t_s),
                        "evaluation_status": evidence["evaluation_status"],
                        "plan_contract_status": evidence["plan_contract_status"],
                        "static_evaluation_status": evidence[
                            "static_evaluation_status"
                        ],
                        "target_evaluation_status": evidence[
                            "target_evaluation_status"
                        ],
                        "combined_evaluation_status": evidence[
                            "combined_evaluation_status"
                        ],
                        "static_margin_m": (
                            None if static is None else float(static[index])
                        ),
                        "target_margin_m": (
                            None if target is None else float(target[index])
                        ),
                        "combined_margin_m": (
                            None if combined is None else float(combined[index])
                        ),
                    }
                )
    return path


def _plot(summaries):
    main = [row for row in summaries if row["role"] == "MAIN"]
    colors = {"C0": "#777777", "C1": "#277da1", "C2": "#43aa8b", "C3": "#f8961e"}
    fig, axes = plt.subplots(3, 3, figsize=(13, 10))
    metrics = [
        ("position_error_p95_m", "position p95 [m]"),
        ("base_omega_integral_deg", "integral |omega_b| [deg]"),
        ("panel_tip_peak_mm", "panel tip peak [mm], provisional"),
    ]
    for i, trajectory in enumerate(TRAJECTORIES):
        rows = [row for row in main if row["trajectory"] == trajectory]
        for j, (field, label) in enumerate(metrics):
            ax = axes[i, j]
            methods = [row["method"] for row in rows]
            values = [float(row[field]) for row in rows]
            ax.bar(methods, values, color=[colors[m] for m in methods])
            ax.set_ylabel(label)
            ax.grid(axis="y", alpha=0.25)
            if j == 0:
                ax.set_title(f"{trajectory} preregistered comparison")
    fig.suptitle(
        "CTRL-01-R C0-C3 solver-grade-ledger comparison (flexible parameters provisional)",
        fontsize=13,
    )
    fig.tight_layout()
    path = RESULTS_DIR / "control_01_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    matrix = load_matrix()
    rows = _matrix_rows(matrix)
    matrix_csv = _write_matrix(rows)
    slow_model = CoupledModel(
        n_modes=int(cfg["model"]["n_modes_per_panel"]),
        stiffness_case=cfg["model"]["stiffness_case"],
    )
    plant = FastPlant(slow_model)
    equivalence = cross_check_against_ssot(slow_model, plant)
    print(
        "fast plant vs sim_11 SSOT cross-check: "
        f"{equivalence['status']} (worst {equivalence['overall_worst']:.3e})",
        flush=True,
    )
    if equivalence["status"] != "PASS":
        report = {
            "schema_version": "control-01-run-v2",
            "task_id": "CTRL-01",
            "status": "ABORTED_FAST_PLANT_EQUIVALENCE_FAIL",
            "fast_plant_equivalence": equivalence,
        }
        (RESULTS_DIR / "control_01_run_summary.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return 2

    slow_rigid = CoupledModel(rigid_panels=True)
    rigid_plant = FastPlant(slow_rigid)
    print("building T1 open-loop anchor references (flexible + rigid)", flush=True)
    t1_reference = build_t1_reference(plant, cfg, slow_model=slow_model)
    rigid_t1 = build_t1_reference(rigid_plant, cfg, slow_model=slow_rigid)
    t2_reference = build_t2_reference(slow_model, cfg)

    variants = _variants(matrix)
    summaries = []
    histories = {}
    trigger_states = {}
    started = time.perf_counter()
    index = 0
    total = len(rows)
    for variant in variants:
        label = variant["label"]
        snapshot = None
        for trajectory in TRAJECTORIES:
            index += 1
            scenario_id = f"{label}_{trajectory}"
            print(
                f"[{index:02d}/{total:02d}] {scenario_id} "
                f"({variant['task_mode']}, {variant['role']})",
                flush=True,
            )
            if trajectory == "T1":
                reference = t1_reference
            elif trajectory == "T2":
                reference = t2_reference
            else:
                if snapshot is None:
                    raise RuntimeError(
                        f"{label}: T2 t=15 s snapshot missing; cannot build T3"
                    )
                reference = build_t3_reference(plant, cfg, snapshot)
            summary, history = run_closed_loop(
                plant,
                cfg,
                variant["method"],
                variant["task_mode"],
                reference,
            )
            if trajectory == "T2":
                snapshot = history["t2_freeze_snapshot"]
                if snapshot is None:
                    raise RuntimeError(f"{label}: T2 freeze snapshot not captured")
                trigger_states[label] = {
                    "t_abs_s": snapshot["t_abs_s"],
                    "theta_rad": snapshot["theta"].tolist(),
                    "theta_dot_radps": snapshot["theta_dot"].tolist(),
                    "base_position_I_m": snapshot["base_position_I"].tolist(),
                    "base_quaternion_BI": snapshot["base_quaternion_BI"].tolist(),
                    "eta": snapshot["eta"].tolist(),
                    "eta_dot": snapshot["eta_dot"].tolist(),
                }
            row = {
                "scenario_id": scenario_id,
                "method": variant["method"],
                "trajectory": trajectory,
                "task_mode": variant["task_mode"],
                "role": variant["role"],
            }
            summary = {
                "scenario_id": scenario_id,
                "role": variant["role"],
                **summary,
                "scenario_contract_sha256": canonical_hash(row),
            }
            summaries.append(summary)
            histories[scenario_id] = history
            print(
                "  p95=%.6g m  base=%.4f deg  momentum=%.3e  eaudit=%.3e  runtime=%.1fs"
                % (
                    summary["position_error_p95_m"],
                    summary["base_attitude_peak_deg"],
                    summary["momentum_max_abs"],
                    summary["energy_audit_relative"],
                    summary["runtime_s"],
                ),
                flush=True,
            )
    elapsed = time.perf_counter() - started
    summary_csv = _write_summary(summaries)
    timeseries_csv = _write_timeseries(histories)
    collision_timeseries_csv = _write_collision_timeseries(histories)
    figure = _plot(summaries)
    t3_collision = histories["C0_T3"]["collision"]
    metadata = {
        "schema_version": "control-01-run-v2",
        "task_id": "CTRL-01",
        "config_sha256": raw_sha256(CONFIG_PATH),
        "matrix_sha256": raw_sha256(MATRIX_PATH),
        "n_main_scenarios": 12,
        "n_matched_5d_scenarios": 6,
        "total_runtime_s": elapsed,
        "python": platform.python_version(),
        "plant": (
            "sim_11 CoupledModel via machine-cross-checked FastPlant, "
            "reduced-momentum closed loop"
        ),
        "integrator": (
            f"{LEDGER_INTEGRATOR}, rtol={LEDGER_RTOL}, atol={LEDGER_ATOL}, "
            "control sample 0.01 s first-order hold"
        ),
        "fast_plant_equivalence": equivalence,
        "open_loop_anchors": {
            "flexible_T1": t1_reference.open_loop,
            "rigid_T1": rigid_t1.open_loop,
            "sim11_frozen_flexible_peak_deg": 19.199885629572467,
            "sim11_frozen_rigid_peak_deg": 19.199850770410567,
        },
        "T2": t2_reference.open_loop,
        "T3": {
            "retreat_distance_m": float(
                cfg["trajectories"]["T3"]["retreat_distance_m"]
            ),
            "move_duration_s": float(
                cfg["trajectories"]["T3"]["duration_move_s"]
            ),
            "trigger_contract": cfg["trajectories"]["T3"]["trigger"],
            "collision_evaluation": {
                key: value
                for key, value in t3_collision.items()
                if key
                not in {
                    "t_s",
                    "static_margin_m",
                    "target_margin_m",
                    "combined_margin_m",
                }
            },
        },
        "t3_trigger_states": trigger_states,
        "preregistration_evidence_status": (
            "PROCEDURAL_ONLY_CONFIG_AND_RESULTS_COMMITTED_TOGETHER"
        ),
        "repeat_preregistration": (
            "10_research/partner_requirement_closure/wave1_repeat/"
            "repeat_preregistration.md"
        ),
        "PROVISIONAL_PARAMS": True,
        "independent_red_team_status": "PENDING_REVIEW",
        "artifacts": [
            str(matrix_csv.relative_to(RESULTS_DIR.parent)),
            str(summary_csv.relative_to(RESULTS_DIR.parent)),
            str(timeseries_csv.relative_to(RESULTS_DIR.parent)),
            str(collision_timeseries_csv.relative_to(RESULTS_DIR.parent)),
            str(figure.relative_to(RESULTS_DIR.parent)),
        ],
    }
    metadata_path = RESULTS_DIR / "control_01_run_summary.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    command_path = RESULTS_DIR / "reproduction_command.txt"
    command_path.write_text(
        "python 30_simulation/control_01_end_effector_tracking/src/run_experiments.py\n",
        encoding="utf-8",
    )
    print(f"completed {len(rows)} scenarios in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
