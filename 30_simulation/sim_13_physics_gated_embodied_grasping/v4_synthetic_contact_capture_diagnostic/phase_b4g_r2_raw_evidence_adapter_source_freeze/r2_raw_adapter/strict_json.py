"""Strict, null-free JSON and canonical hashing for the adapter boundary."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


class StrictJSONError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _reject_constant(token: str) -> None:
    raise StrictJSONError(f"NONFINITE_JSON_TOKEN:{token}")


def validate_tree(value: Any, pointer: str = "") -> None:
    if value is None:
        raise StrictJSONError(f"NULL_JSON_LEAF:{pointer or '/'}")
    if isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StrictJSONError(f"NONFINITE_JSON_NUMBER:{pointer or '/'}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_tree(item, f"{pointer}/{index}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str:
                raise StrictJSONError(f"NONSTRING_JSON_KEY:{pointer or '/'}")
            escaped = key.replace("~", "~0").replace("/", "~1")
            validate_tree(item, f"{pointer}/{escaped}")
        return
    raise StrictJSONError(f"NON_JSON_TYPE:{pointer or '/'}:{type(value).__name__}")


def loads_bytes(payload: bytes) -> Any:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise StrictJSONError("UTF8_REQUIRED") from exc
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise StrictJSONError(f"INVALID_JSON:{exc.msg}") from exc
    validate_tree(value)
    return value


def canonical_bytes(value: Any) -> bytes:
    validate_tree(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def atomic_write_json(path: Path, value: Any) -> None:
    validate_tree(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
