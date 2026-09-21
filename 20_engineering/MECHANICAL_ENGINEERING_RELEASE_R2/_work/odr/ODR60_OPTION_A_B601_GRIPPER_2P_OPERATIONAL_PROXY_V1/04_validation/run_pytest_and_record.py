#!/usr/bin/env python3
"""Run the bounded gripper package tests and write a deterministic receipt."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
TEST_FILE = PACKAGE / "06_tests" / "test_gripper_2p_operational_proxy.py"
OUTPUT = PACKAGE / "05_results" / "PYTEST_RECEIPT_V1.json"


def stable_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_receipt() -> bytes:
    if not TEST_FILE.is_file():
        raise RuntimeError(f"test file is missing: {TEST_FILE}")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(TEST_FILE)],
        cwd=PACKAGE.parents[4],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    match = re.search(r"(?m)^([0-9]+) passed(?:, [^\n]+)? in [0-9.]+s\s*$", completed.stdout)
    if completed.returncode != 0 or match is None:
        raise RuntimeError(f"pytest failed or emitted no pass count:\n{completed.stdout}")
    passed = int(match.group(1))
    return stable_json_bytes(
        {
            "schema": "B601_GRIPPER_2P_PYTEST_RECEIPT_V1",
            "as_of_date": "2026-08-28",
            "command": "python -m pytest -q 06_tests/test_gripper_2p_operational_proxy.py",
            "test_file": "06_tests/test_gripper_2p_operational_proxy.py",
            "tests_passed": passed,
            "tests_failed": 0,
            "exit_code": 0,
            "status": "PASS",
            "authority_flags": {
                "system_registry_reissued": False,
                "system_pair_evaluation_authorized": False,
                "path_search_authorized": False,
                "next_stage_authorized": False,
                "release_credit": False,
            },
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build_receipt()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != data:
            raise RuntimeError("pytest receipt mismatch")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temporary = OUTPUT.with_suffix(".json.tmp")
        temporary.write_bytes(data)
        temporary.replace(OUTPUT)
    print(json.dumps({"status": "PASS", "bytes": len(data)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

