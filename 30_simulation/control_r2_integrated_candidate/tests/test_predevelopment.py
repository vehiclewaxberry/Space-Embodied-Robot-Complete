from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys


MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parents[1]
SRC = MODULE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from predevelopment import (  # noqa: E402
    CONFIG_PATH,
    RESULTS_DIR,
    load_json_strict,
    sha256_file,
    validate_source_pins,
)
from unified_r2_adapters import (  # noqa: E402
    flexibility_static_screen_once,
    validate_joint_state_limits,
    validate_locked_prismatic_state,
)


def test_all_source_pins_match() -> None:
    config = load_json_strict(CONFIG_PATH)
    report = validate_source_pins(REPO_ROOT, config)
    assert report["hash_mismatch_count"] == 0
    assert report["match_count"] == report["pin_count"]


def test_ctrl01_probe_local_execution_closure_is_hash_pinned() -> None:
    config = load_json_strict(CONFIG_PATH)
    pin_ids = {item["id"] for item in config["source_pins"]}
    expected = {
        "accepted_b601_urdf",
        "accepted_fk_module_frozen",
        "geometry_frame_tree",
        "ctrl01_current_config",
        "ctrl01_probe_contracts_source",
        "ctrl01_probe_controller_source",
        "ctrl01_probe_repo_imports_source",
        "ctrl01_probe_trajectories_source",
        "sim11_probe_config_loader_source",
        "sim11_probe_coupled_dynamics_source",
        "sim11_probe_ffr_panel_source",
        "probe_rigid_body_source",
        "sim11_probe_model_card",
        "sim11_probe_flexible_appendage",
        "sim11_probe_target_models",
        "sim11_probe_capture_interface",
        "sim11_probe_mass_inertia_budget",
    }
    assert expected <= pin_ids


