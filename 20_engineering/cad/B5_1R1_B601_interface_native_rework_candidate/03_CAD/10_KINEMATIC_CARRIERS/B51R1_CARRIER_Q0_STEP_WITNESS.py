"""Accepted-URDF-derived B51R1 carrier q0 neutral STEP witness.

This generator is intentionally fail-closed against the frozen URDF and q0
axis register.  It exports only visible frame/topology witnesses.  It is not a
native SolidWorks articulated assembly and carries no T005 or physical credit.
"""

from __future__ import annotations

import csv
import hashlib
from math import cos, sin
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from build123d import Align, Box, Compound, Plane, Solid, Sphere


URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
Q0_AXES_SHA256 = "73F1E674A57F3EB7863BEBF32D497DF8829E4348DBB84C6A1A796106036845C0"

MM_PER_M = 1000.0
FRAME_AXIS_LENGTH = 18.0
FRAME_AXIS_RADIUS = 0.65
JOINT_AXIS_LENGTH = 28.0
JOINT_AXIS_RADIUS = 1.15
TOPOLOGY_EDGE_RADIUS = 0.55
NODE_RADIUS = 2.8
QMAX_MARKER_SIDE = 4.0

CARRIER_NAMES = {
    "base_link": "B51R1_CARRIER_BASE",
    "link1": "B51R1_CARRIER_LINK_01",
    "link2": "B51R1_CARRIER_LINK_02",
    "link3": "B51R1_CARRIER_LINK_03",
    "link4": "B51R1_CARRIER_LINK_04",
    "link5": "B51R1_CARRIER_LINK_05",
    "link6": "B51R1_CARRIER_LINK_06",
    "gripper_link": "B51R1_CARRIER_LINK_07_BRANCH_PARENT",
    "gripper_left": "B51R1_CARRIER_LINK_08_PRISMATIC_LEAF",
    "gripper_right": "B51R1_CARRIER_LINK_09_PRISMATIC_LEAF",
}


def _label(shape, name):
    shape.label = name
    return shape


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _floats(text: str | None, default: tuple[float, float, float]) -> np.ndarray:
    if not text:
        return np.array(default, dtype=float)
    return np.array([float(value) for value in text.split()], dtype=float)


def _rpy_matrix(rpy: np.ndarray) -> np.ndarray:
    roll, pitch, yaw = rpy
    cr, sr = cos(roll), sin(roll)
    cp, sp = cos(pitch), sin(pitch)
    cy, sy = cos(yaw), sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], dtype=float)
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], dtype=float)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], dtype=float)
    return rz @ ry @ rx


def _origin_transform(joint: ET.Element) -> np.ndarray:
    origin = joint.find("origin")
    xyz = _floats(origin.get("xyz") if origin is not None else None, (0, 0, 0))
    rpy = _floats(origin.get("rpy") if origin is not None else None, (0, 0, 0))
    result = np.eye(4)
    result[:3, :3] = _rpy_matrix(rpy)
    result[:3, 3] = xyz
    return result


def _rod_between(p0: np.ndarray, p1: np.ndarray, radius: float, name: str):
    vector = np.asarray(p1, dtype=float) - np.asarray(p0, dtype=float)
    length = float(np.linalg.norm(vector))
    if length <= 1e-9:
        return _label(Sphere(radius).moved(tuple(p0)), name)
    direction = vector / length
    plane = Plane(origin=tuple(p0), z_dir=tuple(direction))
    return _label(Solid.make_cylinder(radius, length, plane), name)


def _rod_centered(center: np.ndarray, direction: np.ndarray, length: float, radius: float, name: str):
    unit = np.asarray(direction, dtype=float)
    unit = unit / np.linalg.norm(unit)
    return _rod_between(center - unit * length / 2.0, center + unit * length / 2.0, radius, name)


def _frame_witness(carrier_name: str, transform_m: np.ndarray):
    origin = transform_m[:3, 3] * MM_PER_M
    rotation = transform_m[:3, :3]
    children = [
        _label(Sphere(NODE_RADIUS).moved(tuple(origin)), f"{carrier_name}_CS_LINK_ORIGIN"),
    ]
    for index, axis_name in enumerate(("X", "Y", "Z")):
        axis = rotation[:, index]
        children.append(
            _rod_between(
                origin,
                origin + axis * FRAME_AXIS_LENGTH,
                FRAME_AXIS_RADIUS,
                f"{carrier_name}_CS_LINK_{axis_name}_POS",
            )
        )
    return _label(Compound(children=children), carrier_name)


def _read_inputs():
    candidate_root = Path(__file__).resolve().parents[2]
    authority = candidate_root / "00_BASELINE" / "AUTHORITIES" / "accepted_urdf"
    urdf_path = authority / "arm_b601_v1.urdf"
    axes_path = authority / "q0_joint_axes.csv"
    actual_urdf = _sha256(urdf_path)
    actual_axes = _sha256(axes_path)
    if actual_urdf != URDF_SHA256:
        raise RuntimeError(f"URDF hash mismatch: {actual_urdf}")
    if actual_axes != Q0_AXES_SHA256:
        raise RuntimeError(f"q0 axes hash mismatch: {actual_axes}")
    root = ET.parse(urdf_path).getroot()
    with axes_path.open("r", encoding="utf-8-sig", newline="") as handle:
        axes_rows = {row["joint"]: row for row in csv.DictReader(handle)}
    return root, axes_rows


