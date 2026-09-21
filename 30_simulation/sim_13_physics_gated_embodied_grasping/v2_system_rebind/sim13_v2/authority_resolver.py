"""Resolve Sim13 V2 gates only from a fixed, hash-bound package config."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import (
    GateEvidence,
    GateSnapshot,
    GateState,
    REQUIRED_GATES,
    _authority_snapshot,
    unknown_evidence,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_CANONICAL_AUTHORITY_BINDINGS_PATH = (
    _PACKAGE_ROOT / "config" / "authority_bindings_v2.json"
)
_AUTHORITY_BINDINGS_PATH = _CANONICAL_AUTHORITY_BINDINGS_PATH
_EXPECTED_BINDINGS_SHA256 = (
    "C3B1930981BF9871094FEB40F45E2440E608E557B93171BC72E2DA9A622F52C1"
)
_CONFIG_SCHEMA = "SIM13_V2_AUTHORITY_BINDINGS_V1"
_CONFIG_SCOPE = "SOURCE_ONLY_PREBIND_NOT_BOUND_NOT_LOADED"
_TOP_LEVEL_FIELDS = frozenset(
    {"schema", "scope", "project_root", "artifacts", "gate_sources"}
)
_ARTIFACT_FIELDS = frozenset(
    {"path", "bytes", "sha256", "schema", "verdict", "next_stage_authorized"}
)
_GATE_SOURCE_FIELDS = frozenset({"artifact", "field", "pass_value"})
_SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
_MISSING = object()


@dataclass(frozen=True)
class ResolvedArtifact:
    artifact_id: str
    path: Path | None
    verified: bool
    reason_code: str
    byte_count: int | None = None
    sha256: str | None = None
    payload: bytes | None = None
    document: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class AuthorityResolution:
    config_path: Path
    config_sha256: str | None
    config_valid: bool
    scope: str
    snapshot: GateSnapshot
    artifacts: Mapping[str, ResolvedArtifact]
    errors: tuple[str, ...]

    @property
    def system_urdf(self) -> ResolvedArtifact | None:
        return self.artifacts.get("system_urdf")


def _unknown_snapshot(reason: str) -> GateSnapshot:
    return _authority_snapshot(unknown_evidence(reason))


def _is_exact(actual: Any, expected: Any) -> bool:
    return type(actual) is type(expected) and actual == expected


def _load_structured_document(payload: bytes) -> Mapping[str, Any] | None:
    try:
        parsed = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        try:
            import yaml  # type: ignore

            parsed = yaml.safe_load(payload.decode("utf-8-sig"))
        except (ImportError, UnicodeDecodeError, ValueError, TypeError):
            return None
    return parsed if isinstance(parsed, Mapping) else None


def _json_pointer(document: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return _MISSING
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                return _MISSING
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit():
                return _MISSING
            index = int(token)
            if index >= len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def _contained_path(root: Path, relative_value: Any) -> Path:
    if not isinstance(relative_value, str) or not relative_value.strip():
        raise ValueError("artifact path must be a non-empty relative string")
    relative = Path(relative_value)
    if relative.is_absolute():
        raise ValueError("absolute artifact path is forbidden")
    candidate = (root / relative).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("artifact path escapes the project root") from exc
    return candidate


class AuthorityResolver:
    """Fixed-path authority resolver; the constructor accepts no path override."""

    def __init__(self) -> None:
        self._bindings_path = _AUTHORITY_BINDINGS_PATH.resolve(strict=False)

    @property
    def bindings_path(self) -> Path:
        return self._bindings_path

    def resolve(self) -> AuthorityResolution:
        errors: list[str] = []
        if self._bindings_path != _AUTHORITY_BINDINGS_PATH.resolve(strict=False):
            return self._invalid(("AUTHORITY_CONFIG_PATH_NOT_FIXED",))
        if not self._bindings_path.is_file():
            return self._invalid(("AUTHORITY_CONFIG_MISSING",))
        try:
            raw = self._bindings_path.read_bytes()
            config = json.loads(raw.decode("utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return self._invalid(("AUTHORITY_CONFIG_UNREADABLE_OR_NOT_JSON",))
        config_sha256 = hashlib.sha256(raw).hexdigest().upper()
        if (
            self._bindings_path
            == _CANONICAL_AUTHORITY_BINDINGS_PATH.resolve(strict=False)
            and config_sha256 != _EXPECTED_BINDINGS_SHA256
        ):
            return self._invalid(("AUTHORITY_CONFIG_SHA256_MISMATCH",))
        if not isinstance(config, Mapping) or set(config) != _TOP_LEVEL_FIELDS:
            return self._invalid(("AUTHORITY_CONFIG_TOP_LEVEL_SCHEMA_MISMATCH",))
        if config["schema"] != _CONFIG_SCHEMA:
            return self._invalid(("AUTHORITY_CONFIG_SCHEMA_MISMATCH",))
        if config["scope"] != _CONFIG_SCOPE:
            return self._invalid(("AUTHORITY_CONFIG_SCOPE_MISMATCH",))

        project_root_value = config["project_root"]
        if not isinstance(project_root_value, str) or Path(project_root_value).is_absolute():
            return self._invalid(("PROJECT_ROOT_MUST_BE_RELATIVE",))
        project_root = (self._bindings_path.parent / project_root_value).resolve(strict=False)
        if project_root != _EXPECTED_PROJECT_ROOT.resolve(strict=False):
            return self._invalid(("PROJECT_ROOT_DOES_NOT_EQUAL_CODE_DERIVED_REPOSITORY_ROOT",))

        artifacts_config = config["artifacts"]
        gate_sources = config["gate_sources"]
        if not isinstance(artifacts_config, Mapping):
            return self._invalid(("ARTIFACTS_NOT_A_MAPPING",))
        if not {"system_interface", "system_urdf"}.issubset(artifacts_config):
            return self._invalid(("REQUIRED_SYSTEM_ARTIFACT_DECLARATIONS_MISSING",))
        if not isinstance(gate_sources, Mapping) or set(gate_sources) != set(REQUIRED_GATES):
            return self._invalid(("GATE_SOURCES_MUST_NAME_EXACTLY_TWELVE_GATES",))

        resolved: dict[str, ResolvedArtifact] = {}
        for artifact_id, record in artifacts_config.items():
            if not isinstance(artifact_id, str) or not artifact_id:
                return self._invalid(("ARTIFACT_ID_INVALID",))
            resolved[artifact_id] = self._resolve_artifact(
                artifact_id, record, project_root
            )

        evidence: dict[str, GateEvidence] = {}
        for gate_name in REQUIRED_GATES:
            source = gate_sources[gate_name]
            if not isinstance(source, Mapping) or set(source) != _GATE_SOURCE_FIELDS:
                errors.append(f"{gate_name}:GATE_SOURCE_SCHEMA_MISMATCH")
                evidence[gate_name] = GateEvidence(
                    GateState.UNKNOWN,
                    None,
                    None,
                    f"{gate_name.upper()}_AUTHORITY_SOURCE_INVALID",
                )
                continue
            artifact_id = source["artifact"]
            pointer = source["field"]
            if not isinstance(artifact_id, str) or artifact_id not in resolved:
                errors.append(f"{gate_name}:GATE_SOURCE_ARTIFACT_UNKNOWN")
                evidence[gate_name] = GateEvidence(
                    GateState.UNKNOWN,
                    str(artifact_id),
                    str(pointer),
                    f"{gate_name.upper()}_AUTHORITY_SOURCE_UNKNOWN",
                )
                continue
            artifact = resolved[artifact_id]
            if not artifact.verified or artifact.document is None:
                evidence[gate_name] = GateEvidence(
                    GateState.UNKNOWN,
                    artifact_id,
                    str(pointer),
                    f"{gate_name.upper()}_{artifact.reason_code}",
                )
                continue
            actual = _json_pointer(artifact.document, pointer)
            if actual is _MISSING:
                evidence[gate_name] = GateEvidence(
                    GateState.UNKNOWN,
                    artifact_id,
                    str(pointer),
                    f"{gate_name.upper()}_AUTHORITY_FIELD_MISSING",
                )
                continue
            state = (
                GateState.PASS
                if _is_exact(actual, source["pass_value"])
                else GateState.FAIL
            )
            evidence[gate_name] = GateEvidence(
                state,
                artifact_id,
                str(pointer),
                f"{gate_name.upper()}_{state.value}",
            )

        # This implementation is intentionally a source-only prebind package.
        # Even a syntactically valid future-looking config cannot make it emit a
        # non-ABORT action.  A production binding requires a new, separately
        # reviewed runtime version with fresh/action-bound receipt semantics.
        evidence["mechanical_system_binding"] = GateEvidence(
            GateState.FAIL,
            "authority_bindings_v2",
            "/scope",
            "MECHANICAL_SYSTEM_BINDING_PREBIND_SCOPE_LOCK",
        )

        errors.extend(
            f"{item.artifact_id}:{item.reason_code}"
            for item in resolved.values()
            if not item.verified
        )
        return AuthorityResolution(
            config_path=self._bindings_path,
            config_sha256=config_sha256,
            config_valid=True,
            scope=_CONFIG_SCOPE,
            snapshot=_authority_snapshot(evidence),
            artifacts=MappingProxyType(resolved),
            errors=tuple(errors),
        )

    def _invalid(self, errors: tuple[str, ...]) -> AuthorityResolution:
        return AuthorityResolution(
            config_path=self._bindings_path,
            config_sha256=None,
            config_valid=False,
            scope="INVALID_OR_UNAVAILABLE_AUTHORITY_CONFIG",
            snapshot=_unknown_snapshot(errors[0]),
            artifacts=MappingProxyType({}),
            errors=errors,
        )

    def _resolve_artifact(
        self,
        artifact_id: str,
        record: Any,
        project_root: Path,
    ) -> ResolvedArtifact:
        if not isinstance(record, Mapping) or set(record) != _ARTIFACT_FIELDS:
            return ResolvedArtifact(
                artifact_id, None, False, "ARTIFACT_RECORD_SCHEMA_MISMATCH"
            )
        try:
            path = _contained_path(project_root, record["path"])
        except ValueError:
            return ResolvedArtifact(artifact_id, None, False, "PATH_CONTAINMENT_FAIL")
        expected_bytes = record["bytes"]
        expected_sha = record["sha256"]
        if expected_bytes is None or expected_sha is None:
            return ResolvedArtifact(
                artifact_id, path, False, "ARTIFACT_NOT_YET_INSTANTIATED"
            )
        if (
            not isinstance(expected_bytes, int)
            or isinstance(expected_bytes, bool)
            or expected_bytes < 0
            or not isinstance(expected_sha, str)
            or _SHA256_RE.fullmatch(expected_sha) is None
        ):
            return ResolvedArtifact(artifact_id, path, False, "PIN_FORMAT_INVALID")
        if not path.is_file():
            return ResolvedArtifact(artifact_id, path, False, "PINNED_FILE_MISSING")
        try:
            payload = path.read_bytes()
        except OSError:
            return ResolvedArtifact(artifact_id, path, False, "PINNED_FILE_UNREADABLE")
        digest = hashlib.sha256(payload).hexdigest().upper()
        if len(payload) != expected_bytes or digest != expected_sha.upper():
            return ResolvedArtifact(
                artifact_id,
                path,
                False,
                "BYTES_OR_SHA256_MISMATCH",
                len(payload),
                digest,
            )

        expected_schema = record["schema"]
        expected_verdict = record["verdict"]
        expected_next = record["next_stage_authorized"]
        expects_document = any(
            value is not None
            for value in (expected_schema, expected_verdict, expected_next)
        )
        document = _load_structured_document(payload) if expects_document else None
        if expects_document and document is None:
            return ResolvedArtifact(
                artifact_id, path, False, "STRUCTURED_DOCUMENT_UNREADABLE", len(payload), digest
            )
        if document is not None:
            if expected_schema is not None and not _is_exact(
                document.get("schema", _MISSING), expected_schema
            ):
                return ResolvedArtifact(
                    artifact_id, path, False, "DOCUMENT_SCHEMA_MISMATCH", len(payload), digest, payload, document
                )
            actual_verdict = document.get(
                "technical_verdict", document.get("verdict", _MISSING)
            )
            if expected_verdict is not None and not _is_exact(
                actual_verdict, expected_verdict
            ):
                return ResolvedArtifact(
                    artifact_id, path, False, "DOCUMENT_VERDICT_MISMATCH", len(payload), digest, payload, document
                )
            if expected_next is not None and not _is_exact(
                document.get("next_stage_authorized", _MISSING), expected_next
            ):
                return ResolvedArtifact(
                    artifact_id, path, False, "DOCUMENT_NEXT_STAGE_MISMATCH", len(payload), digest, payload, document
                )

        # Gate sources can point into a JSON/YAML document even when no metadata
        # assertion was needed by the artifact record itself.
        if document is None:
            document = _load_structured_document(payload)
        return ResolvedArtifact(
            artifact_id,
            path,
            True,
            "HASH_AND_METADATA_VERIFIED",
            len(payload),
            digest,
            payload,
            document,
        )


__all__ = [
    "AuthorityResolution",
    "AuthorityResolver",
    "ResolvedArtifact",
]
