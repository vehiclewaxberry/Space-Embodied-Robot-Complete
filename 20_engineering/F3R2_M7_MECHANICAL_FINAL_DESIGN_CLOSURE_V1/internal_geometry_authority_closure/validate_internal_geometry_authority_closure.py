#!/usr/bin/env python3
"""Independent validation and falsification for the internal geometry ruling."""

from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml


PACKAGE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_yaml(name: str) -> dict[str, Any]:
    with (PACKAGE / name).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(name: str) -> dict[str, Any]:
    with (PACKAGE / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def det3(r: list[list[float]]) -> float:
    return (
        r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
        - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
        + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0])
    )


def mat_vec(r: list[list[float]], v: list[float]) -> list[float]:
    return [sum(float(r[i][j]) * float(v[j]) for j in range(3)) for i in range(3)]


def rotx_vec(q: float, v: list[float]) -> list[float]:
    c, s = math.cos(q), math.sin(q)
    return [v[0], c * v[1] - s * v[2], s * v[1] + c * v[2]]


def rotx4(q: float) -> list[list[float]]:
    c, s = math.cos(q), math.sin(q)
    return [[1.0, 0.0, 0.0, 0.0], [0.0, c, -s, 0.0], [0.0, s, c, 0.0], [0.0, 0.0, 0.0, 1.0]]


def matmul4(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(float(a[i][k]) * float(b[k][j]) for k in range(4)) for j in range(4)] for i in range(4)]


def homogeneous_from_columns(
    origin: list[float] | tuple[float, float, float],
    e1: list[float] | tuple[float, float, float],
    e2: list[float] | tuple[float, float, float],
    e3: list[float] | tuple[float, float, float],
) -> list[list[float]]:
    return [
        [float(e1[0]), float(e2[0]), float(e3[0]), float(origin[0])],
        [float(e1[1]), float(e2[1]), float(e3[1]), float(origin[1])],
        [float(e1[2]), float(e2[2]), float(e3[2]), float(origin[2])],
        [0.0, 0.0, 0.0, 1.0],
    ]


def matrix_approx(a: list[list[float]], b: list[list[float]], tol: float = 1e-10) -> bool:
    return len(a) == len(b) and all(
        len(arow) == len(brow) and all(abs(float(x) - float(y)) <= tol for x, y in zip(arow, brow))
        for arow, brow in zip(a, b)
    )


