"""Extract the accepted B601 chain without changing its source package.

The accepted URDF is the L0 kinematic and inertial authority.  This script
creates only B5.0 traceability artifacts.  It intentionally carries source
number strings as well as parsed values so that later CAD and robot-description
generators cannot silently round the baseline.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import trimesh


CANDIDATE = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[4]
OUT = CANDIDATE / "01_KINEMATICS"
URDF = (
    WORKSPACE
    / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
)
EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_LINK_ORDER = [
    "base_link",
    "link1",
    "link2",
    "link3",
    "link4",
    "link5",
    "link6",
    "gripper_link",
    "gripper_left",
    "gripper_right",
]
EXPECTED_JOINT_ORDER = [
    "joint1",
    "joint2",
    "joint3",
    "joint4",
    "joint5",
    "joint6",
    "gripper_joint",
    "gripper_joint1",
    "gripper_joint2",
]
R_SM = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
S_TRACKS_MM = {
    "S_DISPLAY_MOUNT_FACE": np.array([198.0, 0.0, 0.0]),
    "S_DYNAMICS_T_SM": np.array([185.25, 0.0, 0.0]),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def split_numbers(text: str | None, default: str) -> list[str]:
    return (text or default).split()


def rpy_matrix(rpy: list[float]) -> np.ndarray:
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], dtype=float)
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], dtype=float)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], dtype=float)
    return rz @ ry @ rx


def transform(rotation: np.ndarray, xyz_m: list[float]) -> np.ndarray:
    value = np.eye(4)
    value[:3, :3] = rotation
    value[:3, 3] = np.asarray(xyz_m, dtype=float)
    return value


def csv_write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise RuntimeError(f"refusing to write empty table: {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def matrix_rows(value: np.ndarray) -> list[list[float]]:
    return [[float(x) for x in row] for row in value.tolist()]


def main() -> None:
    before = sha256(URDF)
    if before != EXPECTED_URDF_SHA256:
        raise SystemExit(
            f"accepted URDF drift: {before} != {EXPECTED_URDF_SHA256}"
        )

    root = ET.parse(URDF).getroot()
    link_nodes = {node.get("name"): node for node in root.findall("link")}
    joint_nodes = {node.get("name"): node for node in root.findall("joint")}
    if list(link_nodes) != EXPECTED_LINK_ORDER:
        raise SystemExit(f"link order drift: {list(link_nodes)}")
    if list(joint_nodes) != EXPECTED_JOINT_ORDER:
        raise SystemExit(f"joint order drift: {list(joint_nodes)}")

    links: list[dict[str, object]] = []
    inertial_rows: list[dict[str, object]] = []
    mesh_rows: list[dict[str, object]] = []
    mass_sum = Decimal("0")
    inertia_checks: dict[str, dict[str, object]] = {}
    for name in EXPECTED_LINK_ORDER:
        node = link_nodes[name]
        inertial = node.find("inertial")
        origin = inertial.find("origin")
        mass_text = inertial.find("mass").get("value")
        inertia = inertial.find("inertia")
        xyz_text = origin.get("xyz")
        rpy_text = origin.get("rpy") or "0 0 0"
        inertia_text = {
            key: inertia.get(key)
            for key in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")
        }
        mass_sum += Decimal(mass_text)
        tensor = np.array(
            [
                [float(inertia_text["ixx"]), float(inertia_text["ixy"]),
                 float(inertia_text["ixz"])],
                [float(inertia_text["ixy"]), float(inertia_text["iyy"]),
                 float(inertia_text["iyz"])],
                [float(inertia_text["ixz"]), float(inertia_text["iyz"]),
                 float(inertia_text["izz"])],
            ]
        )
        eig = np.linalg.eigvalsh(tensor)
        principal = sorted(float(v) for v in eig)
        inertia_checks[name] = {
            "positive_definite": bool(np.all(eig > 0)),
            "eigenvalues_kg_m2": principal,
            "triangle_inequality": principal[2] <= principal[0] + principal[1] + 1e-15,
        }

        visual_mesh = node.find("visual/geometry/mesh").get("filename")
        collision_mesh = node.find("collision/geometry/mesh").get("filename")
        mesh_path = (URDF.parent / visual_mesh).resolve()
        if not mesh_path.is_file():
            raise SystemExit(f"missing accepted mesh: {mesh_path}")
        mesh = trimesh.load_mesh(mesh_path, force="mesh", process=False)
        bounds_m = np.asarray(mesh.bounds, dtype=float)
        mesh_hash = sha256(mesh_path)
        mesh_rows.append(
            {
                "link": name,
                "mesh_path": mesh_path.relative_to(WORKSPACE).as_posix(),
                "sha256": mesh_hash,
                "visual_equals_collision": visual_mesh == collision_mesh,
                "scale_attribute": node.find("visual/geometry/mesh").get("scale") or "",
                "bbox_min_x_m": format(bounds_m[0, 0], ".15g"),
                "bbox_min_y_m": format(bounds_m[0, 1], ".15g"),
                "bbox_min_z_m": format(bounds_m[0, 2], ".15g"),
                "bbox_max_x_m": format(bounds_m[1, 0], ".15g"),
                "bbox_max_y_m": format(bounds_m[1, 1], ".15g"),
                "bbox_max_z_m": format(bounds_m[1, 2], ".15g"),
                "cad_import_scale": "1000 mm per m",
            }
        )
        link_record = {
            "name": name,
            "mass_kg_source": mass_text,
            "inertial_origin_xyz_m_source": xyz_text,
            "inertial_origin_rpy_rad_source": rpy_text,
            "inertia_kg_m2_source": inertia_text,
            "visual_mesh": visual_mesh,
            "collision_mesh": collision_mesh,
            "mesh_sha256": mesh_hash,
            "mass_owner_id": "B601_URDF_OWNER",
        }
        links.append(link_record)
        inertial_rows.append(
            {
                "link": name,
                "mass_kg_source": mass_text,
                "com_xyz_m_source": xyz_text,
                "com_rpy_rad_source": rpy_text,
                **{f"{key}_kg_m2_source": value
                   for key, value in inertia_text.items()},
                "mass_owner_id": "B601_URDF_OWNER",
            }
        )

    joints: list[dict[str, object]] = []
    joint_rows: list[dict[str, object]] = []
    children = set()
    outgoing: dict[str, list[str]] = defaultdict(list)
    for name in EXPECTED_JOINT_ORDER:
        node = joint_nodes[name]
        parent = node.find("parent").get("link")
        child = node.find("child").get("link")
        children.add(child)
        outgoing[parent].append(name)
        origin = node.find("origin")
        axis = node.find("axis")
        limit = node.find("limit")
        values = {
            "name": name,
            "type": node.get("type"),
            "parent": parent,
            "child": child,
            "origin_xyz_m_source": origin.get("xyz") or "0 0 0",
            "origin_rpy_rad_source": origin.get("rpy") or "0 0 0",
            "axis_source": axis.get("xyz") if axis is not None else "0 0 0",
            "limit_lower_source": limit.get("lower") if limit is not None else "",
            "limit_upper_source": limit.get("upper") if limit is not None else "",
            "limit_effort_source": limit.get("effort") if limit is not None else "",
            "limit_velocity_source": limit.get("velocity") if limit is not None else "",
        }
        joints.append(values)
        joint_rows.append(values.copy())

    roots = [name for name in EXPECTED_LINK_ORDER if name not in children]
    if roots != ["base_link"]:
        raise SystemExit(f"root drift: {roots}")

    frames: dict[str, np.ndarray] = {"base_link": np.eye(4)}
    joint_frames: dict[str, np.ndarray] = {}
    queue: deque[str] = deque(["base_link"])
    visited_joints: list[str] = []
    while queue:
        parent = queue.popleft()
        for joint_name in outgoing[parent]:
            joint = next(item for item in joints if item["name"] == joint_name)
            xyz = [float(value) for value in joint["origin_xyz_m_source"].split()]
            rpy = [float(value) for value in joint["origin_rpy_rad_source"].split()]
            t_parent_joint = transform(rpy_matrix(rpy), xyz)
            t_a0_joint = frames[parent] @ t_parent_joint
            # q=0: revolute and prismatic motions are identity/zero.
            frames[joint["child"]] = t_a0_joint.copy()
            joint_frames[joint_name] = t_a0_joint
            visited_joints.append(joint_name)
            queue.append(joint["child"])
    if set(frames) != set(EXPECTED_LINK_ORDER):
        raise SystemExit(f"disconnected chain: {sorted(set(EXPECTED_LINK_ORDER)-set(frames))}")

    frame_rows: list[dict[str, object]] = []
    for link_name in EXPECTED_LINK_ORDER:
        t_a0 = frames[link_name]
        row: dict[str, object] = {
            "frame": link_name,
            "parent_contract": "accepted URDF",
            "a0_x_mm": format(t_a0[0, 3] * 1000, ".12g"),
            "a0_y_mm": format(t_a0[1, 3] * 1000, ".12g"),
            "a0_z_mm": format(t_a0[2, 3] * 1000, ".12g"),
            "R_A0_frame_row_major": json.dumps(
                matrix_rows(t_a0[:3, :3]), separators=(",", ":")
            ),
        }
        for track_name, translation_mm in S_TRACKS_MM.items():
            p_s = translation_mm + R_SM @ (t_a0[:3, 3] * 1000)
            r_s = R_SM @ t_a0[:3, :3]
            row[f"{track_name}_xyz_mm"] = " ".join(
                format(float(value), ".12g") for value in p_s
            )
            row[f"{track_name}_R_row_major"] = json.dumps(
                matrix_rows(r_s), separators=(",", ":")
            )
        frame_rows.append(row)

    joint_axis_rows: list[dict[str, object]] = []
    for joint in joints:
        t_joint = joint_frames[joint["name"]]
        axis_local = np.array(
            [float(value) for value in joint["axis_source"].split()], dtype=float
        )
        axis_a0 = t_joint[:3, :3] @ axis_local
        joint_axis_rows.append(
            {
                "joint": joint["name"],
                "joint_type": joint["type"],
                "parent": joint["parent"],
                "child": joint["child"],
                "origin_A0_xyz_mm": " ".join(
                    format(float(value * 1000), ".12g")
                    for value in t_joint[:3, 3]
                ),
                "axis_joint_source": joint["axis_source"],
                "axis_A0_q0": " ".join(
                    format(float(value), ".12g") for value in axis_a0
                ),
                "cad_semantics": (
                    "ROTATION_DOF"
                    if joint["type"] in {"revolute", "continuous"}
                    else "TRANSLATION_DOF"
                    if joint["type"] == "prismatic"
                    else "FIXED"
                ),
            }
        )

    total_mass_source = str(mass_sum)
    contract = {
        "contract_id": "B5_0_ACCEPTED_B601_CHAIN",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": URDF.relative_to(WORKSPACE).as_posix(),
            "sha256": before,
            "editable": False,
        },
        "units": {
            "urdf_length": "m",
            "cad_length": "mm",
            "angle": "rad",
            "mass": "kg",
            "inertia": "kg*m^2",
        },
        "topology": {
            "root": "base_link",
            "link_count": len(links),
            "joint_count": len(joints),
            "joint_type_counts": {
                kind: sum(item["type"] == kind for item in joints)
                for kind in ("revolute", "fixed", "prismatic")
            },
            "joint_traversal_order": visited_joints,
        },
        "mass": {
            "total_kg_source_decimal": total_mass_source,
            "owner_id": "B601_URDF_OWNER",
            "physical_weighing": "PENDING_MEDIUM_CONFIDENCE",
            "cad_mass_authority": "EXCLUDED",
        },
        "spacecraft_mapping": {
            "R_SM_rows": matrix_rows(R_SM),
            "tracks_mm": {
                key: [float(value) for value in translation]
                for key, translation in S_TRACKS_MM.items()
            },
            "track_delta_mm": 12.75,
            "ruling": "DUAL_TRACK_EXPLICIT; do not bury delta in any joint origin",
        },
        "links": links,
        "joints": joints,
        "q0_frames_A0": {
            name: matrix_rows(value) for name, value in frames.items()
        },
        "q0_joint_frames_A0": {
            name: matrix_rows(value) for name, value in joint_frames.items()
        },
        "inertia_checks": inertia_checks,
        "claim_limit": (
            "Accepted digital kinematic/inertial truth only; not physical weigh-in, "
            "actuator qualification, manufacturing or flight authority."
        ),
    }

    checks = {
        "gate_id": "B5_0_G1_ACCEPTED_CHAIN_EXTRACTION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "urdf_hash_match": before == EXPECTED_URDF_SHA256,
            "link_order_match": list(link_nodes) == EXPECTED_LINK_ORDER,
            "joint_order_match": list(joint_nodes) == EXPECTED_JOINT_ORDER,
            "one_root": roots == ["base_link"],
            "all_links_connected": set(frames) == set(EXPECTED_LINK_ORDER),
            "joint_type_counts_match": {
                "revolute": sum(item["type"] == "revolute" for item in joints) == 6,
                "fixed": sum(item["type"] == "fixed" for item in joints) == 1,
                "prismatic": sum(item["type"] == "prismatic" for item in joints) == 2,
            },
            "all_meshes_present": len(mesh_rows) == 10,
            "visual_collision_meshes_match": all(
                bool(row["visual_equals_collision"]) for row in mesh_rows
            ),
            "all_inertias_positive_definite": all(
                bool(value["positive_definite"])
                for value in inertia_checks.values()
            ),
            "all_inertias_triangle_valid": all(
                bool(value["triangle_inequality"])
                for value in inertia_checks.values()
            ),
            "total_mass_exact": total_mass_source == "4.6955559493429862",
            "joint2_axis_sign_preserved": next(
                item for item in joints if item["name"] == "joint2"
            )["axis_source"] == "0 0 -1",
        },
        "recommended_cad_comparison_thresholds": {
            "joint_origin_translation_mm": 0.01,
            "joint_axis_angle_deg": 0.001,
            "zero_orientation_deg": 0.001,
            "link_frame_fk_position_mm": 0.05,
            "gripper_link_fk_position_mm": 0.10,
            "fk_orientation_deg": 0.01,
            "mesh_bbox_axis_mm": 0.05,
            "model_mass_kg": 1e-9,
        },
    }
    flat_checks: list[bool] = []
    for value in checks["checks"].values():
        if isinstance(value, dict):
            flat_checks.extend(bool(item) for item in value.values())
        else:
            flat_checks.append(bool(value))
    checks["verdict"] = (
        "B5_0_G1_ACCEPTED_CHAIN_EXTRACTION_PASS"
        if all(flat_checks)
        else "B5_0_G1_ACCEPTED_CHAIN_EXTRACTION_FAIL"
    )

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "accepted_chain.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "chain_validation.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    csv_write(OUT / "accepted_link_inertials.csv", inertial_rows)
    csv_write(OUT / "accepted_joint_contract.csv", joint_rows)
    csv_write(OUT / "q0_link_frames.csv", frame_rows)
    csv_write(OUT / "q0_joint_axes.csv", joint_axis_rows)
    csv_write(OUT / "accepted_mesh_contract.csv", mesh_rows)

    after = sha256(URDF)
    if after != before:
        raise SystemExit("accepted URDF changed during read-only extraction")
    if checks["verdict"].endswith("_FAIL"):
        raise SystemExit(json.dumps(checks, ensure_ascii=False))
    print(
        json.dumps(
            {
                "verdict": checks["verdict"],
                "links": len(links),
                "joints": len(joints),
                "mass_kg_source": total_mass_source,
                "gripper_link_q0_A0_mm": [
                    float(value * 1000)
                    for value in frames["gripper_link"][:3, 3]
                ],
                "outputs": 7,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
