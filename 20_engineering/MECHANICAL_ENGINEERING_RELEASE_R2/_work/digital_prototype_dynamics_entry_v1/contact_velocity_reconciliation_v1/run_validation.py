"""Run deterministic replay and adversarial tests, then emit a stable validation receipt."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVALUATOR = HERE / "evaluate_contact_velocity_reconciliation.py"
CONTRACT = HERE / "CONTACT_VELOCITY_RECONCILIATION_CANDIDATE_V1.yaml"
GATE = HERE / "CONTACT_VELOCITY_RECONCILIATION_GATE_V1.json"
RECEIPT = HERE / "CONTACT_VELOCITY_RECONCILIATION_VALIDATION_V1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def run_eval(output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EVALUATOR), "--contract", str(CONTRACT), "--output", str(output)],
        cwd=HERE,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cvr_validation_", dir=HERE) as td:
        temp_root = Path(td)
        replay_a = temp_root / "gate_a.json"
        replay_b = temp_root / "gate_b.json"
        run_a = run_eval(replay_a)
        run_b = run_eval(replay_b)
        deterministic = (
            run_a.returncode == 0
            and run_b.returncode == 0
            and replay_a.read_bytes() == replay_b.read_bytes()
        )

        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        pytest_run = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "tests",
                f"--basetemp={temp_root / 'pytest'}",
            ],
            cwd=HERE,
            text=True,
            capture_output=True,
            check=False,
            encoding="utf-8",
            env=env,
        )
        match = re.search(r"(\d+) passed", pytest_run.stdout)
        tests_passed = int(match.group(1)) if match else 0
        tests_ok = pytest_run.returncode == 0 and tests_passed == 11

        official = run_eval(GATE)
        official_ok = official.returncode == 0 and GATE.is_file()

    receipt = {
        "schema": "CONTACT_VELOCITY_RECONCILIATION_VALIDATION_V1",
        "execution_time_policy": "OMITTED_FOR_BYTE_DETERMINISM",
        "checks": {
            "independent_gate_replays_byte_identical": deterministic,
            "pytest_returncode_zero": pytest_run.returncode == 0,
            "pytest_tests_passed": tests_passed,
            "pytest_expected_tests": 11,
            "official_gate_emitted": official_ok,
            "official_gate_criteria": "9/9" if official_ok else "UNKNOWN",
        },
        "artifacts": {
            "contract": {"bytes": CONTRACT.stat().st_size, "sha256": sha256(CONTRACT)},
            "evaluator": {"bytes": EVALUATOR.stat().st_size, "sha256": sha256(EVALUATOR)},
            "test_suite": {
                "bytes": (HERE / "tests" / "test_contact_velocity_reconciliation.py").stat().st_size,
                "sha256": sha256(HERE / "tests" / "test_contact_velocity_reconciliation.py"),
            },
            "gate": {"bytes": GATE.stat().st_size if GATE.is_file() else None, "sha256": sha256(GATE) if GATE.is_file() else None},
        },
        "verdict": "PASS" if deterministic and tests_ok and official_ok else "FAIL",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    payload = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    RECEIPT.write_text(payload, encoding="utf-8", newline="\n")
    print(receipt["verdict"])
    print(f"tests: {tests_passed}/11")
    print(f"gate_sha256: {receipt['artifacts']['gate']['sha256']}")
    print(f"receipt_sha256: {hashlib.sha256(payload.encode('utf-8')).hexdigest().upper()}")
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