def import_hash_pinned_module(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def approx(a: list[float], b: list[float], tol: float = 1e-12) -> bool:
    return len(a) == len(b) and all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def package_semantics_ok(bus: dict[str, Any], solar: dict[str, Any], gate: dict[str, Any], delta: dict[str, Any]) -> bool:
    left = solar["frames"]["T_S_R2_ROOT_L"]
    right = solar["frames"]["T_S_R2_ROOT_R"]
    ml = left["matrix_mm"]
    mr = right["matrix_mm"]
    rl = [row[:3] for row in ml[:3]]
    rr = [row[:3] for row in mr[:3]]
    q90_local = rotx_vec(math.pi / 2.0, [0.0, 0.0, 1.0])
    bridge = solar["kinematics_generated_leaf1_box_local_bridge_q0"]
    expected_bridge_l = [[-1.0, 0.0, 0.0, 150.0], [0.0, 0.0, 1.0, -1.25], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    expected_bridge_r = [[1.0, 0.0, 0.0, -150.0], [0.0, 0.0, -1.0, 1.25], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    urdf = solar["consumer_contract"]["future_system_URDF"]
    return all(
        [
            bus["ruling"]["MODE_OP_rigid_bus_body_length_mm"] == 340.5,
            bus["closure"]["length_conflict_resolved"] is True,
            bus["closure"]["physical_primary_structure_authority_resolved"] is False,
            bus["v22_366_disposition"]["may_be_used_as_physical_primary_structure_authority"] is False,
            bus["v22_366_disposition"]["may_be_averaged_with_340p5"] is False,
            bus["owner_accepted"] is False,
            bus["effective_for_downstream_execution"] is False,
            approx([row[3] for row in ml[:3]], [0.0, 115.4, -108.15]),
            approx([row[3] for row in mr[:3]], [0.0, -115.4, -108.15]),
            abs(det3(rl) - 1.0) <= 1e-12,
            abs(det3(rr) - 1.0) <= 1e-12,
            approx(mat_vec(rl, q90_local), [0.0, 1.0, 0.0]),
            approx(mat_vec(rr, q90_local), [0.0, -1.0, 0.0]),
            solar["legacy_and_stale_dispositions"]["current_consumed_y_abs_mm"] == 115.4,
            solar["leaf1_canonical_geometry_contract_q0"]["T_ROOT_LEAF1_MIDPLANE_Q0"] == [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
            "virtual root-coincident" in solar["leaf1_canonical_geometry_contract_q0"]["semantics"],
            matrix_approx(bridge["T_R2_ROOT_L_KINEMATICS_BOX_LOCAL_Q0_mm"], expected_bridge_l),
            matrix_approx(bridge["T_R2_ROOT_R_KINEMATICS_BOX_LOCAL_Q0_mm"], expected_bridge_r),
            bridge["selection_rule"] == "choose exactly one geometry-authorship branch; applying both bridges is forbidden",
            bridge["direct_fcstd_object_placement_verified"] is False,
            bridge["fcstd_consumption_allowed"] is False,
            len(bridge["kinematics_crosscheck"]) == 6 and all(row["box_chain_matches_hash_pinned_kinematics"] is True for row in bridge["kinematics_crosscheck"]),
            solar["consumer_contract"]["joint_composition"] == "T_S_LEAF1(q)=T_S_R2_ROOT_SIDE * Rx_active_about_positive_X_root(q) * T_ROOT_LEAF1_Q0",
            urdf["left_joint_origin_xyz_m"] == [0.0, 0.1154, -0.10815],
            approx(urdf["left_joint_origin_rpy_rad"], [0.0, 0.0, math.pi]),
            urdf["right_joint_origin_xyz_m"] == [0.0, -0.1154, -0.10815],
            urdf["right_joint_origin_rpy_rad"] == [0.0, 0.0, 0.0],
            urdf["axis_in_joint_frame"] == [1.0, 0.0, 0.0],
            approx(urdf["joint_limit_rad"], [0.0, math.pi / 2.0]),
            "never attach the aggregate STEP" in urdf["visual_collision_rule"],
            solar["consumer_contract"]["forbidden_double_transform"].startswith("FORBIDDEN_TO_APPLY_T_S_ROOT"),
            solar["authority_scope"]["flight_hinge_hardware_datum_released"] is False,
            solar["authority_scope"]["effective_for_downstream_execution"] is False,
            solar["owner_accepted"] is False,
            solar["effective_for_downstream_execution"] is False,
            delta["effective_summary"] == {"criteria_total": 20, "pass": 6, "hold": 14},
            delta["criterion_deltas"][0]["id"] == "PRB-17" and delta["criterion_deltas"][0]["effective_pass"] is False,
            delta["criterion_deltas"][1]["id"] == "PRB-18" and delta["criterion_deltas"][1]["effective_pass"] is True,
            all(value is False for value in delta["authority_flags"].values()),
            delta["engineering_specification_complete"] is False,
            delta["geometry_execution_authorized"] is False,
            delta["next_stage_authorized"] is False,
            delta["release_credit"] is False,
            gate["next_stage_authorized"] is False,
            gate["release_credit"] is False,
            gate["owner_accepted"] is False,
        ]
    )


def independent_kinematics_ok(solar: dict[str, Any], kinematics: ModuleType) -> bool:
    """Cross-check the registry against the pinned source, including box rebasing."""
    bridge = solar["kinematics_generated_leaf1_box_local_bridge_q0"]
    for label, side, frame_name, bridge_name in (
        ("L", +1, "T_S_R2_ROOT_L", "T_R2_ROOT_L_KINEMATICS_BOX_LOCAL_Q0_mm"),
        ("R", -1, "T_S_R2_ROOT_R", "T_R2_ROOT_R_KINEMATICS_BOX_LOCAL_Q0_mm"),
    ):
        t_s_root = solar["frames"][frame_name]["matrix_mm"]
        t_root_box = bridge[bridge_name]
        for q_deg in (0.0, 30.0, 90.0):
            leaf = kinematics.leaf_segments(side, q_deg, 180.0, 180.0)[0]
            origin, e2, e3 = kinematics.leaf_solid_frame(side, leaf)
            source_t_s_box = homogeneous_from_columns(origin, (1.0, 0.0, 0.0), e2, e3)
            composed_t_s_box = matmul4(matmul4(t_s_root, rotx4(math.radians(q_deg))), t_root_box)
            if not matrix_approx(source_t_s_box, composed_t_s_box):
                return False
            expected_span = mat_vec([row[:3] for row in t_s_root[:3]], rotx_vec(math.radians(q_deg), [0.0, 0.0, 1.0]))
            source_span = [0.0, float(leaf["dir"][0]), float(leaf["dir"][1])]
            if not approx(expected_span, source_span, tol=1e-10):
                return False
        if not matrix_approx(matmul4(t_s_root, t_root_box), bridge["current_T_S_KINEMATICS_BOX_LOCAL_Q0_mm"][label]):
            return False
    return True


def main() -> None:
    bus = load_yaml("BUS_12U_LENGTH_TRACK_RULING_V1.yaml")
    solar = load_yaml("SOLAR_R2_ROOT_FRAME_REGISTRATION_V1.yaml")
    gate = load_json("INTERNAL_GEOMETRY_AUTHORITY_GATE_V1.json")
    delta = load_json("UNIFIED_R2_PREBIND_GEOMETRY_DELTA_V1.json")

    checks: list[dict[str, Any]] = []

    def check(identifier: str, name: str, passed: bool) -> None:
        checks.append({"id": identifier, "name": name, "pass": bool(passed)})

    expected_outputs = {
        "BUS_12U_LENGTH_TRACK_RULING_V1.yaml",
        "SOLAR_R2_ROOT_FRAME_REGISTRATION_V1.yaml",
        "INTERNAL_GEOMETRY_AUTHORITY_GATE_V1.json",
        "UNIFIED_R2_PREBIND_GEOMETRY_DELTA_V1.json",
        "INTERNAL_GEOMETRY_AUTHORITY_RECEIPT_V1.md",
    }
    with (PACKAGE / "INTERNAL_GEOMETRY_AUTHORITY_SHA256.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    check("VAL-01", "manifest has exact output set", {row["path"] for row in rows} == expected_outputs and len(rows) == 5)
    check("VAL-02", "manifest bytes and hashes exact", all((PACKAGE / row["path"]).stat().st_size == int(row["bytes"]) and sha256(PACKAGE / row["path"]) == row["sha256"] for row in rows))

    source_rows = gate["source_pins"]
    check("VAL-03", "thirteen source pins remain exact", len(source_rows) == 13 and all((ROOT / row["path"]).stat().st_size == int(row["bytes"]) and sha256(ROOT / row["path"]) == row["sha256"] for row in source_rows))
    check("VAL-04", "independent package semantics", package_semantics_ok(bus, solar, gate, delta))
    check("VAL-05", "Gate exact 15/15 and fail-closed", gate["summary"] == {"passed": 15, "total": 15, "failed": []} and gate["next_stage_authorized"] is False and gate["release_credit"] is False)

    # Recompute the geometry registration from the upstream report, not from
    # the generated registration artifact.
    report_path = ROOT / next(row["path"] for row in source_rows if row["id"] == "SOLAR_R2_REPORT")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    lm = report["shape_metrics"]["R2_LEFT_ROOT_HINGE_KEEPOUT"]["aabb_S_mm"]
    rm = report["shape_metrics"]["R2_RIGHT_ROOT_HINGE_KEEPOUT"]["aabb_S_mm"]
    inferred_l = [(lm[0] + lm[3]) / 2.0, (lm[1] + lm[4]) / 2.0, (lm[2] + lm[5]) / 2.0]
    inferred_r = [(rm[0] + rm[3]) / 2.0, (rm[1] + rm[4]) / 2.0, (rm[2] + rm[5]) / 2.0]
    check("VAL-06", "upstream keepouts independently reproduce both origins", approx(inferred_l, [0.0, 115.4, -108.15]) and approx(inferred_r, [0.0, -115.4, -108.15]))

    kinematics_row = next(row for row in source_rows if row["id"] == "SOLAR_R2_KINEMATICS")
    kinematics = import_hash_pinned_module(ROOT / kinematics_row["path"], "solar_array_r2_kinematics_validation_source")
    check("VAL-07", "0/30/90 degree two-side transforms independently match pinned kinematics", independent_kinematics_ok(solar, kinematics))
    check(
        "VAL-08",
        "URDF joint origins, axes and aggregate-STEP prohibition are explicit",
        solar["consumer_contract"]["future_system_URDF"]["axis_in_joint_frame"] == [1.0, 0.0, 0.0]
        and "never attach the aggregate STEP" in solar["consumer_contract"]["future_system_URDF"]["visual_collision_rule"],
    )

    # In-memory falsification: each forbidden mutation must be rejected by
    # the same semantic predicate.  No repository artifact is changed.
    mutations = []
    b = copy.deepcopy(bus)
    b["ruling"]["MODE_OP_rigid_bus_body_length_mm"] = 366.0
    mutations.append(("VAL-09", "366 mm promoted to MODE_OP", b, solar, gate, delta))
    b = copy.deepcopy(bus)
    b["closure"]["physical_primary_structure_authority_resolved"] = True
    mutations.append(("VAL-10", "proxy promoted to physical structure", b, solar, gate, delta))
    b = copy.deepcopy(bus)
    b["v22_366_disposition"]["may_be_averaged_with_340p5"] = True
    mutations.append(("VAL-11", "340.5/366 averaging enabled", b, solar, gate, delta))
    s = copy.deepcopy(solar)
    s["frames"]["T_S_R2_ROOT_L"]["matrix_mm"][1][3] = 114.9
    mutations.append(("VAL-12", "stale 114.9 left root injected", bus, s, gate, delta))
    s = copy.deepcopy(solar)
    s["frames"]["T_S_R2_ROOT_R"]["matrix_mm"][0][3] = -56.75
    mutations.append(("VAL-13", "legacy R1 x origin injected", bus, s, gate, delta))
    s = copy.deepcopy(solar)
    s["frames"]["T_S_R2_ROOT_L"]["matrix_mm"][0][0] = 1.0
    mutations.append(("VAL-14", "left deployment-axis mirror removed", bus, s, gate, delta))
    s = copy.deepcopy(solar)
    s["kinematics_generated_leaf1_box_local_bridge_q0"]["T_R2_ROOT_L_KINEMATICS_BOX_LOCAL_Q0_mm"][0][3] = 0.0
    mutations.append(("VAL-15", "left Part box rebase removed", bus, s, gate, delta))
    s = copy.deepcopy(solar)
    s["consumer_contract"]["future_system_URDF"]["visual_collision_rule"] = "aggregate STEP allowed"
    mutations.append(("VAL-16", "aggregate dual-pose STEP allowed as URDF visual", bus, s, gate, delta))
    g = copy.deepcopy(gate)
    g["next_stage_authorized"] = True
    mutations.append(("VAL-17", "unauthorized next-stage promotion", bus, solar, g, delta))
    g = copy.deepcopy(gate)
    g["release_credit"] = "false"
    mutations.append(("VAL-18", "truthy-string release flag", bus, solar, g, delta))
    d = copy.deepcopy(delta)
    d["authority_flags"]["geometry_execution_authorized"] = True
    mutations.append(("VAL-19", "prebind geometry authority fabricated", bus, solar, gate, d))
    d = copy.deepcopy(delta)
    d["effective_summary"] = {"criteria_total": 20, "pass": 20, "hold": 0}
    mutations.append(("VAL-20", "prebind effective summary overclaimed", bus, solar, gate, d))
    for identifier, name, b_mut, s_mut, g_mut, d_mut in mutations:
        check(identifier, f"falsifier rejects {name}", not package_semantics_ok(b_mut, s_mut, g_mut, d_mut))

    passed = sum(item["pass"] for item in checks)
    result = {
        "schema": "INTERNAL_GEOMETRY_AUTHORITY_VALIDATION_V1",
        "generated_date_local": "2026-08-24",
        "checks": checks,
        "summary": {"passed": passed, "total": len(checks), "failed": [item["id"] for item in checks if not item["pass"]]},
        "technical_verdict": "PASS_INDEPENDENT_RECOMPUTE_AND_FAIL_CLOSED_FALSIFICATION" if passed == len(checks) else "FAIL_VALIDATION",
        "cad_or_solver_started": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    with (PACKAGE / "INTERNAL_GEOMETRY_AUTHORITY_VALIDATION_V1.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result["summary"] | {"technical_verdict": result["technical_verdict"]}, ensure_ascii=False, indent=2))
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
