"""Build the fail-closed B601 gripper velocity-unit reconciliation package.

This ECR does not modify the accepted URDF and does not assign physical
actuator capability.  It separates URDF SI syntax from hardware authority and
explicitly prevents the legacy 15 mm/s interpretation from propagating into
mission timing, contact, dynamics, RL or hardware commands.
"""
from __future__ import annotations

import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml


REPO = Path(__file__).resolve().parents[4]
BASE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_gripper_velocity_unit_authority"
)
PACK_V2_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml"
)
GENERATED_LOCAL = "2026-08-23T12:55:00+08:00"

INPUTS = {
    "accepted_urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "gripper_engineering_pack": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V1.yaml"
    ),
    "gripper_owner_closure": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp5_mechanisms/GRIPPER_R1_ENGINEERING_OWNER_CLOSURE_V1.yaml"
    ),
    "m4_mechanism_release": (
        "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/"
        "06_mechanism/GRIPPER_R1_MECHANISM_RELEASE_STATUS_V2.yaml"
    ),
    "e17_authority": (
        "30_simulation/e17_b601_mission_trajectory_candidates/"
        "00_authority/E17_AUTHORITY_CONTRACT_V1.yaml"
    ),
    "e17_m06": (
        "30_simulation/e17_b601_mission_trajectory_candidates/"
        "results/candidates/M06_22_SYMBOLIC_ARM_HOLD_V1.json"
    ),
    "e17_gate": (
        "30_simulation/e17_b601_mission_trajectory_candidates/"
        "results/B601_MISSION_TRAJECTORY_CANDIDATE_GATE_V1.json"
    ),
}

EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
URDF_REFERENCE = {
    "title": "ros/urdfdom - URDF parser and specification support",
    "url": "https://github.com/ros/urdfdom",
    "accessed_local_date": "2026-08-23",
    "record_status": "URL_ONLY__NOT_LOCAL_CONTROLLED_COPY",
    "use": "joint-limit syntax and SI convention context; not hardware qualification authority",
}
PRISMATIC_UNIT_REFERENCE = {
    "title": "Newton URDF-to-USD concept mapping - joint velocity units",
    "url": (
        "https://github.com/newton-physics/urdf-usd-converter/"
        "blob/main/docs/concept_mapping.md"
    ),
    "accessed_local_date": "2026-08-23",
    "record_status": "URL_ONLY__NOT_LOCAL_CONTROLLED_COPY",
    "use": "explicit corroboration that prismatic URDF velocity is m/s",
}


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


def write_yaml(relative_path: str, value: Any) -> None:
    path = REPO / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
        newline="\n",
    )


def write_json(relative_path: str, value: Any) -> None:
    path = REPO / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(relative_path: str, value: str) -> None:
    path = REPO / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")


