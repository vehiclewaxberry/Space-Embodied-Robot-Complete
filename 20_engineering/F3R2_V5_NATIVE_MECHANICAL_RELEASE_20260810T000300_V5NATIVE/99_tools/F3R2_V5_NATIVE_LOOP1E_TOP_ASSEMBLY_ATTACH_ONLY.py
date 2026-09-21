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
import ast
import base64
from contextlib import contextmanager
import ctypes
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
RUN_ROOT = ENGINEERING / "F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
sys.path.insert(0, str(RUN_ROOT / "99_tools"))
VALIDATION = RUN_ROOT / "13_validation"
RELEASE = RUN_ROOT / "14_release"
TOP_DIR = RUN_ROOT / "03_top_assembly"
TARGET = TOP_DIR / "SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM"
CHECKPOINT = VALIDATION / "V5_LOOP1E_CHECKPOINT_TOP_ASSEMBLY.json"
PRECOMMIT = VALIDATION / "V5_LOOP1E_TOP_ASSEMBLY_PRECOMMIT.json"
FINAL_RECEIPT = VALIDATION / "V5_LOOP1E_TOP_ASSEMBLY_RECEIPT.json"
FINAL_MANIFEST = RELEASE / "V5_LOOP1E_TOP_ASSEMBLY_MANIFEST_SHA256.txt"
RUN_LOCK = VALIDATION / ".V5_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.lock"
STAGING_ISOLATION_GLOB = "V5_LOOP1E_STAGING_ISOLATION_*.json"
SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py"
ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")
ASSEMBLY_TEMPLATE_SHA256 = "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC"

BASE_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_SHA256 = "E44BC52CFBDECCC107E361ACB0EDD993EFC46248EB663A994564B77BDA30F906"

G0_READY = ENGINEERING / "_MFINAL_G0_SMOKE_20260809T172928_P4E8/G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json"
LOOP1_RECEIPT = VALIDATION / "V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
LOOP1A_RECEIPT = VALIDATION / "V5_LOOP1A_SUBASSEMBLY_RECEIPT.json"
LOOP1B_RECEIPT = VALIDATION / "V5_LOOP1B_WING_ROOT_RECEIPT.json"
LOOP1C_RECEIPT = VALIDATION / "V5_LOOP1C1_GRIPPER_ASSEMBLY_RECEIPT.json"
LOOP1D_RECEIPT = VALIDATION / "V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json"
SOLAR_PROMOTION = VALIDATION / "V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT.json"
SOLAR_PROMOTION_SHA256 = "71952A7AC8761D59BB4596381C1DABD873AE2EFD0B7B8F502A0A95187349A334"
SOLAR_ATTEMPT_ROOT = VALIDATION / "solar_r2_attempts/20260813T123100Z_P9E9"
SOLAR_BUILD_RECEIPT = SOLAR_ATTEMPT_ROOT / "evidence/BUILD_STAGE_RECEIPT.json"
SOLAR_BUILD_RECEIPT_SHA256 = "6537E44BF91E92EC747EA4335BE6E96D2D6BCABC5FBB3BA692C132D2C153EF62"
SOLAR_FRESH_RECEIPT = SOLAR_ATTEMPT_ROOT / "evidence/F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_PASS.json"
SOLAR_FRESH_RECEIPT_SHA256 = "1E4AC41F97317F0D16A8113CCDA79117B4AC08A026F9E5ED39E0F64E569EA753"
SOLAR_CAD_MANIFEST = SOLAR_ATTEMPT_ROOT / "evidence/CAD_MANIFEST.json"
SOLAR_CAD_MANIFEST_SHA256 = "A4DE956E98D2A282078AC97E943E170B15262819D4FB14C25B164ED279E87FAA"
SOLAR_HANDOFF = SOLAR_ATTEMPT_ROOT / "evidence/FRESH_PID_VERIFIER_HANDOFF.json"
SOLAR_HANDOFF_SHA256 = "3A894DBADD5FE3D64E005D1999C0B4FC6F8A534DCE66D9D06FEF7134A222B8CD"
SOLAR_TREE_SHA256 = "B545B299FDD681226CE36451A4587D228E94A71EA50FE84098D0674EB60C1DF7"
SOLAR_INPUT_COMMITMENT_SHA256 = "41149896DC47356A44278FBF088CBF5A35E0FA16FAB7F924FF191B3C44548291"
SOLAR_CONTRACT_SHA256 = "B885E6B4F51663DC268FE6C9F5E497B99A514BE1706B616C230D5D35A2D697FB"
SOLAR_LEFT = SOLAR_ATTEMPT_ROOT / "cad/sides/L_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM"
SOLAR_RIGHT = SOLAR_ATTEMPT_ROOT / "cad/sides/R_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM"
SOLAR_SIDE_SHA256 = {
    "L": "4074EC7906FFE0BB029311006A1E771D343F31512D36A081BAFA44CFB410E29B",
    "R": "C11335A47CB1A04B0D8B7DD1559DF0C8EEB0D482CA0DDC6C2E29448BD464CB48",
}
LEGACY_SOLAR_DENY_PATHS = (
    RUN_ROOT / "02_native_subassemblies/LEFT_WING_ROOT_TRUE_HINGE.SLDASM",
    RUN_ROOT / "02_native_subassemblies/RIGHT_WING_ROOT_TRUE_HINGE.SLDASM",
    RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_WING_PANEL_PHYSICAL.SLDPRT",
    RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_WING_PANEL_PHYSICAL.SLDPRT",
)
LEGACY_SOLAR_DENY_LEAVES = frozenset(path.name.upper() for path in LEGACY_SOLAR_DENY_PATHS)
SOLAR_STATES = (
    "SOLAR_STOWED", "SOLAR_DEPLOY_STAGE1", "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL", "SOLAR_LEFT_FAIL", "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
)

