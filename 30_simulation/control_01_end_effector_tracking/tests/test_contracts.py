import hashlib
import json

import numpy as np

from contracts import (
    ControllerContractError,
    load_config,
    load_matrix,
    method_contract,
    normalized_semantic_sha256,
)
from repo_imports import CONFIG_PATH, MATRIX_PATH, RESULTS_DIR


def test_r1_fix_first_contract():
    cfg = load_config()
    assert cfg["trajectories"]["T2"][
        "target_tumble_rate_before_capture_deg_per_s"
    ] == 3.0
    wheel = cfg["wheel_envelope_interface_only"]
    assert wheel["per_axis_box_abs_Nms"] == [0.1, 0.1, 0.1]
    assert wheel["per_axis_occupancy_pct"] == 89.1
    assert cfg["frame_contract"]["momentum_reference_point"] == "base_origin_S"
    assert cfg["repository_timing_evidence"]["status"] == (
        "PROCEDURAL_ONLY_CONFIG_AND_RESULTS_COMMITTED_TOGETHER"
    )
    collision = cfg["t3_collision_contract_audit"]
    assert collision["plan_contract_status"] == "MATCHED"
    assert collision["target_and_combined_gate_status"] == "EVALUATED"
    trigger = cfg["trajectories"]["T3"]["trigger"]
    assert trigger["time_s"] == 15.0
    assert trigger["method_specific"] is True
    assert trigger["target_phase_continuation"] is True
    remediation = cfg["repeat_remediation"]
    assert remediation["all_gate_thresholds_unchanged"] is True
    thresholds = cfg["gate_thresholds"]
    assert thresholds["energy_relative"] == 1.0e-9
    assert thresholds["momentum_abs"] == 1.0e-12
    assert thresholds["anchor_closed_loop_abs_deg"] == 0.05
    assert thresholds["singular_value_min"] == 1.0e-4
    return 0.0


def test_matrix_is_frozen_and_fair():
    matrix = load_matrix()
    assert matrix["main_matrix"]["methods"] == ["C0", "C1", "C2", "C3"]
    assert matrix["main_matrix"]["trajectories"] == ["T1", "T2", "T3"]
    assert matrix["main_matrix"]["task_mode"]["C3"] == "approach_5d"
    assert matrix["supplemental_matched_task"]["task_mode"] == "approach_5d"
    match5 = matrix["supplemental_matched_feedforward_task"]
    assert match5["label"] == "C2_MATCH5"
    assert match5["method"] == "C2"
    assert match5["task_mode"] == "approach_5d"
    assert match5["isolated_nullspace_comparator_for"] == "C3"
    assert matrix["repeat_revision"]["adds"] == ["C2_MATCH5"]
    assert matrix["result_policy"]["no_per_method_gain_tuning"] is True
    return 0.0


def test_c3_pose6_refusal():
    cfg = load_config()
    try:
        method_contract("C3", "pose_6d", cfg)
    except ControllerContractError as exc:
        assert exc.code == "TASK_NULLITY_ZERO"
        return 0.0
    raise AssertionError("C3 pose_6d request was not refused")


def test_gain_bandwidth_rule():
    cfg = load_config()
    gain = max(
        cfg["controller"]["position_gain_per_s"],
        cfg["controller"]["orientation_gain_per_s"],
    )
    upper = cfg["controller"]["gain_rule"]["resulting_upper_bound_rad_per_s"]
    assert gain <= upper
    assert cfg["gains_tuned_on_plant"] is False
    assert cfg["thresholds_widened"] is False
    return float(upper - gain)


def test_text_hash_lock_is_crlf_portable():
    run = json.loads(
        (RESULTS_DIR / "control_01_run_summary.json").read_text(encoding="utf-8")
    )
    for path, key in (
        (CONFIG_PATH, "config_sha256"),
        (MATRIX_PATH, "matrix_sha256"),
    ):
        lf_bytes = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        simulated_crlf = lf_bytes.replace(b"\n", b"\r\n")
        crlf_semantic = hashlib.sha256(
            simulated_crlf.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        ).hexdigest()
        assert crlf_semantic == run[key]
        assert normalized_semantic_sha256(path) == run[key]
    return 0.0
