"""Fail-closed GC1 adjudication for CTRL-01-R.

Thresholds are the frozen v0 values (repeat preregistration: no threshold may
be rewritten). Structural changes in this loop, all preregistered:
  * the isolated-nullspace comparator is C2_MATCH5 (same 5D task, same
    feedforward as C3); the C1_MATCH5 overall-scheme comparison is retained
    as context and is no longer the basis of the isolation claim;
  * T3 target/combined collision margins are adjudicated (frozen T2 t=15 s
    trigger + const-omega continuation), fail-closed on contract mismatch;
  * the fast-plant/SSOT machine equivalence must be PASS or the verdict is
    BLOCKED.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from contracts import (
    GATE_RESULT_ENUM,
    load_config,
    normalized_semantic_sha256,
    raw_sha256,
)
from repo_imports import (
    CONFIG_PATH,
    MATRIX_PATH,
    REPO_ROOT,
    RESULTS_DIR,
    CoupledModel,
    skew,
)


SUMMARY_PATH = RESULTS_DIR / "control_01_summary.csv"
RUN_PATH = RESULTS_DIR / "control_01_run_summary.json"
BASELINE_PATH = RESULTS_DIR / "baseline_reproduction.json"
TIMESERIES_PATH = RESULTS_DIR / "control_01_timeseries.csv"
COLLISION_TIMESERIES_PATH = RESULTS_DIR / "control_01_collision_timeseries.csv"
FIGURE_PATH = RESULTS_DIR / "control_01_comparison.png"
MATRIX_CSV_PATH = RESULTS_DIR / "preregistered_matrix.csv"
TEST_PATH = RESULTS_DIR / "test_results.json"
GATE_PATH = RESULTS_DIR / "control_01_gate_check.json"
HASH_PATH = RESULTS_DIR / "artifacts_sha256.json"

VARIANT_LABELS = ("C0", "C1", "C2", "C3", "C1_MATCH5", "C2_MATCH5")
COLLISION_PLAN_MATCHED = "MATCHED_T2_T15_TRIGGER_AND_CONST_OMEGA_CONTINUATION"

# v1.0 negative results preserved per repeat preregistration item 1 (they are
# retained in the evidence chain regardless of this loop's outcome).
PREVIOUS_LOOP_NEGATIVE_RESULTS = {
    "source_commit": "7aecf6e36069823f0a0e6094f3c1f71407784ed5",
    "C2_vs_C1_T2_position_improvement_pct": -51.9137123236204,
    "C3_vs_C1_MATCH5_T2_overall_scheme_base_rate_change_pct": -7.989562016686814,
    "C3_T2_nullspace_reaction_command_reduction_pct": 9.98006962488238e-06,
    "energy_audit_relative_max_v0": 0.0789595238864667,
    "energy_audit_v0_diagnosis": (
        "W_ctrl was present in the v0 ledger; the residual was the "
        "first-order rectangle-rule ledger accumulated over a first-order "
        "state map (accounting/discretization defect, not physics)"
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_rows() -> list[dict[str, str]]:
    with SUMMARY_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _f(row, key):
    return float(row[key])


def _status(ok: bool) -> str:
    return "PASS" if ok else "REPEAT"


def _artifact_hashes(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        suffix = path.suffix.lower()
        text = suffix in {".json", ".yaml", ".yml", ".csv", ".txt", ".md", ".py"}
        row = {
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "raw_sha256": raw_sha256(path),
            "hash_mode_for_gate": "normalized_semantic_sha256" if text else "raw_sha256",
        }
        if text:
            row["normalized_semantic_sha256"] = normalized_semantic_sha256(path)
        rows.append(row)
    return rows


def main() -> int:
    required = [
        CONFIG_PATH,
        MATRIX_PATH,
        SUMMARY_PATH,
        RUN_PATH,
        BASELINE_PATH,
        TIMESERIES_PATH,
        COLLISION_TIMESERIES_PATH,
        FIGURE_PATH,
        MATRIX_CSV_PATH,
        TEST_PATH,
    ]
    missing = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in required
        if not path.exists()
    ]
    if missing:
        out = {
            "schema_version": "control-01-gate-v2",
            "task_id": "CTRL-01",
            "verdict": "BLOCKED",
            "reason": "required evidence missing",
            "missing": missing,
            "independent_red_team_status": "PENDING_REVIEW",
        }
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        GATE_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        return 2

    cfg = load_config()
    threshold = cfg["gate_thresholds"]
    rows = _load_rows()
    by_id = {row["scenario_id"]: row for row in rows}
    expected_ids = {
        f"{label}_{traj}"
        for label in VARIANT_LABELS
        for traj in ("T1", "T2", "T3")
    }
    numeric_keys = [
        "position_error_p95_m",
        "orientation_error_p95_rad",
        "base_attitude_peak_deg",
        "base_omega_integral_deg",
        "joint_limit_margin_min_rad",
        "task_sigma_min",
        "joint_speed_max_radps",
        "joint_acceleration_max_radps2",
        "joint_torque_max_Nm",
        "momentum_max_abs",
        "energy_audit_relative",
        "panel_tip_peak_mm",
        "panel_modal_energy_peak_J",
    ]
    nonfinite = []
    for row in rows:
        for key in numeric_keys:
            value = _f(row, key)
            if not np.isfinite(value):
                nonfinite.append({"scenario_id": row["scenario_id"], "field": key})
    with COLLISION_TIMESERIES_PATH.open(newline="", encoding="utf-8") as handle:
        collision_rows = list(csv.DictReader(handle))
    expected_t3_ids = {f"{label}_T3" for label in VARIANT_LABELS}
    collision_coverage_issues = []
    for scenario_id in sorted(expected_t3_ids):
        scenario_rows = [
            row for row in collision_rows if row["scenario_id"] == scenario_id
        ]
        expected_count = int(float(by_id[scenario_id]["n_steps"]))
        if len(scenario_rows) != expected_count:
            collision_coverage_issues.append(
                {
                    "scenario_id": scenario_id,
                    "issue": "time_sample_count",
                    "expected": expected_count,
                    "actual": len(scenario_rows),
                }
            )
            continue
        times = np.asarray([float(row["t_s"]) for row in scenario_rows])
        try:
            static = np.asarray(
                [float(row["static_margin_m"]) for row in scenario_rows]
            )
            target = np.asarray(
                [float(row["target_margin_m"]) for row in scenario_rows]
            )
            combined = np.asarray(
                [float(row["combined_margin_m"]) for row in scenario_rows]
            )
        except ValueError:
            collision_coverage_issues.append(
                {
                    "scenario_id": scenario_id,
                    "issue": "nonnumeric_margin_column",
                }
            )
            continue
        if (
            not np.allclose(
                np.diff(times),
                float(cfg["controller"]["sample_period_s"]),
                rtol=0.0,
                atol=1e-12,
            )
            or not np.all(np.isfinite(static))
            or not np.all(np.isfinite(target))
            or not np.all(np.isfinite(combined))
        ):
            collision_coverage_issues.append(
                {
                    "scenario_id": scenario_id,
                    "issue": "not_all_fixed_nodes_or_nonfinite_margin",
                }
            )
        if any(
            row["evaluation_status"] != "EVALUATED"
            or row["static_evaluation_status"] != "EVALUATED"
            or row["target_evaluation_status"] != "EVALUATED"
            or row["combined_evaluation_status"] != "EVALUATED"
            or row["plan_contract_status"] != COLLISION_PLAN_MATCHED
            for row in scenario_rows
        ):
            collision_coverage_issues.append(
                {
                    "scenario_id": scenario_id,
                    "issue": "collision_contract_semantics",
                }
            )
        if not np.allclose(
            combined, np.minimum(static, target), rtol=0.0, atol=1e-12
        ):
            collision_coverage_issues.append(
                {
                    "scenario_id": scenario_id,
                    "issue": "combined_margin_not_min_of_static_target",
                }
            )
        for column, values in (
            ("t3_collision_static_margin_min_m", static),
            ("t3_collision_target_margin_min_m", target),
            ("t3_collision_combined_margin_min_m", combined),
        ):
            if not np.isclose(
                float(by_id[scenario_id][column]),
                float(np.min(values)),
                rtol=0.0,
                atol=1e-12,
            ):
                collision_coverage_issues.append(
                    {
                        "scenario_id": scenario_id,
                        "issue": f"summary_minimum_mismatch:{column}",
                    }
                )
    observed_collision_ids = {row["scenario_id"] for row in collision_rows}
    if observed_collision_ids != expected_t3_ids:
        collision_coverage_issues.append(
            {
                "issue": "scenario_set",
                "expected": sorted(expected_t3_ids),
                "actual": sorted(observed_collision_ids),
            }
        )
    collision_coverage_ok = not collision_coverage_issues

    run = _load_json(RUN_PATH)
    equivalence = run.get("fast_plant_equivalence", {"status": "MISSING"})
    trigger_states = run.get("t3_trigger_states", {})
    trigger_state_issues = [
        label
        for label in VARIANT_LABELS
        if label not in trigger_states
        or not np.isclose(
            float(trigger_states[label]["t_abs_s"]),
            float(cfg["trajectories"]["T3"]["trigger"]["time_s"]),
            atol=1e-9,
        )
    ]
    evidence_complete = (
        set(by_id) == expected_ids
        and not nonfinite
        and collision_coverage_ok
        and not trigger_state_issues
    )
    baseline = _load_json(BASELINE_PATH)
    if (
        baseline["overall"] != "PASS"
        or not evidence_complete
        or equivalence.get("status") != "PASS"
    ):
        out = {
            "schema_version": "control-01-gate-v2",
            "task_id": "CTRL-01",
            "verdict": "BLOCKED",
            "baseline": baseline["overall"],
            "fast_plant_equivalence": equivalence,
            "missing_scenarios": sorted(expected_ids - set(by_id)),
            "unexpected_scenarios": sorted(set(by_id) - expected_ids),
            "nonfinite": nonfinite,
            "collision_coverage_issues": collision_coverage_issues,
            "t3_trigger_state_issues": trigger_state_issues,
            "independent_red_team_status": "PENDING_REVIEW",
        }
        GATE_PATH.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return 2

    anchors = run["open_loop_anchors"]
    flex_delta = abs(
        anchors["flexible_T1"]["peak_base_attitude_deviation_deg"]
        - anchors["sim11_frozen_flexible_peak_deg"]
    )
    rigid_delta = abs(
        anchors["rigid_T1"]["peak_base_attitude_deviation_deg"]
        - anchors["sim11_frozen_rigid_peak_deg"]
    )
    closed_delta = abs(
        _f(by_id["C1_T1"], "base_attitude_peak_deg")
        - anchors["sim11_frozen_flexible_peak_deg"]
    )
    closed_delta_c2_diag = abs(
        _f(by_id["C2_T1"], "base_attitude_peak_deg")
        - anchors["sim11_frozen_flexible_peak_deg"]
    )

    momentum_worst = max(_f(row, "momentum_max_abs") for row in rows)
    energy_worst = max(_f(row, "energy_audit_relative") for row in rows)
    c0_c1_ratio = (
        _f(by_id["C0_T2"], "position_error_p95_m")
        / _f(by_id["C1_T2"], "position_error_p95_m")
    )
    direction_model = CoupledModel()
    direction_q = np.asarray(cfg["trajectories"]["T2"]["q_initial_rad"], dtype=float)
    direction_eta = np.zeros(2 * direction_model.n_modes)
    direction_fk = direction_model.arm.fk(direction_q)
    direction_Jm = direction_model.arm.jacobian(direction_q, fk_out=direction_fk)
    direction_Jb = np.eye(6)
    direction_Jb[:3, 3:] = -skew(direction_fk["T_E"][:3, 3])
    direction_A = direction_model.momentum_matrix(direction_q, direction_eta)
    predicted_Jstar = direction_Jm - direction_Jb @ np.linalg.solve(
        direction_A[:, :6], direction_A[:, 6:12]
    )
    direction_identity_error = float(
        np.max(
            np.abs(
                direction_model.generalized_jacobian(direction_q, direction_eta)[
                    :, :6
                ]
                - predicted_Jstar
            )
        )
    )
    direction_identity_ok = direction_identity_error <= 1e-12

    # ---- GC1_D: preregistered incremental hypotheses -------------------------
    c2_improvement = 100.0 * (
        _f(by_id["C1_T2"], "position_error_p95_m")
        - _f(by_id["C2_T2"], "position_error_p95_m")
    ) / _f(by_id["C1_T2"], "position_error_p95_m")
    # Isolated nullspace effect: C3 vs C2_MATCH5 (same task, same feedforward).
    c3_isolated_base_rate_improvement = 100.0 * (
        _f(by_id["C2_MATCH5_T2"], "base_omega_integral_deg")
        - _f(by_id["C3_T2"], "base_omega_integral_deg")
    ) / _f(by_id["C2_MATCH5_T2"], "base_omega_integral_deg")
    c3_command_reduction = 100.0 * (
        _f(by_id["C3_T2"], "reaction_primary_peak")
        - _f(by_id["C3_T2"], "reaction_command_peak")
    ) / _f(by_id["C3_T2"], "reaction_primary_peak")
    c3_tracking_degradation = 100.0 * (
        _f(by_id["C3_T2"], "position_error_p95_m")
        - _f(by_id["C2_MATCH5_T2"], "position_error_p95_m")
    ) / _f(by_id["C2_MATCH5_T2"], "position_error_p95_m")
    # Context only (overall-scheme, feedforward-confounded, not the isolation basis)
    c3_overall_scheme_vs_c1_match5 = 100.0 * (
        _f(by_id["C1_MATCH5_T2"], "base_omega_integral_deg")
        - _f(by_id["C3_T2"], "base_omega_integral_deg")
    ) / _f(by_id["C1_MATCH5_T2"], "base_omega_integral_deg")
    c2_orientation_context = 100.0 * (
        _f(by_id["C1_T2"], "orientation_error_p95_rad")
        - _f(by_id["C2_T2"], "orientation_error_p95_rad")
    ) / _f(by_id["C1_T2"], "orientation_error_p95_rad")

    c3_threshold = float(
        threshold["c3_vs_c1_matched5_reaction_improvement_min_pct"]
    )
    gate_d_ok = (
        c2_improvement >= float(threshold["c2_vs_c1_t2_improvement_min_pct"])
        and c3_isolated_base_rate_improvement >= c3_threshold
        and c3_command_reduction >= c3_threshold
        and c3_tracking_degradation
        <= float(threshold["c3_tracking_degradation_max_pct"])
    )

    # ---- GC1_E: constraints --------------------------------------------------
    speed_limit = min(cfg["provisional_actuator_limits"]["joint_speed_abs_rad_per_s"])
    accel_limit = min(
        cfg["provisional_actuator_limits"]["joint_acceleration_abs_rad_per_s2"]
    )
    torque_limit = min(cfg["provisional_actuator_limits"]["joint_torque_abs_Nm"])
    t3_rows = [row for row in rows if row["trajectory"] == "T3"]
    collision_static_min = min(
        _f(row, "t3_collision_static_margin_min_m") for row in t3_rows
    )
    collision_target_min = min(
        _f(row, "t3_collision_target_margin_min_m") for row in t3_rows
    )
    collision_combined_min = min(
        _f(row, "t3_collision_combined_margin_min_m") for row in t3_rows
    )
    constraint_values = {
        "joint_limit_margin_min_rad": min(
            _f(row, "joint_limit_margin_min_rad") for row in rows
        ),
        "task_sigma_min": min(_f(row, "task_sigma_min") for row in rows),
        "joint_speed_max_radps": max(
            _f(row, "joint_speed_max_radps") for row in rows
        ),
        "joint_acceleration_max_radps2": max(
            _f(row, "joint_acceleration_max_radps2") for row in rows
        ),
        "joint_torque_max_Nm": max(_f(row, "joint_torque_max_Nm") for row in rows),
        "t3_collision_static_margin_min_m": collision_static_min,
        "t3_collision_target_margin_min_m": collision_target_min,
        "t3_collision_combined_margin_min_m": collision_combined_min,
        "t3_collision_margin_min_m": collision_combined_min,
    }
    per_scenario_constraints = {
        row["scenario_id"]: {
            "joint_limit_margin_min_rad": _f(row, "joint_limit_margin_min_rad"),
            "task_sigma_min": _f(row, "task_sigma_min"),
            "joint_speed_max_radps": _f(row, "joint_speed_max_radps"),
            "joint_acceleration_max_radps2": _f(
                row, "joint_acceleration_max_radps2"
            ),
            "joint_torque_max_Nm": _f(row, "joint_torque_max_Nm"),
            "t3_collision_combined_margin_min_m": (
                _f(row, "t3_collision_combined_margin_min_m")
                if row["trajectory"] == "T3"
                else None
            ),
        }
        for row in rows
    }
    constraints_ok = (
        constraint_values["joint_limit_margin_min_rad"]
        > float(threshold["joint_limit_margin_min_rad"])
        and constraint_values["task_sigma_min"]
        >= float(threshold["singular_value_min"])
        and constraint_values["joint_speed_max_radps"] <= speed_limit
        and constraint_values["joint_acceleration_max_radps2"] <= accel_limit
        and constraint_values["joint_torque_max_Nm"] <= torque_limit
        and constraint_values["t3_collision_combined_margin_min_m"]
        > float(threshold["t3_collision_margin_min_m"])
    )
    bounded_rows = [
        row
        for row in rows
        if row["method"] in ("C1", "C2", "C3")
    ]
    bounded_violations = [
        {
            "scenario_id": row["scenario_id"],
            "position_p95_m": _f(row, "position_error_p95_m"),
            "position_bound_m": _f(row, "analytic_position_bound_m"),
            "orientation_p95_rad": _f(row, "orientation_error_p95_rad"),
            "orientation_bound_rad": _f(row, "analytic_orientation_bound_rad"),
        }
        for row in bounded_rows
        if (
            _f(row, "position_error_p95_m")
            > _f(row, "analytic_position_bound_m")
            or _f(row, "orientation_error_p95_rad")
            > _f(row, "analytic_orientation_bound_rad")
        )
    ]

    expected_config_semantic = run["config_sha256"]
    expected_matrix_semantic = run["matrix_sha256"]
    config_raw = raw_sha256(CONFIG_PATH)
    matrix_raw = raw_sha256(MATRIX_PATH)
    config_semantic = normalized_semantic_sha256(CONFIG_PATH)
    matrix_semantic = normalized_semantic_sha256(MATRIX_PATH)
    hash_ok = (
        config_semantic == expected_config_semantic
        and matrix_semantic == expected_matrix_semantic
        and cfg["thresholds_widened"] is False
        and cfg["gains_tuned_on_plant"] is False
    )

    gates = {
        "GC1_A1_open_loop_flexible_anchor": {
            "status": _status(flex_delta <= float(threshold["anchor_open_loop_abs_deg"])),
            "delta_deg": flex_delta,
            "threshold_deg": float(threshold["anchor_open_loop_abs_deg"]),
        },
        "GC1_A2_closed_loop_C1_T1_anchor": {
            "status": _status(closed_delta <= float(threshold["anchor_closed_loop_abs_deg"])),
            "delta_deg": closed_delta,
            "threshold_deg": float(threshold["anchor_closed_loop_abs_deg"]),
            "C2_T1_delta_deg_plant_fidelity_diagnostic": closed_delta_c2_diag,
            "diagnostic_note": (
                "C2 (feedforward, near-exact tracking) probes plant fidelity; "
                "a C1 delta with a small C2 delta attributes the residual to "
                "frozen-gain feedback lag physics, not to the integrator"
            ),
        },
        "GC1_A3_open_loop_rigid_anchor": {
            "status": _status(rigid_delta <= float(threshold["anchor_rigid_abs_deg"])),
            "delta_deg": rigid_delta,
            "threshold_deg": float(threshold["anchor_rigid_abs_deg"]),
        },
        "GC1_B_conservation_and_energy": {
            "status": _status(
                momentum_worst <= float(threshold["momentum_abs"])
                and energy_worst <= float(threshold["energy_relative"])
            ),
            "momentum_max_abs": momentum_worst,
            "momentum_threshold": float(threshold["momentum_abs"]),
            "energy_audit_relative_max": energy_worst,
            "energy_threshold": float(threshold["energy_relative"]),
            "momentum_subcheck": _status(
                momentum_worst <= float(threshold["momentum_abs"])
            ),
            "energy_subcheck": _status(
                energy_worst <= float(threshold["energy_relative"])
            ),
            "energy_ledger": {
                "v0_defect_diagnosis": PREVIOUS_LOOP_NEGATIVE_RESULTS[
                    "energy_audit_v0_diagnosis"
                ],
                "remediation": (
                    "first-order-hold command ramp + per-interval DOP853 "
                    "integration of state and W_ctrl/damping ledgers "
                    "(threshold unchanged at 1e-9)"
                ),
            },
        },
        "GC1_C_C0_C1_differentiation": {
            "status": _status(
                c0_c1_ratio >= float(threshold["c0_c1_t2_p95_ratio_min"])
                and direction_identity_ok
            ),
            "T2_position_p95_ratio_C0_over_C1": c0_c1_ratio,
            "threshold_ratio": float(threshold["c0_c1_t2_p95_ratio_min"]),
            "direction_map_identity": "Jstar-Jm=-Jb*Hbb^-1*Hbm",
            "direction_map_identity_max_abs_error": direction_identity_error,
            "direction_map_identity_threshold": 1e-12,
            "direction_matches_Jstar_model_correction": direction_identity_ok,
        },
        "GC1_D_incremental_effectiveness": {
            "status": _status(gate_d_ok),
            "C2_vs_C1_T2_position_improvement_pct": c2_improvement,
            "C2_threshold_pct": float(
                threshold["c2_vs_c1_t2_improvement_min_pct"]
            ),
            "C2_vs_C1_T2_orientation_improvement_context_pct": (
                c2_orientation_context
            ),
            "isolated_nullspace_comparator": "C2_MATCH5",
            "C3_vs_C2_MATCH5_T2_base_rate_improvement_pct": (
                c3_isolated_base_rate_improvement
            ),
            "C3_vs_C2_MATCH5_isolates_nullspace_effect": True,
            "C3_vs_C1_MATCH5_T2_overall_scheme_base_rate_change_context_pct": (
                c3_overall_scheme_vs_c1_match5
            ),
            "C3_T2_nullspace_reaction_command_reduction_pct": c3_command_reduction,
            "C3_threshold_pct": c3_threshold,
            "C3_threshold_config_key": (
                "c3_vs_c1_matched5_reaction_improvement_min_pct "
                "(frozen value reapplied to the preregistered C2_MATCH5 "
                "comparator per repeat preregistration R-3)"
            ),
            "C3_tracking_degradation_vs_C2_MATCH5_pct": c3_tracking_degradation,
            "C3_tracking_degradation_max_pct": float(
                threshold["c3_tracking_degradation_max_pct"]
            ),
            "previous_loop_negative_results_preserved": (
                PREVIOUS_LOOP_NEGATIVE_RESULTS
            ),
            "negative_result_published": True,
        },
        "GC1_E_constraints": {
            "status": _status(constraints_ok),
            "values": constraint_values,
            "per_scenario": per_scenario_constraints,
            "collision_evaluation": {
                "status": _status(
                    collision_coverage_ok
                    and collision_combined_min
                    > float(threshold["t3_collision_margin_min_m"])
                ),
                "static_status": "EVALUATED",
                "target_status": "EVALUATED",
                "combined_status": "EVALUATED",
                "plan_contract_status": COLLISION_PLAN_MATCHED,
                "all_fixed_node_coverage": collision_coverage_ok,
                "coverage_issues": collision_coverage_issues,
                "trigger": cfg["trajectories"]["T3"]["trigger"],
            },
            "conservative_global_limits": {
                "joint_speed_radps": speed_limit,
                "joint_acceleration_radps2": accel_limit,
                "joint_torque_Nm": torque_limit,
                "singular_value_min": float(threshold["singular_value_min"]),
                "collision_margin_m": float(
                    threshold["t3_collision_margin_min_m"]
                ),
            },
            "T1_anchor_joint_limit_conflict_preregistered": True,
        },
        "GC1_F_bounded_error_C1_C2_C3": {
            "status": _status(not bounded_violations),
            "violations": bounded_violations,
            "C0_excluded_per_red_team_T6": True,
        },
        "GC1_G_hash_lock": {
            "status": _status(hash_ok),
            "text_hash_mode_for_gate": "normalized_semantic_sha256",
            "binary_hash_mode_for_gate": "raw_sha256",
            "config": {
                "raw_sha256": config_raw,
                "normalized_semantic_sha256": config_semantic,
                "expected_normalized_semantic_sha256": expected_config_semantic,
            },
            "matrix": {
                "raw_sha256": matrix_raw,
                "normalized_semantic_sha256": matrix_semantic,
                "expected_normalized_semantic_sha256": expected_matrix_semantic,
            },
            "thresholds_widened": cfg["thresholds_widened"],
            "gains_tuned_on_plant": cfg["gains_tuned_on_plant"],
        },
        "GC1_H_fast_plant_ssot_equivalence": {
            **{k: v for k, v in equivalence.items() if k != "status"},
            "cross_check_result": equivalence.get("status"),
            "status": _status(equivalence.get("status") == "PASS"),
        },
    }
    gate_statuses = [gate["status"] for gate in gates.values()]
    verdict = "PASS" if all(status == "PASS" for status in gate_statuses) else "REPEAT"
    assert verdict in GATE_RESULT_ENUM
    artifact_rows = _artifact_hashes(required)
    HASH_PATH.write_text(
        json.dumps(
            {
                "schema_version": "control-01-artifacts-v1",
                "text_hash_mode_for_gate": "normalized_semantic_sha256",
                "binary_hash_mode_for_gate": "raw_sha256",
                "artifacts": artifact_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output = {
        "schema_version": "control-01-gate-v2",
        "task_id": "CTRL-01",
        "remediation_loop": "CTRL-01-R",
        "repeat_preregistration": (
            "10_research/partner_requirement_closure/wave1_repeat/"
            "repeat_preregistration.md"
        ),
        "verdict": verdict,
        "next_stage_authorized": verdict == "PASS",
        "tests_are_not_gate": True,
        "PROVISIONAL_PARAMS": True,
        "independent_red_team_status": "PENDING_REVIEW",
        "evidence_complete": evidence_complete,
        "scenario_count": len(rows),
        "gates": gates,
        "confirmed_results": {
            "momentum_conservation_all_scenarios": momentum_worst,
            "energy_audit_relative_max": energy_worst,
            "C0_C1_T2_machine_differentiation_ratio": c0_c1_ratio,
            "C2_T2_position_increment_pct": c2_improvement,
            "C2_T2_orientation_increment_context_pct": c2_orientation_context,
            "C3_vs_C2_MATCH5_T2_isolated_base_rate_improvement_pct": (
                c3_isolated_base_rate_improvement
            ),
            "C3_T2_nullspace_command_reduction_pct": c3_command_reduction,
            "T3_static_collision_all_fixed_nodes_min_m": collision_static_min,
            "T3_target_collision_all_fixed_nodes_min_m": collision_target_min,
            "T3_combined_collision_all_fixed_nodes_min_m": collision_combined_min,
            "T3_collision_plan_contract_status": COLLISION_PLAN_MATCHED,
            "T1_frame_contract": cfg["frame_contract"]["t1_reference"],
            "T2_rate_before_capture_deg_per_s": cfg["trajectories"]["T2"][
                "target_tumble_rate_before_capture_deg_per_s"
            ],
            "T3_trigger_time_s": float(
                cfg["trajectories"]["T3"]["trigger"]["time_s"]
            ),
            "C3_pose6_contract_error": cfg["controller"][
                "c3_pose_6d_error_code"
            ],
        },
        "claim_scope": {
            "allowed": [
                "C0 and C1 are machine-distinguishable on frozen T2",
                "all frozen runs satisfy the <=1e-12 momentum audit",
                "the discrete energy ledger closes to <=1e-9 relative when it does",
                "C2/C3 preregistered incremental hypotheses adjudicated as recorded",
                "C3 versus C2_MATCH5 isolates the nullspace term on frozen T2",
                "T3 static, target and combined keep-out margins were evaluated "
                "at every 0.01 s node under the frozen T2 t=15 s trigger and "
                "const-omega continuation",
            ],
            "forbidden": [
                "general controller superiority",
                "C3 versus C1_MATCH5 isolates the nullspace effect",
                "between-node continuous collision clearance",
                "absolute flexible response hardware meaning",
                "flight or hardware performance",
                "promotion to the next stage while verdict is not PASS",
            ],
        },
        "artifact_manifest": HASH_PATH.relative_to(REPO_ROOT).as_posix(),
    }
    GATE_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": verdict,
                "gate_statuses": {
                    name: gate["status"] for name, gate in gates.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