# Existing immutable receipts are exact.  Pending receipt hashes MUST be
# replaced with their final SHA-256 values after those write-once receipts are
# produced.  ``None`` is an explicit PENDING gate, never a wildcard.
UPSTREAM_RECEIPTS: Tuple[Dict[str, Any], ...] = (
    {"stage": "G0", "path": G0_READY, "sha256": "58F8240B1D158867C1B61B09B4A098F5AB670141A3CFEE983F5AD2A637CA5CA6", "schema": None, "verdict": "G0_SOLIDWORKS_NATIVE_EXECUTION_READY"},
    {"stage": "LOOP1", "path": LOOP1_RECEIPT, "sha256": "9FC8D1DBBBDD7D1FE37F5FCCA4359838827282A0D7A961D8EEB511E75BE7160D", "schema": "F3R2_V5_LOOP1_NEUTRAL_IMPORT_RECEIPT_V1", "verdict": "V5_LOOP1_NEUTRAL_NATIVE_PART_IMPORT_PASS"},
    {"stage": "LOOP1A", "path": LOOP1A_RECEIPT, "sha256": "F946A361A7CFF8143753853911F23178AF68592D2F7BBE09990575ED86E9BF49", "schema": "F3R2_V5_LOOP1A_SUBASSEMBLY_RECEIPT_V2", "verdict": "V5_LOOP1A_ADAPTER_SUPPORT_SUBASSEMBLIES_PASS"},
    {"stage": "LOOP1B", "path": LOOP1B_RECEIPT, "sha256": "3D0FB60D5FEDD67CCBE45491953A7C4DDE4607D4321E74AA282422F309518D0D", "schema": "F3R2_V5_LOOP1B_WING_ROOT_RECEIPT_V1", "verdict": "V5_LOOP1B_DUAL_WING_ROOT_NATIVE_CLOSURE_PASS"},
    {"stage": "LOOP1C", "path": LOOP1C_RECEIPT, "sha256": "A20F0A441680C9E771DA70B0E58DE68F406BA1A66D5020A1CA5953410D6F7621", "schema": "F3R2_V5_LOOP1C1_GRIPPER_ASSEMBLY_RECEIPT_V1", "verdict": "V5_LOOP1C1_NATIVE_GRIPPER_ASSEMBLY_PASS_MECHANICAL_MAINLINE_FREEZE_READY"},
    {"stage": "LOOP1D", "path": LOOP1D_RECEIPT, "sha256": "ACE6E05C8BE56543EFE71CF7A7C72873145CC1D1173F21B912685DF2511F2E5B", "schema": "F3R2_V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT_V1", "verdict": "V5_LOOP1D_HDRM_CAMERA_HARNESS_NATIVE_FUNCTIONAL_INTERFACE_PASS"},
    {"stage": "SOLAR_R2B_P9_PROMOTION", "path": SOLAR_PROMOTION, "sha256": SOLAR_PROMOTION_SHA256, "schema": "F3R2_V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT_V1", "verdict": "V5_SOLAR_R2B_A_LOGICALLY_PROMOTED_IN_PLACE_FOR_TOP_INTEGRATION"},
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
# Donor corrected to the F3R2-frozen canonical B51 copy: the July export only
# carries ["默认"], while the script's ARM_CONFIGS contract requires
# ("默认", "STOWED_O13V3") — direct read-only probes on 2026-08-11 showed
# JULY=["默认"] vs F3R2_COPY=["STOWED_O13V3","默认"]. Source stays read-only;
# staging copies pairwise and registers the source hash as protected_source.
B51_DONOR_ROOT = ENGINEERING / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/B601_ARM_B51_COPY"
B51_DONOR = B51_DONOR_ROOT / "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
# Lineage roots whose baked absolute references may appear inside the donor
# copy (the F3R2 copy is itself a whole-tree copy of the F3R1 copy, which was
# made from the July export). Their tree layouts are identical, so references
# into them are rebased by relative path into the V5-local staged tree.
F3R1_B51_COPY_ROOT = ENGINEERING / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/B601_ARM_B51_COPY"
JULY_B51_DONOR_ROOT = ENGINEERING / "cad/B5_1_B601_interface_closure_candidate/03_CAD/native_articulated/B51_ARTICULATED_20260728T008"

PROTECTED: Tuple[Tuple[str, Path, str], ...] = (
    ("f3r2_frozen_top", F3R2_FROZEN_TOP, "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0"),
    ("f3r2_spacecraft_top_authority", F3R2_SPACECRAFT_TOP, "8D4762F50EF1E2DF0C5C55127F65E688A1A7B31B09C2A75D993052B18BDC40D4"),
    ("f3r2_primary_structure", SPACECRAFT_PRIMARY, "EEFED6D3C76603F65F598FC14D3DA927EB4533E48165A2D0529095022D532423"),
    ("f3r2_b601_mount_load_path", SPACECRAFT_B601_MOUNT, "ADCAA1C11944341DBFC9FDD36D9725B824102B3872A8F4E31EF32F62CC567D15"),
    ("b51_articulated_arm_donor", B51_DONOR, "597C297526BC4111C3424535139B8A1C93906E7A799FF5346D030700FEF1A32F"),
)

# B51 is localized because its protected donor contains the legacy gripper
# detail which would be a duplicate of Loop-1C1.  Only the V5 copy is edited.
LOCAL_ARM_ROOT = TOP_DIR / "_native_donor_local/B51_ARTICULATED_20260728T008"
LOCAL_ARM = LOCAL_ARM_ROOT / "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
LOCAL_ARM_CHECKPOINT_V1 = VALIDATION / "V5_LOOP1E0_LOCAL_ARM_NO_LEGACY_GRIPPER_CHECKPOINT.json"
LOCAL_ARM_CHECKPOINT_V1_SHA256 = "E2A6113E48B07600ACA1B6BB60AAD249D20505922B9FA232A5BA394557E1E9BC"
LOCAL_ARM_CHECKPOINT = VALIDATION / "V5_LOOP1E0_LOCAL_ARM_INDEPENDENT_CHECKPOINT_V2.json"
LOCAL_ARM_CHECKPOINT_SHA256 = "C8BF1E2E23756AF0A50EB9FDB6BE4CEBC8688C530EB451965FA080906A175893"
LOCAL_ARM_CONTRACT_SHA256 = "E5677AA28F2FE36A55B320BFFDCE5EC11649DC568CA5F9FF7037291CF5698FB2"
LOCAL_ARM_SHA256 = "D794CCFB52CFBF858B99172D6A41119B56271ECC3B3E018E48C30FA19703947A"
ARM_CONFIGS = ("默认", "STOWED_O13V3")
ARM_LEGACY_GRIPPER_LEAF = "B51_REF_gripper_detail_LINKLOCAL-1"
ARM_LINK6_LEAF = "B51_REF_link6_LINKLOCAL-1"
HDRM_PROXY_LEAF_PREFIX = "ARM_HDRM_LATCH_SLIDER-"

V5_SUBASSEMBLIES: Mapping[str, Path] = {
    "B601_BASE_ADAPTER": RUN_ROOT / "02_native_subassemblies/B601_BASE_ADAPTER_REV_B2.SLDASM",
    "G07_SUPPORT": RUN_ROOT / "02_native_subassemblies/G07_PRIMARY_SUPPORT_V2.SLDASM",
    "G08_SUPPORT": RUN_ROOT / "02_native_subassemblies/G08_PRIMARY_SUPPORT_V2.SLDASM",
    "MID_SUPPORT": RUN_ROOT / "02_native_subassemblies/MID_BACKUP_SUPPORT_V2.SLDASM",
    "LEFT_SOLAR_ARRAY": SOLAR_LEFT,
    "RIGHT_SOLAR_ARRAY": SOLAR_RIGHT,
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
    "LEFT_SOLAR_ARRAY": IDENTITY_T16,
    "RIGHT_SOLAR_ARRAY": IDENTITY_T16,
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
    "LEFT_SOLAR_ARRAY": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
    "RIGHT_SOLAR_ARRAY": {"source_frame": "SPACECRAFT_WORLD", "placement": "IDENTITY"},
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
    "Q_DEPLOYED_HOME": "SOLAR_DEPLOYED_NOMINAL",
    "Q_RELEASE_CLEAR": "RELEASE_CLEAR_END_STATE",
    "Q_SERVICE_READY": "SERVICE",
    "Q_STOW_ENGINEERING_CANDIDATE": "SOLAR_STOWED",
    "SOLAR_DEPLOY_ARM_LOCKED": "SOLAR_DEPLOY_ARM_LOCKED",
    "HDRM_RELEASE": "HDRM_RELEASE",
}

# P9 live top vocabulary; earlier single-panel state names are prohibited.
TOP_CONFIGS: Mapping[str, Dict[str, Any]] = {
    "SOLAR_STOWED": {"arm": "STOWED_O13V3", "left_wing": "SOLAR_STOWED", "right_wing": "SOLAR_STOWED", "gripper": "OPEN", "hdrm": "LOCKED", "pose": "Q_STOW_ENGINEERING_CANDIDATE", "authority": "CANDIDATE_HOLD"},
    "SOLAR_DEPLOY_STAGE1": {"arm": "STOWED_O13V3", "left_wing": "SOLAR_DEPLOY_STAGE1", "right_wing": "SOLAR_DEPLOY_STAGE1", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "SIDE_SLDASM_STATE_ONLY"},
    "SOLAR_DEPLOY_STAGE2": {"arm": "STOWED_O13V3", "left_wing": "SOLAR_DEPLOY_STAGE2", "right_wing": "SOLAR_DEPLOY_STAGE2", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "SIDE_SLDASM_STATE_ONLY"},
    "SOLAR_DEPLOYED_NOMINAL": {"arm": ARM_CONFIGS[0], "left_wing": "SOLAR_DEPLOYED_NOMINAL", "right_wing": "SOLAR_DEPLOYED_NOMINAL", "gripper": "OPEN", "hdrm": "RELEASED", "pose": "Q_DEPLOYED_HOME", "authority": "AUTHORIZED_RUNTIME_INPUT_NOT_BAKED"},
    "SOLAR_LEFT_FAIL": {"arm": "STOWED_O13V3", "left_wing": "SOLAR_LEFT_FAIL", "right_wing": "SOLAR_LEFT_FAIL", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "FAULT_STATE_NO_Q_WRITTEN"},
    "SOLAR_RIGHT_FAIL": {"arm": "STOWED_O13V3", "left_wing": "SOLAR_RIGHT_FAIL", "right_wing": "SOLAR_RIGHT_FAIL", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "FAULT_STATE_NO_Q_WRITTEN"},
    "SOLAR_BOTH_FAIL": {"arm": "STOWED_O13V3", "left_wing": "SOLAR_BOTH_FAIL", "right_wing": "SOLAR_BOTH_FAIL", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "FAULT_STATE_NO_Q_WRITTEN"},
    "SOLAR_DEPLOY_ARM_LOCKED": {"arm": "STOWED_O13V3", "left_wing": "SOLAR_DEPLOYED_NOMINAL", "right_wing": "SOLAR_DEPLOYED_NOMINAL", "gripper": "OPEN", "hdrm": "LOCKED", "pose": None, "authority": "ENGINEERING_STATE_NO_Q_WRITTEN"},
    "HDRM_RELEASE": {"arm": "STOWED_O13V3", "left_wing": "SOLAR_DEPLOYED_NOMINAL", "right_wing": "SOLAR_DEPLOYED_NOMINAL", "gripper": "OPEN", "hdrm": "RELEASED", "pose": None, "authority": "SEQUENCE_NODE_ONLY_RELEASE_DYNAMICS_NOT_AUTHORIZED"},
    "SERVICE": {"arm": ARM_CONFIGS[0], "left_wing": "SOLAR_DEPLOYED_NOMINAL", "right_wing": "SOLAR_DEPLOYED_NOMINAL", "gripper": "OPEN", "hdrm": "RELEASED", "pose": "Q_SERVICE_READY", "authority": "PRE_SERVICE_STAGING_RATIFICATION_HOLD_NO_SERVICE_Q_WRITTEN"},
    "RELEASE_CLEAR_END_STATE": {"arm": ARM_CONFIGS[0], "left_wing": "SOLAR_DEPLOYED_NOMINAL", "right_wing": "SOLAR_DEPLOYED_NOMINAL", "gripper": "OPEN", "hdrm": "RELEASED", "pose": "Q_RELEASE_CLEAR", "authority": "AUTHORIZED_GEOMETRIC_END_STATE_RUNTIME_Q_NOT_BAKED"},
}

# SW2024 SP05's generated makepy wrapper advertises
# GetPersistReferenceCount3 / DISPID 99 as returning an I4 count, but
# the live IModelDocExtension rejected that generated call with
# DISP_E_BADPARAMCOUNT after GetPersistReference3 had already returned its
# VT_UI1 payload.  The count wrapper is therefore not a usable independent
# witness on this exact install.  Evidence is instead accepted only after a
# strict recursive UI1 flatten, non-empty canonical byte count, strict
# base64 encode/decode equality, and cold COM object-resolution followed by
# an exact GetPersistReference3 byte-for-byte round trip.
PERSIST_REFERENCE_VALIDATION_POLICY: Mapping[str, Any] = {
    "schema": "F3R2_V5_PERSIST_REFERENCE_VALIDATION_POLICY_V2",
    "solidworks_major": 32,
    "get_persist_reference3_dispid": 98,
    "get_persist_reference_count3_dispid": 99,
    "makepy_count_wrapper_runtime_status": "UNUSABLE_DISP_E_BADPARAMCOUNT",
    "runtime_count_source": "LEN_OF_STRICTLY_FLATTENED_CANONICAL_UI1_BYTES",
    "required_roundtrip": "STRICT_BASE64_AND_COLD_GETOBJECTBYPERSISTREFERENCE3_THEN_EXACT_GETPERSISTREFERENCE3_BYTES",
    "get_persist_reference_count3_runtime_calls_allowed": False,
}

SW_DOC_ASSEMBLY = 2
SW_DOC_PART = 1
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
SW_COMPONENT_FULLY_RESOLVED = 1
SW_COMPONENT_LIGHTWEIGHT = 2
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


@contextmanager
def exclusive_run_lock(command: str) -> Iterable[Dict[str, Any]]:
    """Serialize every filesystem audit/execute transaction on Windows.

    The lock file is deliberately persistent: deleting a lock pathname while a
    process still owns the byte-range lock would allow a second inode/file to
    be created at the same name.  Only the first byte is locked and the handle
    is held for the whole command.
    """
    import msvcrt

    try:
        RUN_LOCK.parent.mkdir(parents=True, exist_ok=True)
        stream = RUN_LOCK.open("a+b")
    except OSError as exc:
        raise GateError("LOOP1E_EXCLUSIVE_LOCK_IO_FAIL", "cannot open the Loop1E exclusive-lock file", {"lock": norm(RUN_LOCK), "command": command, "exception": repr(exc)}) from exc
    acquired = False
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\x00")
            stream.flush()
            os.fsync(stream.fileno())
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            acquired = True
        except OSError as exc:
            raise GateError(
                "LOOP1E_EXCLUSIVE_LOCK_HELD",
                "another Loop1E audit/execute transaction owns the exclusive lock",
                {"lock": norm(RUN_LOCK), "command": command, "pid": os.getpid(), "exception": repr(exc)},
            ) from exc
        yield {"path": norm(RUN_LOCK), "command": command, "pid": os.getpid(), "exclusive": True}
    except OSError as exc:
        raise GateError("LOOP1E_EXCLUSIVE_LOCK_IO_FAIL", "exclusive-lock I/O failed", {"lock": norm(RUN_LOCK), "command": command, "exception": repr(exc)}) from exc
    finally:
        if acquired:
            try:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        stream.close()


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


def stable_json_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def exact_fact(path: Path, expected_sha256: str, expected_bytes: Optional[int] = None) -> Dict[str, Any]:
    if not path.is_file():
        raise GateError("EXACT_FILE_MISSING", "required immutable file is absent", {"path": norm(path)})
    actual = file_fact(path)
    if actual["sha256"] != str(expected_sha256).upper() or (expected_bytes is not None and actual["bytes"] != int(expected_bytes)):
        raise GateError("EXACT_FILE_DRIFT", "required immutable file differs", {"actual": actual, "expected_sha256": expected_sha256, "expected_bytes": expected_bytes})
    return actual


def validate_receipted_fact(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("path"), str) or not isinstance(value.get("sha256"), str) or not isinstance(value.get("bytes"), int):
        raise GateError("RECEIPTED_FACT_SHAPE_FAIL", "receipt file fact is incomplete", {"label": label, "value": value})
    path = Path(str(value["path"])).resolve()
    actual = exact_fact(path, str(value["sha256"]), int(value["bytes"]))
    return {"label": label, **actual}


def show_config_ok(model: Any, name: str, base: Any, types: Any, pythoncom: Any) -> bool:
    """Configuration activation tolerant of the SW2024 SP05 no-op quirk.

    ShowConfiguration2 returns False when asked to activate the ALREADY-active
    configuration (proven in the Loop1D cold-reopen diagnostic and hit by
    Loop1C1/Loop1E). Returns True when the target configuration is active after
    the call (switched or already active); False only for a REAL failed switch,
    so every existing GateError downstream keeps its fail-closed teeth.
    """
    if bool(model.ShowConfiguration2(name)):
        return True
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    return str(base.value(active, "Name")) == str(name)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise GateError("JSON_ROOT_FAIL", "JSON root must be an object", {"path": norm(path)})
    return value


def write_json_once(path: Path, value: Mapping[str, Any]) -> None:
    # Serialize and reject NaN/Infinity before the write-once path is created;
    # a serialization failure must never leave a truncated collision marker.
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


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
        if role in {"LEFT_SOLAR_ARRAY", "RIGHT_SOLAR_ARRAY"}:
            promotion = payloads.get("SOLAR_R2B_P9_PROMOTION", {})
            matches = [row for row in promotion.get("side_assemblies", []) if isinstance(row, dict) and os.path.normcase(str(Path(str(row.get("path", ""))).resolve())) == os.path.normcase(str(path.resolve()))]
            fact = matches[0] if len(matches) == 1 else None
        else:
            fact = find_receipted_fact(payloads, path)
        actual = sha256(path) if path.is_file() else None
        row = {"role": role, "path": norm(path), "exists": path.is_file(), "actual_sha256": actual, "receipt_fact": fact}
        row["inside_unique_v5_root"] = RUN_ROOT.resolve() in path.resolve().parents
        row["pass"] = bool(row["inside_unique_v5_root"] and fact and actual == str(fact.get("sha256", "")).upper() and path.stat().st_size == int(fact.get("bytes", -1))) if path.is_file() else False
        row["status"] = "PASS" if row["pass"] else "PENDING" if (not path.is_file() or fact is None) else "FAIL"
        rows.append(row)
    return rows


def audit_solar_chain() -> Dict[str, Any]:
    promotion_fact = exact_fact(SOLAR_PROMOTION, SOLAR_PROMOTION_SHA256)
    promotion = load_json(SOLAR_PROMOTION)
    if promotion.get("schema") != "F3R2_V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT_V1" or promotion.get("verdict") != "V5_SOLAR_R2B_A_LOGICALLY_PROMOTED_IN_PLACE_FOR_TOP_INTEGRATION":
        raise GateError("SOLAR_PROMOTION_SCHEMA_FAIL", "P9 logical promotion schema/verdict differs")
    if promotion.get("attempt_id") != "V5_SOLAR_R2B_BUILD_20260813T123100Z_P9E9" or Path(str(promotion.get("attempt_root", ""))).resolve() != SOLAR_ATTEMPT_ROOT.resolve():
        raise GateError("SOLAR_PROMOTION_ATTEMPT_FAIL", "logical promotion does not bind exact P9 attempt")
    immutable = promotion.get("immutable_attempt_tree", {})
    files = immutable.get("files")
    if not isinstance(files, list) or len(files) != 52 or immutable.get("file_count") != 52 or immutable.get("tree_sha256") != SOLAR_TREE_SHA256 or immutable.get("authorized_in_place") is not True or immutable.get("reference_only") is not True:
        raise GateError("SOLAR_PROMOTION_TREE_FAIL", "P9 immutable tree contract differs", immutable)
    file_rows = [validate_receipted_fact(row, f"solar_p9_tree_{index}") for index, row in enumerate(files)]
    normalized_paths = [os.path.normcase(str(Path(row["path"]).resolve())) for row in file_rows]
    if len(normalized_paths) != len(set(normalized_paths)):
        raise GateError("SOLAR_PROMOTION_TREE_DUPLICATE", "P9 immutable tree repeats a path")
    inputs = promotion.get("inputs", {})
    for key, path, wanted in (
        ("build_receipt", SOLAR_BUILD_RECEIPT, SOLAR_BUILD_RECEIPT_SHA256),
        ("fresh_read_only_pass", SOLAR_FRESH_RECEIPT, SOLAR_FRESH_RECEIPT_SHA256),
        ("fresh_pid_verifier_handoff", SOLAR_HANDOFF, SOLAR_HANDOFF_SHA256),
    ):
        actual = validate_receipted_fact(inputs.get(key), f"promotion.inputs.{key}")
        if Path(actual["path"]).resolve() != path.resolve() or actual["sha256"] != wanted:
            raise GateError("SOLAR_PROMOTION_INPUT_FAIL", "P9 promotion input differs", {"key": key, "actual": actual})
    if inputs.get("contract_sha256") != SOLAR_CONTRACT_SHA256 or promotion.get("input_commitment_sha256") != SOLAR_INPUT_COMMITMENT_SHA256:
        raise GateError("SOLAR_PROMOTION_COMMITMENT_FAIL", "P9 contract/input commitment differs")
    sides = promotion.get("side_assemblies")
    if not isinstance(sides, list) or len(sides) != 2:
        raise GateError("SOLAR_PROMOTION_SIDE_SET_FAIL", "P9 promotion lacks exactly two side assemblies")
    side_rows: Dict[str, Dict[str, Any]] = {}
    for row in sides:
        side = str(row.get("side", ""))
        path = SOLAR_LEFT if side == "L" else SOLAR_RIGHT if side == "R" else None
        if path is None or Path(str(row.get("path", ""))).resolve() != path.resolve() or row.get("sha256") != SOLAR_SIDE_SHA256[side] or row.get("configuration_names_authority_order") != list(SOLAR_STATES) or row.get("configuration_owner") != "SIDE_SLDASM_ONLY" or row.get("top_level_occurrence_solving") != "RIGID":
            raise GateError("SOLAR_PROMOTION_SIDE_FAIL", "P9 promoted side fact differs", row)
        validate_receipted_fact(row, f"solar_side_{side}")
        side_rows[side] = dict(row)
    build = load_json(SOLAR_BUILD_RECEIPT)
    fresh = load_json(SOLAR_FRESH_RECEIPT)
    if sha256(SOLAR_BUILD_RECEIPT) != SOLAR_BUILD_RECEIPT_SHA256 or build.get("schema") != "F3R2_V5_SOLAR_R2B_A_BUILD_STAGE_RECEIPT_V1" or build.get("verdict") != "V5_SOLAR_R2B_A_BUILD_STAGE_PASS_AWAITING_FRESH_PID_VERIFIER" or build.get("contract_sha256") != SOLAR_CONTRACT_SHA256:
        raise GateError("SOLAR_BUILD_RECEIPT_FAIL", "P9 build receipt differs")
    if sha256(SOLAR_FRESH_RECEIPT) != SOLAR_FRESH_RECEIPT_SHA256 or fresh.get("schema") != "F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_RECEIPT_V1" or fresh.get("verdict") != "V5_SOLAR_R2B_A_NEW_PID_READ_ONLY_ZERO_MUTATION_PASS" or fresh.get("promotion_authorized") is not True or fresh.get("cad_write_calls") != 0 or fresh.get("all_46_cad_hash_pre_equals_post") is not True:
        raise GateError("SOLAR_FRESH_RECEIPT_FAIL", "P9 fresh zero-mutation receipt differs")
    artifacts = build.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 46:
        raise GateError("SOLAR_CAD_ARTIFACT_SET_FAIL", "P9 build receipt lacks 46 CAD artifacts")
    artifact_rows = [validate_receipted_fact(row, f"solar_cad_{index}") for index, row in enumerate(artifacts)]
    if set(fresh.get("cad_hash_pre", {})) != {row["path"] for row in artifacts} or fresh.get("cad_hash_pre") != fresh.get("cad_hash_post"):
        raise GateError("SOLAR_CAD_PRE_POST_FAIL", "fresh P9 CAD map is not exact PRE=POST")
    fresh_sides = {str(row.get("side")): row for row in fresh.get("sides", []) if isinstance(row, dict)}
    if set(fresh_sides) != {"L", "R"}:
        raise GateError("SOLAR_FRESH_SIDE_SET_FAIL", "fresh P9 receipt lacks L/R sides")
    state_oracle: Dict[str, Dict[str, Any]] = {}
    module_paths: Dict[str, Path] = {}
    for side in ("L", "R"):
        rows = fresh_sides[side].get("states", [])
        indexed = {str(row.get("state")): row for row in rows if isinstance(row, dict)}
        if set(indexed) != set(SOLAR_STATES):
            raise GateError("SOLAR_FRESH_STATE_SET_FAIL", "fresh side lacks exact seven states", {"side": side})
        state_oracle[side] = indexed
        nominal_modules = indexed["SOLAR_DEPLOYED_NOMINAL"].get("module_occurrences", {})
        for index in (1, 2, 3):
            key = f"{side}{index}"
            row = nominal_modules.get(key, {})
            path = Path(str(row.get("path", ""))).resolve()
            validate_receipted_fact(row.get("file"), f"solar_module_{key}")
            if row.get("solving") != SW_COMPONENT_RIGID or row.get("suppression") != SW_COMPONENT_RESOLVED or row.get("referenced_configuration") != "默认":
                raise GateError("SOLAR_MODULE_CONTRACT_FAIL", "P9 module is not rigid/resolved/default", {"module": key, "row": row})
            module_paths[key] = path
    state_angles = promotion.get("configuration_contract", {}).get("state_angles_deg")
    if promotion.get("configuration_contract", {}).get("exact_configurations_authority_order") != list(SOLAR_STATES) or promotion.get("configuration_contract", {}).get("top_level_second_driver") != "PROHIBITED" or not isinstance(state_angles, dict):
        raise GateError("SOLAR_CONFIGURATION_CONTRACT_FAIL", "P9 configuration owner/second-driver contract differs")
    chain_payload = {
        "promotion": promotion_fact,
        "tree_sha256": SOLAR_TREE_SHA256,
        "input_commitment_sha256": SOLAR_INPUT_COMMITMENT_SHA256,
        "contract_sha256": SOLAR_CONTRACT_SHA256,
        "build_receipt": file_fact(SOLAR_BUILD_RECEIPT),
        "fresh_receipt": file_fact(SOLAR_FRESH_RECEIPT),
        "cad_manifest": exact_fact(SOLAR_CAD_MANIFEST, SOLAR_CAD_MANIFEST_SHA256),
        "handoff": file_fact(SOLAR_HANDOFF),
        "sides": side_rows,
        "cad_artifacts": artifact_rows,
        "immutable_tree": file_rows,
        "module_paths": {key: norm(path) for key, path in module_paths.items()},
        "state_angles_deg": state_angles,
        "configuration_names": list(SOLAR_STATES),
    }
    chain_payload["solar_chain_digest"] = stable_json_sha256(chain_payload)
    return {"pass": True, "payload": chain_payload, "state_oracle": state_oracle, "module_paths": {key: norm(path) for key, path in module_paths.items()}}


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
        and tuple(TOP_CONFIGS) == (*SOLAR_STATES, "SOLAR_DEPLOY_ARM_LOCKED", "HDRM_RELEASE", "SERVICE", "RELEASE_CLEAR_END_STATE")
        and all(TOP_CONFIGS[state]["left_wing"] == state == TOP_CONFIGS[state]["right_wing"] for state in SOLAR_STATES)
        and all(TOP_CONFIGS[state]["left_wing"] == "SOLAR_DEPLOYED_NOMINAL" == TOP_CONFIGS[state]["right_wing"] for state in ("SOLAR_DEPLOY_ARM_LOCKED", "HDRM_RELEASE", "SERVICE", "RELEASE_CLEAR_END_STATE"))
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
        "exact_top_configuration_names": list(TOP_CONFIGS),
        "solar_configuration_owner": "SIDE_SLDASM_ONLY",
        "top_level_solar_angle_driver_count": 0,
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


def all_staging_candidates() -> List[Path]:
    if not TOP_DIR.is_dir():
        return []
    pattern = TARGET.stem + "__LOOP1E_STAGING_*" + TARGET.suffix
    return sorted((path.resolve() for path in TOP_DIR.glob(pattern) if path.is_file()), key=lambda path: os.path.normcase(str(path)))


def staging_isolation_records() -> List[Dict[str, Any]]:
    """Validate write-once logical isolation receipts without moving CAD.

    A failed pre-precommit SaveAs is retained byte-for-byte for diagnosis.  It
    is excluded from the active transaction only when a write-once receipt
    binds the exact CAD bytes, the exact failure receipt, the historical
    script fact carried by that failure receipt, and an explicit no-resume /
    no-promote disposition.  Missing or drifted evidence holds the gate.
    """
    records: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for receipt_path in sorted(VALIDATION.glob(STAGING_ISOLATION_GLOB), key=lambda path: os.path.normcase(str(path))):
        payload = load_json(receipt_path)
        staging = payload.get("staging_artifact")
        failure = payload.get("source_failure_receipt")
        source_script = payload.get("source_script")
        policy = payload.get("isolation_policy")
        if (
            payload.get("schema") != "F3R2_V5_LOOP1E_STAGING_ISOLATION_V1"
            or payload.get("verdict") != "V5_LOOP1E_FAILED_STAGING_WRITE_ONCE_LOGICAL_ISOLATION_PASS"
            or payload.get("intended_target") != norm(TARGET)
            or payload.get("intended_target_existed_at_isolation") is not False
            or not isinstance(staging, Mapping)
            or not isinstance(failure, Mapping)
            or not isinstance(source_script, Mapping)
            or not isinstance(policy, Mapping)
            or policy.get("disposition") != "LOGICALLY_ISOLATED_IN_PLACE_EXCLUDED_FROM_ACTIVE_LOOP1E_TRANSACTION"
            or policy.get("delete_allowed") is not False
            or policy.get("overwrite_allowed") is not False
            or policy.get("promotion_allowed") is not False
            or policy.get("resume_allowed") is not False
            or policy.get("physical_file_retained") is not True
            or policy.get("exact_fact_must_remain_unchanged") is not True
        ):
            raise GateError("STAGING_ISOLATION_SCHEMA_FAIL", "staging isolation receipt contract differs", {"receipt": norm(receipt_path), "payload": payload})
        staging_fact = validate_receipted_fact(staging, "isolated_staging_artifact")
        staging_path = Path(staging_fact["path"]).resolve()
        if not is_loop1e_staging_path(staging_path):
            raise GateError("STAGING_ISOLATION_PATH_FAIL", "isolated artifact is not an exact Loop1E staging path", {"receipt": norm(receipt_path), "staging": staging_fact})
        key = os.path.normcase(str(staging_path))
        if key in seen:
            raise GateError("STAGING_ISOLATION_DUPLICATE_FAIL", "one staging artifact has multiple isolation receipts", {"staging": staging_fact})
        seen.add(key)
        failure_fact = validate_receipted_fact(failure, "isolated_staging_failure_receipt")
        failure_payload = load_json(Path(failure_fact["path"]))
        historical_script = failure_payload.get("static_audit", {}).get("script") if isinstance(failure_payload.get("static_audit"), Mapping) else None
        failure_pid = failure_payload.get("exclusive_lock", {}).get("pid") if isinstance(failure_payload.get("exclusive_lock"), Mapping) else None
        if (
            failure_payload.get("target") != norm(TARGET)
            or failure_payload.get("transaction_entry_state") != failure.get("transaction_entry_state")
            or failure_payload.get("verdict") != failure.get("verdict")
            or int(failure_pid or -1) != int(failure.get("execution_pid", -2))
            or f"_PID{int(failure_pid or -1)}{TARGET.suffix}" not in staging_path.name
            or not isinstance(historical_script, Mapping)
            or historical_script.get("path") != source_script.get("path")
            or historical_script.get("bytes") != source_script.get("bytes")
            or historical_script.get("sha256") != source_script.get("sha256")
        ):
            raise GateError("STAGING_ISOLATION_LINEAGE_FAIL", "isolation receipt does not bind the exact failed transaction lineage", {"receipt": norm(receipt_path), "failure": failure_payload, "source_script": source_script})
        records.append({
            "receipt": file_fact(receipt_path),
            "staging_artifact": staging_fact,
            "source_failure_receipt": failure_fact,
            "source_script_at_failure": dict(source_script),
            "disposition": policy["disposition"],
            "active_transaction_candidate": False,
            "delete_overwrite_promote_resume_allowed": False,
            "pass": True,
        })
    return records


def staging_candidates() -> List[Path]:
    isolated = {
        os.path.normcase(str(Path(row["staging_artifact"]["path"]).resolve()))
        for row in staging_isolation_records()
    }
    return [path for path in all_staging_candidates() if os.path.normcase(str(path.resolve())) not in isolated]


def is_loop1e_staging_path(path: Path) -> bool:
    resolved = path.resolve()
    return bool(
        resolved.parent == TARGET.resolve().parent
        and resolved.name.startswith(TARGET.stem + "__LOOP1E_STAGING_")
        and resolved.suffix.casefold() == TARGET.suffix.casefold()
        and resolved != TARGET.resolve()
    )


def new_staging_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    candidate = TARGET.with_name(f"{TARGET.stem}__LOOP1E_STAGING_{stamp}_PID{os.getpid()}{TARGET.suffix}")
    if not is_loop1e_staging_path(candidate) or candidate.exists():
        raise GateError("TOP_STAGING_PATH_FAIL", "cannot allocate a unique same-directory staging path", {"path": norm(candidate)})
    return candidate


def precommit_payload_good(payload: Mapping[str, Any]) -> bool:
    staging = payload.get("staging_artifact", {})
    build = payload.get("build", {})
    return bool(
        payload.get("schema") == "F3R2_V5_LOOP1E_TOP_PRECOMMIT_V2"
        and payload.get("script_sha256") == sha256(Path(__file__))
        and payload.get("accepted_urdf_sha256") == ACCEPTED_URDF_SHA256
        and payload.get("solar_chain", {}).get("promotion", {}).get("sha256") == SOLAR_PROMOTION_SHA256
        and payload.get("solar_chain", {}).get("contract_sha256") == SOLAR_CONTRACT_SHA256
        and payload.get("local_arm_contract_sha256") == LOCAL_ARM_CONTRACT_SHA256
        and payload.get("execution_g0", {}).get("schema") == "F3R2_V5_LOOP1E_EXECUTION_G0_BINDING_V1"
        and payload.get("intended_target") == norm(TARGET)
        and isinstance(staging, Mapping)
        and isinstance(staging.get("path"), str)
        and isinstance(staging.get("sha256"), str)
        and isinstance(staging.get("bytes"), int)
        and is_loop1e_staging_path(Path(staging["path"]))
        and isinstance(build, Mapping)
        and build.get("artifact") == staging
        and payload.get("staging_cold_reopen", {}).get("verdict") == "V5_LOOP1E_TOP_COLD_REOPEN_WITH_LOOP2_CONTRACT_PASS"
    )


def checkpoint_state() -> Dict[str, Any]:
    target_exists = TARGET.is_file()
    checkpoint_exists = CHECKPOINT.is_file()
    precommit_exists = PRECOMMIT.is_file()
    receipt_exists = FINAL_RECEIPT.is_file()
    stages = staging_candidates()

    if receipt_exists:
        return {
            "state": "HOLD_WRITE_ONCE_COLLISION",
            "target_exists": target_exists,
            "checkpoint_exists": checkpoint_exists,
            "precommit_exists": precommit_exists,
            "receipt_exists": True,
            "staging_candidates": [norm(path) for path in stages],
        }
    if checkpoint_exists:
        if not target_exists or not precommit_exists or stages:
            return {
                "state": "HOLD_CHECKPOINT_TRANSACTION_INCOMPLETE",
                "target_exists": target_exists,
                "precommit_exists": precommit_exists,
                "staging_candidates": [norm(path) for path in stages],
            }
        try:
            payload = load_json(CHECKPOINT)
            precommit = load_json(PRECOMMIT)
            good = bool(
                precommit_payload_good(precommit)
                and payload.get("schema") == "F3R2_V5_LOOP1E_TOP_CHECKPOINT_V2"
                and payload.get("script_sha256") == sha256(Path(__file__))
                and payload.get("accepted_urdf_sha256") == ACCEPTED_URDF_SHA256
                and payload.get("solar_chain", {}).get("promotion", {}).get("sha256") == SOLAR_PROMOTION_SHA256
                and payload.get("local_arm_contract_sha256") == LOCAL_ARM_CONTRACT_SHA256
                and payload.get("execution_g0", {}).get("schema") == "F3R2_V5_LOOP1E_EXECUTION_G0_BINDING_V1"
                and payload.get("motion_contract", {}).get("schema") == "F3R2_V5_LOOP2_MOTION_CONTRACT_V1"
                and payload.get("precommit", {}).get("sha256") == sha256(PRECOMMIT)
                and payload.get("target", {}).get("sha256") == sha256(TARGET)
                and precommit.get("staging_artifact", {}).get("sha256") == sha256(TARGET)
            )
            return {"state": "RESUME_COLD_REOPEN" if good else "HOLD_CHECKPOINT_DRIFT", "checkpoint": payload, "precommit": precommit}
        except Exception as exc:
            return {"state": "HOLD_CHECKPOINT_PARSE", "exception": repr(exc)}
    if precommit_exists:
        try:
            precommit = load_json(PRECOMMIT)
            if not precommit_payload_good(precommit):
                return {"state": "HOLD_PRECOMMIT_DRIFT", "precommit": precommit}
            staging_path = Path(str(precommit["staging_artifact"]["path"]))
            expected_hash = str(precommit["staging_artifact"]["sha256"])
            if target_exists and not stages and sha256(TARGET) == expected_hash:
                return {"state": "RESUME_PROMOTED_PRECOMMIT", "precommit": precommit}
            if not target_exists and stages == [staging_path.resolve()] and sha256(staging_path) == expected_hash:
                return {"state": "RESUME_PRECOMMIT_STAGED", "precommit": precommit}
            return {
                "state": "HOLD_PRECOMMIT_ARTIFACT_DRIFT",
                "target_exists": target_exists,
                "expected_sha256": expected_hash,
                "staging_candidates": [file_fact(path) for path in stages],
            }
        except Exception as exc:
            return {"state": "HOLD_PRECOMMIT_PARSE", "exception": repr(exc)}
    if target_exists:
        return {"state": "HOLD_WRITE_ONCE_COLLISION", "target_exists": True, "checkpoint_exists": False, "precommit_exists": False, "receipt_exists": False, "staging_candidates": [norm(path) for path in stages]}
    if stages:
        return {"state": "HOLD_UNRECEIPTED_STAGING", "staging_candidates": [file_fact(path) for path in stages]}
    return {"state": "PENDING_NEW"}


def local_arm_state() -> Dict[str, Any]:
    if not LOCAL_ARM_ROOT.exists() and not LOCAL_ARM_CHECKPOINT.exists():
        return {"state": "PENDING_NEW"}
    if LOCAL_ARM.is_file() and LOCAL_ARM_CHECKPOINT.is_file():
        try:
            payload = load_json(LOCAL_ARM_CHECKPOINT)
            contract = payload.get("local_arm_contract")
            source = contract.get("source_v1_payload") if isinstance(contract, dict) else None
            drivers = source.get("native_joint_drivers") if isinstance(source, dict) else None
            good = bool(
                sha256(LOCAL_ARM_CHECKPOINT) == LOCAL_ARM_CHECKPOINT_SHA256
                and payload.get("schema") == "F3R2_V5_LOOP1E0_LOCAL_ARM_INDEPENDENT_CHECKPOINT_V2"
                and payload.get("verdict") == "V5_LOOP1E0_LOCAL_ARM_INDEPENDENT_CHECKPOINT_V2_PASS"
                and payload.get("LOCAL_ARM_CONTRACT_SHA256") == LOCAL_ARM_CONTRACT_SHA256
                and payload.get("accepted_urdf", {}).get("sha256") == ACCEPTED_URDF_SHA256
                and payload.get("source_v1_checkpoint", {}).get("sha256") == LOCAL_ARM_CHECKPOINT_V1_SHA256
                and payload.get("local_arm", {}).get("sha256") == LOCAL_ARM_SHA256 == sha256(LOCAL_ARM)
                and isinstance(source, dict)
                and source.get("schema") == "F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V1"
                and source.get("accepted_urdf_sha256") == ACCEPTED_URDF_SHA256
                and isinstance(drivers, list)
                and [row.get("joint") for row in drivers] == [f"joint{index}" for index in range(1, 7)]
                and all(row.get("cold_reopen_verified") is True for row in drivers)
            )
            return {"state": "PASS_RESUME" if good else "HOLD_CHECKPOINT_DRIFT", "checkpoint": payload, "runtime_payload": source, "contract_sha256": LOCAL_ARM_CONTRACT_SHA256}
        except Exception as exc:
            return {"state": "HOLD_CHECKPOINT_PARSE", "exception": repr(exc)}
    return {"state": "HOLD_PARTIAL_LOCALIZATION", "root_exists": LOCAL_ARM_ROOT.exists(), "arm_exists": LOCAL_ARM.is_file(), "checkpoint_exists": LOCAL_ARM_CHECKPOINT.is_file()}


def static_audit() -> Dict[str, Any]:
    offline_test = offline_self_test()
    isolation = staging_isolation_records()
    receipt_rows, payloads = audit_receipts()
    try:
        solar = audit_solar_chain()
    except Exception as exc:
        solar = {"pass": False, "error": getattr(exc, "code", type(exc).__name__), "reason": str(exc), "detail": getattr(exc, "detail", {})}
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
    executable_target = target["state"] in {"PENDING_NEW", "RESUME_PRECOMMIT_STAGED", "RESUME_PROMOTED_PRECOMMIT", "RESUME_COLD_REOPEN"}
    executable_arm = arm["state"] == "PASS_RESUME"
    authorized = bool(not pending and not failures and solar["pass"] and all(row["pass"] for row in receipt_rows + protected + components) and authority["pass"] and frame_contracts["pass"] and helper_row["pass"] and template_row["pass"] and executable_target and executable_arm)
    verdict = "V5_LOOP1E_STATIC_EXECUTION_READY" if authorized else "V5_LOOP1E_STATIC_PENDING_UPSTREAM" if pending and not failures else "V5_LOOP1E_STATIC_HOLD"
    return {
        "schema": "F3R2_V5_LOOP1E_STATIC_AUDIT_V1", "timestamp_utc": utc_now(), "verdict": verdict,
        "execution_authorized": authorized, "script": file_fact(Path(__file__)), "base_helper": helper_row, "assembly_template": template_row,
        "upstream_receipts": receipt_rows, "protected_inputs": protected, "v5_components": components,
        "authority": authority, "frame_contracts": frame_contracts, "solar_r2b_p9": solar, "target_state": target, "local_arm_state": arm,
        "offline_self_test": offline_test, "persist_ui1_pure_self_test": offline_test["persist_reference"], "script_ast_contract_self_test": offline_test["script_ast_contract"],
        "persist_reference_validation_policy": dict(PERSIST_REFERENCE_VALIDATION_POLICY), "staging_isolation": isolation,
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
            "TOP_ASSEMBLY_DIRECT_FINAL_SAVE_PROHIBITED_STAGING_PRECOMMIT_PROMOTION_REQUIRED",
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
        return state["runtime_payload"]
    raise GateError("LOCAL_ARM_V2_MIGRATION_REQUIRED", "Loop1E may consume only the independent write-once local-arm V2 checkpoint; it may not recreate or update it", state)


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


def feature_error_code(feature: Any, base: Any) -> int:
    # IFeature::GetErrorCode2 declares IsWarning as [in,out] VARIANT_BOOL*
    # (makepy VT_BYREF|VT_BOOL), so win32com returns a (code, isWarning)
    # tuple; unwrap through base.unpack so the int readback stays fail-closed.
    return int(base.unpack(base.value(feature, "GetErrorCode2"))[0])


def angle_definition_exact(feature: Any, joint: Dict[str, Any], angle_rad: float, base: Any, types: Any, pythoncom: Any) -> bool:
    definition = angle_mate_data(feature, base, types, pythoncom)
    return bool(
        base.value(definition, "IsAdvancedMate")
        and abs(float(base.value(definition, "MinimumAngle")) - float(joint["lower_rad"])) <= 1.0e-9
        and abs(float(base.value(definition, "MaximumAngle")) - float(joint["upper_rad"])) <= 1.0e-9
        and abs(float(base.value(definition, "Angle")) - float(angle_rad)) <= 1.0e-9
    )


def write_angle_definition(model: Any, feature: Any, joint: Dict[str, Any], angle_rad: float, base: Any, types: Any, pythoncom: Any) -> bool:
    data = angle_mate_data(feature, base, types, pythoncom)
    data.IsAdvancedMate = True
    data.MinimumAngle = float(joint["lower_rad"])
    data.MaximumAngle = float(joint["upper_rad"])
    data.Angle = float(angle_rad)
    data.MateAlignment = SW_ALIGN_ALIGNED
    if not bool(feature.ModifyDefinition(data, model, None)) or not bool(model.ForceRebuild3(True)):
        return False
    return angle_definition_exact(feature, joint, angle_rad, base, types, pythoncom)


def converge_angle_definition(model: Any, feature: Any, feature_name: str, joint: Dict[str, Any], angle_rad: float, base: Any, types: Any, pythoncom: Any, force: bool = False) -> Tuple[Any, List[str]]:
    """Verify-first advanced-angle convergence with a bounded write ladder.

    ModifyDefinition is intermittent on this build, increasingly under
    memory pressure (identical sequences PASS/FAIL, 2026-08-11/12), and
    AddMate3 already receives Angle plus the absolute limits at creation —
    the created mate reads back advanced+limited+angle=0 exactly (probe
    V5_PROBE_LOOP1E_MODIFY_CONVERGE Q1).  So: verify first, and only write
    on mismatch; the write ladder is direct plus three fresh-handle retries
    with a short settle between attempts (probe V5_PROBE_LOOP1E_MODIFY_PRIME
    and V5_PROBE_LOOP1E_NOOP_SWITCH_POISON show same-state attempts flip
    nondeterministically).  force=True skips the verify-first skip: a
    freshly created mate must be PRIMED by one full ModifyDefinition before
    later drive writes commit — every 20260812 run that skipped the setup
    write failed its drive (0557/0610/0632/0655), every run that executed
    it passed (probes 20260811T232531, 20260812T060323, 20260812T060704).
    Returns the (possibly re-acquired) feature and the ladder trace.
    """
    ladder: List[str] = []
    if not force and angle_definition_exact(feature, joint, angle_rad, base, types, pythoncom):
        ladder.append("verify_first_exact")
        return feature, ladder
    ladder.append("direct_write")
    if write_angle_definition(model, feature, joint, angle_rad, base, types, pythoncom):
        return feature, ladder
    for attempt in range(3):
        time.sleep(0.75)
        retry_feature = mate_features(model, base, types, pythoncom).get(feature_name)
        if retry_feature is None:
            ladder.append(f"fresh_retry_{attempt}_feature_missing")
            continue
        ladder.append(f"fresh_retry_{attempt}_write")
        if write_angle_definition(model, retry_feature, joint, angle_rad, base, types, pythoncom):
            return retry_feature, ladder
        feature = retry_feature
    ladder.append("ladder_exhausted")
    return feature, ladder


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
        # Lightweight occurrences can report an empty Transform2; the total
        # transform stays readable (probe V5_PROBE_LOOP1E_TRANSFORM_OR_RESOLVE
        # S1: 16 finite values on LIGHTWEIGHT base_link/link6).
        raw_total = base.value(component, "GetTotalTransform", False)
        total = [float(value) for value in base.as_list(base.value(raw_total, "ArrayData"))] if raw_total is not None else []
        if len(total) == 16 and all(math.isfinite(value) for value in total):
            values = total
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise GateError("ARM_COMPONENT_TRANSFORM_FAIL", "arm component Transform2 is not finite/16-value", {"component": str(base.value(component, "Name2")), "values": values})
    return values


def selection_manager(model: Any, base: Any, types: Any, pythoncom: Any) -> Any:
    """Tolerant ISelectionMgr accessor (SW2024 makepy quirk).

    The untyped propget "SelectionManager" (dispid 65537) raises
    DISP_E_MEMBERNOTFOUND via dynamic dispatch on this build; the typed
    "ISelectionManager" (dispid 65711) works.  Same dual-name pattern as the
    Loop1A/Loop1B/Loop1C1 scripts.
    """
    for name in ("ISelectionManager", "SelectionManager"):
        try:
            raw = getattr(model, name)
            if raw is not None:
                return base.wrap(raw, "ISelectionMgr", types, pythoncom)
        except Exception:
            continue
    raise GateError("SELECTION_MANAGER_FAIL", "cannot obtain ISelectionMgr")


def add_native_angle_driver(
    model: Any,
    assembly: Any,
    female: Any,
    male: Any,
    joint: Dict[str, Any],
    base: Any,
    types: Any,
    pythoncom: Any,
    angle_rad: float = 0.0,
    flip: bool = False,
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
    selection = selection_manager(model, base, types, pythoncom)
    selected = int(selection.GetSelectedObjectCount2(1))
    selected_owners = []
    for index in range(1, selected + 1):
        raw_owner = selection.GetSelectedObjectsComponent4(index, 1)
        selected_owners.append(str(base.value(base.wrap(raw_owner, "IComponent2", types, pythoncom), "Name2")) if raw_owner is not None else None)
    returned = assembly.AddMate3(
        SW_MATE_ANGLE, SW_ALIGN_ALIGNED, bool(flip),
        0.0, 0.0, 0.0, 0.0, 0.0,
        float(angle_rad), float(joint["upper_rad"]), float(joint["lower_rad"]),
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
    # AddMate3 already received the angle and absolute limits at creation and
    # the created mate reads back advanced+limited+angle=<angle_rad> exactly
    # (probe V5_PROBE_LOOP1E_MODIFY_CONVERGE Q1), so verify first and only
    # write on mismatch; ModifyDefinition is unreliable on this build (bare
    # Angle writes pass but full-field writes fail, 20260812 runs).
    if not angle_definition_exact(feature, joint, angle_rad, base, types, pythoncom):
        feature, ladder = converge_angle_definition(model, feature, name, joint, angle_rad, base, types, pythoncom)
        if ladder[-1] == "ladder_exhausted":
            raise GateError("ANGLE_MATE_ADVANCED_FAIL", "cannot establish/rebuild the advanced limit-angle definition", {"joint": joint["joint"], "ladder": ladder})
    mate = angle_mate_object(feature, base, types, pythoncom)
    definition = angle_mate_data(feature, base, types, pythoncom)
    if int(base.value(mate, "Type")) != SW_MATE_ANGLE or not bool(base.value(definition, "IsAdvancedMate")) or feature_error_code(feature, base) != 0 or bool(base.value(feature, "IsSuppressed")):
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
        "flip": bool(flip),
    }


def recreate_angle_driver(model: Any, assembly: Any, female_leaf: str, male_leaf: str, joint: Dict[str, Any], angle_rad: float, base: Any, types: Any, pythoncom: Any, flip: bool = False) -> Any:
    """Delete the joint's driver mate and recreate it at ``angle_rad``.

    Creation-angle drive: AddMate3's Angle argument moves the joint exactly
    at creation (probe V5_PROBE_LOOP1E_MODIFY_PATHS S3: +0.5 deg pure
    accepted-axis rotation), while ModifyDefinition is unreliable on this
    build.  EditDelete + AddMate3 are both reliable.  All handles are
    re-acquired fresh (handles die across rebuilds/config switches).
    """
    name = f"V5_LOOP2_{joint['joint'].upper()}_LIMIT_ANGLE"
    existing = mate_features(model, base, types, pythoncom).get(name)
    if existing is not None:
        model.ClearSelection2(True)
        if not bool(existing.Select2(False, 0)):
            raise GateError("ANGLE_DRIVER_RECREATE_SELECT_FAIL", "cannot select the existing driver mate for recreation", {"joint": joint["joint"], "feature": name})
        try:
            model.EditDelete()
        finally:
            model.ClearSelection2(True)
        if mate_features(model, base, types, pythoncom).get(name) is not None:
            raise GateError("ANGLE_DRIVER_RECREATE_DELETE_FAIL", "existing driver mate did not delete", {"joint": joint["joint"], "feature": name})
        # AddMate3 right after EditDelete can silently not add (error=0, no
        # additions — joint2, 20260812T0734 run); settle the mate group first.
        if not bool(model.ForceRebuild3(True)):
            raise GateError("ANGLE_DRIVER_RECREATE_REBUILD_FAIL", "rebuild after driver delete failed", {"joint": joint["joint"], "feature": name})
    fresh = {str(base.value(item, "Name2")).split("/")[-1]: item for item in [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]}
    female = fresh.get(female_leaf)
    male = fresh.get(male_leaf)
    if female is None or male is None:
        raise GateError("ANGLE_DRIVER_RECREATE_COMPONENTS_FAIL", "datum components missing for driver recreation", {"joint": joint["joint"], "female": female_leaf, "male": male_leaf})
    feature, _dimension, _creation = add_native_angle_driver(model, assembly, female, male, joint, base, types, pythoncom, angle_rad=angle_rad, flip=flip)
    return feature


def joint_relative_rotation(assembly: Any, joint: Dict[str, Any], base: Any, types: Any, pythoncom: Any) -> List[List[float]]:
    """Relative parent<-child rotation (3x3, fresh component handles)."""
    index = int(joint["joint"].replace("joint", ""))
    parent_leaf = "B51_REF_base_link_LINKLOCAL-1" if index == 1 else f"B51_REF_link{index - 1}_LINKLOCAL-1"
    child_leaf = f"B51_REF_link{index}_LINKLOCAL-1"
    fresh = {str(base.value(item, "Name2")).split("/")[-1]: item for item in [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]}
    if parent_leaf not in fresh or child_leaf not in fresh:
        raise GateError("ANGLE_MEASURE_LIVE_FAIL", "live parent/child occurrence not found for joint angle measurement", {"joint": joint["joint"], "parent_leaf": parent_leaf, "child_leaf": child_leaf})
    parent_rotation = rotation3(component_transform16(fresh[parent_leaf], base))
    child_rotation = rotation3(component_transform16(fresh[child_leaf], base))
    return multiply3(transpose3(parent_rotation), child_rotation)


def project_delta_on_accepted_axis(baseline_relative: List[List[float]], current_relative: List[List[float]], joint: Dict[str, Any]) -> Tuple[float, float]:
    """Delta rotation vs the q=0 baseline, projected on the accepted URDF
    axis.  The baseline-relative form cancels the joint's static origin_rpy
    frame offset (an absolute measurement reports a bogus 90 deg transverse
    for joint2 — ANGLE_CONFIG_POSE_MISMATCH on 20260812T0827Z)."""
    delta = multiply3(current_relative, transpose3(baseline_relative))
    vector = rotation_vector(delta)
    expected_axis_parent = matvec3(rpy_rotation(joint["origin_rpy"]), joint["axis_xyz"])
    norm_axis = math.sqrt(sum(value * value for value in expected_axis_parent))
    expected_axis_parent = [value / norm_axis for value in expected_axis_parent]
    projected = sum(vector[index] * expected_axis_parent[index] for index in range(3))
    transverse = math.sqrt(max(0.0, sum(value * value for value in vector) - projected * projected))
    return projected, transverse


def probe_driver_sign(
    model: Any,
    assembly: Any,
    feature: Any,
    parent: Any,
    child: Any,
    joint: Dict[str, Any],
    base: Any,
    types: Any,
    pythoncom: Any,
    flip: bool = False,
) -> Dict[str, Any]:
    parent_leaf = str(base.value(parent, "Name2")).split("/")[-1]
    child_leaf = str(base.value(child, "Name2")).split("/")[-1]
    index = int(joint["joint"].replace("joint", ""))
    female_leaf = f"B51_REV_DATUM_FEMALE-{index}"
    male_leaf = f"B51_REV_DATUM_MALE-{index}"
    baseline_relative = None
    fresh0 = {str(base.value(item, "Name2")).split("/")[-1]: item for item in [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]}
    if parent_leaf not in fresh0 or child_leaf not in fresh0:
        raise GateError("ANGLE_SIGN_PROBE_LIVE_FAIL", "live parent/child occurrence not found before the sign probe", {"joint": joint["joint"], "parent_leaf": parent_leaf, "child_leaf": child_leaf})
    baseline_parent = rotation3(component_transform16(fresh0[parent_leaf], base))
    baseline_child = rotation3(component_transform16(fresh0[child_leaf], base))
    baseline_relative = multiply3(transpose3(baseline_parent), baseline_child)
    probe = math.radians(0.5)
    # AddMate3 cannot create a NEGATIVE angle (error 0, no additions — probe
    # V5_PROBE_LOOP1E_J2_RECREATE E3), and flip/anti-align/swap all still
    # drive positive (V5_PROBE_LOOP1E_J2_NEGDIRECTION 075158/075731Z), so the
    # sign probe always drives +0.5 deg.  For joint2/joint3 (accepted upper
    # bound 0) this transiently exceeds the soft advanced-mate limit inside
    # this in-memory probe only; advanced-mate limits do not clamp the
    # creation angle (E4), and the driver is restored to q=0 immediately
    # after measurement — nothing out-of-limit is persisted.
    config = ARM_CONFIGS[0]
    if not show_config_ok(model, config, base, types, pythoncom):
        raise GateError("ANGLE_SIGN_PROBE_SET_FAIL", "cannot activate the probe configuration before the sign probe", {"joint": joint["joint"]})
    # Creation-angle drive: AddMate3's Angle argument moves the joint exactly
    # at creation (probe V5_PROBE_LOOP1E_MODIFY_PATHS S3) and EditDelete +
    # AddMate3 are both reliable on this build, while ModifyDefinition is not.
    recreate_angle_driver(model, assembly, female_leaf, male_leaf, joint, probe, base, types, pythoncom, flip=flip)
    current_parent = rotation3(component_transform16({str(base.value(item, "Name2")).split("/")[-1]: item for item in [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]}[parent_leaf], base))
    current_child = rotation3(component_transform16({str(base.value(item, "Name2")).split("/")[-1]: item for item in [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]}[child_leaf], base))
    current_relative = multiply3(transpose3(current_parent), current_child)
    delta = multiply3(current_relative, transpose3(baseline_relative))
    vector = rotation_vector(delta)
    expected_axis_parent = matvec3(rpy_rotation(joint["origin_rpy"]), joint["axis_xyz"])
    norm_axis = math.sqrt(sum(value * value for value in expected_axis_parent))
    expected_axis_parent = [value / norm_axis for value in expected_axis_parent]
    projected = sum(vector[index] * expected_axis_parent[index] for index in range(3))
    transverse = math.sqrt(max(0.0, sum(value * value for value in vector) - projected * projected))
    recreate_angle_driver(model, assembly, female_leaf, male_leaf, joint, 0.0, base, types, pythoncom, flip=flip)
    restored_parent = rotation3(component_transform16({str(base.value(item, "Name2")).split("/")[-1]: item for item in [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]}[parent_leaf], base))
    restored_child = rotation3(component_transform16({str(base.value(item, "Name2")).split("/")[-1]: item for item in [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]}[child_leaf], base))
    restored_relative = multiply3(transpose3(restored_parent), restored_child)
    restore_delta = multiply3(restored_relative, transpose3(baseline_relative))
    restore_vector = rotation_vector(restore_delta)
    if math.sqrt(sum(value * value for value in restore_vector)) > math.radians(0.05):
        raise GateError("ANGLE_SIGN_PROBE_RESTORE_FAIL", "cannot restore q=0 after sign probe", {"joint": joint["joint"], "residual_rad": math.sqrt(sum(value * value for value in restore_vector))})
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
        "drive_mechanism": "DELETE_AND_RECREATE_AT_ANGLE (ModifyDefinition unreliable on this build)",
        "pass": True,
    }


def configure_native_arm_drivers(model: Any, assembly: Any, components: Sequence[Any], base: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    # The sign probe's baseline must be read in the SAME configuration the
    # probe drives (ARM_CONFIGS[0]); otherwise the measured delta includes the
    # STOWED->默认 pose difference (about the joint axis itself) and the
    # kinematic gate sees a bogus radian-scale rotation
    # (ANGLE_SIGN_PROBE_KINEMATIC_FAIL, 2026-08-11 run).
    if not show_config_ok(model, ARM_CONFIGS[0], base, types, pythoncom) or not bool(model.ForceRebuild3(True)):
        raise GateError("ANGLE_DRIVER_CONFIG_ACTIVATE_FAIL", "cannot activate the arm q=0 configuration before driver synthesis")
    # Component handles collected before a ShowConfiguration2 switch go
    # stale: feature traversal and transform reads on them come back empty
    # (JOINT_SIDE_PLANE_MISSING / ARM_COMPONENT_TRANSFORM_FAIL, 2026-08-11).
    # Re-enumerate live occurrences after the switch (probe
    # V5_PROBE_LOOP1E_DATUM_FEATURES: fresh handles expose the RefPlanes in
    # both configurations and load states).
    live = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]
    by_leaf = {str(base.value(item, "Name2")).split("/")[-1]: item for item in live}
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
        try:
            sign_probe = probe_driver_sign(model, assembly, feature, parent, child, joint, base, types, pythoncom)
        except GateError as exc:
            if exc.code != "ANGLE_SIGN_PROBE_DIRECTION_FAIL":
                raise
            # Reversed datum hinge: Flip inverts the drive sign while keeping
            # the q=0 pose and pure accepted-axis kinematics (probe
            # V5_PROBE_LOOP1E_J2_SIGN_FACTORIAL: flip=1 -> pure +probe).
            # The direction gate still fires if the flipped driver is wrong.
            feature = recreate_angle_driver(model, assembly, f"B51_REV_DATUM_FEMALE-{index}", f"B51_REV_DATUM_MALE-{index}", joint, 0.0, base, types, pythoncom, flip=True)
            creation["flip"] = True
            creation["sign_correction"] = "FLIPPED_AFTER_DIRECTION_PROBE"
            sign_probe = probe_driver_sign(model, assembly, feature, parent, child, joint, base, types, pythoncom, flip=True)
        native_limits = [float(joint["lower_rad"]), float(joint["upper_rad"])]
        feature = mate_features(model, base, types, pythoncom).get(creation["feature_name"])
        if feature is None:
            raise GateError("ANGLE_FINAL_LIMIT_FEATURE_MISSING", "native driver feature missing after the sign probe", {"joint": joint["joint"], "feature": creation["feature_name"]})
        if not angle_definition_exact(feature, joint, 0.0, base, types, pythoncom):
            feature, ladder = converge_angle_definition(model, feature, str(base.value(feature, "Name")), joint, 0.0, base, types, pythoncom)
            if ladder[-1] == "ladder_exhausted":
                raise GateError("ANGLE_FINAL_LIMIT_MODIFY_FAIL", "cannot apply accepted URDF limits to native driver", {"joint": joint["joint"], "native_limits": native_limits, "ladder": ladder})
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
        if not show_config_ok(model, config, base, types, pythoncom) or not bool(model.ForceRebuild3(True)):
            raise GateError("ANGLE_CONFIG_ACTIVATE_FAIL", "cannot activate arm configuration for seed verification", {"config": config})
        feature_map = mate_features(model, base, types, pythoncom)
        if config == ARM_CONFIGS[0]:
            baselines = {joint["joint"]: joint_relative_rotation(assembly, joint, base, types, pythoncom) for joint in joints}
        for row in drivers:
            dimension = model.Parameter(row["dimension_full_name"])
            if dimension is None:
                raise GateError("ANGLE_CONFIG_DIMENSION_MISSING", "native driver dimension did not resolve for configuration seed", {"joint": row["joint"], "dimension": row["dimension_full_name"]})
            feature = feature_map.get(row["feature_name"])
            if feature is None:
                raise GateError("ANGLE_CONFIG_FEATURE_MISSING", "native driver feature did not resolve for configuration seed", {"joint": row["joint"], "feature": row["feature_name"]})
            joint = joints[int(row["joint"].replace("joint", "")) - 1]
            requested = math.radians(float(q_deg[int(row["joint"].replace("joint", "")) - 1]))
            # Per-config writes are inert on this build (dimension drive) or
            # unreliable (ModifyDefinition), and the arm pose is per-config
            # via stored positions (probes V5_PROBE_LOOP1E_PERCONFIG*/PATHS).
            # The seed gate therefore MEASURES the joint pose delta against
            # the q=0 baseline on the accepted axis — stronger evidence than
            # a stored mate value.
            measured, transverse = project_delta_on_accepted_axis(baselines[row["joint"]], joint_relative_rotation(assembly, joint, base, types, pythoncom), joint)
            if abs(measured - requested) > 1.0e-6 or transverse > 1.0e-4:
                raise GateError("ANGLE_CONFIG_POSE_MISMATCH", "arm configuration pose does not equal the authorized q seed", {"joint": row["joint"], "config": config, "measured_rad": measured, "authorized_rad": requested, "transverse_rad": transverse})
            row.setdefault("configuration_seed_readback", []).append({"configuration": config, "native_angle_rad": measured, "authorized_q_rad": requested, "source_q_deg": float(q_deg[int(row["joint"].replace("joint", "")) - 1]), "authority": "Q0_GEOMETRY_OR_PREEXISTING_ENGINEERING_STOW_SEED_NOT_LOOP2_POSE_PROOF", "evidence": "MEASURED_PER_CONFIG_POSE_ON_ACCEPTED_AXIS"})
    if not show_config_ok(model, ARM_CONFIGS[0], base, types, pythoncom) or not bool(model.ForceRebuild3(True)):
        raise GateError("ANGLE_DRIVER_CONFIG_RESTORE_FAIL", "cannot restore local-arm q=0 configuration after driver seeding")
    return drivers


def sw_openable_path(path: Path) -> str:
    """Return an OpenDoc6-openable form of an absolute path.

    Direct ISldWorks.OpenDoc6 fails with swFileNotFoundError(2) for absolute
    paths longer than the Win32 MAX_PATH limit (260) even when the file
    exists; assembly dependent loads resolve such files relatively and
    succeed (proven live 2026-08-11: the 261/266-char staged vendor parts
    fail OpenDoc6, their 8.3 aliases open with errors=0).  GetShortPathNameW
    maps over-long paths to their 8.3 alias; the document's file NAME, which
    drives reference name-binding, is unchanged, and Path.resolve()
    canonicalizes the alias back to the long form, so every downstream audit
    comparison is unaffected.
    """
    text = str(path.resolve())
    if len(text) <= 259:
        return text
    buffer = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetShortPathNameW(text, buffer, len(buffer)) == 0:
        raise GateError("SHORT_PATH_FAIL", "GetShortPathNameW failed for over-long part path", {"path": norm(path)})
    return buffer.value


def configure_local_arm(sw: Any, staged: Dict[str, Any], base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    state = local_arm_state()
    if state["state"] == "PASS_RESUME":
        return dict(state["runtime_payload"])
    raise GateError("LOCAL_ARM_V2_MIGRATION_REQUIRED", "Loop1E may consume only the independent write-once local-arm V2 checkpoint; it may not write V1 payload into the V2 path", state)
    # SW2024 reference resolution is name-bound: documents that are already
    # open win reference resolution by file name.  Pre-open every V5-local
    # part so the staged assembly's lineage-baked references bind into the
    # V5-local tree on open; the saved reference table is then re-audited
    # cold below.  ReplaceComponents2 cannot perform this rebase: it returns
    # False on the donor's all-LIGHTWEIGHT components, and after
    # resolve-first or suppress-first it returns True while silently keeping
    # the lineage path (probe logs V5_PROBE_LOOP1E_*_20260811T21*.log); a
    # failed ReplaceComponents2 also leaks the old document as an invisible
    # unclosable doc.  ISldWorks.ReplaceReferencedDocument returns False for
    # these same-name lightweight references.  Pre-open binding is the only
    # probed technique that rebound every reference and persisted through
    # save + cold read-only reopen.
    # Hybrid read/write mode: the eight shorter part paths open READ-WRITE,
    # under which Transform2 stays readable even for LIGHTWEIGHT occurrences
    # (probe V5_PROBE_LOOP1E_TRANSFORM_OR_RESOLVE S1), so no resolve sandwich
    # is needed for driver synthesis; the two >260-char vendor files can only
    # open READ-ONLY via their 8.3 aliases (read-write 8.3 open fails
    # errors=2097152) and their transforms stay readable regardless.  The
    # legacy gripper is never resolved: suppress drives work directly from
    # LIGHTWEIGHT (probe 5), and a dependent-reload (close RO doc, then
    # SetSuppression2(1)) remains the probed fallback that keeps the V5-local
    # binding.
    prebind_titles: List[str] = []
    prebind: List[Dict[str, Any]] = []
    for part in sorted(LOCAL_ARM_ROOT.rglob("*.SLDPRT")):
        if part.name.startswith("~$"):
            continue
        open_form = sw_openable_path(part)
        read_only = open_form != str(part.resolve())
        part_doc, part_opened = open_doc(sw, Path(open_form), SW_DOC_PART, read_only, base, types, pythoncom)
        prebind_titles.append(str(base.value(part_doc, "GetTitle")))
        prebind.append({"path": norm(part), "via_short_8p3": read_only, "read_only_open": part_opened})
    model, opened = open_doc(sw, LOCAL_ARM, SW_DOC_ASSEMBLY, False, base, types, pythoncom)
    try:
        names = sorted(str(value) for value in base.as_list(base.value(model, "GetConfigurationNames")))
        if names != sorted(ARM_CONFIGS):
            raise GateError("LOCAL_ARM_CONFIG_SET_FAIL", "B51 copy configuration set drifted", {"actual": names, "expected": sorted(ARM_CONFIGS)})
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        repaired: List[Dict[str, Any]] = []
        for config in ARM_CONFIGS:
            if not show_config_ok(model, config, base, types, pythoncom):
                raise GateError("LOCAL_ARM_CONFIG_ACTIVATE_FAIL", "cannot activate arm configuration for reference rebind audit", {"config": config})
            comps = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]
            escaped = []
            for component in comps:
                current = Path(str(base.value(component, "GetPathName"))).resolve()
                row = {"configuration": config, "name2": str(base.value(component, "Name2")), "path": norm(current)}
                if LOCAL_ARM_ROOT.resolve() not in current.parents:
                    escaped.append(row)
                else:
                    repaired.append(row)
            if escaped:
                raise GateError("LOCAL_ARM_REFERENCE_REBIND_FAIL", "staged arm component did not bind into the V5-local tree after part pre-open", {"config": config, "escaped": escaped})
        driver_components = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]
        # Everything stays LIGHTWEIGHT end-to-end (the donor convention the
        # top-assembly motion/cold gates require): with the hybrid prebind,
        # Transform2 reads work on lightweight occurrences (probe
        # TRANSFORM_OR_RESOLVE S1) and datum feature traversal works via the
        # fresh live-handle enumerations after configuration switches.  A
        # dependent-reload resolve would block the return to lightweight
        # (LOCAL_ARM_RELIGHTWEIGHT_FAIL evidence, 20260812T0841Z: resolved
        # dependents refuse SetSuppression2(2) in every variant), so no
        # resolve step exists at all.
        native_drivers = configure_native_arm_drivers(model, assembly, driver_components, base, types, pythoncom)
        rows = []
        for config in ARM_CONFIGS:
            if not show_config_ok(model, config, base, types, pythoncom):
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
    # Close the pre-opened read-only part docs so the cold reopen below
    # resolves purely from the saved reference table (the honest audit that
    # LOCAL_ARM_REFERENCE_ESCAPE evaluates).
    for title in prebind_titles:
        try:
            sw.CloseDoc(title)
        except Exception:
            pass
    if int(base.value(sw, "GetDocumentCount")) != 0:
        raise GateError("LOCAL_ARM_WARM_CLOSE_FAIL", "warm local-arm documents remain open before cold audit", {"document_count": int(base.value(sw, "GetDocumentCount"))})
    cold, cold_open = open_doc(sw, LOCAL_ARM, SW_DOC_ASSEMBLY, True, base, types, pythoncom)
    try:
        cold_rows = []
        cold_driver_rows: Dict[str, Dict[str, Any]] = {}
        for config in ARM_CONFIGS:
            if not show_config_ok(cold, config, base, types, pythoncom):
                raise GateError("LOCAL_ARM_COLD_CONFIG_FAIL", "cold arm configuration activation failed", {"config": config})
            comps = top_components(cold, base, types, pythoncom)
            matches = [item for item in comps if str(base.value(item, "Name2")).split("/")[-1] == ARM_LEGACY_GRIPPER_LEAF]
            link6 = [item for item in comps if str(base.value(item, "Name2")).split("/")[-1] == ARM_LINK6_LEAF]
            if len(matches) != 1 or int(base.value(matches[0], "GetSuppression2")) != SW_COMPONENT_SUPPRESSED or len(link6) != 1:
                raise GateError("LOCAL_ARM_COLD_SEMANTIC_FAIL", "cold local arm does not retain no-legacy-gripper/link6 contract", {"config": config, "gripper_count": len(matches), "link6_count": len(link6)})
            feature_map = mate_features(cold, base, types, pythoncom)
            cold_assembly = base.wrap(cold, "IAssemblyDoc", types, pythoncom)
            if config == ARM_CONFIGS[0]:
                cold_baselines = {item["joint"]: joint_relative_rotation(cold_assembly, item, base, types, pythoncom) for item in accepted_urdf_joints()}
            config_driver_rows: List[Dict[str, Any]] = []
            for expected in native_drivers:
                feature = feature_map.get(expected["feature_name"])
                if feature is None or feature_error_code(feature, base) != 0 or bool(base.value(feature, "IsSuppressed")):
                    raise GateError("LOCAL_ARM_COLD_DRIVER_FEATURE_FAIL", "cold native joint driver feature is absent, errored, or suppressed", {"configuration": config, "joint": expected["joint"], "feature": expected["feature_name"]})
                definition = angle_mate_data(feature, base, types, pythoncom)
                minimum = float(base.value(definition, "MinimumAngle"))
                maximum = float(base.value(definition, "MaximumAngle"))
                dimension = angle_mate_dimension(feature, base, types, pythoncom)
                full_name = str(base.value(dimension, "FullName"))
                joint = next(item for item in accepted_urdf_joints() if item["joint"] == expected["joint"])
                measured, transverse = project_delta_on_accepted_axis(cold_baselines[expected["joint"]], joint_relative_rotation(cold_assembly, joint, base, types, pythoncom), joint)
                seed = next((item for item in expected["configuration_seed_readback"] if item["configuration"] == config), None)
                if (
                    not bool(base.value(definition, "IsAdvancedMate"))
                    or abs(minimum - float(expected["native_minimum_rad"])) > 1.0e-9
                    or abs(maximum - float(expected["native_maximum_rad"])) > 1.0e-9
                    or full_name != expected["dimension_full_name"]
                    or seed is None
                    or abs(measured - float(seed["native_angle_rad"])) > 1.0e-6
                    or transverse > 1.0e-4
                ):
                    raise GateError("LOCAL_ARM_COLD_DRIVER_READBACK_FAIL", "cold native joint driver definition/dimension/configuration pose differs from its live ledger", {"configuration": config, "joint": expected["joint"], "minimum": minimum, "maximum": maximum, "dimension": full_name, "measured_rad": measured, "transverse_rad": transverse, "seed": seed})
                row = {
                    "joint": expected["joint"],
                    "configuration": config,
                    "feature_name": expected["feature_name"],
                    "dimension_full_name": full_name,
                    "minimum_rad": minimum,
                    "maximum_rad": maximum,
                    "native_angle_rad": measured,
                    "feature_error_code": feature_error_code(feature, base),
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
        "reference_prebind": prebind,
        "reference_repairs": repaired,
        "native_joint_drivers": native_drivers,
        "legacy_gripper_file": file_fact(legacy_path),
        "configurations": cold_rows,
        "cold_open": cold_open,
        "verdict": "V5_LOOP1E0_LOCAL_ARM_NO_LEGACY_GRIPPER_WITH_SIX_NATIVE_LIMIT_ANGLE_DRIVERS_PASS",
    }
    raise GateError("LOCAL_ARM_V2_WRITE_PROHIBITED", "independent local-arm V2 is write-once and cannot be produced by Loop1E", payload)


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


def component_transform16(component: Any, base: Any) -> List[float]:
    raw = base.value(component, "Transform2")
    if raw is None:
        raise GateError("COMPONENT_TRANSFORM_NULL", "component has no Transform2", {"name2": str(base.value(component, "Name2"))})
    data = [float(value) for value in base.as_list(base.value(raw, "ArrayData"))]
    if len(data) != 16 or not all(math.isfinite(value) for value in data) or abs(data[12] - 1.0) > 2.0e-9:
        raise GateError("COMPONENT_TRANSFORM_SHAPE_FAIL", "component transform is not finite rigid T16", {"name2": str(base.value(component, "Name2")), "data": data})
    return data


def transform_error(actual: Sequence[float], expected: Sequence[float]) -> Dict[str, float]:
    if len(actual) != 16 or len(expected) != 16 or not all(math.isfinite(float(value)) for value in (*actual, *expected)):
        raise GateError("TRANSFORM_COMPARE_SHAPE_FAIL", "transform comparison requires two finite 16-value transforms", {"actual_length": len(actual), "expected_length": len(expected)})
    translation_mm = math.sqrt(sum((float(actual[index]) - float(expected[index])) ** 2 for index in (9, 10, 11))) * 1000.0
    ar = [[float(actual[column * 3 + row]) for column in range(3)] for row in range(3)]
    er = [[float(expected[column * 3 + row]) for column in range(3)] for row in range(3)]
    relative = [[sum(er[k][row] * ar[k][column] for k in range(3)) for column in range(3)] for row in range(3)]
    cosine = max(-1.0, min(1.0, (sum(relative[index][index] for index in range(3)) - 1.0) / 2.0))
    return {"translation_mm": translation_mm, "rotation_deg": math.degrees(math.acos(cosine))}


def assert_transform_close(actual: Sequence[float], expected: Sequence[float], label: str) -> Dict[str, float]:
    error = transform_error(actual, expected)
    if error["translation_mm"] > 2.0e-3 or error["rotation_deg"] > 2.0e-3:
        raise GateError("TRANSFORM_READBACK_FAIL", "component transform differs from P9 fresh oracle", {"label": label, "error": error, "actual": list(actual), "expected": list(expected)})
    return error


def assert_top_side_identity(components: Mapping[str, Any], base: Any) -> Dict[str, Any]:
    rows = {}
    for side, role in (("L", "LEFT_SOLAR_ARRAY"), ("R", "RIGHT_SOLAR_ARRAY")):
        component = components[role]
        transform = component_transform16(component, base)
        row = {
            "side": side,
            "path": norm(Path(str(base.value(component, "GetPathName")))),
            "referenced_configuration": str(base.value(component, "ReferencedConfiguration")),
            "solving": int(base.value(component, "Solving")),
            "suppression": int(base.value(component, "GetSuppression2")),
            "transform16": transform,
            "identity_error": assert_transform_close(transform, IDENTITY_T16, f"top_side_{side}_identity"),
        }
        if row["solving"] != SW_COMPONENT_RIGID or row["suppression"] != SW_COMPONENT_RESOLVED:
            raise GateError("TOP_SOLAR_SIDE_STATE_FAIL", "top solar side is not resolved and rigid", row)
        rows[side] = row
    return rows


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
    raw_mate = base.value(feature, "GetSpecificFeature2")
    if raw_mate is None:
        raise GateError("LOCK_MATE_OBJECT_NULL", "created lock mate has no IMate2", {"name": name})
    mate = base.wrap(raw_mate, "IMate2", types, pythoncom)
    if str(base.value(feature, "Name")) != name or int(base.value(mate, "Type")) != SW_MATE_LOCK or feature_error_code(feature, base) != 0 or bool(base.value(feature, "IsSuppressed")):
        raise GateError("LOCK_MATE_HEALTH_FAIL", "created lock mate is unhealthy", {"name": name})
    return {"name": name, "type": SW_MATE_LOCK, "endpoints": [str(base.value(first, "Name2")), str(base.value(second, "Name2"))], "endpoint_paths": sorted([norm(Path(str(base.value(first, "GetPathName")))), norm(Path(str(base.value(second, "GetPathName"))))]), "feature_error_code": 0, "suppressed": False}


def set_component_config(model: Any, assembly: Any, component: Any, ref_config: str, solving: int, base: Any) -> None:
    model.ClearSelection2(True)
    if not bool(component.Select4(False, None, False)):
        raise GateError("COMP_CONFIG_SELECT_FAIL", "cannot select component for configuration property", {"name2": str(base.value(component, "Name2"))})
    ok = bool(assembly.CompConfigProperties6(SW_COMPONENT_RESOLVED, solving, SW_COMPONENT_VISIBLE, True, ref_config, False, False, 0))
    model.ClearSelection2(True)
    if not ok or str(base.value(component, "ReferencedConfiguration")) != ref_config or int(base.value(component, "Solving")) != solving:
        raise GateError("COMP_CONFIG_PROPERTY_FAIL", "CompConfigProperties6 did not read back", {"name2": str(base.value(component, "Name2")), "ref_config": ref_config, "solving": solving, "ok": ok, "readback_config": str(base.value(component, "ReferencedConfiguration")), "readback_solving": int(base.value(component, "Solving"))})


def configure_top(model: Any, assembly: Any, components: Mapping[str, Any], base: Any, types: Any, pythoncom: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
        if not show_config_ok(model, name, base, types, pythoncom):
            raise GateError("TOP_CONFIG_ACTIVATE_FAIL", "cannot activate top configuration", {"name": name})
        # Component handles collected before configuration creation/switches
        # go stale: Select4 on them returns False (COMP_CONFIG_SELECT_FAIL on
        # the ARM occurrence, 20260812T0936Z).  Re-acquire live occurrences
        # after every activation.
        components = fresh_role_components(model, base, types, pythoncom)
        set_component_config(model, assembly, components["ARM"], spec["arm"], SW_COMPONENT_FLEXIBLE, base)
        set_component_config(model, assembly, components["LEFT_SOLAR_ARRAY"], spec["left_wing"], SW_COMPONENT_RIGID, base)
        set_component_config(model, assembly, components["RIGHT_SOLAR_ARRAY"], spec["right_wing"], SW_COMPONENT_RIGID, base)
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
            "same_physical_occurrences": {role: str(base.value(components[role], "Name2")) for role in ("LEFT_SOLAR_ARRAY", "RIGHT_SOLAR_ARRAY", "GRIPPER", "HDRM")},
        })
    if not show_config_ok(model, "SOLAR_DEPLOYED_NOMINAL", base, types, pythoncom):
        raise GateError("TOP_CONFIG_RESTORE_FAIL", "cannot restore SOLAR_DEPLOYED_NOMINAL")
    return rows, fresh_role_components(model, base, types, pythoncom)


