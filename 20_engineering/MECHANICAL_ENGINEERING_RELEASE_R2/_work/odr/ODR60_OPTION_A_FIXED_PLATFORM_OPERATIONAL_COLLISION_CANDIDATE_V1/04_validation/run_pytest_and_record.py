#!/usr/bin/env python3
"""Run package pytest in a fresh process and write a deterministic receipt."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Iterable

from fixed_platform_validation_lib import (
    PACKAGE,
    RESULTS_DIR,
    ValidationFailure,
    atomic_write,
    file_record,
    require,
    sha256_bytes,
    stable_json_bytes,
)


TEST_FILE = PACKAGE / "06_tests" / "test_fixed_platform_candidate.py"
OUTPUT = RESULTS_DIR / "PYTEST_RECEIPT_V1.json"


def build_receipt() -> dict[str, object]:
    require(TEST_FILE.is_file(), f"pytest source missing: {TEST_FILE}")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(TEST_FILE)],
        cwd=PACKAGE,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    require(completed.returncode == 0, f"pytest failed with {completed.returncode}:\n{completed.stdout}")
    matches = re.findall(r"(?P<passed>\d+) passed", completed.stdout)
    require(matches, f"pytest output lacks passed count:\n{completed.stdout}")
    passed = int(matches[-1])
    require(passed >= 24, f"pytest coverage below 24 tests: {passed}")
    return {
        "schema": "FIXED_PLATFORM_PYTEST_RECEIPT_V1",
        "as_of_date": "2026-08-28",
        "invocation": "python -m pytest -q -p no:cacheprovider 06_tests/test_fixed_platform_candidate.py",
        "test_source": file_record(TEST_FILE),
        "python": sys.version.split()[0],
        "tests_passed": passed,
        "tests_failed": 0,
        "status": "PASS",
        "stdout_summary": f"{passed} passed",
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
        require(OUTPUT.is_file(), "pytest receipt missing")
        require(OUTPUT.read_bytes() == payload, "pytest receipt drift")
        mode_name = "check"
    print(json.dumps({"status": "PASS", "mode": mode_name, "output": str(OUTPUT), "bytes": len(payload), "sha256": sha256_bytes(payload)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationFailure as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
