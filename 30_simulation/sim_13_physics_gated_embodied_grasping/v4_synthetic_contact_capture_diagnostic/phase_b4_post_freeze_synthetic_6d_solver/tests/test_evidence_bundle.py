from __future__ import annotations

import hashlib
import json

import pytest


EVIDENCE_FILES = [
    "SIM13_V4B4E_RUNTIME_ENVIRONMENT_V1.json",
    "SIM13_V4B4E_EVENT_INPUTS_V1.json",
    "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json",
    "SIM13_V4B4E_ACTIVE_TRACES_V1.json",
    "SIM13_V4B4E_NATIVE_UNIT_CHECKS_V1.json",
    "SIM13_V4B4E_CROSS_INTEGRATOR_LEDGER_V1.json",
    "SIM13_V4B4E_NEGATIVE_CONTROLS_V1.json",
    "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json",
    "SIM13_V4B4E_DIFFERENCE_STEP_AUDIT_V1.json",
    "SIM13_V4B4E_SOURCE_MANIFEST_V1.json",
]


@pytest.mark.parametrize("filename", EVIDENCE_FILES)
def test_required_raw_evidence_exists_and_is_json(filename, phase_root):
    path = phase_root / "evidence" / filename
    assert path.is_file()
    assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)


def test_six_runs_exist_in_every_run_ledger(phase_root, read_json):
    acquisitions = read_json(phase_root / "evidence" / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json")
    traces = read_json(phase_root / "evidence" / "SIM13_V4B4E_ACTIVE_TRACES_V1.json")
    expected = {"rk4_coarse", "rk4_fine", "rk4_reference", "midpoint_coarse", "midpoint_fine", "midpoint_reference"}
    assert set(acquisitions["runs"]) == expected
    assert set(traces["runs"]) == expected


def test_all_six_run_check_groups_pass(phase_root, read_json):
    checks = read_json(phase_root / "evidence" / "SIM13_V4B4E_NATIVE_UNIT_CHECKS_V1.json")
    assert all(all(group.values()) for run in checks["runs"].values() for group in run.values())


def test_cross_integrator_uses_independent_event_times(phase_root, read_json):
    cross = read_json(phase_root / "evidence" / "SIM13_V4B4E_CROSS_INTEGRATOR_LEDGER_V1.json")
    assert cross["forced_shared_acquisition_time"] is False
    assert cross["primary_acquisition_time_s"] != cross["independent_acquisition_time_s"]
    assert cross["acquisition_event_time_difference_s"] <= cross["acquisition_event_time_tolerance_s"]


def test_no_finite_removal_is_not_counted_as_removal_pass(phase_root, read_json):
    cross = read_json(phase_root / "evidence" / "SIM13_V4B4E_CROSS_INTEGRATOR_LEDGER_V1.json")
    assert cross["primary_removal_finite"] is False
    assert cross["independent_removal_finite"] is False
    assert cross["removal_event_comparison"] == "NOT_EVALUATED_NO_FINITE_EVENT"
    assert cross["both_horizon_exhausted_is_removal_capability_pass"] is False


def test_negative_control_evidence_is_22_of_22(phase_root, read_json):
    ledger = read_json(phase_root / "evidence" / "SIM13_V4B4E_NEGATIVE_CONTROLS_V1.json")
    assert ledger["count"] == ledger["passed"] == 22
    assert all(item["killed"] and item["affected_path_hit"] for item in ledger["results"])
    assert all(item["nominal_sha256"] != item["mutant_sha256"] for item in ledger["results"])
    assert all(item["nominal_gate_output_sha256"] != item["mutant_gate_output_sha256"] for item in ledger["results"])


def test_abstract_removal_fixture_is_not_main_execution(phase_root, read_json):
    fixture = read_json(phase_root / "evidence" / "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json")
    assert "PERTURBED_FROM_HASH_BOUND_B3_EVENT" in fixture["scope"]
    assert "NOT_MAIN_B3_TRAJECTORY" in fixture["scope"]
    assert fixture["fixture_pass_does_not_set_main_synthetic_removal_executed"] is True
    assert fixture["fixture_inputs_are_hardware_specifications"] is False
    assert fixture["fixture_satisfies_main_b3_soft_capture_trigger"] is False
    assert fixture["fixture_receives_physical_or_main_trigger_credit"] is False
    assert fixture["fixture_contact_points_and_potentials_recomputed_from_perturbed_state"] is True
    assert fixture["no_state_mutation_after_acquisition"] is True
    assert fixture["clearance_derived_from_same_active_state_trajectory"] is True
    assert "COUNTERFACTUAL_ATTACHED_SEARCH_TRACE" in fixture["active_trace_semantics"]
    assert fixture["same_active_trajectory_required_interval_s"] == [
        fixture["fixture_event"]["time_s"], fixture["clearance"]["removal_time_s"]
    ]
    assert fixture["propagate_active_finite_event_branch_executed"] is True
    assert fixture["exact_active_state_reconstructed_at_offgrid_removal_time"] is True
    event = fixture["fixture_event"]
    relative_index = (fixture["clearance"]["removal_time_s"] - event["time_s"]) / event["step_s"]
    assert abs(relative_index - round(relative_index)) > 1.0e-6
    assert fixture["post_release"]["post_release_passed"] is True
    assert abs(fixture["post_release"]["observation_duration_s"] - 0.005) <= 1.0e-12
    assert fixture["internal_negative_gap_trap"]["certifier_returned_finite_event"] is False


def test_runtime_memory_is_diagnostic_not_a_gate_or_override(phase_root, read_json):
    runtime = read_json(phase_root / "evidence" / "SIM13_V4B4E_RUNTIME_ENVIRONMENT_V1.json")
    assert runtime["available_physical_memory_bytes"] > 0
    assert runtime["memory_gate_applicable"] is False
    assert runtime["memory_gate_evaluated"] is False
    assert runtime["memory_gate_passed"] is False
    assert runtime["owner_override_used"] is False
    assert runtime["unified_r2_generator_invoked"] is False
    assert runtime["cad_or_com_write_invoked"] is False


def test_difference_step_is_numerical_not_measurement_uncertainty(phase_root, read_json):
    audit = read_json(phase_root / "evidence" / "SIM13_V4B4E_DIFFERENCE_STEP_AUDIT_V1.json")
    assert audit["classification"] == "NUMERICAL_DIRECTIONAL_DIFFERENCE_STEP_AUDIT_NOT_MEASUREMENT_UNCERTAINTY"


def test_source_manifest_hashes_every_declared_source(phase_root, read_json):
    manifest = read_json(phase_root / "evidence" / "SIM13_V4B4E_SOURCE_MANIFEST_V1.json")
    assert manifest["self_excluded"] is True
    assert manifest["source_count"] == len(manifest["sources"])
    project = next(parent for parent in phase_root.parents if (parent / "PROJECT_MAP.md").is_file())
    for item in manifest["sources"]:
        path = project / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == item["sha256"]


def test_campaign_summary_separates_solver_verification_from_branch_outcome(phase_root, read_json):
    summary = read_json(phase_root / "results" / "SIM13_V4B4E_CAMPAIGN_SUMMARY_V1.json")
    assert summary["all_event_local_and_active_checks_pass"] is True
    assert summary["negative_controls_22_killed"] is True
    assert summary["negative_controls_22_real_raw_mutations_killed"] is True
    assert summary["b4_hybrid_removal_and_post_release_solver_implemented"] is True
    assert summary["algorithm_only_hybrid_removal_fixture_passed"] is True
    assert summary["main_branch_removal_or_release_capability_pass"] is False
    assert summary["primary_terminal_status"] == "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED"
    assert summary["primary_synthetic_removal_executed"] is False
    assert summary["bounded_horizon_global_no_event_claim"] is False
