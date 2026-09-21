"""Prove validator/audit replay does not modify the frozen package."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from mechanical_admission.freeze_support import package_inventory


FORBIDDEN_EXTENSIONS = {".fcstd", ".step", ".stl", ".ply", ".urdf", ".inp", ".odb", ".traj", ".csv", ".npz"}


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(PACKAGE_ROOT / script), *args],
        cwd=PACKAGE_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    before = package_inventory()
    validator = _run("validate_mechanical_evidence_admission_source_freeze.py")
    audit = _run("independent_audit_mechanical_evidence_admission.py", "--check")
    after = package_inventory()
    caches = [path for path in PACKAGE_ROOT.rglob("*") if path.is_file() and (path.suffix.lower() in {".pyc", ".pyo"} or "__pycache__" in path.parts or ".pytest_cache" in path.parts)]
    forbidden = [path for path in PACKAGE_ROOT.rglob("*") if path.is_file() and path.suffix.lower() in FORBIDDEN_EXTENSIONS]
    passed = validator.returncode == 0 and audit.returncode == 0 and before == after and not caches and not forbidden
    print(
        "read_only_replay={} validator_rc={} audit_rc={} inventory_unchanged={} caches={} forbidden_artifacts={}".format(
            "PASS" if passed else "FAIL",
            validator.returncode,
            audit.returncode,
            before == after,
            len(caches),
            len(forbidden),
        )
    )
    if validator.returncode != 0:
        print(validator.stdout.strip())
        print(validator.stderr.strip())
    if audit.returncode != 0:
        print(audit.stdout.strip())
        print(audit.stderr.strip())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
