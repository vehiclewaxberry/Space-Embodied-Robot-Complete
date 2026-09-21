from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


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

FROZEN_B4_TERMINAL_SHA = "09D26114D50358FD488BF51912C68FDB3993AB0035201B22478D7CD9A9B7B76E"
FROZEN_B4_GATE_SHA = "55441DFF42C92235B14DF9C810B013ADC2E59D5607D7697A5D85795149431D92"
EXPECTED_BINDING_IDS = {
    "b4e_audited_gate", "b4e_terminal_manifest", "b4e_solver_source", "b4e_run_spec",
    "b4e_hybrid_fixture", "b4_model_contract", "b4_numerical_contract",
}
EXPECTED_BINDING_PATHS_AND_ROLES = {
    "b4e_audited_gate": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/results/SIM13_V4B4E_AUDITED_GATE_V1.json",
        "PARENT_AUDITED_CAPABILITY_AND_HOLD_BOUNDARY",
    ),
    "b4e_terminal_manifest": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/results/SIM13_V4B4E_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json",
        "PARENT_RECURSIVE_EVIDENCE_ROOT",
    ),
    "b4e_solver_source": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/b4_solver/constraint_solver.py",
        "PARENT_ACTIVE_REMOVAL_AND_POST_RELEASE_IMPLEMENTATION",
    ),
    "b4e_run_spec": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/contracts/PHASE_B4E_RUN_SPEC_V1.json",
        "PARENT_ALGORITHMIC_TOLERANCES_AND_HYBRID_TRANSITION",
    ),
    "b4e_hybrid_fixture": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/evidence/SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json",
        "PARENT_COMPLETE_ALGORITHM_ONLY_HYBRID_REMOVAL_FIXTURE",
    ),
    "b4_model_contract": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_synthetic_6d_constraint_acquisition_release/contracts/PHASE_B4_MODEL_CONTRACT_V1.json",
        "FROZEN_ACQUISITION_ACTIVE_AND_REMOVAL_MODEL",
    ),
    "b4_numerical_contract": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_synthetic_6d_constraint_acquisition_release/contracts/PHASE_B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1.json",
        "FROZEN_NATIVE_UNIT_ACCEPTANCE",
    ),
}
EXPECTED_NC = [
    "B4FNC01_PARENT_SOURCE_BYTE_DRIFT", "B4FNC02_A0_NONZERO_FORCE",
    "B4FNC03_FORCE_OUTSIDE_P_CHANNELS", "B4FNC04_OPENING_SIGN_REVERSED",
    "B4FNC05_ACTUATOR_WORK_OMITTED", "B4FNC06_ACTUATOR_WORK_DOUBLE_COUNTED",
    "B4FNC07_WORK_RESET_AT_REMOVAL", "B4FNC08_COMMAND_ACTIVE_DURING_CLEARANCE_DWELL",
    "B4FNC09_SINGLE_SIDE_CLEARANCE_ACCEPTED", "B4FNC10_ENDPOINT_ONLY_CLEARANCE",
    "B4FNC11_REMOVAL_RESTORES_PRE_ACQUISITION_TWIST",
    "B4FNC12_REMOVAL_RETURNS_DISSIPATED_ENERGY",
    "B4FNC13_POST_RELEASE_TARGET_STILL_SNAPSHOT_DERIVED",
    "B4FNC14_POST_RELEASE_CONTACT_REACTIVATED", "B4FNC15_SHARED_EVENT_TIME_FORCED",
    "B4FNC16_PARAMETER_DOMAIN_EXTENDED_AFTER_RESULTS",
    "B4FNC17_A2_LEFT_RIGHT_MIRROR_BROKEN",
    "B4FNC18_SYNTHETIC_FORCE_PROMOTED_TO_HARDWARE_SPEC",
    "B4FNC19_REQUIRED_FALSE_AUTHORITY_TRUE", "B4FNC20_NULL_PHYSICAL_INPUT_ZERO_FILLED",
    "B4FNC21_P_STROKE_DOMAIN_EXIT_OR_CLIPPING",
    "B4FNC22_LOWEST_TESTED_PROMOTED_TO_MINIMUM_REQUIRED_FORCE",
]
EXPECTED_REQUIRED_FALSE = {
    "b4f_solver_implemented", "b4f_campaign_executed", "synthetic_reachability_passed",
    "minimum_required_synthetic_force_identified", "physical_actuator_force_identified",
    "physical_actuator_timing_identified", "physical_release_implemented",
    "physical_recontact_implemented", "held_capture_passed", "grasp_success_claimed",
    "current_system_bound", "formal_nc19_credit", "owner_authorized", "production_ready",
    "release_authorized", "next_stage_authorized", "hardware_specification_released",
    "physical_gripper_stroke_identified", "measurement_uncertainty_model_available",
}
EXPECTED_NULL_INPUTS = {
    "physical_left_actuator_force_capacity_N", "physical_right_actuator_force_capacity_N",
    "physical_opening_time_s", "physical_braking_time_s", "physical_motor_current_A",
    "physical_transmission_efficiency", "physical_contact_frame_left",
    "physical_contact_frame_right", "physical_lock_transform", "physical_retention_capacity_N",
    "physical_release_energy_J",
}
LOCAL_SOURCE_PATHS = [
    "README.md", "pytest.ini", "validate_phase_b4f_contract.py",
    "independent_audit_phase_b4f_contract.py",
    "contracts/PHASE_B4F_WORK_AUTHORIZATION_V1.json",
    "contracts/PHASE_B4F_MODEL_AND_ENERGY_CONTRACT_V1.json",
    "contracts/PHASE_B4F_EXPERIMENT_DESIGN_V1.json",
    "contracts/PHASE_B4F_NUMERICAL_ACCEPTANCE_V1.json",
    "contracts/PHASE_B4F_GOVERNANCE_V1.json",
    "contracts/PHASE_B4F_SOURCE_BINDINGS_V1.json",
    "contracts/PHASE_B4F_EVIDENCE_SCHEMA_V1.json",
    "contracts/PHASE_B4F_TEST_INVENTORY_V1.json",
    "tests/conftest.py", "tests/test_sources_and_authority.py",
    "tests/test_model_and_work.py", "tests/test_experiment_design.py",
    "tests/test_numerical_and_negative_controls.py", "tests/test_governance_and_schema.py",
]


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


