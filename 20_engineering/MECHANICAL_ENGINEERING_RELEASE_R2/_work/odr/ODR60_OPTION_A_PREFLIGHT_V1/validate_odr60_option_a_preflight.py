"""Read-only ODR-60 Option-A readiness validator.

This program verifies hashes, endpoint/URDF consistency and collision-semantics
normalization.  It never generates, searches, smooths or writes a trajectory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import yaml


HERE = Path(__file__).resolve().parent
INPUTS = HERE / "ODR60_OPTION_A_PREFLIGHT_INPUTS_V1.json"
COLLISION = HERE / "M01_COLLISION_SEMANTICS_DRAFT_V1.yaml"
EXPECTED_ADJACENT = [
    ["base_link", "link1"],
    ["link1", "link2"],
    ["link2", "link3"],
    ["link3", "link4"],
    ["link4", "link5"],
    ["link5", "link6"],
    ["link6", "gripper_link"],
    ["gripper_link", "gripper_left"],
    ["gripper_link", "gripper_right"],
]
EXPECTED_LIMITS = {
    "joint1": (-2.8, 2.8),
    "joint2": (-3.14, 0.0),
    "joint3": (-3.14, 0.0),
    "joint4": (-1.87, 1.57),
    "joint5": (-1.57, 1.57),
    "joint6": (-3.14, 3.14),
}


def workspace_root() -> Path:
    for candidate in [HERE, *HERE.parents]:
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root not found")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_documents() -> tuple[dict, dict]:
    return (
        json.loads(INPUTS.read_text(encoding="utf-8")),
        yaml.safe_load(COLLISION.read_text(encoding="utf-8")),
    )


def runtime_memory() -> dict:
    try:
        import psutil

        vm = psutil.virtual_memory()
        available_gib = vm.available / 1024**3
        total_gib = vm.total / 1024**3
        nominal = available_gib >= 6.0
        return {
            "measured": True,
            "total_physical_gib": total_gib,
            "available_physical_gib": available_gib,
            "nominal_six_gib_available": nominal,
            "memory_gate_passed": nominal,
            "memory_gate_status": (
                "PASS_NOMINAL_AVAILABLE_MEMORY"
                if nominal
                else "FRESH_RUN_SPECIFIC_OWNER_OVERRIDE_REQUIRED__NOT_A_MEMORY_GATE_PASS"
            ),
            "required_low_memory_confirmation": (
                None if nominal else "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK"
            ),
        }
    except Exception as exc:  # fail closed on unavailable telemetry
        return {
            "measured": False,
            "error": type(exc).__name__,
            "nominal_six_gib_available": False,
            "memory_gate_passed": False,
            "memory_gate_status": "UNKNOWN_ABORT",
            "required_low_memory_confirmation": "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK",
        }


def evaluate() -> dict:
    root = workspace_root()
    inputs, collision = load_documents()
    integrity_errors: list[str] = []

    pin_count = 0
    for group in (inputs["input_pins"], collision["input_pins"]):
        for name, pin in group.items():
            pin_count += 1
            path = root / pin["path"]
            if not path.is_file():
                integrity_errors.append(f"missing pin {name}: {pin['path']}")
                continue
            actual = sha256(path)
            if actual != pin["sha256"]:
                integrity_errors.append(
                    f"hash mismatch {name}: expected {pin['sha256']} actual {actual}"
                )

    urdf_path = root / inputs["input_pins"]["accepted_b601_urdf"]["path"]
    robot = ET.parse(urdf_path).getroot()
    links = [node.attrib["name"] for node in robot.findall("link")]
    joints = robot.findall("joint")
    revolute = [j for j in joints if j.attrib["type"] == "revolute"]
    prismatic = [j for j in joints if j.attrib["type"] == "prismatic"]
    observed_limits = {}
    for joint in revolute:
        limit = joint.find("limit")
        observed_limits[joint.attrib["name"]] = (
            float(limit.attrib["lower"]),
            float(limit.attrib["upper"]),
        )
    limits_match = observed_limits == EXPECTED_LIMITS
    if not limits_match:
        integrity_errors.append("accepted URDF revolute limits differ from frozen limits")

    mission_path = root / inputs["input_pins"]["mission_trajectory_contract"]["path"]
    mission = yaml.safe_load(mission_path.read_text(encoding="utf-8"))
    collision_authority_path = (
        root / inputs["input_pins"]["option_a_collision_authority_gate"]["path"]
    )
    collision_authority = json.loads(
        collision_authority_path.read_text(encoding="utf-8")
    )
    proxy_receipt_path = root / inputs["input_pins"]["base_link_proxy_v2_receipt"]["path"]
    proxy_validation_path = (
        root / inputs["input_pins"]["base_link_proxy_v2_validation"]["path"]
    )
    proxy_receipt = json.loads(proxy_receipt_path.read_text(encoding="utf-8"))
    proxy_validation = json.loads(proxy_validation_path.read_text(encoding="utf-8"))
    system_registry_path = (
        root / inputs["input_pins"]["system_collision_registry"]["path"]
    )
    system_registry = json.loads(system_registry_path.read_text(encoding="utf-8"))
    endpoint = inputs["fixed_m01_endpoint_contract"]
    start_match = mission["states"]["STOW"]["q_rad"] == endpoint["q_start"]
    goal_match = mission["states"]["RELEASE_CLEAR"]["q_rad"] == endpoint["q_goal"]
    if not start_match or not goal_match:
        integrity_errors.append("M01 endpoint mismatch")

    inset = float(endpoint["robust_joint_limit_inset_rad"])
    endpoint_margin = math.inf
    endpoint_inside_inset = True
    for q in (endpoint["q_start"], endpoint["q_goal"]):
        for value, joint_name in zip(q, endpoint["joint_order"]):
            lower, upper = EXPECTED_LIMITS[joint_name]
            margin = min(value - lower, upper - value)
            endpoint_margin = min(endpoint_margin, margin)
            endpoint_inside_inset &= margin >= inset
    if not endpoint_inside_inset:
        integrity_errors.append("endpoint violates robust joint-limit inset")

    adjacent = collision["adjacent_link_exclusions"]["pairs"]
    adjacent_match = adjacent == EXPECTED_ADJACENT
    if not adjacent_match:
        integrity_errors.append("adjacent-link exclusion set drift")
    finger_enabled = (
        collision["adjacent_link_exclusions"]["finger_pair"]["collision_check"]
        == "MUST_REMAIN_ENABLED"
    )
    if not finger_enabled:
        integrity_errors.append("finger self-collision was disabled")

    rules = collision["route_c_cable_serving_hardware_rules"]["rules"]
    rule_ids = [rule["rule_id"] for rule in rules]
    rule_count_ok = len(rules) == 15 and len(set(rule_ids)) == 15
    windows_ok = all(
        len(rule["s_window_mm"]) == 2
        and all(math.isfinite(float(x)) for x in rule["s_window_mm"])
        and float(rule["s_window_mm"][1]) >= float(rule["s_window_mm"][0])
        and bool(rule["allowed_part_ids"])
        and bool(rule["witness_clamp_id"])
        for rule in rules
    )
    j4_wholesale_forbidden = not collision["route_c_cable_serving_hardware_rules"][
        "j4_whole_segment_exemption_allowed"
    ]
    if not rule_count_ok or not windows_ok or not j4_wholesale_forbidden:
        integrity_errors.append("Route-C exact interface-rule normalization failed")

    universe = collision["system_collision_universe"]
    registry_objects = system_registry["objects"]
    registry_object_ids = [item["object_id"] for item in registry_objects]
    object_counts: dict[str, int] = {}
    for item in registry_objects:
        category = item["category"]
        object_counts[category] = object_counts.get(category, 0) + 1
    universe_ok = (
        len(registry_objects) == 150
        and len(set(registry_object_ids)) == 150
        and object_counts == {"F": 4, "A": 10, "S": 6, "R": 121, "C": 9}
        and universe["unordered_pair_count"] == 11175
        and universe["adjacent_pair_exceptions"] == 9
        and universe["non_excepted_unassessed_fail_closed"] == 11166
        and universe["conditional_solar_keepout_candidates_not_yet_activated"] == 10
        and universe["raw_urdf_base_link_mesh_consumed"] is False
        and universe["fixed_route_c_own_host_object_skip_inherited"] is False
    )
    authority_registry = collision_authority["system_registry"]
    authority_consistent = (
        collision_authority["structural_registry_pass"] is True
        and collision_authority["proxy_pass"] is True
        and authority_registry["known_active_object_count"] == 150
        and authority_registry["pair_count"] == 11175
        and authority_registry["excepted_pair_count"] == 9
        and authority_registry["unassessed_fail_closed_pair_count"] == 11166
        and collision_authority["path_search_executed"] is False
        and collision_authority["path_search_authorized"] is False
        and collision_authority["pre_search_ready"] is False
        and collision_authority["complete_hash_bound_acm"] is False
        and collision_authority["complete_system_collision_pass"] is False
        and collision_authority["next_stage_authorized"] is False
        and collision_authority["release_credit"] is False
    )
    proxy_evidence_consistent = (
        proxy_receipt["schema"] == "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2"
        and all(value is True for value in proxy_receipt["checks"].values())
        and proxy_receipt["system_pair_evaluation_authorized"] is False
        and proxy_receipt["path_search_authorized"] is False
        and proxy_receipt["next_stage_authorized"] is False
        and proxy_receipt["release_credit"] is False
        and proxy_validation["schema"]
        == "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V2"
        and all(value is True for value in proxy_validation["checks"].values())
        and proxy_validation["system_pair_evaluation_authorized"] is False
        and proxy_validation["path_search_authorized"] is False
        and proxy_validation["next_stage_authorized"] is False
        and proxy_validation["release_credit"] is False
    )
    legacy_rejection_ok = (
        collision["route_c_cable_serving_hardware_rules"][
            "expanded_candidate_object_pair_window_records"
        ]
        == 55
        and collision["route_c_cable_serving_hardware_rules"][
            "candidate_windows_active_as_pair_exceptions"
        ]
        is False
        and collision["route_c_cable_serving_hardware_rules"][
            "legacy_non_j4_segment_wide_sets_rejected"
        ]
        == 8
        and collision["route_c_cable_serving_hardware_rules"][
            "legacy_segment_part_memberships_rejected"
        ]
        == 91
    )
    if not universe_ok or not authority_consistent:
        integrity_errors.append("system collision universe or aggregate gate drift")
    if not proxy_evidence_consistent:
        integrity_errors.append("base_link V2 proxy receipt or validation drift")
    if not legacy_rejection_ok:
        integrity_errors.append("legacy segment-wide collision-exemption audit drift")

    explicit_scene_fields = [
        "gripper_joint1_m",
        "gripper_joint2_m",
        "solar_r2_configuration",
        "solar_hdrm_latch_state",
        "arm_hdrm_state_at_t0_minus",
        "arm_hdrm_state_at_t0_plus",
        "mechanical_constraint_release_snapshot",
        "target_present",
        "target_attached",
    ]
    missing_scene_fields = [
        name
        for name in explicit_scene_fields
        if inputs["scene_state_bindings"][name]["value"] is None
    ]
    memory = runtime_memory()
    owner_authority = bool(inputs["owner_option_a_selected"])
    base_raw_conflict_contained = bool(
        collision["gate"]["base_link_raw_mesh_conflict_contained"]
    )
    base_proxy_pass = bool(
        collision_authority["proxy_pass"]
        and collision["gate"]["base_link_operational_proxy_pass"]
        and proxy_evidence_consistent
    )
    complete_acm = bool(collision_authority["complete_hash_bound_acm"])
    complete_system_collision = bool(
        collision_authority["complete_system_collision_pass"]
    )

    blockers = []
    if not owner_authority:
        blockers.append("ODR60_OPTION_A_OWNER_SELECTION_ABSENT")
    if missing_scene_fields:
        blockers.append("M01_SCENE_STATE_BINDINGS_INCOMPLETE")
    if not base_proxy_pass:
        blockers.append("BASE_LINK_OPERATIONAL_COLLISION_PROXY_HOLD")
    if not complete_acm:
        blockers.append("COMPLETE_HASH_BOUND_ACM_ABSENT")
    if not complete_system_collision:
        blockers.append("COMPLETE_SYSTEM_COLLISION_BACKEND_AND_COVERAGE_ABSENT")
    if not memory["nominal_six_gib_available"]:
        blockers.append("RUNTIME_MEMORY_NOT_NOMINALLY_ADMITTED")
    blockers.extend(
        [
            "SIDE_EFFECT_FREE_EXACT_Q_ADAPTER_ABSENT",
            "CONTINUOUS_EDGE_CERTIFICATE_METHOD_ABSENT",
        ]
    )

    package_integrity_pass = not integrity_errors
    pre_search_ready = package_integrity_pass and not blockers
    return {
        "schema": "ODR60_OPTION_A_PREFLIGHT_VALIDATION_STDOUT_V1",
        "authority": "READ_ONLY_VALIDATOR__NO_PATH_SEARCH",
        "package_integrity_pass": package_integrity_pass,
        "integrity_pin_occurrences_checked": pin_count,
        "integrity_errors": integrity_errors,
        "urdf": {
            "robot": robot.attrib.get("name"),
            "links": len(links),
            "joints": len(joints),
            "revolute": len(revolute),
            "prismatic": len(prismatic),
            "limits_match": limits_match,
        },
        "endpoints": {
            "start_match": start_match,
            "goal_match": goal_match,
            "robust_inset_pass": endpoint_inside_inset,
            "minimum_margin_rad": endpoint_margin,
            "semantics": endpoint["endpoint_semantics"],
        },
        "collision_semantics": {
            "adjacent_pair_count": len(adjacent),
            "adjacent_pairs_match": adjacent_match,
            "finger_pair_collision_enabled": finger_enabled,
            "route_c_interface_rule_count": len(rules),
            "route_c_interface_rules_normalized": rule_count_ok and windows_ok,
            "candidate_local_window_pair_records": 55,
            "candidate_windows_active_as_exceptions": False,
            "legacy_segment_wide_groups_rejected": 8,
            "legacy_segment_part_memberships_rejected": 91,
            "j4_whole_segment_exemption_forbidden": j4_wholesale_forbidden,
            "known_active_object_count": len(registry_objects),
            "object_counts": object_counts,
            "pair_universe_count": 11175,
            "adjacent_pair_exceptions": 9,
            "unassessed_fail_closed_pairs": 11166,
            "conditional_solar_keepouts_not_activated": 10,
            "raw_urdf_base_link_mesh_consumed": False,
            "base_link_raw_mesh_conflict_contained": base_raw_conflict_contained,
            "base_link_operational_proxy_pass": base_proxy_pass,
            "base_link_v2_receipt_and_validation_consistent": proxy_evidence_consistent,
            "complete_hash_bound_acm": complete_acm,
            "complete_system_collision_pass": complete_system_collision,
        },
        "scene_state": {
            "required_fields": explicit_scene_fields,
            "missing_fields": missing_scene_fields,
            "complete": not missing_scene_fields,
        },
        "runtime_memory": memory,
        "owner_authority_present": owner_authority,
        "pre_search_ready": pre_search_ready,
        "blockers": blockers,
        "verdict": (
            "ODR60_OPTION_A_PREFLIGHT_READY_FOR_OWNER_AUTHORIZED_SEARCH"
            if pre_search_ready
            else "ODR60_OPTION_A_PRE_SEARCH_HOLD__NO_PATH_SEARCH"
        ),
        "system_pair_evaluation_authorized": False,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=None if args.compact else 2,
        )
    )
    return 0 if result["package_integrity_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
