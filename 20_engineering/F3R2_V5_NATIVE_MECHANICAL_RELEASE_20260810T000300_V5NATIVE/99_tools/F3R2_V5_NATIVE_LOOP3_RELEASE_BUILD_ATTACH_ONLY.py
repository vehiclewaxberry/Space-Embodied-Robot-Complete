#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F3R2 V5 Loop-3 R2B native release builder and fresh-session verifier.

This program is deliberately attach-only.  It never creates, starts, stops or
terminates a SOLIDWORKS process.  ``audit`` and ``self-test`` are filesystem
only.  ``build-session-a`` and ``verify-session-b`` require an explicit live
PID plus the exact G0 receipt and SHA-256 for that PID; both attach through the
hash-pinned GetActiveObject-only helper and require an empty SW2024 SP05
session.  Session B must be a different process from Session A.

The program is a release operation, not a mechanical redesign.  It reads the
write-once Loop1E dependency ledger, creates release evidence in an isolated
attempt tree, cold-verifies it, writes a precommit, and promotes with Windows
no-replace moves.  It never changes the accepted B601 URDF, q authority,
joint topology, link lengths, inertial truth, P9 CAD or the Loop1E top CAD.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
RUN_ROOT = ENGINEERING / "F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
TOOLS = RUN_ROOT / "99_tools"
VALIDATION = RUN_ROOT / "13_validation"
RELEASE = RUN_ROOT / "14_release"

SCRIPT = Path(__file__).resolve()
BASE_HELPER = TOOLS / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_SHA256 = "E44BC52CFBDECCC107E361ACB0EDD993EFC46248EB663A994564B77BDA30F906"
LOOP1E_SCRIPT = TOOLS / "F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py"
LOOP1E_SCRIPT_SHA256 = "1F8E83AC067A2C4218BCECADBD192A68D55D09A2DC2C4B896E1BD475141B0419"
LOOP2_SCRIPT = TOOLS / "F3R2_V5_NATIVE_LOOP2_MOTION_ROBOTICS_ATTACH_ONLY.py"
LOOP2_SCRIPT_SHA256 = "D5C56071D2D79E1EB6E93622A552C156662BB1D6C98721A3403FA3865A50A050"

LOOP1E_RECEIPT = VALIDATION / "V5_LOOP1E_TOP_ASSEMBLY_RECEIPT.json"
LOOP2_RECEIPT = VALIDATION / "V5_LOOP2_R2B_NATIVE_CLEARANCE_RECEIPT.json"
# Fail-closed registration gates.  Patch each once, after its immutable receipt
# exists.  None is never a wildcard and never authorizes Session A.
LOOP1E_RECEIPT_SHA256: Optional[str] = None  # TBD_BIND_AFTER_WRITE_ONCE
LOOP2_RECEIPT_SHA256: Optional[str] = None  # TBD_BIND_AFTER_WRITE_ONCE

TOP = RUN_ROOT / "03_top_assembly/SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM"
ACCEPTED_URDF = ENGINEERING / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"

P9_ROOT = VALIDATION / "solar_r2_attempts/20260813T123100Z_P9E9"
P9_FRESH = P9_ROOT / "evidence/F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_PASS.json"
P9_FRESH_SHA256 = "1E4AC41F97317F0D16A8113CCDA79117B4AC08A026F9E5ED39E0F64E569EA753"
P9_PROMOTION = VALIDATION / "V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT.json"
P9_PROMOTION_SHA256 = "71952A7AC8761D59BB4596381C1DABD873AE2EFD0B7B8F502A0A95187349A334"
P9_LEFT = P9_ROOT / "cad/sides/L_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM"
P9_LEFT_SHA256 = "4074EC7906FFE0BB029311006A1E771D343F31512D36A081BAFA44CFB410E29B"
P9_RIGHT = P9_ROOT / "cad/sides/R_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM"
P9_RIGHT_SHA256 = "C11335A47CB1A04B0D8B7DD1559DF0C8EEB0D482CA0DDC6C2E29448BD464CB48"

DIGITAL_PROMOTION_RECEIPT = VALIDATION / "V5_DIGITAL_THREAD_SOLAR_R2B_PROMOTION_RECEIPT.json"
DIGITAL_PROMOTION_RECEIPT_SHA256 = "B2AF30DC9C5177EDDE41C5E46D147B32E85996C4317A811CA138AB4A41AA1256"
DIGITAL_PROMOTION_MANIFEST = RELEASE / "V5_DIGITAL_THREAD_SOLAR_R2B_MANIFEST_SHA256.txt"
DIGITAL_PROMOTION_MANIFEST_SHA256 = "52227DC3B9F5E67F14AED1F8939386EF1C2DA3C7A942EEA1BA7591887C19ABC8"
DIGITAL_STATE_MACHINE = RUN_ROOT / "09_digital_thread/V5_MECHANICAL_STATE_MACHINE_R2.yaml"
DIGITAL_STATE_MACHINE_SHA256 = "37ABA1A6CA520A4EBB348D87449BFA0E35EFD2EB5A1879F379C4A99BD4C81125"
DIGITAL_SOLAR_ANNEX = RUN_ROOT / "09_digital_thread/V5_SOLAR_ARRAY_THREAD_ANNEX_R2B.yaml"
DIGITAL_SOLAR_ANNEX_SHA256 = "966E2F521B26CF09AF53DCEA2C9E78F914B2E08BE3DF760FF29108F25885021D"
DIGITAL_SOLAR_REGISTER = RUN_ROOT / "04_configurations/V5_SOLAR_STATE_REGISTER.csv"
DIGITAL_SOLAR_REGISTER_SHA256 = "41AEBC461286B893021747267E9ECDE065A188376685D1A7F1955646F3355D6B"

LOOP2_RESULTS_JSON = RUN_ROOT / "05_clearance/V5_LOOP2_R2B_NATIVE_CLEARANCE_RESULTS.json"
LOOP2_RESULTS_CSV = RUN_ROOT / "05_clearance/V5_LOOP2_R2B_NATIVE_CLEARANCE_RESULTS.csv"
LOOP2_CHECKPOINT = VALIDATION / "V5_LOOP2_R2B_CLEARANCE_CHECKPOINT.json"
LOOP2_MANIFEST = RELEASE / "V5_LOOP2_R2B_NATIVE_CLEARANCE_MANIFEST_SHA256.txt"

