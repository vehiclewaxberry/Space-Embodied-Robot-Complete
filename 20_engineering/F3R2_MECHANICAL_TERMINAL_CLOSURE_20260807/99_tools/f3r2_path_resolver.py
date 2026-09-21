#!/usr/bin/env python3
"""Fail-closed resolver for migrated F3R2 evidence and CAD assets.

The resolver never edits a manifest and never accepts a same-name file as
proof.  A relocated candidate is returned only when either:

* its SHA-256 matches the manifest digest; or
* an unambiguous repository-relative suffix (at least two path elements)
  resolves to exactly one existing file.

When a digest is supplied, all returned files are digest verified.  Ambiguous,
missing, or hash-mismatched requests raise ``ResolutionError``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


class ResolutionError(RuntimeError):
    """Fail-closed asset resolution error."""


SCRIPT = Path(__file__).resolve()
ACTIVE_F3R2_ROOT = SCRIPT.parents[1]
PROJECT_ROOT = ACTIVE_F3R2_ROOT.parents[1]

DEFAULT_ROOTS = (
    ACTIVE_F3R2_ROOT,
    PROJECT_ROOT,
    Path(
        "F:/_SEI_PROJECT_CONSOLIDATION_20260807/12_WAVE4/"
        "WORKTREE_RECONCILIATION/20_engineering"
    ),
    Path(
        "F:/_SEI_PROJECT_CONSOLIDATION_20260807/12_WAVE4/"
        "WORKTREE_SAFETY_SNAPSHOT"
    ),
    PROJECT_ROOT / "20_engineering" / "cad",
    PROJECT_ROOT / "80_third_party",
    Path("F:/Robotic arm"),
)

SUFFIX_MARKERS = (
    ACTIVE_F3R2_ROOT.name.lower(),
    "20_engineering",
    "80_third_party",
    "03_native_cad",
    "05_clearance",
    "08_camera_harness",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _normalise_digest(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().replace("sha256:", "").replace("SHA256:", "")
    value = value.upper()
    if len(value) != 64 or any(c not in "0123456789ABCDEF" for c in value):
        raise ResolutionError("expected SHA-256 must contain exactly 64 hex digits")
    return value


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.path.normcase(os.path.abspath(str(path)))
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result


def _relative_suffixes(stored: Path) -> list[Path]:
    parts = tuple(p for p in stored.parts if p not in (stored.anchor, "\\", "/"))
    lowered = tuple(p.lower() for p in parts)
    candidates: list[Path] = []
    for marker in SUFFIX_MARKERS:
        for index, part in enumerate(lowered):
            if part == marker and len(parts) - index >= 2:
                candidates.append(Path(*parts[index:]))
                if marker == ACTIVE_F3R2_ROOT.name.lower() and len(parts) - index >= 3:
                    candidates.append(Path(*parts[index + 1 :]))
    # Longest suffixes carry the most semantic path information.
    candidates.sort(key=lambda p: (-len(p.parts), str(p).lower()))
    return _dedupe_paths(candidates)


@dataclass(frozen=True)
class Resolution:
    stored_path: str
    resolved_path: str
    sha256: str
    resolution_method: str
    expected_sha256: str | None
    searched_roots: tuple[str, ...]


def resolve_asset(
    stored_path: str | os.PathLike[str],
    expected_sha256: str | None = None,
    roots: Sequence[str | os.PathLike[str]] | None = None,
) -> Resolution:
    """Resolve a migrated asset and fail closed on ambiguity or weak proof."""

    stored = Path(stored_path).expanduser()
    expected = _normalise_digest(expected_sha256)
    search_roots = _dedupe_paths(
        Path(root).expanduser() for root in (roots or DEFAULT_ROOTS)
    )

    if stored.is_file():
        actual = sha256(stored)
        if expected and actual != expected:
            raise ResolutionError(
                f"stored path exists but SHA-256 mismatches: {stored}"
            )
        return Resolution(
            str(stored_path), str(stored.resolve()), actual,
            "STORED_PATH" if not expected else "STORED_PATH_HASH_VERIFIED",
            expected, tuple(str(root) for root in search_roots),
        )

    suffixes = _relative_suffixes(stored)
    exact: list[Path] = []
    for root in search_roots:
        if not root.is_dir():
            continue
        for suffix in suffixes:
            candidate = root / suffix
            if candidate.is_file():
                exact.append(candidate.resolve())
            # A root may already denote the marker named by the first element.
            if suffix.parts and root.name.lower() == suffix.parts[0].lower():
                candidate = root.joinpath(*suffix.parts[1:])
                if candidate.is_file():
                    exact.append(candidate.resolve())
    exact = _dedupe_paths(exact)

    if expected:
        verified = [candidate for candidate in exact if sha256(candidate) == expected]
        if not verified:
            # Hash permits a basename search: identity is proved by content,
            # not by the name.  This is deliberately skipped without a hash.
            basename = stored.name
            for root in search_roots:
                if not root.is_dir():
                    continue
                try:
                    for candidate in root.rglob(basename):
                        if candidate.is_file() and sha256(candidate) == expected:
                            verified.append(candidate.resolve())
                except (OSError, PermissionError):
                    continue
        verified = _dedupe_paths(verified)
        if not verified:
            raise ResolutionError("ASSET_NOT_FOUND_AFTER_EXHAUSTIVE_SEARCH")
        # Identical duplicate copies are acceptable; choose the first root in
        # declared precedence and record content identity via the digest.
        chosen = verified[0]
        return Resolution(
            str(stored_path), str(chosen), expected, "SHA256_VERIFIED_REANCHOR",
            expected, tuple(str(root) for root in search_roots),
        )

    if not suffixes:
        raise ResolutionError(
            "no repository-relative suffix and no SHA-256; same-name lookup forbidden"
        )
    if len(exact) != 1:
        reason = "ambiguous" if exact else "not found"
        raise ResolutionError(f"{reason} suffix resolution without SHA-256")
    chosen = exact[0]
    return Resolution(
        str(stored_path), str(chosen), sha256(chosen),
        "UNAMBIGUOUS_REPOSITORY_SUFFIX", None,
        tuple(str(root) for root in search_roots),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stored-path", required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--root", action="append", dest="roots")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        resolution = resolve_asset(
            args.stored_path, args.expected_sha256, args.roots
        )
    except ResolutionError as exc:
        payload = {"status": "UNRESOLVED", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.as_json else exc)
        return 2
    payload = {"status": "RESOLVED", **asdict(resolution)}
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.as_json
          else resolution.resolved_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
