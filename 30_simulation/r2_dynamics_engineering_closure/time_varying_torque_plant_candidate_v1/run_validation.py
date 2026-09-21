#!/usr/bin/env python3
"""Rebuild candidate artifacts, verify deterministic replay, and run pytest."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


PACKAGE_ROOT = Path(__file__).resolve().parent
EVALUATOR = PACKAGE_ROOT / "evaluate_time_varying_torque_plant.py"
INDEPENDENT_VALIDATOR = PACKAGE_ROOT / "independent_validate_time_varying_torque_plant.py"


def run(command: list[str]) -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=PACKAGE_ROOT.parents[2],
        check=False,
        env=environment,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-builder-replay",
        action="store_true",
        help="skip the same-implementation evaluator replay (not independent validation)",
    )
    parser.add_argument(
        "--skip-standalone-recheck",
        action="store_true",
        help="write one standalone receipt but skip its second independent recomputation",
    )
    args = parser.parse_args()
    run([sys.executable, "-B", str(EVALUATOR), "--write"])
    if not args.skip_builder_replay:
        run([sys.executable, "-B", str(EVALUATOR), "--check"])
    run([sys.executable, "-B", str(INDEPENDENT_VALIDATOR), "--write"])
    if not args.skip_standalone_recheck:
        run([sys.executable, "-B", str(INDEPENDENT_VALIDATOR), "--check"])
    with tempfile.TemporaryDirectory(prefix="r2_torque_plant_pytest_") as temporary:
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
