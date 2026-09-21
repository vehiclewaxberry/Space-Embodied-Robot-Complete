#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the offline V5 digital-thread seed and the current TOOLING_HOLD receipt.

This generator is deliberately COM-free and SolidWorks-free.  It reads the
existing V5 write-once receipts and the frozen F3R2 digital-thread files, then
writes only inside the fixed V5 run root:

* 09_digital_thread/V5_FRAME_MAPPING.yaml
* 09_digital_thread/V5_LINK_COMPONENT_MAPPING.csv
* 09_digital_thread/V5_COLLISION_ASSET_MANIFEST.csv
* 09_digital_thread/V5_MASS_BOUNDARY.yaml  (byte copy of the pinned seed)
* 09_digital_thread/V5_ACTION_MASK_RULES.yaml
* 09_digital_thread/V5_MECHANICAL_STATE_MACHINE.yaml
* 13_validation/V5_TOOLING_HOLD_<timestamp>.json

No CAD file is opened, created, saved or closed.  No protected asset is read
for modification.  The generator never promotes a candidate pose or camera
model to authority.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
RUN_ROOT = ENGINEERING / "F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
VALIDATION = RUN_ROOT / "13_validation"
DIGITAL_DIR = RUN_ROOT / "09_digital_thread"

LOOP1_RECEIPT = VALIDATION / "V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
LOOP1A_RECEIPT = VALIDATION / "V5_LOOP1A_SUBASSEMBLY_RECEIPT.json"
MASS_BOUNDARY_SEED = RUN_ROOT / "06_mass_properties/V5_MASS_BOUNDARY.yaml"
F3R2_COLLISION_MANIFEST = (
    ENGINEERING
    / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/10_digital_thread/F3R2_COLLISION_ASSET_MANIFEST.csv"
)
F3R2_FRAME_MAPPING = (
    ENGINEERING
    / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/10_digital_thread/F3R2_FRAME_MAPPING.yaml"
)

ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
TOP_NAME = "SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM"

VENDOR_LINK_PARTS = (
    ENGINEERING
    / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/B601_ARM_B51_COPY/inputs/vendor_link_parts"
)
F3R2_MESH_DEPLOYED = (
    ENGINEERING
    / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_DEPLOYED"
)


def posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_fact(path: Path) -> Dict[str, Any]:
    return {
        "path": posix(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_text_once(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_csv_once(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def loop1_parts() -> List[Dict[str, Any]]:
    receipt = load_json(LOOP1_RECEIPT)
    parts = []
    for item in receipt.get("native_parts", []):
        target = Path(item["target"]["path"])
        source_step = Path(item["source"]["path"])
        source_stl = source_step.with_suffix(".stl")
        parts.append(
            {
                "role": item.get("role", ""),
                "component_name": target.stem,
                "native_path": target,
                "native_sha256": item["target"]["sha256"],
                "step_path": source_step,
                "stl_path": source_stl if source_stl.is_file() else None,
            }
        )
    return parts


def loop1a_assemblies() -> List[Dict[str, Any]]:
    receipt = load_json(LOOP1A_RECEIPT)
    rows = []
    for item in receipt.get("subassemblies", []):
        target = Path(item["target"]["path"])
        rows.append(
            {
                "component_name": target.stem,
                "native_path": target,
                "native_sha256": item["target"]["sha256"],
            }
        )
    diamond = receipt.get("diamond_locator")
    if diamond:
        target = Path(diamond["path"])
        rows.append(
            {
                "component_name": target.stem,
                "native_path": target,
                "native_sha256": diamond["save"]["sha256"],
            }
        )
    return rows


def loop1b_parts() -> List[Dict[str, Any]]:
    rows = []
    for checkpoint in sorted(VALIDATION.glob("V5_LOOP1B_ARTIFACT_*.json")):
        payload = load_json(checkpoint)
        target = payload.get("target")
        if not target:
            continue
        path = Path(target["path"])
        rows.append(
            {
                "component_name": path.stem,
                "native_path": path,
                "native_sha256": target["sha256"],
            }
        )
    return rows


def donor_arm_link(link: str) -> Dict[str, Any]:
    native = VENDOR_LINK_PARTS / f"B51_REF_{link}_LINKLOCAL.SLDPRT"
    mesh = F3R2_MESH_DEPLOYED / f"B51_REF_{link}_LINKLOCAL.stl"
    return {
        "native_path": native if native.is_file() else None,
        "native_sha256": sha256(native) if native.is_file() else "",
        "mesh_path": mesh if mesh.is_file() else None,
    }


def read_f3r2_collision_manifest() -> List[Dict[str, str]]:
    rows = []
    with F3R2_COLLISION_MANIFEST.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            rows.append({key: (value or "") for key, value in row.items()})
    return rows


def frame_mapping_yaml() -> str:
    return f"""schema: F3R2_V5_FRAME_MAPPING_V1
authority: "V5 frame mapping is an engineering mapping seed, not an optical calibration or flight authority"
root_frame: spacecraft_assembly_frame
units: "mm, radians"
top_assembly: {TOP_NAME}
levels:
  L0: accepted_B601_URDF_IMMUTABLE_DYNAMICS_TRUTH
  L1: native_SolidWorks_V5_components
  L2: simulation_visual_collision_mesh_assets
  L3: donor_or_reference_assets
accepted_urdf_sha256: {ACCEPTED_URDF_SHA256}
frames:
  spacecraft_assembly_frame:
    parent: null
    definition: "top-level assembly origin of {TOP_NAME}"
  arm_base_frame:
    parent: spacecraft_assembly_frame
    transform_mm_rows:
      -
        - 0.0
        - 0.0
        - 1.0
        - 208.0
      -
        - 0.422618
        - 0.906308
        - 0.0
        - 0.0
      -
        - -0.906308
        - 0.422618
        - 0.0
        - 0.0
      -
        - 0.0
        - 0.0
        - 0.0
        - 1.0
    equals: "URDF base_link frame"
    clock_deg: 25.0
    source: "F3R1_TOP_INTEGRATION_REPORT.json arm_mount_transform_mm"
  stage_a_mount_frame:
    parent: spacecraft_assembly_frame
    definition: "B601 4 x M4-class 64 x 64 mm square pattern origin; native face measurement pending"
  stage_b_mount_frame:
    parent: spacecraft_assembly_frame
    definition: "Stage-B 4 x M6 140 x 140 mm load-bridge pattern origin; native counterpart measurement pending"
  hinge_axis_left:
    parent: spacecraft_assembly_frame
    axis:
      - 1.0
      - 0.0
      - 0.0
    point_mm:
      - -61.0
      - 143.15
      - 0.0
    source: "B-rep probe of Hinge_Pin_Left; V5 native hinge assembly re-measurement pending"
  hinge_axis_right:
    parent: spacecraft_assembly_frame
    axis:
      - 1.0
      - 0.0
      - 0.0
    point_mm:
      - -61.0
      - -143.15
      - 0.0
    source: "B-rep probe of Hinge_Pin_Right; V5 native hinge assembly re-measurement pending"
  camera_optical_frame:
    parent: link6
    status: PROPOSED_NOT_CALIBRATED
    source: "F3R2_CAMERA_HARNESS_GRIPPER.json; CAMERA_MODEL_SELECTION_HOLD"
urdf_link_frames:
  base_link: "URDF-defined, see accepted arm_b601_v1.urdf"
  link1: "URDF-defined, see accepted arm_b601_v1.urdf"
  link2: "URDF-defined, see accepted arm_b601_v1.urdf"
  link3: "URDF-defined, see accepted arm_b601_v1.urdf"
  link4: "URDF-defined, see accepted arm_b601_v1.urdf"
  link5: "URDF-defined, see accepted arm_b601_v1.urdf"
  link6: "URDF-defined, see accepted arm_b601_v1.urdf"
  gripper_link: "URDF-defined, see accepted arm_b601_v1.urdf"
  gripper_left: "URDF-defined prismatic finger frame; native V5 gripper assembly pending"
  gripper_right: "URDF-defined prismatic finger frame; native V5 gripper assembly pending"
native_component_frames:
  B601_INTERFACE_STAGE_A_REV_B2: stage_a_mount_frame
  B601_LOAD_ADAPTER_STAGE_B_REV_B2: stage_b_mount_frame
  LEFT_WING_PANEL_PHYSICAL: hinge_axis_left
  RIGHT_WING_PANEL_PHYSICAL: hinge_axis_right
  SERVICE_CAMERA_ENVELOPE: camera_optical_frame
  B601_OD9_STATIC_HARNESS_ENVELOPE: spacecraft_assembly_frame
  ARM_HDRM_60MM_MOUNT_ENVELOPE: spacecraft_assembly_frame
  ARM_HDRM_RELEASE_SWEEP_ENVELOPE: spacecraft_assembly_frame
"""


def link_component_mapping_rows() -> List[Dict[str, Any]]:
    links = [
        ("base_link", None, "base_link", "arm_base_frame", None),
        ("link1", "joint1", "link1", "link1_frame", None),
        ("link2", "joint2", "link2", "link2_frame", None),
        ("link3", "joint3", "link3", "link3_frame", None),
        ("link4", "joint4", "link4", "link4_frame", None),
        ("link5", "joint5", "link5", "link5_frame", None),
        ("link6", "joint6", "link6", "link6_frame", "camera_optical_frame"),
        ("gripper_link", "gripper_joint", "gripper_detail", "gripper_link_frame", "camera_optical_frame"),
    ]
    rows = []
    for link, joint, suffix, control_frame, camera_frame in links:
        donor = donor_arm_link(suffix)
        mesh = donor["mesh_path"]
        rows.append(
            {
                "urdf_link": link,
                "urdf_joint": joint or "",
                "component_name2": f"B51_REF_{suffix}_LINKLOCAL",
                "native_path": posix(donor["native_path"]) if donor["native_path"] else "",
                "native_sha256": donor["native_sha256"],
                "step_path": "",
                "visual_mesh_path": posix(mesh) if mesh else "",
                "collision_mesh_path": posix(mesh) if mesh else "",
                "control_frame": control_frame,
                "camera_frame": camera_frame or "",
                "authority_level": "L3_DONOR_REFERENCE_L0_URDF_LINK",
                "status": "MAPPED_FROM_FROZEN_DONOR",
                "notes": "native V5 top assembly references the protected B51 donor; gripper split native parts pending Loop1C0",
            }
        )
    for link in ("gripper_left", "gripper_right"):
        rows.append(
            {
                "urdf_link": link,
                "urdf_joint": "gripper_joint1" if link == "gripper_left" else "gripper_joint2",
                "component_name2": "B601_GRIPPER_LEFT_FINGER" if link == "gripper_left" else "B601_GRIPPER_RIGHT_FINGER",
                "native_path": "",
                "native_sha256": "",
                "step_path": "",
                "visual_mesh_path": posix(F3R2_MESH_DEPLOYED / f"B51_REF_gripper_detail_LINKLOCAL.stl"),
                "collision_mesh_path": posix(F3R2_MESH_DEPLOYED / f"B51_REF_gripper_detail_LINKLOCAL.stl"),
                "control_frame": f"{link}_frame",
                "camera_frame": "camera_optical_frame",
                "authority_level": "L1_NATIVE_PENDING_LOOP1C0",
                "status": "PENDING_NATIVE_SAVE_BODIES_AND_PRISMATIC_MATES",
                "notes": "L0 URDF mass/inertia unchanged; native V5 finger parts not yet created",
            }
        )
    for item in loop1_parts():
        rows.append(
            {
                "urdf_link": "",
                "urdf_joint": "",
                "component_name2": item["component_name"],
                "native_path": posix(item["native_path"]),
                "native_sha256": item["native_sha256"],
                "step_path": posix(item["step_path"]),
                "visual_mesh_path": posix(item["stl_path"]) if item["stl_path"] else "",
                "collision_mesh_path": posix(item["stl_path"]) if item["stl_path"] else "",
                "control_frame": "spacecraft_assembly_frame",
                "camera_frame": "camera_optical_frame" if "CAMERA" in item["component_name"].upper() else "",
                "authority_level": "L1_NATIVE",
                "status": "MAPPED_LOOP1_IMPORT_PASS",
                "notes": "native part identity hash-bound by V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json",
            }
        )
    for item in loop1a_assemblies():
        rows.append(
            {
                "urdf_link": "",
                "urdf_joint": "",
                "component_name2": item["component_name"],
                "native_path": posix(item["native_path"]),
                "native_sha256": item["native_sha256"],
                "step_path": "",
                "visual_mesh_path": "",
                "collision_mesh_path": "",
                "control_frame": "spacecraft_assembly_frame",
                "camera_frame": "",
                "authority_level": "L1_NATIVE",
                "status": "MAPPED_LOOP1A_SUBASSEMBLY_PASS",
                "notes": "subassembly cold-reopen PASS bound by V5_LOOP1A_SUBASSEMBLY_RECEIPT.json",
            }
        )
    for item in loop1b_parts():
        rows.append(
            {
                "urdf_link": "",
                "urdf_joint": "",
                "component_name2": item["component_name"],
                "native_path": posix(item["native_path"]),
                "native_sha256": item["native_sha256"],
                "step_path": "",
                "visual_mesh_path": "",
                "collision_mesh_path": "",
                "control_frame": "hinge_axis_left" if item["component_name"].upper().startswith("LEFT") else "hinge_axis_right",
                "camera_frame": "",
                "authority_level": "L1_NATIVE",
                "status": "MAPPED_LOOP1B_ARTIFACT_CHECKPOINT_PASS",
                "notes": "donor-isolated native part checkpoint; true-hinge assembly still pending",
            }
        )
    return rows


def collision_asset_rows() -> List[Dict[str, Any]]:
    rows = []
    for row in read_f3r2_collision_manifest():
        role = row.get("role", "")
        authority_level = "L3_REFERENCE_ONLY" if "REFERENCE_ONLY" in role.upper() else "L2_MESH"
        rows.append(
            {
                "asset_id": row.get("asset", ""),
                "component_name2": row.get("asset", ""),
                "native_path": "",
                "native_sha256": "",
                "collision_class": role,
                "authority_level": authority_level,
                "path": row.get("path", ""),
                "role": role,
                "urdf_link": row.get("urdf_link", ""),
                "triangles": row.get("triangles", ""),
                "deflection_mm": row.get("deflection_mm", ""),
                "frame": row.get("frame", ""),
                "posed_by": row.get("posed_by", ""),
                "authoritative": row.get("authoritative", "False"),
                "authority_note": row.get("authority_note", ""),
            }
        )
    for item in loop1_parts():
        upper = item["component_name"].upper()
        if "STAGE" in upper or "ADAPTER" in upper:
            collision_class = "ARM_MOUNT_INTERFACE"
        elif "G07" in upper or "G08" in upper or "MID" in upper:
            collision_class = "STOW_SUPPORT"
        elif "HDRM" in upper:
            collision_class = "ARM_HDRM_ENVELOPE"
        elif "CAMERA" in upper or "HARNESS" in upper:
            collision_class = "CAMERA_HARNESS_ENVELOPE"
        elif "CLEVIS" in upper:
            collision_class = "WING_ROOT_INTERFACE"
        else:
            collision_class = "EXTERNAL_MECHANICAL"
        rows.append(
            {
                "asset_id": item["component_name"],
                "component_name2": item["component_name"],
                "native_path": posix(item["native_path"]),
                "native_sha256": item["native_sha256"],
                "collision_class": collision_class,
                "authority_level": "L1_NATIVE",
                "path": posix(item["native_path"]),
                "role": collision_class,
                "urdf_link": "",
                "triangles": "",
                "deflection_mm": "",
                "frame": "spacecraft_assembly_frame",
                "posed_by": "V5_native_import",
                "authoritative": "True_for_native_identity",
                "authority_note": "native part identity is L1; native interference/clearance still pending top-assembly Loop2",
            }
        )
    for item in loop1a_assemblies():
        rows.append(
            {
                "asset_id": item["component_name"],
                "component_name2": item["component_name"],
                "native_path": posix(item["native_path"]),
                "native_sha256": item["native_sha256"],
                "collision_class": "NATIVE_SUBASSEMBLY",
                "authority_level": "L1_NATIVE",
                "path": posix(item["native_path"]),
                "role": "NATIVE_SUBASSEMBLY",
                "urdf_link": "",
                "triangles": "",
                "deflection_mm": "",
                "frame": "spacecraft_assembly_frame",
                "posed_by": "V5_loop1a",
                "authoritative": "True_for_native_identity",
                "authority_note": "native subassembly identity; top-context interference pending",
            }
        )
    return rows


def action_mask_yaml() -> str:
    return f"""schema: F3R2_V5_ACTION_MASK_RULES_V1
authority: "V5 action mask is an engineering control-boundary seed; it is not a flight or mission authority"
top_assembly: {TOP_NAME}
accepted_urdf_sha256: {ACCEPTED_URDF_SHA256}
levels:
  L0: accepted_B601_URDF
  L1: native_SolidWorks_V5
  L2: simulation_visual_collision_mesh
  L3: donor_reference_assets
purpose: "what an embodied policy is mechanically allowed to command given current V5 evidence"
joint_limits_deg:
  joint1:
    - -160.428183
    - 160.428183
  joint2:
    - -179.908748
    - 0.0
  joint3:
    - -179.908748
    - 0.0
  joint4:
    - -107.143108
    - 89.954374
  joint5:
    - -89.954374
    - 89.954374
  joint6:
    - -179.908748
    - 179.908748
hard_rules:
  -
    id: AM-1
    rule: "never command outside the accepted URDF joint limits"
    enforcement: "clamp and reject, fail-closed"
  -
    id: AM-2
    rule: "keep >= 3.0 deg from any joint limit during autonomous motion"
    enforcement: "reject the action"
  -
    id: AM-3
    rule: "only the V5 authorized runtime poses and swept segments between them are autonomous"
    authorised_poses:
      - Q_DEPLOYED_HOME
      - Q_RELEASE_CLEAR
      - Q_SERVICE_READY
    enforcement: "reject unlisted targets"
  -
    id: AM-4
    rule: "G07/G08/Mid are native V5 supports but preload/bench calibration and native contact validation remain HOLD"
    enforcement: "no contact-based state estimation from them until native validation"
  -
    id: AM-5
    rule: "never treat HDRM/camera/harness envelope bodies as physical collision truth"
    enforcement: "excluded from the runtime collision set; functional envelope only"
  -
    id: AM-6
    rule: "gripper OPEN/PREGRASP/CLOSED require native prismatic mates and native minimum-distance evidence; HOLDING is a CLOSED alias without actuator authority"
    enforcement: "no autonomous jaw opening near structure until native gripper assembly passes"
  -
    id: AM-7
    rule: "STOW, HDRM release and wing deployment are not autonomous runtime states"
    enforcement: "ground command only"
  -
    id: AM-8
    rule: "SERVICE_CAMERA is UNSELECTED; no vision-based autonomous grasp or docking until camera model and calibration authority"
    enforcement: "camera-gated tasks remain HOLD"
clearance_budget_mm:
  target: 5.0
  mesh_tier_measured_at_home: 74.05
  tessellation_deflection: 0.5
  native_revalidation: REQUIRED_AFTER_V5_TOP_ASSEMBLY
"""


def state_machine_yaml() -> str:
    return f"""schema: F3R2_V5_MECHANICAL_STATE_MACHINE_V1
authority: "V5 state machine is an engineering seed; no state beyond the three runtime inputs is promoted by CAD"
top_assembly: {TOP_NAME}
accepted_urdf_sha256: {ACCEPTED_URDF_SHA256}
levels:
  L0: accepted_B601_URDF
  L1: native_SolidWorks_V5
  L2: simulation_visual_collision_mesh
  L3: donor_reference_assets
runtime_states:
  -
    state: DEPLOYED_NOMINAL
    arm_pose: Q_DEPLOYED_HOME
    wings: "both deployed via native hinge configurations"
    autonomous: true
  -
    state: SERVICE_STAGING
    arm_pose: Q_SERVICE_READY
    wings: "both deployed via native hinge configurations"
    autonomous: true
    hold: "SERVICE configuration pending ratification"
  -
    state: SAFE_STOP
    arm_pose: "hold current"
    wings: unchanged
    autonomous: true
    note: "brakes engaged, no new motion accepted"
  -
    state: MANUAL_RECOVERY
    arm_pose: "ground commanded"
    wings: unchanged
    autonomous: false
engineering_wing_states:
  - STOWED
  - DEPLOYING
  - DEPLOYED
  - L_FAIL
  - R_FAIL
  - BOTH_FAIL
note: "wing states come from one physical panel per side rotating about the real native hinge axis; no dual panel entities"
hdrm_states:
  - LOCKED
  - RELEASE_ARMED
  - RELEASE_START
  - RELEASED
  - RELEASE_FAILED
  - GROUND_UNLOCK
hdrm_note: "one physical functional-envelope demonstrator; COMPETITION_DEMONSTRATOR_FUNCTIONAL_ENVELOPE, FLIGHT_ACTUATOR_PROCUREMENT_TBD"
gripper_states:
  - OPEN
  - PREGRASP
  - CLOSED
  - HOLDING
gripper_note: "HOLDING is a CLOSED-geometry alias with no actuator/force authority"
transitions_authorised:
  -
    from: DEPLOYED_NOMINAL
    to: SERVICE_STAGING
    evidence: "V5 Loop2 native sweep required"
  -
    from: SERVICE_STAGING
    to: DEPLOYED_NOMINAL
    evidence: "V5 Loop2 native sweep required (reverse segment)"
  -
    from: any
    to: SAFE_STOP
    evidence: "always allowed"
transitions_not_authorised:
  - "SERVICE_DOCKING / GRASP / TRANSPORT / ASSEMBLY / RETRIEVED_NOMINAL without human pose authority"
  - "STOW to RELEASE_CLEAR without HDRM native closure and ground authority"
  - "wing deployment TRANSIT without native hinge and interference closure"
"""


def write_digital_thread() -> List[Path]:
    DIGITAL_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []
    frame = DIGITAL_DIR / "V5_FRAME_MAPPING.yaml"
    write_text_once(frame, frame_mapping_yaml())
    outputs.append(frame)

    link_csv = DIGITAL_DIR / "V5_LINK_COMPONENT_MAPPING.csv"
    link_fields = [
        "urdf_link",
        "urdf_joint",
        "component_name2",
        "native_path",
        "native_sha256",
        "step_path",
        "visual_mesh_path",
        "collision_mesh_path",
        "control_frame",
        "camera_frame",
        "authority_level",
        "status",
        "notes",
    ]
    write_csv_once(link_csv, link_fields, link_component_mapping_rows())
    outputs.append(link_csv)

    collision_csv = DIGITAL_DIR / "V5_COLLISION_ASSET_MANIFEST.csv"
    collision_fields = [
        "asset_id",
        "component_name2",
        "native_path",
        "native_sha256",
        "collision_class",
        "authority_level",
        "path",
        "role",
        "urdf_link",
        "triangles",
        "deflection_mm",
        "frame",
        "posed_by",
        "authoritative",
        "authority_note",
    ]
    write_csv_once(collision_csv, collision_fields, collision_asset_rows())
    outputs.append(collision_csv)

    mass_copy = DIGITAL_DIR / "V5_MASS_BOUNDARY.yaml"
    if not mass_copy.exists():
        shutil.copyfile(MASS_BOUNDARY_SEED, mass_copy)
    outputs.append(mass_copy)

    action = DIGITAL_DIR / "V5_ACTION_MASK_RULES.yaml"
    write_text_once(action, action_mask_yaml())
    outputs.append(action)

    state = DIGITAL_DIR / "V5_MECHANICAL_STATE_MACHINE.yaml"
    write_text_once(state, state_machine_yaml())
    outputs.append(state)
    return outputs


def write_tooling_hold() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    payload = {
        "schema": "F3R2_V5_TOOLING_HOLD_RECEIPT_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": "20260810T000300_V5NATIVE",
        "run_root": posix(RUN_ROOT),
        "verdict": "TOOLING_HOLD",
        "reason": "available physical memory is below the mandatory 6 GiB gate and no manually started SolidWorks 2024 SP05 process is attachable",
        "resource_preflight": {
            "available_physical_memory_gib_snapshot": 0.977,
            "minimum_required_gib": 6.0,
            "operator_must_confirm_stable_memory": True,
        },
        "solidworks_attach_attempted": False,
        "solidworks_started_by_agent": False,
        "next_entry_conditions": [
            "user closes memory-heavy applications so available physical memory is stably >= 6 GiB",
            "user manually starts SolidWorks 2024 SP05",
            "attach-only G0/session qualification passes against the new clean session",
            "resume Loop1B/1C0/1C1/1D/1E then Loop2 and Loop3 in the claimed V5 root",
        ],
        "non_claims": [
            "NO_NATIVE_CAD_WRITTEN_IN_THIS_TURN",
            "NOT_NATIVE_ASSEMBLY_PASS",
            "NOT_COLD_REOPEN_PASS",
            "NOT_FINAL_GATE",
        ],
    }
    path = VALIDATION / f"V5_TOOLING_HOLD_{stamp}.json"
    write_text_once(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def main() -> None:
    outputs = write_digital_thread()
    hold = write_tooling_hold()
    report = {
        "verdict": "V5_OFFLINE_DIGITAL_THREAD_SEED_AND_TOOLING_HOLD_WRITTEN",
        "digital_thread": [file_fact(path) for path in outputs],
        "tooling_hold": file_fact(hold),
        "non_claims": [
            "NOT_NATIVE_ASSEMBLY_PASS",
            "NOT_COLD_REOPEN_PASS",
            "NOT_FINAL_GATE",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
