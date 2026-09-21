#!/usr/bin/env python3
"""Pure-math serial-FK and mirror oracle for the V5 solar R2 candidate.

This script does not open or mutate SolidWorks.  It validates the frozen
logical state table, evaluates the candidate three-link fold, proves exact
hinge-chain continuity and XZ-plane mirroring, and emits write-once evidence.
It is an independent expected-value source for later native CAD readback.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


RUN_ROOT = Path(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition"
    r"\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
)
AUTHORITY = RUN_ROOT / "00_authority/V5_SOLAR_STATE_AUTHORITY_R2.json"
AUTHORITY_SHA256 = "63A2FBCFA324321DFA3919E0FEEF689770DBED608D2B86EA4078C8C096A46B32"
REQUIREMENTS = RUN_ROOT / "00_authority/SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md"
REQUIREMENTS_SHA256 = "62DDF827056D5199CCA68FD1714874E52FFB06398D4B856175435DD576504014"
AUTHORIZATION = RUN_ROOT / "13_validation/V5_SOLAR_R2_REBUILD_AUTHORIZATION.json"
AUTHORIZATION_SHA256 = "11CBD319738BA6FC5EC1BE937062AC4C96DC9E34F9474A60992542935C2C03A2"
OUT_DIR = RUN_ROOT / "13_validation"

EXPECTED_STATES = (
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
)
TOL = 1.0e-9


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def fact(path: Path) -> dict:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def eye4() -> list[list[float]]:
    return [[1.0 if row == column else 0.0 for column in range(4)] for row in range(4)]


def matmul(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> list[list[float]]:
    return [[sum(float(first[row][k]) * float(second[k][column]) for k in range(4)) for column in range(4)] for row in range(4)]


def transform_point(matrix: Sequence[Sequence[float]], point: Sequence[float]) -> list[float]:
    vector = [float(point[0]), float(point[1]), float(point[2]), 1.0]
    return [sum(float(matrix[row][column]) * vector[column] for column in range(4)) for row in range(3)]


def rx_about_y(angle_deg: float, axis_y_mm: float) -> list[list[float]]:
    angle = math.radians(float(angle_deg))
    cosine, sine = math.cos(angle), math.sin(angle)
    matrix = eye4()
    matrix[1][1], matrix[1][2] = cosine, -sine
    matrix[2][1], matrix[2][2] = sine, cosine
    matrix[1][3] = float(axis_y_mm) * (1.0 - cosine)
    matrix[2][3] = -float(axis_y_mm) * sine
    return matrix


def mirror_matrix() -> list[list[float]]:
    matrix = eye4()
    matrix[1][1] = -1.0
    return matrix


def flatten(matrix: Sequence[Sequence[float]]) -> list[float]:
    return [float(matrix[row][column]) for row in range(4) for column in range(4)]


def max_error(first: Iterable[float], second: Iterable[float]) -> float:
    pairs = list(zip(first, second))
    return max((abs(float(left) - float(right)) for left, right in pairs), default=0.0)


def panel_corners(x_span: Sequence[float], y_span: Sequence[float], thickness_mm: float) -> list[list[float]]:
    return [[x, y, z] for x in x_span for y in y_span for z in (-thickness_mm / 2.0, thickness_mm / 2.0)]


def bbox(points: Sequence[Sequence[float]]) -> list[float]:
    return [min(point[axis] for point in points) for axis in range(3)] + [max(point[axis] for point in points) for axis in range(3)]


def side_fk(side: str, logical_angles: Sequence[float], geometry: dict) -> dict:
    if side not in ("LEFT", "RIGHT") or len(logical_angles) != 3:
        raise ValueError((side, logical_angles))
    sign = 1.0 if side == "LEFT" else -1.0
    pitch = float(geometry["panel_pitch_mm"])
    axes_abs = [float(value) for value in geometry["deployed_hinge_axis_abs_y_mm"]]
    axes = [sign * value for value in axes_abs]
    deltas = [sign * (float(angle) - 90.0) for angle in logical_angles]

    relative = [rx_about_y(deltas[index], axes[index]) for index in range(3)]
    transforms = [relative[0], matmul(relative[0], relative[1]), matmul(matmul(relative[0], relative[1]), relative[2])]

    x_span = [float(value) for value in geometry["panel_x_span_mm"]]
    thickness = float(geometry["panel_thickness_mm"])
    panels = []
    all_points = []
    continuity_errors = []
    for index, transform in enumerate(transforms):
        inner = sign * (axes_abs[0] + index * pitch)
        outer = sign * (axes_abs[0] + (index + 1) * pitch)
        center = sign * float(geometry["deployed_panel_centroid_abs_y_mm"][index])
        corners = [transform_point(transform, point) for point in panel_corners(x_span, (inner, outer), thickness)]
        centroid = transform_point(transform, [(x_span[0] + x_span[1]) / 2.0, center, 0.0])
        all_points.extend(corners)
        panels.append({
            "panel": f"{side[0]}{index + 1}",
            "logical_angle_deg": float(logical_angles[index]),
            "native_relative_rotation_deg": deltas[index],
            "transform_4x4": transform,
            "centroid_mm": centroid,
            "bbox_mm": bbox(corners),
        })
        if index > 0:
            hinge_y = sign * axes_abs[index]
            parent_point = transform_point(transforms[index - 1], [0.0, hinge_y, 0.0])
            child_point = transform_point(transform, [0.0, hinge_y, 0.0])
            continuity_errors.append(max_error(parent_point, child_point))

    actual_axes = [
        [0.0, axes[0], 0.0],
        transform_point(transforms[0], [0.0, axes[1], 0.0]),
        transform_point(transforms[1], [0.0, axes[2], 0.0]),
    ]
    return {
        "side": side,
        "logical_angles_deg": [float(value) for value in logical_angles],
        "native_relative_rotations_deg": deltas,
        "hinge_axes_points_mm": actual_axes,
        "panels": panels,
        "panel_chain_bbox_mm": bbox(all_points),
        "max_chain_continuity_error_mm": max(continuity_errors, default=0.0),
    }


def main() -> int:
    for path, expected in ((AUTHORITY, AUTHORITY_SHA256), (REQUIREMENTS, REQUIREMENTS_SHA256), (AUTHORIZATION, AUTHORIZATION_SHA256)):
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"authority hash mismatch: {path}")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    if tuple(authority["states"]) != EXPECTED_STATES:
        raise RuntimeError(f"state order/set drift: {list(authority['states'])}")

    geometry = authority["candidate_geometry"]
    mirror = mirror_matrix()
    state_rows = []
    max_mirror_transform_error = 0.0
    max_mirror_centroid_error_mm = 0.0
    max_chain_continuity_error_mm = 0.0
    for state in EXPECTED_STATES:
        entry = authority["states"][state]
        left = side_fk("LEFT", entry["LEFT"], geometry)
        right = side_fk("RIGHT", entry["RIGHT"], geometry)
        max_chain_continuity_error_mm = max(max_chain_continuity_error_mm, left["max_chain_continuity_error_mm"], right["max_chain_continuity_error_mm"])

        state_is_side_symmetric = entry["LEFT"] == entry["RIGHT"]
        mirror_rows = []
        if state_is_side_symmetric:
            for left_panel, right_panel in zip(left["panels"], right["panels"]):
                expected_right = matmul(matmul(mirror, left_panel["transform_4x4"]), mirror)
                transform_error = max_error(flatten(expected_right), flatten(right_panel["transform_4x4"]))
                expected_centroid = transform_point(mirror, left_panel["centroid_mm"])
                centroid_error = max_error(expected_centroid, right_panel["centroid_mm"])
                max_mirror_transform_error = max(max_mirror_transform_error, transform_error)
                max_mirror_centroid_error_mm = max(max_mirror_centroid_error_mm, centroid_error)
                mirror_rows.append({
                    "panel_pair": f"{left_panel['panel']}/{right_panel['panel']}",
                    "transform_error": transform_error,
                    "centroid_error_mm": centroid_error,
                })
        state_rows.append({
            "state": state,
            "authority_angles": {"LEFT": entry["LEFT"], "RIGHT": entry["RIGHT"]},
            "hinge_state": {"LEFT": entry["hinge_state_LEFT"], "RIGHT": entry["hinge_state_RIGHT"]},
            "side_symmetric_angles": state_is_side_symmetric,
            "left": left,
            "right": right,
            "mirror_rows": mirror_rows,
        })

    nominal = next(row for row in state_rows if row["state"] == "SOLAR_DEPLOYED_NOMINAL")
    expected_left_bbox = [-174.5, 143.15, -3.0, 52.5, 313.15, 3.0]
    expected_right_bbox = [-174.5, -313.15, -3.0, 52.5, -143.15, 3.0]
    nominal_bbox_error_mm = max(
        max_error(nominal["left"]["panel_chain_bbox_mm"], expected_left_bbox),
        max_error(nominal["right"]["panel_chain_bbox_mm"], expected_right_bbox),
    )
    fail_mapping_pass = (
        authority["states"]["SOLAR_LEFT_FAIL"]["LEFT"] == [0, 0, 0]
        and authority["states"]["SOLAR_LEFT_FAIL"]["RIGHT"] == [90, 90, 90]
        and authority["states"]["SOLAR_RIGHT_FAIL"]["LEFT"] == [90, 90, 90]
        and authority["states"]["SOLAR_RIGHT_FAIL"]["RIGHT"] == [0, 0, 0]
    )
    passed = (
        max_chain_continuity_error_mm <= TOL
        and max_mirror_transform_error <= TOL
        and max_mirror_centroid_error_mm <= TOL
        and nominal_bbox_error_mm <= TOL
        and fail_mapping_pass
    )
    if not passed:
        raise RuntimeError("serial-FK static oracle did not close")

    payload = {
        "schema": "F3R2_V5_SOLAR_R2_STATIC_KINEMATIC_ORACLE_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": [fact(AUTHORITY), fact(REQUIREMENTS), fact(AUTHORIZATION)],
        "units": "mm_deg",
        "tolerance": TOL,
        "state_count": len(state_rows),
        "states": state_rows,
        "gates": {
            "fail_mapping_pass": fail_mapping_pass,
            "max_chain_continuity_error_mm": max_chain_continuity_error_mm,
            "max_mirror_transform_error": max_mirror_transform_error,
            "max_mirror_centroid_error_mm": max_mirror_centroid_error_mm,
            "nominal_bbox_error_mm": nominal_bbox_error_mm,
        },
        "claims": {
            "serial_fk_math_closed": True,
            "right_side_is_xz_mirror_for_symmetric_states": True,
            "native_cad_built": False,
            "solidworks_mates_verified": False,
            "clearance_verified": False,
        },
        "verdict": "V5_SOLAR_R2_STATIC_KINEMATIC_ORACLE_PASS",
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    target = OUT_DIR / f"V5_SOLAR_R2_STATIC_KINEMATIC_ORACLE_{stamp}.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"verdict": payload["verdict"], "target": fact(target), "gates": payload["gates"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
