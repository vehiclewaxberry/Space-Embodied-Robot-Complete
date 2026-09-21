"""SHA-256 provenance helpers. Every consumed and produced artifact is hashed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_canonical_json(obj) -> str:
    """Hash of a canonical (sorted-key, compact) JSON serialization."""
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_file_sha256(path: str | Path, expected: str) -> bool:
    """True only when the file exists and its digest matches exactly."""
    p = Path(path)
    if not p.is_file():
        return False
    return sha256_file(p) == expected.lower()
