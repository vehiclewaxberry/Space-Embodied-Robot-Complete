from __future__ import annotations

import csv
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import yaml


CANDIDATE = Path(__file__).resolve().parents[1]
CLOSURE = CANDIDATE / "09_DELIVERY" / "B51R1_AUTONOMOUS_G1A_CLOSURE_20260801"
AUTONOMOUS_INTAKE = (
    CANDIDATE
    / "00_BASELINE"
    / "AUTHORIZATION_PACKAGE"
    / "B51R1_AUTONOMOUS_LOOP_MULTIAGENT_ENGINEERING_PACKAGE_INTAKE_20260801"
)
AUTONOMOUS_CONTENTS = (
    AUTONOMOUS_INTAKE
    / "CONTENTS"
    / "B51R1_AUTONOMOUS_LOOP_MULTIAGENT_ENGINEERING_PACKAGE"
)
S00_WORKSET = (
    CANDIDATE
    / "09_DELIVERY"
    / "B51R1_PHASE2_S00_G1_REVIEW_WORKSET_20260801"
)
PHASE2A_PACKAGE = (
    CANDIDATE
    / "09_DELIVERY"
    / "B51R1_PHASE2A_NATIVE_SKELETON_CARRIER_START_PACKAGE_20260801"
)

USER_DIRECTIVE = (
    "现在一次性站立委托 + 分级自治 + 多 Agent 法定人数裁决 + Gate 自动续跑 + "
    "不可委托边界保留，使用这个构建航天器空间具身智能机械臂机械设计具体方案内容"
)
USER_DIRECTIVE_SHA = "BAF77DD06C7918E63BA8BCACAB06C51AD8BC143E24CA1671C082699CB5FE60A8"
CHARTER_REL = (
    "00_BASELINE/AUTHORIZATION_PACKAGE/"
    "B51R1_AUTONOMOUS_LOOP_MULTIAGENT_ENGINEERING_PACKAGE_INTAKE_20260801/"
    "CONTENTS/B51R1_AUTONOMOUS_LOOP_MULTIAGENT_ENGINEERING_PACKAGE/"
    "B51R1_AUTONOMOUS_ENGINEERING_CHARTER.yaml"
)
CHARTER_SHA = "142FE0800F1D10D75E32DFD7BF58BECEE25E0C86A67FB782CF8D333942099BC3"
AUTONOMOUS_ZIP_SHA = "5410CB71C72B20679D1E4E026F18CCCDD0AF02638842CDE0FBAC903DBE013242"
URDF_SHA = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
STAGE_A_SHA = "5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B"
LOCK_SHA = "0D477825E5F9D305044B3EADCCAFFB403858E766BDC2E4BBD94A728DA79A4F47"


def now() -> str:
    return datetime.now().astimezone().isoformat()


def rel(path: Path) -> str:
    return path.resolve().relative_to(CANDIDATE.resolve()).as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def file_record(path: Path, role: str, mode: str = "READ_ONLY_HASH_GUARD") -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": rel(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "role": role,
        "mode": mode,
    }


def write_text(path: Path, text: str, *, newline: bool = True) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = text + ("\n" if newline and not text.endswith("\n") else "")
    path.write_text(payload, encoding="utf-8", newline="\n")


def write_json(path: Path, data: dict | list) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def write_yaml(path: Path, data: dict | list) -> None:
    write_text(
        path,
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120),
        newline=False,
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def assert_source(path: Path, expected_sha: str | None = None, expected_bytes: int | None = None) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if expected_bytes is not None and path.stat().st_size != expected_bytes:
        raise RuntimeError(f"Byte mismatch: {path}")
    if expected_sha is not None and sha256(path) != expected_sha:
        raise RuntimeError(f"SHA mismatch: {path}")


if CLOSURE.exists():
    raise FileExistsError(f"Closure workset already exists: {CLOSURE}")

charter_path = CANDIDATE / CHARTER_REL
assert_source(charter_path, CHARTER_SHA, 4953)
assert hashlib.sha256(USER_DIRECTIVE.encode("utf-8")).hexdigest().upper() == USER_DIRECTIVE_SHA
assert len(USER_DIRECTIVE.encode("utf-8")) == 207

autonomous_zip = AUTONOMOUS_INTAKE / "ARCHIVE" / "B51R1_AUTONOMOUS_LOOP_MULTIAGENT_ENGINEERING_PACKAGE.zip"
assert_source(autonomous_zip, AUTONOMOUS_ZIP_SHA, 11250)
urdf = CANDIDATE / "00_BASELINE" / "AUTHORITIES" / "accepted_urdf" / "arm_b601_v1.urdf"
stage_a = CANDIDATE / "02_MASTER_SKELETON" / "B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT"
quarantine_lock = (
    CANDIDATE
    / "00_BASELINE"
    / "QUARANTINE"
    / "STAGE_A_STALE_LOCKFILES"
    / "20260801"
    / "~$B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY__SHA_0D477825E5F9.SLDPRT"
)
original_lock = CANDIDATE / "02_MASTER_SKELETON" / "~$B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT"
assert_source(urdf, URDF_SHA, 11321)
assert_source(stage_a, STAGE_A_SHA, 511198)
assert not original_lock.exists()
assert_source(quarantine_lock, LOCK_SHA, 6)

CLOSURE.mkdir(parents=True)

directive_path = CLOSURE / "B51R1_OWNER_STANDING_DELEGATION_DIRECTIVE.txt"
write_text(directive_path, USER_DIRECTIVE, newline=False)
activation_receipt_path = CLOSURE / "B51R1_AUTONOMOUS_STANDING_DELEGATION_RECEIPT.json"
activation_receipt = {
    "schema": "B51R1_AUTONOMOUS_STANDING_DELEGATION_RECEIPT_V1",
    "generated_at": now(),
    "status": "PASS_OWNER_STANDING_DELEGATION_EFFECTIVE",
    "authority_type": "OWNER_STANDING_DELEGATION",
    "human_signature_present": False,
    "directive": {
        "path": rel(directive_path),
        "utf8_bytes": 207,
        "sha256": USER_DIRECTIVE_SHA,
        "exact_text": USER_DIRECTIVE,
    },
    "delegation_charter": file_record(charter_path, "STANDING_DELEGATION_CHARTER"),
    "source_package": file_record(autonomous_zip, "AUTONOMOUS_LOOP_MULTIAGENT_PACKAGE"),
    "delegated_root": str(CANDIDATE),
    "delegated_levels": ["L0", "L1", "L2", "L3"],
    "non_delegable_level": "L4",
    "non_delegable_boundaries": [
        "MODIFY_OR_OVERWRITE_V2_2_B5_0_B5_1_OR_STAGE_A_PROTECTED_FILES",
        "MODIFY_ACCEPTED_URDF_OR_VENDOR_STEP",
        "CHANGE_ACCEPTED_TOPOLOGY_MASS_OR_INERTIA_AUTHORITY",
        "ACTUATE_REAL_HARDWARE_OR_ISSUE_ROBOT_COMMANDS",
        "PROCURE_COMPONENTS_OR_RELEASE_PURCHASE_ORDERS",
        "PUBLISH_MANUFACTURING_READY_LAUNCH_QUALIFIED_OR_FLIGHT_READY",
        "RELAX_FINAL_ACCEPTANCE_GATES_OR_OVERWRITE_NEGATIVE_RESULTS",
        "FINAL_H9_DOWNSELECT_WITHOUT_AUTHORITATIVE_LAUNCHER_OR_DEPLOYER_ICD",
        "SIGN_PUBLIC_OR_EXTERNAL_RELEASE",
    ],
    "visible_session_pool": {"budget": 20, "concurrent_processes_max": 1},
    "claim_limit": "STANDING_DELEGATION_ACTIVATED_NO_GATE_PASS_INFERRED",
}
write_json(activation_receipt_path, activation_receipt)
activation_sha = sha256(activation_receipt_path)

authority_common = {
    "authority_type": "OWNER_STANDING_DELEGATION",
    "delegation_charter_path": CHARTER_REL,
    "delegation_charter_sha256": CHARTER_SHA,
    "activation_receipt_path": rel(activation_receipt_path),
    "activation_receipt_sha256": activation_sha,
    "human_signature_present": False,
}

datum_path = CLOSURE / "B51R1_G1A_DATUM_MACHINE_RATIFICATION.yaml"
datum = {
    "schema": "B51R1_G1A_DATUM_MACHINE_RATIFICATION_V1",
    "generated_at": now(),
    "status": "PASS_OWNER_STANDING_DELEGATION_MACHINE_RATIFIED",
    "gate": "G1A",
    **authority_common,
    "controlling_contract": file_record(
        CANDIDATE / "02_MASTER_SKELETON" / "B51R1_MASTER_SKELETON_V2_DATUM_REGISTER.yaml",
        "DATUM_CONTRACT_EVIDENCE",
    ),
    "ratified_semantics": {
        "longeron_center_axis_abs_yz_mm": 101.65,
        "primary_load_bearing_surface_abs_yz_mm": 110.15,
        "removable_panel_outer_surface_abs_yz_mm": 113.15,
        "signed_instance_rule": "APPLY_PLUS_AND_MINUS_TO_Y_AND_Z_PER_CONTROLLING_DATUM_REGISTER",
        "historical_105_65_mm": {
            "semantic": "HISTORICAL_SEMANTIC_UNRESOLVED",
            "preserve_source_unchanged": True,
            "may_drive_native_geometry": False,
            "may_receive_load_path_credit": False,
        },
    },
    "s01_semantic_guards": {
        "primary_110_15": "STRUCTURAL_REFERENCE_SURFACE_NOT_ATTACHMENT_BY_ITSELF",
        "panel_113_15": "ENVELOPE_AND_FOOTPRINT_LAYER_ONLY",
        "panel_load_credit": "NONE",
        "panel_attachment_credit": "NONE",
        "panel_contact_credit": "NONE_UNTIL_LATER_CONTACT_MODEL",
        "keepouts": "TBD_HOLD_PLACEHOLDERS_ONLY",
        "legacy_4mm_translation_repair": "PROHIBITED",
        "generic_3mm_shim_inference": "PROHIBITED",
    },
    "claim_limit": "G1A_DATUM_AUTHORITY_FOR_ISOLATED_CANDIDATE_NO_PHYSICAL_INTERFACE_OR_LOAD_CREDIT",
}
write_yaml(datum_path, datum)

