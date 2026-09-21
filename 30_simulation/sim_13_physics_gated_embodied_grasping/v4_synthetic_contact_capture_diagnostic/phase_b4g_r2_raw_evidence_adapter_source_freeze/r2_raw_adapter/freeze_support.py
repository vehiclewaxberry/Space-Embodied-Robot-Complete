"""Shared source-freeze primitives; never import or run physics entrypoints."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from .strict_json import canonical_sha256, file_sha256, loads_bytes


SOURCE_EXTENSIONS = {".ini", ".json", ".md", ".py"}
OUTPUT_PREFIXES = ("evidence/", "results/")
FORBIDDEN_SUFFIXES = {".csv", ".npz", ".pyc", ".step", ".stp", ".tmp", ".urdf"}
FORBIDDEN_DIRECTORIES = {".pytest_cache", "__pycache__", "raw", "raw_cases"}
TEMP_PREFIXES = (".dbg_", ".r2_raw_nc_", ".r2_raw_test_")


class FreezeSupportError(RuntimeError):
    pass


def is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(callable(is_junction) and is_junction())


def project_root_from(package_root: Path) -> Path:
    resolved = package_root.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "30_simulation").is_dir():
            return candidate
    raise FreezeSupportError("PROJECT_ROOT_NOT_FOUND")


def _output_path(relative: str) -> bool:
    return any(relative.startswith(prefix) for prefix in OUTPUT_PREFIXES)


def forbidden_artifacts(package_root: Path) -> list[str]:
    root = package_root.resolve()
    failures: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if is_link_or_reparse(path):
            failures.append(f"LINK_OR_REPARSE:{relative}")
            continue
        if any(part in FORBIDDEN_DIRECTORIES or part.startswith(TEMP_PREFIXES) for part in path.relative_to(root).parts):
            failures.append(f"FORBIDDEN_DIRECTORY:{relative}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"FORBIDDEN_SUFFIX:{relative}")
    return sorted(set(failures))


def local_source_inventory(package_root: Path) -> list[dict[str, Any]]:
    root = package_root.resolve()
    failures = forbidden_artifacts(root)
    if failures:
        raise FreezeSupportError(f"FORBIDDEN_PACKAGE_ARTIFACTS:{failures}")
    inventory: list[dict[str, Any]] = []
    unknown: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if _output_path(relative):
            continue
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            unknown.append(relative)
            continue
        stat_result = path.stat()
        if stat_result.st_nlink != 1:
            raise FreezeSupportError(f"SOURCE_SINGLE_LINK_REQUIRED:{relative}")
        inventory.append({
            "path": relative,
            "bytes": stat_result.st_size,
            "sha256": file_sha256(path),
        })
    if unknown:
        raise FreezeSupportError(f"UNREGISTERED_LOCAL_FILE_TYPE:{unknown}")
    return inventory


def build_source_manifest(package_root: Path) -> dict[str, Any]:
    sources = local_source_inventory(package_root)
    return seal_document({
        "schema": "SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_MANIFEST_V1",
        "scope": "LOCAL_SOURCE_AND_CONTRACT_BYTES_ONLY_SELF_EXCLUDED_OUTPUTS",
        "self_excluded": True,
        "acyclic": True,
        "excluded_output_prefixes": list(OUTPUT_PREFIXES),
        "source_count": len(sources),
        "sources": sources,
        "source_inventory_sha256": canonical_sha256(sources),
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
    })


def seal_document(value: dict[str, Any]) -> dict[str, Any]:
    if "document_sha256" in value:
        raise FreezeSupportError("DOCUMENT_SHA_FIELD_PREEXISTS")
    result = dict(value)
    result["document_sha256"] = canonical_sha256(value)
    return result


def document_seal_valid(value: Any) -> bool:
    if not isinstance(value, dict) or type(value.get("document_sha256")) is not str:
        return False
    payload = {key: item for key, item in value.items() if key != "document_sha256"}
    return canonical_sha256(payload) == value["document_sha256"]


def strict_load(path: Path) -> Any:
    if is_link_or_reparse(path) or not path.is_file():
        raise FreezeSupportError(f"STRICT_REGULAR_JSON_REQUIRED:{path}")
    return loads_bytes(path.read_bytes())


def project_record(path: Path, package_root: Path, identifier: str, role: str) -> dict[str, Any]:
    project_root = project_root_from(package_root)
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError as exc:
        raise FreezeSupportError("BOUND_RECORD_ESCAPES_PROJECT") from exc
    if is_link_or_reparse(path) or not path.is_file() or path.stat().st_nlink != 1:
        raise FreezeSupportError("BOUND_RECORD_REGULAR_SINGLE_LINK_REQUIRED")
    return {
        "id": identifier,
        "role": role,
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def record_matches(record: Any, project_root: Path) -> bool:
    if not isinstance(record, dict) or set(record) != {"id", "role", "path", "bytes", "sha256"}:
        return False
    relative = record["path"]
    if type(relative) is not str or "\\" in relative:
        return False
    raw = Path(relative)
    if raw.is_absolute() or any(part in {"", ".", ".."} for part in raw.parts):
        return False
    lexical = project_root / raw
    if is_link_or_reparse(lexical):
        return False
    resolved = lexical.resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return False
    return bool(
        resolved.is_file()
        and resolved.stat().st_nlink == 1
        and type(record["bytes"]) is int
        and record["bytes"] == resolved.stat().st_size
        and type(record["sha256"]) is str
        and record["sha256"] == file_sha256(resolved)
    )


def package_snapshot(package_root: Path) -> dict[str, dict[str, Any]]:
    root = package_root.resolve()
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if is_link_or_reparse(path):
            raise FreezeSupportError(f"PACKAGE_LINK_OR_REPARSE:{path.relative_to(root).as_posix()}")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            snapshot[relative] = {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
    return snapshot


def snapshot_delta(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    left, right = set(before), set(after)
    return {
        "added": sorted(right - left),
        "removed": sorted(left - right),
        "changed": sorted(path for path in left & right if before[path] != after[path]),
    }


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def all_json_paths(package_root: Path, *, excluded: Iterable[Path] = ()) -> list[Path]:
    excluded_resolved = {path.resolve() for path in excluded}
    return [
        path for path in sorted(package_root.rglob("*.json"), key=lambda item: item.as_posix())
        if path.resolve() not in excluded_resolved
    ]


__all__ = [
    "FORBIDDEN_DIRECTORIES", "FORBIDDEN_SUFFIXES", "FreezeSupportError",
    "OUTPUT_PREFIXES", "SOURCE_EXTENSIONS", "all_json_paths", "build_source_manifest",
    "document_seal_valid", "forbidden_artifacts", "is_link_or_reparse",
    "local_source_inventory", "package_snapshot", "project_record", "project_root_from",
    "record_matches", "seal_document", "sha256_bytes", "snapshot_delta", "strict_load",
]
