"""Independent validator for the e18 B601 mission-input branch package."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
JOINTS = [f"joint{i}" for i in range(1, 7)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_yaml(relative: str) -> Any:
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8-sig"))


def read_json(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def csv_rows(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def all_none(mapping: dict[str, Any], keys: list[str]) -> bool:
    return all(mapping.get(key) is None for key in keys)


def main() -> None:
    authority_rel = "30_simulation/e18_b601_mission_input_branches/00_authority/E18_AUTHORITY_CONTRACT_V1.yaml"
    m01_rel = "30_simulation/e18_b601_mission_input_branches/01_contracts/M01_RELEASE_EVENT_AND_SWEEP_V1.yaml"
    m05_rel = "30_simulation/e18_b601_mission_input_branches/01_contracts/M05_22_TARGET_STATE_AND_SYNC_V1.yaml"
    m06_rel = "30_simulation/e18_b601_mission_input_branches/01_contracts/M06_22_CONTACT_AND_LOCK_V1.yaml"
    m07_rel = "30_simulation/e18_b601_mission_input_branches/01_contracts/M07_22_ATTACHED_TARGET_RECOVERY_V1.yaml"
    m01_csv_rel = "30_simulation/e18_b601_mission_input_branches/02_candidates/M01_HELD_STOW_TO_RELEASE_CLEAR_QUINTIC_V1.csv"
    m05_branches_rel = "30_simulation/e18_b601_mission_input_branches/02_candidates/M05_22_TARGET_STATE_BRANCHES_V1.json"
    m06_csv_rel = "30_simulation/e18_b601_mission_input_branches/02_candidates/M06_22_HALF_SINE_EQUAL_IMPULSE_STIMULUS_MATRIX_V1.csv"
    m07_branches_rel = "30_simulation/e18_b601_mission_input_branches/02_candidates/M07_22_ATTACHED_TARGET_RECOVERY_BRANCHES_V1.json"
    register_rel = "30_simulation/e18_b601_mission_input_branches/results/E18_B601_MISSION_INPUT_BRANCH_REGISTER_V1.json"
    gate_rel = "30_simulation/e18_b601_mission_input_branches/results/E18_B601_MISSION_INPUT_BRANCH_GATE_V1.json"
    manifest_rel = "30_simulation/e18_b601_mission_input_branches/results/E18_OUTPUT_MANIFEST_V1.json"

    authority = read_yaml(authority_rel)
    m01 = read_yaml(m01_rel)
    m05 = read_yaml(m05_rel)
    m06 = read_yaml(m06_rel)
    m07 = read_yaml(m07_rel)
    m01_rows = csv_rows(m01_csv_rel)
    m05_branches = read_json(m05_branches_rel)
    m06_rows = csv_rows(m06_csv_rel)
    m07_branches = read_json(m07_branches_rel)
    register = read_json(register_rel)
    gate = read_json(gate_rel)
    manifest = read_json(manifest_rel)

    mission_rel = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml"
    control_rel = "20_engineering/config/control_scene/control_01_v0.yaml"
    sim06_rel = "30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv"
    sim15_rel = "30_simulation/sim_15_m5_geometry_gated_grasping/evidence/SIM15_DIAGNOSTIC_BASELINE_V1.json"
    mission = read_yaml(mission_rel)
    control = read_yaml(control_rel)
    sim06 = csv_rows(sim06_rel)
    sim15 = read_json(sim15_rel)

    checks: list[dict[str, Any]] = []

    def check(identifier: str, predicate: bool, evidence: Any) -> None:
        checks.append({"id": identifier, "pass": bool(predicate), "evidence": evidence})

    required_files = [authority_rel, m01_rel, m05_rel, m06_rel, m07_rel, m01_csv_rel, m05_branches_rel, m06_csv_rel, m07_branches_rel, register_rel, gate_rel, manifest_rel]
    for relative in required_files:
        check(f"FILE_{Path(relative).name}", (ROOT / relative).is_file(), relative)

    check("SCHEMA_AUTHORITY", authority.get("schema") == "E18_B601_MISSION_INPUT_BRANCH_AUTHORITY_CONTRACT_V1", authority.get("schema"))
    check("SCHEMA_M01", m01.get("schema") == "M01_RELEASE_EVENT_AND_SWEEP_CONTRACT_V1", m01.get("schema"))
    check("SCHEMA_M05", m05.get("schema") == "M05_22_TARGET_STATE_AND_SYNC_CONTRACT_V1", m05.get("schema"))
    check("SCHEMA_M06", m06.get("schema") == "M06_22_CONTACT_AND_LOCK_CONTRACT_V1", m06.get("schema"))
    check("SCHEMA_M07", m07.get("schema") == "M07_22_ATTACHED_TARGET_RECOVERY_CONTRACT_V1", m07.get("schema"))
    check("SCHEMA_REGISTER", register.get("schema") == "E18_B601_MISSION_INPUT_BRANCH_REGISTER_V1", register.get("schema"))
    check("SCHEMA_GATE", gate.get("schema") == "E18_B601_MISSION_INPUT_BRANCH_GATE_V1", gate.get("schema"))
    check("SCHEMA_MANIFEST", manifest.get("schema") == "E18_B601_MISSION_INPUT_BRANCH_OUTPUT_MANIFEST_V1", manifest.get("schema"))

    urdf_path = ROOT / authority["immutable_asset"]["path"]
    check("URDF_HASH_IMMUTABLE", sha256(urdf_path) == URDF_SHA256 == authority["immutable_asset"]["sha256"], sha256(urdf_path))
    check("URDF_MODIFICATION_FORBIDDEN", authority["immutable_asset"]["modification"] == "FORBIDDEN", authority["immutable_asset"])

    source_results = []
    for item in authority["source_bindings"]:
        path = ROOT / item["path"]
        match = path.is_file() and sha256(path) == item["sha256"] and path.stat().st_size == item["bytes"]
        source_results.append({"id": item["id"], "match": match})
    check("ALL_SOURCE_HASHES_MATCH", all(item["match"] for item in source_results), source_results)
    check("GRIPPER_V2_GATE_VALIDATION_BOUND", {"gripper_v2", "gripper_gate", "gripper_validation"}.issubset({item["id"] for item in authority["source_bindings"]}), [item["id"] for item in authority["source_bindings"]])

    manifest_results = []
    for item in manifest["artifacts"]:
        path = ROOT / item["path"]
        match = path.is_file() and sha256(path) == item["sha256"] and path.stat().st_size == item["bytes"]
        manifest_results.append({"path": item["path"], "match": match})
    check("MANIFEST_HASH_CLOSURE", all(item["match"] for item in manifest_results), manifest_results)
    check("MANIFEST_COUNTS_COMPUTED", manifest["artifact_count"] == len(manifest["artifacts"]) and manifest["source_count"] == len(manifest["source_bindings"]), {"artifact_count": len(manifest["artifacts"]), "source_count": len(manifest["source_bindings"])})

    q0 = [float(v) for v in mission["states"]["STOW"]["q_rad"]]
    q1 = [float(v) for v in mission["states"]["RELEASE_CLEAR"]["q_rad"]]
    check("M01_SAMPLE_COUNT", len(m01_rows) == 1151 == m01["joint_coordinate_branch"]["sample_count"], len(m01_rows))
    times = [float(row["t_s"]) for row in m01_rows]
    check("M01_TIME_GRID", math.isclose(times[0], 0.0, abs_tol=1e-15) and math.isclose(times[-1], 11.5, abs_tol=1e-15) and all(math.isclose(b-a, 0.01, abs_tol=1e-12) for a, b in zip(times, times[1:])), [times[0], times[-1]])
    first_q = [float(m01_rows[0][f"{name}_q_rad"]) for name in JOINTS]
    last_q = [float(m01_rows[-1][f"{name}_q_rad"]) for name in JOINTS]
    check("M01_ENDPOINT_Q0", all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(first_q, q0)), first_q)
    check("M01_ENDPOINT_Q1", all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(last_q, q1)), last_q)
    endpoint_derivatives = [float(m01_rows[i][f"{name}_{field}"]) for i in (0, -1) for name in JOINTS for field in ("dq_rad_s", "ddq_rad_s2")]
    check("M01_ZERO_ENDPOINT_DERIVATIVES", max(abs(value) for value in endpoint_derivatives) <= 1e-12, max(abs(value) for value in endpoint_derivatives))
    analytic_ok = True
    for row in m01_rows:
        t = float(row["t_s"])
        u = t / 11.5
        s = 10*u**3 - 15*u**4 + 6*u**5
        ds = (30*u**2 - 60*u**3 + 30*u**4) / 11.5
        dds = (60*u - 180*u**2 + 120*u**3) / 11.5**2
        for idx, name in enumerate(JOINTS):
            delta = q1[idx] - q0[idx]
            analytic_ok &= math.isclose(float(row[f"{name}_q_rad"]), q0[idx] + delta*s, abs_tol=2e-14)
            analytic_ok &= math.isclose(float(row[f"{name}_dq_rad_s"]), delta*ds, abs_tol=2e-14)
            analytic_ok &= math.isclose(float(row[f"{name}_ddq_rad_s2"]), delta*dds, abs_tol=2e-14)
    check("M01_ANALYTIC_QUINTIC_ALL_ROWS", analytic_ok, "1151 rows x 18 state values")
    speed_limits = [float(v) for v in control["provisional_actuator_limits"]["joint_speed_abs_rad_per_s"]]
    accel_limits = [float(v) for v in control["provisional_actuator_limits"]["joint_acceleration_abs_rad_per_s2"]]
    max_speed = [max(abs(float(row[f"{name}_dq_rad_s"])) for row in m01_rows) for name in JOINTS]
    max_accel = [max(abs(float(row[f"{name}_ddq_rad_s2"])) for row in m01_rows) for name in JOINTS]
    check("M01_PROVISIONAL_SPEED_LIMITS", all(a <= b + 1e-12 for a, b in zip(max_speed, speed_limits)), max_speed)
    check("M01_PROVISIONAL_ACCEL_LIMITS", all(a <= b + 1e-12 for a, b in zip(max_accel, accel_limits)), max_accel)
    release = m01["release_event_contract"]
    check("M01_PHYSICAL_FIELDS_HELD", all_none(release, ["physical_stow_q_rad", "hdrm_part_and_revision", "release_command_definition", "release_confirmed_signal_definition", "release_confirmed", "release_timeout_s", "release_sweep_geometry_ref"]), release)
    check("M01_GUARD_FAIL_CLOSED", release["arm_motion_enable_guard"] == "release_confirmed == true" and "HOLD" in release["guard_binding_status"], release["guard_binding_status"])

    branches = m05_branches["branches"]
    ids = [item["branch_id"] for item in branches]
    check("M05_EXACTLY_TWO_BRANCHES", ids == ["SIM13_KINEMATIC_BOOTSTRAP", "SCENE_MANIFEST_STATIC_DISPLAY"], ids)
    check("M05_BRANCHES_NONMERGEABLE", m05["branch_merge_allowed"] is False and all(item["merge_allowed"] is False for item in branches), [item["merge_allowed"] for item in branches])
    sim13_branch, display_branch = branches
    check("M05_SIM13_STATE", sim13_branch["target_relative_position_m"] == [1.0, 0.0, 0.0] and sim13_branch["target_relative_quaternion_xyzw"] == [0.0, 0.0, 0.0, 1.0] and math.isclose(sim13_branch["target_angular_velocity_rad_s"][2], math.radians(0.5), abs_tol=1e-15), sim13_branch["target_angular_velocity_rad_s"])
    R = display_branch["R_TS"]
    p_t = display_branch["primary_grasp_point_T_m"]
    origin = display_branch["target_origin_S_m"]
    mapped = [origin[i] + sum(float(R[i][j])*float(p_t[j]) for j in range(3)) for i in range(3)]
    check("M05_DISPLAY_GRASP_MAP", all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(mapped, display_branch["capture_point_S_m"])), mapped)
    check("M05_BRANCH_VALUES_NOT_FUSED", sim13_branch["target_relative_position_m"] != display_branch["target_origin_S_m"] and m05_branches["selected_branch_for_mission"] is None, [sim13_branch["target_relative_position_m"], display_branch["target_origin_S_m"]])
    check("M05_PHYSICAL_SYNC_FIELDS_NULL", all_none(m05["required_physical_inputs"], list(m05["required_physical_inputs"])), m05["required_physical_inputs"])

    expected_grid = {(v, tc) for v in (0.005, 0.01, 0.02, 0.03) for tc in (5, 10, 20, 50, 100)}
    observed_grid = {(float(row["approach_speed_m_s"]), int(row["solver_contact_window_ms"])) for row in m06_rows}
    check("M06_CASE_COUNT", len(m06_rows) == 20 == m06["stimulus_matrix"]["case_count"], len(m06_rows))
    check("M06_GRID_COMPLETE", observed_grid == expected_grid, sorted(observed_grid))
    source_J = {float(row["v_app_mps"]): float(row["contact_impulse_N_s"]) for row in sim06 if row["target"] == "target_satellite_v0" and math.isclose(float(row["tumble_dps"]), 0.5)}
    j_match = all(math.isclose(float(row["source_impulse_N_s"]), source_J[float(row["approach_speed_m_s"])], abs_tol=1e-15) for row in m06_rows)
    check("M06_J_FROM_SIM06", j_match, source_J)
    formula_ok = True
    reconstruction_ok = True
    for row in m06_rows:
        J = float(row["source_impulse_N_s"])
        Tc = float(row["solver_contact_window_s"])
        peak = float(row["solver_peak_force_N"])
        formula_ok &= math.isclose(peak, math.pi*J/(2*Tc), rel_tol=2e-15, abs_tol=2e-14)
        reconstruction_ok &= math.isclose(float(row["solver_reconstructed_impulse_N_s"]), 2*peak*Tc/math.pi, rel_tol=2e-15, abs_tol=2e-15)
    check("M06_HALF_SINE_PEAK_FORMULA", formula_ok, "Fpeak=pi*J/(2Tc)")
    check("M06_IMPULSE_RECONSTRUCTION", reconstruction_ok, "integral F dt = J")
    physical_csv_fields = ["physical_contact_duration_s", "physical_contact_force_N", "physical_contact_pressure_Pa", "physical_contact_normal", "physical_lock_confirmation"]
    check("M06_CSV_PHYSICAL_FIELDS_BLANK", all(all(row[key] == "" for key in physical_csv_fields) for row in m06_rows), physical_csv_fields)
    physical_contract = m06["physical_contact_and_lock"]
    physical_keys = [key for key in physical_contract if key != "status"]
    check("M06_CONTRACT_PHYSICAL_FIELDS_NULL", all_none(physical_contract, physical_keys) and "HOLD" in physical_contract["status"], physical_contract)
    check("M06_STIMULUS_NOT_HARDWARE", all(row["stimulus_role"] == "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT" for row in m06_rows), sorted({row["stimulus_role"] for row in m06_rows}))
    gripper_bind_ids = {item["id"] for item in m06["source_bindings"]}
    check("M06_GRIPPER_V2_CHAIN", {"gripper_v2", "gripper_gate", "gripper_validation"}.issubset(gripper_bind_ids), sorted(gripper_bind_ids))

    arm_branch = m07_branches["arm_only_trajectory_branch"]
    e17_rows = csv_rows(arm_branch["path"])
    check("M07_E17_HASH", sha256(ROOT / arm_branch["path"]) == arm_branch["sha256"], arm_branch["sha256"])
    check("M07_E17_GRID", len(e17_rows) == arm_branch["sample_count"] == 451 and math.isclose(float(e17_rows[-1]["t_s"]), 4.5, abs_tol=1e-15) and math.isclose(arm_branch["sample_period_s"], 0.01, abs_tol=1e-15), {"samples": len(e17_rows), "duration": e17_rows[-1]["t_s"]})
    masses = m07_branches["C08_diagnostic_mass_branches"]
    check("M07_C08_TWO_MASS_BRANCHES", len(masses) == 2 and math.isclose(masses[0]["mass_kg"], 50.695555949342986, abs_tol=1e-12) and math.isclose(masses[1]["mass_kg"], 51.081436764691, abs_tol=1e-12), masses)
    check("M07_MASS_UNCERTAINTY_NULL", all(item["standard_uncertainty_kg"] is None and item["released"] is False for item in masses), masses)
    source_case = next(item for item in sim15["capture_envelope"]["cases"] if item["anchor_id"] == "ANCHOR_22KG_0P5DPS" and math.isclose(float(item["approach_speed_mps"]), 0.01))
    full_case = m07_branches["sim15_0p01_m_s_full_state_branch"]["full_case_record"]
    check("M07_SIM15_FULL_CASE_EXACT", full_case == source_case, full_case["case_id"])
    check("M07_SIM15_PHYSICAL_CONTACT_NULL", full_case["output"]["contact_duration_s"] is None and full_case["output"]["contact_force_N"] is None and full_case["output"]["contact_pressure_Pa"] is None and full_case["output"]["physical_contact_computed"] is False, full_case["output"]["model_scope"])
    check("M07_SIM15_FULL_STATE_VALUES", math.isclose(full_case["output"]["total_mass_kg"], 51.081436764691, abs_tol=1e-12) and full_case["output"]["combined_center_of_mass_m"] == [0.43068483177840156, 0.0, 0.0] and math.isclose(full_case["output"]["combined_linear_velocity_mps"][1], 0.004306848317784016, abs_tol=1e-18), {"mass": full_case["output"]["total_mass_kg"], "com": full_case["output"]["combined_center_of_mass_m"]})
    check("M07_LOCKED_FIELDS_NULL", all(m07_branches[key] is None for key in ("selected_post_capture_model_branch", "locked_transform_gripper_to_target", "contact_normals", "released_mass_kg", "released_cg_m", "released_inertia_kg_m2")), "selected transform normals released mass/cg/inertia")
    check("M07_REQUIRED_PHYSICAL_INPUTS_NULL", all_none(m07["required_physical_inputs"], list(m07["required_physical_inputs"])), m07["required_physical_inputs"])

    check("REGISTER_FOUR_SEGMENTS", [item["segment_id"] for item in register["segments"]] == ["M01", "M05_22", "M06_22", "M07_22"], [item["segment_id"] for item in register["segments"]])
    actual_branch_counts = [1, len(branches), len(m06_rows), 1 + len(masses) + 1]
    check("REGISTER_BRANCH_COUNTS_FROM_ACTUAL_LISTS", [item["numeric_branch_count"] for item in register["segments"]] == actual_branch_counts, {"registered": [item["numeric_branch_count"] for item in register["segments"]], "actual": actual_branch_counts})
    coverage = register["coverage"]
    check("REGISTER_COVERAGE_COUNTS_FROM_RECORDS", coverage["segments_in_scope"] == len(register["segments"]) and coverage["segments_with_machine_contract"] == sum((ROOT / item["contract"]["path"]).is_file() for item in register["segments"]) and coverage["segments_with_hash_bound_nonrelease_branches"] == sum(bool(item["candidate"]["sha256"]) for item in register["segments"]), coverage)
    check("REGISTER_ZERO_RELEASE", register["coverage"]["released_segments"] == 0 and all(item["released_for_mission_gate"] is False for item in register["segments"]), register["coverage"])
    check("GATE_COUNTS_COMPUTED", gate["criteria_total"] == len(gate["criteria"]) and gate["criteria_observed"] == sum(bool(item["observed"]) for item in gate["criteria"]), {"total": len(gate["criteria"]), "observed": sum(bool(item["observed"]) for item in gate["criteria"])})
    check("GATE_FAIL_CLOSED", gate["gate"] == "HOLD" and gate["mission_trajectory_release_ready"] is False and gate["physical_contact_ready"] is False and gate["hardware_motion_ready"] is False and gate["production_dynamics_ready"] is False and gate["next_stage_authorized"] is False and gate["release_credit"] is False, gate["verdict"])
    check("TEST_PASS_NO_AUTHORITY", authority["testing_pass_grants_authority"] is False and gate["testing_pass_grants_authority"] is False, False)
    forbidden_suffixes = {".step", ".stp", ".stl", ".obj", ".glb", ".gltf", ".urdf"}
    forbidden_files = [str(path.relative_to(PACKAGE)) for path in PACKAGE.rglob("*") if path.is_file() and path.suffix.lower() in forbidden_suffixes]
    check("NO_CAD_OR_GEOMETRY", not forbidden_files and register["cad_or_geometry_created"] is False, forbidden_files)

    baseline_bundle = {
        "authority": authority,
        "m01": m01,
        "m01_rows": m01_rows,
        "m05": m05,
        "m05_branches": m05_branches,
        "m06": m06,
        "m06_rows": m06_rows,
        "m07": m07,
        "m07_branches": m07_branches,
        "register": register,
        "gate": gate,
        "manifest": manifest,
        "package_file_suffixes": [path.suffix.lower() for path in PACKAGE.rglob("*") if path.is_file()],
    }

    def gate_safe(bundle: dict[str, Any]) -> bool:
        """One fail-closed acceptance predicate used by baseline and every mutation.

        It accepts only the currently scoped NON_RELEASE branch package.  Any
        exception, missing key, unit/shape error, filled physical field, model
        merge, release promotion, hash drift, or CAD/geometry artifact rejects.
        """
        try:
            auth = bundle["authority"]
            c01 = bundle["m01"]
            rows01 = bundle["m01_rows"]
            c05 = bundle["m05"]
            branches05 = bundle["m05_branches"]["branches"]
            c06 = bundle["m06"]
            rows06 = bundle["m06_rows"]
            c07 = bundle["m07"]
            branches07 = bundle["m07_branches"]
            reg = bundle["register"]
            result_gate = bundle["gate"]
            output_manifest = bundle["manifest"]

            if auth["immutable_asset"]["sha256"] != URDF_SHA256 or auth["immutable_asset"]["modification"] != "FORBIDDEN":
                return False
            if any((not (ROOT / item["path"]).is_file()) or sha256(ROOT / item["path"]) != item["sha256"] or (ROOT / item["path"]).stat().st_size != item["bytes"] for item in auth["source_bindings"]):
                return False
            if auth["released_for_mission_gate"] is not False or auth["next_stage_authorized"] is not False or auth["testing_pass_grants_authority"] is not False or auth["released_segments"] != 0:
                return False

            branch01 = c01["joint_coordinate_branch"]
            if branch01["duration_s"] != 11.5 or branch01["sample_period_s"] != 0.01 or branch01["sample_count"] != len(rows01) or len(rows01) != 1151:
                return False
            row_times = [float(row["t_s"]) for row in rows01]
            if not (math.isclose(row_times[0], 0.0, abs_tol=1e-15) and math.isclose(row_times[-1], 11.5, abs_tol=1e-15) and all(math.isclose(b-a, 0.01, abs_tol=1e-12) for a, b in zip(row_times, row_times[1:]))):
                return False
            if branch01["q0_rad"] != q0 or branch01["q1_rad"] != q1:
                return False
            if any(not math.isclose(float(rows01[0][f"{name}_q_rad"]), q0[i], abs_tol=1e-12) for i, name in enumerate(JOINTS)):
                return False
            if any(not math.isclose(float(rows01[-1][f"{name}_q_rad"]), q1[i], abs_tol=1e-12) for i, name in enumerate(JOINTS)):
                return False
            if any(abs(float(rows01[index][f"{name}_{field}"])) > 1e-12 for index in (0, -1) for name in JOINTS for field in ("dq_rad_s", "ddq_rad_s2")):
                return False
            for row in rows01:
                t = float(row["t_s"])
                u = t / 11.5
                s = 10*u**3 - 15*u**4 + 6*u**5
                ds = (30*u**2 - 60*u**3 + 30*u**4) / 11.5
                dds = (60*u - 180*u**2 + 120*u**3) / 11.5**2
                for i, name in enumerate(JOINTS):
                    delta = q1[i] - q0[i]
                    if not math.isclose(float(row[f"{name}_q_rad"]), q0[i] + delta*s, abs_tol=2e-14):
                        return False
                    if not math.isclose(float(row[f"{name}_dq_rad_s"]), delta*ds, abs_tol=2e-14):
                        return False
                    if not math.isclose(float(row[f"{name}_ddq_rad_s2"]), delta*dds, abs_tol=2e-14):
                        return False
            release01 = c01["release_event_contract"]
            release01_keys = ["physical_stow_q_rad", "hdrm_part_and_revision", "release_command_definition", "release_confirmed_signal_definition", "release_confirmed", "release_timeout_s", "release_sweep_geometry_ref"]
            if not all_none(release01, release01_keys) or release01["arm_motion_enable_guard"] != "release_confirmed == true" or "HOLD" not in release01["guard_binding_status"]:
                return False
            if c01["released_for_mission_gate"] is not False or c01["next_stage_authorized"] is not False:
                return False

            branch_ids05 = [item["branch_id"] for item in branches05]
            if branch_ids05 != ["SIM13_KINEMATIC_BOOTSTRAP", "SCENE_MANIFEST_STATIC_DISPLAY"]:
                return False
            if c05["branch_merge_allowed"] is not False or any(item["merge_allowed"] is not False for item in branches05):
                return False
            if bundle["m05_branches"]["selected_branch_for_mission"] is not None or not all_none(c05["required_physical_inputs"], list(c05["required_physical_inputs"])):
                return False
            if branches05[0]["target_relative_position_m"] != [1.0, 0.0, 0.0] or not math.isclose(branches05[0]["target_angular_velocity_rad_s"][2], math.radians(0.5), abs_tol=1e-15):
                return False
            display05 = branches05[1]
            mapped05 = [display05["target_origin_S_m"][i] + sum(float(display05["R_TS"][i][j])*float(display05["primary_grasp_point_T_m"][j]) for j in range(3)) for i in range(3)]
            if any(not math.isclose(a, b, abs_tol=1e-12) for a, b in zip(mapped05, display05["capture_point_S_m"])):
                return False
            if c05["released_for_mission_gate"] is not False or c05["next_stage_authorized"] is not False:
                return False

            grid06 = {(float(row["approach_speed_m_s"]), int(row["solver_contact_window_ms"])) for row in rows06}
            if len(rows06) != 20 or c06["stimulus_matrix"]["case_count"] != len(rows06) or grid06 != expected_grid:
                return False
            for row in rows06:
                v_app = float(row["approach_speed_m_s"])
                J = float(row["source_impulse_N_s"])
                Tc = float(row["solver_contact_window_s"])
                peak = float(row["solver_peak_force_N"])
                if not math.isclose(J, source_J[v_app], abs_tol=1e-15):
                    return False
                if not math.isclose(peak, math.pi*J/(2*Tc), rel_tol=2e-15, abs_tol=2e-14):
                    return False
                if not math.isclose(float(row["solver_reconstructed_impulse_N_s"]), 2*peak*Tc/math.pi, rel_tol=2e-15, abs_tol=2e-15):
                    return False
                if any(row[key] != "" for key in physical_csv_fields):
                    return False
                if row["stimulus_role"] != "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT" or row["released_for_mission_gate"] != "false":
                    return False
            physical06 = c06["physical_contact_and_lock"]
            physical06_keys = [key for key in physical06 if key != "status"]
            if not all_none(physical06, physical06_keys) or "HOLD" not in physical06["status"]:
                return False
            if c06["gripper_velocity_semantics"]["physical_speed_authority"] != "HOLD" or c06["gripper_velocity_semantics"]["urdf_literal_use_for_physical_timing"] != "PROHIBITED":
                return False
            if not {"gripper_v2", "gripper_gate", "gripper_validation"}.issubset({item["id"] for item in c06["source_bindings"]}):
                return False
            if c06["released_for_mission_gate"] is not False or c06["next_stage_authorized"] is not False:
                return False

            masses07 = branches07["C08_diagnostic_mass_branches"]
            if len(masses07) != 2 or not math.isclose(masses07[0]["mass_kg"], 50.695555949342986, abs_tol=1e-12) or not math.isclose(masses07[1]["mass_kg"], 51.081436764691, abs_tol=1e-12):
                return False
            if any(item["standard_uncertainty_kg"] is not None or item["released"] is not False for item in masses07):
                return False
            locked07 = ("selected_post_capture_model_branch", "locked_transform_gripper_to_target", "contact_normals", "released_mass_kg", "released_cg_m", "released_inertia_kg_m2")
            if any(branches07[key] is not None for key in locked07) or not all_none(c07["required_physical_inputs"], list(c07["required_physical_inputs"])):
                return False
            sim15_branch = branches07["sim15_0p01_m_s_full_state_branch"]
            case07 = sim15_branch["full_case_record"]
            if case07 != source_case or sim15_branch["physical_contact_authority"] is not False or sim15_branch["merge_with_other_models_allowed"] is not False:
                return False
            if case07["output"]["physical_contact_computed"] is not False or any(case07["output"][key] is not None for key in ("contact_duration_s", "contact_force_N", "contact_pressure_Pa")):
                return False
            if c07["released_for_mission_gate"] is not False or c07["next_stage_authorized"] is not False:
                return False

            segment_ids = [item["segment_id"] for item in reg["segments"]]
            derived_branch_counts = [1, len(branches05), len(rows06), 1 + len(masses07) + 1]
            if segment_ids != ["M01", "M05_22", "M06_22", "M07_22"] or [item["numeric_branch_count"] for item in reg["segments"]] != derived_branch_counts:
                return False
            if any(item["released_for_mission_gate"] or item["physical_authority"] or item["hardware_authority"] for item in reg["segments"]):
                return False
            reg_coverage = reg["coverage"]
            if reg_coverage["segments_in_scope"] != len(reg["segments"]) or reg_coverage["released_segments"] != 0 or reg_coverage["physical_contact_released_segments"] != 0 or reg_coverage["hardware_released_segments"] != 0:
                return False
            if reg["accepted_urdf_sha256"] != URDF_SHA256 or reg["cad_or_geometry_created"] is not False or reg["next_stage_authorized"] is not False:
                return False

            if result_gate["gate"] != "HOLD" or result_gate["released_segments"] != 0:
                return False
            gate_false_fields = ("mission_trajectory_release_ready", "physical_contact_ready", "hardware_motion_ready", "production_dynamics_ready", "cad_geometry_authority", "testing_pass_grants_authority", "next_stage_authorized", "release_credit")
            if any(result_gate[key] is not False for key in gate_false_fields):
                return False
            if result_gate["criteria_total"] != len(result_gate["criteria"]) or result_gate["criteria_observed"] != sum(bool(item["observed"]) for item in result_gate["criteria"]):
                return False
            if output_manifest["accepted_urdf_sha256"] != URDF_SHA256 or output_manifest["released_for_mission_gate"] is not False or output_manifest["next_stage_authorized"] is not False:
                return False
            if output_manifest["artifact_count"] != len(output_manifest["artifacts"]) or output_manifest["source_count"] != len(output_manifest["source_bindings"]):
                return False
            if any((not (ROOT / item["path"]).is_file()) or sha256(ROOT / item["path"]) != item["sha256"] or (ROOT / item["path"]).stat().st_size != item["bytes"] for item in output_manifest["artifacts"]):
                return False
            if any(suffix in forbidden_suffixes for suffix in bundle["package_file_suffixes"]):
                return False
            return True
        except (KeyError, TypeError, ValueError, IndexError, OSError, ZeroDivisionError):
            return False

    check("UNIFIED_GATE_SAFE_BASELINE", gate_safe(copy.deepcopy(baseline_bundle)), "single fail-closed acceptance predicate")

    negatives: list[dict[str, Any]] = []

    def mutate_and_expect_rejected(identifier: str, mutator: Callable[[dict[str, Any]], None]) -> None:
        candidate = copy.deepcopy(baseline_bundle)
        mutator(candidate)
        accepted_after_mutation = gate_safe(candidate)
        negatives.append({
            "id": identifier,
            "pass": not accepted_after_mutation,
            "acceptance_predicate": "gate_safe",
            "accepted_after_mutation": accepted_after_mutation,
        })

    mutate_and_expect_rejected("NC01_MUTATED_URDF_HASH", lambda b: b["authority"]["immutable_asset"].__setitem__("sha256", "0" * 64))
    mutate_and_expect_rejected("NC02_SOURCE_BINDING_HASH_DRIFT", lambda b: b["authority"]["source_bindings"][0].__setitem__("sha256", "0" * 64))
    mutate_and_expect_rejected("NC03_M01_WRONG_DURATION", lambda b: b["m01"]["joint_coordinate_branch"].__setitem__("duration_s", 11.4))
    mutate_and_expect_rejected("NC04_M01_WRONG_DT", lambda b: b["m01"]["joint_coordinate_branch"].__setitem__("sample_period_s", 0.02))
    mutate_and_expect_rejected("NC05_M01_Q0_ALTERED", lambda b: b["m01_rows"][0].__setitem__("joint1_q_rad", str(float(b["m01_rows"][0]["joint1_q_rad"]) + 0.1)))
    mutate_and_expect_rejected("NC06_M01_Q1_ALTERED", lambda b: b["m01_rows"][-1].__setitem__("joint6_q_rad", "0.1"))
    mutate_and_expect_rejected("NC07_RELEASE_CONFIRMED_INVENTED", lambda b: b["m01"]["release_event_contract"].__setitem__("release_confirmed", True))
    mutate_and_expect_rejected("NC08_PHYSICAL_STOW_INVENTED", lambda b: b["m01"]["release_event_contract"].__setitem__("physical_stow_q_rad", q0))
    mutate_and_expect_rejected("NC09_M05_BRANCH_MERGE", lambda b: b["m05"].__setitem__("branch_merge_allowed", True))
    mutate_and_expect_rejected("NC10_M05_EPOCH_INVENTED", lambda b: b["m05"]["required_physical_inputs"].__setitem__("epoch", "2026-08-23T00:00:00Z"))
    mutate_and_expect_rejected("NC11_M05_BRANCH_SELECTED_FOR_MISSION", lambda b: b["m05_branches"].__setitem__("selected_branch_for_mission", "SIM13_KINEMATIC_BOOTSTRAP"))
    mutate_and_expect_rejected("NC12_M06_CASE_DROPPED", lambda b: b["m06_rows"].pop())
    mutate_and_expect_rejected("NC13_M06_PHYSICAL_DURATION_FILLED", lambda b: b["m06_rows"][0].__setitem__("physical_contact_duration_s", "0.02"))
    mutate_and_expect_rejected("NC14_M06_SOLVER_FORCE_PROMOTED", lambda b: b["m06_rows"][0].__setitem__("physical_contact_force_N", b["m06_rows"][0]["solver_peak_force_N"]))
    mutate_and_expect_rejected("NC15_M06_ZERO_FILLED_PRESSURE", lambda b: b["m06_rows"][0].__setitem__("physical_contact_pressure_Pa", "0"))
    mutate_and_expect_rejected("NC16_M06_WRONG_FPEAK", lambda b: b["m06_rows"][0].__setitem__("solver_peak_force_N", str(float(b["m06_rows"][0]["solver_peak_force_N"]) * 2)))
    mutate_and_expect_rejected("NC17_M06_CONTACT_NORMAL_INVENTED", lambda b: b["m06"]["physical_contact_and_lock"].__setitem__("contact_normal", [1.0, 0.0, 0.0]))
    mutate_and_expect_rejected("NC18_GRIPPER_PHYSICAL_SPEED_PROMOTED", lambda b: b["m06"]["gripper_velocity_semantics"].__setitem__("physical_speed_authority", "PASS"))
    mutate_and_expect_rejected("NC19_URDF_LITERAL_USED_FOR_TIMING", lambda b: b["m06"]["gripper_velocity_semantics"].__setitem__("urdf_literal_use_for_physical_timing", "ALLOWED"))
    mutate_and_expect_rejected("NC20_M07_LOCKED_TRANSFORM_INVENTED", lambda b: b["m07_branches"].__setitem__("locked_transform_gripper_to_target", [[1, 0, 0, 0]]))
    mutate_and_expect_rejected("NC21_M07_NORMAL_INVENTED", lambda b: b["m07_branches"].__setitem__("contact_normals", [[1, 0, 0]]))
    mutate_and_expect_rejected("NC22_M07_RELEASED_MASS_FILLED", lambda b: b["m07_branches"].__setitem__("released_mass_kg", 51.081436764691))
    mutate_and_expect_rejected("NC23_SIM15_PHYSICAL_CONTACT_PROMOTED", lambda b: b["m07_branches"]["sim15_0p01_m_s_full_state_branch"]["full_case_record"]["output"].__setitem__("physical_contact_computed", True))
    mutate_and_expect_rejected("NC24_M07_TERMINAL_STATE_INVENTED", lambda b: b["m07"]["required_physical_inputs"].__setitem__("recovery_terminal_state", {"q": [0] * 6}))
    mutate_and_expect_rejected("NC25_SEGMENT_RELEASED", lambda b: b["register"]["segments"][0].__setitem__("released_for_mission_gate", True))
    mutate_and_expect_rejected("NC26_NEXT_STAGE_TRUE", lambda b: b["gate"].__setitem__("next_stage_authorized", True))
    mutate_and_expect_rejected("NC27_PRODUCTION_DYNAMICS_READY", lambda b: b["gate"].__setitem__("production_dynamics_ready", True))
    mutate_and_expect_rejected("NC28_MANIFEST_RELEASE_PROMOTED", lambda b: b["manifest"].__setitem__("released_for_mission_gate", True))
    mutate_and_expect_rejected("NC29_CAD_FILE_PRESENT", lambda b: b["package_file_suffixes"].append(".step"))

    passed = sum(item["pass"] for item in checks)
    negative_passed = sum(item["pass"] for item in negatives)
    integrity = passed == len(checks) and negative_passed == len(negatives)
    validation = {
        "schema": "E18_B601_MISSION_INPUT_BRANCH_VALIDATION_V1",
        "generated_local": "2026-08-23T18:10:00+08:00",
        "scope": "independent hash, units, branch-separation, null/HOLD, dimensional and negative-control validation; no mission, physical, hardware or production authority",
        "package_integrity_pass": integrity,
        "verdict": "PASS_NON_RELEASE_BRANCH_INTEGRITY__MISSION_PHYSICAL_HARDWARE_AND_PRODUCTION_RELEASE_HOLD" if integrity else "FAIL_PACKAGE_INTEGRITY",
        "checks": checks,
        "checks_passed": passed,
        "checks_total": len(checks),
        "negative_controls": negatives,
        "negative_controls_passed": negative_passed,
        "negative_controls_total": len(negatives),
        "accepted_urdf_sha256": sha256(urdf_path),
        "gate": "HOLD",
        "released_for_mission_gate": False,
        "physical_contact_ready": False,
        "hardware_motion_ready": False,
        "production_dynamics_ready": False,
        "testing_pass_grants_authority": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    output = PACKAGE / "results/E18_VALIDATION_V1.json"
    output.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": validation["verdict"],
        "checks": f"{passed}/{len(checks)}",
        "negative_controls": f"{negative_passed}/{len(negatives)}",
        "validation_sha256": sha256(output),
    }, indent=2))
    if not integrity:
        for item in checks:
            if not item["pass"]:
                print(f"FAILED CHECK: {item['id']} -> {item['evidence']}", file=sys.stderr)
        for item in negatives:
            if not item["pass"]:
                print(f"FAILED NEGATIVE: {item['id']}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
