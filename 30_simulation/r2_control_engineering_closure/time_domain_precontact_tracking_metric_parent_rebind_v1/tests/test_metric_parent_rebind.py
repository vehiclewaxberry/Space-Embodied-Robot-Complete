from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[2]
SOURCE = PACKAGE_ROOT / "src" / "metric_parent_rebind.py"
RESULTS = PACKAGE_ROOT / "results"


def core():
    spec = importlib.util.spec_from_file_location("_metric_parent_rebind_test_core", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_contract_and_twelve_direct_pins_are_exact():
    module = core()
    contract = module.load_contract()
    assert module.validate_contract(contract)["valid"] is True
    assert module.validate_source_pins(contract, PROJECT_ROOT)["matched"] == 12


def test_rebind_gate_passes_but_original_gate_remains_false():
    module = core()
    gate = module.load_json_strict(RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_GATE_V1.json")
    assert gate["gate_passed"] is True
    assert gate["summary"] == {"passed": 16, "total": 16, "failed": []}
    assert gate["original_time_domain_gate_passed"] is False
    assert gate["original_time_domain_gate_reissued"] is False


def test_single_mismatch_and_current_parent_hold_are_explicit():
    module = core()
    evidence = module.load_json_strict(RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_EVIDENCE_V1.json")
    assert evidence["original_metric_binding_audit"]["exact_single_parent_hold_mismatch"] is True
    mismatches = evidence["original_metric_binding_audit"]["mismatches"]
    assert len(mismatches) == 1 and mismatches[0]["id"] == "precontact_tracking_parent_gate"
    assert evidence["current_parent_hold_audit"]["all_match"] is True


def test_rebound_metric_is_seven_of_seven_and_seventeen_of_seventeen():
    module = core()
    evidence = module.load_json_strict(RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_EVIDENCE_V1.json")
    assert evidence["rebound_metric_source_binding"]["matched"] == 7
    assert evidence["rebound_metric_gate"]["passed"] == evidence["rebound_metric_gate"]["total"] == 17
    assert evidence["rebound_metric_gate"]["all_checks_pass"] is True


def test_recompute_roundoff_is_bounded_and_structure_exact():
    module = core()
    contract = module.load_contract()
    evidence = module.load_json_strict(RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_EVIDENCE_V1.json")
    comparison = evidence["task_metric_recompute_comparison"]
    assert comparison["structure_and_non_numeric_exact"] is True
    assert comparison["numeric_max_abs"] <= contract["recompute_comparison"]["numeric_max_abs_tolerance"]


def test_original_time_domain_scientific_checks_and_negative_controls_remain():
    module = core()
    evidence = module.load_json_strict(RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_EVIDENCE_V1.json")
    assert evidence["original_time_domain_gate_summary"] == {
        "passed": 19,
        "total": 20,
        "failed": ["G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT"],
    }


def test_rebind_negative_controls_all_pass():
    module = core()
    negative = module.load_json_strict(RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_NEGATIVE_CONTROLS_V1.json")
    assert negative["all_pass"] is True
    assert negative["passed"] == negative["count"] == 10


def test_all_authority_boundaries_stay_false():
    module = core()
    gate = module.load_json_strict(RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_GATE_V1.json")
    assert all(value is False for value in gate["authority_boundaries"].values())
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False


def test_manifest_inventory_matches_current_bytes():
    module = core()
    manifest = module.load_json_strict(RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_MANIFEST_V1.json")
    assert manifest["inventory_count"] == 9
    for row in manifest["inventory"]:
        raw = (PROJECT_ROOT / row["path"]).read_bytes()
        assert len(raw) == row["bytes"]
        assert hashlib.sha256(raw).hexdigest().upper() == row["sha256"]
