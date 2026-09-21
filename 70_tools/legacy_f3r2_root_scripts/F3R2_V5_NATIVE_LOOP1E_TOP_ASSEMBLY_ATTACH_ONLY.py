# -*- coding: utf-8 -*-
"""F3R2 V5 Loop-1E native top-assembly integration (attach-only).

This script is intentionally fail-closed.  ``audit`` is filesystem-only and
must not attach to SOLIDWORKS.  ``execute`` is enabled only after the exact
write-once Loop-1B, Loop-1C1 and Loop-1D receipt hashes have been registered
below.  A receipt which merely exists is never trusted dynamically.

Integration architecture
------------------------
* Protected F3R2 spacecraft donor is *not* inserted as a monolithic top
  assembly because doing so would duplicate the legacy solar roots, saddle
  placeholders, articulated arm and state-proxy wing panels.
* Only the protected F3R2 primary-structure and B601 mount/load-path
  subassemblies are reused as spacecraft structure, at identity.
* The canonical B51 arm tree is copied byte-for-byte into V5, then only the
  copied arm assembly is edited to suppress its legacy gripper-detail
  occurrence.  The protected donor is checked PRE/POST.
* Every new mechanical module is referenced from the unique V5 root.  V5
  B601-local geometry and the B51 arm use the measured mount transform:
  URDF +Z -> world +X, +25 degree clock about world X, X = 208 mm.
* The top configuration matrix changes referenced configurations of the same
  physical left/right wing-root, gripper and HDRM occurrences.  It does not
  create a second wing panel, gripper or HDRM.
* Q_DEPLOYED_HOME, Q_RELEASE_CLEAR and Q_SERVICE_READY remain runtime pose
  authority.  No q vector is written into CAD and no undefined service q is
  invented by this script.

No COM activation helper or process launch/termination path is permitted.  The
sole live entry is the pinned Loop-1 base helper's proven attach-to-existing
session path.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
RUN_ROOT = ENGINEERING / "F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
VALIDATION = RUN_ROOT / "13_validation"
RELEASE = RUN_ROOT / "14_release"
TOP_DIR = RUN_ROOT / "03_top_assembly"
TARGET = TOP_DIR / "SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM"
CHECKPOINT = VALIDATION / "V5_LOOP1E_CHECKPOINT_TOP_ASSEMBLY.json"
FINAL_RECEIPT = VALIDATION / "V5_LOOP1E_TOP_ASSEMBLY_RECEIPT.json"
FINAL_MANIFEST = RELEASE / "V5_LOOP1E_TOP_ASSEMBLY_MANIFEST_SHA256.txt"
SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py"
ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")
ASSEMBLY_TEMPLATE_SHA256 = "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC"

BASE_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_SHA256 = "1F589D3FAE23D64F2364B1CE98FA232A1AA19648398521E55CB5C7F85D0B6062"

G0_READY = ENGINEERING / "_MFINAL_G0_SMOKE_20260809T172928_P4E8/G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json"
LOOP1_RECEIPT = VALIDATION / "V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
LOOP1A_RECEIPT = VALIDATION / "V5_LOOP1A_SUBASSEMBLY_RECEIPT.json"
LOOP1B_RECEIPT = VALIDATION / "V5_LOOP1B_WING_ROOT_RECEIPT.json"
LOOP1C_RECEIPT = VALIDATION / "V5_LOOP1C1_GRIPPER_ASSEMBLY_RECEIPT.json"
LOOP1D_RECEIPT = VALIDATION / "V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json"

# Existing immutable receipts are exact.  Pending receipt hashes MUST be
# replaced with their final SHA-256 values after those write-once receipts are
# produced.  ``None`` is an explicit PENDING gate, never a wildcard.
UPSTREAM_RECEIPTS: Tuple[Dict[str, Any], ...] = (
    {"stage": "G0", "path": G0_READY, "sha256": "58F8240B1D158867C1B61B09B4A098F5AB670141A3CFEE983F5AD2A637CA5CA6", "schema": None, "verdict": "G0_SOLIDWORKS_NATIVE_EXECUTION_READY"},
    {"stage": "LOOP1", "path": LOOP1_RECEIPT, "sha256": "9FC8D1DBBBDD7D1FE37F5FCCA4359838827282A0D7A961D8EEB511E75BE7160D", "schema": "F3R2_V5_LOOP1_NEUTRAL_IMPORT_RECEIPT_V1", "verdict": "V5_LOOP1_NEUTRAL_NATIVE_PART_IMPORT_PASS"},
    {"stage": "LOOP1A", "path": LOOP1A_RECEIPT, "sha256": "F946A361A7CFF8143753853911F23178AF68592D2F7BBE09990575ED86E9BF49", "schema": "F3R2_V5_LOOP1A_SUBASSEMBLY_RECEIPT_V2", "verdict": "V5_LOOP1A_ADAPTER_SUPPORT_SUBASSEMBLIES_PASS"},
    {"stage": "LOOP1B", "path": LOOP1B_RECEIPT, "sha256": None, "schema": "F3R2_V5_LOOP1B_WING_ROOT_RECEIPT_V1", "verdict": "V5_LOOP1B_DUAL_WING_ROOT_NATIVE_CLOSURE_PASS"},
    {"stage": "LOOP1C", "path": LOOP1C_RECEIPT, "sha256": None, "schema": "F3R2_V5_LOOP1C1_GRIPPER_ASSEMBLY_RECEIPT_V1", "verdict": "V5_LOOP1C1_NATIVE_GRIPPER_ASSEMBLY_PASS_MECHANICAL_MAINLINE_FREEZE_READY"},
    {"stage": "LOOP1D", "path": LOOP1D_RECEIPT, "sha256": None, "schema": "F3R2_V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT_V1", "verdict": "V5_LOOP1D_HDRM_CAMERA_HARNESS_NATIVE_FUNCTIONAL_INTERFACE_PASS"},
)

PROTECTED_PRE = RUN_ROOT / "00_authority/V5_PROTECTED_BASELINE_PRE.json"
POSE_REGISTER = RUN_ROOT / "04_configurations/V5_POSE_AUTHORITY_REGISTER.csv"
HDRM_AUTHORITY = RUN_ROOT / "00_authority/V5_HDRM_AUTHORITY.yaml"
CONTROL_BASELINE = RUN_ROOT / "00_authority/V5_CONTROL_BASELINE.yaml"
ACCEPTED_URDF = ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
F3R2_FROZEN_TOP = ENGINEERING / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM"
F3R2_SPACECRAFT_TOP = ENGINEERING / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/SPACECRAFT_V2_2_NATIVE_COPY/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM"
F3R2_SPACECRAFT_ROOT = F3R2_SPACECRAFT_TOP.parents[1]
SPACECRAFT_PRIMARY = F3R2_SPACECRAFT_ROOT / "01_Primary_Structure/01_Primary_Structure_V2_2.SLDASM"
SPACECRAFT_B601_MOUNT = F3R2_SPACECRAFT_ROOT / "02_B601_Mount_and_Load_Path/02_B601_Mount_and_Load_Path.SLDASM"
B51_DONOR_ROOT = ENGINEERING / "cad/B5_1_B601_interface_closure_candidate/03_CAD/native_articulated/B51_ARTICULATED_20260728T008"
B51_DONOR = B51_DONOR_ROOT / "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"

PROTECTED: Tuple[Tuple[str, Path, str], ...] = (
    ("f3r2_frozen_top", F3R2_FROZEN_TOP, "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0"),
    ("f3r2_spacecraft_top_authority", F3R2_SPACECRAFT_TOP, "8D4762F50EF1E2DF0C5C55127F65E688A1A7B31B09C2A75D993052B18BDC40D4"),
    ("f3r2_primary_structure", SPACECRAFT_PRIMARY, "EEFED6D3C76603F65F598FC14D3DA927EB4533E48165A2D0529095022D532423"),
    ("f3r2_b601_mount_load_path", SPACECRAFT_B601_MOUNT, "ADCAA1C11944341DBFC9FDD36D9725B824102B3872A8F4E31EF32F62CC567D15"),
    ("b51_articulated_arm_donor", B51_DONOR, "603B87BBD4398FDDB3F732FFBFA7E1C080ED91ED6E0A026D56CBDCBA08DE2E22"),
)

# B51 is localized because its protected donor contains the legacy gripper
# detail which would be a duplicate of Loop-1C1.  Only the V5 copy is edited.
LOCAL_ARM_ROOT = TOP_DIR / "_native_donor_local/B51_ARTICULATED_20260728T008"
LOCAL_ARM = LOCAL_ARM_ROOT / "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
LOCAL_ARM_CHECKPOINT = VALIDATION / "V5_LOOP1E0_LOCAL_ARM_NO_LEGACY_GRIPPER_CHECKPOINT.json"
ARM_CONFIGS = ("默认", "STOWED_O13V3")
ARM_LEGACY_GRIPPER_LEAF = "B51_REF_gripper_detail_LINKLOCAL-1"
ARM_LINK6_LEAF = "B51_REF_link6_LINKLOCAL-1"

V5_SUBASSEMBLIES: Mapping[str, Path] = {
    "B601_BASE_ADAPTER": RUN_ROOT / "02_native_subassemblies/B601_BASE_ADAPTER_REV_B2.SLDASM",
    "G07_SUPPORT": RUN_ROOT / "02_native_subassemblies/G07_PRIMARY_SUPPORT_V2.SLDASM",
    "G08_SUPPORT": RUN_ROOT / "02_native_subassemblies/G08_PRIMARY_SUPPORT_V2.SLDASM",
    "MID_SUPPORT": RUN_ROOT / "02_native_subassemblies/MID_BACKUP_SUPPORT_V2.SLDASM",
    "LEFT_WING_ROOT": RUN_ROOT / "02_native_subassemblies/LEFT_WING_ROOT_TRUE_HINGE.SLDASM",
    "RIGHT_WING_ROOT": RUN_ROOT / "02_native_subassemblies/RIGHT_WING_ROOT_TRUE_HINGE.SLDASM",
    "GRIPPER": RUN_ROOT / "02_native_subassemblies/B601_GRIPPER.SLDASM",
    "HDRM": RUN_ROOT / "02_native_subassemblies/ARM_HDRM_FUNCTIONAL_ENVELOPE.SLDASM",
    "CAMERA": RUN_ROOT / "02_native_subassemblies/SERVICE_CAMERA_INTERFACE_HOLD.SLDASM",
    "HARNESS": RUN_ROOT / "02_native_subassemblies/B601_HARNESS_STATIC_INTERFACE_HOLD.SLDASM",
}

# SolidWorks ArrayData: 3x3 columns, translation (m), scale, trailing zeros.
IDENTITY_T16 = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
_C25 = math.cos(math.radians(25.0))
_S25 = math.sin(math.radians(25.0))
MOUNT_T16 = (0.0, _S25, -_C25, 0.0, _C25, _S25, 1.0, 0.0, 0.0, 0.208, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)

# Frame ownership is not uniform across the V5 subassemblies.  Only the Stage
# A/B adapter is authored in B601 local coordinates.  The Loop1 receipt proves
# that G07/G08/Mid, the HDRM reference envelopes and the OD9 harness already
# carry spacecraft/world placement coordinates; applying MOUNT_T16 again would
# double-transform them.  Loop1B wing roots are likewise spacecraft/world.
# Gripper and camera placement is deliberately NOT inferred from filenames or
# raw bbox magnitude: Loop1C1/Loop1D must publish a cold-B-rep frame contract.
FIXED_SUBASSEMBLY_TRANSFORMS: Mapping[str, Sequence[float]] = {
    "B601_BASE_ADAPTER": MOUNT_T16,
    "G07_SUPPORT": IDENTITY_T16,
    "G08_SUPPORT": IDENTITY_T16,
    "MID_SUPPORT": IDENTITY_T16,
    "LEFT_WING_ROOT": IDENTITY_T16,
    "RIGHT_WING_ROOT": IDENTITY_T16,
    "HDRM": IDENTITY_T16,
    "HARNESS": IDENTITY_T16,
}
UPSTREAM_FRAME_ROLES = ("GRIPPER", "CAMERA")
FRAME_CONTRACTS: Mapping[str, Dict[str, Any]] = {
    "SPACECRAFT_PRIMARY": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
    "SPACECRAFT_B601_MOUNT": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
    "ARM": {"source_frame": "B601_LOCAL", "placement": "MOUNT_T16"},
    "B601_BASE_ADAPTER": {"source_frame": "B601_LOCAL", "placement": "MOUNT_T16"},
    "G07_SUPPORT": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
    "G08_SUPPORT": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
    "MID_SUPPORT": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
    "LEFT_WING_ROOT": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
    "RIGHT_WING_ROOT": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
    "HDRM": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
    "HARNESS": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
}

FRAME_BBOX_WITNESSES: Mapping[str, Tuple[Dict[str, Any], ...]] = {
    "B601_BASE_ADAPTER": (
        {"path": RUN_ROOT / "01_native_parts/adapter/B601_INTERFACE_STAGE_A_REV_B2.SLDPRT", "sha256": "FC84FBBA450A3C975B1AFA798CF37C492AB2680251BA906FBC1FA383800C1978", "bbox_mm": (-75.0, -75.0, -5.595, 75.0, 75.0, 2.405)},
        {"path": RUN_ROOT / "01_native_parts/adapter/B601_LOAD_ADAPTER_STAGE_B_REV_B2.SLDPRT", "sha256": "AC85890EF29FCC3D5C6FAD87E0255BBAC03256B9EA9FA561092B6CF6CB1BE085", "bbox_mm": (-85.0, -85.0, -12.0, 85.0, 85.0, 0.0)},
    ),
    "G07_SUPPORT": (
        {"path": RUN_ROOT / "01_native_parts/supports/G07_PRIMARY_SUPPORT_V2.SLDPRT", "sha256": "BBD45CCFA724453ABE1AC92E30F59545B454D24D6462671EB655D5753D2FD964", "bbox_mm": (-37.0, -26.810000000000002, 113.15, 17.0, 33.19, 252.5016)},
    ),
    "G08_SUPPORT": (
        {"path": RUN_ROOT / "01_native_parts/supports/G08_PRIMARY_SUPPORT_V2.SLDPRT", "sha256": "C52244E9B262E8C8C448AE1DCEFF1A3F9A2FC6AC16253BF8DF844B59AB56E8E8", "bbox_mm": (153.0, 11.549999999999999, 113.15, 187.0, 71.55, 202.4929)},
    ),
    "MID_SUPPORT": (
        {"path": RUN_ROOT / "01_native_parts/supports/MID_BACKUP_SUPPORT_V2.SLDPRT", "sha256": "5CE735DC17CEB0EC89C83FA5760AB095DDC33C18455A5D1F24E298A6081E9A57", "bbox_mm": (73.0, 17.8, 113.15, 107.0, 77.8, 205.91889999999998)},
    ),
    "HDRM": (
        {"path": RUN_ROOT / "01_native_parts/hdrm/ARM_HDRM_RELEASE_SWEEP_ENVELOPE.SLDPRT", "sha256": "AC90D4FB3FAA6888198255922D0128E4C7B8702467FD3DA266B9A433BCEFAE42", "bbox_mm": (-21.0, -89.0, 127.0, 15.0, 89.0, 173.0)},
        {"path": RUN_ROOT / "01_native_parts/hdrm/ARM_HDRM_60MM_MOUNT_ENVELOPE.SLDPRT", "sha256": "ED08F4BD92F41CD42A92C6D3F497C0570A1B842DA8A79F74ED03AF223A3A95D6", "bbox_mm": (-5.0, -30.0, 120.0, 5.0, 30.0, 180.0)},
    ),
    "HARNESS": (
        {"path": RUN_ROOT / "01_native_parts/camera_harness/B601_OD9_STATIC_HARNESS_ENVELOPE.SLDPRT", "sha256": "3E08F338C6BC7380C8D34CD8BEE748312EDC1A8687DDB2C735176A912A2CE301", "bbox_mm": (166.5, -4.500000004572001, -74.50000000000001, 219.5, 4.500000004572001, 4.5)},
    ),
}

MOTION_CONTRACT_POLICY: Mapping[str, Any] = {
    "schema": "F3R2_V5_LOOP2_MOTION_CONTRACT_V1",
    "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
    "top_configuration_role": "PACKAGING_AND_SUBSYSTEM_STATE_SELECTION_ONLY",
    "top_configuration_is_6r_q_pose_proof": False,
    "arm_referenced_configuration_is_6r_q_pose_proof": False,
    "q_vectors_written_by_loop1e": False,
    "undefined_service_q_created": False,
    "loop2_joint_driver_and_readback_required_for": [
        "Q_DEPLOYED_HOME",
        "Q_RELEASE_CLEAR",
        "Q_SERVICE_READY",
    ],
    "required_loop2_evidence": [
        "six_joint_command_vector",
        "six_joint_angle_readback",
        "axis_and_limit_readback",
        "adaptive_native_clearance",
    ],
}

# Loop1E creates only the native driver mechanism and records the pre-existing
# q=0 / engineering-stow seeds needed to keep both donor configurations
# rebuildable.  It does not promote a q vector or a top configuration to pose
# authority.  Loop2 remains the only stage allowed to command and read back the
# three authorized runtime vectors.
ARM_CONFIGURATION_Q_DEG: Mapping[str, Sequence[float]] = {
    ARM_CONFIGS[0]: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    ARM_CONFIGS[1]: (145.572, -168.0, -57.0, -41.143, -20.954, -3.0),
}

REQUIRED_MOTION_COMPARISONS: Mapping[str, Tuple[str, str]] = {
    "ARM_BUS": ("ARM_MOVING", "BUS"),
    "ARM_WING_LEFT": ("ARM_MOVING", "WING_LEFT"),
    "ARM_WING_RIGHT": ("ARM_MOVING", "WING_RIGHT"),
    "ARM_WING_ROOT": ("ARM_MOVING", "WING_ROOT"),
    "ARM_SUPPORT": ("ARM_MOVING", "SUPPORT"),
    "ARM_HDRM": ("ARM_MOVING", "HDRM"),
    "GRIPPER_BUS": ("GRIPPER", "BUS"),
    "CAMERA_STRUCTURES": ("CAMERA", "STRUCTURES"),
    "HARNESS_MOVING_BODIES": ("HARNESS", "MOVING_BODIES"),
}
REQUIRED_MOTION_ROLES = {
    "ARM_MOVING", "BUS", "WING_LEFT", "WING_RIGHT", "WING_ROOT", "SUPPORT",
    "HDRM", "GRIPPER", "CAMERA", "HARNESS", "MOVING_BODIES", "STRUCTURES",
}
POSE_CONFIGURATION_BINDINGS: Mapping[str, str] = {
    "Q_DEPLOYED_HOME": "DEPLOYED_NOMINAL",
    "Q_RELEASE_CLEAR": "RELEASE_CLEAR_END_STATE",
    "Q_SERVICE_READY": "SERVICE",
    "Q_STOW_ENGINEERING_CANDIDATE": "STOWED_ENGINEERING_CANDIDATE",
    "SOLAR_DEPLOY_ARM_LOCKED": "SOLAR_DEPLOY_ARM_LOCKED",
    "HDRM_RELEASE": "HDRM_RELEASE",
}

TOP_CONFIGS: Mapping[str, Dict[str, Any]] = {
    "STOWED_ENGINEERING_CANDIDATE": {"arm": "STOWED_O13V3", "left_wing": "STOWED", "right_wing": "STOWED", "gripper": "OPEN", "hdrm": "LOCKED", "pose": "Q_STOW_ENGINEERING_CANDIDATE", "authority": "CANDIDATE_HOLD"},
    "SOLAR_DEPLOY_ARM_LOCKED": {"arm": "STOWED_O13V3", "left_wing": "DEPLOYED", "right_wing": "DEPLOYED", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "ENGINEERING_STATE_NO_Q_WRITTEN"},
    "HDRM_RELEASE": {"arm": "STOWED_O13V3", "left_wing": "DEPLOYED", "right_wing": "DEPLOYED", "gripper": "OPEN", "hdrm": "RELEASED", "pose": None, "authority": "SEQUENCE_NODE_ONLY_RELEASE_DYNAMICS_NOT_AUTHORIZED"},
    "DEPLOYED_NOMINAL": {"arm": "默认", "left_wing": "DEPLOYED", "right_wing": "DEPLOYED", "gripper": "OPEN", "hdrm": "RELEASED", "pose": "Q_DEPLOYED_HOME", "authority": "AUTHORIZED_RUNTIME_INPUT_NOT_BAKED"},
    "L_FAIL": {"arm": "STOWED_O13V3", "left_wing": "L_FAIL", "right_wing": "L_FAIL", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "FAULT_STATE_NO_Q_WRITTEN"},
    "R_FAIL": {"arm": "STOWED_O13V3", "left_wing": "R_FAIL", "right_wing": "R_FAIL", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "FAULT_STATE_NO_Q_WRITTEN"},
    "DEPLOY_FAILED_BOTH": {"arm": "STOWED_O13V3", "left_wing": "BOTH_FAIL", "right_wing": "BOTH_FAIL", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "FAULT_STATE_NO_Q_WRITTEN"},
    "PARTIAL": {"arm": "STOWED_O13V3", "left_wing": "DEPLOYING", "right_wing": "DEPLOYING", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "TRUE_1R_NO_INTERMEDIATE_ANGLE_AUTHORITY"},
    "SERVICE": {"arm": "默认", "left_wing": "DEPLOYED", "right_wing": "DEPLOYED", "gripper": "OPEN", "hdrm": "RELEASED", "pose": "Q_SERVICE_READY", "authority": "PRE_SERVICE_STAGING_RATIFICATION_HOLD_NO_SERVICE_Q_WRITTEN"},
    "RELEASE_CLEAR_END_STATE": {"arm": "默认", "left_wing": "DEPLOYED", "right_wing": "DEPLOYED", "gripper": "OPEN", "hdrm": "RELEASED", "pose": "Q_RELEASE_CLEAR", "authority": "AUTHORIZED_GEOMETRIC_END_STATE_RUNTIME_Q_NOT_BAKED"},
}

SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT_READONLY = 3
SW_SAVE_AS_CURRENT_VERSION = 0
SW_SAVE_AS_SILENT = 1
SW_MATE_LOCK = 16
SW_MATE_ANGLE = 6
SW_ALIGN_ALIGNED = 0
SW_ALIGN_ANTI_ALIGNED = 1
SW_ALIGN_CLOSEST = 2
SW_ADD_MATE_NO_ERROR = 1
SW_COMPONENT_SUPPRESSED = 0
SW_COMPONENT_RESOLVED = 2
SW_COMPONENT_VISIBLE = 1
SW_COMPONENT_RIGID = 0
SW_COMPONENT_FLEXIBLE = 1
SW_BODY_SOLID = 0
SW_SET_VALUE_IN_SPECIFIC_CONFIGS = 3
SW_SET_VALUE_SUCCESS = 0


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Any = None):
        super().__init__(message)
        self.code = code
        self.detail = detail


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise GateError("JSON_ROOT_FAIL", "JSON root must be an object", {"path": norm(path)})
    return value


def write_json_once(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_text_once(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def recursive_file_facts(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            yield value
        for item in value.values():
            yield from recursive_file_facts(item)
    elif isinstance(value, list):
        for item in value:
            yield from recursive_file_facts(item)


def audit_receipts() -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    payloads: Dict[str, Dict[str, Any]] = {}
    for contract in UPSTREAM_RECEIPTS:
        path = Path(contract["path"])
        expected_hash = contract["sha256"]
        row: Dict[str, Any] = {
            "stage": contract["stage"], "path": norm(path), "exists": path.is_file(),
            "expected_sha256": expected_hash, "actual_sha256": sha256(path) if path.is_file() else None,
            "hash_registered": expected_hash is not None, "schema_expected": contract["schema"],
            "verdict_expected": contract["verdict"],
        }
        if path.is_file():
            try:
                payload = load_json(path)
                payloads[str(contract["stage"])] = payload
                row["schema_actual"] = payload.get("schema")
                row["verdict_actual"] = payload.get("verdict")
            except Exception as exc:
                row["parse_error"] = repr(exc)
        row["pass"] = bool(
            row["exists"] and expected_hash is not None and row["actual_sha256"] == expected_hash
            and (contract["schema"] is None or row.get("schema_actual") == contract["schema"])
            and row.get("verdict_actual") == contract["verdict"]
        )
        row["status"] = "PASS" if row["pass"] else "PENDING" if (not row["exists"] or expected_hash is None) else "FAIL"
        rows.append(row)
    return rows, payloads


def audit_protected() -> List[Dict[str, Any]]:
    rows = []
    if not PROTECTED_PRE.is_file():
        rows.append({"name": "v5_protected_baseline_pre", "path": norm(PROTECTED_PRE), "exists": False, "expected_sha256": None, "actual_sha256": None, "pass": False})
    else:
        registered = load_json(PROTECTED_PRE).get("assets", [])
        if not isinstance(registered, list) or not registered:
            rows.append({"name": "v5_protected_baseline_pre", "path": norm(PROTECTED_PRE), "exists": True, "expected_sha256": None, "actual_sha256": sha256(PROTECTED_PRE), "pass": False, "reason": "EMPTY_OR_INVALID_ASSET_REGISTER"})
        else:
            for item in registered:
                path = Path(str(item.get("path", "")))
                expected = str(item.get("expected_sha256", "")).upper()
                actual = sha256(path) if path.is_file() else None
                rows.append({"name": "registered_" + str(item.get("name", "UNKNOWN")), "path": norm(path), "exists": path.is_file(), "expected_sha256": expected, "actual_sha256": actual, "pass": bool(expected and actual == expected)})
    for name, path, expected in PROTECTED:
        actual = sha256(path) if path.is_file() else None
        rows.append({"name": name, "path": norm(path), "exists": path.is_file(), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    return rows


def find_receipted_fact(payloads: Mapping[str, Dict[str, Any]], path: Path) -> Optional[Dict[str, Any]]:
    wanted = os.path.normcase(str(path.resolve()))
    matches = []
    for payload in payloads.values():
        for fact in recursive_file_facts(payload):
            try:
                actual = os.path.normcase(str(Path(fact["path"]).resolve()))
            except Exception:
                continue
            if actual == wanted:
                matches.append(fact)
    if not matches:
        return None
    identities = {(str(row.get("sha256", "")).upper(), int(row.get("bytes", -1))) for row in matches}
    if len(identities) != 1:
        raise GateError("UPSTREAM_TARGET_IDENTITY_AMBIGUOUS", "upstream receipts disagree on a V5 target", {"path": norm(path), "matches": matches})
    return matches[0]


def audit_v5_components(payloads: Mapping[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for role, path in V5_SUBASSEMBLIES.items():
        fact = find_receipted_fact(payloads, path)
        actual = sha256(path) if path.is_file() else None
        row = {"role": role, "path": norm(path), "exists": path.is_file(), "actual_sha256": actual, "receipt_fact": fact}
        row["inside_unique_v5_root"] = RUN_ROOT.resolve() in path.resolve().parents
        row["pass"] = bool(row["inside_unique_v5_root"] and fact and actual == str(fact.get("sha256", "")).upper() and path.stat().st_size == int(fact.get("bytes", -1))) if path.is_file() else False
        row["status"] = "PASS" if row["pass"] else "PENDING" if (not path.is_file() or fact is None) else "FAIL"
        rows.append(row)
    return rows


def accepted_urdf_joints() -> List[Dict[str, Any]]:
    if not ACCEPTED_URDF.is_file() or sha256(ACCEPTED_URDF) != ACCEPTED_URDF_SHA256:
        raise GateError("ACCEPTED_URDF_HASH_FAIL", "accepted URDF is absent or changed", file_fact(ACCEPTED_URDF))

    def triple(text: Optional[str], field: str) -> List[float]:
        values = [float(value) for value in str(text or "").split()]
        if len(values) != 3 or not all(math.isfinite(value) for value in values):
            raise GateError("URDF_TRIPLE_PARSE_FAIL", "URDF vector is not a finite xyz/rpy triple", {"field": field, "text": text})
        return values

    root = ET.parse(ACCEPTED_URDF).getroot()
    rows: List[Dict[str, Any]] = []
    for element in root.findall("joint"):
        if element.attrib.get("type") != "revolute":
            continue
        name = str(element.attrib.get("name", ""))
        origin, axis, limit = element.find("origin"), element.find("axis"), element.find("limit")
        parent, child = element.find("parent"), element.find("child")
        if None in (origin, axis, limit, parent, child):
            raise GateError("URDF_REVOLUTE_FIELD_MISSING", "accepted revolute joint omits origin/axis/limit/link fields", {"joint": name})
        lower, upper = float(limit.attrib["lower"]), float(limit.attrib["upper"])
        if not all(math.isfinite(value) for value in (lower, upper)) or upper <= lower:
            raise GateError("URDF_LIMIT_PARSE_FAIL", "accepted revolute joint limits are invalid", {"joint": name, "lower": lower, "upper": upper})
        rows.append({
            "joint": name,
            "parent": str(parent.attrib["link"]),
            "child": str(child.attrib["link"]),
            "origin_xyz": triple(origin.attrib.get("xyz"), f"{name}.origin.xyz"),
            "origin_rpy": triple(origin.attrib.get("rpy", "0 0 0"), f"{name}.origin.rpy"),
            "axis_xyz": triple(axis.attrib.get("xyz"), f"{name}.axis.xyz"),
            "lower_rad": lower,
            "upper_rad": upper,
        })
    if [row["joint"] for row in rows] != [f"joint{index}" for index in range(1, 7)]:
        raise GateError("URDF_REVOLUTE_SET_FAIL", "accepted URDF is not the exact ordered 6R chain", {"joints": [row["joint"] for row in rows]})
    return rows


def audit_authority() -> Dict[str, Any]:
    pose_text = POSE_REGISTER.read_text(encoding="utf-8-sig") if POSE_REGISTER.is_file() else ""
    required = ("Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY", "Q_STOW_ENGINEERING_CANDIDATE")
    undefined = ("Q_SERVICE_GRASP", "Q_SERVICE_DOCKING", "Q_SERVICE_TRANSPORT", "Q_SERVICE_ASSEMBLY", "Q_RETRIEVED_NOMINAL")
    config_poses = {str(spec["pose"]) for spec in TOP_CONFIGS.values() if spec.get("pose")}
    permitted = set(required)
    no_invented = config_poses.issubset(permitted) and not any(name in config_poses for name in undefined)
    motion_contract_pass = (
        MOTION_CONTRACT_POLICY.get("schema") == "F3R2_V5_LOOP2_MOTION_CONTRACT_V1"
        and MOTION_CONTRACT_POLICY.get("accepted_urdf_sha256") == ACCEPTED_URDF_SHA256
        and MOTION_CONTRACT_POLICY.get("top_configuration_is_6r_q_pose_proof") is False
        and MOTION_CONTRACT_POLICY.get("arm_referenced_configuration_is_6r_q_pose_proof") is False
        and MOTION_CONTRACT_POLICY.get("q_vectors_written_by_loop1e") is False
        and MOTION_CONTRACT_POLICY.get("undefined_service_q_created") is False
        and tuple(MOTION_CONTRACT_POLICY.get("loop2_joint_driver_and_readback_required_for", ()))
        == ("Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY")
        and set(POSE_CONFIGURATION_BINDINGS) == {"Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY", "Q_STOW_ENGINEERING_CANDIDATE", "SOLAR_DEPLOY_ARM_LOCKED", "HDRM_RELEASE"}
        and set(POSE_CONFIGURATION_BINDINGS.values()).issubset(TOP_CONFIGS)
        and len(accepted_urdf_joints()) == 6
    )
    return {
        "pose_register": file_fact(POSE_REGISTER) if POSE_REGISTER.is_file() else {"path": norm(POSE_REGISTER), "exists": False},
        "hdrm_authority": file_fact(HDRM_AUTHORITY) if HDRM_AUTHORITY.is_file() else {"path": norm(HDRM_AUTHORITY), "exists": False},
        "control_baseline": file_fact(CONTROL_BASELINE) if CONTROL_BASELINE.is_file() else {"path": norm(CONTROL_BASELINE), "exists": False},
        "required_pose_rows_present": all(name in pose_text for name in required),
        "top_configuration_pose_references": sorted(config_poses),
        "q_vectors_written_by_loop1e": False,
        "undefined_service_q_created": False,
        "no_invented_service_q": no_invented,
        "motion_contract_policy": dict(MOTION_CONTRACT_POLICY),
        "accepted_urdf": file_fact(ACCEPTED_URDF),
        "motion_contract_evidence_status": "PENDING_RUNTIME_NATIVE_DRIVER_BUILD_AND_COLD_REOPEN",
        "motion_contract_pass": motion_contract_pass,
        "pass": all(path.is_file() for path in (POSE_REGISTER, HDRM_AUTHORITY, CONTROL_BASELINE)) and all(name in pose_text for name in required) and no_invented and motion_contract_pass,
    }


def loop1_bbox_witnesses() -> List[Dict[str, Any]]:
    payload = load_json(LOOP1_RECEIPT)
    native_parts = payload.get("native_parts", [])
    rows: List[Dict[str, Any]] = []
    for role, witnesses in FRAME_BBOX_WITNESSES.items():
        for expected in witnesses:
            wanted = os.path.normcase(str(Path(expected["path"]).resolve()))
            matches = [
                item for item in native_parts
                if isinstance(item, dict)
                and os.path.normcase(str(Path(str(item.get("target", {}).get("path", ""))).resolve())) == wanted
            ]
            actual_bbox = matches[0].get("cold_facts", {}).get("bounding_box_mm") if len(matches) == 1 else None
            actual_sha = matches[0].get("target", {}).get("sha256") if len(matches) == 1 else None
            bbox_pass = (
                isinstance(actual_bbox, list)
                and len(actual_bbox) == 6
                and all(abs(float(actual_bbox[index]) - float(expected["bbox_mm"][index])) <= 1.0e-9 for index in range(6))
            )
            row = {
                "role": role,
                "receipt": norm(LOOP1_RECEIPT),
                "receipt_sha256": sha256(LOOP1_RECEIPT),
                "path": norm(Path(expected["path"])),
                "expected_sha256": expected["sha256"],
                "actual_sha256": actual_sha,
                "expected_cold_bbox_mm": list(expected["bbox_mm"]),
                "actual_cold_bbox_mm": actual_bbox,
                "record_count": len(matches),
                "pass": bool(len(matches) == 1 and actual_sha == expected["sha256"] and bbox_pass),
            }
            rows.append(row)
    return rows


def upstream_frame_contract(payloads: Mapping[str, Dict[str, Any]], role: str) -> Dict[str, Any]:
    stage = "LOOP1C" if role == "GRIPPER" else "LOOP1D"
    payload = payloads.get(stage)
    if payload is None:
        return {"role": role, "stage": stage, "status": "PENDING", "pass": False, "reason": "UPSTREAM_RECEIPT_MISSING"}
    contracts = payload.get("frame_contracts")
    contract = contracts.get(role) if isinstance(contracts, dict) else None
    if not isinstance(contract, dict):
        return {"role": role, "stage": stage, "status": "FAIL", "pass": False, "reason": "EXPLICIT_FRAME_CONTRACT_MISSING"}
    source_frame = str(contract.get("source_frame", ""))
    expected_placement = {
        "SPACECRAFT_WORLD": "IDENTITY",
        "B601_LOCAL": "MOUNT_T16",
        "LINK6_LOCAL": "LIVE_LINK6_TOTAL_TRANSFORM",
    }.get(source_frame)
    target = Path(str(contract.get("target_path", "")))
    bbox = contract.get("source_bbox_mm")
    witness = contract.get("witness")
    finite_bbox = (
        isinstance(bbox, list)
        and len(bbox) == 6
        and all(math.isfinite(float(value)) for value in bbox)
        and all(float(bbox[index + 3]) > float(bbox[index]) for index in range(3))
    )
    witness_pass = (
        isinstance(witness, dict)
        and witness.get("method") == "SOLIDWORKS_COLD_BREP_BBOX_AND_DATUM_WITNESS"
        and witness.get("cold_reopen_pass") is True
        and int(witness.get("external_reference_count", -1)) == 0
        and bool(str(witness.get("frame_rationale", "")).strip())
    )
    actual_sha = sha256(target) if target.is_file() else None
    pass_value = bool(
        expected_placement is not None
        and contract.get("placement") == expected_placement
        and target.resolve() == V5_SUBASSEMBLIES[role].resolve()
        and actual_sha == str(contract.get("target_sha256", "")).upper()
        and finite_bbox
        and witness_pass
    )
    return {
        "role": role,
        "stage": stage,
        "status": "PASS" if pass_value else "FAIL",
        "pass": pass_value,
        "source_frame": source_frame,
        "placement": contract.get("placement"),
        "target_path": norm(target) if str(contract.get("target_path", "")) else "",
        "target_sha256": actual_sha,
        "source_bbox_mm": bbox,
        "witness": witness,
        "contract": contract,
    }


def audit_frame_contracts(payloads: Mapping[str, Dict[str, Any]]) -> Dict[str, Any]:
    fixed_expected = set(V5_SUBASSEMBLIES) - set(UPSTREAM_FRAME_ROLES)
    bbox_witnesses = loop1_bbox_witnesses()
    dynamic = [upstream_frame_contract(payloads, role) for role in UPSTREAM_FRAME_ROLES]
    contracts = {role: dict(contract) for role, contract in FRAME_CONTRACTS.items()}
    for row in dynamic:
        if row["pass"]:
            contracts[row["role"]] = {
                "source_frame": row["source_frame"],
                "placement": row["placement"],
                "source_bbox_mm": row["source_bbox_mm"],
                "upstream_stage": row["stage"],
                "witness": row["witness"],
            }
    static_pass = (
        set(FIXED_SUBASSEMBLY_TRANSFORMS) == fixed_expected
        and tuple(FIXED_SUBASSEMBLY_TRANSFORMS["B601_BASE_ADAPTER"]) == MOUNT_T16
        and all(tuple(FIXED_SUBASSEMBLY_TRANSFORMS[role]) == IDENTITY_T16 for role in fixed_expected - {"B601_BASE_ADAPTER"})
        and set(FRAME_CONTRACTS) == {"SPACECRAFT_PRIMARY", "SPACECRAFT_B601_MOUNT", "ARM", *fixed_expected}
        and FRAME_CONTRACTS["B601_BASE_ADAPTER"]["source_frame"] == "B601_LOCAL"
        and all(FRAME_CONTRACTS[role]["source_frame"] == "SPACECRAFT_WORLD" for role in fixed_expected - {"B601_BASE_ADAPTER"})
        and all(row["pass"] for row in bbox_witnesses)
    )
    pending = [row["role"] for row in dynamic if row["status"] == "PENDING"]
    failures = [row["role"] for row in dynamic if row["status"] == "FAIL"]
    return {
        "pass": bool(static_pass and not pending and not failures and all(row["pass"] for row in dynamic)),
        "static_contracts_pass": static_pass,
        "mount_transform_array_data": list(MOUNT_T16),
        "identity_transform_array_data": list(IDENTITY_T16),
        "loop1_receipt_sha256": sha256(LOOP1_RECEIPT),
        "bbox_witnesses": bbox_witnesses,
        "dynamic_upstream_contracts": dynamic,
        "dynamic_pending": pending,
        "dynamic_failures": failures,
        "contracts": contracts,
    }


def checkpoint_state() -> Dict[str, Any]:
    if not TARGET.exists() and not CHECKPOINT.exists() and not FINAL_RECEIPT.exists():
        return {"state": "PENDING_NEW"}
    if TARGET.exists() and CHECKPOINT.exists() and not FINAL_RECEIPT.exists():
        try:
            payload = load_json(CHECKPOINT)
            good = bool(
                payload.get("schema") == "F3R2_V5_LOOP1E_TOP_CHECKPOINT_V1"
                and payload.get("script_sha256") == sha256(Path(__file__))
                and payload.get("accepted_urdf_sha256") == ACCEPTED_URDF_SHA256
                and payload.get("motion_contract", {}).get("schema") == "F3R2_V5_LOOP2_MOTION_CONTRACT_V1"
                and payload.get("target", {}).get("sha256") == sha256(TARGET)
            )
            return {"state": "RESUME_COLD_REOPEN" if good else "HOLD_CHECKPOINT_DRIFT", "checkpoint": payload}
        except Exception as exc:
            return {"state": "HOLD_CHECKPOINT_PARSE", "exception": repr(exc)}
    return {"state": "HOLD_WRITE_ONCE_COLLISION", "target_exists": TARGET.exists(), "checkpoint_exists": CHECKPOINT.exists(), "receipt_exists": FINAL_RECEIPT.exists()}


def local_arm_state() -> Dict[str, Any]:
    if not LOCAL_ARM_ROOT.exists() and not LOCAL_ARM_CHECKPOINT.exists():
        return {"state": "PENDING_NEW"}
    if LOCAL_ARM.is_file() and LOCAL_ARM_CHECKPOINT.is_file():
        try:
            payload = load_json(LOCAL_ARM_CHECKPOINT)
            drivers = payload.get("native_joint_drivers")
            good = bool(
                payload.get("schema") == "F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V1"
                and payload.get("script_sha256") == sha256(Path(__file__))
                and payload.get("accepted_urdf_sha256") == ACCEPTED_URDF_SHA256
                and payload.get("local_arm", {}).get("sha256") == sha256(LOCAL_ARM)
                and isinstance(drivers, list)
                and [row.get("joint") for row in drivers] == [f"joint{index}" for index in range(1, 7)]
                and all(row.get("cold_reopen_verified") is True for row in drivers)
            )
            return {"state": "PASS_RESUME" if good else "HOLD_CHECKPOINT_DRIFT", "checkpoint": payload}
        except Exception as exc:
            return {"state": "HOLD_CHECKPOINT_PARSE", "exception": repr(exc)}
    return {"state": "HOLD_PARTIAL_LOCALIZATION", "root_exists": LOCAL_ARM_ROOT.exists(), "arm_exists": LOCAL_ARM.is_file(), "checkpoint_exists": LOCAL_ARM_CHECKPOINT.is_file()}


def static_audit() -> Dict[str, Any]:
    receipt_rows, payloads = audit_receipts()
    protected = audit_protected()
    components = audit_v5_components(payloads)
    authority = audit_authority()
    frame_contracts = audit_frame_contracts(payloads)
    target = checkpoint_state()
    arm = local_arm_state()
    helper_row = {"path": norm(BASE_HELPER), "expected_sha256": BASE_HELPER_SHA256, "actual_sha256": sha256(BASE_HELPER) if BASE_HELPER.is_file() else None}
    helper_row["pass"] = helper_row["actual_sha256"] == BASE_HELPER_SHA256 and BASE_HELPER_COPY.is_file() and sha256(BASE_HELPER_COPY) == BASE_HELPER_SHA256
    template_row = {"path": norm(ASSEMBLY_TEMPLATE), "expected_sha256": ASSEMBLY_TEMPLATE_SHA256, "actual_sha256": sha256(ASSEMBLY_TEMPLATE) if ASSEMBLY_TEMPLATE.is_file() else None}
    template_row["pass"] = template_row["actual_sha256"] == ASSEMBLY_TEMPLATE_SHA256
    pending = [row["stage"] for row in receipt_rows if row["status"] == "PENDING"] + [row["role"] for row in components if row["status"] == "PENDING"] + ["FRAME_CONTRACT_" + role for role in frame_contracts["dynamic_pending"]]
    failures = [row["stage"] for row in receipt_rows if row["status"] == "FAIL"] + [row["role"] for row in components if row["status"] == "FAIL"] + ["FRAME_CONTRACT_" + role for role in frame_contracts["dynamic_failures"]]
    executable_target = target["state"] in {"PENDING_NEW", "RESUME_COLD_REOPEN"}
    executable_arm = arm["state"] in {"PENDING_NEW", "PASS_RESUME"}
    authorized = bool(not pending and not failures and all(row["pass"] for row in receipt_rows + protected + components) and authority["pass"] and frame_contracts["pass"] and helper_row["pass"] and template_row["pass"] and executable_target and executable_arm)
    verdict = "V5_LOOP1E_STATIC_EXECUTION_READY" if authorized else "V5_LOOP1E_STATIC_PENDING_UPSTREAM" if pending and not failures else "V5_LOOP1E_STATIC_HOLD"
    return {
        "schema": "F3R2_V5_LOOP1E_STATIC_AUDIT_V1", "timestamp_utc": utc_now(), "verdict": verdict,
        "execution_authorized": authorized, "script": file_fact(Path(__file__)), "base_helper": helper_row, "assembly_template": template_row,
        "upstream_receipts": receipt_rows, "protected_inputs": protected, "v5_components": components,
        "authority": authority, "frame_contracts": frame_contracts, "target_state": target, "local_arm_state": arm,
        "pending": pending, "failures": failures,
        "architecture": {
            "spacecraft_monolithic_top_inserted": False,
            "spacecraft_primary_structure": norm(SPACECRAFT_PRIMARY),
            "spacecraft_b601_mount_load_path": norm(SPACECRAFT_B601_MOUNT),
            "legacy_spacecraft_wing_roots_inserted": False,
            "legacy_stow_saddle_placeholder_assembly_inserted": False,
            "canonical_b51_donor": norm(B51_DONOR),
            "b51_local_copy": norm(LOCAL_ARM),
            "legacy_b51_gripper_suppressed_only_in_v5_copy": True,
            "target": norm(TARGET),
            "component_frame_contracts": frame_contracts,
            "motion_contract_policy": dict(MOTION_CONTRACT_POLICY),
            "motion_contract_evidence_status": "PENDING_RUNTIME_NATIVE_DRIVER_BUILD_AND_COLD_REOPEN",
        },
        "explicit_holds": [value for value in [
            "LOOP1B_RECEIPT_HASH_REGISTRATION_PENDING" if UPSTREAM_RECEIPTS[3]["sha256"] is None else None,
            "LOOP1C_RECEIPT_HASH_REGISTRATION_PENDING" if UPSTREAM_RECEIPTS[4]["sha256"] is None else None,
            "LOOP1D_RECEIPT_HASH_REGISTRATION_PENDING" if UPSTREAM_RECEIPTS[5]["sha256"] is None else None,
            "Q_SERVICE_READY_IS_PRE_SERVICE_STAGING_WITH_RATIFICATION_HOLD",
            "Q_RELEASE_CLEAR_IS_GEOMETRIC_END_STATE_NOT_RELEASE_SEQUENCE_AUTHORITY",
            "UNDEFINED_SERVICE_GRASP_DOCK_TRANSPORT_ASSEMBLY_RETRIEVAL_Q_PROHIBITED",
            "LOOP2_NATIVE_INTERFERENCE_CLEARANCE_AND_EXPECTED_CONTACT_WHITELIST_PENDING",
            "PACK_AND_GO_FINAL_SELF_CONTAINMENT_PENDING_AFTER_LOOP1E",
        ] if value is not None],
    }


def load_base() -> Any:
    if sha256(BASE_HELPER) != BASE_HELPER_SHA256 or sha256(BASE_HELPER_COPY) != BASE_HELPER_SHA256:
        raise GateError("BASE_HELPER_HASH_FAIL", "pinned GetActiveObject-only helper drifted")
    spec = importlib.util.spec_from_file_location("f3r2_v5_loop1_base_for_loop1e", BASE_HELPER)
    if spec is None or spec.loader is None:
        raise GateError("BASE_HELPER_IMPORT_FAIL", "cannot create base-helper import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tree_files(root: Path) -> List[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and not path.name.startswith("~$") and "__pycache__" not in path.parts)


def stage_local_arm_copy() -> Dict[str, Any]:
    state = local_arm_state()
    if state["state"] == "PASS_RESUME":
        return state["checkpoint"]
    if state["state"] != "PENDING_NEW":
        raise GateError("LOCAL_ARM_STATE_HOLD", "local arm state is not safely resumable", state)
    staging = LOCAL_ARM_ROOT.with_name(LOCAL_ARM_ROOT.name + "__BUILDING_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"))
    if staging.exists():
        raise GateError("LOCAL_ARM_STAGING_COLLISION", "unique staging directory already exists", {"path": norm(staging)})
    rows = []
    for source in tree_files(B51_DONOR_ROOT):
        relative = source.relative_to(B51_DONOR_ROOT)
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        before, after = sha256(source), sha256(target)
        if before != after:
            raise GateError("LOCAL_ARM_COPY_HASH_FAIL", "pairwise arm copy hash mismatch", {"relative": relative.as_posix()})
        rows.append({"relative": relative.as_posix(), "bytes": source.stat().st_size, "source_sha256": before, "target_sha256": after})
    staging.rename(LOCAL_ARM_ROOT)
    return {"schema": "F3R2_V5_LOOP1E0_LOCAL_ARM_STAGED_V1", "copy_rows": rows, "local_arm": file_fact(LOCAL_ARM), "protected_source": file_fact(B51_DONOR)}


def open_doc(sw: Any, path: Path, doc_type: int, read_only: bool, base: Any, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    options = 1 | (2 if read_only else 0)
    raw = sw.OpenDoc6(str(path), doc_type, options, "", 0, 0)
    model_raw, outs = base.unpack(raw)
    errors = int(outs[0]) if outs else 0
    warnings = int(outs[1]) if len(outs) > 1 else 0
    if model_raw is None or errors != 0:
        raise GateError("OPEN_DOC_FAIL", "OpenDoc6 failed", {"path": norm(path), "errors": errors, "warnings": warnings, "read_only": read_only})
    return base.wrap(model_raw, "IModelDoc2", types, pythoncom), {"errors": errors, "warnings": warnings, "read_only": read_only}


def close_doc(sw: Any, model: Any, base: Any) -> None:
    title = str(base.value(model, "GetTitle"))
    sw.CloseDoc(title)


def top_components(model: Any, base: Any, types: Any, pythoncom: Any) -> List[Any]:
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    return [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]


def component_path(component: Any, base: Any) -> str:
    return os.path.normcase(str(Path(str(base.value(component, "GetPathName"))).resolve()))


def child_by_leaf(component: Any, leaf: str, base: Any, types: Any, pythoncom: Any) -> Any:
    queue = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(base.value(component, "GetChildren"))]
    matches = []
    while queue:
        item = queue.pop(0)
        name = str(base.value(item, "Name2")).split("/")[-1]
        if name == leaf:
            matches.append(item)
        queue.extend(base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(base.value(item, "GetChildren")))
    if len(matches) != 1:
        raise GateError("NESTED_COMPONENT_UNIQUE_FAIL", "nested endpoint is not unique", {"leaf": leaf, "matches": [str(base.value(item, "Name2")) for item in matches]})
    return matches[0]


def dependency_paths(model: Any, base: Any) -> List[str]:
    raw = base.as_list(model.GetDependencies2(False, True, False))
    if len(raw) % 2:
        raise GateError("DEPENDENCY_ARRAY_SHAPE_FAIL", "GetDependencies2 returned an odd array", {"count": len(raw)})
    return sorted(os.path.normcase(str(Path(str(raw[index + 1])).resolve())) for index in range(0, len(raw), 2))


def feature_rows(model: Any, base: Any, types: Any, pythoncom: Any) -> List[Any]:
    rows: List[Any] = []
    raw = base.value(model, "FirstFeature")
    while raw is not None:
        feature = base.wrap(raw, "IFeature", types, pythoncom)
        rows.append(feature)
        raw = base.value(feature, "GetNextFeature")
    return rows


def component_feature_rows(component: Any, base: Any, types: Any, pythoncom: Any) -> List[Any]:
    rows: List[Any] = []
    raw = base.value(component, "FirstFeature")
    while raw is not None:
        feature = base.wrap(raw, "IFeature", types, pythoncom)
        rows.append(feature)
        raw = base.value(feature, "GetNextFeature")
    return rows


def component_side_plane(component: Any, base: Any, types: Any, pythoncom: Any) -> Any:
    planes = [feature for feature in component_feature_rows(component, base, types, pythoncom) if str(base.value(feature, "GetTypeName2")) == "RefPlane"]
    named = [feature for feature in planes if str(base.value(feature, "Name")) in {"上视基准面", "Top Plane", "右视基准面", "Right Plane"}]
    candidates = named or (planes[1:] if len(planes) >= 2 else [])
    if not candidates:
        raise GateError("JOINT_SIDE_PLANE_MISSING", "datum component has no axis-containing reference plane", {"component": str(base.value(component, "Name2")), "planes": [str(base.value(item, "Name")) for item in planes]})
    return candidates[0]


def angle_mate_data(feature: Any, base: Any, types: Any, pythoncom: Any) -> Any:
    raw = base.value(feature, "GetDefinition")
    if raw is None:
        raise GateError("ANGLE_MATE_DEFINITION_NULL", "native angle feature has no definition", {"feature": str(base.value(feature, "Name"))})
    return base.wrap(raw, "IAngleMateFeatureData", types, pythoncom)


def angle_mate_object(feature: Any, base: Any, types: Any, pythoncom: Any) -> Any:
    raw = base.value(feature, "GetSpecificFeature2")
    if raw is None:
        raise GateError("ANGLE_MATE_OBJECT_NULL", "native angle feature has no IMate2", {"feature": str(base.value(feature, "Name"))})
    return base.wrap(raw, "IMate2", types, pythoncom)


def angle_mate_dimension(feature: Any, base: Any, types: Any, pythoncom: Any) -> Any:
    mate = angle_mate_object(feature, base, types, pythoncom)
    raw_display = mate.DisplayDimension2(0)
    if raw_display is None:
        raise GateError("ANGLE_DISPLAY_DIMENSION_NULL", "native angle mate has no DisplayDimension2(0)", {"feature": str(base.value(feature, "Name"))})
    display = base.wrap(raw_display, "IDisplayDimension", types, pythoncom)
    raw_dimension = display.GetDimension2(0)
    if raw_dimension is None:
        raise GateError("ANGLE_DIMENSION_NULL", "native angle display has no IDimension", {"feature": str(base.value(feature, "Name"))})
    return base.wrap(raw_dimension, "IDimension", types, pythoncom)


def rotation3(data: Sequence[float]) -> List[List[float]]:
    if len(data) != 16:
        raise GateError("ROTATION_TRANSFORM_SHAPE_FAIL", "component transform is not 16 values", {"length": len(data)})
    return [
        [float(data[0]), float(data[3]), float(data[6])],
        [float(data[1]), float(data[4]), float(data[7])],
        [float(data[2]), float(data[5]), float(data[8])],
    ]


def multiply3(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[sum(float(first[row][index]) * float(second[index][column]) for index in range(3)) for column in range(3)] for row in range(3)]


def transpose3(value: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[float(value[column][row]) for column in range(3)] for row in range(3)]


def matvec3(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> List[float]:
    return [sum(float(matrix[row][index]) * float(vector[index]) for index in range(3)) for row in range(3)]


def rpy_rotation(rpy: Sequence[float]) -> List[List[float]]:
    roll, pitch, yaw = (float(value) for value in rpy)
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def rotation_vector(matrix: Sequence[Sequence[float]]) -> List[float]:
    cosine = max(-1.0, min(1.0, 0.5 * (float(matrix[0][0]) + float(matrix[1][1]) + float(matrix[2][2]) - 1.0)))
    angle = math.acos(cosine)
    if angle < 1.0e-9:
        return [0.5 * (matrix[2][1] - matrix[1][2]), 0.5 * (matrix[0][2] - matrix[2][0]), 0.5 * (matrix[1][0] - matrix[0][1])]
    scale = angle / (2.0 * math.sin(angle))
    return [scale * (matrix[2][1] - matrix[1][2]), scale * (matrix[0][2] - matrix[2][0]), scale * (matrix[1][0] - matrix[0][1])]


def component_transform16(component: Any, base: Any) -> List[float]:
    raw = base.value(component, "Transform2")
    values = [float(value) for value in base.as_list(base.value(raw, "ArrayData"))] if raw is not None else []
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise GateError("ARM_COMPONENT_TRANSFORM_FAIL", "arm component Transform2 is not finite/16-value", {"component": str(base.value(component, "Name2")), "values": values})
    return values


def add_native_angle_driver(
    model: Any,
    assembly: Any,
    female: Any,
    male: Any,
    joint: Dict[str, Any],
    base: Any,
    types: Any,
    pythoncom: Any,
) -> Tuple[Any, Any, Dict[str, Any]]:
    # Loop2 resolves this exact feature name from the LOCAL_ARM component
    # document.  The dimension value is the accepted URDF q itself: no hidden
    # pi offset and no re-use of the donor concentric/coincident hinge mates.
    name = f"V5_LOOP2_{joint['joint'].upper()}_LIMIT_ANGLE"
    before = set(mate_features(model, base, types, pythoncom))
    first_plane = component_side_plane(female, base, types, pythoncom)
    second_plane = component_side_plane(male, base, types, pythoncom)
    model.ClearSelection2(True)
    if not bool(first_plane.Select2(False, 1)) or not bool(second_plane.Select2(True, 1)):
        raise GateError("ANGLE_ENDPOINT_SELECTION_FAIL", "cannot select the two component side planes", {"joint": joint["joint"], "female": str(base.value(female, "Name2")), "male": str(base.value(male, "Name2"))})
    selection = base.wrap(base.value(model, "SelectionManager"), "ISelectionMgr", types, pythoncom)
    selected = int(selection.GetSelectedObjectCount2(1))
    selected_owners = []
    for index in range(1, selected + 1):
        raw_owner = selection.GetSelectedObjectsComponent4(index, 1)
        selected_owners.append(str(base.value(base.wrap(raw_owner, "IComponent2", types, pythoncom), "Name2")) if raw_owner is not None else None)
    returned = assembly.AddMate3(
        SW_MATE_ANGLE, SW_ALIGN_ALIGNED, False,
        0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, float(joint["upper_rad"]), float(joint["lower_rad"]),
        False, 0,
    )
    mate_raw, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    after = mate_features(model, base, types, pythoncom)
    additions = [feature for feature_name, feature in after.items() if feature_name not in before]
    if mate_raw is None or error != SW_ADD_MATE_NO_ERROR or selected != 2 or len(additions) != 1:
        raise GateError("ANGLE_MATE_CREATE_FAIL", "AddMate3 did not create one healthy native angle mate", {"joint": joint["joint"], "error": error, "selected": selected, "selected_owners": selected_owners, "added_features": [str(base.value(item, "Name")) for item in additions]})
    feature = additions[0]
    feature.Name = name
    if str(base.value(feature, "Name")) != name:
        raise GateError("ANGLE_MATE_RENAME_FAIL", "native angle mate did not keep its deterministic feature name", {"joint": joint["joint"], "expected": name})
    data = angle_mate_data(feature, base, types, pythoncom)
    data.IsAdvancedMate = True
    data.MinimumAngle = float(joint["lower_rad"])
    data.MaximumAngle = float(joint["upper_rad"])
    data.Angle = 0.0
    data.MateAlignment = SW_ALIGN_ALIGNED
    if not bool(feature.ModifyDefinition(data, model, None)) or not bool(model.ForceRebuild3(True)):
        raise GateError("ANGLE_MATE_ADVANCED_FAIL", "cannot establish/rebuild the advanced limit-angle definition", {"joint": joint["joint"]})
    mate = angle_mate_object(feature, base, types, pythoncom)
    definition = angle_mate_data(feature, base, types, pythoncom)
    if int(base.value(mate, "Type")) != SW_MATE_ANGLE or not bool(base.value(definition, "IsAdvancedMate")) or int(base.value(feature, "GetErrorCode2")) != 0 or bool(base.value(feature, "IsSuppressed")):
        raise GateError("ANGLE_MATE_HEALTH_FAIL", "created native angle driver is not a healthy advanced type-6 angle mate", {"joint": joint["joint"]})
    dimension = angle_mate_dimension(feature, base, types, pythoncom)
    return feature, dimension, {
        "joint": joint["joint"],
        "feature_name": name,
        "dimension_full_name": str(base.value(dimension, "FullName")),
        "female_component_leaf": str(base.value(female, "Name2")),
        "male_component_leaf": str(base.value(male, "Name2")),
        "selected_plane_features": [str(base.value(first_plane, "Name")), str(base.value(second_plane, "Name"))],
        "selected_owner_name2": selected_owners,
        "add_mate_error_status": error,
        "mate_type": int(base.value(mate, "Type")),
        "advanced": True,
    }


def probe_driver_sign(
    model: Any,
    dimension: Any,
    parent: Any,
    child: Any,
    joint: Dict[str, Any],
    base: Any,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    baseline_parent = rotation3(component_transform16(parent, base))
    baseline_child = rotation3(component_transform16(child, base))
    baseline_relative = multiply3(transpose3(baseline_parent), baseline_child)
    probe_magnitude = math.radians(0.5)
    # joint2/joint3 have q=0 at their accepted upper bound; probe inward rather
    # than illegally stepping outside the URDF interval.
    probe = probe_magnitude if float(joint["upper_rad"]) >= probe_magnitude else -probe_magnitude
    config = ARM_CONFIGS[0]
    status = int(dimension.SetSystemValue3(probe, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [config]))
    if status != SW_SET_VALUE_SUCCESS or not bool(model.ShowConfiguration2(config)) or not bool(model.ForceRebuild3(True)):
        raise GateError("ANGLE_SIGN_PROBE_SET_FAIL", "cannot apply the positive native angle sign probe", {"joint": joint["joint"], "status": status})
    current_parent = rotation3(component_transform16(parent, base))
    current_child = rotation3(component_transform16(child, base))
    current_relative = multiply3(transpose3(current_parent), current_child)
    delta = multiply3(current_relative, transpose3(baseline_relative))
    vector = rotation_vector(delta)
    expected_axis_parent = matvec3(rpy_rotation(joint["origin_rpy"]), joint["axis_xyz"])
    norm_axis = math.sqrt(sum(value * value for value in expected_axis_parent))
    expected_axis_parent = [value / norm_axis for value in expected_axis_parent]
    projected = sum(vector[index] * expected_axis_parent[index] for index in range(3))
    transverse = math.sqrt(max(0.0, sum(value * value for value in vector) - projected * projected))
    restore_status = int(dimension.SetSystemValue3(0.0, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [config]))
    if restore_status != SW_SET_VALUE_SUCCESS or not bool(model.ForceRebuild3(True)):
        raise GateError("ANGLE_SIGN_PROBE_RESTORE_FAIL", "cannot restore q=0 after sign probe", {"joint": joint["joint"], "status": restore_status})
    if abs(abs(projected) - abs(probe)) > math.radians(0.08) or transverse > math.radians(0.05):
        raise GateError("ANGLE_SIGN_PROBE_KINEMATIC_FAIL", "native angle probe did not produce a pure accepted-axis rotation", {"joint": joint["joint"], "projected_rad": projected, "transverse_rad": transverse, "expected_probe_rad": probe, "rotation_vector": vector, "expected_axis_parent": expected_axis_parent})
    if projected * probe <= 0.0:
        raise GateError("ANGLE_SIGN_PROBE_DIRECTION_FAIL", "native q direction is opposite the accepted URDF axis; endpoint orientation must be corrected before release", {"joint": joint["joint"], "native_probe_rad": probe, "projected_rad": projected, "expected_axis_parent": expected_axis_parent})
    return {
        "joint": joint["joint"],
        "native_probe_delta_rad": probe,
        "accepted_axis_projected_delta_rad": projected,
        "transverse_rotation_rad": transverse,
        "sign": 1.0,
        "zero_offset_rad": 0.0,
        "accepted_axis_in_parent": expected_axis_parent,
        "pass": True,
    }


def configure_native_arm_drivers(model: Any, assembly: Any, components: Sequence[Any], base: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    by_leaf = {str(base.value(item, "Name2")).split("/")[-1]: item for item in components}
    joints = accepted_urdf_joints()
    drivers: List[Dict[str, Any]] = []
    for index, joint in enumerate(joints, start=1):
        female = by_leaf.get(f"B51_REV_DATUM_FEMALE-{index}")
        male = by_leaf.get(f"B51_REV_DATUM_MALE-{index}")
        parent = by_leaf.get("B51_REF_base_link_LINKLOCAL-1" if index == 1 else f"B51_REF_link{index - 1}_LINKLOCAL-1")
        child = by_leaf.get(f"B51_REF_link{index}_LINKLOCAL-1")
        if any(item is None for item in (female, male, parent, child)):
            raise GateError("ARM_JOINT_COMPONENT_SET_FAIL", "joint datum/visual components are not exact", {"joint": joint["joint"], "available": sorted(by_leaf)})
        feature, dimension, creation = add_native_angle_driver(model, assembly, female, male, joint, base, types, pythoncom)
        sign_probe = probe_driver_sign(model, dimension, parent, child, joint, base, types, pythoncom)
        native_limits = [float(joint["lower_rad"]), float(joint["upper_rad"])]
        data = angle_mate_data(feature, base, types, pythoncom)
        data.IsAdvancedMate = True
        data.MinimumAngle = native_limits[0]
        data.MaximumAngle = native_limits[1]
        data.Angle = 0.0
        data.MateAlignment = SW_ALIGN_ALIGNED
        if not bool(feature.ModifyDefinition(data, model, None)) or not bool(model.ForceRebuild3(True)):
            raise GateError("ANGLE_FINAL_LIMIT_MODIFY_FAIL", "cannot apply accepted URDF limits to native driver", {"joint": joint["joint"], "native_limits": native_limits})
        readback = angle_mate_data(feature, base, types, pythoncom)
        actual = [float(base.value(readback, "MinimumAngle")), float(base.value(readback, "MaximumAngle"))]
        if not bool(base.value(readback, "IsAdvancedMate")) or max(abs(actual[i] - native_limits[i]) for i in range(2)) > 1.0e-9:
            raise GateError("ANGLE_FINAL_LIMIT_READBACK_FAIL", "native advanced-angle limit readback differs from accepted URDF limits", {"joint": joint["joint"], "expected": native_limits, "actual": actual})
        row = {
            **creation,
            **sign_probe,
            "accepted_parent_link": joint["parent"],
            "accepted_child_link": joint["child"],
            "accepted_axis_xyz": joint["axis_xyz"],
            "accepted_origin_xyz": joint["origin_xyz"],
            "accepted_origin_rpy": joint["origin_rpy"],
            "accepted_lower_rad": joint["lower_rad"],
            "accepted_upper_rad": joint["upper_rad"],
            "native_minimum_rad": native_limits[0],
            "native_maximum_rad": native_limits[1],
            "driver_generation_stage": "LOOP1E_NATIVE_DRIVER_SYNTHESIS",
            "preexisting_b51_hinge_mate_used_as_driver": False,
        }
        drivers.append(row)
    for config, q_deg in ARM_CONFIGURATION_Q_DEG.items():
        for row in drivers:
            dimension = model.Parameter(row["dimension_full_name"])
            if dimension is None:
                raise GateError("ANGLE_CONFIG_DIMENSION_MISSING", "native driver dimension did not resolve for configuration seed", {"joint": row["joint"], "dimension": row["dimension_full_name"]})
            requested = math.radians(float(q_deg[int(row["joint"].replace("joint", "")) - 1]))
            status = int(dimension.SetSystemValue3(requested, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [config]))
            values = [float(value) for value in base.as_list(dimension.GetSystemValue3(SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [config]))]
            if status != SW_SET_VALUE_SUCCESS or len(values) != 1 or abs(values[0] - requested) > 1.0e-8:
                raise GateError("ANGLE_CONFIG_DIMENSION_DRIVE_FAIL", "pre-existing arm configuration seed did not write/read exactly", {"joint": row["joint"], "config": config, "requested": requested, "status": status, "values": values})
            row.setdefault("configuration_seed_readback", []).append({"configuration": config, "native_angle_rad": values[0], "source_q_deg": float(q_deg[int(row["joint"].replace("joint", "")) - 1]), "authority": "Q0_GEOMETRY_OR_PREEXISTING_ENGINEERING_STOW_SEED_NOT_LOOP2_POSE_PROOF"})
    if not bool(model.ShowConfiguration2(ARM_CONFIGS[0])) or not bool(model.ForceRebuild3(True)):
        raise GateError("ANGLE_DRIVER_CONFIG_RESTORE_FAIL", "cannot restore local-arm q=0 configuration after driver seeding")
    return drivers


def configure_local_arm(sw: Any, staged: Dict[str, Any], base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    if local_arm_state()["state"] == "PASS_RESUME":
        return load_json(LOCAL_ARM_CHECKPOINT)
    model, opened = open_doc(sw, LOCAL_ARM, SW_DOC_ASSEMBLY, False, base, types, pythoncom)
    try:
        names = sorted(str(value) for value in base.as_list(base.value(model, "GetConfigurationNames")))
        if names != sorted(ARM_CONFIGS):
            raise GateError("LOCAL_ARM_CONFIG_SET_FAIL", "B51 copy configuration set drifted", {"actual": names, "expected": sorted(ARM_CONFIGS)})
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        repaired: List[Dict[str, Any]] = []
        repaired_sources = set()
        for config in ARM_CONFIGS:
            if not bool(model.ShowConfiguration2(config)):
                raise GateError("LOCAL_ARM_CONFIG_ACTIVATE_FAIL", "cannot activate arm configuration for reference repair", {"config": config})
            # Whole-tree copies can retain baked absolute source references.
            # ReplaceComponents2 is applied to the V5 copy only, once per
            # source document, and every dependency is re-audited cold below.
            while True:
                changed = False
                comps = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]
                for component in comps:
                    current = Path(str(base.value(component, "GetPathName"))).resolve()
                    if LOCAL_ARM_ROOT.resolve() in current.parents:
                        continue
                    try:
                        relative = current.relative_to(B51_DONOR_ROOT.resolve())
                    except ValueError as exc:
                        raise GateError("LOCAL_ARM_REFERENCE_SOURCE_FAIL", "arm reference is outside both canonical and V5-local trees", {"config": config, "name2": str(base.value(component, "Name2")), "path": norm(current)}) from exc
                    local = (LOCAL_ARM_ROOT / relative).resolve()
                    if not local.is_file():
                        raise GateError("LOCAL_ARM_REFERENCE_TARGET_MISSING", "localized replacement target is missing", {"source": norm(current), "target": norm(local)})
                    source_key = os.path.normcase(str(current))
                    if source_key in repaired_sources:
                        continue
                    model.ClearSelection2(True)
                    if not bool(component.Select4(False, None, False)):
                        raise GateError("LOCAL_ARM_REPLACE_SELECT_FAIL", "cannot select external arm component", {"name2": str(base.value(component, "Name2"))})
                    ok = bool(assembly.ReplaceComponents2(str(local), "", True, 2, True))
                    model.ClearSelection2(True)
                    if not ok:
                        raise GateError("LOCAL_ARM_REPLACE_FAIL", "ReplaceComponents2 rejected V5-local component", {"source": norm(current), "target": norm(local), "config": config})
                    repaired_sources.add(source_key)
                    repaired.append({"configuration": config, "source": norm(current), "target": norm(local)})
                    changed = True
                    break
                if not changed:
                    break
        driver_components = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]
        native_drivers = configure_native_arm_drivers(model, assembly, driver_components, base, types, pythoncom)
        rows = []
        for config in ARM_CONFIGS:
            if not bool(model.ShowConfiguration2(config)):
                raise GateError("LOCAL_ARM_CONFIG_ACTIVATE_FAIL", "cannot activate arm configuration", {"config": config})
            comps = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]
            matches = [item for item in comps if str(base.value(item, "Name2")).split("/")[-1] == ARM_LEGACY_GRIPPER_LEAF]
            if len(matches) != 1:
                raise GateError("LOCAL_ARM_GRIPPER_UNIQUE_FAIL", "legacy gripper occurrence is not unique", {"config": config, "count": len(matches)})
            returned = int(matches[0].SetSuppression2(SW_COMPONENT_SUPPRESSED))
            readback = int(base.value(matches[0], "GetSuppression2"))
            if readback != SW_COMPONENT_SUPPRESSED:
                raise GateError("LOCAL_ARM_GRIPPER_SUPPRESSION_FAIL", "legacy gripper did not suppress in V5 copy", {"config": config, "returned": returned, "readback": readback})
            rows.append({"configuration": config, "name2": str(base.value(matches[0], "Name2")), "suppression": readback})
        if not bool(model.ForceRebuild3(True)):
            raise GateError("LOCAL_ARM_REBUILD_FAIL", "local arm rebuild failed")
        saved = model.Save3(1, 0, 0)
        ok, outs = base.unpack(saved)
        if not bool(ok) or (outs and int(outs[0]) != 0):
            raise GateError("LOCAL_ARM_SAVE_FAIL", "local arm save failed", {"result": ok, "outs": outs})
    finally:
        close_doc(sw, model, base)
    cold, cold_open = open_doc(sw, LOCAL_ARM, SW_DOC_ASSEMBLY, True, base, types, pythoncom)
    try:
        cold_rows = []
        cold_driver_rows: Dict[str, Dict[str, Any]] = {}
        for config in ARM_CONFIGS:
            if not bool(cold.ShowConfiguration2(config)):
                raise GateError("LOCAL_ARM_COLD_CONFIG_FAIL", "cold arm configuration activation failed", {"config": config})
            comps = top_components(cold, base, types, pythoncom)
            matches = [item for item in comps if str(base.value(item, "Name2")).split("/")[-1] == ARM_LEGACY_GRIPPER_LEAF]
            link6 = [item for item in comps if str(base.value(item, "Name2")).split("/")[-1] == ARM_LINK6_LEAF]
            if len(matches) != 1 or int(base.value(matches[0], "GetSuppression2")) != SW_COMPONENT_SUPPRESSED or len(link6) != 1:
                raise GateError("LOCAL_ARM_COLD_SEMANTIC_FAIL", "cold local arm does not retain no-legacy-gripper/link6 contract", {"config": config, "gripper_count": len(matches), "link6_count": len(link6)})
            feature_map = mate_features(cold, base, types, pythoncom)
            config_driver_rows: List[Dict[str, Any]] = []
            for expected in native_drivers:
                feature = feature_map.get(expected["feature_name"])
                if feature is None or int(base.value(feature, "GetErrorCode2")) != 0 or bool(base.value(feature, "IsSuppressed")):
                    raise GateError("LOCAL_ARM_COLD_DRIVER_FEATURE_FAIL", "cold native joint driver feature is absent, errored, or suppressed", {"configuration": config, "joint": expected["joint"], "feature": expected["feature_name"]})
                definition = angle_mate_data(feature, base, types, pythoncom)
                minimum = float(base.value(definition, "MinimumAngle"))
                maximum = float(base.value(definition, "MaximumAngle"))
                dimension = angle_mate_dimension(feature, base, types, pythoncom)
                full_name = str(base.value(dimension, "FullName"))
                values = [float(value) for value in base.as_list(dimension.GetSystemValue3(SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [config]))]
                seed = next((item for item in expected["configuration_seed_readback"] if item["configuration"] == config), None)
                if (
                    not bool(base.value(definition, "IsAdvancedMate"))
                    or abs(minimum - float(expected["native_minimum_rad"])) > 1.0e-9
                    or abs(maximum - float(expected["native_maximum_rad"])) > 1.0e-9
                    or full_name != expected["dimension_full_name"]
                    or seed is None
                    or len(values) != 1
                    or abs(values[0] - float(seed["native_angle_rad"])) > 1.0e-8
                ):
                    raise GateError("LOCAL_ARM_COLD_DRIVER_READBACK_FAIL", "cold native joint driver definition/dimension/configuration differs from its live ledger", {"configuration": config, "joint": expected["joint"], "minimum": minimum, "maximum": maximum, "dimension": full_name, "values": values, "seed": seed})
                row = {
                    "joint": expected["joint"],
                    "configuration": config,
                    "feature_name": expected["feature_name"],
                    "dimension_full_name": full_name,
                    "minimum_rad": minimum,
                    "maximum_rad": maximum,
                    "native_angle_rad": values[0],
                    "feature_error_code": int(base.value(feature, "GetErrorCode2")),
                    "feature_suppressed": bool(base.value(feature, "IsSuppressed")),
                    "advanced_limit_angle": bool(base.value(definition, "IsAdvancedMate")),
                }
                config_driver_rows.append(row)
                cold_driver_rows.setdefault(expected["joint"], {"joint": expected["joint"], "configurations": []})["configurations"].append(row)
            cold_rows.append({"configuration": config, "legacy_gripper_name2": str(base.value(matches[0], "Name2")), "legacy_gripper_path": norm(Path(str(base.value(matches[0], "GetPathName")))), "legacy_gripper_suppression": int(base.value(matches[0], "GetSuppression2")), "link6_name2": str(base.value(link6[0], "Name2")), "native_joint_drivers": config_driver_rows})
        escaped = [path for path in dependency_paths(cold, base) if LOCAL_ARM_ROOT.resolve() not in Path(path).resolve().parents]
        if escaped:
            raise GateError("LOCAL_ARM_REFERENCE_ESCAPE", "localized arm dependency escapes the V5 copy", {"escaped": escaped})
    finally:
        close_doc(sw, cold, base)
    for driver in native_drivers:
        driver["cold_reopen_verified"] = True
        driver["cold_reopen"] = cold_driver_rows[driver["joint"]]
    legacy_path = Path(cold_rows[0]["legacy_gripper_path"])
    if any(Path(row["legacy_gripper_path"]).resolve() != legacy_path.resolve() for row in cold_rows) or not legacy_path.is_file() or LOCAL_ARM_ROOT.resolve() not in legacy_path.resolve().parents:
        raise GateError("LOCAL_ARM_LEGACY_PATH_FAIL", "legacy gripper whitelist path is not one exact V5-local physical file", {"rows": cold_rows})
    payload = {
        "schema": "F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V1",
        "timestamp_utc": utc_now(),
        "script_sha256": sha256(Path(__file__)),
        "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
        "source": file_fact(B51_DONOR),
        "local_arm": file_fact(LOCAL_ARM),
        "copy_proof": staged,
        "reference_repairs": repaired,
        "native_joint_drivers": native_drivers,
        "legacy_gripper_file": file_fact(legacy_path),
        "configurations": cold_rows,
        "cold_open": cold_open,
        "verdict": "V5_LOOP1E0_LOCAL_ARM_NO_LEGACY_GRIPPER_WITH_SIX_NATIVE_LIMIT_ANGLE_DRIVERS_PASS",
    }
    write_json_once(LOCAL_ARM_CHECKPOINT, payload)
    return payload


def transform_object(sw: Any, data: Sequence[float], base: Any, types: Any, pythoncom: Any) -> Any:
    from win32com.client import VARIANT
    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(value) for value in data])
    utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
    result = utility.CreateTransform(typed)
    if result is None:
        raise GateError("CREATE_TRANSFORM_FAIL", "IMathUtility.CreateTransform returned null")
    return result


def total_component_transform(component: Any, base: Any) -> Tuple[float, ...]:
    raw = base.value(component, "GetTotalTransform", False)
    if raw is None:
        raise GateError(
            "TOTAL_COMPONENT_TRANSFORM_NULL",
            "nested link-6 occurrence has no total transform",
            {"name2": str(base.value(component, "Name2"))},
        )
    data = tuple(float(value) for value in base.as_list(base.value(raw, "ArrayData")))
    if len(data) != 16 or not all(math.isfinite(value) for value in data):
        raise GateError(
            "TOTAL_COMPONENT_TRANSFORM_SHAPE_FAIL",
            "nested link-6 total transform is not a finite 16-value transform",
            {"name2": str(base.value(component, "Name2")), "array_data": list(data)},
        )
    if abs(data[12] - 1.0) > 2.0e-9:
        raise GateError(
            "TOTAL_COMPONENT_TRANSFORM_SCALE_FAIL",
            "nested link-6 total transform scale is not unity",
            {"name2": str(base.value(component, "Name2")), "scale": data[12]},
        )
    return data


def insert_component(sw: Any, model: Any, assembly: Any, path: Path, data: Sequence[float], base: Any, types: Any, pythoncom: Any) -> Any:
    preload, _ = open_doc(sw, path, SW_DOC_ASSEMBLY, True, base, types, pythoncom)
    title = str(base.value(model, "GetTitle"))
    sw.ActivateDoc3(title, False, 0, 0)
    raw = assembly.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
    if raw is None:
        close_doc(sw, preload, base)
        raise GateError("ADD_COMPONENT5_FAIL", "AddComponent5 returned null", {"path": norm(path)})
    component = base.wrap(raw, "IComponent2", types, pythoncom)
    if not bool(component.SetTransformAndSolve3(transform_object(sw, data, base, types, pythoncom), True)):
        close_doc(sw, preload, base)
        raise GateError("COMPONENT_TRANSFORM_FAIL", "SetTransformAndSolve3 failed", {"path": norm(path)})
    readback = [float(value) for value in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
    if len(readback) != 16 or max(abs(readback[index] - float(data[index])) for index in range(16)) > 2.0e-9:
        close_doc(sw, preload, base)
        raise GateError("COMPONENT_TRANSFORM_READBACK_FAIL", "component transform drifted", {"path": norm(path), "actual": readback, "expected": list(data)})
    close_doc(sw, preload, base)
    return component


def mate_features(model: Any, base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    rows: Dict[str, Any] = {}
    feature = base.value(model, "FirstFeature")
    while feature is not None:
        typed = base.wrap(feature, "IFeature", types, pythoncom)
        if str(base.value(typed, "GetTypeName2")) == "MateGroup":
            child = base.value(typed, "GetFirstSubFeature")
            while child is not None:
                item = base.wrap(child, "IFeature", types, pythoncom)
                rows[str(base.value(item, "Name"))] = item
                child = base.value(item, "GetNextSubFeature")
        feature = base.value(typed, "GetNextFeature")
    return rows


def add_lock_mate(model: Any, assembly: Any, first: Any, second: Any, name: str, base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    before = set(mate_features(model, base, types, pythoncom))
    model.ClearSelection2(True)
    if not bool(first.Select4(False, None, False)) or not bool(second.Select4(True, None, False)):
        raise GateError("MATE_ENDPOINT_SELECT_FAIL", "cannot select lock-mate endpoints", {"name": name})
    raw = assembly.AddMate3(SW_MATE_LOCK, SW_ALIGN_CLOSEST, False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
    _mate, outs = base.unpack(raw)
    error = int(outs[-1]) if outs else SW_ADD_MATE_NO_ERROR
    model.ClearSelection2(True)
    after = mate_features(model, base, types, pythoncom)
    created = set(after) - before
    if error != SW_ADD_MATE_NO_ERROR or len(created) != 1:
        raise GateError("ADD_LOCK_MATE_FAIL", "AddMate3 did not create exactly one healthy lock mate", {"name": name, "error": error, "created": sorted(created)})
    feature = after[next(iter(created))]
    feature.Name = name
    if str(base.value(feature, "Name")) != name or int(base.value(feature, "GetErrorCode2")) != 0 or bool(base.value(feature, "IsSuppressed")):
        raise GateError("LOCK_MATE_HEALTH_FAIL", "created lock mate is unhealthy", {"name": name})
    return {"name": name, "type": SW_MATE_LOCK, "endpoints": [str(base.value(first, "Name2")), str(base.value(second, "Name2"))], "feature_error_code": 0, "suppressed": False}


def set_component_config(model: Any, assembly: Any, component: Any, ref_config: str, solving: int, base: Any) -> None:
    model.ClearSelection2(True)
    if not bool(component.Select4(False, None, False)):
        raise GateError("COMP_CONFIG_SELECT_FAIL", "cannot select component for configuration property", {"name2": str(base.value(component, "Name2"))})
    ok = bool(assembly.CompConfigProperties6(SW_COMPONENT_RESOLVED, solving, SW_COMPONENT_VISIBLE, True, ref_config, False, 0))
    model.ClearSelection2(True)
    if not ok or str(base.value(component, "ReferencedConfiguration")) != ref_config or int(base.value(component, "Solving")) != solving:
        raise GateError("COMP_CONFIG_PROPERTY_FAIL", "CompConfigProperties6 did not read back", {"name2": str(base.value(component, "Name2")), "ref_config": ref_config, "solving": solving, "ok": ok, "readback_config": str(base.value(component, "ReferencedConfiguration")), "readback_solving": int(base.value(component, "Solving"))})


def configure_top(model: Any, assembly: Any, components: Mapping[str, Any], base: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    names = list(TOP_CONFIGS)
    active.Name = names[0]
    for name in names[1:]:
        if manager.AddConfiguration2(name, "Loop1E controlled top state", "", 0, "", "No q vector baked", True) is None:
            raise GateError("TOP_CONFIG_CREATE_FAIL", "cannot create top configuration", {"name": name})
    actual = [str(value) for value in base.as_list(base.value(model, "GetConfigurationNames"))]
    if set(actual) != set(names) or len(actual) != len(names):
        raise GateError("TOP_CONFIG_SET_FAIL", "top configuration set is not exact", {"actual": actual, "expected": names})
    rows = []
    for name, spec in TOP_CONFIGS.items():
        if not bool(model.ShowConfiguration2(name)):
            raise GateError("TOP_CONFIG_ACTIVATE_FAIL", "cannot activate top configuration", {"name": name})
        set_component_config(model, assembly, components["ARM"], spec["arm"], SW_COMPONENT_FLEXIBLE, base)
        set_component_config(model, assembly, components["LEFT_WING_ROOT"], spec["left_wing"], SW_COMPONENT_RIGID, base)
        set_component_config(model, assembly, components["RIGHT_WING_ROOT"], spec["right_wing"], SW_COMPONENT_RIGID, base)
        set_component_config(model, assembly, components["GRIPPER"], spec["gripper"], SW_COMPONENT_RIGID, base)
        set_component_config(model, assembly, components["HDRM"], spec["hdrm"], SW_COMPONENT_RIGID, base)
        set_component_config(model, assembly, components["CAMERA"], "MODEL_SELECTION_HOLD", SW_COMPONENT_RIGID, base)
        set_component_config(model, assembly, components["HARNESS"], "STATIC_ROUTE_OD9_HOLD", SW_COMPONENT_RIGID, base)
        if not bool(model.ForceRebuild3(True)):
            raise GateError("TOP_CONFIG_REBUILD_FAIL", "top configuration rebuild failed", {"name": name})
        rows.append({
            "configuration": name,
            **spec,
            "q_vector_written": False,
            "six_r_q_pose_proven": False,
            "loop2_joint_driver_and_readback_required": bool(spec.get("pose") in MOTION_CONTRACT_POLICY["loop2_joint_driver_and_readback_required_for"]),
            "same_physical_occurrences": {role: str(base.value(components[role], "Name2")) for role in ("LEFT_WING_ROOT", "RIGHT_WING_ROOT", "GRIPPER", "HDRM")},
        })
    if not bool(model.ShowConfiguration2("DEPLOYED_NOMINAL")):
        raise GateError("TOP_CONFIG_RESTORE_FAIL", "cannot restore DEPLOYED_NOMINAL")
    return rows


def exact_reference_gate(model: Any, components: Mapping[str, Any], base: Any) -> Dict[str, Any]:
    expected_top = {os.path.normcase(str(path.resolve())) for path in (SPACECRAFT_PRIMARY, SPACECRAFT_B601_MOUNT, LOCAL_ARM, *V5_SUBASSEMBLIES.values())}
    actual_top = [component_path(item, base) for item in components.values()]
    if Counter(actual_top) != Counter(expected_top):
        raise GateError("TOP_REFERENCE_SET_FAIL", "top-level occurrence paths are not exact", {"expected": sorted(expected_top), "actual": sorted(actual_top)})
    allowed_roots = (RUN_ROOT.resolve(), F3R2_SPACECRAFT_ROOT.resolve())
    deps = dependency_paths(model, base)
    escaped = [path for path in deps if not any(root == Path(path).resolve() or root in Path(path).resolve().parents for root in allowed_roots)]
    if escaped:
        raise GateError("TOP_REFERENCE_ESCAPE", "top assembly dependency escapes V5/protected F3R2 spacecraft roots", {"escaped": escaped})
    return {"top_level_paths": sorted(actual_top), "dependency_paths": deps, "allowed_roots": [norm(root) for root in allowed_roots], "escaped": []}


def component_name2(component: Any, base: Any) -> str:
    name = str(base.value(component, "Name2"))
    if not name:
        raise GateError("COMPONENT_NAME2_EMPTY", "component occurrence has no Name2")
    return name


def child_components(component: Any, base: Any, types: Any, pythoncom: Any) -> List[Any]:
    return [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(base.value(component, "GetChildren"))]


def component_tree(root: Any, base: Any, types: Any, pythoncom: Any) -> List[Any]:
    rows: List[Any] = []
    stack = [root]
    seen: set[str] = set()
    while stack:
        item = stack.pop()
        name = component_name2(item, base)
        if name in seen:
            continue
        seen.add(name)
        rows.append(item)
        stack.extend(reversed(child_components(item, base, types, pythoncom)))
    return rows


def component_bodies_or_empty(component: Any, base: Any, types: Any, pythoncom: Any) -> List[Any]:
    try:
        raw_bodies = base.as_list(component.GetBodies2(SW_BODY_SOLID))
    except Exception:
        return []
    rows = [base.wrap(raw, "IBody2", types, pythoncom) for raw in raw_bodies]
    if any(int(base.value(body, "GetType")) != SW_BODY_SOLID for body in rows):
        raise GateError("COMPONENT_BODY_TYPE_FAIL", "GetBodies2(swSolidBody) returned a non-solid body", {"component": component_name2(component, base)})
    return rows


def solid_components_under(root: Any, base: Any, types: Any, pythoncom: Any) -> List[Any]:
    rows: List[Any] = []
    for component in component_tree(root, base, types, pythoncom):
        suppression = int(base.value(component, "GetSuppression2"))
        leaf = component_name2(component, base).split("/")[-1]
        if suppression == SW_COMPONENT_SUPPRESSED and leaf == ARM_LEGACY_GRIPPER_LEAF:
            continue
        if suppression != SW_COMPONENT_RESOLVED:
            raise GateError("MOTION_COMPONENT_NOT_RESOLVED", "physical motion component is suppressed/lightweight/unresolved", {"component": component_name2(component, base), "suppression": suppression})
        if component_bodies_or_empty(component, base, types, pythoncom):
            rows.append(component)
    if not rows:
        raise GateError("MOTION_SOLID_SET_EMPTY", "subsystem root exposes no resolved solid occurrence", {"root": component_name2(root, base)})
    return rows


def unique_components(rows: Iterable[Any], base: Any) -> List[Any]:
    by_name = {component_name2(row, base): row for row in rows}
    return [by_name[name] for name in sorted(by_name)]


def build_component_roles(components: Mapping[str, Any], base: Any, types: Any, pythoncom: Any) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
    solids = {role: solid_components_under(components[role], base, types, pythoncom) for role in components}
    arm_moving = [item for item in solids["ARM"] if component_name2(item, base).split("/")[-1].startswith(tuple(f"B51_REF_link{index}_" for index in range(1, 7)))]
    left_panel = [item for item in solids["LEFT_WING_ROOT"] if Path(str(base.value(item, "GetPathName"))).name.upper() == "LEFT_WING_PANEL_PHYSICAL.SLDPRT"]
    right_panel = [item for item in solids["RIGHT_WING_ROOT"] if Path(str(base.value(item, "GetPathName"))).name.upper() == "RIGHT_WING_PANEL_PHYSICAL.SLDPRT"]
    if len(left_panel) != 1 or len(right_panel) != 1:
        raise GateError("WING_PANEL_OCCURRENCE_SET_FAIL", "each V5 wing root must expose exactly one physical panel occurrence", {"left": [component_name2(item, base) for item in left_panel], "right": [component_name2(item, base) for item in right_panel]})
    panel_names = {component_name2(item, base) for item in left_panel + right_panel}
    wing_root = [item for item in solids["LEFT_WING_ROOT"] + solids["RIGHT_WING_ROOT"] if component_name2(item, base) not in panel_names]
    bus = solids["SPACECRAFT_PRIMARY"] + solids["SPACECRAFT_B601_MOUNT"] + solids["B601_BASE_ADAPTER"]
    support = solids["G07_SUPPORT"] + solids["G08_SUPPORT"] + solids["MID_SUPPORT"]
    hdrm, gripper, camera, harness = solids["HDRM"], solids["GRIPPER"], solids["CAMERA"], solids["HARNESS"]
    moving = arm_moving + left_panel + right_panel + gripper + camera
    structures = bus + wing_root + support + hdrm
    objects: Dict[str, List[Any]] = {
        "ARM_MOVING": arm_moving,
        "BUS": bus,
        "WING_LEFT": left_panel,
        "WING_RIGHT": right_panel,
        "WING_ROOT": wing_root,
        "SUPPORT": support,
        "HDRM": hdrm,
        "GRIPPER": gripper,
        "CAMERA": camera,
        "HARNESS": harness,
        "MOVING_BODIES": moving,
        "STRUCTURES": structures,
    }
    if set(objects) != REQUIRED_MOTION_ROLES:
        raise GateError("MOTION_ROLE_SCHEMA_FAIL", "runtime component-role schema differs from Loop2", {"actual": sorted(objects), "expected": sorted(REQUIRED_MOTION_ROLES)})
    objects = {role: unique_components(rows, base) for role, rows in objects.items()}
    if any(not rows for rows in objects.values()):
        raise GateError("MOTION_ROLE_EMPTY", "one or more required Loop2 roles have no physical solid occurrence", {role: [component_name2(item, base) for item in rows] for role, rows in objects.items()})
    ledger = {role: [component_name2(item, base) for item in rows] for role, rows in objects.items()}
    for name, (first_role, second_role) in REQUIRED_MOTION_COMPARISONS.items():
        overlap = set(ledger[first_role]) & set(ledger[second_role])
        if overlap:
            raise GateError("MOTION_COMPARISON_ROLE_OVERLAP", "comparison endpoints contain the same occurrence", {"comparison": name, "overlap": sorted(overlap)})
    by_name = {component_name2(item, base): item for rows in objects.values() for item in rows}
    return ledger, by_name


def persist_bytes(extension: Any, entity: Any, base: Any) -> bytes:
    raw = extension.GetPersistReference3(entity)
    if raw is None:
        raise GateError("PERSIST_REFERENCE_NULL", "GetPersistReference3 returned null")
    data = bytes(raw) if isinstance(raw, (bytes, bytearray)) else bytes(int(value) & 0xFF for value in base.as_list(raw))
    if not data or int(extension.GetPersistReferenceCount3(entity)) != len(data):
        raise GateError("PERSIST_REFERENCE_COUNT_FAIL", "persistent reference byte count is empty/inconsistent", {"bytes": len(data)})
    return data


def persist_base64(extension: Any, entity: Any, base: Any) -> str:
    return base64.b64encode(persist_bytes(extension, entity, base)).decode("ascii")


def resolve_persist(extension: Any, encoded: str, base: Any, pythoncom: Any, label: str) -> Tuple[Any, Dict[str, Any]]:
    from win32com.client import VARIANT
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise GateError("PERSIST_REFERENCE_BASE64_FAIL", "persistent reference is not strict base64", {"label": label}) from exc
    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, list(data))
    obj, outs = base.unpack(extension.GetObjectByPersistReference3(typed, 0))
    error = int(outs[0]) if outs else 0
    if obj is None or error != 0 or persist_bytes(extension, obj, base) != data:
        raise GateError("PERSIST_REFERENCE_COLD_FAIL", "persistent reference did not resolve/round-trip exactly", {"label": label, "error": error})
    return obj, {"label": label, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(), "resolve_error": error, "roundtrip_exact": True}


def component_faces(component: Any, base: Any, types: Any, pythoncom: Any) -> List[Any]:
    faces: List[Any] = []
    for body in component_bodies_or_empty(component, base, types, pythoncom):
        faces.extend(base.wrap(raw, "IFace2", types, pythoncom) for raw in base.as_list(base.value(body, "GetFaces")))
    if not faces:
        raise GateError("COMPONENT_FACE_EMPTY", "solid component returned no B-rep faces", {"component": component_name2(component, base)})
    return faces


def representative_face(component: Any, base: Any, types: Any, pythoncom: Any) -> Any:
    faces = component_faces(component, base, types, pythoncom)
    areas = [(float(base.value(face, "GetArea")), index, face) for index, face in enumerate(faces)]
    if any(not math.isfinite(area) or area <= 0.0 for area, _, _ in areas):
        raise GateError("FACE_AREA_FAIL", "representative-face candidate has non-finite/non-positive area", {"component": component_name2(component, base)})
    return max(areas, key=lambda item: (item[0], -item[1]))[2]


def representative_component(rows: Sequence[Any], base: Any, types: Any, pythoncom: Any) -> Any:
    ranked = []
    for item in rows:
        area = sum(float(base.value(face, "GetArea")) for face in component_faces(item, base, types, pythoncom))
        ranked.append((area, component_name2(item, base), item))
    return sorted(ranked, key=lambda item: (-item[0], item[1]))[0][2]


def closest_body_pair(model: Any, first_rows: Sequence[Any], second_rows: Sequence[Any], base: Any, types: Any, pythoncom: Any, label: str) -> Dict[str, Any]:
    best: Optional[Dict[str, Any]] = None
    for first_component in first_rows:
        for second_component in second_rows:
            for first_body in component_bodies_or_empty(first_component, base, types, pythoncom):
                for second_body in component_bodies_or_empty(second_component, base, types, pythoncom):
                    distance, outs = base.unpack(model.ClosestDistance(first_body, second_body))
                    if distance is None or float(distance) < 0.0 or len(outs) < 2:
                        raise GateError("CLOSEST_DISTANCE_FAIL", "ClosestDistance returned no finite witness", {"label": label, "distance": distance, "outs": repr(outs)})
                    points = [[float(value) for value in base.as_list(raw)] for raw in outs[:2]]
                    if any(len(point) != 3 or not all(math.isfinite(value) for value in point) for point in points):
                        raise GateError("CLOSEST_DISTANCE_POINT_FAIL", "ClosestDistance witness point is not a finite xyz triple", {"label": label, "points": points})
                    row = {"distance_m": float(distance), "first_component": first_component, "second_component": second_component, "first_body": first_body, "second_body": second_body, "points_m": points}
                    if best is None or row["distance_m"] < best["distance_m"]:
                        best = row
    if best is None:
        raise GateError("CLOSEST_DISTANCE_EMPTY", "comparison produced no physical body pair", {"label": label})
    return best


def closest_face_on_body(body: Any, point: Sequence[float], base: Any, types: Any, pythoncom: Any) -> Any:
    faces = [base.wrap(raw, "IFace2", types, pythoncom) for raw in base.as_list(base.value(body, "GetFaces"))]
    ranked = []
    for index, face in enumerate(faces):
        values = [float(value) for value in base.as_list(face.GetClosestPointOn(float(point[0]), float(point[1]), float(point[2])))]
        if len(values) < 3 or not all(math.isfinite(value) for value in values[:3]):
            raise GateError("FACE_CLOSEST_POINT_FAIL", "IFace2.GetClosestPointOn returned no finite xyz", {"point": list(point), "values": values})
        squared = sum((values[axis] - float(point[axis])) ** 2 for axis in range(3))
        ranked.append((squared, index, face))
    if not ranked:
        raise GateError("BODY_FACE_EMPTY", "critical body has no faces")
    return min(ranked, key=lambda item: (item[0], item[1]))[2]


def total_transform_object(component: Any, base: Any, types: Any, pythoncom: Any) -> Any:
    raw = base.value(component, "GetTotalTransform", False)
    if raw is None:
        raise GateError("COMPONENT_TOTAL_TRANSFORM_NULL", "GetTotalTransform(False) returned null", {"component": component_name2(component, base)})
    return base.wrap(raw, "IMathTransform", types, pythoncom)


def relative_transform(first: Any, second: Any, base: Any, types: Any, pythoncom: Any) -> List[float]:
    first_transform = total_transform_object(first, base, types, pythoncom)
    second_transform = total_transform_object(second, base, types, pythoncom)
    inverse_raw = first_transform.IInverse()
    if inverse_raw is None:
        raise GateError("RELATIVE_TRANSFORM_INVERSE_FAIL", "IInverse returned null", {"first": component_name2(first, base)})
    inverse = base.wrap(inverse_raw, "IMathTransform", types, pythoncom)
    relative_raw = inverse.IMultiply(second_transform)
    if relative_raw is None:
        raise GateError("RELATIVE_TRANSFORM_MULTIPLY_FAIL", "IMultiply returned null")
    values = [float(value) for value in base.as_list(base.value(base.wrap(relative_raw, "IMathTransform", types, pythoncom), "ArrayData"))]
    if len(values) != 16 or not all(math.isfinite(value) for value in values) or abs(values[12] - 1.0) > 1.0e-8 or any(abs(values[index]) > 1.0e-8 for index in (13, 14, 15)):
        raise GateError("RELATIVE_TRANSFORM_SHAPE_FAIL", "relative transform is not a finite rigid 16-value ArrayData", {"values": values})
    return values


def component_by_leaf(root: Any, leaf: str, base: Any, types: Any, pythoncom: Any) -> Any:
    matches = [item for item in component_tree(root, base, types, pythoncom) if component_name2(item, base).split("/")[-1] == leaf]
    if len(matches) != 1:
        raise GateError("COMPONENT_LEAF_UNIQUE_FAIL", "nested occurrence leaf is not unique", {"root": component_name2(root, base), "leaf": leaf, "matches": [component_name2(item, base) for item in matches]})
    return matches[0]


def cylinder_axis_witness(component: Any, extension: Any, base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    candidates = []
    for index, face in enumerate(component_faces(component, base, types, pythoncom)):
        surface = base.wrap(base.value(face, "GetSurface"), "ISurface", types, pythoncom)
        if bool(surface.IsCylinder()):
            params = [float(value) for value in base.as_list(base.value(surface, "CylinderParams"))]
            if len(params) >= 7 and all(math.isfinite(value) for value in params[:7]) and params[6] > 0.0:
                candidates.append((float(base.value(face, "GetArea")), params[6], -index, face, params))
    if not candidates:
        raise GateError("AXIS_CYLINDER_FACE_EMPTY", "joint axis owner has no valid cylindrical face", {"component": component_name2(component, base)})
    _, _, _, face, params = max(candidates, key=lambda item: (item[0], item[1], item[2]))
    direction = params[3:6]
    magnitude = math.sqrt(sum(value * value for value in direction))
    if magnitude <= 0.0:
        raise GateError("AXIS_CYLINDER_DIRECTION_FAIL", "cylindrical witness direction is zero", {"component": component_name2(component, base), "params": params})
    return {
        "entity": face,
        "persist_base64": persist_base64(extension, face, base),
        "direction_xyz": [value / magnitude for value in direction],
        "cylinder_params": params,
    }


def build_joint_driver_contract(model: Any, components: Mapping[str, Any], local_arm: Mapping[str, Any], extension: Any, base: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    source = local_arm.get("native_joint_drivers")
    if not isinstance(source, list) or [row.get("joint") for row in source] != [f"joint{index}" for index in range(1, 7)]:
        raise GateError("LOCAL_ARM_DRIVER_LEDGER_FAIL", "local-arm checkpoint lacks exact joint1..joint6 native driver ledger", {"source": source})
    owner_model_raw = base.value(components["ARM"], "GetModelDoc2")
    if owner_model_raw is None:
        raise GateError("LOCAL_ARM_OWNER_MODEL_NULL", "top-level LOCAL_ARM component has no resolved model document")
    owner_model = base.wrap(owner_model_raw, "IModelDoc2", types, pythoncom)
    rows: List[Dict[str, Any]] = []
    for index, accepted in enumerate(accepted_urdf_joints(), start=1):
        source_row = source[index - 1]
        feature_name = f"V5_LOOP2_{accepted['joint'].upper()}_LIMIT_ANGLE"
        raw_feature = owner_model.FeatureByName(feature_name)
        if raw_feature is None:
            raise GateError("TOP_DRIVER_FEATURE_MISSING", "native limit-angle feature does not resolve through LOCAL_ARM", {"joint": accepted["joint"], "feature": feature_name})
        feature = base.wrap(raw_feature, "IFeature", types, pythoncom)
        definition = angle_mate_data(feature, base, types, pythoncom)
        accessed = bool(definition.AccessSelections(owner_model, None)) if hasattr(definition, "AccessSelections") else False
        if hasattr(definition, "AccessSelections") and not accessed:
            raise GateError("TOP_DRIVER_ACCESS_SELECTIONS_FAIL", "native driver definition selection access failed", {"joint": accepted["joint"]})
        try:
            entities = base.as_list(base.value(definition, "EntitiesToMate"))
        finally:
            if accessed and hasattr(definition, "ReleaseSelectionAccess"):
                definition.ReleaseSelectionAccess()
        if len(entities) != 2:
            raise GateError("TOP_DRIVER_MATE_ENTITY_SET_FAIL", "native angle driver does not expose exactly two plane entities", {"joint": accepted["joint"], "count": len(entities)})
        mate_refs, mate_owners = [], []
        for entity_raw in entities:
            entity = base.wrap(entity_raw, "IEntity", types, pythoncom)
            mate_refs.append(persist_base64(extension, entity, base))
            raw_owner = base.value(entity, "GetComponent")
            mate_owners.append(component_name2(base.wrap(raw_owner, "IComponent2", types, pythoncom), base) if raw_owner is not None else "__TOP__")
        if len(set(mate_refs)) != 2:
            raise GateError("TOP_DRIVER_MATE_ENTITY_DUPLICATE", "native angle driver plane persistent refs are not unique", {"joint": accepted["joint"]})
        axis_owner = component_by_leaf(components["ARM"], f"B51_REV_DATUM_MALE-{index}", base, types, pythoncom)
        axis = cylinder_axis_witness(axis_owner, extension, base, types, pythoncom)
        dimension = angle_mate_dimension(feature, base, types, pythoncom)
        dimension_name = str(base.value(dimension, "FullName"))
        minimum, maximum = float(base.value(definition, "MinimumAngle")), float(base.value(definition, "MaximumAngle"))
        if (
            feature_name != source_row.get("feature_name")
            or dimension_name != source_row.get("dimension_full_name")
            or not bool(base.value(definition, "IsAdvancedMate"))
            or int(base.value(feature, "GetErrorCode2")) != 0
            or bool(base.value(feature, "IsSuppressed"))
            or abs(minimum - float(accepted["lower_rad"])) > 1.0e-9
            or abs(maximum - float(accepted["upper_rad"])) > 1.0e-9
            or source_row.get("cold_reopen_verified") is not True
        ):
            raise GateError("TOP_DRIVER_LIVE_READBACK_FAIL", "native driver differs from local-arm cold checkpoint/accepted URDF", {"joint": accepted["joint"], "feature": feature_name, "dimension": dimension_name, "minimum": minimum, "maximum": maximum})
        rows.append({
            "joint": accepted["joint"],
            "dimension_owner_component_name2": component_name2(components["ARM"], base),
            "axis_owner_component_name2": component_name2(axis_owner, base),
            "native_angle_dimension_full_name": dimension_name,
            "native_limit_feature_name": feature_name,
            "sign": 1.0,
            "zero_offset_rad": 0.0,
            "native_minimum_rad": float(accepted["lower_rad"]),
            "native_maximum_rad": float(accepted["upper_rad"]),
            "accepted_axis_xyz": list(accepted["axis_xyz"]),
            "accepted_origin_xyz": list(accepted["origin_xyz"]),
            "accepted_origin_rpy": list(accepted["origin_rpy"]),
            "accepted_parent_link": accepted["parent"],
            "accepted_child_link": accepted["child"],
            "axis_entity_persist_base64": axis["persist_base64"],
            "axis_witness_geometry": "CYLINDRICAL_FACE",
            "axis_witness_cylinder_params_direction_xyz": axis["direction_xyz"],
            "axis_witness_cylinder_params": axis["cylinder_params"],
            "angle_mate_plane_entity_persist_base64": mate_refs,
            "angle_mate_plane_owner_component_name2": mate_owners,
            "driver_generation_stage": "LOOP1E_NATIVE_DRIVER_SYNTHESIS",
            "preexisting_b51_hinge_mate_used_as_driver": False,
            "cold_reopen_verified": True,
        })
    return rows


def build_motion_contract(model: Any, components: Mapping[str, Any], local_arm: Mapping[str, Any], frame_audit: Mapping[str, Any], base: Any, types: Any, pythoncom: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    extension = base.wrap(base.value(model, "Extension"), "IModelDocExtension", types, pythoncom)
    role_ledger, by_name = build_component_roles(components, base, types, pythoncom)
    role_objects = {role: [by_name[name] for name in names] for role, names in role_ledger.items()}
    comparisons = [{"name": name, "first_role": roles[0], "second_role": roles[1], "minimum_allowed_mm": 0.0} for name, roles in sorted(REQUIRED_MOTION_COMPARISONS.items())]
    critical_pairs: List[Dict[str, Any]] = []
    for comparison in comparisons:
        best = closest_body_pair(model, role_objects[comparison["first_role"]], role_objects[comparison["second_role"]], base, types, pythoncom, comparison["name"])
        first_face = closest_face_on_body(best["first_body"], best["points_m"][0], base, types, pythoncom)
        second_face = closest_face_on_body(best["second_body"], best["points_m"][1], base, types, pythoncom)
        critical_pairs.append({
            "name": "CRITICAL_" + comparison["name"],
            "comparison": comparison["name"],
            "first_component_name2": component_name2(best["first_component"], base),
            "second_component_name2": component_name2(best["second_component"], base),
            "first_persist_base64": persist_base64(extension, first_face, base),
            "second_persist_base64": persist_base64(extension, second_face, base),
            "seed_distance_mm": best["distance_m"] * 1000.0,
            "minimum_allowed_mm": 0.0,
            "selection_method": "NATIVE_CLOSEST_BODY_PAIR_THEN_IFACE2_CLOSEST_POINT",
        })
    link6 = component_by_leaf(components["ARM"], ARM_LINK6_LEAF, base, types, pythoncom)
    gripper = representative_component(role_objects["GRIPPER"], base, types, pythoncom)
    camera = representative_component(role_objects["CAMERA"], base, types, pythoncom)
    upstream_contracts = frame_audit.get("contracts", {})
    gripper_frame = upstream_contracts.get("GRIPPER", {})
    camera_frame = upstream_contracts.get("CAMERA", {})
    if not isinstance(gripper_frame, dict) or not isinstance(camera_frame, dict):
        raise GateError("END_EFFECTOR_UPSTREAM_FRAME_FAIL", "Loop1C1/Loop1D frame contracts are not present")
    end_effector = {
        "link6_component_name2": component_name2(link6, base),
        "gripper_component_name2": component_name2(gripper, base),
        "camera_component_name2": component_name2(camera, base),
        "link6_witness_persist_base64": persist_base64(extension, representative_face(link6, base, types, pythoncom), base),
        "gripper_witness_persist_base64": persist_base64(extension, representative_face(gripper, base, types, pythoncom), base),
        "camera_witness_persist_base64": persist_base64(extension, representative_face(camera, base, types, pythoncom), base),
        "source_loop1c1_receipt_sha256": sha256(LOOP1C_RECEIPT),
        "source_loop1d_receipt_sha256": sha256(LOOP1D_RECEIPT),
        "gripper_part_geometry_frame": str(gripper_frame.get("source_frame", "")),
        "gripper_assembly_origin_frame": str(gripper_frame.get("source_frame", "")),
        "top_insertion_transform_authority": str(gripper_frame.get("placement", "")),
        "expected_link6_to_gripper_transform_16": relative_transform(link6, gripper, base, types, pythoncom),
        "expected_link6_to_camera_transform_16": relative_transform(link6, camera, base, types, pythoncom),
        "loop1c1_frame_contract_sha256": hashlib.sha256(json.dumps(gripper_frame, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest().upper(),
        "loop1d_frame_contract_sha256": hashlib.sha256(json.dumps(camera_frame, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest().upper(),
        "upstream_frame_contracts": {"GRIPPER": gripper_frame, "CAMERA": camera_frame},
    }
    if any(not str(end_effector[key]).strip() for key in ("gripper_part_geometry_frame", "gripper_assembly_origin_frame", "top_insertion_transform_authority")):
        raise GateError("END_EFFECTOR_FRAME_STRING_FAIL", "upstream gripper frame contract is incomplete", {"end_effector": end_effector})
    drivers = build_joint_driver_contract(model, components, local_arm, extension, base, types, pythoncom)
    legacy = component_by_leaf(components["ARM"], ARM_LEGACY_GRIPPER_LEAF, base, types, pythoncom)
    legacy_path = Path(str(base.value(legacy, "GetPathName"))).resolve()
    if int(base.value(legacy, "GetSuppression2")) != SW_COMPONENT_SUPPRESSED or not legacy_path.is_file() or LOCAL_ARM_ROOT.resolve() not in legacy_path.parents:
        raise GateError("LEGACY_GRIPPER_WHITELIST_FAIL", "only the V5-local legacy gripper may be suppressed/nonphysical", {"name2": component_name2(legacy, base), "path": norm(legacy_path), "suppression": int(base.value(legacy, "GetSuppression2"))})
    suppressed_whitelist = [{
        "semantic_role": "LEGACY_B51_GRIPPER_DETAIL",
        "component_name2": component_name2(legacy, base),
        "component_path": norm(legacy_path),
        "component_path_sha256": sha256(legacy_path),
        "top_configurations": sorted(set(POSE_CONFIGURATION_BINDINGS.values())),
        "reason": "LEGACY_GRIPPER_REPLACED_BY_V5_LOOP1C1_NONPHYSICAL_FOR_LOOP2",
        "expected_suppression_state": SW_COMPONENT_SUPPRESSED,
        "exclude_from_motion_comparison_sets": True,
    }]
    contract = {
        "schema": "F3R2_V5_LOOP2_MOTION_CONTRACT_V1",
        "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
        "joint_drivers": drivers,
        "component_roles": role_ledger,
        "comparison_contracts": comparisons,
        "critical_face_pairs": critical_pairs,
        "expected_contact_whitelist": [],
        "pose_configurations": dict(POSE_CONFIGURATION_BINDINGS),
        "end_effector_frame_contract": end_effector,
        "contract_scope": "CAD_MAPPING_ONLY_NOT_POSE_AUTHORITY",
        "top_configuration_is_6r_q_pose_proof": False,
        "arm_referenced_configuration_is_6r_q_pose_proof": False,
        "q_vectors_written_by_loop1e": False,
        "undefined_service_q_created": False,
    }
    return contract, suppressed_whitelist


def build_top(sw: Any, frame_audit: Mapping[str, Any], local_arm: Mapping[str, Any], base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    template = Path(str(base.value(sw, "GetDocumentTemplate", SW_DOC_ASSEMBLY, "", 0, 0.0, 0.0)))
    if not template.is_file() or template.resolve() != ASSEMBLY_TEMPLATE.resolve() or sha256(template) != ASSEMBLY_TEMPLATE_SHA256:
        raise GateError("ASSEMBLY_TEMPLATE_FAIL", "GetDocumentTemplate did not return the pinned assembly template", {"actual": norm(template), "expected": norm(ASSEMBLY_TEMPLATE), "actual_sha256": sha256(template) if template.is_file() else None, "expected_sha256": ASSEMBLY_TEMPLATE_SHA256})
    raw = sw.NewDocument(str(template), 0, 0.0, 0.0)
    if raw is None:
        raise GateError("NEW_ASSEMBLY_FAIL", "NewDocument returned null")
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    components: Dict[str, Any] = {}
    try:
        if frame_audit.get("pass") is not True:
            raise GateError("FRAME_CONTRACT_EXECUTION_HOLD", "frame contracts are not fully receipted", frame_audit)
        resolved_contracts = frame_audit["contracts"]
        components["SPACECRAFT_PRIMARY"] = insert_component(sw, model, assembly, SPACECRAFT_PRIMARY, IDENTITY_T16, base, types, pythoncom)
        model.ClearSelection2(True)
        components["SPACECRAFT_PRIMARY"].Select4(False, None, False)
        assembly.FixComponent()
        model.ClearSelection2(True)
        components["SPACECRAFT_B601_MOUNT"] = insert_component(sw, model, assembly, SPACECRAFT_B601_MOUNT, IDENTITY_T16, base, types, pythoncom)
        components["ARM"] = insert_component(sw, model, assembly, LOCAL_ARM, MOUNT_T16, base, types, pythoncom)
        for role, path in V5_SUBASSEMBLIES.items():
            placement = resolved_contracts[role]["placement"]
            if placement == "LIVE_LINK6_TOTAL_TRANSFORM":
                continue
            data = IDENTITY_T16 if placement == "IDENTITY" else MOUNT_T16 if placement == "MOUNT_T16" else None
            if data is None:
                raise GateError("FRAME_PLACEMENT_ENUM_FAIL", "unsupported upstream placement", {"role": role, "placement": placement})
            components[role] = insert_component(
                sw, model, assembly, path, data, base, types, pythoncom
            )
        link6 = child_by_leaf(components["ARM"], ARM_LINK6_LEAF, base, types, pythoncom)
        link6_seed_transform = total_component_transform(link6, base)
        for role, path in V5_SUBASSEMBLIES.items():
            if resolved_contracts[role]["placement"] == "LIVE_LINK6_TOTAL_TRANSFORM":
                components[role] = insert_component(
                    sw, model, assembly, path, link6_seed_transform, base, types, pythoncom
                )
        ledgers = []
        anchor = components["SPACECRAFT_PRIMARY"]
        for role in ("SPACECRAFT_B601_MOUNT", "ARM", "B601_BASE_ADAPTER", "G07_SUPPORT", "G08_SUPPORT", "MID_SUPPORT", "LEFT_WING_ROOT", "RIGHT_WING_ROOT", "HDRM", "HARNESS"):
            ledgers.append(add_lock_mate(model, assembly, anchor, components[role], "MATE_TOP_LOCK_" + role, base, types, pythoncom))
        ledgers.append(add_lock_mate(model, assembly, link6, components["GRIPPER"], "MATE_TOP_LINK6_TO_GRIPPER", base, types, pythoncom))
        ledgers.append(add_lock_mate(model, assembly, link6, components["CAMERA"], "MATE_TOP_LINK6_TO_CAMERA", base, types, pythoncom))
        configs = configure_top(model, assembly, components, base, types, pythoncom)
        references = exact_reference_gate(model, components, base)
        if not bool(model.ForceRebuild3(True)):
            raise GateError("TOP_REBUILD_FAIL", "top assembly full rebuild failed")
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        raw_save = base.value(base.value(model, "Extension"), "SaveAs", str(TARGET), SW_SAVE_AS_CURRENT_VERSION, SW_SAVE_AS_SILENT, None, 0, 0)
        saved, outs = base.unpack(raw_save)
        if not bool(saved) or (outs and int(outs[0]) != 0):
            raise GateError("TOP_SAVE_AS_FAIL", "top SaveAs failed", {"saved": saved, "outs": outs})
        post_save_refs = exact_reference_gate(model, components, base)
        motion_contract, suppressed_whitelist = build_motion_contract(model, components, local_arm, frame_audit, base, types, pythoncom)
        result = {
            "target": file_fact(TARGET),
            "template": file_fact(template),
            "components": {role: {"name2": str(base.value(item, "Name2")), "path": str(Path(str(base.value(item, "GetPathName"))).resolve()).replace("\\", "/"), "frame_contract": dict(resolved_contracts[role])} for role, item in components.items()},
            "link6_seed_transform": list(link6_seed_transform),
            "frame_contracts": dict(frame_audit),
            "motion_contract": motion_contract,
            "suppressed_nonphysical_whitelist": suppressed_whitelist,
            "mate_ledger": ledgers,
            "configuration_ledger": configs,
            "references_pre_save": references,
            "references_post_save": post_save_refs,
            "verdict": "V5_LOOP1E_TOP_LIVE_SAVE_WITH_LOOP2_MOTION_CONTRACT_PASS",
        }
    finally:
        close_doc(sw, model, base)
    return result


def entity_owner_name2(entity_raw: Any, base: Any, types: Any, pythoncom: Any) -> str:
    entity = base.wrap(entity_raw, "IEntity", types, pythoncom)
    raw_owner = base.value(entity, "GetComponent")
    return component_name2(base.wrap(raw_owner, "IComponent2", types, pythoncom), base) if raw_owner is not None else "__TOP__"


def cold_verify_motion_contract(model: Any, assembly: Any, top_roles: Mapping[str, Any], contract: Mapping[str, Any], suppressed_whitelist: Sequence[Mapping[str, Any]], base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    if contract.get("schema") != "F3R2_V5_LOOP2_MOTION_CONTRACT_V1" or contract.get("accepted_urdf_sha256") != ACCEPTED_URDF_SHA256:
        raise GateError("COLD_MOTION_CONTRACT_SCHEMA_FAIL", "cold motion contract is not bound to exact Loop2 schema/URDF")
    if len(suppressed_whitelist) != 1:
        raise GateError("COLD_SUPPRESSED_WHITELIST_SET_FAIL", "exactly one nonphysical legacy-gripper occurrence must be whitelisted")
    whitelist = dict(suppressed_whitelist[0])
    extension = base.wrap(base.value(model, "Extension"), "IModelDocExtension", types, pythoncom)

    # Verify the exact suppression exception in every pose-bound top
    # configuration, and reject every other suppressed/lightweight/unresolved
    # occurrence.  This mirrors the Loop2 runtime gate rather than relying on a
    # receipt-only assertion.
    suppression_rows: List[Dict[str, Any]] = []
    for configuration in sorted(set(str(value) for value in contract["pose_configurations"].values())):
        if not bool(model.ShowConfiguration2(configuration)) or not bool(model.ForceRebuild3(True)):
            raise GateError("COLD_SUPPRESSION_CONFIG_FAIL", "cannot activate/rebuild pose-bound top configuration", {"configuration": configuration})
        all_components = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(False))]
        by_name = {component_name2(item, base): item for item in all_components}
        legacy = by_name.get(str(whitelist["component_name2"]))
        if legacy is None:
            raise GateError("COLD_LEGACY_GRIPPER_MISSING", "whitelisted legacy gripper Name2 does not resolve", {"configuration": configuration})
        legacy_path = Path(str(base.value(legacy, "GetPathName"))).resolve()
        legacy_state = int(base.value(legacy, "GetSuppression2"))
        if legacy_state != SW_COMPONENT_SUPPRESSED or legacy_path != Path(str(whitelist["component_path"])).resolve() or sha256(legacy_path) != str(whitelist["component_path_sha256"]):
            raise GateError("COLD_LEGACY_GRIPPER_WHITELIST_FAIL", "legacy gripper suppression/path/hash differs from exact whitelist", {"configuration": configuration, "name2": component_name2(legacy, base), "path": norm(legacy_path), "suppression": legacy_state})
        nonresolved = []
        for item in all_components:
            state = int(base.value(item, "GetSuppression2"))
            name = component_name2(item, base)
            if state != SW_COMPONENT_RESOLVED and not (name == whitelist["component_name2"] and state == SW_COMPONENT_SUPPRESSED):
                nonresolved.append({"component_name2": name, "suppression": state, "path": str(base.value(item, "GetPathName"))})
        if nonresolved:
            raise GateError("COLD_NONRESOLVED_COMPONENT_FAIL", "suppressed/lightweight/unresolved component is not the exact legacy-gripper exception", {"configuration": configuration, "components": nonresolved})
        suppression_rows.append({"configuration": configuration, "component_name2": component_name2(legacy, base), "component_path": norm(legacy_path), "component_path_sha256": sha256(legacy_path), "suppression": legacy_state, "other_nonresolved_count": 0})

    if not bool(model.ShowConfiguration2(POSE_CONFIGURATION_BINDINGS["Q_DEPLOYED_HOME"])) or not bool(model.ForceRebuild3(True)):
        raise GateError("COLD_MOTION_CONFIG_RESTORE_FAIL", "cannot restore Loop2 deployed-home mapping for cold evidence readback")
    all_components = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(False))]
    component_map = {component_name2(item, base): item for item in all_components}
    for role, names in contract["component_roles"].items():
        missing = [name for name in names if name not in component_map]
        empty = [name for name in names if name in component_map and not component_bodies_or_empty(component_map[name], base, types, pythoncom)]
        if missing or empty:
            raise GateError("COLD_MOTION_ROLE_RESOLVE_FAIL", "motion role occurrence does not resolve as a solid component", {"role": role, "missing": missing, "empty": empty})

    driver_rows: List[Dict[str, Any]] = []
    for driver in contract["joint_drivers"]:
        owner = component_map.get(str(driver["dimension_owner_component_name2"]))
        if owner is None:
            raise GateError("COLD_DRIVER_OWNER_MISSING", "native driver dimension-owner occurrence does not resolve", {"joint": driver["joint"]})
        raw_owner_model = base.value(owner, "GetModelDoc2")
        if raw_owner_model is None:
            raise GateError("COLD_DRIVER_OWNER_MODEL_NULL", "native driver owner document is unresolved", {"joint": driver["joint"]})
        owner_model = base.wrap(raw_owner_model, "IModelDoc2", types, pythoncom)
        raw_feature = owner_model.FeatureByName(str(driver["native_limit_feature_name"]))
        raw_dimension = owner_model.Parameter(str(driver["native_angle_dimension_full_name"]))
        if raw_feature is None or raw_dimension is None:
            raise GateError("COLD_DRIVER_FEATURE_DIMENSION_MISSING", "native driver feature/dimension does not cold-resolve", {"joint": driver["joint"]})
        feature = base.wrap(raw_feature, "IFeature", types, pythoncom)
        dimension = base.wrap(raw_dimension, "IDimension", types, pythoncom)
        definition = angle_mate_data(feature, base, types, pythoncom)
        minimum, maximum = float(base.value(definition, "MinimumAngle")), float(base.value(definition, "MaximumAngle"))
        if (
            str(base.value(dimension, "FullName")) != driver["native_angle_dimension_full_name"]
            or int(base.value(feature, "GetErrorCode2")) != 0
            or bool(base.value(feature, "IsSuppressed"))
            or not bool(base.value(definition, "IsAdvancedMate"))
            or abs(minimum - float(driver["native_minimum_rad"])) > 1.0e-9
            or abs(maximum - float(driver["native_maximum_rad"])) > 1.0e-9
        ):
            raise GateError("COLD_DRIVER_READBACK_FAIL", "native driver feature/dimension/advanced limits differ from contract", {"joint": driver["joint"], "minimum": minimum, "maximum": maximum})
        accessed = bool(definition.AccessSelections(owner_model, owner)) if hasattr(definition, "AccessSelections") else False
        if hasattr(definition, "AccessSelections") and not accessed:
            raise GateError("COLD_DRIVER_ACCESS_SELECTIONS_FAIL", "cold native driver definition selection access failed", {"joint": driver["joint"]})
        try:
            entities = base.as_list(base.value(definition, "EntitiesToMate"))
        finally:
            if accessed and hasattr(definition, "ReleaseSelectionAccess"):
                definition.ReleaseSelectionAccess()
        actual_pairs = sorted((hashlib.sha256(persist_bytes(extension, entity, base)).hexdigest().upper(), entity_owner_name2(entity, base, types, pythoncom)) for entity in entities)
        expected_pairs = sorted((hashlib.sha256(base64.b64decode(encoded, validate=True)).hexdigest().upper(), owner_name) for encoded, owner_name in zip(driver["angle_mate_plane_entity_persist_base64"], driver["angle_mate_plane_owner_component_name2"]))
        if len(entities) != 2 or actual_pairs != expected_pairs:
            raise GateError("COLD_DRIVER_ENDPOINT_REF_FAIL", "native angle mate endpoint refs/owners differ after cold reopen", {"joint": driver["joint"], "actual": actual_pairs, "expected": expected_pairs})
        axis_obj, axis_ref = resolve_persist(extension, str(driver["axis_entity_persist_base64"]), base, pythoncom, f"{driver['joint']}.axis")
        axis_owner = entity_owner_name2(axis_obj, base, types, pythoncom)
        axis_face = base.wrap(axis_obj, "IFace2", types, pythoncom)
        axis_surface = base.wrap(base.value(axis_face, "GetSurface"), "ISurface", types, pythoncom)
        params = [float(value) for value in base.as_list(base.value(axis_surface, "CylinderParams"))] if bool(axis_surface.IsCylinder()) else []
        direction = params[3:6] if len(params) >= 7 else []
        norm_direction = math.sqrt(sum(value * value for value in direction)) if len(direction) == 3 else 0.0
        expected_direction = [float(value) for value in driver["axis_witness_cylinder_params_direction_xyz"]]
        parallel = abs(sum((direction[index] / norm_direction) * expected_direction[index] for index in range(3))) if norm_direction > 0.0 else 0.0
        if axis_owner != driver["axis_owner_component_name2"] or len(params) < 7 or params[6] <= 0.0 or abs(norm_direction - 1.0) > 1.0e-6 or abs(parallel - 1.0) > 1.0e-6:
            raise GateError("COLD_DRIVER_AXIS_WITNESS_FAIL", "cold cylindrical axis witness geometry/owner differs from contract", {"joint": driver["joint"], "axis_owner": axis_owner, "params": params, "parallel": parallel})
        driver_rows.append({"joint": driver["joint"], "dimension_owner_component_name2": component_name2(owner, base), "axis_owner_component_name2": axis_owner, "feature_name": str(base.value(feature, "Name")), "dimension_full_name": str(base.value(dimension, "FullName")), "minimum_rad": minimum, "maximum_rad": maximum, "advanced": True, "mate_entity_ref_owner_pairs": actual_pairs, "axis_persistent_reference": axis_ref, "pass": True})

    persistent_rows: List[Dict[str, Any]] = []
    for pair in contract["critical_face_pairs"]:
        for field, expected_owner in (("first_persist_base64", pair["first_component_name2"]), ("second_persist_base64", pair["second_component_name2"])):
            obj, fact = resolve_persist(extension, str(pair[field]), base, pythoncom, f"{pair['name']}.{field}")
            owner = entity_owner_name2(obj, base, types, pythoncom)
            if owner != expected_owner:
                raise GateError("COLD_CRITICAL_FACE_OWNER_FAIL", "critical face persistent witness owner differs after cold reopen", {"pair": pair["name"], "field": field, "actual": owner, "expected": expected_owner})
            persistent_rows.append({**fact, "owner_component_name2": owner})
    ee = contract["end_effector_frame_contract"]
    for key in ("link6", "gripper", "camera"):
        obj, fact = resolve_persist(extension, str(ee[f"{key}_witness_persist_base64"]), base, pythoncom, f"end_effector.{key}")
        owner = entity_owner_name2(obj, base, types, pythoncom)
        if owner != ee[f"{key}_component_name2"]:
            raise GateError("COLD_END_EFFECTOR_WITNESS_OWNER_FAIL", "end-effector witness owner differs after cold reopen", {"key": key, "actual": owner, "expected": ee[f"{key}_component_name2"]})
        persistent_rows.append({**fact, "owner_component_name2": owner})
    link6, gripper, camera = (component_map[str(ee[f"{key}_component_name2"])] for key in ("link6", "gripper", "camera"))
    actual_gripper = relative_transform(link6, gripper, base, types, pythoncom)
    actual_camera = relative_transform(link6, camera, base, types, pythoncom)
    gripper_error = max(abs(actual - float(expected)) for actual, expected in zip(actual_gripper, ee["expected_link6_to_gripper_transform_16"]))
    camera_error = max(abs(actual - float(expected)) for actual, expected in zip(actual_camera, ee["expected_link6_to_camera_transform_16"]))
    if gripper_error > 1.0e-7 or camera_error > 1.0e-7:
        raise GateError("COLD_END_EFFECTOR_TRANSFORM_FAIL", "link6-to-gripper/camera relative transform differs after cold reopen", {"gripper_max_error": gripper_error, "camera_max_error": camera_error})
    return {
        "schema": contract["schema"],
        "accepted_urdf_sha256": contract["accepted_urdf_sha256"],
        "native_joint_drivers": driver_rows,
        "persistent_reference_roundtrips": persistent_rows,
        "suppressed_nonphysical_whitelist_readback": suppression_rows,
        "end_effector_relative_transform_readback": {"link6_to_gripper_transform_16": actual_gripper, "link6_to_camera_transform_16": actual_camera, "gripper_max_error": gripper_error, "camera_max_error": camera_error},
        "component_role_count": len(contract["component_roles"]),
        "comparison_count": len(contract["comparison_contracts"]),
        "critical_face_pair_count": len(contract["critical_face_pairs"]),
        "verdict": "V5_LOOP1E_LOOP2_MOTION_CONTRACT_COLD_READBACK_PASS",
    }


def cold_verify(sw: Any, expected: Dict[str, Any], base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    model, opened = open_doc(sw, TARGET, SW_DOC_ASSEMBLY, True, base, types, pythoncom)
    try:
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        comps = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]
        by_path = {component_path(item, base): item for item in comps}
        role_map = {role: by_path[os.path.normcase(str(Path(data["path"]).resolve()))] for role, data in expected["components"].items()}
        refs = exact_reference_gate(model, role_map, base)
        configs = []
        for name, spec in TOP_CONFIGS.items():
            if not bool(model.ShowConfiguration2(name)) or not bool(model.ForceRebuild3(True)):
                raise GateError("TOP_COLD_CONFIG_FAIL", "cold configuration activation/rebuild failed", {"name": name})
            row = {"configuration": name, "arm": str(base.value(role_map["ARM"], "ReferencedConfiguration")), "left_wing": str(base.value(role_map["LEFT_WING_ROOT"], "ReferencedConfiguration")), "right_wing": str(base.value(role_map["RIGHT_WING_ROOT"], "ReferencedConfiguration")), "gripper": str(base.value(role_map["GRIPPER"], "ReferencedConfiguration")), "hdrm": str(base.value(role_map["HDRM"], "ReferencedConfiguration")), "q_vector_written": False, "six_r_q_pose_proven": False, "loop2_joint_driver_and_readback_required": bool(spec.get("pose") in MOTION_CONTRACT_POLICY["loop2_joint_driver_and_readback_required_for"])}
            wanted = {key: spec[key] for key in ("arm", "left_wing", "right_wing", "gripper", "hdrm")}
            if any(row[key] != wanted[key] for key in wanted):
                raise GateError("TOP_COLD_CONFIG_READBACK_FAIL", "cold referenced configuration drifted", {"name": name, "actual": row, "expected": wanted})
            configs.append(row)
        ledger = []
        for name, feature in mate_features(model, base, types, pythoncom).items():
            if name.startswith("MATE_TOP_"):
                ledger.append({"name": name, "error": int(base.value(feature, "GetErrorCode2")), "suppressed": bool(base.value(feature, "IsSuppressed"))})
        if len(ledger) != len(expected["mate_ledger"]) or any(row["error"] != 0 or row["suppressed"] for row in ledger):
            raise GateError("TOP_COLD_MATE_LEDGER_FAIL", "cold mate set is not exact and healthy", {"ledger": ledger, "expected_count": len(expected["mate_ledger"])})
        motion_readback = cold_verify_motion_contract(model, assembly, role_map, expected["motion_contract"], expected["suppressed_nonphysical_whitelist"], base, types, pythoncom)
        if sha256(TARGET) != expected["target"]["sha256"]:
            raise GateError("TOP_COLD_HASH_DRIFT", "target hash changed during cold reopen")
        return {"open": opened, "references": refs, "configuration_ledger": configs, "mate_ledger": sorted(ledger, key=lambda row: row["name"]), "motion_contract_readback": motion_readback, "suppressed_nonphysical_whitelist": expected["suppressed_nonphysical_whitelist"], "target": file_fact(TARGET), "verdict": "V5_LOOP1E_TOP_COLD_REOPEN_WITH_LOOP2_CONTRACT_PASS"}
    finally:
        close_doc(sw, model, base)


def protected_snapshot() -> List[Dict[str, Any]]:
    rows = audit_protected()
    if not all(row["pass"] for row in rows):
        raise GateError("PROTECTED_HASH_FAIL", "protected spacecraft/B51 input drifted", rows)
    return rows


def close_owned(sw: Any, base: Any) -> None:
    guard = 0
    while int(base.value(sw, "GetDocumentCount")) and guard < 200:
        active = base.value(sw, "ActiveDoc")
        if active is None:
            break
        sw.CloseDoc(str(base.value(active, "GetTitle")))
        guard += 1
    if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
        raise GateError("DOCUMENT_CLEANUP_FAIL", "owned SOLIDWORKS documents remain open", {"document_count": int(base.value(sw, "GetDocumentCount"))})


def checkpoint_payload(audit: Dict[str, Any], local_arm: Dict[str, Any], build: Dict[str, Any], cold: Dict[str, Any]) -> Dict[str, Any]:
    return {"schema": "F3R2_V5_LOOP1E_TOP_CHECKPOINT_V1", "timestamp_utc": utc_now(), "script_sha256": sha256(Path(__file__)), "accepted_urdf_sha256": ACCEPTED_URDF_SHA256, "upstream_receipt_hashes": {row["stage"]: row["actual_sha256"] for row in audit["upstream_receipts"]}, "local_arm_checkpoint": file_fact(LOCAL_ARM_CHECKPOINT), "local_arm": local_arm["local_arm"], "target": build["target"], "frame_contracts": audit["frame_contracts"], "motion_contract": build["motion_contract"], "suppressed_nonphysical_whitelist": build["suppressed_nonphysical_whitelist"], "build": build, "cold_reopen": cold, "verdict": "V5_LOOP1E_TOP_CHECKPOINT_COLD_REOPEN_WITH_LOOP2_CONTRACT_PASS"}


def manifest_text(paths: Sequence[Path]) -> str:
    rows = []
    for path in paths:
        label = path.relative_to(RUN_ROOT).as_posix() if RUN_ROOT.resolve() in path.resolve().parents else norm(path)
        rows.append(f"{sha256(path)}  {path.stat().st_size}  {label}")
    return "\n".join(sorted(rows)) + "\n"


def failure_receipt(result: Mapping[str, Any]) -> Optional[Path]:
    path = VALIDATION / ("V5_LOOP1E_FAIL_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + ".json")
    try:
        write_json_once(path, result)
        return path
    except Exception:
        return None


def execute() -> int:
    result: Dict[str, Any] = {"schema": "F3R2_V5_LOOP1E_TOP_ASSEMBLY_RECEIPT_V1", "timestamp_start_utc": utc_now(), "target": norm(TARGET), "motion_contract_policy": dict(MOTION_CONTRACT_POLICY), "motion_contract": {"status": "PENDING_RUNTIME_NATIVE_DRIVER_AND_PERSISTENT_EVIDENCE"}, "q_vectors_written": False, "native_driver_seed_values_written": False, "undefined_service_q_created": False, "top_configuration_is_6r_q_pose_proof": False}
    sw = types = pythoncom = base = None
    try:
        audit = static_audit()
        result["static_audit"] = audit
        result["frame_contracts"] = audit["frame_contracts"]
        if not audit["execution_authorized"]:
            raise GateError("LOOP1E_STATIC_EXECUTION_HOLD", "static audit is PENDING/HOLD", audit)
        pre = protected_snapshot()
        result["protected_pre"] = pre
        base = load_base()
        result["memory_samples_gib"] = base.memory_gate()
        sw, types, pythoncom, session = base.attach_empty_session()
        result["solidworks"] = session
        loop1 = load_json(LOOP1_RECEIPT)
        expected_pid = int(loop1.get("solidworks", {}).get("pid", -1))
        if int(session["pid"]) != expected_pid:
            raise GateError("SESSION_B_PID_BINDING_FAIL", "live process is not the fixed Session B", {"live": session["pid"], "expected": expected_pid})
        staged = stage_local_arm_copy()
        local_arm = configure_local_arm(sw, staged, base, types, pythoncom)
        result["local_arm"] = local_arm
        state = checkpoint_state()
        if state["state"] == "PENDING_NEW":
            build = build_top(sw, audit["frame_contracts"], local_arm, base, types, pythoncom)
            cold = cold_verify(sw, build, base, types, pythoncom)
            checkpoint = checkpoint_payload(audit, local_arm, build, cold)
            write_json_once(CHECKPOINT, checkpoint)
        elif state["state"] == "RESUME_COLD_REOPEN":
            checkpoint = load_json(CHECKPOINT)
            build = checkpoint["build"]
            cold = cold_verify(sw, build, base, types, pythoncom)
            if cold["target"]["sha256"] != checkpoint["target"]["sha256"]:
                raise GateError("CHECKPOINT_RESUME_DRIFT", "resume cold readback differs from checkpoint")
        else:
            raise GateError("TARGET_CHECKPOINT_STATE_HOLD", "target/checkpoint state is not executable", state)
        result["checkpoint"] = checkpoint
        result["cold_reopen"] = cold
        close_owned(sw, base)
        post = protected_snapshot()
        result["protected_post"] = post
        if pre != post:
            raise GateError("PROTECTED_POST_DRIFT", "protected spacecraft/B51 assets changed")
        if sha256(Path(__file__)) != audit["script"]["sha256"]:
            raise GateError("SCRIPT_TOCTOU_FAIL", "executing Loop1E script changed")
        if SCRIPT_COPY.exists():
            if sha256(SCRIPT_COPY) != sha256(Path(__file__)):
                raise GateError("SCRIPT_COPY_DRIFT", "existing V5 Loop1E script copy differs")
        else:
            shutil.copy2(Path(__file__).resolve(), SCRIPT_COPY)
        paths = [TARGET, CHECKPOINT, LOCAL_ARM, LOCAL_ARM_CHECKPOINT, SCRIPT_COPY, *(Path(row["path"]) for row in audit["upstream_receipts"]), *V5_SUBASSEMBLIES.values()]
        text = manifest_text(paths)
        if FINAL_MANIFEST.exists():
            if FINAL_MANIFEST.read_text(encoding="utf-8") != text:
                raise GateError("FINAL_MANIFEST_DRIFT", "existing Loop1E manifest differs")
        else:
            write_text_once(FINAL_MANIFEST, text)
        result.update({"timestamp_end_utc": utc_now(), "target_fact": file_fact(TARGET), "manifest": file_fact(FINAL_MANIFEST), "same_physical_wing_occurrences_all_configurations": True, "same_physical_gripper_occurrence_all_configurations": True, "same_physical_hdrm_occurrence_all_configurations": True, "frame_contracts": audit["frame_contracts"], "motion_contract": build["motion_contract"], "suppressed_nonphysical_whitelist": build["suppressed_nonphysical_whitelist"], "motion_contract_cold_readback": cold["motion_contract_readback"], "top_configuration_is_6r_q_pose_proof": False, "arm_referenced_configuration_is_6r_q_pose_proof": False, "q_vectors_written": False, "native_driver_seed_values_written": True, "undefined_service_q_created": False, "verdict": "V5_LOOP1E_NATIVE_TOP_ASSEMBLY_LOOP2_CONTRACT_COLD_REOPEN_PASS", "remaining_holds": ["LOOP2_AUTHORIZED_Q_COMMAND_AND_SIX_JOINT_ANGLE_READBACK_REQUIRED", "LOOP2_NATIVE_INTERFERENCE_CLEARANCE_AND_EXPECTED_CONTACT_AUDIT_PENDING", "Q_SERVICE_READY_RATIFICATION_HOLD", "RELEASE_SEQUENCE_NOT_AUTHORIZED_BY_Q_RELEASE_CLEAR_END_STATE", "PACK_AND_GO_FINAL_SELF_CONTAINMENT_PENDING", "HUMAN_SOLIDWORKS_VISUAL_REVIEW_PENDING"]})
        write_json_once(FINAL_RECEIPT, result)
        print(json.dumps({"verdict": result["verdict"], "target": file_fact(TARGET), "receipt": file_fact(FINAL_RECEIPT), "solidworks_document_count": int(base.value(sw, "GetDocumentCount"))}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        result.update({"timestamp_end_utc": utc_now(), "verdict": getattr(exc, "code", "V5_LOOP1E_UNEXPECTED_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc()})
        failure = failure_receipt(result)
        if failure:
            result["failure_receipt"] = file_fact(failure)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    finally:
        if sw is not None and base is not None:
            try:
                close_owned(sw, base)
            except Exception:
                pass
        sw = None
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F3R2 V5 Loop-1E native top assembly")
    parser.add_argument("command", choices=("audit", "execute"))
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        report = static_audit()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["verdict"] in {"V5_LOOP1E_STATIC_EXECUTION_READY", "V5_LOOP1E_STATIC_PENDING_UPSTREAM"} else 2
    return execute()


if __name__ == "__main__":
    sys.exit(main())