def _record(path: Path, role: str, base: Path = ROOT) -> dict[str, Any]:
    return {
        "path": path.relative_to(base).as_posix(),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _resolve(record_path: str, relative_base: Path) -> Path:
    candidate = Path(record_path)
    if candidate.parts and candidate.parts[0] in {
        "01_project", "10_research", "20_engineering", "30_simulation", "40_evidence",
        "50_literature", "70_tools", "80_third_party",
    }:
        return ROOT / candidate
    return relative_base / candidate


def _verify_declared(record: dict[str, Any], relative_base: Path) -> tuple[bool, dict[str, Any]]:
    path = _resolve(str(record.get("path", "")), relative_base)
    exists = path.is_file()
    actual_bytes = path.stat().st_size if exists else None
    actual_sha = _sha(path) if exists else None
    passed = (
        exists
        and actual_bytes == record.get("bytes")
        and actual_sha == record.get("sha256")
        and bool(re.fullmatch(r"[0-9A-F]{64}", str(record.get("sha256", ""))))
    )
    return passed, {
        "declared_path": record.get("path"), "resolved_path": path.as_posix(),
        "declared_bytes": record.get("bytes"), "actual_bytes": actual_bytes,
        "declared_sha256": record.get("sha256"), "actual_sha256": actual_sha,
        "pass": passed,
    }


def _verify_recursive(bindings: dict[str, Any]) -> dict[str, Any]:
    binding_results: list[dict[str, Any]] = []
    by_id = {row["id"]: row for row in bindings.get("sources", [])}
    for source_id, row in by_id.items():
        passed, detail = _verify_declared(row, ROOT)
        binding_results.append({"id": source_id, **detail})

    terminal_row = by_id.get("b4e_terminal_manifest", {})
    terminal_path = _resolve(str(terminal_row.get("path", "")), ROOT)
    b4e_root = terminal_path.parents[1] if terminal_path.is_file() else HERE
    terminal = _load(terminal_path) if terminal_path.is_file() else {}
    terminal_results = []
    for row in terminal.get("entries", []):
        passed, detail = _verify_declared(row, b4e_root)
        terminal_results.append({"role": row.get("role"), **detail})

    evidence_entry = next(
        (row for row in terminal.get("entries", []) if row.get("role") == "EVIDENCE_DAG"), {}
    )
    evidence_path = _resolve(str(evidence_entry.get("path", "")), b4e_root)
    evidence = _load(evidence_path) if evidence_path.is_file() else {}
    evidence_results = []
    for row in evidence.get("files", []):
        passed, detail = _verify_declared(row, b4e_root)
        evidence_results.append({"role": row.get("role"), **detail})

    source_entry = next(
        (row for row in evidence.get("files", []) if row.get("role") == "SOURCE_DAG_ROOT"), {}
    )
    source_path = _resolve(str(source_entry.get("path", "")), b4e_root)
    source_manifest = _load(source_path) if source_path.is_file() else {}
    source_results = []
    for row in source_manifest.get("sources", []):
        passed, detail = _verify_declared(row, ROOT)
        source_results.append({"id": row.get("id"), "role": row.get("role"), **detail})

    b4_terminal_source = next(
        (row for row in source_manifest.get("sources", []) if row.get("id") == "b4_contract_terminal_manifest"), {}
    )
    b4_gate_source = next(
        (row for row in source_manifest.get("sources", []) if row.get("id") == "b4_contract_audited_gate"), {}
    )
    b4_terminal_path = _resolve(str(b4_terminal_source.get("path", "")), ROOT)
    b4_terminal = _load(b4_terminal_path) if b4_terminal_path.is_file() else {}
    b4_terminal_records = []
    for row in b4_terminal.get("records", []):
        passed, detail = _verify_declared(row, ROOT)
        b4_terminal_records.append({"role": row.get("role"), **detail})

    b4_gate_path = _resolve(str(b4_gate_source.get("path", "")), ROOT)
    b4_gate = _load(b4_gate_path) if b4_gate_path.is_file() else {}
    b4e_gate_row = by_id.get("b4e_audited_gate", {})
    b4e_gate_path = _resolve(str(b4e_gate_row.get("path", "")), ROOT)
    b4e_gate = _load(b4e_gate_path) if b4e_gate_path.is_file() else {}

    recursive_pass = all(
        [
            set(by_id) == EXPECTED_BINDING_IDS,
            all(row["pass"] for row in binding_results),
            terminal.get("schema") == "SIM13_V4B4E_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
            terminal.get("self_excluded") is True,
            terminal_path.resolve() not in {
                _resolve(str(row.get("path", "")), b4e_root).resolve()
                for row in terminal.get("entries", [])
            },
            len(terminal_results) >= 4 and all(row["pass"] for row in terminal_results),
            evidence.get("schema") == "SIM13_V4B4E_EVIDENCE_MANIFEST_V1",
            evidence.get("self_excluded") is True,
            evidence_path.resolve() not in {
                _resolve(str(row.get("path", "")), b4e_root).resolve()
                for row in evidence.get("files", [])
            },
            evidence.get("file_count") == len(evidence_results),
            len(evidence_results) >= 10 and all(row["pass"] for row in evidence_results),
            source_manifest.get("schema") == "SIM13_V4B4E_SOURCE_MANIFEST_V1",
            source_manifest.get("self_excluded") is True,
            source_path.resolve() not in {
                _resolve(str(row.get("path", "")), ROOT).resolve()
                for row in source_manifest.get("sources", [])
            },
            source_manifest.get("source_count") == len(source_results),
            len(source_results) >= 20 and all(row["pass"] for row in source_results),
            b4_terminal_source.get("sha256") == FROZEN_B4_TERMINAL_SHA,
            b4_gate_source.get("sha256") == FROZEN_B4_GATE_SHA,
            b4_terminal_path.is_file() and _sha(b4_terminal_path) == FROZEN_B4_TERMINAL_SHA,
            b4_gate_path.is_file() and _sha(b4_gate_path) == FROZEN_B4_GATE_SHA,
            b4_terminal.get("self_excluded") is True,
            b4_terminal.get("acyclic") is True,
            b4_terminal_path.resolve() not in {
                _resolve(str(row.get("path", "")), ROOT).resolve()
                for row in b4_terminal.get("records", [])
            },
            len(b4_terminal_records) == 2 and all(row["pass"] for row in b4_terminal_records),
            b4_gate.get("final_gate") is True,
            str(b4_gate.get("overall_status", "")).startswith("PASS_PHASE_B4_CONTRACT_FREEZE_ONLY"),
            b4e_gate.get("final") is True,
            str(b4e_gate.get("status", "")).startswith("PASS_PHASE_B4E_SOLVER_AUDIT"),
            b4e_gate.get("nominal_branch", {}).get("removal_or_release_capability_pass") is False,
            all(value is False for value in b4e_gate.get("required_false", {}).values()),
            b4e_gate.get("formal_sim13_v2_state_unchanged") == {
                "passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]
            },
        ]
    )
    return {
        "pass": recursive_pass,
        "binding_records": binding_results,
        "b4e_terminal_records": terminal_results,
        "b4e_evidence_records": evidence_results,
        "b4e_source_records": source_results,
        "frozen_b4_terminal_records": b4_terminal_records,
        "b4e_gate_status": b4e_gate.get("status"),
        "frozen_b4_gate_status": b4_gate.get("overall_status"),
        "frozen_b4_terminal_sha256": _sha(b4_terminal_path) if b4_terminal_path.is_file() else None,
        "frozen_b4_gate_sha256": _sha(b4_gate_path) if b4_gate_path.is_file() else None,
    }


def _collect_and_run_pytest(inventory: dict[str, Any]) -> dict[str, Any]:
    collect = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=HERE,
        text=True, capture_output=True, encoding="utf-8", errors="replace",
    )
    nodeids = sorted(line.strip() for line in collect.stdout.splitlines() if "::" in line)
    nodeid_sha = hashlib.sha256("\n".join(nodeids).encode("utf-8")).hexdigest().upper()
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=HERE,
        text=True, capture_output=True, encoding="utf-8", errors="replace",
    )
    summary_text = run.stdout + "\n" + run.stderr
    passed_match = re.search(r"(\d+) passed", summary_text)
    outcomes = {
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "failed": int(re.search(r"(\d+) failed", summary_text).group(1)) if re.search(r"(\d+) failed", summary_text) else 0,
        "errors": int(re.search(r"(\d+) errors?", summary_text).group(1)) if re.search(r"(\d+) errors?", summary_text) else 0,
        "skipped": int(re.search(r"(\d+) skipped", summary_text).group(1)) if re.search(r"(\d+) skipped", summary_text) else 0,
    }
    expected = inventory["pytest"]
    passed = (
        collect.returncode == 0 and run.returncode == 0
        and len(nodeids) == expected["expected_collected"]
        and nodeid_sha == expected["expected_nodeid_sha256"]
        and outcomes == expected["required_outcome"]
    )
    return {
        "pass": passed, "collect_returncode": collect.returncode, "run_returncode": run.returncode,
        "collected": len(nodeids), "nodeids": nodeids, "nodeid_sha256": nodeid_sha,
        "outcomes": outcomes, "stdout": run.stdout, "stderr": run.stderr,
    }


