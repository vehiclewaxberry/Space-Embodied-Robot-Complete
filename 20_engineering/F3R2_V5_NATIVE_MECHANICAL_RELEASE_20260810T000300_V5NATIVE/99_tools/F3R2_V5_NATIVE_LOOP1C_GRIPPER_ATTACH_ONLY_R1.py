#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loop 1C0: split the frozen B51 58-body gripper into three native parts.

This executable is deliberately limited to the transaction that can be
closed independently: PALM (10 bodies), LEFT_FINGER (24), RIGHT_FINGER (24).
Loop 1C1 owns the native prismatic-mate assembly and the CLOSED/PREGRASP/OPEN
configuration proof.  Nothing in this file claims that 1C1 is complete.

Runtime access is inherited from the hash-pinned Loop-1 helper and is strictly
GetActiveObject-only.  The input body order is never authoritative: every
body is bound by normalized name, exact face count, and volume before Copy2.
Each target body is created with IBody2.Copy2(True) followed by
IPartDoc.CreateFeatureFromBody3(copy, False, swCreateFeatureBodyCheck).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import traceback
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
RUN_ID = "20260810T000300_V5NATIVE"

PART_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot")
PART_TEMPLATE_SHA256 = "5DA21678EFE07EF465770630BEB4FFE540F23D47FCA07715F74D2AFDBEA87271"

IMPORT_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
IMPORT_RECEIPT_SHA256 = "9FC8D1DBBBDD7D1FE37F5FCCA4359838827282A0D7A961D8EEB511E75BE7160D"
AUTHORITY_RECEIPT = RUN_ROOT / "13_validation/V5_AUTHORITY_SEED_RECEIPT.json"
AUTHORITY_RECEIPT_SHA256 = "7251758420639907CAB4F4C134A278B0F860535BCC62A8E264E6862B7ECBED0F"
LOOP1A_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1A_SUBASSEMBLY_RECEIPT.json"
LOOP1A_RECEIPT_SHA256 = "F946A361A7CFF8143753853911F23178AF68592D2F7BBE09990575ED86E9BF49"

BASE_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_SHA256 = "1F589D3FAE23D64F2364B1CE98FA232A1AA19648398521E55CB5C7F85D0B6062"
LOOP1A_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY.py"
LOOP1A_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY.py"
LOOP1A_HELPER_SHA256 = "25369CB867685EBA0C374636F8F540867D3D8B5890F9CE8622A6842E6518EC42"

SOURCE_PART = ROOT / (
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/"
    "B601_ARM_B51_COPY/inputs/vendor_link_parts/B51_REF_gripper_detail_LINKLOCAL.SLDPRT"
)
SOURCE_PART_SHA256 = "6758B99741FFACABC31C2D629C6191F25C461AC877442212B468B141805EEECC"
SOURCE_PART_BYTES = 5_277_750
ASSIGNMENT_CSV = ROOT / (
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/"
    "F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"
)
ASSIGNMENT_CSV_SHA256 = "419F63149413E5EC5677357D95639CFACF68CE143964485EFB402F2A803B2C78"

SW_DOC_PART = 1
SW_OPEN_SILENT_READONLY = 3
SW_CREATE_FEATURE_BODY_CHECK = 1
VOLUME_ABS_TOL_MM3 = 0.02
VOLUME_REL_TOL = 5.0e-6

GROUPS: Dict[str, Dict[str, Any]] = {
    "gripper_link": {
        "role": "PALM",
        "count": 10,
        "target": RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_PALM.SLDPRT",
    },
    "gripper_left": {
        "role": "LEFT_FINGER",
        "count": 24,
        "target": RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_LEFT_FINGER.SLDPRT",
    },
    "gripper_right": {
        "role": "RIGHT_FINGER",
        "count": 24,
        "target": RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_RIGHT_FINGER.SLDPRT",
    },
}

CHECKPOINTS = {
    key: RUN_ROOT / f"13_validation/V5_LOOP1C0_CHECKPOINT_{spec['role']}.json"
    for key, spec in GROUPS.items()
}
FINAL_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json"
FINAL_MANIFEST = RUN_ROOT / "14_release/V5_LOOP1C0_GRIPPER_NATIVE_PART_MANIFEST_SHA256.txt"
PREDECESSOR_SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY.py"
PREDECESSOR_SCRIPT_COPY_SHA256 = "D551B552F861F9B7B9DDEE37558C82B8786C322B87FA10C535F798CA77CFA533"
PREDECESSOR_SCRIPT_COPY_BYTES = 39666
SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY_R1.py"


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return base.sha256(path)


