#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attach-only SOLIDWORKS safety gate for the F3R2 V4 successor.

This program deliberately does not build CAD.  Build mode performs immutable
input/template checks, attaches to an already-running SOLIDWORKS 2024 session,
creates a new run directory exclusively, writes a HOLD receipt, and stops.

Verification mode is also non-mutating with respect to CAD.  It refuses to
proceed if any target document is already loaded, checks every declared output
against its byte count and SHA-256 digest, and asks SOLIDWORKS for the stored
dependency list of the closed primary document.  Every dependency must exist,
remain inside the package root, and be declared (and therefore hash-checked) in
the manifest.

No code path launches or terminates SOLIDWORKS, changes session UI state, opens
target CAD documents, saves CAD documents, or edits an existing run directory.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


MANIFEST_SCHEMA = "F3R2_V4_SOLIDWORKS_ATTACH_INPUT_V1"
RESULT_SCHEMA = "F3R2_V4_SOLIDWORKS_ATTACH_RESULT_V1"
SOLIDWORKS_PROG_ID = "SldWorks.Application"
EXPECTED_SOLIDWORKS_MAJOR = 32  # SOLIDWORKS 2024
MIN_AVAILABLE_MEMORY_GIB = 6.0

SCRIPT_PATH = Path(__file__).resolve()
V4_ROOT = SCRIPT_PATH.parents[1]
RUNS_ROOT = V4_ROOT / "03_native_cad" / "V4_ATTACH_RUNS"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_HOLD = 3
EXIT_ATTACH_REQUIRED = 4

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
SOLIDWORKS_DOCUMENT_EXTENSIONS = {".sldprt", ".sldasm", ".slddrw"}
WINDOWS_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
WINDOWS_INVALID_COMPONENT_CHARS = set('<>:"|?*')


