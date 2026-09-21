#!/usr/bin/env python3
"""Static-only validation for the dormant Unified-R2 URDF source package."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib.util
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INPUTS_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_INPUTS_V1.yaml"
CONTRACT_PATH = HERE / "UNIFIED_R2_URDF_SIM_CANDIDATE_CONTRACT_V1.yaml"
SOURCE_PATH = HERE / "unified_r2_urdf_source_v1.py"
VALIDATION_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_STATIC_VALIDATION_V1.json"
GATE_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_GATE_V1.json"
HASH_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_SHA256.csv"
RECEIPT_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_RECEIPT_V1.md"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def det3(a):
    return (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def transpose(a):
    return [list(row) for row in zip(*a)]


def rotation(T):
    return [row[:3] for row in T[:3]]


def inverse_transform(T):
    R = rotation(T)
    Rt = transpose(R)
    t = [T[i][3] for i in range(3)]
    ti = [-sum(Rt[i][k] * t[k] for k in range(3)) for i in range(3)]
    return [Rt[0] + [ti[0]], Rt[1] + [ti[1]], Rt[2] + [ti[2]], [0.0, 0.0, 0.0, 1.0]]


def max_abs_matrix_delta(a, b):
    return max(abs(a[i][j] - b[i][j]) for i in range(len(a)) for j in range(len(a[0])))


def jacobi_eigenvalues_symmetric_3(a):
    m = [list(map(float, row)) for row in a]
    for _ in range(40):
        pairs = [(0, 1), (0, 2), (1, 2)]
        p, q = max(pairs, key=lambda ij: abs(m[ij[0]][ij[1]]))
        if abs(m[p][q]) < 1.0e-15:
            break
        phi = 0.5 * math.atan2(2.0 * m[p][q], m[q][q] - m[p][p])
        c, s = math.cos(phi), math.sin(phi)
        for k in range(3):
            if k not in (p, q):
                mkp, mkq = m[k][p], m[k][q]
                m[k][p] = m[p][k] = c * mkp - s * mkq
                m[k][q] = m[q][k] = s * mkp + c * mkq
        app, aqq, apq = m[p][p], m[q][q], m[p][q]
        m[p][p] = c * c * app - 2.0 * s * c * apq + s * s * aqq
        m[q][q] = s * s * app + 2.0 * s * c * apq + c * c * aqq
        m[p][q] = m[q][p] = 0.0
    return sorted([m[i][i] for i in range(3)])


def check(cid, name, passed, evidence):
    return {"id": cid, "name": name, "pass": bool(passed), "evidence": evidence}


def load_source_module():
    spec = importlib.util.spec_from_file_location("unified_r2_urdf_source_static", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import generator source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["source-only"], default="source-only")
    parser.parse_args()

    inputs = yaml.safe_load(INPUTS_PATH.read_text(encoding="utf-8"))
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))

    source_pin_results = []
    for source_id, item in inputs["source_pins"].items():
        path = ROOT / item["path"]
        ok = path.is_file() and path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"]
        source_pin_results.append({"id": source_id, "pass": ok, "path": item["path"], "sha256": sha256(path) if path.is_file() else None})

    accepted_path = ROOT / inputs["source_pins"]["accepted_b601_urdf"]["path"]
    accepted = ET.parse(accepted_path).getroot()
    links = accepted.findall("link")
    joints = accepted.findall("joint")
    accepted_mass = sum(float(link.find("inertial/mass").attrib["value"]) for link in links)
    joint_types = {}
    for joint in joints:
        joint_types[joint.attrib["type"]] = joint_types.get(joint.attrib["type"], 0) + 1
    all_inertials = all(link.find("inertial") is not None for link in links)
    all_joint_fields = all(
        joint.find("parent") is not None
        and joint.find("child") is not None
        and joint.find("origin") is not None
        and (joint.attrib["type"] == "fixed" or (joint.find("axis") is not None and joint.find("limit") is not None))
        for joint in joints
    )

    component_masses = [
        inputs["components_c01"]["spacecraft_bus"]["mass_kg"],
        inputs["components_c01"]["load_bridge_candidate"]["mass_kg"],
        inputs["components_c01"]["m3r_lumped_link"]["mass_kg"],
        accepted_mass,
        inputs["components_c01"]["solar_r2_left_c01_snapshot"]["mass_kg"],
        inputs["components_c01"]["solar_r2_right_c01_snapshot"]["mass_kg"],
    ]
    total_mass = sum(component_masses)

    rotation_results = []
    for name, T in inputs["frames"].items():
        R = rotation(T)
        RtR = matmul(transpose(R), R)
        residual = max_abs_matrix_delta(RtR, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        rotation_results.append({"frame": name, "orthogonality_residual": residual, "determinant": det3(R), "pass": residual <= 1.0e-12 and abs(det3(R) - 1.0) <= 1.0e-12})

    T_M3R = inputs["frames"]["T_S_M3R_LOCAL"]
    T_B601 = inputs["frames"]["T_S_B601_ARM_BASE_PHYSICAL"]
    T_rel = matmul(inverse_transform(T_M3R), T_B601)
    round_trip = matmul(T_M3R, T_rel)
    relative_transform_residual = max_abs_matrix_delta(round_trip, T_B601)

    inertia_results = []
    for name in ("spacecraft_bus", "load_bridge_candidate", "m3r_lumped_link", "solar_r2_left_c01_snapshot", "solar_r2_right_c01_snapshot"):
        I = inputs["components_c01"][name]["inertia_about_com_S_kg_m2"]
        symmetry = max(abs(I[i][j] - I[j][i]) for i in range(3) for j in range(3))
        eigenvalues = jacobi_eigenvalues_symmetric_3(I)
        triangle = eigenvalues[0] + eigenvalues[1] >= eigenvalues[2] - 1.0e-12
        inertia_results.append({"component": name, "symmetry_residual": symmetry, "principal_moments": eigenvalues, "positive_definite": min(eigenvalues) > 0.0, "triangle_inequality": triangle, "pass": symmetry <= 1.0e-12 and min(eigenvalues) > 0.0 and triangle})

    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
    gen_defs = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "gen_urdf"]
    gen_contract_ok = len(gen_defs) == 1 and len(gen_defs[0].args.args) == 0 and gen_defs[0].args.vararg is None and gen_defs[0].args.kwarg is None
    forbidden_imports = {"FreeCAD", "Part", "subprocess", "abaqus", "pybullet"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    source_text = SOURCE_PATH.read_text(encoding="utf-8")
    subtree_copy_contract = "copy.deepcopy(source_link)" in source_text and "copy.deepcopy(joint)" in source_text

    urdf_before = sorted(p.name for p in HERE.glob("*.urdf"))
    module = load_source_module()
    fail_closed_message = None
    try:
        module.gen_urdf()
    except RuntimeError as exc:
        fail_closed_message = str(exc)
    urdf_after = sorted(p.name for p in HERE.glob("*.urdf"))
    dormant_call_ok = fail_closed_message is not None and "GENERATION_NOT_AUTHORIZED_PREBIND" in fail_closed_message and urdf_before == urdf_after == []

    flags_false = all(value is False for value in inputs["authority_flags"].values()) and all(value is False for value in contract["authority_flags"].values())
    physical_holds_ok = (
        inputs["physical_capability_holds"]["physical_gripper_speed_m_s"] is None
        and inputs["physical_capability_holds"]["physical_gripper_timing_s"] is None
        and inputs["physical_capability_holds"]["physical_contact_capability"] is None
        and inputs["physical_capability_holds"]["route_c_geometry"] is None
        and inputs["physical_capability_holds"]["route_c_status"] == "HOLD_ABSENT"
    )
    topo = inputs["topology_contract"]

    checks = [
        check("USV-01", "all seven input artifacts exist and hashes match", all(row["pass"] for row in source_pin_results), source_pin_results),
        check("USV-02", "accepted B601 subtree is 10 links and 9 joints", len(links) == 10 and len(joints) == 9, {"links": len(links), "joints": len(joints)}),
        check("USV-03", "accepted B601 joint types are 6R+1F+2P", joint_types == {"revolute": 6, "fixed": 1, "prismatic": 2}, joint_types),
        check("USV-04", "accepted B601 inertials origins axes and limits are structurally present", all_inertials and all_joint_fields and subtree_copy_contract, {"all_inertials": all_inertials, "all_joint_fields": all_joint_fields, "deep_copy_source": subtree_copy_contract}),
        check("USV-05", "accepted B601 mass is exact", abs(accepted_mass - 4.695555949342986) <= 1.0e-15, accepted_mass),
        check("USV-06", "C01 component mass sum is exact and target-free", abs(total_mass - inputs["components_c01"]["total_mass_kg"]) <= 1.0e-12 and abs(total_mass - 31.022864807342987) <= 1.0e-12, {"components": component_masses, "total": total_mass}),
        check("USV-07", "declared future topology is 15 links 14 joints 8 actuated DOF", (topo["physical_links"], topo["joints"], topo["actuated_dof"]) == (15, 14, 8), topo),
        check("USV-08", "all registered rotations are right-handed orthogonal", all(row["pass"] for row in rotation_results), rotation_results),
        check("USV-09", "M3R-to-B601 transform is composed from authorities", relative_transform_residual <= 1.0e-12, {"round_trip_residual": relative_transform_residual, "T_M3R_B601": T_rel}),
        check("USV-10", "all new component inertias are symmetric positive and physical", all(row["pass"] for row in inertia_results), inertia_results),
        check("USV-11", "gen_urdf is top-level zero-argument and source imports no CAD solver or subprocess", gen_contract_ok and imported.isdisjoint(forbidden_imports), {"gen_contract": gen_contract_ok, "imports": sorted(imported)}),
        check("USV-12", "unauthorized gen_urdf call fails closed without emitting URDF", dormant_call_ok, fail_closed_message),
        check("USV-13", "model velocity is not promoted to physical speed timing or contact", physical_holds_ok and inputs["physical_capability_holds"]["gripper_model_velocity_literal_m_s"] == 15.0, inputs["physical_capability_holds"]),
        check("USV-14", "Route-C geometry remains absent and Sim13 rebind remains unauthorized", physical_holds_ok and contract["sim13_contract"]["baseline_mutation_authorized"] is False and contract["sim13_contract"]["current_loader_compatible"] is False, contract["sim13_contract"]),
        check("USV-15", "all execution release flight and Owner flags remain false", flags_false, {"inputs": inputs["authority_flags"], "contract": contract["authority_flags"]}),
        check("USV-16", "package contains no generated URDF", not list(HERE.glob("*.urdf")), {"urdf_matches": sorted(p.name for p in HERE.glob("*.urdf"))}),
    ]
    failed = [row["id"] for row in checks if not row["pass"]]
    if failed:
        raise RuntimeError("Unified R2 source-only validation failed: " + ",".join(failed))

    validation = {
        "schema": "UNIFIED_R2_URDF_SOURCE_STATIC_VALIDATION_V1",
        "generated_date_local": "2026-08-24",
        "mode": "source-only",
        "checks": checks,
        "summary": {"pass": len(checks), "total": len(checks), "failed": []},
        "verdict": "PASS_STATIC_SOURCE_ONLY__GENERATION_FAILS_CLOSED__NO_URDF_NO_SIM13_REBIND_NO_RELEASE_AUTHORITY",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")

    gate = {
        "schema": "UNIFIED_R2_URDF_SOURCE_GATE_V1",
        "generated_date_local": "2026-08-24",
        "package_validation": "PASS",
        "technical_outcome": "HOLD_PREBIND_SOURCE_ONLY",
        "static_validation": {"pass": len(checks), "total": len(checks)},
        "urdf_emitted": False,
        "sim13_rebind_authorized": False,
        "physical_contact_ready": False,
        "flight_qualified": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "technical_verdict": "DORMANT_UNIFIED_R2_C01_URDF_SOURCE_STATICALLY_CLOSED__EXECUTION_ROUTE_C_SIM13_CONTACT_AND_RELEASE_HOLD",
    }
    GATE_PATH.write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")

    RECEIPT_PATH.write_text(
        "# Unified R2 URDF 休眠源包回执\n\n"
        "- 已冻结未来 C01 快照拓扑：15 links / 14 joints / 8 actuated DOF。\n"
        "- B601 10-link/9-joint 子树继续从接受版 URDF 深复制；质量回算为 31.022864807342987 kg。\n"
        "- Solar R2 当前只定义固定部署快照；连续三叶手风琴联动未伪造。\n"
        "- 生成函数 `gen_urdf()` 已建立，但当前调用会 fail-closed，包内没有 `.urdf`。\n"
        "- 当前 Sim13 loader 与系统模型不兼容，禁止修改历史 baseline 或宣称接触/RL 绑定。\n",
        encoding="utf-8",
    )

    hash_paths = [INPUTS_PATH, CONTRACT_PATH, SOURCE_PATH, VALIDATION_PATH, GATE_PATH, RECEIPT_PATH]
    with HASH_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["class", "path", "bytes", "sha256"])
        for path in hash_paths:
            writer.writerow(["SOURCE_ONLY_PACKAGE", str(path.relative_to(ROOT)).replace("\\", "/"), path.stat().st_size, sha256(path)])
    print("PASS: Unified R2 URDF dormant source static validation 16/16; no URDF emitted")


if __name__ == "__main__":
    main()
