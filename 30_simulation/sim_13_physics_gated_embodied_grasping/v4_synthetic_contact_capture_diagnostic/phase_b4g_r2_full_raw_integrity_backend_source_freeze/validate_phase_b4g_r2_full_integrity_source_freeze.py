"""Read-only validator for the full raw-integrity backend source freeze."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

from r2_full_integrity.fixture_factory import write_technical_fixture
from r2_full_integrity.freeze_support import forbidden_artifacts, seal, source_inventory, strict_load
from r2_full_integrity.integrity import REQUIRED_GATES, evaluate_full_raw_integrity
from r2_full_integrity.negative_controls import run_negative_controls
from r2_full_integrity.source_api import verify_source_bindings


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_VALIDATION_V1.json"
FREEZE_CONTRACT = HERE / "contracts/PHASE_B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_CONTRACT_V1.json"
BACKEND_CONTRACT = HERE / "contracts/PHASE_B4G_R2_FULL_RAW_INTEGRITY_BACKEND_V1.json"
GOVERNANCE = HERE / "contracts/PHASE_B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_GOVERNANCE_V1.json"


def _pytest_result() -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=HERE,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(r"(\d+) passed", output)
    return {
        "passed": completed.returncode == 0 and match is not None,
        "return_code": completed.returncode,
        "passed_count": int(match.group(1)) if match else 0,
        "summary": output.strip()[-500:],
    }


def validate_source_freeze(*, write_output: bool = False) -> dict[str, Any]:
    contract = strict_load(FREEZE_CONTRACT)
    backend = strict_load(BACKEND_CONTRACT)
    governance = strict_load(GOVERNANCE)
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, detail: Any) -> None:
        checks.append({"check_id": check_id, "passed": bool(passed), "detail": detail})

    inventory = source_inventory(HERE)
    check("V01_SOURCE_INVENTORY_NONEMPTY", len(inventory) >= 10, len(inventory))
    artifacts = forbidden_artifacts(HERE)
    check("V02_FORBIDDEN_ARTIFACTS_ZERO", not artifacts, artifacts)
    source_bindings = verify_source_bindings()
    check("V03_EXTERNAL_SOURCE_BINDINGS", source_bindings["passed"] is True and source_bindings["source_count"] == 14, source_bindings["source_count"])
    check("V04_FREEZE_CONTRACT", contract.get("required_pytest_pass_count") == 18 and contract.get("required_negative_control_count") == 14, contract.get("schema"))
    check("V05_BACKEND_CONTRACT", backend.get("output_state_separation", {}).get("trajectory_count") == 0 and len(backend.get("gate_rules", {})) == 10, backend.get("schema"))
    required_false = (
        "r2_numerical_preflight_executed", "current_system_bound", "formal_nc19_credit",
        "scientific_credit", "owner_authorized", "production_credit",
        "release_authorized", "next_stage_authorized", "cad_or_urdf_generation_authorized",
        "runner_present",
    )
    check("V06_GOVERNANCE_FALSE", all(governance.get(name) is False for name in required_false), list(required_false))

    with tempfile.TemporaryDirectory(prefix=".technical-fixture-", dir=HERE) as directory:
        case, context = write_technical_fixture(Path(directory)).load()
        nominal = evaluate_full_raw_integrity(case, context)
    check(
        "V07_NOMINAL_ALL_GATE_PREDICATES",
        nominal["technical_fixture_full_raw_integrity_predicate_pass"] is True
        and set(nominal["gate_records"]) == set(REQUIRED_GATES)
        and all(row["scientific_predicate"] is True for row in nominal["gate_records"].values()),
        nominal["status"],
    )
    check(
        "V08_NOMINAL_NO_CREDIT",
        nominal["passed"] is False and nominal["trajectory_count"] == 0
        and nominal["actual_case_full_raw_integrity_recomputed"] is False
        and nominal["source_only_candidate_predicate_pass"] is False
        and nominal["next_stage_authorized"] is False,
        nominal["status"],
    )

    negative = run_negative_controls(HERE)
    check("V09_NEGATIVE_CONTROLS", negative["passed"] is True and negative["control_count"] == negative["killed_count"] == 14, negative["killed_count"])
    pytest_result = _pytest_result()
    check("V10_PYTEST", pytest_result["passed"] is True and pytest_result["passed_count"] == 18, pytest_result)

    integrity_source = (HERE / "r2_full_integrity/integrity.py").read_text(encoding="utf-8")
    forbidden_oracles = ["gate_predicates", "selector_case_integrity_pass", "clearance.integrity_pass"]
    check("V11_FORBIDDEN_ORACLE_INPUTS_ABSENT", all(token not in integrity_source for token in forbidden_oracles), forbidden_oracles)
    check("V12_TEMPORARY_FIXTURES_REMOVED", not forbidden_artifacts(HERE), forbidden_artifacts(HERE))
    passed = all(item["passed"] for item in checks)
    result = seal({
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_VALIDATION_V1",
        "status": "PASS_SOURCE_VALIDATION" if passed else "FAIL_SOURCE_VALIDATION",
        "source_freeze_pass_eligible": passed,
        "score": {
            "total": len(checks),
            "passed": sum(1 for item in checks if item["passed"]),
            "failed": [item["check_id"] for item in checks if not item["passed"]],
        },
        "checks": checks,
        "source_inventory_count": len(inventory),
        "negative_control_count": negative["control_count"],
        "pytest_passed_count": pytest_result["passed_count"],
        "technical_fixture_all_gate_predicates_true": nominal["technical_fixture_full_raw_integrity_predicate_pass"],
        "actual_case_full_raw_integrity_recomputed": False,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
        "next_stage_authorized": False,
    })
    if write_output:
        modules = __import__("r2_full_integrity.source_api", fromlist=["load_raw_modules"])
        modules.load_raw_modules()["strict_json"].atomic_write_json(OUTPUT, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = validate_source_freeze(write_output=args.write_receipt)
    print(f"{result['status']} {result['score']['passed']}/{result['score']['total']}")
    return 0 if result["source_freeze_pass_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
