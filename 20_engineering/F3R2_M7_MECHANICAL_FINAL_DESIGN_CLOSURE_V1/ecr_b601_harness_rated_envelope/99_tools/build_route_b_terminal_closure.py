# -*- coding: utf-8 -*-
"""Build the fail-closed Route-B terminal decision package.

The builder is intentionally capable of producing a negative terminal
decision.  It never weakens criteria, edits the accepted URDF, hides missing
mission trajectories or turns UNKNOWN into ALLOW.

Run with FreeCADCmd.exe.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import itertools
import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml

import harness_uncertainty as hu


HERE = Path(__file__).resolve().parent
BUILDER_SOURCE = Path(__file__).resolve()
UNCERTAINTY_SOURCE = HERE / "harness_uncertainty.py"
VALIDATOR_SOURCE = HERE / "validate_route_b_terminal_closure.py"
PKG = HERE.parent
M7 = PKG.parent
PROJECT = M7.parents[1]
EXACT_SOURCE = PKG / "02_exact_predicate" / "harness_exact_check.py"
PROBE_RESULT = PKG / "02_exact_predicate" / "CURRENT_ROUTE_KEY_STATE_PROBE_V1.json"
ODR = M7 / "00_authority" / "M7_OWNER_DECISION_ODR35_TO_ODR41_B601_HARNESS_RATED_ENVELOPE_V1.yaml"
WORK_ORDER = PKG / "00_authority" / "ECR_B601_HARNESS_RATED_ENVELOPE_01_WORK_ORDER_V1.yaml"
PIN_FILE = PKG / "00_authority" / "ROUTE_B_FROZEN_INPUT_PINS_V1.yaml"
URDF = PROJECT / "20_engineering" / "cad" / "spacecraft_layout" / "arm_b601_v1" / "arm_b601_v1.urdf"
POSES = PROJECT / "20_engineering" / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807" / "04_configurations" / "F3R2_ARM_INITIAL_POSE.yaml"
CONTROL = PROJECT / "20_engineering" / "config" / "control_scene" / "control_01_v0.yaml"
V2 = M7 / "ecr_solar_array_r2" / "HARNESS_B601_FULL_FK_SWEEP_V2.json"
OLD_MASS = M7 / "wp2_design_mass" / "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
OLD_HANDOFF = M7 / "wp13_embodied_contract" / "MECHANICAL_TO_EMBODIED_HANDOFF_GATE_R2.json"
OLD_CONTRACT = M7 / "wp13_embodied_contract" / "EMBODIED_MECHANICAL_CONTRACT_R2.yaml"
FLEX = M7 / "ecr_solar_array_r2" / "FLEXIBLE_APPENDAGE_R2.yaml"
SOLAR_GATE = M7 / "ecr_solar_array_r2" / "SOLAR_ARRAY_R2_CONTINUOUS_CLEARANCE_V1.json"
SOLAR_STEP = M7 / "ecr_solar_array_r2" / "SOLAR_ARRAY_R2_CANDIDATE_V1.step"

PRODUCT = PKG / "01_product_definition" / "B601_HARNESS_ROUTING_PRODUCT_DEFINITION_V1.yaml"
PRED_CONTRACT = PKG / "02_exact_predicate" / "B601_HARNESS_EXACT_PREDICATE_CONTRACT_V1.yaml"
ENV_YAML = PKG / "03_envelope" / "B601_HARNESS_RATED_ENVELOPE_V1.yaml"
ENV_CSV = PKG / "03_envelope" / "B601_HARNESS_ENVELOPE_MAP_V1.csv"
ENV_NPZ = PKG / "03_envelope" / "B601_HARNESS_ENVELOPE_MAP_V1.npz"
MISSION_CONTRACT = PKG / "04_mission" / "B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml"
POSE_REBIND = PKG / "04_mission" / "B601_MISSION_POSE_AUTHORITY_REBIND_V1.yaml"
MISSION_GATE = PKG / "04_mission" / "B601_HARNESS_MISSION_COVERAGE_GATE.json"
MASS = PKG / "05_mass_torque" / "B601_HARNESS_MASS_PROPERTIES_V1.yaml"
MASS_OVERLAY = PKG / "05_mass_torque" / "SYSTEM_DESIGN_MASS_PROPERTIES_V4_HARNESS_CANDIDATE.yaml"
TORQUE = PKG / "05_mass_torque" / "B601_HARNESS_JOINT_TORQUE_ENVELOPE_V1.yaml"
CONTRACT = PKG / "06_contract" / "EMBODIED_MECHANICAL_CONTRACT_R3_HARNESS_CANDIDATE.yaml"
HANDOFF = PKG / "07_release" / "MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json"
RED_TEAM = PKG / "07_release" / "B601_HARNESS_SCOPED_RED_TEAM_V1.json"
TERMINAL = PKG / "07_release" / "B601_HARNESS_TERMINAL_GATE_V1.json"
ROUTE_C = PKG / "08_route_c" / "ECR_HARNESS_FULL_RANGE_01.yaml"
MANIFEST = PKG / "07_release" / "OUTPUT_MANIFEST_V1.json"

REQUIRED_BEND_MM = 30.0
NOMINAL_MASS_INPUTS = hu.nominal_constants()
CUT_LENGTH_M = float(NOMINAL_MASS_INPUTS["cut_length_m"])
TOTAL_MASS_KG = float(NOMINAL_MASS_INPUTS["total_mass_kg"])


def now_local():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def rel(path: Path):
    return str(path.relative_to(PROJECT)).replace("\\", "/")


def ensure_parents():
    for path in (
        PRODUCT, PRED_CONTRACT, ENV_YAML, ENV_CSV, ENV_NPZ,
        POSE_REBIND, MISSION_CONTRACT, MISSION_GATE, MASS, MASS_OVERLAY, TORQUE,
        CONTRACT, HANDOFF, RED_TEAM, TERMINAL, ROUTE_C, MANIFEST,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)


def machine_safe(value):
    """Convert NumPy scalars and non-binding non-finite diagnostics safely.

    Binding predicates classify non-finite margins as UNKNOWN before this
    serializer is reached.  This conversion only prevents JSON/YAML from
    emitting non-standard NaN/Infinity tokens in auxiliary diagnostics.
    """
    if isinstance(value, dict):
        return {str(key): machine_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [machine_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return machine_safe(value.tolist())
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_yaml(path: Path, data):
    path.write_text(
        yaml.safe_dump(
            machine_safe(data),
            sort_keys=False,
            allow_unicode=True,
            width=110,
        ),
        encoding="utf-8",
    )


def write_json(path: Path, data):
    path.write_text(json.dumps(machine_safe(data), indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def load_exact():
    spec = importlib.util.spec_from_file_location("harness_exact_api", EXACT_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import exact evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    evaluator = module.HarnessExactEvaluator(required_bend_radius_mm=REQUIRED_BEND_MM)
    if not evaluator.integrity_ok:
        raise RuntimeError("frozen exact-input integrity failed: " + json.dumps(evaluator.integrity_receipt))
    return evaluator


def product_definition():
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    design = v2["design"]
    return {
        "schema": "B601_HARNESS_ROUTING_PRODUCT_DEFINITION_V1",
        "generated_local": now_local(),
        "authority": "ODR-35..ODR-41",
        "product_status": "FROZEN_TESTED_CANDIDATE__ROUTE_B_REJECTED",
        "route_id": "B601_HARNESS_RATED_ROUTING_V1",
        "architecture": "EXTERNAL_FIXED_DRESS_PACK_WITH_RATED_ENVELOPE",
        "scope": "H-RUN-01_ARM_POWER_AND_DATA only",
        "out_of_scope": ["camera harness", "HDRM harness", "flight electrical qualification"],
        "hardware_items": [
            {"part_id": "HRN-B601-001", "name": "base feedthrough and abrasion grommet", "definition": "P0/HN-01 interface", "selection": None, "status": "HOLD_VENDOR_SELECTION"},
            {"part_id": "HRN-B601-002", "name": "joint1 captive clock-spring coil guide", "definition": {"plane_x_S_mm": 330.0, "candidate_radius_mm": 72.05}, "status": "TESTED_CANDIDATE"},
            {"part_id": "HRN-B601-003", "name": "base fixed clamps HC-1/HC-2", "definition": {"P1_S_mm": design["P1_S_mm"], "P2_S_mm": design["P2_S_mm"]}, "status": "CANDIDATE_NOT_DRAWING_RELEASED"},
            {"part_id": "HRN-B601-004", "name": "link1 moving clamp HC-3", "definition": {"link1_local_mm": design["hc3_clamp_link1_local_mm"]}, "status": "CANDIDATE_NOT_DRAWING_RELEASED"},
            {"part_id": "HRN-B601-005", "name": "joint2-joint4 axial U-bend guides", "definition": {k: v for k, v in design["crossings"].items() if k in ("joint2", "joint3", "joint4")}, "status": "TESTED_CANDIDATE"},
            {"part_id": "HRN-B601-006", "name": "joint5-joint6 wrist wraps", "definition": {k: v for k, v in design["crossings"].items() if k in ("joint5", "joint6")}, "status": "TESTED_CANDIDATE"},
            {"part_id": "HRN-B601-007", "name": "link-side sleeve and P-clamp set", "quantity": 18, "status": "HOLD_VENDOR_SELECTION"},
            {"part_id": "HRN-B601-008", "name": "gripper backshell and strain relief", "definition": {"G0_gripper_link_local_mm": design["G0_gripper_link_local_mm"]}, "status": "HOLD_CONNECTOR_SELECTION"},
        ],
        "length_ledger": {
            "cut_length_candidate_mm": 4001.158,
            "maximum_geometric_path_in_full_range_sweep_mm": 3810.627,
            "installation_surplus_at_full_range_argmax_mm": 190.531,
            "joint1_takeup_supply_mm": 403.48,
            "joint1_wp1_requirement_mm": 347.493596,
            "joint1_takeup_margin_mm": 55.986404,
            "semantic_correction": "403.48 mm is joint1 take-up supply, not additional cut-length service reserve",
        },
        "cross_section_candidate": {
            "overall_diameter_mm": 10.0,
            "tube_radius_used_by_v2_mm": 5.0,
            "conductors_mass_proxy": "24 x TE SPEC55 22-AWG proxy",
            "vendor_selection_status": "HOLD",
        },
        "bend_requirement": {
            "terminal_design_requirement_mm": REQUIRED_BEND_MM,
            "basis": "NASA-STD-8739.4A Table 7-1: overall harness with AWG 10 or smaller and no coax, minimum 3 x OD",
            "official_source": "https://standards.nasa.gov/standard/nasa/nasa-std-87394",
            "v2_legacy_candidate_class_mm": 25.0,
            "v2_minimum_measured_mm": v2["results"]["min_bend_radius_mm"],
            "status": "FAIL",
        },
        "mass_proxy_source": {
            "part": "TE 55/9952-22-1(LAT3)",
            "nominal_mass_kg_per_km_per_wire": 4.27,
            "nominal_od_mm_per_wire": 1.1,
            "official_source": "https://www.te.com/en/product-7534143001.html",
            "use_restriction": "mass proxy only; not an electrical or flight part selection",
        },
        "frozen_geometry_source": {"path": rel(V2), "sha256": sha256(V2)},
        "negative_result": v2["failure_analysis"],
        "open_product_items": [
            "electrical load map and conductor count not approved",
            "connector and strain-relief part numbers absent",
            "clamp drawings and fastener schedule absent",
            "unplaced cut-length surplus geometry unresolved",
            "bundle stiffness/friction/rate-dependent resistance unmeasured",
        ],
    }


def predicate_contract():
    return {
        "schema": "B601_HARNESS_EXACT_PREDICATE_CONTRACT_V1",
        "generated_local": now_local(),
        "authority": "ODR-37",
        "api": "HarnessExactEvaluator.check(q_rad, state_id)",
        "source": {"path": rel(EXACT_SOURCE), "sha256": sha256(EXACT_SOURCE)},
        "kernel": {"path": rel(M7 / "ecr_solar_array_r2" / "sweep_b601_harness_full_fk.py"), "sha256": sha256(M7 / "ecr_solar_array_r2" / "sweep_b601_harness_full_fk.py")},
        "frozen_input_pins": {
            "path": rel(PIN_FILE),
            "expected_sha256_compiled_into_evaluator": "6BB8E9C5FF6910BE07D1720D320C4CB560A2CF07AD254DEB83E931AF4731C588",
            "actual_sha256": sha256(PIN_FILE),
            "match": sha256(PIN_FILE) == "6BB8E9C5FF6910BE07D1720D320C4CB560A2CF07AD254DEB83E931AF4731C588",
            "mismatch_classification": "UNKNOWN",
            "mismatch_action": "ABORT",
        },
        "input_units": {"q_rad": "rad"},
        "margins": {
            "clearance_mm": "minimum signed centerline-to-solid distance minus bundle radius",
            "bend_margin_mm": "minimum centerline bend radius minus 30.0 mm terminal requirement",
            "pinch_mm": "minimum signed joint-interface cable-to-parent/child clearance",
            "length_margin_mm": "4001.158 mm cut-length candidate minus required centerline length",
            "joint_limit_margin_rad": "minimum accepted-URDF hardware-limit margin",
        },
        "safe_rule": "all five margins >= 0 and empty_comparison_sets == 0",
        "classification": ["SAFE", "UNSAFE", "UNKNOWN"],
        "fail_closed": {"UNKNOWN": "ABORT", "UNSAFE": "ABORT", "SAFE": "ALLOW_AFTER_OTHER_GATES"},
        "map_and_surrogate_authority": "ADVISORY_PREFILTER_ONLY",
        "runtime_integrity_rule": "every evaluator startup verifies the frozen pin-file hash, every direct dependency, and every V2 transitive geometry input before loading geometry",
        "known_conservative_limitation": "protected feedthrough/clamp/backshell contact zones are not exempted; this can create conservative false negatives but cannot create an unsafe ALLOW",
    }


def map_envelope(evaluator):
    poses = yaml.safe_load(POSES.read_text(encoding="utf-8"))["poses"]
    control = yaml.safe_load(CONTROL.read_text(encoding="utf-8"))
    pre = np.asarray(control["trajectories"]["T2"]["q_initial_rad"], dtype=float)
    families = {
        "HOME_FAMILY": np.asarray(poses["Q_DEPLOYED_HOME"]["q_rad"], dtype=float),
        "TASK_READY_FAMILY": np.asarray(poses["Q_SERVICE_READY"]["q_rad"], dtype=float),
        "PREGRASP_FAMILY": pre,
    }
    grid = np.linspace(-3.14, 0.0, 5)
    rows = []
    by_family = {name: {} for name in families}
    for family, base in families.items():
        for i, q2 in enumerate(grid):
            for j, q3 in enumerate(grid):
                q = base.copy()
                q[1], q[2] = q2, q3
                result = evaluator.check(q, state_id=f"{family}_Q2_{i}_Q3_{j}")
                row = row_from_result(result, family, "COARSE_Q2_Q3", i, j)
                rows.append(row)
                by_family[family][(i, j)] = result["status"]

    refinements = 0
    for family, base in families.items():
        states = by_family[family]
        for i in range(len(grid) - 1):
            for j in range(len(grid) - 1):
                corner_status = {
                    states[(i, j)], states[(i + 1, j)],
                    states[(i, j + 1)], states[(i + 1, j + 1)],
                }
                if len(corner_status) <= 1:
                    continue
                q = base.copy()
                q[1] = 0.5 * (grid[i] + grid[i + 1])
                q[2] = 0.5 * (grid[j] + grid[j + 1])
                result = evaluator.check(q, state_id=f"{family}_REFINE_{i}_{j}")
                rows.append(row_from_result(result, family, "ADAPTIVE_BOUNDARY", i + 0.5, j + 0.5))
                refinements += 1

    with ENV_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    numeric = np.asarray([
        [r[f"q{i}_rad"] for i in range(1, 7)]
        + [r["clearance_margin_mm"], r["bend_margin_mm"], r["pinch_margin_mm"], r["length_margin_mm"], r["joint_limit_margin_rad"]]
        for r in rows
    ], dtype=float)
    codes = np.asarray([{"SAFE": 1, "UNKNOWN": 0, "UNSAFE": -1}[r["status"]] for r in rows], dtype=np.int8)
    np.savez_compressed(
        ENV_NPZ,
        samples=numeric,
        status_code=codes,
        columns=np.asarray(["q1_rad", "q2_rad", "q3_rad", "q4_rad", "q5_rad", "q6_rad", "clearance_margin_mm", "bend_margin_mm", "pinch_margin_mm", "length_margin_mm", "joint_limit_margin_rad"]),
    )
    counts = {status: sum(r["status"] == status for r in rows) for status in ("SAFE", "UNSAFE", "UNKNOWN")}
    probe = json.loads(PROBE_RESULT.read_text(encoding="utf-8"))
    env = {
        "schema": "B601_HARNESS_RATED_ENVELOPE_V1",
        "generated_local": now_local(),
        "authority": "ODR-35/37/38",
        "E_HW": {
            "source": rel(URDF),
            "sha256": sha256(URDF),
            "joint_limits_rad": evaluator.hardware_limits.tolist(),
            "status": "UNCHANGED_HARDWARE_TRUTH",
        },
        "E_HRN": {
            "architecture": "FIXED_EXTERNAL_DRESS_R2_HRN_05",
            "exact_predicate": rel(EXACT_SOURCE),
            "map_csv": rel(ENV_CSV),
            "map_npz": rel(ENV_NPZ),
            "samples_total": len(rows),
            "sample_counts": counts,
            "adaptive_boundary_samples": refinements,
            "adaptive_note": "no SAFE/UNSAFE sign-changing cells existed when refinements=0; unsampled states remain UNKNOWN",
            "conservative_box": None,
            "conservative_box_status": "EMPTY_NO_OBSERVED_SAFE_SAMPLE",
            "release_status": "NOT_RELEASED",
            "runtime_integrity": {
                "status": "PASS" if evaluator.integrity_ok else "UNKNOWN_ABORT",
                "pin_file_match": evaluator.integrity_receipt["pin_file_match"],
                "checks_total": evaluator.integrity_receipt.get("checks_total", 0),
                "checks_passed": evaluator.integrity_receipt.get("checks_passed", 0),
                "mismatches": evaluator.integrity_receipt.get("mismatches", []),
            },
        },
        "mandatory_key_state_probe": {
            "path": rel(PROBE_RESULT),
            "sha256": sha256(PROBE_RESULT),
            "states_safe": probe["states_safe"],
            "states_unsafe": probe["states_unsafe"],
            "states_unknown": probe["states_unknown"],
        },
        "E_MISSION": {"source": rel(MISSION_CONTRACT), "status": "INCOMPLETE_AND_KEY_STATES_UNSAFE"},
        "E_OP": {"status": "EMPTY_NOT_RELEASED", "reason": "mandatory key states are outside E_HRN and no observed safe map sample exists"},
        "full_urdf_range_external_harness": "DOCUMENTED_NEGATIVE_RESULT",
        "unknown_policy": "ABORT",
        "route_b_verdict": "REJECTED",
    }
    write_yaml(ENV_YAML, env)
    return rows, counts, refinements


def row_from_result(result, family, sample_type, i, j):
    q = result.get("q_rad", [math.nan] * 6)
    margins = result.get("margins", {})
    return {
        "sample_id": result.get("state_id"),
        "family": family,
        "sample_type": sample_type,
        "grid_i": i,
        "grid_j": j,
        **{f"q{k + 1}_rad": float(q[k]) for k in range(6)},
        "clearance_margin_mm": float(margins.get("clearance_mm", math.nan)),
        "bend_margin_mm": float(margins.get("bend_margin_mm", math.nan)),
        "pinch_margin_mm": float(margins.get("pinch_mm", math.nan)),
        "length_margin_mm": float(margins.get("length_margin_mm", math.nan)),
        "joint_limit_margin_rad": float(margins.get("joint_limit_margin_rad", math.nan)),
        "status": result["status"],
        "required_action": result.get("required_action", "ABORT"),
    }


def key_state_q_map():
    pose_doc = yaml.safe_load(POSES.read_text(encoding="utf-8"))["poses"]
    control = yaml.safe_load(CONTROL.read_text(encoding="utf-8"))
    pregrasp = control["trajectories"]["T2"]["q_initial_rad"]
    return {
        "Q_AS_BUILT_REFERENCE": pose_doc["Q_AS_BUILT_REFERENCE"]["q_rad"],
        "ARM_STOWED_ONORBIT_C05": pose_doc["Q_STOW_ENGINEERING_CANDIDATE"]["q_rad"],
        "ARM_RELEASE_CLEAR": pose_doc["Q_RELEASE_CLEAR"]["q_rad"],
        "Q_DEPLOYED_HOME": pose_doc["Q_DEPLOYED_HOME"]["q_rad"],
        "ARM_TASK_READY_C06": pose_doc["Q_SERVICE_READY"]["q_rad"],
        "PREGRASP": pregrasp,
        "CONTACT": pregrasp,
        "CAPTURE_22KG": pregrasp,
        "POST_CAPTURE_22KG": pregrasp,
        "PHYSICS_VETO_150KG": pregrasp,
        "SAFE_RECOVERY_TARGET": pose_doc["Q_DEPLOYED_HOME"]["q_rad"],
    }


def regenerate_key_state_probe(evaluator):
    states = key_state_q_map()
    results = [evaluator.check(q, state_id=name) for name, q in states.items()]
    mandatory_ids = [name for name in states if name != "Q_AS_BUILT_REFERENCE"]
    mandatory_results = [item for item in results if item["state_id"] in mandatory_ids]
    report = {
        "schema": "CURRENT_ROUTE_KEY_STATE_PROBE_V1",
        "generated_local": now_local(),
        "role": "HASH_GUARDED_PRE_ENVELOPE_EXACT_FALSIFICATION_PROBE",
        "authority": "ODR-35..41; geometry semantics inherited unchanged from R2-HRN-05",
        "frozen_input_integrity": evaluator.integrity_receipt,
        "accepted_urdf_limits_unchanged": sha256(URDF) == "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
        "candidate_class_values": {
            "tube_radius_mm": 5.0,
            "bend_radius_required_mm": REQUIRED_BEND_MM,
            "note": "terminal design-class values, not vendor qualification data",
        },
        "states_total": len(results),
        "states_safe": sum(r["status"] == "SAFE" for r in results),
        "states_unsafe": sum(r["status"] == "UNSAFE" for r in results),
        "states_unknown": sum(r["status"] == "UNKNOWN" for r in results),
        "mandatory_states_total": len(mandatory_results),
        "mandatory_states_safe": sum(r["status"] == "SAFE" for r in mandatory_results),
        "mandatory_states_unsafe": sum(r["status"] == "UNSAFE" for r in mandatory_results),
        "mandatory_states_unknown": sum(r["status"] == "UNKNOWN" for r in mandatory_results),
        "route_b_key_state_screen": "PASS_CONTINUE_TO_TRAJECTORY_MAPPING" if all(r["status"] == "SAFE" for r in mandatory_results) else "FAIL_ROUTE_B_KEY_STATE_CONTAINMENT",
        "decision_rule": "all mandatory key states must be SAFE before a trajectory envelope can pass",
        "results": results,
    }
    write_json(PROBE_RESULT, report)
    return report


def build_pose_rebind(evaluator, probe):
    pose_source = yaml.safe_load(POSES.read_text(encoding="utf-8"))
    q_map = key_state_q_map()
    probe_by_id = {item["state_id"]: item for item in probe["results"]}
    source_ids = {
        "STOW": "ARM_STOWED_ONORBIT_C05",
        "RELEASE_CLEAR": "ARM_RELEASE_CLEAR",
        "HOME": "Q_DEPLOYED_HOME",
        "TASK_READY": "ARM_TASK_READY_C06",
        "PREGRASP": "PREGRASP",
    }
    states = {}
    for name, state_id in source_ids.items():
        q = np.asarray(q_map[state_id], dtype=float)
        margins = np.minimum(q - evaluator.hardware_limits[:, 0], evaluator.hardware_limits[:, 1] - q)
        exact_status = probe_by_id[state_id]["status"]
        states[name] = {
            "probe_state_id": state_id,
            "q_rad": q.tolist(),
            "finite_six_vector": bool(q.shape == (6,) and np.all(np.isfinite(q))),
            "inside_current_urdf_limits": bool(np.all(margins >= 0.0)),
            "minimum_joint_limit_margin_rad": float(np.min(margins)),
            "current_exact_fk_loadability": "PASS" if exact_status in ("SAFE", "UNSAFE") else "UNKNOWN",
            "harness_safety_is_separate": exact_status,
        }
    mount = np.asarray(pose_source["mount"]["transform_mm_rows"], dtype=float)
    all_loadable = all(
        item["finite_six_vector"] and item["inside_current_urdf_limits"]
        and item["current_exact_fk_loadability"] == "PASS"
        for item in states.values()
    )
    rebind = {
        "schema": "B601_MISSION_POSE_AUTHORITY_REBIND_V1",
        "generated_local": now_local(),
        "authority": "ODR-36/39 limited rebind",
        "scope": "q-vector loadability, current joint limits and exact-FK solvability only; no trajectory or contact release",
        "legacy_pose_source": {
            "path": rel(POSES),
            "expected_sha256": yaml.safe_load(PIN_FILE.read_text(encoding="utf-8"))["mission_and_mass_dependencies"]["legacy_pose_source"]["expected_sha256"],
            "actual_sha256": sha256(POSES),
            "hash_match": sha256(POSES) == yaml.safe_load(PIN_FILE.read_text(encoding="utf-8"))["mission_and_mass_dependencies"]["legacy_pose_source"]["expected_sha256"],
            "embedded_urdf_sha256": pose_source["kinematics_authority"]["sha256"],
            "embedded_urdf_matches_current": pose_source["kinematics_authority"]["sha256"] == sha256(URDF),
            "legacy_file_modified": False,
        },
        "current_urdf": {"path": rel(URDF), "sha256": sha256(URDF)},
        "mount_transform_finite_4x4": bool(mount.shape == (4, 4) and np.all(np.isfinite(mount))),
        "states": states,
        "all_named_q_vectors_loadable": all_loadable,
        "rebind_status": "PASS_CURRENT_URDF_LOADABILITY_SCOPE" if all_loadable else "UNKNOWN_ABORT",
        "trajectory_authority_granted": False,
        "physical_contact_authority_granted": False,
    }
    write_yaml(POSE_REBIND, rebind)
    return rebind


def mission_artifacts(evaluator, probe):
    pose_rebind = build_pose_rebind(evaluator, probe)
    states = {
        name: {
            "q_rad": item["q_rad"],
            "authority": "CURRENT_URDF_LOADABILITY_REBIND_WITHOUT_TRAJECTORY_RELEASE",
            "rebind_state": item["probe_state_id"],
        }
        for name, item in pose_rebind["states"].items()
    }
    raw_segments = [
        ("M01", "STOW", "RELEASE_CLEAR", "ARM_RELEASE", "MISSING", "BOTH"),
        ("M02", "RELEASE_CLEAR", "HOME", "DEPLOY_TO_HOME", "PROVISIONAL_MINIMUM_JERK_SEED_ONLY", "BOTH"),
        ("M03", "HOME", "TASK_READY", "TASK_STAGING", "PROVISIONAL_MINIMUM_JERK_SEED_ONLY", "BOTH"),
        ("M04", "TASK_READY", "PREGRASP", "PREGRASP_APPROACH", "PROVISIONAL_MINIMUM_JERK_SEED_ONLY", "BOTH"),
        ("M05_22", "PREGRASP", "PREGRASP", "SYNCHRONIZATION_22KG_0P5DPS", "MISSING_22KG_SYNC_TRAJECTORY", "22KG"),
        ("M06_22", "PREGRASP", "PREGRASP", "CONTACT_CAPTURE_POST_CAPTURE", "ARM_Q_HOLD_ONLY_CONTACT_GEOMETRY_HOLD", "22KG"),
        ("M07_22", "PREGRASP", "HOME", "SAFE_RECOVERY_AFTER_22KG", "PROVISIONAL_REVERSE_SEED_ONLY", "22KG"),
        ("M05_150", "PREGRASP", "HOME", "PHYSICS_VETO_ABORT_RECOVERY_150KG_3DPS", "PROVISIONAL_REVERSE_SEED_ONLY", "150KG"),
    ]
    segments = []
    for seg_id, source, target, purpose, authority, anchor in raw_segments:
        released = authority == "RELEASED_HASH_BOUND_TRAJECTORY"
        segments.append({
            "id": seg_id, "from": source, "to": target, "purpose": purpose,
            "trajectory_authority": authority, "expected_anchor": anchor,
            "released_for_mission_gate": released,
            "status": "READY" if released else "UNKNOWN",
        })
    contract = {
        "schema": "B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1",
        "generated_local": now_local(),
        "authority": "ODR-39 plus existing sim10/sim12 anchor verdicts",
        "joint_order": [f"joint{i}" for i in range(1, 7)],
        "units": {"q": "rad", "time": "s"},
        "pose_authority_rebind": {"path": rel(POSE_REBIND), "sha256": sha256(POSE_REBIND), "status": pose_rebind["rebind_status"]},
        "states": states,
        "segments": segments,
        "anchor_outcomes": {
            "22kg_0p5dps": "EXECUTE_NOMINAL_CAPTURE_CHAIN_REQUIRED",
            "150kg_3dps": "INFEASIBLE_RATE__PHYSICS_VETO_ABORT_RECOVERY_REQUIRED",
        },
        "interpolation_seed": "quintic minimum jerk for candidate-only segments",
        "continuous_claim": "NOT_MADE",
        "missing_authority_is": "UNKNOWN",
        "unknown_policy": "ABORT",
    }
    write_yaml(MISSION_CONTRACT, contract)

    required = [
        "ARM_STOWED_ONORBIT_C05", "ARM_RELEASE_CLEAR", "Q_DEPLOYED_HOME",
        "ARM_TASK_READY_C06", "PREGRASP", "CONTACT", "CAPTURE_22KG",
        "POST_CAPTURE_22KG", "PHYSICS_VETO_150KG", "SAFE_RECOVERY_TARGET",
    ]
    results = {item["state_id"]: item for item in probe["results"]}
    key_checks = []
    for state in required:
        item = results[state]
        margins = item.get("margins", {})
        key_checks.append({
            "state_id": state,
            "harness_status": item["status"],
            "clearance_mm": margins.get("clearance_mm"),
            "bend_radius_mm": margins.get("bend_radius_mm"),
            "bend_margin_vs_terminal_30mm_mm": margins.get("bend_margin_mm"),
            "pinch_mm": margins.get("pinch_mm"),
            "length_margin_mm": margins.get("length_margin_mm"),
            "empty_comparison_sets": item.get("empty_comparison_sets"),
            "pass": item["status"] == "SAFE",
            "derivation": "exact_result.status == SAFE",
        })

    released_segments = sum(bool(item["released_for_mission_gate"]) for item in segments)
    trajectory_complete = released_segments == len(segments)
    key_states_complete = all(item["pass"] for item in key_checks)
    external_gates = {
        "IK": "UNKNOWN_NOT_EVALUATED_FOR_COMPLETE_TRAJECTORY_SET",
        "COLLISION": "UNKNOWN_NOT_EVALUATED_FOR_COMPLETE_CURRENT_R2_TRAJECTORY_SET",
        "SOLAR_KEEP_OUT": "UNKNOWN_NOT_EVALUATED_FOR_COMPLETE_TRAJECTORY_SET",
        "SAFE_00": "UNKNOWN_22KG_ONLY_EXISTING_POLICY__150KG_NOT_REGISTERED",
    }
    external_complete = all(value == "PASS" for value in external_gates.values())
    mission_pass = bool(
        evaluator.integrity_ok and pose_rebind["all_named_q_vectors_loadable"]
        and key_states_complete and trajectory_complete and external_complete
    )
    reasons = []
    if not key_states_complete:
        reasons.append("one or more mandatory key states are not SAFE under the hash-guarded exact predicate")
    if not trajectory_complete:
        reasons.append("complete authority-tagged mission trajectories do not exist")
    if not external_complete:
        reasons.append("complete-trajectory IK/collision/Solar/SAFE-00 gates remain UNKNOWN")
    if not evaluator.integrity_ok:
        reasons.append("frozen exact-input integrity is not closed")
    reasons.append("150 kg anchor correctly requires ABORT/RECOVERY, not successful capture")
    gate = {
        "schema": "B601_HARNESS_MISSION_COVERAGE_GATE_V1",
        "generated_local": now_local(),
        "authority": "ODR-39",
        "source_bindings": {
            "probe": {"path": rel(PROBE_RESULT), "captured_sha256": sha256(PROBE_RESULT)},
            "trajectory_contract": {"path": rel(MISSION_CONTRACT), "captured_sha256": sha256(MISSION_CONTRACT)},
            "pose_rebind": {"path": rel(POSE_REBIND), "captured_sha256": sha256(POSE_REBIND)},
            "accepted_urdf": {"path": rel(URDF), "expected_sha256": "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164", "actual_sha256": sha256(URDF), "match": sha256(URDF) == "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"},
        },
        "required_states": required,
        "key_state_checks": key_checks,
        "required_trajectory_segments": len(segments),
        "trajectory_segments_with_released_authority": released_segments,
        "trajectory_segments_unknown": sum(item["status"] == "UNKNOWN" for item in segments),
        "external_trajectory_gates": external_gates,
        "harness_gate": "PASS" if key_states_complete else "FAIL_AT_MANDATORY_KEY_STATES",
        "empty_comparison_sets": sum(int(item.get("empty_comparison_sets") or 0) for item in key_checks),
        "derivation": {
            "key_states_complete": key_states_complete,
            "trajectory_authority_complete": trajectory_complete,
            "external_trajectory_gates_complete": external_complete,
            "pose_rebind_loadable": pose_rebind["all_named_q_vectors_loadable"],
            "frozen_input_integrity": evaluator.integrity_ok,
            "mission_pass_rule": "logical AND of the five booleans above",
        },
        "mission_coverage": "PASS" if mission_pass else "FAIL",
        "route_b": "RELEASE_CANDIDATE" if mission_pass else "REJECTED",
        "route_c_escalation": "NOT_TRIGGERED" if mission_pass else "TRIGGERED",
        "decision_reasons": reasons,
        "next_stage_authorized": False,
    }
    write_json(MISSION_GATE, gate)
    return contract, gate, pose_rebind


def mass_artifacts(evaluator):
    pose_doc = yaml.safe_load(POSES.read_text(encoding="utf-8"))["poses"]
    pre = yaml.safe_load(CONTROL.read_text(encoding="utf-8"))["trajectories"]["T2"]["q_initial_rad"]
    q_map = {
        "C01": pose_doc["Q_DEPLOYED_HOME"]["q_rad"],
        "C02": pose_doc["Q_DEPLOYED_HOME"]["q_rad"],
        "C03": pose_doc["Q_DEPLOYED_HOME"]["q_rad"],
        "C04": pose_doc["Q_DEPLOYED_HOME"]["q_rad"],
        "C05": pose_doc["Q_STOW_ENGINEERING_CANDIDATE"]["q_rad"],
        "C06": pose_doc["Q_SERVICE_READY"]["q_rad"],
        "C07": pre,
        "C08": pre,
        "C09": pre,
    }
    design = evaluator.context["design"]
    per_config = {}
    propagation = {}
    for cid, q in q_map.items():
        points, analytic_length_mm, _, _, _ = design.build(q)
        arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])
        clamp_positions = []
        for target in np.linspace(0.0, arc[-1], NOMINAL_MASS_INPUTS["clamp_count"]):
            index = int(np.argmin(np.abs(arc - target)))
            clamp_positions.append(points[index])
        propagated = hu.propagate_harness(
            points_mm=points,
            analytic_length_mm=float(analytic_length_mm),
            coil_center_mm=np.asarray(design.coil_center_S, dtype=float),
            clamp_positions_mm=np.asarray(clamp_positions, dtype=float),
            n=8192,
            seed=hu.DEFAULT_SEED,
        )
        nominal = propagated["nominal"]
        per_config[cid] = {
            "mass_kg": nominal["mass_kg"],
            "cg_S_m": nominal["cg_S_m"],
            "inertia_about_own_cg_S_kg_m2": nominal["inertia_about_own_cg_S_kg_m2"],
            "inertia_components_kg_m2": nominal["inertia_components_kg_m2"],
            "geometric_path_length_mm": float(analytic_length_mm),
            "unplaced_slack_length_modelled_at_joint1_coil_mm": nominal["nominal_cut_length_surplus_m"] * 1000.0,
            "model_closure_error_kg": nominal["mass_kg"] - TOTAL_MASS_KG,
            "uncertainty": propagated["uncertainty_receipt"],
        }
        propagation[cid] = propagated

    first_receipt = propagation["C01"]["uncertainty_receipt"]
    mass_u = first_receipt["standard_uncertainty"]["mass_kg"]
    input_model = first_receipt["input_model"]
    mass_doc = {
        "schema": "B601_HARNESS_MASS_PROPERTIES_V1",
        "generated_local": now_local(),
        "authority": "ODR-40",
        "status": "PROVISIONAL_DESIGN_MASS_PROXY__NOT_FLIGHT_OR_AS_BUILT",
        "measurement_model": "m = L_cut*(24*m_wire_per_m + m_sleeve_per_m) + 2*m_connector + 18*m_clamp + 2*m_strain_relief",
        "conditional_scope": "24-wire candidate architecture; vendor selection and as-built route remain HOLD",
        "inputs": {
            "cut_length_m": {"value": CUT_LENGTH_M, "standard_uncertainty": 0.003, "distribution": "normal", "unit": "m", "source": rel(V2) + "#/design/cut_length_mm", "authority": "R2_HRN_05_DERIVED_CANDIDATE"},
            "wire_count": {"value": 24, "unit": "count", "standard_uncertainty": 0.0, "distribution": "deterministic_conditional", "source": "ODR40_CONDITIONAL_24_WIRE_CANDIDATE_ARCHITECTURE", "authority": "PROVISIONAL_ELECTRICAL_ARCHITECTURE_ASSUMPTION"},
            "single_wire_linear_mass_kg_per_m": {"value": NOMINAL_MASS_INPUTS["single_wire_linear_mass_kg_per_m"], "bounds": NOMINAL_MASS_INPUTS["single_wire_linear_mass_bounds_kg_per_m"], "distribution": "uniform", "unit": "kg/m", "source": "TE 55/9952-22-1(LAT3) official product page", "authority": "VENDOR_PROXY_NOT_SELECTED__PLUS_10_PERCENT_TYPE_B_DESIGN_RANGE"},
            "sleeve_braid_linear_mass_kg_per_m": {"value": NOMINAL_MASS_INPUTS["sleeve_linear_mass_kg_per_m"], "bounds": NOMINAL_MASS_INPUTS["sleeve_linear_mass_bounds_kg_per_m"], "distribution": "uniform", "unit": "kg/m", "source": "ODR40_TYPE_B_DESIGN_CLASS_RANGE", "authority": "DESIGN_CLASS_ASSUMPTION"},
            "connector_mass_kg_each": {"value": NOMINAL_MASS_INPUTS["connector_mass_kg_each"], "bounds": NOMINAL_MASS_INPUTS["connector_mass_bounds_kg_each"], "distribution": "uniform", "unit": "kg", "source": "ODR40_TYPE_B_DESIGN_CLASS_RANGE", "authority": "DESIGN_CLASS_ASSUMPTION"},
            "clamp_mass_kg_each": {"value": NOMINAL_MASS_INPUTS["clamp_mass_kg_each"], "bounds": NOMINAL_MASS_INPUTS["clamp_mass_bounds_kg_each"], "distribution": "uniform", "unit": "kg", "source": "ODR40_TYPE_B_DESIGN_CLASS_RANGE", "authority": "DESIGN_CLASS_ASSUMPTION"},
            "strain_relief_mass_kg_each": {"value": NOMINAL_MASS_INPUTS["strain_relief_mass_kg_each"], "bounds": NOMINAL_MASS_INPUTS["strain_relief_mass_bounds_kg_each"], "distribution": "uniform", "unit": "kg", "source": "ODR40_TYPE_B_DESIGN_CLASS_RANGE", "authority": "DESIGN_CLASS_ASSUMPTION"},
        },
        "total_mass_kg": TOTAL_MASS_KG,
        "standard_uncertainty_kg": mass_u,
        "expanded_uncertainty_kg_k2": 2.0 * mass_u,
        "uncertainty_statement": "expanded design-model uncertainty, k=2; not a statistical 95% hardware confidence interval",
        "propagation_software": {"path": rel(UNCERTAINTY_SOURCE), "sha256": sha256(UNCERTAINTY_SOURCE)},
        "uncertainty_model": {
            "method": first_receipt["method"],
            "input_order": input_model["input_order"],
            "input_correlation_matrix": input_model["correlation_matrix"],
            "input_distributions": input_model["distributions"],
            "input_specifications": input_model["specifications"],
            "deterministic_exact_inputs": input_model["deterministic_exact_inputs"],
            "repeated_part_correlation": "FULLY_CORRELATED_WITHIN_EACH_PART_CLASS",
            "between_input_categories": "INDEPENDENT",
            "sample_count": first_receipt["N"],
            "seed": first_receipt["seed"],
            "degrees_of_freedom": "infinite_assumed_for_type_B_model",
        },
        "pose_dependent_properties": per_config,
        "slack_location_policy": "cut-length surplus is placed at the joint1 coil center for the nominal overlay; 30 mm/axis CG model uncertainty is retained because no physical slack guide is released",
        "accepted_urdf_inertials_modified": False,
        "release_effect": "candidate overlay only because Route B is rejected",
    }
    write_yaml(MASS, mass_doc)

    old = yaml.safe_load(OLD_MASS.read_text(encoding="utf-8"))
    updated = []
    for index, cfg in enumerate(old["configurations"]):
        cid = cfg["configuration_id"]
        system = hu.propagate_system(
            cfg,
            propagation[cid]["nominal"],
            propagation[cid]["samples"],
            seed=hu.DEFAULT_SEED + 100 + index,
            source_path=f"{rel(OLD_MASS)}#/configurations/{index}",
        )
        nominal = system["nominal"]
        receipt = system["uncertainty_receipt"]
        inertia = np.asarray(nominal["inertia_about_system_cg_S_kg_m2"], dtype=float)
        eigvals, eigvecs = np.linalg.eigh(inertia)
        std = receipt["standard_uncertainty"]
        updated.append({
            "configuration_id": cid,
            "name": cfg["name"],
            "mass": {"value_kg": nominal["mass_kg"], "standard_uncertainty_kg": std["mass_kg"], "expanded_uncertainty_kg_k2": receipt["expanded_uncertainty_k2"]["mass_kg"], "authority": "DESIGN_MODEL_R2_PLUS_REJECTED_ROUTE_B_HARNESS_CANDIDATE"},
            "center_of_mass": {"xyz_m": nominal["cg_S_m"], "standard_uncertainty_xyz_m": [std["cg_x_m"], std["cg_y_m"], std["cg_z_m"]], "reference_frame": "S"},
            "inertia": {"components_kg_m2": nominal["inertia_components_kg_m2"], "standard_uncertainty_components_kg_m2": {name: std[f"{name}_kg_m2"] for name in ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")}, "reference_frame": "S", "reference_point": "system_center_of_mass"},
            "principal_moments_kg_m2": eigvals.tolist(),
            "standard_uncertainty_principal_moments_kg_m2": [std[f"principal_moment_{i}_kg_m2"] for i in (1, 2, 3)],
            "principal_axes_columns_S": eigvecs.tolist(),
            "uncertainty": receipt,
            "checks": {
                "nominal_positive_definite": bool(np.all(eigvals > 0)),
                "nominal_triangle_inequalities": bool(eigvals[0] + eigvals[1] >= eigvals[2] - 1e-12),
                "nominal_mass_addend_matches": abs(nominal["mass_kg"] - float(cfg["mass"]["value_kg"]) - TOTAL_MASS_KG) < 1e-9,
            },
        })
    overlay = {
        "schema": "SYSTEM_DESIGN_MASS_PROPERTIES_V4_HARNESS_CANDIDATE",
        "generated_local": now_local(),
        "status": "DIAGNOSTIC_OVERLAY_NOT_CURRENT_SSOT_ROUTE_B_REJECTED",
        "supersedes": None,
        "base_source": {"path": rel(OLD_MASS), "sha256": sha256(OLD_MASS)},
        "harness_source": {"path": rel(MASS), "sha256": sha256(MASS)},
        "accepted_urdf_inertials_modified": False,
        "uncertainty_policy": "base covariance absent -> independent normal design quantities; harness row-wise covariance preserved; see each configuration receipt",
        "configurations": updated,
    }
    write_yaml(MASS_OVERLAY, overlay)
    return mass_doc, overlay


def torque_artifact():
    doc = {
        "schema": "B601_HARNESS_JOINT_TORQUE_ENVELOPE_V1",
        "generated_local": now_local(),
        "authority": "ODR-40",
        "model_form": "tau_harness_i(q,dq) = k_i*(q_i-q_ref_i) + tau_c_i*tanh(dq_i/epsilon_i) + c_i*dq_i",
        "units": {"torque": "N*m", "stiffness": "N*m/rad", "damping": "N*m*s/rad", "q": "rad", "dq": "rad/s"},
        "parameters": {
            f"joint{i}": {"k_Nm_per_rad": None, "c_Nm_s_per_rad": None, "coulomb_Nm": None, "status": "HOLD_NO_BUNDLE_STIFFNESS_FRICTION_RATE_TEST"}
            for i in range(1, 7)
        },
        "provisional_actuator_capacity_source": rel(CONTROL),
        "capacity_Nm": [12.0, 12.0, 10.0, 6.0, 4.0, 3.0],
        "capacity_margin_Nm": [None] * 6,
        "dynamic_effect": "UNKNOWN_FAIL_CLOSED",
        "negligible_claim": "FORBIDDEN_WITHOUT_EVIDENCE",
        "required_test": "instrumented joint-by-joint quasi-static and rate sweep of the released dress pack over the rated envelope, including thermal extremes",
        "verdict": "HOLD",
    }
    write_yaml(TORQUE, doc)
    return doc


def urdf_frame_tree_receipt():
    root = ET.parse(URDF).getroot()
    links = {item.attrib["name"] for item in root.findall("link")}
    joints = root.findall("joint")
    edges = []
    children = set()
    adjacency = {name: [] for name in links}
    for joint in joints:
        parent = joint.find("parent").attrib["link"]
        child = joint.find("child").attrib["link"]
        edges.append({"joint": joint.attrib["name"], "parent": parent, "child": child})
        children.add(child)
        adjacency.setdefault(parent, []).append(child)
    roots = sorted(links - children)
    visited = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, []))
    one_parent = len(children) == len(edges)
    acyclic_connected = len(roots) == 1 and visited == links and len(edges) == len(links) - 1
    pose_doc = yaml.safe_load(POSES.read_text(encoding="utf-8"))
    mount = np.asarray(pose_doc["mount"]["transform_mm_rows"], dtype=float)
    mount_valid = bool(
        mount.shape == (4, 4) and np.all(np.isfinite(mount))
        and np.allclose(mount[3], [0.0, 0.0, 0.0, 1.0], rtol=0.0, atol=1e-12)
    )
    return {
        "pass": bool(one_parent and acyclic_connected and mount_valid and "gripper_link" in visited),
        "root_links": roots,
        "links": len(links),
        "edges": len(edges),
        "one_parent_per_nonroot": one_parent,
        "acyclic_connected": acyclic_connected,
        "gripper_reachable": "gripper_link" in visited,
        "mount_transform_valid": mount_valid,
    }


def grasp_frame_receipt():
    old = yaml.safe_load(OLD_CONTRACT.read_text(encoding="utf-8"))
    frames = old.get("grasp", {}).get("frames", {})
    root = ET.parse(URDF).getroot()
    links = {item.attrib["name"] for item in root.findall("link")}
    gripper_joint = next((j for j in root.findall("joint") if j.find("child").attrib["link"] == "gripper_link"), None)
    expected = frames.get("grasp_frame", {})
    if gripper_joint is None:
        return {"pass": False, "reason": "GRIPPER_JOINT_MISSING"}
    xyz = [float(v) for v in gripper_joint.find("origin").attrib["xyz"].split()]
    rpy = [float(v) for v in gripper_joint.find("origin").attrib["rpy"].split()]
    match = bool(
        expected.get("parent") == gripper_joint.find("parent").attrib["link"]
        and np.allclose(xyz, expected.get("origin_xyz_m", []), rtol=0.0, atol=1e-12)
        and np.allclose(rpy, expected.get("origin_rpy_rad", []), rtol=0.0, atol=1e-12)
        and frames.get("contact_left", {}).get("definition") == "gripper_left link frame"
        and frames.get("contact_right", {}).get("definition") == "gripper_right link frame"
        and {"gripper_link", "gripper_left", "gripper_right"}.issubset(links)
    )
    return {
        "pass": match,
        "historical_contract_path": rel(OLD_CONTRACT),
        "historical_contract_sha256": sha256(OLD_CONTRACT),
        "urdf_joint": gripper_joint.attrib["name"],
        "parent": gripper_joint.find("parent").attrib["link"],
        "origin_xyz_m": xyz,
        "origin_rpy_rad": rpy,
        "contact_patch_authority": "HOLD_RETAINED_NOT_A_LOADABILITY_FAILURE",
    }


def uncertainty_receipt_complete(mass_doc, overlay):
    required_outputs = ["mass_kg", "cg_x_m", "cg_y_m", "cg_z_m", "Ixx_kg_m2", "Iyy_kg_m2", "Izz_kg_m2", "Ixy_kg_m2", "Ixz_kg_m2", "Iyz_kg_m2"]
    expected_exact = {
        "wire_count": 24,
        "connector_count": 2,
        "clamp_count": 18,
        "strain_relief_count": 2,
    }

    def stochastic_specs_complete(specifications):
        return bool(
            len(specifications) == 12
            and all(
                item.get("source")
                and item.get("authority")
                and item.get("distribution")
                and item.get("degrees_of_freedom")
                and item.get("standard_uncertainty") is not None
                and math.isfinite(float(item["standard_uncertainty"]))
                and float(item["standard_uncertainty"]) >= 0.0
                for item in specifications
            )
        )

    def exact_inputs_complete(items):
        by_name = {item.get("name"): item for item in items}
        return bool(
            set(by_name) == set(expected_exact)
            and all(
                by_name[name].get("value") == value
                and by_name[name].get("unit") == "count"
                and by_name[name].get("standard_uncertainty") == 0.0
                and by_name[name].get("distribution") == "exact"
                and by_name[name].get("degrees_of_freedom")
                and by_name[name].get("source")
                and by_name[name].get("authority")
                and by_name[name].get("correlation_semantics")
                for name, value in expected_exact.items()
            )
        )

    model = mass_doc.get("uncertainty_model", {})
    model_specs = model.get("input_specifications", [])
    model_exact = model.get("deterministic_exact_inputs", [])
    inputs_ok = bool(
        len(model.get("input_order", [])) == 12
        and len(model.get("input_correlation_matrix", [])) == len(model.get("input_order", []))
        and model.get("repeated_part_correlation") == "FULLY_CORRELATED_WITHIN_EACH_PART_CLASS"
        and stochastic_specs_complete(model_specs)
        and exact_inputs_complete(model_exact)
    )
    pose_details = []
    for cid, item in mass_doc.get("pose_dependent_properties", {}).items():
        u = item.get("uncertainty", {})
        order = u.get("output_order", [])
        standard = u.get("standard_uncertainty", {})
        standard_values = [standard.get(key) for key in required_outputs] if isinstance(standard, dict) else list(standard)
        physical = u.get("physical_domain_checks", {})
        n_samples = u.get("sampling", {}).get("n", 0)
        input_model = u.get("input_model", {})
        physical_ok = bool(
            physical.get("sample_count") == n_samples
            and physical.get("positive_mass_pass_count") == n_samples
            and physical.get("positive_definite_pass_count") == n_samples
            and physical.get("triangle_inequality_pass_count") == n_samples
            and physical.get("positive_mass_pass_rate") == 1.0
            and physical.get("positive_definite_pass_rate") == 1.0
            and physical.get("triangle_inequality_pass_rate") == 1.0
            and physical.get("all_samples_in_physical_domain") is True
        )
        ok = bool(
            order == required_outputs and len(standard_values) == 10
            and all(value is not None and math.isfinite(float(value)) and float(value) >= 0.0 for value in standard_values)
            and len(u.get("output_correlation_matrix", [])) == 10
            and u.get("sampling", {}).get("n", 0) >= 4096
            and u.get("sampling", {}).get("seed") is not None
            and stochastic_specs_complete(input_model.get("specifications", []))
            and exact_inputs_complete(input_model.get("deterministic_exact_inputs", []))
            and physical_ok
        )
        pose_details.append({"configuration_id": cid, "complete": ok, "physical_domain": physical})
    overlay_details = []
    for item in overlay.get("configurations", []):
        u = item.get("uncertainty", {})
        standard = u.get("standard_uncertainty", {})
        values = [standard.get(key) for key in required_outputs] if isinstance(standard, dict) else list(standard)
        physical = u.get("physical_domain_checks", {})
        n_samples = u.get("sampling", {}).get("n", 0)
        base_inputs = u.get("base_inputs", [])
        rejection = u.get("base_rejection_sampling", {})
        physical_ok = bool(
            physical.get("sample_count") == n_samples
            and physical.get("positive_mass_pass_count") == n_samples
            and physical.get("positive_definite_pass_count") == n_samples
            and physical.get("triangle_inequality_pass_count") == n_samples
            and physical.get("positive_mass_pass_rate") == 1.0
            and physical.get("positive_definite_pass_rate") == 1.0
            and physical.get("triangle_inequality_pass_rate") == 1.0
            and physical.get("all_samples_in_physical_domain") is True
        )
        base_inputs_ok = bool(
            len(base_inputs) == 10
            and all(
                entry.get("source")
                and entry.get("authority")
                and entry.get("distribution")
                and entry.get("degrees_of_freedom")
                and entry.get("target_standard_uncertainty") is not None
                and entry.get("realized_standard_uncertainty_after_truncation") is not None
                for entry in base_inputs
            )
        )
        rejection_ok = bool(
            rejection.get("policy") == "TRUNCATED_NORMAL_REJECTION_TO_PHYSICAL_MASS_PROPERTY_DOMAIN"
            and rejection.get("accepted") == n_samples
            and rejection.get("total_draws", 0) >= n_samples
            and rejection.get("accepted_sample_physical_domain_checks", {}).get("all_samples_in_physical_domain") is True
        )
        ok = bool(
            u.get("output_order", [])[:10] == required_outputs and len(values) == 10
            and all(value is not None and math.isfinite(float(value)) and float(value) >= 0.0 for value in values)
            and len(u.get("output_correlation_matrix", [])) == len(u.get("output_order", []))
            and u.get("sampling", {}).get("n", 0) >= 4096
            and u.get("sampling", {}).get("seed") is not None
            and base_inputs_ok
            and rejection_ok
            and physical_ok
        )
        overlay_details.append({"configuration_id": item.get("configuration_id"), "complete": ok, "physical_domain": physical})
    complete = bool(inputs_ok and len(pose_details) == 9 and all(x["complete"] for x in pose_details)
                    and len(overlay_details) == 9 and all(x["complete"] for x in overlay_details))
    return {"pass": complete, "input_model_complete": inputs_ok, "pose_outputs": pose_details, "system_overlay_outputs": overlay_details}


def contract_and_gates(map_counts, refinements, mission_gate, torque_doc, evaluator, pose_rebind, mass_doc, overlay):
    product_sha = sha256(PRODUCT)
    env_sha = sha256(ENV_YAML)
    map_csv_sha = sha256(ENV_CSV)
    map_npz_sha = sha256(ENV_NPZ)
    mission_sha = sha256(MISSION_GATE)
    mass_sha = sha256(MASS)
    torque_sha = sha256(TORQUE)
    contract = {
        "schema": "EMBODIED_MECHANICAL_CONTRACT_R3_HARNESS_CANDIDATE",
        "generated_local": now_local(),
        "status": "CANDIDATE_NOT_RELEASED_ROUTE_B_REJECTED" if mission_gate["route_b"] == "REJECTED" else "CANDIDATE_PENDING_ALL_TERMINAL_GATES",
        "supersedes": None,
        "accepted_urdf": {"path": rel(URDF), "sha256": sha256(URDF), "hardware_joint_limits_unchanged": True},
        "frozen_input_integrity": {
            "pin_file": {"path": rel(PIN_FILE), "sha256": sha256(PIN_FILE)},
            "runtime_receipt": evaluator.integrity_receipt,
            "mismatch_policy": {"classification": "UNKNOWN", "action": "ABORT"},
        },
        "harness": {
            "architecture": {"type": "EXTERNAL_FIXED_DRESS_PACK_WITH_RATED_ENVELOPE", "product_definition": {"path": rel(PRODUCT), "sha256": product_sha}},
            "full_hardware_envelope": {"status": "NOT_RELEASED", "negative_result": {"path": rel(V2), "sha256": sha256(V2)}},
            "rated_envelope": {"status": "NOT_RELEASED_EMPTY_OBSERVED_SAFE_SET", "asset": {"path": rel(ENV_YAML), "sha256": env_sha}, "map_csv_sha256": map_csv_sha, "map_npz_sha256": map_npz_sha},
            "exact_validator": {"path": rel(EXACT_SOURCE), "sha256": sha256(EXACT_SOURCE), "authority": "FINAL_GEOMETRY_PREDICATE"},
            "constraints": {"clearance": ">= 0 mm", "bend_radius": f">= {REQUIRED_BEND_MM} mm", "pinch": ">= 0 mm", "length": ">= 0 mm"},
            "mission_coverage": {"path": rel(MISSION_GATE), "sha256": mission_sha, "verdict": mission_gate["mission_coverage"]},
            "pose_authority_rebind": {"path": rel(POSE_REBIND), "sha256": sha256(POSE_REBIND), "status": pose_rebind["rebind_status"]},
            "mass_properties": {"path": rel(MASS), "sha256": mass_sha, "authority": "PROVISIONAL_CANDIDATE_WITH_PROPAGATED_TYPE_B_UNCERTAINTY"},
            "joint_torque": {"path": rel(TORQUE), "sha256": torque_sha, "verdict": torque_doc["verdict"]},
            "planner_policy": {"trajectory_validation_required": True, "endpoint_only_validation_forbidden": True},
            "fail_closed": {"UNKNOWN": "ABORT", "UNSAFE": "ABORT"},
        },
        "failure_states": [
            "HARDWARE_JOINT_LIMIT", "COLLISION_LIMIT", "SOLAR_KEEPOUT_VIOLATION",
            "HARNESS_ENVELOPE_VIOLATION", "MISSION_LIMIT", "CONTROL_LIMIT",
        ],
        "rl_action_mask": "IK AND collision AND joint AND solar AND harness AND SAFE_00",
        "physical_contact": "HOLD",
        "physics_gated_RL": "HOLD",
        "production_dynamics": "HOLD",
        "next_stage_authorized": False,
    }
    write_yaml(CONTRACT, contract)

    captured_bindings = [
        (PRODUCT, product_sha), (PRED_CONTRACT, sha256(PRED_CONTRACT)),
        (ENV_YAML, env_sha), (ENV_CSV, map_csv_sha), (ENV_NPZ, map_npz_sha),
        (POSE_REBIND, sha256(POSE_REBIND)), (MISSION_CONTRACT, sha256(MISSION_CONTRACT)),
        (MISSION_GATE, mission_sha), (MASS, mass_sha), (MASS_OVERLAY, sha256(MASS_OVERLAY)),
        (TORQUE, torque_sha), (CONTRACT, sha256(CONTRACT)),
    ]
    hashes = []
    for path, expected in captured_bindings:
        actual = sha256(path) if path.is_file() else None
        hashes.append({"path": rel(path), "expected_sha256": expected, "actual_sha256": actual,
                       "bytes": path.stat().st_size if path.is_file() else None, "match": actual == expected})
    root = ET.parse(URDF).getroot()
    links = root.findall("link")
    joints = root.findall("joint")
    types = [j.attrib.get("type") for j in joints]
    frame_tree = urdf_frame_tree_receipt()
    probe = json.loads(PROBE_RESULT.read_text(encoding="utf-8"))
    pose_loadable = bool(
        pose_rebind["rebind_status"] == "PASS_CURRENT_URDF_LOADABILITY_SCOPE"
        and pose_rebind["legacy_pose_source"]["hash_match"]
        and probe["states_unknown"] == 0
        and probe["frozen_input_integrity"]["integrity_ok"]
    )
    grasp_receipt = grasp_frame_receipt()
    uncertainty_receipt = uncertainty_receipt_complete(mass_doc, overlay)
    mesh_checks = [item for item in evaluator.integrity_receipt["checks"] if item["path"].lower().endswith(".stl")]
    collision_assets_ok = len(mesh_checks) == 10 and all(item["match"] for item in mesh_checks)
    g12_terms = {
        "mission_coverage_pass": mission_gate["mission_coverage"] == "PASS",
        "map_contains_safe_sample": map_counts["SAFE"] > 0,
        "exact_validator_exists": EXACT_SOURCE.is_file(),
        "runtime_frozen_input_integrity": evaluator.integrity_ok,
        "unknown_fail_closed": contract["harness"]["fail_closed"].get("UNKNOWN") == "ABORT",
        "rl_action_mask_binds_harness": "harness" in contract["rl_action_mask"].lower(),
    }
    checks = [
        {"id": "G01", "name": "FROZEN_INPUT_AND_CAPTURED_ASSET_HASHES_MATCH", "pass": evaluator.integrity_ok and all(x["match"] for x in hashes), "derivation": "runtime pin receipt AND every captured expected_sha256 == independent actual_sha256", "evidence": {"frozen_input_receipt": evaluator.integrity_receipt, "captured_assets": hashes}},
        {"id": "G02", "name": "FRAME_TREE_DEFINED", "pass": frame_tree["pass"], "derivation": "parsed URDF graph is a connected rooted tree and S->M mount matrix is finite 4x4", "evidence": frame_tree},
        {"id": "G03", "name": "URDF_TOPOLOGY_MATCHED", "pass": len(links) == 10 and len(joints) == 9 and types.count("revolute") == 6, "evidence": {"links": len(links), "joints": len(joints), "revolute": types.count("revolute")}},
        {"id": "G04", "name": "DESIGN_MASS_MODEL_LOADABLE", "pass": len(overlay["configurations"]) == 9 and all(item["checks"]["nominal_positive_definite"] and item["checks"]["nominal_triangle_inequalities"] for item in overlay["configurations"]), "derivation": "nine parsed configurations and every explicitly nominal inertia physicality check", "evidence": {"path": rel(MASS_OVERLAY), "configurations": len(overlay["configurations"])}},
        {"id": "G05", "name": "COLLISION_ASSETS_LOADABLE", "pass": collision_assets_ok, "derivation": "ten expected STL hashes from pinned V2 transitive manifest match live files", "evidence": mesh_checks},
        {"id": "G06", "name": "ACCEPTED_CONFIGURATIONS_LOADABLE", "pass": pose_loadable, "derivation": "legacy source hash matches + current-URDF rebind loadable + hash-guarded probe has zero UNKNOWN", "evidence": {"pose_rebind": pose_rebind, "probe_states_total": probe["states_total"], "probe_unknown": probe["states_unknown"]}},
        {"id": "G07", "name": "FAILURE_STATES_ENUMERABLE", "pass": "HARNESS_ENVELOPE_VIOLATION" in contract["failure_states"], "evidence": contract["failure_states"]},
        {"id": "G08", "name": "GRASP_FRAMES_DEFINED", "pass": grasp_receipt["pass"], "derivation": "historical hash-pinned grasp-frame values match current URDF gripper joint and contact links", "evidence": grasp_receipt},
        {"id": "G09", "name": "FLEX_INTERFACE_LOADABLE", "pass": bool(yaml.safe_load(FLEX.read_text(encoding="utf-8"))) and any(item["name"] == "flexible_interface" and item["match"] for item in evaluator.integrity_receipt["checks"]), "derivation": "YAML parses and frozen expected hash matches live file", "evidence": {"path": rel(FLEX), "sha256": sha256(FLEX)}},
        {"id": "G10", "name": "UNCERTAINTY_FIELDS_MACHINE_READABLE", "pass": uncertainty_receipt["pass"] and torque_doc["dynamic_effect"] == "UNKNOWN_FAIL_CLOSED", "derivation": "mass/CG/6-inertia uncertainty receipts complete for harness and nine system configurations; absent torque parameters remain UNKNOWN", "evidence": {"mass_and_inertia": uncertainty_receipt, "torque_unknown_preserved": torque_doc["dynamic_effect"] == "UNKNOWN_FAIL_CLOSED"}},
        {"id": "G11", "name": "UNKNOWN_REMAINS_FAIL_CLOSED", "pass": contract["harness"]["fail_closed"]["UNKNOWN"] == "ABORT", "evidence": contract["harness"]["fail_closed"]},
        {"id": "G12", "name": "HARNESS_RATED_OPERATIONAL_ENVELOPE", "pass": all(g12_terms.values()), "derivation": "logical AND of machine-derived G12 terms", "evidence": {"terms": g12_terms, "mission_coverage": mission_gate["mission_coverage"], "map_counts": map_counts, "adaptive_refinements": refinements}},
    ]
    all_handoff_pass = all(item["pass"] for item in checks)
    handoff = {
        "schema": "MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2",
        "generated_local": now_local(),
        "authority": "ODR-41",
        "historical_gate_preserved": rel(OLD_HANDOFF),
        "contract_under_test": {"path": rel(CONTRACT), "sha256": sha256(CONTRACT)},
        "checks": checks,
        "checks_total": 12,
        "checks_passed": sum(c["pass"] for c in checks),
        "checks_failed": sum(not c["pass"] for c in checks),
        "failing_checks": [c["id"] for c in checks if not c["pass"]],
        "verdict": "MECHANICAL_TO_EMBODIED_HANDOFF_PASS" if all_handoff_pass else "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
    }
    write_json(HANDOFF, handoff)

    check_by_id = {item["id"]: item for item in checks}
    physical_mc_ok = all(
        item.get("physical_domain", {}).get("all_samples_in_physical_domain") is True
        and item.get("physical_domain", {}).get("positive_mass_pass_rate") == 1.0
        and item.get("physical_domain", {}).get("positive_definite_pass_rate") == 1.0
        and item.get("physical_domain", {}).get("triangle_inequality_pass_rate") == 1.0
        for item in uncertainty_receipt["pose_outputs"] + uncertainty_receipt["system_overlay_outputs"]
    )
    attacks = [
        {"id": "RT-H01", "attack": "overwrite accepted URDF limits", "result": "REJECTED_BY_FROZEN_RUNTIME_HASH_GUARD" if evaluator.integrity_ok else "OPEN_HASH_GUARD_FAILURE", "severity_if_uncontrolled": "HIGH", "open": not evaluator.integrity_ok},
        {"id": "RT-H02", "attack": "delete failing mission cases", "result": "REJECTED_BY_EXACT_10_STATE_AND_8_SEGMENT_MANIFEST" if len(mission_gate["required_states"]) == 10 and mission_gate["required_trajectory_segments"] == 8 else "OPEN_MISSION_MANIFEST_INCOMPLETE", "severity_if_uncontrolled": "HIGH", "open": not (len(mission_gate["required_states"]) == 10 and mission_gate["required_trajectory_segments"] == 8)},
        {"id": "RT-H03", "attack": "map interpolation authorizes unsampled state", "result": "REJECTED_EXACT_PREDICATE_REMAINS_AUTHORITY", "severity_if_uncontrolled": "HIGH", "open": contract["harness"]["planner_policy"].get("endpoint_only_validation_forbidden") is not True},
        {"id": "RT-H04", "attack": "UNKNOWN becomes ALLOW", "result": "NEGATIVE_CONTROL_REJECTED", "severity_if_uncontrolled": "HIGH", "open": contract["harness"]["fail_closed"] != {"UNKNOWN": "ABORT", "UNSAFE": "ABORT"}},
        {"id": "RT-H05", "attack": "reuse stale historical handoff", "result": "HISTORICAL_GATE_PRESERVED_BUT_NOT_ACCEPTED", "severity_if_uncontrolled": "HIGH", "open": handoff["historical_gate_preserved"] != rel(OLD_HANDOFF)},
        {"id": "RT-H06", "attack": "treat 403.48 mm take-up as cut-length reserve", "result": "SEMANTIC_CORRECTION_RECORDED", "severity_if_uncontrolled": "MEDIUM", "open": False},
        {"id": "RT-H07", "attack": "claim torque negligible with null stiffness", "result": "FORBIDDEN_DYNAMIC_EFFECT_UNKNOWN", "severity_if_uncontrolled": "HIGH", "open": torque_doc["dynamic_effect"] != "UNKNOWN_FAIL_CLOSED" or torque_doc["negligible_claim"] != "FORBIDDEN_WITHOUT_EVIDENCE"},
        {"id": "RT-H08", "attack": "hard-code handoff booleans instead of deriving them", "result": "CLOSED_BY_FIELD_LEVEL_DERIVATION_RECEIPTS" if all("derivation" in item or item["id"] in ("G03", "G07", "G11") for item in checks) else "OPEN_GATE_DERIVATION_GAP", "severity_if_uncontrolled": "HIGH", "open": not all("derivation" in item or item["id"] in ("G03", "G07", "G11") for item in checks)},
        {"id": "RT-H09", "attack": "accept legacy pose source with stale embedded URDF authority", "result": "CLOSED_BY_NON_MUTATING_CURRENT_URDF_REBIND" if pose_loadable and not pose_rebind["legacy_pose_source"]["embedded_urdf_matches_current"] else ("OPEN_POSE_REBIND_FAILURE" if not pose_loadable else "SOURCE_ALREADY_CURRENT"), "severity_if_uncontrolled": "HIGH", "open": not pose_loadable},
        {"id": "RT-H10", "attack": "declare scalar mass uncertainty without CG/inertia propagation", "result": "CLOSED_BY_10_OUTPUT_RECEIPTS_FOR_HARNESS_AND_NINE_SYSTEM_CONFIGURATIONS" if uncertainty_receipt["pass"] else "OPEN_ODR40_UNCERTAINTY_GAP", "severity_if_uncontrolled": "HIGH", "open": not uncertainty_receipt["pass"]},
        {"id": "RT-H11", "attack": "allow Monte Carlo inertia samples outside the positive-definite physical triangle domain", "result": "CLOSED_ALL_HARNESS_AND_SYSTEM_MC_SAMPLES_PHYSICAL" if physical_mc_ok else "OPEN_NONPHYSICAL_INERTIA_SAMPLES", "severity_if_uncontrolled": "HIGH", "open": not physical_mc_ok},
    ]
    open_counts = {severity: sum(item["open"] and item["severity_if_uncontrolled"] == severity for item in attacks) for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
    red = {
        "schema": "B601_HARNESS_SCOPED_RED_TEAM_V1",
        "generated_local": now_local(),
        "scope": "ODR-35..41 Route-B closure products",
        "attacks": attacks,
        "open_findings": open_counts,
        "verdict": "PASS_FAIL_CLOSED_NEGATIVE_DECISION" if open_counts["HIGH"] == 0 and open_counts["CRITICAL"] == 0 else "FAIL_OPEN_HIGH_FINDINGS",
    }
    write_json(RED_TEAM, red)

    internal_holds = []
    if mission_gate["route_b"] == "REJECTED":
        internal_holds.append("ROUTE_B_KEY_STATES_OR_MISSION_COVERAGE_FAILED")
    if mission_gate["trajectory_segments_with_released_authority"] < mission_gate["required_trajectory_segments"]:
        internal_holds.append("MANDATORY_MISSION_TRAJECTORY_AUTHORITY_INCOMPLETE")
    if torque_doc["verdict"] == "HOLD":
        internal_holds.append("HARNESS_JOINT_RESISTANCE_TORQUE_UNKNOWN")
    if not check_by_id["G10"]["pass"]:
        internal_holds.append("ODR40_UNCERTAINTY_PROPAGATION_INCOMPLETE")
    if not evaluator.integrity_ok:
        internal_holds.append("FROZEN_INPUT_HASH_INTEGRITY_FAILED")
    if open_counts["HIGH"] > 0 or open_counts["CRITICAL"] > 0:
        internal_holds.append("SCOPED_RED_TEAM_HIGH_OR_CRITICAL_OPEN")
    terminal_release = bool(
        mission_gate["mission_coverage"] == "PASS" and all_handoff_pass
        and open_counts["HIGH"] == 0 and open_counts["CRITICAL"] == 0
        and len(internal_holds) == 0
    )
    terminal = {
        "schema": "B601_HARNESS_TERMINAL_GATE_V1",
        "generated_local": now_local(),
        "authority": "ODR-41",
        "terminal_mechanical_gates": [
            {"id": "TMG-1", "name": "Product", "state": "PASS_WITH_DECLARED_OPEN_ITEM", "note": "frozen tested candidate; vendor hardware unresolved"},
            {"id": "TMG-2", "name": "Mass", "state": "PASS_WITH_PROVISIONAL_SCOPE" if check_by_id["G10"]["pass"] else "HOLD_ODR40_UNCERTAINTY_INCOMPLETE", "note": f"{mass_doc['total_mass_kg']:.3f} kg conditional design proxy with mass/CG/inertia uncertainty propagated to nine configurations; not current SSOT because Route B rejected"},
            {"id": "TMG-3", "name": "Mechanism", "state": "PASS_WITH_PROVISIONAL_COMPONENTS", "note": "M7/Solar R2 evidence unchanged"},
            {"id": "TMG-4", "name": "Harness", "state": "PASS_HARNESS_RATED_OPERATIONAL_ENVELOPE" if mission_gate["mission_coverage"] == "PASS" else "FAIL_ROUTE_B_MANDATORY_STATES_OR_TRAJECTORIES", "note": "never renamed FULL_RANGE_HARNESS_PASS"},
            {"id": "TMG-5", "name": "Flexibility", "state": "PASS_WITH_PROVISIONAL_SCOPE", "note": "M7 Solar R2 interface unchanged"},
            {"id": "TMG-6", "name": "Mechanical-to-Embodied", "state": ("PASS_12_OF_12" if all_handoff_pass else f"FAIL_{handoff['checks_passed']}_OF_12"), "note": "machine-derived check count"},
            {"id": "TMG-7", "name": "Adversarial", "state": "PASS_FAIL_CLOSED_NEGATIVE_DECISION" if open_counts["HIGH"] == 0 and open_counts["CRITICAL"] == 0 else "HOLD_OPEN_HIGH_FINDINGS", "note": f"HIGH open findings = {open_counts['HIGH']}"},
        ],
        "mission_coverage": mission_gate["mission_coverage"],
        "handoff_v2": {"passed": handoff["checks_passed"], "total": 12, "verdict": handoff["verdict"]},
        "scoped_high_findings": open_counts["HIGH"],
        "internal_mechanical_holds": internal_holds,
        "internal_mechanical_hold_count": len(internal_holds),
        "route_b": mission_gate["route_b"],
        "route_c": "TRIGGERED" if mission_gate["route_b"] == "REJECTED" else "NOT_TRIGGERED",
        "mechanical_design": "RELEASED" if terminal_release else "NOT_RELEASED",
        "operational_envelope": "NO_HARNESS_RATED_ENVELOPE_RELEASED",
        "full_urdf_joint_range": "NOT_HARNESS_QUALIFIED",
        "flight_qualification": "HOLD",
        "terminal_release_condition": {
            "mission_coverage_pass": mission_gate["mission_coverage"] == "PASS",
            "handoff_12_of_12": all_handoff_pass,
            "scoped_high_zero": open_counts["HIGH"] == 0,
            "scoped_critical_zero": open_counts["CRITICAL"] == 0,
            "internal_hold_zero": len(internal_holds) == 0,
            "all_met": terminal_release,
        },
        "next_stage_authorized": terminal_release,
        "prohibition": "do not enter production dynamics, physical-contact RL or hardware motion from this gate",
    }
    write_json(TERMINAL, terminal)

    route_c = {
        "schema": "ECR_HARNESS_FULL_RANGE_01",
        "generated_local": now_local(),
        "ecr": "ECR-HARNESS-FULL-RANGE-01",
        "trigger": "ODR-41 Route B rejection",
        "status": "TRIGGERED_PENDING_DETAILED_DESIGN_AUTHORIZATION" if terminal["route_c"] == "TRIGGERED" else "INACTIVE_FUTURE_ECR",
        "selected_candidate_family": "GUIDED_DRESS_PACK_FULL_RANGE",
        "requirements": [
            "preserve accepted URDF and Solar R2",
            "eliminate uncontrolled link-side span cusps and protected-anchor false contacts with physical guides",
            "provide guided moving carriers at j2/j3 fold joints and controlled slack storage at joint1",
            "prove current mission trajectories first, then full hardware range only if required",
            "include mass, restoring torque, abrasion, thermal-vacuum and life-cycle qualification plans",
        ],
        "candidate_concepts": ["semi-captive cable carrier", "joint-local moving guide", "rolling loop guide", "split power/data dress packs"],
        "entry_evidence": {"route_b_terminal_gate": {"path": rel(TERMINAL), "sha256": sha256(TERMINAL)}},
        "next_stage_authorized": False,
    }
    write_yaml(ROUTE_C, route_c)
    return contract, handoff, red, terminal


def output_manifest():
    outputs = [
        PRODUCT, PRED_CONTRACT, PROBE_RESULT, ENV_YAML, ENV_CSV, ENV_NPZ,
        POSE_REBIND, MISSION_CONTRACT, MISSION_GATE, MASS, MASS_OVERLAY, TORQUE, CONTRACT,
        HANDOFF, RED_TEAM, TERMINAL, ROUTE_C,
    ]
    manifest = {
        "schema": "B601_HARNESS_ROUTE_B_OUTPUT_MANIFEST_V1",
        "generated_local": now_local(),
        "files": [{"path": rel(p), "sha256": sha256(p), "bytes": p.stat().st_size} for p in outputs],
        "accepted_urdf": {"path": rel(URDF), "sha256": sha256(URDF), "modified": False},
        "frozen_input_pin_ssot": {"path": rel(PIN_FILE), "sha256": sha256(PIN_FILE)},
        "generator_sources": [
            {"role": "terminal_builder", "path": rel(BUILDER_SOURCE), "sha256": sha256(BUILDER_SOURCE)},
            {"role": "exact_predicate", "path": rel(EXACT_SOURCE), "sha256": sha256(EXACT_SOURCE)},
            {"role": "uncertainty_propagator", "path": rel(UNCERTAINTY_SOURCE), "sha256": sha256(UNCERTAINTY_SOURCE)},
            {"role": "independent_validator", "path": rel(VALIDATOR_SOURCE), "sha256": sha256(VALIDATOR_SOURCE)},
        ],
        "route_b": "REJECTED",
        "route_c": "TRIGGERED",
    }
    write_json(MANIFEST, manifest)
    return manifest


def main():
    ensure_parents()
    write_yaml(PRODUCT, product_definition())
    write_yaml(PRED_CONTRACT, predicate_contract())
    evaluator = load_exact()
    probe = regenerate_key_state_probe(evaluator)
    rows, counts, refinements = map_envelope(evaluator)
    _, mission_gate, pose_rebind = mission_artifacts(evaluator, probe)
    mass_doc, overlay = mass_artifacts(evaluator)
    torque_doc = torque_artifact()
    _, handoff, _, terminal = contract_and_gates(counts, refinements, mission_gate, torque_doc, evaluator, pose_rebind, mass_doc, overlay)
    manifest = output_manifest()
    print(json.dumps({
        "route_b": terminal["route_b"],
        "route_c": terminal["route_c"],
        "map_samples": len(rows),
        "map_counts": counts,
        "handoff": f"{handoff['checks_passed']}/{handoff['checks_total']}",
        "manifest_sha256": sha256(MANIFEST),
        "manifest_files": len(manifest["files"]),
    }, indent=2))


if __name__ == "__main__" or (
    len(__import__("sys").argv) > 1
    and Path(__import__("sys").argv[1]).stem == __name__
):
    main()
