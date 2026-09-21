"""Fail-closed validator for the B4E post-freeze solver evidence bundle."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from typing import Any


PHASE_ROOT = Path(__file__).resolve().parent
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))

import b4_solver.constraint_solver as solver  # noqa: E402
import run_phase_b4_solver as campaign_module  # noqa: E402


EVIDENCE = PHASE_ROOT / "evidence"
RESULTS = PHASE_ROOT / "results"
VALIDATION_PATH = EVIDENCE / "SIM13_V4B4E_VALIDATION_V1.json"
EVIDENCE_MANIFEST_PATH = EVIDENCE / "SIM13_V4B4E_EVIDENCE_MANIFEST_V1.json"
PRE_AUDIT_GATE_PATH = RESULTS / "SIM13_V4B4E_PRE_AUDIT_GATE_V1.json"
FINAL_ARTIFACTS = [
    EVIDENCE / "SIM13_V4B4E_INDEPENDENT_AUDIT_RECEIPT_V1.json",
    RESULTS / "SIM13_V4B4E_AUDITED_GATE_V1.json",
    RESULTS / "SIM13_V4B4E_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json",
]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root not object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def file_record(path: Path, role: str) -> dict[str, Any]:
    return {"path": path.relative_to(PHASE_ROOT).as_posix(), "role": role, "bytes": path.stat().st_size, "sha256": sha256(path)}


def cleanup_final_artifacts() -> None:
    for path in FINAL_ARTIFACTS:
        if path.is_file():
            path.unlink()


def main() -> int:
    cleanup_final_artifacts()
    checks: list[dict[str, Any]] = []

    def add(identifier: str, passed: bool, detail: Any) -> None:
        checks.append({"id": identifier, "passed": bool(passed), "detail": detail})

    try:
        source_before = campaign_module.source_inventory()
        contracts = {
            name: read_json(PHASE_ROOT / "contracts" / name)
            for name in (
                "PHASE_B4E_POST_FREEZE_WORK_AUTHORIZATION_V1.json", "PHASE_B4E_RUN_SPEC_V1.json",
                "PHASE_B4E_GOVERNANCE_V1.json", "PHASE_B4E_SOURCE_BINDINGS_V1.json",
                "PHASE_B4E_TEST_INVENTORY_V1.json", "PHASE_B4E_EVIDENCE_SCHEMA_V1.json",
            )
        }
        add("B4EV01_CONTRACT_SCHEMA_SET", all(value.get("schema", "").startswith("SIM13_V4B4E") for value in contracts.values()), sorted(contracts))
        add("B4EV02_POST_FREEZE_PLAN_RECORD", contracts["PHASE_B4E_POST_FREEZE_WORK_AUTHORIZATION_V1.json"]["basis"]["post_freeze_plan_updated"] is True, "workflow only")
        add("B4EV03_NO_OWNER_AUTHORITY", not any(contracts["PHASE_B4E_POST_FREEZE_WORK_AUTHORIZATION_V1.json"]["authority_boundary"].values()), contracts["PHASE_B4E_POST_FREEZE_WORK_AUTHORIZATION_V1.json"]["authority_boundary"])
        add("B4EV04_BOUNDED_HORIZON", contracts["PHASE_B4E_RUN_SPEC_V1.json"]["active_propagation"]["end_time_s"] == 0.08, contracts["PHASE_B4E_RUN_SPEC_V1.json"]["active_propagation"])
        add("B4EV05_HORIZON_NOT_GLOBAL_EMPTY", contracts["PHASE_B4E_RUN_SPEC_V1.json"]["horizon_exhaustion_semantics"]["equivalent_to_global_empty_eligibility_set"] is False, contracts["PHASE_B4E_RUN_SPEC_V1.json"]["horizon_exhaustion_semantics"])
        add("B4EV06_SOURCE_INVENTORY_PRESENT", len(source_before) >= 20, len(source_before))

        manifest = read_json(EVIDENCE / "SIM13_V4B4E_SOURCE_MANIFEST_V1.json")
        add("B4EV07_SOURCE_MANIFEST_COUNT", manifest["source_count"] == len(manifest["sources"]) == len(source_before), {"declared": manifest["source_count"], "observed": len(source_before)})
        add("B4EV08_SOURCE_MANIFEST_EXACT", manifest["sources"] == source_before, "exact path/role/bytes/SHA equality")
        add("B4EV09_TRANSITIVE_B4_VERIFIED", manifest["frozen_b4_contract_recursively_bound"] is True and len(solver.verify_bound_sources()) == 11, "11 direct plus transitive B4 bindings")
        local_names = {path.name for path in PHASE_ROOT.rglob("*") if path.is_file()}
        forbidden = {"MECH_RL_SYSTEM_INTERFACE_V2.yaml", "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json", "execution.lock", "release.marker"}
        add("B4EV10_NO_FORBIDDEN_ARTIFACT", not local_names.intersection(forbidden) and not any(path.suffix.lower() == ".urdf" for path in PHASE_ROOT.rglob("*")), sorted(local_names.intersection(forbidden)))

        inventory = contracts["PHASE_B4E_TEST_INVENTORY_V1.json"]["pytest"]
        collect = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=PHASE_ROOT, capture_output=True, text=True, check=False)
        nodeids = [line.strip() for line in collect.stdout.splitlines() if "::" in line]
        node_payload = ("\n".join(nodeids) + "\n").encode("utf-8")
        module_counts = dict(Counter(nodeid.split("::")[0] for nodeid in nodeids))
        add("B4EV11_COLLECT_RETURN_CODE", collect.returncode == 0, collect.returncode)
        add("B4EV12_NODEID_COUNT", len(nodeids) == inventory["expected_collected"], len(nodeids))
        add("B4EV13_NODEID_SHA", hashlib.sha256(node_payload).hexdigest().upper() == inventory["expected_nodeid_sha256"], hashlib.sha256(node_payload).hexdigest().upper())
        add("B4EV14_NODEID_MODULE_COUNTS", module_counts == inventory["module_counts"], module_counts)

        with tempfile.TemporaryDirectory(prefix="b4e_pytest_") as temporary:
            junit = Path(temporary) / "junit.xml"
            tests = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={junit}"], cwd=PHASE_ROOT, capture_output=True, text=True, check=False)
            root = ET.parse(junit).getroot()
            suite = root if root.tag == "testsuite" else root.find("testsuite")
            if suite is None:
                raise RuntimeError("JUNIT_TESTSUITE_MISSING")
            total = int(suite.attrib.get("tests", "0")); failures = int(suite.attrib.get("failures", "0")); errors = int(suite.attrib.get("errors", "0")); skipped = int(suite.attrib.get("skipped", "0"))
        passed = total - failures - errors - skipped
        add("B4EV15_PYTEST_RETURN_CODE", tests.returncode == 0, tests.returncode)
        add("B4EV16_PYTEST_PASSED", passed == inventory["required_outcome"]["passed"], passed)
        add("B4EV17_PYTEST_FAILED_ZERO", failures == 0, failures)
        add("B4EV18_PYTEST_ERRORS_ZERO", errors == 0, errors)
        add("B4EV19_PYTEST_SKIPPED_ZERO", skipped == 0, skipped)
        add("B4EV20_PYTEST_NO_XFAIL_XPASS_DESELECT", not re.search(r"\b(xfailed|xpassed|deselected)\b", tests.stdout + tests.stderr), (tests.stdout + tests.stderr)[-1000:])

        raw_names = contracts["PHASE_B4E_EVIDENCE_SCHEMA_V1.json"]["publication_order"][:10]
        runtime = read_json(EVIDENCE / "SIM13_V4B4E_RUNTIME_ENVIRONMENT_V1.json")
        runtime_memory_clean = (
            runtime["memory_gate_applicable"] is False
            and runtime["memory_gate_evaluated"] is False
            and runtime["memory_gate_passed"] is False
            and runtime["owner_override_used"] is False
            and runtime["unified_r2_generator_invoked"] is False
            and runtime["cad_or_com_write_invoked"] is False
            and runtime["available_physical_memory_bytes"] is not None
        )
        add("B4EV21_RAW_EVIDENCE_COMPLETE", all((EVIDENCE / name).is_file() for name in raw_names) and runtime_memory_clean, {"files": raw_names, "runtime_memory_clean": runtime_memory_clean})
        events = read_json(EVIDENCE / "SIM13_V4B4E_EVENT_INPUTS_V1.json")
        add("B4EV22_SIX_EVENT_INPUTS", len(events["runs"]) == 6 and len({run["run_id"] for run in events["runs"]}) == 6, [run["run_id"] for run in events["runs"]])
        primary_event = next(run for run in events["runs"] if run["run_id"] == "rk4_reference")
        add("B4EV23_PRIMARY_TRIGGER_ANCHOR", primary_event["index"] == 205 and primary_event["time_s"] == 0.051250000000000004, {"index": primary_event["index"], "time": primary_event["time_s"]})

        acquisitions = read_json(EVIDENCE / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json")["runs"]
        add("B4EV24_SIX_ACQUISITIONS", len(acquisitions) == 6, sorted(acquisitions))
        add("B4EV25_ALL_RANKS", all(value["ranks"] == {"L_hat": 14, "J_hat": 6, "G_bar": 5} for value in acquisitions.values()), {key: value["ranks"] for key, value in acquisitions.items()})
        add("B4EV26_NO_FORBIDDEN_BACKEND", all(value["backend_provenance"]["acquisition_pinv_or_lstsq"] == "FORBIDDEN_NOT_USED" for value in acquisitions.values()), "all six")
        add("B4EV27_CONTACT_POTENTIAL_ONCE", all(value["energy_audit"]["U_contact_minus_J"] == value["energy_audit"]["U_left_minus_J"] + value["energy_audit"]["U_right_minus_J"] for value in acquisitions.values()), "all six")
        add("B4EV28_SYNTHETIC_SIXTH_ATTRIBUTION", all(value["wrench_audit"]["synthetic_sixth_constraint_attributed"] and not value["wrench_audit"]["rank5_contact_capability_attributed"] for value in acquisitions.values()), "all six")

        native = read_json(EVIDENCE / "SIM13_V4B4E_NATIVE_UNIT_CHECKS_V1.json")["runs"]
        add("B4EV29_ALL_ACQUISITION_CHECKS", all(all(value["acquisition"].values()) for value in native.values()), {key: all(value["acquisition"].values()) for key, value in native.items()})
        add("B4EV30_ALL_ACTIVE_CHECKS", all(all(value["active"].values()) for value in native.values()), {key: all(value["active"].values()) for key, value in native.items()})
        traces = read_json(EVIDENCE / "SIM13_V4B4E_ACTIVE_TRACES_V1.json")["runs"]
        add("B4EV31_ACTIVE_HORIZON_ALL_RUNS", all(abs(value["active_end_time_s"] - 0.08) <= 1.0e-14 for value in traces.values()), {key: value["active_end_time_s"] for key, value in traces.items()})
        add("B4EV32_NO_MAIN_REMOVAL_EXECUTED", all(value["synthetic_removal_executed"] is False for value in traces.values()), {key: value["synthetic_removal_executed"] for key, value in traces.items()})
        add("B4EV33_HORIZON_STATUS_INCONCLUSIVE", all(value["terminal_status"] == "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED" for value in traces.values()), {key: value["terminal_status"] for key, value in traces.items()})

        cross = read_json(EVIDENCE / "SIM13_V4B4E_CROSS_INTEGRATOR_LEDGER_V1.json")
        add("B4EV34_INDEPENDENT_ACQUISITION_TIMES", cross["forced_shared_acquisition_time"] is False and cross["primary_acquisition_time_s"] != cross["independent_acquisition_time_s"], {"primary": cross["primary_acquisition_time_s"], "independent": cross["independent_acquisition_time_s"]})
        add("B4EV35_ACQUISITION_TIME_GATE", cross["acquisition_event_gate_pass"] is True, cross["acquisition_event_time_difference_s"])
        add("B4EV36_REMOVAL_NOT_APPLICABLE", cross["removal_event_comparison"] == "NOT_EVALUATED_NO_FINITE_EVENT" and cross["both_horizon_exhausted_is_removal_capability_pass"] is False, cross["removal_event_comparison"])

        negative = read_json(EVIDENCE / "SIM13_V4B4E_NEGATIVE_CONTROLS_V1.json")
        add("B4EV37_NEGATIVE_COUNT", negative["count"] == negative["passed"] == 22, {"count": negative["count"], "passed": negative["passed"]})
        add("B4EV38_NEGATIVE_IDS_UNIQUE", len({item["id"] for item in negative["results"]}) == 22, [item["id"] for item in negative["results"]])
        negative_real = all(
            item["killed"] and item["affected_path_hit"]
            and item["expected_failed_check"] in item["actual_failed_checks"]
            and item["nominal_sha256"] != item["mutant_sha256"]
            and item["nominal_gate_output_sha256"] != item["mutant_gate_output_sha256"]
            and item["mutation_level"] in ("REAL_RAW_ARTIFACT_OR_EXECUTED_PATH", "EVERY_INDIVIDUAL_RAW_GOVERNANCE_FIELD")
            for item in negative["results"]
        )
        nc21 = next(item for item in negative["results"] if item["id"] == "B4NC21_PHYSICAL_OR_FORMAL_AUTHORITY_TRUE")
        nc22 = next(item for item in negative["results"] if item["id"] == "B4NC22_NULL_PHYSICAL_INPUT_ZERO_FILLED")
        add("B4EV39_NEGATIVE_PATHS_HIT", negative_real and nc21["subvariant_count"] == 8 and nc22["subvariant_count"] == 7 and all(item["killed"] for item in nc21["subvariants"] + nc22["subvariants"]), {"real_raw": negative_real, "nc21": nc21["subvariant_count"], "nc22": nc22["subvariant_count"]})

        fixture = read_json(EVIDENCE / "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json")
        fixture_event = fixture["fixture_event"]
        fixture_contract = contracts["PHASE_B4E_RUN_SPEC_V1.json"]["synthetic_removal_transition"]
        relative_removal_index = (
            float(fixture["clearance"]["removal_time_s"]) - float(fixture_event["time_s"])
        ) / float(fixture_event["step_s"])
        fixture_consistent = (
            "PERTURBED_FROM_HASH_BOUND_B3_EVENT" in fixture["scope"]
            and "NOT_MAIN_B3_TRAJECTORY" in fixture["scope"]
            and fixture["fixture_pass_does_not_set_main_synthetic_removal_executed"] is True
            and fixture["fixture_inputs_are_hardware_specifications"] is False
            and fixture["fixture_satisfies_main_b3_soft_capture_trigger"] is False
            and fixture["fixture_receives_physical_or_main_trigger_credit"] is False
            and fixture["fixture_contact_points_and_potentials_recomputed_from_perturbed_state"] is True
            and fixture_event["state_label"] == "ALGORITHM_ONLY_NONTRIGGER_INITIAL_STATE_FIXTURE"
            and fixture_event["criteria"]["soft_capture_transient_qualifies"] is False
            and fixture["synthetic_pre_acquisition_P_coordinate_offset_m"] == fixture_contract["synthetic_fixture_pre_acquisition_P_coordinate_offset_m"]
            and fixture["synthetic_pre_acquisition_P_velocity_m_s"] == fixture_contract["synthetic_fixture_pre_acquisition_P_velocity_m_s"]
            and abs(
                float(fixture["active_run"]["active_end_time_s"])
                - float(fixture_contract["synthetic_fixture_active_end_time_s"])
            ) <= 1.0e-14
            and fixture_contract["fixture_state_mutation_after_acquisition_forbidden"] is True
            and fixture_contract["fixture_clearance_must_come_from_same_active_state_trajectory"] is True
            and fixture_contract["fixture_removal_event_must_be_off_sample_grid"] is True
            and fixture_contract["fixture_must_execute_propagate_active_finite_event_branch"] is True
            and fixture_contract["fixture_satisfies_main_b3_soft_capture_trigger"] is False
            and fixture_contract["fixture_receives_physical_or_main_trigger_credit"] is False
            and fixture_contract["fixture_contact_points_and_potentials_must_be_recomputed_from_perturbed_state"] is True
            and fixture["no_state_mutation_after_acquisition"] is True
            and fixture["clearance_derived_from_same_active_state_trajectory"] is True
            and "COUNTERFACTUAL_ATTACHED_SEARCH_TRACE" in fixture["active_trace_semantics"]
            and fixture["same_active_trajectory_required_interval_s"] == [
                fixture_event["time_s"], fixture["clearance"]["removal_time_s"]
            ]
            and fixture["propagate_active_finite_event_branch_executed"] is True
            and fixture["exact_active_state_reconstructed_at_offgrid_removal_time"] is True
            and fixture["active_run"]["synthetic_removal_executed"] is True
            and fixture["active_run"]["post_release"] == fixture["post_release"]
            and abs(relative_removal_index - round(relative_removal_index)) > 1.0e-6
        )
        add("B4EV40_FIXTURE_NOT_MAIN", fixture_consistent, {"scope": fixture["scope"], "relative_removal_index": relative_removal_index})
        post = fixture["post_release"]; mapping = post["mapping"]
        service_zero = post["trace"]["service_state_29"][0]
        target_zero = post["trace"]["target_state_13"][0]
        post_z_zero = service_zero[15:29] + target_zero[7:13]
        native_slices = ((0, 3), (3, 6), (6, 12), (12, 14), (14, 17), (17, 20))
        first_state_bound = all(
            max(abs(float(post_z_zero[index]) - float(mapping["z_after"][index])) for index in range(start, stop)) <= 1.0e-12
            for start, stop in native_slices
        )
        zero_mapping = (
            mapping["z_before"] == mapping["z_after"]
            and all(float(value) <= 1.0e-12 for value in mapping["native_velocity_jump_maxima"].values())
            and first_state_bound
            and max(abs(value) for value in mapping["linear_impulse_N_s"]) <= 1.0e-12
            and max(abs(value) for value in mapping["angular_impulse_N_m_s"]) <= 1.0e-12
            and abs(mapping["kinetic_energy_jump_J"]) <= 1.0e-12
            and mapping["ideal_constraint_stored_energy_J"] == 0.0
            and post["post_release_passed"] is True
            and abs(post["observation_duration_s"] - 0.005) <= 1.0e-12
            and post["target_state_source_after_removal"] == "INDEPENDENT_13D_ZERO_EXTERNAL_FREE_FLIGHT"
        )
        add("B4EV41_ZERO_IMPULSE_MAPPING", zero_mapping, {"mapping": mapping["mapping_name"], "post_status": post["terminal_status"]})
        add("B4EV42_INTERNAL_GAP_TRAP", fixture["internal_negative_gap_trap"]["endpoint_gaps_above_threshold"] is True and fixture["internal_negative_gap_trap"]["certifier_returned_finite_event"] is False, fixture["internal_negative_gap_trap"])

        difference = read_json(EVIDENCE / "SIM13_V4B4E_DIFFERENCE_STEP_AUDIT_V1.json")
        add("B4EV43_DIFFERENCE_NOT_UNCERTAINTY", difference["classification"] == "NUMERICAL_DIRECTIONAL_DIFFERENCE_STEP_AUDIT_NOT_MEASUREMENT_UNCERTAINTY", difference["classification"])
        campaign = read_json(RESULTS / "SIM13_V4B4E_CAMPAIGN_SUMMARY_V1.json")
        add("B4EV44_CAMPAIGN_CHECKS", campaign["all_event_local_and_active_checks_pass"] is True and campaign["negative_controls_22_real_raw_mutations_killed"] is True and campaign["b4_hybrid_removal_and_post_release_solver_implemented"] is True and campaign["main_branch_removal_or_release_capability_pass"] is False, campaign)
        add("B4EV45_FORMAL_STATE_UNCHANGED", campaign["formal_sim13_v2"] == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]}, campaign["formal_sim13_v2"])
        add("B4EV46_NO_PHYSICAL_CURRENT_FORMAL_CREDIT", campaign["physical_or_current_formal_credit"] is False, campaign["physical_or_current_formal_credit"])
        add("B4EV47_PRIMARY_OUTCOME_SEPARATED", campaign["primary_terminal_status"] == "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED" and campaign["primary_synthetic_removal_executed"] is False and campaign["bounded_horizon_global_no_event_claim"] is False, campaign["primary_terminal_status"])
        source_after = campaign_module.source_inventory()
        add("B4EV48_TOCTOU_SOURCE_STABLE", source_before == source_after == manifest["sources"], "before == after == manifest")

    except Exception as error:
        add("B4EV_FATAL", False, f"{type(error).__name__}:{error}")

    passed_count = sum(item["passed"] for item in checks)
    exact_inventory = len(checks) == 48
    validation = {
        "schema": "SIM13_V4B4E_VALIDATION_V1",
        "status": "PASS" if exact_inventory and passed_count == 48 else "FAIL",
        "expected_checks": 48, "observed_checks": len(checks), "passed_checks": passed_count,
        "failed_check_ids": [item["id"] for item in checks if not item["passed"]],
        "pytest": locals().get("tests") and {
            "return_code": tests.returncode, "collected": locals().get("total"), "passed": locals().get("passed"),
            "failed": locals().get("failures"), "errors": locals().get("errors"), "skipped": locals().get("skipped"),
            "nodeid_sha256": locals().get("node_payload") and hashlib.sha256(node_payload).hexdigest().upper(),
        },
        "checks": checks,
    }
    write_json(VALIDATION_PATH, validation)
    if validation["status"] != "PASS":
        if EVIDENCE_MANIFEST_PATH.is_file(): EVIDENCE_MANIFEST_PATH.unlink()
        if PRE_AUDIT_GATE_PATH.is_file(): PRE_AUDIT_GATE_PATH.unlink()
        cleanup_final_artifacts()
        print(json.dumps(validation, indent=2, ensure_ascii=False))
        return 2

    evidence_records: list[dict[str, Any]] = []
    roles = {
        "SIM13_V4B4E_RUNTIME_ENVIRONMENT_V1.json": "RUNTIME_ENVIRONMENT",
        "SIM13_V4B4E_EVENT_INPUTS_V1.json": "SIX_INDEPENDENT_TRIGGER_INPUTS",
        "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json": "EVENT_LOCAL_MATRICES_IMPULSE_MOMENTUM_ENERGY",
        "SIM13_V4B4E_ACTIVE_TRACES_V1.json": "SIX_SAMPLEWISE_ACTIVE_TRAJECTORIES",
        "SIM13_V4B4E_NATIVE_UNIT_CHECKS_V1.json": "NATIVE_UNIT_ACCEPTANCE_RESULTS",
        "SIM13_V4B4E_CROSS_INTEGRATOR_LEDGER_V1.json": "CROSS_INTEGRATOR_EVENTS_AND_OUTCOME",
        "SIM13_V4B4E_NEGATIVE_CONTROLS_V1.json": "TWENTY_TWO_REAL_RAW_OR_EXECUTED_PATH_KILLED_MUTANTS",
        "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json": "NON_MAIN_COMPLETE_HYBRID_REMOVAL_FIXTURE",
        "SIM13_V4B4E_DIFFERENCE_STEP_AUDIT_V1.json": "NUMERICAL_DIFFERENCE_STEP_AUDIT",
        "SIM13_V4B4E_SOURCE_MANIFEST_V1.json": "SOURCE_DAG_ROOT",
        "SIM13_V4B4E_VALIDATION_V1.json": "VALIDATOR_48_OF_48",
    }
    for name, role in roles.items():
        evidence_records.append(file_record(EVIDENCE / name, role))
    evidence_records.append(file_record(RESULTS / "SIM13_V4B4E_CAMPAIGN_SUMMARY_V1.json", "CAMPAIGN_SUMMARY"))
    evidence_manifest = {
        "schema": "SIM13_V4B4E_EVIDENCE_MANIFEST_V1", "self_excluded": True,
        "file_count": len(evidence_records), "files": sorted(evidence_records, key=lambda item: item["path"]),
    }
    write_json(EVIDENCE_MANIFEST_PATH, evidence_manifest)
    governance = read_json(PHASE_ROOT / "contracts" / "PHASE_B4E_GOVERNANCE_V1.json")
    pre_audit = {
        "schema": "SIM13_V4B4E_PRE_AUDIT_GATE_V1",
        "status": "PASS_PHASE_B4E_SOLVER_VALIDATION_PRE_AUDIT__SYNTHETIC_ACQUISITION_ACTIVE_AND_ALGORITHM_ONLY_NONTRIGGER_HYBRID_BRANCH_VERIFIED__PRIMARY_BRANCH_HORIZON_EXHAUSTED_INCONCLUSIVE__NO_MAIN_REMOVAL__ALL_PHYSICAL_CURRENT_FORMAL_HOLDS",
        "final": False,
        "validation": file_record(VALIDATION_PATH, "VALIDATOR_48_OF_48"),
        "evidence_manifest": file_record(EVIDENCE_MANIFEST_PATH, "EVIDENCE_DAG"),
        "capability_state": {
            "b4_contract_recursively_verified": True,
            "b4_acquisition_and_active_solver_implemented": True,
            "b4_clearance_eligibility_certifier_implemented": True,
            "b4_hybrid_removal_and_post_release_solver_implemented": True,
            "b4_solver_audited": False,
            "synthetic_acquisition_executed": True,
            "synthetic_active_constraint_propagated": True,
            "cross_integrator_checked": True,
            "solver_negative_controls_22_real_raw_mutations_killed": True,
            "synthetic_removal_executed": False,
            "algorithm_only_hybrid_removal_fixture_passed": True,
        },
        "nominal_branch": {
            "status": "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED",
            "search_end_time_s": 0.08,
            "global_no_event_claim": False,
            "release_capability_pass": False,
        },
        "required_false": governance["required_false"],
        "required_null_physical_inputs": {name: None for name in governance["required_null_physical_inputs"]},
        "formal_sim13_v2_state_unchanged": governance["formal_sim13_v2_state_unchanged"],
        "next_action": "independent audit; main-branch release remains HOLD unless a separately preregistered extension or analytic reachability proof produces a finite earliest event",
    }
    write_json(PRE_AUDIT_GATE_PATH, pre_audit)
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
