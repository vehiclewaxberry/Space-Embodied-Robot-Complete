#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Documented user override for the V5 6 GiB memory gate.

The user explicitly instructed on 2026-08-10 to proceed without enforcing the
memory threshold ("不要管门限了开始就行").  This module reads the write-once
override receipt and exposes override_allowed().  It never fabricates a PASS:
actual memory samples are still recorded in every receipt, and the override is
always labelled as USER_OVERRIDE.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = RUN_ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
OVERRIDE = RUN_ROOT / "00_authority/V5_MEMORY_GATE_USER_OVERRIDE.json"


def override_payload() -> Optional[Dict[str, Any]]:
    if not OVERRIDE.is_file():
        return None
    payload = json.loads(OVERRIDE.read_text(encoding="utf-8"))
    if payload.get("schema") != "F3R2_V5_MEMORY_GATE_USER_OVERRIDE_V1":
        raise ValueError("V5_MEMORY_GATE_USER_OVERRIDE schema mismatch")
    return payload


def override_allowed() -> bool:
    payload = override_payload()
    if payload is None:
        return False
    scope = payload.get("scope", "")
    return bool(payload.get("override")) and scope in ("ALL_V5_NATIVE_EXECUTION_AND_G0", "ALL")


def summary() -> Dict[str, Any]:
    payload = override_payload()
    return {
        "override_exists": payload is not None,
        "override_allowed": override_allowed(),
        "path": str(OVERRIDE).replace("\\", "/"),
    }
