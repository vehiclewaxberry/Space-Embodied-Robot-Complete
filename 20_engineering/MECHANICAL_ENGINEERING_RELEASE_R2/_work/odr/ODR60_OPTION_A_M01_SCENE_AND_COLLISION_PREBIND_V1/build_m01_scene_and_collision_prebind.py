#!/usr/bin/env python3
"""Build the append-only M01 scene and collision-asset prebind package.

This module parses and hashes metadata only.  It never imports CAD kernels, loads
collision payloads, evaluates a pair, certifies an edge, or starts a path search.
Unknown scene decisions remain explicit ``null`` values.  Engineering suggestions
are emitted under a separate non-authoritative namespace and never become instances.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import yaml


OUT_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1"
)

SCENE_NAME = "M01_SCENE_DECISION_INTAKE_V1.yaml"
ASSET_NAME = "M01_OPERATIONAL_ASSET_READINESS_V1.csv"
GATE_NAME = "M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json"
MANIFEST_NAME = "M01_SCENE_AND_COLLISION_PREBIND_SHA256_V1.csv"

SOURCE_PINS = {
    "owner_selection": (
        Path(
            "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
            "ODR60_OPTION_A_EXECUTION_CLOSURE_V1/OWNER_SELECTION_RECORD_V1.json"
        ),
        "A88E2301B36D330D9B15AFC73C03D19838E05CD20BBC47406C39B1BF465FF2BF",
        "LATEST_OWNER_OPTION_SELECTION",
    ),
    "execution_mount": (
        Path(
            "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
            "ODR60_OPTION_A_EXECUTION_CLOSURE_V1/EXECUTION_MOUNT_BINDING_V1.json"
        ),
        "B7758F751E273CE21CCD5132C23F2514524DE7613E31B33646E027603B0F6653",
        "LATEST_FULL_PRECISION_MOUNT_BINDING",
    ),
    "collision_frame_registration": (
        Path(
            "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
            "ODR60_OPTION_A_EXECUTION_CLOSURE_V1/COLLISION_FRAME_REGISTRATION_V1.json"
        ),
        "3C60DBFFB2C62AB0C71482D78C8CEC63EC3AF042ABF550A324627771C9D3EA4D",
        "LATEST_ACCEPTED_B601_ASSET_FRAME_LEDGER",
    ),
    "scene_schema_v2": (
        Path(
            "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
            "ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json"
        ),
        "67252BCE1259414876103EE3B6AF25ACC4A33E5A36B73AF974BD4004C285141C",
        "THREE_STAGE_SCHEMA_AUTHORITY",
    ),
    "execution_closure_gate": (
        Path(
            "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
            "ODR60_OPTION_A_EXECUTION_CLOSURE_V1/results/"
            "ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json"
        ),
        "869A248050FD39347D5D502F6174E284943901BA9F3C40A2D4337B4B6FF5A01A",
        "CURRENT_EXECUTION_HOLD_AUTHORITY",
    ),
    "system_collision_registry": (
        Path(
            "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
            "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/"
            "M01_SYSTEM_COLLISION_REGISTRY_V1.json"
        ),
        "AC975D11CC4715277E34FCFF7ABF049BC57334FD8F03AAB223BBED0877B1694F",
        "CURRENT_150_OBJECT_AND_10_KEEPOUT_REGISTRY",
    ),
    "system_collision_registry_gate": (
        Path(
            "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
            "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/"
            "M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json"
        ),
        "F5E91371648756D43FF7CF6C03028FA95174428D088BAAC08254FAD8D5DCC3FF",
        "CURRENT_PAIR_UNIVERSE_HOLD_AUTHORITY",
    ),
    "query_infrastructure_gate": (
        Path(
            "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
            "ODR60_OPTION_A_QUERY_INFRASTRUCTURE_V1/QUERY_INFRASTRUCTURE_GATE_V1.json"
        ),
        "6F8E3BAF38CB69312017B76BAEAB304A84E7B956DE528356831AE378A28A6221",
        "CURRENT_QUERY_AND_SEARCH_HOLD_AUTHORITY",
    ),
}

PRE_POST_FIELDS = [
    "gripper_joint1_m",
    "gripper_joint2_m",
    "solar_state",
    "solar_hdrm_state",
    "solar_latch_state",
    "arm_hdrm_state",
    "target_present",
    "target_attached",
    "active_object_universe_sha256",
    "active_pair_universe_sha256",
]

EVENT_FIELDS = [
    "event_id",
    "event_time_or_ordering",
    "pre_scene_sha256",
    "post_scene_sha256",
    "arm_hdrm_state_t0_minus",
    "arm_hdrm_state_t0_plus",
    "release_outcome",
    "released_constraint_ids",
    "retained_constraint_ids",
    "failure_disposition",
]

ASSET_FIELDS = [
    "id",
    "category",
    "row_class",
    "active_in_current_pair_universe",
    "path",
    "hash_algorithm",
    "hash",
    "bytes",
    "units",
    "frame",
    "state_selector",
    "closed",
    "operational_authority",
    "representation_debit",
    "readiness",
    "blocker",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def strict_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def yaml_text(value: Any) -> str:
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=120,
    )


def posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def null_cell(value: Any) -> str:
    return "null" if value is None else str(value)


def bool_cell(value: bool) -> str:
    return "true" if value is True else "false"


def verify_source_pins(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = []
    parsed = {}
    for source_id, (rel_path, expected_hash, role) in SOURCE_PINS.items():
        path = repo_root / rel_path
        if not path.is_file():
            raise FileNotFoundError(f"SOURCE_PIN_MISSING:{source_id}:{path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"SOURCE_PIN_MISMATCH:{source_id}:expected={expected_hash}:actual={actual_hash}"
            )
        rows.append(
            {
                "source_id": source_id,
                "path": posix(rel_path),
                "bytes": path.stat().st_size,
                "sha256": actual_hash,
                "role": role,
                "match": True,
            }
        )
        parsed[source_id] = strict_json(path)
    return rows, parsed


def validate_parent_truth(parsed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    owner = parsed["owner_selection"]
    mount = parsed["execution_mount"]
    frames = parsed["collision_frame_registration"]
    schema = parsed["scene_schema_v2"]
    execution = parsed["execution_closure_gate"]
    registry = parsed["system_collision_registry"]
    registry_gate = parsed["system_collision_registry_gate"]
    query = parsed["query_infrastructure_gate"]

    if owner["selection"]["selected_option"] != "A" or owner["selection"]["option_a_selected"] is not True:
        raise RuntimeError("LATEST_OWNER_SELECTION_IS_NOT_OPTION_A")
    if owner["low_memory"]["explicitly_not_authorized_now"] is not True:
        raise RuntimeError("UNEXPECTED_LOW_MEMORY_AUTHORITY_CHANGE")
    if mount["canonical_binding_payload_sha256"] != "E20544EF880D1792EB3B616A4B74CBD635F130FC9AB5846C6A09E12EA6187B7D":
        raise RuntimeError("EXECUTION_MOUNT_CANONICAL_PAYLOAD_CHANGED")
    if mount["execution_mount_numeric_spelling_bound"] is not True:
        raise RuntimeError("EXECUTION_MOUNT_NOT_BOUND")
    if any(mount[key] is not False for key in ("pair_evaluation_authorized", "edge_evaluation_authorized", "path_search_authorized")):
        raise RuntimeError("MOUNT_ARTIFACT_UNEXPECTEDLY_AUTHORIZES_EXECUTION")

    summary = frames["summary"]
    if summary["accepted_urdf_link_count"] != 10 or summary["frame_relationships_bound"] != 10:
        raise RuntimeError("B601_FRAME_LEDGER_NOT_10_OF_10")
    if summary["operational_narrowphase_promoted"] != 1:
        raise RuntimeError("UNEXPECTED_B601_OPERATIONAL_PROMOTION_COUNT")
    registrations = frames["registrations"]
    if len(registrations) != 10 or not all(row["frame_relationship_bound"] for row in registrations):
        raise RuntimeError("B601_FRAME_REGISTRATION_ROWS_INCOMPLETE")
    if any(row["pair_evaluation_authorized"] is not False for row in registrations):
        raise RuntimeError("B601_FRAME_LEDGER_UNEXPECTEDLY_AUTHORIZES_PAIR_EVALUATION")

    current = schema["current_instances"]
    if current["stage_instances_bound"] != 0 or current["stage_instances_required"] != 3:
        raise RuntimeError("PARENT_M01_STAGE_COUNT_NO_LONGER_ZERO_OF_THREE")
    if current["legacy_required_values_bound"] != 0 or current["legacy_required_values_total"] != 9:
        raise RuntimeError("PARENT_LEGACY_REQUIRED_VALUE_COUNT_CHANGED")
    if schema["schema_contract"]["stage_order"] != [
        "PRE_RELEASE_CONSTANT_SCENE",
        "RELEASE_EVENT_SCENE",
        "POST_RELEASE_CONSTANT_SCENE",
    ]:
        raise RuntimeError("PARENT_M01_STAGE_ORDER_CHANGED")

    objects = registry["objects"]
    keepouts = registry["conditional_virtual_constraint_candidates"]
    missing = registry["known_missing_objects_or_authorities"]
    counts = registry["object_summary"]["category_counts"]
    if len(objects) != 150 or counts != {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6}:
        raise RuntimeError("CURRENT_150_OBJECT_UNIVERSE_CHANGED")
    if len(keepouts) != 10 or any(row["category"] != "K" for row in keepouts):
        raise RuntimeError("CURRENT_10_KEEPOUT_CANDIDATES_CHANGED")
    if len(missing) != 7:
        raise RuntimeError("KNOWN_MISSING_CATEGORY_COUNT_CHANGED")

    pair_coverage = registry_gate["pair_coverage"]
    if pair_coverage["expected_pairs"] != 11175:
        raise RuntimeError("PAIR_UNIVERSE_COUNT_CHANGED")
    if pair_coverage["status_counts"] != {"EXCEPTED": 9, "UNASSESSED_FAIL_CLOSED": 11166}:
        raise RuntimeError("PAIR_ASSESSMENT_STATE_CHANGED")
    for document_id, document in (("execution", execution), ("query", query)):
        if document.get("path_search_authorized") is not False or document.get("path_search_executed") is not False:
            raise RuntimeError(f"{document_id.upper()}_UNEXPECTED_PATH_AUTHORITY")
    if execution["pair_evaluation_authorized"] is not False:
        raise RuntimeError("EXECUTION_GATE_UNEXPECTED_PAIR_AUTHORITY")
    if query["system_pair_evaluation_authorized"] is not False:
        raise RuntimeError("QUERY_GATE_UNEXPECTED_PAIR_AUTHORITY")

    return {
        "option_a_selected": True,
        "low_memory_override_authorized": False,
        "mount_payload_sha256": mount["canonical_binding_payload_sha256"],
        "mount_document_sha256": SOURCE_PINS["execution_mount"][1],
        "frame_relationships_bound": 10,
        "frame_relationships_required": 10,
        "b601_operational_narrowphase_promoted": 1,
        "stage_instances_bound": 0,
        "stage_instances_required": 3,
        "legacy_required_values_bound": 0,
        "legacy_required_values_required": 9,
        "active_object_count": 150,
        "conditional_keepout_candidate_count": 10,
        "known_missing_category_count": 7,
        "query_required_pair_count": 11166,
        "pair_queries_executed": 0,
        "path_search_authorized": False,
        "path_search_executed": False,
    }


def build_scene_intake(
    source_rows: list[dict[str, Any]], parsed: dict[str, dict[str, Any]], truth: dict[str, Any]
) -> dict[str, Any]:
    schema = parsed["scene_schema_v2"]
    mount = parsed["execution_mount"]

    def null_values(fields: list[str]) -> dict[str, None]:
        return {field: None for field in fields}

    stages = [
        {
            "stage_id": "PRE_RELEASE_CONSTANT_SCENE",
            "kind": "CONSTANT_SCENE_EDGE",
            "instance_status": "EXPLICIT_NULL_INTAKE__NOT_BOUND",
            "values": null_values(PRE_POST_FIELDS),
        },
        {
            "stage_id": "RELEASE_EVENT_SCENE",
            "kind": "DISCRETE_EVENT_CONTRACT",
            "instance_status": "EXPLICIT_NULL_INTAKE__NOT_BOUND",
            "values": null_values(EVENT_FIELDS),
        },
        {
            "stage_id": "POST_RELEASE_CONSTANT_SCENE",
            "kind": "CONSTANT_SCENE_EDGE",
            "instance_status": "EXPLICIT_NULL_INTAKE__NOT_BOUND",
            "values": null_values(PRE_POST_FIELDS),
        },
    ]

    return {
        "schema": "M01_SCENE_DECISION_INTAKE_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "authority": "APPEND_ONLY_DECISION_INTAKE_ONLY__NOT_A_SCENE_INSTANCE_NOT_QUERY_OR_SEARCH_AUTHORITY",
        "source_pins": {
            row["source_id"]: {
                "path": row["path"],
                "bytes": row["bytes"],
                "sha256": row["sha256"],
                "role": row["role"],
            }
            for row in source_rows
        },
        "consumed_current_truth": truth,
        "fixed_structure_binding": {
            "arm_execution_mount": {
                "frame_name": mount["binding"]["frame_name"],
                "parent_frame": mount["binding"]["parent_frame"],
                "child_frame": mount["binding"]["child_frame"],
                "matrix_semantics": mount["binding"]["matrix_semantics"],
                "canonical_matrix_decimal_strings": mount["binding"]["canonical_matrix_decimal_strings"],
                "translation_unit": mount["binding"]["translation_unit"],
                "rotation_unit": mount["binding"]["rotation_unit"],
                "canonical_payload_sha256": mount["canonical_binding_payload_sha256"],
                "bound": True,
            },
            "bus_pose_S": "IDENTITY_PROXY_ONLY",
            "load_bridge_pose_S": None,
            "m3r_stage_a_pose_S": None,
            "m3r_stage_b_pose_S": None,
            "complete_fixed_structure_binding": False,
        },
        "field_types_and_units": schema["field_types"],
        "continuous_q_contract": schema["schema_contract"]["continuous_q_contract"],
        "stage_order": schema["schema_contract"]["stage_order"],
        "stages": stages,
        "authoritative_instance_accounting": {
            "explicit_field_keys_present": 30,
            "explicit_field_keys_required": 30,
            "authoritative_field_values_bound": 0,
            "stage_instances_bound": 0,
            "stage_instances_required": 3,
            "legacy_required_values_bound": 0,
            "legacy_required_values_required": 9,
            "active_object_universe_bound_per_stage": False,
            "active_pair_universe_bound_per_stage": False,
            "event_contract_bound": False,
            "scene_binding_complete": False,
        },
        "candidate_suggestions_not_authority": {
            "authority": "NONE__ENGINEERING_HYPOTHESES_ONLY",
            "may_fill_authoritative_stage_values": False,
            "promotion_rule": (
                "REQUIRES_OWNER_RATIFIED_VALUES_PLUS_REISSUED_STAGE_OBJECT_AND_PAIR_UNIVERSE_HASHES;"
                "COPYING_THIS_BLOCK_INTO_STAGES_IS_FORBIDDEN"
            ),
            "basis": "FIXED_ENDPOINT_RELEASE_CLEAR_INTENT_AND_ZERO_TRAVEL_CONVENTIONS_ONLY",
            "pre_release_candidate": {
                "gripper_joint1_m": 0.0,
                "gripper_joint2_m": 0.0,
                "solar_state": "SOLAR_STOWED",
                "solar_hdrm_state": None,
                "solar_latch_state": None,
                "arm_hdrm_state": "LOCKED",
                "target_present": False,
                "target_attached": False,
                "active_object_universe_sha256": None,
                "active_pair_universe_sha256": None,
            },
            "release_event_candidate": {
                "event_id": "ARM_HDRM_RELEASE_CANDIDATE_01",
                "event_time_or_ordering": "BETWEEN_PRE_AND_POST_CONSTANT_SCENES",
                "pre_scene_sha256": None,
                "post_scene_sha256": None,
                "arm_hdrm_state_t0_minus": "LOCKED",
                "arm_hdrm_state_t0_plus": "RELEASED",
                "release_outcome": "RELEASED",
                "released_constraint_ids": None,
                "retained_constraint_ids": None,
                "failure_disposition": "UNKNOWN_ABORT",
            },
            "post_release_candidate": {
                "gripper_joint1_m": 0.0,
                "gripper_joint2_m": 0.0,
                "solar_state": "SOLAR_STOWED",
                "solar_hdrm_state": None,
                "solar_latch_state": None,
                "arm_hdrm_state": "RELEASED",
                "target_present": False,
                "target_attached": False,
                "active_object_universe_sha256": None,
                "active_pair_universe_sha256": None,
            },
        },
        "fail_closed_execution_state": {
            "collision_geometry_loaded": False,
            "pair_evaluation_authorized": False,
            "pair_queries_executed": 0,
            "edge_evaluation_authorized": False,
            "edges_certified": 0,
            "path_search_authorized": False,
            "path_search_executed": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "verdict": (
            "M01_V2_PRE_EVENT_POST_FIELDS_EXPLICIT_WITH_NULL_AUTHORITY_VALUES__"
            "ZERO_OF_THREE_INSTANCES__CANDIDATE_SUGGESTIONS_QUARANTINED__QUERY_AND_SEARCH_HOLD"
        ),
    }


def choose_declared_asset(obj: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    geometry = obj.get("geometry", {})
    category = obj["category"]
    if category == "C":
        return geometry.get("centerline"), "centerline"
    if category == "F":
        for key in ("narrowphase", "narrowphase_candidate", "broadphase", "container"):
            candidate = geometry.get(key)
            if isinstance(candidate, dict) and candidate.get("path"):
                return candidate, key
    if category == "R":
        return geometry.get("narrowphase_candidate"), "narrowphase_candidate"
    if category == "S":
        return geometry.get("container"), "container"
    return None, None


def validate_asset_pin(repo_root: Path, asset: dict[str, Any], object_id: str) -> None:
    required = ("path", "sha256", "bytes")
    if any(key not in asset for key in required):
        raise RuntimeError(f"ASSET_PIN_INCOMPLETE:{object_id}:{asset}")
    path = repo_root / Path(asset["path"])
    if not path.is_file():
        raise FileNotFoundError(f"ASSET_MISSING:{object_id}:{path}")
    actual_bytes = path.stat().st_size
    actual_hash = sha256_file(path)
    if actual_bytes != asset["bytes"] or actual_hash != asset["sha256"]:
        raise RuntimeError(
            f"ASSET_PIN_MISMATCH:{object_id}:bytes={actual_bytes}/{asset['bytes']}:"
            f"sha256={actual_hash}/{asset['sha256']}"
        )


def active_row(
    repo_root: Path,
    obj: dict[str, Any],
    frame_by_object: dict[str, dict[str, Any]],
) -> dict[str, str]:
    object_id = obj["object_id"]
    category = obj["category"]
    frame = obj.get("parent_frame")
    selector: dict[str, Any] = {
        "active_when": obj.get("active_when"),
        "pose_source": obj.get("pose_source"),
    }
    selected: dict[str, Any] | None
    selected_role: str | None
    operational = False
    closed = False

    if category == "A":
        registration = frame_by_object.get(object_id)
        if registration is None:
            raise RuntimeError(f"MISSING_B601_FRAME_REGISTRATION:{object_id}")
        selected = {
            "path": registration["asset_path"],
            "sha256": registration["asset_sha256"],
            "bytes": (repo_root / Path(registration["asset_path"])).stat().st_size,
            "units": registration["asset_units"],
        }
        selected_role = "accepted_urdf_frame_registered_asset"
        frame = registration["accepted_urdf_registration_frame"]
        selector["motion_registration"] = registration["motion_registration"]
        operational = registration["operational_narrowphase_promoted"] is True
        closed = operational and registration["frame_relationship_bound"] is True
        if operational:
            debit = "NONE_AT_ASSET_LEVEL__RUNTIME_POSE_AND_PAIR_CERTIFICATE_STILL_DEBITED"
            readiness = "ASSET_LEVEL_OPERATIONAL_PROXY_BOUND__SYSTEM_RUNTIME_POSE_AND_PAIR_HOLD"
            blocker = "RUNTIME_OBJECT_POSE_AND_11166_PAIR_CERTIFICATES_UNBOUND"
        else:
            debit = "OPERATIONAL_NARROWPHASE_PROMOTION_ABSENT"
            readiness = "FRAME_BOUND_DESIGN_ASSET__OPERATIONAL_PROMOTION_HOLD"
            blocker = "OPERATIONAL_NARROWPHASE_PROMOTION_AND_RUNTIME_POSE_UNBOUND"
    else:
        selected, selected_role = choose_declared_asset(obj)
        if selected is None:
            raise RuntimeError(f"NO_DECLARED_ASSET_FOR_ACTIVE_OBJECT:{object_id}")
        geometry = obj.get("geometry", {})
        if "container_selector" in geometry:
            selector["container_selector"] = geometry["container_selector"]
        if "container_selector_by_state" in geometry:
            selector["container_selector_by_state"] = geometry["container_selector_by_state"]
        if category == "C":
            selector["diameter_mm"] = geometry.get("diameter_mm")
            debit = "RUNTIME_CAPSULE_CHAIN_AND_HAUSDORFF_DERATE_ABSENT"
            readiness = "CENTERLINE_PINNED__OPERATIONAL_CAPSULE_CHAIN_HOLD"
            blocker = "CAPSULE_CHAIN_HAUSDORFF_DERATE_AND_RUNTIME_POSE_UNBOUND"
        elif category == "F" and object_id == "F::BUS":
            debit = "CONSERVATIVE_PROXY_ONLY__NARROWPHASE_AND_EXTERNAL_PROTRUSIONS_ABSENT"
            readiness = "CONSERVATIVE_BROADPHASE_CONTEXT_ONLY__OPERATIONAL_NARROWPHASE_HOLD"
            blocker = "BUS_OPERATIONAL_NARROWPHASE_AND_EXTERNAL_PROTRUSIONS_UNBOUND"
        elif category == "F":
            debit = "DESIGN_CANDIDATE_ONLY__OPERATIONAL_PROMOTION_ABSENT"
            readiness = "PINNED_DESIGN_CANDIDATE__OPERATIONAL_PROMOTION_HOLD"
            blocker = "OPERATIONAL_SELECTOR_PATCH_AND_RUNTIME_POSE_UNBOUND"
        elif category == "R":
            debit = "V9F_DESIGN_CANDIDATE_ONLY__OPERATIONAL_PROMOTION_AND_INTERFACE_PATCHES_ABSENT"
            readiness = "PINNED_V9F_TRIANGLES__OPERATIONAL_AND_PAIR_HOLD"
            blocker = "INDEPENDENT_ADAPTER_INTERFACE_PATCH_AND_PAIR_EVALUATION_UNBOUND"
        elif category == "S":
            debit = "STATE_SELECTOR_AND_PHYSICAL_HINGE_HDRM_LATCH_AUTHORITY_ABSENT"
            readiness = "CONTAINER_PINNED__SINGLE_STATE_OPERATIONAL_EXTRACTION_HOLD"
            blocker = "SOLAR_STATE_LATCH_HDRM_BINDING_AND_OPERATIONAL_EXTRACTION_UNBOUND"
        else:
            raise RuntimeError(f"UNHANDLED_ACTIVE_CATEGORY:{category}")

    validate_asset_pin(repo_root, selected, object_id)
    units = selected.get("units")
    if units is None:
        debit = debit + "__ASSET_UNITS_NOT_EXPLICIT_IN_SOURCE_REGISTRY"
        blocker = blocker + "__ASSET_UNITS_REQUIRE_AUTHORITY_BINDING"
    selector["selected_representation_role"] = selected_role
    return {
        "id": object_id,
        "category": category,
        "row_class": "ACTIVE_OBJECT",
        "active_in_current_pair_universe": "true",
        "path": null_cell(selected.get("path")),
        "hash_algorithm": "SHA256",
        "hash": null_cell(selected.get("sha256")),
        "bytes": null_cell(selected.get("bytes")),
        "units": null_cell(units),
        "frame": null_cell(frame),
        "state_selector": canonical_json(selector),
        "closed": bool_cell(closed),
        "operational_authority": bool_cell(operational),
        "representation_debit": debit,
        "readiness": readiness,
        "blocker": blocker,
    }


def keepout_row(repo_root: Path, item: dict[str, Any]) -> dict[str, str]:
    container = item["geometry"]["container"]
    validate_asset_pin(repo_root, container, item["object_id"])
    selector = {
        "active_when": item["active_when"],
        "container_selector": item["geometry"]["container_selector"],
        "kind": item["kind"],
    }
    return {
        "id": item["object_id"],
        "category": "K",
        "row_class": "CONDITIONAL_VIRTUAL_KEEPOUT_CANDIDATE",
        "active_in_current_pair_universe": "false",
        "path": container["path"],
        "hash_algorithm": "SHA256",
        "hash": container["sha256"],
        "bytes": str(container["bytes"]),
        "units": null_cell(item["geometry"].get("units")),
        "frame": "null",
        "state_selector": canonical_json(selector),
        "closed": "false",
        "operational_authority": "false",
        "representation_debit": (
            "VIRTUAL_CANDIDATE_NOT_IN_150_PAIR_UNIVERSE__PHYSICAL_HARDWARE_NOT_MODELLED"
        ),
        "readiness": "CONTAINER_SELECTOR_PINNED__ACTIVATION_AND_PHYSICAL_AUTHORITY_HOLD",
        "blocker": "EXPLICIT_SOLAR_STATE_LATCH_HDRM_BINDING_AND_REISSUED_PAIR_UNIVERSE_REQUIRED",
    }


def missing_row(category_name: str) -> dict[str, str]:
    return {
        "id": f"MISSING::{category_name}",
        "category": "MISSING",
        "row_class": "KNOWN_MISSING_OBJECT_OR_AUTHORITY_CATEGORY",
        "active_in_current_pair_universe": "false",
        "path": "null",
        "hash_algorithm": "SHA256",
        "hash": "null",
        "bytes": "null",
        "units": "null",
        "frame": "null",
        "state_selector": "null",
        "closed": "false",
        "operational_authority": "false",
        "representation_debit": "OMITTED_PHYSICAL_CATEGORY_EXPLICIT_DEBIT",
        "readiness": "MISSING_FAIL_CLOSED",
        "blocker": category_name,
    }


def build_asset_rows(
    repo_root: Path, parsed: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    registry = parsed["system_collision_registry"]
    frames = parsed["collision_frame_registration"]
    frame_by_object = {row["object_id"]: row for row in frames["registrations"]}
    rows = [active_row(repo_root, obj, frame_by_object) for obj in registry["objects"]]
    rows.extend(keepout_row(repo_root, item) for item in registry["conditional_virtual_constraint_candidates"])
    rows.extend(missing_row(name) for name in registry["known_missing_objects_or_authorities"])

    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("DUPLICATE_ASSET_READINESS_ID")
    active = [row for row in rows if row["row_class"] == "ACTIVE_OBJECT"]
    keepouts = [row for row in rows if row["category"] == "K"]
    missing = [row for row in rows if row["category"] == "MISSING"]
    category_counts = {
        category: sum(row["category"] == category for row in rows)
        for category in ("A", "C", "F", "R", "S", "K", "MISSING")
    }
    summary = {
        "row_count": len(rows),
        "active_object_rows": len(active),
        "conditional_virtual_keepout_rows": len(keepouts),
        "known_missing_category_rows": len(missing),
        "category_counts": category_counts,
        "asset_level_closed_rows": sum(row["closed"] == "true" for row in active),
        "operational_authority_rows": sum(row["operational_authority"] == "true" for row in active),
        "rows_with_explicit_null_units": sum(row["units"] == "null" for row in rows),
        "all_non_null_asset_pins_verified": True,
    }
    if summary["row_count"] != 167:
        raise RuntimeError(f"UNEXPECTED_READINESS_ROW_COUNT:{summary}")
    if category_counts != {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6, "K": 10, "MISSING": 7}:
        raise RuntimeError(f"UNEXPECTED_READINESS_CATEGORY_COUNTS:{category_counts}")
    if summary["asset_level_closed_rows"] != 1 or summary["operational_authority_rows"] != 1:
        raise RuntimeError(f"UNEXPECTED_OPERATIONAL_ASSET_COUNT:{summary}")
    return rows, summary


def asset_csv_text(rows: list[dict[str, str]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ASSET_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def build_gate(
    source_rows: list[dict[str, Any]],
    scene: dict[str, Any],
    asset_rows: list[dict[str, str]],
    asset_summary: dict[str, Any],
    scene_sha256: str,
    asset_sha256: str,
) -> dict[str, Any]:
    stage_by_id = {stage["stage_id"]: stage for stage in scene["stages"]}
    expected_by_id = {
        "PRE_RELEASE_CONSTANT_SCENE": PRE_POST_FIELDS,
        "RELEASE_EVENT_SCENE": EVENT_FIELDS,
        "POST_RELEASE_CONSTANT_SCENE": PRE_POST_FIELDS,
    }
    all_fields_explicit = all(
        list(stage_by_id[stage_id]["values"].keys()) == fields
        for stage_id, fields in expected_by_id.items()
    )
    all_authoritative_values_null = all(
        value is None
        for stage in scene["stages"]
        for value in stage["values"].values()
    )
    active_ids = [row["id"] for row in asset_rows if row["row_class"] == "ACTIVE_OBJECT"]
    checks = {
        "G01_all_eight_parent_source_hash_pins_match": len(source_rows) == 8 and all(row["match"] for row in source_rows),
        "G02_latest_owner_option_a_selection_consumed": scene["consumed_current_truth"]["option_a_selected"] is True,
        "G03_low_memory_override_remains_false": scene["consumed_current_truth"]["low_memory_override_authorized"] is False,
        "G04_full_precision_mount_payload_consumed": scene["fixed_structure_binding"]["arm_execution_mount"]["bound"] is True,
        "G05_b601_collision_asset_frame_ledger_10_of_10_consumed": scene["consumed_current_truth"]["frame_relationships_bound"] == 10,
        "G06_v2_pre_event_post_stage_order_exact": scene["stage_order"] == list(expected_by_id),
        "G07_all_30_v2_stage_field_keys_explicit": all_fields_explicit,
        "G08_all_30_authoritative_stage_values_are_null": all_authoritative_values_null,
        "G09_stage_instances_remain_zero_of_three": scene["authoritative_instance_accounting"]["stage_instances_bound"] == 0,
        "G10_candidate_suggestions_are_separate_and_non_authoritative": (
            scene["candidate_suggestions_not_authority"]["authority"] == "NONE__ENGINEERING_HYPOTHESES_ONLY"
            and scene["candidate_suggestions_not_authority"]["may_fill_authoritative_stage_values"] is False
        ),
        "G11_asset_ledger_contains_150_active_objects": asset_summary["active_object_rows"] == 150,
        "G12_asset_ledger_contains_10_nonactive_k_candidates": asset_summary["conditional_virtual_keepout_rows"] == 10,
        "G13_asset_ledger_contains_all_7_known_missing_categories": asset_summary["known_missing_category_rows"] == 7,
        "G14_asset_category_counts_exact_10_9_4_121_6_10_7": asset_summary["category_counts"] == {
            "A": 10, "C": 9, "F": 4, "R": 121, "S": 6, "K": 10, "MISSING": 7
        },
        "G15_active_object_ids_unique_and_exact_count": len(active_ids) == 150 and len(set(active_ids)) == 150,
        "G16_all_non_null_asset_paths_hashes_and_bytes_verified": asset_summary["all_non_null_asset_pins_verified"] is True,
        "G17_only_one_of_150_assets_has_asset_level_operational_authority": asset_summary["operational_authority_rows"] == 1,
        "G18_pair_query_and_path_search_remain_false_zero": scene["fail_closed_execution_state"] == {
            "collision_geometry_loaded": False,
            "pair_evaluation_authorized": False,
            "pair_queries_executed": 0,
            "edge_evaluation_authorized": False,
            "edges_certified": 0,
            "path_search_authorized": False,
            "path_search_executed": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
    }
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise RuntimeError(f"PREBIND_GATE_CHECKS_FAILED:{failed}")
    return {
        "schema": "M01_SCENE_AND_COLLISION_PREBIND_GATE_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "authority": "APPEND_ONLY_PREBIND_EVIDENCE_ONLY__NO_PARENT_GATE_REISSUE_NO_QUERY_OR_SEARCH_AUTHORITY",
        "decision_rule": "Authority > evidence > independent reproduction > agent opinion",
        "source_pins": {row["source_id"]: row for row in source_rows},
        "local_artifact_pins": {
            "scene_decision_intake": {"path": SCENE_NAME, "sha256": scene_sha256},
            "operational_asset_readiness": {"path": ASSET_NAME, "sha256": asset_sha256},
        },
        "checks": checks,
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "prebind_package_complete": True,
        "scene_accounting": scene["authoritative_instance_accounting"],
        "asset_accounting": asset_summary,
        "system_execution_state": {
            "complete_system_operational_collision_asset_set_bound": False,
            "system_pair_evaluation_authorized": False,
            "system_pair_queries_executed": 0,
            "system_edges_certified": 0,
            "path_search_authorized": False,
            "path_search_executed": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "manifest_policy": {
            "path": MANIFEST_NAME,
            "self_excluded": True,
            "manifest_hash_not_embedded_to_avoid_circularity": True,
        },
        "maximum_claim": (
            "M01_THREE_STAGE_DECISION_KEYS_AND_167_ROW_ASSET_READINESS_LEDGER_PREBOUND__"
            "ZERO_SCENE_INSTANCES_ONE_ASSET_LEVEL_OPERATIONAL_PROXY_NO_SYSTEM_QUERY_OR_SEARCH"
        ),
        "blockers": [
            "OWNER_RATIFIED_PRE_EVENT_POST_SCENE_VALUES_AND_STAGE_UNIVERSE_HASHES_ABSENT",
            "THREE_STAGE_SCENE_INSTANCES_ZERO_OF_THREE",
            "149_OF_150_ACTIVE_OBJECTS_LACK_ASSET_LEVEL_OPERATIONAL_AUTHORITY",
            "10_SOLAR_KEEPOUT_CANDIDATES_NOT_ACTIVATED_OR_IN_CURRENT_PAIR_UNIVERSE",
            "7_KNOWN_MISSING_OBJECT_OR_AUTHORITY_CATEGORIES_EXPLICITLY_DEBITED",
            "11166_REQUIRED_PAIR_QUERIES_UNEXECUTED_FAIL_CLOSED",
            "NO_CONTINUOUS_EDGE_CERTIFICATES_OR_PATH_SEARCH_AUTHORITY",
        ],
        "review_status": "PENDING_INDEPENDENT_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": (
            "M01_SCENE_AND_COLLISION_PREBIND_18_OF_18_PASS__ZERO_OF_THREE_STAGE_INSTANCES__"
            "ONE_OF_150_ASSET_LEVEL_OPERATIONAL__11166_PAIR_QUERY_AND_PATH_SEARCH_HOLD"
        ),
    }


def build_outputs(repo_root: Path) -> dict[str, str]:
    source_rows, parsed = verify_source_pins(repo_root)
    truth = validate_parent_truth(parsed)
    scene = build_scene_intake(source_rows, parsed, truth)
    asset_rows, asset_summary = build_asset_rows(repo_root, parsed)
    scene_rendered = yaml_text(scene)
    asset_rendered = asset_csv_text(asset_rows)
    gate = build_gate(
        source_rows,
        scene,
        asset_rows,
        asset_summary,
        sha256_bytes(scene_rendered.encode("utf-8")),
        sha256_bytes(asset_rendered.encode("utf-8")),
    )
    return {
        SCENE_NAME: scene_rendered,
        ASSET_NAME: asset_rendered,
        GATE_NAME: json_text(gate),
    }


def package_manifest_text(out_dir: Path) -> str:
    rows = []
    for path in sorted(item for item in out_dir.rglob("*") if item.is_file()):
        if path.name == MANIFEST_NAME:
            continue
        if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        rows.append(
            {
                "path": path.relative_to(out_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["path", "bytes", "sha256"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def write_outputs(repo_root: Path) -> Path:
    out_dir = repo_root / OUT_REL
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, content in build_outputs(repo_root).items():
        (out_dir / name).write_text(content, encoding="utf-8", newline="\n")
    manifest = package_manifest_text(out_dir)
    (out_dir / MANIFEST_NAME).write_text(manifest, encoding="utf-8", newline="\n")
    return out_dir


def check_outputs(repo_root: Path) -> Path:
    out_dir = repo_root / OUT_REL
    expected = build_outputs(repo_root)
    mismatches = []
    for name, content in expected.items():
        path = out_dir / name
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            mismatches.append(name)
    manifest_path = out_dir / MANIFEST_NAME
    expected_manifest = package_manifest_text(out_dir)
    if not manifest_path.is_file() or manifest_path.read_text(encoding="utf-8") != expected_manifest:
        mismatches.append(MANIFEST_NAME)
    if mismatches:
        raise RuntimeError(f"GENERATED_OUTPUT_MISMATCH:{mismatches}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    out_dir = write_outputs(repo_root) if args.write else check_outputs(repo_root)
    print(out_dir)


if __name__ == "__main__":
    main()
