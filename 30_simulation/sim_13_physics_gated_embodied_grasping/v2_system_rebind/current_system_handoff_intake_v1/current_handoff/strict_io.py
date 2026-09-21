"""Strict, one-read, hash-pinned source ingestion for the current-system handoff."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[3]
CROSSWALK_PATH = PACKAGE_ROOT / "contracts" / "FIELD_SOURCE_CROSSWALK_V1.json"
REPARSE_POINT = 0x400
REQUIRED_ABSENT_PATHS_EXACT = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf",
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml",
)
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
YAML_SCHEMA_RE = re.compile(r"(?m)^schema:[ \t]*([^#\r\n]+?)[ \t]*\r?$")
WINDOWS_RESERVED_SEGMENTS = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class IntakeError(ValueError):
    """A fail-closed intake rejection with a machine classification."""

    def __init__(self, classification: str, message: str):
        super().__init__(message)
        self.classification = classification


def _reject_constant(token: str) -> None:
    raise IntakeError("MALFORMED", f"non-finite JSON number forbidden: {token}")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IntakeError("MALFORMED", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_bytes(payload: bytes) -> Any:
    """Parse finite UTF-8 JSON while rejecting duplicate keys."""

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntakeError("MALFORMED", "JSON must be UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except IntakeError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise IntakeError("MALFORMED", f"invalid strict JSON: {exc}") from exc
    reject_nonfinite(value)
    return value


def reject_nonfinite(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise IntakeError("MALFORMED", "non-finite number forbidden")
        return
    if isinstance(value, Mapping):
        for child in value.values():
            reject_nonfinite(child)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            reject_nonfinite(child)
        return
    raise IntakeError("MALFORMED", f"unsupported data type: {type(value).__name__}")


def require_exact_keys(value: Any, expected: set[str], context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IntakeError("MALFORMED", f"{context} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise IntakeError("MALFORMED", f"{context} keys differ; missing={missing}, extra={extra}")
    return value


def deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): deep_freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(deep_freeze(child) for child in value)
    if isinstance(value, tuple):
        return tuple(deep_freeze(child) for child in value)
    return value


def thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [thaw(child) for child in value]
    return value


def validate_project_relative_path(relative_path: str) -> PurePosixPath:
    if not isinstance(relative_path, str) or not relative_path:
        raise IntakeError("MALFORMED", "path must be a non-empty string")
    if any(ord(character) < 32 or ord(character) == 127 for character in relative_path):
        raise IntakeError("MALFORMED", "path control characters are forbidden")
    if "\\" in relative_path or ":" in relative_path:
        raise IntakeError("MALFORMED", "path must be canonical project-relative POSIX syntax")
    if "//" in relative_path or "/./" in relative_path or relative_path.endswith("/."):
        raise IntakeError("MALFORMED", "path aliases are forbidden")
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or pure.as_posix() != relative_path:
        raise IntakeError("MALFORMED", "absolute or non-canonical path forbidden")
    if any(part in ("", ".", "..") for part in pure.parts):
        raise IntakeError("MALFORMED", "empty, dot, or traversal path forbidden")
    for part in pure.parts:
        if part.endswith((" ", ".")):
            raise IntakeError("MALFORMED", "Windows trailing-dot/space path aliases are forbidden")
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED_SEGMENTS:
            raise IntakeError("MALFORMED", f"Windows reserved path segment forbidden: {part}")
    if any(part.lower() in {"desktop", "downloads", "temp", "tmp"} for part in pure.parts):
        raise IntakeError("MALFORMED", "desktop/download/temp ghost paths are forbidden")
    return pure


def _is_link_or_reparse(path: Path) -> bool:
    try:
        stat = path.lstat()
    except OSError as exc:
        raise IntakeError("MISSING", f"cannot lstat path: {path}") from exc
    return path.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & REPARSE_POINT)


def resolve_bound_path(project_root: Path, relative_path: str, *, must_exist: bool = True) -> Path:
    pure = validate_project_relative_path(relative_path)
    try:
        root = project_root.resolve(strict=True)
    except OSError as exc:
        raise IntakeError("MISSING", "project root unavailable") from exc
    if _is_link_or_reparse(root):
        raise IntakeError("MALFORMED", "project root may not be a symlink/reparse point")
    cursor = root
    for part in pure.parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            if _is_link_or_reparse(cursor):
                raise IntakeError("MALFORMED", f"symlink/reparse path forbidden: {relative_path}")
        elif must_exist:
            raise IntakeError("MISSING", f"bound source missing: {relative_path}")
        else:
            break
    candidate = root.joinpath(*pure.parts)
    if not must_exist:
        try:
            candidate.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise IntakeError("MALFORMED", "absent path escapes project root") from exc
        return candidate
    try:
        resolved = candidate.resolve(strict=True)
        canonical = resolved.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise IntakeError("MISSING", f"cannot resolve bound source: {relative_path}") from exc
    if canonical != relative_path:
        raise IntakeError("MALFORMED", f"path alias/case mismatch: {relative_path} != {canonical}")
    if not resolved.is_file():
        raise IntakeError("MALFORMED", f"bound source is not a regular file: {relative_path}")
    return resolved


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def verify_payload(payload: bytes, expected_bytes: Any, expected_sha256: Any) -> str:
    if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes <= 0:
        raise IntakeError("MALFORMED", "expected byte count must be a positive integer")
    if not isinstance(expected_sha256, str) or SHA256_RE.fullmatch(expected_sha256) is None:
        raise IntakeError("MALFORMED", "expected SHA-256 must be uppercase hexadecimal")
    actual = sha256_bytes(payload)
    if len(payload) != expected_bytes or actual != expected_sha256:
        raise IntakeError(
            "HASH_DRIFT",
            f"source bytes/hash drift: expected {expected_bytes}/{expected_sha256}, got {len(payload)}/{actual}",
        )
    return actual


def _parse_yaml_schema(payload: bytes, expected_schema: str) -> Mapping[str, Any]:
    """Treat an externally pinned YAML source as opaque bytes plus one schema marker.

    This is deliberately not an intake YAML parser. All intake, authority, Gate, and
    receipt records in this package are strict JSON. The complete opaque YAML bytes
    are authenticated by length and SHA-256 before this marker check.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntakeError("MALFORMED", "pinned YAML must be UTF-8") from exc
    matches = [match.strip().strip("'\"") for match in YAML_SCHEMA_RE.findall(text)]
    if len(matches) != 1 or matches[0] != expected_schema:
        raise IntakeError("MALFORMED", f"pinned YAML schema mismatch: {matches!r}")
    return {"schema": matches[0], "pinned_payload_text": text}


