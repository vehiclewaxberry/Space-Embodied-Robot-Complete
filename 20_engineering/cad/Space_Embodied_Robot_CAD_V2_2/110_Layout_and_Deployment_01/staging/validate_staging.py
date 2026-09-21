"""Deterministic Gate 5/6 validation for V22 isolated staging."""

from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

from build123d import Compound, Location, import_step

import layout_staging as staging


ROOT = Path(__file__).resolve().parent
TASK_ROOT = ROOT.parent
WORKSPACE = staging.V22_ROOT.parents[2]
RESULT_PATH = TASK_ROOT / "validation" / "staging_validation.json"
TOL = 1.0e-6

CANONICAL_TOP = (
    staging.V22_ROOT
    / "Assembly"
    / "Spacecraft_Service_Vehicle_V2_2.SLDASM"
)
PRIOR_STEP = (
    staging.V22_ROOT
    / "100_Mechanical_Continuation"
    / "v22_mechanical_continuation.step"
)
ACCEPTED_URDF = (
    staging.CAD_ROOT
    / "spacecraft_layout"
    / "arm_b601_v1"
    / "arm_b601_v1.urdf"
)
DECISION_CONTRACT = TASK_ROOT / "design" / "layout_decision_contract.json"
CURRENT_SUBSYSTEM_CONTRACTS = {
    "solar_contract_sha256": (
        TASK_ROOT / "solar" / "solar_deployment_contract.json"
    ),
    "arm_stow_contract_sha256": (
        TASK_ROOT / "arm_stow" / "interface_claim_registry.json"
    ),
}

EXPECTED_HASHES = {
    "canonical_top": (
        CANONICAL_TOP,
        "3b55edb85b460ecbc23eec55b99ff83506c33e0f4cecdb0375babc7b0d50cfb9",
    ),
    "prior_mechanical_continuation_step": (
        PRIOR_STEP,
        "c844c07177daf7e7b96d332d5060cfcbffe2c5989ded04602f9ec0dffd7c4b42",
    ),
    "accepted_b601_urdf": (
        ACCEPTED_URDF,
        "1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164",
    ),
    "q0_box_evidence": (
        staging.Q0_BOX_PATH,
        "fe16f3b8460574c281351e22f97e51843bac918608443ef91041b6194aff2d8b",
    ),
}