def fresh_role_components(model: Any, base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    """Live role -> occurrence map, re-derived from the assembly each call."""
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    by_path: Dict[str, Any] = {}
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        by_path[os.path.normcase(str(Path(str(base.value(component, "GetPathName"))).resolve()))] = component
    role_paths = {"SPACECRAFT_PRIMARY": SPACECRAFT_PRIMARY, "SPACECRAFT_B601_MOUNT": SPACECRAFT_B601_MOUNT, "ARM": LOCAL_ARM, **V5_SUBASSEMBLIES}
    components: Dict[str, Any] = {}
    missing = []
    for role, path in role_paths.items():
        component = by_path.get(os.path.normcase(str(path.resolve())))
        if component is None:
            missing.append(role)
        else:
            components[role] = component
    if missing:
        raise GateError("TOP_ROLE_COMPONENT_MISSING", "live top-assembly occurrence does not resolve for role", {"missing": missing})
    return components


def exact_reference_gate(model: Any, components: Mapping[str, Any], base: Any) -> Dict[str, Any]:
    expected_top = {os.path.normcase(str(path.resolve())) for path in (SPACECRAFT_PRIMARY, SPACECRAFT_B601_MOUNT, LOCAL_ARM, *V5_SUBASSEMBLIES.values())}
    actual_top = [component_path(item, base) for item in components.values()]
    if Counter(actual_top) != Counter(expected_top):
        raise GateError("TOP_REFERENCE_SET_FAIL", "top-level occurrence paths are not exact", {"expected": sorted(expected_top), "actual": sorted(actual_top)})
    solar = audit_solar_chain()
    allowed_solar = {os.path.normcase(str(Path(row["path"]).resolve())) for row in solar["payload"]["cad_artifacts"]}
    allowed_solar.update(os.path.normcase(str(Path(row["path"]).resolve())) for row in solar["payload"]["immutable_tree"] if Path(row["path"]).suffix.upper() in {".SLDASM", ".SLDPRT"})
    old_live_denied = {os.path.normcase(str(path.resolve())) for path in LEGACY_SOLAR_DENY_PATHS}
    allowed_roots = (RUN_ROOT.resolve(), F3R2_SPACECRAFT_ROOT.resolve())
    deps = dependency_paths(model, base)
    escaped = [path for path in deps if not any(root == Path(path).resolve() or root in Path(path).resolve().parents for root in allowed_roots)]
    if escaped:
        raise GateError("TOP_REFERENCE_ESCAPE", "top assembly dependency escapes V5/protected F3R2 spacecraft roots", {"escaped": escaped})
    denied = []
    wrong_attempt = []
    solar_attempts_root = (VALIDATION / "solar_r2_attempts").resolve()
    quarantine = (VALIDATION / "quarantine").resolve()
    for raw in deps:
        path = Path(raw).resolve()
        key = os.path.normcase(str(path))
        if key in old_live_denied or path == quarantine or quarantine in path.parents:
            denied.append(key)
        if solar_attempts_root in path.parents and SOLAR_ATTEMPT_ROOT.resolve() not in path.parents and path != SOLAR_ATTEMPT_ROOT.resolve():
            wrong_attempt.append(key)
        if SOLAR_ATTEMPT_ROOT.resolve() in path.parents and path.suffix.upper() in {".SLDASM", ".SLDPRT"} and key not in allowed_solar:
            wrong_attempt.append(key)
    if denied or wrong_attempt:
        raise GateError("TOP_REFERENCE_DENY_FAIL", "top dependency reaches legacy/quarantine/non-P9 CAD", {"denied": sorted(set(denied)), "wrong_attempt": sorted(set(wrong_attempt))})
    return {"top_level_paths": sorted(actual_top), "dependency_paths": deps, "allowed_roots": [norm(root) for root in allowed_roots], "authorized_p9_cad_count": len(allowed_solar), "explicit_denied_paths": sorted(old_live_denied), "quarantine_root": norm(quarantine), "escaped": [], "denied_found": [], "wrong_attempt_found": []}


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
        if suppression == SW_COMPONENT_SUPPRESSED and (leaf == ARM_LEGACY_GRIPPER_LEAF or leaf.startswith(HDRM_PROXY_LEAF_PREFIX)):
            # Whitelisted nonphysical occurrences: the legacy gripper detail
            # (replaced by the V5 Loop1C1 gripper) and the HDRM latch state
            # proxies (exactly one of six latch-slider occurrences is resolved
            # per HDRM configuration by the accepted Loop1D design; the other
            # five are suppressed state proxies in every configuration).
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
    solar = audit_solar_chain()
    moving_by_side: Dict[str, List[Any]] = {}
    root_by_side: Dict[str, List[Any]] = {}
    partition_audit: Dict[str, Any] = {}
    for side, role in (("L", "LEFT_SOLAR_ARRAY"), ("R", "RIGHT_SOLAR_ARRAY")):
        side_root = components[role]
        module_roots: Dict[str, Any] = {}
        direct_children = child_components(side_root, base, types, pythoncom)
        for index in (1, 2, 3):
            key = f"{side}{index}"
            wanted = Path(str(solar["module_paths"][key])).resolve()
            matches = [item for item in direct_children if Path(str(base.value(item, "GetPathName"))).resolve() == wanted]
            if len(matches) != 1:
                raise GateError("SOLAR_MODULE_ROOT_SET_FAIL", "side does not expose one exact P9 module root", {"side": side, "module": key, "matches": [component_name2(item, base) for item in matches]})
            module_roots[key] = matches[0]
        moving = unique_components([item for root in module_roots.values() for item in solid_components_under(root, base, types, pythoncom)], base)
        moving_names = {component_name2(item, base) for item in moving}
        roots = [item for item in solids[role] if component_name2(item, base) not in moving_names]
        if len(moving) != 20 or len(roots) != 10 or len(solids[role]) != 30:
            raise GateError("SOLAR_ROLE_PARTITION_CARDINALITY_FAIL", "P9 side must partition into 20 moving and 10 fixed root solids", {"side": side, "moving": len(moving), "root": len(roots), "total": len(solids[role])})
        old_panel = [item for item in solids[role] if Path(str(base.value(item, "GetPathName"))).name.upper() in LEGACY_SOLAR_DENY_LEAVES]
        if old_panel or moving_names & {component_name2(item, base) for item in roots}:
            raise GateError("SOLAR_ROLE_PARTITION_OVERLAP", "P9 moving/root partition overlaps or contains old panel", {"side": side, "old_panel": [component_name2(item, base) for item in old_panel]})
        moving_by_side[side], root_by_side[side] = moving, roots
        partition_audit[side] = {"module_roots": {key: component_name2(item, base) for key, item in module_roots.items()}, "moving_solid_count": len(moving), "fixed_root_solid_count": len(roots), "complete_side_solid_count": len(solids[role]), "old_single_panel_count": 0}
    left_panel, right_panel = moving_by_side["L"], moving_by_side["R"]
    wing_root = root_by_side["L"] + root_by_side["R"]
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


def flatten_ui1(value: Any) -> bytes:
    """Recursively normalize a nested VT_UI1 payload without COM access.

    pywin32 may expose ``VT_ARRAY | VT_UI1`` as bytes, a flat tuple of ints,
    or a tuple/list containing bytes-like leaves.  Silent modulo conversion is
    prohibited: a non-byte integer or an unsupported leaf is evidence of a
    marshaling mismatch and must hold the gate.
    """
    output = bytearray()

    def visit(node: Any, trail: Tuple[int, ...]) -> None:
        if isinstance(node, bool):
            raise GateError("PERSIST_UI1_TYPE_FAIL", "boolean is not a VT_UI1 byte", {"trail": list(trail)})
        if isinstance(node, int):
            if not 0 <= node <= 0xFF:
                raise GateError("PERSIST_UI1_RANGE_FAIL", "VT_UI1 integer is outside [0,255]", {"trail": list(trail), "value": node})
            output.append(node)
            return
        if isinstance(node, (bytes, bytearray, memoryview)):
            output.extend(bytes(node))
            return
        if isinstance(node, (str, Mapping)) or node is None:
            raise GateError("PERSIST_UI1_TYPE_FAIL", "unsupported VT_UI1 leaf", {"trail": list(trail), "type": type(node).__name__})
        try:
            children = list(node)
        except TypeError as exc:
            raise GateError("PERSIST_UI1_TYPE_FAIL", "unsupported VT_UI1 leaf", {"trail": list(trail), "type": type(node).__name__}) from exc
        for index, child in enumerate(children):
            visit(child, trail + (index,))

    visit(value, ())
    return bytes(output)


def persist_payload_integrity(data: bytes) -> Dict[str, Any]:
    """Prove canonical length/hash/base64 equality without invoking COM."""
    if not isinstance(data, bytes) or not data:
        raise GateError("PERSIST_REFERENCE_EMPTY", "canonical persistent reference must be non-empty bytes", {"type": type(data).__name__, "bytes": len(data) if isinstance(data, bytes) else None})
    encoded = base64.b64encode(data).decode("ascii")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise GateError("PERSIST_REFERENCE_CANONICAL_BASE64_FAIL", "canonical persistent reference did not strict-base64 decode", {"bytes": len(data)}) from exc
    if decoded != data or len(decoded) != len(data):
        raise GateError("PERSIST_REFERENCE_CANONICAL_ROUNDTRIP_FAIL", "strict base64 changed persistent-reference bytes/count", {"source_bytes": len(data), "decoded_bytes": len(decoded)})
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "base64": encoded,
        "strict_base64_roundtrip_exact": True,
        "count_source": PERSIST_REFERENCE_VALIDATION_POLICY["runtime_count_source"],
    }