joint_order = [
    "joint1", "joint2", "joint3", "joint4", "joint5", "joint6",
    "gripper_joint", "gripper_joint1", "gripper_joint2",
]
link_order = [
    "base_link", "link1", "link2", "link3", "link4", "link5", "link6",
    "gripper_link", "gripper_left", "gripper_right",
]

old_mapping_path = CANDIDATE / "04_CONFIGURATION" / "B51R1_URDF_CARRIER_FRAME_MAPPING.yaml"
old_mapping = read_yaml(old_mapping_path)
joint_by_name = {row["joint_name"]: row for row in old_mapping["joint_frame_authority"]}
carrier_by_link = {row["accepted_link_name"]: row for row in old_mapping["carrier_frame_mapping"]}

carrier_map_v2_path = CANDIDATE / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_CARRIER_MAP_V2.csv"
carrier_register_v2_path = CANDIDATE / "04_CONFIGURATION" / "B51R1_CARRIER_REGISTER_V2.csv"
mapping_v2_path = CANDIDATE / "04_CONFIGURATION" / "B51R1_URDF_CARRIER_FRAME_MAPPING_V2.yaml"
joint_register_v2_path = CANDIDATE / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_NATIVE_JOINT_REGISTER_V2.csv"
driver_v2_path = CANDIDATE / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_NATIVE_DRIVER_MAPPING_V2.csv"
architecture_v2_path = CANDIDATE / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_CARRIER_ARCHITECTURE_CONTRACT_V2.md"
transform_register_path = CANDIDATE / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_JOINT_SIDE_FRAME_TRANSFORM_REGISTER_V2.csv"
session_plan_v2_path = CANDIDATE / "04_CONFIGURATION" / "B51R1_AUTONOMOUS_SESSION_PLAN_V2.yaml"
gate_map_v2_path = CANDIDATE / "04_CONFIGURATION" / "B51R1_AUTONOMOUS_GATE_TRANSITION_MAP_V2.csv"
design_dir = CANDIDATE / "03_CAD" / "00_SYSTEM_ARCHITECTURE"
design_yaml_path = design_dir / "B51R1_SPACE_EMBODIED_ARM_MECHANICAL_DESIGN_BASELINE_V1.yaml"
design_md_path = design_dir / "B51R1_SPACE_EMBODIED_ARM_MECHANICAL_DESIGN_BASELINE_V1.md"

for planned in [
    carrier_map_v2_path, carrier_register_v2_path, mapping_v2_path,
    joint_register_v2_path, driver_v2_path, architecture_v2_path,
    transform_register_path, session_plan_v2_path, gate_map_v2_path,
    design_yaml_path, design_md_path,
]:
    if planned.exists():
        raise FileExistsError(f"Refusing overwrite of operational V2 asset: {planned}")

parent_for = {name: joint_by_name[name]["parent_link"] for name in joint_order}
child_for = {name: joint_by_name[name]["child_link"] for name in joint_order}
carrier_id_for = {link: carrier_by_link[link]["carrier_id"] for link in link_order}

def parent_frame(joint: str) -> str:
    return f"CS_JOINT_{joint}_PARENT_SIDE"


def child_frame(joint: str) -> str:
    return f"CS_JOINT_{joint}_CHILD_SIDE"


outgoing_by_link: dict[str, list[str]] = {link: [] for link in link_order}
incoming_by_link: dict[str, str | None] = {link: None for link in link_order}
for joint in joint_order:
    outgoing_by_link[parent_for[joint]].append(joint)
    incoming_by_link[child_for[joint]] = joint

transform_rows = []
joint_rows_v2 = []
driver_rows_v2 = []
for joint in joint_order:
    src = joint_by_name[joint]
    jtype = src["joint_type"]
    xyz = str(src["origin_xyz_m"])
    rpy = str(src["origin_rpy_rad"])
    axis = str(src.get("axis_joint_frame", src.get("axis_joint_frame_urdf_literal", "N/A")))
    lower = src.get("lower_urdf_rad", src.get("lower_urdf_m", "N/A"))
    upper = src.get("upper_urdf_rad", src.get("upper_urdf_m", "N/A"))
    transform_rows.append({
        "joint_name": joint,
        "joint_type": jtype,
        "parent_link": src["parent_link"],
        "child_link": src["child_link"],
        "parent_carrier": src["parent_carrier"],
        "child_carrier": src["child_carrier"],
        "parent_side_frame": parent_frame(joint),
        "parent_side_xyz_m": xyz,
        "parent_side_rpy_rad": rpy,
        "child_side_frame": child_frame(joint),
        "child_side_xyz_m": "0 0 0",
        "child_side_rpy_rad": "0 0 0",
        "q0_world_relation": "WORLD_TRANSFORMS_COINCIDE_AT_Q0",
        "origin_application_count_required": "EXACTLY_ONCE_ON_PARENT_SIDE",
        "axis_owner": src["child_carrier"] if jtype != "fixed" else "NONE_FIXED_JOINT",
        "axis_joint_frame": axis if jtype != "fixed" else "N/A",
        "status": "REFROZEN_MACHINE_RATIFIED",
    })
    branch_rule = (
        "ABSOLUTE_LINEAR_DIFFERENCE"
        if jtype == "prismatic"
        else "NOT_APPLICABLE_FIXED"
        if jtype == "fixed"
        else "ABSOLUTE_UNWRAPPED_BOUNDED_COORDINATE_WITH_EXPLICIT_BRANCH_INDEX"
    )
    joint_rows_v2.append({
        "joint_name": joint,
        "type": jtype,
        "parent_link": src["parent_link"],
        "child_link": src["child_link"],
        "parent_carrier": src["parent_carrier"],
        "child_carrier": src["child_carrier"],
        "parent_side_frame": parent_frame(joint),
        "child_side_frame": child_frame(joint),
        "parent_side_origin_xyz_m": xyz,
        "parent_side_origin_rpy_rad": rpy,
        "child_side_origin_xyz_m": "0 0 0",
        "child_side_origin_rpy_rad": "0 0 0",
        "axis_owner": src["child_carrier"] if jtype != "fixed" else "NONE_FIXED",
        "axis_joint_frame": axis if jtype != "fixed" else "N/A",
        "lower_urdf": lower,
        "upper_urdf": upper,
        "q0": "0" if jtype != "fixed" else "EXACT_FIXED_TRANSFORM",
        "validation_metric": branch_rule,
        "native_driver": (
            "NONE_FIXED_JOINT" if jtype == "fixed"
            else f"J{joint_order.index(joint)+1:02d}_LIMIT_ANGLE_DRIVER" if jtype == "revolute"
            else "P01_LIMIT_DISTANCE_DRIVER" if joint == "gripper_joint1"
            else "P02_LIMIT_DISTANCE_DRIVER"
        ),
        "status": "REFROZEN_CONTRACT_READY_NATIVE_NOT_CREATED",
    })
    if jtype == "revolute":
        lower_f = float(lower)
        upper_f = float(upper)
        travel = upper_f - lower_f
        driver_rows_v2.append({
            "joint_name": joint,
            "joint_type": jtype,
            "urdf_to_cad_driver": f"theta=q-({lower_f:g})",
            "cad_min": "0",
            "cad_max": f"{travel:g}",
            "cad_q0": f"{-lower_f:g}",
            "native_driver_mate": joint_rows_v2[-1]["native_driver"],
            "readback_channels": "RAW_API_ANGLE|ALIGNMENT_STATE|UNWRAPPED_BRANCH_INDEX|RECONSTRUCTED_Q|AXIS_DOT|ZERO_PLANE_DOT",
            "full_sweep_required": "TRUE",
            "enhanced_branch_probe": "TRUE" if joint in {"joint1", "joint4", "joint6"} else "FALSE",
            "validation_metric": branch_rule,
            "status": "REFROZEN_CONTRACT_READY_NATIVE_NOT_CREATED",
        })
    elif jtype == "prismatic":
        driver_rows_v2.append({
            "joint_name": joint,
            "joint_type": jtype,
            "urdf_to_cad_driver": "d=q",
            "cad_min": str(lower),
            "cad_max": str(upper),
            "cad_q0": "0",
            "native_driver_mate": joint_rows_v2[-1]["native_driver"],
            "readback_channels": "RAW_API_DISTANCE|RECONSTRUCTED_Q|AXIS_DOT|ZERO_PLANE_DOT",
            "full_sweep_required": "TRUE",
            "enhanced_branch_probe": "INDEPENDENT_ASYMMETRIC_AND_FOUR_CORNERS",
            "validation_metric": branch_rule,
            "status": "REFROZEN_CONTRACT_READY_NATIVE_NOT_CREATED",
        })

write_csv(transform_register_path, list(transform_rows[0].keys()), transform_rows)
write_csv(joint_register_v2_path, list(joint_rows_v2[0].keys()), joint_rows_v2)
write_csv(driver_v2_path, list(driver_rows_v2[0].keys()), driver_rows_v2)

