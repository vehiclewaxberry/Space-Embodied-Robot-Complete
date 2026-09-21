#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Register a clean replacement SolidWorks Session B for the claimed V5 run.

The original Loop-1 Session B process (PID 42276) is no longer available.  A
new G0 smoke + Session-B cold-reopen receipt is the only acceptable witness
for a replacement session.  This program:

1. validates the supplied G0 ready receipt (schema, verdict, PID, revision);
2. verifies the process is alive through psutil (read-only);
3. verifies the five V5 execution scripts already use the session resolver;
4. writes 00_authority/V5_SESSION_REQUALIFICATION.json exactly once.

It never starts, stops, kills or creates SolidWorks, and it never modifies the
historical Loop-1 or G0 receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence


RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = RUN_ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
REQUALIFICATION = RUN_ROOT / "00_authority/V5_SESSION_REQUALIFICATION.json"
TOOLS = RUN_ROOT / "99_tools"

PATCHED_SCRIPTS: Sequence[str] = (
    "F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py",
    "F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY_R3.py",
    "F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY.py",
    "F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY.py",
    "F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def file_fact(path: Path) -> Dict[str, Any]:
    return {"path": posix(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def validate_g0_receipt(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    if payload.get("schema") != "F3R2_V5_G0_SMOKE_SESSION_B_V1":
        errors.append("G0_SCHEMA_MISMATCH")
    if payload.get("verdict") != "G0_SOLIDWORKS_NATIVE_EXECUTION_READY":
        errors.append("G0_VERDICT_MISMATCH")
    # Field drift between verifier revisions: older receipts carry
    # solidworks.{pid,revision}+temporary_asset_deleted; newer ones carry
    # session_b_process.{pid,revision}+temporary_asset.deleted. Same facts.
    session = payload.get("solidworks") or payload.get("session_b_process") or {}
    pid = int(session.get("pid", -1))
    revision = str(session.get("revision", ""))
    deleted = payload.get("temporary_asset_deleted")
    if deleted is None:
        deleted = (payload.get("temporary_asset") or {}).get("deleted")
    if pid <= 0:
        errors.append("G0_PID_INVALID")
    if not revision.startswith("32.5."):
        errors.append("G0_REVISION_MISMATCH")
    if deleted is not True:
        errors.append("G0_TEMP_ASSET_NOT_DELETED")
    if errors:
        raise ValueError("invalid G0 ready receipt: " + ",".join(errors))
    return {"payload": payload, "pid": pid, "revision": revision}


def verify_patched_scripts() -> None:
    missing = [name for name in PATCHED_SCRIPTS if not (TOOLS / name).is_file()]
    if missing:
        raise FileNotFoundError("missing patched scripts: " + ",".join(missing))
    for name in PATCHED_SCRIPTS:
        text = (TOOLS / name).read_text(encoding="utf-8")
        if "F3R2_V5_SESSION_BINDING" not in text or "sbin.resolve_pid" not in text:
            raise ValueError(f"script not patched with session resolver: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register replacement V5 Session B from a new G0 ready receipt")
    parser.add_argument("--g0-receipt", required=True, type=Path, help="new _MFINAL_G0_SMOKE_*/G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json")
    args = parser.parse_args()
    if REQUALIFICATION.exists():
        raise SystemExit("REQUALIFICATION_ALREADY_EXISTS")
    if not args.g0_receipt.is_file():
        raise SystemExit("G0_RECEIPT_NOT_FOUND")
    verify_patched_scripts()
    validated = validate_g0_receipt(args.g0_receipt)
    try:
        import psutil
        process = psutil.Process(validated["pid"])
        if not process.is_running():
            raise SystemExit("SESSION_B_PROCESS_NOT_RUNNING")
        executable = Path(process.exe()).resolve()
    except Exception as exc:
        raise SystemExit(f"SESSION_B_PROCESS_VERIFY_FAIL: {exc}") from exc
    payload = {
        "schema": "F3R2_V5_SESSION_REQUALIFICATION_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": RUN_ROOT.name,
        "g0_ready_receipt": file_fact(args.g0_receipt),
        "session_b_pid": validated["pid"],
        "session_b_revision": validated["revision"],
        "session_b_executable": posix(executable),
        "patched_scripts": [file_fact(TOOLS / name) for name in PATCHED_SCRIPTS],
        "historical_session_b_pid": 42276,
        "non_claims": [
            "ORIGINAL_G0_OR_LOOP1_RECEIPTS_UNCHANGED",
            "NOT_AN_AUTOMATED_SOLIDWORKS_START",
            "NOT_FINAL_GATE",
        ],
    }
    REQUALIFICATION.parent.mkdir(parents=True, exist_ok=True)
    with REQUALIFICATION.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"verdict": "V5_SESSION_REQUALIFICATION_REGISTERED", "receipt": file_fact(REQUALIFICATION)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
