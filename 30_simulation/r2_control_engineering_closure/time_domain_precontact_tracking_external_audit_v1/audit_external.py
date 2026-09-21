"""Package-external audit for the current-R2 time-domain tracking diagnostic.

The candidate core is deliberately never imported.  Numeric histories are read
as evidence, while task errors, solver deltas, momentum, energy, constraints,
and authority boundaries are independently recomputed here against a frozen
source lock.  Only pinned upstream plant/control machinery is loaded to expose
the current rigid-body tree and mass/constraint operators.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE.parents[2]
CANDIDATE = PROJECT_ROOT / "30_simulation/r2_control_engineering_closure/time_domain_precontact_tracking_candidate_v1"
REBIND = PROJECT_ROOT / "30_simulation/r2_control_engineering_closure/time_domain_precontact_tracking_metric_parent_rebind_v1"
LOCK_PATH = PACKAGE / "SOURCE_LOCK_V1.json"
RESULT_PATH = PACKAGE / "results" / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_EXTERNAL_AUDIT_GATE_V1.json"
EXPECTED_LOCK_CANONICAL_SHA256 = "F74BA7A6794DD6994FD152EFC9DCD218612A128341A28574F0579DE60C7ECBA0"
PASS_VERDICT = "EXTERNAL_AUDIT_PASS_FOR_TIME_DOMAIN_DIAGNOSTIC_ONLY__NO_CONTROL_RELEASE"
HOLD_VERDICT = "EXTERNAL_AUDIT_HOLD__NO_CONTROL_RELEASE"
HOLD_CLAIM = "EXTERNAL_AUDIT_ATTEMPTED_REPEAT_REQUIRED__NO_CONTROL_RELEASE"
EXPECTED_CANDIDATE_FAILURE = "G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT"
EXPECTED_SCENARIOS = (
    ("C0_UNCONTROLLED_5D_REFERENCE", "PAIR_5D", "FAR_APPROACH_5D", False, 5),
    ("C1_CONTROLLED_5D", "PAIR_5D", "FAR_APPROACH_5D", True, 5),
    ("C0_UNCONTROLLED_6D_REFERENCE", "PAIR_6D", "FINAL_ALIGNMENT_6D", False, 6),
    ("C2_CONTROLLED_6D", "PAIR_6D", "FINAL_ALIGNMENT_6D", True, 6),
)
EXPECTED_ADMISSION_SAMPLES_GIB = [6.17, 6.26, 6.26]
EXPECTED_RUNTIME_SAMPLES_GIB = [6.264, 6.267, 6.267]
AUDIT_ALLOWED_FILES = {
    "SOURCE_LOCK_V1.json",
    "audit_external.py",
    "README.md",
    "tests/test_time_domain_external_audit.py",
    "results/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_EXTERNAL_AUDIT_GATE_V1.json",
}
FALSE_AUTHORITY_KEYS = (
    "parent_gate_reissued",
    "parent_gate_credit",
    "precontact_tracking_validated",
    "pose_or_attitude_tracking_validated",
    "control_valid",
    "hardware_valid",
    "collision_valid",
    "contact_valid",
    "flex_valid",
    "target_attached",
    "m01_path_bound",
    "safe_gate_credit",
    "sim13_credit",
    "non_abort_authorized",
    "next_stage_authorized",
    "release_credit",
)


class AuditError(RuntimeError):
    """Fail-closed external-audit violation."""


def _unique_pairs(rows: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _reject_constant(token: str) -> None:
    raise ValueError(f"NONFINITE_JSON:{token}")


def strict_load(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )


def builtin(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [builtin(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return builtin(value.item())
    if isinstance(value, Mapping):
        return {str(key): builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [builtin(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise AuditError("NONFINITE_OUTPUT")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        builtin(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def pin_matches(pin: Mapping[str, Any]) -> bool:
    path = PROJECT_ROOT / str(pin["path"])
    return path.is_file() and path.stat().st_size == int(pin["bytes"]) and digest(path) == pin["sha256"]


def pin_audit(pins: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    records = [
        {
            "id": pin.get("id"),
            "path": pin["path"],
            "bytes": int(pin["bytes"]),
            "sha256": pin["sha256"],
            "match": pin_matches(pin),
        }
        for pin in pins
    ]
    return {
        "count": len(records),
        "matched": sum(row["match"] for row in records),
        "all_match": all(row["match"] for row in records),
        "records": records,
    }


def observed_files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def forbidden_cache(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ("__pycache__" in path.parts or path.suffix == ".pyc")
    )


def inventory_exact(observed: set[str], expected: Sequence[str]) -> bool:
    return observed == set(expected)


def _pin_by_id(pins: Sequence[Mapping[str, Any]], identifier: str) -> Mapping[str, Any]:
    matches = [pin for pin in pins if pin.get("id") == identifier]
    if len(matches) != 1:
        raise AuditError(f"PIN_ID_NOT_UNIQUE:{identifier}")
    return matches[0]


def _candidate_documents(lock: Mapping[str, Any]) -> dict[str, Any]:
    pins = lock["candidate_pins"]
    return {
        name: strict_load(PROJECT_ROOT / _pin_by_id(pins, identifier)["path"])
        for name, identifier in {
            "contract": "candidate_contract",
            "evidence": "candidate_evidence",
            "gate": "candidate_gate",
            "manifest": "candidate_manifest",
            "negative": "candidate_negative_controls",
        }.items()
    }


def _rebind_documents(lock: Mapping[str, Any]) -> dict[str, Any]:
    pins = lock["rebind_pins"]
    return {
        name: strict_load(PROJECT_ROOT / _pin_by_id(pins, identifier)["path"])
        for name, identifier in {
            "contract": "rebind_contract",
            "evidence": "rebind_evidence",
            "gate": "rebind_gate",
            "manifest": "rebind_manifest",
            "negative": "rebind_negative_controls",
        }.items()
    }


def _import_upstream(name: str, pin: Mapping[str, Any]) -> Any:
    path = (PROJECT_ROOT / pin["path"]).resolve()
    try:
        path.relative_to(CANDIDATE.resolve())
    except ValueError:
        pass
    else:
        raise AuditError("CANDIDATE_CORE_IMPORT_FORBIDDEN")
    try:
        path.relative_to(REBIND.resolve())
    except ValueError:
        pass
    else:
        raise AuditError("REBIND_CORE_IMPORT_FORBIDDEN")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AuditError(f"UPSTREAM_IMPORT_FAILED:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_physics_context(lock: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    direct = lock["candidate_direct_source_pins"]
    plant = _import_upstream("_td_external_upstream_plant", _pin_by_id(direct, "time_varying_plant_source"))
    control = _import_upstream("_td_external_upstream_control", _pin_by_id(direct, "control_kinematics_source"))
    plant_contract = strict_load(PROJECT_ROOT / _pin_by_id(direct, "time_varying_plant_contract")["path"])
    parent = plant._load_parent_module(PROJECT_ROOT)
    backend = parent.load_backend(PROJECT_ROOT)
    model = parent.ReducedR2Model(
        backend=backend,
        qP_star_m=np.asarray(contract["plant"]["qP_star_m"], dtype=float),
    )
    return {
        "plant": plant,
        "control": control,
        "plant_contract": plant_contract,
        "parent": parent,
        "backend": backend,
        "model": model,
        "loaded_paths": [str(Path(plant.__file__).resolve()), str(Path(control.__file__).resolve())],
    }


def close(left: Any, right: Any, *, atol: float = 2.0e-11, rtol: float = 2.0e-11) -> bool:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    return a.shape == b.shape and bool(np.allclose(a, b, atol=atol, rtol=rtol))


def quaternion_rotation(quaternion: Sequence[float]) -> np.ndarray:
    q = np.asarray(quaternion, dtype=float)
    q = q / np.linalg.norm(q)
    w, x, y, z = q
    return np.array(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y)],
            [2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x)],
            [2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y)],
        ]
    )


def attitude_distance(left: Sequence[float], right: Sequence[float]) -> float:
    a = np.asarray(left, dtype=float); a /= np.linalg.norm(a)
    b = np.asarray(right, dtype=float); b /= np.linalg.norm(b)
    if float(a @ b) < 0.0:
        b = -b
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    relative_scalar = aw * bw + ax * bx + ay * by + az * bz
    relative_vector = np.array(
        [
            aw * bx - ax * bw - ay * bz + az * by,
            aw * by + ax * bz - ay * bw - az * bx,
            aw * bz - ax * by + ay * bx - az * bw,
        ]
    )
    return float(2.0 * math.atan2(float(np.linalg.norm(relative_vector)), abs(float(relative_scalar))))


def skew(vector: Sequence[float]) -> np.ndarray:
    x, y, z = np.asarray(vector, dtype=float)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def approach_basis(axis: Sequence[float]) -> tuple[np.ndarray, int]:
    unit = np.asarray(axis, dtype=float)
    unit /= np.linalg.norm(unit)
    seed_index = int(np.argmin(np.abs(unit)))
    seed = np.eye(3)[seed_index]
    first = np.cross(unit, seed); first /= np.linalg.norm(first)
    second = np.cross(unit, first)
    return np.vstack((first, second)), seed_index


def controller_evaluate(
    context: Mapping[str, Any],
    contract: Mapping[str, Any],
    scenario: Mapping[str, Any],
    q8: Sequence[float],
    dq8: Sequence[float],
) -> dict[str, Any]:
    q = np.asarray(q8, dtype=float); dq = np.asarray(dq8, dtype=float)
    transform, _fixed, generalized8, _connection = context["control"]._tool_jacobians(
        context["backend"], q, contract["task_semantics"]["tool_link"]
    )
    axis = np.asarray(transform[:3, 2], dtype=float)
    basis, seed_index = approach_basis(axis)
    generalized6 = np.asarray(generalized8[:, :6], dtype=float)
    if scenario["task"] == "FAR_APPROACH_5D":
        task_jacobian = np.vstack((generalized6[:3], basis @ (-skew(axis)) @ generalized6[3:]))
        dimension = 5
    else:
        task_jacobian = generalized6
        dimension = 6
    length = float(contract["controller"]["characteristic_length_m"])
    weight = np.diag(np.r_[np.full(3, 1.0 / length), np.ones(dimension - 3)])
    weighted_jacobian = weight @ task_jacobian
    weighted_desired = weight @ np.asarray(scenario["desired_twist_native"], dtype=float)
    singular = np.linalg.svd(weighted_jacobian, compute_uv=False)
    rank = int(np.sum(singular > float(contract["controller"]["rank_rtol"]) * singular[0]))
    mass8 = np.asarray(context["model"].mass(q), dtype=float)
    bias8 = np.asarray(context["model"].bias(q, dq), dtype=float)
    mass6 = mass8[:6, :6]
    scale = np.asarray(contract["controller"]["q_rate_scale_diagonal_rad_inverse"], dtype=float)
    scale_inv = np.diag(1.0 / scale)
    mass_bar = scale_inv.T @ mass6 @ scale_inv / float(contract["controller"]["reference_inertia_kg_m2"])
    jacobian_bar = weighted_jacobian @ scale_inv
    mass_bar_inv = np.linalg.inv(mass_bar)
    damping = float(contract["controller"]["dls_lambda_dimensionless"])
    normal = jacobian_bar @ mass_bar_inv @ jacobian_bar.T + damping * damping * np.eye(dimension)
    q_rate_bar = mass_bar_inv @ jacobian_bar.T @ np.linalg.solve(normal, weighted_desired)
    qdot_cmd = scale_inv @ q_rate_bar
    qdd_cmd = float(contract["controller"]["Kv_per_s"]) * (qdot_cmd - dq[:6])
    tau6 = mass6 @ qdd_cmd + bias8[:6] if scenario["controller_enabled"] else np.zeros(6)
    error = weighted_jacobian @ dq[:6] - weighted_desired
    return {
        "error": error,
        "rank": rank,
        "sigma_min": float(singular[-1]),
        "seed_index": seed_index,
        "qdd_cmd": qdd_cmd,
        "tau8": np.r_[tau6, np.zeros(2)],
    }


def body_momentum_energy(
    context: Mapping[str, Any], state: Sequence[float], qP_star: np.ndarray
) -> dict[str, Any]:
    row = np.asarray(state, dtype=float)
    position = row[:3]
    quaternion = row[3:7]
    q = row[7:15].copy(); q[6:] = qP_star
    dq = row[15:23].copy(); dq[6:] = 0.0
    base_twist = np.asarray(context["backend"].mechanical_connection(q), dtype=float) @ dq
    generalized_velocity = np.r_[base_twist, dq]
    rotation = quaternion_rotation(quaternion)
    linear = np.zeros(3); angular = np.zeros(3)
    for body in context["backend"].tree.body_kinematics(q):
        velocity_root = body.linear_jacobian @ generalized_velocity
        omega_root = body.angular_jacobian @ generalized_velocity
        position_inertial = position + rotation @ body.com_root_m
        velocity_inertial = rotation @ velocity_root
        omega_inertial = rotation @ omega_root
        inertia_inertial = rotation @ body.inertia_root_kg_m2 @ rotation.T
        body_linear = body.mass_kg * velocity_inertial
        linear += body_linear
        angular += inertia_inertial @ omega_inertial + np.cross(position_inertial, body_linear)
    matrix = np.asarray(context["backend"].tree.mass_matrix(q), dtype=float)
    root_momentum = matrix @ generalized_velocity
    matrix_linear = rotation @ root_momentum[:3]
    matrix_angular = rotation @ root_momentum[3:6] + np.cross(position, matrix_linear)
    energy = float(0.5 * generalized_velocity @ matrix @ generalized_velocity)
    return {
        "q": q,
        "dq": dq,
        "base_twist": base_twist,
        "linear": linear,
        "angular_about_fixed_O": angular,
        "matrix_linear": matrix_linear,
        "matrix_angular_about_fixed_O": matrix_angular,
        "energy_J": energy,
    }


def recompute_solver(
    context: Mapping[str, Any],
    contract: Mapping[str, Any],
    scenario_contract: Mapping[str, Any],
    state_history: np.ndarray,
    work_history: np.ndarray,
    stored: Mapping[str, Any],
) -> dict[str, Any]:
    thresholds = contract["thresholds"]
    qP_star = np.asarray(contract["plant"]["qP_star_m"], dtype=float)
    lower = np.asarray(context["plant_contract"]["model_contract"]["joint_lower_mixed_rad_m"], dtype=float)
    upper = np.asarray(context["plant_contract"]["model_contract"]["joint_upper_mixed_rad_m"], dtype=float)
    errors: list[np.ndarray] = []
    ranks: list[int] = []
    sigmas: list[float] = []
    seeds: list[int] = []
    p_norm: list[float] = []
    h_norm: list[float] = []
    p_cross: list[float] = []
    h_cross: list[float] = []
    energy: list[float] = []
    quat_error: list[float] = []
    qR_margin: list[float] = []
    qP_margin: list[float] = []
    base_twists: list[np.ndarray] = []
    eq_R: list[float] = []
    eq_P: list[float] = []
    constraint: list[float] = []
    reaction_power: list[float] = []
    reaction_cross: list[float] = []
    accel_cross: list[float] = []
    computed_closure: list[float] = []
    for state in state_history:
        physical = body_momentum_energy(context, state, qP_star)
        q = physical["q"]; dq = physical["dq"]
        command = controller_evaluate(context, contract, scenario_contract, q, dq)
        result = context["model"].locked_acceleration(q[:6], dq[:6], command["tau8"][:6], command["tau8"][6:])
        equilibrium = np.abs(np.asarray(result["kkt_equilibrium_residual"], dtype=float))
        errors.append(command["error"]); ranks.append(command["rank"]); sigmas.append(command["sigma_min"]); seeds.append(command["seed_index"])
        p_norm.append(float(np.linalg.norm(physical["linear"])))
        h_norm.append(float(np.linalg.norm(physical["angular_about_fixed_O"])))
        p_cross.append(float(np.linalg.norm(physical["linear"] - physical["matrix_linear"])))
        h_cross.append(float(np.linalg.norm(physical["angular_about_fixed_O"] - physical["matrix_angular_about_fixed_O"])))
        energy.append(physical["energy_J"]); base_twists.append(physical["base_twist"])
        quat_error.append(abs(float(np.linalg.norm(np.asarray(state[3:7], dtype=float))) - 1.0))
        qR_margin.append(float(np.min(np.minimum(q[:6] - lower[:6], upper[:6] - q[:6]))))
        qP_margin.append(float(np.min(np.minimum(q[6:] - lower[6:], upper[6:] - q[6:]))))
        eq_R.append(float(np.max(equilibrium[:6]))); eq_P.append(float(np.max(equilibrium[6:])))
        constraint.append(float(np.max(np.abs(result["constraint_acceleration"]))))
        reaction_power.append(float(abs(np.asarray(result["kkt_reaction_N"], dtype=float) @ dq[6:])))
        reaction_cross.append(float(result["reaction_cross_max_abs_N"]))
        accel_cross.append(float(result["acceleration_cross_revolute_max_abs_rad_s2"]))
        if scenario_contract["controller_enabled"]:
            computed_closure.append(float(np.max(np.abs(np.asarray(result["kkt_acceleration"][:6]) - command["qdd_cmd"]))))
    error_array = np.asarray(errors)
    error_norm = np.linalg.norm(error_array, axis=1)
    energy_array = np.asarray(energy)
    delta_energy = energy_array - energy_array[0]
    residual = delta_energy - work_history
    work_relative = float(np.max(np.abs(residual)) / max(float(np.max(np.abs(delta_energy))), float(np.max(np.abs(work_history))), 1.0e-15))
    summary = {
        "weighted_error_history_per_s": error_array,
        "weighted_error_norm_initial_per_s": float(error_norm[0]),
        "weighted_error_norm_final_per_s": float(error_norm[-1]),
        "weighted_error_norm_rms_per_s": float(np.sqrt(np.mean(error_norm * error_norm))),
        "weighted_error_norm_peak_per_s": float(np.max(error_norm)),
        "step_rank_min": min(ranks),
        "step_sigma_min_dimensionless": min(sigmas),
        "basis_seed_switch_count": sum(a != b for a, b in zip(seeds[:-1], seeds[1:])),
        "max_linear_momentum_kg_m_s": max(p_norm),
        "max_angular_momentum_about_fixed_O_kg_m2_s": max(h_norm),
        "max_matrix_body_linear_kg_m_s": max(p_cross),
        "max_matrix_body_angular_kg_m2_s": max(h_cross),
        "max_work_energy_absolute_J": float(np.max(np.abs(residual))),
        "max_work_energy_relative": work_relative,
        "max_quaternion_norm_error": max(quat_error),
        "revolute_joint_limit_min_margin_rad": min(qR_margin),
        "prismatic_joint_limit_min_margin_m": min(qP_margin),
        "qP_position_lock_max_abs_m": float(np.max(np.abs(state_history[:, 13:15] - qP_star))),
        "dqP_lock_max_abs_m_s": float(np.max(np.abs(state_history[:, 21:23]))),
        "max_kkt_equilibrium_R_abs_Nm": max(eq_R),
        "max_kkt_equilibrium_P_abs_N": max(eq_P),
        "max_constraint_acceleration_abs_m_s2": max(constraint),
        "max_constraint_reaction_power_abs_W": max(reaction_power),
        "max_kkt_reaction_cross_abs_N": max(reaction_cross),
        "max_kkt_vs_elimination_acceleration_R_abs_rad_s2": max(accel_cross),
        "max_computed_acceleration_closure_abs_rad_s2": max(computed_closure) if computed_closure else 0.0,
        "base_twist_history": np.asarray(base_twists),
    }
    ledger = stored["physics_ledger"]
    summary["stored_field_match"] = all((
        close(error_array, stored["weighted_error_history_per_s"], atol=3.0e-12),
        close(summary["weighted_error_norm_final_per_s"], stored["weighted_error_norm_final_per_s"], atol=3.0e-12),
        close(summary["weighted_error_norm_rms_per_s"], stored["weighted_error_norm_rms_per_s"], atol=3.0e-12),
        summary["step_rank_min"] == stored["step_rank_min"],
        close(summary["step_sigma_min_dimensionless"], stored["step_sigma_min_dimensionless"], atol=3.0e-12),
        close(summary["max_linear_momentum_kg_m_s"], ledger["max_linear_momentum_body_inertial_kg_m_s"], atol=3.0e-12),
        close(summary["max_angular_momentum_about_fixed_O_kg_m2_s"], ledger["max_angular_momentum_body_inertial_kg_m2_s"], atol=3.0e-12),
        close(summary["max_work_energy_absolute_J"], ledger["max_work_energy_absolute_J"], atol=3.0e-12),
        close(summary["max_work_energy_relative"], ledger["max_work_energy_relative"], atol=3.0e-10),
        close(summary["max_quaternion_norm_error"], ledger["max_quaternion_norm_error"], atol=3.0e-13),
        close(summary["qP_position_lock_max_abs_m"], stored["qP_lock"]["qP_position_lock_max_abs_m"], atol=1.0e-15),
        close(summary["dqP_lock_max_abs_m_s"], stored["qP_lock"]["dqP_lock_max_abs_m_s"], atol=1.0e-15),
        close(summary["max_kkt_equilibrium_R_abs_Nm"], stored["max_kkt_equilibrium_R_abs_Nm"], atol=3.0e-11),
        close(summary["max_kkt_equilibrium_P_abs_N"], stored["max_kkt_equilibrium_P_abs_N"], atol=3.0e-11),
    ))
    summary["passes_thresholds"] = all((
        summary["step_sigma_min_dimensionless"] >= thresholds["step_sigma_min_dimensionless_min"],
        summary["basis_seed_switch_count"] <= thresholds["approach_basis_seed_switch_count_max"],
        summary["max_linear_momentum_kg_m_s"] <= thresholds["linear_momentum_residual_max_kg_m_s"],
        summary["max_angular_momentum_about_fixed_O_kg_m2_s"] <= thresholds["angular_momentum_about_fixed_inertial_origin_residual_max_kg_m2_s"],
        summary["max_work_energy_absolute_J"] <= thresholds["work_energy_absolute_max_J"],
        summary["max_work_energy_relative"] <= thresholds["work_energy_relative_max"],
        summary["max_quaternion_norm_error"] <= thresholds["quaternion_norm_error_max"],
        summary["revolute_joint_limit_min_margin_rad"] >= thresholds["joint_limit_min_margin_mixed_rad_m"],
        summary["prismatic_joint_limit_min_margin_m"] >= thresholds["joint_limit_min_margin_mixed_rad_m"],
        summary["qP_position_lock_max_abs_m"] <= thresholds["qP_position_lock_max_abs_m"],
        summary["dqP_lock_max_abs_m_s"] <= thresholds["dqP_lock_max_abs_m_s"],
        summary["max_constraint_acceleration_abs_m_s2"] <= thresholds["ddqP_lock_max_abs_m_s2"],
        summary["max_kkt_equilibrium_R_abs_Nm"] <= thresholds["kkt_equilibrium_R_max_abs_Nm"],
        summary["max_kkt_equilibrium_P_abs_N"] <= thresholds["kkt_equilibrium_P_max_abs_N"],
        summary["max_kkt_vs_elimination_acceleration_R_abs_rad_s2"] <= thresholds["kkt_vs_elimination_acceleration_R_max_abs_rad_s2"],
        summary["max_kkt_reaction_cross_abs_N"] <= thresholds["kkt_reaction_cross_max_abs_N"],
        summary["max_constraint_reaction_power_abs_W"] <= thresholds["constraint_reaction_power_max_abs_W"],
        summary["max_computed_acceleration_closure_abs_rad_s2"] <= thresholds["computed_acceleration_closure_max_abs_rad_s2"],
    ))
    return summary


def recompute_scenario(
    context: Mapping[str, Any], contract: Mapping[str, Any], scenario_contract: Mapping[str, Any], stored: Mapping[str, Any]
) -> dict[str, Any]:
    times = np.asarray(stored["time_s"], dtype=float)
    expected_samples = int(round(contract["plant"]["duration_s"] / contract["plant"]["fixed_step_s"])) + 1
    if times.shape != (expected_samples,):
        raise AuditError("TIME_GRID_SHAPE")
    solvers: dict[str, Any] = {}
    for name in ("rk4", "dop853"):
        states = np.asarray(stored[f"{name}_physical_state_history_23"], dtype=float).copy()
        work = np.asarray(stored[f"{name}_auxiliary_work_history_J"], dtype=float).copy()
        if states.shape != (expected_samples, 23) or work.shape != (expected_samples,) or not np.all(np.isfinite(states)) or not np.all(np.isfinite(work)):
            raise AuditError(f"HISTORY_SHAPE_OR_FINITE:{stored['id']}:{name}")
        solvers[name] = recompute_solver(context, contract, scenario_contract, states, work, stored[f"{name}_audit"])
        solvers[name]["states"] = states
        solvers[name]["work"] = work
    left, right = solvers["rk4"], solvers["dop853"]
    q_error = np.abs(left["states"][:, 7:15] - right["states"][:, 7:15])
    dq_error = np.abs(left["states"][:, 15:23] - right["states"][:, 15:23])
    cross = {
        "qR_max_abs_rad": float(np.max(q_error[:, :6])),
        "qP_max_abs_m": float(np.max(q_error[:, 6:])),
        "dqR_max_abs_rad_s": float(np.max(dq_error[:, :6])),
        "dqP_max_abs_m_s": float(np.max(dq_error[:, 6:])),
        "base_position_max_abs_m": float(np.max(np.abs(left["states"][:, :3] - right["states"][:, :3]))),
        "base_attitude_max_rad": max(attitude_distance(a[3:7], b[3:7]) for a, b in zip(left["states"], right["states"])),
        "base_linear_twist_max_abs_m_s": float(np.max(np.abs(left["base_twist_history"][:, :3] - right["base_twist_history"][:, :3]))),
        "base_angular_twist_max_abs_rad_s": float(np.max(np.abs(left["base_twist_history"][:, 3:] - right["base_twist_history"][:, 3:]))),
        "weighted_task_error_max_abs_per_s": float(np.max(np.abs(left["weighted_error_history_per_s"] - right["weighted_error_history_per_s"]))),
    }
    thresholds = contract["thresholds"]
    cross_match = all(close(cross[key], stored["solver_cross"][key], atol=5.0e-11) for key in cross)
    cross_pass = all((
        cross["qR_max_abs_rad"] <= thresholds["rk4_dop853_qR_max_abs_rad"],
        cross["dqR_max_abs_rad_s"] <= thresholds["rk4_dop853_dqR_max_abs_rad_s"],
        cross["base_position_max_abs_m"] <= thresholds["rk4_dop853_base_position_max_abs_m"],
        cross["base_attitude_max_rad"] <= thresholds["rk4_dop853_base_attitude_max_rad"],
        cross["weighted_task_error_max_abs_per_s"] <= thresholds["rk4_dop853_weighted_task_error_max_abs_per_s"],
    ))
    rk4_augmented = [
        [*physical_state, work_value]
        for physical_state, work_value in zip(
            stored["rk4_physical_state_history_23"],
            stored["rk4_auxiliary_work_history_J"],
        )
    ]
    replay = stored["deterministic_replay"]
    replay_hash_match = canonical_sha256(rk4_augmented) == replay["first_history_canonical_sha256"] == replay["second_history_canonical_sha256"]
    return {
        "id": stored["id"],
        "dimension": stored["dimension"],
        "controller_enabled": stored["controller_enabled"],
        "rk4": {key: value for key, value in left.items() if key not in {"states", "work", "base_twist_history", "weighted_error_history_per_s"}},
        "dop853": {key: value for key, value in right.items() if key not in {"states", "work", "base_twist_history", "weighted_error_history_per_s"}},
        "tracking": {
            "rk4_initial_per_s": left["weighted_error_norm_initial_per_s"],
            "rk4_final_per_s": left["weighted_error_norm_final_per_s"],
            "rk4_rms_per_s": left["weighted_error_norm_rms_per_s"],
        },
        "solver_cross": cross,
        "solver_cross_stored_match": cross_match,
        "solver_cross_pass": cross_pass,
        "replay_hash_match": replay_hash_match,
        "all_pass": left["stored_field_match"] and right["stored_field_match"] and left["passes_thresholds"] and right["passes_thresholds"] and cross_match and cross_pass and replay_hash_match,
    }


def contract_semantics(contract: Mapping[str, Any], lock: Mapping[str, Any]) -> dict[str, bool]:
    admission = contract["execution_resource_admission"]
    scenarios = contract["scenarios"]
    exact_scenarios = all(
        (row["id"], row["comparison_pair"], row["task"], row["controller_enabled"], len(row["desired_twist_native"])) == expected
        for row, expected in zip(scenarios, EXPECTED_SCENARIOS)
    ) and len(scenarios) == 4
    unit_safe = (
        scenarios[0]["desired_units"] == scenarios[1]["desired_units"] == ["m/s", "m/s", "m/s", "1/s", "1/s"]
        and scenarios[2]["desired_units"] == scenarios[3]["desired_units"] == ["m/s", "m/s", "m/s", "rad/s", "rad/s", "rad/s"]
        and contract["task_semantics"]["weighted_error_unit"] == "1/s"
        and contract["task_semantics"]["mixed_unweighted_linear_angular_norm_credit"] is False
    )
    boundaries = contract["claim_boundary"]
    return {
        "schema_scope": contract["schema"] == "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_CONTRACT_V1" and contract["authority_scope"] == "APPEND_ONLY_ZERO_MOMENTUM_RIGID_ROOT_FRAME_TWIST_RATE_DIAGNOSTIC_ONLY",
        "planned_not_self_certifying": "PLANNED_NOT_YET_EXECUTED" in contract["maximum_contract_claim"] and all(value is False for value in boundaries.values()),
        "four_runs_three_logical_labels": exact_scenarios and {row["id"].split("_")[0] for row in scenarios} == {"C0", "C1", "C2"},
        "unit_safe_task_contract": unit_safe,
        "memory_admission_exact_and_above_six": admission["threshold_gib"] == 6.0 and admission["admission_samples_gib"] == EXPECTED_ADMISSION_SAMPLES_GIB and admission["runtime_pre_solve_samples_gib"] == EXPECTED_RUNTIME_SAMPLES_GIB and min(admission["admission_samples_gib"]) >= 6.0 and min(admission["runtime_pre_solve_samples_gib"]) >= 6.0 and admission["admission_pass"] is True and admission["runtime_pre_solve_pass"] is True,
        "memory_has_no_scientific_authority": admission["scientific_or_release_authority"] is False and admission["classification"] == "EXECUTION_RESOURCE_GATE_ONLY__NOT_SCIENTIFIC_THRESHOLD",
        "root_frame_rate_not_pose_tracking": contract["task_semantics"]["twist_expression_frame"] == "INSTANTANEOUS_SPACECRAFT_BUS_ROOT_FRAME" and contract["task_semantics"]["reference_is_inertial_trajectory"] is False and contract["task_semantics"]["pose_or_attitude_tracking_claim_allowed"] is False,
        "fixed_O_angular_momentum_threshold_frozen": contract["thresholds"]["angular_momentum_about_fixed_inertial_origin_residual_max_kg_m2_s"] == 1.0e-11,
        "direct_source_ledger_equals_lock": contract["source_pins"] == lock["candidate_direct_source_pins"],
        "review_and_release_false": contract["review_status"] == "PENDING_OWNER_REVIEW" and contract["next_stage_authorized"] is False and contract["release_credit"] is False,
    }


def manifest_csv_ok(docs: Mapping[str, Any], lock: Mapping[str, Any], prefix: str) -> bool:
    manifest = docs["manifest"]
    if manifest["inventory_count"] != len(manifest["inventory"]):
        return False
    records_ok = all(pin_matches(row) for row in manifest["inventory"])
    pins = lock[f"{prefix}_pins"]
    csv_pin = _pin_by_id(pins, f"{prefix}_sha_csv")
    with (PROJECT_ROOT / csv_pin["path"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    csv_ok = [row["path"] for row in rows] == [row["path"] for row in manifest["inventory"]] and all(
        int(row["bytes"]) == record["bytes"] and row["sha256"] == record["sha256"]
        for row, record in zip(rows, manifest["inventory"])
    )
    return records_ok and csv_ok and manifest["next_stage_authorized"] is False and manifest["release_credit"] is False


def original_and_rebind_semantics(candidate: Mapping[str, Any], rebind: Mapping[str, Any]) -> dict[str, bool]:
    gate = candidate["gate"]
    rb_gate = rebind["gate"]
    old_metric = candidate["evidence"]["upstream_transitive_binding"]["metric"]
    mismatches = [row for row in old_metric["records"] if not row["match"]]
    rb_contract = rebind["contract"]
    single = rb_contract["single_rebind"]
    return {
        "original_gate_truthfully_19_of_20": gate["gate_passed"] is False and gate["summary"] == {"passed": 19, "total": 20, "failed": [EXPECTED_CANDIDATE_FAILURE]} and gate["checks"][EXPECTED_CANDIDATE_FAILURE] is False and sum(bool(value) for value in gate["checks"].values()) == 19,
        "original_has_exactly_one_declared_metric_mismatch": old_metric["matched"] == 6 and old_metric["total"] == 7 and old_metric["all_match"] is False and len(mismatches) == 1 and mismatches[0]["id"] == "precontact_tracking_parent_gate",
        "single_rebind_old_and_current_bytes_hash_exact": single["pin_id"] == "precontact_tracking_parent_gate" and single["declared_old_bytes"] == mismatches[0]["declared_bytes"] and single["declared_old_sha256"] == mismatches[0]["declared_sha256"] and single["current_bytes"] == mismatches[0]["actual_bytes"] and single["current_sha256"] == mismatches[0]["actual_sha256"],
        "rebind_gate_16_of_16": rb_gate["gate_passed"] is True and rb_gate["summary"] == {"passed": 16, "total": 16, "failed": []} and all(rb_gate["checks"].values()),
        "rebind_keeps_original_gate_failed_and_unreissued": rb_gate["original_time_domain_gate_passed"] is False and rb_gate["original_time_domain_gate_reissued"] is False and rebind["evidence"]["original_time_domain_gate_summary"] == gate["summary"],
        "rebind_authorities_all_false": all(value is False for value in rb_gate["authority_boundaries"].values()) and all(value is False for value in rebind["evidence"]["authority_boundaries"].values()) and all(value is False for value in rb_contract["authority_boundaries"].values()),
    }


def candidate_authorities_false(candidate: Mapping[str, Any]) -> bool:
    gate = candidate["gate"]
    evidence = candidate["evidence"]
    contract = candidate["contract"]
    return all((
        all(evidence["authority_boundaries"].get(key) is False for key in FALSE_AUTHORITY_KEYS),
        all(gate["authority_boundaries"].get(key) is False for key in FALSE_AUTHORITY_KEYS),
        gate["parent_dynamics_gate_reissued"] is False,
        gate["parent_control_gate_reissued"] is False,
        gate["next_stage_authorized"] is False,
        gate["release_credit"] is False,
        contract["next_stage_authorized"] is False,
        contract["release_credit"] is False,
    ))


def run_negative_controls(base: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    def record(identifier: str, caught: bool) -> None:
        rows.append({"id": identifier, "caught": bool(caught)})

    bad_lock = copy.deepcopy(base["lock"]); bad_lock["candidate_pins"][0]["sha256"] = "0" * 64
    record("XNC01_HASH_TAMPER", not pin_audit(bad_lock["candidate_pins"])["all_match"])
    bad_contract = copy.deepcopy(base["candidate"]["contract"]); bad_contract["scenarios"][0]["desired_units"][0] = "mm/s"
    record("XNC02_UNIT_TAMPER", not all(contract_semantics(bad_contract, base["lock"]).values()))
    bad_memory = copy.deepcopy(base["candidate"]["contract"]); bad_memory["execution_resource_admission"]["admission_samples_gib"][0] = 5.99
    record("XNC03_MEMORY_TAMPER", not contract_semantics(bad_memory, base["lock"])["memory_admission_exact_and_above_six"])
    bad_gate = copy.deepcopy(base["candidate"]); bad_gate["gate"]["authority_boundaries"]["control_valid"] = True
    record("XNC04_PERMISSION_TAMPER", not candidate_authorities_false(bad_gate))
    bad_parent = copy.deepcopy(base["candidate"]); bad_parent["gate"]["parent_control_gate_reissued"] = True
    record("XNC05_PARENT_GATE_REISSUE_TAMPER", not candidate_authorities_false(bad_parent))
    candidate_files = set(base["candidate_files"])
    record("XNC06_CANDIDATE_MISSING_README", not inventory_exact(candidate_files - {"README.md"}, base["lock"]["candidate_allowed_files"]))
    record("XNC07_CANDIDATE_EXTRA_FILE", not inventory_exact(candidate_files | {"rogue.txt"}, base["lock"]["candidate_allowed_files"]))
    audit_files = set(base["audit_files"])
    record("XNC08_AUDIT_MISSING_TEST", not inventory_exact(audit_files - {"tests/test_time_domain_external_audit.py"}, AUDIT_ALLOWED_FILES))
    record("XNC09_AUDIT_EXTRA_FILE", not inventory_exact(audit_files | {"rogue.txt"}, AUDIT_ALLOWED_FILES))
    bad_rebind = copy.deepcopy(base["rebind"]); bad_rebind["gate"]["original_time_domain_gate_reissued"] = True
    record("XNC10_REBIND_PERMISSION_TAMPER", not all(original_and_rebind_semantics(base["candidate"], bad_rebind).values()))
    bad_old = copy.deepcopy(base["candidate"]); bad_old["gate"]["gate_passed"] = True
    record("XNC11_ORIGINAL_19_OF_20_FORGED_PASS", not all(original_and_rebind_semantics(bad_old, base["rebind"]).values()))
    bad_fixed_o = copy.deepcopy(base["candidate"]["contract"]); bad_fixed_o["thresholds"]["angular_momentum_about_fixed_inertial_origin_residual_max_kg_m2_s"] = 1.0
    record("XNC12_FIXED_O_THRESHOLD_TAMPER", not contract_semantics(bad_fixed_o, base["lock"])["fixed_O_angular_momentum_threshold_frozen"])
    return {"passed": sum(row["caught"] for row in rows), "total": len(rows), "all_pass": all(row["caught"] for row in rows), "records": rows}


def validate() -> dict[str, Any]:
    lock = strict_load(LOCK_PATH)
    if canonical_sha256(lock) != EXPECTED_LOCK_CANONICAL_SHA256:
        raise AuditError("SOURCE_LOCK_CANONICAL_SHA256_DRIFT")
    candidate = _candidate_documents(lock)
    rebind = _rebind_documents(lock)
    pin_groups = {
        name: pin_audit(lock[name])
        for name in (
            "candidate_pins",
            "rebind_pins",
            "candidate_direct_source_pins",
            "rebind_direct_source_pins",
            "plant_transitive_source_pins",
            "metric_current_rebound_source_pins",
            "control_parent_transitive_source_pins",
        )
    }
    context = load_physics_context(lock, candidate["contract"])
    scenario_by_id = {row["id"]: row for row in candidate["contract"]["scenarios"]}
    recomputed = [
        recompute_scenario(context, candidate["contract"], scenario_by_id[row["id"]], row)
        for row in candidate["evidence"]["scenarios"]
    ]
    by_id = {row["id"]: row for row in recomputed}
    comparisons: dict[str, Any] = {}
    for pair, uncontrolled_id, controlled_id in (
        ("PAIR_5D", "C0_UNCONTROLLED_5D_REFERENCE", "C1_CONTROLLED_5D"),
        ("PAIR_6D", "C0_UNCONTROLLED_6D_REFERENCE", "C2_CONTROLLED_6D"),
    ):
        uncontrolled = by_id[uncontrolled_id]["tracking"]
        controlled = by_id[controlled_id]["tracking"]
        comparisons[pair] = {
            "uncontrolled_id": uncontrolled_id,
            "controlled_id": controlled_id,
            "final_error_ratio_controlled_to_uncontrolled": controlled["rk4_final_per_s"] / uncontrolled["rk4_final_per_s"],
            "rms_error_ratio_controlled_to_uncontrolled": controlled["rk4_rms_per_s"] / uncontrolled["rk4_rms_per_s"],
        }
    thresholds = candidate["contract"]["thresholds"]
    comparisons_pass = all(
        row["final_error_ratio_controlled_to_uncontrolled"] <= thresholds["controlled_final_error_ratio_to_same_task_uncontrolled_max"]
        and row["rms_error_ratio_controlled_to_uncontrolled"] <= thresholds["controlled_rms_error_ratio_to_same_task_uncontrolled_max"]
        and close(row["final_error_ratio_controlled_to_uncontrolled"], candidate["evidence"]["same_dimension_comparisons"][pair]["final_error_ratio_controlled_to_uncontrolled"], atol=3.0e-12)
        and close(row["rms_error_ratio_controlled_to_uncontrolled"], candidate["evidence"]["same_dimension_comparisons"][pair]["rms_error_ratio_controlled_to_uncontrolled"], atol=3.0e-12)
        for pair, row in comparisons.items()
    )
    contract_checks = contract_semantics(candidate["contract"], lock)
    lineage_checks = original_and_rebind_semantics(candidate, rebind)
    candidate_files = observed_files(CANDIDATE)
    rebind_files = observed_files(REBIND)
    audit_files = observed_files(PACKAGE)
    base = {"lock": lock, "candidate": candidate, "rebind": rebind, "candidate_files": candidate_files, "audit_files": audit_files}
    negatives = run_negative_controls(base)
    checks = {
        "A01_SOURCE_LOCK_CANONICAL_AND_ALL_EXACT_PIN_GROUPS": all(row["all_match"] for row in pin_groups.values()),
        "A02_CANDIDATE_AND_REBIND_STRICT_INVENTORY_NO_CACHE": inventory_exact(candidate_files, lock["candidate_allowed_files"]) and inventory_exact(rebind_files, lock["rebind_allowed_files"]) and not forbidden_cache(CANDIDATE) and not forbidden_cache(REBIND),
        "A03_ORIGINAL_CANDIDATE_TRUTHFULLY_REMAINS_19_OF_20": lineage_checks["original_gate_truthfully_19_of_20"],
        "A04_SINGLE_PARENT_HOLD_REBIND_16_OF_16_WITHOUT_GATE_REISSUE": all(lineage_checks.values()),
        "A05_CONTRACT_FOUR_RUNS_UNITS_ROOT_FRAME_AND_MEMORY_EXACT": all(contract_checks.values()),
        "A06_FOUR_PHYSICAL_HISTORIES_AND_THREE_LOGICAL_LABELS_NOT_CONFLATED": len(recomputed) == 4 and {row["id"].split("_")[0] for row in recomputed} == {"C0", "C1", "C2"},
        "A07_C0_C1_C2_SAME_DIMENSION_TRACKING_COMPARISONS_RECOMPUTED": comparisons_pass,
        "A08_RK4_DOP853_PER_UNIT_ERRORS_RECOMPUTED": all(row["solver_cross_stored_match"] and row["solver_cross_pass"] for row in recomputed),
        "A09_LINEAR_AND_FIXED_O_ANGULAR_MOMENTUM_RECOMPUTED": all(row[solver]["passes_thresholds"] and row[solver]["stored_field_match"] for row in recomputed for solver in ("rk4", "dop853")),
        "A10_WORK_ENERGY_RESIDUAL_RECOMPUTED": all(row[solver]["max_work_energy_absolute_J"] <= thresholds["work_energy_absolute_max_J"] and row[solver]["max_work_energy_relative"] <= thresholds["work_energy_relative_max"] for row in recomputed for solver in ("rk4", "dop853")),
        "A11_QUATERNION_AND_JOINT_LIMITS_RECOMPUTED": all(row[solver]["max_quaternion_norm_error"] <= thresholds["quaternion_norm_error_max"] and row[solver]["revolute_joint_limit_min_margin_rad"] >= 0.0 and row[solver]["prismatic_joint_limit_min_margin_m"] >= 0.0 for row in recomputed for solver in ("rk4", "dop853")),
        "A12_IDEAL_2P_LOCK_AND_KKT_RECOMPUTED": all(row[solver]["qP_position_lock_max_abs_m"] <= thresholds["qP_position_lock_max_abs_m"] and row[solver]["dqP_lock_max_abs_m_s"] <= thresholds["dqP_lock_max_abs_m_s"] and row[solver]["max_kkt_equilibrium_R_abs_Nm"] <= thresholds["kkt_equilibrium_R_max_abs_Nm"] and row[solver]["max_kkt_equilibrium_P_abs_N"] <= thresholds["kkt_equilibrium_P_max_abs_N"] for row in recomputed for solver in ("rk4", "dop853")),
        "A13_DETERMINISTIC_PRIMARY_HISTORY_HASH_RECONSTRUCTED": all(row["replay_hash_match"] for row in recomputed),
        "A14_CANDIDATE_AND_REBIND_MANIFEST_SHA_TABLES_EXACT": manifest_csv_ok(candidate, lock, "candidate") and manifest_csv_ok(rebind, lock, "rebind"),
        "A15_ALL_PARENT_HARDWARE_SAFE_AND_RELEASE_AUTHORITIES_FALSE": candidate_authorities_false(candidate) and lineage_checks["rebind_authorities_all_false"],
        "A16_PARENT_DYNAMICS_AND_CONTROL_GATE_BYTES_REMAIN_FIXED_HOLD": candidate["evidence"]["upstream_gate_state"]["parent_dynamics_hold_retained"] is True and candidate["evidence"]["upstream_gate_state"]["parent_control_hold_retained"] is True,
        "A17_EXTERNAL_NEGATIVE_CONTROLS_HASH_UNIT_PERMISSION_AND_MISSING_FILE": negatives["all_pass"] and negatives["passed"] == negatives["total"] == 12,
        "A18_EXTERNAL_AUDIT_INVENTORY_EXACT_AND_NO_CANDIDATE_IMPORT": inventory_exact(audit_files, AUDIT_ALLOWED_FILES) and not forbidden_cache(PACKAGE) and all(not str(Path(path)).startswith(str(CANDIDATE.resolve())) and not str(Path(path)).startswith(str(REBIND.resolve())) for path in context["loaded_paths"]),
    }
    receipt = {
        "schema": "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_EXTERNAL_AUDIT_GATE_V1",
        "audit_architecture": "PACKAGE_EXTERNAL_FIXED_SOURCE_LOCK__NO_CANDIDATE_OR_REBIND_CORE_IMPORT__INDEPENDENT_HISTORY_RECOMPUTATION",
        "source_lock_canonical_sha256": EXPECTED_LOCK_CANONICAL_SHA256,
        "checks": checks,
        "passed": sum(bool(value) for value in checks.values()),
        "total": len(checks),
        "all_pass": all(checks.values()),
        "technical_verdict": PASS_VERDICT if all(checks.values()) else HOLD_VERDICT,
        "maximum_claim": PASS_VERDICT if all(checks.values()) else HOLD_CLAIM,
        "original_candidate_gate": {"passed": 19, "total": 20, "gate_passed": False, "failed": [EXPECTED_CANDIDATE_FAILURE], "reissued": False},
        "metric_parent_rebind": {"passed": 16, "total": 16, "gate_passed": True, "original_gate_reissued": False},
        "contract_semantics": contract_checks,
        "lineage_semantics": lineage_checks,
        "pin_audits": pin_groups,
        "recomputed_scenarios": recomputed,
        "recomputed_comparisons": comparisons,
        "execution_memory_admission": {"threshold_gib": 6.0, "admission_samples_gib": EXPECTED_ADMISSION_SAMPLES_GIB, "runtime_pre_solve_samples_gib": EXPECTED_RUNTIME_SAMPLES_GIB, "scientific_or_release_authority": False},
        "momentum_reference": {"linear": "INERTIAL", "angular": "ABOUT_FIXED_INERTIAL_ORIGIN_O", "mixed_scalar_norm_credit": False},
        "negative_controls": negatives,
        "authority_boundaries": {
            "parent_gate_reissued": False,
            "parent_gate_credit": False,
            "original_candidate_gate_reissued": False,
            "task_metric_parent_gate_reissued": False,
            "parent_dynamics_or_control_gate_credit": False,
            "precontact_tracking_validated": False,
            "pose_or_attitude_tracking_validated": False,
            "control_valid": False,
            "hardware_valid": False,
            "collision_valid": False,
            "contact_valid": False,
            "flex_valid": False,
            "target_attached": False,
            "m01_path_bound": False,
            "safe_gate_credit": False,
            "sim13_credit": False,
            "non_abort_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "time_domain_diagnostic_executed": True,
        "original_candidate_gate_passed": False,
        "original_candidate_gate_reissued": False,
        "precontact_tracking_validated": False,
        "pose_or_attitude_tracking_validated": False,
        "control_valid": False,
        "hardware_valid": False,
        "collision_valid": False,
        "contact_valid": False,
        "flex_valid": False,
        "m01_path_bound": False,
        "safe_gate_credit": False,
        "sim13_credit": False,
        "non_abort_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }
    return builtin(receipt)


def pretty(value: Any) -> str:
    return json.dumps(builtin(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    receipt = validate()
    if args.stdout:
        print(pretty(receipt), end="")
        return 0 if receipt["all_pass"] else 2
    if args.check:
        stored = strict_load(RESULT_PATH)
        exact = canonical_bytes(stored) == canonical_bytes(receipt)
        result = {"recompute_pass": receipt["all_pass"], "stored_canonical_exact": exact, "all_pass": receipt["all_pass"] and exact}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["all_pass"] else 3
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(pretty(receipt), encoding="utf-8", newline="\n")
    print(json.dumps({"passed": receipt["passed"], "total": receipt["total"], "verdict": receipt["technical_verdict"]}, indent=2))
    return 0 if receipt["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
