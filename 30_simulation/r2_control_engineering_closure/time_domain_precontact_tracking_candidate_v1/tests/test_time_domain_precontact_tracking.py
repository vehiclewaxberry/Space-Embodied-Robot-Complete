from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[2]
SOURCE = PACKAGE_ROOT / "src" / "time_domain_precontact_tracking.py"
RESULTS = PACKAGE_ROOT / "results"


def load_core():
    spec = importlib.util.spec_from_file_location("_td_tracking_candidate_test_core", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def strict_json(path: Path):
    return load_core().load_json_strict(path)


def test_contract_is_hash_bound_and_planned_not_self_certified():
    core = load_core()
    contract = core.load_contract()
    assert core.validate_contract(contract)["valid"] is True
    assert contract["claim_boundary"]["time_domain_diagnostic_executed"] is False
    assert "PLANNED_NOT_YET_EXECUTED" in contract["maximum_contract_claim"]


def test_all_direct_and_upstream_transitive_sources_are_bound():
    core = load_core()
    contract = core.load_contract()
    assert core.validate_source_pins(contract, PROJECT_ROOT)["matched"] == 10
    upstream = core.load_upstream(contract, PROJECT_ROOT)
    assert upstream["plant_binding"]["all_match"] is True
    assert upstream["metric_binding"]["all_match"] is False
    mismatches = [row for row in upstream["metric_binding"]["records"] if not row["match"]]
    assert len(mismatches) == 1
    assert mismatches[0]["id"] == "precontact_tracking_parent_gate"
    assert mismatches[0]["actual_bytes"] == 12958
    assert mismatches[0]["actual_sha256"] == "79E53F74029598F166C2879E7E0B843B53AAFB1A47F41FDE785290BAA52D70A2"
    assert all(upstream["upstream_parameter_lock"].values())


def test_two_same_dimension_reference_pairs_are_exact():
    contract = load_core().load_contract()
    for pair in ("PAIR_5D", "PAIR_6D"):
        rows = [row for row in contract["scenarios"] if row["comparison_pair"] == pair]
        assert len(rows) == 2
        assert rows[0]["task"] == rows[1]["task"]
        assert rows[0]["desired_twist_native"] == rows[1]["desired_twist_native"]
        assert rows[0]["desired_units"] == rows[1]["desired_units"]


def test_machine_gate_preserves_exact_single_failure_without_claim_upgrade():
    gate = strict_json(RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_GATE_V1.json")
    assert gate["gate_passed"] is False
    assert gate["summary"] == {
        "passed": 19,
        "total": 20,
        "failed": ["G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT"],
    }
    assert gate["maximum_claim"] == "TIME_DOMAIN_TWIST_TRACKING_DIAGNOSTIC_ATTEMPTED_REPEAT_REQUIRED"
    assert all(value is False for value in gate["authority_boundaries"].values())


def test_controlled_runs_improve_only_against_same_task_baselines():
    evidence = strict_json(RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_EVIDENCE_V1.json")
    contract = load_core().load_contract()
    thresholds = contract["thresholds"]
    for row in evidence["same_dimension_comparisons"].values():
        assert row["same_task_dimension_reference_units_frame_metric"] is True
        assert row["final_error_ratio_controlled_to_uncontrolled"] <= thresholds["controlled_final_error_ratio_to_same_task_uncontrolled_max"]
        assert row["rms_error_ratio_controlled_to_uncontrolled"] <= thresholds["controlled_rms_error_ratio_to_same_task_uncontrolled_max"]


def test_p_h_work_and_qp_are_separate_unit_safe_ledgers():
    evidence = strict_json(RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_EVIDENCE_V1.json")
    thresholds = load_core().load_contract()["thresholds"]
    for scenario in evidence["scenarios"]:
        for solver in ("rk4_audit", "dop853_audit"):
            row = scenario[solver]
            ledger = row["physics_ledger"]
            assert ledger["max_linear_momentum_body_inertial_kg_m_s"] <= thresholds["linear_momentum_residual_max_kg_m_s"]
            assert ledger["max_angular_momentum_body_inertial_kg_m2_s"] <= thresholds["angular_momentum_about_fixed_inertial_origin_residual_max_kg_m2_s"]
            assert ledger["max_work_energy_absolute_J"] <= thresholds["work_energy_absolute_max_J"]
            assert row["qP_lock"]["qP_position_lock_max_abs_m"] <= thresholds["qP_position_lock_max_abs_m"]
            assert row["max_constraint_reaction_power_abs_W"] <= thresholds["constraint_reaction_power_max_abs_W"]


def test_solver_cross_and_replay_are_recorded_for_all_four_runs():
    evidence = strict_json(RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_EVIDENCE_V1.json")
    assert len(evidence["scenarios"]) == 4
    for row in evidence["scenarios"]:
        assert row["deterministic_replay"]["byte_identical_canonical_replay"] is True
        assert np.isfinite(row["solver_cross"]["weighted_task_error_max_abs_per_s"])


def test_negative_controls_all_fail_closed():
    negative = strict_json(RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_NEGATIVE_CONTROL_RESULTS_V1.json")
    assert negative["all_pass"] is True
    assert negative["passed"] == negative["count"]
    assert negative["count"] >= negative["minimum_required"]


def test_manifest_and_sha_csv_inventory_match_current_bytes():
    manifest = strict_json(RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_MANIFEST_V1.json")
    assert manifest["inventory_count"] == 9
    for row in manifest["inventory"]:
        path = PROJECT_ROOT / row["path"]
        raw = path.read_bytes()
        assert len(raw) == row["bytes"]
        assert hashlib.sha256(raw).hexdigest().upper() == row["sha256"]
    csv_path = RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_SHA256_V1.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["path"] for row in rows] == [row["path"] for row in manifest["inventory"]]


def test_parent_holds_are_retained_in_evidence():
    evidence = strict_json(RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_EVIDENCE_V1.json")
    assert evidence["upstream_gate_state"]["parent_dynamics_hold_retained"] is True
    assert evidence["upstream_gate_state"]["parent_control_hold_retained"] is True
    assert evidence["authority_boundaries"]["parent_gate_reissued"] is False
    assert evidence["authority_boundaries"]["next_stage_authorized"] is False
    assert evidence["authority_boundaries"]["release_credit"] is False