def persist_bytes_pure_self_test() -> Dict[str, Any]:
    """Exercise UI1 shapes plus canonical count/hash/base64 integrity."""
    expected = bytes((0, 1, 2, 3, 127, 128, 254, 255))
    vectors = (
        expected,
        [0, (1, b"\x02\x03"), [bytearray((127, 128)), memoryview(b"\xfe\xff")]],
        ((item for item in (0, 1)), (2, 3), [127, 128, 254, 255]),
    )
    for index, vector in enumerate(vectors):
        actual = flatten_ui1(vector)
        if actual != expected:
            raise GateError(
                "PERSIST_UI1_SELF_TEST_VECTOR_FAIL",
                "recursive VT_UI1 flattening produced the wrong byte sequence",
                {"vector": index, "actual_hex": actual.hex(), "expected_hex": expected.hex()},
            )
        integrity = persist_payload_integrity(actual)
        if integrity["bytes"] != len(expected) or integrity["sha256"] != hashlib.sha256(expected).hexdigest().upper() or base64.b64decode(integrity["base64"], validate=True) != expected:
            raise GateError("PERSIST_UI1_SELF_TEST_INTEGRITY_FAIL", "canonical count/hash/base64 proof differs", {"vector": index, "integrity": integrity})
    rejected = 0
    for invalid in (-1, 256, True, "UI1", {"byte": 1}, [0, object()]):
        try:
            flatten_ui1(invalid)
        except GateError as exc:
            if exc.code not in {"PERSIST_UI1_TYPE_FAIL", "PERSIST_UI1_RANGE_FAIL"}:
                raise
            rejected += 1
        else:
            raise GateError("PERSIST_UI1_SELF_TEST_REJECTION_FAIL", "invalid VT_UI1 input was accepted", {"type": type(invalid).__name__, "repr": repr(invalid)})
    return {
        "schema": "F3R2_V5_PERSIST_UI1_PURE_SELF_TEST_V1",
        "accepted_vectors": len(vectors),
        "rejected_vectors": rejected,
        "expected_bytes": len(expected),
        "expected_sha256": hashlib.sha256(expected).hexdigest().upper(),
        "strict_base64_roundtrip_exact": True,
        "validation_policy": dict(PERSIST_REFERENCE_VALIDATION_POLICY),
        "verdict": "V5_PERSIST_UI1_RECURSIVE_FLATTEN_PURE_SELF_TEST_PASS",
    }