carrier_map_rows = []
carrier_register_rows = []
feature_rows = []
for link in link_order:
    src = carrier_by_link[link]
    incoming = incoming_by_link[link]
    outgoing = outgoing_by_link[link]
    incoming_src = joint_by_name[incoming] if incoming else None
    moving = bool(incoming and incoming_src["joint_type"] in {"revolute", "prismatic"})
    fixed = bool(incoming and incoming_src["joint_type"] == "fixed")
    outgoing_frames = "|".join(parent_frame(j) for j in outgoing) if outgoing else "NONE"
    incoming_frame = child_frame(incoming) if incoming else "NONE"
    required_features = (
        f"AXIS_{incoming}|PLANE_ZERO_{incoming}" if moving
        else "GFIX_PLN_X|GFIX_PLN_Y|GFIX_PLN_Z" if fixed
        else "NONE"
    )
    carrier_map_rows.append({
        "carrier_id": src["carrier_id"],
        "accepted_link": link,
        "incoming_joint": incoming or "NONE",
        "incoming_child_side_frame": incoming_frame,
        "outgoing_parent_side_frames": outgoing_frames,
        "carrier_role": "ROOT" if link == "base_link" else "BRANCH_PARENT" if link == "gripper_link" else "PRISMATIC_LEAF" if link.startswith("gripper_") else "SERIAL_LINK",
        "execution_authority": "JOINT_SIDE_EXPLICIT_V2",
        "native_part_exists": "NO",
        "status": "REFROZEN_CONTRACT_READY_NATIVE_NOT_CREATED",
    })
    carrier_register_rows.append({
        "carrier_id": src["carrier_id"],
        "accepted_link_name": link,
        "planned_native_part_filename": src["planned_native_part_filename"],
        "incoming_joint": incoming or "NONE",
        "incoming_joint_type": incoming_src["joint_type"] if incoming else "NONE",
        "parent_link": incoming_src["parent_link"] if incoming else "NONE",
        "parent_carrier": incoming_src["parent_carrier"] if incoming else "NONE",
        "incoming_parent_side_frame_on_parent": parent_frame(incoming) if incoming else "NONE",
        "incoming_child_side_frame_on_this_carrier": incoming_frame,
        "parent_side_origin_xyz_m": str(incoming_src["origin_xyz_m"]) if incoming else "N/A",
        "parent_side_origin_rpy_rad": str(incoming_src["origin_rpy_rad"]) if incoming else "N/A",
        "child_side_origin_xyz_m": "0 0 0" if incoming else "N/A",
        "child_side_origin_rpy_rad": "0 0 0" if incoming else "N/A",
        "incoming_axis_joint_frame": str(incoming_src.get("axis_joint_frame", "N/A")) if moving else "N/A",
        "incoming_lower_urdf": str(incoming_src.get("lower_urdf_rad", incoming_src.get("lower_urdf_m", "N/A"))) if incoming else "N/A",
        "incoming_upper_urdf": str(incoming_src.get("upper_urdf_rad", incoming_src.get("upper_urdf_m", "N/A"))) if incoming else "N/A",
        "outgoing_joints": "|".join(outgoing) if outgoing else "NONE",
        "outgoing_parent_side_frames_on_this_carrier": outgoing_frames,
        "required_link_frame": f"CS_LINK_{link}",
        "required_visual_mount_frame": f"CS_VISUAL_MOUNT_{link}",
        "required_joint_reference_features": required_features,
        "accepted_urdf_mass_kg": str(src["accepted_urdf_mass_kg"]),
        "mass_inertia_authority": "ACCEPTED_URDF",
        "cad_mass_contribution": "ZERO",
        "bom_exclude": "TRUE",
        "source_urdf_sha256": URDF_SHA,
        "native_status": "NOT_CREATED",
        "row_status": "REFROZEN_MACHINE_RATIFIED",
    })
    feature_rows.append({
        "carrier_file": src["planned_native_part_filename"],
        "accepted_link": link,
        "link_frame": f"CS_LINK_{link}",
        "incoming_joint_child_side_frame": incoming_frame,
        "outgoing_joint_parent_side_frames": outgoing_frames.replace("|", ";"),
        "moving_axis_features": f"AXIS_{incoming}" if moving else "NONE",
        "q0_plane_features": f"PLANE_ZERO_{incoming}" if moving else "NONE",
        "fixed_joint_reference_features": "GFIX_PLN_X;GFIX_PLN_Y;GFIX_PLN_Z" if fixed else "NONE",
        "visual_mount_frame": f"CS_VISUAL_MOUNT_{link}",
        "owner_local_transform_contract": "INCOMING_CHILD_SIDE_IDENTITY_OUTGOING_PARENT_SIDE_URDF_ORIGIN",
        "status": "PASS_MACHINE_REFROZEN_NATIVE_NOT_CREATED",
    })

write_csv(carrier_map_v2_path, list(carrier_map_rows[0].keys()), carrier_map_rows)
write_csv(carrier_register_v2_path, list(carrier_register_rows[0].keys()), carrier_register_rows)

mapping_v2 = {
    "schema": "B51R1_URDF_CARRIER_FRAME_MAPPING_V2",
    "generated_at": now(),
    "status": "PASS_OFFLINE_MAPPING_REFROZEN_NATIVE_CAD_NOT_CREATED",
    "execution_authority": "JOINT_SIDE_EXPLICIT_V2",
    "authority": {
        "accepted_urdf": file_record(urdf, "KINEMATICS_MASS_INERTIA_AUTHORITY"),
        "standing_delegation_activation": file_record(activation_receipt_path, "OWNER_STANDING_DELEGATION"),
        "historical_v1_mapping": file_record(old_mapping_path, "HISTORICAL_NONEXECUTABLE_SUPERSEDED_BY_V2"),
    },
    "topology": {"links": 10, "joints": 9, "revolute": 6, "fixed": 1, "independent_prismatic": 2, "mimic": 0},
    "joint_side_transform_rule": {
        "parent_side": "T_PARENT_LINK_TO_PARENT_SIDE_EQUALS_ACCEPTED_URDF_JOINT_ORIGIN",
        "child_side": "T_CHILD_LINK_TO_CHILD_SIDE_EQUALS_IDENTITY",
        "q0_relation": "PARENT_AND_CHILD_SIDE_WORLD_TRANSFORMS_COINCIDE_AT_Q0",
        "origin_application_count": "EXACTLY_ONCE_PARENT_SIDE_ONLY",
    },
    "joint_records": transform_rows,
    "carrier_records": carrier_register_rows,
    "gripper_modes": {
        "packaging_mode_domain": ["COMMON", "MODE_A", "MODE_B"],
        "gripper_mode_domain": ["DYNAMICS_V1_LOCKED", "MECHANISM_2P_ACTIVE"],
        "orthogonal_mode_axes": True,
        "mechanism_2p_active": {"p1_range_m": [0.0, 0.0715], "p2_range_m": [0.0, 0.0715], "mimic": 0},
        "dynamics_v1_locked": {"lock_q1_m": None, "lock_q2_m": None, "status": "HOLD_LOCK_VALUES_NOT_AUTHORIZED"},
        "physical_open_closed_semantics": "NOT_AUTHORIZED_USE_MIN_MID_MAX_NUMERIC_ONLY",
    },
    "claim_limit": "REFROZEN_OFFLINE_MAPPING_NATIVE_CAD_AND_CONSUMER_MODEL_VALIDATION_NOT_YET_EXECUTED",
}
write_yaml(mapping_v2_path, mapping_v2)

expanded_path = CLOSURE / "B51R1_G1A_EXPANDED_NATIVE_FEATURE_REGISTER_V2.csv"
write_csv(expanded_path, list(feature_rows[0].keys()), feature_rows)

alias_rows = []
for joint in joint_order:
    parent_link = parent_for[joint]
    child_link = child_for[joint]
    alias_rows.extend([
        {"scope_carrier": carrier_id_for[child_link], "legacy_token": f"CS_PARENT_JOINT_{joint}", "v2_native_token": child_frame(joint), "semantic": "INCOMING_CHILD_SIDE", "api_lookup_allowed": "FALSE", "duplicate_feature_allowed": "FALSE"},
        {"scope_carrier": carrier_id_for[parent_link], "legacy_token": f"CS_CHILD_JOINT_{joint}", "v2_native_token": parent_frame(joint), "semantic": "OUTGOING_PARENT_SIDE", "api_lookup_allowed": "FALSE", "duplicate_feature_allowed": "FALSE"},
        {"scope_carrier": carrier_id_for[child_link], "legacy_token": f"CS_IN_{joint}", "v2_native_token": child_frame(joint), "semantic": "GENERIC_LEGACY_INCOMING", "api_lookup_allowed": "FALSE", "duplicate_feature_allowed": "FALSE"},
        {"scope_carrier": carrier_id_for[parent_link], "legacy_token": f"CS_OUT_{joint}", "v2_native_token": parent_frame(joint), "semantic": "GENERIC_LEGACY_OUTGOING", "api_lookup_allowed": "FALSE", "duplicate_feature_allowed": "FALSE"},
    ])
legacy_out = {
    "CS_OUT_J1": "joint1", "CS_OUT_J2": "joint2", "CS_OUT_J3": "joint3",
    "CS_OUT_J4": "joint4", "CS_OUT_J5": "joint5", "CS_OUT_J6": "joint6",
    "CS_OUT_GRIPPER_FIXED": "gripper_joint", "CS_OUT_P1": "gripper_joint1", "CS_OUT_P2": "gripper_joint2",
}
for token, joint in legacy_out.items():
    alias_rows.append({"scope_carrier": carrier_id_for[parent_for[joint]], "legacy_token": token, "v2_native_token": parent_frame(joint), "semantic": "EXACT_LEGACY_CARRIER_MAP_OUTGOING", "api_lookup_allowed": "FALSE", "duplicate_feature_allowed": "FALSE"})
for link in link_order:
    alias_rows.append({"scope_carrier": carrier_id_for[link], "legacy_token": "CS_VISUAL", "v2_native_token": f"CS_VISUAL_MOUNT_{link}", "semantic": "CONTEXTUAL_VISUAL_ALIAS", "api_lookup_allowed": "FALSE", "duplicate_feature_allowed": "FALSE"})
    alias_rows.append({"scope_carrier": carrier_id_for[link], "legacy_token": "CS_LINK", "v2_native_token": f"CS_LINK_{link}", "semantic": "CONTEXTUAL_LINK_ALIAS", "api_lookup_allowed": "FALSE", "duplicate_feature_allowed": "FALSE"})
for joint in [j for j in joint_order if j != "gripper_joint"]:
    child_carrier = carrier_id_for[child_for[joint]]
    alias_rows.extend([
        {"scope_carrier": child_carrier, "legacy_token": f"AXIS_{joint}_POS", "v2_native_token": f"AXIS_{joint}", "semantic": "MOVING_AXIS_ALIAS", "api_lookup_allowed": "FALSE", "duplicate_feature_allowed": "FALSE"},
        {"scope_carrier": child_carrier, "legacy_token": f"PLN_{joint}_Q0", "v2_native_token": f"PLANE_ZERO_{joint}", "semantic": "ZERO_PLANE_ALIAS", "api_lookup_allowed": "FALSE", "duplicate_feature_allowed": "FALSE"},
    ])
alias_path = CLOSURE / "B51R1_G1A_FEATURE_ALIAS_REGISTER.csv"
write_csv(alias_path, list(alias_rows[0].keys()), alias_rows)

