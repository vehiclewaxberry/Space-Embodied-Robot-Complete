#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loop 1C1: create and prove the native three-component B601 gripper.

The script attaches only to the already-qualified empty SOLIDWORKS 2024
Session B.  It never creates an application process.  Its only kinematic
claim is the evidence-backed prismatic equivalent required by this release:
two physical planar guide coincident mates and one advanced Type-5 limit
distance mate per finger.  Mate Type 23 is prohibited and is never presented
as evidence.

Loop 1C0 remains the owner of the corrected 57-body split (PALM 9, LEFT 24,
RIGHT 24).  Historical aggregate row LINKLOCAL057 is not an input here.
HOLDING has no independent geometric or force authority; it is deliberately
stored at the CLOSED geometry and carries an explicit no-actuator-model hold.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
RUN_ID = "20260810T000300_V5NATIVE"

ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\gb_assembly.asmdot")
ASSEMBLY_TEMPLATE_SHA256 = "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC"
BASE_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_SHA256 = "1F589D3FAE23D64F2364B1CE98FA232A1AA19648398521E55CB5C7F85D0B6062"
LOOP1C0_SCRIPT = ROOT / "70_tools/legacy_f3r2_root_scripts/F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY.py"
LOOP1C0_SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY_R3.py"
LOOP1C0_SCRIPT_SHA256 = "59BCAED201D58B7B585E34A3C1904B934E60D6E535A1A0A2784937934C403023"
LOOP1C0_SCRIPT_BYTES = 79_160
LOOP1C0_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json"

IMPORT_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
IMPORT_RECEIPT_SHA256 = "9FC8D1DBBBDD7D1FE37F5FCCA4359838827282A0D7A961D8EEB511E75BE7160D"
AUTHORITY_RECEIPT = RUN_ROOT / "13_validation/V5_AUTHORITY_SEED_RECEIPT.json"
AUTHORITY_RECEIPT_SHA256 = "7251758420639907CAB4F4C134A278B0F860535BCC62A8E264E6862B7ECBED0F"
BREP_PROBE = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/BREP_PROBE_GRIPPER.json"
BREP_PROBE_SHA256 = "89A1B589E6AB20F2CAB0C7415107908EF1D58307C0EDF2A4D1C25BE5B6330D8A"
M3R_BINDING = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/F3R2_GRIPPER_FINGER_BINDING_ADDENDUM_M3R_V2.json"
M3R_BINDING_SHA256 = "2C31E0D666C835F079E7FB8EF8C6FBC64114F816BAA389017F95F12A067649E6"
STATE_REGISTER = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/F3R2_GRIPPER_STATE_REGISTER_ADDENDUM_M3R_V2.csv"
STATE_REGISTER_SHA256 = "A2A6F3F6F6B061CDFEE4930527E40552E56EB42BEDDE4D036F7F7533E5149CD5"
TRAVEL_CLEARANCE = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/F3R2_GRIPPER_TRAVEL_CLEARANCE.csv"
TRAVEL_CLEARANCE_SHA256 = "F571F443B3FBBC6ACA471A7159B86FCC406A9F0DDD844A283CB6BE78FD5241AA"

PARTS: Dict[str, Dict[str, Any]] = {
    "PALM": {
        "path": RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_PALM.SLDPRT",
        "count": 9,
        "fixed": True,
    },
    "LEFT": {
        "path": RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_LEFT_FINGER.SLDPRT",
        "count": 24,
        "fixed": False,
    },
    "RIGHT": {
        "path": RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_RIGHT_FINGER.SLDPRT",
        "count": 24,
        "fixed": False,
    },
}
LOOP1C0_CHECKPOINTS = {
    "PALM": RUN_ROOT / "13_validation/V5_LOOP1C0_CHECKPOINT_PALM.json",
    "LEFT": RUN_ROOT / "13_validation/V5_LOOP1C0_CHECKPOINT_LEFT_FINGER.json",
    "RIGHT": RUN_ROOT / "13_validation/V5_LOOP1C0_CHECKPOINT_RIGHT_FINGER.json",
}

TARGET = RUN_ROOT / "02_native_subassemblies/B601_GRIPPER.SLDASM"
CHECKPOINT = RUN_ROOT / "13_validation/V5_LOOP1C1_CHECKPOINT_B601_GRIPPER_ASSEMBLY.json"
FINAL_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1C1_GRIPPER_ASSEMBLY_RECEIPT.json"
FINAL_MANIFEST = RUN_ROOT / "14_release/V5_LOOP1C1_GRIPPER_ASSEMBLY_MANIFEST_SHA256.txt"
SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY.py"

# Installed SOLIDWORKS 2024 swconst.tlb / makepy contracts.
SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT_READONLY = 3
SW_BODY_SOLID = 0
SW_COMPONENT_RESOLVED = 2
SW_MATE_COINCIDENT = 0
SW_MATE_DISTANCE = 5
SW_MATE_SLIDER = 23  # prohibited audit sentinel, never passed to AddMate3
SW_ALIGN_ALIGNED = 0
SW_ALIGN_ANTI = 1
SW_ADD_MATE_NO_ERROR = 1
SW_SET_VALUE_IN_SPECIFIC_CONFIGS = 3
SW_SET_VALUE_SUCCESS = 0

JAW_AXIS_RAW = (-0.000007, 0.906306, 0.422622)
_JAW_NORM = math.sqrt(sum(value * value for value in JAW_AXIS_RAW))
JAW_AXIS = tuple(value / _JAW_NORM for value in JAW_AXIS_RAW)

STATES: Dict[str, Dict[str, Any]] = {
    "OPEN": {"travel_mm": 71.5, "gap_mm": 82.2284, "authority": "M3R_V2"},
    "PREGRASP": {"travel_mm": 55.0, "gap_mm": 50.5026, "authority": "M3R_V2"},
    "CLOSED": {"travel_mm": 0.0, "gap_mm": 0.0, "authority": "M3R_V2_CONTACT"},
    "HOLDING": {
        "travel_mm": 0.0,
        "gap_mm": 0.0,
        "authority": "NO_INDEPENDENT_HOLDING_GEOMETRY_CLOSED_ALIAS",
        "grip_force": "NOT_EVALUATED_NO_ACTUATOR_MODEL",
    },
}

# FreeCAD B-rep values only nominate unique physical faces.  Runtime
# SOLIDWORKS faces must independently satisfy normal/plane/area and semantic
# body-name gates; enumeration order and largest-face fallbacks are forbidden.
GUIDE_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "A": {
        "normal": (0.0, 0.422618, -0.906308),
        "offset_mm": 186.2456,
        "PALM": {"source": "B51_REF_gripper_detail_LINKLOCAL012", "area_mm2": 1173.531},
        "LEFT": {"source": "B51_REF_gripper_detail_LINKLOCAL009", "area_mm2": 260.100},
        "RIGHT": {"source": "B51_REF_gripper_detail_LINKLOCAL004", "area_mm2": 260.100},
        "LEFT_alignment": SW_ALIGN_ALIGNED,
        "RIGHT_alignment": SW_ALIGN_ALIGNED,
    },
    "B": {
        "normal": (1.0, 0.0, 0.0),
        "offset_mm": 404.1637,
        "PALM": {"source": "B51_REF_gripper_detail_LINKLOCAL012", "area_mm2": 629.000},
        "LEFT": {"source": "B51_REF_gripper_detail_LINKLOCAL009", "area_mm2": 39.6049},
        "RIGHT": {"source": "B51_REF_gripper_detail_LINKLOCAL004", "area_mm2": 39.6049},
        "LEFT_alignment": SW_ALIGN_ALIGNED,
        "RIGHT_alignment": SW_ALIGN_ANTI,
    },
}

FACE_NORMAL_TOL = 5.0e-4
FACE_OFFSET_TOL_MM = 0.08
FACE_AREA_TOL_MM2 = 0.60
TRANSFORM_TRANSLATION_TOL_MM = 0.03
TRANSFORM_ROTATION_TOL = 2.0e-6
LIMIT_TOL_MM = 0.002
GAP_TOL_MM = 0.80
CLOSED_GAP_TOL_MM = 0.05
PALM_RAIL_CLEARANCE_MAX_MM = 0.08

MATE_NAMES = {
    "L_A": "MATE_L_GUIDE_A_COINCIDENT",
    "L_B": "MATE_L_GUIDE_B_COINCIDENT",
    "L_LIMIT": "MATE_L_TRAVEL_LIMIT_DISTANCE_ADVANCED",
    "R_A": "MATE_R_GUIDE_A_COINCIDENT",
    "R_B": "MATE_R_GUIDE_B_COINCIDENT",
    "R_LIMIT": "MATE_R_TRAVEL_LIMIT_DISTANCE_ADVANCED",
}


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


