"""Independently validate the V2 mechanical-loop continuation gate."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import yaml


REPO = Path(__file__).resolve().parents[4]
BASE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope"
)
OUT_REL = f"{BASE_REL}/12_loop_continuation_v2"
FILES = {
    "gate": f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V2.json",
    "brief": f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V2.md",
    "manifest": f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V2.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(relative_path: str) -> dict[str, Any]:
    return json.loads((REPO / relative_path).read_text(encoding="utf-8"))


def read_yaml(relative_path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO / relative_path).read_text(encoding="utf-8"))


def fact(value: dict[str, Any], fact_id: str) -> dict[str, Any]:
    matches = [item for item in value["facts"] if item["id"] == fact_id]
    if len(matches) != 1:
        raise ValueError(f"expected one fact {fact_id}, got {len(matches)}")
    return matches[0]


def gate_safe(value: dict[str, Any]) -> bool:
    release = value["current_release"]
    blockers = {item["id"]: item["state"] for item in value["blocking_fronts"]}
    expected_true = [
        "isolated_nonrelease_numeric_input_branches_ready",
        "hash_bound_nonrelease_branching_ready",
        "offline_m01_qspace_candidate_integrity",
        "m05_diagnostic_branch_separation_ready",
        "m06_solver_stimulus_matrix_ready",
        "m07_diagnostic_attached_branch_binding_ready",
        "gripper_unit_semantics_reconciled",
    ]
    expected_false = [
        "end_to_end_diagnostic_dynamics_ready",
        "mission_sequence_executable",
        "mission_trajectory_release_ready",
        "owner_detailed_design_authority",
        "route_c_product_selected",
        "cad_generation_authorized",
        "route_c_cad_entry_ready",
        "physical_gripper_speed_ready",
        "physical_contact_ready",
        "physical_contact_model_ready",
        "released_combined_mass_properties_ready",
        "full_path_collision_solar_harness_safe",
        "mechanical_design_released",
        "production_dynamics_ready",
        "sim13_current_production_binding_valid",
        "physical_contact_rl_ready",
        "hardware_motion_ready",
        "flight_qualification_ready",
    ]
    return (
        value["gate"] == "HOLD"
        and value["next_stage_authorized"] is False
        and value["release_credit"] is False
        and value["facts_confirmed"] == value["facts_total"] == 11
        and all(item["observed"] is True for item in value["facts"])
        and all(release[key] is True for key in expected_true)
        and all(release[key] is False for key in expected_false)
        and release["route_c_mpi_controlled"] == 0
        and release["route_c_mpi_total"] == 8
        and release["mission_trajectories_released"] == 0
        and release["mission_trajectories_total"] == 8
        and blockers
        == {
            "BF2-01": "HOLD_ODR42_PENDING",
            "BF2-02": "HOLD_MPI_0_OF_8_CONTROLLED",
            "BF2-03": "HOLD_NO_ACTUATOR_OR_CONTACT_CHARACTERIZATION",
            "BF2-04": "HOLD_RELEASE_0_OF_8",
            "BF2-05": "HOLD_ROUTE_C_CAD_AND_FULL_PATH_GATES_ABSENT",
        }
        and fact(value, "LC2-04")["evidence"]["mission_sequence_executable"] is False
        and fact(value, "LC2-05")["evidence"]["merge_allowed"] is False
        and fact(value, "LC2-06")["evidence"]["physical_force_pressure_duration_normal_lock"] is None
        and fact(value, "LC2-07")["evidence"]["selected_locked_transform"] is None
        and fact(value, "LC2-08")["evidence"]["controlled"] == 0
        and fact(value, "LC2-09")["evidence"]["owner_decision"] == "PENDING"
        and fact(value, "LC2-10")["evidence"]["new_geometry_count"] == 0
        and fact(value, "LC2-11")["evidence"]["current_authority"]["production_dynamics_ready"] is False
    )


def main() -> None:
    gate = read_json(FILES["gate"])
    manifest = read_json(FILES["manifest"])
    brief = (REPO / FILES["brief"]).read_text(encoding="utf-8")
    input_bindings = {item["name"]: item for item in gate["input_bindings"]}
    prior = read_json(input_bindings["prior_continuation_gate"]["path"])
    prior_validation = read_json(input_bindings["prior_continuation_validation"]["path"])
    gripper = read_json(input_bindings["gripper_gate"]["path"])
    gripper_validation = read_json(input_bindings["gripper_validation"]["path"])
    gripper_v2 = read_yaml(input_bindings["gripper_v2"]["path"])
    mpi = read_json(input_bindings["mpi_gate"]["path"])
    mpi_validation = read_json(input_bindings["mpi_validation"]["path"])
    e18 = read_json(input_bindings["e18_gate"]["path"])
    e18_validation = read_json(input_bindings["e18_validation"]["path"])
    e18_register = read_json(input_bindings["e18_register"]["path"])
    sim13 = read_json(input_bindings["sim13_binding_audit"]["path"])
    odr42 = read_yaml(input_bindings["odr42_request"]["path"])

    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, evidence: Any) -> None:
        checks.append({"id": check_id, "pass": bool(passed), "evidence": evidence})

    for name, relative_path in FILES.items():
        path = REPO / relative_path
        add(f"FILE_{name.upper()}", path.is_file() and path.stat().st_size > 0, relative_path)
    add("SCHEMA_GATE", gate["schema"] == "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V2", gate["schema"])
    add("SCHEMA_MANIFEST", manifest["schema"] == "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V2", manifest["schema"])
    add("INPUT_BINDINGS_19", len(gate["input_bindings"]) == 19, len(gate["input_bindings"]))
    matched_inputs = 0
    for item in gate["input_bindings"]:
        path = REPO / item["path"]
        if path.is_file() and path.stat().st_size == item["bytes"] and sha256_file(path) == item["sha256"]:
            matched_inputs += 1
    add("ALL_INPUT_HASHES_MATCH", matched_inputs == len(gate["input_bindings"]), f'{matched_inputs}/{len(gate["input_bindings"])}')
    add("FACTS_11_OF_11", gate["facts_confirmed"] == gate["facts_total"] == 11, f'{gate["facts_confirmed"]}/{gate["facts_total"]}')
    add("ALL_FACTS_OBSERVED", all(item["observed"] is True for item in gate["facts"]), [item["id"] for item in gate["facts"] if not item["observed"]])
    add("EXPECTED_VERDICT", gate["verdict"].endswith("PRE_CAD_PHYSICAL_CONTACT_MISSION_AND_PRODUCTION_RELEASE_HOLD"), gate["verdict"])
    add("FAIL_CLOSED_RELEASE_BUNDLE", gate_safe(gate), gate["current_release"])
    add("PRIOR_GATE_HOLD", prior["gate"] == "HOLD" and prior["next_stage_authorized"] is False, prior["verdict"])
    add("PRIOR_VALIDATION", prior_validation["package_integrity_pass"] is True and prior_validation["checks_passed"] == prior_validation["checks_total"] and prior_validation["negative_controls_passed"] == prior_validation["negative_controls_total"], {"checks": [prior_validation["checks_passed"], prior_validation["checks_total"]], "negative": [prior_validation["negative_controls_passed"], prior_validation["negative_controls_total"]]})
    add("GRIPPER_SEMANTICS_PASS", gripper["semantic_reconciliation"] == "PASS" and gripper["physical_actuator_speed_authority"] == "HOLD", gripper["verdict"])
    add("GRIPPER_VALIDATION", gripper_validation["package_integrity_pass"] is True and gripper_validation["checks_passed"] == gripper_validation["checks_total"] and gripper_validation["negative_controls_passed"] == gripper_validation["negative_controls_total"], {"checks": [gripper_validation["checks_passed"], gripper_validation["checks_total"]], "negative": [gripper_validation["negative_controls_passed"], gripper_validation["negative_controls_total"]]})
    add("GRIPPER_PHYSICAL_NULL", gripper_v2["frozen_inputs"]["urdf_velocity_physical_capability_m_s"] is None and gripper_v2["frozen_inputs"]["urdf_velocity_physical_uncertainty_m_s"] is None, gripper_v2["frozen_inputs"])
    add("MPI_GATE_0_OF_8", mpi["gate"] == "HOLD" and mpi["criteria_controlled"] == 0 and mpi["criteria_total"] == 8 and mpi["next_stage_authorized"] is False, mpi["verdict"])
    add("MPI_VALIDATION", mpi_validation["all_pass"] is True and mpi_validation["checks_passed"] == mpi_validation["checks_total"] == 133 and mpi_validation["negative_controls_passed"] == mpi_validation["negative_controls_total"] == 21, {"checks": [mpi_validation["checks_passed"], mpi_validation["checks_total"]], "negative": [mpi_validation["negative_controls_passed"], mpi_validation["negative_controls_total"]]})
    add("MPI07_SCOPE", mpi["mpi07_local_kinematics_available"] is True and mpi["mpi07_installation_icd_closed"] is False, {"local": mpi["mpi07_local_kinematics_available"], "icd": mpi["mpi07_installation_icd_closed"]})
    add("MPI_NO_CAD", mpi["cad_generation_authorized"] is False and mpi["cad_assets_created"] == 0, {"authorized": mpi["cad_generation_authorized"], "assets": mpi["cad_assets_created"]})
    add("E18_GATE_HOLD", e18["numeric_branch_integrity_ready"] is True and e18["released_segments"] == 0 and e18["production_dynamics_ready"] is False and e18["next_stage_authorized"] is False, e18["verdict"])
    add("E18_VALIDATION", e18_validation["checks_passed"] == e18_validation["checks_total"] == 69 and e18_validation["negative_controls_passed"] == e18_validation["negative_controls_total"] == 29 and e18_validation["gate"] == "HOLD", {"checks": [e18_validation["checks_passed"], e18_validation["checks_total"]], "negative": [e18_validation["negative_controls_passed"], e18_validation["negative_controls_total"]]})
    segments = {item["segment_id"]: item for item in e18_register["segments"]}
    add("E18_SEGMENTS_EXACT", set(segments) == {"M01", "M05_22", "M06_22", "M07_22"}, sorted(segments))
    add("E18_BRANCH_COUNTS", [segments[key]["numeric_branch_count"] for key in ["M01", "M05_22", "M06_22", "M07_22"]] == [1, 2, 20, 4], [segments[key]["numeric_branch_count"] for key in ["M01", "M05_22", "M06_22", "M07_22"]])
    add("E18_ZERO_RELEASES", all(item["released_for_mission_gate"] is False for item in segments.values()) and e18_register["coverage"]["released_segments"] == 0, e18_register["coverage"])
    add("E18_NO_GEOMETRY", e18_register["cad_or_geometry_created"] is False, e18_register["cad_or_geometry_created"])
    add("M01_NOT_EXECUTABLE", fact(gate, "LC2-04")["evidence"]["release_confirmed_signal"] == "UNBOUND" and fact(gate, "LC2-04")["evidence"]["mission_sequence_executable"] is False, fact(gate, "LC2-04")["evidence"])
    add("M05_NO_MERGE", fact(gate, "LC2-05")["evidence"]["branch_count"] == 2 and fact(gate, "LC2-05")["evidence"]["merge_allowed"] is False, fact(gate, "LC2-05")["evidence"])
    add("M06_SOLVER_ONLY", fact(gate, "LC2-06")["evidence"]["case_count"] == 20 and fact(gate, "LC2-06")["evidence"]["peak_force_role"] == "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT" and fact(gate, "LC2-06")["evidence"]["physical_force_pressure_duration_normal_lock"] is None, fact(gate, "LC2-06")["evidence"])
    add("M07_LOCK_HOLD", fact(gate, "LC2-07")["evidence"]["selected_locked_transform"] is None and fact(gate, "LC2-07")["evidence"]["released_mass_cg_inertia"] is None, fact(gate, "LC2-07")["evidence"])
    add("ODR42_PENDING", odr42["record_type"] == "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD" and odr42["owner_decision"] == "PENDING" and odr42["next_stage_authorized"] is False, {"record_type": odr42["record_type"], "owner_decision": odr42["owner_decision"]})
    add("SIM13_INVALID", sim13["current_authority"]["diagnostic_kinematic_bootstrap_only"] is True and sim13["current_authority"]["production_dynamics_ready"] is False and sim13["current_authority"]["physical_contact_ready"] is False and sim13["current_authority"]["physics_gated_rl_ready"] is False, sim13["current_authority"])
    add("BRIEF_BOUNDARIES", all(token in brief for token in ["离线诊断", "release_confirmed", "峰值不是实测/允许接触力", "0/8 CONTROLLED", "Route-C CAD", "生产 Sim13"]), "brief contains all authority boundaries")
    add("PROHIBITION_EXPLICIT", "No Route-C CAD/STEP" in gate["prohibition"] and "production Sim13 rebind" in gate["prohibition"], gate["prohibition"])
    add("OWNER_STATEMENT_EXPLICIT", "APPROVE_BOUNDED_DETAILED_DESIGN" in gate["required_owner_statement"] and "MPI-01..MPI-08" in gate["required_owner_statement"], gate["required_owner_statement"])
    add("MANIFEST_COUNTS", manifest["output_count"] == 2 and manifest["source_count"] == 5, {"outputs": manifest["output_count"], "sources": manifest["source_count"]})
    manifest_items = manifest["outputs"] + manifest["sources"]
    matched_manifest = 0
    for item in manifest_items:
        path = REPO / item["path"]
        if path.is_file() and path.stat().st_size == item["bytes"] and sha256_file(path) == item["sha256"]:
            matched_manifest += 1
    add("MANIFEST_HASH_CLOSURE", matched_manifest == len(manifest_items), f'{matched_manifest}/{len(manifest_items)}')

    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("NC-01_ODR42_APPROVED", lambda value: fact(value, "LC2-09")["evidence"].__setitem__("owner_decision", "APPROVED")),
        ("NC-02_MPI_PROMOTED", lambda value: value["current_release"].__setitem__("route_c_mpi_controlled", 8)),
        ("NC-03_CAD_ENTRY_TRUE", lambda value: value["current_release"].__setitem__("route_c_cad_entry_ready", True)),
        ("NC-04_PRODUCT_SELECTED", lambda value: value["current_release"].__setitem__("route_c_product_selected", True)),
        ("NC-05_MISSION_EXECUTABLE", lambda value: value["current_release"].__setitem__("mission_sequence_executable", True)),
        ("NC-06_MISSION_RELEASE", lambda value: value["current_release"].__setitem__("mission_trajectories_released", 1)),
        ("NC-07_PHYSICAL_SPEED", lambda value: value["current_release"].__setitem__("physical_gripper_speed_ready", True)),
        ("NC-08_PHYSICAL_CONTACT", lambda value: value["current_release"].__setitem__("physical_contact_model_ready", True)),
        ("NC-09_COMBINED_MASS", lambda value: value["current_release"].__setitem__("released_combined_mass_properties_ready", True)),
        ("NC-10_PRODUCTION_DYNAMICS", lambda value: value["current_release"].__setitem__("production_dynamics_ready", True)),
        ("NC-11_SIM13_REBOUND", lambda value: value["current_release"].__setitem__("sim13_current_production_binding_valid", True)),
        ("NC-12_CONTACT_RL", lambda value: value["current_release"].__setitem__("physical_contact_rl_ready", True)),
        ("NC-13_HARDWARE_MOTION", lambda value: value["current_release"].__setitem__("hardware_motion_ready", True)),
        ("NC-14_NEXT_STAGE", lambda value: value.__setitem__("next_stage_authorized", True)),
        ("NC-15_FACT_COUNT", lambda value: value.__setitem__("facts_confirmed", 10)),
        ("NC-16_M01_GUARD_BOUND", lambda value: fact(value, "LC2-04")["evidence"].__setitem__("mission_sequence_executable", True)),
        ("NC-17_M05_MERGE", lambda value: fact(value, "LC2-05")["evidence"].__setitem__("merge_allowed", True)),
        ("NC-18_M06_FORCE_FILL", lambda value: fact(value, "LC2-06")["evidence"].__setitem__("physical_force_pressure_duration_normal_lock", 0.0)),
        ("NC-19_M07_TRANSFORM_FILL", lambda value: fact(value, "LC2-07")["evidence"].__setitem__("selected_locked_transform", "INJECTED")),
        ("NC-20_GEOMETRY_COUNT", lambda value: fact(value, "LC2-10")["evidence"].__setitem__("new_geometry_count", 1)),
        ("NC-21_BLOCKER_PASS", lambda value: value["blocking_fronts"][2].__setitem__("state", "PASS")),
        ("NC-22_RELEASE_CREDIT", lambda value: value.__setitem__("release_credit", True)),
        ("NC-23_END_TO_END_DIAGNOSTIC", lambda value: value["current_release"].__setitem__("end_to_end_diagnostic_dynamics_ready", True)),
        ("NC-24_CAD_GENERATION", lambda value: value["current_release"].__setitem__("cad_generation_authorized", True)),
        ("NC-25_MISSION_GATE_READY", lambda value: value["current_release"].__setitem__("mission_trajectory_release_ready", True)),
    ]
    negative_controls: list[dict[str, Any]] = []
    for control_id, mutate in mutations:
        candidate = copy.deepcopy(gate)
        mutate(candidate)
        negative_controls.append({"id": control_id, "pass": not gate_safe(candidate)})

    checks_passed = sum(item["pass"] for item in checks)
    negative_passed = sum(item["pass"] for item in negative_controls)
    passed = checks_passed == len(checks) and negative_passed == len(negative_controls)
    report = {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V2",
        "generated_local": gate["generated_local"],
        "scope": "hash, semantic, branch-boundary and fail-closed integration validation; no physical release",
        "verdict": "PASS_V2_CONTINUATION_INTEGRITY__NONRELEASE_INPUT_LANE_ONLY" if passed else "FAIL_V2_CONTINUATION_INTEGRITY",
        "package_integrity_pass": passed,
        "checks": checks,
        "checks_passed": checks_passed,
        "checks_total": len(checks),
        "negative_controls": negative_controls,
        "negative_controls_passed": negative_passed,
        "negative_controls_total": len(negative_controls),
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    report_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V2.json"
    path = REPO / report_rel
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "checks": f'{checks_passed}/{len(checks)}',
                "negative_controls": f'{negative_passed}/{len(negative_controls)}',
                "validation_sha256": sha256_file(path),
            },
            ensure_ascii=False,
        )
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
