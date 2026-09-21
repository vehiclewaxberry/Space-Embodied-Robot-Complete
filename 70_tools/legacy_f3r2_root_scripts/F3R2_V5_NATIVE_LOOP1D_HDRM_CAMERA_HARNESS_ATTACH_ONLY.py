#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Loop-1D HDRM, camera-interface and static-harness native CAD.

This is a write-once, checkpointed SolidWorks 2024 automation program.  The
only application attachment path is the pinned Loop-1 helper's
``attach_empty_session`` function.  Importing this module and running the
``audit`` command are COM-free.  ``execute`` creates only the explicitly
listed Loop-1D artifacts below, all inside the unique claimed V5 root.

The HDRM geometry is a competition-demonstrator functional envelope, not a
flight-qualified release mechanism.  The six named configurations are
mutually-exclusive state proxies of one physical latch (BOM quantity one).
The camera remains unselected.  The harness closes only the OD9 static route;
moving-sweep closure remains on HOLD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base
import F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY as loop1a


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
RUN_ID = "20260810T000300_V5NATIVE"
RUN_ROOT = ENGINEERING / f"F3R2_V5_NATIVE_MECHANICAL_RELEASE_{RUN_ID}"
G0_RUN = ENGINEERING / "_MFINAL_G0_SMOKE_20260809T172928_P4E8"

BASE_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
LOOP1A_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY.py"
BASE_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
LOOP1A_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY.py"
G0_READY = G0_RUN / "G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json"
G0_CLAIM = G0_RUN / "G0_V5_EXCLUSIVE_RUN_CLAIM.json"
IMPORT_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
LOOP1A_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1A_SUBASSEMBLY_RECEIPT.json"
LOOP1A_MANIFEST = RUN_ROOT / "14_release/V5_LOOP1A_SUBASSEMBLY_MANIFEST_SHA256.txt"
AUTHORITY_RECEIPT = RUN_ROOT / "13_validation/V5_AUTHORITY_SEED_RECEIPT.json"
HDRM_AUTHORITY = RUN_ROOT / "00_authority/V5_HDRM_AUTHORITY.yaml"
CAMERA_AUTHORITY = RUN_ROOT / "00_authority/SERVICE_CAMERA_DOWNSELECT.md"

# These installed templates were already runtime-proven in the same Session-B
# process by Loop1A.  Their exact bytes are pinned again here.
PART_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot")
ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")

FIXED_INPUTS: Tuple[Tuple[Path, str, int], ...] = (
    (BASE_HELPER, "1F589D3FAE23D64F2364B1CE98FA232A1AA19648398521E55CB5C7F85D0B6062", 53675),
    (LOOP1A_HELPER, "25369CB867685EBA0C374636F8F540867D3D8B5890F9CE8622A6842E6518EC42", 63256),
    (BASE_HELPER_COPY, "1F589D3FAE23D64F2364B1CE98FA232A1AA19648398521E55CB5C7F85D0B6062", 53675),
    (LOOP1A_HELPER_COPY, "25369CB867685EBA0C374636F8F540867D3D8B5890F9CE8622A6842E6518EC42", 63256),
    (G0_READY, "58F8240B1D158867C1B61B09B4A098F5AB670141A3CFEE983F5AD2A637CA5CA6", 7725),
    (G0_CLAIM, "9495D83FC6682F2B8BF67638189C637DC7C981755D06DE3B9098967CA2DDE8AF", 420),
    (IMPORT_RECEIPT, "9FC8D1DBBBDD7D1FE37F5FCCA4359838827282A0D7A961D8EEB511E75BE7160D", 47201),
    (LOOP1A_RECEIPT, "F946A361A7CFF8143753853911F23178AF68592D2F7BBE09990575ED86E9BF49", 131323),
    (LOOP1A_MANIFEST, "5F0E03E49424DCB832D9B2A992459C23053F0CB96963E7CEBEFCF4810DF7C20D", 1684),
    (AUTHORITY_RECEIPT, "7251758420639907CAB4F4C134A278B0F860535BCC62A8E264E6862B7ECBED0F", 6453),
    (HDRM_AUTHORITY, "824DB1B34C1802646675450BE15174CF04D660640AD88E89AA42C92DC8C0968F", 766),
    (CAMERA_AUTHORITY, "55CBB868F50C48B5D6A0E369462E2B26487AD5293972CA0DD85B138297D497D1", 1992),
    (PART_TEMPLATE, "5DA21678EFE07EF465770630BEB4FFE540F23D47FCA07715F74D2AFDBEA87271", 39256),
    (ASSEMBLY_TEMPLATE, "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC", 34942),
)

IMPORTED_BASELINES: Tuple[Tuple[Path, str, int], ...] = (
    (RUN_ROOT / "01_native_parts/hdrm/ARM_HDRM_RELEASE_SWEEP_ENVELOPE.SLDPRT", "AC90D4FB3FAA6888198255922D0128E4C7B8702467FD3DA266B9A433BCEFAE42", 50110),
    (RUN_ROOT / "01_native_parts/hdrm/ARM_HDRM_60MM_MOUNT_ENVELOPE.SLDPRT", "ED08F4BD92F41CD42A92C6D3F497C0570A1B842DA8A79F74ED03AF223A3A95D6", 51287),
    (RUN_ROOT / "01_native_parts/camera_harness/SERVICE_CAMERA_ENVELOPE.SLDPRT", "2C9BFCC330A4EEEAE8F7FF062F090E580D393494007F9BE68BC5BC09523E613C", 52976),
    (RUN_ROOT / "01_native_parts/camera_harness/B601_OD9_STATIC_HARNESS_ENVELOPE.SLDPRT", "3E08F338C6BC7380C8D34CD8BEE748312EDC1A8687DDB2C735176A912A2CE301", 155676),
)

SW_MATE_LOCK = 16
SW_ALIGN_CLOSEST = 2
SW_ADD_MATE_NO_ERROR = 1
SW_COMPONENT_SUPPRESSED = 0
SW_COMPONENT_RESOLVED = 2
SW_BODY_SOLID = 0
CONFIGS_HDRM = (
    "LOCKED",
    "RELEASE_ARMED",
    "RELEASE_START",
    "RELEASED",
    "RELEASE_FAILED",
    "GROUND_UNLOCK",
)

NATIVE_PART_DIR = RUN_ROOT / "01_native_parts/loop1d_functional"
SUBASSEMBLY_DIR = RUN_ROOT / "02_native_subassemblies"


def _part(name: str) -> Path:
    return NATIVE_PART_DIR / f"{name}.SLDPRT"


PART_SPECS: Dict[str, Dict[str, Any]] = {
    "ARM_HDRM_LOAD_TRANSFER_BASE": {
        "target": _part("ARM_HDRM_LOAD_TRANSFER_BASE"),
        "geometry": {"kind": "annulus_holes", "outer_r_mm": 30.0, "inner_r_mm": 12.0, "depth_mm": 10.0, "holes": [(24.0, 0.0, 2.1), (0.0, 24.0, 2.1), (-24.0, 0.0, 2.1), (0.0, -24.0, 2.1)]},
        "expected_sorted_mm": [10.0, 60.0, 60.0],
        "local_center_mm": [0.0, 0.0, 5.0],
        "properties": {"FUNCTION": "PHYSICAL_MOUNT_AND_LOAD_TRANSFER", "MOUNT_PATTERN": "4X_D4.2_PCD48", "MOUNT_ENVELOPE": "D60"},
    },
    "ARM_HDRM_LATCH_SLIDER": {
        "target": _part("ARM_HDRM_LATCH_SLIDER"),
        "geometry": {"kind": "box", "width_mm": 16.0, "height_mm": 16.0, "depth_mm": 14.0},
        "expected_sorted_mm": [14.0, 16.0, 16.0],
        "local_center_mm": [0.0, 0.0, 7.0],
        "properties": {"FUNCTION": "ONE_PHYSICAL_LATCH_SIX_MUTUALLY_EXCLUSIVE_STATE_PROXIES", "PHYSICAL_BOM_QTY": "1", "NOMINAL_STROKE_MM": "6"},
    },
    "ARM_HDRM_HARD_STOP": {
        "target": _part("ARM_HDRM_HARD_STOP"),
        "geometry": {"kind": "box", "width_mm": 20.0, "height_mm": 20.0, "depth_mm": 4.0},
        "expected_sorted_mm": [4.0, 20.0, 20.0],
        "local_center_mm": [0.0, 0.0, 2.0],
        "properties": {"FUNCTION": "PHYSICAL_POSITIVE_HARD_STOP", "PRELOAD_FACE_DIRECTION": "+X", "MOUNTING_TO_BASE": "NATIVE_LOCK_MATE_FASTENER_DETAIL_HOLD"},
    },
    "ARM_HDRM_SENSOR_MOUNT": {
        "target": _part("ARM_HDRM_SENSOR_MOUNT"),
        "geometry": {"kind": "box", "width_mm": 12.0, "height_mm": 12.0, "depth_mm": 6.0},
        "expected_sorted_mm": [6.0, 12.0, 12.0],
        "local_center_mm": [0.0, 0.0, 3.0],
        "properties": {"FUNCTION": "PHYSICAL_RELEASE_STATE_SENSOR_MOUNT", "SENSOR_SELECTION": "HOLD"},
    },
    "ARM_HDRM_CONNECTOR_MOUNT": {
        "target": _part("ARM_HDRM_CONNECTOR_MOUNT"),
        "geometry": {"kind": "plate_holes", "width_mm": 20.0, "height_mm": 16.0, "depth_mm": 6.0, "holes": [(0.0, 0.0, 5.0)]},
        "expected_sorted_mm": [6.0, 16.0, 20.0],
        "local_center_mm": [0.0, 0.0, 3.0],
        "properties": {"FUNCTION": "PHYSICAL_ELECTRICAL_CONNECTOR_MOUNT", "CONNECTOR_PORT": "D10_ENVELOPE", "CONNECTOR_SELECTION": "HOLD"},
    },
    "SERVICE_CAMERA_INTERFACE_BRACKET": {
        "target": _part("SERVICE_CAMERA_INTERFACE_BRACKET"),
        "geometry": {"kind": "plate_holes", "width_mm": 50.0, "height_mm": 40.0, "depth_mm": 4.0, "holes": [(-11.0, 0.0, 1.35), (11.0, 0.0, 1.35)]},
        "expected_sorted_mm": [4.0, 40.0, 50.0],
        "local_center_mm": [0.0, 0.0, 2.0],
        "properties": {"FUNCTION": "NATIVE_CAMERA_INTERFACE_BRACKET", "HOLE_PATTERN": "2X_D2.7_SPACING22", "MOUNT_CONTACT_RADIUS_MM": "28.5", "SERVICE_CAMERA": "UNSELECTED"},
    },
    "SERVICE_CAMERA_OPTICAL_FRAME_MARKER": {
        "target": _part("SERVICE_CAMERA_OPTICAL_FRAME_MARKER"),
        "geometry": {"kind": "cylinder", "radius_mm": 2.0, "depth_mm": 20.0},
        "expected_sorted_mm": [4.0, 4.0, 20.0],
        "local_center_mm": [0.0, 0.0, 10.0],
        "properties": {"FUNCTION": "PROVISIONAL_OPTICAL_FRAME_MARKER", "CANDIDATE_TILT_DEG": "15", "CAMERA_MODEL_SELECTION": "HOLD"},
    },
    "B601_OD9_HARNESS_CLAMP": {
        "target": _part("B601_OD9_HARNESS_CLAMP"),
        "geometry": {"kind": "plate_holes", "width_mm": 20.0, "height_mm": 16.0, "depth_mm": 6.0, "holes": [(0.0, 0.0, 5.0)]},
        "expected_sorted_mm": [6.0, 16.0, 20.0],
        "local_center_mm": [0.0, 0.0, 3.0],
        "properties": {"FUNCTION": "NATIVE_STATIC_HARNESS_CLAMP", "HARNESS_OD_MM": "9", "RADIAL_CLEARANCE_MM": "0.5"},
    },
    "B601_HARNESS_SERVICE_LOOP_ENVELOPE": {
        "target": _part("B601_HARNESS_SERVICE_LOOP_ENVELOPE"),
        "geometry": {"kind": "annulus_holes", "outer_r_mm": 34.5, "inner_r_mm": 25.5, "depth_mm": 9.0, "holes": []},
        "expected_sorted_mm": [9.0, 69.0, 69.0],
        "local_center_mm": [0.0, 0.0, 4.5],
        "properties": {"FUNCTION": "NATIVE_STATIC_SERVICE_LOOP_ENVELOPE", "HARNESS_OD_MM": "9", "CENTERLINE_RADIUS_MM": "30", "MIN_STATIC_BEND_RADIUS_MM": "25", "STATIC_MARGIN_MM": "5", "MOVING_SWEEP": "HOLD"},
    },
}

HDRM_ASM = SUBASSEMBLY_DIR / "ARM_HDRM_FUNCTIONAL_ENVELOPE.SLDASM"
CAMERA_ASM = SUBASSEMBLY_DIR / "SERVICE_CAMERA_INTERFACE_HOLD.SLDASM"
HARNESS_ASM = SUBASSEMBLY_DIR / "B601_HARNESS_STATIC_INTERFACE_HOLD.SLDASM"

