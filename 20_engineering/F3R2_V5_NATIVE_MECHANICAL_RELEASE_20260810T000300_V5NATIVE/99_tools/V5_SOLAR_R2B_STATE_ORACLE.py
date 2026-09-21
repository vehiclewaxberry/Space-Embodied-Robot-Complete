#!/usr/bin/env python3
"""Independent pure-math gate for the V5 solar R2B-A 90-degree fold.

The script never opens CAD.  It evaluates the seven-state contract, proves
serial hinge closure and XZ mirroring, and rejects panel/panel positive-volume
overlap before any native write is authorised.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


RUN_ROOT = Path(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition"
    r"\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
)
AUTHORITY = RUN_ROOT / "00_authority/V5_SOLAR_STATE_AUTHORITY_R2B.json"
REQUIREMENTS = RUN_ROOT / "00_authority/SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md"
OUT_DIR = RUN_ROOT / "13_validation"
EXPECTED_REQUIREMENTS_SHA256 = "62DDF827056D5199CCA68FD1714874E52FFB06398D4B856175435DD576504014"
STATES = (
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


def fact(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def rx(degrees: float) -> list[list[float]]:
    angle = math.radians(float(degrees))
    c, s = math.cos(angle), math.sin(angle)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def mat_vec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    return [sum(float(matrix[row][column]) * float(vector[column]) for column in range(3)) for row in range(3)]


def mat_mul(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> list[list[float]]:
    return [[sum(float(first[row][k]) * float(second[k][column]) for k in range(3)) for column in range(3)] for row in range(3)]


def add(first: Sequence[float], second: Sequence[float]) -> list[float]:
    return [float(first[index]) + float(second[index]) for index in range(3)]


def subtract(first: Sequence[float], second: Sequence[float]) -> list[float]:
    return [float(first[index]) - float(second[index]) for index in range(3)]


def max_error(first: Iterable[float], second: Iterable[float]) -> float:
    return max((abs(float(left) - float(right)) for left, right in zip(first, second)), default=0.0)


def bbox(points: Sequence[Sequence[float]]) -> list[float]:
    return [min(point[axis] for point in points) for axis in range(3)] + [max(point[axis] for point in points) for axis in range(3)]


def box_corners(center: Sequence[float], rotation: Sequence[Sequence[float]], x_span: float, v_span: float, n_span: float) -> list[list[float]]:
    rows = []
    for x in (-x_span / 2.0, x_span / 2.0):
        for v in (-v_span / 2.0, v_span / 2.0):
            for n in (-n_span / 2.0, n_span / 2.0):
                rows.append(add(center, mat_vec(rotation, [x, v, n])))
    return rows


def positive_bbox_overlap(first: Sequence[float], second: Sequence[float]) -> dict[str, Any]:
    depths = [min(float(first[axis + 3]), float(second[axis + 3])) - max(float(first[axis]), float(second[axis])) for axis in range(3)]
    return {"axis_overlap_mm": depths, "positive_volume": all(value > TOL for value in depths)}


def left_fk(logical_angles: Sequence[float], geometry: dict[str, Any]) -> dict[str, Any]:
    if len(logical_angles) != 3:
        raise ValueError(logical_angles)
    a1, a2, a3 = (float(value) for value in logical_angles)
    psi = [a1 - 90.0, 0.0, 0.0]
    psi[1] = psi[0] + (90.0 - a2)
    psi[2] = psi[1] - (90.0 - a3)
    rotations = [rx(value) for value in psi]
    pitch = float(geometry["panel_pitch_mm"])
    q_in = [[0.0, -pitch / 2.0, 0.0], [0.0, -pitch / 2.0, 0.0], [0.0, -pitch / 2.0, 0.0]]
    q_out = [[0.0, pitch / 2.0, 0.0], [0.0, pitch / 2.0, 0.0], None]
    root = [-61.0, 143.15, 0.0]
    centers = [subtract(root, mat_vec(rotations[0], q_in[0]))]
    hinge_12_parent = add(centers[0], mat_vec(rotations[0], q_out[0]))
    centers.append(subtract(hinge_12_parent, mat_vec(rotations[1], q_in[1])))
    hinge_23_parent = add(centers[1], mat_vec(rotations[1], q_out[1]))
    centers.append(subtract(hinge_23_parent, mat_vec(rotations[2], q_in[2])))
    panels = []
    x_span = float(geometry["panel_x_span_mm"][1]) - float(geometry["panel_x_span_mm"][0])
    n_span = float(geometry["panel_thickness_mm"])
    edge_contract = geometry["panel_structure_edge_contract"]
    v_ranges = [edge_contract["L1_main_plate_v_min_max_mm"], edge_contract["L2_v_min_max_mm"], edge_contract["L3_v_min_max_mm"]]
    for index in range(3):
        inboard = add(centers[index], mat_vec(rotations[index], q_in[index]))
        outboard = add(centers[index], mat_vec(rotations[index], q_out[index])) if index < 2 else None
        v_min, v_max = (float(value) for value in v_ranges[index])
        structural_center = add(centers[index], mat_vec(rotations[index], [0.0, (v_min + v_max) / 2.0, 0.0]))
        solid_points = box_corners(structural_center, rotations[index], x_span, v_max - v_min, n_span)
        if index == 0:
            relief = geometry["p1_root_structure_relief"]
            tab_y_min, tab_y_max = (float(value) for value in relief["bridge_tabs_world_y_span_left_mm"])
            nominal_center_y = float(geometry["deployed_panel_centroid_abs_y_mm"][0])
            tab_v_center = ((tab_y_min + tab_y_max) / 2.0) - nominal_center_y
            tab_v_span = tab_y_max - tab_y_min
            for x_min, x_max in relief["bridge_tabs_world_x_spans_mm"]:
                tab_center = add(centers[index], mat_vec(rotations[index], [(float(x_min) + float(x_max)) / 2.0 + 61.0, tab_v_center, 0.0]))
                solid_points.extend(box_corners(tab_center, rotations[index], float(x_max) - float(x_min), tab_v_span, n_span))
        solid_bbox = bbox(solid_points)
        panels.append({
            "panel": f"L{index + 1}",
            "logical_angle_deg": float(logical_angles[index]),
            "native_absolute_rotation_deg": psi[index],
            "rotation_3x3": rotations[index],
            "center_mm": centers[index],
            "inboard_hinge_mm": inboard,
            "outboard_hinge_mm": outboard,
            "solid_bbox_mm": solid_bbox,
        })
    pair_checks = []
    for first_index in range(3):
        for second_index in range(first_index + 1, 3):
            pair_checks.append({
                "pair": [panels[first_index]["panel"], panels[second_index]["panel"]],
                **positive_bbox_overlap(panels[first_index]["solid_bbox_mm"], panels[second_index]["solid_bbox_mm"]),
            })
    closure = [
        max_error(panels[0]["outboard_hinge_mm"], panels[1]["inboard_hinge_mm"]),
        max_error(panels[1]["outboard_hinge_mm"], panels[2]["inboard_hinge_mm"]),
    ]
    return {
        "side": "LEFT",
        "logical_angles_deg": [float(value) for value in logical_angles],
        "panels": panels,
        "panel_pair_checks": pair_checks,
        "positive_volume_panel_pair_count": sum(1 for row in pair_checks if row["positive_volume"]),
        "max_chain_continuity_error_mm": max(closure),
    }


def right_from_left(left: dict[str, Any]) -> dict[str, Any]:
    mirror = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]

    def mirror_point(point: Sequence[float] | None) -> list[float] | None:
        return None if point is None else [float(point[0]), -float(point[1]), float(point[2])]

    panels = []
    for source in left["panels"]:
        rotation = mat_mul(mat_mul(mirror, source["rotation_3x3"]), mirror)
        panels.append({
            **source,
            "panel": source["panel"].replace("L", "R", 1),
            "rotation_3x3": rotation,
            "center_mm": mirror_point(source["center_mm"]),
            "inboard_hinge_mm": mirror_point(source["inboard_hinge_mm"]),
            "outboard_hinge_mm": mirror_point(source["outboard_hinge_mm"]),
            "solid_bbox_mm": [source["solid_bbox_mm"][0], -source["solid_bbox_mm"][4], source["solid_bbox_mm"][2], source["solid_bbox_mm"][3], -source["solid_bbox_mm"][1], source["solid_bbox_mm"][5]],
        })
    return {
        "side": "RIGHT",
        "logical_angles_deg": list(left["logical_angles_deg"]),
        "panels": panels,
        "panel_pair_checks": [{**row, "pair": [name.replace("L", "R", 1) for name in row["pair"]]} for row in left["panel_pair_checks"]],
        "positive_volume_panel_pair_count": left["positive_volume_panel_pair_count"],
        "max_chain_continuity_error_mm": left["max_chain_continuity_error_mm"],
    }


def main() -> int:
    if not AUTHORITY.is_file() or not REQUIREMENTS.is_file() or sha256(REQUIREMENTS) != EXPECTED_REQUIREMENTS_SHA256:
        raise RuntimeError("R2B authority input missing or requirements hash drift")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    if authority.get("schema") != "F3R2_V5_SOLAR_STATE_AUTHORITY_R2B" or tuple(authority.get("states", {})) != STATES:
        raise RuntimeError("R2B state authority schema/order drift")
    geometry = authority["candidate_geometry"]
    state_rows = []
    max_chain = max_mirror_rotation = max_mirror_position = 0.0
    positive_volume_panel_pairs = 0
    for state in STATES:
        entry = authority["states"][state]
        left = left_fk(entry["LEFT"], geometry)
        right_seed = left_fk(entry["RIGHT"], geometry)
        right = right_from_left(right_seed)
        max_chain = max(max_chain, left["max_chain_continuity_error_mm"], right["max_chain_continuity_error_mm"])
        positive_volume_panel_pairs += left["positive_volume_panel_pair_count"] + right["positive_volume_panel_pair_count"]
        mirror_rows = []
        if entry["LEFT"] == entry["RIGHT"]:
            expected_right = right_from_left(left)
            for actual, expected in zip(right["panels"], expected_right["panels"]):
                rotation_error = max_error((value for row in actual["rotation_3x3"] for value in row), (value for row in expected["rotation_3x3"] for value in row))
                position_error = max_error(actual["center_mm"], expected["center_mm"])
                max_mirror_rotation = max(max_mirror_rotation, rotation_error)
                max_mirror_position = max(max_mirror_position, position_error)
                mirror_rows.append({"pair": [actual["panel"], expected["panel"]], "rotation_error": rotation_error, "position_error_mm": position_error})
        state_rows.append({"state": state, "angles": {"LEFT": entry["LEFT"], "RIGHT": entry["RIGHT"]}, "left": left, "right": right, "mirror": mirror_rows})
    nominal = next(row for row in state_rows if row["state"] == "SOLAR_DEPLOYED_NOMINAL")
    expected_abs_y = [float(value) for value in geometry["deployed_panel_centroid_abs_y_mm"]]
    nominal_centroid_error = max(
        max_error([panel["center_mm"][1] for panel in nominal["left"]["panels"]], expected_abs_y),
        max_error([panel["center_mm"][1] for panel in nominal["right"]["panels"]], [-value for value in expected_abs_y]),
    )
    fail_mapping_pass = (
        authority["states"]["SOLAR_LEFT_FAIL"]["LEFT"] == [0, 0, 0]
        and authority["states"]["SOLAR_LEFT_FAIL"]["RIGHT"] == [90, 90, 90]
        and authority["states"]["SOLAR_RIGHT_FAIL"]["LEFT"] == [90, 90, 90]
        and authority["states"]["SOLAR_RIGHT_FAIL"]["RIGHT"] == [0, 0, 0]
    )
    if not (
        max_chain <= TOL
        and max_mirror_rotation <= TOL
        and max_mirror_position <= TOL
        and nominal_centroid_error <= TOL
        and positive_volume_panel_pairs == 0
        and fail_mapping_pass
    ):
        raise RuntimeError("R2B pure-math state oracle failed")
    payload = {
        "schema": "F3R2_V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_V2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": [fact(AUTHORITY), fact(REQUIREMENTS)],
        "states": state_rows,
        "gates": {
            "state_count": len(state_rows),
            "fail_mapping_pass": fail_mapping_pass,
            "max_chain_continuity_error_mm": max_chain,
            "max_mirror_rotation_error": max_mirror_rotation,
            "max_mirror_position_error_mm": max_mirror_position,
            "nominal_centroid_error_mm": nominal_centroid_error,
            "positive_volume_panel_pair_count": positive_volume_panel_pairs,
        },
        "claims": {
            "logical_state_mapping_closed": True,
            "r2b_a_90deg_fold_math_closed": True,
            "right_side_is_xz_mirror_for_side_symmetric_states": True,
            "panel_to_panel_positive_volume_overlap_rejected": True,
            "native_cad_built": False,
            "top_level_clearance_verified": False,
        },
        "verdict": "V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_PASS",
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    target = OUT_DIR / f"V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_{stamp}.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"verdict": payload["verdict"], "target": fact(target), "gates": payload["gates"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
