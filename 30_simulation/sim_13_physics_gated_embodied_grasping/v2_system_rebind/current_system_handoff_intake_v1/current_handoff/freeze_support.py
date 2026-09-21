"""Canonical JSON and deterministic package inventories."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from .strict_io import IntakeError, PACKAGE_ROOT, PROJECT_ROOT


EXCLUDED_SOURCE_PARTS = {"evidence", "results", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis", ".cache"}
FORBIDDEN_ASSET_EXTENSIONS = {
    ".urdf",
    ".step",
    ".stp",
    ".fcstd",
    ".stl",
    ".obj",
    ".dae",
    ".ply",
    ".gltf",
    ".glb",
    ".inp",
    ".odb",
    ".traj",
    ".npz",
    ".xacro",
    ".sdf",
    ".mjcf",
    ".msh",
    ".vtk",
    ".npy",
    ".h5",
}
FORBIDDEN_CACHE_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".cache",
    ".coverage",
}

# This is the complete package file set, not merely a source inventory.  In
# particular, evidence/ and results/ are intentionally present here so an
# unreceipted extra file cannot hide in a directory excluded from the source
# manifest.  Content integrity remains covered by the source manifest and the
# evidence -> Gate -> terminal receipt DAG.
FROZEN_PACKAGE_FILE_ALLOWLIST = tuple(
    sorted(
        {
            "README.md",
            "contracts/CURRENT_SYSTEM_HANDOFF_INTAKE_SCHEMA_V1.json",
            "contracts/CURRENT_SYSTEM_HANDOFF_NEGATIVE_CONTROL_CONTRACT_V1.json",
            "contracts/FIELD_SOURCE_CROSSWALK_V1.json",
            "contracts/PROMOTION_SEQUENCE_CONTRACT_V1.json",
            "contracts/ROUTE_C_DISPOSITION_CONTRACT_V1.json",
            "current_handoff/__init__.py",
            "current_handoff/evaluator.py",
            "current_handoff/freeze_support.py",
            "current_handoff/negative_controls.py",
            "current_handoff/schema.py",
            "current_handoff/strict_io.py",
            "evidence/CURRENT_SYSTEM_HANDOFF_INDEPENDENT_AUDIT_V1.json",
            "evidence/CURRENT_SYSTEM_HANDOFF_INTAKE_V1.json",
            "evidence/CURRENT_SYSTEM_HANDOFF_NEGATIVE_CONTROLS_V1.json",
            "evidence/CURRENT_SYSTEM_HANDOFF_SOURCE_MANIFEST_V1.json",
            "freeze_current_system_handoff_intake.py",
            "independent_audit_current_system_handoff_intake.py",
            "pytest.ini",
            "results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1.json",
            "results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_TERMINAL_V1.json",
            "tests/conftest.py",
            "tests/test_evaluator.py",
            "tests/test_frozen_bundle.py",
            "tests/test_independent_audit.py",
            "tests/test_negative_controls.py",
            "tests/test_schema.py",
            "tests/test_strict_io.py",
            "validate_current_system_handoff_intake_source_freeze.py",
            "verify_current_system_handoff_intake_read_only_replay.py",
        }
    )
)


def canonical_json_bytes(document: Any) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def file_receipt(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
    }


def document_receipt(relative_path: str, document: Any) -> dict[str, Any]:
    payload = canonical_json_bytes(document)
    return {
        "path": relative_path,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
    }


def source_inventory() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(PACKAGE_ROOT.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(PACKAGE_ROOT).parts
        if any(part.lower() in EXCLUDED_SOURCE_PARTS for part in relative_parts):
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        records.append(file_receipt(path))
    return records


def package_inventory() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(PACKAGE_ROOT.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or any(part.lower() in FORBIDDEN_CACHE_NAMES for part in path.relative_to(PACKAGE_ROOT).parts):
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        records.append(file_receipt(path))
    return records


def package_file_paths() -> tuple[str, ...]:
    """Return every current package file, including caches and generated assets."""

    return tuple(
        sorted(
            path.relative_to(PACKAGE_ROOT).as_posix()
            for path in PACKAGE_ROOT.rglob("*")
            if path.is_file()
        )
    )


def validate_frozen_package_file_set(relative_paths: Iterable[str] | None = None) -> None:
    """Reject any missing, duplicate, or extra file regardless of extension/location."""

    actual = package_file_paths() if relative_paths is None else tuple(relative_paths)
    if not all(isinstance(path, str) and path for path in actual):
        raise IntakeError("MALFORMED", "package file inventory contains an invalid path")
    if len(actual) != len(set(actual)):
        raise IntakeError("MALFORMED", "package file inventory contains duplicate paths")
    expected = set(FROZEN_PACKAGE_FILE_ALLOWLIST)
    observed = set(actual)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    if missing or unexpected:
        raise IntakeError(
            "MALFORMED",
            f"complete package file allowlist drift: missing={missing}, unexpected={unexpected}",
        )


def forbidden_package_entries() -> list[str]:
    """Return forbidden generated assets and cache files/directories."""

    findings: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(PACKAGE_ROOT)
        lowered_parts = {part.lower() for part in relative.parts}
        cache_hit = bool(lowered_parts & FORBIDDEN_CACHE_NAMES) or any(
            part.lower().startswith(".coverage.") for part in relative.parts
        )
        bytecode_hit = path.is_file() and path.suffix.lower() in {".pyc", ".pyo"}
        asset_hit = path.is_file() and path.suffix.lower() in FORBIDDEN_ASSET_EXTENSIONS
        if cache_hit or bytecode_hit or asset_hit:
            findings.append(relative.as_posix())
    return findings


def transactional_write_json_bundle(documents: dict[Path, Any], terminal_path: Path) -> None:
    """Stage all files, then publish the terminal commit record last.

    The operation is crash-safe per file. Publishing the terminal last makes a partial
    bundle non-committed and therefore fail-closed to every validator in this package.
    """

    if terminal_path not in documents:
        raise ValueError("transaction bundle must include its terminal commit record")
    staged: dict[Path, Path] = {}
    try:
        for destination, document in documents.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(prefix=".handoff-stage-", suffix=".json", dir=destination.parent)
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(canonical_json_bytes(document))
                handle.flush()
                os.fsync(handle.fileno())
            staged[destination] = temporary
        for destination in sorted((path for path in documents if path != terminal_path), key=lambda item: item.as_posix()):
            os.replace(staged.pop(destination), destination)
        os.replace(staged.pop(terminal_path), terminal_path)
    finally:
        for temporary in staged.values():
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