ASSEMBLY_SPECS: Dict[str, Dict[str, Any]] = {
    "ARM_HDRM_FUNCTIONAL_ENVELOPE": {
        "target": HDRM_ASM,
        "configs": list(CONFIGS_HDRM),
        "state_roles": {name: f"HDRM_LATCH_{name}" for name in CONFIGS_HDRM},
        "components": [
            {"role": "HDRM_BASE", "path": _part("ARM_HDRM_LOAD_TRANSFER_BASE"), "fixed": True, "center_mm": [0.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 5.0]},
            {"role": "HDRM_MOUNT_ENVELOPE_REFERENCE", "path": RUN_ROOT / "01_native_parts/hdrm/ARM_HDRM_60MM_MOUNT_ENVELOPE.SLDPRT", "fixed": False, "center_mm": [0.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 150.0]},
            {"role": "HDRM_RELEASE_SWEEP_REFERENCE", "path": RUN_ROOT / "01_native_parts/hdrm/ARM_HDRM_RELEASE_SWEEP_ENVELOPE.SLDPRT", "fixed": False, "center_mm": [-3.0, 0.0, 150.0], "local_center_mm": [-3.0, 0.0, 150.0]},
            {"role": "HDRM_HARD_STOP", "path": _part("ARM_HDRM_HARD_STOP"), "fixed": False, "center_mm": [17.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 2.0]},
            {"role": "HDRM_SENSOR_MOUNT", "path": _part("ARM_HDRM_SENSOR_MOUNT"), "fixed": False, "center_mm": [8.0, 22.0, 150.0], "local_center_mm": [0.0, 0.0, 3.0]},
            {"role": "HDRM_CONNECTOR_MOUNT", "path": _part("ARM_HDRM_CONNECTOR_MOUNT"), "fixed": False, "center_mm": [8.0, -22.0, 150.0], "local_center_mm": [0.0, 0.0, 3.0]},
            {"role": "HDRM_LATCH_LOCKED", "path": _part("ARM_HDRM_LATCH_SLIDER"), "fixed": False, "center_mm": [8.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 7.0]},
            {"role": "HDRM_LATCH_RELEASE_ARMED", "path": _part("ARM_HDRM_LATCH_SLIDER"), "fixed": False, "center_mm": [8.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 7.0]},
            {"role": "HDRM_LATCH_RELEASE_START", "path": _part("ARM_HDRM_LATCH_SLIDER"), "fixed": False, "center_mm": [7.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 7.0]},
            {"role": "HDRM_LATCH_RELEASED", "path": _part("ARM_HDRM_LATCH_SLIDER"), "fixed": False, "center_mm": [2.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 7.0]},
            {"role": "HDRM_LATCH_RELEASE_FAILED", "path": _part("ARM_HDRM_LATCH_SLIDER"), "fixed": False, "center_mm": [6.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 7.0]},
            {"role": "HDRM_LATCH_GROUND_UNLOCK", "path": _part("ARM_HDRM_LATCH_SLIDER"), "fixed": False, "center_mm": [8.0, 0.0, 156.0], "local_center_mm": [0.0, 0.0, 7.0]},
        ],
        "mate_pairs": [("HDRM_BASE", role) for role in ("HDRM_MOUNT_ENVELOPE_REFERENCE", "HDRM_RELEASE_SWEEP_REFERENCE", "HDRM_HARD_STOP", "HDRM_SENSOR_MOUNT", "HDRM_CONNECTOR_MOUNT", *(f"HDRM_LATCH_{name}" for name in CONFIGS_HDRM))],
        "properties": {
            "RELEASE_SCOPE": "COMPETITION_DEMONSTRATOR_FUNCTIONAL_ENVELOPE",
            "PRELOAD_DIRECTION": "+X",
            "OPERATIONAL_RELEASE_DIRECTION": "-X",
            "GROUND_UNLOCK_DIRECTION": "+Z",
            "NOMINAL_STROKE_MM": "6",
            "CANDIDATE_PRELOAD_FORCE_N": "50_NOT_VERIFIED",
            "PHYSICAL_MOUNT_LOAD_TRANSFER_HARD_STOP_SENSOR_CONNECTOR": "PRESENT",
            "STATE_PROXY_DISCLOSURE": "SIX_MUTUALLY_EXCLUSIVE_OCCURRENCES_ONE_PHYSICAL_LATCH_BOM_QTY_1",
            "FLIGHT_QUALIFICATION": "HOLD",
        },
    },
    "SERVICE_CAMERA_INTERFACE_HOLD": {
        "target": CAMERA_ASM,
        "configs": ["MODEL_SELECTION_HOLD"],
        "state_roles": {},
        "components": [
            {"role": "CAMERA_BRACKET", "path": _part("SERVICE_CAMERA_INTERFACE_BRACKET"), "fixed": True, "center_mm": [0.0, -46.0, 43.0], "local_center_mm": [0.0, 0.0, 2.0]},
            {"role": "CAMERA_ENVELOPE_UNSELECTED", "path": RUN_ROOT / "01_native_parts/camera_harness/SERVICE_CAMERA_ENVELOPE.SLDPRT", "fixed": False, "center_mm": [0.0, -46.0, 58.0], "local_center_mm": [0.0, -46.0, 58.0]},
            {"role": "CAMERA_OPTICAL_FRAME", "path": _part("SERVICE_CAMERA_OPTICAL_FRAME_MARKER"), "fixed": False, "center_mm": [0.0, -46.0, 81.0], "local_center_mm": [0.0, 0.0, 10.0], "rotation_x_deg": 15.0},
        ],
        "mate_pairs": [("CAMERA_BRACKET", "CAMERA_ENVELOPE_UNSELECTED"), ("CAMERA_BRACKET", "CAMERA_OPTICAL_FRAME")],
        "properties": {"SERVICE_CAMERA": "UNSELECTED", "CAMERA_MODEL_SELECTION": "HOLD", "FROZEN_NATIVE_CONTENT": "BRACKET_INTERFACE_ENVELOPE_OPTICAL_FRAME", "MOUNT_CONTACT_RADIUS_MM": "28.5", "CANDIDATE_TILT_DEG": "15", "FLIGHT_QUALIFICATION": "HOLD"},
    },
    "B601_HARNESS_STATIC_INTERFACE_HOLD": {
        "target": HARNESS_ASM,
        "configs": ["STATIC_ROUTE_OD9_HOLD"],
        "state_roles": {},
        "components": [
            {"role": "OD9_STATIC_ENVELOPE", "path": RUN_ROOT / "01_native_parts/camera_harness/B601_OD9_STATIC_HARNESS_ENVELOPE.SLDPRT", "fixed": True, "center_mm": [193.0, 0.0, -35.0], "local_center_mm": [193.0, 0.0, -35.0]},
            {"role": "OD9_CLAMP_A", "path": _part("B601_OD9_HARNESS_CLAMP"), "fixed": False, "center_mm": [170.0, 0.0, -3.0], "local_center_mm": [0.0, 0.0, 3.0], "rotation_x_deg": 90.0},
            {"role": "OD9_CLAMP_B", "path": _part("B601_OD9_HARNESS_CLAMP"), "fixed": False, "center_mm": [216.0, 0.0, -67.0], "local_center_mm": [0.0, 0.0, 3.0], "rotation_x_deg": 90.0},
            {"role": "OD9_SERVICE_LOOP", "path": _part("B601_HARNESS_SERVICE_LOOP_ENVELOPE"), "fixed": False, "center_mm": [193.0, 0.0, -35.0], "local_center_mm": [0.0, 0.0, 4.5], "rotation_x_deg": 90.0},
        ],
        "mate_pairs": [("OD9_STATIC_ENVELOPE", "OD9_CLAMP_A"), ("OD9_STATIC_ENVELOPE", "OD9_CLAMP_B"), ("OD9_STATIC_ENVELOPE", "OD9_SERVICE_LOOP")],
        "properties": {"STATIC_NATIVE_ENVELOPE": "OD9", "NATIVE_CLAMPS": "2", "SERVICE_LOOP_CENTERLINE_RADIUS_MM": "30", "MIN_STATIC_BEND_RADIUS_MM": "25", "STATIC_BEND_RADIUS_MARGIN_MM": "5", "MOVING_SWEEP": "HOLD", "DYNAMIC_BEND_TORSION_FLEX_LIFE": "HOLD"},
    },
}

# Coordinate ownership consumed by Loop1E.  CAMERA is a wrist-side/link-6
# interface by the fixed camera authority, while HDRM and the OD9 static route
# retain the already-positioned spacecraft/world coordinates proven by the
# Loop1 neutral cold B-rep bboxes.  Receipt generation below recomputes the
# complete assembly B-rep extrema in a cold read-only reopen and records the
# fixed component datum transform; these strings alone can never authorize a
# placement.
FRAME_CONTRACT_POLICY: Dict[str, Dict[str, str]] = {
    "CAMERA": {
        "assembly": "SERVICE_CAMERA_INTERFACE_HOLD",
        "source_frame": "LINK6_LOCAL",
        "placement": "LIVE_LINK6_TOTAL_TRANSFORM",
        "fixed_role": "CAMERA_BRACKET",
        "frame_rationale": "Fixed authority defines a wrist-side candidate interface; cold B-rep and fixed bracket datum are expressed in the link-6 attachment frame, not inferred from a filename.",
    },
    "HDRM": {
        "assembly": "ARM_HDRM_FUNCTIONAL_ENVELOPE",
        "source_frame": "SPACECRAFT_WORLD",
        "placement": "IDENTITY",
        "fixed_role": "HDRM_BASE",
        "frame_rationale": "Loop1 cold B-rep witnesses at the controlled arm restraint station already carry spacecraft/world placement; a second B601 mount transform is prohibited.",
    },
    "HARNESS": {
        "assembly": "B601_HARNESS_STATIC_INTERFACE_HOLD",
        "source_frame": "SPACECRAFT_WORLD",
        "placement": "IDENTITY",
        "fixed_role": "OD9_STATIC_ENVELOPE",
        "frame_rationale": "Loop1 cold B-rep OD9 route spans the accepted spacecraft/world stations x=166.5..219.5 mm and therefore remains identity placed.",
    },
}

# All native HDRM primitives are sketched on the Front Plane and rotated as a
# group so their extrusion thickness is global X and the D60 annulus occupies
# the same YZ interface frame as the pinned 60 mm mount envelope.  The two
# already-native reference envelopes retain their proven global frame.
for _hdrm_component in ASSEMBLY_SPECS["ARM_HDRM_FUNCTIONAL_ENVELOPE"]["components"]:
    if _hdrm_component["role"] not in {"HDRM_MOUNT_ENVELOPE_REFERENCE", "HDRM_RELEASE_SWEEP_REFERENCE"}:
        _hdrm_component["rotation_y_deg"] = 90.0

PART_CHECKPOINTS = {name: RUN_ROOT / f"13_validation/V5_LOOP1D0_CHECKPOINT_{name}.json" for name in PART_SPECS}
ASSEMBLY_CHECKPOINTS = {name: RUN_ROOT / f"13_validation/V5_LOOP1D1_CHECKPOINT_{name}.json" for name in ASSEMBLY_SPECS}
FINAL_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json"
FINAL_MANIFEST = RUN_ROOT / "14_release/V5_LOOP1D_HDRM_CAMERA_HARNESS_MANIFEST_SHA256.txt"
SCRIPT_COPY = RUN_ROOT / "99_tools" / Path(__file__).name

NON_COVERAGE = [
    "HDRM_FLIGHT_ACTUATOR_PRODUCT_VENDOR_SELECTION",
    "HDRM_FORCE_CURRENT_THERMAL_DUTY_RELIABILITY_SHOCK_VIBRATION_OR_FLIGHT_QUALIFICATION",
    "HDRM_FINAL_MATING_BREP_CLOCKING_TOLERANCE_FASTENER_PRELOAD_OR_PHYSICAL_50N_TEST",
    "CAMERA_MODEL_VENDOR_BODY_CAD_MASS_COM_CONNECTOR_DRIVER_INTRINSICS_FOV_CALIBRATION_OR_OCCLUSION",
    "HARNESS_MOVING_SWEEP_DYNAMIC_BEND_TORSION_FLEX_LIFE_EMC_OR_CONNECTOR_PINOUT",
    "GLOBAL_TOP_LEVEL_INTEGRATION_INTERFERENCE_CLEARANCE_FEA_MASS_BOM_DRAWINGS_OR_PACK_AND_GO",
]


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return base.sha256(path)


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise GateError("JSON_ROOT_FAIL", "JSON root is not an object", {"path": norm(path)})
    return payload


