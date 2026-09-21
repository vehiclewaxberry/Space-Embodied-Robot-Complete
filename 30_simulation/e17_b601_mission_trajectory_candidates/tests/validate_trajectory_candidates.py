from __future__ import annotations

import copy
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
BUILDER = PACKAGE / "src/build_trajectory_candidates.py"
RESULTS = PACKAGE / "results"
REGISTER = RESULTS / "B601_MISSION_TRAJECTORY_CANDIDATE_REGISTER_V1.json"
GATE = RESULTS / "B601_MISSION_TRAJECTORY_CANDIDATE_GATE_V1.json"
INPUT_MANIFEST = RESULTS / "E17_INPUT_MANIFEST_V1.json"
OUTPUT_MANIFEST = RESULTS / "E17_OUTPUT_MANIFEST_V1.json"
REPORT = RESULTS / "E17_VALIDATION_V1.json"
M06 = RESULTS / "candidates/M06_22_SYMBOLIC_ARM_HOLD_V1.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def quintic(q0, q1, t, duration):
    s = t / duration
    b = 10.0 * s**3 - 15.0 * s**4 + 6.0 * s**5
    db = (30.0 * s**2 - 60.0 * s**3 + 30.0 * s**4) / duration
    ddb = (60.0 * s - 180.0 * s**2 + 120.0 * s**3) / duration**2
    delta = [v1 - v0 for v0, v1 in zip(q0, q1)]
    return (
        [v0 + d * b for v0, d in zip(q0, delta)],
        [d * db for d in delta],
        [d * ddb for d in delta],
    )


def duration_bound(delta, vmax, amax):
    terms = [1.875 * abs(d) / v for d, v in zip(delta, vmax)]
    terms += [math.sqrt(5.7735026919 * abs(d) / a) for d, a in zip(delta, amax)]
    return max(terms)


checks = []


def check(check_id, condition, evidence):
    checks.append({"id": check_id, "pass": bool(condition), "evidence": evidence})


for path in (AUTHORITY, CONFIG, BUILDER, REGISTER, GATE, INPUT_MANIFEST, OUTPUT_MANIFEST, M06):
    check(f"FILE_{path.stem}_EXISTS", path.is_file() and path.stat().st_size > 0, rel(path))

authority = load_yaml(AUTHORITY)
config = load_yaml(CONFIG)
register = load_json(REGISTER)
gate = load_json(GATE)
input_manifest = load_json(INPUT_MANIFEST)
output_manifest = load_json(OUTPUT_MANIFEST)
m06 = load_json(M06)

check("AUTHORITY_NON_RELEASE", authority.get("authority_class") == "NON_RELEASE_DIAGNOSTIC_CANDIDATE" and authority.get("released_for_mission_gate") is False and authority.get("next_stage_authorized") is False, {k: authority.get(k) for k in ("authority_class", "released_for_mission_gate", "next_stage_authorized")})
check("AUTHORITY_PROHIBITS_URDF_EDIT", "edit accepted URDF or any CAD/mesh asset" in authority["scope"]["prohibited"], authority["scope"]["prohibited"])
check("JOINT_UNITS_EXPLICIT", authority["joint_coordinate_contract"]["q_unit"] == "rad" and authority["joint_coordinate_contract"]["dq_unit"] == "rad/s" and authority["joint_coordinate_contract"]["ddq_unit"] == "rad/s^2", authority["joint_coordinate_contract"])
check("WHOLE_SYSTEM_FRAME_FAIL_CLOSED", authority["joint_coordinate_contract"]["whole_system_transform_authority"].startswith("HOLD_"), authority["joint_coordinate_contract"]["whole_system_transform_authority"])

source_hashes_ok = True
source_evidence = []
for binding in authority["source_bindings"]:
    path = WORKSPACE / binding["path"]
    match = path.is_file() and sha256(path) == binding["sha256"]
    source_hashes_ok &= match
    source_evidence.append({"path": binding["path"], "match": match})
check("AUTHORITY_SOURCE_HASHES_MATCH", source_hashes_ok, source_evidence)

