"""Generate Phase-B1 evidence and a non-final pre-audit Gate.

The validator never emits the final audited Gate.  That authority belongs only
to independent_audit_phase_b1.py after it has independently reconstructed the
geometry, force, impulse, P/H/E+D and evidence DAG.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import numpy as np

from b1_contact import (
    deterministic_contact_scenario,
    integrate_contact,
    no_contact_regression,
    run_negative_controls,
    summarize_history,
)
from b1_contact.contact_kernel import (
    CURRENT_SYSTEM_BOUND,
    FORMAL_NC19_CREDIT,
    GRASP_SUCCESS_CLAIMED,
    NEXT_STAGE_AUTHORIZED,
    PRODUCTION_CONTACT_BACKEND,
    RELEASE_AUTHORIZED,
)
from sim13_v4a.full_floating import quaternion_geodesic


HERE = Path(__file__).resolve().parent
PHASE_A = HERE.parent
PROJECT_ROOT = HERE.parents[3]
EVIDENCE = HERE / "evidence"
RESULTS = HERE / "results"

SOURCE_MANIFEST = EVIDENCE / "SIM13_V4B1_SOURCE_MANIFEST_V1.json"
TRACE = EVIDENCE / "SIM13_V4B1_CONTACT_TRACE_V1.json"
LEDGER = EVIDENCE / "SIM13_V4B1_CONTACT_LEDGER_V1.json"
VALIDATION = EVIDENCE / "SIM13_V4B1_VALIDATION_V1.json"
EVIDENCE_MANIFEST = EVIDENCE / "SIM13_V4B1_EVIDENCE_MANIFEST_V1.json"
PRE_AUDIT_GATE = RESULTS / "SIM13_V4B1_PRE_AUDIT_GATE_V1.json"
AUDIT_RECEIPT = EVIDENCE / "SIM13_V4B1_INDEPENDENT_AUDIT_RECEIPT_V1.json"
FINAL_GATE = RESULTS / "SIM13_V4B1_AUDITED_GATE_V1.json"
TERMINAL_MANIFEST = RESULTS / "SIM13_V4B1_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"

PHASE_A_MODEL = PHASE_A / "sim13_v4a/full_floating.py"
PHASE_A_GATE = PHASE_A / "results/SIM13_V4A_PHASE_A_AUDITED_GATE_V3.json"
EXPECTED_PHASE_A_MODEL_SHA = "3EC187C850F72EB1CAFF18713C71D6D0AC1773AF6C7AA8BFF4285FC26055C998"
EXPECTED_PHASE_A_GATE_SHA = "82ECF267AA5F0DF0B79610AB4FBFD4DB4AE564EDE530A7F69AB579D1E15F7A40"

EXPECTED_TEST_COUNT = 27
DURATION_S = 0.04

# Step-halving is accepted component-by-component only when the fine error is
# strictly smaller, or when both errors are already below a declared absolute
# numerical-resolution floor in that component's native unit.  In particular,
# quaternion_geodesic uses acos and resolves identical double-precision unit
# quaternions at O(sqrt(eps)) rather than at O(eps).
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _record(path: Path, role: str) -> dict[str, Any]:
    return {"role": role, "path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha(path)}


def _source_paths() -> list[Path]:
    paths = [
        HERE / "README.md",
        HERE / "pytest.ini",
        HERE / "validate_phase_b1.py",
        HERE / "independent_audit_phase_b1.py",
        HERE / "contracts/PHASE_B1_MODEL_CONTRACT_V1.json",
        HERE / "contracts/PHASE_B1_GOVERNANCE_CONTRACT_V1.json",
    ]
    paths.extend(sorted((HERE / "b1_contact").glob("*.py")))
    paths.extend(sorted((HERE / "tests").glob("*.py")))
    return sorted(set(paths), key=_relative)


def _run_tests() -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    collect = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=HERE,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    nodeids = [line.strip() for line in collect.stdout.splitlines() if "::" in line]
    execution = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=HERE,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
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


def _event_difference(left_summary: dict[str, Any], right_summary: dict[str, Any]) -> dict[str, float]:
    left = left_summary["contact_event"]
    right = right_summary["contact_event"]
    return {
        "first_contact_time_s": abs(left["first_contact_time_s"] - right["first_contact_time_s"]),
        "separation_after_contact_time_s": abs(left["separation_after_contact_time_s"] - right["separation_after_contact_time_s"]),
        "peak_normal_force_n": abs(left["peak_normal_force_n"] - right["peak_normal_force_n"]),
        "maximum_penetration_m": abs(left["maximum_penetration_m"] - right["maximum_penetration_m"]),
    }


def _step_halving_assessment(coarse: dict[str, float], fine: dict[str, float]) -> dict[str, Any]:
    components: dict[str, Any] = {}
    for key, coarse_error in coarse.items():
        fine_error = fine[key]
        floor = CONVERGENCE_ABSOLUTE_FLOORS[key]
        strictly_decreased = fine_error < coarse_error
        both_below_floor = coarse_error <= floor and fine_error <= floor
        components[key] = {
            "coarse_error": coarse_error,
            "fine_error": fine_error,
            "absolute_floor_native_unit": floor,
            "strictly_decreased": strictly_decreased,
            "both_below_absolute_floor": both_below_floor,
            "pass": strictly_decreased or both_below_floor,
        }
    return {
        "rule": "FINE_LT_COARSE_OR_BOTH_LE_DECLARED_ABSOLUTE_FLOOR",
        "components": components,
        "all_components_pass": all(item["pass"] for item in components.values()),
    }


def _convergence(histories: dict[str, Any], summaries: dict[str, Any]) -> dict[str, Any]:
    rk4_coarse = _component_difference(histories["rk4_coarse"], histories["rk4_fine"])
    rk4_fine = _component_difference(histories["rk4_fine"], histories["rk4_reference"])
    midpoint_coarse = _component_difference(histories["midpoint_coarse"], histories["midpoint_fine"])
    midpoint_fine = _component_difference(histories["midpoint_fine"], histories["midpoint_reference"])
    rk4_assessment = _step_halving_assessment(rk4_coarse, rk4_fine)
    midpoint_assessment = _step_halving_assessment(midpoint_coarse, midpoint_fine)
    return {
        "rk4_step_halving": {
            "coarse_dt_s": 1.0e-3,
            "fine_dt_s": 5.0e-4,
            "reference_dt_s": 2.5e-4,
            "coarse_to_fine_difference": rk4_coarse,
            "fine_to_reference_difference": rk4_fine,
            "component_assessment": rk4_assessment,
            "all_component_errors_decrease_or_are_below_floor": rk4_assessment["all_components_pass"],
            "event_coarse_to_fine": _event_difference(summaries["rk4_coarse"], summaries["rk4_fine"]),
            "event_fine_to_reference": _event_difference(summaries["rk4_fine"], summaries["rk4_reference"]),
        },
        "independent_midpoint_step_halving": {
            "coarse_dt_s": 5.0e-4,
            "fine_dt_s": 2.5e-4,
            "reference_dt_s": 1.25e-4,
            "coarse_to_fine_difference": midpoint_coarse,
            "fine_to_reference_difference": midpoint_fine,
            "component_assessment": midpoint_assessment,
            "all_component_errors_decrease_or_are_below_floor": midpoint_assessment["all_components_pass"],
            "event_coarse_to_fine": _event_difference(summaries["midpoint_coarse"], summaries["midpoint_fine"]),
            "event_fine_to_reference": _event_difference(summaries["midpoint_fine"], summaries["midpoint_reference"]),
        },
        "cross_integrator_reference": {
            "rk4_dt_s": 2.5e-4,
            "midpoint_dt_s": 1.25e-4,
            "component_difference": _component_difference(histories["rk4_reference"], histories["midpoint_reference"]),
            "event_difference": _event_difference(summaries["rk4_reference"], summaries["midpoint_reference"]),
        },
    }


def _terminal_payload(history, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": history.method,
        "step_s": history.step_s,
        "time_s": history.time_s.tolist(),
        "gap_m": history.gap_m.tolist(),
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
        "validator_event_summary": summary["contact_event"],
    }


def _reference_records(history) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, time_s in enumerate(history.time_s):
        records.append(
            {
                "index": index,
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
                    "pad_velocity_inertial_m_s": history.pad_velocity_inertial_m_s[index].tolist(),
                    "target_surface_velocity_inertial_m_s": history.target_surface_velocity_inertial_m_s[index].tolist(),
                    "relative_velocity_inertial_m_s": history.relative_velocity_inertial_m_s[index].tolist(),
                    "relative_normal_speed_m_s": float(history.relative_normal_speed_m_s[index]),
                    "normal_force_magnitude_n": float(history.normal_force_magnitude_n[index]),
                    "service_force_inertial_n": history.service_force_inertial_n[index].tolist(),
                    "target_force_inertial_n": history.target_force_inertial_n[index].tolist(),
                    "service_generalized_contact_effort_mixed": history.service_generalized_contact_effort_mixed[index].tolist(),
                    "target_torque_about_com_inertial_n_m": history.target_torque_about_com_inertial_n_m[index].tolist(),
                },
                "integrals": {
                    "service_impulse_n_s": history.cumulative_service_impulse_n_s[index].tolist(),
                    "service_angular_impulse_about_origin_n_m_s": history.cumulative_service_angular_impulse_about_origin_n_m_s[index].tolist(),
                    "dissipation_j": float(history.cumulative_dissipation_j[index]),
                },
                "primary_ledgers": {
                    "service_linear_momentum_n_s": history.service_linear_momentum_n_s[index].tolist(),
                    "service_angular_momentum_about_origin_n_m_s": history.service_angular_momentum_about_origin_n_m_s[index].tolist(),
                    "target_linear_momentum_n_s": history.target_linear_momentum_n_s[index].tolist(),
                    "target_angular_momentum_about_origin_n_m_s": history.target_angular_momentum_about_origin_n_m_s[index].tolist(),
                    "service_kinetic_energy_j": float(history.service_kinetic_energy_j[index]),
                    "target_kinetic_energy_j": float(history.target_kinetic_energy_j[index]),
                    "elastic_energy_j": float(history.elastic_energy_j[index]),
                },
                "state_label": history.state_label[index],
            }
        )
    return records


def _scan_forbidden() -> dict[str, Any]:
    forbidden: list[str] = []
    for path in HERE.rglob("*"):
        relative = path.relative_to(HERE).as_posix()
        lower = path.name.lower()
        if path.is_dir() and lower in {"__pycache__", ".pytest_cache"}:
            forbidden.append(relative)
        elif path.is_file() and (
            lower.endswith(".urdf") or "interface" in lower or "authorization" in lower
        ):
            forbidden.append(relative)
    return {"forbidden_count": len(forbidden), "paths": sorted(forbidden), "pass": not forbidden}


def _check(check_id: str, name: str, passed: bool, metrics: Any) -> dict[str, Any]:
    return {"id": check_id, "name": name, "pass": bool(passed), "metrics": metrics}


def main() -> int:
    for stale in (AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST):
        if stale.is_file():
            stale.unlink()

    source_records = [_record(path, "B1_FROZEN_SOURCE_INPUT") for path in _source_paths()]
    source_records.extend(
        (
            _record(PHASE_A_MODEL, "PHASE_A_V3_PUBLIC_MODEL_UPSTREAM"),
            _record(PHASE_A_GATE, "PHASE_A_V3_AUDITED_GATE_UPSTREAM"),
        )
    )
    source_payload = {
        "schema": "SIM13_V4B1_SOURCE_MANIFEST_V1",
        "self_excluded_path": _relative(SOURCE_MANIFEST),
        "records": source_records,
        "generated_outputs_excluded": [_relative(path) for path in (SOURCE_MANIFEST, TRACE, LEDGER, VALIDATION, EVIDENCE_MANIFEST, PRE_AUDIT_GATE, AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST)],
    }
    _write_json(SOURCE_MANIFEST, source_payload)
    source_reference = _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST")

    tests = _run_tests()
    model, service, target, config = deterministic_contact_scenario()
    run_specs = {
        "rk4_coarse": (1.0e-3, "rk4"),
        "rk4_fine": (5.0e-4, "rk4"),
        "rk4_reference": (2.5e-4, "rk4"),
        "midpoint_coarse": (5.0e-4, "midpoint"),
        "midpoint_fine": (2.5e-4, "midpoint"),
        "midpoint_reference": (1.25e-4, "midpoint"),
    }
    histories = {
        name: integrate_contact(model, service, target, config, step_s=step_s, duration_s=DURATION_S, method=method)
        for name, (step_s, method) in run_specs.items()
    }
    summaries = {name: summarize_history(history) for name, history in histories.items()}
    convergence = _convergence(histories, summaries)
    reference_history = histories["rk4_reference"]
    reference_summary = summaries["rk4_reference"]
    negative_controls = list(run_negative_controls(reference_history, config))
    no_contact = no_contact_regression(step_s=5.0e-4, steps=8)
    forbidden = _scan_forbidden()

    trace_payload = {
        "schema": "SIM13_V4B1_CONTACT_TRACE_V1",
        "hash_chain": {"upstream_source_manifest": source_reference},
        "scenario": {
            "deterministic": True,
            "rng_used": False,
            "duration_s": DURATION_S,
            "sphere_radius_m": config.sphere_radius_m,
            "normal_stiffness_n_m": config.normal_stiffness_n_m,
            "normal_damping_n_s_m": config.normal_damping_n_s_m,
            "pad_link_index": config.pad_link_index,
            "pad_point_local_m": list(config.pad_point_local_m),
            "max_penetration_abort_m": config.max_penetration_abort_m,
            "parameter_status": "SYNTHETIC_PROVISIONAL_NOT_B601",
        },
        "reference_run": {"method": reference_history.method, "step_s": reference_history.step_s, "records": _reference_records(reference_history)},
        "convergence_runs": {name: _terminal_payload(histories[name], summaries[name]) for name in run_specs},
    }
    _write_json(TRACE, trace_payload)

    ledger_payload = {
        "schema": "SIM13_V4B1_CONTACT_LEDGER_V1",
        "hash_chain": {"upstream_source_manifest": source_reference, "upstream_contact_trace": _record(TRACE, "UPSTREAM_CONTACT_TRACE")},
        "reference_summary": reference_summary,
        "convergence": convergence,
        "no_contact_phase_a_v3_regression": no_contact,
        "negative_controls": negative_controls,
        "unit_partition": {
            "R": {"coordinate": "rad", "rate": "rad/s", "effort": "N*m"},
            "P": {"coordinate": "m", "rate": "m/s", "effort": "N"},
            "linear_momentum": "N*s",
            "angular_momentum_about_one_inertial_origin": "N*m*s",
            "energy": "J",
            "heterogeneous_norms_used": False,
        },
    }
    _write_json(LEDGER, ledger_payload)

    geometry = reference_summary["geometry_and_force"]
    linear = reference_summary["linear_momentum_n_s"]
    angular = reference_summary["angular_momentum_about_common_inertial_origin_n_m_s"]
    energy = reference_summary["energy_j"]
    event = reference_summary["contact_event"]
    mixed = reference_summary["mixed_joint_channels"]
    rk4 = convergence["rk4_step_halving"]
    midpoint = convergence["independent_midpoint_step_halving"]
    cross = convergence["cross_integrator_reference"]
    cross_event = cross["event_difference"]
    checks = [
        _check("VB1-01", "pytest exact count and pass", tests["execution_return_code"] == 0 and tests["collected_count"] == EXPECTED_TEST_COUNT and tests["passed"] == EXPECTED_TEST_COUNT, tests),
        _check("VB1-02", "Phase-A V3 public model and audited Gate hash binding", _sha(PHASE_A_MODEL) == EXPECTED_PHASE_A_MODEL_SHA and _sha(PHASE_A_GATE) == EXPECTED_PHASE_A_GATE_SHA, {"model_sha256": _sha(PHASE_A_MODEL), "gate_sha256": _sha(PHASE_A_GATE)}),
        _check("VB1-03", "deterministic provisional synthetic scenario", trace_payload["scenario"]["deterministic"] and not trace_payload["scenario"]["rng_used"] and trace_payload["scenario"]["parameter_status"] == "SYNTHETIC_PROVISIONAL_NOT_B601", trace_payload["scenario"]),
        _check("VB1-04", "sphere gap normal and common point geometry", geometry["normal_unit_max_error"] <= 1.0e-12 and geometry["common_point_radial_moment_max_error_n_m"] <= 1.0e-12, geometry),
        _check("VB1-05", "non-tensile unilateral normal force", geometry["separated_tensile_force_max_n"] == 0.0 and event["peak_normal_force_n"] > 0.0, {"separated_tensile_force_max_n": geometry["separated_tensile_force_max_n"], "peak_normal_force_n": event["peak_normal_force_n"]}),
        _check("VB1-06", "action reaction pair", geometry["action_reaction_max_error_n"] <= 1.0e-12, geometry["action_reaction_max_error_n"]),
        _check("VB1-07", "full floating base R P contact channels", mixed["R_peak_abs_contact_effort_n_m"] > 0.0 and mixed["P_peak_abs_contact_effort_n"] > 0.0, mixed),
        _check("VB1-08", "single common action point no spurious radial offset moment", geometry["common_point_radial_moment_max_error_n_m"] <= 1.0e-12, geometry["common_point_radial_moment_max_error_n_m"]),
        _check("VB1-09", "service linear momentum versus impulse", linear["service_delta_minus_impulse_max_error_n_s"] <= 1.0e-10, linear),
        _check("VB1-10", "target linear momentum versus opposite impulse", linear["target_delta_plus_impulse_max_error_n_s"] <= 1.0e-10, linear),
        _check("VB1-11", "combined linear momentum", linear["total_max_drift_n_s"] <= 1.0e-10, linear),
        _check("VB1-12", "service angular momentum versus common-point angular impulse", angular["service_delta_minus_angular_impulse_max_error_n_m_s"] <= 1.0e-10, angular),
        _check("VB1-13", "target angular momentum versus opposite common-point angular impulse", angular["target_delta_plus_angular_impulse_max_error_n_m_s"] <= 1.0e-10, angular),
        _check("VB1-14", "combined angular momentum about one inertial origin", angular["total_max_drift_n_m_s"] <= 1.0e-10, angular),
        _check("VB1-15", "kinetic elastic and dissipated energy", energy["peak_elastic_j"] > 0.0 and energy["final_dissipated_j"] > 0.0 and energy["total_mechanical_plus_dissipated_max_drift_j"] <= 1.0e-6, energy),
        _check("VB1-16", "minimal single-contact state machine", [item["to"] for item in reference_history.transition_log] == ["SEPARATED", "APPROACH", "SINGLE_CONTACT", "SEPARATING_AFTER_CONTACT"] and not reference_history.aborted_safe, reference_summary["state_machine"]),
        _check("VB1-17", "RK4 step-halving convergence with declared native-unit floors", rk4["all_component_errors_decrease_or_are_below_floor"], rk4),
        _check("VB1-18", "independent midpoint step-halving convergence with declared native-unit floors", midpoint["all_component_errors_decrease_or_are_below_floor"], midpoint),
        _check("VB1-19", "cross-integrator and event convergence", cross_event["first_contact_time_s"] <= 2.0e-6 and cross_event["separation_after_contact_time_s"] <= 5.0e-6 and cross_event["peak_normal_force_n"] <= 2.0e-2 and cross_event["maximum_penetration_m"] <= 2.0e-6, cross),
        _check("VB1-20", "no-contact limit matches Phase-A V3", max(no_contact.values()) <= 2.0e-14, no_contact),
        _check("VB1-21", "all eight raw mutations exceed threshold and are rejected", len(negative_controls) == 8 and all(item["raw_error_exceeds_threshold"] and item["guard_detected"] and item["mutation_rejected"] for item in negative_controls), negative_controls),
        _check("VB1-22", "complete synchronized contact log", all(len(getattr(reference_history, name)) == len(reference_history.time_s) for name in ("gap_m", "penetration_m", "normal_target_to_pad_inertial", "common_contact_point_inertial_m", "relative_velocity_inertial_m_s", "normal_force_magnitude_n", "service_force_inertial_n", "target_force_inertial_n")), {"samples": len(reference_history.time_s), "required_logged_fields": 8}),
        _check("VB1-23", "R P and P H dimensions remain separated", mixed["R_effort_unit"] == "N*m" and mixed["P_effort_unit"] == "N" and not ledger_payload["unit_partition"]["heterogeneous_norms_used"], {"mixed_joint_channels": mixed, "unit_partition": ledger_payload["unit_partition"]}),
        _check("VB1-24", "formal current production grasp release boundaries false", not any((CURRENT_SYSTEM_BOUND, PRODUCTION_CONTACT_BACKEND, FORMAL_NC19_CREDIT, GRASP_SUCCESS_CLAIMED, RELEASE_AUTHORIZED, NEXT_STAGE_AUTHORIZED)), {"current_system_bound": CURRENT_SYSTEM_BOUND, "production_contact_backend": PRODUCTION_CONTACT_BACKEND, "formal_nc19_credit": FORMAL_NC19_CREDIT, "grasp_success_claimed": GRASP_SUCCESS_CLAIMED, "release_authorized": RELEASE_AUTHORIZED, "next_stage_authorized": NEXT_STAGE_AUTHORIZED}),
        _check("VB1-25", "no forbidden URDF interface authorization cache artifacts", forbidden["pass"], forbidden),
    ]
    validation_payload = {
        "schema": "SIM13_V4B1_VALIDATION_V1",
        "hash_chain": {"upstream_source_manifest": source_reference, "upstream_contact_trace": _record(TRACE, "UPSTREAM_CONTACT_TRACE"), "upstream_contact_ledger": _record(LEDGER, "UPSTREAM_CONTACT_LEDGER")},
        "checks": checks,
        "summary": {"pass": sum(item["pass"] for item in checks), "fail": sum(not item["pass"] for item in checks), "total": len(checks)},
    }
    _write_json(VALIDATION, validation_payload)

    evidence_payload = {
        "schema": "SIM13_V4B1_EVIDENCE_MANIFEST_V1",
        "self_excluded_path": _relative(EVIDENCE_MANIFEST),
        "upstream_source_manifest": source_reference,
        "records": [_record(TRACE, "CONTACT_TRACE"), _record(LEDGER, "CONTACT_LEDGER"), _record(VALIDATION, "VALIDATION_EVIDENCE")],
    }
    _write_json(EVIDENCE_MANIFEST, evidence_payload)
    passed = validation_payload["summary"]["fail"] == 0
    pre_audit_payload = {
        "schema": "SIM13_V4B1_PRE_AUDIT_GATE_V1",
        "overall_status": "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" if passed else "FAIL_VALIDATOR_PHASE_B1",
        "pre_audit_gate": True,
        "final_gate": False,
        "hash_chain": {"upstream_source_manifest": source_reference, "upstream_evidence_manifest": _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST")},
        "validator_checks": validation_payload["summary"],
        "authorizations": {
            "synthetic_phase_b1_validator_pass": passed,
            "independent_audit_pass": False,
            "formal_contact_backend": False,
            "friction_ready": False,
            "lock_ready": False,
            "contact_grasp_passed": False,
            "current_system_bound": False,
            "formal_nc19_closed": False,
            "owner_authorized": False,
            "production_ready": False,
            "released": False,
            "next_stage_authorized": False,
        },
        "formal_sim13_v2_state": {"passed": 15, "declared": 20, "dependency_hold": 5, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"], "changed_by_this_package": False},
    }
    _write_json(PRE_AUDIT_GATE, pre_audit_payload)
    print(json.dumps({"status": pre_audit_payload["overall_status"], "checks": validation_payload["summary"], "tests": {"passed": tests["passed"], "expected": EXPECTED_TEST_COUNT}, "reference_contact_event": event, "linear_momentum": linear, "angular_momentum": angular, "energy": energy, "pre_audit_gate_sha256": _sha(PRE_AUDIT_GATE)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
