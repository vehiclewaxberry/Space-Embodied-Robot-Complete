#!/usr/bin/env python3
"""Dormant generator source for a C01 Unified-R2 URDF simulation candidate.

The top-level ``gen_urdf()`` follows the local URDF generator contract, but it
fails closed before constructing XML unless a separate, hash-bound execution
authorization exists.  Importing this module is read-only and side-effect free.
"""

from __future__ import annotations

import copy
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INPUTS_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_INPUTS_V1.yaml"
AUTHORITY_PATH = HERE / "UNIFIED_R2_REBASE_EXECUTION_AUTHORIZATION_V1.json"

PI = math.pi
ROBOT_NAME = "unified_r2_c01_deployed_snapshot_sim_candidate_v1"
EXPECTED_LINKS = 15
EXPECTED_JOINTS = 14
EXPECTED_ACTUATED_DOF = 8
EXPECTED_TOTAL_MASS_KG = 31.022864807342987


def _fmt(values) -> str:
    return " ".join(f"{float(value):.16g}" for value in values)


def _load_inputs() -> dict:
    return yaml.safe_load(INPUTS_PATH.read_text(encoding="utf-8-sig"))


def _require_execution_authority() -> dict:
    if not AUTHORITY_PATH.is_file():
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: missing separately hash-bound execution authorization")
    record = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8-sig"))
    if record.get("schema") != "UNIFIED_R2_REBASE_EXECUTION_AUTHORIZATION_V1":
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: authorization schema mismatch")
    flags = record.get("authority_flags", {})
    required = (
        "rebase_execution_authorized",
        "system_urdf_generation_authorized",
        "route_c_cad_authorized",
        "memory_admitted_for_this_execution",
    )
    if any(flags.get(name) is not True for name in required):
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: exact-true prerequisite missing")
    if record.get("owner_accepted") is not True:
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: Owner acceptance absent")
    return record


def _transpose(a):
    return [list(row) for row in zip(*a)]


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def _matvec(a, v):
    return [sum(a[i][k] * v[k] for k in range(len(v))) for i in range(len(a))]


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _rotation(T):
    return [row[:3] for row in T[:3]]


def _translation(T):
    return [row[3] for row in T[:3]]


def _inverse_transform(T):
    R = _rotation(T)
    Rt = _transpose(R)
    t_inv = [-v for v in _matvec(Rt, _translation(T))]
    return [Rt[0] + [t_inv[0]], Rt[1] + [t_inv[1]], Rt[2] + [t_inv[2]], [0.0, 0.0, 0.0, 1.0]]


def _transform_multiply(a, b):
    return _matmul(a, b)


def _rpy_from_rotation(R):
    pitch = math.asin(max(-1.0, min(1.0, -R[2][0])))
    cp = math.cos(pitch)
    if abs(cp) > 1.0e-12:
        roll = math.atan2(R[2][1], R[2][2])
        yaw = math.atan2(R[1][0], R[0][0])
    else:
        roll = math.atan2(-R[1][2], R[1][1])
        yaw = 0.0
    return [roll, pitch, yaw]


def _to_link_properties(component: dict, T_S_link):
    R = _rotation(T_S_link)
    Rt = _transpose(R)
    t = _translation(T_S_link)
    com_link = _matvec(Rt, _sub(component["com_S_m"], t))
    inertia_link = _matmul(_matmul(Rt, component["inertia_about_com_S_kg_m2"]), R)
    return com_link, inertia_link


def _add_inertial(link, mass_kg: float, com, inertia):
    inertial = ET.SubElement(link, "inertial")
    ET.SubElement(inertial, "origin", {"xyz": _fmt(com), "rpy": "0 0 0"})
    ET.SubElement(inertial, "mass", {"value": f"{mass_kg:.16g}"})
    ET.SubElement(
        inertial,
        "inertia",
        {
            "ixx": f"{inertia[0][0]:.16g}",
            "ixy": f"{inertia[0][1]:.16g}",
            "ixz": f"{inertia[0][2]:.16g}",
            "iyy": f"{inertia[1][1]:.16g}",
            "iyz": f"{inertia[1][2]:.16g}",
            "izz": f"{inertia[2][2]:.16g}",
        },
    )


def _add_box(link, size, origin=(0.0, 0.0, 0.0), rpy=(0.0, 0.0, 0.0), include_collision=True):
    for use in (("visual", True), ("collision", include_collision)):
        if not use[1]:
            continue
        node = ET.SubElement(link, use[0])
        ET.SubElement(node, "origin", {"xyz": _fmt(origin), "rpy": _fmt(rpy)})
        geometry = ET.SubElement(node, "geometry")
        ET.SubElement(geometry, "box", {"size": _fmt(size)})


def _add_fixed_joint(robot, name: str, parent: str, child: str, T_parent_child):
    joint = ET.SubElement(robot, "joint", {"name": name, "type": "fixed"})
    ET.SubElement(joint, "parent", {"link": parent})
    ET.SubElement(joint, "child", {"link": child})
    ET.SubElement(
        joint,
        "origin",
        {"xyz": _fmt(_translation(T_parent_child)), "rpy": _fmt(_rpy_from_rotation(_rotation(T_parent_child)))},
    )


def _box_from_bounds(bounds):
    lower, upper = bounds
    size = [upper[i] - lower[i] for i in range(3)]
    center = [(upper[i] + lower[i]) / 2.0 for i in range(3)]
    if any(value <= 0.0 for value in size):
        raise RuntimeError("non-positive broad-phase box")
    return center, size