DRAWING_TEMPLATE = Path(r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\gb_a3.drwdot")
DRAWING_TEMPLATE_SHA256 = "B376D09B3937C02A57B6496D24F55FF0637243F7FAD215987F9E57610B10210E"
SHEET_FORMAT = Path(r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\lang\Chinese-Simplified\sheetformat\a3 - gb.slddrt")
SHEET_FORMAT_SHA256 = "ED0133F69A8A1701CF2A3D71E2712E64076CCC28E644493B975029BE1ADD4C63"
PACK_AND_GO_DEVIATION_EVIDENCE = ENGINEERING / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/01_asset_selection/F3R1_PACK_AND_GO_PROOF.json"
PACK_AND_GO_DEVIATION_EVIDENCE_SHA256 = "5D84B2305982FB02CF24B9824B8326A1AEFF2C948D4FE26E656262878F3208F0"

TOP_CONFIGS = (
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
    "SOLAR_DEPLOY_ARM_LOCKED",
    "HDRM_RELEASE",
    "SERVICE",
    "RELEASE_CLEAR_END_STATE",
)
SOLAR_STATES = TOP_CONFIGS[:7]
AUTHORIZED_Q = ("Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY")

LEGACY_SOLAR_DENY_PATHS = (
    RUN_ROOT / "02_native_subassemblies/LEFT_WING_ROOT_TRUE_HINGE.SLDASM",
    RUN_ROOT / "02_native_subassemblies/RIGHT_WING_ROOT_TRUE_HINGE.SLDASM",
    RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_WING_PANEL_PHYSICAL.SLDPRT",
    RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_WING_PANEL_PHYSICAL.SLDPRT",
)

DRAWING_SPECS: Tuple[Dict[str, Any], ...] = (
    {"id": "01_STAGE_A", "name": "01_STAGE_A_INTERFACE_RING", "source": RUN_ROOT / "01_native_parts/adapter/B601_INTERFACE_STAGE_A_REV_B2.SLDPRT", "sha256": "FC84FBBA450A3C975B1AFA798CF37C492AB2680251BA906FBC1FA383800C1978", "configurations": ("默认",), "scope": "INTERFACE_RING"},
    {"id": "02_STAGE_B", "name": "02_STAGE_B_LOAD_ADAPTER", "source": RUN_ROOT / "01_native_parts/adapter/B601_LOAD_ADAPTER_STAGE_B_REV_B2.SLDPRT", "sha256": "AC85890EF29FCC3D5C6FAD87E0255BBAC03256B9EA9FA561092B6CF6CB1BE085", "configurations": ("默认",), "scope": "LOAD_ADAPTER"},
    {"id": "03_G07", "name": "03_G07_PRIMARY_SUPPORT", "source": RUN_ROOT / "01_native_parts/supports/G07_PRIMARY_SUPPORT_V2.SLDPRT", "sha256": "BBD45CCFA724453ABE1AC92E30F59545B454D24D6462671EB655D5753D2FD964", "configurations": ("默认",), "scope": "PRIMARY_SUPPORT"},
    {"id": "04_G08", "name": "04_G08_PRIMARY_SUPPORT", "source": RUN_ROOT / "01_native_parts/supports/G08_PRIMARY_SUPPORT_V2.SLDPRT", "sha256": "C52244E9B262E8C8C448AE1DCEFF1A3F9A2FC6AC16253BF8DF844B59AB56E8E8", "configurations": ("默认",), "scope": "PRIMARY_SUPPORT"},
    {"id": "05_MID", "name": "05_MID_BACKUP_SUPPORT", "source": RUN_ROOT / "01_native_parts/supports/MID_BACKUP_SUPPORT_V2.SLDPRT", "sha256": "5CE735DC17CEB0EC89C83FA5760AB095DDC33C18455A5D1F24E298A6081E9A57", "configurations": ("默认",), "scope": "BACKUP_SUPPORT"},
    {"id": "06_HDRM", "name": "06_HDRM_FUNCTIONAL_ENVELOPE", "source": RUN_ROOT / "02_native_subassemblies/ARM_HDRM_FUNCTIONAL_ENVELOPE.SLDASM", "sha256": "32BDAAA648BCC00D0B3CE6AE7F0B00DFB71F835D0541685F137A9CDF77C74261", "configurations": ("LOCKED", "RELEASED"), "scope": "FUNCTIONAL_ENVELOPE"},
    {"id": "07_CAMERA", "name": "07_CAMERA_INTERFACE", "source": RUN_ROOT / "02_native_subassemblies/SERVICE_CAMERA_INTERFACE_HOLD.SLDASM", "sha256": "423524BEA3F4285102BF4CA7E02F639A9976693347D0F7F06FA25D34243E4BF6", "configurations": ("MODEL_SELECTION_HOLD",), "scope": "CAMERA_INTERFACE"},
    {"id": "08_GRIPPER", "name": "08_GRIPPER_INTERFACE", "source": RUN_ROOT / "02_native_subassemblies/B601_GRIPPER.SLDASM", "sha256": "21E74251D58A957A81F659311DFE892B642ED8565B0C26490A95EA8E52459EE4", "configurations": ("OPEN", "PREGRASP", "CLOSED"), "scope": "GRIPPER_INTERFACE"},
    {"id": "09_SOLAR_LEFT", "name": "09_SOLAR_LEFT_R2B_SIDE_STATES", "source": P9_LEFT, "sha256": P9_LEFT_SHA256, "configurations": SOLAR_STATES, "scope": "P9_R2B_SIDE_AND_SEVEN_STATES"},
    {"id": "10_SOLAR_RIGHT", "name": "10_SOLAR_RIGHT_R2B_SIDE_STATES", "source": P9_RIGHT, "sha256": P9_RIGHT_SHA256, "configurations": SOLAR_STATES, "scope": "P9_R2B_SIDE_AND_SEVEN_STATES"},
    {"id": "11_TOP", "name": "11_TOP_GA_CONFIG_EXPLODED_BOM", "source": TOP, "sha256": None, "configurations": TOP_CONFIGS, "scope": "TOP_GA_CONFIG_EXPLODED_DOCUMENTATION_AND_BOM"},
)

EXTERNAL_MASS_ROLES = (
    "B601_BASE_ADAPTER", "G07_SUPPORT", "G08_SUPPORT", "MID_SUPPORT",
    "LEFT_SOLAR_ARRAY", "RIGHT_SOLAR_ARRAY", "GRIPPER", "HDRM", "CAMERA", "HARNESS",
)
EXCLUDED_TRUTH_ROLES = ("SPACECRAFT_PRIMARY", "SPACECRAFT_B601_MOUNT", "ARM")

MASS_CSV = RUN_ROOT / "06_mass_properties/V5_EXTERNAL_MECHANICAL_MASS_PROPERTIES_R2B.csv"
MASS_SUMMARY = RUN_ROOT / "06_mass_properties/V5_EXTERNAL_MECHANICAL_MASS_SUMMARY_R2B.json"
DRAWING_REGISTER = RUN_ROOT / "07_drawings/V5_DRAWING_REGISTER_R2B.csv"
BOM = RUN_ROOT / "08_bom/V5_NATIVE_TOP_BOM_R2B.csv"
FINAL_DIGITAL_THREAD = RUN_ROOT / "09_digital_thread/V5_NATIVE_MECHANICAL_FINAL_THREAD_R2B.json"
FINAL_DIGITAL_MANIFEST = RELEASE / "V5_NATIVE_MECHANICAL_FINAL_THREAD_R2B_MANIFEST_SHA256.txt"
PACK_ROOT = RUN_ROOT / "10_pack_and_go/V5_PACK_AND_GO_R2B"
PACK_TOP = PACK_ROOT / "03_top_assembly/SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM"
PACK_LEDGER = RUN_ROOT / "10_pack_and_go/V5_PACK_AND_GO_R2B_REFERENCE_LEDGER.csv"
PACK_PROOF = RUN_ROOT / "10_pack_and_go/V5_PACK_AND_GO_R2B_PROOF.json"
CLAIMS = RELEASE / "V5_NATIVE_MECHANICAL_RELEASE_CLAIMS_R2B.json"

ATTEMPTS = VALIDATION / "loop3_release_attempts"
PRECOMMIT = VALIDATION / "V5_LOOP3_R2B_RELEASE_BUILD_PRECOMMIT.json"
SESSION_A_CHECKPOINT = VALIDATION / "V5_LOOP3_R2B_RELEASE_SESSION_A_CHECKPOINT.json"
SESSION_B_CHECKPOINT = VALIDATION / "V5_LOOP3_R2B_RELEASE_SESSION_B_CHECKPOINT.json"
ACCEPTANCE_MATRIX = VALIDATION / "V5_LOOP3_R2B_RELEASE_ACCEPTANCE_MATRIX.csv"
FINAL_MANIFEST = RELEASE / "V5_LOOP3_R2B_RELEASE_MANIFEST_SHA256.txt"
FINAL_RECEIPT = VALIDATION / "V5_LOOP3_R2B_RELEASE_RECEIPT.json"

CLASSIFICATION = "COMPETITION_PROTOTYPE_BASELINE"
FINAL_VERDICT = "F3R2_V5_NATIVE_MECHANICAL_BASELINE_CLOSED"
REQUIRED_HOLDS = (
    "LAUNCH_LOAD_HOLD",
    "THERMAL_VACUUM_HOLD",
    "RANDOM_VIBRATION_HOLD",
    "FORMAL_FASTENER_MOS_HOLD",
)
PROHIBITED_CLAIMS = ("FLIGHT_READY", "LAUNCH_QUALIFIED")

SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2
SW_DOC_DRAWING = 3
SW_OPEN_SILENT_READONLY = 3
SW_SAVE_AS_CURRENT_VERSION = 0
SW_SAVE_AS_SILENT = 1

FIXED_INPUTS: Tuple[Tuple[str, Path, str], ...] = (
    ("base_helper", BASE_HELPER, BASE_HELPER_SHA256),
    ("loop1e_final_script", LOOP1E_SCRIPT, LOOP1E_SCRIPT_SHA256),
    ("loop2_final_script", LOOP2_SCRIPT, LOOP2_SCRIPT_SHA256),
    ("accepted_urdf", ACCEPTED_URDF, ACCEPTED_URDF_SHA256),
    ("p9_fresh_new_pid_receipt", P9_FRESH, P9_FRESH_SHA256),
    ("p9_logical_promotion", P9_PROMOTION, P9_PROMOTION_SHA256),
    ("p9_left_side", P9_LEFT, P9_LEFT_SHA256),
    ("p9_right_side", P9_RIGHT, P9_RIGHT_SHA256),
    ("digital_r2b_promotion_receipt", DIGITAL_PROMOTION_RECEIPT, DIGITAL_PROMOTION_RECEIPT_SHA256),
    ("digital_r2b_promotion_manifest", DIGITAL_PROMOTION_MANIFEST, DIGITAL_PROMOTION_MANIFEST_SHA256),
    ("digital_state_machine_r2", DIGITAL_STATE_MACHINE, DIGITAL_STATE_MACHINE_SHA256),
    ("digital_solar_annex_r2b", DIGITAL_SOLAR_ANNEX, DIGITAL_SOLAR_ANNEX_SHA256),
    ("digital_solar_register_r2b", DIGITAL_SOLAR_REGISTER, DIGITAL_SOLAR_REGISTER_SHA256),
    ("drawing_template", DRAWING_TEMPLATE, DRAWING_TEMPLATE_SHA256),
    ("sheet_format", SHEET_FORMAT, SHEET_FORMAT_SHA256),
    ("registered_getpackandgo_deviation_evidence", PACK_AND_GO_DEVIATION_EVIDENCE, PACK_AND_GO_DEVIATION_EVIDENCE_SHA256),
    *((f"drawing_source_{row['id']}", Path(row["source"]), str(row["sha256"])) for row in DRAWING_SPECS if row["sha256"]),
)

MASS_FIELDS = (
    "role", "source_path", "source_sha256", "referenced_configuration", "source_class",
    "mass_kg", "local_com_x_m", "local_com_y_m", "local_com_z_m",
    "world_com_x_m", "world_com_y_m", "world_com_z_m", "world_ixx_kg_m2",
    "world_iyy_kg_m2", "world_izz_kg_m2", "world_ixy_kg_m2", "world_ixz_kg_m2",
    "world_iyz_kg_m2", "total_transform_16", "accepted_urdf_excluded", "scope",
)
DRAWING_FIELDS = (
    "drawing_id", "slddrw_path", "slddrw_sha256", "pdf_path", "pdf_sha256",
    "source_path", "source_sha256", "configurations", "view_count", "sheet_count",
    "scope", "classification", "manufacturing_release", "flight_claim",
)
BOM_FIELDS = (
    "item_no", "level", "parent_occurrence", "component_name2", "quantity", "native_path",
    "native_sha256", "referenced_configuration", "suppression", "source_class", "mass_scope",
    "classification", "holds",
)
PACK_FIELDS = (
    "source_path", "source_sha256_pre", "package_path", "package_sha256_post",
    "source_kind", "from_loop1e_dependency_ledger", "exists", "inside_package",
)
ACCEPTANCE_FIELDS = (
    "gate_id", "status", "release_blocking", "evidence_path", "evidence_sha256", "detail",
)


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Any = None):
        super().__init__(message)
        self.code = code
        self.detail = detail


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def normcase(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


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


def tree_facts(root: Path) -> List[Dict[str, Any]]:
    if not root.is_dir():
        return []
    return [file_fact(path) for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: norm(p).lower())]


def exact_fact(path: Path, expected: str) -> Dict[str, Any]:
    fact = file_fact(path)
    if fact["sha256"] != expected:
        raise GateError("EXACT_INPUT_HASH_FAIL", "hash-pinned input is missing or changed", {"fact": fact, "expected_sha256": expected})
    return fact


def load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise GateError("JSON_READ_FAIL", "cannot parse required JSON", {"path": norm(path), "reason": str(exc)}) from exc
    if not isinstance(payload, dict):
        raise GateError("JSON_OBJECT_REQUIRED", "required JSON root is not an object", {"path": norm(path)})
    return payload


def serialize_json(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def serialize_csv(fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def write_bytes_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    data = serialize_json(payload)  # complete finite serialization precedes file creation
    write_bytes_once(path, data)


def write_text_once(path: Path, value: str) -> None:
    data = value.encode("utf-8")
    write_bytes_once(path, data)


def write_csv_once(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    data = serialize_csv(fields, rows)  # complete serialization precedes file creation
    write_bytes_once(path, data)


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def is_pdf(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 1024:
        return False
    data = path.read_bytes()
    return data.startswith(b"%PDF-") and b"%%EOF" in data[-4096:]


def is_ole(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 512 and path.read_bytes()[:8] == bytes.fromhex("D0CF11E0A1B11AE1")


def path_inside(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved == root_resolved or root_resolved in resolved.parents


def fixed_input_audit() -> List[Dict[str, Any]]:
    rows = []
    for name, path, expected in FIXED_INPUTS:
        fact = file_fact(path)
        rows.append({"name": name, **fact, "expected_sha256": expected, "pass": fact["sha256"] == expected})
    return rows


def validate_loop1e_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    checkpoint = payload.get("checkpoint", {})
    cold = payload.get("cold_reopen", {})
    configs = cold.get("configuration_ledger")
    solar = cold.get("solar_2x7_readback")
    references = cold.get("references", {})
    dependencies = references.get("dependency_paths")
    target = payload.get("target_fact", {})
    script_sha = checkpoint.get("script_sha256") if isinstance(checkpoint, dict) else None
    good = bool(
        payload.get("schema") == "F3R2_V5_LOOP1E_TOP_ASSEMBLY_RECEIPT_V2"
        and payload.get("verdict") == "V5_LOOP1E_NATIVE_TOP_ASSEMBLY_LOOP2_CONTRACT_COLD_REOPEN_PASS"
        and script_sha == LOOP1E_SCRIPT_SHA256
        and isinstance(configs, list)
        and [row.get("configuration") for row in configs] == list(TOP_CONFIGS)
        and isinstance(solar, list)
        and [row.get("configuration") for row in solar] == list(SOLAR_STATES)
        and all(row.get("module_readback_count") == 6 and row.get("angle_dimension_readback_count") == 6 for row in solar)
        and payload.get("top_solar_angle_mate_count") == 0
        and isinstance(dependencies, list) and bool(dependencies)
        and isinstance(target, dict) and target.get("path") == norm(TOP)
        and target.get("sha256") == (sha256(TOP) if TOP.is_file() else None)
    )
    if not good:
        raise GateError("LOOP1E_RECEIPT_SEMANTIC_FAIL", "Loop1E receipt does not prove the exact R2B top contract")
    normalized = sorted(normcase(Path(str(item))) for item in dependencies)
    if len(normalized) != len(set(normalized)):
        raise GateError("LOOP1E_DEPENDENCY_DUPLICATE", "Loop1E dependency ledger is not an exact unique set")
    denied = sorted(set(normalized) & {normcase(path) for path in LEGACY_SOLAR_DENY_PATHS})
    wrong_attempt = [item for item in normalized if path_inside(Path(item), VALIDATION / "solar_r2_attempts") and not path_inside(Path(item), P9_ROOT)]
    if denied or wrong_attempt:
        raise GateError("OLD_SINGLE_PANEL_OR_NON_P9_REFERENCE", "Loop1E dependency ledger reaches denied solar CAD", {"denied": denied, "wrong_attempt": wrong_attempt})
    missing = [item for item in normalized if not Path(item).is_file()]
    if missing:
        raise GateError("LOOP1E_DEPENDENCY_MISSING", "Loop1E exact dependency is missing", {"missing": missing})
    return {"dependency_paths": normalized, "top_sha256": target["sha256"], "configuration_count": len(configs), "solar_state_count": len(solar)}


def validate_loop2_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    facts = ("checkpoint", "clearance_results_json", "clearance_results_csv", "manifest")
    good = bool(
        payload.get("schema") == "F3R2_V5_LOOP2_R2B_NATIVE_CLEARANCE_RECEIPT_V2"
        and payload.get("verdict") == "V5_LOOP2_R2B_NATIVE_CLEARANCE_PASS"
        and payload.get("final_gate_eligible") is True
        and payload.get("overall_gate") == "PASS_R2B_CLEARANCE_TO_LOOP3"
        and payload.get("script", {}).get("sha256") == LOOP2_SCRIPT_SHA256
        and payload.get("exact_top_configurations") == list(TOP_CONFIGS)
        and payload.get("solar_states") == list(SOLAR_STATES)
        and payload.get("authorized_q_order") == list(AUTHORIZED_Q)
        and payload.get("expected_static_cell_count") == 21
        and payload.get("completed_static_cell_count") == 21
        and payload.get("side_configuration_owner") == "SIDE_SLDASM_ONLY"
        and payload.get("top_level_second_driver_count") == 0
        and payload.get("service_grasp_q") is None
        and payload.get("service_grasp_sample_count") == 0
        and payload.get("classification_ceiling") == CLASSIFICATION
        and payload.get("flight_ready") is False
        and payload.get("launch_qualified") is False
    )
    if not good:
        raise GateError("LOOP2_RECEIPT_SEMANTIC_FAIL", "Loop2 receipt is not final-gate-eligible R2B clearance evidence")
    for name in facts:
        fact = payload.get(name, {})
        path = Path(str(fact.get("path", "")))
        if not path.is_file() or fact.get("sha256") != sha256(path):
            raise GateError("LOOP2_RECEIPT_FACT_FAIL", "Loop2 bound output is missing or changed", {"name": name, "fact": fact})
    results = load_json(LOOP2_RESULTS_JSON)
    cells = results.get("static_cells")
    sweep = results.get("continuous_solar_only_sweep", {})
    if (
        results.get("schema") != "F3R2_V5_LOOP2_R2B_NATIVE_CLEARANCE_RESULTS_V2"
        or results.get("final_gate_eligible") is not True
        or not isinstance(cells, list) or len(cells) != 21
        or Counter((row.get("solar_state"), row.get("pose")) for row in cells) != Counter((state, pose) for state in SOLAR_STATES for pose in AUTHORIZED_Q)
        or not all(row.get("pass") is True for row in cells)
        or sweep.get("pass") is not True
    ):
        raise GateError("LOOP2_RESULTS_MATRIX_FAIL", "Loop2 result is not exact 7x3 plus passing solar-only sweep")
    return {"static_cell_count": len(cells), "sweep_segment_count": sweep.get("segment_count"), "minimum_clearance_mm": payload.get("minimum_nonwhitelist_clearance_mm")}


def receipt_audit(stage: str, path: Path, expected: Optional[str]) -> Dict[str, Any]:
    if expected is None:
        return {"stage": stage, **file_fact(path), "expected_sha256": None, "status": "PENDING_HASH_REGISTRATION", "pass": False, "fail_closed": True}
    fact = file_fact(path)
    if fact["sha256"] != expected:
        return {"stage": stage, **fact, "expected_sha256": expected, "status": "FAIL", "pass": False}
    try:
        payload = load_json(path)
        semantic = validate_loop1e_payload(payload) if stage == "LOOP1E" else validate_loop2_payload(payload)
        return {"stage": stage, **fact, "expected_sha256": expected, "status": "PASS", "pass": True, "semantic": semantic}
    except Exception as exc:
        return {"stage": stage, **fact, "expected_sha256": expected, "status": "FAIL", "pass": False, "reason": str(exc), "code": getattr(exc, "code", "RECEIPT_EXCEPTION")}


def final_output_paths() -> List[Path]:
    paths = [MASS_CSV, MASS_SUMMARY, DRAWING_REGISTER, BOM, FINAL_DIGITAL_THREAD, FINAL_DIGITAL_MANIFEST, PACK_LEDGER, PACK_PROOF, CLAIMS]
    for row in DRAWING_SPECS:
        paths.extend((RUN_ROOT / f"07_drawings/{row['name']}.SLDDRW", RUN_ROOT / f"07_drawings/{row['name']}.PDF"))
    return paths


def audit_release_outputs() -> Dict[str, Any]:
    paths = final_output_paths()
    present = [path for path in paths if path.is_file()]
    if not present and not PACK_ROOT.exists():
        return {"status": "PENDING", "pass": False, "missing": [norm(path) for path in paths] + [norm(PACK_ROOT)]}
    missing = [norm(path) for path in paths if not path.is_file()]
    drawing_native = [RUN_ROOT / f"07_drawings/{row['name']}.SLDDRW" for row in DRAWING_SPECS]
    drawing_pdf = [RUN_ROOT / f"07_drawings/{row['name']}.PDF" for row in DRAWING_SPECS]
    bad_native = [norm(path) for path in drawing_native if not is_ole(path)]
    bad_pdf = [norm(path) for path in drawing_pdf if not is_pdf(path)]
    if missing or bad_native or bad_pdf or not PACK_ROOT.is_dir():
        return {"status": "FAIL", "pass": False, "missing": missing, "bad_native": bad_native, "bad_pdf": bad_pdf, "pack_exists": PACK_ROOT.is_dir()}
    try:
        register_fields, register_rows = read_csv(DRAWING_REGISTER)
        bom_fields, bom_rows = read_csv(BOM)
        pack_fields, pack_rows = read_csv(PACK_LEDGER)
        mass_fields, mass_rows = read_csv(MASS_CSV)
        summary = load_json(MASS_SUMMARY)
        proof = load_json(PACK_PROOF)
        claims = load_json(CLAIMS)
        digital = load_json(FINAL_DIGITAL_THREAD)
        good = bool(
            register_fields == list(DRAWING_FIELDS) and len(register_rows) == 11
            and bom_fields == list(BOM_FIELDS) and bool(bom_rows)
            and pack_fields == list(PACK_FIELDS) and bool(pack_rows)
            and mass_fields == list(MASS_FIELDS) and len(mass_rows) == len(EXTERNAL_MASS_ROLES)
            and summary.get("external_mechanical_only") is True and summary.get("accepted_urdf_overwritten") is False
            and proof.get("self_contained") is True and proof.get("missing_reference_count") == 0 and proof.get("escaped_reference_count") == 0
            and claims.get("classification") == CLASSIFICATION and claims.get("mechanical_authoring_after_gate") == "ECR_ONLY"
            and claims.get("holds") == list(REQUIRED_HOLDS)
            and all(claims.get("prohibited_claims", {}).get(name) is False for name in PROHIBITED_CLAIMS)
            and digital.get("schema") == "F3R2_V5_NATIVE_MECHANICAL_FINAL_THREAD_R2B_V1"
            and digital.get("solar_states") == list(SOLAR_STATES) and len(digital.get("state_evidence", [])) == 7
        )
        return {"status": "PASS" if good else "FAIL", "pass": good, "drawing_pair_count": len(register_rows), "bom_row_count": len(bom_rows), "pack_row_count": len(pack_rows), "mass_row_count": len(mass_rows), "facts": [file_fact(path) for path in paths], "pack_tree": tree_facts(PACK_ROOT)}
    except Exception as exc:
        return {"status": "FAIL", "pass": False, "reason": str(exc), "code": getattr(exc, "code", "OUTPUT_AUDIT_EXCEPTION")}


def static_audit() -> Dict[str, Any]:
    fixed = fixed_input_audit()
    loop1e = receipt_audit("LOOP1E", LOOP1E_RECEIPT, LOOP1E_RECEIPT_SHA256)
    loop2 = receipt_audit("LOOP2", LOOP2_RECEIPT, LOOP2_RECEIPT_SHA256)
    outputs = audit_release_outputs()
    hard = [row["name"] for row in fixed if not row["pass"]]
    hard.extend(row["stage"] for row in (loop1e, loop2) if row["status"] == "FAIL")
    pending = [row["stage"] for row in (loop1e, loop2) if row["status"].startswith("PENDING")]
    if hard:
        verdict = "V5_LOOP3_R2B_STATIC_HOLD"
    elif pending:
        verdict = "V5_LOOP3_R2B_PENDING_UPSTREAM_RECEIPT_HASH_BINDING"
    elif outputs["status"] == "PENDING":
        verdict = "V5_LOOP3_R2B_SESSION_A_BUILD_READY"
    elif outputs["status"] == "FAIL":
        verdict = "V5_LOOP3_R2B_STATIC_HOLD"
    elif not SESSION_A_CHECKPOINT.is_file():
        verdict = "V5_LOOP3_R2B_SESSION_A_CHECKPOINT_PENDING"
    elif not SESSION_B_CHECKPOINT.is_file():
        verdict = "V5_LOOP3_R2B_FRESH_SESSION_B_READY"
    elif not FINAL_RECEIPT.is_file():
        verdict = "V5_LOOP3_R2B_FINAL_RECEIPT_PENDING"
    else:
        verdict = FINAL_VERDICT
    return {
        "schema": "F3R2_V5_LOOP3_R2B_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "script": file_fact(SCRIPT),
        "verdict": verdict,
        "fixed_inputs": fixed,
        "upstream": [loop1e, loop2],
        "outputs": outputs,
        "session_a_checkpoint": file_fact(SESSION_A_CHECKPOINT),
        "session_b_checkpoint": file_fact(SESSION_B_CHECKPOINT),
        "final_receipt": file_fact(FINAL_RECEIPT),
        "session_a_execution_authorized": not hard and not pending and outputs["status"] == "PENDING",
        "session_b_execution_authorized": not hard and not pending and outputs["pass"] and SESSION_A_CHECKPOINT.is_file() and not SESSION_B_CHECKPOINT.exists(),
        "hard_failures": hard,
        "pending_hash_bindings": pending,
        "classification_ceiling": CLASSIFICATION,
        "holds": list(REQUIRED_HOLDS),
        "mechanical_authoring_after_gate": "ECR_ONLY",
        "solidworks_connection_attempted": False,
    }


def self_test() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    try:
        serialize_json({"bad": float("nan")})
        checks["nan_rejected_before_create"] = False
    except ValueError:
        checks["nan_rejected_before_create"] = True
    checks["exact_11_top_configurations"] = len(TOP_CONFIGS) == 11 and len(set(TOP_CONFIGS)) == 11
    checks["exact_7_side_states"] = len(SOLAR_STATES) == 7 and TOP_CONFIGS[:7] == SOLAR_STATES
    checks["exact_11_drawings"] = len(DRAWING_SPECS) == 11 and len({row["id"] for row in DRAWING_SPECS}) == 11
    checks["wing_root_drawing_removed"] = all("WING_ROOT" not in str(row["id"]) for row in DRAWING_SPECS)
    checks["top_drawing_present"] = DRAWING_SPECS[-1]["scope"] == "TOP_GA_CONFIG_EXPLODED_DOCUMENTATION_AND_BOM"
    checks["receipt_tbd_is_fail_closed"] = receipt_audit("LOOP1E", LOOP1E_RECEIPT, None)["status"] == "PENDING_HASH_REGISTRATION"
    checks["classification_boundary"] = CLASSIFICATION == "COMPETITION_PROTOTYPE_BASELINE" and FINAL_VERDICT == "F3R2_V5_NATIVE_MECHANICAL_BASELINE_CLOSED"
    checks["required_holds"] = REQUIRED_HOLDS == ("LAUNCH_LOAD_HOLD", "THERMAL_VACUUM_HOLD", "RANDOM_VIBRATION_HOLD", "FORMAL_FASTENER_MOS_HOLD")
    checks["external_mass_roles_partition"] = not set(EXTERNAL_MASS_ROLES) & set(EXCLUDED_TRUTH_ROLES)
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    banned_imports = {"subprocess"}
    imports = {alias.name.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    banned_attrs = {"Exit" + "App"}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    checks["no_process_start_stop_import"] = not (imports & banned_imports)
    checks["no_solidworks_exit_call"] = not (attrs & banned_attrs)
    checks["write_once_helpers_present"] = all(name in {node.name for node in tree.body if isinstance(node, ast.FunctionDef)} for name in ("write_json_once", "write_csv_once", "promote_no_replace"))
    checks["registered_equivalent_packaging_declared"] = (
        "REGISTERED_EQUIVALENT_PACK_AND_GO" in SCRIPT.read_text(encoding="utf-8")
        and "D-F3R1-01_GETPACKANDGO_GENERATED_BINDING_UNAVAILABLE" in SCRIPT.read_text(encoding="utf-8")
    )
    return {"schema": "F3R2_V5_LOOP3_R2B_SELF_TEST_V1", "timestamp_utc": utc_now(), "checks": checks, "pass": all(checks.values()), "solidworks_connection_attempted": False, "filesystem_mutated": False, "verdict": "V5_LOOP3_R2B_SELF_TEST_PASS" if all(checks.values()) else "V5_LOOP3_R2B_SELF_TEST_FAIL"}


def validate_execution_g0(expected_pid: int, receipt_path: Path, expected_sha256: str) -> Dict[str, Any]:
    receipt_path = receipt_path.resolve()
    wanted = expected_sha256.strip().upper()
    if expected_pid <= 0 or not re.fullmatch(r"[0-9A-F]{64}", wanted):
        raise GateError("G0_ARGUMENT_FAIL", "execution requires a positive PID and exact SHA-256")
    fact = exact_fact(receipt_path, wanted)
    payload = load_json(receipt_path)
    process = payload.get("session_b_process", {})
    post = payload.get("solidworks_post", {})
    temporary = payload.get("temporary_asset", {})
    if not (
        payload.get("schema") == "F3R2_V5_G0_SMOKE_SESSION_B_V1"
        and payload.get("verdict") == "G0_SOLIDWORKS_NATIVE_EXECUTION_READY"
        and int(process.get("pid", -1)) == expected_pid
        and int(process.get("major", -1)) == 32
        and str(process.get("revision", "")).startswith("32.5.")
        and process.get("doc_count_pre") == 0
        and process.get("active_doc_is_null_pre") is True
        and post.get("doc_count") == 0
        and post.get("active_doc_is_null") is True
        and temporary.get("deleted") is True
        and temporary.get("exists_after_delete") is False
    ):
        raise GateError("G0_RECEIPT_SEMANTIC_FAIL", "G0 receipt does not bind the requested empty Session-B process", {"receipt": fact, "process": process, "post": post})
    import psutil
    try:
        live = psutil.Process(expected_pid)
        created = float(live.create_time())
        executable = Path(live.exe()).resolve()
    except Exception as exc:
        raise GateError("G0_PID_NOT_LIVE", "explicit G0 process is not live", {"pid": expected_pid, "reason": str(exc)}) from exc
    if Path(str(process.get("executable", ""))).resolve() != executable:
        raise GateError("G0_EXECUTABLE_DRIFT", "live executable differs from G0 receipt", {"live": norm(executable), "receipt": process.get("executable")})
    return {
        "schema": "F3R2_V5_LOOP3_EXPLICIT_G0_BINDING_V1",
        "receipt": fact,
        "expected_pid": expected_pid,
        "process_create_time_epoch": created,
        "process_create_time_utc": datetime.fromtimestamp(created, timezone.utc).isoformat(),
        "session_b_process": dict(process),
        "solidworks_post": dict(post),
        "temporary_asset": dict(temporary),
    }


def attach_explicit_empty(execution_g0: Mapping[str, Any]) -> Tuple[Any, Any, Any, Dict[str, Any]]:
    sw, types, pythoncom, session = base.attach_empty_session()
    expected_pid = int(execution_g0["expected_pid"])
    if int(session["pid"]) != expected_pid:
        raise GateError("LIVE_PID_BINDING_FAIL", "GetActiveObject attached to a process other than the explicit G0 PID", {"live": session, "expected_pid": expected_pid})
    receipted = execution_g0["session_b_process"]
    if (
        str(session["revision"]) != str(receipted["revision"])
        or int(session["major"]) != int(receipted["major"])
        or Path(str(session["executable"])).resolve() != Path(str(receipted["executable"])).resolve()
        or int(session["document_count"]) != 0
        or session["active_doc_is_null"] is not True
    ):
        raise GateError("LIVE_SESSION_FACT_FAIL", "attached session differs from explicit G0 facts", {"live": session, "receipted": receipted})
    import psutil
    process = psutil.Process(expected_pid)
    created = float(process.create_time())
    session = {
        **dict(session),
        "process_create_time_epoch": created,
        "process_create_time_utc": datetime.fromtimestamp(created, timezone.utc).isoformat(),
        "process_name": process.name(),
    }
    if abs(created - float(execution_g0["process_create_time_epoch"])) > 1.0e-6:
        raise GateError("LIVE_PROCESS_CREATION_TIME_FAIL", "live PID was reused after G0 validation", {"live": created, "g0": execution_g0["process_create_time_epoch"]})
    return sw, types, pythoncom, session


def close_owned(sw: Any) -> None:
    guard = 0
    while int(base.value(sw, "GetDocumentCount")) > 0 and guard < 500:
        model = base.value(sw, "ActiveDoc")
        if model is None:
            break
        sw.CloseDoc(str(base.value(model, "GetTitle")))
        guard += 1
    if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
        raise GateError("DOCUMENT_CLEANUP_FAIL", "owned SOLIDWORKS documents remain open", {"document_count": int(base.value(sw, "GetDocumentCount"))})


def doc_type_for(path: Path) -> int:
    suffix = path.suffix.upper()
    if suffix == ".SLDPRT":
        return SW_DOC_PART
    if suffix == ".SLDASM":
        return SW_DOC_ASSEMBLY
    if suffix == ".SLDDRW":
        return SW_DOC_DRAWING
    raise GateError("DOC_TYPE_UNSUPPORTED", "unsupported SOLIDWORKS document suffix", {"path": norm(path)})


def open_read_only(sw: Any, path: Path, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    before = file_fact(path)
    raw, outs = base.unpack(sw.OpenDoc6(str(path), doc_type_for(path), SW_OPEN_SILENT_READONLY, "", 0, 0))
    errors = int(outs[0]) if outs else 0
    warnings = int(outs[1]) if len(outs) > 1 else 0
    if raw is None or errors != 0:
        raise GateError("READ_ONLY_OPEN_FAIL", "SOLIDWORKS read-only open failed", {"path": norm(path), "errors": errors, "warnings": warnings})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    if int(base.value(model, "GetType")) != doc_type_for(path):
        raise GateError("READ_ONLY_OPEN_TYPE_FAIL", "opened document type differs from suffix", {"path": norm(path)})
    return model, {"path": norm(path), "sha256_before": before["sha256"], "errors": errors, "warnings": warnings, "read_only": True}


def close_model(sw: Any, model: Any) -> None:
    sw.CloseDoc(str(base.value(model, "GetTitle")))


def dependencies(model: Any) -> List[str]:
    raw = base.as_list(model.GetDependencies2(False, True, False))
    if len(raw) % 2:
        raise GateError("DEPENDENCY_ARRAY_SHAPE_FAIL", "GetDependencies2 returned an odd array", {"count": len(raw)})
    return sorted(normcase(Path(str(raw[index + 1]))) for index in range(0, len(raw), 2))


def configuration_names(model: Any) -> List[str]:
    return [str(value) for value in base.as_list(base.value(model, "GetConfigurationNames"))]


def show_configuration(model: Any, name: str) -> None:
    raw = model.ShowConfiguration2(name)
    ok, _outs = base.unpack(raw)
    if not bool(ok) or not bool(model.ForceRebuild3(True)):
        raise GateError("CONFIGURATION_ACTIVATE_FAIL", "cannot activate/rebuild required configuration", {"configuration": name})


def component_path(component: Any) -> Path:
    value = str(base.value(component, "GetPathName"))
    if not value:
        raise GateError("COMPONENT_PATH_EMPTY", "component occurrence has no source path", {"name2": str(base.value(component, "Name2"))})
    return Path(value).resolve()


def component_name2(component: Any) -> str:
    value = str(base.value(component, "Name2"))
    if not value:
        raise GateError("COMPONENT_NAME_EMPTY", "component occurrence has no Name2")
    return value


def top_role_paths(loop1e: Mapping[str, Any]) -> Dict[str, Path]:
    try:
        raw = loop1e["checkpoint"]["build"]["components"]
    except Exception as exc:
        raise GateError("LOOP1E_ROLE_LEDGER_MISSING", "Loop1E receipt lacks checkpoint.build.components") from exc
    if not isinstance(raw, dict):
        raise GateError("LOOP1E_ROLE_LEDGER_SHAPE", "Loop1E role ledger is not an object")
    roles = {str(role): Path(str(row["path"])).resolve() for role, row in raw.items()}
    expected = set(EXTERNAL_MASS_ROLES) | set(EXCLUDED_TRUTH_ROLES)
    if set(roles) != expected:
        raise GateError("LOOP1E_ROLE_SET_FAIL", "Loop1E top role set differs from exact release partition", {"actual": sorted(roles), "expected": sorted(expected)})
    if roles["LEFT_SOLAR_ARRAY"] != P9_LEFT.resolve() or roles["RIGHT_SOLAR_ARRAY"] != P9_RIGHT.resolve():
        raise GateError("LOOP1E_P9_ROLE_FAIL", "Loop1E solar roles are not the promoted P9 sides")
    return roles


def top_level_components(model: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    rows = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(True))]
    by_path: Dict[str, Any] = {}
    for row in rows:
        key = normcase(component_path(row))
        if key in by_path:
            raise GateError("TOP_LEVEL_PATH_DUPLICATE", "top has duplicate source paths where roles require uniqueness", {"path": key})
        by_path[key] = row
    return by_path


def matrix3(values: Sequence[float]) -> List[List[float]]:
    if len(values) != 9:
        raise GateError("MATRIX3_SHAPE_FAIL", "expected nine matrix values", {"count": len(values)})
    return [[float(values[0]), float(values[1]), float(values[2])], [float(values[3]), float(values[4]), float(values[5])], [float(values[6]), float(values[7]), float(values[8])]]


def transpose(a: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[float(a[j][i]) for j in range(len(a))] for i in range(len(a[0]))]


def matmul(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[sum(float(a[i][k]) * float(b[k][j]) for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def matvec(a: Sequence[Sequence[float]], value: Sequence[float]) -> List[float]:
    return [sum(float(row[index]) * float(value[index]) for index in range(len(value))) for row in a]


def parse_moi(raw: Sequence[Any]) -> List[List[float]]:
    values = [float(item) for item in raw]
    if len(values) == 9:
        result = matrix3(values)
        return [[0.5 * (result[i][j] + result[j][i]) for j in range(3)] for i in range(3)]
    if len(values) == 6:
        ixx, iyy, izz, ixy, ixz, iyz = values
        return [[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]]
    raise GateError("MASS_MOI_SHAPE_FAIL", "mass property inertia has unsupported shape", {"count": len(values), "values": values})


def component_transform(component: Any) -> Tuple[List[List[float]], List[float], List[float]]:
    transform = base.value(component, "GetTotalTransform", False)
    if transform is None:
        raise GateError("COMPONENT_TRANSFORM_NULL", "GetTotalTransform(False) returned null", {"name2": component_name2(component)})
    values = [float(value) for value in base.as_list(base.value(transform, "ArrayData"))]
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise GateError("COMPONENT_TRANSFORM_FAIL", "component TotalTransform is not a finite 16-vector", {"name2": component_name2(component), "values": values})
    # SOLIDWORKS ArrayData stores the three basis vectors as consecutive columns.
    rotation = [[values[0], values[3], values[6]], [values[1], values[4], values[7]], [values[2], values[5], values[8]]]
    translation = values[9:12]
    scale = values[12]
    if abs(scale - 1.0) > 1.0e-9:
        raise GateError("COMPONENT_SCALE_FAIL", "release component transform has non-unit scale", {"name2": component_name2(component), "scale": scale})
    return rotation, translation, values


def component_mass_fact(component: Any, role: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_model = base.value(component, "GetModelDoc2")
    if raw_model is None:
        raise GateError("MASS_COMPONENT_MODEL_NULL", "resolved external component has no model", {"role": role})
    model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
    configuration = str(base.value(component, "ReferencedConfiguration"))
    show_configuration(model, configuration)
    extension = base.value(model, "Extension")
    try:
        mass_property = base.value(extension, "CreateMassProperty2")
    except Exception:
        mass_property = base.value(extension, "CreateMassProperty")
    if mass_property is None:
        raise GateError("MASS_PROPERTY_NULL", "CreateMassProperty returned null", {"role": role})
    try:
        mass_property.UseSystemUnits = True
    except Exception:
        pass
    try:
        mass_property.Recalculate()
    except Exception:
        pass
    mass = float(base.value(mass_property, "Mass"))
    com_local = [float(item) for item in base.as_list(base.value(mass_property, "CenterOfMass"))]
    moi_local = parse_moi(base.as_list(mass_property.GetMomentOfInertia(0)))
    if mass <= 0.0 or len(com_local) != 3 or not all(math.isfinite(value) for value in [mass, *com_local, *(item for row in moi_local for item in row)]):
        raise GateError("MASS_PROPERTY_NONPHYSICAL", "external mechanical mass property is non-positive or non-finite", {"role": role, "mass": mass, "com": com_local, "moi": moi_local})
    rotation, translation, transform16 = component_transform(component)
    rotated = matvec(rotation, com_local)
    com_world = [rotated[index] + translation[index] for index in range(3)]
    moi_world = matmul(matmul(rotation, moi_local), transpose(rotation))
    source = component_path(component)
    return {
        "role": role,
        "source_path": norm(source),
        "source_sha256": sha256(source),
        "referenced_configuration": configuration,
        "source_class": "V5_NATIVE_EXTERNAL_MECHANICAL",
        "mass_kg": mass,
        "local_com": com_local,
        "world_com": com_world,
        "world_moi": moi_world,
        "total_transform_16": transform16,
        "accepted_urdf_excluded": True,
        "scope": "EXTERNAL_MECHANICAL_MASS_ONLY",
    }


def aggregate_mass(rows: Sequence[Mapping[str, Any]]) -> Tuple[float, List[float], List[List[float]]]:
    total = sum(float(row["mass_kg"]) for row in rows)
    if total <= 0.0:
        raise GateError("EXTERNAL_MASS_TOTAL_FAIL", "external mechanical total mass is not positive")
    com = [sum(float(row["mass_kg"]) * float(row["world_com"][index]) for row in rows) / total for index in range(3)]
    inertia = [[0.0 for _ in range(3)] for _ in range(3)]
    for row in rows:
        mass = float(row["mass_kg"])
        delta = [float(row["world_com"][index]) - com[index] for index in range(3)]
        distance2 = sum(value * value for value in delta)
        local = row["world_moi"]
        for i in range(3):
            for j in range(3):
                parallel = mass * ((distance2 if i == j else 0.0) - delta[i] * delta[j])
                inertia[i][j] += float(local[i][j]) + parallel
    if not all(math.isfinite(value) for value in [total, *com, *(value for row in inertia for value in row)]):
        raise GateError("EXTERNAL_MASS_AGGREGATE_NONFINITE", "aggregate mass property contains non-finite value")
    return total, com, inertia


def stage_path(stage_root: Path, final_path: Path) -> Path:
    if not path_inside(final_path, RUN_ROOT):
        raise GateError("STAGE_TARGET_OUTSIDE_RELEASE", "staged release target is outside RUN_ROOT", {"target": norm(final_path)})
    return stage_root / final_path.resolve().relative_to(RUN_ROOT.resolve())


def build_bom_and_mass(sw: Any, stage_root: Path, loop1e: Mapping[str, Any], types: Any, pythoncom: Any) -> Dict[str, Any]:
    model, opened = open_read_only(sw, TOP, types, pythoncom)
    top_hash_before = sha256(TOP)
    try:
        show_configuration(model, "SOLAR_DEPLOYED_NOMINAL")
        roles = top_role_paths(loop1e)
        live_top = top_level_components(model, types, pythoncom)
        expected_top = {normcase(path) for path in roles.values()}
        if set(live_top) != expected_top:
            raise GateError("TOP_ROLE_COMPONENT_SET_FAIL", "live top-level component set differs from receipted exact role set", {"actual": sorted(live_top), "expected": sorted(expected_top)})

        mass_facts = [component_mass_fact(live_top[normcase(roles[role])], role, types, pythoncom) for role in EXTERNAL_MASS_ROLES]
        total_mass, system_com, system_inertia = aggregate_mass(mass_facts)
        mass_rows = []
        for row in mass_facts:
            mass_rows.append({
                "role": row["role"],
                "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
                "referenced_configuration": row["referenced_configuration"],
                "source_class": row["source_class"],
                "mass_kg": format(float(row["mass_kg"]), ".17g"),
                "local_com_x_m": format(float(row["local_com"][0]), ".17g"),
                "local_com_y_m": format(float(row["local_com"][1]), ".17g"),
                "local_com_z_m": format(float(row["local_com"][2]), ".17g"),
                "world_com_x_m": format(float(row["world_com"][0]), ".17g"),
                "world_com_y_m": format(float(row["world_com"][1]), ".17g"),
                "world_com_z_m": format(float(row["world_com"][2]), ".17g"),
                "world_ixx_kg_m2": format(float(row["world_moi"][0][0]), ".17g"),
                "world_iyy_kg_m2": format(float(row["world_moi"][1][1]), ".17g"),
                "world_izz_kg_m2": format(float(row["world_moi"][2][2]), ".17g"),
                "world_ixy_kg_m2": format(float(row["world_moi"][0][1]), ".17g"),
                "world_ixz_kg_m2": format(float(row["world_moi"][0][2]), ".17g"),
                "world_iyz_kg_m2": format(float(row["world_moi"][1][2]), ".17g"),
                "total_transform_16": json.dumps(row["total_transform_16"], separators=(",", ":"), allow_nan=False),
                "accepted_urdf_excluded": "true",
                "scope": "EXTERNAL_MECHANICAL_MASS_ONLY",
            })
        mass_csv_stage = stage_path(stage_root, MASS_CSV)
        write_csv_once(mass_csv_stage, MASS_FIELDS, mass_rows)
        summary = {
            "schema": "F3R2_V5_EXTERNAL_MECHANICAL_MASS_SUMMARY_R2B_V1",
            "timestamp_utc": utc_now(),
            "source_csv": {"final_path": norm(MASS_CSV), "staging": file_fact(mass_csv_stage)},
            "configuration": "SOLAR_DEPLOYED_NOMINAL",
            "coordinate_frame": "LOOP1E_TOP_SPACECRAFT_WORLD",
            "external_roles": list(EXTERNAL_MASS_ROLES),
            "excluded_truth_roles": list(EXCLUDED_TRUTH_ROLES),
            "total_external_mechanical_mass_kg": total_mass,
            "external_mechanical_com_m": system_com,
            "external_mechanical_inertia_about_external_com_kg_m2": system_inertia,
            "external_mechanical_only": True,
            "solar_mass_scope": "EXTERNAL_MECHANICAL_MASS_ONLY",
            "accepted_urdf": file_fact(ACCEPTED_URDF),
            "accepted_urdf_is_l0_mass_inertia_authority": True,
            "accepted_urdf_overwritten": False,
            "spacecraft_mass_truth_changed": False,
            "classification": CLASSIFICATION,
            "verdict": "V5_R2B_EXTERNAL_MECHANICAL_MASS_SEPARATE_PASS",
        }
        mass_summary_stage = stage_path(stage_root, MASS_SUMMARY)
        write_json_once(mass_summary_stage, summary)

        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        occurrences = [base.wrap(raw, "IComponent2", types, pythoncom) for raw in base.as_list(assembly.GetComponents(False))]
        root_role_by_name = {component_name2(live_top[normcase(path)]): role for role, path in roles.items()}
        grouped: Dict[Tuple[str, str, str, str, int], Dict[str, Any]] = {}
        seen_paths: set[str] = set()
        denied_paths = {normcase(path) for path in LEGACY_SOLAR_DENY_PATHS}
        for component in occurrences:
            name = component_name2(component)
            source = component_path(component)
            source_key = normcase(source)
            if source_key in denied_paths:
                raise GateError("BOM_OLD_SINGLE_PANEL_DENY", "BOM traversal reached a prohibited old solar part", {"name2": name, "path": norm(source)})
            seen_paths.add(source_key)
            parent = name.rsplit("/", 1)[0] if "/" in name else "SEI_MECH_B601_V5_NATIVE_BASELINE"
            level = name.count("/") + 1
            configuration = str(base.value(component, "ReferencedConfiguration"))
            try:
                suppression = int(base.value(component, "GetSuppression"))
            except Exception:
                suppression = -1
            first = name.split("/", 1)[0]
            role = root_role_by_name.get(first, "UNMAPPED")
            if role == "UNMAPPED":
                for root_name, candidate_role in root_role_by_name.items():
                    if name == root_name or name.startswith(root_name + "/"):
                        role = candidate_role
                        break
            source_class = "ACCEPTED_TRUTH_REFERENCE" if role in EXCLUDED_TRUTH_ROLES else "V5_NATIVE_EXTERNAL_MECHANICAL"
            mass_scope = "EXCLUDED_ACCEPTED_URDF_OR_SPACECRAFT_TRUTH" if role in EXCLUDED_TRUTH_ROLES else "EXTERNAL_MECHANICAL_MASS_ONLY"
            key = (parent, source_key, configuration, source_class, suppression)
            if key not in grouped:
                grouped[key] = {
                    "level": level,
                    "parent_occurrence": parent,
                    "component_name2": name,
                    "quantity": 0,
                    "native_path": norm(source),
                    "native_sha256": sha256(source),
                    "referenced_configuration": configuration,
                    "suppression": suppression,
                    "source_class": source_class,
                    "mass_scope": mass_scope,
                    "classification": CLASSIFICATION,
                    "holds": ";".join(REQUIRED_HOLDS),
                }
            grouped[key]["quantity"] += 1
        expected_dependencies = set(validate_loop1e_payload(loop1e)["dependency_paths"])
        missing_bom = sorted(expected_dependencies - seen_paths)
        if missing_bom:
            raise GateError("BOM_DEPENDENCY_COVERAGE_FAIL", "BOM traversal does not cover every Loop1E dependency", {"missing": missing_bom})
        bom_rows = []
        for index, row in enumerate(sorted(grouped.values(), key=lambda value: (value["level"], value["parent_occurrence"], value["component_name2"], value["native_path"])), 1):
            bom_rows.append({"item_no": index, **row})
        bom_stage = stage_path(stage_root, BOM)
        write_csv_once(bom_stage, BOM_FIELDS, bom_rows)
        return {
            "open": opened,
            "mass_csv": file_fact(mass_csv_stage),
            "mass_summary": file_fact(mass_summary_stage),
            "bom": file_fact(bom_stage),
            "external_mass_role_count": len(mass_rows),
            "bom_row_count": len(bom_rows),
            "dependency_coverage_count": len(expected_dependencies),
            "excluded_truth_roles": list(EXCLUDED_TRUTH_ROLES),
        }
    finally:
        close_owned(sw)
        if sha256(TOP) != top_hash_before:
            raise GateError("TOP_HASH_DRIFT_DURING_BOM_MASS", "read-only BOM/mass extraction changed Loop1E top")


def view_layout(count: int) -> List[Tuple[float, float]]:
    columns = 4 if count > 8 else 3 if count > 4 else 2
    rows = math.ceil(count / columns)
    x0, x1 = 0.055, 0.385
    y0, y1 = 0.075, 0.275
    xs = [x0 + (x1 - x0) * (index + 0.5) / columns for index in range(columns)]
    ys = [y1 - (y1 - y0) * (index + 0.5) / rows for index in range(rows)]
    return [(xs[index % columns], ys[index // columns]) for index in range(count)]


def create_view(drawing: Any, source: Path, view_names: Sequence[str], position: Tuple[float, float], configuration: str, types: Any, pythoncom: Any) -> Any:
    raw_view = None
    selected_name = None
    for view_name in view_names:
        try:
            raw_view = drawing.CreateDrawViewFromModelView3(str(source), view_name, position[0], position[1], 0.0)
        except Exception:
            raw_view = None
        if raw_view is not None:
            selected_name = view_name
            break
    if raw_view is None:
        raise GateError("DRAWING_VIEW_CREATE_FAIL", "CreateDrawViewFromModelView3 failed for every localized name", {"source": norm(source), "configuration": configuration, "view_names": list(view_names)})
    view = base.wrap(raw_view, "IView", types, pythoncom)
    try:
        view.ReferencedConfiguration = configuration
    except Exception as exc:
        raise GateError("DRAWING_VIEW_CONFIG_FAIL", "cannot bind drawing view to required configuration", {"source": norm(source), "configuration": configuration, "reason": str(exc)}) from exc
    return {"view": view, "model_view_name": selected_name, "configuration": configuration, "position_m": list(position)}


def insert_release_note(model: Any, text: str, types: Any, pythoncom: Any) -> bool:
    try:
        model.ClearSelection2(True)
        raw = model.InsertNote(text)
        if raw is None:
            return False
        note = base.wrap(raw, "INote", types, pythoncom)
        annotation_raw = base.value(note, "GetAnnotation")
        annotation = base.wrap(annotation_raw, "IAnnotation", types, pythoncom)
        annotation.SetPosition(0.018, 0.397, 0.0)
        return True
    except Exception:
        return False


def set_document_properties(model: Any, values: Mapping[str, str]) -> None:
    manager = base.value(base.value(model, "Extension"), "CustomPropertyManager", "")
    for name, value in values.items():
        try:
            manager.Add3(str(name), 30, str(value), 2)
        except Exception as exc:
            raise GateError("DRAWING_PROPERTY_FAIL", "cannot write release drawing custom property", {"name": name, "reason": str(exc)}) from exc


def build_drawing(sw: Any, spec: Mapping[str, Any], stage_root: Path, bom_stage: Path, types: Any, pythoncom: Any) -> Dict[str, Any]:
    source = Path(spec["source"]).resolve()
    source_before = file_fact(source)
    if spec.get("sha256") and source_before["sha256"] != spec["sha256"]:
        raise GateError("DRAWING_SOURCE_HASH_FAIL", "drawing source differs from pinned identity", {"id": spec["id"], "fact": source_before, "expected": spec["sha256"]})
    source_model, source_open = open_read_only(sw, source, types, pythoncom)
    drawing_model = None
    final_slddrw = RUN_ROOT / f"07_drawings/{spec['name']}.SLDDRW"
    final_pdf = RUN_ROOT / f"07_drawings/{spec['name']}.PDF"
    stage_slddrw = stage_path(stage_root, final_slddrw)
    stage_pdf = stage_path(stage_root, final_pdf)
    if stage_slddrw.exists() or stage_pdf.exists() or final_slddrw.exists() or final_pdf.exists():
        raise GateError("DRAWING_DESTINATION_COLLISION", "drawing staging or final target already exists", {"id": spec["id"]})
    try:
        available = configuration_names(source_model)
        requested = list(spec["configurations"])
        if spec["id"] == "11_TOP":
            if available != list(TOP_CONFIGS):
                raise GateError("TOP_DRAWING_CONFIG_SET_FAIL", "top drawing source does not carry exact 11 configurations", {"available": available})
        elif not set(requested).issubset(set(available)):
            raise GateError("DRAWING_SOURCE_CONFIG_MISSING", "drawing source lacks required configuration", {"id": spec["id"], "requested": requested, "available": available})
        raw_drawing = sw.NewDocument(str(DRAWING_TEMPLATE), 0, 0.0, 0.0)
        if raw_drawing is None:
            raise GateError("NEW_DRAWING_FAIL", "NewDocument returned null", {"template": norm(DRAWING_TEMPLATE)})
        drawing_model = base.wrap(raw_drawing, "IModelDoc2", types, pythoncom)
        drawing = base.wrap(raw_drawing, "IDrawingDoc", types, pythoncom)
        placed: List[Dict[str, Any]] = []
        if len(requested) == 1:
            show_configuration(source_model, requested[0])
            names = (("*前视", "*Front"), ("*上视", "*Top"), ("*右视", "*Right"), ("*等轴测", "*Isometric"))
            for view_names, position in zip(names, view_layout(4)):
                placed.append(create_view(drawing, source, view_names, position, requested[0], types, pythoncom))
        else:
            positions = view_layout(len(requested))
            for configuration, position in zip(requested, positions):
                show_configuration(source_model, configuration)
                placed.append(create_view(drawing, source, ("*等轴测", "*Isometric"), position, configuration, types, pythoncom))
        note_lines = [
            f"F3R2 V5 R2B RELEASE DRAWING {spec['id']}",
            f"SCOPE={spec['scope']}",
            f"CONFIGURATIONS={','.join(requested)}",
            f"CLASSIFICATION={CLASSIFICATION}; FLIGHT_READY=FALSE; LAUNCH_QUALIFIED=FALSE",
            "MASS_SCOPE=EXTERNAL_MECHANICAL_ONLY; ACCEPTED_URDF_L0_UNCHANGED",
            "LAUNCH_LOAD/TVAC/RANDOM_VIBRATION/FORMAL_FASTENER_MOS=HOLD",
        ]
        if spec["id"] == "11_TOP":
            note_lines.extend((
                "TOP_GA=11_CONFIGURATION_NATIVE_READBACK",
                "EXPLODED_DOCUMENTATION=OCCURRENCE_TREE_PLUS_BOM_REGISTER; NO_GEOMETRY_CHANGE",
                f"BOM={norm(BOM)}; BOM_SHA256={sha256(bom_stage)}",
                "AFTER_GATE=ECR_ONLY",
            ))
        note_inserted = insert_release_note(drawing_model, "\n".join(note_lines), types, pythoncom)
        if not note_inserted:
            raise GateError("DRAWING_RELEASE_NOTE_FAIL", "release boundary note was not inserted", {"id": spec["id"]})
        set_document_properties(drawing_model, {
            "F3R2_DRAWING_ID": str(spec["id"]),
            "F3R2_RELEASE_SCOPE": str(spec["scope"]),
            "F3R2_CLASSIFICATION": CLASSIFICATION,
            "F3R2_CONFIGURATION_SET": ";".join(requested),
            "F3R2_MASS_SCOPE": "EXTERNAL_MECHANICAL_ONLY",
            "F3R2_AFTER_GATE": "ECR_ONLY",
            "F3R2_FLIGHT_READY": "FALSE",
            "F3R2_LAUNCH_QUALIFIED": "FALSE",
        })
        if not bool(drawing_model.ForceRebuild3(True)):
            raise GateError("DRAWING_REBUILD_FAIL", "drawing rebuild failed", {"id": spec["id"]})
        stage_slddrw.parent.mkdir(parents=True, exist_ok=True)
        raw_save = base.value(base.value(drawing_model, "Extension"), "SaveAs", str(stage_slddrw), SW_SAVE_AS_CURRENT_VERSION, SW_SAVE_AS_SILENT, None, 0, 0)
        saved, save_outs = base.unpack(raw_save)
        if not bool(saved) or (save_outs and int(save_outs[0]) != 0) or not is_ole(stage_slddrw):
            raise GateError("DRAWING_NATIVE_SAVE_FAIL", "native SLDDRW staging SaveAs failed", {"id": spec["id"], "saved": saved, "outs": save_outs, "fact": file_fact(stage_slddrw)})
        if stage_pdf.exists():
            raise GateError("DRAWING_PDF_COLLISION", "PDF staging target exists before export", {"id": spec["id"], "path": norm(stage_pdf)})
        raw_pdf = drawing_model.SaveAs3(str(stage_pdf), 0, 0)
        pdf_saved, pdf_outs = base.unpack(raw_pdf)
        if not bool(pdf_saved) or not is_pdf(stage_pdf):
            raise GateError("DRAWING_PDF_SAVE_FAIL", "drawing PDF export failed", {"id": spec["id"], "saved": pdf_saved, "outs": pdf_outs, "fact": file_fact(stage_pdf)})
        drawing_dependencies = dependencies(drawing_model)
        if normcase(source) not in drawing_dependencies:
            raise GateError("DRAWING_SOURCE_REFERENCE_FAIL", "saved drawing does not reference contracted source", {"id": spec["id"], "source": norm(source), "dependencies": drawing_dependencies})
        sheet_names = [str(value) for value in base.as_list(drawing.GetSheetNames())]
        if len(sheet_names) != 1:
            raise GateError("DRAWING_SHEET_COUNT_FAIL", "release drawing must have exactly one A3 sheet", {"id": spec["id"], "sheets": sheet_names})
        return {
            "drawing_id": spec["id"],
            "slddrw_path": norm(final_slddrw),
            "slddrw_sha256": sha256(stage_slddrw),
            "pdf_path": norm(final_pdf),
            "pdf_sha256": sha256(stage_pdf),
            "source_path": norm(source),
            "source_sha256": source_before["sha256"],
            "configurations": ";".join(requested),
            "view_count": len(placed),
            "sheet_count": 1,
            "scope": spec["scope"],
            "classification": CLASSIFICATION,
            "manufacturing_release": "false",
            "flight_claim": "false",
            "source_open": source_open,
            "dependencies": drawing_dependencies,
            "placed_views": [{key: value for key, value in row.items() if key != "view"} for row in placed],
        }
    finally:
        close_owned(sw)
        if file_fact(source) != source_before:
            raise GateError("DRAWING_SOURCE_HASH_DRIFT", "drawing generation changed its read-only source", {"id": spec["id"], "pre": source_before, "post": file_fact(source)})


def build_drawings(sw: Any, stage_root: Path, types: Any, pythoncom: Any) -> Dict[str, Any]:
    bom_stage = stage_path(stage_root, BOM)
    if not bom_stage.is_file():
        raise GateError("DRAWING_BOM_STAGE_MISSING", "BOM must be staged before drawings")
    rows = [build_drawing(sw, spec, stage_root, bom_stage, types, pythoncom) for spec in DRAWING_SPECS]
    register_rows = [{field: row[field] for field in DRAWING_FIELDS} for row in rows]
    register_stage = stage_path(stage_root, DRAWING_REGISTER)
    write_csv_once(register_stage, DRAWING_FIELDS, register_rows)
    return {"register": file_fact(register_stage), "drawing_pair_count": len(rows), "drawings": rows, "verdict": "V5_R2B_EXACT_11_NATIVE_DRAWING_PDF_PAIRS_STAGED"}


def state_evidence_from_loop2(loop2_results: Mapping[str, Any]) -> List[Dict[str, Any]]:
    cells = loop2_results.get("static_cells", [])
    rows = []
    for state in SOLAR_STATES:
        selected = [row for row in cells if row.get("solar_state") == state]
        if len(selected) != 3 or {row.get("pose") for row in selected} != set(AUTHORIZED_Q) or not all(row.get("pass") is True for row in selected):
            raise GateError("DIGITAL_STATE_CELL_SET_FAIL", "final digital state does not have exact three authorized-q PASS cells", {"state": state})
        left_angles = selected[0].get("left_angles_deg")
        right_angles = selected[0].get("right_angles_deg")
        if any(row.get("left_angles_deg") != left_angles or row.get("right_angles_deg") != right_angles for row in selected):
            raise GateError("DIGITAL_STATE_ANGLE_DRIFT", "Loop2 state cells disagree on solar angles", {"state": state})
        camera_values = [float(row["camera_visibility_proxy"]["minimum_clearance_mm"]) for row in selected]
        arm_values = [float(row["arm_clearance_mm"]) for row in selected]
        bus_values = [float(row["bus_clearance_mm"]) for row in selected]
        harness_values = [float(row["harness_clearance_mm"]) for row in selected]
        rows.append({
            "solar_state": state,
            "left_panel_angles_deg": left_angles,
            "right_panel_angles_deg": right_angles,
            "hinge_state": "SIDE_SLDASM_LIMIT_ANGLE_NATIVE_READBACK",
            "collision_state": "NO_POSITIVE_INTERFERENCE_EXPECTED_ZERO_VOLUME_CONTACTS_ONLY",
            "camera_visibility": "CLEAR_BY_NATIVE_ENVELOPE_PROXY_NOT_CALIBRATED_FOV",
            "camera_to_solar_minimum_clearance_mm": min(camera_values),
            "arm_clearance_mm": min(arm_values),
            "bus_clearance_mm": min(bus_values),
            "harness_clearance_mm": min(harness_values),
            "authorized_q_samples": list(AUTHORIZED_Q),
            "sample_count": len(selected),
            "pass": True,
        })
    return rows


def build_final_digital_thread(stage_root: Path, loop1e: Mapping[str, Any], loop2: Mapping[str, Any]) -> Dict[str, Any]:
    results = load_json(LOOP2_RESULTS_JSON)
    state_evidence = state_evidence_from_loop2(results)
    payload = {
        "schema": "F3R2_V5_NATIVE_MECHANICAL_FINAL_THREAD_R2B_V1",
        "timestamp_utc": utc_now(),
        "baseline": FINAL_VERDICT,
        "classification": CLASSIFICATION,
        "configuration_owner": "SIDE_SLDASM_ONLY",
        "top_level_second_solar_driver_count": 0,
        "top_configurations": list(TOP_CONFIGS),
        "solar_states": list(SOLAR_STATES),
        "state_evidence": state_evidence,
        "loop1e_receipt": file_fact(LOOP1E_RECEIPT),
        "loop2_receipt": file_fact(LOOP2_RECEIPT),
        "loop2_clearance_results": file_fact(LOOP2_RESULTS_JSON),
        "p9_promotion": file_fact(P9_PROMOTION),
        "p9_left_side": file_fact(P9_LEFT),
        "p9_right_side": file_fact(P9_RIGHT),
        "digital_promotion_receipt": file_fact(DIGITAL_PROMOTION_RECEIPT),
        "state_machine_r2": file_fact(DIGITAL_STATE_MACHINE),
        "solar_annex_r2b": file_fact(DIGITAL_SOLAR_ANNEX),
        "solar_state_register": file_fact(DIGITAL_SOLAR_REGISTER),
        "accepted_urdf": file_fact(ACCEPTED_URDF),
        "accepted_urdf_written": False,
        "q_authority_written": False,
        "service_grasp_q": None,
        "mass_scope": "EXTERNAL_MECHANICAL_MASS_ONLY",
        "holds": list(REQUIRED_HOLDS),
        "mechanical_authoring_after_gate": "ECR_ONLY",
        "next_domains": ["FREE_FLOATING_DYNAMICS", "CONTROL", "SAFE-00", "EMBODIED_CAPTURE", "VLA"],
        "verdict": "V5_NATIVE_MECHANICAL_FINAL_DIGITAL_THREAD_R2B_PASS",
    }
    digital_stage = stage_path(stage_root, FINAL_DIGITAL_THREAD)
    write_json_once(digital_stage, payload)
    manifest_inputs = [
        digital_stage, LOOP1E_RECEIPT, LOOP2_RECEIPT, LOOP2_RESULTS_JSON, LOOP2_RESULTS_CSV,
        LOOP2_CHECKPOINT, LOOP2_MANIFEST, P9_PROMOTION, P9_FRESH, P9_LEFT, P9_RIGHT,
        DIGITAL_PROMOTION_RECEIPT, DIGITAL_PROMOTION_MANIFEST, DIGITAL_STATE_MACHINE,
        DIGITAL_SOLAR_ANNEX, DIGITAL_SOLAR_REGISTER, ACCEPTED_URDF,
    ]
    missing = [norm(path) for path in manifest_inputs if not path.is_file()]
    if missing:
        raise GateError("FINAL_DIGITAL_MANIFEST_INPUT_MISSING", "final R2B digital manifest input is missing", {"missing": missing})
    lines = []
    for path in manifest_inputs:
        label = norm(FINAL_DIGITAL_THREAD) if path == digital_stage else norm(path)
        lines.append(f"{sha256(path)}  {path.stat().st_size}  {label}")
    manifest_stage = stage_path(stage_root, FINAL_DIGITAL_MANIFEST)
    write_text_once(manifest_stage, "\n".join(sorted(lines)) + "\n")
    return {"thread": file_fact(digital_stage), "manifest": file_fact(manifest_stage), "state_count": len(state_evidence), "verdict": payload["verdict"]}


def package_relative(source: Path) -> Path:
    source = source.resolve()
    if path_inside(source, RUN_ROOT):
        return source.relative_to(RUN_ROOT.resolve())
    return Path("_external") / sha256(source)[:16] / source.name


def package_map(sources: Sequence[Path], package_root: Path) -> Dict[str, Path]:
    mapping: Dict[str, Path] = {}
    destinations: Dict[str, str] = {}
    for source in sources:
        key = normcase(source)
        target = (package_root / package_relative(source)).resolve()
        target_key = os.path.normcase(str(target))
        if target_key in destinations and destinations[target_key] != key:
            raise GateError("PACK_DESTINATION_COLLISION", "two source documents map to one package target", {"target": norm(target), "sources": [destinations[target_key], key]})
        mapping[key] = target
        destinations[target_key] = key
    return mapping


def build_pack_and_go_equivalent(sw: Any, stage_root: Path, dependency_paths: Sequence[str], types: Any, pythoncom: Any) -> Dict[str, Any]:
    final_sources = [TOP.resolve(), *(Path(path).resolve() for path in dependency_paths)]
    keys = [normcase(path) for path in final_sources]
    if len(keys) != len(set(keys)):
        raise GateError("PACK_SOURCE_DUPLICATE", "top plus Loop1E dependency ledger is not a unique set")
    stage_pack_root = stage_path(stage_root, PACK_ROOT)
    if stage_pack_root.exists() or PACK_ROOT.exists():
        raise GateError("PACK_DESTINATION_COLLISION", "Pack-and-Go staging or final root already exists")
    mapping = package_map(final_sources, stage_pack_root)
    for source in final_sources:
        target = mapping[normcase(source)]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise GateError("PACK_FILE_COLLISION", "package target exists before copy", {"target": norm(target)})
        shutil.copy2(source, target)
        if sha256(target) != sha256(source):
            raise GateError("PACK_COPY_HASH_FAIL", "initial exact package copy changed bytes", {"source": norm(source), "target": norm(target)})

    # GetPackAndGo is unavailable on this registered installation through its
    # generated COM binding.  The equivalent path remains SOLIDWORKS-native:
    # copy the exact receipted set, rebase every closed native document with
    # ReplaceReferencedDocument, then prove the exact package dependency set by
    # read-only cold reopen.  No fixed file count is assumed.
    replacement_counts: Counter[str] = Counter()
    referencing_sources = [path for path in final_sources if path.suffix.upper() in {".SLDASM", ".SLDDRW"}]
    for referencing in sorted(referencing_sources, key=lambda path: len(path.parts), reverse=True):
        packaged_referencing = mapping[normcase(referencing)]
        for original in final_sources[1:]:
            if original == referencing:
                continue
            try:
                replaced = bool(sw.ReplaceReferencedDocument(str(packaged_referencing), str(original), str(mapping[normcase(original)])))
            except Exception:
                replaced = False
            if replaced:
                replacement_counts[normcase(original)] += 1

    package_top = mapping[normcase(TOP)]
    package_model, opened = open_read_only(sw, package_top, types, pythoncom)
    try:
        actual = dependencies(package_model)
        expected = sorted(normcase(mapping[path]) for path in dependency_paths)
        escaped = [path for path in actual if not path_inside(Path(path), stage_pack_root)]
        if actual != expected or escaped:
            raise GateError("PACK_EXACT_DEPENDENCY_FAIL", "packaged top dependency set is not the exact rebased Loop1E ledger", {"actual": actual, "expected": expected, "escaped": escaped})
        configs = configuration_names(package_model)
        if configs != list(TOP_CONFIGS):
            raise GateError("PACK_TOP_CONFIG_SET_FAIL", "packaged top lost exact 11 configurations", {"actual": configs})
        for config in TOP_CONFIGS:
            show_configuration(package_model, config)
    finally:
        close_owned(sw)

    ledger_rows = []
    for source in final_sources:
        target = mapping[normcase(source)]
        ledger_rows.append({
            "source_path": norm(source),
            "source_sha256_pre": sha256(source),
            "package_path": norm(PACK_ROOT / target.relative_to(stage_pack_root)),
            "package_sha256_post": sha256(target),
            "source_kind": "TOP" if source == TOP.resolve() else "LOOP1E_DEPENDENCY",
            "from_loop1e_dependency_ledger": "false" if source == TOP.resolve() else "true",
            "exists": "true",
            "inside_package": "true",
        })
    ledger_stage = stage_path(stage_root, PACK_LEDGER)
    write_csv_once(ledger_stage, PACK_FIELDS, ledger_rows)
    proof = {
        "schema": "F3R2_V5_PACK_AND_GO_R2B_PROOF_V1",
        "timestamp_utc": utc_now(),
        "release_packaging_class": "REGISTERED_EQUIVALENT_PACK_AND_GO",
        "method": "EXACT_LEDGER_COPY_PLUS_SOLIDWORKS_REPLACE_REFERENCED_DOCUMENT_PLUS_COLD_EXACT_DEPENDENCY",
        "registered_binding_deviation": "D-F3R1-01_GETPACKANDGO_GENERATED_BINDING_UNAVAILABLE",
        "getpackandgo_unavailable_evidence": file_fact(PACK_AND_GO_DEVIATION_EVIDENCE),
        "native_getpackandgo_claimed": False,
        "source_set_authority": "LOOP1E_COLD_REOPEN_DEPENDENCY_LEDGER_PLUS_TOP",
        "fixed_count_assumed": False,
        "dynamic_source_count": len(final_sources),
        "dynamic_dependency_count": len(dependency_paths),
        "source_top": file_fact(TOP),
        "package_top_final_path": norm(PACK_TOP),
        "package_top_staging": file_fact(package_top),
        "reference_ledger_final_path": norm(PACK_LEDGER),
        "reference_ledger_staging": file_fact(ledger_stage),
        "replacement_success_count_by_source": dict(replacement_counts),
        "actual_dependency_count": len(dependency_paths),
        "missing_reference_count": 0,
        "escaped_reference_count": 0,
        "critical_external_reference_count": 0,
        "self_contained": True,
        "exact_11_top_configurations": list(TOP_CONFIGS),
        "cold_open": opened,
        "verdict": "V5_R2B_REGISTERED_EQUIVALENT_PACK_AND_GO_SELF_CONTAINED_PASS",
    }
    proof_stage = stage_path(stage_root, PACK_PROOF)
    write_json_once(proof_stage, proof)
    return {
        "package_root": norm(stage_pack_root),
        "package_top": file_fact(package_top),
        "ledger": file_fact(ledger_stage),
        "proof": file_fact(proof_stage),
        "dynamic_dependency_count": len(dependency_paths),
        "package_tree": tree_facts(stage_pack_root),
        "verdict": proof["verdict"],
    }


def build_claims(stage_root: Path) -> Dict[str, Any]:
    payload = {
        "schema": "F3R2_V5_NATIVE_MECHANICAL_RELEASE_CLAIMS_R2B_V1",
        "timestamp_utc": utc_now(),
        "baseline_gate": FINAL_VERDICT,
        "classification": CLASSIFICATION,
        "prohibited_claims": {name: False for name in PROHIBITED_CLAIMS},
        "holds": list(REQUIRED_HOLDS),
        "accepted_urdf": file_fact(ACCEPTED_URDF),
        "accepted_urdf_overwritten": False,
        "joint_topology_changed": False,
        "link_length_changed": False,
        "inertial_truth_changed": False,
        "q_authority_changed": False,
        "solar_mass_scope": "EXTERNAL_MECHANICAL_MASS_ONLY",
        "mechanical_authoring_after_gate": "ECR_ONLY",
        "next_domains": ["FREE_FLOATING_DYNAMICS", "CONTROL", "SAFE-00", "EMBODIED_CAPTURE", "VLA"],
        "verdict": "V5_NATIVE_MECHANICAL_RELEASE_CLAIM_BOUNDARY_PASS",
    }
    target = stage_path(stage_root, CLAIMS)
    write_json_once(target, payload)
    return file_fact(target)


def tree_digest(root: Path) -> Dict[str, Any]:
    facts = tree_facts(root)
    rows = []
    for fact in facts:
        path = Path(fact["path"])
        rows.append({"relative": path.relative_to(root.resolve()).as_posix(), "bytes": fact["bytes"], "sha256": fact["sha256"]})
    data = serialize_json({"files": rows})
    return {"path": norm(root), "exists": root.is_dir(), "file_count": len(rows), "tree_sha256": hashlib.sha256(data).hexdigest().upper(), "files": rows}


def promotion_units(stage_root: Path) -> List[Dict[str, Any]]:
    files = [path for path in final_output_paths() if path != PACK_ROOT]
    units = []
    for final_path in files:
        source = stage_path(stage_root, final_path)
        if not source.is_file():
            raise GateError("PRECOMMIT_STAGE_FILE_MISSING", "required staged release file is missing", {"source": norm(source), "target": norm(final_path)})
        units.append({"kind": "file", "source": norm(source), "target": norm(final_path), "fact": file_fact(source)})
    package_source = stage_path(stage_root, PACK_ROOT)
    package_fact = tree_digest(package_source)
    if not package_fact["exists"] or package_fact["file_count"] < 1:
        raise GateError("PRECOMMIT_STAGE_PACK_MISSING", "staged package tree is missing or empty")
    units.append({"kind": "directory", "source": norm(package_source), "target": norm(PACK_ROOT), "fact": package_fact})
    return sorted(units, key=lambda row: (0 if row["kind"] == "file" else 1, row["target"]))


def same_unit_fact(unit: Mapping[str, Any], path: Path) -> bool:
    expected = unit["fact"]
    if unit["kind"] == "file":
        fact = file_fact(path)
        return fact.get("bytes") == expected.get("bytes") and fact.get("sha256") == expected.get("sha256")
    fact = tree_digest(path)
    return fact.get("file_count") == expected.get("file_count") and fact.get("tree_sha256") == expected.get("tree_sha256")


def promote_no_replace(source: Path, target: Path) -> None:
    if not source.exists() or target.exists():
        raise GateError("NO_REPLACE_PRECONDITION_FAIL", "promotion requires existing source and absent target", {"source": norm(source), "target": norm(target), "source_exists": source.exists(), "target_exists": target.exists()})
    target.parent.mkdir(parents=True, exist_ok=True)
    import ctypes
    movefile_write_through = 0x00000008
    ok = ctypes.windll.kernel32.MoveFileExW(str(source), str(target), movefile_write_through)
    if not ok:
        error = ctypes.get_last_error()
        raise GateError("NO_REPLACE_MOVE_FAIL", "MoveFileExW no-replace promotion failed", {"source": norm(source), "target": norm(target), "winerror": error})


def promote_units(units: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    # Individual files are promoted before the package directory; every target
    # is absent and each move omits MOVEFILE_REPLACE_EXISTING.
    for unit in units:
        source = Path(str(unit["source"])).resolve()
        target = Path(str(unit["target"])).resolve()
        if target.exists():
            if not same_unit_fact(unit, target):
                raise GateError("PROMOTED_TARGET_DRIFT", "existing no-replace target differs from precommit", {"unit": unit})
            if source.exists():
                raise GateError("PROMOTION_DOUBLE_PRESENT", "both staging and target exist for one promotion unit", {"unit": unit})
            mode = "RESUME_ALREADY_PROMOTED"
        else:
            if not same_unit_fact(unit, source):
                raise GateError("PROMOTION_SOURCE_DRIFT", "staging unit differs from precommit", {"unit": unit})
            promote_no_replace(source, target)
            if not same_unit_fact(unit, target):
                raise GateError("PROMOTION_POST_FACT_FAIL", "promoted target differs from precommit", {"unit": unit})
            mode = "PROMOTED_NO_REPLACE"
        rows.append({"kind": unit["kind"], "source": norm(source), "target": norm(target), "mode": mode, "post_fact": file_fact(target) if unit["kind"] == "file" else tree_digest(target)})
    return rows


def bound_upstream() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    if LOOP1E_RECEIPT_SHA256 is None or LOOP2_RECEIPT_SHA256 is None:
        raise GateError("UPSTREAM_RECEIPT_HASH_TBD", "Loop1E/Loop2 receipt SHA constants remain fail-closed TBD", {"loop1e": LOOP1E_RECEIPT_SHA256, "loop2": LOOP2_RECEIPT_SHA256})
    exact_fact(LOOP1E_RECEIPT, LOOP1E_RECEIPT_SHA256)
    exact_fact(LOOP2_RECEIPT, LOOP2_RECEIPT_SHA256)
    loop1e = load_json(LOOP1E_RECEIPT)
    loop2 = load_json(LOOP2_RECEIPT)
    contract = validate_loop1e_payload(loop1e)
    validate_loop2_payload(loop2)
    return loop1e, loop2, contract


def protected_snapshot() -> List[Dict[str, Any]]:
    paths = [
        *(path for _name, path, _expected in FIXED_INPUTS),
        TOP, LOOP1E_RECEIPT, LOOP2_RECEIPT, LOOP2_RESULTS_JSON, LOOP2_RESULTS_CSV,
        LOOP2_CHECKPOINT, LOOP2_MANIFEST,
    ]
    unique = {normcase(path): path.resolve() for path in paths}
    missing = [norm(path) for path in unique.values() if not path.is_file()]
    if missing:
        raise GateError("PROTECTED_INPUT_MISSING", "protected release input is missing", {"missing": missing})
    return [file_fact(path) for path in sorted(unique.values(), key=lambda item: norm(item).lower())]


def cold_top(sw: Any, path: Path, loop1e: Mapping[str, Any], expected_dependencies: Sequence[str], types: Any, pythoncom: Any, allowed_package_root: Optional[Path] = None, package_expected: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    before = file_fact(path)
    model, opened = open_read_only(sw, path, types, pythoncom)
    try:
        configs = configuration_names(model)
        if configs != list(TOP_CONFIGS):
            raise GateError("COLD_TOP_CONFIG_SET_FAIL", "cold top does not have exact 11 configurations", {"path": norm(path), "actual": configs})
        rows = []
        if allowed_package_root is None:
            role_paths = top_role_paths(loop1e)
            by_path_expected = {role: normcase(role_path) for role, role_path in role_paths.items()}
        else:
            source_map = package_map([TOP.resolve(), *(Path(value).resolve() for value in expected_dependencies)], allowed_package_root)
            source_roles = top_role_paths(loop1e)
            by_path_expected = {role: normcase(source_map[normcase(role_path)]) for role, role_path in source_roles.items()}
        for configuration in TOP_CONFIGS:
            show_configuration(model, configuration)
            live = top_level_components(model, types, pythoncom)
            left = live.get(by_path_expected["LEFT_SOLAR_ARRAY"])
            right = live.get(by_path_expected["RIGHT_SOLAR_ARRAY"])
            if left is None or right is None:
                raise GateError("COLD_SOLAR_SIDE_OCCURRENCE_FAIL", "cold top lacks exact left/right solar side occurrences", {"configuration": configuration})
            expected_state = configuration if configuration in SOLAR_STATES else "SOLAR_DEPLOYED_NOMINAL"
            actual_left = str(base.value(left, "ReferencedConfiguration"))
            actual_right = str(base.value(right, "ReferencedConfiguration"))
            if actual_left != expected_state or actual_right != expected_state:
                raise GateError("COLD_SOLAR_SIDE_STATE_FAIL", "cold top side referenced configuration drifted", {"configuration": configuration, "left": actual_left, "right": actual_right, "expected": expected_state})
            rows.append({"top_configuration": configuration, "left_referenced_configuration": actual_left, "right_referenced_configuration": actual_right})
        actual_dependencies = dependencies(model)
        expected = sorted(package_expected) if package_expected is not None else sorted(expected_dependencies)
        escaped = [] if allowed_package_root is None else [value for value in actual_dependencies if not path_inside(Path(value), allowed_package_root)]
        if actual_dependencies != expected or escaped:
            raise GateError("COLD_TOP_DEPENDENCY_EXACT_FAIL", "cold top dependency set differs from authority", {"path": norm(path), "actual": actual_dependencies, "expected": expected, "escaped": escaped})
        denied = sorted(set(actual_dependencies) & {normcase(item) for item in LEGACY_SOLAR_DENY_PATHS})
        if denied:
            raise GateError("COLD_OLD_SINGLE_PANEL_DENY", "cold top reaches old single-panel solar artifacts", {"denied": denied})
        return {"open": opened, "configuration_rows": rows, "dependency_paths": actual_dependencies, "dependency_count": len(actual_dependencies), "verdict": "V5_R2B_COLD_TOP_EXACT_PASS"}
    finally:
        close_owned(sw)
        if file_fact(path) != before:
            raise GateError("COLD_TOP_HASH_DRIFT", "read-only cold top verification changed bytes", {"path": norm(path), "pre": before, "post": file_fact(path)})


def cold_side(sw: Any, path: Path, types: Any, pythoncom: Any) -> Dict[str, Any]:
    before = file_fact(path)
    model, opened = open_read_only(sw, path, types, pythoncom)
    try:
        configs = configuration_names(model)
        if configs != list(SOLAR_STATES):
            raise GateError("COLD_SIDE_CONFIG_SET_FAIL", "P9 side lacks exact seven states", {"path": norm(path), "actual": configs})
        for configuration in SOLAR_STATES:
            show_configuration(model, configuration)
        return {"open": opened, "configurations": configs, "verdict": "V5_R2B_COLD_SIDE_SEVEN_STATE_PASS"}
    finally:
        close_owned(sw)
        if file_fact(path) != before:
            raise GateError("COLD_SIDE_HASH_DRIFT", "read-only side verification changed bytes", {"path": norm(path)})


def cold_drawing(sw: Any, drawing_path: Path, pdf_path: Path, source: Path, types: Any, pythoncom: Any) -> Dict[str, Any]:
    before = file_fact(drawing_path)
    pdf_before = file_fact(pdf_path)
    model, opened = open_read_only(sw, drawing_path, types, pythoncom)
    try:
        drawing = base.wrap(model, "IDrawingDoc", types, pythoncom)
        sheets = [str(value) for value in base.as_list(drawing.GetSheetNames())]
        deps = dependencies(model)
        if len(sheets) != 1 or normcase(source) not in deps or not is_pdf(pdf_path):
            raise GateError("COLD_DRAWING_FAIL", "cold drawing lacks sheet/source/PDF contract", {"drawing": norm(drawing_path), "sheets": sheets, "source": norm(source), "dependencies": deps, "pdf": file_fact(pdf_path)})
        return {"open": opened, "sheet_names": sheets, "dependencies": deps, "pdf": pdf_before, "verdict": "V5_R2B_COLD_DRAWING_PDF_PASS"}
    finally:
        close_owned(sw)
        if file_fact(drawing_path) != before or file_fact(pdf_path) != pdf_before:
            raise GateError("COLD_DRAWING_HASH_DRIFT", "read-only drawing/PDF verification changed bytes", {"drawing": norm(drawing_path)})


def cold_release_set(sw: Any, stage_root: Optional[Path], loop1e: Mapping[str, Any], dependency_paths: Sequence[str], types: Any, pythoncom: Any) -> Dict[str, Any]:
    left = cold_side(sw, P9_LEFT, types, pythoncom)
    right = cold_side(sw, P9_RIGHT, types, pythoncom)
    top = cold_top(sw, TOP, loop1e, dependency_paths, types, pythoncom)
    drawings = []
    for spec in DRAWING_SPECS:
        final_drawing = RUN_ROOT / f"07_drawings/{spec['name']}.SLDDRW"
        final_pdf = RUN_ROOT / f"07_drawings/{spec['name']}.PDF"
        drawing_path = stage_path(stage_root, final_drawing) if stage_root is not None else final_drawing
        pdf_path = stage_path(stage_root, final_pdf) if stage_root is not None else final_pdf
        drawings.append({"drawing_id": spec["id"], **cold_drawing(sw, drawing_path, pdf_path, Path(spec["source"]), types, pythoncom)})
    package_root = stage_path(stage_root, PACK_ROOT) if stage_root is not None else PACK_ROOT
    package_top = package_root / TOP.relative_to(RUN_ROOT)
    mapping = package_map([TOP.resolve(), *(Path(value).resolve() for value in dependency_paths)], package_root)
    expected_package = sorted(normcase(mapping[value]) for value in dependency_paths)
    package = cold_top(sw, package_top, loop1e, dependency_paths, types, pythoncom, package_root, expected_package)
    if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
        raise GateError("COLD_RELEASE_CLEANUP_FAIL", "cold release verification did not end empty")
    return {
        "top": top,
        "left_side": left,
        "right_side": right,
        "drawings": drawings,
        "drawing_pair_count": len(drawings),
        "package": package,
        "stage_root": norm(stage_root) if stage_root is not None else None,
        "verdict": "V5_R2B_RELEASE_SET_COLD_REOPEN_PASS",
    }


def validate_attempt_id(value: str) -> str:
    if not re.fullmatch(r"V5_LOOP3_RELEASE_[0-9A-Z_]{8,96}", value):
        raise GateError("ATTEMPT_ID_FAIL", "attempt id must match V5_LOOP3_RELEASE_[0-9A-Z_]{8,96}", {"attempt_id": value})
    return value


def release_identity() -> Dict[str, Any]:
    return {
        "files": [file_fact(path) for path in sorted(final_output_paths(), key=lambda path: norm(path).lower())],
        "package": tree_digest(PACK_ROOT),
    }


def precommit_payload(
    attempt_id: str,
    stage_root: Path,
    execution_g0: Mapping[str, Any],
    units: Sequence[Mapping[str, Any]],
    build: Mapping[str, Any],
    staging_cold: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema": "F3R2_V5_LOOP3_R2B_RELEASE_PRECOMMIT_V1",
        "timestamp_utc": utc_now(),
        "script": file_fact(SCRIPT),
        "attempt_id": attempt_id,
        "stage_root": norm(stage_root),
        "execution_g0": dict(execution_g0),
        "loop1e_receipt": file_fact(LOOP1E_RECEIPT),
        "loop2_receipt": file_fact(LOOP2_RECEIPT),
        "accepted_urdf": file_fact(ACCEPTED_URDF),
        "transaction_policy": "ISOLATED_STAGING_COLD_REOPEN_PRECOMMIT_NO_REPLACE_PROMOTION",
        "replacement_allowed": False,
        "direct_final_solidworks_save_allowed": False,
        "promotion_units": list(units),
        "build": dict(build),
        "staging_cold_reopen": dict(staging_cold),
        "classification": CLASSIFICATION,
        "holds": list(REQUIRED_HOLDS),
        "verdict": "V5_LOOP3_R2B_STAGING_PRECOMMIT_COLD_REOPEN_PASS",
    }


def failure_receipt(stage: str, payload: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    target = VALIDATION / f"V5_LOOP3_R2B_{stage}_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
    try:
        write_json_once(target, payload)
        return file_fact(target)
    except Exception:
        return None


def build_session_a(args: argparse.Namespace) -> int:
    result: Dict[str, Any] = {"schema": "F3R2_V5_LOOP3_R2B_SESSION_A_RUNTIME_V1", "timestamp_start_utc": utc_now(), "stage": "BUILD_SESSION_A"}
    sw = types = pythoncom = None
    try:
        if SESSION_A_CHECKPOINT.is_file():
            payload = load_json(SESSION_A_CHECKPOINT)
            if payload.get("verdict") != "V5_LOOP3_R2B_SESSION_A_RELEASE_BUILD_COLD_REOPEN_PASS":
                raise GateError("SESSION_A_CHECKPOINT_DRIFT", "existing Session-A checkpoint is not PASS")
            print(json.dumps({"verdict": payload["verdict"], "checkpoint": file_fact(SESSION_A_CHECKPOINT)}, ensure_ascii=False, indent=2, allow_nan=False))
            return 0
        attempt_id = validate_attempt_id(args.attempt_id)
        execution_g0 = validate_execution_g0(args.expected_pid, Path(args.g0_receipt), args.g0_sha256)
        result["execution_g0"] = execution_g0
        loop1e, loop2, contract = bound_upstream()
        result["upstream"] = {"loop1e": file_fact(LOOP1E_RECEIPT), "loop2": file_fact(LOOP2_RECEIPT)}
        protected_pre = protected_snapshot()
        result["protected_pre"] = protected_pre
        precommit: Optional[Dict[str, Any]] = None
        if PRECOMMIT.is_file():
            precommit = load_json(PRECOMMIT)
            if not (
                precommit.get("schema") == "F3R2_V5_LOOP3_R2B_RELEASE_PRECOMMIT_V1"
                and precommit.get("attempt_id") == attempt_id
                and precommit.get("script", {}).get("sha256") == sha256(SCRIPT)
                and precommit.get("loop1e_receipt", {}).get("sha256") == LOOP1E_RECEIPT_SHA256
                and precommit.get("loop2_receipt", {}).get("sha256") == LOOP2_RECEIPT_SHA256
                and precommit.get("execution_g0") == execution_g0
                and precommit.get("verdict") == "V5_LOOP3_R2B_STAGING_PRECOMMIT_COLD_REOPEN_PASS"
            ):
                raise GateError("PRECOMMIT_RESUME_BINDING_FAIL", "existing precommit differs from this exact script/upstream/G0/attempt")
            stage_root = Path(str(precommit["stage_root"])).resolve()
            units = precommit.get("promotion_units", [])
            if not isinstance(units, list) or not units:
                raise GateError("PRECOMMIT_UNIT_SET_FAIL", "precommit has no promotion units")
            result["transaction_entry_state"] = "RESUME_PRECOMMIT"
        else:
            audit = static_audit()
            result["static_audit"] = audit
            if not audit["session_a_execution_authorized"]:
                raise GateError("SESSION_A_STATIC_HOLD", "static audit does not authorize a new Session-A build", audit)
            stage_root = (ATTEMPTS / attempt_id / "candidate").resolve()
            if stage_root.exists() or any(path.exists() for path in final_output_paths()) or PACK_ROOT.exists():
                raise GateError("NEW_TRANSACTION_DESTINATION_COLLISION", "new transaction requires absent staging and final release targets", {"stage_root": norm(stage_root)})
            units = []
            result["transaction_entry_state"] = "PENDING_NEW"

        result["memory_samples_gib"] = base.memory_gate()
        sw, types, pythoncom, session = attach_explicit_empty(execution_g0)
        result["solidworks"] = session
        if precommit is None:
            bom_mass = build_bom_and_mass(sw, stage_root, loop1e, types, pythoncom)
            digital = build_final_digital_thread(stage_root, loop1e, loop2)
            claims = build_claims(stage_root)
            drawings = build_drawings(sw, stage_root, types, pythoncom)
            package = build_pack_and_go_equivalent(sw, stage_root, contract["dependency_paths"], types, pythoncom)
            build = {
                "bom_mass": bom_mass,
                "digital_thread": digital,
                "claims": claims,
                "drawings": drawings,
                "pack_and_go": package,
                "accepted_urdf_written": False,
                "q_authority_written": False,
                "cad_source_files_written": 0,
            }
            staging_cold = cold_release_set(sw, stage_root, loop1e, contract["dependency_paths"], types, pythoncom)
            units = promotion_units(stage_root)
            precommit = precommit_payload(attempt_id, stage_root, execution_g0, units, build, staging_cold)
            write_json_once(PRECOMMIT, precommit)
        else:
            # A resumed precommit was already cold-proved.  Recheck every
            # staging/promoted byte against that immutable precommit below.
            build = dict(precommit["build"])
            staging_cold = dict(precommit["staging_cold_reopen"])
        result["precommit"] = file_fact(PRECOMMIT)
        promotions = promote_units(units)
        result["promotions"] = promotions
        final_cold = cold_release_set(sw, None, loop1e, contract["dependency_paths"], types, pythoncom)
        close_owned(sw)
        protected_post = protected_snapshot()
        if protected_pre != protected_post:
            raise GateError("SESSION_A_PROTECTED_DRIFT", "protected source assets changed during release build", {"pre": protected_pre, "post": protected_post})
        if sha256(SCRIPT) != precommit["script"]["sha256"]:
            raise GateError("SESSION_A_SCRIPT_TOCTOU", "release builder changed after precommit")
        output_audit = audit_release_outputs()
        if not output_audit["pass"]:
            raise GateError("SESSION_A_OUTPUT_AUDIT_FAIL", "promoted release output audit failed", output_audit)
        checkpoint = {
            "schema": "F3R2_V5_LOOP3_R2B_SESSION_A_CHECKPOINT_V1",
            "timestamp_utc": utc_now(),
            "script": file_fact(SCRIPT),
            "execution_g0": execution_g0,
            "solidworks": session,
            "precommit": file_fact(PRECOMMIT),
            "loop1e_receipt": file_fact(LOOP1E_RECEIPT),
            "loop2_receipt": file_fact(LOOP2_RECEIPT),
            "promotions": promotions,
            "final_cold_reopen": final_cold,
            "release_identity": release_identity(),
            "protected_pre": protected_pre,
            "protected_post": protected_post,
            "accepted_urdf_sha256_pre": ACCEPTED_URDF_SHA256,
            "accepted_urdf_sha256_post": sha256(ACCEPTED_URDF),
            "accepted_urdf_overwritten": False,
            "solidworks_document_count_after_cleanup": int(base.value(sw, "GetDocumentCount")),
            "active_doc_after_cleanup_is_null": base.value(sw, "ActiveDoc") is None,
            "classification": CLASSIFICATION,
            "holds": list(REQUIRED_HOLDS),
            "verdict": "V5_LOOP3_R2B_SESSION_A_RELEASE_BUILD_COLD_REOPEN_PASS",
        }
        write_json_once(SESSION_A_CHECKPOINT, checkpoint)
        print(json.dumps({"verdict": checkpoint["verdict"], "checkpoint": file_fact(SESSION_A_CHECKPOINT), "pid": session["pid"], "drawing_pairs": 11, "package_dependency_count": len(contract["dependency_paths"])}, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except Exception as exc:
        result.update({"timestamp_end_utc": utc_now(), "verdict": getattr(exc, "code", "SESSION_A_UNEXPECTED_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", None), "traceback": traceback.format_exc()})
        failed = failure_receipt("SESSION_A", result)
        if failed:
            result["failure_receipt"] = failed
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), file=sys.stderr)
        return 3
    finally:
        if sw is not None:
            try:
                close_owned(sw)
            except Exception:
                pass
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def session_pair_is_fresh(session_a: Mapping[str, Any], session_b: Mapping[str, Any]) -> bool:
    try:
        return (
            int(session_a["pid"]) != int(session_b["pid"])
            and abs(float(session_a["process_create_time_epoch"]) - float(session_b["process_create_time_epoch"])) > 1.0e-6
            and int(session_b["document_count"]) == 0
            and session_b["active_doc_is_null"] is True
        )
    except Exception:
        return False


def acceptance_rows() -> List[Dict[str, Any]]:
    evidence = (
        ("LOOP1E_R2B_TOP", LOOP1E_RECEIPT, "EXACT_11_TOP_CONFIGS_AND_2X7_SIDE_READBACK"),
        ("LOOP2_R2B_CLEARANCE", LOOP2_RECEIPT, "EXACT_7X3_STATIC_PLUS_SOLAR_ONLY_SWEEP_PASS"),
        ("EXTERNAL_MECHANICAL_MASS", MASS_SUMMARY, "EXTERNAL_ONLY_ACCEPTED_URDF_UNCHANGED"),
        ("NATIVE_DRAWINGS", DRAWING_REGISTER, "EXACT_11_SLDDRW_AND_11_PDF"),
        ("NATIVE_BOM", BOM, "DYNAMIC_TOP_OCCURRENCE_BOM"),
        ("FINAL_DIGITAL_THREAD", FINAL_DIGITAL_THREAD, "R2B_FINAL_STATE_THREAD"),
        ("PACK_AND_GO", PACK_PROOF, "DYNAMIC_LOOP1E_LEDGER_SELF_CONTAINED"),
        ("SESSION_A", SESSION_A_CHECKPOINT, "BUILD_AND_COLD_REOPEN_PASS"),
        ("SESSION_B", SESSION_B_CHECKPOINT, "FRESH_PID_READ_ONLY_COLD_REOPEN_PASS"),
        ("CLAIM_BOUNDARY", CLAIMS, "COMPETITION_PROTOTYPE_HOLDS_ECR_ONLY"),
    )
    return [{"gate_id": gate, "status": "PASS", "release_blocking": "true", "evidence_path": norm(path), "evidence_sha256": sha256(path), "detail": detail} for gate, path, detail in evidence]


def final_manifest_paths() -> List[Path]:
    paths = [
        SCRIPT, TOP, LOOP1E_RECEIPT, LOOP2_RECEIPT, LOOP2_RESULTS_JSON, LOOP2_RESULTS_CSV,
        LOOP2_CHECKPOINT, LOOP2_MANIFEST, PRECOMMIT, SESSION_A_CHECKPOINT,
        SESSION_B_CHECKPOINT, ACCEPTANCE_MATRIX, *final_output_paths(),
        *(path for _name, path, _expected in FIXED_INPUTS),
        *(Path(fact["path"]) for fact in tree_facts(PACK_ROOT)),
    ]
    unique = {normcase(path): path.resolve() for path in paths}
    missing = [norm(path) for path in unique.values() if not path.is_file()]
    if missing:
        raise GateError("FINAL_MANIFEST_INPUT_MISSING", "final release manifest input is missing", {"missing": missing})
    return sorted(unique.values(), key=lambda path: norm(path).lower())


def manifest_text(paths: Sequence[Path]) -> str:
    lines = []
    for path in paths:
        label = path.relative_to(RUN_ROOT).as_posix() if path_inside(path, RUN_ROOT) else norm(path)
        lines.append(f"{sha256(path)}  {path.stat().st_size}  {label}")
    return "\n".join(sorted(lines)) + "\n"


def verify_session_b(args: argparse.Namespace) -> int:
    result: Dict[str, Any] = {"schema": "F3R2_V5_LOOP3_R2B_SESSION_B_RUNTIME_V1", "timestamp_start_utc": utc_now(), "stage": "VERIFY_SESSION_B"}
    sw = types = pythoncom = None
    try:
        if FINAL_RECEIPT.is_file():
            payload = load_json(FINAL_RECEIPT)
            if payload.get("verdict") != FINAL_VERDICT:
                raise GateError("FINAL_RECEIPT_DRIFT", "existing final receipt is not the final closed verdict")
            print(json.dumps({"verdict": payload["verdict"], "receipt": file_fact(FINAL_RECEIPT)}, ensure_ascii=False, indent=2, allow_nan=False))
            return 0
        execution_g0 = validate_execution_g0(args.expected_pid, Path(args.g0_receipt), args.g0_sha256)
        result["execution_g0"] = execution_g0
        loop1e, _loop2, contract = bound_upstream()
        if not SESSION_A_CHECKPOINT.is_file():
            raise GateError("SESSION_A_CHECKPOINT_MISSING", "fresh Session B requires the immutable Session-A checkpoint")
        session_a = load_json(SESSION_A_CHECKPOINT)
        if not (
            session_a.get("schema") == "F3R2_V5_LOOP3_R2B_SESSION_A_CHECKPOINT_V1"
            and session_a.get("verdict") == "V5_LOOP3_R2B_SESSION_A_RELEASE_BUILD_COLD_REOPEN_PASS"
            and session_a.get("script", {}).get("sha256") == sha256(SCRIPT)
        ):
            raise GateError("SESSION_A_CHECKPOINT_SEMANTIC_FAIL", "Session-A checkpoint is not bound to this release script")
        output_audit = audit_release_outputs()
        if not output_audit["pass"]:
            raise GateError("SESSION_B_OUTPUT_AUDIT_FAIL", "release outputs are not complete before fresh Session B", output_audit)
        protected_pre = protected_snapshot()
        identity_pre = release_identity()
        result["memory_samples_gib"] = base.memory_gate()
        sw, types, pythoncom, session = attach_explicit_empty(execution_g0)
        result["solidworks"] = session
        if not session_pair_is_fresh(session_a.get("solidworks", {}), session):
            raise GateError("SESSION_B_NOT_FRESH", "Session B is not a distinct PID/creation-time identity from Session A", {"session_a": session_a.get("solidworks"), "session_b": session})
        cold = cold_release_set(sw, None, loop1e, contract["dependency_paths"], types, pythoncom)
        close_owned(sw)
        protected_post = protected_snapshot()
        identity_post = release_identity()
        if protected_pre != protected_post or identity_pre != identity_post or identity_pre != session_a.get("release_identity"):
            raise GateError("SESSION_B_ZERO_MUTATION_FAIL", "fresh read-only Session B changed or disagreed with Session-A release identity", {"protected_equal": protected_pre == protected_post, "identity_pre_post_equal": identity_pre == identity_post, "identity_session_a_equal": identity_pre == session_a.get("release_identity")})
        checkpoint = {
            "schema": "F3R2_V5_LOOP3_R2B_SESSION_B_CHECKPOINT_V1",
            "timestamp_utc": utc_now(),
            "script": file_fact(SCRIPT),
            "execution_g0": execution_g0,
            "session_a_checkpoint": file_fact(SESSION_A_CHECKPOINT),
            "solidworks": session,
            "fresh_process_from_session_a": True,
            "read_only_cold_reopen": cold,
            "release_identity_pre": identity_pre,
            "release_identity_post": identity_post,
            "protected_pre": protected_pre,
            "protected_post": protected_post,
            "accepted_urdf_overwritten": False,
            "solidworks_document_count_after_cleanup": int(base.value(sw, "GetDocumentCount")),
            "active_doc_after_cleanup_is_null": base.value(sw, "ActiveDoc") is None,
            "verdict": "V5_LOOP3_R2B_FRESH_SESSION_B_ZERO_MUTATION_COLD_REOPEN_PASS",
        }
        write_json_once(SESSION_B_CHECKPOINT, checkpoint)
        rows = acceptance_rows()
        if len(rows) != 10 or any(row["status"] != "PASS" for row in rows):
            raise GateError("ACCEPTANCE_MATRIX_FAIL", "acceptance matrix is not exact all-PASS")
        write_csv_once(ACCEPTANCE_MATRIX, ACCEPTANCE_FIELDS, rows)
        write_text_once(FINAL_MANIFEST, manifest_text(final_manifest_paths()))
        final = {
            "schema": "F3R2_V5_LOOP3_R2B_RELEASE_RECEIPT_V1",
            "timestamp_start_utc": result["timestamp_start_utc"],
            "timestamp_end_utc": utc_now(),
            "script": file_fact(SCRIPT),
            "loop1e_receipt": file_fact(LOOP1E_RECEIPT),
            "loop2_receipt": file_fact(LOOP2_RECEIPT),
            "session_a_checkpoint": file_fact(SESSION_A_CHECKPOINT),
            "session_b_checkpoint": file_fact(SESSION_B_CHECKPOINT),
            "acceptance_matrix": file_fact(ACCEPTANCE_MATRIX),
            "manifest": file_fact(FINAL_MANIFEST),
            "native_slddrw_count": 11,
            "pdf_count": 11,
            "top_configuration_count": 11,
            "solar_state_count_per_side": 7,
            "release_packaging_class": "REGISTERED_EQUIVALENT_PACK_AND_GO",
            "native_getpackandgo_claimed": False,
            "getpackandgo_unavailable_evidence": "D-F3R1-01_GENERATED_COM_BINDING_INVOKETYPES_207",
            "pack_dependency_count_dynamic": len(contract["dependency_paths"]),
            "pack_missing_reference_count": 0,
            "pack_escaped_reference_count": 0,
            "external_mechanical_mass_only": True,
            "accepted_urdf_overwritten": False,
            "q_authority_written": False,
            "classification": CLASSIFICATION,
            "prohibited_claims": {name: False for name in PROHIBITED_CLAIMS},
            "holds": list(REQUIRED_HOLDS),
            "mechanical_authoring_after_gate": "ECR_ONLY",
            "receipt_written_last": True,
            "final_gate_eligible": True,
            "verdict": FINAL_VERDICT,
        }
        write_json_once(FINAL_RECEIPT, final)
        print(json.dumps({"verdict": FINAL_VERDICT, "receipt": file_fact(FINAL_RECEIPT), "manifest": file_fact(FINAL_MANIFEST), "session_b_pid": session["pid"], "solidworks_document_count": int(base.value(sw, "GetDocumentCount"))}, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except Exception as exc:
        result.update({"timestamp_end_utc": utc_now(), "verdict": getattr(exc, "code", "SESSION_B_UNEXPECTED_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", None), "traceback": traceback.format_exc()})
        failed = failure_receipt("SESSION_B", result)
        if failed:
            result["failure_receipt"] = failed
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), file=sys.stderr)
        return 3
    finally:
        if sw is not None:
            try:
                close_owned(sw)
            except Exception:
                pass
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F3R2 V5 Loop3 R2B attach-only release builder/verifier")
    parser.add_argument("command", nargs="?", default="audit", choices=("audit", "self-test", "build-session-a", "verify-session-b"))
    parser.add_argument("--expected-pid", type=int)
    parser.add_argument("--g0-receipt")
    parser.add_argument("--g0-sha256")
    parser.add_argument("--attempt-id")
    args = parser.parse_args(argv)
    if args.command in {"build-session-a", "verify-session-b"}:
        if not args.expected_pid or not args.g0_receipt or not args.g0_sha256:
            parser.error(f"{args.command} requires --expected-pid --g0-receipt --g0-sha256")
    if args.command == "build-session-a" and not args.attempt_id:
        parser.error("build-session-a requires --attempt-id")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        report = static_audit()
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if report["verdict"] == "V5_LOOP3_R2B_STATIC_HOLD" else 0
    if args.command == "self-test":
        report = self_test()
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if report["pass"] else 2
    if args.command == "build-session-a":
        return build_session_a(args)
    return verify_session_b(args)


if __name__ == "__main__":
    sys.exit(main())
