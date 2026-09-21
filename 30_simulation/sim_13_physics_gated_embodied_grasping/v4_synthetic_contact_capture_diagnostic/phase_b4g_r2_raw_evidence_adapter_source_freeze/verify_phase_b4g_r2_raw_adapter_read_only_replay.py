"""Prove validator, independent audit, and pytest preserve package bytes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode = True

from r2_raw_adapter.freeze_support import (  # noqa: E402
    forbidden_artifacts,
    package_snapshot,
    snapshot_delta,
)
from r2_raw_adapter.strict_json import file_sha256  # noqa: E402
from validate_phase_b4g_r2_raw_adapter_source_freeze import verify_published_chain  # noqa: E402


HERE = Path(__file__).resolve().parent
GATE = HERE / "results/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_GATE_V1.json"
TERMINAL = HERE / "results/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_TERMINAL_V1.json"
COMMANDS = (
    ("validator", (sys.executable, "-B", "validate_phase_b4g_r2_raw_adapter_source_freeze.py")),
    ("independent_audit", (sys.executable, "-B", "independent_audit_phase_b4g_r2_raw_adapter_source_freeze.py")),
    ("pytest", (sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider")),
)


def main() -> int:
    before = package_snapshot(HERE)
    forbidden_before = forbidden_artifacts(HERE)
    chain_before = verify_published_chain()
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command_results: list[dict[str, Any]] = []
    for name, command in COMMANDS:
        completed = subprocess.run(
            command, cwd=HERE, env=environment, text=True,
            capture_output=True, check=False,
        )
        command_results.append({
            "name": name,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout.strip().splitlines()[-1:] or [],
            "stderr_tail": completed.stderr.strip().splitlines()[-1:] or [],
        })
        if completed.returncode != 0:
            break
    after = package_snapshot(HERE)
    forbidden_after = forbidden_artifacts(HERE)
    chain_after = verify_published_chain()
    delta = snapshot_delta(before, after)
    unchanged = all(not rows for rows in delta.values())
    commands_pass = len(command_results) == len(COMMANDS) and all(row["returncode"] == 0 for row in command_results)
    passed = bool(
        commands_pass and unchanged and not forbidden_before and not forbidden_after
        and chain_before.get("passed") is True and chain_after.get("passed") is True
    )
    if not commands_pass:
        status = "FAIL_R2_RAW_ADAPTER_READ_ONLY_COMMAND"
    elif not unchanged:
        status = "FAIL_R2_RAW_ADAPTER_READ_ONLY_REPLAY_MUTATED_PACKAGE"
    elif forbidden_before or forbidden_after:
        status = "FAIL_R2_RAW_ADAPTER_FORBIDDEN_ARTIFACT_PRESENT"
    elif chain_before.get("passed") is not True or chain_after.get("passed") is not True:
        status = "FAIL_R2_RAW_ADAPTER_PUBLISHED_HASH_CHAIN"
    else:
        status = "PASS_R2_RAW_ADAPTER_READ_ONLY_REPLAY_PACKAGE_BYTES_UNCHANGED"
    print(json.dumps({
        "status": status,
        "package_file_count": len(before),
        "commands": command_results,
        "delta": delta,
        "forbidden_before": forbidden_before,
        "forbidden_after": forbidden_after,
        "published_chain_before": chain_before,
        "published_chain_after": chain_after,
        "gate_sha256": file_sha256(GATE) if GATE.is_file() else "MISSING",
        "terminal_sha256": file_sha256(TERMINAL) if TERMINAL.is_file() else "MISSING",
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "next_stage_authorized": False,
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
