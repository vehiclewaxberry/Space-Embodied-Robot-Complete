#!/usr/bin/env python3
"""Build a fail-closed SHA-256 manifest from the controlled M3 input register."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
M3 = Path(__file__).resolve().parents[1]
REGISTER = M3 / "00_authority" / "M3_INPUT_SOURCE_REGISTER.csv"
OUTPUT = M3 / "00_authority" / "FROZEN_INPUT_MANIFEST_V1.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest().upper()


def resolve(path_text: str) -> Path:
    candidate = Path(path_text)
    return candidate if candidate.is_absolute() else ROOT / candidate


def main() -> int:
    records = []
    with REGISTER.open(newline="", encoding="utf-8-sig") as stream:
        rows = csv.DictReader(stream)
        for row in rows:
            path = resolve(row["path"])
            exists = path.is_file()
            size = path.stat().st_size if exists else None
            records.append(
                {
                    "input_id": row["input_id"],
                    "path": row["path"].replace("\\", "/"),
                    "role": row["role"],
                    "authority_class": row["authority_class"],
                    "immutable_in_m3": row["immutable_in_m3"].lower() == "true",
                    "exists": exists,
                    "size_bytes": size,
                    "sha256": digest(path) if exists and size else None,
                    "status": (
                        "PASS_HASH_BOUND"
                        if exists and size and size > 0
                        else "FAIL_MISSING_OR_ZERO_BYTE"
                    ),
                }
            )
    missing = sum(not record["exists"] for record in records)
    zero_byte = sum(record["exists"] and record["size_bytes"] == 0 for record in records)
    manifest = {
        "schema": "M3_FROZEN_INPUT_MANIFEST_V1",
        "generated_local": datetime.now().astimezone().isoformat(),
        "register": str(REGISTER.relative_to(ROOT)).replace("\\", "/"),
        "input_count": len(records),
        "hash_bound_count": sum(record["status"] == "PASS_HASH_BOUND" for record in records),
        "missing_count": missing,
        "zero_byte_count": zero_byte,
        "status": "PASS" if missing == 0 and zero_byte == 0 else "FAIL",
        "records": records,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("input_count", "hash_bound_count", "missing_count", "zero_byte_count", "status")}, indent=2))
    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
