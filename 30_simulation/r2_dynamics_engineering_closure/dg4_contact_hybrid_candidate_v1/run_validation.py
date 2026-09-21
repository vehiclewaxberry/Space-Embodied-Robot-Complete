"""Replay the DG4 builder twice, run adversarial tests, and emit a stable receipt."""

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
EVALUATOR = HERE / "evaluate_dg4_candidate.py"
CONTRACT = HERE / "contracts" / "DG4_CONTACT_HYBRID_CANDIDATE_CONTRACT_V1.yaml"
RESULTS = HERE / "results"
EVIDENCE = RESULTS / "DG4_CONTACT_HYBRID_EVIDENCE_V1.json"
GATE = RESULTS / "DG4_CONTACT_HYBRID_GATE_V1.json"
RECEIPT = RESULTS / "DG4_CONTACT_HYBRID_VALIDATION_V1.json"
EXPECTED_TESTS = 37


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def run_evaluator(evidence: Path, gate: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(EVALUATOR),
            "--contract",
            str(CONTRACT),
            "--evidence",
            str(evidence),
            "--gate",
            str(gate),
        ],
        cwd=HERE,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
    )


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dg4_validation_", dir=HERE) as td:
        temp = Path(td)
        evidence_a, gate_a = temp / "evidence_a.json", temp / "gate_a.json"
        evidence_b, gate_b = temp / "evidence_b.json", temp / "gate_b.json"
        run_a = run_evaluator(evidence_a, gate_a)
        run_b = run_evaluator(evidence_b, gate_b)
        evidence_deterministic = (
            run_a.returncode == 0
            and run_b.returncode == 0
            and evidence_a.read_bytes() == evidence_b.read_bytes()
        )
        # Gate subject/evidence paths differ between replay files; compare after replacing
        # those path-only fields with fixed sentinels.
        parsed_a = json.loads(gate_a.read_text(encoding="utf-8")) if gate_a.is_file() else {}
        parsed_b = json.loads(gate_b.read_text(encoding="utf-8")) if gate_b.is_file() else {}
        if parsed_a and parsed_b:
            parsed_a["evidence"]["path"] = "<REPLAY>"
            parsed_b["evidence"]["path"] = "<REPLAY>"
            gate_semantic_deterministic = parsed_a == parsed_b
        else:
            gate_semantic_deterministic = False

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
                f"--basetemp={temp / 'pytest'}",
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
        tests_ok = pytest_run.returncode == 0 and tests_passed == EXPECTED_TESTS

        official = run_evaluator(EVIDENCE, GATE)
        official_ok = official.returncode == 0 and EVIDENCE.is_file() and GATE.is_file()

    gate_data = json.loads(GATE.read_text(encoding="utf-8")) if official_ok else {}
    receipt = {
        "schema": "DG4_CONTACT_HYBRID_VALIDATION_V1",
        "execution_time_policy": "OMITTED_FOR_BYTE_DETERMINISM",
        "checks": {
            "independent_evidence_replays_byte_identical": evidence_deterministic,
            "independent_gate_replays_semantically_identical": gate_semantic_deterministic,
            "pytest_returncode_zero": pytest_run.returncode == 0,
            "pytest_tests_passed": tests_passed,
            "pytest_expected_tests": EXPECTED_TESTS,
            "official_gate_emitted": official_ok,
            "official_gate_criteria": f"{gate_data.get('criteria_passed')}/{gate_data.get('criteria_total')}" if official_ok else "UNKNOWN",
        },
        "artifacts": {
            "contract": {"bytes": CONTRACT.stat().st_size, "sha256": sha256(CONTRACT)},
            "solver": {"bytes": (HERE / "src" / "dg4_contact_hybrid.py").stat().st_size, "sha256": sha256(HERE / "src" / "dg4_contact_hybrid.py")},
            "evaluator": {"bytes": EVALUATOR.stat().st_size, "sha256": sha256(EVALUATOR)},
            "tests": {"bytes": (HERE / "tests" / "test_dg4_contact_hybrid.py").stat().st_size, "sha256": sha256(HERE / "tests" / "test_dg4_contact_hybrid.py")},
            "evidence": {"bytes": EVIDENCE.stat().st_size if EVIDENCE.is_file() else None, "sha256": sha256(EVIDENCE) if EVIDENCE.is_file() else None},
            "gate": {"bytes": GATE.stat().st_size if GATE.is_file() else None, "sha256": sha256(GATE) if GATE.is_file() else None},
        },
        "verdict": "PASS" if evidence_deterministic and gate_semantic_deterministic and tests_ok and official_ok else "FAIL",
        "parent_DG4_satisfied": False,
        "physical_contact_ready": False,
        "non_abort_grasp_ready": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    payload = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    RECEIPT.write_text(payload, encoding="utf-8", newline="\n")
    print(receipt["verdict"])
    print(f"tests: {tests_passed}/{EXPECTED_TESTS}")
    print(f"evidence_sha256: {receipt['artifacts']['evidence']['sha256']}")
    print(f"gate_sha256: {receipt['artifacts']['gate']['sha256']}")
    print(f"receipt_sha256: {hashlib.sha256(payload.encode('utf-8')).hexdigest().upper()}")
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
