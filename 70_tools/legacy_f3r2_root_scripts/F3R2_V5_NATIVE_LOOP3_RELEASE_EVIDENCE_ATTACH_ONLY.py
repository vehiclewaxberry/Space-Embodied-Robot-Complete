#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F3R2 V5 Loop-3 Release / Evidence fail-closed acceptance framework.

This program is intentionally attach-only.  It never starts, stops, kills or
creates a SolidWorks process.  ``audit`` is filesystem-only.  ``session-a`` and
``session-b`` attach to an already running, empty SolidWorks 2024 SP05 session
through the pinned GetActiveObject-only Loop-1 helper.  Session B must have a
different process identity and creation time from Session A.

Loop-3 is documentation, reference, packaging and non-scientific metadata
closure only.  It does not create or modify mechanical geometry and it never
overwrites the accepted B601 URDF mass/inertia truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import shutil
import struct
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
RUN_ROOT = ENGINEERING / "F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
VALIDATION = RUN_ROOT / "13_validation"
RELEASE = RUN_ROOT / "14_release"

BASE_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_SHA256 = "1F589D3FAE23D64F2364B1CE98FA232A1AA19648398521E55CB5C7F85D0B6062"
LOOP1E_SCRIPT = ROOT / "70_tools/legacy_f3r2_root_scripts/F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py"
LOOP1E_SCRIPT_SHA256 = "675EBCC3B95984EAB301378518B5DE2E11EDA8ACE1E73AD7950FBFDDC5AFF0A2"
SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP3_RELEASE_EVIDENCE_ATTACH_ONLY.py"

G0_RECEIPT = ENGINEERING / "_MFINAL_G0_SMOKE_20260809T172928_P4E8/G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json"
LOOP1E_RECEIPT = VALIDATION / "V5_LOOP1E_TOP_ASSEMBLY_RECEIPT.json"
LOOP2_RECEIPT = VALIDATION / "V5_LOOP2_MOTION_ROBOTICS_RECEIPT.json"
TOP = RUN_ROOT / "03_top_assembly/SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM"

# ``None`` is an explicit registration gate, never a wildcard.  Once a
# write-once upstream receipt is produced its final SHA must be patched here.
UPSTREAM: Tuple[Dict[str, Any], ...] = (
    {"stage": "G0", "path": G0_RECEIPT, "sha256": "58F8240B1D158867C1B61B09B4A098F5AB670141A3CFEE983F5AD2A637CA5CA6", "schema": None, "verdicts": ("G0_SOLIDWORKS_NATIVE_EXECUTION_READY",)},
    {"stage": "LOOP1E", "path": LOOP1E_RECEIPT, "sha256": None, "schema": "F3R2_V5_LOOP1E_TOP_ASSEMBLY_RECEIPT_V1", "verdicts": ("V5_LOOP1E_NATIVE_TOP_ASSEMBLY_LOOP2_CONTRACT_COLD_REOPEN_PASS",)},
    {"stage": "LOOP2", "path": LOOP2_RECEIPT, "sha256": None, "schema": "F3R2_V5_LOOP2_MOTION_ROBOTICS_RECEIPT_V1", "verdicts": ("V5_LOOP2_NATIVE_DEFINED_SEGMENTS_VERIFIED_POSE_AUTHORIZATION_REQUIRED", "V5_LOOP2_MOTION_ROBOTICS_FULL_GEOMETRIC_CHAIN_PASS")},
)