def _append_b601_subtree(robot, inputs):
    urdf_rel = inputs["source_pins"]["accepted_b601_urdf"]["path"]
    arm_root = ET.parse(ROOT / urdf_rel).getroot()
    bounds_rel = inputs["source_pins"]["b601_linklocal_bounds"]["path"]
    bounds = json.loads((ROOT / bounds_rel).read_text(encoding="utf-8-sig"))

    for source_link in arm_root.findall("link"):
        link = copy.deepcopy(source_link)
        for child in list(link):
            if child.tag in {"visual", "collision"}:
                link.remove(child)
        name = link.attrib["name"]
        if name in bounds["components"] and name != "legacy_gripper_detail":
            local_bounds = bounds["components"][name]["local_surface"]["bounds_link_m"]
            center, size = _box_from_bounds(local_bounds)
            _add_box(link, size, center, include_collision=True)
        elif name == "gripper_link":
            local_bounds = bounds["active_gripper_r1"]["palm"]["local_surface"]["bounds_gripper_link_m"]
            center, size = _box_from_bounds(local_bounds)
            _add_box(link, size, center, include_collision=True)
        robot.append(link)

    for joint in arm_root.findall("joint"):
        robot.append(copy.deepcopy(joint))


def _build_robot(inputs: dict) -> ET.Element:
    components = inputs["components_c01"]
    frames = inputs["frames"]
    robot = ET.Element("robot", {"name": ROBOT_NAME})
    robot.append(ET.Comment("C01 fixed-deployed simulation candidate; broad-phase only; not production/contact/flight authority"))

    bus = ET.SubElement(robot, "link", {"name": "spacecraft_bus"})
    bus_data = components["spacecraft_bus"]
    _add_inertial(bus, bus_data["mass_kg"], bus_data["com_S_m"], bus_data["inertia_about_com_S_kg_m2"])
    _add_box(bus, bus_data["broadphase_box_size_m"])

    bridge = ET.SubElement(robot, "link", {"name": "load_bridge_candidate"})
    bridge_data = components["load_bridge_candidate"]
    _add_inertial(bridge, bridge_data["mass_kg"], bridge_data["com_S_m"], bridge_data["inertia_about_com_S_kg_m2"])
    _add_box(bridge, bridge_data["broadphase_box_size_m"], bridge_data["com_S_m"])

    T_S_M3R = frames["T_S_M3R_LOCAL"]
    m3r = ET.SubElement(robot, "link", {"name": "m3r_lumped_link"})
    m3r_data = components["m3r_lumped_link"]
    m3r_com, m3r_inertia = _to_link_properties(m3r_data, T_S_M3R)
    _add_inertial(m3r, m3r_data["mass_kg"], m3r_com, m3r_inertia)

    for side, frame_name, component_name in (
        ("left", "T_S_R2_ROOT_L", "solar_r2_left_c01_snapshot"),
        ("right", "T_S_R2_ROOT_R", "solar_r2_right_c01_snapshot"),
    ):
        link = ET.SubElement(robot, "link", {"name": component_name})
        data = components[component_name]
        T = frames[frame_name]
        com, inertia = _to_link_properties(data, T)
        _add_inertial(link, data["mass_kg"], com, inertia)
        for leaf_index in range(3):
            # Root-frame local z is the q=0 span. Rx(+pi/2) maps it to
            # -Y_root, which is +Y_S on the left and -Y_S on the right.
            center = (0.0, -(leaf_index + 0.5) * 0.200, -leaf_index * 0.003)
            _add_box(link, (0.300, 0.0025, 0.200), center, (PI / 2.0, 0.0, 0.0), include_collision=True)

    _append_b601_subtree(robot, inputs)

    identity = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    _add_fixed_joint(robot, "bus_to_load_bridge_candidate", "spacecraft_bus", "load_bridge_candidate", identity)
    _add_fixed_joint(robot, "load_bridge_to_m3r", "load_bridge_candidate", "m3r_lumped_link", T_S_M3R)
    T_M3R_B601 = _transform_multiply(_inverse_transform(T_S_M3R), frames["T_S_B601_ARM_BASE_PHYSICAL"])
    _add_fixed_joint(robot, "m3r_to_b601_base", "m3r_lumped_link", "base_link", T_M3R_B601)
    _add_fixed_joint(robot, "bus_to_solar_r2_left_c01_snapshot", "spacecraft_bus", "solar_r2_left_c01_snapshot", frames["T_S_R2_ROOT_L"])
    _add_fixed_joint(robot, "bus_to_solar_r2_right_c01_snapshot", "spacecraft_bus", "solar_r2_right_c01_snapshot", frames["T_S_R2_ROOT_R"])

    links = robot.findall("link")
    joints = robot.findall("joint")
    if (len(links), len(joints)) != (EXPECTED_LINKS, EXPECTED_JOINTS):
        raise RuntimeError(f"topology drift: links={len(links)} joints={len(joints)}")
    actuated = sum(j.attrib["type"] in {"revolute", "continuous", "prismatic"} for j in joints)
    if actuated != EXPECTED_ACTUATED_DOF:
        raise RuntimeError(f"actuated DOF drift: {actuated}")
    total_mass = sum(float(link.find("inertial/mass").attrib["value"]) for link in links)
    if abs(total_mass - EXPECTED_TOTAL_MASS_KG) > 1.0e-12:
        raise RuntimeError(f"mass drift: {total_mass}")
    return robot


def gen_urdf():
    """Return a complete URDF root only after all external authority joins pass."""
    _require_execution_authority()
    return _build_robot(_load_inputs())


if __name__ == "__main__":
    raise SystemExit("Use the project URDF generator launcher after authorization; direct execution is forbidden.")
