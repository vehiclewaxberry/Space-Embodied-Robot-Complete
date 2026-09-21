import csv
import json

import numpy as np

from contracts import load_config
from repo_imports import CoupledModel, RESULTS_DIR
from collision_evidence import (
    CollisionEvidenceUnavailable,
    build_t2_target_scene,
    evaluate_t3_collision,
)

import collision


EXPECTED_T3_IDS = {
    "C0_T3",
    "C1_T3",
    "C2_T3",
    "C3_T3",
    "C1_MATCH5_T3",
    "C2_MATCH5_T3",
}
PLAN_MATCHED = "MATCHED_T2_T15_TRIGGER_AND_CONST_OMEGA_CONTINUATION"


def test_frozen_target_primitive_constructs_at_t2_pose_only():
    cfg = load_config()
    model = CoupledModel()
    scene = build_t2_target_scene(model, cfg)
    primitive = scene["target_primitive_t0"]
    assert scene["target_id"] == "target_satellite_v0"
    assert scene["primary_grasp_id"] == "launch_adapter_ring"
    assert np.allclose(primitive["half_extents_m"], [0.23, 0.313, 0.213])
    assert scene["t2_pose_position_residual_m"] < 1e-6
    assert scene["target_grasp_placement_residual_m"] < 1e-12
    assert scene["target_rotation_orthogonality_max_abs"] < 1e-10
    assert abs(scene["target_rotation_determinant"] - 1.0) < 1e-10
    q0 = np.asarray(cfg["trajectories"]["T2"]["q_initial_rad"], dtype=float)
    margin = collision.configuration_margin(
        model.arm,
        q0,
        primitive,
        scene["capture_point_I_m"],
        geo=scene["geometry"],
    )
    assert np.isfinite(margin)
    assert all(
        not source["path"].startswith(("F:/", "C:/"))
        for source in scene["sources"].values()
    )
    return max(
        scene["t2_pose_position_residual_m"],
        scene["target_grasp_placement_residual_m"],
    )


def test_t3_collision_evaluates_all_margins_under_frozen_trigger():
    cfg = load_config()
    model = CoupledModel()
    q0 = np.asarray(cfg["trajectories"]["T2"]["q_initial_rad"], dtype=float)
    t_grid = np.arange(4, dtype=float) * cfg["controller"]["sample_period_s"]
    result = evaluate_t3_collision(
        model,
        cfg,
        t_grid,
        np.repeat(q0[None, :], len(t_grid), axis=0),
        np.zeros((len(t_grid), 3)),
        np.repeat(
            np.array([[1.0, 0.0, 0.0, 0.0]]), len(t_grid), axis=0
        ),
        t_offset_s=float(cfg["trajectories"]["T3"]["trigger"]["time_s"]),
    )
    assert result["evaluation_status"] == "EVALUATED"
    assert result["plan_contract_status"] == PLAN_MATCHED
    assert result["static_evaluation_status"] == "EVALUATED"
    assert result["target_evaluation_status"] == "EVALUATED"
    assert result["combined_evaluation_status"] == "EVALUATED"
    assert result["time_samples"] == len(t_grid)
    assert result["static_time_coverage"] == "ALL_FIXED_INTEGRATION_NODES"
    assert result["target_time_coverage"] == "ALL_FIXED_INTEGRATION_NODES"
    for key in ("static_margin_m", "target_margin_m", "combined_margin_m"):
        assert len(result[key]) == len(t_grid)
        assert np.all(np.isfinite(result[key]))
    assert np.allclose(
        result["combined_margin_m"],
        np.minimum(result["static_margin_m"], result["target_margin_m"]),
        rtol=0.0,
        atol=1e-15,
    )
    assert np.isclose(
        result["target_phase_at_t3_start_deg"],
        3.0 * float(cfg["trajectories"]["T3"]["trigger"]["time_s"]),
    )
    return float(np.min(result["combined_margin_m"]))


def test_t3_collision_fails_closed_on_wrong_trigger_offset():
    cfg = load_config()
    model = CoupledModel()
    q0 = np.asarray(cfg["trajectories"]["T2"]["q_initial_rad"], dtype=float)
    t_grid = np.arange(3, dtype=float) * cfg["controller"]["sample_period_s"]
    try:
        evaluate_t3_collision(
            model,
            cfg,
            t_grid,
            np.repeat(q0[None, :], len(t_grid), axis=0),
            np.zeros((len(t_grid), 3)),
            np.repeat(
                np.array([[1.0, 0.0, 0.0, 0.0]]), len(t_grid), axis=0
            ),
            t_offset_s=0.0,
        )
    except CollisionEvidenceUnavailable:
        return 0.0
    raise AssertionError("wrong trigger offset was not refused")


def test_frozen_results_record_all_t3_collision_nodes():
    collision_path = RESULTS_DIR / "control_01_collision_timeseries.csv"
    summary_path = RESULTS_DIR / "control_01_summary.csv"
    with collision_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with summary_path.open(newline="", encoding="utf-8") as handle:
        summaries = {
            row["scenario_id"]: row for row in csv.DictReader(handle)
        }
    assert {row["scenario_id"] for row in rows} == EXPECTED_T3_IDS
    worst = 0.0
    for scenario_id in EXPECTED_T3_IDS:
        scenario_rows = [row for row in rows if row["scenario_id"] == scenario_id]
        assert len(scenario_rows) == 501
        times = np.asarray([float(row["t_s"]) for row in scenario_rows])
        static = np.asarray(
            [float(row["static_margin_m"]) for row in scenario_rows]
        )
        target = np.asarray(
            [float(row["target_margin_m"]) for row in scenario_rows]
        )
        combined = np.asarray(
            [float(row["combined_margin_m"]) for row in scenario_rows]
        )
        assert np.allclose(np.diff(times), 0.01, rtol=0.0, atol=1e-12)
        assert all(
            row["evaluation_status"] == "EVALUATED"
            and row["plan_contract_status"] == PLAN_MATCHED
            and row["static_evaluation_status"] == "EVALUATED"
            and row["target_evaluation_status"] == "EVALUATED"
            and row["combined_evaluation_status"] == "EVALUATED"
            for row in scenario_rows
        )
        assert np.allclose(
            combined, np.minimum(static, target), rtol=0.0, atol=1e-12
        )
        for column, values in (
            ("t3_collision_static_margin_min_m", static),
            ("t3_collision_target_margin_min_m", target),
            ("t3_collision_combined_margin_min_m", combined),
        ):
            summary_min = float(summaries[scenario_id][column])
            assert np.isclose(
                summary_min, np.min(values), rtol=0.0, atol=1e-12
            )
        worst = max(worst, abs(float(np.min(combined))))
    gate = json.loads(
        (RESULTS_DIR / "control_01_gate_check.json").read_text(encoding="utf-8")
    )
    evaluation = gate["gates"]["GC1_E_constraints"]["collision_evaluation"]
    assert evaluation["target_status"] == "EVALUATED"
    assert evaluation["combined_status"] == "EVALUATED"
    assert evaluation["plan_contract_status"] == PLAN_MATCHED
    return worst
