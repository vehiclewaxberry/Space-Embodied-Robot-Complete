"""Run the fixed C9 pytest target and write a deterministic summary receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


class TestFailure(RuntimeError):
    pass


PACKAGE = Path(__file__).resolve().parents[1]
TEST = PACKAGE / "06_tests/test_c9_capsule_candidate.py"
RECEIPT = PACKAGE / "05_results/PYTEST_RECEIPT_V1.json"


def root() -> Path:
    for item in Path(__file__).resolve().parents:
        if (item / "PROJECT_MAP.md").is_file():
            return item
    raise TestFailure("root not found")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def stable(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def atomic(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise TestFailure(message)


def make_receipt() -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUTF8": "1"})
    command = [sys.executable, "-m", "pytest", "-q", str(TEST), "--disable-warnings"]
    completed = subprocess.run(command, cwd=root(), env=environment, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", check=False)
    require(completed.returncode == 0, f"pytest failed: {completed.stdout[-2000:]} {completed.stderr[-2000:]}")
    match = re.search(r"(\d+) passed", completed.stdout)
    require(match is not None, "pytest pass count not found")
    count = int(match.group(1))
    require(count >= 40, f"pytest count below fixed minimum: {count}")
    return {
        "schema": "ROUTE_C_C9_PYTEST_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_TEST_SUMMARY_NO_WALLCLOCK",
        "test_target": {"path": TEST.relative_to(root()).as_posix(), "bytes": TEST.stat().st_size,
                        "sha256": sha(TEST)},
        "invocation": ["<current-python>", "-m", "pytest", "-q", TEST.relative_to(root()).as_posix(),
                       "--disable-warnings"],
        "fixed_environment": {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUTF8": "1"},
        "return_code": completed.returncode,
        "tests_passed": count,
        "tests_failed": 0,
        "minimum_required": 40,
        "pytest_pass": True,
        "stderr_empty": completed.stderr == "",
        "authority_boundary": {"system_pair_credit": 0, "TMG4": "HOLD", "release_credit": False},
        "verdict": "C9_PYTEST_PASS__NO_SYSTEM_PAIR_EDGE_PATH_OR_RELEASE_CREDIT",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = make_receipt()
    encoded = stable(receipt)
    if args.write:
        atomic(RECEIPT, encoded)
        mode = "write"
    else:
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == encoded, "pytest receipt drift")
        mode = "check"
    print(json.dumps({"status": "PASS", "mode": mode, "tests_passed": receipt["tests_passed"],
                      "system_pair_credit": 0, "TMG4": "HOLD"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