def write_json_once(path: Path, payload: Dict[str, Any]) -> None:
    if path.exists():
        raise GateError("WRITE_ONCE_JSON_EXISTS", "write-once JSON already exists", {"path": posix(path)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text_once(path: Path, text: str) -> None:
    if path.exists():
        raise GateError("WRITE_ONCE_TEXT_EXISTS", "write-once text already exists", {"path": posix(path)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def copy_once(source: Path, target: Path) -> None:
    if target.exists():
        if not target.is_file() or target.stat().st_size != source.stat().st_size or sha256(target) != sha256(source):
            raise GateError("SCRIPT_COPY_DRIFT", "existing write-once script copy differs from executable")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if target.stat().st_size != source.stat().st_size or sha256(target) != sha256(source):
        raise GateError("SCRIPT_COPY_FAIL", "script copy identity readback failed")


def file_fact(path: Path) -> Dict[str, Any]:
    return {
        "path": posix(path),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256(path) if path.is_file() else None,
    }


def fixed_fact(path: Path, expected_hash: str, expected_bytes: Optional[int] = None) -> Dict[str, Any]:
    fact = file_fact(path)
    fact.update({"expected_sha256": expected_hash, "expected_bytes": expected_bytes})
    fact["pass"] = fact["exists"] and fact["sha256"] == expected_hash and (expected_bytes is None or fact["bytes"] == expected_bytes)
    return fact


def known_fixed_files(include_loop1c0_copy: bool) -> List[Tuple[Path, str, Optional[int]]]:
    rows = [
        (ASSEMBLY_TEMPLATE, ASSEMBLY_TEMPLATE_SHA256, 34_942),
        (BASE_HELPER, BASE_HELPER_SHA256, None),
        (BASE_HELPER_COPY, BASE_HELPER_SHA256, None),
        (LOOP1C0_SCRIPT, LOOP1C0_SCRIPT_SHA256, LOOP1C0_SCRIPT_BYTES),
        (IMPORT_RECEIPT, IMPORT_RECEIPT_SHA256, None),
        (AUTHORITY_RECEIPT, AUTHORITY_RECEIPT_SHA256, None),
        (BREP_PROBE, BREP_PROBE_SHA256, None),
        (M3R_BINDING, M3R_BINDING_SHA256, None),
        (STATE_REGISTER, STATE_REGISTER_SHA256, None),
        (TRAVEL_CLEARANCE, TRAVEL_CLEARANCE_SHA256, None),
    ]
    if include_loop1c0_copy:
        rows.append((LOOP1C0_SCRIPT_COPY, LOOP1C0_SCRIPT_SHA256, LOOP1C0_SCRIPT_BYTES))
    return rows


def audit_fixed(include_loop1c0_copy: bool) -> List[Dict[str, Any]]:
    rows = [fixed_fact(path, expected_hash, expected_bytes) for path, expected_hash, expected_bytes in known_fixed_files(include_loop1c0_copy)]
    if not all(row["pass"] for row in rows):
        raise GateError("FIXED_INPUT_DRIFT", "one or more fixed 1C1 inputs drifted", {"rows": rows})
    return rows


def component_path(component: Any) -> str:
    return posix(Path(str(base.value(component, "GetPathName"))))


def normalize(vector: Sequence[float]) -> Tuple[float, float, float]:
    if len(vector) != 3:
        raise GateError("VECTOR_SHAPE_FAIL", "vector must have three values", {"vector": list(vector)})
    norm = math.sqrt(sum(float(value) ** 2 for value in vector))
    if not math.isfinite(norm) or norm <= 0.0:
        raise GateError("VECTOR_NORM_FAIL", "vector norm is not positive", {"vector": list(vector)})
    return tuple(float(value) / norm for value in vector)


def dot(first: Sequence[float], second: Sequence[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def vector_sub(first: Sequence[float], second: Sequence[float]) -> List[float]:
    return [float(a) - float(b) for a, b in zip(first, second)]


def vector_norm(values: Sequence[float]) -> float:
    return math.sqrt(sum(float(value) ** 2 for value in values))


def extract_part_facts(result: Dict[str, Any]) -> Dict[str, Any]:
    mode = str(result.get("mode", ""))
    if mode == "CREATED":
        facts = result.get("cold_reopen", {}).get("facts")
    elif mode == "RESUMED":
        facts = result.get("cold_reopen_now", {}).get("facts")
    else:
        facts = None
    if not isinstance(facts, dict):
        raise GateError("LOOP1C0_PART_FACTS_FAIL", "Loop1C0 result lacks cold-open facts", {"mode": mode})
    return facts


def audit_loop1c0_inputs(required: bool) -> Dict[str, Any]:
    required_paths = [LOOP1C0_RECEIPT, LOOP1C0_SCRIPT_COPY, *LOOP1C0_CHECKPOINTS.values(), *(spec["path"] for spec in PARTS.values())]
    missing = [posix(path) for path in required_paths if not path.is_file()]
    if missing:
        result = {
            "ready": False,
            "missing": missing,
            "classification": "LOOP1C0_CORRECTED_PALM9_LEFT24_RIGHT24_INPUTS_PENDING",
        }
        if required:
            raise GateError("LOOP1C0_INPUTS_PENDING", "corrected Loop1C0 outputs are incomplete", result)
        return result
    if sha256(LOOP1C0_SCRIPT_COPY) != LOOP1C0_SCRIPT_SHA256 or LOOP1C0_SCRIPT_COPY.stat().st_size != LOOP1C0_SCRIPT_BYTES:
        raise GateError("LOOP1C0_R3_COPY_DRIFT", "immutable Loop1C0 R3 script copy drifted", file_fact(LOOP1C0_SCRIPT_COPY))
    receipt = load_json(LOOP1C0_RECEIPT)
    if receipt.get("schema") != "F3R2_V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT_V3_LINK6_LOCAL_FINGERPRINT":
        raise GateError("LOOP1C0_RECEIPT_SCHEMA_FAIL", "unexpected Loop1C0 receipt schema")
    if receipt.get("verdict") != "V5_LOOP1C0_57_PHYSICAL_BODIES_THREE_NATIVE_GRIPPER_PARTS_PASS_ASSEMBLY_HOLD":
        raise GateError("LOOP1C0_RECEIPT_VERDICT_FAIL", "Loop1C0 receipt is not the corrected three-part PASS")
    binding = receipt.get("binding", {})
    exclusion = receipt.get("aggregate_exclusion", {})
    conservation = receipt.get("conservation", {})
    frame_contract = receipt.get("frame_contracts", {}).get("GRIPPER", {})
    frame_bbox = frame_contract.get("source_bbox_mm")
    frame_witness = frame_contract.get("witness", {})
    if (
        binding.get("script_sha256") != LOOP1C0_SCRIPT_SHA256
        or int(binding.get("physical_body_count", -1)) != 57
        or binding.get("solid_body_gate_api") != "IBody2.GetType()==swSolidBody(0)"
        or exclusion.get("classification") != "AGGREGATE_WRAPPER_NOT_PHYSICAL_BODY"
        or exclusion.get("copy_authorized") is not False
        or conservation.get("pass") is not True
        or int(conservation.get("body_count", -1)) != 57
        or int(conservation.get("face_count", -1)) != 1798
        or frame_contract.get("source_frame") != "LINK6_LOCAL"
        or frame_contract.get("placement") != "LIVE_LINK6_TOTAL_TRANSFORM"
        or frame_contract.get("mapping_authority") != "SOURCE_SLDPRT_COLD_LINK6_LOCAL_EXACT_LABEL_PLUS_BREP_FINGERPRINT"
        or not isinstance(frame_bbox, list)
        or len(frame_bbox) != 6
        or not all(math.isfinite(float(value)) for value in frame_bbox)
        or any(float(frame_bbox[index + 3]) <= float(frame_bbox[index]) for index in range(3))
        or frame_witness.get("method") != "SOLIDWORKS_COLD_BREP_BBOX_AND_DATUM_WITNESS"
        or frame_witness.get("cold_reopen_pass") is not True
        or int(frame_witness.get("external_reference_count", -1)) != 0
        or frame_witness.get("full_top_world_coordinate_fields_used") is not False
    ):
        raise GateError("LOOP1C0_RECEIPT_BINDING_FAIL", "Loop1C0 corrected 57-body link-6-local binding is incomplete", {"binding": binding, "aggregate_exclusion": exclusion, "conservation": conservation, "frame_contract": frame_contract})

    group_for_role = {"PALM": "gripper_link", "LEFT": "gripper_left", "RIGHT": "gripper_right"}
    parts_result = receipt.get("parts")
    if not isinstance(parts_result, dict):
        raise GateError("LOOP1C0_PART_RESULT_FAIL", "Loop1C0 receipt parts result is not an object")
    audited: Dict[str, Any] = {}
    for role, spec in PARTS.items():
        checkpoint_path = LOOP1C0_CHECKPOINTS[role]
        checkpoint = load_json(checkpoint_path)
        if checkpoint.get("schema") != "F3R2_V5_LOOP1C0_PART_CHECKPOINT_V3_LINK6_LOCAL_FINGERPRINT" or checkpoint.get("verdict") != "V5_LOOP1C0_57_PHYSICAL_NATIVE_PART_CHECKPOINT_PASS":
            raise GateError("LOOP1C0_CHECKPOINT_SCHEMA_FAIL", "unexpected Loop1C0 checkpoint", {"role": role})
        cp_binding = checkpoint.get("binding", {})
        target = checkpoint.get("target", {})
        if cp_binding.get("script_sha256") != LOOP1C0_SCRIPT_SHA256 or cp_binding.get("solid_body_gate_api") != "IBody2.GetType()==swSolidBody(0)":
            raise GateError("LOOP1C0_CHECKPOINT_BINDING_FAIL", "Loop1C0 checkpoint is not bound to corrected R3", {"role": role, "binding": cp_binding})
        actual = file_fact(Path(spec["path"]))
        if target.get("path") != posix(Path(spec["path"])) or target.get("sha256") != actual["sha256"] or int(target.get("bytes", -1)) != actual["bytes"]:
            raise GateError("LOOP1C0_PART_HASH_FAIL", "Loop1C0 part does not match its checkpoint", {"role": role, "target": target, "actual": actual})
        group = group_for_role[role]
        if group not in parts_result or not isinstance(parts_result[group], dict):
            raise GateError("LOOP1C0_GROUP_RESULT_MISSING", "Loop1C0 receipt lacks a part group", {"group": group})
        facts = extract_part_facts(parts_result[group])
        if int(facts.get("body_count", -1)) != int(spec["count"]) or int(facts.get("external_reference_count", -1)) != 0 or int(facts.get("auxiliary_reference_count", -1)) != 0 or facts.get("three_d_interconnect_features"):
            raise GateError("LOOP1C0_PART_SEMANTIC_FAIL", "Loop1C0 part count/reference contract failed", {"role": role, "facts": facts})
        audited[role] = {"file": actual, "checkpoint": file_fact(checkpoint_path), "facts": facts}
    return {
        "ready": True,
        "receipt": file_fact(LOOP1C0_RECEIPT),
        "parts": audited,
        "physical_body_count": 57,
        "aggregate_wrapper": "AGGREGATE_WRAPPER_NOT_PHYSICAL_BODY",
        "frame_contract": frame_contract,
    }


def checkpoint_binding(input_audit: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "script_sha256": sha256(Path(__file__).resolve()),
        "base_helper_sha256": BASE_HELPER_SHA256,
        "loop1c0_script_sha256": LOOP1C0_SCRIPT_SHA256,
        "loop1c0_receipt_sha256": input_audit["receipt"]["sha256"],
        "input_part_sha256": {role: row["file"]["sha256"] for role, row in input_audit["parts"].items()},
        "m3r_binding_sha256": M3R_BINDING_SHA256,
        "state_register_sha256": STATE_REGISTER_SHA256,
        "travel_clearance_sha256": TRAVEL_CLEARANCE_SHA256,
        "mate_contract": "2_GUIDE_COINCIDENT_PLUS_1_ADVANCED_LIMIT_DISTANCE_TYPE5_PER_FINGER",
        "limit_min_mm": 0.0,
        "limit_max_mm": 71.5,
        "mate_type_23_used": False,
        "holding_authority": "CLOSED_GEOMETRY_ALIAS_NO_FORCE_CLAIM",
    }


def target_checkpoint_state(input_audit: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    target_exists = TARGET.is_file()
    checkpoint_exists = CHECKPOINT.is_file()
    if target_exists != checkpoint_exists:
        state = "HOLD_ORPHAN_TARGET_OR_CHECKPOINT"
    elif not target_exists:
        state = "PENDING"
    elif input_audit is None or not input_audit.get("ready"):
        state = "HOLD_INPUT_AUDIT_UNAVAILABLE"
    else:
        checkpoint = load_json(CHECKPOINT)
        target = checkpoint.get("target", {})
        expected_binding = checkpoint_binding(input_audit)
        if (
            checkpoint.get("schema") != "F3R2_V5_LOOP1C1_GRIPPER_ASSEMBLY_CHECKPOINT_V1"
            or checkpoint.get("verdict") != "V5_LOOP1C1_NATIVE_GRIPPER_ASSEMBLY_CHECKPOINT_PASS"
            or checkpoint.get("binding") != expected_binding
            or target.get("path") != posix(TARGET)
            or target.get("sha256") != sha256(TARGET)
            or int(target.get("bytes", -1)) != TARGET.stat().st_size
        ):
            state = "HOLD_CHECKPOINT_DRIFT"
        else:
            state = "RESUME_REQUIRES_COLD_REOPEN"
    return {
        "state": state,
        "target": file_fact(TARGET),
        "checkpoint": file_fact(CHECKPOINT),
    }


def static_audit() -> Dict[str, Any]:
    script = Path(__file__).resolve()
    fixed_without_r3 = audit_fixed(False)
    input_audit = audit_loop1c0_inputs(False)
    if input_audit.get("ready"):
        fixed = audit_fixed(True)
        state = target_checkpoint_state(input_audit)
    else:
        fixed = fixed_without_r3
        state = target_checkpoint_state(None)
    script_copy_state = (
        "ABSENT_PENDING"
        if not SCRIPT_COPY.exists()
        else "EXACT_RESUME"
        if SCRIPT_COPY.is_file() and SCRIPT_COPY.stat().st_size == script.stat().st_size and sha256(SCRIPT_COPY) == sha256(script)
        else "HOLD_SCRIPT_COPY_DRIFT"
    )
    receipt_state = "ABSENT_PENDING" if not FINAL_RECEIPT.exists() else "EXISTS"
    manifest_state = "ABSENT_PENDING" if not FINAL_MANIFEST.exists() else "EXISTS"
    holds: List[Dict[str, Any]] = []
    if not input_audit.get("ready"):
        holds.append({"state": "LOOP1C0_INPUTS_PENDING", "detail": input_audit})
    if state["state"] not in {"PENDING", "RESUME_REQUIRES_COLD_REOPEN"}:
        holds.append({"state": state["state"], "detail": state})
    if script_copy_state == "HOLD_SCRIPT_COPY_DRIFT":
        holds.append({"state": script_copy_state, "path": posix(SCRIPT_COPY)})
    if (FINAL_RECEIPT.exists() or FINAL_MANIFEST.exists()) and state["state"] != "RESUME_REQUIRES_COLD_REOPEN":
        holds.append({"state": "FINAL_ARTIFACT_WITHOUT_RESUMABLE_CHECKPOINT"})
    manifest_resume_ok = manifest_state == "ABSENT_PENDING"
    if manifest_state == "EXISTS" and input_audit.get("ready") and state["state"] == "RESUME_REQUIRES_COLD_REOPEN":
        manifest_resume_ok = FINAL_MANIFEST.read_text(encoding="utf-8") == manifest_text()
        if not manifest_resume_ok:
            holds.append({"state": "HOLD_FINAL_MANIFEST_DRIFT", "path": posix(FINAL_MANIFEST)})
    execution_authorized = not holds and receipt_state == "ABSENT_PENDING" and manifest_resume_ok
    if FINAL_RECEIPT.is_file() and FINAL_MANIFEST.is_file() and state["state"] == "RESUME_REQUIRES_COLD_REOPEN":
        receipt = load_json(FINAL_RECEIPT)
        complete = receipt.get("verdict") == "V5_LOOP1C1_NATIVE_GRIPPER_ASSEMBLY_PASS_MECHANICAL_MAINLINE_FREEZE_READY"
    else:
        complete = False
    return {
        "schema": "F3R2_V5_LOOP1C1_GRIPPER_ASSEMBLY_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "script": file_fact(script),
        "fixed_inputs": fixed,
        "loop1c0_inputs": input_audit,
        "target_checkpoint_state": state,
        "script_copy_state": script_copy_state,
        "final_receipt_state": receipt_state,
        "final_manifest_state": manifest_state,
        "execution_authorized": execution_authorized,
        "complete": complete,
        "holds": holds,
        "mate_type_23_used": False,
        "verdict": (
            "V5_LOOP1C1_ALREADY_COMPLETE"
            if complete
            else "V5_LOOP1C1_STATIC_AUDIT_PASS_EXECUTION_AUTHORIZED"
            if execution_authorized
            else "V5_LOOP1C1_SCRIPT_READY_LOOP1C0_INPUTS_PENDING"
            if not input_audit.get("ready") and not any(row["state"].startswith("HOLD_") for row in holds)
            else "V5_LOOP1C1_STATIC_HOLD"
        ),
    }


def unpack_document(result: Any, label: str) -> Tuple[Any, int, int]:
    if not isinstance(result, tuple) or len(result) < 3:
        raise GateError(f"{label}_RETURN_SHAPE_FAIL", f"{label} did not return model/errors/warnings", {"returned": repr(result)})
    model, outs = base.unpack(result)
    if len(outs) < 2:
        raise GateError(f"{label}_OUT_COUNT_FAIL", f"{label} lacks errors/warnings")
    return model, int(outs[0]), int(outs[1])


def activate(sw: Any, title: str) -> Any:
    returned = sw.ActivateDoc3(title, True, 0, 0)
    model, outs = base.unpack(returned)
    error = int(outs[0]) if outs else 0
    if model is None or error != 0:
        raise GateError("ACTIVATE_DOCUMENT_FAIL", "cannot activate owned assembly", {"title": title, "error": error})
    return model


def transform_data(translation_m: Sequence[float]) -> List[float]:
    if len(translation_m) != 3:
        raise GateError("TRANSFORM_TRANSLATION_SHAPE_FAIL", "translation must have three values")
    return [
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0.0, 0.0, 1.0,
        float(translation_m[0]), float(translation_m[1]), float(translation_m[2]),
        1.0, 0.0, 0.0, 0.0,
    ]


def expected_translation_m(role: str, travel_mm: float) -> Tuple[float, float, float]:
    sign = 0.0 if role == "PALM" else 1.0 if role == "LEFT" else -1.0
    return tuple(sign * float(travel_mm) * value / 1000.0 for value in JAW_AXIS)


def insert_component(
    sw: Any,
    model: Any,
    assembly: Any,
    role: str,
    path: Path,
    fixed: bool,
    translation_m: Sequence[float],
    types: Any,
    pythoncom: Any,
) -> Any:
    raw_part = part = None
    part_title = ""
    assembly_title = str(base.value(model, "GetTitle"))
    baseline_count = int(base.value(sw, "GetDocumentCount"))
    try:
        raw_part, errors, warnings = unpack_document(sw.OpenDoc6(str(path), SW_DOC_PART, SW_OPEN_SILENT_READONLY, "", 0, 0), "OPEN_COMPONENT")
        if raw_part is None:
            raise GateError("OPEN_COMPONENT_NULL", "component preload returned null", {"role": role, "path": posix(path)})
        part = base.wrap(raw_part, "IModelDoc2", types, pythoncom)
        part_title = str(base.value(part, "GetTitle"))
        if errors != 0 or warnings != 0 or not bool(base.value(part, "IsOpenedReadOnly")):
            raise GateError("OPEN_COMPONENT_FAIL", "component did not preload cleanly read-only", {"role": role, "errors": errors, "warnings": warnings})
        activate(sw, assembly_title)
        raw_component = assembly.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw_component is None:
            raise GateError("ADD_COMPONENT_FAIL", "AddComponent5 returned null", {"role": role, "path": posix(path)})
        component = base.wrap(raw_component, "IComponent2", types, pythoncom)
        math_utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
        from win32com.client import VARIANT

        typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, transform_data(translation_m))
        transform = math_utility.CreateTransform(typed)
        if transform is None or not bool(component.SetTransformAndSolve3(transform, True)):
            raise GateError("COMPONENT_TRANSFORM_SOLVE_FAIL", "cannot establish initial component transform", {"role": role})
        if not bool(model.EditRebuild3()):
            raise GateError("COMPONENT_REBUILD_FAIL", "rebuild failed after component insertion", {"role": role})
        readback = [float(value) for value in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
        expected = transform_data(translation_m)
        if len(readback) != 16 or any(abs(a - b) > 2.0e-7 for a, b in zip(readback, expected)):
            raise GateError("COMPONENT_TRANSFORM_READBACK_FAIL", "initial component transform drifted", {"role": role, "actual": readback, "expected": expected})
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise GateError("COMPONENT_SELECT_FAIL", "cannot select component for fixed-state change", {"role": role})
        if fixed:
            assembly.FixComponent()
        else:
            assembly.UnfixComponent()
        model.ClearSelection2(True)
        if bool(base.value(component, "IsFixed")) != bool(fixed):
            raise GateError("COMPONENT_FIXED_STATE_FAIL", "component fixed state did not read back", {"role": role, "expected": fixed})
        return component
    finally:
        if part_title:
            try:
                sw.CloseDoc(part_title)
            except Exception:
                pass
        actual_count = int(base.value(sw, "GetDocumentCount"))
        activate(sw, assembly_title)
        if actual_count != baseline_count + 1:
            raise GateError("COMPONENT_DEPENDENCY_GRAPH_FAIL", "component insertion left an unexpected document graph", {"role": role, "baseline_count": baseline_count, "actual_count": actual_count})


def close_all_owned(sw: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _pass in range(4):
        documents = base.as_list(base.value(sw, "GetDocuments"))
        if not documents:
            break
        titles: List[str] = []
        for raw in documents:
            try:
                titles.append(str(base.value(raw, "GetTitle")))
            except Exception:
                continue
        for title in reversed(list(dict.fromkeys(titles))):
            try:
                sw.CloseDoc(title)
                rows.append({"title": title, "closed": True})
            except Exception as exc:
                rows.append({"title": title, "closed": False, "exception": repr(exc)})
    count = int(base.value(sw, "GetDocumentCount"))
    if count != 0:
        raise GateError("OWNED_DOCUMENT_CLEANUP_FAIL", "documents remain in the initially-empty owned session", {"document_count": count, "attempts": rows})
    return rows


def component_bodies(component: Any, expected_count: int, types: Any, pythoncom: Any) -> List[Any]:
    raw_bodies = base.as_list(component.GetBodies2(SW_BODY_SOLID))
    if len(raw_bodies) != expected_count:
        raise GateError("COMPONENT_BODY_COUNT_FAIL", "component body count is wrong", {"component": component_path(component), "actual": len(raw_bodies), "expected": expected_count})
    bodies: List[Any] = []
    names: set[str] = set()
    for raw in raw_bodies:
        body = base.wrap(raw, "IBody2", types, pythoncom)
        body_type = int(base.value(body, "GetType"))
        name = str(base.value(body, "Name"))
        if body_type != SW_BODY_SOLID or not name or name in names:
            raise GateError("COMPONENT_BODY_SEMANTIC_FAIL", "component exposes non-solid, unnamed, or duplicate bodies", {"body_type": body_type, "name": name})
        names.add(name)
        bodies.append(body)
    return bodies


def body_for_source(component: Any, role: str, source: str, types: Any, pythoncom: Any) -> Any:
    expected_count = int(PARTS[role]["count"])
    suffix = f"__{source}"
    candidates = [body for body in component_bodies(component, expected_count, types, pythoncom) if str(base.value(body, "Name")).endswith(suffix)]
    if len(candidates) != 1:
        raise GateError("SEMANTIC_BODY_NOT_UNIQUE", "source label did not identify one target body", {"role": role, "source": source, "candidate_count": len(candidates)})
    return candidates[0]


def persist_bytes(extension: Any, obj: Any) -> bytes:
    raw = extension.GetPersistReference3(obj)
    if raw is None:
        raise GateError("PERSIST_REFERENCE_NULL", "GetPersistReference3 returned null")
    if isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
    else:
        data = bytes(int(value) & 0xFF for value in base.as_list(raw))
    if not data:
        raise GateError("PERSIST_REFERENCE_EMPTY", "persistent reference is empty")
    return data


def persist_record(extension: Any, obj: Any) -> Dict[str, Any]:
    data = persist_bytes(extension, obj)
    reported_count = int(extension.GetPersistReferenceCount3(obj))
    if reported_count != len(data):
        raise GateError("PERSIST_REFERENCE_COUNT_FAIL", "GetPersistReferenceCount3 disagrees with byte array", {"reported_count": reported_count, "actual_count": len(data)})
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "base64": base64.b64encode(data).decode("ascii"),
    }


def resolve_persist_record(extension: Any, record: Dict[str, Any], pythoncom: Any) -> Dict[str, Any]:
    data = base64.b64decode(str(record["base64"]).encode("ascii"), validate=True)
    from win32com.client import VARIANT

    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, list(data))
    returned = extension.GetObjectByPersistReference3(typed, 0)
    obj, outs = base.unpack(returned)
    error = int(outs[0]) if outs else 0
    if obj is None or error != 0:
        raise GateError("PERSIST_REFERENCE_RESOLVE_FAIL", "persistent reference did not resolve", {"error": error, "record": record})
    roundtrip = persist_bytes(extension, obj)
    roundtrip_hash = hashlib.sha256(roundtrip).hexdigest().upper()
    if roundtrip_hash != record["sha256"]:
        raise GateError("PERSIST_REFERENCE_ROUNDTRIP_FAIL", "resolved persistent reference changed identity", {"expected": record["sha256"], "actual": roundtrip_hash})
    return {"error": error, "roundtrip_sha256": roundtrip_hash, "pass": True}


def guide_face(model: Any, component: Any, role: str, guide: str, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    contract = GUIDE_CONTRACTS[guide]
    role_contract = contract[role]
    body = body_for_source(component, role, str(role_contract["source"]), types, pythoncom)
    expected_normal = normalize(contract["normal"])
    expected_offset = float(contract["offset_mm"])
    expected_area = float(role_contract["area_mm2"])
    candidates: List[Tuple[Any, Dict[str, Any]]] = []
    rejected: List[Dict[str, Any]] = []
    for raw_face in base.as_list(base.value(body, "GetFaces")):
        face = base.wrap(raw_face, "IFace2", types, pythoncom)
        surface = base.wrap(base.value(face, "GetSurface"), "ISurface", types, pythoncom)
        if not bool(base.value(surface, "IsPlane")):
            continue
        params = [float(value) for value in base.as_list(base.value(surface, "PlaneParams"))]
        if len(params) < 6:
            continue
        actual_normal = normalize(params[:3])
        orientation = 1.0 if dot(actual_normal, expected_normal) >= 0.0 else -1.0
        canonical_normal = tuple(orientation * value for value in actual_normal)
        point_mm = [value * 1000.0 for value in params[3:6]]
        offset_mm = dot(canonical_normal, point_mm)
        area_mm2 = float(base.value(face, "GetArea")) * 1.0e6
        normal_error = vector_norm(vector_sub(canonical_normal, expected_normal))
        fact = {
            "normal": list(actual_normal),
            "canonical_normal": list(canonical_normal),
            "normal_error": normal_error,
            "point_mm": point_mm,
            "offset_mm": offset_mm,
            "offset_error_mm": abs(offset_mm - expected_offset),
            "area_mm2": area_mm2,
            "area_error_mm2": abs(area_mm2 - expected_area),
        }
        if fact["normal_error"] <= FACE_NORMAL_TOL and fact["offset_error_mm"] <= FACE_OFFSET_TOL_MM and fact["area_error_mm2"] <= FACE_AREA_TOL_MM2:
            candidates.append((face, fact))
        elif fact["normal_error"] <= 0.02:
            rejected.append(fact)
    if len(candidates) != 1:
        raise GateError("GUIDE_FACE_SIGNATURE_NOT_UNIQUE", "normal/plane/area/source-body signature did not select exactly one guide face", {"role": role, "guide": guide, "source": role_contract["source"], "candidate_count": len(candidates), "nearby": rejected})
    face, fact = candidates[0]
    entity = base.wrap(face, "IEntity", types, pythoncom)
    owner_raw = base.value(entity, "IGetComponent2")
    if owner_raw is not None:
        owner = base.wrap(owner_raw, "IComponent2", types, pythoncom)
        if component_path(owner) != component_path(component):
            raise GateError("GUIDE_FACE_COMPONENT_CONTEXT_FAIL", "selected guide face belongs to a different component", {"role": role, "guide": guide})
    extension = model.Extension
    fact.update({
        "role": role,
        "guide": guide,
        "semantic_body_name": str(base.value(body, "Name")),
        "source": role_contract["source"],
        "component_path": component_path(component),
        "persist_reference": persist_record(extension, entity),
        "selection_rule": "SOURCE_BODY_SUFFIX_PLUS_PLANE_NORMAL_OFFSET_AREA_NO_ENUMERATION_FALLBACK",
    })
    return entity, fact


def selection_manager(model: Any, types: Any, pythoncom: Any) -> Any:
    for name in ("ISelectionManager", "SelectionManager"):
        try:
            raw = getattr(model, name)
            if raw is not None:
                return base.wrap(raw, "ISelectionMgr", types, pythoncom)
        except Exception:
            continue
    raise GateError("SELECTION_MANAGER_FAIL", "cannot obtain ISelectionMgr")


def mate_features(model: Any, types: Any, pythoncom: Any) -> List[Any]:
    rows: List[Any] = []
    feature = base.value(model, "FirstFeature")
    while feature is not None:
        typed = base.wrap(feature, "IFeature", types, pythoncom)
        if str(base.value(typed, "GetTypeName2")) == "MateGroup":
            sub = base.value(typed, "GetFirstSubFeature")
            while sub is not None:
                sf = base.wrap(sub, "IFeature", types, pythoncom)
                rows.append(sf)
                sub = base.value(sf, "GetNextSubFeature")
        feature = base.value(typed, "GetNextFeature")
    return rows


def added_mate_feature(before_names: Sequence[str], model: Any, expected_name: str, types: Any, pythoncom: Any) -> Any:
    after = mate_features(model, types, pythoncom)
    additions = [feature for feature in after if str(base.value(feature, "Name")) not in set(before_names)]
    if len(after) != len(before_names) + 1 or len(additions) != 1:
        raise GateError("MATE_FEATURE_DELTA_FAIL", "AddMate3 did not create exactly one mate feature", {"before": list(before_names), "after": [str(base.value(feature, "Name")) for feature in after]})
    feature = additions[0]
    feature.Name = expected_name
    if str(base.value(feature, "Name")) != expected_name:
        raise GateError("MATE_RENAME_FAIL", "mate feature name did not read back", {"expected": expected_name})
    return feature


def add_face_mate(
    model: Any,
    assembly: Any,
    first: Any,
    second: Any,
    alignment: int,
    name: str,
    types: Any,
    pythoncom: Any,
) -> Any:
    before = [str(base.value(feature, "Name")) for feature in mate_features(model, types, pythoncom)]
    model.ClearSelection2(True)
    manager = selection_manager(model, types, pythoncom)
    data = base.wrap(manager.CreateSelectData(), "ISelectData", types, pythoncom)
    data.Mark = 1
    if not bool(first.Select4(False, data)) or not bool(second.Select4(True, data)):
        raise GateError("GUIDE_FACE_SELECTION_FAIL", "cannot select the two guide faces", {"mate": name})
    selected = int(manager.GetSelectedObjectCount2(1))
    returned = assembly.AddMate3(SW_MATE_COINCIDENT, alignment, False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
    mate_raw, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    if mate_raw is None or error != SW_ADD_MATE_NO_ERROR or selected != 2:
        raise GateError("GUIDE_MATE_ADD_FAIL", "coincident guide AddMate3 failed", {"mate": name, "error": error, "selected": selected, "alignment": alignment})
    feature = added_mate_feature(before, model, name, types, pythoncom)
    mate = base.wrap(mate_raw, "IMate2", types, pythoncom)
    if int(base.value(mate, "Type")) != SW_MATE_COINCIDENT:
        raise GateError("GUIDE_MATE_TYPE_FAIL", "guide mate did not read as coincident", {"mate": name, "actual": int(base.value(mate, "Type"))})
    return feature


def component_origin(component: Any, types: Any, pythoncom: Any) -> Any:
    candidates: List[Any] = []
    raw = base.value(component, "FirstFeature")
    while raw is not None:
        feature = base.wrap(raw, "IFeature", types, pythoncom)
        if str(base.value(feature, "GetTypeName2")) == "OriginProfileFeature":
            candidates.append(feature)
        raw = base.value(feature, "GetNextFeature")
    if len(candidates) != 1:
        raise GateError("COMPONENT_ORIGIN_NOT_UNIQUE", "component does not expose exactly one OriginProfileFeature", {"component": component_path(component), "candidate_count": len(candidates)})
    return candidates[0]


def distance_mate_data(feature: Any, types: Any, pythoncom: Any) -> Any:
    raw = base.value(feature, "GetDefinition")
    if raw is None:
        raise GateError("DISTANCE_MATE_DEFINITION_NULL", "distance mate GetDefinition returned null", {"feature": str(base.value(feature, "Name"))})
    return base.wrap(raw, "IDistanceMateFeatureData", types, pythoncom)


def distance_mate_object(feature: Any, types: Any, pythoncom: Any) -> Any:
    raw = base.value(feature, "GetSpecificFeature2")
    if raw is None:
        raise GateError("MATE_SPECIFIC_FEATURE_NULL", "mate feature lacks IMate2", {"feature": str(base.value(feature, "Name"))})
    return base.wrap(raw, "IMate2", types, pythoncom)


def add_advanced_limit_distance(
    model: Any,
    assembly: Any,
    palm: Any,
    finger: Any,
    name: str,
    types: Any,
    pythoncom: Any,
) -> Any:
    before = [str(base.value(feature, "Name")) for feature in mate_features(model, types, pythoncom)]
    palm_origin = component_origin(palm, types, pythoncom)
    finger_origin = component_origin(finger, types, pythoncom)
    model.ClearSelection2(True)
    if not bool(palm_origin.Select2(False, 1)) or not bool(finger_origin.Select2(True, 1)):
        raise GateError("LIMIT_ENDPOINT_SELECTION_FAIL", "cannot select component origins for travel limit", {"mate": name})
    manager = selection_manager(model, types, pythoncom)
    selected = int(manager.GetSelectedObjectCount2(1))
    maximum_m = STATES["OPEN"]["travel_mm"] / 1000.0
    returned = assembly.AddMate3(
        SW_MATE_DISTANCE,
        SW_ALIGN_ALIGNED,
        False,
        maximum_m,
        maximum_m,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        False,
        0,
    )
    mate_raw, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    if mate_raw is None or error != SW_ADD_MATE_NO_ERROR or selected != 2:
        raise GateError("LIMIT_MATE_ADD_FAIL", "Type-5 distance AddMate3 failed", {"mate": name, "error": error, "selected": selected})
    feature = added_mate_feature(before, model, name, types, pythoncom)
    data = distance_mate_data(feature, types, pythoncom)
    data.IsAdvancedMate = True
    data.MinimumDistance = 0.0
    data.MaximumDistance = maximum_m
    data.Distance = maximum_m
    data.MateAlignment = SW_ALIGN_ALIGNED
    if not bool(feature.ModifyDefinition(data, model, None)):
        raise GateError("LIMIT_MATE_MODIFY_FAIL", "cannot establish advanced min/max distance data", {"mate": name})
    if not bool(model.ForceRebuild3(True)):
        raise GateError("LIMIT_MATE_REBUILD_FAIL", "rebuild failed after advanced limit definition", {"mate": name})
    facts = advanced_limit_facts(feature, types, pythoncom)
    if not facts["pass"]:
        raise GateError("LIMIT_MATE_READBACK_FAIL", "advanced limit distance readback failed", facts)
    return feature


def advanced_limit_facts(feature: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    data = distance_mate_data(feature, types, pythoncom)
    mate = distance_mate_object(feature, types, pythoncom)
    facts = {
        "feature_name": str(base.value(feature, "Name")),
        "mate_type": int(base.value(mate, "Type")),
        "is_advanced": bool(base.value(data, "IsAdvancedMate")),
        "distance_mm": float(base.value(data, "Distance")) * 1000.0,
        "minimum_distance_mm": float(base.value(data, "MinimumDistance")) * 1000.0,
        "maximum_distance_mm": float(base.value(data, "MaximumDistance")) * 1000.0,
        "mate_alignment": int(base.value(data, "MateAlignment")),
        "minimum_variation_mm": float(base.value(mate, "MinimumVariation")) * 1000.0,
        "maximum_variation_mm": float(base.value(mate, "MaximumVariation")) * 1000.0,
    }
    facts["pass"] = (
        facts["mate_type"] == SW_MATE_DISTANCE
        and facts["is_advanced"]
        and abs(facts["minimum_distance_mm"] - 0.0) <= LIMIT_TOL_MM
        and abs(facts["maximum_distance_mm"] - 71.5) <= LIMIT_TOL_MM
    )
    return facts


def mate_dimension(feature: Any, types: Any, pythoncom: Any) -> Any:
    mate = distance_mate_object(feature, types, pythoncom)
    raw_display = mate.DisplayDimension2(0)
    if raw_display is None:
        raise GateError("MATE_DISPLAY_DIMENSION_NULL", "distance mate lacks DisplayDimension2(0)", {"feature": str(base.value(feature, "Name"))})
    display = base.wrap(raw_display, "IDisplayDimension", types, pythoncom)
    raw_dimension = display.GetDimension2(0)
    if raw_dimension is None:
        raise GateError("MATE_DIMENSION_NULL", "display dimension lacks IDimension", {"feature": str(base.value(feature, "Name"))})
    return base.wrap(raw_dimension, "IDimension", types, pythoncom)


def configuration_names(model: Any) -> List[str]:
    return sorted(str(name) for name in base.as_list(base.value(model, "GetConfigurationNames")))


def establish_configurations(model: Any, limit_features: Sequence[Any], types: Any, pythoncom: Any) -> Dict[str, Any]:
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    before = configuration_names(model)
    if len(before) != 1:
        raise GateError("TEMPLATE_CONFIGURATION_COUNT_FAIL", "assembly template must begin with exactly one configuration", {"configurations": before})
    active.Name = "OPEN"
    if str(base.value(base.value(manager, "ActiveConfiguration"), "Name")) != "OPEN":
        raise GateError("OPEN_CONFIGURATION_RENAME_FAIL", "default configuration did not rename to OPEN")
    for name in ("PREGRASP", "CLOSED", "HOLDING"):
        created = manager.AddConfiguration2(name, f"F3R2 B601 gripper {name}", "", 0, "", "", True)
        if created is None:
            raise GateError("CONFIGURATION_CREATE_FAIL", "AddConfiguration2 returned null", {"configuration": name})
    names = configuration_names(model)
    if names != sorted(STATES):
        raise GateError("CONFIGURATION_SET_FAIL", "native configuration set is not exact", {"actual": names, "expected": sorted(STATES)})
    drive: List[Dict[str, Any]] = []
    for feature in limit_features:
        dimension = mate_dimension(feature, types, pythoncom)
        for name, spec in STATES.items():
            requested_m = float(spec["travel_mm"]) / 1000.0
            status = int(dimension.SetSystemValue3(requested_m, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [name]))
            values = [float(value) for value in base.as_list(dimension.GetSystemValue3(SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [name]))]
            if status != SW_SET_VALUE_SUCCESS or len(values) != 1 or abs(values[0] - requested_m) > 2.0e-6:
                raise GateError("CONFIGURATION_DIMENSION_DRIVE_FAIL", "configuration-specific distance value failed", {"feature": str(base.value(feature, "Name")), "configuration": name, "status": status, "values": values, "requested_m": requested_m})
            drive.append({"feature": str(base.value(feature, "Name")), "configuration": name, "requested_mm": spec["travel_mm"], "status": status, "readback_mm": values[0] * 1000.0})
    return {"configurations": names, "dimension_drive": drive}


def mate_ledger(model: Any, types: Any, pythoncom: Any, resolve_refs: bool) -> List[Dict[str, Any]]:
    extension = model.Extension
    rows: List[Dict[str, Any]] = []
    for feature in mate_features(model, types, pythoncom):
        mate = distance_mate_object(feature, types, pythoncom)
        count = int(base.value(mate, "GetMateEntityCount"))
        entities: List[Dict[str, Any]] = []
        for index in range(count):
            entity = base.wrap(mate.MateEntity(index), "IMateEntity2", types, pythoncom)
            raw_component = base.value(entity, "ReferenceComponent")
            raw_reference = base.value(entity, "Reference")
            if raw_component is None or raw_reference is None:
                raise GateError("MATE_ENTITY_REFERENCE_MISSING", "mate entity lacks component or reference", {"feature": str(base.value(feature, "Name")), "index": index})
            component = base.wrap(raw_component, "IComponent2", types, pythoncom)
            reference = persist_record(extension, raw_reference)
            entity_row = {
                "index": index,
                "component_path": component_path(component),
                "reference_type": int(base.value(entity, "ReferenceType2")),
                "persist_reference": reference,
            }
            if resolve_refs:
                entity_row["persist_resolution"] = resolve_persist_record(extension, reference, pythoncom)
            entities.append(entity_row)
        mate_type = int(base.value(mate, "Type"))
        row: Dict[str, Any] = {
            "feature_name": str(base.value(feature, "Name")),
            "feature_error_code": int(base.value(feature, "GetErrorCode")),
            "suppressed": bool(base.value(feature, "IsSuppressed")),
            "mate_type": mate_type,
            "alignment": int(base.value(mate, "Alignment")),
            "flipped": bool(base.value(mate, "Flipped")),
            "entity_count": count,
            "component_paths": sorted(entity["component_path"] for entity in entities),
            "entities": entities,
        }
        error2_returned = feature.GetErrorCode2(False)
        error2, error2_outs = base.unpack(error2_returned)
        warning2 = bool(error2_outs[0]) if error2_outs else False
        row["feature_error_code2"] = int(error2)
        row["feature_error_code2_is_warning"] = warning2
        if mate_type == SW_MATE_DISTANCE:
            row["advanced_limit"] = advanced_limit_facts(feature, types, pythoncom)
        if row["feature_error_code"] != 0 or row["feature_error_code2"] != 0 or row["feature_error_code2_is_warning"] or row["suppressed"] or count != 2:
            raise GateError("MATE_STATUS_FAIL", "mate is errored, suppressed, or lacks two endpoints", row)
        rows.append(row)
    rows.sort(key=lambda row: row["feature_name"])
    return rows


def ledger_signature(ledger: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    signature: List[Dict[str, Any]] = []
    for row in ledger:
        item: Dict[str, Any] = {
            "feature_name": row["feature_name"],
            "mate_type": int(row["mate_type"]),
            "alignment": int(row["alignment"]),
            "flipped": bool(row["flipped"]),
            "component_paths": sorted(row["component_paths"]),
            "reference_types": sorted(int(entity["reference_type"]) for entity in row["entities"]),
            "persist_reference_sha256": sorted(entity["persist_reference"]["sha256"] for entity in row["entities"]),
        }
        if "advanced_limit" in row:
            limit = row["advanced_limit"]
            item["advanced_limit"] = {
                "mate_type": int(limit["mate_type"]),
                "is_advanced": bool(limit["is_advanced"]),
                "minimum_distance_mm": round(float(limit["minimum_distance_mm"]), 6),
                "maximum_distance_mm": round(float(limit["maximum_distance_mm"]), 6),
            }
        signature.append(item)
    return sorted(signature, key=lambda row: row["feature_name"])


def validate_mate_contract(ledger: Sequence[Dict[str, Any]]) -> None:
    expected_names = sorted(MATE_NAMES.values())
    actual_names = sorted(str(row["feature_name"]) for row in ledger)
    if actual_names != expected_names or len(ledger) != 6:
        raise GateError("MATE_NAME_SET_FAIL", "assembly does not contain the exact six controlled mates", {"actual": actual_names, "expected": expected_names})
    paths = {role: posix(Path(spec["path"])) for role, spec in PARTS.items()}
    for row in ledger:
        name = str(row["feature_name"])
        side = "LEFT" if name.startswith("MATE_L_") else "RIGHT" if name.startswith("MATE_R_") else ""
        if not side:
            raise GateError("MATE_SIDE_NAME_FAIL", "mate name does not encode a controlled side", row)
        expected_pair = sorted((paths["PALM"], paths[side]))
        if sorted(row["component_paths"]) != expected_pair:
            raise GateError("MATE_ENDPOINT_PATH_FAIL", "mate endpoints are not the exact palm/finger pair", {"row": row, "expected_pair": expected_pair})
        if name.endswith("ADVANCED"):
            if int(row["mate_type"]) != SW_MATE_DISTANCE or not row.get("advanced_limit", {}).get("pass"):
                raise GateError("ADVANCED_LIMIT_CONTRACT_FAIL", "travel mate is not an advanced Type-5 0..71.5 mm limit", row)
        elif int(row["mate_type"]) != SW_MATE_COINCIDENT:
            raise GateError("GUIDE_MATE_CONTRACT_FAIL", "guide mate is not coincident", row)
        if int(row["mate_type"]) == SW_MATE_SLIDER:
            raise GateError("PROHIBITED_MATE_TYPE_23", "mate Type 23 is prohibited", row)
    coincident = sum(int(row["mate_type"]) == SW_MATE_COINCIDENT for row in ledger)
    distance = sum(int(row["mate_type"]) == SW_MATE_DISTANCE for row in ledger)
    if coincident != 4 or distance != 2:
        raise GateError("MATE_TYPE_CARDINALITY_FAIL", "expected four guide coincident and two distance mates", {"coincident": coincident, "distance": distance})


def assembly_components(model: Any, assembly: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_components = base.as_list(assembly.GetComponents(False))
    components = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in raw_components]
    by_path = {component_path(component): component for component in components}
    expected = {posix(Path(spec["path"])): role for role, spec in PARTS.items()}
    if len(components) != 3 or set(by_path) != set(expected):
        raise GateError("ASSEMBLY_COMPONENT_SET_FAIL", "assembly component set is not the exact three native parts", {"actual": sorted(by_path), "expected": sorted(expected), "count": len(components)})
    return {expected[path]: component for path, component in by_path.items()}


def component_transform_fact(component: Any, role: str, travel_mm: float) -> Dict[str, Any]:
    data = [float(value) for value in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
    if len(data) != 16:
        raise GateError("COMPONENT_TRANSFORM_SHAPE_FAIL", "component Transform2 is not 16 values", {"role": role, "transform": data})
    rotation_error = max(abs(data[index] - (1.0 if index in (0, 4, 8) else 0.0)) for index in range(9))
    translation_mm = [data[9 + index] * 1000.0 for index in range(3)]
    signed_mm = dot(translation_mm, JAW_AXIS)
    residual_mm = vector_norm(vector_sub(translation_mm, [signed_mm * value for value in JAW_AXIS]))
    expected_signed = 0.0 if role == "PALM" else travel_mm if role == "LEFT" else -travel_mm
    fact = {
        "role": role,
        "path": component_path(component),
        "fixed": bool(base.value(component, "IsFixed")),
        "suppression": int(base.value(component, "GetSuppression2")),
        "transform": data,
        "translation_mm": translation_mm,
        "signed_jaw_translation_mm": signed_mm,
        "jaw_axis_residual_mm": residual_mm,
        "expected_signed_jaw_translation_mm": expected_signed,
        "rotation_identity_max_error": rotation_error,
    }
    expected_fixed = bool(PARTS[role]["fixed"])
    fact["pass"] = (
        fact["fixed"] == expected_fixed
        and fact["suppression"] == SW_COMPONENT_RESOLVED
        and rotation_error <= TRANSFORM_ROTATION_TOL
        and abs(signed_mm - expected_signed) <= TRANSFORM_TRANSLATION_TOL_MM
        and residual_mm <= TRANSFORM_TRANSLATION_TOL_MM
    )
    if not fact["pass"]:
        raise GateError("COMPONENT_TRANSFORM_CONTRACT_FAIL", "component transform/fixed/suppression contract failed", fact)
    return fact


def closest_distance(model: Any, first: Any, second: Any) -> Tuple[float, List[float], List[float]]:
    returned = model.ClosestDistance(first, second)
    distance, outs = base.unpack(returned)
    if distance is None or not math.isfinite(float(distance)) or float(distance) < -1.0e-10:
        raise GateError("CLOSEST_DISTANCE_FAIL", "IModelDoc2.ClosestDistance returned an invalid value", {"returned": repr(returned)})
    point1 = [float(value) for value in base.as_list(outs[0])] if len(outs) > 0 else []
    point2 = [float(value) for value in base.as_list(outs[1])] if len(outs) > 1 else []
    if point1 and len(point1) != 3 or point2 and len(point2) != 3:
        raise GateError("CLOSEST_DISTANCE_POINT_SHAPE_FAIL", "ClosestDistance witness point shape is invalid", {"returned": repr(returned)})
    return float(distance), point1, point2


def minimum_component_distance(
    model: Any,
    first_component: Any,
    first_role: str,
    second_component: Any,
    second_role: str,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    first_bodies = component_bodies(first_component, int(PARTS[first_role]["count"]), types, pythoncom)
    second_bodies = component_bodies(second_component, int(PARTS[second_role]["count"]), types, pythoncom)
    best: Optional[Dict[str, Any]] = None
    for first in first_bodies:
        for second in second_bodies:
            distance_m, point1, point2 = closest_distance(model, first, second)
            row = {
                "distance_mm": distance_m * 1000.0,
                "first_body": str(base.value(first, "Name")),
                "second_body": str(base.value(second, "Name")),
                "point1_mm": [value * 1000.0 for value in point1],
                "point2_mm": [value * 1000.0 for value in point2],
            }
            if best is None or row["distance_mm"] < best["distance_mm"]:
                best = row
    if best is None:
        raise GateError("MINIMUM_DISTANCE_EMPTY", "no body pair was available for native minimum distance")
    best.update({"first_role": first_role, "second_role": second_role, "api": "IModelDoc2.ClosestDistance(IBody2,IBody2)"})
    return best


def interference_fact(assembly: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_manager = base.value(assembly, "InterferenceDetectionManager")
    if raw_manager is None:
        raise GateError("INTERFERENCE_MANAGER_NULL", "assembly lacks InterferenceDetectionManager")
    manager = base.wrap(raw_manager, "IInterferenceDetectionMgr", types, pythoncom)
    try:
        manager.TreatCoincidenceAsInterference = False
        manager.TreatSubAssembliesAsComponents = False
        manager.IncludeMultibodyPartInterferences = True
        manager.IgnoreHiddenBodies = False
        manager.ShowIgnoredInterferences = True
        raw_interferences = base.as_list(manager.GetInterferences())
        count = int(base.value(manager, "GetInterferenceCount"))
        rows: List[Dict[str, Any]] = []
        for raw in raw_interferences:
            interference = base.wrap(raw, "IInterference", types, pythoncom)
            components: List[str] = []
            for raw_component in base.as_list(base.value(interference, "Components")):
                component = base.wrap(raw_component, "IComponent2", types, pythoncom)
                components.append(component_path(component))
            rows.append({
                "component_paths": sorted(components),
                "volume_mm3": float(base.value(interference, "Volume")) * 1.0e9,
                "possible": bool(base.value(interference, "IsPossibleInterference")),
                "ignored": bool(base.value(interference, "Ignore")),
            })
        if count != len(rows):
            raise GateError("INTERFERENCE_COUNT_SHAPE_FAIL", "interference count and array disagree", {"count": count, "rows": rows})
        cross_component = [row for row in rows if len(set(row["component_paths"])) >= 2 and float(row["volume_mm3"]) > 0.0]
        internal = [row for row in rows if row not in cross_component]
        fact = {
            "raw_count": count,
            "cross_component_count": len(cross_component),
            "internal_or_zero_volume_count": len(internal),
            "interferences": rows,
            "treat_coincidence_as_interference": False,
            "include_multibody_part_internal_interferences": True,
            "cross_component_positive_volume_interferences": cross_component,
            "pass": len(cross_component) == 0,
        }
        if not fact["pass"]:
            raise GateError("ASSEMBLY_INTERFERENCE_FAIL", "native cross-component interference is nonzero", fact)
        return fact
    finally:
        manager.Done()


def active_configuration_name(model: Any, types: Any, pythoncom: Any) -> str:
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    return str(base.value(active, "Name"))


def show_configuration(model: Any, name: str, types: Any, pythoncom: Any) -> None:
    if not bool(model.ShowConfiguration2(name)):
        raise GateError("CONFIGURATION_ACTIVATE_FAIL", "ShowConfiguration2 returned false", {"configuration": name})
    if active_configuration_name(model, types, pythoncom) != name:
        raise GateError("CONFIGURATION_ACTIVE_READBACK_FAIL", "active configuration name did not read back", {"expected": name, "actual": active_configuration_name(model, types, pythoncom)})
    if not bool(model.ForceRebuild3(True)):
        raise GateError("CONFIGURATION_REBUILD_FAIL", "full rebuild failed", {"configuration": name})


def guide_reference_gate(
    model: Any,
    components: Dict[str, Any],
    ledger: Sequence[Dict[str, Any]],
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    by_name = {str(row["feature_name"]): row for row in ledger}
    faces: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    for side, prefix in (("LEFT", "L"), ("RIGHT", "R")):
        for guide in ("A", "B"):
            palm_key = f"PALM_{guide}"
            side_key = f"{side}_{guide}"
            if palm_key not in faces:
                _entity, faces[palm_key] = guide_face(model, components["PALM"], "PALM", guide, types, pythoncom)
            _entity, faces[side_key] = guide_face(model, components[side], side, guide, types, pythoncom)
            mate_name = MATE_NAMES[f"{prefix}_{guide}"]
            mate_refs = sorted(entity["persist_reference"]["sha256"] for entity in by_name[mate_name]["entities"])
            selected_refs = sorted((faces[palm_key]["persist_reference"]["sha256"], faces[side_key]["persist_reference"]["sha256"]))
            if mate_refs != selected_refs:
                raise GateError("GUIDE_MATE_PERSIST_REFERENCE_FAIL", "mate endpoints are not the two signature-selected physical guide faces", {"mate": mate_name, "mate_refs": mate_refs, "selected_refs": selected_refs})
            rows.append({"mate": mate_name, "palm_face": faces[palm_key], "finger_face": faces[side_key], "persist_reference_match": True})
    return {"guides": rows, "unique_face_contracts": faces, "pass": True}


def configuration_distance_values(
    limit_features: Sequence[Any],
    configuration: str,
    expected_mm: float,
    types: Any,
    pythoncom: Any,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for feature in limit_features:
        facts = advanced_limit_facts(feature, types, pythoncom)
        dimension = mate_dimension(feature, types, pythoncom)
        values = [float(value) for value in base.as_list(dimension.GetSystemValue3(SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [configuration]))]
        if len(values) != 1:
            raise GateError("CONFIGURATION_DIMENSION_READBACK_SHAPE_FAIL", "dimension readback is not one value", {"configuration": configuration, "feature": str(base.value(feature, "Name")), "values": values})
        facts["configured_dimension_mm"] = values[0] * 1000.0
        facts["expected_distance_mm"] = expected_mm
        if not facts["pass"] or abs(facts["distance_mm"] - expected_mm) > LIMIT_TOL_MM or abs(facts["configured_dimension_mm"] - expected_mm) > LIMIT_TOL_MM:
            raise GateError("CONFIGURATION_LIMIT_VALUE_FAIL", "active advanced limit distance does not match its state", {"configuration": configuration, "facts": facts})
        rows.append(facts)
    return rows


def verify_state(
    model: Any,
    assembly: Any,
    components: Dict[str, Any],
    name: str,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    spec = STATES[name]
    travel_mm = float(spec["travel_mm"])
    show_configuration(model, name, types, pythoncom)
    states = {role: component_transform_fact(component, role, travel_mm) for role, component in components.items()}
    opposed_sum = vector_norm([
        states["LEFT"]["translation_mm"][index] + states["RIGHT"]["translation_mm"][index]
        for index in range(3)
    ])
    magnitude_delta = abs(abs(states["LEFT"]["signed_jaw_translation_mm"]) - abs(states["RIGHT"]["signed_jaw_translation_mm"]))
    if opposed_sum > TRANSFORM_TRANSLATION_TOL_MM or magnitude_delta > TRANSFORM_TRANSLATION_TOL_MM:
        raise GateError("OPPOSED_EQUAL_TRANSFORM_FAIL", "finger transforms are not equal and opposite", {"configuration": name, "opposed_vector_sum_mm": opposed_sum, "magnitude_delta_mm": magnitude_delta, "states": states})
    ledger = mate_ledger(model, types, pythoncom, True)
    validate_mate_contract(ledger)
    by_name = {str(feature and base.value(feature, "Name")): feature for feature in mate_features(model, types, pythoncom)}
    limit_features = [by_name[MATE_NAMES["L_LIMIT"]], by_name[MATE_NAMES["R_LIMIT"]]]
    limit_values = configuration_distance_values(limit_features, name, travel_mm, types, pythoncom)
    guide_refs = guide_reference_gate(model, components, ledger, types, pythoncom)
    jaw = minimum_component_distance(model, components["LEFT"], "LEFT", components["RIGHT"], "RIGHT", types, pythoncom)
    left_palm = minimum_component_distance(model, components["LEFT"], "LEFT", components["PALM"], "PALM", types, pythoncom)
    right_palm = minimum_component_distance(model, components["RIGHT"], "RIGHT", components["PALM"], "PALM", types, pythoncom)
    expected_gap = float(spec["gap_mm"])
    gap_tolerance = CLOSED_GAP_TOL_MM if name in {"CLOSED", "HOLDING"} else GAP_TOL_MM
    if abs(float(jaw["distance_mm"]) - expected_gap) > gap_tolerance:
        raise GateError("NATIVE_JAW_GAP_FAIL", "native B-rep minimum jaw gap disagrees with authority", {"configuration": name, "actual": jaw, "expected_gap_mm": expected_gap, "tolerance_mm": gap_tolerance})
    if float(left_palm["distance_mm"]) > PALM_RAIL_CLEARANCE_MAX_MM or float(right_palm["distance_mm"]) > PALM_RAIL_CLEARANCE_MAX_MM:
        raise GateError("PALM_RAIL_CLEARANCE_FAIL", "finger is not riding on its palm rail", {"configuration": name, "left_to_palm": left_palm, "right_to_palm": right_palm, "maximum_mm": PALM_RAIL_CLEARANCE_MAX_MM})
    interference = interference_fact(assembly, types, pythoncom)
    return {
        "configuration": name,
        "authority": spec["authority"],
        "travel_mm": travel_mm,
        "expected_jaw_gap_mm": expected_gap,
        "components": states,
        "opposed_transform_vector_sum_mm": opposed_sum,
        "opposed_transform_magnitude_delta_mm": magnitude_delta,
        "limit_values": limit_values,
        "mate_ledger": ledger,
        "mate_signature": ledger_signature(ledger),
        "guide_reference_gate": guide_refs,
        "native_minimum_distance": {
            "finger_to_finger": jaw,
            "left_to_palm": left_palm,
            "right_to_palm": right_palm,
        },
        "interference": interference,
        "closed_penetration_mm3": 0.0 if name in {"CLOSED", "HOLDING"} and interference["cross_component_count"] == 0 else None,
        "grip_force": spec.get("grip_force"),
        "pass": True,
    }


def verify_all_states(
    model: Any,
    assembly: Any,
    components: Dict[str, Any],
    types: Any,
    pythoncom: Any,
    expected_signature: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if configuration_names(model) != sorted(STATES):
        raise GateError("CONFIGURATION_SET_COLD_FAIL", "configuration set drifted", {"actual": configuration_names(model), "expected": sorted(STATES)})
    rows: Dict[str, Any] = {}
    reference_signature: Optional[List[Dict[str, Any]]] = None
    for name in ("OPEN", "PREGRASP", "CLOSED", "HOLDING"):
        rows[name] = verify_state(model, assembly, components, name, types, pythoncom)
        signature = rows[name]["mate_signature"]
        if reference_signature is None:
            reference_signature = signature
        elif signature != reference_signature:
            raise GateError("CONFIGURATION_MATE_SIGNATURE_DRIFT", "mate identities/endpoints/limits differ across configurations", {"configuration": name, "actual": signature, "expected": reference_signature})
    if expected_signature is not None and reference_signature != expected_signature:
        raise GateError("COLD_MATE_SIGNATURE_DRIFT", "cold-open mate signature differs from saved checkpoint", {"actual": reference_signature, "expected": expected_signature})
    closed = rows["CLOSED"]
    holding = rows["HOLDING"]
    closed_transform = {role: row["translation_mm"] for role, row in closed["components"].items()}
    holding_transform = {role: row["translation_mm"] for role, row in holding["components"].items()}
    if closed_transform != holding_transform or abs(closed["native_minimum_distance"]["finger_to_finger"]["distance_mm"] - holding["native_minimum_distance"]["finger_to_finger"]["distance_mm"]) > 1.0e-6:
        raise GateError("HOLDING_ALIAS_FAIL", "HOLDING is not an exact CLOSED geometry alias", {"closed_transform": closed_transform, "holding_transform": holding_transform})
    show_configuration(model, "OPEN", types, pythoncom)
    return {
        "states": rows,
        "configuration_set": sorted(STATES),
        "common_mate_signature": reference_signature,
        "holding_disposition": "CLOSED_GEOMETRY_ALIAS_TARGET_DEPENDENT_FORCE_STATE_NO_ACTUATOR_MODEL_NO_FORCE_CLAIM",
        "type_23_slider_used": False,
        "closed_native_cross_component_interference_count": closed["interference"]["cross_component_count"],
        "closed_native_penetration_mm3": closed["closed_penetration_mm3"],
        "pass": True,
    }


def set_assembly_properties(model: Any) -> Dict[str, str]:
    properties = {
        "PartNumber": "B601_GRIPPER",
        "Description": "F3R2 B601 native two-finger prismatic-equivalent gripper assembly",
        "Revision": "V5-A",
        "RUN_ID": RUN_ID,
        "LOOP": "1C1",
        "INPUT_SPLIT": "PALM9_LEFT24_RIGHT24_AGGREGATE057_EXCLUDED",
        "KINEMATIC_CONTRACT": "2_GUIDE_COINCIDENT_PLUS_ADVANCED_LIMIT_DISTANCE_TYPE5_PER_FINGER",
        "LIMIT_MM": "0.0..71.5",
        "MATE_TYPE_23_USED": "NO",
        "CONFIGURATIONS": "OPEN;PREGRASP;CLOSED;HOLDING",
        "HOLDING_AUTHORITY": "CLOSED_GEOMETRY_ALIAS_NO_ACTUATOR_MODEL_NO_FORCE_CLAIM",
        "AUTHORIZED_LAUNCH_LOAD": "HOLD",
        "FLIGHT_QUALIFICATION": "HOLD",
    }
    manager = model.Extension.CustomPropertyManager("")
    for name, value in properties.items():
        result = int(manager.Add3(name, 30, value, 2))
        if result < 0:
            raise GateError("ASSEMBLY_PROPERTY_WRITE_FAIL", "cannot set assembly custom property", {"name": name, "result": result})
    return properties


def save_assembly(model: Any) -> Dict[str, Any]:
    if TARGET.exists():
        raise GateError("ASSEMBLY_TARGET_EXISTS", "write-once target already exists", {"path": posix(TARGET)})
    if not bool(model.ForceRebuild3(True)):
        raise GateError("ASSEMBLY_PRE_SAVE_REBUILD_FAIL", "full rebuild failed before save")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    returned = model.Extension.SaveAs(str(TARGET), 0, 1, None, 0, 0)
    ok, outs = base.unpack(returned)
    if len(outs) < 2:
        raise GateError("ASSEMBLY_SAVE_RETURN_SHAPE_FAIL", "SaveAs lacks errors/warnings", {"returned": repr(returned)})
    errors, warnings = int(outs[0]), int(outs[1])
    if not bool(ok) or errors != 0 or warnings != 0 or not TARGET.is_file():
        raise GateError("ASSEMBLY_SAVE_FAIL", "native assembly SaveAs failed", {"ok": bool(ok), "errors": errors, "warnings": warnings})
    final = model.Save3(1, 0, 0)
    final_ok, final_outs = base.unpack(final)
    if len(final_outs) < 2 or not bool(final_ok) or int(final_outs[0]) != 0 or int(final_outs[1]) != 0:
        raise GateError("ASSEMBLY_SAVE3_FAIL", "native assembly Save3 failed", {"returned": repr(final)})
    return {**file_fact(TARGET), "errors": errors, "warnings": warnings}


def transform_point(array: Sequence[float], point: Sequence[float]) -> List[float]:
    if len(array) != 16 or len(point) != 3:
        raise GateError("BREP_TRANSFORM_SHAPE_FAIL", "transform/point shape is invalid")
    return [
        float(array[0]) * point[0] + float(array[3]) * point[1] + float(array[6]) * point[2] + float(array[9]),
        float(array[1]) * point[0] + float(array[4]) * point[1] + float(array[7]) * point[2] + float(array[10]),
        float(array[2]) * point[0] + float(array[5]) * point[1] + float(array[8]) * point[2] + float(array[11]),
    ]


def assembly_brep_bbox_mm(model: Any, types: Any, pythoncom: Any) -> Tuple[List[float], List[Dict[str, Any]]]:
    """Exact cold B-rep extrema in the controlled gripper assembly frame."""
    from win32com.client import VARIANT

    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    components = [base.wrap(item, "IComponent2", types, pythoncom) for item in base.as_list(assembly.GetComponents(True))]
    minima = [math.inf, math.inf, math.inf]
    maxima = [-math.inf, -math.inf, -math.inf]
    witnesses: List[Dict[str, Any]] = []
    total_bodies = 0
    for component in components:
        if int(base.value(component, "GetSuppression2")) != SW_COMPONENT_RESOLVED:
            continue
        raw_transform = base.value(component, "Transform2")
        if raw_transform is None:
            raise GateError("BREP_COMPONENT_TRANSFORM_NULL", "resolved gripper component has no transform", {"name2": str(base.value(component, "Name2"))})
        array = [float(value) for value in base.as_list(base.value(raw_transform, "ArrayData"))]
        if len(array) != 16 or abs(array[12] - 1.0) > 2.0e-9:
            raise GateError("BREP_COMPONENT_TRANSFORM_FAIL", "gripper component transform is not rigid/unity scale", {"name2": str(base.value(component, "Name2")), "transform": array})
        bodies = [base.wrap(item, "IBody2", types, pythoncom) for item in base.as_list(component.GetBodies2(SW_BODY_SOLID))]
        if not bodies:
            raise GateError("BREP_COMPONENT_BODY_EMPTY", "resolved gripper component has no solid body", {"name2": str(base.value(component, "Name2"))})
        component_extrema = [math.inf, math.inf, math.inf, -math.inf, -math.inf, -math.inf]
        for body in bodies:
            total_bodies += 1
            for axis in range(3):
                for sign in (-1.0, 1.0):
                    direction = [sign * float(array[axis]), sign * float(array[axis + 3]), sign * float(array[axis + 6])]
                    outx = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
                    outy = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
                    outz = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
                    if not bool(body.GetExtremePoint(direction[0], direction[1], direction[2], outx, outy, outz)):
                        raise GateError("BREP_EXTREME_POINT_FAIL", "IBody2.GetExtremePoint returned false", {"name2": str(base.value(component, "Name2")), "axis": axis, "sign": sign})
                    assembly_point = transform_point(array, [float(outx.value), float(outy.value), float(outz.value)])
                    if sign < 0.0:
                        minima[axis] = min(minima[axis], assembly_point[axis])
                        component_extrema[axis] = min(component_extrema[axis], assembly_point[axis])
                    else:
                        maxima[axis] = max(maxima[axis], assembly_point[axis])
                        component_extrema[axis + 3] = max(component_extrema[axis + 3], assembly_point[axis])
        witnesses.append({
            "name2": str(base.value(component, "Name2")),
            "path": component_path(component),
            "transform": [round(value, 12) for value in array],
            "brep_bbox_mm": [round(value * 1000.0, 9) for value in component_extrema],
            "solid_body_count": len(bodies),
        })
    if total_bodies != 57 or not all(math.isfinite(value) for value in minima + maxima) or any(maxima[index] <= minima[index] for index in range(3)):
        raise GateError("ASSEMBLY_BREP_BBOX_FAIL", "cold gripper assembly B-rep bbox/body count is invalid", {"minima": minima, "maxima": maxima, "body_count": total_bodies})
    return [round(value * 1000.0, 9) for value in minima + maxima], witnesses


def build_assembly(sw: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_model = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
    if raw_model is None:
        raise GateError("NEW_ASSEMBLY_FAIL", "NewDocument returned null")
    model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    components: Dict[str, Any] = {}
    insert_rows: List[Dict[str, Any]] = []
    for role in ("PALM", "LEFT", "RIGHT"):
        spec = PARTS[role]
        translation = expected_translation_m(role, float(STATES["OPEN"]["travel_mm"]))
        component = insert_component(sw, model, assembly, role, Path(spec["path"]), bool(spec["fixed"]), translation, types, pythoncom)
        components[role] = component
        insert_rows.append({
            "role": role,
            "path": component_path(component),
            "fixed": bool(spec["fixed"]),
            "initial_open_translation_m": list(translation),
            "name2": str(base.value(component, "Name2")),
        })
    components = assembly_components(model, assembly, types, pythoncom)

    creation_geometry: List[Dict[str, Any]] = []
    created_features: Dict[str, Any] = {}
    for side, prefix in (("LEFT", "L"), ("RIGHT", "R")):
        for guide in ("A", "B"):
            palm_face, palm_fact = guide_face(model, components["PALM"], "PALM", guide, types, pythoncom)
            finger_face, finger_fact = guide_face(model, components[side], side, guide, types, pythoncom)
            name = MATE_NAMES[f"{prefix}_{guide}"]
            alignment = int(GUIDE_CONTRACTS[guide][f"{side}_alignment"])
            created_features[name] = add_face_mate(model, assembly, palm_face, finger_face, alignment, name, types, pythoncom)
            creation_geometry.append({"mate": name, "alignment_requested": alignment, "palm_face": palm_fact, "finger_face": finger_fact})
    created_features[MATE_NAMES["L_LIMIT"]] = add_advanced_limit_distance(model, assembly, components["PALM"], components["LEFT"], MATE_NAMES["L_LIMIT"], types, pythoncom)
    created_features[MATE_NAMES["R_LIMIT"]] = add_advanced_limit_distance(model, assembly, components["PALM"], components["RIGHT"], MATE_NAMES["R_LIMIT"], types, pythoncom)
    config_creation = establish_configurations(
        model,
        [created_features[MATE_NAMES["L_LIMIT"]], created_features[MATE_NAMES["R_LIMIT"]]],
        types,
        pythoncom,
    )
    properties = set_assembly_properties(model)
    live_pre_save = verify_all_states(model, assembly, components, types, pythoncom)
    saved = save_assembly(model)
    live_post_save = verify_all_states(model, assembly, components, types, pythoncom)
    if live_post_save["common_mate_signature"] != live_pre_save["common_mate_signature"]:
        raise GateError("SAVE_MATE_SIGNATURE_DRIFT", "saving changed mate persistent identities or semantics", {"pre": live_pre_save["common_mate_signature"], "post": live_post_save["common_mate_signature"]})
    return {
        "document_title": str(base.value(model, "GetTitle")),
        "components_inserted": insert_rows,
        "mate_creation_geometry": creation_geometry,
        "configuration_creation": config_creation,
        "custom_properties": properties,
        "live_pre_save": live_pre_save,
        "save": saved,
        "live_post_save": live_post_save,
    }


def cold_verify(
    sw: Any,
    types: Any,
    pythoncom: Any,
    expected_signature: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    baseline = int(base.value(sw, "GetDocumentCount"))
    if baseline != 0:
        raise GateError("COLD_VERIFY_BASELINE_NOT_EMPTY", "cold verification requires zero open documents", {"count": baseline})
    raw, errors, warnings = unpack_document(sw.OpenDoc6(str(TARGET), SW_DOC_ASSEMBLY, SW_OPEN_SILENT_READONLY, "", 0, 0), "COLD_OPEN_ASSEMBLY")
    if raw is None or errors != 0 or warnings != 0:
        raise GateError("COLD_OPEN_ASSEMBLY_FAIL", "assembly did not cold-open cleanly", {"errors": errors, "warnings": warnings})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    if not bool(base.value(model, "IsOpenedReadOnly")):
        raise GateError("COLD_ASSEMBLY_NOT_READ_ONLY", "cold-opened assembly is not read-only")
    components = assembly_components(model, assembly, types, pythoncom)
    verification = verify_all_states(model, assembly, components, types, pythoncom, expected_signature)
    # verify_all_states restores OPEN before returning; record the complete
    # cold B-rep extrema and the fixed PALM datum in that controlled frame.
    brep_bbox_mm, brep_component_witnesses = assembly_brep_bbox_mm(model, types, pythoncom)
    interconnect = base.feature_names_3d_interconnect(model, types, pythoncom)
    external = int(base.external_reference_count(model, "Loop1C1:GRIPPER_LINK6_LOCAL"))
    auxiliary = int(base.auxiliary_reference_count(model, "Loop1C1:GRIPPER_LINK6_LOCAL"))
    if interconnect or external != 0 or auxiliary != 0:
        raise GateError("COLD_ASSEMBLY_REFERENCE_FAIL", "cold gripper assembly retained interconnect/external/auxiliary references", {"three_d_interconnect_features": interconnect, "external_reference_count": external, "auxiliary_reference_count": auxiliary})
    return {
        "open": {"errors": errors, "warnings": warnings, "read_only": True},
        "components": {role: component_path(component) for role, component in components.items()},
        "verification": verification,
        "cold_brep_bbox_mm": brep_bbox_mm,
        "cold_brep_component_witnesses": brep_component_witnesses,
        "three_d_interconnect_features": interconnect,
        "external_reference_count": external,
        "auxiliary_reference_count": auxiliary,
        "target": file_fact(TARGET),
        "verdict": "V5_LOOP1C1_GRIPPER_COLD_BREP_FRAME_PASS",
    }


def gripper_frame_contract(input_audit: Dict[str, Any], cold: Dict[str, Any]) -> Dict[str, Any]:
    bbox = cold.get("cold_brep_bbox_mm")
    witnesses = cold.get("cold_brep_component_witnesses")
    open_state = cold.get("verification", {}).get("states", {}).get("OPEN", {})
    palm = open_state.get("components", {}).get("PALM", {}) if isinstance(open_state, dict) else {}
    predecessor = input_audit.get("frame_contract", {})
    if (
        cold.get("verdict") != "V5_LOOP1C1_GRIPPER_COLD_BREP_FRAME_PASS"
        or not isinstance(bbox, list)
        or len(bbox) != 6
        or not all(math.isfinite(float(value)) for value in bbox)
        or any(float(bbox[index + 3]) <= float(bbox[index]) for index in range(3))
        or not isinstance(witnesses, list)
        or len(witnesses) != 3
        or int(cold.get("external_reference_count", -1)) != 0
        or int(cold.get("auxiliary_reference_count", -1)) != 0
        or cold.get("three_d_interconnect_features")
        or palm.get("fixed") is not True
        or int(palm.get("suppression", -1)) != SW_COMPONENT_RESOLVED
        or float(palm.get("rotation_identity_max_error", math.inf)) > TRANSFORM_ROTATION_TOL
        or predecessor.get("source_frame") != "LINK6_LOCAL"
        or predecessor.get("placement") != "LIVE_LINK6_TOTAL_TRANSFORM"
    ):
        raise GateError("GRIPPER_FRAME_CONTRACT_FAIL", "cold gripper frame/datum/predecessor witness is incomplete", {"cold": cold, "palm": palm, "predecessor": predecessor})
    target = file_fact(TARGET)
    if cold.get("target") != target:
        raise GateError("GRIPPER_FRAME_TARGET_FAIL", "cold gripper frame witness is not bound to the current native target", {"cold_target": cold.get("target"), "target": target})
    return {
        "schema": "F3R2_V5_NATIVE_FRAME_CONTRACT_V1",
        "source_frame": "LINK6_LOCAL",
        "placement": "LIVE_LINK6_TOTAL_TRANSFORM",
        "target_path": posix(TARGET),
        "target_sha256": target["sha256"],
        "source_bbox_mm": [float(value) for value in bbox],
        "witness": {
            "method": "SOLIDWORKS_COLD_BREP_BBOX_AND_DATUM_WITNESS",
            "cold_reopen_pass": True,
            "cold_reopen_verdict": cold["verdict"],
            "configuration": "OPEN",
            "external_reference_count": 0,
            "auxiliary_reference_count": 0,
            "frame_rationale": "The three-part gripper is cold-reopened and measured in its native link-6-local assembly coordinates with the PALM occurrence fixed at identity; top assembly must apply only the live nested link-6 total transform.",
            "fixed_datum": {
                "role": "PALM",
                "native_path": palm.get("path"),
                "component_transform": palm.get("transform"),
                "assembly_datum_basis": ["ORIGIN", "+X", "+Y", "+Z"],
            },
            "component_brep_witnesses": witnesses,
            "predecessor_part_set_frame_contract": predecessor,
        },
    }


def write_checkpoint(input_audit: Dict[str, Any], build: Optional[Dict[str, Any]], cold: Dict[str, Any], mode: str) -> Dict[str, Any]:
    frame_contract = gripper_frame_contract(input_audit, cold)
    payload = {
        "schema": "F3R2_V5_LOOP1C1_GRIPPER_ASSEMBLY_CHECKPOINT_V1",
        "timestamp_utc": utc_now(),
        "binding": checkpoint_binding(input_audit),
        "target": file_fact(TARGET),
        "script_copy": file_fact(SCRIPT_COPY),
        "mode": mode,
        "build": build,
        "cold_reopen": cold,
        "frame_contracts": {"GRIPPER": frame_contract},
        "mate_signature": cold["verification"]["common_mate_signature"],
        "verdict": "V5_LOOP1C1_NATIVE_GRIPPER_ASSEMBLY_CHECKPOINT_PASS",
    }
    write_json_once(CHECKPOINT, payload)
    return payload


def manifest_text() -> str:
    paths = [TARGET, SCRIPT_COPY, LOOP1C0_RECEIPT, *[Path(spec["path"]) for spec in PARTS.values()]]
    return "".join(f"{sha256(path)}  {path.relative_to(RUN_ROOT).as_posix()}\n" for path in sorted(paths, key=lambda item: item.as_posix()))


def audit_input_hashes_unchanged(before: Dict[str, Any]) -> Dict[str, Any]:
    after = audit_loop1c0_inputs(True)
    before_hashes = {role: row["file"]["sha256"] for role, row in before["parts"].items()}
    after_hashes = {role: row["file"]["sha256"] for role, row in after["parts"].items()}
    if before["receipt"]["sha256"] != after["receipt"]["sha256"] or before_hashes != after_hashes:
        raise GateError("LOOP1C0_INPUT_POST_HASH_FAIL", "Loop1C0 inputs changed during assembly transaction", {"before": before_hashes, "after": after_hashes})
    return after


def execute() -> int:
    started = utc_now()
    script = Path(__file__).resolve()
    sw = types = pythoncom = None
    cleanup: List[Dict[str, Any]] = []
    try:
        audit = static_audit()
        if not audit["execution_authorized"]:
            raise GateError("STATIC_EXECUTION_NOT_AUTHORIZED", "static audit did not authorize execution", audit)
        input_pre = audit_loop1c0_inputs(True)
        protected_pre = base.audit_protected()
        memory_samples = base.memory_gate()
        copy_once(script, SCRIPT_COPY)
        sw, types, pythoncom, session = base.attach_empty_session()
        imported = load_json(IMPORT_RECEIPT)
        receipt_pid = int(imported.get("solidworks", {}).get("pid", -1))
        g0_pid = int(imported.get("g0", {}).get("session_b_pid", -2))
        if receipt_pid <= 0 or receipt_pid != g0_pid or int(session["pid"]) != receipt_pid:
            raise GateError("SESSION_B_PID_BINDING_FAIL", "live attach is not the fixed Session B process", {"live_pid": session["pid"], "receipt_pid": receipt_pid, "g0_pid": g0_pid})
        state = target_checkpoint_state(input_pre)
        if state["state"] == "PENDING":
            build = build_assembly(sw, types, pythoncom)
            close_all_owned(sw)
            cold = cold_verify(sw, types, pythoncom, build["live_post_save"]["common_mate_signature"])
            close_all_owned(sw)
            checkpoint = write_checkpoint(input_pre, build, cold, "CREATED")
        elif state["state"] == "RESUME_REQUIRES_COLD_REOPEN":
            existing = load_json(CHECKPOINT)
            cold = cold_verify(sw, types, pythoncom, existing["mate_signature"])
            close_all_owned(sw)
            checkpoint = existing
            build = None
        else:
            raise GateError("TARGET_CHECKPOINT_STATE_HOLD", "target/checkpoint state is not executable", state)
        input_post = audit_input_hashes_unchanged(input_pre)
        frame_contract = gripper_frame_contract(input_pre, cold)
        protected_post = base.audit_protected()
        if protected_pre != protected_post:
            raise GateError("PROTECTED_POST_HASH_FAIL", "protected asset audit changed during transaction")
        if not FINAL_MANIFEST.exists():
            write_text_once(FINAL_MANIFEST, manifest_text())
        expected_manifest = manifest_text()
        if FINAL_MANIFEST.read_text(encoding="utf-8") != expected_manifest:
            raise GateError("FINAL_MANIFEST_DRIFT", "final manifest differs from exact current identities")
        result = {
            "schema": "F3R2_V5_LOOP1C1_GRIPPER_ASSEMBLY_RECEIPT_V1",
            "timestamp_start_utc": started,
            "timestamp_end_utc": utc_now(),
            "run_root": posix(RUN_ROOT),
            "binding": checkpoint_binding(input_pre),
            "session": session,
            "memory_samples_gib": memory_samples,
            "input_pre": input_pre,
            "input_post": input_post,
            "protected_pre": protected_pre,
            "protected_post": protected_post,
            "build": build,
            "checkpoint": checkpoint,
            "cold_reopen": cold,
            "frame_contracts": {"GRIPPER": frame_contract},
            "target": file_fact(TARGET),
            "script_copy": file_fact(SCRIPT_COPY),
            "manifest": file_fact(FINAL_MANIFEST),
            "mechanical_contract": "TWO_PHYSICAL_GUIDE_COINCIDENT_PLUS_ADVANCED_TYPE5_LIMIT_DISTANCE_0_TO_71_5_MM_PER_FINGER",
            "mate_type_23_used": False,
            "configurations": {name: dict(spec) for name, spec in STATES.items()},
            "holding_disposition": "CLOSED_GEOMETRY_ALIAS_TARGET_DEPENDENT_FORCE_STATE_NOT_EVALUATED_NO_ACTUATOR_MODEL",
            "authorized_launch_load": "HOLD",
            "flight_qualification": "HOLD",
            "remaining_hold": [
                "LOOP1D_TOP_LEVEL_INTEGRATION_IF_NOT_ALREADY_COMPLETE",
                "HUMAN_SOLIDWORKS_VISUAL_REVIEW",
                "MANUFACTURING_TOLERANCE_LOAD_LIFE_AND_ACTUATOR_QUALIFICATION",
            ],
            "verdict": "V5_LOOP1C1_NATIVE_GRIPPER_ASSEMBLY_PASS_MECHANICAL_MAINLINE_FREEZE_READY",
        }
        if not FINAL_RECEIPT.exists():
            write_json_once(FINAL_RECEIPT, result)
        else:
            existing = load_json(FINAL_RECEIPT)
            if existing.get("verdict") != result["verdict"] or existing.get("target", {}).get("sha256") != result["target"]["sha256"]:
                raise GateError("FINAL_RECEIPT_DRIFT", "existing final receipt does not match verified target")
        print(json.dumps({"verdict": result["verdict"], "target": posix(TARGET), "receipt": posix(FINAL_RECEIPT)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        code = exc.code if isinstance(exc, GateError) else "UNHANDLED_EXCEPTION"
        detail = exc.detail if isinstance(exc, GateError) else {}
        if sw is not None:
            try:
                cleanup = close_all_owned(sw)
            except Exception as cleanup_exc:
                cleanup.append({"cleanup_exception": repr(cleanup_exc)})
        failure = {
            "schema": "F3R2_V5_LOOP1C1_GRIPPER_ASSEMBLY_FAILURE_V1",
            "timestamp_utc": utc_now(),
            "code": code,
            "message": str(exc),
            "detail": detail,
            "traceback": traceback.format_exc(),
            "owned_document_cleanup": cleanup,
            "write_once_policy": "NO_DELETE_NO_OVERWRITE_ORPHAN_TARGET_OR_CHECKPOINT_REMAINS_HOLD",
            "verdict": "V5_LOOP1C1_FAIL_CLOSED",
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        try:
            write_json_once(RUN_ROOT / f"13_validation/V5_LOOP1C1_FAIL_{stamp}.json", failure)
        except Exception:
            pass
        print(json.dumps({"verdict": failure["verdict"], "code": code, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        sw = types = None
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F3R2 V5 Loop1C1 attach-only native gripper assembly")
    parser.add_argument("--execute-assembly", action="store_true", help="execute the controlled 1C1 assembly transaction")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.execute_assembly:
        return execute()
    print(json.dumps(static_audit(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