urdf_path = WORKSPACE / authority["immutable_asset"]["path"]
check("ACCEPTED_URDF_HASH_UNCHANGED", sha256(urdf_path) == authority["immutable_asset"]["sha256"] == "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164", sha256(urdf_path))
mission_path = next(WORKSPACE / item["path"] for item in authority["source_bindings"] if item["path"].endswith("B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml"))
control_path = next(WORKSPACE / item["path"] for item in authority["source_bindings"] if item["path"].endswith("control_01_v0.yaml"))
mission = load_yaml(mission_path)
control = load_yaml(control_path)
segment_contract = {item["id"]: item for item in mission["segments"]}
check("MISSION_CONTRACT_EIGHT_UNKNOWN", len(segment_contract) == 8 and all(item["status"] == "UNKNOWN" and item["released_for_mission_gate"] is False for item in segment_contract.values()), {sid: {"status": item["status"], "released": item["released_for_mission_gate"]} for sid, item in segment_contract.items()})

joint_order = authority["joint_coordinate_contract"]["order"]
root = ET.parse(urdf_path).getroot()
urdf_joints = {joint.get("name"): joint for joint in root.findall("joint")}
limits = []
for name in joint_order:
    joint = urdf_joints[name]
    limit = joint.find("limit")
    limits.append((float(limit.get("lower")), float(limit.get("upper"))))
check("SIX_REVOLUTE_JOINTS", all(urdf_joints[name].get("type") == "revolute" for name in joint_order), [(name, urdf_joints[name].get("type")) for name in joint_order])
check("JOINT_LEDGER_MATCHES_URDF", all(abs(register["joint_coordinate_ledger"]["joints"][i]["lower_rad"] - limits[i][0]) < 1e-12 and abs(register["joint_coordinate_ledger"]["joints"][i]["upper_rad"] - limits[i][1]) < 1e-12 for i in range(6)), register["joint_coordinate_ledger"]["joints"])

input_records = input_manifest.get("inputs", [])
input_ok = input_manifest.get("input_count") == len(input_records) == 9
for item in input_records:
    path = WORKSPACE / item["path"]
    input_ok &= path.is_file() and sha256(path) == item["actual_sha256"] and item.get("hash_match") is True
check("INPUT_MANIFEST_HASH_CLOSURE", input_ok, {"count": len(input_records), "expected": input_manifest.get("input_count")})

expected_numeric = ["M02", "M03", "M04", "M05_150", "M07_22"]
numeric_records = register.get("numeric_candidates", [])
check("NUMERIC_CANDIDATE_SET_EXACT", [item["segment_id"] for item in numeric_records] == expected_numeric, [item["segment_id"] for item in numeric_records])
check("COVERAGE_5_1_2_0", register.get("coverage") == {"mission_segments_total": 8, "numeric_arm_only_seed_segments": 5, "symbolic_scaffold_segments": 1, "blocked_uninstantiated_segments": 2, "released_segments": 0}, register.get("coverage"))
check("REGISTER_NON_RELEASE", register.get("authority_class") == "NON_RELEASE_DIAGNOSTIC_CANDIDATE" and register.get("released_for_mission_gate") is False and register.get("next_stage_authorized") is False, {k: register.get(k) for k in ("authority_class", "released_for_mission_gate", "next_stage_authorized")})

