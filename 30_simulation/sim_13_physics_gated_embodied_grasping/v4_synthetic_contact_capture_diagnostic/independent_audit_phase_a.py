"""Independent V4A audit and sole issuer of the final audited Gate.

The validator is never imported.  For the Euler--Lagrange path, primary
acceleration is consumed from a hash-bound ledger while M, Mdot and dM/dq are
rebuilt from finite-difference body kinematics; that path never calls the
primary bias-effort routine.  The separate legacy P/H/E and integrator checks
do run the public primary propagator and are labelled accordingly.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np

from sim13_v4a.full_floating import (
    ServiceState,
    TargetState,
    TARGET_INERTIA_BODY_KG_M2,
    TARGET_MASS_KG,
    deterministic_scenario,
    deterministic_el_audit_states,
    deterministic_stress_points,
    propagate_no_contact,
    quaternion_geodesic,
)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
SOURCE_MANIFEST = HERE / "evidence/SIM13_V4A_PHASE_A_SOURCE_MANIFEST_V3.json"
LEDGER = HERE / "evidence/SIM13_V4A_PHASE_A_DYNAMICS_LEDGER_V3.json"
VALIDATION = HERE / "evidence/SIM13_V4A_PHASE_A_VALIDATION_V3.json"
EVIDENCE_MANIFEST = HERE / "evidence/SIM13_V4A_PHASE_A_EVIDENCE_MANIFEST_V3.json"
PRE_AUDIT_GATE = HERE / "results/SIM13_V4A_PHASE_A_PRE_AUDIT_GATE_V3.json"
AUDIT_RECEIPT = HERE / "evidence/SIM13_V4A_PHASE_A_INDEPENDENT_AUDIT_RECEIPT_V3.json"
FINAL_GATE = HERE / "results/SIM13_V4A_PHASE_A_AUDITED_GATE_V3.json"
TERMINAL_MANIFEST = HERE / "results/SIM13_V4A_PHASE_A_TERMINAL_SELF_EXCLUDED_MANIFEST_V3.json"

INNER_STEP = 2.0e-3
EL_EPSILONS = (5.0e-7, 1.0e-6, 2.0e-6)
EL_R_LIMIT_N_M = 1.0e-7
EL_P_LIMIT_N = 1.0e-7
EL_SCALED_LIMIT = 1.0e-6


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
        return {"pass": False, "expected_path": _relative(expected_path), "expected_role": expected_role, "errors": ["REFERENCE_NOT_OBJECT"]}
    if set(reference) != {"role", "path", "bytes", "sha256"}:
        errors.append("REFERENCE_KEYS_NOT_EXACT")
    if reference.get("role") != expected_role:
        errors.append("ROLE_MISMATCH_OR_UNKNOWN")
    if reference.get("path") != _relative(expected_path):
        errors.append("PATH_MISMATCH")
    resolved, path_error = _resolve_inside_project(reference.get("path"))
    if path_error:
        errors.append(path_error)
    actual_bytes = resolved.stat().st_size if resolved is not None and resolved.is_file() else None
    actual_sha = _sha(resolved) if resolved is not None and resolved.is_file() else None
    if actual_bytes is None:
        errors.append("TARGET_NOT_FILE")
    else:
        if reference.get("bytes") != actual_bytes:
            errors.append("BYTE_COUNT_MISMATCH")
        if reference.get("sha256") != actual_sha:
            errors.append("SHA256_MISMATCH")
    return {
        "pass": not errors,
        "expected_path": _relative(expected_path),
        "expected_role": expected_role,
        "declared": reference,
        "actual_bytes": actual_bytes,
        "actual_sha256": actual_sha,
        "errors": errors,
    }


def _expected_source_paths() -> list[Path]:
    paths = [
        HERE / "README.md",
        HERE / "pytest.ini",
        HERE / "validate_phase_a.py",
        HERE / "independent_audit_phase_a.py",
        HERE / "contracts/SYNTHETIC_FULL_FLOATING_MODEL_CONTRACT_V1.json",
        HERE / "contracts/GOVERNANCE_BOUNDARY_V1.json",
    ]
    paths.extend(sorted((HERE / "sim13_v4a").glob("*.py")))
    paths.extend(sorted((HERE / "tests").glob("*.py")))
    return sorted(set(paths), key=_relative)


def _strict_source_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    expected = _expected_source_paths()
    records = payload.get("records")
    errors: list[str] = []
    if payload.get("schema") != "SIM13_V4A_PHASE_A_SOURCE_MANIFEST_V3":
        errors.append("SOURCE_SCHEMA_MISMATCH")
    if payload.get("self_excluded_path") != _relative(SOURCE_MANIFEST):
        errors.append("SOURCE_SELF_EXCLUSION_MISMATCH")
    if not isinstance(records, list):
        return {"pass": False, "errors": errors + ["SOURCE_RECORDS_NOT_LIST"], "edge_checks": []}
    paths = [item.get("path") for item in records if isinstance(item, dict)]
    if len(paths) != len(set(paths)):
        errors.append("DUPLICATE_SOURCE_PATH")
    if paths != [_relative(path) for path in expected]:
        errors.append("SOURCE_PATH_SET_OR_ORDER_MISMATCH")
    if _relative(SOURCE_MANIFEST) in paths:
        errors.append("SOURCE_MANIFEST_SELF_REFERENCE")
    checks = [
        _strict_reference(records[index] if index < len(records) else None, path, "FROZEN_SOURCE_INPUT")
        for index, path in enumerate(expected)
    ]
    if len(records) != len(expected):
        errors.append("SOURCE_RECORD_COUNT_MISMATCH")
    if not all(item["pass"] for item in checks):
        errors.append("SOURCE_EDGE_INTEGRITY_FAILURE")
    return {"pass": not errors, "errors": errors, "edge_checks": checks}


def _strict_evidence_graph(
    source_payload: dict[str, Any],
    ledger_payload: dict[str, Any],
    validation_payload: dict[str, Any],
    evidence_payload: dict[str, Any],
    pre_audit_payload: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    edge_checks: list[dict[str, Any]] = []
    source_edges = (
        (ledger_payload.get("hash_chain", {}).get("upstream_source_manifest"), "ledger_to_source"),
        (validation_payload.get("hash_chain", {}).get("upstream_source_manifest"), "validation_to_source"),
        (evidence_payload.get("upstream_source_manifest"), "evidence_to_source"),
        (pre_audit_payload.get("hash_chain", {}).get("upstream_source_manifest"), "pre_audit_to_source"),
    )
    for reference, edge_name in source_edges:
        check = _strict_reference(reference, SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST")
        check["edge"] = edge_name
        edge_checks.append(check)
    records = evidence_payload.get("records")
    if evidence_payload.get("schema") != "SIM13_V4A_PHASE_A_EVIDENCE_MANIFEST_V3":
        errors.append("EVIDENCE_SCHEMA_MISMATCH")
    if evidence_payload.get("self_excluded_path") != _relative(EVIDENCE_MANIFEST):
        errors.append("EVIDENCE_SELF_EXCLUSION_MISMATCH")
    if not isinstance(records, list):
        errors.append("EVIDENCE_RECORDS_NOT_LIST")
        records = []
    paths = [item.get("path") for item in records if isinstance(item, dict)]
    if len(paths) != len(set(paths)):
        errors.append("DUPLICATE_EVIDENCE_PATH")
    expectations = ((LEDGER, "DYNAMICS_LEDGER"), (VALIDATION, "VALIDATION_EVIDENCE"))
    if len(records) != len(expectations):
        errors.append("EVIDENCE_RECORD_COUNT_MISMATCH")
    for index, (path, role) in enumerate(expectations):
        check = _strict_reference(records[index] if index < len(records) else None, path, role)
        check["edge"] = f"evidence_to_{role.lower()}"
        edge_checks.append(check)
    check = _strict_reference(
        pre_audit_payload.get("hash_chain", {}).get("upstream_evidence_manifest"),
        EVIDENCE_MANIFEST,
        "UPSTREAM_EVIDENCE_MANIFEST",
    )
    check["edge"] = "pre_audit_to_evidence"
    edge_checks.append(check)
    schemas = {
        source_payload.get("schema"),
        ledger_payload.get("schema"),
        validation_payload.get("schema"),
        evidence_payload.get("schema"),
        pre_audit_payload.get("schema"),
    }
    if schemas != {
        "SIM13_V4A_PHASE_A_SOURCE_MANIFEST_V3",
        "SIM13_V4A_PHASE_A_DYNAMICS_LEDGER_V3",
        "SIM13_V4A_PHASE_A_VALIDATION_V3",
        "SIM13_V4A_PHASE_A_EVIDENCE_MANIFEST_V3",
        "SIM13_V4A_PHASE_A_PRE_AUDIT_GATE_V3",
    }:
        errors.append("UNKNOWN_OR_DUPLICATE_SCHEMA_ROLE")
    if not all(item["pass"] for item in edge_checks):
        errors.append("STRICT_EDGE_PATH_BYTES_SHA_ROLE_FAILURE")
    return {"pass": not errors, "errors": errors, "edge_checks": edge_checks}


def _strict_acyclic_boundary(source_payload: dict[str, Any], evidence_payload: dict[str, Any]) -> dict[str, Any]:
    source_paths = {item.get("path") for item in source_payload.get("records", []) if isinstance(item, dict)}
    evidence_paths = {item.get("path") for item in evidence_payload.get("records", []) if isinstance(item, dict)}
    generated = {
        _relative(SOURCE_MANIFEST), _relative(LEDGER), _relative(VALIDATION),
        _relative(EVIDENCE_MANIFEST), _relative(PRE_AUDIT_GATE),
        _relative(AUDIT_RECEIPT), _relative(FINAL_GATE), _relative(TERMINAL_MANIFEST),
    }
    downstream = {_relative(AUDIT_RECEIPT), _relative(FINAL_GATE), _relative(TERMINAL_MANIFEST)}
    errors: list[str] = []
    if source_paths & generated:
        errors.append("SOURCE_MANIFEST_HAS_GENERATED_BACK_EDGE")
    if evidence_paths != {_relative(LEDGER), _relative(VALIDATION)}:
        errors.append("EVIDENCE_MANIFEST_HAS_UNKNOWN_OR_BACK_EDGE")
    if evidence_paths & downstream:
        errors.append("EVIDENCE_MANIFEST_HAS_DOWNSTREAM_BACK_EDGE")
    downstream_absent = not any(path.is_file() for path in (AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST))
    if not downstream_absent:
        errors.append("STALE_DOWNSTREAM_PRESENT_AT_AUDIT_ENTRY")
    return {
        "pass": not errors,
        "errors": errors,
        "downstream_targets_absent_at_audit_entry": downstream_absent,
        "root_escape_allowed": False,
        "self_reference_allowed": False,
        "back_edge_allowed": False,
        "topological_order": [
            "source_inputs", "source_manifest", "ledger_and_validation",
            "evidence_manifest", "pre_audit_gate", "independent_audit_receipt",
            "final_audited_gate", "terminal_self_excluded_manifest",
        ],
    }


def _vee(matrix: np.ndarray) -> np.ndarray:
    return np.array((matrix[2, 1], matrix[0, 2], matrix[1, 0]))


def _column_step(column: int) -> tuple[float, str]:
    return (INNER_STEP, "m") if column < 3 or column >= 12 else (INNER_STEP, "rad")


def _independent_body_jacobians(model, state: ServiceState) -> list[tuple[np.ndarray, np.ndarray]]:
    """Five-point body-position/orientation derivative; analytic J is unused."""
    center = model.kinematics(state)
    jacobians = [(np.zeros((3, 14)), np.zeros((3, 14))) for _ in center.bodies]
    for column in range(14):
        step, _ = _column_step(column)
        shifted = [
            model.kinematics(model.perturb_configuration(state, column, multiple * step))
            for multiple in (2.0, 1.0, -1.0, -2.0)
        ]
        for body_index, body in enumerate(center.bodies):
            plus_two, plus_one, minus_one, minus_two = [item.bodies[body_index] for item in shifted]
            jv, jw = jacobians[body_index]
            jv[:, column] = (
                -plus_two.position_inertial_m + 8.0 * plus_one.position_inertial_m
                - 8.0 * minus_one.position_inertial_m + minus_two.position_inertial_m
            ) / (12.0 * step)
            rotation_rate = (
                -plus_two.rotation_body_to_inertial + 8.0 * plus_one.rotation_body_to_inertial
                - 8.0 * minus_one.rotation_body_to_inertial + minus_two.rotation_body_to_inertial
            ) / (12.0 * step)
            omega_cross = rotation_rate @ body.rotation_body_to_inertial.T
            jw[:, column] = _vee(0.5 * (omega_cross - omega_cross.T))
    return jacobians


def _independent_mass_matrix(model, state: ServiceState) -> np.ndarray:
    center = model.kinematics(state)
    matrix = np.zeros((14, 14))
    for body, (jv, jw) in zip(center.bodies, _independent_body_jacobians(model, state)):
        matrix += body.mass_kg * jv.T @ jv + jw.T @ body.inertia_inertial_kg_m2 @ jw
    return 0.5 * (matrix + matrix.T)


def _independent_service_ledger(model, state: ServiceState) -> dict[str, Any]:
    center = model.kinematics(state)
    linear, angular, energy = np.zeros(3), np.zeros(3), 0.0
    for body, (jv, jw) in zip(center.bodies, _independent_body_jacobians(model, state)):
        velocity, omega = jv @ state.nu_s_mixed, jw @ state.nu_s_mixed
        body_linear = body.mass_kg * velocity
        spin = body.inertia_inertial_kg_m2 @ omega
        linear += body_linear
        angular += np.cross(body.position_inertial_m, body_linear) + spin
        energy += 0.5 * body.mass_kg * float(velocity @ velocity) + 0.5 * float(omega @ spin)
    return {"P_n_s": linear, "H_about_inertial_origin_n_m_s": angular, "E_j": float(energy)}


def _quat_product(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array((
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ))


def _quat_from_rotvec(vector: np.ndarray) -> np.ndarray:
    angle = float(np.linalg.norm(vector))
    result = np.array((1.0, *(0.5 * vector))) if angle < 1.0e-15 else np.array(
        (math.cos(0.5 * angle), *((vector / angle) * math.sin(0.5 * angle)))
    )
    return result / np.linalg.norm(result)


def _quat_rotation(quaternion: np.ndarray) -> np.ndarray:
    w, x, y, z = quaternion / np.linalg.norm(quaternion)
    return np.array((
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    ))


def _shift_flow(state: ServiceState, epsilon_s: float) -> ServiceState:
    velocity = state.nu_s_mixed
    quaternion = _quat_product(
        _quat_from_rotvec(epsilon_s * velocity[3:6]),
        state.base_quaternion_body_to_inertial_wxyz,
    )
    quaternion /= np.linalg.norm(quaternion)
    return ServiceState(
        state.base_position_inertial_m + epsilon_s * velocity[:3], quaternion,
        state.joint_coordinates_mixed + epsilon_s * velocity[6:], velocity.copy(),
    )


def _centered_derivative(function: Callable[[float], np.ndarray], epsilon: float) -> np.ndarray:
    return (function(epsilon) - function(-epsilon)) / (2.0 * epsilon)


def _primary_acceleration_map(ledger: dict[str, Any]) -> dict[str, np.ndarray]:
    registry = ledger["primary_zero_external_accelerations_for_independent_el_audit"]
    result: dict[str, np.ndarray] = {}
    for case in registry["cases"]:
        item = case["primary_acceleration"]
        result[case["case_id"]] = np.asarray(
            item["base_linear_m_s2"]
            + item["base_angular_rad_s2"]
            + item["joint_R_rad_s2"]
            + item["joint_P_m_s2"],
            dtype=float,
        )
    return result


def _independent_el_audit(model, state: ServiceState, acceleration: np.ndarray) -> dict[str, Any]:
    velocity = state.nu_s_mixed
    mass = _independent_mass_matrix(model, state)
    per_epsilon, residual_vectors = [], []
    for epsilon in EL_EPSILONS:
        mass_dot = _centered_derivative(
            lambda offset: _independent_mass_matrix(model, _shift_flow(state, offset)), epsilon
        )
        mass_acceleration, mass_dot_velocity = mass @ acceleration, mass_dot @ velocity
        residual, terms = np.empty(8), []
        for joint_index in range(8):
            derivative = _centered_derivative(
                lambda offset, index=joint_index: _independent_mass_matrix(
                    model, model.perturb_configuration(state, 6 + index, offset)
                ), epsilon
            )
            gradient = 0.5 * float(velocity @ derivative @ velocity)
            residual[joint_index] = mass_acceleration[6 + joint_index] + mass_dot_velocity[6 + joint_index] - gradient
            terms.append({
                "joint_index": joint_index,
                "joint_type": "R" if joint_index < 6 else "P",
                "M_a": float(mass_acceleration[6 + joint_index]),
                "Mdot_nu": float(mass_dot_velocity[6 + joint_index]),
                "half_nu_dM_nu": gradient,
                "residual": float(residual[joint_index]),
                "unit": "N*m" if joint_index < 6 else "N",
            })
        residual_vectors.append(residual)
        max_r, max_p = float(np.max(np.abs(residual[:6]))), float(np.max(np.abs(residual[6:])))
        per_epsilon.append({
            "epsilon_mixed": epsilon, "epsilon_R_unit": "rad", "epsilon_P_unit": "m",
            "R_max_abs_n_m": max_r, "P_max_abs_n": max_p,
            "R_scaled_by_reference_1_n_m": max_r,
            "P_scaled_by_reference_1_n": max_p,
            "terms": terms,
        })
    stack = np.vstack(residual_vectors)
    envelope_r, envelope_p = float(np.max(np.abs(stack[:, :6]))), float(np.max(np.abs(stack[:, 6:])))
    return {
        "method": "FIVE_POINT_BODY_KINEMATICS_M_FD_PLUS_CENTERED_OUTER_DERIVATIVES",
        "primary_bias_effort_called": False,
        "primary_acceleration_source": "HASH_BOUND_VALIDATOR_LEDGER",
        "inner_five_point_steps": {"base_linear_m": INNER_STEP, "base_angular_rad": INNER_STEP, "R_rad": INNER_STEP, "P_m": INNER_STEP},
        "per_outer_epsilon": per_epsilon,
        "platform_envelope": {
            "R_max_abs_n_m": envelope_r, "P_max_abs_n": envelope_p,
            "R_scaled_by_reference_1_n_m": envelope_r,
            "P_scaled_by_reference_1_n": envelope_p,
            "scaling_reference": {
                "R": "fixed 1 N*m diagnostic scaling reference",
                "P": "fixed 1 N diagnostic scaling reference"
            },
            "absolute_limits": {"R_n_m": EL_R_LIMIT_N_M, "P_n": EL_P_LIMIT_N},
            "scaled_limit": EL_SCALED_LIMIT,
            "all_three_epsilons_pass": all(
                item["R_max_abs_n_m"] <= EL_R_LIMIT_N_M
                and item["P_max_abs_n"] <= EL_P_LIMIT_N
                and item["R_scaled_by_reference_1_n_m"] <= EL_SCALED_LIMIT
                and item["P_scaled_by_reference_1_n"] <= EL_SCALED_LIMIT
                for item in per_epsilon
            ),
        },
        "nominal_residual_at_1e_6": residual_vectors[1].tolist(),
        "mass_matrix_mixed": mass,
    }


def _nullspace_mutation(state: ServiceState, mass: np.ndarray, nominal: np.ndarray) -> dict[str, Any]:
    rates = state.nu_s_mixed[6:]
    effort = np.array((0.0, -0.018, 0.009, -0.014, 0.011, -0.007, 0.025, -0.017))
    effort[0] = -float(np.dot(rates[1:], effort[1:]) / rates[0])
    full_effort = np.concatenate((np.zeros(6), effort))
    wrong_acceleration = np.linalg.solve(mass, full_effort)
    recovered = mass @ wrong_acceleration
    linear_defect = float(np.linalg.norm(recovered[:3]))
    angular_defect = float(np.linalg.norm(recovered[3:6]))
    power = float(state.nu_s_mixed @ recovered)
    mutated = nominal + effort
    max_r, max_p = float(np.max(np.abs(mutated[:6]))), float(np.max(np.abs(mutated[6:])))
    return {
        "mutation_id": "NC-A07_MOMENTUM_ENERGY_NULLSPACE_INTERNAL_ACCELERATION",
        "construction": "M_fd_delta_a=[zero_base_wrench(6),g_internal(8)]_and_qdot_dot_g_zero",
        "injected_internal_generalized_effort": {
            "R_n_m": effort[:6].tolist(), "P_n": effort[6:].tolist(),
            "R_max_abs_n_m": float(np.max(np.abs(effort[:6]))),
            "P_max_abs_n": float(np.max(np.abs(effort[6:]))),
        },
        "wrong_acceleration": {
            "base_linear_m_s2": wrong_acceleration[:3].tolist(),
            "base_angular_rad_s2": wrong_acceleration[3:6].tolist(),
            "joint_R_rad_s2": wrong_acceleration[6:12].tolist(),
            "joint_P_m_s2": wrong_acceleration[12:].tolist(),
        },
        "legacy_invariant_blind_spot": {
            "linear_momentum_rate_defect_n": linear_defect,
            "angular_momentum_rate_defect_n_m": angular_defect,
            "kinetic_energy_power_injection_w": power,
            "legacy_instantaneous_P_H_E_guards_would_accept": linear_defect < 1.0e-10 and angular_defect < 1.0e-10 and abs(power) < 1.0e-12,
        },
        "new_el_guard": {
            "mutated_R_max_abs_n_m": max_r, "mutated_P_max_abs_n": max_p,
            "R_limit_n_m": EL_R_LIMIT_N_M, "P_limit_n": EL_P_LIMIT_N,
            "detected": max_r > EL_R_LIMIT_N_M and max_p > EL_P_LIMIT_N,
        },
    }


def _power_orthogonal_internal_effort(joint_rates: np.ndarray) -> np.ndarray:
    """Fixed nonzero R/P effort seed, balanced to zero instantaneous power."""
    effort = np.array((0.0, -0.018, 0.009, -0.014, 0.011, -0.007, 0.025, -0.017))
    balance_index = int(np.argmax(np.abs(joint_rates[:6])))
    if abs(float(joint_rates[balance_index])) < 1.0e-6:
        raise ValueError("registered wrong-ODE balance R rate became singular")
    other_power = float(np.dot(joint_rates, effort) - joint_rates[balance_index] * effort[balance_index])
    effort[balance_index] = -other_power / joint_rates[balance_index]
    return effort


def _service_vector(state: ServiceState) -> np.ndarray:
    return np.concatenate((
        state.base_position_inertial_m,
        state.base_quaternion_body_to_inertial_wxyz,
        state.joint_coordinates_mixed,
        state.nu_s_mixed,
    ))


def _service_state(vector: np.ndarray) -> ServiceState:
    value = np.asarray(vector, dtype=float)
    quaternion = value[3:7] / np.linalg.norm(value[3:7])
    return ServiceState(value[:3].copy(), quaternion, value[7:15].copy(), value[15:29].copy())


def _wrong_ode_rhs(model, vector: np.ndarray) -> np.ndarray:
    state = _service_state(vector)
    primary_acceleration = model.acceleration_zero_external(state)
    mass = model.mass_matrix(state)
    internal_effort = _power_orthogonal_internal_effort(state.nu_s_mixed[6:])
    wrong_increment = np.linalg.solve(
        mass, np.concatenate((np.zeros(6), internal_effort))
    )
    quaternion_rate = 0.5 * _quat_product(
        np.array((0.0, *state.nu_s_mixed[3:6])),
        state.base_quaternion_body_to_inertial_wxyz,
    )
    return np.concatenate((
        state.nu_s_mixed[:3], quaternion_rate, state.nu_s_mixed[6:],
        primary_acceleration + wrong_increment,
    ))


def _wrong_ode_step(model, vector: np.ndarray, step_s: float) -> np.ndarray:
    k1 = _wrong_ode_rhs(model, vector)
    k2 = _wrong_ode_rhs(model, vector + 0.5 * step_s * k1)
    k3 = _wrong_ode_rhs(model, vector + 0.5 * step_s * k2)
    k4 = _wrong_ode_rhs(model, vector + step_s * k3)
    result = vector + (step_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    result[3:7] /= np.linalg.norm(result[3:7])
    return result


def _propagate_wrong_ode(model, initial: ServiceState, step_s: float, steps: int) -> dict[str, np.ndarray]:
    vector = _service_vector(initial)
    states = np.empty((steps + 1, 29))
    linear = np.empty((steps + 1, 3))
    angular = np.empty((steps + 1, 3))
    energy = np.empty(steps + 1)
    power = np.empty(steps + 1)
    base_linear_effort = np.empty(steps + 1)
    base_angular_effort = np.empty(steps + 1)
    effort_r = np.empty((steps + 1, 6))
    effort_p = np.empty((steps + 1, 2))
    for index in range(steps + 1):
        state = _service_state(vector)
        vector[3:7] = state.base_quaternion_body_to_inertial_wxyz
        ledger = model.momentum_energy(state)
        mass = model.mass_matrix(state)
        internal_effort = _power_orthogonal_internal_effort(state.nu_s_mixed[6:])
        wrong_increment = np.linalg.solve(
            mass, np.concatenate((np.zeros(6), internal_effort))
        )
        recovered = mass @ wrong_increment
        states[index] = vector
        linear[index] = ledger.linear_momentum_n_s
        angular[index] = ledger.angular_momentum_about_inertial_origin_n_m_s
        energy[index] = ledger.kinetic_energy_j
        power[index] = state.nu_s_mixed @ recovered
        base_linear_effort[index] = np.linalg.norm(recovered[:3])
        base_angular_effort[index] = np.linalg.norm(recovered[3:6])
        effort_r[index] = internal_effort[:6]
        effort_p[index] = internal_effort[6:]
        if index < steps:
            vector = _wrong_ode_step(model, vector, step_s)
    return {
        "states": states,
        "linear_momentum_n_s": linear,
        "angular_momentum_n_m_s": angular,
        "kinetic_energy_j": energy,
        "power_injection_w": power,
        "base_linear_effort_n": base_linear_effort,
        "base_angular_effort_n_m": base_angular_effort,
        "effort_R_n_m": effort_r,
        "effort_P_n": effort_p,
        "time_s": np.arange(steps + 1, dtype=float) * step_s,
    }


def _relative_vector_drift(values: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(values[0])), 1.0e-12)
    return float(np.max(np.linalg.norm(values - values[0], axis=1)) / denominator)


def _relative_scalar_drift(values: np.ndarray) -> float:
    denominator = max(abs(float(values[0])), 1.0e-12)
    return float(np.max(np.abs(values - values[0])) / denominator)


def _wrong_ode_integration_evidence(model, initial: ServiceState) -> dict[str, Any]:
    coarse = _propagate_wrong_ode(model, initial, 1.0e-3, 40)
    fine = _propagate_wrong_ode(model, initial, 5.0e-4, 80)
    coarse_final, fine_final = coarse["states"][-1], fine["states"][-1]
    convergence = {
        "base_position_m": float(np.linalg.norm(coarse_final[:3] - fine_final[:3])),
        "base_quaternion_geodesic_rad": quaternion_geodesic(coarse_final[3:7], fine_final[3:7]),
        "joint_R_rad": float(np.max(np.abs(coarse_final[7:13] - fine_final[7:13]))),
        "joint_P_m": float(np.max(np.abs(coarse_final[13:15] - fine_final[13:15]))),
        "base_velocity_m_s": float(np.max(np.abs(coarse_final[15:18] - fine_final[15:18]))),
        "base_omega_rad_s": float(np.max(np.abs(coarse_final[18:21] - fine_final[18:21]))),
        "joint_R_velocity_rad_s": float(np.max(np.abs(coarse_final[21:27] - fine_final[21:27]))),
        "joint_P_velocity_m_s": float(np.max(np.abs(coarse_final[27:29] - fine_final[27:29]))),
    }
    convergence_limits = {name: 2.0e-7 for name in convergence}
    def legacy_metrics(history: dict[str, np.ndarray]) -> dict[str, float]:
        return {
            "linear_momentum_relative_drift": _relative_vector_drift(history["linear_momentum_n_s"]),
            "angular_momentum_relative_drift": _relative_vector_drift(history["angular_momentum_n_m_s"]),
            "kinetic_energy_relative_drift": _relative_scalar_drift(history["kinetic_energy_j"]),
        }
    coarse_legacy, fine_legacy = legacy_metrics(coarse), legacy_metrics(fine)
    legacy_limits = {
        "linear_momentum_relative_drift": 2.0e-8,
        "angular_momentum_relative_drift": 2.0e-8,
        "kinetic_energy_relative_drift": 2.0e-8,
    }
    legacy_accepts = all(
        metrics[name] <= limit
        for metrics in (coarse_legacy, fine_legacy)
        for name, limit in legacy_limits.items()
    )
    self_converges = all(convergence[name] <= limit for name, limit in convergence_limits.items())
    return {
        "actual_integration_performed": True,
        "integrator": "FIXED_STEP_RK4",
        "duration_s": 0.04,
        "coarse": {"step_s": 1.0e-3, "steps": 40, "legacy_P_H_E": coarse_legacy},
        "fine": {"step_s": 5.0e-4, "steps": 80, "legacy_P_H_E": fine_legacy},
        "legacy_limits": legacy_limits,
        "componentwise_step_convergence": convergence,
        "componentwise_step_convergence_limits": convergence_limits,
        "wrong_ode_self_converges": self_converges,
        "legacy_P_H_E_guards_accept_both_steps": legacy_accepts,
        "maximum_zero_power_error_w": float(max(np.max(np.abs(coarse["power_injection_w"])), np.max(np.abs(fine["power_injection_w"])))),
        "maximum_base_linear_effort_defect_n": float(max(np.max(coarse["base_linear_effort_n"]), np.max(fine["base_linear_effort_n"]))),
        "maximum_base_angular_effort_defect_n_m": float(max(np.max(coarse["base_angular_effort_n_m"]), np.max(fine["base_angular_effort_n_m"]))),
        "R_effort_peak_n_m": float(max(np.max(np.abs(coarse["effort_R_n_m"])), np.max(np.abs(fine["effort_R_n_m"])))),
        "P_effort_peak_n": float(max(np.max(np.abs(coarse["effort_P_n"])), np.max(np.abs(fine["effort_P_n"])))),
    }


def _target_ledger(state: TargetState) -> dict[str, Any]:
    rotation = _quat_rotation(state.quaternion_body_to_inertial_wxyz)
    inertia = rotation @ TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    velocity, omega = state.twist_inertial_mixed[:3], state.twist_inertial_mixed[3:]
    linear = TARGET_MASS_KG * velocity
    spin = inertia @ omega
    return {
        "P_n_s": linear,
        "H_about_inertial_origin_n_m_s": np.cross(state.position_inertial_m, linear) + spin,
        "E_j": 0.5 * TARGET_MASS_KG * float(velocity @ velocity) + 0.5 * float(omega @ spin),
    }


def _endpoint_drift(initial: dict[str, Any], final: dict[str, Any]) -> dict[str, float]:
    return {
        "linear_momentum_absolute_drift_n_s": float(np.linalg.norm(final["P_n_s"] - initial["P_n_s"])),
        "angular_momentum_about_inertial_origin_absolute_drift_n_m_s": float(
            np.linalg.norm(final["H_about_inertial_origin_n_m_s"] - initial["H_about_inertial_origin_n_m_s"])
        ),
        "kinetic_energy_absolute_drift_j": abs(float(final["E_j"] - initial["E_j"])),
    }


def _endpoint_states(history) -> tuple[ServiceState, ServiceState, TargetState, TargetState]:
    service_initial = ServiceState(
        history.service_base_position_inertial_m[0],
        history.service_base_quaternion_body_to_inertial_wxyz[0],
        history.service_joint_coordinates_mixed[0],
        history.service_nu_s_mixed[0],
    )
    service_final = ServiceState(
        history.service_base_position_inertial_m[-1],
        history.service_base_quaternion_body_to_inertial_wxyz[-1],
        history.service_joint_coordinates_mixed[-1],
        history.service_nu_s_mixed[-1],
    )
    target_initial = TargetState(
        history.target_position_inertial_m[0],
        history.target_quaternion_body_to_inertial_wxyz[0],
        history.target_twist_inertial_mixed[0],
    )
    target_final = TargetState(
        history.target_position_inertial_m[-1],
        history.target_quaternion_body_to_inertial_wxyz[-1],
        history.target_twist_inertial_mixed[-1],
    )
    return service_initial, service_final, target_initial, target_final


def _integrator_difference(reference, crosscheck) -> dict[str, float]:
    return {
        "service_position_m": float(np.linalg.norm(reference.service_base_position_inertial_m[-1] - crosscheck.service_base_position_inertial_m[-1])),
        "service_quaternion_geodesic_rad": quaternion_geodesic(reference.service_base_quaternion_body_to_inertial_wxyz[-1], crosscheck.service_base_quaternion_body_to_inertial_wxyz[-1]),
        "service_q_R_rad": float(np.max(np.abs(reference.service_joint_coordinates_mixed[-1, :6] - crosscheck.service_joint_coordinates_mixed[-1, :6]))),
        "service_q_P_m": float(np.max(np.abs(reference.service_joint_coordinates_mixed[-1, 6:] - crosscheck.service_joint_coordinates_mixed[-1, 6:]))),
        "service_v_m_s": float(np.max(np.abs(reference.service_nu_s_mixed[-1, :3] - crosscheck.service_nu_s_mixed[-1, :3]))),
        "service_omega_rad_s": float(np.max(np.abs(reference.service_nu_s_mixed[-1, 3:6] - crosscheck.service_nu_s_mixed[-1, 3:6]))),
        "service_qdot_R_rad_s": float(np.max(np.abs(reference.service_nu_s_mixed[-1, 6:12] - crosscheck.service_nu_s_mixed[-1, 6:12]))),
        "service_qdot_P_m_s": float(np.max(np.abs(reference.service_nu_s_mixed[-1, 12:] - crosscheck.service_nu_s_mixed[-1, 12:]))),
        "target_position_m": float(np.linalg.norm(reference.target_position_inertial_m[-1] - crosscheck.target_position_inertial_m[-1])),
        "target_quaternion_geodesic_rad": quaternion_geodesic(reference.target_quaternion_body_to_inertial_wxyz[-1], crosscheck.target_quaternion_body_to_inertial_wxyz[-1]),
        "target_velocity_m_s": float(np.max(np.abs(reference.target_twist_inertial_mixed[-1, :3] - crosscheck.target_twist_inertial_mixed[-1, :3]))),
        "target_omega_rad_s": float(np.max(np.abs(reference.target_twist_inertial_mixed[-1, 3:] - crosscheck.target_twist_inertial_mixed[-1, 3:]))),
    }


def _check(checks: list[dict[str, Any]], identifier: str, name: str, passed: bool, evidence: Any) -> None:
    checks.append({"id": identifier, "name": name, "pass": bool(passed), "evidence": evidence})


def _final_gate(
    pre_audit: dict[str, Any],
    validation: dict[str, Any],
    audit_summary: dict[str, int],
    source_reference: dict[str, Any],
    evidence_reference: dict[str, Any],
    pre_audit_reference: dict[str, Any],
    audit_reference: dict[str, Any],
) -> dict[str, Any]:
    passed = (
        pre_audit.get("overall_status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT"
        and validation.get("summary", {}).get("fail") == 0
        and audit_summary["fail"] == 0
    )
    return {
        "schema": "SIM13_V4A_PHASE_A_AUDITED_GATE_V3",
        "overall_status": "PASS_PHASE_A_SYNTHETIC_FULL_FLOATING_KERNEL_WITH_CONTACT_AND_CURRENT_SYSTEM_HOLD" if passed else "FAIL_PHASE_A_INDEPENDENT_AUDIT",
        "final_gate": True,
        "hash_chain": {
            "upstream_source_manifest": source_reference,
            "upstream_evidence_manifest": evidence_reference,
            "upstream_pre_audit_gate": pre_audit_reference,
            "upstream_independent_audit_receipt": audit_reference,
        },
        "validator_checks": validation.get("summary"),
        "independent_audit_checks": audit_summary,
        "gates": [
            {"id": "V4A-FG01", "name": "synthetic full-floating no-contact Phase-A audited kernel", "status": "PASS_AUDITED" if passed else "FAIL", "pass": passed},
            {"id": "V4A-FG02", "name": "continuous contact backend and capture", "status": "HOLD_PHASE_B_NOT_IMPLEMENTED", "pass": False},
            {"id": "V4A-FG03", "name": "current Unified-R2 system binding", "status": "HOLD_NO_AUTHORIZED_CURRENT_SYSTEM_INSTANCE", "pass": False},
            {"id": "V4A-FG04", "name": "formal Sim13 NC19 closure", "status": "HOLD_FORMAL_V2_REMAINS_15_OF_20", "pass": False},
            {"id": "V4A-FG05", "name": "Owner production release and next stage", "status": "HOLD_NOT_AUTHORIZED", "pass": False},
        ],
        "authorizations": {
            "synthetic_phase_a_audited_ready": passed,
            "contact_ready": False,
            "capture_ready": False,
            "current_system_bound": False,
            "formal_nc19_closed": False,
            "owner_authorized": False,
            "production_ready": False,
            "released": False,
            "next_stage_authorized": False,
        },
        "formal_sim13_v2_state": {
            "passed": 15,
            "declared": 20,
            "dependency_hold": 5,
            "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
            "changed_by_this_package": False,
        },
    }


def main() -> int:
    required = (SOURCE_MANIFEST, LEDGER, VALIDATION, EVIDENCE_MANIFEST, PRE_AUDIT_GATE)
    if not all(path.is_file() for path in required):
        print("Run validate_phase_a.py before the independent audit.")
        return 2
    source = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_MANIFEST.read_text(encoding="utf-8"))
    pre_audit = json.loads(PRE_AUDIT_GATE.read_text(encoding="utf-8"))

    source_integrity = _strict_source_manifest(source)
    evidence_graph = _strict_evidence_graph(source, ledger, validation, evidence, pre_audit)
    acyclic = _strict_acyclic_boundary(source, evidence)
    upstream_before = {
        _relative(path): _sha(path)
        for path in (SOURCE_MANIFEST, LEDGER, VALIDATION, EVIDENCE_MANIFEST, PRE_AUDIT_GATE)
    }

    model, service, target = deterministic_scenario()
    analytic_mass = model.mass_matrix(service)
    independent_mass = _independent_mass_matrix(model, service)
    mass_abs = float(np.max(np.abs(analytic_mass - independent_mass)))
    mass_rel = float(np.linalg.norm(analytic_mass - independent_mass) / np.linalg.norm(analytic_mass))
    mass_minimum = float(np.min(np.linalg.eigvalsh(independent_mass)))

    reference = propagate_no_contact(model, service, target, step_s=0.002, steps=40, method="rk4")
    midpoint = propagate_no_contact(model, service, target, step_s=0.001, steps=80, method="midpoint")
    service_initial, service_final, target_initial, target_final = _endpoint_states(reference)
    service_initial_ledger = _independent_service_ledger(model, service_initial)
    service_final_ledger = _independent_service_ledger(model, service_final)
    target_initial_ledger, target_final_ledger = _target_ledger(target_initial), _target_ledger(target_final)
    combined_initial = {
        "P_n_s": service_initial_ledger["P_n_s"] + target_initial_ledger["P_n_s"],
        "H_about_inertial_origin_n_m_s": service_initial_ledger["H_about_inertial_origin_n_m_s"] + target_initial_ledger["H_about_inertial_origin_n_m_s"],
        "E_j": service_initial_ledger["E_j"] + target_initial_ledger["E_j"],
    }
    combined_final = {
        "P_n_s": service_final_ledger["P_n_s"] + target_final_ledger["P_n_s"],
        "H_about_inertial_origin_n_m_s": service_final_ledger["H_about_inertial_origin_n_m_s"] + target_final_ledger["H_about_inertial_origin_n_m_s"],
        "E_j": service_final_ledger["E_j"] + target_final_ledger["E_j"],
    }
    drift = {
        "service": _endpoint_drift(service_initial_ledger, service_final_ledger),
        "target": _endpoint_drift(target_initial_ledger, target_final_ledger),
        "combined": _endpoint_drift(combined_initial, combined_final),
        "linear_and_angular_momentum_combined": False,
        "reference_origin": "COMMON_INERTIAL_ORIGIN",
    }
    integrator = _integrator_difference(reference, midpoint)
    integrator_limits = {name: 2.0e-7 for name in integrator}
    integrator_limits["target_velocity_m_s"] = 2.0e-10

    acceleration_map = _primary_acceleration_map(ledger)
    el_cases = []
    nominal_mass = None
    nominal_residual = None
    for case in deterministic_el_audit_states():
        case_evidence = _independent_el_audit(
            model, case.service_state, acceleration_map[case.case_id]
        )
        case_mass = case_evidence.pop("mass_matrix_mixed")
        case_evidence["case_id"] = case.case_id
        case_evidence["state_contract"] = {
            "joint_coordinates_R_rad": case.service_state.joint_coordinates_mixed[:6].tolist(),
            "joint_coordinates_P_m": case.service_state.joint_coordinates_mixed[6:].tolist(),
            "joint_velocity_R_rad_s": case.service_state.nu_s_mixed[6:12].tolist(),
            "joint_velocity_P_m_s": case.service_state.nu_s_mixed[12:].tolist(),
        }
        el_cases.append(case_evidence)
        if case.case_id == "EL00_NOMINAL":
            nominal_mass = case_mass
            nominal_residual = np.asarray(
                case_evidence["nominal_residual_at_1e_6"], dtype=float
            )
    worst_r_case = max(
        el_cases, key=lambda item: item["platform_envelope"]["R_max_abs_n_m"]
    )
    worst_p_case = max(
        el_cases, key=lambda item: item["platform_envelope"]["P_max_abs_n"]
    )
    el_campaign = {
        "registry": "SIX_EXPLICIT_NONZERO_VELOCITY_STATES_NO_RNG_V1",
        "case_count": len(el_cases),
        "epsilon_count_per_case": len(EL_EPSILONS),
        "total_state_epsilon_evaluations": len(el_cases) * len(EL_EPSILONS),
        "all_states_all_epsilons_pass": all(
            item["platform_envelope"]["all_three_epsilons_pass"] is True
            for item in el_cases
        ),
        "worst_R": {
            "case_id": worst_r_case["case_id"],
            "max_abs_n_m": worst_r_case["platform_envelope"]["R_max_abs_n_m"],
        },
        "worst_P": {
            "case_id": worst_p_case["case_id"],
            "max_abs_n": worst_p_case["platform_envelope"]["P_max_abs_n"],
        },
        "cases": el_cases,
    }
    if nominal_mass is None or nominal_residual is None:
        raise RuntimeError("nominal EL state missing from frozen registry")
    mutation = _nullspace_mutation(service, nominal_mass, nominal_residual)
    mutation["actual_wrong_ode_integration"] = _wrong_ode_integration_evidence(
        model, service
    )
    stress = ledger.get("point_kinematics", {}).get("fixed_multiconfiguration_stress", {})
    registry = deterministic_stress_points()
    stress_pass = (
        stress.get("registry") == "FIXED_EXPLICIT_ARRAYS_NO_RNG_V1"
        and stress.get("case_count") == 10
        and stress.get("covered_link_indices") == list(range(8))
        and [item.get("case_id") for item in stress.get("cases", [])] == [case.case_id for case in registry]
        and stress.get("maximum_point_jacobian_error_mixed_units", 1.0) < 3.0e-8
    )
    authorizations = pre_audit.get("authorizations", {})
    false_names = (
        "synthetic_phase_a_audited_ready", "contact_ready", "capture_ready",
        "current_system_bound", "formal_nc19_closed", "owner_authorized",
        "production_ready", "released", "next_stage_authorized",
    )
    pre_audit_pass = (
        pre_audit.get("overall_status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT"
        and pre_audit.get("final_gate") is False
        and all(authorizations.get(name) is False for name in false_names)
        and pre_audit.get("formal_sim13_v2_state", {}).get("passed") == 15
        and pre_audit.get("formal_sim13_v2_state", {}).get("declared") == 20
    )

    checks: list[dict[str, Any]] = []
    _check(checks, "IA01", "source manifest strict path bytes SHA role verification", source_integrity["pass"], source_integrity)
    _check(checks, "IA02", "validator evidence and pre-audit edges verify independently", evidence_graph["pass"], evidence_graph)
    _check(checks, "IA03", "five-point body kinematics independently reconstruct the full mass matrix", mass_abs < 2.0e-9 and mass_rel < 2.0e-10 and mass_minimum > 1.0e-5, {
        "maximum_absolute_entry_error_mixed_units": mass_abs,
        "relative_frobenius_error_under_declared_SI_channel_scaling": mass_rel,
        "independent_minimum_eigenvalue_under_declared_SI_channel_scaling": mass_minimum,
        "method": "FIVE_POINT_FINITE_DIFFERENCE_BODY_POSITION_AND_ROTATION",
    })
    _check(checks, "IA04", "independent endpoint service P H E ledger closes", all(value < 2.0e-8 for value in drift["service"].values()), drift["service"])
    _check(checks, "IA05", "independent target and combined P H E ledgers close separately", all(value < 2.0e-8 for section in ("target", "combined") for value in drift[section].values()) and drift["linear_and_angular_momentum_combined"] is False, {
        "target": drift["target"], "combined": drift["combined"],
        "linear_and_angular_momentum_combined": False,
        "reference_origin": "COMMON_INERTIAL_ORIGIN",
    })
    _check(checks, "IA06", "RK4 and explicit midpoint agree componentwise", all(integrator[name] <= limit for name, limit in integrator_limits.items()), {
        "observed": integrator, "limits": integrator_limits, "heterogeneous_sum_used": False,
    })
    _check(checks, "IA07", "pre-audit Gate cannot claim final audit or broaden authority", pre_audit_pass, {
        "overall_status": pre_audit.get("overall_status"), "final_gate": pre_audit.get("final_gate"),
        "authorizations": authorizations, "formal_sim13_v2_state": pre_audit.get("formal_sim13_v2_state"),
    })
    _check(checks, "IA08", "ten explicit no-RNG stress points cover all eight link Jacobians", stress_pass, stress)
    _check(checks, "IA09", "six-state independent joint Euler-Lagrange campaign closes R and P separately at three epsilons", el_campaign["case_count"] >= 6 and el_campaign["total_state_epsilon_evaluations"] >= 18 and el_campaign["all_states_all_epsilons_pass"] is True, el_campaign)
    _check(checks, "IA10", "actual two-step wrong ODE self-converges and bypasses legacy P H E while EL rejects", mutation["legacy_invariant_blind_spot"]["legacy_instantaneous_P_H_E_guards_would_accept"] is True and mutation["actual_wrong_ode_integration"]["actual_integration_performed"] is True and mutation["actual_wrong_ode_integration"]["wrong_ode_self_converges"] is True and mutation["actual_wrong_ode_integration"]["legacy_P_H_E_guards_accept_both_steps"] is True and mutation["new_el_guard"]["detected"] is True, mutation)
    _check(checks, "IA11", "all manifest edges enforce exact path bytes SHA role with no duplicate or unknown role", source_integrity["pass"] and evidence_graph["pass"], {"source": source_integrity, "evidence_graph": evidence_graph})
    _check(checks, "IA12", "DAG is self-excluded root-contained and downstream-free before final issuance", acyclic["pass"], acyclic)
    summary = {"pass": sum(item["pass"] for item in checks), "fail": sum(not item["pass"] for item in checks), "total": len(checks)}

    receipt = {
        "schema": "SIM13_V4A_PHASE_A_INDEPENDENT_AUDIT_RECEIPT_V3",
        "status": "PASS_INDEPENDENT_AUDIT" if summary["fail"] == 0 else "FAIL_INDEPENDENT_AUDIT",
        "method_independence": {
            "validator_module_imported": False,
            "validator_conclusion_function_called": False,
            "primary_bias_effort_called_by_euler_lagrange_path": False,
            "primary_public_propagator_used_for_legacy_P_H_E_and_integrator_checks": True,
            "primary_acceleration_consumed_from_hash_bound_ledger": True,
            "mass_matrix_method": "FIVE_POINT_FINITE_DIFFERENCE_BODY_KINEMATICS",
            "joint_equation_method": "INDEPENDENT_EULER_LAGRANGE_RESIDUAL",
        },
        "upstream_pre_audit_gate": _record(PRE_AUDIT_GATE, "AUDITED_PRE_AUDIT_GATE"),
        "upstream_hashes_before_downstream_issuance": upstream_before,
        "checks": checks,
        "summary": summary,
    }
    _write_json(AUDIT_RECEIPT, receipt)
    final = _final_gate(
        pre_audit, validation, summary,
        _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
        _record(PRE_AUDIT_GATE, "UPSTREAM_PRE_AUDIT_GATE"),
        _record(AUDIT_RECEIPT, "UPSTREAM_INDEPENDENT_AUDIT_RECEIPT"),
    )
    _write_json(FINAL_GATE, final)
    upstream_after = {
        _relative(path): _sha(path)
        for path in (SOURCE_MANIFEST, LEDGER, VALIDATION, EVIDENCE_MANIFEST, PRE_AUDIT_GATE)
    }
    terminal = {
        "schema": "SIM13_V4A_PHASE_A_TERMINAL_SELF_EXCLUDED_MANIFEST_V3",
        "self_excluded_path": _relative(TERMINAL_MANIFEST),
        "records": [
            _record(SOURCE_MANIFEST, "SOURCE_MANIFEST"),
            _record(EVIDENCE_MANIFEST, "EVIDENCE_MANIFEST"),
            _record(PRE_AUDIT_GATE, "PRE_AUDIT_GATE"),
            _record(AUDIT_RECEIPT, "INDEPENDENT_AUDIT_RECEIPT"),
            _record(FINAL_GATE, "FINAL_AUDITED_GATE"),
        ],
        "upstream_hashes_before_downstream_issuance": upstream_before,
        "upstream_hashes_after_final_gate_issuance": upstream_after,
        "upstream_unchanged_after_downstream_issuance": upstream_before == upstream_after,
        "acyclic_rule": "TERMINAL_EXCLUDES_ITSELF; FINAL_REFERENCES_AUDIT; AUDIT_REFERENCES_ONLY_PRE_AUDIT_AND_UPSTREAM",
    }
    _write_json(TERMINAL_MANIFEST, terminal)
    print(json.dumps({
        "audit": receipt["status"], "checks": summary,
        "el_worst_R_case_id": el_campaign["worst_R"]["case_id"],
        "el_R_envelope_n_m": el_campaign["worst_R"]["max_abs_n_m"],
        "el_worst_P_case_id": el_campaign["worst_P"]["case_id"],
        "el_P_envelope_n": el_campaign["worst_P"]["max_abs_n"],
        "nullspace_mutation_R_n_m": mutation["injected_internal_generalized_effort"]["R_max_abs_n_m"],
        "nullspace_mutation_P_n": mutation["injected_internal_generalized_effort"]["P_max_abs_n"],
        "wrong_ode_self_converges": mutation["actual_wrong_ode_integration"]["wrong_ode_self_converges"],
        "wrong_ode_legacy_P_H_E_accepts": mutation["actual_wrong_ode_integration"]["legacy_P_H_E_guards_accept_both_steps"],
        "final_gate": final["overall_status"], "final_gate_sha256": _sha(FINAL_GATE),
        "upstream_unchanged": upstream_before == upstream_after,
    }, indent=2, ensure_ascii=False))
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