STATE_FILES = {
    "STOWED": ROOT / "state_STOWED_HOLD_B601_HIFI.step",
    "DEPLOYED_NOMINAL": ROOT / "state_DEPLOYED_NOMINAL_Q0.step",
    "DEPLOY_FAILED_BOTH": ROOT / "state_DEPLOY_FAILED_BOTH_Q0.step",
    "L_FAIL": ROOT / "state_L_FAIL_Q0.step",
    "R_FAIL": ROOT / "state_R_FAIL_Q0.step",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bbox(shape) -> tuple[float, float, float, float, float, float]:
    bb = shape.bounding_box()
    return (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z)


def _bbox_overlap(left, right) -> bool:
    return all(
        min(left[index + 3], right[index + 3])
        - max(left[index], right[index])
        > TOL
        for index in range(3)
    )


def _leaves(shape) -> Iterable:
    children = list(getattr(shape, "children", []) or [])
    if children:
        for child in children:
            yield from _leaves(child)
    else:
        yield shape


def _positive_intersections(left_items, right_items) -> list[dict[str, Any]]:
    hits = []
    for left in left_items:
        left_bbox = _bbox(left)
        for right in right_items:
            if not _bbox_overlap(left_bbox, _bbox(right)):
                continue
            volume = float((left & right).volume)
            if volume > TOL:
                hits.append(
                    {
                        "left": str(getattr(left, "label", "")),
                        "right": str(getattr(right, "label", "")),
                        "volume_mm3": volume,
                    }
                )
    return hits


def _arm_entities():
    arm = staging._load_module("arm_for_validation", staging.ARM_SOURCE)
    spec = arm.load_spec()
    source_entities = arm.make_entities()
    transform = Location((0.0, 0.0, staging.TOP_LAYOUT_TO_CS_S_Z_MM))
    physical = {}
    nonphysical = {}
    for item in spec["entities"]:
        placed = source_entities[item["id"]].moved(transform)
        placed.label = item["id"]
        if item["classification"].startswith("PHYSICAL"):
            physical[item["id"]] = placed
        else:
            nonphysical[item["id"]] = placed
    return spec, physical, nonphysical


def _q0_proxy_children():
    proxy = staging.build_q0_proxy()
    return list(proxy.children)


def _min_compound_distance(left_items, right_shape) -> tuple[float, str]:
    minimum = float("inf")
    owner = ""
    for item in left_items:
        distance = float(item.distance_to(right_shape))
        if distance < minimum:
            minimum = distance
            owner = str(getattr(item, "label", ""))
    return minimum, owner


def _max_radius_from_hinge(moving_shape, side: int, solar) -> float:
    axis_y = side * solar.DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM
    axis_z = solar.DESIGN_PROPOSAL_HINGE_AXIS_Z_MM
    radii = [
        math.hypot(vertex.Y - axis_y, vertex.Z - axis_z)
        for vertex in moving_shape.vertices()
    ]
    return max(radii)


def _continuous_clearance_bound(static_items, solar, side: int):
    samples = []
    for angle in range(91):
        moving = solar._moving_panel(side, float(angle), "BOUND_SEARCH")
        distance, owner = _min_compound_distance(static_items, moving)
        samples.append(
            {"angle_deg": angle, "distance_mm": distance, "owner": owner}
        )
    minimum_sample = min(samples, key=lambda item: item["distance_mm"])
    radius = _max_radius_from_hinge(
        solar._moving_panel(side, 0.0, "RADIUS"), side, solar
    )
    nearest_sample_half_step_rad = math.radians(0.5)
    motion_bound = radius * nearest_sample_half_step_rad
    lower_bound = minimum_sample["distance_mm"] - motion_bound
    return {
        "side": "LEFT" if side > 0 else "RIGHT",
        "grid_step_deg": 1.0,
        "maximum_unsampled_angle_to_grid_deg": 0.5,
        "maximum_radius_from_hinge_mm": radius,
        "motion_bound_mm": motion_bound,
        "minimum_grid_sample": minimum_sample,
        "continuous_lower_bound_mm": lower_bound,
        "status": "PASS" if lower_bound > TOL else "HOLD",
        "scope": "represented rigid moving group versus listed static proxy geometry only",
    }


def _state_policy_check(policy: dict[str, Any]):
    states = policy["states"]
    ids = [state["id"] for state in states]
    null_bindings = {
        state["id"]
        for state in states
        if state["geometry_binding"] is None
    }
    return (
        policy["state_count"] == 7
        and len(states) == 7
        and len(set(ids)) == 7
        and null_bindings == {"PARTIAL", "SERVICE"}
        and not policy["diagnostic_samples_define_partial"]
    ), {
        "ids": ids,
        "null_geometry_bindings": sorted(null_bindings),
        "diagnostic_samples_define_partial": policy[
            "diagnostic_samples_define_partial"
        ],
    }


def run() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def record(check_id: str, status: str, evidence: Any):
        if status not in {"PASS", "HOLD", "FAIL"}:
            raise ValueError(status)
        checks.append({"id": check_id, "status": status, "evidence": evidence})

    lock_evidence = {}
    locks_pass = True
    for name, (path, expected) in EXPECTED_HASHES.items():
        actual = _sha256(path)
        passed = actual == expected
        locks_pass = locks_pass and passed
        lock_evidence[name] = {
            "path": str(path),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "status": "PASS" if passed else "FAIL",
        }
    record("SOURCE_AND_ACCEPTED_BASELINE_HASH_LOCK", "PASS" if locks_pass else "FAIL", lock_evidence)

    decision_contract = json.loads(
        DECISION_CONTRACT.read_text(encoding="utf-8")
    )
    current_contract_evidence = {}
    current_contracts_pass = True
    for field, path in CURRENT_SUBSYSTEM_CONTRACTS.items():
        expected = decision_contract.get("source_lock", {}).get(field)
        actual = _sha256(path)
        passed = isinstance(expected, str) and actual == expected
        current_contracts_pass = current_contracts_pass and passed
        current_contract_evidence[field] = {
            "path": str(path),
            "expected_sha256_from_layout_decision_contract": expected,
            "actual_sha256": actual,
            "status": "PASS" if passed else "FAIL",
        }
    record(
        "CURRENT_SUBSYSTEM_CONTRACT_HASH_LOCK",
        "PASS" if current_contracts_pass else "FAIL",
        {
            "decision_contract_path": str(DECISION_CONTRACT),
            "contracts": current_contract_evidence,
        },
    )

    urdf_root = ET.parse(ACCEPTED_URDF).getroot()
    urdf_mass = sum(
        float(link.find("inertial/mass").get("value"))
        for link in urdf_root.findall("link")
        if link.find("inertial/mass") is not None
    )
    record(
        "ACCEPTED_URDF_MASS_AUTHORITY_NOT_DUPLICATED",
        "PASS" if abs(urdf_mass - 4.695555949342986) <= 1.0e-12 else "FAIL",
        {
            "accepted_urdf_mass_sum_kg": urdf_mass,
            "step_mass_authority": "EXCLUDED",
        },
    )

    policy = staging.load_state_policy()
    policy_pass, policy_evidence = _state_policy_check(policy)
    record(
        "SEVEN_STATE_POLICY_FAIL_CLOSED",
        "PASS" if policy_pass else "FAIL",
        policy_evidence,
    )

    state_evidence = {}
    state_files_pass = True
    for state_id, path in STATE_FILES.items():
        exists = path.is_file() and path.stat().st_size > 0
        if not exists:
            state_files_pass = False
            state_evidence[state_id] = {
                "path": str(path),
                "status": "FAIL",
            }
            continue
        reopened = import_step(path)
        solids = list(reopened.solids())
        passed = bool(solids) and min(float(solid.volume) for solid in solids) > 0
        state_files_pass = state_files_pass and passed
        state_evidence[state_id] = {
            "path": str(path),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "positive_volume_solid_count": len(solids),
            "bbox_mm": list(_bbox(reopened)),
            "status": "PASS" if passed else "FAIL",
        }
    forbidden_files = {
        "PARTIAL": ROOT / "state_PARTIAL.step",
        "SERVICE": ROOT / "state_SERVICE.step",
    }
    forbidden_absent = all(not path.exists() for path in forbidden_files.values())
    state_files_pass = state_files_pass and forbidden_absent
    state_evidence["manifest_only_states"] = {
        state_id: {
            "path": str(path),
            "absent_as_required": not path.exists(),
        }
        for state_id, path in forbidden_files.items()
    }
    record(
        "FIVE_GEOMETRY_ENTRIES_TWO_MANIFEST_ONLY_ENTRIES",
        "PASS" if state_files_pass else "FAIL",
        state_evidence,
    )

    arm_spec, arm_physical_map, arm_nonphysical_map = _arm_entities()
    arm_physical = list(arm_physical_map.values())
    transform = arm_spec["staging_transform_to_cs_s"]
    mapped_pad_lower = {
        pad_id: _bbox(arm_physical_map[pad_id])[2]
        for pad_id in (
            "PAD_FORWARD_PORT",
            "PAD_FORWARD_STARBOARD",
            "PAD_AFT_PORT",
            "PAD_AFT_STARBOARD",
        )
    }
    transform_pass = (
        transform["translation_mm"] == [0.0, 0.0, 119.15]
        and transform["rotation_matrix_row_major"]
        == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        and all(
            abs(value - staging.CS_S_TOP_EXTERIOR_Z_MM) <= TOL
            for value in mapped_pad_lower.values()
        )
    )
    record(
        "TOP_LAYOUT_TO_CS_S_POSITIONING",
        "PASS" if transform_pass else "FAIL",
        {
            "translation_mm": transform["translation_mm"],
            "rotation_matrix_row_major": transform[
                "rotation_matrix_row_major"
            ],
            "mapped_pad_lower_z_mm": mapped_pad_lower,
            "target_bus_top_exterior_z_mm": staging.CS_S_TOP_EXTERIOR_Z_MM,
            "ratification": transform["ratification"],
        },
    )

    primary = staging.build_revised_primary_structure()
    primary_items = list(_leaves(primary))
    solar = staging._load_module("solar_for_validation", staging.SOLAR_SOURCE)

    moving_platform_hits = {}
    for side in (1, -1):
        side_name = "LEFT" if side > 0 else "RIGHT"
        moving_platform_hits[side_name] = _positive_intersections(
            primary_items,
            list(_leaves(solar._moving_panel(side, 0.0, "POCKET_CHECK"))),
        )
    pocket_pass = all(not hits for hits in moving_platform_hits.values())
    record(
        "STOWED_MOVING_SOLAR_VERSUS_REVISED_PRIMARY_NO_INTERPENETRATION",
        "PASS" if pocket_pass else "FAIL",
        moving_platform_hits,
    )

    original_primary = staging._load_module(
        "prior_original_for_delta", staging.PRIOR_SOURCE
    )._build_primary_structure()
    original_items = list(_leaves(original_primary))
    original_hits = {}
    for side in (1, -1):
        side_name = "LEFT" if side > 0 else "RIGHT"
        original_hits[side_name] = _positive_intersections(
            original_items,
            list(_leaves(solar._moving_panel(side, 0.0, "ORIGINAL_CHECK"))),
        )
    record(
        "PRESERVED_PRE_POCKET_CONFLICT_EVIDENCE",
        "PASS"
        if sum(len(items) for items in original_hits.values()) == 44
        else "FAIL",
        {
            "original_positive_intersection_pair_count": sum(
                len(items) for items in original_hits.values()
            ),
            "by_side": original_hits,
            "claim": "Negative input result retained; not a current staging collision.",
        },
    )

    residual_width = (
        staging.POCKET_LEFT_Y_BOUNDS_MM[0]
        - (105.65 - 7.5)
    )
    record(
        "POCKET_RESIDUAL_PRIMARY_MEMBER_WIDTH",
        "HOLD",
        {
            "original_outer_member_width_mm": 15.0,
            "retained_inboard_width_mm": residual_width,
            "removed_outer_depth_mm": (
                staging.POCKET_LEFT_Y_BOUNDS_MM[1]
                - staging.POCKET_LEFT_Y_BOUNDS_MM[0]
            ),
            "geometry_continuity": "POSITIVE_RESIDUAL_SECTION",
            "strength_stiffness_tolerance": "NOT_EVALUATED_HOLD",
        },
    )

    arm_primary_hits = _positive_intersections(arm_physical, primary_items)
    pad_contact_pass = all(
        abs(value - staging.CS_S_TOP_EXTERIOR_Z_MM) <= TOL
        for value in mapped_pad_lower.values()
    )
    record(
        "ARM_SUPPORT_TO_PLATFORM_PLACEMENT",
        "PASS" if not arm_primary_hits and pad_contact_pass else "FAIL",
        {
            "positive_volume_intersections": arm_primary_hits,
            "pad_lower_face_contact_z_mm": mapped_pad_lower,
            "claim_limit": "face placement only; fasteners and load transfer HOLD",
        },
    )

    fixed_cassette_items = list(_leaves(solar._fixed_cassette(1))) + list(
        _leaves(solar._fixed_cassette(-1))
    )
    cassette_primary_hits = _positive_intersections(
        fixed_cassette_items, primary_items
    )
    record(
        "FIXED_CASSETTE_TO_PRIMARY_EMBEDDED_LOADPATH",
        "HOLD",
        {
            "positive_intersection_pair_count": len(cassette_primary_hits),
            "intersections": cassette_primary_hits,
            "interpretation": (
                "Reference rails/backplane overlap the residual primary "
                "members as load-path intent; joints and section closure are "
                "not established."
            ),
        },
    )

    arm_support_bounds = [
        _continuous_clearance_bound(arm_physical, solar, side)
        for side in (1, -1)
    ]
    record(
        "BOUNDED_CONTINUOUS_SOLAR_VERSUS_ARM_SUPPORT_CLEARANCE",
        "PASS"
        if all(item["status"] == "PASS" for item in arm_support_bounds)
        else "HOLD",
        arm_support_bounds,
    )

    q0_items = _q0_proxy_children()
    q0_bounds = [
        _continuous_clearance_bound(q0_items, solar, side)
        for side in (1, -1)
    ]
    record(
        "BOUNDED_CONTINUOUS_SOLAR_VERSUS_Q0_PROXY_CLEARANCE",
        "PASS" if all(item["status"] == "PASS" for item in q0_bounds) else "HOLD",
        q0_bounds,
    )

    platform_sampled_distances = {}
    for side in (1, -1):
        side_name = "LEFT" if side > 0 else "RIGHT"
        samples = []
        for angle in range(91):
            moving = solar._moving_panel(side, float(angle), "PLATFORM_SEARCH")
            distance, owner = _min_compound_distance(primary_items, moving)
            samples.append(
                {"angle_deg": angle, "distance_mm": distance, "owner": owner}
            )
        platform_sampled_distances[side_name] = min(
            samples, key=lambda item: item["distance_mm"]
        )
    record(
        "ONE_DEG_GRID_SOLAR_VERSUS_REVISED_PRIMARY",
        "HOLD",
        {
            "minimum_grid_samples": platform_sampled_distances,
            "grid_result": (
                "No sampled interpenetration; minimum clearance is below a "
                "qualified tolerance and no continuous lower bound is claimed."
            ),
            "continuous_global_clearance": "NOT_ESTABLISHED",
        },
    )

    legacy = staging.build_legacy_device_references()
    legacy_items = list(_leaves(legacy))
    conflict_witnesses = [
        item
        for item in legacy_items
        if "LEGACY_STAR_TRACKER" in str(getattr(item, "label", ""))
    ]
    retained_legacy = [
        item for item in legacy_items if item not in conflict_witnesses
    ]
    retained_hits = _positive_intersections(arm_physical, retained_legacy)
    star_hits = _positive_intersections(arm_physical, conflict_witnesses)
    star_volume = sum(hit["volume_mm3"] for hit in star_hits)
    record(
        "LEGACY_TOP_DEVICE_RELOCATION_CONFLICT_PRESERVED",
        "PASS"
        if not retained_hits
        and len(star_hits) == 1
        and abs(star_volume - 5625.0) <= 1.0e-6
        else "FAIL",
        {
            "retained_legacy_physical_hits": retained_hits,
            "nonphysical_star_tracker_conflict_hits": star_hits,
            "preserved_conflict_volume_mm3": star_volume,
            "new_side_sensor_reservation": _bbox(
                arm_nonphysical_map["SENSOR_RESERVATION_PORT"]
            ),
            "relocation_fov_mount_harness": "TBD_HOLD",
        },
    )

    record(
        "PRE_CAPTURE_AND_SERVICE_POSE_AUTHORITY",
        "HOLD",
        {
            "PRE_CAPTURE_joint_vector": None,
            "SERVICE_joint_vector": None,
            "SERVICE_geometry_binding": None,
            "reason": (
                "No frozen accepted-URDF joint vector or authorised service "
                "access sequence exists."
            ),
        },
    )

    record(
        "NATIVE_CONFIGURATION_BOM_AND_MASS_READBACK",
        "HOLD",
        {
            "solidworks_configurations": "NONE",
            "component_suppression_readback": "NONE",
            "bom_exclusion_readback": "NONE",
            "step_mass_authority": "EXCLUDED",
            "accepted_urdf_mass_authority_kg": urdf_mass,
        },
    )

    statuses = [check["status"] for check in checks]
    result = {
        "schema_version": "1.0",
        "decision_id": "V22-LAYOUT-AND-DEPLOYMENT-01",
        "scope": "GATE_5_ARM_SOLAR_CLEARANCE_AND_GATE_6_ISOLATED_STAGING",
        "checks": checks,
        "summary": {
            "pass": statuses.count("PASS"),
            "hold": statuses.count("HOLD"),
            "fail": statuses.count("FAIL"),
            "verdict": (
                "STAGING_BUILT_VALIDATED_WITH_ENGINEERING_HOLDS"
                if "FAIL" not in statuses
                else "FAIL_REPAIR_REQUIRED"
            ),
        },
        "gate_disposition": {
            "SOLAR_LAYOUT_TRADE_01": "ACCEPT_STAGING_310_MM_INTERFACE_RATIFICATION_HOLD",
            "SOLAR_CASSETTE_01": "HOLD_STRUCTURAL_AND_INTERNAL_VOLUME",
            "SOLAR_KINEMATIC_01": "PASS_DISCRETE_AND_ASYMMETRIC_WITH_CONTINUOUS_PLATFORM_HOLD",
            "ARM_STOW_LAYOUT_02": "PASS_LAYOUT_WITH_INTERFACE_AND_STRUCTURE_HOLDS",
            "ARM_SOLAR_CLEARANCE_01": "PASS_REPRESENTED_Q0_AND_SUPPORT_SCOPE_PRE_CAPTURE_HOLD",
            "LAYOUT_STAGING_ASSEMBLY_01": "PASS_ISOLATED_FIVE_GEOMETRY_ENTRIES_TWO_MANIFEST_ONLY",
        },
        "claim_limits": [
            "NO_GLOBAL_COLLISION_SAFETY",
            "NO_PRE_CAPTURE_OR_SERVICE_CLEARANCE",
            "NO_STRENGTH_OR_STIFFNESS",
            "NO_RELEASE_RELIABILITY",
            "NO_NATIVE_SOLIDWORKS_CONFIGURATION",
            "NO_STEP_MASS_OR_BOM_AUTHORITY",
            "NO_FLIGHT_QUALIFICATION",
        ],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
