#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Session-B rebinding resolver for the claimed V5 run.

The original Loop-1 Session B process is fixed by write-once receipts.  If a
clean replacement session is re-qualified by a new G0 smoke run, the operator
must write 00_authority/V5_SESSION_REQUALIFICATION.json (never overwrite).
This module lets the Loop1B/1C/1D/1E execution scripts use that replacement
session PID without modifying the immutable historical receipts.

The module is read-only with respect to SolidWorks.  It does not create or
terminate processes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = RUN_ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
REQUALIFICATION = RUN_ROOT / "00_authority/V5_SESSION_REQUALIFICATION.json"


def requalification() -> Optional[Dict[str, Any]]:
    if not REQUALIFICATION.is_file():
        return None
    payload = json.loads(REQUALIFICATION.read_text(encoding="utf-8"))
    if payload.get("schema") != "F3R2_V5_SESSION_REQUALIFICATION_V1":
        raise ValueError("V5_SESSION_REQUALIFICATION schema mismatch")
    if int(payload.get("session_b_pid", -1)) <= 0:
        raise ValueError("V5_SESSION_REQUALIFICATION missing valid session_b_pid")
    return payload


def resolve_pid(default_pid: Any) -> int:
    """Return the replacement session PID when a re-qualification exists."""
    payload = requalification()
    if payload is not None:
        return int(payload["session_b_pid"])
    return int(default_pid)


def binding_summary(default_pid: Any) -> Dict[str, Any]:
    return {
        "resolver": posix(REQUALIFICATION),
        "requalification_exists": REQUALIFICATION.is_file(),
        "resolved_pid": resolve_pid(default_pid),
        "default_pid": int(default_pid),
    }


def posix(path: Path) -> str:
    return str(path).replace("\\", "/")