def _solve_q0(root: ET.Element):
    joints = []
    child_links = set()
    for element in root.findall("joint"):
        parent = element.find("parent").get("link")
        child = element.find("child").get("link")
        child_links.add(child)
        joints.append(
            {
                "name": element.get("name"),
                "type": element.get("type"),
                "parent": parent,
                "child": child,
                "element": element,
                "origin": _origin_transform(element),
                "axis_local": _floats(
                    element.find("axis").get("xyz") if element.find("axis") is not None else None,
                    (0, 0, 0),
                ),
                "lower": float(element.find("limit").get("lower"))
                if element.find("limit") is not None
                else None,
                "upper": float(element.find("limit").get("upper"))
                if element.find("limit") is not None
                else None,
            }
        )

    all_links = [element.get("name") for element in root.findall("link")]
    roots = [name for name in all_links if name not in child_links]
    if roots != ["base_link"]:
        raise RuntimeError(f"Unexpected URDF roots: {roots}")

    transforms = {"base_link": np.eye(4)}
    pending = joints.copy()
    while pending:
        progressed = False
        for joint in pending[:]:
            if joint["parent"] not in transforms:
                continue
            transforms[joint["child"]] = transforms[joint["parent"]] @ joint["origin"]
            pending.remove(joint)
            progressed = True
        if not progressed:
            raise RuntimeError("URDF graph could not be resolved")
    return all_links, joints, transforms


def _validate_against_axis_register(joints, transforms, axes_rows):
    checks = []
    for joint in joints:
        row = axes_rows[joint["name"]]
        expected_origin = np.array(
            [float(v) for v in row["origin_A0_xyz_mm"].split()], dtype=float
        )
        actual_origin = transforms[joint["child"]][:3, 3] * MM_PER_M
        origin_error = float(np.max(np.abs(actual_origin - expected_origin)))

        if joint["type"] == "fixed":
            actual_axis = np.zeros(3)
            expected_axis = np.zeros(3)
            axis_error = 0.0
        else:
            actual_axis = transforms[joint["child"]][:3, :3] @ joint["axis_local"]
            actual_axis = actual_axis / np.linalg.norm(actual_axis)
            expected_axis = np.array(
                [float(v) for v in row["axis_A0_q0"].split()], dtype=float
            )
            expected_axis = expected_axis / np.linalg.norm(expected_axis)
            axis_error = float(np.max(np.abs(actual_axis - expected_axis)))

        if origin_error > 5e-4 or axis_error > 2e-5:
            raise RuntimeError(
                f"{joint['name']} q0 register mismatch: "
                f"origin={origin_error:.9g} mm, axis={axis_error:.9g}"
            )
        checks.append(
            {
                "joint": joint["name"],
                "origin_error_mm": origin_error,
                "axis_error": axis_error,
                "actual_axis": actual_axis,
            }
        )
    return checks


def gen_step():
    root, axes_rows = _read_inputs()
    links, joints, transforms = _solve_q0(root)
    checks = _validate_against_axis_register(joints, transforms, axes_rows)

    children = []
    for link in links:
        children.append(_frame_witness(CARRIER_NAMES[link], transforms[link]))

    for joint, check in zip(joints, checks):
        parent_origin = transforms[joint["parent"]][:3, 3] * MM_PER_M
        child_origin = transforms[joint["child"]][:3, 3] * MM_PER_M
        joint_children = [
            _rod_between(
                parent_origin,
                child_origin,
                TOPOLOGY_EDGE_RADIUS,
                f"{joint['name']}_PARENT_CHILD_TOPOLOGY_EDGE_ONLY",
            )
        ]
        if joint["type"] == "revolute":
            joint_children.append(
                _rod_centered(
                    child_origin,
                    check["actual_axis"],
                    JOINT_AXIS_LENGTH,
                    JOINT_AXIS_RADIUS,
                    f"AXIS_{joint['name']}_Q0_ACCEPTED",
                )
            )
        elif joint["type"] == "prismatic":
            travel_mm = (joint["upper"] - joint["lower"]) * MM_PER_M
            direction = check["actual_axis"]
            qmax = child_origin + direction * travel_mm
            joint_children.extend(
                [
                    _rod_between(
                        child_origin,
                        qmax,
                        JOINT_AXIS_RADIUS,
                        f"TRAVEL_{joint['name']}_Q0_TO_QMAX_71_5MM_INDEPENDENT",
                    ),
                    _label(
                        Box(
                            QMAX_MARKER_SIDE,
                            QMAX_MARKER_SIDE,
                            QMAX_MARKER_SIDE,
                            align=(Align.CENTER, Align.CENTER, Align.CENTER),
                        ).moved(tuple(qmax)),
                        f"{joint['name']}_QMAX_MARKER",
                    ),
                ]
            )
        else:
            joint_children.append(
                _label(
                    Box(
                        5.0,
                        5.0,
                        5.0,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    ).moved(tuple(child_origin)),
                    f"{joint['name']}_FIXED_TRANSFORM_MARKER",
                )
            )
        children.append(
            _label(
                Compound(children=joint_children),
                f"JOINT_{joint['name']}_{joint['type'].upper()}_Q0_WITNESS",
            )
        )

    result = Compound(children=children)
    result.label = "B51R1_CARRIER_Q0_STEP_WITNESS_10_LINKS_6R_1FIXED_2P_DATUM_ONLY"
    return result

