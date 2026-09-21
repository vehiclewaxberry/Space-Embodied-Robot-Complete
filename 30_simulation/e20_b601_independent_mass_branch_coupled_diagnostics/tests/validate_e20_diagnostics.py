"""Independent fail-closed validator for e20.

Every positive and deepcopy-mutation negative control is evaluated through the
same ``gate_safe(bundle)`` predicate.  The validation report is intentionally
excluded from the e20 output manifest to avoid recursive hashing.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml


MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parents[1]
RESULTS_ROOT = MODULE_ROOT / "results"
PREFIX = "30_simulation/e20_b601_independent_mass_branch_coupled_diagnostics"
GENERATED_LOCAL = "2026-08-23T23:10:00+08:00"

ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
SOLAR_R2_SHA256 = "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"
EXPECTED_VERDICT = "E20_INDEPENDENT_SURROGATE_MASS_BRANCH_SIM11_COUPLED_ARM_ONLY_DIAGNOSTICS_CLOSED__E15_ANCF_PROVISIONAL_PANEL_CONTACT_ATTACHED_RECOVERY_CAD_MISSION_PRODUCTION_AND_FLIGHT_HOLD"
EXPECTED_LANES = (
    "LEGACY_A__M01",
    "LEGACY_A__M07_ARM_ONLY",
    "M3R_B__M01",
    "M3R_B__M07_ARM_ONLY",
)
EXPECTED_VARIANTS = (
    "baseline_m3_radau",
    "undamped_m3_radau",
    "rigid_radau",
    "m4_radau",
    "m5_radau",
    "m3_bdf",
)
EXPECTED_MISMATCHES = (
    "sim_11_scene_A1_summary.json",
    "sim_11_scene_A1_summary_bdf.json",
    "sim_11_scene_A1_summary_fullmode.json",
    "sim_11_scene_A1_summary_m2.json",
    "sim_11_scene_A1_summary_m4.json",
    "sim_11_scene_A1_summary_rigid.json",
    "sim_11_scene_A1_summary_rtol8.json",
    "sim_11_scene_A1_summary_undamped.json",
    "sim_11_scene_A2_summary.json",
    "sim_11_scene_A2_summary_bdf.json",
    "sim_11_scene_A2_summary_bw10.json",
    "sim_11_scene_A2_summary_bw100.json",
    "sim_11_scene_A2_summary_bw20.json",
    "sim_11_scene_A2_summary_bw20_bdf.json",
    "sim_11_scene_A2_summary_bw20_m2.json",
    "sim_11_scene_A2_summary_bw20_m4.json",
    "sim_11_scene_A2_summary_bw20_m5.json",
    "sim_11_scene_A2_summary_bw5.json",
    "sim_11_scene_A2_summary_bw50.json",
    "sim_11_scene_A2_summary_conv_m3.json",
    "sim_11_scene_A2_summary_m2.json",
    "sim_11_scene_A2_summary_m4.json",
    "sim_11_scene_A2_summary_m5.json",
    "sim_11_scene_A2_summary_m7.json",
    "sim_11_scene_A2_summary_rtol8.json",
    "sim_11_scene_A2_summary_undamped.json",
)


def project_path(relative: str) -> Path:
    return PROJECT_ROOT / Path(relative)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def load_json(relative: str) -> Any:
    return json.loads(project_path(relative).read_text(encoding="utf-8"))


def load_yaml(relative: str) -> Any:
    return yaml.safe_load(project_path(relative).read_text(encoding="utf-8"))


def close(a: float, b: float, *, atol: float = 1.0e-12, rtol: float = 1.0e-11) -> bool:
    return math.isclose(float(a), float(b), abs_tol=atol, rel_tol=rtol)


def metric_rel(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(abs(float(a)), abs(float(b)), 1.0e-30)


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and finite_tree(item) for key, item in value.items())
    return False


def all_leaves_none(value: Any) -> bool:
    if isinstance(value, dict):
        return all(all_leaves_none(item) for item in value.values())
    if isinstance(value, list):
        return all(all_leaves_none(item) for item in value)
    return value is None


def read_history(relative: str) -> list[dict[str, str]]:
    with project_path(relative).open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def load_bundle() -> dict[str, Any]:
    manifest = load_json(f"{PREFIX}/results/E20_OUTPUT_MANIFEST_V1.json")
    input_manifest = load_json(f"{PREFIX}/results/E20_INPUT_MANIFEST_V1.json")
    mass = load_json(f"{PREFIX}/results/E20_MASS_BRANCH_COMPLETION_REGISTER_V1.json")
    local = load_json(f"{PREFIX}/results/E20_LOCAL_NUMERICAL_VERIFICATION_REGISTER_V1.json")
    register = load_json(f"{PREFIX}/results/E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_REGISTER_V1.json")
    gate = load_json(f"{PREFIX}/results/E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_GATE_V1.json")
    lanes = {}
    histories = {}
    for lane in register["lanes"]:
        lane_id = lane["lane_id"]
        summary = load_json(lane["summary"]["path"])
        lanes[lane_id] = summary
        histories[lane_id] = read_history(summary["history"]["path"])
    actual_artifacts = {}
    for row in manifest["artifacts"]:
        path = project_path(row["path"])
        actual_artifacts[row["path"]] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    actual_sources = {}
    for row in input_manifest["records"]:
        path = project_path(row["path"])
        actual_sources[row["path"]] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return {
        "authority": load_yaml(f"{PREFIX}/00_authority/E20_AUTHORITY_CONTRACT_V1.yaml"),
        "config": load_yaml(f"{PREFIX}/config/E20_INDEPENDENT_MASS_BRANCH_COUPLED_CAMPAIGN_V1.yaml"),
        "input": input_manifest,
        "mass": mass,
        "local": local,
        "register": register,
        "gate": gate,
        "manifest": manifest,
        "lanes": lanes,
        "histories": histories,
        "actual_artifacts": actual_artifacts,
        "actual_sources": actual_sources,
        "sim11_gate": load_json("30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json"),
        "e15_gate": load_json("30_simulation/e15_ancf_certification/results/gate_summary.json"),
        "builder_text": project_path(f"{PREFIX}/src/build_e20_diagnostics.py").read_text(encoding="utf-8"),
    }


def history_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    q = np.asarray([[float(row[key]) for key in ("quat_w", "quat_x", "quat_y", "quat_z")] for row in rows])
    r = np.asarray([[float(row[key]) for key in ("base_x_m", "base_y_m", "base_z_m")] for row in rows])
    w = np.asarray([[float(row[key]) for key in ("base_wx_rad_s", "base_wy_rad_s", "base_wz_rad_s")] for row in rows])
    E = np.asarray([float(row["energy_J"]) for row in rows])
    W = np.asarray([float(row["joint_work_J"]) for row in rows])
    D = np.asarray([float(row["damping_energy_J"]) for row in rows])
    audit = np.abs(W - (E - E[0]) - D)
    scale = max(float(np.max(np.abs(W))), float(np.max(np.abs(E))), 1.0e-300)
    return {
        "sample_count": len(rows),
        "lane_ids": {row["lane_id"] for row in rows},
        "peak_base_attitude_deviation_deg": max(float(row["base_dev_deg"]) for row in rows),
        "peak_base_rate_rad_s": float(np.max(np.linalg.norm(w, axis=1))),
        "max_base_origin_shift_m": float(np.max(np.linalg.norm(r, axis=1))),
        "final_base_position_m": r[-1].tolist(),
        "tip_L_peak_mm": max(abs(float(row["tip_L_mm"])) for row in rows),
        "tip_R_peak_mm": max(abs(float(row["tip_R_mm"])) for row in rows),
        "momentum_max_norm_dP": max(float(row["momentum_dP_norm"]) for row in rows),
        "momentum_max_norm_dL": max(float(row["momentum_dL_norm"]) for row in rows),
        "energy_audit_relative": float(np.max(audit) / scale),
        "quaternion_norm_max_error": float(np.max(np.abs(np.linalg.norm(q, axis=1) - 1.0))),
    }


def gate_safe(bundle: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []

    def req(condition: Any, label: str) -> None:
        if not bool(condition):
            errors.append(label)

    try:
        authority, config = bundle["authority"], bundle["config"]
        inp, mass, local = bundle["input"], bundle["mass"], bundle["local"]
        register, gate, manifest = bundle["register"], bundle["gate"], bundle["manifest"]
        lanes, histories = bundle["lanes"], bundle["histories"]

        req(authority["schema"] == "E20_SIM11_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_AUTHORITY_V1", "authority_schema")
        req(authority["authority_class"] == "NON_RELEASE_SURROGATE_MASS_COMPLETION_COUPLED_ARM_ONLY_DIAGNOSTIC_ONLY", "authority_class")
        req(authority["gate"] == "HOLD" and not authority["next_stage_authorized"] and not authority["release_credit"], "authority_hold")
        req(not authority["lane_isolation"]["cross_lane_chaining_allowed"] and not authority["lane_isolation"]["state_transfer_between_lanes_allowed"], "authority_lane_isolation")
        req(not authority["lane_isolation"]["attached_target_allowed"] and not authority["lane_isolation"]["scene_A2_allowed"] and not authority["lane_isolation"]["contact_window_allowed"] and not authority["lane_isolation"]["lockup_allowed"], "authority_no_a2_target_contact")
        req(not authority["lane_isolation"]["stock_sim11_loader_used"] and authority["lane_isolation"]["e20_narrow_arm_only_loader_used"] and not authority["lane_isolation"]["target_capture_metadata_read"], "authority_narrow_loader")
        req(authority["mass_branch_rule"]["mass_completion_rule"] == "UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE", "authority_mass_rule")
        req(authority["mass_branch_rule"]["bus_only_mass_and_inertia_scaled"] and authority["mass_branch_rule"]["bus_geometry_and_cg_fixed"] and authority["mass_branch_rule"]["bus_inertia_scaled_linearly_with_mass"], "authority_bus_only")
        req(authority["mass_branch_rule"]["branch_lifecycle"] == "LEGACY_TRANSITIONAL_SENSITIVITY_ONLY" and not authority["mass_branch_rule"]["current_M7_design_mass_authority_consumed"] and not authority["mass_branch_rule"]["current_M7_design_mass_authority_superseded"], "authority_m7_boundary")
        req(authority["mount_frame_boundary"]["mount_frame_model"] == "M_DYNAMICS_LEGACY_NUMERICAL" and authority["mount_frame_boundary"]["numerical_translation_m"] == [0.18525, 0.0, 0.0] and authority["mount_frame_boundary"]["numerical_rotation"] == "Ry(+90deg)", "authority_legacy_frame")
        req(not authority["mount_frame_boundary"]["physical_mount_frame_applied"] and authority["mount_frame_boundary"]["physical_mount_transform"] is None and not authority["mount_frame_boundary"]["m4_digital_prototype_installation_dynamics_claimed"], "authority_physical_frame_hold")

        req(config["schema"] == "E20_INDEPENDENT_MASS_BRANCH_COUPLED_CAMPAIGN_V1", "config_schema")
        cm = config["mass_completion"]
        req(cm["rule"] == "UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE" and cm["bus_only_mass_and_inertia_scaled"] and cm["bus_geometry_fixed"] and cm["bus_cg_fixed"], "config_mass_rule")
        req(close(cm["legacy_A_composite_with_target_kg"], 50.69555594934299, atol=1e-14, rtol=0.0) and close(cm["m3r_B_composite_with_target_kg"], 51.081436764691, atol=1e-14, rtol=0.0), "config_composites")
        req(close(cm["legacy_A_service_scalar_kg"], 28.69555594934299, atol=1e-14, rtol=0.0) and close(cm["m3r_B_service_scalar_kg"], 29.081436764691, atol=1e-14, rtol=0.0), "config_service_scalars")
        req(cm["lifecycle"] == "LEGACY_M4_BRANCH_SENSITIVITY_TRANSITIONAL_DIAGNOSTIC" and not cm["current_M7_design_mass_model_consumed"], "config_m7_boundary")
        req(config["main_execution"]["dynamics_mode"] == "reduced_momentum" and config["main_execution"]["method"] == "Radau" and config["main_execution"]["modes_per_panel"] == 3, "config_main_solver")
        req(config["local_numerical_verification"]["horizon_s"] == 1.5 and config["local_numerical_verification"]["anchor_lane_id"] == "M3R_B__M07_ARM_ONLY", "config_local_scope")
        req(not config["global_invariants"]["scene_A2_invoked"] and not config["global_invariants"]["contact_window_invoked"] and not config["global_invariants"]["target_attached"], "config_no_a2_target")
        req(not config["global_invariants"]["physical_mount_frame_applied"] and config["global_invariants"]["physical_mount_transform"] is None, "config_mount_hold")

        req(inp["schema"] == "E20_INPUT_MANIFEST_V1" and inp["all_exact_hash_match"], "input_schema_exact")
        req(inp["record_count"] == len(inp["records"]) == len(bundle["actual_sources"]), "input_count")
        for row in inp["records"]:
            actual = bundle["actual_sources"].get(row["path"])
            req(actual is not None and row["sha256"] == actual["sha256"] == row["expected_sha256"] and row["bytes"] == actual["bytes"] and row["exact_hash_match"], f"source:{row['name']}")
        req(inp["source_set_sha256"] == sha256_bytes(canonical_json_bytes(inp["records"])), "input_set_hash")
        sim_audit = inp["sim11_historical_artifact_audit"]
        req(sim_audit["historical_manifest_count"] == 58 and sim_audit["current_bytewise_match_count"] == 32 and sim_audit["current_bytewise_mismatch_count"] == 26, "sim11_32_26")
        req(tuple(sim_audit["mismatch_artifacts"]) == EXPECTED_MISMATCHES and sim_audit["mismatch_artifacts_all_summary_json"], "sim11_mismatch_set")
        req(sim_audit["historical_gate_verdict"] == "SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS" and sim_audit["historical_gate_verdict_preserved"], "sim11_verdict")
        req(not sim_audit["current_artifact_manifest_bytewise_complete"] and sim_audit["reorg_route_only_semantic_diff"] and not sim_audit["historical_next_stage_authorized_inherited"], "sim11_reorg_scope")
        req(bundle["sim11_gate"]["verdict"] == sim_audit["historical_gate_verdict"] and bundle["sim11_gate"]["next_stage_authorized"] is True, "sim11_gate_source")
        for row in sim_audit["artifact_rows"]:
            current_path = project_path(f"30_simulation/sim_11_coupled_dynamics/results/{row['artifact']}")
            req(row["current_sha256"] == sha256_file(current_path), f"sim11_current:{row['artifact']}")
            req(row["historical_sha256"] == bundle["sim11_gate"]["artifacts_sha256"][row["artifact"]].upper(), f"sim11_historical:{row['artifact']}")
            req(row["bytewise_match"] == (row["current_sha256"] == row["historical_sha256"]), f"sim11_match_flag:{row['artifact']}")
        provisional = inp["sim11_provisional_boundary"]
        req(provisional["PROVISIONAL_PARAMS"] and provisional["provisional_fields"] == ["n_modes", "mode_shape", "stiffness_case", "zeta_modal", "contact_T_c"], "sim11_provisional")
        req(provisional["legacy_stock_ffr_consumed"] and not provisional["current_R2_flexible_appendage_consumed"] and not provisional["current_R2_coupled_model_claimed"] and not provisional["scene_A2_consumed"] and not provisional["contact_T_c_consumed"], "legacy_not_r2")
        req(provisional["stock_loader_reads_unused_target_capture_metadata"] and not provisional["stock_load_model_config_used"] and provisional["e20_narrow_arm_only_loader_used"] and not provisional["target_capture_metadata_read"] and not provisional["target_capture_metadata_consumed_by_dynamics"], "narrow_loader_io_boundary")
        mab = inp["mass_authority_boundary"]
        req(mab["legacy_M4_A_B_branch_lifecycle"] == "TRANSITIONAL_SURROGATE_SENSITIVITY_ONLY" and mab["current_M7_design_mass_v2_hash_bound_as_boundary"] and not mab["current_M7_design_mass_v2_consumed_by_solver"] and not mab["current_M7_design_mass_v2_superseded"] and mab["e21_rebind_required_for_current_M7_design_mass_dynamics"], "m7_mass_boundary")
        debt = inp["e15_certification_debt"]
        req(debt["ancf_certification_status"] == "REPEAT_ANCF_CERTIFICATION" and close(debt["e15_cross_solver_max_relative_difference"], 0.05637349419858036, atol=0.0, rtol=0.0) and debt["e15_cross_solver_max_relative_difference"] > debt["e15_gate_limit"], "e15_repeat")
        req(not debt["e15_final_candidate_available"] and not debt["ancf_certified"] and not debt["flexible_safety_ready"], "e15_false")
        req(bundle["e15_gate"]["overall"] == "REPEAT_ANCF_CERTIFICATION" and close(bundle["e15_gate"]["cross_solver_diagnostic"]["max_relative_difference"], debt["e15_cross_solver_max_relative_difference"], atol=0.0, rtol=0.0), "e15_source")
        req(inp["accepted_urdf_sha256"] == ACCEPTED_URDF_SHA256 and inp["solar_r2_sha256"] == SOLAR_R2_SHA256 and not inp["accepted_urdf_modified"], "immutable_input")

        req(mass["schema"] == "E20_MASS_BRANCH_COMPLETION_REGISTER_V1" and mass["mass_completion_rule"] == "UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE", "mass_schema_rule")
        req(mass["branch_count"] == 2 and len(mass["branches"]) == 2 and mass["bus_only_mass_and_inertia_scaled"] and mass["bus_geometry_and_cg_fixed"], "mass_count_bus_only")
        expected_mass = {
            "M4_DIAG_LEGACY_A": (50.69555594934299, 28.69555594934299),
            "M4_DIAG_M3R_B": (51.081436764691, 29.081436764691),
        }
        req({row["branch_id"] for row in mass["branches"]} == set(expected_mass), "mass_ids")
        for row in mass["branches"]:
            composite, service = expected_mass[row["branch_id"]]
            req(close(row["diagnostic_composite_with_22kg_target_kg"], composite, atol=1e-14, rtol=0.0), f"mass_composite:{row['branch_id']}")
            req(close(row["target_scenario_subtracted_algebraically_kg"], 22.0, atol=0.0, rtol=0.0) and close(row["service_scalar_branch_kg"], service, atol=1e-14, rtol=0.0), f"mass_subtract:{row['branch_id']}")
            req(close(row["surrogate_bus_mass_kg"] + row["non_bus_mass_kg"], service, atol=1e-12, rtol=0.0) and row["scalar_mass_closure_error_kg"] <= 1e-12, f"mass_closure:{row['branch_id']}")
            req(close(row["bus_mass_scale"], row["surrogate_bus_mass_kg"] / row["sim11_original_bus_mass_kg"], atol=1e-14, rtol=1e-13), f"bus_scale:{row['branch_id']}")
            inertia = np.asarray(row["surrogate_bus_inertia_kg_m2"], float)
            req(inertia.shape == (3, 3) and np.max(np.abs(inertia - inertia.T)) <= 1e-15 and np.linalg.eigvalsh(inertia).min() > 0.0 and close(np.linalg.eigvalsh(inertia).min(), row["surrogate_bus_inertia_min_eigenvalue_kg_m2"], atol=1e-14, rtol=1e-12), f"bus_spd:{row['branch_id']}")
            req(row["bus_cg_unchanged"] and row["bus_inertia_linear_scale_max_abs_error_kg_m2"] == 0.0 and row["model_target_is_none"], f"bus_invariant:{row['branch_id']}")
            req(row["standard_uncertainty_kg"] is None and not row["selected"] and not row["released"], f"mass_nonrelease:{row['branch_id']}")
        req(close(mass["branch_delta_kg_not_uncertainty"], 0.3858808153480098, atol=1e-14, rtol=0.0), "branch_delta")
        req(not mass["branch_selection_performed"] and not mass["branch_averaging_performed"] and not mass["model_difference_is_measurement_uncertainty"], "mass_no_merge")
        req(mass["branch_lifecycle"] == "LEGACY_TRANSITIONAL_SENSITIVITY_ONLY" and not mass["current_M7_design_mass_authority_consumed"] and not mass["current_M7_design_mass_authority_superseded"], "mass_m7_boundary")
        req(all(mass[key] is None for key in ("released_service_mass_kg", "released_service_cg_m", "released_service_inertia_kg_m2", "physical_bus_completion_authority")), "mass_nulls")

        req(register["schema"] == "E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_REGISTER_V1", "register_schema")
        req(register["lane_count"] == 4 and tuple(row["lane_id"] for row in register["lanes"]) == EXPECTED_LANES and set(lanes) == set(EXPECTED_LANES) and set(histories) == set(EXPECTED_LANES), "lane_set")
        req(register["lane_initial_states_independent"] and not register["cross_lane_chaining_performed"] and not register["state_transfer_between_lanes_performed"], "lane_isolation")
        req(not register["branch_selection_performed"] and not register["branch_averaging_performed"] and not register["branch_merging_performed"], "branch_isolation")
        req(register["target_subtraction_is_algebra_only"] and not register["attached_target_propagated"] and not register["scene_A2_invoked"] and not register["contact_window_invoked"] and not register["lockup_invoked"], "no_a2_contact_target")
        req(register["legacy_stock_sim11_model_used"] and not register["current_R2_coupled_model_used"] and not register["current_R2_flexible_appendage_used"], "register_legacy_not_r2")
        req(register["legacy_M4_mass_branches_used_as_transitional_sensitivity_only"] and not register["current_M7_design_mass_v2_consumed"] and not register["current_M7_design_mass_v2_superseded"], "register_m7_boundary")
        source_records = {row["path"]: row for row in inp["records"]}
        for lane_row in register["lanes"]:
            lane_id = lane_row["lane_id"]
            summary = lanes[lane_id]
            req(lane_row["state_input_from_other_lane"] is None and summary["cross_lane_state_input"] is None and summary["initial_state"]["source_lane"] is None, f"lane_input:{lane_id}")
            req(lane_row["summary"]["sha256"] == sha256_file(project_path(lane_row["summary"]["path"])) and lane_row["summary"]["bytes"] == project_path(lane_row["summary"]["path"]).stat().st_size, f"lane_summary_hash:{lane_id}")
            req(summary["history"]["sha256"] == sha256_file(project_path(summary["history"]["path"])) and summary["history"]["bytes"] == project_path(summary["history"]["path"]).stat().st_size, f"lane_history_hash:{lane_id}")
            req(summary["schema"] == "E20_COUPLED_ARM_ONLY_LANE_SUMMARY_V1" and summary["lane_id"] == lane_id, f"lane_schema:{lane_id}")
            trajectory_record = source_records.get(summary["trajectory_source"]["path"])
            req(trajectory_record is not None and summary["trajectory_source"]["sha256"] == trajectory_record["sha256"] == bundle["actual_sources"][summary["trajectory_source"]["path"]]["sha256"], f"lane_trajectory_hash:{lane_id}")
            req(summary["solver"]["source"] == "SIM11_STOCK_LEGACY_FFR_WITH_SCOPED_REORG_ADAPTER" and summary["solver"]["mode"] == "reduced_momentum" and summary["solver"]["method"] == "Radau" and summary["solver"]["n_modes_per_panel"] == 3, f"lane_solver:{lane_id}")
            req(summary["solver"]["PROVISIONAL_PARAMS"] and not summary["solver"]["current_R2_model_consumed"] and summary["solver"]["mount_frame_model"] == "M_DYNAMICS_LEGACY_NUMERICAL" and not summary["solver"]["physical_mount_frame_applied"] and summary["solver"]["physical_mount_transform"] is None, f"lane_boundary:{lane_id}")
            req(not summary["target_attached"] and not summary["scene_A2_invoked"] and not summary["contact_window_invoked"] and not summary["physical_contact_computed"] and not summary["engineering_prediction"] and not summary["released_for_mission_gate"], f"lane_nonphysical:{lane_id}")
            req(max(summary["trajectory_source"]["reconstruction"].values()) <= 1e-11 and summary["trajectory_source"]["release_flags_all_false"] and summary["trajectory_source"]["jaw_travel_all_null"], f"lane_traj:{lane_id}")
            hm = history_metrics(histories[lane_id])
            req(hm["lane_ids"] == {lane_id} and hm["sample_count"] == summary["history"]["sample_count"], f"history_identity:{lane_id}")
            for key in ("peak_base_attitude_deviation_deg", "peak_base_rate_rad_s", "max_base_origin_shift_m", "tip_L_peak_mm", "tip_R_peak_mm", "momentum_max_norm_dP", "momentum_max_norm_dL", "energy_audit_relative", "quaternion_norm_max_error"):
                req(close(hm[key], summary["metrics"][key], atol=2e-11, rtol=2e-9), f"history_metric:{lane_id}:{key}")
            req(np.max(np.abs(np.asarray(hm["final_base_position_m"]) - np.asarray(summary["metrics"]["final_base_position_m"]))) <= 2e-13, f"history_final_pos:{lane_id}")
            req(max(summary["metrics"]["momentum_max_norm_dP"], summary["metrics"]["momentum_max_norm_dL"]) <= 1e-12 and summary["metrics"]["energy_audit_relative"] <= 1e-8 and summary["metrics"]["quaternion_norm_max_error"] <= 1e-12 and summary["metrics"]["mass_matrix_min_eigenvalue"] > 0.0, f"lane_numeric:{lane_id}")

        req(local["schema"] == "E20_LOCAL_NUMERICAL_VERIFICATION_REGISTER_V1" and local["anchor_lane_id"] == "M3R_B__M07_ARM_ONLY", "local_schema_anchor")
        variants = {row["variant"]: row for row in local["variants"]}
        req(tuple(row["variant"] for row in local["variants"]) == EXPECTED_VARIANTS and set(variants) == set(EXPECTED_VARIANTS), "local_variants")
        req(all(not row["target_attached"] and not row["scene_A2_invoked"] and not row["contact_window_invoked"] and row["mode"] == "reduced_momentum" for row in variants.values()), "local_nonphysical")
        req(variants["baseline_m3_radau"]["method"] == "Radau" and variants["baseline_m3_radau"]["n_modes_per_panel"] == 3 and variants["m3_bdf"]["method"] == "BDF", "local_solvers")
        req(variants["undamped_m3_radau"]["zeta_modal"] == 0.0 and variants["undamped_m3_radau"]["metrics"]["energy_audit_relative"] <= 1e-8 and close(local["undamped_energy_audit_relative"], variants["undamped_m3_radau"]["metrics"]["energy_audit_relative"], atol=0.0, rtol=0.0), "undamped")
        rigid = local["rigid_degeneration"]
        req(variants["rigid_radau"]["rigid_panels"] and variants["rigid_radau"]["n_modes_per_panel"] == 0 and rigid["n_modes_per_panel"] == 0 and rigid["tip_L_peak_mm"] == 0.0 and rigid["tip_R_peak_mm"] == 0.0 and rigid["panel_modal_energy_peak_J"] == 0.0, "rigid")
        obs_modal = ("peak_base_attitude_deviation_deg", "tip_L_peak_mm", "tip_R_peak_mm", "panel_modal_energy_peak_J")
        calc_m4_m5 = {key: metric_rel(variants["m4_radau"]["metrics"][key], variants["m5_radau"]["metrics"][key]) for key in obs_modal}
        req(all(close(calc_m4_m5[key], local["modal_refinement_relative"]["m4_to_m5"][key], atol=1e-15, rtol=1e-12) for key in obs_modal), "modal_recompute")
        req(close(max(calc_m4_m5.values()), local["modal_refinement_relative"]["max_m4_to_m5"], atol=1e-15, rtol=1e-12) and local["modal_refinement_relative"]["max_m4_to_m5"] < 0.01, "modal_gate")
        obs_cross = ("peak_base_attitude_deviation_deg", "tip_L_peak_mm", "tip_R_peak_mm", "panel_modal_energy_peak_J", "joint_work_final_J")
        calc_cross = {key: metric_rel(variants["baseline_m3_radau"]["metrics"][key], variants["m3_bdf"]["metrics"][key]) for key in obs_cross}
        req(all(close(calc_cross[key], local["radau_vs_bdf_relative"]["observables"][key], atol=1e-15, rtol=1e-12) for key in obs_cross), "cross_recompute")
        req(close(max(calc_cross.values()), local["radau_vs_bdf_relative"]["maximum"], atol=1e-15, rtol=1e-12) and local["radau_vs_bdf_relative"]["maximum"] < 0.05, "cross_gate")
        req(not local["e15_certification_debt_cleared"] and not local["local_cross_solver_is_e15_replacement"] and local["status"] == "PASS", "local_no_e15_promotion")

        frame = register["mount_frame_boundary"]
        req(frame["mount_frame_model"] == "M_DYNAMICS_LEGACY_NUMERICAL" and frame["numerical_translation_m"] == [0.18525, 0.0, 0.0] and frame["numerical_rotation"] == "Ry(+90deg)" and not frame["physical_entity"], "frame_numerical")
        req(not frame["current_M7_unique_dynamics_M_consumed"] and not frame["current_M7_design_dynamics_closure_claimed"], "frame_m7_not_consumed")
        req(frame["geometric_feature_stack_id"] == "B601_ARM_BASE_PHYSICAL" and frame["geometric_feature_stack_x_mm"] == 208.0 and frame["geometric_feature_stack_clock_deg"] == 25.000014 and not frame["geometric_feature_stack_is_dynamics_M_alias"], "frame_geometric_stack")
        req(not frame["physical_mount_frame_applied"] and frame["physical_mount_transform"] is None and not frame["m4_digital_prototype_installation_dynamics_claimed"], "frame_hold")
        req(all_leaves_none(register["physical_unknowns"]), "physical_nulls")
        req(not register["cad_or_mesh_generated"] and not register["accepted_urdf_modified"] and not register["historical_gate_modified"], "no_mutation")
        readiness = ("physical_contact_ready", "attached_target_recovery_ready", "mission_sequence_executable", "mission_release_ready", "production_dynamics_ready", "mechanical_design_released", "hardware_motion_ready", "flight_qualification_ready")
        req(not any(register[key] for key in readiness) and register["released_segments"] == 0 and not register["release_credit"], "register_release_hold")

        req(manifest["schema"] == "E20_OUTPUT_MANIFEST_V1" and manifest["artifact_count"] == len(manifest["artifacts"]), "manifest_schema_count")
        req(manifest["artifact_set_sha256"] == sha256_bytes(canonical_json_bytes(manifest["artifacts"])), "manifest_set_hash")
        paths = [row["path"] for row in manifest["artifacts"]]
        req(len(paths) == len(set(paths)) and f"{PREFIX}/results/E20_VALIDATION_V1.json" not in paths and f"{PREFIX}/results/E20_OUTPUT_MANIFEST_V1.json" not in paths, "manifest_scope")
        req(manifest["validation_report_excluded"] and manifest["manifest_self_excluded"] and manifest["gate"] == "HOLD" and not manifest["next_stage_authorized"] and not manifest["release_credit"] and manifest["released_segments"] == 0, "manifest_hold")
        for row in manifest["artifacts"]:
            actual = bundle["actual_artifacts"].get(row["path"])
            req(actual is not None and row["sha256"] == actual["sha256"] and row["bytes"] == actual["bytes"], f"artifact:{row['path']}")
        req(manifest["accepted_urdf_sha256"] == ACCEPTED_URDF_SHA256 and manifest["solar_r2_sha256"] == SOLAR_R2_SHA256 and manifest["input_source_set_sha256"] == inp["source_set_sha256"], "manifest_roots")

        req(gate["schema"] == "E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_GATE_V1", "gate_schema")
        req(gate["criteria_total"] == len(gate["criteria"]) and gate["criteria_observed"] == gate["criteria_total"] and all(row["observed"] and row["state"] == "PASS_DIAGNOSTIC_ONLY" and not row["release_credit"] for row in gate["criteria"]), "gate_criteria")
        req(gate["diagnostic_execution_verdict"] == "PASS" and gate["independent_surrogate_mass_branch_sim11_coupled_arm_only_diagnostic_execution_closed"] and gate["local_numerical_reproducibility_closed"], "gate_diagnostic_closed")
        req(gate["mass_completion_rule"] == "UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE" and gate["bus_only_mass_and_inertia_scaled"], "gate_mass_rule")
        req(gate["historical_gate_verdict_preserved"] and not gate["current_artifact_manifest_bytewise_complete"] and gate["reorg_route_only_semantic_diff"], "gate_reorg")
        req(gate["ancf_certification_status"] == "REPEAT_ANCF_CERTIFICATION" and gate["e15_cross_solver_max_relative_difference"] > gate["e15_gate_limit"] and not gate["e15_final_candidate_available"] and not gate["ancf_certified"] and not gate["flexible_safety_ready"], "gate_e15")
        req(gate["legacy_stock_sim11_model_used"] and not gate["current_R2_coupled_model_used"] and gate["legacy_M4_mass_branches_used_as_transitional_sensitivity_only"] and not gate["current_M7_design_mass_v2_consumed"] and not gate["current_M7_design_mass_v2_superseded"], "gate_legacy_boundary")
        req(gate["mount_frame_model"] == "M_DYNAMICS_LEGACY_NUMERICAL" and not gate["physical_mount_frame_applied"] and gate["physical_mount_transform"] is None and not gate["m4_digital_prototype_installation_dynamics_claimed"] and not gate["current_M7_unique_dynamics_M_consumed"] and not gate["current_M7_design_dynamics_closure_claimed"], "gate_frame")
        req(not gate["scene_A2_invoked"] and not gate["contact_window_invoked"] and not gate["attached_target_propagated"] and gate["selected_mass_branch"] is None, "gate_no_a2_target")
        req(all(gate[key] is None for key in ("released_service_mass_kg", "released_service_cg_m", "released_service_inertia_kg_m2")), "gate_mass_nulls")
        gate_readiness = ("end_to_end_diagnostic_dynamics_ready", "physical_contact_ready", "attached_target_recovery_ready", "mission_release_ready", "production_dynamics_ready", "mechanical_design_released", "hardware_motion_ready", "flight_qualification_ready")
        req(not any(gate[key] for key in gate_readiness) and gate["released_segments"] == 0 and not gate["testing_pass_grants_authority"], "gate_readiness")
        req(gate["gate"] == "HOLD" and gate["verdict"] == EXPECTED_VERDICT and not gate["next_stage_authorized"] and not gate["release_credit"], "gate_hold_verdict")
        req(gate["input_manifest"]["sha256"] == sha256_file(project_path(gate["input_manifest"]["path"])), "gate_input_hash")
        req(gate["result_register"]["sha256"] == sha256_file(project_path(gate["result_register"]["path"])), "gate_register_hash")

        req("import scene_a2_capture" not in bundle["builder_text"] and "from scene_a2_capture" not in bundle["builder_text"], "source_no_a2_import")
        req(".attach_target(" not in bundle["builder_text"] and "integrate_full(" not in bundle["builder_text"], "source_no_target_full")
        req("config_loader.load_model_config(" not in bundle["builder_text"] and "refs[\"targets\"]" not in bundle["builder_text"] and "refs[\"capture_interface\"]" not in bundle["builder_text"], "source_narrow_loader")
        req(finite_tree({key: value for key, value in bundle.items() if key not in ("builder_text", "histories")}), "finite_tree")
    except (KeyError, TypeError, ValueError, IndexError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    return not errors, errors


def positive_checks(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    safe, errors = gate_safe(bundle)
    probes: list[tuple[str, bool]] = [
        ("P01_UNIFIED_GATE_SAFE", safe),
        ("P02_NO_GATE_ERRORS", not errors),
        ("P03_AUTHORITY_HOLD", bundle["authority"]["gate"] == "HOLD"),
        ("P04_SOURCE_HASH_SET", bundle["input"]["all_exact_hash_match"]),
        ("P05_SIM11_58_ARTIFACTS", bundle["input"]["sim11_historical_artifact_audit"]["historical_manifest_count"] == 58),
        ("P06_SIM11_32_MATCH", bundle["input"]["sim11_historical_artifact_audit"]["current_bytewise_match_count"] == 32),
        ("P07_SIM11_26_REORG_SUMMARIES", tuple(bundle["input"]["sim11_historical_artifact_audit"]["mismatch_artifacts"]) == EXPECTED_MISMATCHES),
        ("P08_SIM11_VERDICT_PRESERVED", bundle["input"]["sim11_historical_artifact_audit"]["historical_gate_verdict_preserved"]),
        ("P09_SIM11_NEXT_NOT_INHERITED", not bundle["input"]["sim11_historical_artifact_audit"]["historical_next_stage_authorized_inherited"]),
        ("P10_E15_REPEAT", bundle["gate"]["ancf_certification_status"] == "REPEAT_ANCF_CERTIFICATION"),
        ("P11_E15_5P64_GT_5PCT", bundle["gate"]["e15_cross_solver_max_relative_difference"] > bundle["gate"]["e15_gate_limit"]),
        ("P12_MASS_BRANCH_COUNT", bundle["mass"]["branch_count"] == 2),
        ("P13_TARGET_SUBTRACTION_ALGEBRA", all(close(row["diagnostic_composite_with_22kg_target_kg"] - 22.0, row["service_scalar_branch_kg"]) for row in bundle["mass"]["branches"])),
        ("P14_BUS_ONLY_COMPLETION", bundle["mass"]["bus_only_mass_and_inertia_scaled"]),
        ("P15_MASS_CLOSURE", all(row["scalar_mass_closure_error_kg"] <= 1e-12 for row in bundle["mass"]["branches"])),
        ("P16_BRANCH_NOT_SELECTED", not bundle["mass"]["branch_selection_performed"]),
        ("P17_BRANCH_NOT_AVERAGED", not bundle["mass"]["branch_averaging_performed"]),
        ("P18_M7_DESIGN_MASS_NOT_CONSUMED", not bundle["register"]["current_M7_design_mass_v2_consumed"]),
        ("P19_FOUR_LANES", tuple(bundle["lanes"]) == EXPECTED_LANES),
        ("P20_LANES_ISOLATED", not bundle["register"]["cross_lane_chaining_performed"]),
        ("P21_MAIN_RADAU_REDUCED", all(row["solver"]["method"] == "Radau" and row["solver"]["mode"] == "reduced_momentum" for row in bundle["lanes"].values())),
        ("P22_MAIN_MOMENTUM", all(max(row["metrics"]["momentum_max_norm_dP"], row["metrics"]["momentum_max_norm_dL"]) <= 1e-12 for row in bundle["lanes"].values())),
        ("P23_MAIN_ENERGY", all(row["metrics"]["energy_audit_relative"] <= 1e-8 for row in bundle["lanes"].values())),
        ("P24_MAIN_QUATERNION", all(row["metrics"]["quaternion_norm_max_error"] <= 1e-12 for row in bundle["lanes"].values())),
        ("P25_MAIN_SPD", all(row["metrics"]["mass_matrix_min_eigenvalue"] > 0.0 for row in bundle["lanes"].values())),
        ("P26_UNDAMPED", bundle["local"]["undamped_energy_audit_relative"] <= 1e-8),
        ("P27_RIGID", bundle["local"]["rigid_degeneration"]["panel_modal_energy_peak_J"] == 0.0),
        ("P28_MODAL_REFINEMENT", bundle["local"]["modal_refinement_relative"]["max_m4_to_m5"] < 0.01),
        ("P29_BDF_CROSS", bundle["local"]["radau_vs_bdf_relative"]["maximum"] < 0.05),
        ("P30_NO_E15_PROMOTION", not bundle["local"]["e15_certification_debt_cleared"]),
        ("P31_NO_A2", not bundle["register"]["scene_A2_invoked"]),
        ("P32_NO_CONTACT", not bundle["register"]["contact_window_invoked"]),
        ("P33_NO_TARGET", not bundle["register"]["attached_target_propagated"]),
        ("P34_M_DYNAMICS_LEGACY", bundle["gate"]["mount_frame_model"] == "M_DYNAMICS_LEGACY_NUMERICAL"),
        ("P35_PHYSICAL_MOUNT_NULL", bundle["gate"]["physical_mount_transform"] is None),
        ("P36_PHYSICAL_UNKNOWNS_NULL", all_leaves_none(bundle["register"]["physical_unknowns"])),
        ("P37_URDF_IMMUTABLE", bundle["manifest"]["accepted_urdf_sha256"] == ACCEPTED_URDF_SHA256),
        ("P38_SOLAR_IMMUTABLE", bundle["manifest"]["solar_r2_sha256"] == SOLAR_R2_SHA256),
        ("P39_MANIFEST_VALIDATION_EXCLUDED", bundle["manifest"]["validation_report_excluded"]),
        ("P40_EXECUTION_CLOSED", bundle["gate"]["independent_surrogate_mass_branch_sim11_coupled_arm_only_diagnostic_execution_closed"]),
        ("P41_OVERALL_HOLD", bundle["gate"]["gate"] == "HOLD"),
        ("P42_NO_NEXT_STAGE", not bundle["gate"]["next_stage_authorized"]),
        ("P43_NO_RELEASE_CREDIT", not bundle["gate"]["release_credit"]),
    ]
    return [{"id": name, "pass": bool(ok)} for name, ok in probes]


def mutation_controls() -> list[tuple[str, Callable[[dict[str, Any]], None]]]:
    return [
        ("NC01_AUTHORITY_CLASS_PROMOTE", lambda b: b["authority"].__setitem__("authority_class", "PRODUCTION")),
        ("NC02_AUTHORITY_GATE_PASS", lambda b: b["authority"].__setitem__("gate", "PASS")),
        ("NC03_AUTHORITY_NEXT_TRUE", lambda b: b["authority"].__setitem__("next_stage_authorized", True)),
        ("NC04_AUTHORITY_RELEASE_TRUE", lambda b: b["authority"].__setitem__("release_credit", True)),
        ("NC05_CROSS_LANE_ALLOWED", lambda b: b["authority"]["lane_isolation"].__setitem__("cross_lane_chaining_allowed", True)),
        ("NC06_TARGET_ALLOWED", lambda b: b["authority"]["lane_isolation"].__setitem__("attached_target_allowed", True)),
        ("NC07_A2_ALLOWED", lambda b: b["authority"]["lane_isolation"].__setitem__("scene_A2_allowed", True)),
        ("NC08_CONTACT_ALLOWED", lambda b: b["authority"]["lane_isolation"].__setitem__("contact_window_allowed", True)),
        ("NC09_MASS_RULE_DRIFT", lambda b: b["config"]["mass_completion"].__setitem__("rule", "AVERAGE_BRANCHES")),
        ("NC10_BUS_ONLY_FALSE", lambda b: b["config"]["mass_completion"].__setitem__("bus_only_mass_and_inertia_scaled", False)),
        ("NC11_TARGET_SUBTRACTION_DRIFT", lambda b: b["mass"]["branches"][0].__setitem__("target_scenario_subtracted_algebraically_kg", 21.0)),
        ("NC12_LEGACY_COMPOSITE_DRIFT", lambda b: b["mass"]["branches"][0].__setitem__("diagnostic_composite_with_22kg_target_kg", 50.7)),
        ("NC13_M3R_COMPOSITE_DRIFT", lambda b: b["mass"]["branches"][1].__setitem__("diagnostic_composite_with_22kg_target_kg", 51.0)),
        ("NC14_LEGACY_SERVICE_DRIFT", lambda b: b["mass"]["branches"][0].__setitem__("service_scalar_branch_kg", 28.0)),
        ("NC15_M3R_SERVICE_DRIFT", lambda b: b["mass"]["branches"][1].__setitem__("service_scalar_branch_kg", 29.0)),
        ("NC16_MASS_UNCERTAINTY_FILL", lambda b: b["mass"]["branches"][0].__setitem__("standard_uncertainty_kg", 0.1)),
        ("NC17_BRANCH_SELECT", lambda b: b["mass"].__setitem__("branch_selection_performed", True)),
        ("NC18_BRANCH_AVERAGE", lambda b: b["mass"].__setitem__("branch_averaging_performed", True)),
        ("NC19_DIFFERENCE_AS_UNCERTAINTY", lambda b: b["mass"].__setitem__("model_difference_is_measurement_uncertainty", True)),
        ("NC20_MASS_CLOSURE_FAIL", lambda b: b["mass"]["branches"][0].__setitem__("scalar_mass_closure_error_kg", 1e-3)),
        ("NC21_BUS_SCALE_FAIL", lambda b: b["mass"]["branches"][0].__setitem__("bus_mass_scale", 1.0)),
        ("NC22_BUS_CG_CHANGED", lambda b: b["mass"]["branches"][0].__setitem__("bus_cg_unchanged", False)),
        ("NC23_BUS_INERTIA_SCALE_FAIL", lambda b: b["mass"]["branches"][0].__setitem__("bus_inertia_linear_scale_max_abs_error_kg_m2", 1e-4)),
        ("NC24_BUS_INERTIA_NONSPD", lambda b: b["mass"]["branches"][0].__setitem__("surrogate_bus_inertia_kg_m2", [[-1,0,0],[0,1,0],[0,0,1]])),
        ("NC25_M7_CONSUMED", lambda b: b["register"].__setitem__("current_M7_design_mass_v2_consumed", True)),
        ("NC26_M7_SUPERSEDED", lambda b: b["register"].__setitem__("current_M7_design_mass_v2_superseded", True)),
        ("NC27_LANE_COUNT", lambda b: b["register"].__setitem__("lane_count", 3)),
        ("NC28_LANE_DUPLICATE", lambda b: b["register"]["lanes"][1].__setitem__("lane_id", "LEGACY_A__M01")),
        ("NC29_CROSS_LANE_INPUT", lambda b: b["register"]["lanes"][0].__setitem__("state_input_from_other_lane", "M3R_B__M01")),
        ("NC30_CROSS_LANE_CHAINED", lambda b: b["register"].__setitem__("cross_lane_chaining_performed", True)),
        ("NC31_STATE_TRANSFER", lambda b: b["register"].__setitem__("state_transfer_between_lanes_performed", True)),
        ("NC32_REGISTER_BRANCH_SELECT", lambda b: b["register"].__setitem__("branch_selection_performed", True)),
        ("NC33_LANE_TARGET", lambda b: b["lanes"]["LEGACY_A__M01"].__setitem__("target_attached", True)),
        ("NC34_A2_INVOKED", lambda b: b["register"].__setitem__("scene_A2_invoked", True)),
        ("NC35_CONTACT_INVOKED", lambda b: b["register"].__setitem__("contact_window_invoked", True)),
        ("NC36_LOCK_INVOKED", lambda b: b["register"].__setitem__("lockup_invoked", True)),
        ("NC37_TRAJECTORY_HASH_DRIFT", lambda b: b["lanes"]["LEGACY_A__M01"]["trajectory_source"].__setitem__("sha256", "0"*64)),
        ("NC38_TRAJECTORY_RELEASE", lambda b: b["lanes"]["LEGACY_A__M01"]["trajectory_source"].__setitem__("release_flags_all_false", False)),
        ("NC39_MAIN_METHOD_BDF", lambda b: b["lanes"]["LEGACY_A__M01"]["solver"].__setitem__("method", "BDF")),
        ("NC40_MAIN_MODE_FULL", lambda b: b["lanes"]["LEGACY_A__M01"]["solver"].__setitem__("mode", "full")),
        ("NC41_MAIN_MODES_DRIFT", lambda b: b["lanes"]["LEGACY_A__M01"]["solver"].__setitem__("n_modes_per_panel", 4)),
        ("NC42_MAIN_MOMENTUM_FAIL", lambda b: b["lanes"]["LEGACY_A__M01"]["metrics"].__setitem__("momentum_max_norm_dL", 1e-4)),
        ("NC43_MAIN_ENERGY_FAIL", lambda b: b["lanes"]["LEGACY_A__M01"]["metrics"].__setitem__("energy_audit_relative", 1e-3)),
        ("NC44_MAIN_QUAT_FAIL", lambda b: b["lanes"]["LEGACY_A__M01"]["metrics"].__setitem__("quaternion_norm_max_error", 1e-3)),
        ("NC45_MAIN_SPD_FAIL", lambda b: b["lanes"]["LEGACY_A__M01"]["metrics"].__setitem__("mass_matrix_min_eigenvalue", -1.0)),
        ("NC46_HISTORY_LANE_ID", lambda b: b["histories"]["LEGACY_A__M01"][0].__setitem__("lane_id", "M3R_B__M01")),
        ("NC47_HISTORY_METRIC", lambda b: b["histories"]["LEGACY_A__M01"][1].__setitem__("base_dev_deg", "999")),
        ("NC48_SUMMARY_HASH", lambda b: b["register"]["lanes"][0]["summary"].__setitem__("sha256", "F"*64)),
        ("NC49_HISTORY_HASH", lambda b: b["lanes"]["LEGACY_A__M01"]["history"].__setitem__("sha256", "F"*64)),
        ("NC50_UNDAMPED_ENERGY", lambda b: b["local"].__setitem__("undamped_energy_audit_relative", 1e-2)),
        ("NC51_RIGID_MODES", lambda b: b["local"]["rigid_degeneration"].__setitem__("n_modes_per_panel", 1)),
        ("NC52_RIGID_MODAL_ENERGY", lambda b: b["local"]["rigid_degeneration"].__setitem__("panel_modal_energy_peak_J", 1e-2)),
        ("NC53_MODAL_CONVERGENCE", lambda b: b["local"]["modal_refinement_relative"].__setitem__("max_m4_to_m5", 0.2)),
        ("NC54_CROSS_SOLVER", lambda b: b["local"]["radau_vs_bdf_relative"].__setitem__("maximum", 0.2)),
        ("NC55_LOCAL_CLEARS_E15", lambda b: b["local"].__setitem__("e15_certification_debt_cleared", True)),
        ("NC56_E15_STATUS_PASS", lambda b: b["input"]["e15_certification_debt"].__setitem__("ancf_certification_status", "PASS")),
        ("NC57_E15_DIFF_HIDE", lambda b: b["input"]["e15_certification_debt"].__setitem__("e15_cross_solver_max_relative_difference", 0.01)),
        ("NC58_E15_FINAL_AVAILABLE", lambda b: b["input"]["e15_certification_debt"].__setitem__("e15_final_candidate_available", True)),
        ("NC59_PROVISIONAL_STRIP", lambda b: b["input"]["sim11_provisional_boundary"].__setitem__("PROVISIONAL_PARAMS", False)),
        ("NC60_R2_CLAIM", lambda b: b["register"].__setitem__("current_R2_coupled_model_used", True)),
        ("NC61_SIM11_MANIFEST_COMPLETE", lambda b: b["input"]["sim11_historical_artifact_audit"].__setitem__("current_artifact_manifest_bytewise_complete", True)),
        ("NC62_REORG_DIFF_FALSE", lambda b: b["input"]["sim11_historical_artifact_audit"].__setitem__("reorg_route_only_semantic_diff", False)),
        ("NC63_SIM11_NEXT_INHERITED", lambda b: b["input"]["sim11_historical_artifact_audit"].__setitem__("historical_next_stage_authorized_inherited", True)),
        ("NC64_SIM11_VERDICT_DRIFT", lambda b: b["input"]["sim11_historical_artifact_audit"].__setitem__("historical_gate_verdict", "PASS")),
        ("NC65_MOUNT_MODEL_PHYSICAL", lambda b: b["register"]["mount_frame_boundary"].__setitem__("mount_frame_model", "B601_ARM_BASE_PHYSICAL")),
        ("NC66_PHYSICAL_MOUNT_APPLIED", lambda b: b["register"]["mount_frame_boundary"].__setitem__("physical_mount_frame_applied", True)),
        ("NC67_PHYSICAL_TRANSFORM_FILL", lambda b: b["register"]["mount_frame_boundary"].__setitem__("physical_mount_transform", [1,0,0])),
        ("NC68_M4_INSTALL_CLAIM", lambda b: b["register"]["mount_frame_boundary"].__setitem__("m4_digital_prototype_installation_dynamics_claimed", True)),
        ("NC69_RELEASED_MASS_FILL", lambda b: b["register"]["physical_unknowns"].__setitem__("released_service_mass_kg", 29.0)),
        ("NC70_CONTACT_DURATION_FILL", lambda b: b["register"]["physical_unknowns"].__setitem__("contact_duration_s", 0.02)),
        ("NC71_LOCK_FILL", lambda b: b["register"]["physical_unknowns"].__setitem__("lock_state", "LOCKED")),
        ("NC72_RECOVERY_FILL", lambda b: b["register"]["physical_unknowns"].__setitem__("attached_recovery_terminal_state", [0,0,0])),
        ("NC73_MISSION_THRESHOLD_FILL", lambda b: b["register"]["physical_unknowns"].__setitem__("mission_acceptance_thresholds", {"angle": 1})),
        ("NC74_HARDWARE_TORQUE_FILL", lambda b: b["register"]["physical_unknowns"].__setitem__("hardware_torque_Nm", 1.0)),
        ("NC75_CAD_GENERATED", lambda b: b["register"].__setitem__("cad_or_mesh_generated", True)),
        ("NC76_PRODUCTION_READY", lambda b: b["register"].__setitem__("production_dynamics_ready", True)),
        ("NC77_FLIGHT_READY", lambda b: b["register"].__setitem__("flight_qualification_ready", True)),
        ("NC78_GATE_PASS", lambda b: b["gate"].__setitem__("gate", "PASS")),
        ("NC79_GATE_NEXT_TRUE", lambda b: b["gate"].__setitem__("next_stage_authorized", True)),
        ("NC80_GATE_RELEASE_TRUE", lambda b: b["gate"].__setitem__("release_credit", True)),
        ("NC81_RELEASED_SEGMENT", lambda b: b["gate"].__setitem__("released_segments", 1)),
        ("NC82_GATE_SELECT_BRANCH", lambda b: b["gate"].__setitem__("selected_mass_branch", "M4_DIAG_M3R_B")),
        ("NC83_GATE_VERDICT_PROMOTE", lambda b: b["gate"].__setitem__("verdict", "PRODUCTION_READY")),
        ("NC84_MANIFEST_VALIDATION_INCLUDED", lambda b: b["manifest"].__setitem__("validation_report_excluded", False)),
        ("NC85_MANIFEST_ARTIFACT_HASH", lambda b: b["manifest"]["artifacts"][0].__setitem__("sha256", "0"*64)),
        ("NC86_INPUT_SOURCE_HASH", lambda b: b["input"]["records"][0].__setitem__("sha256", "0"*64)),
        ("NC87_URDF_HASH", lambda b: b["input"].__setitem__("accepted_urdf_sha256", "0"*64)),
        ("NC88_SOLAR_HASH", lambda b: b["input"].__setitem__("solar_r2_sha256", "0"*64)),
        ("NC89_NAN_METRIC", lambda b: b["lanes"]["LEGACY_A__M01"]["metrics"].__setitem__("peak_base_rate_rad_s", float("nan"))),
        ("NC90_SOURCE_A2_IMPORT", lambda b: b.__setitem__("builder_text", b["builder_text"] + "\nimport scene_a2_capture\n")),
        ("NC91_STOCK_LOADER_USED", lambda b: b["input"]["sim11_provisional_boundary"].__setitem__("stock_load_model_config_used", True)),
        ("NC92_TARGET_METADATA_READ", lambda b: b["input"]["sim11_provisional_boundary"].__setitem__("target_capture_metadata_read", True)),
        ("NC93_CURRENT_M7_DYNAMICS_CLAIM", lambda b: b["gate"].__setitem__("current_M7_design_dynamics_closure_claimed", True)),
    ]


def main() -> int:
    bundle = load_bundle()
    positives = positive_checks(bundle)
    negative_results = []
    for control_id, mutate in mutation_controls():
        mutated = copy.deepcopy(bundle)
        mutate(mutated)
        safe, errors = gate_safe(mutated)
        negative_results.append({"id": control_id, "rejected": not safe, "error_count": len(errors), "first_error": errors[0] if errors else None})
    positive_pass = sum(item["pass"] for item in positives)
    negative_pass = sum(item["rejected"] for item in negative_results)
    safe, errors = gate_safe(bundle)
    passed = safe and positive_pass == len(positives) and negative_pass == len(negative_results)
    report = {
        "schema": "E20_VALIDATION_V1",
        "generated_local": GENERATED_LOCAL,
        "validator": f"{PREFIX}/tests/validate_e20_diagnostics.py",
        "unified_predicate": "gate_safe(bundle)",
        "positive_checks": positives,
        "positive_total": len(positives),
        "positive_passed": positive_pass,
        "negative_controls": negative_results,
        "negative_total": len(negative_results),
        "negative_rejected": negative_pass,
        "base_gate_safe": safe,
        "base_gate_errors": errors,
        "manifest_validation_excluded": True,
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
        "status": "PASS" if passed else "FAIL",
        "verdict": "PASS_E20_INDEPENDENT_SURROGATE_MASS_BRANCH_COUPLED_ARM_ONLY_DIAGNOSTIC_INTEGRITY__ALL_PHYSICAL_MISSION_PRODUCTION_AND_RELEASE_GATES_HOLD" if passed else "FAIL_E20_VALIDATION",
    }
    path = RESULTS_ROOT / "E20_VALIDATION_V1.json"
    path.write_bytes(json_bytes(report))
    print(json.dumps({
        "schema": report["schema"],
        "status": report["status"],
        "positive": f"{positive_pass}/{len(positives)}",
        "negative": f"{negative_pass}/{len(negative_results)}",
        "gate": report["gate"],
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
