"""Canonical, atomic and pickle-free evidence I/O."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

import numpy as np


class EvidenceIOError(RuntimeError):
    """Evidence could not be read or published without ambiguity."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object while rejecting parser-dependent duplicate keys."""

    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise EvidenceIOError(f"JSON_DUPLICATE_KEY:{key}")
        value[key] = item
    return value


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_object_keys,
        )
    except EvidenceIOError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceIOError(f"JSON_READ_FAILED:{Path(path).name}") from error
    if not isinstance(value, dict):
        raise EvidenceIOError(f"JSON_ROOT_NOT_OBJECT:{Path(path).name}")
    return value


def atomic_write_json(path: Path, value: Any) -> None:
    """Write the frozen canonical JSON representation and fsync before replace."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_bytes(value) + b"\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _native_array(name: str, value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype.kind in "OUSV":
        raise EvidenceIOError(f"NPZ_OBJECT_OR_STRING_ARRAY_FORBIDDEN:{name}")
    if array.dtype.kind == "b":
        result = np.asarray(array, dtype=np.bool_)
    elif array.dtype.kind in "iu":
        result = np.asarray(array, dtype="<i8")
    elif array.dtype.kind in "fc":
        if array.dtype.kind == "c":
            raise EvidenceIOError(f"NPZ_COMPLEX_ARRAY_FORBIDDEN:{name}")
        result = np.asarray(array, dtype="<f8")
    else:
        raise EvidenceIOError(f"NPZ_UNSUPPORTED_DTYPE:{name}:{array.dtype}")
    if result.dtype.kind == "f" and not np.all(np.isfinite(result)):
        raise EvidenceIOError(f"NPZ_NONFINITE_ARRAY_FORBIDDEN:{name}")
    return np.ascontiguousarray(result)


def atomic_write_npz(path: Path, arrays: Mapping[str, Any]) -> dict[str, Any]:
    """Write one compressed NPZ containing only numeric/bool arrays."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = {name: _native_array(name, value) for name, value in arrays.items()}
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            np.savez_compressed(stream, **normalized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "bytes": target.stat().st_size,
        "sha256": sha256_file(target),
        "arrays": sorted(normalized),
    }


def verify_npz(path: Path, *, size: int, sha256: str, arrays: list[str]) -> None:
    target = Path(path)
    if not target.is_file() or target.stat().st_size != int(size):
        raise EvidenceIOError(f"NPZ_SIZE_MISMATCH:{target.name}")
    if sha256_file(target) != str(sha256).upper():
        raise EvidenceIOError(f"NPZ_SHA256_MISMATCH:{target.name}")
    try:
        with np.load(target, allow_pickle=False) as archive:
            if sorted(archive.files) != sorted(arrays):
                raise EvidenceIOError(f"NPZ_ARRAY_INVENTORY_MISMATCH:{target.name}")
            for name in archive.files:
                value = archive[name]
                if value.dtype.kind in "OUSV":
                    raise EvidenceIOError(f"NPZ_OBJECT_OR_STRING_ARRAY:{target.name}:{name}")
    except (OSError, ValueError) as error:
        raise EvidenceIOError(f"NPZ_ALLOW_PICKLE_FALSE_READ_FAILED:{target.name}") from error


def array_payload_sha256(arrays: Mapping[str, Any]) -> str:
    """Hash canonical array names, dtypes, shapes and uncompressed numeric bytes."""

    digest = hashlib.sha256()
    for name in sorted(arrays):
        array = _native_array(name, arrays[name])
        header = canonical_bytes({
            "name": name,
            "dtype": array.dtype.str,
            "shape": list(array.shape),
        })
        digest.update(len(header).to_bytes(8, "big"))
        digest.update(header)
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest().upper()


def display_path(path: Path, project_root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(project_root).resolve()).as_posix()
    except ValueError:
        return Path(path).resolve().as_posix()