naming_path = CLOSURE / "B51R1_G1A_FEATURE_NAMING_MACHINE_RATIFICATION.yaml"
naming = {
    "schema": "B51R1_G1A_FEATURE_NAMING_MACHINE_RATIFICATION_V2",
    "generated_at": now(),
    "status": "PASS_OWNER_STANDING_DELEGATION_MACHINE_REFROZEN",
    "gate": "G1A",
    **authority_common,
    "scheme_id": "JOINT_SIDE_EXPLICIT_V2",
    "tokens": {
        "link_frame": "CS_LINK_<LINK>",
        "joint_parent_side_frame": "CS_JOINT_<JOINT>_PARENT_SIDE",
        "joint_child_side_frame": "CS_JOINT_<JOINT>_CHILD_SIDE",
        "moving_axis": "AXIS_<JOINT>",
        "zero_plane": "PLANE_ZERO_<JOINT>",
        "visual_mount": "CS_VISUAL_MOUNT_<LINK>",
    },
    "ownership": {
        "parent_carrier": "JOINT_PARENT_SIDE_FRAME_AT_ACCEPTED_URDF_ORIGIN",
        "child_carrier": "JOINT_CHILD_SIDE_FRAME_AT_LINK_LOCAL_IDENTITY_PLUS_MOVING_AXIS_AND_ZERO_PLANE",
        "fixed_joint_child": "CHILD_SIDE_FRAME_PLUS_GFIX_PLN_X_Y_Z_NO_MOVING_DRIVER",
        "gripper_branch_parent": "TWO_DISTINCT_PARENT_SIDE_FRAMES",
    },
    "transform_contract": file_record(transform_register_path, "OWNER_LOCAL_JOINT_SIDE_TRANSFORM_AUTHORITY"),
    "alias_register": file_record(alias_path, "READ_ONLY_ALIAS_NO_API_LOOKUP"),
    "operational_v2_assets": [
        file_record(carrier_map_v2_path, "OPERATIONAL_V2_CARRIER_MAP"),
        file_record(carrier_register_v2_path, "OPERATIONAL_V2_CARRIER_REGISTER"),
        file_record(mapping_v2_path, "OPERATIONAL_V2_URDF_CARRIER_MAPPING"),
        file_record(joint_register_v2_path, "OPERATIONAL_V2_NATIVE_JOINT_REGISTER"),
        file_record(driver_v2_path, "OPERATIONAL_V2_DRIVER_MAPPING"),
        file_record(expanded_path, "OPERATIONAL_V2_EXPANDED_FEATURE_REGISTER"),
    ],
    "legacy_policy": {
        "original_files_unchanged": True,
        "legacy_execution_status": "HISTORICAL_NONEXECUTABLE_SUPERSEDED_BY_V2",
        "alias_allowed_for_api_lookup": False,
        "duplicate_native_features": False,
    },
    "claim_limit": "FEATURE_NAMING_AUTHORITY_FOR_ISOLATED_NATIVE_CANDIDATE_ONLY",
}
write_yaml(naming_path, naming)

tolerance_items = [
    ("coordinate_system_translation_readback", 1.0e-8, "m", "L2_NORM_OF_TRANSLATION_ERROR_VECTOR", 1.0e-7, "SAME_SESSION_10_REBUILD_READBACKS"),
    ("coordinate_system_rotation_readback", 1.0e-8, "rad", "SO3_GEODESIC_ANGLE_ACOS_CLAMP_TRACE", 1.0e-7, "SAME_SESSION_10_REBUILD_READBACKS"),
    ("fk_link_origin_translation", 5.0e-6, "m", "L2_NORM_OF_TRANSLATION_ERROR_VECTOR", 2.0e-5, "SAME_SESSION_10_REBUILD_READBACKS"),
    ("fk_link_rotation", 5.0e-6, "rad", "SO3_GEODESIC_ANGLE_ACOS_CLAMP_TRACE", 2.0e-5, "SAME_SESSION_10_REBUILD_READBACKS"),
    ("revolute_joint_value_readback", 1.0e-6, "rad", "ABSOLUTE_UNWRAPPED_BOUNDED_JOINT_COORDINATE_DIFFERENCE_WITH_BRANCH_INDEX", 5.0e-6, "SAME_SESSION_10_DRIVE_REBUILD_READBACKS"),
    ("prismatic_joint_value_readback", 1.0e-6, "m", "ABSOLUTE_LINEAR_DIFFERENCE", 5.0e-6, "SAME_SESSION_10_DRIVE_REBUILD_READBACKS"),
    ("q0_reset_revolute", 1.0e-6, "rad", "ABSOLUTE_UNWRAPPED_BOUNDED_JOINT_COORDINATE_DIFFERENCE_WITH_BRANCH_INDEX", 5.0e-6, "SAME_DOCUMENT_10_NONZERO_TO_Q0_CYCLES"),
    ("q0_reset_prismatic", 1.0e-6, "m", "ABSOLUTE_LINEAR_DIFFERENCE", 5.0e-6, "SAME_DOCUMENT_10_NONZERO_TO_Q0_CYCLES"),
    ("same_document_return_to_q0_translation", 5.0e-6, "m", "MAX_LINK_L2_TRANSLATION_ERROR", 2.0e-5, "SAME_DOCUMENT_10_NONZERO_TO_Q0_CYCLES"),
    ("same_document_return_to_q0_rotation", 5.0e-6, "rad", "MAX_LINK_SO3_GEODESIC_ANGLE", 2.0e-5, "SAME_DOCUMENT_10_NONZERO_TO_Q0_CYCLES"),
    ("cold_reopen_revolute_persistence", 1.0e-6, "rad", "ABSOLUTE_UNWRAPPED_BOUNDED_JOINT_COORDINATE_DIFFERENCE_WITH_BRANCH_INDEX", 5.0e-6, "TEN_DISTINCT_NORMAL_EXIT_AND_NEW_PROCESS_REOPENS"),
    ("cold_reopen_prismatic_persistence", 1.0e-6, "m", "ABSOLUTE_LINEAR_DIFFERENCE", 5.0e-6, "TEN_DISTINCT_NORMAL_EXIT_AND_NEW_PROCESS_REOPENS"),
    ("mate_limit_revolute_readback", 1.0e-6, "rad", "ABSOLUTE_UNWRAPPED_LIMIT_ENDPOINT_DIFFERENCE_WITH_BRANCH_INDEX", 5.0e-6, "SAME_SESSION_10_ENDPOINT_READBACKS"),
    ("mate_limit_prismatic_readback", 1.0e-6, "m", "ABSOLUTE_SCALAR_DIFFERENCE", 5.0e-6, "SAME_SESSION_10_ENDPOINT_READBACKS"),
]
tolerances = {}
for name, value, unit, metric, ceiling, sampling in tolerance_items:
    tolerances[name] = {
        "selected_value": value,
        "selected_unit": unit,
        "selected_metric": metric,
        "conditional_authoring_only_ceiling": ceiling,
        "repeatability_sampling_contract": sampling,
        "status": "PASS_OWNER_STANDING_DELEGATION_MACHINE_RATIFIED",
    }
tolerance_path = CLOSURE / "B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml"
tolerance = {
    "schema": "B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION_V3",
    "generated_at": now(),
    "status": "PASS_OWNER_STANDING_DELEGATION_MACHINE_RATIFIED",
    "gate": "G1A",
    **authority_common,
    "scope": "PHASE2A_CAD_URDF_NUMERICAL_CONSISTENCY_ONLY",
    "manufacturing_tolerance_authority": False,
    "structural_or_flight_qualification_authority": False,
    "tolerances": tolerances,
    "repeatability_fallback": {
        "first_failure_preserved": True,
        "sample_count_required": 10,
        "all_raw_values_required": True,
        "required_statistics": ["sample_count", "maximum", "mean", "standard_deviation", "raw_values", "sample_identity"],
        "conditional_pass_requires": [
            "ALL_TEN_VALUES_AT_OR_BELOW_APPLICABLE_HARD_CEILING",
            "MAXIMUM_AT_OR_BELOW_HARD_CEILING",
            "MEAN_PLUS_THREE_STANDARD_DEVIATIONS_AT_OR_BELOW_HARD_CEILING",
            "NO_MISSING_OR_REUSED_SAMPLE_IDENTITY",
            "COLD_REOPEN_METRICS_USE_TEN_DISTINCT_NORMAL_EXIT_NEW_PROCESS_IDENTITIES",
        ],
        "conditional_status": "PASS_WITH_MEASURED_REPEATABILITY_BOUND_AUTHORING_ONLY",
        "gate_pass": False,
        "formal_t005_release": False,
        "control_model_release": False,
        "automatic_threshold_relaxation": False,
        "insufficient_session_budget_action": "HOLD_NO_FALLBACK_CREDIT",
        "exceeds_ceiling_action": "FAIL_CLOSED",
    },
    "claim_limit": "AUTHORING_NUMERICAL_CONSISTENCY_ONLY_NO_MANUFACTURING_OR_FORMAL_T005_CREDIT",
}
write_yaml(tolerance_path, tolerance)

architecture_text = """# B5.1R1 carrier architecture contract V2

Status: `REFROZEN_OPERATIONAL_CONTRACT / NATIVE_PARTS_NOT_CREATED`

This contract supersedes the V1 `CS_IN/CS_OUT` and counterintuitive
`CS_PARENT_JOINT/CS_CHILD_JOINT` tokens for execution. Original files remain
immutable historical evidence.

## Native ownership and transform rule

- Parent carrier owns `CS_JOINT_<JOINT>_PARENT_SIDE` at the accepted URDF
  joint origin: `T(parent_link,parent_side)=T_URDF_origin`.
- Child carrier owns `CS_JOINT_<JOINT>_CHILD_SIDE` at link-local identity:
  `T(child_link,child_side)=I`.
- At q0 the two side-frame world transforms must coincide. The URDF origin is
  applied exactly once, on the parent side; it must never be applied again to
  the child carrier.
- A moving joint's child carrier also owns `AXIS_<JOINT>` and
  `PLANE_ZERO_<JOINT>`. The fixed joint uses `GFIX_PLN_X/Y/Z` and no driver.
- `gripper_link` owns two distinct outgoing parent-side frames for the two
  independent prismatic fingers.

## Carrier content

Every carrier is reference-only, zero solid-body, zero CAD mass, free of
external references, excluded from BOM, and carries the accepted URDF SHA-256.
It contains one `CS_LINK_<LINK>`, zero or one incoming child-side frame, every
required outgoing parent-side frame, and one `CS_VISUAL_MOUNT_<LINK>`.

## Motion contract

The chain is `6R + 1 fixed + 2 independent P`, with one native Limit
Angle/Distance driver per moving joint. Imported faces/edges, component Fix,
Move Component, Transform2 and a shared gripper-width driver are prohibited.
Every revolute joint records raw API angle, alignment state, unwrapped branch
index, reconstructed q, axis dot and zero-plane dot. J1/J4/J6 require enhanced
full-range branch probes; J6 seam witnesses include q=-3.13 and +3.13 rad and
must not be collapsed by shortest-angle comparison.

## Authority and limits

Accepted URDF mass/inertia remain authoritative. Fine geometry may attach only
through `CS_VISUAL_MOUNT_<LINK>` and may not drive motion or overwrite dynamics.
This contract grants no native-CAD, H10, T005, manufacturing, launch or flight
credit until the applicable Gate receipts pass.
"""
write_text(architecture_v2_path, architecture_text)

