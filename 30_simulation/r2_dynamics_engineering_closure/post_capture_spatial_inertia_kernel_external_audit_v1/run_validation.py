#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
AUDITOR = ROOT / "audit_external.py"


def run(command: list[str]) -> None:
    env = os.environ.copy(); env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(command, cwd=ROOT.parents[2], env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    run([sys.executable, "-B", str(AUDITOR), "--write"])
    run([sys.executable, "-B", str(AUDITOR), "--check"])
    with tempfile.TemporaryDirectory(prefix="post_capture_external_audit_") as temporary:
        run([sys.executable, "-B", "-m", "pytest", str(ROOT / "tests"), "-q", "-p", "no:cacheprovider", "--basetemp", temporary])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
