#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loop 1C0: split the frozen B51 57-physical-body gripper into three parts.

This executable is deliberately limited to the transaction that can be
closed independently: PALM (9 bodies), LEFT_FINGER (24), RIGHT_FINGER (24).
Loop 1C1 owns the native prismatic-mate assembly and the CLOSED/PREGRASP/OPEN
configuration proof.  Nothing in this file claims that 1C1 is complete.

Runtime access is inherited from the hash-pinned Loop-1 helper and is strictly
GetActiveObject-only.  The input body order is never authoritative: every
body is bound from the cold-opened source SLDPRT in its native link-6-local
frame by exact source label plus a unique local B-rep bbox/centroid/volume/face
fingerprint before Copy2; GetBodies2 enumeration order is never consulted.
The full-top deployed STEP/STL witnesses are retained only for provenance and
rotation-invariant volume corroboration.  Their world coordinates/topology and
historical world jaw origin are explicitly prohibited as mapping keys.
Historical CSV row LINKLOCAL057 is an aggregate STEP/mesh wrapper containing
the union of rows 000..056.  It is fixed as evidence but explicitly excluded
from physical-body creation to prevent overlapping geometry and double mass.
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
import struct
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
sys.path.insert(0, str(RUN_ROOT / "99_tools"))
import F3R2_V5_SESSION_BINDING as sbin

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
BASE_HELPER_SHA256 = "E44BC52CFBDECCC107E361ACB0EDD993EFC46248EB663A994564B77BDA30F906"
LOOP1A_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY.py"
LOOP1A_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY.py"
LOOP1A_HELPER_SHA256 = "25369CB867685EBA0C374636F8F540867D3D8B5890F9CE8622A6842E6518EC42"

SOURCE_PART = ROOT / (
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/"
    "B601_ARM_B51_COPY/inputs/vendor_link_parts/B51_REF_gripper_detail_LINKLOCAL.SLDPRT"
)
SOURCE_PART_SHA256 = "6758B99741FFACABC31C2D629C6191F25C461AC877442212B468B141805EEECC"
SOURCE_PART_BYTES = 5_277_750
SOURCE_LOCAL_COLD_EVIDENCE = ROOT / (
    "20_engineering/cad/B5_0_B601_space_manipulator_candidate/03_CAD/"
    "native_runs/B50_NATIVE_20260727T2214Z/evidence/native_G08_build.json"
)
SOURCE_LOCAL_COLD_EVIDENCE_SHA256 = "9B581BCB3C13D97059F2CAC3536FF1FBDE4FB672DC10AC6B6472658ACC708684"
SOURCE_LOCAL_COLD_EVIDENCE_BYTES = 7_195
SOURCE_LOCAL_COLD_BBOX_MM = (
    -107.164014536302,
    -92.02740203039404,
    -34.19630827840407,
    0.04531110930097726,
    92.04226712992005,
    34.27035864433205,
)
ASSIGNMENT_CSV = ROOT / (
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/"
    "F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"
)
ASSIGNMENT_CSV_SHA256 = "419F63149413E5EC5677357D95639CFACF68CE143964485EFB402F2A803B2C78"

EVIDENCE_ROOT = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
BREP_PROBE = EVIDENCE_ROOT / "05_clearance/mesh/BREP_PROBE_GRIPPER.json"
BREP_PROBE_SHA256 = "89A1B589E6AB20F2CAB0C7415107908EF1D58307C0EDF2A4D1C25BE5B6330D8A"
MESH_MANIFEST = EVIDENCE_ROOT / "05_clearance/mesh/gripper_solids_DEPLOYED/GRIPPER_SOLID_MESHES.json"
MESH_MANIFEST_SHA256 = "C52124D1AF3C66BE3D597A1AAE3870568B591B8E5E0615A19A5EA58C82676251"
HISTORICAL_BINDING = EVIDENCE_ROOT / "08_camera_harness/F3R2_GRIPPER_FINGER_BINDING.json"
HISTORICAL_BINDING_SHA256 = "C17367F76694634F5D43618D1627AEBC544348D5C94589D16079FEA52530B69E"
M3R_BINDING_ADDENDUM = EVIDENCE_ROOT / "08_camera_harness/F3R2_GRIPPER_FINGER_BINDING_ADDENDUM_M3R_V2.json"
M3R_BINDING_ADDENDUM_SHA256 = "2C31E0D666C835F079E7FB8EF8C6FBC64114F816BAA389017F95F12A067649E6"
R3D_ASSIGNMENT_SCRIPT = EVIDENCE_ROOT / "99_tools/r3d_g33_gripper.py"
R3D_ASSIGNMENT_SCRIPT_SHA256 = "FEB8EB698745F664B3CCD25840B01069E40307964073A87DF3ABF33F1DDDDBB1"
R3E_MESH_SCRIPT = EVIDENCE_ROOT / "99_tools/r3e_g33_gripper_mesh.py"
R3E_MESH_SCRIPT_SHA256 = "637A2D52E31472ADF4551B33A66145B99606279F6D94B0DA608D6FFF54C8602B"
FREECAD_BREP_PROBE_SCRIPT = EVIDENCE_ROOT / "99_tools/fc_probe_brep.py"
FREECAD_BREP_PROBE_SCRIPT_SHA256 = "E04ADEE812EEEE2FE0EAEA7E90784FC7E822F47EBF947389B7DB9F25E4123B6E"
FREECAD_SOLID_EXPORT_SCRIPT = EVIDENCE_ROOT / "99_tools/fc_export_gripper_solids.py"
FREECAD_SOLID_EXPORT_SCRIPT_SHA256 = "FA824FE5C780E0059D6E42CCFAF2D014BB4A651F25D2299A12CF7A0B7F9BE955"
SOURCE_STEP = ROOT / "20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/04_configurations/G2/step/F3R1_V3_DEPLOYED_NOMINAL.step"
SOURCE_STEP_SHA256 = "A7549D0E913584FA4AF894A710F5CE9DF363722FD7F4F863B1C3B3FF2B4653C2"
SOURCE_STEP_BYTES = 125_946_155

BODY_LABEL_PREFIX = "B51_REF_gripper_detail_LINKLOCAL"
B50_BODY_LABEL_PREFIX = "B50_REF_gripper_detail_LINKLOCAL"
AGGREGATE_LABEL = BODY_LABEL_PREFIX + "057"
PHYSICAL_LABELS = [BODY_LABEL_PREFIX] + [BODY_LABEL_PREFIX + f"{index:03d}" for index in range(1, 57)]
SOURCE_EXPECTED_SW_BODY_COUNT = 57
SOURCE_EXPECTED_SW_FACE_COUNT = 1798
SOURCE_EXPECTED_SW_VOLUME_MM3 = 151_641.811

SW_DOC_PART = 1
SW_OPEN_SILENT_READONLY = 3
SW_CREATE_FEATURE_BODY_CHECK = 1
# swBodyType_e from the installed SOLIDWORKS 2024 swconst.tlb.  GetBodies2(0,
# False) already requests solid bodies, but every returned IBody2 is checked
# again through the makepy-exposed IBody2.GetType() contract before any copy.
SW_BODY_SOLID = 0
VOLUME_ABS_TOL_MM3 = 0.02
VOLUME_REL_TOL = 5.0e-6
MAPPING_VOLUME_ABS_TOL_MM3 = 0.10
MAPPING_VOLUME_REL_TOL = 1.0e-4
SOURCE_LOCAL_BBOX_TOL_MM = 1.0e-4
SOURCE_TOTAL_VOLUME_TOL_MM3 = 0.05
LOCAL_FINGERPRINT_DECIMALS = 6
LOCAL_MAPPING_AUTHORITY = "SOURCE_SLDPRT_COLD_LINK6_LOCAL_VOLUME_PLUS_MIRROR_STATION_FINGERPRINT_MAPPING"
FULL_TOP_WORLD_EVIDENCE_DISPOSITION = "PROVENANCE_AND_VOLUME_ONLY_NOT_A_MAPPING_FRAME"

