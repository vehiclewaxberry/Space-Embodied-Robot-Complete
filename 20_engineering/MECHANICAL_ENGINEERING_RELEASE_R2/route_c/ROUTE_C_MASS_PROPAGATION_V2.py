#!/usr/bin/env python3
"""Route-C nine-configuration mass-property propagation, corrected V2.

This tool is deliberately fail-closed and non-authorizing.  It fixes the V1
``components``/``composition`` binding defect and reports mass properties in a
single, explicit convention.  For the ODR-58 V9F fallback it also binds each
mesh part by name to the build-receipt ``motion_class``, applies the frozen
four-stage trombone/follower laws at every configuration q4, and analytically
rebuilds the distributed SEG-04 bundle instead of rigidly freezing its q4=0
shape:

* frame: spacecraft S;
* length: m;
* mass: kg;
* inertia: kg m^2;
* input inertia: about the input configuration centre of mass;
* output inertia: about the updated centre of mass;
* comparable inertia: both input and output about the fixed S origin O_S.

The R2 standard-uncertainty fields are metrology metadata.  They are not used as
acceptance limits.  ODR-50 contains a qualitative reopen trigger but no approved
numerical conformity rule, so this tool cannot issue a TMG-2 or release verdict.

Current non-authorizing replay:
    python -B ROUTE_C_MASS_PROPAGATION_V2.py --variant V7 --self-test \
        --output ROUTE_C_MASS_PROPAGATION_V2_SELFTEST_V7.json

Every evaluation must use a new output path.  Existing files are never
overwritten.  A successful calculation does not override FAIL/HOLD/UNKNOWN
states in the nine-configuration binding gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml


HERE = Path(__file__).resolve().parent
ENGINEERING_ROOT = HERE.parents[1]

P_BASELINE = (
    ENGINEERING_ROOT
    / "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    / "wp2_design_mass"
    / "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
)
P_TRANSFORMS = (
    ENGINEERING_ROOT
    / "F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1"
    / "wp2_mass_properties"
    / "CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml"
)
P_URDF = (
    ENGINEERING_ROOT
    / "cad"
    / "spacecraft_layout"
    / "arm_b601_v1"
    / "arm_b601_v1.urdf"
)
P_MOUNT = (
    ENGINEERING_ROOT
    / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
    / "04_configurations"
    / "F3R2_ARM_INITIAL_POSE.yaml"
)
P_ODR50 = HERE.parent / "_work" / "odr" / "ODR-50_RECORD.json"

URDF_SHA256_PIN = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
LINKS = ("base_link", "link1", "link2", "link3", "link4", "link5", "link6")
VALID_HOSTS = set(LINKS) | {"bus"}
COMPONENT_ORDER = ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")
V9F_DYNAMIC_SEGMENT_ID = "SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER"
V9F_MOTION_FRACTIONS = {
    "FIXED_LINK3": 0.0,
    "ONE_THIRD_TRAVEL": 1.0 / 3.0,
    "TWO_THIRDS_TRAVEL": 2.0 / 3.0,
    "FULL_TRAVEL": 1.0,
}
V9F_RIGID_LINK4_CLASSES = {"FIXED_LINK4", "FOLLOWER_LINK4"}
V9F_ALLOWED_MOTION_CLASSES = set(V9F_MOTION_FRACTIONS) | V9F_RIGID_LINK4_CLASSES

# Nominal values are the design-candidate assumptions already used by the Route-C
# CAD builder.  The uncertainty model is explicitly separate from acceptance.
DENSITY_G_PER_MM3 = {"aluminum": 2.70e-3, "polymer": 1.20e-3}
HARDWARE_RELATIVE_STANDARD_UNCERTAINTY = 0.10
BUNDLE_LINEAR_DENSITY_G_PER_M = 65.0
BUNDLE_BOUNDS_G_PER_M = (56.5, 72.5)
BUNDLE_CONSERVATIVE_HALF_WIDTH_G_PER_M = max(
    abs(BUNDLE_LINEAR_DENSITY_G_PER_M - BUNDLE_BOUNDS_G_PER_M[0]),
    abs(BUNDLE_BOUNDS_G_PER_M[1] - BUNDLE_LINEAR_DENSITY_G_PER_M),
)
BUNDLE_STANDARD_UNCERTAINTY_G_PER_M = BUNDLE_CONSERVATIVE_HALF_WIDTH_G_PER_M / math.sqrt(3.0)


class ContractError(RuntimeError):
    """Raised when an input violates the propagation contract."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def relpath(path: Path) -> str:
    return path.relative_to(ENGINEERING_ROOT).as_posix()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def transform_translation(xyz_mm: Iterable[float]) -> np.ndarray:
    out = np.eye(4)
    out[:3, 3] = np.asarray(tuple(xyz_mm), dtype=float)
    return out


def rotation_axis(axis: Iterable[float], angle_rad: float) -> np.ndarray:
    a = np.asarray(tuple(axis), dtype=float)
    norm = float(np.linalg.norm(a))
    if norm <= 0.0:
        raise ContractError("zero-length URDF joint axis")
    x, y, z = a / norm
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    C = 1.0 - c
    R = np.array(
        [
            [x * x * C + c, x * y * C - z * s, x * z * C + y * s],
            [y * x * C + z * s, y * y * C + c, y * z * C - x * s],
            [z * x * C - y * s, z * y * C + x * s, z * z * C + c],
        ],
        dtype=float,
    )
    out = np.eye(4)
    out[:3, :3] = R
    return out


def rotation_rpy(rpy: Iterable[float]) -> np.ndarray:
    r, p, y = tuple(rpy)
    return rotation_axis((0.0, 0.0, 1.0), y) @ rotation_axis((0.0, 1.0, 0.0), p) @ rotation_axis((1.0, 0.0, 0.0), r)


def parallel_axis(inertia_cg: np.ndarray, mass: float, displacement: np.ndarray) -> np.ndarray:
    d = np.asarray(displacement, dtype=float)
    return inertia_cg + mass * ((d @ d) * np.eye(3) - np.outer(d, d))


def inertia_matrix(components: dict[str, float]) -> np.ndarray:
    return np.array(
        [
            [components["Ixx"], components["Ixy"], components["Ixz"]],
            [components["Ixy"], components["Iyy"], components["Iyz"]],
            [components["Ixz"], components["Iyz"], components["Izz"]],
        ],
        dtype=float,
    )


def matrix_components(matrix: np.ndarray) -> dict[str, float]:
    I = np.asarray(matrix, dtype=float)
    return {
        "Ixx": float(I[0, 0]),
        "Iyy": float(I[1, 1]),
        "Izz": float(I[2, 2]),
        "Ixy": float(I[0, 1]),
        "Ixz": float(I[0, 2]),
        "Iyz": float(I[1, 2]),
    }


def matrix_rows(matrix: np.ndarray) -> list[list[float]]:
    return [[float(value) for value in row] for row in np.asarray(matrix, dtype=float)]


def vector6(matrix: np.ndarray) -> np.ndarray:
    I = np.asarray(matrix, dtype=float)
    return np.array((I[0, 0], I[1, 1], I[2, 2], I[0, 1], I[0, 2], I[1, 2]), dtype=float)


def six_to_matrix(values: Iterable[float]) -> np.ndarray:
    v = np.asarray(tuple(values), dtype=float)
    return np.array(((v[0], v[3], v[4]), (v[3], v[1], v[5]), (v[4], v[5], v[2])), dtype=float)


def inertia_checks(matrix: np.ndarray, tolerance: float = 1.0e-10) -> dict[str, Any]:
    I = np.asarray(matrix, dtype=float)
    symmetry = float(np.max(np.abs(I - I.T)))
    eig = np.linalg.eigvalsh(0.5 * (I + I.T))
    eig_sorted = np.sort(eig)
    triangle_margin = float(eig_sorted[0] + eig_sorted[1] - eig_sorted[2])
    return {
        "finite": bool(np.isfinite(I).all()),
        "symmetric": symmetry <= tolerance,
        "symmetry_max_abs_residual_kg_m2": symmetry,
        "positive_semidefinite": float(eig_sorted[0]) >= -tolerance,
        "minimum_principal_moment_kg_m2": float(eig_sorted[0]),
        "principal_moments_kg_m2": [float(value) for value in eig_sorted],
        "triangle_inequalities": triangle_margin >= -tolerance,
        "minimum_triangle_margin_kg_m2": triangle_margin,
    }


def parse_urdf(path: Path) -> tuple[list[dict[str, Any]], dict[str, tuple[float, float]]]:
    root = ET.parse(path).getroot()
    joints: list[dict[str, Any]] = []
    limits: dict[str, tuple[float, float]] = {}
    for element in root.iter("joint"):
        origin = element.find("origin")
        xyz = [0.0, 0.0, 0.0]
        rpy = [0.0, 0.0, 0.0]
        if origin is not None:
            if origin.get("xyz"):
                xyz = [float(value) * 1000.0 for value in origin.get("xyz", "").split()]
            if origin.get("rpy"):
                rpy = [float(value) for value in origin.get("rpy", "").split()]
        axis_element = element.find("axis")
        axis = [1.0, 0.0, 0.0]
        if axis_element is not None and axis_element.get("xyz"):
            axis = [float(value) for value in axis_element.get("xyz", "").split()]
        joint = {
            "name": element.get("name"),
            "type": element.get("type"),
            "parent": element.find("parent").get("link"),
            "child": element.find("child").get("link"),
            "xyz_mm": xyz,
            "rpy_rad": rpy,
            "axis": axis,
        }
        if joint["type"] == "revolute":
            limit = element.find("limit")
            if limit is None or limit.get("lower") is None or limit.get("upper") is None:
                raise ContractError(f"revolute joint {joint['name']} lacks limits")
            limits[str(joint["name"])] = (float(limit.get("lower")), float(limit.get("upper")))
        joints.append(joint)
    if len(limits) != 6:
        raise ContractError(f"expected six revolute joints, found {len(limits)}")
    return joints, limits


