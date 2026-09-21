"""Execute the bounded post-freeze B4 synthetic solver evidence campaign."""

from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from typing import Any

import numpy as np


PHASE_ROOT = Path(__file__).resolve().parent
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))

import b4_solver.constraint_solver as solver  # noqa: E402


EVIDENCE = PHASE_ROOT / "evidence"
RESULTS = PHASE_ROOT / "results"
RUN_SPECS_PATH = PHASE_ROOT / "contracts" / "PHASE_B4E_RUN_SPEC_V1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_sha(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def source_inventory() -> list[dict[str, Any]]:
    project = solver._project_root()
    records = solver.verify_bound_sources(project)
    local_roots = [PHASE_ROOT / "contracts", PHASE_ROOT / "b4_solver", PHASE_ROOT / "tests"]
    local_files: list[Path] = [
        PHASE_ROOT / "run_phase_b4_solver.py",
        PHASE_ROOT / "validate_phase_b4_solver.py",
        PHASE_ROOT / "independent_audit_phase_b4_solver.py",
        PHASE_ROOT / "README.md",
        PHASE_ROOT / "pytest.ini",
    ]
    for root in local_roots:
        if root.is_dir():
            local_files.extend(path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    seen: set[str] = set()
    for path in sorted(local_files):
        if not path.is_file() or path.suffix in (".pyc", ".pyo"):
            continue
        relative = path.relative_to(project).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        records.append({
            "id": f"local::{path.relative_to(PHASE_ROOT).as_posix()}",
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "role": "POST_FREEZE_SOLVER_SOURCE_OR_FROZEN_LOCAL_CONTRACT",
        })
    return sorted(records, key=lambda item: (item["role"], item["path"]))


def acquisition_checks(acquisition: solver.AcquisitionResult) -> dict[str, bool]:
    metric = acquisition.metrics
    checks = {
        "rank_L_hat_14": acquisition.ranks["L_hat"] == 14,
        "rank_J_hat_6": acquisition.ranks["J_hat"] == 6,
        "rank_G_bar_5": acquisition.ranks["G_bar"] == 5,
        "snapshot_translation": metric["snapshot_translation_identity_m"] <= 1.0e-12,
        "snapshot_rotation": metric["snapshot_rotation_geodesic_rad"] <= 1.0e-12,
        "rotation_orthogonality": metric["rotation_orthogonality_inf"] <= 1.0e-12,
        "rotation_determinant": metric["rotation_determinant_error_abs"] <= 1.0e-12,
        "scaled_JL": metric["Jhat_Lhat_operator_inf_dimensionless"] <= 1.0e-11,
        "Wbar_spd": metric["W_bar_scaled_min_eigenvalue"] > 0.0,
        "Wbar_condition": metric["W_bar_scaled_condition_number"] <= 1.0e10,
        "reduced_kkt_base_linear": metric["reduced_kkt_service_base_linear_component_m_s"] <= 1.0e-10,
        "reduced_kkt_base_angular": metric["reduced_kkt_service_base_angular_component_rad_s"] <= 1.0e-10,
        "reduced_kkt_R": metric["reduced_kkt_R_joint_component_rad_s"] <= 1.0e-10,
        "reduced_kkt_P": metric["reduced_kkt_P_joint_component_m_s"] <= 1.0e-10,
        "reduced_kkt_target_linear": metric["reduced_kkt_target_linear_component_m_s"] <= 1.0e-10,
        "reduced_kkt_target_angular": metric["reduced_kkt_target_angular_component_rad_s"] <= 1.0e-10,
        "constraint_linear": metric["post_constraint_linear_twist_m_s"] <= 1.0e-10,
        "constraint_angular": metric["post_constraint_angular_twist_rad_s"] <= 1.0e-10,
        "impulse_base_linear": metric["combined_impulse_equation_service_base_linear_N_s"] <= 1.0e-9,
        "impulse_base_angular": metric["combined_impulse_equation_service_base_angular_N_m_s"] <= 1.0e-9,
        "impulse_R": metric["combined_impulse_equation_R_joint_N_m_s"] <= 1.0e-9,
        "impulse_P": metric["combined_impulse_equation_P_joint_N_s"] <= 1.0e-9,
        "impulse_target_linear": metric["combined_impulse_equation_target_linear_N_s"] <= 1.0e-9,
        "impulse_target_angular": metric["combined_impulse_equation_target_angular_N_m_s"] <= 1.0e-9,
        "linear_momentum_jump": metric["total_linear_momentum_jump_N_s"] <= 1.0e-9,
        "angular_momentum_jump": metric["total_angular_momentum_jump_about_fixed_inertial_origin_N_m_s"] <= 1.0e-9,
        "projection_energy": metric["projection_energy_identity_J"] <= 1.0e-9,
        "switch_energy": metric["switch_energy_identity_J"] <= 1.0e-9,
        "potential_once": metric["contact_potential_sum_identity_J"] <= 1.0e-12,
        "nonnegative_dissipation": acquisition.energy_audit["D_projection_J"] >= -1.0e-12,
        "fixed_child_mass_agreement": metric["attached_mass_fixed_child_inf"] <= 1.0e-10,
        "no_forbidden_acquisition_backend": acquisition.backend_provenance["acquisition_pinv_or_lstsq"] == "FORBIDDEN_NOT_USED",
    }
    return checks


def active_checks(run: solver.ActiveRunResult) -> dict[str, bool]:
    maximum = run.maxima
    return {
        "linear_momentum": maximum["linear_momentum_drift_N_s"] <= 1.0e-9,
        "angular_momentum": maximum["angular_momentum_drift_N_m_s"] <= 1.0e-9,
        "energy": maximum["energy_plus_dissipation_drift_J"] <= 1.0e-7,
        "pose_translation": maximum["pose_translation_residual_m"] <= 1.0e-9,
        "pose_rotation": maximum["pose_rotation_residual_rad"] <= 1.0e-9,
        "twist_linear": maximum["relative_linear_twist_m_s"] <= 1.0e-9,
        "twist_angular": maximum["relative_angular_twist_rad_s"] <= 1.0e-9,
        "ideal_power": maximum["ideal_constraint_power_W"] <= 1.0e-10,
        "contact_force_disabled": maximum["contact_force_while_active_N"] <= 1.0e-12,
        "contact_torque_disabled": maximum["contact_torque_while_active_N_m"] <= 1.0e-12,
        "mass_rebuild": maximum["mass_formula_fixed_child_inf"] <= 1.0e-10,
        "bias_base_linear_rebuild": maximum["bias_formula_fixed_child_base_linear_N"] <= 1.0e-9,
        "bias_base_angular_rebuild": maximum["bias_formula_fixed_child_base_angular_N_m"] <= 1.0e-9,
        "bias_R_rebuild": maximum["bias_formula_fixed_child_R_joint_N_m"] <= 1.0e-9,
        "bias_P_rebuild": maximum["bias_formula_fixed_child_P_joint_N"] <= 1.0e-9,
        "bounded_horizon_exact": abs(float(run.time_s[-1]) - 0.08) <= 1.0e-14,
        "no_global_empty_set_claim": not run.clearance.get("global_empty_eligibility_set_claimed", False),
    }


def difference_step_audit(event: solver.EventInput, acquisition: solver.AcquisitionResult) -> dict[str, Any]:
    model = solver.BranchedGripperServiceModel()
    service = solver.ServiceState(
        event.service.base_position_inertial_m.copy(), event.service.base_quaternion_body_to_inertial_wxyz.copy(),
        event.service.joint_coordinates_mixed.copy(), acquisition.eta_plus.copy(),
    )
    records: list[dict[str, Any]] = []
    terms: dict[float, tuple[np.ndarray, np.ndarray]] = {}
    for step in (1.0e-6, 2.0e-6, 4.0e-6):
        mass, bias, *_ = solver._active_formula_terms(model, service, acquisition.snapshot, difference_step_s=step)
        terms[step] = (mass, bias)
        records.append({"difference_step_s": step, "mass_minimum_eigenvalue": float(np.linalg.eigvalsh(0.5 * (mass + mass.T))[0]), "bias_mixed": bias.tolist()})
    nominal_bias = terms[2.0e-6][1]
    return {
        "classification": "NUMERICAL_DIRECTIONAL_DIFFERENCE_STEP_AUDIT_NOT_MEASUREMENT_UNCERTAINTY",
        "records": records,
        "half_vs_nominal": {
            "base_linear_N": float(np.max(np.abs(terms[1.0e-6][1][:3] - nominal_bias[:3]))),
            "base_angular_N_m": float(np.max(np.abs(terms[1.0e-6][1][3:6] - nominal_bias[3:6]))),
            "R_joint_N_m": float(np.max(np.abs(terms[1.0e-6][1][6:12] - nominal_bias[6:12]))),
            "P_joint_N": float(np.max(np.abs(terms[1.0e-6][1][12:14] - nominal_bias[12:14]))),
        },
        "double_vs_nominal": {
            "base_linear_N": float(np.max(np.abs(terms[4.0e-6][1][:3] - nominal_bias[:3]))),
            "base_angular_N_m": float(np.max(np.abs(terms[4.0e-6][1][3:6] - nominal_bias[3:6]))),
            "R_joint_N_m": float(np.max(np.abs(terms[4.0e-6][1][6:12] - nominal_bias[6:12]))),
            "P_joint_N": float(np.max(np.abs(terms[4.0e-6][1][12:14] - nominal_bias[12:14]))),
        },
    }


def removal_fixture(primary: solver.ActiveRunResult) -> dict[str, Any]:
    return solver.execute_abstract_removal_fixture(primary)


def memory_diagnostic_sample() -> dict[str, Any]:
    """Read available physical memory without treating it as a B4E Gate."""

    sampled_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    source = "UNKNOWN"
    available: int | None = None
    if sys.platform == "win32":
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        status = MemoryStatusEx(); status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            available = int(status.ullAvailPhys); source = "Windows GlobalMemoryStatusEx.ullAvailPhys"
    return {
        "memory_sampled_utc": sampled_utc,
        "memory_measurement_source": source,
        "available_physical_memory_bytes": available,
        "available_physical_memory_gib": None if available is None else available / (1024.0 ** 3),
        "memory_gate_reference_gib": 6.0,
        "memory_gate_applicable": False,
        "memory_gate_evaluated": False,
        "memory_gate_status": "NOT_APPLICABLE_B4E_BOUNDED_SYNTHETIC_NUMERICAL_EXECUTION",
        "memory_gate_passed": False,
        "owner_override_required": False,
        "owner_override_used": False,
        "owner_override_id": None,
        "low_memory_risk_ack": None,
        "workflow_execution_authorized": True,
        "workflow_authorization_source_path": "contracts/PHASE_B4E_POST_FREEZE_WORK_AUTHORIZATION_V1.json",
        "workflow_authorization_source_sha256": sha256(PHASE_ROOT / "contracts" / "PHASE_B4E_POST_FREEZE_WORK_AUTHORIZATION_V1.json"),
        "owner_mechanical_authorized": False,
        "unified_r2_generator_invoked": False,
        "cad_or_com_write_invoked": False,
    }


def execute_campaign() -> dict[str, Any]:
    runtime_memory = memory_diagnostic_sample()
    before = source_inventory()
    run_spec = json.loads(RUN_SPECS_PATH.read_text(encoding="utf-8"))
    events: dict[str, solver.EventInput] = {}
    runs: dict[str, solver.ActiveRunResult] = {}
    for spec in run_spec["trigger_runs"]:
        run_id = spec["run_id"]
        if run_id == "rk4_reference":
            event = solver.extract_frozen_primary_event()
        else:
            event = solver.rerun_b3_to_event(run_id, spec["method"], float(spec["step_s"]))
        if event.method != spec["method"] or abs(event.step_s - float(spec["step_s"])) > 1.0e-16:
            raise solver.SolverError(f"RUN_SPEC_EVENT_MISMATCH:{run_id}")
        events[run_id] = event
        runs[run_id] = solver.execute_run(event)

    event_records = [solver.event_to_json(events[spec["run_id"]]) for spec in run_spec["trigger_runs"]]
    acquisitions = {run_id: solver.acquisition_to_json(run.acquisition) for run_id, run in runs.items()}
    traces = {run_id: solver.active_to_json(run, full_trace=True) for run_id, run in runs.items()}
    checks = {
        run_id: {"acquisition": acquisition_checks(run.acquisition), "active": active_checks(run)}
        for run_id, run in runs.items()
    }
    primary = runs[run_spec["primary_run_id"]]
    independent = runs[run_spec["independent_reference_run_id"]]
    acquisition_delta = abs(primary.acquisition.acquisition_time_s - independent.acquisition.acquisition_time_s)
    primary_finite = bool(primary.clearance["finite_event"])
    independent_finite = bool(independent.clearance["finite_event"])
    if primary_finite and independent_finite:
        removal_delta: float | None = abs(float(primary.clearance["removal_time_s"]) - float(independent.clearance["removal_time_s"]))
        removal_comparison = "EVALUATED_BOTH_FINITE"
        removal_gate = removal_delta <= 0.00025
    elif primary_finite != independent_finite:
        removal_delta = None; removal_comparison = "FAIL_ONE_FINITE_ONE_NOT"; removal_gate = False
    else:
        removal_delta = None; removal_comparison = "NOT_EVALUATED_NO_FINITE_EVENT"; removal_gate = True
    cross = {
        "primary_run_id": primary.run_id,
        "independent_reference_run_id": independent.run_id,
        "primary_acquisition_time_s": primary.acquisition.acquisition_time_s,
        "independent_acquisition_time_s": independent.acquisition.acquisition_time_s,
        "acquisition_event_time_difference_s": acquisition_delta,
        "acquisition_event_time_tolerance_s": 0.00025,
        "acquisition_event_gate_pass": acquisition_delta <= 0.00025,
        "forced_shared_acquisition_time": False,
        "primary_removal_finite": primary_finite,
        "independent_removal_finite": independent_finite,
        "removal_event_comparison": removal_comparison,
        "removal_event_time_difference_s": removal_delta,
        "removal_event_time_gate_pass_or_not_applicable": removal_gate,
        "outcome_classification_agreement": primary.terminal_status == independent.terminal_status,
        "both_horizon_exhausted_is_removal_capability_pass": False,
    }
    negative = solver.run_negative_controls(primary.acquisition, primary)
    fixture = removal_fixture(primary)
    difference = difference_step_audit(events[primary.run_id], primary.acquisition)

    EVIDENCE.mkdir(parents=True, exist_ok=True); RESULTS.mkdir(parents=True, exist_ok=True)
    write_json(EVIDENCE / "SIM13_V4B4E_RUNTIME_ENVIRONMENT_V1.json", {
        "schema": "SIM13_V4B4E_RUNTIME_ENVIRONMENT_V1",
        "python": sys.version, "python_executable": sys.executable,
        "platform": platform.platform(), "numpy": np.__version__,
        "scipy": __import__("scipy").__version__, "scope": solver.SCOPE,
        **runtime_memory,
    })
    write_json(EVIDENCE / "SIM13_V4B4E_EVENT_INPUTS_V1.json", {"schema": "SIM13_V4B4E_EVENT_INPUTS_V1", "runs": event_records})
    write_json(EVIDENCE / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json", {"schema": "SIM13_V4B4E_ACQUISITION_LEDGER_V1", "runs": acquisitions})
    write_json(EVIDENCE / "SIM13_V4B4E_ACTIVE_TRACES_V1.json", {"schema": "SIM13_V4B4E_ACTIVE_TRACES_V1", "runs": traces})
    write_json(EVIDENCE / "SIM13_V4B4E_NATIVE_UNIT_CHECKS_V1.json", {"schema": "SIM13_V4B4E_NATIVE_UNIT_CHECKS_V1", "runs": checks})
    write_json(EVIDENCE / "SIM13_V4B4E_CROSS_INTEGRATOR_LEDGER_V1.json", {"schema": "SIM13_V4B4E_CROSS_INTEGRATOR_LEDGER_V1", **cross})
    write_json(EVIDENCE / "SIM13_V4B4E_NEGATIVE_CONTROLS_V1.json", {"schema": "SIM13_V4B4E_NEGATIVE_CONTROLS_V1", "count": len(negative), "passed": sum(item["killed"] for item in negative), "results": negative})
    write_json(EVIDENCE / "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json", {"schema": "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1", **fixture})
    write_json(EVIDENCE / "SIM13_V4B4E_DIFFERENCE_STEP_AUDIT_V1.json", {"schema": "SIM13_V4B4E_DIFFERENCE_STEP_AUDIT_V1", **difference})

    after = source_inventory()
    if before != after:
        raise solver.SolverError("TOCTOU_SOURCE_INVENTORY_CHANGED_DURING_CAMPAIGN")
    source_manifest = {
        "schema": "SIM13_V4B4E_SOURCE_MANIFEST_V1", "self_excluded": True,
        "source_count": len(after), "sources": after,
        "frozen_b4_contract_recursively_bound": True,
    }
    write_json(EVIDENCE / "SIM13_V4B4E_SOURCE_MANIFEST_V1.json", source_manifest)

    all_checks = all(all(group.values()) for run in checks.values() for group in run.values())
    fixture_event = fixture["fixture_event"]
    fixture_relative_removal_index = (
        float(fixture["clearance"]["removal_time_s"]) - float(fixture_event["time_s"])
    ) / float(fixture_event["step_s"])
    fixture_pass = bool(
        fixture["no_state_mutation_after_acquisition"]
        and fixture["clearance_derived_from_same_active_state_trajectory"]
        and fixture["fixture_satisfies_main_b3_soft_capture_trigger"] is False
        and fixture["fixture_receives_physical_or_main_trigger_credit"] is False
        and fixture["fixture_contact_points_and_potentials_recomputed_from_perturbed_state"] is True
        and "COUNTERFACTUAL_ATTACHED_SEARCH_TRACE" in fixture["active_trace_semantics"]
        and fixture["same_active_trajectory_required_interval_s"] == [
            fixture_event["time_s"], fixture["clearance"]["removal_time_s"]
        ]
        and fixture["propagate_active_finite_event_branch_executed"]
        and fixture["exact_active_state_reconstructed_at_offgrid_removal_time"]
        and fixture["active_run"]["synthetic_removal_executed"]
        and abs(fixture_relative_removal_index - round(fixture_relative_removal_index)) > 1.0e-6
        and fixture["post_release"]["post_release_passed"]
    )
    campaign = {
        "schema": "SIM13_V4B4E_CAMPAIGN_SUMMARY_V1",
        "scope": solver.SCOPE,
        "run_count": len(runs),
        "all_event_local_and_active_checks_pass": all_checks,
        "cross_integrator": cross,
        "negative_controls_22_killed": len(negative) == 22 and all(item["killed"] for item in negative),
        "negative_controls_22_real_raw_mutations_killed": len(negative) == 22 and all(item["killed"] for item in negative),
        "primary_terminal_status": primary.terminal_status,
        "primary_synthetic_removal_executed": primary.synthetic_removal_executed,
        "bounded_horizon_end_time_s": 0.08,
        "bounded_horizon_global_no_event_claim": False,
        "abstract_removal_mapping_fixture_passed": fixture_pass,
        "algorithm_only_hybrid_removal_fixture_passed": fixture_pass,
        "b4_acquisition_and_active_solver_implemented": True,
        "b4_clearance_eligibility_certifier_implemented": True,
        "b4_hybrid_removal_and_post_release_solver_implemented": True,
        "main_branch_removal_or_release_capability_pass": bool(primary.synthetic_removal_executed),
        "physical_or_current_formal_credit": False,
        "formal_sim13_v2": {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]},
        "campaign_payload_sha256": canonical_sha({"events": event_records, "checks": checks, "cross": cross, "negative": negative}),
    }
    write_json(RESULTS / "SIM13_V4B4E_CAMPAIGN_SUMMARY_V1.json", campaign)
    return campaign


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compute-only", action="store_true")
    arguments = parser.parse_args()
    campaign = execute_campaign()
    print(json.dumps(campaign, indent=2, ensure_ascii=False))
    if not campaign["all_event_local_and_active_checks_pass"] or not campaign["negative_controls_22_real_raw_mutations_killed"]:
        return 2
    if arguments.compute_only:
        return 0
    validation = subprocess.run([sys.executable, str(PHASE_ROOT / "validate_phase_b4_solver.py")], cwd=solver._project_root(), check=False)
    if validation.returncode != 0:
        return validation.returncode
    audit = subprocess.run([sys.executable, str(PHASE_ROOT / "independent_audit_phase_b4_solver.py")], cwd=solver._project_root(), check=False)
    return audit.returncode


if __name__ == "__main__":
    raise SystemExit(main())
