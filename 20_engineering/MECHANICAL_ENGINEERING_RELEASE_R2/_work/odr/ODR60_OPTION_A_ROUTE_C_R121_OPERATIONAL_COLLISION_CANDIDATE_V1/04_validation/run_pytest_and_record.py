"""Run the package pytest suite in a subprocess and write a stable receipt."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from route_c_r20_validation_lib import (
    PACKAGE,
    PYTEST_PATH,
    TEST_DIR,
    atomic_write,
    require,
    sha256_path,
    stable_json_bytes,
    workspace_root,
)


MINIMUM_TESTS = 24


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def runtime_record(path: Path) -> dict:
    require(path.is_file(), f"Python runtime missing: {path}")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_path(path)}


def run_suite() -> dict:
    test_files = sorted(TEST_DIR.glob("test_*.py"), key=lambda path: path.name)
    require(test_files, "no pytest files found")
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONUTF8": "1",
        }
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        str(TEST_DIR),
    ]
    completed = subprocess.run(
        command,
        cwd=workspace_root(),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    combined = completed.stdout + "\n" + completed.stderr
    match = re.search(r"(?m)^\s*(\d+) passed(?:,|\s)", combined)
    require(completed.returncode == 0, f"pytest failed:\n{combined[-8000:]}")
    require(match is not None, f"pytest PASS count not found:\n{combined[-2000:]}")
    passed = int(match.group(1))
    require(passed >= MINIMUM_TESTS, f"pytest count {passed} < {MINIMUM_TESTS}")
    root = workspace_root()
    return {
        "schema": "ROUTE_C_ROOT_STATIC_R20_PYTEST_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_VALIDATION_NO_WALLCLOCK",
        "scope": "INDEPENDENT_VALIDATOR_AND_LOCAL_CANDIDATE_REGRESSION_TESTS",
        "python_runtime": runtime_record(Path(sys.executable)),
        "pytest_version": pytest.__version__,
        "command": ["<current-python>", "-m", "pytest", "-q", "-p", "no:cacheprovider", TEST_DIR.relative_to(root).as_posix()],
        "fixed_environment": {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONUTF8": "1",
        },
        "test_files": [
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_path(path),
            }
            for path in test_files
        ],
        "tests_required_minimum": MINIMUM_TESTS,
        "tests_collected": passed,
        "tests_passed": passed,
        "tests_failed": 0,
        "return_code": completed.returncode,
        "pytest_pass": True,
        "authority_boundary": {
            "test_pass_is_scientific_system_gate_pass": False,
            "system_binding_credit": False,
            "pair_edge_path_credit": False,
            "release_credit": False,
        },
        "maximum_legal_claim": "R20_LOCAL_CANDIDATE_VALIDATION_TEST_SUITE_PASSES",
        "verdict": "PYTEST_PASS__LOCAL_VALIDATION_EVIDENCE_ONLY__NO_SYSTEM_GATE_OR_RELEASE_CREDIT",
    }


def main() -> None:
    args = parse_args()
    receipt = run_suite()
    encoded = stable_json_bytes(receipt)
    if args.write:
        atomic_write(PYTEST_PATH, encoded)
    else:
        require(PYTEST_PATH.is_file(), f"pytest receipt missing: {PYTEST_PATH}")
        require(PYTEST_PATH.read_bytes() == encoded, "pytest receipt drift")
    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": "write" if args.write else "check",
                "tests": receipt["tests_passed"],
                "release_credit": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
