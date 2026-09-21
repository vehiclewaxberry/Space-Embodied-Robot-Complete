#!/usr/bin/env python3
"""Build the append-only M01 rigid-kinematic motion-candidate batch.

This builder deliberately emits zero new system motion certificates.  It derives
full-q-domain conservative candidate coefficients only for the nine B601 design
screening assets that have an accepted-URDF frame registration but no operational
collision-asset promotion.  A::base_link is recorded as a pre-existing certificate
and is never re-issued by this package.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parent


def find_project_root() -> Path:
    for parent in (PACKAGE_DIR, *PACKAGE_DIR.parents):
        if (parent / "PROJECT_MAP.md").is_file() and (parent / "20_engineering").is_dir():
            return parent
    raise RuntimeError("PROJECT_ROOT_NOT_FOUND")


PROJECT_ROOT = find_project_root()

SOURCE_PINS: dict[str, tuple[str, int, str]] = {
    "system_registry": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json",
        247325,
        "AC975D11CC4715277E34FCFF7ABF049BC57334FD8F03AAB223BBED0877B1694F",
    ),
    "motion_contract": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/OBJECT_MOTION_BOUND_CONTRACT_V1.json",
        15414,
        "CA1A741576A90301D77FD684DFA07882FB1AB88A00E927C1381D8709C715A5CD",
    ),
    "collision_registration": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/COLLISION_FRAME_REGISTRATION_V1.json",
        28801,
        "3C60DBFFB2C62AB0C71482D78C8CEC63EC3AF042ABF550A324627771C9D3EA4D",
    ),
    "asset_readiness": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_OPERATIONAL_ASSET_READINESS_V1.csv",
        113527,
        "974D50C1786003ED70F8494F67DFEF20ABF64F1DE103A224E9ACA34DE83A5D09",
    ),
    "accepted_urdf": (
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        11321,
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
    ),
    "scene_schema": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json",
        6733,
        "67252BCE1259414876103EE3B6AF25ACC4A33E5A36B73AF974BD4004C285141C",
    ),
    "execution_mount": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/EXECUTION_MOUNT_BINDING_V1.json",
        3477,
        "B7758F751E273CE21CCD5132C23F2514524DE7613E31B33646E027603B0F6653",
    ),
    "preexisting_base_certificate": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1/A_BASE_LINK_GLOBAL_MOTION_CERTIFICATE_V1.json",
        6097,
        "332E2C67359BE2507058748061227F73FC5938048BAD2D319F19C27815031010",
    ),
    "wp11_cad_urdf_calibration": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml",
        36293,
        "7463C1309C3530A42BB32CB4A661FFA56575691DFB7A4BE801AAE9094BEB51E1",
    ),
    "m5_mesh_frame_decision": (
        "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json",
        32652,
        "2A99484C6CE55B402CB06380F5DCB71D5A8B4BA622A371EEF72F4EC69EF124FF",
    ),
    "urdf_eol_equivalence": (
        "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/11_validation/URDF_LINE_ENDING_HASH_EQUIVALENCE_RECEIPT.json",
        950,
        "DF8D4624B2E33E7DDC93613DE86C663AC230C7F76A06D875ED08037FFE37E7AF",
    ),
    "physical_dynamics_bridge": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml",
        12145,
        "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C",
    ),
}

Q_ORDER = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
Q_LOWER = [-2.8, -3.14, -3.14, -1.87, -1.57, -3.14]
Q_UPPER = [2.8, 0.0, 0.0, 1.57, 1.57, 3.14]

ELIGIBILITY_NAME = "M01_RIGID_KINEMATIC_MOTION_ELIGIBILITY_MATRIX_V1.csv"
CANDIDATE_NAME = "A_B601_RIGID_KINEMATIC_CANDIDATE_BOUNDS_V1.json"
SYSTEM_BATCH_NAME = "M01_RIGID_KINEMATIC_SYSTEM_CERTIFICATE_BATCH_V1.json"
RECOMPUTE_NAME = "INDEPENDENT_RIGID_KINEMATIC_RECOMPUTE_V1.json"
GATE_NAME = "M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_GATE_V1.json"
MANIFEST_NAME = "M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_PACKAGE_SHA256_V1.csv"
RELEASE_RECEIPT_NAME = "STANDALONE_RELEASE_VALIDATION_RECEIPT_V1.json"

GENERATED_NAMES = [
    ELIGIBILITY_NAME,
    CANDIDATE_NAME,
    SYSTEM_BATCH_NAME,
    RECOMPUTE_NAME,
    GATE_NAME,
    MANIFEST_NAME,
    RELEASE_RECEIPT_NAME,
]

MANIFEST_INCLUDED_NAMES = [
    "README.md",
    "build_m01_rigid_kinematic_motion_cert_batch.py",
    "validate_m01_rigid_kinematic_motion_cert_batch.py",
    "test_m01_rigid_kinematic_motion_cert_batch.py",
    ELIGIBILITY_NAME,
    CANDIDATE_NAME,
    SYSTEM_BATCH_NAME,
    RECOMPUTE_NAME,
    GATE_NAME,
]


def reject_constant(value: str) -> None:
    raise ValueError(f"NONFINITE_JSON_CONSTANT:{value}")


def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicate,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def source_pin_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for key, (rel, expected_bytes, expected_sha) in SOURCE_PINS.items():
        path = PROJECT_ROOT / rel
        if not path.is_file():
            raise RuntimeError(f"SOURCE_MISSING:{key}:{rel}")
        actual_bytes = path.stat().st_size
        actual_sha = sha256_file(path)
        if actual_bytes != expected_bytes or actual_sha != expected_sha:
            raise RuntimeError(
                f"SOURCE_PIN_DRIFT:{key}:bytes={actual_bytes}/{expected_bytes}:sha={actual_sha}/{expected_sha}"
            )
        records[key] = {"path": rel, "bytes": actual_bytes, "sha256": actual_sha}
    return records


def parse_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_vec(text: str | None, *, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if text is None:
        return default
    parts = text.split()
    if len(parts) != 3:
        raise RuntimeError(f"URDF_VECTOR_ARITY:{text}")
    values = tuple(float(x) for x in parts)
    if not all(math.isfinite(x) for x in values):
        raise RuntimeError(f"URDF_VECTOR_NONFINITE:{text}")
    return values  # type: ignore[return-value]


def parse_urdf(path: Path) -> dict[str, Any]:
    root = ET.fromstring(path.read_bytes())
    if root.tag != "robot" or root.attrib.get("name") != "arm_b601_v1":
        raise RuntimeError("URDF_ROBOT_IDENTITY_MISMATCH")
    links = [node.attrib["name"] for node in root.findall("link")]
    joints: list[dict[str, Any]] = []
    children: set[str] = set()
    for node in root.findall("joint"):
        origin = node.find("origin")
        axis = node.find("axis")
        limit = node.find("limit")
        record = {
            "name": node.attrib["name"],
            "type": node.attrib["type"],
            "parent": node.find("parent").attrib["link"],  # type: ignore[union-attr]
            "child": node.find("child").attrib["link"],  # type: ignore[union-attr]
            "origin_xyz_m": parse_vec(origin.attrib.get("xyz") if origin is not None else None, default=(0.0, 0.0, 0.0)),
            "origin_rpy_rad": parse_vec(origin.attrib.get("rpy") if origin is not None else None, default=(0.0, 0.0, 0.0)),
            "axis_joint_frame": parse_vec(axis.attrib.get("xyz") if axis is not None else None, default=(1.0, 0.0, 0.0)),
            "lower": float(limit.attrib["lower"]) if limit is not None and "lower" in limit.attrib else None,
            "upper": float(limit.attrib["upper"]) if limit is not None and "upper" in limit.attrib else None,
        }
        if record["child"] in children:
            raise RuntimeError(f"URDF_MULTIPLE_PARENT:{record['child']}")
        children.add(record["child"])
        joints.append(record)
    roots = sorted(set(links) - children)
    if roots != ["base_link"]:
        raise RuntimeError(f"URDF_ROOT_MISMATCH:{roots}")
    q_joints = [joint for joint in joints if joint["name"] in Q_ORDER]
    q_joints.sort(key=lambda joint: Q_ORDER.index(joint["name"]))
    if [joint["name"] for joint in q_joints] != Q_ORDER:
        raise RuntimeError("URDF_Q_ORDER_MISMATCH")
    if [joint["lower"] for joint in q_joints] != Q_LOWER or [joint["upper"] for joint in q_joints] != Q_UPPER:
        raise RuntimeError("URDF_Q_LIMIT_MISMATCH")
    for joint in q_joints:
        if joint["type"] != "revolute":
            raise RuntimeError(f"URDF_Q_NOT_REVOLUTE:{joint['name']}")
        axis_norm = math.sqrt(sum(x * x for x in joint["axis_joint_frame"]))
        if abs(axis_norm - 1.0) > 1e-12:
            raise RuntimeError(f"URDF_AXIS_NOT_UNIT:{joint['name']}:{axis_norm}")
    return {"robot_name": root.attrib["name"], "links": links, "joints": joints, "root_link": roots[0]}


def joint_chain_to_frame(urdf: dict[str, Any], frame: str) -> list[dict[str, Any]]:
    by_child = {joint["child"]: joint for joint in urdf["joints"]}
    chain: list[dict[str, Any]] = []
    cursor = frame
    seen: set[str] = set()
    while cursor != urdf["root_link"]:
        if cursor in seen or cursor not in by_child:
            raise RuntimeError(f"URDF_CHAIN_UNRESOLVED:{frame}:{cursor}")
        seen.add(cursor)
        joint = by_child[cursor]
        chain.append(joint)
        cursor = joint["parent"]
    chain.reverse()
    return chain


def parse_binary_ply_vertices(path: Path) -> tuple[int, tuple[float, float, float], tuple[float, float, float], float]:
    with path.open("rb") as handle:
        header: list[bytes] = []
        while True:
            line = handle.readline()
            if not line:
                raise RuntimeError(f"PLY_HEADER_EOF:{path}")
            header.append(line.rstrip(b"\r\n"))
            if header[-1] == b"end_header":
                break
        if header[0] != b"ply" or b"format binary_little_endian 1.0" not in header:
            raise RuntimeError(f"PLY_FORMAT_UNSUPPORTED:{path}")
        vertex_line = next((line for line in header if line.startswith(b"element vertex ")), None)
        if vertex_line is None:
            raise RuntimeError(f"PLY_VERTEX_COUNT_MISSING:{path}")
        vertex_count = int(vertex_line.split()[2])
        props = [line for line in header if line.startswith(b"property ")]
        if props[:3] != [b"property float x", b"property float y", b"property float z"]:
            raise RuntimeError(f"PLY_VERTEX_LAYOUT_UNSUPPORTED:{path}")
        raw = handle.read(vertex_count * 12)
        if len(raw) != vertex_count * 12:
            raise RuntimeError(f"PLY_VERTEX_DATA_TRUNCATED:{path}")
    mins = [math.inf, math.inf, math.inf]
    maxs = [-math.inf, -math.inf, -math.inf]
    radius_sq = 0.0
    for x, y, z in struct.iter_unpack("<fff", raw):
        if not all(math.isfinite(v) for v in (x, y, z)):
            raise RuntimeError(f"PLY_NONFINITE_VERTEX:{path}")
        values = (x, y, z)
        for idx, value in enumerate(values):
            mins[idx] = min(mins[idx], value)
            maxs[idx] = max(maxs[idx], value)
        radius_sq = max(radius_sq, x * x + y * y + z * z)
    return vertex_count, tuple(mins), tuple(maxs), math.sqrt(radius_sq)


def ceiling_mm(value_m: float) -> float:
    if isinstance(value_m, bool) or not isinstance(value_m, (int, float)) or not math.isfinite(value_m) or value_m < 0:
        raise RuntimeError(f"INVALID_NONNEGATIVE_LENGTH:{value_m!r}")
    return math.ceil(value_m * 1000.0 * 1_000_000_000.0) / 1_000_000_000.0


def norm3(vector: tuple[float, float, float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


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


def assert_A_registration_identity_se3(
    registrations: dict[str, dict[str, Any]], expected_A_ids: set[str]
) -> dict[str, Any]:
    if len(registrations) != 10 or set(registrations) != expected_A_ids:
        raise RuntimeError("A_REGISTRATION_SET_MISMATCH")
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    for object_id in sorted(expected_A_ids):
        row = registrations[object_id]
        transform = row.get("T_registration_frame_asset_storage")
        if not isinstance(transform, dict) or set(transform) != {"rotation", "translation", "translation_unit"}:
            raise RuntimeError(f"A_REGISTRATION_SE3_SCHEMA_INVALID:{object_id}")
        if transform["rotation"] != "IDENTITY":
            raise RuntimeError(f"A_REGISTRATION_ROTATION_NOT_IDENTITY:{object_id}")
        rotation = identity
        if not all(math.isfinite(value) for matrix_row in rotation for value in matrix_row):
            raise RuntimeError(f"A_REGISTRATION_ROTATION_NONFINITE:{object_id}")
        orthogonality_error = max(
            abs(sum(rotation[k][row] * rotation[k][col] for k in range(3)) - (1.0 if row == col else 0.0))
            for row in range(3)
            for col in range(3)
        )
        determinant = (
            rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
            - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
            + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
        )
        if orthogonality_error > 1e-15 or abs(determinant - 1.0) > 1e-15:
            raise RuntimeError(f"A_REGISTRATION_ROTATION_NOT_SO3:{object_id}")
        translation = transform["translation"]
        if (
            type(translation) is not list
            or len(translation) != 3
            or any(type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) for value in translation)
        ):
            raise RuntimeError(f"A_REGISTRATION_TRANSLATION_NOT_FINITE_VECTOR3:{object_id}")
        if transform["translation_unit"] != "m":
            raise RuntimeError(f"A_REGISTRATION_TRANSLATION_UNIT_DRIFT:{object_id}")
        if any(float(value) != 0.0 for value in translation):
            raise RuntimeError(f"A_REGISTRATION_TRANSFORM_NOT_IDENTITY:{object_id}")
        if row.get("frame_relationship_bound") is not True:
            raise RuntimeError(f"A_REGISTRATION_FRAME_RELATIONSHIP_UNBOUND:{object_id}")
        if row.get("accepted_urdf_registration_frame") != row.get("asset_storage_frame"):
            raise RuntimeError(f"A_REGISTRATION_LINK_FRAME_IDENTITY_MISMATCH:{object_id}")
    return {
        "registration_count": 10,
        "finite_legal_se3_count": 10,
        "identity_link_frame_registration_count": 10,
        "rotation_determinant": 1.0,
        "maximum_orthogonality_error": 0.0,
    }


def assert_gripper_prismatic_contract(
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
        if joint is None or joint["type"] != "prismatic":
            raise RuntimeError(f"GRIPPER_PRISMATIC_JOINT_INVALID:{object_id}")
        if joint["parent"] != "gripper_link" or joint["child"] != child:
            raise RuntimeError(f"GRIPPER_PRISMATIC_PARENT_CHILD_DRIFT:{object_id}")
        axis = joint["axis_joint_frame"]
        if any(not math.isfinite(value) for value in axis):
            raise RuntimeError(f"GRIPPER_PRISMATIC_AXIS_NONFINITE:{object_id}")
        axis_norm = norm3(axis)
        if abs(axis_norm - 1.0) > 1e-12:
            raise RuntimeError(f"GRIPPER_PRISMATIC_AXIS_NOT_UNIT:{object_id}:{axis_norm}")
        lower, upper = joint["lower"], joint["upper"]
        if (
            type(lower) not in (int, float)
            or type(upper) not in (int, float)
            or isinstance(lower, bool)
            or isinstance(upper, bool)
            or not math.isfinite(lower)
            or not math.isfinite(upper)
            or lower > upper
        ):
            raise RuntimeError(f"GRIPPER_PRISMATIC_LIMIT_INVALID:{object_id}")
        if lower != 0.0 or upper != 0.0715:
            raise RuntimeError(f"GRIPPER_PRISMATIC_LIMIT_DRIFT:{object_id}:{lower}:{upper}")
        axis_parent = matrix_vector(rotation_matrix_from_rpy(joint["origin_rpy_rad"]), axis)
        if abs(norm3(axis_parent) - 1.0) > 1e-12:
            raise RuntimeError(f"GRIPPER_PRISMATIC_PARENT_AXIS_NOT_UNIT:{object_id}")
        motion = registrations[object_id]["motion_registration"]
        registered_axis_raw = motion.get("axis_in_parent_frame_from_accepted_urdf")
        if (
            type(registered_axis_raw) is not list
            or len(registered_axis_raw) != 3
            or any(type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) for value in registered_axis_raw)
        ):
            raise RuntimeError(f"GRIPPER_REGISTERED_AXIS_NONFINITE:{object_id}")
        registered_axis = tuple(float(value) for value in registered_axis_raw)
        if abs(norm3(registered_axis) - 1.0) > 1e-12:
            raise RuntimeError(f"GRIPPER_REGISTERED_AXIS_NOT_UNIT:{object_id}")
        if max(abs(left - right) for left, right in zip(axis_parent, registered_axis)) > 1e-15:
            raise RuntimeError(f"GRIPPER_REGISTERED_AXIS_DIRECTION_DRIFT:{object_id}")
        domain = motion.get("allowed_domain_m")
        if domain != [lower, upper]:
            raise RuntimeError(f"GRIPPER_PRISMATIC_DOMAIN_LIMIT_DRIFT:{object_id}")
        if motion.get("state_variable") != state_variable:
            raise RuntimeError(f"GRIPPER_PRISMATIC_STATE_VARIABLE_DRIFT:{object_id}")
        stroke_m = upper - lower
        full_travel_envelope_m = max(abs(lower), abs(upper))
        if stroke_m != 0.0715 or full_travel_envelope_m != stroke_m:
            raise RuntimeError(f"GRIPPER_PRISMATIC_FULL_TRAVEL_ENVELOPE_DRIFT:{object_id}")
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


def motion_class(object_id: str, contract: dict[str, Any]) -> str:
    if object_id in set(contract["motion_classes"]["J3_HIDDEN_TRANSLATION"]["object_ids"]):
        return "J3_HIDDEN_TRANSLATION"
    if object_id in set(contract["motion_classes"]["J4_TRAVEL_TRANSLATION"]["object_motion_gain"]):
        return "J4_TRAVEL_TRANSLATION"
    if object_id in set(contract["motion_classes"]["C_SECTION_CAPSULE"]["object_ids"]):
        return "C_SECTION_CAPSULE"
    return "DIRECT_RIGID_FK_CANDIDATE"


def selected_asset(registry_object: dict[str, Any]) -> dict[str, Any]:
    geometry = registry_object["geometry"]
    asset = geometry.get("narrowphase_candidate") or geometry.get("candidate_source_surface")
    if not isinstance(asset, dict):
        raise RuntimeError(f"A_CANDIDATE_ASSET_MISSING:{registry_object['object_id']}")
    return asset


def derive_candidate(
    registry_object: dict[str, Any],
    registration: dict[str, Any],
    urdf: dict[str, Any],
    source_records: dict[str, dict[str, Any]],
    gripper_prismatic_evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    object_id = registry_object["object_id"]
    asset = selected_asset(registry_object)
    asset_path = PROJECT_ROOT / asset["path"]
    actual_hash = sha256_file(asset_path)
    if actual_hash != asset["sha256"] or actual_hash != registration["asset_sha256"]:
        raise RuntimeError(f"CANDIDATE_ASSET_HASH_BINDING_MISMATCH:{object_id}")
    if asset.get("units") != "m" or registration.get("asset_units") != "m":
        raise RuntimeError(f"CANDIDATE_ASSET_UNIT_MISMATCH:{object_id}")
    vertex_count, mins, maxs, raw_radius_m = parse_binary_ply_vertices(asset_path)
    registry_bounds = asset.get("bounds_link_m") or asset.get("bounds_gripper_link_m")
    if not isinstance(registry_bounds, list) or len(registry_bounds) != 2:
        raise RuntimeError(f"CANDIDATE_REGISTRY_BOUNDS_MISSING:{object_id}")
    for actual, declared in zip((*mins, *maxs), (*registry_bounds[0], *registry_bounds[1])):
        if actual < float(declared) - 2e-7 or actual > float(declared) + 2e-7:
            raise RuntimeError(f"CANDIDATE_REGISTRY_BOUNDS_MISMATCH:{object_id}")
    target_frame = registration["accepted_urdf_registration_frame"]
    if target_frame not in urdf["links"]:
        raise RuntimeError(f"CANDIDATE_REGISTRATION_FRAME_NOT_IN_URDF:{object_id}")
    chain = joint_chain_to_frame(urdf, target_frame)
    scene_offset_envelope_m = 0.0
    scene_domain: dict[str, Any] | None = None
    motion_registration = registration["motion_registration"]
    if motion_registration["type"] == "PRISMATIC_TRANSLATION_FROM_CLOSED_TRAVEL_ZERO":
        domain = motion_registration.get("allowed_domain_m")
        if object_id not in gripper_prismatic_evidence or domain != [0.0, 0.0715]:
            raise RuntimeError(f"CANDIDATE_PRISMATIC_DOMAIN_MISMATCH:{object_id}:{domain}")
        scene_offset_envelope_m = gripper_prismatic_evidence[object_id]["full_travel_envelope_m"]
        scene_domain = {
            "field": motion_registration["state_variable"],
            "domain_m": domain,
            "owner_value_consumed": False,
            "edge_rule": "STATE_MUST_BE_CONSTANT_ON_CERTIFIED_EDGE",
        }
    elif motion_registration["type"] != "RIGID_LINK_LOCAL":
        raise RuntimeError(f"CANDIDATE_MOTION_REGISTRATION_UNSUPPORTED:{object_id}")
    full_locus_radius_m = raw_radius_m + scene_offset_envelope_m
    coefficients: list[float] = []
    chain_names = [joint["name"] for joint in chain]
    for q_name in Q_ORDER:
        if q_name not in chain_names:
            coefficients.append(0.0)
            continue
        q_index = chain_names.index(q_name)
        downstream_translation_m = sum(norm3(joint["origin_xyz_m"]) for joint in chain[q_index + 1 :])
        coefficients.append(ceiling_mm(full_locus_radius_m + downstream_translation_m))
    raw_radius_mm = raw_radius_m * 1000.0
    geometry_reference_radius_mm = ceiling_mm(full_locus_radius_m)
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
        "local_design_screening_asset_sha256": actual_hash,
        "asset_storage_frame": registration["asset_storage_frame"],
        "accepted_urdf_registration_frame": target_frame,
        "q_domain_lower_rad": Q_LOWER,
        "q_domain_upper_rad": Q_UPPER,
        "scene_type_domain": scene_domain,
        "derivation_method": "TRIANGLE_INEQUALITY_FULL_CHAIN_ORIGIN_NORMS_PLUS_LINK_LOCAL_VERTEX_RADIUS_AND_DECLARED_SCENE_OFFSET_ENVELOPE",
    }
    evidence_payload = {
        "input_binding_sha256": canonical_sha(input_binding),
        "raw_asset_vertex_radius_mm": raw_radius_mm,
        "scene_offset_envelope_mm": scene_offset_envelope_m * 1000.0,
        "geometry_reference_radius_candidate_mm": geometry_reference_radius_mm,
        "global_L_candidate_mm_per_rad": coefficients,
    }
    blockers = [
        "OPERATIONAL_NARROWPHASE_PROMOTION_ABSENT",
        "RUNTIME_OBJECT_POSE_NOT_SYSTEM_BOUND",
        "DESIGN_SCREENING_SURFACE_NOT_CONSUMABLE_AS_OPERATIONAL_COLLISION_SET",
    ]
    if scene_domain is not None:
        blockers.append("OWNER_SCENE_STATE_VALUE_UNBOUND")
    candidate = {
        "object_id": object_id,
        "motion_class": "DIRECT_RIGID_FK_CANDIDATE",
        "authority": "DESIGN_SCREENING_KINEMATIC_CANDIDATE_ONLY__NOT_OBJECT_MOTION_BOUND_CERTIFICATE",
        "selected_design_screening_asset": {
            "path": asset["path"],
            "sha256": actual_hash,
            "bytes": asset_path.stat().st_size,
            "units": "m",
            "storage_frame": registration["asset_storage_frame"],
            "vertex_count": vertex_count,
            "vertex_bounds_m": [list(mins), list(maxs)],
            "use_limit": asset["use_limit"],
        },
        "registration": {
            "accepted_urdf_registration_frame": target_frame,
            "asset_storage_frame": registration["asset_storage_frame"],
            "frame_relationship_bound": registration["frame_relationship_bound"],
            "T_registration_frame_asset_storage": registration["T_registration_frame_asset_storage"],
            "operational_narrowphase_promoted": registration["operational_narrowphase_promoted"],
            "runtime_object_pose_bound": registration["runtime_object_pose_bound"],
            "motion_registration": motion_registration,
        },
        "urdf_chain": [
            {
                "name": joint["name"],
                "type": joint["type"],
                "parent": joint["parent"],
                "child": joint["child"],
                "origin_xyz_m": list(joint["origin_xyz_m"]),
                "origin_norm_m": norm3(joint["origin_xyz_m"]),
                "axis_joint_frame": list(joint["axis_joint_frame"]),
            }
            for joint in chain
        ],
        "q_order": Q_ORDER,
        "q_domain_lower_rad": Q_LOWER,
        "q_domain_upper_rad": Q_UPPER,
        "scene_type_domain": scene_domain,
        "owner_scene_values_consumed": 0,
        "raw_asset_vertex_radius_mm": raw_radius_mm,
        "scene_offset_envelope_mm": scene_offset_envelope_m * 1000.0,
        "geometry_reference_radius_candidate_mm": geometry_reference_radius_mm,
        "global_L_candidate_mm_per_rad": coefficients,
        "coefficient_ceiling_resolution_mm_per_rad": 1e-9,
        "analytic_proof": {
            "axis_distance_bound": "rho_i,k <= r_full_locus + sum(norm(origin_xyz_j)) for every downstream joint j after k through the registered asset frame",
            "rigid_set_correspondence": "The same local point supplies a Hausdorff correspondence under two rigid FK transforms",
            "path_integral": "d_H(G(q(t),s),G(q_m,s)) <= integral(sum_k rho_i,k*abs(dq_k)) <= 0.5*sum_k L_i,k*abs(q_b[k]-q_a[k])",
            "scene_rule": "The declared scene state is fixed on an edge; finger travel is enveloped across the complete type domain without selecting an Owner value",
            "proof_domain_complete_for_selected_design_screening_surface": True,
            "proof_domain_complete_for_operational_collision_object": False,
        },
        "candidate_input_binding": input_binding,
        "candidate_input_binding_sha256": canonical_sha(input_binding),
        "candidate_evidence_sha256": canonical_sha(evidence_payload),
        "operational_asset_ready": False,
        "system_certificate_eligible": False,
        "system_motion_authority_credit": 0,
        "pair_eligible": False,
        "pair_derating_authority_bound": False,
        "centerline_hausdorff_bound_mm": None,
        "radius_uncertainty_bound_mm": None,
        "model_uncertainty_bound_mm": None,
        "numeric_uncertainty_bound_mm": None,
        "blockers": blockers,
        "disposition": "CANDIDATE_BOUND_RETAINED_FOR_REPLAY_AFTER_OPERATIONAL_ASSET_PROMOTION__NO_SYSTEM_CREDIT",
    }
    return candidate


def make_eligibility_rows(
    registry: dict[str, Any],
    contract: dict[str, Any],
    registrations: dict[str, dict[str, Any]],
    readiness: dict[str, dict[str, str]],
    candidate_ids: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obj in sorted(registry["objects"], key=lambda value: value["object_id"]):
        object_id = obj["object_id"]
        registration = registrations.get(object_id)
        ready = readiness[object_id]
        operational = ready["operational_authority"] == "true"
        preexisting = object_id == "A::base_link"
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
        if preexisting:
            disposition = "PREEXISTING_APPEND_ONLY_BASE_CERTIFICATE_OBSERVED__NOT_REISSUED"
        elif object_id in candidate_ids:
            disposition = "DESIGN_SCREENING_CANDIDATE_BOUND_EMITTED__SYSTEM_CERTIFICATE_WITHHELD"
        else:
            disposition = "NO_CANDIDATE_BOUND_EMITTED__BLOCKED_OR_OUT_OF_SCOPE"
        rows.append(
            {
                "object_id": object_id,
                "category": obj["category"],
                "motion_class": motion_class(object_id, contract),
                "active_when": obj["active_when"],
                "frame_registration_present": str(registration is not None).lower(),
                "frame_relationship_bound": str(bool(registration and registration.get("frame_relationship_bound") is True)).lower(),
                "operational_asset_ready": str(operational).lower(),
                "registration_runtime_pose_bound": str(bool(registration and registration.get("runtime_object_pose_bound") is True)).lower(),
                "accepted_urdf_q_domain_available": str(object_id.startswith("A::")).lower(),
                "design_candidate_bound_emitted": str(object_id in candidate_ids).lower(),
                "preexisting_system_certificate_observed": str(preexisting).lower(),
                "batch_system_certificate_emitted": "false",
                "batch_system_motion_authority_credit": "0",
                "system_certificate_eligible_in_this_batch": "false",
                "readiness": ready["readiness"],
                "blockers": ";".join(blockers) if blockers else "NONE",
                "disposition": disposition,
            }
        )
    return rows


def write_eligibility_csv(rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0])
    with (PACKAGE_DIR / ELIGIBILITY_NAME).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def pin_local(names: list[str]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "bytes": (PACKAGE_DIR / name).stat().st_size,
            "sha256": sha256_file(PACKAGE_DIR / name),
        }
        for name in names
    }


def write_manifest() -> None:
    rows = []
    for name in sorted(MANIFEST_INCLUDED_NAMES):
        path = PACKAGE_DIR / name
        if not path.is_file():
            raise RuntimeError(f"MANIFEST_MEMBER_MISSING:{name}")
        rows.append(
            {
                "path": name,
                "bytes": str(path.stat().st_size),
                "sha256": sha256_file(path),
                "role": "RELEASE_PAYLOAD",
            }
        )
    with (PACKAGE_DIR / MANIFEST_NAME).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256", "role"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_validator(*args: str) -> None:
    command = [sys.executable, "-B", str(PACKAGE_DIR / "validate_m01_rigid_kinematic_motion_cert_batch.py"), *args]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(command, cwd=PROJECT_ROOT, env=env, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"STANDALONE_VALIDATOR_FAILED:{' '.join(args)}\n{result.stdout}\n{result.stderr}")
    if result.stdout:
        print(result.stdout.rstrip())


def build() -> dict[str, Any]:
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_NAMES:
        path = PACKAGE_DIR / name
        if path.is_file():
            path.unlink()

    source_records = source_pin_records()
    registry = strict_json(PROJECT_ROOT / SOURCE_PINS["system_registry"][0])
    contract = strict_json(PROJECT_ROOT / SOURCE_PINS["motion_contract"][0])
    registration_document = strict_json(PROJECT_ROOT / SOURCE_PINS["collision_registration"][0])
    scene = strict_json(PROJECT_ROOT / SOURCE_PINS["scene_schema"][0])
    mount = strict_json(PROJECT_ROOT / SOURCE_PINS["execution_mount"][0])
    base_cert = strict_json(PROJECT_ROOT / SOURCE_PINS["preexisting_base_certificate"][0])
    readiness_rows = parse_csv(PROJECT_ROOT / SOURCE_PINS["asset_readiness"][0])
    active_readiness = {row["id"]: row for row in readiness_rows if row["row_class"] == "ACTIVE_OBJECT"}
    registrations = {row["object_id"]: row for row in registration_document["registrations"]}
    urdf = parse_urdf(PROJECT_ROOT / SOURCE_PINS["accepted_urdf"][0])

    if len(registry["objects"]) != 150 or len(set(obj["object_id"] for obj in registry["objects"])) != 150:
        raise RuntimeError("REGISTRY_OBJECT_COUNT_OR_UNIQUENESS_MISMATCH")
    if set(active_readiness) != {obj["object_id"] for obj in registry["objects"]}:
        raise RuntimeError("READINESS_ACTIVE_OBJECT_SET_MISMATCH")
    A_object_ids = {obj["object_id"] for obj in registry["objects"] if obj["category"] == "A"}
    assert_A_registration_identity_se3(registrations, A_object_ids)
    gripper_prismatic_evidence = assert_gripper_prismatic_contract(urdf, registrations)
    if [row["id"] for row in readiness_rows if row["row_class"] == "ACTIVE_OBJECT" and row["operational_authority"] == "true"] != ["A::base_link"]:
        raise RuntimeError("OPERATIONAL_ASSET_SET_MISMATCH")
    if scene["current_instances"]["stage_instances_bound"] != 0 or scene["current_instances"]["stage_instances_required"] != 3:
        raise RuntimeError("SCENE_INSTANCE_COUNT_DRIFT")
    if mount["execution_mount_numeric_spelling_bound"] is not True:
        raise RuntimeError("EXECUTION_MOUNT_NOT_BOUND")
    if base_cert["object_id"] != "A::base_link" or base_cert["system_motion_authority_credit"] != 1:
        raise RuntimeError("PREEXISTING_BASE_CERTIFICATE_DRIFT")

    category_counts = {key: 0 for key in ["A", "C", "F", "R", "S"]}
    class_counts = {
        "DIRECT_RIGID_FK_CANDIDATE": 0,
        "J3_HIDDEN_TRANSLATION": 0,
        "J4_TRAVEL_TRANSLATION": 0,
        "C_SECTION_CAPSULE": 0,
    }
    for obj in registry["objects"]:
        category_counts[obj["category"]] += 1
        class_counts[motion_class(obj["object_id"], contract)] += 1
    if category_counts != {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6}:
        raise RuntimeError(f"REGISTRY_CATEGORY_COUNT_DRIFT:{category_counts}")
    if class_counts != {
        "DIRECT_RIGID_FK_CANDIDATE": 124,
        "J3_HIDDEN_TRANSLATION": 8,
        "J4_TRAVEL_TRANSLATION": 9,
        "C_SECTION_CAPSULE": 9,
    }:
        raise RuntimeError(f"MOTION_CLASS_COUNT_DRIFT:{class_counts}")

    candidate_objects = sorted(
        (
            obj
            for obj in registry["objects"]
            if obj["category"] == "A" and obj["object_id"] != "A::base_link"
        ),
        key=lambda obj: obj["object_id"],
    )
    candidates = [
        derive_candidate(
            obj,
            registrations[obj["object_id"]],
            urdf,
            source_records,
            gripper_prismatic_evidence,
        )
        for obj in candidate_objects
    ]
    if len(candidates) != 9 or any(candidate["system_motion_authority_credit"] != 0 for candidate in candidates):
        raise RuntimeError("CANDIDATE_COUNT_OR_AUTHORITY_MISMATCH")

    candidate_document = {
        "schema": "A_B601_RIGID_KINEMATIC_CANDIDATE_BOUNDS_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "authority": "NINE_DESIGN_SCREENING_RIGID_KINEMATIC_CANDIDATE_BOUNDS_ONLY__NOT_SYSTEM_CERTIFICATES",
        "source_pins": source_records,
        "units": {
            "urdf_translation": "m",
            "joint_coordinate": "rad",
            "candidate_coefficient": "mm/rad",
            "scene_prismatic_state": "m",
        },
        "q_contract": {
            "order": Q_ORDER,
            "lower_rad": Q_LOWER,
            "upper_rad": Q_UPPER,
            "interpolation": "q(t)=q_a+t*(q_b-q_a), t in [0,1]",
            "scene_state_constant_on_edge": True,
        },
        "method": {
            "asset_radius": "Maximum Euclidean norm of every binary-little-endian float32 PLY vertex in the registered design-screening storage frame; outward ceiling to 1e-9 mm",
            "full_locus_radius": "asset radius plus maximum declared prismatic scene offset where applicable; no Owner scene value selected",
            "joint_coefficient": "full-locus radius plus the sum of Euclidean norms of every downstream URDF joint-origin translation through the registered frame; outward ceiling to 1e-9 mm/rad",
            "conservatism": "Triangle inequality and revolute arc-length bound; constant spacecraft mount rotation/translation cannot increase Hausdorff distance",
            "prohibited_use": "Candidate vectors may not be loaded by the system edge oracle until an operational asset is promoted and a new system certificate is independently issued",
        },
        "candidates": candidates,
        "summary": {
            "active_registry_objects": 150,
            "A_objects": 10,
            "A_frame_registrations": 10,
            "asset_level_operational_objects": 1,
            "preexisting_base_system_certificate_observed": 1,
            "design_screening_candidate_bounds_emitted": 9,
            "candidate_bounds_with_full_accepted_q_domain": 9,
            "candidate_bounds_consuming_owner_scene_values": 0,
            "candidate_bounds_eligible_as_system_certificates": 0,
            "new_system_certificates_emitted": 0,
        },
        "maximum_claim": "NINE_B601_DESIGN_SCREENING_SURFACE_SETS_HAVE_CONSERVATIVE_FULL_ACCEPTED_Q_DOMAIN_RIGID_KINEMATIC_CANDIDATE_COEFFICIENTS__ZERO_OPERATIONAL_PROMOTION_AND_ZERO_SYSTEM_CREDIT",
        "verdict": "CANDIDATE_BOUNDS_DERIVED_FOR_9_OF_9_NONBASE_A_OBJECTS__ALL_WITHHELD_FROM_SYSTEM_CERTIFICATION",
    }
    write_json(PACKAGE_DIR / CANDIDATE_NAME, candidate_document)

    eligibility_rows = make_eligibility_rows(
        registry,
        contract,
        registrations,
        active_readiness,
        {candidate["object_id"] for candidate in candidates},
    )
    write_eligibility_csv(eligibility_rows)

    system_batch = {
        "schema": "M01_RIGID_KINEMATIC_SYSTEM_CERTIFICATE_BATCH_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "authority": "EMPTY_APPEND_ONLY_SYSTEM_CERTIFICATE_BATCH__DESIGN_CANDIDATES_EXPLICITLY_EXCLUDED",
        "source_pins": source_records,
        "parent_contract_snapshot": {
            "parent_system_certified_object_motion_bound_count": 0,
            "parent_system_certified_object_motion_bound_required": 150,
            "parent_gate_reissued_or_modified": False,
        },
        "preexisting_append_only_certificate_observation": {
            "object_id": "A::base_link",
            "certificate_sha256": source_records["preexisting_base_certificate"]["sha256"],
            "observed_system_motion_authority_credit": 1,
            "reissued_by_this_batch": False,
            "counted_as_new_by_this_batch": False,
        },
        "candidate_document_sha256": sha256_file(PACKAGE_DIR / CANDIDATE_NAME),
        "system_certificates": [],
        "batch_new_system_certificate_count": 0,
        "batch_system_motion_authority_credit": 0,
        "effective_observed_append_only_system_certificate_count_after_batch": 1,
        "system_motion_certificate_required": 150,
        "remaining_without_observed_append_only_system_certificate": 149,
        "scene_authoritative_values_bound": 0,
        "scene_authoritative_values_required": 30,
        "stage_instances_bound": 0,
        "stage_instances_required": 3,
        "clearance_policy_rows_bound": 0,
        "clearance_policy_rows_required": 11166,
        "pair_queries_executed": 0,
        "pair_queries_required": 11166,
        "edges_certified": 0,
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "retained_holds": [
            "NINE_NONBASE_A_ASSETS_HAVE_NO_OPERATIONAL_NARROWPHASE_PROMOTION",
            "NINE_NONBASE_A_RUNTIME_OBJECT_POSES_REMAIN_SYSTEM_UNBOUND",
            "ALL_30_OWNER_SCENE_VALUES_AND_ALL_3_SCENE_INSTANCES_REMAIN_UNBOUND",
            "11166_CLEARANCE_POLICY_ROWS_AND_11166_PAIR_QUERIES_REMAIN_ZERO",
            "ZERO_EDGE_CERTIFICATES_AND_NO_PATH_SEARCH_AUTHORITY",
        ],
        "maximum_claim": "ZERO_NEW_SYSTEM_MOTION_CERTIFICATES__NINE_DESIGN_CANDIDATES_ARE_NONCONSUMABLE",
        "verdict": "EMPTY_SYSTEM_CERTIFICATE_BATCH__0_NEW_CREDIT__PARENT_0_OF_150_SNAPSHOT_UNCHANGED__PREEXISTING_BASE_APPEND_ONLY_CREDIT_NOT_REISSUED",
    }
    write_json(PACKAGE_DIR / SYSTEM_BATCH_NAME, system_batch)

    run_validator("--emit-preseal-recompute")
    recompute = strict_json(PACKAGE_DIR / RECOMPUTE_NAME)
    if recompute.get("verdict") != "INDEPENDENT_RECOMPUTE_PASS__9_CANDIDATE_BOUNDS_EXACT__0_NEW_SYSTEM_CERTIFICATES":
        raise RuntimeError("INDEPENDENT_RECOMPUTE_NOT_PASS")

    core_pins = pin_local([ELIGIBILITY_NAME, CANDIDATE_NAME, SYSTEM_BATCH_NAME, RECOMPUTE_NAME])
    checks = {
        "G01_all_12_frozen_source_pins_match": True,
        "G02_registry_is_exactly_150_unique_active_objects": len(eligibility_rows) == 150,
        "G03_registry_category_counts_are_A10_C9_F4_R121_S6": category_counts == {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6},
        "G04_motion_class_partition_is_124_8_9_9": class_counts == {"DIRECT_RIGID_FK_CANDIDATE": 124, "J3_HIDDEN_TRANSLATION": 8, "J4_TRAVEL_TRANSLATION": 9, "C_SECTION_CAPSULE": 9},
        "G05_collision_registration_set_is_exactly_the_10_A_objects": len(registrations) == 10,
        "G06_only_A_base_link_has_operational_asset_authority": sum(row["operational_authority"] == "true" for row in active_readiness.values()) == 1,
        "G07_preexisting_base_certificate_is_observed_not_reissued": base_cert["system_motion_authority_credit"] == 1,
        "G08_accepted_urdf_is_10_links_9_joints_root_base_link": len(urdf["links"]) == 10 and len(urdf["joints"]) == 9 and urdf["root_link"] == "base_link",
        "G09_q_order_and_limits_are_exactly_accepted_urdf": [joint["name"] for joint in urdf["joints"] if joint["name"] in Q_ORDER] == Q_ORDER,
        "G10_execution_mount_spelling_is_bound_but_not_promoted_to_pair_authority": mount["execution_mount_numeric_spelling_bound"] is True and mount["pair_evaluation_authorized"] is False,
        "G11_nine_nonbase_A_design_assets_are_hash_frame_and_unit_bound": len(candidates) == 9,
        "G12_nine_candidate_bounds_cover_full_accepted_q_domain": all(candidate["q_domain_lower_rad"] == Q_LOWER and candidate["q_domain_upper_rad"] == Q_UPPER for candidate in candidates),
        "G13_candidate_coefficients_are_finite_nonnegative_and_bool_free": all(type(value) in (int, float) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 for candidate in candidates for value in candidate["global_L_candidate_mm_per_rad"]),
        "G14_owner_scene_values_consumed_is_zero": all(candidate["owner_scene_values_consumed"] == 0 for candidate in candidates),
        "G15_gripper_finger_offsets_use_schema_domain_not_owner_values": all(candidate["scene_offset_envelope_mm"] == 71.5 for candidate in candidates if candidate["object_id"] in {"A::gripper_left", "A::gripper_right"}),
        "G16_all_candidate_bounds_are_explicitly_nonoperational": all(candidate["operational_asset_ready"] is False for candidate in candidates),
        "G17_all_candidate_system_eligibility_values_are_false": all(candidate["system_certificate_eligible"] is False for candidate in candidates),
        "G18_all_candidate_system_motion_credits_are_exactly_zero": all(candidate["system_motion_authority_credit"] == 0 for candidate in candidates),
        "G19_pair_derate_unknowns_remain_null": all(candidate["radius_uncertainty_bound_mm"] is None and candidate["model_uncertainty_bound_mm"] is None and candidate["numeric_uncertainty_bound_mm"] is None for candidate in candidates),
        "G20_system_certificate_batch_is_exactly_empty": system_batch["system_certificates"] == [] and system_batch["batch_new_system_certificate_count"] == 0,
        "G21_parent_contract_snapshot_remains_zero_of_150": system_batch["parent_contract_snapshot"]["parent_system_certified_object_motion_bound_count"] == 0,
        "G22_effective_append_only_observation_remains_only_base_one_of_150": system_batch["effective_observed_append_only_system_certificate_count_after_batch"] == 1,
        "G23_scene_values_and_instances_remain_zero": system_batch["scene_authoritative_values_bound"] == 0 and system_batch["stage_instances_bound"] == 0,
        "G24_clearance_and_pair_counts_remain_zero_of_11166": system_batch["clearance_policy_rows_bound"] == 0 and system_batch["pair_queries_executed"] == 0,
        "G25_edge_path_next_and_release_authorities_remain_false": not any(system_batch[key] for key in ["edge_evaluation_authorized", "path_search_authorized", "path_search_executed", "next_stage_authorized", "release_credit"]),
        "G26_independent_recompute_exactly_reproduces_all_9_candidates": recompute["candidate_comparisons_passed"] == 9 and recompute["candidate_comparisons_total"] == 9,
        "G27_independent_preseal_negative_controls_all_rejected": recompute["negative_controls_rejected"] == recompute["negative_controls_total"] and recompute["negative_controls_total"] >= 24,
        "G28_append_only_scope_does_not_modify_or_reissue_parent_gate": True,
    }
    if not all(checks.values()):
        raise RuntimeError(f"GATE_CHECK_FAILED:{[key for key, value in checks.items() if not value]}")
    gate = {
        "schema": "M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "authority": "APPEND_ONLY_DESIGN_SCREENING_KINEMATIC_CANDIDATE_BOUNDS_ONLY__ZERO_NEW_SYSTEM_MOTION_CERTIFICATES__NO_PARENT_GATE_REISSUE",
        "review_status": "PENDING_OWNER_REVIEW",
        "decision_rule": "Authority > operational asset readiness > frame registration > full-domain proof > independent reproduction > candidate arithmetic > agent opinion",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "counters": {
            "active_object_count": 150,
            "A_object_count": 10,
            "A_frame_registration_count": 10,
            "asset_level_operational_count": 1,
            "parent_contract_system_motion_certificates_bound": 0,
            "preexisting_append_only_system_motion_certificates_observed": 1,
            "design_screening_candidate_bounds_emitted": 9,
            "batch_new_system_motion_certificates_bound": 0,
            "effective_observed_append_only_system_motion_certificates": 1,
            "system_motion_certificates_required": 150,
            "remaining_objects_without_observed_append_only_system_certificate": 149,
            "authoritative_scene_values_bound": 0,
            "authoritative_scene_values_required": 30,
            "stage_instances_bound": 0,
            "stage_instances_required": 3,
            "clearance_policy_rows_bound": 0,
            "clearance_policy_rows_required": 11166,
            "pair_queries_executed": 0,
            "pair_queries_required": 11166,
            "edges_certified": 0,
            "path_search_executed": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "source_pins": source_records,
        "local_artifact_pins": core_pins,
        "manifest_policy": {
            "exact_unique_no_extra": True,
            "included_files": sorted(MANIFEST_INCLUDED_NAMES),
            "self_excluded_files": [MANIFEST_NAME, RELEASE_RECEIPT_NAME],
            "excluded_release_receipt_role": "NONAUTHORITATIVE_RUNTIME_VALIDATION_RECEIPT_BINDING_THE_SEALED_MANIFEST__CIRCULAR_HASH_AVOIDANCE_ONLY",
            "cache_directories_forbidden": True,
        },
        "candidate_bound_gate_pass": True,
        "system_motion_certificate_gate_pass": False,
        "system_collision_gate_pass": False,
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "retained_holds": system_batch["retained_holds"],
        "maximum_claim": "9_OF_9_NONBASE_B601_A_OBJECTS_HAVE_HASH_BOUND_FULL_Q_DOMAIN_DESIGN_SCREENING_RIGID_KINEMATIC_CANDIDATE_BOUNDS__0_NEW_SYSTEM_CERTIFICATES",
        "verdict": f"M01_RIGID_KINEMATIC_CANDIDATE_BATCH_{sum(checks.values())}_OF_{len(checks)}_PASS__9_CANDIDATE_BOUNDS__0_NEW_SYSTEM_CERTIFICATES__SCENE_PAIR_EDGE_PATH_RELEASE_HOLD",
    }
    write_json(PACKAGE_DIR / GATE_NAME, gate)
    write_manifest()
    run_validator("--release", "--write-release-receipt")
    return gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-op", action="store_true", help="Parse arguments only; retained for harness compatibility")
    args = parser.parse_args()
    if args.no_op:
        return 0
    gate = build()
    print(
        json.dumps(
            {
                "verdict": gate["verdict"],
                "checks": f"{gate['checks_passed']}/{gate['checks_total']}",
                "candidate_bounds": gate["counters"]["design_screening_candidate_bounds_emitted"],
                "new_system_certificates": gate["counters"]["batch_new_system_motion_certificates_bound"],
                "gate_sha256": sha256_file(PACKAGE_DIR / GATE_NAME),
                "manifest_sha256": sha256_file(PACKAGE_DIR / MANIFEST_NAME),
                "release_receipt_sha256": sha256_file(PACKAGE_DIR / RELEASE_RECEIPT_NAME),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
