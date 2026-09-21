from __future__ import annotations

import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parent.parent
WORKSPACE = PACKAGE.parents[1]
AUTHORITY = PACKAGE / "00_authority/E17_AUTHORITY_CONTRACT_V1.yaml"
CONFIG = PACKAGE / "config/trajectory_seed_v1.yaml"
RESULTS = PACKAGE / "results"
CANDIDATES = RESULTS / "candidates"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def canonical_hash(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest().upper()


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def quintic(q0: list[float], q1: list[float], t: float, duration: float):
    s = t / duration
    blend = 10.0 * s**3 - 15.0 * s**4 + 6.0 * s**5
    dblend_dt = (30.0 * s**2 - 60.0 * s**3 + 30.0 * s**4) / duration
    d2blend_dt2 = (60.0 * s - 180.0 * s**2 + 120.0 * s**3) / duration**2
    delta = [b - a for a, b in zip(q0, q1)]
    q = [a + d * blend for a, d in zip(q0, delta)]
    dq = [d * dblend_dt for d in delta]
    ddq = [d * d2blend_dt2 for d in delta]
    return q, dq, ddq


def parse_urdf(path: Path, joint_order: list[str]):
    root = ET.parse(path).getroot()
    by_name = {joint.get("name"): joint for joint in root.findall("joint")}
    revolute = []
    for name in joint_order:
        joint = by_name[name]
        limit = joint.find("limit")
        axis = joint.find("axis")
        origin = joint.find("origin")
        revolute.append(
            {
                "name": name,
                "type": joint.get("type"),
                "parent": joint.find("parent").get("link"),
                "child": joint.find("child").get("link"),
                "origin_xyz_m": [float(x) for x in origin.get("xyz").split()],
                "origin_rpy_rad": [float(x) for x in origin.get("rpy").split()],
                "axis_in_joint_frame": [float(x) for x in axis.get("xyz").split()],
                "lower_rad": float(limit.get("lower")),
                "upper_rad": float(limit.get("upper")),
                "urdf_velocity_limit_rad_s": float(limit.get("velocity")),
                "urdf_effort_limit_Nm": float(limit.get("effort")),
            }
        )
    gripper = []
    for name in ("gripper_joint1", "gripper_joint2"):
        joint = by_name[name]
        limit = joint.find("limit")
        gripper.append(
            {
                "name": name,
                "type": joint.get("type"),
                "lower_m": float(limit.get("lower")),
                "upper_m": float(limit.get("upper")),
                "urdf_velocity_limit_m_s": float(limit.get("velocity")),
                "urdf_effort_limit_N": float(limit.get("effort")),
            }
        )
    return revolute, gripper


def duration_lower_bound(delta, vmax, amax):
    speed_terms = [1.875 * abs(d) / v for d, v in zip(delta, vmax)]
    accel_terms = [math.sqrt(5.7735026919 * abs(d) / a) for d, a in zip(delta, amax)]
    return max(speed_terms + accel_terms), speed_terms, accel_terms


def sample_times(duration: float, dt: float):
    intervals = round(duration / dt)
    if not math.isclose(intervals * dt, duration, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"duration {duration} is not an integer multiple of dt {dt}")
    return [i * dt for i in range(intervals + 1)]


def main() -> None:
    authority = load_yaml(AUTHORITY)
    config = load_yaml(CONFIG)
    generated_local = authority["generated_local"]

    source_receipts = []
    for binding in authority["source_bindings"]:
        path = WORKSPACE / binding["path"]
        actual = sha256(path)
        if actual != binding["sha256"]:
            raise RuntimeError(
                f"source hash mismatch: {binding['path']} expected={binding['sha256']} actual={actual}"
            )
        source_receipts.append(
            {
                "path": binding["path"],
                "expected_sha256": binding["sha256"],
                "actual_sha256": actual,
                "hash_match": True,
                "bytes": path.stat().st_size,
            }
        )

    paths = {Path(item["path"]).name: WORKSPACE / item["path"] for item in authority["source_bindings"]}
    urdf_path = paths["arm_b601_v1.urdf"]
    mission_path = paths["B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml"]
    pose_rebind_path = paths["B601_MISSION_POSE_AUTHORITY_REBIND_V1.yaml"]
    pose_revalidation_path = paths["B601_NAMED_POSE_REVALIDATION_V1.json"]
    control_path = paths["control_01_v0.yaml"]
    gripper_path = paths["GRIPPER_ENGINEERING_PACK_V1.yaml"]
    config_library_path = paths["CONFIGURATION_LIBRARY_V1.yaml"]

    mission = load_yaml(mission_path)
    pose_rebind = load_yaml(pose_rebind_path)
    pose_revalidation = json.loads(pose_revalidation_path.read_text(encoding="utf-8"))
    control = load_yaml(control_path)
    gripper_pack = load_yaml(gripper_path)
    configuration_library = load_yaml(config_library_path)

    joint_order = authority["joint_coordinate_contract"]["order"]
    if mission["joint_order"] != joint_order:
        raise RuntimeError("mission joint order differs from authority contract")
    revolute, gripper_joints = parse_urdf(urdf_path, joint_order)
    if any(joint["type"] != "revolute" for joint in revolute):
        raise RuntimeError("expected six revolute arm joints")
    if any(joint["type"] != "prismatic" for joint in gripper_joints):
        raise RuntimeError("expected two prismatic gripper joints")

    states = {name: [float(x) for x in value["q_rad"]] for name, value in mission["states"].items()}
    if not pose_rebind.get("all_named_q_vectors_loadable"):
        raise RuntimeError("pose rebind does not establish current-URDF q-vector loadability")
    segment_contract = {item["id"]: item for item in mission["segments"]}
    if len(segment_contract) != 8 or any(item["released_for_mission_gate"] for item in segment_contract.values()):
        raise RuntimeError("expected eight non-released mission segments")

    provisional = control["provisional_actuator_limits"]
    vmax = [float(x) for x in provisional["joint_speed_abs_rad_per_s"]]
    amax = [float(x) for x in provisional["joint_acceleration_abs_rad_per_s2"]]
    if provisional["status"] != "PROVISIONAL_CLASS_VALUES":
        raise RuntimeError("control limits lost provisional classification")
    dt = float(config["sample_period"]["value"])

    stow_result = pose_revalidation["pose_results"]["Q_STOW_ENGINEERING_CANDIDATE"]
    stow_residual_mm = float(stow_result["max_abs_position_residual_mm"])
    if stow_result["fk_regression_pass"] or stow_residual_mm <= float(stow_result["position_tolerance_mm"]):
        raise RuntimeError("M01 blocker expected a held STOW FK source mismatch")

    gripper_pack_velocity_mm_s = float(gripper_pack["frozen_inputs"]["urdf_velocity_limit_mm_s"])
    urdf_gripper_velocity_m_s = float(gripper_joints[0]["urdf_velocity_limit_m_s"])
    gripper_unit_conflict = not math.isclose(
        urdf_gripper_velocity_m_s,
        gripper_pack_velocity_mm_s / 1000.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    if not gripper_unit_conflict:
        raise RuntimeError("expected gripper velocity-unit conflict was not present")

    RESULTS.mkdir(parents=True, exist_ok=True)
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    input_manifest_path = RESULTS / "E17_INPUT_MANIFEST_V1.json"
    input_manifest = {
        "schema": "E17_INPUT_MANIFEST_V1",
        "generated_local": generated_local,
        "authority_class": authority["authority_class"],
        "inputs": source_receipts
        + [
            {"path": rel(AUTHORITY), "actual_sha256": sha256(AUTHORITY), "hash_match": True, "bytes": AUTHORITY.stat().st_size},
            {"path": rel(CONFIG), "actual_sha256": sha256(CONFIG), "hash_match": True, "bytes": CONFIG.stat().st_size},
        ],
        "input_count": len(source_receipts) + 2,
        "accepted_urdf_unchanged": True,
    }
    write_json(input_manifest_path, input_manifest)

    release_gates = {
        "full_path_ik": "UNKNOWN_NOT_EVALUATED",
        "collision": "UNKNOWN_NOT_EVALUATED_CURRENT_R2_GEOMETRY",
        "solar_keep_out": "UNKNOWN_NOT_EVALUATED",
        "route_c_harness": "HOLD_ROUTE_C_GEOMETRY_NOT_AUTHORIZED_OR_MODELED",
        "safe00": "UNKNOWN_NO_E17_SEGMENT_POLICY_BINDING",
        "physical_contact": "HOLD_NOT_MODELED",
        "whole_system_frame": "HOLD_ODR01_DYNAMICS_AND_M7_CAD_FRAME_RECONCILIATION_ABSENT",
    }

    numeric_ids = ["M02", "M03", "M04", "M05_150", "M07_22"]
    candidate_records = []
    candidate_paths = []
    for segment_id in numeric_ids:
        spec = config["segments"][segment_id]
        contract = segment_contract[segment_id]
        if spec["from"] != contract["from"] or spec["to"] != contract["to"]:
            raise RuntimeError(f"endpoint name mismatch for {segment_id}")
        q0 = states[spec["from"]]
        q1 = states[spec["to"]]
        duration = float(spec["duration"]["value"])
        delta = [b - a for a, b in zip(q0, q1)]
        required, speed_terms, accel_terms = duration_lower_bound(delta, vmax, amax)
        if duration + 1e-12 < required:
            raise RuntimeError(f"provisional duration too short for {segment_id}")

        csv_path = CANDIDATES / f"{segment_id}_ARM_ONLY_QUINTIC_V1.csv"
        fields = ["sample_index", "t_s"]
        fields += [f"{joint}_q_rad" for joint in joint_order]
        fields += [f"{joint}_dq_rad_s" for joint in joint_order]
        fields += [f"{joint}_ddq_rad_s2" for joint in joint_order]
        fields += ["gripper_state", "jaw_travel_m", "authority_class", "released_for_mission_gate"]
        max_dq = [0.0] * 6
        max_ddq = [0.0] * 6
        min_limit_margin = math.inf
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for index, t in enumerate(sample_times(duration, dt)):
                q, dq, ddq = quintic(q0, q1, t, duration)
                for j in range(6):
                    max_dq[j] = max(max_dq[j], abs(dq[j]))
                    max_ddq[j] = max(max_ddq[j], abs(ddq[j]))
                    min_limit_margin = min(
                        min_limit_margin,
                        q[j] - revolute[j]["lower_rad"],
                        revolute[j]["upper_rad"] - q[j],
                    )
                row = {
                    "sample_index": index,
                    "t_s": f"{t:.12f}",
                    "gripper_state": spec["gripper_state"],
                    "jaw_travel_m": "",
                    "authority_class": authority["authority_class"],
                    "released_for_mission_gate": "false",
                }
                row.update({f"{joint}_q_rad": f"{q[j]:.15g}" for j, joint in enumerate(joint_order)})
                row.update({f"{joint}_dq_rad_s": f"{dq[j]:.15g}" for j, joint in enumerate(joint_order)})
                row.update({f"{joint}_ddq_rad_s2": f"{ddq[j]:.15g}" for j, joint in enumerate(joint_order)})
                writer.writerow(row)

        record = {
            "segment_id": segment_id,
            "purpose": contract["purpose"],
            "from": spec["from"],
            "to": spec["to"],
            "authority_class": authority["authority_class"],
            "numeric_status": "NUMERIC_SEED_WELL_FORMED_ONLY",
            "mission_status": "UNKNOWN",
            "released_for_mission_gate": False,
            "next_stage_authorized": False,
            "candidate_file": {"path": rel(csv_path), "sha256": sha256(csv_path), "bytes": csv_path.stat().st_size},
            "sample_count": len(sample_times(duration, dt)),
            "sample_period_s": dt,
            "duration_s": duration,
            "duration_authority": spec["duration"]["classification"],
            "duration_required_lower_bound_s": required,
            "duration_margin_s": duration - required,
            "speed_term_by_joint_s": speed_terms,
            "acceleration_term_by_joint_s": accel_terms,
            "q0_rad": q0,
            "q1_rad": q1,
            "q0_sha256": canonical_hash(q0),
            "q1_sha256": canonical_hash(q1),
            "max_abs_dq_rad_s": max_dq,
            "max_abs_ddq_rad_s2": max_ddq,
            "provisional_speed_limits_rad_s": vmax,
            "provisional_acceleration_limits_rad_s2": amax,
            "minimum_joint_limit_margin_rad": min_limit_margin,
            "gripper_state": spec["gripper_state"],
            "jaw_travel_m": None,
            "release_gates": dict(release_gates),
            "limitation": spec.get("limitation"),
            "semantic_guard": spec.get("semantic_guard"),
        }
        candidate_records.append(record)
        candidate_paths.append(csv_path)

    m06_spec = config["segments"]["M06_22"]
    m06_path = CANDIDATES / "M06_22_SYMBOLIC_ARM_HOLD_V1.json"
    m06 = {
        "schema": "E17_M06_22_SYMBOLIC_ARM_HOLD_V1",
        "generated_local": generated_local,
        "segment_id": "M06_22",
        "purpose": segment_contract["M06_22"]["purpose"],
        "authority_class": authority["authority_class"],
        "numeric_status": "SYMBOLIC_SCAFFOLD_ONLY",
        "mission_status": "HOLD_CONTACT_AUTHORITY_ABSENT",
        "released_for_mission_gate": False,
        "next_stage_authorized": False,
        "physical_duration_s": None,
        "q_rad": states["PREGRASP"],
        "dq_rad_s": [0.0] * 6,
        "ddq_rad_s2": [0.0] * 6,
        "symbolic_gripper_sequence": m06_spec["symbolic_gripper_sequence"],
        "jaw_travel_m": None,
        "contact_time_s": None,
        "contact_force_N": None,
        "contact_normal": None,
        "lock_confirmation": None,
        "release_gates": dict(release_gates),
        "note": "q-hold is not a capture model; physical contact, closure and locking remain null/HOLD.",
    }
    write_json(m06_path, m06)

    config_names = {item.get("configuration_id") for item in configuration_library.get("configurations", [])}
    register_path = RESULTS / "B601_MISSION_TRAJECTORY_CANDIDATE_REGISTER_V1.json"
    register = {
        "schema": "B601_MISSION_TRAJECTORY_CANDIDATE_REGISTER_V1",
        "generated_local": generated_local,
        "authority_class": authority["authority_class"],
        "released_for_mission_gate": False,
        "next_stage_authorized": False,
        "joint_coordinate_ledger": {
            "order": joint_order,
            "q_unit": "rad",
            "dq_unit": "rad/s",
            "ddq_unit": "rad/s^2",
            "root_frame": "accepted_urdf/base_link",
            "joints": revolute,
            "positive_motion_rule": "axis is expressed in each joint frame exactly as the accepted URDF; no world-frame reinterpretation",
            "whole_system_transform_authority": authority["joint_coordinate_contract"]["whole_system_transform_authority"],
        },
        "gripper_unit_audit": {
            "urdf_prismatic_velocity_value": urdf_gripper_velocity_m_s,
            "urdf_prismatic_velocity_unit": "m/s",
            "engineering_pack_velocity_value": gripper_pack_velocity_mm_s,
            "engineering_pack_velocity_unit": "mm/s",
            "values_equal_only_if_units_are_stripped": math.isclose(urdf_gripper_velocity_m_s, gripper_pack_velocity_mm_s),
            "physical_values_equal_after_unit_conversion": math.isclose(urdf_gripper_velocity_m_s, gripper_pack_velocity_mm_s / 1000.0),
            "state": "UNIT_CONFLICT_HOLD__NO_PHYSICAL_GRIPPER_TIMING_AUTHORIZED",
        },
        "source_defects_retained": {
            "stow_max_abs_position_residual_mm": stow_residual_mm,
            "stow_position_tolerance_mm": float(stow_result["position_tolerance_mm"]),
            "stow_fk_regression_pass": bool(stow_result["fk_regression_pass"]),
            "pregrasp_classification": "PROVISIONAL_150KG_DEBRIS_GEOMETRY_SELECTION_NOT_22KG_DYNAMICS_VALIDATION",
            "configuration_library_contains_C07": "C07" in config_names,
            "configuration_library_contains_C08": "C08" in config_names,
        },
        "numeric_candidates": candidate_records,
        "symbolic_scaffolds": [
            {
                "segment_id": "M06_22",
                "path": rel(m06_path),
                "sha256": sha256(m06_path),
                "status": "SYMBOLIC_ARM_HOLD_ONLY__CONTACT_VALUES_NULL",
                "released_for_mission_gate": False,
            }
        ],
        "blocked_uninstantiated_segments": [
            {
                "segment_id": "M01",
                "status": "HOLD_STOW_FK_SOURCE_MISMATCH_AND_HDRM_RELEASE_SWEEP_AUTHORITY_ABSENT",
                "numeric_candidate_created": False,
                "released_for_mission_gate": False,
            },
            {
                "segment_id": "M05_22",
                "status": "ZERO_PATH_CANNOT_SYNCHRONIZE__TARGET_RELATIVE_STATE_AND_TRACKING_BOUNDARIES_ABSENT",
                "numeric_candidate_created": False,
                "released_for_mission_gate": False,
                "required_missing_inputs": ["22kg target relative pose", "grasp point", "rotation axis", "phase", "target twist", "generalized Jacobian binding", "nonzero terminal tracking boundary"],
            },
        ],
        "coverage": {
            "mission_segments_total": 8,
            "numeric_arm_only_seed_segments": 5,
            "symbolic_scaffold_segments": 1,
            "blocked_uninstantiated_segments": 2,
            "released_segments": 0,
        },
        "input_manifest": {"path": rel(input_manifest_path), "sha256": sha256(input_manifest_path)},
        "claim_limit": "Numerical seeds are deterministic joint-coordinate scaffolds only; no full-path or physical mission predicate is released.",
    }
    write_json(register_path, register)

    gate_path = RESULTS / "B601_MISSION_TRAJECTORY_CANDIDATE_GATE_V1.json"
    gate = {
        "schema": "B601_MISSION_TRAJECTORY_CANDIDATE_GATE_V1",
        "generated_local": generated_local,
        "gate": "HOLD",
        "verdict": "E17_NUMERIC_SEEDS_WELL_FORMED_ONLY__MISSION_TRAJECTORY_RELEASE_REMAINS_HOLD",
        "authority_class": authority["authority_class"],
        "next_stage_authorized": False,
        "numeric_seed_integrity": "NUMERIC_SEED_WELL_FORMED_ONLY",
        "mission_trajectory_release": "HOLD_0_OF_8",
        "criteria": [
            {"id": "E17-G01", "name": "accepted URDF and source hashes", "state": "NUMERIC_INTEGRITY_OK", "release_credit": False},
            {"id": "E17-G02", "name": "five legal arm-only numeric seeds", "state": "NUMERIC_INTEGRITY_OK", "release_credit": False},
            {"id": "E17-G03", "name": "M01 release path", "state": "HOLD", "release_credit": False},
            {"id": "E17-G04", "name": "M05_22 synchronization", "state": "HOLD", "release_credit": False},
            {"id": "E17-G05", "name": "M06_22 physical contact and locking", "state": "HOLD", "release_credit": False},
            {"id": "E17-G06", "name": "M07_22 attached-target recovery", "state": "HOLD", "release_credit": False},
            {"id": "E17-G07", "name": "full-path collision and Solar keep-out", "state": "UNKNOWN", "release_credit": False},
            {"id": "E17-G08", "name": "Route-C harness coupled predicate", "state": "HOLD", "release_credit": False},
            {"id": "E17-G09", "name": "SAFE-00 per-segment policy binding", "state": "UNKNOWN", "release_credit": False},
            {"id": "E17-G10", "name": "gripper velocity-unit consistency", "state": "HOLD_UNIT_CONFLICT", "release_credit": False},
        ],
        "counts": register["coverage"],
        "released_for_mission_gate": False,
        "allowed_next": ["independent numeric validation", "M01 authority acquisition", "22kg target-state/interface definition", "Route-C harness design after its own entry gate"],
        "prohibited_next": ["production dynamics", "physical-contact RL", "hardware motion", "mission trajectory release", "physical gripper timing"],
        "register": {"path": rel(register_path), "sha256": sha256(register_path)},
        "immutable_asset_hash": sha256(urdf_path),
    }
    write_json(gate_path, gate)

    output_manifest_path = RESULTS / "E17_OUTPUT_MANIFEST_V1.json"
    outputs = candidate_paths + [m06_path, input_manifest_path, register_path, gate_path]
    output_manifest = {
        "schema": "E17_OUTPUT_MANIFEST_V1",
        "generated_local": generated_local,
        "scope": "non-release arm-only numerical seeds and fail-closed mission scaffolds",
        "outputs": [{"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in outputs],
        "sources": source_receipts
        + [
            {"path": rel(AUTHORITY), "actual_sha256": sha256(AUTHORITY), "hash_match": True, "bytes": AUTHORITY.stat().st_size},
            {"path": rel(CONFIG), "actual_sha256": sha256(CONFIG), "hash_match": True, "bytes": CONFIG.stat().st_size},
        ],
        "generator": {"path": rel(SCRIPT), "sha256": sha256(SCRIPT), "bytes": SCRIPT.stat().st_size},
        "output_count": len(outputs),
        "source_count": len(source_receipts) + 2,
        "geometry_artifact_count": 0,
        "released_segments": 0,
        "next_stage_authorized": False,
        "validation_report_excluded_to_avoid_recursive_hash": True,
    }
    write_json(output_manifest_path, output_manifest)

    print(
        json.dumps(
            {
                "verdict": gate["verdict"],
                "numeric_candidates": len(candidate_records),
                "symbolic_scaffolds": 1,
                "blocked_uninstantiated": 2,
                "released_segments": 0,
                "input_manifest_sha256": sha256(input_manifest_path),
                "register_sha256": sha256(register_path),
                "gate_sha256": sha256(gate_path),
                "output_manifest_sha256": sha256(output_manifest_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