GROUPS: Dict[str, Dict[str, Any]] = {
    "gripper_link": {
        "role": "PALM",
        "count": 9,
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
PREDECESSOR_R0_SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY.py"
PREDECESSOR_R0_SCRIPT_COPY_SHA256 = "D551B552F861F9B7B9DDEE37558C82B8786C322B87FA10C535F798CA77CFA533"
PREDECESSOR_R0_SCRIPT_COPY_BYTES = 39666
PREDECESSOR_R1_SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY_R1.py"
PREDECESSOR_R1_SCRIPT_COPY_SHA256 = "407844BF6328EDF2DABCFC5507B601AD56D32BB73C0B13A8D487BB78E1AA4BAA"
PREDECESSOR_R1_SCRIPT_COPY_BYTES = 40986
PREDECESSOR_R2_SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY_R2.py"
PREDECESSOR_R2_SCRIPT_COPY_SHA256 = "F92002CF9513BAC7800B6B627482EC893AE45402225600CF36BD79A08BA7B7E0"
PREDECESSOR_R2_SCRIPT_COPY_BYTES = 69704
SCRIPT_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY_R3.py"

_GEOMETRY_CACHE: Optional[Dict[str, Any]] = None


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


def mapping_volume_matches(actual_mm3: float, expected_mm3: float) -> bool:
    tolerance = max(MAPPING_VOLUME_ABS_TOL_MM3, abs(expected_mm3) * MAPPING_VOLUME_REL_TOL)
    return math.isfinite(actual_mm3) and abs(actual_mm3 - expected_mm3) <= tolerance


def vector_dot(first: Sequence[float], second: Sequence[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def vector_distance(first: Sequence[float], second: Sequence[float]) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(first, second)))


def bbox_metrics(box_mm: Sequence[float]) -> Dict[str, Any]:
    box = [float(value) for value in box_mm]
    if len(box) != 6 or not all(math.isfinite(value) for value in box):
        raise GateError("BBOX_SHAPE_FAIL", "body bounding box is not six finite values", {"box_mm": box})
    if any(box[index] > box[index + 3] for index in range(3)):
        raise GateError("BBOX_RANGE_FAIL", "body bounding box has inverted limits", {"box_mm": box})
    centre = [(box[index] + box[index + 3]) / 2.0 for index in range(3)]
    return {
        "bbox_mm": box,
        "bbox_centroid_mm": centre,
        "bbox_size_mm": [box[index + 3] - box[index] for index in range(3)],
    }


def union_bbox_mm(rows: Sequence[Dict[str, Any]]) -> List[float]:
    boxes = [bbox_metrics(row["bbox_mm"])["bbox_mm"] for row in rows]
    if not boxes:
        raise GateError("BBOX_UNION_EMPTY", "cannot form a B-rep bbox union from an empty body set")
    return [
        *[min(box[index] for box in boxes) for index in range(3)],
        *[max(box[index] for box in boxes) for index in range(3, 6)],
    ]


def local_fingerprint(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic identity of one source-SLDPRT body in link-6-local space."""
    payload = {
        "frame": "LINK6_LOCAL",
        "faces": int(facts["faces"]),
        "volume_mm3": round(float(facts["volume_mm3"]), LOCAL_FINGERPRINT_DECIMALS),
        "bbox_mm": [round(float(value), LOCAL_FINGERPRINT_DECIMALS) for value in facts["bbox_mm"]],
        "bbox_centroid_mm": [round(float(value), LOCAL_FINGERPRINT_DECIMALS) for value in facts["bbox_centroid_mm"]],
        "mass_centroid_mm": [round(float(value), LOCAL_FINGERPRINT_DECIMALS) for value in facts["mass_centroid_mm"]],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**payload, "sha256": hashlib.sha256(encoded).hexdigest().upper()}


def binary_stl_mass_centroid(path: Path) -> Dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 84:
        raise GateError("STL_TOO_SHORT", "fixed STL is shorter than a binary header", {"path": posix(path)})
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_bytes = 84 + 50 * triangle_count
    if len(data) != expected_bytes:
        raise GateError("STL_BINARY_SHAPE_FAIL", "fixed STL does not have the expected binary triangle layout", {"path": posix(path), "bytes": len(data), "triangle_count": triangle_count, "expected_bytes": expected_bytes})
    volume6 = 0.0
    moment = [0.0, 0.0, 0.0]
    for record in struct.iter_unpack("<12fH", data[84:]):
        a = record[3:6]
        b = record[6:9]
        c = record[9:12]
        cross = (
            b[1] * c[2] - b[2] * c[1],
            b[2] * c[0] - b[0] * c[2],
            b[0] * c[1] - b[1] * c[0],
        )
        signed6 = vector_dot(a, cross)
        volume6 += signed6
        for index in range(3):
            moment[index] += signed6 * (a[index] + b[index] + c[index]) / 4.0
    if not math.isfinite(volume6) or abs(volume6) <= 1.0e-12:
        raise GateError("STL_CENTROID_FAIL", "fixed STL has zero/non-finite signed volume", {"path": posix(path), "signed_volume6": volume6})
    return {
        "mass_centroid_mm": [value / volume6 for value in moment],
        "tessellated_signed_volume_mm3": volume6 / 6.0,
        "triangle_count": triangle_count,
    }


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
        (SOURCE_LOCAL_COLD_EVIDENCE, SOURCE_LOCAL_COLD_EVIDENCE_SHA256, SOURCE_LOCAL_COLD_EVIDENCE_BYTES),
        (ASSIGNMENT_CSV, ASSIGNMENT_CSV_SHA256, None),
        (BREP_PROBE, BREP_PROBE_SHA256, None),
        (MESH_MANIFEST, MESH_MANIFEST_SHA256, None),
        (HISTORICAL_BINDING, HISTORICAL_BINDING_SHA256, None),
        (M3R_BINDING_ADDENDUM, M3R_BINDING_ADDENDUM_SHA256, None),
        (R3D_ASSIGNMENT_SCRIPT, R3D_ASSIGNMENT_SCRIPT_SHA256, None),
        (R3E_MESH_SCRIPT, R3E_MESH_SCRIPT_SHA256, None),
        (FREECAD_BREP_PROBE_SCRIPT, FREECAD_BREP_PROBE_SCRIPT_SHA256, None),
        (FREECAD_SOLID_EXPORT_SCRIPT, FREECAD_SOLID_EXPORT_SCRIPT_SHA256, None),
        (SOURCE_STEP, SOURCE_STEP_SHA256, SOURCE_STEP_BYTES),
        # The first fail-closed attempt copied its exact executor before the
        # PID-schema defect was detected.  Preserve and hash-bind that file as
        # immutable failure evidence.  R1 is likewise preserved after its
        # 57-vs-58 fail-closed discovery; this aggregate-corrected executor
        # uses a new write-once R2 filename rather than overwriting history.
        (PREDECESSOR_R0_SCRIPT_COPY, PREDECESSOR_R0_SCRIPT_COPY_SHA256, PREDECESSOR_R0_SCRIPT_COPY_BYTES),
        (PREDECESSOR_R1_SCRIPT_COPY, PREDECESSOR_R1_SCRIPT_COPY_SHA256, PREDECESSOR_R1_SCRIPT_COPY_BYTES),
        (PREDECESSOR_R2_SCRIPT_COPY, PREDECESSOR_R2_SCRIPT_COPY_SHA256, PREDECESSOR_R2_SCRIPT_COPY_BYTES),
    ]


def load_geometry_contract() -> Dict[str, Any]:
    global _GEOMETRY_CACHE
    if _GEOMETRY_CACHE is not None:
        return _GEOMETRY_CACHE
    brep_payload = load_json(BREP_PROBE)
    mesh_payload = load_json(MESH_MANIFEST)
    binding_payload = load_json(HISTORICAL_BINDING)
    addendum_payload = load_json(M3R_BINDING_ADDENDUM)
    source_local_payload = load_json(SOURCE_LOCAL_COLD_EVIDENCE)
    brep = brep_payload.get("parts", {})
    meshes = mesh_payload.get("solids", {})
    if not isinstance(brep, dict) or not isinstance(meshes, dict):
        raise GateError("GEOMETRY_MANIFEST_SCHEMA_FAIL", "B-rep or mesh manifest lacks its object map")
    expected_all = set(PHYSICAL_LABELS) | {AGGREGATE_LABEL}
    if set(brep) != expected_all or set(meshes) != expected_all:
        raise GateError("GEOMETRY_LABEL_SET_FAIL", "B-rep/mesh label sets are not exactly 000..057", {"brep_missing": sorted(expected_all - set(brep)), "brep_extra": sorted(set(brep) - expected_all), "mesh_missing": sorted(expected_all - set(meshes)), "mesh_extra": sorted(set(meshes) - expected_all)})
    # This file is a full-top/world witness.  Its jaw axis/origin are retained
    # only as hash-pinned provenance and are never compared with source-local
    # body coordinates.  A world-to-link transform is intentionally absent,
    # so using any of these fields for mapping is fail-closed by construction.
    historical_world_jaw = binding_payload.get("jaw_axis", {})
    if not isinstance(historical_world_jaw, dict):
        raise GateError("HISTORICAL_WORLD_JAW_SCHEMA_FAIL", "historical world-jaw provenance is not an object")

    source_result = source_local_payload.get("result", {})
    source_cold = source_result.get("cold_facts", {}) if isinstance(source_result, dict) else {}
    source_save = source_result.get("save", {}) if isinstance(source_result, dict) else {}
    recorded_local_bbox = [float(value) for value in source_cold.get("bounding_box_mm", [])]
    if (
        source_local_payload.get("status") != "B5_0_NATIVE_BUILD_PASS"
        or source_result.get("group") != "G08"
        or source_result.get("accepted_link") != "gripper_link"
        or int(source_cold.get("solid_body_count", -1)) != SOURCE_EXPECTED_SW_BODY_COUNT
        or source_save.get("sha256") != SOURCE_PART_SHA256
        or int(source_save.get("bytes", -1)) != SOURCE_PART_BYTES
        or len(recorded_local_bbox) != 6
        or max(abs(a - b) for a, b in zip(recorded_local_bbox, SOURCE_LOCAL_COLD_BBOX_MM)) > 1.0e-9
    ):
        raise GateError("SOURCE_LOCAL_COLD_AUTHORITY_FAIL", "canonical G08 cold evidence does not bind the exact source SLDPRT/link-6-local bbox", {"source_result": source_result, "expected_bbox_mm": list(SOURCE_LOCAL_COLD_BBOX_MM)})

    addendum = addendum_payload.get("m3r_addendum", {})
    records = addendum.get("resolution_records", []) if isinstance(addendum, dict) else []
    hash_by_label: Dict[str, str] = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        label = Path(str(row.get("resolved_path", "")).replace("\\", "/")).stem
        digest = str(row.get("sha256", "")).upper()
        if label in expected_all:
            if label in hash_by_label and hash_by_label[label] != digest:
                raise GateError("STL_HASH_DUPLICATE_FAIL", "addendum carries conflicting hashes for one STL", {"label": label})
            hash_by_label[label] = digest
    if set(hash_by_label) != expected_all:
        raise GateError("STL_HASH_COVERAGE_FAIL", "fixed addendum does not hash all 58 historical STL objects", {"missing": sorted(expected_all - set(hash_by_label)), "extra": sorted(set(hash_by_label) - expected_all)})

    physical: Dict[str, Dict[str, Any]] = {}
    stl_audits: List[Dict[str, Any]] = []
    for label in PHYSICAL_LABELS:
        mesh = meshes[label]
        brep_item = brep[label]
        stl_path = Path(str(mesh.get("path", "")).replace("\\", "/"))
        actual_hash = sha256(stl_path) if stl_path.is_file() else None
        expected_hash = hash_by_label[label]
        stl_row = {"label": label, "path": posix(stl_path), "exists": stl_path.is_file(), "expected_sha256": expected_hash, "actual_sha256": actual_hash, "pass": actual_hash == expected_hash}
        stl_audits.append(stl_row)
        if not stl_row["pass"]:
            raise GateError("STL_HASH_FAIL", "a physical per-solid STL drifted", stl_row)
        mesh_volume = float(mesh.get("volume_mm3", 0.0))
        brep_volume = float(brep_item.get("volume_mm3", 0.0))
        mesh_faces = int(mesh.get("n_faces", -1))
        brep_faces = int(brep_item.get("n_faces", -2))
        if not volume_matches(mesh_volume, brep_volume) or mesh_faces != brep_faces or int(brep_item.get("n_solids", 0)) != 1:
            raise GateError("BREP_MESH_SIGNATURE_FAIL", "per-object B-rep and mesh manifests disagree", {"label": label, "mesh_volume_mm3": mesh_volume, "brep_volume_mm3": brep_volume, "mesh_faces": mesh_faces, "brep_faces": brep_faces, "n_solids": brep_item.get("n_solids")})
        # The mesh/B-rep object was extracted from a full-top deployed STEP.
        # Its coordinate-bearing fields are explicitly nested as non-mapping
        # evidence.  Only volume may corroborate the source-local cold B-rep
        # mapping below; STEP face topology (2362 total) is not the native
        # SLDPRT face topology (1798 total) and is never a per-body match key.
        world_metrics = bbox_metrics(mesh.get("box_mm", []))
        stl_centroid = binary_stl_mass_centroid(stl_path)
        physical[label] = {
            "label": label,
            "volume_mm3": mesh_volume,
            "step_brep_faces": mesh_faces,
            "full_top_world_nonmapping": {
                **world_metrics,
                "stl_mass_centroid_mm": stl_centroid["mass_centroid_mm"],
                "disposition": FULL_TOP_WORLD_EVIDENCE_DISPOSITION,
            },
            "stl_triangle_count": stl_centroid["triangle_count"],
            "stl_sha256": actual_hash,
            "stl_path": posix(stl_path),
        }

    aggregate_mesh = meshes[AGGREGATE_LABEL]
    aggregate_brep = brep[AGGREGATE_LABEL]
    aggregate_path = Path(str(aggregate_mesh.get("path", "")).replace("\\", "/"))
    aggregate_hash = sha256(aggregate_path) if aggregate_path.is_file() else None
    if aggregate_hash != hash_by_label[AGGREGATE_LABEL]:
        raise GateError("AGGREGATE_STL_HASH_FAIL", "aggregate-wrapper STL drifted", {"path": posix(aggregate_path), "expected_sha256": hash_by_label[AGGREGATE_LABEL], "actual_sha256": aggregate_hash})
    physical_volume = sum(item["volume_mm3"] for item in physical.values())
    physical_faces = sum(item["step_brep_faces"] for item in physical.values())
    union_box = [min(item["full_top_world_nonmapping"]["bbox_mm"][index] for item in physical.values()) for index in range(3)] + [max(item["full_top_world_nonmapping"]["bbox_mm"][index] for item in physical.values()) for index in range(3, 6)]
    aggregate_box = [float(value) for value in aggregate_mesh.get("box_mm", [])]
    aggregate_proof = {
        "label": AGGREGATE_LABEL,
        "classification": "AGGREGATE_WRAPPER_NOT_PHYSICAL_BODY",
        "physical_child_count": len(physical),
        "physical_children_volume_mm3": physical_volume,
        "aggregate_volume_mm3": float(aggregate_mesh.get("volume_mm3", 0.0)),
        "volume_delta_mm3": float(aggregate_mesh.get("volume_mm3", 0.0)) - physical_volume,
        "physical_children_step_faces": physical_faces,
        "aggregate_step_faces": int(aggregate_mesh.get("n_faces", -1)),
        "physical_union_bbox_mm": union_box,
        "aggregate_mesh_bbox_mm": aggregate_box,
        "bbox_is_physical_union": len(aggregate_box) == 6 and max(abs(a - b) for a, b in zip(union_box, aggregate_box)) <= 1.0e-4,
        "step_brep_n_solids": int(aggregate_brep.get("n_solids", 0)),
        "stl_path": posix(aggregate_path),
        "stl_sha256": aggregate_hash,
        "copy_authorized": False,
        "reason": "FreeCAD object-tree aggregate repeats the 000..056 geometry; copying it would overlap all children and double mass",
    }
    if len(physical) != 57 or abs(aggregate_proof["volume_delta_mm3"]) > 1.0 or physical_faces != aggregate_proof["aggregate_step_faces"] or not aggregate_proof["bbox_is_physical_union"]:
        raise GateError("AGGREGATE_WRAPPER_PROOF_FAIL", "057 does not satisfy the fixed aggregate-wrapper proof", aggregate_proof)
    _GEOMETRY_CACHE = {
        "physical": physical,
        "aggregate": aggregate_proof,
        "stl_audits": stl_audits,
        "source_local_authority": {
            "path": posix(SOURCE_LOCAL_COLD_EVIDENCE),
            "sha256": SOURCE_LOCAL_COLD_EVIDENCE_SHA256,
            "source_sldprt_sha256": SOURCE_PART_SHA256,
            "source_frame": "LINK6_LOCAL",
            "solid_body_count": SOURCE_EXPECTED_SW_BODY_COUNT,
            "cold_bbox_mm": recorded_local_bbox,
            "mapping_authority": LOCAL_MAPPING_AUTHORITY,
        },
        "full_top_world_evidence": {
            "disposition": FULL_TOP_WORLD_EVIDENCE_DISPOSITION,
            "historical_world_jaw_present": bool(historical_world_jaw),
            "world_to_link_transform_used_for_mapping": False,
        },
        "source_step": {"path": posix(SOURCE_STEP), "bytes": SOURCE_STEP_BYTES, "sha256": SOURCE_STEP_SHA256},
        "generation_logic": {
            "r3d": "enumerated every FreeCAD STEP object whose label matched the gripper prefix, including compound wrapper 057",
            "r3e": "consumed that 58-object manifest without detecting object-tree aggregation",
            "correction": "physical SolidWorks IPartDoc.GetBodies2 count is authoritative; accept only rows 000..056",
        },
    }
    return _GEOMETRY_CACHE


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
    geometry = load_geometry_contract()
    groups: Dict[str, List[Dict[str, Any]]] = {key: [] for key in GROUPS}
    seen: Dict[str, str] = {}
    physical_seen: set[str] = set()
    aggregate_seen = False
    with ASSIGNMENT_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"solid", "assigned_body", "volume_mm3", "faces", "s_on_jaw_axis_mm", "u_min_mm", "u_max_mm"}
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
                historical_s = float(raw["s_on_jaw_axis_mm"])
                historical_u_min = float(raw["u_min_mm"])
                historical_u_max = float(raw["u_max_mm"])
            except (TypeError, ValueError) as exc:
                raise GateError("CSV_NUMERIC_FAIL", "face/volume/jaw field is invalid", {"row": row_number, "body": name}) from exc
            if not all(math.isfinite(value) for value in (volume, historical_s, historical_u_min, historical_u_max)) or volume <= 0.0 or faces <= 0 or historical_u_min > historical_u_max:
                raise GateError("CSV_NUMERIC_RANGE_FAIL", "face/volume field is not positive finite", {"body": name, "volume_mm3": volume, "faces": faces})
            seen[normalized] = name
            if name == AGGREGATE_LABEL:
                aggregate_seen = True
                aggregate = geometry["aggregate"]
                if group != "gripper_link" or faces != int(aggregate["aggregate_step_faces"]) or not mapping_volume_matches(volume, float(aggregate["aggregate_volume_mm3"])):
                    raise GateError("CSV_AGGREGATE_SIGNATURE_FAIL", "historical 057 row no longer matches the fixed aggregate wrapper", {"row": row_number, "group": group, "volume_mm3": volume, "faces": faces, "aggregate": aggregate})
                continue
            if name not in geometry["physical"] or name not in set(PHYSICAL_LABELS):
                raise GateError("CSV_PHYSICAL_LABEL_FAIL", "CSV physical row is outside 000..056", {"body": name})
            expected_geometry = geometry["physical"][name]
            if faces != int(expected_geometry["step_brep_faces"]) or not volume_matches(volume, float(expected_geometry["volume_mm3"])):
                raise GateError("CSV_GEOMETRY_SIGNATURE_FAIL", "CSV row no longer matches its fixed STEP/STL object", {"body": name, "csv_volume_mm3": volume, "csv_faces": faces, "geometry": expected_geometry})
            item = {
                "source_name": name,
                "normalized_name": normalized,
                "assigned_body": group,
                "volume_mm3": volume,
                "faces": faces,
                "historical_full_top_world_nonmapping": {
                    "jaw_s_mm": historical_s,
                    "jaw_u_min_mm": historical_u_min,
                    "jaw_u_max_mm": historical_u_max,
                    "disposition": FULL_TOP_WORLD_EVIDENCE_DISPOSITION,
                },
                "geometry": expected_geometry,
                "row": row_number,
            }
            groups[group].append(item)
            physical_seen.add(name)
    if len(seen) != 58 or not aggregate_seen or physical_seen != set(PHYSICAL_LABELS):
        raise GateError("CSV_ROW_COUNT_FAIL", "assignment CSV must contain 57 physical rows 000..056 plus aggregate wrapper 057", {"total_count": len(seen), "physical_count": len(physical_seen), "aggregate_seen": aggregate_seen, "missing_physical": sorted(set(PHYSICAL_LABELS) - physical_seen), "extra_physical": sorted(physical_seen - set(PHYSICAL_LABELS))})
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
            "historical_step_face_count": sum(int(item["faces"]) for item in items),
            "historical_csv_volume_mm3": round(sum(float(item["volume_mm3"]) for item in items), 6),
            "source_names": [item["source_name"] for item in items],
        }
        for key, items in groups.items()
    }


def audit_expected_mapping_uniqueness(groups: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    contracts = [item for items in groups.values() for item in items]
    labels = [normalize_body_name(item["source_name"]) for item in contracts]
    if len(contracts) != SOURCE_EXPECTED_SW_BODY_COUNT or len(set(labels)) != len(labels) or set(item["source_name"] for item in contracts) != set(PHYSICAL_LABELS):
        raise GateError("EXPECTED_MAPPING_LABEL_SET_FAIL", "local-fingerprint contract labels are not exactly the 57 physical source identities", {"count": len(contracts), "unique_normalized": len(set(labels))})
    return {
        "physical_contracts": len(contracts),
        "exact_source_label_set": True,
        "runtime_local_fingerprint_uniqueness_required": False,
        "mapping_authority": LOCAL_MAPPING_AUTHORITY,
        "mapping_fields": [
            "volume_mm3",
            "link6_local_mass_centroid_y_sign",
            "link6_local_mass_centroid_y_magnitude_vs_csv_jaw_station",
            "link6_local_bbox_mm",
            "link6_local_mass_centroid_mm",
            "native_face_count",
        ],
        "mapping_rules": {
            "left_y_sign": "gripper_left bodies have link6-local Y < 0",
            "right_y_sign": "gripper_right bodies have link6-local Y > 0",
            "station_scale": "csv jaw station s == -link6_local_y for small/pin bodies; sign-only for the two large finger-body classes",
            "volume_tolerance_mm3": MAPPING_VOLUME_ABS_TOL_MM3,
            "station_tolerance_mm": MAPPING_STATION_TOL_MM,
            "waiver": {
                "label": MAPPING_VOLUME_WAIVER_LABEL,
                "delta_mm3": MAPPING_VOLUME_WAIVER_DELTA_MM3,
                "reason": "frozen CSV/STEP row 013 volume 2096.062 vs frozen source SLDPRT body 2098.960; documented donor geometry deviation, no L0 mass override",
            },
            "interchangeable_ties": "same-volume same-station bodies inside one assigned-body group are geometrically interchangeable; bijection resolved by enumeration order",
        },
        "full_top_world_bbox_centroid_jaw_mapping_authorized": False,
        "fingerprint_round_decimals": LOCAL_FINGERPRINT_DECIMALS,
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
        "source_local_cold_evidence_sha256": SOURCE_LOCAL_COLD_EVIDENCE_SHA256,
        "assignment_csv_sha256": ASSIGNMENT_CSV_SHA256,
        "source_step_sha256": SOURCE_STEP_SHA256,
        "brep_probe_sha256": BREP_PROBE_SHA256,
        "mesh_manifest_sha256": MESH_MANIFEST_SHA256,
        "historical_binding_sha256": HISTORICAL_BINDING_SHA256,
        "m3r_binding_addendum_sha256": M3R_BINDING_ADDENDUM_SHA256,
        "predecessor_r0_script_sha256": PREDECESSOR_R0_SCRIPT_COPY_SHA256,
        "predecessor_r1_script_sha256": PREDECESSOR_R1_SCRIPT_COPY_SHA256,
        "predecessor_r2_script_sha256": PREDECESSOR_R2_SCRIPT_COPY_SHA256,
        "part_template_sha256": PART_TEMPLATE_SHA256,
        "physical_body_count": 57,
        "aggregate_exclusion": {"label": AGGREGATE_LABEL, "classification": "AGGREGATE_WRAPPER_NOT_PHYSICAL_BODY", "copy_authorized": False},
        "solid_body_gate_api": "IBody2.GetType()==swSolidBody(0)",
        "copy_api": "IBody2.Copy2(True)",
        "insert_api": "IPartDoc.CreateFeatureFromBody3(body,False,1)",
        "source_frame": "LINK6_LOCAL",
        "mapping_authority": LOCAL_MAPPING_AUTHORITY,
        "full_top_world_coordinate_fields_used_for_mapping": False,
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
        payload.get("schema") == "F3R2_V5_LOOP1C0_PART_CHECKPOINT_V3_LINK6_LOCAL_FINGERPRINT"
        and payload.get("group") == key
        and payload.get("binding") == expected
        and fact.get("path") == posix(target)
        and fact.get("sha256") == sha256(target)
        and fact.get("bytes") == target.stat().st_size
        and payload.get("verdict") == "V5_LOOP1C0_57_PHYSICAL_NATIVE_PART_CHECKPOINT_PASS"
    )
    row["state"] = "RESUME_REQUIRES_COLD_REOPEN" if passed else "HOLD_CHECKPOINT_BINDING_FAIL"
    return row


def static_audit() -> Dict[str, Any]:
    fixed = audit_fixed_inputs()
    geometry = load_geometry_contract()
    groups = read_assignment()
    uniqueness = audit_expected_mapping_uniqueness(groups)
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
        "schema": "F3R2_V5_LOOP1C0_STATIC_AUDIT_V3_LINK6_LOCAL_FINGERPRINT",
        "timestamp_utc": utc_now(),
        "script": {"path": posix(Path(__file__)), "bytes": Path(__file__).stat().st_size, "sha256": sha256(Path(__file__))},
        "fixed_inputs": fixed,
        "assignment": assignment_summary(groups),
        "geometry_evidence": {
            "physical_body_count": len(geometry["physical"]),
            "physical_stl_hashes_verified": len(geometry["stl_audits"]),
            "source_step": geometry["source_step"],
            "aggregate_exclusion": geometry["aggregate"],
            "generation_logic": geometry["generation_logic"],
            "mapping_uniqueness": uniqueness,
            "source_local_authority": geometry["source_local_authority"],
            "full_top_world_evidence": geometry["full_top_world_evidence"],
            "runtime_solidworks_anchor": {"physical_body_count": SOURCE_EXPECTED_SW_BODY_COUNT, "total_face_count": SOURCE_EXPECTED_SW_FACE_COUNT, "total_volume_mm3": SOURCE_EXPECTED_SW_VOLUME_MM3, "aggregate_body_present": False},
        },
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
    body_type = int(base.value(body, "GetType"))
    if body_type != SW_BODY_SOLID:
        raise GateError(
            "BODY_NOT_SOLID",
            "IBody2.GetType() did not return swSolidBody",
            {"body": body_name(body), "actual_body_type": body_type, "expected_swSolidBody": SW_BODY_SOLID},
        )
    faces = int(base.value(body, "GetFaceCount"))
    mass = [float(value) for value in base.as_list(body.GetMassProperties(1.0))]
    if len(mass) < 4 or not all(math.isfinite(value) for value in mass[:4]) or mass[3] <= 0.0:
        raise GateError("BODY_MASS_PROPERTIES_FAIL", "IBody2.GetMassProperties did not return a positive volume", {"body": body_name(body), "mass_properties": mass})
    raw_box = [float(value) * 1000.0 for value in base.as_list(base.value(body, "GetBodyBox"))]
    metrics = bbox_metrics(raw_box)
    return {
        "name": body_name(body),
        "faces": faces,
        "volume_mm3": mass[3] * 1.0e9,
        "mass_centroid_mm": [mass[index] * 1000.0 for index in range(3)],
        **metrics,
        "body_type": body_type,
        "solid": True,
    }


MAPPING_VOLUME_WAIVER_LABEL = BODY_LABEL_PREFIX + "013"
MAPPING_VOLUME_WAIVER_DELTA_MM3 = 2.898039
MAPPING_VOLUME_WAIVER_TOL_MM3 = 0.01
MAPPING_STATION_TOL_MM = 0.60
MAPPING_LEFT_Y_SIGN = -1.0
MAPPING_LARGE_BODY_SIGN_ONLY_VOLUMES = {22535.34, 5588.088, 10223.294, 3135.677}
MAPPING_TIE_RESIDUAL_DELTA_MM = 0.05


def canonical_source_label(reported_name: str) -> str:
    """Non-authoritative provenance alias resolver (always fails closed).

    The frozen source SLDPRT bodies were imported through the SolidWorks STEP
    translator and carry "Open CASCADE STEP translator ..." names instead of
    the B50/B51 physical labels.  Label-based mapping is therefore impossible
    and the R4 fingerprint assignment below is the mapping authority.
    """
    raise GateError(
        "SOURCE_LOCAL_LABEL_FAIL",
        "source SLDPRT body does not carry an exact B50/B51 LINKLOCAL physical label; "
        "the frozen donor exposes STEP-translator body names, so B-rep fingerprint "
        "assignment is the mapping authority",
        {"reported_name": reported_name},
    )


def source_station_match(facts: Dict[str, Any], contract: Dict[str, Any]) -> Tuple[bool, float, str]:
    """Local-Y mirror-station rule:
    LEFT bodies sit at Y < 0 and RIGHT bodies at Y > 0 in the link-6-local
    frame; the CSV jaw station s is the negative of local Y for small/pin
    bodies.  The two large finger-body classes and the two mirror knuckle
    classes are matched by sign only because their CSV s is an extreme-station.
    """
    y = float(facts["mass_centroid_mm"][1])
    role = str(contract["assigned_body"])
    if role == "gripper_left" and y >= -1.0e-4:
        return False, float("nan"), "LEFT_Y_SIGN"
    if role == "gripper_right" and y <= 1.0e-4:
        return False, float("nan"), "RIGHT_Y_SIGN"
    s = float(contract["historical_full_top_world_nonmapping"]["jaw_s_mm"])
    if round(float(contract["volume_mm3"]), 3) in MAPPING_LARGE_BODY_SIGN_ONLY_VOLUMES:
        return True, 0.0, "SIGN_ONLY_LARGE_BODY"
    if abs(s) > 1.0:
        residual = abs(abs(y) - abs(s))
        return residual <= MAPPING_STATION_TOL_MM, residual, "STATION_MAGNITUDE"
    residual = abs(y)
    return residual <= MAPPING_STATION_TOL_MM, residual, "PALM_NEAR_CENTER"


def source_volume_match(facts: Dict[str, Any], contract: Dict[str, Any]) -> Tuple[bool, float]:
    actual = float(facts["volume_mm3"])
    expected = float(contract["geometry"]["volume_mm3"])
    if mapping_volume_matches(actual, expected):
        return True, 0.0
    if str(contract["source_name"]) == MAPPING_VOLUME_WAIVER_LABEL:
        delta = abs(actual - expected)
        if abs(delta - MAPPING_VOLUME_WAIVER_DELTA_MM3) <= MAPPING_VOLUME_WAIVER_TOL_MM3:
            return True, delta
    return False, abs(actual - expected)


def map_source_bodies(model: Any, groups: Dict[str, List[Dict[str, Any]]], types: Any, pythoncom: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    part = base.wrap(model, "IPartDoc", types, pythoncom)
    raw_bodies = base.as_list(part.GetBodies2(0, False))
    if len(raw_bodies) != SOURCE_EXPECTED_SW_BODY_COUNT:
        raise GateError("SOURCE_BODY_COUNT_FAIL", "source part must expose exactly 57 physical solid bodies", {"count": len(raw_bodies), "expected": SOURCE_EXPECTED_SW_BODY_COUNT, "aggregate_excluded": AGGREGATE_LABEL})
    expected = {item["normalized_name"]: item for items in groups.values() for item in items}
    if len(expected) != SOURCE_EXPECTED_SW_BODY_COUNT or set(expected) != {normalize_body_name(label) for label in PHYSICAL_LABELS}:
        raise GateError("EXPECTED_MAPPING_LABEL_SET_FAIL", "local-fingerprint contract labels are not exactly the 57 physical source identities")
    observed_bodies: List[Tuple[Any, Dict[str, Any], Dict[str, Any]]] = []
    for raw in raw_bodies:
        body = base.wrap(raw, "IBody2", types, pythoncom)
        facts = body_evidence(body)
        observed_bodies.append((body, facts, local_fingerprint(facts)))
    contracts = [item for items in groups.values() for item in items]

    edges: List[Tuple[int, int, float, float, str]] = []
    for cidx, contract in enumerate(contracts):
        for bidx, (_body, facts, _fingerprint) in enumerate(observed_bodies):
            volume_ok, volume_residual = source_volume_match(facts, contract)
            if not volume_ok:
                continue
            station_ok, station_residual, station_kind = source_station_match(facts, contract)
            if not station_ok:
                continue
            edges.append((cidx, bidx, volume_residual, station_residual, station_kind))
    edges.sort(key=lambda edge: (edge[2], edge[3], edge[0], edge[1]))
    adjacency: Dict[int, List[int]] = {cidx: [] for cidx in range(len(contracts))}
    for cidx, bidx, _v, _s, _k in edges:
        adjacency[cidx].append(bidx)

    contract_match: Dict[int, int] = {}
    body_match: Dict[int, int] = {}

    def augment(cidx: int, visited: set[int]) -> bool:
        for bidx in adjacency[cidx]:
            if bidx in visited:
                continue
            visited.add(bidx)
            if bidx not in body_match or augment(body_match[bidx], visited):
                contract_match[cidx] = bidx
                body_match[bidx] = cidx
                return True
        return False

    for cidx in range(len(contracts)):
        augment(cidx, set())
    if len(contract_match) != len(contracts) or len(body_match) != len(observed_bodies):
        missing_contracts = [contracts[cidx]["source_name"] for cidx in range(len(contracts)) if cidx not in contract_match]
        missing_bodies = [bidx for bidx in range(len(observed_bodies)) if bidx not in body_match]
        raise GateError(
            "SOURCE_LOCAL_FINGERPRINT_MAPPING_FAIL",
            "B-rep fingerprint assignment did not cover all 57 labels and 57 bodies exactly once",
            {"missing_contracts": missing_contracts, "missing_bodies": missing_bodies, "edge_count": len(edges)},
        )

    mapped: Dict[str, Any] = {}
    evidence: List[Dict[str, Any]] = []
    for cidx, bidx in contract_match.items():
        contract = contracts[cidx]
        body, facts, fingerprint = observed_bodies[bidx]
        match_edges = [edge for edge in edges if edge[0] == cidx and edge[1] == bidx]
        volume_residual = match_edges[0][2] if match_edges else float("nan")
        station_residual = match_edges[0][3] if match_edges else float("nan")
        station_kind = match_edges[0][4] if match_edges else "UNKNOWN"
        alternatives = [
            edge[1]
            for edge in edges
            if edge[0] == cidx
            and edge[1] != bidx
            and abs(edge[2] - volume_residual) <= 1.0e-3
            and abs(edge[3] - station_residual) <= MAPPING_TIE_RESIDUAL_DELTA_MM
        ]
        for alternative_bidx in alternatives:
            alternative_contracts = [contracts[c] for c, b in contract_match.items() if b == alternative_bidx]
            if alternative_contracts and str(alternative_contracts[0]["assigned_body"]) != str(contract["assigned_body"]):
                raise GateError(
                    "SOURCE_LOCAL_TIE_CROSS_GROUP_FAIL",
                    "a geometrically interchangeable alternative crosses the frozen assigned-body group",
                    {"contract": contract["source_name"], "body_enum": bidx, "alternative_body_enum": alternative_bidx, "alternative_contract": alternative_contracts[0]["source_name"]},
                )
        normalized = contract["normalized_name"]
        runtime = {
            **facts,
            "mapped_source_name": contract["source_name"],
            "local_brep_fingerprint": fingerprint,
            "source_enum_index": bidx,
            "volume_residual_mm3": volume_residual,
            "station_residual_mm": station_residual,
            "station_rule": station_kind,
            "geometrically_interchangeable_alternatives": alternatives,
            "mapping_authority": LOCAL_MAPPING_AUTHORITY,
        }
        contract["runtime"] = runtime
        mapped[normalized] = body
        evidence.append({
            **runtime,
            "assigned_body": contract["assigned_body"],
            "historical_csv_volume_mm3": contract["volume_mm3"],
            "historical_step_faces": contract["faces"],
            "full_top_world_coordinate_fields_used": False,
            "waiver": (
                {
                    "label": MAPPING_VOLUME_WAIVER_LABEL,
                    "delta_mm3": round(volume_residual, 6),
                    "reason": "frozen CSV/STEP row 013 records 2096.062 mm3 while the frozen source SLDPRT body measures 2098.960 mm3; the +2.898039 mm3 delta is a documented donor geometry deviation, not an L0 mass override",
                }
                if str(contract["source_name"]) == MAPPING_VOLUME_WAIVER_LABEL
                else None
            ),
        })
    if set(mapped) != set(expected):
        raise GateError("SOURCE_BODY_COVERAGE_FAIL", "57 physical source bodies do not cover CSV/STL rows 000..056 exactly once", {"missing": sorted(set(expected) - set(mapped)), "extra": sorted(set(mapped) - set(expected))})
    actual_faces = sum(int(row["faces"]) for row in evidence)
    actual_volume = sum(float(row["volume_mm3"]) for row in evidence)
    if actual_faces != SOURCE_EXPECTED_SW_FACE_COUNT or abs(actual_volume - SOURCE_EXPECTED_SW_VOLUME_MM3) > SOURCE_TOTAL_VOLUME_TOL_MM3:
        raise GateError("SOURCE_SW_TOTAL_SIGNATURE_FAIL", "SolidWorks 57-body B-rep total face/volume signature drifted", {"actual_faces": actual_faces, "expected_faces": SOURCE_EXPECTED_SW_FACE_COUNT, "actual_volume_mm3": actual_volume, "expected_volume_mm3": SOURCE_EXPECTED_SW_VOLUME_MM3, "volume_tolerance_mm3": SOURCE_TOTAL_VOLUME_TOL_MM3})
    local_bbox = union_bbox_mm(evidence)
    bbox_delta = max(abs(actual - expected_value) for actual, expected_value in zip(local_bbox, SOURCE_LOCAL_COLD_BBOX_MM))
    if bbox_delta > SOURCE_LOCAL_BBOX_TOL_MM:
        raise GateError("SOURCE_LOCAL_COLD_BBOX_FAIL", "source SLDPRT cold body union does not match the canonical G08 link-6-local bbox", {"actual_bbox_mm": local_bbox, "expected_bbox_mm": list(SOURCE_LOCAL_COLD_BBOX_MM), "max_abs_delta_mm": bbox_delta, "tolerance_mm": SOURCE_LOCAL_BBOX_TOL_MM})
    return mapped, sorted(evidence, key=lambda row: row["mapped_source_name"])


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
        "SOURCE_PHYSICAL_SOLID_TOTAL": "57",
        "AGGREGATE_WRAPPER_EXCLUDED": AGGREGATE_LABEL,
        "AGGREGATE_CLASSIFICATION": "AGGREGATE_WRAPPER_NOT_PHYSICAL_BODY",
        "GEOMETRY_BINDING": LOCAL_MAPPING_AUTHORITY,
        "SOURCE_FRAME": "LINK6_LOCAL",
        "FULL_TOP_WORLD_COORDINATE_MAPPING": "PROHIBITED",
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
        runtime = contract.get("runtime")
        if not isinstance(runtime, dict):
            raise GateError("TARGET_RUNTIME_AUTHORITY_MISSING", "source runtime geometry was not established before target audit", {"source_name": contract["source_name"]})
        if facts["name"] != contract["semantic_name"]:
            raise GateError("TARGET_BODY_SPELLING_FAIL", "target semantic body name did not persist exactly", {"actual": facts["name"], "expected": contract["semantic_name"]})
        copy_deltas = {
            "volume_mm3": abs(float(facts["volume_mm3"]) - float(runtime["volume_mm3"])),
            "bbox_max_abs_mm": max(abs(float(a) - float(b)) for a, b in zip(facts["bbox_mm"], runtime["bbox_mm"])),
            "mass_centroid_distance_mm": vector_distance(facts["mass_centroid_mm"], runtime["mass_centroid_mm"]),
        }
        if (
            facts["faces"] != int(runtime["faces"])
            or not volume_matches(facts["volume_mm3"], float(runtime["volume_mm3"]))
            or copy_deltas["bbox_max_abs_mm"] > 1.0e-4
            or copy_deltas["mass_centroid_distance_mm"] > 1.0e-4
        ):
            raise GateError("TARGET_BODY_GEOMETRY_FAIL", "target body does not conserve its exact live SolidWorks source body", {"actual": facts, "runtime_source": runtime, "copy_deltas": copy_deltas})
        actual[normalized] = {**facts, "mapped_source_name": contract["source_name"], "copy_deltas": copy_deltas}
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
            # The feature-managed body name follows the feature name in a
            # SolidWorks multibody part, so the feature carries the semantic
            # body name directly (PALM_SOLID_01__B51_...).  IBody2.Name on a
            # feature-managed body is not persistent across re-enumeration.
            feature.Name = contract["semantic_name"]
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
        "schema": "F3R2_V5_LOOP1C0_PART_CHECKPOINT_V3_LINK6_LOCAL_FINGERPRINT",
        "timestamp_utc": utc_now(),
        "group": key,
        "role": GROUPS[key]["role"],
        "binding": binding(),
        "target": {"path": posix(target), "bytes": target.stat().st_size, "sha256": sha256(target)},
        "result": result,
        "cold_reopen": cold,
        "verdict": "V5_LOOP1C0_57_PHYSICAL_NATIVE_PART_CHECKPOINT_PASS",
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
    runtime_items = [item for items in groups.values() for item in items]
    if any(not isinstance(item.get("runtime"), dict) for item in runtime_items):
        raise GateError("CONSERVATION_RUNTIME_AUTHORITY_MISSING", "source runtime geometry is missing during three-part conservation")
    expected_faces = sum(int(item["runtime"]["faces"]) for item in runtime_items)
    expected_volume = sum(float(item["runtime"]["volume_mm3"]) for item in runtime_items)
    historical_step_faces = sum(int(item["faces"]) for item in runtime_items)
    historical_csv_volume = sum(float(item["volume_mm3"]) for item in runtime_items)
    passed = body_count == 57 and face_count == expected_faces == SOURCE_EXPECTED_SW_FACE_COUNT and recorded_names == expected_names and len(recorded_names) == 57 and volume_matches(volume, expected_volume)
    evidence = {
        "body_count": body_count,
        "expected_body_count": 57,
        "face_count": face_count,
        "expected_live_solidworks_face_count": expected_faces,
        "historical_step_object_face_count_not_used_for_copy_gate": historical_step_faces,
        "volume_mm3": volume,
        "expected_live_solidworks_volume_mm3": expected_volume,
        "historical_csv_physical_volume_mm3_not_used_for_copy_gate": historical_csv_volume,
        "source_name_union_count": len(recorded_names),
        "source_name_union_exact": recorded_names == expected_names,
        "aggregate_wrapper_exclusion": {"label": AGGREGATE_LABEL, "classification": "AGGREGATE_WRAPPER_NOT_PHYSICAL_BODY", "copied": False},
        "pass": passed,
    }
    if not passed:
        raise GateError("THREE_PART_CONSERVATION_FAIL", "cold-reopened three-part union does not conserve the 57 physical SolidWorks bodies", evidence)
    return evidence


def source_local_cold_witness(model: Any, evidence: Sequence[Dict[str, Any]], types: Any, pythoncom: Any) -> Dict[str, Any]:
    bbox = union_bbox_mm(evidence)
    bbox_delta = max(abs(actual - expected) for actual, expected in zip(bbox, SOURCE_LOCAL_COLD_BBOX_MM))
    interconnect = base.feature_names_3d_interconnect(model, types, pythoncom)
    external = int(base.external_reference_count(model, "Loop1C0:GRIPPER_SOURCE_LINK6_LOCAL"))
    auxiliary = int(base.auxiliary_reference_count(model, "Loop1C0:GRIPPER_SOURCE_LINK6_LOCAL"))
    fingerprint_hashes = [str(row.get("local_brep_fingerprint", {}).get("sha256", "")) for row in evidence]
    if (
        len(evidence) != SOURCE_EXPECTED_SW_BODY_COUNT
        or len(set(fingerprint_hashes)) != SOURCE_EXPECTED_SW_BODY_COUNT
        or "" in fingerprint_hashes
        or bbox_delta > SOURCE_LOCAL_BBOX_TOL_MM
        or interconnect
        or external != 0
        or auxiliary != 0
    ):
        raise GateError("SOURCE_LOCAL_COLD_WITNESS_FAIL", "source link-6-local cold B-rep witness is incomplete or externally linked", {"body_count": len(evidence), "unique_fingerprint_count": len(set(fingerprint_hashes)), "bbox_mm": bbox, "canonical_bbox_mm": list(SOURCE_LOCAL_COLD_BBOX_MM), "bbox_delta_mm": bbox_delta, "three_d_interconnect_features": interconnect, "external_reference_count": external, "auxiliary_reference_count": auxiliary})
    return {
        "method": "SOLIDWORKS_COLD_BREP_BBOX_AND_DATUM_WITNESS",
        "cold_reopen_pass": True,
        "read_only": True,
        "source_frame": "LINK6_LOCAL",
        "source_path": posix(SOURCE_PART),
        "source_sha256": SOURCE_PART_SHA256,
        "canonical_cold_evidence": {"path": posix(SOURCE_LOCAL_COLD_EVIDENCE), "sha256": SOURCE_LOCAL_COLD_EVIDENCE_SHA256},
        "source_bbox_mm": bbox,
        "canonical_bbox_mm": list(SOURCE_LOCAL_COLD_BBOX_MM),
        "bbox_max_abs_delta_mm": bbox_delta,
        "solid_body_count": len(evidence),
        "face_count": sum(int(row["faces"]) for row in evidence),
        "volume_mm3": sum(float(row["volume_mm3"]) for row in evidence),
        "unique_local_fingerprint_count": len(set(fingerprint_hashes)),
        "mapping_authority": LOCAL_MAPPING_AUTHORITY,
        "three_d_interconnect_features": interconnect,
        "external_reference_count": external,
        "auxiliary_reference_count": auxiliary,
        "full_top_world_coordinate_fields_used": False,
    }


def gripper_frame_contract(results: Dict[str, Dict[str, Any]], source_witness: Dict[str, Any]) -> Dict[str, Any]:
    targets: Dict[str, Dict[str, Any]] = {}
    target_external = 0
    for key, spec in GROUPS.items():
        row = results[key]
        cold = row.get("cold_reopen_now") if row.get("mode") == "RESUMED" else row.get("cold_reopen")
        facts = cold.get("facts") if isinstance(cold, dict) else None
        if not isinstance(facts, dict):
            raise GateError("GRIPPER_FRAME_PART_COLD_MISSING", "a gripper part lacks a current cold-reopen witness", {"group": key})
        if int(facts.get("external_reference_count", -1)) != 0 or int(facts.get("auxiliary_reference_count", -1)) != 0 or facts.get("three_d_interconnect_features"):
            raise GateError("GRIPPER_FRAME_PART_REFERENCE_FAIL", "a gripper part is not independently native", {"group": key, "facts": facts})
        target = Path(spec["target"])
        targets[spec["role"]] = {"path": posix(target), "bytes": target.stat().st_size, "sha256": sha256(target), "cold_brep": facts}
        target_external += int(facts["external_reference_count"])
    bbox = [float(value) for value in source_witness["source_bbox_mm"]]
    return {
        "schema": "F3R2_V5_NATIVE_FRAME_CONTRACT_V1_PART_SET",
        "source_frame": "LINK6_LOCAL",
        "placement": "LIVE_LINK6_TOTAL_TRANSFORM",
        "source_path": posix(SOURCE_PART),
        "source_sha256": SOURCE_PART_SHA256,
        "source_bbox_mm": bbox,
        "target_kind": "THREE_NATIVE_PART_SET",
        "target_paths": {role: row["path"] for role, row in targets.items()},
        "target_sha256": {role: row["sha256"] for role, row in targets.items()},
        "mapping_authority": LOCAL_MAPPING_AUTHORITY,
        "witness": {
            "method": "SOLIDWORKS_COLD_BREP_BBOX_AND_DATUM_WITNESS",
            "cold_reopen_pass": True,
            "external_reference_count": target_external,
            "auxiliary_reference_count": 0,
            "frame_rationale": "The exact G08 source SLDPRT is cold-opened read-only and fingerprinted wholly in link-6-local coordinates; the three copied native parts conserve that local B-rep and must receive the live nested link-6 transform only at top assembly.",
            "source_cold_brep": source_witness,
            "target_part_cold_reopens": targets,
            "full_top_world_coordinate_fields_used": False,
        },
    }


def manifest_text() -> str:
    paths = [Path(GROUPS[key]["target"]) for key in GROUPS] + [SCRIPT_COPY]
    return "".join(f"{sha256(path)}  {path.relative_to(RUN_ROOT).as_posix()}\n" for path in sorted(paths, key=lambda item: item.as_posix()))


def audit_physical_stl_hashes_now(geometry: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for label, item in sorted(geometry["physical"].items()):
        path = Path(str(item["stl_path"]))
        actual = sha256(path) if path.is_file() else None
        row = {"label": label, "path": posix(path), "expected_sha256": item["stl_sha256"], "actual_sha256": actual, "pass": actual == item["stl_sha256"]}
        rows.append(row)
    if not all(row["pass"] for row in rows):
        raise GateError("PHYSICAL_STL_POST_HASH_FAIL", "one or more fixed 000..056 STL witnesses drifted during execution", {"rows": rows})
    return rows


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
        geometry = load_geometry_contract()
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
        expected_pid = int(sbin.resolve_pid(receipt_pid))
        if int(session["pid"]) != expected_pid:
            raise GateError("SESSION_B_PID_FAIL", "attached SolidWorks is not the fixed Loop-1 Session B process", {"actual": session["pid"], "expected": expected_pid})

        source_raw = source_model = None
        source_title = ""
        source_witness: Dict[str, Any] = {}
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
            source_witness = source_local_cold_witness(source_model, source_evidence, types, pythoncom)

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
        frame_contract = gripper_frame_contract(results, source_witness)
        if sha256(SOURCE_PART) != SOURCE_PART_SHA256 or SOURCE_PART.stat().st_size != SOURCE_PART_BYTES or sha256(ASSIGNMENT_CSV) != ASSIGNMENT_CSV_SHA256:
            raise GateError("SOURCE_POST_IDENTITY_FAIL", "source part or assignment CSV drifted during transaction")
        fixed_post = audit_fixed_inputs()
        physical_stl_post = audit_physical_stl_hashes_now(geometry)
        protected_post = base.audit_protected()

        if FINAL_MANIFEST.exists() or FINAL_RECEIPT.exists():
            raise GateError("FINAL_WRITE_ONCE_EXISTS", "final Loop1C0 manifest/receipt already exists")
        FINAL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with FINAL_MANIFEST.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(manifest_text())
        final = {
            "schema": "F3R2_V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT_V3_LINK6_LOCAL_FINGERPRINT",
            "timestamp_start_utc": start,
            "timestamp_end_utc": utc_now(),
            "run_root": posix(RUN_ROOT),
            "binding": binding(),
            "session": session,
            "memory_gate_gib": memory_samples,
            "source_open": {"path": posix(SOURCE_PART), "read_only": True, "source_frame": "LINK6_LOCAL", "physical_body_count": 57, "actual_face_count": sum(int(row["faces"]) for row in source_evidence), "actual_volume_mm3": sum(float(row["volume_mm3"]) for row in source_evidence), "source_bbox_mm": source_witness["source_bbox_mm"], "mapping_authority": LOCAL_MAPPING_AUTHORITY, "full_top_world_coordinate_fields_used": False, "cold_witness": source_witness, "evidence": source_evidence},
            "assignment": assignment_summary(groups),
            "aggregate_exclusion": geometry["aggregate"],
            "historical_generation_logic_correction": geometry["generation_logic"],
            "parts": results,
            "conservation": conserved,
            "frame_contracts": {"GRIPPER": frame_contract},
            "protected_pre": protected_pre,
            "protected_post": protected_post,
            "fixed_inputs_post": fixed_post,
            "physical_stl_hashes_post": physical_stl_post,
            "manifest": {"path": posix(FINAL_MANIFEST), "bytes": FINAL_MANIFEST.stat().st_size, "sha256": sha256(FINAL_MANIFEST)},
            "scope_completed": "1C0_THREE_NATIVE_PARTS",
            "remaining_hold": [
                "1C1_NATIVE_GRIPPER_ASSEMBLY",
                "1C1_TWO_GUIDE_COINCIDENT_PLUS_ADVANCED_LIMIT_DISTANCE_PER_FINGER",
                "1C1_CLOSED_PREGRASP_OPEN_CONFIGURATION_PROOF",
                "1C1_TRANSFORM_CLEARANCE_INTERFERENCE_REFERENCE_AND_MATE_LEDGER",
            ],
            "no_slider_type_23_claim": True,
            "verdict": "V5_LOOP1C0_57_PHYSICAL_BODIES_THREE_NATIVE_GRIPPER_PARTS_PASS_ASSEMBLY_HOLD",
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
            "schema": "F3R2_V5_LOOP1C0_FAILURE_RECEIPT_V3_LINK6_LOCAL_FINGERPRINT",
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