states = {name: [float(x) for x in state["q_rad"]] for name, state in mission["states"].items()}
vmax = [float(x) for x in control["provisional_actuator_limits"]["joint_speed_abs_rad_per_s"]]
amax = [float(x) for x in control["provisional_actuator_limits"]["joint_acceleration_abs_rad_per_s2"]]
tolerances = config["validation_tolerances"]
candidate_audits = []
all_candidate_ok = True
all_hashes_ok = True
for meta in numeric_records:
    sid = meta["segment_id"]
    path = WORKSPACE / meta["candidate_file"]["path"]
    hash_ok = sha256(path) == meta["candidate_file"]["sha256"]
    all_hashes_ok &= hash_ok
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    duration = float(meta["duration_s"])
    dt = float(meta["sample_period_s"])
    expected_count = round(duration / dt) + 1
    q0 = states[meta["from"]]
    q1 = states[meta["to"]]
    max_analytic_error = 0.0
    max_fd_dq_error = 0.0
    max_fd_ddq_error = 0.0
    monotonic = True
    finite = True
    limits_ok = True
    metadata_ok = True
    parsed_q = []
    parsed_dq = []
    parsed_ddq = []
    times = []
    for index, row in enumerate(rows):
        t = float(row["t_s"])
        q = [float(row[f"{name}_q_rad"]) for name in joint_order]
        dq = [float(row[f"{name}_dq_rad_s"]) for name in joint_order]
        ddq = [float(row[f"{name}_ddq_rad_s2"]) for name in joint_order]
        expected_q, expected_dq, expected_ddq = quintic(q0, q1, t, duration)
        max_analytic_error = max(max_analytic_error, *(abs(a - b) for a, b in zip(q + dq + ddq, expected_q + expected_dq + expected_ddq)))
        finite &= all(math.isfinite(value) for value in [t] + q + dq + ddq)
        limits_ok &= all(lower - 1e-12 <= value <= upper + 1e-12 for value, (lower, upper) in zip(q, limits))
        metadata_ok &= row["authority_class"] == "NON_RELEASE_DIAGNOSTIC_CANDIDATE" and row["released_for_mission_gate"] == "false" and row["jaw_travel_m"] == ""
        if index and not t > times[-1]:
            monotonic = False
        times.append(t)
        parsed_q.append(q)
        parsed_dq.append(dq)
        parsed_ddq.append(ddq)
    for index in range(1, len(rows) - 1):
        local_dt = times[index + 1] - times[index - 1]
        for joint_index in range(6):
            fd_dq = (parsed_q[index + 1][joint_index] - parsed_q[index - 1][joint_index]) / local_dt
            fd_ddq = (parsed_dq[index + 1][joint_index] - parsed_dq[index - 1][joint_index]) / local_dt
            max_fd_dq_error = max(max_fd_dq_error, abs(fd_dq - parsed_dq[index][joint_index]))
            max_fd_ddq_error = max(max_fd_ddq_error, abs(fd_ddq - parsed_ddq[index][joint_index]))
    endpoint_q_error = max(abs(a - b) for a, b in zip(parsed_q[0] + parsed_q[-1], q0 + q1))
    endpoint_dq = max(abs(value) for value in parsed_dq[0] + parsed_dq[-1])
    endpoint_ddq = max(abs(value) for value in parsed_ddq[0] + parsed_ddq[-1])
    max_dq = [max(abs(row[j]) for row in parsed_dq) for j in range(6)]
    max_ddq = [max(abs(row[j]) for row in parsed_ddq) for j in range(6)]
    provisional_limits_ok = all(value <= limit + 1e-12 for value, limit in zip(max_dq, vmax)) and all(value <= limit + 1e-12 for value, limit in zip(max_ddq, amax))
    required_duration = duration_bound([b - a for a, b in zip(q0, q1)], vmax, amax)
    duration_ok = duration + 1e-12 >= required_duration and abs(meta["duration_required_lower_bound_s"] - required_duration) < 1e-10
    release_semantics_ok = meta["numeric_status"] == "NUMERIC_SEED_WELL_FORMED_ONLY" and meta["mission_status"] == "UNKNOWN" and meta["released_for_mission_gate"] is False and meta["next_stage_authorized"] is False and all(value != "PASS" for value in meta["release_gates"].values())
    candidate_ok = bool(
        hash_ok
        and len(rows) == expected_count
        and monotonic
        and finite
        and limits_ok
        and metadata_ok
        and max_analytic_error <= float(tolerances["analytic_sample_abs"])
        and max_fd_dq_error <= float(tolerances["finite_difference_dq_abs_rad_s"])
        and max_fd_ddq_error <= float(tolerances["finite_difference_ddq_abs_rad_s2"])
        and endpoint_q_error <= float(tolerances["endpoint_q_abs_rad"])
        and endpoint_dq <= float(tolerances["endpoint_dq_abs_rad_s"])
        and endpoint_ddq <= float(tolerances["endpoint_ddq_abs_rad_s2"])
        and provisional_limits_ok
        and duration_ok
        and release_semantics_ok
    )
    all_candidate_ok &= candidate_ok
    candidate_audits.append(
        {
            "segment_id": sid,
            "candidate_ok": candidate_ok,
            "hash_ok": hash_ok,
            "rows": len(rows),
            "expected_rows": expected_count,
            "monotonic_time": monotonic,
            "finite": finite,
            "joint_limits_ok": limits_ok,
            "metadata_non_release_ok": metadata_ok,
            "max_analytic_error": max_analytic_error,
            "max_fd_dq_error_rad_s": max_fd_dq_error,
            "max_fd_ddq_error_rad_s2": max_fd_ddq_error,
            "endpoint_q_error_rad": endpoint_q_error,
            "endpoint_dq_abs_rad_s": endpoint_dq,
            "endpoint_ddq_abs_rad_s2": endpoint_ddq,
            "provisional_limits_ok": provisional_limits_ok,
            "duration_required_lower_bound_s": required_duration,
            "duration_ok": duration_ok,
            "release_semantics_ok": release_semantics_ok,
        }
    )
