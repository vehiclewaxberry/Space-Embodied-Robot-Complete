"""Verify the Phase-0 protected-source seal without modifying any source."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[4]
SEAL = CANDIDATE / "00_AUDIT/baseline_protected_hashes.csv"
OUTPUT = CANDIDATE / "07_VERIFICATION/protected_hash_verification.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def resolve(display_path: str) -> Path:
    path = Path(display_path)
    return path if path.is_absolute() else WORKSPACE / path


def main() -> None:
    rows = list(csv.DictReader(SEAL.open("r", encoding="utf-8-sig", newline="")))
    results = []
    for row in rows:
        path = resolve(row["file_path"])
        exists = path.is_file()
        actual_size = path.stat().st_size if exists else None
        actual_hash = sha256(path) if exists else None
        results.append(
            {
                "file_path": row["file_path"],
                "exists": exists,
                "expected_size_bytes": int(row["size_bytes"]),
                "actual_size_bytes": actual_size,
                "expected_sha256": row["sha256"],
                "actual_sha256": actual_hash,
                "match": (
                    exists
                    and actual_size == int(row["size_bytes"])
                    and actual_hash == row["sha256"]
                ),
            }
        )
    passed = sum(bool(item["match"]) for item in results)
    report = {
        "gate_id": "B5_0_PROTECTED_BASELINE_HASH_CHECK",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "seal_path": SEAL.relative_to(WORKSPACE).as_posix(),
        "checked": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "verdict": (
            "B5_0_PROTECTED_BASELINE_HASH_PASS"
            if passed == len(results)
            else "B5_0_PROTECTED_BASELINE_HASH_FAIL"
        ),
        "mismatches": [item for item in results if not item["match"]],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: report[key] for key in (
        "verdict", "checked", "passed", "failed"
    )}, ensure_ascii=False))
    if report["failed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
