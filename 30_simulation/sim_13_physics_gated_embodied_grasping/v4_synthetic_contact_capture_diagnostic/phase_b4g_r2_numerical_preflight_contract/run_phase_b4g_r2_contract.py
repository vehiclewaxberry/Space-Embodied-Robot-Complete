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
PROJECT_ROOT = HERE.parents[3]
GOVERNANCE = HERE / "contracts/PHASE_B4G_R2_GOVERNANCE_AND_NEGATIVE_CONTROLS_V1.json"
TEST_RESULT = HERE / "results/SIM13_V4B4G_R2_TEST_RESULT_V1.json"
VALIDATION = HERE / "results/SIM13_V4B4G_R2_VALIDATION_V1.json"
AUDIT = HERE / "results/SIM13_V4B4G_R2_INDEPENDENT_AUDIT_V1.json"
MANIFEST = HERE / "evidence/SIM13_V4B4G_R2_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json"
GATE = HERE / "results/SIM13_V4B4G_R2_PREFLIGHT_CONTRACT_GATE_V1.json"
TERMINAL = HERE / "results/SIM13_V4B4G_R2_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def record(path: Path, role: str) -> dict[str, Any]:
    return {"path": path.relative_to(PROJECT_ROOT).as_posix(), "role": role, "bytes": path.stat().st_size, "sha256": file_sha(path)}


def outcomes(text: str) -> dict[str, int]:
    def count(pattern: str) -> int:
        match = re.search(rf"(\d+) {pattern}", text)
        return int(match.group(1)) if match else 0

    return {"passed": count("passed"), "failed": count("failed"), "errors": count("errors?"), "skipped": count("skipped")}


def run_checked(script: str) -> bool:
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
        return False
    return True


def main() -> int:
    governance = json.loads(GOVERNANCE.read_text(encoding="utf-8"))
    expected = governance["test_contract"]
    collect = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=HERE,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    nodeids = sorted(line.strip() for line in collect.stdout.splitlines() if "::" in line)
    nodeid_sha = hashlib.sha256("\n".join(nodeids).encode("utf-8")).hexdigest().upper()
    run = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=HERE,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    observed = outcomes(run.stdout + "\n" + run.stderr)
    test_pass = bool(
        collect.returncode == 0
        and run.returncode == 0
        and len(nodeids) == expected["expected_collected"]
        and nodeid_sha == expected["expected_nodeid_sha256"]
        and observed == expected["required_outcome"]
    )
    test_result = {
        "schema": "SIM13_V4B4G_R2_TEST_RESULT_V1",
        "status": "PASS_PHASE_B4G_R2_PYTEST" if test_pass else "FAIL_PHASE_B4G_R2_PYTEST",
        "scope": "LOCAL_CONTRACT_AND_READ_ONLY_BOUND_EVIDENCE_TESTS",
        "collect_returncode": collect.returncode,
        "run_returncode": run.returncode,
        "collected": len(nodeids),
        "nodeid_sha256": nodeid_sha,
        "outcomes": observed,
        "new_preflight_executed": False,
        "full_campaign_authorized": False,
    }
    write_json(TEST_RESULT, test_result)
    if not test_pass:
        print(json.dumps({"test_result": test_result, "pytest_stdout": run.stdout, "pytest_stderr": run.stderr}, ensure_ascii=False))
        return 1
    if not run_checked("validate_phase_b4g_r2_contract.py"):
        return 1
    if not run_checked("independent_audit_phase_b4g_r2_contract.py"):
        return 1

    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract_pass = bool(
        validation["score"]["fail"] == 0
        and audit["score"]["fail"] == 0
        and manifest["self_excluded"] is True
        and manifest["acyclic"] is True
        and all(governance["contract_frozen_true"].values())
        and all(value is False for value in governance["required_false"].values())
    )
    if not contract_pass:
        print(json.dumps({"status": "FAIL_R2_CONTRACT_GATE_PREREQUISITE"}, ensure_ascii=False))
        return 1
    evidence = [
        record(TEST_RESULT, "B4G_R2_PYTEST_RESULT"),
        record(VALIDATION, "B4G_R2_VALIDATION"),
        record(MANIFEST, "B4G_R2_SELF_EXCLUDED_EVIDENCE_MANIFEST"),
        record(AUDIT, "B4G_R2_INDEPENDENT_AUDIT"),
    ]
    gate = {
        "schema": "SIM13_V4B4G_R2_PREFLIGHT_CONTRACT_GATE_V1",
        "status": governance["gate_status_exact"],
        "scope": "NUMERICAL_PREFLIGHT_CONTRACT_ONLY_NOT_EXECUTION_OR_SCIENTIFIC_PASS",
        "contract_layer_pass": True,
        "execution_readiness_status": governance["execution_readiness_status_exact"],
        "scientific_matrix_review_status": "INDEPENDENT_REVIEW_FROZEN_FOR_CONTRACT_ONLY",
        "matrix_case_count": 78,
        "fresh_case_count": 60,
        "common_prop_case_count": 18,
        "negative_controls_registered": governance["negative_control_count"],
        "negative_controls_implemented": False,
        "negative_controls_executed": False,
        "evidence": evidence,
        "required_false": governance["required_false"],
        "new_preflight_executed": False,
        "full_campaign_executed": False,
        "full_campaign_authorized": False,
        "gate_implies_scientific_pass": False,
    }
    write_json(GATE, gate)
    terminal_records = [
        record(MANIFEST, "B4G_R2_SELF_EXCLUDED_EVIDENCE_MANIFEST"),
        record(AUDIT, "B4G_R2_INDEPENDENT_AUDIT"),
        record(GATE, "B4G_R2_CONTRACT_ONLY_GATE"),
    ]
    terminal = {
        "schema": "SIM13_V4B4G_R2_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
        "status": governance["gate_status_exact"],
        "self_excluded": True,
        "acyclic": True,
        "scope": "CONTRACT_ONLY_TERMINAL_NO_EXECUTION_AUTHORITY",
        "record_count": len(terminal_records),
        "records": terminal_records,
        "record_inventory_sha256": canonical_hash(terminal_records),
        "execution_readiness_status": governance["execution_readiness_status_exact"],
        "new_preflight_executed": False,
        "full_campaign_authorized": False,
    }
    write_json(TERMINAL, terminal)
    print(json.dumps({"status": gate["status"], "execution_readiness_status": gate["execution_readiness_status"], "gate_sha256": file_sha(GATE), "terminal_sha256": file_sha(TERMINAL)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
