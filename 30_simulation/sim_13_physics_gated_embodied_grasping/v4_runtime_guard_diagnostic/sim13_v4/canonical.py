"""Canonical byte and digest helpers shared by the V4 diagnostic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def canonical_digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def file_record(path: Path, project_root: Path) -> dict[str, object]:
    resolved = path.resolve()
    relative = resolved.relative_to(project_root.resolve()).as_posix()
    payload = resolved.read_bytes()
    return {
        "path": relative,
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


__all__ = (
    "canonical_digest",
    "canonical_json_bytes",
    "file_record",
    "sha256_bytes",
)
