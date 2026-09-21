"""Generate Phase-B3 evidence and a non-final pre-audit Gate.

The validator executes the B3 solver, but it is deliberately not the final
Gate issuer.  ``independent_audit_phase_b3.py`` must reconstruct the physics
from hash-bound raw evidence before any audited Phase-B3 ruling exists.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import numpy as np

from b3_contact import (
    BranchedGripperServiceModel,
    deterministic_dual_contact_scenario,
    integrate_dual_contact,
    summarize_dual_contact_history,
)
from b3_contact.dual_contact_kernel import (
    CURRENT_SYSTEM_BOUND,
    FORMAL_NC19_CREDIT,
    GRASP_SUCCESS_CLAIMED,
    LOCK_IMPLEMENTED,
    NEXT_STAGE_AUTHORIZED,
    PHYSICAL_ACTUATOR_TIMING_IDENTIFIED,
    PHYSICAL_DUAL_CONTACT_IDENTIFIED,
    PHYSICAL_FRICTION_IDENTIFIED,
    PRODUCTION_READY,
    RELEASE_AUTHORIZED,
    SOFT_CAPTURE_CURRENT_SYSTEM_PASSED,
    no_contact_regression,
    run_negative_controls,
)
from sim13_v4a.full_floating import quaternion_geodesic


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
EVIDENCE = HERE / "evidence"
RESULTS = HERE / "results"

SOURCE_MANIFEST = EVIDENCE / "SIM13_V4B3_SOURCE_MANIFEST_V1.json"
TRACE = EVIDENCE / "SIM13_V4B3_DUAL_CONTACT_TRACE_V1.json"
LEDGER = EVIDENCE / "SIM13_V4B3_DUAL_CONTACT_LEDGER_V1.json"
VALIDATION = EVIDENCE / "SIM13_V4B3_VALIDATION_V1.json"
EVIDENCE_MANIFEST = EVIDENCE / "SIM13_V4B3_EVIDENCE_MANIFEST_V1.json"
PRE_AUDIT_GATE = RESULTS / "SIM13_V4B3_PRE_AUDIT_GATE_V1.json"
AUDIT_RECEIPT = EVIDENCE / "SIM13_V4B3_INDEPENDENT_AUDIT_RECEIPT_V1.json"
FINAL_GATE = RESULTS / "SIM13_V4B3_AUDITED_GATE_V1.json"
TERMINAL_MANIFEST = RESULTS / "SIM13_V4B3_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"

PHASE_A_MODEL = HERE.parent / "sim13_v4a/full_floating.py"
PHASE_A_GATE = HERE.parent / "results/SIM13_V4A_PHASE_A_AUDITED_GATE_V3.json"
PHASE_B2_ROOT = HERE.parent / "phase_b2_regularized_friction_single_contact"
PHASE_B2_GATE = PHASE_B2_ROOT / "results/SIM13_V4B2_AUDITED_GATE_V1.json"
URDF = PROJECT_ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"

EXPECTED_PHASE_A_GATE_SHA = "82ECF267AA5F0DF0B79610AB4FBFD4DB4AE564EDE530A7F69AB579D1E15F7A40"
EXPECTED_PHASE_B2_GATE_SHA = "475FE497F8C302AB163A399362A20D322A4753DA557C0116015D21D0E17FD2DE"
EXPECTED_URDF_SHA = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
EXPECTED_TEST_COUNT = 44
DURATION_S = 0.08

RUN_SPECS = {
    "rk4_coarse": ("rk4", 1.0e-3),
    "rk4_fine": ("rk4", 5.0e-4),
    "rk4_reference": ("rk4", 2.5e-4),
    "midpoint_coarse": ("midpoint", 5.0e-4),
    "midpoint_fine": ("midpoint", 2.5e-4),
    "midpoint_reference": ("midpoint", 1.25e-4),
}

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

MIDPOINT_REFERENCE_ENVELOPE = {
    "service_base_position_m": 2.0e-6,
    "service_base_quaternion_geodesic_rad": 2.0e-5,
    "service_q_R_rad": 2.0e-5,
    "service_q_P_m": 2.0e-5,
    "service_v_base_m_s": 1.0e-3,
    "service_omega_base_rad_s": 1.0e-3,
    "service_qdot_R_rad_s": 1.0e-3,
    "service_qdot_P_m_s": 1.0e-3,
    "target_position_m": 2.0e-6,
    "target_quaternion_geodesic_rad": 2.0e-5,
    "target_velocity_m_s": 1.0e-3,
    "target_omega_rad_s": 1.0e-3,
}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _record(path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": _relative(path),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _pytest() -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    collect = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=HERE, text=True, capture_output=True, check=False, env=environment,
    )
    nodeids = [line.strip() for line in collect.stdout.splitlines() if "::" in line]
    execution = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=HERE, text=True, capture_output=True, check=False, env=environment,
    )
    match = re.search(r"(\d+) passed", execution.stdout)
    return {
        "collection_return_code": collect.returncode,
        "execution_return_code": execution.returncode,
        "collected_nodeids": nodeids,
        "collected_count": len(nodeids),
        "expected_count": EXPECTED_TEST_COUNT,
        "passed": int(match.group(1)) if match else 0,
        "stdout_tail": execution.stdout.strip().splitlines()[-5:],
        "stderr": execution.stderr.strip(),
    }


def _component_difference(left: Any, right: Any) -> dict[str, float]:
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


def _rk4_assessment(coarse: dict[str, float], fine: dict[str, float]) -> dict[str, Any]:
    components: dict[str, Any] = {}
    for key, coarse_error in coarse.items():
        floor = CONVERGENCE_ABSOLUTE_FLOORS[key]
        fine_error = fine[key]
        decreased = fine_error < coarse_error
        floored = coarse_error <= floor and fine_error <= floor
        components[key] = {
            "coarse_error": coarse_error,
            "fine_error": fine_error,
            "absolute_floor_native_unit": floor,
            "strictly_decreased": decreased,
            "both_below_absolute_floor": floored,
            "pass": decreased or floored,
        }
    return {
        "rule": "FINE_LT_COARSE_OR_BOTH_LE_DECLARED_ABSOLUTE_FLOOR",
        "components": components,
        "all_components_pass": all(item["pass"] for item in components.values()),
    }


def _midpoint_envelope(difference: dict[str, float]) -> dict[str, Any]:
    components = {
        key: {"error": value, "limit": MIDPOINT_REFERENCE_ENVELOPE[key], "pass": value <= MIDPOINT_REFERENCE_ENVELOPE[key]}
        for key, value in difference.items()
    }
    return {
        "rule": "NONSMOOTH_EVENT_ABSOLUTE_ENVELOPE__NO_FALSE_MONOTONICITY_CLAIM",
        "components": components,
        "all_components_pass": all(item["pass"] for item in components.values()),
    }


def _check(check_id: str, name: str, passed: bool, metrics: Any) -> dict[str, Any]:
    return {"id": check_id, "name": name, "pass": bool(passed), "metrics": metrics}


def _event_payload(history: Any, summary: dict[str, Any]) -> dict[str, Any]:
    transitions = summary["state_machine"]["transition_log"]
    candidate = [item for item in transitions if item["to"] == "SOFT_CAPTURE_TRANSIENT_CANDIDATE"]
    release = [item for item in transitions if item["to"] == "BILATERAL_RELEASE"]
    return {
        "left_first_contact_time_s": summary["per_contact"]["left"]["first_contact_time_s"],
        "right_first_contact_time_s": summary["per_contact"]["right"]["first_contact_time_s"],
        "left_separation_time_s": summary["per_contact"]["left"]["separation_after_contact_time_s"],
        "right_separation_time_s": summary["per_contact"]["right"]["separation_after_contact_time_s"],
        "candidate_transition_time_s": candidate[0]["time_s"] if candidate else None,
        "bilateral_release_transition_time_s": release[0]["time_s"] if release else None,
        "left_peak_normal_force_n": summary["per_contact"]["left"]["peak_normal_force_n"],
        "right_peak_normal_force_n": summary["per_contact"]["right"]["peak_normal_force_n"],
        "left_maximum_penetration_m": summary["per_contact"]["left"]["maximum_penetration_m"],
        "right_maximum_penetration_m": summary["per_contact"]["right"]["maximum_penetration_m"],
        "left_final_impulse_n_s": summary["per_contact"]["left"]["final_impulse_n_s"],
        "right_final_impulse_n_s": summary["per_contact"]["right"]["final_impulse_n_s"],
        "state_transition_sequence": summary["state_machine"]["transition_sequence"],
        "aborted_safe": history.aborted_safe,
    }


def _event_difference(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    scalar_keys = (
        "left_first_contact_time_s", "right_first_contact_time_s",
        "left_separation_time_s", "right_separation_time_s",
        "candidate_transition_time_s", "bilateral_release_transition_time_s",
        "left_peak_normal_force_n", "right_peak_normal_force_n",
        "left_maximum_penetration_m", "right_maximum_penetration_m",
    )
    differences: dict[str, float] = {}
    for key in scalar_keys:
        left_value, right_value = left[key], right[key]
        differences[key] = (
            math.inf if left_value is None or right_value is None
            else abs(float(left_value) - float(right_value))
        )
    differences["left_final_impulse_n_s"] = float(np.linalg.norm(
        np.asarray(left["left_final_impulse_n_s"]) - np.asarray(right["left_final_impulse_n_s"])
    ))
    differences["right_final_impulse_n_s"] = float(np.linalg.norm(
        np.asarray(left["right_final_impulse_n_s"]) - np.asarray(right["right_final_impulse_n_s"])
    ))
    return differences


def _terminal_payload(history: Any, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": history.method,
        "step_s": history.step_s,
        "time_s": history.time_s.tolist(),
        "left_gap_m": history.left.gap_m.tolist(),
        "right_gap_m": history.right.gap_m.tolist(),
        "left_penetration_m": history.left.penetration_m.tolist(),
        "right_penetration_m": history.right.penetration_m.tolist(),
        "left_normal_force_n": history.left.normal_force_magnitude_n.tolist(),
        "right_normal_force_n": history.right.normal_force_magnitude_n.tolist(),
        "state_label": list(history.state_label),
        "final_state": {
            "service_base_position_inertial_m": history.service_base_position_inertial_m[-1].tolist(),
            "service_base_quaternion_body_to_inertial_wxyz": history.service_base_quaternion_body_to_inertial_wxyz[-1].tolist(),
            "service_joint_coordinates_mixed": history.service_joint_coordinates_mixed[-1].tolist(),
            "service_nu_s_mixed": history.service_nu_s_mixed[-1].tolist(),
            "target_position_inertial_m": history.target_position_inertial_m[-1].tolist(),
            "target_quaternion_body_to_inertial_wxyz": history.target_quaternion_body_to_inertial_wxyz[-1].tolist(),
            "target_twist_inertial_mixed": history.target_twist_inertial_mixed[-1].tolist(),
        },
        "events": _event_payload(history, summary),
    }


def _contact_record(history: Any, side: str, index: int) -> dict[str, Any]:
    data = getattr(history, side)
    return {
        "gap_m": float(data.gap_m[index]),
        "penetration_m": float(data.penetration_m[index]),
        "normal_target_to_pad_inertial": data.normal_target_to_pad_inertial[index].tolist(),
        "common_contact_point_inertial_m": data.common_contact_point_inertial_m[index].tolist(),
        "pad_point_inertial_m": data.pad_point_inertial_m[index].tolist(),
        "service_common_point_velocity_inertial_m_s": data.service_common_point_velocity_inertial_m_s[index].tolist(),
        "target_common_point_velocity_inertial_m_s": data.target_common_point_velocity_inertial_m_s[index].tolist(),
        "relative_velocity_inertial_m_s": data.relative_velocity_inertial_m_s[index].tolist(),
        "relative_normal_speed_m_s": float(data.relative_normal_speed_m_s[index]),
        "relative_tangential_velocity_inertial_m_s": data.relative_tangential_velocity_inertial_m_s[index].tolist(),
        "relative_tangential_speed_m_s": float(data.relative_tangential_speed_m_s[index]),
        "normal_force_magnitude_n": float(data.normal_force_magnitude_n[index]),
        "normal_force_service_inertial_n": data.normal_force_service_inertial_n[index].tolist(),
        "tangential_force_service_inertial_n": data.tangential_force_service_inertial_n[index].tolist(),
        "service_force_inertial_n": data.service_force_inertial_n[index].tolist(),
        "target_force_inertial_n": data.target_force_inertial_n[index].tolist(),
        "service_shift_torque_inertial_n_m": data.service_shift_torque_inertial_n_m[index].tolist(),
        "service_generalized_contact_effort_mixed": data.service_generalized_contact_effort_mixed[index].tolist(),
        "target_torque_about_com_inertial_n_m": data.target_torque_about_com_inertial_n_m[index].tolist(),
        "elastic_energy_j": float(data.elastic_energy_j[index]),
        "normal_dissipation_rate_w": float(data.normal_dissipation_rate_w[index]),
        "friction_dissipation_rate_w": float(data.friction_dissipation_rate_w[index]),
        "integrated": {
            "normal_dissipation_j": float(data.cumulative_normal_dissipation_j[index]),
            "friction_dissipation_j": float(data.cumulative_friction_dissipation_j[index]),
            "service_impulse_n_s": data.cumulative_service_impulse_n_s[index].tolist(),
            "service_angular_impulse_n_m_s": data.cumulative_service_angular_impulse_n_m_s[index].tolist(),
        },
    }


def _reference_records(history: Any) -> list[dict[str, Any]]:
    criteria_by_index = {int(item["index"]): item for item in history.soft_capture_criteria_log}
    records: list[dict[str, Any]] = []
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
            "palm": {
                "origin_inertial_m": history.palm_origin_inertial_m[index].tolist(),
                "rotation_body_to_inertial": history.palm_rotation_body_to_inertial[index].tolist(),
                "velocity_inertial_m_s": history.palm_velocity_inertial_m_s[index].tolist(),
                "omega_inertial_rad_s": history.palm_omega_inertial_rad_s[index].tolist(),
                "target_center_palm_m": history.target_center_palm_m[index].tolist(),
                "target_relative_center_speed_m_s": float(history.target_relative_center_speed_m_s[index]),
                "target_relative_omega_rad_s": float(history.target_relative_omega_rad_s[index]),
            },
            "contacts": {
                "left": _contact_record(history, "left", index),
                "right": _contact_record(history, "right", index),
            },
            "declared_ledgers": {
                "service_linear_momentum_n_s": history.service_linear_momentum_n_s[index].tolist(),
                "service_angular_momentum_about_origin_n_m_s": history.service_angular_momentum_about_origin_n_m_s[index].tolist(),
                "target_linear_momentum_n_s": history.target_linear_momentum_n_s[index].tolist(),
                "target_angular_momentum_about_origin_n_m_s": history.target_angular_momentum_about_origin_n_m_s[index].tolist(),
                "service_kinetic_energy_j": float(history.service_kinetic_energy_j[index]),
                "target_kinetic_energy_j": float(history.target_kinetic_energy_j[index]),
            },
            "state_label": history.state_label[index],
            "soft_capture_criteria": criteria_by_index.get(index),
        })
    return records


def _forbidden_scan() -> dict[str, Any]:
    found: list[str] = []
    for path in HERE.rglob("*"):
        lowered = path.name.lower()
        if path.is_dir() and lowered in {"__pycache__", ".pytest_cache", ".ruff_cache"}:
            found.append(path.relative_to(HERE).as_posix())
        elif path.is_file() and (
            lowered.endswith(".urdf")
            or "authorization" in lowered
            or "interface_instance" in lowered
            or lowered.endswith(".lock")
        ):
            found.append(path.relative_to(HERE).as_posix())
    return {"pass": not found, "count": len(found), "paths": sorted(set(found))}


def _ordered_subsequence(sequence: list[str], required: list[str]) -> bool:
    cursor = 0
    for item in sequence:
        if cursor < len(required) and item == required[cursor]:
            cursor += 1
    return cursor == len(required)


def main() -> int:
    for stale in (AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST):
        if stale.is_file():
            stale.unlink()

    source_paths = [
        (PHASE_A_MODEL, "UPSTREAM_PHASE_A_MODEL"),
        (PHASE_A_GATE, "UPSTREAM_PHASE_A_GATE"),
        (PHASE_B2_GATE, "UPSTREAM_PHASE_B2_FINAL_GATE"),
        (URDF, "URDF_TOPOLOGY_SOURCE"),
        (HERE / "contracts/PHASE_B3_URDF_TOPOLOGY_LEDGER_V1.json", "URDF_TOPOLOGY_LEDGER"),
        (HERE / "contracts/PHASE_B3_MODEL_CONTRACT_V1.json", "MODEL_CONTRACT"),
        (HERE / "contracts/PHASE_B3_GOVERNANCE_CONTRACT_V1.json", "GOVERNANCE_CONTRACT"),
        (HERE / "b3_contact/branched_model.py", "BRANCHED_MODEL_SOURCE"),
        (HERE / "b3_contact/dual_contact_kernel.py", "DUAL_CONTACT_KERNEL_SOURCE"),
        (HERE / "b3_contact/__init__.py", "PACKAGE_SOURCE"),
        (HERE / "README.md", "SCOPE_README"),
        (HERE / "pytest.ini", "PYTEST_CONFIG"),
        (HERE / "validate_phase_b3.py", "VALIDATOR_SOURCE"),
        (HERE / "independent_audit_phase_b3.py", "INDEPENDENT_AUDIT_SOURCE"),
    ]
    source_paths.extend((path, "TEST_SOURCE") for path in sorted((HERE / "tests").glob("*.py")))
    source_manifest = {
        "schema": "SIM13_V4B3_SOURCE_MANIFEST_V1",
        "scope": "SYNTHETIC_BRANCHED_DUAL_HARD_FINGER_CONTACT_TRANSIENT_CANDIDATE_ONLY",
        "records": [_record(path, role) for path, role in source_paths],
        "generated_outputs_excluded": [_relative(path) for path in (
            SOURCE_MANIFEST, TRACE, LEDGER, VALIDATION, EVIDENCE_MANIFEST,
            PRE_AUDIT_GATE, AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST,
        )],
    }
    _write(SOURCE_MANIFEST, source_manifest)
    tests = _pytest()

    model, service, target, config = deterministic_dual_contact_scenario()
    histories = {
        name: integrate_dual_contact(
            model, service, target, config,
            step_s=step_s, duration_s=DURATION_S, method=method,
        )
        for name, (method, step_s) in RUN_SPECS.items()
    }
    summaries = {
        name: summarize_dual_contact_history(history, config)
        for name, history in histories.items()
    }
    reference = histories["rk4_reference"]
    reference_summary = summaries["rk4_reference"]
    no_contact = no_contact_regression()
    controls = run_negative_controls(reference, config)

    rk4_coarse_difference = _component_difference(histories["rk4_coarse"], histories["rk4_fine"])
    rk4_fine_difference = _component_difference(histories["rk4_fine"], histories["rk4_reference"])
    midpoint_coarse_difference = _component_difference(histories["midpoint_coarse"], histories["midpoint_fine"])
    midpoint_fine_difference = _component_difference(histories["midpoint_fine"], histories["midpoint_reference"])
    cross_integrator_difference = _component_difference(histories["rk4_reference"], histories["midpoint_reference"])
    event_payloads = {
        name: _event_payload(histories[name], summaries[name]) for name in RUN_SPECS
    }
    cross_event_difference = _event_difference(
        event_payloads["rk4_reference"], event_payloads["midpoint_reference"]
    )
    convergence = {
        "rk4": {
            "coarse_difference": rk4_coarse_difference,
            "fine_difference": rk4_fine_difference,
            "assessment": _rk4_assessment(rk4_coarse_difference, rk4_fine_difference),
        },
        "midpoint_nonsmooth_event": {
            "coarse_difference": midpoint_coarse_difference,
            "fine_difference": midpoint_fine_difference,
            "monotonicity_claimed": False,
            "reason": "single-side contact and release events move across the time grid",
            "reference_vs_rk4": cross_integrator_difference,
            "assessment": _midpoint_envelope(cross_integrator_difference),
        },
        "cross_integrator_events": {
            "differences": cross_event_difference,
            "rk4_reference": event_payloads["rk4_reference"],
            "midpoint_reference": event_payloads["midpoint_reference"],
        },
    }

    mass_matrix = model.mass_matrix(service)
    mass_eigenvalues = np.linalg.eigvalsh(mass_matrix)
    mass_diagnostic = {
        "shape": list(mass_matrix.shape),
        "symmetry_max_error": float(np.max(np.abs(mass_matrix - mass_matrix.T))),
        "minimum_eigenvalue": float(np.min(mass_eigenvalues)),
        "condition_number": float(np.linalg.cond(mass_matrix)),
    }
    qualifying = [
        item for item in reference.soft_capture_criteria_log
        if item.get("soft_capture_transient_qualifies")
    ]
    candidate_diagnostic = {
        "qualifying_sample_count": len(qualifying),
        "first_qualifying_sample": qualifying[0] if qualifying else None,
        "last_qualifying_sample": qualifying[-1] if qualifying else None,
        "all_qualifying_samples_have_closed_ledgers": bool(qualifying) and all(
            item["all_ledgers_closed"] for item in qualifying
        ),
        "all_qualifying_samples_two_contacts": bool(qualifying) and all(
            item["left_contact"] and item["right_contact"] for item in qualifying
        ),
    }
    trace = {
        "schema": "SIM13_V4B3_DUAL_CONTACT_TRACE_V1",
        "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        "scope": "SYNTHETIC_BRANCHED_DUAL_HARD_FINGER_CONTACT_TRANSIENT_CANDIDATE_ONLY",
        "scenario": {
            **asdict(config),
            "urdf_source": _record(URDF, "URDF_TOPOLOGY_SOURCE"),
            "duration_s": DURATION_S,
            "reference_method": "rk4",
            "reference_step_s": RUN_SPECS["rk4_reference"][1],
            "initial_service": {
                "base_position_inertial_m": service.base_position_inertial_m.tolist(),
                "base_quaternion_body_to_inertial_wxyz": service.base_quaternion_body_to_inertial_wxyz.tolist(),
                "joint_coordinates_mixed": service.joint_coordinates_mixed.tolist(),
                "nu_s_mixed": service.nu_s_mixed.tolist(),
            },
            "initial_target": {
                "position_inertial_m": target.position_inertial_m.tolist(),
                "quaternion_body_to_inertial_wxyz": target.quaternion_body_to_inertial_wxyz.tolist(),
                "twist_inertial_mixed": target.twist_inertial_mixed.tolist(),
            },
        },
        "topology_diagnostic": reference.topology_diagnostic,
        "reference_records": _reference_records(reference),
        "convergence_runs": {
            name: _terminal_payload(histories[name], summaries[name]) for name in RUN_SPECS
        },
        "no_contact_regression": no_contact,
        "negative_control_results": list(controls),
    }
    _write(TRACE, trace)
    ledger = {
        "schema": "SIM13_V4B3_DUAL_CONTACT_LEDGER_V1",
        "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        "upstream_trace": _record(TRACE, "UPSTREAM_RAW_TRACE"),
        "reference_summary": reference_summary,
        "mass_matrix_diagnostic": mass_diagnostic,
        "candidate_diagnostic": candidate_diagnostic,
        "convergence": convergence,
        "no_contact_regression": no_contact,
        "negative_control_guard_screen": {
            "scope": "SOLVER_SIDE_ONLY__INDEPENDENT_MUTATION_RECONSTRUCTION_REQUIRED",
            "records": list(controls),
        },
    }
    _write(LEDGER, ledger)

    topology = reference_summary["topology"]
    left = reference_summary["per_contact"]["left"]
    right = reference_summary["per_contact"]["right"]
    linear = reference_summary["linear_momentum_n_s"]
    angular = reference_summary["angular_momentum_n_m_s"]
    energy = reference_summary["energy_j"]
    grasp = reference_summary["grasp_map"]
    state = reference_summary["state_machine"]
    boundaries = reference_summary["boundaries"]
    sequence = state["transition_sequence"]
    required_sequence = [
        "PREGRASP_SEPARATED", "BILATERAL_APPROACH", "DUAL_CONTACT",
        "SOFT_CAPTURE_TRANSIENT_CANDIDATE", "BILATERAL_RELEASE",
    ]
    allowed_states = {
        "PREGRASP_SEPARATED", "BILATERAL_APPROACH", "LEFT_ONLY_CONTACT",
        "RIGHT_ONLY_CONTACT", "DUAL_CONTACT", "SOFT_CAPTURE_TRANSIENT_CANDIDATE",
        "BILATERAL_RELEASE",
    }
    contact_metrics = (left, right)
    forbidden = _forbidden_scan()
    cross_events = convergence["cross_integrator_events"]["differences"]
    all_time_candidate_ledgers = (
        linear["total_max_drift_n_s"] <= config.linear_momentum_ledger_tolerance_n_s
        and angular["total_max_drift_n_m_s"] <= config.angular_momentum_ledger_tolerance_n_m_s
        and energy["total_mechanical_plus_dissipated_max_drift_j"] <= config.energy_ledger_tolerance_j
        and linear["service_delta_minus_sum_impulse_max_error_n_s"] <= config.linear_impulse_identity_tolerance_n_s
        and linear["target_delta_plus_sum_impulse_max_error_n_s"] <= config.linear_impulse_identity_tolerance_n_s
        and angular["service_delta_minus_sum_angular_impulse_max_error_n_m_s"] <= config.angular_impulse_identity_tolerance_n_m_s
        and angular["target_delta_plus_sum_angular_impulse_max_error_n_m_s"] <= config.angular_impulse_identity_tolerance_n_m_s
    )
    event_convergence_pass = (
        cross_events["left_first_contact_time_s"] <= 5.0e-6
        and cross_events["right_first_contact_time_s"] <= 5.0e-6
        and cross_events["left_separation_time_s"] <= 1.0e-5
        and cross_events["right_separation_time_s"] <= 1.0e-5
        and cross_events["candidate_transition_time_s"] <= 3.0e-4
        and cross_events["bilateral_release_transition_time_s"] <= 3.0e-4
        and cross_events["left_peak_normal_force_n"] <= 2.0e-2
        and cross_events["right_peak_normal_force_n"] <= 2.0e-2
        and cross_events["left_maximum_penetration_m"] <= 2.0e-6
        and cross_events["right_maximum_penetration_m"] <= 2.0e-6
        and cross_events["left_final_impulse_n_s"] <= 2.0e-5
        and cross_events["right_final_impulse_n_s"] <= 2.0e-5
    )
    checks = [
        _check("VB3-01", "audited upstream and URDF hashes", _sha(PHASE_A_GATE) == EXPECTED_PHASE_A_GATE_SHA and _sha(PHASE_B2_GATE) == EXPECTED_PHASE_B2_GATE_SHA and _sha(URDF) == EXPECTED_URDF_SHA, {"phase_a": _sha(PHASE_A_GATE), "phase_b2": _sha(PHASE_B2_GATE), "urdf": _sha(URDF)}),
        _check("VB3-02", "fixed pytest inventory", tests["collection_return_code"] == 0 and tests["execution_return_code"] == 0 and tests["collected_count"] == EXPECTED_TEST_COUNT and tests["passed"] == EXPECTED_TEST_COUNT, tests),
        _check("VB3-03", "14-DOF symmetric positive-definite branched mass matrix", mass_diagnostic["shape"] == [14, 14] and mass_diagnostic["symmetry_max_error"] <= 1.0e-12 and mass_diagnostic["minimum_eigenvalue"] > 1.0e-10, mass_diagnostic),
        _check("VB3-04", "actual-model sibling-P own Jacobians", topology["left_own_P_jacobian_fd_max_error"] <= 2.0e-9 and topology["right_own_P_jacobian_fd_max_error"] <= 2.0e-9, topology),
        _check("VB3-05", "actual-model sibling-P cross channels zero", max(topology["left_cross_right_P_fd_norm"], topology["right_cross_left_P_fd_norm"], topology["left_analytic_cross_right_P_norm"], topology["right_analytic_cross_left_P_norm"]) <= 1.0e-12, topology),
        _check("VB3-06", "nominal integration completed without abort", not reference.aborted_safe and not state["abort_reasons"], state),
        _check("VB3-07", "ordered soft-capture transient sequence with allowlisted intermediates", _ordered_subsequence(sequence, required_sequence) and set(sequence).issubset(allowed_states), {"required": required_sequence, "actual": sequence}),
        _check("VB3-08", "candidate has simultaneous contacts and all online ledgers", candidate_diagnostic["qualifying_sample_count"] > 0 and candidate_diagnostic["all_qualifying_samples_two_contacts"] and candidate_diagnostic["all_qualifying_samples_have_closed_ledgers"], candidate_diagnostic),
        _check("VB3-09", "bilateral release without lock or grasp promotion", sequence[-1] == "BILATERAL_RELEASE" and not state["locked_state_present"] and not state["grasp_success_state_present"], state),
        _check("VB3-10", "per-contact action reaction", all(item["action_reaction_max_error_n"] <= config.action_reaction_tolerance_n for item in contact_metrics), contact_metrics),
        _check("VB3-11", "per-contact tangent orthogonality and friction cone", all(item["tangential_orthogonality_max_error_n"] <= 1.0e-12 and item["friction_cone_max_excess_n"] <= 1.0e-12 for item in contact_metrics), contact_metrics),
        _check("VB3-12", "per-contact common-point service shift", all(item["common_point_shift_max_error_n_m"] <= config.common_point_shift_tolerance_n_m for item in contact_metrics), contact_metrics),
        _check("VB3-13", "per-contact target torque identity", all(item["target_common_point_torque_max_error_n_m"] <= config.target_torque_identity_tolerance_n_m for item in contact_metrics), contact_metrics),
        _check("VB3-14", "per-contact service and target virtual power", all(max(item["service_virtual_power_max_error_w"], item["target_virtual_power_max_error_w"]) <= config.virtual_power_tolerance_w for item in contact_metrics), contact_metrics),
        _check("VB3-15", "friction never injects power", all(item["maximum_friction_power_w"] <= config.friction_noninjection_tolerance_w for item in contact_metrics), contact_metrics),
        _check("VB3-16", "four dissipation channels nonnegative and monotone", all(item["final_normal_dissipation_j"] >= 0.0 and item["final_friction_dissipation_j"] >= 0.0 and item["normal_dissipation_minimum_increment_j"] >= -config.dissipation_monotonic_tolerance_j and item["friction_dissipation_minimum_increment_j"] >= -config.dissipation_monotonic_tolerance_j for item in contact_metrics), contact_metrics),
        _check("VB3-17", "service and target linear impulse identities", linear["service_delta_minus_sum_impulse_max_error_n_s"] <= config.linear_impulse_identity_tolerance_n_s and linear["target_delta_plus_sum_impulse_max_error_n_s"] <= config.linear_impulse_identity_tolerance_n_s, linear),
        _check("VB3-18", "total linear momentum", linear["total_max_drift_n_s"] <= config.linear_momentum_ledger_tolerance_n_s, linear),
        _check("VB3-19", "service and target angular impulse identities", angular["service_delta_minus_sum_angular_impulse_max_error_n_m_s"] <= config.angular_impulse_identity_tolerance_n_m_s and angular["target_delta_plus_sum_angular_impulse_max_error_n_m_s"] <= config.angular_impulse_identity_tolerance_n_m_s, angular),
        _check("VB3-20", "total angular momentum", angular["total_max_drift_n_m_s"] <= config.angular_momentum_ledger_tolerance_n_m_s, angular),
        _check("VB3-21", "T plus two U plus four dissipations with zero actuator work", energy["total_mechanical_plus_dissipated_max_drift_j"] <= config.energy_ledger_tolerance_j and energy["actuator_work_j"] == 0.0 and energy["actuator_model_present"] is False, energy),
        _check("VB3-22", "all-trajectory ledger limits", all_time_candidate_ledgers, {"linear": linear, "angular": angular, "energy": energy}),
        _check("VB3-23", "P fingers remain inside design-model stroke", float(np.min(reference.service_joint_coordinates_mixed[:, 6:8])) >= config.stroke_lower_m and float(np.max(reference.service_joint_coordinates_mixed[:, 6:8])) <= config.stroke_upper_m, {"min_m": float(np.min(reference.service_joint_coordinates_mixed[:, 6:8])), "max_m": float(np.max(reference.service_joint_coordinates_mixed[:, 6:8])), "bounds_m": [config.stroke_lower_m, config.stroke_upper_m]}),
        _check("VB3-24", "all qualifying normalized grasp maps have rank five", grasp["qualifying_sample_count_evaluated"] == candidate_diagnostic["qualifying_sample_count"] and grasp["all_evaluated_samples_rank_five"] and grasp["rank_min_across_evaluated_samples"] == 5 and grasp["rank_max_across_evaluated_samples"] == 5, grasp),
        _check("VB3-25", "axial pure torque unreachable and no 6-D closure", grasp["selected_sample"]["normalized_axial_pure_torque_lstsq_residual"] > 0.99 and grasp["full_6d_wrench_span"] is False and grasp["full_6d_force_closure"] is False, grasp),
        _check("VB3-26", "no-contact regression including target quaternion and P/H/E", max(no_contact.values()) <= 2.0e-12, no_contact),
        _check("VB3-27", "RK4 step-halving", convergence["rk4"]["assessment"]["all_components_pass"], convergence["rk4"]),
        _check("VB3-28", "midpoint nonsmooth-event absolute envelope", convergence["midpoint_nonsmooth_event"]["monotonicity_claimed"] is False and convergence["midpoint_nonsmooth_event"]["assessment"]["all_components_pass"], convergence["midpoint_nonsmooth_event"]),
        _check("VB3-29", "cross-integrator contact/candidate/release convergence", event_convergence_pass, convergence["cross_integrator_events"]),
        _check("VB3-30", "solver-side mutation guard screen complete but non-final", len(controls) == 22 and all(item["mutation_rejected"] and item["result"] == "PASS_NEGATIVE_CONTROL" for item in controls) and all("INDEPENDENT_RECONSTRUCTION_REQUIRED" in item["evidence_level"] for item in controls), controls),
        _check("VB3-31", "physical/current/production/release boundaries remain false", not any((PHYSICAL_DUAL_CONTACT_IDENTIFIED, PHYSICAL_FRICTION_IDENTIFIED, PHYSICAL_ACTUATOR_TIMING_IDENTIFIED, SOFT_CAPTURE_CURRENT_SYSTEM_PASSED, LOCK_IMPLEMENTED, GRASP_SUCCESS_CLAIMED, CURRENT_SYSTEM_BOUND, FORMAL_NC19_CREDIT, PRODUCTION_READY, RELEASE_AUTHORIZED, NEXT_STAGE_AUTHORIZED)) and not any(boundaries.values()), boundaries),
        _check("VB3-32", "formal Sim13 V2 remains 15 of 20 with five HOLDs", json.loads((HERE / "contracts/PHASE_B3_GOVERNANCE_CONTRACT_V1.json").read_text(encoding="utf-8"))["formal_sim13_v2_state_unchanged"] == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]}, {"passed": 15, "declared": 20}),
        _check("VB3-33", "no generated URDF/interface/authorization/cache artifacts", forbidden["pass"], forbidden),
    ]
    passed = sum(item["pass"] for item in checks)
    validation = {
        "schema": "SIM13_V4B3_VALIDATION_V1",
        "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        "upstream_trace": _record(TRACE, "UPSTREAM_RAW_TRACE"),
        "upstream_ledger": _record(LEDGER, "UPSTREAM_LEDGER"),
        "status": "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" if passed == len(checks) else "FAIL_VALIDATOR",
        "score": {"pass": passed, "fail": len(checks) - passed, "total": len(checks)},
        "checks": checks,
    }
    _write(VALIDATION, validation)
    evidence_manifest = {
        "schema": "SIM13_V4B3_EVIDENCE_MANIFEST_V1",
        "acyclic": True,
        "self_excluded": True,
        "records": [
            _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
            _record(TRACE, "UPSTREAM_RAW_TRACE"),
            _record(LEDGER, "UPSTREAM_LEDGER"),
            _record(VALIDATION, "UPSTREAM_VALIDATION"),
        ],
    }
    _write(EVIDENCE_MANIFEST, evidence_manifest)
    pre_audit = {
        "schema": "SIM13_V4B3_PRE_AUDIT_GATE_V1",
        "overall_status": "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" if passed == len(checks) else "FAIL_VALIDATOR",
        "final_gate": False,
        "upstream_evidence_manifest": _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
        "validator_checks": validation["score"],
        "scoped_candidate": {
            "synthetic_branched_dual_contact_transient_candidate_validator_passed": passed == len(checks),
            "held_capture": False,
            "full_6d_force_closure": False,
        },
        "authorizations": {
            "physical_dual_contact_identified": False,
            "physical_friction_identified": False,
            "physical_actuator_timing_identified": False,
            "soft_capture_current_system_passed": False,
            "lock_implemented": False,
            "grasp_success": False,
            "current_system_bound": False,
            "formal_nc19_closed": False,
            "owner_authorized": False,
            "production_ready": False,
            "release_authorized": False,
            "next_stage_authorized": False,
        },
        "formal_sim13_v2_state": {
            "passed": 15,
            "declared": 20,
            "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
            "changed_by_this_package": False,
        },
    }
    _write(PRE_AUDIT_GATE, pre_audit)
    print(json.dumps({
        "status": validation["status"],
        "checks": validation["score"],
        "tests": {"passed": tests["passed"], "expected": EXPECTED_TEST_COUNT},
        "events": event_payloads["rk4_reference"],
        "mass_matrix": mass_diagnostic,
        "candidate": candidate_diagnostic,
        "linear": linear,
        "angular": angular,
        "energy": energy,
        "grasp_map": {
            "rank_min": grasp["rank_min_across_evaluated_samples"],
            "rank_max": grasp["rank_max_across_evaluated_samples"],
            "full_6d_force_closure": grasp["full_6d_force_closure"],
        },
        "pre_audit_gate_sha256": _sha(PRE_AUDIT_GATE),
    }, indent=2))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
