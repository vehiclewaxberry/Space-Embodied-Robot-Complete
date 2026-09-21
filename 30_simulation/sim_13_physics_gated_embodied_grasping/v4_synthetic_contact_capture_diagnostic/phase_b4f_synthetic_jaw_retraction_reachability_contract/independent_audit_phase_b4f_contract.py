from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


# Independence rule: this module does not import the B4F validator, its tests, or any dynamics solver.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CONTRACTS = HERE / "contracts"
EVIDENCE = HERE / "evidence"
RESULTS = HERE / "results"

AUTHORIZATION = CONTRACTS / "PHASE_B4F_WORK_AUTHORIZATION_V1.json"
MODEL = CONTRACTS / "PHASE_B4F_MODEL_AND_ENERGY_CONTRACT_V1.json"
EXPERIMENT = CONTRACTS / "PHASE_B4F_EXPERIMENT_DESIGN_V1.json"
NUMERICAL = CONTRACTS / "PHASE_B4F_NUMERICAL_ACCEPTANCE_V1.json"
GOVERNANCE = CONTRACTS / "PHASE_B4F_GOVERNANCE_V1.json"
BINDINGS = CONTRACTS / "PHASE_B4F_SOURCE_BINDINGS_V1.json"
EVIDENCE_SCHEMA = CONTRACTS / "PHASE_B4F_EVIDENCE_SCHEMA_V1.json"
TEST_INVENTORY = CONTRACTS / "PHASE_B4F_TEST_INVENTORY_V1.json"
SOURCE_VERIFICATION = EVIDENCE / "SIM13_V4B4F_SOURCE_VERIFICATION_V1.json"
VALIDATION = EVIDENCE / "SIM13_V4B4F_CONTRACT_VALIDATION_V1.json"
EVIDENCE_MANIFEST = EVIDENCE / "SIM13_V4B4F_CONTRACT_EVIDENCE_MANIFEST_V1.json"
AUDIT_RECEIPT = EVIDENCE / "SIM13_V4B4F_CONTRACT_AUDIT_RECEIPT_V1.json"
FINAL_GATE = RESULTS / "SIM13_V4B4F_CONTRACT_AUDITED_GATE_V1.json"
TERMINAL_MANIFEST = RESULTS / "SIM13_V4B4F_CONTRACT_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"