def test_builder_is_deterministic_and_fail_closed() -> None:
    command = [
        sys.executable,
        "-B",
        str(SRC / "build_predevelopment_gate.py"),
        "--repo-root",
        str(REPO_ROOT),
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True)
    paths = [
        RESULTS_DIR / "CTRL_R2_MODEL_BINDING_V1.json",
        RESULTS_DIR / "CTRL_R2_NOMINAL_DLS_PROBE_V1.json",
        RESULTS_DIR / "CTRL_R2_UNIFIED_8DOF_STATIC_PROBE_V1.json",
        RESULTS_DIR / "CTRL_R2_DUAL_WING_14MODE_STATIC_FLEX_SCREEN_V1.json",
        RESULTS_DIR / "CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_AUDIT_V1.json",
        RESULTS_DIR / "CTRL01_FAILURE_CLASSIFICATION_V1.json",
        RESULTS_DIR / "CURRENT_FRONTIER_ODR60_CTRL_V1.json",
        RESULTS_DIR / "CTRL_R2_PREDEVELOPMENT_GATE_V1.json",
    ]
    first = {path.name: sha256_file(path) for path in paths}
    subprocess.run(command, cwd=REPO_ROOT, check=True)
    second = {path.name: sha256_file(path) for path in paths}
    assert first == second

    gate = load_json_strict(RESULTS_DIR / "CTRL_R2_PREDEVELOPMENT_GATE_V1.json")
    assert gate["candidate_package_complete"] is True
    assert gate["technical_predevelopment_complete"] is False
    assert gate["current_replay_clean"] is False
    assert gate["current_replay_evidence_class"] == "RECORDED_AUDIT_NOT_GATE"
    assert gate["current_replay_gate_qualified"] is False
    replay_integrity = gate["recorded_replay_audit_integrity"]
    assert replay_integrity["bookkeeping_valid"] is True
    assert replay_integrity["per_run_arithmetic_valid"] is True
    assert replay_integrity["declared_collected_counts_match_total"] is True
    assert replay_integrity["new_work_run_ids"] == [
        "CTRL_R2_PREDEVELOPMENT",
        "CURRENT_AUTHORITY_INDEX",
    ]
    assert replay_integrity["new_work_tests_passed"] == 19
    assert replay_integrity["new_work_tests_total"] == 19
    assert replay_integrity["gate_qualified"] is False
    assert gate["integrated_control_ready"] is False
    assert gate["collision_aware_execution_credit"] is False
    assert gate["non_abort_execution_credit"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False
    assert gate["authorized_claim_ceiling"].startswith(
        "CONTROL_PREDEVELOPMENT_CANDIDATE_BUILT_WITH_DECLARED_LIMITS"
    )
    assert "CONTROL_PREDEVELOPMENT_COMPLETE" not in gate["authorized_claim_ceiling"]
    assert gate["summary"]["candidate_packaging_criteria_satisfied"] == 9
    assert all("pass_for_predevelopment" not in item for item in gate["criteria"])
    assert all(item["pass_for_candidate_packaging"] for item in gate["criteria"])
    assert "UNIFIED_R2_8DOF_TO_CTRL01_6R_CONTROL_ADAPTER_NOT_INTEGRATED" not in gate["remaining_holds"]
    assert "E23_DUAL_WING_14MODE_TO_CTRL01_LEGACY_FLEX_ADAPTER_NOT_INTEGRATED" not in gate["remaining_holds"]
    assert "UNIFIED_R2_TORQUE_LEVEL_CONSTRAINED_PRISMATIC_REACTION_SOLVER_NOT_IMPLEMENTED" in gate["remaining_holds"]
    assert "DUAL_WING_14MODE_FULL_COUPLED_MISSION_TIME_HISTORY_NOT_INTEGRATED" in gate["remaining_holds"]


def test_probe_and_negative_result_semantics() -> None:
    probe = load_json_strict(RESULTS_DIR / "CTRL_R2_NOMINAL_DLS_PROBE_V1.json")
    failure = load_json_strict(RESULTS_DIR / "CTRL01_FAILURE_CLASSIFICATION_V1.json")
    assert probe["pass"] is True
    assert probe["determinism"]["bitwise_canonical_equal"] is True
    assert probe["scope"].startswith("NONCONTACT_MODEL_LEVEL")
    assert failure["source_verdict"] == "REPEAT"
    assert failure["reproduction"]["status"] == "NOT_CLAIMED_REORG04_NORMALIZED_HASH_DRIFT"
    assert failure["reproduction"]["config_matches_frozen_gate"] is False
    assert failure["reproduction"]["matrix_matches_frozen_gate"] is False
    assert failure["categories"]["numerical"]["state"] == "NOT_SUPPORTED_AS_ROOT_CAUSE"
    assert failure["next_stage_authorized"] is False


def test_e23_anchor_binding_is_scenario_labeled_and_does_not_inherit_sim10() -> None:
    gate = load_json_strict(RESULTS_DIR / "CTRL_R2_PREDEVELOPMENT_GATE_V1.json")
    c5 = next(item for item in gate["criteria"] if item["id"] == "C5")
    assert c5["source"] == "E23_R2_FULL_FLEX_COUPLED_GATE_V1.key_metrics"
    assert c5["anchors"]["22kg_initial_target_rate_dps"] == 0.5
    assert c5["anchors"]["150kg_initial_target_rate_dps"] == 3.0
    assert c5["sim10_gate_inheritance"] is False
    assert "NOT_SIM10_ANCHOR_EQUIVALENCE" in c5["scope"]


def test_frontier_does_not_invent_odr60_authority() -> None:
    frontier = load_json_strict(RESULTS_DIR / "CURRENT_FRONTIER_ODR60_CTRL_V1.json")
    mechanical = frontier["mechanical"]
    assert mechanical["odr60_decision_absent"] is True
    assert mechanical["option_a_owner_selection_present"] is False
    assert mechanical["pair_evaluation_authorized"] is False
    assert mechanical["edge_evaluation_authorized"] is False
    assert mechanical["path_search_authorized"] is False
    assert mechanical["path_search_executed"] is False


def test_unified_r2_static_adapter_is_locked_and_separates_momentum_residuals() -> None:
    result = load_json_strict(RESULTS_DIR / "CTRL_R2_UNIFIED_8DOF_STATIC_PROBE_V1.json")
    assert result["pass"] is True
    assert result["determinism"]["bitwise_canonical_equal"] is True
    first = result["first"]
    assert first["joint_order"][-2:] == ["gripper_joint1", "gripper_joint2"]
    assert first["locked_prismatic_contract"]["qP_m"] == [0.03575, 0.03575]
    assert first["locked_prismatic_contract"]["qP_limits_source"] == "HASH_PINNED_UNIFIED_R2_URDF"
    assert first["locked_prismatic_contract"]["declared_config_limits_match_URDF"] is True
    assert first["locked_prismatic_contract"]["qdotP_m_s"] == [0.0, 0.0]
    assert first["checks"]["joint_types_exact_6R2P"] is True
    assert first["checks"]["all_8_joint_limits_finite"] is True
    assert first["checks"]["q8_inside_URDF_limits"] is True
    assert first["checks"]["qP_limits_match_URDF"] is True
    assert first["checks"]["qP_inside_URDF_limits"] is True
    limit_audit = first["urdf_joint_limit_audit"]
    assert limit_audit["source"] == "HASH_PINNED_UNIFIED_R2_URDF"
    assert limit_audit["all_8_inside"] is True
    assert len(limit_audit["joints"]) == 8
    assert all(item["inside_inclusive_limits"] for item in limit_audit["joints"])
    assert first["mass_blocks"]["Hbb_shape"] == [6, 6]
    assert first["mass_blocks"]["Hbm_shape"] == [6, 8]
    assert first["locked_6R_adapter"]["mechanical_connection_shape"] == [6, 6]
    assert first["locked_6R_adapter"]["reduced_mass_locked6_shape"] == [6, 6]
    residual = first["zero_momentum_diagnostic"]
    assert residual["linear_and_angular_residuals_not_mixed"] is True
    assert residual["linear_momentum_residual_norm_kg_m_s"] <= 1e-12
    assert residual["angular_momentum_residual_norm_N_m_s"] <= 1e-12
    assert first["execution_guards"] == {
        "backend_advance_called": False,
        "collision_query_called": False,
        "contact_called": False,
        "path_search_called": False,
    }


def test_unified_r2_prismatic_limit_guard_fails_closed() -> None:
    limits = [[0.0, 0.0715], [0.0, 0.0715]]
    assert validate_locked_prismatic_state([0.03575, 0.03575], limits).tolist() == [0.03575, 0.03575]
    try:
        validate_locked_prismatic_state([0.03575, -0.001], limits)
    except ValueError as exc:
        assert "FAIL_CLOSED" in str(exc)
    else:
        raise AssertionError("out-of-limit prismatic state was not rejected")

    q8 = [0.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.03575, 0.03575]
    limits8 = [
        [-2.8, 2.8],
        [-3.14, 0.0],
        [-3.14, 0.0],
        [-1.87, 1.57],
        [-1.57, 1.57],
        [-3.14, 3.14],
        [0.0, 0.0715],
        [0.0, 0.0715],
    ]
    q8[0] = 2.800001
    try:
        validate_joint_state_limits(q8, limits8, [f"joint_{i}" for i in range(8)])
    except ValueError as exc:
        assert str(exc) == "JOINT_STATE_OUTSIDE_URDF_LIMITS_FAIL_CLOSED"
    else:
        raise AssertionError("out-of-range revolute joint state was accepted")


def test_dual_wing_flex_overlay_order_gamma_and_domain_contract() -> None:
    result = load_json_strict(
        RESULTS_DIR / "CTRL_R2_DUAL_WING_14MODE_STATIC_FLEX_SCREEN_V1.json"
    )
    assert result["pass"] is True
    assert result["determinism"]["bitwise_canonical_equal"] is True
    first = result["first"]
    assert first["wing_order"] == ["LEFT", "RIGHT"]
    assert len(first["combined_mode_order"]) == 14
    assert first["gamma_semantics"]["left_right_combined_gamma_distinct"] is True
    assert first["gamma_semantics"]["left_right_rotation_gamma_equal"] is False
    assert first["frame_semantics"]["expressed_in"] == "SPACECRAFT_S_FRAME"
    assert first["excitation_authority"] == "ARBITRARY_NONZERO_DIAGNOSTIC_NOT_TASK_BOUND"
    assert first["mission_flex_robustness_evaluated"] is False
    assert first["frame_semantics"]["base_linear_acceleration_S_m_s2"] != [0.0, 0.0, 0.0]
    assert first["frame_semantics"]["base_angular_acceleration_S_rad_s2"] != [0.0, 0.0, 0.0]
    assert [corner["corner"] for corner in first["corners"]] == ["LOW", "NOMINAL", "HIGH"]
    for corner in first["corners"]:
        assert corner["M14_shape"] == [14, 14]
        assert corner["K14_shape"] == [14, 14]
        assert [wing["wing"] for wing in corner["wings"]] == ["LEFT", "RIGHT"]
        assert all(wing["diagnostic_modal_force_norm"] > 0.0 for wing in corner["wings"])
        assert all(wing["pass"] for wing in corner["wings"])
    assert first["e23_pass_inheritance"] == "NOT_INHERITED"
    assert first["round4_gate_pass_inheritance"] == "NOT_INHERITED"


def test_dual_wing_flex_overlay_fails_closed_outside_linearity_domain() -> None:
    config = load_json_strict(CONFIG_PATH)
    out = flexibility_static_screen_once(
        REPO_ROOT,
        config,
        eta_override_by_wing={"LEFT": [1.0] * 7, "RIGHT": [1.0] * 7},
    )
    assert out["pass"] is False
    assert out["checks"]["all_per_wing_operator_limits_satisfied"] is False
    for corner in out["corners"]:
        assert all(
            wing["state"] == "FAIL_CLOSED_OUT_OF_LINEAR_ROM_DOMAIN"
            for wing in corner["wings"]
        )


def test_actuator_intake_is_complete_null_pending_and_not_a_model() -> None:
    audit = load_json_strict(
        RESULTS_DIR / "CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_AUDIT_V1.json"
    )
    assert audit["minimum_intake_schema_complete"] is True
    assert audit["semantic_requirements_complete"] is False
    assert len(audit["known_missing_requirement_groups"]) >= 6
    assert audit["hardware_measurements_complete"] is False
    assert audit["hardware_model_valid"] is False
    assert audit["hold"].startswith("MEASUREMENT_PENDING")
    assert len(audit["joint_record_checks"]) == 8
    assert all(item["all_measurement_values_null"] for item in audit["joint_record_checks"])
    assert all(
        item["urdf_velocity_literal_unit_undeclared_and_nonphysical"]
        for item in audit["joint_record_checks"]
    )


def test_manifest_rows_match_files() -> None:
    manifest = RESULTS_DIR / "CTRL_R2_PREDEVELOPMENT_SHA256_V1.csv"
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    row_paths = {row["path"] for row in rows}
    expected_paths = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in MODULE_ROOT.rglob("*")
        if path.is_file()
        and path != manifest
        and "__pycache__" not in path.parts
    }
    assert row_paths == expected_paths
    for row in rows:
        path = REPO_ROOT / row["path"]
        assert path.stat().st_size == int(row["bytes"])
        assert sha256_file(path) == row["sha256"]


def test_json_outputs_have_no_nonfinite_tokens() -> None:
    for path in RESULTS_DIR.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "NaN" not in text
        assert "Infinity" not in text
        json.loads(text)
