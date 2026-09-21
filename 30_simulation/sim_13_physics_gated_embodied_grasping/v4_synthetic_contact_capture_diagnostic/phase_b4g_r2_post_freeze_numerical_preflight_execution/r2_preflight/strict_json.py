"""Strict JSON and canonical hashing used by the R2 freeze.

The standard decoder accepts duplicate keys and several non-finite spellings;
both behaviours are forbidden at this evidence boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable


class StrictJSONError(ValueError):
    """Raised when a JSON value is ambiguous or outside the frozen contract."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _reject_constant(token: str) -> None:
    raise StrictJSONError(f"NONFINITE_JSON_TOKEN:{token}")


def validate_finite_tree(value: Any, pointer: str = "", *, allow_null: bool = False) -> None:
    """Reject non-JSON types, non-finite floats, and non-string object keys."""

    if value is None:
        if allow_null:
            return
        raise StrictJSONError(f"NULL_JSON_LEAF:{pointer or '/'}")
    if isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StrictJSONError(f"NONFINITE_JSON_NUMBER:{pointer or '/'}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_finite_tree(item, f"{pointer}/{index}", allow_null=allow_null)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise StrictJSONError(f"NONSTRING_JSON_KEY:{pointer or '/'}")
            escaped = key.replace("~", "~0").replace("/", "~1")
            validate_finite_tree(item, f"{pointer}/{escaped}", allow_null=allow_null)
        return
    raise StrictJSONError(f"NON_JSON_TYPE:{pointer or '/'}:{type(value).__name__}")


def loads(text: str, *, allow_null: bool = False) -> Any:
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise StrictJSONError(f"INVALID_JSON:{exc.msg}") from exc
    validate_finite_tree(value, allow_null=allow_null)
    return value


def load_path(path: Path, *, allow_null: bool = False) -> Any:
    if not path.is_file() or path.is_symlink():
        raise StrictJSONError(f"REGULAR_JSON_FILE_REQUIRED:{path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise StrictJSONError(f"UTF8_REQUIRED:{path}") from exc
    return loads(text, allow_null=allow_null)


def canonical_bytes(value: Any) -> bytes:
    validate_finite_tree(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def contains_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return any(contains_null(item) for item in value)
    if isinstance(value, dict):
        return any(contains_null(item) for item in value.values())
    return False


def iter_json_pointers(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    """Yield every container and leaf so a rehydrator can prove full consumption."""

    yield pointer or "/", value
    if isinstance(value, dict):
        for key, item in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            yield from iter_json_pointers(item, f"{pointer}/{escaped}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_json_pointers(item, f"{pointer}/{index}")


def atomic_write_json(path: Path, value: Any) -> None:
    """Write JSON atomically; the temporary file is removed by os.replace."""

    validate_finite_tree(value)
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
