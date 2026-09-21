#!/usr/bin/env python3
"""Fail-closed guard for dormant Solar-R2 V3 executable sources."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AUTHORITY_RECORD = HERE / "SOLAR_R2_V3_EXECUTION_AUTHORIZATION.json"


def require_execution_authority(operation: str) -> dict:
    if not AUTHORITY_RECORD.is_file():
        raise RuntimeError(
            "SOLAR_R2_V3_GENERATION_NOT_AUTHORIZED_SOURCE_ONLY: missing "
            + str(AUTHORITY_RECORD)
        )
    record = json.loads(AUTHORITY_RECORD.read_text(encoding="utf-8-sig"))
    if record.get("schema") != "SOLAR_R2_V3_EXECUTION_AUTHORIZATION_V1":
        raise RuntimeError("SOLAR_R2_V3_GENERATION_NOT_AUTHORIZED: schema mismatch")
    flags = record.get("authority_flags", {})
    required = {
        "run_specific_execution_authorized": True,
        "frozen_predecessors_immutable": True,
        "versioned_isolated_outputs_required": True,
    }
    if any(flags.get(key) is not value for key, value in required.items()):
        raise RuntimeError("SOLAR_R2_V3_GENERATION_NOT_AUTHORIZED: authority flags incomplete")
    if operation not in record.get("authorized_operations", []):
        raise RuntimeError("SOLAR_R2_V3_GENERATION_NOT_AUTHORIZED: operation not listed")
    memory = record.get("memory_admission", {})
    if memory.get("gate_passed") is not True and memory.get("run_specific_owner_override") is not True:
        raise RuntimeError("SOLAR_R2_V3_GENERATION_NOT_AUTHORIZED: memory gate/override absent")
    return record
