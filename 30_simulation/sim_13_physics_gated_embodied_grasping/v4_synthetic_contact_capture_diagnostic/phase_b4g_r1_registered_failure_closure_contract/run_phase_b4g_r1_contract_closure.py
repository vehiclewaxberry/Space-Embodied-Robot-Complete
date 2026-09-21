from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "contracts/PHASE_B4G_R1_FAILURE_CLOSURE_CONTRACT_V1.json"
TEST_RESULT = HERE / "results/SIM13_V4B4G_R1_TEST_RESULT_V1.json"


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _outcomes(text: str) -> dict[str, int]:
    def count(label: str) -> int:
        match = re.search(rf"(\d+) {label}", text)
        return int(match.group(1)) if match else 0

    return {
        "passed": count("passed"),
        "failed": count("failed"),
        "errors": count("errors?"),
        "skipped": count("skipped"),
    }


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected = contract["test_contract"]
    collect = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q"],
        cwd=HERE,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    nodeids = sorted(line.strip() for line in collect.stdout.splitlines() if "::" in line)
    nodeid_sha = hashlib.sha256("\n".join(nodeids).encode("utf-8")).hexdigest().upper()
    run = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q"],
        cwd=HERE,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    outcomes = _outcomes(run.stdout + "\n" + run.stderr)
    passed = bool(
        collect.returncode == 0
        and run.returncode == 0
        and len(nodeids) == expected["expected_collected"]
        and nodeid_sha == expected["expected_nodeid_sha256"]
        and outcomes == expected["required_outcome"]
    )
    result = {
        "schema": "SIM13_V4B4G_R1_TEST_RESULT_V1",
        "status": "PASS_PHASE_B4G_R1_PYTEST" if passed else "FAIL_PHASE_B4G_R1_PYTEST",
        "scope": "LOCAL_CONTRACT_AND_READ_ONLY_PRESERVED_EVIDENCE_TESTS",
        "collect_returncode": collect.returncode,
        "run_returncode": run.returncode,
        "collected": len(nodeids),
        "nodeid_sha256": nodeid_sha,
        "outcomes": outcomes,
        "no_new_physics_campaign": True,
    }
    _write_json(TEST_RESULT, result)
    if not passed:
        print(json.dumps({"test_result": result, "pytest_stdout": run.stdout, "pytest_stderr": run.stderr}, ensure_ascii=False))
        return 1

    for script in ("validate_phase_b4g_r1_contract.py", "independent_audit_phase_b4g_r1_contract.py"):
        process = subprocess.run(
            [sys.executable, "-B", script],
            cwd=HERE,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.stdout:
            print(process.stdout.strip())
        if process.returncode != 0:
            if process.stderr:
                print(process.stderr.strip(), file=sys.stderr)
            return process.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
