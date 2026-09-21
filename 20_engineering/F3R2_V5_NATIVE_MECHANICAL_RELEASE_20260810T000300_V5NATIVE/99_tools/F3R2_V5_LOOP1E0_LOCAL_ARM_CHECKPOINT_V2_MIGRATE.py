#!/usr/bin/env python3
"""Create the independent Loop1E0 local-arm checkpoint V2.

This is a pure-filesystem evidence migration.  It does not import a COM
package, attach to SOLIDWORKS, open CAD through SOLIDWORKS, or mutate CAD.

The existing V1 checkpoint is accepted only by its exact raw SHA-256.  Its
complete JSON payload is then validated structurally against the immutable
donor, the current localized eleven-file tree, the accepted URDF, both saved
arm configurations, the suppressed legacy gripper, and all six native driver
and cold-readback ledgers.  The complete V1 payload plus the independently
recomputed file/URDF facts form a canonical contract whose SHA-256 is stable
and deliberately independent of the later Loop1E top-builder source hash.

The V1 checkpoint and every CAD/URDF input are read-only.  ``execute`` creates
exactly one write-once V2 checkpoint through a same-directory atomic,
no-replace promotion.  An existing target is never overwritten or resumed.
"""

from __future__ import annotations

import argparse
import ast
import ctypes
import hashlib
import json
import math
import os
import sys
import traceback
import uuid
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, Iterator, List, Mapping, NoReturn, Sequence, Tuple


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
RUN_ROOT = ENGINEERING / "F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
VALIDATION = RUN_ROOT / "13_validation"

V1_CHECKPOINT = VALIDATION / "V5_LOOP1E0_LOCAL_ARM_NO_LEGACY_GRIPPER_CHECKPOINT.json"
V2_CHECKPOINT = VALIDATION / "V5_LOOP1E0_LOCAL_ARM_INDEPENDENT_CHECKPOINT_V2.json"

LOCAL_ARM_ROOT = RUN_ROOT / "03_top_assembly/_native_donor_local/B51_ARTICULATED_20260728T008"
LOCAL_ARM = LOCAL_ARM_ROOT / "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"

DONOR_ROOT = ENGINEERING / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/B601_ARM_B51_COPY"
DONOR_ARM = DONOR_ROOT / "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"

ACCEPTED_URDF = ENGINEERING / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"

EXPECTED_V1_SHA256 = "E2A6113E48B07600ACA1B6BB60AAD249D20505922B9FA232A5BA394557E1E9BC"
EXPECTED_V1_PRODUCER_SHA256 = "98D746893152B2099BF01F7D2A3499C14D9B81F194595351216C50CE93EC0CF6"
EXPECTED_LOCAL_ARM_SHA256 = "D794CCFB52CFBF858B99172D6A41119B56271ECC3B3E018E48C30FA19703947A"
EXPECTED_ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
EXPECTED_DONOR_ARM_SHA256 = "597C297526BC4111C3424535139B8A1C93906E7A799FF5346D030700FEF1A32F"

EXPECTED_V1_SCHEMA = "F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V1"
EXPECTED_V1_VERDICT = "V5_LOOP1E0_LOCAL_ARM_NO_LEGACY_GRIPPER_WITH_SIX_NATIVE_LIMIT_ANGLE_DRIVERS_PASS"
V2_SCHEMA = "F3R2_V5_LOOP1E0_LOCAL_ARM_INDEPENDENT_CHECKPOINT_V2"
V2_VERDICT = "V5_LOOP1E0_LOCAL_ARM_INDEPENDENT_CHECKPOINT_V2_PASS"
CONTRACT_SCHEMA = "F3R2_V5_LOOP1E0_LOCAL_ARM_INDEPENDENT_CONTRACT_V1"
MUTEX_NAME = r"Local\F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATE_V1"

ARM_CONFIGS: Tuple[str, ...] = ("默认", "STOWED_O13V3")
ARM_CONFIGURATION_Q_DEG: Mapping[str, Tuple[float, ...]] = {
    "默认": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "STOWED_O13V3": (145.572, -168.0, -57.0, -41.143, -20.954, -3.0),
}

V1_TOP_KEYS = {
    "schema",
    "timestamp_utc",
    "script_sha256",
    "accepted_urdf_sha256",
    "source",
    "local_arm",
    "copy_proof",
    "reference_prebind",
    "reference_repairs",
    "native_joint_drivers",
    "legacy_gripper_file",
    "configurations",
    "cold_open",
    "verdict",
}

DRIVER_KEYS = {
    "joint",
    "feature_name",
    "dimension_full_name",
    "female_component_leaf",
    "male_component_leaf",
    "selected_plane_features",
    "selected_owner_name2",
    "add_mate_error_status",
    "mate_type",
    "advanced",
    "flip",
    "native_probe_delta_rad",
    "accepted_axis_projected_delta_rad",
    "transverse_rotation_rad",
    "sign",
    "zero_offset_rad",
    "accepted_axis_in_parent",
    "drive_mechanism",
    "pass",
    "accepted_parent_link",
    "accepted_child_link",
    "accepted_axis_xyz",
    "accepted_origin_xyz",
    "accepted_origin_rpy",
    "accepted_lower_rad",
    "accepted_upper_rad",
    "native_minimum_rad",
    "native_maximum_rad",
    "driver_generation_stage",
    "preexisting_b51_hinge_mate_used_as_driver",
    "configuration_seed_readback",
    "cold_reopen_verified",
    "cold_reopen",
}

EXPECTED_RELATIVE_FILES = {
    "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM",
    "inputs/vendor_link_parts/B51_REF_base_link_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_gripper_detail_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link1_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link2_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link3_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link4_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link5_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link6_LINKLOCAL.SLDPRT",
    "parts/B51_REV_DATUM_FEMALE.SLDPRT",
    "parts/B51_REV_DATUM_MALE.SLDPRT",
}

EXPECTED_COMPONENT_LEAVES = {
    "B51_REF_base_link_LINKLOCAL-1",
    "B51_REF_gripper_detail_LINKLOCAL-1",
    *(f"B51_REF_link{index}_LINKLOCAL-1" for index in range(1, 7)),
    *(f"B51_REV_DATUM_FEMALE-{index}" for index in range(1, 7)),
    *(f"B51_REV_DATUM_MALE-{index}" for index in range(1, 7)),
}


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Any = None):
        super().__init__(message)
        self.code = code
        self.detail = detail


def fail(code: str, message: str, detail: Any = None) -> NoReturn:
    raise GateError(code, message, detail)


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        fail("FILE_FACT_MISSING", "required file is missing", {"path": norm(resolved)})
    return {"path": norm(resolved), "bytes": resolved.stat().st_size, "sha256": sha256(resolved)}


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        fail("CANONICAL_JSON_FAIL", "contract is not canonical-JSON serializable", {"exception": repr(exc)})
    return text.encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