def bind_inputs() -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for name, relative_path in INPUTS.items():
        path = REPO / relative_path
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"missing or empty input: {relative_path}")
        bindings.append(
            {
                "name": name,
                "path": relative_path,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return bindings


def parse_gripper_joints() -> list[dict[str, Any]]:
    root = ET.parse(REPO / INPUTS["accepted_urdf"]).getroot()
    records: list[dict[str, Any]] = []
    for joint_name in ("gripper_joint1", "gripper_joint2"):
        matches = [
            item
            for item in root.findall("joint")
            if item.attrib.get("name") == joint_name
        ]
        if len(matches) != 1:
            raise ValueError(f"expected exactly one {joint_name}, got {len(matches)}")
        joint = matches[0]
        limit = joint.find("limit")
        axis = joint.find("axis")
        if limit is None or axis is None:
            raise ValueError(f"{joint_name} has no limit or axis")
        records.append(
            {
                "joint": joint_name,
                "type": joint.attrib.get("type"),
                "axis": [float(x) for x in axis.attrib["xyz"].split()],
                "lower_m": float(limit.attrib["lower"]),
                "upper_m": float(limit.attrib["upper"]),
                "effort_literal": float(limit.attrib["effort"]),
                "velocity_literal_m_s": float(limit.attrib["velocity"]),
            }
        )
    return records


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


def build_contract() -> dict[str, Any]:
    pack = read_yaml(INPUTS["gripper_engineering_pack"])
    owner = read_yaml(INPUTS["gripper_owner_closure"])
    m4 = read_yaml(INPUTS["m4_mechanism_release"])
    e17_authority = read_yaml(INPUTS["e17_authority"])
    e17_m06 = read_json(INPUTS["e17_m06"])
    e17_gate = read_json(INPUTS["e17_gate"])
    joints = parse_gripper_joints()
    mav04 = find_mav(pack, "MAV-04")
    sms06 = find_sms(pack, "GRP-SMS-06")

    legacy_full_time = mav04["results"]["full_stroke_time_s_at_model_velocity"]
    legacy_pregrasp_time = mav04["results"]["pregrasp_time_s_at_model_velocity"]
    semantic_full_time = 0.0715 / 15.0
    semantic_pregrasp_time = 0.055 / 15.0

    return {
        "schema": "GRIPPER_VELOCITY_UNIT_RECONCILIATION_CONTRACT_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "record_type": "ENGINEERING_CHANGE_RECORD__SEMANTIC_RECONCILIATION_ONLY",
        "authority_scope": (
            "URDF_UNIT_SEMANTICS_AND_DOWNSTREAM_CONSUMPTION_RULES__"
            "NO_PHYSICAL_ACTUATOR_RELEASE"
        ),
        "decision_rule": "Authority > unit semantics > dimensional consistency > legacy interpretation",
        "evidence_order_rule": (
            "This explicit ECR supersession relation governs the listed fields; wall-clock ordering is not used."
        ),
        "input_bindings": bind_inputs(),
        "external_references": [URDF_REFERENCE, PRISMATIC_UNIT_REFERENCE],
        "immutable_asset": {
            "path": INPUTS["accepted_urdf"],
            "sha256": sha256_file(REPO / INPUTS["accepted_urdf"]),
            "expected_sha256": EXPECTED_URDF_SHA256,
            "modification": "FORBIDDEN",
        },
        "observed_urdf_facts": {
            "joints": joints,
            "position_unit": "m",
            "velocity_unit": "m/s",
            "semantic_model_velocity_limit_m_s": 15.0,
            "source_classification": "UNVALIDATED_AUTO_EXPORTED_MODEL_LIMIT",
            "provenance_note": (
                "The accepted README identifies a vendor-derived gripper chain. A read-only audit found "
                "the earliest external source to be a SolidWorks-to-URDF export, but that original URDF "
                "is absent from the project-controlled 80_third_party snapshot; this classification is "
                "diagnostic and grants no physical authority."
            ),
            "semantic_role": "URDF_MODEL_LIMIT_ONLY__NOT_MEASURED_ACTUATOR_CAPABILITY",
        },
        "legacy_record_facts": {
            "field": "frozen_inputs.urdf_velocity_limit_mm_s",
            "recorded_value_mm_s": pack["frozen_inputs"]["urdf_velocity_limit_mm_s"],
            "recorded_role": pack["frozen_inputs"]["urdf_limit_role"],
            "sms06_design_target_mm_s": sms06["value_max_mm_s"],
            "mav04_full_stroke_time_s": legacy_full_time,
            "mav04_pregrasp_time_s": legacy_pregrasp_time,
            "implicit_speed_required_by_legacy_timing_m_s": {
                "full_stroke": 0.0715 / legacy_full_time,
                "pregrasp": 0.055 / legacy_pregrasp_time,
            },
            "dimensional_scale_error": (
                "legacy timing uses approximately 0.015 m/s, while the URDF literal is 15 m/s"
            ),
        },
        "semantic_diagnostic_only": {
            "full_stroke_m": 0.0715,
            "pregrasp_travel_m": 0.055,
            "literal_velocity_m_s": 15.0,
            "full_stroke_time_s_if_literal_model_limit_were_used": semantic_full_time,
            "pregrasp_time_s_if_literal_model_limit_were_used": semantic_pregrasp_time,
            "use_prohibited": (
                "These arithmetic values demonstrate the unit mismatch only; they are not physical timing, "
                "not a command, and not a trajectory input."
            ),
        },
        "ruling": {
            "semantic_state": (
                "PASS_URDF_PRISMATIC_VELOCITY_IS_15_M_S__"
                "UNVALIDATED_AUTO_EXPORTED_MODEL_LIMIT"
            ),
            "physical_state": "HOLD_NO_ACTUATOR_SPEED_AUTHORITY",
            "combined_state": (
                "SEMANTIC_RECONCILIATION_PASS__PHYSICAL_ACTUATOR_SPEED_AUTHORITY_HOLD"
            ),
            "accepted_urdf_unchanged": True,
            "legacy_15_mm_s_interpretation_valid_for_downstream": False,
            "legacy_mav04_times_valid_for_downstream": False,
            "design_target_5_mm_s_retained": True,
            "design_target_5_mm_s_role": "DESIGN_TARGET_CANDIDATE__NOT_MEASURED_CAPABILITY",
            "physical_timing_authorized": False,
        },
        "supersession_scope": {
            "superseded_for_downstream_consumption": [
                "GRIPPER_ENGINEERING_PACK_V1.frozen_inputs.urdf_velocity_limit_mm_s",
                "GRIPPER_ENGINEERING_PACK_V1.GRP-SMS-06 basis phrase 'URDF 15 mm/s'",
                "GRIPPER_ENGINEERING_PACK_V1.MAV-04 stroke timing and verdict",
                "GRIPPER_R1_ENGINEERING_OWNER_CLOSURE_V1 note phrase 'URDF 100 N / 15 mm/s limits'",
                "E17-G10 HOLD_UNIT_CONFLICT as the current semantic state",
            ],
            "retained_without_upgrade": [
                "GRP-SMS-06 5 mm/s first-contact design target candidate",
                "M4 actuator/transmission HOLD fields",
                "M06_22 null contact/timing/force/normal/lock fields",
                "all prototype, flight, mission, dynamics, RL and hardware release holds",
            ],
            "historical_files_modified": False,
        },
        "physical_capability_authority": {
            "no_load_speed_m_s": None,
            "rated_speed_m_s": None,
            "first_contact_speed_m_s": None,
            "acceleration_m_s2": None,
            "command_latency_s": None,
            "full_stroke_open_time_s": None,
            "full_stroke_close_time_s": None,
            "force_speed_curve": None,
            "duty_cycle": None,
            "fault_response": None,
            "standard_uncertainty": None,
            "status": "HOLD_NULLS_MUST_NOT_BE_ZERO_FILLED",
            "upstream_m4_status": m4["physical_release_domains"]["actuator_and_transmission"]["status"],
            "upstream_owner_time_status": owner["verification_summary"]["dynamic"]["open_close_time"]["status"],
        },
        "m06_fail_closed_binding": {
            "upstream_e17_rule": e17_authority["fail_closed_boundary"]["M06_22"],
            "physical_duration_s": e17_m06["physical_duration_s"],
            "jaw_travel_m": e17_m06["jaw_travel_m"],
            "contact_time_s": e17_m06["contact_time_s"],
            "contact_force_N": e17_m06["contact_force_N"],
            "contact_normal": e17_m06["contact_normal"],
            "lock_confirmation": e17_m06["lock_confirmation"],
            "release_credit": False,
        },
        "legacy_e17_state": {
            "criterion": "E17-G10",
            "state": find_criterion(e17_gate, "E17-G10")["state"],
            "disposition": (
                "SUPERSEDED_FOR_SEMANTIC_CONFLICT_ONLY__PHYSICAL_TIMING_HOLD_REMAINS"
            ),
        },
        "required_physical_closure_inputs": [
            {
                "id": "GVA-PI-01",
                "input": "exact actuator, transmission and reduction-ratio part numbers/revisions",
                "unit": "identifier/revision",
            },
            {
                "id": "GVA-PI-02",
                "input": "force-speed curves across load, bus voltage and temperature",
                "unit": "N versus m/s with V and degC",
            },
            {
                "id": "GVA-PI-03",
                "input": "no-load, rated, first-contact and fault-case jaw speed",
                "unit": "m/s",
            },
            {
                "id": "GVA-PI-04",
                "input": "command-to-motion and sensor/lock-confirmation latency",
                "unit": "s",
            },
            {
                "id": "GVA-PI-05",
                "input": "continuous/peak current, duty cycle, thermal limits and power-off holding behavior",
                "unit": "A, %, degC, N",
            },
            {
                "id": "GVA-PI-06",
                "input": "jaw position/force sensing range, accuracy, update rate and failure coverage",
                "unit": "m, N, Hz, %",
            },
            {
                "id": "GVA-PI-07",
                "input": "instrumented raw bench data, calibration traceability and uncertainty budget",
                "unit": "SI with standard uncertainty and coverage statement",
            },
        ],
        "prohibited_uses": [
            "use 15 m/s as measured or commandable jaw speed",
            "use 15 mm/s as a URDF-derived physical speed",
            "reuse 4.767 s or 3.667 s as physical timing",
            "promote 5 mm/s design target to measured capability",
            "zero-fill any null capability or uncertainty",
            "release M06 contact, production dynamics, physical-contact RL or hardware motion",
        ],
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_pack_v2(contract: dict[str, Any], contract_rel: str) -> dict[str, Any]:
    """Create a versioned active pack while retaining V1 as historical evidence."""
    pack = copy.deepcopy(read_yaml(INPUTS["gripper_engineering_pack"]))
    pack["schema"] = "GRIPPER_ENGINEERING_PACK_V2"
    pack["generated_local"] = GENERATED_LOCAL
    pack["supersedes"] = {
        "artifact": INPUTS["gripper_engineering_pack"],
        "scope": "velocity-unit semantics and MAV-04 timing only",
        "historical_artifact_modified": False,
        "reason": (
            "V1 silently relabeled the URDF prismatic velocity literal 15 from m/s to mm/s."
        ),
    }
    pack["overall_status"] = (
        "DESIGN_CANDIDATE_SEMANTIC_CORRECTED__"
        "PHYSICAL_ACTUATOR_PROTOTYPE_AND_FLIGHT_RELEASE_HOLD"
    )
    pack["review_status"] = "PENDING_OWNER_REVIEW"
    pack["next_stage_authorized"] = False
    frozen = pack["frozen_inputs"]
    frozen.pop("urdf_velocity_limit_mm_s", None)
    frozen["urdf_velocity_limit_raw"] = 15.0
    frozen["urdf_velocity_semantic_unit"] = "m/s"
    frozen["urdf_velocity_semantic_value_m_s"] = 15.0
    frozen["urdf_velocity_source_classification"] = (
        "UNVALIDATED_AUTO_EXPORTED_MODEL_LIMIT"
    )
    frozen["urdf_velocity_physical_capability_m_s"] = None
    frozen["urdf_velocity_physical_uncertainty_m_s"] = None
    frozen["urdf_limit_role"] = (
        "MODEL_LIMIT_NOT_DESIGN_COMMAND_OR_QUALIFICATION_LOAD"
    )

    sms06 = find_sms(pack, "GRP-SMS-06")
    sms06["basis"] = (
        "limit contact kinetic energy ahead of the capture impulse envelope; "
        "5 mm/s is an independent design target candidate. The URDF literal 15 has "
        "SI syntax 15 m/s but is an unvalidated auto-exported model limit and supplies "
        "no physical capability or timing authority"
    )
    mav04 = find_mav(pack, "MAV-04")
    mav04["title"] = "stroke timing authority"
    mav04["method"] = (
        "physical timing requires a controlled actuator/transmission mapping and "
        "instrumented force-speed/latency data; URDF velocity is excluded"
    )
    mav04["results"] = {
        "full_stroke_time_s": None,
        "pregrasp_time_s": None,
        "physical_velocity_m_s": None,
        "physical_velocity_standard_uncertainty_m_s": None,
        "closing_speed_at_first_contact_design_target_mm_s": 5.0,
        "design_target_role": "DESIGN_TARGET_CANDIDATE__NOT_MEASURED_CAPABILITY",
        "urdf_literal_full_stroke_time_diagnostic_s": 0.0715 / 15.0,
        "urdf_literal_pregrasp_time_diagnostic_s": 0.055 / 15.0,
        "diagnostic_use": (
            "DIMENSIONAL_MISMATCH_DEMONSTRATION_ONLY__NOT_PHYSICAL_TIMING_OR_COMMAND"
        ),
    }
    mav04["verdict"] = "HOLD_NO_PHYSICAL_GRIPPER_SPEED_AUTHORITY"
    retained = pack["retained_holds"]
    if "PHYSICAL_GRIPPER_SPEED_AND_TIMING_HOLD" not in retained:
        retained.append("PHYSICAL_GRIPPER_SPEED_AND_TIMING_HOLD")
    pack["unit_reconciliation"] = {
        "authority_record": contract_rel,
        "authority_record_sha256": sha256_file(REPO / contract_rel),
        "combined_state": contract["ruling"]["combined_state"],
        "active_downstream_rule": (
            "new consumers shall bind V2 plus the reconciliation gate; V1 is historical only"
        ),
    }
    pack["source_register"].append(
        {
            "path": contract_rel,
            "sha256": sha256_file(REPO / contract_rel),
        }
    )
    return pack


def build_interface(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_class": "CANDIDATE_INTERFACE__FAIL_CLOSED",
        "joint_coordinate_contract": {
            "joint_names": ["gripper_joint1", "gripper_joint2"],
            "joint_type": "prismatic",
            "position_unit": "m",
            "velocity_unit": "m/s",
            "acceleration_unit": "m/s^2",
            "axis_each_in_parent_joint_frame": [1.0, 0.0, 0.0],
            "position_range_each_m": [0.0, 0.0715],
            "symmetry": "two independent URDF prismatic coordinates; coupling/transmission authority HOLD",
        },
        "model_layer": {
            "urdf_velocity_limit_literal_m_s": 15.0,
            "role": "MODEL_LIMIT_ONLY",
            "accepted_urdf_sha256": contract["immutable_asset"]["sha256"],
        },
        "design_target_layer": {
            "first_contact_speed_max_m_s": 0.005,
            "original_value_mm_s": 5.0,
            "role": "DESIGN_TARGET_CANDIDATE__NOT_MEASURED_CAPABILITY",
            "uncertainty": None,
        },
        "physical_actuator_layer": {
            "no_load_speed_m_s": None,
            "rated_speed_m_s": None,
            "first_contact_speed_m_s": None,
            "acceleration_m_s2": None,
            "command_latency_s": None,
            "full_stroke_open_time_s": None,
            "full_stroke_close_time_s": None,
            "force_speed_curve": None,
            "standard_uncertainty": None,
            "status": "HOLD_PENDING_GVA_PI_01_THROUGH_07",
        },
        "contact_sequence_layer": {
            "states": ["PREGRASP", "CONTACT", "LOCK"],
            "jaw_travel_m": None,
            "contact_time_s": None,
            "contact_force_N": None,
            "contact_normal_frame": None,
            "contact_normal_vector": None,
            "lock_confirmation_latency_s": None,
            "status": "HOLD_TARGET_INTERFACE_AND_BENCH_AUTHORITY_ABSENT",
        },
        "consumer_rules": {
            "kinematic_visualization": (
                "may consume position range; model velocity only if explicitly labeled nonphysical"
            ),
            "mission_trajectory": "must not derive duration from URDF velocity; remain HOLD",
            "contact_dynamics": "must consume measured force-speed/contact inputs; remain HOLD",
            "physics_gated_rl": "UNKNOWN/HOLD must map to veto; no substitution or zero-fill",
            "hardware_control": "must consume qualified limits from controlled actuator data; remain HOLD",
        },
        "units_and_uncertainty_rule": (
            "Every physical value shall carry an SI unit, authority class and uncertainty. "
            "Unknown values remain null with a named closure input."
        ),
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_gate(
    contract: dict[str, Any], interface: dict[str, Any], pack_v2: dict[str, Any]
) -> dict[str, Any]:
    physical = contract["physical_capability_authority"]
    m06 = contract["m06_fail_closed_binding"]
    criteria = [
        {
            "id": "GVA-G01",
            "name": "accepted URDF immutable hash",
            "state": "PASS",
            "observed": (
                contract["immutable_asset"]["sha256"] == EXPECTED_URDF_SHA256
                and contract["immutable_asset"]["modification"] == "FORBIDDEN"
            ),
            "release_credit": False,
        },
        {
            "id": "GVA-G02",
            "name": "two gripper joints are prismatic with SI limits",
            "state": "PASS",
            "observed": all(
                item["type"] == "prismatic"
                and item["lower_m"] == 0.0
                and item["upper_m"] == 0.0715
                and item["velocity_literal_m_s"] == 15.0
                for item in contract["observed_urdf_facts"]["joints"]
            ),
            "release_credit": False,
        },
        {
            "id": "GVA-G03",
            "name": "legacy millimetre-per-second interpretation rejected",
            "state": "PASS",
            "observed": (
                contract["ruling"]["legacy_15_mm_s_interpretation_valid_for_downstream"]
                is False
                and contract["ruling"]["legacy_mav04_times_valid_for_downstream"] is False
            ),
            "release_credit": False,
        },
        {
            "id": "GVA-G04",
            "name": "5 mm/s remains design target only",
            "state": "PASS_WITH_CANDIDATE_SCOPE",
            "observed": (
                interface["design_target_layer"]["first_contact_speed_max_m_s"] == 0.005
                and "NOT_MEASURED" in interface["design_target_layer"]["role"]
            ),
            "release_credit": False,
        },
        {
            "id": "GVA-G05",
            "name": "physical speed timing and uncertainty remain null",
            "state": "HOLD",
            "observed": all(
                physical[key] is None
                for key in (
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
            ),
            "release_credit": False,
        },
        {
            "id": "GVA-G06",
            "name": "M06 physical contact fields remain null",
            "state": "HOLD",
            "observed": all(
                m06[key] is None
                for key in (
                    "physical_duration_s",
                    "jaw_travel_m",
                    "contact_time_s",
                    "contact_force_N",
                    "contact_normal",
                    "lock_confirmation",
                )
            ),
            "release_credit": False,
        },
        {
            "id": "GVA-G07",
            "name": "physical closure input set complete",
            "state": "PASS_REQUIREMENT_DEFINITION_ONLY",
            "observed": (
                [item["id"] for item in contract["required_physical_closure_inputs"]]
                == [f"GVA-PI-{index:02d}" for index in range(1, 8)]
            ),
            "release_credit": False,
        },
        {
            "id": "GVA-G08",
            "name": "all downstream releases remain fail closed",
            "state": "HOLD",
            "observed": (
                contract["next_stage_authorized"] is False
                and contract["release_credit"] is False
                and interface["next_stage_authorized"] is False
                and interface["release_credit"] is False
            ),
            "release_credit": False,
        },
    ]
    criteria_confirmed = sum(item["observed"] for item in criteria)
    return {
        "schema": "GRIPPER_VELOCITY_UNIT_GATE_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_scope": contract["authority_scope"],
        "active_engineering_pack": {
            "path": PACK_V2_REL,
            "sha256": sha256_file(REPO / PACK_V2_REL),
            "schema": pack_v2["schema"],
            "review_status": pack_v2["review_status"],
            "next_stage_authorized": pack_v2["next_stage_authorized"],
        },
        "criteria": criteria,
        "criteria_total": len(criteria),
        "criteria_confirmed": criteria_confirmed,
        "semantic_reconciliation": (
            "PASS" if all(item["observed"] for item in criteria[:4]) else "FAIL"
        ),
        "physical_actuator_speed_authority": "HOLD",
        "physical_gripper_timing_ready": False,
        "m06_physical_contact_ready": False,
        "production_dynamics_ready": False,
        "physical_contact_rl_ready": False,
        "hardware_motion_ready": False,
        "verdict": (
            "GRIPPER_URDF_UNIT_SEMANTICS_RECONCILED__"
            "PHYSICAL_ACTUATOR_SPEED_AND_CONTACT_TIMING_HOLD"
            if criteria_confirmed == len(criteria)
            else "GRIPPER_VELOCITY_UNIT_RECONCILIATION_INTEGRITY_HOLD"
        ),
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
        "exit_condition": (
            "Close GVA-PI-01..07 with controlled vendor and instrumented bench evidence, "
            "then issue a separately reviewed physical actuator-characterization gate."
        ),
    }


def build_readme(gate: dict[str, Any]) -> str:
    return f"""
# B601 夹爪速度单位权威纠偏 ECR

## 机器结论

`{gate['verdict']}`

## 已关闭的问题

- accepted URDF 中 `gripper_joint1/2` 均为移动副，`velocity=15` 的模型语义为 **15 m/s**。
- 既有 M7 文件把该值解释成 15 mm/s，并据此计算 4.767 s / 3.667 s；这两项不得再作为下游物理时序。
- accepted URDF 未被修改；本 ECR 只纠正解释与消费规则。
- 新的活跃候选为 `wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml`；V1 仅保留为历史证据。

## 仍未关闭的问题

- 15 m/s 只是 URDF 模型上限，不是实测或可指令硬件速度。
- 5 mm/s 仍只是首次接触速度设计目标候选，不是实测能力。
- 真实力—速曲线、时延、占空比、故障响应、开合时间及其不确定度全部保持 `null/HOLD`。
- M06_22 的夹爪行程、接触时间、接触力、法向和锁定确认继续保持 `null/HOLD`。

## 下游规则

动力学、接触、具身强化学习及硬件控制不得从 URDF 速度推导物理时序，也不得用零填充未知量。只有 GVA-PI-01..07 全部受控并通过独立执行器表征 Gate 后，才可生成新的物理夹爪时序。
"""


def main() -> None:
    contract_rel = f"{BASE_REL}/00_authority/GRIPPER_VELOCITY_UNIT_RECONCILIATION_CONTRACT_V1.yaml"
    interface_rel = f"{BASE_REL}/01_interface/GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1.yaml"
    pointer_rel = f"{BASE_REL}/01_interface/GRIPPER_ACTIVE_CONSUMPTION_POINTER_V1.yaml"
    gate_rel = f"{BASE_REL}/02_gate/GRIPPER_VELOCITY_UNIT_GATE_V1.json"
    readme_rel = f"{BASE_REL}/README.md"
    manifest_rel = f"{BASE_REL}/03_validation/GRIPPER_VELOCITY_UNIT_OUTPUT_MANIFEST_V1.json"

    contract = build_contract()
    interface = build_interface(contract)
    write_yaml(contract_rel, contract)
    write_yaml(interface_rel, interface)
    pack_v2 = build_pack_v2(contract, contract_rel)
    write_yaml(PACK_V2_REL, pack_v2)
    pointer = {
        "schema": "GRIPPER_ACTIVE_CONSUMPTION_POINTER_V1",
        "generated_local": GENERATED_LOCAL,
        "active_pack": {
            "path": PACK_V2_REL,
            "sha256": sha256_file(REPO / PACK_V2_REL),
            "schema": pack_v2["schema"],
        },
        "required_companion_gate": {
            "path": gate_rel,
            "hash_binding": "BOUND_AFTER_GATE_GENERATION_IN_OUTPUT_MANIFEST",
        },
        "historical_pack": {
            "path": INPUTS["gripper_engineering_pack"],
            "sha256": sha256_file(REPO / INPUTS["gripper_engineering_pack"]),
            "consumption": "HISTORICAL_EVIDENCE_ONLY__NO_NEW_TIMING_DERIVATION",
        },
        "existing_downstream_artifacts": (
            "historical and not retroactively rewritten; rebuild/rebind required before release credit"
        ),
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_yaml(pointer_rel, pointer)
    gate = build_gate(contract, interface, pack_v2)
    write_json(gate_rel, gate)
    write_text(readme_rel, build_readme(gate))

    outputs = [contract_rel, interface_rel, PACK_V2_REL, pointer_rel, gate_rel, readme_rel]
    sources = [
        f"{BASE_REL}/99_tools/build_gripper_velocity_unit_reconciliation.py",
        f"{BASE_REL}/99_tools/validate_gripper_velocity_unit_reconciliation.py",
    ]
    manifest = {
        "schema": "GRIPPER_VELOCITY_UNIT_OUTPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "hash_algorithm": "SHA-256",
        "outputs": [
            {
                "path": item,
                "sha256": sha256_file(REPO / item),
                "bytes": (REPO / item).stat().st_size,
            }
            for item in outputs
        ],
        "sources": [
            {
                "path": item,
                "sha256": sha256_file(REPO / item),
                "bytes": (REPO / item).stat().st_size,
            }
            for item in sources
        ],
        "output_count": len(outputs),
        "source_count": len(sources),
        "validation_report_excluded_to_avoid_recursive_hash": True,
    }
    write_json(manifest_rel, manifest)
    print(
        json.dumps(
            {
                "verdict": gate["verdict"],
                "criteria": f'{gate["criteria_confirmed"]}/{gate["criteria_total"]}',
                "gate_sha256": sha256_file(REPO / gate_rel),
                "manifest_sha256": sha256_file(REPO / manifest_rel),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
