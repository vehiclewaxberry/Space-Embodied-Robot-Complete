"""Strict parsing, immutable trees, canonical bytes and exact inventory checks."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

import yaml

from .constants import (
    EXACT_DIRECTORY_ALLOWLIST,
    EXACT_FILE_ALLOWLIST,
    FORBIDDEN_CACHE_PARTS,
    FORBIDDEN_SUFFIXES,
)


class StrictIOError(ValueError):
    """Fail-closed parser or inventory error."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader variant that refuses duplicate mapping keys."""


def _construct_unique_mapping(loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    out: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in out
        except TypeError as exc:
            raise StrictIOError("UNHASHABLE_YAML_KEY") from exc
        if duplicate:
            raise StrictIOError(f"DUPLICATE_YAML_KEY:{key}")
        out[key] = loader.construct_object(value_node, deep=deep)
    return out


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise StrictIOError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise StrictIOError(f"NONFINITE_JSON_CONSTANT:{value}")


def _finite_tree(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise StrictIOError(f"NONFINITE_NUMBER:{path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise StrictIOError(f"NON_STRING_KEY:{path}")
            _finite_tree(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _finite_tree(child, f"{path}[{index}]")


def parse_json_bytes(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StrictIOError("JSON_NOT_UTF8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, TypeError) as exc:
        raise StrictIOError(f"INVALID_JSON:{exc}") from exc
    if not isinstance(value, dict):
        raise StrictIOError("JSON_ROOT_NOT_OBJECT")
    _finite_tree(value)
    return value


def parse_yaml_bytes(raw: bytes) -> dict[str, Any]:
    try:
        value = yaml.load(raw.decode("utf-8"), Loader=_UniqueKeySafeLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise StrictIOError(f"INVALID_YAML:{exc}") from exc
    if not isinstance(value, dict):
        raise StrictIOError("YAML_ROOT_NOT_MAPPING")
    _finite_tree(value)
    return value


def deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): deep_freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(deep_freeze(child) for child in value)
    if isinstance(value, tuple):
        return tuple(deep_freeze(child) for child in value)
    return value


def deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): deep_thaw(child) for key, child in value.items()}
    if isinstance(value, list):
        return [deep_thaw(child) for child in value]
    if isinstance(value, tuple):
        return [deep_thaw(child) for child in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    _finite_tree(value)
    return json.dumps(
        deep_thaw(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    _finite_tree(value)
    return (json.dumps(deep_thaw(value), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = pretty_json_bytes(value)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def file_receipt(path: Path, rel: str) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": rel, "bytes": len(raw), "sha256": sha256_bytes(raw)}


def inventory_snapshot(package_root: Path) -> dict[str, Any]:
    files: dict[str, str] = {}
    directories: set[str] = set()
    for item in package_root.rglob("*"):
        rel = item.relative_to(package_root).as_posix()
        if item.is_dir():
            directories.add(rel)
        elif item.is_file():
            files[rel] = sha256_bytes(item.read_bytes())
        else:
            raise StrictIOError(f"NON_REGULAR_INVENTORY_ENTRY:{rel}")
    return {"files": dict(sorted(files.items())), "directories": sorted(directories)}


def validate_inventory_sets(
    files: Iterable[str], directories: Iterable[str], *, require_complete: bool = True
) -> dict[str, Any]:
    file_set = set(files)
    directory_set = set(directories)
    for rel in file_set:
        parts = set(Path(rel).parts)
        if parts & FORBIDDEN_CACHE_PARTS:
            raise StrictIOError(f"FORBIDDEN_CACHE:{rel}")
        if Path(rel).suffix.lower() in FORBIDDEN_SUFFIXES:
            raise StrictIOError(f"FORBIDDEN_ASSET:{rel}")
    for rel in directory_set:
        parts = set(Path(rel).parts)
        if parts & FORBIDDEN_CACHE_PARTS:
            raise StrictIOError(f"FORBIDDEN_CACHE_DIRECTORY:{rel}")
    extra_files = sorted(file_set - EXACT_FILE_ALLOWLIST)
    extra_directories = sorted(directory_set - EXACT_DIRECTORY_ALLOWLIST)
    if extra_files:
        raise StrictIOError(f"EXTRA_FILE:{extra_files[0]}")
    if extra_directories:
        raise StrictIOError(f"EXTRA_DIRECTORY:{extra_directories[0]}")
    missing_files = sorted(EXACT_FILE_ALLOWLIST - file_set)
    missing_directories = sorted(EXACT_DIRECTORY_ALLOWLIST - directory_set)
    if require_complete and missing_files:
        raise StrictIOError(f"MISSING_FILE:{missing_files[0]}")
    if require_complete and missing_directories:
        raise StrictIOError(f"MISSING_DIRECTORY:{missing_directories[0]}")
    return {
        "exact": not extra_files and not extra_directories and (not require_complete or (not missing_files and not missing_directories)),
        "file_count": len(file_set),
        "directory_count": len(directory_set),
        "missing_files": missing_files,
        "missing_directories": missing_directories,
        "extra_files": extra_files,
        "extra_directories": extra_directories,
    }


def validate_inventory(package_root: Path, *, require_complete: bool = True) -> dict[str, Any]:
    snapshot = inventory_snapshot(package_root)
    result = validate_inventory_sets(snapshot["files"], snapshot["directories"], require_complete=require_complete)
    result["file_hashes"] = snapshot["files"]
    return result
