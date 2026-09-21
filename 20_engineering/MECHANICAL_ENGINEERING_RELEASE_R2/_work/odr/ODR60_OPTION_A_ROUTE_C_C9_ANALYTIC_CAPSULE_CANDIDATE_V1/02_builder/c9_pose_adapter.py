"""Side-effect-free URDF/FK pose adapter for the nine C9 capsule chains.

The adapter consumes only hash-pinned data, parses URDF XML directly, applies
the current 12-decimal mount exactly once, and never imports the V9F builder or
evaluator.  J4 uses the frozen seven-section deformation law.  J3 returns both
primary and alternate rigid-host representations and keeps production union
acceptance UNKNOWN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

import numpy as np


class PoseFailure(RuntimeError):
    """Fail-closed pose-adapter error."""


PACKAGE = Path(__file__).resolve().parents[1]
SOURCE_LOCK_PATH = PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"
CONTRACT_PATH = PACKAGE / "00_contract/C9_ANALYTIC_CAPSULE_CONTRACT_V1.json"
FRAME_LEDGER_PATH = PACKAGE / "00_contract/FRAME_UNIT_AND_MOTION_LEDGER_V1.json"
INDEX_PATH = PACKAGE / "05_results/C9_CAPSULE_INDEX_V1.json"
SELF_CHECK_PATH = PACKAGE / "05_results/POSE_ADAPTER_SELF_CHECK_V1.json"
JOINT_ORDER = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
J4_SELECTOR = "SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER"
J3_SELECTOR = "SEG-03_J3_CARRIER_HYBRID_WRAP"
TWELVE_DECIMAL = re.compile(r"^-?\d+\.\d{12}$")


def workspace_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "20_engineering").is_dir():
            return candidate
    raise PoseFailure("workspace root not found")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PoseFailure(message)


def strict_json(path: Path) -> dict[str, Any]:
    def reject_constant(token: str) -> None:
        raise PoseFailure(f"non-finite JSON token {token} in {path}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise PoseFailure(f"cannot load JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def canonical_q_payload_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def verify_pin(root: Path, record: dict[str, Any], label: str) -> Path:
    path = root / str(record.get("path"))
    require(path.is_file(), f"missing pinned source {label}: {path}")
    require(path.stat().st_size == record.get("bytes"), f"byte drift for {label}")
    require(sha256_path(path) == record.get("sha256"), f"hash drift for {label}")
    return path


def xyz(text: str | None, default: Iterable[float]) -> np.ndarray:
    values = list(default) if text is None else [float(token) for token in text.split()]
    array = np.asarray(values, dtype=np.float64)
    require(array.shape == (3,) and np.isfinite(array).all(), "invalid URDF three-vector")
    return array


def translation(x: float, y: float, z: float) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, 3] = [x, y, z]
    return matrix


def rotation_rpy(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rz @ ry @ rx
    return matrix


def rotation_axis(axis_value: np.ndarray, angle: float) -> np.ndarray:
    magnitude = float(np.linalg.norm(axis_value))
    require(magnitude > 1.0e-15 and math.isfinite(angle), "invalid joint axis or angle")
    x, y, z = axis_value / magnitude
    c, s, v = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = np.array([
        [x * x * v + c, x * y * v - z * s, x * z * v + y * s],
        [y * x * v + z * s, y * y * v + c, y * z * v - x * s],
        [z * x * v - y * s, z * y * v + x * s, z * z * v + c],
    ])
    return matrix


class SideEffectFreeArm:
    def __init__(self, urdf_path: Path) -> None:
        try:
            root = ET.parse(urdf_path).getroot()
        except (OSError, ET.ParseError) as exc:
            raise PoseFailure(f"cannot parse accepted URDF: {exc}") from exc
        require(root.tag == "robot", "URDF root is not robot")
        joints: list[dict[str, Any]] = []
        for node in root.findall("joint"):
            origin = node.find("origin")
            axis_node = node.find("axis")
            limit = node.find("limit")
            parent = node.find("parent")
            child = node.find("child")
            require(parent is not None and child is not None, "URDF joint has no parent or child")
            origin_xyz_m = xyz(origin.get("xyz") if origin is not None else None, (0.0, 0.0, 0.0))
            origin_rpy = xyz(origin.get("rpy") if origin is not None else None, (0.0, 0.0, 0.0))
            axis = xyz(axis_node.get("xyz") if axis_node is not None else None, (1.0, 0.0, 0.0))
            joint_type = str(node.get("type"))
            lower = float(limit.get("lower")) if limit is not None and limit.get("lower") is not None else None
            upper = float(limit.get("upper")) if limit is not None and limit.get("upper") is not None else None
            joints.append({
                "name": str(node.get("name")),
                "type": joint_type,
                "parent": str(parent.get("link")),
                "child": str(child.get("link")),
                "origin_xyz_mm": origin_xyz_m * 1000.0,
                "origin_rpy_rad": origin_rpy,
                "axis": axis,
                "lower": lower,
                "upper": upper,
            })
        arm_revolute = [joint for joint in joints if joint["type"] == "revolute"]
        require([joint["name"] for joint in arm_revolute] == JOINT_ORDER,
                "accepted URDF arm revolute order drift")
        self.joints = joints
        self.arm_revolute = arm_revolute
        self.limits = {joint["name"]: (joint["lower"], joint["upper"]) for joint in arm_revolute}

    @staticmethod
    def origin_matrix(joint: dict[str, Any]) -> np.ndarray:
        x, y, z = joint["origin_xyz_mm"]
        r, p, yaw = joint["origin_rpy_rad"]
        return translation(float(x), float(y), float(z)) @ rotation_rpy(float(r), float(p), float(yaw))

    def fk(self, q_rad: list[float]) -> dict[str, np.ndarray]:
        q_by_name = dict(zip(JOINT_ORDER, q_rad, strict=True))
        frames: dict[str, np.ndarray] = {"base_link": np.eye(4, dtype=np.float64)}
        for joint in self.joints:
            parent = joint["parent"]
            require(parent in frames, f"URDF is not ordered as an evaluable tree at {joint['name']}")
            matrix = frames[parent] @ self.origin_matrix(joint)
            if joint["type"] == "revolute":
                matrix = matrix @ rotation_axis(joint["axis"], float(q_by_name.get(joint["name"], 0.0)))
            elif joint["type"] == "prismatic":
                # Gripper prismatic state is outside C9; frozen default is zero.
                matrix = matrix @ translation(0.0, 0.0, 0.0)
            elif joint["type"] != "fixed":
                raise PoseFailure(f"unsupported accepted-URDF joint type: {joint['type']}")
            frames[joint["child"]] = matrix
        return frames


def parse_current_mount(path: Path) -> np.ndarray:
    mount_doc = strict_json(path)
    binding = mount_doc.get("binding", {})
    require(binding.get("canonical_decimal_places") == 12, "mount is not the current 12dp binding")
    require(binding.get("translation_unit") == "m", "mount translation unit drift")
    require(binding.get("matrix_semantics") == "p_parent=R_parent_child*p_child+t_parent_child",
            "mount matrix semantics drift")
    require(mount_doc.get("spelling_policy", {}).get("historical_D6_6dp_mount_forbidden") is True,
            "mount no longer forbids historical D6")
    strings = binding.get("canonical_matrix_decimal_strings")
    require(isinstance(strings, list) and len(strings) == 4, "mount matrix row count drift")
    for row in strings:
        require(isinstance(row, list) and len(row) == 4, "mount matrix column count drift")
        require(all(isinstance(value, str) and TWELVE_DECIMAL.fullmatch(value) for value in row),
                "mount matrix is not canonical 12dp decimal strings")
    matrix = np.asarray([[float(value) for value in row] for row in strings], dtype=np.float64)
    require(np.isfinite(matrix).all(), "mount contains non-finite values")
    require(np.array_equal(matrix[3], np.array([0.0, 0.0, 0.0, 1.0])), "mount last row drift")
    require(float(np.max(np.abs(matrix[:3, :3].T @ matrix[:3, :3] - np.eye(3)))) <= 2.0e-12,
            "mount rotation is not orthonormal within 12dp spelling")
    matrix_mm = matrix.copy()
    matrix_mm[:3, 3] *= 1000.0
    return matrix_mm


def make_q_record(q_rad: Iterable[float]) -> dict[str, Any]:
    values = [float(value) for value in q_rad]
    payload = {"schema": "C9_Q_STATE_V1", "joint_order": JOINT_ORDER, "q_rad": values}
    return {"payload": payload, "payload_sha256": sha256_bytes(canonical_q_payload_bytes(payload))}


def validate_q_record(record: dict[str, Any], arm: SideEffectFreeArm) -> list[float]:
    require(isinstance(record, dict) and set(record) == {"payload", "payload_sha256"},
            "q record must contain only payload and payload_sha256")
    payload = record.get("payload")
    require(isinstance(payload, dict), "q payload is not an object")
    require(payload.get("schema") == "C9_Q_STATE_V1", "q payload schema drift")
    require(payload.get("joint_order") == JOINT_ORDER, "q joint order drift")
    values = payload.get("q_rad")
    require(isinstance(values, list) and len(values) == 6, "q vector must contain six values")
    q_rad: list[float] = []
    for name, value in zip(JOINT_ORDER, values, strict=True):
        require(not isinstance(value, bool) and isinstance(value, (int, float)), f"q is not numeric: {name}")
        q = float(value)
        require(math.isfinite(q), f"q is non-finite: {name}")
        lower, upper = arm.limits[name]
        require(lower is not None and upper is not None, f"finite limits missing: {name}")
        require(float(lower) - 1.0e-12 <= q <= float(upper) + 1.0e-12, f"q out of limit: {name}")
        q_rad.append(q)
    expected_hash = sha256_bytes(canonical_q_payload_bytes(payload))
    require(record.get("payload_sha256") == expected_hash, "q payload hash mismatch")
    return q_rad


def transform_point(matrix: np.ndarray, point: Iterable[float]) -> np.ndarray:
    value = np.ones(4, dtype=np.float64)
    value[:3] = np.asarray(list(point), dtype=np.float64)
    return (matrix @ value)[:3]


def transform_host_matrix(
    mount: np.ndarray,
    frames_q: dict[str, np.ndarray],
    frames_0: dict[str, np.ndarray],
    host: str,
) -> np.ndarray:
    require(host in frames_q and host in frames_0, f"host absent from accepted URDF: {host}")
    return mount @ frames_q[host] @ np.linalg.inv(frames_0[host])


def object_payload(index: dict[str, Any], selector: str) -> dict[str, Any]:
    row = next((item for item in index.get("objects", []) if item.get("selector") == selector), None)
    require(row is not None, f"capsule selector missing from index: {selector}")
    path = PACKAGE / str(row["json"]["path"])
    require(path.is_file(), f"capsule JSON missing: {path}")
    require(path.stat().st_size == row["json"]["bytes"] and sha256_path(path) == row["json"]["sha256"],
            f"capsule JSON pin drift: {selector}")
    return strict_json(path)


def section_endpoints(payload: dict[str, Any], section_index: int) -> tuple[np.ndarray, np.ndarray]:
    capsules = [capsule for capsule in payload["capsules"] if capsule["section_index"] == section_index]
    require(capsules, f"section has no capsules: {section_index}")
    return np.asarray(capsules[0]["a_A0_mm"], float), np.asarray(capsules[-1]["b_A0_mm"], float)


def j4_context(
    payload: dict[str, Any],
    q4: float,
    mount: np.ndarray,
    frames_q: dict[str, np.ndarray],
    frames_0: dict[str, np.ndarray],
) -> dict[str, Any]:
    p_a_fixed, p_a_q0 = section_endpoints(payload, 1)
    p_b_q0, p_b_fixed = section_endpoints(payload, 3)
    _, downstream_q0 = section_endpoints(payload, 5)
    downstream_start_q0, _ = section_endpoints(payload, 6)
    u_primitive = next(primitive for primitive in payload["primitives"] if primitive["section_index"] == 2)
    ann_primitive = next(primitive for primitive in payload["primitives"] if primitive["section_index"] == 5)
    u_center_q0 = np.asarray(u_primitive["center_A0_mm"], float)
    u_e1 = np.asarray(u_primitive["basis_e1_A0"], float)
    u_radius = float(u_primitive["radius_mm"])
    ann_center = np.asarray(ann_primitive["center_A0_mm"], float)
    ann_e1 = np.asarray(ann_primitive["basis_e1_A0"], float)
    ann_e2 = np.asarray(ann_primitive["basis_e2_A0"], float)
    ann_radius = float(ann_primitive["radius_mm"])
    alpha_fixed = float(ann_primitive["start_angle_rad"])
    beta_q0 = abs(float(ann_primitive["sweep_angle_rad"]))
    x_c = -205.0 - 27.5 * (q4 + 0.15)
    x_c_q0 = -205.0 - 27.5 * 0.15
    dx = x_c - x_c_q0
    u_center = u_center_q0 + np.array([dx, 0.0, 0.0])
    plane_a = u_center + u_radius * u_e1
    plane_b = u_center - u_radius * u_e1
    beta = math.radians(20.0) + (1.57 - q4)
    alpha_moving = alpha_fixed - beta
    ann_moving = ann_center + ann_radius * (
        math.cos(alpha_moving) * ann_e1 + math.sin(alpha_moving) * ann_e2)
    m3 = transform_host_matrix(mount, frames_q, frames_0, "link3")
    m4 = transform_host_matrix(mount, frames_q, frames_0, "link4")
    follower_endpoint_s = transform_point(m3, ann_moving)
    link4_endpoint_s = transform_point(m4, downstream_start_q0)
    x_fixed = float(p_a_fixed[0])
    exchange_q0 = 2.0 * (x_fixed - x_c_q0) + math.pi * u_radius + ann_radius * beta_q0
    exchange = 2.0 * (x_fixed - x_c) + math.pi * u_radius + ann_radius * beta
    return {
        "p_a_fixed": p_a_fixed,
        "p_a_q0": p_a_q0,
        "p_b_q0": p_b_q0,
        "p_b_fixed": p_b_fixed,
        "u_center_q0": u_center_q0,
        "u_center": u_center,
        "plane_a": plane_a,
        "plane_b": plane_b,
        "ann_center": ann_center,
        "ann_e1": ann_e1,
        "ann_e2": ann_e2,
        "ann_radius": ann_radius,
        "alpha_fixed": alpha_fixed,
        "beta_q0": beta_q0,
        "beta": beta,
        "alpha_moving": alpha_moving,
        "dx": dx,
        "x_c": x_c,
        "m3": m3,
        "m4": m4,
        "follower_endpoint_s": follower_endpoint_s,
        "link4_endpoint_s": link4_endpoint_s,
        "follower_closure_residual_mm": float(np.linalg.norm(follower_endpoint_s - link4_endpoint_s)),
        "dynamic_exchange_length_mm": exchange,
        "dynamic_exchange_length_residual_mm": exchange - exchange_q0,
        "source_section5_end_A0_mm": downstream_q0,
    }


def deform_j4_point(point: np.ndarray, section_index: int, context: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    if section_index in (0, 4):
        return transform_point(context["m3"], point), point
    if section_index == 1:
        direction = context["p_a_q0"] - context["p_a_fixed"]
        fraction = float((point - context["p_a_fixed"]) @ direction) / max(float(direction @ direction), 1.0e-15)
        deformed = context["p_a_fixed"] + fraction * (context["plane_a"] - context["p_a_fixed"])
        return transform_point(context["m3"], deformed), deformed
    if section_index == 2:
        deformed = point + np.array([context["dx"], 0.0, 0.0])
        return transform_point(context["m3"], deformed), deformed
    if section_index == 3:
        direction = context["p_b_fixed"] - context["p_b_q0"]
        fraction = float((point - context["p_b_q0"]) @ direction) / max(float(direction @ direction), 1.0e-15)
        deformed = context["plane_b"] + fraction * (context["p_b_fixed"] - context["plane_b"])
        return transform_point(context["m3"], deformed), deformed
    if section_index == 5:
        relative = point - context["ann_center"]
        alpha0 = math.atan2(float(relative @ context["ann_e2"]), float(relative @ context["ann_e1"]))
        fraction = float(np.clip((context["alpha_fixed"] - alpha0) / context["beta_q0"], 0.0, 1.0))
        alpha = context["alpha_fixed"] - context["beta"] * fraction
        deformed = context["ann_center"] + context["ann_radius"] * (
            math.cos(alpha) * context["ann_e1"] + math.sin(alpha) * context["ann_e2"])
        return transform_point(context["m3"], deformed), deformed
    if section_index == 6:
        return transform_point(context["m4"], point), point
    raise PoseFailure(f"unexpected J4 section index: {section_index}")


def pose_object(
    payload: dict[str, Any],
    q_record: dict[str, Any],
    arm: SideEffectFreeArm,
    mount: np.ndarray,
) -> dict[str, Any]:
    q = validate_q_record(q_record, arm)
    frames_0 = arm.fk([0.0] * 6)
    frames_q = arm.fk(q)
    selector = payload["selector"]
    posed: list[dict[str, Any]] = []
    j4 = j4_context(payload, q[3], mount, frames_q, frames_0) if selector == J4_SELECTOR else None
    for capsule in payload["capsules"]:
        section_index = int(capsule["section_index"])
        a0 = np.asarray(capsule["a_A0_mm"], dtype=np.float64)
        b0 = np.asarray(capsule["b_A0_mm"], dtype=np.float64)
        representations: list[dict[str, Any]] = []
        if j4 is not None:
            a_s, _ = deform_j4_point(a0, section_index, j4)
            b_s, _ = deform_j4_point(b0, section_index, j4)
            bound = float(capsule["hausdorff_bound_mm"])
            curve_step = float(capsule["curve_arclength_step_mm"])
            if section_index == 5:
                delta = float(capsule["delta_theta_rad"]) * j4["beta"] / j4["beta_q0"]
                curve_step = j4["ann_radius"] * abs(delta)
                bound = j4["ann_radius"] * (1.0 - math.cos(abs(delta) / 2.0))
            design_radius = float(capsule["design_radius_mm"])
            representations.append({
                "role": "PRIMARY",
                "host": capsule["primary_host"],
                "a_S_mm": a_s.tolist(),
                "b_S_mm": b_s.tolist(),
                "design_radius_mm": design_radius,
                "hausdorff_bound_mm": bound,
                "effective_radius_mm": design_radius + bound,
                "curve_arclength_step_mm": curve_step,
                "curve_step_limit_applies": bool(capsule["curve_step_limit_applies"]),
                "narrowphase_query_radius_field": "effective_radius_mm",
            })
        else:
            primary = transform_host_matrix(mount, frames_q, frames_0, capsule["primary_host"])
            design_radius = float(capsule["design_radius_mm"])
            bound = float(capsule["hausdorff_bound_mm"])
            representations.append({
                "role": "PRIMARY",
                "host": capsule["primary_host"],
                "a_S_mm": transform_point(primary, a0).tolist(),
                "b_S_mm": transform_point(primary, b0).tolist(),
                "design_radius_mm": design_radius,
                "hausdorff_bound_mm": bound,
                "effective_radius_mm": design_radius + bound,
                "curve_arclength_step_mm": float(capsule["curve_arclength_step_mm"]),
                "curve_step_limit_applies": bool(capsule["curve_step_limit_applies"]),
                "narrowphase_query_radius_field": "effective_radius_mm",
            })
            alternate_host = capsule.get("alternate_host")
            if alternate_host is not None:
                alternate = transform_host_matrix(mount, frames_q, frames_0, alternate_host)
                representations.append({
                    "role": "ALTERNATE_CONSERVATIVE",
                    "host": alternate_host,
                    "a_S_mm": transform_point(alternate, a0).tolist(),
                    "b_S_mm": transform_point(alternate, b0).tolist(),
                    "design_radius_mm": design_radius,
                    "hausdorff_bound_mm": bound,
                    "effective_radius_mm": design_radius + bound,
                    "curve_arclength_step_mm": float(capsule["curve_arclength_step_mm"]),
                    "curve_step_limit_applies": bool(capsule["curve_step_limit_applies"]),
                    "narrowphase_query_radius_field": "effective_radius_mm",
                })
        posed.append({
            "capsule_id": capsule["capsule_id"],
            "section_index": section_index,
            "required_query_radius_field": "effective_radius_mm",
            "representations": representations,
        })
    result = {
        "schema": "ROUTE_C_C9_POSED_CAPSULE_OBJECT_V1",
        "object_id": payload["object_id"],
        "selector": selector,
        "q_payload_sha256": q_record["payload_sha256"],
        "output_frame": "spacecraft_bus_S",
        "length_unit": "mm",
        "narrowphase_consumer_contract": {
            "required_query_radius_field": "effective_radius_mm",
            "effective_radius_rule": "design_radius_mm + hausdorff_bound_mm exactly once",
            "raw_design_radius_for_curved_capsule": "FORBIDDEN_FAIL_CLOSED",
            "second_hausdorff_debit_or_inflation": "FORBIDDEN_FAIL_CLOSED",
        },
        "capsules": posed,
        "j3_continuous_motion_law": payload.get("j3_continuous_motion_law"),
        "j3_production_union_acceptance": payload.get("j3_production_union_acceptance"),
        "authority": "LOCAL_POSED_CANDIDATE_ONLY__NO_PAIR_EDGE_PATH_OR_RELEASE_CREDIT",
    }
    if j4 is not None:
        section5_representations = [
            representation
            for capsule in posed if capsule["section_index"] == 5
            for representation in capsule["representations"]
        ]
        require(len(section5_representations) == 139, "J4 section-5 posed topology is not 139")
        result["j4_metrics"] = {
            "q4_rad": q[3],
            "x_c_mm": j4["x_c"],
            "annulus_beta_rad": j4["beta"],
            "dynamic_exchange_length_residual_mm": j4["dynamic_exchange_length_residual_mm"],
            "follower_closure_residual_mm": j4["follower_closure_residual_mm"],
            "section5_topology_capsule_count": len(section5_representations),
            "section5_max_dynamic_curve_arclength_step_mm": max(
                float(item["curve_arclength_step_mm"]) for item in section5_representations),
            "section5_max_dynamic_hausdorff_bound_mm": max(
                float(item["hausdorff_bound_mm"]) for item in section5_representations),
            "section5_max_dynamic_effective_radius_mm": max(
                float(item["effective_radius_mm"]) for item in section5_representations),
            "full_hardware_annular_coverage": "DEFERRED_HOLD",
        }
    return result


def load_context() -> tuple[dict[str, Any], SideEffectFreeArm, np.ndarray, dict[str, Any]]:
    root = workspace_root()
    lock = strict_json(SOURCE_LOCK_PATH)
    sources = lock.get("sources", {})
    require(isinstance(sources, dict) and len(sources) == 18, "source lock drift")
    urdf_path = verify_pin(root, sources["accepted_urdf"], "accepted_urdf")
    mount_path = verify_pin(root, sources["current_execution_mount_12dp"], "current_execution_mount_12dp")
    verify_pin(root, sources["mandatory_q_contract"], "mandatory_q_contract")
    verify_pin(root, sources["v9f_centerline"], "v9f_centerline")
    verify_pin(root, sources["current_m01_registry"], "current_m01_registry")
    contract = strict_json(CONTRACT_PATH)
    declaration = contract.get("system_truth_declaration_only", {})
    require(declaration.get("authority") ==
            "DECLARATION_ONLY__MUST_BE_REBUILT_FROM_FOUR_HASH_PINNED_CURRENT_MACHINE_GATES",
            "system truth declaration was presented as self-authority")
    index = strict_json(INDEX_PATH)
    require(index.get("object_count") == 9, "capsule index object count drift")
    return index, SideEffectFreeArm(urdf_path), parse_current_mount(mount_path), contract


def self_check_receipt() -> dict[str, Any]:
    index, arm, mount, contract = load_context()
    j4_payload = object_payload(index, J4_SELECTOR)
    samples = []
    max_follower = 0.0
    max_exchange = 0.0
    full_domain_max_step = 0.0
    full_domain_max_bound = 0.0
    full_domain_max_effective = 0.0
    q0_mount_residual = 0.0
    for q4 in (-1.87, 0.0, 1.57):
        q = [0.0, 0.0, 0.0, q4, 0.0, 0.0]
        q_record = make_q_record(q)
        posed = pose_object(j4_payload, q_record, arm, mount)
        metrics = posed["j4_metrics"]
        expected_delta = float(metrics["annulus_beta_rad"]) / 139.0
        expected_step = 55.0 * expected_delta
        expected_bound = 55.0 * (1.0 - math.cos(expected_delta / 2.0))
        section5_checked = 0
        representation_count = 0
        for capsule in posed["capsules"]:
            for representation in capsule["representations"]:
                representation_count += 1
                design = float(representation["design_radius_mm"])
                bound = float(representation["hausdorff_bound_mm"])
                effective = float(representation["effective_radius_mm"])
                require(design == 5.0, "posed representation design radius drift")
                require(abs(effective - (design + bound)) <= 1.0e-15,
                        "posed representation effective radius is not design plus bound exactly once")
                require(representation["narrowphase_query_radius_field"] == "effective_radius_mm",
                        "posed representation query field drift")
                if representation["curve_step_limit_applies"]:
                    require(float(representation["curve_arclength_step_mm"]) <= 1.5 + 1.0e-12,
                            "posed curve step exceeds 1.5 mm")
                if capsule["section_index"] == 5:
                    section5_checked += 1
                    require(abs(float(representation["curve_arclength_step_mm"]) - expected_step) <= 2.0e-12,
                            "J4 section-5 dynamic step mismatch")
                    require(abs(bound - expected_bound) <= 2.0e-15,
                            "J4 section-5 dynamic Hausdorff mismatch")
                    require(abs(effective - (5.0 + expected_bound)) <= 2.0e-15,
                            "J4 section-5 dynamic effective radius mismatch")
        require(section5_checked == 139, "J4 section-5 did not validate all 139 representations")
        require(representation_count == len(posed["capsules"]), "unexpected J4 alternate representation")
        require(metrics["section5_topology_capsule_count"] == 139, "J4 metric topology count drift")
        require(abs(float(metrics["section5_max_dynamic_curve_arclength_step_mm"]) - expected_step) <= 2.0e-12,
                "J4 metric dynamic step drift")
        require(abs(float(metrics["section5_max_dynamic_hausdorff_bound_mm"]) - expected_bound) <= 2.0e-15,
                "J4 metric dynamic Hausdorff drift")
        require(abs(float(metrics["section5_max_dynamic_effective_radius_mm"]) - (5.0 + expected_bound)) <= 2.0e-15,
                "J4 metric dynamic effective radius drift")
        full_domain_max_step = max(full_domain_max_step, expected_step)
        full_domain_max_bound = max(full_domain_max_bound, expected_bound)
        full_domain_max_effective = max(full_domain_max_effective, 5.0 + expected_bound)
        max_follower = max(max_follower, abs(float(metrics["follower_closure_residual_mm"])))
        max_exchange = max(max_exchange, abs(float(metrics["dynamic_exchange_length_residual_mm"])))
        if q4 == 0.0:
            source_by_id = {capsule["capsule_id"]: capsule for capsule in j4_payload["capsules"]}
            for capsule in posed["capsules"]:
                source = source_by_id[capsule["capsule_id"]]
                primary = capsule["representations"][0]
                q0_mount_residual = max(
                    q0_mount_residual,
                    float(np.linalg.norm(np.asarray(primary["a_S_mm"]) - transform_point(mount, source["a_A0_mm"]))),
                    float(np.linalg.norm(np.asarray(primary["b_S_mm"]) - transform_point(mount, source["b_A0_mm"]))),
                )
        samples.append({
            "q4_rad": q4,
            "q_payload_sha256": q_record["payload_sha256"],
            "x_c_mm": metrics["x_c_mm"],
            "annulus_beta_rad": metrics["annulus_beta_rad"],
            "dynamic_exchange_length_residual_mm": metrics["dynamic_exchange_length_residual_mm"],
            "follower_closure_residual_mm": metrics["follower_closure_residual_mm"],
            "section5_topology_capsule_count": section5_checked,
            "section5_segments_recomputed": section5_checked,
            "section5_max_dynamic_curve_arclength_step_mm": expected_step,
            "section5_max_dynamic_hausdorff_bound_mm": expected_bound,
            "section5_max_dynamic_effective_radius_mm": 5.0 + expected_bound,
            "all_posed_representations_effective_radius_checked": representation_count,
        })
    require(samples[0]["x_c_mm"] > samples[1]["x_c_mm"] > samples[2]["x_c_mm"], "J4 x_c sign drift")
    require(samples[0]["annulus_beta_rad"] > samples[1]["annulus_beta_rad"] > samples[2]["annulus_beta_rad"],
            "J4 beta sign drift")
    require(max_follower <= 1.0e-6, f"J4 follower closure failure: {max_follower}")
    require(max_exchange <= 1.0e-9, f"J4 exchange-length failure: {max_exchange}")
    require(q0_mount_residual <= 1.0e-9, f"J4 q0 identity/mount failure: {q0_mount_residual}")
    require(full_domain_max_step <= 1.5 + 1.0e-12, "J4 section-5 full-domain step failure")
    require(abs(full_domain_max_step - 1.4992706602297674) <= 2.0e-15,
            "J4 section-5 full-domain worst-step drift")

    j3_payload = object_payload(index, J3_SELECTOR)
    j3_q = make_q_record([0.0, 0.0, -1.0, 0.0, 0.0, 0.0])
    j3_posed = pose_object(j3_payload, j3_q, arm, mount)
    dual = [capsule for capsule in j3_posed["capsules"] if len(capsule["representations"]) == 2]
    separation = 0.0
    for capsule in dual:
        primary, alternate = capsule["representations"]
        for representation in (primary, alternate):
            require(representation["narrowphase_query_radius_field"] == "effective_radius_mm",
                    "J3 posed representation query-radius field drift")
            require(abs(float(representation["effective_radius_mm"]) -
                        (float(representation["design_radius_mm"]) +
                         float(representation["hausdorff_bound_mm"]))) <= 1.0e-15,
                    "J3 posed representation effective-radius drift")
        separation = max(
            separation,
            float(np.linalg.norm(np.asarray(primary["a_S_mm"]) - np.asarray(alternate["a_S_mm"]))),
            float(np.linalg.norm(np.asarray(primary["b_S_mm"]) - np.asarray(alternate["b_S_mm"]))),
        )
    require(dual and separation > 0.0, "J3 dual-host representations were not emitted distinctly")
    require(j3_posed["j3_continuous_motion_law"] == "UNKNOWN", "J3 continuous law overreach")
    require(j3_posed["j3_production_union_acceptance"] == "UNKNOWN", "J3 union acceptance overreach")

    return {
        "schema": "ROUTE_C_C9_POSE_ADAPTER_SELF_CHECK_V1",
        "generated_utc": "DETERMINISTIC_POSE_CHECK_NO_WALLCLOCK",
        "adapter": {
            "path": Path(__file__).resolve().relative_to(workspace_root()).as_posix(),
            "bytes": Path(__file__).stat().st_size,
            "sha256": sha256_path(Path(__file__)),
            "side_effect_free_source_consumption": True,
            "v9f_builder_or_evaluator_imported": False,
        },
        "mount": {
            "source_sha256": "B7758F751E273CE21CCD5132C23F2514524DE7613E31B33646E027603B0F6653",
            "canonical_decimal_places": 12,
            "translation_converted_m_to_mm_exactly_once": True,
            "historical_D6_used": False,
        },
        "urdf": {
            "source_sha256": "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
            "joint_order": JOINT_ORDER,
            "joint_limits": {name: list(arm.limits[name]) for name in JOINT_ORDER},
            "parsed_directly_without_generator_execution": True,
        },
        "j4_samples": samples,
        "j4_q4_test_values_rad": [-1.87, 0.0, 1.57],
        "j4_max_follower_closure_residual_mm": max_follower,
        "j4_max_dynamic_exchange_length_residual_mm": max_exchange,
        "j4_section5_full_domain_topology_capsule_count": 139,
        "j4_section5_full_domain_max_dynamic_curve_arclength_step_mm": full_domain_max_step,
        "j4_section5_full_domain_max_dynamic_hausdorff_bound_mm": full_domain_max_bound,
        "j4_section5_full_domain_max_dynamic_effective_radius_mm": full_domain_max_effective,
        "j4_all_139_segments_recomputed_at_each_q4_sample": True,
        "effective_radius_rule_checked_for_every_posed_representation": True,
        "j4_q0_mount_identity_max_residual_mm": q0_mount_residual,
        "j4_sign_checks_pass": True,
        "j4_full_hardware_annular_coverage": "DEFERRED_HOLD",
        "j3": {
            "test_q3_rad": -1.0,
            "dual_host_capsule_count": len(dual),
            "maximum_primary_alternate_separation_mm": separation,
            "continuous_q3_carrier_law": "UNKNOWN",
            "production_union_acceptance": "UNKNOWN",
        },
        "system_truth_declaration_only": contract["system_truth_declaration_only"],
        "pose_adapter_self_check_pass": True,
        "maximum_legal_claim": "SIDE_EFFECT_FREE_LOCAL_C9_POSE_ADAPTER_SELF_CHECK_PASS__J3_PRODUCTION_UNION_UNKNOWN",
        "verdict": "C9_POSE_ADAPTER_LOCAL_SELF_CHECK_PASS__ZERO_CURRENT_PAIR_EDGE_PATH_CREDIT__TMG4_HOLD",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-self-check", action="store_true")
    mode.add_argument("--check-self-check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = self_check_receipt()
    encoded = stable_json_bytes(receipt)
    if args.write_self_check:
        atomic_write(SELF_CHECK_PATH, encoded)
        mode = "write"
    else:
        require(SELF_CHECK_PATH.is_file(), f"self-check receipt missing: {SELF_CHECK_PATH}")
        require(SELF_CHECK_PATH.read_bytes() == encoded, "pose-adapter self-check receipt drift")
        mode = "check"
    print(json.dumps({
        "status": "PASS",
        "mode": mode,
        "j4_samples": 3,
        "j4_max_follower_closure_residual_mm": receipt["j4_max_follower_closure_residual_mm"],
        "j4_max_dynamic_exchange_length_residual_mm": receipt["j4_max_dynamic_exchange_length_residual_mm"],
        "j4_section5_full_domain_max_dynamic_curve_arclength_step_mm":
            receipt["j4_section5_full_domain_max_dynamic_curve_arclength_step_mm"],
        "j4_section5_full_domain_max_dynamic_hausdorff_bound_mm":
            receipt["j4_section5_full_domain_max_dynamic_hausdorff_bound_mm"],
        "j3_dual_host_capsules": receipt["j3"]["dual_host_capsule_count"],
        "j3_production_union_acceptance": "UNKNOWN",
        "system_pair_credit": 0,
        "TMG4": "HOLD",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
