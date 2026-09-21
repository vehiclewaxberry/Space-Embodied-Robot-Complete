#!/usr/bin/env python3
"""Run one builder ``--check`` replay in a fresh CPython process."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Iterable

from fixed_platform_validation_lib import (
    CANDIDATES,
    PACKAGE,
    RESULTS_DIR,
    ValidationFailure,
    atomic_write,
    file_record,
    require,
    sha256_bytes,
    stable_json_bytes,
)


BUILDER = PACKAGE / "02_builder" / "build_fixed_platform_operational_collision_candidate.py"
OUTPUT = RESULTS_DIR / "FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json"


def _parse_payload(stdout: str) -> dict[str, Any]:
    rows = [line.strip() for line in stdout.splitlines() if line.strip()]
    require(rows, "fresh-process builder emitted no output")
    try:
        payload = json.loads(rows[-1])
    except json.JSONDecodeError as exc:
        raise ValidationFailure(f"fresh-process final line is not JSON: {rows[-1]!r}") from exc
    require(isinstance(payload, dict), "fresh-process payload must be an object")
    return payload


def build_receipt() -> dict[str, Any]:
    require(BUILDER.is_file(), f"builder missing: {BUILDER}")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=PACKAGE,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    require(completed.returncode == 0, f"fresh-process builder failed with {completed.returncode}:\n{completed.stdout}")
    payload = _parse_payload(completed.stdout)
    require(payload.get("status") == "PASS", "fresh-process builder status is not PASS")
    require(payload.get("mode") == "check", "fresh-process builder mode is not check")
    require(payload.get("object_count") == 3, "fresh-process builder object_count is not 3")
    require(isinstance(payload.get("source_pin_count"), int) and payload["source_pin_count"] >= 8, "fresh-process source_pin_count invalid")
    require(isinstance(payload.get("artifact_count"), int) and payload["artifact_count"] >= 12, "fresh-process artifact_count invalid")
    require(payload.get("system_operational_authority_rows") == 1, "fresh-process system authority row drift")
    require(payload.get("system_pair_queries") == 0, "fresh-process pair query drift")
    require(payload.get("release_credit") is False, "fresh-process replay granted release credit")
    step_records = {
        name: file_record(PACKAGE / "01_cad" / spec["step"])
        for name, spec in CANDIDATES.items()
    }
    return {
        "schema": "FIXED_PLATFORM_FRESH_PROCESS_DETERMINISTIC_REPLAY_V1",
        "as_of_date": "2026-08-28",
        "process_contract": {
            "invocation": "python 02_builder/build_fixed_platform_operational_collision_candidate.py --check",
            "fresh_cpython_process": True,
            "pythondontwritebytecode": True,
            "pythonutf8": True,
            "child_builder_invocation_count": 1,
        },
        "builder": file_record(BUILDER),
        "builder_payload": payload,
        "primary_step_records_after_replay": step_records,
        "checks": {
            "child_process_exit_zero": True,
            "builder_reported_pass_check": True,
            "three_objects_replayed": True,
            "existing_artifact_bytes_equal_rebuilt_bytes": True,
            "system_authority_rows_preserved_at_one": True,
            "system_pair_queries_preserved_at_zero": True,
            "release_credit_false": True,
        },
        "status": "PASS",
        "authority_flags": {
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "parent_gate_credit": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    payload = stable_json_bytes(build_receipt())
    if args.write:
        atomic_write(OUTPUT, payload)
        mode_name = "write"
    else:
        require(OUTPUT.is_file(), "fresh-process replay receipt missing")
        require(OUTPUT.read_bytes() == payload, "fresh-process replay receipt drift")
        mode_name = "check"
    print(json.dumps({"status": "PASS", "mode": mode_name, "output": str(OUTPUT), "bytes": len(payload), "sha256": sha256_bytes(payload)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationFailure as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