def parse_bound_payload(payload: bytes, artifact_format: str, expected_schema: str, schema_field: str) -> Any:
    if artifact_format == "JSON":
        parsed = strict_json_bytes(payload)
        if not isinstance(parsed, Mapping) or parsed.get(schema_field) != expected_schema:
            raise IntakeError("MALFORMED", f"JSON schema mismatch: expected {expected_schema}")
        return parsed
    if artifact_format == "YAML_PINNED":
        if schema_field != "schema":
            raise IntakeError("MALFORMED", "YAML schema field must be 'schema'")
        return _parse_yaml_schema(payload, expected_schema)
    raise IntakeError("MALFORMED", f"unsupported source format: {artifact_format}")


@dataclass(frozen=True)
class BoundArtifact:
    artifact_id: str
    relative_path: str
    byte_count: int
    sha256: str
    artifact_format: str
    parsed: Any
    payload: bytes
    read_count: int = 1


@dataclass(frozen=True)
class SourceSnapshot:
    project_root: Path
    crosswalk_relative_path: str
    crosswalk_bytes: int
    crosswalk_sha256: str
    crosswalk: Mapping[str, Any]
    artifacts: Mapping[str, BoundArtifact]
    required_absent_paths: tuple[str, ...]


_CROSSWALK_KEYS = {
    "schema",
    "source_policy",
    "classification_enum",
    "required_domains",
    "artifacts",
    "domain_bindings",
    "required_absent_paths",
}
_ARTIFACT_KEYS = {"id", "path", "bytes", "sha256", "format", "expected_schema", "schema_field"}


