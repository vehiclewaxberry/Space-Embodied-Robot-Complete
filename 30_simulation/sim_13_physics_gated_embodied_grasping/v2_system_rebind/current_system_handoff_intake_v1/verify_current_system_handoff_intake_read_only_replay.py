"""Prove validator and independent audit replay leave the package unchanged."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from current_handoff.freeze_support import (
    FROZEN_PACKAGE_FILE_ALLOWLIST,
    forbidden_package_entries,
    package_file_paths,
    package_inventory,
)


def _run(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(PACKAGE_ROOT / script), *arguments],
        cwd=PACKAGE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    before = package_inventory()
    before_files = package_file_paths()
    validator = _run("validate_current_system_handoff_intake_source_freeze.py")
    audit = _run("independent_audit_current_system_handoff_intake.py", "--check")
    after = package_inventory()
    after_files = package_file_paths()
    forbidden = forbidden_package_entries()
    complete_allowlist_exact = before_files == after_files == FROZEN_PACKAGE_FILE_ALLOWLIST
    passed = validator.returncode == 0 and audit.returncode == 0 and before == after and complete_allowlist_exact and not forbidden
    print(
        "read_only_replay={} validator_rc={} audit_rc={} inventory_unchanged={} complete_allowlist_exact={} package_files={} forbidden_or_cache_entries={}".format(
            "PASS" if passed else "FAIL",
            validator.returncode,
            audit.returncode,
            before == after,
            complete_allowlist_exact,
            len(after_files),
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
