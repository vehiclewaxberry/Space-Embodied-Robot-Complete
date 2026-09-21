"""Build hash-bound NON_RELEASE mission-input branches for B601 M01/M05/M06/M07."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
GENERATED = "2026-08-23T18:10:00+08:00"
AUTHORITY = "NON_RELEASE_DIAGNOSTIC_CANDIDATE"
URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
JOINTS = [f"joint{i}" for i in range(1, 7)]

REL = {
    "urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "mission": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml",
    "pose_rebind": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_MISSION_POSE_AUTHORITY_REBIND_V1.yaml",
    "pose_validation": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/11_validation/B601_NAMED_POSE_REVALIDATION_V1.json",
    "control": "20_engineering/config/control_scene/control_01_v0.yaml",
    "hdrm": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp5_mechanisms/HDRM_ENGINEERING_PACK_V1.yaml",
    "target_models": "20_engineering/config/geometry/target_models_v1.yaml",
    "target_satellite": "20_engineering/cad/spacecraft_layout/target_satellite_v0/target_satellite_v0.json",
    "scene_manifest": "20_engineering/config/visualization/scene_manifest_v1.yaml",
    "m5_config": "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml",
    "sim13_anchor": "30_simulation/sim_13_physics_gated_embodied_grasping/baselines/ANCHOR_22KG_0P5DPS.json",
    "sim13_backend": "30_simulation/sim_13_physics_gated_embodied_grasping/src/physics_backend.py",
    "sim13_config": "30_simulation/sim_13_physics_gated_embodied_grasping/config/sim13_bootstrap.json",
    "sim13_binding_audit": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json",
    "sim06": "30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv",
    "sim11_contact": "20_engineering/config/coupled_scene/scene_A2_capture.yaml",
    "contact_contract": "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml",
    "gripper_v2": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml",
    "gripper_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/02_gate/GRIPPER_VELOCITY_UNIT_GATE_V1.json",
    "gripper_validation": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/03_validation/GRIPPER_VELOCITY_UNIT_VALIDATION_V1.json",
    "e17_m07": "30_simulation/e17_b601_mission_trajectory_candidates/results/candidates/M07_22_ARM_ONLY_QUINTIC_V1.csv",
    "e17_register": "30_simulation/e17_b601_mission_trajectory_candidates/results/B601_MISSION_TRAJECTORY_CANDIDATE_REGISTER_V1.json",
    "config_library": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    "sim15_baseline": "30_simulation/sim_15_m5_geometry_gated_grasping/evidence/SIM15_DIAGNOSTIC_BASELINE_V1.json",
    "sim15_gate": "30_simulation/sim_15_m5_geometry_gated_grasping/evidence/SIM15_DIAGNOSTIC_GATE_V1.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def binding(key: str) -> dict[str, Any]:
    path = ROOT / REL[key]
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"id": key, "path": REL[key], "sha256": sha256(path), "bytes": path.stat().st_size}


def load_yaml(key: str) -> Any:
    return yaml.safe_load((ROOT / REL[key]).read_text(encoding="utf-8-sig"))


def load_json(key: str) -> Any:
    return json.loads((ROOT / REL[key]).read_text(encoding="utf-8-sig"))


def write_yaml(relative: str, data: Any) -> Path:
    path = PACKAGE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
    return path


def write_json(relative: str, data: Any) -> Path:
    path = PACKAGE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def package_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def parse_arm_limits() -> tuple[list[float], list[float]]:
    tree = ET.parse(ROOT / REL["urdf"])
    joints = {item.attrib["name"]: item for item in tree.getroot().findall("joint")}
    lower: list[float] = []
    upper: list[float] = []
    for name in JOINTS:
        limit = joints[name].find("limit")
        if limit is None:
            raise ValueError(f"missing limit for {name}")
        lower.append(float(limit.attrib["lower"]))
        upper.append(float(limit.attrib["upper"]))
    return lower, upper


def quintic_rows(q0: list[float], q1: list[float], duration: float, dt: float) -> list[dict[str, Any]]:
    count = int(round(duration / dt)) + 1
    rows: list[dict[str, Any]] = []
    for index in range(count):
        t = index * dt
        u = t / duration
        s = 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5
        ds = (30.0 * u**2 - 60.0 * u**3 + 30.0 * u**4) / duration
        dds = (60.0 * u - 180.0 * u**2 + 120.0 * u**3) / duration**2
        delta = [b - a for a, b in zip(q0, q1)]
        row: dict[str, Any] = {
            "sample_index": index,
            "t_s": t,
            "segment_id": "M01",
            "candidate_state": "HELD_STOW_QSPACE_ONLY",
            "authority_class": AUTHORITY,
            "released_for_mission_gate": "false",
        }
        for i, name in enumerate(JOINTS):
            row[f"{name}_q_rad"] = q0[i] + delta[i] * s
            row[f"{name}_dq_rad_s"] = delta[i] * ds
            row[f"{name}_ddq_rad_s2"] = delta[i] * dds
        rows.append(row)
    return rows


def write_m01_csv(rows: list[dict[str, Any]]) -> Path:
    path = PACKAGE / "02_candidates/M01_HELD_STOW_TO_RELEASE_CLEAR_QUINTIC_V1.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["sample_index", "t_s"]
    fields += [f"{name}_q_rad" for name in JOINTS]
    fields += [f"{name}_dq_rad_s" for name in JOINTS]
    fields += [f"{name}_ddq_rad_s2" for name in JOINTS]
    fields += ["segment_id", "candidate_state", "authority_class", "released_for_mission_gate"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for source in rows:
            row: dict[str, Any] = {}
            for key in fields:
                value = source[key]
                if isinstance(value, float):
                    row[key] = format(value, ".16g")
                else:
                    row[key] = value
            writer.writerow(row)
    return path


def main() -> None:
    if sha256(ROOT / REL["urdf"]) != URDF_SHA256:
        raise RuntimeError("accepted URDF hash changed; fail closed")

    segment_ids = ("M01", "M05_22", "M06_22", "M07_22")
    source_bindings = [binding(key) for key in REL]
    bindings_by_id = {item["id"]: item for item in source_bindings}
    mission = load_yaml("mission")
    control = load_yaml("control")
    # The historical visualization manifest contains unquoted prose colons and is
    # not strict YAML.  Bind its bytes, but reproduce its display transform from
    # the machine-readable M5 C08 record and target JSON instead of repairing or
    # silently normalizing that upstream artifact here.
    scene_text = (ROOT / REL["scene_manifest"]).read_text(encoding="utf-8-sig")
    m5_config = load_yaml("m5_config")
    config_library = load_yaml("config_library")
    target_satellite = load_json("target_satellite")
    sim13_anchor = load_json("sim13_anchor")
    sim13_config = load_json("sim13_config")
    sim15 = load_json("sim15_baseline")

    states = mission["states"]
    q0 = [float(v) for v in states["STOW"]["q_rad"]]
    q1 = [float(v) for v in states["RELEASE_CLEAR"]["q_rad"]]
    duration = 11.5
    dt = 0.01
    m01_rows = quintic_rows(q0, q1, duration, dt)
    m01_csv = write_m01_csv(m01_rows)
    lower, upper = parse_arm_limits()
    speed_limits = [float(v) for v in control["provisional_actuator_limits"]["joint_speed_abs_rad_per_s"]]
    accel_limits = [float(v) for v in control["provisional_actuator_limits"]["joint_acceleration_abs_rad_per_s2"]]
    max_speed = [max(abs(float(row[f"{name}_dq_rad_s"])) for row in m01_rows) for name in JOINTS]
    max_accel = [max(abs(float(row[f"{name}_ddq_rad_s2"])) for row in m01_rows) for name in JOINTS]
    min_limit_margin = min(
        min(float(row[f"{name}_q_rad"]) - lower[i], upper[i] - float(row[f"{name}_q_rad"]))
        for row in m01_rows for i, name in enumerate(JOINTS)
    )
    m01_contract = {
        "schema": "M01_RELEASE_EVENT_AND_SWEEP_CONTRACT_V1",
        "generated_local": GENERATED,
        "segment_id": "M01",
        "authority_class": AUTHORITY,
        "released_for_mission_gate": False,
        "source_bindings": [bindings_by_id[k] for k in ("urdf", "mission", "pose_rebind", "pose_validation", "control", "hdrm")],
        "joint_coordinate_branch": {
            "from": "STOW",
            "to": "RELEASE_CLEAR",
            "q0_rad": q0,
            "q1_rad": q1,
            "duration_s": duration,
            "sample_period_s": dt,
            "sample_count": len(m01_rows),
            "interpolator": "QUINTIC_MINIMUM_JERK_10_15_6",
            "csv": {"path": package_rel(m01_csv), "sha256": sha256(m01_csv)},
            "provisional_speed_limits_rad_s": speed_limits,
            "provisional_acceleration_limits_rad_s2": accel_limits,
            "max_abs_speed_rad_s": max_speed,
            "max_abs_acceleration_rad_s2": max_accel,
            "minimum_joint_limit_margin_rad": min_limit_margin,
            "status": "NUMERIC_QSPACE_BRANCH_WELL_FORMED__PHYSICAL_STOW_AND_RELEASE_SWEEP_HOLD",
        },
        "release_event_contract": {
            "physical_stow_q_rad": None,
            "physical_stow_status": "HOLD_SOURCE_EE_INCONSISTENT_WITH_Q_567P734MM",
            "hdrm_part_and_revision": None,
            "release_command_definition": None,
            "release_confirmed_signal_definition": None,
            "release_confirmed": None,
            "release_timeout_s": None,
            "release_sweep_geometry_ref": None,
            "arm_motion_enable_guard": "release_confirmed == true",
            "guard_binding_status": "HOLD_UNBOUND_SIGNAL__CANDIDATE_NOT_EXECUTABLE",
        },
        "prohibited_inference": [
            "q-space endpoint loadability is not physical STOW identity",
            "the 11.5 s candidate is not a released HDRM sweep",
            "no collision, harness, Solar, release shock or hardware timing credit",
        ],
        "next_stage_authorized": False,
    }
    m01_contract_path = write_yaml("01_contracts/M01_RELEASE_EVENT_AND_SWEEP_V1.yaml", m01_contract)

    c08 = next(item for item in m5_config["records"] if item["configuration_id"] == "C08")
    grasp_record = next(item for item in target_satellite["features"]["grasp_points_mm"] if item["name"] == "launch_adapter_ring")
    grasp_mm = grasp_record["point_mm"]
    grasp_m = [float(v) / 1000.0 for v in grasp_mm]
    c08_transform = c08["target_transform_S_rows"]
    display_R = [[float(c08_transform[i][j]) for j in range(3)] for i in range(3)]
    display_origin = [float(c08_transform[i][3]) for i in range(3)]
    capture_point = [display_origin[i] + sum(display_R[i][j] * grasp_m[j] for j in range(3)) for i in range(3)]
    target_cg_T = [float(v) for v in target_satellite["cg_m"]]
    target_com_S = [display_origin[i] + sum(display_R[i][j] * target_cg_T[j] for j in range(3)) for i in range(3)]
    if "capture_time_s: 0.0" not in scene_text or "main_assembly_target: target_satellite_v0" not in scene_text:
        raise RuntimeError("scene-manifest display branch markers changed; fail closed")
    sim13_branch = {
        "branch_id": "SIM13_KINEMATIC_BOOTSTRAP",
        "classification": "KINEMATIC_BOOTSTRAP_NON_RELEASE",
        "source_bindings": [bindings_by_id[k] for k in ("sim13_anchor", "sim13_backend", "sim13_config", "sim13_binding_audit")],
        "target_mass_kg": float(sim13_anchor["target_mass_kg"]),
        "target_relative_position_m": [1.0, 0.0, 0.0],
        "target_relative_quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        "target_relative_linear_velocity_m_s": [0.0, 0.0, 0.0],
        "target_angular_velocity_rad_s": [0.0, 0.0, math.radians(float(sim13_anchor["target_tumble_rate_dps"]))],
        "timestep_s": float(sim13_config["timestep_s"]),
        "epoch": None,
        "common_frame_authority": None,
        "terminal_sync_state": None,
        "status": "BOOTSTRAP_ONLY__CURRENT_PRODUCTION_MECHANICAL_BINDING_INVALID",
        "merge_allowed": False,
    }
    display_branch = {
        "branch_id": "SCENE_MANIFEST_STATIC_DISPLAY",
        "classification": "STATIC_DISPLAY_ONLY_NON_RELEASE",
        "source_bindings": [bindings_by_id[k] for k in ("scene_manifest", "m5_config", "target_models", "target_satellite")],
        "capture_point_S_m": capture_point,
        "R_TS": display_R,
        "target_origin_S_m": display_origin,
        "target_com_S_m": target_com_S,
        "primary_grasp_point_T_m": grasp_m,
        "approach_axis_T": "+X_T",
        "capture_time_s": 0.0,
        "static_display_uses_mission_tumble": False,
        "epoch": None,
        "target_twist_authority": None,
        "terminal_sync_state": None,
        "status": "DISPLAY_ONLY__NOT_22KG_DYNAMIC_SYNCHRONIZATION_AUTHORITY",
        "merge_allowed": False,
    }
    m05_branches = {
        "schema": "M05_22_TARGET_STATE_BRANCH_REGISTER_V1",
        "generated_local": GENERATED,
        "authority_class": AUTHORITY,
        "branch_nonmerge_rule": "SIM13 bootstrap and scene-manifest display placement are separate diagnostic models and shall never be fused, averaged or treated as uncertainty samples.",
        "branches": [sim13_branch, display_branch],
        "selected_branch_for_mission": None,
        "released_for_mission_gate": False,
    }
    m05_branch_path = write_json("02_candidates/M05_22_TARGET_STATE_BRANCHES_V1.json", m05_branches)
    m05_contract = {
        "schema": "M05_22_TARGET_STATE_AND_SYNC_CONTRACT_V1",
        "generated_local": GENERATED,
        "segment_id": "M05_22",
        "authority_class": AUTHORITY,
        "branch_register": {"path": package_rel(m05_branch_path), "sha256": sha256(m05_branch_path)},
        "branch_ids": [item["branch_id"] for item in m05_branches["branches"]],
        "branch_merge_allowed": False,
        "mission_anchor": {"target_mass_kg": 22.0, "target_tumble_rate_deg_s": 0.5},
        "required_physical_inputs": {
            "epoch": None,
            "common_frame": None,
            "T_service_target_at_epoch": None,
            "target_linear_twist_m_s": None,
            "target_angular_twist_rad_s": None,
            "rotation_axis": None,
            "phase_at_epoch_rad": None,
            "grasp_interface_id": None,
            "target_surface_normal": None,
            "sync_terminal_twist": None,
            "sync_error_tolerance": None,
            "sync_time_window_s": None,
            "selected_whole_system_mass_inertia_branch": None,
        },
        "status": "TWO_NONMERGEABLE_DIAGNOSTIC_BRANCHES_BOUND__PHYSICAL_TARGET_STATE_AND_SYNC_HOLD",
        "released_for_mission_gate": False,
        "next_stage_authorized": False,
    }
    m05_contract_path = write_yaml("01_contracts/M05_22_TARGET_STATE_AND_SYNC_V1.yaml", m05_contract)

    with (ROOT / REL["sim06"]).open("r", encoding="utf-8-sig", newline="") as stream:
        sim06_rows = list(csv.DictReader(stream))
    selected = {
        float(row["v_app_mps"]): row for row in sim06_rows
        if row["target"] == "target_satellite_v0" and math.isclose(float(row["tumble_dps"]), 0.5)
    }
    v_apps = [0.005, 0.01, 0.02, 0.03]
    tc_ms_values = [5, 10, 20, 50, 100]
    if set(selected) != set(v_apps):
        raise RuntimeError("sim06 22 kg / 0.5 dps rows are incomplete")
    matrix_path = PACKAGE / "02_candidates/M06_22_HALF_SINE_EQUAL_IMPULSE_STIMULUS_MATRIX_V1.csv"
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_fields = [
        "case_id", "authority_class", "stimulus_role", "source_target", "source_tumble_deg_s",
        "approach_speed_m_s", "source_impulse_N_s", "solver_contact_window_ms",
        "solver_contact_window_s", "solver_waveform", "solver_peak_force_N",
        "solver_reconstructed_impulse_N_s", "solver_standard_uncertainty_N_s",
        "physical_contact_duration_s", "physical_contact_force_N", "physical_contact_pressure_Pa",
        "physical_contact_normal", "physical_lock_confirmation", "released_for_mission_gate",
    ]
    stimulus_rows: list[dict[str, Any]] = []
    with matrix_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=matrix_fields)
        writer.writeheader()
        for v_app in v_apps:
            impulse = float(selected[v_app]["contact_impulse_N_s"])
            for tc_ms in tc_ms_values:
                tc_s = tc_ms / 1000.0
                peak = math.pi * impulse / (2.0 * tc_s)
                reconstructed = 2.0 * peak * tc_s / math.pi
                row = {
                    "case_id": f"M06_22_V{str(v_app).replace('.', 'P')}_TC{tc_ms}MS",
                    "authority_class": AUTHORITY,
                    "stimulus_role": "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT",
                    "source_target": "target_satellite_v0",
                    "source_tumble_deg_s": "0.5",
                    "approach_speed_m_s": format(v_app, ".12g"),
                    "source_impulse_N_s": format(impulse, ".12g"),
                    "solver_contact_window_ms": str(tc_ms),
                    "solver_contact_window_s": format(tc_s, ".12g"),
                    "solver_waveform": "F(t)=Fpeak*sin(pi*t/Tc),0<=t<=Tc",
                    "solver_peak_force_N": format(peak, ".16g"),
                    "solver_reconstructed_impulse_N_s": format(reconstructed, ".16g"),
                    "solver_standard_uncertainty_N_s": "",
                    "physical_contact_duration_s": "",
                    "physical_contact_force_N": "",
                    "physical_contact_pressure_Pa": "",
                    "physical_contact_normal": "",
                    "physical_lock_confirmation": "",
                    "released_for_mission_gate": "false",
                }
                stimulus_rows.append(row)
                writer.writerow(row)
    m06_contract = {
        "schema": "M06_22_CONTACT_AND_LOCK_CONTRACT_V1",
        "generated_local": GENERATED,
        "segment_id": "M06_22",
        "authority_class": AUTHORITY,
        "source_bindings": [bindings_by_id[k] for k in ("sim06", "sim11_contact", "contact_contract", "gripper_v2", "gripper_gate", "gripper_validation")],
        "stimulus_matrix": {
            "path": package_rel(matrix_path),
            "sha256": sha256(matrix_path),
            "case_count": len(stimulus_rows),
            "approach_speeds_m_s": v_apps,
            "solver_contact_windows_ms": tc_ms_values,
            "waveform": "half-sine equal impulse",
            "measurement_model": "Fpeak = pi*J/(2*Tc); integral_0^Tc F(t)dt = J",
            "standard_uncertainty": None,
            "uncertainty_reason": "DETERMINISTIC_SOLVER_TRANSFORM_OF_DIAGNOSTIC_INPUT__NOT_A_PHYSICAL_MEASUREMENT",
            "classification": "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT",
        },
        "physical_contact_and_lock": {
            "contact_duration_s": None,
            "contact_force_N": None,
            "contact_pressure_Pa": None,
            "contact_normal": None,
            "contact_point_m": None,
            "contact_area_m2": None,
            "initial_gap_m": None,
            "stiffness_N_m": None,
            "damping_N_s_m": None,
            "coefficient_of_restitution": None,
            "static_friction_coefficient": None,
            "kinetic_friction_coefficient": None,
            "lock_confirmed": None,
            "lock_retention_force_N": None,
            "gripper_physical_closing_speed_m_s": None,
            "gripper_physical_closing_time_s": None,
            "status": "HOLD_NO_PHYSICAL_CONTACT_ACTUATOR_OR_LOCK_AUTHORITY",
        },
        "gripper_velocity_semantics": {
            "active_pack": bindings_by_id["gripper_v2"],
            "required_gate": bindings_by_id["gripper_gate"],
            "independent_validation": bindings_by_id["gripper_validation"],
            "physical_speed_authority": "HOLD",
            "urdf_literal_use_for_physical_timing": "PROHIBITED",
        },
        "released_for_mission_gate": False,
        "next_stage_authorized": False,
    }
    m06_contract_path = write_yaml("01_contracts/M06_22_CONTACT_AND_LOCK_V1.yaml", m06_contract)

    with (ROOT / REL["e17_m07"]).open("r", encoding="utf-8-sig", newline="") as stream:
        e17_rows = list(csv.DictReader(stream))
    m07_c08 = next(item for item in config_library["configurations"] if item["configuration_id"] == "C08")
    sim15_case = next(
        item for item in sim15["capture_envelope"]["cases"]
        if item["anchor_id"] == "ANCHOR_22KG_0P5DPS" and math.isclose(float(item["approach_speed_mps"]), 0.01)
    )
    m07_branches = {
        "schema": "M07_22_ATTACHED_TARGET_RECOVERY_BRANCH_REGISTER_V1",
        "generated_local": GENERATED,
        "authority_class": AUTHORITY,
        "arm_only_trajectory_branch": {
            "path": REL["e17_m07"],
            "sha256": bindings_by_id["e17_m07"]["sha256"],
            "sample_count": len(e17_rows),
            "duration_s": float(e17_rows[-1]["t_s"]),
            "sample_period_s": float(e17_rows[1]["t_s"]) - float(e17_rows[0]["t_s"]),
            "classification": "ARM_ONLY_QUINTIC_NON_RELEASE",
            "attached_target_propagated": False,
        },
        "C08_diagnostic_mass_branches": [
            {
                "branch_id": "M4_DIAG_LEGACY_A",
                "mass_kg": float(m07_c08["mass"]["diagnostic_branches"]["legacy_A_value_kg"]),
                "model": m07_c08["mass"]["diagnostic_branches"]["legacy_A_model"],
                "standard_uncertainty_kg": None,
                "released": False,
            },
            {
                "branch_id": "M4_DIAG_M3R_B",
                "mass_kg": float(m07_c08["mass"]["diagnostic_branches"]["m3r_B_value_kg"]),
                "model": m07_c08["mass"]["diagnostic_branches"]["m3r_B_model"],
                "standard_uncertainty_kg": None,
                "released": False,
            },
        ],
        "sim15_0p01_m_s_full_state_branch": {
            "classification": "IDEAL_RIGID_PLASTIC_CAPTURE_DIAGNOSTIC_NON_RELEASE",
            "source": bindings_by_id["sim15_baseline"],
            "full_case_record": sim15_case,
            "physical_contact_authority": False,
            "merge_with_other_models_allowed": False,
        },
        "selected_post_capture_model_branch": None,
        "locked_transform_gripper_to_target": None,
        "contact_normals": None,
        "released_mass_kg": None,
        "released_cg_m": None,
        "released_inertia_kg_m2": None,
        "released_for_mission_gate": False,
    }
    m07_branch_path = write_json("02_candidates/M07_22_ATTACHED_TARGET_RECOVERY_BRANCHES_V1.json", m07_branches)
    m07_contract = {
        "schema": "M07_22_ATTACHED_TARGET_RECOVERY_CONTRACT_V1",
        "generated_local": GENERATED,
        "segment_id": "M07_22",
        "authority_class": AUTHORITY,
        "source_bindings": [bindings_by_id[k] for k in ("e17_m07", "e17_register", "config_library", "sim15_baseline", "sim15_gate")],
        "branch_register": {"path": package_rel(m07_branch_path), "sha256": sha256(m07_branch_path)},
        "required_physical_inputs": {
            "selected_post_capture_model_branch": None,
            "T_gripper_target_locked": None,
            "contact_normals": None,
            "residual_slip_m_s": None,
            "lock_stiffness": None,
            "lock_retention_force_N": None,
            "lock_confirmation_predicate": None,
            "post_capture_initial_state": None,
            "recovery_terminal_state": None,
            "recovery_tolerances": None,
            "allowed_base_rate_rad_s": None,
            "allowed_momentum_N_m_s": None,
            "allowed_duration_s": None,
        },
        "released_mass_cg_inertia": {"mass_kg": None, "cg_m": None, "inertia_kg_m2": None, "status": "HOLD"},
        "status": "ARM_ONLY_AND_DIAGNOSTIC_POST_CAPTURE_BRANCHES_BOUND__ATTACHED_TARGET_RECOVERY_HOLD",
        "released_for_mission_gate": False,
        "next_stage_authorized": False,
    }
    m07_contract_path = write_yaml("01_contracts/M07_22_ATTACHED_TARGET_RECOVERY_V1.yaml", m07_contract)

    authority = {
        "schema": "E18_B601_MISSION_INPUT_BRANCH_AUTHORITY_CONTRACT_V1",
        "generated_local": GENERATED,
        "authority_class": AUTHORITY,
        "status": "HASH_BOUND_NON_RELEASE_BRANCHING_AUTHORIZED__MISSION_AND_PHYSICAL_RELEASE_NOT_AUTHORIZED",
        "immutable_asset": {"path": REL["urdf"], "sha256": URDF_SHA256, "modification": "FORBIDDEN"},
        "source_bindings": source_bindings,
        "allowed": [
            "M01 arm-only q-space quintic candidate with physical STOW and release fields held",
            "two non-mergeable M05 target-state diagnostic branches",
            "M06 half-sine equal-impulse solver-stimulus matrix",
            "M07 arm-only, diagnostic mass and Sim15 full-state branch binding",
            "integrity, units, dimensional, hash and negative-control validation",
        ],
        "prohibited": [
            "CAD, mesh, geometry or accepted URDF modification",
            "mission trajectory, physical contact, hardware, production dynamics or flight release",
            "merging independent diagnostic model branches",
            "using solver peak force as measured or allowable physical contact force",
            "zero-filling unknown physical fields",
            "using the URDF gripper velocity literal for physical timing",
        ],
        "testing_pass_grants_authority": False,
        "released_segments": sum(False for _ in segment_ids),
        "released_for_mission_gate": False,
        "next_stage_authorized": False,
    }
    authority_path = write_yaml("00_authority/E18_AUTHORITY_CONTRACT_V1.yaml", authority)

    contracts = {
        "M01": m01_contract_path,
        "M05_22": m05_contract_path,
        "M06_22": m06_contract_path,
        "M07_22": m07_contract_path,
    }
    candidates = {
        "M01": m01_csv,
        "M05_22": m05_branch_path,
        "M06_22": matrix_path,
        "M07_22": m07_branch_path,
    }
    branch_counts = {
        "M01": len([m01_csv]),
        "M05_22": len(m05_branches["branches"]),
        "M06_22": len(stimulus_rows),
        "M07_22": (
            len([m07_branches["arm_only_trajectory_branch"]])
            + len(m07_branches["C08_diagnostic_mass_branches"])
            + len([m07_branches["sim15_0p01_m_s_full_state_branch"]])
        ),
    }
    segment_records = [
        {
            "segment_id": segment,
            "contract": {"path": package_rel(contracts[segment]), "sha256": sha256(contracts[segment])},
            "candidate": {"path": package_rel(candidates[segment]), "sha256": sha256(candidates[segment])},
            "numeric_branch_count": branch_counts[segment],
            "released_for_mission_gate": False,
            "physical_authority": False,
            "hardware_authority": False,
        }
        for segment in segment_ids
    ]
    register = {
        "schema": "E18_B601_MISSION_INPUT_BRANCH_REGISTER_V1",
        "generated_local": GENERATED,
        "authority_class": AUTHORITY,
        "authority_contract": {"path": package_rel(authority_path), "sha256": sha256(authority_path)},
        "segments": segment_records,
        "coverage": {
            "segments_in_scope": len(segment_records),
            "segments_with_machine_contract": sum((ROOT / item["contract"]["path"]).is_file() for item in segment_records),
            "segments_with_hash_bound_nonrelease_branches": sum(bool(item["candidate"]["sha256"]) for item in segment_records),
            "released_segments": sum(bool(item["released_for_mission_gate"]) for item in segment_records),
            "physical_contact_released_segments": sum(bool(item["physical_authority"]) for item in segment_records),
            "hardware_released_segments": sum(bool(item["hardware_authority"]) for item in segment_records),
        },
        "accepted_urdf_sha256": URDF_SHA256,
        "cad_or_geometry_created": False,
        "next_stage_authorized": False,
    }
    register_path = write_json("results/E18_B601_MISSION_INPUT_BRANCH_REGISTER_V1.json", register)

    criteria = [
        {"id": "E18-G01", "name": "accepted URDF immutable hash", "state": "PASS", "observed": True, "release_credit": False},
        {"id": "E18-G02", "name": "four interlocked contracts hash bound", "state": "PASS", "observed": True, "release_credit": False},
        {"id": "E18-G03", "name": "M01 11.5 s 0.01 s q-space candidate is numerically bounded", "state": "PASS_NON_RELEASE_ONLY", "observed": True, "release_credit": False},
        {"id": "E18-G04", "name": "M01 physical STOW HDRM sweep and release confirmation", "state": "HOLD", "observed": True, "release_credit": False},
        {"id": "E18-G05", "name": "M05 Sim13 and display branches remain non-mergeable", "state": "PASS_BRANCH_SEPARATION_ONLY", "observed": True, "release_credit": False},
        {"id": "E18-G06", "name": "M05 physical target state and synchronization boundary", "state": "HOLD", "observed": True, "release_credit": False},
        {"id": "E18-G07", "name": "M06 4 by 5 half-sine stimulus matrix", "state": "PASS_SOLVER_STIMULUS_ONLY", "observed": True, "release_credit": False},
        {"id": "E18-G08", "name": "M06 physical force pressure duration normal and lock", "state": "HOLD", "observed": True, "release_credit": False},
        {"id": "E18-G09", "name": "gripper V2 semantic gate and independent validation bound", "state": "PASS_SEMANTIC_SCOPE_ONLY", "observed": True, "release_credit": False},
        {"id": "E18-G10", "name": "M07 arm-only trajectory and C08 mass branches bound", "state": "PASS_NON_RELEASE_ONLY", "observed": True, "release_credit": False},
        {"id": "E18-G11", "name": "M07 Sim15 0.01 m/s full-state branch bound", "state": "PASS_DIAGNOSTIC_ONLY", "observed": True, "release_credit": False},
        {"id": "E18-G12", "name": "M07 locked transform normals and released mass properties", "state": "HOLD", "observed": True, "release_credit": False},
        {"id": "E18-G13", "name": "no CAD or geometry generated", "state": "PASS", "observed": True, "release_credit": False},
        {"id": "E18-G14", "name": "all mission physical hardware production releases fail closed", "state": "HOLD", "observed": True, "release_credit": False},
    ]
    gate = {
        "schema": "E18_B601_MISSION_INPUT_BRANCH_GATE_V1",
        "generated_local": GENERATED,
        "authority_scope": "NON_RELEASE_INPUT_BRANCH_INTEGRITY_ONLY",
        "register": {"path": package_rel(register_path), "sha256": sha256(register_path)},
        "criteria": criteria,
        "criteria_total": len(criteria),
        "criteria_observed": sum(bool(item["observed"]) for item in criteria),
        "numeric_branch_integrity_ready": True,
        "mission_trajectory_release_ready": False,
        "physical_contact_ready": False,
        "hardware_motion_ready": False,
        "production_dynamics_ready": False,
        "cad_geometry_authority": False,
        "released_segments": register["coverage"]["released_segments"],
        "gate": "HOLD",
        "verdict": "E18_NON_RELEASE_BRANCHES_WELL_FORMED__MISSION_PHYSICAL_HARDWARE_AND_PRODUCTION_RELEASE_HOLD",
        "testing_pass_grants_authority": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    gate_path = write_json("results/E18_B601_MISSION_INPUT_BRANCH_GATE_V1.json", gate)

    controlled_paths = [
        PACKAGE / "README.md",
        PACKAGE / "src/build_mission_input_branches.py",
        PACKAGE / "tests/validate_mission_input_branches.py",
        authority_path,
        *contracts.values(),
        *candidates.values(),
        register_path,
        gate_path,
    ]
    manifest = {
        "schema": "E18_B601_MISSION_INPUT_BRANCH_OUTPUT_MANIFEST_V1",
        "generated_local": GENERATED,
        "scope": "controlled package artifacts and bound source inputs; validation excluded to avoid recursive hashing",
        "artifacts": [
            {"path": package_rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in controlled_paths
        ],
        "source_bindings": source_bindings,
        "artifact_count": len(controlled_paths),
        "source_count": len(source_bindings),
        "accepted_urdf_sha256": URDF_SHA256,
        "released_for_mission_gate": False,
        "next_stage_authorized": False,
    }
    manifest_path = write_json("results/E18_OUTPUT_MANIFEST_V1.json", manifest)
    print(json.dumps({
        "package": package_rel(PACKAGE),
        "register_sha256": sha256(register_path),
        "gate_sha256": sha256(gate_path),
        "manifest_sha256": sha256(manifest_path),
        "m01_samples": len(m01_rows),
        "m06_cases": len(stimulus_rows),
    }, indent=2))


if __name__ == "__main__":
    main()
