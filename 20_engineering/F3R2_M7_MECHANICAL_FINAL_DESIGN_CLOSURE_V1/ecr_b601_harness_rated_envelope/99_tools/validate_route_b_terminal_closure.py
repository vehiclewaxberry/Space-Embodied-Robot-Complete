# -*- coding: utf-8 -*-
"""Independent, deterministic audit of the Route-B terminal evidence package.

This validator never regenerates design evidence.  It only re-loads the
released inputs and candidate outputs, recomputes arithmetic/hash invariants,
and checks that every unsafe or unknown result remains fail-closed.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import yaml


HERE = Path(__file__).resolve().parent
PKG = HERE.parent
M7 = PKG.parent
PROJECT = M7.parents[1]
REPORT = PKG / "07_release" / "B601_HARNESS_TERMINAL_INDEPENDENT_VALIDATION_V1.json"
PIN_FILE = PKG / "00_authority/ROUTE_B_FROZEN_INPUT_PINS_V1.yaml"
EXACT_SOURCE = PKG / "02_exact_predicate/harness_exact_check.py"

URDF = PROJECT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
FULL_V2 = M7 / "ecr_solar_array_r2/HARNESS_B601_FULL_FK_SWEEP_V2.json"
OLD_MASS = M7 / "wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
ENV = PKG / "03_envelope/B601_HARNESS_RATED_ENVELOPE_V1.yaml"
MAP_CSV = PKG / "03_envelope/B601_HARNESS_ENVELOPE_MAP_V1.csv"
MAP_NPZ = PKG / "03_envelope/B601_HARNESS_ENVELOPE_MAP_V1.npz"
MISSION_CONTRACT = PKG / "04_mission/B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml"
POSE_REBIND = PKG / "04_mission/B601_MISSION_POSE_AUTHORITY_REBIND_V1.yaml"
MISSION_GATE = PKG / "04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json"
MASS = PKG / "05_mass_torque/B601_HARNESS_MASS_PROPERTIES_V1.yaml"
MASS_OVERLAY = PKG / "05_mass_torque/SYSTEM_DESIGN_MASS_PROPERTIES_V4_HARNESS_CANDIDATE.yaml"
TORQUE = PKG / "05_mass_torque/B601_HARNESS_JOINT_TORQUE_ENVELOPE_V1.yaml"
CONTRACT = PKG / "06_contract/EMBODIED_MECHANICAL_CONTRACT_R3_HARNESS_CANDIDATE.yaml"
HANDOFF = PKG / "07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json"
RED_TEAM = PKG / "07_release/B601_HARNESS_SCOPED_RED_TEAM_V1.json"
TERMINAL = PKG / "07_release/B601_HARNESS_TERMINAL_GATE_V1.json"
MANIFEST = PKG / "07_release/OUTPUT_MANIFEST_V1.json"
ROUTE_C = PKG / "08_route_c/ECR_HARNESS_FULL_RANGE_01.yaml"

URDF_PIN = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
FULL_V2_PIN = "DB86348B8276FB2DCEB48DA30D1969948B37AAC4DF6D67D7588D928CF8281FAE"
PIN_FILE_PIN = "6BB8E9C5FF6910BE07D1720D320C4CB560A2CF07AD254DEB83E931AF4731C588"
EXPECTED_LIMITS = [
    [-2.8, 2.8], [-3.14, 0.0], [-3.14, 0.0],
    [-1.87, 1.57], [-1.57, 1.57], [-3.14, 3.14],
]
EXPECTED_REQUIRED_STATES = [
    "ARM_STOWED_ONORBIT_C05", "ARM_RELEASE_CLEAR", "Q_DEPLOYED_HOME",
    "ARM_TASK_READY_C06", "PREGRASP", "CONTACT", "CAPTURE_22KG", "POST_CAPTURE_22KG",
    "PHYSICS_VETO_150KG", "SAFE_RECOVERY_TARGET",
]
EXPECTED_SEGMENTS = ["M01", "M02", "M03", "M04", "M05_22", "M06_22", "M07_22", "M05_150"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


checks = []


def check(check_id: str, name: str, condition, evidence):
    checks.append({"id": check_id, "name": name, "pass": bool(condition), "evidence": evidence})


# A00: independently replay the frozen-input hash guard and its transitive V2 manifest.
pin_doc = load_yaml(PIN_FILE)
pin_results = []
for group in ("runtime_exact_dependencies", "mission_and_mass_dependencies"):
    for name, item in pin_doc[group].items():
        path = PROJECT / item["path"].replace("\\", "/")
        actual = sha256(path) if path.is_file() else None
        pin_results.append({"group": group, "name": name, "path": item["path"],
                            "expected": item["expected_sha256"], "actual": actual,
                            "match": actual == item["expected_sha256"]})
v2_for_pins = load_json(FULL_V2)
for relative_path, expected in v2_for_pins["inputs_sha256"].items():
    path = PROJECT / relative_path.replace("\\", "/")
    actual = sha256(path) if path.is_file() else None
    pin_results.append({"group": "v2_transitive_geometry_inputs", "name": Path(relative_path).name,
                        "path": relative_path.replace("\\", "/"), "expected": expected,
                        "actual": actual, "match": actual == expected})
spec = importlib.util.spec_from_file_location("route_b_exact_guard_validation", EXACT_SOURCE)
exact_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exact_module)
runtime_receipt = exact_module.verify_frozen_inputs()
compiled_pin = exact_module.PIN_FILE_EXPECTED_SHA256
exact_module.PIN_FILE_EXPECTED_SHA256 = "0" * 64
negative_evaluator = exact_module.HarnessExactEvaluator()
negative_result = negative_evaluator.check([0.0] * 6, state_id="NEGATIVE_HASH_CONTROL")
exact_module.PIN_FILE_EXPECTED_SHA256 = compiled_pin
negative_control_ok = (
    not negative_evaluator.integrity_ok
    and negative_result["status"] == "UNKNOWN"
    and negative_result["required_action"] == "ABORT"
    and negative_result["reason"] == "FROZEN_INPUT_HASH_MISMATCH"
)
pin_ok = (
    sha256(PIN_FILE) == PIN_FILE_PIN
    and exact_module.PIN_FILE_EXPECTED_SHA256 == PIN_FILE_PIN
    and all(item["match"] for item in pin_results)
    and runtime_receipt["integrity_ok"]
    and runtime_receipt["checks_total"] == len(pin_results)
    and negative_control_ok
)
check("A00", "FROZEN_INPUT_HASH_GUARD_REPLAY", pin_ok,
      {"pin_file_expected": PIN_FILE_PIN, "pin_file_actual": sha256(PIN_FILE),
       "independent_checks": len(pin_results),
       "independent_mismatches": [item for item in pin_results if not item["match"]],
       "runtime_guard": {key: runtime_receipt.get(key) for key in
                         ("pin_file_match", "checks_total", "checks_passed", "integrity_ok", "mismatches")},
       "negative_hash_control": {"status": negative_result["status"],
                                 "action": negative_result["required_action"],
                                 "reason": negative_result["reason"],
                                 "pass": negative_control_ok}})


# A01: immutable accepted geometry and retained full-range negative result.
urdf_hash = sha256(URDF)
v2_hash = sha256(FULL_V2)
root = ET.parse(URDF).getroot()
limits = []
for i in range(1, 7):
    joint = root.find("./joint[@name='joint%d']" % i)
    limits.append([float(joint.find("limit").attrib["lower"]), float(joint.find("limit").attrib["upper"])])
full_v2 = load_json(FULL_V2)
check(
    "A01", "ACCEPTED_URDF_AND_FULL_RANGE_NEGATIVE_IMMUTABLE",
    urdf_hash == URDF_PIN and v2_hash == FULL_V2_PIN and limits == EXPECTED_LIMITS
    and full_v2["verdict"]["B601_HARNESS_FUNCTIONAL_GATE"] == "FAIL",
    {"urdf_sha256": urdf_hash, "full_v2_sha256": v2_hash, "joint_limits_rad": limits,
     "full_v2_verdict": full_v2["verdict"]["B601_HARNESS_FUNCTIONAL_GATE"]},
)

# A02: every manifest member remains byte-for-byte bound.
manifest = load_json(MANIFEST)
manifest_results = []
for item in manifest["files"]:
    path = PROJECT / item["path"]
    ok = path.is_file() and path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"]
    manifest_results.append({"path": item["path"], "match": ok})
generator_source_results = []
for item in manifest.get("generator_sources", []):
    path = PROJECT / item["path"]
    ok = path.is_file() and sha256(path) == item["sha256"]
    generator_source_results.append({"role": item.get("role"), "path": item["path"], "match": ok})
pin_manifest = manifest.get("frozen_input_pin_ssot", {})
pin_manifest_ok = bool(
    pin_manifest.get("path")
    and (PROJECT / pin_manifest["path"]).is_file()
    and sha256(PROJECT / pin_manifest["path"]) == pin_manifest.get("sha256") == PIN_FILE_PIN
)
urdf_manifest = manifest.get("accepted_urdf", {})
urdf_manifest_ok = bool(
    urdf_manifest.get("path")
    and (PROJECT / urdf_manifest["path"]).is_file()
    and sha256(PROJECT / urdf_manifest["path"]) == urdf_manifest.get("sha256") == URDF_PIN
    and urdf_manifest.get("modified") is False
)
manifest_closed = bool(
    len(manifest_results) == 17
    and all(x["match"] for x in manifest_results)
    and len(generator_source_results) == 4
    and all(x["match"] for x in generator_source_results)
    and pin_manifest_ok
    and urdf_manifest_ok
)
check("A02", "OUTPUT_AND_GENERATOR_MANIFEST_HASH_CLOSURE", manifest_closed,
      {"files": len(manifest_results),
       "file_mismatches": [x for x in manifest_results if not x["match"]],
       "generator_sources": len(generator_source_results),
       "generator_source_mismatches": [x for x in generator_source_results if not x["match"]],
       "frozen_pin_manifest_match": pin_manifest_ok,
       "accepted_urdf_manifest_match": urdf_manifest_ok})

# A03: CSV and NPZ are two consistent views of the same 75 exact outcomes.
with MAP_CSV.open("r", encoding="utf-8", newline="") as stream:
    rows = list(csv.DictReader(stream))
npz = np.load(MAP_NPZ, allow_pickle=False)
csv_numeric = np.asarray([
    [float(row[k]) for k in (
        "q1_rad", "q2_rad", "q3_rad", "q4_rad", "q5_rad", "q6_rad",
        "clearance_margin_mm", "bend_margin_mm", "pinch_margin_mm",
        "length_margin_mm", "joint_limit_margin_rad",
    )] for row in rows
])
map_consistent = (
    len(rows) == 75 and npz["samples"].shape == (75, 11)
    and np.allclose(csv_numeric, npz["samples"], rtol=0.0, atol=1e-12)
    and np.all(npz["status_code"] == -1)
    and all(row["status"] == "UNSAFE" and row["required_action"] == "ABORT" for row in rows)
)
check("A03", "ENVELOPE_MAP_CSV_NPZ_CONSISTENT_FAIL_CLOSED", map_consistent,
      {"rows": len(rows), "safe": sum(r["status"] == "SAFE" for r in rows),
       "unsafe": sum(r["status"] == "UNSAFE" for r in rows),
       "unknown": sum(r["status"] == "UNKNOWN" for r in rows),
       "npz_shape": list(npz["samples"].shape)})

# A04: the empty rated envelope is not rewritten as a release.
env = load_yaml(ENV)
env_ok = (
    env["E_HRN"]["sample_counts"] == {"SAFE": 0, "UNSAFE": 75, "UNKNOWN": 0}
    and env["E_HRN"]["conservative_box"] is None
    and env["E_HRN"]["release_status"] == "NOT_RELEASED"
    and env["E_OP"]["status"] == "EMPTY_NOT_RELEASED"
    and env["unknown_policy"] == "ABORT" and env["route_b_verdict"] == "REJECTED"
)
check("A04", "NO_SAFE_COMPONENT_NO_RATED_ENVELOPE_RELEASE", env_ok,
      {"sample_counts": env["E_HRN"]["sample_counts"], "conservative_box": env["E_HRN"]["conservative_box"],
       "release_status": env["E_HRN"]["release_status"], "route_b": env["route_b_verdict"]})

# A05: mandatory mission states/segments are complete and both anchor semantics are preserved.
mission_contract = load_yaml(MISSION_CONTRACT)
mission_gate = load_json(MISSION_GATE)
pose_rebind = load_yaml(POSE_REBIND)
segment_ids = [x["id"] for x in mission_contract["segments"]]
mission_ok = (
    mission_gate["required_states"] == EXPECTED_REQUIRED_STATES
    and segment_ids == EXPECTED_SEGMENTS
    and len(mission_gate["key_state_checks"]) == len(EXPECTED_REQUIRED_STATES)
    and all(not x["pass"] and x["harness_status"] == "UNSAFE" for x in mission_gate["key_state_checks"])
    and all(x["pass"] == (x["harness_status"] == "SAFE") for x in mission_gate["key_state_checks"])
    and all(x["status"] == "UNKNOWN" for x in mission_contract["segments"])
    and all(not x["released_for_mission_gate"] for x in mission_contract["segments"])
    and mission_contract["anchor_outcomes"]["22kg_0p5dps"] == "EXECUTE_NOMINAL_CAPTURE_CHAIN_REQUIRED"
    and mission_contract["anchor_outcomes"]["150kg_3dps"] == "INFEASIBLE_RATE__PHYSICS_VETO_ABORT_RECOVERY_REQUIRED"
    and mission_contract["unknown_policy"] == "ABORT"
    and pose_rebind["legacy_pose_source"]["hash_match"]
    and not pose_rebind["legacy_pose_source"]["embedded_urdf_matches_current"]
    and pose_rebind["current_urdf"]["sha256"] == URDF_PIN
    and pose_rebind["all_named_q_vectors_loadable"]
    and pose_rebind["rebind_status"] == "PASS_CURRENT_URDF_LOADABILITY_SCOPE"
    and not pose_rebind["trajectory_authority_granted"]
    and not pose_rebind["physical_contact_authority_granted"]
    and mission_gate["derivation"]["mission_pass_rule"] == "logical AND of the five booleans above"
    and not all(bool(v) for k, v in mission_gate["derivation"].items() if k != "mission_pass_rule")
    and mission_gate["mission_coverage"] == "FAIL" and not mission_gate["next_stage_authorized"]
)
check("A05", "MANDATORY_MISSION_SET_PRESERVED_AND_FAILS_HONESTLY", mission_ok,
      {"required_states": mission_gate["required_states"], "segments": segment_ids,
       "released_segments": mission_gate["trajectory_segments_with_released_authority"],
       "pose_rebind": pose_rebind["rebind_status"],
       "22kg": mission_contract["anchor_outcomes"]["22kg_0p5dps"],
       "150kg": mission_contract["anchor_outcomes"]["150kg_3dps"],
       "mission_coverage": mission_gate["mission_coverage"]})

# A06: recompute harness mass and uncertainty declarations from their unit-tagged inputs.
mass = load_yaml(MASS)
mi = mass["inputs"]
mass_recomputed = (
    mi["cut_length_m"]["value"]
    * (mi["wire_count"]["value"] * mi["single_wire_linear_mass_kg_per_m"]["value"]
       + mi["sleeve_braid_linear_mass_kg_per_m"]["value"])
    + 2 * mi["connector_mass_kg_each"]["value"]
    + 18 * mi["clamp_mass_kg_each"]["value"]
    + 2 * mi["strain_relief_mass_kg_each"]["value"]
)
pose_props = mass["pose_dependent_properties"]
required_outputs = ["mass_kg", "cg_x_m", "cg_y_m", "cg_z_m", "Ixx_kg_m2", "Iyy_kg_m2", "Izz_kg_m2", "Ixy_kg_m2", "Ixz_kg_m2", "Iyz_kg_m2"]
input_order = mass["uncertainty_model"]["input_order"]
input_corr = np.asarray(mass["uncertainty_model"]["input_correlation_matrix"], dtype=float)
expected_exact_inputs = {
    "wire_count": 24,
    "connector_count": 2,
    "clamp_count": 18,
    "strain_relief_count": 2,
}


def stochastic_input_ledger_ok(specifications):
    return bool(
        len(specifications) == 12
        and all(
            item.get("source")
            and item.get("authority")
            and item.get("distribution")
            and item.get("degrees_of_freedom")
            and item.get("standard_uncertainty") is not None
            and np.isfinite(float(item["standard_uncertainty"]))
            and float(item["standard_uncertainty"]) >= 0.0
            for item in specifications
        )
    )


def exact_input_ledger_ok(items):
    by_name = {item.get("name"): item for item in items}
    return bool(
        set(by_name) == set(expected_exact_inputs)
        and all(
            by_name[name].get("value") == expected_value
            and by_name[name].get("unit") == "count"
            and by_name[name].get("standard_uncertainty") == 0.0
            and by_name[name].get("distribution") == "exact"
            and by_name[name].get("degrees_of_freedom")
            and by_name[name].get("source")
            and by_name[name].get("authority")
            and by_name[name].get("correlation_semantics")
            for name, expected_value in expected_exact_inputs.items()
        )
    )


top_input_ledger_ok = (
    stochastic_input_ledger_ok(mass["uncertainty_model"].get("input_specifications", []))
    and exact_input_ledger_ok(mass["uncertainty_model"].get("deterministic_exact_inputs", []))
)
pose_uncertainty_ok = True
for value in pose_props.values():
    receipt = value["uncertainty"]
    std = receipt["standard_uncertainty"]
    physical = receipt.get("physical_domain_checks", {})
    receipt_model = receipt.get("input_model", {})
    pose_uncertainty_ok = pose_uncertainty_ok and (
        receipt["output_order"] == required_outputs
        and all(np.isfinite(float(std[name])) and float(std[name]) >= 0.0 for name in required_outputs)
        and np.asarray(receipt["output_correlation_matrix"]).shape == (10, 10)
        and receipt["sampling"]["n"] == 8192
        and receipt["sampling"]["seed"] == 20260823
        and receipt["half_vs_full_convergence"]["diagnostic_pass"]
        and physical.get("sample_count") == 8192
        and physical.get("positive_mass_pass_count") == 8192
        and physical.get("positive_definite_pass_count") == 8192
        and physical.get("triangle_inequality_pass_count") == 8192
        and physical.get("positive_mass_pass_rate") == 1.0
        and physical.get("positive_definite_pass_rate") == 1.0
        and physical.get("triangle_inequality_pass_rate") == 1.0
        and physical.get("all_samples_in_physical_domain") is True
        and stochastic_input_ledger_ok(receipt_model.get("specifications", []))
        and exact_input_ledger_ok(receipt_model.get("deterministic_exact_inputs", []))
    )
mass_ok = (
    abs(mass_recomputed - mass["total_mass_kg"]) <= 1e-12
    and mass["standard_uncertainty_kg"] > 0
    and abs(mass["expanded_uncertainty_kg_k2"] - 2 * mass["standard_uncertainty_kg"]) <= 1e-12
    and len(pose_props) == 9
    and all(abs(v["mass_kg"] - mass_recomputed) <= 1e-12 for v in pose_props.values())
    and all(abs(v["model_closure_error_kg"]) <= 1e-12 for v in pose_props.values())
    and len(input_order) == 12 and input_corr.shape == (12, 12)
    and np.allclose(input_corr, np.eye(12), rtol=0.0, atol=0.0)
    and top_input_ledger_ok
    and mass["uncertainty_model"]["repeated_part_correlation"] == "FULLY_CORRELATED_WITHIN_EACH_PART_CLASS"
    and pose_uncertainty_ok
    and not mass["accepted_urdf_inertials_modified"]
)
check("A06", "HARNESS_MASS_FORMULA_AND_UNCERTAINTY_RECOMPUTE", mass_ok,
      {"recomputed_kg": mass_recomputed, "reported_kg": mass["total_mass_kg"],
       "standard_uncertainty_kg": mass["standard_uncertainty_kg"],
       "expanded_uncertainty_k2_kg": mass["expanded_uncertainty_kg_k2"],
       "pose_count": len(pose_props), "input_dimension": len(input_order),
       "field_level_input_ledger_complete": top_input_ledger_ok,
       "pose_uncertainty_receipts_complete": pose_uncertainty_ok})

# A07: candidate system overlay is diagnostic, algebraically additive and physically valid.
old_mass = load_yaml(OLD_MASS)
overlay = load_yaml(MASS_OVERLAY)
old_by_id = {x["configuration_id"]: x for x in old_mass["configurations"]}
overlay_ok = overlay["status"] == "DIAGNOSTIC_OVERLAY_NOT_CURRENT_SSOT_ROUTE_B_REJECTED" and overlay["supersedes"] is None
overlay_details = []
for cfg in overlay["configurations"]:
    cid = cfg["configuration_id"]
    delta = cfg["mass"]["value_kg"] - old_by_id[cid]["mass"]["value_kg"]
    moments = np.asarray(cfg["principal_moments_kg_m2"], dtype=float)
    receipt = cfg["uncertainty"]
    std = receipt["standard_uncertainty"]
    physical = receipt.get("physical_domain_checks", {})
    rejection = receipt.get("base_rejection_sampling", {})
    base_inputs = receipt.get("base_inputs", [])
    base_inputs_valid = bool(
        len(base_inputs) == 10
        and all(
            item.get("source")
            and item.get("authority")
            and item.get("distribution")
            and item.get("degrees_of_freedom")
            and item.get("target_standard_uncertainty") is not None
            and np.isfinite(float(item["target_standard_uncertainty"]))
            and item.get("realized_standard_uncertainty_after_truncation") is not None
            and np.isfinite(float(item["realized_standard_uncertainty_after_truncation"]))
            for item in base_inputs
        )
    )
    accepted_physical = rejection.get("accepted_sample_physical_domain_checks", {})
    uncertainty_valid = (
        receipt["output_order"][:10] == required_outputs
        and len(receipt["output_order"]) == 13
        and all(np.isfinite(float(std[name])) and float(std[name]) >= 0.0 for name in receipt["output_order"])
        and np.asarray(receipt["output_correlation_matrix"]).shape == (13, 13)
        and receipt["sampling"]["n"] == 8192
        and receipt["half_vs_full_convergence"]["diagnostic_pass"]
        and receipt["correlation_assumptions"]["base_covariance_status"] == "UNKNOWN_NOT_PROVIDED"
        and receipt["correlation_assumptions"]["base_target_input_correlations"] == "ASSUMED_INDEPENDENT_BEFORE_TRUNCATION"
        and receipt["correlation_assumptions"]["base_realized_correlations"] == "INDUCED_BY_PHYSICAL_DOMAIN_TRUNCATION_AND_REPORTED"
        and rejection.get("policy") == "TRUNCATED_NORMAL_REJECTION_TO_PHYSICAL_MASS_PROPERTY_DOMAIN"
        and rejection.get("accepted") == 8192
        and rejection.get("total_draws", 0) >= 8192
        and 0.0 < float(rejection.get("acceptance_rate", 0.0)) <= 1.0
        and np.asarray(rejection.get("target_correlation_matrix", [])).shape == (10, 10)
        and np.asarray(rejection.get("realized_correlation_matrix_after_truncation", [])).shape == (10, 10)
        and accepted_physical.get("all_samples_in_physical_domain") is True
        and physical.get("sample_count") == 8192
        and physical.get("positive_mass_pass_count") == 8192
        and physical.get("positive_definite_pass_count") == 8192
        and physical.get("triangle_inequality_pass_count") == 8192
        and physical.get("positive_mass_pass_rate") == 1.0
        and physical.get("positive_definite_pass_rate") == 1.0
        and physical.get("triangle_inequality_pass_rate") == 1.0
        and physical.get("all_samples_in_physical_domain") is True
        and all(receipt["quantiles_2p5_97p5"][f"principal_moment_{i}_kg_m2"][0] > 0.0 for i in (1, 2, 3))
        and base_inputs_valid
    )
    valid = (
        abs(delta - mass_recomputed) <= 1e-9
        and np.all(moments > 0)
        and moments[0] + moments[1] >= moments[2] - 1e-12
        and all(cfg["checks"].values())
        and uncertainty_valid
    )
    overlay_ok = overlay_ok and valid
    overlay_details.append({"configuration_id": cid, "mass_addend_kg": delta,
                            "uncertainty_complete": uncertainty_valid,
                            "base_input_sources_complete": base_inputs_valid,
                            "base_rejection_draws": rejection.get("total_draws"),
                            "base_rejection_acceptance_rate": rejection.get("acceptance_rate"),
                            "physical_domain": physical, "valid": valid})
overlay_ok = overlay_ok and len(overlay_details) == 9 and not overlay["accepted_urdf_inertials_modified"]
check("A07", "DIAGNOSTIC_MASS_OVERLAY_ALGEBRA_AND_INERTIA_VALID", overlay_ok,
      {"status": overlay["status"], "configurations": overlay_details})

# A08: missing bundle stiffness/friction remains an explicit dynamics HOLD.
torque = load_yaml(TORQUE)
torque_params = list(torque["parameters"].values())
torque_ok = (
    len(torque_params) == 6
    and all(x["k_Nm_per_rad"] is None and x["c_Nm_s_per_rad"] is None and x["coulomb_Nm"] is None for x in torque_params)
    and all(str(x["status"]).startswith("HOLD_") for x in torque_params)
    and torque["dynamic_effect"] == "UNKNOWN_FAIL_CLOSED"
    and torque["negligible_claim"] == "FORBIDDEN_WITHOUT_EVIDENCE"
    and torque["verdict"] == "HOLD"
)
check("A08", "HARNESS_RESTORING_TORQUE_UNKNOWN_REMAINS_HOLD", torque_ok,
      {"joint_count": len(torque_params), "dynamic_effect": torque["dynamic_effect"],
       "verdict": torque["verdict"]})

# A09: embodied contract blocks unsafe/unknown and production/contact execution.
contract = load_yaml(CONTRACT)
contract_ok = (
    contract["status"] == "CANDIDATE_NOT_RELEASED_ROUTE_B_REJECTED"
    and contract["harness"]["fail_closed"] == {"UNKNOWN": "ABORT", "UNSAFE": "ABORT"}
    and contract["harness"]["planner_policy"]["trajectory_validation_required"]
    and contract["harness"]["planner_policy"]["endpoint_only_validation_forbidden"]
    and contract["physical_contact"] == "HOLD" and contract["physics_gated_RL"] == "HOLD"
    and contract["production_dynamics"] == "HOLD" and not contract["next_stage_authorized"]
    and contract["frozen_input_integrity"]["runtime_receipt"]["integrity_ok"]
    and contract["frozen_input_integrity"]["mismatch_policy"] == {"classification": "UNKNOWN", "action": "ABORT"}
)
check("A09", "EMBODIED_CONTRACT_FAIL_CLOSED", contract_ok,
      {"status": contract["status"], "fail_closed": contract["harness"]["fail_closed"],
       "physical_contact": contract["physical_contact"], "production_dynamics": contract["production_dynamics"]})

# A10: handoff and terminal decisions have one coherent failure path and trigger Route C.
handoff = load_json(HANDOFF)
terminal = load_json(TERMINAL)
route_c = load_yaml(ROUTE_C)
red_team = load_json(RED_TEAM)
failed = [x["id"] for x in handoff["checks"] if not x["pass"]]
handoff_by_id = {x["id"]: x for x in handoff["checks"]}
g12_terms = handoff_by_id["G12"]["evidence"]["terms"]
captured_hashes = handoff_by_id["G01"]["evidence"]["captured_assets"]
terminal_terms = terminal["terminal_release_condition"]
decision_ok = (
    handoff["checks_total"] == 12 and handoff["checks_passed"] == 11 and failed == ["G12"]
    and handoff["verdict"] == "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL" and not handoff["next_stage_authorized"]
    and terminal["mission_coverage"] == "FAIL" and terminal["route_b"] == "REJECTED"
    and terminal["route_c"] == "TRIGGERED" and terminal["mechanical_design"] == "NOT_RELEASED"
    and terminal["internal_mechanical_hold_count"] == len(terminal["internal_mechanical_holds"]) == 3
    and not terminal["next_stage_authorized"]
    and route_c["status"] == "TRIGGERED_PENDING_DETAILED_DESIGN_AUTHORIZATION"
    and not route_c["next_stage_authorized"]
    and handoff_by_id["G12"]["pass"] == all(bool(value) for value in g12_terms.values())
    and not handoff_by_id["G12"]["pass"] and not g12_terms["mission_coverage_pass"]
    and all(item["match"] and item["expected_sha256"] == item["actual_sha256"] for item in captured_hashes)
    and handoff_by_id["G01"]["evidence"]["frozen_input_receipt"]["integrity_ok"]
    and all(item["pass"] for item in handoff["checks"] if item["id"] != "G12")
    and red_team["open_findings"] == {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    and all(not item["open"] for item in red_team["attacks"])
    and red_team["verdict"] == "PASS_FAIL_CLOSED_NEGATIVE_DECISION"
    and terminal_terms["all_met"] == all(bool(value) for key, value in terminal_terms.items() if key != "all_met")
    and not terminal_terms["all_met"]
)
check("A10", "TERMINAL_DECISION_COHERENT_AND_ROUTE_C_TRIGGERED", decision_ok,
      {"handoff": "%d/%d" % (handoff["checks_passed"], handoff["checks_total"]),
       "failed_checks": failed, "internal_holds": terminal["internal_mechanical_holds"],
       "g12_terms": g12_terms, "red_team": red_team["open_findings"],
       "route_b": terminal["route_b"], "route_c": route_c["status"],
       "next_stage_authorized": terminal["next_stage_authorized"]})

failed_checks = [x["id"] for x in checks if not x["pass"]]
report = {
    "schema": "B601_HARNESS_TERMINAL_INDEPENDENT_VALIDATION_V1",
    "validation_basis_generation": terminal["generated_local"],
    "validator_sha256": sha256(Path(__file__).resolve()),
    "checks": checks,
    "checks_total": len(checks),
    "checks_passed": len(checks) - len(failed_checks),
    "checks_failed": len(failed_checks),
    "failed_checks": failed_checks,
    "verdict": "INDEPENDENT_VALIDATION_PASS" if not failed_checks else "INDEPENDENT_VALIDATION_FAIL",
    "validated_terminal_decision": "ROUTE_B_REJECTED__ROUTE_C_TRIGGERED" if not failed_checks else "NOT_VALIDATED",
    "next_stage_authorized": False,
}
REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({k: report[k] for k in (
    "checks_total", "checks_passed", "checks_failed", "verdict",
    "validated_terminal_decision", "next_stage_authorized",
)}, indent=2, ensure_ascii=False))
raise SystemExit(0 if not failed_checks else 1)