sessions = [
    ("S01", "CREATE_FINAL_MASTER_SKELETON", "G1A_PASS"),
    ("S02", "COLD_REOPEN_MASTER_SKELETON", "S01_PASS"),
    ("S03", "CREATE_10_CARRIERS", "S02_PASS"),
    ("S04", "COLD_REOPEN_10_CARRIERS", "S03_PASS"),
    ("S05", "BUILD_J00_J09_AND_T005_A0_B0", "S04_PASS"),
    ("S06", "T005_C0_COLD_REOPEN", "S05_PASS"),
    ("S07", "ATTACH_FINE_GEOMETRY_INCREMENTALLY", "S06_PASS"),
    ("S08", "FORMAL_T005_A_B", "S07_PASS"),
    ("S09", "FORMAL_T005_C", "S08_PASS"),
    ("S10", "ADAPTER_CANDIDATE_AUTHORING", "FORMAL_T005_PASS"),
    ("S11", "G07_G08_HDRM_CANDIDATE_AUTHORING", "ADAPTER_TRADE_PASS"),
    ("S12", "H10_REWORK_MEASUREMENT", "S11_PASS"),
    ("S13", "TOP_INTEGRATION_CANDIDATE", "H10_CLOSED"),
    ("S14", "G8A_RIGID_CONTINUOUS_CLEARANCE", "TOP_INTEGRATION_PASS"),
    ("S15", "PRELIMINARY_STRUCTURE_MODAL_AND_UNCERTAINTY_ENVELOPES", "G8A_PASS"),
    ("S16", "G8B_ROBUST_CONTINUOUS_CLEARANCE", "S15_ENVELOPES_COMPLETE"),
    ("S17", "MASS_LEDGER_AND_CONTROL_HANDOFF", "G8B_PASS"),
    ("S18", "CANDIDATE_DRAWINGS_AND_EXCHANGE", "G10_CANDIDATE_READY"),
]
session_plan = {
    "schema": "B51R1_AUTONOMOUS_SESSION_PLAN_V2",
    "generated_at": now(),
    "status": "REFROZEN_OPERATIONAL_STANDING_DELEGATION_PLAN",
    "authority": authority_common,
    "max_visible_sessions": 20,
    "primary_sessions": 18,
    "global_recovery_reserve": ["SR01", "SR02"],
    "single_process_only": True,
    "sessions": [{"id": sid, "purpose": purpose, "auto_start_after": after} for sid, purpose, after in sessions],
    "corrected_dependency_order": "G8A_THEN_STRUCTURE_THERMAL_TOLERANCE_HARNESS_BACKLASH_ENVELOPES_THEN_G8B",
    "g8b_required_inputs": [
        "SIGNED_STRUCTURAL_DEFORMATION_BY_STATE_AND_PAIR",
        "CONTACT_PAD_COMPRESSION",
        "THERMAL_DISTORTION",
        "MANUFACTURING_AND_ASSEMBLY_TOLERANCE",
        "JOINT_BACKLASH",
        "HARNESS_UNCERTAINTY",
        "SOLAR_AND_HDRM_FAILURE_BRANCHES",
        "FULL_2P_TRAVEL",
    ],
    "unknown_input_rule": "UNKNOWN_FAIL_CLOSED_NO_G8B_PASS",
    "recovery_rule": "MAX_TWO_GLOBAL_DISTINCT_RECOVERY_LAUNCHES_THEN_EXCEPTION_PACKAGE",
    "historical_session_authorizations_do_not_consume_new_pool": True,
}
write_yaml(session_plan_v2_path, session_plan)

gate_rows = []
for sid, purpose, after in sessions:
    gate_rows.append({
        "session_id": sid,
        "purpose": purpose,
        "symbolic_prerequisite": after,
        "required_receipt_pattern": f"07_VERIFICATION/AUTONOMOUS/{sid}/PREREQUISITE_*.json",
        "required_status": "PASS",
        "required_sha256_non_null": "TRUE",
        "process_count_before": "0",
        "concurrency_max": "1",
        "failure_action": "STOP_BRANCH_AND_PRESERVE_EXCEPTION_EVIDENCE",
    })
write_csv(gate_map_v2_path, list(gate_rows[0].keys()), gate_rows)

design_yaml = {
    "schema": "B51R1_SPACE_EMBODIED_ARM_MECHANICAL_DESIGN_BASELINE_V1",
    "generated_at": now(),
    "status": "ENGINEERING_CANDIDATE_BASELINE_NO_FLIGHT_CREDIT",
    "authority": {"accepted_urdf": file_record(urdf, "KINEMATICS_MASS_INERTIA_AUTHORITY"), "standing_delegation": file_record(activation_receipt_path, "OWNER_STANDING_DELEGATION")},
    "system_layers": [
        {"id": "LAYER_0", "name": "MASTER_SKELETON", "content": "ZERO_BODY_DATUM_INTERFACE_KEEPOUT_CONTROL"},
        {"id": "LAYER_1", "name": "KINEMATIC_CARRIERS", "content": "TEN_ZERO_MASS_CARRIERS_6R_1FIXED_2P"},
        {"id": "LAYER_2", "name": "FINE_GEOMETRY", "content": "RIGID_VISUAL_MOUNT_ONLY_NO_MOTION_MATES"},
        {"id": "LAYER_3", "name": "SPACECRAFT_INTERFACE", "content": "PANEL_BYPASS_ADAPTER_PLUS_G07_G08_HDRM"},
        {"id": "LAYER_4", "name": "EMBODIED_SAFETY", "content": "PERCEPTION_TO_PHYSICS_TO_SAFE_UNKNOWN_TO_CONTROL"},
    ],
    "master_skeleton": {
        "coordinate_tracks": {"task_face_x_mm": 183.0, "dynamics_mount_x_mm": 185.25, "display_mount_x_mm": 198.0, "a0_clock_deg": 25.0},
        "cross_section_datums_mm": {"longeron_axis_abs_yz": 101.65, "primary_surface_abs_yz": 110.15, "panel_outer_abs_yz": 113.15},
        "mount_target": {"face_mm": [160.0, 160.0], "central_keep_clear_diameter_mm": 100.0},
        "configurations": ["COMMON_CANONICAL", "MODE_A_EVALUATION", "MODE_B_EVALUATION"],
        "keepouts": {"solar_sweep": "TBD_HOLD", "arm_release": "TBD_HOLD", "harness": "TBD_HOLD", "service_access": "TBD_HOLD"},
    },
    "arm_topology": {"links": link_order, "joints": joint_order, "semantic": "6R_PLUS_1_FIXED_PLUS_2_INDEPENDENT_P", "branch_parent": "gripper_link"},
    "mode_axes": {
        "packaging_mode": ["COMMON", "MODE_A", "MODE_B"],
        "gripper_mode": ["DYNAMICS_V1_LOCKED", "MECHANISM_2P_ACTIVE"],
        "gripper_lock_values": "TBD_AUTHORITY_NO_DEFAULT_TO_Q0",
        "mechanism_2p_numeric_states": ["MIN_NUMERIC", "MID_NUMERIC", "MAX_NUMERIC", "ASYMMETRIC", "FOUR_CORNERS"],
    },
    "adapter_candidates": [
        {"id": "A", "name": "DUAL_TRANSVERSE_PRIMARY_BRIDGE", "load_path": "B601_FLANGE_TO_TWO_CROSSBEAMS_TO_FOUR_NAMED_LONGERON_NODES", "central_channel": "PRESERVE_D100", "panel_credit": "NONE"},
        {"id": "B", "name": "FORE_AFT_MAIN_FRAME_BRIDGE", "load_path": "B601_FLANGE_TO_FORE_AFT_BRIDGE_TO_TWO_NAMED_TRANSVERSE_FRAMES", "central_channel": "PRESERVE_D100", "panel_credit": "NONE"},
        {"id": "C", "name": "LOCAL_REINFORCEMENT_RING", "load_path": "B601_FLANGE_TO_CLOSED_RING_TO_FOUR_PRIMARY_NODE_ATTACHMENTS", "central_channel": "PRESERVE_D100", "panel_credit": "NONE"},
    ],
    "adapter_trade_weights": {"primary_load_path": 0.25, "h10_and_keepout": 0.15, "stiffness_trend": 0.15, "mass_trend": 0.10, "tool_and_service_access": 0.10, "mode_a_b_compatibility": 0.10, "central_channel_and_harness": 0.10, "manufacturability_candidate": 0.05},
    "adapter_downselect": "NONE_UNTIL_S10_MACHINE_EVIDENCE",
    "stowage_candidate": {
        "architecture": "TWO_STATION_KINEMATIC_COMPLIANT_RESTRAINT_WITH_INDEPENDENT_HDRM_PRELOAD",
        "G07": "PRIMARY_V_LOCATOR_RESTRAINS_TWO_LOCAL_NORMAL_DIRECTIONS_ALLOWS_AXIAL_FLOAT",
        "G08": "SECONDARY_FLAT_FLOATING_SADDLE_RESTRAINS_ONE_LOCAL_NORMAL_DIRECTION",
        "compliance": "METALLIC_FLEXURE_OR_SPHERICAL_WASHER_CANDIDATE_TBD",
        "HDRM": "PRELOAD_NORMAL_TO_SADDLES_RELEASE_RETRACTS_OUTSIDE_RESIDUAL_KEEPOUT",
        "panel_bypass": "ALL_SUPPORT_STANDOFFS_CONNECT_TO_NAMED_PRIMARY_FRAMES_OR_LONGERONS_WITH_PANEL_CLEARANCE",
        "contact_model": "UNILATERAL_OPEN_STICK_SLIP_WITH_PRELOAD_TOLERANCE_AND_COMPLIANCE_TBD",
        "flight_device_selection": "NOT_SELECTED",
    },
    "verification": {
        "T005": ["A0_20_IMMUTABLE_POSES", "B0_SAME_DOCUMENT_CONTINUOUS_AND_Q0_RETURN", "C0_NORMAL_EXIT_COLD_REOPEN", "FORMAL_A_B_C_AFTER_FINE_GEOMETRY"],
        "clearance": ["G8A_RIGID_NOMINAL", "S15_UNCERTAINTY_ENVELOPES", "G8B_ROBUST_CONTINUOUS"],
        "H10": "28_OF_28_ROW_MEASUREMENT_AND_HASH_REQUIRED",
        "mass_books": ["DYNAMICS_AUTHORITY", "PHYSICAL_CAD", "SYSTEM_ADDITIVE_OVERLAY"],
    },
    "provisional_items": ["LOAD_SPECTRUM", "MATERIAL_RELEASE", "FASTENER_PATTERN", "HDRM_DEVICE", "PAD_FRICTION_AND_COMPLIANCE", "THERMAL_MAP", "HARNESS_PROPERTIES", "SENSOR_MODELS"],
    "forbidden_claims": ["MANUFACTURING_READY", "LAUNCH_QUALIFIED", "FLIGHT_READY", "FINAL_H9_ARCHITECTURE"],
}
write_yaml(design_yaml_path, design_yaml)

