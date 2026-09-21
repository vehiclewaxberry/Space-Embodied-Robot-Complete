"""Canonical byte and digest helpers shared by the V2 fail-closed backends."""

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


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def file_record(path: Path, project_root: Path) -> dict[str, object]:
    resolved = Path(path).resolve()
    relative = resolved.relative_to(project_root.resolve()).as_posix()
    payload = resolved.read_bytes()
    return {
        "path": relative,
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def write_canonical_json(path: Path, document: Any) -> None:
    """Write strict canonical JSON with LF newlines on every host."""

    payload = canonical_json_bytes(document)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(payload + b"\n")


__all__ = (
    "canonical_digest",
    "canonical_json_bytes",
    "file_record",
    "sha256_bytes",
    "sha256_file",
    "write_canonical_json",
)