FROZEN_B4_TERMINAL_SHA = "09D26114D50358FD488BF51912C68FDB3993AB0035201B22478D7CD9A9B7B76E"
FROZEN_B4_GATE_SHA = "55441DFF42C92235B14DF9C810B013ADC2E59D5607D7697A5D85795149431D92"
EXPECTED_BINDINGS = {
    "b4e_audited_gate": ("30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/results/SIM13_V4B4E_AUDITED_GATE_V1.json", "PARENT_AUDITED_CAPABILITY_AND_HOLD_BOUNDARY"),
    "b4e_terminal_manifest": ("30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/results/SIM13_V4B4E_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json", "PARENT_RECURSIVE_EVIDENCE_ROOT"),
    "b4e_solver_source": ("30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/b4_solver/constraint_solver.py", "PARENT_ACTIVE_REMOVAL_AND_POST_RELEASE_IMPLEMENTATION"),
    "b4e_run_spec": ("30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/contracts/PHASE_B4E_RUN_SPEC_V1.json", "PARENT_ALGORITHMIC_TOLERANCES_AND_HYBRID_TRANSITION"),
    "b4e_hybrid_fixture": ("30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/evidence/SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json", "PARENT_COMPLETE_ALGORITHM_ONLY_HYBRID_REMOVAL_FIXTURE"),
    "b4_model_contract": ("30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_synthetic_6d_constraint_acquisition_release/contracts/PHASE_B4_MODEL_CONTRACT_V1.json", "FROZEN_ACQUISITION_ACTIVE_AND_REMOVAL_MODEL"),
    "b4_numerical_contract": ("30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_synthetic_6d_constraint_acquisition_release/contracts/PHASE_B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1.json", "FROZEN_NATIVE_UNIT_ACCEPTANCE"),
}
PASS_STATUS = (
    "PASS_PHASE_B4F_CONTRACT_FREEZE_AUDIT_ONLY__SYNTHETIC_P_ONLY_JAW_RETRACTION_"
    "REACHABILITY_CAMPAIGN_PREREGISTERED__SOLVER_NOT_IMPLEMENTED__CAMPAIGN_NOT_EXECUTED__"
    "ALL_PHYSICAL_CURRENT_FORMAL_OWNER_PRODUCTION_HOLDS"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _record(path: Path, role: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(), "role": role,
        "bytes": path.stat().st_size, "sha256": _sha(path),
    }


def _resolve(path_text: str, base: Path) -> Path:
    path = Path(path_text)
    if path.parts and path.parts[0] in {
        "01_project", "10_research", "20_engineering", "30_simulation", "40_evidence",
        "50_literature", "70_tools", "80_third_party",
    }:
        return ROOT / path
    return base / path


def _matches(row: dict[str, Any], base: Path) -> bool:
    path = _resolve(str(row.get("path", "")), base)
    return (
        path.is_file()
        and path.stat().st_size == row.get("bytes")
        and _sha(path) == row.get("sha256")
        and bool(re.fullmatch(r"[0-9A-F]{64}", str(row.get("sha256", ""))))
    )


def _recursive_parent_audit(bindings: dict[str, Any]) -> dict[str, Any]:
    sources = bindings.get("sources", [])
    by_id = {row.get("id"): row for row in sources}
    bound_ok = (
        set(by_id) == set(EXPECTED_BINDINGS)
        and all((by_id[key].get("path"), by_id[key].get("role")) == expected for key, expected in EXPECTED_BINDINGS.items())
        and all(_matches(row, ROOT) for row in sources)
    )

    terminal_path = _resolve(str(by_id.get("b4e_terminal_manifest", {}).get("path", "")), ROOT)
    b4e_root = terminal_path.parents[1] if terminal_path.is_file() else HERE
    terminal = _load(terminal_path) if terminal_path.is_file() else {}
    terminal_ok = (
        terminal.get("schema") == "SIM13_V4B4E_TERMINAL_SELF_EXCLUDED_MANIFEST_V1"
        and terminal.get("self_excluded") is True
        and terminal_path.resolve() not in {
            _resolve(str(row.get("path", "")), b4e_root).resolve()
            for row in terminal.get("entries", [])
        }
        and len(terminal.get("entries", [])) >= 4
        and all(_matches(row, b4e_root) for row in terminal.get("entries", []))
    )

    evidence_row = next((row for row in terminal.get("entries", []) if row.get("role") == "EVIDENCE_DAG"), {})
    evidence_path = _resolve(str(evidence_row.get("path", "")), b4e_root)
    evidence = _load(evidence_path) if evidence_path.is_file() else {}
    evidence_ok = (
        evidence.get("schema") == "SIM13_V4B4E_EVIDENCE_MANIFEST_V1"
        and evidence.get("self_excluded") is True
        and evidence_path.resolve() not in {
            _resolve(str(row.get("path", "")), b4e_root).resolve()
            for row in evidence.get("files", [])
        }
        and evidence.get("file_count") == len(evidence.get("files", []))
        and len(evidence.get("files", [])) >= 10
        and all(_matches(row, b4e_root) for row in evidence.get("files", []))
    )

    source_row = next((row for row in evidence.get("files", []) if row.get("role") == "SOURCE_DAG_ROOT"), {})
    source_path = _resolve(str(source_row.get("path", "")), b4e_root)
    source = _load(source_path) if source_path.is_file() else {}
    source_ok = (
        source.get("schema") == "SIM13_V4B4E_SOURCE_MANIFEST_V1"
        and source.get("self_excluded") is True
        and source_path.resolve() not in {
            _resolve(str(row.get("path", "")), ROOT).resolve()
            for row in source.get("sources", [])
        }
        and source.get("source_count") == len(source.get("sources", []))
        and len(source.get("sources", [])) >= 20
        and all(_matches(row, ROOT) for row in source.get("sources", []))
    )

    b4_terminal_row = next((row for row in source.get("sources", []) if row.get("id") == "b4_contract_terminal_manifest"), {})
    b4_gate_row = next((row for row in source.get("sources", []) if row.get("id") == "b4_contract_audited_gate"), {})
    b4_terminal_path = _resolve(str(b4_terminal_row.get("path", "")), ROOT)
    b4_gate_path = _resolve(str(b4_gate_row.get("path", "")), ROOT)
    b4_terminal = _load(b4_terminal_path) if b4_terminal_path.is_file() else {}
    b4_gate = _load(b4_gate_path) if b4_gate_path.is_file() else {}
    frozen_b4_ok = (
        b4_terminal_row.get("sha256") == FROZEN_B4_TERMINAL_SHA
        and b4_gate_row.get("sha256") == FROZEN_B4_GATE_SHA
        and b4_terminal_path.is_file() and _sha(b4_terminal_path) == FROZEN_B4_TERMINAL_SHA
        and b4_gate_path.is_file() and _sha(b4_gate_path) == FROZEN_B4_GATE_SHA
        and b4_terminal.get("self_excluded") is True and b4_terminal.get("acyclic") is True
        and b4_terminal_path.resolve() not in {
            _resolve(str(row.get("path", "")), ROOT).resolve()
            for row in b4_terminal.get("records", [])
        }
        and len(b4_terminal.get("records", [])) == 2
        and all(_matches(row, ROOT) for row in b4_terminal.get("records", []))
        and b4_gate.get("final_gate") is True
        and str(b4_gate.get("overall_status", "")).startswith("PASS_PHASE_B4_CONTRACT_FREEZE_ONLY")
    )

    b4e_gate_path = _resolve(str(by_id.get("b4e_audited_gate", {}).get("path", "")), ROOT)
    b4e_gate = _load(b4e_gate_path) if b4e_gate_path.is_file() else {}
    b4e_boundary_ok = (
        b4e_gate.get("final") is True
        and str(b4e_gate.get("status", "")).startswith("PASS_PHASE_B4E_SOLVER_AUDIT")
        and b4e_gate.get("nominal_branch", {}).get("removal_or_release_capability_pass") is False
        and b4e_gate.get("formal_sim13_v2_state_unchanged") == {
            "passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]
        }
        and b4e_gate.get("required_false")
        and all(value is False for value in b4e_gate["required_false"].values())
    )
    return {
        "pass": all([bound_ok, terminal_ok, evidence_ok, source_ok, frozen_b4_ok, b4e_boundary_ok]),
        "bound_sources_pass": bound_ok, "b4e_terminal_pass": terminal_ok,
        "b4e_evidence_pass": evidence_ok, "b4e_source_dag_pass": source_ok,
        "frozen_b4_terminal_pass": frozen_b4_ok, "b4e_claim_boundary_pass": b4e_boundary_ok,
        "b4e_terminal_entry_count": len(terminal.get("entries", [])),
        "b4e_evidence_record_count": len(evidence.get("files", [])),
        "b4e_source_record_count": len(source.get("sources", [])),
    }


def main() -> int:
    required_paths = [
        AUTHORIZATION, MODEL, EXPERIMENT, NUMERICAL, GOVERNANCE, BINDINGS, EVIDENCE_SCHEMA,
        TEST_INVENTORY, SOURCE_VERIFICATION, VALIDATION, EVIDENCE_MANIFEST,
    ]
    missing = [str(path) for path in required_paths if not path.is_file()]
    if missing:
        print(json.dumps({"status": "FAIL_MISSING_PREDECESSOR", "missing": missing}, ensure_ascii=False))
        return 1

    authorization = _load(AUTHORIZATION)
    model = _load(MODEL)
    experiment = _load(EXPERIMENT)
    numerical = _load(NUMERICAL)
    governance = _load(GOVERNANCE)
    bindings = _load(BINDINGS)
    schema = _load(EVIDENCE_SCHEMA)
    inventory = _load(TEST_INVENTORY)
    source_verification = _load(SOURCE_VERIFICATION)
    validation = _load(VALIDATION)
    evidence_manifest = _load(EVIDENCE_MANIFEST)
    recursive = _recursive_parent_audit(bindings)
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"id": f"B4FA{len(checks) + 1:02d}", "name": name, "pass": bool(condition), "detail": detail})

    check("contract schemas independently parsed", all([
        authorization.get("schema") == "SIM13_V4B4F_WORK_AUTHORIZATION_V1",
        model.get("schema") == "SIM13_V4B4F_MODEL_AND_ENERGY_CONTRACT_V1",
        experiment.get("schema") == "SIM13_V4B4F_EXPERIMENT_DESIGN_V1",
        numerical.get("schema") == "SIM13_V4B4F_NUMERICAL_ACCEPTANCE_V1",
        governance.get("schema") == "SIM13_V4B4F_GOVERNANCE_V1",
        bindings.get("schema") == "SIM13_V4B4F_SOURCE_BINDINGS_V1",
        schema.get("schema") == "SIM13_V4B4F_EVIDENCE_SCHEMA_V1",
    ]))
    check("all top-level source bindings rehashed", recursive["bound_sources_pass"])
    check("B4E terminal manifest recursively rehashed", recursive["b4e_terminal_pass"], recursive["b4e_terminal_entry_count"])
    check("B4E evidence manifest recursively rehashed", recursive["b4e_evidence_pass"], recursive["b4e_evidence_record_count"])
    check("B4E source DAG recursively rehashed", recursive["b4e_source_dag_pass"], recursive["b4e_source_record_count"])
    check("frozen B4 terminal and Gate remain byte-identical", recursive["frozen_b4_terminal_pass"])
    check("B4E final claim boundary retains all holds", recursive["b4e_claim_boundary_pass"])

    local_records = source_verification.get("local_sources", [])
    check("source verification local sources independently rehashed", source_verification.get("self_excluded") is True and source_verification.get("local_source_count") == len(local_records) and len(local_records) >= 18 and all(_matches(row, HERE) for row in local_records))
    check("source verification reports recursive PASS", source_verification.get("status") == "PASS_RECURSIVE_SOURCE_VERIFICATION" and source_verification.get("recursive_parent_verification", {}).get("pass") is True and recursive["pass"])

    evidence_records = evidence_manifest.get("records", [])
    evidence_paths = {row.get("path") for row in evidence_records}
    check("evidence manifest is acyclic and self-excluded", evidence_manifest.get("schema") == "SIM13_V4B4F_CONTRACT_EVIDENCE_MANIFEST_V1" and evidence_manifest.get("self_excluded") is True and evidence_manifest.get("acyclic") is True and evidence_manifest.get("record_count") == 2 and len(evidence_records) == 2 and all(_matches(row, ROOT) for row in evidence_records) and EVIDENCE_MANIFEST.relative_to(ROOT).as_posix() not in evidence_paths)

    expected_validator_total = inventory["validator"]["expected_checks"]
    check("validator output exact all-pass score", validation.get("schema") == "SIM13_V4B4F_CONTRACT_VALIDATION_V1" and validation.get("status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" and validation.get("score") == {"pass": expected_validator_total, "fail": 0, "total": expected_validator_total, "failed": []} and len(validation.get("checks", [])) == expected_validator_total and all(row.get("pass") is True for row in validation.get("checks", [])))
    pytest_result = validation.get("pytest", {})
    expected_pytest = inventory["pytest"]
    audited_nodeids = pytest_result.get("nodeids", [])
    audited_nodeid_sha256 = hashlib.sha256("\n".join(audited_nodeids).encode("utf-8")).hexdigest().upper()
    check("pytest nodeid inventory exact", pytest_result.get("collect_returncode") == 0 and pytest_result.get("collected") == expected_pytest["expected_collected"] and pytest_result.get("nodeid_sha256") == expected_pytest["expected_nodeid_sha256"] and audited_nodeid_sha256 == expected_pytest["expected_nodeid_sha256"] and len(audited_nodeids) == expected_pytest["expected_collected"])
    check("pytest outcomes exact", pytest_result.get("run_returncode") == 0 and pytest_result.get("outcomes") == expected_pytest["required_outcome"])
    passed_match = re.search(r"(\d+) passed", str(pytest_result.get("stdout", "")))
    independently_parsed_passed = int(passed_match.group(1)) if passed_match else 0
    check("pytest stdout independently parsed", independently_parsed_passed == expected_pytest["required_outcome"]["passed"] and " failed" not in str(pytest_result.get("stdout", "")) and " error" not in str(pytest_result.get("stdout", "")).lower())
    check("validator capability state remains unimplemented", validation.get("implementation_state") == {"b4f_solver_implemented": False, "b4f_campaign_executed": False, "synthetic_reachability_passed": False, "future_negative_controls_executed": False})

    auth = authorization["authorized"]
    check("authorization is contract-only", auth.get("freeze_contracts_and_test_contracts") is True and auth.get("bind_parent_sources_and_evidence") is True and auth.get("implement_or_execute_b4f_solver") is False and auth.get("modify_b4_or_b4e") is False and auth.get("modify_or_generate_urdf") is False and auth.get("bind_current_system_interface") is False and all(value is False for value in authorization["authority_boundary"].values()))
    check("authorization hash follows current B4E Gate", authorization["basis"]["parent_b4e_audited_gate_sha256"] == next(row for row in bindings["sources"] if row["id"] == "b4e_audited_gate")["sha256"])

    equation = model["active_equation"]
    check("P-only 14D internal effort", equation["Q_a_shape"] == 14 and equation["allowed_nonzero_indices_zero_based"] == [12, 13] and equation["all_base_and_R_joint_applied_efforts_exact_zero"] is True and equation["contact_kernel_enabled_while_synthetic_constraint_active"] is False)
    ledger = model["actuator_work_ledger"]
    check("signed work and energy-minus-work ledger", "W_act_dot=P_act" in ledger["primary_integration"] and "-W_act" in ledger["active_energy_identity"] and ledger["dissipated_energy_return_on_removal"] is False and ledger["actuator_work_reset_on_removal"] is False)
    domain = model["synthetic_geometry_validity_domain"]
    check("exact fail-closed synthetic geometry domain", domain["left_P_coordinate_m_closed_interval"] == [0.0, 0.0715] and domain["right_P_coordinate_m_closed_interval"] == [0.0, 0.0715] and domain["evaluation"] == "every accepted integrator stage, stored sample and exact event state" and domain["exit_action"] == "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN" and domain["extrapolation_or_clipping_forbidden"] is True)
    removal = model["removal_transition"]
    check("exact zero-jump removal and independent post-release frozen", "componentwise copy" in removal["mapping"] and removal["post_release_observation_s"] == 0.005 and removal["post_release_contact_kernel_enabled"] is False and removal["post_release_actuator_generalized_force"] == "exact_zero")

    arms = {row["id"]: row for row in experiment["arms"]}
    check("A0 A1 A2 design frozen", set(arms) == {"A0_ZERO_INPUT_EXACT_REPLAY", "A1_SYMMETRIC_BRAKE_OPEN", "A2_ASYMMETRIC_LAG_AND_ONE_SIDE_LOSS"} and arms["A0_ZERO_INPUT_EXACT_REPLAY"]["alpha_left"] == 0.0 and arms["A1_SYMMETRIC_BRAKE_OPEN"]["alpha_levels_dimensionless"] == [0.5, 1.0, 2.0, 4.0, 8.0, 16.0] and arms["A1_SYMMETRIC_BRAKE_OPEN"]["command_duration_levels_s"] == [0.005, 0.01, 0.02] and len(arms["A2_ASYMMETRIC_LAG_AND_ONE_SIDE_LOSS"]["variants"]) == 4)
    selector = experiment["primary_case_selector"]
    check("discrete reporting cannot become minimum required", selector["reported_label"] == "lowest_tested_reachable_alpha_in_registered_discrete_grid" and selector["minimum_required_force_or_work_claim_authorized"] is False and selector["between_level_interpolation_or_inverse_threshold_estimation_authorized"] is False)
    check("future 22 negative controls registered but not executed", len(numerical["required_negative_controls"]) == 22 and len(set(numerical["required_negative_controls"])) == 22 and numerical["required_negative_controls"][0].startswith("B4FNC01_") and numerical["required_negative_controls"][-1].startswith("B4FNC22_") and validation["implementation_state"]["future_negative_controls_executed"] is False)

    check("all required capability states false", set(governance["required_false"]) == {
        "b4f_solver_implemented", "b4f_campaign_executed", "synthetic_reachability_passed",
        "minimum_required_synthetic_force_identified", "physical_actuator_force_identified",
        "physical_actuator_timing_identified", "physical_release_implemented",
        "physical_recontact_implemented", "held_capture_passed", "grasp_success_claimed",
        "current_system_bound", "formal_nc19_credit", "owner_authorized", "production_ready",
        "release_authorized", "next_stage_authorized", "hardware_specification_released",
        "physical_gripper_stroke_identified", "measurement_uncertainty_model_available",
    } and all(value is False for value in governance["required_false"].values()))
    check("all physical inputs remain null", len(governance["required_null_physical_inputs"]) == 11 and len(set(governance["required_null_physical_inputs"])) == 11)
    check("formal Sim13 V2 remains 15 of 20", governance["formal_sim13_v2_state_unchanged"] == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]})
    memory = governance["memory_governance"]
    check("memory is diagnostic only with no gate or override", memory["unified_r2_or_v5_cad_memory_gate_applicable"] is False and memory["memory_gate_credit_allowed"] is False and memory["historical_owner_override_reuse_allowed"] is False and memory["future_b4f_run_records_memory_as_diagnostic_only"] is True)
    names = {path.name for path in HERE.rglob("*") if path.is_file()}
    check("no URDF interface execution lock or release marker", not any(name.endswith(".urdf") for name in names) and all(name not in names for name in governance["forbidden_artifacts"][1:]))
    check("publication DAG self-exclusion contract exact", schema["self_exclusion"] == {"evidence_manifest_self_excluded": True, "terminal_manifest_self_excluded": True} and schema["publication_order"][-1] == TERMINAL_MANIFEST.name)

    expected_audit_total = inventory["independent_audit"]["expected_checks"]
    count_contract_ok = len(checks) == expected_audit_total
    if not count_contract_ok:
        checks.append({"id": f"B4FA{len(checks) + 1:02d}", "name": "audit inventory count contract", "pass": False, "detail": {"actual_before_count_check": len(checks), "expected": expected_audit_total}})
    failed = [row["id"] for row in checks if not row["pass"]]
    receipt = {
        "schema": "SIM13_V4B4F_CONTRACT_AUDIT_RECEIPT_V1",
        "status": "PASS_INDEPENDENT_CONTRACT_AUDIT" if not failed else "FAIL_INDEPENDENT_CONTRACT_AUDIT",
        "scope": "CONTRACT_FREEZE_ONLY_NO_SOLVER_OR_CAMPAIGN_EXECUTION",
        "independence": {
            "imports_b4f_validator": False, "imports_b4f_tests": False,
            "imports_b4f_or_b4e_dynamics_solver": False,
            "reads_json_and_rehashes_with_hashlib": True,
        },
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "recursive_parent_audit": recursive,
    }
    _atomic_json(AUDIT_RECEIPT, receipt)
    if failed:
        print(json.dumps({"status": receipt["status"], "score": receipt["score"]}, ensure_ascii=False))
        return 1

    required_null = {key: None for key in governance["required_null_physical_inputs"]}
    final_gate = {
        "schema": "SIM13_V4B4F_CONTRACT_AUDITED_GATE_V1",
        "status": PASS_STATUS,
        "final": True,
        "scope": "CONTRACT_FREEZE_AND_AUDIT_ONLY_NO_SOLVER_NO_CAMPAIGN",
        "hash_chain": {
            "source_verification": _record(SOURCE_VERIFICATION, "B4F_RECURSIVE_SOURCE_VERIFICATION"),
            "validation": _record(VALIDATION, "B4F_CONTRACT_VALIDATION"),
            "evidence_manifest": _record(EVIDENCE_MANIFEST, "B4F_CONTRACT_EVIDENCE_DAG"),
            "independent_audit_receipt": _record(AUDIT_RECEIPT, "B4F_INDEPENDENT_CONTRACT_AUDIT"),
        },
        "contract_capability_state": {
            "b4f_contract_frozen": True,
            "b4f_contract_audited": True,
            "parent_b4e_recursively_verified": True,
        },
        "implementation_and_campaign_state": {
            "b4f_solver_implemented": False,
            "b4f_campaign_executed": False,
            "future_negative_controls_executed": False,
            "synthetic_reachability_passed": False,
            "lowest_tested_reachable_alpha": None,
            "minimum_required_synthetic_force_identified": False,
        },
        "preregistered_domain": {
            "generalized_force_shape": 14,
            "allowed_nonzero_indices_zero_based": [12, 13],
            "signed_actuator_work_required": True,
            "arms": ["A0_ZERO_INPUT_EXACT_REPLAY", "A1_SYMMETRIC_BRAKE_OPEN", "A2_ASYMMETRIC_LAG_AND_ONE_SIDE_LOSS"],
            "left_P_coordinate_m_closed_interval": [0.0, 0.0715],
            "right_P_coordinate_m_closed_interval": [0.0, 0.0715],
            "out_of_domain_action": "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN",
            "future_negative_control_count": 22,
            "reporting_boundary": "LOWEST_TESTED_ONLY__NO_MINIMUM_REQUIRED_FORCE_OR_INTERPOLATION",
        },
        "required_false": governance["required_false"],
        "required_null_physical_inputs": required_null,
        "formal_sim13_v2_state_unchanged": governance["formal_sim13_v2_state_unchanged"],
        "memory_record": {
            "memory_gate_applicable": False,
            "memory_gate_passed": False,
            "owner_override_used": False,
            "classification": "DIAGNOSTIC_ONLY",
        },
        "mechanical_ruling": "B4F synthetic P-only jaw-retraction reachability contracts are frozen and recursively audited; no B4F solver or campaign has been executed, no reachable level has been observed, and no synthetic command can be promoted to a physical actuator, stroke, lock, release, current-system, formal NC19, Owner, production or next-stage claim",
        "next_action": "implement only under a separate post-freeze authorization, execute the exact preregistered A0/A1/A2 domain without horizon or grid extension, and report at most the lowest tested reachable discrete alpha",
    }
    _atomic_json(FINAL_GATE, final_gate)
    terminal = {
        "schema": "SIM13_V4B4F_CONTRACT_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
        "self_excluded": True,
        "acyclic": True,
        "records": [
            _record(EVIDENCE_MANIFEST, "B4F_CONTRACT_EVIDENCE_DAG"),
            _record(AUDIT_RECEIPT, "B4F_INDEPENDENT_CONTRACT_AUDIT"),
            _record(FINAL_GATE, "B4F_CONTRACT_FINAL_AUDITED_GATE"),
        ],
    }
    _atomic_json(TERMINAL_MANIFEST, terminal)
    print(json.dumps({"status": final_gate["status"], "audit_score": receipt["score"], "final_gate_sha256": _sha(FINAL_GATE), "terminal_sha256": _sha(TERMINAL_MANIFEST)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
