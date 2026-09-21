"""Generate Phase-B2 raw evidence and a non-final pre-audit Gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import numpy as np

from b2_contact import (
    deterministic_friction_scenario,
    integrate_friction_contact,
    no_contact_regression,
    run_negative_controls,
    summarize_friction_history,
)
from b2_contact.friction_kernel import (
    CURRENT_SYSTEM_BOUND,
    DUAL_CONTACT_IMPLEMENTED,
    FORMAL_NC19_CREDIT,
    GRASP_SUCCESS_CLAIMED,
    LOCK_IMPLEMENTED,
    NEXT_STAGE_AUTHORIZED,
    PHYSICAL_FRICTION_IDENTIFIED,
    PRODUCTION_CONTACT_BACKEND,
    RELEASE_AUTHORIZED,
    SOFT_CAPTURE_IMPLEMENTED,
)
from sim13_v4a.full_floating import quaternion_geodesic


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
EVIDENCE = HERE / "evidence"
RESULTS = HERE / "results"

SOURCE_MANIFEST = EVIDENCE / "SIM13_V4B2_SOURCE_MANIFEST_V1.json"
TRACE = EVIDENCE / "SIM13_V4B2_FRICTION_TRACE_V1.json"
LEDGER = EVIDENCE / "SIM13_V4B2_FRICTION_LEDGER_V1.json"
VALIDATION = EVIDENCE / "SIM13_V4B2_VALIDATION_V1.json"
EVIDENCE_MANIFEST = EVIDENCE / "SIM13_V4B2_EVIDENCE_MANIFEST_V1.json"
PRE_AUDIT_GATE = RESULTS / "SIM13_V4B2_PRE_AUDIT_GATE_V1.json"
AUDIT_RECEIPT = EVIDENCE / "SIM13_V4B2_INDEPENDENT_AUDIT_RECEIPT_V1.json"
FINAL_GATE = RESULTS / "SIM13_V4B2_AUDITED_GATE_V1.json"
TERMINAL_MANIFEST = RESULTS / "SIM13_V4B2_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"

PHASE_A_MODEL = HERE.parent / "sim13_v4a/full_floating.py"
PHASE_A_GATE = HERE.parent / "results/SIM13_V4A_PHASE_A_AUDITED_GATE_V3.json"
PHASE_B1_ROOT = HERE.parent / "phase_b1_frictionless_single_contact"
PHASE_B1_KERNEL = PHASE_B1_ROOT / "b1_contact/contact_kernel.py"
PHASE_B1_GATE = PHASE_B1_ROOT / "results/SIM13_V4B1_AUDITED_GATE_V1.json"

EXPECTED_PHASE_A_GATE_SHA = "82ECF267AA5F0DF0B79610AB4FBFD4DB4AE564EDE530A7F69AB579D1E15F7A40"
EXPECTED_PHASE_B1_GATE_SHA = "91F11FA541A336D9C3E073104CB15C215BCAEC4417090D9FA743D7D089604BE4"
EXPECTED_TEST_COUNT = 23
DURATION_S = 0.04

CONVERGENCE_ABSOLUTE_FLOORS = {
    "service_base_position_m": 1.0e-12,
    "service_base_quaternion_geodesic_rad": 5.0e-8,
    "service_q_R_rad": 1.0e-12,
    "service_q_P_m": 1.0e-12,
    "service_v_base_m_s": 1.0e-12,
    "service_omega_base_rad_s": 1.0e-14,
    "service_qdot_R_rad_s": 1.0e-12,
    "service_qdot_P_m_s": 1.0e-12,
    "target_position_m": 1.0e-12,
    "target_quaternion_geodesic_rad": 5.0e-8,
    "target_velocity_m_s": 1.0e-12,
    "target_omega_rad_s": 1.0e-14,
}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _record(path: Path, role: str) -> dict[str, Any]:
    return {"role": role, "path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha(path)}


def _pytest() -> dict[str, Any]:
    collect = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=HERE, text=True, capture_output=True, check=False,
    )
    nodeids = [line.strip() for line in collect.stdout.splitlines() if "::" in line]
    execution = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=HERE, text=True, capture_output=True, check=False,
    )
    match = re.search(r"(\d+) passed", execution.stdout)
    return {
        "collection_return_code": collect.returncode,
        "execution_return_code": execution.returncode,
        "collected_nodeids": nodeids,
        "collected_count": len(nodeids),
        "expected_count": EXPECTED_TEST_COUNT,
        "passed": int(match.group(1)) if match else 0,
        "stdout_tail": execution.stdout.strip().splitlines()[-4:],
        "stderr": execution.stderr.strip(),
    }


def _component_difference(left, right) -> dict[str, float]:
    return {
        "service_base_position_m": float(np.linalg.norm(left.service_base_position_inertial_m[-1] - right.service_base_position_inertial_m[-1])),
        "service_base_quaternion_geodesic_rad": quaternion_geodesic(left.service_base_quaternion_body_to_inertial_wxyz[-1], right.service_base_quaternion_body_to_inertial_wxyz[-1]),
        "service_q_R_rad": float(np.max(np.abs(left.service_joint_coordinates_mixed[-1, :6] - right.service_joint_coordinates_mixed[-1, :6]))),
        "service_q_P_m": float(np.max(np.abs(left.service_joint_coordinates_mixed[-1, 6:] - right.service_joint_coordinates_mixed[-1, 6:]))),
        "service_v_base_m_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, :3] - right.service_nu_s_mixed[-1, :3]))),
        "service_omega_base_rad_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, 3:6] - right.service_nu_s_mixed[-1, 3:6]))),
        "service_qdot_R_rad_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, 6:12] - right.service_nu_s_mixed[-1, 6:12]))),
        "service_qdot_P_m_s": float(np.max(np.abs(left.service_nu_s_mixed[-1, 12:] - right.service_nu_s_mixed[-1, 12:]))),
        "target_position_m": float(np.linalg.norm(left.target_position_inertial_m[-1] - right.target_position_inertial_m[-1])),
        "target_quaternion_geodesic_rad": quaternion_geodesic(left.target_quaternion_body_to_inertial_wxyz[-1], right.target_quaternion_body_to_inertial_wxyz[-1]),
        "target_velocity_m_s": float(np.max(np.abs(left.target_twist_inertial_mixed[-1, :3] - right.target_twist_inertial_mixed[-1, :3]))),
        "target_omega_rad_s": float(np.max(np.abs(left.target_twist_inertial_mixed[-1, 3:] - right.target_twist_inertial_mixed[-1, 3:]))),
    }


def _assessment(coarse: dict[str, float], fine: dict[str, float]) -> dict[str, Any]:
    components = {}
    for key, coarse_error in coarse.items():
        floor = CONVERGENCE_ABSOLUTE_FLOORS[key]
        fine_error = fine[key]
        decreased = fine_error < coarse_error
        floored = coarse_error <= floor and fine_error <= floor
        components[key] = {
            "coarse_error": coarse_error, "fine_error": fine_error,
            "absolute_floor_native_unit": floor, "strictly_decreased": decreased,
            "both_below_absolute_floor": floored, "pass": decreased or floored,
        }
    return {
        "rule": "FINE_LT_COARSE_OR_BOTH_LE_DECLARED_ABSOLUTE_FLOOR",
        "components": components,
        "all_components_pass": all(value["pass"] for value in components.values()),
    }


def _event_difference(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    return {key: abs(float(left[key]) - float(right[key])) for key in (
        "first_contact_time_s", "separation_after_contact_time_s",
        "peak_normal_force_n", "maximum_penetration_m",
    )}


def _terminal_payload(history, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": history.method, "step_s": history.step_s,
        "time_s": history.time_s.tolist(), "gap_m": history.gap_m.tolist(),
        "penetration_m": history.penetration_m.tolist(),
        "normal_force_magnitude_n": history.normal_force_magnitude_n.tolist(),
        "final_state": {
            "service_base_position_inertial_m": history.service_base_position_inertial_m[-1].tolist(),
            "service_base_quaternion_body_to_inertial_wxyz": history.service_base_quaternion_body_to_inertial_wxyz[-1].tolist(),
            "service_joint_coordinates_mixed": history.service_joint_coordinates_mixed[-1].tolist(),
            "service_nu_s_mixed": history.service_nu_s_mixed[-1].tolist(),
            "target_position_inertial_m": history.target_position_inertial_m[-1].tolist(),
            "target_quaternion_body_to_inertial_wxyz": history.target_quaternion_body_to_inertial_wxyz[-1].tolist(),
            "target_twist_inertial_mixed": history.target_twist_inertial_mixed[-1].tolist(),
        },
        "declared_event": summary["contact_event"],
    }


def _reference_records(history) -> list[dict[str, Any]]:
    records = []
    for index, time_s in enumerate(history.time_s):
        records.append({
            "time_s": float(time_s),
            "service": {
                "base_position_inertial_m": history.service_base_position_inertial_m[index].tolist(),
                "base_quaternion_body_to_inertial_wxyz": history.service_base_quaternion_body_to_inertial_wxyz[index].tolist(),
                "joint_coordinates_mixed": history.service_joint_coordinates_mixed[index].tolist(),
                "nu_s_mixed": history.service_nu_s_mixed[index].tolist(),
            },
            "target": {
                "position_inertial_m": history.target_position_inertial_m[index].tolist(),
                "quaternion_body_to_inertial_wxyz": history.target_quaternion_body_to_inertial_wxyz[index].tolist(),
                "twist_inertial_mixed": history.target_twist_inertial_mixed[index].tolist(),
            },
            "contact": {
                "gap_m": float(history.gap_m[index]),
                "penetration_m": float(history.penetration_m[index]),
                "normal_target_to_pad_inertial": history.normal_target_to_pad_inertial[index].tolist(),
                "common_contact_point_inertial_m": history.common_contact_point_inertial_m[index].tolist(),
                "pad_point_inertial_m": history.pad_point_inertial_m[index].tolist(),
                "service_common_point_velocity_inertial_m_s": history.service_common_point_velocity_inertial_m_s[index].tolist(),
                "target_common_point_velocity_inertial_m_s": history.target_common_point_velocity_inertial_m_s[index].tolist(),
                "relative_tangential_velocity_inertial_m_s": history.relative_tangential_velocity_inertial_m_s[index].tolist(),
                "relative_tangential_speed_m_s": float(history.relative_tangential_speed_m_s[index]),
                "normal_force_magnitude_n": float(history.normal_force_magnitude_n[index]),
                "normal_force_service_inertial_n": history.normal_force_service_inertial_n[index].tolist(),
                "tangential_force_service_inertial_n": history.tangential_force_service_inertial_n[index].tolist(),
                "service_force_inertial_n": history.service_force_inertial_n[index].tolist(),
                "target_force_inertial_n": history.target_force_inertial_n[index].tolist(),
                "service_shift_torque_inertial_n_m": history.service_shift_torque_inertial_n_m[index].tolist(),
                "service_generalized_contact_effort_mixed": history.service_generalized_contact_effort_mixed[index].tolist(),
                "target_torque_about_com_inertial_n_m": history.target_torque_about_com_inertial_n_m[index].tolist(),
                "normal_dissipation_rate_w": float(history.normal_dissipation_rate_w[index]),
                "friction_dissipation_rate_w": float(history.friction_dissipation_rate_w[index]),
            },
            "integrated": {
                "normal_dissipation_j": float(history.cumulative_normal_dissipation_j[index]),
                "friction_dissipation_j": float(history.cumulative_friction_dissipation_j[index]),
                "service_impulse_n_s": history.cumulative_service_impulse_n_s[index].tolist(),
                "service_angular_impulse_n_m_s": history.cumulative_service_angular_impulse_about_origin_n_m_s[index].tolist(),
            },
        })
    return records


def _forbidden_scan() -> dict[str, Any]:
    found = []
    for path in HERE.rglob("*"):
        name = path.name.lower()
        if path.is_dir() and name in {"__pycache__", ".pytest_cache"}:
            found.append(path.relative_to(HERE).as_posix())
        elif path.is_file() and (name.endswith(".urdf") or "authorization" in name or "interface" in name):
            found.append(path.relative_to(HERE).as_posix())
    return {"pass": not found, "count": len(found), "paths": sorted(found)}


def _check(check_id: str, name: str, passed: bool, metrics: Any) -> dict[str, Any]:
    return {"id": check_id, "name": name, "pass": bool(passed), "metrics": metrics}


def main() -> int:
    for stale in (AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST):
        if stale.is_file():
            stale.unlink()
    source_paths = [
        (PHASE_A_MODEL, "UPSTREAM_PHASE_A_MODEL"),
        (PHASE_A_GATE, "UPSTREAM_PHASE_A_GATE"),
        (PHASE_B1_KERNEL, "UPSTREAM_PHASE_B1_KERNEL"),
        (PHASE_B1_GATE, "UPSTREAM_PHASE_B1_FINAL_GATE"),
        (HERE / "contracts/PHASE_B2_MODEL_CONTRACT_V1.json", "MODEL_CONTRACT"),
        (HERE / "contracts/PHASE_B2_GOVERNANCE_CONTRACT_V1.json", "GOVERNANCE_CONTRACT"),
        (HERE / "b2_contact/__init__.py", "PACKAGE_SOURCE"),
        (HERE / "b2_contact/friction_kernel.py", "FRICTION_KERNEL_SOURCE"),
        (HERE / "README.md", "SCOPE_README"),
        (HERE / "pytest.ini", "PYTEST_CONFIG"),
        (HERE / "validate_phase_b2.py", "VALIDATOR_SOURCE"),
        (HERE / "independent_audit_phase_b2.py", "INDEPENDENT_AUDIT_SOURCE"),
    ]
    source_paths.extend((path, "TEST_SOURCE") for path in sorted((HERE / "tests").glob("*.py")))
    source_manifest = {
        "schema": "SIM13_V4B2_SOURCE_MANIFEST_V1",
        "scope": "SYNTHETIC_REGULARIZED_FRICTION_SINGLE_CONTACT_ONLY",
        "records": [_record(path, role) for path, role in source_paths],
        "generated_outputs_excluded": [_relative(path) for path in (
            SOURCE_MANIFEST, TRACE, LEDGER, VALIDATION, EVIDENCE_MANIFEST,
            PRE_AUDIT_GATE, AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST,
        )],
    }
    _write(SOURCE_MANIFEST, source_manifest)
    tests = _pytest()

    model, service, target, config = deterministic_friction_scenario()
    specs = {
        "rk4_coarse": ("rk4", 1.0e-3), "rk4_fine": ("rk4", 5.0e-4),
        "rk4_reference": ("rk4", 2.5e-4),
        "midpoint_coarse": ("midpoint", 5.0e-4),
        "midpoint_fine": ("midpoint", 2.5e-4),
        "midpoint_reference": ("midpoint", 1.25e-4),
    }
    histories = {
        name: integrate_friction_contact(
            model, service, target, config,
            step_s=step, duration_s=DURATION_S, method=method,
        )
        for name, (method, step) in specs.items()
    }
    summaries = {name: summarize_friction_history(history, config) for name, history in histories.items()}
    reference = histories["rk4_reference"]
    reference_summary = summaries["rk4_reference"]
    controls = run_negative_controls(reference, config)
    no_contact = no_contact_regression()
    rk_coarse = _component_difference(histories["rk4_coarse"], histories["rk4_fine"])
    rk_fine = _component_difference(histories["rk4_fine"], histories["rk4_reference"])
    mp_coarse = _component_difference(histories["midpoint_coarse"], histories["midpoint_fine"])
    mp_fine = _component_difference(histories["midpoint_fine"], histories["midpoint_reference"])
    convergence = {
        "rk4": {"coarse": rk_coarse, "fine": rk_fine, "assessment": _assessment(rk_coarse, rk_fine)},
        "midpoint": {"coarse": mp_coarse, "fine": mp_fine, "assessment": _assessment(mp_coarse, mp_fine)},
        "cross_integrator": {
            "components": _component_difference(histories["rk4_reference"], histories["midpoint_reference"]),
            "events": _event_difference(summaries["rk4_reference"]["contact_event"], summaries["midpoint_reference"]["contact_event"]),
        },
    }
    trace = {
        "schema": "SIM13_V4B2_FRICTION_TRACE_V1",
        "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        "scenario": {
            "sphere_radius_m": config.sphere_radius_m,
            "normal_stiffness_n_m": config.normal_stiffness_n_m,
            "normal_damping_n_s_m": config.normal_damping_n_s_m,
            "friction_coefficient": config.friction_coefficient,
            "tangential_regularization_speed_m_s": config.tangential_regularization_speed_m_s,
            "pad_link_index": config.pad_link_index,
            "pad_point_local_m": list(config.pad_point_local_m),
            "max_penetration_abort_m": config.max_penetration_abort_m,
        },
        "reference_method": "rk4", "reference_step_s": 2.5e-4,
        "reference_records": _reference_records(reference),
        "convergence_runs": {name: _terminal_payload(histories[name], summaries[name]) for name in specs},
    }
    _write(TRACE, trace)
    ledger = {
        "schema": "SIM13_V4B2_FRICTION_LEDGER_V1",
        "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        "upstream_trace": _record(TRACE, "UPSTREAM_RAW_TRACE"),
        "reference_summary": reference_summary,
        "convergence": convergence,
        "no_contact_regression": no_contact,
        "negative_controls": list(controls),
    }
    _write(LEDGER, ledger)

    geometry = reference_summary["geometry_and_force"]
    friction = reference_summary["friction"]
    linear = reference_summary["linear_momentum_n_s"]
    angular = reference_summary["angular_momentum_about_common_inertial_origin_n_m_s"]
    energy = reference_summary["energy_j"]
    cross = convergence["cross_integrator"]["events"]
    forbidden = _forbidden_scan()
    checks = [
        _check("VB2-01", "Phase A and B1 audited upstream hashes", _sha(PHASE_A_GATE) == EXPECTED_PHASE_A_GATE_SHA and _sha(PHASE_B1_GATE) == EXPECTED_PHASE_B1_GATE_SHA, {"phase_a": _sha(PHASE_A_GATE), "phase_b1": _sha(PHASE_B1_GATE)}),
        _check("VB2-02", "fixed pytest inventory", tests["collection_return_code"] == 0 and tests["execution_return_code"] == 0 and tests["collected_count"] == EXPECTED_TEST_COUNT and tests["passed"] == EXPECTED_TEST_COUNT, tests),
        _check("VB2-03", "single-contact transition sequence including initial separated state", [item["to"] for item in reference_summary["state_machine"]["transition_log"]] == ["SEPARATED", "APPROACH", "SINGLE_CONTACT", "SEPARATING_AFTER_CONTACT"], reference_summary["state_machine"]),
        _check("VB2-04", "nominal integration not aborted", not reference.aborted_safe, reference_summary["state_machine"]),
        _check("VB2-05", "action reaction", geometry["action_reaction_max_error_n"] <= 1.0e-12, geometry),
        _check("VB2-06", "normal projection", geometry["normal_projection_max_error_n"] <= 1.0e-12, geometry),
        _check("VB2-07", "tangential orthogonality", geometry["tangential_orthogonality_max_error_n"] <= 1.0e-12, geometry),
        _check("VB2-08", "regularized Coulomb bound", geometry["friction_cone_max_excess_n"] <= 1.0e-12, geometry),
        _check("VB2-09", "common point service wrench shift", geometry["service_common_point_wrench_shift_max_error_n_m"] <= 1.0e-12, geometry),
        _check("VB2-10", "no separated force", geometry["separated_total_force_max_n"] <= 1.0e-12 and geometry["separated_tangential_force_max_n"] <= 1.0e-12, geometry),
        _check("VB2-11", "friction never injects power", friction["maximum_friction_power_w"] <= 1.0e-14 and friction["minimum_friction_dissipation_rate_w"] >= 0.0, friction),
        _check("VB2-12", "friction response is active", friction["peak_tangential_force_n"] > 0.1 and friction["final_friction_dissipation_j"] > 0.0 and friction["friction_changes_target_spin_rad_s"] > 1.0e-5, friction),
        _check("VB2-13", "service linear impulse ledger", linear["service_delta_minus_impulse_max_error_n_s"] <= 1.0e-10, linear),
        _check("VB2-14", "target linear impulse ledger", linear["target_delta_plus_impulse_max_error_n_s"] <= 1.0e-10, linear),
        _check("VB2-15", "total linear momentum", linear["total_max_drift_n_s"] <= 1.0e-10, linear),
        _check("VB2-16", "service angular impulse ledger", angular["service_delta_minus_angular_impulse_max_error_n_m_s"] <= 1.0e-10, angular),
        _check("VB2-17", "target angular impulse ledger", angular["target_delta_plus_angular_impulse_max_error_n_m_s"] <= 1.0e-10, angular),
        _check("VB2-18", "total angular momentum", angular["total_max_drift_n_m_s"] <= 1.0e-10, angular),
        _check("VB2-19", "T plus U plus normal/friction dissipation", energy["total_mechanical_plus_dissipated_max_drift_j"] <= 1.0e-6, energy),
        _check("VB2-20", "no-contact regression", max(no_contact.values()) <= 2.0e-14, no_contact),
        _check("VB2-21", "RK4 step-halving", convergence["rk4"]["assessment"]["all_components_pass"], convergence["rk4"]),
        _check("VB2-22", "midpoint step-halving", convergence["midpoint"]["assessment"]["all_components_pass"], convergence["midpoint"]),
        _check("VB2-23", "cross-integrator event convergence", cross["first_contact_time_s"] <= 2.0e-6 and cross["separation_after_contact_time_s"] <= 5.0e-6 and cross["peak_normal_force_n"] <= 2.0e-2 and cross["maximum_penetration_m"] <= 2.0e-6, convergence["cross_integrator"]),
        _check("VB2-24", "ten negative controls", len(controls) == 10 and all(item["mutation_rejected"] for item in controls), controls),
        _check("VB2-25", "formal physical current production release boundaries false", not any((PHYSICAL_FRICTION_IDENTIFIED, DUAL_CONTACT_IMPLEMENTED, SOFT_CAPTURE_IMPLEMENTED, LOCK_IMPLEMENTED, GRASP_SUCCESS_CLAIMED, CURRENT_SYSTEM_BOUND, PRODUCTION_CONTACT_BACKEND, FORMAL_NC19_CREDIT, RELEASE_AUTHORIZED, NEXT_STAGE_AUTHORIZED)), {"all_required_false": True}),
        _check("VB2-26", "no forbidden generated artifacts", forbidden["pass"], forbidden),
    ]
    passed = sum(item["pass"] for item in checks)
    validation = {
        "schema": "SIM13_V4B2_VALIDATION_V1",
        "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        "upstream_trace": _record(TRACE, "UPSTREAM_RAW_TRACE"),
        "upstream_ledger": _record(LEDGER, "UPSTREAM_LEDGER"),
        "status": "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" if passed == len(checks) else "FAIL_VALIDATOR",
        "score": {"pass": passed, "fail": len(checks) - passed, "total": len(checks)},
        "checks": checks,
    }
    _write(VALIDATION, validation)
    evidence_manifest = {
        "schema": "SIM13_V4B2_EVIDENCE_MANIFEST_V1",
        "acyclic": True, "self_excluded": True,
        "records": [
            _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
            _record(TRACE, "UPSTREAM_RAW_TRACE"),
            _record(LEDGER, "UPSTREAM_LEDGER"),
            _record(VALIDATION, "UPSTREAM_VALIDATION"),
        ],
    }
    _write(EVIDENCE_MANIFEST, evidence_manifest)
    pre_audit = {
        "schema": "SIM13_V4B2_PRE_AUDIT_GATE_V1",
        "overall_status": "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" if passed == len(checks) else "FAIL_VALIDATOR",
        "final_gate": False,
        "upstream_evidence_manifest": _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
        "validator_checks": validation["score"],
        "authorizations": {
            "synthetic_phase_b2_audited_ready": False,
            "physical_friction_identified": False, "dual_contact_ready": False,
            "soft_capture_ready": False, "lock_ready": False,
            "contact_grasp_passed": False, "current_system_bound": False,
            "formal_nc19_closed": False, "owner_authorized": False,
            "production_ready": False, "released": False, "next_stage_authorized": False,
        },
        "formal_sim13_v2_state": {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"], "changed_by_this_package": False},
    }
    _write(PRE_AUDIT_GATE, pre_audit)
    print(json.dumps({
        "status": validation["status"], "checks": validation["score"],
        "tests": {"passed": tests["passed"], "expected": EXPECTED_TEST_COUNT},
        "contact_event": reference_summary["contact_event"],
        "friction": friction, "linear": linear, "angular": angular,
        "energy": energy, "pre_audit_gate_sha256": _sha(PRE_AUDIT_GATE),
    }, indent=2))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