def main() -> int:
    authorization = _load(AUTHORIZATION)
    model = _load(MODEL)
    experiment = _load(EXPERIMENT)
    numerical = _load(NUMERICAL)
    governance = _load(GOVERNANCE)
    bindings = _load(BINDINGS)
    schema = _load(EVIDENCE_SCHEMA)
    inventory = _load(TEST_INVENTORY)
    recursive = _verify_recursive(bindings)

    local_records = [_record(HERE / rel, "B4F_FROZEN_LOCAL_SOURCE", HERE) for rel in LOCAL_SOURCE_PATHS]
    source_payload = {
        "schema": "SIM13_V4B4F_SOURCE_VERIFICATION_V1",
        "scope": "LOCAL_CONTRACT_SOURCES_AND_RECURSIVE_PARENT_DAG",
        "status": "PASS_RECURSIVE_SOURCE_VERIFICATION" if recursive["pass"] else "FAIL_RECURSIVE_SOURCE_VERIFICATION",
        "self_excluded": True,
        "local_source_count": len(local_records),
        "local_sources": local_records,
        "recursive_parent_verification": recursive,
    }
    _atomic_json(SOURCE_VERIFICATION, source_payload)

    arms = {row["id"]: row for row in experiment.get("arms", [])}
    checks: list[dict[str, Any]] = []

    def check(check_id: str, name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "name": name, "pass": bool(condition), "detail": detail})

    expected_schemas = {
        authorization.get("schema"): "SIM13_V4B4F_WORK_AUTHORIZATION_V1",
        model.get("schema"): "SIM13_V4B4F_MODEL_AND_ENERGY_CONTRACT_V1",
        experiment.get("schema"): "SIM13_V4B4F_EXPERIMENT_DESIGN_V1",
        numerical.get("schema"): "SIM13_V4B4F_NUMERICAL_ACCEPTANCE_V1",
        governance.get("schema"): "SIM13_V4B4F_GOVERNANCE_V1",
        bindings.get("schema"): "SIM13_V4B4F_SOURCE_BINDINGS_V1",
        schema.get("schema"): "SIM13_V4B4F_EVIDENCE_SCHEMA_V1",
        inventory.get("schema"): "SIM13_V4B4F_TEST_INVENTORY_V1",
    }
    check("B4FV01", "all eight contract schemas exact", len(expected_schemas) == 8 and all(k == v for k, v in expected_schemas.items()))
    check("B4FV02", "recursive B4E evidence/source DAG and frozen B4 terminal", recursive["pass"], recursive.get("b4e_gate_status"))
    by_id = {row["id"]: row for row in bindings["sources"]}
    check(
        "B4FV03", "source binding ids paths and roles exact",
        set(by_id) == EXPECTED_BINDING_IDS
        and all((by_id[key].get("path"), by_id[key].get("role")) == value for key, value in EXPECTED_BINDING_PATHS_AND_ROLES.items()),
    )
    check(
        "B4FV04", "authorization basis bound to current B4E audited gate",
        authorization["basis"]["parent_b4e_audited_gate_sha256"] == by_id.get("b4e_audited_gate", {}).get("sha256"),
    )
    auth = authorization["authorized"]
    check("B4FV05", "contract work authorized without solver or upstream mutation", all([
        auth["freeze_contracts_and_test_contracts"], auth["bind_parent_sources_and_evidence"],
        auth["define_synthetic_generalized_force_profiles"], auth["define_algorithm_only_parameter_domain"],
        not auth["implement_or_execute_b4f_solver"], not auth["modify_b4_or_b4e"],
        not auth["modify_or_generate_urdf"], not auth["bind_current_system_interface"],
        not auth["invoke_private_builder_or_generator"],
    ]))
    check("B4FV06", "workflow authority is not Owner or physical authority", all(v is False for v in authorization["authority_boundary"].values()))

    equation = model["active_equation"]
    check("B4FV07", "14D P-only internal generalized force", equation["Q_a_shape"] == 14 and equation["allowed_nonzero_indices_zero_based"] == [12, 13] and equation["allowed_native_unit"] == "N" and equation["all_base_and_R_joint_applied_efforts_exact_zero"] is True)
    check("B4FV08", "contact kernel excluded while synthetic constraint active", equation["contact_kernel_enabled_while_synthetic_constraint_active"] is False and equation["ideal_constraint_stored_energy_J"] == 0.0)
    signs = model["sign_and_basis"]
    check("B4FV09", "opening sign definition and invariance fail-closed", signs["registered_opening_sign_vector_left_right"] == [1, 1] and signs["sign_must_be_reverified_from_raw_gap_jacobian_at_every_acquisition"] is True and signs["sign_must_remain_invariant_over_every_accepted_trajectory_sample"] is True and signs["zero_or_changed_sign_action"] == "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN")
    force = model["reference_force_scaling"]
    check("B4FV10", "reference force cannot become actuator specification", force["classification"] == "ALGORITHM_ONLY_DIMENSIONAL_REFERENCE_NOT_ACTUATOR_SPECIFICATION" and force["one_common_reference_force_for_all_integrators_blocks_and_treatments"] is True and force["per_run_or_per_treatment_reference_force_recomputation_forbidden"] is True and force["hardware_force_capacity_inferred"] is False)
    command = model["command_profile"]
    check("B4FV11", "command exact zero through dwell/removal and after release", command["command_must_be_exact_zero_through_clearance_dwell_and_at_removal"] is True and command["post_release_applied_generalized_force"] == "exact_zero")
    work = model["actuator_work_ledger"]
    check("B4FV12", "signed actuator work integrated as state", "W_act_dot=P_act" in work["primary_integration"] and "-W_act" in work["active_energy_identity"] and work["actuator_work_reset_on_removal"] is False and work["dissipated_energy_return_on_removal"] is False)

    domain = model["synthetic_geometry_validity_domain"]
    check("B4FV13", "geometry domain is exact [0,0.0715] on both P coordinates", domain["left_P_coordinate_m_closed_interval"] == [0.0, 0.0715] and domain["right_P_coordinate_m_closed_interval"] == [0.0, 0.0715])
    check("B4FV14", "geometry evaluated at stages samples events and fail-closed", domain["evaluation"] == "every accepted integrator stage, stored sample and exact event state" and domain["exit_action"] == "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN" and domain["extrapolation_or_clipping_forbidden"] is True)
    removal = model["removal_transition"]
    check("B4FV15", "zero-jump exact removal and independent 5ms post-release", "componentwise copy" in removal["mapping"] and removal["post_release_observation_s"] == 0.005 and removal["post_release_contact_kernel_enabled"] is False and removal["post_release_actuator_generalized_force"] == "exact_zero")

    check("B4FV16", "A0 zero-input B4E replay preregistered", arms.get("A0_ZERO_INPUT_EXACT_REPLAY", {}).get("alpha_left") == 0.0 and arms.get("A0_ZERO_INPUT_EXACT_REPLAY", {}).get("alpha_right") == 0.0 and "W_act=0" in arms.get("A0_ZERO_INPUT_EXACT_REPLAY", {}).get("required_outcome", ""))
    a1 = arms.get("A1_SYMMETRIC_BRAKE_OPEN", {})
    check("B4FV17", "A1 discrete full factorial exact", a1.get("alpha_levels_dimensionless") == [0.5, 1.0, 2.0, 4.0, 8.0, 16.0] and a1.get("command_duration_levels_s") == [0.005, 0.01, 0.02] and a1.get("full_factorial_case_count_per_event_and_integrator") == 18 and a1.get("center_or_unregistered_levels_forbidden") is True)
    a2 = arms.get("A2_ASYMMETRIC_LAG_AND_ONE_SIDE_LOSS", {})
    check("B4FV18", "A2 mirror and one-side-loss variants exact", {row["id"] for row in a2.get("variants", [])} == {"RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR", "RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR"} and a2.get("bilateral_clearance_gate_never_relaxed") is True and "if no A1 succeeds, A2 is NOT_EVALUATED" in a2.get("parent_case_selection", ""))
    horizon = experiment["registered_horizon"]
    check("B4FV19", "registered 0.08s horizon and no global unreachability", horizon["active_duration_after_acquisition_s"] == 0.08 and horizon["extension_after_observing_results_forbidden"] is True and horizon["global_unreachability_claim"] is False)
    selector = experiment["primary_case_selector"]
    check("B4FV20", "only lowest-tested discrete level may be reported", selector["reported_label"] == "lowest_tested_reachable_alpha_in_registered_discrete_grid" and selector["minimum_required_force_or_work_claim_authorized"] is False and selector["between_level_interpolation_or_inverse_threshold_estimation_authorized"] is False)
    geometry_policy = experiment["geometry_domain_policy"]
    check("B4FV21", "out-of-domain cases excluded from selector", geometry_policy["any_stage_sample_or_event_outside_domain"] == "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN" and geometry_policy["failed_domain_case_can_enter_primary_selector"] is False and geometry_policy["clipping_or_extrapolation_forbidden"] is True)
    check("B4FV22", "deterministic blocking fresh events and seed frozen", experiment["blocking"]["each_treatment_uses_its_own_first_qualifying_B3_event"] is True and experiment["blocking"]["forced_shared_event_time_forbidden"] is True and experiment["blocking"]["fresh_initial_state_for_every_run"] is True and experiment["run_order"]["seed"] == 20260824 and experiment["run_order"]["hidden_state_between_runs_forbidden"] is True)

    check("B4FV23", "17 future numerical gates unique", len(numerical["gate_ids"]) == 17 and len(set(numerical["gate_ids"])) == 17)
    check("B4FV24", "22 future negative controls frozen in order", numerical["required_negative_controls"] == EXPECTED_NC and numerical["all_negative_controls_must_mutate_real_raw_artifacts_or_executed_paths"] is True and numerical["dictionary_flag_only_mutation_forbidden"] is True)
    outcomes = numerical["terminal_outcomes"]
    check("B4FV25", "future outcome labels do not create physical/global claims", outcomes["success_is_physical_release_capability"] is False and outcomes["no_observed_success_is_global_unreachability"] is False)

    required_false = governance["required_false"]
    check("B4FV26", "all physical current formal Owner production states false", set(required_false) == EXPECTED_REQUIRED_FALSE and all(v is False for v in required_false.values()))
    check("B4FV27", "physical inputs are null-only keys", set(governance["required_null_physical_inputs"]) == EXPECTED_NULL_INPUTS)
    check("B4FV28", "formal Sim13 V2 remains 15/20", governance["formal_sim13_v2_state_unchanged"] == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]})
    memory = governance["memory_governance"]
    check("B4FV29", "CAD memory gate inapplicable and no override reuse", memory["unified_r2_or_v5_cad_memory_gate_applicable"] is False and memory["memory_gate_credit_allowed"] is False and memory["historical_owner_override_reuse_allowed"] is False and memory["future_b4f_run_records_memory_as_diagnostic_only"] is True)
    names = {path.name for path in HERE.rglob("*") if path.is_file()}
    forbidden_ok = not any(name.endswith(".urdf") for name in names) and all(name not in names for name in governance["forbidden_artifacts"][1:])
    check("B4FV30", "no URDF interface execution lock or release marker", forbidden_ok)
    check("B4FV31", "allowed true states limited to contract audit", governance["allowed_true_after_contract_audit"] == ["b4f_contract_frozen", "b4f_contract_audited", "parent_b4e_recursively_verified"])
    check("B4FV32", "evidence and terminal manifests self-excluded", schema["self_exclusion"] == {"evidence_manifest_self_excluded": True, "terminal_manifest_self_excluded": True})

    pytest_result = _collect_and_run_pytest(inventory)
    check("B4FV33", "frozen pytest inventory exact and all green", pytest_result["pass"], pytest_result["outcomes"])
    check("B4FV34", "source verification artifact published atomically", SOURCE_VERIFICATION.is_file() and source_payload["self_excluded"] is True and source_payload["status"] == "PASS_RECURSIVE_SOURCE_VERIFICATION")

    failed = [row["id"] for row in checks if not row["pass"]]
    validation_payload = {
        "schema": "SIM13_V4B4F_CONTRACT_VALIDATION_V1",
        "status": "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" if not failed else "FAIL_CONTRACT_VALIDATION",
        "scope": "CONTRACT_FREEZE_ONLY_NO_SOLVER_OR_CAMPAIGN_EXECUTION",
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "pytest": pytest_result,
        "source_verification": _record(SOURCE_VERIFICATION, "B4F_RECURSIVE_SOURCE_VERIFICATION", ROOT),
        "implementation_state": {
            "b4f_solver_implemented": False,
            "b4f_campaign_executed": False,
            "synthetic_reachability_passed": False,
            "future_negative_controls_executed": False,
        },
    }
    _atomic_json(VALIDATION, validation_payload)
    evidence_payload = {
        "schema": "SIM13_V4B4F_CONTRACT_EVIDENCE_MANIFEST_V1",
        "self_excluded": True,
        "acyclic": True,
        "record_count": 2,
        "records": [
            _record(SOURCE_VERIFICATION, "B4F_RECURSIVE_SOURCE_VERIFICATION", ROOT),
            _record(VALIDATION, "B4F_CONTRACT_VALIDATION", ROOT),
        ],
    }
    _atomic_json(EVIDENCE_MANIFEST, evidence_payload)
    print(json.dumps({"status": validation_payload["status"], "score": validation_payload["score"], "pytest": pytest_result["outcomes"]}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
