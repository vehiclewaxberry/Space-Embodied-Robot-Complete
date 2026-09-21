"""Prove validation, audit, tests and mutations leave the frozen package unchanged."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

from independent_audit_phase_b4g_r2_full_integrity_source_freeze import audit
from r2_full_integrity.freeze_support import package_snapshot, seal_valid, snapshot_delta, strict_load
from r2_full_integrity.negative_controls import run_negative_controls
from validate_phase_b4g_r2_full_integrity_source_freeze import validate_source_freeze


HERE = Path(__file__).resolve().parent
GATE = HERE / "results/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_GATE_V1.json"
TERMINAL = HERE / "results/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_TERMINAL_V1.json"


def replay() -> dict[str, object]:
    before = package_snapshot(HERE)
    validation = validate_source_freeze(write_output=False)
    independent = audit(write_output=False)
    negative = run_negative_controls(HERE)
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest"], cwd=HERE, env=environment,
        capture_output=True, text=True, timeout=180, check=False,
    )
    summary = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(r"(\d+) passed", summary)
    gate = strict_load(GATE)
    terminal = strict_load(TERMINAL)
    after = package_snapshot(HERE)
    delta = snapshot_delta(before, after)
    passed = bool(
        validation["source_freeze_pass_eligible"] is True
        and independent["independent_source_freeze_pass_eligible"] is True
        and negative["passed"] is True
        and completed.returncode == 0 and match is not None and int(match.group(1)) == 18
        and seal_valid(gate) and seal_valid(terminal)
        and delta == {"added": [], "removed": [], "changed": []}
    )
    return {
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_READ_ONLY_REPLAY_V1",
        "passed": passed,
        "validation_pass": validation["source_freeze_pass_eligible"],
        "independent_audit_pass": independent["independent_source_freeze_pass_eligible"],
        "negative_controls_pass": negative["passed"],
        "pytest_passed_count": int(match.group(1)) if match else 0,
        "package_delta": delta,
        "trajectory_count": 0,
        "next_stage_authorized": False,
    }


def main() -> int:
    result = replay()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