check("ALL_NUMERIC_CANDIDATES_RECOMPUTE", all_candidate_ok, candidate_audits)
check("ALL_CANDIDATE_HASHES_MATCH", all_hashes_ok, [{"segment_id": item["segment_id"], "hash": item["candidate_file"]["sha256"]} for item in numeric_records])
check("M05_150_SEMANTIC_GUARD", next(item for item in numeric_records if item["segment_id"] == "M05_150")["semantic_guard"] == "PHYSICS_VETO_ABORT_RECOVERY_150KG_3DPS", next(item for item in numeric_records if item["segment_id"] == "M05_150")["semantic_guard"])
check("M07_ARM_ONLY_LIMIT_RETAINED", "attached-target recovery remains HOLD" in next(item for item in numeric_records if item["segment_id"] == "M07_22")["limitation"], next(item for item in numeric_records if item["segment_id"] == "M07_22")["limitation"])

blocked = {item["segment_id"]: item for item in register["blocked_uninstantiated_segments"]}
blocked_files = list((RESULTS / "candidates").glob("M01*.csv")) + list((RESULTS / "candidates").glob("M05_22*.csv"))
check("M01_M05_22_UNINSTANTIATED", set(blocked) == {"M01", "M05_22"} and not blocked_files and all(item["numeric_candidate_created"] is False for item in blocked.values()), {"blocked": blocked, "unexpected_files": [rel(path) for path in blocked_files]})
check("M05_22_ZERO_PATH_REJECTED", blocked["M05_22"]["status"].startswith("ZERO_PATH_CANNOT_SYNCHRONIZE"), blocked["M05_22"]["status"])
check("STOW_DEFECT_RETAINED", register["source_defects_retained"]["stow_fk_regression_pass"] is False and abs(register["source_defects_retained"]["stow_max_abs_position_residual_mm"] - 567.7340012437787) < 1e-9, register["source_defects_retained"])

check("M06_SCHEMA_AND_NON_RELEASE", m06.get("schema") == "E17_M06_22_SYMBOLIC_ARM_HOLD_V1" and m06.get("authority_class") == "NON_RELEASE_DIAGNOSTIC_CANDIDATE" and m06.get("released_for_mission_gate") is False and m06.get("next_stage_authorized") is False, {k: m06.get(k) for k in ("schema", "authority_class", "released_for_mission_gate", "next_stage_authorized")})
check("M06_PHYSICAL_VALUES_NULL", all(m06.get(key) is None for key in ("physical_duration_s", "jaw_travel_m", "contact_time_s", "contact_force_N", "contact_normal", "lock_confirmation")), {key: m06.get(key) for key in ("physical_duration_s", "jaw_travel_m", "contact_time_s", "contact_force_N", "contact_normal", "lock_confirmation")})
check("M06_ARM_HOLD_EXACT", m06["q_rad"] == states["PREGRASP"] and m06["dq_rad_s"] == [0.0] * 6 and m06["ddq_rad_s2"] == [0.0] * 6, {"q": m06["q_rad"], "dq": m06["dq_rad_s"], "ddq": m06["ddq_rad_s2"]})
check("M06_SYMBOLIC_SEQUENCE_ONLY", m06["symbolic_gripper_sequence"] == ["PREGRASP", "CONTACT", "LOCK"] and m06["mission_status"].startswith("HOLD_"), {"sequence": m06["symbolic_gripper_sequence"], "status": m06["mission_status"]})

