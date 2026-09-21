"""Independent validation for the mechanical-loop continuation gate."""
from __future__ import annotations

import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

import yaml


REPO = Path(__file__).resolve().parents[4]
BASE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope"
)
OUT_REL = f"{BASE_REL}/11_loop_continuation"
FILES = {
    "gate": f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V1.json",
    "brief": f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V1.md",
    "manifest": f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V1.json",
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


def fact_by_id(value: dict[str, Any], fact_id: str) -> dict[str, Any]:
    matches = [item for item in value["facts"] if item["id"] == fact_id]
    if len(matches) != 1:
        raise ValueError(f"expected one fact {fact_id}, got {len(matches)}")
    return matches[0]


def gate_safe(value: dict[str, Any]) -> bool:
    release = value["current_release"]
    expected_false = [
        "owner_detailed_design_authority",
        "route_c_product_selected",
        "route_c_cad_entry_ready",
        "full_path_collision_solar_safe",
        "physical_gripper_timing_ready",
        "mechanical_design_released",
        "production_dynamics_ready",
        "physical_contact_rl_ready",
        "hardware_motion_ready",
        "flight_qualification_ready",
    ]
    blocker_states = {item["id"]: item["state"] for item in value["blocking_fronts"]}
    e17_counts = fact_by_id(value, "LC-04")["evidence"]["counts"]
    gripper_evidence = fact_by_id(value, "LC-05")["evidence"]
    odr_evidence = fact_by_id(value, "LC-06")["evidence"]
    product_evidence = fact_by_id(value, "LC-02")["evidence"]
    sim13_evidence = fact_by_id(value, "LC-09")["evidence"]
    return (
        value["gate"] == "HOLD"
        and value["next_stage_authorized"] is False
        and value["facts_confirmed"] == value["facts_total"] == 9
        and all(release[key] is False for key in expected_false)
        and release["mission_trajectories_released"] == 0
        and release["mission_trajectories_total"] == 8
        and e17_counts["mission_segments_total"] == 8
        and e17_counts["released_segments"] == 0
        and (
            e17_counts["numeric_arm_only_seed_segments"]
            + e17_counts["symbolic_scaffold_segments"]
            + e17_counts["blocked_uninstantiated_segments"]
            == e17_counts["mission_segments_total"]
        )
        and gripper_evidence["state"] == "HOLD_UNIT_CONFLICT"
        and gripper_evidence["physical_gripper_timing_authorized"] is False
        and odr_evidence["record_type"] == "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD"
        and odr_evidence["owner_decision"] == "PENDING"
        and odr_evidence["next_stage_authorized"] is False
        and product_evidence["minimum_inputs"] == "0/8 CONTROLLED"
        and product_evidence["rc_ceg_03"] == "HOLD"
        and sim13_evidence["verdict"]
        == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE"
        and sim13_evidence["current_authority"]["production_dynamics_ready"] is False
        and sim13_evidence["current_authority"]["physical_contact_ready"] is False
        and sim13_evidence["current_authority"]["physics_gated_rl_ready"] is False
        and sim13_evidence["next_stage_authorized"] is False
        and blocker_states == {
            "BF-01": "HOLD_ODR42_PENDING",
            "BF-02": "HOLD_MPI_0_OF_8_CONTROLLED",
            "BF-03": "HOLD_RELEASE_0_OF_8",
            "BF-04": "HOLD_CURRENT_SIM13_PRODUCTION_BINDING_INVALID",
        }
    )


def main() -> None:
    gate = read_json(FILES["gate"])
    manifest = read_json(FILES["manifest"])
    brief = (REPO / FILES["brief"]).read_text(encoding="utf-8")
    input_bindings = {item["name"]: item for item in gate["input_bindings"]}
    e17_upstream = read_json(input_bindings["e17_gate"]["path"])
    product_upstream = read_json(input_bindings["product_input_gate"]["path"])
    rfi_upstream = read_json(input_bindings["vendor_rfi_gate"]["path"])
    sim13_upstream = read_json(input_bindings["sim13_binding_audit"]["path"])
    odr42_upstream = read_yaml(input_bindings["odr42_request"]["path"])
    gripper_upstream = read_yaml(input_bindings["gripper_engineering_pack"]["path"])
    urdf_root = ET.parse(REPO / input_bindings["accepted_urdf"]["path"]).getroot()
    urdf_gripper_velocities_m_s = [
        float(joint.find("limit").attrib["velocity"])
        for joint in urdf_root.findall("joint")
        if joint.attrib.get("name") in {"gripper_joint1", "gripper_joint2"}
        and joint.attrib.get("type") == "prismatic"
        and joint.find("limit") is not None
    ]
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, evidence: Any) -> None:
        checks.append({"id": check_id, "pass": bool(passed), "evidence": evidence})

    for name, relative_path in FILES.items():
        path = REPO / relative_path
        add(f"FILE_{name.upper()}", path.is_file() and path.stat().st_size > 0, relative_path)
    add("SCHEMA_GATE", gate["schema"] == "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V1", gate["schema"])
    add("SCHEMA_MANIFEST", manifest["schema"] == "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V1", manifest["schema"])
    add("INPUT_BINDINGS_15", len(gate["input_bindings"]) == 15, len(gate["input_bindings"]))
    matched_inputs = 0
    for item in gate["input_bindings"]:
        path = REPO / item["path"]
        if path.is_file() and path.stat().st_size == item["bytes"] and sha256_file(path) == item["sha256"]:
            matched_inputs += 1
    add("ALL_INPUT_HASHES_MATCH", matched_inputs == len(gate["input_bindings"]), f'{matched_inputs}/{len(gate["input_bindings"])}')
    add("FACTS_9_OF_9", gate["facts_confirmed"] == gate["facts_total"] == 9, f'{gate["facts_confirmed"]}/{gate["facts_total"]}')
    add("ALL_FACTS_OBSERVED", all(item["observed"] is True for item in gate["facts"]), [item["id"] for item in gate["facts"] if not item["observed"]])
    add("EXPECTED_VERDICT", gate["verdict"].endswith("PRE_CAD_AND_MISSION_RELEASE_HOLD"), gate["verdict"])
    add("FAIL_CLOSED_RELEASE_BITS", gate_safe(gate), gate["current_release"])
    add("RFI_PROGRESS_RECORDED", "53_OF_53_WITH_15_OF_15" in gate["engineering_progress"]["route_c_vendor_rfi_pack"], gate["engineering_progress"]["route_c_vendor_rfi_pack"])
    add("PRODUCT_PROGRESS_RECORDED", "51_OF_51_WITH_4_OF_4" in gate["engineering_progress"]["route_c_product_input_pack"], gate["engineering_progress"]["route_c_product_input_pack"])
    add("E17_PROGRESS_RECORDED", "42_OF_42_WITH_10_OF_10" in gate["engineering_progress"]["e17_trajectory_candidate_pack"], gate["engineering_progress"]["e17_trajectory_candidate_pack"])
    add("RFI_ZERO_SELECTION", "0 selected" in gate["engineering_progress"]["candidate_route_shape"], gate["engineering_progress"]["candidate_route_shape"])
    add("TRAJECTORY_ZERO_RELEASE", "0/8 released" in gate["engineering_progress"]["trajectory_shape"], gate["engineering_progress"]["trajectory_shape"])
    upstream_counts = e17_upstream["counts"]
    add("UPSTREAM_TRAJECTORY_COUNTS", upstream_counts["mission_segments_total"] == 8 and upstream_counts["numeric_arm_only_seed_segments"] == 5 and upstream_counts["symbolic_scaffold_segments"] == 1 and upstream_counts["blocked_uninstantiated_segments"] == 2 and upstream_counts["released_segments"] == 0 and upstream_counts["numeric_arm_only_seed_segments"] + upstream_counts["symbolic_scaffold_segments"] + upstream_counts["blocked_uninstantiated_segments"] == upstream_counts["mission_segments_total"], upstream_counts)
    add("UPSTREAM_PRODUCT_HOLD", product_upstream["criteria_controlled"] == 0 and product_upstream["criteria_total"] == 8 and product_upstream["rc_ceg_03"] == "HOLD" and product_upstream["next_stage_authorized"] is False, {"controlled": product_upstream["criteria_controlled"], "total": product_upstream["criteria_total"], "rc_ceg_03": product_upstream["rc_ceg_03"]})
    add("UPSTREAM_RFI_ZERO_SELECTION", rfi_upstream["candidate_routes"]["selected_routes"] == 0 and rfi_upstream["rc_ceg_03"] == "HOLD" and rfi_upstream["odr42"] == "PENDING" and rfi_upstream["next_stage_authorized"] is False, rfi_upstream["candidate_routes"])
    add("UPSTREAM_ODR42_PENDING", odr42_upstream["record_type"] == "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD" and odr42_upstream["owner_decision"] == "PENDING" and odr42_upstream["next_stage_authorized"] is False, {"record_type": odr42_upstream["record_type"], "owner_decision": odr42_upstream["owner_decision"]})
    add("UPSTREAM_SIM13_INVALID", sim13_upstream["verdict"] == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE" and sim13_upstream["current_authority"]["production_dynamics_ready"] is False and sim13_upstream["current_authority"]["physical_contact_ready"] is False and sim13_upstream["current_authority"]["physics_gated_rl_ready"] is False and sim13_upstream["next_stage_authorized"] is False, sim13_upstream["verdict"])
    add("UPSTREAM_GRIPPER_UNIT_CONFLICT", urdf_gripper_velocities_m_s == [15.0, 15.0] and gripper_upstream["frozen_inputs"]["urdf_velocity_limit_mm_s"] == 15.0 and gripper_upstream["frozen_inputs"]["urdf_limit_role"] == "MODEL_LIMIT_NOT_DESIGN_OR_QUALIFICATION_LOAD", {"urdf_m_s": urdf_gripper_velocities_m_s, "engineering_pack_mm_s": gripper_upstream["frozen_inputs"]["urdf_velocity_limit_mm_s"]})
    add("ODR42_EXPLICIT", "APPROVE_BOUNDED_DETAILED_DESIGN" in gate["required_owner_statement"], gate["required_owner_statement"])
    add("PROHIBITION_EXPLICIT", "No Route-C CAD/STEP" in gate["prohibition"], gate["prohibition"])
    add("BRIEF_DUAL_ENTRY", "双入口" in brief and "MPI-01..MPI-08" in brief and "ODR-42" in brief, "brief retains both entry fronts")
    add("BRIEF_UNIT_HOLD", "15 m/s" in brief and "15 mm/s" in brief, "gripper unit conflict retained")
    add("MANIFEST_COUNTS", manifest["output_count"] == 2 and manifest["source_count"] == 2, {"outputs": manifest["output_count"], "sources": manifest["source_count"]})
    manifest_items = manifest["outputs"] + manifest["sources"]
    matched_manifest = 0
    for item in manifest_items:
        path = REPO / item["path"]
        if path.is_file() and path.stat().st_size == item["bytes"] and sha256_file(path) == item["sha256"]:
            matched_manifest += 1
    add("MANIFEST_HASH_CLOSURE", matched_manifest == len(manifest_items), f'{matched_manifest}/{len(manifest_items)}')

    negative_controls: list[dict[str, Any]] = []
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("NC-01_CAD_ENTRY_TRUE", lambda value: value["current_release"].__setitem__("route_c_cad_entry_ready", True)),
        ("NC-02_PRODUCT_SELECTED", lambda value: value["current_release"].__setitem__("route_c_product_selected", True)),
        ("NC-03_MISSION_RELEASE_INJECTED", lambda value: value["current_release"].__setitem__("mission_trajectories_released", 1)),
        ("NC-04_ODR42_SILENT_APPROVAL", lambda value: value["blocking_fronts"][0].__setitem__("state", "PASS")),
        ("NC-05_MPI_SILENT_PASS", lambda value: value["blocking_fronts"][1].__setitem__("state", "PASS")),
        ("NC-06_SIM13_SILENT_REBIND", lambda value: value["blocking_fronts"][3].__setitem__("state", "PASS")),
        ("NC-07_NEXT_STAGE_TRUE", lambda value: value.__setitem__("next_stage_authorized", True)),
        ("NC-08_FACT_COUNT_TAMPER", lambda value: value.__setitem__("facts_confirmed", 7)),
        ("NC-09_TRAJECTORY_TOTAL_TAMPER", lambda value: fact_by_id(value, "LC-04")["evidence"]["counts"].__setitem__("mission_segments_total", 9)),
        ("NC-10_GRIPPER_CONFLICT_CLEARED", lambda value: fact_by_id(value, "LC-05")["evidence"].__setitem__("state", "PASS")),
        ("NC-11_ODR42_EVIDENCE_APPROVED", lambda value: fact_by_id(value, "LC-06")["evidence"].__setitem__("owner_decision", "APPROVED")),
        ("NC-12_SIM13_AUTHORITY_PROMOTED", lambda value: fact_by_id(value, "LC-09")["evidence"]["current_authority"].__setitem__("production_dynamics_ready", True)),
        ("NC-13_RC_CEG_03_EVIDENCE_PASS", lambda value: fact_by_id(value, "LC-02")["evidence"].__setitem__("rc_ceg_03", "PASS")),
    ]
    for control_id, mutate in mutations:
        candidate = copy.deepcopy(gate)
        mutate(candidate)
        detected = not gate_safe(candidate)
        negative_controls.append({"id": control_id, "pass": detected})

    checks_passed = sum(item["pass"] for item in checks)
    negative_passed = sum(item["pass"] for item in negative_controls)
    passed = checks_passed == len(checks) and negative_passed == len(negative_controls)
    report = {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V1",
        "generated_local": gate["generated_local"],
        "scope": "cross-package integrity and fail-closed authority semantics; not a physical release",
        "verdict": "PASS_INTEGRATED_CONTINUATION_INTEGRITY__PRE_CAD_AND_MISSION_HOLD" if passed else "FAIL_INTEGRATED_CONTINUATION_INTEGRITY",
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
    report_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V1.json"
    path = REPO / report_rel
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
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