def _object_no_duplicates(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            fail("JSON_DUPLICATE_KEY", "JSON object contains a duplicate key", {"key": key})
        output[key] = value
    return output


def _reject_json_constant(value: str) -> NoReturn:
    fail("JSON_NONFINITE_CONSTANT", "JSON contains a non-finite numeric constant", {"value": value})


def strict_json_load(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        fail("JSON_FILE_MISSING", "required JSON file is missing", {"path": norm(path)})
    try:
        value = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_json_constant,
        )
    except GateError:
        raise
    except Exception as exc:
        fail("JSON_PARSE_FAIL", "JSON cannot be parsed strictly", {"path": norm(path), "exception": repr(exc)})
    if not isinstance(value, dict):
        fail("JSON_ROOT_FAIL", "JSON root must be an object", {"path": norm(path)})
    return value


def require_exact_keys(value: Any, expected: Iterable[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        fail("OBJECT_TYPE_FAIL", "value must be a JSON object", {"label": label, "type": type(value).__name__})
    actual, wanted = set(value), set(expected)
    if actual != wanted:
        fail("OBJECT_KEY_SET_FAIL", "JSON object key set is not exact", {"label": label, "actual": sorted(actual), "expected": sorted(wanted)})
    return value


def require_list(value: Any, length: int, label: str) -> List[Any]:
    if not isinstance(value, list) or len(value) != length:
        fail("LIST_SHAPE_FAIL", "value is not a list of the exact required length", {"label": label, "length": len(value) if isinstance(value, list) else None, "expected_length": length})
    return value


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail("NUMBER_TYPE_FAIL", "value is not a real number", {"label": label, "value": value})
    result = float(value)
    if not math.isfinite(result):
        fail("NUMBER_NONFINITE_FAIL", "value is not finite", {"label": label, "value": value})
    return result


def finite_vector(value: Any, length: int, label: str) -> List[float]:
    return [finite_number(item, f"{label}[{index}]") for index, item in enumerate(require_list(value, length, label))]


def same_numbers(first: Sequence[float], second: Sequence[float], tolerance: float = 1.0e-9) -> bool:
    return len(first) == len(second) and all(abs(float(left) - float(right)) <= tolerance for left, right in zip(first, second))


def require_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail("TIMESTAMP_TYPE_FAIL", "timestamp must be a non-empty string", {"label": label})
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        fail("TIMESTAMP_PARSE_FAIL", "timestamp is not ISO-8601", {"label": label, "value": value, "exception": repr(exc)})
    if parsed.tzinfo is None:
        fail("TIMESTAMP_ZONE_FAIL", "timestamp must include a timezone", {"label": label, "value": value})
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_fact_payload(payload: Any, expected: Mapping[str, Any], label: str) -> None:
    row = require_exact_keys(payload, {"path", "bytes", "sha256"}, label)
    normalized = {
        "path": norm(Path(str(row["path"]))),
        "bytes": row["bytes"],
        "sha256": str(row["sha256"]).upper(),
    }
    if normalized != dict(expected):
        fail("FILE_FACT_PAYLOAD_FAIL", "embedded file fact differs from recomputed fact", {"label": label, "actual": normalized, "expected": expected})


def tree_files(root: Path) -> List[Path]:
    if not root.is_dir():
        fail("TREE_ROOT_MISSING", "required tree root is missing", {"root": norm(root)})
    return sorted((path.resolve() for path in root.rglob("*") if path.is_file()), key=lambda item: norm(item).casefold())


def relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        fail("PATH_ESCAPE", "path escapes its required root", {"path": norm(path), "root": norm(root)})


def checked_relative(text: Any, label: str) -> str:
    if not isinstance(text, str) or not text:
        fail("RELATIVE_PATH_TYPE_FAIL", "relative path must be a non-empty string", {"label": label})
    normalized = text.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts or normalized != candidate.as_posix():
        fail("RELATIVE_PATH_FAIL", "relative path is not canonical or attempts traversal", {"label": label, "path": text})
    return normalized


def source_policy_audit() -> Dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(Path(__file__)))
    except SyntaxError as exc:
        fail("SOURCE_PARSE_FAIL", "migration source is not valid Python", {"exception": repr(exc)})
    imports: List[str] = []
    calls: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(str(node.module or ""))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    forbidden_modules = {"win32com", "pythoncom", "comtypes", "subprocess"}
    forbidden_calls = {"Dispatch", "DispatchEx", "GetActiveObject", "CoInitialize", "OpenDoc6", "Save3", "SaveAs"}
    bad_modules = sorted(name for name in imports if name.split(".")[0] in forbidden_modules)
    bad_calls = sorted(set(calls) & forbidden_calls)
    if bad_modules or bad_calls:
        fail("SOURCE_POLICY_FAIL", "migration source contains a prohibited COM/CAD/process API", {"modules": bad_modules, "calls": bad_calls})
    return {
        "source": file_fact(Path(__file__)),
        "parsed_with_ast": True,
        "imported_modules": sorted(set(imports)),
        "forbidden_modules_present": [],
        "forbidden_calls_present": [],
        "solidworks_or_com_access": False,
        "cad_mutation_calls": 0,
        "pass": True,
    }


def parse_triple(text: Any, label: str) -> List[float]:
    try:
        values = [float(item) for item in str(text or "").split()]
    except ValueError as exc:
        fail("URDF_VECTOR_PARSE_FAIL", "URDF vector contains a non-number", {"label": label, "text": text, "exception": repr(exc)})
    if len(values) != 3 or not all(math.isfinite(item) for item in values):
        fail("URDF_VECTOR_SHAPE_FAIL", "URDF vector is not a finite triple", {"label": label, "values": values})
    return values


def validate_accepted_urdf() -> Dict[str, Any]:
    fact = file_fact(ACCEPTED_URDF)
    if fact["sha256"] != EXPECTED_ACCEPTED_URDF_SHA256:
        fail("ACCEPTED_URDF_HASH_FAIL", "accepted URDF raw bytes differ", {"actual": fact, "expected_sha256": EXPECTED_ACCEPTED_URDF_SHA256})
    try:
        root = ET.parse(ACCEPTED_URDF).getroot()
    except Exception as exc:
        fail("ACCEPTED_URDF_PARSE_FAIL", "accepted URDF XML cannot be parsed", {"exception": repr(exc)})
    rows: List[Dict[str, Any]] = []
    for element in root.findall("joint"):
        if element.get("type") != "revolute":
            continue
        parent, child = element.find("parent"), element.find("child")
        origin, axis, limit = element.find("origin"), element.find("axis"), element.find("limit")
        if None in (parent, child, origin, axis, limit):
            fail("ACCEPTED_URDF_JOINT_FIELD_FAIL", "revolute joint is missing a required element", {"joint": element.get("name")})
        try:
            lower, upper = float(str(limit.get("lower"))), float(str(limit.get("upper")))
        except ValueError as exc:
            fail("ACCEPTED_URDF_LIMIT_PARSE_FAIL", "joint limit is not numeric", {"joint": element.get("name"), "exception": repr(exc)})
        if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
            fail("ACCEPTED_URDF_LIMIT_FAIL", "joint limits are invalid", {"joint": element.get("name"), "lower": lower, "upper": upper})
        rows.append({
            "joint": str(element.get("name")),
            "parent": str(parent.get("link")),
            "child": str(child.get("link")),
            "origin_xyz": parse_triple(origin.get("xyz"), f"{element.get('name')}.origin_xyz"),
            "origin_rpy": parse_triple(origin.get("rpy"), f"{element.get('name')}.origin_rpy"),
            "axis_xyz": parse_triple(axis.get("xyz"), f"{element.get('name')}.axis_xyz"),
            "lower_rad": lower,
            "upper_rad": upper,
        })
    if [row["joint"] for row in rows] != [f"joint{index}" for index in range(1, 7)]:
        fail("ACCEPTED_URDF_CHAIN_FAIL", "accepted URDF is not the exact ordered six-revolute-joint chain", {"joints": [row["joint"] for row in rows]})
    for row in rows:
        norm_axis = math.sqrt(sum(value * value for value in row["axis_xyz"]))
        if abs(norm_axis - 1.0) > 1.0e-9:
            fail("ACCEPTED_URDF_AXIS_FAIL", "accepted joint axis is not unit length", {"joint": row["joint"], "norm": norm_axis})
    return {"fact": fact, "joints": rows, "pass": True}


def validate_copy_and_trees(v1: Mapping[str, Any]) -> Dict[str, Any]:
    copy_proof = require_exact_keys(v1["copy_proof"], {"schema", "copy_rows", "local_arm", "protected_source"}, "v1.copy_proof")
    if copy_proof["schema"] != "F3R2_V5_LOOP1E0_LOCAL_ARM_STAGED_V1":
        fail("COPY_PROOF_SCHEMA_FAIL", "V1 copy-proof schema differs", {"schema": copy_proof["schema"]})
    rows = require_list(copy_proof["copy_rows"], 11, "v1.copy_proof.copy_rows")
    row_by_relative: Dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(rows):
        row = require_exact_keys(raw, {"relative", "bytes", "source_sha256", "target_sha256"}, f"copy_rows[{index}]")
        relative = checked_relative(row["relative"], f"copy_rows[{index}].relative")
        if relative in row_by_relative:
            fail("COPY_PROOF_DUPLICATE_RELATIVE", "copy proof contains a duplicate relative path", {"relative": relative})
        if isinstance(row["bytes"], bool) or not isinstance(row["bytes"], int) or row["bytes"] <= 0:
            fail("COPY_PROOF_BYTES_FAIL", "copy row bytes is not a positive integer", {"relative": relative, "bytes": row["bytes"]})
        source_hash, target_hash = str(row["source_sha256"]).upper(), str(row["target_sha256"]).upper()
        if len(source_hash) != 64 or len(target_hash) != 64 or any(char not in "0123456789ABCDEF" for char in source_hash + target_hash):
            fail("COPY_PROOF_HASH_FORMAT_FAIL", "copy row hash is not uppercase SHA-256", {"relative": relative})
        if source_hash != target_hash:
            fail("COPY_PROOF_PAIRWISE_HASH_FAIL", "staged copy row did not preserve source bytes", {"relative": relative, "source_sha256": source_hash, "target_sha256": target_hash})
        row_by_relative[relative] = row
    if set(row_by_relative) != EXPECTED_RELATIVE_FILES:
        fail("COPY_PROOF_FILE_SET_FAIL", "copy proof does not contain the exact eleven-file arm tree", {"actual": sorted(row_by_relative), "expected": sorted(EXPECTED_RELATIVE_FILES)})

    source_files = tree_files(DONOR_ROOT)
    localized_files = tree_files(LOCAL_ARM_ROOT)
    source_relative = {relative_posix(path, DONOR_ROOT) for path in source_files}
    localized_relative = {relative_posix(path, LOCAL_ARM_ROOT) for path in localized_files}
    if source_relative != EXPECTED_RELATIVE_FILES or localized_relative != EXPECTED_RELATIVE_FILES:
        fail("ARM_TREE_FILE_SET_FAIL", "donor or localized tree contains a missing/extra file", {"source": sorted(source_relative), "localized": sorted(localized_relative), "expected": sorted(EXPECTED_RELATIVE_FILES)})

    source_facts: List[Dict[str, Any]] = []
    localized_facts: List[Dict[str, Any]] = []
    for relative in sorted(EXPECTED_RELATIVE_FILES):
        row = row_by_relative[relative]
        source = DONOR_ROOT / Path(relative)
        localized = LOCAL_ARM_ROOT / Path(relative)
        source_fact = file_fact(source)
        localized_fact = file_fact(localized)
        expected_copy = {"bytes": int(row["bytes"]), "sha256": str(row["source_sha256"]).upper()}
        if {"bytes": source_fact["bytes"], "sha256": source_fact["sha256"]} != expected_copy:
            fail("DONOR_COPY_ROW_DRIFT", "donor file differs from the pinned V1 copy row", {"relative": relative, "actual": source_fact, "expected": expected_copy})
        if relative == "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM":
            if localized_fact["sha256"] != EXPECTED_LOCAL_ARM_SHA256 or localized_fact["bytes"] != int(v1["local_arm"]["bytes"]):
                fail("LOCAL_ARM_FINAL_FACT_FAIL", "localized arm assembly differs from the final V1 fact", {"actual": localized_fact, "expected_sha256": EXPECTED_LOCAL_ARM_SHA256})
        elif {"bytes": localized_fact["bytes"], "sha256": localized_fact["sha256"]} != expected_copy:
            fail("LOCALIZED_COPY_ROW_DRIFT", "localized dependency differs from the pinned V1 copy row", {"relative": relative, "actual": localized_fact, "expected": expected_copy})
        source_facts.append({"relative": relative, **source_fact})
        localized_facts.append({"relative": relative, **localized_fact})

    donor_fact = file_fact(DONOR_ARM)
    local_arm_fact = file_fact(LOCAL_ARM)
    if donor_fact["sha256"] != EXPECTED_DONOR_ARM_SHA256:
        fail("DONOR_ARM_HASH_FAIL", "protected donor arm differs", {"actual": donor_fact, "expected_sha256": EXPECTED_DONOR_ARM_SHA256})
    if local_arm_fact["sha256"] != EXPECTED_LOCAL_ARM_SHA256:
        fail("LOCAL_ARM_HASH_FAIL", "localized arm differs", {"actual": local_arm_fact, "expected_sha256": EXPECTED_LOCAL_ARM_SHA256})
    validate_fact_payload(v1["source"], donor_fact, "v1.source")
    validate_fact_payload(v1["local_arm"], local_arm_fact, "v1.local_arm")
    validate_fact_payload(copy_proof["protected_source"], donor_fact, "v1.copy_proof.protected_source")

    assembly_copy_row = row_by_relative["assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"]
    historical_staged_fact = {
        "path": norm(LOCAL_ARM),
        "bytes": int(assembly_copy_row["bytes"]),
        "sha256": str(assembly_copy_row["target_sha256"]).upper(),
    }
    validate_fact_payload(copy_proof["local_arm"], historical_staged_fact, "v1.copy_proof.local_arm")
    return {
        "copy_proof": copy_proof,
        "donor_arm": donor_fact,
        "local_arm": local_arm_fact,
        "donor_tree_files": source_facts,
        "localized_tree_files": localized_facts,
        "copy_row_count": 11,
        "pass": True,
    }


def expected_component_path(leaf: str) -> Path:
    if leaf == "B51_REF_base_link_LINKLOCAL-1":
        return LOCAL_ARM_ROOT / "inputs/vendor_link_parts/B51_REF_base_link_LINKLOCAL.SLDPRT"
    if leaf == "B51_REF_gripper_detail_LINKLOCAL-1":
        return LOCAL_ARM_ROOT / "inputs/vendor_link_parts/B51_REF_gripper_detail_LINKLOCAL.SLDPRT"
    if leaf.startswith("B51_REF_link") and leaf.endswith("_LINKLOCAL-1"):
        index_text = leaf[len("B51_REF_link") : -len("_LINKLOCAL-1")]
        if index_text in {str(index) for index in range(1, 7)}:
            return LOCAL_ARM_ROOT / f"inputs/vendor_link_parts/B51_REF_link{index_text}_LINKLOCAL.SLDPRT"
    if leaf.startswith("B51_REV_DATUM_FEMALE-") and leaf.rsplit("-", 1)[-1] in {str(index) for index in range(1, 7)}:
        return LOCAL_ARM_ROOT / "parts/B51_REV_DATUM_FEMALE.SLDPRT"
    if leaf.startswith("B51_REV_DATUM_MALE-") and leaf.rsplit("-", 1)[-1] in {str(index) for index in range(1, 7)}:
        return LOCAL_ARM_ROOT / "parts/B51_REV_DATUM_MALE.SLDPRT"
    fail("COMPONENT_LEAF_FAIL", "component leaf is outside the exact local-arm contract", {"leaf": leaf})


def validate_reference_ledgers(v1: Mapping[str, Any]) -> Dict[str, Any]:
    prebind = require_list(v1["reference_prebind"], 10, "v1.reference_prebind")
    prebind_paths: set[Path] = set()
    for index, raw in enumerate(prebind):
        row = require_exact_keys(raw, {"path", "via_short_8p3", "read_only_open"}, f"reference_prebind[{index}]")
        path = Path(str(row["path"])).resolve()
        if path in prebind_paths:
            fail("REFERENCE_PREBIND_DUPLICATE", "reference prebind path is duplicated", {"path": norm(path)})
        if path.suffix.upper() != ".SLDPRT" or LOCAL_ARM_ROOT.resolve() not in path.parents or not path.is_file():
            fail("REFERENCE_PREBIND_PATH_FAIL", "reference prebind path is not a localized SLDPRT", {"path": norm(path)})
        opened = require_exact_keys(row["read_only_open"], {"errors", "warnings", "read_only"}, f"reference_prebind[{index}].read_only_open")
        if not isinstance(row["via_short_8p3"], bool) or opened["errors"] != 0 or opened["warnings"] != 0 or opened["read_only"] is not row["via_short_8p3"]:
            fail("REFERENCE_PREBIND_OPEN_FAIL", "prebind open evidence is inconsistent", {"index": index, "row": row})
        prebind_paths.add(path)
    expected_prebind = {path for path in tree_files(LOCAL_ARM_ROOT) if path.suffix.upper() == ".SLDPRT"}
    if prebind_paths != expected_prebind:
        fail("REFERENCE_PREBIND_SET_FAIL", "prebind paths are not the exact ten localized parts", {"actual": sorted(norm(path) for path in prebind_paths), "expected": sorted(norm(path) for path in expected_prebind)})

    repairs = require_list(v1["reference_repairs"], 40, "v1.reference_repairs")
    by_configuration: Dict[str, Dict[str, Mapping[str, Any]]] = {name: {} for name in ARM_CONFIGS}
    for index, raw in enumerate(repairs):
        row = require_exact_keys(raw, {"configuration", "name2", "path"}, f"reference_repairs[{index}]")
        configuration, name2 = str(row["configuration"]), str(row["name2"])
        if configuration not in by_configuration or name2 not in EXPECTED_COMPONENT_LEAVES:
            fail("REFERENCE_REPAIR_ID_FAIL", "reference repair configuration/component is outside the exact contract", {"index": index, "configuration": configuration, "name2": name2})
        if name2 in by_configuration[configuration]:
            fail("REFERENCE_REPAIR_DUPLICATE", "reference repair repeats a component in one configuration", {"configuration": configuration, "name2": name2})
        expected = expected_component_path(name2).resolve()
        actual = Path(str(row["path"])).resolve()
        if actual != expected or not actual.is_file():
            fail("REFERENCE_REPAIR_PATH_FAIL", "reference repair path differs from exact localized ownership", {"configuration": configuration, "name2": name2, "actual": norm(actual), "expected": norm(expected)})
        by_configuration[configuration][name2] = row
    for configuration, rows in by_configuration.items():
        if set(rows) != EXPECTED_COMPONENT_LEAVES:
            fail("REFERENCE_REPAIR_SET_FAIL", "configuration reference repair set is not exact", {"configuration": configuration, "actual": sorted(rows), "expected": sorted(EXPECTED_COMPONENT_LEAVES)})
    return {
        "reference_prebind": prebind,
        "reference_repairs": repairs,
        "prebind_count": 10,
        "repair_count": 40,
        "repair_count_per_configuration": {name: 20 for name in ARM_CONFIGS},
        "pass": True,
    }


def validate_drivers(v1: Mapping[str, Any], urdf_joints: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    drivers = require_list(v1["native_joint_drivers"], 6, "v1.native_joint_drivers")
    if [str(row.get("joint", "")) if isinstance(row, dict) else "" for row in drivers] != [f"joint{index}" for index in range(1, 7)]:
        fail("DRIVER_ORDER_FAIL", "native driver list is not ordered joint1..joint6")
    driver_by_joint: Dict[str, Mapping[str, Any]] = {}
    for index, (raw, accepted) in enumerate(zip(drivers, urdf_joints), start=1):
        joint = f"joint{index}"
        expected_driver_keys = DRIVER_KEYS | ({"sign_correction"} if joint in {"joint2", "joint5"} else set())
        row = require_exact_keys(raw, expected_driver_keys, f"native_joint_drivers[{index - 1}]")
        feature_name = f"V5_LOOP2_JOINT{index}_LIMIT_ANGLE"
        dimension_name = f"D1@{feature_name}@B51_B601_ARTICULATED_ENGINEERING_ARM.Assembly"
        if row["joint"] != joint or row["feature_name"] != feature_name or row["dimension_full_name"] != dimension_name:
            fail("DRIVER_IDENTITY_FAIL", "native driver feature/dimension identity differs", {"joint": joint, "row": row})
        if row["female_component_leaf"] != f"B51_REV_DATUM_FEMALE-{index}" or row["male_component_leaf"] != f"B51_REV_DATUM_MALE-{index}":
            fail("DRIVER_DATUM_OWNER_FAIL", "native driver datum owners differ", {"joint": joint})
        plane_features = require_list(row["selected_plane_features"], 2, f"{joint}.selected_plane_features")
        owners = require_list(row["selected_owner_name2"], 2, f"{joint}.selected_owner_name2")
        if any(not isinstance(item, str) or not item for item in plane_features) or owners != [f"B51_REV_DATUM_FEMALE-{index}", f"B51_REV_DATUM_MALE-{index}"]:
            fail("DRIVER_SELECTION_LEDGER_FAIL", "native driver selection ledger differs", {"joint": joint, "planes": plane_features, "owners": owners})
        if row["add_mate_error_status"] != 1 or row["mate_type"] != 6 or row["advanced"] is not True or not isinstance(row["flip"], bool):
            fail("DRIVER_MATE_CONTRACT_FAIL", "native driver is not one healthy advanced angle mate", {"joint": joint})
        probe = finite_number(row["native_probe_delta_rad"], f"{joint}.native_probe_delta_rad")
        projected = finite_number(row["accepted_axis_projected_delta_rad"], f"{joint}.accepted_axis_projected_delta_rad")
        transverse = finite_number(row["transverse_rotation_rad"], f"{joint}.transverse_rotation_rad")
        expected_probe = math.radians(0.5)
        if abs(probe - expected_probe) > 1.0e-12 or abs(projected - expected_probe) > 2.0e-10 or abs(transverse) > 1.0e-8:
            fail("DRIVER_PROBE_FAIL", "native driver probe does not remain a pure positive accepted-axis rotation", {"joint": joint, "probe": probe, "projected": projected, "transverse": transverse})
        axis_in_parent = finite_vector(row["accepted_axis_in_parent"], 3, f"{joint}.accepted_axis_in_parent")
        if abs(math.sqrt(sum(value * value for value in axis_in_parent)) - 1.0) > 1.0e-6:
            fail("DRIVER_AXIS_WITNESS_FAIL", "driver accepted axis witness is not unit length", {"joint": joint, "axis": axis_in_parent})
        if row["sign"] != 1.0 or row["zero_offset_rad"] != 0.0 or row["pass"] is not True:
            fail("DRIVER_SIGN_OR_PASS_FAIL", "driver sign/zero/pass differs", {"joint": joint})
        if joint in {"joint2", "joint5"}:
            if row["flip"] is not True or row["sign_correction"] != "FLIPPED_AFTER_DIRECTION_PROBE":
                fail("DRIVER_SIGN_CORRECTION_FAIL", "reversed datum driver lacks the exact probed sign correction", {"joint": joint, "flip": row["flip"], "sign_correction": row["sign_correction"]})
        elif row["flip"] is not False:
            fail("DRIVER_UNEXPECTED_FLIP_FAIL", "non-reversed datum driver is unexpectedly flipped", {"joint": joint, "flip": row["flip"]})
        if row["drive_mechanism"] != "DELETE_AND_RECREATE_AT_ANGLE (ModifyDefinition unreliable on this build)":
            fail("DRIVER_MECHANISM_FAIL", "driver mechanism provenance differs", {"joint": joint, "mechanism": row["drive_mechanism"]})

        scalar_pairs = (
            ("accepted_lower_rad", "lower_rad"),
            ("accepted_upper_rad", "upper_rad"),
            ("native_minimum_rad", "lower_rad"),
            ("native_maximum_rad", "upper_rad"),
        )
        if row["accepted_parent_link"] != accepted["parent"] or row["accepted_child_link"] != accepted["child"]:
            fail("DRIVER_URDF_LINK_FAIL", "driver parent/child differs from accepted URDF", {"joint": joint})
        for driver_field, urdf_field in scalar_pairs:
            if abs(finite_number(row[driver_field], f"{joint}.{driver_field}") - float(accepted[urdf_field])) > 1.0e-9:
                fail("DRIVER_URDF_LIMIT_FAIL", "driver limit differs from accepted URDF", {"joint": joint, "field": driver_field})
        for driver_field, urdf_field in (("accepted_axis_xyz", "axis_xyz"), ("accepted_origin_xyz", "origin_xyz"), ("accepted_origin_rpy", "origin_rpy")):
            if not same_numbers(finite_vector(row[driver_field], 3, f"{joint}.{driver_field}"), accepted[urdf_field]):
                fail("DRIVER_URDF_VECTOR_FAIL", "driver vector differs from accepted URDF", {"joint": joint, "field": driver_field, "actual": row[driver_field], "expected": accepted[urdf_field]})
        if row["driver_generation_stage"] != "LOOP1E_NATIVE_DRIVER_SYNTHESIS" or row["preexisting_b51_hinge_mate_used_as_driver"] is not False or row["cold_reopen_verified"] is not True:
            fail("DRIVER_PROVENANCE_FAIL", "driver generation/cold provenance differs", {"joint": joint})

        seeds = require_list(row["configuration_seed_readback"], 2, f"{joint}.configuration_seed_readback")
        seed_by_config: Dict[str, Mapping[str, Any]] = {}
        for seed_index, seed_raw in enumerate(seeds):
            seed = require_exact_keys(seed_raw, {"configuration", "native_angle_rad", "authorized_q_rad", "source_q_deg", "authority", "evidence"}, f"{joint}.configuration_seed_readback[{seed_index}]")
            configuration = str(seed["configuration"])
            if configuration in seed_by_config or configuration not in ARM_CONFIGS:
                fail("DRIVER_SEED_CONFIG_FAIL", "driver seed configuration is duplicate/unknown", {"joint": joint, "configuration": configuration})
            expected_deg = ARM_CONFIGURATION_Q_DEG[configuration][index - 1]
            expected_rad = math.radians(expected_deg)
            if abs(finite_number(seed["source_q_deg"], f"{joint}.{configuration}.source_q_deg") - expected_deg) > 1.0e-9 or abs(finite_number(seed["authorized_q_rad"], f"{joint}.{configuration}.authorized_q_rad") - expected_rad) > 1.0e-12 or abs(finite_number(seed["native_angle_rad"], f"{joint}.{configuration}.native_angle_rad") - expected_rad) > 1.0e-6:
                fail("DRIVER_SEED_VALUE_FAIL", "driver saved-configuration seed differs", {"joint": joint, "configuration": configuration, "seed": seed, "expected_deg": expected_deg})
            if seed["authority"] != "Q0_GEOMETRY_OR_PREEXISTING_ENGINEERING_STOW_SEED_NOT_LOOP2_POSE_PROOF" or seed["evidence"] != "MEASURED_PER_CONFIG_POSE_ON_ACCEPTED_AXIS":
                fail("DRIVER_SEED_AUTHORITY_FAIL", "driver seed authority/proof label differs", {"joint": joint, "configuration": configuration})
            seed_by_config[configuration] = seed
        if set(seed_by_config) != set(ARM_CONFIGS):
            fail("DRIVER_SEED_SET_FAIL", "driver seed configurations are not exact", {"joint": joint, "actual": sorted(seed_by_config)})

        cold = require_exact_keys(row["cold_reopen"], {"joint", "configurations"}, f"{joint}.cold_reopen")
        if cold["joint"] != joint:
            fail("DRIVER_COLD_JOINT_FAIL", "cold ledger joint differs", {"joint": joint, "actual": cold["joint"]})
        cold_rows = require_list(cold["configurations"], 2, f"{joint}.cold_reopen.configurations")
        cold_by_config: Dict[str, Mapping[str, Any]] = {}
        for cold_index, cold_raw in enumerate(cold_rows):
            cold_row = require_exact_keys(cold_raw, {"joint", "configuration", "feature_name", "dimension_full_name", "minimum_rad", "maximum_rad", "native_angle_rad", "feature_error_code", "feature_suppressed", "advanced_limit_angle"}, f"{joint}.cold_reopen.configurations[{cold_index}]")
            configuration = str(cold_row["configuration"])
            if configuration in cold_by_config or configuration not in ARM_CONFIGS or cold_row["joint"] != joint or cold_row["feature_name"] != feature_name or cold_row["dimension_full_name"] != dimension_name:
                fail("DRIVER_COLD_ID_FAIL", "cold driver row identity/configuration differs", {"joint": joint, "row": cold_row})
            expected_rad = math.radians(ARM_CONFIGURATION_Q_DEG[configuration][index - 1])
            if abs(finite_number(cold_row["minimum_rad"], f"{joint}.cold.minimum") - float(accepted["lower_rad"])) > 1.0e-9 or abs(finite_number(cold_row["maximum_rad"], f"{joint}.cold.maximum") - float(accepted["upper_rad"])) > 1.0e-9 or abs(finite_number(cold_row["native_angle_rad"], f"{joint}.cold.native") - expected_rad) > 1.0e-6:
                fail("DRIVER_COLD_VALUE_FAIL", "cold driver row differs from accepted limits/seed", {"joint": joint, "configuration": configuration, "row": cold_row})
            if cold_row["feature_error_code"] != 0 or cold_row["feature_suppressed"] is not False or cold_row["advanced_limit_angle"] is not True:
                fail("DRIVER_COLD_HEALTH_FAIL", "cold driver feature is not healthy", {"joint": joint, "configuration": configuration})
            cold_by_config[configuration] = cold_row
        if set(cold_by_config) != set(ARM_CONFIGS):
            fail("DRIVER_COLD_SET_FAIL", "cold driver configurations are not exact", {"joint": joint, "actual": sorted(cold_by_config)})
        driver_by_joint[joint] = row
    return {"drivers": drivers, "driver_by_joint": driver_by_joint, "driver_count": 6, "pass": True}


def validate_saved_configurations(v1: Mapping[str, Any], driver_by_joint: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    configurations = require_list(v1["configurations"], 2, "v1.configurations")
    by_name: Dict[str, Mapping[str, Any]] = {}
    legacy_fact = file_fact(LOCAL_ARM_ROOT / "inputs/vendor_link_parts/B51_REF_gripper_detail_LINKLOCAL.SLDPRT")
    validate_fact_payload(v1["legacy_gripper_file"], legacy_fact, "v1.legacy_gripper_file")
    for index, raw in enumerate(configurations):
        row = require_exact_keys(raw, {"configuration", "legacy_gripper_name2", "legacy_gripper_path", "legacy_gripper_suppression", "link6_name2", "native_joint_drivers"}, f"configurations[{index}]")
        configuration = str(row["configuration"])
        if configuration not in ARM_CONFIGS or configuration in by_name:
            fail("SAVED_CONFIG_ID_FAIL", "saved arm configuration is duplicate/unknown", {"configuration": configuration})
        if row["legacy_gripper_name2"] != "B51_REF_gripper_detail_LINKLOCAL-1" or Path(str(row["legacy_gripper_path"])).resolve() != Path(legacy_fact["path"]).resolve() or row["legacy_gripper_suppression"] != 0:
            fail("LEGACY_GRIPPER_SUPPRESSION_FAIL", "legacy gripper identity/path/suppression differs", {"configuration": configuration, "row": row})
        if row["link6_name2"] != "B51_REF_link6_LINKLOCAL-1":
            fail("LINK6_IDENTITY_FAIL", "saved configuration link6 identity differs", {"configuration": configuration, "actual": row["link6_name2"]})
        cold_rows = require_list(row["native_joint_drivers"], 6, f"{configuration}.native_joint_drivers")
        if [str(item.get("joint", "")) if isinstance(item, dict) else "" for item in cold_rows] != [f"joint{item}" for item in range(1, 7)]:
            fail("SAVED_CONFIG_DRIVER_ORDER_FAIL", "saved configuration driver rows are not ordered joint1..joint6", {"configuration": configuration})
        for cold_row in cold_rows:
            joint = str(cold_row["joint"])
            matches = [item for item in driver_by_joint[joint]["cold_reopen"]["configurations"] if item["configuration"] == configuration]
            if len(matches) != 1 or cold_row != matches[0]:
                fail("SAVED_CONFIG_COLD_LEDGER_FAIL", "saved configuration driver row differs from the canonical cold ledger", {"configuration": configuration, "joint": joint})
        by_name[configuration] = row
    if set(by_name) != set(ARM_CONFIGS):
        fail("SAVED_CONFIG_SET_FAIL", "saved arm configuration set is not exact", {"actual": sorted(by_name), "expected": sorted(ARM_CONFIGS)})
    return {"configurations": configurations, "legacy_gripper_file": legacy_fact, "configuration_count": 2, "legacy_gripper_suppression": 0, "pass": True}


def validate_v1() -> Dict[str, Any]:
    v1_fact = file_fact(V1_CHECKPOINT)
    if v1_fact["sha256"] != EXPECTED_V1_SHA256:
        fail("V1_RAW_HASH_FAIL", "V1 checkpoint raw bytes differ", {"actual": v1_fact, "expected_sha256": EXPECTED_V1_SHA256})
    v1 = strict_json_load(V1_CHECKPOINT)
    require_exact_keys(v1, V1_TOP_KEYS, "v1")
    require_timestamp(v1["timestamp_utc"], "v1.timestamp_utc")
    if v1["schema"] != EXPECTED_V1_SCHEMA or v1["verdict"] != EXPECTED_V1_VERDICT:
        fail("V1_SCHEMA_VERDICT_FAIL", "V1 schema/verdict differs", {"schema": v1["schema"], "verdict": v1["verdict"]})
    if str(v1["script_sha256"]).upper() != EXPECTED_V1_PRODUCER_SHA256:
        fail("V1_PRODUCER_HASH_FAIL", "V1 producer hash differs", {"actual": v1["script_sha256"], "expected": EXPECTED_V1_PRODUCER_SHA256})
    if str(v1["accepted_urdf_sha256"]).upper() != EXPECTED_ACCEPTED_URDF_SHA256:
        fail("V1_URDF_BINDING_FAIL", "V1 accepted URDF binding differs", {"actual": v1["accepted_urdf_sha256"], "expected": EXPECTED_ACCEPTED_URDF_SHA256})
    cold_open = require_exact_keys(v1["cold_open"], {"errors", "warnings", "read_only"}, "v1.cold_open")
    if cold_open != {"errors": 0, "warnings": 0, "read_only": True}:
        fail("V1_COLD_OPEN_FAIL", "V1 cold-open evidence differs", {"actual": cold_open})

    urdf = validate_accepted_urdf()
    trees = validate_copy_and_trees(v1)
    references = validate_reference_ledgers(v1)
    drivers = validate_drivers(v1, urdf["joints"])
    configurations = validate_saved_configurations(v1, drivers["driver_by_joint"])
    return {
        "v1_payload": v1,
        "v1_checkpoint": v1_fact,
        "accepted_urdf": urdf,
        "trees": trees,
        "references": references,
        "drivers": drivers,
        "configurations": configurations,
        "pass": True,
    }


def build_contract(validation: Mapping[str, Any]) -> Dict[str, Any]:
    contract = {
        "schema": CONTRACT_SCHEMA,
        "contract_policy": {
            "producer_independence": "NOT_BOUND_TO_LOOP1E_TOP_BUILDER_SHA256",
            "source_evidence": "EXACT_V1_RAW_BYTES_PLUS_COMPLETE_VALIDATED_V1_PAYLOAD",
            "cad_evidence": "EXACT_LOCALIZED_ELEVEN_FILE_TREE_UNCHANGED_FROM_V1_EXCEPT_V1_RECEIPTED_FINAL_ARM_ASSEMBLY",
            "urdf_authority": "EXACT_ACCEPTED_URDF_RAW_BYTES_AND_SIX_JOINT_PARSE",
            "solidworks_reexecution": "NOT_REQUIRED_BECAUSE_ALL_V1_COLD_PROVEN_BYTES_ARE_UNCHANGED",
            "cad_mutation": "PROHIBITED",
        },
        "source_v1_checkpoint": validation["v1_checkpoint"],
        "source_v1_producer_sha256": EXPECTED_V1_PRODUCER_SHA256,
        "source_v1_payload": validation["v1_payload"],
        "accepted_urdf": validation["accepted_urdf"],
        "protected_donor_arm": validation["trees"]["donor_arm"],
        "localized_arm": validation["trees"]["local_arm"],
        "donor_tree_files": validation["trees"]["donor_tree_files"],
        "localized_tree_files": validation["trees"]["localized_tree_files"],
        "validated_counts": {
            "tree_files": 11,
            "copy_rows": validation["trees"]["copy_row_count"],
            "reference_prebind_rows": validation["references"]["prebind_count"],
            "reference_repair_rows": validation["references"]["repair_count"],
            "reference_repairs_per_configuration": validation["references"]["repair_count_per_configuration"],
            "saved_configurations": validation["configurations"]["configuration_count"],
            "native_joint_drivers": validation["drivers"]["driver_count"],
        },
        "semantic_contract": {
            "configurations": list(ARM_CONFIGS),
            "legacy_gripper_name2": "B51_REF_gripper_detail_LINKLOCAL-1",
            "legacy_gripper_suppression": validation["configurations"]["legacy_gripper_suppression"],
            "link6_name2": "B51_REF_link6_LINKLOCAL-1",
            "native_driver_names": [f"V5_LOOP2_JOINT{index}_LIMIT_ANGLE" for index in range(1, 7)],
            "native_driver_generation_stage": "LOOP1E_NATIVE_DRIVER_SYNTHESIS",
            "accepted_urdf_sha256": EXPECTED_ACCEPTED_URDF_SHA256,
            "accepted_urdf_modified": False,
            "joint_topology_modified": False,
            "link_length_modified": False,
            "inertial_truth_modified": False,
        },
    }
    # Force canonical serialization here so non-finite or unsupported values
    # cannot survive into either the digest or the write-once checkpoint.
    canonical_json_bytes(contract)
    return contract


def input_snapshot(validation: Mapping[str, Any], source_policy: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "migration_tool": source_policy["source"],
        "v1_checkpoint": validation["v1_checkpoint"],
        "accepted_urdf": validation["accepted_urdf"]["fact"],
        "donor_tree_files": validation["trees"]["donor_tree_files"],
        "localized_tree_files": validation["trees"]["localized_tree_files"],
    }


def prepare() -> Dict[str, Any]:
    source_policy = source_policy_audit()
    validation = validate_v1()
    contract = build_contract(validation)
    contract_sha = canonical_sha256(contract)
    snapshot = input_snapshot(validation, source_policy)
    return {
        "source_policy": source_policy,
        "validation": validation,
        "contract": contract,
        "LOCAL_ARM_CONTRACT_SHA256": contract_sha,
        "input_snapshot": snapshot,
        "input_snapshot_sha256": canonical_sha256(snapshot),
    }


def expected_v2_payload(prepared: Mapping[str, Any], timestamp_utc: str) -> Dict[str, Any]:
    return {
        "schema": V2_SCHEMA,
        "timestamp_utc": timestamp_utc,
        "migration_mode": "PURE_FILESYSTEM_NO_SOLIDWORKS_NO_COM_NO_CAD_MUTATION",
        "migration_tool": prepared["source_policy"]["source"],
        "source_policy_audit": prepared["source_policy"],
        "source_v1_checkpoint": prepared["validation"]["v1_checkpoint"],
        "source_v1_producer_sha256": EXPECTED_V1_PRODUCER_SHA256,
        "accepted_urdf": prepared["validation"]["accepted_urdf"]["fact"],
        "local_arm": prepared["validation"]["trees"]["local_arm"],
        "input_snapshot": prepared["input_snapshot"],
        "input_snapshot_sha256": prepared["input_snapshot_sha256"],
        "local_arm_contract": prepared["contract"],
        "LOCAL_ARM_CONTRACT_SHA256": prepared["LOCAL_ARM_CONTRACT_SHA256"],
        "validation_summary": {
            "v1_raw_sha256_exact": True,
            "v1_complete_payload_validated": True,
            "v1_producer_sha256_exact": True,
            "accepted_urdf_raw_sha256_exact": True,
            "accepted_urdf_six_joint_parse_exact": True,
            "localized_arm_sha256_exact": True,
            "copy_proof_eleven_files_exact": True,
            "reference_prebind_ten_parts_exact": True,
            "reference_repairs_two_by_twenty_exact": True,
            "saved_configurations_exact": list(ARM_CONFIGS),
            "legacy_gripper_suppression_exact": 0,
            "six_native_driver_ledgers_exact": True,
            "six_native_driver_cold_readbacks_exact": True,
            "solidworks_started_or_attached": False,
            "cad_files_written": 0,
            "legacy_v1_modified": False,
        },
        "write_contract": {
            "target": norm(V2_CHECKPOINT),
            "policy": "SAME_DIRECTORY_ATOMIC_NO_REPLACE_WRITE_ONCE",
            "resume": False,
            "overwrite": False,
            "legacy_v1_preserved": True,
        },
        "verdict": V2_VERDICT,
    }


def validate_existing_v2(prepared: Mapping[str, Any]) -> Dict[str, Any]:
    fact = file_fact(V2_CHECKPOINT)
    payload = strict_json_load(V2_CHECKPOINT)
    require_exact_keys(payload, {
        "schema",
        "timestamp_utc",
        "migration_mode",
        "migration_tool",
        "source_policy_audit",
        "source_v1_checkpoint",
        "source_v1_producer_sha256",
        "accepted_urdf",
        "local_arm",
        "input_snapshot",
        "input_snapshot_sha256",
        "local_arm_contract",
        "LOCAL_ARM_CONTRACT_SHA256",
        "validation_summary",
        "write_contract",
        "verdict",
    }, "v2")
    require_timestamp(payload["timestamp_utc"], "v2.timestamp_utc")
    expected = expected_v2_payload(prepared, str(payload["timestamp_utc"]))
    if payload != expected:
        fail("V2_PAYLOAD_DRIFT", "existing V2 payload differs from the recomputed independent contract", {"target": fact})
    if canonical_sha256(payload["local_arm_contract"]) != payload["LOCAL_ARM_CONTRACT_SHA256"]:
        fail("V2_CONTRACT_DIGEST_FAIL", "existing V2 local-arm contract digest differs", {"target": fact})
    return {"target": fact, "payload": payload, "pass": True}


@contextmanager
def exclusive_mutex() -> Iterator[None]:
    if os.name != "nt":
        # The production environment is Windows.  The fallback preserves
        # functional testability; atomic no-replace still protects the target.
        yield
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel32.ReleaseMutex.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.CreateMutexW(None, 0, MUTEX_NAME)
    if not handle:
        fail("MUTEX_CREATE_FAIL", "cannot create the migration mutex", {"winerror": ctypes.get_last_error()})
    acquired = False
    try:
        status = int(kernel32.WaitForSingleObject(handle, 0))
        if status not in (0x00000000, 0x00000080):
            fail("MUTEX_BUSY", "another V2 migration transaction owns the mutex", {"status": status})
        acquired = True
        yield
    finally:
        if acquired:
            kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)


def atomic_no_replace_write(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if V2_CHECKPOINT.exists():
        fail("V2_TARGET_COLLISION", "write-once V2 checkpoint already exists", {"target": file_fact(V2_CHECKPOINT) if V2_CHECKPOINT.is_file() else norm(V2_CHECKPOINT)})
    if not VALIDATION.is_dir() or V2_CHECKPOINT.parent.resolve() != VALIDATION.resolve():
        fail("V2_TARGET_SCOPE_FAIL", "V2 target parent is not the exact validation directory", {"target": norm(V2_CHECKPOINT), "validation": norm(VALIDATION)})
    staging = V2_CHECKPOINT.with_name(f".{V2_CHECKPOINT.name}.STAGING_{os.getpid()}_{uuid.uuid4().hex}.tmp")
    if staging.exists() or staging.parent.resolve() != VALIDATION.resolve():
        fail("V2_STAGING_SCOPE_FAIL", "cannot allocate an exact same-directory staging path", {"staging": norm(staging)})
    promoted = False
    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        with staging.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        staged_payload = strict_json_load(staging)
        if staged_payload != payload:
            fail("V2_STAGING_READBACK_FAIL", "staged V2 bytes do not parse back to the intended payload", {"staging": file_fact(staging)})
        staged_fact = file_fact(staging)
        if os.name == "nt":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.MoveFileExW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
            kernel32.MoveFileExW.restype = ctypes.c_int
            if not kernel32.MoveFileExW(str(staging), str(V2_CHECKPOINT), 0):
                fail("V2_ATOMIC_PROMOTION_FAIL", "atomic no-replace promotion failed", {"staging": staged_fact, "target": norm(V2_CHECKPOINT), "winerror": ctypes.get_last_error()})
        else:
            os.link(staging, V2_CHECKPOINT)
            staging.unlink()
        promoted = True
        target_fact = file_fact(V2_CHECKPOINT)
        if target_fact["sha256"] != staged_fact["sha256"] or target_fact["bytes"] != staged_fact["bytes"]:
            fail("V2_PROMOTION_HASH_FAIL", "promoted V2 bytes differ from staging", {"staging": staged_fact, "target": target_fact})
        return {
            "staging_sha256": staged_fact["sha256"],
            "target": target_fact,
            "mechanism": "MOVEFILEEXW_NO_FLAGS_NO_REPLACE" if os.name == "nt" else "HARDLINK_NO_REPLACE_THEN_UNLINK",
            "pass": True,
        }
    finally:
        if not promoted and staging.is_file():
            try:
                staging.unlink()
            except OSError:
                pass


def audit_command() -> int:
    try:
        prepared = prepare()
        if V2_CHECKPOINT.exists():
            existing = validate_existing_v2(prepared)
            result = {
                "schema": "F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_AUDIT_V1",
                "timestamp_utc": utc_now(),
                "state": "PASS_EXISTING_WRITE_ONCE_V2",
                "execution_authorized": False,
                "source_policy_audit": prepared["source_policy"],
                "source_v1_checkpoint": prepared["validation"]["v1_checkpoint"],
                "local_arm": prepared["validation"]["trees"]["local_arm"],
                "accepted_urdf": prepared["validation"]["accepted_urdf"]["fact"],
                "LOCAL_ARM_CONTRACT_SHA256": prepared["LOCAL_ARM_CONTRACT_SHA256"],
                "existing_v2": existing["target"],
                "verdict": "V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_AUDIT_EXISTING_PASS",
            }
        else:
            result = {
                "schema": "F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_AUDIT_V1",
                "timestamp_utc": utc_now(),
                "state": "READY_TO_CREATE_WRITE_ONCE_V2",
                "execution_authorized": True,
                "source_policy_audit": prepared["source_policy"],
                "source_v1_checkpoint": prepared["validation"]["v1_checkpoint"],
                "local_arm": prepared["validation"]["trees"]["local_arm"],
                "accepted_urdf": prepared["validation"]["accepted_urdf"]["fact"],
                "validated_counts": prepared["contract"]["validated_counts"],
                "input_snapshot_sha256": prepared["input_snapshot_sha256"],
                "LOCAL_ARM_CONTRACT_SHA256": prepared["LOCAL_ARM_CONTRACT_SHA256"],
                "target": norm(V2_CHECKPOINT),
                "verdict": "V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_AUDIT_READY",
            }
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except Exception as exc:
        result = {
            "schema": "F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_AUDIT_V1",
            "timestamp_utc": utc_now(),
            "execution_authorized": False,
            "verdict": getattr(exc, "code", "V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_AUDIT_UNEXPECTED_FAIL"),
            "reason": str(exc),
            "detail": getattr(exc, "detail", {}),
            "traceback": traceback.format_exc(),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), file=sys.stderr)
        return 3


def execute_command() -> int:
    try:
        with exclusive_mutex():
            if V2_CHECKPOINT.exists():
                fail("V2_TARGET_COLLISION", "write-once V2 checkpoint already exists; execute never resumes or overwrites", {"target": file_fact(V2_CHECKPOINT) if V2_CHECKPOINT.is_file() else norm(V2_CHECKPOINT)})
            prepared_pre = prepare()
            payload = expected_v2_payload(prepared_pre, utc_now())
            # Recompute every input immediately before the commit.  This is a
            # pure-filesystem TOCTOU gate; no input is opened for writing.
            prepared_commit = prepare()
            if prepared_commit["input_snapshot"] != prepared_pre["input_snapshot"] or prepared_commit["LOCAL_ARM_CONTRACT_SHA256"] != prepared_pre["LOCAL_ARM_CONTRACT_SHA256"]:
                fail("INPUT_TOCTOU_PRECOMMIT_FAIL", "migration inputs changed before write-once commit")
            if payload != expected_v2_payload(prepared_commit, str(payload["timestamp_utc"])):
                fail("PAYLOAD_TOCTOU_PRECOMMIT_FAIL", "intended V2 payload differs after precommit revalidation")
            promotion = atomic_no_replace_write(payload)
            existing = validate_existing_v2(prepared_commit)
            prepared_post = prepare()
            if prepared_post["input_snapshot"] != prepared_pre["input_snapshot"] or prepared_post["LOCAL_ARM_CONTRACT_SHA256"] != prepared_pre["LOCAL_ARM_CONTRACT_SHA256"]:
                fail("INPUT_TOCTOU_POSTCOMMIT_FAIL", "migration inputs changed across the write-once commit")
            result = {
                "schema": "F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_EXECUTION_V1",
                "timestamp_utc": utc_now(),
                "migration_mode": "PURE_FILESYSTEM_NO_SOLIDWORKS_NO_COM_NO_CAD_MUTATION",
                "source_v1_checkpoint": prepared_post["validation"]["v1_checkpoint"],
                "accepted_urdf": prepared_post["validation"]["accepted_urdf"]["fact"],
                "local_arm": prepared_post["validation"]["trees"]["local_arm"],
                "LOCAL_ARM_CONTRACT_SHA256": prepared_post["LOCAL_ARM_CONTRACT_SHA256"],
                "promotion": promotion,
                "v2_checkpoint": existing["target"],
                "solidworks_started_or_attached": False,
                "cad_files_written": 0,
                "legacy_v1_modified": False,
                "verdict": "V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_EXECUTION_PASS",
            }
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
            return 0
    except Exception as exc:
        result = {
            "schema": "F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_EXECUTION_V1",
            "timestamp_utc": utc_now(),
            "migration_mode": "PURE_FILESYSTEM_NO_SOLIDWORKS_NO_COM_NO_CAD_MUTATION",
            "verdict": getattr(exc, "code", "V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATION_EXECUTION_UNEXPECTED_FAIL"),
            "reason": str(exc),
            "detail": getattr(exc, "detail", {}),
            "traceback": traceback.format_exc(),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), file=sys.stderr)
        return 3


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pure-filesystem Loop1E0 local-arm checkpoint V2 migration")
    parser.add_argument("command", choices=("audit", "execute"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    return audit_command() if args.command == "audit" else execute_command()


if __name__ == "__main__":
    raise SystemExit(main())
