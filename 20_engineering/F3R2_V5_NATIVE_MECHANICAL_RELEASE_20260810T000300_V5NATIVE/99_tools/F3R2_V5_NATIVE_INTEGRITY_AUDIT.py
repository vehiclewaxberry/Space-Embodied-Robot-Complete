#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only integrity audit for every native V5 part and subassembly.

The audit compares the current bytes of each SLDPRT/SLDASM under the claimed
V5 root against the write-once Loop1, Loop1A and Loop1B receipts.  Files not
yet registered are reported as UNREGISTERED, never as PASS.  Protected assets
are re-hashed and reported.  No file is opened in SolidWorks and nothing is
modified.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = RUN_ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
VALIDATION = RUN_ROOT / "13_validation"

LOOP1_RECEIPT = VALIDATION / "V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
LOOP1A_RECEIPT = VALIDATION / "V5_LOOP1A_SUBASSEMBLY_RECEIPT.json"
PROTECTED_PRE = RUN_ROOT / "00_authority/V5_PROTECTED_BASELINE_PRE.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_registered() -> Dict[str, Dict[str, Any]]:
    registered: Dict[str, Dict[str, Any]] = {}
    loop1 = load_json(LOOP1_RECEIPT)
    for item in loop1.get("native_parts", []):
        target = Path(item["target"]["path"])
        registered[posix(target).lower()] = {
            "path": target,
            "sha256": item["target"]["sha256"],
            "receipt": "V5_LOOP1_NEUTRAL_IMPORT_RECEIPT",
        }
    loop1a = load_json(LOOP1A_RECEIPT)
    for item in loop1a.get("subassemblies", []):
        target = Path(item["target"]["path"])
        registered[posix(target).lower()] = {
            "path": target,
            "sha256": item["target"]["sha256"],
            "receipt": "V5_LOOP1A_SUBASSEMBLY_RECEIPT",
        }
    diamond = loop1a.get("diamond_locator")
    if diamond:
        target = Path(diamond["path"])
        registered[posix(target).lower()] = {
            "path": target,
            "sha256": diamond["save"]["sha256"],
            "receipt": "V5_LOOP1A_SUBASSEMBLY_RECEIPT_DIAMOND_LOCATOR",
        }
    for checkpoint in sorted(VALIDATION.glob("V5_LOOP1B_ARTIFACT_*.json")):
        payload = load_json(checkpoint)
        target = payload.get("target")
        if not target:
            continue
        path = Path(target["path"])
        registered[posix(path).lower()] = {
            "path": path,
            "sha256": target["sha256"],
            "receipt": checkpoint.name,
        }
    return registered


def audit_native(registered: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen = set()
    for pattern in ("01_native_parts/**/*.SLDPRT", "02_native_subassemblies/*.SLDASM"):
        for path in sorted(RUN_ROOT.glob(pattern)):
            key = posix(path).lower()
            if key in seen:
                continue
            seen.add(key)
            actual = sha256(path)
            known = registered.get(key)
            if known is None:
                status = "UNREGISTERED"
            elif actual == known["sha256"]:
                status = "PASS"
            else:
                status = "MISMATCH"
            rows.append(
                {
                    "path": posix(path),
                    "bytes": path.stat().st_size,
                    "sha256": actual,
                    "registered_sha256": known["sha256"] if known else "",
                    "receipt": known["receipt"] if known else "",
                    "status": status,
                }
            )
    return rows


def audit_protected() -> List[Dict[str, Any]]:
    payload = load_json(PROTECTED_PRE)
    rows = []
    for asset in payload.get("assets", []):
        path = Path(asset["path"])
        actual = sha256(path) if path.is_file() else ""
        rows.append(
            {
                "name": asset["name"],
                "path": posix(path),
                "exists": path.is_file(),
                "expected_sha256": asset["expected_sha256"],
                "actual_sha256": actual,
                "status": "PASS" if path.is_file() and actual == asset["expected_sha256"] else "MISMATCH",
            }
        )
    return rows


def main() -> None:
    registered = collect_registered()
    native = audit_native(registered)
    protected = audit_protected()
    report = {
        "schema": "F3R2_V5_NATIVE_INTEGRITY_AUDIT_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_root": posix(RUN_ROOT),
        "native_files": native,
        "native_count": len(native),
        "native_pass_count": sum(1 for row in native if row["status"] == "PASS"),
        "native_unregistered_count": sum(1 for row in native if row["status"] == "UNREGISTERED"),
        "native_mismatch_count": sum(1 for row in native if row["status"] == "MISMATCH"),
        "protected": protected,
        "protected_pass_count": sum(1 for row in protected if row["status"] == "PASS"),
        "verdict": "PASS" if all(row["status"] == "PASS" for row in native) and all(row["status"] == "PASS" for row in protected) else "AUDIT_HOLD",
        "non_claims": ["NOT_NATIVE_REBUILD", "NOT_COLD_REOPEN", "NOT_FINAL_GATE"],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = VALIDATION / f"V5_NATIVE_INTEGRITY_AUDIT_{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": report["verdict"], "native_count": len(native), "native_pass": report["native_pass_count"], "native_unregistered": report["native_unregistered_count"], "protected_pass": report["protected_pass_count"], "receipt": posix(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
