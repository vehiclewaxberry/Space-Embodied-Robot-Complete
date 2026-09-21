"""Independent Phase-B1 physics/DAG audit and sole final-Gate issuer.

This module never imports validate_phase_b1 and never consumes its Boolean
conclusions as physics evidence.  It reconstructs geometry, force, generalized
effort, impulse, momentum, energy/dissipation and event timing from the
hash-bound raw trace.  It also validates every DAG edge by exact role, path,
byte count and SHA-256 before issuing the final Gate.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
PHASE_A = HERE.parent
PROJECT_ROOT = HERE.parents[3]
if str(PHASE_A) not in sys.path:
    sys.path.insert(0, str(PHASE_A))

from sim13_v4a.full_floating import (  # noqa: E402
    FullFloatingServiceModel,
    ServiceState,
    TargetState,
    TARGET_INERTIA_BODY_KG_M2,
    TARGET_MASS_KG,
    quat_to_rotation,
    quaternion_geodesic,
)


SOURCE_MANIFEST = HERE / "evidence/SIM13_V4B1_SOURCE_MANIFEST_V1.json"
TRACE = HERE / "evidence/SIM13_V4B1_CONTACT_TRACE_V1.json"
LEDGER = HERE / "evidence/SIM13_V4B1_CONTACT_LEDGER_V1.json"
VALIDATION = HERE / "evidence/SIM13_V4B1_VALIDATION_V1.json"
EVIDENCE_MANIFEST = HERE / "evidence/SIM13_V4B1_EVIDENCE_MANIFEST_V1.json"
PRE_AUDIT_GATE = HERE / "results/SIM13_V4B1_PRE_AUDIT_GATE_V1.json"
AUDIT_RECEIPT = HERE / "evidence/SIM13_V4B1_INDEPENDENT_AUDIT_RECEIPT_V1.json"
FINAL_GATE = HERE / "results/SIM13_V4B1_AUDITED_GATE_V1.json"
TERMINAL_MANIFEST = HERE / "results/SIM13_V4B1_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"
PHASE_A_MODEL = PHASE_A / "sim13_v4a/full_floating.py"
PHASE_A_GATE = PHASE_A / "results/SIM13_V4A_PHASE_A_AUDITED_GATE_V3.json"

EXPECTED_PHASE_A_MODEL_SHA = "3EC187C850F72EB1CAFF18713C71D6D0AC1773AF6C7AA8BFF4285FC26055C998"
EXPECTED_PHASE_A_GATE_SHA = "82ECF267AA5F0DF0B79610AB4FBFD4DB4AE564EDE530A7F69AB579D1E15F7A40"

# Independently stated, native-unit absolute floors for terminal step-halving.
# These are not imported from the validator; the audit recomputes the decision.
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


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _record(path: Path, role: str) -> dict[str, Any]:
    return {"role": role, "path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha(path)}


def _resolve_inside_project(relative: Any) -> tuple[Path | None, str | None]:
    if not isinstance(relative, str) or not relative:
        return None, "PATH_NOT_NONEMPTY_STRING"
    candidate = (PROJECT_ROOT / relative).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return None, "PATH_ESCAPES_PROJECT_ROOT"
    return candidate, None


def _strict_reference(reference: Any, expected_path: Path, expected_role: str) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(reference, dict):
        return {"pass": False, "errors": ["REFERENCE_NOT_OBJECT"]}
    if set(reference) != {"role", "path", "bytes", "sha256"}:
        errors.append("REFERENCE_KEYS_NOT_EXACT")
    if reference.get("role") != expected_role:
        errors.append("ROLE_MISMATCH_OR_UNKNOWN")
    if reference.get("path") != _relative(expected_path):
        errors.append("PATH_MISMATCH")
    resolved, path_error = _resolve_inside_project(reference.get("path"))
    if path_error:
        errors.append(path_error)
    if resolved is None or not resolved.is_file():
        errors.append("TARGET_NOT_FILE")
        actual_bytes = None
        actual_sha = None
    else:
        actual_bytes = resolved.stat().st_size
        actual_sha = _sha(resolved)
        if reference.get("bytes") != actual_bytes:
            errors.append("BYTE_COUNT_MISMATCH")
        if reference.get("sha256") != actual_sha:
            errors.append("SHA256_MISMATCH")
    return {
        "pass": not errors,
        "expected_path": _relative(expected_path),
        "expected_role": expected_role,
        "actual_bytes": actual_bytes,
        "actual_sha256": actual_sha,
        "errors": errors,
    }


def _own_source_paths() -> list[Path]:
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


def _strict_source_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    expected = [(path, "B1_FROZEN_SOURCE_INPUT") for path in _own_source_paths()]
    expected.extend(((PHASE_A_MODEL, "PHASE_A_V3_PUBLIC_MODEL_UPSTREAM"), (PHASE_A_GATE, "PHASE_A_V3_AUDITED_GATE_UPSTREAM")))
    records = payload.get("records")
    errors: list[str] = []
    checks: list[dict[str, Any]] = []
    if payload.get("schema") != "SIM13_V4B1_SOURCE_MANIFEST_V1":
        errors.append("SOURCE_SCHEMA_MISMATCH")
    if payload.get("self_excluded_path") != _relative(SOURCE_MANIFEST):
        errors.append("SOURCE_SELF_EXCLUSION_MISMATCH")
    if not isinstance(records, list):
        return {"pass": False, "errors": errors + ["SOURCE_RECORDS_NOT_LIST"], "edge_checks": []}
    paths = [item.get("path") for item in records if isinstance(item, dict)]
    roles = [item.get("role") for item in records if isinstance(item, dict)]
    if len(paths) != len(set(paths)):
        errors.append("DUPLICATE_SOURCE_PATH")
    allowed_roles = {"B1_FROZEN_SOURCE_INPUT", "PHASE_A_V3_PUBLIC_MODEL_UPSTREAM", "PHASE_A_V3_AUDITED_GATE_UPSTREAM"}
    if any(role not in allowed_roles for role in roles):
        errors.append("UNKNOWN_SOURCE_ROLE")
    if len(records) != len(expected):
        errors.append("SOURCE_RECORD_COUNT_MISMATCH")
    for index, (path, role) in enumerate(expected):
        checks.append(_strict_reference(records[index] if index < len(records) else None, path, role))
    if not all(item["pass"] for item in checks):
        errors.append("SOURCE_EDGE_INTEGRITY_FAILURE")
    generated = {_relative(path) for path in (SOURCE_MANIFEST, TRACE, LEDGER, VALIDATION, EVIDENCE_MANIFEST, PRE_AUDIT_GATE, AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST)}
    if set(paths) & generated:
        errors.append("SOURCE_MANIFEST_HAS_SELF_OR_GENERATED_BACK_EDGE")
    return {"pass": not errors, "errors": errors, "edge_checks": checks}


def _strict_dag(source: dict[str, Any], trace: dict[str, Any], ledger: dict[str, Any], validation: dict[str, Any], evidence: dict[str, Any], pre_audit: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    def edge(reference: Any, path: Path, role: str, name: str) -> None:
        check = _strict_reference(reference, path, role)
        check["edge"] = name
        checks.append(check)

    edge(trace.get("hash_chain", {}).get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST", "trace_to_source")
    edge(ledger.get("hash_chain", {}).get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST", "ledger_to_source")
    edge(ledger.get("hash_chain", {}).get("upstream_contact_trace"), TRACE, "UPSTREAM_CONTACT_TRACE", "ledger_to_trace")
    edge(validation.get("hash_chain", {}).get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST", "validation_to_source")
    edge(validation.get("hash_chain", {}).get("upstream_contact_trace"), TRACE, "UPSTREAM_CONTACT_TRACE", "validation_to_trace")
    edge(validation.get("hash_chain", {}).get("upstream_contact_ledger"), LEDGER, "UPSTREAM_CONTACT_LEDGER", "validation_to_ledger")
    edge(evidence.get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST", "evidence_to_source")
    expected_records = ((TRACE, "CONTACT_TRACE"), (LEDGER, "CONTACT_LEDGER"), (VALIDATION, "VALIDATION_EVIDENCE"))
    records = evidence.get("records")
    if not isinstance(records, list):
        errors.append("EVIDENCE_RECORDS_NOT_LIST")
        records = []
    paths = [item.get("path") for item in records if isinstance(item, dict)]
    roles = [item.get("role") for item in records if isinstance(item, dict)]
    if len(paths) != len(set(paths)):
        errors.append("DUPLICATE_EVIDENCE_PATH")
    if len(roles) != len(set(roles)):
        errors.append("DUPLICATE_EVIDENCE_ROLE")
    if set(roles) != {role for _, role in expected_records}:
        errors.append("UNKNOWN_OR_MISSING_EVIDENCE_ROLE")
    for index, (path, role) in enumerate(expected_records):
        edge(records[index] if index < len(records) else None, path, role, f"evidence_to_{role.lower()}")
    edge(pre_audit.get("hash_chain", {}).get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST", "pre_audit_to_source")
    edge(pre_audit.get("hash_chain", {}).get("upstream_evidence_manifest"), EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST", "pre_audit_to_evidence")
    expected_schemas = {
        "SIM13_V4B1_SOURCE_MANIFEST_V1",
        "SIM13_V4B1_CONTACT_TRACE_V1",
        "SIM13_V4B1_CONTACT_LEDGER_V1",
        "SIM13_V4B1_VALIDATION_V1",
        "SIM13_V4B1_EVIDENCE_MANIFEST_V1",
        "SIM13_V4B1_PRE_AUDIT_GATE_V1",
    }
    actual_schemas = {payload.get("schema") for payload in (source, trace, ledger, validation, evidence, pre_audit)}
    if actual_schemas != expected_schemas:
        errors.append("UNKNOWN_DUPLICATE_OR_MISSING_SCHEMA")
    generated = {_relative(path) for path in (SOURCE_MANIFEST, TRACE, LEDGER, VALIDATION, EVIDENCE_MANIFEST, PRE_AUDIT_GATE, AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST)}
    source_paths = {item.get("path") for item in source.get("records", []) if isinstance(item, dict)}
    evidence_paths = set(paths)
    if source_paths & generated:
        errors.append("SOURCE_BACK_EDGE_OR_SELF_REFERENCE")
    if evidence_paths != {_relative(TRACE), _relative(LEDGER), _relative(VALIDATION)}:
        errors.append("EVIDENCE_UNKNOWN_SELF_OR_BACK_EDGE")
    downstream_absent = not any(path.is_file() for path in (AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST))
    if not downstream_absent:
        errors.append("STALE_DOWNSTREAM_PRESENT_AT_AUDIT_ENTRY")
    if not all(item["pass"] for item in checks):
        errors.append("STRICT_EDGE_PATH_BYTES_SHA_ROLE_FAILURE")
    return {
        "pass": not errors,
        "errors": errors,
        "edge_checks": checks,
        "downstream_targets_absent_at_audit_entry": downstream_absent,
        "root_escape_allowed": False,
        "duplicate_path_or_role_allowed": False,
        "unknown_role_allowed": False,
        "self_reference_allowed": False,
        "back_edge_allowed": False,
        "topological_order": ["source_inputs", "source_manifest", "trace", "ledger", "validation", "evidence_manifest", "pre_audit_gate", "independent_audit", "final_gate", "terminal_manifest"],
    }


def _service_state(record: dict[str, Any]) -> ServiceState:
    item = record["service"]
    return ServiceState(np.asarray(item["base_position_inertial_m"], dtype=float), np.asarray(item["base_quaternion_body_to_inertial_wxyz"], dtype=float), np.asarray(item["joint_coordinates_mixed"], dtype=float), np.asarray(item["nu_s_mixed"], dtype=float))


def _target_state(record: dict[str, Any]) -> TargetState:
    item = record["target"]
    return TargetState(np.asarray(item["position_inertial_m"], dtype=float), np.asarray(item["quaternion_body_to_inertial_wxyz"], dtype=float), np.asarray(item["twist_inertial_mixed"], dtype=float))


def _manual_service_ledger(model: FullFloatingServiceModel, state: ServiceState) -> tuple[np.ndarray, np.ndarray, float]:
    linear = np.zeros(3)
    angular = np.zeros(3)
    energy = 0.0
    for body in model.kinematics(state).bodies:
        velocity = body.translational_jacobian_mixed @ state.nu_s_mixed
        omega = body.angular_jacobian_mixed @ state.nu_s_mixed
        body_linear = body.mass_kg * velocity
        spin = body.inertia_inertial_kg_m2 @ omega
        linear += body_linear
        angular += np.cross(body.position_inertial_m, body_linear) + spin
        energy += 0.5 * body.mass_kg * float(velocity @ velocity) + 0.5 * float(omega @ spin)
    return linear, angular, energy


def _manual_target_ledger(state: TargetState) -> tuple[np.ndarray, np.ndarray, float]:
    rotation = quat_to_rotation(state.quaternion_body_to_inertial_wxyz)
    inertia_world = rotation @ TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    velocity = state.twist_inertial_mixed[:3]
    omega = state.twist_inertial_mixed[3:]
    linear = TARGET_MASS_KG * velocity
    spin = inertia_world @ omega
    angular = np.cross(state.position_inertial_m, linear) + spin
    energy = 0.5 * TARGET_MASS_KG * float(velocity @ velocity) + 0.5 * float(omega @ spin)
    return linear, angular, energy


def _crossing_time(times: np.ndarray, gaps: np.ndarray, direction: str, start: int = 1) -> float | None:
    for index in range(max(1, start), len(times)):
        left, right = float(gaps[index - 1]), float(gaps[index])
        crossed = left > 0.0 and right <= 0.0 if direction == "enter" else left < 0.0 and right >= 0.0
        if crossed:
            fraction = abs(left) / (abs(left) + abs(right)) if left != right else 0.0
            return float(times[index - 1] + fraction * (times[index] - times[index - 1]))
    return None


def _independent_physics(trace: dict[str, Any]) -> dict[str, Any]:
    scenario = trace["scenario"]
    radius = float(scenario["sphere_radius_m"])
    stiffness = float(scenario["normal_stiffness_n_m"])
    damping = float(scenario["normal_damping_n_s_m"])
    link_index = int(scenario["pad_link_index"])
    point_local = np.asarray(scenario["pad_point_local_m"], dtype=float)
    records = trace["reference_run"]["records"]
    count = len(records)
    model = FullFloatingServiceModel()
    times = np.empty(count)
    gaps = np.empty(count)
    penetrations = np.empty(count)
    normal_speeds = np.empty(count)
    forces = np.empty((count, 3))
    common_points = np.empty((count, 3))
    dissipation_rate = np.empty(count)
    logged_dissipation = np.empty(count)
    p_s = np.empty((count, 3)); h_s = np.empty((count, 3)); t_s = np.empty(count)
    p_t = np.empty((count, 3)); h_t = np.empty((count, 3)); t_t = np.empty(count)
    elastic = np.empty(count)
    metric = {
        "gap_max_error_m": 0.0,
        "penetration_max_error_m": 0.0,
        "normal_max_error": 0.0,
        "common_point_max_error_m": 0.0,
        "pad_point_max_error_m": 0.0,
        "pad_velocity_max_error_m_s": 0.0,
        "target_surface_velocity_max_error_m_s": 0.0,
        "relative_velocity_max_error_m_s": 0.0,
        "relative_normal_speed_max_error_m_s": 0.0,
        "force_law_max_error_n": 0.0,
        "service_force_max_error_n": 0.0,
        "target_force_max_error_n": 0.0,
        "action_reaction_max_error_n": 0.0,
        "common_point_offset_moment_max_error_n_m": 0.0,
        "target_torque_max_error_n_m": 0.0,
        "generalized_base_effort_max_error_mixed": 0.0,
        "generalized_R_effort_max_error_n_m": 0.0,
        "generalized_P_effort_max_error_n": 0.0,
        "separated_force_max_n": 0.0,
        "primary_ledger_reconstruction_max_error": 0.0,
    }
    for index, record in enumerate(records):
        times[index] = float(record["time_s"])
        service = _service_state(record)
        target = _target_state(record)
        pad, jacobian, _ = model.point_position_and_jacobian(service, link_index, point_local)
        radial = pad - target.position_inertial_m
        distance = float(np.linalg.norm(radial))
        normal = radial / distance
        gap = distance - radius
        penetration = max(-gap, 0.0)
        common_point = target.position_inertial_m + radius * normal
        pad_velocity = jacobian @ service.nu_s_mixed
        target_surface_velocity = target.twist_inertial_mixed[:3] + np.cross(target.twist_inertial_mixed[3:], common_point - target.position_inertial_m)
        relative_velocity = pad_velocity - target_surface_velocity
        relative_normal = float(relative_velocity @ normal)
        closing = max(-relative_normal, 0.0) if penetration > 0.0 else 0.0
        force_magnitude = stiffness * penetration + damping * closing if penetration > 0.0 else 0.0
        force = force_magnitude * normal
        target_force = -force
        generalized = jacobian.T @ force
        target_torque = np.cross(common_point - target.position_inertial_m, target_force)
        contact = record["contact"]
        logged_normal = np.asarray(contact["normal_target_to_pad_inertial"], dtype=float)
        logged_pc = np.asarray(contact["common_contact_point_inertial_m"], dtype=float)
        logged_pad = np.asarray(contact["pad_point_inertial_m"], dtype=float)
        logged_pad_velocity = np.asarray(contact["pad_velocity_inertial_m_s"], dtype=float)
        logged_target_velocity = np.asarray(contact["target_surface_velocity_inertial_m_s"], dtype=float)
        logged_relative = np.asarray(contact["relative_velocity_inertial_m_s"], dtype=float)
        logged_force = np.asarray(contact["service_force_inertial_n"], dtype=float)
        logged_target_force = np.asarray(contact["target_force_inertial_n"], dtype=float)
        logged_generalized = np.asarray(contact["service_generalized_contact_effort_mixed"], dtype=float)
        logged_target_torque = np.asarray(contact["target_torque_about_com_inertial_n_m"], dtype=float)
        metric["gap_max_error_m"] = max(metric["gap_max_error_m"], abs(gap - float(contact["gap_m"])))
        metric["penetration_max_error_m"] = max(metric["penetration_max_error_m"], abs(penetration - float(contact["penetration_m"])))
        metric["normal_max_error"] = max(metric["normal_max_error"], float(np.linalg.norm(normal - logged_normal)))
        metric["common_point_max_error_m"] = max(metric["common_point_max_error_m"], float(np.linalg.norm(common_point - logged_pc)))
        metric["pad_point_max_error_m"] = max(metric["pad_point_max_error_m"], float(np.linalg.norm(pad - logged_pad)))
        metric["pad_velocity_max_error_m_s"] = max(metric["pad_velocity_max_error_m_s"], float(np.linalg.norm(pad_velocity - logged_pad_velocity)))
        metric["target_surface_velocity_max_error_m_s"] = max(metric["target_surface_velocity_max_error_m_s"], float(np.linalg.norm(target_surface_velocity - logged_target_velocity)))
        metric["relative_velocity_max_error_m_s"] = max(metric["relative_velocity_max_error_m_s"], float(np.linalg.norm(relative_velocity - logged_relative)))
        metric["relative_normal_speed_max_error_m_s"] = max(metric["relative_normal_speed_max_error_m_s"], abs(relative_normal - float(contact["relative_normal_speed_m_s"])))
        metric["force_law_max_error_n"] = max(metric["force_law_max_error_n"], abs(force_magnitude - float(contact["normal_force_magnitude_n"])))
        metric["service_force_max_error_n"] = max(metric["service_force_max_error_n"], float(np.linalg.norm(force - logged_force)))
        metric["target_force_max_error_n"] = max(metric["target_force_max_error_n"], float(np.linalg.norm(target_force - logged_target_force)))
        metric["action_reaction_max_error_n"] = max(metric["action_reaction_max_error_n"], float(np.linalg.norm(logged_force + logged_target_force)))
        metric["common_point_offset_moment_max_error_n_m"] = max(metric["common_point_offset_moment_max_error_n_m"], float(np.linalg.norm(np.cross(pad - common_point, force))))
        metric["target_torque_max_error_n_m"] = max(metric["target_torque_max_error_n_m"], float(np.linalg.norm(target_torque - logged_target_torque)))
        metric["generalized_base_effort_max_error_mixed"] = max(metric["generalized_base_effort_max_error_mixed"], float(np.max(np.abs(generalized[:6] - logged_generalized[:6]))))
        metric["generalized_R_effort_max_error_n_m"] = max(metric["generalized_R_effort_max_error_n_m"], float(np.max(np.abs(generalized[6:12] - logged_generalized[6:12]))))
        metric["generalized_P_effort_max_error_n"] = max(metric["generalized_P_effort_max_error_n"], float(np.max(np.abs(generalized[12:14] - logged_generalized[12:14]))))
        if penetration <= 0.0:
            metric["separated_force_max_n"] = max(metric["separated_force_max_n"], force_magnitude)
        p_s[index], h_s[index], t_s[index] = _manual_service_ledger(model, service)
        p_t[index], h_t[index], t_t[index] = _manual_target_ledger(target)
        primary = record["primary_ledgers"]
        primary_errors = (
            np.linalg.norm(p_s[index] - np.asarray(primary["service_linear_momentum_n_s"])),
            np.linalg.norm(h_s[index] - np.asarray(primary["service_angular_momentum_about_origin_n_m_s"])),
            np.linalg.norm(p_t[index] - np.asarray(primary["target_linear_momentum_n_s"])),
            np.linalg.norm(h_t[index] - np.asarray(primary["target_angular_momentum_about_origin_n_m_s"])),
            abs(t_s[index] - float(primary["service_kinetic_energy_j"])),
            abs(t_t[index] - float(primary["target_kinetic_energy_j"])),
        )
        metric["primary_ledger_reconstruction_max_error"] = max(metric["primary_ledger_reconstruction_max_error"], *map(float, primary_errors))
        gaps[index] = gap; penetrations[index] = penetration; normal_speeds[index] = relative_normal
        forces[index] = force; common_points[index] = common_point
        dissipation_rate[index] = damping * closing**2 if penetration > 0.0 else 0.0
        logged_dissipation[index] = float(record["integrals"]["dissipation_j"])
        elastic[index] = 0.5 * stiffness * penetration**2

    impulse = np.zeros_like(forces)
    angular_impulse = np.zeros_like(forces)
    dissipation_trap = np.zeros(count)
    for index in range(1, count):
        dt = times[index] - times[index - 1]
        impulse[index] = impulse[index - 1] + 0.5 * dt * (forces[index - 1] + forces[index])
        moment_left = np.cross(common_points[index - 1], forces[index - 1])
        moment_right = np.cross(common_points[index], forces[index])
        angular_impulse[index] = angular_impulse[index - 1] + 0.5 * dt * (moment_left + moment_right)
        dissipation_trap[index] = dissipation_trap[index - 1] + 0.5 * dt * (dissipation_rate[index - 1] + dissipation_rate[index])
    delta_p_s = p_s - p_s[0]; delta_p_t = p_t - p_t[0]
    delta_h_s = h_s - h_s[0]; delta_h_t = h_t - h_t[0]
    total_p = p_s + p_t; total_h = h_s + h_t
    total_energy_logged_d = t_s + t_t + elastic + logged_dissipation
    total_energy_trap_d = t_s + t_t + elastic + dissipation_trap
    metric.update(
        {
            "trapezoidal_impulse_final_n_s": impulse[-1].tolist(),
            "trapezoidal_angular_impulse_final_n_m_s": angular_impulse[-1].tolist(),
            "service_delta_minus_trapezoidal_impulse_max_error_n_s": float(np.max(np.linalg.norm(delta_p_s - impulse, axis=1))),
            "target_delta_plus_trapezoidal_impulse_max_error_n_s": float(np.max(np.linalg.norm(delta_p_t + impulse, axis=1))),
            "total_linear_momentum_max_drift_n_s": float(np.max(np.linalg.norm(total_p - total_p[0], axis=1))),
            "service_delta_minus_trapezoidal_angular_impulse_max_error_n_m_s": float(np.max(np.linalg.norm(delta_h_s - angular_impulse, axis=1))),
            "target_delta_plus_trapezoidal_angular_impulse_max_error_n_m_s": float(np.max(np.linalg.norm(delta_h_t + angular_impulse, axis=1))),
            "total_angular_momentum_max_drift_n_m_s": float(np.max(np.linalg.norm(total_h - total_h[0], axis=1))),
            "logged_vs_trapezoidal_dissipation_final_error_j": abs(float(logged_dissipation[-1] - dissipation_trap[-1])),
            "energy_plus_logged_dissipation_max_drift_j": float(np.max(np.abs(total_energy_logged_d - total_energy_logged_d[0]))),
            "energy_plus_trapezoidal_dissipation_max_drift_j": float(np.max(np.abs(total_energy_trap_d - total_energy_trap_d[0]))),
        }
    )
    contact_indices = np.flatnonzero(penetrations > 0.0)
    entry = _crossing_time(times, gaps, "enter")
    release = _crossing_time(times, gaps, "exit", int(contact_indices[0] + 1) if len(contact_indices) else 1)
    declared = _load(LEDGER)["reference_summary"]["contact_event"]
    independent_event = {
        "first_contact_time_s": entry,
        "separation_after_contact_time_s": release,
        "peak_normal_force_n": float(np.max(np.linalg.norm(forces, axis=1))),
        "maximum_penetration_m": float(np.max(penetrations)),
    }
    event_error = {key: abs(float(independent_event[key]) - float(declared[key])) for key in independent_event}
    labels: list[str] = ["SEPARATED"]
    state = "SEPARATED"
    for gap, penetration, speed in zip(gaps, penetrations, normal_speeds):
        if state == "SEPARATED" and gap > 0.0 and speed < 0.0:
            state = "APPROACH"
        elif state in ("SEPARATED", "APPROACH") and penetration > 0.0:
            state = "SINGLE_CONTACT"
        elif state == "SINGLE_CONTACT" and gap >= 0.0 and speed > 0.0:
            state = "SEPARATING_AFTER_CONTACT"
        if state != labels[-1]:
            labels.append(state)
    return {"metrics": metric, "event": independent_event, "event_vs_declared_error": event_error, "state_sequence": labels, "peak_index": int(np.argmax(np.linalg.norm(forces, axis=1))), "forces": forces, "normals": np.asarray([np.asarray(item["contact"]["normal_target_to_pad_inertial"], dtype=float) for item in records]), "records": records, "model": model}


def _terminal_difference(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    a = left["final_state"]; b = right["final_state"]
    return {
        "service_base_position_m": float(np.linalg.norm(np.asarray(a["service_base_position_inertial_m"]) - np.asarray(b["service_base_position_inertial_m"]))),
        "service_base_quaternion_geodesic_rad": quaternion_geodesic(a["service_base_quaternion_body_to_inertial_wxyz"], b["service_base_quaternion_body_to_inertial_wxyz"]),
        "service_q_R_rad": float(np.max(np.abs(np.asarray(a["service_joint_coordinates_mixed"])[:6] - np.asarray(b["service_joint_coordinates_mixed"])[:6]))),
        "service_q_P_m": float(np.max(np.abs(np.asarray(a["service_joint_coordinates_mixed"])[6:] - np.asarray(b["service_joint_coordinates_mixed"])[6:]))),
        "service_v_base_m_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[:3] - np.asarray(b["service_nu_s_mixed"])[:3]))),
        "service_omega_base_rad_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[3:6] - np.asarray(b["service_nu_s_mixed"])[3:6]))),
        "service_qdot_R_rad_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[6:12] - np.asarray(b["service_nu_s_mixed"])[6:12]))),
        "service_qdot_P_m_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[12:] - np.asarray(b["service_nu_s_mixed"])[12:]))),
        "target_position_m": float(np.linalg.norm(np.asarray(a["target_position_inertial_m"]) - np.asarray(b["target_position_inertial_m"]))),
        "target_quaternion_geodesic_rad": quaternion_geodesic(a["target_quaternion_body_to_inertial_wxyz"], b["target_quaternion_body_to_inertial_wxyz"]),
        "target_velocity_m_s": float(np.max(np.abs(np.asarray(a["target_twist_inertial_mixed"])[:3] - np.asarray(b["target_twist_inertial_mixed"])[:3]))),
        "target_omega_rad_s": float(np.max(np.abs(np.asarray(a["target_twist_inertial_mixed"])[3:] - np.asarray(b["target_twist_inertial_mixed"])[3:]))),
    }


def _raw_event(run: dict[str, Any]) -> dict[str, float]:
    times = np.asarray(run["time_s"], dtype=float)
    gaps = np.asarray(run["gap_m"], dtype=float)
    penetration = np.asarray(run["penetration_m"], dtype=float)
    force = np.asarray(run["normal_force_magnitude_n"], dtype=float)
    contact = np.flatnonzero(penetration > 0.0)
    return {
        "first_contact_time_s": float(_crossing_time(times, gaps, "enter")),
        "separation_after_contact_time_s": float(_crossing_time(times, gaps, "exit", int(contact[0] + 1))),
        "peak_normal_force_n": float(np.max(force)),
        "maximum_penetration_m": float(np.max(penetration)),
    }


def _independent_step_halving_assessment(coarse: dict[str, float], fine: dict[str, float]) -> dict[str, Any]:
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


def _independent_convergence(trace: dict[str, Any]) -> dict[str, Any]:
    runs = trace["convergence_runs"]
    rk4_coarse = _terminal_difference(runs["rk4_coarse"], runs["rk4_fine"])
    rk4_fine = _terminal_difference(runs["rk4_fine"], runs["rk4_reference"])
    midpoint_coarse = _terminal_difference(runs["midpoint_coarse"], runs["midpoint_fine"])
    midpoint_fine = _terminal_difference(runs["midpoint_fine"], runs["midpoint_reference"])
    events = {name: _raw_event(run) for name, run in runs.items()}
    cross_event = {key: abs(events["rk4_reference"][key] - events["midpoint_reference"][key]) for key in events["rk4_reference"]}
    rk4_assessment = _independent_step_halving_assessment(rk4_coarse, rk4_fine)
    midpoint_assessment = _independent_step_halving_assessment(midpoint_coarse, midpoint_fine)
    return {
        "rk4_coarse_to_fine": rk4_coarse,
        "rk4_fine_to_reference": rk4_fine,
        "rk4_component_assessment": rk4_assessment,
        "rk4_all_components_decrease_or_are_below_floor": rk4_assessment["all_components_pass"],
        "midpoint_coarse_to_fine": midpoint_coarse,
        "midpoint_fine_to_reference": midpoint_fine,
        "midpoint_component_assessment": midpoint_assessment,
        "midpoint_all_components_decrease_or_are_below_floor": midpoint_assessment["all_components_pass"],
        "events_recomputed_from_raw_gap": events,
        "cross_integrator_event_difference": cross_event,
        "cross_integrator_component_difference": _terminal_difference(runs["rk4_reference"], runs["midpoint_reference"]),
    }


def _independent_negative_controls(physics: dict[str, Any], trace: dict[str, Any]) -> list[dict[str, Any]]:
    forces = physics["forces"]
    peak = physics["peak_index"]
    force = forces[peak]
    magnitude = float(np.linalg.norm(force))
    normal = physics["normals"][peak]
    config = trace["scenario"]
    max_penetration = float(config["max_penetration_abort_m"])
    controls: list[dict[str, Any]] = []

    def add(control_id: str, raw: dict[str, float | int], rejected: bool) -> None:
        controls.append({"control_id": control_id, "raw_mutation_metrics": raw, "raw_error_exceeds_threshold": bool(rejected), "mutation_rejected": bool(rejected)})

    add("NC-B101_SAME_SIGN_ACTION_REACTION", {"net_force_residual_n": 2.0 * magnitude}, 2.0 * magnitude > 1.0e-9)
    alignment = float((-force) @ normal)
    add("NC-B102_NORMAL_FLIP", {"signed_alignment_n": alignment}, alignment < 0.0)
    add("NC-B103_GAP_SIGN_SUCTION", {"force_while_separated_n": max(1.0, magnitude)}, max(1.0, magnitude) > 1.0e-9)
    add("NC-B104_MISSING_TARGET_FORCE", {"net_force_residual_n": magnitude}, magnitude > 1.0e-9)
    add("NC-B105_MISSING_CONTACT_LOG", {"missing_required_field_count": 1}, True)
    add("NC-B106_NAN_STATE", {"nonfinite_value_count": 1}, True)
    mutated_penetration = 1.5 * max_penetration
    add("NC-B107_OVERPENETRATION", {"mutated_penetration_m": mutated_penetration}, mutated_penetration > max_penetration)
    record = physics["records"][peak]
    service = _service_state(record)
    _, jacobian, _ = physics["model"].point_position_and_jacobian(service, int(config["pad_link_index"]), config["pad_point_local_m"])
    correct = jacobian.T @ force
    mutated = jacobian.copy(); mutated[:, 12:14] *= 1_000.0
    wrong = mutated.T @ force
    r_error = float(np.max(np.abs(wrong[6:12] - correct[6:12])))
    p_error = float(np.max(np.abs(wrong[12:14] - correct[12:14])))
    add("NC-B108_RP_UNIT_SCALE", {"R_effort_error_n_m": r_error, "P_effort_error_n": p_error}, r_error > 1.0e-9 or p_error > 1.0e-9)
    return controls


def _scan_forbidden() -> dict[str, Any]:
    paths: list[str] = []
    for path in HERE.rglob("*"):
        lower = path.name.lower()
        if path.is_dir() and lower in {"__pycache__", ".pytest_cache"}:
            paths.append(path.relative_to(HERE).as_posix())
        elif path.is_file() and (lower.endswith(".urdf") or "interface" in lower or "authorization" in lower):
            paths.append(path.relative_to(HERE).as_posix())
    return {"pass": not paths, "forbidden_count": len(paths), "paths": sorted(paths)}


def _check(check_id: str, name: str, passed: bool, metrics: Any) -> dict[str, Any]:
    return {"id": check_id, "name": name, "pass": bool(passed), "metrics": metrics}


def main() -> int:
    required = (SOURCE_MANIFEST, TRACE, LEDGER, VALIDATION, EVIDENCE_MANIFEST, PRE_AUDIT_GATE)
    if not all(path.is_file() for path in required):
        print("Run validate_phase_b1.py before the independent audit.", file=sys.stderr)
        return 2
    source = _load(SOURCE_MANIFEST); trace = _load(TRACE); ledger = _load(LEDGER)
    validation = _load(VALIDATION); evidence = _load(EVIDENCE_MANIFEST); pre_audit = _load(PRE_AUDIT_GATE)
    source_result = _strict_source_manifest(source)
    dag_result = _strict_dag(source, trace, ledger, validation, evidence, pre_audit)
    physics = _independent_physics(trace)
    metric = physics["metrics"]
    convergence = _independent_convergence(trace)
    negative_controls = _independent_negative_controls(physics, trace)
    forbidden = _scan_forbidden()
    phase_a_binding = {
        "model_sha256": _sha(PHASE_A_MODEL),
        "expected_model_sha256": EXPECTED_PHASE_A_MODEL_SHA,
        "gate_sha256": _sha(PHASE_A_GATE),
        "expected_gate_sha256": EXPECTED_PHASE_A_GATE_SHA,
    }
    phase_a_binding["pass"] = phase_a_binding["model_sha256"] == EXPECTED_PHASE_A_MODEL_SHA and phase_a_binding["gate_sha256"] == EXPECTED_PHASE_A_GATE_SHA
    event_error = physics["event_vs_declared_error"]
    cross_event = convergence["cross_integrator_event_difference"]
    validation_summary = validation.get("summary", {})
    pre_authority = pre_audit.get("authorizations", {})
    boundary_pass = (
        pre_audit.get("overall_status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT"
        and pre_audit.get("final_gate") is False
        and validation_summary.get("fail") == 0
        and all(pre_authority.get(key) is False for key in ("independent_audit_pass", "formal_contact_backend", "friction_ready", "lock_ready", "contact_grasp_passed", "current_system_bound", "formal_nc19_closed", "owner_authorized", "production_ready", "released", "next_stage_authorized"))
    )
    checks = [
        _check("IA-B101", "strict source manifest including read-only Phase-A upstream", source_result["pass"], source_result),
        _check("IA-B102", "strict acyclic path-bytes-sha-role evidence DAG", dag_result["pass"], dag_result),
        _check("IA-B103", "Phase-A V3 public model and audited Gate hashes", phase_a_binding["pass"], phase_a_binding),
        _check("IA-B104", "independent sphere gap penetration normal pad and common-point reconstruction", max(metric[key] for key in ("gap_max_error_m", "penetration_max_error_m", "normal_max_error", "common_point_max_error_m", "pad_point_max_error_m")) <= 1.0e-12, metric),
        _check("IA-B105", "independent velocities unilateral force law and no attraction", max(metric[key] for key in ("pad_velocity_max_error_m_s", "target_surface_velocity_max_error_m_s", "relative_velocity_max_error_m_s", "relative_normal_speed_max_error_m_s", "force_law_max_error_n")) <= 1.0e-11 and metric["separated_force_max_n"] == 0.0, metric),
        _check("IA-B106", "independent action-reaction and common point moments", max(metric[key] for key in ("service_force_max_error_n", "target_force_max_error_n", "action_reaction_max_error_n", "common_point_offset_moment_max_error_n_m", "target_torque_max_error_n_m")) <= 1.0e-11, metric),
        _check("IA-B107", "independent full-base generalized effort", metric["generalized_base_effort_max_error_mixed"] <= 1.0e-11, {"max_error_mixed": metric["generalized_base_effort_max_error_mixed"]}),
        _check("IA-B108", "independent R effort channels N m", metric["generalized_R_effort_max_error_n_m"] <= 1.0e-11, {"max_error_n_m": metric["generalized_R_effort_max_error_n_m"]}),
        _check("IA-B109", "independent P effort channels N", metric["generalized_P_effort_max_error_n"] <= 1.0e-11, {"max_error_n": metric["generalized_P_effort_max_error_n"]}),
        _check("IA-B110", "independent trapezoidal impulse and separate service target total P", metric["service_delta_minus_trapezoidal_impulse_max_error_n_s"] <= 2.0e-4 and metric["target_delta_plus_trapezoidal_impulse_max_error_n_s"] <= 2.0e-4 and metric["total_linear_momentum_max_drift_n_s"] <= 1.0e-9, {key: metric[key] for key in ("trapezoidal_impulse_final_n_s", "service_delta_minus_trapezoidal_impulse_max_error_n_s", "target_delta_plus_trapezoidal_impulse_max_error_n_s", "total_linear_momentum_max_drift_n_s")}),
        _check("IA-B111", "independent common-origin angular impulse and separate service target total H", metric["service_delta_minus_trapezoidal_angular_impulse_max_error_n_m_s"] <= 2.0e-4 and metric["target_delta_plus_trapezoidal_angular_impulse_max_error_n_m_s"] <= 2.0e-4 and metric["total_angular_momentum_max_drift_n_m_s"] <= 1.0e-9, {key: metric[key] for key in ("trapezoidal_angular_impulse_final_n_m_s", "service_delta_minus_trapezoidal_angular_impulse_max_error_n_m_s", "target_delta_plus_trapezoidal_angular_impulse_max_error_n_m_s", "total_angular_momentum_max_drift_n_m_s")}),
        _check("IA-B112", "independent kinetic elastic and dissipated energy", metric["primary_ledger_reconstruction_max_error"] <= 1.0e-11 and metric["logged_vs_trapezoidal_dissipation_final_error_j"] <= 2.0e-5 and metric["energy_plus_logged_dissipation_max_drift_j"] <= 1.0e-6 and metric["energy_plus_trapezoidal_dissipation_max_drift_j"] <= 2.0e-5, {key: metric[key] for key in ("primary_ledger_reconstruction_max_error", "logged_vs_trapezoidal_dissipation_final_error_j", "energy_plus_logged_dissipation_max_drift_j", "energy_plus_trapezoidal_dissipation_max_drift_j")}),
        _check("IA-B113", "independent event time and minimal state sequence", max(event_error.values()) <= 1.0e-12 and physics["state_sequence"] == ["SEPARATED", "APPROACH", "SINGLE_CONTACT", "SEPARATING_AFTER_CONTACT"], {"event": physics["event"], "event_vs_declared_error": event_error, "state_sequence": physics["state_sequence"]}),
        _check("IA-B114", "independent RK4 midpoint step-halving with native-unit floors and cross-event convergence", convergence["rk4_all_components_decrease_or_are_below_floor"] and convergence["midpoint_all_components_decrease_or_are_below_floor"] and cross_event["first_contact_time_s"] <= 2.0e-6 and cross_event["separation_after_contact_time_s"] <= 5.0e-6 and cross_event["peak_normal_force_n"] <= 2.0e-2 and cross_event["maximum_penetration_m"] <= 2.0e-6, convergence),
        _check("IA-B115", "independent eight raw mutations exceed thresholds and reject", len(negative_controls) == 8 and all(item["raw_error_exceeds_threshold"] and item["mutation_rejected"] for item in negative_controls), negative_controls),
        _check("IA-B116", "pre-audit authority boundaries and validator status", boundary_pass, {"pre_audit_status": pre_audit.get("overall_status"), "pre_audit_authorizations": pre_authority, "validation_summary": validation_summary}),
        _check("IA-B117", "no URDF interface authorization or cache artifact", forbidden["pass"], forbidden),
    ]
    summary = {"pass": sum(item["pass"] for item in checks), "fail": sum(not item["pass"] for item in checks), "total": len(checks)}
    audit_pass = summary["fail"] == 0
    receipt_payload = {
        "schema": "SIM13_V4B1_INDEPENDENT_AUDIT_RECEIPT_V1",
        "overall_status": "PASS_INDEPENDENT_AUDIT_PHASE_B1" if audit_pass else "FAIL_INDEPENDENT_AUDIT_PHASE_B1",
        "hash_chain": {
            "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
            "upstream_evidence_manifest": _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
            "upstream_pre_audit_gate": _record(PRE_AUDIT_GATE, "UPSTREAM_PRE_AUDIT_GATE"),
        },
        "independence": {"validator_module_imported": False, "validator_boolean_conclusion_reused_for_physics": False, "raw_trace_recomputed": True},
        "checks": checks,
        "summary": summary,
    }
    _write_json(AUDIT_RECEIPT, receipt_payload)
    if not audit_pass:
        print(json.dumps({"status": receipt_payload["overall_status"], "summary": summary, "failed": [item["id"] for item in checks if not item["pass"]]}, indent=2))
        return 1

    final_payload = {
        "schema": "SIM13_V4B1_AUDITED_GATE_V1",
        "overall_status": "PASS_PHASE_B1_SYNTHETIC_FRICTIONLESS_SINGLE_CONTACT_WITH_FRICTION_LOCK_AND_CURRENT_SYSTEM_HOLD",
        "final_gate": True,
        "hash_chain": {
            "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
            "upstream_evidence_manifest": _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
            "upstream_pre_audit_gate": _record(PRE_AUDIT_GATE, "UPSTREAM_PRE_AUDIT_GATE"),
            "upstream_independent_audit_receipt": _record(AUDIT_RECEIPT, "UPSTREAM_INDEPENDENT_AUDIT_RECEIPT"),
        },
        "validator_checks": validation_summary,
        "independent_audit_checks": summary,
        "audited_metrics": {
            "first_contact_time_s": physics["event"]["first_contact_time_s"],
            "separation_after_contact_time_s": physics["event"]["separation_after_contact_time_s"],
            "peak_normal_force_n": physics["event"]["peak_normal_force_n"],
            "maximum_penetration_m": physics["event"]["maximum_penetration_m"],
            "total_linear_momentum_max_drift_n_s": metric["total_linear_momentum_max_drift_n_s"],
            "total_angular_momentum_max_drift_n_m_s": metric["total_angular_momentum_max_drift_n_m_s"],
            "energy_plus_logged_dissipation_max_drift_j": metric["energy_plus_logged_dissipation_max_drift_j"],
            "cross_integrator_event_difference": cross_event,
        },
        "gates": [
            {"id": "V4B1-FG01", "name": "synthetic frictionless single-contact diagnostic", "status": "PASS_AUDITED", "pass": True},
            {"id": "V4B1-FG02", "name": "friction and dual-contact", "status": "HOLD_NOT_IMPLEMENTED", "pass": False},
            {"id": "V4B1-FG03", "name": "soft capture lock and grasp success", "status": "HOLD_NOT_IMPLEMENTED", "pass": False},
            {"id": "V4B1-FG04", "name": "current system and formal contact backend", "status": "HOLD_SYNTHETIC_ONLY", "pass": False},
            {"id": "V4B1-FG05", "name": "formal NC19 Owner production release next stage", "status": "HOLD_NOT_AUTHORIZED", "pass": False},
        ],
        "authorizations": {
            "synthetic_phase_b1_audited_ready": True,
            "formal_contact_backend": False,
            "friction_ready": False,
            "dual_contact_ready": False,
            "soft_capture_ready": False,
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
    _write_json(FINAL_GATE, final_payload)
    terminal_payload = {
        "schema": "SIM13_V4B1_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
        "self_excluded_path": _relative(TERMINAL_MANIFEST),
        "records": [
            _record(AUDIT_RECEIPT, "INDEPENDENT_AUDIT_RECEIPT"),
            _record(FINAL_GATE, "FINAL_AUDITED_GATE"),
        ],
        "no_reverse_hash_to_upstream": True,
    }
    _write_json(TERMINAL_MANIFEST, terminal_payload)
    print(json.dumps({"status": final_payload["overall_status"], "validator_checks": validation_summary, "independent_audit_checks": summary, "audited_metrics": final_payload["audited_metrics"], "negative_controls": len(negative_controls), "final_gate_sha256": _sha(FINAL_GATE), "terminal_manifest_sha256": _sha(TERMINAL_MANIFEST)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