def file_fact(path: Path) -> Dict[str, Any]:
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_json_once(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def fixed_file_audit(path: Path, expected_sha: str, expected_bytes: int) -> Dict[str, Any]:
    exists = path.is_file()
    actual_bytes = path.stat().st_size if exists else None
    actual_sha = sha256(path) if exists else None
    return {
        "path": norm(path),
        "expected_bytes": expected_bytes,
        "actual_bytes": actual_bytes,
        "expected_sha256": expected_sha,
        "actual_sha256": actual_sha,
        "pass": exists and actual_bytes == expected_bytes and actual_sha == expected_sha,
    }


def parse_loop1a_manifest() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw in LOOP1A_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        fields = raw.split("  ", 2)
        if len(fields) != 3:
            raise GateError("LOOP1A_MANIFEST_PARSE_FAIL", "manifest row is not SHA/bytes/path", {"row": raw})
        expected_sha, expected_bytes_text, relative = fields
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise GateError("LOOP1A_MANIFEST_PATH_FAIL", "manifest path escapes V5", {"path": relative})
        path = RUN_ROOT / relative_path
        rows.append(fixed_file_audit(path, expected_sha, int(expected_bytes_text)))
    if len(rows) != 13 or not all(row["pass"] for row in rows):
        raise GateError("LOOP1A_MANIFEST_DRIFT", "Loop1A manifest does not prove exactly 13 immutable artifacts", {"rows": rows})
    return rows


def registered_import_parts(receipt: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in receipt.get("native_parts", []):
        target = item.get("target", {})
        path = Path(str(target.get("path", ""))).resolve()
        if RUN_ROOT.resolve() not in path.parents:
            raise GateError("IMPORT_PART_OUTSIDE_V5", "registered part is outside the unique V5 root", {"path": str(path)})
        rows.append(fixed_file_audit(path, str(target.get("sha256", "")), int(target.get("bytes", -1))))
    if len(rows) != 20 or len({row["path"] for row in rows}) != 20 or not all(row["pass"] for row in rows):
        raise GateError("IMPORT_PART_CONTRACT_DRIFT", "20-part imported native contract drifted", {"rows": rows})
    return sorted(rows, key=lambda row: row["path"])


def engineering_contract_audit() -> Dict[str, Any]:
    hdrm = ASSEMBLY_SPECS["ARM_HDRM_FUNCTIONAL_ENVELOPE"]
    by_role = expected_component_map(hdrm)
    locked = [float(value) for value in by_role["HDRM_LATCH_LOCKED"]["center_mm"]]
    expected_centers = {
        "HDRM_LATCH_RELEASE_ARMED": locked,
        "HDRM_LATCH_RELEASE_START": [locked[0] - 1.0, locked[1], locked[2]],
        "HDRM_LATCH_RELEASED": [locked[0] - 6.0, locked[1], locked[2]],
        "HDRM_LATCH_RELEASE_FAILED": [locked[0] - 2.0, locked[1], locked[2]],
        "HDRM_LATCH_GROUND_UNLOCK": [locked[0], locked[1], locked[2] + 6.0],
    }
    for role, expected in expected_centers.items():
        actual = [float(value) for value in by_role[role]["center_mm"]]
        if actual != expected:
            raise GateError("HDRM_STATE_VECTOR_FAIL", "HDRM state proxy does not preserve the controlled direction/stroke", {"role": role, "expected_mm": expected, "actual_mm": actual})
    hard_stop_center_x = float(by_role["HDRM_HARD_STOP"]["center_mm"][0])
    locked_positive_face_x = locked[0] + 7.0
    hard_stop_negative_face_x = hard_stop_center_x - 2.0
    sensor_negative_face_x = float(by_role["HDRM_SENSOR_MOUNT"]["center_mm"][0]) - 3.0
    connector_negative_face_x = float(by_role["HDRM_CONNECTOR_MOUNT"]["center_mm"][0]) - 3.0
    if hard_stop_negative_face_x != locked_positive_face_x or sensor_negative_face_x != 5.0 or connector_negative_face_x != 5.0:
        raise GateError("HDRM_PHYSICAL_INTERFACE_FAIL", "hard-stop contact or sensor/connector base-face mounting geometry drifted", {"locked_positive_face_x_mm": locked_positive_face_x, "hard_stop_negative_face_x_mm": hard_stop_negative_face_x, "sensor_negative_face_x_mm": sensor_negative_face_x, "connector_negative_face_x_mm": connector_negative_face_x})
    if tuple(hdrm["configs"]) != CONFIGS_HDRM or set(hdrm["state_roles"]) != set(CONFIGS_HDRM):
        raise GateError("HDRM_CONFIGURATION_CONTRACT_FAIL", "HDRM configuration names/state map drifted")

    camera = ASSEMBLY_SPECS["SERVICE_CAMERA_INTERFACE_HOLD"]
    camera_roles = expected_component_map(camera)
    bracket_top = float(camera_roles["CAMERA_BRACKET"]["center_mm"][2]) + 2.0
    envelope_bottom = float(camera_roles["CAMERA_ENVELOPE_UNSELECTED"]["center_mm"][2]) - 13.0
    if camera["configs"] != ["MODEL_SELECTION_HOLD"] or bracket_top != 45.0 or envelope_bottom != 45.0 or float(camera_roles["CAMERA_OPTICAL_FRAME"].get("rotation_x_deg", 0.0)) != 15.0:
        raise GateError("CAMERA_INTERFACE_CONTRACT_FAIL", "camera bracket/envelope/optical-frame hold contract drifted", {"bracket_top_mm": bracket_top, "envelope_bottom_mm": envelope_bottom})

    harness = ASSEMBLY_SPECS["B601_HARNESS_STATIC_INTERFACE_HOLD"]
    harness_roles = expected_component_map(harness)
    if harness["configs"] != ["STATIC_ROUTE_OD9_HOLD"] or any(float(harness_roles[role].get("rotation_x_deg", 0.0)) != 90.0 for role in ("OD9_CLAMP_A", "OD9_CLAMP_B", "OD9_SERVICE_LOOP")):
        raise GateError("HARNESS_STATIC_INTERFACE_CONTRACT_FAIL", "OD9 clamp/service-loop static frame drifted")
    loop_properties = PART_SPECS["B601_HARNESS_SERVICE_LOOP_ENVELOPE"]["properties"]
    if float(loop_properties["CENTERLINE_RADIUS_MM"]) != 30.0 or float(loop_properties["MIN_STATIC_BEND_RADIUS_MM"]) != 25.0 or loop_properties["MOVING_SWEEP"] != "HOLD":
        raise GateError("HARNESS_BEND_RADIUS_CONTRACT_FAIL", "static service-loop radius or moving-sweep HOLD drifted")
    return {
        "hdrm_preload_direction": "+X",
        "hdrm_operational_release_direction": "-X",
        "hdrm_ground_unlock_direction": "+Z",
        "hdrm_stroke_mm": 6.0,
        "hdrm_hard_stop_contact_x_mm": 15.0,
        "hdrm_sensor_connector_base_face_x_mm": 5.0,
        "camera_bracket_envelope_contact_z_mm": 45.0,
        "camera_model_selection": "HOLD",
        "harness_od_mm": 9.0,
        "harness_static_centerline_radius_mm": 30.0,
        "harness_min_static_bend_radius_mm": 25.0,
        "harness_moving_sweep": "HOLD",
        "pass": True,
    }


def unique_authority_capture(text: str, pattern: str, label: str) -> str:
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    if len(matches) != 1:
        raise GateError(
            "AUTHORITY_FIELD_CARDINALITY_FAIL",
            "authority field must occur exactly once",
            {"field": label, "match_count": len(matches)},
        )
    captured = matches[0]
    if isinstance(captured, tuple):
        raise GateError("AUTHORITY_CAPTURE_SHAPE_FAIL", "authority scalar capture returned multiple groups", {"field": label})
    return str(captured).strip()


def parse_vector_authority(text: str, key: str) -> Tuple[float, float, float]:
    raw = unique_authority_capture(
        text,
        rf"^  {re.escape(key)}:\s*\[([^\]]+)\]\s*$",
        f"directions.{key}",
    )
    fields = [field.strip() for field in raw.split(",")]
    if len(fields) != 3:
        raise GateError("AUTHORITY_VECTOR_SHAPE_FAIL", "authority direction is not a three-vector", {"field": key, "raw": raw})
    try:
        return tuple(float(field) for field in fields)  # type: ignore[return-value]
    except ValueError as exc:
        raise GateError("AUTHORITY_VECTOR_VALUE_FAIL", "authority direction contains a non-numeric value", {"field": key, "raw": raw}) from exc


def parse_hdrm_authority(text: str) -> Dict[str, Any]:
    schema = unique_authority_capture(text, r"^schema:\s*(\S+)\s*$", "schema")
    designation = unique_authority_capture(text, r"^designation:\s*(\S+)\s*$", "designation")
    scope = unique_authority_capture(text, r"^scope:\s*(\S+)\s*$", "scope")
    mechanism = unique_authority_capture(text, r"^mechanism_route:\s*(\S+)\s*$", "mechanism_route")
    physical_status = unique_authority_capture(text, r"^physical_status:\s*(\S+)\s*$", "physical_status")
    stroke_raw = unique_authority_capture(text, r"^release_stroke_candidate_mm:\s*([^\s]+)\s*$", "release_stroke_candidate_mm")
    preload_raw = unique_authority_capture(text, r"^working_preload_candidate_N:\s*([^\s]+)\s*$", "working_preload_candidate_N")
    states_raw = unique_authority_capture(text, r"^required_native_states:\s*\[([^\]]+)\]\s*$", "required_native_states")
    try:
        stroke_mm = float(stroke_raw)
        preload_n = float(preload_raw)
    except ValueError as exc:
        raise GateError("AUTHORITY_SCALAR_VALUE_FAIL", "HDRM stroke/preload authority is not numeric", {"stroke": stroke_raw, "preload": preload_raw}) from exc
    states = tuple(field.strip() for field in states_raw.split(",") if field.strip())
    directions = {
        "preload": parse_vector_authority(text, "preload"),
        "operational_release": parse_vector_authority(text, "operational_release"),
        "ground_removal_unlock": parse_vector_authority(text, "ground_removal_unlock"),
    }
    holds = tuple(re.findall(r"^  - ([A-Z0-9_]+)\s*$", text, flags=re.MULTILINE))
    expected_holds = (
        "FLIGHT_ACTUATOR_PROCUREMENT_TBD",
        "PRODUCT_FORCE_CURRENT_THERMAL_DUTY_TBD",
        "MATING_BREP_AND_CLOCKING_TBD",
        "PHYSICAL_RELEASE_TEST_TBD",
        "FLIGHT_QUALIFICATION_HOLD",
    )
    if (
        schema != "F3R2_V5_HDRM_AUTHORITY_V1"
        or designation != "ARM_HDRM"
        or scope != "COMPETITION_DEMONSTRATOR_FUNCTIONAL_ENVELOPE"
        or directions["preload"] != (1.0, 0.0, 0.0)
        or directions["operational_release"] != (-1.0, 0.0, 0.0)
        or directions["ground_removal_unlock"] != (0.0, 0.0, 1.0)
        or stroke_mm != 6.0
        or preload_n != 50.0
        or states != CONFIGS_HDRM
        or mechanism != "ELECTROMAGNET_HOLD_RELEASE_PLUS_COMPRESSION_SPRING_PLUS_MECHANICAL_STOP"
        or physical_status != "FUNCTIONAL_ENVELOPE_PENDING_NATIVE_ASSEMBLY"
        or holds != expected_holds
    ):
        raise GateError(
            "HDRM_AUTHORITY_SEMANTIC_FAIL",
            "fixed HDRM authority does not preserve the required scope, vectors, stroke, states, mechanism, status and holds",
            {
                "schema": schema,
                "designation": designation,
                "scope": scope,
                "directions": directions,
                "stroke_mm": stroke_mm,
                "preload_candidate_n": preload_n,
                "states": states,
                "mechanism_route": mechanism,
                "physical_status": physical_status,
                "holds": holds,
            },
        )
    return {
        "schema": schema,
        "designation": designation,
        "scope": scope,
        "directions": {name: list(vector) for name, vector in directions.items()},
        "engineering_direction_labels": {"preload": "+X", "operational_release": "-X", "ground_removal_unlock": "+Z"},
        "release_stroke_candidate_mm": stroke_mm,
        "working_preload_candidate_N": preload_n,
        "required_native_states": list(states),
        "mechanism_route": mechanism,
        "physical_status": physical_status,
        "holds": list(holds),
        "pass": True,
    }


def parse_camera_authority(text: str) -> Dict[str, Any]:
    decision = re.findall(
        r"^Decision: `SERVICE_CAMERA = ([A-Z_]+)`; freeze only `([A-Z_]+)` and `([A-Z_]+)`\.\s*$",
        text,
        flags=re.MULTILINE,
    )
    if len(decision) != 1:
        raise GateError("CAMERA_AUTHORITY_DECISION_CARDINALITY_FAIL", "camera decision must occur exactly once", {"matches": decision})
    selection, first_frozen, second_frozen = decision[0]
    geometry = re.findall(
        r"^Frozen wrist-side candidate interface: contact cylinder radius ([0-9]+(?:\.[0-9]+)?) mm, two geometry-only Ø([0-9]+(?:\.[0-9]+)?) mm holes at ([0-9]+(?:\.[0-9]+)?) mm spacing, nominal mount-plane tilt ([0-9]+(?:\.[0-9]+)?)°\. These values are not thread, tolerance, optical-frame or calibration authority\.\s*$",
        text,
        flags=re.MULTILINE,
    )
    if len(geometry) != 1:
        raise GateError("CAMERA_AUTHORITY_GEOMETRY_CARDINALITY_FAIL", "camera candidate interface sentence must occur exactly once", {"matches": geometry})
    radius_mm, hole_diameter_mm, spacing_mm, tilt_deg = (float(value) for value in geometry[0])
    hold = unique_authority_capture(text, r"^Activation requires .* Until then: `([A-Z_]+)`\.\s*$", "camera_activation_hold")
    conditional_non_authority = "but this is not a purchase, model-selection, calibration, or release authority." in text
    if (
        selection != "UNSELECTED"
        or (first_frozen, second_frozen) != ("CAMERA_INTERFACE_STANDARD", "CAMERA_ENVELOPE")
        or radius_mm != 28.5
        or hole_diameter_mm != 2.7
        or spacing_mm != 22.0
        or tilt_deg != 15.0
        or hold != "CAMERA_MODEL_SELECTION_HOLD"
        or not conditional_non_authority
    ):
        raise GateError(
            "CAMERA_AUTHORITY_SEMANTIC_FAIL",
            "fixed camera authority does not preserve UNSELECTED/interface/envelope/geometry/HOLD semantics",
            {
                "selection": selection,
                "frozen": [first_frozen, second_frozen],
                "contact_radius_mm": radius_mm,
                "hole_diameter_mm": hole_diameter_mm,
                "hole_spacing_mm": spacing_mm,
                "tilt_deg": tilt_deg,
                "hold": hold,
                "conditional_preference_is_non_authority": conditional_non_authority,
            },
        )
    return {
        "selection": selection,
        "frozen": [first_frozen, second_frozen],
        "contact_radius_mm": radius_mm,
        "hole_diameter_mm": hole_diameter_mm,
        "hole_spacing_mm": spacing_mm,
        "nominal_tilt_deg": tilt_deg,
        "model_selection_hold": hold,
        "conditional_preference_is_non_authority": True,
        "pass": True,
    }


def validate_inputs() -> Dict[str, Any]:
    formal_roots = sorted(path.resolve() for path in ENGINEERING.glob("F3R2_V5_NATIVE_MECHANICAL_RELEASE_*_V5NATIVE") if path.is_dir())
    if formal_roots != [RUN_ROOT.resolve()]:
        raise GateError("V5_UNIQUE_ROOT_FAIL", "formal V5 release root is not unique", {"expected": norm(RUN_ROOT), "actual": [norm(path) for path in formal_roots]})
    fixed = [fixed_file_audit(*row) for row in FIXED_INPUTS]
    baseline = [fixed_file_audit(*row) for row in IMPORTED_BASELINES]
    if not all(row["pass"] for row in fixed + baseline):
        raise GateError("FIXED_INPUT_HASH_FAIL", "one or more fixed inputs drifted", {"fixed": fixed, "baseline": baseline})

    g0 = load_json(G0_READY)
    claim = load_json(G0_CLAIM)
    imported = load_json(IMPORT_RECEIPT)
    loop1a_receipt = load_json(LOOP1A_RECEIPT)
    authority_receipt = load_json(AUTHORITY_RECEIPT)
    g0_process = g0.get("session_b_process", {})
    if (
        g0.get("verdict") != "G0_SOLIDWORKS_NATIVE_EXECUTION_READY"
        or g0_process.get("pid") != 42276
        or g0_process.get("revision") != "32.5.0"
        or g0_process.get("doc_count_pre") != 0
        or g0_process.get("active_doc_is_null_pre") is not True
        or claim.get("run_id") != RUN_ID
        or Path(str(claim.get("target", ""))).resolve() != RUN_ROOT.resolve()
        or claim.get("g0_ready_receipt_sha256") != FIXED_INPUTS[4][1]
        or claim.get("solidworks_pid") != 42276
    ):
        raise GateError("G0_EXCLUSIVE_CLAIM_FAIL", "G0 or the exclusive V5 claim is incomplete", {"g0_process": g0_process, "claim": claim})
    if imported.get("verdict") != "V5_LOOP1_NEUTRAL_NATIVE_PART_IMPORT_PASS" or imported.get("native_part_count") != 20 or imported.get("solidworks", {}).get("pid") != 42276:
        raise GateError("IMPORT_RECEIPT_FAIL", "neutral import PASS/session is not fixed")
    imported_rows = registered_import_parts(imported)
    if loop1a_receipt.get("verdict") != "V5_LOOP1A_ADAPTER_SUPPORT_SUBASSEMBLIES_PASS" or loop1a_receipt.get("native_part_created") != 1 or loop1a_receipt.get("native_subassemblies_created") != 4 or loop1a_receipt.get("solidworks", {}).get("pid") != 42276:
        raise GateError("LOOP1A_RECEIPT_FAIL", "Loop1A PASS/session is not fixed")
    loop1a_rows = parse_loop1a_manifest()
    if authority_receipt.get("verdict") != "V5_AUTHORITY_SEEDS_MATERIALIZED_PASS":
        raise GateError("AUTHORITY_SEED_FAIL", "authority seed PASS is absent")

    authority_semantics = {
        "hdrm": parse_hdrm_authority(HDRM_AUTHORITY.read_text(encoding="utf-8")),
        "camera": parse_camera_authority(CAMERA_AUTHORITY.read_text(encoding="utf-8")),
    }

    return {
        "fixed": fixed,
        "imported_baselines": baseline,
        "registered_import_parts": imported_rows,
        "loop1a_manifest_rows": loop1a_rows,
        "g0_session_pid": 42276,
        "run_root_unique": True,
        "hdrm_scope": authority_semantics["hdrm"]["scope"],
        "camera_selection": authority_semantics["camera"]["selection"],
        "authority_semantics": authority_semantics,
        "engineering_contract": engineering_contract_audit(),
    }


def immutable_snapshot(validated: Dict[str, Any]) -> Dict[str, Any]:
    def refresh(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [fixed_file_audit(Path(row["path"]), row["expected_sha256"], int(row["expected_bytes"])) for row in rows]

    snapshot = {
        "protected": base.audit_protected(),
        "fixed": refresh(validated["fixed"]),
        "imported_baselines": refresh(validated["imported_baselines"]),
        "registered_import_parts": refresh(validated["registered_import_parts"]),
        "loop1a_manifest_rows": refresh(validated["loop1a_manifest_rows"]),
    }
    if not all(row.get("pass") for group in snapshot.values() for row in group):
        raise GateError("IMMUTABLE_SNAPSHOT_FAIL", "an immutable input failed PRE/POST audit", snapshot)
    return snapshot


def select_front_plane(model: Any) -> str:
    model.ClearSelection2(True)
    for name in ("前视基准面", "Front Plane"):
        try:
            feature = model.FeatureByName(name)
            if feature is not None and bool(feature.Select2(False, 0)):
                return f"{name}::FeatureByName"
        except Exception:
            pass
        if bool(model.Extension.SelectByID2(name, "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0)):
            return f"{name}::SelectByID2"
    raise GateError("FRONT_PLANE_SELECTION_FAIL", "cannot select the native Front Plane")


def sketch_rectangle(sketch: Any, width_m: float, height_m: float) -> None:
    x = width_m / 2.0
    y = height_m / 2.0
    points = ((-x, -y), (x, -y), (x, y), (-x, y), (-x, -y))
    for first, second in zip(points[:-1], points[1:]):
        if sketch.CreateLine(first[0], first[1], 0.0, second[0], second[1], 0.0) is None:
            raise GateError("SKETCH_RECTANGLE_FAIL", "native rectangle line creation returned null")


def sketch_circle(sketch: Any, x_mm: float, y_mm: float, radius_mm: float) -> None:
    if sketch.CreateCircleByRadius(x_mm / 1000.0, y_mm / 1000.0, 0.0, radius_mm / 1000.0) is None:
        raise GateError("SKETCH_CIRCLE_FAIL", "native circle creation returned null", {"x_mm": x_mm, "y_mm": y_mm, "radius_mm": radius_mm})


def create_native_primitive(model: Any, geometry: Dict[str, Any]) -> Dict[str, Any]:
    plane = select_front_plane(model)
    sketch = model.SketchManager
    sketch.InsertSketch(True)
    kind = str(geometry["kind"])
    if kind == "box":
        sketch_rectangle(sketch, float(geometry["width_mm"]) / 1000.0, float(geometry["height_mm"]) / 1000.0)
    elif kind == "cylinder":
        sketch_circle(sketch, 0.0, 0.0, float(geometry["radius_mm"]))
    elif kind == "plate_holes":
        sketch_rectangle(sketch, float(geometry["width_mm"]) / 1000.0, float(geometry["height_mm"]) / 1000.0)
        for x_mm, y_mm, radius_mm in geometry["holes"]:
            sketch_circle(sketch, float(x_mm), float(y_mm), float(radius_mm))
    elif kind == "annulus_holes":
        sketch_circle(sketch, 0.0, 0.0, float(geometry["outer_r_mm"]))
        sketch_circle(sketch, 0.0, 0.0, float(geometry["inner_r_mm"]))
        for x_mm, y_mm, radius_mm in geometry["holes"]:
            sketch_circle(sketch, float(x_mm), float(y_mm), float(radius_mm))
    else:
        raise GateError("PRIMITIVE_KIND_FAIL", "unsupported primitive geometry", {"kind": kind})
    sketch.InsertSketch(True)
    feature = model.FeatureManager.FeatureExtrusion2(
        True, False, False, 0, 0, float(geometry["depth_mm"]) / 1000.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, True, True,
        0, 0.0, False,
    )
    if feature is None:
        raise GateError("NATIVE_EXTRUSION_FAIL", "FeatureExtrusion2 returned null", {"geometry": geometry})
    return {"plane_selection": plane, "primitive": kind, "depth_mm": float(geometry["depth_mm"]), "feature_api": "FeatureExtrusion2"}


def set_properties(model: Any, properties: Dict[str, str]) -> None:
    manager = model.Extension.CustomPropertyManager("")
    common = {
        "Revision": "V5-A",
        "RUN_ID": RUN_ID,
        "RELEASE_SCOPE": "COMPETITION_DEMONSTRATOR_FUNCTIONAL_ENVELOPE",
        "REPRESENTATION_LAYER": "LOOP1D_SOLIDWORKS_NATIVE_FUNCTIONAL_INTERFACE",
        "EXISTING_CAD_MODIFIED": "FALSE",
        "FLIGHT_QUALIFICATION": "HOLD",
    }
    for name, value in {**common, **properties}.items():
        if int(manager.Add3(str(name), 30, str(value), 2)) < 0:
            raise GateError("CUSTOM_PROPERTY_FAIL", "cannot set native custom property", {"name": name, "value": value})


def verify_part_cold(sw: Any, types: Any, pythoncom: Any, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    target = Path(spec["target"])
    cold = None
    title: Optional[str] = None
    try:
        cold, opened = base.open_read_only(sw, target, types, pythoncom)
        title = str(base.value(cold, "GetTitle"))
        if Path(str(base.value(cold, "GetPathName"))).resolve() != target.resolve():
            raise GateError("PART_COLD_PATH_FAIL", "cold-opened part path is not the write-once target", {"name": name})
        if not bool(cold.ForceRebuild3(True)):
            raise GateError("PART_COLD_REBUILD_FAIL", "cold-opened part rebuild failed", {"name": name})
        facts = base.body_facts(cold, types, pythoncom)
        if facts["solid_body_count"] != 1 or facts["all_bodies_solid"] is not True or facts["bounding_box_mm"] is None:
            raise GateError("PART_BODY_FAIL", "native primitive is not exactly one solid body", {"name": name, "facts": facts})
        box = [float(value) for value in facts["bounding_box_mm"]]
        dimensions = sorted((box[3] - box[0], box[4] - box[1], box[5] - box[2]))
        expected = sorted(float(value) for value in spec["expected_sorted_mm"])
        if len(dimensions) != len(expected) or any(abs(actual - wanted) > 0.08 for actual, wanted in zip(dimensions, expected)):
            raise GateError("PART_DIMENSION_FAIL", "native primitive bounding dimensions drifted", {"name": name, "actual_mm": dimensions, "expected_mm": expected})
        interconnect = base.feature_names_3d_interconnect(cold, types, pythoncom)
        external = base.external_reference_count(cold, f"Loop1D0:{name}")
        auxiliary = base.auxiliary_reference_count(cold, f"Loop1D0:{name}")
        if interconnect or external != 0 or auxiliary != 0:
            raise GateError("PART_EXTERNAL_REFERENCE_FAIL", "native primitive retained linked geometry", {"name": name, "interconnect": interconnect, "external": external, "auxiliary": auxiliary})
        return {
            "name": name,
            "target": file_fact(target),
            "open": opened,
            "body_facts": facts,
            "dimensions_mm_sorted": dimensions,
            "three_d_interconnect": interconnect,
            "external_reference_count": external,
            "auxiliary_reference_count": auxiliary,
            "verdict": "V5_LOOP1D0_NATIVE_PRIMITIVE_COLD_PASS",
        }
    finally:
        if title:
            sw.CloseDoc(title)
        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise GateError("PART_COLD_CLEANUP_FAIL", "part cold verification left a document open", {"name": name, "document_count": int(base.value(sw, "GetDocumentCount"))})


def build_part(sw: Any, types: Any, pythoncom: Any, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    target = Path(spec["target"])
    if target.exists():
        raise GateError("PART_TARGET_EXISTS", "write-once native part target exists", {"target": norm(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = sw.NewDocument(str(PART_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("PART_NEW_DOCUMENT_FAIL", "cannot create native part document", {"name": name})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    owned_title = str(base.value(model, "GetTitle"))
    try:
        primitive = create_native_primitive(model, spec["geometry"])
        set_properties(model, {
            "PartNumber": f"SEI-MECH-V5-{name}",
            "Description": name.replace("_", " "),
            "MaterialSpecification": "6061_T6_OR_17_4PH_CANDIDATE_NOT_RELEASED",
            **{str(key): str(value) for key, value in spec["properties"].items()},
        })
        save = base.save_native_part(model, target)
        saved_path = Path(str(base.value(model, "GetPathName"))).resolve()
        if saved_path != target.resolve():
            raise GateError("PART_SAVE_PATH_READBACK_FAIL", "saved part path readback drifted", {"actual": str(saved_path), "expected": str(target)})
    finally:
        try:
            sw.CloseDoc(str(base.value(model, "GetTitle")))
        except Exception:
            sw.CloseDoc(owned_title)
    if int(base.value(sw, "GetDocumentCount")) != 0:
        raise GateError("PART_CLOSE_FAIL", "native part remained open before cold verification", {"name": name})
    cold = verify_part_cold(sw, types, pythoncom, name, spec)
    return {"name": name, "primitive": primitive, "save": save, "cold": cold, "verdict": "V5_LOOP1D0_NATIVE_PART_PASS"}


def rotation_x(degrees: float) -> List[List[float]]:
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    return [[1.0, 0.0, 0.0], [0.0, cosine, -sine], [0.0, sine, cosine]]


def rotation_y(degrees: float) -> List[List[float]]:
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    return [[cosine, 0.0, sine], [0.0, 1.0, 0.0], [-sine, 0.0, cosine]]


def matrix_product(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[sum(float(first[row][index]) * float(second[index][column]) for index in range(3)) for column in range(3)] for row in range(3)]


def mat_vec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> List[float]:
    return [sum(float(matrix[row][column]) * float(vector[column]) for column in range(3)) for row in range(3)]


def component_transform(spec: Dict[str, Any]) -> List[float]:
    # Apply local X rotation first, then local-to-global Y rotation.
    matrix = matrix_product(rotation_y(float(spec.get("rotation_y_deg", 0.0))), rotation_x(float(spec.get("rotation_x_deg", 0.0))))
    local_m = [float(value) / 1000.0 for value in spec["local_center_mm"]]
    desired_m = [float(value) / 1000.0 for value in spec["center_mm"]]
    rotated_local = mat_vec(matrix, local_m)
    translation = [desired_m[index] - rotated_local[index] for index in range(3)]
    # IMathTransform ArrayData is column-major for the 3x3 rotation block.
    return [
        matrix[0][0], matrix[1][0], matrix[2][0],
        matrix[0][1], matrix[1][1], matrix[2][1],
        matrix[0][2], matrix[1][2], matrix[2][2],
        translation[0], translation[1], translation[2],
        1.0, 0.0, 0.0, 0.0,
    ]


def unpack_document(result: Any, label: str) -> Tuple[Any, int, int]:
    if not isinstance(result, tuple) or len(result) < 3:
        raise GateError(f"{label}_RETURN_SHAPE_FAIL", "typed document call did not return model/errors/warnings", {"returned": repr(result)})
    model, outs = base.unpack(result)
    if len(outs) < 2:
        raise GateError(f"{label}_OUT_SHAPE_FAIL", "typed document call omitted errors/warnings", {"returned": repr(result)})
    return model, int(outs[0]), int(outs[1])


def activate(sw: Any, title: str) -> Any:
    returned = sw.ActivateDoc3(title, True, 0, 0)
    if isinstance(returned, tuple):
        raw, outs = base.unpack(returned)
        error = int(outs[0]) if outs else 0
    else:
        raw, error = returned, 0
    if raw is None or error != 0:
        raise GateError("ACTIVATE_OWNED_ASSEMBLY_FAIL", "cannot activate the owned assembly", {"title": title, "error": error})
    return raw


def insert_component(
    sw: Any,
    model: Any,
    assembly: Any,
    component_spec: Dict[str, Any],
    known_unique_paths: set,
    types: Any,
    pythoncom: Any,
) -> Any:
    path = Path(component_spec["path"]).resolve()
    assembly_title = str(base.value(model, "GetTitle"))
    before_unique = set(known_unique_paths)
    raw_part = part = None
    part_title: Optional[str] = None
    inserted = False
    try:
        raw_part, errors, warnings = unpack_document(sw.OpenDoc6(str(path), 1, 3, "", 0, 0), "OPEN_COMPONENT")
        if raw_part is not None:
            part = base.wrap(raw_part, "IModelDoc2", types, pythoncom)
            part_title = str(base.value(part, "GetTitle"))
        if raw_part is None or errors != 0 or warnings != 0 or not bool(base.value(part, "IsOpenedReadOnly")):
            raise GateError("OPEN_COMPONENT_FAIL", "component preload was not a clean read-only open", {"path": norm(path), "errors": errors, "warnings": warnings})
        if Path(str(base.value(part, "GetPathName"))).resolve() != path:
            raise GateError("OPEN_COMPONENT_PATH_FAIL", "component preload resolved a different file", {"path": norm(path)})
        activate(sw, assembly_title)
        raw_component = assembly.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw_component is None:
            raise GateError("ADD_COMPONENT_FAIL", "AddComponent5 returned null", {"path": norm(path)})
        inserted = True
        component = base.wrap(raw_component, "IComponent2", types, pythoncom)
        math_utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
        from win32com.client import VARIANT

        expected_transform = component_transform(component_spec)
        typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, expected_transform)
        transform = math_utility.CreateTransform(typed)
        if transform is None or not bool(component.SetTransformAndSolve3(transform, True)):
            raise GateError("COMPONENT_TRANSFORM_SOLVE_FAIL", "component transform could not be solved", {"role": component_spec["role"]})
        component.Name2 = str(component_spec["role"])
        if str(base.value(component, "Name2")) != str(component_spec["role"]):
            raise GateError("COMPONENT_RENAME_FAIL", "component occurrence name did not read back exactly", {"expected": component_spec["role"], "actual": str(base.value(component, "Name2"))})
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise GateError("COMPONENT_SELECTION_FAIL", "cannot select component for fixed-state assignment", {"role": component_spec["role"]})
        if bool(component_spec["fixed"]):
            assembly.FixComponent()
        else:
            assembly.UnfixComponent()
        model.ClearSelection2(True)
        if bool(base.value(component, "IsFixed")) != bool(component_spec["fixed"]):
            raise GateError("COMPONENT_FIXED_STATE_FAIL", "component fixed state drifted", {"role": component_spec["role"]})
        readback = [float(value) for value in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
        if len(readback) != 16 or any(abs(actual - wanted) > 2.0e-7 for actual, wanted in zip(readback, expected_transform)):
            raise GateError("COMPONENT_TRANSFORM_READBACK_FAIL", "component transform readback drifted", {"role": component_spec["role"], "expected": expected_transform, "actual": readback})
        known_unique_paths.add(norm(path))
        return component
    finally:
        if part_title:
            try:
                sw.CloseDoc(part_title)
            except Exception:
                pass
        activate(sw, assembly_title)
        expected_count = 1 + len(before_unique | ({norm(path)} if inserted else set()))
        actual_count = int(base.value(sw, "GetDocumentCount"))
        if actual_count != expected_count:
            raise GateError("COMPONENT_DEPENDENCY_GRAPH_FAIL", "assembly/dependency document graph count drifted", {"role": component_spec["role"], "expected": expected_count, "actual": actual_count})


def component_state(component: Any) -> Dict[str, Any]:
    path = Path(str(base.value(component, "GetPathName"))).resolve()
    raw_transform = base.value(component, "Transform2")
    if raw_transform is None:
        raise GateError("COMPONENT_TRANSFORM_NULL", "component has no Transform2", {"name2": str(base.value(component, "Name2"))})
    transform = [float(value) for value in base.as_list(base.value(raw_transform, "ArrayData"))]
    if len(transform) != 16:
        raise GateError("COMPONENT_TRANSFORM_SHAPE_FAIL", "component Transform2 is not a 16-value array", {"path": norm(path), "transform": transform})
    return {
        "path": norm(path),
        "name2": str(base.value(component, "Name2")),
        "fixed": bool(base.value(component, "IsFixed")),
        "suppression": int(base.value(component, "GetSuppression2")),
        "transform": [round(value, 12) for value in transform],
    }


def mate_ledger(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    feature = base.value(model, "FirstFeature")
    while feature is not None:
        typed = base.wrap(feature, "IFeature", types, pythoncom)
        if str(base.value(typed, "GetTypeName2")) == "MateGroup":
            sub = base.value(typed, "GetFirstSubFeature")
            while sub is not None:
                sf = base.wrap(sub, "IFeature", types, pythoncom)
                raw_mate = base.value(sf, "GetSpecificFeature2")
                if raw_mate is None:
                    raise GateError("MATE_SPECIFIC_FEATURE_FAIL", "mate subfeature has no IMate2")
                mate = base.wrap(raw_mate, "IMate2", types, pythoncom)
                count = int(base.value(mate, "GetMateEntityCount"))
                endpoints: List[Dict[str, str]] = []
                reference_types: List[int] = []
                for index in range(count):
                    raw_entity = mate.MateEntity(index)
                    if raw_entity is None:
                        raise GateError("MATE_ENTITY_FAIL", "mate entity is null", {"index": index})
                    entity = base.wrap(raw_entity, "IMateEntity2", types, pythoncom)
                    raw_component = base.value(entity, "ReferenceComponent")
                    if raw_component is None:
                        raise GateError("MATE_ENDPOINT_COMPONENT_FAIL", "mate endpoint has no component", {"index": index})
                    component = base.wrap(raw_component, "IComponent2", types, pythoncom)
                    endpoints.append({"name2": str(base.value(component, "Name2")), "path": norm(Path(str(base.value(component, "GetPathName"))))})
                    reference_types.append(int(base.value(entity, "ReferenceType2")))
                row = {
                    "feature_name": str(base.value(sf, "Name")),
                    "feature_error_code": int(base.value(sf, "GetErrorCode")),
                    "suppressed": bool(base.value(sf, "IsSuppressed")),
                    "mate_type": int(base.value(mate, "Type")),
                    "alignment": int(base.value(mate, "Alignment")),
                    "flipped": bool(base.value(mate, "Flipped")),
                    "entity_count": count,
                    "endpoints": sorted(endpoints, key=lambda item: (item["name2"], item["path"])),
                    "reference_types": sorted(reference_types),
                }
                if count != 2 or row["mate_type"] != SW_MATE_LOCK or row["alignment"] != SW_ALIGN_CLOSEST or row["flipped"]:
                    raise GateError("MATE_TYPE_SEMANTIC_FAIL", "mate is not the required two-endpoint native lock/closest contract", row)
                rows.append(row)
                sub = base.value(sf, "GetNextSubFeature")
        feature = base.value(typed, "GetNextFeature")
    return rows


def mate_signature(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        ({
            "mate_type": int(row["mate_type"]),
            "alignment": int(row["alignment"]),
            "flipped": bool(row["flipped"]),
            "entity_count": int(row["entity_count"]),
            "endpoints": sorted((item["name2"], item["path"]) for item in row["endpoints"]),
            "reference_types": sorted(int(value) for value in row["reference_types"]),
            "suppressed": bool(row["suppressed"]),
            "feature_error_code": int(row["feature_error_code"]),
        } for row in rows),
        key=lambda row: (row["endpoints"], row["mate_type"], row["alignment"]),
    )


def expected_component_map(spec: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(item["role"]): item for item in spec["components"]}


def expected_active_roles(spec: Dict[str, Any], config: str) -> set:
    all_roles = set(expected_component_map(spec))
    state_roles = set(spec["state_roles"].values())
    if not state_roles:
        return all_roles
    return (all_roles - state_roles) | {spec["state_roles"][config]}


def validate_mate_contract(ledger: Sequence[Dict[str, Any]], spec: Dict[str, Any], config: str) -> None:
    actual_pairs = Counter(tuple(sorted(item["name2"] for item in row["endpoints"])) for row in ledger)
    expected_pairs = Counter(tuple(sorted(pair)) for pair in spec["mate_pairs"])
    if actual_pairs != expected_pairs or len(ledger) != len(spec["mate_pairs"]):
        raise GateError("MATE_ENDPOINT_CONTRACT_FAIL", "native mate endpoints differ from the exact occurrence contract", {"config": config, "expected": expected_pairs, "actual": actual_pairs, "ledger": list(ledger)})
    active = expected_active_roles(spec, config)
    for row in ledger:
        endpoints = {item["name2"] for item in row["endpoints"]}
        should_suppress = not endpoints.issubset(active)
        if bool(row["suppressed"]) != should_suppress:
            raise GateError("MATE_CONFIGURATION_SUPPRESSION_FAIL", "mate suppression does not follow active state-proxy endpoints", {"config": config, "row": row, "active_roles": sorted(active)})
        if not should_suppress and int(row["feature_error_code"]) != 0:
            raise GateError("MATE_ACTIVE_ERROR_FAIL", "active configuration mate has an error", {"config": config, "row": row})


def configure_document(model: Any, components: Dict[str, Any], spec: Dict[str, Any], types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    raw_active = base.value(manager, "ActiveConfiguration")
    if raw_active is None:
        raise GateError("ACTIVE_CONFIGURATION_FAIL", "new assembly has no active configuration")
    active = base.wrap(raw_active, "IConfiguration", types, pythoncom)
    configs = list(spec["configs"])
    active.Name = configs[0]
    if str(base.value(active, "Name")) != configs[0]:
        raise GateError("CONFIGURATION_RENAME_FAIL", "default configuration did not rename exactly", {"expected": configs[0], "actual": str(base.value(active, "Name"))})
    for config in configs[1:]:
        raw = manager.AddConfiguration2(config, "Loop1D controlled state", "", 0, "", "Loop1D native state proxy", True)
        if raw is None:
            raise GateError("CONFIGURATION_ADD_FAIL", "IConfigurationManager.AddConfiguration2 returned null", {"config": config})
    actual_names = [str(value) for value in base.as_list(base.value(model, "GetConfigurationNames"))]
    if set(actual_names) != set(configs) or len(actual_names) != len(configs):
        raise GateError("CONFIGURATION_SET_FAIL", "assembly configuration set is not exact", {"expected": configs, "actual": actual_names})

    state_rows: List[Dict[str, Any]] = []
    for config in configs:
        if not bool(model.ShowConfiguration2(config)):
            raise GateError("CONFIGURATION_ACTIVATE_FAIL", "ShowConfiguration2 returned false", {"config": config})
        active_roles = expected_active_roles(spec, config)
        for role, component in components.items():
            wanted = SW_COMPONENT_RESOLVED if role in active_roles else SW_COMPONENT_SUPPRESSED
            returned = int(component.SetSuppression2(wanted))
            readback = int(base.value(component, "GetSuppression2"))
            if readback != wanted:
                raise GateError("COMPONENT_SUPPRESSION_FAIL", "SetSuppression2 did not read back the intended state", {"config": config, "role": role, "returned": returned, "wanted": wanted, "readback": readback})
        if not bool(model.ForceRebuild3(True)):
            raise GateError("CONFIGURATION_REBUILD_FAIL", "configuration rebuild failed", {"config": config})
        state_rows.append(configuration_snapshot(model, spec, config, types, pythoncom))
    if not bool(model.ShowConfiguration2(configs[0])):
        raise GateError("CONFIGURATION_RESTORE_FAIL", "cannot restore the controlled default configuration")
    return state_rows


def configuration_snapshot(model: Any, spec: Dict[str, Any], config: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    raw_components = base.as_list(assembly.GetComponents(True))
    components = [base.wrap(item, "IComponent2", types, pythoncom) for item in raw_components]
    states = sorted((component_state(item) for item in components), key=lambda row: row["name2"])
    expected = expected_component_map(spec)
    if {row["name2"] for row in states} != set(expected) or len(states) != len(expected):
        raise GateError("CONFIG_COMPONENT_SET_FAIL", "configuration component occurrence set is not exact", {"config": config, "expected": sorted(expected), "actual": states})
    active_roles = expected_active_roles(spec, config)
    for row in states:
        contract = expected[row["name2"]]
        wanted_suppression = SW_COMPONENT_RESOLVED if row["name2"] in active_roles else SW_COMPONENT_SUPPRESSED
        if row["suppression"] != wanted_suppression or row["fixed"] != bool(contract["fixed"]):
            raise GateError("CONFIG_COMPONENT_STATE_FAIL", "component fixed/suppression state drifted", {"config": config, "state": row, "wanted_suppression": wanted_suppression, "wanted_fixed": bool(contract["fixed"])})
        wanted_transform = component_transform(contract)
        if any(abs(float(actual) - float(wanted)) > 2.0e-6 for actual, wanted in zip(row["transform"], wanted_transform)):
            raise GateError("CONFIG_COMPONENT_TRANSFORM_FAIL", "configuration component transform drifted", {"config": config, "role": row["name2"], "expected": wanted_transform, "actual": row["transform"]})
        if RUN_ROOT.resolve() not in Path(row["path"]).resolve().parents:
            raise GateError("CONFIG_COMPONENT_OUTSIDE_V5", "component reference escapes the unique V5 root", {"state": row})
    ledger = mate_ledger(model, types, pythoncom)
    validate_mate_contract(ledger, spec, config)
    return {"configuration": config, "active_roles": sorted(active_roles), "component_states": states, "mate_ledger": ledger}


def dependency_paths(model: Any) -> List[str]:
    raw = base.as_list(model.GetDependencies2(False, True, False))
    if len(raw) % 2 != 0:
        raise GateError("DEPENDENCY_RETURN_SHAPE_FAIL", "GetDependencies2 did not return name/path pairs", {"returned": raw})
    paths: List[str] = []
    for index in range(1, len(raw), 2):
        path = Path(str(raw[index])).resolve()
        if not path.is_file() or RUN_ROOT.resolve() not in path.parents:
            raise GateError("DEPENDENCY_OUTSIDE_V5", "assembly dependency is absent or outside the unique V5 root", {"path": str(path), "returned": raw})
        paths.append(norm(path))
    return sorted(set(paths))


def expected_dependency_paths(spec: Dict[str, Any]) -> List[str]:
    return sorted({norm(Path(item["path"])) for item in spec["components"]})


def snapshots_signature(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        "configuration": row["configuration"],
        "active_roles": row["active_roles"],
        "component_states": row["component_states"],
        "mate_signature": mate_signature(row["mate_ledger"]),
    } for row in rows]


def transform_point(array: Sequence[float], point: Sequence[float]) -> List[float]:
    if len(array) != 16 or len(point) != 3:
        raise GateError("BREP_TRANSFORM_SHAPE_FAIL", "transform/point shape is invalid")
    return [
        float(array[0]) * point[0] + float(array[3]) * point[1] + float(array[6]) * point[2] + float(array[9]),
        float(array[1]) * point[0] + float(array[4]) * point[1] + float(array[7]) * point[2] + float(array[10]),
        float(array[2]) * point[0] + float(array[5]) * point[1] + float(array[8]) * point[2] + float(array[11]),
    ]


def assembly_brep_bbox_mm(model: Any, types: Any, pythoncom: Any) -> Tuple[List[float], List[Dict[str, Any]]]:
    """Exact cold B-rep extrema transformed into the assembly coordinate frame."""
    from win32com.client import VARIANT

    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    components = [base.wrap(item, "IComponent2", types, pythoncom) for item in base.as_list(assembly.GetComponents(True))]
    minima = [math.inf, math.inf, math.inf]
    maxima = [-math.inf, -math.inf, -math.inf]
    witnesses: List[Dict[str, Any]] = []
    body_count = 0
    for component in components:
        if int(base.value(component, "GetSuppression2")) != SW_COMPONENT_RESOLVED:
            continue
        raw_transform = base.value(component, "Transform2")
        if raw_transform is None:
            raise GateError("BREP_COMPONENT_TRANSFORM_NULL", "resolved component has no transform", {"name2": str(base.value(component, "Name2"))})
        array = [float(value) for value in base.as_list(base.value(raw_transform, "ArrayData"))]
        if len(array) != 16 or abs(array[12] - 1.0) > 2.0e-9:
            raise GateError("BREP_COMPONENT_TRANSFORM_FAIL", "component transform is not rigid/unity scale", {"name2": str(base.value(component, "Name2")), "transform": array})
        bodies = [base.wrap(item, "IBody2", types, pythoncom) for item in base.as_list(component.GetBodies2(SW_BODY_SOLID))]
        if not bodies:
            raise GateError("BREP_COMPONENT_BODY_EMPTY", "resolved physical component has no solid body", {"name2": str(base.value(component, "Name2"))})
        component_extrema = [math.inf, math.inf, math.inf, -math.inf, -math.inf, -math.inf]
        for body in bodies:
            body_count += 1
            for axis in range(3):
                for sign in (-1.0, 1.0):
                    # R^T * world-axis direction; ArrayData stores the 3x3 block column-major.
                    direction = [
                        sign * float(array[axis]),
                        sign * float(array[axis + 3]),
                        sign * float(array[axis + 6]),
                    ]
                    outx = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
                    outy = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
                    outz = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
                    ok = bool(body.GetExtremePoint(direction[0], direction[1], direction[2], outx, outy, outz))
                    if not ok:
                        raise GateError("BREP_EXTREME_POINT_FAIL", "IBody2.GetExtremePoint returned false", {"name2": str(base.value(component, "Name2")), "axis": axis, "sign": sign})
                    world = transform_point(array, [float(outx.value), float(outy.value), float(outz.value)])
                    if sign < 0.0:
                        minima[axis] = min(minima[axis], world[axis])
                        component_extrema[axis] = min(component_extrema[axis], world[axis])
                    else:
                        maxima[axis] = max(maxima[axis], world[axis])
                        component_extrema[axis + 3] = max(component_extrema[axis + 3], world[axis])
        witnesses.append({
            "name2": str(base.value(component, "Name2")),
            "path": norm(Path(str(base.value(component, "GetPathName")))),
            "transform": [round(value, 12) for value in array],
            "brep_bbox_mm": [round(value * 1000.0, 9) for value in component_extrema],
            "solid_body_count": len(bodies),
        })
    if body_count == 0 or not all(math.isfinite(value) for value in minima + maxima) or any(maxima[index] <= minima[index] for index in range(3)):
        raise GateError("ASSEMBLY_BREP_BBOX_FAIL", "cold assembly B-rep bbox is empty/non-finite", {"minima": minima, "maxima": maxima, "body_count": body_count})
    return [round(value * 1000.0, 9) for value in minima + maxima], witnesses


def fixed_datum_witness(snapshot: Dict[str, Any], spec: Dict[str, Any], fixed_role: str) -> Dict[str, Any]:
    expected = expected_component_map(spec)
    wanted_name2 = next((name2 for name2, item in expected.items() if item["role"] == fixed_role), None)
    rows = [row for row in snapshot["component_states"] if row["name2"] == wanted_name2]
    if wanted_name2 is None or len(rows) != 1 or rows[0]["fixed"] is not True or rows[0]["suppression"] != SW_COMPONENT_RESOLVED:
        raise GateError("FRAME_FIXED_DATUM_WITNESS_FAIL", "fixed datum occurrence is absent/not fixed", {"fixed_role": fixed_role, "wanted_name2": wanted_name2, "rows": rows})
    return {
        "fixed_role": fixed_role,
        "name2": wanted_name2,
        "native_path": rows[0]["path"],
        "native_sha256": sha256(Path(rows[0]["path"])),
        "component_transform": rows[0]["transform"],
        "assembly_datum_basis": ["ORIGIN", "+X", "+Y", "+Z"],
    }


def frame_contracts_from_results(items: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build Loop1E-consumable frame contracts only from fresh cold-reopen evidence."""
    by_name = {str(item.get("name", "")): item for item in items}
    if len(by_name) != len(items):
        raise GateError("FRAME_RESULT_SET_FAIL", "native subassembly results have missing/duplicate names", {"names": sorted(by_name)})
    contracts: Dict[str, Dict[str, Any]] = {}
    valid_pairs = {
        "SPACECRAFT_WORLD": "IDENTITY",
        "B601_LOCAL": "MOUNT_T16",
        "LINK6_LOCAL": "LIVE_LINK6_TOTAL_TRANSFORM",
    }
    for role, policy in FRAME_CONTRACT_POLICY.items():
        assembly_name = policy["assembly"]
        result = by_name.get(assembly_name)
        if not isinstance(result, dict):
            raise GateError("FRAME_ASSEMBLY_RESULT_MISSING", "frame contract has no matching assembly result", {"role": role, "assembly": assembly_name})
        # Resumed checkpoints predate this evidence extension.  They are accepted
        # only after the current invocation performs a fresh read-only cold reopen.
        cold = result.get("resume_reverification") if result.get("resumed_from_checkpoint") is True else result.get("cold")
        if not isinstance(cold, dict) or cold.get("verdict") != "V5_LOOP1D1_ASSEMBLY_COLD_CONFIG_MATE_REFERENCE_PASS":
            raise GateError("FRAME_COLD_EVIDENCE_MISSING", "frame contract is not backed by the current cold-reopen verifier", {"role": role, "assembly": assembly_name})
        bbox = cold.get("cold_brep_bbox_mm")
        if (
            not isinstance(bbox, list)
            or len(bbox) != 6
            or not all(math.isfinite(float(value)) for value in bbox)
            or any(float(bbox[index + 3]) <= float(bbox[index]) for index in range(3))
        ):
            raise GateError("FRAME_BREP_BBOX_FAIL", "frame source bbox is absent/non-finite/degenerate", {"role": role, "bbox": bbox})
        external = cold.get("external_reference_count")
        auxiliary = cold.get("auxiliary_reference_count")
        component_witnesses = cold.get("cold_brep_component_witnesses")
        if external != 0 or auxiliary != 0 or not isinstance(component_witnesses, list) or not component_witnesses:
            raise GateError("FRAME_REFERENCE_WITNESS_FAIL", "frame source is not independently native or lacks component B-rep witnesses", {"role": role, "external": external, "auxiliary": auxiliary})
        snapshots = cold.get("configuration_ledgers")
        if not isinstance(snapshots, list) or not snapshots or snapshots[0].get("configuration") != ASSEMBLY_SPECS[assembly_name]["configs"][0]:
            raise GateError("FRAME_CONFIGURATION_WITNESS_FAIL", "cold evidence omits the controlled datum configuration", {"role": role, "assembly": assembly_name})
        source_frame = policy["source_frame"]
        placement = policy["placement"]
        if valid_pairs.get(source_frame) != placement:
            raise GateError("FRAME_POLICY_PAIR_FAIL", "source-frame/placement pair is not an allowed Loop1E contract", {"role": role, "source_frame": source_frame, "placement": placement})
        target = Path(ASSEMBLY_SPECS[assembly_name]["target"])
        if not target.is_file() or cold.get("target") != file_fact(target):
            raise GateError("FRAME_TARGET_BINDING_FAIL", "cold target fact does not bind the current native assembly", {"role": role, "target": norm(target), "cold_target": cold.get("target")})
        datum = fixed_datum_witness(snapshots[0], ASSEMBLY_SPECS[assembly_name], policy["fixed_role"])
        contracts[role] = {
            "schema": "F3R2_V5_NATIVE_FRAME_CONTRACT_V1",
            "source_frame": source_frame,
            "placement": placement,
            "target_path": norm(target),
            "target_sha256": sha256(target),
            "source_bbox_mm": [float(value) for value in bbox],
            "witness": {
                "method": "SOLIDWORKS_COLD_BREP_BBOX_AND_DATUM_WITNESS",
                "cold_reopen_pass": True,
                "cold_reopen_verdict": cold["verdict"],
                "configuration": snapshots[0]["configuration"],
                "external_reference_count": 0,
                "auxiliary_reference_count": 0,
                "frame_rationale": policy["frame_rationale"],
                "fixed_datum": datum,
                "component_brep_witnesses": component_witnesses,
            },
        }
    if set(contracts) != set(FRAME_CONTRACT_POLICY):
        raise GateError("FRAME_CONTRACT_SET_FAIL", "generated frame-contract role set is not exact", {"expected": sorted(FRAME_CONTRACT_POLICY), "actual": sorted(contracts)})
    return contracts


def verify_assembly_cold(sw: Any, types: Any, pythoncom: Any, name: str, spec: Dict[str, Any], expected_snapshots: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    target = Path(spec["target"])
    raw = cold = None
    title: Optional[str] = None
    try:
        raw, errors, warnings = unpack_document(sw.OpenDoc6(str(target), 2, 3, "", 0, 0), "COLD_OPEN_ASSEMBLY")
        if raw is not None:
            cold = base.wrap(raw, "IModelDoc2", types, pythoncom)
            title = str(base.value(cold, "GetTitle"))
        if raw is None or errors != 0 or warnings != 0 or not bool(base.value(cold, "IsOpenedReadOnly")):
            raise GateError("ASSEMBLY_COLD_OPEN_FAIL", "assembly cold open was not clean/read-only", {"name": name, "errors": errors, "warnings": warnings})
        if Path(str(base.value(cold, "GetPathName"))).resolve() != target.resolve():
            raise GateError("ASSEMBLY_COLD_PATH_FAIL", "cold-opened assembly path is not exact", {"name": name})
        cold_assembly = base.wrap(cold, "IAssemblyDoc", types, pythoncom)
        cold_assembly.ResolveAllLightWeightComponents(True)
        dependencies = dependency_paths(cold)
        expected_dependencies = expected_dependency_paths(spec)
        if dependencies != expected_dependencies:
            raise GateError("ASSEMBLY_DEPENDENCY_SET_FAIL", "cold GetDependencies2 set is not exact", {"name": name, "expected": expected_dependencies, "actual": dependencies})
        snapshots: List[Dict[str, Any]] = []
        for config in spec["configs"]:
            if not bool(cold.ShowConfiguration2(config)) or not bool(cold.ForceRebuild3(True)):
                raise GateError("ASSEMBLY_COLD_CONFIG_FAIL", "cold configuration activation/rebuild failed", {"name": name, "config": config})
            snapshots.append(configuration_snapshot(cold, spec, config, types, pythoncom))
        if expected_snapshots is not None and snapshots_signature(snapshots) != snapshots_signature(expected_snapshots):
            raise GateError("ASSEMBLY_COLD_SEMANTIC_DRIFT", "configuration/mate/transform ledger drifted on cold reopen", {"name": name, "before": snapshots_signature(expected_snapshots), "cold": snapshots_signature(snapshots)})
        component_multiset = Counter(state["path"] for state in snapshots[0]["component_states"])
        expected_multiset = Counter(norm(Path(item["path"])) for item in spec["components"])
        if component_multiset != expected_multiset:
            raise GateError("ASSEMBLY_COMPONENT_MULTISET_FAIL", "cold component reference multiset is not exact", {"name": name, "expected": expected_multiset, "actual": component_multiset})
        reference_facts = [file_fact(Path(path)) for path in dependencies]
        if not bool(cold.ShowConfiguration2(spec["configs"][0])) or not bool(cold.ForceRebuild3(True)):
            raise GateError("FRAME_WITNESS_CONFIG_RESTORE_FAIL", "cannot restore controlled frame-witness configuration", {"name": name})
        brep_bbox_mm, brep_component_witnesses = assembly_brep_bbox_mm(cold, types, pythoncom)
        external = int(base.external_reference_count(cold, f"Loop1D1:{name}"))
        auxiliary = int(base.auxiliary_reference_count(cold, f"Loop1D1:{name}"))
        if external != 0 or auxiliary != 0:
            raise GateError("ASSEMBLY_EXTERNAL_REFERENCE_FAIL", "cold assembly retained external/auxiliary references", {"name": name, "external": external, "auxiliary": auxiliary})
        return {
            "name": name,
            "target": file_fact(target),
            "errors": errors,
            "warnings": warnings,
            "read_only": True,
            "dependencies": reference_facts,
            "component_reference_multiset": dict(component_multiset),
            "configuration_ledgers": snapshots,
            "cold_brep_bbox_mm": brep_bbox_mm,
            "cold_brep_component_witnesses": brep_component_witnesses,
            "external_reference_count": external,
            "auxiliary_reference_count": auxiliary,
            "verdict": "V5_LOOP1D1_ASSEMBLY_COLD_CONFIG_MATE_REFERENCE_PASS",
        }
    finally:
        if title:
            sw.CloseDoc(title)
        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise GateError("ASSEMBLY_COLD_CLEANUP_FAIL", "cold assembly remained open after owned close", {"name": name, "document_count": int(base.value(sw, "GetDocumentCount"))})


def build_assembly(sw: Any, types: Any, pythoncom: Any, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    target = Path(spec["target"])
    if target.exists():
        raise GateError("ASSEMBLY_TARGET_EXISTS", "write-once assembly target exists", {"target": norm(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("ASSEMBLY_NEW_DOCUMENT_FAIL", "cannot create native assembly", {"name": name})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    owned_title = str(base.value(model, "GetTitle"))
    components: Dict[str, Any] = {}
    unique_paths: set = set()
    try:
        for item in spec["components"]:
            component = insert_component(sw, model, assembly, item, unique_paths, types, pythoncom)
            components[str(item["role"])] = component
        mate_results = []
        for first_role, second_role in spec["mate_pairs"]:
            created = loop1a.add_component_lock_mate(model, assembly, components[first_role], components[second_role], types, pythoncom)
            if int(created.get("mate_type", -1)) != SW_MATE_LOCK or int(created.get("align", -1)) != SW_ALIGN_CLOSEST or int(created.get("error_status", -1)) != SW_ADD_MATE_NO_ERROR or int(created.get("selected_count", -1)) != 2:
                raise GateError("LOCK_MATE_CREATE_RESULT_FAIL", "native lock mate result does not meet the exact contract", {"first": first_role, "second": second_role, "result": created})
            mate_results.append({"first": first_role, "second": second_role, **created})
        configuration_rows = configure_document(model, components, spec, types, pythoncom)
        dependencies = dependency_paths(model)
        if dependencies != expected_dependency_paths(spec):
            raise GateError("ASSEMBLY_LIVE_DEPENDENCY_FAIL", "live dependency set is not exact", {"name": name, "expected": expected_dependency_paths(spec), "actual": dependencies})
        set_properties(model, {
            "AssemblyNumber": f"SEI-MECH-V5-{name}",
            "Description": name.replace("_", " "),
            "MATE_ARCHITECTURE": "NATIVE_COMPONENT_LOCK_MATES_WITH_EXACT_ENDPOINT_LEDGER",
            **{str(key): str(value) for key, value in spec["properties"].items()},
        })
        save = loop1a.save_assembly(model, target)
        if Path(str(base.value(model, "GetPathName"))).resolve() != target.resolve():
            raise GateError("ASSEMBLY_SAVE_PATH_READBACK_FAIL", "saved assembly path readback drifted", {"name": name})
        title_after_save = str(base.value(model, "GetTitle"))
        if title_after_save.lower() not in {target.name.lower(), target.stem.lower()}:
            raise GateError("ASSEMBLY_SAVE_TITLE_READBACK_FAIL", "saved assembly title is not native SLDASM", {"title": title_after_save})
        sw.CloseDoc(title_after_save)
        model = None
        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise GateError("ASSEMBLY_CLOSE_FAIL", "owned assembly/dependencies remained open before cold reopen", {"name": name})
        cold = verify_assembly_cold(sw, types, pythoncom, name, spec, configuration_rows)
        return {
            "name": name,
            "target": save,
            "component_occurrences": [{"role": item["role"], "path": norm(Path(item["path"])), "fixed": bool(item["fixed"]), "center_mm": item["center_mm"], "transform": component_transform(item)} for item in spec["components"]],
            "mates_created": mate_results,
            "configuration_ledgers": configuration_rows,
            "cold": cold,
            "interference_closure_claimed": False,
            "flight_qualification_claimed": False,
            "verdict": "V5_LOOP1D1_NATIVE_FUNCTIONAL_ASSEMBLY_PASS",
        }
    finally:
        if model is not None:
            try:
                sw.CloseDoc(str(base.value(model, "GetTitle")))
            except Exception:
                try:
                    sw.CloseDoc(owned_title)
                except Exception:
                    pass


def baseline_contract_digest() -> str:
    contract = {
        "parts": {name: {"target": norm(Path(spec["target"])), "geometry": spec["geometry"], "expected_sorted_mm": spec["expected_sorted_mm"], "properties": spec["properties"]} for name, spec in PART_SPECS.items()},
        "assemblies": {name: {"target": norm(Path(spec["target"])), "configs": spec["configs"], "components": [{key: (norm(Path(value)) if key == "path" else value) for key, value in item.items()} for item in spec["components"]], "mate_pairs": spec["mate_pairs"], "properties": spec["properties"]} for name, spec in ASSEMBLY_SPECS.items()},
        "non_coverage": NON_COVERAGE,
    }
    encoded = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def checkpoint_binding() -> Dict[str, Any]:
    return {
        "script_sha256": sha256(Path(__file__)),
        "base_helper_sha256": FIXED_INPUTS[0][1],
        "loop1a_helper_sha256": FIXED_INPUTS[1][1],
        "g0_ready_sha256": FIXED_INPUTS[4][1],
        "g0_exclusive_claim_sha256": FIXED_INPUTS[5][1],
        "import_receipt_sha256": FIXED_INPUTS[6][1],
        "loop1a_receipt_sha256": FIXED_INPUTS[7][1],
        "loop1a_manifest_sha256": FIXED_INPUTS[8][1],
        "authority_seed_receipt_sha256": FIXED_INPUTS[9][1],
        "hdrm_authority_sha256": FIXED_INPUTS[10][1],
        "camera_authority_sha256": FIXED_INPUTS[11][1],
        "baseline_contract_sha256": baseline_contract_digest(),
        "run_id": RUN_ID,
    }


def write_checkpoint(path: Path, target: Path, kind: str, name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "schema": "F3R2_V5_LOOP1D_ARTIFACT_CHECKPOINT_V1",
        "timestamp_utc": utc_now(),
        "kind": kind,
        "name": name,
        "binding": checkpoint_binding(),
        "target": file_fact(target),
        "result": result,
        "verdict": "V5_LOOP1D_ARTIFACT_CHECKPOINT_PASS",
    }
    write_json_once(path, payload)
    return file_fact(path)


def load_checkpoint(path: Path, target: Path, kind: str, name: str) -> Dict[str, Any]:
    if not path.is_file() or not target.is_file():
        raise GateError("CHECKPOINT_PAIR_FAIL", "target/checkpoint pair is incomplete", {"target": norm(target), "checkpoint": norm(path)})
    payload = load_json(path)
    if (
        payload.get("schema") != "F3R2_V5_LOOP1D_ARTIFACT_CHECKPOINT_V1"
        or payload.get("kind") != kind
        or payload.get("name") != name
        or payload.get("binding") != checkpoint_binding()
        or payload.get("target") != file_fact(target)
        or payload.get("verdict") != "V5_LOOP1D_ARTIFACT_CHECKPOINT_PASS"
        or not isinstance(payload.get("result"), dict)
    ):
        raise GateError("CHECKPOINT_BINDING_FAIL", "checkpoint does not bind the current script/input/contract/target", {"target": norm(target), "checkpoint": norm(path)})
    return payload


def artifact_static_state(target: Path, checkpoint: Path, kind: str, name: str) -> Dict[str, Any]:
    target_exists, checkpoint_exists = target.is_file(), checkpoint.is_file()
    state: Dict[str, Any] = {"name": name, "kind": kind, "target": norm(target), "checkpoint": norm(checkpoint), "target_exists": target_exists, "checkpoint_exists": checkpoint_exists}
    if not target_exists and not checkpoint_exists:
        state.update({"status": "PENDING", "pass": True})
    elif target_exists and checkpoint_exists:
        try:
            payload = load_checkpoint(checkpoint, target, kind, name)
        except GateError as exc:
            state.update({"status": exc.code, "pass": False, "reason": str(exc)})
        else:
            state.update({"status": "CHECKPOINT_VERIFIED_RESUMABLE", "pass": True, "target_fact": payload["target"], "checkpoint_sha256": sha256(checkpoint)})
    else:
        state.update({"status": "UNPAIRED_PARTIAL_ARTIFACT_HOLD", "pass": False, "recovery": "MANUAL_ADJUDICATION_REQUIRED_NO_AUTOMATIC_DELETE_OR_ADOPTION"})
    return state


def static_audit() -> Dict[str, Any]:
    validated = validate_inputs()
    targets: List[Dict[str, Any]] = []
    for name, spec in PART_SPECS.items():
        targets.append(artifact_static_state(Path(spec["target"]), PART_CHECKPOINTS[name], "LOOP1D0_NATIVE_PART", name))
    for name, spec in ASSEMBLY_SPECS.items():
        targets.append(artifact_static_state(Path(spec["target"]), ASSEMBLY_CHECKPOINTS[name], "LOOP1D1_NATIVE_ASSEMBLY", name))
    script_copy_ok = not SCRIPT_COPY.exists() or (SCRIPT_COPY.is_file() and sha256(SCRIPT_COPY) == sha256(Path(__file__)))
    packaging = {
        "script_copy_exists": SCRIPT_COPY.exists(),
        "script_copy_matches_current": script_copy_ok,
        "final_manifest_exists": FINAL_MANIFEST.exists(),
        "final_receipt_exists": FINAL_RECEIPT.exists(),
    }
    allowed_pairs = {
        "SPACECRAFT_WORLD": "IDENTITY",
        "B601_LOCAL": "MOUNT_T16",
        "LINK6_LOCAL": "LIVE_LINK6_TOTAL_TRANSFORM",
    }
    policy_rows = [{
        "role": role,
        **dict(policy),
        "target": norm(Path(ASSEMBLY_SPECS[policy["assembly"]]["target"])) if policy.get("assembly") in ASSEMBLY_SPECS else None,
        "pass": bool(
            policy.get("assembly") in ASSEMBLY_SPECS
            and allowed_pairs.get(policy.get("source_frame")) == policy.get("placement")
            and policy.get("fixed_role") in {item["role"] for item in ASSEMBLY_SPECS[policy["assembly"]]["components"]}
            and bool(str(policy.get("frame_rationale", "")).strip())
        ),
    } for role, policy in FRAME_CONTRACT_POLICY.items()]
    frame_policy = {
        "schema": "F3R2_V5_NATIVE_FRAME_CONTRACT_V1",
        "required_roles": ["CAMERA", "HDRM", "HARNESS"],
        "rows": policy_rows,
        "pass": set(FRAME_CONTRACT_POLICY) == {"CAMERA", "HDRM", "HARNESS"} and all(row["pass"] for row in policy_rows),
        "runtime_evidence_required": "SOLIDWORKS_COLD_BREP_BBOX_AND_DATUM_WITNESS",
    }
    executable = all(row["pass"] for row in targets) and frame_policy["pass"] and script_copy_ok and not FINAL_MANIFEST.exists() and not FINAL_RECEIPT.exists()
    return {
        "schema": "F3R2_V5_LOOP1D_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "run_root": norm(RUN_ROOT),
        "input_audit": validated,
        "targets": targets,
        "packaging": packaging,
        "frame_contract_policy": frame_policy,
        "application_connection_contract": "PINNED_BASE_HELPER_ATTACH_EMPTY_SESSION_ONLY",
        "existing_cad_mutation_authorized": False,
        "native_parts_planned": len(PART_SPECS),
        "native_subassemblies_planned": len(ASSEMBLY_SPECS),
        "explicit_non_coverage": NON_COVERAGE,
        "execution_authorized": executable,
        "verdict": "V5_LOOP1D_STATIC_PASS_OR_VERIFIED_RESUME" if executable else "V5_LOOP1D_STATIC_HOLD_OR_COMPLETE",
    }


def resume_part(sw: Any, types: Any, pythoncom: Any, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    payload = load_checkpoint(PART_CHECKPOINTS[name], Path(spec["target"]), "LOOP1D0_NATIVE_PART", name)
    cold = verify_part_cold(sw, types, pythoncom, name, spec)
    result = dict(payload["result"])
    result.update({"resumed_from_checkpoint": True, "resume_reverification": cold})
    return result


def resume_assembly(sw: Any, types: Any, pythoncom: Any, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    payload = load_checkpoint(ASSEMBLY_CHECKPOINTS[name], Path(spec["target"]), "LOOP1D1_NATIVE_ASSEMBLY", name)
    prior_rows = payload["result"].get("configuration_ledgers")
    if not isinstance(prior_rows, list):
        raise GateError("CHECKPOINT_ASSEMBLY_LEDGER_FAIL", "assembly checkpoint omits the controlled configuration ledger", {"name": name})
    cold = verify_assembly_cold(sw, types, pythoncom, name, spec, prior_rows)
    result = dict(payload["result"])
    result.update({"resumed_from_checkpoint": True, "resume_reverification": cold})
    return result


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def write_failure(result: Dict[str, Any]) -> Optional[Path]:
    failure = RUN_ROOT / f"13_validation/V5_LOOP1D_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
    try:
        write_json_once(failure, json_safe(result))
    except Exception:
        return None
    return failure


def execute() -> int:
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT_V1",
        "timestamp_start_utc": utc_now(),
        "run_root": norm(RUN_ROOT),
        "native_parts": [],
        "native_subassemblies": [],
        "artifact_checkpoints_written_this_invocation": [],
        "explicit_non_coverage": NON_COVERAGE,
        "script_sha256_start": sha256(Path(__file__)),
    }
    sw = types = pythoncom = None
    try:
        audit = static_audit()
        if not audit["execution_authorized"]:
            raise GateError("LOOP1D_STATIC_EXECUTION_HOLD", "static target/checkpoint/packaging state is not executable", {"audit": audit})
        result["static_audit"] = audit
        validated = audit["input_audit"]
        result["immutable_pre"] = immutable_snapshot(validated)
        sw, types, pythoncom, session = base.attach_empty_session()
        result["solidworks"] = session
        if session.get("pid") != 42276 or session.get("revision") != "32.5.0" or session.get("document_count") != 0 or session.get("active_doc_is_null") is not True:
            raise GateError("QUALIFIED_SESSION_DRIFT", "attached application is not the fixed empty Session-B process", {"session": session})

        for name, spec in PART_SPECS.items():
            target = Path(spec["target"])
            if target.exists():
                item = resume_part(sw, types, pythoncom, name, spec)
            else:
                item = build_part(sw, types, pythoncom, name, spec)
                result["artifact_checkpoints_written_this_invocation"].append(write_checkpoint(PART_CHECKPOINTS[name], target, "LOOP1D0_NATIVE_PART", name, item))
            result["native_parts"].append(item)

        for name, spec in ASSEMBLY_SPECS.items():
            target = Path(spec["target"])
            if target.exists():
                item = resume_assembly(sw, types, pythoncom, name, spec)
            else:
                item = build_assembly(sw, types, pythoncom, name, spec)
                result["artifact_checkpoints_written_this_invocation"].append(write_checkpoint(ASSEMBLY_CHECKPOINTS[name], target, "LOOP1D1_NATIVE_ASSEMBLY", name, item))
            result["native_subassemblies"].append(item)

        result["frame_contracts"] = frame_contracts_from_results(result["native_subassemblies"])

        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise GateError("POST_BUILD_SESSION_NOT_EMPTY", "owned documents remain after Loop1D", {"document_count": int(base.value(sw, "GetDocumentCount"))})
        result["immutable_post"] = immutable_snapshot(validated)
        if result["immutable_pre"] != result["immutable_post"]:
            raise GateError("IMMUTABLE_POST_DRIFT", "protected/imported/Loop1A/authority assets changed")
        if sha256(Path(__file__)) != result["script_sha256_start"]:
            raise GateError("EXECUTING_SCRIPT_TOCTOU_FAIL", "Loop1D script changed during execution")

        if SCRIPT_COPY.exists():
            if sha256(SCRIPT_COPY) != sha256(Path(__file__)):
                raise GateError("SCRIPT_COPY_DRIFT", "existing V5 tool copy differs from executing script")
        else:
            SCRIPT_COPY.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(__file__).resolve(), SCRIPT_COPY)
        manifest_paths = [
            *(Path(spec["target"]) for spec in PART_SPECS.values()),
            *(PART_CHECKPOINTS.values()),
            *(Path(spec["target"]) for spec in ASSEMBLY_SPECS.values()),
            *(ASSEMBLY_CHECKPOINTS.values()),
            SCRIPT_COPY,
            IMPORT_RECEIPT,
            LOOP1A_RECEIPT,
            LOOP1A_MANIFEST,
            AUTHORITY_RECEIPT,
            HDRM_AUTHORITY,
            CAMERA_AUTHORITY,
        ]
        lines = [f"{sha256(path)}  {path.stat().st_size}  {path.relative_to(RUN_ROOT).as_posix()}" for path in manifest_paths]
        with FINAL_MANIFEST.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(sorted(lines)) + "\n")

        result.update({
            "timestamp_end_utc": utc_now(),
            "verdict": "V5_LOOP1D_HDRM_CAMERA_HARNESS_NATIVE_FUNCTIONAL_INTERFACE_PASS",
            "native_part_count": len(PART_SPECS),
            "native_subassembly_count": len(ASSEMBLY_SPECS),
            "hdrm_scope": "COMPETITION_DEMONSTRATOR_FUNCTIONAL_ENVELOPE",
            "hdrm_directions": {"preload": "+X", "operational_release": "-X", "ground_unlock": "+Z"},
            "hdrm_stroke_mm": 6.0,
            "hdrm_configurations": list(CONFIGS_HDRM),
            "camera_selection": "UNSELECTED",
            "camera_model_selection": "HOLD",
            "harness_static_envelope": "OD9",
            "harness_static_bend_radius_mm": {"centerline": 30.0, "minimum": 25.0, "margin": 5.0},
            "harness_moving_sweep": "HOLD",
            "flight_qualification_claimed": False,
            "interference_closure_claimed": False,
            "manifest": file_fact(FINAL_MANIFEST),
        })
        # PASS receipt is deliberately the final write.
        write_json_once(FINAL_RECEIPT, result)
        print(json.dumps({"verdict": result["verdict"], "receipt": file_fact(FINAL_RECEIPT), "manifest": result["manifest"], "solidworks_document_count": int(base.value(sw, "GetDocumentCount"))}, ensure_ascii=False, indent=2))
        return 0
    except (GateError, base.GateError, loop1a.GateError) as exc:
        result.update({
            "verdict": getattr(exc, "code", "V5_LOOP1D_GATE_FAIL"),
            "reason": str(exc),
            "detail": getattr(exc, "detail", {}),
            "traceback": traceback.format_exc(),
            "timestamp_end_utc": utc_now(),
            "partial_artifacts": [file_fact(path) for path in [*(Path(spec["target"]) for spec in PART_SPECS.values()), *(Path(spec["target"]) for spec in ASSEMBLY_SPECS.values())] if path.is_file()],
        })
        failure = write_failure(result)
        if failure is not None:
            result["failure_receipt"] = file_fact(failure)
        print(json.dumps(json_safe(result), ensure_ascii=False, indent=2, default=str), file=sys.stderr)
        return 3
    except Exception as exc:
        result.update({
            "verdict": "V5_LOOP1D_UNEXPECTED_EXCEPTION",
            "reason": repr(exc),
            "traceback": traceback.format_exc(),
            "timestamp_end_utc": utc_now(),
            "partial_artifacts": [file_fact(path) for path in [*(Path(spec["target"]) for spec in PART_SPECS.values()), *(Path(spec["target"]) for spec in ASSEMBLY_SPECS.values())] if path.is_file()],
        })
        if sw is not None:
            try:
                result["solidworks_document_count_on_failure"] = int(base.value(sw, "GetDocumentCount"))
            except Exception:
                pass
        failure = write_failure(result)
        if failure is not None:
            result["failure_receipt"] = file_fact(failure)
        print(json.dumps(json_safe(result), ensure_ascii=False, indent=2, default=str), file=sys.stderr)
        return 4
    finally:
        sw = None
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("audit", "execute"))
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        print(json.dumps(static_audit(), ensure_ascii=False, indent=2))
        return 0
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
