#!/usr/bin/env python3
"""Rebuild, independently validate, and test the candidate package."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


PACKAGE_ROOT = Path(__file__).resolve().parent
EVALUATOR = PACKAGE_ROOT / "evaluate_post_capture_spatial_inertia.py"
VALIDATOR = PACKAGE_ROOT / "independent_validate_post_capture_spatial_inertia.py"


def run(command: list[str]) -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=PACKAGE_ROOT.parents[2],
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    run([sys.executable, "-B", str(EVALUATOR), "--write"])
    run([sys.executable, "-B", str(EVALUATOR), "--check"])
    run([sys.executable, "-B", str(VALIDATOR), "--write"])
    run([sys.executable, "-B", str(VALIDATOR), "--check"])
    with tempfile.TemporaryDirectory(prefix="post_capture_inertia_pytest_") as temporary:
        run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                str(PACKAGE_ROOT / "tests"),
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                temporary,
            ]
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

