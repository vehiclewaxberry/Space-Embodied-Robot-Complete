#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F3R2 V5 Loop2 R2B native clearance and robotics verifier.

Static mode is the default.  Execution is impossible until the write-once
Loop1E R2B native top assembly and its receipt exist and expose the frozen
6R motion contract.  Runtime access is inherited from the hash-pinned Loop1
helper and is attach-only to the exact, initially-empty SOLIDWORKS 2024
Session B recorded by Loop1E.

The release evidence is an exact 7 solar-state by 3 frozen-authorized-q
matrix (21 static cells), plus a best-effort adaptive solar-only deployment
sweep driven only by the side-SLDASM native angle mates.  The top assembly
never owns a second solar driver.  Every required non-whitelisted body pair
must retain at least 5 mm and every positive-volume cross-component
interference is a hard failure.  The expected-contact whitelist is explicit,
state-scoped, and zero-volume only.

This file never promotes or invents a q vector.  In particular,
SERVICE_GRASP has no q and is never sampled.
"""

from __future__ import annotations

import argparse
import ast
import base64
import csv
import hashlib
import io
import json
import math
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
RUN_ID = "20260810T000300_V5NATIVE"

BASE_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_SHA256 = "E44BC52CFBDECCC107E361ACB0EDD993EFC46248EB663A994564B77BDA30F906"
IMPORT_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
IMPORT_RECEIPT_SHA256 = "9FC8D1DBBBDD7D1FE37F5FCCA4359838827282A0D7A961D8EEB511E75BE7160D"
AUTHORITY_SEED_RECEIPT = RUN_ROOT / "13_validation/V5_AUTHORITY_SEED_RECEIPT.json"
AUTHORITY_SEED_RECEIPT_SHA256 = "7251758420639907CAB4F4C134A278B0F860535BCC62A8E264E6862B7ECBED0F"
CONTROL_BASELINE = RUN_ROOT / "00_authority/V5_CONTROL_BASELINE.yaml"
CONTROL_BASELINE_SHA256 = "6F10BF844B975F416FAB0B7BB02CB82D984A9CC8A5BF81D442870C7EBE554B75"
POSE_AUTHORITY_REGISTER = RUN_ROOT / "04_configurations/V5_POSE_AUTHORITY_REGISTER.csv"
POSE_AUTHORITY_REGISTER_SHA256 = "1EB0D4CF3A7CC2B0F785B7C465C3BD89990A6F0647806B12C06BC931F0A3C326"
POSE_AUTHORIZATION_SEED = RUN_ROOT / "00_authority/POSE_AUTHORIZATION_REQUIRED.md"
POSE_AUTHORIZATION_SEED_SHA256 = "BA984DBF80B49D2A9B0354DDA703A85BDF9E9B26F8CB2211AF9402111F698762"

F3R2_ROOT = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
POSE_FREEZE = F3R2_ROOT / "04_configurations/F3R2_POSE_FREEZE.json"
POSE_FREEZE_SHA256 = "05E399AD909965367C95F9D42019FE4C23C507100CE0C46EFCA3C89B00CE44AC"
POSE_REGISTER = F3R2_ROOT / "04_configurations/F3R2_ARM_POSE_REGISTER.csv"
POSE_REGISTER_SHA256 = "999163799109D34F369AB634AFC3DA48DAC52D0A09836EE4787B12336D60CE2E"
POSE_TRANSITIONS = F3R2_ROOT / "04_configurations/F3R2_POSE_TRANSITION_MATRIX.csv"
POSE_TRANSITIONS_SHA256 = "F06FFEC13028F49E6307C48E6B3A02C9BF92AE719619A98761B424581EC614DD"
POSE_SEARCH = F3R2_ROOT / "04_configurations/F3R2_POSE_SEARCH.json"
POSE_SEARCH_SHA256 = "D0C25ADB6F561D2B0CDDFF79FD52D9B67125A0BFFD8624B13531B627EAAF2B28"
G5_JOURNAL = F3R2_ROOT / "05_clearance/F3R2_G5_JOURNAL.json"
G5_JOURNAL_SHA256 = "6D27F96C313738FB70F7C2854FC951C9B8917086515A0CC9EF5DD13A8C1EC35A"
G5_SCRIPT = F3R2_ROOT / "99_tools/r2k_g5_paths.py"
G5_SCRIPT_SHA256 = "F11BAC484D8981F93533E1F55F764234AAB8D204251DCDFA940B3CEC024DF881"
G5_RESULTS_JSON = F3R2_ROOT / "05_clearance/F3R2_CONTINUOUS_CLEARANCE_RESULTS.json"
G5_RESULTS_JSON_SHA256 = "87CF764FA069D49A08F7A59E5912B1A4E320DA6B5939C780F02233EE2AD13517"
G5_RESULTS_CSV = F3R2_ROOT / "05_clearance/F3R2_CONTINUOUS_CLEARANCE_RESULTS.csv"
G5_RESULTS_CSV_SHA256 = "FCCCB05667D50AD0A642EF71FB09CF01AA7CF6B9FBF6049A4AD054B05853A1F4"
ACCEPTED_URDF = ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
USER_LOOP_REQUIREMENT = Path(r"C:\Users\stude\.codex\attachments\62ab5338-5e01-431e-80e7-e67100ba5f32\pasted-text.txt")
USER_LOOP_REQUIREMENT_SHA256 = "5A4D90C7C1B43671E552BBB1B4776CC07AEAE210EFC2B3481F655BDEF09D37F2"

TOP_ASSEMBLY = RUN_ROOT / "03_top_assembly/SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM"
LOOP1E_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1E_TOP_ASSEMBLY_RECEIPT.json"

LOOP1E_SOURCE = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py"
LOOP1E_SOURCE_SHA256 = "1F8E83AC067A2C4218BCECADBD192A68D55D09A2DC2C4B896E1BD475141B0419"
SOLAR_PROMOTION = RUN_ROOT / "13_validation/V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT.json"
SOLAR_PROMOTION_SHA256 = "71952A7AC8761D59BB4596381C1DABD873AE2EFD0B7B8F502A0A95187349A334"
SOLAR_INTERFACE_REQUIREMENTS = RUN_ROOT / "00_authority/SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md"
SOLAR_INTERFACE_REQUIREMENTS_SHA256 = "62DDF827056D5199CCA68FD1714874E52FFB06398D4B856175435DD576504014"
DIGITAL_STATE_MACHINE_R2 = RUN_ROOT / "09_digital_thread/V5_MECHANICAL_STATE_MACHINE_R2.yaml"
DIGITAL_STATE_MACHINE_R2_SHA256 = "37ABA1A6CA520A4EBB348D87449BFA0E35EFD2EB5A1879F379C4A99BD4C81125"
DIGITAL_SOLAR_ANNEX_R2B = RUN_ROOT / "09_digital_thread/V5_SOLAR_ARRAY_THREAD_ANNEX_R2B.yaml"
DIGITAL_SOLAR_ANNEX_R2B_SHA256 = "966E2F521B26CF09AF53DCEA2C9E78F914B2E08BE3DF760FF29108F25885021D"
SOLAR_STATE_REGISTER_R2 = RUN_ROOT / "04_configurations/V5_SOLAR_STATE_REGISTER.csv"
SOLAR_STATE_REGISTER_R2_SHA256 = "41AEBC461286B893021747267E9ECDE065A188376685D1A7F1955646F3355D6B"
DIGITAL_THREAD_RECEIPT_R2B = RUN_ROOT / "13_validation/V5_DIGITAL_THREAD_SOLAR_R2B_PROMOTION_RECEIPT.json"
DIGITAL_THREAD_RECEIPT_R2B_SHA256 = "B2AF30DC9C5177EDDE41C5E46D147B32E85996C4317A811CA138AB4A41AA1256"
DIGITAL_THREAD_MANIFEST_R2B = RUN_ROOT / "14_release/V5_DIGITAL_THREAD_SOLAR_R2B_MANIFEST_SHA256.txt"
DIGITAL_THREAD_MANIFEST_R2B_SHA256 = "52227DC3B9F5E67F14AED1F8939386EF1C2DA3C7A942EEA1BA7591887C19ABC8"

P9_ROOT = RUN_ROOT / "13_validation/solar_r2_attempts/20260813T123100Z_P9E9"
P9_LEFT_SIDE = P9_ROOT / "cad/sides/L_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM"
P9_LEFT_SIDE_SHA256 = "4074EC7906FFE0BB029311006A1E771D343F31512D36A081BAFA44CFB410E29B"
P9_RIGHT_SIDE = P9_ROOT / "cad/sides/R_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM"
P9_RIGHT_SIDE_SHA256 = "C11335A47CB1A04B0D8B7DD1559DF0C8EEB0D482CA0DDC6C2E29448BD464CB48"

IK_CANDIDATE_SET = RUN_ROOT / "04_configurations/V5_LOOP2_IK_CANDIDATE_SET.json"  # legacy V1 output; never written by R2B V2
AUTHORIZATION_REQUIRED = RUN_ROOT / "12_human_review/V5_LOOP2_POSE_AUTHORIZATION_REQUIRED.md"  # legacy V1 output; never written by R2B V2
CHECKPOINT = RUN_ROOT / "13_validation/V5_LOOP2_R2B_CLEARANCE_CHECKPOINT.json"
CLEARANCE_RESULTS_JSON = RUN_ROOT / "05_clearance/V5_LOOP2_R2B_NATIVE_CLEARANCE_RESULTS.json"
CLEARANCE_RESULTS_CSV = RUN_ROOT / "05_clearance/V5_LOOP2_R2B_NATIVE_CLEARANCE_RESULTS.csv"
FINAL_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP2_R2B_NATIVE_CLEARANCE_RECEIPT.json"
FINAL_MANIFEST = RUN_ROOT / "14_release/V5_LOOP2_R2B_NATIVE_CLEARANCE_MANIFEST_SHA256.txt"
SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP2_MOTION_ROBOTICS_ATTACH_ONLY.py"

SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT_READONLY = 3
SW_BODY_SOLID = 0
SW_SET_VALUE_IN_SPECIFIC_CONFIGURATIONS = 3
SW_SET_VALUE_SUCCESS = 0

AUTHORIZED = "AUTHORIZED"
CANDIDATE = "CANDIDATE"
NOT_AUTHORIZED = "NOT_AUTHORIZED"
ALLOWED_AUTHORITY_CLASSES = {AUTHORIZED, CANDIDATE, NOT_AUTHORIZED}

POSES: Dict[str, Dict[str, Any]] = {
    "Q_DEPLOYED_HOME": {
        "class": AUTHORIZED,
        "scope": "CONTROL_AND_DYNAMICS_INITIALIZATION_INPUT_REQUIRES_V5_NATIVE_REVALIDATION",
        "q_deg": [-90.0, -120.0, -60.0, 0.0, -30.0, 0.0],
    },
    "Q_RELEASE_CLEAR": {
        "class": AUTHORIZED,
        "scope": "GEOMETRIC_END_STATE_ONLY_RELEASE_SEQUENCE_NOT_AUTHORIZED",
        "q_deg": [-90.0, -120.0, -120.0, -60.0, -30.0, 0.0],
    },
    "Q_SERVICE_READY": {
        "class": AUTHORIZED,
        "scope": "PRE_SERVICE_STAGING_INPUT_SERVICE_RATIFICATION_HOLD",
        "q_deg": [-90.0, -60.0, -120.0, -30.0, 0.0, 0.0],
    },
    "Q_STOW_ENGINEERING_CANDIDATE": {
        "class": CANDIDATE,
        "scope": "ENGINEERING_FIT_UP_SEED_NOT_RUNTIME_OR_CONTROL_AUTHORITY",
        "q_deg": [145.572, -168.0, -57.0, -41.143, -20.954, -3.0],
    },
    "Q_SERVICE_DOCKING": {"class": NOT_AUTHORIZED, "scope": "IK_CANDIDATE_SEARCH_ONLY", "q_deg": None},
    "Q_SERVICE_GRASP": {"class": NOT_AUTHORIZED, "scope": "IK_CANDIDATE_SEARCH_ONLY", "q_deg": None},
    "Q_SERVICE_TRANSPORT": {"class": NOT_AUTHORIZED, "scope": "IK_CANDIDATE_SEARCH_ONLY", "q_deg": None},
    "Q_SERVICE_ASSEMBLY": {"class": NOT_AUTHORIZED, "scope": "IK_CANDIDATE_SEARCH_ONLY", "q_deg": None},
    "Q_RETRIEVED_NOMINAL": {"class": NOT_AUTHORIZED, "scope": "IK_CANDIDATE_SEARCH_ONLY", "q_deg": None},
}

# User-facing path names and the frozen register use different spellings.  The
# alias map is explicit so no state can disappear through an accidental fuzzy
# match.  All receipts and candidate files use the canonical register names.
POSE_ALIASES = {
    "SERVICE_DOCKING": "Q_SERVICE_DOCKING",
    "SERVICE_GRASP": "Q_SERVICE_GRASP",
    "SERVICE_TRANSPORT": "Q_SERVICE_TRANSPORT",
    "SERVICE_ASSEMBLY": "Q_SERVICE_ASSEMBLY",
    "RETRIEVED": "Q_RETRIEVED_NOMINAL",
    "RETRIEVED_NOMINAL": "Q_RETRIEVED_NOMINAL",
    "Q_RETRIEVED": "Q_RETRIEVED_NOMINAL",
    "Q_STOW_ENGINEERING": "Q_STOW_ENGINEERING_CANDIDATE",
}

SERVICE_CHAIN = [
    "Q_DEPLOYED_HOME",
    "Q_SERVICE_READY",
    "Q_SERVICE_DOCKING",
    "Q_SERVICE_GRASP",
    "Q_SERVICE_TRANSPORT",
    "Q_SERVICE_ASSEMBLY",
    "Q_RETRIEVED_NOMINAL",
]
STOW_RELEASE_CHAIN = [
    "Q_STOW_ENGINEERING_CANDIDATE",
    "SOLAR_DEPLOY_ARM_LOCKED",
    "HDRM_RELEASE",
    "Q_RELEASE_CLEAR",
    "Q_DEPLOYED_HOME",
]

SEQUENCE_NODES = {
    "SOLAR_DEPLOY_ARM_LOCKED": {
        "class": CANDIDATE,
        "q_source": "Q_STOW_ENGINEERING_CANDIDATE",
        "scope": "CONFIGURATION_STATE_ARM_LOCKED_WING_DEPLOY_SEQUENCE_NOT_AUTHORIZED",
    },
    "HDRM_RELEASE": {
        "class": CANDIDATE,
        "q_source": "Q_STOW_ENGINEERING_CANDIDATE",
        "scope": "CONFIGURATION_STATE_MINUS_X_HDRM_SEQUENCE_NOT_AUTHORIZED",
    },
}

REQUIRED_COMPARISONS = {
    "ARM_BUS",
    "ARM_WING_LEFT",
    "ARM_WING_RIGHT",
    "ARM_WING_ROOT",
    "ARM_SUPPORT",
    "ARM_HDRM",
    "GRIPPER_BUS",
    "CAMERA_STRUCTURES",
    "HARNESS_MOVING_BODIES",
}
REQUIRED_COMPONENT_ROLES = {
    "ARM_MOVING",
    "BUS",
    "WING_LEFT",
    "WING_RIGHT",
    "WING_ROOT",
    "SUPPORT",
    "HDRM",
    "GRIPPER",
    "CAMERA",
    "HARNESS",
    "MOVING_BODIES",
    "STRUCTURES",
}

# R2B V2 release authority.  These are the exact top configurations created
# by Loop1E; only the first seven participate in the 7x3 static matrix.
SOLAR_STATES: Tuple[str, ...] = (
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
)
TOP_CONFIGURATIONS: Tuple[str, ...] = (
    *SOLAR_STATES,
    "SOLAR_DEPLOY_ARM_LOCKED",
    "HDRM_RELEASE",
    "SERVICE",
    "RELEASE_CLEAR_END_STATE",
)
AUTHORIZED_POSE_ORDER: Tuple[str, ...] = (
    "Q_DEPLOYED_HOME",
    "Q_RELEASE_CLEAR",
    "Q_SERVICE_READY",
)
SOLAR_STATE_ANGLES_DEG: Dict[str, Dict[str, Tuple[float, float, float]]] = {
    "SOLAR_STOWED": {"L": (0.0, 0.0, 0.0), "R": (0.0, 0.0, 0.0)},
    "SOLAR_DEPLOY_STAGE1": {"L": (90.0, 0.0, 0.0), "R": (90.0, 0.0, 0.0)},
    "SOLAR_DEPLOY_STAGE2": {"L": (90.0, 90.0, 0.0), "R": (90.0, 90.0, 0.0)},
    "SOLAR_DEPLOYED_NOMINAL": {"L": (90.0, 90.0, 90.0), "R": (90.0, 90.0, 90.0)},
    "SOLAR_LEFT_FAIL": {"L": (0.0, 0.0, 0.0), "R": (90.0, 90.0, 90.0)},
    "SOLAR_RIGHT_FAIL": {"L": (90.0, 90.0, 90.0), "R": (0.0, 0.0, 0.0)},
    "SOLAR_BOTH_FAIL": {"L": (0.0, 0.0, 0.0), "R": (0.0, 0.0, 0.0)},
}

# Every listed comparison is evaluated body-pair by body-pair.  A row cannot
# hide a sub-5-mm pair behind an aggregate minimum or an Infinity sentinel.
R2B_REQUIRED_COMPARISONS: Dict[str, Tuple[str, str]] = {
    "ARM_BUS": ("ARM_MOVING", "BUS"),
    "ARM_SOLAR_L1": ("ARM_MOVING", "SOLAR_L1"),
    "ARM_SOLAR_L2": ("ARM_MOVING", "SOLAR_L2"),
    "ARM_SOLAR_L3": ("ARM_MOVING", "SOLAR_L3"),
    "ARM_SOLAR_R1": ("ARM_MOVING", "SOLAR_R1"),
    "ARM_SOLAR_R2": ("ARM_MOVING", "SOLAR_R2"),
    "ARM_SOLAR_R3": ("ARM_MOVING", "SOLAR_R3"),
    "ARM_SOLAR_ROOT": ("ARM_MOVING", "SOLAR_ROOT"),
    "GRIPPER_SOLAR": ("GRIPPER", "SOLAR_PANELS"),
    "CAMERA_SOLAR": ("CAMERA", "SOLAR_PANELS"),
    "B601_HARNESS_SOLAR": ("B601_HARNESS", "SOLAR_PANELS"),
    "SOLAR_HARNESS_BUS": ("SOLAR_HARNESS", "BUS"),
    "SOLAR_HARNESS_MOVING": ("SOLAR_HARNESS", "MOVING_WITH_ARM_EE"),
    "SOLAR_BUS": ("SOLAR_PANELS", "BUS"),
    "SOLAR_G07": ("SOLAR_PANELS", "G07"),
    "SOLAR_G08": ("SOLAR_PANELS", "G08"),
    "SOLAR_MID": ("SOLAR_PANELS", "MID"),
    "SOLAR_HDRM": ("SOLAR_PANELS", "HDRM"),
    "SOLAR_LEFT_RIGHT": ("SOLAR_LEFT", "SOLAR_RIGHT"),
}
MINIMUM_NONWHITELIST_CLEARANCE_MM = 5.0

# No positive volume is ever acceptable.  Zero-distance contact may only be
# added later as an exact component-pair + exact-state row with a mandatory
# maximum_volume_mm3 of 0.0.  The currently accepted R2B clearance scope has
# no such exception, so the explicit whitelist is empty.
R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST: Tuple[Dict[str, Any], ...] = ()

SOLAR_DEPLOYMENT_SEQUENCE: Tuple[Tuple[str, str], ...] = (
    ("SOLAR_STOWED", "SOLAR_DEPLOY_STAGE1"),
    ("SOLAR_DEPLOY_STAGE1", "SOLAR_DEPLOY_STAGE2"),
    ("SOLAR_DEPLOY_STAGE2", "SOLAR_DEPLOYED_NOMINAL"),
)
SOLAR_DRIVER_JOINTS: Tuple[str, ...] = ("ROOT", "H12", "H23")
SOLAR_SWEEP_INITIAL_MAX_STEP_DEG = 7.5
SOLAR_SWEEP_NEAR_CLEARANCE_MAX_STEP_DEG = 0.5
SOLAR_SWEEP_MAX_DEPTH = 8

INITIAL_MAX_JOINT_STEP_DEG = 7.5
NEAR_CLEARANCE_MM = 10.0
CLEARANCE_CURVATURE_MM = 0.50
MAX_ADAPTIVE_DEPTH = 8
NUMERIC_TOL = 1.0e-9
EXPLICIT_HOLDS: Tuple[str, ...] = (
    "Q_SERVICE_READY_RATIFICATION_REQUIRED",
    "Q_RELEASE_CLEAR_IS_GEOMETRIC_END_STATE_NOT_RELEASE_SEQUENCE_AUTHORITY",
    "SERVICE_GRASP_Q_NOT_AUTHORIZED_AND_NOT_SAMPLED",
    "CAMERA_VISIBILITY_IS_NATIVE_ENVELOPE_CLEARANCE_PROXY_NOT_CALIBRATED_FOV",
    "HARNESS_IS_NATIVE_ENVELOPE_CLEARANCE_NOT_FLEXIBLE_CABLE_DYNAMICS",
    "LAUNCH_LOAD_THERMAL_VACUUM_RANDOM_VIBRATION_FORMAL_FASTENER_MOS_HOLD",
)


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def posix(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    return base.sha256(path)


def load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GateError("JSON_ROOT_FAIL", "JSON root is not an object", {"path": posix(path)})
    return data


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    if not rows:
        raise GateError("CSV_EMPTY", "authority CSV contains no rows", {"path": posix(path)})
    return rows


def file_fact(path: Path) -> Dict[str, Any]:
    return {
        "path": posix(path),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256(path) if path.is_file() else None,
    }


def fixed_fact(path: Path, expected_hash: str) -> Dict[str, Any]:
    fact = file_fact(path)
    fact["expected_sha256"] = expected_hash
    fact["pass"] = fact["exists"] and fact["sha256"] == expected_hash
    return fact


def fixed_files() -> List[Tuple[Path, str]]:
    return [
        (BASE_HELPER, BASE_HELPER_SHA256),
        (BASE_HELPER_COPY, BASE_HELPER_SHA256),
        (IMPORT_RECEIPT, IMPORT_RECEIPT_SHA256),
        (AUTHORITY_SEED_RECEIPT, AUTHORITY_SEED_RECEIPT_SHA256),
        (CONTROL_BASELINE, CONTROL_BASELINE_SHA256),
        (POSE_AUTHORITY_REGISTER, POSE_AUTHORITY_REGISTER_SHA256),
        (POSE_AUTHORIZATION_SEED, POSE_AUTHORIZATION_SEED_SHA256),
        (POSE_FREEZE, POSE_FREEZE_SHA256),
        (POSE_REGISTER, POSE_REGISTER_SHA256),
        (POSE_TRANSITIONS, POSE_TRANSITIONS_SHA256),
        (POSE_SEARCH, POSE_SEARCH_SHA256),
        (G5_JOURNAL, G5_JOURNAL_SHA256),
        (G5_SCRIPT, G5_SCRIPT_SHA256),
        (G5_RESULTS_JSON, G5_RESULTS_JSON_SHA256),
        (G5_RESULTS_CSV, G5_RESULTS_CSV_SHA256),
        (ACCEPTED_URDF, ACCEPTED_URDF_SHA256),
        (USER_LOOP_REQUIREMENT, USER_LOOP_REQUIREMENT_SHA256),
        (LOOP1E_SOURCE, LOOP1E_SOURCE_SHA256),
        (SOLAR_PROMOTION, SOLAR_PROMOTION_SHA256),
        (SOLAR_INTERFACE_REQUIREMENTS, SOLAR_INTERFACE_REQUIREMENTS_SHA256),
        (DIGITAL_STATE_MACHINE_R2, DIGITAL_STATE_MACHINE_R2_SHA256),
        (DIGITAL_SOLAR_ANNEX_R2B, DIGITAL_SOLAR_ANNEX_R2B_SHA256),
        (SOLAR_STATE_REGISTER_R2, SOLAR_STATE_REGISTER_R2_SHA256),
        (DIGITAL_THREAD_RECEIPT_R2B, DIGITAL_THREAD_RECEIPT_R2B_SHA256),
        (DIGITAL_THREAD_MANIFEST_R2B, DIGITAL_THREAD_MANIFEST_R2B_SHA256),
        (P9_LEFT_SIDE, P9_LEFT_SIDE_SHA256),
        (P9_RIGHT_SIDE, P9_RIGHT_SIDE_SHA256),
    ]


def audit_fixed() -> List[Dict[str, Any]]:
    rows = [fixed_fact(path, expected_hash) for path, expected_hash in fixed_files()]
    if not all(row["pass"] for row in rows):
        raise GateError("FIXED_INPUT_DRIFT", "one or more Loop2 fixed inputs drifted", {"rows": rows})
    return rows


def audit_r2b_authority_chain() -> Dict[str, Any]:
    promotion = load_json(SOLAR_PROMOTION)
    if promotion.get("schema") != "F3R2_V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT_V1" or promotion.get("verdict") != "V5_SOLAR_R2B_A_LOGICALLY_PROMOTED_IN_PLACE_FOR_TOP_INTEGRATION":
        raise GateError("R2B_PROMOTION_IDENTITY_FAIL", "logical promotion schema/verdict changed", {"schema": promotion.get("schema"), "verdict": promotion.get("verdict")})
    configuration = promotion.get("configuration_contract")
    promoted_sides = promotion.get("side_assemblies")
    rigid_sides = isinstance(promoted_sides, list) and len(promoted_sides) == 2 and all(isinstance(row, dict) and row.get("top_level_occurrence_solving") == "RIGID" for row in promoted_sides)
    if not isinstance(configuration, dict) or configuration.get("exact_configurations_authority_order") != list(SOLAR_STATES) or configuration.get("configuration_owner") != "SIDE_SLDASM_ONLY" or configuration.get("top_level_second_driver") != "PROHIBITED" or not rigid_sides:
        raise GateError("R2B_PROMOTION_CONFIGURATION_FAIL", "promotion lost the seven-state side-owner/no-second-driver contract", {"configuration_contract": configuration})

    rows = read_csv(SOLAR_STATE_REGISTER_R2)
    if [str(row.get("state", "")) for row in rows] != list(SOLAR_STATES):
        raise GateError("R2B_STATE_REGISTER_ORDER_FAIL", "R2 state register is not the exact seven-state authority order", {"actual": [row.get("state") for row in rows], "expected": list(SOLAR_STATES)})
    state_ledger: List[Dict[str, Any]] = []
    for row in rows:
        state = str(row["state"])
        left = tuple(float(value) for value in str(row.get("panel_angle_deg_L[3]", "")).split("/"))
        right = tuple(float(value) for value in str(row.get("panel_angle_deg_R[3]", "")).split("/"))
        if left != SOLAR_STATE_ANGLES_DEG[state]["L"] or right != SOLAR_STATE_ANGLES_DEG[state]["R"]:
            raise GateError("R2B_STATE_REGISTER_ANGLE_FAIL", "R2 state register logical angle vector changed", {"state": state, "left": left, "right": right, "expected": SOLAR_STATE_ANGLES_DEG[state]})
        if row.get("configuration_owner") != "SIDE_SLDASM_ONLY" or row.get("top_level_operation") != "SELECT_REFERENCED_CONFIGURATION_ONLY" or row.get("top_level_second_driver") != "PROHIBITED":
            raise GateError("R2B_STATE_REGISTER_OWNER_FAIL", "R2 state row lost side-only configuration ownership", {"state": state, "row": row})
        state_ledger.append({"state": state, "left_angles_deg": list(left), "right_angles_deg": list(right), "configuration_owner": row["configuration_owner"], "top_level_second_driver": row["top_level_second_driver"]})

    machine = yaml.safe_load(DIGITAL_STATE_MACHINE_R2.read_text(encoding="utf-8-sig"))
    if not isinstance(machine, dict) or machine.get("schema") != "F3R2_V5_MECHANICAL_STATE_MACHINE_R2" or machine.get("solar_configuration_contract", {}).get("top_level_second_driver") != "PROHIBITED" or [row.get("state") for row in machine.get("solar_states", [])] != list(SOLAR_STATES):
        raise GateError("R2B_DIGITAL_STATE_MACHINE_FAIL", "R2 digital state machine schema/state/driver contract changed")
    receipt = load_json(DIGITAL_THREAD_RECEIPT_R2B)
    if receipt.get("schema") != "F3R2_V5_DIGITAL_THREAD_SOLAR_R2B_PROMOTION_RECEIPT_V1" or receipt.get("verdict") != "V5_DIGITAL_THREAD_SOLAR_R2B_PROMOTION_BOUND_WRITE_ONCE_PASS":
        raise GateError("R2B_DIGITAL_THREAD_RECEIPT_FAIL", "R2 digital-thread promotion receipt verdict changed", {"schema": receipt.get("schema"), "verdict": receipt.get("verdict")})
    return {
        "logical_promotion": file_fact(SOLAR_PROMOTION),
        "interface_requirements": file_fact(SOLAR_INTERFACE_REQUIREMENTS),
        "digital_state_machine_r2": file_fact(DIGITAL_STATE_MACHINE_R2),
        "digital_annex_r2b": file_fact(DIGITAL_SOLAR_ANNEX_R2B),
        "state_register_r2": file_fact(SOLAR_STATE_REGISTER_R2),
        "digital_thread_receipt": file_fact(DIGITAL_THREAD_RECEIPT_R2B),
        "states": state_ledger,
        "configuration_owner": "SIDE_SLDASM_ONLY",
        "top_level_second_driver": "PROHIBITED",
        "pass": True,
    }


def pure_self_test() -> Dict[str, Any]:
    checks = {
        "exact_top_configuration_count_11": len(TOP_CONFIGURATIONS) == 11 and len(set(TOP_CONFIGURATIONS)) == 11,
        "exact_solar_state_count_7": len(SOLAR_STATES) == 7 and tuple(TOP_CONFIGURATIONS[:7]) == SOLAR_STATES,
        "exact_authorized_q_count_3": tuple(name for name in AUTHORIZED_POSE_ORDER if POSES[name]["class"] == AUTHORIZED and POSES[name]["q_deg"] is not None) == AUTHORIZED_POSE_ORDER,
        "exact_static_cell_count_21": len(SOLAR_STATES) * len(AUTHORIZED_POSE_ORDER) == 21,
        "service_grasp_has_no_q": POSES["Q_SERVICE_GRASP"]["q_deg"] is None and "Q_SERVICE_GRASP" not in AUTHORIZED_POSE_ORDER,
        "clearance_threshold_5mm": MINIMUM_NONWHITELIST_CLEARANCE_MM == 5.0,
        "zero_volume_contact_whitelist_explicit": isinstance(R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST, tuple) and all(float(row.get("maximum_volume_mm3", math.nan)) == 0.0 for row in R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST),
        "zero_volume_contact_whitelist_states_scoped": all(isinstance(row.get("allowed_top_configurations"), (list, tuple)) and row.get("allowed_top_configurations") and set(row["allowed_top_configurations"]).issubset(SOLAR_STATES) for row in R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST),
        "comparison_names_unique": len(R2B_REQUIRED_COMPARISONS) == len(set(R2B_REQUIRED_COMPARISONS)),
        "six_panel_arm_coverage": {f"ARM_SOLAR_{side}{index}" for side in ("L", "R") for index in (1, 2, 3)}.issubset(R2B_REQUIRED_COMPARISONS),
        "required_robot_solar_coverage": {"ARM_BUS", "ARM_SOLAR_ROOT", "GRIPPER_SOLAR", "CAMERA_SOLAR", "B601_HARNESS_SOLAR", "SOLAR_HARNESS_BUS", "SOLAR_HARNESS_MOVING", "SOLAR_BUS", "SOLAR_G07", "SOLAR_G08", "SOLAR_MID", "SOLAR_HDRM", "SOLAR_LEFT_RIGHT"}.issubset(R2B_REQUIRED_COMPARISONS),
    }
    try:
        json.dumps({"nonfinite": float("nan")}, allow_nan=False)
    except ValueError:
        checks["json_nonfinite_rejected"] = True
    else:
        checks["json_nonfinite_rejected"] = False
    try:
        checks["resume_gate_recomputed_from_exact_evidence"] = checkpoint_gate_pure_self_test()
    except Exception:
        checks["resume_gate_recomputed_from_exact_evidence"] = False
    if not all(checks.values()):
        raise GateError("R2B_PURE_SELF_TEST_FAIL", "one or more pure Loop2 R2B checks failed", {"checks": checks})
    return {"schema": "F3R2_V5_LOOP2_R2B_PURE_SELF_TEST_V1", "checks": checks, "verdict": "V5_LOOP2_R2B_PURE_SELF_TEST_PASS"}


def write_json_once(path: Path, payload: Dict[str, Any]) -> None:
    try:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise GateError("JSON_PRE_SERIALIZATION_FAIL", "JSON payload is not finite/serializable", {"path": posix(path), "exception": repr(exc)}) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
    except FileExistsError as exc:
        raise GateError("WRITE_ONCE_JSON_EXISTS", "write-once JSON already exists", {"path": posix(path)}) from exc


def write_text_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
    except FileExistsError as exc:
        raise GateError("WRITE_ONCE_TEXT_EXISTS", "write-once text already exists", {"path": posix(path)}) from exc


def write_csv_once(path: Path, fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames), extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    serialized = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="") as handle:
            handle.write(serialized)
            handle.flush()
    except FileExistsError as exc:
        raise GateError("WRITE_ONCE_CSV_EXISTS", "write-once CSV already exists", {"path": posix(path)}) from exc


def copy_once(source: Path, target: Path) -> None:
    if target.exists():
        if not target.is_file() or target.stat().st_size != source.stat().st_size or sha256(target) != sha256(source):
            raise GateError("SCRIPT_COPY_DRIFT", "existing write-once script copy differs from executable")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if target.stat().st_size != source.stat().st_size or sha256(target) != sha256(source):
        raise GateError("SCRIPT_COPY_FAIL", "script copy identity readback failed")


def canonical_pose(name: str) -> str:
    value = str(name).strip()
    return POSE_ALIASES.get(value, value)


def parse_q(value: Any, *, allow_empty: bool = False) -> Optional[List[float]]:
    if value is None or str(value).strip() == "":
        if allow_empty:
            return None
        raise GateError("Q_EMPTY", "joint vector is empty")
    try:
        raw = json.loads(str(value)) if isinstance(value, str) else value
        q = [float(item) for item in raw]
    except Exception as exc:
        raise GateError("Q_PARSE_FAIL", "joint vector is not a numeric JSON array", {"value": value}) from exc
    if len(q) != 6 or not all(math.isfinite(item) for item in q):
        raise GateError("Q_SHAPE_OR_FINITE_FAIL", "joint vector must contain six finite values", {"q": q})
    return q


def same_q(first: Sequence[float], second: Sequence[float], tolerance: float = 1.0e-9) -> bool:
    return len(first) == len(second) and all(abs(float(a) - float(b)) <= tolerance for a, b in zip(first, second))


def audit_authority_inputs() -> Dict[str, Any]:
    rows = read_csv(POSE_AUTHORITY_REGISTER)
    by_pose: Dict[str, Dict[str, str]] = {}
    duplicates: List[str] = []
    for row in rows:
        pose = canonical_pose(row.get("pose", ""))
        if not pose or pose in by_pose:
            duplicates.append(pose)
        by_pose[pose] = row
    if duplicates or set(by_pose) != set(POSES):
        raise GateError(
            "POSE_REGISTER_SET_FAIL",
            "V5 pose register names are not the exact frozen canonical set",
            {"duplicates": duplicates, "actual": sorted(by_pose), "expected": sorted(POSES)},
        )
    ledger: List[Dict[str, Any]] = []
    for pose, expected in POSES.items():
        row = by_pose[pose]
        actual_q = parse_q(row.get("q_deg"), allow_empty=True)
        expected_q = expected["q_deg"]
        if (actual_q is None) != (expected_q is None) or (actual_q is not None and not same_q(actual_q, expected_q)):
            raise GateError("POSE_Q_DRIFT", "pose vector differs from the frozen V5 register", {"pose": pose, "actual": actual_q, "expected": expected_q})
        source_status = str(row.get("source_status", ""))
        if expected["class"] == AUTHORIZED and source_status != "F3R2_FROZEN_RUNTIME_INPUT":
            raise GateError("AUTHORIZED_POSE_SOURCE_FAIL", "authorized pose is not a frozen runtime input", {"pose": pose, "source_status": source_status})
        if expected["class"] == CANDIDATE and source_status != "F3R2_NON_RUNTIME_CANDIDATE":
            raise GateError("CANDIDATE_POSE_SOURCE_FAIL", "stow pose lost its non-runtime candidate classification", {"pose": pose})
        if expected["class"] == NOT_AUTHORIZED and (source_status != "NOT_DEFINED" or actual_q is not None):
            raise GateError("UNAUTHORIZED_POSE_HAS_Q", "undefined service pose acquired a joint vector", {"pose": pose})
        if str(row.get("native_path_gate")) != "HOLD":
            raise GateError("NATIVE_PATH_GATE_DRIFT", "pre-Loop2 pose register must remain HOLD", {"pose": pose, "actual": row.get("native_path_gate")})
        ledger.append({
            "pose": pose,
            "authority_class": expected["class"],
            "q_deg": actual_q,
            "source_status": source_status,
            "native_path_gate": row.get("native_path_gate"),
            "human_authority": row.get("human_authority"),
        })

    freeze = load_json(POSE_FREEZE)
    expected_frozen = {"Q_AS_BUILT_REFERENCE", "Q_STOW_ENGINEERING_CANDIDATE", "Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY"}
    expected_runtime = {"Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY"}
    if freeze.get("schema") != "F3R2_POSE_FREEZE_V1" or set(freeze.get("poses_frozen", [])) != expected_frozen or set(freeze.get("runtime_poses", [])) != expected_runtime or freeze.get("transition_rows") != 20 or freeze.get("verdict") != "G3B_POSES_FROZEN":
        raise GateError("F3R2_POSE_FREEZE_CONTRACT_FAIL", "F3R2 pose freeze schema/sets/verdict changed", {"freeze": freeze})
    register_rows = read_csv(POSE_REGISTER)
    old_by_pose = {canonical_pose(row.get("pose", "")): row for row in register_rows}
    for pose in ("Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY", "Q_STOW_ENGINEERING_CANDIDATE"):
        if pose not in old_by_pose or pose not in expected_frozen:
            raise GateError("F3R2_AUTHORITY_CROSSCHECK_FAIL", "F3R2 freeze/register lacks a V5 seeded pose", {"pose": pose})
        old_q = parse_q(old_by_pose[pose].get("q_deg"))
        if not same_q(old_q, POSES[pose]["q_deg"]):
            raise GateError("F3R2_AUTHORITY_Q_DRIFT", "V5 seed no longer matches the frozen F3R2 vector", {"pose": pose, "old": old_q})

    transitions = read_csv(POSE_TRANSITIONS)
    if len(transitions) != 20:
        raise GateError("TRANSITION_REGISTER_ROW_COUNT_FAIL", "frozen transition matrix must retain 20 directed rows", {"rows": len(transitions)})
    if not any(canonical_pose(row.get("from", "")) == "Q_DEPLOYED_HOME" and canonical_pose(row.get("to", "")) == "Q_SERVICE_READY" for row in transitions):
        raise GateError("TRANSITION_REGISTER_MISSING", "frozen transition matrix lacks HOME to SERVICE_READY")
    try:
        control = yaml.safe_load(CONTROL_BASELINE.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise GateError("CONTROL_BASELINE_YAML_PARSE_FAIL", "control baseline is not valid YAML") from exc
    if not isinstance(control, dict) or control.get("schema") != "F3R2_V5_CONTROL_BASELINE_V1" or control.get("baseline_id") != RUN_ROOT.name:
        raise GateError("CONTROL_BASELINE_SCHEMA_FAIL", "control baseline schema/run id changed", {"schema": control.get("schema") if isinstance(control, dict) else None})
    pose_authority = control.get("pose_authority")
    if not isinstance(pose_authority, dict):
        raise GateError("CONTROL_POSE_AUTHORITY_PARSE_FAIL", "control baseline pose_authority is not a mapping")
    structured = {
        "authorized_runtime_inputs": {canonical_pose(value) for value in pose_authority.get("authorized_runtime_inputs", [])},
        "candidate_only": {canonical_pose(value) for value in pose_authority.get("candidate_only", [])},
        "not_authorized": {canonical_pose(value) for value in pose_authority.get("not_authorized", [])},
    }
    expected_structured = {
        "authorized_runtime_inputs": {name for name, spec in POSES.items() if spec["class"] == AUTHORIZED},
        "candidate_only": {name for name, spec in POSES.items() if spec["class"] == CANDIDATE},
        "not_authorized": {name for name, spec in POSES.items() if spec["class"] == NOT_AUTHORIZED},
    }
    if structured != expected_structured:
        raise GateError("CONTROL_POSE_AUTHORITY_SET_FAIL", "structured YAML authority sets differ from frozen classification", {"actual": {k: sorted(v) for k, v in structured.items()}, "expected": {k: sorted(v) for k, v in expected_structured.items()}})
    search = load_json(POSE_SEARCH)
    if search.get("schema") != "F3R2_POSE_SEARCH_V1" or search.get("grid_points") != 5625 or search.get("verdict") != "G3B_SEARCH_DONE" or set(search.get("results", {})) != expected_runtime:
        raise GateError("POSE_SEARCH_CONTRACT_FAIL", "historical deterministic pose search identity changed", {"schema": search.get("schema"), "grid_points": search.get("grid_points"), "results": sorted(search.get("results", {})), "verdict": search.get("verdict")})
    for pose in expected_runtime:
        chosen = search["results"][pose].get("chosen", {}).get("evaluation", {}).get("q_deg")
        if parse_q(chosen) != POSES[pose]["q_deg"]:
            raise GateError("POSE_SEARCH_CHOSEN_Q_DRIFT", "historical search chosen vector differs from frozen authority input", {"pose": pose, "chosen": chosen, "expected": POSES[pose]["q_deg"]})
    return {
        "pose_ledger": ledger,
        "canonical_aliases": dict(sorted(POSE_ALIASES.items())),
        "f3r2_pose_freeze_schema": freeze.get("schema"),
        "f3r2_pose_register_rows": len(register_rows),
        "transition_rows": len(transitions),
        "pose_search": {"schema": search["schema"], "grid_points": search["grid_points"], "verdict": search["verdict"], "chosen_poses": sorted(search["results"])},
        "control_pose_authority": {key: sorted(value) for key, value in structured.items()},
        "authority_rule": "ONLY_EXISTING_FROZEN_Q_CAN_BE_AUTHORIZED; CANDIDATES_NEVER_SELF_PROMOTE",
        "pass": True,
    }


def audit_urdf() -> Dict[str, Any]:
    try:
        root = ET.parse(ACCEPTED_URDF).getroot()
    except Exception as exc:
        raise GateError("URDF_PARSE_FAIL", "accepted URDF cannot be parsed") from exc
    expected_links = {"base_link", "link1", "link2", "link3", "link4", "link5", "link6", "gripper_link", "gripper_left", "gripper_right"}
    actual_links = [str(link.get("name", "")) for link in root.findall("link")]
    if len(actual_links) != 10 or set(actual_links) != expected_links or len(actual_links) != len(set(actual_links)):
        raise GateError("URDF_LINK_SET_FAIL", "accepted URDF must contain the exact ten-link topology", {"actual": actual_links, "expected": sorted(expected_links)})
    mass_rows: List[Dict[str, Any]] = []
    for link in root.findall("link"):
        mass = link.find("inertial/mass")
        inertia = link.find("inertial/inertia")
        origin = link.find("inertial/origin")
        if mass is None or inertia is None or origin is None:
            raise GateError("URDF_INERTIAL_FIELD_MISSING", "each accepted URDF link must retain mass/inertia/origin", {"link": link.get("name")})
        mass_value = require_finite_number(mass.get("value"), "URDF_MASS_FAIL", str(link.get("name")))
        inertia_values = {key: require_finite_number(inertia.get(key), "URDF_INERTIA_FAIL", f"{link.get('name')}.{key}") for key in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")}
        if mass_value <= 0.0 or min(inertia_values["ixx"], inertia_values["iyy"], inertia_values["izz"]) <= 0.0:
            raise GateError("URDF_INERTIAL_POSITIVITY_FAIL", "link mass/inertia diagonal must be positive", {"link": link.get("name"), "mass": mass_value, "inertia": inertia_values})
        mass_rows.append({"link": str(link.get("name")), "mass_kg": mass_value, "inertia_kg_m2": inertia_values})
    total_mass = sum(row["mass_kg"] for row in mass_rows)
    if abs(total_mass - 4.695555949342986) > 1.0e-12:
        raise GateError("URDF_TOTAL_MASS_DRIFT", "accepted URDF ten-link total mass changed", {"actual_kg": total_mass, "expected_kg": 4.695555949342986})
    all_joints = root.findall("joint")
    if len(all_joints) != 9 or len({str(joint.get("name", "")) for joint in all_joints}) != 9:
        raise GateError("URDF_NINE_JOINT_SET_FAIL", "accepted URDF must contain exactly nine uniquely named joints", {"actual": [joint.get("name") for joint in all_joints]})
    joints: Dict[str, Dict[str, Any]] = {}
    for joint in root.findall("joint"):
        name = str(joint.get("name", ""))
        if name not in {f"joint{index}" for index in range(1, 7)}:
            continue
        axis = joint.find("axis")
        parent = joint.find("parent")
        child = joint.find("child")
        limit = joint.find("limit")
        origin = joint.find("origin")
        if axis is None or parent is None or child is None or limit is None or origin is None:
            raise GateError("URDF_JOINT_FIELD_MISSING", "revolute joint lacks axis/link/limit", {"joint": name})
        try:
            xyz = [float(value) for value in str(axis.get("xyz", "")).split()]
            origin_xyz = [float(value) for value in str(origin.get("xyz", "")).split()]
            origin_rpy = [float(value) for value in str(origin.get("rpy", "")).split()]
            lower = float(limit.get("lower", "nan"))
            upper = float(limit.get("upper", "nan"))
        except Exception as exc:
            raise GateError("URDF_JOINT_PARSE_FAIL", "URDF joint numeric field is invalid", {"joint": name}) from exc
        if str(joint.get("type")) != "revolute" or len(xyz) != 3 or len(origin_xyz) != 3 or len(origin_rpy) != 3 or not all(math.isfinite(v) for v in xyz + origin_xyz + origin_rpy + [lower, upper]) or lower >= upper or joint.find("mimic") is not None:
            raise GateError("URDF_JOINT_CONTRACT_FAIL", "URDF revolute joint contract is invalid", {"joint": name})
        joints[name] = {
            "joint": name,
            "parent": str(parent.get("link")),
            "child": str(child.get("link")),
            "axis_xyz": xyz,
            "origin_xyz": origin_xyz,
            "origin_rpy": origin_rpy,
            "lower_rad": lower,
            "upper_rad": upper,
        }
    if set(joints) != {f"joint{index}" for index in range(1, 7)}:
        raise GateError("URDF_SIX_JOINT_SET_FAIL", "accepted URDF does not expose exactly joint1..joint6", {"actual": sorted(joints)})
    margin_rows: List[Dict[str, Any]] = []
    for pose, spec in POSES.items():
        q = spec["q_deg"]
        if q is None:
            continue
        margins: List[float] = []
        for index, angle_deg in enumerate(q, start=1):
            angle = math.radians(float(angle_deg))
            joint = joints[f"joint{index}"]
            if angle < joint["lower_rad"] - 1.0e-9 or angle > joint["upper_rad"] + 1.0e-9:
                raise GateError("POSE_OUTSIDE_URDF_LIMIT", "frozen/candidate q violates the accepted URDF", {"pose": pose, "joint": index, "angle_rad": angle, "limit": [joint["lower_rad"], joint["upper_rad"]]})
            margins.append(min(angle - joint["lower_rad"], joint["upper_rad"] - angle))
        margin_rows.append({"pose": pose, "authority_class": spec["class"], "minimum_joint_margin_deg": math.degrees(min(margins))})

    fixed = [joint for joint in all_joints if str(joint.get("name")) == "gripper_joint"]
    if len(fixed) != 1 or str(fixed[0].get("type")) != "fixed" or fixed[0].find("parent") is None or fixed[0].find("child") is None or fixed[0].find("parent").get("link") != "link6" or fixed[0].find("child").get("link") != "gripper_link" or fixed[0].find("mimic") is not None:
        raise GateError("URDF_GRIPPER_FIXED_JOINT_FAIL", "gripper_joint must be the unique fixed link6-to-gripper_link joint")
    gripper_rows: List[Dict[str, Any]] = []
    for name, child_name in (("gripper_joint1", "gripper_left"), ("gripper_joint2", "gripper_right")):
        candidates = [joint for joint in root.findall("joint") if str(joint.get("name")) == name]
        if len(candidates) != 1:
            raise GateError("URDF_GRIPPER_JOINT_SET_FAIL", "accepted URDF lacks an exact gripper prismatic joint", {"joint": name, "count": len(candidates)})
        joint = candidates[0]
        limit, axis = joint.find("limit"), joint.find("axis")
        parent, child = joint.find("parent"), joint.find("child")
        if str(joint.get("type")) != "prismatic" or limit is None or axis is None or parent is None or child is None or joint.find("mimic") is not None:
            raise GateError("URDF_GRIPPER_JOINT_TYPE_FAIL", "gripper joint is not prismatic", {"joint": name})
        lower, upper = float(limit.get("lower", "nan")), float(limit.get("upper", "nan"))
        axis_xyz = [float(value) for value in str(axis.get("xyz", "")).split()]
        if not math.isfinite(lower) or not math.isfinite(upper) or abs(lower) > 1.0e-9 or abs(upper - 0.0715) > 1.0e-9 or axis_xyz != [1.0, 0.0, 0.0] or parent.get("link") != "gripper_link" or child.get("link") != child_name:
            raise GateError("URDF_GRIPPER_LIMIT_FAIL", "gripper travel no longer equals 0..71.5 mm", {"joint": name, "lower": lower, "upper": upper})
        gripper_rows.append({"joint": name, "parent": parent.get("link"), "child": child.get("link"), "axis_xyz": axis_xyz, "lower_m": lower, "upper_m": upper, "mimic": None})
    return {"robot_name": root.get("name"), "link_count": 10, "joint_count": 9, "links": actual_links, "link_inertials": mass_rows, "total_mass_kg": total_mass, "revolute_joints": [joints[f"joint{i}"] for i in range(1, 7)], "gripper_fixed_joint": {"joint": "gripper_joint", "parent": "link6", "child": "gripper_link"}, "pose_limit_margins": margin_rows, "gripper_joints": gripper_rows, "pass": True}


def audit_g5_history() -> Dict[str, Any]:
    data = load_json(G5_JOURNAL)
    results = load_json(G5_RESULTS_JSON)
    result_csv = read_csv(G5_RESULTS_CSV)
    if results.get("schema") != "F3R2_CONTINUOUS_CLEARANCE_V1" or results.get("verdict") != "G5_SWEPT_OFFICIAL_INCOMPLETE" or results.get("official_path_fully_verified") is not False or len(results.get("official_path", [])) != 6 or len(results.get("engineering_path", [])) != 3:
        raise GateError("G5_RESULTS_CONTRACT_FAIL", "historical continuous-clearance result schema/scope/verdict changed", {"schema": results.get("schema"), "verdict": results.get("verdict"), "official_count": len(results.get("official_path", [])), "engineering_count": len(results.get("engineering_path", []))})
    if "mesh tier" not in str(results.get("authority_note", "")).lower() or "linear interpolation" not in str(results.get("method", "")).lower():
        raise GateError("G5_RESULTS_METHOD_FAIL", "historical G5 must remain explicitly mesh-tier linear joint interpolation", {"method": results.get("method"), "authority_note": results.get("authority_note")})
    if len(result_csv) != 30:
        raise GateError("G5_RESULTS_CSV_ROW_COUNT_FAIL", "historical continuous-clearance CSV must retain 30 sample rows", {"rows": len(result_csv)})
    expected = {
        "OFFICIAL: Q_DEPLOYED_HOME -> Q_SERVICE_READY": ("SWEPT", 9, True),
        "OFFICIAL: Q_SERVICE_READY -> SERVICE_DOCKING": ("NOT_DEFINED_NO_AUTHORISED_POSE", 0, None),
        "OFFICIAL: SERVICE_DOCKING -> SERVICE_GRASP": ("NOT_DEFINED_NO_AUTHORISED_POSE", 0, None),
        "OFFICIAL: SERVICE_GRASP -> SERVICE_TRANSPORT": ("NOT_DEFINED_NO_AUTHORISED_POSE", 0, None),
        "OFFICIAL: SERVICE_TRANSPORT -> SERVICE_ASSEMBLY": ("NOT_DEFINED_NO_AUTHORISED_POSE", 0, None),
        "OFFICIAL: SERVICE_ASSEMBLY -> RETRIEVED_NOMINAL": ("NOT_DEFINED_NO_AUTHORISED_POSE", 0, None),
        "ENGINEERING: Q_STOW_ENGINEERING_CANDIDATE -> SOLAR_DEPLOY_ARM_LOCKED": ("NO_ARM_MOTION_CONFIG_CHANGE_ONLY", 0, None),
        "ENGINEERING: SOLAR_DEPLOY_ARM_LOCKED -> Q_RELEASE_CLEAR": ("SWEPT", 12, False),
        "ENGINEERING: Q_RELEASE_CLEAR -> Q_DEPLOYED_HOME": ("SWEPT", 9, True),
    }
    if set(data) != set(expected):
        raise GateError("G5_SEGMENT_SET_DRIFT", "historical G5 segment set changed", {"actual": sorted(data), "expected": sorted(expected)})
    ledger: List[Dict[str, Any]] = []
    for name, (status, row_count, passed) in expected.items():
        segment = data[name]
        summary = segment.get("summary")
        rows = segment.get("rows")
        if not isinstance(summary, dict) or not isinstance(rows, list):
            raise GateError("G5_SEGMENT_PARSE_FAIL", "historical segment has unparsed summary/rows", {"segment": name})
        if summary.get("status") != status or len(rows) != row_count or summary.get("pass") is not passed:
            raise GateError("G5_SEGMENT_FACT_DRIFT", "historical G5 facts changed", {"segment": name, "summary": summary, "rows": len(rows)})
        ledger.append({"segment": name, "status": status, "rows": len(rows), "historical_pass": passed})
    result_summaries = {str(row.get("segment")): row for row in results["official_path"] + results["engineering_path"]}
    if set(result_summaries) != set(expected):
        raise GateError("G5_RESULTS_SEGMENT_SET_FAIL", "results JSON and journal segment sets disagree", {"results": sorted(result_summaries), "journal": sorted(expected)})
    for name, (status, _row_count, passed) in expected.items():
        row = result_summaries[name]
        if row.get("status") != status or row.get("pass") is not passed:
            raise GateError("G5_RESULTS_JOURNAL_DISAGREE", "results JSON and journal disagree on segment status/pass", {"segment": name, "results": row, "journal": data[name]["summary"]})
    return {
        "tier": "HISTORICAL_MESH_ONLY_NOT_NATIVE_V5_EVIDENCE",
        "official_segments_total": 6,
        "official_segments_swept": 1,
        "official_segments_undefined": 5,
        "historical_verdict": "G5_SWEPT_OFFICIAL_INCOMPLETE",
        "results_json": {"schema": results["schema"], "method": results["method"], "authority_note": results["authority_note"], "csv_sample_rows": len(result_csv)},
        "segments": ledger,
        "inherited_as_v5_native_pass": False,
        "pass": True,
    }


def require_finite_number(value: Any, code: str, field: str) -> float:
    try:
        number = float(value)
    except Exception as exc:
        raise GateError(code, "required numeric contract field is unparsed", {"field": field, "value": value}) from exc
    if not math.isfinite(number):
        raise GateError(code, "required numeric contract field is not finite", {"field": field, "value": value})
    return number


def audit_motion_contract(contract: Any, urdf: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(contract, dict) or contract.get("schema") != "F3R2_V5_LOOP2_MOTION_CONTRACT_V1":
        raise GateError("MOTION_CONTRACT_MISSING", "Loop1E receipt lacks the exact Loop2 motion contract schema")
    if str(contract.get("accepted_urdf_sha256", "")).upper() != ACCEPTED_URDF_SHA256:
        raise GateError("MOTION_CONTRACT_URDF_DRIFT", "motion contract is not bound to the accepted URDF")

    urdf_joints = {row["joint"]: row for row in urdf["revolute_joints"]}
    drivers = contract.get("joint_drivers")
    if not isinstance(drivers, list) or len(drivers) != 6:
        raise GateError("JOINT_DRIVER_SET_FAIL", "motion contract must expose exactly six 6R joint drivers")
    driver_by_joint: Dict[str, Dict[str, Any]] = {}
    for raw in drivers:
        if not isinstance(raw, dict):
            raise GateError("JOINT_DRIVER_PARSE_FAIL", "joint driver is not an object")
        joint = str(raw.get("joint", ""))
        if joint in driver_by_joint:
            raise GateError("JOINT_DRIVER_DUPLICATE", "joint driver names are not unique", {"joint": joint})
        dimension_owner = str(raw.get("dimension_owner_component_name2", ""))
        axis_owner = str(raw.get("axis_owner_component_name2", ""))
        dimension = str(raw.get("native_angle_dimension_full_name", ""))
        limit_feature = str(raw.get("native_limit_feature_name", ""))
        sign = require_finite_number(raw.get("sign"), "JOINT_DRIVER_NUMERIC_FAIL", f"{joint}.sign")
        offset = require_finite_number(raw.get("zero_offset_rad"), "JOINT_DRIVER_NUMERIC_FAIL", f"{joint}.zero_offset_rad")
        native_minimum = require_finite_number(raw.get("native_minimum_rad"), "JOINT_DRIVER_NUMERIC_FAIL", f"{joint}.native_minimum_rad")
        native_maximum = require_finite_number(raw.get("native_maximum_rad"), "JOINT_DRIVER_NUMERIC_FAIL", f"{joint}.native_maximum_rad")
        axis = raw.get("accepted_axis_xyz")
        origin_xyz, origin_rpy = raw.get("accepted_origin_xyz"), raw.get("accepted_origin_rpy")
        axis_ref = str(raw.get("axis_entity_persist_base64", ""))
        try:
            axis_ref_bytes = base64.b64decode(axis_ref, validate=True)
        except Exception as exc:
            raise GateError("JOINT_AXIS_REF_PARSE_FAIL", "joint axis witness is not strict base64", {"joint": joint}) from exc
        mate_refs = raw.get("angle_mate_plane_entity_persist_base64")
        mate_owners = raw.get("angle_mate_plane_owner_component_name2")
        if not isinstance(mate_refs, list) or len(mate_refs) != 2 or len(set(str(value) for value in mate_refs)) != 2:
            raise GateError("JOINT_MATE_ENTITY_REF_SET_FAIL", "joint motion contract must provide two unique angle-mate plane refs", {"joint": joint})
        if not isinstance(mate_owners, list) or len(mate_owners) != 2 or any(not isinstance(value, str) or not value for value in mate_owners):
            raise GateError("JOINT_MATE_ENTITY_OWNER_SET_FAIL", "joint motion contract must provide two exact plane-entity owners", {"joint": joint})
        decoded_mate_refs: List[bytes] = []
        for index, encoded in enumerate(mate_refs):
            try:
                decoded = base64.b64decode(str(encoded), validate=True)
            except Exception as exc:
                raise GateError("JOINT_MATE_ENTITY_REF_PARSE_FAIL", "native mate entity ref is not strict base64", {"joint": joint, "index": index}) from exc
            if not decoded:
                raise GateError("JOINT_MATE_ENTITY_REF_EMPTY", "native mate entity ref is empty", {"joint": joint, "index": index})
            decoded_mate_refs.append(decoded)
        if axis_ref_bytes in decoded_mate_refs:
            raise GateError("JOINT_AXIS_WITNESS_NOT_INDEPENDENT", "cylindrical axis witness must be independent of the two angle-mate plane refs", {"joint": joint})
        axis_direction = raw.get("axis_witness_cylinder_params_direction_xyz")
        if raw.get("axis_witness_geometry") != "CYLINDRICAL_FACE" or not isinstance(axis_direction, list) or len(axis_direction) != 3:
            raise GateError("JOINT_AXIS_GEOMETRY_CONTRACT_FAIL", "independent axis witness must be a cylindrical face with a frozen CylinderParams direction", {"joint": joint})
        axis_direction_f = [require_finite_number(value, "JOINT_AXIS_DIRECTION_NONFINITE", f"{joint}.axis_witness_direction") for value in axis_direction]
        axis_norm = math.sqrt(sum(value * value for value in axis_direction_f))
        if abs(axis_norm - 1.0) > 1.0e-6:
            raise GateError("JOINT_AXIS_DIRECTION_UNIT_FAIL", "independent cylindrical axis direction must be unit length", {"joint": joint, "direction": axis_direction_f, "norm": axis_norm})
        expected_feature_name = f"V5_LOOP2_{joint.upper()}_LIMIT_ANGLE"
        if raw.get("driver_generation_stage") != "LOOP1E_NATIVE_DRIVER_SYNTHESIS" or raw.get("cold_reopen_verified") is not True or raw.get("preexisting_b51_hinge_mate_used_as_driver") is not False or limit_feature != expected_feature_name or expected_feature_name not in dimension:
            raise GateError("JOINT_DRIVER_PROVENANCE_FAIL", "six 6R drivers must be newly synthesized/named/cold-verified by Loop1E and cannot reuse B51 hinge mates", {"joint": joint, "driver": raw, "expected_feature_name": expected_feature_name})
        if not dimension_owner or not axis_owner or not dimension or not limit_feature or not axis_ref_bytes or sign not in (-1.0, 1.0) or abs(offset) > NUMERIC_TOL or not isinstance(axis, list) or len(axis) != 3 or not isinstance(origin_xyz, list) or len(origin_xyz) != 3 or not isinstance(origin_rpy, list) or len(origin_rpy) != 3:
            raise GateError("JOINT_DRIVER_FIELD_FAIL", "joint driver lacks separate dimension/axis owners, dimension, sign, or URDF witness", {"joint": joint, "driver": raw})
        axis_f = [require_finite_number(value, "JOINT_DRIVER_AXIS_FAIL", f"{joint}.axis") for value in axis]
        origin_xyz_f = [require_finite_number(value, "JOINT_DRIVER_ORIGIN_FAIL", f"{joint}.origin_xyz") for value in origin_xyz]
        origin_rpy_f = [require_finite_number(value, "JOINT_DRIVER_ORIGIN_FAIL", f"{joint}.origin_rpy") for value in origin_rpy]
        accepted = urdf_joints.get(joint)
        if accepted is None or not same_q(axis_f, accepted["axis_xyz"]) or not same_q(origin_xyz_f, accepted["origin_xyz"]) or not same_q(origin_rpy_f, accepted["origin_rpy"]) or abs(native_minimum - accepted["lower_rad"]) > NUMERIC_TOL or abs(native_maximum - accepted["upper_rad"]) > NUMERIC_TOL or str(raw.get("accepted_parent_link")) != accepted["parent"] or str(raw.get("accepted_child_link")) != accepted["child"]:
            raise GateError("JOINT_DRIVER_URDF_BINDING_FAIL", "joint driver axis/links do not match accepted URDF", {"joint": joint, "driver": raw, "urdf": accepted})
        driver_by_joint[joint] = dict(raw)
    if set(driver_by_joint) != set(urdf_joints):
        raise GateError("JOINT_DRIVER_NAME_SET_FAIL", "joint driver set is not exactly joint1..joint6", {"actual": sorted(driver_by_joint)})

    roles = contract.get("component_roles")
    if not isinstance(roles, dict) or set(roles) != REQUIRED_COMPONENT_ROLES:
        raise GateError("COMPONENT_ROLE_SET_FAIL", "motion contract component roles are not exact", {"actual": sorted(roles) if isinstance(roles, dict) else None, "expected": sorted(REQUIRED_COMPONENT_ROLES)})
    role_ledger: Dict[str, List[str]] = {}
    for role, names in roles.items():
        if not isinstance(names, list) or not names or any(not isinstance(name, str) or not name.strip() for name in names) or len(names) != len(set(names)):
            raise GateError("COMPONENT_ROLE_MEMBER_FAIL", "component role must contain unique exact Name2 strings", {"role": role, "members": names})
        role_ledger[role] = list(names)

    comparisons = contract.get("comparison_contracts")
    if not isinstance(comparisons, list):
        raise GateError("COMPARISON_CONTRACT_PARSE_FAIL", "comparison_contracts is not a list")
    comparison_by_name: Dict[str, Dict[str, Any]] = {}
    for raw in comparisons:
        if not isinstance(raw, dict):
            raise GateError("COMPARISON_CONTRACT_ROW_FAIL", "comparison row is not an object")
        name = str(raw.get("name", ""))
        if name in comparison_by_name:
            raise GateError("COMPARISON_CONTRACT_DUPLICATE", "comparison names are not unique", {"name": name})
        first_role, second_role = str(raw.get("first_role", "")), str(raw.get("second_role", ""))
        minimum = require_finite_number(raw.get("minimum_allowed_mm"), "COMPARISON_LIMIT_FAIL", f"{name}.minimum_allowed_mm")
        if first_role not in roles or second_role not in roles or first_role == second_role or minimum < 0.0:
            raise GateError("COMPARISON_ROLE_OR_LIMIT_FAIL", "comparison roles/clearance limit are invalid", {"row": raw})
        comparison_by_name[name] = dict(raw)
    if set(comparison_by_name) != REQUIRED_COMPARISONS:
        raise GateError("COMPARISON_NAME_SET_FAIL", "all required mechanical/robotic comparison classes must be explicit", {"actual": sorted(comparison_by_name), "expected": sorted(REQUIRED_COMPARISONS)})

    face_pairs = contract.get("critical_face_pairs")
    if not isinstance(face_pairs, list) or not face_pairs:
        raise GateError("CRITICAL_FACE_PAIR_EMPTY", "critical_face_pairs is empty or missing")
    pair_names: set[str] = set()
    covered: set[str] = set()
    clean_pairs: List[Dict[str, Any]] = []
    for raw in face_pairs:
        if not isinstance(raw, dict):
            raise GateError("CRITICAL_FACE_PAIR_PARSE_FAIL", "critical face pair is not an object")
        name, comparison = str(raw.get("name", "")), str(raw.get("comparison", ""))
        if not name or name in pair_names or comparison not in comparison_by_name:
            raise GateError("CRITICAL_FACE_PAIR_ID_FAIL", "critical face pair name/comparison is invalid", {"row": raw})
        for field in ("first_persist_base64", "second_persist_base64"):
            try:
                decoded = base64.b64decode(str(raw.get(field, "")), validate=True)
            except Exception as exc:
                raise GateError("CRITICAL_FACE_REF_PARSE_FAIL", "persistent face reference is not strict base64", {"name": name, "field": field}) from exc
            if not decoded:
                raise GateError("CRITICAL_FACE_REF_EMPTY", "persistent face reference is empty", {"name": name, "field": field})
        minimum = require_finite_number(raw.get("minimum_allowed_mm"), "CRITICAL_FACE_LIMIT_FAIL", f"{name}.minimum_allowed_mm")
        first_name, second_name = str(raw.get("first_component_name2", "")), str(raw.get("second_component_name2", ""))
        comparison_row = comparison_by_name[comparison]
        if first_name not in roles[comparison_row["first_role"]] or second_name not in roles[comparison_row["second_role"]]:
            raise GateError("CRITICAL_FACE_COMPONENT_BINDING_FAIL", "critical face owners do not belong to the comparison endpoint roles", {"name": name, "first": first_name, "second": second_name, "comparison": comparison_row})
        if minimum < 0.0:
            raise GateError("CRITICAL_FACE_LIMIT_FAIL", "critical face minimum cannot be negative", {"name": name})
        pair_names.add(name)
        covered.add(comparison)
        clean_pairs.append(dict(raw))
    if covered != REQUIRED_COMPARISONS:
        raise GateError("CRITICAL_FACE_COVERAGE_FAIL", "every comparison class needs at least one critical face pair", {"covered": sorted(covered), "required": sorted(REQUIRED_COMPARISONS)})

    whitelist = contract.get("expected_contact_whitelist")
    if not isinstance(whitelist, list):
        raise GateError("EXPECTED_CONTACT_WHITELIST_MISSING", "expected_contact_whitelist must be an explicit list, even when empty")
    whitelist_names: set[str] = set()
    clean_whitelist: List[Dict[str, Any]] = []
    allowed_state_names = set(POSES) | set(SEQUENCE_NODES)
    for raw in whitelist:
        if not isinstance(raw, dict):
            raise GateError("EXPECTED_CONTACT_ROW_PARSE_FAIL", "expected contact row is not an object")
        name = str(raw.get("name", ""))
        members = raw.get("component_name2")
        states = raw.get("allowed_pose_or_sequence_nodes")
        maximum = require_finite_number(raw.get("maximum_volume_mm3"), "EXPECTED_CONTACT_VOLUME_FAIL", f"{name}.maximum_volume_mm3")
        if not name or name in whitelist_names or not isinstance(members, list) or len(members) < 2 or len(members) != len(set(members)) or not isinstance(states, list) or not states or any(canonical_pose(state) not in allowed_state_names for state in states) or maximum < 0.0 or not str(raw.get("physical_basis", "")).strip():
            raise GateError("EXPECTED_CONTACT_CONTRACT_FAIL", "expected contact whitelist row is incomplete/ambiguous", {"row": raw})
        missing_members = [member for member in members if member not in {name for values in roles.values() for name in values}]
        if missing_members:
            raise GateError("EXPECTED_CONTACT_MEMBER_FAIL", "expected contact component is not present in any motion role", {"name": name, "missing": missing_members})
        whitelist_names.add(name)
        clean_whitelist.append({**raw, "allowed_pose_or_sequence_nodes": [canonical_pose(state) for state in states], "maximum_volume_mm3": maximum})
    if clean_whitelist:
        raise GateError("UPSTREAM_EXPECTED_CONTACT_WHITELIST_NONEMPTY", "R2B V2 accepts no inherited contact exception; any future zero-volume exception must be exact and local to R2B", {"rows": clean_whitelist})

    pose_configs = contract.get("pose_configurations")
    required_pose_configs = {
        "Q_DEPLOYED_HOME",
        "Q_RELEASE_CLEAR",
        "Q_SERVICE_READY",
        "Q_STOW_ENGINEERING_CANDIDATE",
        "SOLAR_DEPLOY_ARM_LOCKED",
        "HDRM_RELEASE",
    }
    if not isinstance(pose_configs, dict) or set(pose_configs) != required_pose_configs or any(not isinstance(value, str) or not value for value in pose_configs.values()):
        raise GateError("POSE_CONFIGURATION_CONTRACT_FAIL", "motion contract lacks exact pose/configuration bindings", {"actual": pose_configs, "expected_keys": sorted(required_pose_configs)})

    ee = contract.get("end_effector_frame_contract")
    required_ee_strings = {
        "link6_component_name2",
        "gripper_component_name2",
        "camera_component_name2",
        "link6_witness_persist_base64",
        "gripper_witness_persist_base64",
        "camera_witness_persist_base64",
        "source_loop1c1_receipt_sha256",
        "source_loop1d_receipt_sha256",
        "gripper_part_geometry_frame",
        "gripper_assembly_origin_frame",
        "top_insertion_transform_authority",
    }
    if not isinstance(ee, dict) or any(not isinstance(ee.get(key), str) or not str(ee.get(key)).strip() for key in required_ee_strings):
        raise GateError("END_EFFECTOR_FRAME_CONTRACT_MISSING", "Loop1E motion contract lacks explicit link6/gripper/camera frame provenance", {"required": sorted(required_ee_strings), "actual": ee})
    for field in ("source_loop1c1_receipt_sha256", "source_loop1d_receipt_sha256"):
        source_hash = str(ee[field]).upper()
        if len(source_hash) != 64 or any(char not in "0123456789ABCDEF" for char in source_hash):
            raise GateError("END_EFFECTOR_SOURCE_HASH_FAIL", "end-effector frame contract is not bound to exact upstream receipt hashes", {"field": field})
    for field in ("link6_witness_persist_base64", "gripper_witness_persist_base64", "camera_witness_persist_base64"):
        try:
            raw = base64.b64decode(str(ee[field]), validate=True)
        except Exception as exc:
            raise GateError("END_EFFECTOR_WITNESS_PARSE_FAIL", "end-effector persistent witness is not strict base64", {"field": field}) from exc
        if not raw:
            raise GateError("END_EFFECTOR_WITNESS_EMPTY", "end-effector persistent witness is empty", {"field": field})
    for field in ("expected_link6_to_gripper_transform_16", "expected_link6_to_camera_transform_16"):
        values = ee.get(field)
        if not isinstance(values, list) or len(values) != 16:
            raise GateError("END_EFFECTOR_TRANSFORM_SHAPE_FAIL", "end-effector relative transform must contain 16 values", {"field": field})
        clean = [require_finite_number(value, "END_EFFECTOR_TRANSFORM_NONFINITE", field) for value in values]
        if abs(clean[12] - 1.0) > NUMERIC_TOL or any(abs(clean[index]) > NUMERIC_TOL for index in (13, 14, 15)):
            raise GateError("END_EFFECTOR_TRANSFORM_FORMAT_FAIL", "end-effector transform trailing scale/zeros are invalid", {"field": field, "values": clean})
        ee[field] = clean

    return {
        "schema": contract["schema"],
        "accepted_urdf_sha256": contract["accepted_urdf_sha256"],
        "joint_drivers": [driver_by_joint[f"joint{i}"] for i in range(1, 7)],
        "component_roles": role_ledger,
        "comparison_contracts": [comparison_by_name[name] for name in sorted(comparison_by_name)],
        "critical_face_pairs": clean_pairs,
        "expected_contact_whitelist": clean_whitelist,
        "pose_configurations": dict(pose_configs),
        "end_effector_frame_contract": dict(ee),
        "contract_scope": "CAD_MAPPING_ONLY_NOT_POSE_AUTHORITY",
        "pass": True,
    }


def audit_manifest_from_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    fact = receipt.get("manifest")
    if not isinstance(fact, dict):
        raise GateError("LOOP1E_MANIFEST_FACT_MISSING", "Loop1E receipt lacks manifest file identity")
    path = Path(str(fact.get("path", "")))
    if not path.is_file() or path.stat().st_size != int(fact.get("bytes", -1)) or sha256(path) != str(fact.get("sha256", "")).upper():
        raise GateError("LOOP1E_MANIFEST_FACT_DRIFT", "Loop1E manifest bytes differ from its receipt", {"receipt_fact": fact, "actual": file_fact(path)})
    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("  ", 2)
        if len(fields) != 3:
            raise GateError("LOOP1E_MANIFEST_ROW_PARSE_FAIL", "Loop1E manifest row is unparsed", {"line": line})
        expected_hash, expected_bytes_text, label = fields
        candidate = Path(label) if Path(label).is_absolute() else RUN_ROOT / label
        if label in seen or not candidate.is_file():
            raise GateError("LOOP1E_MANIFEST_MEMBER_FAIL", "Loop1E manifest member is duplicate/missing", {"label": label})
        try:
            expected_bytes = int(expected_bytes_text)
        except ValueError as exc:
            raise GateError("LOOP1E_MANIFEST_BYTES_PARSE_FAIL", "Loop1E manifest byte count is unparsed", {"line": line}) from exc
        actual = file_fact(candidate)
        if actual["sha256"] != expected_hash.upper() or actual["bytes"] != expected_bytes:
            raise GateError("LOOP1E_MANIFEST_MEMBER_DRIFT", "Loop1E manifested dependency changed", {"label": label, "expected_sha256": expected_hash, "expected_bytes": expected_bytes, "actual": actual})
        seen.add(label)
        rows.append(actual)
    if not rows or not any(Path(row["path"]).resolve() == TOP_ASSEMBLY.resolve() for row in rows):
        raise GateError("LOOP1E_MANIFEST_TARGET_MISSING", "Loop1E manifest is empty or omits the top assembly")
    return {"manifest": file_fact(path), "member_count": len(rows), "members": rows, "pass": True}


def audit_suppressed_nonphysical_whitelist(receipt: Dict[str, Any], motion: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_rows = receipt.get("suppressed_nonphysical_whitelist")
    if not isinstance(raw_rows, list) or len(raw_rows) != 7 or any(not isinstance(row, dict) for row in raw_rows):
        raise GateError("SUPPRESSED_WHITELIST_SET_FAIL", "Loop1E R2B must ledger exactly one legacy gripper plus all six HDRM state proxies", {"rows": raw_rows})
    semantic_counts = {
        "LEGACY_B51_GRIPPER_DETAIL": sum(row.get("semantic_role") == "LEGACY_B51_GRIPPER_DETAIL" for row in raw_rows),
        "HDRM_LATCH_STATE_PROXY": sum(row.get("semantic_role") == "HDRM_LATCH_STATE_PROXY" for row in raw_rows),
    }
    if semantic_counts != {"LEGACY_B51_GRIPPER_DETAIL": 1, "HDRM_LATCH_STATE_PROXY": 6}:
        raise GateError("SUPPRESSED_WHITELIST_SEMANTIC_CARDINALITY_FAIL", "suppressed ledger is not exact 1 legacy + all 6 HDRM proxies", {"counts": semantic_counts})
    clean: List[Dict[str, Any]] = []
    seen_names: set[str] = set()
    for raw in raw_rows:
        semantic = str(raw.get("semantic_role", ""))
        name = str(raw.get("component_name2", ""))
        path = Path(str(raw.get("component_path", "")))
        expected_hash = str(raw.get("component_path_sha256", "")).upper()
        configurations = raw.get("top_configurations")
        by_config = raw.get("expected_suppression_by_pose_config")
        expected_reason = (
            "LEGACY_GRIPPER_REPLACED_BY_V5_LOOP1C1_NONPHYSICAL_FOR_LOOP2"
            if semantic == "LEGACY_B51_GRIPPER_DETAIL"
            else "LOOP1D_STATE_PROXY_EXACTLY_ONE_OF_SIX_RESOLVED_PER_CONFIG_NONPHYSICAL_FOR_LOOP2"
        )
        resolved_count = sum(int(value) == 2 for value in by_config.values()) if isinstance(by_config, dict) else -1
        if (
            not name
            or name in seen_names
            or not path.is_file()
            or RUN_ROOT.resolve() not in path.resolve().parents
            or len(expected_hash) != 64
            or sha256(path) != expected_hash
            or not isinstance(configurations, list)
            or tuple(configurations) != TOP_CONFIGURATIONS
            or not isinstance(by_config, dict)
            or tuple(by_config) != TOP_CONFIGURATIONS
            or any(int(value) not in {0, 2} for value in by_config.values())
            or (semantic == "LEGACY_B51_GRIPPER_DETAIL" and any(int(value) != 0 for value in by_config.values()))
            or (semantic == "HDRM_LATCH_STATE_PROXY" and resolved_count <= 0)
            or raw.get("reason") != expected_reason
            or (semantic == "LEGACY_B51_GRIPPER_DETAIL" and int(raw.get("expected_suppression_state", -1)) != 0)
            or (semantic == "HDRM_LATCH_STATE_PROXY" and raw.get("expected_suppression_state") != "CONFIGURATION_DEPENDENT_0_OR_2")
            or raw.get("exclude_from_motion_comparison_sets") is not True
        ):
            raise GateError("SUPPRESSED_WHITELIST_CONTRACT_FAIL", "suppressed occurrence path/hash/exact-11 configuration contract is invalid", {"row": raw, "required_top_configurations": list(TOP_CONFIGURATIONS), "actual_hash": sha256(path) if path.is_file() else None})
        seen_names.add(name)
        clean.append({
            "semantic_role": semantic,
            "component_name2": name,
            "component_path": posix(path),
            "component_path_sha256": expected_hash,
            "top_configurations": list(TOP_CONFIGURATIONS),
            "expected_suppression_by_pose_config": {config: int(by_config[config]) for config in TOP_CONFIGURATIONS},
            "reason": expected_reason,
            "expected_suppression_state": 0 if semantic == "LEGACY_B51_GRIPPER_DETAIL" else "CONFIGURATION_DEPENDENT_0_OR_2",
            "exclude_from_motion_comparison_sets": True,
        })
    hdrm_rows = [row for row in clean if row["semantic_role"] == "HDRM_LATCH_STATE_PROXY"]
    for config in TOP_CONFIGURATIONS:
        if sum(int(row["expected_suppression_by_pose_config"][config]) == 2 for row in hdrm_rows) != 1:
            raise GateError("SUPPRESSED_WHITELIST_HDRM_ONE_RESOLVED_FAIL", "each of exact 11 configs must resolve exactly one of six HDRM proxies", {"configuration": config, "states": {row["component_name2"]: row["expected_suppression_by_pose_config"][config] for row in hdrm_rows}})
    return sorted(clean, key=lambda row: (row["semantic_role"], row["component_name2"]))


def audit_loop1e(required: bool, urdf: Dict[str, Any]) -> Dict[str, Any]:
    top_exists, receipt_exists = TOP_ASSEMBLY.is_file(), LOOP1E_RECEIPT.is_file()
    result: Dict[str, Any] = {
        "top_assembly": file_fact(TOP_ASSEMBLY),
        "receipt": file_fact(LOOP1E_RECEIPT),
        "ready": False,
        "motion_contract": None,
    }
    if not top_exists and not receipt_exists:
        result.update({"state": "PENDING", "reason": "LOOP1E_TOP_ASSEMBLY_AND_RECEIPT_MISSING"})
        if required:
            raise GateError("LOOP1E_INPUTS_PENDING", "Loop1E top assembly and receipt are missing", result)
        return result
    if top_exists != receipt_exists:
        result.update({"state": "HOLD", "reason": "LOOP1E_TOP_RECEIPT_UNPAIRED"})
        if required:
            raise GateError("LOOP1E_INPUTS_UNPAIRED", "Loop1E target/receipt write-once pair is incomplete", result)
        return result
    try:
        receipt = load_json(LOOP1E_RECEIPT)
        if receipt.get("schema") != "F3R2_V5_LOOP1E_TOP_ASSEMBLY_RECEIPT_V2" or receipt.get("verdict") != "V5_LOOP1E_NATIVE_TOP_ASSEMBLY_LOOP2_CONTRACT_COLD_REOPEN_PASS":
            raise GateError("LOOP1E_RECEIPT_IDENTITY_FAIL", "Loop1E receipt schema/verdict is not the accepted R2B cold-reopen result")
        target_fact = receipt.get("target_fact")
        if not isinstance(target_fact, dict):
            raise GateError("LOOP1E_TARGET_FACT_MISSING", "Loop1E receipt lacks target_fact")
        if Path(str(target_fact.get("path", ""))).resolve() != TOP_ASSEMBLY.resolve() or str(target_fact.get("sha256", "")).upper() != sha256(TOP_ASSEMBLY) or int(target_fact.get("bytes", -1)) != TOP_ASSEMBLY.stat().st_size:
            raise GateError("LOOP1E_TARGET_BINDING_FAIL", "Loop1E receipt does not bind the exact top assembly bytes", {"target_fact": target_fact, "actual": file_fact(TOP_ASSEMBLY)})
        if receipt.get("q_vectors_written") is not False or receipt.get("undefined_service_q_created") is not False:
            raise GateError("LOOP1E_AUTHORITY_CLAIM_FAIL", "Loop1E must not bake or invent service q vectors")
        if receipt.get("top_solar_angle_mate_count") != 0 or receipt.get("top_configuration_is_6r_q_pose_proof") is not False or receipt.get("arm_referenced_configuration_is_6r_q_pose_proof") is not False:
            raise GateError("LOOP1E_SECOND_DRIVER_OR_Q_PROOF_FAIL", "Loop1E must own zero top solar angle drivers and must not claim a top config proves q")
        solar_chain = receipt.get("solar_chain")
        if not isinstance(solar_chain, dict) or solar_chain.get("promotion", {}).get("sha256") != SOLAR_PROMOTION_SHA256 or solar_chain.get("configuration_names") != list(SOLAR_STATES):
            raise GateError("LOOP1E_SOLAR_PROMOTION_BINDING_FAIL", "Loop1E receipt is not bound to the exact P9 logical promotion/no-second-driver contract", {"solar_chain": solar_chain})
        session = receipt.get("solidworks")
        if not isinstance(session, dict) or int(session.get("pid", -1)) <= 0 or not str(session.get("revision", "")).startswith("32.5."):
            raise GateError("LOOP1E_SESSION_BINDING_MISSING", "Loop1E receipt lacks a valid Session B PID/revision binding")
        motion = audit_motion_contract(receipt.get("motion_contract"), urdf)
        cold = receipt.get("cold_reopen")
        ledger = cold.get("configuration_ledger") if isinstance(cold, dict) else None
        if not isinstance(ledger, list) or [row.get("configuration") for row in ledger if isinstance(row, dict)] != list(TOP_CONFIGURATIONS):
            raise GateError("LOOP1E_EXACT_TOP_CONFIGURATIONS_FAIL", "Loop1E cold receipt does not expose the exact 11 top configurations in authority order", {"actual": [row.get("configuration") for row in ledger] if isinstance(ledger, list) else ledger, "expected": list(TOP_CONFIGURATIONS)})
        for row in ledger:
            expected_side_state = row["configuration"] if row["configuration"] in SOLAR_STATES else "SOLAR_DEPLOYED_NOMINAL"
            if row.get("left_wing") != expected_side_state or row.get("right_wing") != expected_side_state:
                raise GateError("LOOP1E_SIDE_CONFIG_BINDING_FAIL", "top configuration does not select the exact same side-owned state on L/R", {"row": row, "expected_side_state": expected_side_state})
        manifest = audit_manifest_from_receipt(receipt)
        suppressed_whitelist = audit_suppressed_nonphysical_whitelist(receipt, motion)
        motion["suppressed_nonphysical_whitelist"] = suppressed_whitelist
        suppressed_names = {row["component_name2"] for row in suppressed_whitelist if row["semantic_role"] == "LEGACY_B51_GRIPPER_DETAIL"}
        role_names = {name for names in motion["component_roles"].values() for name in names}
        if suppressed_names & role_names:
            raise GateError("SUPPRESSED_COMPONENT_IN_COMPARISON_ROLE", "nonphysical legacy gripper may not appear in any motion/comparison component role", {"overlap": sorted(suppressed_names & role_names)})
        static_receipt = receipt.get("static_audit")
        upstream_rows = static_receipt.get("upstream_receipts") if isinstance(static_receipt, dict) else None
        if not isinstance(upstream_rows, list):
            raise GateError("LOOP1E_UPSTREAM_RECEIPT_LEDGER_MISSING", "Loop1E receipt lacks its static upstream receipt ledger")
        loop1c_rows = [row for row in upstream_rows if isinstance(row, dict) and row.get("stage") == "LOOP1C"]
        if len(loop1c_rows) != 1 or str(loop1c_rows[0].get("actual_sha256", "")).upper() != str(motion["end_effector_frame_contract"]["source_loop1c1_receipt_sha256"]).upper():
            raise GateError("GRIPPER_FRAME_RECEIPT_BINDING_FAIL", "end-effector contract is not bound to the exact Loop1C1 receipt consumed by Loop1E", {"loop1c_rows": loop1c_rows, "motion_source": motion["end_effector_frame_contract"]["source_loop1c1_receipt_sha256"]})
        loop1d_rows = [row for row in upstream_rows if isinstance(row, dict) and row.get("stage") == "LOOP1D"]
        if len(loop1d_rows) != 1 or str(loop1d_rows[0].get("actual_sha256", "")).upper() != str(motion["end_effector_frame_contract"]["source_loop1d_receipt_sha256"]).upper():
            raise GateError("CAMERA_FRAME_RECEIPT_BINDING_FAIL", "end-effector contract is not bound to the exact Loop1D receipt consumed by Loop1E", {"loop1d_rows": loop1d_rows, "motion_source": motion["end_effector_frame_contract"]["source_loop1d_receipt_sha256"]})
        frame_contracts = receipt.get("frame_contracts")
        contracts = frame_contracts.get("contracts") if isinstance(frame_contracts, dict) else None
        if not isinstance(frame_contracts, dict) or frame_contracts.get("pass") is not True or not isinstance(contracts, dict):
            raise GateError("LOOP1E_FRAME_CONTRACT_LEDGER_FAIL", "Loop1E receipt lacks a passing frame-contract ledger")
        for role in ("GRIPPER", "CAMERA"):
            if not isinstance(contracts.get(role), dict) or contracts[role].get("source_frame") != "LINK6_LOCAL" or contracts[role].get("placement") != "LIVE_LINK6_TOTAL_TRANSFORM":
                raise GateError("LOOP1E_LINK6_FRAME_CONTRACT_FAIL", "gripper/camera must carry an explicit LINK6_LOCAL live-transform contract", {"role": role, "contract": contracts.get(role)})
        result.update({"state": "READY", "ready": True, "motion_contract": motion, "loop1e_manifest": manifest, "loop1e_session": session, "receipt_schema": receipt.get("schema"), "receipt_verdict": receipt.get("verdict")})
        return result
    except GateError as exc:
        result.update({"state": "HOLD", "reason": exc.code, "detail": exc.detail})
        if required:
            raise
        return result
    except Exception as exc:
        result.update({"state": "HOLD", "reason": "LOOP1E_RECEIPT_PARSE_FAIL", "exception": repr(exc)})
        if required:
            raise GateError("LOOP1E_RECEIPT_PARSE_FAIL", "Loop1E receipt could not be parsed", result) from exc
        return result


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def native_evidence_final_gate(native: Dict[str, Any]) -> bool:
    """Recompute the release gate from evidence, never from a stored verdict bit."""
    if not isinstance(native, dict) or native.get("schema") != "F3R2_V5_LOOP2_R2B_NATIVE_CLEARANCE_RESULTS_V2":
        raise GateError("CHECKPOINT_NATIVE_SCHEMA_FAIL", "checkpoint native evidence schema is not the exact R2B V2 schema")
    if native.get("exact_top_configurations") != list(TOP_CONFIGURATIONS) or native.get("solar_states") != list(SOLAR_STATES) or native.get("authorized_q_order") != list(AUTHORIZED_POSE_ORDER):
        raise GateError("CHECKPOINT_NATIVE_AUTHORITY_SET_FAIL", "checkpoint native evidence changed the frozen configuration/state/q sets")
    if native.get("service_grasp_q") is not None or native.get("service_grasp_sample_count") != 0:
        raise GateError("CHECKPOINT_SERVICE_GRASP_AUTHORITY_FAIL", "SERVICE_GRASP must have no q and exactly zero samples")
    if native.get("expected_static_cell_count") != len(SOLAR_STATES) * len(AUTHORIZED_POSE_ORDER):
        raise GateError("CHECKPOINT_STATIC_EXPECTED_COUNT_FAIL", "checkpoint expected static-cell count is not exact 7 x 3")

    cells = native.get("static_cells")
    if not isinstance(cells, list):
        raise GateError("CHECKPOINT_STATIC_CELLS_SHAPE_FAIL", "checkpoint static cells are not a list")
    expected_pairs = [(state, pose) for state in SOLAR_STATES for pose in AUTHORIZED_POSE_ORDER]
    actual_pairs: List[Tuple[str, str]] = []
    for cell in cells:
        if not isinstance(cell, dict):
            raise GateError("CHECKPOINT_STATIC_CELL_SHAPE_FAIL", "checkpoint contains a non-object static cell")
        actual_pairs.append((str(cell.get("solar_state", "")), str(cell.get("pose", ""))))
    # Runtime stops at the first failed cell, so a valid HOLD is an exact prefix;
    # duplicates, reordered cells, or foreign state/q pairs are never accepted.
    if actual_pairs != expected_pairs[:len(actual_pairs)] or len(actual_pairs) > len(expected_pairs):
        raise GateError("CHECKPOINT_STATIC_CELL_IDENTITY_FAIL", "static cells are not a unique ordered prefix of the exact 7 x 3 matrix", {"actual": actual_pairs, "expected": expected_pairs})
    if native.get("completed_static_cell_count") != len(cells):
        raise GateError("CHECKPOINT_STATIC_COMPLETED_COUNT_FAIL", "completed static-cell count disagrees with the evidence list")

    static_complete_pass = (
        native.get("static_matrix_error") is None
        and len(cells) == len(expected_pairs)
        and all(
            cell.get("pass") is True
            and isinstance(cell.get("metrics"), dict)
            and cell["metrics"].get("pass") is True
            and isinstance(cell.get("arm_base_invariant"), dict)
            and cell["arm_base_invariant"].get("pass") is True
            and cell.get("top_level_second_solar_driver_count") == 0
            for cell in cells
        )
    )

    sweep = native.get("continuous_solar_only_sweep")
    if not isinstance(sweep, dict):
        raise GateError("CHECKPOINT_SWEEP_SHAPE_FAIL", "continuous solar-only sweep is not an object")
    segments = sweep.get("segments")
    expected_segments = [
        (pose, f"{start_state}->{end_state}")
        for pose in AUTHORIZED_POSE_ORDER
        for start_state, end_state in SOLAR_DEPLOYMENT_SEQUENCE
    ]
    sweep_complete_pass = False
    if isinstance(segments, list):
        actual_segments = [
            (str(segment.get("q_pose", "")), str(segment.get("segment", "")))
            if isinstance(segment, dict) else ("", "")
            for segment in segments
        ]
        sweep_complete_pass = (
            sweep.get("attempted") is True
            and sweep.get("available") is True
            and sweep.get("pass") is True
            and sweep.get("q_pose_count") == len(AUTHORIZED_POSE_ORDER)
            and sweep.get("segment_count") == len(expected_segments)
            and actual_segments == expected_segments
            and all(
                isinstance(segment, dict)
                and segment.get("pass") is True
                and segment.get("top_level_second_driver_count") == 0
                and isinstance(segment.get("samples"), list)
                and bool(segment["samples"])
                and all(
                    isinstance(sample, dict)
                    and sample.get("pass") is True
                    and isinstance(sample.get("metrics"), dict)
                    and sample["metrics"].get("pass") is True
                    and isinstance(sample.get("arm_base_invariant"), dict)
                    and sample["arm_base_invariant"].get("pass") is True
                    for sample in segment["samples"]
                )
                for segment in segments
            )
        )
    return static_complete_pass and sweep_complete_pass


def checkpoint_gate_pure_self_test() -> bool:
    cells = [
        {
            "solar_state": state,
            "pose": pose,
            "pass": True,
            "metrics": {"pass": True},
            "arm_base_invariant": {"pass": True},
            "top_level_second_solar_driver_count": 0,
        }
        for state in SOLAR_STATES
        for pose in AUTHORIZED_POSE_ORDER
    ]
    segments = [
        {
            "q_pose": pose,
            "segment": f"{start_state}->{end_state}",
            "pass": True,
            "top_level_second_driver_count": 0,
            "samples": [{"pass": True, "metrics": {"pass": True}, "arm_base_invariant": {"pass": True}}],
        }
        for pose in AUTHORIZED_POSE_ORDER
        for start_state, end_state in SOLAR_DEPLOYMENT_SEQUENCE
    ]
    native = {
        "schema": "F3R2_V5_LOOP2_R2B_NATIVE_CLEARANCE_RESULTS_V2",
        "exact_top_configurations": list(TOP_CONFIGURATIONS),
        "solar_states": list(SOLAR_STATES),
        "authorized_q_order": list(AUTHORIZED_POSE_ORDER),
        "service_grasp_q": None,
        "service_grasp_sample_count": 0,
        "expected_static_cell_count": len(cells),
        "completed_static_cell_count": len(cells),
        "static_cells": cells,
        "static_matrix_error": None,
        "continuous_solar_only_sweep": {
            "attempted": True,
            "available": True,
            "pass": True,
            "q_pose_count": len(AUTHORIZED_POSE_ORDER),
            "segment_count": len(segments),
            "segments": segments,
        },
    }
    if native_evidence_final_gate(native) is not True:
        return False
    duplicate = dict(native)
    duplicate_cells = list(cells)
    duplicate_cells[1] = dict(duplicate_cells[0])
    duplicate["static_cells"] = duplicate_cells
    try:
        duplicate_rejected = native_evidence_final_gate(duplicate) is False
    except GateError:
        duplicate_rejected = True
    unauthorized = dict(native)
    unauthorized["service_grasp_sample_count"] = 1
    try:
        service_grasp_rejected = native_evidence_final_gate(unauthorized) is False
    except GateError:
        service_grasp_rejected = True
    return duplicate_rejected and service_grasp_rejected


def validate_checkpoint_payload(payload: Dict[str, Any]) -> bool:
    try:
        if not isinstance(payload, dict) or payload.get("schema") != "F3R2_V5_LOOP2_R2B_CLEARANCE_CHECKPOINT_V2":
            return False
        if not CHECKPOINT.is_file() or canonical_json(load_json(CHECKPOINT)) != canonical_json(payload):
            return False
        exact_bindings = (
            ("script", file_fact(Path(__file__))),
            ("script_copy", file_fact(SCRIPT_COPY)),
            ("top", file_fact(TOP_ASSEMBLY)),
            ("loop1e_receipt", file_fact(LOOP1E_RECEIPT)),
        )
        if any(payload.get(name) != fact or fact.get("exists") is not True for name, fact in exact_bindings):
            return False
        expected_outputs = [file_fact(CLEARANCE_RESULTS_JSON), file_fact(CLEARANCE_RESULTS_CSV)]
        if payload.get("write_once_outputs") != expected_outputs or not all(fact.get("exists") is True for fact in expected_outputs):
            return False
        native = payload.get("native_evidence")
        if not isinstance(native, dict) or canonical_json(load_json(CLEARANCE_RESULTS_JSON)) != canonical_json(native):
            return False
        recomputed = native_evidence_final_gate(native)
        expected_native_verdict = "V5_LOOP2_R2B_NATIVE_CLEARANCE_PASS" if recomputed else "V5_LOOP2_R2B_NATIVE_CLEARANCE_HOLD"
        expected_checkpoint_verdict = "V5_LOOP2_R2B_CLEARANCE_CHECKPOINT_PASS" if recomputed else "V5_LOOP2_R2B_CLEARANCE_CHECKPOINT_HOLD"
        if native.get("final_gate_eligible") is not recomputed or native.get("verdict") != expected_native_verdict:
            return False
        if payload.get("final_gate_eligible") is not recomputed or payload.get("verdict") != expected_checkpoint_verdict:
            return False
        if payload.get("protected_pre_equals_post") is not True or native.get("protected_pre_equals_post") is not True:
            return False
        return True
    except Exception:
        return False


def output_state() -> Dict[str, Any]:
    primary = [CLEARANCE_RESULTS_JSON, CLEARANCE_RESULTS_CSV, CHECKPOINT, FINAL_RECEIPT, FINAL_MANIFEST]
    exists = {posix(path): path.exists() for path in primary}
    if SCRIPT_COPY.exists() and (not SCRIPT_COPY.is_file() or sha256(SCRIPT_COPY) != sha256(Path(__file__)) or SCRIPT_COPY.stat().st_size != Path(__file__).stat().st_size):
        return {"state": "HOLD_SCRIPT_COPY_DRIFT", "exists": exists, "script_copy": file_fact(SCRIPT_COPY)}
    if not any(exists.values()):
        return {"state": "PENDING_NEW", "exists": exists, "script_copy": file_fact(SCRIPT_COPY)}
    if all(path.is_file() for path in primary):
        try:
            receipt = load_json(FINAL_RECEIPT)
            if validate_complete_outputs(receipt):
                return {"state": "COMPLETE_PASS" if receipt.get("final_gate_eligible") is True else "COMPLETE_HOLD", "exists": exists, "receipt": file_fact(FINAL_RECEIPT)}
        except Exception:
            pass
        return {"state": "HOLD_COMPLETE_OUTPUT_DRIFT", "exists": exists}
    if CHECKPOINT.is_file() and CLEARANCE_RESULTS_JSON.is_file() and CLEARANCE_RESULTS_CSV.is_file() and not FINAL_RECEIPT.exists():
        try:
            checkpoint = load_json(CHECKPOINT)
            if validate_checkpoint_payload(checkpoint):
                return {"state": "RESUME_FINALIZE", "exists": exists, "checkpoint": checkpoint, "script_copy": file_fact(SCRIPT_COPY)}
        except Exception as exc:
            return {"state": "HOLD_CHECKPOINT_PARSE", "exists": exists, "exception": repr(exc)}
    return {"state": "HOLD_UNPAIRED_WRITE_ONCE_OUTPUTS", "exists": exists}


def source_policy_audit() -> Dict[str, Any]:
    text = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(Path(__file__)))
    forbidden = [
        "Dis" + "patch" + "(", "Dis" + "patchEx" + "(", "Ensure" + "Dis" + "patch" + "(", "CoCreate" + "Instance" + "(",
        ".Qu" + "it(", "Exit" + "App(", "sub" + "process", "os." + "system(", "task" + "kill", "Stop" + "-Process",
        "Vis" + "ible =", "User" + "Control =",
    ]
    hits = [token for token in forbidden if token in text]
    if hits:
        raise GateError("STATIC_FORBIDDEN_API", "script contains prohibited launch/process/UI automation tokens", {"hits": hits})
    attach_calls = 0
    direct_get_active_calls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "base" and node.func.attr == "attach_empty_session":
                attach_calls += 1
            if node.func.attr == "GetActiveObject":
                direct_get_active_calls += 1
    if attach_calls != 1 or direct_get_active_calls != 0:
        raise GateError("STATIC_ATTACH_PATH_FAIL", "runtime must have exactly one attach call through the pinned helper and no direct COM attach", {"helper_attach_calls": attach_calls, "direct_get_active_calls": direct_get_active_calls})
    module_com_imports: List[Dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [str(node.module)]
        else:
            continue
        if any(name.startswith("win32com") or name == "pythoncom" for name in modules):
            module_com_imports.append({"line": node.lineno, "modules": modules})
    if module_com_imports:
        raise GateError("STATIC_COM_IMPORT_SCOPE_FAIL", "COM imports may not execute on the module/static audit path", {"imports": module_com_imports})
    return {
        "get_active_object_only_via_pinned_helper": True,
        "pinned_helper_attach_call_count": attach_calls,
        "direct_get_active_object_call_count": direct_get_active_calls,
        "com_imports_in_loop2_static_path": False,
        "forbidden_hits": [],
        "solidworks_launch_or_quit_path": False,
        "pass": True,
    }


def r2b_source_contract_audit() -> Dict[str, Any]:
    text = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(Path(__file__)))
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    required_functions = {
        "expand_r2b_roles",
        "every_body_pair_clearance",
        "r2b_sample_metrics",
        "static_clearance_cell",
        "continuous_solar_only_sweep",
        "solar_only_adaptive_segment",
        "restore_arm_driver_originals",
        "restore_solar_driver_originals",
        "clearance_csv_rows",
    }
    missing = sorted(required_functions - function_names)
    required_tokens = {
        "exact_21_cells": "len(SOLAR_STATES) * len(AUTHORIZED_POSE_ORDER) == 21",
        "nonwhitelist_5mm": "MINIMUM_NONWHITELIST_CLEARANCE_MM = 5.0",
        "service_grasp_zero_sample": '"service_grasp_sample_count": 0',
        "side_only_driver": '"SIDE_SLDASM_ONLY"',
        "top_second_driver_zero": '"top_level_second_driver_count": 0',
        "positive_interference_gate": "NATIVE_POSITIVE_CROSS_INTERFERENCE",
        "write_once_json": 'path.open("x", encoding="utf-8"',
        "json_finite": "allow_nan=False",
        "pre_post": '"protected_pre_equals_post": True',
    }
    token_fail = sorted(name for name, token in required_tokens.items() if token not in text)
    if missing or token_fail:
        raise GateError("R2B_SOURCE_CONTRACT_AUDIT_FAIL", "R2B V2 required implementation functions/tokens are missing", {"missing_functions": missing, "missing_tokens": token_fail})
    return {"required_functions": sorted(required_functions), "required_tokens": sorted(required_tokens), "pass": True}


def audit_user_requirement_traceability() -> Dict[str, Any]:
    text = USER_LOOP_REQUIREMENT.read_text(encoding="utf-8-sig")
    required_tokens = [
        "AUTHORIZED", "CANDIDATE", "NOT_AUTHORIZED", "IK_CANDIDATE_SET",
        "POSE_AUTHORIZATION_REQUIRED.md", "minimum distance", "critical face distance",
        "adaptive continuous sampling", "arm ↔ bus", "camera ↔ structures",
        "harness ↔ moving bodies", "Infinity from missing comparison geometry",
    ]
    missing = [token for token in required_tokens if token not in text]
    if missing:
        raise GateError("USER_REQUIREMENT_TOKEN_MISSING", "fixed user Loop2 requirement no longer contains the audited fail-closed clauses", {"missing": missing})
    return {
        "source": file_fact(USER_LOOP_REQUIREMENT),
        "tokens_verified": required_tokens,
        "implementation": {
            "authority_classes": sorted(ALLOWED_AUTHORITY_CLASSES),
            "undefined_pose_output": [posix(IK_CANDIDATE_SET), posix(AUTHORIZATION_REQUIRED)],
            "adaptive_sampling_function": "adaptive_segment",
            "native_interference_function": "native_interference",
            "minimum_distance_function": "minimum_role_distance",
            "critical_face_function": "critical_face_distances",
            "missing_empty_nonfinite_unparsed_policy": "FAIL_CLOSED",
            "comparison_coverage_upstream_loop1e": sorted(REQUIRED_COMPARISONS),
            "comparison_coverage_r2b_v2": sorted(R2B_REQUIRED_COMPARISONS),
            "static_matrix": "7_SOLAR_STATES_X_3_FROZEN_AUTHORIZED_Q_EQUALS_21",
            "minimum_nonwhitelist_clearance_mm": MINIMUM_NONWHITELIST_CLEARANCE_MM,
            "positive_interference_policy": "ANY_POSITIVE_VOLUME_FAIL",
            "solar_driver_policy": "SIDE_SLDASM_ONLY_TOP_SECOND_DRIVER_PROHIBITED",
        },
        "pass": True,
    }


def static_audit() -> Dict[str, Any]:
    fixed = audit_fixed()
    self_test = pure_self_test()
    r2b = audit_r2b_authority_chain()
    authority = audit_authority_inputs()
    urdf = audit_urdf()
    history = audit_g5_history()
    source_policy = source_policy_audit()
    source_contract = r2b_source_contract_audit()
    requirements = audit_user_requirement_traceability()
    loop1e = audit_loop1e(False, urdf)
    state = output_state()
    if loop1e["state"] == "PENDING" and state["state"] == "PENDING_NEW":
        verdict = "V5_LOOP2_R2B_SCRIPT_READY_LOOP1E_INPUTS_PENDING"
        execution_authorized = False
    elif loop1e.get("ready") and state["state"] in {"PENDING_NEW", "RESUME_FINALIZE"}:
        verdict = "V5_LOOP2_R2B_STATIC_EXECUTION_READY"
        execution_authorized = True
    elif state["state"] in {"COMPLETE_PASS", "COMPLETE_HOLD"}:
        verdict = "V5_LOOP2_R2B_STATIC_ALREADY_COMPLETE"
        execution_authorized = False
    else:
        verdict = "V5_LOOP2_R2B_STATIC_HOLD"
        execution_authorized = False
    return {
        "schema": "F3R2_V5_LOOP2_R2B_STATIC_AUDIT_V2",
        "timestamp_utc": utc_now(),
        "script": file_fact(Path(__file__)),
        "verdict": verdict,
        "execution_authorized": execution_authorized,
        "fixed_inputs": fixed,
        "pure_self_test": self_test,
        "r2b_authority_chain": r2b,
        "authority": authority,
        "accepted_urdf": urdf,
        "historical_g5": history,
        "source_policy": source_policy,
        "r2b_source_contract": source_contract,
        "user_requirement_traceability": requirements,
        "loop1e": loop1e,
        "output_state": state,
        "authority_classes": {
            AUTHORIZED: sorted(name for name, spec in POSES.items() if spec["class"] == AUTHORIZED),
            CANDIDATE: sorted(name for name, spec in POSES.items() if spec["class"] == CANDIDATE),
            NOT_AUTHORIZED: sorted(name for name, spec in POSES.items() if spec["class"] == NOT_AUTHORIZED),
        },
        "exact_top_configurations": list(TOP_CONFIGURATIONS),
        "solar_states": list(SOLAR_STATES),
        "authorized_q_order": list(AUTHORIZED_POSE_ORDER),
        "exact_static_cell_count": 21,
        "required_comparison_coverage": sorted(R2B_REQUIRED_COMPARISONS),
        "minimum_nonwhitelist_clearance_mm": MINIMUM_NONWHITELIST_CLEARANCE_MM,
        "expected_zero_volume_contact_whitelist": list(R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST),
        "explicit_holds": list(EXPLICIT_HOLDS),
    }


def unpack_document(result: Any, label: str) -> Tuple[Any, int, int]:
    if not isinstance(result, tuple) or len(result) < 3:
        raise GateError(f"{label}_RETURN_SHAPE_FAIL", f"{label} did not return document/errors/warnings", {"returned": repr(result)})
    model, outs = base.unpack(result)
    if len(outs) < 2:
        raise GateError(f"{label}_OUT_COUNT_FAIL", f"{label} lacks typed errors/warnings")
    return model, int(outs[0]), int(outs[1])


def open_top_read_only(sw: Any, types: Any, pythoncom: Any) -> Tuple[Any, Any, Dict[str, Any]]:
    raw, errors, warnings = unpack_document(sw.OpenDoc6(str(TOP_ASSEMBLY), SW_DOC_ASSEMBLY, SW_OPEN_SILENT_READONLY, "", 0, 0), "OPEN_TOP")
    if raw is None or errors != 0 or warnings != 0:
        raise GateError("TOP_OPEN_FAIL", "Loop1E top did not open read-only with zero typed errors/warnings", {"errors": errors, "warnings": warnings})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    return model, assembly, {"path": posix(TOP_ASSEMBLY), "read_only": True, "errors": errors, "warnings": warnings}


def loaded_models(sw: Any, types: Any, pythoncom: Any) -> List[Any]:
    rows: List[Any] = []
    for raw in base.as_list(base.value(sw, "GetDocuments")):
        if raw is not None:
            rows.append(base.wrap(raw, "IModelDoc2", types, pythoncom))
    return rows


def close_all_owned(sw: Any, types: Any, pythoncom: Any) -> List[str]:
    closed: List[str] = []
    for _ in range(100):
        docs = loaded_models(sw, types, pythoncom)
        if not docs:
            break
        progressed = False
        for model in reversed(docs):
            title = str(base.value(model, "GetTitle"))
            if not title:
                raise GateError("OWNED_DOC_TITLE_EMPTY", "loaded SolidWorks document has no title")
            sw.CloseDoc(title)
            closed.append(title)
            progressed = True
        if not progressed:
            break
    if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
        raise GateError("OWNED_DOC_CLEANUP_FAIL", "Loop2 did not close every document loaded from the initially empty session", {"closed": closed, "remaining": int(base.value(sw, "GetDocumentCount"))})
    return closed


def component_name2(component: Any) -> str:
    return str(base.value(component, "Name2"))


def component_path(component: Any) -> str:
    value = str(base.value(component, "GetPathName"))
    if not value:
        raise GateError("COMPONENT_PATH_EMPTY", "resolved component has no path", {"name2": component_name2(component)})
    return posix(Path(value))


def all_components(assembly: Any, configuration: str, whitelist: Sequence[Dict[str, Any]], types: Any, pythoncom: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    rows: Dict[str, Any] = {}
    suppressed_rows: List[Dict[str, Any]] = []
    seen_names: set[str] = set()
    raw_components = base.as_list(assembly.GetComponents(False))
    if not raw_components:
        raise GateError("ASSEMBLY_COMPONENT_SET_EMPTY", "top assembly returned no components")
    for raw in raw_components:
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        name = component_name2(component)
        if not name or name in seen_names:
            raise GateError("COMPONENT_NAME2_NOT_UNIQUE", "recursive Name2 must be nonempty and unique", {"name2": name})
        seen_names.add(name)
        suppression = int(base.value(component, "GetSuppression2"))
        matches = [item for item in whitelist if item["component_name2"] == name]
        if matches:
            expected_by_config = matches[0].get("expected_suppression_by_pose_config") if len(matches) == 1 else None
            expected = int(expected_by_config[configuration]) if isinstance(expected_by_config, dict) and configuration in expected_by_config else -1
            if len(matches) != 1 or suppression != expected or configuration not in matches[0]["top_configurations"]:
                raise GateError("WHITELISTED_SUPPRESSION_STATE_FAIL", "exact legacy/HDRM whitelist occurrence differs from its state-scoped suppression", {"name2": name, "suppression": suppression, "expected": expected, "configuration": configuration, "matches": matches})
            actual_path = component_path(component)
            if Path(actual_path).resolve() != Path(matches[0]["component_path"]).resolve() or sha256(Path(actual_path)) != matches[0]["component_path_sha256"]:
                raise GateError("WHITELISTED_SUPPRESSION_PATH_FAIL", "legacy/HDRM whitelist path/hash differs from Loop1E receipt", {"name2": name, "actual_path": actual_path, "contract": matches[0]})
            if expected == 0:
                suppressed_rows.append({"component_name2": name, "component_path": actual_path, "component_path_sha256": matches[0]["component_path_sha256"], "suppression": suppression, "expected_suppression": expected, "semantic_role": matches[0]["semantic_role"], "top_configuration": configuration, "reason": matches[0]["reason"], "excluded_from_comparisons": True})
                continue
            if expected != 2:
                raise GateError("WHITELISTED_SUPPRESSION_ENUM_FAIL", "whitelist expected suppression must be 0 or 2", {"name2": name, "configuration": configuration, "expected": expected})
        if suppression != 2:
            raise GateError("UNWHITELISTED_COMPONENT_NOT_RESOLVED", "an unwhitelisted recursive component is suppressed/lightweight/unresolved", {"name2": name, "suppression": suppression, "configuration": configuration})
        lightweight = bool(base.value(component, "IsLightWeight"))
        if lightweight:
            raise GateError("UNWHITELISTED_COMPONENT_LIGHTWEIGHT", "motion evidence cannot use a lightweight component", {"name2": name, "configuration": configuration})
        rows[name] = component
    expected_suppressed = {item["component_name2"] for item in whitelist if configuration in item["top_configurations"] and int(item["expected_suppression_by_pose_config"][configuration]) == 0}
    actual_suppressed = {item["component_name2"] for item in suppressed_rows}
    if actual_suppressed != expected_suppressed:
        raise GateError("SUPPRESSED_WHITELIST_RUNTIME_SET_FAIL", "recursive component audit did not observe the exact expected suppressed occurrence set", {"configuration": configuration, "actual": sorted(actual_suppressed), "expected": sorted(expected_suppressed)})
    if not rows:
        raise GateError("RESOLVED_COMPONENT_SET_EMPTY", "all recursive components were suppressed or missing")
    return rows, suppressed_rows


def bind_role_components(contract: Dict[str, Any], components: Dict[str, Any]) -> Dict[str, List[Any]]:
    roles: Dict[str, List[Any]] = {}
    proxy_names = {
        str(row["component_name2"])
        for row in contract.get("suppressed_nonphysical_whitelist", [])
        if row.get("semantic_role") == "HDRM_LATCH_STATE_PROXY"
    }
    for role, names in contract["component_roles"].items():
        bound_names = list(names)
        if role == "HDRM" and proxy_names:
            fixed = [name for name in names if name not in proxy_names]
            resolved_proxies = sorted(name for name in proxy_names if name in components)
            if len(resolved_proxies) != 1:
                raise GateError("HDRM_RESOLVED_PROXY_CARDINALITY_FAIL", "exactly one of six HDRM proxies must resolve in each top configuration", {"resolved": resolved_proxies, "all_proxies": sorted(proxy_names)})
            bound_names = fixed + resolved_proxies
        missing = [name for name in bound_names if name not in components]
        if missing:
            raise GateError("ROLE_COMPONENT_MISSING", "motion role names do not resolve exactly in cold top assembly", {"role": role, "missing": missing})
        roles[role] = [components[name] for name in bound_names]
    for comparison in contract["comparison_contracts"]:
        first = {component_name2(item) for item in roles[comparison["first_role"]]}
        second = {component_name2(item) for item in roles[comparison["second_role"]]}
        if first & second:
            raise GateError("COMPARISON_COMPONENT_OVERLAP", "comparison endpoints contain the same occurrence", {"comparison": comparison["name"], "overlap": sorted(first & second)})
    return roles


def unique_component_rows(rows: Sequence[Any]) -> List[Any]:
    indexed = {component_name2(row): row for row in rows}
    return [indexed[name] for name in sorted(indexed)]


def require_role_subset(role: str, rows: Sequence[Any]) -> List[Any]:
    clean = unique_component_rows(rows)
    if not clean:
        raise GateError("R2B_ROLE_EMPTY", "required R2B clearance role is empty", {"role": role})
    return clean


def expand_r2b_roles(contract: Dict[str, Any], components: Dict[str, Any]) -> Dict[str, List[Any]]:
    """Expand the frozen Loop1E role ledger without inventing occurrences.

    The six panel roles are partitioned by the exact nested P9 module token in
    Name2.  Root/support/harness partitions use exact receipted path leaves.
    Every expanded member must already belong to an upstream Loop1E role.
    """
    upstream = bind_role_components(contract, components)
    panel_roles: Dict[str, List[Any]] = {}
    for side, upstream_role in (("L", "WING_LEFT"), ("R", "WING_RIGHT")):
        source = upstream[upstream_role]
        for index in (1, 2, 3):
            role = f"SOLAR_{side}{index}"
            token = f"SOLAR_PANEL_MODULE_{side}{index}_R2B-"
            panel_roles[role] = require_role_subset(role, [item for item in source if token in component_name2(item)])
        union = {component_name2(item) for index in (1, 2, 3) for item in panel_roles[f"SOLAR_{side}{index}"]}
        source_names = {component_name2(item) for item in source}
        if union != source_names:
            raise GateError("R2B_PANEL_PARTITION_FAIL", "six P9 panel roles do not exactly partition Loop1E WING_LEFT/WING_RIGHT", {"side": side, "missing": sorted(source_names - union), "extra": sorted(union - source_names)})

    support = upstream["SUPPORT"]
    g07 = require_role_subset("G07", [item for item in support if Path(component_path(item)).name.upper().startswith("G07_")])
    g08 = require_role_subset("G08", [item for item in support if Path(component_path(item)).name.upper().startswith("G08_")])
    mid = require_role_subset("MID", [item for item in support if Path(component_path(item)).name.upper().startswith("MID_")])
    if {component_name2(item) for item in g07 + g08 + mid} != {component_name2(item) for item in support}:
        raise GateError("R2B_SUPPORT_PARTITION_FAIL", "G07/G08/Mid do not exactly partition Loop1E SUPPORT")

    panels = unique_component_rows([item for role in panel_roles.values() for item in role])
    left_panels = unique_component_rows([item for index in (1, 2, 3) for item in panel_roles[f"SOLAR_L{index}"]])
    right_panels = unique_component_rows([item for index in (1, 2, 3) for item in panel_roles[f"SOLAR_R{index}"]])
    root = upstream["WING_ROOT"]
    side_roots = side_root_components(components)
    side_prefixes = {side: component_name2(item) + "/" for side, item in side_roots.items()}
    root_by_side = {
        side: require_role_subset(f"SOLAR_ROOT_{side}", [item for item in root if component_name2(item).startswith(prefix)])
        for side, prefix in side_prefixes.items()
    }
    if {component_name2(item) for side in ("L", "R") for item in root_by_side[side]} != {component_name2(item) for item in root}:
        raise GateError("R2B_ROOT_SIDE_PARTITION_FAIL", "L/R side roots do not exactly partition Loop1E WING_ROOT", {"prefixes": side_prefixes})
    left = unique_component_rows(left_panels + root_by_side["L"])
    right = unique_component_rows(right_panels + root_by_side["R"])
    solar_harness = require_role_subset(
        "SOLAR_HARNESS",
        [
            item
            for item in panels + root
            if any(token in Path(component_path(item)).name.upper() for token in ("_HARNESS_EXIT_IF_R2B", "HARNESS_SERVICE_LOOP", "WING_HARNESS_GROMMET"))
        ],
    )
    moving_with_arm_ee = unique_component_rows(upstream["ARM_MOVING"] + upstream["GRIPPER"] + upstream["CAMERA"])
    roles: Dict[str, List[Any]] = {
        "ARM_MOVING": upstream["ARM_MOVING"],
        "BUS": upstream["BUS"],
        **panel_roles,
        "SOLAR_ROOT": root,
        "GRIPPER": upstream["GRIPPER"],
        "CAMERA": upstream["CAMERA"],
        "B601_HARNESS": upstream["HARNESS"],
        "SOLAR_HARNESS": solar_harness,
        "MOVING_WITH_ARM_EE": moving_with_arm_ee,
        "SOLAR_PANELS": panels,
        "G07": g07,
        "G08": g08,
        "MID": mid,
        "HDRM": upstream["HDRM"],
        "SOLAR_LEFT": left,
        "SOLAR_RIGHT": right,
    }
    required_role_names = {role for pair in R2B_REQUIRED_COMPARISONS.values() for role in pair}
    if set(roles) != required_role_names:
        raise GateError("R2B_ROLE_SCHEMA_FAIL", "expanded R2B role schema differs from exact comparison endpoints", {"actual": sorted(roles), "expected": sorted(required_role_names)})
    for name, (first_role, second_role) in R2B_REQUIRED_COMPARISONS.items():
        overlap = {component_name2(item) for item in roles[first_role]} & {component_name2(item) for item in roles[second_role]}
        if overlap:
            raise GateError("R2B_COMPARISON_ROLE_OVERLAP", "R2B comparison endpoint roles overlap", {"comparison": name, "overlap": sorted(overlap)})
    return roles


def r2b_comparison_contracts() -> List[Dict[str, Any]]:
    return [
        {"name": name, "first_role": pair[0], "second_role": pair[1], "minimum_allowed_mm": MINIMUM_NONWHITELIST_CLEARANCE_MM}
        for name, pair in R2B_REQUIRED_COMPARISONS.items()
    ]


def exact_zero_contact_match(first_name: str, second_name: str, state: str) -> Optional[Dict[str, Any]]:
    wanted = {first_name, second_name}
    matches = [
        dict(row)
        for row in R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST
        if set(str(value) for value in row.get("component_name2", [])) == wanted
        and state in row.get("allowed_top_configurations", [])
        and float(row.get("maximum_volume_mm3", math.nan)) == 0.0
    ]
    if len(matches) > 1:
        raise GateError("R2B_CONTACT_WHITELIST_AMBIGUOUS", "body pair matches multiple zero-volume contact rows", {"first": first_name, "second": second_name, "state": state, "matches": matches})
    return matches[0] if matches else None


def audit_r2b_contact_whitelist_runtime(components: Dict[str, Any]) -> List[Dict[str, Any]]:
    clean: List[Dict[str, Any]] = []
    known = set(components)
    names: set[str] = set()
    for raw in R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST:
        name = str(raw.get("name", ""))
        members = raw.get("component_name2")
        states = raw.get("allowed_top_configurations")
        if (
            not name
            or name in names
            or not isinstance(members, (list, tuple))
            or len(members) != 2
            or len(set(str(value) for value in members)) != 2
            or any(str(value) not in known for value in members)
            or not isinstance(states, (list, tuple))
            or not states
            or any(str(value) not in SOLAR_STATES for value in states)
            or float(raw.get("maximum_volume_mm3", math.nan)) != 0.0
            or not str(raw.get("physical_basis", "")).strip()
        ):
            raise GateError("R2B_CONTACT_WHITELIST_CONTRACT_FAIL", "zero-volume contact whitelist row is not exact component-pair/state scoped", {"row": raw})
        names.add(name)
        clean.append(dict(raw))
    return clean


def every_body_pair_clearance(model: Any, comparison: Dict[str, Any], roles: Dict[str, List[Any]], state: str, types: Any, pythoncom: Any, *, include_body_pairs: bool) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for first_component in roles[comparison["first_role"]]:
        for second_component in roles[comparison["second_role"]]:
            first_name, second_name = component_name2(first_component), component_name2(second_component)
            contact = exact_zero_contact_match(first_name, second_name, state)
            for first_body in component_bodies(first_component, types, pythoncom):
                for second_body in component_bodies(second_component, types, pythoncom):
                    distance = strict_closest_distance(model, first_body, second_body, str(comparison["name"]))
                    allowed = 0.0 if contact is not None else MINIMUM_NONWHITELIST_CLEARANCE_MM
                    row = {
                        **distance,
                        "comparison": comparison["name"],
                        "first_role": comparison["first_role"],
                        "second_role": comparison["second_role"],
                        "first_component": first_name,
                        "second_component": second_name,
                        "first_body": str(base.value(first_body, "Name")),
                        "second_body": str(base.value(second_body, "Name")),
                        "state": state,
                        "zero_volume_contact_whitelist": contact,
                        "minimum_allowed_mm": allowed,
                        "pass": distance["distance_mm"] >= allowed,
                    }
                    rows.append(row)
                    if not row["pass"]:
                        raise GateError("R2B_BODY_PAIR_CLEARANCE_LT_5MM", "non-whitelisted body pair is below 5 mm", row)
    if not rows:
        raise GateError("R2B_BODY_PAIR_SET_EMPTY", "required comparison produced no native solid body pair", {"comparison": comparison})
    worst = min(rows, key=lambda row: (row["distance_mm"], row["first_component"], row["second_component"], row["first_body"], row["second_body"]))
    return {
        "comparison": comparison["name"],
        "first_role": comparison["first_role"],
        "second_role": comparison["second_role"],
        "minimum_allowed_mm": MINIMUM_NONWHITELIST_CLEARANCE_MM,
        "body_pair_count": len(rows),
        "minimum_distance_mm": worst["distance_mm"],
        "worst_body_pair": worst,
        "zero_volume_whitelisted_pair_count": sum(row["zero_volume_contact_whitelist"] is not None for row in rows),
        "body_pair_ledger_scope": "ALL_BODY_PAIRS" if include_body_pairs else "COUNT_PLUS_WORST_WITNESS_ALL_PAIRS_EVALUATED",
        "body_pairs": rows if include_body_pairs else None,
        "pass": all(row["pass"] for row in rows),
    }


def r2b_sample_metrics(model: Any, assembly: Any, roles: Dict[str, List[Any]], state: str, types: Any, pythoncom: Any, *, include_body_pairs: bool) -> Dict[str, Any]:
    comparisons = [every_body_pair_clearance(model, row, roles, state, types, pythoncom, include_body_pairs=include_body_pairs) for row in r2b_comparison_contracts()]
    if {row["comparison"] for row in comparisons} != set(R2B_REQUIRED_COMPARISONS):
        raise GateError("R2B_SAMPLE_COMPARISON_COVERAGE_FAIL", "R2B sample comparison coverage is not exact", {"actual": sorted(row["comparison"] for row in comparisons)})
    interference_contract = {
        "comparison_contracts": r2b_comparison_contracts(),
        "expected_contact_whitelist": [
            {
                "name": row["name"],
                "component_name2": list(row["component_name2"]),
                "allowed_pose_or_sequence_nodes": list(row["allowed_top_configurations"]),
                "maximum_volume_mm3": 0.0,
            }
            for row in R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST
        ],
    }
    interference = native_interference(assembly, roles, interference_contract, state, types, pythoncom)
    minimum = min(row["minimum_distance_mm"] for row in comparisons)
    if not math.isfinite(minimum):
        raise GateError("R2B_MINIMUM_CLEARANCE_NONFINITE", "R2B sample minimum clearance is nonfinite")
    return {
        "minimum_clearance_mm": minimum,
        "comparison_count": len(comparisons),
        "comparisons": comparisons,
        "native_interference": interference,
        "nonwhitelist_minimum_required_mm": MINIMUM_NONWHITELIST_CLEARANCE_MM,
        "body_pair_evidence_scope": "ALL_BODY_PAIRS" if include_body_pairs else "COUNT_PLUS_WORST_WITNESS_ALL_PAIRS_EVALUATED",
        "any_positive_interference_fails": True,
        "pass": interference["pass"] and all(row["pass"] for row in comparisons),
    }


def component_bodies(component: Any, types: Any, pythoncom: Any) -> List[Any]:
    bodies = [base.wrap(raw, "IBody2", types, pythoncom) for raw in base.as_list(component.GetBodies2(SW_BODY_SOLID))]
    if not bodies:
        raise GateError("COMPONENT_SOLID_BODY_EMPTY", "comparison component returned no solid bodies", {"name2": component_name2(component), "path": component_path(component)})
    for body in bodies:
        if int(base.value(body, "GetType")) != SW_BODY_SOLID:
            raise GateError("COMPONENT_BODY_TYPE_FAIL", "GetBodies2(swSolidBody) returned a non-solid body", {"name2": component_name2(component), "body": str(base.value(body, "Name"))})
    return bodies


def strict_closest_distance(model: Any, first: Any, second: Any, label: str) -> Dict[str, Any]:
    returned = model.ClosestDistance(first, second)
    distance, outs = base.unpack(returned)
    if distance is None:
        raise GateError("CLOSEST_DISTANCE_MISSING", "native ClosestDistance returned no distance", {"label": label, "returned": repr(returned)})
    distance_m = require_finite_number(distance, "CLOSEST_DISTANCE_NONFINITE", f"{label}.distance")
    if distance_m < 0.0:
        raise GateError("CLOSEST_DISTANCE_NO_SOLUTION", "native ClosestDistance returned -1/no solution", {"label": label, "distance_m": distance_m})
    if len(outs) < 2:
        raise GateError("CLOSEST_DISTANCE_WITNESS_MISSING", "native ClosestDistance omitted witness points", {"label": label, "returned": repr(returned)})
    points: List[List[float]] = []
    for index, raw in enumerate(outs[:2]):
        values = [require_finite_number(value, "CLOSEST_DISTANCE_WITNESS_NONFINITE", f"{label}.point{index}") for value in base.as_list(raw)]
        if len(values) != 3:
            raise GateError("CLOSEST_DISTANCE_WITNESS_SHAPE", "native ClosestDistance witness must contain three coordinates", {"label": label, "point": values})
        points.append(values)
    return {"distance_mm": distance_m * 1000.0, "point1_mm": [value * 1000.0 for value in points[0]], "point2_mm": [value * 1000.0 for value in points[1]], "api": "IModelDoc2.ClosestDistance"}


def minimum_role_distance(model: Any, comparison: Dict[str, Any], roles: Dict[str, List[Any]], types: Any, pythoncom: Any) -> Dict[str, Any]:
    best: Optional[Dict[str, Any]] = None
    pair_count = 0
    for first_component in roles[comparison["first_role"]]:
        for second_component in roles[comparison["second_role"]]:
            for first_body in component_bodies(first_component, types, pythoncom):
                for second_body in component_bodies(second_component, types, pythoncom):
                    pair_count += 1
                    row = strict_closest_distance(model, first_body, second_body, str(comparison["name"]))
                    row.update({
                        "first_component": component_name2(first_component),
                        "second_component": component_name2(second_component),
                        "first_body": str(base.value(first_body, "Name")),
                        "second_body": str(base.value(second_body, "Name")),
                    })
                    if best is None or row["distance_mm"] < best["distance_mm"]:
                        best = row
    if best is None or pair_count <= 0:
        raise GateError("MINIMUM_DISTANCE_COMPARISON_EMPTY", "required comparison produced no body pairs", {"comparison": comparison["name"]})
    minimum = require_finite_number(comparison["minimum_allowed_mm"], "COMPARISON_LIMIT_NONFINITE", str(comparison["name"]))
    best.update({"comparison": comparison["name"], "body_pair_count": pair_count, "minimum_allowed_mm": minimum, "pass": best["distance_mm"] + NUMERIC_TOL >= minimum})
    if not best["pass"]:
        raise GateError("MINIMUM_CLEARANCE_FAIL", "native minimum component distance is below the contracted limit", best)
    return best


def persist_bytes(extension: Any, obj: Any) -> bytes:
    raw = extension.GetPersistReference3(obj)
    if raw is None:
        raise GateError("PERSIST_REFERENCE_NULL", "GetPersistReference3 returned null")
    data = bytes(raw) if isinstance(raw, (bytes, bytearray)) else bytes(int(value) & 0xFF for value in base.as_list(raw))
    if not data or int(extension.GetPersistReferenceCount3(obj)) != len(data):
        raise GateError("PERSIST_REFERENCE_COUNT_FAIL", "persistent reference byte count is empty/inconsistent", {"bytes": len(data)})
    return data


def resolve_persist_entity(extension: Any, encoded: str, pythoncom: Any, label: str) -> Tuple[Any, Dict[str, Any]]:
    from win32com.client import VARIANT

    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise GateError("PERSIST_REFERENCE_BASE64_FAIL", "persistent entity reference is unparsed", {"label": label}) from exc
    if not data:
        raise GateError("PERSIST_REFERENCE_EMPTY", "persistent entity reference is empty", {"label": label})
    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, list(data))
    obj, outs = base.unpack(extension.GetObjectByPersistReference3(typed, 0))
    error = int(outs[0]) if outs else 0
    if obj is None or error != 0:
        raise GateError("PERSIST_REFERENCE_RESOLVE_FAIL", "persistent entity did not resolve", {"label": label, "error": error})
    roundtrip = persist_bytes(extension, obj)
    if roundtrip != data:
        raise GateError("PERSIST_REFERENCE_ROUNDTRIP_FAIL", "persistent entity bytes changed after recovery", {"label": label, "expected_sha256": hashlib.sha256(data).hexdigest().upper(), "actual_sha256": hashlib.sha256(roundtrip).hexdigest().upper()})
    return obj, {"label": label, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(), "resolve_error": error, "roundtrip_exact": True}


def active_configuration_name(model: Any, types: Any, pythoncom: Any) -> str:
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    name = str(base.value(active, "Name"))
    if not name:
        raise GateError("ACTIVE_CONFIGURATION_EMPTY", "document active configuration has no name")
    return name


def show_configuration(model: Any, configuration: str, types: Any, pythoncom: Any) -> None:
    names = [str(value) for value in base.as_list(base.value(model, "GetConfigurationNames"))]
    if configuration not in names:
        raise GateError("TOP_CONFIGURATION_MISSING", "contracted top configuration is absent", {"configuration": configuration, "actual": names})
    if not bool(model.ShowConfiguration2(configuration)) or active_configuration_name(model, types, pythoncom) != configuration:
        raise GateError("TOP_CONFIGURATION_ACTIVATE_FAIL", "top configuration did not activate/read back", {"configuration": configuration})
    if not bool(model.ForceRebuild3(True)):
        raise GateError("TOP_CONFIGURATION_REBUILD_FAIL", "full rebuild failed after configuration activation", {"configuration": configuration})


def driver_owner_model(top_model: Any, components: Dict[str, Any], driver: Dict[str, Any], types: Any, pythoncom: Any) -> Tuple[Any, Optional[Any]]:
    owner_name = str(driver["dimension_owner_component_name2"])
    if owner_name == "__TOP__":
        return top_model, None
    if owner_name not in components:
        raise GateError("JOINT_DRIVER_OWNER_MISSING", "joint driver owner Name2 does not resolve", {"joint": driver["joint"], "owner": owner_name})
    component = components[owner_name]
    raw_model = base.value(component, "GetModelDoc2")
    if raw_model is None:
        raise GateError("JOINT_DRIVER_OWNER_DOC_NULL", "joint driver owner component has no resolved model document", {"joint": driver["joint"], "owner": owner_name})
    return base.wrap(raw_model, "IModelDoc2", types, pythoncom), component


def audit_joint_driver_runtime(top_model: Any, components: Dict[str, Any], driver: Dict[str, Any], extension: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    owner_model, owner_component = driver_owner_model(top_model, components, driver, types, pythoncom)
    raw_dimension = owner_model.Parameter(str(driver["native_angle_dimension_full_name"]))
    if raw_dimension is None:
        raise GateError("JOINT_ANGLE_DIMENSION_MISSING", "native joint angle dimension did not resolve", {"joint": driver["joint"], "dimension": driver["native_angle_dimension_full_name"]})
    dimension = base.wrap(raw_dimension, "IDimension", types, pythoncom)
    actual_dimension_full_name = str(base.value(dimension, "FullName"))
    if actual_dimension_full_name != str(driver["native_angle_dimension_full_name"]):
        raise GateError("JOINT_ANGLE_DIMENSION_FULLNAME_FAIL", "native joint dimension FullName differs from the motion contract", {"joint": driver["joint"], "actual": actual_dimension_full_name, "expected": driver["native_angle_dimension_full_name"]})
    raw_feature = owner_model.FeatureByName(str(driver["native_limit_feature_name"]))
    if raw_feature is None:
        raise GateError("JOINT_LIMIT_FEATURE_MISSING", "native joint limit feature did not resolve", {"joint": driver["joint"], "feature": driver["native_limit_feature_name"]})
    feature = base.wrap(raw_feature, "IFeature", types, pythoncom)
    raw_dimension_owner = base.value(dimension, "GetFeatureOwner")
    if raw_dimension_owner is None:
        raise GateError("JOINT_DIMENSION_OWNER_NULL", "native joint angle dimension has no feature owner", {"joint": driver["joint"]})
    dimension_owner = base.wrap(raw_dimension_owner, "IFeature", types, pythoncom)
    if str(base.value(dimension_owner, "Name")) != str(base.value(feature, "Name")):
        raise GateError("JOINT_DIMENSION_LIMIT_FEATURE_BINDING_FAIL", "native angle dimension is not owned by the contracted limit feature", {"joint": driver["joint"], "dimension_owner": str(base.value(dimension_owner, "Name")), "expected_feature": str(base.value(feature, "Name"))})
    if int(base.value(feature, "GetErrorCode2")) != 0 or bool(base.value(feature, "IsSuppressed")):
        raise GateError("JOINT_LIMIT_FEATURE_HEALTH_FAIL", "native joint limit feature is errored or suppressed", {"joint": driver["joint"], "feature": driver["native_limit_feature_name"]})
    raw_definition = base.value(feature, "GetDefinition")
    if raw_definition is None:
        raise GateError("JOINT_LIMIT_DEFINITION_NULL", "joint limit feature returned no definition", {"joint": driver["joint"]})
    try:
        definition = base.wrap(raw_definition, "IAngleMateFeatureData", types, pythoncom)
    except Exception as exc:
        raise GateError("JOINT_LIMIT_DEFINITION_TYPE_FAIL", "joint limit feature definition is not IAngleMateFeatureData", {"joint": driver["joint"]}) from exc
    accessed = False
    try:
        if hasattr(definition, "AccessSelections"):
            accessed = bool(definition.AccessSelections(top_model, owner_component))
            if not accessed:
                raise GateError("JOINT_LIMIT_ACCESS_SELECTIONS_FAIL", "joint limit definition selection access failed", {"joint": driver["joint"]})
        minimum = require_finite_number(base.value(definition, "MinimumAngle"), "JOINT_LIMIT_READBACK_FAIL", f"{driver['joint']}.MinimumAngle")
        maximum = require_finite_number(base.value(definition, "MaximumAngle"), "JOINT_LIMIT_READBACK_FAIL", f"{driver['joint']}.MaximumAngle")
        advanced = bool(base.value(definition, "IsAdvancedMate"))
        mate_entities = base.as_list(base.value(definition, "EntitiesToMate"))
    finally:
        if accessed and hasattr(definition, "ReleaseSelectionAccess"):
            definition.ReleaseSelectionAccess()
    if not advanced or abs(minimum - float(driver["native_minimum_rad"])) > NUMERIC_TOL or abs(maximum - float(driver["native_maximum_rad"])) > NUMERIC_TOL:
        raise GateError("JOINT_LIMIT_NATIVE_READBACK_FAIL", "native advanced limit angle does not match accepted URDF", {"joint": driver["joint"], "minimum": minimum, "maximum": maximum, "expected": [driver["native_minimum_rad"], driver["native_maximum_rad"]], "advanced": advanced})
    if len(mate_entities) != 2:
        raise GateError("JOINT_MATE_ENTITY_RUNTIME_SET_FAIL", "native angle mate does not expose exactly two entities", {"joint": driver["joint"], "count": len(mate_entities)})
    actual_mate_pairs: List[Tuple[str, str]] = []
    for entity in mate_entities:
        ref_hash = hashlib.sha256(persist_bytes(extension, entity)).hexdigest().upper()
        try:
            typed_entity = base.wrap(entity, "IEntity", types, pythoncom)
            raw_entity_owner = base.value(typed_entity, "GetComponent")
            entity_owner = component_name2(base.wrap(raw_entity_owner, "IComponent2", types, pythoncom)) if raw_entity_owner is not None else "__TOP__"
        except Exception as exc:
            raise GateError("JOINT_MATE_PLANE_ENTITY_INTERFACE_FAIL", "angle-mate endpoint is not a persistent assembly plane IEntity", {"joint": driver["joint"]}) from exc
        actual_mate_pairs.append((ref_hash, entity_owner))
    expected_mate_pairs = sorted((hashlib.sha256(base64.b64decode(str(encoded), validate=True)).hexdigest().upper(), str(owner)) for encoded, owner in zip(driver["angle_mate_plane_entity_persist_base64"], driver["angle_mate_plane_owner_component_name2"]))
    if sorted(actual_mate_pairs) != expected_mate_pairs:
        raise GateError("JOINT_MATE_ENTITY_PERSIST_READBACK_FAIL", "native angle-mate plane refs/owners differ from the persistent receipt contract", {"joint": driver["joint"], "actual": sorted(actual_mate_pairs), "expected": expected_mate_pairs})
    axis_obj, axis_ref = resolve_persist_entity(extension, str(driver["axis_entity_persist_base64"]), pythoncom, f"{driver['joint']}.axis")
    try:
        entity = base.wrap(axis_obj, "IEntity", types, pythoncom)
        raw_owner = base.value(entity, "GetComponent")
    except Exception as exc:
        raise GateError("JOINT_AXIS_ENTITY_INTERFACE_FAIL", "persistent joint axis witness is not an assembly IEntity", {"joint": driver["joint"]}) from exc
    axis_owner = component_name2(base.wrap(raw_owner, "IComponent2", types, pythoncom)) if raw_owner is not None else "__TOP__"
    if axis_owner != str(driver["axis_owner_component_name2"]):
        raise GateError("JOINT_AXIS_OWNER_FAIL", "persistent joint axis witness owner differs from its independent axis-owner contract", {"joint": driver["joint"], "actual": axis_owner, "expected": driver["axis_owner_component_name2"]})
    try:
        axis_face = base.wrap(axis_obj, "IFace2", types, pythoncom)
        axis_surface = base.wrap(base.value(axis_face, "GetSurface"), "ISurface", types, pythoncom)
        if not bool(axis_surface.IsCylinder()):
            raise GateError("JOINT_AXIS_WITNESS_NOT_CYLINDER", "independent joint axis witness surface is not cylindrical", {"joint": driver["joint"]})
        cylinder_params = [require_finite_number(value, "JOINT_AXIS_CYLINDER_NONFINITE", str(driver["joint"])) for value in base.as_list(base.value(axis_surface, "CylinderParams"))]
    except GateError:
        raise
    except Exception as exc:
        raise GateError("JOINT_AXIS_WITNESS_GEOMETRY_FAIL", "independent joint axis witness cannot be read as IFace2/ISurface", {"joint": driver["joint"]}) from exc
    if len(cylinder_params) < 7 or cylinder_params[6] <= 0.0:
        raise GateError("JOINT_AXIS_CYLINDER_PARAMS_FAIL", "independent axis CylinderParams shape/radius is invalid", {"joint": driver["joint"], "params": cylinder_params})
    direction = cylinder_params[3:6]
    direction_norm = math.sqrt(sum(value * value for value in direction))
    expected_direction = [float(value) for value in driver["axis_witness_cylinder_params_direction_xyz"]]
    parallel = abs(sum((value / direction_norm) * expected for value, expected in zip(direction, expected_direction))) if direction_norm > 0.0 else 0.0
    if abs(direction_norm - 1.0) > 1.0e-6 or abs(parallel - 1.0) > 1.0e-6:
        raise GateError("JOINT_AXIS_CYLINDER_DIRECTION_FAIL", "independent cylindrical axis direction differs from its frozen geometry witness", {"joint": driver["joint"], "actual": direction, "expected": expected_direction, "norm": direction_norm, "absolute_parallel_dot": parallel})
    return {
        "joint": driver["joint"],
        "dimension_owner_component_name2": driver["dimension_owner_component_name2"],
        "axis_owner_component_name2": driver["axis_owner_component_name2"],
        "owner_document_configuration": active_configuration_name(owner_model, types, pythoncom),
        "native_angle_dimension_full_name": driver["native_angle_dimension_full_name"],
        "native_limit_feature_name": driver["native_limit_feature_name"],
        "native_minimum_rad": minimum,
        "native_maximum_rad": maximum,
        "advanced_limit_angle": advanced,
        "zero_offset_rad": driver["zero_offset_rad"],
        "sign": driver["sign"],
        "axis_persistent_witness": axis_ref,
        "angle_mate_plane_ref_owner_pairs": [{"sha256": ref_hash, "owner_component_name2": owner} for ref_hash, owner in sorted(actual_mate_pairs)],
        "axis_owner_name2": axis_owner,
        "axis_witness_geometry": "CYLINDRICAL_FACE",
        "axis_witness_cylinder_params": cylinder_params,
        "dimension": dimension,
        "owner_model": owner_model,
    }


def prepare_joint_drivers(top_model: Any, components: Dict[str, Any], contract: Dict[str, Any], types: Any, pythoncom: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    extension = base.wrap(base.value(top_model, "Extension"), "IModelDocExtension", types, pythoncom)
    contexts: List[Dict[str, Any]] = []
    ledger: List[Dict[str, Any]] = []
    for driver in contract["joint_drivers"]:
        context = audit_joint_driver_runtime(top_model, components, driver, extension, types, pythoncom)
        contexts.append({**driver, **context})
        ledger.append({key: value for key, value in context.items() if key not in {"dimension", "owner_model"}})
    return contexts, ledger


def set_joint_vector(top_model: Any, contexts: List[Dict[str, Any]], q_deg: Sequence[float], types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    from win32com.client import VARIANT

    q = parse_q(q_deg)
    rows: List[Dict[str, Any]] = []
    for index, context in enumerate(contexts):
        requested_q_rad = math.radians(q[index])
        requested_native = float(context["sign"]) * requested_q_rad + float(context["zero_offset_rad"])
        if requested_native < float(context["native_minimum_rad"]) - NUMERIC_TOL or requested_native > float(context["native_maximum_rad"]) + NUMERIC_TOL:
            raise GateError("NATIVE_DRIVER_LIMIT_FAIL", "requested joint angle lies outside native limit mate", {"joint": context["joint"], "requested_native_rad": requested_native, "limit": [context["native_minimum_rad"], context["native_maximum_rad"]]})
        owner_model = context["owner_model"]
        owner_configuration = active_configuration_name(owner_model, types, pythoncom)
        configuration_names = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [owner_configuration])
        status = int(context["dimension"].SetSystemValue3(requested_native, SW_SET_VALUE_IN_SPECIFIC_CONFIGURATIONS, configuration_names))
        if status != SW_SET_VALUE_SUCCESS:
            raise GateError("JOINT_DIMENSION_SET_FAIL", "IDimension.SetSystemValue3 rejected native joint value", {"joint": context["joint"], "status": status, "configuration": owner_configuration})
        readback = require_finite_number(context["dimension"].GetSystemValue2(owner_configuration), "JOINT_DIMENSION_READBACK_NONFINITE", str(context["joint"]))
        if abs(readback - requested_native) > NUMERIC_TOL:
            raise GateError("JOINT_DIMENSION_READBACK_FAIL", "native joint dimension differs from requested q mapping", {"joint": context["joint"], "requested_native_rad": requested_native, "readback_rad": readback})
        rows.append({"joint": context["joint"], "q_deg": q[index], "q_rad": requested_q_rad, "native_dimension_rad": readback, "sign": context["sign"], "zero_offset_rad": context["zero_offset_rad"], "owner_configuration": owner_configuration, "set_status": status})
    if not bool(top_model.ForceRebuild3(True)):
        raise GateError("POSE_REBUILD_FAIL", "top full rebuild failed after setting six native joint dimensions", {"q_deg": q})
    for row, context in zip(rows, contexts):
        owner_configuration = active_configuration_name(context["owner_model"], types, pythoncom)
        post = require_finite_number(context["dimension"].GetSystemValue2(owner_configuration), "JOINT_POST_REBUILD_READBACK_NONFINITE", str(context["joint"]))
        if abs(post - row["native_dimension_rad"]) > NUMERIC_TOL:
            raise GateError("JOINT_POST_REBUILD_DRIFT", "joint dimension drifted after rebuild", {"joint": context["joint"], "before": row["native_dimension_rad"], "after": post})
        row["post_rebuild_native_dimension_rad"] = post
    return rows


def transform_max_abs(first: Sequence[float], second: Sequence[float]) -> float:
    if len(first) != 16 or len(second) != 16:
        raise GateError("R2B_TRANSFORM_COMPARE_SHAPE_FAIL", "transform comparison requires two 16-value arrays", {"first": len(first), "second": len(second)})
    return max(abs(float(a) - float(b)) for a, b in zip(first, second))


def arm_base_component(components: Dict[str, Any], contract: Dict[str, Any]) -> Any:
    owners = {str(row["dimension_owner_component_name2"]) for row in contract["joint_drivers"]}
    if len(owners) != 1:
        raise GateError("R2B_ARM_BASE_OWNER_SET_FAIL", "six native drivers do not share one exact local-arm owner", {"owners": sorted(owners)})
    name = next(iter(owners))
    if name not in components:
        raise GateError("R2B_ARM_BASE_COMPONENT_MISSING", "local-arm base/driver owner occurrence does not resolve", {"name2": name})
    return components[name]


def side_root_components(components: Dict[str, Any]) -> Dict[str, Any]:
    rows: Dict[str, Any] = {}
    for side, path in (("L", P9_LEFT_SIDE), ("R", P9_RIGHT_SIDE)):
        matches = [item for item in components.values() if Path(component_path(item)).resolve() == path.resolve()]
        if len(matches) != 1:
            raise GateError("R2B_SIDE_ROOT_COMPONENT_SET_FAIL", "top must resolve exactly one promoted P9 side occurrence", {"side": side, "path": posix(path), "matches": [component_name2(item) for item in matches]})
        rows[side] = matches[0]
    return rows


def side_referenced_configuration_fact(side_roots: Dict[str, Any], expected: str) -> Dict[str, str]:
    actual = {side: str(base.value(component, "ReferencedConfiguration")) for side, component in side_roots.items()}
    if actual != {"L": expected, "R": expected}:
        raise GateError("R2B_SIDE_REFERENCED_CONFIGURATION_FAIL", "top config did not select the exact same side-owned state on L/R", {"actual": actual, "expected": expected})
    return actual


def capture_arm_driver_originals(contexts: Sequence[Dict[str, Any]], originals: Dict[Tuple[str, str, str], Dict[str, Any]], types: Any, pythoncom: Any) -> None:
    for context in contexts:
        owner_model = context["owner_model"]
        owner_configuration = active_configuration_name(owner_model, types, pythoncom)
        owner_path = str(base.value(owner_model, "GetPathName"))
        key = (owner_path.lower(), owner_configuration, str(context["native_angle_dimension_full_name"]))
        if key not in originals:
            value = require_finite_number(context["dimension"].GetSystemValue2(owner_configuration), "R2B_ARM_ORIGINAL_READBACK_FAIL", str(context["joint"]))
            originals[key] = {"dimension": context["dimension"], "owner_model": owner_model, "configuration": owner_configuration, "value_rad": value, "joint": context["joint"], "dimension_full_name": context["native_angle_dimension_full_name"]}


def restore_arm_driver_originals(top_model: Any, originals: Dict[Tuple[str, str, str], Dict[str, Any]], types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    from win32com.client import VARIANT

    rows: List[Dict[str, Any]] = []
    for key in sorted(originals):
        row = originals[key]
        current_configuration = active_configuration_name(row["owner_model"], types, pythoncom)
        if current_configuration != str(row["configuration"]):
            if not bool(row["owner_model"].ShowConfiguration2(str(row["configuration"]))) or active_configuration_name(row["owner_model"], types, pythoncom) != str(row["configuration"]):
                raise GateError("R2B_ARM_RESTORE_CONFIGURATION_FAIL", "cannot activate original local-arm configuration before restoration", {"key": key, "current": current_configuration, "expected": row["configuration"]})
        configuration_names = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [str(row["configuration"])])
        status = int(row["dimension"].SetSystemValue3(float(row["value_rad"]), SW_SET_VALUE_IN_SPECIFIC_CONFIGURATIONS, configuration_names))
        if status != SW_SET_VALUE_SUCCESS:
            raise GateError("R2B_ARM_RESTORE_SET_FAIL", "cannot restore original in-memory arm driver value", {"key": key, "status": status})
        readback = require_finite_number(row["dimension"].GetSystemValue2(str(row["configuration"])), "R2B_ARM_RESTORE_READBACK_FAIL", str(row["joint"]))
        if abs(readback - float(row["value_rad"])) > NUMERIC_TOL:
            raise GateError("R2B_ARM_RESTORE_DRIFT", "restored arm driver differs from PRE value", {"key": key, "readback": readback, "expected": row["value_rad"]})
        rows.append({"owner_path": key[0], "configuration": row["configuration"], "joint": row["joint"], "dimension_full_name": row["dimension_full_name"], "restored_rad": readback, "set_status": status})
    if originals and not bool(top_model.ForceRebuild3(True)):
        raise GateError("R2B_ARM_RESTORE_REBUILD_FAIL", "top rebuild failed after arm driver restoration")
    return rows


def angle_dimension_from_feature(feature: Any, types: Any, pythoncom: Any) -> Any:
    raw_mate = base.value(feature, "GetSpecificFeature2")
    if raw_mate is None:
        raise GateError("R2B_SOLAR_ANGLE_MATE_NULL", "side limit-angle feature has no IMate2")
    mate = base.wrap(raw_mate, "IMate2", types, pythoncom)
    raw_display = mate.DisplayDimension2(0)
    if raw_display is None:
        raise GateError("R2B_SOLAR_ANGLE_DISPLAY_NULL", "side limit-angle mate has no display dimension")
    display = base.wrap(raw_display, "IDisplayDimension", types, pythoncom)
    raw_dimension = base.value(display, "GetDimension2")
    if raw_dimension is None:
        raise GateError("R2B_SOLAR_ANGLE_DIMENSION_NULL", "side limit-angle display has no IDimension")
    return base.wrap(raw_dimension, "IDimension", types, pythoncom)


def prepare_solar_side_drivers(side_roots: Dict[str, Any], types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for side, root in side_roots.items():
        raw_model = base.value(root, "GetModelDoc2")
        if raw_model is None:
            raise GateError("R2B_SOLAR_SIDE_MODEL_NULL", "promoted side occurrence has no resolved model", {"side": side})
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        configuration = active_configuration_name(model, types, pythoncom)
        if configuration != "SOLAR_STOWED":
            raise GateError("R2B_SOLAR_SWEEP_OWNER_CONFIG_FAIL", "solar-only sweep must use the side-owned SOLAR_STOWED slot", {"side": side, "active": configuration})
        for joint in SOLAR_DRIVER_JOINTS:
            feature_name = f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90"
            raw_feature = model.FeatureByName(feature_name)
            if raw_feature is None:
                raise GateError("R2B_SOLAR_DRIVER_FEATURE_MISSING", "side-owned limit-angle feature is missing", {"side": side, "joint": joint, "feature": feature_name})
            feature = base.wrap(raw_feature, "IFeature", types, pythoncom)
            if int(base.value(feature, "GetErrorCode2")) != 0 or bool(base.value(feature, "IsSuppressed")):
                raise GateError("R2B_SOLAR_DRIVER_FEATURE_HEALTH_FAIL", "side-owned limit-angle feature is errored/suppressed", {"side": side, "joint": joint})
            definition = base.wrap(base.value(feature, "GetDefinition"), "IAngleMateFeatureData", types, pythoncom)
            minimum = require_finite_number(base.value(definition, "MinimumAngle"), "R2B_SOLAR_DRIVER_LIMIT_FAIL", f"{side}.{joint}.minimum")
            maximum = require_finite_number(base.value(definition, "MaximumAngle"), "R2B_SOLAR_DRIVER_LIMIT_FAIL", f"{side}.{joint}.maximum")
            if not bool(base.value(definition, "IsAdvancedMate")) or abs(minimum) > NUMERIC_TOL or abs(maximum - math.pi / 2.0) > NUMERIC_TOL:
                raise GateError("R2B_SOLAR_DRIVER_LIMIT_FAIL", "side driver is not an advanced 0..90 degree limit angle", {"side": side, "joint": joint, "minimum": minimum, "maximum": maximum})
            dimension = angle_dimension_from_feature(feature, types, pythoncom)
            original = require_finite_number(dimension.GetSystemValue2(configuration), "R2B_SOLAR_DRIVER_ORIGINAL_READBACK_FAIL", f"{side}.{joint}")
            rows.append({"side": side, "joint": joint, "feature_name": feature_name, "model": model, "dimension": dimension, "configuration": configuration, "original_rad": original, "minimum_rad": minimum, "maximum_rad": maximum})
    if [(row["side"], row["joint"]) for row in rows] != [(side, joint) for side in ("L", "R") for joint in SOLAR_DRIVER_JOINTS]:
        raise GateError("R2B_SOLAR_DRIVER_SET_FAIL", "solar-only sweep did not resolve exact L/R x ROOT/H12/H23 drivers")
    return rows


def set_solar_driver_angles(top_model: Any, contexts: Sequence[Dict[str, Any]], angles: Dict[str, Sequence[float]], pythoncom: Any) -> List[Dict[str, Any]]:
    from win32com.client import VARIANT

    rows: List[Dict[str, Any]] = []
    for context in contexts:
        index = SOLAR_DRIVER_JOINTS.index(str(context["joint"]))
        requested = math.radians(float(angles[str(context["side"])][index]))
        if requested < float(context["minimum_rad"]) - NUMERIC_TOL or requested > float(context["maximum_rad"]) + NUMERIC_TOL:
            raise GateError("R2B_SOLAR_DRIVER_REQUEST_LIMIT_FAIL", "solar-only sweep angle lies outside 0..90", {"context": {key: value for key, value in context.items() if key not in {"model", "dimension"}}, "requested_rad": requested})
        names = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [str(context["configuration"])])
        status = int(context["dimension"].SetSystemValue3(requested, SW_SET_VALUE_IN_SPECIFIC_CONFIGURATIONS, names))
        if status != SW_SET_VALUE_SUCCESS:
            raise GateError("R2B_SOLAR_DRIVER_SET_FAIL", "side-owned solar IDimension rejected in-memory value", {"side": context["side"], "joint": context["joint"], "status": status})
        readback = require_finite_number(context["dimension"].GetSystemValue2(str(context["configuration"])), "R2B_SOLAR_DRIVER_READBACK_FAIL", f"{context['side']}.{context['joint']}")
        if abs(readback - requested) > NUMERIC_TOL:
            raise GateError("R2B_SOLAR_DRIVER_READBACK_DRIFT", "side-owned solar dimension differs from requested value", {"side": context["side"], "joint": context["joint"], "requested_rad": requested, "readback_rad": readback})
        rows.append({"side": context["side"], "joint": context["joint"], "feature_name": context["feature_name"], "configuration_owner": "SIDE_SLDASM_ONLY", "requested_deg": math.degrees(requested), "readback_rad": readback, "set_status": status})
    owner_models = {id(context["model"]): context["model"] for context in contexts}.values()
    if any(not bool(owner.ForceRebuild3(True)) for owner in owner_models) or not bool(top_model.ForceRebuild3(True)):
        raise GateError("R2B_SOLAR_DRIVER_REBUILD_FAIL", "top rebuild failed after side-owned solar angle command")
    return rows


def restore_solar_driver_originals(top_model: Any, contexts: Sequence[Dict[str, Any]], pythoncom: Any) -> List[Dict[str, Any]]:
    from win32com.client import VARIANT

    rows: List[Dict[str, Any]] = []
    for context in contexts:
        names = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [str(context["configuration"])])
        status = int(context["dimension"].SetSystemValue3(float(context["original_rad"]), SW_SET_VALUE_IN_SPECIFIC_CONFIGURATIONS, names))
        if status != SW_SET_VALUE_SUCCESS:
            raise GateError("R2B_SOLAR_DRIVER_RESTORE_SET_FAIL", "cannot restore solar side dimension", {"side": context["side"], "joint": context["joint"], "status": status})
        readback = require_finite_number(context["dimension"].GetSystemValue2(str(context["configuration"])), "R2B_SOLAR_DRIVER_RESTORE_READBACK_FAIL", f"{context['side']}.{context['joint']}")
        if abs(readback - float(context["original_rad"])) > NUMERIC_TOL:
            raise GateError("R2B_SOLAR_DRIVER_RESTORE_DRIFT", "solar side dimension differs from PRE value after restoration", {"side": context["side"], "joint": context["joint"], "readback_rad": readback, "expected_rad": context["original_rad"]})
        rows.append({"side": context["side"], "joint": context["joint"], "configuration": context["configuration"], "restored_rad": readback, "set_status": status})
    owner_models = {id(context["model"]): context["model"] for context in contexts}.values()
    if contexts and (any(not bool(owner.ForceRebuild3(True)) for owner in owner_models) or not bool(top_model.ForceRebuild3(True))):
        raise GateError("R2B_SOLAR_DRIVER_RESTORE_REBUILD_FAIL", "top rebuild failed after solar driver restoration")
    return rows


def verify_arm_base_invariant(arm_base: Any, reference: Sequence[float], label: str) -> Dict[str, Any]:
    actual = component_transform_array(arm_base)
    error = transform_max_abs(actual, reference)
    if error > 1.0e-8:
        raise GateError("R2B_ARM_BASE_INVARIANT_FAIL", "arm base occurrence moved while only q/solar side drivers were commanded", {"label": label, "max_abs_error": error, "reference": list(reference), "actual": actual})
    return {"label": label, "component_name2": component_name2(arm_base), "world_transform_16": actual, "reference_transform_16": list(reference), "max_abs_error": error, "pass": True}


def static_clearance_cell(
    model: Any,
    assembly: Any,
    contract: Dict[str, Any],
    solar_state: str,
    pose: str,
    arm_originals: Dict[Tuple[str, str, str], Dict[str, Any]],
    arm_base_reference: Optional[List[float]],
    types: Any,
    pythoncom: Any,
) -> Tuple[Dict[str, Any], List[float]]:
    show_configuration(model, solar_state, types, pythoncom)
    components, suppressed = all_components(assembly, solar_state, contract["suppressed_nonphysical_whitelist"], types, pythoncom)
    side_roots = side_root_components(components)
    side_configs = side_referenced_configuration_fact(side_roots, solar_state)
    roles = expand_r2b_roles(contract, components)
    contexts, driver_ledger = prepare_joint_drivers(model, components, contract, types, pythoncom)
    capture_arm_driver_originals(contexts, arm_originals, types, pythoncom)
    arm_base = arm_base_component(components, contract)
    # The first reference is captured before any Loop2 q command.  This is
    # essential: capturing it after the first q would mask a floating or
    # underconstrained arm base on the first cell.
    reference = arm_base_reference if arm_base_reference is not None else component_transform_array(arm_base)
    q = parse_q(POSES[pose]["q_deg"])
    q_readback = set_joint_vector(model, contexts, q, types, pythoncom)
    base_invariant = verify_arm_base_invariant(arm_base, reference, f"{solar_state}::{pose}")
    metrics = r2b_sample_metrics(model, assembly, roles, solar_state, types, pythoncom, include_body_pairs=True)
    frame = end_effector_frame_fact(model, components, contract, types, pythoncom)
    return ({
        "solar_state": solar_state,
        "left_angles_deg": list(SOLAR_STATE_ANGLES_DEG[solar_state]["L"]),
        "right_angles_deg": list(SOLAR_STATE_ANGLES_DEG[solar_state]["R"]),
        "pose": pose,
        "authority_class": AUTHORIZED,
        "q_deg": q,
        "side_configuration_owner": "SIDE_SLDASM_ONLY",
        "side_referenced_configurations": side_configs,
        "top_level_second_solar_driver_count": 0,
        "suppressed_nonphysical_ledger": suppressed,
        "joint_driver_contract": driver_ledger,
        "joint_dimension_readback": q_readback,
        "arm_base_invariant": base_invariant,
        "end_effector_frame": frame,
        "camera_visibility_proxy": {"method": "CAMERA_NATIVE_ENVELOPE_TO_SOLAR_BODY_PAIR_CLEARANCE", "minimum_clearance_mm": next(row["minimum_distance_mm"] for row in metrics["comparisons"] if row["comparison"] == "CAMERA_SOLAR"), "calibrated_fov_claim": False},
        "arm_clearance_mm": min(row["minimum_distance_mm"] for row in metrics["comparisons"] if row["comparison"].startswith("ARM_")),
        "bus_clearance_mm": min(row["minimum_distance_mm"] for row in metrics["comparisons"] if row["comparison"] in {"SOLAR_BUS", "SOLAR_HARNESS_BUS"}),
        "harness_clearance_mm": min(row["minimum_distance_mm"] for row in metrics["comparisons"] if "HARNESS" in row["comparison"]),
        "metrics": metrics,
        "pass": metrics["pass"],
    }, list(reference))


def interpolate_solar_angles(start_state: str, end_state: str, t: float) -> Dict[str, List[float]]:
    if not math.isfinite(t) or not 0.0 <= t <= 1.0:
        raise GateError("R2B_SOLAR_SWEEP_T_FAIL", "solar sweep interpolation parameter lies outside [0,1]", {"t": t})
    return {
        side: [
            float(first) + t * (float(second) - float(first))
            for first, second in zip(SOLAR_STATE_ANGLES_DEG[start_state][side], SOLAR_STATE_ANGLES_DEG[end_state][side])
        ]
        for side in ("L", "R")
    }


def solar_only_adaptive_segment(
    model: Any,
    assembly: Any,
    contract: Dict[str, Any],
    components: Dict[str, Any],
    roles: Dict[str, List[Any]],
    arm_contexts: List[Dict[str, Any]],
    q_pose: str,
    solar_contexts: Sequence[Dict[str, Any]],
    start_state: str,
    end_state: str,
    arm_base: Any,
    arm_base_reference: Sequence[float],
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    cache: Dict[float, Dict[str, Any]] = {}
    subdivisions: List[Dict[str, Any]] = []
    q = parse_q(POSES[q_pose]["q_deg"])

    def evaluate(t: float, depth: int) -> Dict[str, Any]:
        key = round(float(t), 12)
        if key in cache:
            return cache[key]
        angles = interpolate_solar_angles(start_state, end_state, t)
        solar_readback = set_solar_driver_angles(model, solar_contexts, angles, pythoncom)
        # Solar-only means all six arm dimensions must remain exactly at q.
        arm_readback: List[Dict[str, Any]] = []
        for index, context in enumerate(arm_contexts):
            owner_configuration = active_configuration_name(context["owner_model"], types, pythoncom)
            native = require_finite_number(context["dimension"].GetSystemValue2(owner_configuration), "R2B_SOLAR_SWEEP_ARM_READBACK_FAIL", str(context["joint"]))
            expected = float(context["sign"]) * math.radians(q[index]) + float(context["zero_offset_rad"])
            if abs(native - expected) > NUMERIC_TOL:
                raise GateError("R2B_SOLAR_SWEEP_ARM_Q_DRIFT", "arm q changed during solar-only sweep", {"joint": context["joint"], "actual_rad": native, "expected_rad": expected, "q_pose": q_pose})
            arm_readback.append({"joint": context["joint"], "q_deg": q[index], "native_dimension_rad": native, "owner_configuration": owner_configuration})
        invariant = verify_arm_base_invariant(arm_base, arm_base_reference, f"{q_pose}::{start_state}->{end_state}@{t:.12f}")
        label = f"SOLAR_ONLY_{start_state}_TO_{end_state}"
        metrics = r2b_sample_metrics(model, assembly, roles, label, types, pythoncom, include_body_pairs=False)
        row = {"t": float(t), "depth_first_evaluated": depth, "q_pose": q_pose, "q_deg": q, "angles_deg": angles, "solar_driver_readback": solar_readback, "arm_joint_readback": arm_readback, "arm_base_invariant": invariant, "metrics": metrics, "pass": metrics["pass"]}
        cache[key] = row
        return row

    def recurse(left_t: float, right_t: float, depth: int) -> None:
        middle_t = 0.5 * (left_t + right_t)
        left, middle, right = evaluate(left_t, depth), evaluate(middle_t, depth), evaluate(right_t, depth)
        angle_span = max(
            abs(float(a) - float(b))
            for side in ("L", "R")
            for a, b in zip(left["angles_deg"][side], right["angles_deg"][side])
        )
        minimum = min(left["metrics"]["minimum_clearance_mm"], middle["metrics"]["minimum_clearance_mm"], right["metrics"]["minimum_clearance_mm"])
        reasons: List[str] = []
        if angle_span > SOLAR_SWEEP_INITIAL_MAX_STEP_DEG:
            reasons.append("SOLAR_ANGLE_STEP_GT_7P5_DEG")
        if minimum < NEAR_CLEARANCE_MM and angle_span > SOLAR_SWEEP_NEAR_CLEARANCE_MAX_STEP_DEG:
            reasons.append("NEAR_CLEARANCE_LT_10MM_REQUIRES_0P5DEG_SOLAR_STEP")
        subdivisions.append({"left_t": left_t, "middle_t": middle_t, "right_t": right_t, "depth": depth, "max_solar_angle_span_deg": angle_span, "minimum_clearance_mm": minimum, "refine_reasons": reasons})
        if not reasons:
            return
        if depth >= SOLAR_SWEEP_MAX_DEPTH:
            raise GateError("R2B_SOLAR_SWEEP_ADAPTIVE_UNRESOLVED", "solar-only sweep still requires refinement at max depth", {"q_pose": q_pose, "segment": f"{start_state}->{end_state}", "interval": subdivisions[-1]})
        recurse(left_t, middle_t, depth + 1)
        recurse(middle_t, right_t, depth + 1)

    recurse(0.0, 1.0, 0)
    samples = [cache[key] for key in sorted(cache)]
    if len(samples) < 3 or samples[0]["t"] != 0.0 or samples[-1]["t"] != 1.0:
        raise GateError("R2B_SOLAR_SWEEP_SAMPLE_SET_FAIL", "adaptive solar segment lacks endpoint/midpoint samples")
    return {
        "segment": f"{start_state}->{end_state}",
        "q_pose": q_pose,
        "driver_owner": "SIDE_SLDASM_ONLY",
        "top_level_second_driver_count": 0,
        "interpolation": "LINEAR_IN_SIDE_NATIVE_LOGICAL_ANGLE_COORDINATES",
        "adaptive_sampling": {"initial_max_step_deg": SOLAR_SWEEP_INITIAL_MAX_STEP_DEG, "near_clearance_mm": NEAR_CLEARANCE_MM, "near_clearance_max_step_deg": SOLAR_SWEEP_NEAR_CLEARANCE_MAX_STEP_DEG, "max_depth": SOLAR_SWEEP_MAX_DEPTH, "sample_count": len(samples), "subdivision_tests": subdivisions, "status": "COMPLETE"},
        "samples": samples,
        "worst_minimum_clearance_mm": min(row["metrics"]["minimum_clearance_mm"] for row in samples),
        "pass": all(row["pass"] for row in samples),
    }


def continuous_solar_only_sweep(
    model: Any,
    assembly: Any,
    contract: Dict[str, Any],
    arm_originals: Dict[Tuple[str, str, str], Dict[str, Any]],
    arm_base_reference: Sequence[float],
    types: Any,
    pythoncom: Any,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    show_configuration(model, "SOLAR_STOWED", types, pythoncom)
    components, suppressed = all_components(assembly, "SOLAR_STOWED", contract["suppressed_nonphysical_whitelist"], types, pythoncom)
    side_roots = side_root_components(components)
    side_referenced_configuration_fact(side_roots, "SOLAR_STOWED")
    roles = expand_r2b_roles(contract, components)
    arm_base = arm_base_component(components, contract)
    solar_contexts = prepare_solar_side_drivers(side_roots, types, pythoncom)
    segments: List[Dict[str, Any]] = []
    try:
        for pose in AUTHORIZED_POSE_ORDER:
            arm_contexts, _ledger = prepare_joint_drivers(model, components, contract, types, pythoncom)
            capture_arm_driver_originals(arm_contexts, arm_originals, types, pythoncom)
            set_joint_vector(model, arm_contexts, POSES[pose]["q_deg"], types, pythoncom)
            verify_arm_base_invariant(arm_base, arm_base_reference, f"{pose}::SOLAR_SWEEP_START")
            for start_state, end_state in SOLAR_DEPLOYMENT_SEQUENCE:
                segments.append(solar_only_adaptive_segment(model, assembly, contract, components, roles, arm_contexts, pose, solar_contexts, start_state, end_state, arm_base, arm_base_reference, types, pythoncom))
    finally:
        restored = restore_solar_driver_originals(model, solar_contexts, pythoncom)
    return ({
        "attempted": True,
        "available": True,
        "driver_contract": "EXACT_2_SIDE_SLDASM_X_3_ADVANCED_LIMIT_ANGLE_0_TO_90",
        "side_configuration_owner": "SIDE_SLDASM_ONLY",
        "top_level_second_driver_count": 0,
        "q_pose_count": len(AUTHORIZED_POSE_ORDER),
        "segment_count": len(segments),
        "segments": segments,
        "suppressed_nonphysical_ledger": suppressed,
        "pass": len(segments) == len(AUTHORIZED_POSE_ORDER) * len(SOLAR_DEPLOYMENT_SEQUENCE) and all(row["pass"] for row in segments),
    }, restored)


def critical_face_distances(model: Any, contract: Dict[str, Any], pythoncom: Any, types: Any) -> List[Dict[str, Any]]:
    extension = base.wrap(base.value(model, "Extension"), "IModelDocExtension", types, pythoncom)
    rows: List[Dict[str, Any]] = []
    for pair in contract["critical_face_pairs"]:
        first, first_ref = resolve_persist_entity(extension, str(pair["first_persist_base64"]), pythoncom, f"{pair['name']}.first")
        second, second_ref = resolve_persist_entity(extension, str(pair["second_persist_base64"]), pythoncom, f"{pair['name']}.second")
        owners: List[str] = []
        for label, obj in (("first", first), ("second", second)):
            try:
                entity = base.wrap(obj, "IEntity", types, pythoncom)
                raw_owner = base.value(entity, "GetComponent")
                owner = component_name2(base.wrap(raw_owner, "IComponent2", types, pythoncom)) if raw_owner is not None else "__TOP__"
            except Exception as exc:
                raise GateError("CRITICAL_FACE_ENTITY_INTERFACE_FAIL", "critical persistent reference is not an assembly IEntity", {"pair": pair["name"], "endpoint": label}) from exc
            owners.append(owner)
        expected_owners = [str(pair["first_component_name2"]), str(pair["second_component_name2"])]
        if owners != expected_owners:
            raise GateError("CRITICAL_FACE_OWNER_READBACK_FAIL", "critical face owner occurrences differ from the contract", {"pair": pair["name"], "actual": owners, "expected": expected_owners})
        distance = strict_closest_distance(model, first, second, str(pair["name"]))
        minimum = require_finite_number(pair["minimum_allowed_mm"], "CRITICAL_FACE_LIMIT_NONFINITE", str(pair["name"]))
        distance.update({
            "name": pair["name"],
            "comparison": pair["comparison"],
            "minimum_allowed_mm": minimum,
            "first_persistent_reference": first_ref,
            "second_persistent_reference": second_ref,
            "component_name2": owners,
            "pass": distance["distance_mm"] + NUMERIC_TOL >= minimum,
        })
        if not distance["pass"]:
            raise GateError("CRITICAL_FACE_CLEARANCE_FAIL", "critical persistent-face distance is below its contracted minimum", distance)
        rows.append(distance)
    if not rows or {row["comparison"] for row in rows} != REQUIRED_COMPARISONS:
        raise GateError("CRITICAL_FACE_RUNTIME_COVERAGE_FAIL", "runtime critical face coverage is empty/incomplete", {"actual": sorted({row["comparison"] for row in rows})})
    return rows


def native_interference(assembly: Any, roles: Dict[str, List[Any]], contract: Dict[str, Any], state_label: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_manager = base.value(assembly, "InterferenceDetectionManager")
    if raw_manager is None:
        raise GateError("INTERFERENCE_MANAGER_NULL", "top assembly lacks native InterferenceDetectionManager")
    manager = base.wrap(raw_manager, "IInterferenceDetectionMgr", types, pythoncom)
    try:
        manager.TreatCoincidenceAsInterference = False
        manager.TreatSubAssembliesAsComponents = False
        manager.IncludeMultibodyPartInterferences = True
        manager.IgnoreHiddenBodies = False
        manager.ShowIgnoredInterferences = True
        raw_rows = base.as_list(manager.GetInterferences())
        reported_count = int(base.value(manager, "GetInterferenceCount"))
        rows: List[Dict[str, Any]] = []
        for raw in raw_rows:
            interference = base.wrap(raw, "IInterference", types, pythoncom)
            raw_components = base.as_list(base.value(interference, "Components"))
            expected_component_count = int(base.value(interference, "GetComponentCount"))
            if len(raw_components) != expected_component_count or expected_component_count <= 0:
                raise GateError("INTERFERENCE_COMPONENT_SHAPE_FAIL", "IInterference component array/count is empty or inconsistent", {"reported": expected_component_count, "array": len(raw_components)})
            names: List[str] = []
            paths: List[str] = []
            for raw_component in raw_components:
                component = base.wrap(raw_component, "IComponent2", types, pythoncom)
                names.append(component_name2(component))
                paths.append(component_path(component))
            volume_mm3 = require_finite_number(base.value(interference, "Volume"), "INTERFERENCE_VOLUME_NONFINITE", "IInterference.Volume") * 1.0e9
            if volume_mm3 < 0.0:
                raise GateError("INTERFERENCE_VOLUME_NEGATIVE", "IInterference returned a negative volume", {"names": names, "volume_mm3": volume_mm3})
            rows.append({
                "component_name2": sorted(names),
                "component_paths": sorted(paths),
                "component_count": expected_component_count,
                "volume_mm3": volume_mm3,
                "possible": bool(base.value(interference, "IsPossibleInterference")),
                "fastener": bool(base.value(interference, "IsFastener")),
            })
        if reported_count != len(rows):
            raise GateError("INTERFERENCE_COUNT_FAIL", "GetInterferenceCount disagrees with parsed interference rows", {"reported": reported_count, "parsed": len(rows)})
        role_names = {role: {component_name2(item) for item in members} for role, members in roles.items()}
        comparison_hits: Dict[str, List[Dict[str, Any]]] = {row["name"]: [] for row in contract["comparison_contracts"]}
        positive_cross: List[Dict[str, Any]] = []
        for row in rows:
            names = set(row["component_name2"])
            if len(names) >= 2 and row["volume_mm3"] > 0.0:
                positive_cross.append(row)
            for comparison in contract["comparison_contracts"]:
                if names & role_names[comparison["first_role"]] and names & role_names[comparison["second_role"]]:
                    comparison_hits[comparison["name"]].append(row)
        # Possible/fastener flags are evidence fields, never an implicit
        # exception. Each positive row must match exactly one state-scoped,
        # volume-bounded expected-contact contract.
        accepted_contacts: List[Dict[str, Any]] = []
        offending: List[Dict[str, Any]] = []
        canonical_state = str(state_label) if str(state_label).startswith("SOLAR_ONLY_") else canonical_pose(state_label)
        for row in positive_cross:
            names = set(row["component_name2"])
            matches = [entry for entry in contract["expected_contact_whitelist"] if set(entry["component_name2"]) == names and canonical_state in entry["allowed_pose_or_sequence_nodes"]]
            if len(matches) == 1 and row["volume_mm3"] <= float(matches[0]["maximum_volume_mm3"]):
                accepted_contacts.append({"interference": row, "whitelist": matches[0]})
            else:
                offending.append({**row, "matching_whitelist_count": len(matches), "matching_whitelist": matches})
        if offending:
            raise GateError("NATIVE_POSITIVE_CROSS_INTERFERENCE", "native assembly contains positive-volume cross-component interference", {"offending": offending, "all_rows": rows})
        return {
            "raw_count": reported_count,
            "parsed_count": len(rows),
            "positive_cross_component_count": len(positive_cross),
            "definite_positive_cross_component_count": len(offending),
            "state_label": canonical_state,
            "accepted_expected_contacts": accepted_contacts,
            "comparison_interference_rows": comparison_hits,
            "settings": {
                "TreatCoincidenceAsInterference": False,
                "TreatSubAssembliesAsComponents": False,
                "IncludeMultibodyPartInterferences": True,
                "IgnoreHiddenBodies": False,
            },
            "pass": not offending,
        }
    except GateError:
        raise
    except Exception as exc:
        raise GateError("INTERFERENCE_UNPARSED", "native interference result could not be fully parsed", {"exception": repr(exc)}) from exc
    finally:
        manager.Done()


def sample_metrics(model: Any, assembly: Any, contract: Dict[str, Any], roles: Dict[str, List[Any]], state_label: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    comparisons = [minimum_role_distance(model, row, roles, types, pythoncom) for row in contract["comparison_contracts"]]
    if len(comparisons) != len(REQUIRED_COMPARISONS) or {row["comparison"] for row in comparisons} != REQUIRED_COMPARISONS:
        raise GateError("SAMPLE_COMPARISON_COVERAGE_FAIL", "sample comparison coverage is empty/incomplete", {"actual": sorted(row["comparison"] for row in comparisons)})
    faces = critical_face_distances(model, contract, pythoncom, types)
    interference = native_interference(assembly, roles, contract, state_label, types, pythoncom)
    all_distances = [row["distance_mm"] for row in comparisons] + [row["distance_mm"] for row in faces]
    if not all_distances or not all(math.isfinite(value) for value in all_distances):
        raise GateError("SAMPLE_CLEARANCE_EMPTY_OR_NONFINITE", "sample clearance set is empty/nonfinite")
    return {
        "minimum_component_distances": comparisons,
        "critical_face_distances": faces,
        "native_interference": interference,
        "minimum_clearance_mm": min(all_distances),
        "comparison_count": len(comparisons),
        "critical_face_pair_count": len(faces),
        "pass": True,
    }


def component_transform_array(component: Any) -> List[float]:
    transform = base.value(component, "GetTotalTransform", False)
    if transform is None:
        raise GateError("COMPONENT_TRANSFORM_NULL", "component GetTotalTransform(False) is null", {"name2": component_name2(component)})
    values = [require_finite_number(value, "COMPONENT_TRANSFORM_NONFINITE", component_name2(component)) for value in base.as_list(base.value(transform, "ArrayData"))]
    if len(values) != 16 or abs(values[12] - 1.0) > 1.0e-8 or any(abs(values[index]) > 1.0e-8 for index in (13, 14, 15)):
        raise GateError("COMPONENT_TRANSFORM_SHAPE_FAIL", "component total-transform ArrayData is not a rigid 16-value transform", {"name2": component_name2(component), "values": values})
    rotation = [values[0:3], values[3:6], values[6:9]]
    for row in rotation:
        if abs(sum(value * value for value in row) - 1.0) > 1.0e-6:
            raise GateError("COMPONENT_TRANSFORM_ROTATION_FAIL", "component rotation row is not unit length", {"name2": component_name2(component), "rotation": rotation})
    for first in range(3):
        for second in range(first + 1, 3):
            if abs(sum(rotation[first][index] * rotation[second][index] for index in range(3))) > 1.0e-6:
                raise GateError("COMPONENT_TRANSFORM_ROTATION_FAIL", "component rotation rows are not orthogonal", {"name2": component_name2(component), "rotation": rotation})
    return values


def component_total_transform_object(component: Any, types: Any, pythoncom: Any) -> Any:
    raw = base.value(component, "GetTotalTransform", False)
    if raw is None:
        raise GateError("COMPONENT_TRANSFORM_NULL", "component GetTotalTransform(False) is null", {"name2": component_name2(component)})
    return base.wrap(raw, "IMathTransform", types, pythoncom)


def relative_component_transform(first: Any, second: Any, types: Any, pythoncom: Any) -> List[float]:
    first_transform = component_total_transform_object(first, types, pythoncom)
    second_transform = component_total_transform_object(second, types, pythoncom)
    raw_inverse = first_transform.IInverse()
    if raw_inverse is None:
        raise GateError("COMPONENT_TRANSFORM_INVERSE_NULL", "IMathTransform.IInverse returned null", {"first": component_name2(first)})
    inverse = base.wrap(raw_inverse, "IMathTransform", types, pythoncom)
    raw_relative = inverse.IMultiply(second_transform)
    if raw_relative is None:
        raise GateError("COMPONENT_TRANSFORM_MULTIPLY_NULL", "IMathTransform.IMultiply returned null", {"first": component_name2(first), "second": component_name2(second)})
    relative = base.wrap(raw_relative, "IMathTransform", types, pythoncom)
    values = [require_finite_number(value, "RELATIVE_TRANSFORM_NONFINITE", f"{component_name2(first)}->{component_name2(second)}") for value in base.as_list(base.value(relative, "ArrayData"))]
    if len(values) != 16 or abs(values[12] - 1.0) > 1.0e-8 or any(abs(values[index]) > 1.0e-8 for index in (13, 14, 15)):
        raise GateError("RELATIVE_TRANSFORM_SHAPE_FAIL", "relative IMathTransform ArrayData is not 16 values", {"first": component_name2(first), "second": component_name2(second), "values": values})
    return values


def end_effector_frame_fact(model: Any, components: Dict[str, Any], contract: Dict[str, Any], types: Any, pythoncom: Any) -> Dict[str, Any]:
    ee = contract["end_effector_frame_contract"]
    names = {key: str(ee[key]) for key in ("link6_component_name2", "gripper_component_name2", "camera_component_name2")}
    missing = [name for name in names.values() if name not in components]
    if missing:
        raise GateError("END_EFFECTOR_COMPONENT_MISSING", "link6/gripper/camera component occurrence does not resolve", {"missing": missing})
    transforms = {key: component_transform_array(components[name]) for key, name in names.items()}
    relative_gripper = relative_component_transform(components[names["link6_component_name2"]], components[names["gripper_component_name2"]], types, pythoncom)
    relative_camera = relative_component_transform(components[names["link6_component_name2"]], components[names["camera_component_name2"]], types, pythoncom)
    expected_gripper = [float(value) for value in ee["expected_link6_to_gripper_transform_16"]]
    expected_camera = [float(value) for value in ee["expected_link6_to_camera_transform_16"]]
    gripper_error = max(abs(actual - expected) for actual, expected in zip(relative_gripper, expected_gripper))
    camera_error = max(abs(actual - expected) for actual, expected in zip(relative_camera, expected_camera))
    if gripper_error > 1.0e-7 or camera_error > 1.0e-7:
        raise GateError("END_EFFECTOR_RELATIVE_TRANSFORM_FAIL", "link6-to-gripper/camera relative transform differs from receipt authority", {"gripper_max_error": gripper_error, "camera_max_error": camera_error, "relative_gripper": relative_gripper, "expected_gripper": expected_gripper, "relative_camera": relative_camera, "expected_camera": expected_camera})
    extension = base.wrap(base.value(model, "Extension"), "IModelDocExtension", types, pythoncom)
    witness_rows: List[Dict[str, Any]] = []
    for key, expected_owner in (("link6", names["link6_component_name2"]), ("gripper", names["gripper_component_name2"]), ("camera", names["camera_component_name2"])):
        obj, ref = resolve_persist_entity(extension, str(ee[f"{key}_witness_persist_base64"]), pythoncom, f"end_effector.{key}")
        try:
            entity = base.wrap(obj, "IEntity", types, pythoncom)
            raw_owner = base.value(entity, "GetComponent")
            owner = component_name2(base.wrap(raw_owner, "IComponent2", types, pythoncom)) if raw_owner is not None else "__TOP__"
        except Exception as exc:
            raise GateError("END_EFFECTOR_WITNESS_ENTITY_FAIL", "end-effector witness is not an assembly IEntity", {"witness": key}) from exc
        if owner != expected_owner:
            raise GateError("END_EFFECTOR_WITNESS_OWNER_FAIL", "end-effector witness owner differs from frame contract", {"witness": key, "actual": owner, "expected": expected_owner})
        witness_rows.append({"witness": key, "owner_component_name2": owner, "persistent_reference": ref})
    return {
        "component_world_transforms": transforms,
        "link6_to_gripper_transform_16": relative_gripper,
        "link6_to_camera_transform_16": relative_camera,
        "gripper_transform_max_error": gripper_error,
        "camera_transform_max_error": camera_error,
        "persistent_witnesses": witness_rows,
        "gripper_frame_provenance": {
            "source_loop1c1_receipt_sha256": ee["source_loop1c1_receipt_sha256"],
            "source_loop1d_receipt_sha256": ee["source_loop1d_receipt_sha256"],
            "part_geometry_frame": ee["gripper_part_geometry_frame"],
            "assembly_origin_frame": ee["gripper_assembly_origin_frame"],
            "top_insertion_transform_authority": ee["top_insertion_transform_authority"],
        },
        "pass": True,
    }


def interpolate_q(first: Sequence[float], second: Sequence[float], t: float) -> List[float]:
    if not math.isfinite(t) or t < 0.0 or t > 1.0:
        raise GateError("INTERPOLATION_PARAMETER_FAIL", "segment interpolation parameter lies outside [0,1]", {"t": t})
    return [float(a) + t * (float(b) - float(a)) for a, b in zip(first, second)]


def adaptive_segment(
    model: Any,
    assembly: Any,
    contract: Dict[str, Any],
    start_name: str,
    end_name: str,
    start_q: Sequence[float],
    end_q: Sequence[float],
    configuration: str,
    state_label: str,
    authority_class: str,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    start = parse_q(start_q)
    end = parse_q(end_q)
    cache: Dict[float, Dict[str, Any]] = {}
    subdivisions: List[Dict[str, Any]] = []

    def evaluate(t: float, depth: int) -> Dict[str, Any]:
        key = round(float(t), 12)
        if key in cache:
            return cache[key]
        q = interpolate_q(start, end, t)
        show_configuration(model, configuration, types, pythoncom)
        components_now, suppressed_now = all_components(assembly, configuration, contract["suppressed_nonphysical_whitelist"], types, pythoncom)
        roles_now = bind_role_components(contract, components_now)
        contexts, driver_ledger = prepare_joint_drivers(model, components_now, contract, types, pythoncom)
        joint_readback = set_joint_vector(model, contexts, q, types, pythoncom)
        metrics = sample_metrics(model, assembly, contract, roles_now, state_label, types, pythoncom)
        frame = end_effector_frame_fact(model, components_now, contract, types, pythoncom)
        row = {
            "t": float(t),
            "depth_first_evaluated": depth,
            "q_deg": q,
            "configuration": configuration,
            "state_label_for_contact_whitelist": canonical_pose(state_label),
            "suppressed_nonphysical_occurrences": suppressed_now,
            "joint_driver_contract": driver_ledger,
            "joint_dimension_readback": joint_readback,
            "metrics": metrics,
            "end_effector_frame": frame,
            "pass": True,
        }
        cache[key] = row
        return row

    def recurse(left_t: float, right_t: float, depth: int) -> None:
        middle_t = 0.5 * (left_t + right_t)
        left, middle, right = evaluate(left_t, depth), evaluate(middle_t, depth), evaluate(right_t, depth)
        joint_span = max(abs(a - b) for a, b in zip(left["q_deg"], right["q_deg"]))
        minimum_clearance = min(left["metrics"]["minimum_clearance_mm"], middle["metrics"]["minimum_clearance_mm"], right["metrics"]["minimum_clearance_mm"])
        curvature = abs(middle["metrics"]["minimum_clearance_mm"] - 0.5 * (left["metrics"]["minimum_clearance_mm"] + right["metrics"]["minimum_clearance_mm"]))
        refine_reasons: List[str] = []
        if joint_span > INITIAL_MAX_JOINT_STEP_DEG:
            refine_reasons.append("JOINT_STEP_GT_7P5_DEG")
        if minimum_clearance < NEAR_CLEARANCE_MM and joint_span > 0.5:
            refine_reasons.append("NEAR_CLEARANCE_LT_10MM_REQUIRES_0P5DEG_STEP")
        if curvature > CLEARANCE_CURVATURE_MM:
            refine_reasons.append("MIDPOINT_CLEARANCE_CURVATURE_GT_0P5MM")
        subdivisions.append({"left_t": left_t, "middle_t": middle_t, "right_t": right_t, "depth": depth, "max_joint_span_deg": joint_span, "minimum_clearance_mm": minimum_clearance, "midpoint_curvature_mm": curvature, "refine_reasons": refine_reasons})
        if not refine_reasons:
            return
        if depth >= MAX_ADAPTIVE_DEPTH:
            raise GateError("ADAPTIVE_SAMPLING_UNRESOLVED", "adaptive segment still requires refinement at the maximum depth", {"segment": f"{start_name}->{end_name}", "interval": subdivisions[-1]})
        recurse(left_t, middle_t, depth + 1)
        recurse(middle_t, right_t, depth + 1)

    recurse(0.0, 1.0, 0)
    samples = [cache[key] for key in sorted(cache)]
    if len(samples) < 3 or samples[0]["t"] != 0.0 or samples[-1]["t"] != 1.0:
        raise GateError("ADAPTIVE_SAMPLE_SET_FAIL", "adaptive segment lacks endpoint/midpoint samples", {"segment": f"{start_name}->{end_name}", "sample_count": len(samples)})
    worst = min(row["metrics"]["minimum_clearance_mm"] for row in samples)
    if not math.isfinite(worst):
        raise GateError("ADAPTIVE_WORST_CLEARANCE_NONFINITE", "adaptive segment worst clearance is nonfinite", {"segment": f"{start_name}->{end_name}"})
    return {
        "segment": f"{start_name}->{end_name}",
        "start": start_name,
        "end": end_name,
        "authority_class": authority_class,
        "authority_scope": "NATIVE_GEOMETRIC_PATH_EVIDENCE_ONLY_NO_CONTROL_AUTHORITY_PROMOTION",
        "configuration": configuration,
        "interpolation": "LINEAR_IN_ACCEPTED_URDF_JOINT_COORDINATES_NO_WRAP",
        "adaptive_sampling": {
            "initial_max_joint_step_deg": INITIAL_MAX_JOINT_STEP_DEG,
            "near_clearance_mm": NEAR_CLEARANCE_MM,
            "near_clearance_max_joint_step_deg": 0.5,
            "midpoint_curvature_mm": CLEARANCE_CURVATURE_MM,
            "max_depth": MAX_ADAPTIVE_DEPTH,
            "sample_count": len(samples),
            "subdivision_tests": subdivisions,
            "status": "COMPLETE",
        },
        "samples": samples,
        "worst_minimum_clearance_mm": worst,
        "native_interference_pass_all_samples": all(row["metrics"]["native_interference"]["pass"] for row in samples),
        "minimum_distance_pass_all_samples": True,
        "critical_face_distance_pass_all_samples": True,
        "pass": True,
    }


def endpoint_pose_fact(model: Any, assembly: Any, contract: Dict[str, Any], pose_or_node: str, q_deg: Sequence[float], types: Any, pythoncom: Any) -> Dict[str, Any]:
    canonical = canonical_pose(pose_or_node)
    configuration = str(contract["pose_configurations"][canonical])
    show_configuration(model, configuration, types, pythoncom)
    components_now, suppressed_now = all_components(assembly, configuration, contract["suppressed_nonphysical_whitelist"], types, pythoncom)
    roles_now = bind_role_components(contract, components_now)
    contexts, driver_ledger = prepare_joint_drivers(model, components_now, contract, types, pythoncom)
    joint_readback = set_joint_vector(model, contexts, q_deg, types, pythoncom)
    metrics = sample_metrics(model, assembly, contract, roles_now, canonical, types, pythoncom)
    frame = end_effector_frame_fact(model, components_now, contract, types, pythoncom)
    authority_class = POSES[canonical]["class"] if canonical in POSES else SEQUENCE_NODES[canonical]["class"]
    return {
        "state": canonical,
        "configuration": configuration,
        "authority_class": authority_class,
        "q_deg": parse_q(q_deg),
        "suppressed_nonphysical_occurrences": suppressed_now,
        "joint_driver_contract": driver_ledger,
        "joint_dimension_readback": joint_readback,
        "metrics": metrics,
        "end_effector_frame": frame,
        "pass": True,
    }


def ik_candidate_payload(static: Dict[str, Any], native: Dict[str, Any]) -> Dict[str, Any]:
    blocked_states = [name for name in SERVICE_CHAIN if POSES[name]["q_deg"] is None]
    return {
        "schema": "F3R2_V5_LOOP2_IK_CANDIDATE_SET_V1",
        "timestamp_utc": utc_now(),
        "baseline_id": RUN_ROOT.name,
        "accepted_urdf": file_fact(ACCEPTED_URDF),
        "authority_register": file_fact(POSE_AUTHORITY_REGISTER),
        "rule": "IK_CANDIDATES_ARE_NEVER_POSE_AUTHORITY_AND_CANNOT_SELF_PROMOTE",
        "authorized_inputs_unchanged": {name: POSES[name]["q_deg"] for name in POSES if POSES[name]["class"] == AUTHORIZED},
        "existing_engineering_candidates_unchanged": {
            "Q_STOW_ENGINEERING_CANDIDATE": {
                "q_deg": POSES["Q_STOW_ENGINEERING_CANDIDATE"]["q_deg"],
                "authority_class": CANDIDATE,
                "source": posix(POSE_AUTHORITY_REGISTER),
                "native_endpoint_evidence": next(row for row in native["endpoint_states"] if row["state"] == "Q_STOW_ENGINEERING_CANDIDATE"),
            }
        },
        "service_task_candidates": [
            {
                "pose": name,
                "canonical_pose": canonical_pose(name),
                "authority_class": NOT_AUTHORIZED,
                "authorized_target_ee_pose_available": False,
                "candidate_generation_status": "BLOCKED_NO_AUTHORIZED_EE_TARGET_POSE",
                "candidates": [],
                "candidate_count": 0,
                "ranking_contract": {
                    "joint_limit_margin": None,
                    "native_clearances": None,
                    "base_reaction": None,
                    "camera_visibility": None,
                    "end_effector_error": None,
                    "reason": "NO_AUTHORIZED_TARGET_POSE_AND_NO_TIMING_OR_DYNAMICS_MODEL",
                },
            }
            for name in blocked_states
        ],
        "invented_service_q_count": 0,
        "empty_candidate_sets_are_intentional_fail_closed_evidence": True,
        "pose_authorization_required": True,
        "static_audit_sha256": hashlib.sha256(json.dumps(static, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest().upper(),
        "verdict": "IK_CANDIDATE_SET_EMPTY_NO_AUTHORIZED_SERVICE_TARGET_POSE",
    }


def authorization_markdown(native: Dict[str, Any]) -> str:
    undefined = "\n".join(f"- `{name}`: q 未定义；当前候选集为空，禁止升格。" for name in SERVICE_CHAIN if POSES[name]["q_deg"] is None)
    verified = "\n".join(f"- `{row['segment']}`: 原生自适应几何复核完成；权限仍为 `{row['authority_class']}`，不产生控制路径授权。" for row in native["adaptive_segments"])
    blocked = "\n".join(f"- `{row['segment']}`: `{row['status']}` — {row['reason']}" for row in native["blocked_segments"])
    return f"""# V5 Loop2 姿态授权仍需人工闭环