def script_ast_contract_self_test() -> Dict[str, Any]:
    """COM-free AST gate for known fatal call-name/API regressions."""
    source_path = Path(__file__).resolve()
    source = source_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(source_path))
        compile(source, str(source_path), "exec")
    except (SyntaxError, ValueError) as exc:
        raise GateError("SCRIPT_AST_PARSE_FAIL", "Loop1E script does not parse/compile", {"exception": repr(exc)}) from exc
    function_defs = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    direct_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    attribute_calls = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    imported_names: set[str] = set()
    assigned_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
    argument_names = {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    class_defs = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)
    import builtins
    undefined_direct_calls = sorted({
        node.func.id for node in direct_calls
        if node.func.id not in set(function_defs) | class_defs | imported_names | assigned_names | argument_names | set(dir(builtins))
    })
    undefined_angle_calls = [node.lineno for node in direct_calls if node.func.id == "angle_dimension"]
    correct_angle_calls = [node for node in direct_calls if node.func.id == "angle_mate_dimension"]
    wrong_arity = [node.lineno for node in correct_angle_calls if len(node.args) != 4 or node.keywords]
    forbidden_count_calls = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "GetPersistReferenceCount3"]
    if undefined_direct_calls:
        raise GateError("SCRIPT_AST_UNDEFINED_DIRECT_CALL_FAIL", "one or more direct call names have no definition/import/assignment/argument/builtin binding", {"undefined_direct_calls": undefined_direct_calls})
    if function_defs.count("angle_mate_dimension") != 1 or undefined_angle_calls or not correct_angle_calls or wrong_arity:
        raise GateError("SCRIPT_AST_ANGLE_CALL_FAIL", "angle-mate dimension calls are undefined/missing/wrong-arity", {"definition_count": function_defs.count("angle_mate_dimension"), "undefined_angle_dimension_lines": undefined_angle_calls, "correct_call_count": len(correct_angle_calls), "wrong_arity_lines": wrong_arity})
    if forbidden_count_calls:
        raise GateError("SCRIPT_AST_PERSIST_COUNT_API_FAIL", "unusable GetPersistReferenceCount3 call re-entered the runtime path", {"lines": forbidden_count_calls})
    forbidden_activation = sorted({name for name in attribute_calls if name in {"Dispatch", "DispatchEx", "CoCreateInstance", "ExitApp"}})
    if forbidden_activation:
        raise GateError("SCRIPT_AST_APPLICATION_LIFECYCLE_FAIL", "attach-only script contains an application activation/termination call", {"calls": forbidden_activation})
    exact_top = (
        "SOLAR_STOWED", "SOLAR_DEPLOY_STAGE1", "SOLAR_DEPLOY_STAGE2",
        "SOLAR_DEPLOYED_NOMINAL", "SOLAR_LEFT_FAIL", "SOLAR_RIGHT_FAIL",
        "SOLAR_BOTH_FAIL", "SOLAR_DEPLOY_ARM_LOCKED", "HDRM_RELEASE",
        "SERVICE", "RELEASE_CLEAR_END_STATE",
    )
    if tuple(TOP_CONFIGS) != exact_top or len(TOP_CONFIGS) != 11:
        raise GateError("SCRIPT_AST_TOP_CONFIG_SET_FAIL", "top configuration authority is not the exact ordered 11-state set", {"actual": list(TOP_CONFIGS), "expected": list(exact_top)})
    return {
        "schema": "F3R2_V5_LOOP1E_SCRIPT_AST_CONTRACT_SELF_TEST_V1",
        "script": file_fact(source_path),
        "compile_pass": True,
        "angle_mate_dimension_definition_count": 1,
        "angle_mate_dimension_call_count": len(correct_angle_calls),
        "undefined_direct_call_names": [],
        "undefined_angle_dimension_call_count": 0,
        "get_persist_reference_count3_call_count": 0,
        "application_activation_or_termination_call_count": 0,
        "exact_top_configuration_count": 11,
        "verdict": "V5_LOOP1E_SCRIPT_AST_CONTRACT_SELF_TEST_PASS",
    }