COMPLETION_MATRIX = VALIDATION / "V5_COMPLETION_EVIDENCE_MATRIX.csv"
PROTECTED_PRE = RUN_ROOT / "00_authority/V5_PROTECTED_BASELINE_PRE.json"
MASS_BOUNDARY_SEED = RUN_ROOT / "06_mass_properties/V5_MASS_BOUNDARY.yaml"
POSE_AUTHORITY = RUN_ROOT / "04_configurations/V5_POSE_AUTHORITY_REGISTER.csv"
CONTROL_BASELINE = RUN_ROOT / "00_authority/V5_CONTROL_BASELINE.yaml"
DRAWING_TEMPLATE = Path(r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\gb_a3.drwdot")
SHEET_FORMAT = Path(r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\lang\Chinese-Simplified\sheetformat\a3 - gb.slddrt")

FIXED_INPUTS: Tuple[Tuple[str, Path, str], ...] = (
    ("base_helper", BASE_HELPER, BASE_HELPER_SHA256),
    ("base_helper_v5_copy", BASE_HELPER_COPY, BASE_HELPER_SHA256),
    ("loop1e_script_design_basis", LOOP1E_SCRIPT, LOOP1E_SCRIPT_SHA256),
    ("completion_matrix_design_basis", COMPLETION_MATRIX, "CE57D3141C54C6494E2E110837CE80A8E4A46A9ACDC6831D98C5C70F2BC97D16"),
    ("protected_pre_register", PROTECTED_PRE, "EB95A5B4F611BBFB119B6F88A8F25C8DA81B4EA2A3626406C009BF9D05B0B69C"),
    ("mass_boundary_seed", MASS_BOUNDARY_SEED, "23570C102A0F1072FB1EF528AEF3B5E66B16547C8112D56DDBA1E3C71CD4373A"),
    ("pose_authority", POSE_AUTHORITY, "1EB0D4CF3A7CC2B0F785B7C465C3BD89990A6F0647806B12C06BC931F0A3C326"),
    ("control_baseline", CONTROL_BASELINE, "6F10BF844B975F416FAB0B7BB02CB82D984A9CC8A5BF81D442870C7EBE554B75"),
    ("drawing_template", DRAWING_TEMPLATE, "B376D09B3937C02A57B6496D24F55FF0637243F7FAD215987F9E57610B10210E"),
    ("sheet_format", SHEET_FORMAT, "ED0133F69A8A1701CF2A3D71E2712E64076CCC28E644493B975029BE1ADD4C63"),
)

ACCEPTED_URDF = ENGINEERING / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"

# The accepted URDF remains the L0 mass/inertia authority.  Loop3 records only
# the external mechanical contribution and is never permitted to rewrite or
# replace this file.
FIXED_INPUTS = (*FIXED_INPUTS, ("accepted_b601_urdf_l0", ACCEPTED_URDF, ACCEPTED_URDF_SHA256))

MASS_CSV = RUN_ROOT / "06_mass_properties/V5_EXTERNAL_MECHANICAL_MASS_PROPERTIES.csv"
MASS_SUMMARY = RUN_ROOT / "06_mass_properties/V5_EXTERNAL_MECHANICAL_MASS_SUMMARY.json"
MASS_ITEMS = (
    "Stage_A", "Stage_B", "wing_root_left", "wing_root_right", "G07", "G08", "Mid",
    "pads", "springs", "HDRM", "camera_bracket", "camera_or_envelope", "harness",
    "gripper", "fasteners", "pins",
)
MASS_COLUMNS = (
    "item_id", "native_path", "native_sha256", "configuration", "source_class",
    "mass_kg", "com_x_m", "com_y_m", "com_z_m", "ixx_kg_m2", "iyy_kg_m2",
    "izz_kg_m2", "ixy_kg_m2", "ixz_kg_m2", "iyz_kg_m2", "material_or_basis",
    "accepted_urdf_excluded", "notes",
)

DRAWING_REGISTER = RUN_ROOT / "07_drawings/V5_DRAWING_REGISTER.csv"
DRAWING_SPECS: Tuple[Tuple[str, str, Path], ...] = (
    ("01_STAGE_A", "01_STAGE_A_INTERFACE_RING", RUN_ROOT / "01_native_parts/adapter/B601_INTERFACE_STAGE_A_REV_B2.SLDPRT"),
    ("02_STAGE_B", "02_STAGE_B_LOAD_ADAPTER", RUN_ROOT / "01_native_parts/adapter/B601_LOAD_ADAPTER_STAGE_B_REV_B2.SLDPRT"),
    ("03_WING_ROOT", "03_WING_ROOT_CLEVIS", RUN_ROOT / "02_native_subassemblies/LEFT_WING_ROOT_TRUE_HINGE.SLDASM"),
    ("04_G07", "04_G07_PRIMARY_SUPPORT", RUN_ROOT / "01_native_parts/supports/G07_PRIMARY_SUPPORT_V2.SLDPRT"),
    ("05_G08", "05_G08_PRIMARY_SUPPORT", RUN_ROOT / "01_native_parts/supports/G08_PRIMARY_SUPPORT_V2.SLDPRT"),
    ("06_MID", "06_MID_BACKUP_SUPPORT", RUN_ROOT / "01_native_parts/supports/MID_BACKUP_SUPPORT_V2.SLDPRT"),
    ("07_HDRM", "07_HDRM_BRACKET", RUN_ROOT / "02_native_subassemblies/ARM_HDRM_FUNCTIONAL_ENVELOPE.SLDASM"),
    ("08_CAMERA", "08_CAMERA_BRACKET", RUN_ROOT / "02_native_subassemblies/SERVICE_CAMERA_INTERFACE_HOLD.SLDASM"),
    ("09_GRIPPER", "09_GRIPPER_INTERFACES", RUN_ROOT / "02_native_subassemblies/B601_GRIPPER.SLDASM"),
)
DRAWING_COLUMNS = (
    "drawing_id", "slddrw_path", "slddrw_sha256", "pdf_path", "pdf_sha256",
    "source_native_path", "source_native_sha256", "part_number", "revision", "material",
    "datum", "critical_dimensions", "holes_threads", "gd_t", "surface_treatment",
    "inspection_dimensions", "sheet_count", "view_count", "release_scope",
)

BOM = RUN_ROOT / "08_bom/V5_NATIVE_TOP_BOM.csv"
BOM_COLUMNS = (
    "item_no", "level", "parent_component", "component_name", "part_number", "revision",
    "quantity", "material", "native_path", "native_sha256", "configuration", "source_class",
    "release_scope", "status", "holds",
)

FASTENER_REGISTER = RUN_ROOT / "00_authority/V5_FASTENER_REGISTER.csv"
FASTENER_COLUMNS = (
    "interface", "fastener_id", "quantity", "size", "grade_material", "washer",
    "thread_engagement", "assembly_torque_nm", "locking_method", "tightening_sequence",
    "inspection", "source_or_basis", "status", "formal_launch_fastener_mos",
)

DIGITAL_DIR = RUN_ROOT / "09_digital_thread"
DIGITAL_FILES: Tuple[Path, ...] = tuple(DIGITAL_DIR / name for name in (
    "V5_FRAME_MAPPING.yaml",
    "V5_LINK_COMPONENT_MAPPING.csv",
    "V5_COLLISION_ASSET_MANIFEST.csv",
    "V5_MASS_BOUNDARY.yaml",
    "V5_ACTION_MASK_RULES.yaml",
    "V5_MECHANICAL_STATE_MACHINE.yaml",
))

PACK_ROOT = RUN_ROOT / "10_pack_and_go/V5_PACK_AND_GO"
PACK_TOP = PACK_ROOT / "03_top_assembly/SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM"
PACK_LEDGER = RUN_ROOT / "10_pack_and_go/V5_PACK_AND_GO_REFERENCE_LEDGER.csv"
PACK_PROOF = RUN_ROOT / "10_pack_and_go/V5_PACK_AND_GO_PROOF.json"
PACK_LEDGER_COLUMNS = (
    "configuration", "component", "resolved_path", "resolved_sha256", "exists",
    "inside_package", "critical_external", "missing",
)

SHOT_NAMES = (
    "01_deployed_isometric", "02_deployed_top", "03_service", "04_B601_interface",
    "05_Stage_A_B_section", "06_wing_root", "07_G07", "08_G08", "09_Mid_2mm",
    "10_HDRM_locked", "11_HDRM_released", "12_camera_FOV", "13_harness_route",
    "14_gripper_OPEN", "15_gripper_PREGRASP", "16_gripper_CLOSED",
    "17_Q_DEPLOYED_HOME", "18_Q_SERVICE_READY", "19_critical_clearance",
    "20_exploded_assembly", "21_engineering_drawing_sample", "22_BOM",
)
SHOT_MANIFEST = RUN_ROOT / "11_screenshots/V5_22_SHOT_MANIFEST.csv"
SHOT_MANIFEST_COLUMNS = (
    "shot_id", "raw_path", "raw_sha256", "annotated_path", "annotated_sha256",
    "configuration_or_state", "view_or_evidence", "reviewer", "review_status", "notes",
)

CLAIMS = RELEASE / "V5_RELEASE_CLAIMS.json"
HIGHEST_ALLOWED_CLAIM = "F3R2_V5_COMPETITION_NATIVE_MECHANICAL_BASELINE_CLOSED"
PROHIBITED_CLAIMS = (
    "FINAL_NATIVE_CAD_BASELINE",
    "MANUFACTURING_RELEASED_BASELINE",
    "FLIGHT_READY",
    "LAUNCH_QUALIFIED",
    "FULLY_AUTHORIZED_SERVICE_AND_GRASP_TRAJECTORY",
    "FLIGHT_MANUFACTURING_RELEASE",
    "OEM_B601_INTERFACE_VERIFIED",
)
REQUIRED_HOLDS = (
    "AUTHORIZED_LAUNCH_LOAD_HOLD",
    "FLIGHT_QUALIFICATION_HOLD",
    "THERMAL_VACUUM_HOLD",
    "RANDOM_VIBRATION_HOLD",
    "FORMAL_FASTENER_MOS_HOLD",
    "PHYSICAL_TRIAL_FIT_HOLD",
    "FINAL_FLEXIBLE_CERTIFICATION_LIMITATION",
)

SESSION_A_CHECKPOINT = VALIDATION / "V5_LOOP3_SESSION_A_CHECKPOINT.json"
SESSION_B_CHECKPOINT = VALIDATION / "V5_LOOP3_SESSION_B_CHECKPOINT.json"
ACCEPTANCE_MATRIX = VALIDATION / "V5_LOOP3_RELEASE_EVIDENCE_ACCEPTANCE_MATRIX.csv"
ACCEPTANCE_MATRIX_COLUMNS = (
    "gate_id", "status", "release_blocking", "evidence_path", "evidence_sha256", "detail",
)
FINAL_MANIFEST = RELEASE / "V5_LOOP3_RELEASE_MANIFEST_SHA256.txt"
FINAL_RECEIPT = VALIDATION / "V5_LOOP3_RELEASE_EVIDENCE_RECEIPT.json"

SW_DOC_ASSEMBLY = 2
SW_DOC_DRAWING = 3
SW_OPEN_SILENT_READONLY = 3


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Any = None):
        super().__init__(message)
        self.code = code
        self.detail = detail


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    return {
        "path": norm(path),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256(path) if path.is_file() else None,
    }


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise GateError("JSON_ROOT_FAIL", "JSON root must be an object", {"path": norm(path)})
    return payload


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        return fields, [dict(row) for row in reader]


def write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_text_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def copy_once(source: Path, target: Path) -> None:
    if target.exists():
        if not target.is_file() or sha256(target) != sha256(source):
            raise GateError("SCRIPT_COPY_DRIFT", "existing Loop3 script copy differs", {"path": norm(target)})
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if sha256(target) != sha256(source):
        raise GateError("SCRIPT_COPY_FAIL", "Loop3 script copy hash readback failed", {"path": norm(target)})


def status(identifier: str, state: str, **detail: Any) -> Dict[str, Any]:
    if state not in {"PASS", "PENDING", "FAIL"}:
        raise ValueError(state)
    return {"id": identifier, "status": state, "pass": state == "PASS", **detail}


def fixed_audit() -> List[Dict[str, Any]]:
    rows = []
    for name, path, expected in FIXED_INPUTS:
        actual = sha256(path) if path.is_file() else None
        rows.append({"name": name, "path": norm(path), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    return rows


def protected_snapshot() -> List[Dict[str, Any]]:
    if not PROTECTED_PRE.is_file():
        raise GateError("PROTECTED_REGISTER_MISSING", "V5 protected PRE register is missing")
    assets = load_json(PROTECTED_PRE).get("assets")
    if not isinstance(assets, list) or not assets:
        raise GateError("PROTECTED_REGISTER_EMPTY", "V5 protected PRE register has no assets")
    rows = []
    for item in assets:
        path = Path(str(item.get("path", "")))
        expected = str(item.get("expected_sha256", "")).upper()
        actual = sha256(path) if path.is_file() else None
        rows.append({"name": item.get("name"), "path": norm(path), "expected_sha256": expected, "actual_sha256": actual, "pass": bool(expected and actual == expected)})
    if not all(row["pass"] for row in rows):
        raise GateError("PROTECTED_HASH_DRIFT", "one or more protected assets drifted", rows)
    return rows


def upstream_audit() -> List[Dict[str, Any]]:
    rows = []
    for contract in UPSTREAM:
        path = Path(contract["path"])
        expected = contract["sha256"]
        row: Dict[str, Any] = {
            "stage": contract["stage"], "path": norm(path), "exists": path.is_file(),
            "expected_sha256": expected, "actual_sha256": sha256(path) if path.is_file() else None,
            "hash_registered": expected is not None, "expected_schema": contract["schema"],
            "allowed_verdicts": list(contract["verdicts"]),
        }
        if path.is_file():
            try:
                payload = load_json(path)
                row["actual_schema"] = payload.get("schema")
                row["actual_verdict"] = payload.get("verdict")
                if contract["stage"] == "LOOP2":
                    row["final_gate_eligible"] = payload.get("final_gate_eligible") is True
                    row["pose_authorization_hold"] = payload.get("verdict") == "V5_LOOP2_NATIVE_DEFINED_SEGMENTS_VERIFIED_POSE_AUTHORIZATION_REQUIRED"
            except Exception as exc:
                row["parse_error"] = repr(exc)
        identity = bool(
            row["exists"] and expected is not None and row["actual_sha256"] == expected
            and (contract["schema"] is None or row.get("actual_schema") == contract["schema"])
            and row.get("actual_verdict") in contract["verdicts"]
        )
        row["pass"] = identity
        row["status"] = "PASS" if identity else "PENDING" if (not row["exists"] or expected is None) else "FAIL"
        rows.append(row)
    return rows


def safe_audit(identifier: str, function: Any) -> Dict[str, Any]:
    try:
        return function()
    except Exception as exc:
        return status(identifier, "FAIL", reason=str(exc), code=getattr(exc, "code", "AUDIT_EXCEPTION"), detail=getattr(exc, "detail", None))


def finite_vector(value: Any, length: int) -> bool:
    return isinstance(value, list) and len(value) == length and all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in value)


def physical_inertia(ixx: float, iyy: float, izz: float, ixy: float, ixz: float, iyz: float, tolerance: float = 1.0e-12) -> bool:
    # Symmetric inertia tensor about a stated CoM must be positive
    # semidefinite.  Principal minors plus the standard triangle inequalities
    # provide a dependency-free fail-closed check.
    determinant = ixx * iyy * izz + 2.0 * ixy * ixz * iyz - ixx * iyz * iyz - iyy * ixz * ixz - izz * ixy * ixy
    scale = max(1.0, abs(ixx), abs(iyy), abs(izz))
    return bool(
        min(ixx, iyy, izz) >= -tolerance
        and ixx * iyy - ixy * ixy >= -tolerance * scale * scale
        and ixx * izz - ixz * ixz >= -tolerance * scale * scale
        and iyy * izz - iyz * iyz >= -tolerance * scale * scale
        and determinant >= -tolerance * scale * scale * scale
        and ixx + iyy >= izz - tolerance * scale
        and ixx + izz >= iyy - tolerance * scale
        and iyy + izz >= ixx - tolerance * scale
    )


def validate_mass_summary(payload: Mapping[str, Any], calculated_total: float, csv_hash: str) -> bool:
    inertia = payload.get("external_inertia_about_external_com_kg_m2")
    inertia_ok = (
        isinstance(inertia, list)
        and len(inertia) == 3
        and all(finite_vector(row, 3) for row in inertia)
        and all(abs(float(inertia[row][column]) - float(inertia[column][row])) <= 1.0e-12 for row in range(3) for column in range(3))
        and physical_inertia(float(inertia[0][0]), float(inertia[1][1]), float(inertia[2][2]), float(inertia[0][1]), float(inertia[0][2]), float(inertia[1][2]))
    )
    return bool(
        payload.get("schema") == "F3R2_V5_EXTERNAL_MECHANICAL_MASS_SUMMARY_V1"
        and payload.get("boundary_definition") == "V5_EXTERNAL_MECHANICAL_ONLY_EXCLUDES_ACCEPTED_B601_URDF"
        and payload.get("mass_properties_coordinate_frame") == "SPACECRAFT_WORLD"
        and payload.get("source_csv_sha256") == csv_hash
        and payload.get("accepted_b601_urdf", {}).get("sha256") == ACCEPTED_URDF_SHA256
        and payload.get("accepted_b601_urdf", {}).get("cad_override_allowed") is False
        and payload.get("external_mechanical_only") is True
        and payload.get("accepted_urdf_overwritten") is False
        and finite_vector(payload.get("external_system_com_m"), 3)
        and inertia_ok
        and math.isclose(float(payload.get("total_external_mass_kg", float("nan"))), calculated_total, rel_tol=0.0, abs_tol=1.0e-9)
        and payload.get("verdict") == "V5_EXTERNAL_MECHANICAL_MASS_COM_INERTIA_SEPARATE_PASS"
    )


def audit_mass() -> Dict[str, Any]:
    if not MASS_CSV.is_file() or not MASS_SUMMARY.is_file():
        return status("MASS", "PENDING", missing=[norm(path) for path in (MASS_CSV, MASS_SUMMARY) if not path.is_file()])
    fields, rows = read_csv(MASS_CSV)
    missing_columns = [name for name in MASS_COLUMNS if name not in fields]
    if missing_columns or not rows:
        return status("MASS", "FAIL", missing_columns=missing_columns, row_count=len(rows))
    seen = {row.get("item_id", "") for row in rows}
    missing_items = sorted(set(MASS_ITEMS) - seen)
    errors = []
    total = 0.0
    numeric = MASS_COLUMNS[5:15]
    for index, row in enumerate(rows, 2):
        try:
            values = [float(row[name]) for name in numeric]
            if not all(math.isfinite(value) for value in values) or values[0] <= 0.0:
                raise ValueError("non-finite or negative mass")
            if not physical_inertia(values[4], values[5], values[6], values[7], values[8], values[9]):
                raise ValueError("inertia tensor is not physical positive-semidefinite CoM inertia")
            total += values[0]
        except Exception as exc:
            errors.append({"row": index, "reason": str(exc)})
        if row.get("source_class") not in {"MEASURED_CAD", "VENDOR", "ESTIMATED"}:
            errors.append({"row": index, "reason": "SOURCE_CLASS_INVALID"})
        if row.get("accepted_urdf_excluded", "").strip().lower() != "true":
            errors.append({"row": index, "reason": "ACCEPTED_URDF_NOT_EXCLUDED"})
        native = Path(row.get("native_path", ""))
        if native.resolve() == ACCEPTED_URDF.resolve():
            errors.append({"row": index, "reason": "ACCEPTED_URDF_INCLUDED_AS_CAD_MASS"})
        if not native.is_file() or sha256(native) != row.get("native_sha256", "").upper():
            errors.append({"row": index, "reason": "NATIVE_IDENTITY_FAIL"})
        if not row.get("configuration", "").strip() or not row.get("material_or_basis", "").strip():
            errors.append({"row": index, "reason": "CONFIGURATION_OR_BASIS_EMPTY"})
    summary = load_json(MASS_SUMMARY)
    summary_pass = validate_mass_summary(summary, total, sha256(MASS_CSV))
    state = "PASS" if not missing_items and not errors and summary_pass else "FAIL"
    return status("MASS", state, csv=file_fact(MASS_CSV), summary=file_fact(MASS_SUMMARY), row_count=len(rows), missing_items=missing_items, errors=errors, calculated_total_external_mass_kg=total, summary_contract_pass=summary_pass, accepted_urdf=file_fact(ACCEPTED_URDF), accepted_urdf_overwritten=False)


def ole_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 4096 and path.read_bytes()[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def pdf_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 4096 and path.read_bytes()[:5] == b"%PDF-"


def audit_drawings() -> Dict[str, Any]:
    expected = {
        drawing_id: {
            "slddrw": RUN_ROOT / f"07_drawings/{base_name}.SLDDRW",
            "pdf": RUN_ROOT / f"07_drawings/{base_name}.PDF",
            "source": source,
        }
        for drawing_id, base_name, source in DRAWING_SPECS
    }
    missing = [norm(path) for spec in expected.values() for path in (spec["slddrw"], spec["pdf"]) if not path.is_file()]
    if not DRAWING_REGISTER.is_file() or missing:
        return status("DRAWINGS", "PENDING", required_count=len(expected), missing_register=not DRAWING_REGISTER.is_file(), missing=missing)
    fields, rows = read_csv(DRAWING_REGISTER)
    missing_columns = [name for name in DRAWING_COLUMNS if name not in fields]
    by_id = {row.get("drawing_id", ""): row for row in rows}
    errors = []
    for drawing_id, spec in expected.items():
        row = by_id.get(drawing_id)
        if row is None:
            errors.append({"drawing_id": drawing_id, "reason": "REGISTER_ROW_MISSING"})
            continue
        slddrw, pdf, source = spec["slddrw"], spec["pdf"], spec["source"]
        checks = {
            "slddrw_signature": ole_file(slddrw), "pdf_signature": pdf_file(pdf),
            "slddrw_path": Path(row.get("slddrw_path", "")).resolve() == slddrw.resolve(),
            "pdf_path": Path(row.get("pdf_path", "")).resolve() == pdf.resolve(),
            "source_path": Path(row.get("source_native_path", "")).resolve() == source.resolve(),
            "slddrw_hash": sha256(slddrw) == row.get("slddrw_sha256", "").upper(),
            "pdf_hash": sha256(pdf) == row.get("pdf_sha256", "").upper(),
            "source_hash": source.is_file() and sha256(source) == row.get("source_native_sha256", "").upper(),
            "sheet_count": int(row.get("sheet_count", "0")) >= 1,
            "view_count": int(row.get("view_count", "0")) >= 2,
            "release_scope": row.get("release_scope") == "COMPETITION_PROTOTYPE_MANUFACTURING_DEFINITION",
        }
        metadata = ("part_number", "revision", "material", "datum", "critical_dimensions", "holes_threads", "gd_t", "surface_treatment", "inspection_dimensions")
        checks["metadata_complete"] = all(bool(row.get(name, "").strip()) and "TBD" not in row.get(name, "").upper() for name in metadata)
        if not all(checks.values()):
            errors.append({"drawing_id": drawing_id, "checks": checks})
    state = "PASS" if not missing_columns and len(rows) == len(expected) and not errors else "FAIL"
    return status("DRAWINGS", state, register=file_fact(DRAWING_REGISTER), required_count=len(expected), paired_slddrw_pdf_count=len(expected), missing_columns=missing_columns, errors=errors, files=[{"drawing_id": key, "slddrw": file_fact(value["slddrw"]), "pdf": file_fact(value["pdf"]), "source": file_fact(value["source"])} for key, value in expected.items()])


def audit_bom() -> Dict[str, Any]:
    if not BOM.is_file():
        return status("BOM", "PENDING", path=norm(BOM))
    fields, rows = read_csv(BOM)
    missing_columns = [name for name in BOM_COLUMNS if name not in fields]
    errors = []
    identities = set()
    for index, row in enumerate(rows, 2):
        try:
            if int(row.get("quantity", "0")) <= 0:
                raise ValueError("quantity is not positive")
        except Exception as exc:
            errors.append({"row": index, "reason": str(exc)})
        path = Path(row.get("native_path", ""))
        if not path.is_file() or sha256(path) != row.get("native_sha256", "").upper():
            errors.append({"row": index, "reason": "NATIVE_IDENTITY_FAIL", "path": row.get("native_path")})
        if "PROVISIONAL" in (row.get("status", "") + row.get("release_scope", "")).upper():
            errors.append({"row": index, "reason": "PROVISIONAL_SEED_IS_NOT_NATIVE_BOM"})
        if not all(row.get(name, "").strip() for name in ("part_number", "revision", "material", "source_class", "release_scope", "status")):
            errors.append({"row": index, "reason": "REQUIRED_BOM_FIELD_EMPTY"})
        identity = (row.get("level", ""), row.get("parent_component", ""), row.get("component_name", ""), norm(path))
        if identity in identities:
            errors.append({"row": index, "reason": "BOM_OCCURRENCE_DUPLICATE", "identity": identity})
        identities.add(identity)
        if row.get("release_scope") != "COMPETITION_PROTOTYPE_NATIVE_BOM" or row.get("status") not in {"NATIVE_VERIFIED", "PROTOTYPE_HOLD"}:
            errors.append({"row": index, "reason": "BOM_RELEASE_SCOPE_OR_STATUS_FAIL"})
    state = "PASS" if not missing_columns and rows and not errors else "FAIL"
    return status("BOM", state, file=file_fact(BOM), row_count=len(rows), missing_columns=missing_columns, errors=errors)


def audit_fasteners() -> Dict[str, Any]:
    if not FASTENER_REGISTER.is_file():
        return status("FASTENERS", "PENDING", path=norm(FASTENER_REGISTER))
    fields, rows = read_csv(FASTENER_REGISTER)
    missing_columns = [name for name in FASTENER_COLUMNS if name not in fields]
    errors = []
    critical = ("size", "grade_material", "washer", "thread_engagement", "assembly_torque_nm", "locking_method", "tightening_sequence", "inspection")
    for index, row in enumerate(rows, 2):
        if not all(row.get(name, "").strip() and "TBD" not in row.get(name, "").upper() for name in critical):
            errors.append({"row": index, "reason": "FASTENER_DEFINITION_INCOMPLETE"})
        if row.get("status") != "PROTOTYPE_ASSEMBLY_PRELOAD_DEFINED":
            errors.append({"row": index, "reason": "PROTOTYPE_PRELOAD_NOT_DEFINED"})
        if row.get("formal_launch_fastener_mos") != "HOLD":
            errors.append({"row": index, "reason": "FORMAL_LAUNCH_FASTENER_MOS_MUST_REMAIN_HOLD"})
        try:
            if int(row.get("quantity", "0")) <= 0 or float(row.get("assembly_torque_nm", "nan")) <= 0.0:
                raise ValueError("quantity/torque must be positive")
        except Exception as exc:
            errors.append({"row": index, "reason": str(exc)})
    state = "PASS" if not missing_columns and rows and not errors else "FAIL"
    return status("FASTENERS", state, file=file_fact(FASTENER_REGISTER), row_count=len(rows), missing_columns=missing_columns, errors=errors, formal_launch_fastener_mos="HOLD")


def audit_digital_thread() -> Dict[str, Any]:
    missing = [norm(path) for path in DIGITAL_FILES if not path.is_file()]
    if missing:
        return status("DIGITAL_THREAD", "PENDING", required_count=6, missing=missing)
    rows = []
    errors = []
    for path in DIGITAL_FILES:
        fact = file_fact(path)
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if path.suffix.lower() == ".csv":
            fields, data = read_csv(path)
            if not fields or not data:
                errors.append({"path": norm(path), "reason": "CSV_EMPTY"})
            required = {
                "V5_LINK_COMPONENT_MAPPING.csv": {"urdf_link", "component_name2", "native_path", "native_sha256", "authority_level"},
                "V5_COLLISION_ASSET_MANIFEST.csv": {"asset_id", "component_name2", "native_path", "native_sha256", "collision_class", "authority_level"},
            }.get(path.name, set())
            if not required.issubset(set(fields)):
                errors.append({"path": norm(path), "reason": "CSV_SCHEMA_FAIL", "missing_columns": sorted(required - set(fields))})
            for index, item in enumerate(data, 2):
                native_text = item.get("native_path", "")
                native_hash = item.get("native_sha256", "").upper()
                if native_text:
                    native = Path(native_text)
                    if not native.is_file() or sha256(native) != native_hash:
                        errors.append({"path": norm(path), "row": index, "reason": "DIGITAL_NATIVE_IDENTITY_FAIL", "native_path": native_text})
        elif len(text.strip()) < 80:
            errors.append({"path": norm(path), "reason": "YAML_EMPTY_OR_STUB"})
        elif "schema:" not in text:
            errors.append({"path": norm(path), "reason": "YAML_SCHEMA_MISSING"})
        elif path.name == "V5_MASS_BOUNDARY.yaml" and ("cad_override_allowed: false" not in text or "IMMUTABLE_DYNAMICS_TRUTH" not in text):
            errors.append({"path": norm(path), "reason": "MASS_BOUNDARY_AUTHORITY_MISSING"})
        elif path.name != "V5_MASS_BOUNDARY.yaml" and "authority" not in text.lower():
            errors.append({"path": norm(path), "reason": "YAML_AUTHORITY_MISSING"})
        rows.append(fact)
    digital_mass = DIGITAL_DIR / "V5_MASS_BOUNDARY.yaml"
    if sha256(digital_mass) != sha256(MASS_BOUNDARY_SEED):
        errors.append({"path": norm(digital_mass), "reason": "DIGITAL_MASS_BOUNDARY_DIFFERS_FROM_FIXED_SEED"})
    joined = "\n".join(path.read_text(encoding="utf-8-sig", errors="replace") for path in DIGITAL_FILES)
    required_tokens = ("L0", "L1", "L2", "L3", ACCEPTED_URDF_SHA256, "SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM")
    missing_tokens = [token for token in required_tokens if token not in joined]
    state = "PASS" if not errors and not missing_tokens else "FAIL"
    return status("DIGITAL_THREAD", state, required_count=6, files=rows, errors=errors, missing_authority_tokens=missing_tokens, accepted_urdf_level="L0", native_solidworks_level="L1", simulation_level="L2", donor_reference_level="L3")


def validate_pack_proof(proof: Mapping[str, Any], package_top_hash: str, ledger_hash: str, reference_count: int) -> bool:
    return bool(
        proof.get("schema") == "F3R2_V5_PACK_AND_GO_PROOF_V1"
        and proof.get("method") == "SOLIDWORKS_PACK_AND_GO"
        and int(proof.get("critical_external_reference_count", -1)) == 0
        and int(proof.get("missing_reference_count", -1)) == 0
        and int(proof.get("reference_count", -1)) == reference_count
        and proof.get("reference_ledger_sha256") == ledger_hash
        and proof.get("package_top", {}).get("sha256") == package_top_hash
        and proof.get("source_top", {}).get("sha256") == (sha256(TOP) if TOP.is_file() else None)
        and proof.get("verdict") == "V5_PACK_AND_GO_SELF_CONTAINED_PASS"
    )


def audit_pack() -> Dict[str, Any]:
    required = (PACK_TOP, PACK_LEDGER, PACK_PROOF)
    missing = [norm(path) for path in required if not path.is_file()]
    if missing:
        return status("PACK_AND_GO", "PENDING", package_root=norm(PACK_ROOT), missing=missing)
    fields, rows = read_csv(PACK_LEDGER)
    missing_columns = [name for name in PACK_LEDGER_COLUMNS if name not in fields]
    errors = []
    identities = set()
    for index, row in enumerate(rows, 2):
        resolved = Path(row.get("resolved_path", ""))
        inside = PACK_ROOT.resolve() == resolved.resolve() or PACK_ROOT.resolve() in resolved.resolve().parents
        if row.get("exists", "").lower() != "true" or not resolved.is_file():
            errors.append({"row": index, "reason": "MISSING_REFERENCE"})
        if row.get("inside_package", "").lower() != "true" or not inside:
            errors.append({"row": index, "reason": "REFERENCE_OUTSIDE_PACKAGE"})
        if row.get("critical_external", "").lower() != "false" or row.get("missing", "").lower() != "false":
            errors.append({"row": index, "reason": "CRITICAL_EXTERNAL_OR_MISSING_FLAG"})
        if resolved.is_file() and sha256(resolved) != row.get("resolved_sha256", "").upper():
            errors.append({"row": index, "reason": "REFERENCE_HASH_MISMATCH"})
        identity = (row.get("configuration", ""), row.get("component", ""), norm(resolved))
        if identity in identities:
            errors.append({"row": index, "reason": "REFERENCE_LEDGER_DUPLICATE", "identity": identity})
        identities.add(identity)
    if not ole_file(PACK_TOP):
        errors.append({"reason": "PACKAGE_TOP_NOT_NATIVE_OLE_ASSEMBLY"})
    expected_configurations: set[str] = set()
    if LOOP1E_RECEIPT.is_file():
        motion = load_json(LOOP1E_RECEIPT).get("motion_contract", {})
        if isinstance(motion, dict) and isinstance(motion.get("pose_configurations"), dict):
            expected_configurations = {str(value) for value in motion["pose_configurations"].values()}
    actual_configurations = {row.get("configuration", "") for row in rows}
    if expected_configurations and not expected_configurations.issubset(actual_configurations):
        errors.append({"reason": "PACKAGE_CONFIGURATION_COVERAGE_FAIL", "missing": sorted(expected_configurations - actual_configurations)})
    proof = load_json(PACK_PROOF)
    proof_pass = validate_pack_proof(proof, sha256(PACK_TOP), sha256(PACK_LEDGER), len(rows))
    state = "PASS" if not missing_columns and rows and not errors and proof_pass else "FAIL"
    return status("PACK_AND_GO", state, package_root=norm(PACK_ROOT), top=file_fact(PACK_TOP), ledger=file_fact(PACK_LEDGER), proof=file_fact(PACK_PROOF), row_count=len(rows), missing_columns=missing_columns, errors=errors, proof_contract_pass=proof_pass, critical_external_reference_count=0 if proof_pass else proof.get("critical_external_reference_count"), missing_reference_count=0 if proof_pass else proof.get("missing_reference_count"))


def png_dimensions(path: Path) -> Optional[Tuple[int, int]]:
    if not path.is_file() or path.stat().st_size < 24:
        return None
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def audit_shots() -> Dict[str, Any]:
    pairs = []
    missing = []
    errors = []
    for name in SHOT_NAMES:
        raw = RUN_ROOT / f"11_screenshots/RAW/{name}.png"
        annotated = RUN_ROOT / f"11_screenshots/ANNOTATED/{name}.png"
        if not raw.is_file() or not annotated.is_file():
            missing.extend(norm(path) for path in (raw, annotated) if not path.is_file())
            continue
        raw_dim, ann_dim = png_dimensions(raw), png_dimensions(annotated)
        row = {"shot": name, "raw": file_fact(raw), "annotated": file_fact(annotated), "raw_dimensions": raw_dim, "annotated_dimensions": ann_dim}
        if raw_dim is None or ann_dim is None or raw_dim[0] < 800 or raw_dim[1] < 600 or ann_dim != raw_dim or sha256(raw) == sha256(annotated):
            errors.append({"shot": name, "reason": "PNG_DIMENSION_OR_ANNOTATION_IDENTITY_FAIL", "raw_dimensions": raw_dim, "annotated_dimensions": ann_dim})
        pairs.append(row)
    if missing or not SHOT_MANIFEST.is_file():
        return status("HUMAN_REVIEW", "PENDING", required_pairs=22, present_pairs=len(pairs), missing_manifest=not SHOT_MANIFEST.is_file(), missing=missing, errors=errors)
    fields, rows = read_csv(SHOT_MANIFEST)
    missing_columns = [name for name in SHOT_MANIFEST_COLUMNS if name not in fields]
    if missing_columns:
        errors.append({"reason": "SHOT_MANIFEST_SCHEMA_FAIL", "missing_columns": missing_columns})
    manifest_names = {row.get("shot_id", "") for row in rows}
    if set(SHOT_NAMES) != manifest_names or len(rows) != 22:
        errors.append({"reason": "SHOT_MANIFEST_SET_FAIL", "actual": sorted(manifest_names)})
    by_name = {row.get("shot_id", ""): row for row in rows}
    for item in pairs:
        row = by_name.get(item["shot"])
        if row is None:
            continue
        raw_path = Path(row.get("raw_path", ""))
        annotated_path = Path(row.get("annotated_path", ""))
        if (
            raw_path.resolve() != Path(item["raw"]["path"]).resolve()
            or annotated_path.resolve() != Path(item["annotated"]["path"]).resolve()
            or row.get("raw_sha256", "").upper() != item["raw"]["sha256"]
            or row.get("annotated_sha256", "").upper() != item["annotated"]["sha256"]
            or not row.get("configuration_or_state", "").strip()
            or not row.get("view_or_evidence", "").strip()
            or not row.get("reviewer", "").strip()
            or row.get("review_status") != "PASS"
        ):
            errors.append({"shot": item["shot"], "reason": "SHOT_MANIFEST_IDENTITY_OR_REVIEW_FAIL"})
    state = "PASS" if len(pairs) == 22 and not errors else "FAIL"
    return status("HUMAN_REVIEW", state, required_pairs=22, present_pairs=len(pairs), manifest=file_fact(SHOT_MANIFEST), pairs=pairs, errors=errors)


def validate_claims_payload(payload: Mapping[str, Any]) -> bool:
    claims = payload.get("prohibited_claims")
    holds = payload.get("holds")
    return bool(
        payload.get("schema") == "F3R2_V5_RELEASE_CLAIMS_V1"
        and payload.get("highest_allowed_claim") == HIGHEST_ALLOWED_CLAIM
        and payload.get("mechanical_authoring_after_gate") == "ECR_ONLY"
        and isinstance(claims, dict)
        and set(claims) == set(PROHIBITED_CLAIMS)
        and all(claims[name] is False for name in PROHIBITED_CLAIMS)
        and isinstance(holds, list)
        and set(REQUIRED_HOLDS).issubset(set(holds))
    )


def audit_claims() -> Dict[str, Any]:
    if not CLAIMS.is_file():
        return status("PROHIBITED_CLAIMS", "PENDING", path=norm(CLAIMS))
    payload = load_json(CLAIMS)
    claims = payload.get("prohibited_claims")
    holds = payload.get("holds")
    pass_value = validate_claims_payload(payload)
    return status("PROHIBITED_CLAIMS", "PASS" if pass_value else "FAIL", file=file_fact(CLAIMS), highest_allowed_claim=payload.get("highest_allowed_claim"), prohibited_claims=claims, holds=holds, contract_pass=pass_value)


def audit_top_binding() -> Dict[str, Any]:
    if not TOP.is_file() or not LOOP1E_RECEIPT.is_file():
        return status("TOP_BINDING", "PENDING", top=file_fact(TOP), loop1e_receipt=file_fact(LOOP1E_RECEIPT))
    receipt = load_json(LOOP1E_RECEIPT)
    fact = receipt.get("target_fact")
    motion = receipt.get("motion_contract")
    pass_value = bool(
        isinstance(fact, dict)
        and Path(str(fact.get("path", ""))).resolve() == TOP.resolve()
        and fact.get("sha256") == sha256(TOP)
        and int(fact.get("bytes", -1)) == TOP.stat().st_size
        and isinstance(motion, dict)
        and motion.get("schema") == "F3R2_V5_LOOP2_MOTION_CONTRACT_V1"
        and motion.get("accepted_urdf_sha256") == ACCEPTED_URDF_SHA256
        and receipt.get("q_vectors_written") is False
        and receipt.get("undefined_service_q_created") is False
    )
    return status("TOP_BINDING", "PASS" if pass_value else "FAIL", top=file_fact(TOP), loop1e_receipt=file_fact(LOOP1E_RECEIPT), receipt_target_fact=fact, accepted_urdf_overwritten=False)


def evidence_audits() -> List[Dict[str, Any]]:
    return [
        safe_audit("TOP_BINDING", audit_top_binding),
        safe_audit("MASS", audit_mass),
        safe_audit("DRAWINGS", audit_drawings),
        safe_audit("BOM", audit_bom),
        safe_audit("FASTENERS", audit_fasteners),
        safe_audit("DIGITAL_THREAD", audit_digital_thread),
        safe_audit("PACK_AND_GO", audit_pack),
        safe_audit("HUMAN_REVIEW", audit_shots),
        safe_audit("PROHIBITED_CLAIMS", audit_claims),
    ]


def artifact_identity_manifest() -> Dict[str, Dict[str, Any]]:
    paths: List[Path] = [
        ACCEPTED_URDF, TOP, MASS_CSV, MASS_SUMMARY, DRAWING_REGISTER, BOM,
        FASTENER_REGISTER, *DIGITAL_FILES, PACK_TOP, PACK_LEDGER, PACK_PROOF,
    ]
    for _drawing_id, base_name, _source in DRAWING_SPECS:
        paths.extend((RUN_ROOT / f"07_drawings/{base_name}.SLDDRW", RUN_ROOT / f"07_drawings/{base_name}.PDF"))
    missing = [norm(path) for path in paths if not path.is_file()]
    if missing:
        raise GateError("CORE_ARTIFACT_IDENTITY_PENDING", "core release artifact set is incomplete", {"missing": missing})
    return {norm(path): file_fact(path) for path in sorted(set(paths), key=lambda item: norm(item).lower())}


def validate_session_pair(session_a: Mapping[str, Any], session_b: Mapping[str, Any]) -> bool:
    try:
        return bool(
            int(session_a.get("pid", -1)) > 0
            and int(session_b.get("pid", -1)) > 0
            and int(session_a["pid"]) != int(session_b["pid"])
            and float(session_a.get("process_create_time_epoch", -1.0)) > 0.0
            and float(session_b.get("process_create_time_epoch", -1.0)) > 0.0
            and not math.isclose(float(session_a["process_create_time_epoch"]), float(session_b["process_create_time_epoch"]), rel_tol=0.0, abs_tol=1.0e-6)
            and session_a.get("document_count") == 0
            and session_b.get("document_count") == 0
            and session_a.get("active_doc_is_null") is True
            and session_b.get("active_doc_is_null") is True
        )
    except Exception:
        return False


def audit_session_checkpoint(path: Path, stage: str) -> Dict[str, Any]:
    if not path.is_file():
        return status(stage, "PENDING", path=norm(path))
    payload = load_json(path)
    expected_schema = f"F3R2_V5_LOOP3_{stage}_CHECKPOINT_V1"
    expected_verdict = f"V5_LOOP3_{stage}_COLD_REOPEN_PASS"
    pass_value = bool(
        payload.get("schema") == expected_schema
        and payload.get("script_sha256") == sha256(Path(__file__))
        and payload.get("accepted_urdf_sha256_pre") == ACCEPTED_URDF_SHA256
        and payload.get("accepted_urdf_sha256_post") == ACCEPTED_URDF_SHA256
        and payload.get("accepted_urdf_overwritten") is False
        and payload.get("protected_pre") == payload.get("protected_post")
        and payload.get("solidworks_document_count_after_cleanup") == 0
        and payload.get("active_doc_after_cleanup_is_null") is True
        and payload.get("core_artifact_identities") == artifact_identity_manifest()
        and payload.get("verdict") == expected_verdict
    )
    if stage == "SESSION_B":
        if not SESSION_A_CHECKPOINT.is_file():
            pass_value = False
        else:
            session_a_payload = load_json(SESSION_A_CHECKPOINT)
            pass_value = bool(
                pass_value
                and payload.get("session_a_checkpoint_sha256") == sha256(SESSION_A_CHECKPOINT)
                and validate_session_pair(session_a_payload.get("solidworks", {}), payload.get("solidworks", {}))
                and payload.get("fresh_process_from_session_a") is True
            )
    return status(stage, "PASS" if pass_value else "FAIL", checkpoint=file_fact(path), payload_verdict=payload.get("verdict"), session=payload.get("solidworks"), contract_pass=pass_value)


def audit_final_receipt() -> Dict[str, Any]:
    if not FINAL_RECEIPT.is_file():
        return status("FINAL_RECEIPT", "PENDING", path=norm(FINAL_RECEIPT))
    payload = load_json(FINAL_RECEIPT)
    manifest = payload.get("manifest")
    pass_value = bool(
        payload.get("schema") == "F3R2_V5_LOOP3_RELEASE_EVIDENCE_RECEIPT_V1"
        and payload.get("verdict") == "F3R2_V5_COMPETITION_NATIVE_MECHANICAL_BASELINE_CLOSED"
        and payload.get("final_gate_eligible") is True
        and payload.get("receipt_written_last") is True
        and payload.get("accepted_urdf_sha256") == ACCEPTED_URDF_SHA256
        and payload.get("accepted_urdf_overwritten") is False
        and isinstance(manifest, dict)
        and Path(str(manifest.get("path", ""))).resolve() == FINAL_MANIFEST.resolve()
        and FINAL_MANIFEST.is_file()
        and manifest.get("sha256") == sha256(FINAL_MANIFEST)
        and SESSION_B_CHECKPOINT.is_file()
        and payload.get("session_b_checkpoint_sha256") == sha256(SESSION_B_CHECKPOINT)
    )
    return status("FINAL_RECEIPT", "PASS" if pass_value else "FAIL", receipt=file_fact(FINAL_RECEIPT), verdict=payload.get("verdict"), contract_pass=pass_value)


def loop2_final_gate_eligible(upstream: Sequence[Mapping[str, Any]]) -> bool:
    rows = [row for row in upstream if row.get("stage") == "LOOP2"]
    return len(rows) == 1 and rows[0].get("pass") is True and rows[0].get("final_gate_eligible") is True


def static_audit() -> Dict[str, Any]:
    fixed = fixed_audit()
    upstream = upstream_audit()
    try:
        protected_rows = protected_snapshot()
        protected = status("PROTECTED_PRE", "PASS", assets=protected_rows, asset_count=len(protected_rows))
    except Exception as exc:
        protected = status("PROTECTED_PRE", "FAIL", reason=str(exc), code=getattr(exc, "code", "PROTECTED_EXCEPTION"), detail=getattr(exc, "detail", None))
    evidence = evidence_audits()
    session_a = safe_audit("SESSION_A", lambda: audit_session_checkpoint(SESSION_A_CHECKPOINT, "SESSION_A"))
    session_b = safe_audit("SESSION_B", lambda: audit_session_checkpoint(SESSION_B_CHECKPOINT, "SESSION_B"))
    final_receipt = safe_audit("FINAL_RECEIPT", audit_final_receipt)

    fixed_failures = [row["name"] for row in fixed if not row["pass"]]
    upstream_pending = [row["stage"] for row in upstream if row["status"] == "PENDING"]
    upstream_failures = [row["stage"] for row in upstream if row["status"] == "FAIL"]
    evidence_pending = [row["id"] for row in evidence if row["status"] == "PENDING"]
    evidence_failures = [row["id"] for row in evidence if row["status"] == "FAIL"]
    checkpoint_failures = [row["id"] for row in (session_a, session_b, final_receipt) if row["status"] == "FAIL"]
    hard_failures = fixed_failures + upstream_failures + evidence_failures + checkpoint_failures + ([] if protected["pass"] else ["PROTECTED_PRE"])
    core_ids = {"TOP_BINDING", "MASS", "DRAWINGS", "BOM", "FASTENERS", "DIGITAL_THREAD", "PACK_AND_GO"}
    core_pass = all(row["pass"] for row in evidence if row["id"] in core_ids) and {row["id"] for row in evidence if row["id"] in core_ids} == core_ids
    claims_row = next(row for row in evidence if row["id"] == "PROHIBITED_CLAIMS")
    shots_row = next(row for row in evidence if row["id"] == "HUMAN_REVIEW")
    prerequisites_pass = not fixed_failures and all(row["pass"] for row in upstream) and protected["pass"]
    session_a_authorized = bool(prerequisites_pass and core_pass and not hard_failures and session_a["status"] == "PENDING")
    session_b_authorized = bool(
        prerequisites_pass
        and core_pass
        and shots_row["pass"]
        and claims_row["status"] in {"PASS", "PENDING"}
        and session_a["pass"]
        and session_b["status"] == "PENDING"
        and loop2_final_gate_eligible(upstream)
        and not hard_failures
    )
    release_gate_eligible = bool(
        prerequisites_pass
        and all(row["pass"] for row in evidence)
        and session_a["pass"]
        and session_b["pass"]
        and loop2_final_gate_eligible(upstream)
        and not hard_failures
    )
    if final_receipt["pass"] and release_gate_eligible:
        verdict = "V5_LOOP3_RELEASE_EVIDENCE_COMPLETE_READ_ONLY"
    elif hard_failures:
        verdict = "V5_LOOP3_STATIC_HOLD"
    elif upstream_pending:
        verdict = "V5_LOOP3_STATIC_PENDING_UPSTREAM"
    elif evidence_pending:
        verdict = "V5_LOOP3_STATIC_PENDING_EVIDENCE"
    elif not session_a["pass"]:
        verdict = "V5_LOOP3_STATIC_PENDING_SESSION_A"
    elif not session_b["pass"]:
        verdict = "V5_LOOP3_STATIC_PENDING_FRESH_SESSION_B"
    elif not release_gate_eligible:
        verdict = "V5_LOOP3_STATIC_PENDING_FINAL_GATE"
    else:
        verdict = "V5_LOOP3_STATIC_RELEASE_READY_RECEIPT_PENDING"
    holds = []
    if upstream_pending:
        holds.append("UPSTREAM_RECEIPT_HASH_REGISTRATION_OR_ARTIFACT_PENDING:" + ",".join(upstream_pending))
    if not loop2_final_gate_eligible(upstream):
        holds.append("LOOP2_FINAL_GATE_ELIGIBILITY_PENDING")
    if evidence_pending:
        holds.append("RELEASE_EVIDENCE_PENDING:" + ",".join(evidence_pending))
    if session_a["status"] != "PASS":
        holds.append("SESSION_A_CHECKPOINT_PENDING")
    if session_b["status"] != "PASS":
        holds.append("FRESH_SESSION_B_COLD_REOPEN_PENDING")
    holds.extend(REQUIRED_HOLDS)
    return {
        "schema": "F3R2_V5_LOOP3_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "verdict": verdict,
        "script": file_fact(Path(__file__)),
        "fixed_inputs": fixed,
        "upstream": upstream,
        "protected": protected,
        "evidence": evidence,
        "session_a": session_a,
        "session_b": session_b,
        "final_receipt": final_receipt,
        "session_a_execution_authorized": session_a_authorized,
        "session_b_execution_authorized": session_b_authorized,
        "release_gate_eligible": release_gate_eligible,
        "loop2_final_gate_eligible": loop2_final_gate_eligible(upstream),
        "accepted_urdf": file_fact(ACCEPTED_URDF),
        "accepted_urdf_overwritten": False,
        "pending": {"upstream": upstream_pending, "evidence": evidence_pending},
        "failures": hard_failures,
        "holds": sorted(set(holds)),
        "coverage": {
            "external_mass_com_inertia_boundary": True,
            "native_slddrw_pdf_pairs": len(DRAWING_SPECS),
            "native_bom": True,
            "fastener_register": True,
            "digital_thread_named_files": [path.name for path in DIGITAL_FILES],
            "pack_and_go_exact_critical_external_zero_missing_zero": True,
            "fresh_session_b_cold_reopen": True,
            "raw_annotated_shot_pairs": len(SHOT_NAMES),
            "hash_manifest": True,
            "prohibited_claims_and_final_gate": True,
        },
    }


def load_base() -> Any:
    if sha256(BASE_HELPER) != BASE_HELPER_SHA256 or sha256(BASE_HELPER_COPY) != BASE_HELPER_SHA256:
        raise GateError("BASE_HELPER_HASH_FAIL", "pinned attach-only helper or its V5 copy drifted")
    spec = importlib.util.spec_from_file_location("f3r2_v5_loop1_base_for_loop3", BASE_HELPER)
    if spec is None or spec.loader is None:
        raise GateError("BASE_HELPER_IMPORT_FAIL", "cannot create pinned helper import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def process_identity(session: Mapping[str, Any]) -> Dict[str, Any]:
    import psutil
    pid = int(session["pid"])
    process = psutil.Process(pid)
    created = float(process.create_time())
    return {
        **dict(session),
        "process_create_time_epoch": created,
        "process_create_time_utc": datetime.fromtimestamp(created, timezone.utc).isoformat(),
        "process_name": process.name(),
    }


def dependency_paths(model: Any, base: Any) -> List[str]:
    raw = base.as_list(model.GetDependencies2(False, True, False))
    if len(raw) % 2:
        raise GateError("DEPENDENCY_ARRAY_SHAPE_FAIL", "GetDependencies2 returned an odd array", {"count": len(raw)})
    return sorted(os.path.normcase(str(Path(str(raw[index + 1])).resolve())) for index in range(0, len(raw), 2))


def open_doc(sw: Any, path: Path, doc_type: int, base: Any, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    before_hash = sha256(path)
    raw, outs = base.unpack(sw.OpenDoc6(str(path), doc_type, SW_OPEN_SILENT_READONLY, "", 0, 0))
    errors = int(outs[0]) if outs else 0
    warnings = int(outs[1]) if len(outs) > 1 else 0
    if raw is None or errors != 0:
        raise GateError("COLD_OPEN_FAIL", "read-only cold open returned null/error", {"path": norm(path), "errors": errors, "warnings": warnings})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    if int(base.value(model, "GetType")) != doc_type:
        raise GateError("COLD_OPEN_TYPE_FAIL", "opened document type differs from contract", {"path": norm(path), "actual": int(base.value(model, "GetType")), "expected": doc_type})
    return model, {"path": norm(path), "sha256_before": before_hash, "errors": errors, "warnings": warnings, "read_only": True}


def close_doc(sw: Any, model: Any, base: Any) -> None:
    title = str(base.value(model, "GetTitle"))
    sw.CloseDoc(title)
    # Drawings may transiently load referenced models.  The session was empty
    # on entry, so all documents now present are owned by this cold-open step.
    close_owned(sw, base)
    if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
        raise GateError("DOCUMENT_CLEANUP_FAIL", "SolidWorks document remains after cold close", {"title": title, "document_count": int(base.value(sw, "GetDocumentCount"))})


def expected_top_dependencies() -> List[str]:
    receipt = load_json(LOOP1E_RECEIPT)
    raw = receipt.get("cold_reopen", {}).get("references", {}).get("dependency_paths")
    if not isinstance(raw, list) or not raw:
        raise GateError("LOOP1E_DEPENDENCY_LEDGER_MISSING", "Loop1E receipt lacks cold dependency ledger")
    return sorted(os.path.normcase(str(Path(str(path)).resolve())) for path in raw)


def cold_document(sw: Any, path: Path, doc_type: int, base: Any, types: Any, pythoncom: Any, allowed_root: Optional[Path] = None, exact_dependencies: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    model, opened = open_doc(sw, path, doc_type, base, types, pythoncom)
    try:
        if not bool(model.ForceRebuild3(True)):
            raise GateError("COLD_REBUILD_FAIL", "ForceRebuild3 failed", {"path": norm(path)})
        deps = dependency_paths(model, base)
        missing = [item for item in deps if not Path(item).is_file()]
        escaped = [item for item in deps if allowed_root is not None and allowed_root.resolve() != Path(item).resolve() and allowed_root.resolve() not in Path(item).resolve().parents]
        if missing or escaped:
            raise GateError("COLD_DEPENDENCY_FAIL", "cold document has missing or escaped dependency", {"path": norm(path), "missing": missing, "escaped": escaped})
        if exact_dependencies is not None:
            expected = sorted(os.path.normcase(str(Path(item).resolve())) for item in exact_dependencies)
            if deps != expected:
                raise GateError("COLD_DEPENDENCY_EXACT_SET_FAIL", "cold dependency set differs from receipted exact set", {"path": norm(path), "actual": deps, "expected": expected})
        fact: Dict[str, Any] = {
            **opened,
            "dependencies": deps,
            "dependency_count": len(deps),
            "missing_reference_count": len(missing),
            "escaped_reference_count": len(escaped),
            "configuration_names": sorted(str(value) for value in base.as_list(base.value(model, "GetConfigurationNames"))),
            "rebuild_pass": True,
        }
        if doc_type == SW_DOC_DRAWING:
            drawing = base.wrap(model, "IDrawingDoc", types, pythoncom)
            sheets = [str(value) for value in base.as_list(drawing.GetSheetNames())]
            if not sheets:
                raise GateError("DRAWING_SHEET_EMPTY", "native drawing has no sheet", {"path": norm(path)})
            fact["sheet_names"] = sheets
            fact["sheet_count"] = len(sheets)
    finally:
        close_doc(sw, model, base)
    if sha256(path) != opened["sha256_before"]:
        raise GateError("READ_ONLY_COLD_HASH_DRIFT", "read-only cold reopen changed document hash", {"path": norm(path)})
    fact["sha256_after"] = sha256(path)
    return fact


def cold_release_set(sw: Any, include_pack: bool, base: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    top = cold_document(sw, TOP, SW_DOC_ASSEMBLY, base, types, pythoncom, exact_dependencies=expected_top_dependencies())
    drawings = []
    for drawing_id, base_name, source in DRAWING_SPECS:
        path = RUN_ROOT / f"07_drawings/{base_name}.SLDDRW"
        row = cold_document(sw, path, SW_DOC_DRAWING, base, types, pythoncom)
        if os.path.normcase(str(source.resolve())) not in row["dependencies"]:
            raise GateError("DRAWING_SOURCE_DEPENDENCY_FAIL", "drawing does not reference its contracted native source", {"drawing_id": drawing_id, "source": norm(source), "dependencies": row["dependencies"]})
        drawings.append({"drawing_id": drawing_id, **row})
    package = cold_document(sw, PACK_TOP, SW_DOC_ASSEMBLY, base, types, pythoncom, allowed_root=PACK_ROOT) if include_pack else None
    return {"top": top, "drawings": drawings, "package_top": package, "bom": file_fact(BOM), "mass_csv": file_fact(MASS_CSV), "mass_summary": file_fact(MASS_SUMMARY)}


def close_owned(sw: Any, base: Any) -> None:
    guard = 0
    while int(base.value(sw, "GetDocumentCount")) and guard < 200:
        active = base.value(sw, "ActiveDoc")
        if active is None:
            break
        sw.CloseDoc(str(base.value(active, "GetTitle")))
        guard += 1
    if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
        raise GateError("DOCUMENT_CLEANUP_FAIL", "owned SolidWorks documents remain open", {"document_count": int(base.value(sw, "GetDocumentCount"))})


def failure_receipt(stage: str, payload: Mapping[str, Any]) -> Optional[Path]:
    path = VALIDATION / f"V5_LOOP3_{stage}_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
    try:
        write_json_once(path, payload)
        return path
    except Exception:
        return None


def session_a_execute() -> int:
    result: Dict[str, Any] = {"schema": "F3R2_V5_LOOP3_SESSION_A_CHECKPOINT_V1", "timestamp_start_utc": utc_now(), "stage": "SESSION_A"}
    sw = base = types = pythoncom = None
    try:
        existing = audit_session_checkpoint(SESSION_A_CHECKPOINT, "SESSION_A")
        if existing["pass"]:
            print(json.dumps(existing, ensure_ascii=False, indent=2))
            return 0
        audit = static_audit()
        result["static_audit"] = audit
        if not audit["session_a_execution_authorized"]:
            raise GateError("SESSION_A_STATIC_HOLD", "Loop3 Session A is not authorized", audit)
        protected_pre = protected_snapshot()
        urdf_pre = sha256(ACCEPTED_URDF)
        base = load_base()
        memory = base.memory_gate()
        sw, types, pythoncom, session = base.attach_empty_session()
        session = process_identity(session)
        cold = cold_release_set(sw, True, base, types, pythoncom)
        close_owned(sw, base)
        protected_post = protected_snapshot()
        urdf_post = sha256(ACCEPTED_URDF)
        if protected_pre != protected_post or urdf_pre != ACCEPTED_URDF_SHA256 or urdf_post != ACCEPTED_URDF_SHA256:
            raise GateError("SESSION_A_PROTECTED_DRIFT", "protected assets or accepted URDF drifted during Session A")
        copy_once(Path(__file__).resolve(), SCRIPT_COPY)
        result.update({
            "timestamp_end_utc": utc_now(),
            "script_sha256": sha256(Path(__file__)),
            "solidworks": session,
            "memory_samples_gib": memory,
            "cold_reopen": cold,
            "core_artifact_identities": artifact_identity_manifest(),
            "protected_pre": protected_pre,
            "protected_post": protected_post,
            "accepted_urdf_sha256_pre": urdf_pre,
            "accepted_urdf_sha256_post": urdf_post,
            "accepted_urdf_overwritten": False,
            "solidworks_document_count_after_cleanup": int(base.value(sw, "GetDocumentCount")),
            "active_doc_after_cleanup_is_null": base.value(sw, "ActiveDoc") is None,
            "verdict": "V5_LOOP3_SESSION_A_COLD_REOPEN_PASS",
        })
        write_json_once(SESSION_A_CHECKPOINT, result)
        print(json.dumps({"verdict": result["verdict"], "checkpoint": file_fact(SESSION_A_CHECKPOINT), "pid": session["pid"]}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        result.update({"timestamp_end_utc": utc_now(), "verdict": getattr(exc, "code", "SESSION_A_UNEXPECTED_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", None), "traceback": traceback.format_exc()})
        failed = failure_receipt("SESSION_A", result)
        if failed:
            result["failure_receipt"] = file_fact(failed)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    finally:
        if sw is not None and base is not None:
            try:
                close_owned(sw, base)
            except Exception:
                pass
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def claims_payload(session_b: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "schema": "F3R2_V5_RELEASE_CLAIMS_V1",
        "timestamp_utc": utc_now(),
        "highest_allowed_claim": HIGHEST_ALLOWED_CLAIM,
        "mechanical_authoring_after_gate": "ECR_ONLY",
        "prohibited_claims": {name: False for name in PROHIBITED_CLAIMS},
        "holds": list(REQUIRED_HOLDS),
        "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
        "accepted_urdf_overwritten": False,
        "session_b_pid": session_b.get("pid"),
        "scope": "COMPETITION_NATIVE_MECHANICAL_BASELINE_NOT_FLIGHT_OR_MANUFACTURING_RELEASE",
    }


def write_csv_once(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def acceptance_rows(audit: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in audit["upstream"]:
        rows.append({"gate_id": "UPSTREAM_" + item["stage"], "status": item["status"], "release_blocking": "true", "evidence_path": item["path"], "evidence_sha256": item.get("actual_sha256") or "", "detail": item.get("actual_verdict") or "PENDING"})
    for item in audit["fixed_inputs"]:
        rows.append({"gate_id": "FIXED_" + item["name"], "status": "PASS" if item["pass"] else "FAIL", "release_blocking": "true", "evidence_path": item["path"], "evidence_sha256": item.get("actual_sha256") or "", "detail": "HASH_PIN"})
    for item in audit["evidence"]:
        fact = next((value for value in item.values() if isinstance(value, dict) and isinstance(value.get("path"), str) and value.get("sha256")), None)
        rows.append({"gate_id": item["id"], "status": item["status"], "release_blocking": "true", "evidence_path": fact.get("path", "") if fact else "", "evidence_sha256": fact.get("sha256", "") if fact else "", "detail": item.get("verdict") or item.get("reason") or "FAIL_CLOSED_AUDIT"})
    for key in ("session_a", "session_b"):
        item = audit[key]
        fact = item.get("checkpoint", {})
        rows.append({"gate_id": item["id"], "status": item["status"], "release_blocking": "true", "evidence_path": fact.get("path", ""), "evidence_sha256": fact.get("sha256", ""), "detail": item.get("payload_verdict") or "PENDING"})
    rows.append({"gate_id": "FINAL_GATE", "status": "PASS" if audit["release_gate_eligible"] else "PENDING", "release_blocking": "true", "evidence_path": norm(ACCEPTANCE_MATRIX), "evidence_sha256": "", "detail": HIGHEST_ALLOWED_CLAIM if audit["release_gate_eligible"] else "RELEASE_NOT_ELIGIBLE"})
    return rows


def manifest_paths() -> List[Path]:
    paths: List[Path] = [
        Path(__file__).resolve(), SCRIPT_COPY, ACCEPTED_URDF, TOP, MASS_CSV, MASS_SUMMARY,
        DRAWING_REGISTER, BOM, FASTENER_REGISTER, *DIGITAL_FILES, PACK_TOP, PACK_LEDGER,
        PACK_PROOF, SHOT_MANIFEST, CLAIMS, SESSION_A_CHECKPOINT, SESSION_B_CHECKPOINT,
        ACCEPTANCE_MATRIX, *(Path(item["path"]) for item in UPSTREAM),
    ]
    for _drawing_id, base_name, _source in DRAWING_SPECS:
        paths.extend((RUN_ROOT / f"07_drawings/{base_name}.SLDDRW", RUN_ROOT / f"07_drawings/{base_name}.PDF"))
    for name in SHOT_NAMES:
        paths.extend((RUN_ROOT / f"11_screenshots/RAW/{name}.png", RUN_ROOT / f"11_screenshots/ANNOTATED/{name}.png"))
    unique = sorted(set(path.resolve() for path in paths), key=lambda item: norm(item).lower())
    missing = [norm(path) for path in unique if not path.is_file()]
    if missing:
        raise GateError("FINAL_MANIFEST_INPUT_MISSING", "final hash manifest input is missing", {"missing": missing})
    return unique


def manifest_text(paths: Sequence[Path]) -> str:
    rows = []
    for path in paths:
        label = path.relative_to(RUN_ROOT).as_posix() if RUN_ROOT.resolve() in path.resolve().parents else norm(path)
        rows.append(f"{sha256(path)}  {path.stat().st_size}  {label}")
    return "\n".join(sorted(rows)) + "\n"


def session_b_execute() -> int:
    result: Dict[str, Any] = {"schema": "F3R2_V5_LOOP3_RELEASE_EVIDENCE_RECEIPT_V1", "timestamp_start_utc": utc_now(), "stage": "SESSION_B_AND_FINAL_GATE"}
    sw = base = types = pythoncom = None
    try:
        completed = audit_final_receipt()
        if completed["pass"]:
            print(json.dumps(completed, ensure_ascii=False, indent=2))
            return 0
        audit = static_audit()
        result["static_audit_pre"] = audit
        if not audit["session_b_execution_authorized"]:
            raise GateError("SESSION_B_STATIC_HOLD", "Loop3 fresh Session B is not authorized", audit)
        session_a_payload = load_json(SESSION_A_CHECKPOINT)
        protected_pre = protected_snapshot()
        urdf_pre = sha256(ACCEPTED_URDF)
        base = load_base()
        memory = base.memory_gate()
        sw, types, pythoncom, session = base.attach_empty_session()
        session = process_identity(session)
        if not validate_session_pair(session_a_payload.get("solidworks", {}), session):
            raise GateError("SESSION_B_NOT_FRESH", "Session B PID/creation-time identity is not distinct from Session A", {"session_a": session_a_payload.get("solidworks"), "session_b": session})
        cold = cold_release_set(sw, True, base, types, pythoncom)
        close_owned(sw, base)
        protected_post = protected_snapshot()
        urdf_post = sha256(ACCEPTED_URDF)
        if protected_pre != protected_post or urdf_pre != ACCEPTED_URDF_SHA256 or urdf_post != ACCEPTED_URDF_SHA256:
            raise GateError("SESSION_B_PROTECTED_DRIFT", "protected assets or accepted URDF drifted during Session B")
        checkpoint = {
            "schema": "F3R2_V5_LOOP3_SESSION_B_CHECKPOINT_V1",
            "timestamp_utc": utc_now(),
            "script_sha256": sha256(Path(__file__)),
            "session_a_checkpoint_sha256": sha256(SESSION_A_CHECKPOINT),
            "solidworks": session,
            "fresh_process_from_session_a": True,
            "memory_samples_gib": memory,
            "cold_reopen": cold,
            "core_artifact_identities": artifact_identity_manifest(),
            "protected_pre": protected_pre,
            "protected_post": protected_post,
            "accepted_urdf_sha256_pre": urdf_pre,
            "accepted_urdf_sha256_post": urdf_post,
            "accepted_urdf_overwritten": False,
            "solidworks_document_count_after_cleanup": int(base.value(sw, "GetDocumentCount")),
            "active_doc_after_cleanup_is_null": base.value(sw, "ActiveDoc") is None,
            "verdict": "V5_LOOP3_SESSION_B_COLD_REOPEN_PASS",
        }
        write_json_once(SESSION_B_CHECKPOINT, checkpoint)
        if CLAIMS.exists():
            if not audit_claims()["pass"]:
                raise GateError("RELEASE_CLAIMS_DRIFT", "existing release claims file is invalid")
        else:
            write_json_once(CLAIMS, claims_payload(session))
        post_audit = static_audit()
        if not post_audit["release_gate_eligible"]:
            raise GateError("FINAL_GATE_NOT_ELIGIBLE", "release evidence remains PENDING/HOLD after fresh Session B", post_audit)
        rows = acceptance_rows(post_audit)
        if any(row["status"] != "PASS" for row in rows):
            raise GateError("ACCEPTANCE_MATRIX_NOT_ALL_PASS", "acceptance matrix contains non-PASS release-blocking row", {"rows": rows})
        write_csv_once(ACCEPTANCE_MATRIX, ACCEPTANCE_MATRIX_COLUMNS, rows)
        text = manifest_text(manifest_paths())
        write_text_once(FINAL_MANIFEST, text)
        final = {
            "schema": "F3R2_V5_LOOP3_RELEASE_EVIDENCE_RECEIPT_V1",
            "timestamp_start_utc": result["timestamp_start_utc"],
            "timestamp_end_utc": utc_now(),
            "script": file_fact(Path(__file__)),
            "script_copy": file_fact(SCRIPT_COPY),
            "upstream": post_audit["upstream"],
            "evidence": post_audit["evidence"],
            "session_a_checkpoint": file_fact(SESSION_A_CHECKPOINT),
            "session_b_checkpoint": file_fact(SESSION_B_CHECKPOINT),
            "session_b_checkpoint_sha256": sha256(SESSION_B_CHECKPOINT),
            "acceptance_matrix": file_fact(ACCEPTANCE_MATRIX),
            "manifest": file_fact(FINAL_MANIFEST),
            "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
            "accepted_urdf_overwritten": False,
            "pack_and_go_critical_external_reference_count": 0,
            "pack_and_go_missing_reference_count": 0,
            "native_slddrw_pdf_pair_count": len(DRAWING_SPECS),
            "raw_annotated_shot_pair_count": len(SHOT_NAMES),
            "digital_thread_file_count": len(DIGITAL_FILES),
            "prohibited_claims": {name: False for name in PROHIBITED_CLAIMS},
            "holds": list(REQUIRED_HOLDS),
            "final_gate_eligible": True,
            "receipt_written_last": True,
            "mechanical_authoring_after_gate": "ECR_ONLY",
            "highest_allowed_claim": HIGHEST_ALLOWED_CLAIM,
            "verdict": HIGHEST_ALLOWED_CLAIM,
        }
        write_json_once(FINAL_RECEIPT, final)
        print(json.dumps({"verdict": final["verdict"], "receipt": file_fact(FINAL_RECEIPT), "manifest": file_fact(FINAL_MANIFEST), "session_b_pid": session["pid"], "solidworks_document_count": int(base.value(sw, "GetDocumentCount"))}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        result.update({"timestamp_end_utc": utc_now(), "verdict": getattr(exc, "code", "SESSION_B_UNEXPECTED_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", None), "traceback": traceback.format_exc()})
        failed = failure_receipt("SESSION_B", result)
        if failed:
            result["failure_receipt"] = file_fact(failed)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    finally:
        if sw is not None and base is not None:
            try:
                close_owned(sw, base)
            except Exception:
                pass
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def negative_test() -> Dict[str, Any]:
    valid_claims = {
        "schema": "F3R2_V5_RELEASE_CLAIMS_V1",
        "highest_allowed_claim": HIGHEST_ALLOWED_CLAIM,
        "mechanical_authoring_after_gate": "ECR_ONLY",
        "prohibited_claims": {name: False for name in PROHIBITED_CLAIMS},
        "holds": list(REQUIRED_HOLDS),
    }
    bad_claims = json.loads(json.dumps(valid_claims))
    bad_claims["prohibited_claims"][PROHIBITED_CLAIMS[0]] = True
    valid_mass = {
        "schema": "F3R2_V5_EXTERNAL_MECHANICAL_MASS_SUMMARY_V1",
        "boundary_definition": "V5_EXTERNAL_MECHANICAL_ONLY_EXCLUDES_ACCEPTED_B601_URDF",
        "mass_properties_coordinate_frame": "SPACECRAFT_WORLD",
        "source_csv_sha256": "A" * 64,
        "accepted_b601_urdf": {"sha256": ACCEPTED_URDF_SHA256, "cad_override_allowed": False},
        "external_mechanical_only": True,
        "accepted_urdf_overwritten": False,
        "external_system_com_m": [0.0, 0.0, 0.0],
        "external_inertia_about_external_com_kg_m2": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "total_external_mass_kg": 1.0,
        "verdict": "V5_EXTERNAL_MECHANICAL_MASS_COM_INERTIA_SEPARATE_PASS",
    }
    bad_mass = json.loads(json.dumps(valid_mass))
    bad_mass["accepted_urdf_overwritten"] = True
    source_top_hash = sha256(TOP) if TOP.is_file() else None
    valid_pack = {
        "schema": "F3R2_V5_PACK_AND_GO_PROOF_V1",
        "method": "SOLIDWORKS_PACK_AND_GO",
        "critical_external_reference_count": 0,
        "missing_reference_count": 0,
        "reference_count": 1,
        "reference_ledger_sha256": "B" * 64,
        "package_top": {"sha256": "C" * 64},
        "source_top": {"sha256": source_top_hash},
        "verdict": "V5_PACK_AND_GO_SELF_CONTAINED_PASS",
    }
    bad_pack = json.loads(json.dumps(valid_pack))
    bad_pack["critical_external_reference_count"] = 1
    session_a = {"pid": 100, "process_create_time_epoch": 1000.0, "document_count": 0, "active_doc_is_null": True}
    fresh_b = {"pid": 101, "process_create_time_epoch": 1001.0, "document_count": 0, "active_doc_is_null": True}
    same_b = dict(session_a)
    checks = {
        "valid_claims_accept": validate_claims_payload(valid_claims),
        "prohibited_claim_true_rejected": not validate_claims_payload(bad_claims),
        "valid_mass_boundary_accept": validate_mass_summary(valid_mass, 1.0, "A" * 64),
        "accepted_urdf_overwrite_rejected": not validate_mass_summary(bad_mass, 1.0, "A" * 64),
        "valid_pack_zero_external_accept": validate_pack_proof(valid_pack, "C" * 64, "B" * 64, 1),
        "critical_external_reference_rejected": not validate_pack_proof(bad_pack, "C" * 64, "B" * 64, 1),
        "fresh_session_pair_accept": validate_session_pair(session_a, fresh_b),
        "same_session_rejected": not validate_session_pair(session_a, same_b),
        "nonphysical_inertia_rejected": not physical_inertia(1.0, 1.0, -1.0, 0.0, 0.0, 0.0),
    }
    return {"schema": "F3R2_V5_LOOP3_NEGATIVE_TEST_V1", "timestamp_utc": utc_now(), "checks": checks, "pass": all(checks.values()), "solidworks_attached": False, "filesystem_mutated": False, "verdict": "V5_LOOP3_NEGATIVE_TEST_PASS" if all(checks.values()) else "V5_LOOP3_NEGATIVE_TEST_FAIL"}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F3R2 V5 Loop-3 Release/Evidence fail-closed framework")
    parser.add_argument("command", nargs="?", default="audit", choices=("audit", "negative-test", "session-a", "session-b"))
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    command = parse_args(argv).command
    if command == "audit":
        report = static_audit()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if report["verdict"] == "V5_LOOP3_STATIC_HOLD" else 0
    if command == "negative-test":
        report = negative_test()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["pass"] else 2
    if command == "session-a":
        return session_a_execute()
    return session_b_execute()


if __name__ == "__main__":
    sys.exit(main())
