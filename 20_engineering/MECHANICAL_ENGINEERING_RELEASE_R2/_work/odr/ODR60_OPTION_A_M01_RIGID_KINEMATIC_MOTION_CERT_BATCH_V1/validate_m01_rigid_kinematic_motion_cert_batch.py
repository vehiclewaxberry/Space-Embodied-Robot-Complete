#!/usr/bin/env python3
"""Standalone validator for the M01 rigid-kinematic candidate-bound batch.

The validator intentionally does not import or execute the builder.  It owns a
separate frozen source ledger, parses all sources independently, recomputes every
PLY radius and every URDF-chain coefficient, executes mutation controls, and then
validates the sealed manifest with an exact/no-extra policy.
"""

from __future__ import annotations

import argparse
import ast
import copy
import csv
import hashlib
import json
import math
import os
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable


PACKAGE_DIR = Path(__file__).resolve().parent


def locate_project_root() -> Path:
    cursor = PACKAGE_DIR
    while True:
        if (cursor / "PROJECT_MAP.md").is_file() and (cursor / "20_engineering").is_dir():
            return cursor
        if cursor.parent == cursor:
            raise RuntimeError("VALIDATOR_PROJECT_ROOT_NOT_FOUND")
        cursor = cursor.parent


PROJECT_ROOT = locate_project_root()

