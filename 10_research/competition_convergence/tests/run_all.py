"""Deterministic test runner with explicit 15/15 red-team accounting."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "10_research" / "competition_convergence" / "src"
sys.path.insert(0, str(SRC))

from evidence_contract import deterministic_json_bytes  # noqa: E402


def flatten(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.success_ids: list[str] = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.success_ids.append(test.id())


def main() -> int:
    tests_dir = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(tests_dir), pattern="test_*.py")
    test_ids = sorted(test.id() for test in flatten(suite))
    red_team_ids = [test_id for test_id in test_ids if ".test_rt_" in test_id]
    runner = unittest.TextTestRunner(
        verbosity=2,
        resultclass=RecordingResult,
    )
    result: RecordingResult = runner.run(suite)
    failed_ids = {test.id() for test, _ in result.failures}
    failed_ids.update(test.id() for test, _ in result.errors)
    skipped_ids = {test.id() for test, _ in result.skipped}
    statuses = []
    for test_id in test_ids:
        if test_id in failed_ids:
            status = "FAIL"
        elif test_id in skipped_ids:
            status = "SKIP"
        else:
            status = "PASS"
        statuses.append({"test": test_id, "status": status})
    red_team_passed = sum(
        1
        for item in statuses
        if item["test"] in red_team_ids and item["status"] == "PASS"
    )
    red_team_ok = (
        len(red_team_ids) == 15
        and red_team_passed == 15
        and not any(item["status"] == "SKIP" for item in statuses)
    )
    overall = "PASS" if result.wasSuccessful() and red_team_ok else "FAIL"
    report = {
        "schema_version": "competition-convergence-test-report-v1",
        "overall": overall,
        "tests_total": len(test_ids),
        "tests_passed": sum(item["status"] == "PASS" for item in statuses),
        "tests_failed": sum(item["status"] == "FAIL" for item in statuses),
        "tests_skipped": sum(item["status"] == "SKIP" for item in statuses),
        "red_team": {
            "planned": 15,
            "discovered": len(red_team_ids),
            "completed": len(red_team_ids),
            "passed": red_team_passed,
        },
        "tests": statuses,
    }
    output = ROOT / "10_research" / "competition_convergence" / "results"
    output.mkdir(parents=True, exist_ok=True)
    (output / "test_report.json").write_bytes(deterministic_json_bytes(report))
    print(
        f"overall={overall} tests={len(test_ids)} "
        f"red_team={red_team_passed}/{len(red_team_ids)}"
    )
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