design_md = """# B5.1R1 空间具身智能机械臂机械设计基线 V1

状态：`ENGINEERING_CANDIDATE_BASELINE_NO_FLIGHT_CREDIT`

本方案把机械系统分成五层：零实体 Master Skeleton、十个零质量运动
Carrier、按 link 刚性挂接的精细几何、绕过可拆面板的航天器接口与收拢
约束，以及位于 VLA 和执行器之间的物理/SAFE 层。

## 机构主线

运动拓扑严格保持 accepted URDF 的 `6R + 1 fixed + 2 independent P`。
父 Carrier 的 joint-side frame 承载一次 URDF origin；子 Carrier 的对应
frame 为 link-local identity。任何 child 侧再次施加 origin 的实现均判为
失败。两指没有 mimic 或共享宽度驱动。

## 航天器接口

共同约束为 160 × 160 mm 候选安装面和 Ø100 mm 中央禁入通道。101.65 mm
是纵梁轴，110.15 mm 是主结构参考面，113.15 mm 仅为可拆面板/footprint
层。面板永远不获得根部弯矩主载荷路径信用。

S10 比较三种候选：双横梁四纵梁节点桥接、前后主框桥接、局部闭合加强
环。当前不作飞行架构下选；所有尺寸、材料、紧固件和载荷门槛在缺少
launcher/deployer ICD 与正式载荷谱时保持 provisional。

## G07/G08/HDRM

采用“两站运动学兼容约束”候选：G07 为主 V 形定位站，约束两个局部法向
并允许臂轴向浮动；G08 为次级平面浮动鞍座，仅约束一个局部法向。HDRM
沿鞍座法向施加预紧，释放后撤出残余禁入包络。所有支撑通过独立支柱或
桥架接入命名主框/纵梁，并与可拆面板留隙。最终约束信用必须由接触
Jacobian、容差角点和六向单位载荷反力闭合给出。

## Gate 顺序

先完成刚体名义连续间隙 G8a，再由结构/模态阶段生成结构变形、垫压缩、
热、制造装配公差、回差和线束不确定度包络，最后运行鲁棒连续间隙 G8b。
任一包络来源未知即保持 UNKNOWN/HOLD。H9 在没有权威 ICD 时维持
Mode A/Mode B 双分支。
"""
write_text(design_md_path, design_md)

lock_receipt_path = CLOSURE / "B51R1_STAGE_A_LOCKFILE_QUARANTINE_RECEIPT.json"
lock_receipt = {
    "schema": "B51R1_STAGE_A_LOCKFILE_QUARANTINE_RECEIPT_V2",
    "generated_at": now(),
    "status": "PASS_HASH_AND_QUARANTINE_NOT_DELETE",
    "authority_type": "OWNER_STANDING_DELEGATION_L1_REVERSIBLE_FILE_AUTONOMY",
    "delegation_charter_path": CHARTER_REL,
    "delegation_charter_sha256": CHARTER_SHA,
    "preconditions": {"solidworks_process_count": 0, "source_bytes": 6, "source_sha256": LOCK_SHA},
    "action": "MOVE_WITHIN_CANDIDATE_TO_QUARANTINE_NO_DELETE",
    "source": {"path": "02_MASTER_SKELETON/~$B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT", "exists_after": False},
    "quarantine": file_record(quarantine_lock, "RECOVERABLE_STALE_LOCKFILE_QUARANTINE", "QUARANTINED_NO_DELETE"),
    "stage_a_before": {"path": rel(stage_a), "bytes": 511198, "sha256": STAGE_A_SHA},
    "stage_a_after": file_record(stage_a, "PROTECTED_STAGE_A_UNCHANGED", "READ_ONLY_NO_SAVE_NO_REPAIR_NO_OVERWRITE"),
    "stage_a_unchanged": True,
    "recovery_method": "MOVE_QUARANTINE_FILE_BACK_TO_ORIGINAL_PATH_ONLY_UNDER_EXPLICIT_ENGINEERING_NEED_AND_ZERO_SW_PROCESS",
    "claim_limit": "STALE_TEMPORARY_LOCKFILE_QUARANTINED_STAGE_A_BYTES_UNCHANGED",
}
write_json(lock_receipt_path, lock_receipt)

session_ledger_path = CLOSURE / "B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json"
session_ledger = {
    "schema": "B51R1_AUTONOMOUS_SESSION_POOL_LEDGER_V1",
    "generated_at": now(),
    "status": "PREPARED_PENDING_G1A_PASS_AND_G1B_ACTIVATION",
    "authority_type": "OWNER_STANDING_DELEGATION",
    "budget": 20,
    "consumed_since_activation": 0,
    "remaining": 20,
    "concurrent_processes_max": 1,
    "planned_primary_sessions": [sid for sid, _, _ in sessions],
    "recovery_reserve": ["SR01", "SR02"],
    "historical_sessions_excluded_from_new_pool": True,
    "recovery_constraints": {"global_recovery_launches_max": 2, "must_bind_failed_primary_session": True, "must_use_distinct_technical_route": True},
    "entries": [],
}
write_json(session_ledger_path, session_ledger)

current_gate_path = CLOSURE / "B51R1_PHASE2_CURRENT_GATE_COMPOSITION.json"
current_gate = {
    "schema": "B51R1_PHASE2_CURRENT_GATE_COMPOSITION_V2",
    "generated_at": now(),
    "status": "G1A_CLOSURE_ASSETS_PREPARED_PENDING_DISTINCT_AGENT_QUORUM",
    "single_coordinate_system": file_record(CANDIDATE / "07_VERIFICATION" / "B51R1_SINGLE_CS_DIAGNOSTIC_GATE.json", "CURRENT_SINGLE_CS_GATE"),
    "phase1_intermediate": file_record(CANDIDATE / "07_VERIFICATION" / "B51R1_PHASE1_INTERMEDIATE_GATE_20260729.json", "CURRENT_PHASE1_GATE"),
    "h10": {"closed": 0, "total": 28, "unresolved": 28, "status": "HOLD"},
    "t005": {"A": "NOT_RUN", "B": "NOT_RUN", "C": "NOT_RUN"},
    "stale_embedded_snapshots": {
        "paths": ["05_H10/B51R1_H10_PHASE1_STATUS_CURRENT.json", "06_T005/B51R1_T005_EXECUTION_READINESS_CURRENT.json"],
        "disposition": "HISTORICAL_NESTED_PREREQUISITE_VALUES_SUPERSEDED_BY_THIS_COMPOSITION",
        "files_mutated": False,
    },
    "solidworks_process_count": 0,
    "native_targets": {"final_master_skeleton": "ABSENT", "carriers": "0_OF_10", "articulated_assembly": "ABSENT"},
    "claim_limit": "CURRENT_STATUS_COMPOSED_NO_NATIVE_GATE_PASS",
}
write_json(current_gate_path, current_gate)

finding_source_path = S00_WORKSET / "B51R1_PHASE2_G1_ADVERSARIAL_FINDINGS.csv"
disposition_source_path = S00_WORKSET / "B51R1_PHASE2_FINDING_DISPOSITION_REGISTER.csv"
findings = {row["finding_id"]: row for row in read_csv(finding_source_path)}
source_dispositions = read_csv(disposition_source_path)
g1a_evidence = {
    "AUTH-001": "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json",
    "AUTH-002": "B51R1_AUTONOMOUS_STANDING_DELEGATION_RECEIPT.json",
    "AUTH-003": "B51R1_STAGE_A_LOCKFILE_QUARANTINE_RECEIPT.json",
    "AUTH-004": "B51R1_STAGE_A_LOCKFILE_QUARANTINE_RECEIPT.json",
    "AUTH-005": "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json",
    "AUTH-006": "B51R1_AUTONOMOUS_EXPECTED_ARTIFACT_MANIFEST_V3.csv",
    "MRT-G1-001": "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json",
    "MRT-G1-002": "B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml",
    "MRT-G1-003": "B51R1_G1A_DATUM_MACHINE_RATIFICATION.yaml",
    "MRT-A7-004": "B51R1_G1A_MULTIAGENT_QUORUM_RECEIPT.json",
    "MRT-CM-014": "B51R1_PHASE2_CURRENT_GATE_COMPOSITION.json",
    "RBT-A2-004": "B51R1_G1A_FEATURE_NAMING_MACHINE_RATIFICATION.yaml",
    "FW-G1A-004": "B51R1_AUTONOMOUS_FINDING_DISPOSITION_REGISTER_V2.csv",
}
downstream_ids = {
    "MRT-A1-005", "MRT-A1-006", "MRT-A4-007", "MRT-A4-008", "MRT-A5-009",
    "MRT-A5-010", "MRT-A4A5-011", "MRT-A5-012", "MRT-A5-013", "RBT-A2-001",
    "RBT-A2-002", "RBT-A2-003", "RBT-A3-005", "RBT-A2-006", "RBT-A8-007",
    "RBT-A8-008", "RBT-A3-009", "A3A8-G8-003", "A3A8-G8-004",
}
disposition_rows = []
for row in source_dispositions:
    out = deepcopy(row)
    fid = row["finding_id"]
    if fid in g1a_evidence:
        out.update({"technical_status": "CLOSURE_ASSET_PREPARED_PENDING_FINAL_QUORUM", "a0_a6_disposition": "PREPARED", "closure_evidence_path": g1a_evidence[fid], "admission_effect": "BLOCK_G1A_UNTIL_FINAL_QUORUM"})
    elif fid in downstream_ids:
        out.update({"technical_status": "OPEN_DOWNSTREAM", "a0_a6_disposition": "APPROVED_DEFERRED_HOLD_REGISTERED", "admission_effect": "NO_S01_BLOCK_REACTIVATES_AT_NAMED_GATE"})
    elif fid in {"AUTH-008", "RBT-A0-010"}:
        out.update({"technical_status": "SUPERSEDED_PENDING_G1A_PASS", "a0_a6_disposition": "OWNER_STANDING_DELEGATION_REPLACES_SINGLE_S01_TEXT", "closure_evidence_path": "B51R1_G1B_STANDING_SESSION_ADMISSION.json", "admission_effect": "BLOCK_G1B_UNTIL_G1A_PASS"})
    disposition_rows.append(out)

