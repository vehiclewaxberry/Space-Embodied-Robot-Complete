r"""V5R-RAPID Phase 0 - long-path-safe SHA-256 manifest and backup verifier.

Why a filesystem walk and not `git ls-files --others`: this repository has
core.longpaths unset, so git silently *skips* directories whose paths exceed
MAX_PATH (260 chars) and emits only a warning. Building the pre-execution
hash manifest on top of git enumeration would therefore under-report the very
assets the cold backup exists to protect. os.walk over a `\\?\`-prefixed
absolute path has no such limit.

Usage:
  python V5R_PHASE0_HASH_MANIFEST.py hash   --root <dir> --out <csv>
  python V5R_PHASE0_HASH_MANIFEST.py verify --src-csv <csv> --dst-csv <csv> --out <json>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys

CHUNK = 1 << 20
MAX_PATH = 260


def long_path(p: str) -> str:
    """Return a Win32 extended-length path so MAX_PATH does not apply."""
    p = os.path.abspath(p).replace("/", "\\")
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p.lstrip("\\")
    return "\\\\?\\" + p


def sha256_file(path: str) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with open(long_path(path), "rb") as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                break
            h.update(b)
            size += len(b)
    return h.hexdigest().upper(), size


def cmd_hash(args: argparse.Namespace) -> int:
    root = os.path.abspath(args.root)
    rows: list[tuple[str, int, str, int]] = []
    errors: list[dict[str, str]] = []
    over_max_path = 0

    for dirpath, dirnames, filenames in os.walk(long_path(root)):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            # strip the \\?\ prefix and the root to get a stable relative key
            plain = full[4:] if full.startswith("\\\\?\\") else full
            rel = os.path.relpath(plain, root).replace("\\", "/")
            try:
                digest, size = sha256_file(plain)
            except OSError as exc:
                errors.append({"path": rel, "error": f"{type(exc).__name__}: {exc}"})
                continue
            if len(plain) > MAX_PATH:
                over_max_path += 1
            rows.append((rel, size, digest, len(plain)))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(long_path(args.out), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["relpath", "size_bytes", "sha256", "abs_path_len"])
        w.writerows(rows)

    summary = {
        "root": root.replace("\\", "/"),
        "file_count": len(rows),
        "total_bytes": sum(r[1] for r in rows),
        "files_exceeding_MAX_PATH_260": over_max_path,
        "max_abs_path_len": max((r[3] for r in rows), default=0),
        "read_error_count": len(errors),
        "read_errors": errors[:50],
        "manifest_csv": os.path.abspath(args.out).replace("\\", "/"),
    }
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    # fail closed: unreadable files mean the manifest is not a complete record
    return 1 if errors else 0


def load_csv(path: str, exclude_prefix: str | None = None) -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    with open(long_path(path), "r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rel = row["relpath"]
            if exclude_prefix and rel.startswith(exclude_prefix):
                continue
            out[rel] = (int(row["size_bytes"]), row["sha256"])
    return out


def cmd_verify(args: argparse.Namespace) -> int:
    # The cold backup protects *pre-existing inputs*. This round's own output
    # directory is excluded from both sides: it did not exist at snapshot time
    # and keeps growing as Phase 0 artifacts land, so including it would make
    # a 1:1 file count an unreachable moving target rather than a real check.
    src = load_csv(args.src_csv, args.exclude_prefix)
    dst = load_csv(args.dst_csv, args.exclude_prefix)

    missing = sorted(set(src) - set(dst))
    extra = sorted(set(dst) - set(src))
    mismatch = sorted(k for k in (set(src) & set(dst)) if src[k][1] != dst[k][1])

    result = {
        "schema": "V5R_PHASE0_BACKUP_VERIFY_V1",
        "src_csv": os.path.abspath(args.src_csv).replace("\\", "/"),
        "dst_csv": os.path.abspath(args.dst_csv).replace("\\", "/"),
        "excluded_relpath_prefix": args.exclude_prefix,
        "scope": "pre-existing inputs only; this round's own output directory excluded from both sides",
        "src_file_count": len(src),
        "dst_file_count": len(dst),
        "src_total_bytes": sum(v[0] for v in src.values()),
        "dst_total_bytes": sum(v[0] for v in dst.values()),
        "missing_in_backup_count": len(missing),
        "extra_in_backup_count": len(extra),
        "sha256_mismatch_count": len(mismatch),
        "missing_in_backup": missing[:100],
        "extra_in_backup": extra[:100],
        "sha256_mismatch": mismatch[:100],
        "every_source_file_present_and_bit_identical": not missing and not mismatch,
    }
    result["verdict"] = (
        "V5R_PHASE0_COLD_BACKUP_VERIFIED_BIT_IDENTICAL"
        if result["every_source_file_present_and_bit_identical"]
        else "V5R_PHASE0_COLD_BACKUP_INCOMPLETE_FAIL_CLOSED"
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(long_path(args.out), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("missing_in_backup", "extra_in_backup", "sha256_mismatch")},
                     indent=1, ensure_ascii=False))
    return 0 if result["every_source_file_present_and_bit_identical"] else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("hash")
    h.add_argument("--root", required=True)
    h.add_argument("--out", required=True)
    h.set_defaults(func=cmd_hash)

    v = sub.add_parser("verify")
    v.add_argument("--src-csv", required=True)
    v.add_argument("--dst-csv", required=True)
    v.add_argument("--out", required=True)
    v.add_argument("--exclude-prefix", default=None,
                   help="relpath prefix to drop from both manifests (this round's output dir)")
    v.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
