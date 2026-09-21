from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import sys
import textwrap
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, Polygon, Rectangle, Wedge
import yaml


PROJECT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RAPID = PROJECT / "20_engineering" / "F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
V5 = PROJECT / "20_engineering" / "F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
V4 = PROJECT / "20_engineering" / "F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
V2 = PROJECT / "20_engineering" / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
URDF = PROJECT / "20_engineering" / "cad" / "spacecraft_layout" / "arm_b601_v1" / "arm_b601_v1.urdf"

INTERFACES = RAPID / "02_interfaces"
DRAWINGS = RAPID / "03_drawings"
VIS = RAPID / "05_visualization"
PACK_ROOT = RAPID / "06_pack_and_go"
PACKAGE = PACK_ROOT / "V5R_NEUTRAL_OPERATIONAL_PACKAGE"
EVIDENCE = RAPID / "07_evidence"

NEUTRAL_STEP = RAPID / "01_native_cad" / "SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.step"
NEUTRAL_FCSTD = RAPID / "01_native_cad" / "SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.FCStd"
VISUAL_MESH = RAPID / "01_native_cad" / "SEI_MECH_B601_V5R_VISUAL_MESH.stl"
COLLISION_MESH = RAPID / "01_native_cad" / "SEI_MECH_B601_V5R_COLLISION_MESH.stl"
LIGHTWEIGHT_SLDASM = RAPID / "01_native_cad" / "SEI_MECH_B601_V5R_LIGHTWEIGHT_OPERATIONAL_BASELINE.SLDASM"
GRIPPER_R1_ROOT = RAPID / "01_native_cad" / "gripper_r1"
GRIPPER_R1_ASSETS = [
    GRIPPER_R1_ROOT / "B601_GRIPPER_PALM_RAIL_SLOT_R1.step",
    GRIPPER_R1_ROOT / "B601_GRIPPER_PALM_RAIL_SLOT_R1.stl",
    GRIPPER_R1_ROOT / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step",
    GRIPPER_R1_ROOT / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.stl",
    GRIPPER_R1_ROOT / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step",
    GRIPPER_R1_ROOT / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.stl",
    GRIPPER_R1_ROOT / "B601_GRIPPER_LEFT_FINGER_NEUTRAL_SOURCE.stl",
    GRIPPER_R1_ROOT / "B601_GRIPPER_RIGHT_FINGER_NEUTRAL_SOURCE.stl",
]

GRIPPER_RECEIPT_CANDIDATES = [
    RAPID / "04_validation" / "GRIPPER_R1_GEOMETRY_VALIDATION.json",
    RAPID / "04_validation" / "B601_GRIPPER_PALM_RAIL_SLOT_R1_VALIDATION.json",
    RAPID / "04_validation" / "GRIPPER_R1_VALIDATION.json",
]

STAMP = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
OWNER_RULING = "AUTHORIZE_LOW_MEMORY_EXECUTION_WITH_BOUNDED_NATIVE_ATTEMPTS"
BASELINE_ID = "F3R2_V5R_NEUTRAL_OPERATIONAL_MECHANICAL_BASELINE_20260820"


def ensure_dirs() -> None:
    for path in (INTERFACES, DRAWINGS, VIS, PACK_ROOT, PACKAGE, EVIDENCE):
        path.mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    try:
        return path.relative_to(PROJECT).as_posix()
    except ValueError:
        return path.as_posix()


def asset_record(path: Path, status_if_present: str = "PRESENT") -> dict:
    exists = path.is_file() and path.stat().st_size > 0
    return {
        "path": rel(path),
        "absolute_path": path.as_posix(),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else None,
        "sha256": sha256(path) if exists else None,
        "status": status_if_present if exists else "HOLD_MISSING_OR_ZERO_BYTE",
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_yaml(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True, width=120)


def write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_gripper_receipt() -> tuple[Path | None, dict | None]:
    for path in GRIPPER_RECEIPT_CANDIDATES:
        if path.is_file():
            try:
                return path, json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception:
                return path, None
    return None, None


def gripper_truth() -> dict:
    path, payload = read_gripper_receipt()
    if not path or not isinstance(payload, dict):
        return {
            "status": "HOLD_NO_R1_CONTINUOUS_SWEEP_VALIDATION_RECEIPT",
            "post_rows": 36,
            "positive_overlap_volume_mm3": 2046.563836,
            "native_v5_remaining_count": 36,
            "native_v5_reintegration_status": "HOLD",
            "removed_volume_mm3": None,
            "estimated_mass_delta_g": None,
            "minimum_remaining_wall_thickness_mm": None,
            "minimum_remaining_wall_thickness_status": "HOLD",
            "outputs": {},
            "receipt": None,
            "manufacturing_clearance": "HOLD",
            "structural_strength": "HOLD",
        }
    raw_status = str(
        payload.get("status")
        or payload.get("verdict")
        or payload.get("gripper_geometry_correction_status")
        or "HOLD_UNRECOGNIZED_RECEIPT"
    )
    rows = payload.get("pose_induced_rail_palm_interference_rows")
    if rows is None:
        rows = payload.get("post_interference_rows")
    volume = payload.get("positive_overlap_volume_mm3")
    if volume is None:
        volume = payload.get("post_positive_overlap_volume_mm3")
    pass_by_metrics = rows == 0 and volume == 0
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    return {
        "status": "GRIPPER_GEOMETRY_CORRECTION_PASS_NEUTRAL_ONLY" if pass_by_metrics else raw_status,
        "post_rows": rows if rows is not None else 36,
        "positive_overlap_volume_mm3": volume if volume is not None else 2046.563836,
        "native_v5_remaining_count": payload.get("native_v5_remaining_count", 36),
        "native_v5_reintegration_status": payload.get("native_v5_reintegration_status", "HOLD"),
        "removed_volume_mm3": metrics.get("removed_volume_mm3"),
        "estimated_mass_delta_g": -abs(float(metrics["estimated_mass_delta_g"])) if metrics.get("estimated_mass_delta_g") is not None else None,
        "minimum_remaining_wall_thickness_mm": metrics.get("minimum_remaining_wall_thickness_mm"),
        "minimum_remaining_wall_thickness_status": metrics.get("minimum_remaining_wall_thickness_status", "HOLD"),
        "outputs": outputs,
        "receipt": rel(path),
        "manufacturing_clearance": payload.get("manufacturing_clearance_status", "HOLD"),
        "structural_strength": payload.get("structural_strength_status", "HOLD"),
    }


def parse_urdf() -> tuple[list[dict], list[dict]]:
    robot = ET.parse(URDF).getroot()
    links: list[dict] = []
    joints: list[dict] = []
    for link in robot.findall("link"):
        inertial = link.find("inertial")
        visual_mesh = link.find("visual/geometry/mesh")
        collision_mesh = link.find("collision/geometry/mesh")
        links.append(
            {
                "name": link.attrib["name"],
                "mass_kg": float(inertial.find("mass").attrib["value"]),
                "com_xyz_m": inertial.find("origin").attrib["xyz"],
                "visual_mesh": visual_mesh.attrib["filename"],
                "collision_mesh": collision_mesh.attrib["filename"],
            }
        )
    for joint in robot.findall("joint"):
        limit = joint.find("limit")
        joints.append(
            {
                "name": joint.attrib["name"],
                "type": joint.attrib["type"],
                "parent": joint.find("parent").attrib["link"],
                "child": joint.find("child").attrib["link"],
                "origin_xyz_m": joint.find("origin").attrib["xyz"],
                "origin_rpy_rad": joint.find("origin").attrib["rpy"],
                "axis": joint.find("axis").attrib["xyz"],
                "lower": limit.attrib.get("lower", "") if limit is not None else "",
                "upper": limit.attrib.get("upper", "") if limit is not None else "",
                "effort": limit.attrib.get("effort", "") if limit is not None else "",
                "velocity": limit.attrib.get("velocity", "") if limit is not None else "",
            }
        )
    return links, joints


def read_v5_link_map() -> dict[str, dict]:
    path = V5 / "09_digital_thread" / "V5_LINK_COMPONENT_MAPPING.csv"
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["urdf_link"]: row for row in rows if row.get("urdf_link")}


def native_gripper_parts() -> dict[str, Path]:
    root = V5 / "01_native_parts" / "gripper"
    return {
        "gripper_link": root / "B601_GRIPPER_PALM.SLDPRT",
        "gripper_left": root / "B601_GRIPPER_LEFT_FINGER.SLDPRT",
        "gripper_right": root / "B601_GRIPPER_RIGHT_FINGER.SLDPRT",
    }


