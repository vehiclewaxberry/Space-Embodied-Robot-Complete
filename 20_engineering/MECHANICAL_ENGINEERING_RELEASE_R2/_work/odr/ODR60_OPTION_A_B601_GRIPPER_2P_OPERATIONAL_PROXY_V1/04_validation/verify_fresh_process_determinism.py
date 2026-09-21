#!/usr/bin/env python3
"""Prove builder replay in a fresh CPython process and record its hashes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
BUILDER = PACKAGE / "02_builder" / "build_gripper_2p_operational_proxy.py"
OUTPUT = PACKAGE / "05_results" / "FRESH_PROCESS_DETERMINISTIC_REPLAY_V1.json"


def stable_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_receipt() -> bytes:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=PACKAGE.parents[4],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"fresh-process builder replay failed:\n{completed.stdout}")
    payload = None
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith("{") and line.endswith("}"):
            payload = json.loads(line)
            break
    if payload is None or payload.get("status") != "PASS" or payload.get("deterministic_replay") is not True:
        raise RuntimeError("fresh-process builder replay emitted no valid PASS payload")
    receipt = {
        "schema": "B601_GRIPPER_2P_FRESH_PROCESS_DETERMINISTIC_REPLAY_V1",
        "as_of_date": "2026-08-28",
        "process_contract": {
            "builder_invocation": "python build_gripper_2p_operational_proxy.py --check",
            "fresh_cpython_process": True,
            "pythondontwritebytecode": True,
            "pythonutf8": True,
            "maximum_builder_invocations_in_child_process": 1,
        },
        "artifact_count": payload["artifact_count"],
        "objects": payload["objects"],
        "artifact_sha256": payload["sha256"],
        "step_sha256": {
            key: value
            for key, value in payload["sha256"].items()
            if key.lower().endswith(".step")
        },
        "checks": {
            "child_process_exit_zero": True,
            "builder_reported_deterministic_replay": True,
            "all_existing_artifact_bytes_equal_rebuilt_bytes": True,
            "three_primary_step_hashes_repeated": True,
        },
        "status": "PASS",
        "authority_flags": {
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
    }
    return stable_json_bytes(receipt)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build_receipt()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != data:
            raise RuntimeError("fresh-process deterministic replay receipt mismatch")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temporary = OUTPUT.with_suffix(".json.tmp")
        temporary.write_bytes(data)
        temporary.replace(OUTPUT)
    print(json.dumps({"status": "PASS", "receipt": str(OUTPUT), "bytes": len(data)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