生成时间：{utc_now()}

本文件不是姿态授权。Loop2 只复核已有冻结输入和工程候选的原生几何；没有创建任何新的 service q，也没有把 IK candidate 升格为 authority。

## 已有权限边界

- `Q_DEPLOYED_HOME`、`Q_RELEASE_CLEAR`、`Q_SERVICE_READY`：仅保留既有冻结输入身份；本轮原生路径证据不等于控制器授权。
- `Q_STOW_ENGINEERING_CANDIDATE`：仍是非运行工程候选。
- `Q_RELEASE_CLEAR`：仅为释放后几何终态，不授权 HDRM/翼板连续释放过程。

## 已完成的原生几何段

{verified}

## 失败关闭/未授权段

{blocked}

## 缺失 service / retrieval 任务姿态

{undefined}

## 人工授权前必须补齐

1. 对每个 service/retrieval 状态给出可追溯的目标末端位姿、容差、目标物几何/坐标系和任务顺序。
2. 对候选 q 完成关节限位、原生连续干涉、component minimum distance、persistent critical-face distance、相机 envelope 可见性和末端误差审查。
3. 提供时间标定/动力学模型后再评价基座反作用；当前为 `NOT_EVALUATED_NO_TIMING_OR_DYNAMICS_MODEL`。
4. 线束目前只证明静态 envelope；动态弯曲/扫掠为 `HOLD_DYNAMIC_HARNESS_MODEL_REQUIRED`。
5. 相机仍未选型；只能声明 envelope/optical-frame 几何检查，不能声明标定 FOV。
6. 由有权人员把选定 candidate 写回正式 authority register；Agent 不得自行授权。
"""


def blocked_path_segments() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for first, second in zip(SERVICE_CHAIN[1:], SERVICE_CHAIN[2:]):
        rows.append({
            "segment": f"{first}->{second}",
            "chain": "SERVICE",
            "authority_class": NOT_AUTHORIZED,
            "status": "BLOCKED_MISSING_AUTHORIZED_Q",
            "adaptive_sampling_status": "NOT_STARTED_FAIL_CLOSED_NO_ENDPOINT_Q",
            "sample_count": 0,
            "native_interference": "NOT_EVALUATED",
            "minimum_distance": "NOT_EVALUATED",
            "critical_face_distance": "NOT_EVALUATED",
            "reason": "one or both service endpoint q vectors are undefined; inventing q is prohibited",
        })
    rows.extend([
        {
            "segment": "Q_STOW_ENGINEERING_CANDIDATE->SOLAR_DEPLOY_ARM_LOCKED",
            "chain": "STOW_RELEASE",
            "authority_class": CANDIDATE,
            "status": "ENDPOINTS_ONLY_CONTINUOUS_WING_DEPLOY_NOT_AUTHORIZED",
            "adaptive_sampling_status": "BLOCKED_NO_CONTINUOUS_WING_DRIVER_AUTHORITY",
            "sample_count": 0,
            "native_interference": "ENDPOINTS_EVALUATED_SEPARATELY",
            "minimum_distance": "ENDPOINTS_EVALUATED_SEPARATELY",
            "critical_face_distance": "ENDPOINTS_EVALUATED_SEPARATELY",
            "reason": "the same stow q exists at both configuration endpoints, but no authorized continuous wing-angle trajectory exists",
        },
        {
            "segment": "SOLAR_DEPLOY_ARM_LOCKED->HDRM_RELEASE",
            "chain": "STOW_RELEASE",
            "authority_class": CANDIDATE,
            "status": "ENDPOINTS_ONLY_CONTINUOUS_HDRM_RELEASE_NOT_AUTHORIZED",
            "adaptive_sampling_status": "BLOCKED_NO_CONTINUOUS_HDRM_DRIVER_AUTHORITY",
            "sample_count": 0,
            "native_interference": "ENDPOINTS_EVALUATED_SEPARATELY",
            "minimum_distance": "ENDPOINTS_EVALUATED_SEPARATELY",
            "critical_face_distance": "ENDPOINTS_EVALUATED_SEPARATELY",
            "reason": "Q_RELEASE_CLEAR is a geometric end state and does not authorize the HDRM release transit",
        },
    ])
    return rows


CLEARANCE_CSV_FIELDS: Tuple[str, ...] = (
    "evidence_type",
    "solar_state_or_segment",
    "q_pose",
    "t",
    "comparison",
    "first_role",
    "second_role",
    "body_pair_count",
    "minimum_distance_mm",
    "minimum_allowed_mm",
    "positive_interference_count",
    "pass",
)


def clearance_csv_rows(native: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for cell in native.get("static_cells", []):
        interference = cell["metrics"]["native_interference"]
        for comparison in cell["metrics"]["comparisons"]:
            rows.append({
                "evidence_type": "STATIC_7X3_CELL",
                "solar_state_or_segment": cell["solar_state"],
                "q_pose": cell["pose"],
                "t": "",
                "comparison": comparison["comparison"],
                "first_role": comparison["first_role"],
                "second_role": comparison["second_role"],
                "body_pair_count": comparison["body_pair_count"],
                "minimum_distance_mm": f"{float(comparison['minimum_distance_mm']):.12g}",
                "minimum_allowed_mm": f"{MINIMUM_NONWHITELIST_CLEARANCE_MM:.12g}",
                "positive_interference_count": interference["positive_cross_component_count"],
                "pass": str(bool(comparison["pass"] and interference["pass"])).lower(),
            })
    sweep = native.get("continuous_solar_only_sweep", {})
    for segment in sweep.get("segments", []) if isinstance(sweep, dict) else []:
        for sample in segment.get("samples", []):
            interference = sample["metrics"]["native_interference"]
            for comparison in sample["metrics"]["comparisons"]:
                rows.append({
                    "evidence_type": "ADAPTIVE_SOLAR_ONLY_SWEEP",
                    "solar_state_or_segment": segment["segment"],
                    "q_pose": segment["q_pose"],
                    "t": f"{float(sample['t']):.12g}",
                    "comparison": comparison["comparison"],
                    "first_role": comparison["first_role"],
                    "second_role": comparison["second_role"],
                    "body_pair_count": comparison["body_pair_count"],
                    "minimum_distance_mm": f"{float(comparison['minimum_distance_mm']):.12g}",
                    "minimum_allowed_mm": f"{MINIMUM_NONWHITELIST_CLEARANCE_MM:.12g}",
                    "positive_interference_count": interference["positive_cross_component_count"],
                    "pass": str(bool(comparison["pass"] and interference["pass"])).lower(),
                })
    if not rows and native.get("static_matrix_error"):
        rows.append({
            "evidence_type": "FAIL_CLOSED_NO_COMPLETED_COMPARISON",
            "solar_state_or_segment": "",
            "q_pose": "",
            "t": "",
            "comparison": "",
            "first_role": "",
            "second_role": "",
            "body_pair_count": 0,
            "minimum_distance_mm": "",
            "minimum_allowed_mm": f"{MINIMUM_NONWHITELIST_CLEARANCE_MM:.12g}",
            "positive_interference_count": "",
            "pass": "false",
        })
    return rows


def execute_native(static: Dict[str, Any]) -> Dict[str, Any]:
    if not static.get("execution_authorized"):
        raise GateError("STATIC_EXECUTION_NOT_AUTHORIZED", "Loop2 static audit did not authorize SolidWorks attachment", {"verdict": static.get("verdict")})
    script = Path(__file__).resolve()
    top_pre = file_fact(TOP_ASSEMBLY)
    loop1e_pre = file_fact(LOOP1E_RECEIPT)
    fixed_pre = audit_fixed()
    memory_samples = base.memory_gate()
    copy_once(script, SCRIPT_COPY)
    sw = types = pythoncom = None
    model = assembly = None
    closed_docs: List[str] = []
    role_dependency_paths: List[Path] = []
    role_dependencies_pre: List[Dict[str, Any]] = []
    arm_originals: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    solar_restore: List[Dict[str, Any]] = []
    arm_restore: List[Dict[str, Any]] = []
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_LOOP2_R2B_RUNTIME_TRANSACTION_V2",
        "timestamp_start_utc": utc_now(),
        "static_audit": static,
        "memory_samples_gib": memory_samples,
        "top_pre": top_pre,
        "loop1e_receipt_pre": loop1e_pre,
        "fixed_pre": fixed_pre,
    }
    try:
        sw, types, pythoncom, session = base.attach_empty_session()
        expected_session = static["loop1e"]["loop1e_session"]
        if int(session["pid"]) != int(expected_session["pid"]) or str(session["revision"]) != str(expected_session["revision"]):
            raise GateError("SESSION_B_LOOP1E_BINDING_FAIL", "live attach is not the exact Session B process recorded by Loop1E", {"live": session, "loop1e": expected_session})
        result["solidworks"] = session
        model, assembly, open_fact = open_top_read_only(sw, types, pythoncom)
        result["top_open"] = open_fact
        contract = static["loop1e"]["motion_contract"]
        names = [str(value) for value in base.as_list(base.value(model, "GetConfigurationNames"))]
        if len(names) != len(TOP_CONFIGURATIONS) or set(names) != set(TOP_CONFIGURATIONS):
            raise GateError("R2B_RUNTIME_TOP_CONFIGURATION_SET_FAIL", "live top configuration set differs from exact 11", {"actual": names, "expected": list(TOP_CONFIGURATIONS)})
        show_configuration(model, "SOLAR_STOWED", types, pythoncom)
        components, initial_suppressed = all_components(assembly, "SOLAR_STOWED", contract["suppressed_nonphysical_whitelist"], types, pythoncom)
        result["expected_zero_volume_contact_whitelist_runtime"] = audit_r2b_contact_whitelist_runtime(components)
        roles = expand_r2b_roles(contract, components)
        role_dependency_paths = sorted(
            {
                Path(component_path(item))
                for members in roles.values()
                for item in members
            }
            | {
                Path(str(row["component_path"]))
                for row in contract["suppressed_nonphysical_whitelist"]
            },
            key=lambda path: str(path).lower(),
        )
        role_dependencies_pre = [file_fact(path) for path in role_dependency_paths]
        result["component_bindings"] = {
            "component_count_recursive": len(components),
            "initial_configuration": "SOLAR_STOWED",
            "suppressed_nonphysical_whitelist": contract["suppressed_nonphysical_whitelist"],
            "initial_suppressed_occurrences": initial_suppressed,
            "roles": {role: [{"name2": component_name2(item), "path": component_path(item)} for item in members] for role, members in roles.items()},
            "role_dependency_facts_pre": role_dependencies_pre,
        }
        static_cells: List[Dict[str, Any]] = []
        arm_base_reference: Optional[List[float]] = None
        static_error: Optional[Dict[str, Any]] = None
        try:
            for solar_state in SOLAR_STATES:
                for pose in AUTHORIZED_POSE_ORDER:
                    cell, arm_base_reference = static_clearance_cell(model, assembly, contract, solar_state, pose, arm_originals, arm_base_reference, types, pythoncom)
                    static_cells.append(cell)
        except Exception as exc:
            static_error = {"verdict": getattr(exc, "code", "R2B_STATIC_MATRIX_UNEXPECTED_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", {}), "completed_cell_count": len(static_cells), "traceback": traceback.format_exc()}

        sweep: Dict[str, Any]
        if static_error is None and len(static_cells) == 21 and arm_base_reference is not None:
            try:
                sweep, solar_restore = continuous_solar_only_sweep(model, assembly, contract, arm_originals, arm_base_reference, types, pythoncom)
            except Exception as exc:
                sweep = {"attempted": True, "available": False, "pass": False, "final_gate_eligible": False, "verdict": getattr(exc, "code", "R2B_SOLAR_SWEEP_UNEXPECTED_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc(), "policy": "FAIL_CLOSED_NO_CONTINUOUS_SOLAR_CLAIM"}
        else:
            sweep = {"attempted": False, "available": False, "pass": False, "final_gate_eligible": False, "verdict": "R2B_SOLAR_SWEEP_BLOCKED_BY_STATIC_MATRIX", "static_error": static_error}

        # Always restore every in-memory runtime dimension before close.  The
        # solar helper restores in its own finally; this call covers cases in
        # which driver preparation failed before the helper owned contexts.
        arm_restore = restore_arm_driver_originals(model, arm_originals, types, pythoncom)
        show_configuration(model, "SOLAR_STOWED", types, pythoncom)
        final_gate_eligible = static_error is None and len(static_cells) == 21 and all(cell["pass"] for cell in static_cells) and sweep.get("pass") is True
        native = {
            "schema": "F3R2_V5_LOOP2_R2B_NATIVE_CLEARANCE_RESULTS_V2",
            "timestamp_utc": utc_now(),
            "exact_top_configurations": list(TOP_CONFIGURATIONS),
            "solar_states": list(SOLAR_STATES),
            "authorized_q_order": list(AUTHORIZED_POSE_ORDER),
            "service_grasp_q": None,
            "service_grasp_sample_count": 0,
            "expected_static_cell_count": 21,
            "completed_static_cell_count": len(static_cells),
            "static_cells": static_cells,
            "static_matrix_error": static_error,
            "continuous_solar_only_sweep": sweep,
            "comparison_contracts": r2b_comparison_contracts(),
            "expected_zero_volume_contact_whitelist": list(R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST),
            "minimum_nonwhitelist_clearance_mm": MINIMUM_NONWHITELIST_CLEARANCE_MM,
            "any_positive_interference_fails": True,
            "arm_base_invariant_required": True,
            "side_configuration_owner": "SIDE_SLDASM_ONLY",
            "top_level_second_driver_count": 0,
            "camera_visibility_claim_scope": "NATIVE_ENVELOPE_CLEARANCE_PROXY_NOT_CALIBRATED_FOV",
            "harness_claim_scope": "NATIVE_STATIC_AND_SOLAR_SWEEP_ENVELOPE_NOT_FLEXIBLE_CABLE_DYNAMICS",
            "arm_driver_restore": arm_restore,
            "solar_driver_restore": solar_restore,
            "authority_promotion_count": 0,
            "invented_q_count": 0,
            "final_gate_eligible": final_gate_eligible,
            "verdict": "V5_LOOP2_R2B_NATIVE_CLEARANCE_PASS" if final_gate_eligible else "V5_LOOP2_R2B_NATIVE_CLEARANCE_HOLD",
        }
        result["native_evidence"] = native
        closed_docs = close_all_owned(sw, types, pythoncom)
        model = assembly = None
        result["closed_owned_documents"] = closed_docs

        role_dependencies_post = [file_fact(path) for path in role_dependency_paths]
        result["component_bindings"]["role_dependency_facts_post"] = role_dependencies_post
        if file_fact(TOP_ASSEMBLY) != top_pre or file_fact(LOOP1E_RECEIPT) != loop1e_pre or audit_fixed() != fixed_pre or role_dependencies_post != role_dependencies_pre:
            raise GateError("PROTECTED_INPUT_POST_DRIFT", "top/receipt/fixed inputs changed during read-only motion transaction")
        native["protected_pre_equals_post"] = True
        write_json_once(CLEARANCE_RESULTS_JSON, native)
        csv_rows = clearance_csv_rows(native)
        write_csv_once(CLEARANCE_RESULTS_CSV, CLEARANCE_CSV_FIELDS, csv_rows)
        checkpoint = {
            "schema": "F3R2_V5_LOOP2_R2B_CLEARANCE_CHECKPOINT_V2",
            "timestamp_utc": utc_now(),
            "script": file_fact(script),
            "script_copy": file_fact(SCRIPT_COPY),
            "top": file_fact(TOP_ASSEMBLY),
            "loop1e_receipt": file_fact(LOOP1E_RECEIPT),
            "write_once_outputs": [file_fact(CLEARANCE_RESULTS_JSON), file_fact(CLEARANCE_RESULTS_CSV)],
            "native_evidence": native,
            "solidworks": session,
            "closed_owned_documents": closed_docs,
            "document_count_after_close": int(base.value(sw, "GetDocumentCount")),
            "protected_pre_equals_post": True,
            "final_gate_eligible": final_gate_eligible,
            "verdict": "V5_LOOP2_R2B_CLEARANCE_CHECKPOINT_PASS" if final_gate_eligible else "V5_LOOP2_R2B_CLEARANCE_CHECKPOINT_HOLD",
        }
        write_json_once(CHECKPOINT, checkpoint)
        result["checkpoint"] = checkpoint
        return result
    finally:
        if sw is not None and types is not None and pythoncom is not None:
            try:
                close_all_owned(sw, types, pythoncom)
            except Exception:
                pass


def manifest_text() -> str:
    rows = [
        file_fact(TOP_ASSEMBLY),
        file_fact(LOOP1E_RECEIPT),
        file_fact(ACCEPTED_URDF),
        file_fact(POSE_AUTHORITY_REGISTER),
        file_fact(SOLAR_PROMOTION),
        file_fact(SOLAR_INTERFACE_REQUIREMENTS),
        file_fact(DIGITAL_STATE_MACHINE_R2),
        file_fact(SOLAR_STATE_REGISTER_R2),
        file_fact(SCRIPT_COPY),
        file_fact(CLEARANCE_RESULTS_JSON),
        file_fact(CLEARANCE_RESULTS_CSV),
        file_fact(CHECKPOINT),
    ]
    return "# F3R2 V5 Loop2 R2B native-clearance manifest\n" + "\n".join(f"{row['sha256']}  {row['bytes']}  {row['path']}" for row in rows) + "\n"


def validate_complete_outputs(receipt: Dict[str, Any]) -> bool:
    """Cold-reopen validation for an already finalized write-once evidence set."""
    try:
        if not isinstance(receipt, dict) or receipt.get("schema") != "F3R2_V5_LOOP2_R2B_NATIVE_CLEARANCE_RECEIPT_V2":
            return False
        checkpoint = load_json(CHECKPOINT)
        if not validate_checkpoint_payload(checkpoint):
            return False
        if FINAL_MANIFEST.read_text(encoding="utf-8") != manifest_text():
            return False
        exact_facts = (
            ("script", file_fact(Path(__file__))),
            ("script_copy", file_fact(SCRIPT_COPY)),
            ("top", file_fact(TOP_ASSEMBLY)),
            ("loop1e_receipt", file_fact(LOOP1E_RECEIPT)),
            ("accepted_urdf", file_fact(ACCEPTED_URDF)),
            ("pose_authority_register", file_fact(POSE_AUTHORITY_REGISTER)),
            ("checkpoint", file_fact(CHECKPOINT)),
            ("clearance_results_json", file_fact(CLEARANCE_RESULTS_JSON)),
            ("clearance_results_csv", file_fact(CLEARANCE_RESULTS_CSV)),
            ("manifest", file_fact(FINAL_MANIFEST)),
        )
        if any(receipt.get(name) != fact or fact.get("exists") is not True for name, fact in exact_facts):
            return False
        native = checkpoint["native_evidence"]
        recomputed = native_evidence_final_gate(native)
        expected_gate = "PASS_R2B_CLEARANCE_TO_LOOP3" if recomputed else "HOLD_R2B_CLEARANCE_NOT_ELIGIBLE_FOR_FINAL_GATE"
        expected_verdict = "V5_LOOP2_R2B_NATIVE_CLEARANCE_PASS" if recomputed else "V5_LOOP2_R2B_NATIVE_CLEARANCE_HOLD"
        sweep = native["continuous_solar_only_sweep"]
        expected_sweep_summary = {
            "attempted": sweep.get("attempted"),
            "available": sweep.get("available"),
            "pass": sweep.get("pass"),
            "segment_count": sweep.get("segment_count", 0),
        }
        exact_contract = (
            receipt.get("baseline_id") == RUN_ROOT.name
            and receipt.get("exact_top_configurations") == list(TOP_CONFIGURATIONS)
            and receipt.get("solar_states") == list(SOLAR_STATES)
            and receipt.get("authorized_q_order") == list(AUTHORIZED_POSE_ORDER)
            and receipt.get("expected_static_cell_count") == len(SOLAR_STATES) * len(AUTHORIZED_POSE_ORDER)
            and receipt.get("completed_static_cell_count") == native.get("completed_static_cell_count")
            and receipt.get("continuous_solar_only_sweep") == expected_sweep_summary
            and receipt.get("minimum_nonwhitelist_clearance_mm") == MINIMUM_NONWHITELIST_CLEARANCE_MM
            and receipt.get("any_positive_interference_fails") is True
            and receipt.get("expected_zero_volume_contact_whitelist") == list(R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST)
            and receipt.get("side_configuration_owner") == "SIDE_SLDASM_ONLY"
            and receipt.get("top_level_second_driver_count") == 0
            and receipt.get("service_grasp_q") is None
            and receipt.get("service_grasp_sample_count") == 0
            and receipt.get("protected_pre_equals_post") is True
            and receipt.get("authority_promotion_count") == 0
            and receipt.get("invented_service_q_count") == 0
            and receipt.get("arm_base_invariant") is True
            and receipt.get("remaining_holds") == list(EXPLICIT_HOLDS)
            and receipt.get("classification_ceiling") == "COMPETITION_PROTOTYPE_BASELINE"
            and receipt.get("flight_ready") is False
            and receipt.get("launch_qualified") is False
            and receipt.get("final_gate_eligible") is recomputed
            and receipt.get("overall_gate") == expected_gate
            and receipt.get("verdict") == expected_verdict
        )
        return bool(exact_contract)
    except Exception:
        return False


def finalize_checkpoint(checkpoint: Dict[str, Any], static: Dict[str, Any]) -> Dict[str, Any]:
    if not validate_checkpoint_payload(checkpoint):
        raise GateError("CHECKPOINT_RESUME_VALIDATION_FAIL", "Loop2 checkpoint/output facts failed write-once resume validation")
    final_gate_eligible = native_evidence_final_gate(checkpoint["native_evidence"])
    if not FINAL_MANIFEST.exists():
        write_text_once(FINAL_MANIFEST, manifest_text())
    else:
        expected = manifest_text()
        if FINAL_MANIFEST.read_text(encoding="utf-8") != expected:
            raise GateError("FINAL_MANIFEST_DRIFT", "existing final manifest differs from current checkpoint facts")
    receipt = {
        "schema": "F3R2_V5_LOOP2_R2B_NATIVE_CLEARANCE_RECEIPT_V2",
        "timestamp_utc": utc_now(),
        "baseline_id": RUN_ROOT.name,
        "script": file_fact(Path(__file__)),
        "script_copy": file_fact(SCRIPT_COPY),
        "top": file_fact(TOP_ASSEMBLY),
        "loop1e_receipt": file_fact(LOOP1E_RECEIPT),
        "accepted_urdf": file_fact(ACCEPTED_URDF),
        "pose_authority_register": file_fact(POSE_AUTHORITY_REGISTER),
        "checkpoint": file_fact(CHECKPOINT),
        "clearance_results_json": file_fact(CLEARANCE_RESULTS_JSON),
        "clearance_results_csv": file_fact(CLEARANCE_RESULTS_CSV),
        "manifest": file_fact(FINAL_MANIFEST),
        "exact_top_configurations": list(TOP_CONFIGURATIONS),
        "solar_states": list(SOLAR_STATES),
        "authorized_q_order": list(AUTHORIZED_POSE_ORDER),
        "expected_static_cell_count": 21,
        "completed_static_cell_count": checkpoint["native_evidence"]["completed_static_cell_count"],
        "continuous_solar_only_sweep": {
            "attempted": checkpoint["native_evidence"]["continuous_solar_only_sweep"].get("attempted"),
            "available": checkpoint["native_evidence"]["continuous_solar_only_sweep"].get("available"),
            "pass": checkpoint["native_evidence"]["continuous_solar_only_sweep"].get("pass"),
            "segment_count": checkpoint["native_evidence"]["continuous_solar_only_sweep"].get("segment_count", 0),
        },
        "minimum_nonwhitelist_clearance_mm": MINIMUM_NONWHITELIST_CLEARANCE_MM,
        "any_positive_interference_fails": True,
        "expected_zero_volume_contact_whitelist": list(R2B_EXPECTED_ZERO_VOLUME_CONTACT_WHITELIST),
        "side_configuration_owner": "SIDE_SLDASM_ONLY",
        "top_level_second_driver_count": 0,
        "arm_base_invariant": True,
        "service_grasp_q": None,
        "service_grasp_sample_count": 0,
        "protected_pre_equals_post": checkpoint.get("protected_pre_equals_post") is True,
        "authority_promotion_count": 0,
        "invented_service_q_count": 0,
        "final_gate_eligible": final_gate_eligible,
        "overall_gate": "PASS_R2B_CLEARANCE_TO_LOOP3" if final_gate_eligible else "HOLD_R2B_CLEARANCE_NOT_ELIGIBLE_FOR_FINAL_GATE",
        "remaining_holds": static["explicit_holds"],
        "classification_ceiling": "COMPETITION_PROTOTYPE_BASELINE",
        "flight_ready": False,
        "launch_qualified": False,
        "verdict": "V5_LOOP2_R2B_NATIVE_CLEARANCE_PASS" if final_gate_eligible else "V5_LOOP2_R2B_NATIVE_CLEARANCE_HOLD",
    }
    write_json_once(FINAL_RECEIPT, receipt)
    return receipt


def failure_receipt(exc: Exception, phase: str) -> Optional[Dict[str, Any]]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    path = RUN_ROOT / f"13_validation/V5_LOOP2_FAILURE_{stamp}.json"
    payload = {
        "schema": "F3R2_V5_LOOP2_FAILURE_RECEIPT_V1",
        "timestamp_utc": utc_now(),
        "phase": phase,
        "verdict": getattr(exc, "code", "V5_LOOP2_UNEXPECTED_EXCEPTION"),
        "reason": str(exc),
        "detail": getattr(exc, "detail", {}),
        "traceback": traceback.format_exc(),
        "partial_outputs_preserved": [file_fact(path) for path in (CLEARANCE_RESULTS_JSON, CLEARANCE_RESULTS_CSV, CHECKPOINT, FINAL_MANIFEST, FINAL_RECEIPT) if path.is_file()],
        "solidworks_was_not_launched_or_terminated": True,
    }
    try:
        write_json_once(path, payload)
        return file_fact(path)
    except Exception:
        return None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    parser = argparse.ArgumentParser(description="F3R2 V5 Loop2 R2B native clearance fail-closed verifier")
    parser.add_argument("--execute", action="store_true", help="attach to the already-qualified empty Session B only when every static gate is ready")
    parser.add_argument("--self-test", action="store_true", help="run pure filesystem-free contract self-tests only")
    args = parser.parse_args()
    if args.self_test:
        try:
            print(json.dumps(pure_self_test(), ensure_ascii=False, indent=2, allow_nan=False))
            return 0
        except Exception as exc:
            print(json.dumps({"verdict": getattr(exc, "code", "V5_LOOP2_R2B_SELF_TEST_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", {})}, ensure_ascii=False, indent=2, allow_nan=False))
            return 2
    try:
        report = static_audit()
    except Exception as exc:
        print(json.dumps({"verdict": getattr(exc, "code", "V5_LOOP2_STATIC_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc()}, ensure_ascii=False, indent=2))
        return 2
    if not args.execute:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["verdict"] in {"V5_LOOP2_R2B_SCRIPT_READY_LOOP1E_INPUTS_PENDING", "V5_LOOP2_R2B_STATIC_EXECUTION_READY", "V5_LOOP2_R2B_STATIC_ALREADY_COMPLETE"} else 2
    if not report.get("execution_authorized"):
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 3
    phase = "RESUME_FINALIZE" if report["output_state"]["state"] == "RESUME_FINALIZE" else "NATIVE_TRANSACTION"
    try:
        if phase == "RESUME_FINALIZE":
            checkpoint = load_json(CHECKPOINT)
        else:
            transaction = execute_native(report)
            checkpoint = transaction["checkpoint"]
        receipt = finalize_checkpoint(checkpoint, report)
        print(json.dumps({"verdict": receipt["verdict"], "overall_gate": receipt["overall_gate"], "receipt": file_fact(FINAL_RECEIPT), "solidworks_launched_or_terminated": False}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        failed = failure_receipt(exc, phase)
        print(json.dumps({"verdict": getattr(exc, "code", "V5_LOOP2_UNEXPECTED_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", {}), "failure_receipt": failed, "traceback": traceback.format_exc()}, ensure_ascii=False, indent=2))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