def offline_self_test() -> Dict[str, Any]:
    persist = persist_bytes_pure_self_test()
    script = script_ast_contract_self_test()
    return {
        "schema": "F3R2_V5_LOOP1E_OFFLINE_SELF_TEST_V2",
        "persist_reference": persist,
        "script_ast_contract": script,
        "validation_policy": dict(PERSIST_REFERENCE_VALIDATION_POLICY),
        "verdict": "V5_LOOP1E_OFFLINE_PERSIST_AND_AST_SELF_TEST_PASS",
    }


def persist_bytes(extension: Any, entity: Any, base: Any) -> bytes:
    raw = extension.GetPersistReference3(entity)
    if raw is None:
        raise GateError("PERSIST_REFERENCE_NULL", "GetPersistReference3 returned null")
    source = raw if isinstance(raw, (bytes, bytearray, memoryview, list, tuple)) else base.as_list(raw)
    data = flatten_ui1(source)
    # Do not call GetPersistReferenceCount3 here.  SW2024 SP05's makepy
    # wrapper for DISPID 99 is observably unusable (DISP_E_BADPARAMCOUNT).
    # Canonical count/hash/base64 integrity is proven now; resolve_persist adds
    # the independent cold COM resolution + exact byte roundtrip witness.
    persist_payload_integrity(data)
    return data


def persist_base64(extension: Any, entity: Any, base: Any) -> str:
    return str(persist_payload_integrity(persist_bytes(extension, entity, base))["base64"])


def resolve_persist(extension: Any, encoded: str, base: Any, pythoncom: Any, label: str) -> Tuple[Any, Dict[str, Any]]:
    from win32com.client import VARIANT
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise GateError("PERSIST_REFERENCE_BASE64_FAIL", "persistent reference is not strict base64", {"label": label}) from exc
    integrity = persist_payload_integrity(data)
    if integrity["base64"] != encoded:
        raise GateError("PERSIST_REFERENCE_BASE64_CANONICAL_FAIL", "persistent reference is valid but not canonical base64", {"label": label, "bytes": len(data)})
    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, list(data))
    obj, outs = base.unpack(extension.GetObjectByPersistReference3(typed, 0))
    error = int(outs[0]) if outs else 0
    if obj is None or error != 0 or persist_bytes(extension, obj, base) != data:
        raise GateError("PERSIST_REFERENCE_COLD_FAIL", "persistent reference did not resolve/round-trip exactly", {"label": label, "error": error})
    return obj, {"label": label, "bytes": len(data), "sha256": integrity["sha256"], "count_source": integrity["count_source"], "strict_base64_roundtrip_exact": True, "resolve_error": error, "roundtrip_exact": True}


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
    """Relative transform A^-1 B, i.e. the pose of `second` in `first`'s frame.

    SW2024 SP5 makepy quirk (same dual-name class as selection_manager above):
    the I-prefixed IMathTransform members are present in the typelib but are not
    invocable through IDispatch on this build - both raise 61836 "cannot read
    write-only property". Their non-prefixed siblings work:

        IInverse  (dispid 10) FAIL 61836   ->  Inverse  (dispid 9) OK
        IMultiply (dispid  2) FAIL 61836   ->  Multiply (dispid 1) OK

    NOTE the operands are deliberately swapped relative to the IMultiply form.
    Dispid-1 Multiply composes in the opposite order: X.Multiply(Y) == M_Y x M_X.
    So preserving A^-1 B requires second.Multiply(inverse); a name-only swap
    would compute B A^-1 instead. That error would NOT surface as a failure -
    this function is called both to record the expected transform and to
    re-measure it after cold reopen, and the two are compared at 1e-7, so a
    consistently-wrong order cancels out and passes while writing a meaningless
    link6->gripper transform into the motion contract.

    Verified on this install over three independent transform pairs, residual
    <= 1.11e-16 against an independent 4x4 computation:
    04_validation/LOOP1E_CORRECTED_ORDER_RECEIPT.json
    """
    first_transform = total_transform_object(first, base, types, pythoncom)
    second_transform = total_transform_object(second, base, types, pythoncom)
    inverse_raw = first_transform.Inverse()
    if inverse_raw is None:
        raise GateError("RELATIVE_TRANSFORM_INVERSE_FAIL", "Inverse returned null", {"first": component_name2(first, base)})
    inverse = base.wrap(inverse_raw, "IMathTransform", types, pythoncom)
    relative_raw = second_transform.Multiply(inverse)
    if relative_raw is None:
        raise GateError("RELATIVE_TRANSFORM_MULTIPLY_FAIL", "Multiply returned null")
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
    # SW2024 makepy: FeatureByName is NOT a member of IModelDoc2. The typelib
    # exposes it only on the document-type-specific interfaces (IAssemblyDoc,
    # IPartDoc, IDrawingDoc) and on IComponent2. LOCAL_ARM is a sub-assembly, so
    # the feature lookup must go through IAssemblyDoc - the same interface this
    # script already uses for assembly-level work (see line 2963 and 1226).
    # Calling it on the IModelDoc2 wrapper raises AttributeError, which is what
    # ended Loop1E attempt 2 on 2026-08-20 at this line.
    owner_doc_type = int(base.value(owner_model, "GetType"))
    if owner_doc_type != SW_DOC_ASSEMBLY:
        raise GateError(
            "LOCAL_ARM_OWNER_NOT_ASSEMBLY",
            "LOCAL_ARM owner document is not an assembly, so IAssemblyDoc feature lookup is invalid",
            {"actual_doc_type": owner_doc_type, "expected_doc_type": SW_DOC_ASSEMBLY},
        )
    owner_features = base.wrap(owner_model_raw, "IAssemblyDoc", types, pythoncom)
    rows: List[Dict[str, Any]] = []
    for index, accepted in enumerate(accepted_urdf_joints(), start=1):
        source_row = source[index - 1]
        feature_name = f"V5_LOOP2_{accepted['joint'].upper()}_LIMIT_ANGLE"
        raw_feature = owner_features.FeatureByName(feature_name)
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
            or feature_error_code(feature, base) != 0
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


def hdrm_proxy_suppression_authority() -> Dict[str, Dict[str, int]]:
    """Map Loop1D proxy leaves to top-level 0/2 states by HDRM config."""
    receipt = load_json(LOOP1D_RECEIPT)
    assemblies = receipt.get("native_subassemblies")
    matches = [row for row in assemblies if isinstance(row, Mapping) and row.get("name") == "ARM_HDRM_FUNCTIONAL_ENVELOPE"] if isinstance(assemblies, list) else []
    if len(matches) != 1 or not isinstance(matches[0].get("configuration_ledgers"), list):
        raise GateError("HDRM_PROXY_AUTHORITY_ASSEMBLY_FAIL", "Loop1D receipt lacks one HDRM configuration ledger", {"matches": len(matches)})
    authority: Dict[str, Dict[str, int]] = {}
    for row in matches[0]["configuration_ledgers"]:
        if not isinstance(row, Mapping) or not isinstance(row.get("component_states"), list):
            raise GateError("HDRM_PROXY_AUTHORITY_ROW_FAIL", "Loop1D HDRM configuration row is incomplete", {"row": row})
        configuration = str(row.get("configuration", ""))
        proxy_states: Dict[str, int] = {}
        for state in row["component_states"]:
            if not isinstance(state, Mapping):
                continue
            leaf = str(state.get("name2", "")).split("/")[-1]
            if leaf.startswith(HDRM_PROXY_LEAF_PREFIX):
                source_state = int(state.get("suppression", -1))
                if source_state not in {0, 1, 2}:
                    raise GateError("HDRM_PROXY_AUTHORITY_STATE_FAIL", "Loop1D proxy state is not suppressed/resolved", {"configuration": configuration, "leaf": leaf, "suppression": source_state})
                proxy_states[leaf] = SW_COMPONENT_SUPPRESSED if source_state == 0 else SW_COMPONENT_RESOLVED
        if len(proxy_states) != 6 or sum(value == SW_COMPONENT_RESOLVED for value in proxy_states.values()) != 1:
            raise GateError("HDRM_PROXY_AUTHORITY_SET_FAIL", "Loop1D must resolve exactly one of six HDRM proxies", {"configuration": configuration, "proxy_states": proxy_states})
        authority[configuration] = proxy_states
    expected_configs = {"LOCKED", "RELEASE_ARMED", "RELEASE_START", "RELEASED", "RELEASE_FAILED", "GROUND_UNLOCK"}
    if set(authority) != expected_configs or len({tuple(sorted(row)) for row in authority.values()}) != 1:
        raise GateError("HDRM_PROXY_AUTHORITY_CONFIG_FAIL", "Loop1D HDRM authority is not the exact six-state/six-proxy matrix", {"configurations": sorted(authority)})
    return authority


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
        "top_configurations": list(TOP_CONFIGS),
        "expected_suppression_by_pose_config": {str(config): SW_COMPONENT_SUPPRESSED for config in TOP_CONFIGS},
        "reason": "LEGACY_GRIPPER_REPLACED_BY_V5_LOOP1C1_NONPHYSICAL_FOR_LOOP2",
        "expected_suppression_state": SW_COMPONENT_SUPPRESSED,
        "exclude_from_motion_comparison_sets": True,
    }]
    # The accepted Loop1D HDRM design resolves exactly one of six latch-slider
    # state proxies per referenced HDRM configuration.  All six occurrences
    # must be conditionally whitelisted: collecting only the five suppressed
    # in the currently-active RELEASED state would omit the RELEASED proxy
    # when a LOCKED top configuration is activated.  The exact 11-state map is
    # derived from the write-once Loop1D configuration ledger.
    source_authority = hdrm_proxy_suppression_authority()
    proxies = [
        proxy for proxy in component_tree(components["HDRM"], base, types, pythoncom)
        if component_name2(proxy, base).split("/")[-1].startswith(HDRM_PROXY_LEAF_PREFIX)
    ]
    expected_proxy_leaves = set(source_authority["LOCKED"])
    actual_proxy_leaves = {component_name2(proxy, base).split("/")[-1] for proxy in proxies}
    if len(proxies) != 6 or actual_proxy_leaves != expected_proxy_leaves:
        raise GateError("HDRM_PROXY_LIVE_SET_FAIL", "top HDRM does not expose the exact six Loop1D proxy occurrences", {"actual": sorted(actual_proxy_leaves), "expected": sorted(expected_proxy_leaves)})
    for proxy in sorted(proxies, key=lambda item: component_name2(item, base)):
        proxy_leaf = component_name2(proxy, base).split("/")[-1]
        proxy_path = Path(str(base.value(proxy, "GetPathName"))).resolve()
        if not proxy_path.is_file() or RUN_ROOT.resolve() not in proxy_path.parents:
            raise GateError("HDRM_PROXY_PATH_FAIL", "HDRM state proxy is not one exact V5 physical file", {"name2": component_name2(proxy, base), "path": norm(proxy_path)})
        expected_by_top = {
            top_config: int(source_authority[str(spec["hdrm"])][proxy_leaf])
            for top_config, spec in TOP_CONFIGS.items()
        }
        suppressed_whitelist.append({
            "semantic_role": "HDRM_LATCH_STATE_PROXY",
            "component_name2": component_name2(proxy, base),
            "component_path": norm(proxy_path),
            "component_path_sha256": sha256(proxy_path),
            "top_configurations": list(TOP_CONFIGS),
            "expected_suppression_by_pose_config": expected_by_top,
            "reason": "LOOP1D_STATE_PROXY_EXACTLY_ONE_OF_SIX_RESOLVED_PER_CONFIG_NONPHYSICAL_FOR_LOOP2",
            "expected_suppression_state": "CONFIGURATION_DEPENDENT_0_OR_2",
            "suppressed_top_configurations": [name for name, state in expected_by_top.items() if state == SW_COMPONENT_SUPPRESSED],
            "resolved_top_configurations": [name for name, state in expected_by_top.items() if state == SW_COMPONENT_RESOLVED],
            "exclude_from_motion_comparison_sets": True,
        })
    if len(suppressed_whitelist) != 7:
        raise GateError("SUPPRESSED_WHITELIST_CARDINALITY_FAIL", "motion whitelist must contain one legacy gripper plus all six HDRM proxies", {"count": len(suppressed_whitelist)})
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


def promote_no_replace(staging_path: Path, target_path: Path) -> Dict[str, Any]:
    """Atomically publish a cold-verified same-directory file without replace."""
    source = staging_path.resolve()
    destination = target_path.resolve()
    if not is_loop1e_staging_path(source) or destination != TARGET.resolve() or source.parent != destination.parent:
        raise GateError("TOP_PROMOTION_PATH_FAIL", "promotion endpoints are outside the exact Loop1E transaction contract", {"source": norm(source), "destination": norm(destination)})
    if not source.is_file():
        raise GateError("TOP_PROMOTION_SOURCE_MISSING", "cold-verified staging artifact is missing", {"source": norm(source)})
    if destination.exists():
        raise GateError("TOP_PROMOTION_NO_REPLACE_HOLD", "final target already exists; replacement is prohibited", {"destination": norm(destination)})
    before = file_fact(source)
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file_ex = kernel32.MoveFileExW
        move_file_ex.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        move_file_ex.restype = ctypes.c_int
        movefile_write_through = 0x00000008
        if not move_file_ex(str(source), str(destination), movefile_write_through):
            error = ctypes.get_last_error()
            raise GateError(
                "TOP_PROMOTION_NO_REPLACE_FAIL",
                "MoveFileExW without MOVEFILE_REPLACE_EXISTING failed",
                {"source": norm(source), "destination": norm(destination), "winerror": error},
            )
        mechanism = "MoveFileExW_WRITE_THROUGH_NO_REPLACE"
    else:
        # os.link is create-if-absent; unlike os.replace it cannot overwrite the
        # destination.  This branch exists for static/pure validation only; the
        # production environment is pinned to Windows/SOLIDWORKS.
        try:
            os.link(source, destination)
        except FileExistsError as exc:
            raise GateError("TOP_PROMOTION_NO_REPLACE_HOLD", "final target appeared during promotion", {"destination": norm(destination)}) from exc
        try:
            source.unlink()
        except OSError as exc:
            raise GateError("TOP_PROMOTION_STAGE_UNLINK_FAIL", "no-replace link was created but staging unlink failed", {"source": norm(source), "destination": norm(destination)}) from exc
        mechanism = "HARDLINK_CREATE_IF_ABSENT_THEN_UNLINK"
    if source.exists() or not destination.is_file():
        raise GateError("TOP_PROMOTION_POSTCONDITION_FAIL", "promotion postcondition is not exact", {"source_exists": source.exists(), "destination_exists": destination.is_file()})
    after = file_fact(destination)
    if (after["bytes"], after["sha256"]) != (before["bytes"], before["sha256"]):
        raise GateError("TOP_PROMOTION_HASH_DRIFT", "artifact bytes changed during promotion", {"before": before, "after": after})
    return {
        "schema": "F3R2_V5_LOOP1E_NO_REPLACE_PROMOTION_V1",
        "source": before,
        "target": after,
        "mechanism": mechanism,
        "replacement_allowed": False,
        "verdict": "V5_LOOP1E_STAGING_PROMOTED_NO_REPLACE_PASS",
    }


