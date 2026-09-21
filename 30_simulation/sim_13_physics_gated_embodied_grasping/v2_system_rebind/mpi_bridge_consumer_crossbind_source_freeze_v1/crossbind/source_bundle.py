"""One-read, exact path/bytes/SHA source receipt loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .constants import SOURCE_PINS
from .strict_io import deep_freeze, parse_json_bytes, parse_yaml_bytes, sha256_bytes


class SourceBundleError(ValueError):
    """Pinned-source mismatch or authority conflict."""


@dataclass(frozen=True, slots=True)
class SourceReceipt:
    source_id: str
    path: str
    byte_count: int
    sha256: str
    raw_bytes: bytes
    parsed: Mapping[str, Any]

    def public_receipt(self) -> dict[str, Any]:
        return {"id": self.source_id, "path": self.path, "bytes": self.byte_count, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class SourceBundle:
    receipts: Mapping[str, SourceReceipt]
    read_counts: Mapping[str, int]

    def __getitem__(self, key: str) -> SourceReceipt:
        return self.receipts[key]


def verify_raw_against_pin(source_id: str, path: str, raw: bytes, expected_sha256: str) -> str:
    actual = sha256_bytes(raw)
    if actual != expected_sha256:
        raise SourceBundleError(f"SOURCE_SHA_MISMATCH:{source_id}:{path}:{actual}")
    return actual


def _safe_absolute(repo_root: Path, rel: str) -> Path:
    root = repo_root.resolve()
    lexical_target = root / rel
    if lexical_target.is_symlink():
        raise SourceBundleError(f"SOURCE_SYMLINK_REJECTED:{rel}")
    target = lexical_target.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise SourceBundleError(f"SOURCE_PATH_ESCAPE:{rel}") from exc
    if not target.is_file():
        raise SourceBundleError(f"SOURCE_MISSING:{rel}")
    return target


def load_source_bundle(
    repo_root: Path, observer: Callable[[str], None] | None = None
) -> SourceBundle:
    receipts: dict[str, SourceReceipt] = {}
    read_counts: dict[str, int] = {}
    for pin in SOURCE_PINS:
        source_id = pin["id"]
        rel = pin["path"]
        target = _safe_absolute(repo_root, rel)
        if observer is not None:
            observer(rel)
        with target.open("rb") as handle:
            raw = handle.read()
        read_counts[rel] = read_counts.get(rel, 0) + 1
        if read_counts[rel] != 1:
            raise SourceBundleError(f"SOURCE_READ_MORE_THAN_ONCE:{rel}")
        actual_sha = verify_raw_against_pin(source_id, rel, raw, pin["sha256"])
        if pin["format"] == "json":
            parsed = parse_json_bytes(raw)
        elif pin["format"] == "yaml":
            parsed = parse_yaml_bytes(raw)
        elif pin["format"] == "python":
            # Python is pinned as opaque source text.  It is never executed by
            # the source loader; the composition adapter separately imports the
            # exact final verifier only after these bytes match their pin.
            try:
                raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise SourceBundleError(f"PYTHON_SOURCE_NOT_UTF8:{source_id}") from exc
            parsed = {"schema": None, "source_kind": "PINNED_PYTHON_SOURCE"}
        else:
            raise SourceBundleError(f"UNSUPPORTED_SOURCE_FORMAT:{source_id}:{pin['format']}")
        if parsed.get("schema") != pin["schema"]:
            raise SourceBundleError(f"SOURCE_SCHEMA_MISMATCH:{source_id}:{parsed.get('schema')}")
        receipts[source_id] = SourceReceipt(
            source_id=source_id,
            path=rel,
            byte_count=len(raw),
            sha256=actual_sha,
            raw_bytes=raw,
            parsed=deep_freeze(parsed),
        )
    if len(receipts) != len(SOURCE_PINS):
        raise SourceBundleError("SOURCE_RECEIPT_COUNT_MISMATCH")
    return SourceBundle(MappingProxyType(receipts), MappingProxyType(read_counts))