new_findings = [
    {"finding_id": "AUT-QUORUM-001", "blocks_gate": "G1A", "defer_to_gate": "NONE", "closure_kind": "DISTINCT_AGENT_QUORUM_REQUIRED", "technical_status": "PENDING_FINAL_QUORUM", "a0_a6_disposition": "STRICT_UNION_RULE_ADOPTED", "closure_evidence_path": "B51R1_G1A_MULTIAGENT_QUORUM_RECEIPT.json", "admission_effect": "BLOCK_G1A_UNTIL_FINAL_QUORUM"},
    {"finding_id": "AUT-POOL-001", "blocks_gate": "G1A", "defer_to_gate": "NONE", "closure_kind": "BOUNDED_SESSION_POOL_LEDGER_REQUIRED", "technical_status": "CLOSURE_ASSET_PREPARED_PENDING_FINAL_QUORUM", "a0_a6_disposition": "20_TOTAL_18_PRIMARY_2_RECOVERY", "closure_evidence_path": "B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json", "admission_effect": "BLOCK_G1A_UNTIL_FINAL_QUORUM"},
    {"finding_id": "AUT-GATE-001", "blocks_gate": "G1A", "defer_to_gate": "NONE", "closure_kind": "SYMBOLIC_GATE_TO_HASHED_RECEIPT_MAPPING_REQUIRED", "technical_status": "CLOSURE_ASSET_PREPARED_PENDING_FINAL_QUORUM", "a0_a6_disposition": "GATE_TRANSITION_MAP_V2_PREPARED", "closure_evidence_path": rel(gate_map_v2_path), "admission_effect": "BLOCK_G1A_UNTIL_FINAL_QUORUM"},
]
disposition_rows.extend(new_findings)
disposition_path = CLOSURE / "B51R1_AUTONOMOUS_FINDING_DISPOSITION_REGISTER_V2.csv"
write_csv(disposition_path, list(disposition_rows[0].keys()), disposition_rows)

claim_rows = [
    {"claim_id": "AUT-CLM-001", "claim": "Owner standing delegation", "status": "PASS", "evidence": "B51R1_AUTONOMOUS_STANDING_DELEGATION_RECEIPT.json", "allowed_wording": "PASS_OWNER_STANDING_DELEGATION_EFFECTIVE", "forbidden_extrapolation": "NON_DELEGABLE_L4_AUTHORIZED"},
    {"claim_id": "AUT-CLM-002", "claim": "Datum authority", "status": "PASS_CANDIDATE_SCOPE", "evidence": "B51R1_G1A_DATUM_MACHINE_RATIFICATION.yaml", "allowed_wording": "DATUM_MACHINE_RATIFIED_FOR_ISOLATED_CANDIDATE", "forbidden_extrapolation": "FLIGHT_INTERFACE_RELEASE"},
    {"claim_id": "AUT-CLM-003", "claim": "Feature naming and transform ownership", "status": "PASS_OFFLINE_REFROZEN", "evidence": "B51R1_G1A_FEATURE_NAMING_MACHINE_RATIFICATION.yaml", "allowed_wording": "JOINT_SIDE_EXPLICIT_V2_REFROZEN", "forbidden_extrapolation": "NATIVE_FEATURES_EXIST"},
    {"claim_id": "AUT-CLM-004", "claim": "Acceptance tolerance authority", "status": "PASS_AUTHORING_SCOPE", "evidence": "B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml", "allowed_wording": "CAD_URDF_NUMERICAL_TOLERANCES_MACHINE_RATIFIED", "forbidden_extrapolation": "FORMAL_T005_OR_MANUFACTURING_TOLERANCE_PASS"},
    {"claim_id": "AUT-CLM-005", "claim": "Stage A lockfile quarantine", "status": "PASS", "evidence": "B51R1_STAGE_A_LOCKFILE_QUARANTINE_RECEIPT.json", "allowed_wording": "HASH_AND_QUARANTINE_NOT_DELETE_STAGE_A_UNCHANGED", "forbidden_extrapolation": "STAGE_A_MODIFIED_OR_REPAIRED"},
    {"claim_id": "AUT-CLM-006", "claim": "G1A", "status": "HOLD_PENDING_FINAL_QUORUM", "evidence": "B51R1_G1A_MULTIAGENT_QUORUM_RECEIPT.json", "allowed_wording": "G1A_CLOSURE_ASSETS_PREPARED", "forbidden_extrapolation": "G1A_PASS"},
    {"claim_id": "AUT-CLM-007", "claim": "G1B/S01", "status": "NOT_AUTHORIZED", "evidence": "B51R1_G1B_STANDING_SESSION_ADMISSION.json", "allowed_wording": "G1B_PENDING_G1A_PASS", "forbidden_extrapolation": "SOLIDWORKS_LAUNCH_AUTHORIZED"},
    {"claim_id": "AUT-CLM-008", "claim": "Native CAD", "status": "NOT_CREATED", "evidence": "B51R1_PHASE2_CURRENT_GATE_COMPOSITION.json", "allowed_wording": "FINAL_SKELETON_ABSENT_CARRIERS_0_OF_10", "forbidden_extrapolation": "NATIVE_ARTICULATION_ACCEPTED"},
    {"claim_id": "AUT-CLM-009", "claim": "Mechanical design baseline", "status": "ENGINEERING_CANDIDATE", "evidence": rel(design_yaml_path), "allowed_wording": "MECHANICAL_DESIGN_CANDIDATE_BASELINE_CREATED", "forbidden_extrapolation": "MANUFACTURING_READY_OR_FINAL_H9"},
]
claim_path = CLOSURE / "B51R1_AUTONOMOUS_CLAIM_MATRIX_V2.csv"
write_csv(claim_path, list(claim_rows[0].keys()), claim_rows)

manifest_path = CLOSURE / "B51R1_AUTONOMOUS_EXPECTED_ARTIFACT_MANIFEST_V3.csv"
manifest_rows = []
for idx, (sid, purpose, after) in enumerate(sessions, start=1):
    manifest_rows.append({"artifact_id": f"SESSION-{sid}", "gate": sid, "artifact_path_or_pattern": f"07_VERIFICATION/AUTONOMOUS/{sid}/*", "required_count": "1+", "current_count": "0", "status": "FUTURE_REQUIRED", "hash_policy": "EACH_FILE_SHA256", "claim_credit": purpose})
for artifact_id, path, gate in [
    ("G1A-DATUM", datum_path, "G1A"), ("G1A-NAMING", naming_path, "G1A"),
    ("G1A-TOLERANCE", tolerance_path, "G1A"), ("G1A-ALIAS", alias_path, "G1A"),
    ("G1A-TRANSFORMS", transform_register_path, "G1A"), ("G1A-DISPOSITION", disposition_path, "G1A"),
    ("G1A-POOL", session_ledger_path, "G1A"), ("G1A-GATE-MAP", gate_map_v2_path, "G1A"),
    ("G1A-LOCK-RECEIPT", lock_receipt_path, "G1A"), ("DESIGN-BASELINE", design_yaml_path, "W00"),
]:
    manifest_rows.append({"artifact_id": artifact_id, "gate": gate, "artifact_path_or_pattern": rel(path), "required_count": "1", "current_count": "1", "status": "CURRENT_PREPARED", "hash_policy": sha256(path), "claim_credit": "CANDIDATE_SCOPE_ONLY"})
manifest_rows.extend([
    {"artifact_id": "G1A-INPUT-LOCK", "gate": "G1A", "artifact_path_or_pattern": "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json", "required_count": "1", "current_count": "0", "status": "GENERATED_AFTER_MANIFEST", "hash_policy": "HASH_DEFERRED_TO_CLOSURE_INDEX", "claim_credit": "G1A_HASH_LOCK"},
    {"artifact_id": "G1A-RECEIPT", "gate": "G1A", "artifact_path_or_pattern": "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_G1A_MACHINE_RATIFICATION_RECEIPT.json", "required_count": "1", "current_count": "0", "status": "FINAL_QUORUM_REQUIRED", "hash_policy": "HASH_DEFERRED_TO_CLOSURE_INDEX", "claim_credit": "G1A_PASS"},
    {"artifact_id": "G1B-ADMISSION", "gate": "G1B", "artifact_path_or_pattern": "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_G1B_STANDING_SESSION_ADMISSION.json", "required_count": "1", "current_count": "0", "status": "AFTER_G1A_PASS", "hash_policy": "HASH_DEFERRED_TO_CLOSURE_INDEX", "claim_credit": "S01_ADMISSION"},
])
write_csv(manifest_path, list(manifest_rows[0].keys()), manifest_rows)