# This ledger is intentionally duplicated rather than imported from the builder.
FROZEN_SOURCES: dict[str, dict[str, Any]] = {
    "system_registry": {"path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json", "bytes": 247325, "sha256": "AC975D11CC4715277E34FCFF7ABF049BC57334FD8F03AAB223BBED0877B1694F"},
    "motion_contract": {"path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/OBJECT_MOTION_BOUND_CONTRACT_V1.json", "bytes": 15414, "sha256": "CA1A741576A90301D77FD684DFA07882FB1AB88A00E927C1381D8709C715A5CD"},
    "collision_registration": {"path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/COLLISION_FRAME_REGISTRATION_V1.json", "bytes": 28801, "sha256": "3C60DBFFB2C62AB0C71482D78C8CEC63EC3AF042ABF550A324627771C9D3EA4D"},
    "asset_readiness": {"path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_OPERATIONAL_ASSET_READINESS_V1.csv", "bytes": 113527, "sha256": "974D50C1786003ED70F8494F67DFEF20ABF64F1DE103A224E9ACA34DE83A5D09"},
    "accepted_urdf": {"path": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf", "bytes": 11321, "sha256": "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"},
    "scene_schema": {"path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json", "bytes": 6733, "sha256": "67252BCE1259414876103EE3B6AF25ACC4A33E5A36B73AF974BD4004C285141C"},
    "execution_mount": {"path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/EXECUTION_MOUNT_BINDING_V1.json", "bytes": 3477, "sha256": "B7758F751E273CE21CCD5132C23F2514524DE7613E31B33646E027603B0F6653"},
    "preexisting_base_certificate": {"path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1/A_BASE_LINK_GLOBAL_MOTION_CERTIFICATE_V1.json", "bytes": 6097, "sha256": "332E2C67359BE2507058748061227F73FC5938048BAD2D319F19C27815031010"},
    "wp11_cad_urdf_calibration": {"path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml", "bytes": 36293, "sha256": "7463C1309C3530A42BB32CB4A661FFA56575691DFB7A4BE801AAE9094BEB51E1"},
    "m5_mesh_frame_decision": {"path": "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json", "bytes": 32652, "sha256": "2A99484C6CE55B402CB06380F5DCB71D5A8B4BA622A371EEF72F4EC69EF124FF"},
    "urdf_eol_equivalence": {"path": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/11_validation/URDF_LINE_ENDING_HASH_EQUIVALENCE_RECEIPT.json", "bytes": 950, "sha256": "DF8D4624B2E33E7DDC93613DE86C663AC230C7F76A06D875ED08037FFE37E7AF"},
    "physical_dynamics_bridge": {"path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml", "bytes": 12145, "sha256": "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C"},
}

Q_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
Q_MIN = [-2.8, -3.14, -3.14, -1.87, -1.57, -3.14]
Q_MAX = [2.8, 0.0, 0.0, 1.57, 1.57, 3.14]

ELIGIBILITY_NAME = "M01_RIGID_KINEMATIC_MOTION_ELIGIBILITY_MATRIX_V1.csv"
CANDIDATE_NAME = "A_B601_RIGID_KINEMATIC_CANDIDATE_BOUNDS_V1.json"
SYSTEM_BATCH_NAME = "M01_RIGID_KINEMATIC_SYSTEM_CERTIFICATE_BATCH_V1.json"
RECOMPUTE_NAME = "INDEPENDENT_RIGID_KINEMATIC_RECOMPUTE_V1.json"
GATE_NAME = "M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_GATE_V1.json"
MANIFEST_NAME = "M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_PACKAGE_SHA256_V1.csv"
RELEASE_RECEIPT_NAME = "STANDALONE_RELEASE_VALIDATION_RECEIPT_V1.json"

INCLUDED_FILES = sorted([
    "README.md",
    "build_m01_rigid_kinematic_motion_cert_batch.py",
    "validate_m01_rigid_kinematic_motion_cert_batch.py",
    "test_m01_rigid_kinematic_motion_cert_batch.py",
    ELIGIBILITY_NAME,
    CANDIDATE_NAME,
    SYSTEM_BATCH_NAME,
    RECOMPUTE_NAME,
    GATE_NAME,
])

ELIGIBILITY_HEADERS = [
    "object_id", "category", "motion_class", "active_when", "frame_registration_present",
    "frame_relationship_bound", "operational_asset_ready", "registration_runtime_pose_bound",
    "accepted_urdf_q_domain_available", "design_candidate_bound_emitted",
    "preexisting_system_certificate_observed", "batch_system_certificate_emitted",
    "batch_system_motion_authority_credit", "system_certificate_eligible_in_this_batch",
    "readiness", "blockers", "disposition",
]

CANDIDATE_TOP_KEYS = {
    "schema", "generated_utc", "authority", "source_pins", "units", "q_contract", "method",
    "candidates", "summary", "maximum_claim", "verdict",
}
CANDIDATE_ROW_KEYS = {
    "object_id", "motion_class", "authority", "selected_design_screening_asset", "registration",
    "urdf_chain", "q_order", "q_domain_lower_rad", "q_domain_upper_rad", "scene_type_domain",
    "owner_scene_values_consumed", "raw_asset_vertex_radius_mm", "scene_offset_envelope_mm",
    "geometry_reference_radius_candidate_mm", "global_L_candidate_mm_per_rad",
    "coefficient_ceiling_resolution_mm_per_rad", "analytic_proof", "candidate_input_binding",
    "candidate_input_binding_sha256", "candidate_evidence_sha256", "operational_asset_ready",
    "system_certificate_eligible", "system_motion_authority_credit", "pair_eligible",
    "pair_derating_authority_bound", "centerline_hausdorff_bound_mm",
    "radius_uncertainty_bound_mm", "model_uncertainty_bound_mm", "numeric_uncertainty_bound_mm",
    "blockers", "disposition",
}
SYSTEM_TOP_KEYS = {
    "schema", "generated_utc", "authority", "source_pins", "parent_contract_snapshot",
    "preexisting_append_only_certificate_observation", "candidate_document_sha256",
    "system_certificates", "batch_new_system_certificate_count", "batch_system_motion_authority_credit",
    "effective_observed_append_only_system_certificate_count_after_batch",
    "system_motion_certificate_required", "remaining_without_observed_append_only_system_certificate",
    "scene_authoritative_values_bound", "scene_authoritative_values_required", "stage_instances_bound",
    "stage_instances_required", "clearance_policy_rows_bound", "clearance_policy_rows_required",
    "pair_queries_executed", "pair_queries_required", "edges_certified", "pair_evaluation_authorized",
    "edge_evaluation_authorized", "path_search_authorized", "path_search_executed",
    "next_stage_authorized", "release_credit", "retained_holds", "maximum_claim", "verdict",
}
GATE_TOP_KEYS = {
    "schema", "generated_utc", "authority", "review_status", "decision_rule", "checks",
    "checks_passed", "checks_total", "counters", "source_pins", "local_artifact_pins",
    "manifest_policy", "candidate_bound_gate_pass", "system_motion_certificate_gate_pass",
    "system_collision_gate_pass", "pair_evaluation_authorized", "edge_evaluation_authorized",
    "path_search_authorized", "next_stage_authorized", "release_credit", "retained_holds",
    "maximum_claim", "verdict",
}

CHECK_NAMES = [
    "G01_all_12_frozen_source_pins_match",
    "G02_registry_is_exactly_150_unique_active_objects",
    "G03_registry_category_counts_are_A10_C9_F4_R121_S6",
    "G04_motion_class_partition_is_124_8_9_9",
    "G05_collision_registration_set_is_exactly_the_10_A_objects",
    "G06_only_A_base_link_has_operational_asset_authority",
    "G07_preexisting_base_certificate_is_observed_not_reissued",
    "G08_accepted_urdf_is_10_links_9_joints_root_base_link",
    "G09_q_order_and_limits_are_exactly_accepted_urdf",
    "G10_execution_mount_spelling_is_bound_but_not_promoted_to_pair_authority",
    "G11_nine_nonbase_A_design_assets_are_hash_frame_and_unit_bound",
    "G12_nine_candidate_bounds_cover_full_accepted_q_domain",
    "G13_candidate_coefficients_are_finite_nonnegative_and_bool_free",
    "G14_owner_scene_values_consumed_is_zero",
    "G15_gripper_finger_offsets_use_schema_domain_not_owner_values",
    "G16_all_candidate_bounds_are_explicitly_nonoperational",
    "G17_all_candidate_system_eligibility_values_are_false",
    "G18_all_candidate_system_motion_credits_are_exactly_zero",
    "G19_pair_derate_unknowns_remain_null",
    "G20_system_certificate_batch_is_exactly_empty",
    "G21_parent_contract_snapshot_remains_zero_of_150",
    "G22_effective_append_only_observation_remains_only_base_one_of_150",
    "G23_scene_values_and_instances_remain_zero",
    "G24_clearance_and_pair_counts_remain_zero_of_11166",
    "G25_edge_path_next_and_release_authorities_remain_false",
    "G26_independent_recompute_exactly_reproduces_all_9_candidates",
    "G27_independent_preseal_negative_controls_all_rejected",
    "G28_append_only_scope_does_not_modify_or_reissue_parent_gate",
]


class ValidationError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValidationError(code)


def object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"JSON_DUPLICATE_KEY:{key}")
        result[key] = value
    return result


def no_nonfinite_constant(value: str) -> None:
    raise ValidationError(f"JSON_NONFINITE_CONSTANT:{value}")


def strict_json_text(text: str) -> Any:
    return json.loads(text, object_pairs_hook=object_no_duplicates, parse_constant=no_nonfinite_constant)


def strict_json_file(path: Path) -> Any:
    try:
        return strict_json_text(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ValidationError(f"JSON_UTF8_ERROR:{path.name}") from exc


def file_sha(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1 << 20)
            if not block:
                break
            state.update(block)
    return state.hexdigest().upper()


def canon_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canon_sha(value: Any) -> str:
    return hashlib.sha256(canon_bytes(value)).hexdigest().upper()


def emit_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def exact_keys(value: Any, expected: set[str], code: str) -> None:
    require(type(value) is dict and set(value) == expected, code)


def finite_nonnegative_number(value: Any) -> bool:
    return type(value) in (int, float) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def verify_sources() -> dict[str, dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for key, frozen in FROZEN_SOURCES.items():
        path = PROJECT_ROOT / frozen["path"]
        require(path.is_file(), f"SOURCE_MISSING:{key}")
        size = path.stat().st_size
        digest = file_sha(path)
        require(size == frozen["bytes"], f"SOURCE_BYTES_DRIFT:{key}")
        require(digest == frozen["sha256"], f"SOURCE_HASH_DRIFT:{key}")
        observed[key] = {"path": frozen["path"], "bytes": size, "sha256": digest}
    return observed


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def vector3(text: str | None, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if text is None:
        return default
    tokens = text.split()
    require(len(tokens) == 3, "URDF_VECTOR_ARITY")
    result = tuple(float(token) for token in tokens)
    require(all(math.isfinite(item) for item in result), "URDF_VECTOR_NONFINITE")
    return result  # type: ignore[return-value]


def independent_urdf_parse() -> dict[str, Any]:
    root = ET.fromstring((PROJECT_ROOT / FROZEN_SOURCES["accepted_urdf"]["path"]).read_bytes())
    require(root.tag == "robot" and root.attrib.get("name") == "arm_b601_v1", "URDF_IDENTITY_DRIFT")
    links = [link.attrib["name"] for link in root.findall("link")]
    joints: list[dict[str, Any]] = []
    child_set: set[str] = set()
    for element in root.findall("joint"):
        parent_element = element.find("parent")
        child_element = element.find("child")
        require(parent_element is not None and child_element is not None, "URDF_PARENT_CHILD_MISSING")
        origin = element.find("origin")
        axis = element.find("axis")
        limit = element.find("limit")
        item = {
            "name": element.attrib["name"],
            "type": element.attrib["type"],
            "parent": parent_element.attrib["link"],
            "child": child_element.attrib["link"],
            "origin": vector3(origin.attrib.get("xyz") if origin is not None else None, (0.0, 0.0, 0.0)),
            "rpy": vector3(origin.attrib.get("rpy") if origin is not None else None, (0.0, 0.0, 0.0)),
            "axis": vector3(axis.attrib.get("xyz") if axis is not None else None, (1.0, 0.0, 0.0)),
            "lower": float(limit.attrib["lower"]) if limit is not None and limit.attrib.get("lower") is not None else None,
            "upper": float(limit.attrib["upper"]) if limit is not None and limit.attrib.get("upper") is not None else None,
        }
        require(item["child"] not in child_set, f"URDF_DUPLICATE_CHILD:{item['child']}")
        child_set.add(item["child"])
        joints.append(item)
    roots = set(links) - child_set
    require(roots == {"base_link"}, "URDF_ROOT_NOT_BASE_LINK")
    require(len(links) == 10 and len(set(links)) == 10 and len(joints) == 9, "URDF_GRAPH_COUNT_DRIFT")
    qmap = {joint["name"]: joint for joint in joints}
    require(all(name in qmap for name in Q_NAMES), "URDF_Q_JOINT_MISSING")
    require([qmap[name]["lower"] for name in Q_NAMES] == Q_MIN, "URDF_Q_LOWER_DRIFT")
    require([qmap[name]["upper"] for name in Q_NAMES] == Q_MAX, "URDF_Q_UPPER_DRIFT")
    for name in Q_NAMES:
        require(qmap[name]["type"] == "revolute", f"URDF_Q_TYPE_DRIFT:{name}")
        length = math.sqrt(sum(component * component for component in qmap[name]["axis"]))
        require(abs(length - 1.0) <= 1e-12, f"URDF_Q_AXIS_NOT_UNIT:{name}")
    return {"name": root.attrib["name"], "links": links, "joints": joints, "root": "base_link"}


def chain_to(urdf: dict[str, Any], frame: str) -> list[dict[str, Any]]:
    incoming = {joint["child"]: joint for joint in urdf["joints"]}
    sequence: list[dict[str, Any]] = []
    node = frame
    visited: set[str] = set()
    while node != urdf["root"]:
        require(node not in visited and node in incoming, f"URDF_CHAIN_FAILURE:{frame}")
        visited.add(node)
        edge = incoming[node]
        sequence.append(edge)
        node = edge["parent"]
    sequence.reverse()
    return sequence


def ply_recompute(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        header: list[bytes] = []
        while True:
            line = stream.readline()
            require(bool(line), f"PLY_HEADER_TRUNCATED:{path.name}")
            clean = line.rstrip(b"\r\n")
            header.append(clean)
            if clean == b"end_header":
                break
        require(header[0] == b"ply" and b"format binary_little_endian 1.0" in header, f"PLY_FORMAT_DRIFT:{path.name}")
        vertex_decl = [line for line in header if line.startswith(b"element vertex ")]
        require(len(vertex_decl) == 1, f"PLY_VERTEX_DECLARATION_DRIFT:{path.name}")
        count = int(vertex_decl[0].split()[2])
        properties = [line for line in header if line.startswith(b"property ")]
        require(properties[:3] == [b"property float x", b"property float y", b"property float z"], f"PLY_VERTEX_LAYOUT_DRIFT:{path.name}")
        buffer = stream.read(count * struct.calcsize("<fff"))
        require(len(buffer) == count * 12, f"PLY_VERTEX_BYTES_TRUNCATED:{path.name}")
    low = [float("inf")] * 3
    high = [-float("inf")] * 3
    greatest_sq = 0.0
    for vertex in struct.iter_unpack("<fff", buffer):
        require(all(math.isfinite(value) for value in vertex), f"PLY_VERTEX_NONFINITE:{path.name}")
        for index, value in enumerate(vertex):
            if value < low[index]:
                low[index] = value
            if value > high[index]:
                high[index] = value
        current_sq = vertex[0] * vertex[0] + vertex[1] * vertex[1] + vertex[2] * vertex[2]
        if current_sq > greatest_sq:
            greatest_sq = current_sq
    return {"vertex_count": count, "min_m": low, "max_m": high, "radius_m": math.sqrt(greatest_sq)}


def upward_mm(metres: float) -> float:
    require(finite_nonnegative_number(metres), "NUMERIC_LENGTH_INVALID")
    return math.ceil(metres * 1_000_000_000_000.0) / 1_000_000_000.0


def length3(values: tuple[float, float, float]) -> float:
    return math.sqrt(values[0] * values[0] + values[1] * values[1] + values[2] * values[2])


def rotation_matrix_from_rpy(rpy: tuple[float, float, float]) -> tuple[tuple[float, float, float], ...]:
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def matrix_vector(
    matrix: tuple[tuple[float, float, float], ...],
    vector: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(sum(matrix[row][col] * vector[col] for col in range(3)) for row in range(3))  # type: ignore[return-value]


def validate_A_registration_identity_se3(
    registrations: dict[str, dict[str, Any]], expected_A_ids: set[str]
) -> dict[str, Any]:
    require(len(registrations) == 10 and set(registrations) == expected_A_ids, "REGISTRATION_A_SET_DRIFT")
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    for object_id in sorted(expected_A_ids):
        row = registrations[object_id]
        transform = row.get("T_registration_frame_asset_storage")
        require(
            type(transform) is dict and set(transform) == {"rotation", "translation", "translation_unit"},
            f"A_REGISTRATION_SE3_SCHEMA_INVALID:{object_id}",
        )
        require(transform["rotation"] == "IDENTITY", f"A_REGISTRATION_ROTATION_NOT_IDENTITY:{object_id}")
        rotation = identity
        require(
            all(math.isfinite(value) for matrix_row in rotation for value in matrix_row),
            f"A_REGISTRATION_ROTATION_NONFINITE:{object_id}",
        )
        orthogonality_error = max(
            abs(sum(rotation[k][row_index] * rotation[k][col_index] for k in range(3)) - (1.0 if row_index == col_index else 0.0))
            for row_index in range(3)
            for col_index in range(3)
        )
        determinant = (
            rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
            - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
            + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
        )
        require(
            orthogonality_error <= 1e-15 and abs(determinant - 1.0) <= 1e-15,
            f"A_REGISTRATION_ROTATION_NOT_SO3:{object_id}",
        )
        translation = transform["translation"]
        require(
            type(translation) is list
            and len(translation) == 3
            and all(type(value) in (int, float) and not isinstance(value, bool) and math.isfinite(value) for value in translation),
            f"A_REGISTRATION_TRANSLATION_NOT_FINITE_VECTOR3:{object_id}",
        )
        require(transform["translation_unit"] == "m", f"A_REGISTRATION_TRANSLATION_UNIT_DRIFT:{object_id}")
        require(all(float(value) == 0.0 for value in translation), f"A_REGISTRATION_TRANSFORM_NOT_IDENTITY:{object_id}")
        require(row.get("frame_relationship_bound") is True, f"A_REGISTRATION_FRAME_RELATIONSHIP_UNBOUND:{object_id}")
        require(
            row.get("accepted_urdf_registration_frame") == row.get("asset_storage_frame"),
            f"A_REGISTRATION_LINK_FRAME_IDENTITY_MISMATCH:{object_id}",
        )
    return {
        "registration_count": 10,
        "finite_legal_se3_count": 10,
        "identity_link_frame_registration_count": 10,
        "rotation_determinant": 1.0,
        "maximum_orthogonality_error": 0.0,
    }


def validate_gripper_prismatic_contract(
    urdf: dict[str, Any], registrations: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    joint_map = {joint["name"]: joint for joint in urdf["joints"]}
    specs = {
        "A::gripper_left": ("gripper_joint1", "gripper_left", "gripper_joint1_m"),
        "A::gripper_right": ("gripper_joint2", "gripper_right", "gripper_joint2_m"),
    }
    evidence: dict[str, dict[str, Any]] = {}
    for object_id, (joint_name, child, state_variable) in specs.items():
        joint = joint_map.get(joint_name)
        require(joint is not None and joint["type"] == "prismatic", f"GRIPPER_PRISMATIC_JOINT_INVALID:{object_id}")
        require(
            joint["parent"] == "gripper_link" and joint["child"] == child,
            f"GRIPPER_PRISMATIC_PARENT_CHILD_DRIFT:{object_id}",
        )
        axis = joint["axis"]
        require(all(math.isfinite(value) for value in axis), f"GRIPPER_PRISMATIC_AXIS_NONFINITE:{object_id}")
        axis_norm = length3(axis)
        require(abs(axis_norm - 1.0) <= 1e-12, f"GRIPPER_PRISMATIC_AXIS_NOT_UNIT:{object_id}")
        lower, upper = joint["lower"], joint["upper"]
        require(
            type(lower) in (int, float)
            and type(upper) in (int, float)
            and not isinstance(lower, bool)
            and not isinstance(upper, bool)
            and math.isfinite(lower)
            and math.isfinite(upper)
            and lower <= upper,
            f"GRIPPER_PRISMATIC_LIMIT_INVALID:{object_id}",
        )
        require(lower == 0.0 and upper == 0.0715, f"GRIPPER_PRISMATIC_LIMIT_DRIFT:{object_id}")
        axis_parent = matrix_vector(rotation_matrix_from_rpy(joint["rpy"]), axis)
        require(abs(length3(axis_parent) - 1.0) <= 1e-12, f"GRIPPER_PRISMATIC_PARENT_AXIS_NOT_UNIT:{object_id}")
        motion = registrations[object_id]["motion_registration"]
        registered_axis_raw = motion.get("axis_in_parent_frame_from_accepted_urdf")
        require(
            type(registered_axis_raw) is list
            and len(registered_axis_raw) == 3
            and all(type(value) in (int, float) and not isinstance(value, bool) and math.isfinite(value) for value in registered_axis_raw),
            f"GRIPPER_REGISTERED_AXIS_NONFINITE:{object_id}",
        )
        registered_axis = tuple(float(value) for value in registered_axis_raw)
        require(abs(length3(registered_axis) - 1.0) <= 1e-12, f"GRIPPER_REGISTERED_AXIS_NOT_UNIT:{object_id}")
        require(
            max(abs(left - right) for left, right in zip(axis_parent, registered_axis)) <= 1e-15,
            f"GRIPPER_REGISTERED_AXIS_DIRECTION_DRIFT:{object_id}",
        )
        require(motion.get("allowed_domain_m") == [lower, upper], f"GRIPPER_PRISMATIC_DOMAIN_LIMIT_DRIFT:{object_id}")
        require(motion.get("state_variable") == state_variable, f"GRIPPER_PRISMATIC_STATE_VARIABLE_DRIFT:{object_id}")
        stroke_m = upper - lower
        full_travel_envelope_m = max(abs(lower), abs(upper))
        require(
            stroke_m == 0.0715 and full_travel_envelope_m == stroke_m,
            f"GRIPPER_PRISMATIC_FULL_TRAVEL_ENVELOPE_DRIFT:{object_id}",
        )
        evidence[object_id] = {
            "accepted_urdf_joint": joint_name,
            "axis_joint_frame": list(axis),
            "axis_parent_frame": list(axis_parent),
            "axis_norm": axis_norm,
            "lower_m": lower,
            "upper_m": upper,
            "stroke_m": stroke_m,
            "full_travel_envelope_m": full_travel_envelope_m,
            "envelope_composition_rule": "RAW_LINK_FRAME_RADIUS_PLUS_FULL_PRISMATIC_TRAVEL_ENVELOPE_EXACTLY_ONCE",
        }
    return evidence


def classify(object_id: str, contract: dict[str, Any]) -> str:
    j3 = contract["motion_classes"]["J3_HIDDEN_TRANSLATION"]["object_ids"]
    j4 = contract["motion_classes"]["J4_TRAVEL_TRANSLATION"]["object_motion_gain"]
    cable = contract["motion_classes"]["C_SECTION_CAPSULE"]["object_ids"]
    memberships = [object_id in j3, object_id in j4, object_id in cable]
    require(sum(memberships) <= 1, f"MOTION_CLASS_OVERLAP:{object_id}")
    if memberships[0]:
        return "J3_HIDDEN_TRANSLATION"
    if memberships[1]:
        return "J4_TRAVEL_TRANSLATION"
    if memberships[2]:
        return "C_SECTION_CAPSULE"
    return "DIRECT_RIGID_FK_CANDIDATE"


def candidate_asset(obj: dict[str, Any]) -> dict[str, Any]:
    chosen = obj["geometry"].get("narrowphase_candidate") or obj["geometry"].get("candidate_source_surface")
    require(type(chosen) is dict, f"CANDIDATE_ASSET_ABSENT:{obj['object_id']}")
    return chosen


def independent_expected_candidate(
    obj: dict[str, Any],
    registration: dict[str, Any],
    urdf: dict[str, Any],
    source_records: dict[str, dict[str, Any]],
    gripper_prismatic_evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    object_id = obj["object_id"]
    asset = candidate_asset(obj)
    path = PROJECT_ROOT / asset["path"]
    require(path.is_file(), f"CANDIDATE_ASSET_FILE_MISSING:{object_id}")
    digest = file_sha(path)
    require(digest == asset["sha256"] == registration["asset_sha256"], f"CANDIDATE_ASSET_SOURCE_PIN_DRIFT:{object_id}")
    require(asset["units"] == registration["asset_units"] == "m", f"CANDIDATE_ASSET_UNITS_DRIFT:{object_id}")
    ply = ply_recompute(path)
    declared_bounds = asset.get("bounds_link_m") or asset.get("bounds_gripper_link_m")
    require(type(declared_bounds) is list and len(declared_bounds) == 2, f"CANDIDATE_DECLARED_BOUNDS_MISSING:{object_id}")
    for actual, declared in zip(ply["min_m"] + ply["max_m"], declared_bounds[0] + declared_bounds[1]):
        require(float(declared) - 2e-7 <= actual <= float(declared) + 2e-7, f"CANDIDATE_DECLARED_BOUNDS_DRIFT:{object_id}")
    frame = registration["accepted_urdf_registration_frame"]
    require(frame in urdf["links"], f"CANDIDATE_FRAME_NOT_IN_URDF:{object_id}")
    chain = chain_to(urdf, frame)
    motion = registration["motion_registration"]
    scene_offset_m = 0.0
    scene_domain: dict[str, Any] | None = None
    if motion["type"] == "PRISMATIC_TRANSLATION_FROM_CLOSED_TRAVEL_ZERO":
        require(motion["allowed_domain_m"] == [0.0, 0.0715], f"CANDIDATE_SCENE_DOMAIN_DRIFT:{object_id}")
        require(object_id in gripper_prismatic_evidence, f"CANDIDATE_GRIPPER_EVIDENCE_MISSING:{object_id}")
        scene_offset_m = gripper_prismatic_evidence[object_id]["full_travel_envelope_m"]
        scene_domain = {"field": motion["state_variable"], "domain_m": [0.0, 0.0715], "owner_value_consumed": False, "edge_rule": "STATE_MUST_BE_CONSTANT_ON_CERTIFIED_EDGE"}
    else:
        require(motion["type"] == "RIGID_LINK_LOCAL", f"CANDIDATE_MOTION_TYPE_DRIFT:{object_id}")
    expanded_radius_m = ply["radius_m"] + scene_offset_m
    chain_joint_names = [edge["name"] for edge in chain]
    vector: list[float] = []
    for joint_name in Q_NAMES:
        if joint_name not in chain_joint_names:
            vector.append(0.0)
        else:
            position = chain_joint_names.index(joint_name)
            tail = sum(length3(edge["origin"]) for edge in chain[position + 1 :])
            vector.append(upward_mm(expanded_radius_m + tail))
    input_binding = {
        "object_id": object_id,
        "motion_class": "DIRECT_RIGID_FK_CANDIDATE",
        "registry_sha256": source_records["system_registry"]["sha256"],
        "motion_contract_sha256": source_records["motion_contract"]["sha256"],
        "accepted_urdf_raw_sha256": source_records["accepted_urdf"]["sha256"],
        "collision_registration_sha256": source_records["collision_registration"]["sha256"],
        "asset_readiness_sha256": source_records["asset_readiness"]["sha256"],
        "scene_schema_sha256": source_records["scene_schema"]["sha256"],
        "execution_mount_sha256": source_records["execution_mount"]["sha256"],
        "physical_dynamics_bridge_sha256": source_records["physical_dynamics_bridge"]["sha256"],
        "wp11_cad_urdf_calibration_sha256": source_records["wp11_cad_urdf_calibration"]["sha256"],
        "local_design_screening_asset_sha256": digest,
        "asset_storage_frame": registration["asset_storage_frame"],
        "accepted_urdf_registration_frame": frame,
        "q_domain_lower_rad": Q_MIN,
        "q_domain_upper_rad": Q_MAX,
        "scene_type_domain": scene_domain,
        "derivation_method": "TRIANGLE_INEQUALITY_FULL_CHAIN_ORIGIN_NORMS_PLUS_LINK_LOCAL_VERTEX_RADIUS_AND_DECLARED_SCENE_OFFSET_ENVELOPE",
    }
    return {
        "object_id": object_id,
        "asset": asset,
        "asset_path": path,
        "asset_sha256": digest,
        "asset_bytes": path.stat().st_size,
        "ply": ply,
        "frame": frame,
        "chain": chain,
        "scene_domain": scene_domain,
        "scene_offset_mm": scene_offset_m * 1000.0,
        "geometry_reference_radius_mm": upward_mm(expanded_radius_m),
        "L": vector,
        "input_binding": input_binding,
        "input_binding_sha256": canon_sha(input_binding),
        "evidence_sha256": canon_sha({
            "input_binding_sha256": canon_sha(input_binding),
            "raw_asset_vertex_radius_mm": ply["radius_m"] * 1000.0,
            "scene_offset_envelope_mm": scene_offset_m * 1000.0,
            "geometry_reference_radius_candidate_mm": upward_mm(expanded_radius_m),
            "global_L_candidate_mm_per_rad": vector,
        }),
    }


def load_authoritative_context() -> dict[str, Any]:
    sources = verify_sources()
    registry = strict_json_file(PROJECT_ROOT / FROZEN_SOURCES["system_registry"]["path"])
    contract = strict_json_file(PROJECT_ROOT / FROZEN_SOURCES["motion_contract"]["path"])
    registration_doc = strict_json_file(PROJECT_ROOT / FROZEN_SOURCES["collision_registration"]["path"])
    scene = strict_json_file(PROJECT_ROOT / FROZEN_SOURCES["scene_schema"]["path"])
    mount = strict_json_file(PROJECT_ROOT / FROZEN_SOURCES["execution_mount"]["path"])
    base_cert = strict_json_file(PROJECT_ROOT / FROZEN_SOURCES["preexisting_base_certificate"]["path"])
    readiness_headers, readiness_rows = read_csv(PROJECT_ROOT / FROZEN_SOURCES["asset_readiness"]["path"])
    require(len(registry["objects"]) == 150 and len({row["object_id"] for row in registry["objects"]}) == 150, "REGISTRY_150_UNIQUE_REQUIRED")
    require(readiness_headers == ["id", "category", "row_class", "active_in_current_pair_universe", "path", "hash_algorithm", "hash", "bytes", "units", "frame", "state_selector", "closed", "operational_authority", "representation_debit", "readiness", "blocker"], "READINESS_HEADER_DRIFT")
    active = {row["id"]: row for row in readiness_rows if row["row_class"] == "ACTIVE_OBJECT"}
    require(len(active) == 150 and set(active) == {row["object_id"] for row in registry["objects"]}, "READINESS_ACTIVE_SET_DRIFT")
    registrations = {row["object_id"]: row for row in registration_doc["registrations"]}
    a_set = {row["object_id"] for row in registry["objects"] if row["category"] == "A"}
    registration_se3 = validate_A_registration_identity_se3(registrations, a_set)
    require([key for key, row in active.items() if row["operational_authority"] == "true"] == ["A::base_link"], "OPERATIONAL_OBJECT_SET_DRIFT")
    require(scene["current_instances"]["stage_instances_bound"] == 0 and scene["current_instances"]["stage_instances_required"] == 3, "SCENE_INSTANCE_SNAPSHOT_DRIFT")
    require(scene["current_instances"]["legacy_required_values_bound"] == 0 and scene["current_instances"]["legacy_required_values_total"] == 9, "SCENE_VALUE_SNAPSHOT_DRIFT")
    require(mount["execution_mount_numeric_spelling_bound"] is True and mount["pair_evaluation_authorized"] is False, "MOUNT_AUTHORITY_DRIFT")
    require(base_cert["object_id"] == "A::base_link" and type(base_cert["system_motion_authority_credit"]) is int and base_cert["system_motion_authority_credit"] == 1, "BASE_CERTIFICATE_DRIFT")
    urdf = independent_urdf_parse()
    gripper_prismatic = validate_gripper_prismatic_contract(urdf, registrations)
    category_counts: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    for obj in registry["objects"]:
        category_counts[obj["category"]] = category_counts.get(obj["category"], 0) + 1
        label = classify(obj["object_id"], contract)
        class_counts[label] = class_counts.get(label, 0) + 1
    require(category_counts == {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6}, "REGISTRY_CATEGORY_COUNTS_DRIFT")
    require(class_counts == {"DIRECT_RIGID_FK_CANDIDATE": 124, "J3_HIDDEN_TRANSLATION": 8, "J4_TRAVEL_TRANSLATION": 9, "C_SECTION_CAPSULE": 9}, "MOTION_CLASS_COUNTS_DRIFT")
    expected: dict[str, dict[str, Any]] = {}
    for obj in sorted((row for row in registry["objects"] if row["category"] == "A" and row["object_id"] != "A::base_link"), key=lambda row: row["object_id"]):
        expected[obj["object_id"]] = independent_expected_candidate(
            obj,
            registrations[obj["object_id"]],
            urdf,
            sources,
            gripper_prismatic,
        )
    return {
        "sources": sources, "registry": registry, "contract": contract, "registration_doc": registration_doc,
        "registrations": registrations, "active_readiness": active, "scene": scene, "mount": mount,
        "base_cert": base_cert, "urdf": urdf, "category_counts": category_counts,
        "class_counts": class_counts, "expected_candidates": expected,
        "registration_se3": registration_se3, "gripper_prismatic": gripper_prismatic,
    }


def validate_candidate_document(document: Any, context: dict[str, Any]) -> None:
    exact_keys(document, CANDIDATE_TOP_KEYS, "CANDIDATE_TOP_LEVEL_KEYS_DRIFT")
    require(document["schema"] == "A_B601_RIGID_KINEMATIC_CANDIDATE_BOUNDS_V1", "CANDIDATE_SCHEMA_DRIFT")
    require(document["generated_utc"] == "DETERMINISTIC_BUILD_NO_WALLCLOCK", "CANDIDATE_GENERATION_TAG_DRIFT")
    require(document["authority"] == "NINE_DESIGN_SCREENING_RIGID_KINEMATIC_CANDIDATE_BOUNDS_ONLY__NOT_SYSTEM_CERTIFICATES", "CANDIDATE_AUTHORITY_ESCALATION")
    require(document["source_pins"] == context["sources"], "CANDIDATE_SOURCE_PIN_DRIFT")
    require(document["units"] == {"urdf_translation": "m", "joint_coordinate": "rad", "candidate_coefficient": "mm/rad", "scene_prismatic_state": "m"}, "CANDIDATE_UNITS_DRIFT")
    require(document["q_contract"] == {"order": Q_NAMES, "lower_rad": Q_MIN, "upper_rad": Q_MAX, "interpolation": "q(t)=q_a+t*(q_b-q_a), t in [0,1]", "scene_state_constant_on_edge": True}, "CANDIDATE_Q_CONTRACT_DRIFT")
    require(type(document["method"]) is dict and document["method"].get("prohibited_use") == "Candidate vectors may not be loaded by the system edge oracle until an operational asset is promoted and a new system certificate is independently issued", "CANDIDATE_METHOD_SCOPE_DRIFT")
    rows = document["candidates"]
    require(type(rows) is list and len(rows) == 9, "CANDIDATE_COUNT_DRIFT")
    require([row.get("object_id") for row in rows] == sorted(context["expected_candidates"]), "CANDIDATE_OBJECT_ORDER_OR_SET_DRIFT")
    for row in rows:
        exact_keys(row, CANDIDATE_ROW_KEYS, "CANDIDATE_ROW_KEYS_DRIFT")
        object_id = row["object_id"]
        expected = context["expected_candidates"][object_id]
        registration = context["registrations"][object_id]
        asset = expected["asset"]
        require(row["motion_class"] == "DIRECT_RIGID_FK_CANDIDATE", f"CANDIDATE_MOTION_CLASS_DRIFT:{object_id}")
        require(row["authority"] == "DESIGN_SCREENING_KINEMATIC_CANDIDATE_ONLY__NOT_OBJECT_MOTION_BOUND_CERTIFICATE", f"CANDIDATE_ROW_AUTHORITY_ESCALATION:{object_id}")
        selected = row["selected_design_screening_asset"]
        require(type(selected) is dict and selected == {
            "path": asset["path"], "sha256": expected["asset_sha256"], "bytes": expected["asset_bytes"],
            "units": "m", "storage_frame": registration["asset_storage_frame"],
            "vertex_count": expected["ply"]["vertex_count"],
            "vertex_bounds_m": [expected["ply"]["min_m"], expected["ply"]["max_m"]],
            "use_limit": asset["use_limit"],
        }, f"CANDIDATE_SELECTED_ASSET_DRIFT:{object_id}")
        require(row["registration"] == {
            "accepted_urdf_registration_frame": registration["accepted_urdf_registration_frame"],
            "asset_storage_frame": registration["asset_storage_frame"],
            "frame_relationship_bound": registration["frame_relationship_bound"],
            "T_registration_frame_asset_storage": registration["T_registration_frame_asset_storage"],
            "operational_narrowphase_promoted": registration["operational_narrowphase_promoted"],
            "runtime_object_pose_bound": registration["runtime_object_pose_bound"],
            "motion_registration": registration["motion_registration"],
        }, f"CANDIDATE_REGISTRATION_DRIFT:{object_id}")
        expected_chain = [{
            "name": edge["name"], "type": edge["type"], "parent": edge["parent"], "child": edge["child"],
            "origin_xyz_m": list(edge["origin"]), "origin_norm_m": length3(edge["origin"]),
            "axis_joint_frame": list(edge["axis"]),
        } for edge in expected["chain"]]
        require(row["urdf_chain"] == expected_chain, f"CANDIDATE_URDF_CHAIN_DRIFT:{object_id}")
        require(row["q_order"] == Q_NAMES and row["q_domain_lower_rad"] == Q_MIN and row["q_domain_upper_rad"] == Q_MAX, f"CANDIDATE_Q_DOMAIN_DRIFT:{object_id}")
        require(row["scene_type_domain"] == expected["scene_domain"], f"CANDIDATE_SCENE_TYPE_DOMAIN_DRIFT:{object_id}")
        require(type(row["owner_scene_values_consumed"]) is int and row["owner_scene_values_consumed"] == 0, f"CANDIDATE_OWNER_VALUE_CONSUMPTION_DRIFT:{object_id}")
        require(row["raw_asset_vertex_radius_mm"] == expected["ply"]["radius_m"] * 1000.0, f"CANDIDATE_RAW_RADIUS_DRIFT:{object_id}")
        require(row["scene_offset_envelope_mm"] == expected["scene_offset_mm"], f"CANDIDATE_SCENE_OFFSET_DRIFT:{object_id}")
        require(row["geometry_reference_radius_candidate_mm"] == expected["geometry_reference_radius_mm"], f"CANDIDATE_GEOMETRY_RADIUS_DRIFT:{object_id}")
        require(row["global_L_candidate_mm_per_rad"] == expected["L"], f"CANDIDATE_L_VECTOR_DRIFT:{object_id}")
        require(all(finite_nonnegative_number(value) for value in row["global_L_candidate_mm_per_rad"]), f"CANDIDATE_L_NUMERIC_TYPE_DRIFT:{object_id}")
        require(finite_nonnegative_number(row["geometry_reference_radius_candidate_mm"]), f"CANDIDATE_RADIUS_NUMERIC_TYPE_DRIFT:{object_id}")
        require(type(row["coefficient_ceiling_resolution_mm_per_rad"]) is float and row["coefficient_ceiling_resolution_mm_per_rad"] == 1e-9, f"CANDIDATE_CEILING_DRIFT:{object_id}")
        proof = row["analytic_proof"]
        require(type(proof) is dict and proof.get("proof_domain_complete_for_selected_design_screening_surface") is True and proof.get("proof_domain_complete_for_operational_collision_object") is False, f"CANDIDATE_PROOF_SCOPE_DRIFT:{object_id}")
        require(row["candidate_input_binding"] == expected["input_binding"], f"CANDIDATE_INPUT_BINDING_DRIFT:{object_id}")
        require(row["candidate_input_binding_sha256"] == expected["input_binding_sha256"], f"CANDIDATE_INPUT_BINDING_HASH_DRIFT:{object_id}")
        require(row["candidate_evidence_sha256"] == expected["evidence_sha256"], f"CANDIDATE_EVIDENCE_HASH_DRIFT:{object_id}")
        require(row["operational_asset_ready"] is False, f"CANDIDATE_OPERATIONAL_AUTHORITY_ESCALATION:{object_id}")
        require(row["system_certificate_eligible"] is False, f"CANDIDATE_SYSTEM_ELIGIBILITY_ESCALATION:{object_id}")
        require(type(row["system_motion_authority_credit"]) is int and row["system_motion_authority_credit"] == 0, f"CANDIDATE_SYSTEM_CREDIT_ESCALATION:{object_id}")
        require(row["pair_eligible"] is False and row["pair_derating_authority_bound"] is False, f"CANDIDATE_PAIR_AUTHORITY_ESCALATION:{object_id}")
        require(all(row[key] is None for key in ["centerline_hausdorff_bound_mm", "radius_uncertainty_bound_mm", "model_uncertainty_bound_mm", "numeric_uncertainty_bound_mm"]), f"CANDIDATE_UNKNOWN_DERATE_ZERO_FILL:{object_id}")
        required_blockers = {"OPERATIONAL_NARROWPHASE_PROMOTION_ABSENT", "RUNTIME_OBJECT_POSE_NOT_SYSTEM_BOUND", "DESIGN_SCREENING_SURFACE_NOT_CONSUMABLE_AS_OPERATIONAL_COLLISION_SET"}
        if object_id in {"A::gripper_left", "A::gripper_right"}:
            required_blockers.add("OWNER_SCENE_STATE_VALUE_UNBOUND")
        require(type(row["blockers"]) is list and set(row["blockers"]) == required_blockers and len(row["blockers"]) == len(required_blockers), f"CANDIDATE_BLOCKER_DRIFT:{object_id}")
        require(row["disposition"] == "CANDIDATE_BOUND_RETAINED_FOR_REPLAY_AFTER_OPERATIONAL_ASSET_PROMOTION__NO_SYSTEM_CREDIT", f"CANDIDATE_DISPOSITION_ESCALATION:{object_id}")
    require(document["summary"] == {
        "active_registry_objects": 150, "A_objects": 10, "A_frame_registrations": 10,
        "asset_level_operational_objects": 1, "preexisting_base_system_certificate_observed": 1,
        "design_screening_candidate_bounds_emitted": 9, "candidate_bounds_with_full_accepted_q_domain": 9,
        "candidate_bounds_consuming_owner_scene_values": 0, "candidate_bounds_eligible_as_system_certificates": 0,
        "new_system_certificates_emitted": 0,
    }, "CANDIDATE_SUMMARY_DRIFT")
    require(document["maximum_claim"] == "NINE_B601_DESIGN_SCREENING_SURFACE_SETS_HAVE_CONSERVATIVE_FULL_ACCEPTED_Q_DOMAIN_RIGID_KINEMATIC_CANDIDATE_COEFFICIENTS__ZERO_OPERATIONAL_PROMOTION_AND_ZERO_SYSTEM_CREDIT", "CANDIDATE_MAXIMUM_CLAIM_ESCALATION")
    require(document["verdict"] == "CANDIDATE_BOUNDS_DERIVED_FOR_9_OF_9_NONBASE_A_OBJECTS__ALL_WITHHELD_FROM_SYSTEM_CERTIFICATION", "CANDIDATE_VERDICT_DRIFT")


def expected_eligibility(context: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    registrations = context["registrations"]
    candidate_ids = set(context["expected_candidates"])
    for obj in sorted(context["registry"]["objects"], key=lambda row: row["object_id"]):
        object_id = obj["object_id"]
        registration = registrations.get(object_id)
        readiness = context["active_readiness"][object_id]
        operational = readiness["operational_authority"] == "true"
        blockers: list[str] = []
        if registration is None:
            blockers.append("COLLISION_ASSET_FRAME_REGISTRATION_ABSENT")
        elif registration.get("frame_relationship_bound") is not True:
            blockers.append("COLLISION_ASSET_FRAME_RELATIONSHIP_UNBOUND")
        if not operational:
            blockers.append("OPERATIONAL_COLLISION_ASSET_NOT_READY")
        if object_id in {"A::gripper_left", "A::gripper_right"}:
            blockers.append("OWNER_SCENE_STATE_VALUE_UNBOUND")
        if not object_id.startswith("A::"):
            blockers.append("OUTSIDE_B601_ACCEPTED_URDF_RIGID_KINEMATIC_BATCH_SCOPE")
        if object_id == "A::base_link":
            disposition = "PREEXISTING_APPEND_ONLY_BASE_CERTIFICATE_OBSERVED__NOT_REISSUED"
        elif object_id in candidate_ids:
            disposition = "DESIGN_SCREENING_CANDIDATE_BOUND_EMITTED__SYSTEM_CERTIFICATE_WITHHELD"
        else:
            disposition = "NO_CANDIDATE_BOUND_EMITTED__BLOCKED_OR_OUT_OF_SCOPE"
        result.append({
            "object_id": object_id, "category": obj["category"], "motion_class": classify(object_id, context["contract"]),
            "active_when": obj["active_when"], "frame_registration_present": str(registration is not None).lower(),
            "frame_relationship_bound": str(bool(registration and registration.get("frame_relationship_bound") is True)).lower(),
            "operational_asset_ready": str(operational).lower(),
            "registration_runtime_pose_bound": str(bool(registration and registration.get("runtime_object_pose_bound") is True)).lower(),
            "accepted_urdf_q_domain_available": str(object_id.startswith("A::")).lower(),
            "design_candidate_bound_emitted": str(object_id in candidate_ids).lower(),
            "preexisting_system_certificate_observed": str(object_id == "A::base_link").lower(),
            "batch_system_certificate_emitted": "false", "batch_system_motion_authority_credit": "0",
            "system_certificate_eligible_in_this_batch": "false", "readiness": readiness["readiness"],
            "blockers": ";".join(blockers) if blockers else "NONE", "disposition": disposition,
        })
    return result


def validate_eligibility(headers: list[str], rows: list[dict[str, str]], context: dict[str, Any]) -> None:
    require(headers == ELIGIBILITY_HEADERS, "ELIGIBILITY_HEADER_DRIFT")
    require(len(rows) == 150 and len({row["object_id"] for row in rows}) == 150, "ELIGIBILITY_150_UNIQUE_REQUIRED")
    require(rows == expected_eligibility(context), "ELIGIBILITY_ROW_DRIFT")


def validate_system_document(document: Any, context: dict[str, Any]) -> None:
    exact_keys(document, SYSTEM_TOP_KEYS, "SYSTEM_BATCH_TOP_LEVEL_KEYS_DRIFT")
    require(document["schema"] == "M01_RIGID_KINEMATIC_SYSTEM_CERTIFICATE_BATCH_V1", "SYSTEM_BATCH_SCHEMA_DRIFT")
    require(document["generated_utc"] == "DETERMINISTIC_BUILD_NO_WALLCLOCK", "SYSTEM_BATCH_GENERATION_TAG_DRIFT")
    require(document["authority"] == "EMPTY_APPEND_ONLY_SYSTEM_CERTIFICATE_BATCH__DESIGN_CANDIDATES_EXPLICITLY_EXCLUDED", "SYSTEM_BATCH_AUTHORITY_ESCALATION")
    require(document["source_pins"] == context["sources"], "SYSTEM_BATCH_SOURCE_PIN_DRIFT")
    require(document["parent_contract_snapshot"] == {"parent_system_certified_object_motion_bound_count": 0, "parent_system_certified_object_motion_bound_required": 150, "parent_gate_reissued_or_modified": False}, "SYSTEM_BATCH_PARENT_SNAPSHOT_DRIFT")
    require(document["preexisting_append_only_certificate_observation"] == {"object_id": "A::base_link", "certificate_sha256": context["sources"]["preexisting_base_certificate"]["sha256"], "observed_system_motion_authority_credit": 1, "reissued_by_this_batch": False, "counted_as_new_by_this_batch": False}, "SYSTEM_BATCH_BASE_OBSERVATION_DRIFT")
    require(document["candidate_document_sha256"] == file_sha(PACKAGE_DIR / CANDIDATE_NAME), "SYSTEM_BATCH_CANDIDATE_HASH_DRIFT")
    require(document["system_certificates"] == [], "SYSTEM_BATCH_NONEMPTY_CERTIFICATE_ESCAPE")
    int_expected = {
        "batch_new_system_certificate_count": 0, "batch_system_motion_authority_credit": 0,
        "effective_observed_append_only_system_certificate_count_after_batch": 1,
        "system_motion_certificate_required": 150, "remaining_without_observed_append_only_system_certificate": 149,
        "scene_authoritative_values_bound": 0, "scene_authoritative_values_required": 30,
        "stage_instances_bound": 0, "stage_instances_required": 3,
        "clearance_policy_rows_bound": 0, "clearance_policy_rows_required": 11166,
        "pair_queries_executed": 0, "pair_queries_required": 11166, "edges_certified": 0,
    }
    for key, expected in int_expected.items():
        require(type(document[key]) is int and document[key] == expected, f"SYSTEM_BATCH_COUNT_DRIFT:{key}")
    for key in ["pair_evaluation_authorized", "edge_evaluation_authorized", "path_search_authorized", "path_search_executed", "next_stage_authorized", "release_credit"]:
        require(document[key] is False, f"SYSTEM_BATCH_AUTHORITY_ESCALATION:{key}")
    require(document["retained_holds"] == [
        "NINE_NONBASE_A_ASSETS_HAVE_NO_OPERATIONAL_NARROWPHASE_PROMOTION",
        "NINE_NONBASE_A_RUNTIME_OBJECT_POSES_REMAIN_SYSTEM_UNBOUND",
        "ALL_30_OWNER_SCENE_VALUES_AND_ALL_3_SCENE_INSTANCES_REMAIN_UNBOUND",
        "11166_CLEARANCE_POLICY_ROWS_AND_11166_PAIR_QUERIES_REMAIN_ZERO",
        "ZERO_EDGE_CERTIFICATES_AND_NO_PATH_SEARCH_AUTHORITY",
    ], "SYSTEM_BATCH_HOLD_DRIFT")
    require(document["maximum_claim"] == "ZERO_NEW_SYSTEM_MOTION_CERTIFICATES__NINE_DESIGN_CANDIDATES_ARE_NONCONSUMABLE", "SYSTEM_BATCH_MAXIMUM_CLAIM_ESCALATION")
    require(document["verdict"] == "EMPTY_SYSTEM_CERTIFICATE_BATCH__0_NEW_CREDIT__PARENT_0_OF_150_SNAPSHOT_UNCHANGED__PREEXISTING_BASE_APPEND_ONLY_CREDIT_NOT_REISSUED", "SYSTEM_BATCH_VERDICT_DRIFT")


def load_core(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str], list[dict[str, str]]]:
    candidate = strict_json_file(PACKAGE_DIR / CANDIDATE_NAME)
    system = strict_json_file(PACKAGE_DIR / SYSTEM_BATCH_NAME)
    headers, eligibility = read_csv(PACKAGE_DIR / ELIGIBILITY_NAME)
    validate_candidate_document(candidate, context)
    validate_system_document(system, context)
    validate_eligibility(headers, eligibility, context)
    return candidate, system, headers, eligibility


def expect_rejection(name: str, expected_code: str, operation: Callable[[], None]) -> dict[str, str]:
    try:
        operation()
    except ValidationError as exc:
        require(exc.code == expected_code, f"NEGATIVE_CONTROL_WRONG_CODE:{name}:{exc.code}:{expected_code}")
        return {"case": name, "expected_rejection_code": expected_code, "observed_rejection_code": exc.code, "result": "REJECTED_AS_EXPECTED"}
    raise ValidationError(f"NEGATIVE_CONTROL_ESCAPE:{name}")


def run_core_negative_controls(candidate: dict[str, Any], system: dict[str, Any], headers: list[str], eligibility: list[dict[str, str]], context: dict[str, Any]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    def candidate_mutation(name: str, code: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        value = copy.deepcopy(candidate)
        mutate(value)
        results.append(expect_rejection(name, code, lambda: validate_candidate_document(value, context)))

    def system_mutation(name: str, code: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        value = copy.deepcopy(system)
        mutate(value)
        results.append(expect_rejection(name, code, lambda: validate_system_document(value, context)))

    def registration_mutation(name: str, code: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        registrations = copy.deepcopy(context["registrations"])
        mutate(registrations)
        A_ids = {row["object_id"] for row in context["registry"]["objects"] if row["category"] == "A"}
        results.append(
            expect_rejection(name, code, lambda: validate_A_registration_identity_se3(registrations, A_ids))
        )

    def gripper_mutation(
        name: str,
        code: str,
        mutate: Callable[[dict[str, Any], dict[str, Any]], None],
    ) -> None:
        urdf = copy.deepcopy(context["urdf"])
        registrations = copy.deepcopy(context["registrations"])
        mutate(urdf, registrations)
        results.append(
            expect_rejection(name, code, lambda: validate_gripper_prismatic_contract(urdf, registrations))
        )

    registration_mutation(
        "registration_translation_nonidentity",
        "A_REGISTRATION_TRANSFORM_NOT_IDENTITY:A::link1",
        lambda rows: rows["A::link1"]["T_registration_frame_asset_storage"]["translation"].__setitem__(0, 1e-6),
    )
    registration_mutation(
        "registration_translation_nonfinite",
        "A_REGISTRATION_TRANSLATION_NOT_FINITE_VECTOR3:A::link1",
        lambda rows: rows["A::link1"]["T_registration_frame_asset_storage"]["translation"].__setitem__(0, float("nan")),
    )
    registration_mutation(
        "registration_rotation_nonidentity",
        "A_REGISTRATION_ROTATION_NOT_IDENTITY:A::link1",
        lambda rows: rows["A::link1"]["T_registration_frame_asset_storage"].__setitem__("rotation", "ROT_Z_90"),
    )
    gripper_mutation(
        "gripper_registered_axis_norm_mutation",
        "GRIPPER_REGISTERED_AXIS_NOT_UNIT:A::gripper_left",
        lambda _urdf, rows: rows["A::gripper_left"]["motion_registration"].__setitem__(
            "axis_in_parent_frame_from_accepted_urdf", [0.0, -2.0, 0.0]
        ),
    )
    gripper_mutation(
        "gripper_registered_axis_direction_mutation",
        "GRIPPER_REGISTERED_AXIS_DIRECTION_DRIFT:A::gripper_left",
        lambda _urdf, rows: rows["A::gripper_left"]["motion_registration"].__setitem__(
            "axis_in_parent_frame_from_accepted_urdf",
            [-value for value in rows["A::gripper_left"]["motion_registration"]["axis_in_parent_frame_from_accepted_urdf"]],
        ),
    )
    gripper_mutation(
        "gripper_urdf_axis_norm_mutation",
        "GRIPPER_PRISMATIC_AXIS_NOT_UNIT:A::gripper_left",
        lambda urdf, _rows: next(joint for joint in urdf["joints"] if joint["name"] == "gripper_joint1").__setitem__(
            "axis", (2.0, 0.0, 0.0)
        ),
    )
    gripper_mutation(
        "gripper_urdf_axis_direction_mutation",
        "GRIPPER_REGISTERED_AXIS_DIRECTION_DRIFT:A::gripper_left",
        lambda urdf, _rows: next(joint for joint in urdf["joints"] if joint["name"] == "gripper_joint1").__setitem__(
            "axis", (-1.0, 0.0, 0.0)
        ),
    )
    gripper_mutation(
        "gripper_urdf_limit_mutation",
        "GRIPPER_PRISMATIC_LIMIT_DRIFT:A::gripper_left",
        lambda urdf, _rows: next(joint for joint in urdf["joints"] if joint["name"] == "gripper_joint1").__setitem__(
            "upper", 0.07
        ),
    )

    candidate_mutation("candidate_authority_escalation", "CANDIDATE_AUTHORITY_ESCALATION", lambda d: d.__setitem__("authority", "SYSTEM_CERTIFICATE"))
    candidate_mutation("candidate_source_pin_drift", "CANDIDATE_SOURCE_PIN_DRIFT", lambda d: d["source_pins"]["system_registry"].__setitem__("sha256", "0" * 64))
    candidate_mutation("candidate_count_drop", "CANDIDATE_COUNT_DRIFT", lambda d: d["candidates"].pop())
    candidate_mutation("candidate_duplicate_object", "CANDIDATE_OBJECT_ORDER_OR_SET_DRIFT", lambda d: d["candidates"].__setitem__(1, copy.deepcopy(d["candidates"][0])))
    candidate_mutation("candidate_row_extra_key", "CANDIDATE_ROW_KEYS_DRIFT", lambda d: d["candidates"][0].__setitem__("escape", True))
    candidate_mutation("candidate_operational_escalation", "CANDIDATE_OPERATIONAL_AUTHORITY_ESCALATION:A::gripper_left", lambda d: d["candidates"][0].__setitem__("operational_asset_ready", True))
    candidate_mutation("candidate_system_eligibility_escalation", "CANDIDATE_SYSTEM_ELIGIBILITY_ESCALATION:A::gripper_left", lambda d: d["candidates"][0].__setitem__("system_certificate_eligible", True))
    candidate_mutation("candidate_system_credit_escalation", "CANDIDATE_SYSTEM_CREDIT_ESCALATION:A::gripper_left", lambda d: d["candidates"][0].__setitem__("system_motion_authority_credit", 1))
    candidate_mutation("candidate_pair_authority_escalation", "CANDIDATE_PAIR_AUTHORITY_ESCALATION:A::gripper_left", lambda d: d["candidates"][0].__setitem__("pair_eligible", True))
    candidate_mutation("candidate_L_decrease", "CANDIDATE_L_VECTOR_DRIFT:A::gripper_left", lambda d: d["candidates"][0]["global_L_candidate_mm_per_rad"].__setitem__(0, d["candidates"][0]["global_L_candidate_mm_per_rad"][0] - 1.0))
    candidate_mutation("candidate_L_bool", "CANDIDATE_L_VECTOR_DRIFT:A::gripper_left", lambda d: d["candidates"][0]["global_L_candidate_mm_per_rad"].__setitem__(0, True))
    candidate_mutation("candidate_radius_decrease", "CANDIDATE_GEOMETRY_RADIUS_DRIFT:A::gripper_left", lambda d: d["candidates"][0].__setitem__("geometry_reference_radius_candidate_mm", d["candidates"][0]["geometry_reference_radius_candidate_mm"] - 1.0))
    candidate_mutation("candidate_q_domain_mutation", "CANDIDATE_Q_DOMAIN_DRIFT:A::gripper_left", lambda d: d["candidates"][0]["q_domain_lower_rad"].__setitem__(0, -2.7))
    candidate_mutation("candidate_scene_offset_decrease", "CANDIDATE_SCENE_OFFSET_DRIFT:A::gripper_left", lambda d: d["candidates"][0].__setitem__("scene_offset_envelope_mm", 0.0))
    candidate_mutation("candidate_owner_value_consumed", "CANDIDATE_OWNER_VALUE_CONSUMPTION_DRIFT:A::gripper_left", lambda d: d["candidates"][0].__setitem__("owner_scene_values_consumed", 1))
    candidate_mutation("candidate_derate_zero_fill", "CANDIDATE_UNKNOWN_DERATE_ZERO_FILL:A::gripper_left", lambda d: d["candidates"][0].__setitem__("model_uncertainty_bound_mm", 0.0))
    candidate_mutation("candidate_input_hash_mutation", "CANDIDATE_INPUT_BINDING_HASH_DRIFT:A::gripper_left", lambda d: d["candidates"][0].__setitem__("candidate_input_binding_sha256", "F" * 64))
    candidate_mutation("candidate_evidence_hash_mutation", "CANDIDATE_EVIDENCE_HASH_DRIFT:A::gripper_left", lambda d: d["candidates"][0].__setitem__("candidate_evidence_sha256", "F" * 64))
    candidate_mutation("candidate_maximum_claim_escalation", "CANDIDATE_MAXIMUM_CLAIM_ESCALATION", lambda d: d.__setitem__("maximum_claim", "SYSTEM_COMPLETE"))
    candidate_mutation("candidate_summary_new_certificate", "CANDIDATE_SUMMARY_DRIFT", lambda d: d["summary"].__setitem__("new_system_certificates_emitted", 1))

    system_mutation("system_nonempty_certificate_escape", "SYSTEM_BATCH_NONEMPTY_CERTIFICATE_ESCAPE", lambda d: d["system_certificates"].append({"object_id": "A::link1"}))
    system_mutation("system_new_count_escalation", "SYSTEM_BATCH_COUNT_DRIFT:batch_new_system_certificate_count", lambda d: d.__setitem__("batch_new_system_certificate_count", 1))
    system_mutation("system_new_count_bool", "SYSTEM_BATCH_COUNT_DRIFT:batch_new_system_certificate_count", lambda d: d.__setitem__("batch_new_system_certificate_count", False))
    system_mutation("system_parent_snapshot_escalation", "SYSTEM_BATCH_PARENT_SNAPSHOT_DRIFT", lambda d: d["parent_contract_snapshot"].__setitem__("parent_system_certified_object_motion_bound_count", 1))
    system_mutation("system_effective_count_escalation", "SYSTEM_BATCH_COUNT_DRIFT:effective_observed_append_only_system_certificate_count_after_batch", lambda d: d.__setitem__("effective_observed_append_only_system_certificate_count_after_batch", 2))
    system_mutation("system_scene_value_escalation", "SYSTEM_BATCH_COUNT_DRIFT:scene_authoritative_values_bound", lambda d: d.__setitem__("scene_authoritative_values_bound", 1))
    system_mutation("system_pair_query_escalation", "SYSTEM_BATCH_COUNT_DRIFT:pair_queries_executed", lambda d: d.__setitem__("pair_queries_executed", 1))
    system_mutation("system_edge_authority_escalation", "SYSTEM_BATCH_AUTHORITY_ESCALATION:edge_evaluation_authorized", lambda d: d.__setitem__("edge_evaluation_authorized", True))
    system_mutation("system_path_authority_escalation", "SYSTEM_BATCH_AUTHORITY_ESCALATION:path_search_authorized", lambda d: d.__setitem__("path_search_authorized", True))
    system_mutation("system_next_stage_escalation", "SYSTEM_BATCH_AUTHORITY_ESCALATION:next_stage_authorized", lambda d: d.__setitem__("next_stage_authorized", True))
    system_mutation("system_release_credit_escalation", "SYSTEM_BATCH_AUTHORITY_ESCALATION:release_credit", lambda d: d.__setitem__("release_credit", True))

    changed_rows = copy.deepcopy(eligibility)
    changed_rows[0]["batch_system_certificate_emitted"] = "true"
    results.append(expect_rejection("eligibility_system_certificate_escape", "ELIGIBILITY_ROW_DRIFT", lambda: validate_eligibility(headers, changed_rows, context)))
    duplicated_rows = copy.deepcopy(eligibility)
    duplicated_rows[-1] = copy.deepcopy(duplicated_rows[0])
    results.append(expect_rejection("eligibility_duplicate_object", "ELIGIBILITY_150_UNIQUE_REQUIRED", lambda: validate_eligibility(headers, duplicated_rows, context)))
    results.append(expect_rejection("json_duplicate_key", "JSON_DUPLICATE_KEY:a", lambda: strict_json_text('{"a":1,"a":2}')))
    results.append(expect_rejection("json_nan", "JSON_NONFINITE_CONSTANT:NaN", lambda: strict_json_text('{"a":NaN}')))
    results.append(expect_rejection("json_infinity", "JSON_NONFINITE_CONSTANT:Infinity", lambda: strict_json_text('{"a":Infinity}')))
    return results


def core_binding() -> dict[str, Any]:
    names = [ELIGIBILITY_NAME, CANDIDATE_NAME, SYSTEM_BATCH_NAME, "validate_m01_rigid_kinematic_motion_cert_batch.py"]
    files = {name: {"bytes": (PACKAGE_DIR / name).stat().st_size, "sha256": file_sha(PACKAGE_DIR / name)} for name in names}
    return {"files": files, "canonical_sha256": canon_sha(files)}


def expected_recompute(context: dict[str, Any], candidate: dict[str, Any], system: dict[str, Any], headers: list[str], eligibility: list[dict[str, str]]) -> dict[str, Any]:
    negatives = run_core_negative_controls(candidate, system, headers, eligibility, context)
    recomputations = []
    for object_id in sorted(context["expected_candidates"]):
        expected = context["expected_candidates"][object_id]
        row = next(item for item in candidate["candidates"] if item["object_id"] == object_id)
        recomputations.append({
            "object_id": object_id,
            "asset_sha256": expected["asset_sha256"],
            "vertex_count": expected["ply"]["vertex_count"],
            "raw_asset_vertex_radius_mm": expected["ply"]["radius_m"] * 1000.0,
            "scene_offset_envelope_mm": expected["scene_offset_mm"],
            "geometry_reference_radius_candidate_mm": expected["geometry_reference_radius_mm"],
            "global_L_candidate_mm_per_rad": expected["L"],
            "artifact_exact_match": row["global_L_candidate_mm_per_rad"] == expected["L"] and row["geometry_reference_radius_candidate_mm"] == expected["geometry_reference_radius_mm"],
            "system_certificate_eligible": False,
            "system_motion_authority_credit": 0,
        })
    qmap = {joint["name"]: joint for joint in context["urdf"]["joints"]}
    return {
        "schema": "INDEPENDENT_RIGID_KINEMATIC_RECOMPUTE_V1",
        "generated_utc": "DETERMINISTIC_STANDALONE_VALIDATION_NO_WALLCLOCK",
        "authority": "INDEPENDENT_RECOMPUTE_OF_DESIGN_CANDIDATE_ARITHMETIC_AND_ZERO_SYSTEM_CREDIT_ONLY",
        "validator_sha256": file_sha(Path(__file__).resolve()),
        "validator_imported_or_executed_builder": False,
        "source_pins": context["sources"],
        "registry_recompute": {
            "active_unique_objects": 150,
            "category_counts": context["category_counts"],
            "motion_class_counts": context["class_counts"],
            "collision_frame_registration_count": 10,
            "asset_level_operational_count": 1,
            "asset_level_operational_object_ids": ["A::base_link"],
        },
        "collision_registration_se3_recompute": context["registration_se3"],
        "urdf_recompute": {
            "robot_name": context["urdf"]["name"],
            "root_link": context["urdf"]["root"],
            "link_count": len(context["urdf"]["links"]),
            "joint_count": len(context["urdf"]["joints"]),
            "q_order": Q_NAMES,
            "q_domain_lower_rad": Q_MIN,
            "q_domain_upper_rad": Q_MAX,
            "joint_origin_norms_m": {name: length3(qmap[name]["origin"]) for name in Q_NAMES},
            "fixed_gripper_joint_origin_norm_m": length3(next(joint for joint in context["urdf"]["joints"] if joint["name"] == "gripper_joint")["origin"]),
            "gripper_prismatic_full_travel_envelopes": context["gripper_prismatic"],
        },
        "candidate_recomputations": recomputations,
        "candidate_comparisons_passed": sum(row["artifact_exact_match"] is True for row in recomputations),
        "candidate_comparisons_total": len(recomputations),
        "batch_new_system_certificates_recomputed": len(system["system_certificates"]),
        "parent_contract_system_certificate_snapshot": system["parent_contract_snapshot"]["parent_system_certified_object_motion_bound_count"],
        "preexisting_base_certificate_observed": 1,
        "owner_scene_values_consumed": 0,
        "negative_controls": negatives,
        "negative_controls_rejected": sum(row["result"] == "REJECTED_AS_EXPECTED" for row in negatives),
        "negative_controls_total": len(negatives),
        "core_binding": core_binding(),
        "all_independent_checks_pass": True,
        "maximum_claim": "INDEPENDENT_REPRODUCTION_OF_9_DESIGN_SCREENING_CANDIDATE_BOUNDS_AND_CONFIRMATION_OF_0_NEW_SYSTEM_CERTIFICATES",
        "verdict": "INDEPENDENT_RECOMPUTE_PASS__9_CANDIDATE_BOUNDS_EXACT__0_NEW_SYSTEM_CERTIFICATES",
    }


def validate_recompute_receipt(actual: Any, expected: dict[str, Any]) -> None:
    require(actual == expected, "INDEPENDENT_RECOMPUTE_RECEIPT_DRIFT")


def expected_gate(context: dict[str, Any], recompute: dict[str, Any]) -> dict[str, Any]:
    local_names = [ELIGIBILITY_NAME, CANDIDATE_NAME, SYSTEM_BATCH_NAME, RECOMPUTE_NAME]
    local_pins = {name: {"bytes": (PACKAGE_DIR / name).stat().st_size, "sha256": file_sha(PACKAGE_DIR / name)} for name in local_names}
    checks = {name: True for name in CHECK_NAMES}
    holds = [
        "NINE_NONBASE_A_ASSETS_HAVE_NO_OPERATIONAL_NARROWPHASE_PROMOTION",
        "NINE_NONBASE_A_RUNTIME_OBJECT_POSES_REMAIN_SYSTEM_UNBOUND",
        "ALL_30_OWNER_SCENE_VALUES_AND_ALL_3_SCENE_INSTANCES_REMAIN_UNBOUND",
        "11166_CLEARANCE_POLICY_ROWS_AND_11166_PAIR_QUERIES_REMAIN_ZERO",
        "ZERO_EDGE_CERTIFICATES_AND_NO_PATH_SEARCH_AUTHORITY",
    ]
    return {
        "schema": "M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "authority": "APPEND_ONLY_DESIGN_SCREENING_KINEMATIC_CANDIDATE_BOUNDS_ONLY__ZERO_NEW_SYSTEM_MOTION_CERTIFICATES__NO_PARENT_GATE_REISSUE",
        "review_status": "PENDING_OWNER_REVIEW",
        "decision_rule": "Authority > operational asset readiness > frame registration > full-domain proof > independent reproduction > candidate arithmetic > agent opinion",
        "checks": checks, "checks_passed": 28, "checks_total": 28,
        "counters": {
            "active_object_count": 150, "A_object_count": 10, "A_frame_registration_count": 10,
            "asset_level_operational_count": 1, "parent_contract_system_motion_certificates_bound": 0,
            "preexisting_append_only_system_motion_certificates_observed": 1,
            "design_screening_candidate_bounds_emitted": 9, "batch_new_system_motion_certificates_bound": 0,
            "effective_observed_append_only_system_motion_certificates": 1,
            "system_motion_certificates_required": 150,
            "remaining_objects_without_observed_append_only_system_certificate": 149,
            "authoritative_scene_values_bound": 0, "authoritative_scene_values_required": 30,
            "stage_instances_bound": 0, "stage_instances_required": 3,
            "clearance_policy_rows_bound": 0, "clearance_policy_rows_required": 11166,
            "pair_queries_executed": 0, "pair_queries_required": 11166, "edges_certified": 0,
            "path_search_executed": False, "next_stage_authorized": False, "release_credit": False,
        },
        "source_pins": context["sources"], "local_artifact_pins": local_pins,
        "manifest_policy": {
            "exact_unique_no_extra": True, "included_files": INCLUDED_FILES,
            "self_excluded_files": [MANIFEST_NAME, RELEASE_RECEIPT_NAME],
            "excluded_release_receipt_role": "NONAUTHORITATIVE_RUNTIME_VALIDATION_RECEIPT_BINDING_THE_SEALED_MANIFEST__CIRCULAR_HASH_AVOIDANCE_ONLY",
            "cache_directories_forbidden": True,
        },
        "candidate_bound_gate_pass": True, "system_motion_certificate_gate_pass": False,
        "system_collision_gate_pass": False, "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False, "path_search_authorized": False,
        "next_stage_authorized": False, "release_credit": False, "retained_holds": holds,
        "maximum_claim": "9_OF_9_NONBASE_B601_A_OBJECTS_HAVE_HASH_BOUND_FULL_Q_DOMAIN_DESIGN_SCREENING_RIGID_KINEMATIC_CANDIDATE_BOUNDS__0_NEW_SYSTEM_CERTIFICATES",
        "verdict": "M01_RIGID_KINEMATIC_CANDIDATE_BATCH_28_OF_28_PASS__9_CANDIDATE_BOUNDS__0_NEW_SYSTEM_CERTIFICATES__SCENE_PAIR_EDGE_PATH_RELEASE_HOLD",
    }


def validate_gate(actual: Any, expected: dict[str, Any]) -> None:
    exact_keys(actual, GATE_TOP_KEYS, "GATE_TOP_LEVEL_KEYS_DRIFT")
    require(actual == expected, "GATE_PAYLOAD_DRIFT")


def parse_manifest(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    headers, rows = read_csv(path)
    return headers, rows


def validate_manifest_rows(headers: list[str], rows: list[dict[str, str]]) -> None:
    require(headers == ["path", "bytes", "sha256", "role"], "MANIFEST_HEADER_DRIFT")
    paths = [row["path"] for row in rows]
    require(paths == sorted(INCLUDED_FILES), "MANIFEST_PATH_SET_OR_ORDER_DRIFT")
    require(len(paths) == len(set(paths)), "MANIFEST_DUPLICATE_PATH")
    for row in rows:
        path = PACKAGE_DIR / row["path"]
        require(path.is_file(), f"MANIFEST_FILE_MISSING:{row['path']}")
        require(row["role"] == "RELEASE_PAYLOAD", f"MANIFEST_ROLE_DRIFT:{row['path']}")
        require(row["bytes"].isdigit() and int(row["bytes"]) == path.stat().st_size, f"MANIFEST_BYTES_DRIFT:{row['path']}")
        require(row["sha256"] == file_sha(path), f"MANIFEST_HASH_DRIFT:{row['path']}")


def validate_package_file_set(*, receipt_may_be_absent: bool) -> None:
    actual_names: set[str] = set()
    for entry in PACKAGE_DIR.iterdir():
        require(entry.is_file(), f"PACKAGE_DIRECTORY_OR_NONFILE_FORBIDDEN:{entry.name}")
        actual_names.add(entry.name)
    expected = set(INCLUDED_FILES) | {MANIFEST_NAME, RELEASE_RECEIPT_NAME}
    if receipt_may_be_absent and RELEASE_RECEIPT_NAME not in actual_names:
        expected.remove(RELEASE_RECEIPT_NAME)
    require(actual_names == expected, f"PACKAGE_EXACT_FILE_SET_DRIFT:actual={sorted(actual_names)}:expected={sorted(expected)}")


def release_negative_controls(gate: dict[str, Any], headers: list[str], rows: list[dict[str, str]], expected_gate_value: dict[str, Any]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    changed = copy.deepcopy(gate)
    changed["authority"] = "SYSTEM_RELEASE"
    results.append(expect_rejection("gate_authority_escalation", "GATE_PAYLOAD_DRIFT", lambda: validate_gate(changed, expected_gate_value)))
    changed = copy.deepcopy(gate)
    changed["counters"]["batch_new_system_motion_certificates_bound"] = 1
    results.append(expect_rejection("gate_system_count_escalation", "GATE_PAYLOAD_DRIFT", lambda: validate_gate(changed, expected_gate_value)))
    changed = copy.deepcopy(gate)
    changed["path_search_authorized"] = True
    results.append(expect_rejection("gate_path_authority_escalation", "GATE_PAYLOAD_DRIFT", lambda: validate_gate(changed, expected_gate_value)))
    changed = copy.deepcopy(gate)
    changed["maximum_claim"] = "SYSTEM_COMPLETE"
    results.append(expect_rejection("gate_maximum_claim_escalation", "GATE_PAYLOAD_DRIFT", lambda: validate_gate(changed, expected_gate_value)))
    duplicate = copy.deepcopy(rows)
    duplicate.append(copy.deepcopy(duplicate[0]))
    results.append(expect_rejection("manifest_duplicate", "MANIFEST_PATH_SET_OR_ORDER_DRIFT", lambda: validate_manifest_rows(headers, duplicate)))
    missing = copy.deepcopy(rows[:-1])
    results.append(expect_rejection("manifest_missing", "MANIFEST_PATH_SET_OR_ORDER_DRIFT", lambda: validate_manifest_rows(headers, missing)))
    extra = copy.deepcopy(rows)
    extra.append({"path": "EXTRA.txt", "bytes": "0", "sha256": "0" * 64, "role": "RELEASE_PAYLOAD"})
    results.append(expect_rejection("manifest_extra", "MANIFEST_PATH_SET_OR_ORDER_DRIFT", lambda: validate_manifest_rows(headers, extra)))
    bad_hash = copy.deepcopy(rows)
    bad_hash[0]["sha256"] = "0" * 64
    results.append(expect_rejection("manifest_hash_mutation", f"MANIFEST_HASH_DRIFT:{bad_hash[0]['path']}", lambda: validate_manifest_rows(headers, bad_hash)))
    results.append(expect_rejection("release_json_duplicate", "JSON_DUPLICATE_KEY:x", lambda: strict_json_text('{"x":1,"x":2}')))
    results.append(expect_rejection("release_json_negative_infinity", "JSON_NONFINITE_CONSTANT:-Infinity", lambda: strict_json_text('{"x":-Infinity}')))
    return results


def make_release_receipt(context: dict[str, Any], recompute: dict[str, Any], release_negatives: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema": "STANDALONE_RELEASE_VALIDATION_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_STANDALONE_RELEASE_VALIDATION_NO_WALLCLOCK",
        "authority": "NONAUTHORITATIVE_VALIDATION_RECEIPT__BINDS_SEALED_PACKAGE_WITHOUT_CHANGING_SCIENTIFIC_GATE",
        "validator_sha256": file_sha(Path(__file__).resolve()),
        "builder_imported_or_executed": False,
        "source_binding_sha256": canon_sha(context["sources"]),
        "gate_sha256": file_sha(PACKAGE_DIR / GATE_NAME),
        "manifest_sha256": file_sha(PACKAGE_DIR / MANIFEST_NAME),
        "independent_recompute_sha256": file_sha(PACKAGE_DIR / RECOMPUTE_NAME),
        "candidate_document_sha256": file_sha(PACKAGE_DIR / CANDIDATE_NAME),
        "eligibility_matrix_sha256": file_sha(PACKAGE_DIR / ELIGIBILITY_NAME),
        "system_batch_sha256": file_sha(PACKAGE_DIR / SYSTEM_BATCH_NAME),
        "candidate_comparisons_passed": recompute["candidate_comparisons_passed"],
        "candidate_comparisons_total": recompute["candidate_comparisons_total"],
        "core_negative_controls_rejected": recompute["negative_controls_rejected"],
        "core_negative_controls_total": recompute["negative_controls_total"],
        "release_negative_controls": release_negatives,
        "release_negative_controls_rejected": len(release_negatives),
        "release_negative_controls_total": len(release_negatives),
        "batch_new_system_certificates": 0,
        "parent_contract_system_certificate_snapshot": 0,
        "preexisting_append_only_base_certificate_observed": 1,
        "scene_values_bound": 0,
        "stage_instances_bound": 0,
        "pair_queries_executed": 0,
        "edges_certified": 0,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "all_release_checks_pass": True,
        "verdict": "STANDALONE_RELEASE_VALIDATION_PASS__9_CANDIDATES_RECOMPUTED__0_NEW_SYSTEM_CERTIFICATES__NO_AUTHORITY_ESCAPES",
    }


def ensure_no_builder_import() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=str(Path(__file__)))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            require(
                all(alias.name != "build_m01_rigid_kinematic_motion_cert_batch" for alias in node.names),
                "VALIDATOR_IMPORTS_BUILDER",
            )
        if isinstance(node, ast.ImportFrom):
            require(node.module != "build_m01_rigid_kinematic_motion_cert_batch", "VALIDATOR_IMPORTS_BUILDER")


def run_preseal(*, emit: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    ensure_no_builder_import()
    context = load_authoritative_context()
    candidate, system, headers, eligibility = load_core(context)
    recompute = expected_recompute(context, candidate, system, headers, eligibility)
    if emit:
        emit_json(PACKAGE_DIR / RECOMPUTE_NAME, recompute)
    return context, recompute


def run_release(*, write_receipt: bool) -> dict[str, Any]:
    context, expected_recompute_value = run_preseal(emit=False)
    actual_recompute = strict_json_file(PACKAGE_DIR / RECOMPUTE_NAME)
    validate_recompute_receipt(actual_recompute, expected_recompute_value)
    expected_gate_value = expected_gate(context, actual_recompute)
    actual_gate = strict_json_file(PACKAGE_DIR / GATE_NAME)
    validate_gate(actual_gate, expected_gate_value)
    manifest_headers, manifest_rows = parse_manifest(PACKAGE_DIR / MANIFEST_NAME)
    validate_manifest_rows(manifest_headers, manifest_rows)
    validate_package_file_set(receipt_may_be_absent=write_receipt)
    release_negatives = release_negative_controls(actual_gate, manifest_headers, manifest_rows, expected_gate_value)
    receipt = make_release_receipt(context, actual_recompute, release_negatives)
    if write_receipt:
        emit_json(PACKAGE_DIR / RELEASE_RECEIPT_NAME, receipt)
    elif (PACKAGE_DIR / RELEASE_RECEIPT_NAME).is_file():
        require(strict_json_file(PACKAGE_DIR / RELEASE_RECEIPT_NAME) == receipt, "RELEASE_RECEIPT_DRIFT")
    validate_package_file_set(receipt_may_be_absent=False)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit-preseal-recompute", action="store_true")
    mode.add_argument("--release", action="store_true")
    parser.add_argument("--write-release-receipt", action="store_true")
    args = parser.parse_args()
    try:
        if args.emit_preseal_recompute:
            require(not args.write_release_receipt, "ARGUMENT_MODE_CONFLICT")
            _, recompute = run_preseal(emit=True)
            payload = {
                "mode": "PRESEAL_RECOMPUTE",
                "verdict": recompute["verdict"],
                "candidate_comparisons": f"{recompute['candidate_comparisons_passed']}/{recompute['candidate_comparisons_total']}",
                "negative_controls": f"{recompute['negative_controls_rejected']}/{recompute['negative_controls_total']}",
                "receipt_sha256": file_sha(PACKAGE_DIR / RECOMPUTE_NAME),
            }
        else:
            receipt = run_release(write_receipt=args.write_release_receipt)
            payload = {
                "mode": "SEALED_RELEASE",
                "verdict": receipt["verdict"],
                "candidate_comparisons": f"{receipt['candidate_comparisons_passed']}/{receipt['candidate_comparisons_total']}",
                "core_negative_controls": f"{receipt['core_negative_controls_rejected']}/{receipt['core_negative_controls_total']}",
                "release_negative_controls": f"{receipt['release_negative_controls_rejected']}/{receipt['release_negative_controls_total']}",
                "batch_new_system_certificates": receipt["batch_new_system_certificates"],
                "release_receipt_sha256": canon_sha(receipt),
            }
        print(json.dumps(payload, indent=2))
        return 0
    except (ValidationError, RuntimeError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        print(json.dumps({"verdict": "FAIL_CLOSED", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
