from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


V2_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = V2_ROOT / "run_negative_controls_prebind_v1.py"


def _runner_module():
    module_name = "formal_nc_runner"
    spec = importlib.util.spec_from_file_location(module_name, RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_formal_runner_executes_only_defensible_subset() -> None:
    runner = _runner_module()
    evidence = runner.build_evidence()
    assert evidence["summary"] == {
        "total": 20,
        "executed": 15,
        "passed": 15,
        "failed": 0,
        "pass": 15,
        "fail": 0,
        "hold": 5,
        "not_run_dependency_hold": 5,
    }
    assert evidence["formal_runner_verdict"] == "PASS_EXECUTED_SUBSET_WITH_DEPENDENCY_HOLDS"
    assert evidence["release_credit"] is False
    assert evidence["release"] is False
    assert evidence["next"] is False
    assert evidence["contact_release_eligible"] is False
    assert evidence["next_stage_authorized"] is False
    assert evidence["negative_controls_all_passed"] is False


def test_every_row_matches_frozen_registry_and_invariants() -> None:
    runner = _runner_module()
    evidence = runner.build_evidence()
    rows = evidence["controls"]
    assert [item["control_id"] for item in rows] == [f"NC{index:02d}" for index in range(1, 21)]
    specs = {item.control_id: item for item in runner.REGISTRY}
    for row in rows:
        spec = specs[row["control_id"]]
        assert row["stimulus"] == spec.stimulus
        assert row["required_observation"] == spec.required_observation
        assert row["canonical_outcome"] == spec.canonical_outcome
        assert row["future_gate"] == spec.future_gate
        assert row["registry_execution_class"] == spec.execution_class.value
        assert row["registry_dependency"] == spec.dependency
        if row["executed"]:
            assert row["status"] == "PASS_NEGATIVE_CONTROL_DETECTED"
            assert row["baseline"]["qualified"] is True
            assert row["mutation"]["deep_copy"] is True
            assert row["mutation"]["single_fault"] is True
            assert row["non_abort_execution_count"] == 0
            assert row["exact_reason_match"] is True
            assert row["deterministic_repeat"] is True
            assert row["baseline_source_hashes_unchanged"] is True
        else:
            assert row["status"] == "NOT_RUN_DEPENDENCY_HOLD"
            assert row["hold_dependency"]


def test_dependency_holds_are_not_filled_with_synthetic_passes() -> None:
    runner = _runner_module()
    evidence = runner.build_evidence()
    holds = {row["control_id"] for row in evidence["controls"] if not row["executed"]}
    assert holds == {"NC15", "NC16", "NC18", "NC19", "NC20"}


def test_exact_reasons_and_unit_scope_are_preserved() -> None:
    runner = _runner_module()
    evidence = runner.build_evidence()
    rows = {row["control_id"]: row for row in evidence["controls"]}
    for control_id, reason in runner.EXPECTED_REASON.items():
        assert rows[control_id]["exact_reason_observed"] == reason
    for control_id in {"NC08", "NC09", "NC10", "NC13"}:
        assert rows[control_id]["runner_scope"] == "UNIT_KERNEL_NOT_PRODUCTION_RUNTIME"


def test_runner_is_byte_deterministic_and_writes_requested_path(tmp_path: Path) -> None:
    runner = _runner_module()
    first = runner.build_evidence()
    second = runner.build_evidence()
    assert first == second
    output = tmp_path / "evidence.json"
    written = runner.write_evidence(output)
    assert written == first
    assert json.loads(output.read_text(encoding="utf-8")) == first
    assert output.read_bytes().endswith(b"\n")
    assert b"\r\n" not in output.read_bytes()
