"""Hash the final M4 and isolated Sim14 deliverables without self-reference."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


M4_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = M4_ROOT.parents[1]
SIM14_ROOT = PROJECT_ROOT / "30_simulation" / "sim_14_m4_digital_prototype_grasping"
OUTPUT = M4_ROOT / "12_release" / "M4_OUTPUT_MANIFEST_V1.json"
EXCLUDED_DIRS = {"__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".fcbak"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        if path.resolve() == OUTPUT.resolve():
            continue
        yield path


def main() -> int:
    roots = (
        ("M4", M4_ROOT),
        ("SIM14", SIM14_ROOT),
    )
    records: list[dict[str, object]] = []
    missing_roots: list[str] = []
    for root_id, root in roots:
        if not root.is_dir():
            missing_roots.append(str(root))
            continue
        for path in iter_files(root):
            records.append(
                {
                    "root_id": root_id,
                    "path": path.relative_to(PROJECT_ROOT).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    payload = {
        "schema": "M4_OUTPUT_MANIFEST_V1",
        "generated_local": datetime.now().astimezone().isoformat(),
        "hash_algorithm": "SHA-256",
        "self_excluded": True,
        "cache_and_backup_files_excluded": True,
        "root_count": len(roots),
        "missing_roots": missing_roots,
        "file_count": len(records),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in records),
        "status": "PASS" if not missing_roots and records else "HOLD",
        "files": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "file_count": payload["file_count"],
                "total_size_bytes": payload["total_size_bytes"],
                "missing_roots": payload["missing_roots"],
                "status": payload["status"],
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
