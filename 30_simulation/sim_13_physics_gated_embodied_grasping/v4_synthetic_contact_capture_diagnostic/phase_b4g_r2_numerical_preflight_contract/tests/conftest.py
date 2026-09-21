from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parents[1]
PROJECT_ROOT = HERE.parents[3]
CONTRACTS = HERE / "contracts"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def load_contract(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def has_null_leaf(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return any(has_null_leaf(key) or has_null_leaf(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(has_null_leaf(item) for item in value)
    return False


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()
