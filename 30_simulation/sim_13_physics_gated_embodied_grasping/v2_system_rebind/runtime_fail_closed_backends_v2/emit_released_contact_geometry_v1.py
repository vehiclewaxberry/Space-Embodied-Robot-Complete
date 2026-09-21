#!/usr/bin/env python3
"""Emit the released narrow-phase contact-geometry artifact (WO-NC19).

The artifact is *derived*, never measured: pad frames come from the accepted
gripper prismatic joints of the hash-pinned Unified R2 URDF; stroke, initial
gap, and effective area come from the hash-pinned BOUNDED_PROVISIONAL
DESIGN_CONTACT_MODEL_V1 envelope.  The derivation is deterministic and the
output is canonical JSON so the artifact can be hash-pinned downstream.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import yaml

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sim13_v2_backends.canonical import sha256_bytes, write_canonical_json

PROJECT_ROOT = HERE.parents[3]
URDF_PATH = (
    PROJECT_ROOT
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    / "unified_r2_digital_prototype_prebind/generated_v2"
    / "unified_r2_c01_no_route_c_sim_candidate_v2.urdf"
)
CONTACT_MODEL_PATH = (
    PROJECT_ROOT
    / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b"
    / "DESIGN_CONTACT_MODEL_V1.yaml"
)
EXPECTED_URDF_SHA256 = (
    "D84AA23CE98A2A9C697B1F32E433C01C3F0AE3BD0B5C56EF9A218DD88911CBDA"
)
EXPECTED_CONTACT_MODEL_SHA256 = (
    "E57C799768BFDAB5DF22A3B834F6C8B9F8232D046A46774D24CA1FBB3DB879AD"
)
DEFAULT_OUTPUT = HERE / "assets" / "SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1.json"


def _rotation_z(yaw: float) -> list[list[float]]:
    c, s = math.cos(yaw), math.sin(yaw)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def _mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[i] * vector[i] for i in range(3)) for row in matrix]


def derive_contact_geometry() -> dict:
    if not URDF_PATH.is_file():
        raise RuntimeError("UNIFIED_R2_URDF_SOURCE_MISSING")
    urdf_bytes = URDF_PATH.read_bytes()
    if sha256_bytes(urdf_bytes) != EXPECTED_URDF_SHA256:
        raise RuntimeError("UNIFIED_R2_URDF_SOURCE_HASH_DRIFT")
    if not CONTACT_MODEL_PATH.is_file():
        raise RuntimeError("DESIGN_CONTACT_MODEL_V1_SOURCE_MISSING")
    model_bytes = CONTACT_MODEL_PATH.read_bytes()
    if sha256_bytes(model_bytes) != EXPECTED_CONTACT_MODEL_SHA256:
        raise RuntimeError("DESIGN_CONTACT_MODEL_V1_HASH_DRIFT")
    model = yaml.safe_load(model_bytes.decode("utf-8"))
    if model.get("schema") != "DESIGN_CONTACT_MODEL_V1":
        raise RuntimeError("DESIGN_CONTACT_MODEL_V1_SCHEMA_DRIFT")

    root = ET.fromstring(urdf_bytes)
    joints = {}
    for joint in root.findall("joint"):
        name = joint.get("name")
        if name in ("gripper_joint1", "gripper_joint2"):
            origin = joint.find("origin")
            limit = joint.find("limit")
            axis = joint.find("axis")
            joints[name] = {
                "xyz": [float(v) for v in origin.get("xyz").split()],
                "rpy": [float(v) for v in origin.get("rpy").split()],
                "axis": [float(v) for v in axis.get("xyz").split()],
                "lower": float(limit.get("lower")),
                "upper": float(limit.get("upper")),
            }
    if set(joints) != {"gripper_joint1", "gripper_joint2"}:
        raise RuntimeError("GRIPPER_PRISMATIC_JOINTS_MISSING")

    stroke = float(model["gripper_actuator"]["stroke_m"]["nominal"])
    gap = float(model["contact_geometry"]["initial_gap_m"]["nominal"])
    area = float(model["contact_geometry"]["effective_area_m2"]["nominal"])
    for name, joint in joints.items():
        if abs(joint["upper"] - stroke) > 1.0e-12 or joint["lower"] != 0.0:
            raise RuntimeError("GRIPPER_STROKE_CONTRACT_DRIFT")

    face_side = math.sqrt(area)  # square pad face derived from effective area
    pads = {}
    for name, sign, finger in (
        ("gripper_joint1", +1.0, "left"),
        ("gripper_joint2", -1.0, "right"),
    ):
        joint = joints[name]
        rotation = _rotation_z(joint["rpy"][2])
        closing_axis = _mat_vec(rotation, joint["axis"])
        # left pad closes along -y; right pad closes along +y (URDF rpy is
        # stored to 1e-4 rad, so the axis check uses a 1e-4 tolerance)
        closing_expected = [0.0, -1.0, 0.0] if finger == "left" else [0.0, +1.0, 0.0]
        if any(abs(a - b) > 1.0e-4 for a, b in zip(closing_axis, closing_expected)):
            raise RuntimeError("GRIPPER_CLOSING_AXIS_DERIVATION_DRIFT")
        normal = [0.0, -1.0, 0.0] if finger == "left" else [0.0, +1.0, 0.0]
        pads[finger] = {
            "finger_link": f"gripper_{finger}",
            "prismatic_joint": name,
            "joint_origin_gripper_link_xyz_m": joint["xyz"],
            "joint_origin_gripper_link_rpy_rad": joint["rpy"],
            "closing_axis_gripper_link": closing_axis,
            "face_normal_gripper_link": normal,
            "open_face_position_m": sign * stroke,
            "closed_face_position_m": 0.0,
            "face_dimensions_m": [face_side, face_side],
            "face_area_m2": area,
        }
    target = {
        "kind": "PLATE_BETWEEN_PADS_CANDIDATE",
        "half_thickness_m": stroke - gap,
        "surface_normal_gripper_link": [0.0, 1.0, 0.0],
        "surface_authority": "CANDIDATE_DERIVED_NOT_MEASURED_TARGET_SURFACE_UNKNOWN_PER_CONTRACT",
        "initial_gap_per_side_m": gap,
    }
    return {
        "schema": "SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1",
        "class": "BOUNDED_PROVISIONAL_DERIVED_NOT_MEASURED",
        "derivation": "accepted Unified R2 URDF gripper prismatic joints + DESIGN_CONTACT_MODEL_V1 nominal envelope; zero measured values",
        "frame": "gripper_link",
        "pads": pads,
        "target_plate": target,
        "provenance": {
            "unified_r2_urdf_sha256": EXPECTED_URDF_SHA256,
            "design_contact_model_v1_sha256": EXPECTED_CONTACT_MODEL_SHA256,
            "urdf_path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf",
            "contact_model_path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/DESIGN_CONTACT_MODEL_V1.yaml",
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    document = derive_contact_geometry()
    if args.check_only:
        existing = json.loads(args.output.read_bytes().decode("utf-8"))
        print("deterministic:", existing == document)
        return 0 if existing == document else 1
    write_canonical_json(args.output, document)
    print(json.dumps({"output": str(args.output), "sha256": sha256_bytes(args.output.read_bytes())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