# Refrozen input lock: immutable inputs and executable V2 contracts only. It deliberately
# excludes itself and every downstream receipt that references it.
v1_lock_path = PHASE2A_PACKAGE / "B51R1_PHASE2A_INPUT_LOCK.json"
v1_lock = json.loads(v1_lock_path.read_text(encoding="utf-8"))
locked_items = []
superseded_ids = {
    "MECHANICAL_ENGINEERING_DIRECTIVE",
    "PHASE2_EXECUTION_MAP",
    "CARRIER_ARCHITECTURE_CONTRACT",
    "URDF_CARRIER_FRAME_MAPPING",
    "CARRIER_REGISTER",
    "NATIVE_JOINT_REGISTER",
    "NATIVE_DRIVER_MAPPING",
}
for item in v1_lock["locked_inputs"]:
    copied = deepcopy(item)
    copied["source_lock"] = "PHASE2A_INPUT_LOCK_V1"
    if item["id"] in superseded_ids:
        copied["effective_mode"] = "HISTORICAL_NONEXECUTABLE_SUPERSEDED_BY_AUTONOMOUS_V2"
    else:
        copied["effective_mode"] = "ACTIVE_READ_ONLY_SOURCE"
    locked_items.append(copied)

additional_paths = [
    ("AUTONOMOUS_INTAKE_ZIP", autonomous_zip, "OWNER_STANDING_DELEGATION_PACKAGE", "ACTIVE_AUTHORITY"),
    ("AUTONOMOUS_CHARTER", charter_path, "STANDING_DELEGATION_CHARTER", "ACTIVE_AUTHORITY"),
    ("AUTONOMOUS_G1A_ADJUDICATION", AUTONOMOUS_CONTENTS / "B51R1_G1A_AUTONOMOUS_ADJUDICATION.yaml", "G1A_TECHNICAL_DECISION", "ACTIVE_AUTHORITY"),
    ("AUTONOMOUS_MASTER_PROMPT", AUTONOMOUS_CONTENTS / "CODEX_B51R1_AUTONOMOUS_LOOP_MULTIAGENT_MASTER_PROMPT.md", "EXECUTION_POLICY", "ACTIVE_AUTHORITY"),
    ("AUTONOMOUS_FINDING_POLICY", AUTONOMOUS_CONTENTS / "B51R1_AUTONOMOUS_FINDING_DISPOSITION_POLICY.csv", "FINDING_POLICY", "ACTIVE_AUTHORITY"),
    ("AUTONOMOUS_SESSION_PLAN_SOURCE", AUTONOMOUS_CONTENTS / "B51R1_AUTONOMOUS_SESSION_PLAN.yaml", "HISTORICAL_SESSION_PLAN_SOURCE", "SUPERSEDED_BY_OPERATIONAL_V2_ORDER"),
    ("STANDING_DELEGATION_DIRECTIVE", directive_path, "OWNER_DIRECTIVE", "ACTIVE_AUTHORITY"),
    ("STANDING_DELEGATION_ACTIVATION", activation_receipt_path, "AUTHORITY_ACTIVATION", "ACTIVE_AUTHORITY"),
    ("G1A_DATUM_AUTHORITY", datum_path, "RATIFIED_DATUM", "ACTIVE_EXECUTION_AUTHORITY"),
    ("G1A_NAMING_AUTHORITY", naming_path, "RATIFIED_NAMING", "ACTIVE_EXECUTION_AUTHORITY"),
    ("G1A_TOLERANCE_AUTHORITY", tolerance_path, "RATIFIED_TOLERANCE", "ACTIVE_EXECUTION_AUTHORITY"),
    ("G1A_ALIAS_REGISTER", alias_path, "READ_ONLY_ALIAS", "NONEXECUTABLE_ALIAS"),
    ("G1A_EXPANDED_FEATURE_REGISTER", expanded_path, "V2_FEATURE_REGISTER", "ACTIVE_EXECUTION_AUTHORITY"),
    ("CARRIER_MAP_V2", carrier_map_v2_path, "V2_CARRIER_MAP", "ACTIVE_EXECUTION_AUTHORITY"),
    ("CARRIER_REGISTER_V2", carrier_register_v2_path, "V2_CARRIER_REGISTER", "ACTIVE_EXECUTION_AUTHORITY"),
    ("URDF_CARRIER_MAPPING_V2", mapping_v2_path, "V2_FRAME_MAPPING", "ACTIVE_EXECUTION_AUTHORITY"),
    ("NATIVE_JOINT_REGISTER_V2", joint_register_v2_path, "V2_JOINT_REGISTER", "ACTIVE_EXECUTION_AUTHORITY"),
    ("NATIVE_DRIVER_MAPPING_V2", driver_v2_path, "V2_DRIVER_MAPPING", "ACTIVE_EXECUTION_AUTHORITY"),
    ("JOINT_SIDE_TRANSFORM_REGISTER_V2", transform_register_path, "V2_OWNER_LOCAL_TRANSFORMS", "ACTIVE_EXECUTION_AUTHORITY"),
    ("CARRIER_ARCHITECTURE_CONTRACT_V2", architecture_v2_path, "V2_ARCHITECTURE", "ACTIVE_EXECUTION_AUTHORITY"),
    ("SESSION_PLAN_V2", session_plan_v2_path, "CORRECTED_OPERATIONAL_SESSION_PLAN", "ACTIVE_EXECUTION_AUTHORITY"),
    ("GATE_TRANSITION_MAP_V2", gate_map_v2_path, "SYMBOL_TO_HASHED_RECEIPT_MAP", "ACTIVE_EXECUTION_AUTHORITY"),
    ("MECHANICAL_DESIGN_BASELINE_YAML", design_yaml_path, "CANDIDATE_MECHANICAL_DESIGN", "ACTIVE_CANDIDATE_BASELINE"),
    ("MECHANICAL_DESIGN_BASELINE_MD", design_md_path, "CANDIDATE_MECHANICAL_DESIGN_NARRATIVE", "ACTIVE_CANDIDATE_BASELINE"),
    ("STAGE_A_LOCKFILE_QUARANTINE_RECEIPT", lock_receipt_path, "REVERSIBLE_FILE_DISPOSITION", "ACTIVE_EVIDENCE"),
    ("QUARANTINED_STAGE_A_LOCKFILE", quarantine_lock, "RECOVERABLE_QUARANTINED_TEMPORARY_FILE", "QUARANTINED"),
    ("CURRENT_GATE_COMPOSITION", current_gate_path, "CURRENT_STATUS_COMPOSITION", "ACTIVE_EVIDENCE"),
    ("FINDING_DISPOSITION_V2", disposition_path, "GATE_SCOPED_FINDING_POLICY", "ACTIVE_EVIDENCE"),
    ("CLAIM_MATRIX_V2", claim_path, "CLAIM_BOUNDARY", "ACTIVE_EVIDENCE"),
    ("EXPECTED_ARTIFACT_MANIFEST_V3", manifest_path, "ARTIFACT_CONTRACT", "ACTIVE_EXECUTION_AUTHORITY"),
    ("SESSION_POOL_LEDGER", session_ledger_path, "BOUNDED_VISIBLE_SESSION_LEDGER", "ACTIVE_EXECUTION_AUTHORITY"),
    ("S00_WORKSET_ZIP", CANDIDATE / "09_DELIVERY" / "B51R1_PHASE2_S00_G1_REVIEW_WORKSET_20260801.zip", "PRIOR_S00_EVIDENCE", "READ_ONLY_HASH_GUARD"),
    ("CURRENT_PHASE1_GATE", CANDIDATE / "07_VERIFICATION" / "B51R1_PHASE1_INTERMEDIATE_GATE_20260729.json", "CURRENT_PHASE1_GATE", "READ_ONLY_HASH_GUARD"),
]
for item_id, path, role, mode in additional_paths:
    rec = file_record(path, role, mode)
    rec["id"] = item_id
    locked_items.append(rec)

input_lock_path = CLOSURE / "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json"
input_lock = {
    "schema": "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN",
    "generated_at": now(),
    "status": "PASS_HASH_LOCKED_PENDING_FINAL_DISTINCT_AGENT_QUORUM",
    "candidate_root": str(CANDIDATE),
    "authority_type": "OWNER_STANDING_DELEGATION",
    "delegation_charter_sha256": CHARTER_SHA,
    "locked_item_count": len(locked_items),
    "minimum_required_count": 35,
    "all_paths_bytes_hash_non_null": all(x.get("path") and x.get("bytes") is not None and x.get("sha256") for x in locked_items),
    "self_included": False,
    "downstream_receipts_included": False,
    "hash_graph": "L0_IMMUTABLE_TO_L1_RATIFIED_TO_L2_CONTROL_TO_THIS_L3_LOCK_NO_BACK_REFERENCES",
    "locked_items": locked_items,
    "original_phase2a_v1_lock": file_record(v1_lock_path, "IMMUTABLE_V1_LOCK_HISTORICAL"),
    "claim_limit": "INPUTS_AND_OPERATIONAL_V2_FILES_HASH_LOCKED_FINAL_G1A_QUORUM_STILL_REQUIRED",
}
write_json(input_lock_path, input_lock)
write_text(CLOSURE / "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json.sha256", sha256(input_lock_path), newline=True)

readme = f"""# B51R1 Autonomous G1A Closure Workset

Status: `CLOSURE_ASSETS_PREPARED_PENDING_FINAL_DISTINCT_AGENT_QUORUM`

This directory is separate from and does not modify the prior 19-file S00/G1
workset or the immutable 11-file Phase2A start package.

Prepared evidence includes owner standing-delegation activation, machine-ratified
datum/naming/tolerance, JOINT_SIDE_EXPLICIT_V2 operational contracts, Stage A
lockfile quarantine receipt, 20-session pool ledger, corrected G8a→structure→G8b
session order, gate-to-receipt mapping, a concrete mechanical candidate baseline,
and a non-circular V2 input lock.

SolidWorks remains prohibited until the final distinct-agent quorum receipt closes
all current-Gate Critical/High findings and G1B standing admission is issued.

Input lock SHA-256: `{sha256(input_lock_path)}`
"""
write_text(CLOSURE / "README.md", readme)

summary = {
    "closure_dir": str(CLOSURE),
    "files_created_in_closure": len([p for p in CLOSURE.rglob("*") if p.is_file()]),
    "operational_v2_files_created": [rel(p) for p in [carrier_map_v2_path, carrier_register_v2_path, mapping_v2_path, joint_register_v2_path, driver_v2_path, architecture_v2_path, transform_register_path, session_plan_v2_path, gate_map_v2_path, design_yaml_path, design_md_path]],
    "input_lock_sha256": sha256(input_lock_path),
    "locked_item_count": len(locked_items),
    "status": "PREPARED_PENDING_FINAL_DISTINCT_AGENT_QUORUM",
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
