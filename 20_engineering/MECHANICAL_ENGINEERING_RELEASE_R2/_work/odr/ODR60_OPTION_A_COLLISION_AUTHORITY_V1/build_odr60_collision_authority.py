#!/usr/bin/env python3
"""Build the deterministic, fail-closed ODR-60 Option-A aggregate gate.

This builder owns only the two top-level generated files declared below.  It
never runs a trajectory/path search and never invokes either sibling builder.
The sibling packages are inspected read-only so missing, partial, stale, or
invalid inputs remain an explicit HOLD rather than an exception that could be
mistaken for authorization.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import struct
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parent
PROXY_DIR = ROOT / "base_link_proxy_v2"
REGISTRY_DIR = ROOT / "system_registry"

BUILDER_NAME = "build_odr60_collision_authority.py"
GATE_NAME = "ODR60_OPTION_A_COLLISION_AUTHORITY_GATE_V1.json"
MANIFEST_NAME = "ODR60_OPTION_A_COLLISION_AUTHORITY_SHA256_V1.csv"
README_NAME = "README.md"
TEST_NAME = "test_odr60_collision_authority.py"

STEP_NAME = "B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2.step"
NPZ_NAME = "BASE_LINK_OPERATIONAL_COLLISION_V2.npz"
STL_NAME = "BASE_LINK_OPERATIONAL_COLLISION_V2.stl"
RECEIPT_NAME = "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2.json"
VALIDATION_NAME = "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V2.json"
HOLD_DIAGNOSTIC_NAME = "BASE_LINK_OPERATIONAL_COLLISION_HOLD_DIAGNOSTIC_V1.json"

REGISTRY_NAME = "M01_SYSTEM_COLLISION_REGISTRY_V1.json"
PAIR_COVERAGE_NAME = "M01_PAIR_COVERAGE_V1.csv"
REGISTRY_GATE_NAME = "M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json"

FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256 = (
    "22641C079014FE968702393F61E7F7F1A8F80C6C1DF45A61E31545F6EAFF3B65"
)
EXPECTED_OBJECT_COUNTS = {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6}
EXPECTED_OBJECTS = 150
EXPECTED_PAIRS = 11_175
EXPECTED_EXCEPTED = 9
EXPECTED_UNASSESSED = 11_166

CACHE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
CACHE_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def stable_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def relative_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": relative_label(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _false_checks(names: Iterable[str]) -> dict[str, bool]:
    return {name: False for name in names}


PROXY_CHECK_NAMES = (
    "required_step_receipt_validation_npz_stl_present",
    "receipt_json_and_schema_valid",
    "receipt_internal_checks_all_true",
    "receipt_remains_non_authorizing",
    "receipt_artifact_hashes_and_sizes_match",
    "canonical_npz_schema_valid",
    "npz_geometry_finite_nonempty_and_index_valid",
    "npz_has_68_proxy_solid_ids",
    "binary_stl_layout_valid",
    "npz_and_stl_triangle_geometry_identical",
    "receipt_geometry_metrics_match_npz",
    "replacement_aabb_containment_passed",
    "forbidden_raw_urdf_mesh_not_reemitted",
    "independent_validation_report_pass",
)


def _read_binary_stl_triangles(data: bytes) -> np.ndarray:
    if len(data) < 84:
        raise ValueError("binary STL shorter than 84-byte header")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * count:
        raise ValueError("binary STL byte count does not match triangle count")
    dtype = np.dtype(
        [
            ("normal", "<f4", (3,)),
            ("vertices", "<f4", (3, 3)),
            ("attribute", "<u2"),
        ],
        align=False,
    )
    if dtype.itemsize != 50:
        raise RuntimeError("internal binary STL dtype is not 50 bytes")
    return np.frombuffer(data, dtype=dtype, count=count, offset=84)


def inspect_base_link_proxy(proxy_dir: Path = PROXY_DIR) -> dict[str, Any]:
    """Validate the STEP-first V2 proxy artifacts without rebuilding them."""
    checks = _false_checks(PROXY_CHECK_NAMES)
    issues: list[str] = []
    required_paths = {
        "step": proxy_dir / STEP_NAME,
        "receipt": proxy_dir / RECEIPT_NAME,
        "validation": proxy_dir / VALIDATION_NAME,
        "npz": proxy_dir / NPZ_NAME,
        "stl": proxy_dir / STL_NAME,
    }
    present = {name: path.is_file() for name, path in required_paths.items()}
    checks["required_step_receipt_validation_npz_stl_present"] = all(present.values())
    artifact_records = {
        name: file_record(path)
        for name, path in required_paths.items()
        if path.is_file()
    }
    validation_path = required_paths["validation"]
    hold_path = proxy_dir / HOLD_DIAGNOSTIC_NAME
    hold_diagnostic: dict[str, Any] = {"present": hold_path.is_file(), "valid": False}
    if hold_path.is_file():
        artifact_records["hold_diagnostic"] = file_record(hold_path)
        try:
            hold_payload = json.loads(hold_path.read_text(encoding="utf-8"))
            outputs = hold_payload.get("outputs", {})
            hold_diagnostic = {
                "present": True,
                "valid": (
                    hold_payload.get("schema")
                    == "BASE_LINK_OPERATIONAL_COLLISION_HOLD_DIAGNOSTIC_V1"
                    and hold_payload.get("next_stage_authorized") is False
                    and hold_payload.get("path_search_authorized") is False
                    and hold_payload.get("release_credit") is False
                    and outputs.get("canonical_npz_written") is False
                    and outputs.get("binary_stl_written") is False
                    and outputs.get("pass_receipt_written") is False
                    and str(hold_payload.get("verdict", "")).startswith("HOLD_")
                ),
                "verdict": hold_payload.get("verdict"),
                "brepcheck_valid_solid_count": hold_payload.get("brep_observations", {}).get(
                    "brepcheck_valid_solid_count"
                ),
                "brepcheck_invalid_solid_count": hold_payload.get("brep_observations", {}).get(
                    "brepcheck_invalid_solid_count"
                ),
                "all_nonzero_area_faces_triangulated": hold_payload.get("gate", {}).get(
                    "all_nonzero_area_faces_triangulated"
                ),
            }
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            hold_diagnostic = {
                "present": True,
                "valid": False,
                "error": f"{type(exc).__name__}",
            }

    if not checks["required_step_receipt_validation_npz_stl_present"]:
        for name, exists in present.items():
            if not exists:
                issues.append(f"MISSING_{name.upper()}:{required_paths[name].name}")
        if hold_diagnostic["present"]:
            status = (
                "OPERATIONAL_PROXY_HOLD_DIAGNOSTIC"
                if hold_diagnostic["valid"]
                else "OPERATIONAL_PROXY_HOLD_DIAGNOSTIC_INVALID"
            )
            issues.append(
                "UPSTREAM_HOLD_DIAGNOSTIC:"
                + str(hold_diagnostic.get("verdict", "INVALID_OR_UNREADABLE"))
            )
        else:
            status = (
                "MISSING_OPERATIONAL_PROXY"
                if not any(present.values())
                else "INCOMPLETE_OPERATIONAL_PROXY"
            )
        return {
            "status": status,
            "proxy_pass": False,
            "required_files": [
                f"base_link_proxy_v2/{STEP_NAME}",
                f"base_link_proxy_v2/{RECEIPT_NAME}",
                f"base_link_proxy_v2/{VALIDATION_NAME}",
                f"base_link_proxy_v2/{NPZ_NAME}",
                f"base_link_proxy_v2/{STL_NAME}",
            ],
            "present": present,
            "checks": checks,
            "issues": issues,
            "artifacts": artifact_records,
            "validation_report_present": validation_path.is_file(),
            "hold_diagnostic": hold_diagnostic,
        }

    receipt: dict[str, Any] = {}
    vertices = np.empty((0, 3), dtype=np.float64)
    faces = np.empty((0, 3), dtype=np.uint32)
    solid_ids = np.empty((0,), dtype=np.uint16)
    npz_bytes = required_paths["npz"].read_bytes()
    stl_bytes = required_paths["stl"].read_bytes()

    try:
        receipt = json.loads(required_paths["receipt"].read_text(encoding="utf-8"))
        checks["receipt_json_and_schema_valid"] = (
            isinstance(receipt, dict)
            and receipt.get("schema") == "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2"
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issues.append(f"RECEIPT_PARSE_ERROR:{type(exc).__name__}")

    if checks["receipt_json_and_schema_valid"]:
        receipt_checks = receipt.get("checks")
        checks["receipt_internal_checks_all_true"] = (
            isinstance(receipt_checks, dict)
            and bool(receipt_checks)
            and all(value is True for value in receipt_checks.values())
        )
        checks["receipt_remains_non_authorizing"] = (
            receipt.get("next_stage_authorized") is False
            and receipt.get("path_search_authorized") is False
            and receipt.get("system_pair_evaluation_authorized") is False
            and receipt.get("release_credit") is False
        )
        receipt_artifacts = receipt.get("artifacts", {})
        npz_record = receipt_artifacts.get("canonical_npz", {})
        stl_record = receipt_artifacts.get("binary_stl", {})
        checks["receipt_artifact_hashes_and_sizes_match"] = (
            str(npz_record.get("sha256", "")).upper() == sha256_bytes(npz_bytes)
            and int(npz_record.get("bytes", -1)) == len(npz_bytes)
            and str(stl_record.get("sha256", "")).upper() == sha256_bytes(stl_bytes)
            and int(stl_record.get("bytes", -1)) == len(stl_bytes)
        )

    try:
        with zipfile.ZipFile(io.BytesIO(npz_bytes)) as archive:
            info = archive.infolist()
            member_names = [item.filename for item in info]
            canonical_zip = (
                member_names
                == ["faces.npy", "frame.npy", "solid_ids.npy", "units.npy", "vertices_m.npy"]
                and all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in info)
                and all(item.compress_type == zipfile.ZIP_STORED for item in info)
            )
        with np.load(io.BytesIO(npz_bytes), allow_pickle=False) as data:
            exact_keys = set(data.files) == {
                "faces",
                "frame",
                "solid_ids",
                "units",
                "vertices_m",
            }
            vertices = np.asarray(data["vertices_m"])
            faces = np.asarray(data["faces"])
            solid_ids = np.asarray(data["solid_ids"])
            scalar_contract = data["units"].item() == "meter" and data["frame"].item() == "base_link"
            dtype_contract = (
                vertices.dtype == np.dtype("<f8")
                and faces.dtype == np.dtype("<u4")
                and solid_ids.dtype == np.dtype("<u2")
            )
        checks["canonical_npz_schema_valid"] = bool(
            canonical_zip and exact_keys and scalar_contract and dtype_contract
        )
        checks["npz_geometry_finite_nonempty_and_index_valid"] = bool(
            vertices.ndim == 2
            and vertices.shape[1:] == (3,)
            and faces.ndim == 2
            and faces.shape[1:] == (3,)
            and len(vertices) > 0
            and len(faces) > 0
            and len(solid_ids) == len(faces)
            and np.isfinite(vertices).all()
            and int(faces.max(initial=0)) < len(vertices)
        )
        checks["npz_has_68_proxy_solid_ids"] = bool(
            np.array_equal(np.unique(solid_ids), np.arange(68, dtype=np.uint16))
        )
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        issues.append(f"NPZ_VALIDATION_ERROR:{type(exc).__name__}")

    try:
        stl_triangles = _read_binary_stl_triangles(stl_bytes)
        checks["binary_stl_layout_valid"] = len(stl_triangles) == len(faces) and len(faces) > 0
        if checks["binary_stl_layout_valid"] and checks["npz_geometry_finite_nonempty_and_index_valid"]:
            expected_triangles = vertices[faces].astype("<f4", copy=False)
            checks["npz_and_stl_triangle_geometry_identical"] = bool(
                np.array_equal(stl_triangles["vertices"], expected_triangles)
            )
    except (ValueError, RuntimeError, IndexError) as exc:
        issues.append(f"STL_VALIDATION_ERROR:{type(exc).__name__}")

    if checks["receipt_json_and_schema_valid"] and checks["npz_geometry_finite_nonempty_and_index_valid"]:
        mesh = receipt.get("mesh", {})
        bbox_mm = np.vstack((vertices.min(axis=0), vertices.max(axis=0))) * 1000.0
        try:
            receipt_bbox = np.asarray(mesh.get("bbox_mm"), dtype=np.float64)
            checks["receipt_geometry_metrics_match_npz"] = bool(
                receipt_bbox.shape == (2, 3)
                and np.array_equal(receipt_bbox, bbox_mm)
                and int(mesh.get("vertex_count", -1)) == len(vertices)
                and int(mesh.get("triangle_count", -1)) == len(faces)
                and int(mesh.get("solid_id_count", -1)) == 68
            )
        except (TypeError, ValueError):
            checks["receipt_geometry_metrics_match_npz"] = False
        receipt_checks = receipt.get("checks", {})
        checks["replacement_aabb_containment_passed"] = (
            receipt_checks.get("motor_tolerance_aabb_contains_source") is True
            and receipt_checks.get("plate_tolerance_aabb_contains_source") is True
            and receipt_checks.get("raw_urdf_mesh_hash_not_used") is True
        )

    checks["forbidden_raw_urdf_mesh_not_reemitted"] = (
        sha256_bytes(stl_bytes) != FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256
    )

    try:
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        validation_checks = validation.get("checks", {})
        checks["independent_validation_report_pass"] = (
            validation.get("schema") == "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V2"
            and validation.get("next_stage_authorized") is False
            and validation.get("path_search_authorized") is False
            and validation.get("system_pair_evaluation_authorized") is False
            and validation.get("release_credit") is False
            and isinstance(validation_checks, dict)
            and bool(validation_checks)
            and all(value is True for value in validation_checks.values())
            and str(validation.get("verdict", "")).startswith(
                "BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2_INDEPENDENT_GEOMETRY_VALIDATION_PASS"
            )
            and str(validation.get("canonical_npz", {}).get("sha256", "")).upper()
            == sha256_bytes(npz_bytes)
            and str(validation.get("binary_stl", {}).get("sha256", "")).upper()
            == sha256_bytes(stl_bytes)
            and str(validation.get("receipt", {}).get("sha256", "")).upper()
            == sha256_file(required_paths["receipt"])
            and str(validation.get("primary_step", {}).get("sha256", "")).upper()
            == sha256_file(required_paths["step"])
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issues.append(f"VALIDATION_REPORT_ERROR:{type(exc).__name__}")

    for name, passed in checks.items():
        if not passed:
            issues.append(f"CHECK_FAILED:{name}")
    proxy_pass = all(checks.values())
    return {
        "status": "OPERATIONAL_PROXY_VERIFIED_PASS" if proxy_pass else "OPERATIONAL_PROXY_HOLD_INVALID",
        "proxy_pass": proxy_pass,
        "required_files": [
            f"base_link_proxy_v2/{STEP_NAME}",
            f"base_link_proxy_v2/{RECEIPT_NAME}",
            f"base_link_proxy_v2/{VALIDATION_NAME}",
            f"base_link_proxy_v2/{NPZ_NAME}",
            f"base_link_proxy_v2/{STL_NAME}",
        ],
        "present": present,
        "checks": checks,
        "issues": issues,
        "artifacts": artifact_records,
        "receipt_verdict": receipt.get("verdict") if receipt else None,
        "validation_report_present": validation_path.is_file(),
        "hold_diagnostic": hold_diagnostic,
    }


REGISTRY_CHECK_NAMES = (
    "required_registry_pair_csv_gate_present",
    "registry_json_and_schema_valid",
    "150_unique_active_objects_with_frozen_class_counts",
    "11175_unique_pairs_sequentially_enumerated",
    "nine_adjacent_exceptions_only",
    "11166_non_excepted_pairs_unassessed_fail_closed",
    "registry_unknown_and_wildcard_policy_fail_closed",
    "registry_gate_structural_claim_matches_payload",
    "registry_gate_complete_system_collision_false",
    "registry_gate_path_search_not_executed",
    "registry_gate_next_stage_not_authorized",
    "registry_source_hash_mismatch_count_zero",
)


def inspect_system_registry(registry_dir: Path = REGISTRY_DIR) -> dict[str, Any]:
    checks = _false_checks(REGISTRY_CHECK_NAMES)
    issues: list[str] = []
    paths = {
        "registry": registry_dir / REGISTRY_NAME,
        "pairs": registry_dir / PAIR_COVERAGE_NAME,
        "gate": registry_dir / REGISTRY_GATE_NAME,
    }
    present = {name: path.is_file() for name, path in paths.items()}
    checks["required_registry_pair_csv_gate_present"] = all(present.values())
    records = {name: file_record(path) for name, path in paths.items() if path.is_file()}
    if not all(present.values()):
        for name, exists in present.items():
            if not exists:
                issues.append(f"MISSING_{name.upper()}:{paths[name].name}")
        return {
            "status": "SYSTEM_REGISTRY_MISSING_OR_INCOMPLETE",
            "structural_registry_pass": False,
            "complete_system_collision_pass": False,
            "checks": checks,
            "issues": issues,
            "artifacts": records,
        }

    registry: dict[str, Any] = {}
    gate: dict[str, Any] = {}
    pairs: list[dict[str, str]] = []
    try:
        registry = json.loads(paths["registry"].read_text(encoding="utf-8"))
        gate = json.loads(paths["gate"].read_text(encoding="utf-8"))
        with paths["pairs"].open(encoding="utf-8", newline="") as stream:
            pairs = list(csv.DictReader(stream))
        checks["registry_json_and_schema_valid"] = (
            registry.get("schema") == "SYSTEM_COLLISION_REGISTRY_V1"
            and gate.get("schema") == "SYSTEM_COLLISION_REGISTRY_GATE_V1"
        )
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        issues.append(f"SYSTEM_REGISTRY_PARSE_ERROR:{type(exc).__name__}")

    if checks["registry_json_and_schema_valid"]:
        objects = registry.get("objects", [])
        object_ids = [row.get("object_id") for row in objects]
        checks["150_unique_active_objects_with_frozen_class_counts"] = (
            len(object_ids) == len(set(object_ids)) == EXPECTED_OBJECTS
            and gate.get("object_counts") == EXPECTED_OBJECT_COUNTS
            and gate.get("known_active_object_count") == EXPECTED_OBJECTS
        )

        pair_indices: list[int] = []
        pair_keys: list[tuple[str, str]] = []
        status_counts: Counter[str] = Counter()
        unassessed_forbid = True
        try:
            for row in pairs:
                pair_indices.append(int(row["pair_index"]))
                pair_keys.append(tuple(sorted((row["object_a"], row["object_b"]))))
                status_counts[row["status"]] += 1
                if row["status"] == "UNASSESSED_FAIL_CLOSED" and row.get("policy") != "FORBID":
                    unassessed_forbid = False
        except (KeyError, TypeError, ValueError):
            pair_indices = []
            pair_keys = []
            status_counts = Counter()
            unassessed_forbid = False
        checks["11175_unique_pairs_sequentially_enumerated"] = (
            len(pairs) == EXPECTED_PAIRS
            and pair_indices == list(range(1, EXPECTED_PAIRS + 1))
            and len(pair_keys) == len(set(pair_keys)) == EXPECTED_PAIRS
        )
        checks["nine_adjacent_exceptions_only"] = (
            status_counts.get("EXCEPTED", 0) == EXPECTED_EXCEPTED
            and gate.get("adjacent_pair_exceptions") == EXPECTED_EXCEPTED
            and gate.get("active_non_adjacent_pair_exceptions") == 0
        )
        checks["11166_non_excepted_pairs_unassessed_fail_closed"] = (
            status_counts.get("UNASSESSED_FAIL_CLOSED", 0) == EXPECTED_UNASSESSED
            and sum(status_counts.values()) == EXPECTED_PAIRS
            and unassessed_forbid
        )
        pair_policy = registry.get("pair_policy", {})
        checks["registry_unknown_and_wildcard_policy_fail_closed"] = (
            pair_policy.get("unknown") == "ABORT"
            and pair_policy.get("wildcard_or_manual_exception") == "FORBIDDEN"
        )
        checks["registry_gate_structural_claim_matches_payload"] = (
            gate.get("structural_registry_complete") is True
            and gate.get("pair_universe_enumerated") is True
            and gate.get("pair_coverage", {}).get("expected_pairs") == EXPECTED_PAIRS
            and gate.get("pair_coverage", {}).get("status_counts")
            == {"EXCEPTED": EXPECTED_EXCEPTED, "UNASSESSED_FAIL_CLOSED": EXPECTED_UNASSESSED}
        )
        checks["registry_gate_complete_system_collision_false"] = (
            gate.get("complete_system_collision_pass") is False
            and registry.get("gate_semantics", {}).get("complete_system_collision_pass") is False
        )
        checks["registry_gate_path_search_not_executed"] = gate.get("path_search_executed") is False
        checks["registry_gate_next_stage_not_authorized"] = gate.get("next_stage_authorized") is False
        checks["registry_source_hash_mismatch_count_zero"] = gate.get("source_hash_mismatch_count") == 0

    for name, passed in checks.items():
        if not passed:
            issues.append(f"CHECK_FAILED:{name}")
    structural_pass = all(checks.values())
    return {
        "status": (
            "SYSTEM_REGISTRY_STRUCTURAL_PASS_COLLISION_HOLD"
            if structural_pass
            else "SYSTEM_REGISTRY_STRUCTURAL_HOLD"
        ),
        "structural_registry_pass": structural_pass,
        "complete_system_collision_pass": False,
        "known_active_object_count": gate.get("known_active_object_count"),
        "pair_count": len(pairs),
        "excepted_pair_count": sum(row.get("status") == "EXCEPTED" for row in pairs),
        "unassessed_fail_closed_pair_count": sum(
            row.get("status") == "UNASSESSED_FAIL_CLOSED" for row in pairs
        ),
        "base_link_proxy_state_reported_by_registry": gate.get("base_link_proxy_state"),
        "carried_registry_blockers": gate.get("blockers", []),
        "checks": checks,
        "issues": issues,
        "artifacts": records,
    }


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def build_gate() -> dict[str, Any]:
    proxy = inspect_base_link_proxy()
    registry = inspect_system_registry()
    blockers: list[str] = []
    if not proxy["proxy_pass"]:
        _append_unique(blockers, "BASE_LINK_OPERATIONAL_PROXY_NOT_VERIFIED")
    if proxy.get("hold_diagnostic", {}).get("valid"):
        _append_unique(blockers, "BASE_LINK_PROXY_UPSTREAM_HOLD_DIAGNOSTIC_ACTIVE")
    if not registry["structural_registry_pass"]:
        _append_unique(blockers, "SYSTEM_COLLISION_REGISTRY_STRUCTURAL_VALIDATION_FAILED")

    reported_proxy = registry.get("base_link_proxy_state_reported_by_registry") or {}
    registry_proxy_states_after_emission = {
        "PROXY_EMITTED_PENDING_SYSTEM_PAIR_EVALUATION",
        "OPERATIONAL_PROXY_VERIFIED_PASS",
    }
    if (
        proxy["proxy_pass"]
        and reported_proxy.get("status") not in registry_proxy_states_after_emission
    ):
        _append_unique(blockers, "SYSTEM_REGISTRY_REBUILD_REQUIRED_AFTER_PROXY_PROMOTION")
    for blocker in registry.get("carried_registry_blockers", []):
        if blocker == "MISSING_OPERATIONAL_PROXY" and proxy["proxy_pass"]:
            continue
        _append_unique(blockers, str(blocker))
    _append_unique(blockers, "11166_NON_EXCEPTED_PAIRS_UNASSESSED")

    proxy_pass = bool(proxy["proxy_pass"])
    registry_pass = bool(registry["structural_registry_pass"])
    checks = {
        "base_link_proxy_receipt_npz_stl_verified": proxy_pass,
        "system_registry_structurally_verified": registry_pass,
        "11175_pair_universe_enumerated": (
            registry.get("pair_count") == EXPECTED_PAIRS
        ),
        "11166_pairs_remain_unassessed_fail_closed": (
            registry.get("unassessed_fail_closed_pair_count") == EXPECTED_UNASSESSED
        ),
        "complete_system_collision_pass_is_false": True,
        "path_search_executed_is_false": True,
        "next_stage_authorized_is_false": True,
    }
    verdict = (
        "ODR60_OPTION_A_BASE_LINK_PROXY_VERIFIED_PASS__SYSTEM_COLLISION_HOLD__"
        "11166_UNASSESSED_FAIL_CLOSED__NO_PATH_SEARCH_OR_RELEASE_AUTHORITY"
        if proxy_pass
        else "ODR60_OPTION_A_BASE_LINK_PROXY_HOLD__SYSTEM_COLLISION_HOLD__"
        "11166_UNASSESSED_FAIL_CLOSED__NO_PATH_SEARCH_OR_RELEASE_AUTHORITY"
    )
    return {
        "schema": "ODR60_OPTION_A_COLLISION_AUTHORITY_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "authority": "ODR60_OPTION_A_COLLISION_AUTHORITY_AGGREGATE_ONLY__NO_M01_EXECUTION_AUTHORITY",
        "review_status": "PENDING_OWNER_REVIEW",
        "base_link_proxy": proxy,
        "system_registry": registry,
        "proxy_pass": proxy_pass,
        "structural_registry_pass": registry_pass,
        "complete_hash_bound_acm": False,
        "complete_system_collision_pass": False,
        "pre_search_ready": False,
        "path_search_executed": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "checks": checks,
        "blockers": blockers,
        "verdict": verdict,
    }


def is_non_cache_core_file(path: Path) -> bool:
    if not path.is_file():
        return False
    relative = path.relative_to(ROOT)
    if relative.as_posix() == MANIFEST_NAME:
        return False
    if any(part in CACHE_DIR_NAMES for part in relative.parts):
        return False
    if path.suffix.lower() in CACHE_SUFFIXES:
        return False
    if path.name.endswith("~"):
        return False
    return True


def collect_core_paths() -> list[Path]:
    paths = [path for path in ROOT.iterdir() if is_non_cache_core_file(path)]
    for directory in (PROXY_DIR, REGISTRY_DIR):
        if directory.is_dir():
            paths.extend(path for path in directory.rglob("*") if is_non_cache_core_file(path))
    unique = {path.resolve(): path for path in paths}
    return sorted(unique.values(), key=lambda path: path.relative_to(ROOT).as_posix())


def build_manifest_bytes(overrides: Mapping[str, bytes] | None = None) -> bytes:
    override_map = dict(overrides or {})
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["path", "bytes", "sha256"])
    paths = collect_core_paths()
    existing_relatives = {path.relative_to(ROOT).as_posix() for path in paths}
    for relative in sorted(override_map):
        if relative != MANIFEST_NAME and relative not in existing_relatives:
            paths.append(ROOT / relative)
    paths.sort(key=lambda path: path.relative_to(ROOT).as_posix())
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        data = override_map.get(relative)
        if data is None:
            data = path.read_bytes()
        writer.writerow([relative, len(data), sha256_bytes(data)])
    return output.getvalue().encode("utf-8")


def output_map() -> dict[str, bytes]:
    gate_bytes = stable_json_bytes(build_gate())
    manifest_bytes = build_manifest_bytes({GATE_NAME: gate_bytes})
    return {GATE_NAME: gate_bytes, MANIFEST_NAME: manifest_bytes}


def atomic_write_owned(path: Path, data: bytes) -> None:
    if path.parent.resolve() != ROOT.resolve() or path.name not in {GATE_NAME, MANIFEST_NAME}:
        raise RuntimeError(f"write target is outside top-level ownership: {path}")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def check_outputs(expected: Mapping[str, bytes]) -> list[str]:
    mismatches: list[str] = []
    for name, data in expected.items():
        path = ROOT / name
        if not path.is_file():
            mismatches.append(f"MISSING:{name}")
        elif path.read_bytes() != data:
            mismatches.append(f"BYTE_MISMATCH:{name}")
    return mismatches


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="atomically write only gate and manifest")
    mode.add_argument("--check", action="store_true", help="verify checked-in gate and manifest bytes")
    mode.add_argument("--print-gate", action="store_true", help="print the expected gate without writing")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    expected = output_map()
    if args.write:
        atomic_write_owned(ROOT / GATE_NAME, expected[GATE_NAME])
        # Recompute after the gate is present so collection is identical to a clean replay.
        expected = output_map()
        atomic_write_owned(ROOT / MANIFEST_NAME, expected[MANIFEST_NAME])
        print(json.dumps({"written": list(expected), "gate": build_gate()["verdict"]}, indent=2))
        return 0
    if args.print_gate:
        sys.stdout.buffer.write(expected[GATE_NAME])
        return 0
    mismatches = check_outputs(expected)
    if mismatches:
        print(json.dumps({"status": "HOLD", "mismatches": mismatches}, indent=2))
        return 1
    print(json.dumps({"status": "PASS_BYTE_IDENTITY", "files": list(expected)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