class GateError(RuntimeError):
    """Expected gate failure with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int = EXIT_FAIL,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.detail = detail or {}


class _MemoryStatusEx(ctypes.Structure):
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


def emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _normal_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _validate_windows_component(component: str, field_name: str) -> None:
    if (
        not component
        or component.endswith((" ", "."))
        or any(char in WINDOWS_INVALID_COMPONENT_CHARS for char in component)
        or component.split(".", 1)[0].upper() in WINDOWS_RESERVED_BASENAMES
    ):
        raise GateError(
            "UNSAFE_WINDOWS_PATH_COMPONENT",
            f"{field_name} contains a Windows-unsafe path component: {component!r}",
        )


def _safe_relative(value: Any, field_name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise GateError("MANIFEST_INVALID", f"{field_name} must be a non-empty string")
    relative = Path(value)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise GateError(
            "UNSAFE_RELATIVE_PATH",
            f"{field_name} must be a relative path without '..': {value!r}",
        )
    if relative == Path("."):
        raise GateError("UNSAFE_RELATIVE_PATH", f"{field_name} cannot be '.'")
    for component in relative.parts:
        _validate_windows_component(component, field_name)
    return relative


def _resolve_under(root: Path, relative: Path, field_name: str) -> Path:
    target = (root / relative).resolve(strict=False)
    if not _is_within(target, root):
        raise GateError(
            "PATH_ESCAPES_ROOT",
            f"{field_name} resolves outside the permitted root",
            detail={"root": str(root), "target": str(target)},
        )
    return target


def _resolve_manifest_file(base: Path, value: Any, field_name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise GateError("MANIFEST_INVALID", f"{field_name} must be a non-empty string")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve(strict=False)


def _validate_sha(value: Any, field_name: str, *, required: bool) -> Optional[str]:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise GateError("MANIFEST_INVALID", f"{field_name} must be a 64-character SHA-256")
    return value.upper()


def _validate_bytes(value: Any, field_name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GateError("MANIFEST_INVALID", f"{field_name} must be a positive integer")
    return value


def _parse_source_entries(
    raw_entries: Any,
    section: str,
    manifest_dir: Path,
) -> List[Dict[str, Any]]:
    if not isinstance(raw_entries, list) or not raw_entries:
        raise GateError("MANIFEST_INVALID", f"{section} must be a non-empty list")
    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_entries):
        field = f"{section}[{index}]"
        if not isinstance(raw, dict):
            raise GateError("MANIFEST_INVALID", f"{field} must be an object")
        role = raw.get("role")
        if not isinstance(role, str) or not role.strip():
            raise GateError("MANIFEST_INVALID", f"{field}.role must be a non-empty string")
        path = _resolve_manifest_file(manifest_dir, raw.get("path"), f"{field}.path")
        key = _normal_path(path)
        if key in seen:
            raise GateError("MANIFEST_INVALID", f"duplicate {section} path: {path}")
        seen.add(key)
        result.append(
            {
                "role": role.strip(),
                "path": path,
                "sha256": _validate_sha(raw.get("sha256"), f"{field}.sha256", required=True),
                "bytes": _validate_bytes(raw.get("bytes"), f"{field}.bytes"),
            }
        )
    return result


def _parse_expected_outputs(
    raw_entries: Any,
    package_root: Path,
    *,
    verify_only: bool,
) -> List[Dict[str, Any]]:
    if not isinstance(raw_entries, list) or not raw_entries:
        raise GateError("MANIFEST_INVALID", "expected_outputs must be a non-empty list")
    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_entries):
        field = f"expected_outputs[{index}]"
        if not isinstance(raw, dict):
            raise GateError("MANIFEST_INVALID", f"{field} must be an object")
        role = raw.get("role")
        if not isinstance(role, str) or not role.strip():
            raise GateError("MANIFEST_INVALID", f"{field}.role must be a non-empty string")
        relative = _safe_relative(raw.get("relative_path"), f"{field}.relative_path")
        path = _resolve_under(package_root, relative, f"{field}.relative_path")
        key = _normal_path(path)
        if key in seen:
            raise GateError("MANIFEST_INVALID", f"duplicate expected output path: {relative}")
        seen.add(key)
        result.append(
            {
                "role": role.strip(),
                "relative_path": relative,
                "path": path,
                "sha256": _validate_sha(
                    raw.get("sha256"), f"{field}.sha256", required=verify_only
                ),
                "bytes": _validate_bytes(raw.get("bytes"), f"{field}.bytes"),
            }
        )
    return result


def load_manifest(path: Path, *, verify_only: bool) -> Dict[str, Any]:
    manifest_path = path.resolve(strict=False)
    if not manifest_path.is_file():
        raise GateError("MANIFEST_NOT_FOUND", f"manifest not found: {manifest_path}", exit_code=EXIT_USAGE)
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(
            "MANIFEST_READ_ERROR",
            f"cannot read manifest: {exc}",
            exit_code=EXIT_USAGE,
        ) from exc
    if not isinstance(raw, dict):
        raise GateError("MANIFEST_INVALID", "manifest root must be an object", exit_code=EXIT_USAGE)
    if raw.get("schema") != MANIFEST_SCHEMA:
        raise GateError(
            "MANIFEST_SCHEMA_MISMATCH",
            f"schema must equal {MANIFEST_SCHEMA}",
            exit_code=EXIT_USAGE,
        )

    run_id = raw.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id) or run_id in {".", ".."}:
        raise GateError(
            "MANIFEST_INVALID",
            "run_id must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
            exit_code=EXIT_USAGE,
        )
    _validate_windows_component(run_id, "run_id")

    run_dir = _resolve_under(RUNS_ROOT, Path(run_id), "run_id")
    package_relative = _safe_relative(raw.get("package_relative_root", "package"), "package_relative_root")
    package_root = _resolve_under(run_dir, package_relative, "package_relative_root")
    manifest_dir = manifest_path.parent

    inputs = _parse_source_entries(raw.get("inputs"), "inputs", manifest_dir)
    templates = _parse_source_entries(raw.get("templates"), "templates", manifest_dir)
    expected = _parse_expected_outputs(
        raw.get("expected_outputs"), package_root, verify_only=verify_only
    )

    primary_relative = _safe_relative(raw.get("primary_document"), "primary_document")
    primary_document = _resolve_under(package_root, primary_relative, "primary_document")
    expected_keys = {_normal_path(item["path"]) for item in expected}
    if _normal_path(primary_document) not in expected_keys:
        raise GateError(
            "MANIFEST_INVALID",
            "primary_document must also be declared in expected_outputs",
            exit_code=EXIT_USAGE,
        )

    minimum_dependencies = raw.get("minimum_dependency_count")
    if minimum_dependencies is None:
        minimum_dependencies = 1 if primary_document.suffix.lower() in {".sldasm", ".slddrw"} else 0
    if (
        isinstance(minimum_dependencies, bool)
        or not isinstance(minimum_dependencies, int)
        or minimum_dependencies < 0
    ):
        raise GateError(
            "MANIFEST_INVALID",
            "minimum_dependency_count must be a non-negative integer",
            exit_code=EXIT_USAGE,
        )

    return {
        "manifest_path": manifest_path,
        "manifest_sha256": sha256(manifest_path),
        "run_id": run_id,
        "run_dir": run_dir,
        "package_root": package_root,
        "package_relative_root": package_relative,
        "inputs": inputs,
        "templates": templates,
        "expected_outputs": expected,
        "primary_document": primary_document,
        "minimum_dependency_count": minimum_dependencies,
    }


def audit_files(items: Iterable[Dict[str, Any]], section: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    for item in items:
        path: Path = item["path"]
        row: Dict[str, Any] = {
            "section": section,
            "role": item["role"],
            "path": str(path).replace("\\", "/"),
            "expected_bytes": item.get("bytes"),
            "expected_sha256": item.get("sha256"),
            "exists": path.is_file(),
        }
        if not path.is_file():
            row["status"] = "MISSING"
            issues.append({"code": "FILE_MISSING", "section": section, "path": row["path"]})
            rows.append(row)
            continue
        stat = path.stat()
        actual_hash = sha256(path)
        row.update({"actual_bytes": stat.st_size, "actual_sha256": actual_hash})
        mismatch = False
        if item.get("bytes") is not None and stat.st_size != item["bytes"]:
            mismatch = True
            issues.append({"code": "BYTE_COUNT_MISMATCH", "section": section, "path": row["path"]})
        if item.get("sha256") is not None and actual_hash != item["sha256"]:
            mismatch = True
            issues.append({"code": "SHA256_MISMATCH", "section": section, "path": row["path"]})
        if stat.st_size <= 0:
            mismatch = True
            issues.append({"code": "EMPTY_FILE", "section": section, "path": row["path"]})
        row["status"] = "MISMATCH" if mismatch else "PASS"
        rows.append(row)
    return rows, issues


def available_memory_gib() -> Optional[float]:
    if os.name != "nt":
        return None
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    try:
        ok = bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)))
    except Exception:
        return None
    if not ok:
        return None
    return round(status.ullAvailPhys / (1024.0 ** 3), 3)


def _com_value(obj: Any, member_name: str, *args: Any) -> Any:
    member = getattr(obj, member_name)
    return member(*args) if callable(member) else member


@contextlib.contextmanager
def attached_solidworks() -> Iterator[Any]:
    """Attach to a running SOLIDWORKS instance; never create or terminate one."""
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise GateError(
            "PYWIN32_UNAVAILABLE",
            "pywin32/pythoncom is required",
            exit_code=EXIT_USAGE,
        ) from exc

    pythoncom.CoInitialize()
    sw = None
    try:
        try:
            sw = win32com.client.GetActiveObject(SOLIDWORKS_PROG_ID)
        except Exception as exc:
            detail: Dict[str, Any] = {"exception_type": type(exc).__name__}
            hresult = getattr(exc, "hresult", None)
            if hresult is not None:
                detail["hresult"] = int(hresult)
            raise GateError(
                "ATTACH_REQUIRED",
                "SOLIDWORKS is not already running under the current user",
                exit_code=EXIT_ATTACH_REQUIRED,
                detail=detail,
            ) from exc
        yield sw
    finally:
        sw = None
        pythoncom.CoUninitialize()


def solidworks_version(sw: Any) -> Dict[str, Any]:
    try:
        revision = str(_com_value(sw, "RevisionNumber"))
        major = int(revision.split(".", 1)[0])
    except Exception as exc:
        raise GateError(
            "SOLIDWORKS_VERSION_QUERY_FAILED",
            f"cannot read SOLIDWORKS revision: {exc}",
            exit_code=EXIT_HOLD,
        ) from exc
    result = {"revision": revision, "major": major, "expected_major": EXPECTED_SOLIDWORKS_MAJOR}
    if major != EXPECTED_SOLIDWORKS_MAJOR:
        raise GateError(
            "SOLIDWORKS_VERSION_MISMATCH",
            f"attached SOLIDWORKS major is {major}; expected {EXPECTED_SOLIDWORKS_MAJOR}",
            exit_code=EXIT_HOLD,
            detail=result,
        )
    return result


def _as_sequence(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def enumerate_open_documents(sw: Any) -> List[Dict[str, str]]:
    docs: Optional[List[Any]] = None
    try:
        docs = _as_sequence(_com_value(sw, "GetDocuments"))
    except Exception:
        docs = None

    if docs is None:
        try:
            first = _com_value(sw, "GetFirstDocument")
        except Exception as exc:
            raise GateError(
                "OPEN_DOCUMENT_ENUMERATION_FAILED",
                f"cannot enumerate open SOLIDWORKS documents: {exc}",
            ) from exc
        docs = []
        current = first
        seen: set[Tuple[str, str]] = set()
        for _ in range(4096):
            if current is None:
                break
            try:
                title = str(_com_value(current, "GetTitle") or "")
                path = str(_com_value(current, "GetPathName") or "")
            except Exception as exc:
                raise GateError("OPEN_DOCUMENT_ENUMERATION_FAILED", str(exc)) from exc
            key = (title.casefold(), os.path.normcase(path))
            if key in seen:
                raise GateError("OPEN_DOCUMENT_ENUMERATION_FAILED", "cycle detected in open documents")
            seen.add(key)
            docs.append(current)
            try:
                current = _com_value(current, "GetNext")
            except Exception as exc:
                raise GateError("OPEN_DOCUMENT_ENUMERATION_FAILED", str(exc)) from exc
        else:
            raise GateError("OPEN_DOCUMENT_ENUMERATION_FAILED", "open document limit exceeded")

    records: List[Dict[str, str]] = []
    for doc in docs:
        try:
            records.append(
                {
                    "title": str(_com_value(doc, "GetTitle") or ""),
                    "path": str(_com_value(doc, "GetPathName") or "").replace("\\", "/"),
                }
            )
        except Exception as exc:
            raise GateError("OPEN_DOCUMENT_ENUMERATION_FAILED", str(exc)) from exc
    return records


def target_document_collisions(
    expected_outputs: Sequence[Dict[str, Any]],
    open_documents: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    targets = [
        item["path"]
        for item in expected_outputs
        if item["path"].suffix.lower() in SOLIDWORKS_DOCUMENT_EXTENSIONS
    ]
    target_paths = {_normal_path(path): path for path in targets}
    target_names = {path.name.casefold(): path for path in targets}
    target_stems = {path.stem.casefold(): path for path in targets}
    collisions: List[Dict[str, str]] = []
    for doc in open_documents:
        raw_path = doc.get("path", "")
        title = doc.get("title", "")
        exact = _normal_path(Path(raw_path)) in target_paths if raw_path else False
        title_key = Path(title).name.casefold()
        title_stem = Path(title).stem.casefold()
        same_name = title_key in target_names or title_stem in target_stems
        if exact or same_name:
            collisions.append({"title": title, "path": raw_path, "reason": "path" if exact else "title"})
    return collisions


def audit_dependencies(
    sw: Any,
    primary_document: Path,
    package_root: Path,
    expected_outputs: Sequence[Dict[str, Any]],
    minimum_count: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    try:
        raw = _com_value(
            sw,
            "GetDocumentDependencies2",
            str(primary_document),
            True,   # traverse all dependency levels
            False,  # use stored paths; do not apply ambient search rules
            False,  # omit read-only marker so the result is name/path pairs
        )
    except Exception as exc:
        return (
            {"status": "ERROR", "error": str(exc), "dependencies": []},
            [{"code": "DEPENDENCY_QUERY_FAILED", "message": str(exc)}],
        )

    values = [str(value) for value in _as_sequence(raw)]
    issues: List[Dict[str, Any]] = []
    if len(values) % 2:
        return (
            {"status": "ERROR", "raw_value_count": len(values), "dependencies": []},
            [{"code": "DEPENDENCY_RESULT_SHAPE_INVALID", "raw_value_count": len(values)}],
        )

    manifest_paths = {_normal_path(item["path"]): item for item in expected_outputs}
    rows: List[Dict[str, Any]] = []
    for index in range(0, len(values), 2):
        reference_name = values[index]
        stored_path = values[index + 1].strip().strip('"')
        native_path_text = stored_path.split("|", 1)[0]
        dependency_path = Path(native_path_text)
        if not dependency_path.is_absolute():
            dependency_path = primary_document.parent / dependency_path
        dependency_path = dependency_path.resolve(strict=False)
        inside = _is_within(dependency_path, package_root)
        exists = dependency_path.is_file()
        declared = _normal_path(dependency_path) in manifest_paths
        row = {
            "reference_name": reference_name,
            "stored_path": stored_path,
            "resolved_path": str(dependency_path).replace("\\", "/"),
            "inside_package": inside,
            "exists": exists,
            "declared_in_expected_outputs": declared,
        }
        rows.append(row)
        if not inside:
            issues.append({"code": "DEPENDENCY_OUTSIDE_PACKAGE", "path": row["resolved_path"]})
        if not exists:
            issues.append({"code": "DEPENDENCY_MISSING", "path": row["resolved_path"]})
        if not declared:
            issues.append({"code": "UNMANIFESTED_DEPENDENCY", "path": row["resolved_path"]})

    if len(rows) < minimum_count:
        issues.append(
            {
                "code": "DEPENDENCY_COUNT_BELOW_MINIMUM",
                "actual": len(rows),
                "minimum": minimum_count,
            }
        )
    return (
        {
            "status": "PASS" if not issues else "FAIL",
            "search_rules_applied": False,
            "dependency_count": len(rows),
            "minimum_dependency_count": minimum_count,
            "dependencies": rows,
        },
        issues,
    )


def write_json_exclusive(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def base_result(manifest: Dict[str, Any], mode: str) -> Dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "timestamp_utc": utc_now(),
        "mode": mode,
        "run_id": manifest["run_id"],
        "manifest_path": str(manifest["manifest_path"]).replace("\\", "/"),
        "manifest_sha256": manifest["manifest_sha256"],
        "v4_root": str(V4_ROOT).replace("\\", "/"),
        "run_dir": str(manifest["run_dir"]).replace("\\", "/"),
        "package_root": str(manifest["package_root"]).replace("\\", "/"),
    }


def _resource_gate(result: Dict[str, Any]) -> Optional[int]:
    free_gib = available_memory_gib()
    result["resource_preflight"] = {
        "available_physical_memory_gib_snapshot": free_gib,
        "minimum_required_gib": MIN_AVAILABLE_MEMORY_GIB,
        "operator_must_confirm_stable_memory": True,
    }
    if free_gib is None:
        result.update(
            {
                "verdict": "RESOURCE_QUERY_UNAVAILABLE_HOLD",
                "exit_code": EXIT_HOLD,
                "reason": "available physical memory could not be measured",
            }
        )
        return EXIT_HOLD
    if free_gib < MIN_AVAILABLE_MEMORY_GIB:
        result.update(
            {
                "verdict": "INSUFFICIENT_MEMORY_HOLD",
                "exit_code": EXIT_HOLD,
                "reason": "at least 6 GiB available physical memory is required",
            }
        )
        return EXIT_HOLD
    return None


def build_preflight(manifest: Dict[str, Any]) -> int:
    result = base_result(manifest, "BUILD_PREFLIGHT_ONLY")
    input_rows, input_issues = audit_files(manifest["inputs"], "inputs")
    template_rows, template_issues = audit_files(manifest["templates"], "templates")
    result["inputs"] = input_rows
    result["templates"] = template_rows
    result["planned_outputs"] = [
        {
            "role": item["role"],
            "relative_path": str(item["relative_path"]).replace("\\", "/"),
        }
        for item in manifest["expected_outputs"]
    ]
    offline_issues = input_issues + template_issues
    if offline_issues:
        result.update(
            {
                "verdict": "INPUT_OR_TEMPLATE_VALIDATION_FAIL",
                "exit_code": EXIT_FAIL,
                "issues": offline_issues,
                "native_files_created": 0,
            }
        )
        emit(result)
        return EXIT_FAIL
    if manifest["run_dir"].exists():
        result.update(
            {
                "verdict": "RUN_DIRECTORY_ALREADY_EXISTS_FAIL",
                "exit_code": EXIT_FAIL,
                "native_files_created": 0,
            }
        )
        emit(result)
        return EXIT_FAIL
    resource_exit = _resource_gate(result)
    if resource_exit is not None:
        result["native_files_created"] = 0
        emit(result)
        return resource_exit

    try:
        with attached_solidworks() as sw:
            result["solidworks"] = solidworks_version(sw)
    except GateError as exc:
        result.update(
            {
                "verdict": exc.code,
                "exit_code": exc.exit_code,
                "reason": exc.message,
                "detail": exc.detail,
                "native_files_created": 0,
            }
        )
        emit(result)
        return exc.exit_code

    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        manifest["run_dir"].mkdir(exist_ok=False)
    except FileExistsError:
        result.update(
            {
                "verdict": "RUN_DIRECTORY_ALREADY_EXISTS_FAIL",
                "exit_code": EXIT_FAIL,
                "native_files_created": 0,
            }
        )
        emit(result)
        return EXIT_FAIL

    result.update(
        {
            "verdict": "NATIVE_BUILD_NOT_IMPLEMENTED_HOLD",
            "exit_code": EXIT_HOLD,
            "native_build_implemented": False,
            "native_files_created": 0,
            "writes_confined_to": ["V4_ATTACH_BUILD_GATE.json"],
            "non_claims": [
                "NO_CAD_CREATED",
                "NOT_NATIVE_BUILD_PASS",
                "NOT_COLD_REOPEN_PASS",
                "NOT_INTERFERENCE_PASS",
                "NOT_MANUFACTURING_RELEASE",
            ],
        }
    )
    receipt = manifest["run_dir"] / "V4_ATTACH_BUILD_GATE.json"
    try:
        write_json_exclusive(receipt, result)
    except OSError as exc:
        result.update(
            {
                "verdict": "RECEIPT_WRITE_FAIL",
                "exit_code": EXIT_FAIL,
                "reason": str(exc),
            }
        )
        emit(result)
        return EXIT_FAIL
    result["receipt_path"] = str(receipt).replace("\\", "/")
    emit(result)
    return EXIT_HOLD


def _verify_receipt_path(run_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    suffix = uuid.uuid4().hex[:8].upper()
    return run_dir / "verification_receipts" / f"V4_ATTACH_VERIFY_{stamp}_{suffix}.json"


def _finish_verify(manifest: Dict[str, Any], result: Dict[str, Any], exit_code: int) -> int:
    result["exit_code"] = exit_code
    receipt = _verify_receipt_path(manifest["run_dir"])
    try:
        write_json_exclusive(receipt, result)
        result["receipt_path"] = str(receipt).replace("\\", "/")
    except OSError as exc:
        result.update(
            {
                "verdict": "RECEIPT_WRITE_FAIL",
                "exit_code": EXIT_FAIL,
                "receipt_error": str(exc),
            }
        )
        exit_code = EXIT_FAIL
    emit(result)
    return exit_code


def verify_only(manifest: Dict[str, Any]) -> int:
    result = base_result(manifest, "VERIFY_ONLY_STATIC_PACKAGE_GATE")
    if not manifest["run_dir"].is_dir():
        result.update(
            {
                "verdict": "RUN_DIRECTORY_NOT_FOUND_FAIL",
                "exit_code": EXIT_FAIL,
                "reason": "verify-only never creates a run directory",
            }
        )
        emit(result)
        return EXIT_FAIL
    if not manifest["package_root"].is_dir() or not _is_within(
        manifest["package_root"], manifest["run_dir"]
    ):
        result.update(
            {
                "verdict": "PACKAGE_ROOT_INVALID_FAIL",
                "reason": "package root is missing or resolves outside the run directory",
            }
        )
        return _finish_verify(manifest, result, EXIT_FAIL)

    input_rows, input_issues = audit_files(manifest["inputs"], "inputs")
    template_rows, template_issues = audit_files(manifest["templates"], "templates")
    output_rows, output_issues = audit_files(manifest["expected_outputs"], "expected_outputs")
    result["inputs"] = input_rows
    result["templates"] = template_rows
    result["expected_outputs"] = output_rows
    offline_issues = input_issues + template_issues + output_issues
    if offline_issues:
        result.update(
            {
                "verdict": "STATIC_FILE_VALIDATION_FAIL",
                "issues": offline_issues,
                "solidworks_check": "NOT_ATTEMPTED_DUE_TO_OFFLINE_FAILURE",
            }
        )
        return _finish_verify(manifest, result, EXIT_FAIL)

    resource_exit = _resource_gate(result)
    if resource_exit is not None:
        return _finish_verify(manifest, result, resource_exit)

    try:
        with attached_solidworks() as sw:
            result["solidworks"] = solidworks_version(sw)
            open_documents = enumerate_open_documents(sw)
            result["open_document_inventory"] = open_documents
            collisions = target_document_collisions(manifest["expected_outputs"], open_documents)
            result["target_documents_already_loaded"] = collisions
            if collisions:
                result.update(
                    {
                        "verdict": "TARGET_DOCUMENT_ALREADY_IN_MEMORY_FAIL",
                        "issues": [
                            {
                                "code": "TARGET_DOCUMENT_ALREADY_IN_MEMORY",
                                "title": row["title"],
                                "path": row["path"],
                            }
                            for row in collisions
                        ],
                    }
                )
                return _finish_verify(manifest, result, EXIT_FAIL)

            dependency_result, dependency_issues = audit_dependencies(
                sw,
                manifest["primary_document"],
                manifest["package_root"],
                manifest["expected_outputs"],
                manifest["minimum_dependency_count"],
            )
            result["dependency_audit"] = dependency_result
            if dependency_issues:
                result.update(
                    {
                        "verdict": "PACKAGE_DEPENDENCY_VALIDATION_FAIL",
                        "issues": dependency_issues,
                    }
                )
                return _finish_verify(manifest, result, EXIT_FAIL)
    except GateError as exc:
        result.update(
            {
                "verdict": exc.code,
                "reason": exc.message,
                "detail": exc.detail,
            }
        )
        return _finish_verify(manifest, result, exc.exit_code)

    result.update(
        {
            "verdict": "V4_PACKAGE_STATIC_VERIFY_PASS",
            "issues": [],
            "non_claims": [
                "NOT_NATIVE_REBUILD_PASS",
                "NOT_COLD_REOPEN_REBUILD_PASS",
                "NOT_INTERFERENCE_OR_CLEARANCE_PASS",
                "NOT_DRAWING_OR_BOM_CONTENT_ACCEPTANCE",
                "NOT_MANUFACTURING_RELEASE",
            ],
        }
    )
    return _finish_verify(manifest, result, EXIT_PASS)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Attach-only SOLIDWORKS 2024 safety gate. Default mode writes a HOLD "
            "receipt only; --verify-only performs a closed-document package audit."
        )
    )
    parser.add_argument("manifest", type=Path, help="JSON input manifest")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify an existing package; never create the target run directory",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        manifest = load_manifest(args.manifest, verify_only=bool(args.verify_only))
    except GateError as exc:
        emit(
            {
                "schema": RESULT_SCHEMA,
                "timestamp_utc": utc_now(),
                "mode": "VERIFY_ONLY" if args.verify_only else "BUILD_PREFLIGHT_ONLY",
                "verdict": exc.code,
                "exit_code": exc.exit_code,
                "reason": exc.message,
                "detail": exc.detail,
            }
        )
        return exc.exit_code
    except Exception as exc:  # defensive: never emit a misleading PASS
        emit(
            {
                "schema": RESULT_SCHEMA,
                "timestamp_utc": utc_now(),
                "verdict": "UNEXPECTED_PREFLIGHT_EXCEPTION",
                "exit_code": EXIT_FAIL,
                "exception_type": type(exc).__name__,
                "reason": str(exc),
            }
        )
        return EXIT_FAIL

    try:
        return verify_only(manifest) if args.verify_only else build_preflight(manifest)
    except Exception as exc:  # defensive: never emit a misleading PASS
        emit(
            {
                **base_result(manifest, "VERIFY_ONLY" if args.verify_only else "BUILD_PREFLIGHT_ONLY"),
                "verdict": "UNEXPECTED_RUNTIME_EXCEPTION",
                "exit_code": EXIT_FAIL,
                "exception_type": type(exc).__name__,
                "reason": str(exc),
            }
        )
        return EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