def fk_all(q_rad: Iterable[float], joints: list[dict[str, Any]], mount: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    q = tuple(float(value) for value in q_rad)
    revolute_names = [joint["name"] for joint in joints if joint["type"] == "revolute"]
    if len(q) != len(revolute_names):
        raise ContractError(f"expected {len(revolute_names)} joint values, got {len(q)}")
    q_by_name = dict(zip(revolute_names, q))
    base: dict[str, np.ndarray] = {"base_link": np.eye(4)}
    pending = list(joints)
    while pending:
        progressed = False
        for joint in pending[:]:
            if joint["parent"] not in base:
                continue
            T = base[joint["parent"]] @ transform_translation(joint["xyz_mm"]) @ rotation_rpy(joint["rpy_rad"])
            if joint["type"] == "revolute":
                T = T @ rotation_axis(joint["axis"], q_by_name[joint["name"]])
            base[joint["child"]] = T
            pending.remove(joint)
            progressed = True
        if not progressed:
            unresolved = [joint["name"] for joint in pending]
            raise ContractError(f"URDF tree cannot be resolved: {unresolved}")
    return {name: mount @ transform for name, transform in base.items()}, base


def line_points(p0: np.ndarray, p1: np.ndarray, step_mm: float) -> np.ndarray:
    length = float(np.linalg.norm(p1 - p0))
    count = max(1, int(math.ceil(length / step_mm)))
    return np.linspace(p0, p1, count + 1)


def arc_points(center: np.ndarray, e1: np.ndarray, e2: np.ndarray, radius: float, phi0: float, phi1: float, step_mm: float) -> np.ndarray:
    length = abs(phi1 - phi0) * radius
    count = max(2, int(math.ceil(length / step_mm)))
    phi = np.linspace(phi0, phi1, count + 1)
    return center + radius * (np.cos(phi)[:, None] * e1 + np.sin(phi)[:, None] * e2)


def fillet_points(corner: np.ndarray, incoming: np.ndarray, outgoing: np.ndarray, radius: float, available_in: float, available_out: float, step_mm: float) -> np.ndarray | None:
    u1 = incoming / np.linalg.norm(incoming)
    u2 = outgoing / np.linalg.norm(outgoing)
    turn = math.acos(float(np.clip(u1 @ u2, -1.0, 1.0)))
    if turn < math.radians(1.0):
        return None
    tangent = radius * math.tan(turn / 2.0)
    limit = 0.98 * min(available_in, available_out)
    if tangent > limit:
        tangent = limit
        radius = tangent / math.tan(turn / 2.0)
    t1 = corner - tangent * u1
    t2 = corner + tangent * u2
    normal_in_plane = u2 - (u1 @ u2) * u1
    norm = float(np.linalg.norm(normal_in_plane))
    if norm < 1.0e-12:
        return None
    normal_in_plane /= norm
    origin = t1 + radius * normal_in_plane
    normal_axis = np.cross(u1, normal_in_plane)
    normal_axis /= np.linalg.norm(normal_axis)
    e1 = normal_in_plane
    e2 = np.cross(normal_axis, e1)
    a1 = math.atan2(float((t1 - origin) @ e2), float((t1 - origin) @ e1))
    a2 = math.atan2(float((t2 - origin) @ e2), float((t2 - origin) @ e1))
    delta = (a2 - a1 + math.pi) % (2.0 * math.pi) - math.pi
    return arc_points(origin, e1, e2, radius, a1, a1 + delta, step_mm)


def polyline_points(raw_points: list[list[float]], radii: list[float], step_mm: float) -> np.ndarray:
    points = [np.asarray(point, dtype=float) for point in raw_points]
    output = [points[0][None, :]]
    cursor = points[0]
    index = 1
    while index < len(points):
        if index < len(points) - 1:
            radius = float(radii[index - 1]) if index - 1 < len(radii) else 0.0
            if radius > 0.0:
                fillet = fillet_points(
                    points[index],
                    points[index] - cursor,
                    points[index + 1] - points[index],
                    radius,
                    float(np.linalg.norm(points[index] - cursor)),
                    float(np.linalg.norm(points[index + 1] - points[index])),
                    step_mm,
                )
                if fillet is not None:
                    straight = line_points(cursor, fillet[0], step_mm)
                    output.append(straight[1:])
                    output.append(fillet[1:])
                    cursor = fillet[-1]
                    index += 1
                    continue
        straight = line_points(cursor, points[index], step_mm)
        output.append(straight[1:])
        cursor = points[index]
        index += 1
    return np.vstack(output)


def section_points(section: dict[str, Any], step_mm: float = 1.5) -> np.ndarray:
    section_type = section["type"]
    if section_type == "polyline":
        return polyline_points(section["points"], section.get("corner_fillet_radii_mm", []), step_mm)
    if section_type == "arc":
        return arc_points(
            np.asarray(section["center"], dtype=float),
            np.asarray(section["basis_e1"], dtype=float),
            np.asarray(section["basis_e2"], dtype=float),
            float(section["radius_mm"]),
            math.radians(float(section["start_angle_deg"])),
            math.radians(float(section["start_angle_deg"] + section["sweep_deg"])),
            step_mm,
        )
    if section_type == "helix":
        origin = np.asarray(section["origin"], dtype=float)
        axis = np.asarray(section["axis"], dtype=float)
        e1 = np.asarray(section["basis_e1"], dtype=float)
        e2 = np.asarray(section["basis_e2"], dtype=float)
        phi0 = math.radians(float(section["start_angle_deg"]))
        delta = math.radians(float(section["sweep_deg"]))
        advance = float(section["pitch_mm_per_turn"]) * delta / (2.0 * math.pi)
        length = math.sqrt((float(section["radius_mm"]) * delta) ** 2 + advance**2)
        count = max(2, int(math.ceil(length / step_mm)))
        t = np.linspace(0.0, 1.0, count + 1)
        phi = phi0 + delta * t
        return (
            origin
            + float(section["radius_mm"]) * (np.cos(phi)[:, None] * e1 + np.sin(phi)[:, None] * e2)
            + (advance * t)[:, None] * axis
        )
    raise ContractError(f"unknown centerline section type: {section_type}")


def quadrature(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(points) < 2:
        raise ContractError("centerline section has fewer than two points")
    ds = np.linalg.norm(np.diff(points, axis=0), axis=1)
    if not bool((ds > 0.0).all()):
        raise ContractError("centerline contains zero-length sampled edge")
    weights = np.concatenate(([ds[0] / 2.0], (ds[:-1] + ds[1:]) / 2.0, [ds[-1] / 2.0]))
    return points, weights


def aggregate_point_masses(points_m: np.ndarray, masses_kg: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    mass = float(np.sum(masses_kg))
    if mass <= 0.0:
        raise ContractError("non-positive aggregate mass")
    cg = np.sum(masses_kg[:, None] * points_m, axis=0) / mass
    inertia = np.zeros((3, 3))
    for point, value in zip(points_m, masses_kg):
        inertia = parallel_axis(inertia, float(value), point - cg)
    return mass, cg, inertia


def combine_bodies(bodies: list[dict[str, Any]]) -> tuple[float, np.ndarray, np.ndarray]:
    mass = float(sum(body["mass_kg"] for body in bodies))
    if mass <= 0.0:
        raise ContractError("cannot combine an empty/non-positive body group")
    cg = sum(body["mass_kg"] * body["cg"] for body in bodies) / mass
    inertia = np.zeros((3, 3))
    for body in bodies:
        inertia += parallel_axis(body["inertia_cg"], body["mass_kg"], body["cg"] - cg)
    return mass, cg, inertia


def binding_gate_assessment(binding: dict[str, Any]) -> dict[str, str]:
    """Classify the frozen binding text without upgrading its authority."""
    status = str(binding.get("revalidation_status") or "")
    classification = str(binding.get("classification") or "")
    combined = f"{status}__{classification}".upper()
    # The frozen accepted-pose token is explicitly ``NO_SOURCE_HOLD``; remove
    # that negated phrase before searching for positive HOLD authority.
    authority_tokens = combined.replace("NO_SOURCE_HOLD", "")
    if "FAIL" in authority_tokens:
        state = "FAIL"
        reason = "binding source explicitly contains FAIL"
    elif any(token in authority_tokens for token in ("HOLD", "HELD", "PROVISIONAL", "UNRATIFIED")):
        state = "HOLD"
        reason = "binding source explicitly retains HOLD/HELD/PROVISIONAL authority"
    elif status.upper().startswith("PASS_"):
        state = "PASS"
        reason = "binding source explicitly reports PASS and contains no hold/fail token"
    else:
        state = "UNKNOWN"
        reason = "binding source has no recognized fail-closed authority token"
    return {"state": state, "reason": reason, "source_status": status,
            "source_classification": classification}


def parse_v9f_motion_contract(
    parts_doc: dict[str, Any], centerline_doc: dict[str, Any], receipt_doc: dict[str, Any]
) -> dict[str, Any]:
    """Bind mesh geometry to the V9F receipt and parse its frozen motion laws."""
    j4 = centerline_doc.get("j4_trombone_annular_follower")
    if not isinstance(j4, dict) or not bool(j4.get("dynamic_evaluator_required")):
        raise ContractError("V9F centerline lacks required dynamic J4 motion contract")

    number = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
    trombone_match = re.fullmatch(
        rf"\s*x_C_mm\s*=\s*(?P<base>{number})\s*(?P<outer>[+-])\s*"
        rf"(?P<gain>{number})\s*\*\s*\(\s*q4_rad\s*(?P<inner>[+-])\s*"
        rf"(?P<offset>{number})\s*\)\s*",
        str(j4.get("q4_trombone_law", "")),
    )
    if trombone_match is None:
        raise ContractError("V9F q4_trombone_law is not the supported explicit affine form")
    base = float(trombone_match.group("base"))
    gain = float(trombone_match.group("gain"))
    outer_sign = 1.0 if trombone_match.group("outer") == "+" else -1.0
    inner_sign = 1.0 if trombone_match.group("inner") == "+" else -1.0
    offset = float(trombone_match.group("offset"))

    annulus_match = re.fullmatch(
        rf"\s*beta_rad\s*=\s*radians\(\s*(?P<beta0>{number})\s*\)\s*\+\s*"
        rf"\(\s*(?P<qmax>{number})\s*-\s*q4_rad\s*\)\s*;\s*"
        rf"alpha_m\s*=\s*radians\(\s*(?P<alpha0>{number})\s*\)\s*-\s*beta_rad\s*",
        str(j4.get("q4_annulus_law", "")),
    )
    if annulus_match is None:
        raise ContractError("V9F q4_annulus_law is not the supported explicit form")
    beta0_rad = math.radians(float(annulus_match.group("beta0")))
    qmax_law = float(annulus_match.group("qmax"))
    alpha0_rad = math.radians(float(annulus_match.group("alpha0")))

    def x_center(q4: float) -> float:
        return base + outer_sign * gain * (q4 + inner_sign * offset)

    def beta(q4: float) -> float:
        return beta0_rad + qmax_law - q4

    full_limits = [float(value) for value in j4["q4_full_hardware_limits_rad"]]
    proof = j4["constant_length_proof"]
    residual_tolerance_mm = float(proof["machine_residual_tolerance_required_mm"])
    if len(full_limits) != 2 or full_limits[0] > full_limits[1]:
        raise ContractError("V9F q4 hardware limits are invalid")
    if not math.isclose(qmax_law, full_limits[1], rel_tol=0.0, abs_tol=1.0e-12):
        raise ContractError("V9F annulus qmax law disagrees with hardware limit")
    if not math.isclose(x_center(0.0), float(j4["center_x_at_q0_mm"]),
                        rel_tol=0.0, abs_tol=residual_tolerance_mm):
        raise ContractError("V9F parsed trombone law disagrees with q4=0 center")
    if not math.isclose(-math.degrees(beta(0.0)),
                        float(j4["annular_follower"]["q0_bundle_sweep_deg"]),
                        rel_tol=0.0, abs_tol=1.0e-10):
        raise ContractError("V9F parsed annulus law disagrees with q4=0 sweep")

    receipt_rows = receipt_doc.get("parts")
    geometry_rows = parts_doc.get("parts")
    if not isinstance(receipt_rows, list) or not isinstance(geometry_rows, list):
        raise ContractError("V9F receipt/mesh parts collections are invalid")
    receipt_by_name: dict[str, dict[str, Any]] = {}
    for row in receipt_rows:
        name = str(row.get("name"))
        if name in receipt_by_name:
            raise ContractError(f"duplicate V9F receipt part name: {name}")
        receipt_by_name[name] = row
    geometry_nonbundle = [row for row in geometry_rows if row.get("kind") != "bundle_envelope"]
    geometry_names = {str(row.get("name")) for row in geometry_nonbundle}
    receipt_nonbundle_names = {
        name for name, row in receipt_by_name.items() if row.get("kind") != "bundle_envelope"
    }
    if geometry_names != receipt_nonbundle_names:
        raise ContractError("V9F mesh/receipt non-bundle part-name sets differ")

    motion_by_name: dict[str, str | None] = {}
    class_counts: dict[str, int] = {}
    class_mass_kg: dict[str, float] = {}
    for part in geometry_nonbundle:
        name = str(part["name"])
        receipt_part = receipt_by_name[name]
        for field in ("host_link", "kind", "material"):
            if part.get(field) != receipt_part.get(field):
                raise ContractError(f"V9F mesh/receipt {field} mismatch for {name}")
        motion_class = receipt_part.get("motion_class")
        if motion_class is not None and motion_class not in V9F_ALLOWED_MOTION_CLASSES:
            raise ContractError(f"unknown V9F motion_class {motion_class!r} for {name}")
        embedded = part.get("motion_class")
        if embedded is not None and embedded != motion_class:
            raise ContractError(f"V9F mesh/receipt motion_class mismatch for {name}")
        if motion_class in V9F_MOTION_FRACTIONS and receipt_part.get("host_link") != "link3":
            raise ContractError(f"{motion_class} part {name} is not link3-owned")
        if motion_class in V9F_RIGID_LINK4_CLASSES and receipt_part.get("host_link") != "link4":
            raise ContractError(f"{motion_class} part {name} is not link4-owned")
        motion_by_name[name] = motion_class
        label = motion_class or "RIGID_HOST_DEFAULT"
        class_counts[label] = class_counts.get(label, 0) + 1
        if motion_class is not None:
            density = DENSITY_G_PER_MM3[str(part["material"])]
            class_mass_kg[label] = class_mass_kg.get(label, 0.0) + (
                float(part["volume_mm3"]) * density / 1000.0
            )
    missing_classes = sorted(V9F_ALLOWED_MOTION_CLASSES - set(class_counts))
    if missing_classes:
        raise ContractError(f"V9F receipt lacks required motion classes: {missing_classes}")

    segment_matches = [
        segment for segment in centerline_doc.get("segments", [])
        if segment.get("id") == V9F_DYNAMIC_SEGMENT_ID
    ]
    if len(segment_matches) != 1:
        raise ContractError("V9F centerline must contain exactly one dynamic SEG-04")
    dynamic_segment = segment_matches[0]
    section_types = [section.get("type") for section in dynamic_segment.get("sections", [])]
    if section_types != ["polyline", "polyline", "arc", "polyline",
                         "polyline", "arc", "polyline"]:
        raise ContractError(f"V9F SEG-04 section topology changed: {section_types}")

    stage = j4["four_stage_telescope"]
    annulus = j4["annular_follower"]
    return {
        "x_center": x_center,
        "beta": beta,
        "x_slope_mm_per_rad": outer_sign * gain,
        "alpha0_rad": alpha0_rad,
        "full_limits_rad": full_limits,
        "residual_tolerance_mm": residual_tolerance_mm,
        "motion_by_name": motion_by_name,
        "class_counts": class_counts,
        "class_mass_kg": class_mass_kg,
        "dynamic_segment": dynamic_segment,
        "j4": j4,
        "stage_count": int(stage["stage_count_per_leg"]),
        "stage_length_mm": float(stage["stage_length_mm"]),
        "minimum_overlap_mm": float(stage["minimum_overlap_requirement_mm"]),
        "annulus": annulus,
        "parsed_laws": {
            "trombone_base_mm": base,
            "trombone_gain_signed_mm_per_rad": outer_sign * gain,
            "trombone_inner_offset_signed_rad": inner_sign * offset,
            "annulus_beta0_rad": beta0_rad,
            "annulus_qmax_rad": qmax_law,
            "annulus_fixed_alpha_rad": alpha0_rad,
        },
    }


def localize_body(
    host: str, mass_kg: float, cg_a0_m: np.ndarray, inertia_a0: np.ndarray,
    q0_base: dict[str, np.ndarray], group: str, source: str,
    motion_class: str | None = None, dynamic_pose_replaced: bool = False,
) -> dict[str, Any]:
    if host not in VALID_HOSTS:
        raise ContractError(f"unknown Route-C host: {host}")
    if host == "bus":
        T = np.eye(4)
    else:
        T = q0_base[host]
    R = T[:3, :3]
    cg_local = R.T @ (cg_a0_m - T[:3, 3] / 1000.0)
    inertia_local = R.T @ inertia_a0 @ R
    return {
        "host": host,
        "group": group,
        "mass_kg": float(mass_kg),
        "cg_local_m": cg_local,
        "inertia_local_kg_m2": inertia_local,
        "source": source,
        "motion_class": motion_class,
        "dynamic_pose_replaced": bool(dynamic_pose_replaced),
    }


def build_route_c_bodies(
    parts_doc: dict[str, Any], centerline_doc: dict[str, Any],
    q0_base: dict[str, np.ndarray], variant: str,
    receipt_doc: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
    bodies: list[dict[str, Any]] = []
    hardware_counts = {"aluminum": 0, "polymer": 0}
    motion_contract = None
    if variant == "V9F":
        if receipt_doc is None:
            raise ContractError("V9F mass propagation requires its build receipt")
        motion_contract = parse_v9f_motion_contract(parts_doc, centerline_doc, receipt_doc)
    for part in parts_doc["parts"]:
        if part["kind"] == "bundle_envelope":
            continue
        material = part["material"]
        if material not in DENSITY_G_PER_MM3:
            raise ContractError(f"unknown material {material!r} for {part['name']}")
        density = DENSITY_G_PER_MM3[material]
        mass_kg = float(part["volume_mm3"]) * density / 1000.0
        cg_a0_m = np.asarray(part["cg_mm_A0"], dtype=float) / 1000.0
        inertia_a0 = np.asarray(part["inertia_vol_mm5_about_cg_A0"], dtype=float) * density * 1.0e-9
        motion_class = (motion_contract["motion_by_name"].get(str(part["name"]))
                        if motion_contract is not None else None)
        bodies.append(localize_body(
            part["host_link"], mass_kg, cg_a0_m, inertia_a0, q0_base,
            material, part["name"], motion_class=motion_class,
        ))
        hardware_counts[material] += 1

    bundle_assignment_records = []
    for segment in centerline_doc["segments"]:
        hosts = tuple(segment["host_links"])
        if not hosts or any(host not in VALID_HOSTS for host in hosts):
            raise ContractError(f"invalid hosts for segment {segment['id']}: {hosts}")
        sampled_points: list[np.ndarray] = []
        sampled_weights: list[np.ndarray] = []
        for section in segment["sections"]:
            points, weights = quadrature(section_points(section))
            sampled_points.append(points)
            sampled_weights.append(weights)
        points_mm = np.vstack(sampled_points)
        weights_mm = np.concatenate(sampled_weights)
        sampled_length = float(np.sum(weights_mm))
        declared_length = float(segment["path_length_mm"])
        if sampled_length <= 0.0 or declared_length <= 0.0:
            raise ContractError(f"non-positive length for {segment['id']}")
        weights_mm *= declared_length / sampled_length
        total_mass_kg = declared_length / 1000.0 * BUNDLE_LINEAR_DENSITY_G_PER_M / 1000.0
        point_mass_kg = weights_mm / declared_length * total_mass_kg
        host_fraction = 1.0 / len(hosts)
        dynamic_pose_replaced = bool(
            motion_contract is not None and segment["id"] == V9F_DYNAMIC_SEGMENT_ID
        )
        for host in hosts:
            mass, cg_a0_m, inertia_a0 = aggregate_point_masses(points_mm / 1000.0, point_mass_kg * host_fraction)
            bodies.append(localize_body(
                host, mass, cg_a0_m, inertia_a0, q0_base, "bundle",
                segment["id"], dynamic_pose_replaced=dynamic_pose_replaced,
            ))
        bundle_assignment_records.append(
            {
                "segment_id": segment["id"],
                "declared_path_length_mm": declared_length,
                "sampled_path_length_before_normalization_mm": sampled_length,
                "assigned_hosts": list(hosts),
                "host_fraction_each": host_fraction,
                "total_bundle_mass_kg": total_mass_kg,
                "configuration_pose_model": (
                    "ANALYTIC_SECTION_REBUILD_EACH_CONFIGURATION"
                    if dynamic_pose_replaced else "RIGID_HOST_ALLOCATION"
                ),
            }
        )

    model_note = {
        "hardware_part_counts": hardware_counts,
        "bundle_host_allocation": (
            "Each segment retains the builder's equal host split for q0 registry cross-check. "
            "For V9F SEG-04 only, those static shares are excluded from posed aggregates and "
            "replaced by an analytic per-configuration distributed centerline rebuild with "
            "unchanged total declared length and mass. Other segments retain the rigid-host "
            "candidate allocation."
        ),
        "bundle_segments": bundle_assignment_records,
        "v9f_receipt_motion_binding": (
            None if motion_contract is None else {
                "mesh_embedded_motion_class_count": sum(
                    1 for part in parts_doc["parts"] if part.get("motion_class") is not None
                ),
                "binding_source": "B601_ROUTE_C_BUILD_RECEIPT_V9F.parts[name].motion_class",
                "class_counts": motion_contract["class_counts"],
                "class_mass_kg": motion_contract["class_mass_kg"],
                "parsed_laws": motion_contract["parsed_laws"],
                "bundle_distributed_kinematics_status": "EVALUATED_ANALYTIC_V9F_SECTION_REBUILD",
                "mass_property_model_complete_for_frozen_v9f_motion_contract": True,
            }
        ),
    }
    return bodies, model_note, motion_contract


def extract_binding(configuration: dict[str, Any], bindings: dict[str, Any]) -> tuple[str, str, list[float], dict[str, Any]]:
    # V2 contract: the frozen R2 schema calls this array ``composition``.  There
    # is intentionally no fallback to V1's erroneous ``components`` key.
    composition = configuration.get("composition")
    if not isinstance(composition, list):
        raise ContractError(f"{configuration.get('configuration_id')} lacks composition list")
    matches = [item for item in composition if "b601_complete_arm" in str(item.get("component_id", ""))]
    if len(matches) != 1:
        raise ContractError(f"{configuration.get('configuration_id')} must contain exactly one B601 composition member; found {len(matches)}")
    transform_ref = matches[0].get("transform_ref")
    marker = "#transform_library.arm_named_pose_bindings."
    if not isinstance(transform_ref, str) or marker not in transform_ref:
        raise ContractError(f"{configuration.get('configuration_id')} has invalid arm transform_ref: {transform_ref!r}")
    binding_name = transform_ref.split(marker, 1)[1]
    if binding_name not in bindings:
        raise ContractError(f"{configuration.get('configuration_id')} references absent binding {binding_name}")
    binding = bindings[binding_name]
    q = binding.get("q_rad")
    if not isinstance(q, list) or len(q) != 6 or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in q):
        raise ContractError(f"{configuration.get('configuration_id')} binding {binding_name} has invalid q_rad")
    return transform_ref, binding_name, [float(value) for value in q], binding


def transform_a0_points_to_s(
    points_mm: np.ndarray, host: str, transforms_s: dict[str, np.ndarray],
    q0_base: dict[str, np.ndarray],
) -> np.ndarray:
    """Move q0 A0 points through one accepted URDF host into current S."""
    T0 = q0_base[host]
    current = transforms_s[host]
    local_mm = (np.asarray(points_mm, dtype=float) - T0[:3, 3]) @ T0[:3, :3]
    return local_mm @ current[:3, :3].T + current[:3, 3]


def v9f_dynamic_bundle_body(
    contract: dict[str, Any], q4: float, transforms_s: dict[str, np.ndarray],
    q0_base: dict[str, np.ndarray],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rebuild V9F SEG-04 at q4 without changing its declared mass/length."""
    segment = contract["dynamic_segment"]
    sections = segment["sections"]
    j4 = contract["j4"]
    annulus = contract["annulus"]
    x_center = float(contract["x_center"](q4))
    beta_rad = float(contract["beta"](q4))

    fixed_a = np.asarray(j4["plane_A_fixed_point_mm"], dtype=float)
    fixed_b = np.asarray(j4["plane_B_fixed_point_mm"], dtype=float)
    plane_a = fixed_a.copy()
    plane_b = fixed_b.copy()
    plane_a[0] = x_center
    plane_b[0] = x_center
    trombone_center = np.asarray(j4["trombone_center_q0_mm"], dtype=float)
    trombone_center[0] = x_center

    q4_sections_a0 = [
        section_points(sections[0]),
        line_points(fixed_a, plane_a, 1.5),
        arc_points(
            trombone_center,
            np.asarray(sections[2]["basis_e1"], dtype=float),
            np.asarray(sections[2]["basis_e2"], dtype=float),
            float(sections[2]["radius_mm"]),
            math.radians(float(sections[2]["start_angle_deg"])),
            math.radians(float(sections[2]["start_angle_deg"] + sections[2]["sweep_deg"])),
            1.5,
        ),
        line_points(plane_b, fixed_b, 1.5),
        section_points(sections[4]),
        arc_points(
            np.asarray(annulus["axis_origin_A0_mm"], dtype=float),
            np.asarray(annulus["basis_e1"], dtype=float),
            np.asarray(annulus["basis_e2"], dtype=float),
            float(annulus["radius_mm"]),
            contract["alpha0_rad"],
            contract["alpha0_rad"] - beta_rad,
            1.5,
        ),
    ]
    downstream_a0 = section_points(sections[6])

    points_s_mm: list[np.ndarray] = []
    weights_mm: list[np.ndarray] = []
    for points_a0 in q4_sections_a0:
        _, weights = quadrature(points_a0)
        points_s_mm.append(transform_a0_points_to_s(points_a0, "link3", transforms_s, q0_base))
        weights_mm.append(weights)
    _, downstream_weights = quadrature(downstream_a0)
    points_s_mm.append(transform_a0_points_to_s(downstream_a0, "link4", transforms_s, q0_base))
    weights_mm.append(downstream_weights)

    all_points_s_mm = np.vstack(points_s_mm)
    all_weights_mm = np.concatenate(weights_mm)
    sampled_length_mm = float(np.sum(all_weights_mm))
    declared_length_mm = float(segment["path_length_mm"])
    if sampled_length_mm <= 0.0 or declared_length_mm <= 0.0:
        raise ContractError("V9F dynamic SEG-04 has non-positive length")
    all_weights_mm *= declared_length_mm / sampled_length_mm
    total_mass_kg = (
        declared_length_mm / 1000.0 * BUNDLE_LINEAR_DENSITY_G_PER_M / 1000.0
    )
    point_mass_kg = all_weights_mm / declared_length_mm * total_mass_kg
    mass, cg_s_m, inertia_s = aggregate_point_masses(
        all_points_s_mm / 1000.0, point_mass_kg
    )

    annular_endpoint_s = points_s_mm[5][-1]
    follower_q0_a0 = np.asarray(annulus["moving_endpoint_q0_mm"], dtype=float)[None, :]
    follower_expected_s = transform_a0_points_to_s(
        follower_q0_a0, "link4", transforms_s, q0_base
    )[0]
    follower_residual_mm = float(np.linalg.norm(annular_endpoint_s - follower_expected_s))

    trombone_r = float(j4["trombone_u_radius_mm"])
    leg_length_mm = float(fixed_a[0] - x_center)
    trombone_length_mm = 2.0 * leg_length_mm + math.pi * trombone_r
    bridge_length_mm = float(np.linalg.norm(
        fixed_b - np.asarray(annulus["fixed_entry_mm"], dtype=float)
    ))
    annulus_length_mm = float(annulus["radius_mm"]) * beta_rad
    exchange_length_mm = trombone_length_mm + bridge_length_mm + annulus_length_mm
    exchange_reference_mm = float(
        j4["constant_length_proof"]["exchange_subsystem_constant_length_mm"]
    )
    exchange_residual_mm = exchange_length_mm - exchange_reference_mm
    overlap_mm = (
        contract["stage_count"] * contract["stage_length_mm"] - leg_length_mm
    ) / (contract["stage_count"] - 1.0)
    stop_min, stop_max = sorted(float(value) for value in j4["hard_stop_center_x_mm"])
    q_min, q_max = contract["full_limits_rad"]
    physical_guide_sweep_rad = math.radians(abs(float(annulus["physical_guide_sweep_deg"])))
    tolerance_mm = contract["residual_tolerance_mm"]
    checks = {
        "q4_within_full_hardware_limits": q_min <= q4 <= q_max,
        "trombone_center_within_hard_stops": stop_min <= x_center <= stop_max,
        "minimum_stage_overlap_satisfied": overlap_mm >= contract["minimum_overlap_mm"],
        "annular_guide_covers_configuration": beta_rad <= physical_guide_sweep_rad,
        "constant_length_residual_within_frozen_tolerance": abs(exchange_residual_mm) <= tolerance_mm,
        "follower_closure_residual_within_frozen_tolerance": follower_residual_mm <= tolerance_mm,
    }
    diagnostics = {
        "bundle_distributed_kinematics_status": "EVALUATED_ANALYTIC_V9F_SECTION_REBUILD",
        "mass_property_model_complete": bool(all(checks.values())),
        "q4_rad": q4,
        "x_center_mm": x_center,
        "delta_x_from_q0_mm": x_center - float(j4["center_x_at_q0_mm"]),
        "beta_rad": beta_rad,
        "beta_deg": math.degrees(beta_rad),
        "stage_overlap_mm": overlap_mm,
        "sampled_length_before_declared_length_normalization_mm": sampled_length_mm,
        "declared_length_mm": declared_length_mm,
        "exchange_subsystem_length_mm": exchange_length_mm,
        "exchange_subsystem_reference_length_mm": exchange_reference_mm,
        "exchange_subsystem_residual_mm": exchange_residual_mm,
        "follower_closure_residual_mm": follower_residual_mm,
        "frozen_machine_residual_tolerance_mm": tolerance_mm,
        "checks": checks,
        "all_checks_pass": bool(all(checks.values())),
        "qualification_exclusions": [
            "installed_bundle_resistance_torque remains HOLD_UNKNOWN_TORSION",
            "follower contact/preload/tribology qualification remains HOLD",
            "mass-property kinematic evaluation does not grant TMG2 or release credit",
        ],
    }
    return {"mass_kg": mass, "cg": cg_s_m, "inertia_cg": inertia_s}, diagnostics


def pose_bodies(
    bodies: list[dict[str, Any]], q: list[float], joints: list[dict[str, Any]],
    mount: np.ndarray, q0_base: dict[str, np.ndarray],
    motion_contract: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, np.ndarray | float]], dict[str, Any]]:
    transforms_s, _ = fk_all(q, joints, mount)
    groups: dict[str, list[dict[str, Any]]] = {"aluminum": [], "polymer": [], "bundle": []}
    applied_counts: dict[str, int] = {}
    applied_mass_kg: dict[str, float] = {}
    delta_x_mm = 0.0
    if motion_contract is not None:
        delta_x_mm = float(motion_contract["x_center"](q[3]) -
                           motion_contract["x_center"](0.0))
    for body in bodies:
        if body.get("dynamic_pose_replaced"):
            continue
        T = mount if body["host"] == "bus" else transforms_s[body["host"]]
        R = T[:3, :3]
        cg_local = np.asarray(body["cg_local_m"], dtype=float).copy()
        motion_class = body.get("motion_class")
        if motion_class is not None:
            applied_counts[motion_class] = applied_counts.get(motion_class, 0) + 1
            applied_mass_kg[motion_class] = (
                applied_mass_kg.get(motion_class, 0.0) + float(body["mass_kg"])
            )
        if motion_class in V9F_MOTION_FRACTIONS:
            if body["host"] != "link3" or motion_contract is None:
                raise ContractError(f"cannot apply {motion_class} to {body['source']}")
            fraction = V9F_MOTION_FRACTIONS[motion_class]
            delta_a0_m = np.array((fraction * delta_x_mm / 1000.0, 0.0, 0.0))
            cg_local += q0_base["link3"][:3, :3].T @ delta_a0_m
        elif motion_class in V9F_RIGID_LINK4_CLASSES:
            if body["host"] != "link4" or motion_contract is None:
                raise ContractError(f"cannot apply {motion_class} to {body['source']}")
            # FOLLOWER_LINK4 and FIXED_LINK4 are both rigid link4 bodies.  The
            # former's analytic follower closure is independently checked by
            # the distributed SEG-04 rebuild above.
        elif motion_class is not None:
            raise ContractError(f"unsupported motion_class during pose: {motion_class}")
        cg_s = R @ cg_local + T[:3, 3] / 1000.0
        inertia_s = R @ body["inertia_local_kg_m2"] @ R.T
        groups[body["group"]].append({"mass_kg": body["mass_kg"], "cg": cg_s, "inertia_cg": inertia_s})

    dynamic_diagnostics = None
    if motion_contract is not None:
        expected_counts = {
            key: int(motion_contract["class_counts"].get(key, 0))
            for key in V9F_ALLOWED_MOTION_CLASSES
        }
        if applied_counts != expected_counts:
            raise ContractError(
                f"V9F posed motion-class counts differ from receipt: "
                f"applied={applied_counts}, expected={expected_counts}"
            )
        dynamic_body, dynamic_diagnostics = v9f_dynamic_bundle_body(
            motion_contract, q[3], transforms_s, q0_base
        )
        groups["bundle"].append(dynamic_body)
    output: dict[str, dict[str, np.ndarray | float]] = {}
    for group, members in groups.items():
        if not members:
            output[group] = {"mass_kg": 0.0, "first_moment_kg_m": np.zeros(3), "inertia_about_S_origin_kg_m2": np.zeros((3, 3))}
            continue
        mass, cg, inertia_cg = combine_bodies(members)
        output[group] = {
            "mass_kg": mass,
            "first_moment_kg_m": mass * cg,
            "inertia_about_S_origin_kg_m2": parallel_axis(inertia_cg, mass, cg),
        }
    motion_diagnostics = {
        "motion_contract_applied": motion_contract is not None,
        "hardware_motion_class_counts_applied": applied_counts,
        "hardware_motion_class_counts_expected_from_receipt": (
            None if motion_contract is None else {
                key: int(motion_contract["class_counts"].get(key, 0))
                for key in V9F_ALLOWED_MOTION_CLASSES
            }
        ),
        "hardware_motion_class_mass_kg_applied": applied_mass_kg,
        "hardware_delta_x_full_travel_from_q0_mm": delta_x_mm,
        "follower_link4_rule": (
            "rigid accepted-URDF link4 FK plus independent analytic annular closure check"
            if motion_contract is not None else "NOT_APPLICABLE"
        ),
        "distributed_bundle": dynamic_diagnostics,
        "all_checks_pass": bool(
            dynamic_diagnostics is None or dynamic_diagnostics["all_checks_pass"]
        ),
    }
    return output, motion_diagnostics


def measurement(scales: np.ndarray, baseline_mass: float, baseline_cg: np.ndarray, baseline_inertia_cg: np.ndarray, group_aggregates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    group_names = ("aluminum", "polymer", "bundle")
    baseline_origin = parallel_axis(baseline_inertia_cg, baseline_mass, baseline_cg)
    delta_mass = 0.0
    delta_first = np.zeros(3)
    delta_origin = np.zeros((3, 3))
    for scale, group in zip(scales, group_names):
        aggregate = group_aggregates[group]
        delta_mass += float(scale) * float(aggregate["mass_kg"])
        delta_first += float(scale) * np.asarray(aggregate["first_moment_kg_m"], dtype=float)
        delta_origin += float(scale) * np.asarray(aggregate["inertia_about_S_origin_kg_m2"], dtype=float)
    updated_mass = baseline_mass + delta_mass
    updated_cg = (baseline_mass * baseline_cg + delta_first) / updated_mass
    updated_origin = baseline_origin + delta_origin
    updated_cg_inertia = updated_origin - updated_mass * ((updated_cg @ updated_cg) * np.eye(3) - np.outer(updated_cg, updated_cg))
    delta_cg = updated_cg - baseline_cg
    return {
        "delta_mass": delta_mass,
        "updated_mass": updated_mass,
        "updated_cg": updated_cg,
        "delta_cg": delta_cg,
        "baseline_origin": baseline_origin,
        "delta_origin": delta_origin,
        "updated_origin": updated_origin,
        "updated_cg_inertia": updated_cg_inertia,
        "delta_own_cg_inertia": updated_cg_inertia - baseline_inertia_cg,
    }


def measurement_vector(result: dict[str, Any]) -> np.ndarray:
    return np.concatenate(
        (
            [result["updated_mass"]],
            result["updated_cg"],
            vector6(result["updated_cg_inertia"]),
            vector6(result["updated_origin"]),
        )
    )


def uncertainty_propagation(baseline_mass: float, baseline_cg: np.ndarray, baseline_inertia_cg: np.ndarray, groups: dict[str, dict[str, Any]], seed: int, sample_count: int) -> dict[str, Any]:
    u_scale = np.array(
        (
            HARDWARE_RELATIVE_STANDARD_UNCERTAINTY,
            HARDWARE_RELATIVE_STANDARD_UNCERTAINTY,
            BUNDLE_STANDARD_UNCERTAINTY_G_PER_M / BUNDLE_LINEAR_DENSITY_G_PER_M,
        ),
        dtype=float,
    )
    nominal = np.ones(3)
    step = 1.0e-6
    sensitivities = []
    for index in range(3):
        plus = nominal.copy()
        minus = nominal.copy()
        plus[index] += step
        minus[index] -= step
        y_plus = measurement_vector(measurement(plus, baseline_mass, baseline_cg, baseline_inertia_cg, groups))
        y_minus = measurement_vector(measurement(minus, baseline_mass, baseline_cg, baseline_inertia_cg, groups))
        sensitivities.append((y_plus - y_minus) / (2.0 * step))
    sensitivity = np.vstack(sensitivities).T
    gum_u = np.sqrt(np.sum((sensitivity * u_scale[None, :]) ** 2, axis=1))

    rng = np.random.default_rng(seed)
    scales = np.empty((sample_count, 3), dtype=float)
    scales[:, 0] = rng.normal(1.0, u_scale[0], sample_count)
    scales[:, 1] = rng.normal(1.0, u_scale[1], sample_count)
    half_relative = BUNDLE_CONSERVATIVE_HALF_WIDTH_G_PER_M / BUNDLE_LINEAR_DENSITY_G_PER_M
    scales[:, 2] = rng.uniform(1.0 - half_relative, 1.0 + half_relative, sample_count)

    # The aggregate measurement model is vectorized for deterministic MC replay.
    group_names = ("aluminum", "polymer", "bundle")
    masses = np.array([groups[name]["mass_kg"] for name in group_names], dtype=float)
    firsts = np.stack([groups[name]["first_moment_kg_m"] for name in group_names])
    origins = np.stack([groups[name]["inertia_about_S_origin_kg_m2"] for name in group_names])
    delta_mass = scales @ masses
    updated_mass = baseline_mass + delta_mass
    updated_first = baseline_mass * baseline_cg + scales @ firsts
    updated_cg = updated_first / updated_mass[:, None]
    baseline_origin = parallel_axis(baseline_inertia_cg, baseline_mass, baseline_cg)
    updated_origin = baseline_origin[None, :, :] + np.einsum("ng,gij->nij", scales, origins)
    norm2 = np.einsum("ni,ni->n", updated_cg, updated_cg)
    shift = updated_mass[:, None, None] * (norm2[:, None, None] * np.eye(3)[None, :, :] - np.einsum("ni,nj->nij", updated_cg, updated_cg))
    updated_cg_inertia = updated_origin - shift
    samples = np.concatenate(
        (
            updated_mass[:, None],
            updated_cg,
            np.stack(
                (
                    updated_cg_inertia[:, 0, 0], updated_cg_inertia[:, 1, 1], updated_cg_inertia[:, 2, 2],
                    updated_cg_inertia[:, 0, 1], updated_cg_inertia[:, 0, 2], updated_cg_inertia[:, 1, 2],
                ),
                axis=1,
            ),
            np.stack(
                (
                    updated_origin[:, 0, 0], updated_origin[:, 1, 1], updated_origin[:, 2, 2],
                    updated_origin[:, 0, 1], updated_origin[:, 0, 2], updated_origin[:, 1, 2],
                ),
                axis=1,
            ),
        ),
        axis=1,
    )
    mc_u = np.std(samples, axis=0, ddof=1)
    q025, q975 = np.quantile(samples, (0.025, 0.975), axis=0)
    significant = gum_u > 1.0e-12
    relative_difference = np.zeros_like(gum_u)
    relative_difference[significant] = np.abs(mc_u[significant] - gum_u[significant]) / gum_u[significant]
    labels = (
        "updated_mass_kg", "updated_cg_x_m", "updated_cg_y_m", "updated_cg_z_m",
        "updated_Icg_Ixx_kg_m2", "updated_Icg_Iyy_kg_m2", "updated_Icg_Izz_kg_m2",
        "updated_Icg_Ixy_kg_m2", "updated_Icg_Ixz_kg_m2", "updated_Icg_Iyz_kg_m2",
        "updated_IOs_Ixx_kg_m2", "updated_IOs_Iyy_kg_m2", "updated_IOs_Izz_kg_m2",
        "updated_IOs_Ixy_kg_m2", "updated_IOs_Ixz_kg_m2", "updated_IOs_Iyz_kg_m2",
    )
    return {
        "method": "First-order GUM sensitivity coefficients plus deterministic Monte Carlo diagnostic",
        "scope": "Route-C increment input uncertainty only; baseline/output joint covariance is unavailable, so no combined updated-system uncertainty or conformity decision is claimed",
        "input_variables": [
            {"name": "aluminum_density_scale", "estimate": 1.0, "standard_uncertainty": float(u_scale[0]), "distribution": "normal engineering allocation", "degrees_of_freedom": "infinite_assumed", "correlation": "fully correlated across all aluminum parts"},
            {"name": "polymer_density_scale", "estimate": 1.0, "standard_uncertainty": float(u_scale[1]), "distribution": "normal engineering allocation", "degrees_of_freedom": "infinite_assumed", "correlation": "fully correlated across all polymer parts"},
            {"name": "bundle_linear_density_scale", "estimate": 1.0, "standard_uncertainty": float(u_scale[2]), "distribution": "rectangular conservative symmetric interval", "degrees_of_freedom": "infinite_Type_B", "correlation": "fully correlated along all bundle segments"},
        ],
        "independence_between_input_variables": True,
        "output_order": list(labels),
        "gum_standard_uncertainty": {label: float(value) for label, value in zip(labels, gum_u)},
        "sensitivity_coefficients_by_output": {
            label: {group: float(sensitivity[row, col]) for col, group in enumerate(("aluminum_density_scale", "polymer_density_scale", "bundle_linear_density_scale"))}
            for row, label in enumerate(labels)
        },
        "monte_carlo": {
            "seed": seed,
            "sample_count": sample_count,
            "standard_uncertainty": {label: float(value) for label, value in zip(labels, mc_u)},
            "equal_tail_95_percent_interval": {label: [float(lo), float(hi)] for label, lo, hi in zip(labels, q025, q975)},
            "negative_scale_sample_count": int(np.sum(np.any(scales <= 0.0, axis=1))),
        },
        "linearization_diagnostic": {
            "comparison": "absolute relative difference between MC and first-order standard uncertainties where u_GUM > 1e-12",
            "maximum_relative_difference": float(np.max(relative_difference)),
            "formal_JCGM_101_clause_8_verdict": "NOT_CLAIMED_NO_APPROVED_REPORTING_RESOLUTION_OR_CONFORMITY_RULE",
        },
    }


def pose_limit_check(q: list[float], limits: dict[str, tuple[float, float]], joints: list[dict[str, Any]]) -> dict[str, Any]:
    names = [str(joint["name"]) for joint in joints if joint["type"] == "revolute"]
    records = []
    for name, value in zip(names, q):
        lower, upper = limits[name]
        records.append({"joint": name, "q_rad": value, "lower_rad": lower, "upper_rad": upper, "within_limit": lower <= value <= upper})
    return {"all_within_accepted_urdf_limits": all(record["within_limit"] for record in records), "joints": records}


def baseline_uncertainty_record(configuration: dict[str, Any]) -> dict[str, Any]:
    return {
        "semantics": "input standard uncertainties carried as metrology metadata; they are not acceptance limits and are not combined with Route-C uncertainty because required covariance/correlation information is unavailable",
        "mass_standard_uncertainty_kg": float(configuration["mass"]["standard_uncertainty_kg"]),
        "cg_standard_uncertainty_xyz_m": [float(value) for value in configuration["center_of_mass"]["standard_uncertainty_xyz_m"]],
        "inertia_standard_uncertainty_components_kg_m2": {name: float(configuration["inertia"]["standard_uncertainty_components_kg_m2"][name]) for name in COMPONENT_ORDER},
        "updated_system_combined_standard_uncertainty": None,
        "combined_uncertainty_status": "NOT_COMPUTED_MISSING_BASELINE_ROUTE_C_CROSS_COVARIANCE_AND_COUPLED_MEASUREMENT_MODEL",
    }


def configuration_record(
    configuration: dict[str, Any], bindings: dict[str, Any],
    bodies: list[dict[str, Any]], joints: list[dict[str, Any]],
    limits: dict[str, tuple[float, float]], mount: np.ndarray,
    q0_base: dict[str, np.ndarray], motion_contract: dict[str, Any] | None,
    index: int, sample_count: int,
) -> dict[str, Any]:
    transform_ref, binding_name, q, binding = extract_binding(configuration, bindings)
    binding_gate = binding_gate_assessment(binding)
    groups, motion_diagnostics = pose_bodies(
        bodies, q, joints, mount, q0_base, motion_contract
    )
    baseline_mass = float(configuration["mass"]["value_kg"])
    baseline_cg = np.asarray(configuration["center_of_mass"]["xyz_m"], dtype=float)
    baseline_inertia = inertia_matrix(configuration["inertia"]["components_kg_m2"])
    nominal = measurement(np.ones(3), baseline_mass, baseline_cg, baseline_inertia, groups)
    uncertainty = uncertainty_propagation(baseline_mass, baseline_cg, baseline_inertia, groups, 260826 + index, sample_count)
    translation_residual = nominal["updated_origin"] - parallel_axis(nominal["updated_cg_inertia"], nominal["updated_mass"], nominal["updated_cg"])
    delta_mass_by_group = {name: float(groups[name]["mass_kg"]) for name in ("aluminum", "polymer", "bundle")}
    baseline_u = baseline_uncertainty_record(configuration)
    delta_i_cg = nominal["delta_own_cg_inertia"]
    diagnostic_ratios = {
        "warning": "dimensionless diagnostic only; standard uncertainty is not an acceptance limit",
        "mass_delta_over_baseline_standard_uncertainty": abs(nominal["delta_mass"]) / baseline_u["mass_standard_uncertainty_kg"] if baseline_u["mass_standard_uncertainty_kg"] > 0.0 else None,
        "cg_delta_abs_over_baseline_standard_uncertainty_xyz": [abs(float(value)) / float(u) if float(u) > 0.0 else None for value, u in zip(nominal["delta_cg"], baseline_u["cg_standard_uncertainty_xyz_m"])],
        "own_cg_inertia_delta_abs_over_baseline_standard_uncertainty": {name: abs(float(value)) / baseline_u["inertia_standard_uncertainty_components_kg_m2"][name] if baseline_u["inertia_standard_uncertainty_components_kg_m2"][name] > 0.0 else None for name, value in zip(COMPONENT_ORDER, vector6(delta_i_cg))},
    }
    checks = {
        "arm_pose_binding_nonempty": bool(transform_ref and binding_name),
        "q_rad_has_six_finite_values": len(q) == 6 and all(math.isfinite(value) for value in q),
        "joint_limits": pose_limit_check(q, limits, joints),
        "baseline_inertia_about_baseline_cg": inertia_checks(baseline_inertia),
        "updated_inertia_about_updated_cg": inertia_checks(nominal["updated_cg_inertia"]),
        "updated_inertia_about_fixed_S_origin": inertia_checks(nominal["updated_origin"]),
        "parallel_axis_round_trip_max_abs_residual_kg_m2": float(np.max(np.abs(translation_residual))),
        "parallel_axis_round_trip": float(np.max(np.abs(translation_residual))) <= 1.0e-10,
        "mass_positive": nominal["updated_mass"] > 0.0,
        "cg_finite": bool(np.isfinite(nominal["updated_cg"]).all()),
        "v9f_motion_kinematics": motion_diagnostics,
    }
    checks["all_physical_consistency_checks_pass"] = bool(
        checks["arm_pose_binding_nonempty"]
        and checks["q_rad_has_six_finite_values"]
        and checks["joint_limits"]["all_within_accepted_urdf_limits"]
        and checks["baseline_inertia_about_baseline_cg"]["positive_semidefinite"]
        and checks["baseline_inertia_about_baseline_cg"]["triangle_inequalities"]
        and checks["updated_inertia_about_updated_cg"]["positive_semidefinite"]
        and checks["updated_inertia_about_updated_cg"]["triangle_inequalities"]
        and checks["parallel_axis_round_trip"]
        and checks["mass_positive"]
        and checks["cg_finite"]
        and checks["v9f_motion_kinematics"]["all_checks_pass"]
    )
    return {
        "configuration_id": configuration["configuration_id"],
        "name": configuration["name"],
        "pose_binding": {
            "source_collection": "configuration.composition",
            "transform_ref": transform_ref,
            "binding_name": binding_name,
            "q_rad": q,
            "binding_revalidation_status": binding.get("revalidation_status"),
            "binding_classification": binding.get("classification"),
            "gate_state": binding_gate["state"],
            "gate_reason": binding_gate["reason"],
        },
        "coordinate_and_reference_contract": {
            "frame": "S",
            "units": {"mass": "kg", "position": "m", "inertia": "kg*m^2"},
            "input_center_of_mass_reference_point": "baseline system center of mass listed below",
            "output_center_of_mass_reference_point": "updated system center of mass listed below",
            "fixed_comparable_reference_point": {"name": "O_S", "xyz_m_in_S": [0.0, 0.0, 0.0]},
            "comparison_rule": "Only inertia tensors expressed about the same fixed point O_S are direct before/after comparands. The own-CG delta is reported but changes reference point.",
        },
        "mass": {
            "baseline_kg": baseline_mass,
            "route_c_increment_kg": float(nominal["delta_mass"]),
            "route_c_increment_by_uncertainty_group_kg": delta_mass_by_group,
            "updated_kg": float(nominal["updated_mass"]),
        },
        "center_of_mass": {
            "baseline_xyz_m_in_S": [float(value) for value in baseline_cg],
            "route_c_increment_subassembly_xyz_m_in_S": [float(value) for value in sum(np.asarray(groups[name]["first_moment_kg_m"]) for name in groups) / nominal["delta_mass"]],
            "updated_xyz_m_in_S": [float(value) for value in nominal["updated_cg"]],
            "delta_xyz_m": [float(value) for value in nominal["delta_cg"]],
        },
        "inertia": {
            "baseline_about_baseline_cg_in_S_kg_m2": {"matrix_3x3": matrix_rows(baseline_inertia), "components": matrix_components(baseline_inertia)},
            "updated_about_updated_cg_in_S_kg_m2": {"matrix_3x3": matrix_rows(nominal["updated_cg_inertia"]), "components": matrix_components(nominal["updated_cg_inertia"])},
            "own_cg_reference_points_differ_delta_kg_m2": {"matrix_3x3": matrix_rows(delta_i_cg), "components": matrix_components(delta_i_cg), "direct_fixed_point_comparison": False},
            "baseline_about_fixed_S_origin_kg_m2": {"matrix_3x3": matrix_rows(nominal["baseline_origin"]), "components": matrix_components(nominal["baseline_origin"])},
            "route_c_increment_about_fixed_S_origin_kg_m2": {"matrix_3x3": matrix_rows(nominal["delta_origin"]), "components": matrix_components(nominal["delta_origin"])},
            "updated_about_fixed_S_origin_kg_m2": {"matrix_3x3": matrix_rows(nominal["updated_origin"]), "components": matrix_components(nominal["updated_origin"])},
        },
        "uncertainty": {"baseline_input": baseline_u, "route_c_increment_propagation": uncertainty},
        "diagnostic_only_not_acceptance": diagnostic_ratios,
        "conformity_assessment": {
            "ODR_50_qualitative_trigger": "Route-C changes system mass/CG/inertia beyond current uncertainty envelope",
            "approved_numerical_acceptance_rule": None,
            "baseline_standard_uncertainty_used_as_acceptance_limit": False,
            "decision": "NOT_EVALUATED_NO_APPROVED_NUMERICAL_ACCEPTANCE_RULE",
            "TMG2_reopen_conclusion": "NOT_ISSUED_BY_THIS_TOOL",
        },
        "physical_consistency": checks,
    }


def registry_cross_check(bodies: list[dict[str, Any]], registry: dict[str, Any]) -> dict[str, Any]:
    exact: dict[str, dict[str, float]] = {}
    for body in bodies:
        host = body["host"]
        row = exact.setdefault(host, {"hardware_kg": 0.0, "bundle_kg": 0.0})
        key = "bundle_kg" if body["group"] == "bundle" else "hardware_kg"
        row[key] += body["mass_kg"]
    records = []
    for candidate in registry["mass_delta_by_link"]:
        host = candidate["host_link"]
        row = exact.get(host, {"hardware_kg": 0.0, "bundle_kg": 0.0})
        records.append(
            {
                "host_link": host,
                "registry_rounded_hardware_kg": float(candidate["hardware_g"]) / 1000.0,
                "registry_rounded_bundle_kg": float(candidate["bundle_g"]) / 1000.0,
                "recomputed_hardware_kg": float(row["hardware_kg"]),
                "recomputed_bundle_kg": float(row["bundle_kg"]),
                "hardware_residual_kg": float(row["hardware_kg"] - float(candidate["hardware_g"]) / 1000.0),
                "bundle_residual_kg": float(row["bundle_kg"] - float(candidate["bundle_g"]) / 1000.0),
            }
        )
    max_residual = max(max(abs(row["hardware_residual_kg"]), abs(row["bundle_residual_kg"])) for row in records)
    return {
        "semantics": "Cross-check against builder's two-decimal gram registry; this is not a second mass source",
        "records": records,
        "maximum_absolute_residual_kg": max_residual,
        "within_rounding_tolerance_5p1e_minus_6_kg": max_residual <= 5.1e-6,
    }


def run_synthetic_self_tests() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    fixture = {
        "configuration_id": "FIXTURE",
        "composition": [{"component_id": "b601_complete_arm_fixture", "transform_ref": "fixture.yaml#transform_library.arm_named_pose_bindings.POSE"}],
        "components": [],
    }
    binding_fixture = {"POSE": {"q_rad": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}}
    try:
        _, name, q, _ = extract_binding(fixture, binding_fixture)
        passed = name == "POSE" and q == binding_fixture["POSE"]["q_rad"]
        detail = "composition binding consumed; empty components ignored"
    except Exception as exc:  # pragma: no cover - recorded in self-test artifact
        passed, detail = False, repr(exc)
    results.append({"test": "composition_not_components_regression_guard", "pass": passed, "detail": detail})

    missing = {"configuration_id": "MISSING", "composition": []}
    try:
        extract_binding(missing, binding_fixture)
        passed, detail = False, "missing binding was accepted"
    except ContractError as exc:
        passed, detail = True, str(exc)
    results.append({"test": "missing_pose_binding_fails_closed", "pass": passed, "detail": detail})

    I0 = np.diag((1.0, 1.0, 1.0))
    base_mass = 2.0
    base_cg = np.array((1.0, 0.0, 0.0))
    groups = {
        "aluminum": {"mass_kg": 1.0, "first_moment_kg_m": np.array((0.0, 1.0, 0.0)), "inertia_about_S_origin_kg_m2": np.diag((1.0, 0.0, 1.0))},
        "polymer": {"mass_kg": 0.0, "first_moment_kg_m": np.zeros(3), "inertia_about_S_origin_kg_m2": np.zeros((3, 3))},
        "bundle": {"mass_kg": 0.0, "first_moment_kg_m": np.zeros(3), "inertia_about_S_origin_kg_m2": np.zeros((3, 3))},
    }
    result = measurement(np.ones(3), base_mass, base_cg, I0, groups)
    round_trip = parallel_axis(result["updated_cg_inertia"], result["updated_mass"], result["updated_cg"])
    passed = np.allclose(result["updated_cg"], np.array((2.0 / 3.0, 1.0 / 3.0, 0.0)), atol=1e-12) and np.allclose(round_trip, result["updated_origin"], atol=1e-12)
    results.append({"test": "parallel_axis_fixed_reference_round_trip", "pass": bool(passed), "detail": {"updated_cg": [float(value) for value in result["updated_cg"]], "max_residual": float(np.max(np.abs(round_trip - result["updated_origin"])))}})

    full = np.array(((3.0, 0.2, -0.1), (0.2, 4.0, 0.3), (-0.1, 0.3, 5.0)))
    passed = np.allclose(six_to_matrix(vector6(full)), full, atol=0.0)
    results.append({"test": "full_3x3_inertia_off_diagonal_round_trip", "pass": bool(passed), "detail": matrix_components(full)})

    binding_cases = [
        ({"revalidation_status": "PASS_RUNTIME_FK_AND_INERTIA_NO_SOURCE_HOLD",
          "classification": "CANDIDATE_BINDING_OF_ACCEPTED_RUNTIME_DIGITAL_POSE"}, "PASS"),
        ({"revalidation_status": "HELD_CANDIDATE_FK_REGRESSION_FAIL_MAX_RESIDUAL_567P734_MM",
          "classification": "CANDIDATE_BINDING_OF_HELD_STOW_POSE"}, "FAIL"),
        ({"revalidation_status": "PASS_RUNTIME_FK_AND_INERTIA_WITH_SOURCE_CONFIGURATION_RATIFICATION_HOLD",
          "classification": "CANDIDATE_BINDING_OF_RATIFICATION_HELD_POSE"}, "HOLD"),
        ({"revalidation_status": "DIAGNOSTIC_CANDIDATE_HOLD_FOR_CAPTURE_DYNAMICS",
          "classification": "CANDIDATE_BINDING_OF_PROVISIONAL_SCENE_POSE"}, "HOLD"),
    ]
    observed = [binding_gate_assessment(case)["state"] for case, _ in binding_cases]
    expected = [state for _, state in binding_cases]
    results.append({
        "test": "binding_authority_fail_closed_token_classification",
        "pass": observed == expected,
        "detail": {"expected": expected, "observed": observed},
    })

    expected_fractions = {
        "FIXED_LINK3": 0.0,
        "ONE_THIRD_TRAVEL": 1.0 / 3.0,
        "TWO_THIRDS_TRAVEL": 2.0 / 3.0,
        "FULL_TRAVEL": 1.0,
    }
    results.append({
        "test": "v9f_rigid_stage_motion_fraction_contract",
        "pass": V9F_MOTION_FRACTIONS == expected_fractions,
        "detail": V9F_MOTION_FRACTIONS,
    })
    return results


def build_report(variant: str, sample_count: int, include_self_tests: bool) -> dict[str, Any]:
    if not (re.fullmatch(r"V[1-9][0-9]*", variant) or variant == "V9F"):
        raise ContractError(
            "variant must be explicit V<number> or the ODR-58 explicit fallback V9F; aliases such as VF are forbidden")
    paths = {
        "parts": HERE / f"ROUTE_C_SWEEP_MESH_PACK_{variant}" / "rc_parts_mass_geometry.json",
        "centerline": HERE / f"B601_ROUTE_C_HARNESS_CENTERLINE_{variant}.json",
        "mass_registry": HERE / f"B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_{variant}.json",
        "baseline": P_BASELINE,
        "transforms": P_TRANSFORMS,
        "accepted_urdf": P_URDF,
        "mount": P_MOUNT,
        "odr50": P_ODR50,
    }
    if variant == "V9F":
        paths["build_receipt"] = HERE / "B601_ROUTE_C_BUILD_RECEIPT_V9F.json"
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise ContractError(f"missing required inputs: {missing}")
    if sha256_file(P_URDF) != URDF_SHA256_PIN:
        raise ContractError("accepted URDF hash mismatch")

    parts = load_json(paths["parts"])
    centerline = load_json(paths["centerline"])
    registry = load_json(paths["mass_registry"])
    receipt = load_json(paths["build_receipt"]) if "build_receipt" in paths else None
    baseline = load_yaml(P_BASELINE)
    transforms = load_yaml(P_TRANSFORMS)
    mount_doc = load_yaml(P_MOUNT)
    joints, limits = parse_urdf(P_URDF)
    mount = np.asarray(mount_doc["mount"]["transform_mm_rows"], dtype=float)
    mount_rotation_residual = float(np.max(np.abs(mount[:3, :3].T @ mount[:3, :3] - np.eye(3))))
    if mount_rotation_residual > 1.0e-5:
        raise ContractError(f"mount rotation is not orthonormal within 1e-5: {mount_rotation_residual}")
    _, q0_base = fk_all([0.0] * 6, joints, mount)
    bodies, body_model, motion_contract = build_route_c_bodies(
        parts, centerline, q0_base, variant, receipt
    )
    bindings = transforms["transform_library"]["arm_named_pose_bindings"]
    configurations = baseline.get("configurations")
    if not isinstance(configurations, list) or len(configurations) != 9:
        raise ContractError(f"expected exactly nine baseline configurations, found {len(configurations) if isinstance(configurations, list) else 'non-list'}")
    ids = [configuration.get("configuration_id") for configuration in configurations]
    if len(set(ids)) != 9:
        raise ContractError("configuration IDs are not unique")
    records = [
        configuration_record(
            configuration, bindings, bodies, joints, limits, mount,
            q0_base, motion_contract, index, sample_count,
        )
        for index, configuration in enumerate(configurations)
    ]
    all_bindings = all(record["physical_consistency"]["arm_pose_binding_nonempty"] for record in records)
    all_physics = all(record["physical_consistency"]["all_physical_consistency_checks_pass"] for record in records)
    binding_states = {
        record["configuration_id"]: record["pose_binding"]["gate_state"]
        for record in records
    }
    binding_state_counts = {
        state: sum(1 for value in binding_states.values() if value == state)
        for state in ("PASS", "HOLD", "FAIL", "UNKNOWN")
    }
    if binding_state_counts["FAIL"]:
        aggregate_binding_state = "FAIL"
    elif binding_state_counts["HOLD"]:
        aggregate_binding_state = "HOLD"
    elif binding_state_counts["UNKNOWN"]:
        aggregate_binding_state = "UNKNOWN"
    else:
        aggregate_binding_state = "PASS"
    binding_gate_pass = aggregate_binding_state == "PASS"
    mass_property_model_complete = bool(
        all(
            record["physical_consistency"]["v9f_motion_kinematics"]["all_checks_pass"]
            for record in records
        )
    )
    cross_check = registry_cross_check(bodies, registry)
    self_tests = run_synthetic_self_tests() if include_self_tests else []
    execution_checks_pass = bool(
        all_bindings and all_physics and mass_property_model_complete
        and (not include_self_tests or all(item["pass"] for item in self_tests))
    )
    if not execution_checks_pass:
        overall_status = "FAIL_CLOSED_TOOL_OR_PHYSICS_CHECK"
    elif binding_gate_pass:
        overall_status = "PASS_NON_AUTHORIZING_TOOL_EXECUTION"
    else:
        overall_status = (
            "COMPLETE_NON_AUTHORIZING__NINE_CONFIGURATION_BINDING_GATE_"
            + aggregate_binding_state
        )

    report = {
        "schema": "ROUTE_C_MASS_PROPAGATION_V2",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "tool_version": "V2",
        "evaluated_route_c_variant": variant,
        "scope": "NON_AUTHORIZING_MASS_PROPERTY_PROPAGATION",
        "authority": "DESIGN_ANALYSIS_TOOL_OUTPUT_PENDING_OWNER_REVIEW",
        "input_pins": {name: {"path": relpath(path), "sha256": sha256_file(path)} for name, path in paths.items()},
        "global_coordinate_and_units_contract": {
            "frame": "S",
            "fixed_reference_point": {"name": "O_S", "xyz_m_in_S": [0.0, 0.0, 0.0]},
            "mass_unit": "kg",
            "length_unit": "m",
            "inertia_unit": "kg*m^2",
            "CAD_input_length_unit": "mm converted exactly by 1e-3 at the input boundary",
            "CAD_input_mass_density_unit": "g/mm^3 converted to kg and kg*m^2 at the input boundary",
            "mount_rotation_orthonormality_max_abs_residual": mount_rotation_residual,
        },
        "route_c_measurement_model": {
            "hardware_density_nominal_g_per_mm3": DENSITY_G_PER_MM3,
            "bundle_linear_density_nominal_g_per_m": BUNDLE_LINEAR_DENSITY_G_PER_M,
            "bundle_linear_density_bounded_range_g_per_m": list(BUNDLE_BOUNDS_G_PER_M),
            "bundle_conservative_symmetric_half_width_g_per_m": BUNDLE_CONSERVATIVE_HALF_WIDTH_G_PER_M,
            "bundle_linear_density_standard_uncertainty_g_per_m": BUNDLE_STANDARD_UNCERTAINTY_G_PER_M,
            "hardware_relative_standard_uncertainty": HARDWARE_RELATIVE_STANDARD_UNCERTAINTY,
            "uncertainty_acceptance_separation": "All values in this block are input uncertainty assumptions. None is an acceptance limit.",
            "body_model": body_model,
        },
        "mass_registry_cross_check": cross_check,
        "nine_configuration_binding_gate": {
            "expected_count": 9,
            "evaluated_count": len(records),
            "unique_configuration_ids": len(set(ids)) == 9,
            "all_arm_pose_bindings_nonempty": all_bindings,
            "binding_states_by_configuration": binding_states,
            "binding_state_counts": binding_state_counts,
            "aggregate_state": aggregate_binding_state,
            "binding_source_key": "composition",
            "forbidden_legacy_fallback_key": "components",
            "rule": "PASS requires nine unique configurations, nonempty bindings, and every frozen binding authority state PASS; FAIL/HOLD/UNKNOWN never pass",
            "pass": bool(
                len(records) == 9 and len(set(ids)) == 9 and all_bindings
                and binding_gate_pass
            ),
        },
        "configurations": records,
        "aggregate_physical_consistency": {
            "all_nine_configurations_pass": all_physics,
            "mass_registry_within_rounding_tolerance": cross_check["within_rounding_tolerance_5p1e_minus_6_kg"],
            "mass_property_model_complete_for_frozen_v9f_motion_contract": mass_property_model_complete,
            "nine_configuration_binding_gate_pass": binding_gate_pass,
        },
        "acceptance_and_authorization": {
            "ODR_50_reopen_trigger_text": load_json(P_ODR50)["reopen_triggers"][0],
            "approved_numerical_acceptance_rule_found": False,
            "baseline_standard_uncertainty_is_acceptance_limit": False,
            "TMG2_reopen_decision": "NOT_EVALUATED_NO_APPROVED_NUMERICAL_ACCEPTANCE_RULE",
            "reason": "The ODR-50 record supplies a qualitative trigger only. Standard uncertainty does not become a tolerance or conformity limit without an approved decision rule and risk policy.",
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "synthetic_self_tests": {
            "executed": include_self_tests,
            "results": self_tests,
            "all_pass": bool(include_self_tests and all(item["pass"] for item in self_tests)),
        },
        "overall_tool_execution": {
            "status": overall_status,
            "calculation_completed": execution_checks_pass,
            "nine_configuration_binding_gate_state": aggregate_binding_state,
            "scientific_or_release_gate": False,
            "review_status": "PENDING_OWNER_REVIEW",
            "next_stage_authorized": False,
            "release_credit": False,
        },
    }
    return report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="V7", help="explicit Route-C input variant, e.g. V7 or ODR-58 fallback V9F; aliases are forbidden")
    parser.add_argument("--output", type=Path, help="new JSON output path; existing files are refused")
    parser.add_argument("--self-test", action="store_true", help="include synthetic contract regression tests")
    parser.add_argument("--check-only", action="store_true", help="evaluate and print summary without writing an artifact")
    parser.add_argument("--mc-samples", type=int, default=8192, help="deterministic Monte Carlo sample count (minimum 2048)")
    args = parser.parse_args(argv)
    if args.mc_samples < 2048:
        parser.error("--mc-samples must be >= 2048")
    if not args.check_only and args.output is None:
        parser.error("--output is required unless --check-only is used")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = build_report(args.variant.upper(), args.mc_samples, args.self_test)
        if args.output is not None and not args.check_only:
            output = args.output.resolve()
            if not output.is_relative_to(HERE):
                raise ContractError(f"output must remain inside the Route-C directory: {HERE}")
            if output.exists():
                raise ContractError(f"refusing to overwrite existing output: {output}")
            output.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            with output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
            print(f"wrote {output}")
            print(f"sha256 {sha256_file(output)}")
        print(json.dumps({
            "status": report["overall_tool_execution"]["status"],
            "variant": report["evaluated_route_c_variant"],
            "nine_configuration_binding_gate": report["nine_configuration_binding_gate"],
            "aggregate_physical_consistency": report["aggregate_physical_consistency"],
            "TMG2_reopen_decision": report["acceptance_and_authorization"]["TMG2_reopen_decision"],
            "release_credit": False,
        }, indent=2, ensure_ascii=False))
        return 0 if report["overall_tool_execution"]["status"] == "PASS_NON_AUTHORIZING_TOOL_EXECUTION" else 2
    except (ContractError, KeyError, ValueError, OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