def posix(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise GateError("JSON_ROOT_FAIL", "JSON root must be an object", {"path": posix(path)})
    return payload


def write_json_once(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def copy_once(source: Path, target: Path) -> None:
    if target.exists():
        if not target.is_file() or target.stat().st_size != source.stat().st_size or sha256(target) != sha256(source):
            raise GateError("SCRIPT_COPY_DRIFT", "existing write-once script copy does not match this executable")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
    if target.stat().st_size != source.stat().st_size or sha256(target) != sha256(source):
        raise GateError("SCRIPT_COPY_FAIL", "write-once script copy failed identity readback")


def normalize_body_name(name: str) -> str:
    # NFKC/casefold is used only for lookup.  The original CSV spelling and
    # the complete three-digit suffix remain part of the recorded authority.
    return unicodedata.normalize("NFKC", str(name)).strip().casefold()


def volume_matches(actual_mm3: float, expected_mm3: float) -> bool:
    tolerance = max(VOLUME_ABS_TOL_MM3, abs(expected_mm3) * VOLUME_REL_TOL)
    return math.isfinite(actual_mm3) and abs(actual_mm3 - expected_mm3) <= tolerance


def fixed_files() -> List[Tuple[Path, str, Optional[int]]]:
    return [
        (PART_TEMPLATE, PART_TEMPLATE_SHA256, None),
        (IMPORT_RECEIPT, IMPORT_RECEIPT_SHA256, None),
        (AUTHORITY_RECEIPT, AUTHORITY_RECEIPT_SHA256, None),
        (LOOP1A_RECEIPT, LOOP1A_RECEIPT_SHA256, None),
        (BASE_HELPER, BASE_HELPER_SHA256, None),
        (BASE_HELPER_COPY, BASE_HELPER_SHA256, None),
        (LOOP1A_HELPER, LOOP1A_HELPER_SHA256, None),
        (LOOP1A_HELPER_COPY, LOOP1A_HELPER_SHA256, None),
        (SOURCE_PART, SOURCE_PART_SHA256, SOURCE_PART_BYTES),
        (ASSIGNMENT_CSV, ASSIGNMENT_CSV_SHA256, None),
        # The first fail-closed attempt copied its exact executor before the
        # PID-schema defect was detected.  Preserve and hash-bind that file as
        # immutable failure evidence; the corrected executor uses a new,
        # write-once R1 filename rather than overwriting history.
        (PREDECESSOR_SCRIPT_COPY, PREDECESSOR_SCRIPT_COPY_SHA256, PREDECESSOR_SCRIPT_COPY_BYTES),
    ]


def audit_fixed_inputs() -> List[Dict[str, Any]]:
    roots = sorted(
        path.resolve()
        for path in (ROOT / "20_engineering").glob("F3R2_V5_NATIVE_MECHANICAL_RELEASE_*")
        if path.is_dir()
    )
    if roots != [RUN_ROOT.resolve()]:
        raise GateError(
            "UNIQUE_V5_ROOT_FAIL",
            "the fixed V5 root is not the unique formal V5 release root",
            {"roots": [posix(path) for path in roots], "expected": posix(RUN_ROOT)},
        )
    rows: List[Dict[str, Any]] = []
    for path, expected_hash, expected_bytes in fixed_files():
        exists = path.is_file()
        actual_hash = sha256(path) if exists else None
        actual_bytes = path.stat().st_size if exists else None
        passed = exists and actual_hash == expected_hash and (
            expected_bytes is None or actual_bytes == expected_bytes
        )
        rows.append(
            {
                "path": posix(path),
                "exists": exists,
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
                "expected_bytes": expected_bytes,
                "actual_bytes": actual_bytes,
                "pass": passed,
            }
        )
    if not all(row["pass"] for row in rows):
        raise GateError("FIXED_INPUT_HASH_FAIL", "a fixed receipt/helper/template/source drifted", {"audits": rows})
    imported = load_json(IMPORT_RECEIPT)
    loop1a = load_json(LOOP1A_RECEIPT)
    if imported.get("verdict") != "V5_LOOP1_NEUTRAL_NATIVE_PART_IMPORT_PASS" or imported.get("native_part_count") != 20:
        raise GateError("IMPORT_RECEIPT_FAIL", "the fixed 20-part import PASS is absent")
    if loop1a.get("verdict") != "V5_LOOP1A_ADAPTER_SUPPORT_SUBASSEMBLIES_PASS":
        raise GateError("LOOP1A_RECEIPT_FAIL", "the fixed Loop1A PASS is absent")
    return rows


def read_assignment() -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {key: [] for key in GROUPS}
    seen: Dict[str, str] = {}
    with ASSIGNMENT_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"solid", "assigned_body", "volume_mm3", "faces"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise GateError("CSV_SCHEMA_FAIL", "assignment CSV lacks required columns", {"columns": reader.fieldnames})
        for row_number, raw in enumerate(reader, start=2):
            name = str(raw["solid"]).strip()
            group = str(raw["assigned_body"]).strip()
            normalized = normalize_body_name(name)
            if not name or group not in groups:
                raise GateError("CSV_ROW_FAIL", "blank body or unknown assignment", {"row": row_number, "body": name, "group": group})
            if normalized in seen:
                raise GateError("CSV_DUPLICATE_BODY", "normalized body name is duplicated", {"row": row_number, "body": name, "prior": seen[normalized]})
            if not name.startswith("B51_REF_gripper_detail_LINKLOCAL"):
                raise GateError("CSV_BODY_PREFIX_FAIL", "body name is outside the frozen B51 namespace", {"body": name})
            suffix = name.removeprefix("B51_REF_gripper_detail_LINKLOCAL")
            if suffix and (len(suffix) != 3 or not suffix.isdigit()):
                raise GateError("CSV_BODY_SUFFIX_FAIL", "numbered B51 body lacks its exact three-digit suffix", {"body": name})
            try:
                volume = float(raw["volume_mm3"])
                faces = int(raw["faces"])
            except (TypeError, ValueError) as exc:
                raise GateError("CSV_NUMERIC_FAIL", "face/volume field is invalid", {"row": row_number, "body": name}) from exc
            if not math.isfinite(volume) or volume <= 0.0 or faces <= 0:
                raise GateError("CSV_NUMERIC_RANGE_FAIL", "face/volume field is not positive finite", {"body": name, "volume_mm3": volume, "faces": faces})
            item = {
                "source_name": name,
                "normalized_name": normalized,
                "assigned_body": group,
                "volume_mm3": volume,
                "faces": faces,
                "row": row_number,
            }
            groups[group].append(item)
            seen[normalized] = name
    if len(seen) != 58:
        raise GateError("CSV_ROW_COUNT_FAIL", "assignment CSV must bind exactly 58 unique solids", {"count": len(seen)})
    for key, spec in GROUPS.items():
        groups[key].sort(key=lambda item: item["source_name"])
        if len(groups[key]) != int(spec["count"]):
            raise GateError("CSV_GROUP_COUNT_FAIL", "assignment group count drifted", {"group": key, "actual": len(groups[key]), "expected": spec["count"]})
        for index, item in enumerate(groups[key], start=1):
            item["semantic_name"] = f"{spec['role']}_SOLID_{index:02d}__{item['source_name']}"
            item["feature_name"] = f"{spec['role']}_BODY_{index:02d}"
    return groups


def assignment_summary(groups: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    return {
        key: {
            "role": GROUPS[key]["role"],
            "body_count": len(items),
            "face_count": sum(int(item["faces"]) for item in items),
            "volume_mm3": round(sum(float(item["volume_mm3"]) for item in items), 6),
            "source_names": [item["source_name"] for item in items],
        }
        for key, items in groups.items()
    }


def binding() -> Dict[str, Any]:
    script = Path(__file__).resolve()
    return {
        "run_id": RUN_ID,
        "script_sha256": sha256(script),
        "base_helper_sha256": BASE_HELPER_SHA256,
        "loop1a_helper_sha256": LOOP1A_HELPER_SHA256,
        "import_receipt_sha256": IMPORT_RECEIPT_SHA256,
        "authority_receipt_sha256": AUTHORITY_RECEIPT_SHA256,
        "loop1a_receipt_sha256": LOOP1A_RECEIPT_SHA256,
        "source_part_sha256": SOURCE_PART_SHA256,
        "assignment_csv_sha256": ASSIGNMENT_CSV_SHA256,
        "part_template_sha256": PART_TEMPLATE_SHA256,
        "copy_api": "IBody2.Copy2(True)",
        "insert_api": "IPartDoc.CreateFeatureFromBody3(body,False,1)",
    }


def checkpoint_state(key: str) -> Dict[str, Any]:
    target = Path(GROUPS[key]["target"])
    checkpoint = CHECKPOINTS[key]
    target_exists = target.is_file()
    checkpoint_exists = checkpoint.is_file()
    row: Dict[str, Any] = {
        "group": key,
        "target": posix(target),
        "checkpoint": posix(checkpoint),
        "target_exists": target_exists,
        "checkpoint_exists": checkpoint_exists,
    }
    if not target_exists and not checkpoint_exists:
        row["state"] = "PENDING"
        return row
    if target_exists != checkpoint_exists:
        row["state"] = "HOLD_ORPHAN_WRITE_ONCE_ARTIFACT"
        return row
    payload = load_json(checkpoint)
    expected = binding()
    fact = payload.get("target", {})
    row["checkpoint_schema"] = payload.get("schema")
    row["binding_match"] = payload.get("binding") == expected
    row["target_hash_match"] = fact.get("sha256") == sha256(target)
    row["target_bytes_match"] = fact.get("bytes") == target.stat().st_size
    row["verdict"] = payload.get("verdict")
    passed = (
        payload.get("schema") == "F3R2_V5_LOOP1C0_PART_CHECKPOINT_V1"
        and payload.get("group") == key
        and payload.get("binding") == expected
        and fact.get("path") == posix(target)
        and fact.get("sha256") == sha256(target)
        and fact.get("bytes") == target.stat().st_size
        and payload.get("verdict") == "V5_LOOP1C0_NATIVE_PART_CHECKPOINT_PASS"
    )
    row["state"] = "RESUME_REQUIRES_COLD_REOPEN" if passed else "HOLD_CHECKPOINT_BINDING_FAIL"
    return row


def static_audit() -> Dict[str, Any]:
    fixed = audit_fixed_inputs()
    groups = read_assignment()
    protected = base.audit_protected()
    states = [checkpoint_state(key) for key in GROUPS]
    holds = [row for row in states if row["state"].startswith("HOLD")]
    script_copy_state = (
        "ABSENT_PENDING"
        if not SCRIPT_COPY.exists()
        else "EXACT_RESUME"
        if SCRIPT_COPY.is_file()
        and SCRIPT_COPY.stat().st_size == Path(__file__).stat().st_size
        and sha256(SCRIPT_COPY) == sha256(Path(__file__))
        else "HOLD_SCRIPT_COPY_DRIFT"
    )
    if script_copy_state.startswith("HOLD"):
        holds.append({"state": script_copy_state, "path": posix(SCRIPT_COPY)})
    complete_exists = FINAL_RECEIPT.exists() or FINAL_MANIFEST.exists()
    return {
        "schema": "F3R2_V5_LOOP1C0_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "script": {"path": posix(Path(__file__)), "bytes": Path(__file__).stat().st_size, "sha256": sha256(Path(__file__))},
        "fixed_inputs": fixed,
        "assignment": assignment_summary(groups),
        "protected_assets": protected,
        "checkpoint_states": states,
        "script_copy_state": script_copy_state,
        "final_receipt_exists": FINAL_RECEIPT.exists(),
        "final_manifest_exists": FINAL_MANIFEST.exists(),
        "execution_authorized": not holds and not complete_exists,
        "scope": "1C0_THREE_NATIVE_PARTS_ONLY",
        "remaining_hold": [
            "1C1_NATIVE_GRIPPER_ASSEMBLY",
            "1C1_TWO_GUIDE_COINCIDENT_PLUS_ADVANCED_LIMIT_DISTANCE_PER_FINGER",
            "1C1_CLOSED_PREGRASP_OPEN_CONFIGURATION_PROOF",
            "1C1_TRANSFORM_CLEARANCE_INTERFERENCE_REFERENCE_AND_MATE_LEDGER",
        ],
        "verdict": (
            "V5_LOOP1C0_STATIC_AUDIT_PASS_EXECUTION_AUTHORIZED"
            if not holds and not complete_exists
            else "V5_LOOP1C0_STATIC_AUDIT_PASS_ALREADY_COMPLETE"
            if not holds and FINAL_RECEIPT.exists() and FINAL_MANIFEST.exists()
            else "V5_LOOP1C0_STATIC_AUDIT_HOLD"
        ),
    }


def body_name(body: Any) -> str:
    name = str(base.value(body, "Name"))
    if not name:
        raise GateError("BODY_NAME_EMPTY", "IBody2.Name is empty")
    return name


def body_evidence(body: Any) -> Dict[str, Any]:
    if not bool(base.value(body, "IsSolidBody")):
        raise GateError("BODY_NOT_SOLID", "a bound body is not a solid", {"body": body_name(body)})
    faces = int(base.value(body, "GetFaceCount"))
    mass = [float(value) for value in base.as_list(body.GetMassProperties(1.0))]
    if len(mass) < 4 or not math.isfinite(mass[3]) or mass[3] <= 0.0:
        raise GateError("BODY_MASS_PROPERTIES_FAIL", "IBody2.GetMassProperties did not return a positive volume", {"body": body_name(body), "mass_properties": mass})
    return {"name": body_name(body), "faces": faces, "volume_mm3": mass[3] * 1.0e9, "solid": True}


def map_source_bodies(model: Any, groups: Dict[str, List[Dict[str, Any]]], types: Any, pythoncom: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    part = base.wrap(model, "IPartDoc", types, pythoncom)
    raw_bodies = base.as_list(part.GetBodies2(0, False))
    if len(raw_bodies) != 58:
        raise GateError("SOURCE_BODY_COUNT_FAIL", "source part must expose exactly 58 solid bodies", {"count": len(raw_bodies)})
    expected = {item["normalized_name"]: item for items in groups.values() for item in items}
    mapped: Dict[str, Any] = {}
    evidence: List[Dict[str, Any]] = []
    for raw in raw_bodies:
        body = base.wrap(raw, "IBody2", types, pythoncom)
        facts = body_evidence(body)
        normalized = normalize_body_name(facts["name"])
        if normalized in mapped:
            raise GateError("SOURCE_BODY_DUPLICATE", "source contains duplicate normalized body names", {"body": facts["name"]})
        if normalized not in expected:
            raise GateError("SOURCE_BODY_UNMAPPED", "source body is absent from the 58-row assignment", facts)
        contract = expected[normalized]
        if facts["name"] != contract["source_name"]:
            raise GateError("SOURCE_BODY_SPELLING_FAIL", "source and CSV body spellings differ after normalized lookup", {"actual": facts["name"], "expected": contract["source_name"]})
        if facts["faces"] != int(contract["faces"]) or not volume_matches(facts["volume_mm3"], float(contract["volume_mm3"])):
            raise GateError("SOURCE_BODY_GEOMETRY_FAIL", "source body face/volume signature drifted", {"actual": facts, "expected": contract})
        mapped[normalized] = body
        evidence.append({**facts, "assigned_body": contract["assigned_body"], "csv_volume_mm3": contract["volume_mm3"], "csv_faces": contract["faces"]})
    if set(mapped) != set(expected):
        raise GateError("SOURCE_BODY_COVERAGE_FAIL", "source/CSV body-name sets do not conserve", {"missing": sorted(set(expected) - set(mapped)), "extra": sorted(set(mapped) - set(expected))})
    return mapped, sorted(evidence, key=lambda row: row["name"])


def set_part_properties(model: Any, key: str, items: Sequence[Dict[str, Any]]) -> None:
    spec = GROUPS[key]
    properties = {
        "PartNumber": Path(spec["target"]).stem,
        "Description": f"F3R2 B601 gripper {spec['role']} native multibody part",
        "Revision": "V5-A",
        "RUN_ID": RUN_ID,
        "LOOP": "1C0",
        "REPRESENTATION_LAYER": "L1_SOLIDWORKS_NATIVE_COPY2_BODY_FEATURES",
        "SOURCE_B51_PART": SOURCE_PART.name,
        "SOURCE_B51_SHA256": SOURCE_PART_SHA256,
        "SOLID_ASSIGNMENT_SHA256": ASSIGNMENT_CSV_SHA256,
        "SOURCE_SOLID_COUNT": str(len(items)),
        "BODY_COPY_API": "IBody2.Copy2(True)",
        "BODY_INSERT_API": "IPartDoc.CreateFeatureFromBody3(False,swCreateFeatureBodyCheck)",
        "EXTERNAL_REFERENCE_POLICY": "ZERO",
        "ASSEMBLY_KINEMATICS": "HOLD_LOOP1C1",
        "AUTHORIZED_LAUNCH_LOAD": "HOLD",
        "FLIGHT_QUALIFICATION": "HOLD",
    }
    manager = model.Extension.CustomPropertyManager("")
    for name, value in properties.items():
        result = int(manager.Add3(str(name), 30, str(value), 2))
        if result < 0:
            raise GateError("CUSTOM_PROPERTY_WRITE_FAIL", "cannot set native part property", {"name": name, "result": result})


def audit_target_model(model: Any, key: str, items: Sequence[Dict[str, Any]], types: Any, pythoncom: Any) -> Dict[str, Any]:
    part = base.wrap(model, "IPartDoc", types, pythoncom)
    raw_bodies = base.as_list(part.GetBodies2(0, False))
    if len(raw_bodies) != len(items):
        raise GateError("TARGET_BODY_COUNT_FAIL", "target native part body count is wrong", {"group": key, "actual": len(raw_bodies), "expected": len(items)})
    expected = {normalize_body_name(item["semantic_name"]): item for item in items}
    actual: Dict[str, Dict[str, Any]] = {}
    for raw in raw_bodies:
        body = base.wrap(raw, "IBody2", types, pythoncom)
        facts = body_evidence(body)
        normalized = normalize_body_name(facts["name"])
        if normalized in actual or normalized not in expected:
            raise GateError("TARGET_BODY_NAME_FAIL", "target body name is duplicate or unauthorized", facts)
        contract = expected[normalized]
        if facts["name"] != contract["semantic_name"]:
            raise GateError("TARGET_BODY_SPELLING_FAIL", "target semantic body name did not persist exactly", {"actual": facts["name"], "expected": contract["semantic_name"]})
        if facts["faces"] != int(contract["faces"]) or not volume_matches(facts["volume_mm3"], float(contract["volume_mm3"])):
            raise GateError("TARGET_BODY_GEOMETRY_FAIL", "target body face/volume signature drifted", {"actual": facts, "expected": contract})
        actual[normalized] = facts
    if set(actual) != set(expected):
        raise GateError("TARGET_BODY_COVERAGE_FAIL", "target semantic body-name set is incomplete")
    interconnect = base.feature_names_3d_interconnect(model, types, pythoncom)
    external = base.external_reference_count(model, GROUPS[key]["role"])
    auxiliary = base.auxiliary_reference_count(model, GROUPS[key]["role"])
    if interconnect or external != 0 or auxiliary != 0:
        raise GateError("TARGET_REFERENCE_FAIL", "target retained linked/import/interconnect references", {"interconnect": interconnect, "external": external, "auxiliary": auxiliary})
    return {
        "group": key,
        "role": GROUPS[key]["role"],
        "body_count": len(actual),
        "face_count": sum(row["faces"] for row in actual.values()),
        "volume_mm3": sum(row["volume_mm3"] for row in actual.values()),
        "bodies": sorted(actual.values(), key=lambda row: row["name"]),
        "three_d_interconnect_features": interconnect,
        "external_reference_count": external,
        "auxiliary_reference_count": auxiliary,
    }


def close_owned(sw: Any, title: str, owned_titles: List[str]) -> None:
    if title:
        sw.CloseDoc(title)
        while title in owned_titles:
            owned_titles.remove(title)


def cold_verify(sw: Any, path: Path, key: str, items: Sequence[Dict[str, Any]], types: Any, pythoncom: Any, owned_titles: List[str]) -> Dict[str, Any]:
    baseline = int(base.value(sw, "GetDocumentCount"))
    model = None
    title = ""
    try:
        model, opened = base.open_read_only(sw, path, types, pythoncom)
        title = str(base.value(model, "GetTitle"))
        owned_titles.append(title)
        facts = audit_target_model(model, key, items, types, pythoncom)
        return {"open": opened, "facts": facts}
    finally:
        if title:
            close_owned(sw, title, owned_titles)
        if int(base.value(sw, "GetDocumentCount")) != baseline:
            raise GateError("COLD_CLOSE_FAIL", "cold-opened target remained in the SolidWorks session", {"path": posix(path), "baseline": baseline, "actual": int(base.value(sw, "GetDocumentCount"))})


def build_part(sw: Any, key: str, items: Sequence[Dict[str, Any]], mapped: Dict[str, Any], types: Any, pythoncom: Any, owned_titles: List[str]) -> Dict[str, Any]:
    target = Path(GROUPS[key]["target"])
    if target.exists():
        raise GateError("TARGET_EXISTS", "write-once native part target already exists", {"target": posix(target)})
    baseline = int(base.value(sw, "GetDocumentCount"))
    raw_model = sw.NewDocument(str(PART_TEMPLATE), 0, 0.0, 0.0)
    if raw_model is None:
        raise GateError("NEW_PART_FAIL", "NewDocument returned null", {"group": key})
    model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
    title = str(base.value(model, "GetTitle"))
    owned_titles.append(title)
    try:
        if int(base.value(sw, "GetDocumentCount")) != baseline + 1:
            raise GateError("NEW_PART_DOCUMENT_COUNT_FAIL", "new part did not add exactly one owned document")
        part = base.wrap(model, "IPartDoc", types, pythoncom)
        if base.as_list(part.GetBodies2(0, False)):
            raise GateError("PART_TEMPLATE_NOT_EMPTY", "fixed part template unexpectedly contains solid bodies")
        created: List[Dict[str, Any]] = []
        for index, contract in enumerate(items, start=1):
            source = mapped[contract["normalized_name"]]
            before = len(base.as_list(part.GetBodies2(0, False)))
            copied_raw = source.Copy2(True)
            if copied_raw is None:
                raise GateError("BODY_COPY2_NULL", "IBody2.Copy2(True) returned null", {"source": contract["source_name"]})
            copied = base.wrap(copied_raw, "IBody2", types, pythoncom)
            copied.Name = contract["semantic_name"]
            if body_name(copied) != contract["semantic_name"]:
                raise GateError("COPIED_BODY_RENAME_FAIL", "temporary copied body name did not read back", {"source": contract["source_name"]})
            raw_feature = part.CreateFeatureFromBody3(copied, False, SW_CREATE_FEATURE_BODY_CHECK)
            if raw_feature is None:
                raise GateError("CREATE_FEATURE_FROM_BODY3_NULL", "CreateFeatureFromBody3 returned null", {"source": contract["source_name"]})
            feature = base.wrap(raw_feature, "IFeature", types, pythoncom)
            feature.Name = contract["feature_name"]
            after = len(base.as_list(part.GetBodies2(0, False)))
            if after != before + 1 or after != index:
                raise GateError("BODY_INSERT_CONSERVATION_FAIL", "CreateFeatureFromBody3 did not add exactly one body", {"source": contract["source_name"], "before": before, "after": after, "expected_after": index})
            created.append({"source_name": contract["source_name"], "semantic_name": contract["semantic_name"], "feature_name": str(base.value(feature, "Name")), "body_count_after": after})
        set_part_properties(model, key, items)
        live = audit_target_model(model, key, items, types, pythoncom)
        saved = base.save_native_part(model, target)
        saved_title = str(base.value(model, "GetTitle"))
        if saved_title and saved_title != title:
            owned_titles.append(saved_title)
        return {"created": created, "live": live, "target": saved, "document_title": saved_title or title}
    except Exception:
        current = str(base.value(model, "GetTitle"))
        if current and current not in owned_titles:
            owned_titles.append(current)
        raise


def write_checkpoint(key: str, result: Dict[str, Any], cold: Dict[str, Any]) -> Dict[str, Any]:
    target = Path(GROUPS[key]["target"])
    payload = {
        "schema": "F3R2_V5_LOOP1C0_PART_CHECKPOINT_V1",
        "timestamp_utc": utc_now(),
        "group": key,
        "role": GROUPS[key]["role"],
        "binding": binding(),
        "target": {"path": posix(target), "bytes": target.stat().st_size, "sha256": sha256(target)},
        "result": result,
        "cold_reopen": cold,
        "verdict": "V5_LOOP1C0_NATIVE_PART_CHECKPOINT_PASS",
    }
    write_json_once(CHECKPOINTS[key], payload)
    return payload


def resume_part(sw: Any, key: str, items: Sequence[Dict[str, Any]], types: Any, pythoncom: Any, owned_titles: List[str]) -> Dict[str, Any]:
    state = checkpoint_state(key)
    if state["state"] != "RESUME_REQUIRES_COLD_REOPEN":
        raise GateError("RESUME_STATE_FAIL", "part checkpoint is not authorized for resume", state)
    cold = cold_verify(sw, Path(GROUPS[key]["target"]), key, items, types, pythoncom, owned_titles)
    return {"mode": "RESUMED", "checkpoint": load_json(CHECKPOINTS[key]), "cold_reopen_now": cold}


def cleanup_owned(sw: Any, owned_titles: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for title in reversed(list(dict.fromkeys(owned_titles))):
        try:
            sw.CloseDoc(title)
            rows.append({"title": title, "closed": True})
        except Exception as exc:
            rows.append({"title": title, "closed": False, "exception": repr(exc)})
    owned_titles.clear()
    try:
        count = int(base.value(sw, "GetDocumentCount"))
    except Exception:
        count = -1
    if count != 0:
        raise GateError("OWNED_DOCUMENT_CLEANUP_FAIL", "owned documents remain after cleanup", {"document_count": count, "attempts": rows})
    return rows


def conservation(results: Dict[str, Dict[str, Any]], groups: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    expected_names = {item["source_name"] for items in groups.values() for item in items}
    recorded_names: set[str] = set()
    body_count = 0
    face_count = 0
    volume = 0.0
    for key, row in results.items():
        facts = row["cold_reopen_now"]["facts"] if row.get("mode") == "RESUMED" else row["cold_reopen"]["facts"]
        body_count += int(facts["body_count"])
        face_count += int(facts["face_count"])
        volume += float(facts["volume_mm3"])
        recorded_names.update(item["source_name"] for item in groups[key])
    expected_faces = sum(int(item["faces"]) for items in groups.values() for item in items)
    expected_volume = sum(float(item["volume_mm3"]) for items in groups.values() for item in items)
    passed = body_count == 58 and face_count == expected_faces and recorded_names == expected_names and volume_matches(volume, expected_volume)
    evidence = {
        "body_count": body_count,
        "expected_body_count": 58,
        "face_count": face_count,
        "expected_face_count": expected_faces,
        "volume_mm3": volume,
        "expected_volume_mm3": expected_volume,
        "source_name_union_count": len(recorded_names),
        "source_name_union_exact": recorded_names == expected_names,
        "pass": passed,
    }
    if not passed:
        raise GateError("THREE_PART_CONSERVATION_FAIL", "cold-reopened three-part union does not conserve the 58-body source", evidence)
    return evidence


def manifest_text() -> str:
    paths = [Path(GROUPS[key]["target"]) for key in GROUPS] + [SCRIPT_COPY]
    return "".join(f"{sha256(path)}  {path.relative_to(RUN_ROOT).as_posix()}\n" for path in sorted(paths, key=lambda item: item.as_posix()))


def execute_parts() -> int:
    start = utc_now()
    script = Path(__file__).resolve()
    sw = types = pythoncom = None
    owned_titles: List[str] = []
    failure_cleanup: List[Dict[str, Any]] = []
    try:
        audit = static_audit()
        if not audit["execution_authorized"]:
            raise GateError("STATIC_EXECUTION_NOT_AUTHORIZED", "static audit did not authorize execution", audit)
        groups = read_assignment()
        protected_pre = base.audit_protected()
        memory_samples = base.memory_gate()
        copy_once(script, SCRIPT_COPY)
        sw, types, pythoncom, session = base.attach_empty_session()
        imported = load_json(IMPORT_RECEIPT)
        # The fixed Loop-1 receipt records Session B in both the SolidWorks
        # block and its anchored G0 block; it has no top-level session_b_pid.
        # Require those two immutable witnesses to agree before comparing the
        # live attach-only session so a missing key can never become -1.
        receipt_pid = int(imported.get("solidworks", {}).get("pid", -1))
        g0_pid = int(imported.get("g0", {}).get("session_b_pid", -2))
        if receipt_pid <= 0 or receipt_pid != g0_pid:
            raise GateError("SESSION_B_RECEIPT_BINDING_FAIL", "Loop-1 receipt does not contain two matching Session-B PID witnesses", {"solidworks_pid": receipt_pid, "g0_session_b_pid": g0_pid})
        expected_pid = receipt_pid
        if int(session["pid"]) != expected_pid:
            raise GateError("SESSION_B_PID_FAIL", "attached SolidWorks is not the fixed Loop-1 Session B process", {"actual": session["pid"], "expected": expected_pid})

        source_raw = source_model = None
        source_title = ""
        try:
            opened = sw.OpenDoc6(str(SOURCE_PART), SW_DOC_PART, SW_OPEN_SILENT_READONLY, "", 0, 0)
            if not isinstance(opened, tuple) or len(opened) < 3:
                raise GateError("SOURCE_OPEN_SHAPE_FAIL", "typed OpenDoc6 did not return model/errors/warnings", {"returned": repr(opened)})
            source_raw, outs = base.unpack(opened)
            errors, warnings = int(outs[0]), int(outs[1])
            if source_raw is None or errors != 0 or warnings != 0:
                raise GateError("SOURCE_OPEN_FAIL", "frozen B51 source did not open cleanly read-only", {"errors": errors, "warnings": warnings})
            source_model = base.wrap(source_raw, "IModelDoc2", types, pythoncom)
            source_title = str(base.value(source_model, "GetTitle"))
            owned_titles.append(source_title)
            if not bool(base.value(source_model, "IsOpenedReadOnly")):
                raise GateError("SOURCE_NOT_READ_ONLY", "frozen B51 source was not opened read-only")
            mapped, source_evidence = map_source_bodies(source_model, groups, types, pythoncom)

            results: Dict[str, Dict[str, Any]] = {}
            for key, items in groups.items():
                state = checkpoint_state(key)
                if state["state"] == "RESUME_REQUIRES_COLD_REOPEN":
                    results[key] = resume_part(sw, key, items, types, pythoncom, owned_titles)
                    continue
                if state["state"] != "PENDING":
                    raise GateError("PART_STATE_HOLD", "part state is neither pending nor authorized resume", state)
                built = build_part(sw, key, items, mapped, types, pythoncom, owned_titles)
                close_owned(sw, built["document_title"], owned_titles)
                cold = cold_verify(sw, Path(GROUPS[key]["target"]), key, items, types, pythoncom, owned_titles)
                checkpoint = write_checkpoint(key, built, cold)
                results[key] = {"mode": "CREATED", "build": built, "cold_reopen": cold, "checkpoint": checkpoint}
        finally:
            if source_title:
                close_owned(sw, source_title, owned_titles)

        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise GateError("POST_PART_DOCUMENT_COUNT_FAIL", "SolidWorks is not empty after owned part transaction", {"document_count": int(base.value(sw, "GetDocumentCount"))})
        conserved = conservation(results, groups)
        if sha256(SOURCE_PART) != SOURCE_PART_SHA256 or SOURCE_PART.stat().st_size != SOURCE_PART_BYTES or sha256(ASSIGNMENT_CSV) != ASSIGNMENT_CSV_SHA256:
            raise GateError("SOURCE_POST_IDENTITY_FAIL", "source part or assignment CSV drifted during transaction")
        protected_post = base.audit_protected()

        if FINAL_MANIFEST.exists() or FINAL_RECEIPT.exists():
            raise GateError("FINAL_WRITE_ONCE_EXISTS", "final Loop1C0 manifest/receipt already exists")
        FINAL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with FINAL_MANIFEST.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(manifest_text())
        final = {
            "schema": "F3R2_V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT_V1",
            "timestamp_start_utc": start,
            "timestamp_end_utc": utc_now(),
            "run_root": posix(RUN_ROOT),
            "binding": binding(),
            "session": session,
            "memory_gate_gib": memory_samples,
            "source_open": {"path": posix(SOURCE_PART), "read_only": True, "body_count": 58, "evidence": source_evidence},
            "assignment": assignment_summary(groups),
            "parts": results,
            "conservation": conserved,
            "protected_pre": protected_pre,
            "protected_post": protected_post,
            "manifest": {"path": posix(FINAL_MANIFEST), "bytes": FINAL_MANIFEST.stat().st_size, "sha256": sha256(FINAL_MANIFEST)},
            "scope_completed": "1C0_THREE_NATIVE_PARTS",
            "remaining_hold": [
                "1C1_NATIVE_GRIPPER_ASSEMBLY",
                "1C1_TWO_GUIDE_COINCIDENT_PLUS_ADVANCED_LIMIT_DISTANCE_PER_FINGER",
                "1C1_CLOSED_PREGRASP_OPEN_CONFIGURATION_PROOF",
                "1C1_TRANSFORM_CLEARANCE_INTERFERENCE_REFERENCE_AND_MATE_LEDGER",
            ],
            "no_slider_type_23_claim": True,
            "verdict": "V5_LOOP1C0_THREE_NATIVE_GRIPPER_PARTS_PASS_ASSEMBLY_HOLD",
        }
        write_json_once(FINAL_RECEIPT, final)
        print(json.dumps({"verdict": final["verdict"], "receipt": posix(FINAL_RECEIPT)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        code = exc.code if isinstance(exc, GateError) else "UNHANDLED_EXCEPTION"
        detail = exc.detail if isinstance(exc, GateError) else {}
        try:
            if sw is not None:
                failure_cleanup = cleanup_owned(sw, owned_titles)
        except Exception as cleanup_exc:
            failure_cleanup.append({"cleanup_gate": repr(cleanup_exc)})
        failure = {
            "schema": "F3R2_V5_LOOP1C0_FAILURE_RECEIPT_V1",
            "timestamp_utc": utc_now(),
            "code": code,
            "message": str(exc),
            "detail": detail,
            "traceback": traceback.format_exc(),
            "owned_document_cleanup": failure_cleanup,
            "write_once_policy": "NO_DELETE_NO_OVERWRITE; orphan target/checkpoint mismatch remains HOLD",
            "verdict": "V5_LOOP1C0_FAIL_CLOSED",
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        try:
            write_json_once(RUN_ROOT / f"13_validation/V5_LOOP1C0_FAIL_{stamp}.json", failure)
        except Exception:
            pass
        print(json.dumps({"verdict": failure["verdict"], "code": code, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        # COM detach only.  Never terminate, hide, or change ownership of the
        # manually started SolidWorks Session B process.
        sw = types = None
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F3R2 V5 Loop1C0 attach-only gripper three-part transaction")
    parser.add_argument("--execute-parts", action="store_true", help="execute only the 1C0 three-native-part transaction")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.execute_parts:
        return execute_parts()
    print(json.dumps(static_audit(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