def generate_joint_and_frame_files(links: list[dict], joints: list[dict]) -> None:
    link_map = read_v5_link_map()
    gripper_parts = native_gripper_parts()
    rows = []
    joint_by_child = {joint["child"]: joint for joint in joints}
    for link in links:
        name = link["name"]
        joint = joint_by_child.get(name, {})
        src = link_map.get(name, {})
        native_path = Path(src["native_path"]) if src.get("native_path") else gripper_parts.get(name)
        if name in gripper_parts:
            native_path = gripper_parts[name]
        rows.append(
            {
                "urdf_link": name,
                "urdf_joint": joint.get("name", ""),
                "joint_type": joint.get("type", "ROOT"),
                "parent_link": joint.get("parent", ""),
                "cad_component": src.get("component_name2") or (native_path.stem if native_path else "UNMAPPED"),
                "cad_native_path": rel(native_path) if native_path else "",
                "cad_native_sha256": sha256(native_path) if native_path else "",
                "joint_origin_xyz_m": joint.get("origin_xyz_m", "0 0 0"),
                "joint_origin_rpy_rad": joint.get("origin_rpy_rad", "0 0 0"),
                "joint_axis": joint.get("axis", ""),
                "lower_limit": joint.get("lower", ""),
                "upper_limit": joint.get("upper", ""),
                "urdf_mass_kg": f"{link['mass_kg']:.15g}",
                "mass_authority": "ACCEPTED_URDF",
                "mapping_status": "MAPPED_WITH_GRIPPER_R1_HOLD" if name.startswith("gripper") else "MAPPED_FROM_FROZEN_V5_THREAD",
                "notes": "Accepted URDF is unmodified; CAD is geometry comparison only.",
            }
        )
    fields = list(rows[0].keys())
    write_csv(INTERFACES / "B601_URDF_CAD_JOINT_MAP.csv", fields, rows)

    frame_rows = []
    frame_rows.append(
        {
            "frame": "spacecraft_assembly_frame",
            "parent": "",
            "source": "F3R2_FRAME_MAPPING_V1",
            "translation_xyz": "0 0 0",
            "rpy": "0 0 0",
            "units": "mm,rad",
            "status": "NEUTRAL_ROOT_FRAME",
            "notes": "Neutral interface root; not a native CAD screenshot assertion.",
        }
    )
    frame_rows.append(
        {
            "frame": "arm_base_frame",
            "parent": "spacecraft_assembly_frame",
            "source": "F3R2_FRAME_MAPPING_V1 arm_mount_transform_mm",
            "translation_xyz": "208 0 0",
            "rpy": "MATRIX_DEFINED_IN_SYSTEM_FRAME_TREE",
            "units": "mm,rad",
            "status": "FROZEN_MAPPING",
            "notes": "Equals accepted URDF base_link nominal frame.",
        }
    )
    for joint in joints:
        frame_rows.append(
            {
                "frame": f"{joint['child']}_frame",
                "parent": f"{joint['parent']}_frame" if joint["parent"] != "base_link" else "arm_base_frame",
                "source": "accepted arm_b601_v1.urdf",
                "translation_xyz": joint["origin_xyz_m"],
                "rpy": joint["origin_rpy_rad"],
                "units": "m,rad",
                "status": "URDF_AUTHORITY",
                "notes": f"{joint['name']} axis={joint['axis']} type={joint['type']}",
            }
        )
    for frame, parent, notes in (
        ("gripper_contact_left", "gripper_left_frame", "Contact frame is semantic; calibration/normal authority HOLD."),
        ("gripper_contact_right", "gripper_right_frame", "Contact frame is semantic; calibration/normal authority HOLD."),
        ("camera_optical_frame", "link6_frame", "Proposed only; camera selection and hand-eye calibration HOLD."),
        ("left_wing_hinge_axis", "spacecraft_assembly_frame", "Axis +X through (-61,143.15,0) mm from B-rep probe."),
        ("right_wing_hinge_axis", "spacecraft_assembly_frame", "Axis +X through (-61,-143.15,0) mm from B-rep probe."),
    ):
        frame_rows.append(
            {
                "frame": frame,
                "parent": parent,
                "source": "F3R2_FRAME_MAPPING_V1 / interface semantics",
                "translation_xyz": "SEE_SYSTEM_FRAME_TREE",
                "rpy": "SEE_SYSTEM_FRAME_TREE",
                "units": "mm,rad",
                "status": "PROVISIONAL_HOLD" if "camera" in frame or "contact" in frame else "FROZEN_MAPPING",
                "notes": notes,
            }
        )
    write_csv(INTERFACES / "B601_FRAME_MAP.csv", list(frame_rows[0].keys()), frame_rows)

    frame_tree = {
        "schema": "SYSTEM_FRAME_TREE_V1",
        "baseline_id": BASELINE_ID,
        "units": {"system_translation": "mm", "urdf_translation": "m", "rotation": "radians unless explicitly degrees"},
        "root_frame": "spacecraft_assembly_frame",
        "frames": {
            "spacecraft_assembly_frame": {"parent": None, "transform": "identity", "status": "NEUTRAL_ROOT_FRAME"},
            "M_FRAME": {
                "parent": "spacecraft_assembly_frame",
                "transform": "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED",
                "status": "HOLD_ROOT_TO_M_FRAME_NOT_REASSERTED_BY_NEUTRAL_PACKAGE",
            },
            "B601_AS_BUILT_PATTERN_DATUM": {
                "parent": "M_FRAME",
                "translation_xyz_mm": [25.155, 0.015994151, -0.08636607],
                "rotation_about_x_deg": 25.000014,
                "rotation_matrix": [
                    [1.0, 0.0, 0.0],
                    [0.0, 0.9063076848, -0.4226184837],
                    [0.0, 0.4226184837, 0.9063076848],
                ],
                "status": "MEASURED_COMPETITION_DATUM_NOT_OEM_FLANGE",
                "source": rel(V2 / "03_native_cad" / "M3_interface_authority" / "M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json"),
            },
            "M3R_STAGE_A_RING": {
                "parent": "B601_AS_BUILT_PATTERN_DATUM",
                "transform": "identity_at_competition_pattern_datum",
                "status": "COMPETITION_INTERFACE_FRAME",
            },
            "M3R_STAGE_B_LOAD_DIFFUSION_PLATE": {
                "parent": "M3R_STAGE_A_RING",
                "transform": "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED",
                "status": "GEOMETRY_PRESENT_FASTENER_AND_LOCATING_FIT_HOLD",
            },
            "arm_base_frame": {
                "parent": "spacecraft_assembly_frame",
                "transform_mm_rows": [
                    [0.0, 0.0, 1.0, 208.0],
                    [0.422618, 0.906308, 0.0, 0.0],
                    [-0.906308, 0.422618, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
                "equals": "accepted URDF base_link nominal frame",
                "status": "FROZEN_F3R2_MAPPING",
            },
            "left_wing_hinge_axis": {
                "parent": "spacecraft_assembly_frame",
                "point_xyz_mm": [-61.0, 143.15, 0.0],
                "axis_xyz": [1.0, 0.0, 0.0],
                "status": "B_REP_PROBE_MAPPING",
            },
            "right_wing_hinge_axis": {
                "parent": "spacecraft_assembly_frame",
                "point_xyz_mm": [-61.0, -143.15, 0.0],
                "axis_xyz": [1.0, 0.0, 0.0],
                "status": "B_REP_PROBE_MAPPING",
            },
            "camera_optical_frame": {
                "parent": "link6_frame",
                "transform": "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED",
                "status": "HOLD_CAMERA_SELECTION_AND_CALIBRATION",
            },
            "gripper_contact_left": {
                "parent": "gripper_left_frame",
                "transform": "SEMANTIC_CONTACT_FRAME; NORMAL_AUTHORITY_PENDING",
                "status": "PROVISIONAL_FOR_SIM13_STATE_INTERFACE",
            },
            "gripper_contact_right": {
                "parent": "gripper_right_frame",
                "transform": "SEMANTIC_CONTACT_FRAME; NORMAL_AUTHORITY_PENDING",
                "status": "PROVISIONAL_FOR_SIM13_STATE_INTERFACE",
            },
            "CAMERA_KEEP_OUT": {
                "parent": "camera_optical_frame",
                "transform": "V4_V5_STATIC_ENVELOPE_SEMANTICS",
                "status": "KEEP_OUT_ONLY_CAMERA_SELECTION_HOLD",
            },
            "CABLE_KEEP_OUT": {
                "parent": "arm_base_frame",
                "transform": "V4_V5_OD9_STATIC_ENVELOPE_SEMANTICS",
                "status": "STATIC_KEEP_OUT_MOVING_SWEEP_HOLD",
            },
            "ARM_HDRM_RELEASE_SWEEP_KEEP_OUT": {
                "parent": "spacecraft_assembly_frame",
                "transform": "V4_V5_RELEASE_SWEEP_ENVELOPE_SEMANTICS",
                "status": "KEEP_OUT_ONLY_HDRM_RELIABILITY_HOLD",
            },
        },
        "urdf_chain": [
            {"joint": j["name"], "parent": j["parent"], "child": j["child"], "xyz_m": j["origin_xyz_m"], "rpy_rad": j["origin_rpy_rad"], "axis": j["axis"]}
            for j in joints
        ],
        "integrity": {"accepted_urdf_modified": False, "native_top_assembly_status": "HOLD", "neutral_only": True},
    }
    # Materialize the URDF link-frame chain inside the loader-visible frames map;
    # the separate urdf_chain section is documentary and is intentionally not
    # relied upon by the sim13 tree validator.
    for joint in joints:
        frame_tree["frames"][f"{joint['child']}_frame"] = {
            "parent": "arm_base_frame" if joint["parent"] == "base_link" else f"{joint['parent']}_frame",
            "translation_xyz_m": [float(value) for value in joint["origin_xyz_m"].split()],
            "rpy_rad": [float(value) for value in joint["origin_rpy_rad"].split()],
            "axis_xyz": [float(value) for value in joint["axis"].split()],
            "joint": joint["name"],
            "joint_type": joint["type"],
            "status": "ACCEPTED_URDF_FRAME_AUTHORITY",
        }
    write_yaml(INTERFACES / "SYSTEM_FRAME_TREE.yaml", frame_tree)


def generate_mass_files(links: list[dict], gripper: dict) -> None:
    rows = []
    for link in links:
        rows.append(
            {
                "item": link["name"],
                "urdf_mass_kg": f"{link['mass_kg']:.15g}",
                "cad_mass_kg": "",
                "delta_kg": "",
                "authority": "ACCEPTED_URDF",
                "cad_comparison_status": "HOLD_NATIVE_CAD_MASS_NOT_READ_BACK",
                "notes": "Do not infer mass from visual or collision mesh.",
            }
        )
    total = sum(item["mass_kg"] for item in links)
    rows.append(
        {
            "item": "B601_TOTAL_10_LINKS",
            "urdf_mass_kg": f"{total:.15f}",
            "cad_mass_kg": "",
            "delta_kg": "",
            "authority": "ACCEPTED_URDF",
            "cad_comparison_status": "URDF_AUTHORITY_CAD_COMPARISON_HOLD",
            "notes": "10 links; 9 joints (6R + 1 fixed + 2P).",
        }
    )
    write_csv(INTERFACES / "CAD_URDF_MASS_COMPARISON.csv", list(rows[0].keys()), rows)

    mass_rows = [
        {
            "item": "B601_ARM_WITH_GRIPPER",
            "mass_value": f"{total:.15f}",
            "units": "kg",
            "source": rel(URDF),
            "authority": "DYNAMICS_AUTHORITY",
            "status": "ACCEPTED_URDF",
            "hold": "PHYSICAL_WEIGHING_PENDING_CONFIDENCE_MEDIUM",
        },
        {
            "item": "M3R_STAGE_A_PLUS_STAGE_B_OWNER_FROZEN_SUMMARY",
            "mass_value": "0.761904197",
            "units": "kg",
            "source": rel(V2 / "03_native_cad" / "M3_interface_authority" / "M3R_ADAPTER_BOM_CANDIDATE.csv"),
            "authority": "OWNER_FROZEN_APPROXIMATE_MASS",
            "status": "PROVISIONAL",
            "hold": "M3R_MASS_RECONCILIATION_HOLD",
        },
        {
            "item": "M3R_STAGE_A_PLUS_STAGE_B_V5_CAD_DENSITY_PROVISIONAL",
            "mass_value": "0.782327248",
            "units": "kg",
            "source": rel(V5 / "08_bom" / "V5_NATIVE_BOM_SEED.csv"),
            "authority": "CAD_COMPARISON_ONLY",
            "status": "SOURCE_CONFLICT_PLUS_0.020423051_KG",
            "hold": "M3R_MASS_RECONCILIATION_HOLD;NATIVE_MASS_MEASUREMENT_PENDING",
        },
        {
            "item": "TARGET_SATELLITE_ANCHOR",
            "mass_value": "22",
            "units": "kg",
            "source": "OWNER_EMERGENCY_RULING_2026-08-20",
            "authority": "SIM13_SCENARIO_ANCHOR",
            "status": "SCENARIO_ONLY",
            "hold": "NOT_A_FLIGHT_HARDWARE_MASS_ASSERTION",
        },
        {
            "item": "TARGET_DEBRIS_ANCHOR",
            "mass_value": "150",
            "units": "kg",
            "source": "OWNER_EMERGENCY_RULING_2026-08-20",
            "authority": "SIM13_SCENARIO_ANCHOR",
            "status": "SCENARIO_ONLY",
            "hold": "NOT_A_FLIGHT_HARDWARE_MASS_ASSERTION",
        },
        {
            "item": "SPACECRAFT_BUS_AND_SOLAR_ARRAYS",
            "mass_value": "",
            "units": "kg",
            "source": "NEUTRAL_GEOMETRY_ONLY",
            "authority": "NONE",
            "status": "HOLD",
            "hold": "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED",
        },
    ]
    mass_rows.insert(
        1,
        {
            "item": "B601_GRIPPER_PALM_RAIL_SLOT_R1_ESTIMATED_DELTA",
            "mass_value": str(gripper["estimated_mass_delta_g"]),
            "units": "g",
            "source": gripper["receipt"] or "NO_R1_RECEIPT",
            "authority": "GEOMETRY_DERIVATIVE_COMPARISON_ONLY_URDF_UNCHANGED",
            "status": gripper["status"],
            "hold": "MASS_ESTIMATE_NOT_APPLIED_TO_ACCEPTED_URDF;PHYSICAL_WEIGHING_HOLD",
        },
    )
    write_csv(INTERFACES / "MASS_PROPERTIES_TABLE.csv", list(mass_rows[0].keys()), mass_rows)


CONFIGS = [
    ("DEPLOYED_NOMINAL", "SYSTEM", "L=DEPLOYED;R=DEPLOYED;arm=TASK_READY", "SIM13_PRIMARY"),
    ("LEFT_PANEL_FAIL", "SYSTEM", "L=STOWED;R=DEPLOYED;arm=RESTRAINED", "OFF_NOMINAL"),
    ("RIGHT_PANEL_FAIL", "SYSTEM", "L=DEPLOYED;R=STOWED;arm=RESTRAINED", "OFF_NOMINAL"),
    ("BOTH_PANEL_FAIL", "SYSTEM", "L=STOWED;R=STOWED;arm=RESTRAINED", "OFF_NOMINAL"),
    ("ARM_STOWED_ONORBIT", "ARM", "q=[145.572,-168,-57,-41.143,-20.954,-3] deg", "ONORBIT_SEMANTIC"),
    ("ARM_TASK_READY", "ARM", "q=[0,0,0,0,0,0] deg", "SIM13_PRIMARY"),
    ("GRIPPER_CLOSED", "GRIPPER", "left/right prismatic=0.0000 m", "SEMANTIC"),
    ("GRIPPER_PARTIAL", "GRIPPER", "left/right prismatic=0.023833 m", "SEMANTIC"),
    ("GRIPPER_PREGRASP", "GRIPPER", "left/right prismatic=0.047667 m", "SEMANTIC"),
    ("GRIPPER_OPEN", "GRIPPER", "left/right prismatic=0.0715 m", "SEMANTIC"),
]


def generate_configuration_and_interference(gripper: dict) -> None:
    config_rows = []
    for name, kind, summary, use in CONFIGS:
        config_rows.append(
            {
                "configuration": name,
                "configuration_class": kind,
                "unique_geometry_summary": summary,
                "interface_acceptance": "ACCEPTED_FOR_NEUTRAL_SIM_STATE_ENUM",
                "independent_activation": "SEMANTIC_STATE_ONLY",
                "native_rebuild": "HOLD_NATIVE_TOP_ASSEMBLY",
                "neutral_reload": "HOLD_NO_PARAMETRIC_CONFIGURATION_READBACK",
                "suppression_mate_readback": "NOT_APPLICABLE_TO_SINGLE_NEUTRAL_BREP",
                "bounding_box": "HOLD_PER_CONFIGURATION_BBOX_NOT_MEASURED",
                "external_interference": "HOLD_INDEPENDENT_CONTINUOUS_COLLISION_TEST",
                "sim13_use": use,
                "qualification": "ONORBIT_COMPETITION_PROTOTYPE_ONLY",
            }
        )
    write_csv(INTERFACES / "CONFIGURATION_MATRIX.csv", list(config_rows[0].keys()), config_rows)

    post_rows = gripper["post_rows"]
    post_volume = gripper["positive_overlap_volume_mm3"]
    class2_status = "PASS" if post_rows == 0 and post_volume == 0 else "HOLD"
    interference_rows = [
        {
            "class_id": "CLASS_1",
            "classification": "DONOR_STATIC_INHERITED_INTERFERENCE",
            "scope": "V5_NATIVE_HISTORICAL",
            "pre_count": 81,
            "post_count": 81,
            "positive_overlap_volume_mm3": "NOT_RECOMPUTED",
            "status": "ACCEPTED_EXCEPTION_OPTION_A_HISTORICAL_ONLY",
            "disposition": "Preserve evidence; exclude only from system-external count under signed Option A.",
            "evidence": rel(V5 / "00_authority" / "V5_LOOP1C1_INTERFERENCE_FINGERPRINT_ACCEPTANCE.json"),
        },
        {
            "class_id": "CLASS_2",
            "classification": "B601_GRIPPER_PALM_RAIL_SLOT_GEOMETRY_HOLD",
            "scope": "NEUTRAL_R1_DERIVATIVE",
            "pre_count": 36,
            "post_count": post_rows,
            "positive_overlap_volume_mm3": post_volume,
            "status": class2_status,
            "disposition": f"{gripper['status']}; native V5 remains {gripper['native_v5_remaining_count']} rows and reintegration HOLD",
            "evidence": gripper["receipt"] or rel(V5 / "04_configurations" / "V5_LOOP1C1_INTERFERENCE_FINGERPRINT_REGISTER.csv"),
        },
        {
            "class_id": "CLASS_3_MAIN",
            "classification": "SYSTEM_EXTERNAL_UNEXPLAINED_MAIN_NEUTRAL",
            "scope": "BYTE_IDENTICAL_V2_F3R2_MAIN_NEUTRAL_DEPLOYED_NOMINAL_AND_SERVICE",
            "pre_count": 0,
            "post_count": 0,
            "positive_overlap_volume_mm3": 0,
            "status": "PASS_REUSED_ONLY_FOR_HASH_IDENTICAL_MAIN_NEUTRAL_GEOMETRY",
            "disposition": "Does not propagate to separately packaged V4/R1 addenda.",
            "evidence": rel(V2 / "05_clearance" / "F3R2_NATIVE_INTERFERENCE_OUTCOME.json"),
        },
        {
            "class_id": "CLASS_3_COMPOSITE",
            "classification": "PACKAGE_ADDENDA_EXTERNAL_INTERFERENCE",
            "scope": "MAIN_NEUTRAL_PLUS_V4_DELTA_PLUS_GRIPPER_R1_PACKAGE_COMPOSITE",
            "pre_count": "UNKNOWN",
            "post_count": "UNKNOWN",
            "positive_overlap_volume_mm3": "UNKNOWN",
            "status": "HOLD_UNKNOWN_ADDENDA_NOT_MONOLITHICALLY_PLACED_OR_NARROW_PHASE_VALIDATED",
            "disposition": "UNKNOWN must fail closed in sim13; main-neutral zero is not extended to composite package.",
            "evidence": rel(PACK_ROOT / "NEUTRAL_PACKAGE_VALIDATION.json"),
        },
    ]
    write_csv(INTERFACES / "INTERFERENCE_CLASSIFICATION.csv", list(interference_rows[0].keys()), interference_rows)


def generate_bom_and_datums(gripper: dict) -> None:
    components = [
        ("12U_BUS", "V2_2 main neutral STEP/FCStd", "MAIN_NEUTRAL_GEOMETRY_PRESENT"),
        ("M3R_STAGE_A_RING", "V4_B601_STAGE_A_INTERFACE_RING_REVB.step addendum", "PACKAGE_ADDENDUM_PRESENT;MONOLITHIC_PLACEMENT_HOLD"),
        ("M3R_STAGE_B_LOAD_DIFFUSION_PLATE", "V4_B601_STAGE_B_LOAD_ADAPTER_REVB2.step addendum", "PACKAGE_ADDENDUM_PRESENT;MONOLITHIC_PLACEMENT_AND_MASS_RECONCILIATION_HOLD"),
        ("B601_BASE", "accepted URDF base_link", "URDF_AUTHORITY"),
        ("B601_LINK_1", "accepted URDF link1", "URDF_AUTHORITY"),
        ("B601_LINK_2", "accepted URDF link2", "URDF_AUTHORITY"),
        ("B601_LINK_3", "accepted URDF link3", "URDF_AUTHORITY"),
        ("B601_LINK_4", "accepted URDF link4", "URDF_AUTHORITY"),
        ("B601_LINK_5", "accepted URDF link5", "URDF_AUTHORITY"),
        ("B601_LINK_6", "accepted URDF link6", "URDF_AUTHORITY"),
        ("B601_WRIST_FIXED", "accepted URDF gripper_joint", "URDF_AUTHORITY"),
        ("B601_GRIPPER_R1", "gripper_r1/B601_GRIPPER_PALM_RAIL_SLOT_R1.step addendum", f"{gripper['status']};NATIVE_V5_REINTEGRATION_HOLD"),
        ("SOLAR_ARRAY_LEFT", "V2_2/V5 left wing", "GEOMETRY_SOURCE_PRESENT;CONFIG_READBACK_HOLD"),
        ("SOLAR_ARRAY_RIGHT", "V2_2/V5 right wing", "GEOMETRY_SOURCE_PRESENT;CONFIG_READBACK_HOLD"),
        ("LEFT_WING_ROOT_HINGE", "V5 LEFT_WING_ROOT_TRUE_HINGE", "NATIVE_SUBASSEMBLY_PRESENT"),
        ("RIGHT_WING_ROOT_HINGE", "V5 RIGHT_WING_ROOT_TRUE_HINGE", "NATIVE_SUBASSEMBLY_PRESENT"),
        ("G07_SUPPORT", "V5 G07_PRIMARY_SUPPORT_V2", "NATIVE_SUBASSEMBLY_PRESENT"),
        ("G08_SUPPORT", "V5 G08_PRIMARY_SUPPORT_V2", "NATIVE_SUBASSEMBLY_PRESENT"),
        ("MID_SUPPORT", "V5 MID_BACKUP_SUPPORT_V2", "NATIVE_SUBASSEMBLY_PRESENT"),
        ("CAMERA_KEEP_OUT", "V4/V5 envelope", "KEEP_OUT_ONLY;CAMERA_SELECTION_HOLD"),
        ("CABLE_KEEP_OUT", "V4/V5 OD9 envelope", "KEEP_OUT_ONLY;HARNESS_SWEEP_HOLD"),
        ("TARGET_SATELLITE_22KG", "sim13 analytic/proxy object", "SCENARIO_ASSET_NOT_FLIGHT_CAD"),
        ("TARGET_DEBRIS_150KG", "sim13 analytic/proxy object", "SCENARIO_ASSET_NOT_FLIGHT_CAD"),
    ]
    rows = []
    for idx, (name, source, status) in enumerate(components, 1):
        rows.append(
            {
                "item": idx,
                "component": name,
                "quantity": 1,
                "source": source,
                "material": "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED",
                "tolerance": "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED",
                "finish": "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED",
                "fastener_torque": "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED",
                "status": status,
                "release_scope": "COMPETITION_PROTOTYPE_ONORBIT_OPERATIONAL_INTERFACE",
            }
        )
    write_csv(INTERFACES / "TOP_LEVEL_BOM.csv", list(rows[0].keys()), rows)

    datum_rows = [
        {"datum": "spacecraft_assembly_frame", "parent": "", "definition": "Neutral assembly root", "source": "F3R2_FRAME_MAPPING_V1", "status": "NEUTRAL_ROOT"},
        {"datum": "M_FRAME", "parent": "spacecraft_assembly_frame", "definition": "Mechanical interface frame", "source": "M3R T_SM authority", "status": "ROOT_RELATION_HOLD"},
        {"datum": "B601_AS_BUILT_PATTERN_DATUM", "parent": "M_FRAME", "definition": "t=[25.155,0.015994151,-0.08636607] mm; Rx=25.000014 deg", "source": "M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json", "status": "MEASURED_COMPETITION_DATUM"},
        {"datum": "arm_base_frame", "parent": "spacecraft_assembly_frame", "definition": "translation [208,0,0] mm; matrix in SYSTEM_FRAME_TREE", "source": "F3R2_FRAME_MAPPING_V1", "status": "FROZEN_MAPPING"},
        {"datum": "M3R_ARM_PATTERN", "parent": "B601_AS_BUILT_PATTERN_DATUM", "definition": "4xM4-class; 64x64 mm; PCD 90.509641772 mm", "source": "Owner frozen fact", "status": "COMPETITION_INTERFACE"},
        {"datum": "M3R_CLOCKING", "parent": "M_FRAME", "definition": "25.000014 deg", "source": "M3R T_SM authority", "status": "MEASURED_DATUM"},
        {"datum": "M3R_CONTINUOUS_MOUNTING_FACE", "parent": "M3R_ARM_PATTERN", "definition": "false", "source": "Owner frozen fact", "status": "NO_CONTINUOUS_FACE"},
        {"datum": "left_wing_hinge_axis", "parent": "spacecraft_assembly_frame", "definition": "point [-61,143.15,0] mm; axis +X", "source": "B-rep probe", "status": "MAPPED"},
        {"datum": "right_wing_hinge_axis", "parent": "spacecraft_assembly_frame", "definition": "point [-61,-143.15,0] mm; axis +X", "source": "B-rep probe", "status": "MAPPED"},
        {"datum": "camera_optical_frame", "parent": "link6_frame", "definition": "TBD", "source": "camera envelope only", "status": "HOLD"},
    ]
    write_csv(INTERFACES / "COORDINATE_DATUM_TABLE.csv", list(datum_rows[0].keys()), datum_rows)


def package_readiness() -> tuple[list[Path], list[Path]]:
    required = [NEUTRAL_STEP, NEUTRAL_FCSTD, VISUAL_MESH, COLLISION_MESH, URDF]
    required.extend(sorted((URDF.parent / "meshes_b601_gripper").glob("*.STL")))
    required.extend(GRIPPER_R1_ASSETS)
    required.extend(sorted((V4 / "02_neutral_cad").rglob("*.step")))
    required.extend(
        [
            RAPID / "04_validation" / "GRIPPER_R1_GEOMETRY_VALIDATION.json",
            RAPID / "04_validation" / "GRIPPER_R1_NEUTRAL_REOPEN_VALIDATION.json",
            RAPID / "04_validation" / "GRIPPER_R1_CONTINUOUS_STROKE_SAMPLES.csv",
            RAPID / "04_validation" / "V5R_FALLBACK_B_NEUTRAL_FORMATION_RECEIPT.json",
        ]
    )
    interface_required = [
        INTERFACES / "B601_URDF_CAD_JOINT_MAP.csv",
        INTERFACES / "B601_FRAME_MAP.csv",
        INTERFACES / "SYSTEM_FRAME_TREE.yaml",
        INTERFACES / "CAD_URDF_MASS_COMPARISON.csv",
        INTERFACES / "CONFIGURATION_MATRIX.csv",
        INTERFACES / "INTERFERENCE_CLASSIFICATION.csv",
        INTERFACES / "MECH_RL_INTERFACE_V1.yaml",
    ]
    required.extend(interface_required)
    missing = [path for path in required if not path.is_file() or path.stat().st_size == 0]
    return required, missing


def generate_holds(gripper: dict, neutral_missing: list[Path]) -> None:
    holds = [
        ("H-001", "NATIVE_TOP_ASSEMBLY", "HOLD", "Loop1E bounded attempts exhausted; no validated final native top."),
        ("H-002", "LIGHTWEIGHT_SLDASM", "HOLD", "Byte-identical staging derivative exists but native/lightweight cold validation did not close."),
        ("H-003", "NEUTRAL_PACKAGE_ASSET_COMPLETENESS", "HOLD" if neutral_missing else "CLOSED", ";".join(rel(x) for x in neutral_missing) if neutral_missing else "All required neutral package inputs present and non-zero."),
        ("H-004", "GRIPPER_R1_CONTINUOUS_SWEEP", "CLOSED" if gripper["post_rows"] == 0 and gripper["positive_overlap_volume_mm3"] == 0 else "HOLD", gripper["status"]),
        ("H-005", "GRIPPER_MANUFACTURING_CLEARANCE", "HOLD", str(gripper["manufacturing_clearance"])),
        ("H-006", "GRIPPER_STRUCTURAL_STRENGTH", "HOLD", str(gripper["structural_strength"])),
        ("H-007", "M3R_MASS_RECONCILIATION", "HOLD", "Owner/legacy 761.904197 g conflicts with V5 CAD-density 782.327248 g."),
        ("H-008", "M3R_FASTENER_MOS_AND_PRELOAD", "HOLD", "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED"),
        ("H-009", "M3R_LOCATING_DOWEL_FIT", "HOLD", "TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED"),
        ("H-010", "CONFIGURATION_NATIVE_READBACK", "HOLD", "Neutral B-rep is a single geometry; configuration enum is semantic for sim13."),
        ("H-011", "PER_CONFIGURATION_BOUNDING_BOX", "HOLD", "No source-backed parametric readback for ten semantic configurations."),
        ("H-012", "PACKAGE_ADDENDA_EXTERNAL_INTERFERENCE", "HOLD", "Hash-identical main neutral retains its historical zero; V4/R1 addenda are not monolithically placed or narrow-phase validated, so composite scope is UNKNOWN and must fail closed."),
        ("H-013", "LAUNCH_STOWED_CONFIGURATION", "HOLD", "Historical envelope exceedance 132.72 mm; not repaired or qualified here."),
        ("H-014", "PARASOLID_EXPORT", "HOLD", "Not produced by fallback B neutral-copy route."),
        ("H-015", "CAMERA_SELECTION_AND_CALIBRATION", "HOLD", "Keep-out only; camera product/optical/hand-eye authority absent."),
        ("H-016", "HARNESS_MOVING_SWEEP", "HOLD", "Static OD9 keep-out exists; moving sweep not closed."),
        ("H-017", "HDRM_RELIABILITY", "HOLD", "No product selection or physical release reliability test."),
        ("H-018", "FLIGHT_STRUCTURE_QUALIFICATION", "HOLD", "No launch/vibration/thermal-vac qualification."),
        ("H-019", "REAL_ROBOTIC_EXECUTION", "HOLD", "sim13 authorization is scene bootstrap only."),
        ("H-020", "MONOLITHIC_NEUTRAL_INTEGRATION", "HOLD", "Main neutral STEP, 23 V4 delta STEP files, and gripper R1 are package-level composite assets, not a single updated assembly B-rep."),
    ]
    rows = [{"hold_id": x[0], "subject": x[1], "status": x[2], "basis": x[3]} for x in holds]
    write_csv(INTERFACES / "OPEN_HOLD_REGISTER.csv", list(rows[0].keys()), rows)


def generate_interface_yaml(links: list[dict], joints: list[dict], gripper: dict) -> None:
    total_mass = sum(item["mass_kg"] for item in links)
    frame_tree = INTERFACES / "SYSTEM_FRAME_TREE.yaml"
    config_matrix = INTERFACES / "CONFIGURATION_MATRIX.csv"
    production_artifacts_ready = all(
        path.is_file() and path.stat().st_size > 0
        for path in (URDF, VISUAL_MESH, COLLISION_MESH, frame_tree)
    )
    theta_half = math.radians(25.000014) / 2.0
    payload = {
        "schema": "MECH_RL_INTERFACE_V1",
        "schema_version": "MECH_RL_INTERFACE_V1",
        "format_version": "1.0",
        "asset_root": "../../..",
        "baseline_id": BASELINE_ID,
        "generated_utc": STAMP,
        "scope": "competition_prototype_onorbit_operational_mechanical_baseline",
        "gate_eligible": production_artifacts_ready,
        "owner_ruling": OWNER_RULING,
        "memory_gate_passed": False,
        "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY",
        "native_top_assembly_status": "HOLD",
        "neutral_operational_baseline_status": "PASS" if all(p.is_file() and p.stat().st_size > 0 for p in (NEUTRAL_STEP, NEUTRAL_FCSTD, VISUAL_MESH, COLLISION_MESH)) else "HOLD_ASSET_COPY_PENDING",
        "accepted_urdf": rel(URDF),
        "visual_mesh": rel(VISUAL_MESH),
        "collision_mesh": rel(COLLISION_MESH),
        "frame_tree": rel(frame_tree),
        "configuration_matrix": rel(config_matrix),
        "artifacts": {
            "accepted_urdf": {"path": rel(URDF), "sha256": sha256(URDF)},
            "visual_mesh": {"path": rel(VISUAL_MESH), "sha256": sha256(VISUAL_MESH)},
            "collision_mesh": {"path": rel(COLLISION_MESH), "sha256": sha256(COLLISION_MESH)},
            "frame_tree": {"path": rel(frame_tree), "sha256": sha256(frame_tree)},
        },
        "assets": {
            "accepted_urdf": {**asset_record(URDF, "ACCEPTED_URDF_AUTHORITY"), "link_count": len(links), "joint_count": len(joints), "mass_kg": total_mass},
            "neutral_baseline_step": asset_record(NEUTRAL_STEP, "NEUTRAL_GEOMETRY_AUTHORITY"),
            "neutral_baseline_fcstd": asset_record(NEUTRAL_FCSTD, "NEUTRAL_CONTAINER_COPY"),
            "visual_mesh": asset_record(VISUAL_MESH, "SIM13_VISUAL_MESH"),
            "collision_mesh": asset_record(COLLISION_MESH, "SIM13_COLLISION_MESH"),
            "frame_tree": asset_record(frame_tree, "FRAME_AUTHORITY"),
            "configuration_matrix": asset_record(config_matrix, "SEMANTIC_CONFIGURATION_ENUM"),
            "lightweight_sldasm": asset_record(LIGHTWEIGHT_SLDASM, "UNVALIDATED_CANDIDATE_HOLD"),
            "gripper_r1_palm_step": asset_record(GRIPPER_R1_ROOT / "B601_GRIPPER_PALM_RAIL_SLOT_R1.step", "NEUTRAL_R1_CORRECTION_ADDENDUM"),
            "gripper_r1_palm_mesh": asset_record(GRIPPER_R1_ROOT / "B601_GRIPPER_PALM_RAIL_SLOT_R1.stl", "NEUTRAL_R1_VISUAL_ADDENDUM"),
            "left_rail_full_stroke_sweep": asset_record(GRIPPER_R1_ROOT / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step", "NEUTRAL_R1_SWEEP_EVIDENCE"),
            "right_rail_full_stroke_sweep": asset_record(GRIPPER_R1_ROOT / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step", "NEUTRAL_R1_SWEEP_EVIDENCE"),
            "m3r_stage_a_step": asset_record(V4 / "02_neutral_cad" / "adapter" / "V4_B601_STAGE_A_INTERFACE_RING_REVB.step", "V4_DELTA_ADDENDUM"),
            "m3r_stage_b_step": asset_record(V4 / "02_neutral_cad" / "adapter" / "V4_B601_STAGE_B_LOAD_ADAPTER_REVB2.step", "V4_DELTA_ADDENDUM"),
            "v4_delta_step_count": len(list((V4 / "02_neutral_cad").rglob("*.step"))),
        },
        "composition": {
            "mode": "PACKAGE_LEVEL_COMPOSITE_NOT_MONOLITHICALLY_INTEGRATED",
            "main_neutral_contains_original_b51_arm_and_gripper": True,
            "main_neutral_contains_m3r_rev_b2": False,
            "main_neutral_contains_gripper_r1": False,
            "addenda": ["23_V4_DELTA_STEP_FILES", "GRIPPER_R1_PALM_AND_FULL_STROKE_SWEEPS"],
            "placement_and_narrow_phase_status": "HOLD_UNKNOWN",
            "sim13_disposition": "LOAD_HASH_BOUND_ARTIFACTS_AND_FAIL_CLOSED_ON_UNKNOWN",
        },
        "mass_and_inertia_authority": {
            "b601": "accepted_urdf_only",
            "mesh_inference_forbidden": True,
            "b601_mass_kg": total_mass,
            "m3r_owner_frozen_approx_mass_kg": 0.761904197,
            "m3r_v5_cad_density_provisional_mass_kg": 0.782327248,
            "m3r_mass_status": "M3R_MASS_RECONCILIATION_HOLD",
        },
        "kinematic_contract": {
            "links": [item["name"] for item in links],
            "joints": [item["name"] for item in joints],
            "joint_types": {item["name"]: item["type"] for item in joints},
            "topology": "10 links / 9 joints / 6R + 1 fixed + 2P",
            "gripper_prismatic_limit_m": [0.0, 0.0715],
        },
        "accepted_configurations": [name for name, _, _, _ in CONFIGS],
        "configuration_authority": "SEMANTIC_ENUM_FOR_SIM13;NATIVE_GEOMETRIC_READBACK_HOLD",
        "gripper_contact_frames": [
            {
                "id": "GC_LEFT_PROVISIONAL",
                "frame_id": "gripper_contact_left",
                "surface_normal": [0.0, 1.0, 0.0],
                "status": "PROVISIONAL_EXTERNAL_OBJECT_CONTACT_DATUM_HOLD",
            },
            {
                "id": "GC_RIGHT_PROVISIONAL",
                "frame_id": "gripper_contact_right",
                "surface_normal": [0.0, -1.0, 0.0],
                "status": "PROVISIONAL_EXTERNAL_OBJECT_CONTACT_DATUM_HOLD",
            },
        ],
        "capture_timing_ids": ["T_EARLY", "T_NOMINAL", "T_LATE"],
        "m3r_mount_transform": {
            "parent_frame": "M_FRAME",
            "child_frame": "B601_AS_BUILT_PATTERN_DATUM",
            "translation_m": [0.025155, 0.000015994151, -0.00008636607],
            "quaternion_xyzw": [math.sin(theta_half), 0.0, 0.0, math.cos(theta_half)],
            "status": "MEASURED_COMPETITION_DATUM_NOT_OEM_FLANGE",
        },
        "camera_reserve_frames": ["camera_optical_frame"],
        "keep_out": [
            {"id": "CAMERA_KEEP_OUT", "frame_id": "CAMERA_KEEP_OUT", "status": "CAMERA_SELECTION_HOLD"},
            {"id": "CABLE_KEEP_OUT", "frame_id": "CABLE_KEEP_OUT", "status": "MOVING_SWEEP_HOLD"},
            {"id": "ARM_HDRM_RELEASE_SWEEP_KEEP_OUT", "frame_id": "ARM_HDRM_RELEASE_SWEEP_KEEP_OUT", "status": "HDRM_RELIABILITY_HOLD"},
        ],
        "mass_and_inertia": {
            "authority": "accepted_urdf",
            "b601_total_mass_kg": total_mass,
            "mesh_mass_inference_forbidden": True,
        },
        "m3r_mount": {
            "architecture": "STAGE_A_RING_PLUS_STAGE_B_LOAD_DIFFUSION_PLATE_REV_B2",
            "arm_pattern": "4xM4-class at 64x64 mm square",
            "pcd_mm": 90.509641772,
            "clocking_deg": 25.000014,
            "continuous_mounting_face": False,
            "T_M_to_B601_as_built_pattern_datum": {
                "translation_xyz_mm": [25.155, 0.015994151, -0.08636607],
                "rotation_about_x_deg": 25.000014,
                "rotation_matrix": [[1.0, 0.0, 0.0], [0.0, 0.9063076848, -0.4226184837], [0.0, 0.4226184837, 0.9063076848]],
            },
            "cable_channel": "PRESENT_AS_INTERFACE_ENVELOPE;MOVING_SWEEP_HOLD",
            "tool_access": "SCHEMATIC_INTERFACE_EVIDENCE_ONLY;PHYSICAL_FITUP_HOLD",
        },
        "frames": {
            "root": "spacecraft_assembly_frame",
            "arm_base": "arm_base_frame",
            "gripper_contacts": ["gripper_contact_left", "gripper_contact_right"],
            "camera": {"name": "camera_optical_frame", "status": "HOLD_CAMERA_SELECTION_AND_CALIBRATION"},
            "keep_out": ["CAMERA_KEEP_OUT", "CABLE_KEEP_OUT", "ARM_HDRM_RELEASE_SWEEP_KEEP_OUT"],
        },
        "gripper": {
            "geometry_status": gripper["status"],
            "pose_induced_interference_rows": gripper["post_rows"],
            "positive_overlap_volume_mm3": gripper["positive_overlap_volume_mm3"],
            "native_v5_pose_induced_interference_rows": gripper["native_v5_remaining_count"],
            "native_v5_reintegration_status": gripper["native_v5_reintegration_status"],
            "removed_volume_mm3": gripper["removed_volume_mm3"],
            "estimated_mass_delta_g": gripper["estimated_mass_delta_g"],
            "minimum_remaining_wall_thickness_mm": gripper["minimum_remaining_wall_thickness_mm"],
            "minimum_remaining_wall_thickness_status": gripper["minimum_remaining_wall_thickness_status"],
            "manufacturing_clearance_status": gripper["manufacturing_clearance"],
            "structural_strength_status": gripper["structural_strength"],
            "unknown_is_action_masked": True,
        },
        "external_interference": {
            "main_neutral_hash_identical_v2_scope": {"DEPLOYED_NOMINAL": 0, "SERVICE": 0, "status": "PASS_HISTORICAL_SOURCE_ONLY"},
            "package_composite_addenda": {"count": "UNKNOWN", "status": "HOLD_NOT_MONOLITHICALLY_PLACED_OR_NARROW_PHASE_VALIDATED"},
            "unknown_fail_closed": True,
        },
        "targets": {
            "primary": {"mass_kg": 22.0, "tumble_deg_s": 0.5, "role": "SIM13_ANCHOR"},
            "secondary": {"mass_kg": 150.0, "tumble_deg_s": 3.0, "role": "SIM13_ANCHOR"},
        },
        "action_contract": {
            "high_level_only": True,
            "fields": ["grasp_candidate_id", "capture_timing_id", "strategy_id"],
            "strategy_id": ["S1", "S3a", "ABORT"],
            "direct_joint_torque_output_forbidden": True,
            "abort_always_available": True,
            "unknown_fail_closed": True,
        },
        "qualification_holds": [
            "NATIVE_TOP_ASSEMBLY_HOLD",
            "LAUNCH_STOWED_CONFIGURATION_HOLD",
            "FLIGHT_STRUCTURE_QUALIFICATION_HOLD",
            "FASTENER_MOS_HOLD",
            "HDRM_RELIABILITY_HOLD",
            "REAL_ROBOTIC_EXECUTION_HOLD",
        ],
        "next_stage": {"authorized": True, "scope": "SIM13_PHYSICS_GATED_EMBODIED_GRASPING_SCENE_BOOTSTRAP_ONLY"},
    }
    write_yaml(INTERFACES / "MECH_RL_INTERFACE_V1.yaml", payload)


def source_register() -> None:
    sources = [
        ("accepted_urdf", URDF, "READ_ONLY_DYNAMICS_AUTHORITY"),
        ("v2_neutral_step", V2 / "03_native_cad" / "F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step", "FALLBACK_B_SOURCE"),
        ("v2_neutral_fcstd", V2 / "03_native_cad" / "F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.FCStd", "FALLBACK_B_SOURCE"),
        ("v2_native_top", V2 / "03_native_cad" / "F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM", "FROZEN_SOURCE_NOT_MODIFIED"),
        ("v2_frame_mapping", V2 / "10_digital_thread" / "F3R2_FRAME_MAPPING.yaml", "FRAME_SOURCE"),
        ("v2_m3r_transform", V2 / "03_native_cad" / "M3_interface_authority" / "M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json", "M3R_TRANSFORM_SOURCE"),
        ("v4_delta_manifest", V4 / "10_validation" / "MFINAL_NEUTRAL_CAD_MANIFEST_SHA256.txt", "DELTA_SOURCE_REGISTER"),
        ("v4_stage_a", V4 / "02_neutral_cad" / "adapter" / "V4_B601_STAGE_A_INTERFACE_RING_REVB.step", "DELTA_GEOMETRY"),
        ("v4_stage_b", V4 / "02_neutral_cad" / "adapter" / "V4_B601_STAGE_B_LOAD_ADAPTER_REVB2.step", "DELTA_GEOMETRY"),
        ("v5_link_map", V5 / "09_digital_thread" / "V5_LINK_COMPONENT_MAPPING.csv", "MAPPING_SOURCE"),
        ("v5_mass_boundary", V5 / "09_digital_thread" / "V5_MASS_BOUNDARY.yaml", "MASS_BOUNDARY_SOURCE"),
        ("v5_bom", V5 / "08_bom" / "V5_NATIVE_BOM_SEED.csv", "CAD_COMPARISON_SOURCE"),
        ("v5_interference_register", V5 / "04_configurations" / "V5_LOOP1C1_INTERFERENCE_FINGERPRINT_REGISTER.csv", "INTERFERENCE_SOURCE"),
        ("v5_loop1c1_acceptance", V5 / "00_authority" / "V5_LOOP1C1_INTERFERENCE_FINGERPRINT_ACCEPTANCE.json", "OPTION_A_EXCEPTION_SOURCE"),
        ("fallback_lightweight_candidate", LIGHTWEIGHT_SLDASM, "UNVALIDATED_HOLD"),
        ("neutral_step", NEUTRAL_STEP, "DERIVED_FALLBACK_B"),
        ("neutral_fcstd", NEUTRAL_FCSTD, "DERIVED_FALLBACK_B"),
        ("visual_mesh", VISUAL_MESH, "DERIVED_FALLBACK_B"),
        ("collision_mesh", COLLISION_MESH, "DERIVED_FALLBACK_B"),
        ("fallback_b_receipt", RAPID / "04_validation" / "V5R_FALLBACK_B_NEUTRAL_FORMATION_RECEIPT.json", "FALLBACK_B_FORMATION_EVIDENCE"),
        ("gripper_r1_receipt", RAPID / "04_validation" / "GRIPPER_R1_GEOMETRY_VALIDATION.json", "NEUTRAL_R1_PASS_NATIVE_REINTEGRATION_HOLD"),
        ("gripper_r1_palm_step", GRIPPER_R1_ROOT / "B601_GRIPPER_PALM_RAIL_SLOT_R1.step", "PACKAGE_ADDENDUM"),
        ("gripper_r1_left_sweep_step", GRIPPER_R1_ROOT / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step", "PACKAGE_ADDENDUM"),
        ("gripper_r1_right_sweep_step", GRIPPER_R1_ROOT / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step", "PACKAGE_ADDENDUM"),
    ]
    rows = []
    for role, path, authority in sources:
        rec = asset_record(path)
        rows.append({"role": role, "path": rec["path"], "exists": rec["exists"], "size_bytes": rec["size_bytes"], "sha256": rec["sha256"], "authority_or_status": authority})
    write_csv(EVIDENCE / "SOURCE_EVIDENCE_REGISTER.csv", list(rows[0].keys()), rows)


def sheet_base(title: str, subtitle: str = "NEUTRAL / INTERFACE EVIDENCE — NOT A NATIVE CAD SCREENSHOT"):
    fig, ax = plt.subplots(figsize=(11.69, 8.27), dpi=150)
    fig.patch.set_facecolor("#f7f9fc")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 70)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((1, 1), 98, 68, fill=False, lw=1.4, ec="#1e3a5f"))
    ax.add_patch(Rectangle((1, 64), 98, 5, facecolor="#16324f", edgecolor="#16324f"))
    ax.text(3, 66.5, title, color="white", fontsize=15, fontweight="bold", va="center")
    ax.text(98, 66.5, "V5R • NEUTRAL", color="#9ed8ff", fontsize=10, ha="right", va="center", fontweight="bold")
    ax.add_patch(Rectangle((1, 1), 98, 4, facecolor="#eef4fa", edgecolor="#1e3a5f", lw=0.8))
    ax.text(3, 3.0, subtitle, color="#a2191f", fontsize=8.5, va="center", fontweight="bold")
    ax.text(98, 3.0, "Scope: on-orbit competition prototype • Flight/launch qualification HOLD", color="#36454f", fontsize=7, ha="right", va="center")
    return fig, ax


def save_sheet(fig, stem: Path, formats=("png", "svg", "pdf")) -> None:
    for ext in formats:
        fig.savefig(stem.with_suffix(f".{ext}"), bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def draw_spacecraft(ax, view="iso", panel=(True, True), arm="task", gripper="open") -> None:
    if view == "front":
        ax.add_patch(Rectangle((39, 23), 22, 27, facecolor="#dbe8f5", edgecolor="#24476b", lw=2))
        if panel[0]: ax.add_patch(Rectangle((10, 28), 27, 17, facecolor="#244a7c", edgecolor="#112b46"))
        if panel[1]: ax.add_patch(Rectangle((63, 28), 27, 17, facecolor="#244a7c", edgecolor="#112b46"))
    elif view == "side":
        ax.add_patch(Rectangle((36, 20), 28, 31, facecolor="#dbe8f5", edgecolor="#24476b", lw=2))
        if panel[0] or panel[1]: ax.add_patch(Rectangle((39, 53), 22, 5, facecolor="#244a7c", edgecolor="#112b46"))
    elif view == "top":
        ax.add_patch(Rectangle((38, 24), 24, 24, facecolor="#dbe8f5", edgecolor="#24476b", lw=2))
        if panel[0]: ax.add_patch(Rectangle((8, 28), 28, 16, facecolor="#244a7c", edgecolor="#112b46"))
        if panel[1]: ax.add_patch(Rectangle((64, 28), 28, 16, facecolor="#244a7c", edgecolor="#112b46"))
    else:
        bus = Polygon([(38, 21), (60, 25), (64, 47), (42, 51), (34, 44), (34, 26)], closed=True, facecolor="#dbe8f5", edgecolor="#24476b", lw=2)
        ax.add_patch(bus)
        if panel[0]: ax.add_patch(Polygon([(34, 30), (8, 23), (8, 40), (34, 44)], closed=True, facecolor="#244a7c", edgecolor="#112b46"))
        if panel[1]: ax.add_patch(Polygon([(62, 30), (91, 23), (91, 40), (64, 45)], closed=True, facecolor="#244a7c", edgecolor="#112b46"))
    if arm == "task":
        pts = [(52, 42), (59, 49), (68, 47), (75, 54), (82, 51)]
    else:
        pts = [(51, 42), (48, 48), (44, 46), (42, 41), (46, 38)]
    for p0, p1 in zip(pts, pts[1:]):
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="#e07a1f", lw=5, solid_capstyle="round")
        ax.add_patch(Circle(p0, 1.4, facecolor="#ffd28d", edgecolor="#874100"))
    ax.add_patch(Circle(pts[-1], 1.4, facecolor="#ffd28d", edgecolor="#874100"))
    gap = {"closed": 1.0, "pregrasp": 3.0, "open": 5.0}.get(gripper, 3.0)
    gx, gy = pts[-1]
    ax.plot([gx, gx + 3], [gy, gy + gap], color="#784f9e", lw=2.5)
    ax.plot([gx, gx + 3], [gy, gy - gap], color="#784f9e", lw=2.5)


def engineering_drawings(gripper: dict) -> list[dict]:
    index = []

    fig, ax = sheet_base("D01 — TOP-LEVEL NEUTRAL ASSEMBLY INTERFACE DRAWING")
    draw_spacecraft(ax, "iso")
    ax.text(5, 59, "12U BUS + bilateral arrays + B601 6R chain + M3R + gripper", fontsize=10, color="#1c334a")
    ax.text(5, 8, "Geometry source: Fallback-B neutral copy. Native top: HOLD. Diagram is schematic; no dimensional release.", fontsize=8)
    save_sheet(fig, DRAWINGS / "D01_TOP_LEVEL_NEUTRAL_ASSEMBLY")
    index.append({"drawing": "D01", "title": "Top-level neutral assembly", "status": "INTERFACE_EVIDENCE", "source": rel(NEUTRAL_STEP)})

    fig, ax = sheet_base("D02 — M3R TWO-STAGE INTERFACE ASSEMBLY")
    ax.add_patch(Circle((40, 36), 15, fill=False, lw=4, ec="#4b6f8f"))
    ax.add_patch(Circle((40, 36), 9, fill=False, lw=1.5, ec="#4b6f8f"))
    ax.add_patch(Rectangle((60, 22), 28, 28, fill=False, lw=3, ec="#457b4d"))
    for sx in (-1, 1):
        for sy in (-1, 1):
            ax.add_patch(Circle((40 + sx * 6.4, 36 + sy * 6.4), 0.7, color="#a2191f"))
            ax.add_patch(Circle((74 + sx * 7, 36 + sy * 7), 0.8, color="#a2191f"))
    ax.annotate("Stage A Ring", (40, 18), ha="center", fontsize=11, fontweight="bold")
    ax.annotate("Stage B Load Diffusion Plate", (74, 18), ha="center", fontsize=11, fontweight="bold")
    ax.annotate("load path", (56, 36), xytext=(51, 36), arrowprops=dict(arrowstyle="->", lw=2), va="center")
    ax.text(7, 9, "4×M4-class • 64×64 mm • PCD 90.509641772 mm • clock 25.000014° • continuous face=false", fontsize=9)
    ax.text(7, 7, "Mass: owner/legacy 761.904 g vs V5 CAD-density 782.327 g — RECONCILIATION HOLD", fontsize=8, color="#a2191f")
    save_sheet(fig, DRAWINGS / "D02_M3R_TWO_STAGE_INTERFACE_ASSEMBLY")
    index.append({"drawing": "D02", "title": "M3R two-stage interface assembly", "status": "INTERFACE_EVIDENCE_WITH_MASS_HOLD", "source": "M3R authority + V5 BOM"})

    fig, ax = sheet_base("D03 — M3R STAGE A RING INTERFACE")
    ax.add_patch(Circle((48, 35), 20, fill=False, lw=5, ec="#4b6f8f"))
    ax.add_patch(Circle((48, 35), 11, fill=False, lw=2, ec="#4b6f8f"))
    for sx in (-1, 1):
        for sy in (-1, 1): ax.add_patch(Circle((48 + sx * 6.4, 35 + sy * 6.4), 0.8, facecolor="#f7f9fc", edgecolor="#a2191f", lw=2))
    ax.plot([41.6, 54.4], [28.6, 28.6], color="#a2191f", lw=0.8)
    ax.text(70, 47, "ARM-SIDE PATTERN", fontsize=10, fontweight="bold")
    ax.text(70, 43, "4 × M4-class", fontsize=9)
    ax.text(70, 39, "64 × 64 mm square", fontsize=9)
    ax.text(70, 35, "PCD 90.509641772 mm", fontsize=9)
    ax.text(70, 31, "clocking 25.000014°", fontsize=9)
    ax.text(70, 27, "continuous face: FALSE", fontsize=9, color="#a2191f")
    ax.text(7, 8, "Material/tolerance/finish/torque: TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED", fontsize=8)
    save_sheet(fig, DRAWINGS / "D03_M3R_STAGE_A_RING_INTERFACE")
    index.append({"drawing": "D03", "title": "M3R Stage A ring", "status": "INTERFACE_EVIDENCE", "source": "V4/V5 Rev-B2 assets"})

    fig, ax = sheet_base("D04 — M3R STAGE B LOAD DIFFUSION PLATE")
    ax.add_patch(Rectangle((27, 15), 42, 42, fill=False, lw=4, ec="#457b4d"))
    ax.add_patch(Circle((48, 36), 12, fill=False, lw=2, ec="#457b4d"))
    for sx in (-1, 1):
        for sy in (-1, 1): ax.add_patch(Circle((48 + sx * 17.5, 36 + sy * 17.5), 0.8, facecolor="#f7f9fc", edgecolor="#a2191f", lw=2))
    for angle in range(0, 360, 45):
        ax.add_patch(Circle((48 + 15.6 * math.cos(math.radians(angle)), 36 + 15.6 * math.sin(math.radians(angle))), 0.55, facecolor="#f7f9fc", edgecolor="#2563a6"))
    ax.text(74, 46, "Rev-B2 role", fontsize=10, fontweight="bold")
    ax.text(74, 42, "load diffusion", fontsize=9)
    ax.text(74, 38, "cable passage", fontsize=9)
    ax.text(74, 34, "tool access: HOLD", fontsize=9, color="#a2191f")
    ax.text(7, 8, "Live mating load bridge, fastener stack, preload and MoS remain HOLD.", fontsize=8)
    save_sheet(fig, DRAWINGS / "D04_M3R_STAGE_B_LOAD_DIFFUSION_PLATE")
    index.append({"drawing": "D04", "title": "M3R Stage B plate", "status": "INTERFACE_EVIDENCE_WITH_FASTENER_HOLD", "source": "V4/V5 Rev-B2 assets"})

    fig, ax = sheet_base("D05 — B601 GRIPPER PALM RAIL-SLOT R1")
    ax.add_patch(Rectangle((28, 18), 44, 35, facecolor="#d8d4e8", edgecolor="#58427c", lw=3))
    ax.add_patch(Rectangle((34, 25), 32, 6, facecolor="#ffffff", edgecolor="#a2191f", lw=2, hatch="//"))
    ax.add_patch(Rectangle((34, 40), 32, 6, facecolor="#ffffff", edgecolor="#a2191f", lw=2, hatch="//"))
    ax.arrow(35, 28, 29, 0, width=0.3, head_width=1.8, head_length=2.5, color="#e07a1f", length_includes_head=True)
    ax.arrow(35, 43, 29, 0, width=0.3, head_width=1.8, head_length=2.5, color="#e07a1f", length_includes_head=True)
    ax.text(76, 48, "LEFT/RIGHT full stroke", fontsize=10, fontweight="bold")
    ax.text(76, 44, "0 → 71.5 mm URDF range", fontsize=8)
    ax.text(76, 40, f"neutral post rows: {gripper['post_rows']}", fontsize=8)
    ax.text(76, 36, f"neutral overlap mm³: {gripper['positive_overlap_volume_mm3']}", fontsize=8)
    ax.text(76, 32, f"removed mm³: {gripper['removed_volume_mm3']}", fontsize=8)
    ax.text(76, 28, f"estimated mass delta: {gripper['estimated_mass_delta_g']} g", fontsize=8)
    ax.text(76, 24, f"native V5 rows: {gripper['native_v5_remaining_count']} (HOLD)", fontsize=8, color="#a2191f")
    ax.text(7, 8, "Neutral R1 B-rep/sweeps validated separately. Main STEP still carries original gripper; native V5 reintegration, wall and strength HOLD.", fontsize=8)
    save_sheet(fig, DRAWINGS / "D05_GRIPPER_PALM_RAIL_SLOT_R1")
    index.append({"drawing": "D05", "title": "Gripper palm rail-slot R1", "status": gripper["status"], "source": gripper["receipt"] or "V5 interference register"})

    fig, ax = sheet_base("D06 — SOLAR ARRAY ROOT INSTALLATION INTERFACE")
    ax.add_patch(Rectangle((15, 20), 25, 30, facecolor="#dbe8f5", edgecolor="#24476b", lw=2))
    ax.add_patch(Rectangle((59, 24), 30, 22, facecolor="#244a7c", edgecolor="#112b46", lw=2))
    ax.add_patch(Circle((51, 35), 4, facecolor="#f0c36d", edgecolor="#7a4f00", lw=2))
    ax.plot([40, 47], [35, 35], color="#1f2933", lw=5)
    ax.plot([55, 59], [35, 35], color="#1f2933", lw=5)
    ax.arrow(51, 35, 0, 12, width=0.2, head_width=1.4, head_length=2, color="#a2191f")
    ax.text(55, 49, "hinge axis +X", fontsize=9, color="#a2191f")
    ax.text(7, 10, "Left point (-61, +143.15, 0) mm • Right point (-61, -143.15, 0) mm • load/fit/transport authority HOLD", fontsize=8)
    save_sheet(fig, DRAWINGS / "D06_SOLAR_ARRAY_ROOT_INSTALLATION")
    index.append({"drawing": "D06", "title": "Solar-array root installation", "status": "INTERFACE_EVIDENCE_WITH_LOAD_FIT_HOLD", "source": "V5 true-hinge assets + F3R2 frame map"})

    fig, ax = sheet_base("D07 — ACCEPTED SEMANTIC CONFIGURATION STATE MAP")
    y = 58
    for idx, (name, kind, summary, use) in enumerate(CONFIGS, 1):
        color = "#d8eef7" if idx % 2 else "#edf4e8"
        ax.add_patch(Rectangle((6, y - 3), 88, 4, facecolor=color, edgecolor="#b8c6d1", lw=0.5))
        ax.text(8, y - 1, f"{idx:02d}  {name}", fontsize=8.5, fontweight="bold", va="center")
        ax.text(45, y - 1, summary, fontsize=7.5, va="center")
        ax.text(92, y - 1, use, fontsize=6.8, va="center", ha="right")
        y -= 5
    ax.text(7, 8, "Accepted = sim13 semantic state enum. Native activation/rebuild/reopen and per-state bounding box remain HOLD.", fontsize=8, color="#a2191f")
    save_sheet(fig, DRAWINGS / "D07_CONFIGURATION_STATE_MAP")
    index.append({"drawing": "D07", "title": "Configuration state map", "status": "SEMANTIC_ENUM_NATIVE_READBACK_HOLD", "source": "Owner ruling + F3R2 configuration matrix"})

    fig, ax = sheet_base("D08 — B601 ARM SWEPT-ENVELOPE INTERFACE")
    ax.add_patch(Rectangle((10, 20), 25, 28, facecolor="#dbe8f5", edgecolor="#24476b", lw=2))
    ax.add_patch(Wedge((36, 35), 48, -50, 55, width=18, facecolor="#f8d7a5", alpha=0.6, edgecolor="#e07a1f", hatch="//"))
    for angle in (-40, 0, 45):
        x = 36 + 36 * math.cos(math.radians(angle)); y = 35 + 36 * math.sin(math.radians(angle))
        ax.plot([36, x], [35, y], color="#e07a1f", lw=2)
    ax.add_patch(Rectangle((22, 16), 18, 8, facecolor="#f3bbbb", edgecolor="#a2191f", alpha=0.8))
    ax.text(12, 17, "HDRM keep-out", fontsize=8)
    ax.text(60, 57, "schematic sweep only", fontsize=9, color="#a2191f")
    ax.text(7, 8, "Continuous self/system collision, flexible solar modes and launch restraint load envelope remain HOLD.", fontsize=8)
    save_sheet(fig, DRAWINGS / "D08_ARM_SWEPT_ENVELOPE")
    index.append({"drawing": "D08", "title": "Arm swept envelope", "status": "SCHEMATIC_INTERFACE_HOLD", "source": "URDF chain + V4 HDRM envelope"})

    fig, ax = sheet_base("D09 — CAMERA AND CABLE KEEP-OUT INTERFACE")
    ax.add_patch(Rectangle((15, 19), 38, 34, facecolor="#dbe8f5", edgecolor="#24476b", lw=2))
    ax.plot([53, 62, 72, 84], [37, 45, 42, 52], color="#e07a1f", lw=5)
    ax.add_patch(Wedge((84, 52), 20, 205, 255, facecolor="#a8d5ba", alpha=0.55, edgecolor="#2f6f44"))
    ax.plot([53, 58, 65, 75, 84], [34, 29, 31, 26, 30], color="#6d4c41", lw=5, alpha=0.8)
    ax.text(65, 18, "OD9 static harness envelope", fontsize=8, color="#6d4c41")
    ax.text(67, 58, "camera selection cone (provisional)", fontsize=8, color="#2f6f44")
    ax.text(7, 8, "Camera product, connector/clamp, moving harness sweep and optical/hand-eye calibration remain HOLD.", fontsize=8)
    save_sheet(fig, DRAWINGS / "D09_CAMERA_CABLE_KEEP_OUT")
    index.append({"drawing": "D09", "title": "Camera/cable keep-out", "status": "KEEP_OUT_ONLY_AUTHORITY_HOLD", "source": "V4/V5 envelopes"})

    write_csv(DRAWINGS / "DRAWING_INDEX.csv", ["drawing", "title", "status", "source"], index)
    return index


def evidence_visuals(gripper: dict, package_status: str) -> list[dict]:
    specs = [
        (1, "TOTAL ASSEMBLY — ISOMETRIC", "assembly_iso", "Fallback-B neutral baseline"),
        (2, "TOTAL ASSEMBLY — FRONT", "assembly_front", "Fallback-B neutral baseline"),
        (3, "TOTAL ASSEMBLY — SIDE", "assembly_side", "Fallback-B neutral baseline"),
        (4, "TOTAL ASSEMBLY — TOP", "assembly_top", "Fallback-B neutral baseline"),
        (5, "B601 INSTALLATION INTERFACE", "m3r_install", "M3R authority / frame mapping"),
        (6, "M3R STAGE A", "stage_a", "V4/V5 Rev-B2 delta"),
        (7, "M3R STAGE B", "stage_b", "V4/V5 Rev-B2 delta"),
        (8, "M3R TOOL ACCESS", "tool", "Interface schematic; physical fit-up HOLD"),
        (9, "M3R CABLE CHANNEL", "cable", "V4/V5 envelope authority"),
        (10, "DEPLOYED_NOMINAL", "config_deployed", "Neutral semantic configuration"),
        (11, "LEFT_PANEL_FAIL", "config_left_fail", "Neutral semantic configuration"),
        (12, "RIGHT_PANEL_FAIL", "config_right_fail", "Neutral semantic configuration"),
        (13, "BOTH_PANEL_FAIL", "config_both_fail", "Neutral semantic configuration"),
        (14, "ARM_STOWED_ONORBIT", "arm_stowed", "F3R2 frozen stow pose semantics"),
        (15, "ARM_TASK_READY", "arm_task", "Accepted URDF q=0 semantic anchor"),
        (16, "GRIPPER_CLOSED", "gripper_closed", "URDF prismatic=0 m"),
        (17, "GRIPPER_PREGRASP", "gripper_pregrasp", "Semantic position 0.047667 m"),
        (18, "GRIPPER_OPEN", "gripper_open", "URDF prismatic=0.0715 m"),
        (19, "GRIPPER FULL-STROKE SWEPT VOLUME", "gripper_sweep", gripper["receipt"] or "No R1 validation receipt — HOLD"),
        (20, "EXTERNAL INTERFERENCE CLASSIFICATION", "interference", "Main neutral historical class-3=0; composite addenda UNKNOWN/fail closed"),
        (21, "ENGINEERING DRAWINGS AND BOM", "documents", "Generated neutral interface evidence"),
        (22, "NEUTRAL PACKAGE INDEPENDENT REOPEN", "package", package_status),
    ]
    rows = []
    for number, title, kind, source in specs:
        fig, ax = sheet_base(f"E{number:02d} — {title}")
        if kind.startswith("assembly_"):
            draw_spacecraft(ax, kind.split("_")[1])
        elif kind.startswith("config_"):
            state = kind[7:]
            panels = {
                "deployed": (True, True),
                "left_fail": (False, True),
                "right_fail": (True, False),
                "both_fail": (False, False),
            }[state]
            draw_spacecraft(ax, "front", panels, "stowed" if state != "deployed" else "task")
            ax.text(50, 10, "SIM13 semantic state; native parametric activation HOLD", ha="center", fontsize=9, color="#a2191f")
        elif kind in ("arm_stowed", "arm_task"):
            draw_spacecraft(ax, "iso", (True, True), "stowed" if kind == "arm_stowed" else "task")
        elif kind.startswith("gripper_"):
            if kind == "gripper_sweep":
                ax.add_patch(Rectangle((25, 27), 50, 17, facecolor="#d8d4e8", edgecolor="#58427c", lw=3))
                ax.add_patch(Rectangle((30, 31), 40, 4, facecolor="#f8d7a5", edgecolor="#e07a1f", hatch="//"))
                ax.add_patch(Rectangle((30, 37), 40, 4, facecolor="#f8d7a5", edgecolor="#e07a1f", hatch="//"))
                ax.text(50, 50, gripper["status"], ha="center", fontsize=10, color="#a2191f")
            else:
                gap = {"gripper_closed": 2, "gripper_pregrasp": 12, "gripper_open": 20}[kind]
                ax.add_patch(Rectangle((37, 27), 26, 18, facecolor="#d8d4e8", edgecolor="#58427c", lw=3))
                ax.add_patch(Rectangle((18, 34 - gap / 4), 20, 4, facecolor="#e9c9ab", edgecolor="#784f3a"))
                ax.add_patch(Rectangle((62, 34 + gap / 4), 20, 4, facecolor="#e9c9ab", edgecolor="#784f3a"))
        elif kind in ("m3r_install", "stage_a", "stage_b", "tool", "cable"):
            ax.add_patch(Circle((42, 36), 16, fill=False, lw=4, ec="#4b6f8f"))
            ax.add_patch(Rectangle((62, 24), 27, 24, fill=False, lw=3, ec="#457b4d"))
            for sx in (-1, 1):
                for sy in (-1, 1): ax.add_patch(Circle((42 + sx * 6.4, 36 + sy * 6.4), 0.7, ec="#a2191f", fc="white"))
            if kind == "tool":
                for yy in (29, 43): ax.arrow(8, yy, 25, 0, width=0.3, head_width=1.5, head_length=2, color="#e07a1f")
                ax.text(10, 48, "TOOL ACCESS — PHYSICAL FIT-UP HOLD", fontsize=9, color="#a2191f")
            if kind == "cable":
                ax.plot([15, 30, 55, 72, 86], [20, 27, 22, 30, 20], color="#6d4c41", lw=5)
        elif kind == "interference":
            values = [81, 36, 0]
            labels = ["CLASS 1\nDONOR STATIC", "CLASS 2\nPRE-R1", "CLASS 3\nUNKNOWN"]
            colors = ["#6b8eaa", "#d98c3f", "#a2191f"]
            for x, value, label, color in zip((25, 50, 75), values, labels, colors):
                height = 38.0 * value / 81.0 if value else 3.0
                ax.add_patch(Rectangle((x - 7, 12), 14, height, facecolor=color if value else "none", edgecolor=color, lw=2, hatch=None if value else "xx"))
                ax.text(x, 12 + height + 2, str(value) if value else "UNKNOWN", ha="center", fontsize=9)
                ax.text(x, 8, label, ha="center", fontsize=8)
            ax.text(50, 58, f"Class-2 current: {gripper['post_rows']} rows / {gripper['positive_overlap_volume_mm3']} mm³", ha="center", fontsize=9, color="#a2191f")
            ax.text(50, 54.5, "Main neutral class-3=0 (historical hash-bound); composite addenda=UNKNOWN", ha="center", fontsize=7.5, color="#36454f")
        elif kind == "documents":
            for idx, name in enumerate(("DRAWING INDEX", "TOP-LEVEL BOM", "MASS TABLE", "FRAME MAP", "OPEN HOLDS")):
                x = 15 + idx * 16
                ax.add_patch(Rectangle((x, 24), 13, 27, facecolor="#ffffff", edgecolor="#24476b", lw=1.5))
                ax.text(x + 6.5, 37, name, ha="center", va="center", rotation=90, fontsize=8)
        elif kind == "package":
            color = "#2f6f44" if package_status == "PASS" else "#a2191f"
            ax.add_patch(Rectangle((18, 17), 64, 37, facecolor="#ffffff", edgecolor=color, lw=3))
            ax.text(50, 43, "V5R NEUTRAL PACKAGE", ha="center", fontsize=16, fontweight="bold")
            ax.text(50, 34, package_status, ha="center", fontsize=22, color=color, fontweight="bold")
            ax.text(50, 25, "STEP + FCStd + visual/collision STL + accepted URDF + 10 meshes + frame/interface files", ha="center", fontsize=8)
        ax.text(5, 59.5, f"Source: {source}", fontsize=8.5, color="#36454f")
        stem = VIS / f"E{number:02d}_{kind.upper()}_NEUTRAL_EVIDENCE"
        save_sheet(fig, stem, formats=("png",))
        rows.append(
            {
                "evidence_no": number,
                "title": title,
                "file": rel(stem.with_suffix(".png")),
                "classification": "NEUTRAL_INTERFACE_EVIDENCE_NOT_NATIVE_CAD_SCREENSHOT",
                "source": source,
                "status": package_status if number == 22 else (gripper["status"] if number == 19 else "EVIDENCE_ONLY"),
                "sha256": sha256(stem.with_suffix(".png")),
            }
        )
    write_csv(VIS / "SCREENSHOT_EVIDENCE_INDEX.csv", list(rows[0].keys()), rows)
    return rows


def copy_package() -> tuple[str, list[dict], list[str]]:
    package_map: list[tuple[Path, Path]] = [
        (NEUTRAL_STEP, PACKAGE / "cad" / NEUTRAL_STEP.name),
        (NEUTRAL_FCSTD, PACKAGE / "cad" / NEUTRAL_FCSTD.name),
        (VISUAL_MESH, PACKAGE / "mesh" / VISUAL_MESH.name),
        (COLLISION_MESH, PACKAGE / "mesh" / COLLISION_MESH.name),
        (URDF, PACKAGE / "urdf" / URDF.name),
    ]
    for mesh in sorted((URDF.parent / "meshes_b601_gripper").glob("*.STL")):
        package_map.append((mesh, PACKAGE / "urdf" / "meshes_b601_gripper" / mesh.name))
    for asset in GRIPPER_R1_ASSETS:
        package_map.append((asset, PACKAGE / "addenda" / "gripper_r1" / asset.name))
    v4_steps = sorted((V4 / "02_neutral_cad").rglob("*.step"))
    for asset in v4_steps:
        package_map.append((asset, PACKAGE / "addenda" / "v4_delta" / asset.relative_to(V4 / "02_neutral_cad")))
    for asset in (
        RAPID / "04_validation" / "GRIPPER_R1_GEOMETRY_VALIDATION.json",
        RAPID / "04_validation" / "GRIPPER_R1_NEUTRAL_REOPEN_VALIDATION.json",
        RAPID / "04_validation" / "GRIPPER_R1_CONTINUOUS_STROKE_SAMPLES.csv",
        RAPID / "04_validation" / "V5R_FALLBACK_B_NEUTRAL_FORMATION_RECEIPT.json",
        V4 / "10_validation" / "MFINAL_NEUTRAL_CAD_MANIFEST_SHA256.txt",
    ):
        package_map.append((asset, PACKAGE / "evidence" / asset.name))
    for name in (
        "B601_URDF_CAD_JOINT_MAP.csv",
        "B601_FRAME_MAP.csv",
        "SYSTEM_FRAME_TREE.yaml",
        "CAD_URDF_MASS_COMPARISON.csv",
        "CONFIGURATION_MATRIX.csv",
        "INTERFERENCE_CLASSIFICATION.csv",
        "MECH_RL_INTERFACE_V1.yaml",
        "TOP_LEVEL_BOM.csv",
        "MASS_PROPERTIES_TABLE.csv",
        "COORDINATE_DATUM_TABLE.csv",
        "OPEN_HOLD_REGISTER.csv",
    ):
        package_map.append((INTERFACES / name, PACKAGE / "interface" / name))
    missing = [rel(src) for src, _ in package_map if not src.is_file() or src.stat().st_size == 0]
    for src, dst in package_map:
        if src.is_file() and src.stat().st_size > 0:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    start_here = PACKAGE / "PACKAGE_START_HERE.md"
    start_here.write_text(
        "# V5R Neutral Operational Package\n\n"
        "This is a neutral/interface package for competition-prototype on-orbit simulation. "
        "It is not a native CAD, manufacturing, launch, or flight release.\n\n"
        "## Composition boundary\n\n"
        "This is a **package-level composite**, not one monolithically updated STEP assembly. The main STEP/FCStd is the "
        "byte-identical F3R2/V2 neutral baseline and still contains the original B51 arm/gripper. The 23 V4 delta STEP files "
        "(including M3R Stage A/Stage B, wing-root/support and keep-out geometry) and the gripper R1 palm/full-stroke sweeps "
        "are separately hash-bound addenda. Their system placement and composite narrow-phase interference remain HOLD/UNKNOWN.\n\n"
        "- Dynamics mass/inertia authority: `urdf/arm_b601_v1.urdf` only.\n"
        "- Visual/collision STL shall not be used to infer mass.\n"
        "- Configuration entries are semantic sim13 enums; native rebuild/readback remains HOLD.\n"
        "- Main-neutral historical external-interference zero does not propagate to the separately packaged addenda.\n"
        "- `ABORT` must remain available and all UNKNOWN safety inputs must fail closed.\n",
        encoding="utf-8",
        newline="\n",
    )
    # Make the packaged interface independently loadable: from package/interface
    # the package root is '..', and all strict artifacts are package-local.
    package_interface = PACKAGE / "interface" / "MECH_RL_INTERFACE_V1.yaml"
    package_document = yaml.safe_load((INTERFACES / "MECH_RL_INTERFACE_V1.yaml").read_text(encoding="utf-8"))
    package_document["asset_root"] = ".."
    package_document["package_local_binding"] = True
    package_document["artifacts"] = {
        "accepted_urdf": {"path": f"urdf/{URDF.name}", "sha256": sha256(PACKAGE / "urdf" / URDF.name)},
        "visual_mesh": {"path": f"mesh/{VISUAL_MESH.name}", "sha256": sha256(PACKAGE / "mesh" / VISUAL_MESH.name)},
        "collision_mesh": {"path": f"mesh/{COLLISION_MESH.name}", "sha256": sha256(PACKAGE / "mesh" / COLLISION_MESH.name)},
        "frame_tree": {"path": "interface/SYSTEM_FRAME_TREE.yaml", "sha256": sha256(PACKAGE / "interface" / "SYSTEM_FRAME_TREE.yaml")},
    }
    write_yaml(package_interface, package_document)

    expected_package_files = {dst.resolve() for _, dst in package_map}
    expected_package_files.add(start_here.resolve())
    actual_package_files = {path.resolve() for path in PACKAGE.rglob("*") if path.is_file()}
    extra_package_files = sorted(path.relative_to(PACKAGE.resolve()).as_posix() for path in actual_package_files - expected_package_files)
    copy_hash_mismatches = []
    destination_missing = []
    for src, dst in package_map:
        if not dst.is_file() or dst.stat().st_size <= 0:
            destination_missing.append(dst.relative_to(PACKAGE).as_posix())
        elif dst.resolve() != package_interface.resolve() and src.is_file() and sha256(src) != sha256(dst):
            copy_hash_mismatches.append(dst.relative_to(PACKAGE).as_posix())

    strict_loader_status = "HOLD_LOADER_NOT_AVAILABLE"
    strict_loader_error = None
    try:
        sim_src = PROJECT / "30_simulation" / "sim_13_physics_gated_embodied_grasping" / "src"
        if str(sim_src) not in sys.path:
            sys.path.insert(0, str(sim_src))
        from mechanical_asset_loader import load_mechanical_assets

        bundle = load_mechanical_assets(package_interface)
        strict_loader_status = "PASS"
        strict_loader_summary = {
            "manifest_sha256": bundle.manifest_sha256.upper(),
            "urdf_link_count": len(bundle.urdf.link_names),
            "urdf_joint_count": len(bundle.urdf.joint_names),
            "urdf_mass_kg": bundle.urdf.total_mass_kg,
            "frame_count": len(bundle.frame_tree.frame_ids),
            "accepted_configuration_count": len(bundle.accepted_configurations),
        }
    except Exception as exc:
        strict_loader_summary = None
        strict_loader_error = f"{type(exc).__name__}: {exc}"

    manifest_rows = []
    for path in sorted(p for p in PACKAGE.rglob("*") if p.is_file()):
        manifest_rows.append({"package_relative_path": path.relative_to(PACKAGE).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    write_csv(PACK_ROOT / "NEUTRAL_PACKAGE_MANIFEST_SHA256.csv", ["package_relative_path", "size_bytes", "sha256"], manifest_rows)
    status = (
        "PASS"
        if not missing and not destination_missing and not copy_hash_mismatches and not extra_package_files and strict_loader_status == "PASS"
        else ("HOLD_MISSING_ASSETS" if missing or destination_missing else "HOLD_PACKAGE_INTEGRITY_OR_LOADER_FAIL")
    )
    validation = {
        "schema": "V5R_NEUTRAL_PACKAGE_VALIDATION_V1",
        "generated_utc": STAMP,
        "status": status,
        "package_root": rel(PACKAGE),
        "required_asset_count": len(package_map),
        "missing_asset_count": len(missing),
        "missing_assets": missing,
        "destination_missing_count": len(destination_missing),
        "destination_missing_assets": destination_missing,
        "copy_hash_mismatch_count": len(copy_hash_mismatches),
        "copy_hash_mismatches": copy_hash_mismatches,
        "extra_asset_count": len(extra_package_files),
        "extra_assets": extra_package_files,
        "manifest_file_count": len(manifest_rows),
        "v4_delta_step_count": len(v4_steps),
        "gripper_r1_asset_count": len(GRIPPER_R1_ASSETS),
        "all_packaged_files_nonzero": all(row["size_bytes"] > 0 for row in manifest_rows),
        "accepted_urdf_source_sha256": sha256(URDF),
        "packaged_urdf_sha256": sha256(PACKAGE / "urdf" / URDF.name),
        "accepted_urdf_byte_identical": sha256(URDF) == sha256(PACKAGE / "urdf" / URDF.name),
        "step_mesh_frame_urdf_mapping_complete": status == "PASS",
        "strict_sim13_loader_status": strict_loader_status,
        "strict_sim13_loader_summary": strict_loader_summary,
        "strict_sim13_loader_error": strict_loader_error,
        "independent_package_interface_reopen": strict_loader_status,
        "neutral_cad_geometry_cold_reopen": "SOURCE_SCOPE_ONLY_SEE_FALLBACK_B_AND_GRIPPER_R1_REOPEN_RECEIPTS",
        "composition": "PACKAGE_LEVEL_COMPOSITE_NOT_MONOLITHICALLY_INTEGRATED",
        "composite_narrow_phase_interference": "HOLD_UNKNOWN",
        "native_top_assembly": "HOLD",
        "memory_gate_passed": False,
        "owner_override_used": True,
    }
    write_json(PACK_ROOT / "NEUTRAL_PACKAGE_VALIDATION.json", validation)
    return status, manifest_rows, missing


def readme_files(gripper: dict) -> None:
    (INTERFACES / "README_PHASE_G_H.md").write_text(
        "# V5R Phase G/H digital thread\n\n"
        "These files close the neutral mechanical-to-sim13 interface only. They do not assert a validated native top assembly, "
        "manufacturing release, launch-stowed qualification, fastener MoS, HDRM reliability, or flight qualification.\n\n"
        "The ten configuration names are accepted semantic state enums for deterministic scene bootstrap. The single neutral "
        "B-rep does not provide native per-configuration mate/suppression, bounding-box, rebuild, or reopen evidence; those fields remain HOLD.\n\n"
        f"Current gripper status: `{gripper['status']}`.\n\n"
        "The M3R mass sources conflict and are kept separate: owner/legacy 761.904197 g versus V5 CAD-density 782.327248 g. "
        "This is `M3R_MASS_RECONCILIATION_HOLD`.\n",
        encoding="utf-8",
        newline="\n",
    )
    (DRAWINGS / "README_DRAWINGS.md").write_text(
        "# Neutral interface drawings\n\n"
        "Every D01–D09 page is a schematic engineering/interface evidence sheet generated from frozen source facts. "
        "No page is a native CAD drawing or SolidWorks screenshot. Missing material, tolerance, finish and torque authority is explicitly HOLD/TBD.\n",
        encoding="utf-8",
        newline="\n",
    )
    (VIS / "README_22_EVIDENCE_IMAGES.md").write_text(
        "# 22 neutral evidence images\n\n"
        "E01–E22 satisfy the requested review viewpoints as neutral/interface evidence. They are deliberately watermarked "
        "`NEUTRAL / INTERFACE EVIDENCE — NOT A NATIVE CAD SCREENSHOT`; they must not be cited as SolidWorks render or native cold-reopen proof.\n",
        encoding="utf-8",
        newline="\n",
    )


def final_receipt(gripper: dict, package_status: str, package_missing: list[str], drawing_count: int, visual_count: int) -> None:
    scoped_dirs = [INTERFACES, DRAWINGS, VIS, PACK_ROOT]
    outputs = []
    for root in scoped_dirs:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            outputs.append({"path": rel(path), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    receipt = {
        "schema": "V5R_PHASE_G_H_AUDIT_RECEIPT_V1",
        "generated_utc": STAMP,
        "baseline_id": BASELINE_ID,
        "execution_mode": "STATIC_FILESYSTEM_AUDIT_AND_NEUTRAL_INTERFACE_GENERATION",
        "solidworks_connected_or_started": False,
        "donor_modified": False,
        "accepted_urdf_modified": False,
        "accepted_urdf_sha256": sha256(URDF),
        "memory_gate_passed": False,
        "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY",
        "owner_override_used": True,
        "native_top_assembly_status": "HOLD",
        "neutral_package_status": package_status,
        "neutral_package_missing_asset_count": len(package_missing),
        "neutral_package_missing_assets": package_missing,
        "gripper_status": gripper,
        "m3r_mass_status": "M3R_MASS_RECONCILIATION_HOLD",
        "configuration_status": "10_SEMANTIC_ENUMS_ACCEPTED_NATIVE_GEOMETRIC_READBACK_HOLD",
        "system_external_interference": "MAIN_NEUTRAL_HISTORICAL_ZERO;PACKAGE_COMPOSITE_ADDENDA_HOLD_UNKNOWN",
        "drawing_sheet_count": drawing_count,
        "evidence_image_count": visual_count,
        "drawings_are_native_cad": False,
        "evidence_images_are_native_cad_screenshots": False,
        "next_stage_interface": "SIM13_SCENE_BOOTSTRAP_ONLY",
        "hard_stop_triggered": False,
        "output_file_count_excluding_this_receipt": len(outputs),
        "outputs": outputs,
    }
    write_json(EVIDENCE / "PHASE_G_H_AUDIT_RECEIPT.json", receipt)


def main() -> int:
    ensure_dirs()
    links, joints = parse_urdf()
    gripper = gripper_truth()
    generate_joint_and_frame_files(links, joints)
    generate_mass_files(links, gripper)
    generate_configuration_and_interference(gripper)
    generate_bom_and_datums(gripper)
    generate_interface_yaml(links, joints, gripper)
    _, preliminary_missing = package_readiness()
    generate_holds(gripper, preliminary_missing)
    # Regenerate the interface YAML after HOLD files exist so the package copies a complete interface set.
    generate_interface_yaml(links, joints, gripper)
    source_register()
    readme_files(gripper)
    drawings = engineering_drawings(gripper)
    package_status, _, package_missing = copy_package()
    visuals = evidence_visuals(gripper, package_status)
    final_receipt(gripper, package_status, package_missing, len(drawings), len(visuals))
    print(
        json.dumps(
            {
                "status": "PHASE_G_H_FILES_GENERATED",
                "neutral_package_status": package_status,
                "missing_assets": package_missing,
                "drawing_count": len(drawings),
                "evidence_image_count": len(visuals),
                "gripper_status": gripper["status"],
                "accepted_urdf_sha256": sha256(URDF),
            },
            indent=2,
        )
    )
    return 0 if package_status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
