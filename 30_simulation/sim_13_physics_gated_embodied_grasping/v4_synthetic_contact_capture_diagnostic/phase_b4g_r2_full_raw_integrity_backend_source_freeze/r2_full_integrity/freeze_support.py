"""Acyclic source-freeze helpers; evidence and results self-exclude."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .source_api import load_raw_modules, project_root


SOURCE_SUFFIXES = {".py", ".json", ".md", ".ini"}
OUTPUT_PREFIXES = ("evidence/", "results/")
FORBIDDEN_SUFFIXES = {".npz", ".csv", ".pyc", ".step", ".stp", ".urdf", ".tmp"}
FORBIDDEN_DIRECTORIES = {"__pycache__", ".pytest_cache", "raw", "raw_cases"}
TEMP_PREFIXES = (".technical-fixture-", ".nc-fixture-")


class FreezeError(RuntimeError):
    pass


def _strict() -> Any:
    return load_raw_modules()["strict_json"]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    junction = getattr(path, "is_junction", None)
    return bool(callable(junction) and junction())


def forbidden_artifacts(package_root: Path) -> list[str]:
    failures: list[str] = []
    for path in package_root.resolve().rglob("*"):
        relative = path.relative_to(package_root.resolve()).as_posix()
        if is_link(path):
            failures.append(f"LINK_OR_REPARSE:{relative}")
        parts = path.relative_to(package_root.resolve()).parts
        if any(part in FORBIDDEN_DIRECTORIES or part.startswith(TEMP_PREFIXES) for part in parts):
            failures.append(f"FORBIDDEN_DIRECTORY:{relative}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"FORBIDDEN_SUFFIX:{relative}")
    return sorted(set(failures))


def source_inventory(package_root: Path) -> list[dict[str, Any]]:
    root = package_root.resolve()
    failures = forbidden_artifacts(root)
    if failures:
        raise FreezeError(f"FORBIDDEN_ARTIFACTS:{failures}")
    records: list[dict[str, Any]] = []
    unknown: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(OUTPUT_PREFIXES):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            unknown.append(relative)
            continue
        records.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    if unknown:
        raise FreezeError(f"UNREGISTERED_LOCAL_FILE_TYPES:{unknown}")
    return records


def seal(value: dict[str, Any]) -> dict[str, Any]:
    if "document_sha256" in value:
        raise FreezeError("DOCUMENT_ALREADY_SEALED")
    result = dict(value)
    result["document_sha256"] = _strict().canonical_sha256(value)
    return result


def seal_valid(value: Any) -> bool:
    if not isinstance(value, dict) or type(value.get("document_sha256")) is not str:
        return False
    payload = {key: item for key, item in value.items() if key != "document_sha256"}
    return _strict().canonical_sha256(payload) == value["document_sha256"]


def strict_load(path: Path) -> Any:
    if is_link(path) or not path.is_file():
        raise FreezeError(f"STRICT_REGULAR_FILE_REQUIRED:{path}")
    return _strict().loads_bytes(path.read_bytes())


def project_record(path: Path, identifier: str, role: str) -> dict[str, Any]:
    root = project_root().resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise FreezeError("RECORD_OUTSIDE_PROJECT") from exc
    return {
        "id": identifier,
        "role": role,
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def record_valid(record: Any) -> bool:
    if not isinstance(record, dict) or set(record) != {"id", "role", "path", "bytes", "sha256"}:
        return False
    path = (project_root() / record["path"]).resolve()
    try:
        path.relative_to(project_root().resolve())
    except ValueError:
        return False
    return bool(
        path.is_file() and not is_link(path)
        and path.stat().st_size == record["bytes"]
        and file_sha256(path) == record["sha256"]
    )


def package_snapshot(package_root: Path) -> dict[str, dict[str, Any]]:
    root = package_root.resolve()
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if is_link(path):
            raise FreezeError(f"SNAPSHOT_LINK:{path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = {
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
    return result


def snapshot_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
    left, right = set(before), set(after)
    return {
        "added": sorted(right - left),
        "removed": sorted(left - right),
        "changed": sorted(name for name in left & right if before[name] != after[name]),
    }


__all__ = [
    "FreezeError", "file_sha256", "forbidden_artifacts", "package_snapshot",
    "project_record", "record_valid", "seal", "seal_valid", "snapshot_delta",
    "source_inventory", "strict_load",
]
