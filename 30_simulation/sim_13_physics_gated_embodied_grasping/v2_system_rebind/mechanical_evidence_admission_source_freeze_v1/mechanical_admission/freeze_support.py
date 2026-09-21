"""Deterministic source inventory and canonical JSON helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .strict_io import PACKAGE_ROOT, PROJECT_ROOT


EXCLUDED_PARTS = {"evidence", "results", "__pycache__", ".pytest_cache"}


def canonical_json_bytes(document: Any) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def file_receipt(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def source_inventory() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(PACKAGE_ROOT.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or any(part in EXCLUDED_PARTS for part in path.relative_to(PACKAGE_ROOT).parts):
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        records.append(file_receipt(path))
    return records


def package_inventory() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(PACKAGE_ROOT.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or any(part in {"__pycache__", ".pytest_cache"} for part in path.relative_to(PACKAGE_ROOT).parts):
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        records.append(file_receipt(path))
    return records


def write_canonical_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(document))
