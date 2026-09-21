#!/usr/bin/env python3
"""Side-effect-free accepted-URDF joint1 and 12dp execution-mount adapter."""

from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np


PACKAGE = Path(__file__).resolve().parents[1]
SOURCE_LOCK = PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root not found")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_locked_sources() -> tuple[dict[str, Any], dict[str, Path]]:
    lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
    require(lock["source_pin_count"] == 10 and len(lock["source_pins"]) == 10, "source pin count drift")
    root = workspace_root()
    paths: dict[str, Path] = {}
    for row in lock["source_pins"]:
        path = root / row["path"]
        require(row["id"] not in paths, f"duplicate source pin id: {row['id']}")
        require(path.is_file(), f"missing source pin: {row['path']}")
        require(path.stat().st_size == int(row["bytes"]), f"source byte drift: {row['id']}")
        require(sha256(path) == row["sha256"], f"source hash drift: {row['id']}")
        paths[row["id"]] = path
    return lock, paths


def _raw_vector(text: str | None, expected: int, context: str) -> tuple[list[str], np.ndarray]:
    require(text is not None, f"missing {context}")
    raw = text.split()
    require(len(raw) == expected, f"{context} length drift")
    values = np.asarray([float(value) for value in raw], dtype=np.float64)
    require(np.all(np.isfinite(values)), f"nonfinite {context}")
    return raw, values


def rpy_matrix(rpy: np.ndarray) -> np.ndarray:
    roll, pitch, yaw = (float(value) for value in rpy)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.asarray([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], dtype=np.float64)
    ry = np.asarray([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], dtype=np.float64)
    rz = np.asarray([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], dtype=np.float64)
    return rz @ ry @ rx


def axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    norm = float(np.linalg.norm(axis))
    require(math.isfinite(norm) and norm > 0.0, "joint1 axis is zero/nonfinite")
    x, y, z = axis / norm
    c, s, one_minus_c = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    return np.asarray(
        [
            [c + x * x * one_minus_c, x * y * one_minus_c - z * s, x * z * one_minus_c + y * s],
            [y * x * one_minus_c + z * s, c + y * y * one_minus_c, y * z * one_minus_c - x * s],
            [z * x * one_minus_c - y * s, z * y * one_minus_c + x * s, c + z * z * one_minus_c],
        ],
        dtype=np.float64,
    )


def parse_joint1(urdf_path: Path) -> dict[str, Any]:
    root = ET.parse(urdf_path).getroot()
    matches = [joint for joint in root.findall("joint") if joint.get("name") == "joint1"]
    require(len(matches) == 1, "accepted URDF must contain exactly one joint1")
    joint = matches[0]
    require(joint.get("type") == "revolute", "joint1 type drift")
    require(joint.find("parent").get("link") == "base_link", "joint1 parent drift")
    require(joint.find("child").get("link") == "link1", "joint1 child drift")
    xyz_raw, xyz = _raw_vector(joint.find("origin").get("xyz"), 3, "joint1 origin xyz")
    rpy_raw, rpy = _raw_vector(joint.find("origin").get("rpy"), 3, "joint1 origin rpy")
    axis_raw, axis = _raw_vector(joint.find("axis").get("xyz"), 3, "joint1 axis")
    limit = joint.find("limit")
    lower_raw, upper_raw = limit.get("lower"), limit.get("upper")
    require(lower_raw is not None and upper_raw is not None, "joint1 limits missing")
    lower, upper = float(lower_raw), float(upper_raw)
    require(math.isfinite(lower) and math.isfinite(upper) and lower < upper, "joint1 limits invalid")
    origin = np.eye(4, dtype=np.float64)
    origin[:3, :3] = rpy_matrix(rpy)
    origin[:3, 3] = xyz
    return {
        "axis": axis,
        "axis_raw": axis_raw,
        "limit_lower": lower,
        "limit_lower_raw": lower_raw,
        "limit_upper": upper,
        "limit_upper_raw": upper_raw,
        "origin": origin,
        "origin_rpy_raw": rpy_raw,
        "origin_xyz_raw": xyz_raw,
    }


def parse_mount(mount_path: Path) -> tuple[np.ndarray, list[list[str]], str]:
    document = json.loads(mount_path.read_text(encoding="utf-8"))
    require(document["schema"] == "ODR60_OPTION_A_EXECUTION_MOUNT_BINDING_V1", "mount schema drift")
    require(document["binding"]["canonical_decimal_places"] == 12, "mount decimal-place drift")
    require(document["binding"]["translation_unit"] == "m", "mount unit drift")
    strings = document["binding"]["canonical_matrix_decimal_strings"]
    require(len(strings) == 4 and all(len(row) == 4 for row in strings), "mount matrix shape drift")
    require(all(isinstance(value, str) and len(value.rsplit(".", 1)[-1]) == 12 for row in strings for value in row), "mount 12dp spelling drift")
    matrix = np.asarray([[float(value) for value in row] for row in strings], dtype=np.float64)
    require(np.max(np.abs(matrix[3] - [0, 0, 0, 1])) <= 1e-15, "mount homogeneous row drift")
    require(np.max(np.abs(matrix[:3, :3].T @ matrix[:3, :3] - np.eye(3))) <= 1e-11, "mount rotation drift")
    require(abs(float(np.linalg.det(matrix[:3, :3])) - 1.0) <= 1e-11, "mount determinant drift")
    return matrix, strings, document["canonical_binding_payload_sha256"]


def joint1_transform_A0_link1(q1_rad: float, joint: dict[str, Any]) -> np.ndarray:
    require(math.isfinite(q1_rad), "q1 must be finite")
    require(joint["limit_lower"] <= q1_rad <= joint["limit_upper"], "q1 outside accepted limits")
    motion = np.eye(4, dtype=np.float64)
    motion[:3, :3] = axis_angle(joint["axis"], q1_rad)
    return joint["origin"] @ motion


def pose_matrix_S_link1(q1_rad: float, joint: dict[str, Any], mount: np.ndarray) -> np.ndarray:
    return mount @ joint1_transform_A0_link1(q1_rad, joint)


def load_adapter() -> dict[str, Any]:
    lock, paths = load_locked_sources()
    joint = parse_joint1(paths["accepted_urdf"])
    mount, mount_strings, mount_payload_sha256 = parse_mount(paths["execution_mount_12dp"])
    return {
        "source_lock": lock,
        "paths": paths,
        "joint": joint,
        "mount": mount,
        "mount_strings": mount_strings,
        "mount_payload_sha256": mount_payload_sha256,
    }