def load_snapshot(project_root: Path, crosswalk_path: Path, *, require_default: bool = False) -> SourceSnapshot:
    root = project_root.resolve(strict=True)
    try:
        relative = crosswalk_path.absolute().relative_to(root).as_posix()
    except ValueError as exc:
        raise IntakeError("MALFORMED", "crosswalk contract is outside project root") from exc
    if require_default and crosswalk_path.absolute() != CROSSWALK_PATH.absolute():
        raise IntakeError("OWNER_REQUIRED", "production intake accepts only the frozen crosswalk")
    contract_path = resolve_bound_path(root, relative)
    with contract_path.open("rb") as handle:
        crosswalk_payload = handle.read()
    crosswalk = strict_json_bytes(crosswalk_payload)
    require_exact_keys(crosswalk, _CROSSWALK_KEYS, "FIELD_SOURCE_CROSSWALK_V1")
    if crosswalk.get("schema") != "FIELD_SOURCE_CROSSWALK_V1":
        raise IntakeError("MALFORMED", "crosswalk schema mismatch")
    specs = crosswalk.get("artifacts")
    if not isinstance(specs, list) or not specs:
        raise IntakeError("MALFORMED", "crosswalk artifacts must be a non-empty list")
    artifacts: dict[str, BoundArtifact] = {}
    seen_paths: set[str] = set()
    for raw_spec in specs:
        spec = require_exact_keys(raw_spec, _ARTIFACT_KEYS, "crosswalk artifact")
        artifact_id = spec["id"]
        relative_path = spec["path"]
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in artifacts:
            raise IntakeError("MALFORMED", "artifact IDs must be unique non-empty strings")
        if not isinstance(relative_path, str) or relative_path in seen_paths:
            raise IntakeError("MALFORMED", "artifact paths must be unique strings")
        path = resolve_bound_path(root, relative_path)
        # One and only one open/read supplies byte count, SHA-256, and parser input.
        with path.open("rb") as handle:
            payload = handle.read()
        digest = verify_payload(payload, spec["bytes"], spec["sha256"])
        parsed = parse_bound_payload(payload, spec["format"], spec["expected_schema"], spec["schema_field"])
        artifacts[artifact_id] = BoundArtifact(
            artifact_id=artifact_id,
            relative_path=relative_path,
            byte_count=len(payload),
            sha256=digest,
            artifact_format=spec["format"],
            parsed=deep_freeze(parsed),
            payload=payload,
        )
        seen_paths.add(relative_path)
    absent = crosswalk.get("required_absent_paths")
    if not isinstance(absent, list) or tuple(absent) != REQUIRED_ABSENT_PATHS_EXACT:
        raise IntakeError("OWNER_REQUIRED", "required_absent_paths must be the exact system URDF/interface pair")
    absent_paths: list[str] = []
    for relative_path in absent:
        candidate = resolve_bound_path(root, relative_path, must_exist=False)
        if candidate.exists() or candidate.is_symlink():
            raise IntakeError("OWNER_REQUIRED", f"unadmitted current-system artifact exists: {relative_path}")
        absent_paths.append(relative_path)
    return SourceSnapshot(
        project_root=root,
        crosswalk_relative_path=relative,
        crosswalk_bytes=len(crosswalk_payload),
        crosswalk_sha256=sha256_bytes(crosswalk_payload),
        crosswalk=deep_freeze(crosswalk),
        artifacts=MappingProxyType(artifacts),
        required_absent_paths=tuple(absent_paths),
    )


def load_default_snapshot() -> SourceSnapshot:
    return load_snapshot(PROJECT_ROOT, CROSSWALK_PATH, require_default=True)
