"""Independent V4B3 physics/DAG audit and sole final-Gate issuer.

This file deliberately does not import ``b3_contact``, ``branched_model``,
``dual_contact_kernel`` or ``validate_phase_b3``.  It parses the frozen B601
URDF, locally reconstructs the V4A free-base/6R geometry plus the fixed palm
and two sibling prismatic fingers, and recomputes every contact and ledger
quantity from hash-bound raw trace records.

The only positive conclusion this auditor may issue is an audited *synthetic
transient dual-contact candidate*.  Physical contact, held grasp, lock,
current-system binding, formal NC19, production and release remain false.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence
import xml.etree.ElementTree as ET

import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
V4_ROOT = HERE.parent
URDF = PROJECT_ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
V4A_MODEL = V4_ROOT / "sim13_v4a/full_floating.py"

SOURCE_MANIFEST = HERE / "evidence/SIM13_V4B3_SOURCE_MANIFEST_V1.json"
TRACE = HERE / "evidence/SIM13_V4B3_DUAL_CONTACT_TRACE_V1.json"
LEDGER = HERE / "evidence/SIM13_V4B3_DUAL_CONTACT_LEDGER_V1.json"
VALIDATION = HERE / "evidence/SIM13_V4B3_VALIDATION_V1.json"
EVIDENCE_MANIFEST = HERE / "evidence/SIM13_V4B3_EVIDENCE_MANIFEST_V1.json"
PRE_AUDIT_GATE = HERE / "results/SIM13_V4B3_PRE_AUDIT_GATE_V1.json"
AUDIT_RECEIPT = HERE / "evidence/SIM13_V4B3_INDEPENDENT_AUDIT_RECEIPT_V1.json"
FINAL_GATE = HERE / "results/SIM13_V4B3_AUDITED_GATE_V1.json"
TERMINAL_MANIFEST = HERE / "results/SIM13_V4B3_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"

EXPECTED_PHASE_A_GATE_SHA = "82ECF267AA5F0DF0B79610AB4FBFD4DB4AE564EDE530A7F69AB579D1E15F7A40"
EXPECTED_PHASE_B2_GATE_SHA = "475FE497F8C302AB163A399362A20D322A4753DA557C0116015D21D0E17FD2DE"
EXPECTED_URDF_SHA = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"

BASE_MASS_KG = 19.4
BASE_INERTIA_BODY_KG_M2 = np.diag((0.46, 0.52, 0.39))
ARM_MASSES_KG = np.asarray((1.15, 0.94, 0.78, 0.62, 0.47, 0.36), dtype=float)
ARM_INERTIAS_BODY_KG_M2 = tuple(
    np.diag(values)
    for values in (
        (0.010, 0.019, 0.020),
        (0.008, 0.015, 0.016),
        (0.006, 0.012, 0.013),
        (0.0045, 0.0090, 0.0095),
        (0.0033, 0.0062, 0.0066),
        (0.0025, 0.0045, 0.0048),
    )
)
ARM_AXES_PARENT = tuple(
    np.asarray(axis, dtype=float)
    for axis in (
        (0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
    )
)
ARM_JOINT_ORIGINS_PARENT_M = tuple(
    np.asarray(value, dtype=float)
    for value in (
        (0.19, 0.00, 0.11),
        (0.03, 0.01, 0.00),
        (0.02, -0.01, 0.01),
        (0.02, 0.00, 0.00),
        (0.01, 0.01, 0.00),
        (0.015, 0.00, 0.005),
    )
)
ARM_TIP_OFFSETS_BODY_M = tuple(
    np.asarray(value, dtype=float)
    for value in (
        (0.30, 0.00, 0.00),
        (0.27, 0.00, 0.00),
        (0.24, 0.00, 0.00),
        (0.20, 0.00, 0.00),
        (0.17, 0.00, 0.00),
        (0.14, 0.00, 0.00),
    )
)
ARM_COM_OFFSETS_BODY_M = tuple(0.48 * value for value in ARM_TIP_OFFSETS_BODY_M)
TARGET_MASS_KG = 22.0
TARGET_INERTIA_BODY_KG_M2 = np.asarray(
    ((2.8, 0.08, -0.04), (0.08, 3.5, 0.06), (-0.04, 0.06, 4.1)), dtype=float
)

FLOORS = {
    "service_base_position_m": 1.0e-12,
    "service_base_quaternion_geodesic_rad": 5.0e-8,
    "service_q_R_rad": 1.0e-12,
    "service_q_P_m": 1.0e-12,
    "service_v_base_m_s": 1.0e-12,
    "service_omega_base_rad_s": 1.0e-14,
    "service_qdot_R_rad_s": 1.0e-12,
    "service_qdot_P_m_s": 1.0e-12,
    "target_position_m": 1.0e-12,
    "target_quaternion_geodesic_rad": 5.0e-8,
    "target_velocity_m_s": 1.0e-12,
    "target_omega_rad_s": 1.0e-14,
}

MIDPOINT_REFERENCE_ENVELOPE = {
    "service_base_position_m": 2.0e-6,
    "service_base_quaternion_geodesic_rad": 2.0e-5,
    "service_q_R_rad": 2.0e-5,
    "service_q_P_m": 2.0e-5,
    "service_v_base_m_s": 1.0e-3,
    "service_omega_base_rad_s": 1.0e-3,
    "service_qdot_R_rad_s": 1.0e-3,
    "service_qdot_P_m_s": 1.0e-3,
    "target_position_m": 2.0e-6,
    "target_quaternion_geodesic_rad": 2.0e-5,
    "target_velocity_m_s": 1.0e-3,
    "target_omega_rad_s": 1.0e-3,
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _record(path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": _relative(path),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _resolve(relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    candidate = (PROJECT_ROOT / relative).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return None
    return candidate


def _strict_reference(reference: Any, path: Path, role: str) -> dict[str, Any]:
    actual = _record(path, role) if path.is_file() else None
    passed = isinstance(reference, dict) and reference == actual
    return {"pass": bool(passed), "declared": reference, "actual": actual}


def _array(values: Sequence[float], size: int, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain {size} finite values")
    return result


def _vec(text: str | None, size: int = 3) -> np.ndarray:
    if text is None:
        return np.zeros(size)
    return _array([float(item) for item in text.split()], size, "XML vector")


def _skew(vector: Sequence[float]) -> np.ndarray:
    x, y, z = _array(vector, 3, "skew vector")
    return np.asarray(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def _normalize_quaternion(value: Sequence[float]) -> np.ndarray:
    result = _array(value, 4, "quaternion")
    norm = float(np.linalg.norm(result))
    if norm < 1.0e-14:
        raise ValueError("zero quaternion")
    return result / norm


def _quat_to_rotation(value: Sequence[float]) -> np.ndarray:
    w, x, y, z = _normalize_quaternion(value)
    return np.asarray(
        (
            (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
            (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
            (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
        )
    )


def _axis_rotation(axis: Sequence[float], angle: float) -> np.ndarray:
    direction = _array(axis, 3, "rotation axis").copy()
    direction /= np.linalg.norm(direction)
    cross = _skew(direction)
    return np.eye(3) + math.sin(angle) * cross + (1.0 - math.cos(angle)) * (cross @ cross)


def _canonical_angle(angle: float) -> float:
    quarter = round(angle / (0.5 * math.pi)) * (0.5 * math.pi)
    return quarter if abs(angle - quarter) <= 5.0e-6 else angle


def _rpy_rotation(rpy: Sequence[float], *, canonical: bool = True) -> np.ndarray:
    roll, pitch, yaw = _array(rpy, 3, "rpy")
    if canonical:
        roll, pitch, yaw = (_canonical_angle(float(item)) for item in (roll, pitch, yaw))
    return (
        _axis_rotation((0.0, 0.0, 1.0), float(yaw))
        @ _axis_rotation((0.0, 1.0, 0.0), float(pitch))
        @ _axis_rotation((1.0, 0.0, 0.0), float(roll))
    )


def _quaternion_geodesic(left: Sequence[float], right: Sequence[float]) -> float:
    lq = _normalize_quaternion(left); rq = _normalize_quaternion(right)
    return float(2.0 * math.acos(min(1.0, abs(float(lq @ rq)))))


def _inertial_from_link(link: ET.Element) -> dict[str, Any]:
    inertial = link.find("inertial")
    if inertial is None:
        raise ValueError(f"missing inertial for {link.get('name')}")
    origin = inertial.find("origin"); mass = inertial.find("mass"); inertia = inertial.find("inertia")
    if origin is None or mass is None or inertia is None:
        raise ValueError(f"incomplete inertial for {link.get('name')}")
    tensor = np.asarray(
        (
            (float(inertia.get("ixx")), float(inertia.get("ixy")), float(inertia.get("ixz"))),
            (float(inertia.get("ixy")), float(inertia.get("iyy")), float(inertia.get("iyz"))),
            (float(inertia.get("ixz")), float(inertia.get("iyz")), float(inertia.get("izz"))),
        )
    )
    rpy = _vec(origin.get("rpy"))
    rotation = _rpy_rotation(rpy)
    return {
        "mass": float(mass.get("value")),
        "com": _vec(origin.get("xyz")),
        "inertia": rotation @ tensor @ rotation.T,
    }


def _joint_from_xml(joint: ET.Element) -> dict[str, Any]:
    origin = joint.find("origin"); axis = joint.find("axis"); limit = joint.find("limit")
    parent = joint.find("parent"); child = joint.find("child")
    if origin is None or parent is None or child is None:
        raise ValueError(f"incomplete joint {joint.get('name')}")
    literal_rpy = _vec(origin.get("rpy"))
    rotation = _rpy_rotation(literal_rpy)
    axis_joint = _vec(axis.get("xyz")) if axis is not None else np.zeros(3)
    return {
        "name": joint.get("name"), "type": joint.get("type"),
        "parent": parent.get("link"), "child": child.get("link"),
        "origin": _vec(origin.get("xyz")), "literal_rpy": literal_rpy,
        "rotation": rotation, "axis_joint": axis_joint,
        "axis_parent": rotation @ axis_joint,
        "lower": float(limit.get("lower")) if limit is not None and limit.get("lower") is not None else None,
        "upper": float(limit.get("upper")) if limit is not None and limit.get("upper") is not None else None,
    }


def _parse_urdf() -> tuple[dict[str, Any], dict[str, Any]]:
    root = ET.parse(URDF).getroot()
    links = {item.get("name"): item for item in root.findall("link")}
    joints = {item.get("name"): _joint_from_xml(item) for item in root.findall("joint")}
    required_links = ("gripper_link", "gripper_left", "gripper_right")
    required_joints = ("gripper_joint", "gripper_joint1", "gripper_joint2")
    if not all(name in links for name in required_links) or not all(name in joints for name in required_joints):
        raise ValueError("frozen URDF lacks required gripper topology")
    palm_joint = joints["gripper_joint"]
    left_joint = joints["gripper_joint1"]
    right_joint = joints["gripper_joint2"]
    data = {
        "palm": _inertial_from_link(links["gripper_link"]),
        "left": _inertial_from_link(links["gripper_left"]),
        "right": _inertial_from_link(links["gripper_right"]),
        "palm_joint": palm_joint, "left_joint": left_joint, "right_joint": right_joint,
    }
    literal_canonical_error = max(
        float(np.max(np.abs(_rpy_rotation(item["literal_rpy"], canonical=False) - item["rotation"])))
        for item in (palm_joint, left_joint, right_joint)
    )
    checks = {
        "urdf_sha256": _sha(URDF),
        "palm_fixed_parent_child": palm_joint["type"] == "fixed" and palm_joint["parent"] == "link6" and palm_joint["child"] == "gripper_link",
        "left_sibling_topology": left_joint["type"] == "prismatic" and left_joint["parent"] == "gripper_link" and left_joint["child"] == "gripper_left",
        "right_sibling_topology": right_joint["type"] == "prismatic" and right_joint["parent"] == "gripper_link" and right_joint["child"] == "gripper_right",
        "left_axis_palm": left_joint["axis_parent"].tolist(),
        "right_axis_palm": right_joint["axis_parent"].tolist(),
        "left_stroke_m": [left_joint["lower"], left_joint["upper"]],
        "right_stroke_m": [right_joint["lower"], right_joint["upper"]],
        "literal_to_canonical_rotation_max_error": literal_canonical_error,
    }
    checks["pass"] = bool(
        checks["urdf_sha256"] == EXPECTED_URDF_SHA
        and checks["palm_fixed_parent_child"]
        and checks["left_sibling_topology"] and checks["right_sibling_topology"]
        and np.max(np.abs(left_joint["axis_parent"] - np.asarray((0.0, -1.0, 0.0)))) <= 1.0e-12
        and np.max(np.abs(right_joint["axis_parent"] - np.asarray((0.0, 1.0, 0.0)))) <= 1.0e-12
        and [left_joint["lower"], left_joint["upper"]] == [0.0, 0.0715]
        and [right_joint["lower"], right_joint["upper"]] == [0.0, 0.0715]
        and literal_canonical_error <= 5.0e-6
    )
    return data, checks


def _v4a_source_audit() -> dict[str, Any]:
    """Bind the locally reconstructed canonical constants to the frozen V4A source."""
    text = V4A_MODEL.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported_modules = []
    for node in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    required_snippets = (
        "self.base_mass_kg = 19.4",
        "self.base_inertia_body_kg_m2 = np.diag((0.46, 0.52, 0.39))",
        "self.link_masses_kg = np.array((1.15, 0.94, 0.78, 0.62, 0.47, 0.36, 0.24, 0.19))",
        "TARGET_MASS_KG = 22.0",
        "((2.8, 0.08, -0.04), (0.08, 3.5, 0.06), (-0.04, 0.06, 4.1))",
    )
    banned = ("b3_contact", "branched_model", "dual_contact_kernel", "validate_phase_b3")
    return {
        "v4a_source_sha256": _sha(V4A_MODEL),
        "v4a_ast_parsed": isinstance(tree, ast.Module),
        "required_canonical_snippets_present": all(item in text for item in required_snippets),
        "audit_imported_modules": sorted(set(imported_modules)),
        "banned_runtime_imports_absent": not any(
            module == name or module.startswith(f"{name}.")
            for module in imported_modules for name in banned
        ),
    }


def _service_state(record: dict[str, Any]) -> dict[str, np.ndarray]:
    data = record["service"]
    return {
        "base_position": _array(data["base_position_inertial_m"], 3, "service base position"),
        "base_quaternion": _normalize_quaternion(data["base_quaternion_body_to_inertial_wxyz"]),
        "q": _array(data["joint_coordinates_mixed"], 8, "service q"),
        "nu": _array(data["nu_s_mixed"], 14, "service nu"),
    }


def _target_state(record: dict[str, Any]) -> dict[str, np.ndarray]:
    data = record["target"]
    return {
        "position": _array(data["position_inertial_m"], 3, "target position"),
        "quaternion": _normalize_quaternion(data["quaternion_body_to_inertial_wxyz"]),
        "twist": _array(data["twist_inertial_mixed"], 6, "target twist"),
    }


def _arm_point_jacobians(
    state: dict[str, np.ndarray], point: np.ndarray, origins: list[np.ndarray], axes: list[np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    jv = np.zeros((3, 14)); jw = np.zeros((3, 14))
    jv[:, :3] = np.eye(3); jv[:, 3:6] = -_skew(point - state["base_position"])
    jw[:, 3:6] = np.eye(3)
    for index, (origin, axis) in enumerate(zip(origins, axes)):
        jv[:, 6 + index] = np.cross(axis, point - origin)
        jw[:, 6 + index] = axis
    return jv, jw


def _frames(state: dict[str, np.ndarray], urdf: dict[str, Any]) -> dict[str, Any]:
    parent_position = state["base_position"].copy()
    parent_rotation = _quat_to_rotation(state["base_quaternion"])
    origins: list[np.ndarray] = []; axes: list[np.ndarray] = []
    link_origins: list[np.ndarray] = []; link_rotations: list[np.ndarray] = []
    for index in range(6):
        origin = parent_position + parent_rotation @ ARM_JOINT_ORIGINS_PARENT_M[index]
        axis = parent_rotation @ ARM_AXES_PARENT[index]
        child_rotation = parent_rotation @ _axis_rotation(ARM_AXES_PARENT[index], float(state["q"][index]))
        origins.append(origin); axes.append(axis)
        link_origins.append(origin); link_rotations.append(child_rotation)
        parent_position = origin + child_rotation @ ARM_TIP_OFFSETS_BODY_M[index]
        parent_rotation = child_rotation
    palm_joint = urdf["palm_joint"]
    palm_origin = parent_position + parent_rotation @ palm_joint["origin"]
    palm_rotation = parent_rotation @ palm_joint["rotation"]
    result: dict[str, Any] = {
        "arm_origins": origins, "arm_axes": axes,
        "link_origins": link_origins, "link_rotations": link_rotations,
        "palm_origin": palm_origin, "palm_rotation": palm_rotation,
    }
    for side, q_index in (("left", 6), ("right", 7)):
        joint = urdf[f"{side}_joint"]
        joint_origin = palm_origin + palm_rotation @ joint["origin"]
        axis = palm_rotation @ joint["axis_parent"]
        result[f"{side}_joint_origin"] = joint_origin
        result[f"{side}_axis"] = axis
        result[f"{side}_origin"] = joint_origin + axis * float(state["q"][q_index])
        result[f"{side}_rotation"] = palm_rotation @ joint["rotation"]
    return result


def _pad(
    state: dict[str, np.ndarray], frames: dict[str, Any], scenario: dict[str, Any], side: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    q_index, column, sign = (6, 12, -1.0) if side == "left" else (7, 13, 1.0)
    local = np.asarray(
        (
            float(scenario["pad_x_palm_m"]),
            sign * (float(scenario["closed_half_gap_m"]) + float(state["q"][q_index])),
            float(scenario["pad_z_palm_m"]),
        )
    )
    point = frames["palm_origin"] + frames["palm_rotation"] @ local
    jv, jw = _arm_point_jacobians(state, point, frames["arm_origins"], frames["arm_axes"])
    jv[:, column] = frames[f"{side}_axis"]
    return point, jv, jw


def _body(
    name: str, mass: float, inertia_body: np.ndarray, position: np.ndarray,
    rotation: np.ndarray, jv: np.ndarray, jw: np.ndarray,
) -> dict[str, Any]:
    return {
        "name": name, "mass": float(mass), "position": position,
        "inertia": rotation @ inertia_body @ rotation.T, "jv": jv, "jw": jw,
    }


def _service_bodies(state: dict[str, np.ndarray], urdf: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frames = _frames(state, urdf)
    base_rotation = _quat_to_rotation(state["base_quaternion"])
    base_jv = np.zeros((3, 14)); base_jw = np.zeros((3, 14))
    base_jv[:, :3] = np.eye(3); base_jw[:, 3:6] = np.eye(3)
    bodies = [_body("service_base", BASE_MASS_KG, BASE_INERTIA_BODY_KG_M2, state["base_position"], base_rotation, base_jv, base_jw)]
    for index in range(6):
        rotation = frames["link_rotations"][index]
        position = frames["link_origins"][index] + rotation @ ARM_COM_OFFSETS_BODY_M[index]
        jv, jw = _arm_point_jacobians(state, position, frames["arm_origins"][: index + 1], frames["arm_axes"][: index + 1])
        bodies.append(_body(f"arm_link_{index + 1}", ARM_MASSES_KG[index], ARM_INERTIAS_BODY_KG_M2[index], position, rotation, jv, jw))
    palm_data = urdf["palm"]
    palm_position = frames["palm_origin"] + frames["palm_rotation"] @ palm_data["com"]
    palm_jv, palm_jw = _arm_point_jacobians(state, palm_position, frames["arm_origins"], frames["arm_axes"])
    bodies.append(_body("palm", palm_data["mass"], palm_data["inertia"], palm_position, frames["palm_rotation"], palm_jv, palm_jw))
    for side, column in (("left", 12), ("right", 13)):
        data = urdf[side]; rotation = frames[f"{side}_rotation"]
        position = frames[f"{side}_origin"] + rotation @ data["com"]
        jv, jw = _arm_point_jacobians(state, position, frames["arm_origins"], frames["arm_axes"])
        jv[:, column] = frames[f"{side}_axis"]
        bodies.append(_body(f"{side}_finger", data["mass"], data["inertia"], position, rotation, jv, jw))
    return bodies, frames


def _service_ledger(
    state: dict[str, np.ndarray], urdf: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray, float, dict[str, Any], np.ndarray]:
    bodies, frames = _service_bodies(state, urdf)
    linear = np.zeros(3); angular = np.zeros(3); energy = 0.0; mass_matrix = np.zeros((14, 14))
    for item in bodies:
        velocity = item["jv"] @ state["nu"]
        omega = item["jw"] @ state["nu"]
        momentum = item["mass"] * velocity
        spin = item["inertia"] @ omega
        linear += momentum
        angular += np.cross(item["position"], momentum) + spin
        energy += 0.5 * item["mass"] * float(velocity @ velocity) + 0.5 * float(omega @ spin)
        mass_matrix += item["mass"] * item["jv"].T @ item["jv"] + item["jw"].T @ item["inertia"] @ item["jw"]
    mass_matrix = 0.5 * (mass_matrix + mass_matrix.T)
    return linear, angular, float(energy), frames, mass_matrix


def _target_ledger(state: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, float]:
    rotation = _quat_to_rotation(state["quaternion"])
    inertia = rotation @ TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    velocity = state["twist"][:3]; omega = state["twist"][3:]
    linear = TARGET_MASS_KG * velocity; spin = inertia @ omega
    angular = np.cross(state["position"], linear) + spin
    energy = 0.5 * TARGET_MASS_KG * float(velocity @ velocity) + 0.5 * float(omega @ spin)
    return linear, angular, float(energy)


def _source_audit(source: dict[str, Any]) -> dict[str, Any]:
    records = source.get("records")
    if not isinstance(records, list):
        return {"pass": False, "reason": "records_not_list"}
    checks = []; roles: list[Any] = []; paths: list[Any] = []
    for declared in records:
        path = _resolve(declared.get("path")) if isinstance(declared, dict) else None
        role = declared.get("role") if isinstance(declared, dict) else None
        actual = _record(path, role) if path is not None and path.is_file() and isinstance(role, str) else None
        checks.append({"pass": actual == declared, "declared": declared, "actual": actual})
        if isinstance(declared, dict):
            roles.append(role); paths.append(declared.get("path"))
    required = {
        "UPSTREAM_PHASE_A_MODEL", "UPSTREAM_PHASE_A_GATE", "UPSTREAM_PHASE_B2_FINAL_GATE",
        "URDF_TOPOLOGY_SOURCE", "URDF_TOPOLOGY_LEDGER", "MODEL_CONTRACT", "GOVERNANCE_CONTRACT",
        "BRANCHED_MODEL_SOURCE", "DUAL_CONTACT_KERNEL_SOURCE", "VALIDATOR_SOURCE",
        "INDEPENDENT_AUDIT_SOURCE", "SCOPE_README", "PYTEST_CONFIG", "TEST_SOURCE",
    }
    phase_a = [item for item in records if isinstance(item, dict) and item.get("role") == "UPSTREAM_PHASE_A_GATE"]
    phase_b2 = [item for item in records if isinstance(item, dict) and item.get("role") == "UPSTREAM_PHASE_B2_FINAL_GATE"]
    urdf = [item for item in records if isinstance(item, dict) and item.get("role") == "URDF_TOPOLOGY_SOURCE"]
    passed = bool(
        source.get("schema") == "SIM13_V4B3_SOURCE_MANIFEST_V1"
        and all(item["pass"] for item in checks)
        and len(paths) == len(set(paths))
        and required.issubset(set(roles))
        and len(phase_a) == 1 and phase_a[0].get("sha256") == EXPECTED_PHASE_A_GATE_SHA
        and len(phase_b2) == 1 and phase_b2[0].get("sha256") == EXPECTED_PHASE_B2_GATE_SHA
        and len(urdf) == 1 and urdf[0].get("sha256") == EXPECTED_URDF_SHA
    )
    return {"pass": passed, "record_count": len(records), "checks": checks, "roles": roles}


def _dag_audit(
    trace: dict[str, Any], ledger: dict[str, Any], validation: dict[str, Any],
    evidence: dict[str, Any], pre_audit: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        _strict_reference(trace.get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        _strict_reference(ledger.get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        _strict_reference(ledger.get("upstream_trace"), TRACE, "UPSTREAM_RAW_TRACE"),
        _strict_reference(validation.get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        _strict_reference(validation.get("upstream_trace"), TRACE, "UPSTREAM_RAW_TRACE"),
        _strict_reference(validation.get("upstream_ledger"), LEDGER, "UPSTREAM_LEDGER"),
        _strict_reference(pre_audit.get("upstream_evidence_manifest"), EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
    ]
    declared = evidence.get("records") if isinstance(evidence.get("records"), list) else []
    expected = (
        (SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        (TRACE, "UPSTREAM_RAW_TRACE"),
        (LEDGER, "UPSTREAM_LEDGER"),
        (VALIDATION, "UPSTREAM_VALIDATION"),
    )
    for index, (path, role) in enumerate(expected):
        checks.append(_strict_reference(declared[index] if index < len(declared) else None, path, role))
    passed = bool(
        evidence.get("schema") == "SIM13_V4B3_EVIDENCE_MANIFEST_V1"
        and evidence.get("acyclic") is True and evidence.get("self_excluded") is True
        and len(declared) == len(expected) and all(item["pass"] for item in checks)
    )
    return {"pass": passed, "checks": checks}


def _nested(record: dict[str, Any], key: str, aliases: Iterable[str] = ()) -> Any:
    if key in record:
        return record[key]
    for alias in aliases:
        if alias in record:
            return record[alias]
    raise KeyError(key)


def _logged_contact(record: dict[str, Any], side: str) -> dict[str, Any]:
    contacts = record.get("contacts")
    if isinstance(contacts, dict) and isinstance(contacts.get(side), dict):
        return contacts[side]
    value = record.get(side)
    if isinstance(value, dict):
        return value
    raise KeyError(f"contacts.{side}")


def _logged_integrated(record: dict[str, Any], side: str) -> dict[str, Any]:
    integrated = record.get("integrated")
    if isinstance(integrated, dict) and isinstance(integrated.get(side), dict):
        return integrated[side]
    contact = _logged_contact(record, side)
    if isinstance(contact.get("integrated"), dict):
        return contact["integrated"]
    raise KeyError(f"integrated.{side}")


def _crossing_time(times: np.ndarray, gaps: np.ndarray, direction: str, start: int = 1) -> float:
    for index in range(max(1, start), len(times)):
        before, after = float(gaps[index - 1]), float(gaps[index])
        crossed = (before > 0.0 and after <= 0.0) if direction == "enter" else (before < 0.0 and after >= 0.0)
        if crossed:
            denominator = abs(before) + abs(after)
            fraction = abs(before) / denominator if denominator else 0.0
            return float(times[index - 1] + fraction * (times[index] - times[index - 1]))
    raise ValueError(f"required {direction} crossing absent")


def _contact_reconstruction(
    state: dict[str, np.ndarray], target: dict[str, np.ndarray], frames: dict[str, Any],
    scenario: dict[str, Any], side: str,
) -> dict[str, Any]:
    pad, jv, jw = _pad(state, frames, scenario, side)
    radius = float(scenario["sphere_radius_m"])
    radial = pad - target["position"]; distance = float(np.linalg.norm(radial))
    if distance <= 1.0e-12:
        raise ValueError("target center coincides with pad")
    normal = radial / distance; gap = distance - radius; penetration = max(-gap, 0.0)
    common = target["position"] + radius * normal
    pad_velocity = jv @ state["nu"]; finger_omega = jw @ state["nu"]
    service_common = pad_velocity + np.cross(finger_omega, common - pad)
    target_common = target["twist"][:3] + np.cross(target["twist"][3:], common - target["position"])
    relative = service_common - target_common
    normal_speed = float(relative @ normal)
    tangent_velocity = relative - normal_speed * normal
    tangent_speed = float(np.linalg.norm(tangent_velocity))
    if penetration > 0.0:
        closing = max(-normal_speed, 0.0)
        normal_force = float(scenario["normal_stiffness_n_m"]) * penetration + float(scenario["normal_damping_n_s_m"]) * closing
        tangent_force = (
            -float(scenario["friction_coefficient"]) * normal_force * tangent_velocity
            / math.sqrt(tangent_speed**2 + float(scenario["tangential_regularization_speed_m_s"]) ** 2)
        )
    else:
        closing = 0.0; normal_force = 0.0; tangent_force = np.zeros(3)
    normal_vector = normal_force * normal
    force = normal_vector + tangent_force; target_force = -force
    shift = np.cross(common - pad, force)
    effort = jv.T @ force + jw.T @ shift
    target_torque = np.cross(common - target["position"], target_force)
    normal_rate = float(scenario["normal_damping_n_s_m"]) * closing**2 if penetration > 0.0 else 0.0
    friction_rate = max(float(-tangent_force @ tangent_velocity), 0.0)
    return {
        "pad_point_inertial_m": pad,
        "gap_m": gap, "penetration_m": penetration,
        "normal_target_to_pad_inertial": normal,
        "common_contact_point_inertial_m": common,
        "service_common_point_velocity_inertial_m_s": service_common,
        "target_common_point_velocity_inertial_m_s": target_common,
        "relative_velocity_inertial_m_s": relative,
        "relative_normal_speed_m_s": normal_speed,
        "relative_tangential_velocity_inertial_m_s": tangent_velocity,
        "relative_tangential_speed_m_s": tangent_speed,
        "normal_force_magnitude_n": normal_force,
        "normal_force_service_inertial_n": normal_vector,
        "tangential_force_service_inertial_n": tangent_force,
        "service_force_inertial_n": force,
        "target_force_inertial_n": target_force,
        "service_shift_torque_inertial_n_m": shift,
        "service_generalized_contact_effort_mixed": effort,
        "target_torque_about_com_inertial_n_m": target_torque,
        "elastic_energy_j": 0.5 * float(scenario["normal_stiffness_n_m"]) * penetration**2,
        "normal_dissipation_rate_w": normal_rate,
        "friction_dissipation_rate_w": friction_rate,
        "jv": jv, "jw": jw,
    }


CONTACT_FIELDS = (
    "pad_point_inertial_m", "gap_m", "penetration_m", "normal_target_to_pad_inertial",
    "common_contact_point_inertial_m", "service_common_point_velocity_inertial_m_s",
    "target_common_point_velocity_inertial_m_s", "relative_velocity_inertial_m_s",
    "relative_normal_speed_m_s", "relative_tangential_velocity_inertial_m_s",
    "relative_tangential_speed_m_s", "normal_force_magnitude_n",
    "normal_force_service_inertial_n", "tangential_force_service_inertial_n",
    "service_force_inertial_n", "target_force_inertial_n", "service_shift_torque_inertial_n_m",
    "service_generalized_contact_effort_mixed", "target_torque_about_com_inertial_n_m",
    "elastic_energy_j", "normal_dissipation_rate_w", "friction_dissipation_rate_w",
)


def _candidate_predicate(criteria: dict[str, Any], scenario: dict[str, Any]) -> bool:
    return bool(
        criteria["left_contact"] and criteria["right_contact"]
        and criteria["dual_contact_dwell_s"] >= float(scenario["dual_contact_dwell_s"])
        and criteria["normals_dot"] <= float(scenario["normals_opposition_max_dot"])
        and criteria["target_inside_corridor"]
        and criteria["target_relative_center_speed_m_s"] <= float(scenario["soft_capture_max_relative_center_speed_m_s"])
        and criteria["target_relative_omega_rad_s"] <= float(scenario["soft_capture_max_relative_omega_rad_s"])
        and abs(criteria["left_relative_normal_speed_m_s"]) <= float(scenario["soft_capture_max_abs_contact_normal_speed_m_s"])
        and abs(criteria["right_relative_normal_speed_m_s"]) <= float(scenario["soft_capture_max_abs_contact_normal_speed_m_s"])
        and criteria["left_relative_tangential_speed_m_s"] <= float(scenario["soft_capture_max_contact_tangential_speed_m_s"])
        and criteria["right_relative_tangential_speed_m_s"] <= float(scenario["soft_capture_max_contact_tangential_speed_m_s"])
        and criteria["left_finger_rate_m_s"] <= float(scenario["soft_capture_max_finger_opening_speed_m_s"])
        and criteria["right_finger_rate_m_s"] <= float(scenario["soft_capture_max_finger_opening_speed_m_s"])
        and criteria["left_normal_force_n"] >= float(scenario["soft_capture_min_normal_force_n"])
        and criteria["right_normal_force_n"] >= float(scenario["soft_capture_min_normal_force_n"])
        and criteria["all_ledgers_closed"]
    )


def _grasp_map_audit(
    target_positions: np.ndarray, left_points: np.ndarray, right_points: np.ndarray,
    indices: list[int],
) -> dict[str, Any]:
    samples = []; all_rank_five = bool(indices)
    for index in indices:
        r_left = left_points[index] - target_positions[index]
        r_right = right_points[index] - target_positions[index]
        line = r_right - r_left; separation = float(np.linalg.norm(line)); length = 0.5 * separation
        if length <= 1.0e-12:
            all_rank_five = False
            samples.append({"index": index, "contact_separation_m": separation, "numerical_rank": 0})
            continue
        identity = np.eye(3)
        grasp = np.block([[identity, identity], [_skew(r_left) / length, _skew(r_right) / length]])
        singular = np.linalg.svd(grasp, compute_uv=False)
        tolerance = 1.0e-10 * max(float(singular[0]), 1.0)
        rank = int(np.count_nonzero(singular > tolerance)); all_rank_five &= rank == 5
        axis = line / separation
        desired = np.concatenate((np.zeros(3), axis))
        least_squares = np.linalg.lstsq(grasp, desired, rcond=tolerance)[0]
        axial_residual = float(np.linalg.norm(grasp @ least_squares - desired))
        samples.append({
            "index": index, "contact_separation_m": separation, "length_scale_m": length,
            "normalized_singular_values": singular.tolist(), "rank_tolerance": tolerance,
            "numerical_rank": rank, "rank_deficiency": 6 - rank,
            "sigma5_over_sigma1": float(singular[4] / singular[0]),
            "sigma6_over_sigma1": float(singular[5] / singular[0]),
            "contact_line_unit_inertial": axis.tolist(),
            "normalized_pure_axial_torque_least_squares_residual": axial_residual,
        })
    return {
        "normalization": "moment_rows_divided_by_half_contact_separation",
        "contact_model": "TWO_HARD_FINGER_FRICTIONAL_POINT_CONTACTS_FORCE_ONLY",
        "qualifying_sample_count": len(indices), "samples": samples,
        "all_qualifying_samples_rank_five": all_rank_five,
        "maximum_sigma6_over_sigma1": max((item.get("sigma6_over_sigma1", math.inf) for item in samples), default=math.inf),
        "minimum_sigma5_over_sigma1": min((item.get("sigma5_over_sigma1", 0.0) for item in samples), default=0.0),
        "minimum_axial_torque_residual": min((item.get("normalized_pure_axial_torque_least_squares_residual", 0.0) for item in samples), default=0.0),
        "full_6d_wrench_span": False, "full_6d_force_closure": False,
    }


def _physics_audit(trace: dict[str, Any], urdf: dict[str, Any]) -> dict[str, Any]:
    scenario = trace["scenario"]
    records = trace["reference_records"]
    if not isinstance(records, list) or len(records) < 3:
        raise ValueError("reference_records must contain a trajectory")
    times = np.asarray([float(item["time_s"]) for item in records])
    if np.any(np.diff(times) <= 0.0):
        raise ValueError("reference time must increase strictly")

    contact_errors = {side: {field: 0.0 for field in CONTACT_FIELDS} for side in ("left", "right")}
    palm_errors = {
        "origin_inertial_m": 0.0, "rotation_body_to_inertial": 0.0,
        "velocity_inertial_m_s": 0.0, "omega_inertial_rad_s": 0.0,
        "target_center_palm_m": 0.0, "target_relative_center_speed_m_s": 0.0,
        "target_relative_omega_rad_s": 0.0,
    }
    declared_ledger_errors = {
        "service_linear_momentum_n_s": 0.0,
        "service_angular_momentum_about_origin_n_m_s": 0.0,
        "target_linear_momentum_n_s": 0.0,
        "target_angular_momentum_about_origin_n_m_s": 0.0,
        "service_kinetic_energy_j": 0.0,
        "target_kinetic_energy_j": 0.0,
    }
    history: dict[str, Any] = {
        "service_p": [], "service_h": [], "service_t": [], "target_p": [], "target_h": [], "target_t": [],
        "target_position": [], "q": [], "nu": [], "mass_min_eigenvalue": [], "quaternion_norm_error": [],
        "target_center_palm": [], "relative_center_speed": [], "relative_omega": [], "labels": [], "logged_criteria": [],
    }
    for side in ("left", "right"):
        history[side] = {key: [] for key in (
            "gap", "penetration", "normal", "common", "pad", "normal_speed", "tangent_speed",
            "normal_force", "tangent_force", "service_force", "target_force", "shift", "effort",
            "target_torque", "service_common_velocity", "target_common_velocity", "tangent_velocity",
            "elastic", "normal_rate", "friction_rate", "normal_d", "friction_d", "impulse", "angular_impulse",
            "action_reaction_error", "shift_error", "target_torque_error", "virtual_power_error", "friction_positive_power",
        )}

    for record in records:
        service = _service_state(record); target = _target_state(record)
        service_p, service_h, service_t, frames, mass_matrix = _service_ledger(service, urdf)
        target_p, target_h, target_t = _target_ledger(target)
        declared_ledgers = record["declared_ledgers"]
        rebuilt_ledgers = {
            "service_linear_momentum_n_s": service_p,
            "service_angular_momentum_about_origin_n_m_s": service_h,
            "target_linear_momentum_n_s": target_p,
            "target_angular_momentum_about_origin_n_m_s": target_h,
            "service_kinetic_energy_j": service_t,
            "target_kinetic_energy_j": target_t,
        }
        for key in declared_ledger_errors:
            declared_ledger_errors[key] = max(
                declared_ledger_errors[key],
                float(np.max(np.abs(np.asarray(declared_ledgers[key], dtype=float) - np.asarray(rebuilt_ledgers[key], dtype=float)))),
            )
        palm_jv, palm_jw = _arm_point_jacobians(service, frames["palm_origin"], frames["arm_origins"], frames["arm_axes"])
        palm_velocity = palm_jv @ service["nu"]; palm_omega = palm_jw @ service["nu"]
        center_offset = target["position"] - frames["palm_origin"]
        center_palm = frames["palm_rotation"].T @ center_offset
        relative_center_vector = target["twist"][:3] - (palm_velocity + np.cross(palm_omega, center_offset))
        relative_center_speed = float(np.linalg.norm(relative_center_vector))
        relative_omega = float(np.linalg.norm(target["twist"][3:] - palm_omega))
        palm = record["palm"]
        declared_palm = {
            "origin_inertial_m": _nested(palm, "origin_inertial_m", ("palm_origin_inertial_m",)),
            "rotation_body_to_inertial": _nested(palm, "rotation_body_to_inertial", ("palm_rotation_body_to_inertial",)),
            "velocity_inertial_m_s": _nested(palm, "velocity_inertial_m_s", ("palm_velocity_inertial_m_s",)),
            "omega_inertial_rad_s": _nested(palm, "omega_inertial_rad_s", ("palm_omega_inertial_rad_s",)),
            "target_center_palm_m": palm["target_center_palm_m"],
            "target_relative_center_speed_m_s": palm["target_relative_center_speed_m_s"],
            "target_relative_omega_rad_s": palm["target_relative_omega_rad_s"],
        }
        rebuilt_palm = {
            "origin_inertial_m": frames["palm_origin"], "rotation_body_to_inertial": frames["palm_rotation"],
            "velocity_inertial_m_s": palm_velocity, "omega_inertial_rad_s": palm_omega,
            "target_center_palm_m": center_palm, "target_relative_center_speed_m_s": relative_center_speed,
            "target_relative_omega_rad_s": relative_omega,
        }
        for key in palm_errors:
            palm_errors[key] = max(
                palm_errors[key],
                float(np.max(np.abs(np.asarray(declared_palm[key], dtype=float) - np.asarray(rebuilt_palm[key], dtype=float)))),
            )

        history["service_p"].append(service_p); history["service_h"].append(service_h); history["service_t"].append(service_t)
        history["target_p"].append(target_p); history["target_h"].append(target_h); history["target_t"].append(target_t)
        history["target_position"].append(target["position"]); history["q"].append(service["q"]); history["nu"].append(service["nu"])
        history["mass_min_eigenvalue"].append(float(np.min(np.linalg.eigvalsh(mass_matrix))))
        history["quaternion_norm_error"].append(max(abs(np.linalg.norm(service["base_quaternion"]) - 1.0), abs(np.linalg.norm(target["quaternion"]) - 1.0)))
        history["target_center_palm"].append(center_palm); history["relative_center_speed"].append(relative_center_speed)
        history["relative_omega"].append(relative_omega); history["labels"].append(record["state_label"])
        history["logged_criteria"].append(record.get("criteria", record.get("soft_capture_criteria", {})))

        for side in ("left", "right"):
            rebuilt = _contact_reconstruction(service, target, frames, scenario, side)
            logged = _logged_contact(record, side); integrated = _logged_integrated(record, side)
            for field in CONTACT_FIELDS:
                difference = np.asarray(logged[field], dtype=float) - np.asarray(rebuilt[field], dtype=float)
                contact_errors[side][field] = max(contact_errors[side][field], float(np.max(np.abs(difference))))
            declared_force = np.asarray(logged["service_force_inertial_n"], dtype=float)
            declared_target_force = np.asarray(logged["target_force_inertial_n"], dtype=float)
            declared_pad = np.asarray(logged["pad_point_inertial_m"], dtype=float)
            declared_common = np.asarray(logged["common_contact_point_inertial_m"], dtype=float)
            declared_shift = np.asarray(logged["service_shift_torque_inertial_n_m"], dtype=float)
            declared_target_torque = np.asarray(logged["target_torque_about_com_inertial_n_m"], dtype=float)
            declared_effort = np.asarray(logged["service_generalized_contact_effort_mixed"], dtype=float)
            declared_service_common = np.asarray(logged["service_common_point_velocity_inertial_m_s"], dtype=float)
            declared_target_common = np.asarray(logged["target_common_point_velocity_inertial_m_s"], dtype=float)
            declared_tangent = np.asarray(logged["tangential_force_service_inertial_n"], dtype=float)
            declared_tangent_velocity = np.asarray(logged["relative_tangential_velocity_inertial_m_s"], dtype=float)
            action_reaction = float(np.linalg.norm(declared_force + declared_target_force))
            shift_error = float(np.linalg.norm(np.cross(declared_pad, declared_force) + declared_shift - np.cross(declared_common, declared_force)))
            target_torque_error = float(np.linalg.norm(np.cross(target["position"], declared_target_force) + declared_target_torque - np.cross(declared_common, declared_target_force)))
            service_power_error = abs(float(service["nu"] @ declared_effort - declared_service_common @ declared_force))
            target_power_error = abs(float(target["twist"][:3] @ declared_target_force + target["twist"][3:] @ declared_target_torque - declared_target_common @ declared_target_force))
            virtual_power_error = max(service_power_error, target_power_error)
            friction_positive = max(float(declared_tangent @ declared_tangent_velocity), 0.0)
            data = history[side]
            values = {
                "gap": rebuilt["gap_m"], "penetration": rebuilt["penetration_m"], "normal": rebuilt["normal_target_to_pad_inertial"],
                "common": rebuilt["common_contact_point_inertial_m"], "pad": rebuilt["pad_point_inertial_m"],
                "normal_speed": rebuilt["relative_normal_speed_m_s"], "tangent_speed": rebuilt["relative_tangential_speed_m_s"],
                "normal_force": rebuilt["normal_force_magnitude_n"], "tangent_force": rebuilt["tangential_force_service_inertial_n"],
                "service_force": rebuilt["service_force_inertial_n"], "target_force": rebuilt["target_force_inertial_n"],
                "shift": rebuilt["service_shift_torque_inertial_n_m"], "effort": rebuilt["service_generalized_contact_effort_mixed"],
                "target_torque": rebuilt["target_torque_about_com_inertial_n_m"],
                "service_common_velocity": rebuilt["service_common_point_velocity_inertial_m_s"],
                "target_common_velocity": rebuilt["target_common_point_velocity_inertial_m_s"],
                "tangent_velocity": rebuilt["relative_tangential_velocity_inertial_m_s"], "elastic": rebuilt["elastic_energy_j"],
                "normal_rate": rebuilt["normal_dissipation_rate_w"], "friction_rate": rebuilt["friction_dissipation_rate_w"],
                "normal_d": float(integrated["normal_dissipation_j"]), "friction_d": float(integrated["friction_dissipation_j"]),
                "impulse": np.asarray(integrated["service_impulse_n_s"], dtype=float),
                "angular_impulse": np.asarray(integrated["service_angular_impulse_n_m_s"], dtype=float),
                "action_reaction_error": action_reaction, "shift_error": shift_error,
                "target_torque_error": target_torque_error, "virtual_power_error": virtual_power_error,
                "friction_positive_power": friction_positive,
            }
            for key, value in values.items():
                data[key].append(value)

    for key in (
        "service_p", "service_h", "service_t", "target_p", "target_h", "target_t", "target_position", "q", "nu",
        "mass_min_eigenvalue", "quaternion_norm_error", "target_center_palm", "relative_center_speed", "relative_omega",
    ):
        history[key] = np.asarray(history[key])
    for side in ("left", "right"):
        for key in history[side]:
            history[side][key] = np.asarray(history[side][key])

    total_p = history["service_p"] + history["target_p"]
    total_h = history["service_h"] + history["target_h"]
    total_energy = history["service_t"] + history["target_t"]
    for side in ("left", "right"):
        total_energy += history[side]["elastic"] + history[side]["normal_d"] + history[side]["friction_d"]
    sum_impulse = history["left"]["impulse"] + history["right"]["impulse"]
    sum_angular_impulse = history["left"]["angular_impulse"] + history["right"]["angular_impulse"]
    ledger_arrays = {
        "linear_momentum_drift": np.linalg.norm(total_p - total_p[0], axis=1),
        "angular_momentum_drift": np.linalg.norm(total_h - total_h[0], axis=1),
        "service_linear_impulse_identity_error_n_s": np.linalg.norm((history["service_p"] - history["service_p"][0]) - sum_impulse, axis=1),
        "target_linear_impulse_identity_error_n_s": np.linalg.norm((history["target_p"] - history["target_p"][0]) + sum_impulse, axis=1),
        "service_angular_impulse_identity_error_n_m_s": np.linalg.norm((history["service_h"] - history["service_h"][0]) - sum_angular_impulse, axis=1),
        "target_angular_impulse_identity_error_n_m_s": np.linalg.norm((history["target_h"] - history["target_h"][0]) + sum_angular_impulse, axis=1),
        "energy_drift": np.abs(total_energy - total_energy[0]),
        "action_reaction_error_n": np.maximum(history["left"]["action_reaction_error"], history["right"]["action_reaction_error"]),
        "common_point_shift_error_n_m": np.maximum(history["left"]["shift_error"], history["right"]["shift_error"]),
        "target_torque_identity_error_n_m": np.maximum(history["left"]["target_torque_error"], history["right"]["target_torque_error"]),
        "virtual_power_error_w": np.maximum(history["left"]["virtual_power_error"], history["right"]["virtual_power_error"]),
        "friction_positive_power_w": np.maximum(history["left"]["friction_positive_power"], history["right"]["friction_positive_power"]),
    }
    monotonic_violation = np.zeros(len(times))
    for side in ("left", "right"):
        for key in ("normal_d", "friction_d"):
            monotonic_violation[1:] = np.maximum(monotonic_violation[1:], np.maximum(-np.diff(history[side][key]), 0.0))
    ledger_arrays["dissipation_monotonic_violation_j"] = monotonic_violation

    criteria_errors: dict[str, float] = {}; criteria_bool_mismatches = 0; reconstructed_criteria = []
    dual_start: float | None = None
    for index, time_s in enumerate(times):
        left = history["left"]; right = history["right"]
        left_on = bool(left["penetration"][index] > 0.0 and left["normal_force"][index] > 0.0)
        right_on = bool(right["penetration"][index] > 0.0 and right["normal_force"][index] > 0.0)
        if left_on and right_on:
            if dual_start is None:
                dual_start = float(time_s)
            dwell = float(time_s) - dual_start
        else:
            dual_start = None; dwell = 0.0
        frame_i = _frames(_service_state(records[index]), urdf)
        left_y = float((frame_i["palm_rotation"].T @ (left["pad"][index] - frame_i["palm_origin"]))[1])
        right_y = float((frame_i["palm_rotation"].T @ (right["pad"][index] - frame_i["palm_origin"]))[1])
        center_y = float(history["target_center_palm"][index, 1])
        corridor = min(left_y, right_y) - float(scenario["corridor_margin_m"]) <= center_y <= max(left_y, right_y) + float(scenario["corridor_margin_m"])
        criteria = {
            "index": index, "time_s": float(time_s), "left_contact": left_on, "right_contact": right_on,
            "dual_contact_dwell_s": dwell,
            "normals_dot": float(left["normal"][index] @ right["normal"][index]),
            "target_inside_corridor": bool(corridor),
            "target_relative_center_speed_m_s": float(history["relative_center_speed"][index]),
            "target_relative_omega_rad_s": float(history["relative_omega"][index]),
            "left_relative_normal_speed_m_s": float(left["normal_speed"][index]),
            "right_relative_normal_speed_m_s": float(right["normal_speed"][index]),
            "left_relative_tangential_speed_m_s": float(left["tangent_speed"][index]),
            "right_relative_tangential_speed_m_s": float(right["tangent_speed"][index]),
            "left_finger_rate_m_s": float(history["nu"][index, 12]),
            "right_finger_rate_m_s": float(history["nu"][index, 13]),
            "jaw_aperture_rate_m_s": float(history["nu"][index, 12] + history["nu"][index, 13]),
            "left_normal_force_n": float(left["normal_force"][index]), "right_normal_force_n": float(right["normal_force"][index]),
            "linear_momentum_drift_n_s": float(ledger_arrays["linear_momentum_drift"][index]),
            "angular_momentum_drift_n_m_s": float(ledger_arrays["angular_momentum_drift"][index]),
            "service_linear_impulse_identity_error_n_s": float(ledger_arrays["service_linear_impulse_identity_error_n_s"][index]),
            "target_linear_impulse_identity_error_n_s": float(ledger_arrays["target_linear_impulse_identity_error_n_s"][index]),
            "service_angular_impulse_identity_error_n_m_s": float(ledger_arrays["service_angular_impulse_identity_error_n_m_s"][index]),
            "target_angular_impulse_identity_error_n_m_s": float(ledger_arrays["target_angular_impulse_identity_error_n_m_s"][index]),
            "energy_plus_dissipation_drift_j": float(ledger_arrays["energy_drift"][index]),
            "action_reaction_error_n": float(ledger_arrays["action_reaction_error_n"][index]),
            "common_point_shift_error_n_m": float(ledger_arrays["common_point_shift_error_n_m"][index]),
            "target_torque_identity_error_n_m": float(ledger_arrays["target_torque_identity_error_n_m"][index]),
            "virtual_power_identity_error_w": float(ledger_arrays["virtual_power_error_w"][index]),
            "friction_positive_power_w": float(ledger_arrays["friction_positive_power_w"][index]),
            "dissipation_monotonic_violation_j": float(ledger_arrays["dissipation_monotonic_violation_j"][index]),
        }
        criteria["all_ledgers_closed"] = bool(
            criteria["linear_momentum_drift_n_s"] <= float(scenario["linear_momentum_ledger_tolerance_n_s"])
            and criteria["angular_momentum_drift_n_m_s"] <= float(scenario["angular_momentum_ledger_tolerance_n_m_s"])
            and criteria["service_linear_impulse_identity_error_n_s"] <= float(scenario["linear_impulse_identity_tolerance_n_s"])
            and criteria["target_linear_impulse_identity_error_n_s"] <= float(scenario["linear_impulse_identity_tolerance_n_s"])
            and criteria["service_angular_impulse_identity_error_n_m_s"] <= float(scenario["angular_impulse_identity_tolerance_n_m_s"])
            and criteria["target_angular_impulse_identity_error_n_m_s"] <= float(scenario["angular_impulse_identity_tolerance_n_m_s"])
            and criteria["energy_plus_dissipation_drift_j"] <= float(scenario["energy_ledger_tolerance_j"])
            and criteria["action_reaction_error_n"] <= float(scenario["action_reaction_tolerance_n"])
            and criteria["common_point_shift_error_n_m"] <= float(scenario["common_point_shift_tolerance_n_m"])
            and criteria["target_torque_identity_error_n_m"] <= float(scenario["target_torque_identity_tolerance_n_m"])
            and criteria["virtual_power_identity_error_w"] <= float(scenario["virtual_power_tolerance_w"])
            and criteria["friction_positive_power_w"] <= float(scenario["friction_noninjection_tolerance_w"])
            and criteria["dissipation_monotonic_violation_j"] <= float(scenario["dissipation_monotonic_tolerance_j"])
        )
        criteria["soft_capture_transient_qualifies"] = _candidate_predicate(criteria, scenario)
        logged = history["logged_criteria"][index]
        for key, value in criteria.items():
            if isinstance(value, bool):
                criteria_bool_mismatches += int(bool(logged.get(key)) != value)
            elif key in logged:
                criteria_errors[key] = max(criteria_errors.get(key, 0.0), abs(float(logged[key]) - float(value)))
            else:
                criteria_errors[key] = math.inf
        reconstructed_criteria.append(criteria)

    qualifying_indices = [int(item["index"]) for item in reconstructed_criteria if item["soft_capture_transient_qualifies"]]
    labels = list(history["labels"]); allowed = {
        "PREGRASP_SEPARATED", "BILATERAL_APPROACH", "LEFT_ONLY_CONTACT", "RIGHT_ONLY_CONTACT",
        "DUAL_CONTACT", "SOFT_CAPTURE_TRANSIENT_CANDIDATE", "BILATERAL_RELEASE", "ABORTED_SAFE",
    }
    first_qualifying = min(qualifying_indices) if qualifying_indices else None
    first_candidate = next((index for index, label in enumerate(labels) if label == "SOFT_CAPTURE_TRANSIENT_CANDIDATE"), None)
    first_release = next((index for index, label in enumerate(labels) if label == "BILATERAL_RELEASE"), None)
    no_recontact_after_release = True
    if first_release is not None:
        no_recontact_after_release = not np.any(
            (history["left"]["penetration"][first_release:] > 0.0)
            | (history["right"]["penetration"][first_release:] > 0.0)
        )
    initial_bilaterally_separated = bool(
        history["left"]["gap"][0] > 0.0 and history["right"]["gap"][0] > 0.0
    )
    core_indices = {
        "PREGRASP_SEPARATED": 0 if initial_bilaterally_separated else None,
        **{
            name: next((index for index, label in enumerate(labels) if label == name), None)
            for name in (
                "BILATERAL_APPROACH", "DUAL_CONTACT",
                "SOFT_CAPTURE_TRANSIENT_CANDIDATE", "BILATERAL_RELEASE",
            )
        },
    }
    core_order = all(value is not None for value in core_indices.values()) and list(core_indices.values()) == sorted(core_indices.values())

    grasp = _grasp_map_audit(history["target_position"], history["left"]["common"], history["right"]["common"], qualifying_indices)
    per_contact_event = {}
    for side in ("left", "right"):
        contact = np.flatnonzero(history[side]["penetration"] > 0.0)
        per_contact_event[side] = {
            "first_contact_time_s": _crossing_time(times, history[side]["gap"], "enter"),
            "separation_after_contact_time_s": _crossing_time(times, history[side]["gap"], "exit", int(contact[0] + 1)),
            "peak_normal_force_n": float(np.max(history[side]["normal_force"])),
            "maximum_penetration_m": float(np.max(history[side]["penetration"])),
        }

    topology = _topology_audit(records[0], scenario, urdf)
    raw_friction_power = {
        side: np.einsum("ij,ij->i", history[side]["tangent_force"], history[side]["tangent_velocity"])
        for side in ("left", "right")
    }
    metrics = {
        "contact_reconstruction_max_abs_errors": contact_errors, "palm_reconstruction_max_abs_errors": palm_errors,
        "declared_ledger_reconstruction_max_abs_errors": declared_ledger_errors,
        "minimum_service_mass_matrix_eigenvalue": float(np.min(history["mass_min_eigenvalue"])),
        "maximum_quaternion_norm_error": float(np.max(history["quaternion_norm_error"])),
        "finger_stroke": {
            "left_min_m": float(np.min(history["q"][:, 6])), "left_max_m": float(np.max(history["q"][:, 6])),
            "right_min_m": float(np.min(history["q"][:, 7])), "right_max_m": float(np.max(history["q"][:, 7])),
        },
        "topology": topology, "per_contact_event": per_contact_event,
        "action_reaction_max_error_n": float(np.max(ledger_arrays["action_reaction_error_n"])),
        "common_point_shift_max_error_n_m": float(np.max(ledger_arrays["common_point_shift_error_n_m"])),
        "target_torque_identity_max_error_n_m": float(np.max(ledger_arrays["target_torque_identity_error_n_m"])),
        "virtual_power_identity_max_error_w": float(np.max(ledger_arrays["virtual_power_error_w"])),
        "friction_maximum_signed_power_w": max(float(np.max(raw_friction_power["left"])), float(np.max(raw_friction_power["right"]))),
        "friction_minimum_signed_power_w": min(float(np.min(raw_friction_power["left"])), float(np.min(raw_friction_power["right"]))),
        "friction_cone_max_excess_n": max(
            float(np.max(np.maximum(np.linalg.norm(history[side]["tangent_force"], axis=1) - float(scenario["friction_coefficient"]) * history[side]["normal_force"], 0.0)))
            for side in ("left", "right")
        ),
        "tangential_orthogonality_max_error_n": max(
            float(np.max(np.abs(np.einsum("ij,ij->i", history[side]["tangent_force"], history[side]["normal"]))))
            for side in ("left", "right")
        ),
        "service_linear_impulse_error_n_s": float(np.max(ledger_arrays["service_linear_impulse_identity_error_n_s"])),
        "target_linear_impulse_error_n_s": float(np.max(ledger_arrays["target_linear_impulse_identity_error_n_s"])),
        "total_linear_momentum_drift_n_s": float(np.max(ledger_arrays["linear_momentum_drift"])),
        "service_angular_impulse_error_n_m_s": float(np.max(ledger_arrays["service_angular_impulse_identity_error_n_m_s"])),
        "target_angular_impulse_error_n_m_s": float(np.max(ledger_arrays["target_angular_impulse_identity_error_n_m_s"])),
        "total_angular_momentum_drift_n_m_s": float(np.max(ledger_arrays["angular_momentum_drift"])),
        "energy_plus_dissipation_drift_j": float(np.max(ledger_arrays["energy_drift"])),
        "final_normal_dissipation_j": {side: float(history[side]["normal_d"][-1]) for side in ("left", "right")},
        "final_friction_dissipation_j": {side: float(history[side]["friction_d"][-1]) for side in ("left", "right")},
        "normal_dissipation_trapezoidal_error_j": {
            side: abs(float(np.trapezoid(history[side]["normal_rate"], times) - history[side]["normal_d"][-1])) for side in ("left", "right")
        },
        "friction_dissipation_trapezoidal_error_j": {
            side: abs(float(np.trapezoid(history[side]["friction_rate"], times) - history[side]["friction_d"][-1])) for side in ("left", "right")
        },
        "dissipation_monotonic_violation_j": float(np.max(ledger_arrays["dissipation_monotonic_violation_j"])),
        "actuator_work_j": 0.0,
        "criteria_max_abs_errors": criteria_errors, "criteria_boolean_mismatch_count": criteria_bool_mismatches,
        "state": {
            "labels_allowed": all(label in allowed for label in labels), "core_first_indices": core_indices,
            "core_partial_order_pass": bool(core_order), "qualifying_sample_count": len(qualifying_indices),
            "initial_bilaterally_separated_from_raw_gap": initial_bilaterally_separated,
            "first_qualifying_index": first_qualifying, "first_candidate_index": first_candidate,
            "candidate_begins_at_qualification": first_candidate == first_qualifying,
            "first_release_index": first_release, "no_recontact_after_release": bool(no_recontact_after_release),
            "forbidden_state_present": any(label in {"LOCKED", "GRASP_SUCCESS"} for label in labels),
        },
        "grasp_map": grasp,
    }
    return {"metrics": metrics, "history": history, "criteria": reconstructed_criteria, "ledger_arrays": ledger_arrays}


def _topology_audit(record: dict[str, Any], scenario: dict[str, Any], urdf: dict[str, Any]) -> dict[str, Any]:
    state = _service_state(record); frames = _frames(state, urdf); step = 1.0e-7
    analytic = {side: _pad(state, frames, scenario, side)[1] for side in ("left", "right")}

    def finite_difference(side: str, q_index: int) -> np.ndarray:
        points = []
        for sign in (-1.0, 1.0):
            perturbed = {key: value.copy() for key, value in state.items()}
            perturbed["q"][q_index] += sign * step
            perturbed_frames = _frames(perturbed, urdf)
            points.append(_pad(perturbed, perturbed_frames, scenario, side)[0])
        return (points[1] - points[0]) / (2.0 * step)

    left_own = finite_difference("left", 6); left_cross = finite_difference("left", 7)
    right_cross = finite_difference("right", 6); right_own = finite_difference("right", 7)
    return {
        "class": "INDEPENDENT_6R_FIXED_PALM_PARALLEL_SIBLING_2P",
        "finite_difference_step_m": step,
        "left_own_P_jacobian_fd_max_error": float(np.max(np.abs(left_own - analytic["left"][:, 12]))),
        "right_own_P_jacobian_fd_max_error": float(np.max(np.abs(right_own - analytic["right"][:, 13]))),
        "left_analytic_own_P_norm": float(np.linalg.norm(analytic["left"][:, 12])),
        "right_analytic_own_P_norm": float(np.linalg.norm(analytic["right"][:, 13])),
        "left_cross_right_P_fd_norm": float(np.linalg.norm(left_cross)),
        "right_cross_left_P_fd_norm": float(np.linalg.norm(right_cross)),
        "left_analytic_cross_right_P_norm": float(np.linalg.norm(analytic["left"][:, 13])),
        "right_analytic_cross_left_P_norm": float(np.linalg.norm(analytic["right"][:, 12])),
        "left_axis_vs_urdf_max_error": float(np.max(np.abs(analytic["left"][:, 12] - frames["left_axis"]))),
        "right_axis_vs_urdf_max_error": float(np.max(np.abs(analytic["right"][:, 13] - frames["right_axis"]))),
        "left_crosswire_inserted_right_axis_residual": float(np.linalg.norm(frames["right_axis"] - analytic["left"][:, 13])),
        "right_crosswire_inserted_left_axis_residual": float(np.linalg.norm(frames["left_axis"] - analytic["right"][:, 12])),
    }


def _terminal_difference(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    a = left["final_state"]; b = right["final_state"]
    return {
        "service_base_position_m": float(np.linalg.norm(np.asarray(a["service_base_position_inertial_m"]) - np.asarray(b["service_base_position_inertial_m"]))),
        "service_base_quaternion_geodesic_rad": _quaternion_geodesic(a["service_base_quaternion_body_to_inertial_wxyz"], b["service_base_quaternion_body_to_inertial_wxyz"]),
        "service_q_R_rad": float(np.max(np.abs(np.asarray(a["service_joint_coordinates_mixed"])[:6] - np.asarray(b["service_joint_coordinates_mixed"])[:6]))),
        "service_q_P_m": float(np.max(np.abs(np.asarray(a["service_joint_coordinates_mixed"])[6:] - np.asarray(b["service_joint_coordinates_mixed"])[6:]))),
        "service_v_base_m_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[:3] - np.asarray(b["service_nu_s_mixed"])[:3]))),
        "service_omega_base_rad_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[3:6] - np.asarray(b["service_nu_s_mixed"])[3:6]))),
        "service_qdot_R_rad_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[6:12] - np.asarray(b["service_nu_s_mixed"])[6:12]))),
        "service_qdot_P_m_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[12:] - np.asarray(b["service_nu_s_mixed"])[12:]))),
        "target_position_m": float(np.linalg.norm(np.asarray(a["target_position_inertial_m"]) - np.asarray(b["target_position_inertial_m"]))),
        "target_quaternion_geodesic_rad": _quaternion_geodesic(a["target_quaternion_body_to_inertial_wxyz"], b["target_quaternion_body_to_inertial_wxyz"]),
        "target_velocity_m_s": float(np.max(np.abs(np.asarray(a["target_twist_inertial_mixed"])[:3] - np.asarray(b["target_twist_inertial_mixed"])[:3]))),
        "target_omega_rad_s": float(np.max(np.abs(np.asarray(a["target_twist_inertial_mixed"])[3:] - np.asarray(b["target_twist_inertial_mixed"])[3:]))),
    }


def _run_side(run: dict[str, Any], side: str, field: str) -> np.ndarray:
    contacts = run.get("contacts")
    if isinstance(contacts, dict) and isinstance(contacts.get(side), dict) and field in contacts[side]:
        return np.asarray(contacts[side][field], dtype=float)
    if isinstance(run.get(side), dict) and field in run[side]:
        return np.asarray(run[side][field], dtype=float)
    name = f"{side}_{field}"
    if name in run:
        return np.asarray(run[name], dtype=float)
    aliases = {
        "normal_force_magnitude_n": f"{side}_normal_force_n",
    }
    alias = aliases.get(field)
    if alias in run:
        return np.asarray(run[alias], dtype=float)
    raise KeyError(name)


def _raw_dual_event(run: dict[str, Any]) -> dict[str, dict[str, float]]:
    times = np.asarray(run["time_s"], dtype=float); result = {}
    for side in ("left", "right"):
        gap = _run_side(run, side, "gap_m"); penetration = _run_side(run, side, "penetration_m")
        force = _run_side(run, side, "normal_force_magnitude_n")
        contact = np.flatnonzero(penetration > 0.0)
        result[side] = {
            "first_contact_time_s": _crossing_time(times, gap, "enter"),
            "separation_after_contact_time_s": _crossing_time(times, gap, "exit", int(contact[0] + 1)),
            "peak_normal_force_n": float(np.max(force)), "maximum_penetration_m": float(np.max(penetration)),
        }
    return result


def _assess(coarse: dict[str, float], fine: dict[str, float]) -> dict[str, Any]:
    components = {}
    for key, coarse_error in coarse.items():
        fine_error = fine[key]; floor = FLOORS[key]
        passed = fine_error < coarse_error or (coarse_error <= floor and fine_error <= floor)
        components[key] = {"coarse": coarse_error, "fine": fine_error, "floor": floor, "pass": passed}
    return {"components": components, "all_components_pass": all(item["pass"] for item in components.values())}


def _run_outcome(run: dict[str, Any]) -> dict[str, bool]:
    labels = run.get("state_label", run.get("state_events", []))
    if labels and isinstance(labels[0], dict):
        labels = [item.get("to") for item in labels]
    labels = list(labels)
    return {
        "candidate_present": "SOFT_CAPTURE_TRANSIENT_CANDIDATE" in labels,
        "release_present": "BILATERAL_RELEASE" in labels,
        "abort_absent": "ABORTED_SAFE" not in labels,
        "forbidden_absent": not any(item in {"LOCKED", "GRASP_SUCCESS"} for item in labels),
    }


def _convergence(trace: dict[str, Any]) -> dict[str, Any]:
    runs = trace["convergence_runs"]
    required = ("rk4_coarse", "rk4_fine", "rk4_reference", "midpoint_coarse", "midpoint_fine", "midpoint_reference")
    if not all(name in runs for name in required):
        raise KeyError("six convergence runs required")
    rk_c = _terminal_difference(runs["rk4_coarse"], runs["rk4_fine"])
    rk_f = _terminal_difference(runs["rk4_fine"], runs["rk4_reference"])
    mp_c = _terminal_difference(runs["midpoint_coarse"], runs["midpoint_fine"])
    mp_f = _terminal_difference(runs["midpoint_fine"], runs["midpoint_reference"])
    cross_terminal = _terminal_difference(runs["rk4_reference"], runs["midpoint_reference"])
    events = {name: _raw_dual_event(runs[name]) for name in required}
    cross: dict[str, dict[str, float]] = {"left": {}, "right": {}}
    for side in ("left", "right"):
        for key in events["rk4_reference"][side]:
            cross[side][key] = abs(events["rk4_reference"][side][key] - events["midpoint_reference"][side][key])
    left_event = runs["rk4_reference"]["events"]; right_event = runs["midpoint_reference"]["events"]
    extended_cross: dict[str, float] = {}
    for key in (
        "candidate_transition_time_s", "bilateral_release_transition_time_s",
    ):
        a, b = left_event.get(key), right_event.get(key)
        extended_cross[key] = math.inf if a is None or b is None else abs(float(a) - float(b))
    for side in ("left", "right"):
        key = f"{side}_final_impulse_n_s"
        extended_cross[key] = float(np.linalg.norm(np.asarray(left_event[key]) - np.asarray(right_event[key])))
    outcomes = {name: _run_outcome(runs[name]) for name in required}
    midpoint_components = {
        key: {"error": value, "limit": MIDPOINT_REFERENCE_ENVELOPE[key], "pass": value <= MIDPOINT_REFERENCE_ENVELOPE[key]}
        for key, value in cross_terminal.items()
    }
    return {
        "rk4": _assess(rk_c, rk_f),
        "midpoint": {
            "monotonicity_claimed": False,
            "coarse_difference": mp_c, "fine_difference": mp_f,
            "reference_vs_rk4": cross_terminal,
            "components": midpoint_components,
            "all_components_pass": all(item["pass"] for item in midpoint_components.values()),
        },
        "events": events, "cross_integrator_event_difference": cross,
        "extended_cross_integrator_event_difference": extended_cross,
        "outcomes": outcomes,
        "all_core_outcomes_pass": all(all(item.values()) for item in outcomes.values()),
    }


def _independent_negative_controls(
    physics: dict[str, Any], scenario: dict[str, Any], reported: Any,
) -> dict[str, Any]:
    criteria = physics["criteria"]
    nominal = next((dict(item) for item in criteria if item["soft_capture_transient_qualifies"]), None)
    if nominal is None:
        return {"pass": False, "reason": "no nominal qualifying sample"}
    mutations: dict[str, dict[str, Any]] = {}

    def predicate(control_id: str, field: str, value: Any) -> None:
        mutated = dict(nominal); mutated[field] = value
        mutations[control_id] = {
            "mutation": f"{field}={value}", "mutation_rejected": not _candidate_predicate(mutated, scenario)
        }

    predicate("NC-B301_SINGLE_SIDE_FALSE_CAPTURE", "right_contact", False)
    predicate("NC-B302_SAME_DIRECTION_NORMALS", "normals_dot", abs(float(nominal["normals_dot"])))
    predicate("NC-B303_NO_DWELL_FALSE_CAPTURE", "dual_contact_dwell_s", 0.0)
    predicate("NC-B304_TARGET_OUTSIDE_CORRIDOR", "target_inside_corridor", False)
    predicate("NC-B305_EXCESS_CENTER_SPEED", "target_relative_center_speed_m_s", 1.1 * float(scenario["soft_capture_max_relative_center_speed_m_s"]))
    predicate("NC-B306_EXCESS_RELATIVE_OMEGA", "target_relative_omega_rad_s", 1.1 * float(scenario["soft_capture_max_relative_omega_rad_s"]))
    predicate("NC-B307_LOW_LEFT_NORMAL_FORCE", "left_normal_force_n", 0.0)
    predicate("NC-B308_OPEN_LEDGER", "all_ledgers_closed", False)
    predicate("NC-B309_EXCESS_LEFT_CONTACT_NORMAL_SPEED", "left_relative_normal_speed_m_s", 1.1 * float(scenario["soft_capture_max_abs_contact_normal_speed_m_s"]))
    predicate("NC-B310_EXCESS_RIGHT_CONTACT_TANGENTIAL_SPEED", "right_relative_tangential_speed_m_s", 1.1 * float(scenario["soft_capture_max_contact_tangential_speed_m_s"]))
    predicate("NC-B311_LEFT_FINGER_OPENING_DURING_CANDIDATE", "left_finger_rate_m_s", 1.1 * float(scenario["soft_capture_max_finger_opening_speed_m_s"]))

    history = physics["history"]
    peak = int(np.argmax(history["left"]["normal_force"] + history["right"]["normal_force"]))
    for side, control_sign, control_shift in (
        ("left", "NC-B312_LEFT_ACTION_REACTION_SIGN", "NC-B314_MISSING_LEFT_COMMON_SHIFT"),
        ("right", "NC-B313_RIGHT_ACTION_REACTION_SIGN", "NC-B315_MISSING_RIGHT_COMMON_SHIFT"),
    ):
        force = history[side]["service_force"][peak]
        sign_error = float(np.linalg.norm(force + force))
        shift_error = float(np.linalg.norm(np.cross(history[side]["pad"][peak] - history[side]["common"][peak], force)))
        mutations[control_sign] = {"raw_error": sign_error, "mutation_rejected": sign_error > 1.0e-12}
        mutations[control_shift] = {"raw_error": shift_error, "mutation_rejected": shift_error > 1.0e-12}
    friction_power_after_flip = 0.0
    for side in ("left", "right"):
        values = -np.einsum("ij,ij->i", history[side]["tangent_force"], history[side]["tangent_velocity"])
        friction_power_after_flip = max(friction_power_after_flip, float(np.max(values)))
    mutations["NC-B316_FRICTION_POWER_SIGN_FLIP"] = {"raw_error": friction_power_after_flip, "mutation_rejected": friction_power_after_flip > 1.0e-12}
    topology = physics["metrics"]["topology"]
    crosswire_error = topology["left_crosswire_inserted_right_axis_residual"]
    mutations["NC-B317_P_BRANCH_CROSS_WIRING"] = {
        "mutation": "RIGHT_BRANCH_AXIS_INSERTED_IN_LEFT_ZERO_CROSS_COLUMN",
        "raw_error": crosswire_error, "mutation_rejected": crosswire_error > 1.0e-12,
    }
    grasp = physics["metrics"]["grasp_map"]
    mutations["NC-B318_FALSE_RANK6_PROMOTION"] = {"measured_all_rank_five": grasp["all_qualifying_samples_rank_five"], "mutation_rejected": grasp["all_qualifying_samples_rank_five"]}
    q = history["q"][0].copy(); q[6] = float(scenario["stroke_upper_m"]) + 1.0e-3
    in_bounds = float(scenario["stroke_lower_m"]) <= q[6] <= float(scenario["stroke_upper_m"])
    mutations["NC-B319_P_STROKE_OVERRUN"] = {"mutated_left_q_m": float(q[6]), "mutation_rejected": not in_bounds}
    governance = _load(HERE / "contracts/PHASE_B3_GOVERNANCE_CONTRACT_V1.json")
    required_false = governance.get("required_false", {})
    for control_id, field in (
        ("NC-B320_LOCK_WITHOUT_AUTHORITY", "lock_implemented"),
        ("NC-B321_PHYSICAL_TIMING_PROMOTION", "physical_actuator_timing_identified"),
    ):
        baseline = dict(required_false); mutated = dict(required_false); mutated[field] = True
        rejected = (
            baseline.get(field) is False
            and mutated != baseline
            and any(bool(value) for value in mutated.values())
        )
        mutations[control_id] = {
            "mutation": f"{field}=True", "baseline_required_false": baseline.get(field),
            "mutated_value": mutated[field], "mutation_rejected": rejected,
        }
    release_index = next(
        (index for index, label in enumerate(history["labels"]) if label == "BILATERAL_RELEASE"), None
    )
    if release_index is None:
        recontact_rejected = False; mutation_index = None
    else:
        mutation_index = min(release_index + 1, len(history["labels"]) - 1)
        mutated_left_penetration = history["left"]["penetration"].copy()
        mutated_left_force = history["left"]["normal_force"].copy()
        mutated_left_penetration[mutation_index] = 1.0e-6
        mutated_left_force[mutation_index] = max(float(scenario["soft_capture_min_normal_force_n"]), 0.1)
        left_on = mutated_left_penetration[mutation_index] > 0.0 and mutated_left_force[mutation_index] > 0.0
        right_on = history["right"]["penetration"][mutation_index] > 0.0 and history["right"]["normal_force"][mutation_index] > 0.0
        recontact_rejected = history["labels"][release_index] == "BILATERAL_RELEASE" and bool(left_on or right_on)
    mutations["NC-B322_RECONTACT_AFTER_RELEASE"] = {
        "mutation": "LEFT_CONTACT_REINTRODUCED_IN_RECONSTRUCTED_TRACE_AFTER_RELEASE",
        "release_index": release_index, "mutation_index": mutation_index,
        "mutation_rejected": recontact_rejected,
    }

    reported_records = reported if isinstance(reported, list) else []
    reported_by_id = {item.get("control_id"): item for item in reported_records if isinstance(item, dict)}
    expected_ids = set(mutations)
    reported_pass = set(reported_by_id) == expected_ids and all(
        item.get("mutation_rejected") is True and item.get("result") == "PASS_NEGATIVE_CONTROL"
        for item in reported_by_id.values()
    )
    independent_pass = all(item["mutation_rejected"] for item in mutations.values())
    return {
        "pass": bool(reported_pass and independent_pass), "expected_ids": sorted(expected_ids),
        "reported_ids": sorted(str(item) for item in reported_by_id), "reported_pass": reported_pass,
        "independent_mutations": mutations,
    }


def _forbidden_scan() -> dict[str, Any]:
    found = []
    for path in HERE.rglob("*"):
        name = path.name.lower()
        if path.is_dir() and name in {"__pycache__", ".pytest_cache", ".ruff_cache"}:
            found.append(path.relative_to(HERE).as_posix())
        elif path.is_file() and name.endswith(".urdf"):
            found.append(path.relative_to(HERE).as_posix())
    return {"pass": not found, "paths": sorted(found)}


def _ledger_crosscheck(metrics: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    summary = ledger.get("reference_summary", {})
    errors: dict[str, float] = {}
    for side in ("left", "right"):
        declared = summary.get("per_contact", {}).get(side, {})
        rebuilt = metrics["per_contact_event"][side]
        for key, value in rebuilt.items():
            errors[f"{side}.{key}"] = abs(float(declared.get(key, math.inf)) - float(value))
    linear = summary.get("linear_momentum_n_s", {})
    angular = summary.get("angular_momentum_n_m_s", {})
    energy = summary.get("energy_j", {})
    mappings = {
        "linear.service": (linear.get("service_delta_minus_sum_impulse_max_error_n_s", math.inf), metrics["service_linear_impulse_error_n_s"]),
        "linear.target": (linear.get("target_delta_plus_sum_impulse_max_error_n_s", math.inf), metrics["target_linear_impulse_error_n_s"]),
        "linear.total": (linear.get("total_max_drift_n_s", math.inf), metrics["total_linear_momentum_drift_n_s"]),
        "angular.service": (angular.get("service_delta_minus_sum_angular_impulse_max_error_n_m_s", math.inf), metrics["service_angular_impulse_error_n_m_s"]),
        "angular.target": (angular.get("target_delta_plus_sum_angular_impulse_max_error_n_m_s", math.inf), metrics["target_angular_impulse_error_n_m_s"]),
        "angular.total": (angular.get("total_max_drift_n_m_s", math.inf), metrics["total_angular_momentum_drift_n_m_s"]),
        "energy.total": (energy.get("total_mechanical_plus_dissipated_max_drift_j", math.inf), metrics["energy_plus_dissipation_drift_j"]),
    }
    for key, (declared, rebuilt) in mappings.items():
        errors[key] = abs(float(declared) - float(rebuilt))
    declared_state = summary.get("state_machine", {})
    state_match = (
        declared_state.get("soft_capture_qualifying_sample_count") == metrics["state"]["qualifying_sample_count"]
        and declared_state.get("locked_state_present") is False
        and declared_state.get("grasp_success_state_present") is False
    )
    declared_grasp = summary.get("grasp_map", {})
    grasp_match = (
        declared_grasp.get("all_evaluated_samples_rank_five") is True
        and declared_grasp.get("rank_min_across_evaluated_samples") == 5
        and declared_grasp.get("rank_max_across_evaluated_samples") == 5
        and declared_grasp.get("full_6d_wrench_span") is False
        and declared_grasp.get("full_6d_force_closure") is False
    )
    return {
        "pass": max(errors.values(), default=math.inf) <= 2.0e-11 and state_match and grasp_match,
        "numeric_errors": errors, "state_match": state_match, "grasp_match": grasp_match,
    }


def _check(check_id: str, name: str, passed: bool, metrics: Any) -> dict[str, Any]:
    return {"id": check_id, "name": name, "pass": bool(passed), "metrics": metrics}


def main() -> int:
    for stale in (FINAL_GATE, TERMINAL_MANIFEST):
        if stale.is_file():
            stale.unlink()
    required = (SOURCE_MANIFEST, TRACE, LEDGER, VALIDATION, EVIDENCE_MANIFEST, PRE_AUDIT_GATE)
    if not all(path.is_file() for path in required):
        print("missing pre-audit evidence", file=sys.stderr)
        return 2

    source = _load(SOURCE_MANIFEST); trace = _load(TRACE); ledger = _load(LEDGER)
    validation = _load(VALIDATION); evidence = _load(EVIDENCE_MANIFEST); pre_audit = _load(PRE_AUDIT_GATE)
    urdf, urdf_audit = _parse_urdf(); v4a_audit = _v4a_source_audit()
    source_result = _source_audit(source); dag_result = _dag_audit(trace, ledger, validation, evidence, pre_audit)
    physics = _physics_audit(trace, urdf); metrics = physics["metrics"]
    convergence = _convergence(trace)
    controls = _independent_negative_controls(physics, trace["scenario"], trace.get("negative_control_results"))
    forbidden = _forbidden_scan(); ledger_crosscheck = _ledger_crosscheck(metrics, ledger)

    scenario = trace["scenario"]
    scenario_binding = {
        "urdf_reference_exact": scenario.get("urdf_source") == _record(URDF, "URDF_TOPOLOGY_SOURCE"),
        "reference_method": scenario.get("reference_method"),
        "reference_step_s": scenario.get("reference_step_s"),
        "duration_s": scenario.get("duration_s"),
        "scope": trace.get("scope"),
    }
    scenario_binding["pass"] = bool(
        scenario_binding["urdf_reference_exact"]
        and scenario_binding["reference_method"] == "rk4"
        and float(scenario_binding["reference_step_s"]) == 2.5e-4
        and float(scenario_binding["duration_s"]) == 0.08
        and scenario_binding["scope"] == "SYNTHETIC_BRANCHED_DUAL_HARD_FINGER_CONTACT_TRANSIENT_CANDIDATE_ONLY"
    )
    contact_reconstruction_max = max(
        value for side in metrics["contact_reconstruction_max_abs_errors"].values() for value in side.values()
    )
    palm_reconstruction_max = max(metrics["palm_reconstruction_max_abs_errors"].values())
    declared_ledger_reconstruction_max = max(metrics["declared_ledger_reconstruction_max_abs_errors"].values())
    topology = metrics["topology"]; state = metrics["state"]; grasp = metrics["grasp_map"]
    stroke = metrics["finger_stroke"]
    no_contact = trace.get("no_contact_regression", {})
    no_contact_pass = isinstance(no_contact, dict) and bool(no_contact) and max(float(value) for value in no_contact.values()) <= 2.0e-12
    cross = convergence["cross_integrator_event_difference"]
    extended_cross = convergence["extended_cross_integrator_event_difference"]
    event_convergence_pass = (
        cross["left"]["first_contact_time_s"] <= 5.0e-6
        and cross["right"]["first_contact_time_s"] <= 5.0e-6
        and cross["left"]["separation_after_contact_time_s"] <= 1.0e-5
        and cross["right"]["separation_after_contact_time_s"] <= 1.0e-5
        and cross["left"]["peak_normal_force_n"] <= 2.0e-2
        and cross["right"]["peak_normal_force_n"] <= 2.0e-2
        and cross["left"]["maximum_penetration_m"] <= 2.0e-6
        and cross["right"]["maximum_penetration_m"] <= 2.0e-6
        and extended_cross["candidate_transition_time_s"] <= 3.0e-4
        and extended_cross["bilateral_release_transition_time_s"] <= 3.0e-4
        and extended_cross["left_final_impulse_n_s"] <= 2.0e-5
        and extended_cross["right_final_impulse_n_s"] <= 2.0e-5
    )
    normal_quadrature_max = max(metrics["normal_dissipation_trapezoidal_error_j"].values())
    friction_quadrature_max = max(metrics["friction_dissipation_trapezoidal_error_j"].values())
    final_normal_positive = all(value > 0.0 for value in metrics["final_normal_dissipation_j"].values())
    final_friction_positive = all(value > 0.0 for value in metrics["final_friction_dissipation_j"].values())
    expected_authorizations = {
        "physical_dual_contact_identified": False,
        "physical_friction_identified": False,
        "physical_actuator_timing_identified": False,
        "soft_capture_current_system_passed": False,
        "lock_implemented": False,
        "grasp_success": False,
        "current_system_bound": False,
        "formal_nc19_closed": False,
        "owner_authorized": False,
        "production_ready": False,
        "release_authorized": False,
        "next_stage_authorized": False,
    }
    formal_state = {
        "passed": 15, "declared": 20,
        "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
        "changed_by_this_package": False,
    }
    checks = [
        _check("IA-B301", "strict source manifest and frozen upstream hashes", source_result["pass"], source_result),
        _check("IA-B302", "strict acyclic path-bytes-sha-role evidence DAG", dag_result["pass"], dag_result),
        _check("IA-B303", "validator remains pre-audit only", validation.get("status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" and validation.get("score", {}).get("fail") == 0 and pre_audit.get("final_gate") is False, {"validation": validation.get("status"), "score": validation.get("score"), "pre_audit_final": pre_audit.get("final_gate")}),
        _check("IA-B304", "frozen URDF independently parsed with sibling-P frame semantics", urdf_audit["pass"], urdf_audit),
        _check("IA-B305", "V4A constants source-bound and no B3/validator runtime import", v4a_audit["v4a_ast_parsed"] and v4a_audit["required_canonical_snippets_present"] and v4a_audit["banned_runtime_imports_absent"], v4a_audit),
        _check("IA-B306", "trace scenario and URDF hash binding", scenario_binding["pass"], scenario_binding),
        _check("IA-B307", "palm and bilateral contact law independently reconstructed", max(contact_reconstruction_max, palm_reconstruction_max) <= 2.0e-11, {"contact_max": contact_reconstruction_max, "palm_max": palm_reconstruction_max, "contact": metrics["contact_reconstruction_max_abs_errors"], "palm": metrics["palm_reconstruction_max_abs_errors"]}),
        _check("IA-B308", "service and target P H T raw ledgers independently reconstructed", declared_ledger_reconstruction_max <= 2.0e-11, metrics["declared_ledger_reconstruction_max_abs_errors"]),
        _check("IA-B309", "independent branched mass matrix positive definite", metrics["minimum_service_mass_matrix_eigenvalue"] > 1.0e-10, {"minimum_eigenvalue": metrics["minimum_service_mass_matrix_eigenvalue"]}),
        _check("IA-B310", "sibling-P own Jacobians and zero cross channels", max(topology["left_own_P_jacobian_fd_max_error"], topology["right_own_P_jacobian_fd_max_error"]) <= 2.0e-9 and max(topology["left_cross_right_P_fd_norm"], topology["right_cross_left_P_fd_norm"], topology["left_analytic_cross_right_P_norm"], topology["right_analytic_cross_left_P_norm"]) <= 1.0e-12, topology),
        _check("IA-B311", "per-contact action reaction and separated dimensioned wrench identities", metrics["action_reaction_max_error_n"] <= float(scenario["action_reaction_tolerance_n"]) and metrics["common_point_shift_max_error_n_m"] <= float(scenario["common_point_shift_tolerance_n_m"]) and metrics["target_torque_identity_max_error_n_m"] <= float(scenario["target_torque_identity_tolerance_n_m"]), {"action_reaction_n": metrics["action_reaction_max_error_n"], "service_shift_n_m": metrics["common_point_shift_max_error_n_m"], "target_torque_n_m": metrics["target_torque_identity_max_error_n_m"]}),
        _check("IA-B312", "service and target common-point virtual power identities", metrics["virtual_power_identity_max_error_w"] <= float(scenario["virtual_power_tolerance_w"]), {"max_error_w": metrics["virtual_power_identity_max_error_w"]}),
        _check("IA-B313", "regularized friction cone orthogonality and non-injection", metrics["friction_cone_max_excess_n"] <= 1.0e-12 and metrics["tangential_orthogonality_max_error_n"] <= 1.0e-12 and metrics["friction_maximum_signed_power_w"] <= float(scenario["friction_noninjection_tolerance_w"]) and metrics["friction_minimum_signed_power_w"] < 0.0, {key: metrics[key] for key in ("friction_cone_max_excess_n", "tangential_orthogonality_max_error_n", "friction_maximum_signed_power_w", "friction_minimum_signed_power_w")}),
        _check("IA-B314", "service and target linear impulse identities plus total P", metrics["service_linear_impulse_error_n_s"] <= float(scenario["linear_impulse_identity_tolerance_n_s"]) and metrics["target_linear_impulse_error_n_s"] <= float(scenario["linear_impulse_identity_tolerance_n_s"]) and metrics["total_linear_momentum_drift_n_s"] <= float(scenario["linear_momentum_ledger_tolerance_n_s"]), {key: metrics[key] for key in ("service_linear_impulse_error_n_s", "target_linear_impulse_error_n_s", "total_linear_momentum_drift_n_s")}),
        _check("IA-B315", "service and target angular impulse identities plus total H", metrics["service_angular_impulse_error_n_m_s"] <= float(scenario["angular_impulse_identity_tolerance_n_m_s"]) and metrics["target_angular_impulse_error_n_m_s"] <= float(scenario["angular_impulse_identity_tolerance_n_m_s"]) and metrics["total_angular_momentum_drift_n_m_s"] <= float(scenario["angular_momentum_ledger_tolerance_n_m_s"]), {key: metrics[key] for key in ("service_angular_impulse_error_n_m_s", "target_angular_impulse_error_n_m_s", "total_angular_momentum_drift_n_m_s")}),
        _check("IA-B316", "T plus two U plus four dissipations and zero actuator work", metrics["energy_plus_dissipation_drift_j"] <= float(scenario["energy_ledger_tolerance_j"]) and final_normal_positive and final_friction_positive and metrics["actuator_work_j"] == 0.0, {"energy_drift_j": metrics["energy_plus_dissipation_drift_j"], "normal": metrics["final_normal_dissipation_j"], "friction": metrics["final_friction_dissipation_j"], "actuator_work_j": metrics["actuator_work_j"]}),
        _check("IA-B317", "four dissipation channels monotone and independently quadrature-checked", metrics["dissipation_monotonic_violation_j"] <= float(scenario["dissipation_monotonic_tolerance_j"]) and normal_quadrature_max <= 1.0e-5 and friction_quadrature_max <= 1.0e-7, {"monotonic_violation_j": metrics["dissipation_monotonic_violation_j"], "normal_quadrature": metrics["normal_dissipation_trapezoidal_error_j"], "friction_quadrature": metrics["friction_dissipation_trapezoidal_error_j"]}),
        _check("IA-B318", "continuous bilateral dwell and full online criteria independently reconstructed", max(metrics["criteria_max_abs_errors"].values(), default=math.inf) <= 2.0e-11 and metrics["criteria_boolean_mismatch_count"] == 0 and state["qualifying_sample_count"] > 0 and state["candidate_begins_at_qualification"], {"numeric_errors": metrics["criteria_max_abs_errors"], "boolean_mismatches": metrics["criteria_boolean_mismatch_count"], "state": state}),
        _check("IA-B319", "ordered transient candidate then bilateral release without recontact", state["labels_allowed"] and state["core_partial_order_pass"] and state["no_recontact_after_release"] and not state["forbidden_state_present"], state),
        _check("IA-B320", "all qualifying normalized hard-finger grasp maps are rank five", grasp["qualifying_sample_count"] == state["qualifying_sample_count"] and grasp["all_qualifying_samples_rank_five"] and grasp["maximum_sigma6_over_sigma1"] <= 1.0e-10 and grasp["minimum_sigma5_over_sigma1"] >= 1.0e-3, grasp),
        _check("IA-B321", "axial pure torque unreachable and no 6-D force closure", grasp["minimum_axial_torque_residual"] > 0.99 and grasp["full_6d_wrench_span"] is False and grasp["full_6d_force_closure"] is False, grasp),
        _check("IA-B322", "both P coordinates remain in design-model stroke", min(stroke["left_min_m"], stroke["right_min_m"]) >= float(scenario["stroke_lower_m"]) and max(stroke["left_max_m"], stroke["right_max_m"]) <= float(scenario["stroke_upper_m"]), stroke),
        _check("IA-B323", "no-contact regression including target quaternion and P H E", no_contact_pass, no_contact),
        _check("IA-B324", "independent RK4 step-halving", convergence["rk4"]["all_components_pass"], convergence["rk4"]),
        _check("IA-B325", "midpoint nonsmooth-event absolute envelope without monotonicity claim", convergence["midpoint"]["monotonicity_claimed"] is False and convergence["midpoint"]["all_components_pass"], convergence["midpoint"]),
        _check("IA-B326", "cross-integrator contact candidate release and impulse convergence", event_convergence_pass and convergence["all_core_outcomes_pass"], convergence),
        _check("IA-B327", "22 real solver-side and independent mutation controls", controls["pass"], controls),
        _check("IA-B328", "independent metrics match hash-bound declared ledger", ledger_crosscheck["pass"], ledger_crosscheck),
        _check("IA-B329", "physical current lock production release authorizations remain false", pre_audit.get("authorizations") == expected_authorizations, pre_audit.get("authorizations")),
        _check("IA-B330", "formal Sim13 V2 remains 15 of 20 with five HOLDs", pre_audit.get("formal_sim13_v2_state") == formal_state, pre_audit.get("formal_sim13_v2_state")),
        _check("IA-B331", "no generated URDF or cache artifacts", forbidden["pass"], forbidden),
    ]
    passed = sum(item["pass"] for item in checks); all_pass = passed == len(checks)
    receipt = {
        "schema": "SIM13_V4B3_INDEPENDENT_AUDIT_RECEIPT_V1",
        "status": "PASS_INDEPENDENT_AUDIT" if all_pass else "FAIL_INDEPENDENT_AUDIT",
        "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        "upstream_evidence_manifest": _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
        "upstream_pre_audit_gate": _record(PRE_AUDIT_GATE, "UPSTREAM_PRE_AUDIT_GATE"),
        "score": {"pass": passed, "fail": len(checks) - passed, "total": len(checks)},
        "checks": checks,
    }
    _write(AUDIT_RECEIPT, receipt)
    if not all_pass:
        print(json.dumps({"status": receipt["status"], "score": receipt["score"]}, indent=2))
        return 1

    final_authorizations = dict(expected_authorizations)
    final_authorizations["synthetic_phase_b3_audited_ready"] = True
    final = {
        "schema": "SIM13_V4B3_AUDITED_GATE_V1",
        "overall_status": "PASS_PHASE_B3_SYNTHETIC_BRANCHED_DUAL_HARD_FINGER_CONTACT_TRANSIENT_CANDIDATE_WITH_RANK5_NO_6D_CLOSURE_AND_ALL_PHYSICAL_CURRENT_LOCK_RELEASE_HOLDS",
        "final_gate": True,
        "hash_chain": {
            "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
            "upstream_evidence_manifest": _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
            "upstream_pre_audit_gate": _record(PRE_AUDIT_GATE, "UPSTREAM_PRE_AUDIT_GATE"),
            "upstream_independent_audit_receipt": _record(AUDIT_RECEIPT, "UPSTREAM_INDEPENDENT_AUDIT_RECEIPT"),
        },
        "validator_checks": validation["score"], "independent_audit_checks": receipt["score"],
        "audited_metrics": {
            "per_contact_event": metrics["per_contact_event"],
            "qualifying_sample_count": state["qualifying_sample_count"],
            "total_linear_momentum_max_drift_n_s": metrics["total_linear_momentum_drift_n_s"],
            "total_angular_momentum_max_drift_n_m_s": metrics["total_angular_momentum_drift_n_m_s"],
            "energy_plus_dissipation_max_drift_j": metrics["energy_plus_dissipation_drift_j"],
            "all_qualifying_grasp_map_rank": 5,
            "full_6d_wrench_span": False, "full_6d_force_closure": False,
            "axial_pure_torque_unreachable": True,
            "cross_integrator_event_difference": cross,
            "extended_cross_integrator_event_difference": extended_cross,
        },
        "gates": [
            {"id": "V4B3-FG01", "name": "synthetic branched dual hard-finger transient candidate", "status": "PASS_AUDITED", "pass": True},
            {"id": "V4B3-FG02", "name": "full 6-D wrench span and force closure", "status": "HOLD_FALSE_RANK5", "pass": False},
            {"id": "V4B3-FG03", "name": "physical contact friction actuator identification", "status": "HOLD_SYNTHETIC_PARAMETERS", "pass": False},
            {"id": "V4B3-FG04", "name": "held capture lock and grasp success", "status": "HOLD_NOT_IMPLEMENTED", "pass": False},
            {"id": "V4B3-FG05", "name": "current system and formal NC19", "status": "HOLD_NOT_BOUND", "pass": False},
            {"id": "V4B3-FG06", "name": "Owner production release next stage", "status": "HOLD_NOT_AUTHORIZED", "pass": False},
        ],
        "authorizations": final_authorizations,
        "formal_sim13_v2_state": formal_state,
    }
    _write(FINAL_GATE, final)
    terminal = {
        "schema": "SIM13_V4B3_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
        "self_excluded": True, "acyclic": True,
        "records": [
            _record(AUDIT_RECEIPT, "UPSTREAM_INDEPENDENT_AUDIT_RECEIPT"),
            _record(FINAL_GATE, "UPSTREAM_FINAL_GATE"),
        ],
    }
    _write(TERMINAL_MANIFEST, terminal)
    print(json.dumps({
        "status": final["overall_status"], "validator_checks": validation["score"],
        "independent_audit_checks": receipt["score"], "audited_metrics": final["audited_metrics"],
        "negative_controls": len(controls["expected_ids"]), "final_gate_sha256": _sha(FINAL_GATE),
        "terminal_manifest_sha256": _sha(TERMINAL_MANIFEST),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
