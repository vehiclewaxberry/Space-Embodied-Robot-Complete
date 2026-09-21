#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the exclusive F3R2 V5 tree and import the controlled V4 STEP parts.

This is a deliberately narrow first native-build phase.  It runs only after
the two-session G0 smoke receipt exists, attaches only to an already-running
empty SOLIDWORKS 2024 session, creates a previously absent V5 run root, imports
the 20 registered V4 STEP inputs with 3D Interconnect disabled, breaks external
references, saves native SLDPRT files, and cold-reopens each part read-only.

It does not start or exit SOLIDWORKS, does not modify application visibility or
user-control state, does not modify V4 or any protected asset, and does not
claim that assemblies, mates, configurations, drawings, motion, Pack-and-Go or
the final V5 Gate are complete.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


sys.dont_write_bytecode = True

import F3R2_V5_MEMORY_OVERRIDE as mo

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
V4 = ENGINEERING / "F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
V4_MANIFEST = V4 / "99_tools/MFINAL_SOLIDWORKS_INPUT_MANIFEST.json"
V4_MANIFEST_SHA256 = "A92AC96C9CD150374B566956E7383F8CCBE0625A41C5C833A3FAE5961913DE92"
G0_RUN = ENGINEERING / "_MFINAL_G0_SMOKE_20260809T172928_P4E8"
G0_READY = G0_RUN / "G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json"
G0_SMOKE_PART = G0_RUN / "G0_SMOKE_20X20X10.SLDPRT"
G0_SESSION_A_RECEIPT = G0_RUN / "G0_SMOKE_SESSION_A_RECEIPT.json"
G0_PREDELETE_RECEIPT = G0_RUN / "G0_SMOKE_SESSION_B_PREDELETE_RECEIPT.json"
G0_V5_RUN_CLAIM = G0_RUN / "G0_V5_EXCLUSIVE_RUN_CLAIM.json"
G0_SESSION_A_RECEIPT_SHA256 = "AA070605E7576A79239E0877DA855FCC3F7693E9FCD906E8EFF93F9CC2880F87"
G0_SESSION_A_PID = 10332
G0_SMOKE_PART_BYTES = 59102
G0_SMOKE_PART_SHA256 = "797A28B0FD24239A14037690ADCE4A4D0DC4504AC2946B7D59C020D83E709656"
SOLIDWORKS_EXE = Path(r"F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe")
RELEASE_PREFIX = "F3R2_V5_NATIVE_MECHANICAL_RELEASE_"
RUN_ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}_[A-Z0-9]{4,12}$")
EXPECTED_SW_MAJOR = 32
MIN_AVAILABLE_GIB = 6.0
SW_PROG_ID = "SldWorks.Application"
SW_TLB = ("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)

DIRS = (
    "00_authority",
    "01_native_parts/adapter",
    "01_native_parts/wing_root",
    "01_native_parts/supports",
    "01_native_parts/hdrm",
    "01_native_parts/camera_harness",
    "01_native_parts/gripper",
    "02_native_subassemblies",
    "03_top_assembly",
    "04_configurations",
    "05_clearance",
    "06_mass_properties",
    "07_drawings",
    "08_bom",
    "09_digital_thread",
    "10_pack_and_go",
    "11_screenshots/RAW",
    "11_screenshots/ANNOTATED",
    "12_human_review",
    "13_validation",
    "14_release",
    "99_tools",
)

# Only the 20 neutral STEP inputs are admitted in this phase.  The frozen top
# and 58-solid gripper donor remain read-only inputs for later controlled phases.
PART_CONTRACT: Dict[str, Dict[str, str]] = {
    "NEUTRAL_V4_B601_STAGE_A_INTERFACE_RING_REVB": {
        "relative": "01_native_parts/adapter/B601_INTERFACE_STAGE_A_REV_B2.SLDPRT",
        "part_number": "SEI-MECH-B601-A-REVB2",
        "description": "4xM4-class 64x64 as-built B601 interface ring; 8xM5 transition",
        "material": "AL6061-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_B601_STAGE_B_LOAD_ADAPTER_REVB2": {
        "relative": "01_native_parts/adapter/B601_LOAD_ADAPTER_STAGE_B_REV_B2.SLDPRT",
        "part_number": "SEI-MECH-B601-B-REVB2",
        "description": "140x140 M6 load adapter with four R15 local load ears",
        "material": "AL6061-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_WING_ROOT_THREE_WEB_CLEVIS_LEFT": {
        "relative": "01_native_parts/wing_root/LEFT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT",
        "part_number": "SEI-MECH-WR-L-001",
        "description": "Left three-web double-shear wing-root clevis candidate",
        "material": "AL6061-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_WING_ROOT_THREE_WEB_CLEVIS_RIGHT": {
        "relative": "01_native_parts/wing_root/RIGHT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT",
        "part_number": "SEI-MECH-WR-R-001",
        "description": "Right three-web double-shear wing-root clevis candidate",
        "material": "AL6061-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_HINGE_AXIAL_SPACER": {
        "relative": "01_native_parts/wing_root/WING_HINGE_AXIAL_SPACER.SLDPRT",
        "part_number": "SEI-MECH-WR-SPACER-001",
        "description": "D18/D8.6 x 0.5 hinge axial spacer candidate",
        "material": "PTFE-FILLED-BRONZE",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_WING_HARNESS_GROMMET": {
        "relative": "01_native_parts/wing_root/WING_HARNESS_GROMMET.SLDPRT",
        "part_number": "SEI-MECH-WR-GROMMET-001",
        "description": "D13/D8 x 8 wing harness grommet candidate",
        "material": "VMQ-60A",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_WING_STOP_PAD": {
        "relative": "01_native_parts/wing_root/WING_MECHANICAL_STOP_PAD.SLDPRT",
        "part_number": "SEI-MECH-WR-STOP-001",
        "description": "Wing hard-stop pad candidate",
        "material": "AL6061-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_G07_PRIMARY_SUPPORT": {
        "relative": "01_native_parts/supports/G07_PRIMARY_SUPPORT_V2.SLDPRT",
        "part_number": "SEI-MECH-G07-BODY-V2",
        "description": "G07 hollow primary support body",
        "material": "AL7075-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_G07_PAD_CARRIER": {
        "relative": "01_native_parts/supports/G07_PAD_CARRIER_V2.SLDPRT",
        "part_number": "SEI-MECH-G07-CARRIER-V2",
        "description": "G07 replaceable pad carrier",
        "material": "AL6061-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_G07_CONTACT_PAD": {
        "relative": "01_native_parts/supports/G07_PTFE_CONTACT_PAD_V2.SLDPRT",
        "part_number": "SEI-MECH-G07-PAD-V2",
        "description": "50x50x3 G07 PTFE contact pad",
        "material": "PTFE-25GF",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_G08_PRIMARY_SUPPORT": {
        "relative": "01_native_parts/supports/G08_PRIMARY_SUPPORT_V2.SLDPRT",
        "part_number": "SEI-MECH-G08-BODY-V2",
        "description": "G08 hollow primary support body",
        "material": "AL7075-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_G08_PAD_CARRIER": {
        "relative": "01_native_parts/supports/G08_PAD_CARRIER_V2.SLDPRT",
        "part_number": "SEI-MECH-G08-CARRIER-V2",
        "description": "G08 replaceable pad carrier",
        "material": "AL6061-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_G08_CONTACT_PAD": {
        "relative": "01_native_parts/supports/G08_VMQ_CONTACT_PAD_V2.SLDPRT",
        "part_number": "SEI-MECH-G08-PAD-V2",
        "description": "30x30x2 G08 VMQ 60A contact pad",
        "material": "VMQ-60A",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_MID_BACKUP_SUPPORT": {
        "relative": "01_native_parts/supports/MID_BACKUP_SUPPORT_V2.SLDPRT",
        "part_number": "SEI-MECH-MID-BODY-V2",
        "description": "Mid backup-only support body; nominal 2 mm gap",
        "material": "AL7075-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_MID_PAD_CARRIER": {
        "relative": "01_native_parts/supports/MID_PAD_CARRIER_V2.SLDPRT",
        "part_number": "SEI-MECH-MID-CARRIER-V2",
        "description": "Mid backup support pad carrier",
        "material": "AL6061-T6",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_MID_CONTACT_PAD": {
        "relative": "01_native_parts/supports/MID_CONTACT_PAD_V2.SLDPRT",
        "part_number": "SEI-MECH-MID-PAD-V2",
        "description": "Mid backup support contact pad",
        "material": "VESPEL-SP1",
        "classification": "COMPETITION_PROTOTYPE_PHYSICAL_CANDIDATE",
    },
    "NEUTRAL_V4_ARM_HDRM_RELEASE_SWEEP_KEEP_OUT": {
        "relative": "01_native_parts/hdrm/ARM_HDRM_RELEASE_SWEEP_ENVELOPE.SLDPRT",
        "part_number": "SEI-MECH-HDRM-SWEEP-REF",
        "description": "6 mm -X operational release sweep reference envelope",
        "material": "NON_PHYSICAL",
        "classification": "ENVELOPE_REFERENCE_ONLY",
    },
    "NEUTRAL_V4_ARM_HDRM_60MM_FLANGE_SKELETON": {
        "relative": "01_native_parts/hdrm/ARM_HDRM_60MM_MOUNT_ENVELOPE.SLDPRT",
        "part_number": "SEI-MECH-HDRM-MOUNT-REF",
        "description": "60x60x10 competition HDRM mounting reference envelope",
        "material": "NON_PHYSICAL",
        "classification": "ENVELOPE_REFERENCE_ONLY",
    },
    "NEUTRAL_V4_CAMERA_SELECTION_KEEP_OUT_LINK6": {
        "relative": "01_native_parts/camera_harness/SERVICE_CAMERA_ENVELOPE.SLDPRT",
        "part_number": "SEI-MECH-CAM-ENV-001",
        "description": "40x34x26 service-camera selection envelope",
        "material": "NON_PHYSICAL",
        "classification": "CAMERA_MODEL_SELECTION_HOLD_ENVELOPE_ONLY",
    },
    "NEUTRAL_V4_HARNESS_STATIC_ROUTE_OD9_KEEP_OUT": {
        "relative": "01_native_parts/camera_harness/B601_OD9_STATIC_HARNESS_ENVELOPE.SLDPRT",
        "part_number": "SEI-MECH-HARNESS-OD9-REF",
        "description": "OD9 static harness route and bend-radius reference envelope",
        "material": "NON_PHYSICAL",
        "classification": "ENVELOPE_REFERENCE_ONLY",
    },
}

PROTECTED = (
    ("accepted_b601_urdf", ENGINEERING / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf", "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"),
    ("mass_inertia_budget", ENGINEERING / "stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv", "073C802527E35C9495188EEFD5D8BA51F524D326142CF2AB31E436BAD0899392"),
    ("v2_2_native_donor_top", ENGINEERING / "cad/Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM", "30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A"),
    ("b51_articulated_arm_donor", ENGINEERING / "cad/B5_1_B601_interface_closure_candidate/03_CAD/native_articulated/B51_ARTICULATED_20260728T008/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM", "603B87BBD4398FDDB3F732FFBFA7E1C080ED91ED6E0A026D56CBDCBA08DE2E22"),
    ("f3r1_frozen_top", ENGINEERING / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM", "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0"),
    ("f3r2_frozen_top", ENGINEERING / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM", "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0"),
)

IMPORT_INTEGER = {577: 0, 578: 1, 579: 2, 580: 0}
IMPORT_TOGGLE = {
    291: False,
    686: True,
    687: False,
    688: False,
    689: False,
    690: False,
    691: False,
    696: False,
    697: False,
    698: False,
    699: False,
    700: False,
    701: False,
}


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


class MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_json_once(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_text_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def value(obj: Any, name: str, *args: Any) -> Any:
    member = getattr(obj, name)
    return member(*args) if callable(member) else member


def unpack(result: Any) -> Tuple[Any, List[Any]]:
    if isinstance(result, tuple):
        return result[0], list(result[1:])
    return result, []


def as_list(item: Any) -> List[Any]:
    if item is None:
        return []
    return list(item) if isinstance(item, (tuple, list)) else [item]


def wrap(obj: Any, interface: str, types: Any, pythoncom: Any) -> Any:
    klass = getattr(types, interface)
    ole = obj._oleobj_.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
    return klass(ole)


def available_gib() -> float:
    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise GateError("MEMORY_QUERY_FAILED", "GlobalMemoryStatusEx returned false")
    return status.ullAvailPhys / (1024.0 ** 3)


def memory_gate() -> List[float]:
    samples = []
    for index in range(10):
        samples.append(round(available_gib(), 6))
        if index < 9:
            time.sleep(0.25)
    if not mo.override_allowed() and not all(sample >= MIN_AVAILABLE_GIB for sample in samples):
        raise GateError(
            "AVAILABLE_RAM_HOLD",
            "ten consecutive available-memory samples must be >= 6 GiB",
            {"samples_gib": samples, "minimum_gib": MIN_AVAILABLE_GIB},
        )
    return samples


def audit_protected() -> List[Dict[str, Any]]:
    rows = []
    for name, path, expected in PROTECTED:
        actual = sha256(path) if path.is_file() else None
        row = {
            "name": name,
            "path": str(path).replace("\\", "/"),
            "exists": path.is_file(),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "pass": actual == expected,
        }
        rows.append(row)
    if not all(row["pass"] for row in rows):
        raise GateError("PROTECTED_HASH_DRIFT", "one or more protected assets drifted", {"rows": rows})
    return rows


def load_and_audit_inputs() -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    if not V4_MANIFEST.is_file():
        raise GateError("V4_MANIFEST_MISSING", "V4 SolidWorks input manifest is missing")
    if sha256(V4_MANIFEST) != V4_MANIFEST_SHA256:
        raise GateError(
            "V4_MANIFEST_IDENTITY_FAIL",
            "V4 SolidWorks input manifest is not the Session-A anchored manifest",
            {"expected": V4_MANIFEST_SHA256, "actual": sha256(V4_MANIFEST)},
        )
    manifest = json.loads(V4_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema") != "F3R2_V4_SOLIDWORKS_ATTACH_INPUT_V1":
        raise GateError("V4_MANIFEST_SCHEMA_DRIFT", "unexpected V4 manifest schema")
    inputs = {str(item["role"]): item for item in manifest.get("inputs", [])}
    missing_roles = sorted(set(PART_CONTRACT) - set(inputs))
    if missing_roles:
        raise GateError("V4_INPUT_ROLE_MISSING", "neutral input roles are missing", {"roles": missing_roles})
    audit: List[Dict[str, Any]] = []
    for section in ("inputs", "templates"):
        for item in manifest.get(section, []):
            path = Path(str(item["path"]))
            actual_hash = sha256(path) if path.is_file() else None
            actual_bytes = path.stat().st_size if path.is_file() else None
            row = {
                "section": section,
                "role": item["role"],
                "path": str(path).replace("\\", "/"),
                "exists": path.is_file(),
                "expected_bytes": int(item["bytes"]),
                "actual_bytes": actual_bytes,
                "expected_sha256": str(item["sha256"]).upper(),
                "actual_sha256": actual_hash,
            }
            row["pass"] = (
                row["exists"]
                and row["actual_bytes"] == row["expected_bytes"]
                and row["actual_sha256"] == row["expected_sha256"]
            )
            audit.append(row)
    if not all(row["pass"] for row in audit):
        raise GateError("V4_INPUT_OR_TEMPLATE_DRIFT", "V4 input/template audit failed", {"rows": audit})
    return manifest, inputs, audit


def audit_g0() -> Dict[str, Any]:
    if not G0_READY.is_file():
        raise GateError("G0_READY_RECEIPT_MISSING", "Session-B G0 ready receipt does not exist")
    receipt = json.loads(G0_READY.read_text(encoding="utf-8"))
    if receipt.get("schema") != "F3R2_V5_G0_SMOKE_SESSION_B_V1":
        raise GateError("G0_READY_SCHEMA_FAIL", "unexpected G0 Session-B receipt schema")
    if receipt.get("verdict") != "G0_SOLIDWORKS_NATIVE_EXECUTION_READY":
        raise GateError("G0_READY_VERDICT_FAIL", "G0 receipt is not execution-ready")
    if G0_SMOKE_PART.exists():
        raise GateError("G0_TEMP_ASSET_NOT_DELETED", "G0 smoke part still exists")
    temporary = receipt.get("temporary_asset", {})
    if (
        temporary.get("bytes") != G0_SMOKE_PART_BYTES
        or temporary.get("sha256") != G0_SMOKE_PART_SHA256
        or not temporary.get("deleted")
        or temporary.get("exists_after_delete") is not False
    ):
        raise GateError("G0_TEMP_DELETE_EVIDENCE_FAIL", "G0 deletion evidence is incomplete")
    safety = receipt.get("safety", {})
    if safety != {
        "attach_only": True,
        "script_start_solidworks": False,
        "script_exit_solidworks": False,
        "changes_visible_or_user_control": False,
        "open_read_only": True,
        "v5_release_created": False,
    }:
        raise GateError("G0_SAFETY_CONTRACT_FAIL", "G0 safety declaration is incomplete or changed")
    session_a = receipt.get("session_a_evidence", {})
    if (
        not G0_SESSION_A_RECEIPT.is_file()
        or sha256(G0_SESSION_A_RECEIPT) != G0_SESSION_A_RECEIPT_SHA256
        or session_a.get("session_a_receipt_sha256") != G0_SESSION_A_RECEIPT_SHA256
        or session_a.get("session_a_pid") != G0_SESSION_A_PID
        or session_a.get("smoke_part_bytes") != G0_SMOKE_PART_BYTES
        or session_a.get("smoke_part_sha256") != G0_SMOKE_PART_SHA256
    ):
        raise GateError("G0_SESSION_A_CHAIN_FAIL", "G0 Session-A evidence chain is not intact")
    session_b = receipt.get("session_b_process", {})
    if (
        session_b.get("pid") in (None, G0_SESSION_A_PID)
        or session_b.get("major") != EXPECTED_SW_MAJOR
        or session_b.get("doc_count_pre") != 0
        or session_b.get("active_doc_is_null_pre") is not True
        or session_b.get("different_pid_from_session_a") is not True
        or os.path.normcase(str(session_b.get("executable", "")))
        != os.path.normcase(str(SOLIDWORKS_EXE).replace("\\", "/"))
    ):
        raise GateError("G0_SESSION_B_PROCESS_FAIL", "G0 Session-B process evidence is incomplete")
    cold = receipt.get("cold_reopen", {})
    memory_samples = receipt.get("memory_samples_gib", [])
    cold_dimensions = sorted(float(number) for number in cold.get("dimensions_m_sorted", []))
    expected_cold_dimensions = [0.01, 0.02, 0.02]
    cold_dimensions_pass = len(cold_dimensions) == 3 and all(
        abs(actual - expected) <= 0.00005
        for actual, expected in zip(cold_dimensions, expected_cold_dimensions)
    )
    if (
        len(memory_samples) != 10
        or (not mo.override_allowed() and not all(float(sample) >= MIN_AVAILABLE_GIB for sample in memory_samples))
        or cold.get("path") != str(G0_RUN / "G0_SMOKE_20X20X10.SLDPRT").replace("\\", "/")
        or cold.get("open_errors") != 0
        or cold.get("open_warnings") != 0
        or cold.get("rebuild_ok") is not True
        or cold.get("feature_count") != 19
        or cold.get("solid_body_count") != 1
        or not cold_dimensions_pass
    ):
        raise GateError("G0_COLD_REOPEN_EVIDENCE_FAIL", "G0 cold-reopen evidence is incomplete")
    protected_pre = receipt.get("protected_pre", [])
    protected_post = receipt.get("protected_post", [])
    if (
        len(protected_pre) != len(PROTECTED)
        or protected_pre != protected_post
        or not all(row.get("pass") is True for row in protected_pre)
    ):
        raise GateError("G0_PROTECTED_CHAIN_FAIL", "G0 protected PRE/POST evidence is not identical")
    solidworks_post = receipt.get("solidworks_post", {})
    if solidworks_post.get("doc_count") != 0 or solidworks_post.get("active_doc_is_null") is not True:
        raise GateError("G0_SESSION_B_POST_FAIL", "G0 Session-B did not end document-empty")
    predelete = receipt.get("predelete_receipt", {})
    if (
        not G0_PREDELETE_RECEIPT.is_file()
        or Path(str(predelete.get("path", ""))).resolve() != G0_PREDELETE_RECEIPT.resolve()
        or predelete.get("sha256") != sha256(G0_PREDELETE_RECEIPT)
    ):
        raise GateError("G0_PREDELETE_CHAIN_FAIL", "G0 pre-delete receipt chain is not intact")
    predelete_payload = json.loads(G0_PREDELETE_RECEIPT.read_text(encoding="utf-8"))
    if predelete_payload.get("verdict") != "G0_SMOKE_SESSION_B_COLD_REOPEN_PASS_PENDING_TEMP_DELETE":
        raise GateError("G0_PREDELETE_VERDICT_FAIL", "G0 pre-delete verdict is not the expected PASS")
    if receipt.get("next_authorized_action") != "CREATE_NEW_EXCLUSIVE_V5_RELEASE_ROOT":
        raise GateError("G0_NEXT_ACTION_FAIL", "G0 receipt does not authorize an exclusive V5 root")
    return {
        "path": str(G0_READY).replace("\\", "/"),
        "bytes": G0_READY.stat().st_size,
        "sha256": sha256(G0_READY),
        "verdict": receipt.get("verdict"),
        "session_b_pid": session_b.get("pid"),
        "temporary_asset_deleted": True,
    }


def release_root(run_id: str) -> Path:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise GateError(
            "RUN_ID_INVALID",
            "run id must match YYYYMMDDTHHMMSS_TOKEN using uppercase alphanumerics",
            {"run_id": run_id},
        )
    target = (ENGINEERING / f"{RELEASE_PREFIX}{run_id}").resolve()
    if target.parent != ENGINEERING.resolve():
        raise GateError("RUN_ROOT_SCOPE_FAIL", "release root escapes 20_engineering")
    return target


def create_release_tree(target: Path) -> None:
    existing_roots = sorted(
        path for path in ENGINEERING.glob(f"{RELEASE_PREFIX}*") if path.is_dir()
    )
    if existing_roots:
        raise GateError(
            "V5_GLOBAL_UNIQUENESS_FAIL",
            "a formal V5 native release root already exists",
            {"existing": [str(path).replace("\\", "/") for path in existing_roots]},
        )
    if target.exists():
        raise GateError("RUN_ROOT_ALREADY_EXISTS", "exclusive V5 run root already exists", {"path": str(target)})
    target.mkdir()
    for relative in DIRS:
        (target / relative).mkdir(parents=True, exist_ok=False)


def snapshot_preferences(sw: Any) -> Dict[str, Dict[str, Any]]:
    return {
        "integer": {str(key): int(sw.GetUserPreferenceIntegerValue(key)) for key in IMPORT_INTEGER},
        "toggle": {str(key): bool(sw.GetUserPreferenceToggle(key)) for key in IMPORT_TOGGLE},
    }


def target_preferences() -> Dict[str, Dict[str, Any]]:
    return {
        "integer": {str(key): int(setting) for key, setting in IMPORT_INTEGER.items()},
        "toggle": {str(key): bool(setting) for key, setting in IMPORT_TOGGLE.items()},
    }


def set_preferences(sw: Any, settings: Dict[str, Dict[str, Any]]) -> None:
    for key, setting in settings["integer"].items():
        sw.SetUserPreferenceIntegerValue(int(key), int(setting))
    for key, setting in settings["toggle"].items():
        sw.SetUserPreferenceToggle(int(key), bool(setting))


def feature_names_3d_interconnect(model: Any, types: Any, pythoncom: Any) -> List[str]:
    found: List[str] = []
    feature = value(model, "FirstFeature")
    count = 0
    while feature is not None and count < 10000:
        typed = wrap(feature, "IFeature", types, pythoncom)
        try:
            is_interconnect = bool(value(typed, "Is3DInterconnectFeature"))
        except Exception as exc:
            raise GateError(
                "THREE_D_INTERCONNECT_QUERY_FAIL",
                "cannot prove imported feature is not a 3D Interconnect feature",
                {"feature": str(value(typed, "Name")), "exception": repr(exc)},
            ) from exc
        if is_interconnect:
            found.append(str(value(typed, "Name")))
        feature = value(typed, "GetNextFeature")
        count += 1
    if count >= 10000:
        raise GateError("FEATURE_TRAVERSAL_LIMIT", "feature traversal exceeded 10000")
    return found


def external_reference_count(model: Any, label: str) -> int:
    failures = []
    for call in (("ListExternalFileReferencesCount2", ()), ("ListExternalFileReferencesCount", (False,))):
        try:
            return int(value(model, call[0], *call[1]))
        except Exception as exc:
            failures.append({"api": call[0], "exception": repr(exc)})
    raise GateError(
        "EXTERNAL_REFERENCE_QUERY_FAIL",
        f"cannot prove external-reference count for {label}",
        {"failures": failures},
    )


def auxiliary_reference_count(model: Any, label: str) -> int:
    try:
        return int(value(model, "ListAuxiliaryExternalFileReferencesCount"))
    except Exception as exc:
        raise GateError(
            "AUXILIARY_REFERENCE_QUERY_FAIL",
            f"cannot prove auxiliary-reference count for {label}",
            {"exception": repr(exc)},
        ) from exc


def body_facts(model: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    part = wrap(model, "IPartDoc", types, pythoncom)
    bodies = as_list(part.GetBodies2(0, False))
    boxes = []
    solid_flags = []
    for raw_body in bodies:
        body = wrap(raw_body, "IBody2", types, pythoncom)
        try:
            solid_flags.append(bool(value(body, "IsSolidBody")))
        except Exception:
            solid_flags.append(True)
        box = [float(number) * 1000.0 for number in as_list(value(body, "GetBodyBox"))]
        if len(box) == 6:
            boxes.append(box)
    overall = None
    if boxes:
        overall = [
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            min(box[2] for box in boxes),
            max(box[3] for box in boxes),
            max(box[4] for box in boxes),
            max(box[5] for box in boxes),
        ]
    return {
        "solid_body_count": len(bodies),
        "all_bodies_solid": bool(bodies) and all(solid_flags),
        "bounding_box_mm": overall,
    }


def set_properties(model: Any, role: str, contract: Dict[str, str], source: Path, run_id: str) -> None:
    properties = {
        "PartNumber": contract["part_number"],
        "Description": contract["description"],
        "Revision": "V5-A",
        "MaterialSpecification": contract["material"],
        "RELEASE_SCOPE": "COMPETITION_PROTOTYPE_MANUFACTURING_DEFINITION",
        "REPRESENTATION_LAYER": "L1_SOLIDWORKS_NATIVE_IMPORTED_GEOMETRY",
        "SOURCE_ROLE": role,
        "SOURCE_STEP": source.name,
        "SOURCE_STEP_SHA256": sha256(source),
        "CLASSIFICATION": contract["classification"],
        "RUN_ID": run_id,
        "L0_AUTHORITY": "ACCEPTED_B601_URDF_UNCHANGED",
        "MASS_BOUNDARY": "EXTERNAL_MECHANICAL_ONLY_DO_NOT_OVERRIDE_ACCEPTED_URDF",
        "AUTHORIZED_LAUNCH_LOAD": "HOLD",
        "FLIGHT_QUALIFICATION": "HOLD",
    }
    manager = model.Extension.CustomPropertyManager("")
    for name, property_value in properties.items():
        result = manager.Add3(str(name), 30, str(property_value), 2)
        if int(result) < 0:
            raise GateError("CUSTOM_PROPERTY_WRITE_FAIL", f"cannot set {name}", {"result": int(result)})


def save_native_part(model: Any, target: Path) -> Dict[str, Any]:
    if target.exists():
        raise GateError("NATIVE_TARGET_EXISTS", "native part target already exists", {"path": str(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    if not bool(model.ForceRebuild3(True)):
        raise GateError("PRE_SAVE_REBUILD_FAIL", "full rebuild failed before SaveAs", {"target": str(target)})
    returned = model.Extension.SaveAs(str(target), 0, 1, None, 0, 0)
    if not isinstance(returned, tuple) or len(returned) < 3:
        raise GateError(
            "NATIVE_SAVE_AS_RETURN_SHAPE_FAIL",
            "typed SaveAs did not return api/errors/warnings",
            {"returned": repr(returned)},
        )
    ok, outs = unpack(returned)
    errors = int(outs[0]) if len(outs) > 0 else None
    warnings = int(outs[1]) if len(outs) > 1 else None
    if not bool(ok) or errors != 0 or warnings != 0 or not target.is_file():
        raise GateError(
            "NATIVE_SAVE_AS_FAIL",
            "SaveAs did not create a valid native part",
            {"ok": bool(ok), "errors": errors, "warnings": warnings, "target": str(target)},
        )
    returned_final = model.Save3(1, 0, 0)
    if not isinstance(returned_final, tuple) or len(returned_final) < 3:
        raise GateError(
            "NATIVE_FINAL_SAVE_RETURN_SHAPE_FAIL",
            "typed Save3 did not return api/errors/warnings",
            {"returned": repr(returned_final)},
        )
    final_ok, final_outs = unpack(returned_final)
    final_errors = int(final_outs[0]) if len(final_outs) > 0 else None
    final_warnings = int(final_outs[1]) if len(final_outs) > 1 else None
    if not bool(final_ok) or final_errors != 0 or final_warnings != 0:
        raise GateError(
            "NATIVE_FINAL_SAVE_FAIL",
            "Save3 did not finalize the native part",
            {"ok": bool(final_ok), "errors": final_errors, "warnings": final_warnings},
        )
    return {
        "path": str(target).replace("\\", "/"),
        "bytes": target.stat().st_size,
        "sha256": sha256(target),
        "save_as_errors": errors,
        "save_as_warnings": warnings,
        "save3_errors": final_errors,
        "save3_warnings": final_warnings,
    }


def open_read_only(sw: Any, path: Path, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    before_count = int(value(sw, "GetDocumentCount"))
    raw_model = model = None
    try:
        returned = sw.OpenDoc6(str(path), 1, 3, "", 0, 0)
        if not isinstance(returned, tuple) or len(returned) < 3:
            raise GateError(
                "COLD_OPEN_RETURN_SHAPE_FAIL",
                "typed OpenDoc6 did not return model/errors/warnings",
                {"returned": repr(returned)},
            )
        raw_model, outs = unpack(returned)
        errors = int(outs[0])
        warnings = int(outs[1])
        if raw_model is None or errors != 0 or warnings != 0:
            raise GateError(
                "COLD_OPEN_FAIL",
                "OpenDoc6 failed for native part",
                {"path": str(path), "errors": errors, "warnings": warnings},
            )
        model = wrap(raw_model, "IModelDoc2", types, pythoncom)
        if not bool(value(model, "IsOpenedReadOnly")):
            raise GateError("COLD_OPEN_NOT_READ_ONLY", "native part did not open read-only", {"path": str(path)})
        return model, {
            "errors": errors,
            "warnings": warnings,
            "read_only": True,
        }
    except Exception:
        candidate = model if model is not None else raw_model
        if candidate is not None:
            try:
                sw.CloseDoc(str(value(candidate, "GetTitle")))
            except Exception:
                pass
        if int(value(sw, "GetDocumentCount")) != before_count:
            raise GateError(
                "COLD_OPEN_FAILURE_CLEANUP_FAIL",
                "failed cold-open document remained in the session",
            )
        raise


def import_one(
    sw: Any,
    types: Any,
    pythoncom: Any,
    source_item: Dict[str, Any],
    contract: Dict[str, str],
    target: Path,
    run_id: str,
) -> Dict[str, Any]:
    source = Path(str(source_item["path"]))
    expected_source_bytes = int(source_item["bytes"])
    expected_source_sha = str(source_item["sha256"]).upper()
    if (
        not source.is_file()
        or source.stat().st_size != expected_source_bytes
        or sha256(source) != expected_source_sha
    ):
        raise GateError("IMPORT_SOURCE_PRE_IDENTITY_FAIL", "STEP source drifted before import", {"source": str(source)})
    before = snapshot_preferences(sw)
    applied = target_preferences()
    model = None
    raw_model = None
    title = None
    if int(value(sw, "GetDocumentCount")) != 0 or value(sw, "ActiveDoc") is not None:
        raise GateError("IMPORT_SESSION_NOT_EMPTY", "each native import must begin document-empty")
    import_started = time.perf_counter()
    try:
        set_preferences(sw, applied)
        if snapshot_preferences(sw) != applied:
            raise GateError("IMPORT_PREFERENCE_READBACK_FAIL", "STEP import settings did not read back")
        import_data = sw.GetImportFileData(str(source))
        if import_data is None:
            raise GateError("GET_IMPORT_DATA_FAIL", "GetImportFileData returned null", {"source": str(source)})
        typed_import = wrap(import_data, "IImportStepData", types, pythoncom)
        typed_import.MapConfigurationData = False
        if bool(typed_import.MapConfigurationData):
            raise GateError(
                "STEP_MAP_CONFIGURATION_READBACK_FAIL",
                "MapConfigurationData did not remain false",
            )
        returned = sw.LoadFile4(str(source), "r", typed_import, 0)
        if not isinstance(returned, tuple) or len(returned) < 2:
            raise GateError(
                "CLASSIC_STEP_IMPORT_RETURN_SHAPE_FAIL",
                "typed LoadFile4 did not return model/errors",
                {"returned": repr(returned)},
            )
        raw_model, outs = unpack(returned)
        import_errors = int(outs[0])
        if raw_model is None or import_errors != 0:
            if raw_model is not None:
                try:
                    sw.CloseDoc(str(value(raw_model, "GetTitle")))
                except Exception:
                    pass
            raise GateError(
                "CLASSIC_STEP_IMPORT_FAIL",
                "LoadFile4 failed",
                {"source": str(source), "errors": import_errors},
            )
        model = wrap(raw_model, "IModelDoc2", types, pythoncom)
        title = str(value(model, "GetTitle"))
        if int(value(model, "GetType")) != 1:
            raise GateError("IMPORTED_DOCUMENT_NOT_PART", "STEP did not import as a part")
        interconnect = feature_names_3d_interconnect(model, types, pythoncom)
        if interconnect:
            raise GateError("THREE_D_INTERCONNECT_PRESENT", "linked import features remain", {"features": interconnect})
        external_before = external_reference_count(model, "imported_source_before_break")
        auxiliary_before = auxiliary_reference_count(model, "imported_source_before_break")
        try:
            model.Extension.BreakAllExternalFileReferences2(True)
        except Exception as exc:
            raise GateError(
                "BREAK_EXTERNAL_REFERENCE_FAIL",
                "BreakAllExternalFileReferences2 failed",
                {"exception": repr(exc)},
            ) from exc
        external_after = external_reference_count(model, "imported_source_after_break")
        auxiliary_after = auxiliary_reference_count(model, "imported_source_after_break")
        if external_after != 0 or auxiliary_after != 0:
            raise GateError(
                "IMPORTED_EXTERNAL_REFERENCE_HOLD",
                "native part retained external references",
                {"external": external_after, "auxiliary": auxiliary_after},
            )
        set_properties(model, str(source_item["role"]), contract, source, run_id)
        pre_facts = body_facts(model, types, pythoncom)
        if pre_facts["solid_body_count"] < 1 or not pre_facts["all_bodies_solid"]:
            raise GateError("IMPORTED_BODY_FAIL", "imported part has no valid solid body", pre_facts)
        save = save_native_part(model, target)
        title = str(value(model, "GetTitle"))
        saved_path = Path(str(value(model, "GetPathName"))).resolve()
        if saved_path != target.resolve():
            raise GateError(
                "POST_SAVE_DOCUMENT_PATH_FAIL",
                "active imported document did not switch to the V5 target",
                {"actual": str(saved_path), "expected": str(target.resolve())},
            )
    finally:
        restore_failure = None
        try:
            set_preferences(sw, before)
            restored = snapshot_preferences(sw)
            if restored != before:
                restore_failure = {"before": before, "restored": restored}
        except Exception as exc:
            restore_failure = {"exception": repr(exc), "before": before}
        try:
            candidate = model if model is not None else raw_model
            if candidate is not None:
                current_title = str(value(candidate, "GetTitle"))
                if current_title:
                    title = current_title
            if title:
                sw.CloseDoc(title)
        finally:
            if restore_failure is not None:
                raise GateError(
                    "IMPORT_PREFERENCE_RESTORE_FAIL",
                    "STEP import preferences were not restored",
                    restore_failure,
                )
    if int(value(sw, "GetDocumentCount")) != 0 or value(sw, "ActiveDoc") is not None:
        raise GateError("POST_SAVE_CLOSE_FAIL", "saved native part remained open before cold reopen")

    cold_model, cold_open = open_read_only(sw, target, types, pythoncom)
    cold_title = str(value(cold_model, "GetTitle"))
    try:
        if not bool(cold_model.ForceRebuild3(True)):
            raise GateError("COLD_REBUILD_FAIL", "cold native part rebuild failed", {"target": str(target)})
        cold_facts = body_facts(cold_model, types, pythoncom)
        cold_interconnect = feature_names_3d_interconnect(cold_model, types, pythoncom)
        cold_external = external_reference_count(cold_model, "cold_native_part")
        cold_auxiliary = auxiliary_reference_count(cold_model, "cold_native_part")
        if cold_facts["solid_body_count"] < 1 or not cold_facts["all_bodies_solid"]:
            raise GateError("COLD_BODY_FAIL", "cold native part body verification failed", cold_facts)
        if cold_interconnect or cold_external != 0 or cold_auxiliary != 0:
            raise GateError(
                "COLD_REFERENCE_FAIL",
                "cold native part retained linked geometry",
                {"interconnect": cold_interconnect, "external": cold_external, "auxiliary": cold_auxiliary},
            )
    finally:
        sw.CloseDoc(cold_title)
    if int(value(sw, "GetDocumentCount")) != 0 or value(sw, "ActiveDoc") is not None:
        raise GateError("POST_COLD_CLOSE_FAIL", "cold native part remained open")
    if source.stat().st_size != expected_source_bytes or sha256(source) != expected_source_sha:
        raise GateError("IMPORT_SOURCE_POST_IDENTITY_FAIL", "STEP source drifted during import", {"source": str(source)})
    return {
        "role": source_item["role"],
        "source": {
            "path": str(source).replace("\\", "/"),
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
        },
        "target": save,
        "import_mode": "CLASSIC_STEP_3D_INTERCONNECT_DISABLED",
        "import_arg": "r",
        "elapsed_seconds": round(time.perf_counter() - import_started, 3),
        "external_references_before": external_before,
        "auxiliary_references_before": auxiliary_before,
        "break_external_references_called": True,
        "external_references_after": external_after,
        "auxiliary_references_after": auxiliary_after,
        "pre_save_facts": pre_facts,
        "cold_open": cold_open,
        "cold_facts": cold_facts,
        "cold_three_d_interconnect": cold_interconnect,
        "cold_external_references": cold_external,
        "cold_auxiliary_references": cold_auxiliary,
        "verdict": "V5_NATIVE_PART_IMPORT_PASS",
    }


def attach_empty_session() -> Tuple[Any, Any, Any, Dict[str, Any]]:
    import pythoncom
    import win32com.client
    from win32com.client import gencache

    pythoncom.CoInitialize()
    types = gencache.GetModuleForTypelib(*SW_TLB)
    raw = win32com.client.GetActiveObject(SW_PROG_ID)
    sw = wrap(raw, "ISldWorks", types, pythoncom)
    revision = str(value(sw, "RevisionNumber"))
    try:
        major = int(revision.split(".", 1)[0])
    except ValueError as exc:
        raise GateError("SW_REVISION_PARSE_FAIL", "cannot parse SolidWorks revision", {"revision": revision}) from exc
    if major != EXPECTED_SW_MAJOR:
        raise GateError("SW_VERSION_FAIL", "SolidWorks major is not 32", {"revision": revision})
    if not revision.startswith("32.5."):
        raise GateError("SW_SERVICE_PACK_FAIL", "SolidWorks must be 2024 SP05 (revision 32.5.x)", {"revision": revision})
    doc_count = int(value(sw, "GetDocumentCount"))
    if doc_count != 0 or value(sw, "ActiveDoc") is not None:
        raise GateError("SW_SESSION_NOT_EMPTY", "SolidWorks must have zero open documents", {"document_count": doc_count})
    pid = int(value(sw, "GetProcessID"))
    import psutil

    process = psutil.Process(pid)
    executable = Path(process.exe()).resolve()
    if os.path.normcase(str(executable)) != os.path.normcase(str(SOLIDWORKS_EXE.resolve())):
        raise GateError(
            "SW_EXECUTABLE_FAIL",
            "attached process is not the pinned SOLIDWORKS executable",
            {"actual": str(executable), "expected": str(SOLIDWORKS_EXE.resolve())},
        )
    return sw, types, pythoncom, {
        "attach_only": True,
        "revision": revision,
        "major": major,
        "pid": pid,
        "executable": str(executable).replace("\\", "/"),
        "document_count": doc_count,
        "active_doc_is_null": True,
    }


def static_audit(run_id: Optional[str]) -> Dict[str, Any]:
    manifest, _inputs, input_audit = load_and_audit_inputs()
    protected = audit_protected()
    g0 = audit_g0() if G0_READY.is_file() else {
        "path": str(G0_READY).replace("\\", "/"),
        "exists": False,
        "verdict": "G0_READY_RECEIPT_MISSING",
    }
    target = release_root(run_id) if run_id else None
    static_inputs_pass = all(row["pass"] for row in input_audit + protected)
    g0_ready = g0.get("verdict") == "G0_SOLIDWORKS_NATIVE_EXECUTION_READY"
    existing_roots = sorted(path for path in ENGINEERING.glob(f"{RELEASE_PREFIX}*") if path.is_dir())
    return {
        "schema": "F3R2_V5_LOOP1_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "script": {
            "path": str(Path(__file__).resolve()).replace("\\", "/"),
            "bytes": Path(__file__).stat().st_size,
            "sha256": sha256(Path(__file__)),
        },
        "v4_manifest": {
            "path": str(V4_MANIFEST).replace("\\", "/"),
            "sha256": sha256(V4_MANIFEST),
            "schema": manifest["schema"],
            "registered_inputs": len(manifest["inputs"]),
            "registered_templates": len(manifest["templates"]),
        },
        "input_template_audit": input_audit,
        "protected_assets": protected,
        "g0": g0,
        "requested_run_id": run_id,
        "target": str(target).replace("\\", "/") if target else None,
        "target_exists": target.exists() if target else None,
        "existing_formal_v5_roots": [str(path).replace("\\", "/") for path in existing_roots],
        "g0_run_claim_exists": G0_V5_RUN_CLAIM.exists(),
        "contracted_native_parts": len(PART_CONTRACT),
        "execution_authorized": (
            static_inputs_pass
            and g0_ready
            and bool(target)
            and not target.exists()
            and not existing_roots
            and not G0_V5_RUN_CLAIM.exists()
        ),
        "verdict": (
            "V5_LOOP1_STATIC_AUDIT_PASS_G0_READY"
            if static_inputs_pass and g0_ready
            else "V5_LOOP1_STATIC_INPUT_AUDIT_PASS_G0_PENDING"
            if static_inputs_pass
            else "V5_LOOP1_STATIC_AUDIT_FAIL"
        ),
    }


def execute(run_id: str) -> int:
    target = release_root(run_id)
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_LOOP1_NEUTRAL_IMPORT_RECEIPT_V1",
        "run_id": run_id,
        "timestamp_start_utc": utc_now(),
        "target": str(target).replace("\\", "/"),
        "highest_claim_if_pass": "V5_LOOP1_NEUTRAL_PARTS_NATIVE_IMPORTED_NOT_ASSEMBLED",
        "prohibited_claims": [
            "FINAL_NATIVE_CAD_BASELINE",
            "MANUFACTURING_RELEASED_BASELINE",
            "F3R2_V5_COMPETITION_NATIVE_MECHANICAL_BASELINE_CLOSED",
        ],
    }
    sw = types = pythoncom = None
    created = False
    try:
        manifest, inputs, input_audit = load_and_audit_inputs()
        result["g0"] = audit_g0()
        result["protected_pre"] = audit_protected()
        result["memory_samples_gib"] = memory_gate()
        sw, types, pythoncom, session = attach_empty_session()
        result["solidworks"] = session
        if target.exists():
            raise GateError("RUN_ROOT_ALREADY_EXISTS", "exclusive V5 root already exists")
        existing_roots = sorted(path for path in ENGINEERING.glob(f"{RELEASE_PREFIX}*") if path.is_dir())
        if existing_roots:
            raise GateError(
                "V5_GLOBAL_UNIQUENESS_FAIL",
                "a formal V5 native release root already exists",
                {"existing": [str(path).replace("\\", "/") for path in existing_roots]},
            )
        if G0_V5_RUN_CLAIM.exists():
            raise GateError("G0_RUN_ALREADY_CLAIMED", "the G0 receipt is already bound to a V5 run")
        claim = {
            "schema": "F3R2_V5_EXCLUSIVE_RUN_CLAIM_V1",
            "timestamp_utc": utc_now(),
            "run_id": run_id,
            "target": str(target).replace("\\", "/"),
            "g0_ready_receipt_sha256": result["g0"]["sha256"],
            "solidworks_pid": session["pid"],
        }
        write_json_once(G0_V5_RUN_CLAIM, claim)
        result["exclusive_run_claim"] = {
            **claim,
            "path": str(G0_V5_RUN_CLAIM).replace("\\", "/"),
            "sha256": sha256(G0_V5_RUN_CLAIM),
        }
        create_release_tree(target)
        created = True
        write_json_once(target / "00_authority/V5_G0_GATE_REFERENCE.json", result["g0"])
        write_json_once(target / "00_authority/V5_PROTECTED_BASELINE_PRE.json", {"assets": result["protected_pre"]})
        write_json_once(
            target / "00_authority/V5_BUILD_INPUT_AUDIT.json",
            {
                "v4_manifest_path": str(V4_MANIFEST).replace("\\", "/"),
                "v4_manifest_sha256": sha256(V4_MANIFEST),
                "inputs_and_templates": input_audit,
                "admitted_neutral_roles": sorted(PART_CONTRACT),
            },
        )
        script_copy = target / "99_tools" / Path(__file__).name
        shutil.copy2(Path(__file__).resolve(), script_copy)
        result["script_copy"] = {
            "path": script_copy.relative_to(target).as_posix(),
            "bytes": script_copy.stat().st_size,
            "sha256": sha256(script_copy),
        }
        write_text_once(
            target / "PROJECT_START_HERE.md",
            "# F3R2 V5 native mechanical release\n\n"
            f"Run ID: `{run_id}`\n\n"
            "Current status: `LOOP1_NEUTRAL_PART_IMPORT_IN_PROGRESS`.\n\n"
            "This tree is a V5 successor. V4 and all frozen baselines remain read-only. "
            "No final mechanical-baseline claim is authorized until all three engineering "
            "loops, Pack-and-Go, new-session cold reopen, drawings/BOM, review book and final Gate pass.\n",
        )

        imports = []
        for role, contract in PART_CONTRACT.items():
            imports.append(
                import_one(
                    sw,
                    types,
                    pythoncom,
                    inputs[role],
                    contract,
                    target / contract["relative"],
                    run_id,
                )
            )
        result["native_parts"] = imports
        result["native_part_count"] = len(imports)
        if int(value(sw, "GetDocumentCount")) != 0 or value(sw, "ActiveDoc") is not None:
            raise GateError("POST_IMPORT_SESSION_NOT_EMPTY", "documents remain open after imports")
        result["protected_post"] = audit_protected()
        result["protected_unchanged"] = result["protected_pre"] == result["protected_post"]
        if not result["protected_unchanged"]:
            raise GateError("PROTECTED_POST_DRIFT", "protected hashes changed during import")
        result["timestamp_end_utc"] = utc_now()
        result["verdict"] = "V5_LOOP1_NEUTRAL_NATIVE_PART_IMPORT_PASS"
        result["next_required_action"] = "BUILD_NATIVE_SUBASSEMBLIES_WITH_MATES_AND_CONFIGURATIONS"
        receipt = target / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
        write_json_once(receipt, result)
        manifest_path = target / "14_release/V5_LOOP1_NATIVE_PART_MANIFEST_SHA256.txt"
        lines = []
        for item in imports:
            file_path = Path(item["target"]["path"])
            lines.append(f"{sha256(file_path)}  {file_path.stat().st_size}  {file_path.relative_to(target).as_posix()}")
        write_text_once(manifest_path, "\n".join(sorted(lines)) + "\n")
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "run_root": str(target).replace("\\", "/"),
                    "native_part_count": len(imports),
                    "receipt": str(receipt).replace("\\", "/"),
                    "receipt_sha256": sha256(receipt),
                    "manifest_sha256": sha256(manifest_path),
                    "solidworks_left_running": True,
                    "solidworks_document_count": int(value(sw, "GetDocumentCount")),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except GateError as exc:
        created = created or target.exists()
        result.update({"verdict": exc.code, "reason": str(exc), "detail": exc.detail, "timestamp_end_utc": utc_now()})
        if created:
            failure = target / f"13_validation/V5_LOOP1_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
            try:
                write_json_once(failure, result)
                result["failure_receipt"] = str(failure).replace("\\", "/")
            except Exception as receipt_error:
                result["failure_receipt_error"] = repr(receipt_error)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except Exception as exc:
        created = created or target.exists()
        result.update(
            {
                "verdict": "V5_LOOP1_UNEXPECTED_EXCEPTION",
                "reason": repr(exc),
                "traceback": traceback.format_exc(),
                "timestamp_end_utc": utc_now(),
            }
        )
        if created:
            failure = target / f"13_validation/V5_LOOP1_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
            try:
                write_json_once(failure, result)
            except Exception:
                pass
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        sw = None
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="read-only static audit")
    audit.add_argument("--run-id")
    run = sub.add_parser("execute", help="create the V5 root and import the 20 neutral native parts")
    run.add_argument("--run-id", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        print(json.dumps(static_audit(args.run_id), ensure_ascii=False, indent=2))
        return 0
    return execute(args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