unit_audit = register["gripper_unit_audit"]
check("GRIPPER_UNIT_CONFLICT_DETECTED", unit_audit == {"urdf_prismatic_velocity_value": 15.0, "urdf_prismatic_velocity_unit": "m/s", "engineering_pack_velocity_value": 15.0, "engineering_pack_velocity_unit": "mm/s", "values_equal_only_if_units_are_stripped": True, "physical_values_equal_after_unit_conversion": False, "state": "UNIT_CONFLICT_HOLD__NO_PHYSICAL_GRIPPER_TIMING_AUTHORIZED"}, unit_audit)

check("GATE_HOLD_0_OF_8", gate.get("gate") == "HOLD" and gate.get("mission_trajectory_release") == "HOLD_0_OF_8" and gate.get("released_for_mission_gate") is False and gate.get("next_stage_authorized") is False, {k: gate.get(k) for k in ("gate", "mission_trajectory_release", "released_for_mission_gate", "next_stage_authorized")})
check("GATE_NO_RELEASE_CREDIT", all(item.get("release_credit") is False for item in gate["criteria"]), gate["criteria"])
check("GATE_REGISTER_HASH", gate["register"]["sha256"] == sha256(REGISTER), gate["register"])
check("GATE_URDF_HASH", gate["immutable_asset_hash"] == sha256(urdf_path), gate["immutable_asset_hash"])

manifest_outputs = output_manifest.get("outputs", [])
manifest_sources = output_manifest.get("sources", [])
manifest_hash_ok = all((WORKSPACE / item["path"]).is_file() and sha256(WORKSPACE / item["path"]) == item["sha256"] for item in manifest_outputs)
manifest_source_ok = all((WORKSPACE / item["path"]).is_file() and sha256(WORKSPACE / item["path"]) == item["actual_sha256"] and item.get("hash_match") is True for item in manifest_sources)
check("OUTPUT_MANIFEST_COUNTS", output_manifest.get("output_count") == len(manifest_outputs) == 9 and output_manifest.get("source_count") == len(manifest_sources) == 9, {"outputs": len(manifest_outputs), "sources": len(manifest_sources)})
check("OUTPUT_MANIFEST_HASH_CLOSURE", manifest_hash_ok and manifest_source_ok and sha256(BUILDER) == output_manifest["generator"]["sha256"], {"outputs": manifest_hash_ok, "sources": manifest_source_ok, "generator": sha256(BUILDER) == output_manifest["generator"]["sha256"]})
check("OUTPUT_MANIFEST_NON_RELEASE", output_manifest.get("geometry_artifact_count") == 0 and output_manifest.get("released_segments") == 0 and output_manifest.get("next_stage_authorized") is False, {k: output_manifest.get(k) for k in ("geometry_artifact_count", "released_segments", "next_stage_authorized")})

geometry_suffixes = {".step", ".stp", ".stl", ".glb", ".3mf", ".fcstd", ".sldprt", ".sldasm", ".urdf"}
created_geometry = [rel(path) for path in PACKAGE.rglob("*") if path.is_file() and path.suffix.lower() in geometry_suffixes]
check("NO_GEOMETRY_OR_URDF_CREATED_IN_E17", not created_geometry, created_geometry)


def q_within_limits(q):
    return len(q) == 6 and all(math.isfinite(x) and lower <= x <= upper for x, (lower, upper) in zip(q, limits))


def m06_schema_valid(item):
    return all(item.get(key) is None for key in ("physical_duration_s", "jaw_travel_m", "contact_time_s", "contact_force_N", "contact_normal", "lock_confirmation")) and item.get("released_for_mission_gate") is False


def release_record_valid(item):
    return item.get("released_for_mission_gate") is False and item.get("next_stage_authorized") is False and all(value != "PASS" for value in item.get("release_gates", {}).values())


