from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    build = subprocess.run(
        [sys.executable, "30_simulation/e15_core_coverage/src/build_core_coverage.py"],
        cwd=ROOT,
        text=True,
    )
    if build.returncode:
        return build.returncode
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "30_simulation/e15_core_coverage/tests/test_core_coverage.py"],
        cwd=ROOT,
        text=True,
    )
    return test.returncode


if __name__ == "__main__":
    raise SystemExit(main())
