"""Independently validate the B601 gripper velocity-unit reconciliation."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

import yaml


REPO = Path(__file__).resolve().parents[4]
BASE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_gripper_velocity_unit_authority"
)
FILES = {
    "contract": f"{BASE_REL}/00_authority/GRIPPER_VELOCITY_UNIT_RECONCILIATION_CONTRACT_V1.yaml",
    "interface": f"{BASE_REL}/01_interface/GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1.yaml",
    "pack_v2": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml"
    ),
    "pointer": f"{BASE_REL}/01_interface/GRIPPER_ACTIVE_CONSUMPTION_POINTER_V1.yaml",
    "gate": f"{BASE_REL}/02_gate/GRIPPER_VELOCITY_UNIT_GATE_V1.json",
    "readme": f"{BASE_REL}/README.md",
    "manifest": f"{BASE_REL}/03_validation/GRIPPER_VELOCITY_UNIT_OUTPUT_MANIFEST_V1.json",
}
EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_yaml(relative_path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO / relative_path).read_text(encoding="utf-8"))


def read_json(relative_path: str) -> dict[str, Any]:
    return json.loads((REPO / relative_path).read_text(encoding="utf-8"))


def find_sms(pack: dict[str, Any], req_id: str) -> dict[str, Any]:
    return next(item for item in pack["sms_requirements"] if item["req_id"] == req_id)


def find_mav(pack: dict[str, Any], check_id: str) -> dict[str, Any]:
    return next(
        item
        for item in pack["mav_analytical_verification"]["checks"]
        if item["check_id"] == check_id
    )


def find_criterion(gate: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    return next(item for item in gate["criteria"] if item["id"] == criterion_id)


def parse_upstream_joints(path: Path) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    output: list[dict[str, Any]] = []
    for name in ("gripper_joint1", "gripper_joint2"):
        matches = [item for item in root.findall("joint") if item.attrib.get("name") == name]
        if len(matches) != 1:
            raise ValueError(f"expected exactly one {name}")
        joint = matches[0]
        limit = joint.find("limit")
        axis = joint.find("axis")
        if limit is None or axis is None:
            raise ValueError(f"{name} has no limit or axis")
        output.append(
            {
                "joint": name,
                "type": joint.attrib.get("type"),
                "axis": [float(x) for x in axis.attrib["xyz"].split()],
                "lower_m": float(limit.attrib["lower"]),
                "upper_m": float(limit.attrib["upper"]),
                "effort_literal": float(limit.attrib["effort"]),
                "velocity_literal_m_s": float(limit.attrib["velocity"]),
            }
        )
    return output


def reconciliation_safe(bundle: dict[str, Any]) -> bool:
    contract = bundle["contract"]
    interface = bundle["interface"]
    gate = bundle["gate"]
    pack_v2 = bundle["pack_v2"]
    pointer = bundle["pointer"]
    physical = contract["physical_capability_authority"]
    m06 = contract["m06_fail_closed_binding"]
    gate_holds = (
        gate["gate"] == "HOLD"
        and gate["next_stage_authorized"] is False
        and gate["release_credit"] is False
        and gate["physical_gripper_timing_ready"] is False
        and gate["m06_physical_contact_ready"] is False
        and gate["production_dynamics_ready"] is False
        and gate["physical_contact_rl_ready"] is False
        and gate["hardware_motion_ready"] is False
    )
    physical_keys = (
        "no_load_speed_m_s",
        "rated_speed_m_s",
        "first_contact_speed_m_s",
        "acceleration_m_s2",
        "command_latency_s",
        "full_stroke_open_time_s",
        "full_stroke_close_time_s",
        "force_speed_curve",
        "duty_cycle",
        "fault_response",
        "standard_uncertainty",
    )
    interface_physical_keys = (
        "no_load_speed_m_s",
        "rated_speed_m_s",
        "first_contact_speed_m_s",
        "acceleration_m_s2",
        "command_latency_s",
        "full_stroke_open_time_s",
        "full_stroke_close_time_s",
        "force_speed_curve",
        "standard_uncertainty",
    )
    m06_keys = (
        "physical_duration_s",
        "jaw_travel_m",
        "contact_time_s",
        "contact_force_N",
        "contact_normal",
        "lock_confirmation",
    )
    target = interface["design_target_layer"]
    ruling = contract["ruling"]
    return (
        contract["immutable_asset"]["sha256"] == EXPECTED_URDF_SHA256
        and contract["immutable_asset"]["modification"] == "FORBIDDEN"
        and contract["observed_urdf_facts"]["velocity_unit"] == "m/s"
        and contract["observed_urdf_facts"]["semantic_model_velocity_limit_m_s"] == 15.0
        and ruling["legacy_15_mm_s_interpretation_valid_for_downstream"] is False
        and ruling["legacy_mav04_times_valid_for_downstream"] is False
        and ruling["physical_timing_authorized"] is False
        and target["first_contact_speed_max_m_s"] == 0.005
        and target["original_value_mm_s"] == 5.0
        and "NOT_MEASURED" in target["role"]
        and target["uncertainty"] is None
        and all(physical[key] is None for key in physical_keys)
        and all(
            interface["physical_actuator_layer"][key] is None
            for key in interface_physical_keys
        )
        and all(m06[key] is None for key in m06_keys)
        and m06["release_credit"] is False
        and interface["contact_sequence_layer"]["jaw_travel_m"] is None
        and interface["contact_sequence_layer"]["contact_time_s"] is None
        and interface["contact_sequence_layer"]["contact_force_N"] is None
        and interface["contact_sequence_layer"]["contact_normal_frame"] is None
        and interface["contact_sequence_layer"]["contact_normal_vector"] is None
        and interface["contact_sequence_layer"]["lock_confirmation_latency_s"] is None
        and interface["next_stage_authorized"] is False
        and interface["release_credit"] is False
        and pack_v2["schema"] == "GRIPPER_ENGINEERING_PACK_V2"
        and "urdf_velocity_limit_mm_s" not in pack_v2["frozen_inputs"]
        and pack_v2["frozen_inputs"]["urdf_velocity_semantic_unit"] == "m/s"
        and pack_v2["frozen_inputs"]["urdf_velocity_semantic_value_m_s"] == 15.0
        and pack_v2["frozen_inputs"]["urdf_velocity_physical_capability_m_s"] is None
        and pack_v2["frozen_inputs"]["urdf_velocity_physical_uncertainty_m_s"] is None
        and find_mav(pack_v2, "MAV-04")["results"]["full_stroke_time_s"] is None
        and find_mav(pack_v2, "MAV-04")["results"]["pregrasp_time_s"] is None
        and find_mav(pack_v2, "MAV-04")["verdict"]
        == "HOLD_NO_PHYSICAL_GRIPPER_SPEED_AUTHORITY"
        and pointer["active_pack"]["path"] == FILES["pack_v2"]
        and pointer["historical_pack"]["consumption"]
        == "HISTORICAL_EVIDENCE_ONLY__NO_NEW_TIMING_DERIVATION"
        and pointer["next_stage_authorized"] is False
        and pointer["release_credit"] is False
        and gate_holds
    )


def main() -> None:
    contract = read_yaml(FILES["contract"])
    interface = read_yaml(FILES["interface"])
    pack_v2 = read_yaml(FILES["pack_v2"])
    pointer = read_yaml(FILES["pointer"])
    gate = read_json(FILES["gate"])
    manifest = read_json(FILES["manifest"])
    readme = (REPO / FILES["readme"]).read_text(encoding="utf-8")
    bundle = {
        "contract": contract,
        "interface": interface,
        "pack_v2": pack_v2,
        "pointer": pointer,
        "gate": gate,
    }
    bindings = {item["name"]: item for item in contract["input_bindings"]}

    upstream_urdf = REPO / bindings["accepted_urdf"]["path"]
    upstream_joints = parse_upstream_joints(upstream_urdf)
    upstream_pack = read_yaml(bindings["gripper_engineering_pack"]["path"])
    upstream_owner = read_yaml(bindings["gripper_owner_closure"]["path"])
    upstream_m4 = read_yaml(bindings["m4_mechanism_release"]["path"])
    upstream_e17_authority = read_yaml(bindings["e17_authority"]["path"])
    upstream_m06 = read_json(bindings["e17_m06"]["path"])
    upstream_e17_gate = read_json(bindings["e17_gate"]["path"])
    upstream_mav04 = find_mav(upstream_pack, "MAV-04")
    upstream_sms06 = find_sms(upstream_pack, "GRP-SMS-06")

    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, evidence: Any) -> None:
        checks.append({"id": check_id, "pass": bool(passed), "evidence": evidence})

    for name, relative_path in FILES.items():
        path = REPO / relative_path
        add(f"FILE_{name.upper()}", path.is_file() and path.stat().st_size > 0, relative_path)

    add(
        "SCHEMAS",
        contract["schema"] == "GRIPPER_VELOCITY_UNIT_RECONCILIATION_CONTRACT_V1"
        and interface["schema"] == "GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1"
        and pack_v2["schema"] == "GRIPPER_ENGINEERING_PACK_V2"
        and pointer["schema"] == "GRIPPER_ACTIVE_CONSUMPTION_POINTER_V1"
        and gate["schema"] == "GRIPPER_VELOCITY_UNIT_GATE_V1"
        and manifest["schema"] == "GRIPPER_VELOCITY_UNIT_OUTPUT_MANIFEST_V1",
        [
            contract["schema"],
            interface["schema"],
            pack_v2["schema"],
            pointer["schema"],
            gate["schema"],
            manifest["schema"],
        ],
    )
    add("INPUT_BINDINGS_7", len(bindings) == 7, len(bindings))
    matched_inputs = 0
    for item in contract["input_bindings"]:
        path = REPO / item["path"]
        if (
            path.is_file()
            and path.stat().st_size == item["bytes"]
            and sha256_file(path) == item["sha256"]
        ):
            matched_inputs += 1
    add("ALL_INPUT_HASHES_MATCH", matched_inputs == len(bindings), f"{matched_inputs}/{len(bindings)}")
    add(
        "URDF_IMMUTABLE_HASH",
        sha256_file(upstream_urdf) == EXPECTED_URDF_SHA256
        and contract["immutable_asset"]["sha256"] == EXPECTED_URDF_SHA256,
        sha256_file(upstream_urdf),
    )
    add(
        "URDF_JOINT_FACTS_REPRODUCED",
        upstream_joints == contract["observed_urdf_facts"]["joints"]
        and all(
            item["type"] == "prismatic"
            and item["axis"] == [1.0, 0.0, 0.0]
            and item["lower_m"] == 0.0
            and item["upper_m"] == 0.0715
            and item["velocity_literal_m_s"] == 15.0
            for item in upstream_joints
        ),
        upstream_joints,
    )
    add(
        "URDF_SI_SEMANTICS_EXPLICIT",
        contract["observed_urdf_facts"]["position_unit"] == "m"
        and contract["observed_urdf_facts"]["velocity_unit"] == "m/s"
        and contract["observed_urdf_facts"]["semantic_role"]
        == "URDF_MODEL_LIMIT_ONLY__NOT_MEASURED_ACTUATOR_CAPABILITY",
        contract["observed_urdf_facts"],
    )
    add(
        "PRIMARY_REFERENCE_BOUND_WITH_SCOPE",
        len(contract["external_references"]) == 2
        and all(item["url"].startswith("https://github.com/") for item in contract["external_references"])
        and all(
            item["record_status"] == "URL_ONLY__NOT_LOCAL_CONTROLLED_COPY"
            for item in contract["external_references"]
        ),
        contract["external_references"],
    )
    add(
        "LEGACY_15_MM_S_OBSERVED",
        upstream_pack["frozen_inputs"]["urdf_velocity_limit_mm_s"] == 15.0
        and upstream_pack["frozen_inputs"]["urdf_limit_role"]
        == "MODEL_LIMIT_NOT_DESIGN_OR_QUALIFICATION_LOAD",
        upstream_pack["frozen_inputs"],
    )
    add(
        "LEGACY_TIMES_REPRODUCED",
        upstream_mav04["results"]["full_stroke_time_s_at_model_velocity"] == 4.767
        and upstream_mav04["results"]["pregrasp_time_s_at_model_velocity"] == 3.667,
        upstream_mav04["results"],
    )
    implied = contract["legacy_record_facts"]["implicit_speed_required_by_legacy_timing_m_s"]
    add(
        "LEGACY_TIMES_REQUIRE_APPROX_0P015_M_S",
        math.isclose(implied["full_stroke"], 0.015, rel_tol=1e-4)
        and math.isclose(implied["pregrasp"], 0.015, rel_tol=1e-4)
        and not math.isclose(implied["full_stroke"], 15.0, rel_tol=1e-4),
        implied,
    )
    semantic_diag = contract["semantic_diagnostic_only"]
    add(
        "SEMANTIC_DIAGNOSTIC_ARITHMETIC",
        math.isclose(
            semantic_diag["full_stroke_time_s_if_literal_model_limit_were_used"],
            0.0715 / 15.0,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        and math.isclose(
            semantic_diag["pregrasp_time_s_if_literal_model_limit_were_used"],
            0.055 / 15.0,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        and "not physical timing" in semantic_diag["use_prohibited"],
        semantic_diag,
    )
    add(
        "SUPERSESSION_NARROW_AND_NONMUTATING",
        len(contract["supersession_scope"]["superseded_for_downstream_consumption"]) == 5
        and contract["supersession_scope"]["historical_files_modified"] is False
        and contract["ruling"]["accepted_urdf_unchanged"] is True,
        contract["supersession_scope"],
    )
    add(
        "DESIGN_TARGET_RETAINED_ONLY_AS_CANDIDATE",
        upstream_sms06["value_max_mm_s"] == 5.0
        and upstream_sms06["classification"] == "DESIGN_TARGET_CANDIDATE"
        and interface["design_target_layer"]["first_contact_speed_max_m_s"] == 0.005
        and "NOT_MEASURED" in interface["design_target_layer"]["role"],
        interface["design_target_layer"],
    )
    pack_v2_mav04 = find_mav(pack_v2, "MAV-04")
    add(
        "PACK_V2_CORRECTED_AND_FAIL_CLOSED",
        "urdf_velocity_limit_mm_s" not in pack_v2["frozen_inputs"]
        and pack_v2["frozen_inputs"]["urdf_velocity_limit_raw"] == 15.0
        and pack_v2["frozen_inputs"]["urdf_velocity_semantic_unit"] == "m/s"
        and pack_v2["frozen_inputs"]["urdf_velocity_physical_capability_m_s"] is None
        and pack_v2["frozen_inputs"]["urdf_velocity_physical_uncertainty_m_s"] is None
        and pack_v2_mav04["results"]["full_stroke_time_s"] is None
        and pack_v2_mav04["results"]["pregrasp_time_s"] is None
        and pack_v2_mav04["verdict"] == "HOLD_NO_PHYSICAL_GRIPPER_SPEED_AUTHORITY"
        and pack_v2["review_status"] == "PENDING_OWNER_REVIEW"
        and pack_v2["next_stage_authorized"] is False,
        {
            "frozen_inputs": pack_v2["frozen_inputs"],
            "mav04": pack_v2_mav04,
        },
    )
    add(
        "ACTIVE_POINTER_HASH_AND_HISTORY_RULE",
        pointer["active_pack"]["path"] == FILES["pack_v2"]
        and pointer["active_pack"]["sha256"] == sha256_file(REPO / FILES["pack_v2"])
        and pointer["historical_pack"]["path"]
        == bindings["gripper_engineering_pack"]["path"]
        and pointer["historical_pack"]["sha256"]
        == bindings["gripper_engineering_pack"]["sha256"]
        and pointer["historical_pack"]["consumption"]
        == "HISTORICAL_EVIDENCE_ONLY__NO_NEW_TIMING_DERIVATION"
        and pointer["next_stage_authorized"] is False,
        pointer,
    )
    add(
        "UPSTREAM_PHYSICAL_HOLDS_REPRODUCED",
        upstream_m4["physical_release_domains"]["actuator_and_transmission"]["status"] == "HOLD"
        and upstream_m4["subgate"]["actuator_capability"] == "HOLD"
        and upstream_owner["verification_summary"]["dynamic"]["open_close_time"]["value"] is None
        and upstream_owner["verification_summary"]["dynamic"]["open_close_time"]["status"]
        == "HOLD_NO_ACTUATOR_DYNAMICS_AUTHORITY"
        and upstream_owner["next_stage_authorized"] is False,
        {
            "m4_actuator": upstream_m4["subgate"]["actuator_capability"],
            "owner_time": upstream_owner["verification_summary"]["dynamic"]["open_close_time"],
        },
    )
    upstream_m06_nulls = [
        upstream_m06[key]
        for key in (
            "physical_duration_s",
            "jaw_travel_m",
            "contact_time_s",
            "contact_force_N",
            "contact_normal",
            "lock_confirmation",
        )
    ]
    add(
        "UPSTREAM_M06_NULLS_REPRODUCED",
        all(value is None for value in upstream_m06_nulls)
        and upstream_m06["released_for_mission_gate"] is False
        and upstream_e17_authority["fail_closed_boundary"]["M06_22"]
        == contract["m06_fail_closed_binding"]["upstream_e17_rule"],
        upstream_m06_nulls,
    )
    add(
        "E17_SEMANTIC_CONFLICT_EXPLICITLY_DISPOSED",
        find_criterion(upstream_e17_gate, "E17-G10")["state"] == "HOLD_UNIT_CONFLICT"
        and contract["legacy_e17_state"]["disposition"]
        == "SUPERSEDED_FOR_SEMANTIC_CONFLICT_ONLY__PHYSICAL_TIMING_HOLD_REMAINS",
        contract["legacy_e17_state"],
    )
    add(
        "PHYSICAL_INPUT_REQUIREMENTS_7",
        [item["id"] for item in contract["required_physical_closure_inputs"]]
        == [f"GVA-PI-{index:02d}" for index in range(1, 8)]
        and all(item["unit"] for item in contract["required_physical_closure_inputs"]),
        contract["required_physical_closure_inputs"],
    )
    add(
        "GATE_CRITERIA_8_OF_8",
        gate["criteria_confirmed"] == gate["criteria_total"] == 8
        and all(item["observed"] is True for item in gate["criteria"]),
        f'{gate["criteria_confirmed"]}/{gate["criteria_total"]}',
    )
    add(
        "EXPECTED_GATE_VERDICT",
        gate["verdict"]
        == "GRIPPER_URDF_UNIT_SEMANTICS_RECONCILED__PHYSICAL_ACTUATOR_SPEED_AND_CONTACT_TIMING_HOLD",
        gate["verdict"],
    )
    add("FAIL_CLOSED_BUNDLE", reconciliation_safe(bundle), gate)
    add(
        "README_BOUNDARY_EXPLICIT",
        "15 m/s" in readme
        and "15 mm/s" in readme
        and "4.767 s / 3.667 s" in readme
        and "null/HOLD" in readme,
        "README contains unit, invalid timing and null/HOLD boundary",
    )
    add(
        "MANIFEST_COUNTS",
        manifest["output_count"] == 6 and manifest["source_count"] == 2,
        {"outputs": manifest["output_count"], "sources": manifest["source_count"]},
    )
    manifest_items = manifest["outputs"] + manifest["sources"]
    matched_manifest = 0
    for item in manifest_items:
        path = REPO / item["path"]
        if (
            path.is_file()
            and path.stat().st_size == item["bytes"]
            and sha256_file(path) == item["sha256"]
        ):
            matched_manifest += 1
    add(
        "MANIFEST_HASH_CLOSURE",
        matched_manifest == len(manifest_items),
        f"{matched_manifest}/{len(manifest_items)}",
    )

    negative_controls: list[dict[str, Any]] = []
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        (
            "NC-01_TREAT_15_M_S_AS_PHYSICAL",
            lambda value: value["contract"]["physical_capability_authority"].__setitem__(
                "rated_speed_m_s", 15.0
            ),
        ),
        (
            "NC-02_TREAT_15_MM_S_AS_PHYSICAL",
            lambda value: value["contract"]["physical_capability_authority"].__setitem__(
                "rated_speed_m_s", 0.015
            ),
        ),
        (
            "NC-03_REINSTATE_LEGACY_TIMING",
            lambda value: value["contract"]["ruling"].__setitem__(
                "legacy_mav04_times_valid_for_downstream", True
            ),
        ),
        (
            "NC-04_ZERO_FILL_UNKNOWN_SPEED",
            lambda value: value["interface"]["physical_actuator_layer"].__setitem__(
                "rated_speed_m_s", 0.0
            ),
        ),
        (
            "NC-05_ALTER_URDF_HASH",
            lambda value: value["contract"]["immutable_asset"].__setitem__("sha256", "0" * 64),
        ),
        (
            "NC-06_PROMOTE_5_MM_S_TO_MEASURED",
            lambda value: value["interface"]["design_target_layer"].__setitem__(
                "role", "MEASURED_CAPABILITY"
            ),
        ),
        (
            "NC-07_NEXT_STAGE_TRUE",
            lambda value: value["gate"].__setitem__("next_stage_authorized", True),
        ),
        (
            "NC-08_CLEAR_M06_NULL",
            lambda value: value["contract"]["m06_fail_closed_binding"].__setitem__(
                "contact_time_s", 0.02
            ),
        ),
        (
            "NC-09_DROP_TARGET_UNCERTAINTY_NULL",
            lambda value: value["interface"]["design_target_layer"].__setitem__(
                "uncertainty", {"standard": 0.0, "unit": "m/s"}
            ),
        ),
        (
            "NC-10_RELEASE_PHYSICAL_TIMING",
            lambda value: value["gate"].__setitem__("physical_gripper_timing_ready", True),
        ),
        (
            "NC-11_RELEASE_CONTACT_RL",
            lambda value: value["gate"].__setitem__("physical_contact_rl_ready", True),
        ),
        (
            "NC-12_REMOVE_MODEL_UNIT",
            lambda value: value["contract"]["observed_urdf_facts"].__setitem__(
                "velocity_unit", ""
            ),
        ),
        (
            "NC-13_RESTORE_V1_MM_S_FIELD_IN_V2",
            lambda value: value["pack_v2"]["frozen_inputs"].__setitem__(
                "urdf_velocity_limit_mm_s", 15.0
            ),
        ),
        (
            "NC-14_FILL_V2_TIMING",
            lambda value: find_mav(value["pack_v2"], "MAV-04")["results"].__setitem__(
                "full_stroke_time_s", 4.767
            ),
        ),
        (
            "NC-15_REACTIVATE_V1",
            lambda value: value["pointer"]["historical_pack"].__setitem__(
                "consumption", "ACTIVE"
            ),
        ),
    ]
    for control_id, mutate in mutations:
        candidate = copy.deepcopy(bundle)
        mutate(candidate)
        negative_controls.append(
            {"id": control_id, "pass": not reconciliation_safe(candidate)}
        )

    checks_passed = sum(item["pass"] for item in checks)
    negative_passed = sum(item["pass"] for item in negative_controls)
    passed = checks_passed == len(checks) and negative_passed == len(negative_controls)
    report = {
        "schema": "GRIPPER_VELOCITY_UNIT_VALIDATION_V1",
        "generated_local": contract["generated_local"],
        "scope": (
            "independent syntax, dimensional, hash and fail-closed validation; "
            "not physical actuator or mission release"
        ),
        "verdict": (
            "PASS_SEMANTIC_RECONCILIATION_INTEGRITY__PHYSICAL_ACTUATOR_SPEED_HOLD"
            if passed
            else "FAIL_GRIPPER_VELOCITY_UNIT_RECONCILIATION_INTEGRITY"
        ),
        "package_integrity_pass": passed,
        "checks": checks,
        "checks_passed": checks_passed,
        "checks_total": len(checks),
        "negative_controls": negative_controls,
        "negative_controls_passed": negative_passed,
        "negative_controls_total": len(negative_controls),
        "semantic_reconciliation": "PASS" if passed else "FAIL",
        "physical_actuator_speed_authority": "HOLD",
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    report_rel = f"{BASE_REL}/03_validation/GRIPPER_VELOCITY_UNIT_VALIDATION_V1.json"
    path = REPO / report_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "checks": f"{checks_passed}/{len(checks)}",
                "negative_controls": f"{negative_passed}/{len(negative_controls)}",
                "validation_sha256": sha256_file(path),
            },
            ensure_ascii=False,
        )
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
