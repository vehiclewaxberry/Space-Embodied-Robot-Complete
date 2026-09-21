"""Fail-closed, single-read source binding for mechanical evidence."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping
import xml.etree.ElementTree as ET

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[3]
BINDINGS_PATH = PACKAGE_ROOT / "contracts" / "MECHANICAL_EVIDENCE_SOURCE_BINDINGS_V1.json"
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
REPARSE_POINT = 0x400


class AdmissionError(ValueError):
    """A source cannot be admitted without weakening the frozen contract."""


def _reject_constant(token: str) -> None:
    raise AdmissionError(f"non-finite JSON number is forbidden: {token}")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AdmissionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_bytes(payload: bytes) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AdmissionError("JSON must be UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, TypeError) as exc:
        raise AdmissionError(f"invalid strict JSON: {exc}") from exc


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, (str, int, float, bool, type(None))):
            raise AdmissionError("YAML mapping keys must be scalar")
        if key in result:
            raise AdmissionError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def strict_yaml_bytes(payload: bytes) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AdmissionError("YAML must be UTF-8") from exc
    try:
        value = yaml.load(text, Loader=_UniqueKeyLoader)
    except (yaml.YAMLError, AdmissionError) as exc:
        raise AdmissionError(f"invalid strict YAML: {exc}") from exc
    _reject_nonfinite(value)
    return value


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AdmissionError("non-finite YAML number is forbidden")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_nonfinite(key)
            _reject_nonfinite(child)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            _reject_nonfinite(child)
        return


def deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): deep_freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(deep_freeze(child) for child in value)
    if isinstance(value, tuple):
        return tuple(deep_freeze(child) for child in value)
    if isinstance(value, set):
        return frozenset(deep_freeze(child) for child in value)
    return value


def thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [thaw(child) for child in value]
    if isinstance(value, frozenset):
        return sorted(thaw(child) for child in value)
    return value


def validate_project_relative_path(relative_path: str) -> PurePosixPath:
    if not isinstance(relative_path, str) or not relative_path:
        raise AdmissionError("path must be a non-empty string")
    if "\\" in relative_path or ":" in relative_path:
        raise AdmissionError("path must use canonical project-root POSIX syntax")
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise AdmissionError("absolute, empty, dot, and traversal paths are forbidden")
    if pure.as_posix() != relative_path:
        raise AdmissionError("path alias or non-canonical spelling is forbidden")
    return pure


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        stat = path.lstat()
    except OSError as exc:
        raise AdmissionError(f"cannot lstat path component: {path}") from exc
    return path.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & REPARSE_POINT)


def resolve_bound_path(project_root: Path, relative_path: str, *, must_exist: bool = True) -> Path:
    pure = validate_project_relative_path(relative_path)
    root = project_root.resolve(strict=True)
    if _is_reparse_or_symlink(root):
        raise AdmissionError("project root must not be a symlink or reparse point")
    candidate = root.joinpath(*pure.parts)
    cursor = root
    for part in pure.parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            if _is_reparse_or_symlink(cursor):
                raise AdmissionError(f"symlink/reparse component forbidden: {relative_path}")
        elif must_exist:
            raise AdmissionError(f"bound source is absent: {relative_path}")
        else:
            break
    if must_exist:
        try:
            resolved = candidate.resolve(strict=True)
            canonical = resolved.relative_to(root).as_posix()
        except (OSError, ValueError) as exc:
            raise AdmissionError(f"path escapes project root: {relative_path}") from exc
        if canonical != relative_path:
            raise AdmissionError(f"path alias/case mismatch: {relative_path} != {canonical}")
        if not resolved.is_file():
            raise AdmissionError(f"bound source is not a regular file: {relative_path}")
        return resolved
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise AdmissionError(f"absent path escapes project root: {relative_path}") from exc
    return candidate


def verify_payload(payload: bytes, expected_bytes: int, expected_sha256: str) -> str:
    if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes <= 0:
        raise AdmissionError("expected bytes must be a positive integer")
    if not isinstance(expected_sha256, str) or SHA256_RE.fullmatch(expected_sha256) is None:
        raise AdmissionError("expected SHA256 must be 64 uppercase hexadecimal characters")
    actual_sha = hashlib.sha256(payload).hexdigest().upper()
    if len(payload) != expected_bytes:
        raise AdmissionError(f"byte-count mismatch: expected {expected_bytes}, got {len(payload)}")
    if actual_sha != expected_sha256:
        raise AdmissionError(f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha}")
    return actual_sha


def _parse_payload(payload: bytes, artifact_format: str, expected: Mapping[str, Any]) -> Any:
    if artifact_format == "JSON":
        parsed = strict_json_bytes(payload)
    elif artifact_format == "YAML":
        parsed = strict_yaml_bytes(payload)
    elif artifact_format == "URDF_XML":
        upper = payload.upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise AdmissionError("DTD/entity declarations are forbidden in URDF")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise AdmissionError(f"invalid URDF XML: {exc}") from exc
        if root.tag != expected.get("expected_root"):
            raise AdmissionError("URDF root mismatch")
        return payload
    elif artifact_format == "BINARY_STL":
        if len(payload) < 84:
            raise AdmissionError("STL evidence is empty/truncated")
        return None
    else:
        raise AdmissionError(f"unsupported source format: {artifact_format}")
    expected_schema = expected.get("expected_schema")
    if not isinstance(parsed, Mapping) or parsed.get("schema") != expected_schema:
        raise AdmissionError(
            f"schema mismatch for {expected.get('id')}: expected {expected_schema!r}"
        )
    return parsed


@dataclass(frozen=True)
class BoundArtifact:
    artifact_id: str
    relative_path: str
    byte_count: int
    sha256: str
    artifact_format: str
    payload: bytes
    parsed: Any
    read_count: int = 1


@dataclass(frozen=True)
class EvidenceSnapshot:
    project_root: Path
    binding_relative_path: str
    binding_bytes: int
    binding_sha256: str
    artifacts: Mapping[str, BoundArtifact]
    required_absent_paths: tuple[str, ...]


def load_snapshot(
    project_root: Path,
    bindings_path: Path,
    *,
    require_default_binding_location: bool = False,
) -> EvidenceSnapshot:
    root = project_root.resolve(strict=True)
    try:
        binding_relative = bindings_path.absolute().relative_to(root).as_posix()
    except ValueError as exc:
        raise AdmissionError("binding contract is outside project root") from exc
    binding_resolved = resolve_bound_path(root, binding_relative)
    if require_default_binding_location and bindings_path.absolute() != BINDINGS_PATH.absolute():
        raise AdmissionError("production loader accepts only the frozen binding contract")
    # The contract itself is also captured by one immutable byte snapshot.
    with binding_resolved.open("rb") as handle:
        binding_payload = handle.read()
    binding_sha = hashlib.sha256(binding_payload).hexdigest().upper()
    binding = strict_json_bytes(binding_payload)
    if not isinstance(binding, Mapping) or binding.get("schema") != "MECHANICAL_EVIDENCE_SOURCE_BINDINGS_V1":
        raise AdmissionError("source-binding contract schema mismatch")
    artifacts_spec = binding.get("artifacts")
    if not isinstance(artifacts_spec, list) or not artifacts_spec:
        raise AdmissionError("source-binding contract must contain artifacts")
    bound: dict[str, BoundArtifact] = {}
    seen_paths: set[str] = set()
    for spec in artifacts_spec:
        if not isinstance(spec, Mapping):
            raise AdmissionError("artifact binding must be an object")
        artifact_id = spec.get("id")
        relative_path = spec.get("path")
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in bound:
            raise AdmissionError("artifact IDs must be unique non-empty strings")
        if not isinstance(relative_path, str) or relative_path in seen_paths:
            raise AdmissionError("artifact paths must be unique strings")
        path = resolve_bound_path(root, relative_path)
        # Exactly one file open/read supplies bytes, hash, and parser input.
        with path.open("rb") as handle:
            payload = handle.read()
        sha = verify_payload(payload, spec.get("bytes"), spec.get("sha256"))
        parsed = _parse_payload(payload, spec.get("format"), spec)
        bound[artifact_id] = BoundArtifact(
            artifact_id=artifact_id,
            relative_path=relative_path,
            byte_count=len(payload),
            sha256=sha,
            artifact_format=spec.get("format"),
            payload=payload,
            parsed=deep_freeze(parsed),
        )
        seen_paths.add(relative_path)
    absent_spec = binding.get("required_absent_paths")
    if not isinstance(absent_spec, list) or not absent_spec:
        raise AdmissionError("required_absent_paths must be a non-empty list")
    absences: list[str] = []
    for relative_path in absent_spec:
        candidate = resolve_bound_path(root, relative_path, must_exist=False)
        if candidate.exists() or candidate.is_symlink():
            raise AdmissionError(f"artifact required absent but exists: {relative_path}")
        absences.append(relative_path)
    return EvidenceSnapshot(
        project_root=root,
        binding_relative_path=binding_relative,
        binding_bytes=len(binding_payload),
        binding_sha256=binding_sha,
        artifacts=MappingProxyType(bound),
        required_absent_paths=tuple(absences),
    )


def load_default_snapshot() -> EvidenceSnapshot:
    return load_snapshot(PROJECT_ROOT, BINDINGS_PATH, require_default_binding_location=True)