def build_top(sw: Any, output_path: Path, frame_audit: Mapping[str, Any], local_arm: Mapping[str, Any], base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    output_path = output_path.resolve()
    if not is_loop1e_staging_path(output_path):
        raise GateError(
            "TOP_DIRECT_FINAL_SAVE_PROHIBITED",
            "build_top may SaveAs only to an exact same-directory Loop1E staging path",
            {"requested": norm(output_path), "final_target": norm(TARGET)},
        )
    if output_path.exists() or TARGET.exists():
        raise GateError(
            "TOP_BUILD_DESTINATION_COLLISION",
            "staging or final target already exists before SaveAs",
            {"staging_exists": output_path.exists(), "target_exists": TARGET.exists(), "staging": norm(output_path), "target": norm(TARGET)},
        )
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
        for role in ("SPACECRAFT_B601_MOUNT", "ARM", "B601_BASE_ADAPTER", "G07_SUPPORT", "G08_SUPPORT", "MID_SUPPORT", "LEFT_SOLAR_ARRAY", "RIGHT_SOLAR_ARRAY", "HDRM", "HARNESS"):
            ledgers.append(add_lock_mate(model, assembly, anchor, components[role], "MATE_TOP_LOCK_" + role, base, types, pythoncom))
        ledgers.append(add_lock_mate(model, assembly, link6, components["GRIPPER"], "MATE_TOP_LINK6_TO_GRIPPER", base, types, pythoncom))
        ledgers.append(add_lock_mate(model, assembly, link6, components["CAMERA"], "MATE_TOP_LINK6_TO_CAMERA", base, types, pythoncom))
        if len(ledgers) != 12 or any(int(row.get("type", -1)) != SW_MATE_LOCK for row in ledgers):
            raise GateError("TOP_LOCK_MATE_SET_FAIL", "top must own exactly 12 lock mates and no solar angle driver", {"mate_ledger": ledgers})
        configs, components = configure_top(model, assembly, components, base, types, pythoncom)
        references = exact_reference_gate(model, components, base)
        if not bool(model.ForceRebuild3(True)):
            raise GateError("TOP_REBUILD_FAIL", "top assembly full rebuild failed")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        raw_save = base.value(base.value(model, "Extension"), "SaveAs", str(output_path), SW_SAVE_AS_CURRENT_VERSION, SW_SAVE_AS_SILENT, None, 0, 0)
        saved, outs = base.unpack(raw_save)
        if not bool(saved) or (outs and int(outs[0]) != 0):
            raise GateError("TOP_STAGING_SAVE_AS_FAIL", "top staging SaveAs failed", {"saved": saved, "outs": outs, "staging": norm(output_path)})
        if not output_path.is_file() or TARGET.exists():
            raise GateError("TOP_STAGING_SAVE_POSTCONDITION_FAIL", "SaveAs did not create only the staging artifact", {"staging_exists": output_path.is_file(), "target_exists": TARGET.exists()})
        post_save_refs = exact_reference_gate(model, components, base)
        motion_contract, suppressed_whitelist = build_motion_contract(model, components, local_arm, frame_audit, base, types, pythoncom)
        result = {
            "artifact": file_fact(output_path),
            "template": file_fact(template),
            "components": {role: {"name2": str(base.value(item, "Name2")), "path": str(Path(str(base.value(item, "GetPathName"))).resolve()).replace("\\", "/"), "frame_contract": dict(resolved_contracts[role])} for role, item in components.items()},
            "link6_seed_transform": list(link6_seed_transform),
            "frame_contracts": dict(frame_audit),
            "motion_contract": motion_contract,
            "suppressed_nonphysical_whitelist": suppressed_whitelist,
            "mate_ledger": ledgers,
            "top_solar_angle_mate_count": 0,
            "configuration_ledger": configs,
            "references_pre_save": references,
            "references_post_save": post_save_refs,
            "final_target_written": False,
            "verdict": "V5_LOOP1E_TOP_LIVE_STAGING_SAVE_WITH_LOOP2_MOTION_CONTRACT_PASS",
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
    # Exactly the ratified conditional suppression exceptions: one legacy
    # gripper plus all six HDRM latch state proxies, each bound by exact
    # identity and an exact 11-top-configuration expected-state matrix.
    whitelist = [dict(entry) for entry in suppressed_whitelist]
    roles = sorted(str(entry.get("semantic_role")) for entry in whitelist)
    if len(whitelist) != 7 or roles != sorted(["LEGACY_B51_GRIPPER_DETAIL"] + ["HDRM_LATCH_STATE_PROXY"] * 6) or len(set(str(entry["component_name2"]) for entry in whitelist)) != 7:
        raise GateError("COLD_SUPPRESSED_WHITELIST_SET_FAIL", "suppression whitelist is not exactly the legacy gripper plus all six HDRM proxies", {"roles": roles})
    for entry in whitelist:
        expected_map = entry.get("expected_suppression_by_pose_config")
        if (
            not str(entry.get("component_name2", "")).strip()
            or not str(entry.get("component_path", "")).strip()
            or not str(entry.get("component_path_sha256", "")).strip()
            or entry.get("top_configurations") != list(TOP_CONFIGS)
            or not isinstance(expected_map, dict)
            or list(expected_map) != list(TOP_CONFIGS)
            or any(int(value) not in {SW_COMPONENT_SUPPRESSED, SW_COMPONENT_RESOLVED} for value in expected_map.values())
        ):
            raise GateError("COLD_SUPPRESSED_WHITELIST_SET_FAIL", "suppression whitelist entry is not exact-identity bound", {"entry": entry})
    legacy_entries = [entry for entry in whitelist if entry["semantic_role"] == "LEGACY_B51_GRIPPER_DETAIL"]
    proxy_entries = [entry for entry in whitelist if entry["semantic_role"] == "HDRM_LATCH_STATE_PROXY"]
    if len(legacy_entries) != 1 or any(int(value) != SW_COMPONENT_SUPPRESSED for value in legacy_entries[0]["expected_suppression_by_pose_config"].values()):
        raise GateError("COLD_LEGACY_SUPPRESSION_MATRIX_FAIL", "legacy gripper must be suppressed in all 11 top configurations")
    for configuration in TOP_CONFIGS:
        states = [int(entry["expected_suppression_by_pose_config"][configuration]) for entry in proxy_entries]
        if states.count(SW_COMPONENT_RESOLVED) != 1 or states.count(SW_COMPONENT_SUPPRESSED) != 5:
            raise GateError("COLD_HDRM_SUPPRESSION_MATRIX_FAIL", "each top configuration must resolve exactly one of six HDRM proxies", {"configuration": configuration, "states": states})
    extension = base.wrap(base.value(model, "Extension"), "IModelDocExtension", types, pythoncom)

    # Verify the exact suppression exception in every one of the 11 top
    # configuration, and reject every other suppressed/lightweight/unresolved
    # occurrence.  This mirrors the Loop2 runtime gate rather than relying on a
    # receipt-only assertion.
    suppression_rows: List[Dict[str, Any]] = []
    for configuration in TOP_CONFIGS:
        if not show_config_ok(model, configuration, base, types, pythoncom) or not bool(model.ForceRebuild3(True)):
            raise GateError("COLD_SUPPRESSION_CONFIG_FAIL", "cannot activate/rebuild one exact top configuration", {"configuration": configuration})
        all_components = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(False))]
        by_name = {component_name2(item, base): item for item in all_components}
        whitelisted = {str(entry["component_name2"]): entry for entry in whitelist}
        config_rows = []
        for entry in whitelist:
            occurrence = by_name.get(str(entry["component_name2"]))
            if occurrence is None:
                raise GateError("COLD_WHITELIST_OCCURRENCE_MISSING", "whitelisted occurrence Name2 does not resolve", {"configuration": configuration, "name2": entry["component_name2"]})
            occurrence_path = Path(str(base.value(occurrence, "GetPathName"))).resolve()
            occurrence_state = int(base.value(occurrence, "GetSuppression2"))
            expected_state = int(entry["expected_suppression_by_pose_config"][configuration])
            if occurrence_path != Path(str(entry["component_path"])).resolve() or sha256(occurrence_path) != str(entry["component_path_sha256"]) or occurrence_state != expected_state:
                raise GateError("COLD_WHITELIST_OCCURRENCE_FAIL", "whitelisted occurrence suppression/path/hash differs from its exact entry", {"configuration": configuration, "name2": component_name2(occurrence, base), "path": norm(occurrence_path), "suppression": occurrence_state, "expected_suppression": expected_state, "semantic_role": entry["semantic_role"]})
            config_rows.append({"component_name2": component_name2(occurrence, base), "component_path": norm(occurrence_path), "component_path_sha256": sha256(occurrence_path), "suppression": occurrence_state, "expected_suppression": expected_state, "semantic_role": entry["semantic_role"]})
        nonresolved = []
        for item in all_components:
            state = int(base.value(item, "GetSuppression2"))
            name = component_name2(item, base)
            if state == SW_COMPONENT_RESOLVED:
                continue
            entry = whitelisted.get(name)
            if entry is None or state != int(entry["expected_suppression_by_pose_config"][configuration]):
                nonresolved.append({"component_name2": name, "suppression": state, "path": str(base.value(item, "GetPathName"))})
        if nonresolved:
            raise GateError("COLD_NONRESOLVED_COMPONENT_FAIL", "suppressed/lightweight/unresolved component is not one exact whitelisted exception", {"configuration": configuration, "components": nonresolved})
        suppression_rows.append({"configuration": configuration, "whitelisted": config_rows, "other_nonresolved_count": 0})

    if not show_config_ok(model, POSE_CONFIGURATION_BINDINGS["Q_DEPLOYED_HOME"], base, types, pythoncom) or not bool(model.ForceRebuild3(True)):
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
        # Same SW2024 makepy interface split as in build_joint_driver_contract:
        # FeatureByName exists ONLY on IAssemblyDoc, while Parameter exists ONLY
        # on IModelDoc2. Verified against the generated typelib - so BOTH wrappers
        # are required here and neither call may be moved to the other interface.
        owner_features = base.wrap(raw_owner_model, "IAssemblyDoc", types, pythoncom)
        raw_feature = owner_features.FeatureByName(str(driver["native_limit_feature_name"]))
        raw_dimension = owner_model.Parameter(str(driver["native_angle_dimension_full_name"]))
        if raw_feature is None or raw_dimension is None:
            raise GateError("COLD_DRIVER_FEATURE_DIMENSION_MISSING", "native driver feature/dimension does not cold-resolve", {"joint": driver["joint"]})
        feature = base.wrap(raw_feature, "IFeature", types, pythoncom)
        dimension = base.wrap(raw_dimension, "IDimension", types, pythoncom)
        definition = angle_mate_data(feature, base, types, pythoncom)
        minimum, maximum = float(base.value(definition, "MinimumAngle")), float(base.value(definition, "MaximumAngle"))
        if (
            str(base.value(dimension, "FullName")) != driver["native_angle_dimension_full_name"]
            or feature_error_code(feature, base) != 0
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


def cold_solar_state_readback(role_map: Mapping[str, Any], state: str, solar: Mapping[str, Any], base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    """Re-acquire and prove both rigid P9 side trees in one top configuration."""
    side_identity = assert_top_side_identity(role_map, base)
    rows: Dict[str, Any] = {}
    for side, role in (("L", "LEFT_SOLAR_ARRAY"), ("R", "RIGHT_SOLAR_ARRAY")):
        root = role_map[role]
        raw_side_model = base.value(root, "GetModelDoc2")
        if raw_side_model is None:
            raise GateError("TOP_COLD_SOLAR_SIDE_MODEL_NULL", "rigid P9 side occurrence has no loaded IModelDoc2", {"side": side, "state": state})
        side_model = base.wrap(raw_side_model, "IModelDoc2", types, pythoncom)
        if bool(base.value(side_model, "GetSaveFlag")):
            raise GateError("TOP_COLD_SOLAR_SIDE_SAVE_FLAG_PRE", "P9 side was dirty before read-only dimension readback", {"side": side, "state": state})
        direct = child_components(root, base, types, pythoncom)
        by_path = {component_path(item, base): item for item in direct}
        oracle = solar["state_oracle"][side][state]
        expected_modules = oracle.get("module_occurrences", {})
        module_rows: Dict[str, Any] = {}
        for index in (1, 2, 3):
            key = f"{side}{index}"
            expected_row = expected_modules.get(key, {})
            wanted_path = os.path.normcase(str(Path(str(expected_row.get("path", ""))).resolve()))
            occurrence = by_path.get(wanted_path)
            if occurrence is None:
                raise GateError("TOP_COLD_SOLAR_MODULE_MISSING", "P9 module is not a direct child of its rigid side occurrence", {"side": side, "state": state, "module": key, "path": wanted_path})
            actual = component_transform16(occurrence, base)
            error = assert_transform_close(actual, expected_row.get("transform16", []), f"top/{side}/{state}/{key}")
            solving = int(base.value(occurrence, "Solving"))
            suppression = int(base.value(occurrence, "GetSuppression2"))
            if solving != SW_COMPONENT_RIGID or suppression != SW_COMPONENT_RESOLVED:
                raise GateError("TOP_COLD_SOLAR_MODULE_STATE_FAIL", "nested P9 module is not rigid/resolved", {"side": side, "state": state, "module": key, "solving": solving, "suppression": suppression})
            module_rows[key] = {"path": norm(Path(str(base.value(occurrence, "GetPathName")))), "transform16": actual, "transform_error": error, "solving": solving, "suppression": suppression}
        angle_rows = []
        side_mates = mate_features(side_model, base, types, pythoncom)
        expected_angles = oracle.get("cold_angle_dimension_readback", [])
        if not isinstance(expected_angles, list) or len(expected_angles) != 3:
            raise GateError("TOP_COLD_SOLAR_ANGLE_ORACLE_FAIL", "fresh oracle lacks exact three side angle dimensions", {"side": side, "state": state})
        for expected_angle in expected_angles:
            feature_name = str(expected_angle.get("feature_name", ""))
            feature = side_mates.get(feature_name)
            if feature is None:
                raise GateError("TOP_COLD_SOLAR_ANGLE_FEATURE_MISSING", "P9 side angle feature is absent", {"side": side, "state": state, "feature": feature_name})
            dimension = angle_mate_dimension(feature, base, types, pythoncom)
            actual_rad = float(dimension.GetSystemValue2(state))
            expected_rad = float(expected_angle.get("expected_rad"))
            full_name = str(base.value(dimension, "FullName"))
            if abs(actual_rad - expected_rad) > 2.0e-6 or full_name != str(expected_angle.get("dimension_full_name")):
                raise GateError("TOP_COLD_SOLAR_ANGLE_READBACK_FAIL", "configuration-specific side angle differs from P9 fresh oracle", {"side": side, "state": state, "feature": feature_name, "actual_rad": actual_rad, "expected_rad": expected_rad, "full_name": full_name, "expected_full_name": expected_angle.get("dimension_full_name")})
            angle_rows.append({"feature_name": feature_name, "dimension_full_name": full_name, "expected_rad": expected_rad, "readback_rad": actual_rad})
        if bool(base.value(side_model, "GetSaveFlag")):
            raise GateError("TOP_COLD_SOLAR_SIDE_SAVE_FLAG_POST", "GetSystemValue2 dirtied the P9 side during cold readback", {"side": side, "state": state})
        rows[side] = {"side_occurrence": side_identity[side], "modules": module_rows, "angle_dimensions": angle_rows, "oracle_verdict": oracle.get("verdict"), "save_flag_pre": False, "save_flag_post": False}
    return {"configuration": state, "sides": rows, "module_readback_count": 6, "angle_dimension_readback_count": 6, "verdict": "V5_LOOP1E_TOP_P9_2X3_NESTED_TRANSFORM_AND_ANGLE_READBACK_PASS"}


def cold_lock_mate_ledger(model: Any, base: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    all_mates = mate_features(model, base, types, pythoncom)
    unexpected = []
    for feature_name, feature in all_mates.items():
        raw_mate = base.value(feature, "GetSpecificFeature2")
        if raw_mate is None:
            unexpected.append({"name": feature_name, "reason": "NO_IMATE2"})
            continue
        mate = base.wrap(raw_mate, "IMate2", types, pythoncom)
        mate_type = int(base.value(mate, "Type"))
        if not feature_name.startswith("MATE_TOP_") or mate_type != SW_MATE_LOCK:
            unexpected.append({"name": feature_name, "type": mate_type})
    if unexpected:
        raise GateError("TOP_COLD_UNEXPECTED_MATE_FAIL", "top owns a non-lock or non-contract mate; top solar angle drivers are prohibited", {"unexpected": unexpected})
    for name, feature in all_mates.items():
        if not name.startswith("MATE_TOP_"):
            continue
        raw_mate = base.value(feature, "GetSpecificFeature2")
        if raw_mate is None:
            raise GateError("TOP_COLD_MATE_OBJECT_NULL", "top mate has no IMate2", {"name": name})
        mate = base.wrap(raw_mate, "IMate2", types, pythoncom)
        endpoint_paths: List[str] = []
        count = int(base.value(mate, "GetMateEntityCount"))
        for index in range(count):
            entity = base.wrap(mate.MateEntity(index), "IMateEntity2", types, pythoncom)
            raw_component = base.value(entity, "ReferenceComponent")
            if raw_component is None:
                raise GateError("TOP_COLD_MATE_ENDPOINT_NULL", "top lock mate endpoint has no component", {"name": name, "index": index})
            component = base.wrap(raw_component, "IComponent2", types, pythoncom)
            endpoint_paths.append(norm(Path(str(base.value(component, "GetPathName")))))
        rows.append({"name": name, "type": int(base.value(mate, "Type")), "endpoint_paths": sorted(endpoint_paths), "feature_error_code": feature_error_code(feature, base), "suppressed": bool(base.value(feature, "IsSuppressed"))})
    return sorted(rows, key=lambda row: row["name"])


def cold_verify(sw: Any, artifact_path: Path, expected: Dict[str, Any], base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    artifact_path = artifact_path.resolve()
    expected_hash = str(expected.get("artifact", {}).get("sha256", ""))
    if not artifact_path.is_file() or not expected_hash or sha256(artifact_path) != expected_hash:
        raise GateError("TOP_COLD_ARTIFACT_PRECHECK_FAIL", "cold-reopen artifact is missing or differs from the staged build", {"artifact": norm(artifact_path), "expected_sha256": expected_hash, "actual_sha256": sha256(artifact_path) if artifact_path.is_file() else None})
    model, opened = open_doc(sw, artifact_path, SW_DOC_ASSEMBLY, True, base, types, pythoncom)
    try:
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        solar = audit_solar_chain()
        configs = []
        solar_2x7 = []
        for name, spec in TOP_CONFIGS.items():
            if not show_config_ok(model, name, base, types, pythoncom) or not bool(model.ForceRebuild3(True)):
                raise GateError("TOP_COLD_CONFIG_FAIL", "cold configuration activation/rebuild failed", {"name": name})
            role_map = fresh_role_components(model, base, types, pythoncom)
            row = {"configuration": name, "arm": str(base.value(role_map["ARM"], "ReferencedConfiguration")), "left_wing": str(base.value(role_map["LEFT_SOLAR_ARRAY"], "ReferencedConfiguration")), "right_wing": str(base.value(role_map["RIGHT_SOLAR_ARRAY"], "ReferencedConfiguration")), "gripper": str(base.value(role_map["GRIPPER"], "ReferencedConfiguration")), "hdrm": str(base.value(role_map["HDRM"], "ReferencedConfiguration")), "q_vector_written": False, "six_r_q_pose_proven": False, "loop2_joint_driver_and_readback_required": bool(spec.get("pose") in MOTION_CONTRACT_POLICY["loop2_joint_driver_and_readback_required_for"])}
            wanted = {key: spec[key] for key in ("arm", "left_wing", "right_wing", "gripper", "hdrm")}
            if any(row[key] != wanted[key] for key in wanted):
                raise GateError("TOP_COLD_CONFIG_READBACK_FAIL", "cold referenced configuration drifted", {"name": name, "actual": row, "expected": wanted})
            assert_top_side_identity(role_map, base)
            if name in SOLAR_STATES:
                solar_2x7.append(cold_solar_state_readback(role_map, name, solar, base, types, pythoncom))
            configs.append(row)
        if len(solar_2x7) != 7 or any(row.get("module_readback_count") != 6 or row.get("angle_dimension_readback_count") != 6 for row in solar_2x7):
            raise GateError("TOP_COLD_SOLAR_2X7_FAIL", "cold P9 side readback is not exact 2x7", {"rows": solar_2x7})
        if not show_config_ok(model, "SOLAR_DEPLOYED_NOMINAL", base, types, pythoncom) or not bool(model.ForceRebuild3(True)):
            raise GateError("TOP_COLD_NOMINAL_RESTORE_FAIL", "cannot restore exact nominal configuration")
        role_map = fresh_role_components(model, base, types, pythoncom)
        refs = exact_reference_gate(model, role_map, base)
        ledger = cold_lock_mate_ledger(model, base, types, pythoncom)
        expected_ledger = sorted(({"name": row["name"], "type": int(row["type"]), "endpoint_paths": sorted(row["endpoint_paths"]), "feature_error_code": 0, "suppressed": False} for row in expected["mate_ledger"]), key=lambda row: row["name"])
        if ledger != expected_ledger or len(ledger) != 12 or any(row["type"] != SW_MATE_LOCK for row in ledger):
            raise GateError("TOP_COLD_MATE_LEDGER_FAIL", "cold top mate type/name/endpoints are not exact 12 lock mates", {"ledger": ledger, "expected": expected_ledger})
        motion_readback = cold_verify_motion_contract(model, assembly, role_map, expected["motion_contract"], expected["suppressed_nonphysical_whitelist"], base, types, pythoncom)
        if sha256(artifact_path) != expected_hash:
            raise GateError("TOP_COLD_HASH_DRIFT", "artifact hash changed during cold reopen", {"artifact": norm(artifact_path)})
        return {"open": opened, "references": refs, "configuration_ledger": configs, "solar_2x7_readback": solar_2x7, "top_solar_angle_mate_count": 0, "mate_ledger": ledger, "motion_contract_readback": motion_readback, "suppressed_nonphysical_whitelist": expected["suppressed_nonphysical_whitelist"], "artifact": file_fact(artifact_path), "verdict": "V5_LOOP1E_TOP_COLD_REOPEN_WITH_LOOP2_CONTRACT_PASS"}
    finally:
        close_doc(sw, model, base)


def validate_execution_g0(expected_pid: int, receipt_path: Path, expected_sha256: str) -> Dict[str, Any]:
    receipt_path = receipt_path.resolve()
    wanted_hash = str(expected_sha256).strip().upper()
    if expected_pid <= 0 or len(wanted_hash) != 64 or any(ch not in "0123456789ABCDEF" for ch in wanted_hash):
        raise GateError("EXECUTION_G0_ARGUMENT_FAIL", "execute requires a positive PID and exact uppercase/lowercase SHA-256", {"expected_pid": expected_pid, "g0_sha256": expected_sha256})
    fact = exact_fact(receipt_path, wanted_hash)
    payload = load_json(receipt_path)
    process = payload.get("session_b_process", {})
    post = payload.get("solidworks_post", {})
    temporary = payload.get("temporary_asset", {})
    run_dir = Path(str(payload.get("run_dir", ""))).resolve()
    expected_executable = Path(r"F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe").resolve()
    good = bool(
        payload.get("schema") == "F3R2_V5_G0_SMOKE_SESSION_B_V1"
        and payload.get("verdict") == "G0_SOLIDWORKS_NATIVE_EXECUTION_READY"
        and receipt_path.name == "G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json"
        and receipt_path.parent == run_dir
        and int(process.get("pid", -1)) == expected_pid
        and int(process.get("major", -1)) == 32
        and str(process.get("revision", "")).startswith("32.5.")
        and Path(str(process.get("executable", ""))).resolve() == expected_executable
        and process.get("doc_count_pre") == 0
        and process.get("active_doc_is_null_pre") is True
        and post.get("doc_count") == 0
        and post.get("active_doc_is_null") is True
        and temporary.get("deleted") is True
        and temporary.get("exists_after_delete") is False
    )
    if not good:
        raise GateError("EXECUTION_G0_RECEIPT_FAIL", "explicit Session-B ready receipt is not exact/live-session eligible", {"receipt": fact, "expected_pid": expected_pid, "session_b_process": process, "solidworks_post": post, "temporary_asset": temporary})
    return {
        "schema": "F3R2_V5_LOOP1E_EXECUTION_G0_BINDING_V1",
        "receipt": fact,
        "expected_pid": expected_pid,
        "session_b_process": dict(process),
        "solidworks_post": dict(post),
        "temporary_asset": dict(temporary),
        "verdict": "V5_LOOP1E_EXPLICIT_G0_SESSION_B_RECEIPT_PASS",
    }


def protected_snapshot(execution_g0: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = audit_protected()
    if not all(row["pass"] for row in rows):
        raise GateError("PROTECTED_HASH_FAIL", "protected spacecraft/B51 input drifted", rows)
    solar = audit_solar_chain()["payload"]
    immutable = [dict(row) for row in solar["immutable_tree"]]
    chain_paths = [
        SOLAR_PROMOTION, SOLAR_BUILD_RECEIPT, SOLAR_FRESH_RECEIPT,
        SOLAR_CAD_MANIFEST, SOLAR_HANDOFF, LOCAL_ARM_CHECKPOINT_V1,
        LOCAL_ARM_CHECKPOINT, LOCAL_ARM,
    ]
    chain_rows = [{"label": "loop1e_chain", **file_fact(path), "pass": True} for path in chain_paths]
    chain_rows.extend({"label": "solar_p9_immutable", **row, "pass": True} for row in immutable)
    g0_fact = dict(execution_g0.get("receipt", {}))
    if not g0_fact or exact_fact(Path(str(g0_fact.get("path", ""))), str(g0_fact.get("sha256", ""))) != g0_fact:
        raise GateError("EXECUTION_G0_PROTECTED_FACT_FAIL", "explicit G0 receipt fact changed before protected snapshot", g0_fact)
    chain_rows.append({"label": "execution_g0", **g0_fact, "pass": True})
    return rows + sorted(chain_rows, key=lambda row: (str(row.get("label", "")), str(row.get("path", ""))))


def close_owned(sw: Any, base: Any) -> None:
    # Invisible (silently opened) documents leak under an ActiveDoc-only loop:
    # the 20260811T2154 failure left all ten prebind part docs open because
    # ActiveDoc was None while GetDocuments listed them.  Enumerate titles
    # from GetDocuments every pass instead; still fail-closed on any remnant.
    guard = 0
    while guard < 200:
        titles: List[str] = []
        for raw in base.as_list(base.value(sw, "GetDocuments")):
            try:
                titles.append(str(base.value(raw, "GetTitle")))
            except Exception:
                continue
        if not titles:
            break
        for title in reversed(list(dict.fromkeys(titles))):
            try:
                sw.CloseDoc(title)
            except Exception:
                pass
        guard += 1
    if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
        raise GateError("DOCUMENT_CLEANUP_FAIL", "owned SOLIDWORKS documents remain open", {"document_count": int(base.value(sw, "GetDocumentCount"))})


def release_chain_evidence(audit: Mapping[str, Any], execution_g0: Mapping[str, Any]) -> Dict[str, Any]:
    solar = audit.get("solar_r2b_p9", {})
    payload = solar.get("payload", {}) if isinstance(solar, Mapping) else {}
    return {
        "solar_chain": payload,
        "local_arm_checkpoint_v1": file_fact(LOCAL_ARM_CHECKPOINT_V1),
        "local_arm_checkpoint_v2": file_fact(LOCAL_ARM_CHECKPOINT),
        "local_arm_contract_sha256": LOCAL_ARM_CONTRACT_SHA256,
        "execution_g0": dict(execution_g0),
        "accepted_urdf": file_fact(ACCEPTED_URDF),
    }


def top_precommit_payload(audit: Dict[str, Any], local_arm: Dict[str, Any], build: Dict[str, Any], staging_cold: Dict[str, Any], execution_g0: Mapping[str, Any]) -> Dict[str, Any]:
    if build.get("artifact") != staging_cold.get("artifact"):
        raise GateError("TOP_PRECOMMIT_ARTIFACT_MISMATCH", "live build and staging cold-reopen facts differ", {"build": build.get("artifact"), "cold": staging_cold.get("artifact")})
    return {
        "schema": "F3R2_V5_LOOP1E_TOP_PRECOMMIT_V2",
        "timestamp_utc": utc_now(),
        "script_sha256": sha256(Path(__file__)),
        "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
        **release_chain_evidence(audit, execution_g0),
        "intended_target": norm(TARGET),
        "replacement_allowed": False,
        "promotion_policy": "SAME_DIRECTORY_COLD_VERIFIED_PRECOMMIT_THEN_ATOMIC_NO_REPLACE",
        "upstream_receipt_hashes": {row["stage"]: row["actual_sha256"] for row in audit["upstream_receipts"]},
        "local_arm_checkpoint": file_fact(LOCAL_ARM_CHECKPOINT),
        "local_arm": local_arm["local_arm"],
        "staging_artifact": build["artifact"],
        "build": build,
        "staging_cold_reopen": staging_cold,
        "verdict": "V5_LOOP1E_TOP_STAGING_PRECOMMIT_COLD_REOPEN_PASS",
    }


def checkpoint_payload(audit: Dict[str, Any], local_arm: Dict[str, Any], build: Dict[str, Any], cold: Dict[str, Any], promotion: Dict[str, Any], execution_g0: Mapping[str, Any]) -> Dict[str, Any]:
    return {"schema": "F3R2_V5_LOOP1E_TOP_CHECKPOINT_V2", "timestamp_utc": utc_now(), "script_sha256": sha256(Path(__file__)), "accepted_urdf_sha256": ACCEPTED_URDF_SHA256, **release_chain_evidence(audit, execution_g0), "upstream_receipt_hashes": {row["stage"]: row["actual_sha256"] for row in audit["upstream_receipts"]}, "local_arm_checkpoint": file_fact(LOCAL_ARM_CHECKPOINT), "local_arm": local_arm["local_arm"], "precommit": file_fact(PRECOMMIT), "promotion": promotion, "target": file_fact(TARGET), "frame_contracts": audit["frame_contracts"], "motion_contract": build["motion_contract"], "suppressed_nonphysical_whitelist": build["suppressed_nonphysical_whitelist"], "build": build, "cold_reopen": cold, "verdict": "V5_LOOP1E_TOP_CHECKPOINT_COLD_REOPEN_WITH_LOOP2_CONTRACT_PASS"}


def manifest_text(paths: Sequence[Path]) -> str:
    rows = []
    unique = {os.path.normcase(str(path.resolve())): path.resolve() for path in paths}
    for path in unique.values():
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


def execute(lock_info: Mapping[str, Any], execution_g0: Mapping[str, Any]) -> int:
    result: Dict[str, Any] = {"schema": "F3R2_V5_LOOP1E_TOP_ASSEMBLY_RECEIPT_V2", "timestamp_start_utc": utc_now(), "target": norm(TARGET), "exclusive_lock": dict(lock_info), "execution_g0": dict(execution_g0), "transaction_policy": "STAGING_COLD_REOPEN_PRECOMMIT_ATOMIC_NO_REPLACE_PROMOTION_FINAL_COLD_REOPEN", "motion_contract_policy": dict(MOTION_CONTRACT_POLICY), "motion_contract": {"status": "PENDING_RUNTIME_NATIVE_DRIVER_AND_PERSISTENT_EVIDENCE"}, "q_vectors_written": False, "native_driver_seed_values_written": False, "undefined_service_q_created": False, "top_configuration_is_6r_q_pose_proof": False}
    sw = types = pythoncom = base = None
    try:
        audit = static_audit()
        result["static_audit"] = audit
        result["frame_contracts"] = audit["frame_contracts"]
        if not audit["execution_authorized"]:
            raise GateError("LOOP1E_STATIC_EXECUTION_HOLD", "static audit is PENDING/HOLD", audit)
        pre = protected_snapshot(execution_g0)
        result["protected_pre"] = pre
        base = load_base()
        result["memory_samples_gib"] = base.memory_gate()
        sw, types, pythoncom, session = base.attach_empty_session()
        result["solidworks"] = session
        expected_pid = int(execution_g0["expected_pid"])
        if int(session["pid"]) != expected_pid:
            raise GateError("SESSION_B_PID_BINDING_FAIL", "live process is not the explicitly receipted Session B", {"live": session["pid"], "expected": expected_pid})
        receipted_process = execution_g0["session_b_process"]
        if str(session["revision"]) != str(receipted_process["revision"]) or int(session["major"]) != int(receipted_process["major"]) or Path(str(session["executable"])).resolve() != Path(str(receipted_process["executable"])).resolve() or int(session["document_count"]) != 0 or session["active_doc_is_null"] is not True:
            raise GateError("SESSION_B_LIVE_FACT_BINDING_FAIL", "attached empty Session B differs from explicit G0 receipt", {"live": session, "receipted": receipted_process})
        staged = stage_local_arm_copy()
        local_arm = configure_local_arm(sw, staged, base, types, pythoncom)
        result["local_arm"] = local_arm
        state = checkpoint_state()
        result["transaction_entry_state"] = state["state"]
        stored = state.get("checkpoint") or state.get("precommit")
        if isinstance(stored, Mapping) and stored.get("execution_g0") != dict(execution_g0):
            raise GateError("TRANSACTION_G0_BINDING_DRIFT", "resume transaction was created under a different explicit Session-B receipt", {"stored": stored.get("execution_g0"), "current": dict(execution_g0)})
        if state["state"] == "PENDING_NEW":
            staging_path = new_staging_path()
            build = build_top(sw, staging_path, audit["frame_contracts"], local_arm, base, types, pythoncom)
            staging_cold = cold_verify(sw, staging_path, build, base, types, pythoncom)
            precommit = top_precommit_payload(audit, local_arm, build, staging_cold, execution_g0)
            write_json_once(PRECOMMIT, precommit)
            promotion = promote_no_replace(staging_path, TARGET)
            cold = cold_verify(sw, TARGET, build, base, types, pythoncom)
            checkpoint = checkpoint_payload(audit, local_arm, build, cold, promotion, execution_g0)
            write_json_once(CHECKPOINT, checkpoint)
        elif state["state"] == "RESUME_PRECOMMIT_STAGED":
            precommit = state["precommit"]
            build = dict(precommit["build"])
            staging_path = Path(str(precommit["staging_artifact"]["path"]))
            staging_cold = cold_verify(sw, staging_path, build, base, types, pythoncom)
            if staging_cold["artifact"] != precommit["staging_artifact"]:
                raise GateError("PRECOMMIT_RESUME_STAGING_DRIFT", "staging cold readback differs from the precommit", {"actual": staging_cold["artifact"], "expected": precommit["staging_artifact"]})
            promotion = promote_no_replace(staging_path, TARGET)
            cold = cold_verify(sw, TARGET, build, base, types, pythoncom)
            checkpoint = checkpoint_payload(audit, local_arm, build, cold, promotion, execution_g0)
            write_json_once(CHECKPOINT, checkpoint)
        elif state["state"] == "RESUME_PROMOTED_PRECOMMIT":
            precommit = state["precommit"]
            build = dict(precommit["build"])
            promotion = {
                "schema": "F3R2_V5_LOOP1E_NO_REPLACE_PROMOTION_V1",
                "source": precommit["staging_artifact"],
                "target": file_fact(TARGET),
                "mechanism": "RECOVERED_POST_PROMOTION_FROM_PRECOMMIT_HASH_IDENTITY",
                "replacement_allowed": False,
                "verdict": "V5_LOOP1E_STAGING_PROMOTED_NO_REPLACE_RECOVERY_PASS",
            }
            cold = cold_verify(sw, TARGET, build, base, types, pythoncom)
            checkpoint = checkpoint_payload(audit, local_arm, build, cold, promotion, execution_g0)
            write_json_once(CHECKPOINT, checkpoint)
        elif state["state"] == "RESUME_COLD_REOPEN":
            checkpoint = state["checkpoint"]
            build = checkpoint["build"]
            promotion = checkpoint["promotion"]
            cold = cold_verify(sw, TARGET, build, base, types, pythoncom)
            if cold["artifact"]["sha256"] != checkpoint["target"]["sha256"]:
                raise GateError("CHECKPOINT_RESUME_DRIFT", "resume cold readback differs from checkpoint")
        else:
            raise GateError("TARGET_CHECKPOINT_STATE_HOLD", "target/checkpoint state is not executable", state)
        result["precommit"] = file_fact(PRECOMMIT)
        result["promotion"] = promotion
        result["checkpoint"] = checkpoint
        result["cold_reopen"] = cold
        close_owned(sw, base)
        post = protected_snapshot(execution_g0)
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
        solar_payload = audit["solar_r2b_p9"]["payload"]
        paths = [TARGET, PRECOMMIT, CHECKPOINT, LOCAL_ARM, LOCAL_ARM_CHECKPOINT_V1, LOCAL_ARM_CHECKPOINT, SCRIPT_COPY, Path(execution_g0["receipt"]["path"]), *(Path(row["path"]) for row in audit["upstream_receipts"]), *(Path(row["path"]) for row in solar_payload["immutable_tree"]), *V5_SUBASSEMBLIES.values()]
        text = manifest_text(paths)
        if FINAL_MANIFEST.exists():
            if FINAL_MANIFEST.read_text(encoding="utf-8") != text:
                raise GateError("FINAL_MANIFEST_DRIFT", "existing Loop1E manifest differs")
        else:
            write_text_once(FINAL_MANIFEST, text)
        result.update({"timestamp_end_utc": utc_now(), "target_fact": file_fact(TARGET), "manifest": file_fact(FINAL_MANIFEST), **release_chain_evidence(audit, execution_g0), "direct_final_save_used": False, "same_physical_wing_occurrences_all_configurations": True, "same_physical_gripper_occurrence_all_configurations": True, "same_physical_hdrm_occurrence_all_configurations": True, "frame_contracts": audit["frame_contracts"], "motion_contract": build["motion_contract"], "suppressed_nonphysical_whitelist": build["suppressed_nonphysical_whitelist"], "motion_contract_cold_readback": cold["motion_contract_readback"], "solar_2x7_cold_readback": cold["solar_2x7_readback"], "top_solar_angle_mate_count": 0, "top_configuration_is_6r_q_pose_proof": False, "arm_referenced_configuration_is_6r_q_pose_proof": False, "q_vectors_written": False, "native_driver_seed_values_written": True, "undefined_service_q_created": False, "verdict": "V5_LOOP1E_NATIVE_TOP_ASSEMBLY_LOOP2_CONTRACT_COLD_REOPEN_PASS", "remaining_holds": ["LOOP2_AUTHORIZED_Q_COMMAND_AND_SIX_JOINT_ANGLE_READBACK_REQUIRED", "LOOP2_NATIVE_INTERFERENCE_CLEARANCE_AND_EXPECTED_CONTACT_AUDIT_PENDING", "Q_SERVICE_READY_RATIFICATION_HOLD", "RELEASE_SEQUENCE_NOT_AUTHORIZED_BY_Q_RELEASE_CLEAR_END_STATE", "PACK_AND_GO_FINAL_SELF_CONTAINMENT_PENDING", "HUMAN_SOLIDWORKS_VISUAL_REVIEW_PENDING"]})
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
    parser.add_argument("command", choices=("self-test", "audit", "execute"))
    parser.add_argument("--expected-pid", type=int)
    parser.add_argument("--g0-receipt", type=Path)
    parser.add_argument("--g0-sha256")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "self-test":
        if args.expected_pid is not None or args.g0_receipt is not None or args.g0_sha256 is not None:
            raise SystemExit("G0/PID arguments are valid only with execute")
        print(json.dumps(offline_self_test(), ensure_ascii=False, indent=2))
        return 0
    try:
        with exclusive_run_lock(args.command) as lock_info:
            if args.command == "audit":
                if args.expected_pid is not None or args.g0_receipt is not None or args.g0_sha256 is not None:
                    raise GateError("AUDIT_G0_ARGUMENT_FAIL", "filesystem-only audit does not accept live-session arguments")
                report = static_audit()
                report["exclusive_lock"] = dict(lock_info)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0 if report["verdict"] in {"V5_LOOP1E_STATIC_EXECUTION_READY", "V5_LOOP1E_STATIC_PENDING_UPSTREAM"} else 2
            if args.expected_pid is None or args.g0_receipt is None or args.g0_sha256 is None:
                raise GateError("EXECUTION_G0_ARGUMENTS_REQUIRED", "execute requires --expected-pid, --g0-receipt and --g0-sha256")
            execution_g0 = validate_execution_g0(args.expected_pid, args.g0_receipt, args.g0_sha256)
            return execute(lock_info, execution_g0)
    except GateError as exc:
        print(json.dumps({"schema": "F3R2_V5_LOOP1E_COMMAND_HOLD_V1", "timestamp_utc": utc_now(), "command": args.command, "verdict": exc.code, "reason": str(exc), "detail": exc.detail}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