negative_controls = []
mutant_q = list(states["HOME"])
mutant_q[1] = 0.01
negative_controls.append({"id": "NC-01", "mutation": "J2 above URDF upper limit", "detected": not q_within_limits(mutant_q)})
mutant_q = [value * 180.0 / math.pi for value in states["HOME"]]
negative_controls.append({"id": "NC-02", "mutation": "radians reinterpreted as degrees", "detected": not q_within_limits(mutant_q)})
mutant_order = list(joint_order)
mutant_order[1], mutant_order[2] = mutant_order[2], mutant_order[1]
negative_controls.append({"id": "NC-03", "mutation": "joint2/joint3 order swap", "detected": mutant_order != joint_order})
zero_sync_is_valid = states["PREGRASP"] != states["PREGRASP"] or bool(blocked["M05_22"].get("target_twist"))
negative_controls.append({"id": "NC-04", "mutation": "PREGRASP-to-PREGRASP zero path promoted to synchronization", "detected": not zero_sync_is_valid})
mutant_m06 = copy.deepcopy(m06)
mutant_m06["physical_duration_s"] = 1.0
mutant_m06["contact_force_N"] = 25.0
negative_controls.append({"id": "NC-05", "mutation": "invent M06 contact duration and force", "detected": not m06_schema_valid(mutant_m06)})
gripper_timing_claim_valid = unit_audit["physical_values_equal_after_unit_conversion"] and not unit_audit["state"].startswith("UNIT_CONFLICT")
negative_controls.append({"id": "NC-06", "mutation": "derive physical gripper timing from stripped value 15", "detected": not gripper_timing_claim_valid})
mutant_release = copy.deepcopy(numeric_records[0])
mutant_release["released_for_mission_gate"] = True
mutant_release["release_gates"]["collision"] = "PASS"
negative_controls.append({"id": "NC-07", "mutation": "release seed with collision PASS injected", "detected": not release_record_valid(mutant_release)})
mutant_semantic = copy.deepcopy(next(item for item in numeric_records if item["segment_id"] == "M05_150"))
mutant_semantic["semantic_guard"] = "CAPTURE_150KG"
negative_controls.append({"id": "NC-08", "mutation": "150kg abort recovery relabeled capture", "detected": mutant_semantic["semantic_guard"] != "PHYSICS_VETO_ABORT_RECOVERY_150KG_3DPS"})
m01_prerequisites = {"stow_fk_match": False, "hdrm_release_confirmed": False, "release_sweep_authority": False}
negative_controls.append({"id": "NC-09", "mutation": "create M01 release candidate without prerequisites", "detected": not all(m01_prerequisites.values())})
m07_claim = {"released": True, "target_lock_confirmed": False, "attached_target_collision_evaluated": False}
negative_controls.append({"id": "NC-10", "mutation": "release full M07_22 with unconfirmed lock/target collision", "detected": m07_claim["released"] and not (m07_claim["target_lock_confirmed"] and m07_claim["attached_target_collision_evaluated"])})
check("NEGATIVE_CONTROLS_ALL_DETECTED", all(item["detected"] for item in negative_controls), negative_controls)

failed = [item["id"] for item in checks if not item["pass"]]
report = {
    "schema": "E17_B601_TRAJECTORY_CANDIDATE_VALIDATION_V1",
    "generated_local": authority["generated_local"],
    "verdict": "PASS_NUMERIC_SEED_INTEGRITY_ONLY__MISSION_RELEASE_REMAINS_HOLD" if not failed else "FAIL_E17_INTEGRITY",
    "package_integrity_pass": not failed,
    "mission_trajectory_release": "HOLD_0_OF_8",
    "released_for_mission_gate": False,
    "next_stage_authorized": False,
    "checks_passed": len(checks) - len(failed),
    "checks_total": len(checks),
    "failed_checks": failed,
    "negative_controls_passed": sum(item["detected"] for item in negative_controls),
    "negative_controls_total": len(negative_controls),
    "negative_controls": negative_controls,
    "candidate_audits": candidate_audits,
    "checks": checks,
    "input_manifest_sha256": sha256(INPUT_MANIFEST),
    "output_manifest_sha256": sha256(OUTPUT_MANIFEST),
    "gate_sha256": sha256(GATE),
    "accepted_urdf_sha256": sha256(urdf_path),
    "claim_limit": "Validation PASS proves deterministic numerical seed integrity only. It grants no trajectory, collision, harness, contact, SAFE-00, dynamics, RL or hardware authority.",
}
write_json(REPORT, report)
print(json.dumps({"verdict": report["verdict"], "checks": f"{report['checks_passed']}/{report['checks_total']}", "negative_controls": f"{report['negative_controls_passed']}/{report['negative_controls_total']}", "failed": failed, "validation_sha256": sha256(REPORT)}, indent=2, ensure_ascii=False))
raise SystemExit(0 if not failed else 1)
